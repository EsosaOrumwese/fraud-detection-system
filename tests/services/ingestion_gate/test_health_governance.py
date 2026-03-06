from pathlib import Path
import time
import pytest

from fraud_detection.ingestion_gate.governance import GovernanceEmitter
from fraud_detection.ingestion_gate.health import HealthProbe, HealthState
from fraud_detection.ingestion_gate.ops_index import OpsIndex
from fraud_detection.ingestion_gate.partitioning import PartitioningProfiles
from fraud_detection.ingestion_gate.store import LocalObjectStore, observe_object_store
from fraud_detection.event_bus import FileEventBusPublisher


def _write_partitioning(path: Path) -> None:
    payload = {
        "version": "0.1.0",
        "profiles": {
            "ig.partitioning.v0.audit": {
                "stream": "fp.bus.audit.v1",
                "key_precedence": ["event_id"],
                "hash_algo": "sha256",
            }
        },
    }
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_health_probe_bus_failure_threshold(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    ops = OpsIndex(tmp_path / "ops.db")
    dummy_bus = object()
    probe = HealthProbe(store, dummy_bus, ops, probe_interval_seconds=0, max_publish_failures=2)

    assert probe.check().state == HealthState.GREEN
    probe.record_publish_failure()
    assert probe.check().state == HealthState.GREEN
    probe.record_publish_failure()
    probe._last_checked_at = 0.0
    assert probe.check().state == HealthState.GREEN
    for _ in range(20):
        if probe.check().state == HealthState.RED:
            break
        time.sleep(0.05)
    assert probe.check().state == HealthState.RED


def test_health_probe_returns_cached_result_while_refreshing_in_background(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = LocalObjectStore(tmp_path / "store")
    bus = FileEventBusPublisher(tmp_path / "bus")
    ops = OpsIndex(tmp_path / "ops.db")
    probe = HealthProbe(store, bus, ops, probe_interval_seconds=0, max_publish_failures=2)

    first = probe.check()
    assert first.state == HealthState.GREEN

    def _slow_store_ok() -> bool:
        time.sleep(0.25)
        return True

    monkeypatch.setattr(probe, "_store_ok", _slow_store_ok)
    probe._last_checked_at = 0.0

    started = time.perf_counter()
    cached = probe.check()
    elapsed = time.perf_counter() - started

    assert cached.state == HealthState.GREEN
    assert elapsed < 0.1

    for _ in range(20):
        refreshed_at = probe._last_checked_at
        if refreshed_at and refreshed_at > 0.0:
            break
        time.sleep(0.05)

    assert probe._last_checked_at is not None
    assert probe._last_checked_at > 0.0


def test_health_probe_uses_observed_store_failures(tmp_path: Path) -> None:
    class FlakyStore:
        def __init__(self) -> None:
            self.fail = False

        def write_json(self, relative_path: str, payload: dict) -> object:
            if self.fail:
                raise RuntimeError("store_down")
            return object()

        def write_json_if_absent(self, relative_path: str, payload: dict) -> object:
            if self.fail:
                raise RuntimeError("store_down")
            return object()

        def read_json(self, relative_path: str) -> dict:
            if self.fail:
                raise RuntimeError("store_down")
            return {}

        def write_text(self, relative_path: str, content: str) -> object:
            if self.fail:
                raise RuntimeError("store_down")
            return object()

        def append_jsonl(self, relative_path: str, records: list[dict]) -> object:
            if self.fail:
                raise RuntimeError("store_down")
            return object()

        def exists(self, relative_path: str) -> bool:
            if self.fail:
                raise RuntimeError("store_down")
            return False

    flaky = FlakyStore()
    store = observe_object_store(flaky)
    bus = FileEventBusPublisher(tmp_path / "bus")
    ops = OpsIndex(tmp_path / "ops.db")
    probe = HealthProbe(store, bus, ops, probe_interval_seconds=0, max_publish_failures=2)

    store.write_json("ok.json", {"ok": True})
    assert probe.check().state == HealthState.GREEN

    flaky.fail = True
    try:
        store.write_json("fail.json", {"ok": False})
    except RuntimeError:
        pass

    probe._last_checked_at = 0.0
    result = probe.check()
    assert result.state == HealthState.GREEN
    for _ in range(20):
        result = probe.check()
        if result.state == HealthState.RED:
            break
        time.sleep(0.05)
    assert result.state == HealthState.RED
    assert "OBJECT_STORE_UNHEALTHY" in result.reasons


def test_observed_store_write_if_absent_conflict_is_not_unhealthy(tmp_path: Path) -> None:
    store = observe_object_store(LocalObjectStore(tmp_path / "store"))
    bus = FileEventBusPublisher(tmp_path / "bus")
    ops = OpsIndex(tmp_path / "ops.db")
    probe = HealthProbe(store, bus, ops, probe_interval_seconds=0, max_publish_failures=2)

    store.write_json_if_absent("markers/seen.json", {"ok": True})
    with pytest.raises(FileExistsError):
        store.write_json_if_absent("markers/seen.json", {"ok": True})

    snapshot = store.health_snapshot()
    assert snapshot.consecutive_failures == 0
    assert snapshot.last_benign_conflict_operation == "write_json_if_absent"
    assert probe.check().state == HealthState.GREEN


def test_governance_quarantine_spike_emits_once(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    bus = FileEventBusPublisher(tmp_path / "bus")
    profiles_path = tmp_path / "partitioning.yaml"
    _write_partitioning(profiles_path)
    partitioning = PartitioningProfiles(str(profiles_path))
    emitter = GovernanceEmitter(
        store=store,
        bus=bus,
        partitioning=partitioning,
        quarantine_spike_threshold=2,
        quarantine_spike_window_seconds=60,
        policy_id="ig_policy",
        prefix="runs/fraud-platform",
    )

    emitter.emit_quarantine_spike(1)
    emitter.emit_quarantine_spike(2)
    emitter.emit_quarantine_spike(3)

    log = (tmp_path / "bus" / "fp.bus.audit.v1" / "partition=0.jsonl").read_text(encoding="utf-8")
    assert len(log.splitlines()) == 1


def test_policy_activation_defaults_to_store_only(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "store")
    bus = FileEventBusPublisher(tmp_path / "bus")
    profiles_path = tmp_path / "partitioning.yaml"
    _write_partitioning(profiles_path)
    partitioning = PartitioningProfiles(str(profiles_path))
    emitter = GovernanceEmitter(
        store=store,
        bus=bus,
        partitioning=partitioning,
        quarantine_spike_threshold=2,
        quarantine_spike_window_seconds=60,
        policy_id="ig_policy",
        prefix="platform_20260306T160000Z",
    )

    emitter.emit_policy_activation(
        {
            "policy_id": "ig_policy",
            "revision": "dev-full-v0",
            "content_digest": "a" * 64,
        }
    )

    active_path = tmp_path / "store" / "platform_20260306T160000Z" / "ig" / "policy" / "active.json"
    governance_events = (
        tmp_path / "store" / "fraud-platform" / "platform_20260306T160000Z" / "obs" / "governance" / "events.jsonl"
    )
    assert active_path.exists()
    assert governance_events.exists()
    assert not (tmp_path / "bus" / "fp.bus.audit.v1").exists()
