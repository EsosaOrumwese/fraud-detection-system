"""Kafka Event Bus adapters (Confluent Cloud compatible)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any

from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
from kafka import KafkaConsumer
from kafka import TopicPartition as PyKafkaTopicPartition
from kafka.sasl.oauth import AbstractTokenProvider

from .publisher import EbRef

logger = logging.getLogger("fraud_detection.event_bus")


def _import_confluent() -> tuple[Any, Any, Any, Any]:
    from confluent_kafka import Consumer, KafkaError, Producer, TopicPartition

    return Consumer, KafkaError, Producer, TopicPartition


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
    aws_region: str | None = None


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
    aws_region: str | None = None


def _strip_scheme(value: str) -> str:
    v = value.strip()
    for prefix in ("SASL_SSL://", "PLAINTEXT://", "SSL://"):
        if v.upper().startswith(prefix):
            return v[len(prefix) :]
    return v


def _uses_sasl(security_protocol: str) -> bool:
    return str(security_protocol or "").strip().upper().startswith("SASL_")


def _uses_oauth_bearer(security_protocol: str, sasl_mechanism: str) -> bool:
    return _uses_sasl(security_protocol) and str(sasl_mechanism or "").strip().upper() == "OAUTHBEARER"


def _resolve_region(explicit: str | None) -> str:
    return (
        str(explicit or "").strip()
        or (os.getenv("KAFKA_AWS_REGION") or "").strip()
        or (os.getenv("AWS_DEFAULT_REGION") or "").strip()
        or (os.getenv("AWS_REGION") or "").strip()
        or "eu-west-2"
    )


class _MskIamTokenProvider(AbstractTokenProvider):
    def __init__(self, region: str) -> None:
        self._region = _resolve_region(region)

    def token(self) -> str:
        token, _expiry_ms = MSKAuthTokenProvider.generate_auth_token(self._region)
        return token


def _producer_conf(config: KafkaConfig) -> dict[str, Any]:
    request_timeout_ms = _producer_request_timeout_ms(config)
    publish_deadline_ms = _producer_publish_deadline_ms(config)
    conf = {
        "bootstrap.servers": config.bootstrap_servers,
        "security.protocol": config.security_protocol,
        "sasl.mechanism": config.sasl_mechanism,
        "client.id": config.client_id,
        "request.timeout.ms": request_timeout_ms,
        "delivery.timeout.ms": publish_deadline_ms,
        "socket.timeout.ms": publish_deadline_ms,
        "message.send.max.retries": max(0, int(config.retries)),
        "retry.backoff.ms": 250,
        "retry.backoff.max.ms": 2000,
        "socket.keepalive.enable": True,
        "enable.idempotence": True,
        "acks": "all",
    }
    if _uses_oauth_bearer(config.security_protocol, config.sasl_mechanism):
        conf["oauth_cb"] = _confluent_oauth_cb(config.aws_region)
    else:
        conf["sasl.username"] = config.sasl_username or ""
        conf["sasl.password"] = config.sasl_password or ""
    return conf


def _confluent_oauth_cb(region: str | None):
    resolved_region = _resolve_region(region)

    def _callback(_oauth_config: dict[str, Any] | None = None) -> tuple[str, float]:
        token, expiry_ms = MSKAuthTokenProvider.generate_auth_token(resolved_region)
        expiry_seconds = max(1.0, float(expiry_ms) / 1000.0)
        return token, expiry_seconds

    return _callback


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
            aws_region=_resolve_region(config.aws_region),
        )
        self._producer_mode = "oauth" if _uses_oauth_bearer(self.config.security_protocol, self.config.sasl_mechanism) else "standard"
        if (
            _uses_sasl(self.config.security_protocol)
            and self._producer_mode != "oauth"
            and not (self.config.sasl_username and self.config.sasl_password)
        ):
            raise RuntimeError("KAFKA_SASL_CREDENTIALS_MISSING")
        _consumer_cls, _kafka_error_cls, producer_cls, _topic_partition_cls = _import_confluent()
        self._producer = producer_cls(_producer_conf(self.config))

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
        publish_deadline_seconds = _producer_publish_deadline_ms(self.config) / 1000.0
        deadline = time.monotonic() + publish_deadline_seconds
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
            aws_region=_resolve_region(config.aws_region),
        )
        self._consumer_mode = "oauth" if _uses_oauth_bearer(self.config.security_protocol, self.config.sasl_mechanism) else "standard"
        self._oauth_provider = _MskIamTokenProvider(self.config.aws_region) if self._consumer_mode == "oauth" else None
        if (
            _uses_sasl(self.config.security_protocol)
            and self._consumer_mode != "oauth"
            and not (self.config.sasl_username and self.config.sasl_password)
        ):
            raise RuntimeError("KAFKA_SASL_CREDENTIALS_MISSING")
        # Hold the initial startup boundary for fresh readers until the caller
        # persists a real checkpoint. Without this, "latest" readers can skip
        # records that arrive between empty poll cycles.
        self._startup_offsets: dict[tuple[str, int], int] = {}
        if self._consumer_mode == "oauth":
            self._consumer = KafkaConsumer(
                bootstrap_servers=[self.config.bootstrap_servers],
                security_protocol=self.config.security_protocol,
                sasl_mechanism=self.config.sasl_mechanism,
                sasl_oauth_token_provider=self._oauth_provider,
                client_id=self.config.client_id,
                enable_auto_commit=False,
                auto_offset_reset="latest",
                request_timeout_ms=max(1000, int(self.config.request_timeout_ms)),
            )
        else:
            consumer_cls, kafka_error_cls, producer_cls, topic_partition_cls = _import_confluent()
            self._consumer = consumer_cls(_consumer_conf(self.config))

    def list_partitions(self, topic: str) -> list[int]:
        if not topic:
            return []
        if self._consumer_mode == "oauth":
            try:
                partitions = self._consumer.partitions_for_topic(topic) or set()
                return sorted(int(partition) for partition in partitions)
            except Exception as exc:
                logger.warning("Kafka list_partitions failed topic=%s detail=%s", topic, str(exc)[:256])
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
        if self._consumer_mode == "oauth":
            max_records = max(1, int(limit))
            base_tp = PyKafkaTopicPartition(topic, int(partition))
            try:
                self._consumer.assign([base_tp])
                start_offset = self._resolve_oauth_start_offset(
                    topic=topic,
                    partition=partition,
                    from_offset=from_offset,
                    start_position=start_position,
                    base_tp=base_tp,
                )
                self._consumer.seek(base_tp, start_offset)
                rows: list[dict[str, Any]] = []
                records_map = self._consumer.poll(timeout_ms=max(50, int(self.config.poll_timeout_ms)), max_records=max_records)
                for tp, messages in records_map.items():
                    if int(tp.partition) != int(partition):
                        continue
                    for msg in messages:
                        rows.append(
                            {
                                "offset": int(msg.offset),
                                "payload": _decode_kafka_payload(msg.value),
                                "published_at_utc": _kafka_record_timestamp_utc(getattr(msg, "timestamp", None)),
                            }
                        )
                        if len(rows) >= max_records:
                            return rows
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
        max_records = max(1, int(limit))
        _consumer_cls, kafka_error_cls, _producer_cls, topic_partition_cls = _import_confluent()
        base_tp = topic_partition_cls(topic, int(partition))
        try:
            start_offset = self._resolve_standard_start_offset(
                topic=topic,
                partition=partition,
                from_offset=from_offset,
                start_position=start_position,
                base_tp=base_tp,
            )
            self._consumer.assign([topic_partition_cls(topic, int(partition), int(start_offset))])
            rows: list[dict[str, Any]] = []
            poll_timeout = max(0.05, int(self.config.poll_timeout_ms) / 1000.0)
            while len(rows) < max_records:
                msg = self._consumer.poll(timeout=poll_timeout)
                if msg is None:
                    break
                if msg.error():
                    if msg.error().code() != kafka_error_cls._PARTITION_EOF:
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

    def _startup_key(self, *, topic: str, partition: int) -> tuple[str, int]:
        return (str(topic), int(partition))

    def _remember_start_offset(self, *, topic: str, partition: int, offset: int) -> int:
        resolved = max(0, int(offset))
        self._startup_offsets[self._startup_key(topic=topic, partition=partition)] = resolved
        return resolved

    def _startup_offset(self, *, topic: str, partition: int) -> int | None:
        return self._startup_offsets.get(self._startup_key(topic=topic, partition=partition))

    def _resolve_oauth_start_offset(
        self,
        *,
        topic: str,
        partition: int,
        from_offset: int | None,
        start_position: str,
        base_tp: Any,
    ) -> int:
        if from_offset is not None:
            return self._remember_start_offset(topic=topic, partition=partition, offset=max(0, int(from_offset)))
        remembered = self._startup_offset(topic=topic, partition=partition)
        if remembered is not None:
            return remembered
        if str(start_position).strip().lower() == "latest":
            end_offsets = self._consumer.end_offsets([base_tp])
            start_offset = int(end_offsets.get(base_tp, 0))
        else:
            beginning_offsets = self._consumer.beginning_offsets([base_tp])
            start_offset = int(beginning_offsets.get(base_tp, 0))
        return self._remember_start_offset(topic=topic, partition=partition, offset=start_offset)

    def _resolve_standard_start_offset(
        self,
        *,
        topic: str,
        partition: int,
        from_offset: int | None,
        start_position: str,
        base_tp: Any,
    ) -> int:
        if from_offset is not None:
            return self._remember_start_offset(topic=topic, partition=partition, offset=max(0, int(from_offset)))
        remembered = self._startup_offset(topic=topic, partition=partition)
        if remembered is not None:
            return remembered
        low, high = self._consumer.get_watermark_offsets(base_tp, timeout=max(1.0, self.config.request_timeout_ms / 1000.0))
        start_offset = high if str(start_position).strip().lower() == "latest" else low
        return self._remember_start_offset(topic=topic, partition=partition, offset=start_offset)

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
    aws_region = (os.getenv("KAFKA_AWS_REGION") or "").strip() or None
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
            aws_region=aws_region,
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
    aws_region = (os.getenv("KAFKA_AWS_REGION") or "").strip() or None
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
            aws_region=aws_region,
        )
    )


def _producer_request_timeout_ms(config: KafkaConfig) -> int:
    return max(3000, int(config.request_timeout_ms))


def _producer_publish_deadline_ms(config: KafkaConfig) -> int:
    request_timeout_ms = _producer_request_timeout_ms(config)
    return max(5000, request_timeout_ms * 2)


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
