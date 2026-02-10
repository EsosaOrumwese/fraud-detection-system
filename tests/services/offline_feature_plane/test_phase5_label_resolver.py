from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.label_store import LabelStoreWriterBoundary
from fraud_detection.offline_feature_plane import (
    OfsBuildIntent,
    OfsLabelAsOfResolver,
    OfsLabelResolverConfig,
    OfsPhase5LabelError,
)


PLATFORM_RUN_ID = "platform_20260210T120000Z"
SCENARIO_RUN_ID = "74bd83db1ad3d1fa136e579115d55429"


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": PLATFORM_RUN_ID,
        "scenario_run_id": SCENARIO_RUN_ID,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "baseline.v0",
        "seed": 42,
    }


def _assertion_payload(
    *,
    case_timeline_event_id: str,
    event_id: str,
    label_value: str,
    effective_time: str,
    observed_time: str,
) -> dict[str, object]:
    return {
        "case_timeline_event_id": case_timeline_event_id,
        "label_subject_key": {"platform_run_id": PLATFORM_RUN_ID, "event_id": event_id},
        "pins": _pins(),
        "label_type": "fraud_disposition",
        "label_value": label_value,
        "effective_time": effective_time,
        "observed_time": observed_time,
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_001",
        "evidence_refs": [{"ref_type": "CASE_EVENT", "ref_id": f"case_evt_{case_timeline_event_id}"}],
    }


def _intent_payload(
    *,
    request_id: str,
    label_asof_utc: str = "2026-02-10T11:00:00Z",
    non_training_allowed: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": request_id,
        "intent_kind": "dataset_build",
        "platform_run_id": PLATFORM_RUN_ID,
        "scenario_run_ids": [SCENARIO_RUN_ID],
        "replay_basis": [
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset_kind": "kinesis_sequence",
                "start_offset": "100",
                "end_offset": "105",
            }
        ],
        "label_basis": {
            "label_asof_utc": label_asof_utc,
            "resolution_rule": "observed_time<=label_asof_utc",
            "maturity_days": 0,
        },
        "feature_definition_set": {
            "feature_set_id": "core_features",
            "feature_set_version": "v1",
        },
        "join_scope": {"subject_key": "platform_run_id,event_id"},
        "filters": {
            "label_types": ["fraud_disposition"],
            "label_coverage_policy": {
                "min_coverage_by_label_type": {"fraud_disposition": 1.0},
                "max_conflict_ratio": 0.0,
            },
        },
        "run_facts_ref": "s3://fraud-platform/platform_20260210T120000Z/sr/run_facts_view/run.json",
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
        "non_training_allowed": non_training_allowed,
    }


def _resolver(tmp_path: Path, *, db_path: Path) -> OfsLabelAsOfResolver:
    config = OfsLabelResolverConfig(
        label_store_locator=str(db_path),
        object_store_root=str(tmp_path / "store"),
    )
    return OfsLabelAsOfResolver(config=config)


def test_phase5_resolves_as_of_cutoff_and_emits_immutable_receipt(tmp_path: Path) -> None:
    db_path = tmp_path / "label_store.sqlite"
    writer = LabelStoreWriterBoundary(db_path)
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="a" * 32,
            event_id="evt_001",
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-10T09:00:00Z",
            observed_time="2026-02-10T10:00:00Z",
        )
    )
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="b" * 32,
            event_id="evt_001",
            label_value="LEGIT_CONFIRMED",
            effective_time="2026-02-10T11:30:00Z",
            observed_time="2026-02-10T12:00:00Z",
        )
    )
    resolver = _resolver(tmp_path, db_path=db_path)
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase5.req.001"))
    receipt = resolver.resolve(
        intent=intent,
        target_subjects=[{"platform_run_id": PLATFORM_RUN_ID, "event_id": "evt_001"}],
    )
    assert receipt.status == "READY_FOR_TRAINING"
    assert receipt.row_total == 1
    assert receipt.target_total == 1
    assert receipt.selected_value_counts == {"FRAUD_CONFIRMED": 1}
    assert receipt.gate["ready_for_training"] is True
    first_ref = Path(resolver.emit_immutable(receipt=receipt))
    second_ref = Path(resolver.emit_immutable(receipt=receipt))
    assert first_ref == second_ref
    assert first_ref.exists()


def test_phase5_training_intent_coverage_violation_fails_closed(tmp_path: Path) -> None:
    db_path = tmp_path / "label_store_empty.sqlite"
    LabelStoreWriterBoundary(db_path)
    resolver = _resolver(tmp_path, db_path=db_path)
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase5.req.002"))
    with pytest.raises(OfsPhase5LabelError) as exc:
        resolver.resolve(
            intent=intent,
            target_subjects=[{"platform_run_id": PLATFORM_RUN_ID, "event_id": "evt_missing"}],
        )
    assert exc.value.code == "COVERAGE_POLICY_VIOLATION"


def test_phase5_non_training_allows_coverage_violation(tmp_path: Path) -> None:
    db_path = tmp_path / "label_store_non_training.sqlite"
    LabelStoreWriterBoundary(db_path)
    resolver = _resolver(tmp_path, db_path=db_path)
    intent = OfsBuildIntent.from_payload(
        _intent_payload(request_id="ofs.phase5.req.003", non_training_allowed=True)
    )
    receipt = resolver.resolve(
        intent=intent,
        target_subjects=[{"platform_run_id": PLATFORM_RUN_ID, "event_id": "evt_missing"}],
    )
    assert receipt.status == "NOT_READY_FOR_TRAINING"
    assert receipt.gate["ready_for_training"] is False
    assert any(str(item).startswith("COVERAGE_BELOW_MIN:fraud_disposition") for item in receipt.gate["reasons"])


def test_phase5_receipt_immutability_violation_is_fail_closed(tmp_path: Path) -> None:
    db_path = tmp_path / "label_store_immutability.sqlite"
    writer = LabelStoreWriterBoundary(db_path)
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="c" * 32,
            event_id="evt_002",
            label_value="FRAUD_CONFIRMED",
            effective_time="2026-02-10T09:00:00Z",
            observed_time="2026-02-10T10:00:00Z",
        )
    )
    resolver = _resolver(tmp_path, db_path=db_path)
    intent = OfsBuildIntent.from_payload(_intent_payload(request_id="ofs.phase5.req.004"))
    receipt = resolver.resolve(
        intent=intent,
        target_subjects=[{"platform_run_id": PLATFORM_RUN_ID, "event_id": "evt_002"}],
    )
    ref = Path(resolver.emit_immutable(receipt=receipt))
    payload = json.loads(ref.read_text(encoding="utf-8"))
    payload["status"] = "NOT_READY_FOR_TRAINING"
    ref.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    with pytest.raises(OfsPhase5LabelError) as exc:
        resolver.emit_immutable(receipt=receipt)
    assert exc.value.code == "LABEL_RESOLUTION_IMMUTABILITY_VIOLATION"
