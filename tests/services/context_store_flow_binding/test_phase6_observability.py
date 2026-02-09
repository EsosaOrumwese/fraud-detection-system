from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from fraud_detection.context_store_flow_binding.contracts import FlowBindingRecord, JoinFrameKey
from fraud_detection.context_store_flow_binding.observability import CsfbObservabilityReporter
from fraud_detection.context_store_flow_binding.store import build_store


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260207T030000Z",
        "scenario_run_id": "a" * 32,
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "scenario_id": "baseline_v1",
        "seed": 7,
        "run_id": "d" * 32,
    }


def _join_key(merchant_id: str, arrival_seq: int) -> JoinFrameKey:
    return JoinFrameKey.from_mapping(
        {
            "platform_run_id": _pins()["platform_run_id"],
            "scenario_run_id": _pins()["scenario_run_id"],
            "merchant_id": merchant_id,
            "arrival_seq": arrival_seq,
            "run_id": _pins()["run_id"],
        }
    )


def _source_event(*, event_id: str, event_type: str, topic: str, offset: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "ts_utc": "2026-02-07T03:00:00.000000Z",
        "eb_ref": {
            "topic": topic,
            "partition": 0,
            "offset": offset,
            "offset_kind": "file_line",
        },
    }


def _flow_binding(*, flow_id: str, join_key: JoinFrameKey, event_id: str) -> FlowBindingRecord:
    return FlowBindingRecord.from_mapping(
        {
            "flow_id": flow_id,
            "join_frame_key": join_key.as_dict(),
            "source_event": _source_event(
                event_id=event_id,
                event_type="s2_flow_anchor_baseline_6B",
                topic="fp.bus.context.flow_anchor.baseline.v1",
                offset="1",
            ),
            "authoritative_source_event_type": "s2_flow_anchor_baseline_6B",
            "payload_hash": ("e" * 63) + flow_id[-1],
            "pins": _pins(),
            "bound_at_utc": "2026-02-07T03:00:01.000000Z",
        }
    )


def _seed_store(db_path: Path):
    store = build_store(locator=db_path, stream_id="csfb.v0")
    join_key_hit = _join_key("m-1", 1)
    frame_payload = {
        "join_frame_key": join_key_hit.as_dict(),
        "arrival_event": {"merchant_id": "m-1", "arrival_seq": 1},
        "flow_anchor": {"merchant_id": "m-1", "arrival_seq": 1, "flow_id": "flow-1"},
        "context_complete": True,
    }
    frame_hash = "f" * 64
    store.upsert_join_frame(
        join_frame_key=join_key_hit,
        payload_hash=frame_hash,
        frame_payload=frame_payload,
        source_event=_source_event(
            event_id="1" * 64,
            event_type="arrival_events_5B",
            topic="fp.bus.context.arrival_events.v1",
            offset="0",
        ),
    )
    store.upsert_flow_binding(record=_flow_binding(flow_id="flow-1", join_key=join_key_hit, event_id="2" * 64))

    # Orphan binding drives join_misses metric.
    join_key_orphan = _join_key("m-2", 2)
    store.upsert_flow_binding(record=_flow_binding(flow_id="flow-2", join_key=join_key_orphan, event_id="3" * 64))

    store.record_apply_failure(
        reason_code="FLOW_BINDING_PAYLOAD_HASH_MISMATCH",
        details={"reason": "test"},
        platform_run_id=str(_pins()["platform_run_id"]),
        scenario_run_id=str(_pins()["scenario_run_id"]),
        topic="fp.bus.context.flow_anchor.baseline.v1",
        partition_id=0,
        offset="5",
        offset_kind="file_line",
        event_id="4" * 64,
        event_type="s2_flow_anchor_baseline_6B",
    )
    store.advance_checkpoint(
        topic="fp.bus.context.arrival_events.v1",
        partition_id=0,
        next_offset="10",
        offset_kind="file_line",
        watermark_ts_utc="2026-02-07T03:00:00.000000Z",
    )
    return store


def test_phase6_collect_metrics_and_health(tmp_path: Path) -> None:
    db_path = tmp_path / "csfb.sqlite"
    _seed_store(db_path)
    reporter = CsfbObservabilityReporter.build(locator=db_path, stream_id="csfb.v0")
    payload = reporter.collect(
        platform_run_id=str(_pins()["platform_run_id"]),
        scenario_run_id=str(_pins()["scenario_run_id"]),
    )

    metrics = payload["metrics"]
    assert metrics["join_hits"] == 1
    assert metrics["join_misses"] == 1
    assert metrics["binding_conflicts"] == 1
    assert metrics["apply_failures"] == 1
    assert metrics["apply_failures_hard"] == 1
    assert metrics["late_context_applied"] == 0
    assert payload["threshold_policy_ref"] == "csfb.observability.v0"
    assert payload["applied_offset_basis"] is not None
    assert payload["applied_offset_basis"]["basis_digest"]
    assert len(payload["unresolved_anomalies"]) >= 1
    assert payload["lag_seconds"] is not None
    assert payload["health_state"] in {"AMBER", "RED"}


