"""Action Layer IG publish boundary helpers (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import time
from typing import Any, Mapping

import requests

from fraud_detection.ingestion_gate.schemas import SchemaRegistry

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
        "ts_utc": str(payload["completed_at_utc"]),
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

