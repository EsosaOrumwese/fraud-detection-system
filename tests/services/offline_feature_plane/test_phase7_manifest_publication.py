from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.offline_feature_plane import (
    OfsBuildIntent,
    OfsDatasetDraftBuilder,
    OfsDatasetDraftBuilderConfig,
    OfsManifestPublisher,
    OfsManifestPublisherConfig,
    OfsPhase7PublishError,
    ResolvedFeatureProfile,
)


def _intent_payload(*, request_id: str, non_training_allowed: bool = False) -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": request_id,
        "intent_kind": "dataset_build",
        "platform_run_id": "platform_20260210T120000Z",
        "scenario_run_ids": ["74bd83db1ad3d1fa136e579115d55429"],
        "replay_basis": [
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset_kind": "kinesis_sequence",
                "start_offset": "100",
                "end_offset": "110",
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
        "join_scope": {"subject_key": "platform_run_id,event_id"},
        "filters": {"country": ["US"]},
        "run_facts_ref": "s3://fraud-platform/platform_20260210T120000Z/sr/run_facts_view/run.json",
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
        "non_training_allowed": non_training_allowed,
    }


def _profile() -> ResolvedFeatureProfile:
    return ResolvedFeatureProfile(
        profile_ref="config/platform/ofp/features_v0.yaml",
        feature_set_id="core_features",
        feature_set_version="v1",
        policy_id="ofp.features.v0",
        revision="r1",
        profile_digest="a" * 64,
        matched_group_digest="b" * 64,
    )


def _draft_builder(store_root: Path) -> OfsDatasetDraftBuilder:
    return OfsDatasetDraftBuilder(config=OfsDatasetDraftBuilderConfig(object_store_root=str(store_root)))


def _publisher(store_root: Path) -> OfsManifestPublisher:
    return OfsManifestPublisher(config=OfsManifestPublisherConfig(object_store_root=str(store_root)))


def _event(*, offset: str, event_id: str, payload_hash: str) -> dict[str, object]:
    return {
        "topic": "fp.bus.traffic.fraud.v1",
        "partition": 0,
        "offset_kind": "kinesis_sequence",
        "offset": offset,
        "event_id": event_id,
        "ts_utc": "2026-02-10T10:00:00Z",
        "payload_hash": payload_hash,
        "payload": {"amount": 42.0},
    }


def _build_draft(*, intent: OfsBuildIntent, store_root: Path):
    draft_builder = _draft_builder(store_root)
    return draft_builder.build(
        intent=intent,
        resolved_feature_profile=_profile(),
        replay_events=[_event(offset="100", event_id="evt_001", payload_hash="a" * 64)],
        replay_receipt={"status": "COMPLETE"},
        label_receipt={"status": "READY_FOR_TRAINING"},
    )


def test_phase7_publish_commits_manifest_and_is_idempotent(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase7.req.001"))
    draft = _build_draft(intent=intent, store_root=store_root)
    publisher = _publisher(store_root)
    receipt_a = publisher.publish(
        intent=intent,
        draft=draft,
        replay_receipt={"status": "COMPLETE"},
        label_receipt={"status": "READY_FOR_TRAINING", "gate": {"ready_for_training": True}},
        draft_ref="s3://fraud-platform/path/to/draft.json",
    )
    assert receipt_a.publication_mode == "NEW"
    assert Path(receipt_a.manifest_ref).exists()
    assert Path(receipt_a.dataset_materialization_ref).exists()
    manifest_payload = json.loads(Path(receipt_a.manifest_ref).read_text(encoding="utf-8"))
    assert manifest_payload["schema_version"] == "learning.dataset_manifest.v0"
    receipt_b = publisher.publish(
        intent=intent,
        draft=draft,
        replay_receipt={"status": "COMPLETE"},
        label_receipt={"status": "READY_FOR_TRAINING", "gate": {"ready_for_training": True}},
    )
    assert receipt_b.publication_mode == "ALREADY_PUBLISHED"
    assert receipt_b.manifest_ref == receipt_a.manifest_ref


def test_phase7_replay_incomplete_fails_closed(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase7.req.002"))
    draft = _build_draft(intent=intent, store_root=store_root)
    publisher = _publisher(store_root)
    with pytest.raises(OfsPhase7PublishError) as exc:
        publisher.publish(
            intent=intent,
            draft=draft,
            replay_receipt={"status": "INCOMPLETE"},
            label_receipt={"status": "READY_FOR_TRAINING", "gate": {"ready_for_training": True}},
        )
    assert exc.value.code == "REPLAY_INCOMPLETE"


def test_phase7_training_label_gate_violation_fails_closed(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase7.req.003"))
    draft = _build_draft(intent=intent, store_root=store_root)
    publisher = _publisher(store_root)
    with pytest.raises(OfsPhase7PublishError) as exc:
        publisher.publish(
            intent=intent,
            draft=draft,
            replay_receipt={"status": "COMPLETE"},
            label_receipt={"status": "NOT_READY_FOR_TRAINING", "gate": {"ready_for_training": False}},
        )
    assert exc.value.code == "LABEL_GATE_UNSATISFIED"


def test_phase7_manifest_immutability_violation_is_fail_closed(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase7.req.004"))
    draft = _build_draft(intent=intent, store_root=store_root)
    publisher = _publisher(store_root)
    manifest_payload = intent.to_dataset_manifest().payload
    manifest_id = str(manifest_payload["dataset_manifest_id"])
    manifest_path = (
        store_root / intent.platform_run_id / "ofs" / "manifests" / f"{manifest_id}.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    drifted = dict(manifest_payload)
    drifted["dataset_fingerprint"] = "0" * 64
    manifest_path.write_text(json.dumps(drifted, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    with pytest.raises(OfsPhase7PublishError) as exc:
        publisher.publish(
            intent=intent,
            draft=draft,
            replay_receipt={"status": "COMPLETE"},
            label_receipt={"status": "READY_FOR_TRAINING", "gate": {"ready_for_training": True}},
        )
    assert exc.value.code == "MANIFEST_IMMUTABILITY_VIOLATION"


def test_phase7_supersession_link_is_emitted_explicitly(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase7.req.005"))
    draft = _build_draft(intent=intent, store_root=store_root)
    publisher = _publisher(store_root)
    receipt = publisher.publish(
        intent=intent,
        draft=draft,
        replay_receipt={"status": "COMPLETE"},
        label_receipt={"status": "READY_FOR_TRAINING", "gate": {"ready_for_training": True}},
        supersedes_manifest_refs=("s3://fraud-platform/old/manifest-A.json", "s3://fraud-platform/old/manifest-B.json"),
        backfill_reason="LATE_LABEL_BACKFILL",
    )
    assert receipt.supersession_ref is not None
    assert Path(str(receipt.supersession_ref)).exists()
    payload = json.loads(Path(str(receipt.supersession_ref)).read_text(encoding="utf-8"))
    assert payload["supersedes_manifest_refs"] == [
        "s3://fraud-platform/old/manifest-A.json",
        "s3://fraud-platform/old/manifest-B.json",
    ]
    assert payload["backfill_reason"] == "LATE_LABEL_BACKFILL"
