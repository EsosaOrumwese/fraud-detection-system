from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.offline_feature_plane import (
    OfsBuildIntent,
    OfsDatasetDraftBuilder,
    OfsDatasetDraftBuilderConfig,
    OfsPhase6FeatureError,
    ResolvedFeatureProfile,
)


def _intent_payload(
    *,
    request_id: str,
    intent_kind: str = "dataset_build",
) -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": request_id,
        "intent_kind": intent_kind,
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
        "non_training_allowed": False,
    }


def _profile(*, feature_set_id: str = "core_features", feature_set_version: str = "v1") -> ResolvedFeatureProfile:
    return ResolvedFeatureProfile(
        profile_ref="config/platform/ofp/features_v0.yaml",
        feature_set_id=feature_set_id,
        feature_set_version=feature_set_version,
        policy_id="ofp.features.v0",
        revision="r1",
        profile_digest="a" * 64,
        matched_group_digest="b" * 64,
    )


def _builder(tmp_path: Path) -> OfsDatasetDraftBuilder:
    return OfsDatasetDraftBuilder(config=OfsDatasetDraftBuilderConfig(object_store_root=str(tmp_path / "store")))


def _event(
    *,
    topic: str = "fp.bus.traffic.fraud.v1",
    partition: int = 0,
    offset_kind: str = "kinesis_sequence",
    offset: str,
    event_id: str,
    ts_utc: str,
    payload_hash: str,
    amount: float,
) -> dict[str, object]:
    return {
        "topic": topic,
        "partition": partition,
        "offset_kind": offset_kind,
        "offset": offset,
        "event_id": event_id,
        "ts_utc": ts_utc,
        "payload_hash": payload_hash,
        "payload": {"amount": amount, "risk_flag": amount > 75},
    }


def test_phase6_draft_is_deterministic_under_out_of_order_and_duplicates(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase6.req.001"))
    replay_events = [
        _event(offset="102", event_id="evt_001", ts_utc="2026-02-10T10:00:00Z", payload_hash="a" * 64, amount=100.0),
        _event(offset="101", event_id="evt_002", ts_utc="2026-02-10T10:01:00Z", payload_hash="b" * 64, amount=50.0),
        _event(offset="100", event_id="evt_001", ts_utc="2026-02-10T10:00:00Z", payload_hash="a" * 64, amount=100.0),
        _event(offset="101", event_id="evt_002", ts_utc="2026-02-10T10:01:00Z", payload_hash="b" * 64, amount=50.0),
    ]
    draft_a = builder.build(
        intent=intent,
        resolved_feature_profile=_profile(),
        replay_events=replay_events,
        replay_receipt={"status": "COMPLETE"},
        label_receipt={"status": "READY_FOR_TRAINING"},
    )
    draft_b = builder.build(
        intent=intent,
        resolved_feature_profile=_profile(),
        replay_events=list(reversed(replay_events)),
        replay_receipt={"status": "COMPLETE"},
        label_receipt={"status": "READY_FOR_TRAINING"},
    )
    assert draft_a.rows_digest == draft_b.rows_digest
    assert [row.event_id for row in draft_a.rows] == ["evt_001", "evt_002"]
    assert [row.offset for row in draft_a.rows] == ["100", "101"]
    assert draft_a.dedupe_stats["input_events_total"] == 4
    assert draft_a.dedupe_stats["offset_tuple_unique_total"] == 3
    assert draft_a.dedupe_stats["event_unique_total"] == 2
    assert draft_a.dedupe_stats["duplicate_offsets_dropped"] == 1
    assert draft_a.dedupe_stats["event_replays_dropped"] == 1
    assert draft_a.parity_hash is None


def test_phase6_conflicting_event_id_payload_hash_fails_closed(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase6.req.002"))
    replay_events = [
        _event(offset="100", event_id="evt_001", ts_utc="2026-02-10T10:00:00Z", payload_hash="a" * 64, amount=100.0),
        _event(offset="101", event_id="evt_001", ts_utc="2026-02-10T10:00:01Z", payload_hash="c" * 64, amount=101.0),
    ]
    with pytest.raises(OfsPhase6FeatureError) as exc:
        builder.build(intent=intent, resolved_feature_profile=_profile(), replay_events=replay_events)
    assert exc.value.code == "REPLAY_EVENT_ID_CONFLICT"


def test_phase6_feature_profile_alignment_is_enforced(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase6.req.003"))
    replay_events = [
        _event(offset="100", event_id="evt_001", ts_utc="2026-02-10T10:00:00Z", payload_hash="a" * 64, amount=42.0),
    ]
    with pytest.raises(OfsPhase6FeatureError) as exc:
        builder.build(
            intent=intent,
            resolved_feature_profile=_profile(feature_set_version="v2"),
            replay_events=replay_events,
        )
    assert exc.value.code == "FEATURE_PROFILE_MISMATCH"


def test_phase6_parity_intent_emits_parity_hash(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    intent = OfsBuildIntent.from_payload(
        _intent_payload(request_id="ofs.phase6.req.004", intent_kind="parity_rebuild")
    )
    replay_events = [
        _event(offset="100", event_id="evt_010", ts_utc="2026-02-10T10:10:00Z", payload_hash="d" * 64, amount=12.0),
    ]
    draft = builder.build(intent=intent, resolved_feature_profile=_profile(), replay_events=replay_events)
    assert draft.parity_hash is not None
    assert len(str(draft.parity_hash)) == 64


def test_phase6_draft_immutability_violation_is_fail_closed(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase6.req.005"))
    replay_events = [
        _event(offset="100", event_id="evt_001", ts_utc="2026-02-10T10:00:00Z", payload_hash="a" * 64, amount=88.0),
    ]
    draft = builder.build(intent=intent, resolved_feature_profile=_profile(), replay_events=replay_events)
    ref = Path(builder.emit_immutable(draft=draft))
    payload = json.loads(ref.read_text(encoding="utf-8"))
    payload["rows_digest"] = "0" * 64
    ref.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    with pytest.raises(OfsPhase6FeatureError) as exc:
        builder.emit_immutable(draft=draft)
    assert exc.value.code == "DATASET_DRAFT_IMMUTABILITY_VIOLATION"
