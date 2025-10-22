"""Gate receipt loading for S3 requirements."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from engine.layers.l1.seg_1B.s0_gate.l1.verification import validate_receipt_payload

from ...shared.dictionary import render_dataset_path
from ..exceptions import err


@dataclass(frozen=True)
class GateReceipt:
    """Fingerprint-scoped S0 receipt required before reading outlet_catalogue."""

    manifest_fingerprint: str
    flag_sha256_hex: str
    sealed_inputs: tuple[Mapping[str, Any], ...]
    path: Path
    payload: Mapping[str, Any]


def load_gate_receipt(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> GateReceipt:
    """Load and validate the S0 gate receipt for the target fingerprint."""

    rendered = render_dataset_path(
        "s0_gate_receipt_1B",
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    receipt_path = (base_path / rendered).resolve()
    if not receipt_path.exists():
        raise err(
            "E301_NO_PASS_FLAG",
            f"s0_gate_receipt_1B missing for fingerprint '{manifest_fingerprint}' at '{receipt_path}'",
        )
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err(
            "E_RECEIPT_SCHEMA_INVALID",
            f"s0_gate_receipt_1B payload could not be decoded as JSON: {exc}",
        ) from exc

    try:
        validate_receipt_payload(payload)
    except Exception as exc:  # pragma: no cover - err raised below
        raise err("E_RECEIPT_SCHEMA_INVALID", f"receipt schema violation: {exc}") from exc

    observed_fp = payload.get("manifest_fingerprint")
    if observed_fp != manifest_fingerprint:
        raise err(
            "E301_NO_PASS_FLAG",
            "s0 gate receipt manifest_fingerprint mismatch with requested fingerprint",
        )

    flag_hash = str(payload.get("flag_sha256_hex") or "")
    sealed_inputs_raw = payload.get("sealed_inputs", [])
    if not isinstance(sealed_inputs_raw, list):
        raise err(
            "E_RECEIPT_SCHEMA_INVALID",
            "sealed_inputs field must be an array in the receipt payload",
        )
    sealed_inputs: tuple[Mapping[str, Any], ...] = tuple()
    tmp_list: list[Mapping[str, Any]] = []
    for idx, item in enumerate(sealed_inputs_raw):
        if not isinstance(item, Mapping):
            raise err(
                "E_RECEIPT_SCHEMA_INVALID",
                f"sealed_inputs[{idx}] must be an object in the receipt payload",
            )
        tmp_list.append(item)
    sealed_inputs = tuple(tmp_list)

    return GateReceipt(
        manifest_fingerprint=manifest_fingerprint,
        flag_sha256_hex=flag_hash,
        sealed_inputs=sealed_inputs,
        path=receipt_path,
        payload=payload,
    )


__all__ = ["GateReceipt", "load_gate_receipt"]
