from __future__ import annotations

import importlib
import json
import sys
import types

import pytest


def test_event_bus_package_import_does_not_require_kafka_dependency(monkeypatch) -> None:
    sys.modules.pop("fraud_detection.event_bus", None)
    sys.modules.pop("fraud_detection.event_bus.kafka", None)

    real_import_module = importlib.import_module

    def _deny_kafka(name: str, package: str | None = None):
        if name == "fraud_detection.event_bus.kafka":
            raise ImportError("simulated missing confluent_kafka dependency")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _deny_kafka)

    module = importlib.import_module("fraud_detection.event_bus")

    assert module.FileEventBusPublisher is not None


def test_kafka_auth_required_only_for_sasl_protocols(monkeypatch) -> None:
    class _NoopProducer:
        def __init__(self, *_args, **_kwargs):
            return

    fake_module = types.SimpleNamespace(
        Producer=_NoopProducer,
        Consumer=object,
        KafkaError=types.SimpleNamespace(_PARTITION_EOF=-191),
        TopicPartition=object,
    )
    monkeypatch.setitem(sys.modules, "confluent_kafka", fake_module)
    sys.modules.pop("fraud_detection.event_bus.kafka", None)

    kafka = importlib.import_module("fraud_detection.event_bus.kafka")

    with pytest.raises(RuntimeError, match="KAFKA_SASL_CREDENTIALS_MISSING"):
        kafka.KafkaEventBusPublisher(
            kafka.KafkaConfig(
                bootstrap_servers="localhost:9092",
                security_protocol="SASL_SSL",
                sasl_username=None,
                sasl_password=None,
            )
        )

    publisher = kafka.KafkaEventBusPublisher(
        kafka.KafkaConfig(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
            sasl_username=None,
            sasl_password=None,
        )
    )
    assert publisher is not None


def test_kafka_oauthbearer_does_not_require_static_sasl_credentials(monkeypatch) -> None:
    class _NoopProducer:
        def __init__(self, *_args, **_kwargs):
            self.args = _args
            self.kwargs = _kwargs

    class _NoopConsumer:
        def __init__(self, *_args, **_kwargs):
            self.kwargs = _kwargs

        def partitions_for_topic(self, _topic):
            return {0}

        def assign(self, _parts):
            return

        def end_offsets(self, _parts):
            return {}

        def beginning_offsets(self, _parts):
            return {}

        def seek(self, *_args, **_kwargs):
            return

        def poll(self, *args, **kwargs):
            return {}

        def close(self):
            return

    class _PyTopicPartition:
        def __init__(self, topic, partition):
            self.topic = topic
            self.partition = partition

        def __hash__(self):
            return hash((self.topic, self.partition))

        def __eq__(self, other):
            return isinstance(other, _PyTopicPartition) and (self.topic, self.partition) == (other.topic, other.partition)

    class _AbstractTokenProvider:
        pass

    fake_confluent = types.SimpleNamespace(
        Producer=_NoopProducer,
        Consumer=_NoopConsumer,
        KafkaError=types.SimpleNamespace(_PARTITION_EOF=-191),
        TopicPartition=_PyTopicPartition,
    )
    fake_kafka = types.SimpleNamespace(
        KafkaProducer=_NoopProducer,
        KafkaConsumer=_NoopConsumer,
        TopicPartition=_PyTopicPartition,
    )
    fake_kafka_oauth = types.SimpleNamespace(AbstractTokenProvider=_AbstractTokenProvider)
    fake_signer = types.SimpleNamespace(
        MSKAuthTokenProvider=types.SimpleNamespace(generate_auth_token=lambda region: (f"token-for-{region}", 0))
    )

    monkeypatch.setitem(sys.modules, "confluent_kafka", fake_confluent)
    monkeypatch.setitem(sys.modules, "kafka", fake_kafka)
    monkeypatch.setitem(sys.modules, "kafka.sasl.oauth", fake_kafka_oauth)
    monkeypatch.setitem(sys.modules, "aws_msk_iam_sasl_signer", fake_signer)
    sys.modules.pop("fraud_detection.event_bus.kafka", None)

    kafka = importlib.import_module("fraud_detection.event_bus.kafka")

    publisher = kafka.KafkaEventBusPublisher(
        kafka.KafkaConfig(
            bootstrap_servers="boot.example:9098",
            security_protocol="SASL_SSL",
            sasl_mechanism="OAUTHBEARER",
            sasl_username=None,
            sasl_password=None,
            aws_region="eu-west-2",
        )
    )
    reader = kafka.KafkaEventBusReader(
        kafka.KafkaReaderConfig(
            bootstrap_servers="boot.example:9098",
            security_protocol="SASL_SSL",
            sasl_mechanism="OAUTHBEARER",
            sasl_username=None,
            sasl_password=None,
            aws_region="eu-west-2",
        )
    )

    assert publisher is not None
    assert reader is not None
    assert callable(publisher._producer.args[0].get("oauth_cb"))


