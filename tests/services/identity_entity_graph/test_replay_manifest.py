from __future__ import annotations

import sqlite3

import pytest

from fraud_detection.identity_entity_graph.replay import ReplayManifest
from fraud_detection.identity_entity_graph.replay_manifest_writer import build_manifest_from_basis
from fraud_detection.identity_entity_graph.store import build_store


def test_replay_manifest_loads() -> None:
    payload = {
        "stream_id": "fp.bus.traffic.fraud.v1",
        "pins": {"platform_run_id": "platform_20260205T000000Z"},
        "topics": [
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partitions": [
                    {"partition": 0, "from_offset": 0, "to_offset": 10},
                ],
            }
        ],
    }
    manifest = ReplayManifest.from_payload(payload)
    assert manifest.topics[0].topic == "fp.bus.traffic.fraud.v1"
    assert manifest.replay_id()


def test_replay_manifest_requires_topics() -> None:
    with pytest.raises(ValueError):
        ReplayManifest.from_payload({"pins": {"platform_run_id": "x"}})


def test_record_replay_basis(tmp_path) -> None:
    db_path = tmp_path / "ieg.db"
    store = build_store(str(db_path), stream_id="ieg.v0")
    store.record_replay_basis(
        replay_id="abc123",
        manifest_json="{}",
        basis_json="{}",
        graph_version="gv-1",
    )
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM ieg_replay_basis").fetchone()[0]
        assert count == 1


def test_build_manifest_from_basis_file_offsets() -> None:
    basis = {
        "graph_scope": {"platform_run_id": "platform_20260205T000000Z"},
        "graph_version": "gv-1",
        "run_config_digest": "cfg-1",
        "basis": {
            "stream_id": "ieg.v0::platform_20260205T000000Z",
            "topics": {
                "fp.bus.traffic.fraud.v1": {
                    "partitions": {"0": {"next_offset": "10", "offset_kind": "file_line"}}
                }
            },
        },
    }
    payload = build_manifest_from_basis(basis)
    topic = payload["topics"][0]
    partition = topic["partitions"][0]
    assert partition["from_offset"] == "0"
    assert partition["to_offset"] == "9"
