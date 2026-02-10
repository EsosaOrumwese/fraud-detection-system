from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import fraud_detection.case_mgmt.observability as case_mgmt_observability

from fraud_detection.case_mgmt import (
    AL_SUBMIT_ACCEPTED,
    LS_WRITE_ACCEPTED,
    CaseActionHandshakeCoordinator,
    CaseEvidenceResolutionCorridor,
    CaseLabelHandshakeCoordinator,
    CaseMgmtRunReporter,
    CaseTriggerIntakeLedger,
    ActionSubmitWriteResult,
    EVIDENCE_UNAVAILABLE,
    LabelStoreWriteResult,
    load_action_emission_policy,
    load_evidence_resolution_policy,
    load_label_emission_policy,
)


PLATFORM_RUN_ID = "platform_20260209T200000Z"
SCENARIO_RUN_ID = "1" * 32


@dataclass
class _AcceptedLabelWriter:
    calls: int = 0

    def write_label_assertion(self, assertion_payload: dict[str, object]) -> LabelStoreWriteResult:
        self.calls += 1
        return LabelStoreWriteResult(
            status=LS_WRITE_ACCEPTED,
            reason_code="LS_ACCEPTED",
            assertion_ref="ls://assertion/001",
        )


@dataclass
class _AcceptedActionWriter:
    calls: int = 0

    def write_action_intent(self, intent_payload: dict[str, object]) -> ActionSubmitWriteResult:
        self.calls += 1
        return ActionSubmitWriteResult(
            status=AL_SUBMIT_ACCEPTED,
            reason_code="AL_ACCEPTED",
            intent_ref="al://intent/001",
        )


