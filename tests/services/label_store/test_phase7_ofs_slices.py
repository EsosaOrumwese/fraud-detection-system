from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from fraud_detection.label_store import (
    LabelStoreSliceBuilder,
    LabelStoreSliceError,
    LabelStoreWriterBoundary,
)


PLATFORM_RUN_ID = "platform_20260209T220000Z"
SCENARIO_RUN_ID = "1" * 32


def _pins(*, platform_run_id: str = PLATFORM_RUN_ID, scenario_run_id: str = SCENARIO_RUN_ID) -> dict[str, object]:
    return {
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 99,
    }


def _subject(*, platform_run_id: str = PLATFORM_RUN_ID, event_id: str) -> dict[str, str]:
    return {
        "platform_run_id": platform_run_id,
        "event_id": event_id,
    }


def _assertion_payload(
    *,
    case_timeline_event_id: str,
    event_id: str,
    label_value: str,
    effective_time: str,
    observed_time: str,
    platform_run_id: str = PLATFORM_RUN_ID,
    scenario_run_id: str = SCENARIO_RUN_ID,
) -> dict[str, object]:
    return {
        "case_timeline_event_id": case_timeline_event_id,
        "label_subject_key": _subject(platform_run_id=platform_run_id, event_id=event_id),
        "pins": _pins(platform_run_id=platform_run_id, scenario_run_id=scenario_run_id),
        "label_type": "fraud_disposition",
        "label_value": label_value,
        "effective_time": effective_time,
        "observed_time": observed_time,
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_011",
        "evidence_refs": [
            {"ref_type": "CASE_EVENT", "ref_id": f"case_evt_{case_timeline_event_id}"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{case_timeline_event_id}"},
        ],
        "label_payload": {"sensitive_note": "must_not_escape_slice_rows"},
    }


def test_phase7_bulk_slice_parity_with_single_label_as_of_and_basis_echo(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase7.sqlite")
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="a" * 32,
            event_id="evt_ofs_001",
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-09T22:00:00.000000Z",
            observed_time="2026-02-09T22:01:00.000000Z",
        )
    )
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="b" * 32,
            event_id="evt_ofs_002",
            label_value="LEGIT_CONFIRMED",
            effective_time="2026-02-09T22:02:00.000000Z",
            observed_time="2026-02-09T22:03:00.000000Z",
        )
    )

    builder = LabelStoreSliceBuilder(writer_boundary=writer)
    slice_payload = builder.build_resolved_as_of_slice(
        target_subjects=[
            _subject(event_id="evt_ofs_001"),
            _subject(event_id="evt_ofs_002"),
        ],
        observed_as_of="2026-02-09T22:05:00.000000Z",
        label_types=["fraud_disposition"],
        scenario_run_id=SCENARIO_RUN_ID,
    )

    assert slice_payload.platform_run_id == PLATFORM_RUN_ID
    assert slice_payload.observed_as_of == "2026-02-09T22:05:00Z"
    assert slice_payload.effective_at == "2026-02-09T22:05:00Z"
    assert len(slice_payload.rows) == 2
    assert len(slice_payload.target_set_fingerprint) == 64
    assert len(slice_payload.basis_digest) == 64
    assert len(slice_payload.slice_digest) == 64

    for row in slice_payload.rows:
        single = writer.label_as_of(
            platform_run_id=row.platform_run_id,
            event_id=row.event_id,
            label_type=row.label_type,
            as_of_observed_time="2026-02-09T22:05:00.000000Z",
        )
        assert row.status == single.status
        assert row.selected_label_value == single.selected_label_value
        assert row.selected_assertion_id == single.selected_assertion_id

    payload_json = json.dumps(slice_payload.as_dict(), sort_keys=True, ensure_ascii=True)
    assert "must_not_escape_slice_rows" not in payload_json


