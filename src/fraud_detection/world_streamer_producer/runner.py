"""WSP runner: READY -> run_facts_view -> stream to IG."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from fraud_detection.ingestion_gate.catalogue import OutputCatalogue
from fraud_detection.ingestion_gate.engine_pull import EnginePuller
from fraud_detection.ingestion_gate.errors import IngestionError
from fraud_detection.platform_runtime import append_session_event
from fraud_detection.scenario_runner.schemas import SchemaRegistry
from fraud_detection.scenario_runner.storage import LocalObjectStore, S3ObjectStore

from .config import WspProfile
from .control_bus import FileControlBusReader, ReadyMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamResult:
    message_id: str
    run_id: str
    status: str
    emitted: int
    reason: str | None = None


class WorldStreamProducer:
    def __init__(self, profile: WspProfile) -> None:
        self.profile = profile
        self._catalogue = OutputCatalogue(Path(profile.wiring.engine_catalogue_path))
        self._facts_registry = SchemaRegistry(Path(profile.wiring.schema_root) / "scenario_runner")
        self._control_registry = SchemaRegistry(Path(profile.wiring.schema_root) / "scenario_runner")
        self._reader = FileControlBusReader(
            Path(profile.wiring.control_bus_root),
            profile.wiring.control_bus_topic,
            registry=self._control_registry,
        )

    def poll_ready_once(self, *, max_events: int | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for message in self._reader.iter_ready_messages():
            result = self._process_ready(message, max_events=max_events)
            results.append(result.__dict__)
        return results

    def _process_ready(self, message: ReadyMessage, *, max_events: int | None) -> StreamResult:
        append_session_event(
            "wsp",
            "ready_received",
            {"message_id": message.message_id, "run_id": message.run_id},
            create_if_missing=False,
        )
        try:
            facts = self._load_run_facts(message.facts_view_ref)
        except Exception as exc:
            logger.warning("WSP run_facts unreadable message_id=%s error=%s", message.message_id, str(exc))
            return StreamResult(message.message_id, message.run_id, "FAILED", 0, "RUN_FACTS_UNREADABLE")

        try:
            self._facts_registry.validate("run_facts_view.schema.yaml", facts)
        except ValueError as exc:
            logger.warning("WSP run_facts schema invalid run_id=%s error=%s", message.run_id, str(exc))
            return StreamResult(message.message_id, message.run_id, "FAILED", 0, "RUN_FACTS_INVALID")

        mode = facts.get("traffic_delivery_mode") or "STREAM"
        if mode != "STREAM":
            logger.info("WSP READY skipped run_id=%s mode=%s", message.run_id, mode)
            return StreamResult(message.message_id, message.run_id, "SKIPPED_MODE", 0)

        facts = self._resolve_oracle_paths(facts)
        output_ids = self._traffic_output_ids(facts)
        missing = self._missing_required_gates(facts, output_ids)
        if missing and self.profile.policy.require_gate_pass:
            logger.warning("WSP missing gate PASS run_id=%s missing=%s", message.run_id, missing)
            return StreamResult(message.message_id, message.run_id, "FAILED", 0, "GATE_PASS_MISSING")

        puller = EnginePuller(
            run_facts_view_path=None,
            catalogue=self._catalogue,
            run_facts_payload=facts,
        )
        try:
            emitted = self._stream_events(puller, max_events=max_events)
        except IngestionError as exc:
            logger.warning("WSP stream failed run_id=%s reason=%s", message.run_id, exc.code)
            return StreamResult(message.message_id, message.run_id, "FAILED", 0, exc.code)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("WSP stream failed run_id=%s error=%s", message.run_id, str(exc))
            return StreamResult(message.message_id, message.run_id, "FAILED", 0, "STREAM_FAILED")
        append_session_event(
            "wsp",
            "ready_streamed",
            {"message_id": message.message_id, "run_id": message.run_id, "emitted": emitted},
            create_if_missing=False,
        )
        return StreamResult(message.message_id, message.run_id, "STREAMED", emitted)

    def _stream_events(self, puller: EnginePuller, *, max_events: int | None) -> int:
        emitted = 0
        speedup = self.profile.policy.stream_speedup
        last_ts: datetime | None = None
        for envelope in puller.iter_events():
            envelope["producer"] = "svc:world_stream_producer"
            current_ts = _parse_ts(envelope.get("ts_utc"))
            if last_ts and current_ts:
                delay = _delay_seconds(last_ts, current_ts, speedup)
                if delay > 0:
                    time.sleep(delay)
            if current_ts:
                last_ts = current_ts
            self._push_to_ig(envelope)
            emitted += 1
            if max_events is not None and emitted >= max_events:
                break
        return emitted

    def _push_to_ig(self, envelope: dict[str, Any]) -> None:
        url = self.profile.wiring.ig_ingest_url.rstrip("/")
        response = requests.post(f"{url}/v1/ingest/push", json=envelope, timeout=30)
        if response.status_code >= 400:
            raise IngestionError("IG_PUSH_FAILED", response.text)

    def _traffic_output_ids(self, facts: dict[str, Any]) -> list[str]:
        output_roles = facts.get("output_roles", {})
        locators = facts.get("locators", [])
        locator_ids = {loc.get("output_id") for loc in locators}
        outputs: list[str] = []
        for output_id, role in output_roles.items():
            if role != "business_traffic":
                continue
            if output_id not in locator_ids:
                continue
            outputs.append(output_id)
        return outputs

    def _missing_required_gates(self, facts: dict[str, Any], output_ids: list[str]) -> dict[str, list[str]]:
        passed = {
            receipt.get("gate_id")
            for receipt in facts.get("gate_receipts", [])
            if receipt.get("status") == "PASS"
        }
        missing: dict[str, list[str]] = {}
        for output_id in output_ids:
            entry = self._catalogue.get(output_id)
            required = list(entry.read_requires_gates or [])
            missing_gates = [gate for gate in required if gate not in passed]
            if missing_gates:
                missing[output_id] = missing_gates
        return missing

    def _resolve_oracle_paths(self, facts: dict[str, Any]) -> dict[str, Any]:
        oracle_root = self.profile.wiring.oracle_root
        resolved: list[dict[str, Any]] = []
        for locator in facts.get("locators", []):
            updated = dict(locator)
            path = locator.get("path", "")
            updated["path"] = _resolve_oracle_path(path, oracle_root)
            resolved.append(updated)
        facts["locators"] = resolved
        return facts

    def _load_run_facts(self, facts_view_ref: str) -> dict[str, Any]:
        if facts_view_ref.startswith("s3://"):
            parsed = urlparse(facts_view_ref)
            store = S3ObjectStore(parsed.netloc, prefix="", endpoint_url=None, region_name=None)
            return store.read_json(parsed.path.lstrip("/"))
        if Path(facts_view_ref).is_absolute():
            return json.loads(Path(facts_view_ref).read_text(encoding="utf-8"))
        store = _build_object_store(self.profile)
        return store.read_json(facts_view_ref)


def _build_object_store(profile: WspProfile) -> LocalObjectStore | S3ObjectStore:
    root = profile.wiring.object_store_root
    endpoint = profile.wiring.object_store_endpoint
    region = profile.wiring.object_store_region
    path_style = profile.wiring.object_store_path_style
    if root.startswith("s3://"):
        parsed = urlparse(root)
        return S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=endpoint,
            region_name=region,
            path_style=path_style,
        )
    return LocalObjectStore(Path(root))


def _resolve_oracle_path(path: str, oracle_root: str) -> str:
    if not path:
        return path
    if path.startswith("s3://"):
        return path
    normalized = path.replace("\\", "/")
    oracle_norm = oracle_root.replace("\\", "/").rstrip("/")
    if oracle_norm and normalized.startswith(oracle_norm):
        return path
    if Path(path).is_absolute():
        return path
    if oracle_root.startswith("s3://"):
        return f"{oracle_root.rstrip('/')}/{normalized.lstrip('/')}"
    return str(Path(oracle_root) / Path(path))


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _delay_seconds(prev: datetime, current: datetime, speedup: float) -> float:
    if speedup <= 0:
        return 0.0
    delta = (current - prev).total_seconds()
    if delta <= 0:
        return 0.0
    return delta / speedup
