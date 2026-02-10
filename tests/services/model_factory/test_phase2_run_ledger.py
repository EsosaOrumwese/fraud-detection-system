from __future__ import annotations

import pytest

from fraud_detection.model_factory import (
    MF_RUN_PUBLISHED,
    MF_RUN_PUBLISH_PENDING,
    MF_RUN_QUEUED,
    MF_RUN_RUNNING,
    MfRunControl,
    MfRunControlPolicy,
    MfRunLedger,
    MfRunLedgerError,
    MfTrainBuildRequest,
)


def _payload(request_id: str) -> dict[str, object]:
    return {
        "schema_version": "learning.mf_train_build_request.v0",
        "request_id": request_id,
        "intent_kind": "baseline_train",
        "platform_run_id": "platform_20260210T091951Z",
        "dataset_manifest_refs": [
            "s3://fraud-platform/platform_20260210T091951Z/ofs/manifests/dm_a.json",
            "s3://fraud-platform/platform_20260210T091951Z/ofs/manifests/dm_b.json",
        ],
        "training_config_ref": "s3://fraud-platform/config/mf/train_config_v0.yaml",
        "governance_profile_ref": "s3://fraud-platform/config/mf/governance_profile_v0.yaml",
        "requester_principal": "SYSTEM::run_operate",
        "target_scope": {
            "environment": "local_parity",
            "mode": "fraud",
            "bundle_slot": "primary",
        },
        "policy_revision": "mf-policy-v0",
        "config_revision": "local-parity-v0",
        "mf_code_release_id": "git:def456",
        "publish_allowed": True,
    }


def _request(request_id: str) -> MfTrainBuildRequest:
    return MfTrainBuildRequest.from_payload(_payload(request_id))


def test_phase2_submit_duplicate_request_converges_to_same_run_identity(tmp_path) -> None:
    ledger = MfRunLedger(locator=str(tmp_path / "mf_phase2.sqlite"))
    request = _request("mf.phase2.req.001")
    first = ledger.submit_request(request=request, queued_at_utc="2026-02-10T13:45:00Z")
    second = ledger.submit_request(request=request, queued_at_utc="2026-02-10T13:45:01Z")

    assert first.outcome == "NEW"
    assert second.outcome == "DUPLICATE"
    assert first.run_key == second.run_key == request.deterministic_train_run_id()
    assert second.receipt.status == MF_RUN_QUEUED


def test_phase2_request_id_payload_mismatch_fails_closed(tmp_path) -> None:
    ledger = MfRunLedger(locator=str(tmp_path / "mf_phase2.sqlite"))
    first = _payload("mf.phase2.req.002")
    second = _payload("mf.phase2.req.002")
    second["training_config_ref"] = "s3://fraud-platform/config/mf/train_config_v1.yaml"

    ledger.submit_request(request=MfTrainBuildRequest.from_payload(first), queued_at_utc="2026-02-10T13:46:00Z")
    with pytest.raises(MfRunLedgerError) as exc:
        ledger.submit_request(request=MfTrainBuildRequest.from_payload(second), queued_at_utc="2026-02-10T13:46:01Z")
    assert exc.value.code == "REQUEST_ID_PAYLOAD_MISMATCH"


def test_phase2_semantic_duplicate_request_with_new_request_id_converges_by_run_key(tmp_path) -> None:
    ledger = MfRunLedger(locator=str(tmp_path / "mf_phase2.sqlite"))
    first = _payload("mf.phase2.req.003a")
    second = _payload("mf.phase2.req.003b")
    first_req = MfTrainBuildRequest.from_payload(first)
    second_req = MfTrainBuildRequest.from_payload(second)

    first_submission = ledger.submit_request(request=first_req, queued_at_utc="2026-02-10T13:47:00Z")
    second_submission = ledger.submit_request(request=second_req, queued_at_utc="2026-02-10T13:47:01Z")
    assert first_submission.run_key == second_submission.run_key
    assert second_submission.outcome == "DUPLICATE"


