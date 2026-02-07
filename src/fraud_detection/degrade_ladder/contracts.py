"""DL contract helpers (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

MODE_SEQUENCE: tuple[str, ...] = ("NORMAL", "DEGRADED_1", "DEGRADED_2", "FAIL_CLOSED")
ACTION_POSTURES: set[str] = {"NORMAL", "STEP_UP_ONLY"}
CAPABILITY_KEYS: tuple[str, ...] = (
    "allow_ieg",
    "allowed_feature_groups",
    "allow_model_primary",
    "allow_model_stage2",
    "allow_fallback_heuristics",
    "action_posture",
)


class DegradeContractError(ValueError):
    """Raised when degrade posture payloads violate the DL contract."""


@dataclass(frozen=True)
class PolicyRev:
    policy_id: str
    revision: str
    content_digest: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PolicyRev":
        if not isinstance(payload, dict):
            raise DegradeContractError("policy_rev must be a mapping")
        policy_id = str(payload.get("policy_id") or "").strip()
        revision = str(payload.get("revision") or "").strip()
        if not policy_id or not revision:
            raise DegradeContractError("policy_rev requires non-empty policy_id and revision")
        digest = payload.get("content_digest")
        if digest is None or str(digest).strip() == "":
            return cls(policy_id=policy_id, revision=revision, content_digest=None)
        return cls(policy_id=policy_id, revision=revision, content_digest=str(digest))

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"policy_id": self.policy_id, "revision": self.revision}
        if self.content_digest:
            payload["content_digest"] = self.content_digest
        return payload


@dataclass(frozen=True)
class CapabilitiesMask:
    allow_ieg: bool
    allowed_feature_groups: tuple[str, ...]
    allow_model_primary: bool
    allow_model_stage2: bool
    allow_fallback_heuristics: bool
    action_posture: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CapabilitiesMask":
        if not isinstance(payload, dict):
            raise DegradeContractError("capabilities_mask must be a mapping")
        missing = [key for key in CAPABILITY_KEYS if key not in payload]
        if missing:
            raise DegradeContractError(f"capabilities_mask missing keys: {','.join(missing)}")
        unknown = sorted(set(payload) - set(CAPABILITY_KEYS))
        if unknown:
            raise DegradeContractError(f"capabilities_mask has unknown keys: {','.join(unknown)}")

        feature_groups = payload.get("allowed_feature_groups")
        if not isinstance(feature_groups, list):
            raise DegradeContractError("allowed_feature_groups must be a list")
        normalized_groups: list[str] = []
        for index, item in enumerate(feature_groups):
            group = str(item).strip()
            if not group:
                raise DegradeContractError(f"allowed_feature_groups[{index}] must be a non-empty string")
            normalized_groups.append(group)

        action_posture = str(payload.get("action_posture") or "").strip()
        if action_posture not in ACTION_POSTURES:
            raise DegradeContractError(
                f"action_posture must be one of {sorted(ACTION_POSTURES)}: {action_posture!r}"
            )

        bool_fields = {
            "allow_ieg": payload.get("allow_ieg"),
            "allow_model_primary": payload.get("allow_model_primary"),
            "allow_model_stage2": payload.get("allow_model_stage2"),
            "allow_fallback_heuristics": payload.get("allow_fallback_heuristics"),
        }
        for field_name, value in bool_fields.items():
            if not isinstance(value, bool):
                raise DegradeContractError(f"{field_name} must be boolean")

        return cls(
            allow_ieg=bool_fields["allow_ieg"],
            allowed_feature_groups=tuple(normalized_groups),
            allow_model_primary=bool_fields["allow_model_primary"],
            allow_model_stage2=bool_fields["allow_model_stage2"],
            allow_fallback_heuristics=bool_fields["allow_fallback_heuristics"],
            action_posture=action_posture,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "allow_ieg": self.allow_ieg,
            "allowed_feature_groups": list(self.allowed_feature_groups),
            "allow_model_primary": self.allow_model_primary,
            "allow_model_stage2": self.allow_model_stage2,
            "allow_fallback_heuristics": self.allow_fallback_heuristics,
            "action_posture": self.action_posture,
        }


@dataclass(frozen=True)
class DegradeDecision:
    mode: str
    capabilities_mask: CapabilitiesMask
    policy_rev: PolicyRev
    posture_seq: int
    decided_at_utc: str
    reason: str | None = None
    evidence_refs: tuple[dict[str, str], ...] = ()

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DegradeDecision":
        if not isinstance(payload, dict):
            raise DegradeContractError("degrade decision payload must be a mapping")
        required = ["mode", "capabilities_mask", "policy_rev", "posture_seq", "decided_at_utc"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise DegradeContractError(f"degrade decision missing fields: {','.join(missing)}")

        mode = str(payload.get("mode") or "").strip()
        if mode not in MODE_SEQUENCE:
            raise DegradeContractError(f"mode must be one of {MODE_SEQUENCE}: {mode!r}")

        posture_seq = payload.get("posture_seq")
        if not isinstance(posture_seq, int) or posture_seq < 0:
            raise DegradeContractError("posture_seq must be a non-negative integer")

        decided_at_utc = str(payload.get("decided_at_utc") or "").strip()
        if not decided_at_utc:
            raise DegradeContractError("decided_at_utc is required")

        reason = payload.get("reason")
        normalized_reason = None if reason in (None, "") else str(reason)

        evidence_refs = _parse_evidence_refs(payload.get("evidence_refs"))
        capabilities_payload = payload.get("capabilities_mask")
        policy_rev_payload = payload.get("policy_rev")
        return cls(
            mode=mode,
            capabilities_mask=CapabilitiesMask.from_payload(capabilities_payload),  # type: ignore[arg-type]
            policy_rev=PolicyRev.from_payload(policy_rev_payload),  # type: ignore[arg-type]
            posture_seq=posture_seq,
            decided_at_utc=decided_at_utc,
            reason=normalized_reason,
            evidence_refs=tuple(evidence_refs),
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": self.mode,
            "capabilities_mask": self.capabilities_mask.as_dict(),
            "policy_rev": self.policy_rev.as_dict(),
            "posture_seq": self.posture_seq,
            "decided_at_utc": self.decided_at_utc,
        }
        if self.reason:
            payload["reason"] = self.reason
        if self.evidence_refs:
            payload["evidence_refs"] = list(self.evidence_refs)
        return payload

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def ensure_mode_sequence(mode_sequence: list[str]) -> tuple[str, ...]:
    normalized = tuple(str(mode).strip() for mode in mode_sequence)
    if normalized != MODE_SEQUENCE:
        raise DegradeContractError(
            f"mode_sequence must be exactly {MODE_SEQUENCE}; got {normalized}"
        )
    return normalized


def _parse_evidence_refs(value: Any) -> list[dict[str, str]]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise DegradeContractError("evidence_refs must be a list when provided")
    refs: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DegradeContractError(f"evidence_refs[{index}] must be a mapping")
        kind = str(item.get("kind") or "").strip()
        ref = str(item.get("ref") or "").strip()
        if not kind or not ref:
            raise DegradeContractError(f"evidence_refs[{index}] requires non-empty kind and ref")
        refs.append({"kind": kind, "ref": ref})
    return refs
