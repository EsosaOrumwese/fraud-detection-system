"""Helpers for reading the Segment 2B S0 gate receipt."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ..s0_gate.exceptions import err
from .dictionary import render_dataset_path


@dataclass(frozen=True)
class GateReceiptAssetRef:
    """Minimal description of a sealed asset listed inside the S0 receipt."""

    asset_id: str
    partition: tuple[str, ...]
    schema_ref: str


@dataclass(frozen=True)
class SealedInputRecord:
    """Parsed representation of a sealed_inputs_v1 inventory row."""

    asset_id: str
    version_tag: str
    sha256_hex: str
    catalog_path: str
    partition: tuple[str, ...]
    schema_ref: str


@dataclass(frozen=True)
class GateReceiptSummary:
    """Parsed representation of the 2B S0 gate receipt."""

    manifest_fingerprint: str
    seed: str
    parameter_hash: str
    validation_bundle_path: str
    flag_sha256_hex: str
    verified_at_utc: str
    assets: tuple[GateReceiptAssetRef, ...]
    catalogue_resolution: Mapping[str, str]
    determinism_receipt: Mapping[str, object]
    path: Path


def load_gate_receipt(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> GateReceiptSummary:
    """Load and lightly validate the 2B.S0 gate receipt."""

    receipt_rel = render_dataset_path(
        "s0_gate_receipt_2B",
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

    _expect(payload, "segment", "2B")
    _expect(payload, "state", "S0")
    _expect(payload, "manifest_fingerprint", manifest_fingerprint)
    seed = _expect(payload, "seed")
    parameter_hash = _expect(payload, "parameter_hash")
    validation_bundle_path = _expect(payload, "validation_bundle_path")
    flag_sha256_hex = _expect(payload, "flag_sha256_hex")
    verified_at_utc = _expect(payload, "verified_at_utc")

    sealed_inputs = payload.get("sealed_inputs") or []
    if not isinstance(sealed_inputs, Sequence):
        raise err("E_S0_RECEIPT_INVALID", "sealed_inputs must be an array")

    assets = tuple(_parse_asset(entry) for entry in sealed_inputs)
    catalogue_resolution = payload.get("catalogue_resolution") or {}
    if not isinstance(catalogue_resolution, Mapping):
        catalogue_resolution = {}
    determinism_receipt = payload.get("determinism_receipt") or {}
    if not isinstance(determinism_receipt, Mapping):
        determinism_receipt = {}

    return GateReceiptSummary(
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        parameter_hash=parameter_hash,
        validation_bundle_path=validation_bundle_path,
        flag_sha256_hex=flag_sha256_hex,
        verified_at_utc=verified_at_utc,
        assets=assets,
        catalogue_resolution=catalogue_resolution,
        determinism_receipt=determinism_receipt,
        path=receipt_path,
    )


def load_sealed_inputs_inventory(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> tuple[SealedInputRecord, ...]:
    """Load the sealed_inputs_v1 inventory referenced by the manifest."""

    inventory_rel = render_dataset_path(
        "sealed_inputs_v1",
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    inventory_path = (base_path / inventory_rel).resolve()
    if not inventory_path.exists():
        raise err(
            "E_SEALED_INPUTS_MISSING",
            f"sealed_inputs_v1 inventory not found at '{inventory_path}'",
        )
    try:
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise err(
            "E_SEALED_INPUTS_INVALID",
            f"sealed_inputs_v1 inventory at '{inventory_path}' is not valid JSON",
        ) from exc
    if not isinstance(payload, Sequence):
        raise err(
            "E_SEALED_INPUTS_INVALID",
            "sealed_inputs_v1 inventory must be an array of objects",
        )
    records: list[SealedInputRecord] = []
    for entry in payload:
        if not isinstance(entry, Mapping):
            raise err(
                "E_SEALED_INPUTS_INVALID",
                "sealed_inputs_v1 entries must be objects",
            )
        asset_id = _expect_string(entry, "asset_id", context="sealed_inputs_v1")
        version_tag = _expect_string(entry, "version_tag", context=asset_id)
        sha256_hex = _expect_string(entry, "sha256_hex", context=asset_id)
        catalog_path = _expect_string(entry, "path", context=asset_id)
        schema_ref = _expect_string(entry, "schema_ref", context=asset_id)
        partition_list = entry.get("partition") or []
        if not isinstance(partition_list, Sequence):
            raise err(
                "E_SEALED_INPUTS_INVALID",
                f"sealed asset '{asset_id}' partition must be an array",
            )
        partition = tuple(str(item) for item in partition_list if isinstance(item, str))
        records.append(
            SealedInputRecord(
                asset_id=asset_id,
                version_tag=version_tag,
                sha256_hex=sha256_hex,
                catalog_path=catalog_path,
                partition=partition,
                schema_ref=schema_ref,
            )
        )
    return tuple(records)


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


def _expect_string(payload: Mapping[str, object], field: str, *, context: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise err(
            "E_SEALED_INPUTS_INVALID",
            f"sealed asset '{context}' missing string field '{field}'",
        )
    return value


__all__ = [
    "GateReceiptAssetRef",
    "GateReceiptSummary",
    "SealedInputRecord",
    "load_gate_receipt",
    "load_sealed_inputs_inventory",
]

