"""Action Layer authorization and execution-posture gate (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from .contracts import ActionIntent
from .policy import AlExecutionPosture, AlPolicyBundle, AlPolicyRev


AUTHZ_ALLOW = "ALLOW"
AUTHZ_DENY = "DENY"


@dataclass(frozen=True)
class AlAuthzDecision:
    disposition: str
    reason_codes: tuple[str, ...]
    policy_rev: AlPolicyRev
    posture_mode: str
    fail_safe: bool

    @property
    def allowed(self) -> bool:
        return self.disposition == AUTHZ_ALLOW


def authorize_intent(intent: ActionIntent, *, bundle: AlPolicyBundle | None) -> AlAuthzDecision:
    if bundle is None:
        return AlAuthzDecision(
            disposition=AUTHZ_DENY,
            reason_codes=("POSTURE_MISSING_FAIL_SAFE",),
            policy_rev=AlPolicyRev(
                policy_id="al.authz.fail_safe",
                revision="missing_policy",
                content_digest="0" * 64,
            ),
            posture_mode="FAIL_CLOSED",
            fail_safe=True,
        )

    posture = bundle.execution_posture
    if not _posture_allows_execution(posture):
        reason = posture.reason.strip() or "POSTURE_BLOCKED"
        return AlAuthzDecision(
            disposition=AUTHZ_DENY,
            reason_codes=(f"POSTURE_BLOCK:{posture.mode}", reason),
            policy_rev=bundle.policy_rev,
            posture_mode=posture.mode,
            fail_safe=True,
        )

    payload = intent.as_dict()
    origin = str(payload["origin"])
    action_kind = str(payload["action_kind"])
    actor_principal = str(payload["actor_principal"])
    reasons: list[str] = []

    if origin not in bundle.authz.allowed_origins:
        reasons.append("AUTHZ_ORIGIN_DENY")
    if action_kind not in bundle.authz.allowed_action_kinds:
        reasons.append("AUTHZ_ACTION_KIND_DENY")
    prefixes = bundle.authz.actor_principal_prefix_allowlist.get(origin, tuple())
    if prefixes and not any(actor_principal.startswith(prefix) for prefix in prefixes):
        reasons.append("AUTHZ_ACTOR_PRINCIPAL_DENY")

    if reasons:
        return AlAuthzDecision(
            disposition=AUTHZ_DENY,
            reason_codes=tuple(sorted(set(reasons))),
            policy_rev=bundle.policy_rev,
            posture_mode=posture.mode,
            fail_safe=False,
        )

    return AlAuthzDecision(
        disposition=AUTHZ_ALLOW,
        reason_codes=(),
        policy_rev=bundle.policy_rev,
        posture_mode=posture.mode,
        fail_safe=False,
    )


def build_denied_outcome_payload(
    *,
    intent: ActionIntent,
    decision: AlAuthzDecision,
    completed_at_utc: str | None = None,
) -> dict[str, Any]:
    payload = intent.as_dict()
    ts = completed_at_utc or datetime.now(tz=timezone.utc).isoformat()
    reason = ";".join(decision.reason_codes) if decision.reason_codes else "AUTHZ_DENIED"
    identity = {
        "decision_id": payload["decision_id"],
        "action_id": payload["action_id"],
        "idempotency_key": payload["idempotency_key"],
        "status": "DENIED",
        "authz_policy_rev": decision.policy_rev.as_dict(),
        "reason": reason,
    }
    outcome_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]
    return {
        "outcome_id": outcome_id,
        "decision_id": payload["decision_id"],
        "action_id": payload["action_id"],
        "action_kind": payload["action_kind"],
        "status": "DENIED",
        "idempotency_key": payload["idempotency_key"],
        "actor_principal": payload["actor_principal"],
        "origin": payload["origin"],
        "authz_policy_rev": decision.policy_rev.as_dict(),
        "run_config_digest": payload["run_config_digest"],
        "pins": payload["pins"],
        "completed_at_utc": ts,
        "attempt_seq": 1,
        "reason": reason,
    }


def _posture_allows_execution(posture: AlExecutionPosture) -> bool:
    mode = str(posture.mode).strip().upper()
    if mode not in {"NORMAL", "DRAIN", "FAIL_CLOSED"}:
        return False
    if mode != "NORMAL":
        return False
    return bool(posture.allow_execution)