def test_phase6_health_turns_red_when_checkpoint_and_watermark_stale(tmp_path: Path) -> None:
    db_path = tmp_path / "csfb.sqlite"
    _seed_store(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE csfb_join_checkpoints
            SET watermark_ts_utc = ?, updated_at_utc = ?
            """,
            ("2000-01-01T00:00:00.000000Z", "2000-01-01T00:00:00.000000Z"),
        )
        conn.commit()

    reporter = CsfbObservabilityReporter.build(locator=db_path, stream_id="csfb.v0")
    payload = reporter.collect(
        platform_run_id=str(_pins()["platform_run_id"]),
        scenario_run_id=str(_pins()["scenario_run_id"]),
    )
    assert payload["health_state"] == "RED"
    reasons = set(payload["health_reasons"])
    assert "WATERMARK_TOO_OLD" in reasons
    assert "CHECKPOINT_TOO_OLD" in reasons


def test_phase6_export_writes_reconciliation_artifact(tmp_path: Path) -> None:
    db_path = tmp_path / "csfb.sqlite"
    _seed_store(db_path)
    reporter = CsfbObservabilityReporter.build(locator=db_path, stream_id="csfb.v0")
    output_root = tmp_path / "out"
    payload = reporter.export(
        platform_run_id=str(_pins()["platform_run_id"]),
        scenario_run_id=str(_pins()["scenario_run_id"]),
        output_root=output_root,
    )
    recon_path = output_root / "context_store_flow_binding" / "reconciliation" / "last_reconciliation.json"
    metrics_path = output_root / "context_store_flow_binding" / "metrics" / "last_metrics.json"
    health_path = output_root / "context_store_flow_binding" / "health" / "last_health.json"
    assert recon_path.exists()
    assert metrics_path.exists()
    assert health_path.exists()
    recon = json.loads(recon_path.read_text(encoding="utf-8"))
    assert recon["applied_offset_basis"] == payload["applied_offset_basis"]
    assert recon["unresolved_anomalies"] == payload["unresolved_anomalies"]


def test_phase6_policy_load_applies_env_threshold_overrides(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "csfb.sqlite"
    _seed_store(db_path)
    monkeypatch.setenv("CSFB_HEALTH_AMBER_CHECKPOINT_AGE_SECONDS", "777")
    monkeypatch.setenv("CSFB_HEALTH_RED_CHECKPOINT_AGE_SECONDS", "999")

    reporter = CsfbObservabilityReporter.build(locator=db_path, stream_id="csfb.v0")

    assert reporter.policy.thresholds.amber_checkpoint_age_seconds == 777.0
    assert reporter.policy.thresholds.red_checkpoint_age_seconds == 999.0


def test_phase6_late_applied_anomaly_not_counted_as_hard_apply_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "csfb.sqlite"
    store = build_store(locator=db_path, stream_id="csfb.v0")
    now = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    store.record_apply_failure(
        reason_code="LATE_CONTEXT_EVENT",
        details={
            "applied": True,
            "event_type": "arrival_events_5B",
            "event_ts_utc": "2026-02-07T03:00:00.000000Z",
            "watermark_ts_utc": "2026-02-07T03:00:10.000000Z",
        },
        platform_run_id=str(_pins()["platform_run_id"]),
        scenario_run_id=str(_pins()["scenario_run_id"]),
        topic="fp.bus.context.arrival_events.v1",
        partition_id=0,
        offset="99",
        offset_kind="file_line",
        event_id="9" * 64,
        event_type="arrival_events_5B",
    )
    store.advance_checkpoint(
        topic="fp.bus.context.arrival_events.v1",
        partition_id=0,
        next_offset="100",
        offset_kind="file_line",
        watermark_ts_utc=now,
    )
    reporter = CsfbObservabilityReporter.build(locator=db_path, stream_id="csfb.v0")
    payload = reporter.collect(
        platform_run_id=str(_pins()["platform_run_id"]),
        scenario_run_id=str(_pins()["scenario_run_id"]),
    )

    metrics = payload["metrics"]
    assert metrics["apply_failures"] == 1
    assert metrics["late_context_applied"] == 1
    assert metrics["apply_failures_hard"] == 0
    assert "APPLY_FAILURES_RED" not in set(payload["health_reasons"])