def test_phase7_dataset_gate_signals_surface_coverage_and_conflict(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase7_gate.sqlite")
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="c" * 32,
            event_id="evt_gate_001",
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-09T22:10:00.000000Z",
            observed_time="2026-02-09T22:11:00.000000Z",
        )
    )
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="d" * 32,
            event_id="evt_gate_002",
            label_value="FRAUD_SUSPECTED",
            effective_time="2026-02-09T22:12:00.000000Z",
            observed_time="2026-02-09T22:13:00.000000Z",
        )
    )
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="e" * 32,
            event_id="evt_gate_002",
            label_value="LEGIT_CONFIRMED",
            effective_time="2026-02-09T22:12:00.000000Z",
            observed_time="2026-02-09T22:13:00.000000Z",
        )
    )

    builder = LabelStoreSliceBuilder(writer_boundary=writer)
    slice_payload = builder.build_resolved_as_of_slice(
        target_subjects=[
            _subject(event_id="evt_gate_001"),
            _subject(event_id="evt_gate_002"),
            _subject(event_id="evt_gate_003"),
        ],
        observed_as_of="2026-02-09T22:20:00.000000Z",
        label_types=["fraud_disposition"],
        scenario_run_id=SCENARIO_RUN_ID,
    )
    coverage = slice_payload.coverage_signals[0]
    assert coverage.label_type == "fraud_disposition"
    assert coverage.target_total == 3
    assert coverage.resolved_total == 1
    assert coverage.conflict_total == 1
    assert coverage.not_found_total == 1

    gate = builder.evaluate_dataset_gate(
        slice_payload=slice_payload,
        min_coverage_by_label_type={"fraud_disposition": 0.8},
        max_conflict_ratio=0.0,
    )
    assert gate.ready_for_training is False
    assert any(reason.startswith("COVERAGE_BELOW_MIN:fraud_disposition") for reason in gate.reasons)
    assert any(reason.startswith("CONFLICT_RATIO_ABOVE_MAX:fraud_disposition") for reason in gate.reasons)


def test_phase7_bulk_slice_fails_closed_on_mixed_platform_run_scope(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase7_scope.sqlite")
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="f" * 32,
            event_id="evt_scope_001",
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-09T22:20:00.000000Z",
            observed_time="2026-02-09T22:21:00.000000Z",
        )
    )
    builder = LabelStoreSliceBuilder(writer_boundary=writer)
    with pytest.raises(LabelStoreSliceError, match="must share one platform_run_id"):
        builder.build_resolved_as_of_slice(
            target_subjects=[
                _subject(event_id="evt_scope_001"),
                _subject(platform_run_id="platform_20260209T220500Z", event_id="evt_scope_002"),
            ],
            observed_as_of="2026-02-09T22:25:00.000000Z",
            label_types=["fraud_disposition"],
        )


def test_phase7_slice_digest_and_artifact_are_rebuild_stable(tmp_path: Path) -> None:
    db_path = tmp_path / "label_store_phase7_rebuild.sqlite"
    writer = LabelStoreWriterBoundary(db_path)
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="1" * 32,
            event_id="evt_rebuild_001",
            label_value="FRAUD_SUSPECTED",
            effective_time="2026-02-09T22:30:00.000000Z",
            observed_time="2026-02-09T22:31:00.000000Z",
        )
    )
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="2" * 32,
            event_id="evt_rebuild_002",
            label_value="LEGIT_CONFIRMED",
            effective_time="2026-02-09T22:32:00.000000Z",
            observed_time="2026-02-09T22:33:00.000000Z",
        )
    )

    builder = LabelStoreSliceBuilder(writer_boundary=writer)
    first = builder.build_resolved_as_of_slice(
        target_subjects=[
            _subject(event_id="evt_rebuild_001"),
            _subject(event_id="evt_rebuild_002"),
        ],
        observed_as_of="2026-02-09T22:40:00.000000Z",
        label_types=["fraud_disposition"],
        scenario_run_id=SCENARIO_RUN_ID,
    )
    output_root = tmp_path / "runs" / PLATFORM_RUN_ID
    artifact_a = builder.export_slice_artifact(slice_payload=first, output_root=output_root)
    assert artifact_a.written_new is True

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM ls_label_timeline")
        conn.commit()
    assert writer.rebuild_timeline_from_assertion_ledger() == 2

    second = builder.build_resolved_as_of_slice(
        target_subjects=[
            _subject(event_id="evt_rebuild_001"),
            _subject(event_id="evt_rebuild_002"),
        ],
        observed_as_of="2026-02-09T22:40:00.000000Z",
        label_types=["fraud_disposition"],
        scenario_run_id=SCENARIO_RUN_ID,
    )
    assert second.basis_digest == first.basis_digest
    assert second.slice_digest == first.slice_digest

    artifact_b = builder.export_slice_artifact(slice_payload=second, output_root=output_root)
    assert artifact_b.written_new is False
    assert artifact_b.local_path == artifact_a.local_path
    assert artifact_b.slice_digest == artifact_a.slice_digest

