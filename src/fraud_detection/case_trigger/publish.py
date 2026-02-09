"""CaseTrigger IG publish corridor helpers (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import random
import time
from typing import Any, Mapping

import requests

from fraud_detection.case_mgmt.contracts import CaseTrigger
from fraud_detection.ingestion_gate.schemas import SchemaRegistry

from .storage import CaseTriggerPublishStore


CASE_TRIGGER_EVENT_TYPE = "case_trigger"
CASE_TRIGGER_SCHEMA_VERSION = "v1"

PUBLISH_ADMIT = "ADMIT"
PUBLISH_DUPLICATE = "DUPLICATE"
PUBLISH_QUARANTINE = "QUARANTINE"
PUBLISH_AMBIGUOUS = "AMBIGUOUS"
PUBLISH_DECISIONS = {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE}
PUBLISH_TERMINALS = {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE, PUBLISH_AMBIGUOUS}


class CaseTriggerPublishError(ValueError):
    """Raised when CaseTrigger cannot publish safely through IG."""


@dataclass(frozen=True)
class PublishedCaseTriggerRecord:
    case_trigger_id: str
    event_id: str
    event_type: str
    decision: str
    receipt: dict[str, Any]
    receipt_ref: str | None
    reason_code: str | None = None
    actor_principal: str | None = None
    actor_source_type: str | None = None


@dataclass
class CaseTriggerIgPublisher:
    ig_ingest_url: str
    api_key: str | None = None
    api_key_header: str = "X-IG-Api-Key"
    timeout_seconds: float = 30.0
    max_attempts: int = 5
    retry_base_delay_ms: int = 100
    retry_max_delay_ms: int = 5000
    session: requests.Session | None = None
    publish_store: CaseTriggerPublishStore | None = None
    require_auth_token: bool = True
    actor_source_type: str = "SYSTEM"
    engine_contracts_root: Path | str = "docs/model_spec/data-engine/interface_pack/contracts"

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise CaseTriggerPublishError("max_attempts must be >= 1")
        if self.retry_base_delay_ms < 0 or self.retry_max_delay_ms < 0:
            raise CaseTriggerPublishError("retry delays must be >= 0")
        if self.require_auth_token and not str(self.api_key or "").strip():
            raise CaseTriggerPublishError("auth token is required for CaseTrigger publish corridor attribution")
        self._schema_registry = SchemaRegistry(Path(self.engine_contracts_root))
        self._session = self.session or requests.Session()

    def publish_case_trigger(
        self,
        trigger: CaseTrigger,
        *,
        producer: str = "case_trigger",
    ) -> PublishedCaseTriggerRecord:
        actor_principal = _actor_principal_from_token(self.api_key)
        envelope = build_case_trigger_envelope(
            trigger,
            producer=producer,
        )
        record = self.publish_envelope(envelope)
        annotated = PublishedCaseTriggerRecord(
            case_trigger_id=trigger.case_trigger_id,
            event_id=record.event_id,
            event_type=record.event_type,
            decision=record.decision,
            receipt=record.receipt,
            receipt_ref=record.receipt_ref,
            reason_code=record.reason_code,
            actor_principal=actor_principal,
            actor_source_type=self.actor_source_type,
        )
        if self.publish_store is not None:
            self.publish_store.register_publish_result(
                case_trigger_id=trigger.case_trigger_id,
                event_id=annotated.event_id,
                event_type=annotated.event_type,
                publish_decision=annotated.decision,
                receipt=annotated.receipt,
                receipt_ref=annotated.receipt_ref,
                reason_code=annotated.reason_code,
                actor_principal=actor_principal,
                actor_source_type=self.actor_source_type,
                published_at_utc=_utc_now(),
            )
        return annotated

    def publish_envelope(self, envelope: Mapping[str, Any]) -> PublishedCaseTriggerRecord:
        payload = dict(envelope)
        self._validate_envelope(payload)

        url = self.ig_ingest_url.rstrip("/") + "/v1/ingest/push"
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
                    raise CaseTriggerPublishError(
                        f"IG_PUSH_REJECTED:{response.status_code}:{_response_text(response)}"
                    )

            if attempt >= self.max_attempts or not retryable:
                return PublishedCaseTriggerRecord(
                    case_trigger_id=str((payload.get("payload") or {}).get("case_trigger_id") or payload.get("event_id") or ""),
                    event_id=str(payload.get("event_id") or ""),
                    event_type=str(payload.get("event_type") or ""),
                    decision=PUBLISH_AMBIGUOUS,
                    receipt={},
                    receipt_ref=None,
                    reason_code=f"IG_PUSH_RETRY_EXHAUSTED:{last_error}",
                )
            self._sleep_backoff(attempt)

        return PublishedCaseTriggerRecord(
            case_trigger_id=str((payload.get("payload") or {}).get("case_trigger_id") or payload.get("event_id") or ""),
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
    ) -> PublishedCaseTriggerRecord:
        try:
            body = response.json()
        except Exception as exc:  # pragma: no cover - defensive
            raise CaseTriggerPublishError(f"IG_RESPONSE_INVALID_JSON:{exc}") from exc
        if not isinstance(body, Mapping):
            raise CaseTriggerPublishError("IG_RESPONSE_INVALID_SHAPE")
        decision = str(body.get("decision") or "").strip().upper()
        if decision not in PUBLISH_DECISIONS:
            raise CaseTriggerPublishError(f"IG_DECISION_UNKNOWN:{decision}")
        receipt_raw = body.get("receipt")
        receipt = dict(receipt_raw) if isinstance(receipt_raw, Mapping) else {}
        receipt_ref_raw = body.get("receipt_ref")
        receipt_ref = str(receipt_ref_raw).strip() if isinstance(receipt_ref_raw, str) and receipt_ref_raw.strip() else None
        return PublishedCaseTriggerRecord(
            case_trigger_id=str((envelope.get("payload") or {}).get("case_trigger_id") or envelope.get("event_id") or ""),
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
            raise CaseTriggerPublishError(f"CANONICAL_ENVELOPE_INVALID:{exc}") from exc

    def _sleep_backoff(self, attempt: int) -> None:
        base = max(0.0, self.retry_base_delay_ms / 1000.0)
        cap = max(base, self.retry_max_delay_ms / 1000.0)
        delay = min(cap, base * (2 ** max(0, attempt - 1)))
        jitter = random.uniform(0.0, delay) if delay > 0 else 0.0
        time.sleep(delay + jitter)


def build_case_trigger_envelope(
    trigger: CaseTrigger,
    *,
    producer: str = "case_trigger",
) -> dict[str, Any]:
    payload = trigger.as_dict()
    pins = dict(payload.get("pins") or {})
    manifest_fingerprint = str(pins.get("manifest_fingerprint") or "").strip()
    parameter_hash = str(pins.get("parameter_hash") or "").strip()
    scenario_id = str(pins.get("scenario_id") or "").strip()
    platform_run_id = str(pins.get("platform_run_id") or "").strip()
    scenario_run_id = str(pins.get("scenario_run_id") or "").strip()
    if not manifest_fingerprint or not parameter_hash or not scenario_id or not platform_run_id or not scenario_run_id:
        raise CaseTriggerPublishError("CaseTrigger pins missing required envelope fields")

    seed_raw = pins.get("seed")
    if seed_raw in (None, ""):
        raise CaseTriggerPublishError("CaseTrigger pins.seed is required")
    seed = int(seed_raw)

    ts_utc = _canonicalize_utc_timestamp(
        payload.get("observed_time"),
        field_name="payload.observed_time",
    )

    envelope: dict[str, Any] = {
        "event_id": str(payload.get("case_trigger_id") or ""),
        "event_type": CASE_TRIGGER_EVENT_TYPE,
        "schema_version": CASE_TRIGGER_SCHEMA_VERSION,
        "ts_utc": ts_utc,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "seed": seed,
        "scenario_id": scenario_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "parent_event_id": str(payload.get("source_ref_id") or ""),
        "producer": str(producer or "").strip() or "case_trigger",
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


def _canonicalize_utc_timestamp(value: Any, *, field_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise CaseTriggerPublishError(f"{field_name} is required")

    parse_input = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(parse_input)
    except ValueError as exc:
        raise CaseTriggerPublishError(f"{field_name} must be an ISO-8601 timestamp") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _actor_principal_from_token(token: str | None) -> str:
    raw = str(token or "").strip()
    if not raw:
        return "SYSTEM::ANONYMOUS"
    upper = raw.upper()
    if upper.startswith("SYSTEM::") or upper.startswith("HUMAN::"):
        return raw
    if raw.startswith("st.v1."):
        return "SYSTEM::SERVICE_TOKEN"
    return f"SYSTEM::{raw}"


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
