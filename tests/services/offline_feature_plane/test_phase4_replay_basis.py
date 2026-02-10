from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.offline_feature_plane import (
    OfsBuildIntent,
    OfsPhase4ReplayError,
    OfsReplayBasisResolver,
    OfsReplayBasisResolverConfig,
    ReplayBasisEvidence,
)


def _intent_payload(
    *,
    run_facts_ref: str = "s3://fraud-platform/platform_20260210T120000Z/sr/run_facts_view/run.json",
    non_training_allowed: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": "ofs.phase4.req.001",
        "intent_kind": "dataset_build",
        "platform_run_id": "platform_20260210T120000Z",
        "scenario_run_ids": ["74bd83db1ad3d1fa136e579115d55429"],
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
            "label_asof_utc": "2026-02-10T10:00:00Z",
            "resolution_rule": "observed_time<=label_asof_utc",
            "maturity_days": 30,
        },
        "feature_definition_set": {
            "feature_set_id": "core_features",
            "feature_set_version": "v1",
        },
        "join_scope": {"subject_key": "platform_run_id,event_id"},
        "filters": {"country": ["US"]},
        "run_facts_ref": run_facts_ref,
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
        "non_training_allowed": non_training_allowed,
    }


def _intent(*, non_training_allowed: bool = False) -> OfsBuildIntent:
    return OfsBuildIntent.from_payload(_intent_payload(non_training_allowed=non_training_allowed))


