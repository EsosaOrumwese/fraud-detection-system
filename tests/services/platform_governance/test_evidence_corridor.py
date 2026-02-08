from __future__ import annotations

import json
from pathlib import Path

from fraud_detection.platform_governance import (
    EvidenceRefResolutionCorridor,
    EvidenceRefResolutionRequest,
)
from fraud_detection.scenario_runner.storage import LocalObjectStore


def test_evidence_corridor_resolves_allowed_ref_and_emits_audit(tmp_path: Path) -> None:
    run_id = "platform_20260208T220000Z"
    store = LocalObjectStore(tmp_path / "store")
    store.write_json(f"fraud-platform/{run_id}/ig/receipts/r1.json", {"receipt_id": "r1"})
    corridor = EvidenceRefResolutionCorridor(
        store=store,
        actor_allowlist={"svc:test_resolver"},
    )

    result = corridor.resolve(
        EvidenceRefResolutionRequest(
            actor_id="svc:test_resolver",
            source_type="service",
            source_component="unit_test",
            purpose="corridor_validation",
            ref_type="receipt_ref",
            ref_id=f"fraud-platform/{run_id}/ig/receipts/r1.json",
            platform_run_id=run_id,
        )
    )

    assert result.resolution_status == "RESOLVED"
    assert result.reason_code is None
    governance_path = tmp_path / "store" / "fraud-platform" / run_id / "obs" / "governance" / "events.jsonl"
    events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(events) == 1
    assert events[0]["event_family"] == "EVIDENCE_REF_RESOLVED"
    assert events[0]["details"]["resolution_status"] == "RESOLVED"


def test_evidence_corridor_denied_actor_emits_audit_and_anomaly(tmp_path: Path) -> None:
    run_id = "platform_20260208T220100Z"
    store = LocalObjectStore(tmp_path / "store")
    store.write_json(f"fraud-platform/{run_id}/ig/receipts/r2.json", {"receipt_id": "r2"})
    corridor = EvidenceRefResolutionCorridor(
        store=store,
        actor_allowlist={"svc:allowed"},
    )

    result = corridor.resolve(
        EvidenceRefResolutionRequest(
            actor_id="svc:blocked",
            source_type="service",
            source_component="unit_test",
            purpose="corridor_validation",
            ref_type="receipt_ref",
            ref_id=f"fraud-platform/{run_id}/ig/receipts/r2.json",
            platform_run_id=run_id,
        )
    )

    assert result.resolution_status == "DENIED"
    assert result.reason_code == "REF_ACCESS_DENIED"
    governance_path = tmp_path / "store" / "fraud-platform" / run_id / "obs" / "governance" / "events.jsonl"
    events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    families = [item["event_family"] for item in events]
    assert "EVIDENCE_REF_RESOLVED" in families
    assert "CORRIDOR_ANOMALY" in families
    denied = [item for item in events if item["event_family"] == "EVIDENCE_REF_RESOLVED"][-1]
    assert denied["details"]["resolution_status"] == "DENIED"
    assert denied["details"]["reason_code"] == "REF_ACCESS_DENIED"


def test_evidence_corridor_scope_mismatch_emits_anomaly(tmp_path: Path) -> None:
    run_id = "platform_20260208T220200Z"
    other_run_id = "platform_20260208T220201Z"
    store = LocalObjectStore(tmp_path / "store")
    store.write_json(f"fraud-platform/{other_run_id}/ig/receipts/r3.json", {"receipt_id": "r3"})
    corridor = EvidenceRefResolutionCorridor(
        store=store,
        actor_allowlist={"svc:allowed"},
    )

    result = corridor.resolve(
        EvidenceRefResolutionRequest(
            actor_id="svc:allowed",
            source_type="service",
            source_component="unit_test",
            purpose="corridor_validation",
            ref_type="receipt_ref",
            ref_id=f"fraud-platform/{other_run_id}/ig/receipts/r3.json",
            platform_run_id=run_id,
        )
    )

    assert result.resolution_status == "DENIED"
    assert result.reason_code == "REF_SCOPE_MISMATCH"
    governance_path = tmp_path / "store" / "fraud-platform" / run_id / "obs" / "governance" / "events.jsonl"
    events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    anomalies = [item for item in events if item["event_family"] == "CORRIDOR_ANOMALY"]
    assert anomalies
    assert anomalies[-1]["details"]["reason_code"] == "REF_SCOPE_MISMATCH"
