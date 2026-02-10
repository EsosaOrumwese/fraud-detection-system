from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from fraud_detection.case_trigger.adapters import (
    CaseTriggerAdapterError,
    adapt_case_trigger_from_source,
    adapt_from_df_decision,
)
from fraud_detection.case_trigger.checkpoints import (
    CHECKPOINT_COMMITTED,
    CaseTriggerCheckpointGate,
)
from fraud_detection.case_trigger.config import load_trigger_policy
from fraud_detection.case_trigger.observability import (
    CaseTriggerGovernanceEmitter,
    CaseTriggerRunMetrics,
)
from fraud_detection.case_trigger.publish import (
    PUBLISH_ADMIT,
    PUBLISH_DUPLICATE,
    CaseTriggerIgPublisher,
)
from fraud_detection.case_trigger.reconciliation import CaseTriggerReconciliationBuilder
from fraud_detection.case_trigger.replay import (
    REPLAY_MATCH,
    REPLAY_NEW,
    REPLAY_PAYLOAD_MISMATCH,
    CaseTriggerReplayLedger,
)
from fraud_detection.scenario_runner.storage import LocalObjectStore


PINS = {
    "platform_run_id": "platform_20260209T180000Z",
    "scenario_run_id": "1" * 32,
    "manifest_fingerprint": "2" * 64,
    "parameter_hash": "3" * 64,
    "scenario_id": "scenario.v0",
    "seed": 42,
}


@dataclass(frozen=True)
class _ParityProof:
    expected_events: int
    triggers_seen_total: int
    published_total: int
    duplicate_total: int
    quarantine_total: int
    publish_ambiguous_total: int
    replay_payload_mismatch_total: int
    checkpoint_committed_total: int
    status: str
    reasons: tuple[str, ...]
    artifact_path: str


@dataclass(frozen=True)
class _Processed:
    replay_outcome: str
    publish_decision: str
    checkpoint_status: str


class _Response:
    def __init__(self, *, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body, sort_keys=True)

    def json(self) -> dict[str, Any]:
        return dict(self._body)


class _Session:
    def __init__(self) -> None:
        self.seen_event_ids: set[str] = set()
        self.requests: list[dict[str, Any]] = []

    def post(self, url: str, json: Mapping[str, Any], timeout: float, headers: Mapping[str, str]) -> _Response:
        payload = dict(json)
        self.requests.append(payload)
        event_id = str(payload.get("event_id") or "")
        if event_id in self.seen_event_ids:
            decision = PUBLISH_DUPLICATE
            receipt_id = f"ct_dup_{event_id}"
        else:
            self.seen_event_ids.add(event_id)
            decision = PUBLISH_ADMIT
            receipt_id = f"ct_admit_{event_id}"
        return _Response(
            status_code=200,
            body={
                "decision": decision,
                "receipt": {"receipt_id": receipt_id, "event_id": event_id},
                "receipt_ref": f"runs/fraud-platform/{PINS['platform_run_id']}/ig/receipts/{receipt_id}.json",
            },
        )


def _policy():
    return load_trigger_policy(Path("config/platform/case_trigger/trigger_policy_v0.yaml"))


def _decision_id(index: int) -> str:
    return f"{index + 1:032x}"[-32:]


def _decision_payload(*, index: int, action_kind: str = "QUEUE_REVIEW") -> dict[str, object]:
    decision_id = _decision_id(index)
    source_event_id = f"evt_case_trigger_{index:06d}"
    return {
        "decision_id": decision_id,
        "decision_kind": "txn_disposition",
        "bundle_ref": {"bundle_id": "b" * 64, "bundle_version": "2026.02.09", "registry_ref": "registry://active"},
        "snapshot_hash": "c" * 64,
        "graph_version": {"version_id": "d" * 32, "watermark_ts_utc": "2026-02-09T18:00:00.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": str(100 + index)}],
            "basis_digest": "e" * 64,
        },
        "degrade_posture": {
            "mode": "NORMAL",
            "capabilities_mask": {
                "allow_ieg": True,
                "allowed_feature_groups": ["core_features"],
                "allow_model_primary": True,
                "allow_model_stage2": True,
                "allow_fallback_heuristics": True,
                "action_posture": "NORMAL",
            },
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1", "content_digest": "f" * 64},
            "posture_seq": 1,
            "decided_at_utc": "2026-02-09T18:00:00.000000Z",
        },
        "pins": dict(PINS),
        "decided_at_utc": f"2026-02-09T18:{index % 60:02d}:00.000000Z",
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8", "content_digest": "9" * 64},
        "run_config_digest": "4" * 64,
        "source_event": {
            "event_id": source_event_id,
            "event_type": "transaction_authorization",
            "ts_utc": f"2026-02-09T18:{index % 60:02d}:00.000000Z",
            "origin_offset": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": str(100 + index),
                "offset_kind": "kinesis_sequence",
            },
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": str(100 + index),
                "offset_kind": "kinesis_sequence",
            },
        },
        "decision": {"action_kind": action_kind},
    }


