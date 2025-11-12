"""Helpers for reading the Segment 2A S0 gate receipt."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, Tuple

import polars as pl

from ..s0_gate.exceptions import err
from .dictionary import render_dataset_path


@dataclass(frozen=True)
class GateReceiptAssetRef:
    """Minimal description of a sealed asset listed inside the S0 receipt."""

    asset_id: str
    partition: tuple[str, ...]
    schema_ref: str


@dataclass(frozen=True)
class GateReceiptSummary:
    """Parsed representation of the gate receipt."""

    manifest_fingerprint: str
    parameter_hash: str
    validation_bundle_path: str
    flag_sha256_hex: str
    verified_at_utc: str
    assets: tuple[GateReceiptAssetRef, ...]
    path: Path


@dataclass(frozen=True)
class SealedInputRecord:
    """Row from the sealed_inputs_v1 manifest."""

    asset_id: str
    asset_kind: str
    schema_ref: str
    catalog_path: str
    version_tag: str
    sha256_hex: str
    size_bytes: int
    partition_keys: tuple[str, ...]
    license_class: str | None
    notes: str | None


def load_gate_receipt(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> GateReceiptSummary:
    """Load and lightly validate the 2A.S0 gate receipt."""

    receipt_rel = render_dataset_path(
        "s0_gate_receipt_2A",
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    receipt_path = (base_path / receipt_rel).resolve()
    if not receipt_path.exists():
        raise err(
            "E_S0_RECEIPT_MISSING",
            f"S0 receipt not found at '{receipt_path}'",
        )

    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err("E_S0_RECEIPT_INVALID", f"S0 receipt is not valid JSON: {exc}") from exc

    _expect(payload, "manifest_fingerprint", manifest_fingerprint)
    parameter_hash = _expect(payload, "parameter_hash")
    validation_bundle_path = _expect(payload, "validation_bundle_path")
    flag_sha256_hex = _expect(payload, "flag_sha256_hex")
    verified_at_utc = _expect(payload, "verified_at_utc")

    sealed_inputs = payload.get("sealed_inputs") or []
    if not isinstance(sealed_inputs, Sequence):
        raise err("E_S0_RECEIPT_INVALID", "sealed_inputs must be an array")

    assets = tuple(_parse_asset(entry) for entry in sealed_inputs)

    return GateReceiptSummary(
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        validation_bundle_path=validation_bundle_path,
        flag_sha256_hex=flag_sha256_hex,
        verified_at_utc=verified_at_utc,
        assets=assets,
        path=receipt_path,
    )


def load_sealed_inputs_inventory(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> Tuple[SealedInputRecord, ...]:
    """Load the sealed_inputs_v1 manifest for the provided fingerprint."""

    inventory_rel = render_dataset_path(
        "sealed_inputs_v1",
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    inventory_path = (base_path / inventory_rel).resolve()
    if not inventory_path.exists():
        raise err(
            "2A-S0-050",
            f"sealed_inputs_v1 not found at '{inventory_path}'",
        )
    table = pl.read_parquet(inventory_path)
    records = []
    for row in table.to_dicts():
        records.append(
            SealedInputRecord(
                asset_id=str(row["asset_id"]),
                asset_kind=str(row.get("asset_kind") or ""),
                schema_ref=str(row["schema_ref"]),
                catalog_path=str(row["catalog_path"]),
                version_tag=str(row.get("version_tag") or ""),
                sha256_hex=str(row["sha256_hex"]),
                size_bytes=int(row.get("size_bytes") or 0),
                partition_keys=tuple(row.get("partition_keys") or ()),
                license_class=(
                    str(row["license_class"])
                    if row.get("license_class") is not None
                    else None
                ),
                notes=str(row["notes"]) if row.get("notes") is not None else None,
            )
        )
    return tuple(records)


def load_determinism_receipt(
    *,
    base_path: Path,
    manifest_fingerprint: str,
) -> Mapping[str, object]:
    """Load the determinism receipt emitted by S0 for the given fingerprint."""

    receipt_path = (
        base_path
        / "reports"
        / "l1"
        / "s0_gate"
        / f"fingerprint={manifest_fingerprint}"
        / "determinism_receipt.json"
    ).resolve()
    if not receipt_path.exists():
        raise err(
            "2A-S0-044",
            f"determinism receipt missing at '{receipt_path}'",
        )
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err("2A-S0-044", f"determinism receipt invalid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise err("2A-S0-044", "determinism receipt must be a JSON object")
    return payload


def _expect(payload: Mapping[str, object], field: str, expected: str | None = None) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise err("E_S0_RECEIPT_INVALID", f"S0 receipt missing string field '{field}'")
    if expected is not None and value != expected:
        raise err(
            "E_S0_RECEIPT_MISMATCH",
            f"S0 receipt '{field}' was '{value}' expected '{expected}'",
        )
    return value


def _parse_asset(entry: object) -> GateReceiptAssetRef:
    if not isinstance(entry, Mapping):
        raise err("E_S0_RECEIPT_INVALID", "sealed_inputs entries must be objects")
    asset_id = entry.get("id")
    if not isinstance(asset_id, str) or not asset_id:
        raise err("E_S0_RECEIPT_INVALID", "sealed_inputs entries must declare string id")
    partition_obj = entry.get("partition") or ()
    if not isinstance(partition_obj, Sequence):
        raise err("E_S0_RECEIPT_INVALID", f"sealed asset '{asset_id}' partition must be an array")
    partition: tuple[str, ...] = tuple(
        str(item) for item in partition_obj if isinstance(item, str)
    )
    schema_ref = entry.get("schema_ref")
    if not isinstance(schema_ref, str) or not schema_ref:
        raise err(
            "E_S0_RECEIPT_INVALID",
            f"sealed asset '{asset_id}' missing schema_ref",
        )
    return GateReceiptAssetRef(
        asset_id=asset_id,
        partition=partition,
        schema_ref=schema_ref,
    )


__all__ = [
    "GateReceiptAssetRef",
    "GateReceiptSummary",
    "SealedInputRecord",
    "load_gate_receipt",
    "load_sealed_inputs_inventory",
    "load_determinism_receipt",
]

