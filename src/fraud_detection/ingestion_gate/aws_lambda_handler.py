"""Production ingress edge for API Gateway -> Lambda -> DDB -> MSK."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import hmac
import threading
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from fraud_detection.event_bus.kafka import build_kafka_publisher
from fraud_detection.ingestion_gate.admission import IngestionGate, _bus_probe_streams, _validate_rtdl_policy_alignment
from fraud_detection.ingestion_gate.config import ClassMap, PolicyRev, SchemaPolicy
from fraud_detection.ingestion_gate.health import HealthProbe
from fraud_detection.ingestion_gate.metrics import MetricsRecorder
from fraud_detection.ingestion_gate.policy_digest import compute_policy_digest
from fraud_detection.ingestion_gate.governance import GovernanceEmitter
from fraud_detection.ingestion_gate.rate_limit import RateLimiter
from fraud_detection.ingestion_gate.receipts import ReceiptWriter
from fraud_detection.ingestion_gate.schema import SchemaEnforcer
from fraud_detection.ingestion_gate.schemas import SchemaRegistry
from fraud_detection.ingestion_gate.partitioning import PartitioningProfiles
from fraud_detection.ingestion_gate.security import AuthContext
from fraud_detection.ingestion_gate.store import build_object_store, observe_object_store

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

CORRELATION_FIELDS = (
    "platform_run_id",
    "scenario_run_id",
    "phase_id",
    "event_id",
    "runtime_lane",
    "trace_id",
)

PROTECTED_ROUTES = {
    ("GET", "/ops/health"),
    ("POST", "/ingest/push"),
}

_API_KEY_CACHE = {
    "path": None,
    "value": None,
    "loaded_at_epoch": 0,
}

_GATE_CACHE: dict[str, IngestionGate] = {}
_GATE_CACHE_LOCK = threading.Lock()


def _bundle_root() -> Path:
    override = str(os.getenv("PLATFORM_BUNDLE_ROOT") or os.getenv("IG_BUNDLE_ROOT") or "").strip()
    if override:
        return Path(override).resolve()
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2],
        here.parents[3],
        Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "config" / "platform" / "ig" / "schema_policy_v0.yaml").exists():
            return candidate.resolve()
    return here.parents[2]


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = str(os.getenv(name, "true" if default else "false")).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _aws_runtime_config() -> Config:
    max_pool_connections = max(16, _env_int("IG_AWS_MAX_POOL_CONNECTIONS", 256))
    connect_timeout = max(1, _env_int("IG_AWS_CONNECT_TIMEOUT_SECONDS", 2))
    read_timeout = max(connect_timeout, _env_int("IG_AWS_READ_TIMEOUT_SECONDS", 5))
    return Config(
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        retries={"max_attempts": max(1, _env_int("IG_AWS_MAX_ATTEMPTS", 3)), "mode": "standard"},
        max_pool_connections=max_pool_connections,
    )


_AWS_CONTROL_PLANE_CONFIG = _aws_runtime_config()
_SSM_CLIENT = boto3.client("ssm", config=_AWS_CONTROL_PLANE_CONFIG)
_SQS_CLIENT = boto3.client("sqs", config=_AWS_CONTROL_PLANE_CONFIG)
_DDB_RESOURCE = boto3.resource("dynamodb", config=_AWS_CONTROL_PLANE_CONFIG)


def _configured_envelope() -> dict[str, Any]:
    return {
        "max_request_bytes": _env_int("IG_MAX_REQUEST_BYTES", 1048576),
        "request_timeout_seconds": _env_int("IG_REQUEST_TIMEOUT_SECONDS", 30),
        "internal_retry_max_attempts": _env_int("IG_INTERNAL_RETRY_MAX_ATTEMPTS", 3),
        "internal_retry_backoff_ms": _env_int("IG_INTERNAL_RETRY_BACKOFF_MS", 250),
        "idempotency_ttl_seconds": _env_int("IG_IDEMPOTENCY_TTL_SECONDS", 259200),
        "dlq_mode": os.getenv("IG_DLQ_MODE", "sqs"),
        "dlq_queue_name": os.getenv("IG_DLQ_QUEUE_NAME", ""),
        "replay_mode": os.getenv("IG_REPLAY_MODE", "dlq_replay_workflow"),
        "rate_limit_rps": _env_float("IG_RATE_LIMIT_RPS", 3000.0),
        "rate_limit_burst": _env_int("IG_RATE_LIMIT_BURST", 6000),
    }


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=True),
    }


def _normalize_path(event: dict[str, Any]) -> tuple[str, str]:
    request_context = event.get("requestContext", {}) if isinstance(event, dict) else {}
    http = request_context.get("http", {}) if isinstance(request_context, dict) else {}
    method = str(http.get("method") or "").upper()
    path = str(http.get("path") or event.get("rawPath") or "")
    stage = request_context.get("stage") if isinstance(request_context, dict) else None
    if stage:
        stage_prefix = f"/{stage}"
        if path == stage_prefix:
            path = "/"
        elif path.startswith(f"{stage_prefix}/"):
            path = path[len(stage_prefix) :]
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return method, path


def _body_size_bytes(event: dict[str, Any]) -> int:
    raw = event.get("body")
    if raw is None:
        return 0
    if isinstance(raw, dict):
        return len(json.dumps(raw, separators=(",", ":")).encode("utf-8"))
    if isinstance(raw, str):
        if bool(event.get("isBase64Encoded")):
            try:
                return len(base64.b64decode(raw.encode("utf-8"), validate=False))
            except Exception:
                return len(raw.encode("utf-8"))
        return len(raw.encode("utf-8"))
    return len(str(raw).encode("utf-8"))


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body")
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    text = raw
    if bool(event.get("isBase64Encoded")):
        try:
            text = base64.b64decode(raw.encode("utf-8"), validate=False).decode("utf-8")
        except Exception:
            return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_headers(event: dict[str, Any]) -> dict[str, str]:
    headers = event.get("headers") if isinstance(event.get("headers"), dict) else {}
    return {str(k).lower(): "" if v is None else str(v) for k, v in headers.items()}


def _api_key_cache_ttl_seconds() -> int:
    return _env_int("IG_API_KEY_CACHE_SECONDS", 300)


def _load_expected_api_key() -> tuple[str | None, str | None]:
    api_key_path = str(os.getenv("IG_API_KEY_PATH", "")).strip()
    if not api_key_path:
        return None, "ig_api_key_path_missing"

    now = int(time.time())
    ttl_seconds = _api_key_cache_ttl_seconds()
    if (
        _API_KEY_CACHE["path"] == api_key_path
        and _API_KEY_CACHE["value"]
        and (now - int(_API_KEY_CACHE["loaded_at_epoch"])) < ttl_seconds
    ):
        return str(_API_KEY_CACHE["value"]), None

    LOGGER.info("IG auth cache miss; resolving api key from SSM path=%s", api_key_path)
    try:
        response = _SSM_CLIENT.get_parameter(Name=api_key_path, WithDecryption=True)
    except (BotoCoreError, ClientError) as exc:
        LOGGER.exception("IG api key resolution failed path=%s", api_key_path)
        return None, f"ssm_get_parameter_failed:{type(exc).__name__}"
    value = response.get("Parameter", {}).get("Value") if isinstance(response, dict) else None
    if not value:
        return None, "ig_api_key_empty"
    _API_KEY_CACHE["path"] = api_key_path
    _API_KEY_CACHE["value"] = value
    _API_KEY_CACHE["loaded_at_epoch"] = now
    LOGGER.info("IG auth cache refresh succeeded path=%s ttl_seconds=%s", api_key_path, ttl_seconds)
    return str(value), None


def _authorize(headers: dict[str, str]) -> tuple[AuthContext | None, dict[str, Any] | None]:
    header_name = str(os.getenv("IG_AUTH_HEADER_NAME", "X-IG-Api-Key")).strip().lower()
    supplied = headers.get(header_name, "")
    if not supplied:
        return None, _response(401, {"error": "unauthorized", "reason": "missing_api_key"})
    expected, load_error = _load_expected_api_key()
    if load_error:
        return None, _response(503, {"error": "auth_backend_unavailable", "reason": load_error})
    if not hmac.compare_digest(supplied, str(expected)):
        return None, _response(401, {"error": "unauthorized", "reason": "invalid_api_key"})
    actor = str(os.getenv("IG_EDGE_AUTH_ACTOR", "SYSTEM::managed_edge")).strip() or "SYSTEM::managed_edge"
    principal = str(os.getenv("IG_EDGE_AUTH_PRINCIPAL", "api_key")).strip() or "api_key"
    return AuthContext(actor_id=actor, source_type="SYSTEM", auth_mode="api_key", principal=principal), None


@dataclass
class DdbAdmissionIndex:
    table_name: str
    hash_key_name: str

    def __post_init__(self) -> None:
        self._table = _DDB_RESOURCE.Table(self.table_name)

    def probe(self) -> bool:
        try:
            self._table.load()
            return True
        except Exception:
            return False

    def lookup(self, dedupe_key: str) -> dict[str, Any] | None:
        response = self._table.get_item(
            Key={self.hash_key_name: dedupe_key},
            ConsistentRead=True,
        )
        item = _ddb_normalize(response.get("Item"))
        if not item:
            return None
        eb_topic = item.get("eb_topic")
        eb_ref = None
        if eb_topic:
            eb_ref = {
                "topic": eb_topic,
                "partition": item.get("eb_partition"),
                "offset": item.get("eb_offset"),
                "offset_kind": item.get("eb_offset_kind"),
                "published_at_utc": item.get("eb_published_at_utc"),
            }
        return {
            "state": item.get("state"),
            "payload_hash": item.get("payload_hash"),
            "receipt_ref": item.get("receipt_ref"),
            "receipt_write_failed": bool(item.get("receipt_write_failed", 0)),
            "admitted_at_utc": item.get("admitted_at_utc"),
            "eb_ref": eb_ref,
            "platform_run_id": item.get("platform_run_id"),
            "event_class": item.get("event_class"),
            "event_id": item.get("event_id"),
        }

    def record_in_flight(
        self,
        dedupe_key: str,
        *,
        platform_run_id: str,
        event_class: str,
        event_id: str,
        payload_hash: str,
    ) -> bool:
        now_epoch = int(time.time())
        ttl_attr = str(os.getenv("IG_TTL_ATTRIBUTE", "ttl_epoch")).strip() or "ttl_epoch"
        ttl_seconds = max(60, _env_int("IG_IDEMPOTENCY_TTL_SECONDS", 259200))
        item = {
            self.hash_key_name: dedupe_key,
            "state": "PUBLISH_IN_FLIGHT",
            "platform_run_id": platform_run_id,
            "event_class": event_class,
            "event_id": event_id,
            "payload_hash": payload_hash,
            "receipt_ref": "",
            "receipt_write_failed": 0,
            "created_at_epoch": now_epoch,
            ttl_attr: now_epoch + ttl_seconds,
        }
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(#hk)",
                ExpressionAttributeNames={"#hk": self.hash_key_name},
            )
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "ConditionalCheckFailedException":
                return False
            raise

    def record_admitted(
        self,
        dedupe_key: str,
        *,
        eb_ref: dict[str, Any],
        admitted_at_utc: str,
        payload_hash: str,
    ) -> None:
        self._table.update_item(
            Key={self.hash_key_name: dedupe_key},
            UpdateExpression=(
                "SET #state = :state, payload_hash = :payload_hash, admitted_at_utc = :admitted_at_utc, "
                "eb_topic = :eb_topic, eb_partition = :eb_partition, eb_offset = :eb_offset, "
                "eb_offset_kind = :eb_offset_kind, eb_published_at_utc = :eb_published_at_utc"
            ),
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":state": "ADMITTED",
                ":payload_hash": payload_hash,
                ":admitted_at_utc": admitted_at_utc,
                ":eb_topic": eb_ref.get("topic"),
                ":eb_partition": eb_ref.get("partition"),
                ":eb_offset": eb_ref.get("offset"),
                ":eb_offset_kind": eb_ref.get("offset_kind"),
                ":eb_published_at_utc": eb_ref.get("published_at_utc"),
            },
        )

    def record_ambiguous(self, dedupe_key: str, payload_hash: str | None) -> None:
        self._table.update_item(
            Key={self.hash_key_name: dedupe_key},
            UpdateExpression="SET #state = :state, payload_hash = if_not_exists(payload_hash, :payload_hash)",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":state": "PUBLISH_AMBIGUOUS",
                ":payload_hash": payload_hash or "",
            },
        )

    def record_receipt(self, dedupe_key: str, receipt_ref: str) -> None:
        self._table.update_item(
            Key={self.hash_key_name: dedupe_key},
            UpdateExpression="SET receipt_ref = :receipt_ref, receipt_write_failed = :receipt_write_failed",
            ExpressionAttributeValues={
                ":receipt_ref": receipt_ref,
                ":receipt_write_failed": 0,
            },
        )

    def mark_receipt_failed(self, dedupe_key: str) -> None:
        self._table.update_item(
            Key={self.hash_key_name: dedupe_key},
            UpdateExpression="SET receipt_write_failed = :receipt_write_failed",
            ExpressionAttributeValues={":receipt_write_failed": 1},
        )


@dataclass
class NoopOpsIndex:
    def record_receipt(self, receipt_payload: dict[str, Any], receipt_ref: str) -> None:
        return

    def record_quarantine(self, quarantine_payload: dict[str, Any], quarantine_ref: str, event_id: str | None) -> None:
        return

    def lookup_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        return None

    def lookup_dedupe(self, dedupe_key: str) -> dict[str, Any] | None:
        return None

    def lookup_event(self, event_id: str) -> dict[str, Any] | None:
        return None

    def probe(self) -> bool:
        return True


def _ddb_normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {str(k): _ddb_normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_ddb_normalize(item) for item in value]
    return value


def _runtime_path(*parts: str) -> str:
    return str((_bundle_root() / Path(*parts)).resolve())


def _object_store_root() -> str:
    return str(os.getenv("PLATFORM_STORE_ROOT") or os.getenv("IG_OBJECT_STORE_ROOT") or "s3://fraud-platform-dev-full-object-store").strip()


def _ensure_kafka_bootstrap_env() -> None:
    current = str(os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")).strip()
    if current:
        return
    param_path = str(os.getenv("KAFKA_BOOTSTRAP_BROKERS_PARAM_PATH", "")).strip()
    if not param_path:
        raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS_MISSING")
    response = _SSM_CLIENT.get_parameter(Name=param_path, WithDecryption=True)
    value = response.get("Parameter", {}).get("Value") if isinstance(response, dict) else None
    resolved = str(value or "").strip()
    if not resolved:
        raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS_MISSING")
    os.environ["KAFKA_BOOTSTRAP_SERVERS"] = resolved


def _platform_profile_id() -> str:
    return str(os.getenv("PLATFORM_PROFILE_ID") or "dev_full").strip() or "dev_full"


def _partitioning_profile_id() -> str:
    return str(os.getenv("IG_PARTITIONING_PROFILE_ID") or "ig.partitioning.v0.traffic").strip() or "ig.partitioning.v0.traffic"


def _policy_revision() -> str:
    return str(os.getenv("PLATFORM_CONFIG_REVISION") or "dev-full-v0").strip() or "dev-full-v0"


def _gate_for(platform_run_id: str) -> IngestionGate:
    cached = _GATE_CACHE.get(platform_run_id)
    if cached is not None:
        return cached

    with _GATE_CACHE_LOCK:
        cached = _GATE_CACHE.get(platform_run_id)
        if cached is not None:
            return cached

        init_started = time.perf_counter()
        _ensure_kafka_bootstrap_env()

        schema_policy_ref = _runtime_path("config", "platform", "ig", "schema_policy_v0.yaml")
        class_map_ref = _runtime_path("config", "platform", "ig", "class_map_v0.yaml")
        partitioning_profiles_ref = _runtime_path("config", "platform", "ig", "partitioning_profiles_v0.yaml")
        schema_root = Path(_runtime_path("docs", "model_spec", "platform", "contracts"))
        engine_contracts_root = Path(_runtime_path("docs", "model_spec", "data-engine", "interface_pack", "contracts"))

        policy = SchemaPolicy.load(Path(schema_policy_ref))
        class_map = ClassMap.load(Path(class_map_ref))
        _validate_rtdl_policy_alignment(policy, class_map)
        policy_digest = compute_policy_digest(
            [
                Path(schema_policy_ref),
                Path(class_map_ref),
                Path(partitioning_profiles_ref),
            ]
        )
        policy_rev = PolicyRev(
            policy_id="ig_policy",
            revision=_policy_revision(),
            content_digest=policy_digest,
        )
        partitioning = PartitioningProfiles(partitioning_profiles_ref)
        schema_enforcer = SchemaEnforcer(
            envelope_registry=SchemaRegistry(engine_contracts_root),
            payload_registry_root=_bundle_root(),
            policy=policy,
        )
        contract_registry = SchemaRegistry(schema_root / "ingestion_gate")
        store = observe_object_store(
            build_object_store(
                _object_store_root(),
                s3_endpoint_url=str(os.getenv("OBJECT_STORE_ENDPOINT", "")).strip() or None,
                s3_region=str(os.getenv("OBJECT_STORE_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip() or None,
                s3_path_style=_env_bool("OBJECT_STORE_PATH_STYLE", False),
            )
        )
        receipt_writer = ReceiptWriter(store=store, prefix=f"{platform_run_id}/ig")
        admission_index = DdbAdmissionIndex(
            table_name=str(os.getenv("IG_IDEMPOTENCY_TABLE", "")).strip(),
            hash_key_name=str(os.getenv("IG_HASH_KEY", "dedupe_key")).strip() or "dedupe_key",
        )
        ops_index = NoopOpsIndex()
        bus = build_kafka_publisher(client_id=f"ig-{_platform_profile_id()}-lambda")
        wiring = SimpleNamespace(
            profile_id=_platform_profile_id(),
            policy_rev=policy_rev.revision,
            event_bus_kind="kafka",
            event_bus_path=None,
            partitioning_profile_id=_partitioning_profile_id(),
            health_deny_on_amber=False,
            health_amber_sleep_seconds=0.0,
            auth_mode="api_key",
            auth_allowlist=[],
            service_token_secrets=[],
            api_key_header=str(os.getenv("IG_AUTH_HEADER_NAME", "X-IG-Api-Key")).strip() or "X-IG-Api-Key",
        )
        bus_probe_streams = _bus_probe_streams(wiring, partitioning, class_map)
        health = HealthProbe(
            store=store,
            bus=bus,
            ops_index=ops_index,
            probe_interval_seconds=_env_int("IG_HEALTH_PROBE_INTERVAL_SECONDS", 30),
            max_publish_failures=_env_int("IG_BUS_PUBLISH_FAILURE_THRESHOLD", 3),
            max_read_failures=_env_int("IG_STORE_READ_FAILURE_THRESHOLD", 3),
            health_path=f"{platform_run_id}/ig/health/last_probe.json",
            bus_probe_mode=str(os.getenv("IG_HEALTH_BUS_PROBE_MODE", "describe")).strip().lower(),
            bus_probe_streams=bus_probe_streams,
        )
        health.check()
        metrics = MetricsRecorder(flush_interval_seconds=_env_int("IG_METRICS_FLUSH_SECONDS", 30))
        governance = GovernanceEmitter(
            store=store,
            bus=bus,
            partitioning=partitioning,
            quarantine_spike_threshold=_env_int("IG_QUARANTINE_SPIKE_THRESHOLD", 25),
            quarantine_spike_window_seconds=_env_int("IG_QUARANTINE_SPIKE_WINDOW_SECONDS", 60),
            policy_id=policy_rev.policy_id,
            prefix=platform_run_id,
            policy_activation_audit_mode=str(
                os.getenv("IG_POLICY_ACTIVATION_AUDIT_MODE", "store_only")
            ).strip()
            or "store_only",
        )
        governance.emit_policy_activation(
            {
                "policy_id": policy_rev.policy_id,
                "revision": policy_rev.revision,
                "content_digest": policy_rev.content_digest,
            }
        )
        gate = IngestionGate(
            wiring=wiring,
            policy=policy,
            class_map=class_map,
            policy_rev=policy_rev,
            partitioning=partitioning,
            schema_enforcer=schema_enforcer,
            contract_registry=contract_registry,
            receipt_writer=receipt_writer,
            admission_index=admission_index,
            ops_index=ops_index,
            bus=bus,
            store=store,
            health=health,
            metrics=metrics,
            governance=governance,
            auth_mode="api_key",
            auth_allowlist=[],
            auth_service_token_secrets=[],
            api_key_header=str(os.getenv("IG_AUTH_HEADER_NAME", "X-IG-Api-Key")).strip() or "X-IG-Api-Key",
            push_limiter=RateLimiter(0),
        )
        _GATE_CACHE[platform_run_id] = gate
        LOGGER.info(
            "IG gate initialized platform_run_id=%s init_seconds=%.3f",
            platform_run_id,
            time.perf_counter() - init_started,
        )
        return gate


def _send_dlq(payload: dict[str, Any], reason: str, correlation_headers: dict[str, str]) -> None:
    queue_url = str(os.getenv("IG_DLQ_URL", "")).strip()
    if not queue_url:
        return
    body = {
        "failed_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "reason": reason,
        "platform_run_id": payload.get("platform_run_id"),
        "event_id": payload.get("event_id"),
        "event_type": payload.get("event_type"),
        "scenario_run_id": payload.get("scenario_run_id") or payload.get("run_id"),
        "correlation_headers": correlation_headers,
    }
    try:
        _SQS_CLIENT.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body, ensure_ascii=True))
    except Exception:
        LOGGER.exception("IG DLQ send failed")


def _health_response() -> dict[str, Any]:
    return _response(
        200,
        {
            "status": "ok",
            "service": "ig-edge",
            "mode": "apigw_lambda_ddb_kafka",
            "timestamp_epoch": int(time.time()),
            "envelope": _configured_envelope(),
            "profile_id": _platform_profile_id(),
        },
    )


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    method, path = _normalize_path(event if isinstance(event, dict) else {})
    if (method, path) not in PROTECTED_ROUTES:
        return _response(404, {"error": "route_not_found", "path": path, "method": method})

    if method == "GET" and path == "/ops/health":
        LOGGER.info("IG health request received")

    headers = _extract_headers(event if isinstance(event, dict) else {})
    auth_context, auth_failure = _authorize(headers)
    if auth_failure is not None:
        return auth_failure

    if method == "GET" and path == "/ops/health":
        LOGGER.info("IG health request authorized; returning static health envelope")
        return _health_response()

    body_size = _body_size_bytes(event if isinstance(event, dict) else {})
    max_bytes = _env_int("IG_MAX_REQUEST_BYTES", 1048576)
    if body_size > max_bytes:
        return _response(
            413,
            {
                "error": "payload_too_large",
                "body_size_bytes": body_size,
                "max_request_bytes": max_bytes,
            },
        )

    payload = _parse_body(event if isinstance(event, dict) else {})
    platform_run_id = str(payload.get("platform_run_id") or "missing_platform_run_id").strip() or "missing_platform_run_id"
    correlation_echo = {k: payload.get(k) for k in CORRELATION_FIELDS}

    try:
        remaining_ms = getattr(_context, "get_remaining_time_in_millis", lambda: None)()
        LOGGER.info(
            "IG request start path=%s method=%s platform_run_id=%s remaining_ms=%s",
            path,
            method,
            platform_run_id,
            remaining_ms,
        )
        gate = _gate_for(platform_run_id)
        decision, receipt = gate.admit_push_with_decision(payload, auth_context=auth_context)
        response_body = {
            "decision": decision.decision,
            "receipt": receipt.payload,
            "receipt_ref": receipt.ref,
            "body_size_bytes": body_size,
            "correlation_echo": correlation_echo,
        }
        status_code = 202 if decision.decision in {"ADMIT", "DUPLICATE"} else 400
        return _response(status_code, response_body)
    except Exception as exc:
        reason = str(exc)
        LOGGER.exception(
            json.dumps(
                {
                    "event": "ig_publish_failure",
                    "timestamp_epoch": int(time.time()),
                    "correlation_echo": correlation_echo,
                    "reason": reason,
                }
            )
        )
        _send_dlq(payload, reason, headers)
        return _response(
            503,
            {
                "error": "ingress_publish_failed",
                "reason": reason,
                "body_size_bytes": body_size,
                "correlation_echo": correlation_echo,
            },
        )
