import json
from pathlib import Path
import sqlite3

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
    index.rebuild_from_store(
        store,
        receipts_prefix=f"{RUN_PREFIX}/ig/receipts",
        quarantine_prefix=f"{RUN_PREFIX}/ig/quarantine",
    )
    assert index.lookup_event("evt-9") is not None


def test_ops_index_accepts_same_receipt_id_across_platform_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "ops.db"
    index = OpsIndex(db_path)
    shared_receipt_id = "c" * 32

    first = {
        "receipt_id": shared_receipt_id,
        "event_id": "evt-100",
        "event_type": "arrival_events_5B",
        "event_class": "context_arrival",
        "dedupe_key": "x" * 64,
        "decision": "ADMIT",
        "platform_run_id": "platform_20260101T000000Z",
        "scenario_run_id": "a" * 32,
        "run_config_digest": "1" * 64,
        "policy_rev": {"policy_id": "ig", "revision": "v1", "content_digest": "1" * 64},
        "pins": {
            "manifest_fingerprint": "m" * 64,
            "platform_run_id": "platform_20260101T000000Z",
            "scenario_run_id": "a" * 32,
        },
        "eb_ref": {"topic": "fp.bus.context.arrival_events.v1", "partition": 0, "offset": "1", "offset_kind": "file_line"},
    }
    second = {
        **first,
        "event_id": "evt-101",
        "platform_run_id": "platform_20260102T000000Z",
        "scenario_run_id": "b" * 32,
        "pins": {
            "manifest_fingerprint": "m" * 64,
            "platform_run_id": "platform_20260102T000000Z",
            "scenario_run_id": "b" * 32,
        },
        "eb_ref": {"topic": "fp.bus.context.arrival_events.v1", "partition": 0, "offset": "2", "offset_kind": "file_line"},
    }
    index.record_receipt(first, "fraud-platform/platform_20260101T000000Z/ig/receipts/r1.json")
    index.record_receipt(second, "fraud-platform/platform_20260102T000000Z/ig/receipts/r1.json")

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT platform_run_id, receipt_id
            FROM receipts
            WHERE receipt_id = ?
            ORDER BY platform_run_id
            """,
            (shared_receipt_id,),
        ).fetchall()
    assert rows == [
        ("platform_20260101T000000Z", shared_receipt_id),
        ("platform_20260102T000000Z", shared_receipt_id),
    ]


def test_ops_index_migrates_legacy_receipts_pk_to_run_scoped_uniqueness(tmp_path: Path) -> None:
    db_path = tmp_path / "ops_legacy.db"
    shared_receipt_id = "d" * 32
    pins = json.dumps(
        {
            "platform_run_id": "platform_20260101T000000Z",
            "scenario_run_id": "legacy_scenario",
        },
        ensure_ascii=True,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE receipts (
                receipt_id TEXT PRIMARY KEY,
                event_id TEXT,
                event_type TEXT,
                dedupe_key TEXT,
                decision TEXT,
                eb_topic TEXT,
                eb_partition INTEGER,
                policy_id TEXT,
                policy_revision TEXT,
                policy_digest TEXT,
                created_at_utc TEXT,
                receipt_ref TEXT,
                pins_json TEXT,
                reason_codes_json TEXT,
                evidence_refs_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO receipts(
                receipt_id, event_id, event_type, dedupe_key, decision, eb_topic, eb_partition,
                policy_id, policy_revision, policy_digest, created_at_utc, receipt_ref, pins_json,
                reason_codes_json, evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shared_receipt_id,
                "evt-legacy",
                "arrival_events_5B",
                "k" * 64,
                "ADMIT",
                "fp.bus.context.arrival_events.v1",
                0,
                "ig",
                "v1",
                "p" * 64,
                "2026-01-01T00:00:00+00:00",
                "fraud-platform/platform_20260101T000000Z/ig/receipts/legacy.json",
                pins,
                "[]",
                "[]",
            ),
        )
        conn.commit()

    index = OpsIndex(db_path)
    payload = {
        "receipt_id": shared_receipt_id,
        "event_id": "evt-new",
        "event_type": "arrival_events_5B",
        "event_class": "context_arrival",
        "dedupe_key": "n" * 64,
        "decision": "ADMIT",
        "platform_run_id": "platform_20260102T000000Z",
        "scenario_run_id": "new_scenario",
        "run_config_digest": "1" * 64,
        "policy_rev": {"policy_id": "ig", "revision": "v1", "content_digest": "1" * 64},
        "pins": {
            "manifest_fingerprint": "m" * 64,
            "platform_run_id": "platform_20260102T000000Z",
            "scenario_run_id": "new_scenario",
        },
        "eb_ref": {"topic": "fp.bus.context.arrival_events.v1", "partition": 0, "offset": "5", "offset_kind": "file_line"},
    }
    index.record_receipt(payload, "fraud-platform/platform_20260102T000000Z/ig/receipts/new.json")

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT platform_run_id, receipt_id
            FROM receipts
            WHERE receipt_id = ?
            ORDER BY platform_run_id
            """,
            (shared_receipt_id,),
        ).fetchall()
    assert rows == [
        ("platform_20260101T000000Z", shared_receipt_id),
        ("platform_20260102T000000Z", shared_receipt_id),
    ]
