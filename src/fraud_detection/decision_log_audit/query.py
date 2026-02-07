"""Decision Log & Audit query/read contract surfaces (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .storage import DecisionLogAuditIntakeStore, DecisionLogAuditLineageChain


class DecisionLogAuditQueryError(ValueError):
    """Raised when DLA query/read requests are invalid or unauthorized."""


@dataclass(frozen=True)
class DecisionLogAuditReadAccessPolicy:
    allowed_platform_run_ids: tuple[str, ...] | None = None

    def ensure_allowed(self, *, platform_run_id: str) -> None:
        allowed = self.allowed_platform_run_ids
        if allowed is None:
            return
        if platform_run_id not in allowed:
            raise DecisionLogAuditQueryError(f"READ_ACCESS_DENIED:platform_run_id={platform_run_id}")


@dataclass(frozen=True)
class DecisionLogAuditLineageReadRecord:
    decision_id: str
    platform_run_id: str
    scenario_run_id: str
    chain_status: str
    unresolved_reasons: tuple[str, ...]
    intent_count: int
    outcome_count: int
    decision_event_id: str | None
    decision_payload_hash: str | None
    decision_ref: dict[str, Any] | None
    intent_refs: tuple[dict[str, Any], ...]
    outcome_refs: tuple[dict[str, Any], ...]
    created_at_utc: str
    updated_at_utc: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "chain_status": self.chain_status,
            "unresolved_reasons": list(self.unresolved_reasons),
            "intent_count": self.intent_count,
            "outcome_count": self.outcome_count,
            "decision_event_id": self.decision_event_id,
            "decision_payload_hash": self.decision_payload_hash,
            "decision_ref": dict(self.decision_ref) if isinstance(self.decision_ref, Mapping) else self.decision_ref,
            "intent_refs": [dict(item) for item in self.intent_refs],
            "outcome_refs": [dict(item) for item in self.outcome_refs],
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }


RedactionHook = Callable[[dict[str, Any]], Mapping[str, Any]]


class DecisionLogAuditQueryService:
    def __init__(
        self,
        *,
        store: DecisionLogAuditIntakeStore,
        access_policy: DecisionLogAuditReadAccessPolicy | None = None,
        redaction_hook: RedactionHook | None = None,
    ) -> None:
        self.store = store
        self.access_policy = access_policy or DecisionLogAuditReadAccessPolicy()
        self.redaction_hook = redaction_hook

    def query_run_scope(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        start_ts_utc: str | None = None,
        end_ts_utc: str | None = None,
        limit: int = 100,
    ) -> tuple[dict[str, Any], ...]:
        self.access_policy.ensure_allowed(platform_run_id=platform_run_id)
        if start_ts_utc and end_ts_utc and str(start_ts_utc) > str(end_ts_utc):
            raise DecisionLogAuditQueryError("INVALID_TIME_RANGE")
        chains = self.store.list_lineage_chains_by_run_scope(
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            start_ts_utc=start_ts_utc,
            end_ts_utc=end_ts_utc,
            limit=limit,
        )
        return tuple(self._serialize_chain(item) for item in chains)

    def query_decision_id(self, *, decision_id: str) -> dict[str, Any] | None:
        chain = self.store.get_lineage_chain(decision_id=decision_id)
        if chain is None:
            return None
        self.access_policy.ensure_allowed(platform_run_id=chain.platform_run_id)
        return self._serialize_chain(chain)

    def query_action_id(
        self,
        *,
        action_id: str,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[dict[str, Any], ...]:
        if platform_run_id:
            self.access_policy.ensure_allowed(platform_run_id=platform_run_id)
        chains = self.store.list_lineage_chains_by_action_id(
            action_id=action_id,
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            limit=limit,
        )
        records: list[dict[str, Any]] = []
        for chain in chains:
            self.access_policy.ensure_allowed(platform_run_id=chain.platform_run_id)
            records.append(self._serialize_chain(chain))
        return tuple(records)

    def query_outcome_id(
        self,
        *,
        outcome_id: str,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[dict[str, Any], ...]:
        if platform_run_id:
            self.access_policy.ensure_allowed(platform_run_id=platform_run_id)
        chains = self.store.list_lineage_chains_by_outcome_id(
            outcome_id=outcome_id,
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            limit=limit,
        )
        records: list[dict[str, Any]] = []
        for chain in chains:
            self.access_policy.ensure_allowed(platform_run_id=chain.platform_run_id)
            records.append(self._serialize_chain(chain))
        return tuple(records)

    def _serialize_chain(self, chain: DecisionLogAuditLineageChain) -> dict[str, Any]:
        intent_refs = tuple(
            {
                "action_id": item.action_id,
                "intent_event_id": item.intent_event_id,
                "payload_hash": item.payload_hash,
                "source_ref": dict(item.source_ref),
                "requested_at_utc": item.requested_at_utc,
                "created_at_utc": item.created_at_utc,
            }
            for item in self.store.list_lineage_intents(decision_id=chain.decision_id)
        )
        outcome_refs = tuple(
            {
                "outcome_id": item.outcome_id,
                "action_id": item.action_id,
                "outcome_event_id": item.outcome_event_id,
                "payload_hash": item.payload_hash,
                "status": item.status,
                "source_ref": dict(item.source_ref),
                "completed_at_utc": item.completed_at_utc,
                "created_at_utc": item.created_at_utc,
            }
            for item in self.store.list_lineage_outcomes(decision_id=chain.decision_id)
        )
        record = DecisionLogAuditLineageReadRecord(
            decision_id=chain.decision_id,
            platform_run_id=chain.platform_run_id,
            scenario_run_id=chain.scenario_run_id,
            chain_status=chain.chain_status,
            unresolved_reasons=chain.unresolved_reasons,
            intent_count=chain.intent_count,
            outcome_count=chain.outcome_count,
            decision_event_id=chain.decision_event_id,
            decision_payload_hash=chain.decision_payload_hash,
            decision_ref=chain.decision_ref,
            intent_refs=intent_refs,
            outcome_refs=outcome_refs,
            created_at_utc=chain.created_at_utc,
            updated_at_utc=chain.updated_at_utc,
        ).as_dict()
        return self._redact(record)

    def _redact(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.redaction_hook is None:
            return payload
        redacted = self.redaction_hook(dict(payload))
        if not isinstance(redacted, Mapping):
            raise DecisionLogAuditQueryError("REDACTION_HOOK_INVALID")
        return dict(redacted)
