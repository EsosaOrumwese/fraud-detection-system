from fraud_detection.ingestion_gate.pull_state import PullRunStore
from fraud_detection.ingestion_gate.store import LocalObjectStore


def test_shard_checkpoint_paths(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    pull_store = PullRunStore(store)
    run_id = "b" * 32
    payload = {"run_id": run_id, "output_id": "out-1", "shard_id": 0, "shard_total": 2}
    payload2 = {"run_id": run_id, "output_id": "out-1", "shard_id": 1, "shard_total": 2}

    assert pull_store.write_checkpoint(run_id, "out-1", payload, shard_id=0)
    assert pull_store.write_checkpoint(run_id, "out-1", payload2, shard_id=1)
    checkpoints = pull_store.list_checkpoints(run_id)
    assert len(checkpoints) == 2
