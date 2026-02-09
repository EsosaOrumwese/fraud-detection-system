"""WSP runner: oracle/engine world -> stream to IG."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
import json
import logging
import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.config import Config
import requests
import yaml

from fraud_detection.ingestion_gate.catalogue import OutputCatalogue
from fraud_detection.oracle_store.engine_pull import EnginePuller
from fraud_detection.ingestion_gate.errors import IngestionError
from fraud_detection.platform_runtime import append_session_event, resolve_platform_run_id
from fraud_detection.scenario_runner.schemas import SchemaRegistry
from fraud_detection.scenario_runner.storage import LocalObjectStore, S3ObjectStore

from fraud_detection.oracle_store.engine_reader import (
    discover_scenario_ids,
    join_engine_path,
    resolve_engine_root,
)
from fraud_detection.oracle_store.packer import OracleWorldKey
from fraud_detection.oracle_store.stream_sorter import compute_stream_view_id
from fraud_detection.ingestion_gate.ids import derive_engine_event_id

from .config import WspProfile
from .checkpoints import CheckpointCursor, CheckpointStore, FileCheckpointStore, PostgresCheckpointStore

logger = logging.getLogger(__name__)
narrative_logger = logging.getLogger("fraud_detection.platform_narrative")


@dataclass(frozen=True)
class StreamResult:
    engine_run_root: str
    scenario_id: str
    status: str
    emitted: int
    reason: str | None = None
    output_ids: list[str] | None = None


class WorldStreamProducer:
    def __init__(self, profile: WspProfile) -> None:
        self.profile = profile
        self._catalogue = OutputCatalogue(Path(profile.wiring.engine_catalogue_path))
        self._oracle_registry = SchemaRegistry(Path(profile.wiring.schema_root) / "oracle_store")
        self._gate_map = yaml.safe_load(
            Path(profile.wiring.engine_catalogue_path)
            .with_name("engine_gates.map.yaml")
            .read_text(encoding="utf-8")
        )
        self._producer_id = profile.wiring.producer_id
        self._producer_allowlist_ref = profile.wiring.producer_allowlist_ref
        self._producer_allowlist: set[str] | None = None

    def stream_engine_world(
        self,
        *,
        engine_run_root: str | None = None,
        scenario_id: str | None = None,
        scenario_run_id: str | None = None,
        output_ids: list[str] | None = None,
        max_events: int | None = None,
        max_events_per_output: int | None = None,
    ) -> StreamResult:
        run_root = engine_run_root or self.profile.wiring.oracle_engine_run_root
        if not run_root:
            return StreamResult("", "", "FAILED", 0, "ENGINE_ROOT_MISSING")

        resolved_root = resolve_engine_root(run_root, self.profile.wiring.oracle_root)
        append_session_event(
            "wsp",
            "engine_world_selected",
            {"engine_run_root": resolved_root},
            create_if_missing=False,
        )
        platform_run_id = resolve_platform_run_id(create_if_missing=True)
        if not platform_run_id:
            return StreamResult(resolved_root, "", "FAILED", 0, "PLATFORM_RUN_ID_MISSING")

        receipt = self._load_run_receipt(resolved_root)
        if receipt is None:
            return StreamResult(resolved_root, "", "FAILED", 0, "RUN_RECEIPT_UNREADABLE")

        scenario_value = self._resolve_scenario_id(resolved_root, scenario_id)
        if not scenario_value:
            return StreamResult(resolved_root, "", "FAILED", 0, "SCENARIO_ID_MISSING")

        world_key = self._world_key_from_receipt(receipt, scenario_value)
        if world_key is None:
            return StreamResult(resolved_root, scenario_value, "FAILED", 0, "WORLD_KEY_MISSING")
        run_id = str(receipt.get("run_id", ""))
        resolved_scenario_run_id = scenario_run_id or run_id

        strict_seal = self.profile.wiring.profile_id in {"dev", "prod"}
        manifest_error, pack_key, engine_release = self._verify_pack_manifest(
            resolved_root, world_key, strict=strict_seal
        )
        if manifest_error:
            return StreamResult(resolved_root, scenario_value, "FAILED", 0, manifest_error)

        seal_error = self._verify_pack_seal(resolved_root, strict=strict_seal)
        if seal_error:
            return StreamResult(resolved_root, scenario_value, "FAILED", 0, seal_error)
        if not pack_key:
            pack_key = _fallback_pack_key(resolved_root)

        traffic_outputs = self._select_output_ids(output_ids)
        if not traffic_outputs:
            return StreamResult(resolved_root, scenario_value, "FAILED", 0, "NO_TRAFFIC_OUTPUTS")
        context_outputs = self._select_context_output_ids()
        chosen_outputs = _merge_outputs(traffic_outputs, context_outputs)

        missing_gates = self._missing_required_gates(resolved_root, world_key, chosen_outputs)
        if missing_gates and self.profile.policy.require_gate_pass:
            logger.warning("WSP missing gate PASS missing=%s", missing_gates)
            return StreamResult(
                resolved_root,
                scenario_value,
                "FAILED",
                0,
                "GATE_PASS_MISSING",
                output_ids=chosen_outputs,
            )

        producer_error = self._ensure_producer_allowed()
        if producer_error:
            return StreamResult(resolved_root, scenario_value, "FAILED", 0, producer_error)

        checkpoint_store = _build_checkpoint_store(self.profile)
        try:
            append_session_event(
                "wsp",
                "stream_start",
                {
                    "engine_run_root": resolved_root,
                    "scenario_id": scenario_value,
                    "output_ids": chosen_outputs,
                    "traffic_output_ids": traffic_outputs,
                    "context_output_ids": context_outputs,
                    "pack_key": pack_key,
                    "producer_id": self._producer_id,
                    "stream_mode": "stream_view",
                },
                create_if_missing=False,
            )
            emitted = self._stream_from_stream_view(
                engine_root=resolved_root,
                world_key=world_key,
                run_id=run_id,
                scenario_run_id=resolved_scenario_run_id,
                platform_run_id=platform_run_id,
                pack_key=pack_key,
                engine_release=engine_release,
                producer_id=self._producer_id,
                checkpoint_store=checkpoint_store,
                max_events=max_events,
                max_events_per_output=max_events_per_output,
                output_ids=chosen_outputs,
            )
        except IngestionError as exc:
            logger.warning("WSP stream failed reason=%s", exc.code)
            return StreamResult(
                resolved_root, scenario_value, "FAILED", 0, exc.code, output_ids=chosen_outputs
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("WSP stream failed error=%s", str(exc))
            return StreamResult(
                resolved_root, scenario_value, "FAILED", 0, "STREAM_FAILED", output_ids=chosen_outputs
            )
        append_session_event(
            "wsp",
            "engine_world_streamed",
            {
                "engine_run_root": resolved_root,
                "scenario_id": scenario_value,
                "emitted": emitted,
                "output_ids": chosen_outputs,
                "traffic_output_ids": traffic_outputs,
                "context_output_ids": context_outputs,
            },
            create_if_missing=False,
        )
        append_session_event(
            "wsp",
            "stream_complete",
            {"engine_run_root": resolved_root, "emitted": emitted, "status": "STREAMED"},
            create_if_missing=False,
        )
        return StreamResult(
            resolved_root,
            scenario_value,
            "STREAMED",
            emitted,
            output_ids=chosen_outputs,
        )

    def _load_run_receipt(self, engine_root: str) -> dict[str, Any] | None:
        try:
            return _read_run_receipt(engine_root, self.profile)
        except Exception as exc:
            logger.warning("WSP run_receipt unreadable root=%s error=%s", engine_root, str(exc))
            return None

    def _resolve_scenario_id(self, engine_root: str, scenario_id: str | None) -> str | None:
        if scenario_id:
            return scenario_id
        if self.profile.wiring.oracle_scenario_id:
            return self.profile.wiring.oracle_scenario_id
        candidates = discover_scenario_ids(engine_root)
        if len(candidates) == 1:
            return next(iter(candidates))
        if len(candidates) > 1:
            logger.warning("WSP scenario_id ambiguous root=%s candidates=%s", engine_root, candidates)
            return None
        logger.warning("WSP scenario_id missing root=%s", engine_root)
        return None

    def _world_key_from_receipt(
        self, receipt: dict[str, Any], scenario_id: str
    ) -> OracleWorldKey | None:
        try:
            return OracleWorldKey(
                manifest_fingerprint=receipt["manifest_fingerprint"],
                parameter_hash=receipt["parameter_hash"],
                scenario_id=scenario_id,
                seed=int(receipt["seed"]),
            )
        except Exception:
            return None

    def _verify_pack_manifest(
        self, engine_root: str, world_key: OracleWorldKey, *, strict: bool
    ) -> tuple[str | None, str | None, str | None]:
        manifest_path = join_engine_path(engine_root, "_oracle_pack_manifest.json")
        if not _path_exists(
            manifest_path,
            endpoint=self.profile.wiring.object_store_endpoint,
            region=self.profile.wiring.object_store_region,
            path_style=self.profile.wiring.object_store_path_style,
        ):
            if strict:
                return "PACK_MANIFEST_MISSING", None, None
            logger.info("WSP pack manifest missing root=%s", engine_root)
            return None, None, None
        try:
            if manifest_path.startswith("s3://"):
                payload = _read_json_s3(
                    manifest_path,
                    endpoint=self.profile.wiring.object_store_endpoint,
                    region=self.profile.wiring.object_store_region,
                    path_style=self.profile.wiring.object_store_path_style,
                )
            else:
                payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            self._oracle_registry.validate("oracle_pack_manifest.schema.yaml", payload)
        except Exception:
            return "PACK_MANIFEST_INVALID", None, None
        stored_key = payload.get("world_key") or {}
        if stored_key.get("manifest_fingerprint") != world_key.manifest_fingerprint:
            return "WORLD_KEY_MISMATCH", payload.get("oracle_pack_id"), payload.get("engine_release")
        if stored_key.get("parameter_hash") != world_key.parameter_hash:
            return "WORLD_KEY_MISMATCH", payload.get("oracle_pack_id"), payload.get("engine_release")
        if stored_key.get("scenario_id") != world_key.scenario_id:
            return "WORLD_KEY_MISMATCH", payload.get("oracle_pack_id"), payload.get("engine_release")
        if int(stored_key.get("seed", -1)) != world_key.seed:
            return "WORLD_KEY_MISMATCH", payload.get("oracle_pack_id"), payload.get("engine_release")
        return None, payload.get("oracle_pack_id"), payload.get("engine_release")

    def _verify_pack_seal(self, engine_root: str, *, strict: bool) -> str | None:
        seal_paths = [
            join_engine_path(engine_root, "_SEALED.flag"),
            join_engine_path(engine_root, "_SEALED.json"),
        ]
        seal_exists = any(
            _path_exists(
                path,
                endpoint=self.profile.wiring.object_store_endpoint,
                region=self.profile.wiring.object_store_region,
                path_style=self.profile.wiring.object_store_path_style,
            )
            for path in seal_paths
        )
        if seal_exists:
            return None
        if strict:
            return "PACK_NOT_SEALED"
        logger.info("WSP pack not sealed root=%s", engine_root)
        return None

    def _select_output_ids(self, override: list[str] | None) -> list[str]:
        base = list(self.profile.policy.traffic_output_ids)
        if override:
            missing = [item for item in override if item not in base]
            if missing:
                logger.warning("WSP output override not in policy %s", missing)
                return []
            chosen = list(override)
        else:
            chosen = base
        unknown: list[str] = []
        for item in chosen:
            try:
                self._catalogue.get(item)
            except KeyError:
                unknown.append(item)
        if unknown:
            logger.warning("WSP unknown output_ids %s", unknown)
            return []
        return chosen

    def _select_context_output_ids(self) -> list[str]:
        base = list(self.profile.policy.context_output_ids)
        if not base:
            return []
        unknown: list[str] = []
        for item in base:
            try:
                self._catalogue.get(item)
            except KeyError:
                unknown.append(item)
        if unknown:
            logger.warning("WSP unknown context_output_ids %s", unknown)
            return []
        return base

    def _missing_required_gates(
        self,
        engine_root: str,
        world_key: OracleWorldKey,
        output_ids: list[str],
    ) -> dict[str, list[str]]:
        tokens = {
            "manifest_fingerprint": world_key.manifest_fingerprint,
            "parameter_hash": world_key.parameter_hash,
            "scenario_id": world_key.scenario_id,
            "seed": world_key.seed,
        }
        gate_templates = _gate_templates(self._gate_map)
        missing: dict[str, list[str]] = {}
        for output_id in output_ids:
            entry = self._catalogue.get(output_id)
            required = list(entry.read_requires_gates or [])
            if not required:
                continue
            missing_gates: list[str] = []
            for gate_id in required:
                template = gate_templates.get(gate_id)
                if not template:
                    missing_gates.append(gate_id)
                    continue
                relative = _render_path_template(template, tokens)
                if not relative:
                    missing_gates.append(gate_id)
                    continue
                candidate = join_engine_path(engine_root, relative)
                if not _path_exists(
                    candidate,
                    endpoint=self.profile.wiring.object_store_endpoint,
                    region=self.profile.wiring.object_store_region,
                    path_style=self.profile.wiring.object_store_path_style,
                ):
                    missing_gates.append(gate_id)
            if missing_gates:
                missing[output_id] = missing_gates
        return missing

    def _build_facts_payload(
        self,
        engine_root: str,
        world_key: OracleWorldKey,
        run_id: str,
        output_ids: list[str],
    ) -> dict[str, Any]:
        tokens = {
            "manifest_fingerprint": world_key.manifest_fingerprint,
            "parameter_hash": world_key.parameter_hash,
            "scenario_id": world_key.scenario_id,
            "seed": world_key.seed,
            "run_id": run_id,
        }
        locators: list[dict[str, Any]] = []
        output_roles: dict[str, str] = {}
        traffic_outputs = set(self.profile.policy.traffic_output_ids)
        context_outputs = set(self.profile.policy.context_output_ids)
        for output_id in output_ids:
            entry = self._catalogue.get(output_id)
            if not entry.path_template:
                raise IngestionError("OUTPUT_TEMPLATE_MISSING", output_id)
            try:
                relative = entry.path_template.strip().format(**tokens)
            except KeyError as exc:
                raise IngestionError("TEMPLATE_TOKEN_MISSING", f"{output_id}:{exc}")
            locator_path = join_engine_path(engine_root, relative)
            locators.append({"output_id": output_id, "path": locator_path})
            if output_id in traffic_outputs:
                output_roles[output_id] = "business_traffic"
            elif output_id in context_outputs:
                output_roles[output_id] = "behavioural_context"
            else:
                output_roles[output_id] = "other"
        return {
            "pins": {
                "manifest_fingerprint": world_key.manifest_fingerprint,
                "parameter_hash": world_key.parameter_hash,
                "scenario_id": world_key.scenario_id,
                "seed": world_key.seed,
                "run_id": run_id,
            },
            "output_roles": output_roles,
            "locators": locators,
        }

    def _stream_events(
        self,
        puller: EnginePuller,
        *,
        pack_key: str,
        engine_release: str | None,
        producer_id: str,
        scenario_run_id: str | None,
        checkpoint_store: CheckpointStore,
        max_events: int | None,
        output_ids: list[str] | None,
    ) -> int:
        emitted = 0
        speedup = self.profile.policy.stream_speedup
        last_ts: datetime | None = None
        checkpoint_every = max(1, self.profile.wiring.checkpoint_every)
        progress_every = max(1, int(os.getenv("WSP_PROGRESS_EVERY", "1000")))
        progress_seconds = max(1.0, float(os.getenv("WSP_PROGRESS_SECONDS", "30")))
        last_progress_time = time.monotonic()
        last_progress_emitted = 0
        if not output_ids:
            return 0

        def _save_checkpoint(cursor: CheckpointCursor, *, reason: str) -> None:
            checkpoint_store.save(cursor)
            append_session_event(
                "wsp",
                "checkpoint_saved",
                {
                    "pack_key": cursor.pack_key,
                    "output_id": cursor.output_id,
                    "last_file": cursor.last_file,
                    "last_row_index": cursor.last_row_index,
                    "last_ts_utc": cursor.last_ts_utc,
                    "reason": reason,
                },
                create_if_missing=False,
            )

        for output_id in output_ids:
            cursor = checkpoint_store.load(pack_key, output_id)
            paths = sorted(puller.list_locator_paths(output_id))
            logger.info(
                "WSP stream start output_id=%s files=%s speedup=%.2f max_events=%s",
                output_id,
                len(paths),
                speedup,
                max_events if max_events is not None else "all",
            )
            for envelope, path, row_index in puller.iter_events_for_paths_with_positions(
                output_id, paths
            ):
                if cursor and _should_skip(cursor, path, row_index):
                    continue
                platform_run_id = resolve_platform_run_id(create_if_missing=True)
                if platform_run_id and not envelope.get("platform_run_id"):
                    envelope["platform_run_id"] = platform_run_id
                if scenario_run_id:
                    envelope["scenario_run_id"] = scenario_run_id
                elif envelope.get("run_id") and not envelope.get("scenario_run_id"):
                    envelope["scenario_run_id"] = envelope.get("run_id")
                envelope["producer"] = producer_id
                if pack_key and not envelope.get("trace_id"):
                    envelope["trace_id"] = pack_key
                if engine_release and not envelope.get("span_id"):
                    envelope["span_id"] = engine_release
                current_ts = _parse_ts(envelope.get("ts_utc"))
                if last_ts and current_ts:
                    delay = _delay_seconds(last_ts, current_ts, speedup)
                    if delay > 0:
                        time.sleep(delay)
                if current_ts:
                    last_ts = current_ts
                self._push_to_ig(envelope)
                emitted += 1
                cursor = CheckpointCursor(
                    pack_key=pack_key,
                    output_id=output_id,
                    last_file=path,
                    last_row_index=row_index,
                    last_ts_utc=envelope.get("ts_utc"),
                )
                if emitted % checkpoint_every == 0:
                    _save_checkpoint(cursor, reason="periodic_flush")
                if (
                    emitted - last_progress_emitted >= progress_every
                    or (time.monotonic() - last_progress_time) >= progress_seconds
                ):
                    logger.info(
                        "WSP progress output_id=%s emitted=%s last_file=%s row=%s ts=%s",
                        output_id,
                        emitted,
                        path,
                        row_index,
                        envelope.get("ts_utc"),
                    )
                    last_progress_time = time.monotonic()
                    last_progress_emitted = emitted
                if max_events is not None and emitted >= max_events:
                    if cursor:
                        _save_checkpoint(cursor, reason="max_events")
                    return emitted
            if cursor:
                _save_checkpoint(cursor, reason="output_complete")
            logger.info("WSP stream output complete output_id=%s emitted=%s", output_id, emitted)
        return emitted

    def _stream_from_stream_view(
        self,
        *,
        engine_root: str,
        world_key: OracleWorldKey,
        run_id: str,
        scenario_run_id: str,
        platform_run_id: str,
        pack_key: str,
        engine_release: str | None,
        producer_id: str,
        checkpoint_store: CheckpointStore,
        max_events: int | None,
        max_events_per_output: int | None,
        output_ids: list[str],
    ) -> int:
        base_root = self.profile.wiring.stream_view_root or join_engine_path(
            engine_root, "stream_view/ts_utc"
        )
        emitted_total = 0
        speedup = self.profile.policy.stream_speedup
        checkpoint_every = max(1, self.profile.wiring.checkpoint_every)
        progress_every = max(1, int(os.getenv("WSP_PROGRESS_EVERY", "1000")))
        progress_seconds = max(1.0, float(os.getenv("WSP_PROGRESS_SECONDS", "30")))
        output_parallel_env = os.getenv("WSP_OUTPUT_CONCURRENCY")
        if output_parallel_env is not None:
            try:
                output_parallelism = max(1, int(output_parallel_env))
            except ValueError:
                output_parallelism = 1
        else:
            output_parallelism = len(output_ids) if len(output_ids) > 1 else 1
        checkpoint_pack_key = _checkpoint_scope_key(
            pack_key=pack_key,
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
        )

        def _save_checkpoint(cursor: CheckpointCursor, *, reason: str) -> None:
            checkpoint_store.save(cursor)
            append_session_event(
                "wsp",
                "checkpoint_saved",
                {
                    "pack_key": cursor.pack_key,
                    "pack_key_base": pack_key,
                    "platform_run_id": platform_run_id,
                    "scenario_run_id": scenario_run_id,
                    "output_id": cursor.output_id,
                    "last_file": cursor.last_file,
                    "last_row_index": cursor.last_row_index,
                    "last_ts_utc": cursor.last_ts_utc,
                    "reason": reason,
                },
                create_if_missing=False,
            )

        def _stream_output(output_id: str, *, max_events_output: int | None) -> int:
            stream_view_id = compute_stream_view_id(
                engine_run_root=engine_root,
                scenario_id=world_key.scenario_id,
                output_id=output_id,
                sort_keys=["ts_utc", "filename", "file_row_number"],
                partition_granularity="flat",
            )
            stream_view_root = f"{base_root.rstrip('/')}/output_id={output_id}"
            store = _build_stream_view_store(
                stream_view_root,
                endpoint=self.profile.wiring.object_store_endpoint,
                region=self.profile.wiring.object_store_region,
                path_style=self.profile.wiring.object_store_path_style,
            )
            manifest = _read_stream_view_manifest(store)
            receipt = _read_stream_view_receipt(store)
            if not manifest or not receipt:
                raise IngestionError("STREAM_VIEW_MISSING", output_id)
            if receipt.get("status") not in {"OK", None, ""}:
                raise IngestionError("STREAM_VIEW_RECEIPT_BAD", output_id)
            if manifest.get("stream_view_id") and manifest.get("stream_view_id") != stream_view_id:
                logger.warning(
                    "WSP stream_view_id mismatch output_id=%s expected=%s actual=%s",
                    output_id,
                    stream_view_id,
                    manifest.get("stream_view_id"),
                )
                raise IngestionError("STREAM_VIEW_ID_MISMATCH", output_id)
            if manifest.get("output_id") and manifest.get("output_id") != output_id:
                raise IngestionError("STREAM_VIEW_OUTPUT_MISMATCH", output_id)

            narrative_logger.info(
                "WSP stream start run_id=%s output_id=%s max_events=%s speedup=%.2f concurrency=%s",
                run_id,
                output_id,
                max_events_output if max_events_output is not None else "all",
                speedup,
                output_parallelism,
            )

            files = _list_stream_view_files(store)
            if not files:
                raise IngestionError("STREAM_VIEW_EMPTY", output_id)
            files = sorted([path for path in files if path.endswith(".parquet")])
            cursor = checkpoint_store.load(checkpoint_pack_key, output_id)
            last_ts: datetime | None = None
            emitted_output = 0
            last_progress_time = time.monotonic()
            last_progress_emitted = 0
            for file_path in files:
                for row_index, row in _read_stream_view_rows_with_index(
                    file_path,
                    endpoint=self.profile.wiring.object_store_endpoint,
                    region=self.profile.wiring.object_store_region,
                    path_style=self.profile.wiring.object_store_path_style,
                ):
                    if cursor and _should_skip(cursor, file_path, row_index):
                        continue
                    payload = _payload_from_stream_row(row)
                    entry = self._catalogue.get(output_id)
                    pins = {
                        "manifest_fingerprint": world_key.manifest_fingerprint,
                        "parameter_hash": world_key.parameter_hash,
                        "scenario_id": world_key.scenario_id,
                        "seed": world_key.seed,
                        "run_id": run_id,
                    }
                    event_id = derive_engine_event_id(output_id, entry.primary_key, payload, pins)
                    ts_utc = row.get("ts_utc")
                    envelope = {
                        "event_id": event_id,
                        "event_type": output_id,
                        "schema_version": "v1",
                        "ts_utc": _normalize_ts(ts_utc),
                        "manifest_fingerprint": world_key.manifest_fingerprint,
                        "parameter_hash": world_key.parameter_hash,
                        "seed": world_key.seed,
                        "scenario_id": world_key.scenario_id,
                        "run_id": run_id,
                        "platform_run_id": platform_run_id,
                        "scenario_run_id": scenario_run_id,
                        "producer": producer_id,
                        "payload": payload,
                    }
                    if pack_key and not envelope.get("trace_id"):
                        envelope["trace_id"] = pack_key
                    if engine_release and not envelope.get("span_id"):
                        envelope["span_id"] = engine_release
                    current_ts = _parse_ts(envelope.get("ts_utc"))
                    if last_ts and current_ts:
                        delay = _delay_seconds(last_ts, current_ts, speedup)
                        if delay > 0:
                            time.sleep(delay)
                    if current_ts:
                        last_ts = current_ts
                    self._push_to_ig(envelope)
                    emitted_output += 1
                    cursor = CheckpointCursor(
                        pack_key=checkpoint_pack_key,
                        output_id=output_id,
                        last_file=file_path,
                        last_row_index=row_index,
                        last_ts_utc=envelope.get("ts_utc"),
                    )
                    if emitted_output % checkpoint_every == 0:
                        _save_checkpoint(cursor, reason="periodic_flush")
                    if (
                        emitted_output - last_progress_emitted >= progress_every
                        or (time.monotonic() - last_progress_time) >= progress_seconds
                    ):
                        logger.info(
                            "WSP stream_view progress output_id=%s emitted=%s last_file=%s row=%s ts=%s",
                            output_id,
                            emitted_output,
                            file_path,
                            row_index,
                            envelope.get("ts_utc"),
                        )
                        last_progress_time = time.monotonic()
                        last_progress_emitted = emitted_output
                    if max_events_output is not None and emitted_output >= max_events_output:
                        if cursor:
                            _save_checkpoint(cursor, reason="max_events")
                        narrative_logger.info(
                            "WSP stream stop run_id=%s output_id=%s emitted=%s reason=max_events",
                            run_id,
                            output_id,
                            emitted_output,
                        )
                        return emitted_output
                if cursor:
                    _save_checkpoint(cursor, reason="file_complete")
            if cursor:
                _save_checkpoint(cursor, reason="output_complete")
            narrative_logger.info(
                "WSP stream complete run_id=%s output_id=%s emitted=%s",
                run_id,
                output_id,
                emitted_output,
            )
            return emitted_output

        def _resolve_output_cap(remaining_total: int | None) -> int | None:
            if max_events_per_output is not None:
                return max_events_per_output
            if remaining_total is not None:
                return max(0, remaining_total)
            return max_events

        if output_parallelism > 1 and len(output_ids) > 1:
            if max_events is not None and max_events_per_output is None:
                logger.warning(
                    "WSP max_events applies per-output in concurrent mode; set WSP_MAX_EVENTS_PER_OUTPUT for clarity."
                )
            max_workers = min(output_parallelism, len(output_ids))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        _stream_output, output_id, max_events_output=_resolve_output_cap(None)
                    ): output_id
                    for output_id in output_ids
                }
                for future in as_completed(futures):
                    emitted_total += future.result()
            return emitted_total

        for output_id in output_ids:
            remaining_total = None
            if max_events is not None and max_events_per_output is None:
                remaining_total = max_events - emitted_total
                if remaining_total <= 0:
                    break
            emitted_total += _stream_output(
                output_id, max_events_output=_resolve_output_cap(remaining_total)
            )
            if max_events is not None and max_events_per_output is None and emitted_total >= max_events:
                break
        return emitted_total

    def _push_to_ig(self, envelope: dict[str, Any]) -> None:
        if not envelope.get("schema_version"):
            envelope["schema_version"] = "v1"
        url = self.profile.wiring.ig_ingest_url.rstrip("/")
        max_attempts = max(1, int(self.profile.wiring.ig_retry_max_attempts))
        base_delay = max(0, int(self.profile.wiring.ig_retry_base_delay_ms)) / 1000.0
        max_delay = max(base_delay, int(self.profile.wiring.ig_retry_max_delay_ms) / 1000.0)
        headers: dict[str, str] = {}
        if self.profile.wiring.ig_auth_token:
            headers[self.profile.wiring.ig_auth_header] = self.profile.wiring.ig_auth_token
        attempt = 0
        last_error: str | None = None
        while attempt < max_attempts:
            attempt += 1
            try:
                response = requests.post(f"{url}/v1/ingest/push", json=envelope, headers=headers, timeout=30)
            except requests.Timeout:
                last_error = "timeout"
                retryable = True
            except requests.RequestException as exc:
                last_error = str(exc)[:256]
                retryable = True
            else:
                if response.status_code < 400:
                    return
                if response.status_code in (408, 429) or response.status_code >= 500:
                    last_error = f"http_{response.status_code}"
                    retryable = True
                else:
                    detail = response.text[:256] if response.text else f"http_{response.status_code}"
                    raise IngestionError("IG_PUSH_REJECTED", detail)
            if attempt >= max_attempts or not retryable:
                raise IngestionError("IG_PUSH_RETRY_EXHAUSTED", last_error)
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            jitter = random.uniform(0.0, delay) if delay > 0 else 0.0
            logger.warning(
                "WSP IG push retry attempt=%s/%s delay=%.3fs reason=%s event_id=%s",
                attempt,
                max_attempts,
                delay + jitter,
                last_error,
                envelope.get("event_id"),
            )
            time.sleep(delay + jitter)

    def _ensure_producer_allowed(self) -> str | None:
        if not self._producer_id:
            return "PRODUCER_ID_MISSING"
        allowlist_ref = self._producer_allowlist_ref
        if not allowlist_ref:
            return "PRODUCER_ALLOWLIST_MISSING"
        if self._producer_allowlist is None:
            try:
                self._producer_allowlist = _load_allowlist(allowlist_ref)
            except IngestionError as exc:
                logger.warning("WSP producer allowlist error=%s", exc.code)
                return exc.code
        if not self._producer_allowlist:
            return "PRODUCER_ALLOWLIST_EMPTY"
        if self._producer_id not in self._producer_allowlist:
            return "PRODUCER_NOT_ALLOWED"
        return None


def _gate_templates(gate_map: dict[str, Any]) -> dict[str, str]:
    templates: dict[str, str] = {}
    for gate in gate_map.get("gates", []):
        gate_id = gate.get("gate_id")
        template = gate.get("passed_flag_path_template")
        if gate_id and template:
            templates[gate_id] = template
    return templates


def _merge_outputs(traffic_outputs: list[str], context_outputs: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in traffic_outputs + context_outputs:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _render_path_template(template: str, tokens: dict[str, Any]) -> str | None:
    try:
        return template.format(**tokens)
    except KeyError:
        return None


def _path_exists(path: str, *, endpoint: str | None, region: str | None, path_style: bool | None) -> bool:
    if not path:
        return False
    if path.startswith("s3://"):
        parsed = urlparse(path)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        if "*" in key:
            return bool(_list_s3_matches(bucket, key, endpoint, region, path_style))
        return _head_s3(bucket, key, endpoint, region, path_style)
    local = Path(path)
    if "*" in local.name:
        return bool(list(local.parent.glob(local.name)))
    return local.exists()


def _s3_client(endpoint: str | None, region: str | None, path_style: bool | None):
    config = None
    if path_style:
        config = Config(s3={"addressing_style": "path"})
    return boto3.client("s3", endpoint_url=endpoint, region_name=region, config=config)


def _head_s3(bucket: str, key: str, endpoint: str | None, region: str | None, path_style: bool | None) -> bool:
    client = _s3_client(endpoint, region, path_style)
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def _list_s3_matches(
    bucket: str,
    key_pattern: str,
    endpoint: str | None,
    region: str | None,
    path_style: bool | None,
) -> list[str]:
    from fnmatch import fnmatch

    client = _s3_client(endpoint, region, path_style)
    prefix = key_pattern.split("*", 1)[0]
    paginator = client.get_paginator("list_objects_v2")
    matches: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            candidate = item["Key"]
            if fnmatch(candidate, key_pattern):
                matches.append(candidate)
    return matches


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


def _read_run_receipt(engine_root: str, profile: WspProfile) -> dict[str, Any]:
    if engine_root.startswith("s3://"):
        parsed = urlparse(engine_root)
        client = _s3_client(
            profile.wiring.object_store_endpoint,
            profile.wiring.object_store_region,
            profile.wiring.object_store_path_style,
        )
        key = f"{parsed.path.lstrip('/')}/run_receipt.json" if parsed.path else "run_receipt.json"
        response = client.get_object(Bucket=parsed.netloc, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    path = Path(engine_root) / "run_receipt.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _build_checkpoint_store(profile: WspProfile) -> CheckpointStore:
    backend = profile.wiring.checkpoint_backend
    if backend == "postgres":
        dsn = profile.wiring.checkpoint_dsn
        if not dsn:
            raise IngestionError("CHECKPOINT_DSN_MISSING")
        return PostgresCheckpointStore(dsn)
    return FileCheckpointStore(Path(profile.wiring.checkpoint_root))


def _fallback_pack_key(engine_root: str) -> str:
    return hashlib.sha256(engine_root.encode("utf-8")).hexdigest()


def _checkpoint_scope_key(*, pack_key: str, platform_run_id: str, scenario_run_id: str) -> str:
    # Keep checkpoint scope run-bound so new platform runs never resume prior offsets.
    payload = "|".join((pack_key, platform_run_id, scenario_run_id))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _should_skip(cursor: CheckpointCursor, path: str, row_index: int) -> bool:
    if path < cursor.last_file:
        return True
    if path == cursor.last_file and row_index <= cursor.last_row_index:
        return True
    return False


def _read_json_s3(
    path: str,
    *,
    endpoint: str | None,
    region: str | None,
    path_style: bool | None,
) -> dict[str, Any]:
    parsed = urlparse(path)
    client = _s3_client(endpoint, region, path_style)
    response = client.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
    return json.loads(response["Body"].read().decode("utf-8"))


def _build_stream_view_store(
    stream_view_root: str,
    *,
    endpoint: str | None,
    region: str | None,
    path_style: bool | None,
) -> LocalObjectStore | S3ObjectStore:
    if stream_view_root.startswith("s3://"):
        parsed = urlparse(stream_view_root)
        return S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=endpoint,
            region_name=region,
            path_style=path_style,
        )
    return LocalObjectStore(Path(stream_view_root))


def _read_stream_view_manifest(store: LocalObjectStore | S3ObjectStore) -> dict[str, Any]:
    try:
        return store.read_json("_stream_view_manifest.json")
    except Exception:
        return {}


def _read_stream_view_receipt(store: LocalObjectStore | S3ObjectStore) -> dict[str, Any]:
    try:
        return store.read_json("_stream_sort_receipt.json")
    except Exception:
        return {}


def _list_stream_view_files(store: LocalObjectStore | S3ObjectStore) -> list[str]:
    return store.list_files("")


def _read_stream_view_rows_with_index(
    path: str,
    *,
    endpoint: str | None,
    region: str | None,
    path_style: bool | None,
) -> Any:
    import pyarrow as pa
    import pyarrow.fs as fs
    import pyarrow.parquet as pq

    if path.startswith("s3://"):
        parsed = urlparse(path)
        endpoint_override = endpoint
        if endpoint and "://" in endpoint:
            endpoint_override = endpoint.split("://", 1)[1]
        options: dict[str, Any] = {"endpoint_override": endpoint_override, "region": region}
        if path_style:
            # PyArrow uses force_virtual_addressing (not path_style_access).
            # For MinIO/path-style, keep virtual addressing disabled.
            options["force_virtual_addressing"] = False
        access_key = os.getenv("AWS_ACCESS_KEY_ID") or None
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or None
        session_token = os.getenv("AWS_SESSION_TOKEN") or None
        if access_key and secret_key:
            options["access_key"] = access_key
            options["secret_key"] = secret_key
        if session_token:
            options["session_token"] = session_token
        if endpoint and endpoint.startswith("http://"):
            options["scheme"] = "http"
        filesystem = fs.S3FileSystem(**{k: v for k, v in options.items() if v})
        key = parsed.path.lstrip("/")
        with filesystem.open_input_file(f"{parsed.netloc}/{key}") as handle:
            parquet = pq.ParquetFile(handle)
            row_index = 0
            for batch in parquet.iter_batches(batch_size=int(os.getenv("WSP_STREAM_VIEW_BATCH_SIZE", "1024"))):
                for row in batch.to_pylist():
                    yield row_index, row
                    row_index += 1
        return
    local_path = Path(path)
    parquet = pq.ParquetFile(local_path)
    row_index = 0
    for batch in parquet.iter_batches(batch_size=int(os.getenv("WSP_STREAM_VIEW_BATCH_SIZE", "1024"))):
        for row in batch.to_pylist():
            yield row_index, row
            row_index += 1
    return


def _parse_payload(payload_raw: Any) -> dict[str, Any]:
    if payload_raw is None:
        raise IngestionError("STREAM_VIEW_PAYLOAD_MISSING")
    if isinstance(payload_raw, dict):
        return payload_raw
    if isinstance(payload_raw, bytes):
        payload_raw = payload_raw.decode("utf-8")
    if isinstance(payload_raw, str):
        return json.loads(payload_raw)
    return json.loads(str(payload_raw))


def _payload_from_stream_row(row: dict[str, Any]) -> dict[str, Any]:
    if "payload_json" in row:
        return _parse_payload(row.get("payload_json"))
    return row


def _normalize_ts(value: Any) -> str | None:
    parsed = _parse_ts(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    # Canonical envelope requires RFC3339 with exactly 6 fractional digits and trailing Z.
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _load_allowlist(ref: str) -> set[str]:
    if ref.startswith("s3://"):
        raise IngestionError("PRODUCER_ALLOWLIST_UNSUPPORTED", ref)
    path = Path(ref)
    if not path.exists():
        raise IngestionError("PRODUCER_ALLOWLIST_MISSING", ref)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        raise IngestionError("PRODUCER_ALLOWLIST_UNREADABLE", str(exc)) from exc
    entries: list[str] = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        entries.append(cleaned)
    if not entries:
        raise IngestionError("PRODUCER_ALLOWLIST_EMPTY", ref)
    return set(entries)
