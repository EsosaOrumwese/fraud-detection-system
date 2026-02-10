"""Decision Fabric DL posture integration and enforcement (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, DegradeDecision, MODE_SEQUENCE, PolicyRev
from fraud_detection.degrade_ladder.health import DlHealthGate
from fraud_detection.degrade_ladder.serve import DlGuardedPostureService, DlServeResult


_MODE_STRICTNESS_RANK = {
    "NORMAL": 0,
    "DEGRADED_1": 1,
    "DEGRADED_2": 2,
    "FAIL_CLOSED": 3,
}


class DfPostureError(ValueError):
    """Raised when DF posture wiring/enforcement inputs are invalid."""


@dataclass(frozen=True)
class DfPostureStamp:
    scope_key: str
    mode: str
    capabilities_mask: CapabilitiesMask
    policy_rev: PolicyRev
    posture_seq: int
    decided_at_utc: str
    source: str
    trust_state: str
    served_at_utc: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope_key": self.scope_key,
            "mode": self.mode,
            "capabilities_mask": self.capabilities_mask.as_dict(),
            "policy_rev": self.policy_rev.as_dict(),
            "posture_seq": self.posture_seq,
            "decided_at_utc": self.decided_at_utc,
            "source": self.source,
            "trust_state": self.trust_state,
            "served_at_utc": self.served_at_utc,
            "reasons": list(self.reasons),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DfPostureEnforcementResult:
    blocked: bool
    reasons: tuple[str, ...]
    allow_ieg: bool
    allowed_feature_groups: tuple[str, ...]
    allow_model_primary: bool
    allow_model_stage2: bool
    allow_fallback_heuristics: bool
    action_posture: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "reasons": list(self.reasons),
            "allow_ieg": self.allow_ieg,
            "allowed_feature_groups": list(self.allowed_feature_groups),
            "allow_model_primary": self.allow_model_primary,
            "allow_model_stage2": self.allow_model_stage2,
            "allow_fallback_heuristics": self.allow_fallback_heuristics,
            "action_posture": self.action_posture,
        }


@dataclass
class DfPostureTransitionGuard:
    """Maintain DF transition behavior compatible with DL anti-flap semantics."""

    min_relax_interval_seconds: int = 0

    def __post_init__(self) -> None:
        if self.min_relax_interval_seconds < 0:
            raise DfPostureError("min_relax_interval_seconds must be >= 0")
        self._last_by_scope: dict[str, DfPostureStamp] = {}

    def apply(self, incoming: DfPostureStamp) -> DfPostureStamp:
        previous = self._last_by_scope.get(incoming.scope_key)
        if previous is None:
            self._last_by_scope[incoming.scope_key] = incoming
            return incoming

        if _mode_rank(incoming.mode) > _mode_rank(previous.mode):
            self._last_by_scope[incoming.scope_key] = incoming
            return incoming

        if _mode_rank(incoming.mode) == _mode_rank(previous.mode):
            if incoming.posture_seq >= previous.posture_seq:
                self._last_by_scope[incoming.scope_key] = incoming
                return incoming
            held = _with_reason(previous, "RELAX_BLOCKED_NON_MONOTONIC_SEQ")
            self._last_by_scope[incoming.scope_key] = held
            return held

        if incoming.posture_seq <= previous.posture_seq:
            held = _with_reason(previous, "RELAX_BLOCKED_NON_MONOTONIC_SEQ")
            self._last_by_scope[incoming.scope_key] = held
            return held

        if self.min_relax_interval_seconds > 0:
            incoming_dt = _parse_utc(incoming.decided_at_utc)
            previous_dt = _parse_utc(previous.decided_at_utc)
            elapsed = int((incoming_dt - previous_dt).total_seconds())
            if elapsed < self.min_relax_interval_seconds:
                held = _with_reason(previous, "RELAX_BLOCKED_HOLD_DOWN")
                self._last_by_scope[incoming.scope_key] = held
                return held

        self._last_by_scope[incoming.scope_key] = incoming
        return incoming


@dataclass
class DfPostureResolver:
    guarded_service: DlGuardedPostureService
    max_age_seconds: int
    transition_guard: DfPostureTransitionGuard | None = None

    def resolve(
        self,
        *,
        scope_key: Any,
        decision_time_utc: str,
        policy_ok: bool,
        required_signals_ok: bool,
        store_ok: bool = True,
        serve_ok: bool = True,
        control_publish_ok: bool = True,
        reason_codes: tuple[str, ...] = (),
    ) -> DfPostureStamp:
        if not isinstance(self.max_age_seconds, int) or self.max_age_seconds <= 0:
            raise DfPostureError("max_age_seconds must be a positive integer")
        normalized_scope_key = _canonical_scope_key(scope_key)

        dl_result, gate = self.guarded_service.get_guarded_posture(
            scope_key=normalized_scope_key,
            decision_time_utc=decision_time_utc,
            max_age_seconds=self.max_age_seconds,
            policy_ok=policy_ok,
            required_signals_ok=required_signals_ok,
            store_ok=store_ok,
            serve_ok=serve_ok,
            control_publish_ok=control_publish_ok,
            reason_codes=reason_codes,
        )
        stamp = posture_stamp_from_dl(dl_result=dl_result, health_gate=gate)
        if self.transition_guard is None:
            return stamp
        return self.transition_guard.apply(stamp)


def posture_stamp_from_dl(
    *,
    dl_result: DlServeResult,
    health_gate: DlHealthGate | None = None,
) -> DfPostureStamp:
    decision = dl_result.decision
    if not isinstance(decision, DegradeDecision):
        return _fail_closed_stamp(
            scope_key=dl_result.scope_key,
            decided_at_utc=dl_result.decision_time_utc,
            source="DF_FAILSAFE_INVALID_DL_RESULT",
            trust_state=dl_result.trust_state,
            served_at_utc=dl_result.served_at_utc,
            reason_codes=("DL_POSTURE_INVALID:decision_type",),
        )

    if decision.mode not in MODE_SEQUENCE:
        return _fail_closed_stamp(
            scope_key=dl_result.scope_key,
            decided_at_utc=dl_result.decision_time_utc,
            source="DF_FAILSAFE_INVALID_DL_RESULT",
            trust_state=dl_result.trust_state,
            served_at_utc=dl_result.served_at_utc,
            reason_codes=(f"DL_POSTURE_INVALID:mode={decision.mode}",),
            posture_seq=decision.posture_seq,
            policy_rev=decision.policy_rev,
        )

    reasons: list[str] = [f"DL_SOURCE:{dl_result.source}", f"DL_TRUST:{dl_result.trust_state}"]
    if dl_result.staleness_reason:
        reasons.append(f"DL_STALENESS:{dl_result.staleness_reason}")
    if decision.reason:
        reasons.append(f"DL_REASON:{decision.reason}")
    if health_gate is not None:
        reasons.append(f"DL_HEALTH_STATE:{health_gate.state}")
        reasons.extend(f"DL_HEALTH_REASON:{code}" for code in health_gate.reason_codes)
    normalized_reasons = tuple(sorted(set(reasons)))

    return DfPostureStamp(
        scope_key=dl_result.scope_key,
        mode=decision.mode,
        capabilities_mask=decision.capabilities_mask,
        policy_rev=decision.policy_rev,
        posture_seq=decision.posture_seq,
        decided_at_utc=decision.decided_at_utc,
        source=dl_result.source,
        trust_state=dl_result.trust_state,
        served_at_utc=dl_result.served_at_utc,
        reasons=normalized_reasons,
    )


def enforce_posture_constraints(
    *,
    posture: DfPostureStamp,
    require_ieg: bool,
    requested_feature_groups: tuple[str, ...],
    require_model_primary: bool,
    require_model_stage2: bool,
    require_fallback_heuristics: bool,
    requested_action_posture: str,
) -> DfPostureEnforcementResult:
    reasons: list[str] = []
    mask = posture.capabilities_mask

    allow_ieg = bool(mask.allow_ieg)
    if require_ieg and not allow_ieg:
        reasons.append("CAPABILITY_BLOCK:allow_ieg")

    allowed_set = set(mask.allowed_feature_groups)
    requested = tuple(str(item).strip() for item in requested_feature_groups if str(item).strip())
    allowed_feature_groups = tuple(sorted(group for group in requested if group in allowed_set))
    missing = sorted(group for group in requested if group not in allowed_set)
    reasons.extend(f"CAPABILITY_BLOCK:feature_group={group}" for group in missing)

    allow_model_primary = bool(mask.allow_model_primary)
    if require_model_primary and not allow_model_primary:
        reasons.append("CAPABILITY_BLOCK:allow_model_primary")

    allow_model_stage2 = bool(mask.allow_model_stage2)
    if require_model_stage2 and not allow_model_stage2:
        reasons.append("CAPABILITY_BLOCK:allow_model_stage2")

    allow_fallback = bool(mask.allow_fallback_heuristics)
    if require_fallback_heuristics and not allow_fallback:
        reasons.append("CAPABILITY_BLOCK:allow_fallback_heuristics")

    requested_action = str(requested_action_posture or "").strip() or "NORMAL"
    action_posture = mask.action_posture
    if requested_action == "NORMAL" and action_posture == "STEP_UP_ONLY":
        reasons.append("CAPABILITY_BLOCK:action_posture")

    normalized_reasons = tuple(sorted(set(reasons)))
    return DfPostureEnforcementResult(
        blocked=bool(normalized_reasons),
        reasons=normalized_reasons,
        allow_ieg=allow_ieg,
        allowed_feature_groups=allowed_feature_groups,
        allow_model_primary=allow_model_primary,
        allow_model_stage2=allow_model_stage2,
        allow_fallback_heuristics=allow_fallback,
        action_posture=action_posture,
    )


def _mode_rank(mode: str) -> int:
    if mode not in _MODE_STRICTNESS_RANK:
        raise DfPostureError(f"unsupported posture mode: {mode!r}")
    return _MODE_STRICTNESS_RANK[mode]


def _with_reason(stamp: DfPostureStamp, reason: str) -> DfPostureStamp:
    reasons = tuple(sorted(set(stamp.reasons + (reason,))))
    return DfPostureStamp(
        scope_key=stamp.scope_key,
        mode=stamp.mode,
        capabilities_mask=stamp.capabilities_mask,
        policy_rev=stamp.policy_rev,
        posture_seq=stamp.posture_seq,
        decided_at_utc=stamp.decided_at_utc,
        source="DF_TRANSITION_HOLD",
        trust_state=stamp.trust_state,
        served_at_utc=stamp.served_at_utc,
        reasons=reasons,
    )


def _fail_closed_stamp(
    *,
    scope_key: str,
    decided_at_utc: str,
    source: str,
    trust_state: str,
    served_at_utc: str,
    reason_codes: tuple[str, ...],
    posture_seq: int = 0,
    policy_rev: PolicyRev | None = None,
) -> DfPostureStamp:
    return DfPostureStamp(
        scope_key=scope_key,
        mode="FAIL_CLOSED",
        capabilities_mask=CapabilitiesMask(
            allow_ieg=False,
            allowed_feature_groups=(),
            allow_model_primary=False,
            allow_model_stage2=False,
            allow_fallback_heuristics=True,
            action_posture="STEP_UP_ONLY",
        ),
        policy_rev=policy_rev or PolicyRev(policy_id="dl.policy.fail_closed", revision="df_failsafe"),
        posture_seq=max(0, int(posture_seq)),
        decided_at_utc=decided_at_utc,
        source=source,
        trust_state=trust_state,
        served_at_utc=served_at_utc,
        reasons=tuple(sorted(set(reason_codes))),
    )


def _parse_utc(value: str) -> datetime:
    text = str(value).strip()
    normalized = text.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _canonical_scope_key(scope_key: Any) -> str:
    if isinstance(scope_key, str):
        token = scope_key.strip()
        if not token:
            raise DfPostureError("scope_key must be a non-empty string")
        return token
    if isinstance(scope_key, Mapping):
        return _canonical_scope_key_from_mapping(scope_key)
    canonical = getattr(scope_key, "canonical_key", None)
    if callable(canonical):
        token = str(canonical()).strip()
        if token:
            return token
    as_dict = getattr(scope_key, "as_dict", None)
    if callable(as_dict):
        payload = as_dict()
        if isinstance(payload, Mapping):
            return _canonical_scope_key_from_mapping(payload)
    raise DfPostureError("scope_key must be a canonical string or scope mapping/object")


def _canonical_scope_key_from_mapping(scope_key: Mapping[str, Any]) -> str:
    environment = str(scope_key.get("environment") or "").strip()
    mode = str(scope_key.get("mode") or "").strip()
    bundle_slot = str(scope_key.get("bundle_slot") or "").strip()
    if not environment or not mode or not bundle_slot:
        raise DfPostureError("scope_key mapping requires environment, mode, bundle_slot")
    tenant = str(scope_key.get("tenant_id") or "").strip()
    return "|".join([environment, mode, bundle_slot, tenant])
