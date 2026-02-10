from __future__ import annotations

from pathlib import Path

from fraud_detection.decision_log_audit.contracts import AuditRecord
from fraud_detection.decision_log_audit.storage import (
    DecisionLogAuditIndexStore,
    build_storage_layout,
)


def _audit_record() -> AuditRecord:
    payload: dict[str, object] = {
        "audit_id": "a" * 32,
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
        "recorded_at_utc": "2026-02-07T18:20:01.000000Z",
    }
    return AuditRecord.from_payload(payload)


def test_dla_storage_layout_uses_configured_prefix_and_locator(tmp_path: Path) -> None:
    layout = build_storage_layout(
        {
            "object_store_prefix": "fraud-platform",
            "index_locator": str(tmp_path / "dla_index.sqlite"),
        }
    )
    assert layout.index_locator.endswith("dla_index.sqlite")
    assert layout.object_key_for(platform_run_id="platform_20260207T182000Z", audit_id="a" * 32).endswith(
        "/platform_20260207T182000Z/decision_log_audit/records/" + ("a" * 32) + ".json"
    )


def test_dla_index_registers_new_duplicate_and_hash_mismatch(tmp_path: Path) -> None:
    store = DecisionLogAuditIndexStore(locator=str(tmp_path / "dla_index.sqlite"))
    record = _audit_record()

    first = store.register_audit_record(record, object_ref="s3://fraud-platform/audit/a.json")
    assert first.status == "NEW"

    duplicate = store.register_audit_record(record, object_ref="s3://fraud-platform/audit/a.json")
    assert duplicate.status == "DUPLICATE"
    assert duplicate.record_digest == first.record_digest

    changed_payload = record.as_dict()
    changed_payload["recorded_at_utc"] = "2026-02-07T18:20:02.000000Z"
    changed_record = AuditRecord.from_payload(changed_payload)
    mismatch = store.register_audit_record(changed_record, object_ref="s3://fraud-platform/audit/a.json")
    assert mismatch.status == "HASH_MISMATCH"

