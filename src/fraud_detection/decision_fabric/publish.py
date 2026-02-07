"""Decision Fabric IG publish boundary helpers (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import time
from typing import Any, Mapping

import requests

from fraud_detection.ingestion_gate.schemas import SchemaRegistry


PUBLISH_ADMIT = "ADMIT"
PUBLISH_DUPLICATE = "DUPLICATE"
PUBLISH_QUARANTINE = "QUARANTINE"
PUBLISH_DECISIONS = {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE}


class DecisionFabricPublishError(ValueError):
    """Raised when DF cannot publish safely through IG."""


@dataclass(frozen=True)
class PublishedRecord:
    event_id: str
    event_type: str
    decision: str
    receipt: dict[str, Any]
    receipt_ref: str | None


@dataclass(frozen=True)
class PublishBatchResult:
    decision_record: PublishedRecord
    action_records: tuple[PublishedRecord, ...]
    halted: bool
    halt_reason: str | None = None


@dataclass
class DecisionFabricIgPublisher:
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
            raise DecisionFabricPublishError("max_attempts must be >= 1")
        if self.retry_base_delay_ms < 0 or self.retry_max_delay_ms < 0:
            raise DecisionFabricPublishError("retry delays must be >= 0")
        self._schema_registry = SchemaRegistry(Path(self.engine_contracts_root))
        self._session = self.session or requests.Session()

    def publish_decision_and_intents(
        self,
        *,
        decision_envelope: Mapping[str, Any],
        action_envelopes: tuple[Mapping[str, Any], ...],
    ) -> PublishBatchResult:
        decision_record = self.publish_envelope(decision_envelope)
        if decision_record.decision == PUBLISH_QUARANTINE:
            return PublishBatchResult(
                decision_record=decision_record,
                action_records=tuple(),
                halted=True,
                halt_reason="DECISION_QUARANTINED",
            )
        action_records: list[PublishedRecord] = []
        for envelope in action_envelopes:
            record = self.publish_envelope(envelope)
            action_records.append(record)
            if record.decision == PUBLISH_QUARANTINE:
                return PublishBatchResult(
                    decision_record=decision_record,
                    action_records=tuple(action_records),
                    halted=True,
                    halt_reason="ACTION_QUARANTINED",
                )
        return PublishBatchResult(
            decision_record=decision_record,
            action_records=tuple(action_records),
            halted=False,
            halt_reason=None,
        )

    def publish_envelope(self, envelope: Mapping[str, Any]) -> PublishedRecord:
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
                    raise DecisionFabricPublishError(
                        f"IG_PUSH_REJECTED:{response.status_code}:{_response_text(response)}"
                    )
            if attempt >= self.max_attempts or not retryable:
                raise DecisionFabricPublishError(f"IG_PUSH_RETRY_EXHAUSTED:{last_error}")
            self._sleep_backoff(attempt)
        raise DecisionFabricPublishError(f"IG_PUSH_RETRY_EXHAUSTED:{last_error}")

    def _parse_publish_response(
        self,
        envelope: Mapping[str, Any],
        response: Any,
    ) -> PublishedRecord:
        try:
            body = response.json()
        except Exception as exc:  # pragma: no cover - defensive
            raise DecisionFabricPublishError(f"IG_RESPONSE_INVALID_JSON:{exc}") from exc
        if not isinstance(body, Mapping):
            raise DecisionFabricPublishError("IG_RESPONSE_INVALID_SHAPE")
        decision = str(body.get("decision") or "").strip().upper()
        if decision not in PUBLISH_DECISIONS:
            raise DecisionFabricPublishError(f"IG_DECISION_UNKNOWN:{decision}")
        receipt_raw = body.get("receipt")
        receipt = dict(receipt_raw) if isinstance(receipt_raw, Mapping) else {}
        receipt_ref_raw = body.get("receipt_ref")
        receipt_ref = str(receipt_ref_raw).strip() if isinstance(receipt_ref_raw, str) and receipt_ref_raw.strip() else None
        return PublishedRecord(
            event_id=str(envelope.get("event_id") or ""),
            event_type=str(envelope.get("event_type") or ""),
            decision=decision,
            receipt=receipt,
            receipt_ref=receipt_ref,
        )

    def _validate_envelope(self, envelope: Mapping[str, Any]) -> None:
        try:
            self._schema_registry.validate("canonical_event_envelope.schema.yaml", dict(envelope))
        except Exception as exc:
            raise DecisionFabricPublishError(f"CANONICAL_ENVELOPE_INVALID:{exc}") from exc

    def _sleep_backoff(self, attempt: int) -> None:
        base = max(0.0, self.retry_base_delay_ms / 1000.0)
        cap = max(base, self.retry_max_delay_ms / 1000.0)
        delay = min(cap, base * (2 ** max(0, attempt - 1)))
        jitter = random.uniform(0.0, delay) if delay > 0 else 0.0
        time.sleep(delay + jitter)


def _response_text(response: Any) -> str:
    value = getattr(response, "text", "")
    text = str(value or "").strip()
    return text[:256]
