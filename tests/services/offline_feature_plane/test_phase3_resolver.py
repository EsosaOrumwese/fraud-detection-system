from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from fraud_detection.offline_feature_plane import (
    OfsBuildIntent,
    OfsBuildPlanResolver,
    OfsBuildPlanResolverConfig,
    OfsPhase3ResolverError,
)


def _intent_payload(*, run_facts_ref: str, parity_anchor_ref: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": "ofs.phase3.req.001",
        "intent_kind": "dataset_build",
        "platform_run_id": "platform_20260210T113700Z",
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
            "feature_set_id": "core_features",
            "feature_set_version": "v1",
        },
        "join_scope": {
            "subject_key": "platform_run_id,event_id",
            "required_output_ids": ["s2_event_stream_baseline_6B"],
        },
        "filters": {"country": ["US"]},
        "run_facts_ref": run_facts_ref,
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
        "non_training_allowed": False,
    }
    if parity_anchor_ref:
        payload["parity_anchor_ref"] = parity_anchor_ref
    return payload


def _intent(*, run_facts_ref: str, parity_anchor_ref: str | None = None) -> OfsBuildIntent:
    return OfsBuildIntent.from_payload(_intent_payload(run_facts_ref=run_facts_ref, parity_anchor_ref=parity_anchor_ref))


def _write_run_facts(path: Path, *, with_pass: bool = True, platform_run_id: str = "platform_20260210T113700Z") -> None:
    payload = {
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
                "status": "PASS" if with_pass else "FAIL",
                "scope": {"manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"},
            }
        ],
        "instance_receipts": [
            {
                "output_id": "s2_event_stream_baseline_6B",
                "status": "PASS" if with_pass else "FAIL",
                "scope": {"manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"},
                "target_ref": {
                    "output_id": "s2_event_stream_baseline_6B",
                    "path": "s3://oracle-store/local_full_run-5/data/s2_event_stream_baseline_6B/part-*.parquet",
                },
                "target_digest": {"algo": "sha256", "hex": "a" * 64},
            }
        ],
        "policy_rev": {"policy_id": "sr_policy", "revision": "v0-local", "content_digest": "b" * 64},
        "bundle_hash": "c" * 64,
        "plan_ref": "platform_20260210T113700Z/sr/run_plan/74bd83db1ad3d1fa136e579115d55429.json",
        "record_ref": "platform_20260210T113700Z/sr/run_record/74bd83db1ad3d1fa136e579115d55429.jsonl",
        "status_ref": "platform_20260210T113700Z/sr/run_status/74bd83db1ad3d1fa136e579115d55429.json",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")


