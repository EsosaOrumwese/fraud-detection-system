"""Segment 6B S4 truth + bank-view labelling runner."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import polars as pl
import yaml

from engine.layers.l3.seg_6B.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l3.seg_6B.shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path, repository_root
from engine.layers.l3.shared.deterministic import stable_int_hash, stable_uniform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LabelInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class LabelOutputs:
    flow_truth_paths: dict[str, Path]
    flow_bank_paths: dict[str, Path]
    event_label_paths: dict[str, Path]
    case_timeline_paths: dict[str, Path]


class LabelRunner:
    """Assign truth and bank-view labels for 6B."""

    _SCENARIO_PATTERN = re.compile(r"scenario_id=([^/\\\\]+)")

    def run(self, inputs: LabelInputs) -> LabelOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        repo_root = repository_root()
        receipt, sealed_df = load_control_plane(
            data_root=inputs.data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        inventory = SealedInventory(
            dataframe=sealed_df,
            base_path=inputs.data_root,
            repo_root=repo_root,
            template_args={
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
                "seed": str(inputs.seed),
            },
        )
        self._assert_upstream_pass(receipt.payload)

        truth_policy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("truth_labelling_policy_6B", dictionary, sealed_df)
            )[0]
        )
        bank_policy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("bank_view_policy_6B", dictionary, sealed_df)
            )[0]
        )
        detection_rate = self._detection_rate(bank_policy)

        flow_manifest_key = self._manifest_key_for("s3_flow_anchor_with_fraud_6B", dictionary, sealed_df)
        event_manifest_key = self._manifest_key_for("s3_event_stream_with_fraud_6B", dictionary, sealed_df)
        flow_paths = inventory.resolve_files(manifest_key=flow_manifest_key)
        event_paths = inventory.resolve_files(manifest_key=event_manifest_key)
        scenarios = self._group_by_scenario(flow_paths)

        flow_truth_paths: dict[str, Path] = {}
        flow_bank_paths: dict[str, Path] = {}
        event_label_paths: dict[str, Path] = {}
        case_paths: dict[str, Path] = {}

        for scenario_id, paths in scenarios.items():
            flows_df = pl.scan_parquet([path.as_posix() for path in paths]).collect()
            events_df = self._load_events_for_scenario(event_paths, scenario_id)

            flow_truth_rows = []
            flow_bank_rows = []
            case_rows = []
            truth_map: dict[int, dict[str, object]] = {}
            for row in flows_df.to_dicts():
                flow_id = int(row.get("flow_id"))
                is_fraud = bool(row.get("fraud_flag"))
                bank_hit = is_fraud and stable_uniform(flow_id, "bank_view") < detection_rate
                truth_row = {
                    "flow_id": flow_id,
                    "is_fraud_truth": is_fraud,
                    "fraud_label": row.get("campaign_id") if is_fraud else None,
                    "seed": inputs.seed,
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": inputs.parameter_hash,
                    "scenario_id": scenario_id,
                }
                bank_row = {
                    "flow_id": flow_id,
                    "is_fraud_bank_view": bank_hit,
                    "bank_label": row.get("campaign_id") if bank_hit else None,
                    "seed": inputs.seed,
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": inputs.parameter_hash,
                    "scenario_id": scenario_id,
                }
                flow_truth_rows.append(truth_row)
                flow_bank_rows.append(bank_row)
                truth_map[flow_id] = {
                    "is_fraud_truth": is_fraud,
                    "is_fraud_bank_view": bank_hit,
                }
                if bank_hit:
                    case_id = stable_int_hash(flow_id, "case")
                    case_rows.append(
                        {
                            "case_id": case_id,
                            "case_event_seq": 1,
                            "flow_id": flow_id,
                            "case_event_type": "CASE_OPEN",
                            "ts_utc": row.get("ts_utc"),
                            "seed": inputs.seed,
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "scenario_id": scenario_id,
                        }
                    )

            event_rows = []
            for row in events_df.to_dicts():
                flow_id = int(row.get("flow_id"))
                labels = truth_map.get(flow_id, {})
                event_rows.append(
                    {
                        "flow_id": flow_id,
                        "event_seq": row.get("event_seq"),
                        "is_fraud_truth": labels.get("is_fraud_truth", False),
                        "is_fraud_bank_view": labels.get("is_fraud_bank_view", False),
                        "seed": inputs.seed,
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                        "scenario_id": scenario_id,
                    }
                )

            flow_truth_df = pl.DataFrame(flow_truth_rows)
            flow_bank_df = pl.DataFrame(flow_bank_rows)
            event_label_df = pl.DataFrame(event_rows)
            case_df = pl.DataFrame(case_rows)

            flow_truth_paths[scenario_id] = self._write_dataset(
                flow_truth_df,
                inputs,
                dictionary,
                "s4_flow_truth_labels_6B",
                scenario_id=scenario_id,
            )
            flow_bank_paths[scenario_id] = self._write_dataset(
                flow_bank_df,
                inputs,
                dictionary,
                "s4_flow_bank_view_6B",
                scenario_id=scenario_id,
            )
            event_label_paths[scenario_id] = self._write_dataset(
                event_label_df,
                inputs,
                dictionary,
                "s4_event_labels_6B",
                scenario_id=scenario_id,
            )
            case_paths[scenario_id] = self._write_dataset(
                case_df,
                inputs,
                dictionary,
                "s4_case_timeline_6B",
                scenario_id=scenario_id,
            )

        return LabelOutputs(
            flow_truth_paths=flow_truth_paths,
            flow_bank_paths=flow_bank_paths,
            event_label_paths=event_label_paths,
            case_timeline_paths=case_paths,
        )

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6B missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6B.S4 upstream segment {segment} not PASS")

    @staticmethod
    def _load_yaml(path: Path) -> Mapping[str, object]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"expected mapping in {path}")
        return payload

    @staticmethod
    def _detection_rate(policy: Mapping[str, object]) -> float:
        for key in ("detection_rate", "fraud_detection_rate", "default_detection_rate"):
            if key in policy:
                try:
                    value = float(policy.get(key))
                    return max(0.0, min(1.0, value))
                except (TypeError, ValueError):
                    continue
        return 0.8

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

    def _group_by_scenario(self, paths: Sequence[Path]) -> dict[str, list[Path]]:
        scenarios: dict[str, list[Path]] = {}
        for path in paths:
            match = self._SCENARIO_PATTERN.search(path.as_posix())
            scenario_id = match.group(1) if match else "baseline"
            scenarios.setdefault(scenario_id, []).append(path)
        return scenarios

    def _load_events_for_scenario(self, paths: Sequence[Path], scenario_id: str) -> pl.DataFrame:
        filtered = [path for path in paths if f"scenario_id={scenario_id}" in path.as_posix()]
        if not filtered:
            return pl.DataFrame([])
        return pl.scan_parquet([path.as_posix() for path in filtered]).collect()

    @staticmethod
    def _write_dataset(
        df: pl.DataFrame,
        inputs: LabelInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        dataset_id: str,
        *,
        scenario_id: str,
    ) -> Path:
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
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)
        return path


__all__ = ["LabelInputs", "LabelOutputs", "LabelRunner"]