def _checkpoint_ref(index: int) -> dict[str, object]:
    return {
        "stream": "fp.bus.case.v1",
        "partition": 0,
        "offset": str(10_000 + index),
        "offset_kind": "kinesis_sequence",
    }


def _process_decision(
    *,
    index: int,
    replay: CaseTriggerReplayLedger,
    publisher: CaseTriggerIgPublisher,
    checkpoints: CaseTriggerCheckpointGate,
    metrics: CaseTriggerRunMetrics,
    reconciliation: CaseTriggerReconciliationBuilder,
) -> _Processed:
    decision_payload = _decision_payload(index=index)
    trigger = adapt_from_df_decision(
        decision_payload=decision_payload,
        audit_record_id=f"audit_{_decision_id(index)}",
        policy=_policy(),
    )
    trigger_payload = trigger.as_dict()
    metrics.record_trigger_seen(trigger_payload=trigger_payload)

    replay_result = replay.register_case_trigger(
        payload=trigger_payload,
        source_class="DF_DECISION",
        observed_at_utc=f"2026-02-09T18:{index % 60:02d}:01.000000Z",
        policy=_policy(),
    )

    publish_record = publisher.publish_case_trigger(trigger)
    metrics.record_publish(decision=publish_record.decision, reason_code=publish_record.reason_code)

    token = checkpoints.issue_token(
        source_ref_id=trigger.source_ref_id,
        case_trigger_id=trigger.case_trigger_id,
        issued_at_utc=f"2026-02-09T18:{index % 60:02d}:02.000000Z",
    )
    checkpoints.mark_ledger_committed(token_id=token.token_id)
    checkpoints.mark_publish_result(
        token_id=token.token_id,
        publish_decision=publish_record.decision,
        halted=False,
        halt_reason=None,
    )
    checkpoint = checkpoints.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=_checkpoint_ref(index),
        committed_at_utc=f"2026-02-09T18:{index % 60:02d}:03.000000Z",
    )

    reconciliation.add_record(
        trigger_payload=trigger_payload,
        publish_record={
            "decision": publish_record.decision,
            "reason_code": publish_record.reason_code,
            "receipt_ref": publish_record.receipt_ref,
        },
        replay_outcome=replay_result.outcome,
    )
    return _Processed(
        replay_outcome=replay_result.outcome,
        publish_decision=publish_record.decision,
        checkpoint_status=checkpoint.status,
    )


