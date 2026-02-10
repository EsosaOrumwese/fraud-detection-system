from __future__ import annotations

import json
from pathlib import Path

from fraud_detection.decision_fabric.reconciliation import DfReconciliationBuilder


def _decision_payload(
    *,
    decision_id: str,
    mode: str,
    bundle_id: str,
    action_kind: str,
    registry_outcome: str = "RESOLVED",
    reason_codes: tuple[str, ...] = tuple(),
) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "decision_kind": "fraud_decision_v0",
        "bundle_ref": {"bundle_id": bundle_id},
        "snapshot_hash": "1" * 64,
        "graph_version": {"version_id": "2" * 32, "watermark_ts_utc": "2026-02-07T13:30:00.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "11"}],
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
            "decided_at_utc": "2026-02-07T13:30:00.000000Z",
        },
        "pins": {
            "platform_run_id": "platform_20260207T133000Z",
            "scenario_run_id": "a" * 32,
            "manifest_fingerprint": "3" * 64,
            "parameter_hash": "4" * 64,
            "scenario_id": "fraud_synth_v1",
            "seed": 7,
        },
        "decided_at_utc": "2026-02-07T13:30:00.000000Z",
        "policy_rev": {"policy_id": "df.registry_resolution.v0", "revision": "r1"},
        "run_config_digest": "5" * 64,
        "source_event": {
            "event_id": f"evt_{decision_id}",
            "event_type": "transaction_fraud",
            "ts_utc": "2026-02-07T13:30:00.000000Z",
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": "11",
                "offset_kind": "kinesis_sequence",
            },
        },
        "decision": {
            "action_kind": action_kind,
            "context_status": "CONTEXT_READY",
            "registry_outcome": registry_outcome,
        },
        "reason_codes": list(reason_codes),
    }


def _intent(*, decision_id: str, action_id: str) -> dict[str, object]:
    return {
        "action_id": action_id,
        "decision_id": decision_id,
        "action_kind": "ALLOW",
        "idempotency_key": f"idem-{action_id}",
        "pins": {
            "platform_run_id": "platform_20260207T133000Z",
            "scenario_run_id": "a" * 32,
            "manifest_fingerprint": "3" * 64,
            "parameter_hash": "4" * 64,
            "scenario_id": "fraud_synth_v1",
            "seed": 7,
        },
        "requested_at_utc": "2026-02-07T13:30:00.100000Z",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "policy_rev": {"policy_id": "df.registry_resolution.v0", "revision": "r1"},
        "run_config_digest": "5" * 64,
    }


def test_reconciliation_summary_groups_mode_bundle_action_and_evidence(tmp_path: Path) -> None:
    builder = DfReconciliationBuilder(
        platform_run_id="platform_20260207T133000Z",
        scenario_run_id="a" * 32,
    )
    builder.add_record(
        decision_payload=_decision_payload(
            decision_id="1" * 32,
            mode="NORMAL",
            bundle_id="b" * 64,
            action_kind="ALLOW",
        ),
        action_intents=(_intent(decision_id="1" * 32, action_id="9" * 32),),
        publish_decision="ADMIT",
        decision_receipt_ref="runs/fraud-platform/platform_20260207T133000Z/ingestion_gate/receipts/r1.json",
        action_receipt_refs=("runs/fraud-platform/platform_20260207T133000Z/ingestion_gate/receipts/a1.json",),
    )
    builder.add_record(
        decision_payload=_decision_payload(
            decision_id="2" * 32,
            mode="SAFE_STOP",
            bundle_id="b" * 64,
            action_kind="STEP_UP",
            reason_codes=("CONTEXT_MISSING:flow_anchor",),
        ),
        publish_decision="DUPLICATE",
    )
    builder.add_record(
        decision_payload=_decision_payload(
            decision_id="3" * 32,
            mode="FAIL_CLOSED",
            bundle_id="c" * 64,
            action_kind="QUEUE_REVIEW",
            registry_outcome="FAIL_CLOSED",
            reason_codes=("RESOLUTION_FAIL_CLOSED",),
        ),
        publish_decision="QUARANTINE",
    )

    summary = builder.summary(generated_at_utc="2026-02-07T13:31:00.000000Z")
    assert summary["totals"]["decisions_total"] == 3
    assert summary["totals"]["degrade_total"] == 2
    assert summary["totals"]["fail_closed_total"] == 1
    assert summary["totals"]["quarantined_total"] == 1
    assert summary["by_mode"]["NORMAL"] == 1
    assert summary["by_mode"]["SAFE_STOP"] == 1
    assert summary["by_mode"]["FAIL_CLOSED"] == 1
    assert summary["by_bundle_id"]["b" * 64] == 2
    assert summary["by_bundle_id"]["c" * 64] == 1
    assert summary["by_action_kind"]["ALLOW"] == 1
    assert summary["by_action_kind"]["STEP_UP"] == 1
    assert summary["by_action_kind"]["QUEUE_REVIEW"] == 1
    assert summary["evidence_refs"][0]["source_eb_ref"]["topic"] == "fp.bus.traffic.fraud.v1"

    output_path = tmp_path / "reconciliation.json"
    exported = builder.export(output_path=output_path, generated_at_utc="2026-02-07T13:31:00.000000Z")
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["platform_run_id"] == "platform_20260207T133000Z"
    assert loaded["totals"]["decisions_total"] == 3


def test_reconciliation_parity_proof_pass_and_fail() -> None:
    builder = DfReconciliationBuilder(
        platform_run_id="platform_20260207T133000Z",
        scenario_run_id="a" * 32,
    )
    for index in range(20):
        digest = f"{index + 1:064x}"[-64:]
        decision_id = f"{index + 1:032x}"[-32:]
        builder.add_record(
            decision_payload=_decision_payload(
                decision_id=decision_id,
                mode="NORMAL",
                bundle_id=digest,
                action_kind="ALLOW",
            ),
            publish_decision="ADMIT",
        )
    proof_pass = builder.parity_proof(expected_events=20)
    assert proof_pass.status == "PASS"
    assert proof_pass.observed_events == 20
    proof_fail = builder.parity_proof(expected_events=200)
    assert proof_fail.status == "FAIL"
    assert proof_fail.reasons == ("OBSERVED_MISMATCH:20:200",)
