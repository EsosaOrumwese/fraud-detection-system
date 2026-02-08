from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pytest

from fraud_detection.decision_log_audit.config import load_intake_policy
from fraud_detection.decision_log_audit.intake import DlaBusInput, DecisionLogAuditIntakeProcessor
from fraud_detection.decision_log_audit.observability import (
    DecisionLogAuditObservabilityReporter,
)
from fraud_detection.decision_log_audit.storage import DecisionLogAuditIntakeStore


PINS = {
    "platform_run_id": "platform_20260207T220000Z",
    "scenario_run_id": "1" * 32,
    "manifest_fingerprint": "2" * 64,
    "parameter_hash": "3" * 64,
    "scenario_id": "scenario.v0",
    "seed": 42,
    "run_id": "1" * 32,
}


@dataclass(frozen=True)
class _ParityProof:
    expected_events: int
    observed_resolved_chains: int
    unresolved_chains: int
    quarantine_total: int
    replay_divergence_total: int
    status: str
    reasons: tuple[str, ...]
    artifact_path: str


def _policy():
    return load_intake_policy(Path("config/platform/dla/intake_policy_v0.yaml"))


def _decision_payload(*, decision_id: str, amount: float = 100.0) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "decision_kind": "txn_disposition",
        "bundle_ref": {"bundle_id": "b" * 64, "bundle_version": "2026.02.07", "registry_ref": "registry://active"},
        "snapshot_hash": "c" * 64,
        "graph_version": {"version_id": "d" * 32, "watermark_ts_utc": "2026-02-07T10:27:00.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "101"}],
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
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1"},
            "posture_seq": 3,
            "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        },
        "pins": {
            "platform_run_id": PINS["platform_run_id"],
            "scenario_run_id": PINS["scenario_run_id"],
            "manifest_fingerprint": PINS["manifest_fingerprint"],
            "parameter_hash": PINS["parameter_hash"],
            "scenario_id": PINS["scenario_id"],
            "seed": PINS["seed"],
            "run_id": PINS["run_id"],
        },
        "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8"},
        "run_config_digest": "4" * 64,
        "source_event": {
            "event_id": f"src_{decision_id}",
            "event_type": "transaction_authorization",
            "ts_utc": "2026-02-07T10:26:59.000000Z",
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": "100",
                "offset_kind": "kinesis_sequence",
            },
        },
        "decision": {"disposition": "ALLOW", "amount": amount},
    }


def _action_intent_payload(*, decision_id: str, action_id: str) -> dict[str, object]:
    return {
        "action_id": action_id,
        "decision_id": decision_id,
        "action_kind": "txn_disposition_publish",
        "idempotency_key": f"{decision_id}:{action_id}:publish",
        "pins": {
            "platform_run_id": PINS["platform_run_id"],
            "scenario_run_id": PINS["scenario_run_id"],
            "manifest_fingerprint": PINS["manifest_fingerprint"],
            "parameter_hash": PINS["parameter_hash"],
            "scenario_id": PINS["scenario_id"],
            "seed": PINS["seed"],
            "run_id": PINS["run_id"],
        },
        "requested_at_utc": "2026-02-07T10:27:01.000000Z",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8"},
        "run_config_digest": "4" * 64,
        "action_payload": {"target": "fraud.disposition"},
    }


def _action_outcome_payload(*, decision_id: str, action_id: str, outcome_id: str) -> dict[str, object]:
    return {
        "outcome_id": outcome_id,
        "decision_id": decision_id,
        "action_id": action_id,
        "action_kind": "txn_disposition_publish",
        "status": "EXECUTED",
        "idempotency_key": f"{decision_id}:{action_id}:publish",
        "actor_principal": "SYSTEM::action_layer",
        "origin": "DF",
        "authz_policy_rev": {"policy_id": "al.authz.v0", "revision": "r5"},
        "run_config_digest": "4" * 64,
        "pins": {
            "platform_run_id": PINS["platform_run_id"],
            "scenario_run_id": PINS["scenario_run_id"],
            "manifest_fingerprint": PINS["manifest_fingerprint"],
            "parameter_hash": PINS["parameter_hash"],
            "scenario_id": PINS["scenario_id"],
            "seed": PINS["seed"],
            "run_id": PINS["run_id"],
        },
        "completed_at_utc": "2026-02-07T10:27:02.000000Z",
        "attempt_seq": 1,
        "outcome_payload": {"receipt": "ok"},
    }


def _envelope(*, event_id: str, event_type: str, payload: dict[str, object], ts_utc: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": "v1",
        "ts_utc": ts_utc,
        "manifest_fingerprint": PINS["manifest_fingerprint"],
        "parameter_hash": PINS["parameter_hash"],
        "seed": PINS["seed"],
        "scenario_id": PINS["scenario_id"],
        "platform_run_id": PINS["platform_run_id"],
        "scenario_run_id": PINS["scenario_run_id"],
        "run_id": PINS["run_id"],
        "payload": payload,
    }


def _process(processor: DecisionLogAuditIntakeProcessor, *, offset: int, envelope: dict[str, object]):
    return processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset=str(offset),
            offset_kind="file_line",
            payload=envelope,
        )
    )


def _decision_id(index: int) -> str:
    return f"{index:032x}"[-32:]


def _action_id(index: int) -> str:
    return f"{index + 10_000:032x}"[-32:]


def _outcome_id(index: int) -> str:
    return f"{index + 20_000:032x}"[-32:]


