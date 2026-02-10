"""DL health gate and self-trust clamp (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


HEALTH_STATES: tuple[str, ...] = ("HEALTHY", "IMPAIRED", "BLIND", "BROKEN")

REBUILD_REASON_CODES: frozenset[str] = frozenset(
    {
        "POSTURE_MISSING",
        "POSTURE_STORE_ERROR",
        "POSTURE_STORE_CORRUPT",
    }
)


class DlHealthError(ValueError):
    """Raised when health gate inputs are invalid."""


@dataclass(frozen=True)
class DlHealthPolicy:
    healthy_clear_observations: int = 2
    hold_down_seconds: int = 30
    rebuild_cooldown_seconds: int = 120


@dataclass(frozen=True)
class DlHealthGate:
    scope_key: str
    state: str
    forced_mode: str | None
    reason_codes: tuple[str, ...]
    effective_at_utc: str
    hold_down_until_utc: str | None
    healthy_observation_streak: int
    rebuild_requested: bool
    rebuild_reason: str | None

    @property
    def is_forced(self) -> bool:
        return self.forced_mode is not None


@dataclass
class _ScopeMemory:
    state: str
    since_utc: datetime
    hold_down_until_utc: datetime | None
    healthy_observation_streak: int
    last_rebuild_at_utc: datetime | None


class DlHealthGateController:
    def __init__(self, policy: DlHealthPolicy | None = None) -> None:
        self.policy = policy or DlHealthPolicy()
        self._validate_policy(self.policy)
        self._state: dict[str, _ScopeMemory] = {}

    def evaluate(
        self,
        *,
        scope_key: str,
        decision_time_utc: str,
        policy_ok: bool,
        required_signals_ok: bool,
        store_ok: bool,
        serve_ok: bool,
        control_publish_ok: bool = True,
        reason_codes: Iterable[str] = (),
    ) -> DlHealthGate:
        normalized_scope = _normalize_scope(scope_key)
        now = _parse_utc(decision_time_utc, field_name="decision_time_utc")
        reasons = set(_normalize_reason_codes(reason_codes))

        if not policy_ok:
            reasons.add("POLICY_UNAVAILABLE")
        if not required_signals_ok:
            reasons.add("REQUIRED_SIGNALS_UNHEALTHY")
        if not store_ok:
            reasons.add("POSTURE_STORE_ERROR")
        if not serve_ok:
            reasons.add("SERVE_SURFACE_ERROR")
        if not control_publish_ok:
            reasons.add("CONTROL_PUBLISH_UNHEALTHY")

        raw_state = _classify_raw_state(
            policy_ok=policy_ok,
            required_signals_ok=required_signals_ok,
            store_ok=store_ok,
            serve_ok=serve_ok,
            control_publish_ok=control_publish_ok,
            reasons=reasons,
        )
        memory = self._state.get(normalized_scope)
        if memory is None:
            memory = _ScopeMemory(
                state=raw_state,
                since_utc=now,
                hold_down_until_utc=_next_hold_down(now, self.policy.hold_down_seconds)
                if raw_state in {"BLIND", "BROKEN"}
                else None,
                healthy_observation_streak=0 if raw_state != "HEALTHY" else 1,
                last_rebuild_at_utc=None,
            )
            self._state[normalized_scope] = memory

        next_state, next_streak, next_since, next_hold_down, extra_reasons = self._transition_state(
            memory=memory,
            raw_state=raw_state,
            now=now,
        )
        reasons.update(extra_reasons)

        rebuild_requested, rebuild_reason, last_rebuild = self._maybe_trigger_rebuild(
            now=now,
            state=next_state,
            reason_codes=reasons,
            last_rebuild_at_utc=memory.last_rebuild_at_utc,
        )

        memory.state = next_state
        memory.since_utc = next_since
        memory.hold_down_until_utc = next_hold_down
        memory.healthy_observation_streak = next_streak
        memory.last_rebuild_at_utc = last_rebuild
        self._state[normalized_scope] = memory

        ordered_reasons = tuple(sorted(reasons))
        return DlHealthGate(
            scope_key=normalized_scope,
            state=next_state,
            forced_mode="FAIL_CLOSED" if next_state in {"BLIND", "BROKEN"} else None,
            reason_codes=ordered_reasons,
            effective_at_utc=decision_time_utc,
            hold_down_until_utc=None
            if next_hold_down is None
            else next_hold_down.astimezone(timezone.utc).isoformat(),
            healthy_observation_streak=next_streak,
            rebuild_requested=rebuild_requested,
            rebuild_reason=rebuild_reason,
        )

    def _transition_state(
        self,
        *,
        memory: _ScopeMemory,
        raw_state: str,
        now: datetime,
    ) -> tuple[str, int, datetime, datetime | None, set[str]]:
        reasons: set[str] = set()
        current = memory.state
        streak = memory.healthy_observation_streak
        hold_down_until = memory.hold_down_until_utc
        since = memory.since_utc

        if raw_state in {"BLIND", "BROKEN"}:
            if raw_state != current:
                since = now
            return (
                raw_state,
                0,
                since,
                _next_hold_down(now, self.policy.hold_down_seconds),
                reasons,
            )

        if current in {"BLIND", "BROKEN"}:
            if raw_state == "HEALTHY":
                streak = streak + 1
                hold_blocked = hold_down_until is not None and now < hold_down_until
                if streak < self.policy.healthy_clear_observations or hold_blocked:
                    reasons.add("RECOVERY_PENDING")
                    return current, streak, since, hold_down_until, reasons
                return "HEALTHY", streak, now, None, reasons
            reasons.add("RECOVERY_PENDING")
            return current, 0, since, hold_down_until, reasons

        if raw_state == "IMPAIRED":
            if current != "IMPAIRED":
                since = now
            return "IMPAIRED", 0, since, None, reasons

        if raw_state == "HEALTHY":
            if current == "HEALTHY":
                return "HEALTHY", min(streak + 1, self.policy.healthy_clear_observations), since, None, reasons
            streak = streak + 1
            if streak < self.policy.healthy_clear_observations:
                reasons.add("RECOVERY_PENDING")
                return current, streak, since, None, reasons
            return "HEALTHY", streak, now, None, reasons

        return current, streak, since, hold_down_until, reasons

    def _maybe_trigger_rebuild(
        self,
        *,
        now: datetime,
        state: str,
        reason_codes: set[str],
        last_rebuild_at_utc: datetime | None,
    ) -> tuple[bool, str | None, datetime | None]:
        if state not in {"BLIND", "BROKEN"}:
            return False, None, last_rebuild_at_utc
        matched = sorted(code for code in reason_codes if code in REBUILD_REASON_CODES)
        if not matched:
            return False, None, last_rebuild_at_utc
        if last_rebuild_at_utc is not None:
            cooldown = timedelta(seconds=self.policy.rebuild_cooldown_seconds)
            if now < last_rebuild_at_utc + cooldown:
                return False, None, last_rebuild_at_utc
        return True, matched[0], now

    @staticmethod
    def _validate_policy(policy: DlHealthPolicy) -> None:
        if policy.healthy_clear_observations <= 0:
            raise DlHealthError("healthy_clear_observations must be >= 1")
        if policy.hold_down_seconds < 0:
            raise DlHealthError("hold_down_seconds must be >= 0")
        if policy.rebuild_cooldown_seconds < 0:
            raise DlHealthError("rebuild_cooldown_seconds must be >= 0")


def _classify_raw_state(
    *,
    policy_ok: bool,
    required_signals_ok: bool,
    store_ok: bool,
    serve_ok: bool,
    control_publish_ok: bool,
    reasons: set[str],
) -> str:
    if not store_ok or not serve_ok or "POSTURE_STORE_CORRUPT" in reasons:
        return "BROKEN"
    if not policy_ok or not required_signals_ok:
        return "BLIND"
    if not control_publish_ok:
        return "IMPAIRED"
    return "HEALTHY"


def _normalize_scope(scope_key: str) -> str:
    normalized = str(scope_key).strip()
    if not normalized:
        raise DlHealthError("scope_key must be non-empty")
    return normalized


def _parse_utc(value: str, *, field_name: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise DlHealthError(f"{field_name} must be non-empty")
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DlHealthError(f"{field_name} must be RFC3339-ish UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise DlHealthError(f"{field_name} must include timezone information")
    return dt.astimezone(timezone.utc)


def _normalize_reason_codes(reason_codes: Iterable[str]) -> list[str]:
    normalized: set[str] = set()
    for code in reason_codes:
        token = str(code).strip().upper()
        if token:
            normalized.add(token)
    return sorted(normalized)


def _next_hold_down(now: datetime, hold_down_seconds: int) -> datetime | None:
    if hold_down_seconds <= 0:
        return None
    return now + timedelta(seconds=hold_down_seconds)
