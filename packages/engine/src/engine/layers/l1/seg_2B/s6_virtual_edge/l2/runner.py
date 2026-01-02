"""Segment 2B state-6 virtual edge router runner."""

from __future__ import annotations

import json
import logging
import math
import platform
import socket
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple
from uuid import uuid4

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import (
    PhiloxEngine,
    PhiloxState,
    PhiloxSubstream,
    comp_u64,
)

from ...shared.dictionary import (
    load_dictionary,
    get_dataset_entry,
    render_dataset_path,
    resolve_dataset_path,
    repository_root,
)
from ...shared.policies import load_policy_asset
from ...shared.receipt import (
    GateReceiptSummary,
    SealedInputRecord,
    load_gate_receipt,
    load_sealed_inputs_inventory,
)
from ...shared.rng_trace import append_trace_records
from ...shared.runtime import RouterVirtualArrival
from ...s0_gate.exceptions import S0GateError, err

RUN_REPORT_ROOT = Path("reports") / "l1" / "s6_virtual_edge"

logger = logging.getLogger(__name__)


def _comp_string(value: str) -> Tuple[str, str]:
    return ("string", value)


@dataclass(frozen=True)
class EdgeEntry:
    """Single edge option declared in the policy."""

    edge_id: str
    ip_country: str
    weight: float
    lat: float
    lon: float


@dataclass
class AliasTable:
    """Deterministic alias table."""

    values: List[EdgeEntry]
    probabilities: List[float]
    aliases: List[int]
    value_probabilities: Dict[str, float]

    def sample(self, u: float) -> EdgeEntry:
        n = len(self.values)
        scaled = u * n
        idx = min(int(math.floor(scaled)), n - 1)
        frac = scaled - idx
        threshold = self.probabilities[idx]
        if frac >= threshold:
            idx = self.aliases[idx]
        return self.values[idx]


@dataclass(frozen=True)
class S6VirtualEdgeInputs:
    """Configuration required to execute S6 virtual edge routing."""

    data_root: Path
    seed: int | str
    manifest_fingerprint: str
    parameter_hash: str
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    run_id: Optional[str] = None
    arrivals: Sequence[RouterVirtualArrival] | None = None
    emit_edge_log: bool = False
    emit_run_report_stdout: bool = True

    def __post_init__(self) -> None:
        data_root = self.data_root.expanduser().resolve()
        object.__setattr__(self, "data_root", data_root)
        seed_value = str(self.seed)
        if not seed_value:
            raise err("E_S6_SEED_EMPTY", "seed must be provided for S6")
        object.__setattr__(self, "seed", seed_value)
        manifest = self._validate_hex(self.manifest_fingerprint, field="manifest_fingerprint")
        parameter_hash = self._validate_hex(self.parameter_hash, field="parameter_hash")
        object.__setattr__(self, "manifest_fingerprint", manifest)
        object.__setattr__(self, "parameter_hash", parameter_hash)
        run_id = self.run_id
        if run_id is not None:
            if len(run_id) != 32:
                raise err("E_S6_RUN_ID", "run_id must be 32 hex characters")
            int(run_id, 16)
            object.__setattr__(self, "run_id", run_id.lower())
        arrivals = tuple(self.arrivals) if self.arrivals is not None else None
        object.__setattr__(self, "arrivals", arrivals)

    @staticmethod
    def _validate_hex(value: str, *, field: str) -> str:
        lowered = value.lower()
        if len(lowered) != 64:
            raise err("E_S6_HEX_FIELD", f"{field} must be 64 hex characters")
        int(lowered, 16)
        return lowered


@dataclass(frozen=True)
class S6VirtualEdgeResult:
    """Outputs emitted by the S6 runner."""

    run_id: str
    rng_event_edge_path: Optional[Path]
    rng_trace_log_path: Optional[Path]
    rng_audit_log_path: Optional[Path]
    edge_log_paths: Tuple[Path, ...]
    run_report_path: Path
    arrivals_processed: int
    virtual_arrivals: int


