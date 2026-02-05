import json
from pathlib import Path

from fraud_detection.ingestion_gate.ops_index import OpsIndex
from fraud_detection.ingestion_gate.policy_digest import compute_policy_digest
from fraud_detection.ingestion_gate.store import LocalObjectStore

RUN_PREFIX = "fraud-platform/platform_20260101T000000Z"


def test_policy_digest_is_deterministic(tmp_path: Path) -> None:
    policy_a = tmp_path / "a.yaml"
    policy_b = tmp_path / "b.yaml"
    policy_a.write_text("version: 1\nfoo: bar\n", encoding="utf-8")
    policy_b.write_text("items:\n  - 2\n  - 1\n", encoding="utf-8")

    digest1 = compute_policy_digest([policy_a, policy_b])
    digest2 = compute_policy_digest([policy_b, policy_a])
    assert digest1 == digest2


def test_ops_index_records_and_looks_up(tmp_path: Path) -> None:
    db_path = tmp_path / "ops.db"
    index = OpsIndex(db_path)
    receipt_payload = {
        "receipt_id": "a" * 32,
        "event_id": "evt-1",
        "event_type": "test_event",
        "event_class": "traffic",
        "dedupe_key": "d" * 64,
        "decision": "ADMIT",
        "platform_run_id": "platform_20260101T000000Z",
        "scenario_run_id": "b" * 32,
        "run_config_digest": "c" * 64,
        "policy_rev": {"policy_id": "ig", "revision": "v1", "content_digest": "c" * 64},
        "pins": {"manifest_fingerprint": "b" * 64, "platform_run_id": "platform_20260101T000000Z"},
        "eb_ref": {"topic": "fp.bus.traffic.v1", "partition": 0, "offset": "1", "offset_kind": "file_line"},
    }
    index.record_receipt(receipt_payload, f"{RUN_PREFIX}/ig/receipts/abcd.json")

    lookup = index.lookup_event("evt-1")
    assert lookup is not None
    assert lookup["receipt_id"] == "a" * 32

    quarantine_payload = {
        "quarantine_id": "q" * 32,
        "decision": "QUARANTINE",
        "reason_codes": ["SCHEMA_FAIL"],
        "policy_rev": {"policy_id": "ig", "revision": "v1", "content_digest": "c" * 64},
        "pins": {"manifest_fingerprint": "b" * 64, "platform_run_id": "platform_20260101T000000Z"},
    }
    index.record_quarantine(quarantine_payload, f"{RUN_PREFIX}/ig/quarantine/q.json", "evt-2")
    # ensure no exceptions and DB probe works
    assert index.probe() is True


def test_ops_index_rebuild_from_store(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    receipt_payload = {
        "receipt_id": "b" * 32,
        "event_id": "evt-9",
        "event_type": "test_event",
        "event_class": "traffic",
        "dedupe_key": "e" * 64,
        "decision": "ADMIT",
        "platform_run_id": "platform_20260101T000000Z",
        "scenario_run_id": "b" * 32,
        "run_config_digest": "f" * 64,
        "policy_rev": {"policy_id": "ig", "revision": "v2", "content_digest": "f" * 64},
        "pins": {"manifest_fingerprint": "c" * 64, "platform_run_id": "platform_20260101T000000Z"},
        "eb_ref": {"topic": "fp.bus.traffic.v1", "partition": 0, "offset": "2", "offset_kind": "file_line"},
    }
    quarantine_payload = {
        "quarantine_id": "q" * 32,
        "decision": "QUARANTINE",
        "reason_codes": ["SCHEMA_FAIL"],
        "policy_rev": {"policy_id": "ig", "revision": "v2", "content_digest": "f" * 64},
        "pins": {"manifest_fingerprint": "c" * 64, "platform_run_id": "platform_20260101T000000Z"},
    }
    store.write_json(f"{RUN_PREFIX}/ig/receipts/b.json", receipt_payload)
    store.write_json(f"{RUN_PREFIX}/ig/quarantine/q.json", quarantine_payload)

    index = OpsIndex(tmp_path / "ops.db")
    index.rebuild_from_store(store)
    assert index.lookup_event("evt-9") is not None
