from __future__ import annotations

import pytest

from fraud_detection.offline_feature_plane import (
    OFS_RUN_DONE,
    OFS_RUN_PUBLISH_PENDING,
    OFS_RUN_QUEUED,
    OFS_RUN_RUNNING,
    OfsBuildIntent,
    OfsRunControl,
    OfsRunControlPolicy,
    OfsRunLedger,
    OfsRunLedgerError,
    deterministic_run_key,
)


def _payload(request_id: str) -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": request_id,
        "intent_kind": "dataset_build",
        "platform_run_id": "platform_20260210T091951Z",
        "scenario_run_ids": ["74bd83db1ad3d1fa136e579115d55429"],
        "replay_basis": [
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset_kind": "kinesis_sequence",
                "start_offset": "100",
                "end_offset": "200",
            }
        ],
        "label_basis": {
            "label_asof_utc": "2026-02-10T10:00:00Z",
            "resolution_rule": "observed_time<=label_asof_utc",
            "maturity_days": 30,
        },
        "feature_definition_set": {
            "feature_set_id": "core",
            "feature_set_version": "v1",
        },
        "join_scope": {"subject_key": "platform_run_id,event_id"},
        "filters": {"country": ["US"]},
        "run_facts_ref": "s3://fraud-platform/platform_20260210T091951Z/sr/run_facts_view.json",
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
        "non_training_allowed": False,
    }


def _intent(request_id: str) -> OfsBuildIntent:
    return OfsBuildIntent.from_payload(_payload(request_id))


def test_phase2_submit_duplicate_request_converges_to_same_run_identity(tmp_path) -> None:
    ledger = OfsRunLedger(locator=str(tmp_path / "ofs_phase2.sqlite"))
    intent = _intent("ofs.phase2.req.001")
    first = ledger.submit_intent(intent=intent, queued_at_utc="2026-02-10T11:30:00Z")
    second = ledger.submit_intent(intent=intent, queued_at_utc="2026-02-10T11:30:01Z")

    assert first.outcome == "NEW"
    assert second.outcome == "DUPLICATE"
    assert first.run_key == second.run_key == deterministic_run_key(intent.request_id)
    assert second.receipt.status == OFS_RUN_QUEUED


def test_phase2_request_id_payload_mismatch_fails_closed(tmp_path) -> None:
    ledger = OfsRunLedger(locator=str(tmp_path / "ofs_phase2.sqlite"))
    first = _payload("ofs.phase2.req.002")
    second = _payload("ofs.phase2.req.002")
    second["filters"] = {"country": ["US"], "merchant_segment": ["enterprise"]}

    ledger.submit_intent(intent=OfsBuildIntent.from_payload(first), queued_at_utc="2026-02-10T11:31:00Z")
    with pytest.raises(OfsRunLedgerError) as exc:
        ledger.submit_intent(intent=OfsBuildIntent.from_payload(second), queued_at_utc="2026-02-10T11:31:01Z")
    assert exc.value.code == "REQUEST_ID_PAYLOAD_MISMATCH"


def test_phase2_state_machine_supports_publish_only_retry_without_full_rerun(tmp_path) -> None:
    ledger = OfsRunLedger(locator=str(tmp_path / "ofs_phase2.sqlite"))
    control = OfsRunControl(ledger=ledger, policy=OfsRunControlPolicy(max_publish_retry_attempts=2))
    intent = _intent("ofs.phase2.req.003")
    submission = control.enqueue(intent=intent, queued_at_utc="2026-02-10T11:32:00Z")

    control.start_full_run(run_key=submission.run_key, started_at_utc="2026-02-10T11:32:10Z")
    pending = control.mark_publish_pending(
        run_key=submission.run_key,
        pending_at_utc="2026-02-10T11:32:20Z",
        reason_code="REGISTRY_TIMEOUT",
    )
    assert pending.status == OFS_RUN_PUBLISH_PENDING

    retry_receipt, decision = control.start_publish_retry(
        run_key=submission.run_key,
        requested_at_utc="2026-02-10T11:32:30Z",
        started_at_utc="2026-02-10T11:32:31Z",
    )
    assert decision.decision == "ALLOWED"
    assert retry_receipt.status == OFS_RUN_RUNNING

    done = control.mark_done(
        run_key=submission.run_key,
        completed_at_utc="2026-02-10T11:32:40Z",
        result_ref="s3://fraud-platform/ofs/manifests/dm_001.json",
    )
    assert done.status == OFS_RUN_DONE
    assert done.full_run_attempts == 1
    assert done.publish_retry_attempts == 1


def test_phase2_publish_retry_budget_is_bounded(tmp_path) -> None:
    ledger = OfsRunLedger(locator=str(tmp_path / "ofs_phase2.sqlite"))
    control = OfsRunControl(ledger=ledger, policy=OfsRunControlPolicy(max_publish_retry_attempts=1))
    intent = _intent("ofs.phase2.req.004")
    submission = control.enqueue(intent=intent, queued_at_utc="2026-02-10T11:33:00Z")

    control.start_full_run(run_key=submission.run_key, started_at_utc="2026-02-10T11:33:10Z")
    control.mark_publish_pending(
        run_key=submission.run_key,
        pending_at_utc="2026-02-10T11:33:20Z",
        reason_code="REGISTRY_TIMEOUT",
    )
    control.start_publish_retry(
        run_key=submission.run_key,
        requested_at_utc="2026-02-10T11:33:30Z",
        started_at_utc="2026-02-10T11:33:31Z",
    )
    control.mark_publish_pending(
        run_key=submission.run_key,
        pending_at_utc="2026-02-10T11:33:40Z",
        reason_code="REGISTRY_TIMEOUT",
    )
    with pytest.raises(OfsRunLedgerError) as exc:
        control.start_publish_retry(
            run_key=submission.run_key,
            requested_at_utc="2026-02-10T11:33:50Z",
            started_at_utc="2026-02-10T11:33:51Z",
        )
    assert exc.value.code == "PUBLISH_RETRY_EXHAUSTED"


def test_phase2_invalid_transition_publish_only_from_queued_rejected(tmp_path) -> None:
    ledger = OfsRunLedger(locator=str(tmp_path / "ofs_phase2.sqlite"))
    intent = _intent("ofs.phase2.req.005")
    submission = ledger.submit_intent(intent=intent, queued_at_utc="2026-02-10T11:34:00Z")

    with pytest.raises(OfsRunLedgerError) as exc:
        ledger.start_run(
            run_key=submission.run_key,
            started_at_utc="2026-02-10T11:34:05Z",
            mode="PUBLISH_ONLY",
        )
    assert exc.value.code == "INVALID_TRANSITION"


def test_phase2_receipt_includes_pinned_input_summary_and_provenance(tmp_path) -> None:
    ledger = OfsRunLedger(locator=str(tmp_path / "ofs_phase2.sqlite"))
    intent = _intent("ofs.phase2.req.006")
    submission = ledger.submit_intent(intent=intent, queued_at_utc="2026-02-10T11:35:00Z")
    receipt = ledger.receipt(run_key=submission.run_key)

    assert receipt.input_summary["request_id"] == intent.request_id
    assert receipt.input_summary["replay_slice_count"] == 1
    assert receipt.provenance["ofs_code_release_id"] == "git:abc123"
    assert receipt.provenance["run_facts_ref"].startswith("s3://fraud-platform/")
    events = ledger.list_events(run_key=submission.run_key)
    assert len(events) == 1
    assert events[0].event_type == "INTENT_QUEUED"
