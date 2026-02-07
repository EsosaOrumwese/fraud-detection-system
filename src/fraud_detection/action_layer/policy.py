"""Action Layer authz/posture policy loader (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


AL_POSTURE_MODES: set[str] = {"NORMAL", "DRAIN", "FAIL_CLOSED"}


class ActionLayerPolicyError(ValueError):
    """Raised when AL policy payloads are invalid."""


@dataclass(frozen=True)
class AlPolicyRev:
    policy_id: str
    revision: str
    content_digest: str

    def as_dict(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "revision": self.revision,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True)
class AlExecutionPosture:
    mode: str
    allow_execution: bool
    reason: str


@dataclass(frozen=True)
class AlAuthzPolicy:
    allowed_origins: tuple[str, ...]
    allowed_action_kinds: tuple[str, ...]
    actor_principal_prefix_allowlist: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class AlRetryPolicy:
    max_attempts: int
    base_backoff_ms: int
    max_backoff_ms: int


@dataclass(frozen=True)
class AlPolicyBundle:
    version: str
    policy_rev: AlPolicyRev
    execution_posture: AlExecutionPosture
    authz: AlAuthzPolicy
    retry_policy: AlRetryPolicy


def load_policy_bundle(path: Path) -> AlPolicyBundle:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ActionLayerPolicyError("AL policy bundle must be a mapping")

    version = _require_non_empty_str(payload.get("version"), "version")
    policy_id = _require_non_empty_str(payload.get("policy_id"), "policy_id")
    revision = _require_non_empty_str(payload.get("revision"), "revision")

    posture_payload = payload.get("execution_posture")
    if not isinstance(posture_payload, Mapping):
        raise ActionLayerPolicyError("execution_posture must be a mapping")
    posture_mode = _require_non_empty_str(posture_payload.get("mode"), "execution_posture.mode").upper()
    if posture_mode not in AL_POSTURE_MODES:
        raise ActionLayerPolicyError(
            f"execution_posture.mode must be one of {sorted(AL_POSTURE_MODES)}"
        )
    posture = AlExecutionPosture(
        mode=posture_mode,
        allow_execution=bool(posture_payload.get("allow_execution", posture_mode == "NORMAL")),
        reason=str(posture_payload.get("reason") or "").strip(),
    )

    authz_payload = payload.get("authz")
    if not isinstance(authz_payload, Mapping):
        raise ActionLayerPolicyError("authz must be a mapping")
    allowed_origins = tuple(sorted(set(_to_non_empty_list(authz_payload.get("allowed_origins"), "authz.allowed_origins"))))
    allowed_action_kinds = tuple(
        sorted(set(_to_non_empty_list(authz_payload.get("allowed_action_kinds"), "authz.allowed_action_kinds")))
    )
    allowlist_raw = authz_payload.get("actor_principal_prefix_allowlist")
    if not isinstance(allowlist_raw, Mapping):
        raise ActionLayerPolicyError("authz.actor_principal_prefix_allowlist must be a mapping")
    actor_allow: dict[str, tuple[str, ...]] = {}
    for origin in allowed_origins:
        prefixes = allowlist_raw.get(origin)
        if prefixes is None:
            actor_allow[origin] = tuple()
            continue
        actor_allow[origin] = tuple(sorted(set(_to_non_empty_list(prefixes, f"authz.actor_principal_prefix_allowlist.{origin}"))))

    retry_payload = payload.get("retry")
    if retry_payload is None:
        retry = AlRetryPolicy(max_attempts=3, base_backoff_ms=100, max_backoff_ms=1000)
    else:
        if not isinstance(retry_payload, Mapping):
            raise ActionLayerPolicyError("retry must be a mapping when provided")
        max_attempts = _to_positive_int(retry_payload.get("max_attempts"), "retry.max_attempts")
        base_backoff_ms = _to_positive_int(retry_payload.get("base_backoff_ms"), "retry.base_backoff_ms")
        max_backoff_ms = _to_positive_int(retry_payload.get("max_backoff_ms"), "retry.max_backoff_ms")
        if max_backoff_ms < base_backoff_ms:
            raise ActionLayerPolicyError("retry.max_backoff_ms must be >= retry.base_backoff_ms")
        retry = AlRetryPolicy(
            max_attempts=max_attempts,
            base_backoff_ms=base_backoff_ms,
            max_backoff_ms=max_backoff_ms,
        )

    digest_payload = {
        "version": version,
        "policy_id": policy_id,
        "revision": revision,
        "execution_posture": {
            "mode": posture.mode,
            "allow_execution": posture.allow_execution,
            "reason": posture.reason,
        },
        "authz": {
            "allowed_origins": list(allowed_origins),
            "allowed_action_kinds": list(allowed_action_kinds),
            "actor_principal_prefix_allowlist": {k: list(v) for k, v in sorted(actor_allow.items())},
        },
        "retry": {
            "max_attempts": retry.max_attempts,
            "base_backoff_ms": retry.base_backoff_ms,
            "max_backoff_ms": retry.max_backoff_ms,
        },
    }
    canonical = json.dumps(digest_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return AlPolicyBundle(
        version=version,
        policy_rev=AlPolicyRev(policy_id=policy_id, revision=revision, content_digest=content_digest),
        execution_posture=posture,
        authz=AlAuthzPolicy(
            allowed_origins=allowed_origins,
            allowed_action_kinds=allowed_action_kinds,
            actor_principal_prefix_allowlist=actor_allow,
        ),
        retry_policy=retry,
    )


def _require_non_empty_str(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ActionLayerPolicyError(f"{field_name} must be a non-empty string")
    return text


def _to_non_empty_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ActionLayerPolicyError(f"{field_name} must be a non-empty list")
    normalized: list[str] = []
    for idx, item in enumerate(value):
        text = str(item or "").strip()
        if not text:
            raise ActionLayerPolicyError(f"{field_name}[{idx}] must be non-empty")
        normalized.append(text)
    return normalized


def _to_positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ActionLayerPolicyError(f"{field_name} must be a positive integer") from exc
    if parsed <= 0:
        raise ActionLayerPolicyError(f"{field_name} must be a positive integer")
    return parsed
