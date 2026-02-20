"""Kafka Event Bus adapters (Confluent Cloud compatible)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any

from confluent_kafka import Consumer, KafkaError, Producer, TopicPartition

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


@dataclass(frozen=True)
class KafkaReaderConfig:
    bootstrap_servers: str
    security_protocol: str = "SASL_SSL"
    sasl_mechanism: str = "PLAIN"
    sasl_username: str | None = None
    sasl_password: str | None = None
    client_id: str = "fraud-platform-reader"
    request_timeout_ms: int = 15000
    poll_timeout_ms: int = 500
    max_poll_records: int = 500


def _strip_scheme(value: str) -> str:
    v = value.strip()
    for prefix in ("SASL_SSL://", "PLAINTEXT://", "SSL://"):
        if v.upper().startswith(prefix):
            return v[len(prefix) :]
    return v


def _producer_conf(config: KafkaConfig) -> dict[str, Any]:
    return {
        "bootstrap.servers": config.bootstrap_servers,
        "security.protocol": config.security_protocol,
        "sasl.mechanism": config.sasl_mechanism,
        "sasl.username": config.sasl_username or "",
        "sasl.password": config.sasl_password or "",
        "client.id": config.client_id,
        "request.timeout.ms": max(1000, int(config.request_timeout_ms)),
        "message.send.max.retries": max(0, int(config.retries)),
        "enable.idempotence": True,
    }


def _consumer_conf(config: KafkaReaderConfig) -> dict[str, Any]:
    return {
        "bootstrap.servers": config.bootstrap_servers,
        "security.protocol": config.security_protocol,
        "sasl.mechanism": config.sasl_mechanism,
        "sasl.username": config.sasl_username or "",
        "sasl.password": config.sasl_password or "",
        "client.id": config.client_id,
        "group.id": f"{config.client_id}-group",
        "enable.auto.commit": False,
        "auto.offset.reset": "latest",
        "session.timeout.ms": max(6000, int(config.request_timeout_ms)),
    }


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
        self._producer = Producer(_producer_conf(self.config))

    def publish(self, topic: str, partition_key: str, payload: dict[str, Any]) -> EbRef:
        if not topic:
            raise RuntimeError("KAFKA_TOPIC_MISSING")
        payload_bytes = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        delivery: dict[str, Any] = {}

        def _on_delivery(err, msg) -> None:
            delivery["error"] = err
            delivery["message"] = msg

        self._producer.produce(
            topic=topic,
            key=(partition_key or "").encode("utf-8"),
            value=payload_bytes,
            on_delivery=_on_delivery,
        )
        deadline = time.monotonic() + (max(1000, int(self.config.request_timeout_ms)) / 1000.0)
        while "message" not in delivery and "error" not in delivery:
            self._producer.poll(0.1)
            if time.monotonic() >= deadline:
                raise RuntimeError("KAFKA_PUBLISH_TIMEOUT")
        err = delivery.get("error")
        if err is not None:
            raise RuntimeError(f"KAFKA_PUBLISH_ERROR:{err}")
        msg = delivery["message"]
        published_at = datetime.now(tz=timezone.utc).isoformat()
        logger.info(
            "EB publish kafka topic=%s partition=%s offset=%s bytes=%s",
            topic,
            msg.partition(),
            msg.offset(),
            len(payload_bytes),
        )
        return EbRef(
            topic=topic,
            partition=int(msg.partition()),
            offset=str(msg.offset()),
            offset_kind="kafka_offset",
            published_at_utc=published_at,
        )


class KafkaEventBusReader:
    def __init__(self, config: KafkaReaderConfig) -> None:
        if not config.bootstrap_servers.strip():
            raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS_MISSING")
        bootstrap = _strip_scheme(config.bootstrap_servers)
        self.config = KafkaReaderConfig(
            bootstrap_servers=bootstrap,
            security_protocol=config.security_protocol,
            sasl_mechanism=config.sasl_mechanism,
            sasl_username=config.sasl_username,
            sasl_password=config.sasl_password,
            client_id=config.client_id,
            request_timeout_ms=config.request_timeout_ms,
            poll_timeout_ms=config.poll_timeout_ms,
            max_poll_records=config.max_poll_records,
        )
        if not (self.config.sasl_username and self.config.sasl_password):
            raise RuntimeError("KAFKA_SASL_CREDENTIALS_MISSING")
        self._consumer = Consumer(_consumer_conf(self.config))

    def list_partitions(self, topic: str) -> list[int]:
        if not topic:
            return []
        try:
            metadata = self._consumer.list_topics(topic=topic, timeout=max(1.0, self.config.request_timeout_ms / 1000.0))
            topic_meta = metadata.topics.get(topic)
            if topic_meta is None or topic_meta.error is not None:
                return []
            return sorted(int(partition) for partition in topic_meta.partitions.keys())
        except Exception as exc:
            logger.warning("Kafka list_partitions failed topic=%s detail=%s", topic, str(exc)[:256])
            return []

    def read(
        self,
        *,
        topic: str,
        partition: int,
        from_offset: int | None,
        limit: int,
        start_position: str = "latest",
    ) -> list[dict[str, Any]]:
        if not topic:
            return []
        max_records = max(1, int(limit))
        base_tp = TopicPartition(topic, int(partition))
        try:
            if from_offset is None:
                low, high = self._consumer.get_watermark_offsets(base_tp, timeout=max(1.0, self.config.request_timeout_ms / 1000.0))
                start_offset = high if str(start_position).strip().lower() == "latest" else low
            else:
                start_offset = max(0, int(from_offset))
            self._consumer.assign([TopicPartition(topic, int(partition), int(start_offset))])
            rows: list[dict[str, Any]] = []
            poll_timeout = max(0.05, int(self.config.poll_timeout_ms) / 1000.0)
            while len(rows) < max_records:
                msg = self._consumer.poll(timeout=poll_timeout)
                if msg is None:
                    break
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        logger.warning(
                            "Kafka read failed topic=%s partition=%s from_offset=%s detail=%s",
                            topic,
                            partition,
                            from_offset,
                            str(msg.error())[:256],
                        )
                    break
                ts_type, ts_ms = msg.timestamp()
                if ts_type is None:
                    ts_ms = None
                rows.append(
                    {
                        "offset": int(msg.offset()),
                        "payload": _decode_kafka_payload(msg.value()),
                        "published_at_utc": _kafka_record_timestamp_utc(ts_ms),
                    }
                )
            return rows
        except Exception as exc:
            logger.warning(
                "Kafka read failed topic=%s partition=%s from_offset=%s detail=%s",
                topic,
                partition,
                from_offset,
                str(exc)[:256],
            )
            return []

    def close(self) -> None:
        try:
            self._consumer.close()
        except Exception:
            return


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


def build_kafka_reader(*, client_id: str) -> KafkaEventBusReader:
    bootstrap = (os.getenv("KAFKA_BOOTSTRAP_SERVERS") or "").strip()
    username = (os.getenv("KAFKA_SASL_USERNAME") or "").strip()
    password = (os.getenv("KAFKA_SASL_PASSWORD") or "").strip()
    security_protocol = (os.getenv("KAFKA_SECURITY_PROTOCOL") or "SASL_SSL").strip()
    mechanism = (os.getenv("KAFKA_SASL_MECHANISM") or "PLAIN").strip()
    timeout_ms = int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS") or "15000")
    poll_timeout_ms = int(os.getenv("KAFKA_POLL_TIMEOUT_MS") or "500")
    max_poll_records = int(os.getenv("KAFKA_MAX_POLL_RECORDS") or "500")
    return KafkaEventBusReader(
        KafkaReaderConfig(
            bootstrap_servers=bootstrap,
            security_protocol=security_protocol,
            sasl_mechanism=mechanism,
            sasl_username=username or None,
            sasl_password=password or None,
            client_id=client_id,
            request_timeout_ms=timeout_ms,
            poll_timeout_ms=poll_timeout_ms,
            max_poll_records=max_poll_records,
        )
    )


def _decode_kafka_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, bytes):
        try:
            decoded = json.loads(value.decode("utf-8"))
            return decoded if isinstance(decoded, dict) else {}
        except Exception:
            return {}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except Exception:
            return {}
    return {}


def _kafka_record_timestamp_utc(timestamp_ms: Any) -> str | None:
    try:
        value = int(timestamp_ms)
    except Exception:
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).isoformat()
