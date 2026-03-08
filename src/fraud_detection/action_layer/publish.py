"""Action Layer IG publish boundary helpers (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import random
import time
from typing import Any, Mapping

import requests

from fraud_detection.ingestion_gate.schemas import SchemaRegistry
from fraud_detection.platform_internal_publish import (
    InternalCanonicalEventPublisher,
    InternalEventPublishError,
)

from .contracts import ActionOutcome


ACTION_OUTCOME_EVENT_TYPE = "action_outcome"
ACTION_OUTCOME_SCHEMA_VERSION = "v1"

PUBLISH_ADMIT = "ADMIT"
PUBLISH_DUPLICATE = "DUPLICATE"
PUBLISH_QUARANTINE = "QUARANTINE"
PUBLISH_AMBIGUOUS = "AMBIGUOUS"
PUBLISH_DECISIONS = {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE}
PUBLISH_TERMINALS = {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE, PUBLISH_AMBIGUOUS}


class ActionLayerPublishError(ValueError):
    """Raised when AL cannot publish safely through IG."""


@dataclass(frozen=True)
class PublishedOutcomeRecord:
    outcome_id: str
    event_id: str
    event_type: str
    decision: str
    receipt: dict[str, Any]
    receipt_ref: str | None
    reason_code: str | None = None


@dataclass
class ActionLayerIgPublisher:
    ig_ingest_url: str
    api_key: str | None = None
    api_key_header: str = "X-IG-Api-Key"
    timeout_seconds: float = 30.0
    max_attempts: int = 5
    retry_base_delay_ms: int = 100
    retry_max_delay_ms: int = 5000
    session: requests.Session | None = None
    engine_contracts_root: Path | str = "docs/model_spec/data-engine/interface_pack/contracts"

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ActionLayerPublishError("max_attempts must be >= 1")
        if self.retry_base_delay_ms < 0 or self.retry_max_delay_ms < 0:
            raise ActionLayerPublishError("retry delays must be >= 0")
        self._schema_registry = SchemaRegistry(Path(self.engine_contracts_root))
        self._session = self.session or requests.Session()

    def publish_outcome(self, outcome: ActionOutcome) -> PublishedOutcomeRecord:
        envelope = build_action_outcome_envelope(outcome)
        return self.publish_envelope(envelope)

    def publish_envelope(self, envelope: Mapping[str, Any]) -> PublishedOutcomeRecord:
        payload = dict(envelope)
        self._validate_envelope(payload)

        url = _resolve_ig_push_url(self.ig_ingest_url)
        headers: dict[str, str] = {}
        if self.api_key:
            headers[self.api_key_header] = self.api_key

        last_error: str | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._session.post(url, json=payload, timeout=self.timeout_seconds, headers=headers)
            except requests.Timeout:
                last_error = "timeout"
                retryable = True
            except requests.RequestException as exc:
                last_error = str(exc)[:256]
                retryable = True
            else:
                if response.status_code < 400:
                    return self._parse_publish_response(payload, response)
                retryable = response.status_code in {408, 429} or response.status_code >= 500
                last_error = f"http_{response.status_code}"
                if not retryable:
                    raise ActionLayerPublishError(
                        f"IG_PUSH_REJECTED:{response.status_code}:{_response_text(response)}"
                    )

            if attempt >= self.max_attempts or not retryable:
                return PublishedOutcomeRecord(
                    outcome_id=str((payload.get("payload") or {}).get("outcome_id") or ""),
                    event_id=str(payload.get("event_id") or ""),
                    event_type=str(payload.get("event_type") or ""),
                    decision=PUBLISH_AMBIGUOUS,
                    receipt={},
                    receipt_ref=None,
                    reason_code=f"IG_PUSH_RETRY_EXHAUSTED:{last_error}",
                )
            self._sleep_backoff(attempt)

        return PublishedOutcomeRecord(
            outcome_id=str((payload.get("payload") or {}).get("outcome_id") or ""),
            event_id=str(payload.get("event_id") or ""),
            event_type=str(payload.get("event_type") or ""),
            decision=PUBLISH_AMBIGUOUS,
            receipt={},
            receipt_ref=None,
            reason_code=f"IG_PUSH_RETRY_EXHAUSTED:{last_error}",
        )

    def _parse_publish_response(
        self,
        envelope: Mapping[str, Any],
        response: Any,
    ) -> PublishedOutcomeRecord:
        try:
            body = response.json()
        except Exception as exc:  # pragma: no cover - defensive
            raise ActionLayerPublishError(f"IG_RESPONSE_INVALID_JSON:{exc}") from exc
        if not isinstance(body, Mapping):
            raise ActionLayerPublishError("IG_RESPONSE_INVALID_SHAPE")
        decision = str(body.get("decision") or "").strip().upper()
        if decision not in PUBLISH_DECISIONS:
            raise ActionLayerPublishError(f"IG_DECISION_UNKNOWN:{decision}")
        receipt_raw = body.get("receipt")
        receipt = dict(receipt_raw) if isinstance(receipt_raw, Mapping) else {}
        receipt_ref_raw = body.get("receipt_ref")
        receipt_ref = str(receipt_ref_raw).strip() if isinstance(receipt_ref_raw, str) and receipt_ref_raw.strip() else None
        return PublishedOutcomeRecord(
            outcome_id=str((envelope.get("payload") or {}).get("outcome_id") or ""),
            event_id=str(envelope.get("event_id") or ""),
            event_type=str(envelope.get("event_type") or ""),
            decision=decision,
            receipt=receipt,
            receipt_ref=receipt_ref,
            reason_code=None,
        )

    def _validate_envelope(self, envelope: Mapping[str, Any]) -> None:
        try:
            self._schema_registry.validate("canonical_event_envelope.schema.yaml", dict(envelope))
        except Exception as exc:
            raise ActionLayerPublishError(f"CANONICAL_ENVELOPE_INVALID:{exc}") from exc

    def _sleep_backoff(self, attempt: int) -> None:
        base = max(0.0, self.retry_base_delay_ms / 1000.0)
        cap = max(base, self.retry_max_delay_ms / 1000.0)
        delay = min(cap, base * (2 ** max(0, attempt - 1)))
        jitter = random.uniform(0.0, delay) if delay > 0 else 0.0
        time.sleep(delay + jitter)


def build_action_outcome_envelope(
    outcome: ActionOutcome,
    *,
    producer: str = "action_layer",
) -> dict[str, Any]:
    payload = outcome.as_dict()
    pins_raw = payload.get("pins")
    if not isinstance(pins_raw, Mapping):
        raise ActionLayerPublishError("ActionOutcome pins missing for envelope build")
    pins = dict(pins_raw)

    envelope: dict[str, Any] = {
        "event_id": str(payload["outcome_id"]),
        "event_type": ACTION_OUTCOME_EVENT_TYPE,
        "schema_version": ACTION_OUTCOME_SCHEMA_VERSION,
        "ts_utc": _canonicalize_utc_timestamp(
            payload.get("completed_at_utc"),
            field_name="payload.completed_at_utc",
        ),
        "manifest_fingerprint": str(pins["manifest_fingerprint"]),
        "parameter_hash": str(pins["parameter_hash"]),
        "seed": int(pins["seed"]),
        "scenario_id": str(pins["scenario_id"]),
        "platform_run_id": str(pins["platform_run_id"]),
        "scenario_run_id": str(pins["scenario_run_id"]),
        "parent_event_id": str(payload["decision_id"]),
        "producer": producer,
        "payload": payload,
    }
    run_id = pins.get("run_id")
    if run_id not in (None, ""):
        envelope["run_id"] = str(run_id)
    return envelope


def _response_text(response: Any) -> str:
    value = getattr(response, "text", "")
    text = str(value or "").strip()
    return text[:256]


def _resolve_ig_push_url(raw_url: str) -> str:
    base = str(raw_url or "").strip().rstrip("/")
    if not base:
        return "/v1/ingest/push"
    if base.endswith("/v1/ingest/push"):
        return base
    return f"{base}/v1/ingest/push"


def _canonicalize_utc_timestamp(value: Any, *, field_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ActionLayerPublishError(f"{field_name} is required")

    parse_input = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(parse_input)
    except ValueError as exc:
        raise ActionLayerPublishError(f"{field_name} must be an ISO-8601 timestamp") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass
class ActionLayerInternalPublisher:
    event_bus_kind: str
    event_bus_root: str
    event_bus_stream: str | None
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    class_map_ref: Path | str
    partitioning_profiles_ref: Path | str
    engine_contracts_root: Path | str = "docs/model_spec/data-engine/interface_pack/contracts"
    client_id: str = "al-internal-publisher"

    def __post_init__(self) -> None:
        self._publisher = InternalCanonicalEventPublisher(
            event_bus_kind=self.event_bus_kind,
            event_bus_root=self.event_bus_root,
            event_bus_stream=self.event_bus_stream,
            event_bus_region=self.event_bus_region,
            event_bus_endpoint_url=self.event_bus_endpoint_url,
            class_map_ref=self.class_map_ref,
            partitioning_profiles_ref=self.partitioning_profiles_ref,
            engine_contracts_root=self.engine_contracts_root,
            client_id=self.client_id,
        )

    def publish_outcome(self, outcome: ActionOutcome) -> PublishedOutcomeRecord:
        return self.publish_envelope(build_action_outcome_envelope(outcome))

    def publish_envelope(self, envelope: Mapping[str, Any]) -> PublishedOutcomeRecord:
        try:
            result = self._publisher.publish_envelope(envelope)
        except InternalEventPublishError as exc:
            raise ActionLayerPublishError(str(exc)) from exc
        return PublishedOutcomeRecord(
            outcome_id=str((envelope.get("payload") or {}).get("outcome_id") or ""),
            event_id=result.event_id,
            event_type=result.event_type,
            decision=PUBLISH_ADMIT,
            receipt={"eb_ref": _eb_ref_receipt(result.eb_ref)},
            receipt_ref=None,
            reason_code=None,
        )


def _eb_ref_receipt(eb_ref: Any) -> dict[str, Any]:
    payload = {
        "topic": str(getattr(eb_ref, "topic", "") or ""),
        "partition": getattr(eb_ref, "partition", None),
        "offset": str(getattr(eb_ref, "offset", "") or ""),
        "offset_kind": str(getattr(eb_ref, "offset_kind", "") or ""),
    }
    published_at_utc = str(getattr(eb_ref, "published_at_utc", "") or "").strip()
    if published_at_utc:
        payload["published_at_utc"] = published_at_utc
    return payload
