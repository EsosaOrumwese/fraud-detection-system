from pathlib import Path

from fraud_detection.ingestion_gate.governance import GovernanceEmitter
from fraud_detection.ingestion_gate.health import HealthProbe, HealthState
from fraud_detection.ingestion_gate.ops_index import OpsIndex
from fraud_detection.ingestion_gate.partitioning import PartitioningProfiles
from fraud_detection.ingestion_gate.store import LocalObjectStore
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

    assert probe.check().state == HealthState.AMBER
    probe.record_publish_failure()
    assert probe.check().state == HealthState.AMBER
    probe.record_publish_failure()
    assert probe.check().state == HealthState.RED


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
    )

    emitter.emit_quarantine_spike(1)
    emitter.emit_quarantine_spike(2)
    emitter.emit_quarantine_spike(3)

    log = (tmp_path / "bus" / "fp.bus.audit.v1" / "partition=0.jsonl").read_text(encoding="utf-8")
    assert len(log.splitlines()) == 1
