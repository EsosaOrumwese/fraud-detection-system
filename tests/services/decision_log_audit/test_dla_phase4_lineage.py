from __future__ import annotations

import sqlite3
from pathlib import Path

from fraud_detection.decision_log_audit.config import load_intake_policy
from fraud_detection.decision_log_audit.intake import (
    DLA_INTAKE_LINEAGE_CONFLICT,
    DLA_INTAKE_WRITE_FAILED,
    DlaBusInput,
    DecisionLogAuditIntakeProcessor,
)
from fraud_detection.decision_log_audit.storage import DecisionLogAuditIntakeStore


PINS = {
    "platform_run_id": "platform_20260207T102700Z",
    "scenario_run_id": "1" * 32,
    "manifest_fingerprint": "2" * 64,
    "parameter_hash": "3" * 64,
    "scenario_id": "scenario.v0",
    "seed": 42,
    "run_id": "1" * 32,
}


def _policy():
    return load_intake_policy(Path("config/platform/dla/intake_policy_v0.yaml"))


def _decision_payload(*, decision_id: str = "a" * 32, amount: float = 100.0) -> dict[str, object]:
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
            "event_id": "evt_src",
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


def _action_intent_payload(*, decision_id: str = "a" * 32, action_id: str = "5" * 32) -> dict[str, object]:
    return {
        "action_id": action_id,
        "decision_id": decision_id,
        "action_kind": "txn_disposition_publish",
        "idempotency_key": "merchant_42:evt_123:publish",
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


def _action_outcome_payload(
    *,
    decision_id: str = "a" * 32,
    action_id: str = "5" * 32,
    outcome_id: str = "8" * 32,
    run_config_digest: str = "4" * 64,
) -> dict[str, object]:
    return {
        "outcome_id": outcome_id,
        "decision_id": decision_id,
        "action_id": action_id,
        "action_kind": "txn_disposition_publish",
        "status": "EXECUTED",
        "idempotency_key": "merchant_42:evt_123:publish",
        "actor_principal": "SYSTEM::action_layer",
        "origin": "DF",
        "authz_policy_rev": {"policy_id": "al.authz.v0", "revision": "r5"},
        "run_config_digest": run_config_digest,
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


def _process(processor: DecisionLogAuditIntakeProcessor, *, offset: str, envelope: dict[str, object]):
    return processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset=offset,
            offset_kind="file_line",
            payload=envelope,
        )
    )