def test_kafka_publisher_uses_extended_delivery_deadline(monkeypatch) -> None:
    class _RecordingProducer:
        def __init__(self, conf):
            self.conf = conf

    fake_module = types.SimpleNamespace(
        Producer=_RecordingProducer,
        Consumer=object,
        KafkaError=types.SimpleNamespace(_PARTITION_EOF=-191),
        TopicPartition=object,
    )
    monkeypatch.setitem(sys.modules, "confluent_kafka", fake_module)
    sys.modules.pop("fraud_detection.event_bus.kafka", None)

    kafka = importlib.import_module("fraud_detection.event_bus.kafka")

    publisher = kafka.KafkaEventBusPublisher(
        kafka.KafkaConfig(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
            request_timeout_ms=2000,
        )
    )

    conf = publisher._producer.conf
    assert conf["request.timeout.ms"] == 3000
    assert conf["delivery.timeout.ms"] == 6000
    assert conf["socket.timeout.ms"] == 6000


def test_kafka_reader_holds_latest_start_boundary_across_empty_standard_polls(monkeypatch) -> None:
    class _Message:
        def __init__(self, offset: int, payload: dict[str, object]):
            self._offset = offset
            self._payload = json.dumps(payload).encode("utf-8")

        def error(self):
            return None

        def timestamp(self):
            return (0, 1_772_000_000_000)

        def offset(self):
            return self._offset

        def value(self):
            return self._payload

    class _TopicPartition:
        def __init__(self, topic, partition, offset=None):
            self.topic = topic
            self.partition = partition
            self.offset = offset

    class _Consumer:
        def __init__(self, _conf):
            self.watermark_calls = 0
            self.assignments: list[tuple[str, int, int | None]] = []
            self.poll_calls = 0

        def get_watermark_offsets(self, _tp, timeout=None):
            self.watermark_calls += 1
            return (0, 100)

        def assign(self, parts):
            self.assignments.append((parts[0].topic, parts[0].partition, parts[0].offset))

        def poll(self, timeout=None):
            self.poll_calls += 1
            if self.poll_calls == 1:
                return None
            return _Message(100, {"ok": True})

        def close(self):
            return

    fake_module = types.SimpleNamespace(
        Producer=object,
        Consumer=_Consumer,
        KafkaError=types.SimpleNamespace(_PARTITION_EOF=-191),
        TopicPartition=_TopicPartition,
    )
    monkeypatch.setitem(sys.modules, "confluent_kafka", fake_module)
    sys.modules.pop("fraud_detection.event_bus.kafka", None)
    kafka = importlib.import_module("fraud_detection.event_bus.kafka")

    reader = kafka.KafkaEventBusReader(
        kafka.KafkaReaderConfig(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
            client_id="test-standard",
        )
    )

    first = reader.read(topic="demo", partition=0, from_offset=None, limit=10, start_position="latest")
    second = reader.read(topic="demo", partition=0, from_offset=None, limit=10, start_position="latest")

    assert first == []
    assert second[0]["offset"] == 100
    assert reader._consumer.watermark_calls == 1
    assert reader._consumer.assignments == [("demo", 0, 100), ("demo", 0, 100)]


