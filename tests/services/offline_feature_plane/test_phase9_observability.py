from __future__ import annotations

import json
from pathlib import Path

import yaml

from fraud_detection.offline_feature_plane.contracts import OfsBuildIntent
from fraud_detection.offline_feature_plane.observability import OfsRunReporter
from fraud_detection.offline_feature_plane.run_control import OfsRunControl, OfsRunControlPolicy
from fraud_detection.offline_feature_plane.run_ledger import OfsRunLedger
from fraud_detection.offline_feature_plane.worker import (
    OfsJobWorker,
    enqueue_build_request,
    load_worker_config,
)
from fraud_detection.platform_governance import EvidenceRefResolutionCorridor, EvidenceRefResolutionRequest
from fraud_detection.scenario_runner.storage import LocalObjectStore


def _write_policy(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "policy_id": "ofs.launcher.v0",
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


def _write_feature_profile(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "policy_id": "ofp.features.v0",
                "revision": "r1",
                "feature_groups": [
                    {
                        "name": "core_features",
                        "version": "v1",
                        "windows": [{"window": "1h", "duration": "1h", "ttl": "1h"}],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_profile(path: Path, *, store_root: Path, policy_path: Path, feature_profile: Path, run_id: str, run_ledger: Path, label_store: Path) -> None:
    payload = {
        "profile_id": "test_local",
        "wiring": {
            "object_store": {
                "root": str(store_root),
            }
        },
        "ofp": {
            "policy": {
                "features_ref": str(feature_profile),
            }
        },
        "ofs": {
            "policy": {
                "launcher_policy_ref": str(policy_path),
            },
            "wiring": {
                "stream_id": "ofs.v0",
                "required_platform_run_id": run_id,
                "run_ledger_locator": str(run_ledger),
                "label_store_locator": str(label_store),
                "object_store_root": str(store_root),
                "feature_profile_ref": str(feature_profile),
                "request_prefix": f"{run_id}/ofs/job_requests",
                "request_poll_seconds": 0.01,
                "request_batch_limit": 10,
                "max_publish_retry_attempts": 2,
                "replay_discover_archive_events": False,
                "require_complete_for_dataset_build": True,
                "evidence_ref_actor_id": "SYSTEM::ofs_worker",
                "evidence_ref_source_type": "SYSTEM",
                "evidence_ref_purpose": "ofs_dataset_build",
                "evidence_ref_strict": True,
            },
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _intent_payload(platform_run_id: str, *, request_id: str, intent_kind: str = "dataset_build") -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": request_id,
        "intent_kind": intent_kind,
        "platform_run_id": platform_run_id,
        "scenario_run_ids": ["74bd83db1ad3d1fa136e579115d55429"],
        "replay_basis": [
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset_kind": "kinesis_sequence",
                "start_offset": "100",
                "end_offset": "100",
            }
        ],
        "label_basis": {
            "label_asof_utc": "2026-02-10T10:00:00Z",
            "resolution_rule": "observed_time<=label_asof_utc",
            "maturity_days": 30,
        },
        "feature_definition_set": {
            "feature_set_id": "core_features",
            "feature_set_version": "v1",
        },
        "join_scope": {"subject_key": "platform_run_id,event_id", "required_output_ids": ["s2_event_stream_baseline_6B"]},
        "filters": {"country": ["US"], "label_types": ["fraud_disposition"]},
        "run_facts_ref": f"{platform_run_id}/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json",
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
        "non_training_allowed": intent_kind != "dataset_build",
    }


def test_phase9_ofs_run_reporter_exports_metrics_governance_and_reconciliation(tmp_path: Path) -> None:
    run_id = "platform_20260210T124800Z"
    locator = tmp_path / "ofs_run_ledger.sqlite"
    store_root = tmp_path / "store"

    control = OfsRunControl(
        ledger=OfsRunLedger(locator=str(locator)),
        policy=OfsRunControlPolicy(max_publish_retry_attempts=2),
    )

    done_intent = OfsBuildIntent.from_payload(_intent_payload(run_id, request_id="ofs.phase9.done.001", intent_kind="dataset_build"))
    done_run = control.enqueue(intent=done_intent, queued_at_utc="2026-02-10T12:48:00Z")
    control.start_full_run(run_key=done_run.run_key, started_at_utc="2026-02-10T12:48:01Z")
    control.mark_done(
        run_key=done_run.run_key,
        completed_at_utc="2026-02-10T12:48:02Z",
        result_ref=f"s3://fraud-platform/{run_id}/ofs/manifests/dataset_done.json",
    )

    failed_intent = OfsBuildIntent.from_payload(_intent_payload(run_id, request_id="ofs.phase9.fail.001", intent_kind="dataset_build"))
    failed_run = control.enqueue(intent=failed_intent, queued_at_utc="2026-02-10T12:49:00Z")
    control.start_full_run(run_key=failed_run.run_key, started_at_utc="2026-02-10T12:49:01Z")
    control.mark_failed(
        run_key=failed_run.run_key,
        failed_at_utc="2026-02-10T12:49:02Z",
        reason_code="REPLAY_BASIS_MISMATCH",
    )

    parity_intent = OfsBuildIntent.from_payload(_intent_payload(run_id, request_id="ofs.phase9.parity.001", intent_kind="parity_rebuild"))
    parity_run = control.enqueue(intent=parity_intent, queued_at_utc="2026-02-10T12:50:00Z")
    control.start_full_run(run_key=parity_run.run_key, started_at_utc="2026-02-10T12:50:01Z")
    control.mark_done(
        run_key=parity_run.run_key,
        completed_at_utc="2026-02-10T12:50:02Z",
        result_ref=f"s3://fraud-platform/{run_id}/ofs/parity/parity_001.json",
    )

    store = LocalObjectStore(store_root)
    protected_ref = f"fraud-platform/{run_id}/ofs/publication_receipts/test.json"
    store.write_json(protected_ref, {"ok": True})
    corridor = EvidenceRefResolutionCorridor(store=store, actor_allowlist={"SYSTEM::ofs_worker"})
    corridor.resolve(
        EvidenceRefResolutionRequest(
            actor_id="SYSTEM::ofs_worker",
            source_type="SYSTEM",
            source_component="offline_feature_plane",
            purpose="ofs_dataset_build:run_facts_ref",
            ref_type="artifact_ref",
            ref_id=protected_ref,
            platform_run_id=run_id,
        )
    )
    corridor.resolve(
        EvidenceRefResolutionRequest(
            actor_id="SYSTEM::ofs_blocked",
            source_type="SYSTEM",
            source_component="offline_feature_plane",
            purpose="ofs_dataset_build:run_facts_ref",
            ref_type="artifact_ref",
            ref_id=protected_ref,
            platform_run_id=run_id,
        )
    )

    output_root = tmp_path / "runs" / run_id
    reporter = OfsRunReporter(
        locator=str(locator),
        platform_run_id=run_id,
        object_store_root=str(store_root),
    )
    payload = reporter.export(output_root=output_root)

    metrics = payload["metrics"]
    assert metrics["build_requested"] == 2
    assert metrics["build_completed"] == 1
    assert metrics["build_failed"] == 1
    assert metrics["datasets_built"] == 1
    assert metrics["parity_requested"] == 1
    assert metrics["parity_completed"] == 1
    assert metrics["parity_failed"] == 0

    evidence = payload["evidence_ref_resolution"]
    assert evidence["attempted"] >= 2
    assert evidence["resolved"] >= 1
    assert evidence["denied"] >= 1

    governance_path = output_root / "ofs" / "governance" / "events.jsonl"
    assert governance_path.exists()
    events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    lifecycle_types = {str(item.get("lifecycle_type") or "") for item in events}
    assert "DATASET_BUILD_COMPLETED" in lifecycle_types
    assert "DATASET_BUILD_FAILED" in lifecycle_types
    assert "PARITY_RESULT" in lifecycle_types

    learning_reconciliation = output_root / "learning" / "reconciliation" / "ofs_reconciliation.json"
    assert learning_reconciliation.exists()
    summary = json.loads(learning_reconciliation.read_text(encoding="utf-8"))["summary"]
    assert summary["datasets_built"] == 1


def test_phase9_ofs_governance_export_is_idempotent(tmp_path: Path) -> None:
    run_id = "platform_20260210T124900Z"
    locator = tmp_path / "ofs_run_ledger_idempotent.sqlite"

    control = OfsRunControl(
        ledger=OfsRunLedger(locator=str(locator)),
        policy=OfsRunControlPolicy(max_publish_retry_attempts=2),
    )
    intent = OfsBuildIntent.from_payload(_intent_payload(run_id, request_id="ofs.phase9.idempotent.001", intent_kind="dataset_build"))
    submitted = control.enqueue(intent=intent, queued_at_utc="2026-02-10T12:51:00Z")
    control.start_full_run(run_key=submitted.run_key, started_at_utc="2026-02-10T12:51:01Z")
    control.mark_done(run_key=submitted.run_key, completed_at_utc="2026-02-10T12:51:02Z", result_ref=f"{run_id}/ofs/manifests/idempotent.json")

    output_root = tmp_path / "runs" / run_id
    reporter = OfsRunReporter(
        locator=str(locator),
        platform_run_id=run_id,
        object_store_root=str(tmp_path / "store"),
    )
    first = reporter.export(output_root=output_root)
    second = reporter.export(output_root=output_root)

    assert first["governance"]["emitted_total"] > 0
    assert second["governance"]["emitted_total"] == 0
    assert second["governance"]["duplicate_skipped_total"] >= first["governance"]["emitted_total"]


def test_phase9_worker_fails_closed_when_protected_ref_scope_mismatches(tmp_path: Path) -> None:
    run_id = "platform_20260210T125000Z"
    other_run_id = "platform_20260210T125001Z"
    store_root = tmp_path / "store"
    policy_path = tmp_path / "ofs_policy.yaml"
    feature_profile = tmp_path / "features_v0.yaml"
    profile_path = tmp_path / "profile.yaml"
    run_ledger = tmp_path / "ofs_run_ledger.sqlite"
    label_store = tmp_path / "label_store.sqlite"

    _write_policy(policy_path)
    _write_feature_profile(feature_profile)
    _write_profile(
        profile_path,
        store_root=store_root,
        policy_path=policy_path,
        feature_profile=feature_profile,
        run_id=run_id,
        run_ledger=run_ledger,
        label_store=label_store,
    )

    run_facts_path = store_root / other_run_id / "sr" / "run_facts_view" / "74bd83db1ad3d1fa136e579115d55429.json"
    run_facts_path.parent.mkdir(parents=True, exist_ok=True)
    run_facts_path.write_text(json.dumps({"run_id": "74bd83db1ad3d1fa136e579115d55429"}, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    intent = _intent_payload(run_id, request_id="ofs.phase9.scope.fail.001", intent_kind="dataset_build")
    intent["run_facts_ref"] = f"{other_run_id}/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json"
    intent_path = tmp_path / "intent_scope_fail.json"
    intent_path.write_text(json.dumps(intent, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    config = load_worker_config(profile_path)
    request_ref = enqueue_build_request(
        config=config,
        intent_path=intent_path,
        replay_events_path=None,
        target_subjects_path=None,
        replay_evidence_path=None,
        supersedes_manifest_refs=(),
        backfill_reason=None,
        request_id_override=None,
    )
    assert request_ref

    worker = OfsJobWorker(config)
    assert worker.run_once() == 1

    receipt_path = store_root / run_id / "ofs" / "job_invocations" / "ofs.phase9.scope.fail.001.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "FAILED"
    assert receipt["error"]["code"] == "REF_ACCESS_DENIED"
    assert "REF_SCOPE_MISMATCH" in receipt["error"]["message"]

