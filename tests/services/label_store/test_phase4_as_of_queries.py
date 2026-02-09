from __future__ import annotations

from pathlib import Path

from fraud_detection.label_store import (
    LS_AS_OF_CONFLICT,
    LS_AS_OF_NOT_FOUND,
    LS_AS_OF_RESOLVED,
    LabelStoreWriterBoundary,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260209T193000Z",
        "scenario_run_id": "1" * 32,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 42,
    }


def _subject() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T193000Z",
        "event_id": "evt_decision_trigger_009",
    }


def _payload(
    *,
    case_timeline_event_id: str,
    label_type: str,
    label_value: str,
    effective_time: str,
    observed_time: str,
) -> dict[str, object]:
    return {
        "case_timeline_event_id": case_timeline_event_id,
        "label_subject_key": _subject(),
        "pins": _pins(),
        "label_type": label_type,
        "label_value": label_value,
        "effective_time": effective_time,
        "observed_time": observed_time,
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_001",
        "evidence_refs": [
            {"ref_type": "CASE_EVENT", "ref_id": f"case_evt_{case_timeline_event_id}"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{case_timeline_event_id}"},
        ],
    }


def test_phase4_label_as_of_enforces_observed_time_eligibility(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase4.sqlite")
    writer.write_label_assertion(
        _payload(
            case_timeline_event_id="a" * 32,
            label_type="fraud_disposition",
            label_value="FRAUD_SUSPECTED",
            effective_time="2026-02-09T19:31:00.000000Z",
            observed_time="2026-02-09T19:32:00.000000Z",
        )
    )
    writer.write_label_assertion(
        _payload(
            case_timeline_event_id="b" * 32,
            label_type="fraud_disposition",
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-09T19:35:00.000000Z",
            observed_time="2026-02-09T19:40:00.000000Z",
        )
    )

    early = writer.label_as_of(
        platform_run_id=_subject()["platform_run_id"],
        event_id=_subject()["event_id"],
        label_type="fraud_disposition",
        as_of_observed_time="2026-02-09T19:33:00.000000Z",
    )
    late = writer.label_as_of(
        platform_run_id=_subject()["platform_run_id"],
        event_id=_subject()["event_id"],
        label_type="fraud_disposition",
        as_of_observed_time="2026-02-09T19:41:00.000000Z",
    )
    assert early.status == LS_AS_OF_RESOLVED
    assert early.selected_label_value == "FRAUD_SUSPECTED"
    assert late.status == LS_AS_OF_RESOLVED
    assert late.selected_label_value == "FRAUD_CONFIRMED"


def test_phase4_label_as_of_conflict_is_explicit(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase4.sqlite")
    first = writer.write_label_assertion(
        _payload(
            case_timeline_event_id="c" * 32,
            label_type="fraud_disposition",
            label_value="FRAUD_SUSPECTED",
            effective_time="2026-02-09T19:50:00.000000Z",
            observed_time="2026-02-09T19:55:00.000000Z",
        )
    )
    second = writer.write_label_assertion(
        _payload(
            case_timeline_event_id="d" * 32,
            label_type="fraud_disposition",
            label_value="LEGIT_CONFIRMED",
            effective_time="2026-02-09T19:50:00.000000Z",
            observed_time="2026-02-09T19:55:00.000000Z",
        )
    )
    assert first.label_assertion_id != second.label_assertion_id

    resolution = writer.label_as_of(
        platform_run_id=_subject()["platform_run_id"],
        event_id=_subject()["event_id"],
        label_type="fraud_disposition",
        as_of_observed_time="2026-02-09T19:56:00.000000Z",
    )
    assert resolution.status == LS_AS_OF_CONFLICT
    assert resolution.selected_assertion_id is None
    assert resolution.selected_label_value is None
    assert len(resolution.candidate_assertion_ids) == 2
    assert set(resolution.candidate_label_values) == {"FRAUD_SUSPECTED", "LEGIT_CONFIRMED"}


def test_phase4_resolved_labels_as_of_returns_stable_per_label_type_contract(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase4.sqlite")
    writer.write_label_assertion(
        _payload(
            case_timeline_event_id="e" * 32,
            label_type="fraud_disposition",
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-09T19:11:00.000000Z",
            observed_time="2026-02-09T19:12:00.000000Z",
        )
    )
    writer.write_label_assertion(
        _payload(
            case_timeline_event_id="f" * 32,
            label_type="chargeback_status",
            label_value="PENDING",
            effective_time="2026-02-09T19:13:00.000000Z",
            observed_time="2026-02-09T19:14:00.000000Z",
        )
    )
    rows = writer.resolved_labels_as_of(
        platform_run_id=_subject()["platform_run_id"],
        event_id=_subject()["event_id"],
        as_of_observed_time="2026-02-09T19:15:00.000000Z",
    )
    assert [row.label_type for row in rows] == ["chargeback_status", "fraud_disposition"]
    assert all(row.status == LS_AS_OF_RESOLVED for row in rows)
    assert rows[0].as_of_observed_time == "2026-02-09T19:15:00.000000Z"


def test_phase4_label_as_of_returns_not_found_when_no_eligible_assertion(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase4.sqlite")
    writer.write_label_assertion(
        _payload(
            case_timeline_event_id="1" * 32,
            label_type="fraud_disposition",
            label_value="FRAUD_SUSPECTED",
            effective_time="2026-02-09T19:11:00.000000Z",
            observed_time="2026-02-09T19:12:00.000000Z",
        )
    )
    result = writer.label_as_of(
        platform_run_id=_subject()["platform_run_id"],
        event_id=_subject()["event_id"],
        label_type="fraud_disposition",
        as_of_observed_time="2026-02-09T19:11:30.000000Z",
    )
    assert result.status == LS_AS_OF_NOT_FOUND
    assert result.selected_assertion_id is None