def test_phase2_state_machine_supports_publish_only_retry_without_full_rerun(tmp_path) -> None:
    ledger = MfRunLedger(locator=str(tmp_path / "mf_phase2.sqlite"))
    control = MfRunControl(ledger=ledger, policy=MfRunControlPolicy(max_publish_retry_attempts=2))
    request = _request("mf.phase2.req.004")
    submission = control.enqueue(request=request, queued_at_utc="2026-02-10T13:48:00Z")

    control.start_full_run(run_key=submission.run_key, started_at_utc="2026-02-10T13:48:10Z")
    control.mark_eval_ready(
        run_key=submission.run_key,
        eval_ready_at_utc="2026-02-10T13:48:20Z",
        eval_report_ref="s3://fraud-platform/mf/eval/er_001.json",
    )
    control.mark_pass(
        run_key=submission.run_key,
        passed_at_utc="2026-02-10T13:48:30Z",
        gate_receipt_ref="s3://fraud-platform/mf/gates/gr_001.json",
    )
    pending = control.mark_publish_pending(
        run_key=submission.run_key,
        pending_at_utc="2026-02-10T13:48:40Z",
        reason_code="REGISTRY_TIMEOUT",
    )
    assert pending.status == MF_RUN_PUBLISH_PENDING

    retry_receipt, decision = control.start_publish_retry(
        run_key=submission.run_key,
        requested_at_utc="2026-02-10T13:48:50Z",
        started_at_utc="2026-02-10T13:48:51Z",
    )
    assert decision.decision == "ALLOWED"
    assert retry_receipt.status == MF_RUN_RUNNING

    published = control.mark_published(
        run_key=submission.run_key,
        published_at_utc="2026-02-10T13:49:00Z",
        bundle_publication_ref="s3://fraud-platform/mf/publish/bp_001.json",
    )
    assert published.status == MF_RUN_PUBLISHED
    assert published.full_run_attempts == 1
    assert published.publish_retry_attempts == 1


def test_phase2_publish_retry_budget_is_bounded(tmp_path) -> None:
    ledger = MfRunLedger(locator=str(tmp_path / "mf_phase2.sqlite"))
    control = MfRunControl(ledger=ledger, policy=MfRunControlPolicy(max_publish_retry_attempts=1))
    request = _request("mf.phase2.req.005")
    submission = control.enqueue(request=request, queued_at_utc="2026-02-10T13:50:00Z")

    control.start_full_run(run_key=submission.run_key, started_at_utc="2026-02-10T13:50:10Z")
    control.mark_eval_ready(
        run_key=submission.run_key,
        eval_ready_at_utc="2026-02-10T13:50:20Z",
        eval_report_ref="s3://fraud-platform/mf/eval/er_002.json",
    )
    control.mark_pass(
        run_key=submission.run_key,
        passed_at_utc="2026-02-10T13:50:30Z",
        gate_receipt_ref="s3://fraud-platform/mf/gates/gr_002.json",
    )
    control.mark_publish_pending(
        run_key=submission.run_key,
        pending_at_utc="2026-02-10T13:50:40Z",
        reason_code="REGISTRY_TIMEOUT",
    )
    control.start_publish_retry(
        run_key=submission.run_key,
        requested_at_utc="2026-02-10T13:50:50Z",
        started_at_utc="2026-02-10T13:50:51Z",
    )
    control.mark_publish_pending(
        run_key=submission.run_key,
        pending_at_utc="2026-02-10T13:51:00Z",
        reason_code="REGISTRY_TIMEOUT",
    )
    with pytest.raises(MfRunLedgerError) as exc:
        control.start_publish_retry(
            run_key=submission.run_key,
            requested_at_utc="2026-02-10T13:51:10Z",
            started_at_utc="2026-02-10T13:51:11Z",
        )
    assert exc.value.code == "PUBLISH_RETRY_EXHAUSTED"


def test_phase2_invalid_transition_publish_only_from_queued_rejected(tmp_path) -> None:
    ledger = MfRunLedger(locator=str(tmp_path / "mf_phase2.sqlite"))
    request = _request("mf.phase2.req.006")
    submission = ledger.submit_request(request=request, queued_at_utc="2026-02-10T13:52:00Z")

    with pytest.raises(MfRunLedgerError) as exc:
        ledger.start_run(
            run_key=submission.run_key,
            started_at_utc="2026-02-10T13:52:05Z",
            mode="PUBLISH_ONLY",
        )
    assert exc.value.code == "INVALID_TRANSITION"


def test_phase2_receipt_includes_pinned_input_summary_and_provenance(tmp_path) -> None:
    ledger = MfRunLedger(locator=str(tmp_path / "mf_phase2.sqlite"))
    request = _request("mf.phase2.req.007")
    submission = ledger.submit_request(request=request, queued_at_utc="2026-02-10T13:53:00Z")
    receipt = ledger.receipt(run_key=submission.run_key)

    assert receipt.input_summary["request_id"] == request.request_id
    assert receipt.input_summary["dataset_manifest_count"] == 2
    assert receipt.provenance["mf_code_release_id"] == "git:def456"
    assert receipt.provenance["training_config_ref"].startswith("s3://fraud-platform/")
    events = ledger.list_events(run_key=submission.run_key)
    assert len(events) == 1
    assert events[0].event_type == "REQUEST_QUEUED"

