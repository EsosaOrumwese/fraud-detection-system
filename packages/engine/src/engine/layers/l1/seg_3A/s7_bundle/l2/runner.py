"""Segment 3A S7 runner – validation bundle assembly and PASS flag."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from engine.layers.l1.seg_3A.s0_gate.exceptions import err
from engine.layers.l1.seg_3A.s0_gate.l0 import aggregate_sha256, expand_files, hash_files, total_size_bytes
from engine.layers.l1.seg_3A.shared import SegmentStateKey, render_dataset_path, write_segment_state_run_report
from engine.layers.l1.seg_3A.shared.dictionary import load_dictionary


@dataclass(frozen=True)
class BundleInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class BundleResult:
    bundle_path: Path
    passed_flag_path: Path
    index_path: Path
    run_report_path: Path
    resumed: bool


class BundleRunner:
    """Assemble the validation bundle and emit the 3A PASS flag."""

    _COMPONENTS: Sequence[tuple[str, str]] = (
        ("s0_gate_receipt_3A", "receipt"),
        ("sealed_inputs_3A", "sealed_inputs"),
        ("s1_escalation_queue", "escalation"),
        ("s2_country_zone_priors", "priors"),
        ("s3_zone_shares", "shares"),
        ("s4_zone_counts", "counts"),
        ("zone_alloc", "zone_alloc"),
        ("zone_alloc_universe_hash", "universe_hash"),
        ("s6_validation_report_3A", "validation_report"),
        ("s6_issue_table_3A", "validation_issues"),
        ("s6_receipt_3A", "validation_receipt"),
    )

    def run(self, inputs: BundleInputs) -> BundleResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        parameter_hash = inputs.parameter_hash
        seed = inputs.seed

        # Precondition: S6 PASS exists
        self._assert_s6_pass(
            base=data_root,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            dictionary=dictionary,
        )

        bundle_dir = data_root / render_dataset_path(
            dataset_id="validation_bundle_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        bundle_dir.mkdir(parents=True, exist_ok=True)
        index_path = bundle_dir / "index.json"
        passed_flag_path = bundle_dir / "_passed.flag"

        components = self._gather_components(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        s6_receipt_digest = self._find_component_digest(components, "s6_receipt_3A")
        bundle_index = self._build_index(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            s6_receipt_digest=s6_receipt_digest,
            components=components,
        )
        bundle_digest = self._compute_bundle_digest(bundle_index)

        # idempotency
        resumed = False
        if index_path.exists():
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if existing != bundle_index:
                raise err("E_IMMUTABILITY", f"validation bundle index differs at '{index_path}'")
            existing_flag = passed_flag_path.read_text(encoding="utf-8").strip()
            if existing_flag != f"sha256_hex = {bundle_digest}":
                raise err("E_IMMUTABILITY", "passed flag mismatch for existing bundle")
            resumed = True
        else:
            index_path.write_text(json.dumps(bundle_index, indent=2, sort_keys=True), encoding="utf-8")
            passed_flag_path.write_text(f"sha256_hex = {bundle_digest}", encoding="utf-8")

        run_report_path = data_root / render_dataset_path(
            dataset_id="s7_run_report_3A",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3A",
            "state": "S7",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "bundle_path": str(bundle_dir),
            "bundle_digest": bundle_digest,
            "index_path": str(index_path),
            "passed_flag_path": str(passed_flag_path),
            "resumed": resumed,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer1",
            segment="3A",
            state="S7",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        report_dataset_path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(
            path=report_dataset_path,
            key=key,
            payload={
                **key.as_dict(),
                "status": "PASS",
                "attempt": 1,
                "bundle_digest": bundle_digest,
                "bundle_path": str(bundle_dir),
                "run_report_path": str(run_report_path),
                "resumed": resumed,
            },
        )

        return BundleResult(
            bundle_path=bundle_dir,
            passed_flag_path=passed_flag_path,
            index_path=index_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    # ----------------------------------------------------------- helpers
    def _assert_s6_pass(
        self,
        *,
        base: Path,
        manifest_fingerprint: str,
        parameter_hash: str,
        dictionary: Mapping[str, object],
    ) -> None:
        state_runs_path = base / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        if not state_runs_path.exists():
            raise err("E_S6_PRECONDITION", "segment_state_runs missing; run S6 before S7")
        passed = False
        for line in state_runs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if (
                payload.get("layer") == "layer1"
                and payload.get("segment") == "3A"
                and payload.get("state") == "S6"
                and str(payload.get("manifest_fingerprint")) == str(manifest_fingerprint)
                and str(payload.get("parameter_hash")) == str(parameter_hash)
                and payload.get("status") == "PASS"
            ):
                passed = True
                break
        if not passed:
            raise err("E_S6_PRECONDITION", "S6 PASS run-report entry missing; cannot emit PASS flag")

    def _gather_components(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        parameter_hash: str,
        seed: int,
    ) -> list[Mapping[str, Any]]:
        components = []
        for dataset_id, role in self._COMPONENTS:
            if dataset_id == "s2_country_zone_priors":
                template_args = {"parameter_hash": parameter_hash}
            elif dataset_id in ("s1_escalation_queue", "s3_zone_shares", "s4_zone_counts"):
                template_args = {"seed": seed, "manifest_fingerprint": manifest_fingerprint}
            elif dataset_id == "zone_alloc":
                template_args = {"seed": seed, "manifest_fingerprint": manifest_fingerprint}
            else:
                template_args = {"manifest_fingerprint": manifest_fingerprint}
            rel_path = render_dataset_path(
                dataset_id=dataset_id,
                template_args=template_args,
                dictionary=dictionary,
            )
            path = data_root / rel_path
            if not path.exists():
                raise err("E_COMPONENT_MISSING", f"bundle component '{dataset_id}' missing at '{path}'")
            entry = self._entry_for(dataset_id, dictionary)
            schema_ref = entry.get("schema_ref")
            if not isinstance(schema_ref, str):
                raise err("E_DICTIONARY_RESOLUTION_FAILED", f"schema_ref missing for {dataset_id}")
            files = expand_files(path)
            digests = hash_files(files, error_prefix=dataset_id)
            digest = aggregate_sha256(digests)
            size_bytes = total_size_bytes(digests)
            components.append(
                {
                    "logical_id": dataset_id,
                    "role": entry.get("description", role),
                    "path": str(path),
                    "schema_ref": schema_ref,
                    "sha256_hex": digest,
                    "size_bytes": size_bytes,
                    "notes": entry.get("notes"),
                }
            )
        components.sort(key=lambda c: c["path"])
        return components

    def _build_index(
        self,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        s6_receipt_digest: str,
        components: Iterable[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        return {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "s6_receipt_digest": s6_receipt_digest,
            "members": list(components),
        }

    def _compute_bundle_digest(self, index: Mapping[str, Any]) -> str:
        concat = "".join(item["sha256_hex"] for item in index.get("members", []))
        from hashlib import sha256

        return sha256(concat.encode()).hexdigest()

    def _entry_for(self, dataset_id: str, dictionary: Mapping[str, object]) -> Mapping[str, object]:
        from engine.layers.l1.seg_3A.shared.dictionary import get_dataset_entry

        entry = get_dataset_entry(dataset_id, dictionary=dictionary)
        return entry

    def _find_component_digest(self, components: Sequence[Mapping[str, Any]], logical_id: str) -> str:
        for item in components:
            if item.get("logical_id") == logical_id:
                return str(item.get("sha256_hex"))
        raise err("E_COMPONENT_MISSING", f"bundle component '{logical_id}' missing from index")
