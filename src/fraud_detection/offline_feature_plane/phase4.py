"""OFS Phase 4 replay-basis resolver + completeness receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlparse

from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .contracts import OfsBuildIntent, ReplayBasisSlice
from .run_ledger import deterministic_run_key


@dataclass(frozen=True)
class OfsPhase4ReplayError(ValueError):
    """Raised when Phase 4 replay/completeness checks fail."""

    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code or "").strip() or "UNKNOWN")
        object.__setattr__(self, "message", str(self.message or "").strip() or self.code)
        ValueError.__init__(self, f"{self.code}:{self.message}")


@dataclass(frozen=True)
class ReplayTupleObservation:
    topic: str
    partition: int
    offset_kind: str
    offset: str
    payload_hash: str
    source: str
    archive_ref: str | None = None

    @property
    def source_upper(self) -> str:
        return str(self.source or "").strip().upper()

    @property
    def offset_int(self) -> int:
        try:
            return int(str(self.offset or "").strip())
        except Exception as exc:  # noqa: BLE001
            raise OfsPhase4ReplayError(
                "BASIS_UNRESOLVED",
                f"offset must be integer-like for tuple {self.topic}/{self.partition}/{self.offset_kind}:{self.offset}",
            ) from exc

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "topic": self.topic,
            "partition": int(self.partition),
            "offset_kind": self.offset_kind,
            "offset": self.offset,
            "payload_hash": self.payload_hash,
            "source": self.source_upper,
        }
        if self.archive_ref:
            payload["archive_ref"] = self.archive_ref
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ReplayTupleObservation":
        item = _mapping(payload, field_name="observation", code="BASIS_UNRESOLVED")
        topic = _required_text(item.get("topic"), code="BASIS_UNRESOLVED", field_name="observation.topic")
        partition = _required_non_negative_int(
            item.get("partition"),
            code="BASIS_UNRESOLVED",
            field_name="observation.partition",
        )
        offset_kind = _required_text(
            item.get("offset_kind"),
            code="BASIS_UNRESOLVED",
            field_name="observation.offset_kind",
        )
        offset = _required_text(item.get("offset"), code="BASIS_UNRESOLVED", field_name="observation.offset")
        payload_hash = _required_text(
            item.get("payload_hash"),
            code="BASIS_UNRESOLVED",
            field_name="observation.payload_hash",
        )
        source = _required_text(item.get("source"), code="BASIS_UNRESOLVED", field_name="observation.source").upper()
        if source not in {"EB", "ARCHIVE"}:
            raise OfsPhase4ReplayError("BASIS_UNRESOLVED", f"observation.source must be EB or ARCHIVE: {source}")
        archive_ref = _text_or_none(item.get("archive_ref"))
        return cls(
            topic=topic,
            partition=partition,
            offset_kind=offset_kind,
            offset=offset,
            payload_hash=payload_hash,
            source=source,
            archive_ref=archive_ref,
        )


@dataclass(frozen=True)
class ReplayBasisEvidence:
    observations: tuple[ReplayTupleObservation, ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ReplayBasisEvidence":
        body = _mapping(payload, field_name="replay_basis_evidence", code="BASIS_UNRESOLVED")
        raw = body.get("observations")
        if not isinstance(raw, list):
            raise OfsPhase4ReplayError("BASIS_UNRESOLVED", "observations must be a list")
        rows: list[ReplayTupleObservation] = []
        for item in raw:
            rows.append(ReplayTupleObservation.from_payload(_mapping(item, field_name="observations[]", code="BASIS_UNRESOLVED")))
        return cls(observations=tuple(rows))

    def as_dict(self) -> dict[str, Any]:
        return {"observations": [item.as_dict() for item in self.observations]}


@dataclass(frozen=True)
class ReplayResolvedTuple:
    topic: str
    partition: int
    offset_kind: str
    start_offset: str
    end_offset: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "partition": int(self.partition),
            "offset_kind": self.offset_kind,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "source": self.source,
        }


@dataclass(frozen=True)
class ReplayCutover:
    topic: str
    partition: int
    offset_kind: str
    requested_start_offset: str
    requested_end_offset: str
    cutover_mode: str
    cutover_offset: str | None
    archive_authoritative_from_offset: str | None
    eb_coverage_ranges: tuple[dict[str, str], ...]
    archive_coverage_ranges: tuple[dict[str, str], ...]
    selected_ranges: tuple[dict[str, str], ...]
    missing_ranges: tuple[dict[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "topic": self.topic,
            "partition": int(self.partition),
            "offset_kind": self.offset_kind,
            "requested_start_offset": self.requested_start_offset,
            "requested_end_offset": self.requested_end_offset,
            "cutover_mode": self.cutover_mode,
            "eb_coverage_ranges": [dict(item) for item in self.eb_coverage_ranges],
            "archive_coverage_ranges": [dict(item) for item in self.archive_coverage_ranges],
            "selected_ranges": [dict(item) for item in self.selected_ranges],
            "missing_ranges": [dict(item) for item in self.missing_ranges],
        }
        if self.cutover_offset is not None:
            payload["cutover_offset"] = self.cutover_offset
        if self.archive_authoritative_from_offset is not None:
            payload["archive_authoritative_from_offset"] = self.archive_authoritative_from_offset
        return payload


@dataclass(frozen=True)
class ReplayAnomaly:
    code: str
    message: str
    topic: str
    partition: int
    offset_kind: str
    start_offset: str
    end_offset: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "topic": self.topic,
            "partition": int(self.partition),
            "offset_kind": self.offset_kind,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ReplayCompletenessReceipt:
    run_key: str
    request_id: str
    platform_run_id: str
    status: str
    generated_at_utc: str
    replay_resolved_tuples: tuple[ReplayResolvedTuple, ...]
    cutovers: tuple[ReplayCutover, ...]
    anomalies: tuple[ReplayAnomaly, ...]
    totals: dict[str, int]
    evidence_digest: str

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/ofs/replay_completeness/{self.run_key}.json"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "learning.ofs_replay_completeness_receipt.v0",
            "run_key": self.run_key,
            "request_id": self.request_id,
            "platform_run_id": self.platform_run_id,
            "status": self.status,
            "generated_at_utc": self.generated_at_utc,
            "totals": dict(self.totals),
            "evidence_digest": self.evidence_digest,
            "replay_resolved_tuples": [item.as_dict() for item in self.replay_resolved_tuples],
            "cutovers": [item.as_dict() for item in self.cutovers],
            "anomalies": [item.as_dict() for item in self.anomalies],
        }


@dataclass(frozen=True)
class OfsReplayBasisResolverConfig:
    object_store_root: str = "runs"
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = None
    eb_observations_ref: str | None = None
    archive_observations_ref: str | None = None
    discover_archive_events: bool = True
    require_complete_for_dataset_build: bool = True


class OfsReplayBasisResolver:
    """Resolves replay basis and emits completeness receipts for OFS Phase 4."""

    def __init__(self, *, config: OfsReplayBasisResolverConfig | None = None) -> None:
        self.config = config or OfsReplayBasisResolverConfig()
        self._store = _build_store(self.config)

    def resolve(
        self,
        *,
        intent: OfsBuildIntent,
        run_key: str | None = None,
        evidence: ReplayBasisEvidence | None = None,
    ) -> ReplayCompletenessReceipt:
        resolved_run_key = str(run_key or deterministic_run_key(intent.request_id))
        source_evidence = evidence or self._load_evidence(intent=intent)
        anomalies: list[ReplayAnomaly] = []
        resolved_tuples: list[ReplayResolvedTuple] = []
        cutovers: list[ReplayCutover] = []
        required_offsets = 0
        covered_offsets = 0
        mismatch_count = 0
        for basis in intent.replay_basis:
            result = _resolve_slice(
                basis=basis,
                observations=source_evidence.observations,
            )
            anomalies.extend(result["anomalies"])
            resolved_tuples.extend(result["resolved_tuples"])
            cutovers.append(result["cutover"])
            required_offsets += int(result["required_offsets"])
            covered_offsets += int(result["covered_offsets"])
            mismatch_count += int(result["mismatch_count"])

        training_intent = _is_training_intent(intent=intent)
        if mismatch_count > 0 and training_intent:
            raise OfsPhase4ReplayError(
                "REPLAY_BASIS_MISMATCH",
                f"payload-hash mismatches detected across EB/Archive ({mismatch_count}) for training-intent build",
            )

        status = "COMPLETE" if required_offsets == covered_offsets and mismatch_count == 0 else "INCOMPLETE"
        receipt = ReplayCompletenessReceipt(
            run_key=resolved_run_key,
            request_id=intent.request_id,
            platform_run_id=intent.platform_run_id,
            status=status,
            generated_at_utc=_utc_now(),
            replay_resolved_tuples=tuple(_merge_resolved_tuples(resolved_tuples)),
            cutovers=tuple(cutovers),
            anomalies=tuple(anomalies),
            totals={
                "required_offsets": int(required_offsets),
                "covered_offsets": int(covered_offsets),
                "missing_offsets": int(max(required_offsets - covered_offsets, 0)),
                "mismatch_count": int(mismatch_count),
            },
            evidence_digest=_sha256_payload(source_evidence.as_dict()),
        )
        if training_intent and self.config.require_complete_for_dataset_build:
            self.require_complete_for_publication(receipt=receipt)
        return receipt

    def emit_immutable(self, *, receipt: ReplayCompletenessReceipt) -> str:
        relative_path = receipt.artifact_relative_path()
        payload = receipt.as_dict()
        try:
            ref = self._store.write_json_if_absent(relative_path, payload)
            return str(ref.path)
        except FileExistsError:
            existing = self._store.read_json(relative_path)
            if _normalize_mapping(existing) != _normalize_mapping(payload):
                raise OfsPhase4ReplayError(
                    "COMPLETENESS_RECEIPT_IMMUTABILITY_VIOLATION",
                    f"completeness receipt drift detected at {relative_path}",
                )
            return _artifact_ref(self.config, relative_path)

    def require_complete_for_publication(self, *, receipt: ReplayCompletenessReceipt) -> None:
        if str(receipt.status).strip().upper() != "COMPLETE":
            raise OfsPhase4ReplayError(
                "REPLAY_INCOMPLETE",
                f"publication blocked: replay completeness status={receipt.status}",
            )

    def _load_evidence(self, *, intent: OfsBuildIntent) -> ReplayBasisEvidence:
        observations: list[ReplayTupleObservation] = []
        if self.config.eb_observations_ref:
            observations.extend(_load_observations_from_ref(ref=self.config.eb_observations_ref, source_hint="EB", resolver=self))
        if self.config.archive_observations_ref:
            observations.extend(
                _load_observations_from_ref(ref=self.config.archive_observations_ref, source_hint="ARCHIVE", resolver=self)
            )
        elif self.config.discover_archive_events:
            observations.extend(self._discover_archive_observations(intent=intent))
        return ReplayBasisEvidence(observations=tuple(observations))

    def _discover_archive_observations(self, *, intent: OfsBuildIntent) -> list[ReplayTupleObservation]:
        rows: list[ReplayTupleObservation] = []
        for slice_item in intent.replay_basis:
            prefix = _archive_prefix(
                platform_run_id=intent.platform_run_id,
                topic=slice_item.topic,
                partition=slice_item.partition,
                offset_kind=slice_item.offset_kind,
            )
            refs = self._store.list_files(prefix)
            for ref in refs:
                try:
                    payload = _read_json_ref(ref=ref, store=self._store, config=self.config)
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(payload, Mapping):
                    continue
                origin = payload.get("origin_offset")
                if not isinstance(origin, Mapping):
                    continue
                topic = _text_or_empty(origin.get("topic"))
                partition_raw = origin.get("partition")
                offset_kind = _text_or_empty(origin.get("offset_kind"))
                offset = _text_or_empty(origin.get("offset"))
                payload_hash = _text_or_empty(payload.get("payload_hash"))
                if not (topic and offset_kind and offset and payload_hash):
                    continue
                try:
                    partition = int(partition_raw)
                except Exception:  # noqa: BLE001
                    continue
                rows.append(
                    ReplayTupleObservation(
                        topic=topic,
                        partition=partition,
                        offset_kind=offset_kind,
                        offset=offset,
                        payload_hash=payload_hash,
                        source="ARCHIVE",
                        archive_ref=str(ref),
                    )
                )
        return rows

def _resolve_slice(
    *,
    basis: ReplayBasisSlice,
    observations: tuple[ReplayTupleObservation, ...],
) -> dict[str, Any]:
    start = _parse_offset_int(basis.start_offset, field_name="replay_basis[].start_offset")
    end = _parse_offset_int(basis.end_offset, field_name="replay_basis[].end_offset")
    if end < start:
        raise OfsPhase4ReplayError(
            "BASIS_UNRESOLVED",
            f"replay basis end_offset must be >= start_offset for {basis.topic}/{basis.partition}",
        )
    requested = (start, end)
    relevant = [
        row
        for row in observations
        if row.topic == basis.topic
        and int(row.partition) == int(basis.partition)
        and row.offset_kind == basis.offset_kind
        and start <= row.offset_int <= end
    ]
    eb_map: dict[int, ReplayTupleObservation] = {}
    archive_map: dict[int, ReplayTupleObservation] = {}
    anomalies: list[ReplayAnomaly] = []
    mismatch_count = 0
    for row in relevant:
        target = eb_map if row.source_upper == "EB" else archive_map
        offset = row.offset_int
        existing = target.get(offset)
        if existing is None:
            target[offset] = row
            continue
        if existing.payload_hash == row.payload_hash:
            continue
        mismatch_count += 1
        anomalies.append(
            ReplayAnomaly(
                code="REPLAY_DUPLICATE_OFFSET_MISMATCH",
                message="conflicting payload hashes for duplicate source observation",
                topic=basis.topic,
                partition=basis.partition,
                offset_kind=basis.offset_kind,
                start_offset=str(offset),
                end_offset=str(offset),
                details={
                    "source": row.source_upper,
                    "first_payload_hash": existing.payload_hash,
                    "second_payload_hash": row.payload_hash,
                },
            )
        )

    for offset in sorted(set(eb_map).intersection(archive_map)):
        eb_hash = eb_map[offset].payload_hash
        archive_hash = archive_map[offset].payload_hash
        if eb_hash == archive_hash:
            continue
        mismatch_count += 1
        anomalies.append(
            ReplayAnomaly(
                code="REPLAY_BASIS_MISMATCH",
                message="EB and Archive payload hashes differ for same offset tuple",
                topic=basis.topic,
                partition=basis.partition,
                offset_kind=basis.offset_kind,
                start_offset=str(offset),
                end_offset=str(offset),
                details={
                    "eb_payload_hash": eb_hash,
                    "archive_payload_hash": archive_hash,
                    "archive_ref": archive_map[offset].archive_ref,
                },
            )
        )

    eb_intervals = _intervals_from_offsets(sorted(eb_map))
    archive_intervals = _intervals_from_offsets(sorted(archive_map))
    cutover_offset = max(eb_map) if eb_map else None
    selected: list[tuple[int, int, str]] = []
    missing: list[tuple[int, int]] = []
    cutover_mode = "ARCHIVE_ONLY"
    archive_authoritative_from = None
    if cutover_offset is None:
        archive_selected = _intersect_intervals(archive_intervals, requested)
        selected.extend([(a, b, "ARCHIVE") for a, b in archive_selected])
        missing.extend(_subtract_interval(requested, archive_selected))
    else:
        low = (start, min(end, cutover_offset))
        high = (max(start, cutover_offset + 1), end)
        eb_low = _intersect_intervals(eb_intervals, low) if low[0] <= low[1] else []
        low_fill: list[tuple[int, int]] = []
        low_gaps = _subtract_interval(low, eb_low) if low[0] <= low[1] else []
        for gap in low_gaps:
            low_fill.extend(_intersect_intervals(archive_intervals, gap))
        low_missing = []
        for gap in low_gaps:
            covered_gap = _intersect_intervals(_merge_intervals(low_fill), gap)
            low_missing.extend(_subtract_interval(gap, covered_gap))
        if high[0] <= high[1]:
            archive_authoritative_from = str(high[0])
            high_archive = _intersect_intervals(archive_intervals, high)
            high_missing = _subtract_interval(high, high_archive)
        else:
            high_archive = []
            high_missing = []

        selected.extend([(a, b, "EB") for a, b in eb_low])
        selected.extend([(a, b, "ARCHIVE") for a, b in low_fill])
        selected.extend([(a, b, "ARCHIVE") for a, b in high_archive])
        missing.extend(low_missing)
        missing.extend(high_missing)
        if high[0] <= high[1]:
            cutover_mode = "EB_THEN_ARCHIVE"
        elif low_fill:
            cutover_mode = "EB_WITH_ARCHIVE_BACKFILL"
        else:
            cutover_mode = "EB_ONLY"

    for gap in missing:
        anomalies.append(
            ReplayAnomaly(
                code="REPLAY_BASIS_GAP",
                message="requested replay basis has uncovered offsets",
                topic=basis.topic,
                partition=basis.partition,
                offset_kind=basis.offset_kind,
                start_offset=str(gap[0]),
                end_offset=str(gap[1]),
                details={},
            )
        )

    merged_selected = _merge_source_intervals(selected)
    covered_merged = _merge_intervals([(a, b) for a, b, _ in merged_selected])
    covered_count = _interval_length_sum(covered_merged)
    required_count = end - start + 1
    resolved_tuples = [
        ReplayResolvedTuple(
            topic=basis.topic,
            partition=basis.partition,
            offset_kind=basis.offset_kind,
            start_offset=str(a),
            end_offset=str(b),
            source=source,
        )
        for a, b, source in merged_selected
    ]
    cutover = ReplayCutover(
        topic=basis.topic,
        partition=basis.partition,
        offset_kind=basis.offset_kind,
        requested_start_offset=basis.start_offset,
        requested_end_offset=basis.end_offset,
        cutover_mode=cutover_mode,
        cutover_offset=str(cutover_offset) if cutover_offset is not None else None,
        archive_authoritative_from_offset=archive_authoritative_from,
        eb_coverage_ranges=tuple(_intervals_to_ranges(eb_intervals)),
        archive_coverage_ranges=tuple(_intervals_to_ranges(archive_intervals)),
        selected_ranges=tuple(_source_intervals_to_ranges(merged_selected)),
        missing_ranges=tuple(_intervals_to_ranges(_merge_intervals(missing))),
    )
    return {
        "resolved_tuples": resolved_tuples,
        "cutover": cutover,
        "anomalies": anomalies,
        "required_offsets": required_count,
        "covered_offsets": covered_count,
        "mismatch_count": mismatch_count,
    }


def _load_observations_from_ref(
    *,
    ref: str,
    source_hint: str,
    resolver: OfsReplayBasisResolver,
) -> list[ReplayTupleObservation]:
    payload = _read_json_ref(ref=ref, store=resolver._store, config=resolver.config)  # noqa: SLF001
    rows: list[ReplayTupleObservation] = []
    if isinstance(payload, Mapping) and isinstance(payload.get("observations"), list):
        raw = payload.get("observations")
    elif isinstance(payload, list):
        raw = payload
    else:
        raise OfsPhase4ReplayError("BASIS_UNRESOLVED", f"observation ref {ref} must be list or {{observations:[...]}}")
    for item in raw:
        row_payload = _mapping(item, field_name="observations[]", code="BASIS_UNRESOLVED")
        if "source" not in row_payload:
            row_payload = dict(row_payload)
            row_payload["source"] = source_hint
        rows.append(ReplayTupleObservation.from_payload(row_payload))
    return rows


def _is_training_intent(*, intent: OfsBuildIntent) -> bool:
    return intent.intent_kind == "dataset_build" and not bool(intent.non_training_allowed)


def _merge_resolved_tuples(rows: list[ReplayResolvedTuple]) -> list[ReplayResolvedTuple]:
    grouped: dict[tuple[str, int, str], list[tuple[int, int, str]]] = {}
    for row in rows:
        key = (row.topic, int(row.partition), row.offset_kind)
        grouped.setdefault(key, []).append(
            (
                _parse_offset_int(row.start_offset, field_name="resolved_tuple.start_offset"),
                _parse_offset_int(row.end_offset, field_name="resolved_tuple.end_offset"),
                row.source,
            )
        )
    merged_rows: list[ReplayResolvedTuple] = []
    for key, intervals in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
        merged = _merge_source_intervals(intervals)
        for start, end, source in merged:
            merged_rows.append(
                ReplayResolvedTuple(
                    topic=key[0],
                    partition=key[1],
                    offset_kind=key[2],
                    start_offset=str(start),
                    end_offset=str(end),
                    source=source,
                )
            )
    return merged_rows


def _intervals_from_offsets(offsets: list[int]) -> list[tuple[int, int]]:
    if not offsets:
        return []
    unique = sorted(set(offsets))
    start = unique[0]
    prev = unique[0]
    rows: list[tuple[int, int]] = []
    for value in unique[1:]:
        if value == prev + 1:
            prev = value
            continue
        rows.append((start, prev))
        start = value
        prev = value
    rows.append((start, prev))
    return rows


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged: list[tuple[int, int]] = []
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end + 1:
            current_end = max(current_end, end)
            continue
        merged.append((current_start, current_end))
        current_start, current_end = start, end
    merged.append((current_start, current_end))
    return merged


def _intersect_intervals(intervals: list[tuple[int, int]], target: tuple[int, int]) -> list[tuple[int, int]]:
    if not intervals or target[0] > target[1]:
        return []
    out: list[tuple[int, int]] = []
    for start, end in intervals:
        left = max(start, target[0])
        right = min(end, target[1])
        if left <= right:
            out.append((left, right))
    return _merge_intervals(out)


def _subtract_interval(target: tuple[int, int], covers: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if target[0] > target[1]:
        return []
    merged_covers = _intersect_intervals(_merge_intervals(covers), target)
    if not merged_covers:
        return [target]
    out: list[tuple[int, int]] = []
    cursor = target[0]
    for start, end in merged_covers:
        if cursor < start:
            out.append((cursor, start - 1))
        cursor = max(cursor, end + 1)
    if cursor <= target[1]:
        out.append((cursor, target[1]))
    return out


def _merge_source_intervals(intervals: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda row: (row[0], row[1], row[2]))
    merged: list[tuple[int, int, str]] = []
    current_start, current_end, current_source = ordered[0]
    for start, end, source in ordered[1:]:
        if source == current_source and start <= current_end + 1:
            current_end = max(current_end, end)
            continue
        merged.append((current_start, current_end, current_source))
        current_start, current_end, current_source = start, end, source
    merged.append((current_start, current_end, current_source))
    return merged


def _interval_length_sum(intervals: list[tuple[int, int]]) -> int:
    total = 0
    for start, end in intervals:
        total += end - start + 1
    return total


def _intervals_to_ranges(intervals: list[tuple[int, int]]) -> list[dict[str, str]]:
    return [{"start_offset": str(start), "end_offset": str(end)} for start, end in _merge_intervals(intervals)]


def _source_intervals_to_ranges(intervals: list[tuple[int, int, str]]) -> list[dict[str, str]]:
    return [
        {"start_offset": str(start), "end_offset": str(end), "source": source}
        for start, end, source in _merge_source_intervals(intervals)
    ]


def _archive_prefix(*, platform_run_id: str, topic: str, partition: int, offset_kind: str) -> str:
    return (
        f"{platform_run_id}/archive/events/"
        f"topic={_sanitize_token(topic)}/partition={int(partition)}/offset_kind={_sanitize_token(offset_kind)}"
    )


_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9_.:-]+")


def _sanitize_token(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "_"
    return _SAFE_TOKEN.sub("_", text)


def _parse_offset_int(value: Any, *, field_name: str) -> int:
    text = str(value or "").strip()
    if not text:
        raise OfsPhase4ReplayError("BASIS_UNRESOLVED", f"{field_name} is required")
    try:
        return int(text)
    except Exception as exc:  # noqa: BLE001
        raise OfsPhase4ReplayError("BASIS_UNRESOLVED", f"{field_name} must be integer-like: {text}") from exc


def _build_store(config: OfsReplayBasisResolverConfig) -> ObjectStore:
    root = str(config.object_store_root or "").strip()
    if not root:
        raise ValueError("object_store_root is required")
    if root.startswith("s3://"):
        parsed = urlparse(root)
        return S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=config.object_store_endpoint,
            region_name=config.object_store_region,
            path_style=config.object_store_path_style,
        )
    return LocalObjectStore(Path(root))


def _artifact_ref(config: OfsReplayBasisResolverConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


def _read_json_ref(*, ref: str, store: ObjectStore, config: OfsReplayBasisResolverConfig) -> dict[str, Any]:
    text = str(ref or "").strip()
    if not text:
        raise OfsPhase4ReplayError("BASIS_UNRESOLVED", "artifact ref is required")
    if text.startswith("s3://"):
        parsed = urlparse(text)
        s3_store = S3ObjectStore(
            parsed.netloc,
            prefix="",
            endpoint_url=config.object_store_endpoint,
            region_name=config.object_store_region,
            path_style=config.object_store_path_style,
        )
        return s3_store.read_json(parsed.path.lstrip("/"))
    path = Path(text)
    if path.is_absolute():
        return json.loads(path.read_text(encoding="utf-8"))
    return store.read_json(text)


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_normalize_mapping(payload), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return _normalize_generic(dict(value))


def _normalize_generic(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_generic(val) for key, val in sorted(value.items(), key=lambda row: str(row[0]))}
    if isinstance(value, list):
        return [_normalize_generic(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _mapping(value: Any, *, field_name: str, code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OfsPhase4ReplayError(code, f"{field_name} must be a mapping")
    return dict(value)


def _required_text(value: Any, *, code: str, field_name: str) -> str:
    text = _text_or_empty(value)
    if not text:
        raise OfsPhase4ReplayError(code, f"{field_name} is required")
    return text


def _required_non_negative_int(value: Any, *, code: str, field_name: str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:  # noqa: BLE001
        raise OfsPhase4ReplayError(code, f"{field_name} must be an integer") from exc
    if parsed < 0:
        raise OfsPhase4ReplayError(code, f"{field_name} must be >= 0")
    return parsed


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _text_or_none(value: Any) -> str | None:
    text = _text_or_empty(value)
    return text or None


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
