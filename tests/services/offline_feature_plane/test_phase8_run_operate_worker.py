from __future__ import annotations

import json
from pathlib import Path

import yaml

from fraud_detection.offline_feature_plane.contracts import OfsBuildIntent
from fraud_detection.offline_feature_plane.run_control import OfsRunControl, OfsRunControlPolicy
from fraud_detection.offline_feature_plane.run_ledger import OfsRunLedger
from fraud_detection.offline_feature_plane.worker import (
    OfsJobWorker,
    enqueue_build_request,
    enqueue_publish_retry_request,
    load_worker_config,
)


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


def _run_facts_payload(platform_run_id: str) -> dict[str, object]:
    return {
        "run_id": "74bd83db1ad3d1fa136e579115d55429",
        "platform_run_id": platform_run_id,
        "scenario_run_id": "74bd83db1ad3d1fa136e579115d55429",
        "pins": {
            "manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8",
            "parameter_hash": "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7",
            "seed": 42,
            "scenario_id": "baseline_v1",
            "run_id": "74bd83db1ad3d1fa136e579115d55429",
            "platform_run_id": platform_run_id,
            "scenario_run_id": "74bd83db1ad3d1fa136e579115d55429",
        },
        "locators": [
            {
                "output_id": "s2_event_stream_baseline_6B",
                "path": "s3://oracle-store/local_full_run-5/data/s2_event_stream_baseline_6B/part-*.parquet",
                "manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8",
                "parameter_hash": "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7",
                "scenario_id": "baseline_v1",
                "seed": 42,
                "content_digest": {"algo": "sha256", "hex": "a" * 64},
            }
        ],
        "gate_receipts": [
            {
                "gate_id": "gate.layer3.6B.validation",
                "status": "PASS",
                "scope": {"manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"},
            }
        ],
        "instance_receipts": [
            {
                "output_id": "s2_event_stream_baseline_6B",
                "status": "PASS",
                "scope": {"manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"},
                "target_ref": {
                    "output_id": "s2_event_stream_baseline_6B",
                    "path": "s3://oracle-store/local_full_run-5/data/s2_event_stream_baseline_6B/part-*.parquet",
                },
                "target_digest": {"algo": "sha256", "hex": "a" * 64},
            }
        ],
    }


def _intent_payload(platform_run_id: str) -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": "ofs.phase8.req.001",
        "intent_kind": "dataset_build",
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
        "non_training_allowed": True,
    }


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
            },
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_phase8_worker_processes_dataset_build_request(tmp_path: Path) -> None:
    run_id = "platform_20260210T122800Z"
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

    run_facts_path = store_root / run_id / "sr" / "run_facts_view" / "74bd83db1ad3d1fa136e579115d55429.json"
    run_facts_path.parent.mkdir(parents=True, exist_ok=True)
    run_facts_path.write_text(json.dumps(_run_facts_payload(run_id), sort_keys=True, ensure_ascii=True), encoding="utf-8")

    intent_path = tmp_path / "intent.json"
    intent_path.write_text(json.dumps(_intent_payload(run_id), sort_keys=True, ensure_ascii=True), encoding="utf-8")
    replay_events_path = tmp_path / "replay_events.json"
    replay_events_path.write_text(
        json.dumps(
            [
                {
                    "topic": "fp.bus.traffic.fraud.v1",
                    "partition": 0,
                    "offset_kind": "kinesis_sequence",
                    "offset": "100",
                    "event_id": "evt_001",
                    "ts_utc": "2026-02-10T10:00:00Z",
                    "payload_hash": "a" * 64,
                    "payload": {"amount": 10.0},
                }
            ],
            sort_keys=True,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    replay_evidence_path = tmp_path / "replay_evidence.json"
    replay_evidence_path.write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "topic": "fp.bus.traffic.fraud.v1",
                        "partition": 0,
                        "offset_kind": "kinesis_sequence",
                        "offset": "100",
                        "payload_hash": "a" * 64,
                        "source": "EB",
                    }
                ]
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    config = load_worker_config(profile_path)
    request_ref = enqueue_build_request(
        config=config,
        intent_path=intent_path,
        replay_events_path=replay_events_path,
        target_subjects_path=None,
        replay_evidence_path=replay_evidence_path,
        supersedes_manifest_refs=(),
        backfill_reason=None,
        request_id_override=None,
    )
    assert request_ref

    worker = OfsJobWorker(config)
    assert worker.run_once() == 1

    receipt_path = store_root / run_id / "ofs" / "job_invocations" / "ofs.phase8.req.001.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "DONE"
    assert receipt["run_config_digest"] == config.run_config_digest
    assert Path(receipt["refs"]["manifest_ref"]).exists()


