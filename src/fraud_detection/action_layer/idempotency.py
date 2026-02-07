"""Action Layer semantic idempotency gate (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from .contracts import ActionIntent, build_semantic_idempotency_key
from .storage import ActionLedgerStore


AL_EXECUTE = "EXECUTE"
AL_DROP_DUPLICATE = "DROP_DUPLICATE"
AL_QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class ActionIdempotencyDecision:
    disposition: str
    ledger_status: str
    semantic_key: str
    payload_hash: str
    reason_code: str


def build_action_payload_hash(payload: Mapping[str, Any]) -> str:
    normalized = dict(payload)
    pins = dict(normalized.get("pins") or {})
    identity = {
        "action_id": normalized.get("action_id"),
        "decision_id": normalized.get("decision_id"),
        "action_kind": normalized.get("action_kind"),
        "idempotency_key": normalized.get("idempotency_key"),
        "actor_principal": normalized.get("actor_principal"),
        "origin": normalized.get("origin"),
        "policy_rev": normalized.get("policy_rev"),
        "run_config_digest": normalized.get("run_config_digest"),
        "pins": {
            "platform_run_id": pins.get("platform_run_id"),
            "scenario_run_id": pins.get("scenario_run_id"),
            "manifest_fingerprint": pins.get("manifest_fingerprint"),
            "parameter_hash": pins.get("parameter_hash"),
            "scenario_id": pins.get("scenario_id"),
            "seed": pins.get("seed"),
        },
        "action_payload": normalized.get("action_payload"),
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ActionIdempotencyGate:
    def __init__(self, *, store: ActionLedgerStore) -> None:
        self.store = store

    def evaluate(
        self,
        *,
        intent: ActionIntent,
        first_seen_at_utc: str | None = None,
    ) -> ActionIdempotencyDecision:
        payload = intent.as_dict()
        pins = dict(payload["pins"])
        semantic_key = build_semantic_idempotency_key(payload)
        payload_hash = build_action_payload_hash(payload)
        seen_ts = first_seen_at_utc or datetime.now(tz=timezone.utc).isoformat()

        write = self.store.register_semantic_intent(
            platform_run_id=str(pins["platform_run_id"]),
            scenario_run_id=str(pins["scenario_run_id"]),
            semantic_key=semantic_key,
            idempotency_key=intent.idempotency_key,
            action_id=intent.action_id,
            decision_id=intent.decision_id,
            payload_hash=payload_hash,
            first_seen_at_utc=seen_ts,
        )
        if write.status == "NEW":
            return ActionIdempotencyDecision(
                disposition=AL_EXECUTE,
                ledger_status=write.status,
                semantic_key=semantic_key,
                payload_hash=payload_hash,
                reason_code="NEW_SEMANTIC_INTENT",
            )
        if write.status == "DUPLICATE":
            return ActionIdempotencyDecision(
                disposition=AL_DROP_DUPLICATE,
                ledger_status=write.status,
                semantic_key=semantic_key,
                payload_hash=payload_hash,
                reason_code="SEMANTIC_DUPLICATE",
            )
        return ActionIdempotencyDecision(
            disposition=AL_QUARANTINE,
            ledger_status=write.status,
            semantic_key=semantic_key,
            payload_hash=payload_hash,
            reason_code="SEMANTIC_PAYLOAD_HASH_MISMATCH",
        )

