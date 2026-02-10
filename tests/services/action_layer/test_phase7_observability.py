from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.action_layer.authz import authorize_intent, build_denied_outcome_payload
from fraud_detection.action_layer.contracts import ActionIntent
from fraud_detection.action_layer.execution import (
    EXECUTION_COMMITTED,
    EXECUTION_UNKNOWN_COMMIT,
    ActionExecutionAttempt,
    ActionExecutionTerminal,
    build_execution_outcome_payload,
)
from fraud_detection.action_layer.observability import (
    ActionLayerHealthThresholds,
    ActionLayerObservabilityError,
    ActionLayerRunMetrics,
)


def _intent_payload() -> dict[str, object]:
    return {
        "action_id": "1" * 32,
        "decision_id": "2" * 32,
        "action_kind": "txn_disposition_publish",
        "idempotency_key": "merchant_42:evt_123:publish",
        "pins": {
            "platform_run_id": "platform_20260207T190000Z",
            "scenario_run_id": "3" * 32,
            "manifest_fingerprint": "4" * 64,
            "parameter_hash": "5" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "requested_at_utc": "2026-02-07T19:00:00.000000Z",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "policy_rev": {"policy_id": "al.policy.v0", "revision": "r1"},
        "run_config_digest": "7" * 64,
        "action_payload": {
            "target": "fraud.disposition",
            "api_key": "live-secret-123",
            "nested": {"refresh_token": "abc123"},
        },
    }


def _terminal(state: str) -> ActionExecutionTerminal:
    if state == EXECUTION_UNKNOWN_COMMIT:
        attempts = (
            ActionExecutionAttempt(
                attempt_seq=1,
                state=EXECUTION_UNKNOWN_COMMIT,
                provider_code="UNCERTAIN",
                provider_ref="provider-1",
                message="unknown commit",
            ),
        )
        return ActionExecutionTerminal(
            terminal_state="UNCERTAIN_COMMIT",
            reason_code="UNCERTAIN_COMMIT:UNCERTAIN",
            final_attempt_seq=1,
            attempts=attempts,
            final_provider_code="UNCERTAIN",
            final_provider_ref="provider-1",
        )

    attempts = (
        ActionExecutionAttempt(
            attempt_seq=1,
            state=EXECUTION_COMMITTED,
            provider_code="OK",
            provider_ref="provider-2",
            message="committed",
        ),
    )
    return ActionExecutionTerminal(
        terminal_state="EXECUTED",
        reason_code="EXECUTED",
        final_attempt_seq=1,
        attempts=attempts,
        final_provider_code="OK",
        final_provider_ref="provider-2",
    )


def test_phase7_metrics_cover_required_lanes() -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    metrics = ActionLayerRunMetrics(
        platform_run_id=str(intent.payload["pins"]["platform_run_id"]),
        scenario_run_id=str(intent.payload["pins"]["scenario_run_id"]),
    )
    metrics.record_intake(intent_payload=intent.as_dict())

    uncertain_terminal = _terminal(EXECUTION_UNKNOWN_COMMIT)
    metrics.record_execution_terminal(terminal=uncertain_terminal)
    failed_payload = build_execution_outcome_payload(
        intent=intent,
        authz_policy_rev={"policy_id": "al.policy.v0", "revision": "r1"},
        terminal=uncertain_terminal,
        completed_at_utc="2026-02-07T19:00:10.000000Z",
    )
    metrics.record_outcome(outcome_payload=failed_payload)
    metrics.record_publish(decision="AMBIGUOUS", reason_code="IG_PUSH_RETRY_EXHAUSTED:timeout")

    denied_decision = authorize_intent(intent, bundle=None)
    denied_payload = build_denied_outcome_payload(
        intent=intent,
        decision=denied_decision,
        completed_at_utc="2026-02-07T19:00:11.000000Z",
    )
    metrics.record_outcome(outcome_payload=denied_payload)
    metrics.record_publish(decision="QUARANTINE", reason_code="IG_POLICY_REJECTED")

    snapshot = metrics.snapshot(generated_at_utc="2026-02-07T19:00:20.000000Z")
    counters = snapshot["metrics"]

    assert counters["intake_total"] == 1
    assert counters["execution_attempts_total"] == 1
    assert counters["execution_retries_total"] == 0
    assert counters["unknown_commit_total"] == 1
    assert counters["outcome_failed_total"] == 1
    assert counters["outcome_denied_total"] == 1
    assert counters["publish_ambiguous_total"] == 1
    assert counters["publish_quarantine_total"] == 1


def test_phase7_health_posture_reason_codes() -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    metrics = ActionLayerRunMetrics(
        platform_run_id=str(intent.payload["pins"]["platform_run_id"]),
        scenario_run_id=str(intent.payload["pins"]["scenario_run_id"]),
    )
    for _ in range(10):
        metrics.record_intake(intent_payload=intent.as_dict())
    metrics.counters["outcome_failed_total"] = 1

    thresholds = ActionLayerHealthThresholds(
        amber_lag_events=5,
        red_lag_events=10,
        amber_queue_depth=10,
        red_queue_depth=20,
        amber_error_rate=0.05,
        red_error_rate=0.2,
    )
    amber = metrics.evaluate_health(lag_events=1, queue_depth=1, thresholds=thresholds)
    assert amber.state == "AMBER"
    assert "ERROR_RATE_AMBER" in amber.reason_codes

    red = metrics.evaluate_health(lag_events=11, queue_depth=25, thresholds=thresholds)
    assert red.state == "RED"
    assert "LAG_RED" in red.reason_codes
    assert "QUEUE_RED" in red.reason_codes


def test_phase7_execution_outcome_has_governance_stamps() -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    terminal = _terminal(EXECUTION_COMMITTED)
    payload = build_execution_outcome_payload(
        intent=intent,
        authz_policy_rev={"policy_id": "al.policy.v0", "revision": "r2"},
        terminal=terminal,
        completed_at_utc="2026-02-07T19:00:30.000000Z",
    )

    governance = payload["outcome_payload"]["governance"]
    assert governance["policy_rev"]["policy_id"] == "al.policy.v0"
    assert governance["policy_rev"]["revision"] == "r2"
    assert governance["execution_profile_ref"].startswith("policy://al.policy.v0@r2#mode=")
    assert governance["actor_principal"] == payload["actor_principal"]
    assert governance["origin"] == payload["origin"]


def test_phase7_export_redacts_sensitive_fields(tmp_path: Path) -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    metrics = ActionLayerRunMetrics(
        platform_run_id=str(intent.payload["pins"]["platform_run_id"]),
        scenario_run_id=str(intent.payload["pins"]["scenario_run_id"]),
    )
    metrics.record_intake(intent_payload=intent.as_dict())
    out = tmp_path / "al_phase7_metrics.json"
    metrics.export(output_path=out, generated_at_utc="2026-02-07T19:00:40.000000Z")

    payload = json.loads(out.read_text(encoding="utf-8"))
    intake_events = [item for item in payload["recent_events"] if item["event_type"] == "intent_intake"]
    assert intake_events
    action_payload = intake_events[0]["payload"]["action_payload"]
    assert action_payload["api_key"] == "[REDACTED]"
    assert action_payload["nested"]["refresh_token"] == "[REDACTED]"


def test_phase7_run_scope_mismatch_fails_closed() -> None:
    intent_payload = _intent_payload()
    metrics = ActionLayerRunMetrics(
        platform_run_id="platform_20260207T190001Z",
        scenario_run_id="a" * 32,
    )
    with pytest.raises(ActionLayerObservabilityError):
        metrics.record_intake(intent_payload=intent_payload)
