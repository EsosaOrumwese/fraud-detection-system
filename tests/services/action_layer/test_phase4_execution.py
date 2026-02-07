from __future__ import annotations

from pathlib import Path

from fraud_detection.action_layer.contracts import ActionIntent, ActionOutcome
from fraud_detection.action_layer.execution import (
    EXECUTION_COMMITTED,
    EXECUTION_PERMANENT_ERROR,
    EXECUTION_RETRYABLE_ERROR,
    EXECUTION_UNKNOWN_COMMIT,
    TERMINAL_EXECUTED,
    TERMINAL_FAILED,
    TERMINAL_UNCERTAIN_COMMIT,
    ActionExecutionEngine,
    ActionExecutionRequest,
    ActionExecutionResult,
    build_execution_outcome_payload,
)
from fraud_detection.action_layer.idempotency import ActionIdempotencyGate
from fraud_detection.action_layer.policy import load_policy_bundle
from fraud_detection.action_layer.storage import ActionLedgerStore


class SequenceExecutor:
    def __init__(self, states: list[ActionExecutionResult]) -> None:
        self._states = list(states)
        self.requests: list[ActionExecutionRequest] = []

    def execute(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        self.requests.append(request)
        if not self._states:
            return ActionExecutionResult(
                state=EXECUTION_PERMANENT_ERROR,
                provider_code="NO_STATE",
                message="no planned state",
            )
        return self._states.pop(0)


def _intent_payload() -> dict[str, object]:
    return {
        "action_id": "1" * 32,
        "decision_id": "2" * 32,
        "action_kind": "txn_disposition_publish",
        "idempotency_key": "merchant_42:evt_123:publish",
        "pins": {
            "platform_run_id": "platform_20260207T185000Z",
            "scenario_run_id": "3" * 32,
            "manifest_fingerprint": "4" * 64,
            "parameter_hash": "5" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "requested_at_utc": "2026-02-07T18:50:00.000000Z",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "policy_rev": {"policy_id": "al.policy.v0", "revision": "r1"},
        "run_config_digest": "7" * 64,
        "action_payload": {"target": "fraud.disposition"},
    }


def _semantic_key(intent: ActionIntent, tmp_path: Path) -> str:
    gate = ActionIdempotencyGate(store=ActionLedgerStore(locator=str(tmp_path / "al_phase4.sqlite")))
    decision = gate.evaluate(intent=intent, first_seen_at_utc="2026-02-07T18:50:00.000000Z")
    return decision.semantic_key


def test_execution_engine_retries_then_commits_with_bounded_attempts(tmp_path: Path) -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    semantic_key = _semantic_key(intent, tmp_path)
    bundle = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))

    executor = SequenceExecutor(
        [
            ActionExecutionResult(state=EXECUTION_RETRYABLE_ERROR, provider_code="TIMEOUT"),
            ActionExecutionResult(state=EXECUTION_RETRYABLE_ERROR, provider_code="RATE_LIMIT"),
            ActionExecutionResult(state=EXECUTION_COMMITTED, provider_code="OK", provider_ref="r-123"),
        ]
    )
    engine = ActionExecutionEngine(executor=executor, retry_policy=bundle.retry_policy)
    terminal = engine.execute(intent=intent, semantic_key=semantic_key)

    assert terminal.terminal_state == TERMINAL_EXECUTED
    assert terminal.final_attempt_seq == 3
    assert len(terminal.attempts) == 3
    assert all(req.idempotency_token == semantic_key for req in executor.requests)


def test_execution_engine_emits_retry_exhausted_terminal_failure(tmp_path: Path) -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    semantic_key = _semantic_key(intent, tmp_path)
    bundle = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))

    executor = SequenceExecutor(
        [
            ActionExecutionResult(state=EXECUTION_RETRYABLE_ERROR, provider_code="TIMEOUT"),
            ActionExecutionResult(state=EXECUTION_RETRYABLE_ERROR, provider_code="TIMEOUT"),
            ActionExecutionResult(state=EXECUTION_RETRYABLE_ERROR, provider_code="TIMEOUT"),
        ]
    )
    engine = ActionExecutionEngine(executor=executor, retry_policy=bundle.retry_policy)
    terminal = engine.execute(intent=intent, semantic_key=semantic_key)

    assert terminal.terminal_state == TERMINAL_FAILED
    assert terminal.reason_code == "RETRY_EXHAUSTED:TIMEOUT"
    assert terminal.final_attempt_seq == bundle.retry_policy.max_attempts


def test_execution_engine_maps_unknown_commit_to_explicit_terminal_lane(tmp_path: Path) -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    semantic_key = _semantic_key(intent, tmp_path)
    bundle = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))
    executor = SequenceExecutor(
        [ActionExecutionResult(state=EXECUTION_UNKNOWN_COMMIT, provider_code="PROVIDER_UNCERTAIN")]
    )
    engine = ActionExecutionEngine(executor=executor, retry_policy=bundle.retry_policy)
    terminal = engine.execute(intent=intent, semantic_key=semantic_key)

    assert terminal.terminal_state == TERMINAL_UNCERTAIN_COMMIT
    assert terminal.reason_code == "UNCERTAIN_COMMIT:PROVIDER_UNCERTAIN"
    assert terminal.final_attempt_seq == 1


def test_execution_outcome_payload_is_contract_valid_for_uncertain_lane(tmp_path: Path) -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    semantic_key = _semantic_key(intent, tmp_path)
    bundle = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))
    executor = SequenceExecutor(
        [ActionExecutionResult(state=EXECUTION_UNKNOWN_COMMIT, provider_code="PROVIDER_UNCERTAIN")]
    )
    engine = ActionExecutionEngine(executor=executor, retry_policy=bundle.retry_policy)
    terminal = engine.execute(intent=intent, semantic_key=semantic_key)
    outcome_payload = build_execution_outcome_payload(
        intent=intent,
        authz_policy_rev=bundle.policy_rev.as_dict(),
        terminal=terminal,
        completed_at_utc="2026-02-07T18:50:10.000000Z",
    )
    outcome = ActionOutcome.from_payload(outcome_payload)
    assert outcome.payload["status"] == "FAILED"
    assert outcome.payload["reason"].startswith("UNCERTAIN_COMMIT:")
    assert outcome.payload["outcome_payload"]["terminal_state"] == TERMINAL_UNCERTAIN_COMMIT

