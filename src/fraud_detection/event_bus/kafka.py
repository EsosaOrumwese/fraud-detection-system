"""Kafka publish-only Event Bus adapter (Confluent Cloud compatible)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any

from kafka import KafkaProducer

from .publisher import EbRef

logger = logging.getLogger("fraud_detection.event_bus")


@dataclass(frozen=True)
class KafkaConfig:
    bootstrap_servers: str
    security_protocol: str = "SASL_SSL"
    sasl_mechanism: str = "PLAIN"
    sasl_username: str | None = None
    sasl_password: str | None = None
    client_id: str = "fraud-platform"
    request_timeout_ms: int = 15000
    retries: int = 3


def _strip_scheme(value: str) -> str:
    # Some stacks store bootstrap as "SASL_SSL://host:9092". kafka-python expects "host:9092".
    v = value.strip()
    for prefix in ("SASL_SSL://", "PLAINTEXT://", "SSL://"):
        if v.upper().startswith(prefix):
            return v[len(prefix) :]
    return v


class KafkaEventBusPublisher:
    def __init__(self, config: KafkaConfig) -> None:
        if not config.bootstrap_servers.strip():
            raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS_MISSING")
        bootstrap = _strip_scheme(config.bootstrap_servers)
        self.config = KafkaConfig(
            bootstrap_servers=bootstrap,
            security_protocol=config.security_protocol,
            sasl_mechanism=config.sasl_mechanism,
            sasl_username=config.sasl_username,
            sasl_password=config.sasl_password,
            client_id=config.client_id,
            request_timeout_ms=config.request_timeout_ms,
            retries=config.retries,
        )
        if not (self.config.sasl_username and self.config.sasl_password):
            raise RuntimeError("KAFKA_SASL_CREDENTIALS_MISSING")
        self._producer = KafkaProducer(
            bootstrap_servers=self.config.bootstrap_servers,
            security_protocol=self.config.security_protocol,
            sasl_mechanism=self.config.sasl_mechanism,
            sasl_plain_username=self.config.sasl_username,
            sasl_plain_password=self.config.sasl_password,
            client_id=self.config.client_id,
            acks="all",
            retries=max(0, int(self.config.retries)),
            request_timeout_ms=max(1000, int(self.config.request_timeout_ms)),
            value_serializer=lambda obj: json.dumps(obj, ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
            key_serializer=lambda s: (s or "").encode("utf-8"),
        )

    def publish(self, topic: str, partition_key: str, payload: dict[str, Any]) -> EbRef:
        if not topic:
            raise RuntimeError("KAFKA_TOPIC_MISSING")
        future = self._producer.send(topic, key=partition_key, value=payload)
        metadata = future.get(timeout=self.config.request_timeout_ms / 1000.0)
        published_at = datetime.now(tz=timezone.utc).isoformat()
        logger.info(
            "EB publish kafka topic=%s partition=%s offset=%s bytes=%s",
            topic,
            metadata.partition,
            metadata.offset,
            len(json.dumps(payload, ensure_ascii=True, separators=(",", ":"))),
        )
        return EbRef(
            topic=topic,
            partition=int(metadata.partition),
            offset=str(metadata.offset),
            offset_kind="kafka_offset",
            published_at_utc=published_at,
        )


def build_kafka_publisher(*, client_id: str) -> KafkaEventBusPublisher:
    bootstrap = (os.getenv("KAFKA_BOOTSTRAP_SERVERS") or "").strip()
    username = (os.getenv("KAFKA_SASL_USERNAME") or "").strip()
    password = (os.getenv("KAFKA_SASL_PASSWORD") or "").strip()
    security_protocol = (os.getenv("KAFKA_SECURITY_PROTOCOL") or "SASL_SSL").strip()
    mechanism = (os.getenv("KAFKA_SASL_MECHANISM") or "PLAIN").strip()
    timeout_ms = int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS") or "15000")
    retries = int(os.getenv("KAFKA_PUBLISH_RETRIES") or "3")
    return KafkaEventBusPublisher(
        KafkaConfig(
            bootstrap_servers=bootstrap,
            security_protocol=security_protocol,
            sasl_mechanism=mechanism,
            sasl_username=username or None,
            sasl_password=password or None,
            client_id=client_id,
            request_timeout_ms=timeout_ms,
            retries=retries,
        )
    )

