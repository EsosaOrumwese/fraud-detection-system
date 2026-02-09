"""Decision Fabric context acquisition + decision-time budgets (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from .inlet import DecisionTriggerCandidate, SourceEbRef
from .posture import DfPostureEnforcementResult, DfPostureStamp, enforce_posture_constraints
from .registry import RegistryCompatibility


CONTEXT_READY = "CONTEXT_READY"
CONTEXT_WAITING = "CONTEXT_WAITING"
CONTEXT_MISSING = "CONTEXT_MISSING"
CONTEXT_BLOCKED = "CONTEXT_BLOCKED"
CONTEXT_UNAVAILABLE = "CONTEXT_UNAVAILABLE"
DECISION_DEADLINE_EXCEEDED = "DECISION_DEADLINE_EXCEEDED"


class DecisionContextError(ValueError):
    """Raised when DF context policy or acquisition inputs are invalid."""


@dataclass(frozen=True)
class DecisionContextPolicy:
    version: str
    policy_id: str
    revision: str
    decision_deadline_ms: int
    join_wait_budget_ms: int
    required_context_roles: tuple[str, ...]
    optional_context_roles: tuple[str, ...]
    ofp_feature_groups: tuple[tuple[str, str], ...]
    ofp_graph_resolution_mode: str
    require_ofp: bool
    require_ieg: bool
    content_digest: str

    @classmethod
    def load(cls, path: Path) -> "DecisionContextPolicy":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise DecisionContextError("DF context policy must be a mapping")
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DecisionContextPolicy":
        version = _non_empty(payload.get("version"), "version")
        policy_id = _non_empty(payload.get("policy_id"), "policy_id")
        revision = _non_empty(payload.get("revision"), "revision")

        budgets = payload.get("budgets") or {}
        if not isinstance(budgets, Mapping):
            raise DecisionContextError("budgets must be a mapping")
        decision_deadline_ms = _positive_int(budgets.get("decision_deadline_ms"), "budgets.decision_deadline_ms")
        join_wait_budget_ms = _positive_int(budgets.get("join_wait_budget_ms"), "budgets.join_wait_budget_ms")
        if join_wait_budget_ms > decision_deadline_ms:
            raise DecisionContextError("join_wait_budget_ms must be <= decision_deadline_ms")

        roles = payload.get("context_roles") or {}
        if not isinstance(roles, Mapping):
            raise DecisionContextError("context_roles must be a mapping")
        required_roles = _non_empty_list(roles.get("required"), "context_roles.required")
        optional_roles = _unique_list(roles.get("optional"))

        ofp = payload.get("ofp") or {}
        if not isinstance(ofp, Mapping):
            raise DecisionContextError("ofp must be a mapping")
        require_ofp = bool(ofp.get("require_ofp", True))
        graph_mode = str(ofp.get("graph_resolution_mode") or "resolve_if_needed").strip()
        if graph_mode not in {"none", "resolve_if_needed", "require_ieg"}:
            raise DecisionContextError("ofp.graph_resolution_mode must be none|resolve_if_needed|require_ieg")
        ofp_groups = _parse_feature_groups(ofp.get("feature_groups"), require_ofp=require_ofp)

        ieg = payload.get("ieg") or {}
        if not isinstance(ieg, Mapping):
            raise DecisionContextError("ieg must be a mapping")
        require_ieg = bool(ieg.get("require_ieg", False))

        digest_payload = {
            "version": version,
            "policy_id": policy_id,
            "revision": revision,
            "budgets": {
                "decision_deadline_ms": decision_deadline_ms,
                "join_wait_budget_ms": join_wait_budget_ms,
            },
            "context_roles": {
                "required": sorted(required_roles),
                "optional": sorted(optional_roles),
            },
            "ofp": {
                "require_ofp": require_ofp,
                "graph_resolution_mode": graph_mode,
                "feature_groups": [{"name": name, "version": version} for name, version in ofp_groups],
            },
            "ieg": {"require_ieg": require_ieg},
        }
        content_digest = hashlib.sha256(_canonical_json(digest_payload).encode("utf-8")).hexdigest()

        return cls(
            version=version,
            policy_id=policy_id,
            revision=revision,
            decision_deadline_ms=decision_deadline_ms,
            join_wait_budget_ms=join_wait_budget_ms,
            required_context_roles=tuple(sorted(required_roles)),
            optional_context_roles=tuple(sorted(optional_roles)),
            ofp_feature_groups=tuple(sorted(ofp_groups)),
            ofp_graph_resolution_mode=graph_mode,
            require_ofp=require_ofp,
            require_ieg=require_ieg,
            content_digest=content_digest,
        )

    def feature_group_specs(self) -> list[dict[str, str]]:
        return [{"name": name, "version": version} for name, version in self.ofp_feature_groups]


@dataclass(frozen=True)
class DecisionBudgetSnapshot:
    decision_deadline_ms: int
    join_wait_budget_ms: int
    started_at_utc: str
    now_utc: str
    elapsed_ms: int
    decision_remaining_ms: int
    join_wait_remaining_ms: int
    decision_expired: bool
    join_wait_expired: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_deadline_ms": self.decision_deadline_ms,
            "join_wait_budget_ms": self.join_wait_budget_ms,
            "started_at_utc": self.started_at_utc,
            "now_utc": self.now_utc,
            "elapsed_ms": self.elapsed_ms,
            "decision_remaining_ms": self.decision_remaining_ms,
            "join_wait_remaining_ms": self.join_wait_remaining_ms,
            "decision_expired": self.decision_expired,
            "join_wait_expired": self.join_wait_expired,
        }


@dataclass(frozen=True)
class DecisionBudget:
    decision_deadline_ms: int
    join_wait_budget_ms: int
    started_at_utc: str

    def snapshot(self, now_utc: str) -> DecisionBudgetSnapshot:
        start = _parse_utc(self.started_at_utc)
        now = _parse_utc(now_utc)
        if start is None or now is None:
            raise DecisionContextError("started_at_utc and now_utc must be RFC3339 timestamps")
        elapsed_ms = max(0, int((now - start).total_seconds() * 1000))
        decision_remaining = max(0, self.decision_deadline_ms - elapsed_ms)
        join_remaining = max(0, self.join_wait_budget_ms - elapsed_ms)
        return DecisionBudgetSnapshot(
            decision_deadline_ms=self.decision_deadline_ms,
            join_wait_budget_ms=self.join_wait_budget_ms,
            started_at_utc=self.started_at_utc,
            now_utc=str(now_utc),
            elapsed_ms=elapsed_ms,
            decision_remaining_ms=decision_remaining,
            join_wait_remaining_ms=join_remaining,
            decision_expired=elapsed_ms >= self.decision_deadline_ms,
            join_wait_expired=elapsed_ms >= self.join_wait_budget_ms,
        )


@dataclass(frozen=True)
class ContextEvidence:
    source_eb_ref: dict[str, Any]
    context_refs: dict[str, dict[str, Any]]
    ofp_snapshot_hash: str | None
    ofp_eb_offset_basis: dict[str, Any] | None
    graph_version: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_eb_ref": dict(self.source_eb_ref),
            "context_refs": {key: dict(value) for key, value in sorted(self.context_refs.items())},
            "ofp_snapshot_hash": self.ofp_snapshot_hash,
            "ofp_eb_offset_basis": None if self.ofp_eb_offset_basis is None else dict(self.ofp_eb_offset_basis),
            "graph_version": None if self.graph_version is None else dict(self.graph_version),
        }

    def digest(self) -> str:
        canonical = _canonical_json(self.as_dict())
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DecisionContextResult:
    status: str
    reasons: tuple[str, ...]
    budget: DecisionBudgetSnapshot
    enforcement: DfPostureEnforcementResult | None
    evidence: ContextEvidence
    ofp_snapshot: dict[str, Any] | None
    feature_group_versions: dict[str, str]
    graph_version: dict[str, Any] | None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reasons": list(self.reasons),
            "budget": self.budget.as_dict(),
            "enforcement": None if self.enforcement is None else self.enforcement.as_dict(),
            "evidence": self.evidence.as_dict(),
            "feature_group_versions": dict(self.feature_group_versions),
            "graph_version": self.graph_version,
            "detail": self.detail,
        }


@dataclass
class DecisionContextAcquirer:
    policy: DecisionContextPolicy
    ofp_client: Any
    ieg_query: Any | None = None

    def __post_init__(self) -> None:
        if self.policy.require_ofp and self.ofp_client is None:
            raise DecisionContextError("ofp_client is required when policy.require_ofp is true")

    def acquire(
        self,
        *,
        candidate: DecisionTriggerCandidate,
        posture: DfPostureStamp,
        decision_started_at_utc: str,
        now_utc: str,
        context_refs: Mapping[str, Any],
        feature_keys: list[dict[str, Any]] | None = None,
        compatibility: RegistryCompatibility | None = None,
    ) -> DecisionContextResult:
        budget = DecisionBudget(
            decision_deadline_ms=self.policy.decision_deadline_ms,
            join_wait_budget_ms=self.policy.join_wait_budget_ms,
            started_at_utc=decision_started_at_utc,
        ).snapshot(now_utc)

        normalized_context_refs = _normalize_context_refs(context_refs)
        evidence = ContextEvidence(
            source_eb_ref=candidate.source_eb_ref.as_dict(),
            context_refs=normalized_context_refs,
            ofp_snapshot_hash=None,
            ofp_eb_offset_basis=None,
            graph_version=None,
        )

        if budget.decision_expired:
            return DecisionContextResult(
                status=DECISION_DEADLINE_EXCEEDED,
                reasons=("DEADLINE_EXCEEDED",),
                budget=budget,
                enforcement=None,
                evidence=evidence,
                ofp_snapshot=None,
                feature_group_versions={},
                graph_version=None,
            )

        missing_roles = _missing_roles(self.policy.required_context_roles, normalized_context_refs)
        if missing_roles:
            waiting_reasons = tuple(sorted(f"CONTEXT_WAITING:{role}" for role in missing_roles))
            missing_reasons = tuple(sorted(f"CONTEXT_MISSING:{role}" for role in missing_roles))
            if budget.join_wait_expired:
                reasons = tuple(sorted({"JOIN_WAIT_EXCEEDED", *missing_reasons}))
                return DecisionContextResult(
                    status=CONTEXT_MISSING,
                    reasons=reasons,
                    budget=budget,
                    enforcement=None,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=None,
                )
            return DecisionContextResult(
                status=CONTEXT_WAITING,
                reasons=waiting_reasons,
                budget=budget,
                enforcement=None,
                evidence=evidence,
                ofp_snapshot=None,
                feature_group_versions={},
                graph_version=None,
            )

        requirements = _context_requirements(self.policy, compatibility, posture)
        enforcement = enforce_posture_constraints(
            posture=posture,
            require_ieg=requirements.require_ieg,
            requested_feature_groups=tuple(name for name, _ in requirements.feature_groups),
            require_model_primary=requirements.require_model_primary,
            require_model_stage2=requirements.require_model_stage2,
            require_fallback_heuristics=requirements.require_fallback_heuristics,
            requested_action_posture=requirements.required_action_posture,
        )
        if enforcement.blocked:
            return DecisionContextResult(
                status=CONTEXT_BLOCKED,
                reasons=enforcement.reasons,
                budget=budget,
                enforcement=enforcement,
                evidence=evidence,
                ofp_snapshot=None,
                feature_group_versions={},
                graph_version=None,
            )

        graph_version = None
        if requirements.require_ieg:
            if self.ieg_query is None:
                return DecisionContextResult(
                    status=CONTEXT_UNAVAILABLE,
                    reasons=("IEG_UNAVAILABLE",),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=None,
                )
            try:
                status = self.ieg_query.status(scenario_run_id=candidate.pins.get("scenario_run_id"))
            except Exception as exc:
                return DecisionContextResult(
                    status=CONTEXT_UNAVAILABLE,
                    reasons=("IEG_UNAVAILABLE",),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=None,
                    detail=str(exc),
                )
            graph_version = status.get("graph_version")
            if not graph_version:
                return DecisionContextResult(
                    status=CONTEXT_UNAVAILABLE,
                    reasons=("IEG_GRAPH_VERSION_MISSING",),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=None,
                )
            health_state = str(status.get("health_state") or "")
            if health_state == "RED":
                return DecisionContextResult(
                    status=CONTEXT_UNAVAILABLE,
                    reasons=("IEG_HEALTH_RED",),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=graph_version,
                )

        feature_keys_normalized, feature_key_errors = _normalize_feature_keys(feature_keys)
        if self.policy.require_ofp:
            if not requirements.feature_groups:
                return DecisionContextResult(
                    status=CONTEXT_MISSING,
                    reasons=("OFP_FEATURE_GROUPS_MISSING",),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=graph_version,
                )
            if not feature_keys_normalized:
                reasons = ["OFP_FEATURE_KEYS_MISSING"]
                reasons.extend(feature_key_errors)
                return DecisionContextResult(
                    status=CONTEXT_MISSING,
                    reasons=tuple(sorted(set(reasons))),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=graph_version,
                )

        ofp_snapshot = None
        feature_group_versions: dict[str, str] = {}
        detail = None
        if self.policy.require_ofp:
            request_payload = {
                "pins": candidate.pins,
                "as_of_time_utc": str(candidate.source_ts_utc),
                "feature_keys": feature_keys_normalized,
                "feature_groups": [{"name": name, "version": version} for name, version in requirements.feature_groups],
                "graph_resolution_mode": _graph_mode_for_enforcement(
                    self.policy.ofp_graph_resolution_mode,
                    enforcement.allow_ieg,
                ),
                "request_id": _ofp_request_id(candidate),
            }
            try:
                response = self.ofp_client.get_features(request_payload)
            except Exception as exc:
                return DecisionContextResult(
                    status=CONTEXT_UNAVAILABLE,
                    reasons=("OFP_UNAVAILABLE",),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=graph_version,
                    detail=str(exc),
                )
            if not isinstance(response, Mapping) or response.get("status") != "OK":
                code = str(response.get("code") or "UNKNOWN") if isinstance(response, Mapping) else "UNKNOWN"
                detail = str(response.get("detail") or "") if isinstance(response, Mapping) else None
                return DecisionContextResult(
                    status=CONTEXT_UNAVAILABLE,
                    reasons=(f"OFP_ERROR:{code}",),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=None,
                    feature_group_versions={},
                    graph_version=graph_version,
                    detail=detail,
                )
            ofp_snapshot = dict(response.get("snapshot") or {})
            for group in list(ofp_snapshot.get("feature_groups") or []):
                if not isinstance(group, Mapping):
                    continue
                name = str(group.get("name") or "").strip()
                version = str(group.get("version") or "").strip()
                if name and version:
                    feature_group_versions[name] = version

            evidence = ContextEvidence(
                source_eb_ref=candidate.source_eb_ref.as_dict(),
                context_refs=normalized_context_refs,
                ofp_snapshot_hash=str(ofp_snapshot.get("snapshot_hash") or "") or None,
                ofp_eb_offset_basis=_coerce_mapping(ofp_snapshot.get("eb_offset_basis")),
                graph_version=_coerce_mapping(ofp_snapshot.get("graph_version")) or graph_version,
            )

            missing_groups = _to_list((ofp_snapshot.get("freshness") or {}).get("missing_groups"))
            missing_keys = _to_list((ofp_snapshot.get("freshness") or {}).get("missing_feature_keys"))
            missing_reasons = [
                *(f"OFP_MISSING_GROUP:{name}" for name in missing_groups),
                *(f"OFP_MISSING_FEATURE:{name}" for name in missing_keys),
            ]
            if missing_reasons:
                return DecisionContextResult(
                    status=CONTEXT_MISSING,
                    reasons=tuple(sorted(set(missing_reasons))),
                    budget=budget,
                    enforcement=enforcement,
                    evidence=evidence,
                    ofp_snapshot=ofp_snapshot,
                    feature_group_versions=feature_group_versions,
                    graph_version=evidence.graph_version,
                    detail=detail,
                )

        return DecisionContextResult(
            status=CONTEXT_READY,
            reasons=tuple(),
            budget=budget,
            enforcement=enforcement,
            evidence=evidence,
            ofp_snapshot=ofp_snapshot,
            feature_group_versions=feature_group_versions,
            graph_version=evidence.graph_version,
            detail=detail,
        )


@dataclass(frozen=True)
class _ContextRequirements:
    feature_groups: tuple[tuple[str, str], ...]
    require_ieg: bool
    require_model_primary: bool
    require_model_stage2: bool
    require_fallback_heuristics: bool
    required_action_posture: str


def _context_requirements(
    policy: DecisionContextPolicy,
    compatibility: RegistryCompatibility | None,
    posture: DfPostureStamp,
) -> _ContextRequirements:
    if compatibility is None:
        action_posture = str(posture.capabilities_mask.action_posture or "").strip().upper() or "NORMAL"
        if action_posture not in {"NORMAL", "STEP_UP_ONLY"}:
            action_posture = "NORMAL"
        return _ContextRequirements(
            feature_groups=policy.ofp_feature_groups,
            require_ieg=policy.require_ieg,
            require_model_primary=False,
            require_model_stage2=False,
            require_fallback_heuristics=False,
            required_action_posture=action_posture,
        )
    feature_groups = compatibility.required_feature_groups or policy.ofp_feature_groups
    return _ContextRequirements(
        feature_groups=feature_groups,
        require_ieg=compatibility.require_ieg or policy.require_ieg,
        require_model_primary=compatibility.require_model_primary,
        require_model_stage2=compatibility.require_model_stage2,
        require_fallback_heuristics=compatibility.require_fallback_heuristics,
        required_action_posture=compatibility.required_action_posture,
    )


def _normalize_context_refs(context_refs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(context_refs, Mapping):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for role, value in context_refs.items():
        name = str(role or "").strip()
        if not name:
            continue
        if isinstance(value, SourceEbRef):
            normalized[name] = value.as_dict()
        elif isinstance(value, Mapping):
            normalized[name] = dict(value)
    return normalized


def _missing_roles(required: tuple[str, ...], refs: Mapping[str, Any]) -> list[str]:
    return [role for role in required if role not in refs]


def _normalize_feature_keys(value: list[dict[str, Any]] | None) -> tuple[list[dict[str, str]], list[str]]:
    if not value:
        return [], []
    if not isinstance(value, list):
        return [], ["OFP_FEATURE_KEYS_INVALID"]
    normalized: list[dict[str, str]] = []
    errors: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            errors.append("OFP_FEATURE_KEYS_INVALID")
            continue
        key_type = str(item.get("key_type") or "").strip()
        key_id = str(item.get("key_id") or "").strip()
        if not key_type or not key_id:
            errors.append("OFP_FEATURE_KEYS_INVALID")
            continue
        normalized.append({"key_type": key_type, "key_id": key_id})
    return normalized, errors


def _parse_feature_groups(value: Any, *, require_ofp: bool) -> list[tuple[str, str]]:
    if value in (None, ""):
        if not require_ofp:
            return []
        raise DecisionContextError("ofp.feature_groups must be provided")
    if not isinstance(value, list):
        raise DecisionContextError("ofp.feature_groups must be a list")
    groups: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise DecisionContextError(f"ofp.feature_groups[{index}] must be a mapping")
        name = _non_empty(item.get("name"), f"ofp.feature_groups[{index}].name")
        version = _non_empty(item.get("version"), f"ofp.feature_groups[{index}].version")
        groups.append((name, version))
    return groups


def _graph_mode_for_enforcement(mode: str, allow_ieg: bool) -> str:
    if not allow_ieg:
        return "none"
    if mode not in {"none", "resolve_if_needed", "require_ieg"}:
        return "resolve_if_needed"
    return mode


def _ofp_request_id(candidate: DecisionTriggerCandidate) -> str:
    payload = {
        "source_event_id": candidate.source_event_id,
        "source_event_type": candidate.source_event_type,
        "source_eb_ref": candidate.source_eb_ref.as_dict(),
    }
    canonical = _canonical_json(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"df_ofp_{digest}"


def _parse_utc(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionContextError(f"{field_name} must be a non-empty string")
    return text


def _positive_int(value: Any, field_name: str) -> int:
    try:
        number = int(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise DecisionContextError(f"{field_name} must be an integer") from exc
    if number <= 0:
        raise DecisionContextError(f"{field_name} must be > 0")
    return number


def _non_empty_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DecisionContextError(f"{field_name} must be a non-empty list")
    return [str(item).strip() for item in value if str(item).strip()]


def _unique_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _to_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
