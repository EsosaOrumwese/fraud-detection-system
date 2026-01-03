"""Segment 6B S2 baseline flow/event generator."""

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
class BaselineInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class BaselineOutputs:
    flow_paths: dict[str, Path]
    event_paths: dict[str, Path]


class BaselineRunner:
    """Generate baseline flows and events from S1 attachments."""

    _SCENARIO_PATTERN = re.compile(r"scenario_id=([^/\\\\]+)")

    def run(self, inputs: BaselineInputs) -> BaselineOutputs:
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

        amount_policy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("amount_model_6B", dictionary, sealed_df)
            )[0]
        )
        amount_min, amount_max = self._amount_bounds(amount_policy)

        arrival_manifest_key = self._manifest_key_for("s1_arrival_entities_6B", dictionary, sealed_df)
        arrival_paths = inventory.resolve_files(manifest_key=arrival_manifest_key)
        scenarios = self._group_by_scenario(arrival_paths)
        flow_paths: dict[str, Path] = {}
        event_paths: dict[str, Path] = {}

        for scenario_id, paths in scenarios.items():
            part_index = 0
            first_flow_path: Path | None = None
            first_event_path: Path | None = None
            for path in sorted(paths):
                arrivals_df = pl.read_parquet(path)
                if arrivals_df.is_empty():
                    continue
                flow_rows = []
                event_rows = []
                for row in arrivals_df.iter_rows(named=True):
                    merchant_id = row.get("merchant_id")
                    arrival_seq = row.get("arrival_seq", row.get("arrival_id", 0))
                    flow_id = stable_int_hash(
                        inputs.manifest_fingerprint,
                        inputs.parameter_hash,
                        scenario_id,
                        merchant_id,
                        arrival_seq,
                        "flow",
                    )
                    u = stable_uniform(flow_id, "amount")
                    amount = round(amount_min + u * (amount_max - amount_min), 2)
                    flow_rows.append(
                        {
                            "flow_id": flow_id,
                            "arrival_seq": arrival_seq,
                            "merchant_id": merchant_id,
                            "party_id": row.get("party_id"),
                            "account_id": row.get("account_id"),
                            "instrument_id": row.get("instrument_id"),
                            "device_id": row.get("device_id"),
                            "ip_id": row.get("ip_id"),
                            "ts_utc": row.get("ts_utc"),
                            "amount": amount,
                            "seed": inputs.seed,
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "scenario_id": scenario_id,
                        }
                    )
                    event_rows.append(
                        {
                            "flow_id": flow_id,
                            "event_seq": 1,
                            "event_type": "AUTH",
                            "ts_utc": row.get("ts_utc"),
                            "amount": amount,
                            "seed": inputs.seed,
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "scenario_id": scenario_id,
                        }
                    )

                if flow_rows:
                    flow_path = self._resolve_output_path(
                        inputs,
                        dictionary,
                        "s2_flow_anchor_baseline_6B",
                        scenario_id=scenario_id,
                        part_index=part_index,
                    )
                    pl.DataFrame(flow_rows).write_parquet(flow_path)
                    if first_flow_path is None:
                        first_flow_path = flow_path
                if event_rows:
                    event_path = self._resolve_output_path(
                        inputs,
                        dictionary,
                        "s2_event_stream_baseline_6B",
                        scenario_id=scenario_id,
                        part_index=part_index,
                    )
                    pl.DataFrame(event_rows).write_parquet(event_path)
                    if first_event_path is None:
                        first_event_path = event_path
                if flow_rows or event_rows:
                    part_index += 1

            if first_flow_path is not None:
                flow_paths[scenario_id] = first_flow_path
            if first_event_path is not None:
                event_paths[scenario_id] = first_event_path

        return BaselineOutputs(flow_paths=flow_paths, event_paths=event_paths)

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6B missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6B.S2 upstream segment {segment} not PASS")

    @staticmethod
    def _load_yaml(path: Path) -> Mapping[str, object]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"expected mapping in {path}")
        return payload

    @staticmethod
    def _amount_bounds(policy: Mapping[str, object]) -> tuple[float, float]:
        bounds = policy.get("bounds") or {}
        min_value = float(bounds.get("min", policy.get("amount_min", 1.0)))
        max_value = float(bounds.get("max", policy.get("amount_max", max(min_value, 100.0))))
        if max_value <= min_value:
            max_value = min_value + 1.0
        return min_value, max_value

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
        inputs: BaselineInputs,
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


__all__ = ["BaselineInputs", "BaselineOutputs", "BaselineRunner"]
