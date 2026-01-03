"""Segment 6B S4 truth + bank-view labelling runner."""

from __future__ import annotations

import logging
import time
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
        event_scenarios = self._group_by_scenario(event_paths)

        flow_truth_paths: dict[str, Path] = {}
        flow_bank_paths: dict[str, Path] = {}
        event_label_paths: dict[str, Path] = {}
        case_paths: dict[str, Path] = {}

        for scenario_id, paths in scenarios.items():
            logger.info(
                "6B.S4 scenario=%s flow_shards=%d event_shards=%d",
                scenario_id,
                len(paths),
                len(event_scenarios.get(scenario_id, [])),
            )
            flow_part_index = 0
            first_truth_path: Path | None = None
            first_bank_path: Path | None = None
            first_event_path: Path | None = None
            first_case_path: Path | None = None

            log_every = 10
            log_interval_s = 120.0
            last_log = time.monotonic()
            for shard_idx, path in enumerate(sorted(paths), start=1):
                now = time.monotonic()
                if shard_idx == 1 or shard_idx % log_every == 0 or now - last_log >= log_interval_s:
                    logger.info("6B.S4 scenario=%s flow_shard %d/%d", scenario_id, shard_idx, len(paths))
                    last_log = now
                flows_df = pl.read_parquet(path)
                if flows_df.is_empty():
                    continue
                flow_truth_rows = []
                flow_bank_rows = []
                case_rows = []
                for row in flows_df.iter_rows(named=True):
                    flow_id = int(row.get("flow_id"))
                    is_fraud = bool(row.get("fraud_flag"))
                    bank_hit = is_fraud and stable_uniform(flow_id, "bank_view") < detection_rate
                    flow_truth_rows.append(
                        {
                            "flow_id": flow_id,
                            "is_fraud_truth": is_fraud,
                            "fraud_label": row.get("campaign_id") if is_fraud else None,
                            "seed": inputs.seed,
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "scenario_id": scenario_id,
                        }
                    )
                    flow_bank_rows.append(
                        {
                            "flow_id": flow_id,
                            "is_fraud_bank_view": bank_hit,
                            "bank_label": row.get("campaign_id") if bank_hit else None,
                            "seed": inputs.seed,
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "scenario_id": scenario_id,
                        }
                    )
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

                if flow_truth_rows:
                    flow_truth_path = self._resolve_output_path(
                        inputs,
                        dictionary,
                        "s4_flow_truth_labels_6B",
                        scenario_id=scenario_id,
                        part_index=flow_part_index,
                    )
                    pl.DataFrame(flow_truth_rows).write_parquet(flow_truth_path)
                    if first_truth_path is None:
                        first_truth_path = flow_truth_path
                if flow_bank_rows:
                    flow_bank_path = self._resolve_output_path(
                        inputs,
                        dictionary,
                        "s4_flow_bank_view_6B",
                        scenario_id=scenario_id,
                        part_index=flow_part_index,
                    )
                    pl.DataFrame(flow_bank_rows).write_parquet(flow_bank_path)
                    if first_bank_path is None:
                        first_bank_path = flow_bank_path
                if case_rows:
                    case_path = self._resolve_output_path(
                        inputs,
                        dictionary,
                        "s4_case_timeline_6B",
                        scenario_id=scenario_id,
                        part_index=flow_part_index,
                    )
                    pl.DataFrame(case_rows).write_parquet(case_path)
                    if first_case_path is None:
                        first_case_path = case_path

                if flow_truth_rows or flow_bank_rows or case_rows:
                    flow_part_index += 1

            event_part_index = 0
            event_paths_for_scenario = sorted(event_scenarios.get(scenario_id, []))
            last_event_log = time.monotonic()
            for shard_idx, path in enumerate(event_paths_for_scenario, start=1):
                now = time.monotonic()
                if shard_idx == 1 or shard_idx % log_every == 0 or now - last_event_log >= log_interval_s:
                    logger.info(
                        "6B.S4 scenario=%s event_shard %d/%d",
                        scenario_id,
                        shard_idx,
                        len(event_paths_for_scenario),
                    )
                    last_event_log = now
                events_df = pl.read_parquet(path)
                if events_df.is_empty():
                    continue
                event_rows = []
                for row in events_df.iter_rows(named=True):
                    flow_id = int(row.get("flow_id"))
                    is_fraud = bool(row.get("fraud_flag", False))
                    bank_hit = is_fraud and stable_uniform(flow_id, "bank_view") < detection_rate
                    event_rows.append(
                        {
                            "flow_id": flow_id,
                            "event_seq": row.get("event_seq"),
                            "is_fraud_truth": is_fraud,
                            "is_fraud_bank_view": bank_hit,
                            "seed": inputs.seed,
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "scenario_id": scenario_id,
                        }
                    )

                if not event_rows:
                    continue
                event_path = self._resolve_output_path(
                    inputs,
                    dictionary,
                    "s4_event_labels_6B",
                    scenario_id=scenario_id,
                    part_index=event_part_index,
                )
                pl.DataFrame(event_rows).write_parquet(event_path)
                if first_event_path is None:
                    first_event_path = event_path
                event_part_index += 1

            if first_truth_path is not None:
                flow_truth_paths[scenario_id] = first_truth_path
            if first_bank_path is not None:
                flow_bank_paths[scenario_id] = first_bank_path
            if first_event_path is not None:
                event_label_paths[scenario_id] = first_event_path
            if first_case_path is not None:
                case_paths[scenario_id] = first_case_path

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

    @staticmethod
    def _resolve_output_path(
        inputs: LabelInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        dataset_id: str,
        *,
        scenario_id: str,
        part_index: int = 0,
    ) -> Path:
        raw_path = render_dataset_path(
            dataset_id=dataset_id,
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
                "scenario_id": scenario_id,
            },
            dictionary=dictionary,
        )
        template_path = Path(raw_path)
        filename = template_path.name
        if "*" in filename:
            filename = filename.replace("*", f"{part_index:05d}")
        resolved = inputs.data_root / template_path.parent / filename
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved


__all__ = ["LabelInputs", "LabelOutputs", "LabelRunner"]
