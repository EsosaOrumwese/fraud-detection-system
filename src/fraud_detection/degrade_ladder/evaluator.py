"""DL scope resolution and deterministic posture evaluation (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .config import DlPolicyProfile
from .contracts import CapabilitiesMask, DegradeDecision, MODE_SEQUENCE, PolicyRev
from .signals import DlSignalSnapshot


SCOPE_KINDS: tuple[str, ...] = ("GLOBAL", "MANIFEST", "RUN")


class DlEvaluationError(ValueError):
    """Raised when posture evaluation inputs are invalid or inconsistent."""


@dataclass(frozen=True)
class DlScope:
    scope_kind: str
    scope_key: str


def resolve_scope(
    *,
    scope_kind: str,
    manifest_fingerprint: str | None = None,
    run_id: str | None = None,
    scenario_id: str | None = None,
    parameter_hash: str | None = None,
    seed: str | None = None,
) -> DlScope:
    kind = _normalize_scope_kind(scope_kind)
    manifest = _norm(manifest_fingerprint)
    run = _norm(run_id)
    scenario = _norm(scenario_id)
    parameter = _norm(parameter_hash)
    seed_value = _norm(seed)

    if kind == "GLOBAL":
        if any((manifest, run, scenario, parameter, seed_value)):
            raise DlEvaluationError("GLOBAL scope cannot carry manifest/run pins")
        return DlScope(scope_kind=kind, scope_key="scope=GLOBAL")

    if kind == "MANIFEST":
        if not manifest:
            raise DlEvaluationError("MANIFEST scope requires manifest_fingerprint")
        if any((run, scenario, parameter, seed_value)):
            raise DlEvaluationError("MANIFEST scope cannot carry run-level pins")
        return DlScope(
            scope_kind=kind,
            scope_key=f"scope=MANIFEST|manifest_fingerprint={manifest}",
        )

    if not manifest:
        raise DlEvaluationError("RUN scope requires manifest_fingerprint")
    if not run:
        raise DlEvaluationError("RUN scope requires run_id")

    components = [
        ("manifest_fingerprint", manifest),
        ("run_id", run),
        ("scenario_id", scenario),
        ("parameter_hash", parameter),
        ("seed", seed_value),
    ]
    suffix = "|".join(f"{key}={value}" for key, value in components if value)
    return DlScope(scope_kind=kind, scope_key=f"scope=RUN|{suffix}")


def evaluate_posture(
    *,
    profile: DlPolicyProfile,
    policy_rev: PolicyRev,
    snapshot: DlSignalSnapshot,
    decision_time_utc: str,
    scope_key: str,
    posture_seq: int,
    prior_decision: DegradeDecision | None = None,
) -> DegradeDecision:
    normalized_scope = _norm(scope_key)
    if not normalized_scope:
        raise DlEvaluationError("scope_key must be non-empty")
    if snapshot.scope_key != normalized_scope:
        raise DlEvaluationError(
            f"snapshot.scope_key mismatch: expected {normalized_scope!r}, got {snapshot.scope_key!r}"
        )
    if not isinstance(posture_seq, int) or posture_seq < 0:
        raise DlEvaluationError("posture_seq must be a non-negative integer")

    decision_dt = _parse_utc(decision_time_utc, field_name="decision_time_utc")
    baseline_mode, baseline_reason = _determine_baseline_mode(snapshot.states, snapshot.has_required_gaps)
    next_mode, transition_reason = _apply_hysteresis(
        profile=profile,
        baseline_mode=baseline_mode,
        prior_decision=prior_decision,
        decision_dt=decision_dt,
    )
    mode_policy = profile.modes.get(next_mode)
    if mode_policy is None:
        raise DlEvaluationError(f"profile {profile.profile_id!r} has no policy for mode {next_mode!r}")

    reason = ";".join(
        [
            f"baseline={baseline_reason}",
            f"transition={transition_reason}",
            f"profile={profile.profile_id}",
            f"scope={normalized_scope}",
        ]
    )
    evidence_refs = (
        {"kind": "dl_snapshot", "ref": snapshot.snapshot_digest},
        {"kind": "dl_profile", "ref": profile.profile_id},
    )
    return DegradeDecision(
        mode=next_mode,
        capabilities_mask=mode_policy.capabilities_mask,
        policy_rev=policy_rev,
        posture_seq=posture_seq,
        decided_at_utc=decision_time_utc,
        reason=reason,
        evidence_refs=evidence_refs,
    )


def evaluate_posture_safe(
    *,
    profile: DlPolicyProfile,
    policy_rev: PolicyRev,
    snapshot: DlSignalSnapshot,
    decision_time_utc: str,
    scope_key: str,
    posture_seq: int,
    prior_decision: DegradeDecision | None = None,
) -> DegradeDecision:
    try:
        return evaluate_posture(
            profile=profile,
            policy_rev=policy_rev,
            snapshot=snapshot,
            decision_time_utc=decision_time_utc,
            scope_key=scope_key,
            posture_seq=posture_seq,
            prior_decision=prior_decision,
        )
    except Exception as exc:
        normalized_scope = _norm(scope_key) or "scope=UNKNOWN"
        decision_time = _norm(decision_time_utc) or "1970-01-01T00:00:00Z"
        seq = posture_seq if isinstance(posture_seq, int) and posture_seq >= 0 else 0
        reason = ";".join(
            [
                f"EVALUATOR_FAIL_CLOSED:{exc.__class__.__name__}",
                f"profile={profile.profile_id}",
                f"scope={normalized_scope}",
            ]
        )
        evidence_refs = (
            {"kind": "dl_error", "ref": exc.__class__.__name__},
            {"kind": "dl_snapshot", "ref": snapshot.snapshot_digest},
        )
        return DegradeDecision(
            mode="FAIL_CLOSED",
            capabilities_mask=_fail_closed_mask(profile),
            policy_rev=policy_rev,
            posture_seq=seq,
            decided_at_utc=decision_time,
            reason=reason,
            evidence_refs=evidence_refs,
        )


def _determine_baseline_mode(
    states: Iterable[object],
    has_required_gaps: bool,
) -> tuple[str, str]:
    if has_required_gaps:
        required_gap_names = sorted(
            state.name  # type: ignore[attr-defined]
            for state in states
            if bool(getattr(state, "required", False))
            and str(getattr(state, "state", "")).upper() in {"MISSING", "STALE", "ERROR"}
        )
        suffix = ",".join(required_gap_names) if required_gap_names else "required_gaps"
        return "FAIL_CLOSED", f"required_signal_gap:{suffix}"

    optional_errors = sorted(
        state.name  # type: ignore[attr-defined]
        for state in states
        if not bool(getattr(state, "required", False)) and str(getattr(state, "state", "")).upper() == "ERROR"
    )
    if optional_errors:
        return "DEGRADED_2", f"optional_signal_error:{','.join(optional_errors)}"

    optional_soft = sorted(
        state.name  # type: ignore[attr-defined]
        for state in states
        if not bool(getattr(state, "required", False))
        and str(getattr(state, "state", "")).upper() in {"MISSING", "STALE"}
    )
    if optional_soft:
        return "DEGRADED_1", f"optional_signal_soft_gap:{','.join(optional_soft)}"

    return "NORMAL", "all_signals_ok"


def _apply_hysteresis(
    *,
    profile: DlPolicyProfile,
    baseline_mode: str,
    prior_decision: DegradeDecision | None,
    decision_dt: datetime,
) -> tuple[str, str]:
    if baseline_mode not in MODE_SEQUENCE:
        raise DlEvaluationError(f"baseline_mode must be one of {MODE_SEQUENCE}: {baseline_mode!r}")
    if prior_decision is None:
        return baseline_mode, "init_from_baseline"

    current_mode = prior_decision.mode
    if current_mode not in MODE_SEQUENCE:
        raise DlEvaluationError(f"prior_decision.mode must be one of {MODE_SEQUENCE}: {current_mode!r}")

    current_index = MODE_SEQUENCE.index(current_mode)
    baseline_index = MODE_SEQUENCE.index(baseline_mode)
    if baseline_index > current_index:
        return baseline_mode, "downshift_immediate"
    if baseline_index == current_index:
        return current_mode, "steady_state"

    quiet_seconds = _quiet_period_seconds(profile)
    prior_dt = _parse_utc(prior_decision.decided_at_utc, field_name="prior_decision.decided_at_utc")
    elapsed_seconds = int((decision_dt - prior_dt).total_seconds())
    if elapsed_seconds < quiet_seconds:
        return current_mode, f"upshift_held_quiet_period:{elapsed_seconds}s<{quiet_seconds}s"

    candidate_index = current_index - 1
    if candidate_index < baseline_index:
        candidate_index = baseline_index
    next_mode = MODE_SEQUENCE[candidate_index]
    return next_mode, f"upshift_one_rung:{current_mode}->{next_mode}"


def _quiet_period_seconds(profile: DlPolicyProfile) -> int:
    thresholds = profile.thresholds
    if not isinstance(thresholds, dict):
        raise DlEvaluationError(f"profile {profile.profile_id!r} thresholds must be a mapping")

    hysteresis = thresholds.get("hysteresis")
    if not isinstance(hysteresis, dict):
        raise DlEvaluationError(f"profile {profile.profile_id!r} thresholds.hysteresis must be a mapping")

    downshift_immediate = hysteresis.get("downshift_immediate")
    if not isinstance(downshift_immediate, bool):
        raise DlEvaluationError(
            f"profile {profile.profile_id!r} thresholds.hysteresis.downshift_immediate must be boolean"
        )
    if not downshift_immediate:
        raise DlEvaluationError("downshift_immediate=false violates DL phase 3 semantics")

    quiet_seconds = hysteresis.get("upshift_quiet_period_seconds")
    if not isinstance(quiet_seconds, int) or quiet_seconds < 0:
        raise DlEvaluationError(
            f"profile {profile.profile_id!r} thresholds.hysteresis.upshift_quiet_period_seconds"
            " must be a non-negative integer"
        )
    return quiet_seconds


def _fail_closed_mask(profile: DlPolicyProfile) -> CapabilitiesMask:
    policy = profile.modes.get("FAIL_CLOSED")
    if policy is not None:
        return policy.capabilities_mask
    return CapabilitiesMask(
        allow_ieg=False,
        allowed_feature_groups=(),
        allow_model_primary=False,
        allow_model_stage2=False,
        allow_fallback_heuristics=True,
        action_posture="STEP_UP_ONLY",
    )


def _normalize_scope_kind(scope_kind: str) -> str:
    kind = str(scope_kind).strip().upper()
    if kind not in SCOPE_KINDS:
        raise DlEvaluationError(f"scope_kind must be one of {SCOPE_KINDS}: {scope_kind!r}")
    return kind


def _norm(value: str | None) -> str:
    return "" if value in (None, "") else str(value).strip()


def _parse_utc(value: str, *, field_name: str) -> datetime:
    token = _norm(value)
    if not token:
        raise DlEvaluationError(f"{field_name} must be non-empty")
    normalized = token.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DlEvaluationError(f"{field_name} must be RFC3339-ish UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise DlEvaluationError(f"{field_name} must include timezone information")
    return dt.astimezone(timezone.utc)
