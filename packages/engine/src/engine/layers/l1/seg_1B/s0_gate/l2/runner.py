"""L2 orchestration for the Segment 1B S0 gate."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

from ...shared import dictionary as dict_utils
from ...shared.dictionary import load_dictionary
from ..exceptions import err
from ..l1.verification import (
    VerifiedBundle,
    build_sealed_inputs,
    ensure_reference_surfaces,
    validate_receipt_payload,
    verify_bundle,
    verify_license_map_coverage,
    verify_outlet_catalogue_lineage,
)


@dataclass(frozen=True)
class GateInputs:
    """Configuration required to execute the S0 gate."""

    base_path: Path
    output_base_path: Path
    manifest_fingerprint: str
    seed: str
    parameter_hash: str
    notes: Optional[str] = None
    dictionary: Mapping[str, object] | None = None
    validation_bundle_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "seed", str(self.seed))


@dataclass(frozen=True)
class GateResult:
    """Summary returned after a successful run."""

    bundle: VerifiedBundle
    receipt_path: Path
    outlet_catalogue_path: Path


class S0GateRunner:
    """High-level helper that wires the gate verification steps together."""

    def run(self, inputs: GateInputs) -> GateResult:
        dictionary = inputs.dictionary or load_dictionary()
        bundle_dir = self._resolve_bundle_path(inputs, dictionary=dictionary)

        if not bundle_dir.exists():
            raise err(
                "E_BUNDLE_MISSING",
                f"validation bundle '{bundle_dir}' not found",
            )
        if not bundle_dir.is_dir():
            raise err(
                "E_INDEX_INVALID",
                f"validation bundle path '{bundle_dir}' must be a directory",
            )

        verified_bundle = verify_bundle(bundle_dir)

        ensure_reference_surfaces(
            base_path=inputs.base_path,
            dictionary=dictionary,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
        )
        outlet_catalogue_path = verify_outlet_catalogue_lineage(
            base_path=inputs.base_path,
            dictionary=dictionary,
            manifest_fingerprint=inputs.manifest_fingerprint,
            seed=inputs.seed,
        )
        sealed_inputs = build_sealed_inputs(dictionary=dictionary)
        verify_license_map_coverage(sealed_inputs=sealed_inputs, dictionary=dictionary)

        receipt_payload = self._build_receipt_payload(
            inputs=inputs,
            dictionary=dictionary,
            verified_bundle=verified_bundle,
        )
        validate_receipt_payload(receipt_payload)

        receipt_path = self._materialise_receipt(
            payload=receipt_payload,
            inputs=inputs,
            dictionary=dictionary,
        )

        return GateResult(
            bundle=verified_bundle,
            receipt_path=receipt_path,
            outlet_catalogue_path=outlet_catalogue_path,
        )

    def _resolve_bundle_path(
        self, inputs: GateInputs, *, dictionary: Mapping[str, object]
    ) -> Path:
        if inputs.validation_bundle_path is not None:
            return inputs.validation_bundle_path
        rendered = dict_utils.render_dataset_path(
            "validation_bundle_1A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        return (inputs.base_path / rendered).resolve()

    def _build_receipt_payload(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        verified_bundle: VerifiedBundle,
    ) -> dict:
        bundle_path = dict_utils.render_dataset_path(
            "validation_bundle_1A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        timestamp = (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        payload: dict[str, object] = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "validation_bundle_path": bundle_path,
            "flag_sha256_hex": verified_bundle.flag_sha256_hex,
            "verified_at_utc": timestamp,
            "sealed_inputs": build_sealed_inputs(dictionary=dictionary),
        }
        if inputs.notes:
            payload["notes"] = inputs.notes
        return payload

    def _materialise_receipt(
        self,
        *,
        payload: Mapping[str, object],
        inputs: GateInputs,
        dictionary: Mapping[str, object],
    ) -> Path:
        rendered = dict_utils.render_dataset_path(
            "s0_gate_receipt_1B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        target = (inputs.output_base_path / rendered).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        candidate_payload = dict(payload)
        if target.exists():
            existing_payload = json.loads(target.read_text(encoding="utf-8"))
            if (
                "verified_at_utc" in existing_payload
                and candidate_payload.get("verified_at_utc")
                != existing_payload.get("verified_at_utc")
            ):
                candidate_payload["verified_at_utc"] = existing_payload["verified_at_utc"]
            if existing_payload == candidate_payload:
                return target
            raise err(
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                f"receipt already exists at '{target}' with different content",
            )

        content = json.dumps(candidate_payload, indent=2, sort_keys=True).encode("utf-8")
        temp_path = target.parent / f".tmp.{uuid.uuid4().hex}.json"
        try:
            temp_path.write_bytes(content)
            temp_path.replace(target)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
        return target


__all__ = ["S0GateRunner", "GateInputs", "GateResult"]
