"""OFS Phase 6 deterministic feature reconstruction and dataset drafting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .contracts import OfsBuildIntent
from .phase3 import ResolvedFeatureProfile
from .run_ledger import deterministic_run_key


@dataclass(frozen=True)
class OfsPhase6FeatureError(ValueError):
    """Raised when OFS Phase 6 checks fail."""

    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code or "").strip() or "UNKNOWN")
        object.__setattr__(self, "message", str(self.message or "").strip() or self.code)
        ValueError.__init__(self, f"{self.code}:{self.message}")


@dataclass(frozen=True)
class ReplayFeatureInputEvent:
    topic: str
    partition: int
    offset_kind: str
    offset: str
    event_id: str
    ts_utc: str
    payload_hash: str
    payload: dict[str, Any]

    @property
    def offset_int(self) -> int:
        try:
            return int(str(self.offset).strip())
        except Exception as exc:  # noqa: BLE001
            raise OfsPhase6FeatureError(
                "REPLAY_EVENT_INVALID",
                f"offset must be integer-like for event_id={self.event_id!r}",
            ) from exc

    @property
    def ts_dt_utc(self) -> datetime:
        return _parse_utc(self.ts_utc, field_name="replay_events[].ts_utc")

    def tuple_key(self) -> tuple[str, int, str, str, str]:
        return (self.topic, int(self.partition), self.offset_kind, self.offset, self.event_id)

    def event_tie_break_key(self) -> tuple[str, int, str, int, str]:
        return (self.topic, int(self.partition), self.offset_kind, self.offset_int, self.payload_hash)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ReplayFeatureInputEvent":
        row = _mapping(payload, field_name="replay_events[]", code="REPLAY_EVENT_INVALID")
        return cls(
            topic=_required_text(row.get("topic"), code="REPLAY_EVENT_INVALID", field_name="replay_events[].topic"),
            partition=_required_non_negative_int(
                row.get("partition"),
                code="REPLAY_EVENT_INVALID",
                field_name="replay_events[].partition",
            ),
            offset_kind=_required_text(
                row.get("offset_kind"),
                code="REPLAY_EVENT_INVALID",
                field_name="replay_events[].offset_kind",
            ),
            offset=_required_text(row.get("offset"), code="REPLAY_EVENT_INVALID", field_name="replay_events[].offset"),
            event_id=_required_text(
                row.get("event_id"),
                code="REPLAY_EVENT_INVALID",
                field_name="replay_events[].event_id",
            ),
            ts_utc=_required_text(
                row.get("ts_utc"),
                code="REPLAY_EVENT_INVALID",
                field_name="replay_events[].ts_utc",
            ),
            payload_hash=_required_text(
                row.get("payload_hash"),
                code="REPLAY_EVENT_INVALID",
                field_name="replay_events[].payload_hash",
            ),
            payload=_mapping_or_empty(row.get("payload")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "partition": int(self.partition),
            "offset_kind": self.offset_kind,
            "offset": self.offset,
            "event_id": self.event_id,
            "ts_utc": self.ts_utc,
            "payload_hash": self.payload_hash,
            "payload": _normalize_mapping(self.payload),
        }


@dataclass(frozen=True)
class OfsFeatureDraftRow:
    row_id: str
    platform_run_id: str
    event_id: str
    ts_utc: str
    topic: str
    partition: int
    offset_kind: str
    offset: str
    payload_hash: str
    feature_values: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "platform_run_id": self.platform_run_id,
            "event_id": self.event_id,
            "ts_utc": self.ts_utc,
            "topic": self.topic,
            "partition": int(self.partition),
            "offset_kind": self.offset_kind,
            "offset": self.offset,
            "payload_hash": self.payload_hash,
            "feature_values": _normalize_mapping(self.feature_values),
        }


@dataclass(frozen=True)
class OfsDatasetDraft:
    run_key: str
    request_id: str
    intent_kind: str
    platform_run_id: str
    generated_at_utc: str
    feature_profile: dict[str, Any]
    row_order_rules: tuple[str, ...]
    dedupe_stats: dict[str, int]
    replay_status: str | None
    label_status: str | None
    rows: tuple[OfsFeatureDraftRow, ...]
    rows_digest: str
    parity_hash: str | None

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/ofs/dataset_draft/{self.run_key}.json"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "learning.ofs_dataset_draft.v0",
            "run_key": self.run_key,
            "request_id": self.request_id,
            "intent_kind": self.intent_kind,
            "platform_run_id": self.platform_run_id,
            "generated_at_utc": self.generated_at_utc,
            "feature_profile": dict(self.feature_profile),
            "row_order_rules": list(self.row_order_rules),
            "dedupe_stats": {k: int(v) for k, v in sorted(self.dedupe_stats.items())},
            "row_count": len(self.rows),
            "rows_digest": self.rows_digest,
            "rows": [item.as_dict() for item in self.rows],
        }
        if self.replay_status:
            payload["replay_status"] = self.replay_status
        if self.label_status:
            payload["label_status"] = self.label_status
        if self.parity_hash:
            payload["parity_hash"] = self.parity_hash
        return _normalize_mapping(payload)


@dataclass(frozen=True)
class OfsDatasetDraftBuilderConfig:
    object_store_root: str = "runs"
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = None


class OfsDatasetDraftBuilder:
    """Builds deterministic dataset drafts from replay + label evidence."""

    def __init__(self, *, config: OfsDatasetDraftBuilderConfig | None = None) -> None:
        self.config = config or OfsDatasetDraftBuilderConfig()
        self._store = _build_store(self.config)

    def build(
        self,
        *,
        intent: OfsBuildIntent,
        resolved_feature_profile: ResolvedFeatureProfile,
        replay_events: Sequence[ReplayFeatureInputEvent | Mapping[str, Any]],
        replay_receipt: Mapping[str, Any] | None = None,
        label_receipt: Mapping[str, Any] | None = None,
        run_key: str | None = None,
    ) -> OfsDatasetDraft:
        _assert_feature_profile_alignment(intent=intent, profile=resolved_feature_profile)
        events = _normalize_events(replay_events)
        deduped_by_tuple, duplicate_offsets_dropped = _dedupe_by_offset_tuple(events)
        selected_by_event, replay_rows_dropped = _dedupe_by_event_id(deduped_by_tuple)
        ordered = sorted(
            selected_by_event,
            key=lambda row: (
                row.ts_dt_utc,
                row.event_id,
                row.topic,
                int(row.partition),
                row.offset_int,
                row.offset_kind,
                row.payload_hash,
            ),
        )

        rows: list[OfsFeatureDraftRow] = []
        for event in ordered:
            row_id = _deterministic_row_id(
                platform_run_id=intent.platform_run_id,
                event_id=event.event_id,
                topic=event.topic,
                partition=event.partition,
                offset_kind=event.offset_kind,
                offset=event.offset,
                payload_hash=event.payload_hash,
                feature_revision=resolved_feature_profile.resolved_revision,
            )
            rows.append(
                OfsFeatureDraftRow(
                    row_id=row_id,
                    platform_run_id=intent.platform_run_id,
                    event_id=event.event_id,
                    ts_utc=_format_utc(event.ts_dt_utc),
                    topic=event.topic,
                    partition=int(event.partition),
                    offset_kind=event.offset_kind,
                    offset=event.offset,
                    payload_hash=event.payload_hash,
                    feature_values=_project_feature_values(event=event),
                )
            )

        run_key_value = str(run_key or deterministic_run_key(intent.request_id))
        rows_payload = [item.as_dict() for item in rows]
        rows_digest = _sha256_payload({"rows": rows_payload})
        parity_hash = _parity_hash(rows_payload) if _is_parity_intent(intent=intent) else None
        replay_status = _optional_text(replay_receipt.get("status")) if isinstance(replay_receipt, Mapping) else None
        label_status = _optional_text(label_receipt.get("status")) if isinstance(label_receipt, Mapping) else None
        return OfsDatasetDraft(
            run_key=run_key_value,
            request_id=intent.request_id,
            intent_kind=intent.intent_kind,
            platform_run_id=intent.platform_run_id,
            generated_at_utc=_utc_now(),
            feature_profile=resolved_feature_profile.as_dict(),
            row_order_rules=(
                "offset_tuple_dedupe=topic,partition,offset_kind,offset,event_id,payload_hash",
                "event_dedupe=event_id",
                "event_tie_break=min(topic,partition,offset_kind,offset_int,payload_hash)",
                "final_sort=ts_utc,event_id,topic,partition,offset_int,offset_kind,payload_hash",
            ),
            dedupe_stats={
                "input_events_total": len(events),
                "offset_tuple_unique_total": len(deduped_by_tuple),
                "event_unique_total": len(selected_by_event),
                "duplicate_offsets_dropped": int(duplicate_offsets_dropped),
                "event_replays_dropped": int(replay_rows_dropped),
            },
            replay_status=replay_status,
            label_status=label_status,
            rows=tuple(rows),
            rows_digest=rows_digest,
            parity_hash=parity_hash,
        )

    def emit_immutable(self, *, draft: OfsDatasetDraft) -> str:
        relative_path = draft.artifact_relative_path()
        payload = draft.as_dict()
        try:
            ref = self._store.write_json_if_absent(relative_path, payload)
            return str(ref.path)
        except FileExistsError:
            existing = self._store.read_json(relative_path)
            if _normalize_mapping(existing) != payload:
                raise OfsPhase6FeatureError(
                    "DATASET_DRAFT_IMMUTABILITY_VIOLATION",
                    f"dataset draft drift detected at {relative_path}",
                )
            return _artifact_ref(self.config, relative_path)


def _assert_feature_profile_alignment(*, intent: OfsBuildIntent, profile: ResolvedFeatureProfile) -> None:
    if profile.feature_set_id != intent.feature_definition_set.feature_set_id:
        raise OfsPhase6FeatureError(
            "FEATURE_PROFILE_MISMATCH",
            (
                "feature_set_id mismatch between intent and resolved profile: "
                f"{intent.feature_definition_set.feature_set_id!r} != {profile.feature_set_id!r}"
            ),
        )
    if profile.feature_set_version != intent.feature_definition_set.feature_set_version:
        raise OfsPhase6FeatureError(
            "FEATURE_PROFILE_MISMATCH",
            (
                "feature_set_version mismatch between intent and resolved profile: "
                f"{intent.feature_definition_set.feature_set_version!r} != {profile.feature_set_version!r}"
            ),
        )


def _normalize_events(rows: Sequence[ReplayFeatureInputEvent | Mapping[str, Any]]) -> list[ReplayFeatureInputEvent]:
    if not rows:
        raise OfsPhase6FeatureError("REPLAY_EVENTS_EMPTY", "replay_events must be non-empty")
    output: list[ReplayFeatureInputEvent] = []
    for item in rows:
        event = item if isinstance(item, ReplayFeatureInputEvent) else ReplayFeatureInputEvent.from_payload(item)
        _ = event.offset_int
        _ = event.ts_dt_utc
        output.append(event)
    return output


def _dedupe_by_offset_tuple(
    rows: Sequence[ReplayFeatureInputEvent],
) -> tuple[list[ReplayFeatureInputEvent], int]:
    by_tuple: dict[tuple[str, int, str, str, str], ReplayFeatureInputEvent] = {}
    duplicate_offsets_dropped = 0
    for event in rows:
        key = event.tuple_key()
        existing = by_tuple.get(key)
        if existing is None:
            by_tuple[key] = event
            continue
        if existing.payload_hash != event.payload_hash:
            raise OfsPhase6FeatureError(
                "REPLAY_DUPLICATE_OFFSET_MISMATCH",
                (
                    "duplicate offset tuple has conflicting payload_hash: "
                    f"{event.topic}/{event.partition}/{event.offset_kind}/{event.offset} event_id={event.event_id!r}"
                ),
            )
        duplicate_offsets_dropped += 1
    ordered = sorted(by_tuple.values(), key=lambda item: item.event_tie_break_key() + (item.event_id,))
    return ordered, duplicate_offsets_dropped


def _dedupe_by_event_id(
    rows: Sequence[ReplayFeatureInputEvent],
) -> tuple[list[ReplayFeatureInputEvent], int]:
    grouped: dict[str, list[ReplayFeatureInputEvent]] = {}
    for row in rows:
        grouped.setdefault(row.event_id, []).append(row)
    selected: list[ReplayFeatureInputEvent] = []
    replay_rows_dropped = 0
    for event_id, items in grouped.items():
        payload_hashes = sorted({item.payload_hash for item in items})
        if len(payload_hashes) > 1:
            raise OfsPhase6FeatureError(
                "REPLAY_EVENT_ID_CONFLICT",
                f"event_id {event_id!r} has conflicting payload hashes across replay rows",
            )
        winner = min(items, key=lambda item: item.event_tie_break_key())
        selected.append(winner)
        replay_rows_dropped += max(len(items) - 1, 0)
    return selected, replay_rows_dropped


def _project_feature_values(*, event: ReplayFeatureInputEvent) -> dict[str, Any]:
    values: dict[str, Any] = {
        "partition": int(event.partition),
        "offset_value": int(event.offset_int),
        "topic_hash_mod_100000": int(hashlib.sha256(event.topic.encode("utf-8")).hexdigest(), 16) % 100_000,
        "event_id_hash_mod_100000": int(hashlib.sha256(event.event_id.encode("utf-8")).hexdigest(), 16) % 100_000,
    }
    for key in sorted(event.payload):
        value = event.payload[key]
        if isinstance(value, bool):
            values[f"payload_num::{key}"] = int(value)
            continue
        if isinstance(value, (int, float)):
            values[f"payload_num::{key}"] = value
            continue
    values["payload_numeric_feature_count"] = sum(1 for key in values if key.startswith("payload_num::"))
    return values


def _deterministic_row_id(
    *,
    platform_run_id: str,
    event_id: str,
    topic: str,
    partition: int,
    offset_kind: str,
    offset: str,
    payload_hash: str,
    feature_revision: str,
) -> str:
    payload = {
        "recipe": "ofs.phase6.row_id.v1",
        "platform_run_id": platform_run_id,
        "event_id": event_id,
        "topic": topic,
        "partition": int(partition),
        "offset_kind": offset_kind,
        "offset": offset,
        "payload_hash": payload_hash,
        "feature_revision": feature_revision,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


def _parity_hash(rows_payload: Sequence[Mapping[str, Any]]) -> str:
    payload = {"recipe": "ofs.phase6.parity_hash.v1", "rows": list(rows_payload)}
    encoded = json.dumps(_normalize_mapping(payload), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_parity_intent(*, intent: OfsBuildIntent) -> bool:
    return intent.intent_kind in {"parity_rebuild", "forensic_rebuild"} or bool(intent.parity_anchor_ref)


def _build_store(config: OfsDatasetDraftBuilderConfig) -> ObjectStore:
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


def _artifact_ref(config: OfsDatasetDraftBuilderConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


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
        raise OfsPhase6FeatureError(code, f"{field_name} must be a mapping")
    return dict(value)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _required_text(value: Any, *, code: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise OfsPhase6FeatureError(code, f"{field_name} is required")
    return text


def _required_non_negative_int(value: Any, *, code: str, field_name: str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:  # noqa: BLE001
        raise OfsPhase6FeatureError(code, f"{field_name} must be an integer") from exc
    if parsed < 0:
        raise OfsPhase6FeatureError(code, f"{field_name} must be >= 0")
    return parsed


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse_utc(value: str, *, field_name: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise OfsPhase6FeatureError("REPLAY_EVENT_INVALID", f"{field_name} is required")
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(probe)
    except ValueError as exc:
        raise OfsPhase6FeatureError("REPLAY_EVENT_INVALID", f"{field_name} must be ISO-8601: {text}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