def test_phase8_worker_fails_closed_on_digest_mismatch(tmp_path: Path) -> None:
    run_id = "platform_20260210T122900Z"
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

    request_path = store_root / run_id / "ofs" / "job_requests" / "ofs.bad.digest.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        json.dumps(
            {
                "schema_version": "learning.ofs_job_request.v0",
                "request_id": "ofs.bad.digest",
                "command": "dataset_build",
                "platform_run_id": run_id,
                "run_config_digest": "0" * 64,
                "intent": _intent_payload(run_id),
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    config = load_worker_config(profile_path)
    worker = OfsJobWorker(config)
    assert worker.run_once() == 1

    receipt = json.loads((store_root / run_id / "ofs" / "job_invocations" / "ofs.bad.digest.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "FAILED"
    assert receipt["error"]["code"] == "RUN_CONFIG_DIGEST_MISMATCH"


def test_phase8_publish_retry_requires_pending_run_state(tmp_path: Path) -> None:
    run_id = "platform_20260210T123000Z"
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

    intent_payload = _intent_payload(run_id)
    intent_path = tmp_path / "intent.json"
    intent_path.write_text(json.dumps(intent_payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    config = load_worker_config(profile_path)
    control = OfsRunControl(
        ledger=OfsRunLedger(locator=str(run_ledger)),
        policy=OfsRunControlPolicy(max_publish_retry_attempts=2),
    )
    intent = OfsBuildIntent.from_payload(intent_payload)
    submitted = control.enqueue(intent=intent, queued_at_utc="2026-02-10T10:00:00Z")
    run_key = submitted.run_key
    control.start_full_run(run_key=run_key, started_at_utc="2026-02-10T10:00:01Z")
    control.mark_done(run_key=run_key, completed_at_utc="2026-02-10T10:00:02Z", result_ref="s3://fraud-platform/ofs/manifests/test.json")

    draft_path = tmp_path / "draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "schema_version": "learning.ofs_dataset_draft.v0",
                "run_key": run_key,
                "request_id": intent_payload["request_id"],
                "intent_kind": "dataset_build",
                "platform_run_id": run_id,
                "generated_at_utc": "2026-02-10T10:00:00Z",
                "feature_profile": {"policy_id": "ofp.features.v0", "revision": "r1"},
                "row_order_rules": ["final_sort=ts_utc,event_id"],
                "dedupe_stats": {},
                "rows_digest": "f" * 64,
                "rows": [],
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    replay_receipt_path = tmp_path / "replay_receipt.json"
    replay_receipt_path.write_text(json.dumps({"status": "COMPLETE"}, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    request_ref = enqueue_publish_retry_request(
        config=config,
        run_key=run_key,
        platform_run_id=run_id,
        intent_path=intent_path,
        draft_path=draft_path,
        replay_receipt_path=replay_receipt_path,
        label_receipt_path=None,
        supersedes_manifest_refs=(),
        backfill_reason=None,
        request_id_override="ofs.publish.retry.fail",
    )
    assert request_ref

    worker = OfsJobWorker(config)
    assert worker.run_once() == 1

    receipt = json.loads((store_root / run_id / "ofs" / "job_invocations" / "ofs.publish.retry.fail.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "FAILED"
    assert receipt["error"]["code"] == "RETRY_NOT_PENDING"
