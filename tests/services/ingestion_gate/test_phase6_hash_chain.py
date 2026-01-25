from fraud_detection.ingestion_gate.pull_state import PullRunStore, _hash_event
from fraud_detection.ingestion_gate.store import LocalObjectStore


def test_pull_run_hash_chain(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    pull_store = PullRunStore(store)
    run_id = "a" * 32
    pull_store.append_event(run_id, {"event_kind": "PULL_STARTED", "ts_utc": "2026-01-01T00:00:00Z", "run_id": run_id})
    pull_store.append_event(run_id, {"event_kind": "OUTPUT_COMPLETED", "ts_utc": "2026-01-01T00:01:00Z", "run_id": run_id})

    events = pull_store.iter_events(run_id)
    assert len(events) == 2
    prev_hash = "0" * 64
    for event in events:
        assert event["prev_hash"] == prev_hash
        assert event["event_hash"] == _hash_event(prev_hash, event)
        prev_hash = event["event_hash"]
