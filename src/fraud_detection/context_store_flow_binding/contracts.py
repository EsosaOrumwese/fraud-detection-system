"""Context Store + FlowBinding contract validators (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import re

from .taxonomy import (
    ContextStoreFlowBindingTaxonomyError,
    ensure_authoritative_flow_binding_event_type,
)


HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PLATFORM_RUN_ID_RE = re.compile(r"^platform_[0-9]{8}T[0-9]{6}Z$")

REQUIRED_PINS: tuple[str, ...] = (
    "platform_run_id",
    "scenario_run_id",
    "manifest_fingerprint",
    "parameter_hash",
    "scenario_id",
    "seed",
)

QUERY_KINDS: set[str] = {"resolve_flow_binding", "fetch_join_frame"}
RESPONSE_STATUSES: set[str] = {
    "READY",
    "MISSING_BINDING",
    "MISSING_JOIN_FRAME",
    "CONFLICT",
    "INVALID_REQUEST",
}


class ContextStoreFlowBindingContractError(ValueError):
    """Raised when CSFB contracts are malformed."""


@dataclass(frozen=True)
class JoinFrameKey:
    platform_run_id: str
    scenario_run_id: str
    merchant_id: str
    arrival_seq: int
    run_id: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "JoinFrameKey":
        mapped = _as_mapping(payload, "join_frame_key")
        platform_run_id = _require_platform_run_id(mapped.get("platform_run_id"), "join_frame_key.platform_run_id")
        scenario_run_id = _require_hex32(mapped.get("scenario_run_id"), "join_frame_key.scenario_run_id")
        merchant_id = _require_non_empty_str(mapped.get("merchant_id"), "join_frame_key.merchant_id")
        arrival_seq = _require_uint(mapped.get("arrival_seq"), "join_frame_key.arrival_seq")
        run_id_raw = mapped.get("run_id")
        run_id = _require_hex32(run_id_raw, "join_frame_key.run_id") if run_id_raw not in (None, "") else None
        return cls(
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            merchant_id=merchant_id,
            arrival_seq=arrival_seq,
            run_id=run_id,
        )

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "merchant_id": self.merchant_id,
            "arrival_seq": self.arrival_seq,
        }
        if self.run_id:
            payload["run_id"] = self.run_id
        return payload


@dataclass(frozen=True)
class QueryRequest:
    request_id: str
    query_kind: str
    pins: dict[str, Any]
    flow_id: str | None
    join_frame_key: JoinFrameKey | None
    as_of_ts_utc: str | None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "QueryRequest":
        mapped = _as_mapping(payload, "query_request")
        request_id = _require_non_empty_str(mapped.get("request_id"), "query_request.request_id")
        query_kind = _require_non_empty_str(mapped.get("query_kind"), "query_request.query_kind")
        if query_kind not in QUERY_KINDS:
            raise ContextStoreFlowBindingContractError(
                f"query_request.query_kind must be one of {sorted(QUERY_KINDS)}"
            )
        pins = _normalize_pins(mapped.get("pins"), "query_request.pins")
        flow_id_raw = mapped.get("flow_id")
        join_frame_key_raw = mapped.get("join_frame_key")
        has_flow_id = flow_id_raw not in (None, "")
        has_join_key = join_frame_key_raw is not None
        if has_flow_id == has_join_key:
            raise ContextStoreFlowBindingContractError(
                "query_request requires exactly one selector: flow_id xor join_frame_key"
            )
        flow_id = _require_non_empty_str(flow_id_raw, "query_request.flow_id") if has_flow_id else None
        join_frame_key = JoinFrameKey.from_mapping(join_frame_key_raw) if has_join_key else None
        as_of_ts_utc_raw = mapped.get("as_of_ts_utc")
        as_of_ts_utc = _require_non_empty_str(as_of_ts_utc_raw, "query_request.as_of_ts_utc") if as_of_ts_utc_raw else None
        return cls(
            request_id=request_id,
            query_kind=query_kind,
            pins=pins,
            flow_id=flow_id,
            join_frame_key=join_frame_key,
            as_of_ts_utc=as_of_ts_utc,
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "query_kind": self.query_kind,
            "pins": dict(self.pins),
        }
        if self.flow_id is not None:
            payload["flow_id"] = self.flow_id
        if self.join_frame_key is not None:
            payload["join_frame_key"] = self.join_frame_key.as_dict()
        if self.as_of_ts_utc is not None:
            payload["as_of_ts_utc"] = self.as_of_ts_utc
        return payload


@dataclass(frozen=True)
class FlowBindingRecord:
    flow_id: str
    join_frame_key: JoinFrameKey
    source_event: dict[str, Any]
    authoritative_source_event_type: str
    payload_hash: str
    pins: dict[str, Any]
    bound_at_utc: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "FlowBindingRecord":
        mapped = _as_mapping(payload, "flow_binding")
        flow_id = _require_non_empty_str(mapped.get("flow_id"), "flow_binding.flow_id")
        join_frame_key = JoinFrameKey.from_mapping(mapped.get("join_frame_key"))
        source_event = _normalize_source_event(mapped.get("source_event"), "flow_binding.source_event")
        authoritative_source_event_type = _require_non_empty_str(
            mapped.get("authoritative_source_event_type"),
            "flow_binding.authoritative_source_event_type",
        )
        try:
            ensure_authoritative_flow_binding_event_type(authoritative_source_event_type)
        except ContextStoreFlowBindingTaxonomyError as exc:
            raise ContextStoreFlowBindingContractError(str(exc)) from exc
        payload_hash = _require_hex64(mapped.get("payload_hash"), "flow_binding.payload_hash")
        pins = _normalize_pins(mapped.get("pins"), "flow_binding.pins")
        bound_at_utc = _require_non_empty_str(mapped.get("bound_at_utc"), "flow_binding.bound_at_utc")
        return cls(
            flow_id=flow_id,
            join_frame_key=join_frame_key,
            source_event=source_event,
            authoritative_source_event_type=authoritative_source_event_type,
            payload_hash=payload_hash,
            pins=pins,
            bound_at_utc=bound_at_utc,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "join_frame_key": self.join_frame_key.as_dict(),
            "source_event": dict(self.source_event),
            "authoritative_source_event_type": self.authoritative_source_event_type,
            "payload_hash": self.payload_hash,
            "pins": dict(self.pins),
            "bound_at_utc": self.bound_at_utc,
        }


@dataclass(frozen=True)
class QueryResponse:
    request_id: str
    status: str
    reason_codes: tuple[str, ...]
    pins: dict[str, Any]
    resolved_at_utc: str
    flow_id: str | None = None
    join_frame_key: JoinFrameKey | None = None
    flow_binding: FlowBindingRecord | None = None
    evidence_refs: tuple[dict[str, str], ...] = ()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "QueryResponse":
        mapped = _as_mapping(payload, "query_response")
        request_id = _require_non_empty_str(mapped.get("request_id"), "query_response.request_id")
        status = _require_non_empty_str(mapped.get("status"), "query_response.status")
        if status not in RESPONSE_STATUSES:
            raise ContextStoreFlowBindingContractError(
                f"query_response.status must be one of {sorted(RESPONSE_STATUSES)}"
            )
        reason_codes = _normalize_reason_codes(mapped.get("reason_codes"))
        pins = _normalize_pins(mapped.get("pins"), "query_response.pins")
        resolved_at_utc = _require_non_empty_str(mapped.get("resolved_at_utc"), "query_response.resolved_at_utc")
        flow_id_raw = mapped.get("flow_id")
        flow_id = _require_non_empty_str(flow_id_raw, "query_response.flow_id") if flow_id_raw not in (None, "") else None
        join_frame_key_raw = mapped.get("join_frame_key")
        join_frame_key = JoinFrameKey.from_mapping(join_frame_key_raw) if join_frame_key_raw is not None else None
        flow_binding_raw = mapped.get("flow_binding")
        flow_binding = FlowBindingRecord.from_mapping(flow_binding_raw) if flow_binding_raw is not None else None
        evidence_refs = _normalize_evidence_refs(mapped.get("evidence_refs"))
        return cls(
            request_id=request_id,
            status=status,
            reason_codes=reason_codes,
            pins=pins,
            resolved_at_utc=resolved_at_utc,
            flow_id=flow_id,
            join_frame_key=join_frame_key,
            flow_binding=flow_binding,
            evidence_refs=evidence_refs,
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "pins": dict(self.pins),
            "resolved_at_utc": self.resolved_at_utc,
        }
        if self.flow_id is not None:
            payload["flow_id"] = self.flow_id
        if self.join_frame_key is not None:
            payload["join_frame_key"] = self.join_frame_key.as_dict()
        if self.flow_binding is not None:
            payload["flow_binding"] = self.flow_binding.as_dict()
        if self.evidence_refs:
            payload["evidence_refs"] = [dict(item) for item in self.evidence_refs]
        return payload


def _as_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContextStoreFlowBindingContractError(f"{field_name} must be a mapping")
    return dict(value)


def _require_non_empty_str(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContextStoreFlowBindingContractError(f"{field_name} must be a non-empty string")
    return text


def _require_hex32(value: Any, field_name: str) -> str:
    text = _require_non_empty_str(value, field_name)
    if not HEX32_RE.fullmatch(text):
        raise ContextStoreFlowBindingContractError(f"{field_name} must be 32-char lowercase hex")
    return text


def _require_hex64(value: Any, field_name: str) -> str:
    text = _require_non_empty_str(value, field_name)
    if not HEX64_RE.fullmatch(text):
        raise ContextStoreFlowBindingContractError(f"{field_name} must be 64-char lowercase hex")
    return text


def _require_platform_run_id(value: Any, field_name: str) -> str:
    text = _require_non_empty_str(value, field_name)
    if not PLATFORM_RUN_ID_RE.fullmatch(text):
        raise ContextStoreFlowBindingContractError(
            f"{field_name} must match platform_YYYYMMDDTHHMMSSZ"
        )
    return text


def _require_uint(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise ContextStoreFlowBindingContractError(f"{field_name} must be an integer >= 0")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContextStoreFlowBindingContractError(f"{field_name} must be an integer >= 0") from exc
    if parsed < 0:
        raise ContextStoreFlowBindingContractError(f"{field_name} must be an integer >= 0")
    return parsed


def _normalize_pins(value: Any, field_name: str) -> dict[str, Any]:
    mapped = _as_mapping(value, field_name)
    missing = [pin for pin in REQUIRED_PINS if mapped.get(pin) in (None, "")]
    if missing:
        raise ContextStoreFlowBindingContractError(
            f"{field_name} missing required pins: {','.join(missing)}"
        )
    pins = {
        "platform_run_id": _require_platform_run_id(mapped.get("platform_run_id"), f"{field_name}.platform_run_id"),
        "scenario_run_id": _require_hex32(mapped.get("scenario_run_id"), f"{field_name}.scenario_run_id"),
        "manifest_fingerprint": _require_hex64(
            mapped.get("manifest_fingerprint"), f"{field_name}.manifest_fingerprint"
        ),
        "parameter_hash": _require_hex64(mapped.get("parameter_hash"), f"{field_name}.parameter_hash"),
        "scenario_id": _require_non_empty_str(mapped.get("scenario_id"), f"{field_name}.scenario_id"),
        "seed": _require_uint(mapped.get("seed"), f"{field_name}.seed"),
    }
    run_id_raw = mapped.get("run_id")
    if run_id_raw not in (None, ""):
        pins["run_id"] = _require_hex32(run_id_raw, f"{field_name}.run_id")
    return pins


def _normalize_source_event(value: Any, field_name: str) -> dict[str, Any]:
    mapped = _as_mapping(value, field_name)
    event_id = _require_non_empty_str(mapped.get("event_id"), f"{field_name}.event_id")
    event_type = _require_non_empty_str(mapped.get("event_type"), f"{field_name}.event_type")
    ts_utc = _require_non_empty_str(mapped.get("ts_utc"), f"{field_name}.ts_utc")
    eb_ref = _normalize_eb_ref(mapped.get("eb_ref"), f"{field_name}.eb_ref")
    source = {"event_id": event_id, "event_type": event_type, "ts_utc": ts_utc, "eb_ref": eb_ref}
    return source


def _normalize_eb_ref(value: Any, field_name: str) -> dict[str, Any]:
    mapped = _as_mapping(value, field_name)
    topic = _require_non_empty_str(mapped.get("topic"), f"{field_name}.topic")
    partition = _require_uint(mapped.get("partition"), f"{field_name}.partition")
    offset = _require_non_empty_str(mapped.get("offset"), f"{field_name}.offset")
    offset_kind = _require_non_empty_str(mapped.get("offset_kind"), f"{field_name}.offset_kind")
    if offset_kind not in {"file_line", "kinesis_sequence", "kafka_offset"}:
        raise ContextStoreFlowBindingContractError(
            f"{field_name}.offset_kind must be one of file_line,kinesis_sequence,kafka_offset"
        )
    payload = {
        "topic": topic,
        "partition": partition,
        "offset": offset,
        "offset_kind": offset_kind,
    }
    published_at_utc = mapped.get("published_at_utc")
    if published_at_utc not in (None, ""):
        payload["published_at_utc"] = _require_non_empty_str(
            published_at_utc, f"{field_name}.published_at_utc"
        )
    return payload


def _normalize_reason_codes(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContextStoreFlowBindingContractError("query_response.reason_codes must be a list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(_require_non_empty_str(item, f"query_response.reason_codes[{index}]"))
    return tuple(normalized)


def _normalize_evidence_refs(value: Any) -> tuple[dict[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ContextStoreFlowBindingContractError("query_response.evidence_refs must be a list")
    refs: list[dict[str, str]] = []
    for index, item in enumerate(value):
        mapped = _as_mapping(item, f"query_response.evidence_refs[{index}]")
        kind = _require_non_empty_str(mapped.get("kind"), f"query_response.evidence_refs[{index}].kind")
        ref = _require_non_empty_str(mapped.get("ref"), f"query_response.evidence_refs[{index}].ref")
        refs.append({"kind": kind, "ref": ref})
    return tuple(refs)
