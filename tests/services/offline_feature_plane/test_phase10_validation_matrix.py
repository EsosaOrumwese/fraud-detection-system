from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from fraud_detection.label_store import LabelStoreWriterBoundary
from fraud_detection.learning_registry.contracts import DatasetManifestContract
from fraud_detection.offline_feature_plane import (
    OfsBuildIntent,
    OfsBuildPlanResolver,
    OfsBuildPlanResolverConfig,
    OfsPhase1ContractError,
    OfsPhase3ResolverError,
    OfsPhase4ReplayError,
    OfsReplayBasisResolver,
    OfsReplayBasisResolverConfig,
    ReplayBasisEvidence,
)
from fraud_detection.offline_feature_plane.worker import (
    OfsJobWorker,
    enqueue_build_request,
    load_worker_config,
)
from fraud_detection.platform_reporter import run_reporter as run_reporter_module
from fraud_detection.offline_feature_plane import observability as ofs_observability_module


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


def _write_profile(
    path: Path,
    *,
    store_root: Path,
    policy_path: Path,
    feature_profile: Path,
    run_id: str,
    run_ledger: Path,
    label_store: Path,
) -> None:
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


def _run_facts_payload(platform_run_id: str, *, pass_ready: bool) -> dict[str, object]:
    gate_receipts = []
    instance_receipts = []
    if pass_ready:
        gate_receipts = [
            {
                "gate_id": "gate.layer3.6B.validation",
                "status": "PASS",
                "scope": {"manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"},
            }
        ]
        instance_receipts = [
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
        ]
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
        "gate_receipts": gate_receipts,
        "instance_receipts": instance_receipts,
    }


def _intent_payload(platform_run_id: str, *, request_id: str) -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": request_id,
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
        "join_scope": {
            "subject_key": "platform_run_id,event_id",
            "required_output_ids": ["s2_event_stream_baseline_6B"],
        },
        "filters": {
            "country": ["US"],
            "label_types": ["fraud_disposition"],
            "label_coverage_policy": {
                "min_coverage_by_label_type": {"fraud_disposition": 1.0},
                "max_conflict_ratio": 0.0,
            },
        },
        "run_facts_ref": f"{platform_run_id}/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json",
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
        "non_training_allowed": False,
    }


