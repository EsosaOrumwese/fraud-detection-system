from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.decision_fabric.observability import DfRunMetrics


def _decision_payload(
    *,
    decision_id: str,
    mode: str = "NORMAL",
    context_status: str = "CONTEXT_READY",
    registry_outcome: str = "RESOLVED",
    reason_codes: tuple[str, ...] = tuple(),
) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "decision_kind": "fraud_decision_v0",
        "bundle_ref": {"bundle_id": "a" * 64},
        "snapshot_hash": "b" * 64,
        "graph_version": {"version_id": "c" * 32, "watermark_ts_utc": "2026-02-07T13:00:00.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "9"}],
        },
        "degrade_posture": {
            "mode": mode,
            "capabilities_mask": {
                "allow_ieg": True,
                "allowed_feature_groups": ["core_features"],
                "allow_model_primary": True,
                "allow_model_stage2": False,
                "allow_fallback_heuristics": True,
                "action_posture": "NORMAL",
            },
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1"},
            "posture_seq": 1,
            "decided_at_utc": "2026-02-07T13:00:00.000000Z",
        },
        "pins": {
            "platform_run_id": "platform_20260207T130000Z",
            "scenario_run_id": "d" * 32,
            "manifest_fingerprint": "e" * 64,
            "parameter_hash": "f" * 64,
            "scenario_id": "fraud_synth_v1",
            "seed": 7,
        },
        "decided_at_utc": "2026-02-07T13:00:00.000000Z",
        "policy_rev": {"policy_id": "df.registry_resolution.v0", "revision": "r1"},
        "run_config_digest": "1" * 64,
        "source_event": {
            "event_id": f"evt_{decision_id}",
            "event_type": "transaction_fraud",
            "ts_utc": "2026-02-07T13:00:00.000000Z",
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": "9",
                "offset_kind": "kinesis_sequence",
            },
        },
        "decision": {
            "action_kind": "ALLOW",
            "context_status": context_status,
            "registry_outcome": registry_outcome,
        },
        "reason_codes": list(reason_codes),
    }


def test_run_metrics_tracks_required_counters_and_latency_percentiles(tmp_path: Path) -> None:
    metrics = DfRunMetrics(
        platform_run_id="platform_20260207T130000Z",
        scenario_run_id="d" * 32,
    )
    metrics.record_decision(
        decision_payload=_decision_payload(decision_id="1" * 32),
        latency_ms=12.0,
        publish_decision="ADMIT",
    )
    metrics.record_decision(
        decision_payload=_decision_payload(
            decision_id="2" * 32,
            mode="SAFE_STOP",
            context_status="CONTEXT_MISSING",
            reason_codes=("CONTEXT_MISSING:flow_anchor",),
        ),
        latency_ms=35.0,
        publish_decision="DUPLICATE",
    )
    metrics.record_decision(
        decision_payload=_decision_payload(
            decision_id="3" * 32,
            mode="FAIL_CLOSED",
            registry_outcome="FAIL_CLOSED",
            reason_codes=("RESOLUTION_FAIL_CLOSED",),
        ),
        latency_ms=70.0,
        publish_decision="QUARANTINE",
    )
    metrics.record_decision(
        decision_payload=_decision_payload(
            decision_id="4" * 32,
            context_status="CONTEXT_WAITING",
            reason_codes=("CONTEXT_WAITING:flow_anchor",),
        ),
        latency_ms=99.0,
    )

    snapshot = metrics.snapshot(generated_at_utc="2026-02-07T13:01:00.000000Z")
    assert snapshot["metrics"]["decisions_total"] == 4
    assert snapshot["metrics"]["degrade_total"] == 3
    assert snapshot["metrics"]["missing_context_total"] == 2
    assert snapshot["metrics"]["resolver_failures_total"] == 1
    assert snapshot["metrics"]["fail_closed_total"] == 1
    assert snapshot["metrics"]["publish_admit_total"] == 1
    assert snapshot["metrics"]["publish_duplicate_total"] == 1
    assert snapshot["metrics"]["publish_quarantine_total"] == 1
    assert snapshot["latency_ms"]["p50"] == 35.0
    assert snapshot["latency_ms"]["p95"] == 99.0
    assert snapshot["latency_ms"]["p99"] == 99.0

    output_path = tmp_path / "metrics.json"
    exported = metrics.export(output_path=output_path, generated_at_utc="2026-02-07T13:01:00.000000Z")
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["latency_ms"]["count"] == 4
    assert loaded["platform_run_id"] == "platform_20260207T130000Z"


def test_run_metrics_fails_closed_on_run_scope_mismatch() -> None:
    metrics = DfRunMetrics(
        platform_run_id="platform_20260207T130000Z",
        scenario_run_id="d" * 32,
    )
    bad = _decision_payload(decision_id="5" * 32)
    bad["pins"] = dict(bad["pins"])
    bad["pins"]["platform_run_id"] = "platform_other"
    with pytest.raises(ValueError, match="platform_run_id mismatch"):
        metrics.record_decision(decision_payload=bad, latency_ms=1.0)
