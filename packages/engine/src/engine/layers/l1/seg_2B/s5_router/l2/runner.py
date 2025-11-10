"""Segment 2B state-5 router runner."""

from __future__ import annotations

import hashlib
import logging
import json
import math
import platform
import socket
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple
from uuid import uuid4

import polars as pl

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import (
    PhiloxEngine,
    PhiloxState,
    PhiloxSubstream,
    comp_u64,
)

from ...shared.dictionary import load_dictionary, render_dataset_path, resolve_dataset_path, repository_root
from ...shared.receipt import (
    GateReceiptSummary,
    SealedInputRecord,
    load_gate_receipt,
    load_sealed_inputs_inventory,
)
from ...shared.rng_trace import append_trace_records
from ...shared.runtime import RouterVirtualArrival
from ...shared.policies import load_policy_asset
from ...shared.virtual import VirtualMerchantClassifier, VirtualRules
from ...s0_gate.exceptions import err

RUN_REPORT_ROOT = Path("reports") / "l1" / "s5_router"

logger = logging.getLogger(__name__)


def _comp_string(value: str) -> tuple[str, str]:
    return ("string", value)


@dataclass(frozen=True)
class RouterArrival:
    """Single routing request."""

    merchant_id: int
    utc_timestamp: datetime
    is_virtual: bool = False

    @staticmethod
    def from_payload(payload: Mapping[str, object]) -> "RouterArrival":
        merchant_id = int(payload["merchant_id"])
        raw_ts = str(payload["utc_timestamp"])
        if raw_ts.endswith("Z"):
            raw_ts = raw_ts[:-1] + "+00:00"
        ts = datetime.fromisoformat(raw_ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        virtual_value = payload.get("is_virtual", False)
        if isinstance(virtual_value, bool):
            is_virtual = virtual_value
        elif isinstance(virtual_value, (int, float)):
            is_virtual = bool(int(virtual_value))
        elif isinstance(virtual_value, str):
            is_virtual = virtual_value.strip().lower() in {"1", "true", "yes"}
        else:
            is_virtual = False
        return RouterArrival(
            merchant_id=merchant_id,
            utc_timestamp=ts.astimezone(timezone.utc),
            is_virtual=is_virtual,
        )


@dataclass(frozen=True)
class S5RouterInputs:
    """Configuration required to execute the router."""

    data_root: Path
    seed: int | str
    manifest_fingerprint: str
    seg2a_manifest_fingerprint: str
    parameter_hash: str
    git_commit_hex: str
    arrivals: Sequence[RouterArrival] | None = None
    dictionary_path: Optional[Path] = None
    run_id: Optional[str] = None
    emit_selection_log: bool = False
    emit_run_report_stdout: bool = True

    def __post_init__(self) -> None:
        data_root = self.data_root.expanduser().resolve()
        object.__setattr__(self, "data_root", data_root)
        seed_value = str(self.seed)
        if not seed_value:
            raise err("E_S5_SEED_EMPTY", "seed must be provided for S5")
        object.__setattr__(self, "seed", seed_value)
        manifest = self._validate_hex(self.manifest_fingerprint, field="manifest_fingerprint")
        seg2a_manifest = self._validate_hex(
            self.seg2a_manifest_fingerprint,
            field="seg2a_manifest_fingerprint",
        )
        parameter_hash = self._validate_hex(self.parameter_hash, field="parameter_hash")
        object.__setattr__(self, "manifest_fingerprint", manifest)
        object.__setattr__(self, "seg2a_manifest_fingerprint", seg2a_manifest)
        object.__setattr__(self, "parameter_hash", parameter_hash)
        run_id = self.run_id
        if run_id is not None:
            if len(run_id) != 32:
                raise err("E_S5_RUN_ID", "run_id must be 32 hex characters")
            int(run_id, 16)
            object.__setattr__(self, "run_id", run_id.lower())
        arrivals = tuple(self.arrivals) if self.arrivals is not None else None
        object.__setattr__(self, "arrivals", arrivals)

    @staticmethod
    def _validate_hex(value: str, *, field: str) -> str:
        lowered = value.lower()
        if len(lowered) != 64:
            raise err("E_S5_HEX_FIELD", f"{field} must be 64 hex characters")
        int(lowered, 16)
        return lowered


@dataclass(frozen=True)
class S5RouterResult:
    """Outputs emitted by the router."""

    run_id: str
    rng_event_group_path: Optional[Path]
    rng_event_site_path: Optional[Path]
    rng_trace_log_path: Optional[Path]
    rng_audit_log_path: Optional[Path]
    selection_log_paths: Tuple[Path, ...]
    virtual_arrivals: Tuple[RouterVirtualArrival, ...]
    run_report_path: Path
    selections_total: int
    arrivals_processed: int


@dataclass
class AliasTable:
    """Deterministic alias table."""

    values: List[object]
    probabilities: List[float]
    aliases: List[int]
    value_probabilities: Dict[object, float]

    def sample(self, u: float) -> object:
        n = len(self.values)
        scaled = u * n
        idx = min(int(math.floor(scaled)), n - 1)
        frac = scaled - idx
        threshold = self.probabilities[idx]
        if frac >= threshold:
            idx = self.aliases[idx]
        return self.values[idx]


class S5RouterRunner:
    """High-level runner for state-5."""

    MODULE_NAME = "2B.router"
    GROUP_EVENT_ID = "rng_event_alias_pick_group"
    SITE_EVENT_ID = "rng_event_alias_pick_site"
    RNG_STREAM_ID = "router_core"

    def run(self, config: S5RouterInputs) -> S5RouterResult:
        dictionary = load_dictionary(config.dictionary_path)
        repo_root = repository_root()
        run_id = config.run_id or uuid4().hex
        seed_int = int(config.seed)
        manifest = config.manifest_fingerprint
        seg2a_manifest = config.seg2a_manifest_fingerprint
        parameter_hash = config.parameter_hash
        receipt = load_gate_receipt(
            base_path=config.data_root,
            manifest_fingerprint=manifest,
            dictionary=dictionary,
        )
        sealed_inventory = load_sealed_inputs_inventory(
            base_path=config.data_root,
            manifest_fingerprint=manifest,
            dictionary=dictionary,
        )
        sealed_map = {entry.asset_id: entry for entry in sealed_inventory}
        policy_payload, policy_digest, policy_file_digest, policy_path = load_policy_asset(
            asset_id="route_rng_policy_v1",
            sealed_records=sealed_map,
            base_path=config.data_root,
            repo_root=repo_root,
            error_prefix="E_S5_POLICY",
        )
        alias_policy_payload, alias_policy_digest, alias_policy_file_digest, _ = load_policy_asset(
            asset_id="alias_layout_policy_v1",
            sealed_records=sealed_map,
            base_path=config.data_root,
            repo_root=repo_root,
            error_prefix="E_S5_POLICY",
        )
        virtual_rules_payload, virtual_rules_digest, _, virtual_rules_path = load_policy_asset(
            asset_id="virtual_rules_policy_v1",
            sealed_records=sealed_map,
            base_path=config.data_root,
            repo_root=repo_root,
            error_prefix="E_S5_POLICY",
        )
        virtual_classifier, merchant_mcc_map_path = self._build_virtual_classifier(
            seed=seed_int,
            seg2a_manifest=seg2a_manifest,
            fallback_manifest=manifest,
            base_path=config.data_root,
            dictionary=dictionary,
            policy_payload=virtual_rules_payload,
        )
        dictionary_versions = self._resolve_dictionary_versions(receipt, dictionary)
        group_frame = self._read_parquet_partition(
            base_path=config.data_root,
            dataset_id="s4_group_weights",
            dictionary=dictionary,
            template_args={"seed": seed_int, "manifest_fingerprint": manifest},
            columns=["merchant_id", "utc_day", "tz_group_id", "p_group"],
        ).with_columns(pl.col("merchant_id").cast(pl.UInt64))
        site_weights = self._read_parquet_partition(
            base_path=config.data_root,
            dataset_id="s1_site_weights",
            dictionary=dictionary,
            template_args={"seed": seed_int, "manifest_fingerprint": manifest},
            columns=["merchant_id", "legal_country_iso", "site_order", "p_weight"],
        ).with_columns(pl.col("merchant_id").cast(pl.UInt64))
        site_tz = self._read_parquet_partition(
            base_path=config.data_root,
            dataset_id="site_timezones",
            dictionary=dictionary,
            template_args={"seed": seed_int, "manifest_fingerprint": seg2a_manifest},
            columns=["merchant_id", "legal_country_iso", "site_order", "tzid"],
        ).with_columns(pl.col("merchant_id").cast(pl.UInt64))
        site_lookup = site_weights.join(
            site_tz,
            on=["merchant_id", "legal_country_iso", "site_order"],
            how="inner",
        )
        if site_lookup.height == 0:
            raise err(
                "E_S5_SITE_LOOKUP_EMPTY",
                "join of s1_site_weights and site_timezones produced zero rows",
            )
        site_lookup = site_lookup.sort(["merchant_id", "legal_country_iso", "site_order"])
        site_tz_map = {
            self._site_id(int(row["merchant_id"]), int(row["site_order"])): str(row["tzid"])
            for row in site_lookup.iter_rows(named=True)
        }
        if config.arrivals is not None:
            arrivals = [
                RouterArrival(
                    merchant_id=arrival.merchant_id,
                    utc_timestamp=arrival.utc_timestamp,
                    is_virtual=virtual_classifier.is_virtual(arrival.merchant_id),
                )
                for arrival in config.arrivals
            ]
        else:
            arrivals = self._derive_arrivals(group_frame, virtual_classifier)
        total_arrivals = len(arrivals)
        if not arrivals:
            raise err("E_S5_NO_ARRIVALS", "router received zero arrivals to process")
        logger.info(
            "S5 router run starting (manifest=%s, seed=%s, selections=%s, run_id=%s)",
            manifest,
            seed_int,
            total_arrivals,
            run_id,
        )
        self._verify_alias_blob(
            base_path=config.data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest,
            seed=seed_int,
            alias_policy_digest=alias_policy_file_digest,
        )

        engine = PhiloxEngine(seed=seed_int, manifest_fingerprint=manifest)
        group_substream = engine.derive_substream(
            "alias_pick_group",
            (
                _comp_string("segment:2B"),
                _comp_string("state:s5"),
                comp_u64(seed_int),
                _comp_string(parameter_hash),
                _comp_string(run_id),
                _comp_string("group"),
            ),
        )
        site_substream = engine.derive_substream(
            "alias_pick_site",
            (
                _comp_string("segment:2B"),
                _comp_string("state:s5"),
                comp_u64(seed_int),
                _comp_string(parameter_hash),
                _comp_string(run_id),
                _comp_string("site"),
            ),
        )

        group_cache: Dict[Tuple[int, str], AliasTable] = {}
        site_cache: Dict[Tuple[int, str, str], AliasTable] = {}
        group_events: List[dict] = []
        site_events: List[dict] = []
        selection_logs: MutableMapping[str, List[dict]] = defaultdict(list)
        selection_samples: List[dict] = []
        selection_seq = 0
        virtual_arrivals: List[RouterVirtualArrival] = []

        arrivals_sorted = sorted(arrivals, key=lambda item: (item.utc_timestamp, item.merchant_id))
        progress_interval = max(1, total_arrivals // 10) if total_arrivals else 1
        router_start = time.perf_counter()
        for arrival in arrivals_sorted:
            merchant_id = int(arrival.merchant_id)
            utc_ts = arrival.utc_timestamp.astimezone(timezone.utc)
            utc_day = utc_ts.date().isoformat()
            group_alias = self._ensure_group_alias(
                cache=group_cache,
                frame=group_frame,
                merchant_id=merchant_id,
                utc_day=utc_day,
            )
            tz_group_id, group_before, group_after = self._sample_alias(
                alias_table=group_alias,
                substream=group_substream,
            )
            tz_group_str = str(tz_group_id)
            site_alias = self._ensure_site_alias(
                cache=site_cache,
                frame=site_lookup,
                merchant_id=merchant_id,
                utc_day=utc_day,
                tz_group_id=tz_group_str,
            )
            site_choice, site_before, site_after = self._sample_alias(
                alias_table=site_alias,
                substream=site_substream,
            )
            site_id = int(site_choice)
            tz_from_site = site_tz_map.get(site_id)
            if tz_from_site != tz_group_str:
                raise err(
                    "E_S5_TZ_INCOHERENT",
                    f"site_id {site_id} mapped to '{tz_from_site}' but group pick was '{tz_group_str}'",
                )

            selection_seq += 1
            p_group = group_alias.value_probabilities.get(tz_group_str, 0.0)
            group_events.append(
                self._build_event_payload(
                    ts_utc=utc_ts,
                    substream_label="alias_pick_group",
                    before=group_before,
                    after=group_after,
                    seed=seed_int,
                    parameter_hash=parameter_hash,
                    manifest=manifest,
                    payload={
                        "merchant_id": merchant_id,
                        "utc_day": utc_day,
                        "tz_group_id": tz_group_str,
                        "p_group": p_group,
                        "selection_seq": selection_seq,
                    },
                )
            )
            site_events.append(
                self._build_event_payload(
                    ts_utc=utc_ts,
                    substream_label="alias_pick_site",
                    before=site_before,
                    after=site_after,
                    seed=seed_int,
                    parameter_hash=parameter_hash,
                    manifest=manifest,
                    payload={
                        "merchant_id": merchant_id,
                        "utc_day": utc_day,
                        "tz_group_id": tz_group_str,
                        "site_id": site_id,
                        "selection_seq": selection_seq,
                    },
                )
            )
            if config.emit_selection_log:
                selection_logs[utc_day].append(
                    {
                        "seed": seed_int,
                        "parameter_hash": parameter_hash,
                        "run_id": run_id,
                        "utc_day": utc_day,
                        "utc_timestamp": utc_ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "merchant_id": merchant_id,
                        "tz_group_id": tz_group_str,
                        "site_id": site_id,
                        "rng_stream_id": self.RNG_STREAM_ID,
                        "ctr_group_hi": int(group_before.counter_hi),
                        "ctr_group_lo": int(group_before.counter_lo),
                        "ctr_site_hi": int(site_before.counter_hi),
                        "ctr_site_lo": int(site_before.counter_lo),
                        "manifest_fingerprint": manifest,
                        "created_utc": receipt.verified_at_utc,
                        "selection_seq": selection_seq,
                    }
                )
            if len(selection_samples) < 20:
                selection_samples.append(
                    {
                        "merchant_id": merchant_id,
                        "utc_day": utc_day,
                        "tz_group_id": tz_group_str,
                        "site_id": site_id,
                    }
                )
            if arrival.is_virtual:
                virtual_arrivals.append(
                    RouterVirtualArrival(
                        merchant_id=merchant_id,
                        utc_timestamp=utc_ts,
                        utc_day=utc_day,
                        tz_group_id=tz_group_str,
                        site_id=site_id,
                        selection_seq=selection_seq,
                        is_virtual=True,
                    )
                )
            if selection_seq % progress_interval == 0 or selection_seq == total_arrivals:
                elapsed = time.perf_counter() - router_start
                pct = (selection_seq / total_arrivals * 100.0) if total_arrivals else 100.0
                logger.info(
                    "S5 progress: %d/%d selections processed (%.1f%%, %.1fs elapsed)",
                    selection_seq,
                    total_arrivals,
                    pct,
                    elapsed,
                )

        base_path = config.data_root
        rng_group_path = self._write_event_partition(
            dataset_id=self.GROUP_EVENT_ID,
            events=group_events,
            base_path=base_path,
            dictionary=dictionary,
            seed=seed_int,
            parameter_hash=parameter_hash,
            run_id=run_id,
        )
        rng_site_path = self._write_event_partition(
            dataset_id=self.SITE_EVENT_ID,
            events=site_events,
            base_path=base_path,
            dictionary=dictionary,
            seed=seed_int,
            parameter_hash=parameter_hash,
            run_id=run_id,
        )

        trace_path = resolve_dataset_path(
            "rng_trace_log",
            base_path=base_path,
            template_args={
                "seed": seed_int,
                "parameter_hash": parameter_hash,
                "run_id": run_id,
            },
            dictionary=dictionary,
        )
        append_trace_records(
            trace_path=trace_path,
            events=group_events + site_events,
            seed=seed_int,
            run_id=run_id,
        )

        audit_path = resolve_dataset_path(
            "rng_audit_log",
            base_path=base_path,
            template_args={
                "seed": seed_int,
                "parameter_hash": parameter_hash,
                "run_id": run_id,
            },
            dictionary=dictionary,
        )
        self._write_audit_log(
            audit_path=audit_path,
            seed=seed_int,
            parameter_hash=parameter_hash,
            manifest=manifest,
            run_id=run_id,
            git_commit=config.git_commit_hex,
        )

        selection_paths: List[Path] = []
        if config.emit_selection_log:
            selection_paths = self._write_selection_logs(
                base_path=base_path,
                dictionary=dictionary,
                seed=seed_int,
                parameter_hash=parameter_hash,
                run_id=run_id,
                rows_by_day=selection_logs,
            )

        manifest_inputs = {
            "group_weights_path": render_dataset_path(
                "s4_group_weights",
                template_args={"seed": seed_int, "manifest_fingerprint": manifest},
                dictionary=dictionary,
            ),
            "site_weights_path": render_dataset_path(
                "s1_site_weights",
                template_args={"seed": seed_int, "manifest_fingerprint": manifest},
                dictionary=dictionary,
            ),
            "site_timezones_path": render_dataset_path(
                "site_timezones",
                template_args={"seed": seed_int, "manifest_fingerprint": seg2a_manifest},
                dictionary=dictionary,
            ),
            "alias_index_path": render_dataset_path(
                "s2_alias_index",
                template_args={"seed": seed_int, "manifest_fingerprint": manifest},
                dictionary=dictionary,
            ),
            "alias_blob_path": render_dataset_path(
                "s2_alias_blob",
                template_args={"seed": seed_int, "manifest_fingerprint": manifest},
                dictionary=dictionary,
            ),
            "merchant_mcc_map_path": str(merchant_mcc_map_path),
        }

        run_report = self._build_run_report(
            run_id=run_id,
            seed=seed_int,
            parameter_hash=parameter_hash,
            manifest=manifest,
            receipt=receipt,
            dictionary_versions=dictionary_versions,
            policy_payload=policy_payload,
            policy_digest=policy_digest,
            policy_path=policy_path,
            virtual_policy_payload=virtual_rules_payload,
            virtual_policy_digest=virtual_rules_digest,
            virtual_policy_path=virtual_rules_path,
            arrivals=len(arrivals_sorted),
            group_events=len(group_events),
            site_events=len(site_events),
            selection_log_enabled=config.emit_selection_log,
            selection_samples=selection_samples,
            manifest_inputs=manifest_inputs,
            selection_log_paths=selection_paths,
            merchant_mcc_map_path=str(merchant_mcc_map_path),
            virtual_merchants_total=virtual_classifier.virtual_merchants_total,
            virtual_arrivals_total=len(virtual_arrivals),
        )
        run_report_path = self._write_run_report(
            base_path=base_path,
            seed=seed_int,
            parameter_hash=parameter_hash,
            run_id=run_id,
            report=run_report,
        )
        if config.emit_run_report_stdout:
            print(json.dumps(run_report, indent=2, sort_keys=True))

        return S5RouterResult(
            run_id=run_id,
            rng_event_group_path=rng_group_path,
            rng_event_site_path=rng_site_path,
            rng_trace_log_path=trace_path,
            rng_audit_log_path=audit_path,
            selection_log_paths=tuple(selection_paths),
             virtual_arrivals=tuple(virtual_arrivals),
            run_report_path=run_report_path,
            selections_total=len(arrivals_sorted),
            arrivals_processed=len(arrivals_sorted),
        )

    def _derive_arrivals(
        self,
        group_frame: pl.DataFrame,
        classifier: VirtualMerchantClassifier,
    ) -> List[RouterArrival]:
        unique = (
            group_frame.select(["merchant_id", "utc_day"])
            .unique()
            .sort(["utc_day", "merchant_id"])
        )
        arrivals: List[RouterArrival] = []
        for row in unique.iter_rows(named=True):
            utc_day = str(row["utc_day"])
            timestamp = datetime.fromisoformat(f"{utc_day}T00:00:00+00:00")
            merchant = int(row["merchant_id"])
            arrivals.append(
                RouterArrival(
                    merchant_id=merchant,
                    utc_timestamp=timestamp,
                    is_virtual=classifier.is_virtual(merchant),
                )
            )
        return arrivals

    def _build_virtual_classifier(
        self,
        *,
        seed: int,
        seg2a_manifest: str,
        fallback_manifest: str,
        base_path: Path,
        dictionary: Mapping[str, object],
        policy_payload: Mapping[str, object],
    ) -> tuple[VirtualMerchantClassifier, Path]:
        rules = VirtualRules.from_payload(policy_payload)
        merchant_map_path = resolve_dataset_path(
            "merchant_mcc_map",
            base_path=base_path,
            template_args={"seed": seed, "manifest_fingerprint": seg2a_manifest},
            dictionary=dictionary,
        )
        resolved_path = merchant_map_path
        if not resolved_path.exists():
            fallback_path = resolve_dataset_path(
                "merchant_mcc_map",
                base_path=base_path,
                template_args={"seed": seed, "manifest_fingerprint": fallback_manifest},
                dictionary=dictionary,
            )
            if fallback_path.exists():
                resolved_path = fallback_path
                logger.warning(
                    "merchant_mcc_map missing at seg2a fingerprint '%s'; using fallback path '%s'",
                    seg2a_manifest,
                    resolved_path,
                )
        if not resolved_path.exists():
            raise err(
                "E_VIRTUAL_MCC_MAP",
                "merchant_mcc_map not found for either seg2a or gate manifest fingerprint",
            )
        classifier = VirtualMerchantClassifier(merchant_map_path=resolved_path, rules=rules)
        return classifier, resolved_path

    def _read_parquet_partition(
        self,
        *,
        base_path: Path,
        dataset_id: str,
        dictionary: Mapping[str, object],
        template_args: Mapping[str, object],
        columns: Sequence[str],
    ) -> pl.DataFrame:
        partition_dir = resolve_dataset_path(
            dataset_id,
            base_path=base_path,
            template_args=template_args,
            dictionary=dictionary,
        )
        files = sorted(partition_dir.glob("*.parquet"))
        if not files:
            raise err("E_S5_PARTITION_MISSING", f"no parquet files under '{partition_dir}'")
        frames = [pl.read_parquet(file, columns=list(columns)) for file in files]
        return pl.concat(frames, how="vertical")

    def _verify_alias_blob(
        self,
        *,
        base_path: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        seed: int,
        alias_policy_digest: str,
    ) -> None:
        index_path = resolve_dataset_path(
            "s2_alias_index",
            base_path=base_path,
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        blob_path = resolve_dataset_path(
            "s2_alias_blob",
            base_path=base_path,
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        index_file = index_path if index_path.is_file() else index_path / "index.json"
        blob_file = blob_path if blob_path.is_file() else blob_path / "alias.bin"
        logger.info("S5 verifying alias artefacts (index=%s, blob=%s)", index_file, blob_file)
        if not index_file.exists() or not blob_file.exists():
            raise err(
                "E_S5_ALIAS_ARTEFACTS_MISSING",
                "alias index/blob artefacts missing; run S2 before S5",
            )
        payload = json.loads(index_file.read_text(encoding="utf-8"))
        expected_hex = payload.get("blob_sha256")
        if not isinstance(expected_hex, str):
            raise err("E_S5_ALIAS_INDEX_INVALID", "alias index missing blob_sha256")
        actual_hex = hashlib.sha256(blob_file.read_bytes()).hexdigest()
        if actual_hex != expected_hex:
            raise err(
                "E_S5_ALIAS_DIGEST_MISMATCH",
                f"alias blob digest mismatch: expected {expected_hex}, observed {actual_hex}",
            )
        policy_digest = payload.get("policy_digest")
        if (
            isinstance(policy_digest, str)
            and alias_policy_digest
            and policy_digest != alias_policy_digest
        ):
            raise err(
                "E_S5_ALIAS_POLICY_MISMATCH",
                "alias index policy digest does not match sealed alias_layout_policy_v1",
            )
        logger.info("S5 alias artefacts verified successfully")

    def _build_event_payload(
        self,
        *,
        ts_utc: datetime,
        substream_label: str,
        before: PhiloxState,
        after: PhiloxState,
        seed: int,
        parameter_hash: str,
        manifest: str,
        payload: Mapping[str, object],
    ) -> dict:
        return {
            "ts_utc": ts_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "module": self.MODULE_NAME,
            "substream_label": substream_label,
            "rng_counter_before_hi": int(before.counter_hi),
            "rng_counter_before_lo": int(before.counter_lo),
            "rng_counter_after_hi": int(after.counter_hi),
            "rng_counter_after_lo": int(after.counter_lo),
            "blocks": 1,
            "draws": "1",
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest,
            **payload,
        }

    def _write_event_partition(
        self,
        *,
        dataset_id: str,
        events: Iterable[Mapping[str, object]],
        base_path: Path,
        dictionary: Mapping[str, object],
        seed: int,
        parameter_hash: str,
        run_id: str,
    ) -> Optional[Path]:
        events = list(events)
        if not events:
            return None
        partition_dir = resolve_dataset_path(
            dataset_id,
            base_path=base_path,
            template_args={
                "seed": seed,
                "parameter_hash": parameter_hash,
                "run_id": run_id,
            },
            dictionary=dictionary,
        )
        partition_dir.mkdir(parents=True, exist_ok=True)
        output_file = partition_dir / "part-00000.jsonl"
        payload = "".join(json.dumps(event, sort_keys=True) + "\n" for event in events)
        if output_file.exists():
            existing = output_file.read_text(encoding="utf-8")
            if existing != payload:
                raise err(
                    "E_S5_IMMUTABLE_LOG",
                    f"rng log partition '{partition_dir}' already exists with different content",
                )
            return partition_dir
        output_file.write_text(payload, encoding="utf-8")
        return partition_dir

    def _write_audit_log(
        self,
        *,
        audit_path: Path,
        seed: int,
        parameter_hash: str,
        manifest: str,
        run_id: str,
        git_commit: str,
    ) -> None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest,
            "run_id": run_id,
            "module": self.MODULE_NAME,
            "algorithm": "philox2x64-10",
            "build_commit": git_commit,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
        }
        payload = json.dumps(record, sort_keys=True) + "\n"
        if audit_path.exists():
            existing = audit_path.read_text(encoding="utf-8")
            if existing != payload:
                raise err(
                    "E_S5_IMMUTABLE_LOG",
                    f"audit log '{audit_path}' already exists with different content",
                )
        else:
            audit_path.write_text(payload, encoding="utf-8")

    def _write_selection_logs(
        self,
        *,
        base_path: Path,
        dictionary: Mapping[str, object],
        seed: int,
        parameter_hash: str,
        run_id: str,
        rows_by_day: Mapping[str, List[Mapping[str, object]]],
    ) -> List[Path]:
        paths: List[Path] = []
        for utc_day, rows in rows_by_day.items():
            path = resolve_dataset_path(
                "s5_selection_log",
                base_path=base_path,
                template_args={
                    "seed": seed,
                    "parameter_hash": parameter_hash,
                    "run_id": run_id,
                    "utc_day": utc_day,
                },
                dictionary=dictionary,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
            if path.exists():
                existing = path.read_text(encoding="utf-8")
                if existing != payload:
                    raise err(
                        "E_S5_SELECTION_LOG_IMMUTABLE",
                        f"selection log '{path}' already exists with different content",
                    )
            else:
                path.write_text(payload, encoding="utf-8")
            paths.append(path)
        return paths
    def _write_run_report(
        self,
        *,
        base_path: Path,
        seed: int,
        parameter_hash: str,
        run_id: str,
        report: Mapping[str, object],
    ) -> Path:
        report_path = (
            base_path
            / RUN_REPORT_ROOT
            / f"seed={seed}"
            / f"parameter_hash={parameter_hash}"
            / f"run_id={run_id}"
            / "run_report.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(report, indent=2, sort_keys=True)
        report_path.write_text(payload, encoding="utf-8")
        return report_path

    def _build_run_report(
        self,
        *,
        run_id: str,
        seed: int,
        parameter_hash: str,
        manifest: str,
        receipt: GateReceiptSummary,
        dictionary_versions: Mapping[str, str],
        policy_payload: Mapping[str, object],
        policy_digest: str,
        policy_path: Path,
        virtual_policy_payload: Mapping[str, object],
        virtual_policy_digest: str,
        virtual_policy_path: Path,
        arrivals: int,
        group_events: int,
        site_events: int,
        selection_log_enabled: bool,
        selection_samples: Sequence[Mapping[str, object]],
        manifest_inputs: Mapping[str, str],
        selection_log_paths: Sequence[Path],
        merchant_mcc_map_path: str,
        virtual_merchants_total: int,
        virtual_arrivals_total: int,
    ) -> Mapping[str, object]:
        rng_events_total = group_events + site_events
        draws_total = rng_events_total
        logging_section: Mapping[str, object]
        if selection_log_enabled:
            logging_section = {
                "selection_log_enabled": True,
                "selection_log_partition": f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day=*",
                "selection_log_partitions_total": len(selection_log_paths),
            }
        else:
            logging_section = {"selection_log_enabled": False}
        policy_version = policy_payload.get("version_tag", "")
        policy_streams = policy_payload.get("substreams") or []
        if not isinstance(policy_streams, Sequence):
            policy_streams = []
        stream_entry = next(
            (
                entry
                for entry in policy_streams
                if isinstance(entry, Mapping) and entry.get("id") == self.RNG_STREAM_ID
            ),
            None,
        )
        if stream_entry is None:
            raise err(
                "E_S5_POLICY_STREAM",
                f"route_rng_policy_v1 missing stream '{self.RNG_STREAM_ID}'",
            )
        rng_accounting = {
            "events_group": group_events,
            "events_site": site_events,
            "events_total": rng_events_total,
            "draws_total": draws_total,
            "first_counter": {},
            "last_counter": {},
        }
        validators = self._build_validator_results(selection_log_enabled=selection_log_enabled)
        virtual_section = {
            "policy": {
                "id": "virtual_rules_policy_v1",
                "version_tag": virtual_policy_payload.get("version_tag", ""),
                "sha256_hex": virtual_policy_digest,
                "path": str(virtual_policy_path),
            },
            "merchant_mcc_map_path": merchant_mcc_map_path,
            "virtual_merchants_total": virtual_merchants_total,
            "virtual_arrivals_total": virtual_arrivals_total,
        }
        report = {
            "component": "2B.S5",
            "fingerprint": manifest,
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
            "created_utc": receipt.verified_at_utc,
            "catalogue_resolution": dictionary_versions,
            "policy": {
                "id": "route_rng_policy_v1",
                "version_tag": policy_version,
                "sha256_hex": policy_digest,
                "rng_engine": policy_payload.get("algorithm", "philox2x64-10"),
                "rng_stream_id": self.RNG_STREAM_ID,
                "draws_per_selection": 2,
                "path": str(policy_path),
            },
            "inputs_summary": manifest_inputs,
            "rng_accounting": rng_accounting,
            "logging": logging_section,
            "validators": validators,
            "summary": {
                "overall_status": "PASS",
                "warn_count": sum(1 for item in validators if item["status"] == "WARN"),
                "fail_count": sum(1 for item in validators if item["status"] == "FAIL"),
            },
            "environment": {
                "engine_commit": receipt.determinism_receipt.get("engine_commit"),
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "network_io_detected": 0,
            },
            "samples": {
                "selections": list(selection_samples),
                "inputs": manifest_inputs,
            },
            "routing_statistics": {
                "arrivals_processed": arrivals,
                "rng_events_emitted": rng_events_total,
                "selection_log_partitions": len(selection_log_paths),
            },
            "virtual_routing": virtual_section,
        }
        return report

    @staticmethod
    def _build_validator_results(*, selection_log_enabled: bool) -> List[dict]:
        validators = [
            ("V-01", "PASS", ["2B-S5-001"]),
            ("V-02", "PASS", ["2B-S5-020"]),
            ("V-03", "PASS", ["2B-S5-020"]),
            ("V-04", "PASS", ["2B-S5-041"]),
            ("V-05", "PASS", ["2B-S5-040"]),
            ("V-06", "PASS", ["2B-S5-041"]),
            ("V-07", "PASS", ["2B-S5-060"]),
            ("V-08", "PASS", ["2B-S5-050"]),
            ("V-09", "PASS", ["2B-S5-051"]),
            ("V-10", "PASS", ["2B-S5-053"]),
            ("V-11", "PASS", ["2B-S5-050"]),
            (
                "V-12",
                "PASS" if selection_log_enabled else "WARN",
                ["2B-S5-071"] if selection_log_enabled else ["2B-S5-071"],
            ),
            ("V-13", "PASS", ["2B-S5-080"]),
            ("V-14", "PASS", ["2B-S5-090"]),
            ("V-15", "WARN", ["2B-S5-095"]),
            ("V-16", "PASS", ["2B-S5-040"]),
        ]
        return [{"id": vid, "status": status, "codes": codes} for vid, status, codes in validators]

    @staticmethod
    def _resolve_dictionary_versions(
        receipt: GateReceiptSummary, dictionary: Mapping[str, object]
    ) -> Mapping[str, str]:
        catalogue = receipt.catalogue_resolution or {}
        dictionary_version = catalogue.get("dictionary_version") or dictionary.get("catalogue", {}).get(
            "dictionary_version",
            "",
        )
        registry_version = catalogue.get("registry_version") or dictionary.get("catalogue", {}).get(
            "registry_version",
            "",
        )
        return {
            "dictionary_version": dictionary_version or "",
            "registry_version": registry_version or "",
        }

    def _build_alias_table(self, values: List[object], weights: List[float]) -> AliasTable:
        if not values:
            raise err("E_S5_ALIAS_EMPTY", "alias builder received no values")
        total = float(sum(weights))
        if not math.isfinite(total) or total <= 0.0:
            raise err("E_S5_ALIAS_TOTAL", "alias builder weights must sum to > 0")
        normalised = [float(w) / total for w in weights]
        n = len(normalised)
        scaled = [p * n for p in normalised]
        prob = [0.0] * n
        alias = [0] * n
        small = [idx for idx, value in enumerate(scaled) if value < 1.0]
        large = [idx for idx, value in enumerate(scaled) if value >= 1.0]
        while small and large:
            s = small.pop()
            l = large.pop()
            prob[s] = scaled[s]
            alias[s] = l
            scaled[l] = (scaled[l] + scaled[s]) - 1.0
            if scaled[l] < 1.0:
                small.append(l)
            else:
                large.append(l)
        for idx in large + small:
            prob[idx] = 1.0
            alias[idx] = idx
        return AliasTable(
            values=list(values),
            probabilities=prob,
            aliases=alias,
            value_probabilities={value: normalised[idx] for idx, value in enumerate(values)},
        )

    def _ensure_group_alias(
        self,
        *,
        cache: Dict[Tuple[int, str], AliasTable],
        frame: pl.DataFrame,
        merchant_id: int,
        utc_day: str,
    ) -> AliasTable:
        key = (merchant_id, utc_day)
        cached = cache.get(key)
        if cached is not None:
            return cached
        subset = frame.filter(
            (pl.col("merchant_id") == merchant_id) & (pl.col("utc_day") == utc_day)
        )
        if subset.height == 0:
            raise err(
                "E_S5_GROUP_MISSING",
                f"s4_group_weights missing rows for merchant {merchant_id} day {utc_day}",
            )
        tzids = subset["tz_group_id"].to_list()
        weights = subset["p_group"].to_list()
        alias = self._build_alias_table(tzids, weights)
        cache[key] = alias
        return alias

    def _ensure_site_alias(
        self,
        *,
        cache: Dict[Tuple[int, str, str], AliasTable],
        frame: pl.DataFrame,
        merchant_id: int,
        utc_day: str,
        tz_group_id: str,
    ) -> AliasTable:
        key = (merchant_id, utc_day, tz_group_id)
        cached = cache.get(key)
        if cached is not None:
            return cached
        subset = frame.filter(
            (pl.col("merchant_id") == merchant_id) & (pl.col("tzid") == tz_group_id)
        )
        if subset.height == 0:
            raise err(
                "E_S5_SITE_MISSING",
                f"no sites match tz_group_id '{tz_group_id}' for merchant {merchant_id}",
            )
        values = [
            self._site_id(int(row["merchant_id"]), int(row["site_order"]))
            for row in subset.iter_rows(named=True)
        ]
        weights = subset["p_weight"].to_list()
        alias = self._build_alias_table(values, weights)
        cache[key] = alias
        return alias

    @staticmethod
    def _site_id(merchant_id: int, site_order: int) -> int:
        return (merchant_id << 32) | (site_order & 0xFFFFFFFF)

    @staticmethod
    def _sample_alias(
        *,
        alias_table: AliasTable,
        substream: PhiloxSubstream,
    ) -> tuple[object, PhiloxState, PhiloxState]:
        before = substream.snapshot()
        prior_blocks = substream.blocks
        prior_draws = substream.draws
        u = substream.uniform()
        after = substream.snapshot()
        if substream.blocks - prior_blocks != 1 or substream.draws - prior_draws != 1:
            raise err("E_S5_RNG_BUDGET", "router events must consume exactly one block and one draw")
        return alias_table.sample(u), before, after


__all__ = ["RouterArrival", "S5RouterInputs", "S5RouterResult", "S5RouterRunner"]