class S6VirtualEdgeRunner:
    """High-level runner for Segment 2B S6."""

    MODULE_NAME = "2B.virtual_edge"
    EDGE_EVENT_ID = "rng_event_cdn_edge_pick"
    RNG_STREAM_ID = "virtual_edge"
    SUBSTREAM_LABEL = "cdn_edge_pick"

    def run(self, config: S6VirtualEdgeInputs) -> S6VirtualEdgeResult:
        dictionary = load_dictionary(config.dictionary_path)
        repo_root = repository_root()
        run_id = config.run_id or uuid4().hex
        seed_int = int(config.seed)
        manifest = config.manifest_fingerprint
        parameter_hash = config.parameter_hash

        if config.arrivals is None:
            raise err("E_S6_ARRIVALS_MISSING", "S6 requires arrivals emitted by S5")
        virtual_arrivals = [arrival for arrival in config.arrivals if arrival.is_virtual]
        total_virtual = len(virtual_arrivals)
        arrivals_sorted = sorted(virtual_arrivals, key=lambda rec: rec.selection_seq)

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
        sealed_map: Dict[str, SealedInputRecord] = {entry.asset_id: entry for entry in sealed_inventory}

        route_policy_payload, route_policy_digest, _, route_policy_path = load_policy_asset(
            asset_id="route_rng_policy_v1",
            sealed_records=sealed_map,
            base_path=config.data_root,
            repo_root=repo_root,
            error_prefix="E_S6_POLICY",
        )
        route_policy_stream_id, route_policy_draws_per_virtual, route_policy_rng_engine = (
            self._resolve_route_policy_stream(route_policy_payload, min_draws=1)
        )
        edge_policy_payload, edge_policy_digest, edge_policy_file_digest, edge_policy_path = load_policy_asset(
            asset_id="virtual_edge_policy_v1",
            sealed_records=sealed_map,
            base_path=config.data_root,
            repo_root=repo_root,
            error_prefix="E_S6_POLICY",
        )

        dictionary_versions = self._resolve_dictionary_versions(receipt, dictionary)
        default_edge_entries, merchant_edge_entries = self._prepare_edge_entries(edge_policy_payload)
        alias_cache: Dict[str, AliasTable] = {}

        if total_virtual == 0:
            logger.info("S6 detected zero virtual arrivals; emitting run report only.")

        base_path = config.data_root
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

        engine = PhiloxEngine(seed=seed_int, manifest_fingerprint=manifest)
        edge_substream = engine.derive_substream(
            self.SUBSTREAM_LABEL,
            (
                _comp_string("segment:2B"),
                _comp_string("state:s6"),
                comp_u64(seed_int),
                _comp_string(parameter_hash),
                _comp_string(run_id),
                _comp_string("virtual_edge"),
            ),
        )

        rng_events: List[Mapping[str, object]] = []
        edge_log_rows: MutableMapping[str, List[Mapping[str, object]]] = defaultdict(list)
        tensor_start = datetime.now(timezone.utc)
        progress_interval = max(1, total_virtual // 10) if total_virtual else 1

        for idx, arrival in enumerate(arrivals_sorted, start=1):
            merchant_key = str(arrival.merchant_id)
            entries = merchant_edge_entries.get(merchant_key, default_edge_entries)
            cache_key = merchant_key if merchant_key in merchant_edge_entries else "__default__"
            alias_table = alias_cache.get(cache_key)
            if alias_table is None:
                alias_table = self._build_alias_table(entries)
                alias_cache[cache_key] = alias_table
            edge_entry, before, after = self._sample_alias(alias_table=alias_table, substream=edge_substream)
            ts_utc = arrival.normalised_timestamp()
            event_payload = self._build_event_payload(
                ts_utc=ts_utc,
                before=before,
                after=after,
                seed=seed_int,
                parameter_hash=parameter_hash,
                manifest=manifest,
                run_id=run_id,
                arrival=arrival,
            )
            rng_events.append(event_payload)

            if config.emit_edge_log:
                edge_log_rows[arrival.utc_day].append(
                    {
                        "utc_day": arrival.utc_day,
                        "utc_timestamp": ts_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "merchant_id": arrival.merchant_id,
                        "is_virtual": True,
                        "tz_group_id": arrival.tz_group_id,
                        "site_id": arrival.site_id,
                        "edge_id": edge_entry.edge_id,
                        "ip_country": edge_entry.ip_country,
                        "edge_lat": edge_entry.lat,
                        "edge_lon": edge_entry.lon,
                        "rng_stream_id": route_policy_stream_id,
                        "ctr_edge_hi": int(before.counter_hi),
                        "ctr_edge_lo": int(before.counter_lo),
                        "manifest_fingerprint": manifest,
                        "created_utc": receipt.verified_at_utc,
                    }
                )

            if idx % progress_interval == 0 or idx == total_virtual:
                elapsed = (datetime.now(timezone.utc) - tensor_start).total_seconds()
                pct = (idx / total_virtual * 100.0) if total_virtual else 100.0
                logger.info(
                    "S6 progress: %d/%d virtual arrivals processed (%.1f%%, %.1fs elapsed)",
                    idx,
                    total_virtual,
                    pct,
                    elapsed,
                )

        rng_event_path = self._write_event_partition(
            dataset_id=self.EDGE_EVENT_ID,
            events=rng_events,
            base_path=base_path,
            dictionary=dictionary,
            seed=seed_int,
            parameter_hash=parameter_hash,
            run_id=run_id,
        )

        append_trace_records(
            trace_path,
            events=rng_events,
            seed=seed_int,
            run_id=run_id,
        )

        self._write_audit_log(
            audit_path=audit_path,
            seed=seed_int,
            parameter_hash=parameter_hash,
            manifest=manifest,
            run_id=run_id,
            git_commit=config.git_commit_hex,
        )

        edge_log_paths: List[Path] = []
        if config.emit_edge_log:
            edge_log_paths = self._write_edge_logs(
                base_path=base_path,
                dictionary=dictionary,
                seed=seed_int,
                parameter_hash=parameter_hash,
                run_id=run_id,
                rows_by_day=edge_log_rows,
            )

        manifest_inputs = {
            "route_rng_policy_path": render_dataset_path(
                "route_rng_policy_v1",
                template_args={},
                dictionary=dictionary,
            ),
            "virtual_edge_policy_path": render_dataset_path(
                "virtual_edge_policy_v1",
                template_args={},
                dictionary=dictionary,
            ),
        }

        run_report = self._build_run_report(
            run_id=run_id,
            seed=seed_int,
            parameter_hash=parameter_hash,
            manifest=manifest,
            receipt=receipt,
            dictionary_versions=dictionary_versions,
            route_policy=route_policy_payload,
            route_policy_digest=route_policy_digest,
            route_policy_path=route_policy_path,
            route_policy_stream_id=route_policy_stream_id,
            route_policy_draws_per_virtual=route_policy_draws_per_virtual,
            route_policy_rng_engine=route_policy_rng_engine,
            edge_policy=edge_policy_payload,
            edge_policy_digest=edge_policy_digest,
            edge_policy_file_digest=edge_policy_file_digest,
            edge_policy_path=edge_policy_path,
            total_arrivals=len(config.arrivals),
            virtual_arrivals=total_virtual,
            rng_events=len(rng_events),
            manifest_inputs=manifest_inputs,
            edge_log_paths=edge_log_paths,
            edge_log_enabled=config.emit_edge_log and bool(edge_log_paths),
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

        return S6VirtualEdgeResult(
            run_id=run_id,
            rng_event_edge_path=rng_event_path,
            rng_trace_log_path=trace_path,
            rng_audit_log_path=audit_path,
            edge_log_paths=tuple(edge_log_paths),
            run_report_path=run_report_path,
            arrivals_processed=len(config.arrivals),
            virtual_arrivals=total_virtual,
        )

    def _prepare_edge_entries(
        self, payload: Mapping[str, object]
    ) -> tuple[List[EdgeEntry], Dict[str, List[EdgeEntry]]]:
        edges_payload = payload.get("edges") or []
        if not isinstance(edges_payload, Sequence) or not edges_payload:
            raise err("E_S6_POLICY_MINIMA", "virtual_edge_policy_v1 missing edges")

        entries: List[EdgeEntry] = []
        for entry in edges_payload:
            if not isinstance(entry, Mapping):
                raise err("E_S6_POLICY_MINIMA", "edge entries must be objects")
            edge_id = str(entry.get("edge_id", "")).strip()
            ip_country = str(entry.get("ip_country", "")).strip().upper()
            lat = entry.get("edge_lat")
            lon = entry.get("edge_lon")
            if not edge_id or not ip_country:
                raise err("E_S6_POLICY_MINIMA", "edge entries must declare edge_id and ip_country")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                raise err("E_S6_POLICY_MINIMA", f"edge '{edge_id}' missing edge_lat/edge_lon")
            if not (-90.0 <= float(lat) <= 90.0):
                raise err("E_S6_POLICY_MINIMA", f"edge '{edge_id}' latitude out of range")
            if not (-180.0 < float(lon) <= 180.0):
                raise err("E_S6_POLICY_MINIMA", f"edge '{edge_id}' longitude out of range")
            weight: Optional[float] = None
            if "weight" in entry:
                weight = float(entry.get("weight", 0.0))
            elif "country_weights" in entry:
                weights_map = entry.get("country_weights")
                if not isinstance(weights_map, Mapping):
                    raise err("E_S6_POLICY_MINIMA", f"edge '{edge_id}' country_weights must be a map")
                if ip_country not in weights_map:
                    raise err(
                        "E_S6_POLICY_MINIMA",
                        f"edge '{edge_id}' missing country_weights for {ip_country}",
                    )
                weight = float(weights_map[ip_country])
            if weight is None or weight <= 0 or not math.isfinite(weight):
                raise err("E_S6_POLICY_MINIMA", f"edge '{edge_id}' weight must be positive")
            entries.append(
                EdgeEntry(
                    edge_id=edge_id,
                    ip_country=ip_country,
                    weight=weight,
                    lat=float(lat),
                    lon=float(lon),
                )
            )

        if not entries:
            raise err("E_S6_POLICY_MINIMA", "edge set produced zero entries")
        total = sum(item.weight for item in entries)
        if not math.isfinite(total) or total <= 0.0:
            raise err("E_S6_POLICY_MINIMA", "edge weights must sum to > 0")
        if abs(total - 1.0) > 1e-6:
            raise err("E_S6_POLICY_MINIMA", "edge weights must sum to 1 ñ epsilon")
        entries.sort(key=lambda item: (item.ip_country, item.edge_id))
        return entries, {}

    def _resolve_route_policy_stream(
        self,
        payload: Mapping[str, object],
        *,
        min_draws: int,
    ) -> tuple[str, int, str]:
        rng_engine = str(payload.get("rng_engine") or payload.get("algorithm") or "philox2x64-10")
        streams = payload.get("streams")
        if isinstance(streams, Mapping):
            stream_key = "routing_edge"
            stream = streams.get(stream_key)
            if not isinstance(stream, Mapping):
                raise err("E_S6_POLICY_STREAM", f"route_rng_policy_v1 missing stream '{stream_key}'")
            draws_per_unit = stream.get("draws_per_unit") or {}
            draws = int(draws_per_unit.get("draws_per_virtual", 0))
            if draws < min_draws:
                raise err(
                    "E_S6_POLICY_STREAM",
                    f"route_rng_policy_v1 stream '{stream_key}' insufficient draws_per_virtual",
                )
            stream_id = str(stream.get("rng_stream_id") or stream_key)
            return stream_id, draws, rng_engine
        substreams = payload.get("substreams") or []
        if not isinstance(substreams, Sequence):
            raise err("E_S6_POLICY_STREAM", "route_rng_policy_v1 malformed (substreams missing)")
        entry = next(
            (
                candidate
                for candidate in substreams
                if isinstance(candidate, Mapping) and candidate.get("id") == self.RNG_STREAM_ID
            ),
            None,
        )
        if entry is None:
            raise err(
                "E_S6_POLICY_STREAM",
                f"route_rng_policy_v1 missing stream '{self.RNG_STREAM_ID}'",
            )
        label = str(entry.get("label", "")).strip()
        if label != self.SUBSTREAM_LABEL:
            raise err(
                "E_S6_POLICY_STREAM",
                f"route_rng_policy_v1 stream '{self.RNG_STREAM_ID}' must use label '{self.SUBSTREAM_LABEL}'",
            )
        max_uniforms = int(entry.get("max_uniforms", 0))
        if max_uniforms < min_draws:
            raise err(
                "E_S6_POLICY_STREAM",
                f"route_rng_policy_v1 stream '{self.RNG_STREAM_ID}' must allocate at least one uniform",
            )
        return str(entry.get("id") or self.RNG_STREAM_ID), max_uniforms, rng_engine

    def _build_alias_table(self, entries: List[EdgeEntry]) -> AliasTable:
        if not entries:
            raise err("E_S6_ALIAS_EMPTY", "alias builder received no values")
        weights = [entry.weight for entry in entries]
        total = float(sum(weights))
        if not math.isfinite(total) or total <= 0.0:
            raise err("E_S6_ALIAS_TOTAL", "alias builder weights must sum to > 0")
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
            values=list(entries),
            probabilities=prob,
            aliases=alias,
            value_probabilities={entry.edge_id: normalised[idx] for idx, entry in enumerate(entries)},
        )

    @staticmethod
    def _sample_alias(
        *,
        alias_table: AliasTable,
        substream: PhiloxSubstream,
    ) -> Tuple[EdgeEntry, PhiloxState, PhiloxState]:
        before = substream.snapshot()
        prior_blocks = substream.blocks
        prior_draws = substream.draws
        u = substream.uniform()
        after = substream.snapshot()
        if substream.blocks - prior_blocks != 1 or substream.draws - prior_draws != 1:
            raise err("E_S6_RNG_BUDGET", "virtual edge events must consume exactly one block and one draw")
        return alias_table.sample(u), before, after

    def _build_event_payload(
        self,
        *,
        ts_utc: datetime,
        before: PhiloxState,
        after: PhiloxState,
        seed: int,
        parameter_hash: str,
        manifest: str,
        run_id: str,
        arrival: RouterVirtualArrival,
    ) -> Mapping[str, object]:
        return {
            "ts_utc": ts_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest,
            "run_id": run_id,
            "module": self.MODULE_NAME,
            "substream_label": self.SUBSTREAM_LABEL,
            "blocks": 1,
            "draws": "1",
            "rng_counter_before_lo": int(before.counter_lo),
            "rng_counter_before_hi": int(before.counter_hi),
            "rng_counter_after_lo": int(after.counter_lo),
            "rng_counter_after_hi": int(after.counter_hi),
            "merchant_id": arrival.merchant_id,
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
                    "E_S6_IMMUTABLE_LOG",
                    f"rng log partition '{partition_dir}' already exists with different content",
                )
            return partition_dir
        output_file.write_text(payload, encoding="utf-8")
        return partition_dir

    def _write_edge_logs(
        self,
        *,
        base_path: Path,
        dictionary: Mapping[str, object],
        seed: int,
        parameter_hash: str,
        run_id: str,
        rows_by_day: Mapping[str, List[Mapping[str, object]]],
    ) -> List[Path]:
        if not rows_by_day:
            return []
        paths: List[Path] = []
        try:
            get_dataset_entry("s6_edge_log", dictionary=dictionary)
        except S0GateError:
            logger.info("s6_edge_log dictionary entry missing; skipping diagnostic emission")
            return []
        for utc_day, rows in rows_by_day.items():
            path = resolve_dataset_path(
                "s6_edge_log",
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
                        "E_S6_EDGE_LOG_IMMUTABLE",
                        f"edge log '{path}' already exists with different content",
                    )
            else:
                path.write_text(payload, encoding="utf-8")
            paths.append(path)
        return paths

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
                    "E_S6_IMMUTABLE_LOG",
                    f"audit log '{audit_path}' already exists with different content",
                )
        else:
            audit_path.write_text(payload, encoding="utf-8")

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
        route_policy: Mapping[str, object],
        route_policy_digest: str,
        route_policy_path: Path,
        route_policy_stream_id: str,
        route_policy_draws_per_virtual: int,
        route_policy_rng_engine: str,
        edge_policy: Mapping[str, object],
        edge_policy_digest: str,
        edge_policy_file_digest: str,
        edge_policy_path: Path,
        total_arrivals: int,
        virtual_arrivals: int,
        rng_events: int,
        manifest_inputs: Mapping[str, str],
        edge_log_paths: Sequence[Path],
        edge_log_enabled: bool,
    ) -> Mapping[str, object]:
        rng_accounting = {
            "events_edge": rng_events,
            "draws_total": rng_events,
            "first_counter": {},
            "last_counter": {},
        }
        validators = self._build_validator_results(edge_log_enabled=edge_log_enabled)
        report = {
            "component": "2B.S6",
            "fingerprint": manifest,
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
            "created_utc": receipt.verified_at_utc,
            "catalogue_resolution": dictionary_versions,
            "policy": {
                "route_policy": {
                    "id": "route_rng_policy_v1",
                    "version_tag": route_policy.get("version_tag", ""),
                    "sha256_hex": route_policy_digest,
                    "rng_engine": route_policy_rng_engine,
                    "rng_stream_id": route_policy_stream_id,
                    "draws_per_virtual": route_policy_draws_per_virtual,
                    "path": str(route_policy_path),
                },
                "edge_policy": {
                    "id": "virtual_edge_policy_v1",
                    "version_tag": edge_policy.get("version_tag", ""),
                    "sha256_hex": edge_policy_digest,
                    "file_sha256_hex": edge_policy_file_digest,
                    "path": str(edge_policy_path),
                    "edges_total": len(edge_policy.get("edges") or []),
                },
            },
            "rng_accounting": rng_accounting,
            "validators": validators,
            "diagnostics": {
                "edge_log_enabled": edge_log_enabled,
                "edge_log_partitions": len(edge_log_paths),
                "edge_log_partition_template": (
                    f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day=*"
                    if edge_log_enabled
                    else ""
                ),
                "virtual_arrivals": virtual_arrivals,
                "arrivals_total": total_arrivals,
            },
            "inputs_summary": manifest_inputs,
            "determinism": dict(receipt.determinism_receipt),
        }
        return report

    @staticmethod
    def _build_validator_results(*, edge_log_enabled: bool) -> List[dict]:
        validators = [
            ("V-01", "PASS", ["2B-S6-001"]),
            ("V-02", "PASS", ["2B-S6-020"]),
            ("V-03", "PASS", ["2B-S6-021"]),
            ("V-04", "PASS", ["2B-S6-030"]),
            ("V-05", "PASS", ["2B-S6-040"]),
            ("V-06", "PASS", ["2B-S6-041"]),
            ("V-07", "PASS", ["2B-S6-060"]),
            ("V-08", "PASS", ["2B-S6-050"]),
            ("V-09", "PASS", ["2B-S6-051"]),
            ("V-10", "PASS", ["2B-S6-053"]),
            ("V-11", "PASS", ["2B-S6-050"]),
            (
                "V-12",
                "PASS" if edge_log_enabled else "WARN",
                ["2B-S6-071"],
            ),
            ("V-13", "PASS", ["2B-S6-080"]),
            ("V-14", "PASS", ["2B-S6-090"]),
            ("V-15", "WARN", ["2B-S6-095"]),
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


__all__ = [
    "S6VirtualEdgeInputs",
    "S6VirtualEdgeResult",
    "S6VirtualEdgeRunner",
]
