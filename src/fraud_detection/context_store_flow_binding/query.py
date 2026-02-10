"""CSFB read/query surface for DF/DL (Phase 5)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import (
    ContextStoreFlowBindingContractError,
    QueryRequest,
    QueryResponse,
)
from .store import ContextStoreFlowBindingStore, build_store


class ContextStoreFlowBindingQueryService:
    def __init__(self, store: ContextStoreFlowBindingStore, *, stream_id: str) -> None:
        self.store = store
        self.stream_id = stream_id

    @classmethod
    def build(cls, *, locator: str | Path, stream_id: str) -> "ContextStoreFlowBindingQueryService":
        store = build_store(locator, stream_id=stream_id)
        return cls(store=store, stream_id=stream_id)

    @classmethod
    def build_from_policy(cls, policy_path: str | Path) -> "ContextStoreFlowBindingQueryService":
        from .intake import CsfbInletPolicy

        policy = CsfbInletPolicy.load(Path(policy_path))
        return cls.build(locator=policy.projection_db_dsn, stream_id=policy.stream_id)

    def query(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        resolved_at_utc = _utc_now()
        try:
            request = QueryRequest.from_mapping(payload)
        except ContextStoreFlowBindingContractError as exc:
            invalid = self._invalid_request_response(payload=payload, resolved_at_utc=resolved_at_utc)
            if invalid is not None:
                return invalid
            raise exc

        if request.query_kind == "resolve_flow_binding":
            return self._resolve_flow_binding(request=request, resolved_at_utc=resolved_at_utc)
        if request.query_kind == "fetch_join_frame":
            return self._fetch_join_frame(request=request, resolved_at_utc=resolved_at_utc)
        return self._response(
            request_id=request.request_id,
            status="INVALID_REQUEST",
            reason_codes=["INVALID_REQUEST"],
            pins=request.pins,
            resolved_at_utc=resolved_at_utc,
            evidence_refs=(),
        )

    def _resolve_flow_binding(self, *, request: QueryRequest, resolved_at_utc: str) -> dict[str, Any]:
        assert request.flow_id is not None
        binding = self.store.read_flow_binding(
            platform_run_id=str(request.pins["platform_run_id"]),
            scenario_run_id=str(request.pins["scenario_run_id"]),
            flow_id=request.flow_id,
        )
        if binding is None:
            return self._response(
                request_id=request.request_id,
                status="MISSING_BINDING",
                reason_codes=["FLOW_BINDING_NOT_FOUND"],
                pins=request.pins,
                resolved_at_utc=resolved_at_utc,
                flow_id=request.flow_id,
                evidence_refs=(),
            )

        if _pins_mismatch(request.pins, binding.pins):
            return self._response(
                request_id=request.request_id,
                status="CONFLICT",
                reason_codes=["PINS_MISMATCH"],
                pins=request.pins,
                resolved_at_utc=resolved_at_utc,
                flow_id=request.flow_id,
                join_frame_key=binding.join_frame_key.as_dict(),
                flow_binding=binding.as_dict(),
                evidence_refs=_binding_evidence(binding=binding),
            )

        join_frame = self.store.read_join_frame_record(join_frame_key=binding.join_frame_key)
        if join_frame is None:
            return self._response(
                request_id=request.request_id,
                status="MISSING_JOIN_FRAME",
                reason_codes=["JOIN_FRAME_NOT_FOUND"],
                pins=request.pins,
                resolved_at_utc=resolved_at_utc,
                flow_id=request.flow_id,
                join_frame_key=binding.join_frame_key.as_dict(),
                flow_binding=binding.as_dict(),
                evidence_refs=_binding_evidence(binding=binding),
            )

        evidence_refs = _binding_evidence(binding=binding) + _join_evidence(join_source=join_frame.source_event)
        evidence_refs = evidence_refs + _checkpoint_evidence(
            store=self.store,
            topic=str(join_frame.source_event.get("eb_ref", {}).get("topic") or ""),
            partition=_as_int(join_frame.source_event.get("eb_ref", {}).get("partition"), default=0),
        )
        return self._response(
            request_id=request.request_id,
            status="READY",
            reason_codes=["READY"],
            pins=request.pins,
            resolved_at_utc=resolved_at_utc,
            flow_id=request.flow_id,
            join_frame_key=binding.join_frame_key.as_dict(),
            flow_binding=binding.as_dict(),
            evidence_refs=evidence_refs,
        )

    def _fetch_join_frame(self, *, request: QueryRequest, resolved_at_utc: str) -> dict[str, Any]:
        assert request.join_frame_key is not None
        join_frame = self.store.read_join_frame_record(join_frame_key=request.join_frame_key)
        if join_frame is None:
            return self._response(
                request_id=request.request_id,
                status="MISSING_JOIN_FRAME",
                reason_codes=["JOIN_FRAME_NOT_FOUND"],
                pins=request.pins,
                resolved_at_utc=resolved_at_utc,
                join_frame_key=request.join_frame_key.as_dict(),
                evidence_refs=(),
            )

        flow_binding = self.store.read_flow_binding_for_join_frame(join_frame_key=request.join_frame_key)
        flow_id = flow_binding.flow_id if flow_binding is not None else None
        if flow_binding is not None and _pins_mismatch(request.pins, flow_binding.pins):
            return self._response(
                request_id=request.request_id,
                status="CONFLICT",
                reason_codes=["PINS_MISMATCH"],
                pins=request.pins,
                resolved_at_utc=resolved_at_utc,
                flow_id=flow_id,
                join_frame_key=request.join_frame_key.as_dict(),
                flow_binding=flow_binding.as_dict(),
                evidence_refs=_join_evidence(join_source=join_frame.source_event),
            )

        evidence_refs = _join_evidence(join_source=join_frame.source_event)
        evidence_refs = evidence_refs + _checkpoint_evidence(
            store=self.store,
            topic=str(join_frame.source_event.get("eb_ref", {}).get("topic") or ""),
            partition=_as_int(join_frame.source_event.get("eb_ref", {}).get("partition"), default=0),
        )
        if flow_binding is not None:
            evidence_refs = _binding_evidence(binding=flow_binding) + evidence_refs

        return self._response(
            request_id=request.request_id,
            status="READY",
            reason_codes=["READY"],
            pins=request.pins,
            resolved_at_utc=resolved_at_utc,
            flow_id=flow_id,
            join_frame_key=request.join_frame_key.as_dict(),
            flow_binding=flow_binding.as_dict() if flow_binding is not None else None,
            evidence_refs=evidence_refs,
        )

    def _invalid_request_response(self, *, payload: Mapping[str, Any], resolved_at_utc: str) -> dict[str, Any] | None:
        request_id = str(payload.get("request_id") or "invalid-request")
        pins = payload.get("pins")
        if not isinstance(pins, Mapping):
            return None
        response_payload: dict[str, Any] = {
            "request_id": request_id,
            "status": "INVALID_REQUEST",
            "reason_codes": ["INVALID_REQUEST"],
            "pins": dict(pins),
            "resolved_at_utc": resolved_at_utc,
        }
        try:
            response = QueryResponse.from_mapping(response_payload)
        except ContextStoreFlowBindingContractError:
            return None
        return response.as_dict()

    def _response(
        self,
        *,
        request_id: str,
        status: str,
        reason_codes: list[str],
        pins: Mapping[str, Any],
        resolved_at_utc: str,
        flow_id: str | None = None,
        join_frame_key: Mapping[str, Any] | None = None,
        flow_binding: Mapping[str, Any] | None = None,
        evidence_refs: tuple[dict[str, str], ...] = (),
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": request_id,
            "status": status,
            "reason_codes": reason_codes,
            "pins": dict(pins),
            "resolved_at_utc": resolved_at_utc,
        }
        if flow_id:
            payload["flow_id"] = flow_id
        if join_frame_key is not None:
            payload["join_frame_key"] = dict(join_frame_key)
        if flow_binding is not None:
            payload["flow_binding"] = dict(flow_binding)
        if evidence_refs:
            payload["evidence_refs"] = [dict(item) for item in evidence_refs]
        response = QueryResponse.from_mapping(payload)
        return response.as_dict()


def _pins_mismatch(request_pins: Mapping[str, Any], record_pins: Mapping[str, Any]) -> bool:
    keys = (
        "platform_run_id",
        "scenario_run_id",
        "manifest_fingerprint",
        "parameter_hash",
        "scenario_id",
        "seed",
    )
    for key in keys:
        if str(request_pins.get(key)) != str(record_pins.get(key)):
            return True
    request_run_id = request_pins.get("run_id")
    record_run_id = record_pins.get("run_id")
    if request_run_id not in (None, "") and record_run_id not in (None, ""):
        if str(request_run_id) != str(record_run_id):
            return True
    return False


def _binding_evidence(*, binding: Any) -> tuple[dict[str, str], ...]:
    source = dict(binding.source_event)
    eb_ref = dict(source.get("eb_ref") or {})
    ref = (
        f"topic={eb_ref.get('topic')};partition={eb_ref.get('partition')};offset={eb_ref.get('offset')};"
        f"offset_kind={eb_ref.get('offset_kind')};event_id={source.get('event_id')};event_type={source.get('event_type')}"
    )
    return ({"kind": "flow_binding_source_event", "ref": ref},)


def _join_evidence(*, join_source: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    source = dict(join_source)
    eb_ref = dict(source.get("eb_ref") or {})
    ref = (
        f"topic={eb_ref.get('topic')};partition={eb_ref.get('partition')};offset={eb_ref.get('offset')};"
        f"offset_kind={eb_ref.get('offset_kind')};event_id={source.get('event_id')};event_type={source.get('event_type')}"
    )
    return ({"kind": "join_frame_source_event", "ref": ref},)


def _checkpoint_evidence(*, store: ContextStoreFlowBindingStore, topic: str, partition: int) -> tuple[dict[str, str], ...]:
    if not topic:
        return ()
    checkpoint = store.get_checkpoint(topic=topic, partition_id=partition)
    if checkpoint is None:
        return ()
    ref = (
        f"topic={checkpoint.topic};partition={checkpoint.partition_id};next_offset={checkpoint.next_offset};"
        f"offset_kind={checkpoint.offset_kind};watermark_ts_utc={checkpoint.watermark_ts_utc}"
    )
    return ({"kind": "join_checkpoint", "ref": ref},)


def _as_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
