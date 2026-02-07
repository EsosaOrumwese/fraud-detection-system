"""DL serving boundary (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .config import DlPolicyProfile
from .contracts import CapabilitiesMask, DegradeDecision, PolicyRev
from .store import DlCurrentPosture, DlPostureStore, DlPostureStoreError


class DlServeError(ValueError):
    """Raised when serving inputs are invalid."""


@dataclass(frozen=True)
class DlServeResult:
    scope_key: str
    decision: DegradeDecision
    source: str
    trust_state: str
    served_at_utc: str
    decision_time_utc: str
    record_updated_at_utc: str | None
    age_seconds: int | None
    is_stale: bool
    staleness_reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope_key": self.scope_key,
            "decision": self.decision.as_dict(),
            "source": self.source,
            "trust_state": self.trust_state,
            "served_at_utc": self.served_at_utc,
            "decision_time_utc": self.decision_time_utc,
            "record_updated_at_utc": self.record_updated_at_utc,
            "age_seconds": self.age_seconds,
            "is_stale": self.is_stale,
            "staleness_reason": self.staleness_reason,
        }


@dataclass
class DlCurrentPostureService:
    store: DlPostureStore
    fallback_profile: DlPolicyProfile | None = None
    fallback_policy_rev: PolicyRev | None = None

    def get_current_posture(
        self,
        *,
        scope_key: str,
        decision_time_utc: str,
        max_age_seconds: int,
    ) -> DlServeResult:
        normalized_scope = _normalize_scope(scope_key)
        decision_dt = _parse_utc(decision_time_utc, field_name="decision_time_utc")
        if not isinstance(max_age_seconds, int) or max_age_seconds <= 0:
            raise DlServeError("max_age_seconds must be a positive integer")

        served_at_utc = _utc_now()
        try:
            record = self.store.read_current(scope_key=normalized_scope)
        except DlPostureStoreError as exc:
            return self._fail_closed_result(
                scope_key=normalized_scope,
                decision_time_utc=decision_time_utc,
                served_at_utc=served_at_utc,
                trust_state="UNTRUSTED",
                source="FAILSAFE_STORE_ERROR",
                staleness_reason=f"STORE_ERROR:{exc}",
                age_seconds=None,
                record=None,
            )

        if record is None:
            return self._fail_closed_result(
                scope_key=normalized_scope,
                decision_time_utc=decision_time_utc,
                served_at_utc=served_at_utc,
                trust_state="MISSING",
                source="FAILSAFE_MISSING",
                staleness_reason="POSTURE_MISSING",
                age_seconds=None,
                record=None,
            )

        try:
            decided_dt = _parse_utc(record.decision.decided_at_utc, field_name="decision.decided_at_utc")
        except DlServeError:
            return self._fail_closed_result(
                scope_key=normalized_scope,
                decision_time_utc=decision_time_utc,
                served_at_utc=served_at_utc,
                trust_state="UNTRUSTED",
                source="FAILSAFE_STORE_ERROR",
                staleness_reason="POSTURE_DECISION_TIME_INVALID",
                age_seconds=None,
                record=record,
            )

        age_seconds = int((decision_dt - decided_dt).total_seconds())
        is_stale = age_seconds > max_age_seconds
        if is_stale:
            return self._fail_closed_result(
                scope_key=normalized_scope,
                decision_time_utc=decision_time_utc,
                served_at_utc=served_at_utc,
                trust_state="TRUSTED",
                source="FAILSAFE_STALE",
                staleness_reason=f"POSTURE_STALE:{age_seconds}s>{max_age_seconds}s",
                age_seconds=age_seconds,
                record=record,
            )

        return DlServeResult(
            scope_key=normalized_scope,
            decision=record.decision,
            source="CURRENT_POSTURE",
            trust_state="TRUSTED",
            served_at_utc=served_at_utc,
            decision_time_utc=decision_time_utc,
            record_updated_at_utc=record.updated_at_utc,
            age_seconds=age_seconds,
            is_stale=False,
            staleness_reason=None,
        )

    def _fail_closed_result(
        self,
        *,
        scope_key: str,
        decision_time_utc: str,
        served_at_utc: str,
        trust_state: str,
        source: str,
        staleness_reason: str,
        age_seconds: int | None,
        record: DlCurrentPosture | None,
    ) -> DlServeResult:
        fallback_decision = DegradeDecision(
            mode="FAIL_CLOSED",
            capabilities_mask=self._fallback_mask(record),
            policy_rev=self._fallback_policy_rev(record),
            posture_seq=self._fallback_posture_seq(record),
            decided_at_utc=decision_time_utc,
            reason=f"DL_SERVE_FAILSAFE:{staleness_reason}",
            evidence_refs=self._fallback_evidence_refs(record, staleness_reason),
        )
        return DlServeResult(
            scope_key=scope_key,
            decision=fallback_decision,
            source=source,
            trust_state=trust_state,
            served_at_utc=served_at_utc,
            decision_time_utc=decision_time_utc,
            record_updated_at_utc=None if record is None else record.updated_at_utc,
            age_seconds=age_seconds,
            is_stale=source == "FAILSAFE_STALE",
            staleness_reason=staleness_reason,
        )

    def _fallback_mask(self, record: DlCurrentPosture | None) -> CapabilitiesMask:
        if self.fallback_profile is not None and "FAIL_CLOSED" in self.fallback_profile.modes:
            return self.fallback_profile.modes["FAIL_CLOSED"].capabilities_mask
        if record is not None and record.decision.mode == "FAIL_CLOSED":
            return record.decision.capabilities_mask
        return CapabilitiesMask(
            allow_ieg=False,
            allowed_feature_groups=(),
            allow_model_primary=False,
            allow_model_stage2=False,
            allow_fallback_heuristics=True,
            action_posture="STEP_UP_ONLY",
        )

    def _fallback_policy_rev(self, record: DlCurrentPosture | None) -> PolicyRev:
        if self.fallback_policy_rev is not None:
            return self.fallback_policy_rev
        if record is not None:
            return record.decision.policy_rev
        return PolicyRev(policy_id="dl.policy.fail_closed", revision="fallback")

    def _fallback_posture_seq(self, record: DlCurrentPosture | None) -> int:
        if record is None:
            return 0
        return max(0, int(record.decision.posture_seq))

    def _fallback_evidence_refs(
        self,
        record: DlCurrentPosture | None,
        staleness_reason: str,
    ) -> tuple[dict[str, str], ...]:
        refs: list[dict[str, str]] = [{"kind": "dl_serve_reason", "ref": staleness_reason}]
        if record is not None:
            refs.append({"kind": "dl_scope_key", "ref": record.scope_key})
            refs.append({"kind": "dl_record_updated_at", "ref": record.updated_at_utc})
        return tuple(refs)


def _parse_utc(value: str, *, field_name: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise DlServeError(f"{field_name} must be non-empty")
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DlServeError(f"{field_name} must be RFC3339-ish UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise DlServeError(f"{field_name} must include timezone information")
    return dt.astimezone(timezone.utc)


def _normalize_scope(scope_key: str) -> str:
    normalized = str(scope_key).strip()
    if not normalized:
        raise DlServeError("scope_key must be non-empty")
    return normalized


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