def _seed_label_store(label_store: Path, *, platform_run_id: str, event_id: str, observed_time: str) -> None:
    writer = LabelStoreWriterBoundary(label_store)
    payload = {
        "case_timeline_event_id": "a" * 32,
        "label_subject_key": {"platform_run_id": platform_run_id, "event_id": event_id},
        "pins": {
            "platform_run_id": platform_run_id,
            "scenario_run_id": "74bd83db1ad3d1fa136e579115d55429",
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "baseline.v0",
            "seed": 42,
        },
        "label_type": "fraud_disposition",
        "label_value": "FRAUD_CONFIRMED",
        "effective_time": observed_time,
        "observed_time": observed_time,
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_001",
        "evidence_refs": [{"ref_type": "CASE_EVENT", "ref_id": "case_evt_000001"}],
    }
    result = writer.write_label_assertion(payload)
    assert result.status == "ACCEPTED"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def test_phase10_integration_closure_positive_path_and_handoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "platform_20260210T130700Z"
    runs_root = tmp_path / "runs"
    monkeypatch.setattr(ofs_observability_module, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(run_reporter_module, "RUNS_ROOT", runs_root)

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
    _write_json(run_facts_path, _run_facts_payload(run_id, pass_ready=True))
    _seed_label_store(
        label_store,
        platform_run_id=run_id,
        event_id="evt_001",
        observed_time="2026-02-10T09:00:00Z",
    )

    intent_path = tmp_path / "intent.json"
    _write_json(intent_path, _intent_payload(run_id, request_id="ofs.phase10.req.positive.001"))

    replay_events_path = tmp_path / "replay_events.json"
    _write_json(
        replay_events_path,
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
    )
    replay_evidence_path = tmp_path / "replay_evidence.json"
    _write_json(
        replay_evidence_path,
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

    receipt_path = store_root / run_id / "ofs" / "job_invocations" / "ofs.phase10.req.positive.001.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "DONE"

    refs = receipt["refs"]
    required_refs = (
        "resolved_build_plan_ref",
        "replay_receipt_ref",
        "label_receipt_ref",
        "dataset_draft_ref",
        "manifest_ref",
        "publication_receipt_ref",
    )
    reasons: list[str] = []
    for ref_name in required_refs:
        ref_path = Path(str(refs.get(ref_name) or ""))
        if not ref_path.exists():
            reasons.append(f"MISSING_REF:{ref_name}")

    manifest_payload = json.loads(Path(refs["manifest_ref"]).read_text(encoding="utf-8"))
    DatasetManifestContract.from_payload(manifest_payload)

    ofs_reconciliation = runs_root / run_id / "ofs" / "reconciliation" / "last_reconciliation.json"
    learning_reconciliation = runs_root / run_id / "learning" / "reconciliation" / "ofs_reconciliation.json"
    if not ofs_reconciliation.exists():
        reasons.append("MISSING_OFS_RECONCILIATION")
    if not learning_reconciliation.exists():
        reasons.append("MISSING_LEARNING_RECONCILIATION")

    component_refs = run_reporter_module._component_reconciliation_refs(run_id)
    if str(ofs_reconciliation) not in component_refs:
        reasons.append("REPORTER_MISSING_OFS_RECONCILIATION_REF")
    if str(learning_reconciliation) not in component_refs:
        reasons.append("REPORTER_MISSING_LEARNING_RECONCILIATION_REF")

    proof_path = runs_root / run_id / "ofs" / "reconciliation" / "phase10_integration_proof.json"
    proof_payload = {
        "platform_run_id": run_id,
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "continuity": {
            "request_ref": request_ref,
            "receipt_ref": str(receipt_path),
            "refs": {key: str(refs.get(key) or "") for key in required_refs},
        },
        "mf_handoff": {
            "dataset_manifest_validated": True,
            "manifest_ref": str(refs["manifest_ref"]),
            "dataset_manifest_id": str(manifest_payload.get("dataset_manifest_id") or ""),
            "dataset_fingerprint": str(manifest_payload.get("dataset_fingerprint") or ""),
        },
        "reconciliation_refs": {
            "ofs": str(ofs_reconciliation),
            "learning": str(learning_reconciliation),
            "component_refs_sample": component_refs[:10],
        },
    }
    _write_json(proof_path, proof_payload)
    assert proof_payload["status"] == "PASS"


def test_phase10_negative_path_fail_closed_matrix(tmp_path: Path) -> None:
    run_id = "platform_20260210T130800Z"
    store_root = tmp_path / "store"
    policy_path = tmp_path / "ofs_policy.yaml"
    feature_profile = tmp_path / "features_v0.yaml"
    run_facts_dir = store_root / run_id / "sr" / "run_facts_view"
    run_facts_dir.mkdir(parents=True, exist_ok=True)

    _write_policy(policy_path)
    _write_feature_profile(feature_profile)

    pass_run_facts_ref = f"{run_id}/sr/run_facts_view/pass.json"
    _write_json(run_facts_dir / "pass.json", _run_facts_payload(run_id, pass_ready=True))
    no_pass_run_facts_ref = f"{run_id}/sr/run_facts_view/no_pass.json"
    _write_json(run_facts_dir / "no_pass.json", _run_facts_payload(run_id, pass_ready=False))

    results: dict[str, dict[str, str]] = {}
    reasons: list[str] = []

    missing_label_payload = _intent_payload(run_id, request_id="ofs.phase10.req.neg.001")
    del missing_label_payload["label_basis"]["label_asof_utc"]
    try:
        OfsBuildIntent.from_payload(missing_label_payload)
        reasons.append("MISSING_LABEL_BASIS_NOT_BLOCKED")
    except OfsPhase1ContractError as exc:
        results["missing_label_basis"] = {"status": "PASS", "code": exc.code}
        if exc.code not in {"LABEL_ASOF_MISSING", "SCHEMA_INVALID"}:
            reasons.append(f"MISSING_LABEL_BASIS_CODE_DRIFT:{exc.code}")

    unresolved_profile_intent_payload = _intent_payload(run_id, request_id="ofs.phase10.req.neg.002")
    unresolved_profile_intent_payload["run_facts_ref"] = pass_run_facts_ref
    unresolved_profile_intent = OfsBuildIntent.from_payload(unresolved_profile_intent_payload)
    try:
        OfsBuildPlanResolver(
            config=OfsBuildPlanResolverConfig(
                object_store_root=str(store_root),
                feature_profile_ref=str(tmp_path / "missing_features.yaml"),
            )
        ).resolve(intent=unresolved_profile_intent)
        reasons.append("FEATURE_PROFILE_UNRESOLVED_NOT_BLOCKED")
    except OfsPhase3ResolverError as exc:
        results["unresolved_feature_profile"] = {"status": "PASS", "code": exc.code}
        if exc.code != "FEATURE_PROFILE_UNRESOLVED":
            reasons.append(f"UNRESOLVED_FEATURE_PROFILE_CODE_DRIFT:{exc.code}")

    no_pass_intent_payload = _intent_payload(run_id, request_id="ofs.phase10.req.neg.003")
    no_pass_intent_payload["run_facts_ref"] = no_pass_run_facts_ref
    no_pass_intent = OfsBuildIntent.from_payload(no_pass_intent_payload)
    try:
        OfsBuildPlanResolver(
            config=OfsBuildPlanResolverConfig(
                object_store_root=str(store_root),
                feature_profile_ref=str(feature_profile),
            )
        ).resolve(intent=no_pass_intent)
        reasons.append("NO_PASS_NO_READ_NOT_BLOCKED")
    except OfsPhase3ResolverError as exc:
        results["no_pass_no_read"] = {"status": "PASS", "code": exc.code}
        if exc.code != "NO_PASS_NO_READ":
            reasons.append(f"NO_PASS_NO_READ_CODE_DRIFT:{exc.code}")

    mismatch_intent = OfsBuildIntent.from_payload(_intent_payload(run_id, request_id="ofs.phase10.req.neg.004"))
    mismatch_evidence = ReplayBasisEvidence.from_payload(
        {
            "observations": [
                {
                    "topic": "fp.bus.traffic.fraud.v1",
                    "partition": 0,
                    "offset_kind": "kinesis_sequence",
                    "offset": "100",
                    "payload_hash": "a" * 64,
                    "source": "EB",
                },
                {
                    "topic": "fp.bus.traffic.fraud.v1",
                    "partition": 0,
                    "offset_kind": "kinesis_sequence",
                    "offset": "100",
                    "payload_hash": "b" * 64,
                    "source": "ARCHIVE",
                },
            ]
        }
    )
    try:
        OfsReplayBasisResolver(
            config=OfsReplayBasisResolverConfig(
                object_store_root=str(store_root),
                discover_archive_events=False,
                require_complete_for_dataset_build=True,
            )
        ).resolve(intent=mismatch_intent, evidence=mismatch_evidence)
        reasons.append("REPLAY_MISMATCH_NOT_BLOCKED")
    except OfsPhase4ReplayError as exc:
        results["replay_mismatch"] = {"status": "PASS", "code": exc.code}
        if exc.code != "REPLAY_BASIS_MISMATCH":
            reasons.append(f"REPLAY_MISMATCH_CODE_DRIFT:{exc.code}")

    proof_path = tmp_path / "runs" / run_id / "ofs" / "reconciliation" / "phase10_negative_path_proof.json"
    proof_payload = {
        "platform_run_id": run_id,
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "results": results,
    }
    _write_json(proof_path, proof_payload)
    assert proof_payload["status"] == "PASS"
