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
class GateReceiptSummary:
    """Parsed representation of the 2B S0 gate receipt."""

    manifest_fingerprint: str
    seed: str
    parameter_hash: str
    validation_bundle_path: str
    flag_sha256_hex: str
    verified_at_utc: str
    assets: tuple[GateReceiptAssetRef, ...]
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

    return GateReceiptSummary(
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        parameter_hash=parameter_hash,
        validation_bundle_path=validation_bundle_path,
        flag_sha256_hex=flag_sha256_hex,
        verified_at_utc=verified_at_utc,
        assets=assets,
        path=receipt_path,
    )


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


__all__ = ["GateReceiptAssetRef", "GateReceiptSummary", "load_gate_receipt"]

