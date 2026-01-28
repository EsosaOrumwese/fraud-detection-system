"""WSP runner: oracle/engine world -> stream to IG."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.config import Config
import requests
import yaml

from fraud_detection.ingestion_gate.catalogue import OutputCatalogue
from fraud_detection.ingestion_gate.engine_pull import EnginePuller
from fraud_detection.ingestion_gate.errors import IngestionError
from fraud_detection.platform_runtime import append_session_event
from fraud_detection.scenario_runner.schemas import SchemaRegistry

from fraud_detection.oracle_store.engine_reader import (
    discover_scenario_ids,
    join_engine_path,
    resolve_engine_root,
)
from fraud_detection.oracle_store.packer import OracleWorldKey

from .config import WspProfile
from .checkpoints import CheckpointCursor, CheckpointStore, FileCheckpointStore, PostgresCheckpointStore

logger = logging.getLogger(__name__)


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

    def stream_engine_world(
        self,
        *,
        engine_run_root: str | None = None,
        scenario_id: str | None = None,
        output_ids: list[str] | None = None,
        max_events: int | None = None,
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

        strict_seal = self.profile.wiring.profile_id in {"dev", "prod"}
        manifest_error, pack_key = self._verify_pack_manifest(resolved_root, world_key, strict=strict_seal)
        if manifest_error:
            return StreamResult(resolved_root, scenario_value, "FAILED", 0, manifest_error)

        seal_error = self._verify_pack_seal(resolved_root, strict=strict_seal)
        if seal_error:
            return StreamResult(resolved_root, scenario_value, "FAILED", 0, seal_error)
        if not pack_key:
            pack_key = _fallback_pack_key(resolved_root)

        chosen_outputs = self._select_output_ids(output_ids)
        if not chosen_outputs:
            return StreamResult(resolved_root, scenario_value, "FAILED", 0, "NO_TRAFFIC_OUTPUTS")

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

        facts_payload = self._build_facts_payload(resolved_root, world_key, run_id, chosen_outputs)
        puller = EnginePuller(
            run_facts_view_path=None,
            catalogue=self._catalogue,
            run_facts_payload=facts_payload,
        )
        checkpoint_store = _build_checkpoint_store(self.profile)
        try:
            emitted = self._stream_events(
                puller,
                pack_key=pack_key,
                checkpoint_store=checkpoint_store,
                max_events=max_events,
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
            },
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
    ) -> tuple[str | None, str | None]:
        manifest_path = join_engine_path(engine_root, "_oracle_pack_manifest.json")
        if not _path_exists(
            manifest_path,
            endpoint=self.profile.wiring.object_store_endpoint,
            region=self.profile.wiring.object_store_region,
            path_style=self.profile.wiring.object_store_path_style,
        ):
            if strict:
                return "PACK_MANIFEST_MISSING", None
            logger.info("WSP pack manifest missing root=%s", engine_root)
            return None, None
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
            return "PACK_MANIFEST_INVALID", None
        stored_key = payload.get("world_key") or {}
        if stored_key.get("manifest_fingerprint") != world_key.manifest_fingerprint:
            return "WORLD_KEY_MISMATCH", payload.get("oracle_pack_id")
        if stored_key.get("parameter_hash") != world_key.parameter_hash:
            return "WORLD_KEY_MISMATCH", payload.get("oracle_pack_id")
        if stored_key.get("scenario_id") != world_key.scenario_id:
            return "WORLD_KEY_MISMATCH", payload.get("oracle_pack_id")
        if int(stored_key.get("seed", -1)) != world_key.seed:
            return "WORLD_KEY_MISMATCH", payload.get("oracle_pack_id")
        return None, payload.get("oracle_pack_id")

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
            output_roles[output_id] = "business_traffic"
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
        checkpoint_store: CheckpointStore,
        max_events: int | None,
        output_ids: list[str] | None,
    ) -> int:
        emitted = 0
        speedup = self.profile.policy.stream_speedup
        last_ts: datetime | None = None
        checkpoint_every = max(1, self.profile.wiring.checkpoint_every)
        if not output_ids:
            return 0
        for output_id in output_ids:
            cursor = checkpoint_store.load(pack_key, output_id)
            paths = sorted(puller.list_locator_paths(output_id))
            for envelope, path, row_index in puller.iter_events_for_paths_with_positions(
                output_id, paths
            ):
                if cursor and _should_skip(cursor, path, row_index):
                    continue
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
                cursor = CheckpointCursor(
                    pack_key=pack_key,
                    output_id=output_id,
                    last_file=path,
                    last_row_index=row_index,
                    last_ts_utc=envelope.get("ts_utc"),
                )
                if emitted % checkpoint_every == 0:
                    checkpoint_store.save(cursor)
                if max_events is not None and emitted >= max_events:
                    if cursor:
                        checkpoint_store.save(cursor)
                    return emitted
            if cursor:
                checkpoint_store.save(cursor)
        return emitted

    def _push_to_ig(self, envelope: dict[str, Any]) -> None:
        url = self.profile.wiring.ig_ingest_url.rstrip("/")
        response = requests.post(f"{url}/v1/ingest/push", json=envelope, timeout=30)
        if response.status_code >= 400:
            raise IngestionError("IG_PUSH_FAILED", response.text)


def _gate_templates(gate_map: dict[str, Any]) -> dict[str, str]:
    templates: dict[str, str] = {}
    for gate in gate_map.get("gates", []):
        gate_id = gate.get("gate_id")
        template = gate.get("passed_flag_path_template")
        if gate_id and template:
            templates[gate_id] = template
    return templates


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
    import hashlib

    return hashlib.sha256(engine_root.encode("utf-8")).hexdigest()


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