def test_phase8_df_to_case_trigger_continuity(tmp_path: Path) -> None:
    session = _Session()
    publisher = CaseTriggerIgPublisher(
        ig_ingest_url="http://example.invalid",
        api_key="SYSTEM::case_trigger_writer",
        timeout_seconds=0.1,
        max_attempts=1,
        session=session,
    )
    replay = CaseTriggerReplayLedger(tmp_path / "phase8_replay.sqlite")
    checkpoints = CaseTriggerCheckpointGate(tmp_path / "phase8_checkpoints.sqlite")
    metrics = CaseTriggerRunMetrics(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    reconciliation = CaseTriggerReconciliationBuilder(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )

    result = _process_decision(
        index=0,
        replay=replay,
        publisher=publisher,
        checkpoints=checkpoints,
        metrics=metrics,
        reconciliation=reconciliation,
    )
    assert result.replay_outcome == REPLAY_NEW
    assert result.publish_decision == PUBLISH_ADMIT
    assert result.checkpoint_status == CHECKPOINT_COMMITTED
    assert len(session.requests) == 1


@pytest.mark.parametrize("event_count", [20, 200])
def test_phase8_component_local_parity_proof(event_count: int, tmp_path: Path) -> None:
    session = _Session()
    publisher = CaseTriggerIgPublisher(
        ig_ingest_url="http://example.invalid",
        api_key="SYSTEM::case_trigger_writer",
        timeout_seconds=0.1,
        max_attempts=1,
        session=session,
    )
    replay = CaseTriggerReplayLedger(tmp_path / "phase8_replay.sqlite")
    checkpoints = CaseTriggerCheckpointGate(tmp_path / "phase8_checkpoints.sqlite")
    metrics = CaseTriggerRunMetrics(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    reconciliation = CaseTriggerReconciliationBuilder(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )

    committed_total = 0
    for index in range(event_count):
        result = _process_decision(
            index=index,
            replay=replay,
            publisher=publisher,
            checkpoints=checkpoints,
            metrics=metrics,
            reconciliation=reconciliation,
        )
        assert result.replay_outcome == REPLAY_NEW
        assert result.publish_decision == PUBLISH_ADMIT
        assert result.checkpoint_status == CHECKPOINT_COMMITTED
        committed_total += 1

    for index in range(event_count):
        result = _process_decision(
            index=index,
            replay=replay,
            publisher=publisher,
            checkpoints=checkpoints,
            metrics=metrics,
            reconciliation=reconciliation,
        )
        assert result.replay_outcome == REPLAY_MATCH
        assert result.publish_decision == PUBLISH_DUPLICATE
        assert result.checkpoint_status == CHECKPOINT_COMMITTED
        committed_total += 1

    metrics_payload = metrics.export(generated_at_utc="2026-02-09T18:59:00.000000Z")
    reconciliation_payload = reconciliation.export(generated_at_utc="2026-02-09T18:59:01.000000Z")

    reasons: list[str] = []
    counters = metrics_payload["metrics"]
    expected_seen = event_count * 2

    if int(counters.get("triggers_seen", 0)) != expected_seen:
        reasons.append(f"TRIGGERS_SEEN_MISMATCH:{counters.get('triggers_seen', 0)}:{expected_seen}")
    if int(counters.get("published", 0)) != event_count:
        reasons.append(f"PUBLISHED_MISMATCH:{counters.get('published', 0)}:{event_count}")
    if int(counters.get("duplicates", 0)) != event_count:
        reasons.append(f"DUPLICATES_MISMATCH:{counters.get('duplicates', 0)}:{event_count}")
    if int(counters.get("quarantine", 0)) != 0:
        reasons.append(f"QUARANTINE_NONZERO:{counters.get('quarantine', 0)}")
    if int(counters.get("publish_ambiguous", 0)) != 0:
        reasons.append(f"AMBIGUOUS_NONZERO:{counters.get('publish_ambiguous', 0)}")
    if int(reconciliation_payload["totals"].get("payload_mismatch", 0)) != 0:
        reasons.append(f"PAYLOAD_MISMATCH_NONZERO:{reconciliation_payload['totals'].get('payload_mismatch', 0)}")
    if committed_total != expected_seen:
        reasons.append(f"CHECKPOINT_COMMIT_MISMATCH:{committed_total}:{expected_seen}")

    artifact_dir = Path("runs/fraud-platform") / PINS["platform_run_id"] / "case_trigger" / "reconciliation"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"phase8_parity_proof_{event_count}.json"

    proof = _ParityProof(
        expected_events=event_count,
        triggers_seen_total=int(counters.get("triggers_seen", 0)),
        published_total=int(counters.get("published", 0)),
        duplicate_total=int(counters.get("duplicates", 0)),
        quarantine_total=int(counters.get("quarantine", 0)),
        publish_ambiguous_total=int(counters.get("publish_ambiguous", 0)),
        replay_payload_mismatch_total=int(reconciliation_payload["totals"].get("payload_mismatch", 0)),
        checkpoint_committed_total=committed_total,
        status="PASS" if not reasons else "FAIL",
        reasons=tuple(reasons),
        artifact_path=str(artifact_path),
    )

    artifact_path.write_text(
        json.dumps(
            {
                "expected_events": proof.expected_events,
                "triggers_seen_total": proof.triggers_seen_total,
                "published_total": proof.published_total,
                "duplicate_total": proof.duplicate_total,
                "quarantine_total": proof.quarantine_total,
                "publish_ambiguous_total": proof.publish_ambiguous_total,
                "replay_payload_mismatch_total": proof.replay_payload_mismatch_total,
                "checkpoint_committed_total": proof.checkpoint_committed_total,
                "status": proof.status,
                "reasons": list(proof.reasons),
                "artifact_path": proof.artifact_path,
            },
            sort_keys=True,
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    assert proof.status == "PASS"


def test_phase8_negative_path_injections_fail_closed_and_emit_proof(tmp_path: Path) -> None:
    unsupported_closed = False
    try:
        adapt_case_trigger_from_source(
            source_class="UNSUPPORTED_SOURCE",
            source_payload=_decision_payload(index=999),
            policy=_policy(),
        )
    except CaseTriggerAdapterError:
        unsupported_closed = True

    replay = CaseTriggerReplayLedger(tmp_path / "phase8_negative_replay.sqlite")
    baseline = adapt_from_df_decision(
        decision_payload=_decision_payload(index=77, action_kind="QUEUE_REVIEW"),
        audit_record_id="audit_neg_77",
        policy=_policy(),
    )
    baseline_outcome = replay.register_case_trigger(
        payload=baseline.as_dict(),
        source_class="DF_DECISION",
        observed_at_utc="2026-02-09T18:45:00.000000Z",
        policy=_policy(),
    )
    assert baseline_outcome.outcome == REPLAY_NEW

    mutated = adapt_from_df_decision(
        decision_payload=_decision_payload(index=77, action_kind="ALLOW"),
        audit_record_id="audit_neg_77",
        policy=_policy(),
    )
    assert mutated.case_trigger_id == baseline.case_trigger_id
    assert mutated.payload_hash != baseline.payload_hash

    mismatch_outcome = replay.register_case_trigger(
        payload=mutated.as_dict(),
        source_class="DF_DECISION",
        observed_at_utc="2026-02-09T18:45:01.000000Z",
        policy=_policy(),
    )

    governance_store = LocalObjectStore(tmp_path / "fraud-platform")
    governance = CaseTriggerGovernanceEmitter(
        store=governance_store,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
        run_config_digest="a" * 64,
        environment="test",
        config_revision="phase8-v0",
    )
    first_emit = governance.emit_collision_anomaly(case_trigger_id=mutated.case_trigger_id)
    second_emit = governance.emit_collision_anomaly(case_trigger_id=mutated.case_trigger_id)

    events_path = (
        tmp_path
        / "fraud-platform"
        / PINS["platform_run_id"]
        / "obs"
        / "governance"
        / "events.jsonl"
    )
    event_lines = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    reasons: list[str] = []
    if not unsupported_closed:
        reasons.append("UNSUPPORTED_SOURCE_NOT_FAIL_CLOSED")
    if mismatch_outcome.outcome != REPLAY_PAYLOAD_MISMATCH:
        reasons.append(f"MISMATCH_NOT_FAIL_CLOSED:{mismatch_outcome.outcome}")
    if first_emit is None:
        reasons.append("GOVERNANCE_EMIT_MISSING")
    if second_emit is not None:
        reasons.append("GOVERNANCE_DEDUPE_FAILED")
    if len(event_lines) != 1:
        reasons.append(f"GOVERNANCE_EVENT_COUNT:{len(event_lines)}:1")

    artifact_dir = Path("runs/fraud-platform") / PINS["platform_run_id"] / "case_trigger" / "reconciliation"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "phase8_negative_path_proof.json"
    artifact_path.write_text(
        json.dumps(
            {
                "unsupported_source_fail_closed": unsupported_closed,
                "collision_mismatch_outcome": mismatch_outcome.outcome,
                "governance_collision_emitted": first_emit is not None,
                "governance_dedupe_working": second_emit is None,
                "governance_event_count": len(event_lines),
                "status": "PASS" if not reasons else "FAIL",
                "reasons": reasons,
            },
            sort_keys=True,
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    assert not reasons
