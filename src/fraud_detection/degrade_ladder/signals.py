"""DL signal intake and snapshot normalization (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence


SIGNAL_INPUT_STATUSES: set[str] = {"OK", "ERROR"}
SIGNAL_STATES: set[str] = {"OK", "STALE", "MISSING", "ERROR"}


class DlSignalError(ValueError):
    """Raised when DL signal samples or snapshots are invalid."""


@dataclass(frozen=True)
class DlSignalSample:
    name: str
    scope_key: str
    observed_at_utc: str
    status: str
    value: Any = None
    source: str | None = None
    detail: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DlSignalSample":
        if not isinstance(payload, Mapping):
            raise DlSignalError("signal sample payload must be a mapping")
        name = str(payload.get("name") or "").strip()
        scope_key = str(payload.get("scope_key") or "").strip()
        observed_at_utc = str(payload.get("observed_at_utc") or "").strip()
        status = str(payload.get("status") or "").strip().upper()
        if not name:
            raise DlSignalError("signal sample requires non-empty name")
        if not scope_key:
            raise DlSignalError("signal sample requires non-empty scope_key")
        if not observed_at_utc:
            raise DlSignalError("signal sample requires observed_at_utc")
        if status not in SIGNAL_INPUT_STATUSES:
            raise DlSignalError(f"signal sample status must be one of {sorted(SIGNAL_INPUT_STATUSES)}")
        source = payload.get("source")
        detail = payload.get("detail")
        return cls(
            name=name,
            scope_key=scope_key,
            observed_at_utc=observed_at_utc,
            status=status,
            value=payload.get("value"),
            source=None if source in (None, "") else str(source),
            detail=None if detail in (None, "") else str(detail),
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "scope_key": self.scope_key,
            "observed_at_utc": self.observed_at_utc,
            "status": self.status,
            "value": _normalize_value(self.value),
        }
        if self.source:
            payload["source"] = self.source
        if self.detail:
            payload["detail"] = self.detail
        return payload

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


@dataclass(frozen=True)
class DlSignalState:
    name: str
    required: bool
    state: str
    observed_at_utc: str | None
    age_seconds: int | None
    input_status: str | None
    source: str | None
    detail: str | None
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "required": self.required,
            "state": self.state,
            "observed_at_utc": self.observed_at_utc,
            "age_seconds": self.age_seconds,
            "input_status": self.input_status,
            "source": self.source,
            "detail": self.detail,
            "value": _normalize_value(self.value),
        }
        return payload


@dataclass(frozen=True)
class DlSignalSnapshot:
    scope_key: str
    decision_time_utc: str
    required_signal_names: tuple[str, ...]
    optional_signal_names: tuple[str, ...]
    required_max_age_seconds: int
    states: tuple[DlSignalState, ...]
    has_required_gaps: bool
    snapshot_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope_key": self.scope_key,
            "decision_time_utc": self.decision_time_utc,
            "required_signal_names": list(self.required_signal_names),
            "optional_signal_names": list(self.optional_signal_names),
            "required_max_age_seconds": self.required_max_age_seconds,
            "has_required_gaps": self.has_required_gaps,
            "states": [state.as_dict() for state in self.states],
            "snapshot_digest": self.snapshot_digest,
        }

    def state_by_name(self, name: str) -> DlSignalState:
        for state in self.states:
            if state.name == name:
                return state
        raise KeyError(name)


def normalize_signal_samples(payloads: Iterable[Mapping[str, Any]]) -> list[DlSignalSample]:
    return [DlSignalSample.from_payload(payload) for payload in payloads]


def build_signal_snapshot(
    samples: Sequence[DlSignalSample],
    *,
    scope_key: str,
    decision_time_utc: str,
    required_signal_names: Sequence[str],
    optional_signal_names: Sequence[str] = (),
    required_max_age_seconds: int,
) -> DlSignalSnapshot:
    normalized_scope = str(scope_key).strip()
    if not normalized_scope:
        raise DlSignalError("scope_key must be non-empty")
    if not isinstance(required_max_age_seconds, int) or required_max_age_seconds <= 0:
        raise DlSignalError("required_max_age_seconds must be a positive integer")

    decision_dt = _parse_utc(decision_time_utc, field_name="decision_time_utc")
    required = _normalize_signal_name_list(required_signal_names, field_name="required_signal_names")
    if not required:
        raise DlSignalError("required_signal_names must be non-empty")
    optional = _normalize_signal_name_list(optional_signal_names, field_name="optional_signal_names")
    overlap = sorted(set(required) & set(optional))
    if overlap:
        raise DlSignalError(f"signals cannot be both required and optional: {','.join(overlap)}")

    tracked = tuple(required) + tuple(name for name in optional if name not in set(required))
    latest: dict[str, tuple[datetime, str, DlSignalSample]] = {}
    for sample in samples:
        if sample.scope_key != normalized_scope:
            continue
        if sample.name not in tracked:
            continue
        observed = _parse_utc(sample.observed_at_utc, field_name=f"sample:{sample.name}.observed_at_utc")
        tie_break = sample.canonical_json()
        current = latest.get(sample.name)
        candidate = (observed, tie_break, sample)
        if current is None or candidate > current:
            latest[sample.name] = candidate

    states: list[DlSignalState] = []
    has_required_gaps = False
    required_set = set(required)
    for name in tracked:
        required_flag = name in required_set
        selected = latest.get(name)
        if selected is None:
            state = DlSignalState(
                name=name,
                required=required_flag,
                state="MISSING",
                observed_at_utc=None,
                age_seconds=None,
                input_status=None,
                source=None,
                detail="MISSING_SIGNAL",
                value=None,
            )
        else:
            observed, _, sample = selected
            age_seconds = int((decision_dt - observed).total_seconds())
            if age_seconds < 0:
                state = DlSignalState(
                    name=name,
                    required=required_flag,
                    state="ERROR",
                    observed_at_utc=sample.observed_at_utc,
                    age_seconds=age_seconds,
                    input_status=sample.status,
                    source=sample.source,
                    detail="SIGNAL_FROM_FUTURE",
                    value=sample.value,
                )
            elif sample.status == "ERROR":
                state = DlSignalState(
                    name=name,
                    required=required_flag,
                    state="ERROR",
                    observed_at_utc=sample.observed_at_utc,
                    age_seconds=age_seconds,
                    input_status=sample.status,
                    source=sample.source,
                    detail=sample.detail or "SOURCE_ERROR",
                    value=sample.value,
                )
            elif age_seconds > required_max_age_seconds:
                state = DlSignalState(
                    name=name,
                    required=required_flag,
                    state="STALE",
                    observed_at_utc=sample.observed_at_utc,
                    age_seconds=age_seconds,
                    input_status=sample.status,
                    source=sample.source,
                    detail=sample.detail or "SIGNAL_STALE",
                    value=sample.value,
                )
            else:
                state = DlSignalState(
                    name=name,
                    required=required_flag,
                    state="OK",
                    observed_at_utc=sample.observed_at_utc,
                    age_seconds=age_seconds,
                    input_status=sample.status,
                    source=sample.source,
                    detail=sample.detail,
                    value=sample.value,
                )

        if required_flag and state.state in {"MISSING", "STALE", "ERROR"}:
            has_required_gaps = True
        states.append(state)

    snapshot_payload = {
        "scope_key": normalized_scope,
        "decision_time_utc": str(decision_time_utc).strip(),
        "required_signal_names": list(required),
        "optional_signal_names": list(optional),
        "required_max_age_seconds": required_max_age_seconds,
        "has_required_gaps": has_required_gaps,
        "states": [state.as_dict() for state in states],
    }
    canonical = json.dumps(snapshot_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return DlSignalSnapshot(
        scope_key=normalized_scope,
        decision_time_utc=str(decision_time_utc).strip(),
        required_signal_names=required,
        optional_signal_names=optional,
        required_max_age_seconds=required_max_age_seconds,
        states=tuple(states),
        has_required_gaps=has_required_gaps,
        snapshot_digest=digest,
    )


def build_signal_snapshot_from_payloads(
    payloads: Sequence[Mapping[str, Any]],
    *,
    scope_key: str,
    decision_time_utc: str,
    required_signal_names: Sequence[str],
    optional_signal_names: Sequence[str] = (),
    required_max_age_seconds: int,
) -> DlSignalSnapshot:
    return build_signal_snapshot(
        normalize_signal_samples(payloads),
        scope_key=scope_key,
        decision_time_utc=decision_time_utc,
        required_signal_names=required_signal_names,
        optional_signal_names=optional_signal_names,
        required_max_age_seconds=required_max_age_seconds,
    )


def _normalize_signal_name_list(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        name = str(value).strip()
        if not name:
            raise DlSignalError(f"{field_name}[{index}] must be non-empty")
        if name in seen:
            raise DlSignalError(f"{field_name} contains duplicate signal '{name}'")
        seen.add(name)
        names.append(name)
    return tuple(names)


def _parse_utc(value: str, *, field_name: str) -> datetime:
    token = str(value).strip()
    if not token:
        raise DlSignalError(f"{field_name} must be non-empty")
    normalized = token.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DlSignalError(f"{field_name} must be RFC3339-ish UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise DlSignalError(f"{field_name} must include timezone information")
    return dt.astimezone(timezone.utc)


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    return str(value)
