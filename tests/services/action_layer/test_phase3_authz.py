from __future__ import annotations

from pathlib import Path

from fraud_detection.action_layer.authz import (
    AUTHZ_ALLOW,
    AUTHZ_DENY,
    authorize_intent,
    build_denied_outcome_payload,
)
from fraud_detection.action_layer.contracts import ActionIntent, ActionOutcome
from fraud_detection.action_layer.policy import (
    AlExecutionPosture,
    AlPolicyBundle,
    AlRetryPolicy,
    load_policy_bundle,
)


def _intent_payload() -> dict[str, object]:
    return {
        "action_id": "1" * 32,
        "decision_id": "2" * 32,
        "action_kind": "txn_disposition_publish",
        "idempotency_key": "merchant_42:evt_123:publish",
        "pins": {
            "platform_run_id": "platform_20260207T184000Z",
            "scenario_run_id": "3" * 32,
            "manifest_fingerprint": "4" * 64,
            "parameter_hash": "5" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "requested_at_utc": "2026-02-07T18:40:00.000000Z",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "policy_rev": {"policy_id": "al.policy.v0", "revision": "r1"},
        "run_config_digest": "7" * 64,
        "action_payload": {"target": "fraud.disposition"},
    }


def test_authorize_intent_allows_when_policy_and_posture_are_ok() -> None:
    bundle = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))
    intent = ActionIntent.from_payload(_intent_payload())
    decision = authorize_intent(intent, bundle=bundle)
    assert decision.disposition == AUTHZ_ALLOW
    assert decision.allowed is True
    assert decision.reason_codes == ()


def test_authorize_intent_denies_when_action_kind_not_allowed() -> None:
    bundle = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))
    payload = _intent_payload()
    payload["action_kind"] = "unsupported_action"
    intent = ActionIntent.from_payload(payload)
    decision = authorize_intent(intent, bundle=bundle)
    assert decision.disposition == AUTHZ_DENY
    assert "AUTHZ_ACTION_KIND_DENY" in decision.reason_codes


def test_authorize_intent_fail_safe_when_posture_blocks_execution() -> None:
    bundle = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))
    blocked_bundle = AlPolicyBundle(
        version=bundle.version,
        policy_rev=bundle.policy_rev,
        execution_posture=AlExecutionPosture(mode="DRAIN", allow_execution=False, reason="operator_drain"),
        authz=bundle.authz,
        retry_policy=AlRetryPolicy(max_attempts=3, base_backoff_ms=100, max_backoff_ms=1000),
    )
    intent = ActionIntent.from_payload(_intent_payload())
    decision = authorize_intent(intent, bundle=blocked_bundle)
    assert decision.disposition == AUTHZ_DENY
    assert decision.fail_safe is True
    assert "POSTURE_BLOCK:DRAIN" in decision.reason_codes


def test_authorize_intent_fail_safe_when_policy_missing() -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    decision = authorize_intent(intent, bundle=None)
    assert decision.disposition == AUTHZ_DENY
    assert decision.fail_safe is True
    assert "POSTURE_MISSING_FAIL_SAFE" in decision.reason_codes


def test_denied_outcome_payload_includes_policy_rev_stamp_and_is_contract_valid() -> None:
    bundle = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))
    payload = _intent_payload()
    payload["action_kind"] = "unsupported_action"
    intent = ActionIntent.from_payload(payload)
    decision = authorize_intent(intent, bundle=bundle)
    denied = build_denied_outcome_payload(intent=intent, decision=decision, completed_at_utc="2026-02-07T18:41:00.000000Z")
    assert denied["status"] == "DENIED"
    assert denied["authz_policy_rev"]["policy_id"] == bundle.policy_rev.policy_id
    outcome = ActionOutcome.from_payload(denied)
    assert outcome.payload["status"] == "DENIED"
