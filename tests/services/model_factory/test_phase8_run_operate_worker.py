from __future__ import annotations

import json
from pathlib import Path

import yaml

from fraud_detection.model_factory.contracts import MfTrainBuildRequest
from fraud_detection.model_factory.run_control import MfRunControl, MfRunControlPolicy
from fraud_detection.model_factory.run_ledger import MfRunLedger
from fraud_detection.model_factory.worker import (
    MfJobWorker,
    enqueue_publish_retry_request,
    enqueue_train_build_request,
    load_worker_config,
)


def _write_policy(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "policy_id": "mf.launcher.v0",
                "revision": "r1",
                "launcher": {
                    "max_publish_retry_attempts": 2,
                    "request_poll_seconds": 0.01,
                    "request_batch_limit": 10,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_profile(path: Path, *, store_root: Path, policy_path: Path, run_id: str, run_ledger: Path) -> None:
    payload = {
        "profile_id": "test_local",
        "mf": {
            "policy": {
                "launcher_policy_ref": str(policy_path),
            },
            "wiring": {
                "stream_id": "mf.v0",
                "required_platform_run_id": run_id,
                "run_ledger_locator": str(run_ledger),
                "object_store_root": str(store_root),
                "request_prefix": f"{run_id}/mf/job_requests",
                "request_poll_seconds": 0.01,
                "request_batch_limit": 10,
                "max_publish_retry_attempts": 2,
                "service_release_id": "git:test",
            },
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _train_request_payload(platform_run_id: str, *, request_id: str) -> dict[str, object]:
    return {
        "schema_version": "learning.mf_train_build_request.v0",
        "request_id": request_id,
        "intent_kind": "baseline_train",
        "platform_run_id": platform_run_id,
        "dataset_manifest_refs": [f"{platform_run_id}/ofs/manifests/dm_001.json"],
        "training_config_ref": "config/platform/mf/training_profile_v0.yaml",
        "governance_profile_ref": "config/platform/mf/governance_profile_v0.yaml",
        "requester_principal": "SYSTEM::run_operate",
        "target_scope": {
            "environment": "local_parity",
            "mode": "fraud",
            "bundle_slot": "primary",
        },
        "policy_revision": "mf-policy-v0",
        "config_revision": "local-parity-v0",
        "mf_code_release_id": "git:phase8",
        "publish_allowed": True,
    }


def test_phase8_worker_processes_train_build_request(tmp_path: Path) -> None:
    run_id = "platform_20260210T145200Z"
    store_root = tmp_path / "store"
    policy_path = tmp_path / "mf_policy.yaml"
    profile_path = tmp_path / "profile.yaml"
    run_ledger = tmp_path / "mf_run_ledger.sqlite"

    _write_policy(policy_path)
    _write_profile(
        profile_path,
        store_root=store_root,
        policy_path=policy_path,
        run_id=run_id,
        run_ledger=run_ledger,
    )

    request_payload = _train_request_payload(run_id, request_id="mf.phase8.req.001")
    request_path = tmp_path / "train_request.json"
    request_path.write_text(json.dumps(request_payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    config = load_worker_config(profile_path)
    request_ref = enqueue_train_build_request(
        config=config,
        request_path=request_path,
        request_id_override=None,
    )
    assert request_ref

    worker = MfJobWorker(config)
    worker._execute_train_build = lambda request: {  # type: ignore[method-assign]
        "status": "DONE",
        "run_key": "mf_run_phase8_001",
        "refs": {"synthetic_ref": "s3://fraud-platform/test/ref.json"},
        "details": {"submission_outcome": "CREATED"},
    }
    assert worker.run_once() == 1

    receipt_path = store_root / run_id / "mf" / "job_invocations" / "mf.phase8.req.001.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "DONE"
    assert receipt["run_config_digest"] == config.run_config_digest
    assert receipt["run_key"] == "mf_run_phase8_001"


def test_phase8_worker_fails_closed_on_digest_mismatch(tmp_path: Path) -> None:
    run_id = "platform_20260210T145300Z"
    store_root = tmp_path / "store"
    policy_path = tmp_path / "mf_policy.yaml"
    profile_path = tmp_path / "profile.yaml"
    run_ledger = tmp_path / "mf_run_ledger.sqlite"

    _write_policy(policy_path)
    _write_profile(
        profile_path,
        store_root=store_root,
        policy_path=policy_path,
        run_id=run_id,
        run_ledger=run_ledger,
    )
    config = load_worker_config(profile_path)

    request_path = store_root / run_id / "mf" / "job_requests" / "mf.bad.digest.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        json.dumps(
            {
                "schema_version": "learning.mf_job_request.v0",
                "request_id": "mf.bad.digest",
                "command": "train_build",
                "platform_run_id": run_id,
                "run_config_digest": "0" * 64,
                "request": _train_request_payload(run_id, request_id="mf.bad.digest"),
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    worker = MfJobWorker(config)
    assert worker.run_once() == 1

    receipt = json.loads((store_root / run_id / "mf" / "job_invocations" / "mf.bad.digest.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "FAILED"
    assert receipt["error"]["code"] == "RUN_CONFIG_DIGEST_MISMATCH"


def test_phase8_publish_retry_requires_pending_run_state(tmp_path: Path) -> None:
    run_id = "platform_20260210T145400Z"
    store_root = tmp_path / "store"
    policy_path = tmp_path / "mf_policy.yaml"
    profile_path = tmp_path / "profile.yaml"
    run_ledger = tmp_path / "mf_run_ledger.sqlite"

    _write_policy(policy_path)
    _write_profile(
        profile_path,
        store_root=store_root,
        policy_path=policy_path,
        run_id=run_id,
        run_ledger=run_ledger,
    )
    config = load_worker_config(profile_path)

    control = MfRunControl(
        ledger=MfRunLedger(locator=str(run_ledger)),
        policy=MfRunControlPolicy(max_publish_retry_attempts=2),
    )
    request = MfTrainBuildRequest.from_payload(_train_request_payload(run_id, request_id="mf.phase8.req.retry"))
    submitted = control.enqueue(request=request, queued_at_utc="2026-02-10T14:54:00Z")
    run_key = submitted.run_key
    control.start_full_run(run_key=run_key, started_at_utc="2026-02-10T14:54:01Z")
    control.mark_eval_ready(
        run_key=run_key,
        eval_ready_at_utc="2026-02-10T14:54:02Z",
        eval_report_ref="s3://fraud-platform/test/eval_report.json",
    )
    control.mark_pass(
        run_key=run_key,
        passed_at_utc="2026-02-10T14:54:03Z",
        gate_receipt_ref="s3://fraud-platform/test/gate_receipt.json",
    )
    control.mark_published(
        run_key=run_key,
        published_at_utc="2026-02-10T14:54:04Z",
        bundle_publication_ref="s3://fraud-platform/test/bundle_publication.json",
    )

    request_ref = enqueue_publish_retry_request(
        config=config,
        run_key=run_key,
        platform_run_id=run_id,
        request_id_override="mf.publish.retry.fail",
        resolved_train_plan_ref=None,
        gate_receipt_ref=None,
        publish_eligibility_ref=None,
    )
    assert request_ref

    worker = MfJobWorker(config)
    assert worker.run_once() == 1

    receipt = json.loads((store_root / run_id / "mf" / "job_invocations" / "mf.publish.retry.fail.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "FAILED"
    assert receipt["error"]["code"] == "RETRY_NOT_PENDING"
