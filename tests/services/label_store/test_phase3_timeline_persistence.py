from __future__ import annotations

import sqlite3
from pathlib import Path

from fraud_detection.label_store import (
    LS_WRITE_ACCEPTED,
    LabelStoreWriterBoundary,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260209T190000Z",
        "scenario_run_id": "1" * 32,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 42,
    }


def _subject() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T190000Z",
        "event_id": "evt_decision_trigger_001",
    }


def _payload(
    *,
    case_timeline_event_id: str,
    label_value: str,
    effective_time: str,
    observed_time: str,
) -> dict[str, object]:
    return {
        "case_timeline_event_id": case_timeline_event_id,
        "label_subject_key": _subject(),
        "pins": _pins(),
        "label_type": "fraud_disposition",
        "label_value": label_value,
        "effective_time": effective_time,
        "observed_time": observed_time,
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_001",
        "evidence_refs": [
            {"ref_type": "CASE_EVENT", "ref_id": f"case_evt_{case_timeline_event_id}"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{case_timeline_event_id}"},
        ],
        "label_payload": {"notes": "phase3 timeline test"},
    }


def test_phase3_append_only_corrections_create_new_timeline_rows(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase3.sqlite")
    first = writer.write_label_assertion(
        _payload(
            case_timeline_event_id="a" * 32,
            label_value="FRAUD_SUSPECTED",
            effective_time="2026-02-09T19:00:00.000000Z",
            observed_time="2026-02-09T19:02:00.000000Z",
        )
    )
    second = writer.write_label_assertion(
        _payload(
            case_timeline_event_id="b" * 32,
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-09T19:03:00.000000Z",
            observed_time="2026-02-09T19:04:00.000000Z",
        )
    )
    assert first.status == LS_WRITE_ACCEPTED
    assert second.status == LS_WRITE_ACCEPTED

    timeline = writer.list_timeline(platform_run_id=_subject()["platform_run_id"], event_id=_subject()["event_id"])
    assert len(timeline) == 2
    ids = {row.label_assertion_id for row in timeline}
    assert first.label_assertion_id in ids
    assert second.label_assertion_id in ids


def test_phase3_timeline_order_is_deterministic_by_observed_effective_id(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase3.sqlite")
    late = writer.write_label_assertion(
        _payload(
            case_timeline_event_id="c" * 32,
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-09T19:40:00.000000Z",
            observed_time="2026-02-09T19:45:00.000000Z",
        )
    )
    same_obs_later_effective = writer.write_label_assertion(
        _payload(
            case_timeline_event_id="d" * 32,
            label_value="FRAUD_SUSPECTED",
            effective_time="2026-02-09T19:20:00.000000Z",
            observed_time="2026-02-09T19:30:00.000000Z",
        )
    )
    same_obs_earlier_effective = writer.write_label_assertion(
        _payload(
            case_timeline_event_id="e" * 32,
            label_value="LEGIT_CONFIRMED",
            effective_time="2026-02-09T19:10:00.000000Z",
            observed_time="2026-02-09T19:30:00.000000Z",
        )
    )
    timeline = writer.list_timeline(platform_run_id=_subject()["platform_run_id"], event_id=_subject()["event_id"])
    ids_by_order = [row.label_assertion_id for row in timeline]
    assert ids_by_order == [
        same_obs_earlier_effective.label_assertion_id,
        same_obs_later_effective.label_assertion_id,
        late.label_assertion_id,
    ]


def test_phase3_duplicate_replay_does_not_append_timeline_and_refs_are_persisted(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase3.sqlite")
    payload = _payload(
        case_timeline_event_id="f" * 32,
        label_value="FRAUD_CONFIRMED",
        effective_time="2026-02-09T19:10:00.000000Z",
        observed_time="2026-02-09T19:11:00.000000Z",
    )
    first = writer.write_label_assertion(payload)
    second = writer.write_label_assertion(payload)
    assert first.status == LS_WRITE_ACCEPTED
    assert second.status == LS_WRITE_ACCEPTED

    timeline = writer.list_timeline(
        platform_run_id=payload["label_subject_key"]["platform_run_id"],  # type: ignore[index]
        event_id=payload["label_subject_key"]["event_id"],  # type: ignore[index]
    )
    assert len(timeline) == 1
    refs = list(timeline[0].evidence_refs)
    assert refs
    assert all("ref_type" in item and "ref_id" in item for item in refs)


def test_phase3_rebuild_timeline_from_assertion_ledger_is_restore_safe(tmp_path: Path) -> None:
    db_path = tmp_path / "label_store_phase3.sqlite"
    writer = LabelStoreWriterBoundary(db_path)
    writer.write_label_assertion(
        _payload(
            case_timeline_event_id="1" * 32,
            label_value="FRAUD_SUSPECTED",
            effective_time="2026-02-09T19:00:00.000000Z",
            observed_time="2026-02-09T19:01:00.000000Z",
        )
    )
    writer.write_label_assertion(
        _payload(
            case_timeline_event_id="2" * 32,
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-09T19:02:00.000000Z",
            observed_time="2026-02-09T19:03:00.000000Z",
        )
    )
    baseline = writer.list_timeline(platform_run_id=_subject()["platform_run_id"], event_id=_subject()["event_id"])
    assert len(baseline) == 2

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM ls_label_timeline")
        conn.commit()

    wiped = writer.list_timeline(platform_run_id=_subject()["platform_run_id"], event_id=_subject()["event_id"])
    assert len(wiped) == 0

    rebuilt = writer.rebuild_timeline_from_assertion_ledger()
    assert rebuilt == 2
    after = writer.list_timeline(platform_run_id=_subject()["platform_run_id"], event_id=_subject()["event_id"])
    assert len(after) == 2
    assert {item.label_assertion_id for item in after} == {item.label_assertion_id for item in baseline}

    rebuilt_again = writer.rebuild_timeline_from_assertion_ledger()
    assert rebuilt_again == 0
