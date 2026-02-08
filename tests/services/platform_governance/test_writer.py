from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.platform_governance import GovernanceEvent, PlatformGovernanceError, PlatformGovernanceWriter
from fraud_detection.scenario_runner.storage import LocalObjectStore


def test_writer_is_append_only_and_idempotent(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "store")
    writer = PlatformGovernanceWriter(store)

    event = GovernanceEvent(
        event_family="RUN_STARTED",
        actor_id="svc:test",
        source_type="service",
        source_component="unit_test",
        platform_run_id="platform_20260208T200000Z",
        scenario_run_id="scenario_1",
        details={"message_id": "m1"},
        dedupe_key="start:m1",
    )
    first = writer.emit(event)
    second = writer.emit(event)

    assert first is not None
    assert second is None

    events_path = tmp_path / "store" / "fraud-platform" / "platform_20260208T200000Z" / "obs" / "governance" / "events.jsonl"
    lines = events_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event_family"] == "RUN_STARTED"
    assert payload["actor"]["actor_id"] == "svc:test"
    assert payload["pins"]["platform_run_id"] == "platform_20260208T200000Z"


def test_writer_query_filters_and_limits(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "store")
    writer = PlatformGovernanceWriter(store)
    run_id = "platform_20260208T200100Z"

    writer.emit(
        GovernanceEvent(
            event_family="RUN_READY_SEEN",
            actor_id="svc:test",
            source_type="service",
            source_component="unit_test",
            platform_run_id=run_id,
            details={"k": "1"},
            dedupe_key="a",
        )
    )
    writer.emit(
        GovernanceEvent(
            event_family="RUN_ENDED",
            actor_id="svc:test",
            source_type="service",
            source_component="unit_test",
            platform_run_id=run_id,
            details={"k": "2"},
            dedupe_key="b",
        )
    )
    all_rows = writer.query(platform_run_id=run_id)
    ended_rows = writer.query(platform_run_id=run_id, event_family="RUN_ENDED", limit=1)

    assert len(all_rows) == 2
    assert len(ended_rows) == 1
    assert ended_rows[0]["event_family"] == "RUN_ENDED"


def test_writer_fails_closed_on_missing_mandatory_fields(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "store")
    writer = PlatformGovernanceWriter(store)

    with pytest.raises(PlatformGovernanceError):
        writer.emit(
            GovernanceEvent(
                event_family="RUN_STARTED",
                actor_id="",
                source_type="service",
                source_component="unit_test",
                platform_run_id="platform_20260208T200200Z",
                details={},
            )
        )