def _write_feature_profile(path: Path, *, version: str = "v1") -> None:
    payload = {
        "policy_id": "ofp.features.v0",
        "revision": "r1",
        "feature_groups": [
            {
                "name": "core_features",
                "version": version,
                "key_type": "flow_id",
                "windows": [{"window": "1h", "duration": "1h", "ttl": "1h"}],
            }
        ],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_phase3_resolves_build_plan_and_emits_immutable_artifact(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    run_facts_rel = "platform_20260210T113700Z/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json"
    run_facts_path = store_root / run_facts_rel
    _write_run_facts(run_facts_path)
    feature_profile_path = tmp_path / "features_v0.yaml"
    _write_feature_profile(feature_profile_path)

    resolver = OfsBuildPlanResolver(
        config=OfsBuildPlanResolverConfig(
            object_store_root=str(store_root),
            feature_profile_ref=str(feature_profile_path),
        )
    )
    plan = resolver.resolve(intent=_intent(run_facts_ref=run_facts_rel))
    assert plan.platform_run_id == "platform_20260210T113700Z"
    assert plan.feature_profile.resolved_revision == "ofp.features.v0@r1"
    assert len(plan.world_locators) == 1
    first_ref = resolver.emit_immutable(plan=plan)
    second_ref = resolver.emit_immutable(plan=plan)
    assert first_ref == second_ref
    assert Path(first_ref).exists()


def test_phase3_fails_closed_on_run_scope_mismatch(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    run_facts_rel = "platform_20260210T113700Z/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json"
    run_facts_path = store_root / run_facts_rel
    _write_run_facts(run_facts_path, platform_run_id="platform_20990101T000000Z")
    feature_profile_path = tmp_path / "features_v0.yaml"
    _write_feature_profile(feature_profile_path)

    resolver = OfsBuildPlanResolver(
        config=OfsBuildPlanResolverConfig(
            object_store_root=str(store_root),
            feature_profile_ref=str(feature_profile_path),
        )
    )
    with pytest.raises(OfsPhase3ResolverError) as exc:
        resolver.resolve(intent=_intent(run_facts_ref=run_facts_rel))
    assert exc.value.code == "RUN_SCOPE_INVALID"


def test_phase3_enforces_no_pass_no_read(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    run_facts_rel = "platform_20260210T113700Z/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json"
    run_facts_path = store_root / run_facts_rel
    _write_run_facts(run_facts_path, with_pass=False)
    feature_profile_path = tmp_path / "features_v0.yaml"
    _write_feature_profile(feature_profile_path)

    resolver = OfsBuildPlanResolver(
        config=OfsBuildPlanResolverConfig(
            object_store_root=str(store_root),
            feature_profile_ref=str(feature_profile_path),
        )
    )
    with pytest.raises(OfsPhase3ResolverError) as exc:
        resolver.resolve(intent=_intent(run_facts_ref=run_facts_rel))
    assert exc.value.code == "NO_PASS_NO_READ"


def test_phase3_fails_when_feature_profile_is_unresolved(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    run_facts_rel = "platform_20260210T113700Z/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json"
    run_facts_path = store_root / run_facts_rel
    _write_run_facts(run_facts_path)
    feature_profile_path = tmp_path / "features_v0.yaml"
    _write_feature_profile(feature_profile_path, version="v2")

    resolver = OfsBuildPlanResolver(
        config=OfsBuildPlanResolverConfig(
            object_store_root=str(store_root),
            feature_profile_ref=str(feature_profile_path),
        )
    )
    with pytest.raises(OfsPhase3ResolverError) as exc:
        resolver.resolve(intent=_intent(run_facts_ref=run_facts_rel))
    assert exc.value.code == "FEATURE_PROFILE_UNRESOLVED"


def test_phase3_resolves_optional_parity_anchor_as_typed_payload(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    run_facts_rel = "platform_20260210T113700Z/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json"
    run_facts_path = store_root / run_facts_rel
    _write_run_facts(run_facts_path)
    feature_profile_path = tmp_path / "features_v0.yaml"
    _write_feature_profile(feature_profile_path)
    parity_anchor_path = tmp_path / "parity_anchor.json"
    parity_anchor_path.write_text(
        json.dumps(
            {
                "audit_id": "d" * 32,
                "snapshot_hash": "e" * 64,
                "pins": {
                    "platform_run_id": "platform_20260210T113700Z",
                    "scenario_run_id": "74bd83db1ad3d1fa136e579115d55429",
                    "manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8",
                    "parameter_hash": "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7",
                    "scenario_id": "baseline_v1",
                    "seed": 42,
                },
                "eb_offset_basis": {
                    "stream": "fp.bus.traffic.fraud.v1",
                    "offset_kind": "kinesis_sequence",
                    "offsets": [{"partition": 0, "offset": "200"}],
                },
                "feature_groups": [{"name": "core_features", "version": "v1"}],
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    resolver = OfsBuildPlanResolver(
        config=OfsBuildPlanResolverConfig(
            object_store_root=str(store_root),
            feature_profile_ref=str(feature_profile_path),
        )
    )
    plan = resolver.resolve(
        intent=_intent(run_facts_ref=run_facts_rel, parity_anchor_ref=str(parity_anchor_path.resolve()))
    )
    assert plan.parity_anchor is not None
    assert plan.parity_anchor.anchor_kind == "audit_record"
    assert plan.parity_anchor.snapshot_hash == "e" * 64
    assert plan.parity_anchor.feature_definition_set is not None
    assert plan.parity_anchor.feature_definition_set.feature_set_id == "core_features"


def test_phase3_build_plan_artifact_detects_immutability_drift(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    run_facts_rel = "platform_20260210T113700Z/sr/run_facts_view/74bd83db1ad3d1fa136e579115d55429.json"
    run_facts_path = store_root / run_facts_rel
    _write_run_facts(run_facts_path)
    feature_profile_path = tmp_path / "features_v0.yaml"
    _write_feature_profile(feature_profile_path)

    resolver = OfsBuildPlanResolver(
        config=OfsBuildPlanResolverConfig(
            object_store_root=str(store_root),
            feature_profile_ref=str(feature_profile_path),
        )
    )
    plan = resolver.resolve(intent=_intent(run_facts_ref=run_facts_rel))
    emitted_path = Path(resolver.emit_immutable(plan=plan))
    drifted = plan.as_dict()
    drifted["run_facts_digest"] = "f" * 64
    emitted_path.write_text(json.dumps(drifted, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    with pytest.raises(OfsPhase3ResolverError) as exc:
        resolver.emit_immutable(plan=plan)
    assert exc.value.code == "BUILD_PLAN_IMMUTABILITY_VIOLATION"
