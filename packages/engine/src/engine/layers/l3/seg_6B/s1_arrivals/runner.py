"""Segment 6B S1 arrival-to-entity attachment runner."""

from __future__ import annotations

import logging
import time
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import polars as pl

from engine.layers.l3.seg_6B.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l3.seg_6B.shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path, repository_root
from engine.layers.l3.shared.deterministic import stable_int_hash, stable_uniform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArrivalInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ArrivalOutputs:
    arrival_entities_paths: dict[str, Path]
    session_index_paths: dict[str, Path]


class ArrivalRunner:
    """Attach entities and sessions to 5B arrivals."""

    _SCENARIO_PATTERN = re.compile(r"scenario_id=([^/\\\\]+)")

    def run(self, inputs: ArrivalInputs) -> ArrivalOutputs:
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

        arrival_manifest_key = self._manifest_key_for("arrival_events_5B", dictionary, sealed_df)
        arrival_paths = inventory.resolve_files(manifest_key=arrival_manifest_key)
        scenarios = self._group_by_scenario(arrival_paths)
        if not scenarios:
            logger.warning("6B.S1 no arrival events found for manifest=%s", inputs.manifest_fingerprint)
            return ArrivalOutputs(arrival_entities_paths={}, session_index_paths={})

        party_df = self._load_dataset(inputs, dictionary, "s1_party_base_6A")
        account_df = self._load_dataset(inputs, dictionary, "s2_account_base_6A")
        instrument_df = self._load_dataset(inputs, dictionary, "s3_instrument_base_6A")
        device_df = self._load_dataset(inputs, dictionary, "s4_device_base_6A")
        ip_df = self._load_dataset(inputs, dictionary, "s4_ip_base_6A")
        device_links = self._load_dataset(inputs, dictionary, "s4_device_links_6A")
        ip_links = self._load_dataset(inputs, dictionary, "s4_ip_links_6A")

        party_ids = [int(row["party_id"]) for row in party_df.select("party_id").to_dicts()]
        account_map = self._group_ids(account_df, "owner_party_id", "account_id")
        instrument_map = self._group_ids(instrument_df, "account_id", "instrument_id")
        device_map = self._group_ids(device_links.drop_nulls(["party_id"]), "party_id", "device_id")
        ip_map = self._group_ids(ip_links.drop_nulls(["device_id"]), "device_id", "ip_id")
        device_ids = [int(row["device_id"]) for row in device_df.select("device_id").to_dicts()]
        ip_ids = [int(row["ip_id"]) for row in ip_df.select("ip_id").to_dicts()]

        arrival_entities_paths: dict[str, Path] = {}
        session_index_paths: dict[str, Path] = {}

        for scenario_id, paths in scenarios.items():
            logger.info("6B.S1 scenario=%s shards=%d", scenario_id, len(paths))
            part_index = 0
            part_paths: list[Path] = []
            log_every = 10
            log_interval_s = 120.0
            last_log = time.monotonic()
            for shard_idx, path in enumerate(sorted(paths), start=1):
                now = time.monotonic()
                if shard_idx == 1 or shard_idx % log_every == 0 or now - last_log >= log_interval_s:
                    logger.info("6B.S1 scenario=%s shard %d/%d", scenario_id, shard_idx, len(paths))
                    last_log = now
                arrivals_df = pl.read_parquet(path)
                if arrivals_df.is_empty():
                    continue
                attached_rows = []
                for row in arrivals_df.iter_rows(named=True):
                    merchant_id = row.get("merchant_id")
                    arrival_seq = row.get("arrival_seq", row.get("arrival_id", 0))
                    party_id = self._pick_id(
                        party_ids,
                        inputs,
                        scenario_id,
                        merchant_id,
                        arrival_seq,
                        label="party_id",
                    )
                    account_id = self._pick_linked_id(
                        account_map.get(party_id, []),
                        inputs,
                        scenario_id,
                        party_id,
                        arrival_seq,
                        label="account_id",
                    )
                    instrument_id = self._pick_linked_id(
                        instrument_map.get(account_id, []),
                        inputs,
                        scenario_id,
                        account_id,
                        arrival_seq,
                        label="instrument_id",
                    )
                    device_id = self._pick_linked_id(
                        device_map.get(party_id, []),
                        inputs,
                        scenario_id,
                        party_id,
                        arrival_seq,
                        label="device_id",
                        fallback=device_ids,
                    )
                    ip_id = self._pick_linked_id(
                        ip_map.get(device_id, []),
                        inputs,
                        scenario_id,
                        device_id,
                        arrival_seq,
                        label="ip_id",
                        fallback=ip_ids,
                    )
                    session_id = stable_int_hash(
                        inputs.manifest_fingerprint,
                        inputs.parameter_hash,
                        scenario_id,
                        party_id,
                        device_id,
                        merchant_id,
                        int(arrival_seq) // 10,
                    )

                    enriched = dict(row)
                    enriched.update(
                        {
                            "party_id": party_id,
                            "account_id": account_id,
                            "instrument_id": instrument_id,
                            "device_id": device_id,
                            "ip_id": ip_id,
                            "session_id": session_id,
                            "parameter_hash": inputs.parameter_hash,
                        }
                    )
                    attached_rows.append(enriched)

                if not attached_rows:
                    continue
                part_path = self._resolve_output_path(
                    inputs,
                    dictionary,
                    "s1_arrival_entities_6B",
                    scenario_id=scenario_id,
                    part_index=part_index,
                )
                pl.DataFrame(attached_rows).write_parquet(part_path)
                part_paths.append(part_path)
                part_index += 1

            if not part_paths:
                logger.warning("6B.S1 no arrival rows for scenario=%s", scenario_id)
                continue

            arrival_entities_paths[scenario_id] = part_paths[0]
            session_index_path = self._write_session_index(
                part_paths,
                inputs,
                dictionary,
                scenario_id=scenario_id,
            )
            session_index_paths[scenario_id] = session_index_path

        return ArrivalOutputs(
            arrival_entities_paths=arrival_entities_paths,
            session_index_paths=session_index_paths,
        )

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6B missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6B.S1 upstream segment {segment} not PASS")

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
    def _group_ids(df: pl.DataFrame, key_col: str, id_col: str) -> dict[int, list[int]]:
        groups: dict[int, list[int]] = {}
        for row in df.select([key_col, id_col]).to_dicts():
            key = row.get(key_col)
            value = row.get(id_col)
            if key is None or value is None:
                continue
            groups.setdefault(int(key), []).append(int(value))
        return groups

    @staticmethod
    def _pick_id(
        ids: list[int],
        inputs: ArrivalInputs,
        scenario_id: str,
        merchant_id: object,
        arrival_seq: object,
        *,
        label: str,
    ) -> int:
        if not ids:
            return -1
        u = stable_uniform(
            inputs.manifest_fingerprint,
            inputs.parameter_hash,
            scenario_id,
            merchant_id,
            arrival_seq,
            label,
        )
        index = min(int(u * len(ids)), len(ids) - 1)
        return ids[index]

    @staticmethod
    def _pick_linked_id(
        ids: list[int],
        inputs: ArrivalInputs,
        scenario_id: str,
        anchor_id: object,
        arrival_seq: object,
        *,
        label: str,
        fallback: list[int] | None = None,
    ) -> int:
        if not ids and fallback:
            ids = fallback
        if not ids:
            return -1
        u = stable_uniform(
            inputs.manifest_fingerprint,
            inputs.parameter_hash,
            scenario_id,
            anchor_id,
            arrival_seq,
            label,
        )
        index = min(int(u * len(ids)), len(ids) - 1)
        return ids[index]

    @staticmethod
    def _build_session_index(arrival_entities: pl.DataFrame) -> pl.DataFrame:
        if arrival_entities.is_empty():
            return pl.DataFrame([])
        cols = [
            col
            for col in [
                "seed",
                "manifest_fingerprint",
                "scenario_id",
                "session_id",
                "party_id",
                "device_id",
                "account_id",
                "instrument_id",
                "merchant_id",
            ]
            if col in arrival_entities.columns
        ]
        grouped = arrival_entities.group_by(["session_id"]).agg(
            pl.count().alias("arrival_count"),
            pl.col("ts_utc").min().alias("session_start_utc"),
            pl.col("ts_utc").max().alias("session_end_utc"),
        )
        firsts = arrival_entities.select(cols).group_by("session_id").first()
        return grouped.join(firsts, on="session_id", how="left")

    @staticmethod
    def _resolve_output_path(
        inputs: ArrivalInputs,
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

    @staticmethod
    def _write_session_index(
        part_paths: Sequence[Path],
        inputs: ArrivalInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        *,
        scenario_id: str,
    ) -> Path:
        scan = pl.scan_parquet([path.as_posix() for path in part_paths])
        schema_cols = scan.collect_schema().names()
        cols = [
            col
            for col in [
                "seed",
                "manifest_fingerprint",
                "scenario_id",
                "session_id",
                "party_id",
                "device_id",
                "account_id",
                "instrument_id",
                "merchant_id",
            ]
            if col in schema_cols
        ]
        grouped = scan.group_by("session_id").agg(
            pl.count().alias("arrival_count"),
            pl.col("ts_utc").min().alias("session_start_utc"),
            pl.col("ts_utc").max().alias("session_end_utc"),
        )
        firsts = scan.select(cols).group_by("session_id").first()
        session_index = grouped.join(firsts, on="session_id", how="left")
        path = ArrivalRunner._resolve_output_path(
            inputs,
            dictionary,
            "s1_session_index_6B",
            scenario_id=scenario_id,
            part_index=0,
        )
        session_index.sink_parquet(path)
        return path

    @staticmethod
    def _load_dataset(
        inputs: ArrivalInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        dataset_id: str,
    ) -> pl.DataFrame:
        path = inputs.data_root / render_dataset_path(
            dataset_id=dataset_id,
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        return pl.read_parquet(path)


__all__ = ["ArrivalInputs", "ArrivalOutputs", "ArrivalRunner"]