def _evidence_payload(*, mismatch: bool = False, gap: bool = False) -> dict[str, object]:
    observations: list[dict[str, object]] = [
        {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kinesis_sequence", "offset": "100", "payload_hash": "a" * 64, "source": "EB"},
        {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kinesis_sequence", "offset": "101", "payload_hash": "b" * 64, "source": "EB"},
        {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kinesis_sequence", "offset": "102", "payload_hash": "c" * 64, "source": "EB"},
    ]
    if not gap:
        observations.extend(
            [
                {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kinesis_sequence", "offset": "103", "payload_hash": "d" * 64, "source": "ARCHIVE", "archive_ref": "s3://fraud-platform/path/103.json"},
                {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kinesis_sequence", "offset": "104", "payload_hash": "e" * 64, "source": "ARCHIVE", "archive_ref": "s3://fraud-platform/path/104.json"},
                {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kinesis_sequence", "offset": "105", "payload_hash": "f" * 64, "source": "ARCHIVE", "archive_ref": "s3://fraud-platform/path/105.json"},
            ]
        )
    else:
        observations.extend(
            [
                {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kinesis_sequence", "offset": "104", "payload_hash": "e" * 64, "source": "ARCHIVE", "archive_ref": "s3://fraud-platform/path/104.json"},
                {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kinesis_sequence", "offset": "105", "payload_hash": "f" * 64, "source": "ARCHIVE", "archive_ref": "s3://fraud-platform/path/105.json"},
            ]
        )
    if mismatch:
        observations.append(
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset_kind": "kinesis_sequence",
                "offset": "103",
                "payload_hash": "9" * 64,
                "source": "EB",
            }
        )
    return {"observations": observations}


def _resolver(tmp_path: Path, *, require_complete: bool = True, discover_archive_events: bool = False) -> OfsReplayBasisResolver:
    config = OfsReplayBasisResolverConfig(
        object_store_root=str(tmp_path / "store"),
        require_complete_for_dataset_build=require_complete,
        discover_archive_events=discover_archive_events,
    )
    return OfsReplayBasisResolver(config=config)


def test_phase4_resolves_canonical_cutover_and_emits_receipt(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path)
    intent = _intent()
    evidence = ReplayBasisEvidence.from_payload(_evidence_payload())
    receipt = resolver.resolve(intent=intent, evidence=evidence)
    assert receipt.status == "COMPLETE"
    assert receipt.totals["required_offsets"] == 6
    assert receipt.totals["covered_offsets"] == 6
    assert len(receipt.replay_resolved_tuples) == 2
    assert receipt.replay_resolved_tuples[0].source == "EB"
    assert receipt.replay_resolved_tuples[1].source == "ARCHIVE"
    assert receipt.cutovers[0].cutover_mode == "EB_THEN_ARCHIVE"
    assert receipt.cutovers[0].archive_authoritative_from_offset == "103"
    resolver.require_complete_for_publication(receipt=receipt)

    first_ref = resolver.emit_immutable(receipt=receipt)
    second_ref = resolver.emit_immutable(receipt=receipt)
    assert first_ref == second_ref
    assert Path(first_ref).exists()


def test_phase4_training_intent_mismatch_fails_closed(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path)
    intent = _intent()
    evidence = ReplayBasisEvidence.from_payload(_evidence_payload(mismatch=True))
    with pytest.raises(OfsPhase4ReplayError) as exc:
        resolver.resolve(intent=intent, evidence=evidence)
    assert exc.value.code == "REPLAY_BASIS_MISMATCH"


def test_phase4_non_training_mismatch_is_recorded_and_blocked_at_publication(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path, require_complete=False)
    intent = _intent(non_training_allowed=True)
    evidence = ReplayBasisEvidence.from_payload(_evidence_payload(mismatch=True))
    receipt = resolver.resolve(intent=intent, evidence=evidence)
    assert receipt.status == "INCOMPLETE"
    codes = {item.code for item in receipt.anomalies}
    assert "REPLAY_BASIS_MISMATCH" in codes
    with pytest.raises(OfsPhase4ReplayError) as exc:
        resolver.require_complete_for_publication(receipt=receipt)
    assert exc.value.code == "REPLAY_INCOMPLETE"


def test_phase4_gap_in_coverage_emits_incomplete_receipt(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path, require_complete=False)
    intent = _intent()
    evidence = ReplayBasisEvidence.from_payload(_evidence_payload(gap=True))
    receipt = resolver.resolve(intent=intent, evidence=evidence)
    assert receipt.status == "INCOMPLETE"
    assert receipt.totals["missing_offsets"] == 1
    codes = {item.code for item in receipt.anomalies}
    assert "REPLAY_BASIS_GAP" in codes


def test_phase4_discovers_archive_events_from_store_when_refs_not_provided(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    base = (
        store_root
        / "platform_20260210T120000Z"
        / "archive"
        / "events"
        / "topic=fp.bus.traffic.fraud.v1"
        / "partition=0"
        / "offset_kind=kinesis_sequence"
    )
    for offset, payload_hash in [("100", "1" * 64), ("101", "2" * 64), ("102", "3" * 64), ("103", "4" * 64), ("104", "5" * 64), ("105", "6" * 64)]:
        payload = {
            "archived_at_utc": "2026-02-10T12:00:00Z",
            "platform_run_id": "platform_20260210T120000Z",
            "scenario_run_id": "74bd83db1ad3d1fa136e579115d55429",
            "manifest_fingerprint": "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8",
            "parameter_hash": "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7",
            "scenario_id": "baseline_v1",
            "event_id": f"evt-{offset}",
            "event_type": "ARRIVAL_EVENT",
            "ts_utc": "2026-02-10T12:00:00Z",
            "payload_hash": payload_hash,
            "origin_offset": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": offset,
                "offset_kind": "kinesis_sequence",
            },
            "envelope": {"event_id": f"evt-{offset}"},
        }
        path = base / f"offset={offset}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    resolver = _resolver(tmp_path, discover_archive_events=True)
    intent = _intent(non_training_allowed=True)
    receipt = resolver.resolve(intent=intent)
    assert receipt.status == "COMPLETE"
    assert receipt.cutovers[0].cutover_mode == "ARCHIVE_ONLY"
    assert receipt.totals["required_offsets"] == 6
    assert receipt.totals["covered_offsets"] == 6


def test_phase4_receipt_immutability_violation_is_fail_closed(tmp_path: Path) -> None:
    resolver = _resolver(tmp_path)
    intent = _intent()
    evidence = ReplayBasisEvidence.from_payload(_evidence_payload())
    receipt = resolver.resolve(intent=intent, evidence=evidence)
    ref = Path(resolver.emit_immutable(receipt=receipt))
    payload = json.loads(ref.read_text(encoding="utf-8"))
    payload["status"] = "INCOMPLETE"
    ref.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    with pytest.raises(OfsPhase4ReplayError) as exc:
        resolver.emit_immutable(receipt=receipt)
    assert exc.value.code == "COMPLETENESS_RECEIPT_IMMUTABILITY_VIOLATION"
