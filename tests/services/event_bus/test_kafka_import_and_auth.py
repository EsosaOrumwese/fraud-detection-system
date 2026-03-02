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
