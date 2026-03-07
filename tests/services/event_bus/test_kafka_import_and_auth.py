from __future__ import annotations

import importlib
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
