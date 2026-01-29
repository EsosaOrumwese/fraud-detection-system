"""WSP READY consumer runner (SR -> WSP orchestration)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fraud_detection.oracle_store.engine_reader import resolve_engine_root
from fraud_detection.platform_runtime import append_session_event, platform_log_paths
from fraud_detection.scenario_runner.logging_utils import configure_logging
from fraud_detection.scenario_runner.schemas import SchemaRegistry
from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .config import WspProfile
from .control_bus import FileControlBusReader, KinesisControlBusReader, ReadyMessage
from .runner import StreamResult, WorldStreamProducer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReadyConsumeResult:
    message_id: str
    run_id: str
    status: str
    reason: str | None = None
    emitted: int | None = None
    engine_run_root: str | None = None
    scenario_id: str | None = None


class ReadyConsumerRunner:
    def __init__(
        self,
        profile: WspProfile,
        *,
        producer: WorldStreamProducer | None = None,
        store: ObjectStore | None = None,
    ) -> None:
        self.profile = profile
        self._store = store or _build_store(profile)
        self._producer = producer or WorldStreamProducer(profile)
        self._sr_registry = SchemaRegistry(Path(profile.wiring.schema_root) / "scenario_runner")
        kind = (profile.wiring.control_bus_kind or "file").lower()
        if kind == "kinesis":
            if not profile.wiring.control_bus_stream:
                raise RuntimeError("CONTROL_BUS_STREAM_MISSING")
            self._reader = KinesisControlBusReader(
                profile.wiring.control_bus_stream,
                profile.wiring.control_bus_topic,
                region=profile.wiring.control_bus_region,
                endpoint_url=profile.wiring.control_bus_endpoint_url,
                registry=self._sr_registry,
            )
        elif kind == "file":
            root = Path(profile.wiring.control_bus_root)
            self._reader = FileControlBusReader(root, profile.wiring.control_bus_topic, registry=self._sr_registry)
        else:
            raise RuntimeError("CONTROL_BUS_KIND_UNSUPPORTED")

    def poll_once(
        self,
        *,
        max_messages: int | None = None,
        max_events: int | None = None,
    ) -> list[ReadyConsumeResult]:
        messages = list(self._reader.iter_ready_messages())
        if max_messages:
            messages = messages[:max_messages]
        results: list[ReadyConsumeResult] = []
        for message in messages:
            results.append(self._process_message(message, max_events=max_events))
        return results

    def _process_message(self, message: ReadyMessage, *, max_events: int | None) -> ReadyConsumeResult:
        append_session_event(
            "wsp",
            "ready_received",
            {"message_id": message.message_id, "run_id": message.run_id},
            create_if_missing=False,
        )
        if self._already_streamed(message.message_id):
            logger.info("WSP READY duplicate skipped message_id=%s run_id=%s", message.message_id, message.run_id)
            result = ReadyConsumeResult(
                message_id=message.message_id,
                run_id=message.run_id,
                status="SKIPPED_DUPLICATE",
            )
            self._append_ready_record(message.message_id, result)
            return result

        try:
            run_facts = _read_run_facts(self._store, message.facts_view_ref, self.profile)
            self._sr_registry.validate("run_facts_view.schema.yaml", run_facts)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("WSP READY run_facts invalid message_id=%s error=%s", message.message_id, str(exc)[:256])
            result = ReadyConsumeResult(
                message_id=message.message_id,
                run_id=message.run_id,
                status="FAILED",
                reason="RUN_FACTS_INVALID",
            )
            self._append_ready_record(message.message_id, result)
            return result

        scenario_id = (run_facts.get("pins") or {}).get("scenario_id")
        oracle_pack_ref = message.payload.get("oracle_pack_ref") or run_facts.get("oracle_pack_ref") or {}
        engine_run_root = oracle_pack_ref.get("engine_run_root") or self.profile.wiring.oracle_engine_run_root
        oracle_root = oracle_pack_ref.get("oracle_root") or self.profile.wiring.oracle_root
        if not scenario_id:
            result = ReadyConsumeResult(
                message_id=message.message_id,
                run_id=message.run_id,
                status="FAILED",
                reason="SCENARIO_ID_MISSING",
            )
            self._append_ready_record(message.message_id, result)
            return result
        if not engine_run_root:
            result = ReadyConsumeResult(
                message_id=message.message_id,
                run_id=message.run_id,
                status="FAILED",
                reason="ENGINE_ROOT_MISSING",
                scenario_id=scenario_id,
            )
            self._append_ready_record(message.message_id, result)
            return result

        resolved_root = resolve_engine_root(engine_run_root, oracle_root)
        stream_result: StreamResult = self._producer.stream_engine_world(
            engine_run_root=resolved_root,
            scenario_id=scenario_id,
            max_events=max_events,
        )
        result = ReadyConsumeResult(
            message_id=message.message_id,
            run_id=message.run_id,
            status=stream_result.status,
            reason=stream_result.reason,
            emitted=stream_result.emitted,
            engine_run_root=resolved_root,
            scenario_id=scenario_id,
        )
        self._append_ready_record(message.message_id, result)
        return result

    def _already_streamed(self, message_id: str) -> bool:
        record_path = _ready_record_path(message_id)
        if not self._store.exists(record_path):
            return False
        try:
            text = self._store.read_text(record_path)
        except Exception:
            return False
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("status") == "STREAMED":
                return True
        return False

    def _append_ready_record(self, message_id: str, result: ReadyConsumeResult) -> None:
        payload = {
            "message_id": result.message_id,
            "run_id": result.run_id,
            "status": result.status,
            "reason": result.reason,
            "emitted": result.emitted,
            "engine_run_root": result.engine_run_root,
            "scenario_id": result.scenario_id,
            "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._store.append_jsonl(_ready_record_path(message_id), [payload])


def _ready_record_path(message_id: str) -> str:
    return f"fraud-platform/wsp/ready_runs/{message_id}.jsonl"


def _build_store(profile: WspProfile) -> ObjectStore:
    root = profile.wiring.object_store_root
    if root.startswith("s3://"):
        parsed = urlparse(root)
        return S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=profile.wiring.object_store_endpoint,
            region_name=profile.wiring.object_store_region,
            path_style=profile.wiring.object_store_path_style,
        )
    return LocalObjectStore(Path(root))


def _read_run_facts(store: ObjectStore, ref: str, profile: WspProfile) -> dict[str, Any]:
    if ref.startswith("s3://"):
        parsed = urlparse(ref)
        s3_store = S3ObjectStore(
            parsed.netloc,
            prefix="",
            endpoint_url=profile.wiring.object_store_endpoint,
            region_name=profile.wiring.object_store_region,
            path_style=profile.wiring.object_store_path_style,
        )
        return s3_store.read_json(parsed.path.lstrip("/"))
    candidate = Path(ref)
    if candidate.is_absolute():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return store.read_json(ref)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="WSP READY consumer")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Process current READY messages once and exit")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help="Polling interval when looping")
    parser.add_argument("--max-messages", type=int, default=0, help="Max READY messages per poll (0 = all)")
    parser.add_argument("--max-events", type=int, default=0, help="Max events per READY stream (0 = all)")
    args = parser.parse_args()

    configure_logging(level=logging.INFO, log_paths=platform_log_paths(create_if_missing=False))
    profile = WspProfile.load(Path(args.profile))
    runner = ReadyConsumerRunner(profile)

    max_messages = args.max_messages or None
    max_events = args.max_events or None
    if args.once:
        results = runner.poll_once(max_messages=max_messages, max_events=max_events)
        print(json.dumps([r.__dict__ for r in results], sort_keys=True))
        return
    while True:
        results = runner.poll_once(max_messages=max_messages, max_events=max_events)
        if results:
            logger.info("WSP READY poll processed=%s", len(results))
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
