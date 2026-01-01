"""Segment 6B S3 fraud overlay runner."""

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
from engine.layers.l3.shared.deterministic import stable_uniform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FraudInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class FraudOutputs:
    campaign_paths: dict[str, Path]
    flow_paths: dict[str, Path]
    event_paths: dict[str, Path]


class FraudRunner:
    """Overlay fraud campaigns on baseline flows."""

    _SCENARIO_PATTERN = re.compile(r"scenario_id=([^/\\\\]+)")

    def run(self, inputs: FraudInputs) -> FraudOutputs:
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

        fraud_policy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("fraud_overlay_policy_6B", dictionary, sealed_df)
            )[0]
        )
        campaign_config = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("fraud_campaign_catalogue_config_6B", dictionary, sealed_df)
            )[0]
        )
        fraud_rate = self._fraud_rate(fraud_policy)
        campaign_id, campaign_label = self._campaign_defaults(campaign_config)

        flow_manifest_key = self._manifest_key_for("s2_flow_anchor_baseline_6B", dictionary, sealed_df)
        event_manifest_key = self._manifest_key_for("s2_event_stream_baseline_6B", dictionary, sealed_df)
        flow_paths = inventory.resolve_files(manifest_key=flow_manifest_key)
        event_paths = inventory.resolve_files(manifest_key=event_manifest_key)
        scenarios = self._group_by_scenario(flow_paths)

        campaign_paths: dict[str, Path] = {}
        out_flow_paths: dict[str, Path] = {}
        out_event_paths: dict[str, Path] = {}

        for scenario_id, paths in scenarios.items():
            flows_df = pl.scan_parquet([path.as_posix() for path in paths]).collect()
            events_df = self._load_events_for_scenario(event_paths, scenario_id)

            flow_rows = []
            fraud_flow_ids: set[int] = set()
            for row in flows_df.to_dicts():
                flow_id = int(row.get("flow_id"))
                is_fraud = stable_uniform(flow_id, scenario_id, "fraud") < fraud_rate
                if is_fraud:
                    fraud_flow_ids.add(flow_id)
                enriched = dict(row)
                enriched.update(
                    {
                        "fraud_flag": bool(is_fraud),
                        "campaign_id": campaign_id if is_fraud else None,
                    }
                )
                flow_rows.append(enriched)

            event_rows = []
            for row in events_df.to_dicts():
                flow_id = int(row.get("flow_id"))
                is_fraud = flow_id in fraud_flow_ids
                enriched = dict(row)
                enriched.update(
                    {
                        "fraud_flag": bool(is_fraud),
                        "campaign_id": campaign_id if is_fraud else None,
                    }
                )
                event_rows.append(enriched)

            flow_out = pl.DataFrame(flow_rows)
            event_out = pl.DataFrame(event_rows)
            flow_path = self._write_dataset(
                flow_out,
                inputs,
                dictionary,
                "s3_flow_anchor_with_fraud_6B",
                scenario_id=scenario_id,
            )
            event_path = self._write_dataset(
                event_out,
                inputs,
                dictionary,
                "s3_event_stream_with_fraud_6B",
                scenario_id=scenario_id,
            )
            campaign_df = pl.DataFrame(
                [
                    {
                        "campaign_id": campaign_id,
                        "campaign_label": campaign_label,
                        "fraud_rate": fraud_rate,
                        "scenario_id": scenario_id,
                        "seed": inputs.seed,
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                    }
                ]
            )
            campaign_path = self._write_dataset(
                campaign_df,
                inputs,
                dictionary,
                "s3_campaign_catalogue_6B",
                scenario_id=scenario_id,
                single_file=True,
            )

            campaign_paths[scenario_id] = campaign_path
            out_flow_paths[scenario_id] = flow_path
            out_event_paths[scenario_id] = event_path

        return FraudOutputs(
            campaign_paths=campaign_paths,
            flow_paths=out_flow_paths,
            event_paths=out_event_paths,
        )

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6B missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6B.S3 upstream segment {segment} not PASS")

    @staticmethod
    def _load_yaml(path: Path) -> Mapping[str, object]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"expected mapping in {path}")
        return payload

    @staticmethod
    def _fraud_rate(policy: Mapping[str, object]) -> float:
        for key in ("fraud_rate", "fraud_share", "default_fraud_rate"):
            if key in policy:
                try:
                    value = float(policy.get(key))
                    return max(0.0, min(1.0, value))
                except (TypeError, ValueError):
                    continue
        return 0.01

    @staticmethod
    def _campaign_defaults(config: Mapping[str, object]) -> tuple[str, str]:
        campaigns = config.get("campaigns") or []
        if campaigns and isinstance(campaigns, list):
            first = campaigns[0]
            if isinstance(first, Mapping):
                return str(first.get("campaign_id", "CAMP_DEFAULT")), str(
                    first.get("label", "Default campaign")
                )
        return "CAMP_DEFAULT", "Default campaign"

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
        inputs: FraudInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        dataset_id: str,
        *,
        scenario_id: str,
        single_file: bool = False,
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
        if single_file:
            df.write_parquet(path)
            return path
        df.write_parquet(path)
        return path


__all__ = ["FraudInputs", "FraudOutputs", "FraudRunner"]
