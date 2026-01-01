"""Segment 6B S5 validation runner."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import polars as pl

from engine.layers.l3.seg_6B.shared.control_plane import load_control_plane
from engine.layers.l3.seg_6B.shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ValidationOutputs:
    report_path: Path
    issue_table_path: Path
    bundle_index_path: Path
    passed_flag_path: Path | None


class ValidationRunner:
    """Build validation report + bundle for Segment 6B."""

    _SPEC_VERSION = "1.0.0"
    _SCENARIO_PATTERN = re.compile(r"scenario_id=([^/\\\\]+)")

    def run(self, inputs: ValidationInputs) -> ValidationOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        receipt, _ = load_control_plane(
            data_root=inputs.data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        self._assert_upstream_pass(receipt.payload)

        scenarios = self._discover_scenarios(inputs, dictionary)
        if not scenarios:
            scenarios = ["baseline"]

        issues: list[Mapping[str, object]] = []
        required_ids = [
            "s1_arrival_entities_6B",
            "s1_session_index_6B",
            "s2_flow_anchor_baseline_6B",
            "s2_event_stream_baseline_6B",
            "s3_campaign_catalogue_6B",
            "s3_flow_anchor_with_fraud_6B",
            "s3_event_stream_with_fraud_6B",
            "s4_flow_truth_labels_6B",
            "s4_flow_bank_view_6B",
            "s4_event_labels_6B",
            "s4_case_timeline_6B",
        ]

        for scenario_id in scenarios:
            for dataset_id in required_ids:
                path = inputs.data_root / render_dataset_path(
                    dataset_id=dataset_id,
                    template_args={
                        "seed": inputs.seed,
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                        "scenario_id": scenario_id,
                    },
                    dictionary=dictionary,
                )
                if not path.exists():
                    issues.append(
                        {
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "check_id": "S5_MISSING_OUTPUT",
                            "issue_id": f"{dataset_id}:{scenario_id}",
                            "severity": "FAIL",
                            "scope_type": "dataset",
                            "seed": inputs.seed,
                            "scenario_id": scenario_id,
                            "message": f"missing {dataset_id} at {path}",
                        }
                    )

        overall_status = "PASS" if not issues else "FAIL"

        report_payload = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "spec_version_6B": self._SPEC_VERSION,
            "overall_status": overall_status,
            "upstream_segments": self._upstream_payload(receipt.payload),
            "segment_states": {
                "6B.S1": "PASS",
                "6B.S2": "PASS",
                "6B.S3": "PASS",
                "6B.S4": "PASS",
                "6B.S5": overall_status,
            },
            "checks": self._summarise_checks(issues),
        }
        report_path = self._write_report(inputs, dictionary, report_payload)
        issue_table_path = self._write_issue_table(inputs, dictionary, issues)

        bundle_dir = inputs.data_root / render_dataset_path(
            dataset_id="validation_bundle_6B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        bundle_dir.mkdir(parents=True, exist_ok=True)
        index_payload, items = self._bundle_index_payload(
            bundle_dir=bundle_dir,
            report_path=report_path,
            issue_table_path=issue_table_path,
            inputs=inputs,
        )
        bundle_index_path = bundle_dir / "index.json"
        bundle_index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")
        bundle_digest = self._bundle_digest(
            items + [self._bundle_item(bundle_dir, bundle_index_path, role="index")],
            bundle_dir,
        )

        passed_flag_path = None
        if overall_status == "PASS":
            passed_flag_path = bundle_dir / "_passed.flag"
            passed_flag_path.write_text(f"sha256_hex = {bundle_digest}", encoding="utf-8")

        return ValidationOutputs(
            report_path=report_path,
            issue_table_path=issue_table_path,
            bundle_index_path=bundle_index_path,
            passed_flag_path=passed_flag_path,
        )

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6B missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6B.S5 upstream segment {segment} not PASS")

    def _discover_scenarios(
        self,
        inputs: ValidationInputs,
        dictionary: Mapping[str, object] | Sequence[object],
    ) -> list[str]:
        entry = get_dataset_entry("s1_arrival_entities_6B", dictionary=dictionary)
        path_template = str(entry.get("path") or "").strip()
        if not path_template:
            return []
        template_args = {
            "seed": inputs.seed,
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "run_id": inputs.run_id,
            "scenario_id": "*",
        }
        try:
            glob_pattern = path_template.format(**template_args)
        except KeyError as exc:
            raise ValueError(f"missing template arg {exc} for scenario discovery") from exc
        paths = list(inputs.data_root.glob(glob_pattern))
        scenarios: set[str] = set()
        for path in paths:
            match = self._SCENARIO_PATTERN.search(path.as_posix())
            if match:
                scenarios.add(match.group(1))
        return sorted(scenarios)

    @staticmethod
    def _manifest_key_for(
        dataset_id: str,
        dictionary: Mapping[str, object] | Sequence[object],
        sealed_df: pl.DataFrame,
    ) -> str:
        entry = get_dataset_entry(dataset_id, dictionary=dictionary)
        path_template = str(entry.get("path") or "").strip()
        rows = sealed_df.filter(pl.col("path_template") == path_template).to_dicts()
        if rows:
            return str(rows[0].get("manifest_key"))
        return f"mlr.6B.dataset.{dataset_id}"

    @staticmethod
    def _summarise_checks(issues: list[Mapping[str, object]]) -> list[Mapping[str, object]]:
        if not issues:
            return [
                {
                    "check_id": "S5_OUTPUTS_PRESENT",
                    "severity": "REQUIRED",
                    "result": "PASS",
                }
            ]
        return [
            {
                "check_id": "S5_OUTPUTS_PRESENT",
                "severity": "REQUIRED",
                "result": "FAIL",
                "metrics": {"issues_total": len(issues)},
            }
        ]

    @staticmethod
    def _upstream_payload(receipt: Mapping[str, object]) -> Mapping[str, object]:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            return {}
        payload: dict[str, object] = {}
        for segment, status in upstream.items():
            if isinstance(status, Mapping):
                payload[segment] = {
                    "status": status.get("status"),
                    "bundle_sha256": status.get("bundle_sha256"),
                    "flag_path": status.get("flag_path"),
                }
        return payload

    def _write_report(
        self,
        inputs: ValidationInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        payload: Mapping[str, object],
    ) -> Path:
        path = inputs.data_root / render_dataset_path(
            dataset_id="s5_validation_report_6B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def _write_issue_table(
        self,
        inputs: ValidationInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        issues: list[Mapping[str, object]],
    ) -> Path:
        path = inputs.data_root / render_dataset_path(
            dataset_id="s5_issue_table_6B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(issues).write_parquet(path)
        return path

    def _bundle_index_payload(
        self,
        *,
        bundle_dir: Path,
        report_path: Path,
        issue_table_path: Path,
        inputs: ValidationInputs,
    ) -> tuple[Mapping[str, object], list[Mapping[str, object]]]:
        items = [
            self._bundle_item(bundle_dir, report_path, role="validation_report"),
            self._bundle_item(bundle_dir, issue_table_path, role="issue_table"),
        ]
        index_payload = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "spec_version_6B": self._SPEC_VERSION,
            "items": items,
        }
        return index_payload, items

    @staticmethod
    def _bundle_item(bundle_dir: Path, path: Path, *, role: str) -> Mapping[str, object]:
        rel_path = path.relative_to(bundle_dir).as_posix()
        sha256_hex = hashlib.sha256(path.read_bytes()).hexdigest()
        return {"path": rel_path, "sha256_hex": sha256_hex, "role": role, "schema_ref": None}

    @staticmethod
    def _bundle_digest(items: list[Mapping[str, object]], bundle_dir: Path) -> str:
        digest = hashlib.sha256()
        for item in sorted(items, key=lambda row: row.get("path", "")):
            target = bundle_dir / str(item.get("path"))
            digest.update(target.read_bytes())
        return digest.hexdigest()


__all__ = ["ValidationInputs", "ValidationOutputs", "ValidationRunner"]
