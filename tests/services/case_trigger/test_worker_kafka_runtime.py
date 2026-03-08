from __future__ import annotations

from pathlib import Path

import fraud_detection.case_trigger.worker as worker_module
from fraud_detection.case_trigger.worker import CaseTriggerWorker, CaseTriggerWorkerConfig


class _FakeKafkaReader:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = records

    def list_partitions(self, topic: str) -> list[int]:
        return [0] if topic == "fp.bus.rtdl.v1" else []

    def read(
        self,
        *,
        topic: str,
        partition: int,
        from_offset: int | None,
        limit: int,
        start_position: str = "latest",
    ) -> list[dict[str, object]]:
        assert topic == "fp.bus.rtdl.v1"
        assert partition == 0
        return list(self._records[:limit])


def _config(tmp_path: Path) -> CaseTriggerWorkerConfig:
    return CaseTriggerWorkerConfig(
        profile_path=Path("config/platform/profiles/dev_full.yaml"),
        policy_ref=Path("config/platform/case_trigger/trigger_policy_v0.yaml"),
        event_bus_kind="kafka",
        event_bus_root=str(tmp_path / "bus"),
        event_bus_stream=None,
        event_bus_region="eu-west-2",
        event_bus_endpoint_url=None,
        event_bus_start_position="earliest",
        admitted_topics=("fp.bus.rtdl.v1",),
        poll_max_records=10,
        poll_sleep_seconds=0.01,
        stream_id="case_trigger.v0::platform_20260308T131411Z",
        platform_run_id="platform_20260308T131411Z",
        required_platform_run_id="platform_20260308T131411Z",
        scenario_run_id="132f468e8c894bd2bd46b88c21684322",
        event_class="traffic_fraud",
        ig_ingest_url="http://127.0.0.1:8081",
        ig_api_key="SYSTEM::case_trigger_writer",
        ig_api_key_header="X-IG-Api-Key",
        replay_dsn=str(tmp_path / "case_trigger_replay.sqlite"),
        checkpoint_dsn=str(tmp_path / "case_trigger_checkpoints.sqlite"),
        publish_store_dsn=str(tmp_path / "case_trigger_publish.sqlite"),
        consumer_checkpoint_path=tmp_path / "case_trigger_consumer_checkpoints.sqlite",
        platform_store_root=str(tmp_path / "platform_store"),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=False,
        environment="dev_full",
        config_revision="r1",
        publish_mode="ig",
    )


def test_case_trigger_kafka_reader_preserves_canonical_envelope(monkeypatch, tmp_path: Path) -> None:
    canonical_envelope = {
        "event_id": "a" * 32,
        "event_type": "decision_response",
        "schema_version": "v1",
        "ts_utc": "2026-03-08T13:14:11.000000Z",
        "platform_run_id": "platform_20260308T131411Z",
        "scenario_run_id": "132f468e8c894bd2bd46b88c21684322",
        "scenario_id": "baseline_v1",
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "payload": {
            "decision_id": "d" * 32,
            "decision_kind": "FRAUD_CHECK",
            "bundle_ref": {"bundle_id": "e" * 64},
            "snapshot_hash": "f" * 64,
            "graph_version": {"version_id": "1" * 32, "watermark_ts_utc": "2026-03-08T13:14:10.000000Z"},
            "eb_offset_basis": {"stream": "fp.bus.traffic.fraud.v1", "offset_kind": "kafka_offset", "offsets": [{"partition": 0, "offset": "1"}]},
            "degrade_posture": {
                "mode": "NORMAL",
                "capabilities_mask": {
                    "allow_ieg": True,
                    "allowed_feature_groups": ["core_features"],
                    "allow_model_primary": True,
                    "allow_model_stage2": False,
                    "allow_fallback_heuristics": True,
                    "action_posture": "NORMAL",
                },
                "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1"},
                "posture_seq": 1,
                "decided_at_utc": "2026-03-08T13:14:11.000000Z",
            },
            "pins": {
                "platform_run_id": "platform_20260308T131411Z",
                "scenario_run_id": "132f468e8c894bd2bd46b88c21684322",
                "manifest_fingerprint": "b" * 64,
                "parameter_hash": "c" * 64,
                "scenario_id": "baseline_v1",
                "seed": 7,
            },
            "decided_at_utc": "2026-03-08T13:14:11.000000Z",
            "policy_rev": {"policy_id": "df.policy.v0", "revision": "r1"},
            "run_config_digest": "9" * 64,
            "source_event": {
                "event_id": "src" * 10 + "ab",
                "event_type": "traffic_fraud",
                "ts_utc": "2026-03-08T13:14:10.000000Z",
                "eb_ref": {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset": "1", "offset_kind": "kafka_offset"},
            },
            "decision": {"action_kind": "ALLOW"},
        },
    }
    fake_reader = _FakeKafkaReader(
        [
            {
                "offset": 41,
                "payload": canonical_envelope,
                "published_at_utc": "2026-03-08T13:14:11.100000Z",
            }
        ]
    )
    monkeypatch.setattr(worker_module, "build_kafka_reader", lambda client_id: fake_reader)

    worker = CaseTriggerWorker(_config(tmp_path))
    rows = worker._read_kafka()

    assert len(rows) == 1
    assert rows[0]["payload"]["event_type"] == "decision_response"
    assert rows[0]["payload"]["platform_run_id"] == "platform_20260308T131411Z"
    assert rows[0]["payload"]["payload"]["decision_id"] == "d" * 32