def _build_run(
    *,
    processor: DecisionLogAuditIntakeProcessor,
    event_count: int,
    start_offset: int = 0,
) -> int:
    offset = start_offset
    for index in range(event_count):
        decision_id = _decision_id(index)
        action_id = _action_id(index)
        outcome_id = _outcome_id(index)
        decision = _process(
            processor,
            offset=offset,
            envelope=_envelope(
                event_id=f"evt_decision_{index}",
                event_type="decision_response",
                payload=_decision_payload(decision_id=decision_id, amount=100.0 + float(index)),
                ts_utc="2026-02-07T10:27:00.000000Z",
            ),
        )
        assert decision.accepted is True
        offset += 1
        intent = _process(
            processor,
            offset=offset,
            envelope=_envelope(
                event_id=f"evt_intent_{index}",
                event_type="action_intent",
                payload=_action_intent_payload(decision_id=decision_id, action_id=action_id),
                ts_utc="2026-02-07T10:27:01.000000Z",
            ),
        )
        assert intent.accepted is True
        offset += 1
        outcome = _process(
            processor,
            offset=offset,
            envelope=_envelope(
                event_id=f"evt_outcome_{index}",
                event_type="action_outcome",
                payload=_action_outcome_payload(decision_id=decision_id, action_id=action_id, outcome_id=outcome_id),
                ts_utc="2026-02-07T10:27:02.000000Z",
            ),
        )
        assert outcome.accepted is True
        offset += 1
    return offset


def test_phase8_df_al_surfaces_form_complete_dla_chain(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)
    _build_run(processor=processor, event_count=1)

    decision_id = _decision_id(0)
    chain = store.get_lineage_chain(decision_id=decision_id)
    assert chain is not None
    assert chain.chain_status == "RESOLVED"
    assert chain.unresolved_reasons == ()
    intents = store.list_lineage_intents(decision_id=decision_id)
    outcomes = store.list_lineage_outcomes(decision_id=decision_id)
    assert len(intents) == 1
    assert len(outcomes) == 1
    assert intents[0].action_id == _action_id(0)
    assert outcomes[0].action_id == _action_id(0)
    assert outcomes[0].outcome_id == _outcome_id(0)


@pytest.mark.parametrize("event_count", [20, 200])
def test_phase8_component_local_parity_proof(event_count: int, tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / f"dla_intake_{event_count}.sqlite"))
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)
    _build_run(processor=processor, event_count=event_count)

    reporter = DecisionLogAuditObservabilityReporter(
        store=store,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    payload = reporter.export()
    metrics = payload["metrics"]

    reasons: list[str] = []
    resolved_total = int(metrics.get("lineage_resolved_total", 0))
    unresolved_total = int(metrics.get("lineage_unresolved_total", 0))
    quarantine_total = int(metrics.get("quarantine_total", 0))
    replay_divergence_total = int(metrics.get("replay_divergence_total", 0))

    if resolved_total != event_count:
        reasons.append(f"RESOLVED_MISMATCH:{resolved_total}:{event_count}")
    if unresolved_total != 0:
        reasons.append(f"UNRESOLVED_NONZERO:{unresolved_total}")
    if quarantine_total != 0:
        reasons.append(f"QUARANTINE_NONZERO:{quarantine_total}")
    if replay_divergence_total != 0:
        reasons.append(f"REPLAY_DIVERGENCE_NONZERO:{replay_divergence_total}")
    if payload["health_state"] != "GREEN":
        reasons.append(f"HEALTH_NOT_GREEN:{payload['health_state']}")

    artifact_dir = Path("runs/fraud-platform") / PINS["platform_run_id"] / "decision_log_audit" / "reconciliation"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"phase8_parity_proof_{event_count}.json"
    proof = _ParityProof(
        expected_events=event_count,
        observed_resolved_chains=resolved_total,
        unresolved_chains=unresolved_total,
        quarantine_total=quarantine_total,
        replay_divergence_total=replay_divergence_total,
        status="PASS" if not reasons else "FAIL",
        reasons=tuple(reasons),
        artifact_path=str(artifact_path),
    )
    artifact_path.write_text(
        json.dumps(
            {
                "expected_events": proof.expected_events,
                "observed_resolved_chains": proof.observed_resolved_chains,
                "unresolved_chains": proof.unresolved_chains,
                "quarantine_total": proof.quarantine_total,
                "replay_divergence_total": proof.replay_divergence_total,
                "status": proof.status,
                "reasons": list(proof.reasons),
                "artifact_path": proof.artifact_path,
            },
            sort_keys=True,
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert proof.status == "PASS"


def test_phase8_replay_reconstructs_identical_lineage_from_same_basis(tmp_path: Path) -> None:
    event_count = 40
    source = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_source.sqlite"))
    source_processor = DecisionLogAuditIntakeProcessor(_policy(), source)
    _build_run(processor=source_processor, event_count=event_count)
    source_hash = source.lineage_fingerprint(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )

    rebuilt = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_rebuilt.sqlite"))
    rebuilt_processor = DecisionLogAuditIntakeProcessor(_policy(), rebuilt)
    _build_run(processor=rebuilt_processor, event_count=event_count)
    rebuilt_hash = rebuilt.lineage_fingerprint(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    assert source_hash == rebuilt_hash

    before_metrics = source.intake_metrics_snapshot(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    _build_run(processor=source_processor, event_count=event_count, start_offset=0)
    after_metrics = source.intake_metrics_snapshot(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    assert after_metrics["candidate_total"] == before_metrics["candidate_total"]
    assert source.lineage_fingerprint(
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    ) == source_hash
