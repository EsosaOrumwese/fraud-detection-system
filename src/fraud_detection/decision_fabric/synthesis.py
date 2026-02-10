"""Decision Fabric deterministic synthesis + envelope emission helpers (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .context import CONTEXT_READY, DecisionContextResult
from .contracts import ActionIntent, DecisionResponse
from .ids import (
    deterministic_action_idempotency_key,
    deterministic_action_intent_event_id,
    deterministic_decision_id,
    deterministic_decision_response_event_id,
)
from .inlet import DecisionTriggerCandidate
from .posture import DfPostureStamp
from .registry import RESOLUTION_FAIL_CLOSED, RegistryResolutionResult


ACTION_ALLOW = "ALLOW"
ACTION_STEP_UP = "STEP_UP"
ACTION_REVIEW = "QUEUE_REVIEW"


class DecisionFabricSynthesisError(ValueError):
    """Raised when DF synthesis inputs are invalid."""


@dataclass(frozen=True)
class DecisionArtifacts:
    decision_payload: dict[str, Any]
    action_intents: tuple[dict[str, Any], ...]
    decision_envelope: dict[str, Any]
    action_envelopes: tuple[dict[str, Any], ...]


@dataclass
class DecisionSynthesizer:
    decision_kind: str = "fraud_decision_v0"
    actor_principal: str = "SYSTEM::decision_fabric"
    schema_version: str = "v1"

    def synthesize(
        self,
        *,
        candidate: DecisionTriggerCandidate,
        posture: DfPostureStamp,
        registry_result: RegistryResolutionResult,
        context_result: DecisionContextResult,
        run_config_digest: str,
        decided_at_utc: str,
        requested_at_utc: str,
        decision_scope: str = "fraud.primary",
    ) -> DecisionArtifacts:
        pins = _normalize_pins(candidate.pins)
        reason_codes = _decision_reason_codes(context_result=context_result, registry_result=registry_result)
        action_kind, clamp_reasons = _choose_action_kind(
            posture=posture,
            context_result=context_result,
            registry_result=registry_result,
        )
        reason_codes.extend(clamp_reasons)
        bundle_ref = _normalize_bundle_ref(registry_result.bundle_ref)
        eb_offset_basis = _decision_eb_offset_basis(candidate, context_result)
        graph_version = _decision_graph_version(candidate, context_result)
        decision_id = deterministic_decision_id(
            source_event_id=candidate.source_event_id,
            platform_run_id=str(candidate.pins.get("platform_run_id") or ""),
            decision_scope=decision_scope,
            bundle_ref=bundle_ref,
            origin_offset=_origin_offset_from_candidate(candidate),
        )
        decision_payload = {
            "decision_id": decision_id,
            "decision_kind": self.decision_kind,
            "bundle_ref": bundle_ref,
            "snapshot_hash": _snapshot_hash(context_result),
            "graph_version": graph_version,
            "eb_offset_basis": eb_offset_basis,
            "degrade_posture": _degrade_posture_payload(posture),
            "pins": pins,
            "decided_at_utc": decided_at_utc,
            "policy_rev": registry_result.policy_rev.as_dict(),
            "run_config_digest": run_config_digest,
            "source_event": _source_event_payload(candidate),
            "decision": {
                "action_kind": action_kind,
                "context_status": context_result.status,
                "registry_outcome": registry_result.outcome,
                "context_evidence_digest": context_result.evidence.digest(),
            },
            "reason_codes": sorted(set(reason_codes)),
        }
        if context_result.evidence.ofp_snapshot_hash:
            decision_payload["snapshot_ref"] = f"ofp://snapshot/{context_result.evidence.ofp_snapshot_hash}"

        decision_response = DecisionResponse.from_payload(decision_payload)
        action_payload = _build_action_intent(
            decision_response=decision_response,
            candidate=candidate,
            action_kind=action_kind,
            posture=posture,
            policy_rev=registry_result.policy_rev.as_dict(),
            run_config_digest=run_config_digest,
            requested_at_utc=requested_at_utc,
            actor_principal=self.actor_principal,
        )
        action_intent = ActionIntent.from_payload(action_payload)
        action_intents = (action_intent.as_dict(),)

        decision_envelope = self._decision_envelope(
            candidate=candidate,
            decision_payload=decision_response.as_dict(),
            decision_scope=decision_scope,
            decided_at_utc=decided_at_utc,
        )
        action_envelopes = tuple(
            self._action_envelope(
                candidate=candidate,
                action_payload=payload,
                action_domain=str(payload["action_kind"]).lower(),
                requested_at_utc=requested_at_utc,
            )
            for payload in sorted(action_intents, key=lambda item: (item["action_kind"], item["action_id"]))
        )
        return DecisionArtifacts(
            decision_payload=decision_response.as_dict(),
            action_intents=action_intents,
            decision_envelope=decision_envelope,
            action_envelopes=action_envelopes,
        )

    def build_correction(
        self,
        *,
        original_decision_payload: Mapping[str, Any],
        corrected_decision_fragment: Mapping[str, Any],
        correction_reason: str,
        corrected_at_utc: str,
        decision_scope: str,
    ) -> dict[str, Any]:
        base = dict(original_decision_payload)
        original = DecisionResponse.from_payload(base)
        corrected = dict(base)
        superseded_id = original.decision_id
        bundle_ref = _normalize_bundle_ref(base.get("bundle_ref"))
        new_scope = f"{decision_scope}:correction:{correction_reason}"
        corrected["decision_id"] = deterministic_decision_id(
            source_event_id=str(base.get("source_event", {}).get("event_id") or ""),
            platform_run_id=str((base.get("pins") or {}).get("platform_run_id") or ""),
            decision_scope=new_scope,
            bundle_ref=bundle_ref,
            origin_offset=_origin_offset_from_source_event(base.get("source_event")),
        )
        corrected["decided_at_utc"] = corrected_at_utc
        decision_obj = dict(base.get("decision") or {})
        decision_obj.update(dict(corrected_decision_fragment))
        decision_obj["supersedes_decision_id"] = superseded_id
        corrected["decision"] = decision_obj
        reasons = list(base.get("reason_codes") or [])
        reasons.extend(["CORRECTION", f"CORRECTION_REASON:{correction_reason}"])
        corrected["reason_codes"] = sorted(set(str(item) for item in reasons if str(item).strip()))
        return DecisionResponse.from_payload(corrected).as_dict()

    def _decision_envelope(
        self,
        *,
        candidate: DecisionTriggerCandidate,
        decision_payload: dict[str, Any],
        decision_scope: str,
        decided_at_utc: str,
    ) -> dict[str, Any]:
        event_id = deterministic_decision_response_event_id(
            source_event_id=candidate.source_event_id,
            decision_scope=decision_scope,
            pins=candidate.pins,
        )
        envelope = _canonical_envelope(
            event_id=event_id,
            event_type="decision_response",
            schema_version=self.schema_version,
            ts_utc=decided_at_utc,
            pins=candidate.pins,
            payload=decision_payload,
            parent_event_id=candidate.source_event_id,
            producer="decision_fabric",
        )
        return envelope

    def _action_envelope(
        self,
        *,
        candidate: DecisionTriggerCandidate,
        action_payload: dict[str, Any],
        action_domain: str,
        requested_at_utc: str,
    ) -> dict[str, Any]:
        event_id = deterministic_action_intent_event_id(
            source_event_id=candidate.source_event_id,
            action_domain=action_domain,
            pins=candidate.pins,
        )
        envelope = _canonical_envelope(
            event_id=event_id,
            event_type="action_intent",
            schema_version=self.schema_version,
            ts_utc=requested_at_utc,
            pins=candidate.pins,
            payload=action_payload,
            parent_event_id=candidate.source_event_id,
            producer="decision_fabric",
        )
        return envelope


def _build_action_intent(
    *,
    decision_response: DecisionResponse,
    candidate: DecisionTriggerCandidate,
    action_kind: str,
    posture: DfPostureStamp,
    policy_rev: Mapping[str, Any],
    run_config_digest: str,
    requested_at_utc: str,
    actor_principal: str,
) -> dict[str, Any]:
    domain = action_kind.lower()
    idempotency_key = deterministic_action_idempotency_key(
        source_event_id=candidate.source_event_id,
        action_domain=domain,
        pins=candidate.pins,
    )
    action_id = hashlib.sha256(f"{decision_response.decision_id}:{action_kind}".encode("utf-8")).hexdigest()[:32]
    payload = {
        "action_id": action_id,
        "decision_id": decision_response.decision_id,
        "action_kind": action_kind,
        "idempotency_key": idempotency_key,
        "pins": _normalize_pins(candidate.pins),
        "requested_at_utc": requested_at_utc,
        "actor_principal": actor_principal,
        "origin": "DF",
        "policy_rev": dict(policy_rev),
        "run_config_digest": run_config_digest,
        "reason_ref": f"decision://{decision_response.decision_id}",
        "action_payload": {
            "source_event_id": candidate.source_event_id,
            "source_event_type": candidate.source_event_type,
            "action_posture": posture.capabilities_mask.action_posture,
        },
    }
    return payload


def _choose_action_kind(
    *,
    posture: DfPostureStamp,
    context_result: DecisionContextResult,
    registry_result: RegistryResolutionResult,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if registry_result.outcome == RESOLUTION_FAIL_CLOSED:
        action_kind = ACTION_REVIEW
        reasons.append("REGISTRY_FAIL_CLOSED")
    elif context_result.status != CONTEXT_READY:
        action_kind = ACTION_STEP_UP
        reasons.append(f"CONTEXT_STATUS:{context_result.status}")
    else:
        action_kind = ACTION_ALLOW
    if posture.capabilities_mask.action_posture == "STEP_UP_ONLY" and action_kind == ACTION_ALLOW:
        action_kind = ACTION_STEP_UP
        reasons.append("ACTION_POSTURE_CLAMPED:STEP_UP_ONLY")
    return action_kind, reasons


def _decision_reason_codes(
    *,
    context_result: DecisionContextResult,
    registry_result: RegistryResolutionResult,
) -> list[str]:
    codes = []
    codes.extend(str(item) for item in context_result.reasons)
    codes.extend(str(item) for item in registry_result.reason_codes)
    return [item for item in codes if item]


def _degrade_posture_payload(posture: DfPostureStamp) -> dict[str, Any]:
    return {
        "mode": posture.mode,
        "capabilities_mask": {
            "allow_ieg": posture.capabilities_mask.allow_ieg,
            "allowed_feature_groups": sorted(posture.capabilities_mask.allowed_feature_groups),
            "allow_model_primary": posture.capabilities_mask.allow_model_primary,
            "allow_model_stage2": posture.capabilities_mask.allow_model_stage2,
            "allow_fallback_heuristics": posture.capabilities_mask.allow_fallback_heuristics,
            "action_posture": posture.capabilities_mask.action_posture,
        },
        "policy_rev": posture.policy_rev.as_dict(),
        "posture_seq": posture.posture_seq,
        "decided_at_utc": posture.decided_at_utc,
        "reason": ";".join(sorted(set(posture.reasons))),
    }


def _decision_eb_offset_basis(candidate: DecisionTriggerCandidate, context_result: DecisionContextResult) -> dict[str, Any]:
    if context_result.evidence.ofp_eb_offset_basis:
        return _normalize_eb_offset_basis(context_result.evidence.ofp_eb_offset_basis)
    return {
        "stream": candidate.source_eb_ref.topic,
        "offset_kind": candidate.source_eb_ref.offset_kind,
        "offsets": [{"partition": int(candidate.source_eb_ref.partition), "offset": str(candidate.source_eb_ref.offset)}],
        "basis_digest": hashlib.sha256(
            _canonical_json(
                {
                    "topic": candidate.source_eb_ref.topic,
                    "partition": candidate.source_eb_ref.partition,
                    "offset": candidate.source_eb_ref.offset,
                    "offset_kind": candidate.source_eb_ref.offset_kind,
                }
            ).encode("utf-8")
        ).hexdigest(),
        "window_start_utc": candidate.source_ts_utc,
        "window_end_utc": candidate.source_ts_utc,
    }


def _decision_graph_version(candidate: DecisionTriggerCandidate, context_result: DecisionContextResult) -> dict[str, Any]:
    graph = context_result.graph_version or context_result.evidence.graph_version
    if isinstance(graph, Mapping) and graph.get("version_id") and graph.get("watermark_ts_utc"):
        payload = {
            "version_id": str(graph.get("version_id")),
            "watermark_ts_utc": str(graph.get("watermark_ts_utc")),
        }
        if graph.get("stream"):
            payload["stream"] = str(graph.get("stream"))
        if graph.get("basis_digest"):
            payload["basis_digest"] = str(graph.get("basis_digest"))
        if graph.get("computed_at_utc"):
            payload["computed_at_utc"] = str(graph.get("computed_at_utc"))
        return payload
    return {
        "version_id": "0" * 32,
        "stream": candidate.source_eb_ref.topic,
        "basis_digest": hashlib.sha256(candidate.source_event_id.encode("utf-8")).hexdigest(),
        "watermark_ts_utc": candidate.source_ts_utc,
    }


def _snapshot_hash(context_result: DecisionContextResult) -> str:
    if context_result.evidence.ofp_snapshot_hash:
        return str(context_result.evidence.ofp_snapshot_hash)
    return hashlib.sha256(context_result.evidence.digest().encode("utf-8")).hexdigest()


def _source_event_payload(candidate: DecisionTriggerCandidate) -> dict[str, Any]:
    origin_offset = {
        "topic": candidate.source_eb_ref.topic,
        "partition": int(candidate.source_eb_ref.partition),
        "offset": str(candidate.source_eb_ref.offset),
        "offset_kind": candidate.source_eb_ref.offset_kind,
    }
    return {
        "event_id": candidate.source_event_id,
        "event_type": candidate.source_event_type,
        "ts_utc": candidate.source_ts_utc,
        "origin_offset": origin_offset,
        "eb_ref": candidate.source_eb_ref.as_dict(),
    }


def _normalize_pins(pins: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "manifest_fingerprint",
        "parameter_hash",
        "seed",
        "scenario_id",
        "platform_run_id",
        "scenario_run_id",
    )
    payload: dict[str, Any] = {}
    for key in required:
        if key not in pins:
            raise DecisionFabricSynthesisError(f"missing pin: {key}")
        value = pins.get(key)
        if value in (None, ""):
            raise DecisionFabricSynthesisError(f"empty pin: {key}")
        payload[key] = value
    if "run_id" in pins and pins.get("run_id") not in (None, ""):
        payload["run_id"] = pins.get("run_id")
    return payload


def _origin_offset_from_candidate(candidate: DecisionTriggerCandidate) -> dict[str, Any]:
    return {
        "topic": candidate.source_eb_ref.topic,
        "partition": int(candidate.source_eb_ref.partition),
        "offset": str(candidate.source_eb_ref.offset),
        "offset_kind": str(candidate.source_eb_ref.offset_kind),
    }


def _origin_offset_from_source_event(source_event: Any) -> dict[str, Any]:
    source_payload = source_event if isinstance(source_event, Mapping) else {}
    origin_offset = source_payload.get("origin_offset")
    if isinstance(origin_offset, Mapping):
        return {
            "topic": str(origin_offset.get("topic") or origin_offset.get("stream") or ""),
            "partition": int(origin_offset.get("partition", 0)),
            "offset": str(origin_offset.get("offset") or ""),
            "offset_kind": str(origin_offset.get("offset_kind") or ""),
        }
    eb_ref = source_payload.get("eb_ref") if isinstance(source_payload.get("eb_ref"), Mapping) else {}
    return {
        "topic": str(eb_ref.get("topic") or ""),
        "partition": int(eb_ref.get("partition", 0)),
        "offset": str(eb_ref.get("offset") or ""),
        "offset_kind": str(eb_ref.get("offset_kind") or ""),
    }


def _normalize_bundle_ref(bundle_ref: Mapping[str, Any] | None) -> dict[str, Any]:
    if bundle_ref is None:
        return {
            "bundle_id": "0" * 64,
            "registry_ref": "registry://fail_closed",
            "bundle_version": "fail_closed",
        }
    bundle_id = str(bundle_ref.get("bundle_id") or "").strip()
    if not bundle_id:
        bundle_id = "0" * 64
    payload = {"bundle_id": bundle_id}
    if bundle_ref.get("registry_ref"):
        payload["registry_ref"] = str(bundle_ref.get("registry_ref"))
    if bundle_ref.get("bundle_version"):
        payload["bundle_version"] = str(bundle_ref.get("bundle_version"))
    return payload


def _normalize_eb_offset_basis(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DecisionFabricSynthesisError("eb_offset_basis must be a mapping")
    stream = str(value.get("stream") or "").strip()
    offset_kind = str(value.get("offset_kind") or "").strip()
    offsets_raw = value.get("offsets")
    if not stream or not offset_kind or not isinstance(offsets_raw, list) or not offsets_raw:
        raise DecisionFabricSynthesisError("eb_offset_basis requires stream, offset_kind, non-empty offsets")
    offsets = []
    for item in offsets_raw:
        if not isinstance(item, Mapping):
            continue
        offsets.append(
            {
                "partition": int(item.get("partition", 0)),
                "offset": str(item.get("offset") or ""),
            }
        )
    offsets = sorted(offsets, key=lambda item: (item["partition"], item["offset"]))
    payload = {
        "stream": stream,
        "offset_kind": offset_kind,
        "offsets": offsets,
    }
    if value.get("basis_digest"):
        payload["basis_digest"] = str(value.get("basis_digest"))
    else:
        payload["basis_digest"] = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    if value.get("window_start_utc"):
        payload["window_start_utc"] = str(value.get("window_start_utc"))
    if value.get("window_end_utc"):
        payload["window_end_utc"] = str(value.get("window_end_utc"))
    return payload


def _canonical_envelope(
    *,
    event_id: str,
    event_type: str,
    schema_version: str,
    ts_utc: str,
    pins: Mapping[str, Any],
    payload: Mapping[str, Any],
    parent_event_id: str,
    producer: str,
) -> dict[str, Any]:
    envelope = {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": schema_version,
        "ts_utc": ts_utc,
        "manifest_fingerprint": pins.get("manifest_fingerprint"),
        "parameter_hash": pins.get("parameter_hash"),
        "seed": pins.get("seed"),
        "scenario_id": pins.get("scenario_id"),
        "platform_run_id": pins.get("platform_run_id"),
        "scenario_run_id": pins.get("scenario_run_id"),
        "producer": producer,
        "parent_event_id": parent_event_id,
        "payload": dict(payload),
    }
    if pins.get("run_id") not in (None, ""):
        envelope["run_id"] = pins.get("run_id")
    return envelope


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
