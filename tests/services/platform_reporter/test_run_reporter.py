from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import yaml

from fraud_detection.platform_reporter import run_reporter as run_reporter_module
from fraud_detection.platform_reporter.run_reporter import PlatformRunReporter


def test_platform_run_reporter_exports_cross_plane_artifact(tmp_path: Path, monkeypatch) -> None:
    platform_run_id = "platform_20260208T210000Z"
    scenario_run_id = "scenario_abc123"

    runs_root = tmp_path / "runs"
    monkeypatch.setattr(run_reporter_module, "RUNS_ROOT", runs_root)

    object_store_root = tmp_path / "fraud-platform"
    ig_db = tmp_path / "ig.sqlite"
    ieg_db = tmp_path / "ieg.sqlite"
    ofp_db = tmp_path / "ofp.sqlite"
    ofp_index_db = tmp_path / "ofp_index.sqlite"
    csfb_db = tmp_path / "csfb.sqlite"
    bus_root = tmp_path / "bus"
    profile_path = tmp_path / "profile.yaml"

    _write_profile(
        profile_path=profile_path,
        object_store_root=object_store_root,
        ig_db=ig_db,
        ieg_db=ieg_db,
        ofp_db=ofp_db,
        ofp_index_db=ofp_index_db,
        csfb_db=csfb_db,
        bus_root=bus_root,
    )
    _write_wsp_ready_record(
        object_store_root=object_store_root,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
    )
    _seed_ig_tables(
        db_path=ig_db,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
    )
    _seed_ieg_store(
        db_path=ieg_db,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
    )
    _seed_ofp_store(db_path=ofp_db, scenario_run_id=scenario_run_id)
    _seed_csfb_store(
        db_path=csfb_db,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
    )

    (runs_root / platform_run_id / "identity_entity_graph" / "reconciliation").mkdir(parents=True, exist_ok=True)
    (runs_root / platform_run_id / "identity_entity_graph" / "reconciliation" / "reconciliation.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (runs_root / platform_run_id / "decision_log_audit" / "metrics").mkdir(parents=True, exist_ok=True)
    (runs_root / platform_run_id / "decision_log_audit" / "metrics" / "last_metrics.json").write_text(
        json.dumps({"metrics": {"append_success_total": 5}}, ensure_ascii=True),
        encoding="utf-8",
    )

    reporter = PlatformRunReporter.build(profile_path=str(profile_path), platform_run_id=platform_run_id)
    payload = reporter.export()

    assert payload["platform_run_id"] == platform_run_id
    assert payload["ingress"]["sent"] == 20
    assert payload["ingress"]["received"] == 4
    assert payload["ingress"]["admit"] == 2
    assert payload["ingress"]["quarantine"] == 1
    assert payload["ingress"]["publish_ambiguous"] == 1
    assert payload["ingress"]["receipt_write_failed"] == 1
    assert payload["rtdl"]["decision"] == 1
    assert payload["rtdl"]["outcome"] == 1
    assert payload["rtdl"]["audit_append"] == 5
    assert payload["basis"]["evidence_ref_resolution"]["attempted"] >= 1
    assert payload["basis"]["provenance"]["service_release_id"] == "dev-local"
    assert payload["basis"]["provenance"]["environment"] == "test"
    assert payload["artifact_refs"]["local_path"]
    assert payload["artifact_refs"]["object_store_path"].endswith("/obs/platform_run_report.json")

    governance_path = object_store_root / platform_run_id / "obs" / "governance" / "events.jsonl"
    assert governance_path.exists()
    event_families = [
        json.loads(line)["event_family"]
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert "EVIDENCE_REF_RESOLVED" in event_families
    assert "RUN_REPORT_GENERATED" in event_families
    events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reporter_events = [item for item in events if item.get("event_family") == "RUN_REPORT_GENERATED"]
    assert reporter_events
    assert reporter_events[-1]["actor"]["actor_id"] == "SYSTEM::platform_run_reporter"
    assert reporter_events[-1]["provenance"]["environment"] == "test"


def _write_profile(
    *,
    profile_path: Path,
    object_store_root: Path,
    ig_db: Path,
    ieg_db: Path,
    ofp_db: Path,
    ofp_index_db: Path,
    csfb_db: Path,
    bus_root: Path,
) -> None:
    payload = {
        "profile_id": "test",
        "policy": {
            "policy_rev": "test-v0",
            "partitioning_profiles_ref": "config/platform/ig/partitioning_profiles_v0.yaml",
            "partitioning_profile_id": "ig.partitioning.v0.traffic",
        },
        "wiring": {
            "object_store": {
                "root": str(object_store_root),
            },
            "admission_db_path": str(ig_db),
            "event_bus": {"root": str(bus_root)},
        },
        "ieg": {
            "policy": {
                "classification_ref": "config/platform/ieg/classification_v0.yaml",
                "identity_hints_ref": "config/platform/ieg/identity_hints_v0.yaml",
                "retention_ref": "config/platform/ieg/retention_v0.yaml",
                "class_map_ref": "config/platform/ig/class_map_v0.yaml",
                "partitioning_profiles_ref": "config/platform/ig/partitioning_profiles_v0.yaml",
                "graph_stream_id": "ieg.v0",
            },
            "wiring": {
                "projection_db_dsn": str(ieg_db),
                "event_bus_kind": "file",
                "event_bus": {"root": str(bus_root), "topics": ["fp.bus.traffic.fraud.v1"]},
            },
        },
        "ofp": {
            "policy": {
                "stream_id": "ofp.v0",
                "features_ref": "config/platform/ofp/features_v0.yaml",
            },
            "wiring": {
                "projection_db_dsn": str(ofp_db),
                "snapshot_index_dsn": str(ofp_index_db),
                "event_bus_kind": "file",
                "event_bus": {"root": str(bus_root), "topics": ["fp.bus.traffic.fraud.v1"]},
            },
        },
        "context_store_flow_binding": {
            "policy": {
                "stream_id": "csfb.v0",
                "class_map_ref": "config/platform/ig/class_map_v0.yaml",
                "context_event_classes": [
                    "context_arrival",
                    "context_arrival_entities",
                    "context_flow_fraud",
                ],
                "context_topics": ["fp.bus.context.arrival_events.v1"],
            },
            "wiring": {
                "projection_db_dsn": str(csfb_db),
                "event_bus_kind": "file",
                "event_bus": {"root": str(bus_root)},
            },
        },
    }
    profile_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_wsp_ready_record(
    *,
    object_store_root: Path,
    platform_run_id: str,
    scenario_run_id: str,
) -> None:
    path = object_store_root / platform_run_id / "wsp" / "ready_runs" / ("m" * 64 + ".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "message_id": "m" * 64,
        "run_id": scenario_run_id,
        "status": "STREAMED",
        "emitted": 20,
    }
    path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")


def _seed_ig_tables(*, db_path: Path, platform_run_id: str, scenario_run_id: str) -> None:
    pins = json.dumps({"platform_run_id": platform_run_id, "scenario_run_id": scenario_run_id}, ensure_ascii=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE admissions (
                dedupe_key TEXT PRIMARY KEY,
                state TEXT,
                platform_run_id TEXT,
                receipt_write_failed INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE receipts (
                decision TEXT,
                event_type TEXT,
                receipt_ref TEXT,
                pins_json TEXT,
                evidence_refs_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE quarantines (
                evidence_ref TEXT,
                pins_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO admissions(dedupe_key, state, platform_run_id, receipt_write_failed) VALUES (?, ?, ?, ?)",
            ("a1", "ADMITTED", platform_run_id, 0),
        )
        conn.execute(
            "INSERT INTO admissions(dedupe_key, state, platform_run_id, receipt_write_failed) VALUES (?, ?, ?, ?)",
            ("a2", "PUBLISH_AMBIGUOUS", platform_run_id, 0),
        )
        conn.execute(
            "INSERT INTO admissions(dedupe_key, state, platform_run_id, receipt_write_failed) VALUES (?, ?, ?, ?)",
            ("a3", "ADMITTED", platform_run_id, 1),
        )
        conn.execute(
            "INSERT INTO receipts(decision, event_type, receipt_ref, pins_json, evidence_refs_json) VALUES (?, ?, ?, ?, ?)",
            ("ADMIT", "s3_event_stream_with_fraud_6B", "s3://fraud-platform/r1.json", pins, "[]"),
        )
        conn.execute(
            "INSERT INTO receipts(decision, event_type, receipt_ref, pins_json, evidence_refs_json) VALUES (?, ?, ?, ?, ?)",
            ("ADMIT", "decision_response", "s3://fraud-platform/r2.json", pins, "[]"),
        )
        conn.execute(
            "INSERT INTO receipts(decision, event_type, receipt_ref, pins_json, evidence_refs_json) VALUES (?, ?, ?, ?, ?)",
            (
                "QUARANTINE",
                "action_outcome",
                "s3://fraud-platform/r3.json",
                pins,
                json.dumps([{"kind": "quarantine_record", "ref": "s3://fraud-platform/q1.json"}], ensure_ascii=True),
            ),
        )
        conn.execute(
            "INSERT INTO quarantines(evidence_ref, pins_json) VALUES (?, ?)",
            ("s3://fraud-platform/q2.json", pins),
        )


def _seed_ieg_store(*, db_path: Path, platform_run_id: str, scenario_run_id: str) -> None:
    from fraud_detection.identity_entity_graph.store import build_store

    build_store(str(db_path), stream_id="ieg.v0", run_config_digest="c" * 64)
    now = "2026-02-08T21:00:00+00:00"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO ieg_metrics(stream_id, scenario_run_id, metric_name, metric_value, updated_at_utc) VALUES (?, ?, ?, ?, ?)",
            ("ieg.v0", scenario_run_id, "events_seen", 12, now),
        )
        conn.execute(
            "INSERT INTO ieg_metrics(stream_id, scenario_run_id, metric_name, metric_value, updated_at_utc) VALUES (?, ?, ?, ?, ?)",
            ("ieg.v0", scenario_run_id, "duplicate", 2, now),
        )
        conn.execute(
            """
            INSERT INTO ieg_apply_failures(
                failure_id, stream_id, topic, partition_id, "offset", offset_kind, event_id, event_type,
                platform_run_id, scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "f1",
                "ieg.v0",
                "fp.bus.context.arrival_events.v1",
                0,
                "1",
                "file_line",
                "e1",
                "arrival_events_5B",
                platform_run_id,
                scenario_run_id,
                "TEST_FAILURE",
                "{}",
                now,
                now,
            ),
        )


def _seed_ofp_store(*, db_path: Path, scenario_run_id: str) -> None:
    from fraud_detection.online_feature_plane.store import build_store

    store = build_store(
        str(db_path),
        stream_id="ofp.v0",
        basis_stream="fp.bus.traffic.fraud.v1",
        run_config_digest="d" * 64,
        feature_def_policy_id="ofp.features.v0",
        feature_def_revision="r1",
        feature_def_content_digest="e" * 64,
    )
    store.increment_metric(scenario_run_id=scenario_run_id, metric_name="events_seen", delta=7)
    store.increment_metric(scenario_run_id=scenario_run_id, metric_name="duplicates", delta=1)
    store.increment_metric(scenario_run_id=scenario_run_id, metric_name="payload_hash_mismatch", delta=1)


def _seed_csfb_store(*, db_path: Path, platform_run_id: str, scenario_run_id: str) -> None:
    from fraud_detection.context_store_flow_binding.store import build_store

    store = build_store(locator=str(db_path), stream_id="csfb.v0")
    store.record_apply_failure(
        reason_code="TEST_CSFB_FAILURE",
        details={"kind": "unit"},
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        topic="fp.bus.context.arrival_events.v1",
        partition_id=0,
        offset="1",
        offset_kind="file_line",
        event_id="c1",
        event_type="arrival_events_5B",
    )