def _trigger_payload(
    *,
    platform_run_id: str,
    scenario_run_id: str,
    event_id: str,
    source_ref_id: str,
    observed_time: str,
) -> dict[str, object]:
    suffix = source_ref_id.split(":")[-1]
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": source_ref_id,
        "case_subject_key": {
            "platform_run_id": platform_run_id,
            "event_class": "traffic_fraud",
            "event_id": event_id,
        },
        "pins": {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 77,
        },
        "observed_time": observed_time,
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": suffix},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{suffix}"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def test_phase7_export_emits_metrics_governance_and_case_labels_reconciliation(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase7.sqlite")
    ledger = CaseTriggerIntakeLedger(locator)
    intake = ledger.ingest_case_trigger(
        payload=_trigger_payload(
            platform_run_id=PLATFORM_RUN_ID,
            scenario_run_id=SCENARIO_RUN_ID,
            event_id="evt_001",
            source_ref_id="decision:dec_001",
            observed_time="2026-02-09T20:00:00.000000Z",
        ),
        ingested_at_utc="2026-02-09T20:00:00.500000Z",
    )

    label_policy = load_label_emission_policy(Path("config/platform/case_mgmt/label_emission_policy_v0.yaml"))
    label_writer = _AcceptedLabelWriter()
    label_coordinator = CaseLabelHandshakeCoordinator(
        locator=locator,
        intake_ledger=ledger,
        policy=label_policy,
        label_store_writer=label_writer,
    )
    label_coordinator.submit_label_assertion(
        case_id=intake.case_id,
        source_case_event_id=intake.timeline_event_id,
        label_subject_key={
            "platform_run_id": PLATFORM_RUN_ID,
            "event_id": "evt_001",
        },
        pins={
            "platform_run_id": PLATFORM_RUN_ID,
            "scenario_run_id": SCENARIO_RUN_ID,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 77,
        },
        label_type="fraud_disposition",
        label_value="FRAUD_CONFIRMED",
        effective_time="2026-02-09T20:00:01.000000Z",
        observed_time="2026-02-09T20:00:01.000000Z",
        source_type="HUMAN",
        actor_id="HUMAN::investigator_01",
        evidence_refs=[{"ref_type": "DECISION", "ref_id": "dec_001"}],
        requested_at_utc="2026-02-09T20:00:01.000000Z",
    )

    action_policy = load_action_emission_policy(Path("config/platform/case_mgmt/action_emission_policy_v0.yaml"))
    action_writer = _AcceptedActionWriter()
    action_coordinator = CaseActionHandshakeCoordinator(
        locator=locator,
        intake_ledger=ledger,
        policy=action_policy,
        action_intent_writer=action_writer,
    )
    action_result = action_coordinator.submit_manual_action(
        case_id=intake.case_id,
        source_case_event_id=intake.timeline_event_id,
        action_kind="BLOCK_ACCOUNT",
        target_ref={"ref_type": "ACCOUNT", "ref_id": "acct_001"},
        pins={
            "platform_run_id": PLATFORM_RUN_ID,
            "scenario_run_id": SCENARIO_RUN_ID,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 77,
        },
        actor_principal="HUMAN::investigator_01",
        source_type="HUMAN",
        requested_at_utc="2026-02-09T20:00:02.000000Z",
        reason_code="MANUAL_BLOCK_REQUESTED",
        evidence_refs=[{"ref_type": "DECISION", "ref_id": "dec_001"}],
    )
    action_coordinator.attach_action_outcome(
        case_id=intake.case_id,
        action_idempotency_key=action_result.action_idempotency_key,
        action_outcome_id="outcome_001",
        outcome_status="DENIED",
        observed_at_utc="2026-02-09T20:00:03.000000Z",
        actor_id="SYSTEM::action_layer",
        source_type="SYSTEM",
        evidence_refs=[{"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_outcome_001"}],
        outcome_ref="dla://audit/outcome_001",
    )

    evidence_policy = load_evidence_resolution_policy(Path("config/platform/case_mgmt/evidence_resolution_policy_v0.yaml"))
    evidence = CaseEvidenceResolutionCorridor(locator=locator, policy=evidence_policy)
    evidence.request_resolution(
        case_id=intake.case_id,
        case_timeline_event_id=intake.timeline_event_id,
        ref_type="DECISION",
        ref_id="dec_001",
        actor_id="BOT::forbidden",
        source_type="SYSTEM",
        requested_at_utc="2026-02-09T20:00:04.000000Z",
    )
    allowed = evidence.request_resolution(
        case_id=intake.case_id,
        case_timeline_event_id=intake.timeline_event_id,
        ref_type="DECISION",
        ref_id="dec_002",
        actor_id="SYSTEM::case_mgmt",
        source_type="SYSTEM",
        requested_at_utc="2026-02-09T20:00:05.000000Z",
    )
    evidence.record_resolution(
        request_id=allowed.snapshot.request_id,
        status=EVIDENCE_UNAVAILABLE,
        reason_code="NOT_FOUND",
        actor_id="SYSTEM::resolver",
        source_type="SYSTEM",
        observed_at_utc="2026-02-09T20:00:06.000000Z",
    )

    output_root = tmp_path / "runs" / PLATFORM_RUN_ID
    reporter = CaseMgmtRunReporter(
        locator=locator,
        platform_run_id=PLATFORM_RUN_ID,
        scenario_run_id=SCENARIO_RUN_ID,
    )
    payload = reporter.export(output_root=output_root)

    metrics = payload["metrics"]
    assert metrics["case_triggers"] == 1
    assert metrics["cases_created"] == 1
    assert metrics["timeline_events_appended"] >= 1
    assert metrics["label_assertions"] == 1
    assert metrics["labels_accepted"] == 1
    assert metrics["labels_pending"] == 0
    assert metrics["labels_rejected"] == 0

    lanes = {item["kind"] for item in payload["anomalies"]["lanes"]}
    assert "EVIDENCE_FORBIDDEN" in lanes
    assert "EVIDENCE_UNAVAILABLE" in lanes

    governance_path = output_root / "case_mgmt" / "governance" / "events.jsonl"
    assert governance_path.exists()
    events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    label_events = [item for item in events if str(item.get("lifecycle_type") or "").startswith("LABEL_")]
    assert any(item["lifecycle_type"] == "LABEL_SUBMITTED" for item in label_events)
    assert any(item["lifecycle_type"] == "LABEL_ACCEPTED" for item in label_events)
    assert all(item["actor"]["actor_id"] for item in label_events)
    assert all(isinstance(item["details"]["evidence_refs"], list) for item in label_events)

    day_stamp = str(payload["generated_at_utc"]).split("T", 1)[0]
    dated_reconciliation = output_root / "case_labels" / "reconciliation" / f"{day_stamp}.json"
    assert dated_reconciliation.exists()
    latest_reconciliation = output_root / "case_labels" / "reconciliation" / "case_mgmt_reconciliation.json"
    assert latest_reconciliation.exists()
    dated_payload = json.loads(dated_reconciliation.read_text(encoding="utf-8"))
    assert dated_payload["summary"]["labels_accepted"] == 1


def test_phase7_export_is_idempotent_for_lifecycle_governance_events(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase7_idempotent.sqlite")
    ledger = CaseTriggerIntakeLedger(locator)
    intake = ledger.ingest_case_trigger(
        payload=_trigger_payload(
            platform_run_id=PLATFORM_RUN_ID,
            scenario_run_id=SCENARIO_RUN_ID,
            event_id="evt_010",
            source_ref_id="decision:dec_010",
            observed_time="2026-02-09T20:10:00.000000Z",
        ),
        ingested_at_utc="2026-02-09T20:10:00.500000Z",
    )
    label_policy = load_label_emission_policy(Path("config/platform/case_mgmt/label_emission_policy_v0.yaml"))
    label_coordinator = CaseLabelHandshakeCoordinator(
        locator=locator,
        intake_ledger=ledger,
        policy=label_policy,
        label_store_writer=_AcceptedLabelWriter(),
    )
    label_coordinator.submit_label_assertion(
        case_id=intake.case_id,
        source_case_event_id=intake.timeline_event_id,
        label_subject_key={"platform_run_id": PLATFORM_RUN_ID, "event_id": "evt_010"},
        pins={
            "platform_run_id": PLATFORM_RUN_ID,
            "scenario_run_id": SCENARIO_RUN_ID,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 77,
        },
        label_type="fraud_disposition",
        label_value="FRAUD_CONFIRMED",
        effective_time="2026-02-09T20:10:01.000000Z",
        observed_time="2026-02-09T20:10:01.000000Z",
        source_type="HUMAN",
        actor_id="HUMAN::investigator_01",
        evidence_refs=[{"ref_type": "DECISION", "ref_id": "dec_010"}],
        requested_at_utc="2026-02-09T20:10:01.000000Z",
    )

    output_root = tmp_path / "runs" / PLATFORM_RUN_ID
    reporter = CaseMgmtRunReporter(
        locator=locator,
        platform_run_id=PLATFORM_RUN_ID,
        scenario_run_id=SCENARIO_RUN_ID,
    )
    first = reporter.export(output_root=output_root)
    second = reporter.export(output_root=output_root)

    assert first["governance"]["emitted_total"] > 0
    assert second["governance"]["emitted_total"] == 0
    assert second["governance"]["duplicate_skipped_total"] >= first["governance"]["emitted_total"]


def test_phase7_collect_is_run_scoped_by_platform_and_scenario(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase7_scope.sqlite")
    ledger = CaseTriggerIntakeLedger(locator)
    ledger.ingest_case_trigger(
        payload=_trigger_payload(
            platform_run_id=PLATFORM_RUN_ID,
            scenario_run_id=SCENARIO_RUN_ID,
            event_id="evt_100",
            source_ref_id="decision:dec_100",
            observed_time="2026-02-09T20:20:00.000000Z",
        ),
        ingested_at_utc="2026-02-09T20:20:00.500000Z",
    )
    ledger.ingest_case_trigger(
        payload=_trigger_payload(
            platform_run_id=PLATFORM_RUN_ID,
            scenario_run_id="9" * 32,
            event_id="evt_101",
            source_ref_id="decision:dec_101",
            observed_time="2026-02-09T20:20:01.000000Z",
        ),
        ingested_at_utc="2026-02-09T20:20:01.500000Z",
    )

    reporter = CaseMgmtRunReporter(
        locator=locator,
        platform_run_id=PLATFORM_RUN_ID,
        scenario_run_id=SCENARIO_RUN_ID,
    )
    payload = reporter.collect()
    assert payload["metrics"]["cases_created"] == 1
    assert payload["metrics"]["case_triggers"] == 1


def test_phase7_collect_handles_optional_tables_absent(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase7_optional.sqlite")
    ledger = CaseTriggerIntakeLedger(locator)
    ledger.ingest_case_trigger(
        payload=_trigger_payload(
            platform_run_id=PLATFORM_RUN_ID,
            scenario_run_id=SCENARIO_RUN_ID,
            event_id="evt_200",
            source_ref_id="decision:dec_200",
            observed_time="2026-02-09T20:30:00.000000Z",
        ),
        ingested_at_utc="2026-02-09T20:30:00.500000Z",
    )

    reporter = CaseMgmtRunReporter(
        locator=locator,
        platform_run_id=PLATFORM_RUN_ID,
        scenario_run_id=SCENARIO_RUN_ID,
    )
    payload = reporter.collect()
    assert payload["metrics"]["label_assertions"] == 0
    assert payload["metrics"]["labels_pending"] == 0
    assert payload["metrics"]["labels_accepted"] == 0
    assert payload["metrics"]["labels_rejected"] == 0


@dataclass
class _RollbackTrackingConn:
    rollback_calls: int = 0

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_phase7_optional_query_rolls_back_postgres_on_missing_table(monkeypatch: object) -> None:
    conn = _RollbackTrackingConn()

    def _raise_missing_table(*args: object, **kwargs: object) -> list[object]:
        raise RuntimeError('relation "cm_action_intent_mismatches" does not exist')

    monkeypatch.setattr(case_mgmt_observability, "_query_all", _raise_missing_table)
    rows = case_mgmt_observability._query_all_optional(conn, "postgres", "SELECT 1", tuple())

    assert rows == []
    assert conn.rollback_calls == 1
