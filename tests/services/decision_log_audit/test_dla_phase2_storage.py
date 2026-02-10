from __future__ import annotations

from pathlib import Path

from fraud_detection.decision_log_audit.contracts import AuditRecord
from fraud_detection.decision_log_audit.storage import (
    DecisionLogAuditIndexStore,
    DecisionLogAuditObjectStore,
    build_storage_layout,
    load_storage_policy,
)


def _audit_record(*, audit_id: str, recorded_at_utc: str) -> AuditRecord:
    payload: dict[str, object] = {
        "audit_id": audit_id,
        "decision_event": {
            "event_id": "b" * 32,
            "event_type": "decision_response",
            "ts_utc": "2026-02-07T18:20:00.000000Z",
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": "100",
                "offset_kind": "kinesis_sequence",
            },
        },
        "bundle_ref": {"bundle_id": "c" * 64},
        "snapshot_hash": "d" * 64,
        "graph_version": {"version_id": "e" * 32, "watermark_ts_utc": "2026-02-07T18:19:58.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "100"}],
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
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r2"},
            "posture_seq": 5,
            "decided_at_utc": "2026-02-07T18:20:00.000000Z",
        },
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r9"},
        "run_config_digest": "1" * 64,
        "pins": {
            "platform_run_id": "platform_20260207T182000Z",
            "scenario_run_id": "2" * 32,
            "manifest_fingerprint": "3" * 64,
            "parameter_hash": "4" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "recorded_at_utc": recorded_at_utc,
    }
    return AuditRecord.from_payload(payload)


def test_phase2_storage_policy_covers_env_ladder() -> None:
    policy = load_storage_policy("config/platform/dla/storage_policy_v0.yaml")
    assert set(policy.profiles) == {"local", "local_parity", "dev", "prod"}
    assert policy.profile("local_parity").object_store_prefix == "fraud-platform/local_parity"
    assert policy.profile("prod").retention.audit_record_ttl_days >= policy.profile("dev").retention.audit_record_ttl_days


def test_phase2_build_layout_resolves_prefix_and_retention_from_profile(tmp_path: Path) -> None:
    layout = build_storage_layout(
        {
            "profile_id": "local_parity",
            "storage_policy_path": "config/platform/dla/storage_policy_v0.yaml",
            "index_locator": str(tmp_path / "dla_index.sqlite"),
        }
    )
    assert layout.profile_id == "local_parity"
    assert layout.object_store_prefix == "fraud-platform/local_parity"
    assert layout.retention_window is not None
    assert layout.retention_window.audit_record_ttl_days == 30


def test_phase2_object_writer_is_append_only(tmp_path: Path) -> None:
    layout = build_storage_layout(
        {
            "object_store_prefix": "fraud-platform/local_parity",
            "index_locator": str(tmp_path / "dla_index.sqlite"),
        }
    )
    writer = DecisionLogAuditObjectStore(root_locator=str(tmp_path / "objects"))

    first_record = _audit_record(audit_id="a" * 32, recorded_at_utc="2026-02-07T18:20:01.000000Z")
    first = writer.append_audit_record(record=first_record, layout=layout)
    assert first.status == "NEW"
    object_path = tmp_path / "objects" / Path(*first.object_ref.split("/"))
    initial_bytes = object_path.read_bytes()

    duplicate = writer.append_audit_record(record=first_record, layout=layout)
    assert duplicate.status == "DUPLICATE"
    assert duplicate.record_digest == first.record_digest

    mutated = _audit_record(audit_id="a" * 32, recorded_at_utc="2026-02-07T18:20:02.000000Z")
    mismatch = writer.append_audit_record(record=mutated, layout=layout)
    assert mismatch.status == "HASH_MISMATCH"
    assert object_path.read_bytes() == initial_bytes


def test_phase2_index_lookup_keys_are_deterministic(tmp_path: Path) -> None:
    store = DecisionLogAuditIndexStore(locator=str(tmp_path / "dla_index.sqlite"))
    first = _audit_record(audit_id="a" * 32, recorded_at_utc="2026-02-07T18:20:01.000000Z")
    second = _audit_record(audit_id="b" * 32, recorded_at_utc="2026-02-07T18:20:02.000000Z")

    first_write = store.register_audit_record(first, object_ref="fraud-platform/local/platform_20260207T182000Z/decision_log_audit/records/a.json")
    second_write = store.register_audit_record(second, object_ref="fraud-platform/local/platform_20260207T182000Z/decision_log_audit/records/b.json")
    assert first_write.status == "NEW"
    assert second_write.status == "NEW"

    fetched = store.get_by_audit_id("a" * 32)
    assert fetched is not None
    assert fetched.platform_run_id == "platform_20260207T182000Z"

    run_rows = store.list_by_run_scope(
        platform_run_id="platform_20260207T182000Z",
        scenario_run_id="2" * 32,
        limit=10,
    )
    assert [row.audit_id for row in run_rows] == ["a" * 32, "b" * 32]

    decision_rows = store.list_by_decision_event(decision_event_id="b" * 32, limit=10)
    assert len(decision_rows) == 2