def test_phase4_lineage_resolves_in_order_and_stores_provenance_refs(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    decision_id = "a" * 32
    action_id = "5" * 32
    outcome_id = "8" * 32

    _process(
        processor,
        offset="0",
        envelope=_envelope(
            event_id="evt_decision",
            event_type="decision_response",
            payload=_decision_payload(decision_id=decision_id),
            ts_utc="2026-02-07T10:27:00.000000Z",
        ),
    )
    _process(
        processor,
        offset="1",
        envelope=_envelope(
            event_id="evt_intent",
            event_type="action_intent",
            payload=_action_intent_payload(decision_id=decision_id, action_id=action_id),
            ts_utc="2026-02-07T10:27:01.000000Z",
        ),
    )
    _process(
        processor,
        offset="2",
        envelope=_envelope(
            event_id="evt_outcome",
            event_type="action_outcome",
            payload=_action_outcome_payload(decision_id=decision_id, action_id=action_id, outcome_id=outcome_id),
            ts_utc="2026-02-07T10:27:02.000000Z",
        ),
    )

    chain = store.get_lineage_chain(decision_id=decision_id)
    assert chain is not None
    assert chain.chain_status == "RESOLVED"
    assert chain.unresolved_reasons == ()
    assert chain.decision_event_id == "evt_decision"
    assert chain.intent_count == 1
    assert chain.outcome_count == 1
    assert chain.decision_ref is not None
    assert chain.decision_ref["topic"] == "fp.bus.traffic.fraud.v1"
    assert chain.decision_ref["offset"] == "0"

    intents = store.list_lineage_intents(decision_id=decision_id)
    assert len(intents) == 1
    assert intents[0].action_id == action_id
    assert intents[0].source_ref["event_type"] == "action_intent"

    outcomes = store.list_lineage_outcomes(decision_id=decision_id)
    assert len(outcomes) == 1
    assert outcomes[0].outcome_id == outcome_id
    assert outcomes[0].source_ref["event_type"] == "action_outcome"


def test_phase4_lineage_handles_partial_order_with_explicit_unresolved_states(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    decision_id = "b" * 32
    action_id = "6" * 32
    outcome_id = "9" * 32

    _process(
        processor,
        offset="0",
        envelope=_envelope(
            event_id="evt_outcome_first",
            event_type="action_outcome",
            payload=_action_outcome_payload(decision_id=decision_id, action_id=action_id, outcome_id=outcome_id),
            ts_utc="2026-02-07T10:27:02.000000Z",
        ),
    )
    chain = store.get_lineage_chain(decision_id=decision_id)
    assert chain is not None
    assert chain.chain_status == "UNRESOLVED"
    assert set(chain.unresolved_reasons) == {"MISSING_DECISION", "MISSING_INTENT_LINK"}

    _process(
        processor,
        offset="1",
        envelope=_envelope(
            event_id="evt_intent_second",
            event_type="action_intent",
            payload=_action_intent_payload(decision_id=decision_id, action_id=action_id),
            ts_utc="2026-02-07T10:27:01.000000Z",
        ),
    )
    chain = store.get_lineage_chain(decision_id=decision_id)
    assert chain is not None
    assert chain.chain_status == "UNRESOLVED"
    assert set(chain.unresolved_reasons) == {"MISSING_DECISION"}

    _process(
        processor,
        offset="2",
        envelope=_envelope(
            event_id="evt_decision_last",
            event_type="decision_response",
            payload=_decision_payload(decision_id=decision_id),
            ts_utc="2026-02-07T10:27:00.000000Z",
        ),
    )
    chain = store.get_lineage_chain(decision_id=decision_id)
    assert chain is not None
    assert chain.chain_status == "RESOLVED"
    assert chain.unresolved_reasons == ()


def test_phase4_lineage_conflict_is_quarantined_without_silent_correction(tmp_path: Path) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    decision_id = "c" * 32

    first = _process(
        processor,
        offset="0",
        envelope=_envelope(
            event_id="evt_decision_original",
            event_type="decision_response",
            payload=_decision_payload(decision_id=decision_id, amount=100.0),
            ts_utc="2026-02-07T10:27:00.000000Z",
        ),
    )
    second = _process(
        processor,
        offset="1",
        envelope=_envelope(
            event_id="evt_decision_conflict",
            event_type="decision_response",
            payload=_decision_payload(decision_id=decision_id, amount=999.0),
            ts_utc="2026-02-07T10:27:03.000000Z",
        ),
    )

    assert first.accepted is True
    assert second.accepted is False
    assert second.reason_code == DLA_INTAKE_LINEAGE_CONFLICT
    assert second.checkpoint_advanced is True

    chain = store.get_lineage_chain(decision_id=decision_id)
    assert chain is not None
    assert chain.decision_event_id == "evt_decision_original"

    conn = sqlite3.connect(locator)
    row = conn.execute(
        "SELECT reason_code FROM dla_intake_quarantine WHERE source_partition = ? AND source_offset = ?",
        (0, "1"),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == DLA_INTAKE_LINEAGE_CONFLICT


def test_phase4_lineage_run_config_digest_mismatch_is_quarantined(tmp_path: Path) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    decision_id = "e" * 32
    action_id = "f" * 32

    first = _process(
        processor,
        offset="0",
        envelope=_envelope(
            event_id="evt_decision",
            event_type="decision_response",
            payload=_decision_payload(decision_id=decision_id),
            ts_utc="2026-02-07T10:27:00.000000Z",
        ),
    )
    second = _process(
        processor,
        offset="1",
        envelope=_envelope(
            event_id="evt_outcome",
            event_type="action_outcome",
            payload=_action_outcome_payload(
                decision_id=decision_id,
                action_id=action_id,
                outcome_id="7" * 32,
                run_config_digest="7" * 64,
            ),
            ts_utc="2026-02-07T10:27:02.000000Z",
        ),
    )

    assert first.accepted is True
    assert second.accepted is False
    assert second.reason_code == DLA_INTAKE_LINEAGE_CONFLICT
    assert second.detail is not None
    assert "RUN_CONFIG_DIGEST_MISMATCH" in second.detail
    assert second.checkpoint_advanced is True

    conn = sqlite3.connect(locator)
    row = conn.execute(
        "SELECT reason_code, detail FROM dla_intake_quarantine WHERE source_partition = ? AND source_offset = ?",
        (0, "1"),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == DLA_INTAKE_LINEAGE_CONFLICT
    assert row[1] is not None
    assert "RUN_CONFIG_DIGEST_MISMATCH" in str(row[1])


def test_phase4_lineage_write_error_blocks_checkpoint(tmp_path: Path, monkeypatch) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    def _boom(**kwargs):
        raise RuntimeError("lineage db unavailable")

    monkeypatch.setattr(store, "apply_lineage_candidate", _boom)

    result = _process(
        processor,
        offset="0",
        envelope=_envelope(
            event_id="evt_decision",
            event_type="decision_response",
            payload=_decision_payload(decision_id="d" * 32),
            ts_utc="2026-02-07T10:27:00.000000Z",
        ),
    )
    assert result.accepted is False
    assert result.reason_code == DLA_INTAKE_WRITE_FAILED
    assert result.checkpoint_advanced is False
    assert store.get_checkpoint(topic="fp.bus.traffic.fraud.v1", partition=0) is None