def test_kafka_reader_holds_latest_start_boundary_across_empty_oauth_polls(monkeypatch) -> None:
    class _PyTopicPartition:
        def __init__(self, topic, partition):
            self.topic = topic
            self.partition = partition

        def __hash__(self):
            return hash((self.topic, self.partition))

        def __eq__(self, other):
            return isinstance(other, _PyTopicPartition) and (self.topic, self.partition) == (other.topic, other.partition)

    class _Message:
        def __init__(self, offset: int, payload: dict[str, object]):
            self.offset = offset
            self.value = json.dumps(payload).encode("utf-8")
            self.timestamp = 1_772_000_000_000

    class _KafkaConsumer:
        def __init__(self, *args, **kwargs):
            self.end_offset_calls = 0
            self.assign_calls = 0
            self.seek_calls: list[int] = []
            self.poll_calls = 0

        def partitions_for_topic(self, _topic):
            return {0}

        def assign(self, _parts):
            self.assign_calls += 1

        def end_offsets(self, parts):
            self.end_offset_calls += 1
            return {parts[0]: 100}

        def beginning_offsets(self, parts):
            return {parts[0]: 0}

        def seek(self, _tp, offset):
            self.seek_calls.append(offset)

        def poll(self, *args, **kwargs):
            self.poll_calls += 1
            if self.poll_calls == 1:
                return {}
            tp = _PyTopicPartition("demo", 0)
            return {tp: [_Message(100, {"ok": True})]}

        def close(self):
            return

    class _NoopProducer:
        def __init__(self, *_args, **_kwargs):
            return

    class _AbstractTokenProvider:
        pass

    fake_confluent = types.SimpleNamespace(
        Producer=_NoopProducer,
        Consumer=object,
        KafkaError=types.SimpleNamespace(_PARTITION_EOF=-191),
        TopicPartition=_PyTopicPartition,
    )
    fake_kafka = types.SimpleNamespace(
        KafkaProducer=_NoopProducer,
        KafkaConsumer=_KafkaConsumer,
        TopicPartition=_PyTopicPartition,
    )
    fake_kafka_oauth = types.SimpleNamespace(AbstractTokenProvider=_AbstractTokenProvider)
    fake_signer = types.SimpleNamespace(
        MSKAuthTokenProvider=types.SimpleNamespace(generate_auth_token=lambda region: (f"token-for-{region}", 0))
    )

    monkeypatch.setitem(sys.modules, "confluent_kafka", fake_confluent)
    monkeypatch.setitem(sys.modules, "kafka", fake_kafka)
    monkeypatch.setitem(sys.modules, "kafka.sasl.oauth", fake_kafka_oauth)
    monkeypatch.setitem(sys.modules, "aws_msk_iam_sasl_signer", fake_signer)
    sys.modules.pop("fraud_detection.event_bus.kafka", None)
    kafka = importlib.import_module("fraud_detection.event_bus.kafka")

    reader = kafka.KafkaEventBusReader(
        kafka.KafkaReaderConfig(
            bootstrap_servers="boot.example:9098",
            security_protocol="SASL_SSL",
            sasl_mechanism="OAUTHBEARER",
            aws_region="eu-west-2",
            client_id="test-oauth",
        )
    )

    first = reader.read(topic="demo", partition=0, from_offset=None, limit=10, start_position="latest")
    second = reader.read(topic="demo", partition=0, from_offset=None, limit=10, start_position="latest")

    assert first == []
    assert second[0]["offset"] == 100
    assert reader._consumer.end_offset_calls == 1
    assert reader._consumer.seek_calls == [100, 100]
