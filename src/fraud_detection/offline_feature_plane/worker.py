"""OFS Phase 8 run/operate worker and launcher CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import yaml

from fraud_detection.platform_runtime import resolve_platform_run_id, resolve_run_scoped_path
from fraud_detection.scenario_runner.storage import S3ObjectStore, build_object_store

from .contracts import OfsBuildIntent
from .phase3 import OfsBuildPlanResolver, OfsBuildPlanResolverConfig
from .phase4 import OfsReplayBasisResolver, OfsReplayBasisResolverConfig, ReplayBasisEvidence
from .phase5 import OfsLabelAsOfResolver, OfsLabelResolverConfig
from .phase6 import OfsDatasetDraft, OfsDatasetDraftBuilder, OfsDatasetDraftBuilderConfig, OfsFeatureDraftRow
from .phase7 import OfsManifestPublisher, OfsManifestPublisherConfig, OfsPhase7PublishError
from .run_control import OfsRunControl, OfsRunControlPolicy
from .run_ledger import OfsRunLedger, OfsRunLedgerError

logger = logging.getLogger("fraud_detection.offline_feature_plane.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9_.:-]+")

_REQUEST_SCHEMA = "learning.ofs_job_request.v0"
_DATASET_BUILD = "dataset_build"
_PUBLISH_RETRY = "publish_retry"


@dataclass(frozen=True)
class _RequestError(RuntimeError):
    code: str
    message: str

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, f"{self.code}:{self.message}")


@dataclass(frozen=True)
class OfsLauncherPolicy:
    policy_id: str
    revision: str
    max_publish_retry_attempts: int
    request_poll_seconds: float
    request_batch_limit: int


@dataclass(frozen=True)
class OfsWorkerConfig:
    profile_path: Path
    policy_ref: Path
    profile_id: str
    stream_id: str
    platform_run_id: str | None
    required_platform_run_id: str | None
    run_ledger_locator: str
    object_store_root: str
    object_store_endpoint: str | None
    object_store_region: str | None
    object_store_path_style: bool
    request_prefix: str
    request_poll_seconds: float
    request_batch_limit: int
    max_publish_retry_attempts: int
    feature_profile_ref: str
    label_store_locator: str
    replay_eb_observations_ref: str | None
    replay_archive_observations_ref: str | None
    replay_discover_archive_events: bool
    require_complete_for_dataset_build: bool
    service_release_id: str
    launcher_policy_id: str
    launcher_policy_revision: str
    run_config_digest: str


class OfsJobWorker:
    def __init__(self, config: OfsWorkerConfig) -> None:
        self.config = config
        self.store = build_object_store(
            root=config.object_store_root,
            s3_endpoint_url=config.object_store_endpoint,
            s3_region=config.object_store_region,
            s3_path_style=config.object_store_path_style,
        )
        self.ledger = OfsRunLedger(locator=config.run_ledger_locator)
        self.control = OfsRunControl(
            ledger=self.ledger,
            policy=OfsRunControlPolicy(max_publish_retry_attempts=config.max_publish_retry_attempts),
        )

    def run_once(self) -> int:
        processed = 0
        for request_ref in sorted(self.store.list_files(self.config.request_prefix)):
            request_payload = self._read_json_ref(request_ref)
            request_id = _required_text(request_payload.get("request_id"), "REQUEST_INVALID", "request_id")
            receipt_rel = _receipt_relative_path(self._request_platform_run_id(request_payload), request_id)
            if self.store.exists(receipt_rel):
                continue
            receipt = self._process_request(request_payload=request_payload, request_ref=request_ref)
            try:
                self.store.write_json_if_absent(receipt_rel, receipt)
            except FileExistsError:
                pass
            processed += 1
            if processed >= self.config.request_batch_limit:
                break
        return processed

    def run_forever(self) -> None:
        while True:
            if self.run_once() == 0:
                time.sleep(self.config.request_poll_seconds)

    def _process_request(self, *, request_payload: Mapping[str, Any], request_ref: str) -> dict[str, Any]:
        started = _utc_now()
        request_id = _required_text(request_payload.get("request_id"), "REQUEST_INVALID", "request_id")
        platform_run_id = self._request_platform_run_id(request_payload)
        command = _required_text(request_payload.get("command"), "REQUEST_INVALID", "command").lower()
        digest = _required_text(request_payload.get("run_config_digest"), "REQUEST_INVALID", "run_config_digest")
        if digest != self.config.run_config_digest:
            return self._receipt(
                request_id=request_id,
                command=command,
                platform_run_id=platform_run_id,
                status="FAILED",
                started_at_utc=started,
                completed_at_utc=_utc_now(),
                request_ref=request_ref,
                error_code="RUN_CONFIG_DIGEST_MISMATCH",
                error_message="request digest does not match worker digest",
            )
        if self.config.required_platform_run_id and platform_run_id != self.config.required_platform_run_id:
            return self._receipt(
                request_id=request_id,
                command=command,
                platform_run_id=platform_run_id,
                status="FAILED",
                started_at_utc=started,
                completed_at_utc=_utc_now(),
                request_ref=request_ref,
                error_code="RUN_SCOPE_INVALID",
                error_message="request platform_run_id does not match required active run",
            )
        try:
            if command == _DATASET_BUILD:
                result = self._execute_dataset_build(request_payload)
            elif command == _PUBLISH_RETRY:
                result = self._execute_publish_retry(request_payload)
            else:
                raise _RequestError("REQUEST_COMMAND_UNSUPPORTED", f"unsupported command: {command}")
        except _RequestError as exc:
            return self._receipt(
                request_id=request_id,
                command=command,
                platform_run_id=platform_run_id,
                status="FAILED",
                started_at_utc=started,
                completed_at_utc=_utc_now(),
                request_ref=request_ref,
                error_code=exc.code,
                error_message=exc.message,
            )
        except OfsRunLedgerError as exc:
            return self._receipt(
                request_id=request_id,
                command=command,
                platform_run_id=platform_run_id,
                status="FAILED",
                started_at_utc=started,
                completed_at_utc=_utc_now(),
                request_ref=request_ref,
                error_code=str(exc.code or "RUN_LEDGER_ERROR"),
                error_message=exc.message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("OFS worker request failed request_id=%s", request_id)
            return self._receipt(
                request_id=request_id,
                command=command,
                platform_run_id=platform_run_id,
                status="FAILED",
                started_at_utc=started,
                completed_at_utc=_utc_now(),
                request_ref=request_ref,
                error_code="WORKER_RUNTIME_ERROR",
                error_message=str(exc)[:500],
            )
        return self._receipt(
            request_id=request_id,
            command=command,
            platform_run_id=platform_run_id,
            status=str(result.get("status") or "DONE"),
            started_at_utc=started,
            completed_at_utc=_utc_now(),
            request_ref=request_ref,
            run_key=_none_if_blank(result.get("run_key")),
            refs=_mapping_or_empty(result.get("refs")),
            details=_mapping_or_empty(result.get("details")),
            error_code=_none_if_blank(result.get("error_code")),
            error_message=_none_if_blank(result.get("error_message")),
        )
    def _execute_dataset_build(self, request_payload: Mapping[str, Any]) -> dict[str, Any]:
        intent_payload = _mapping(request_payload.get("intent"), "REQUEST_INVALID", "intent")
        intent = OfsBuildIntent.from_payload(intent_payload)
        request_run_id = self._request_platform_run_id(request_payload)
        if intent.platform_run_id != request_run_id:
            raise _RequestError("RUN_SCOPE_INVALID", "request platform_run_id does not match intent")

        submitted = self.control.enqueue(intent=intent, queued_at_utc=_utc_now())
        run_key = submitted.run_key
        submission_outcome = str(submitted.outcome).upper()
        if submission_outcome == "DUPLICATE" and str(submitted.receipt.status).upper() == "DONE":
            return {
                "status": "ALREADY_DONE",
                "run_key": run_key,
                "refs": {"result_ref": str(submitted.receipt.result_ref or "")},
                "details": {"submission_outcome": submission_outcome},
            }

        self.control.start_full_run(run_key=run_key, started_at_utc=_utc_now())
        inputs = _mapping_or_empty(request_payload.get("inputs"))
        supersedes = tuple(sorted({str(item).strip() for item in _list_or_empty(inputs.get("supersedes_manifest_refs")) if str(item).strip()}))
        backfill_reason = _none_if_blank(inputs.get("backfill_reason"))
        try:
            phase3 = OfsBuildPlanResolver(
                config=OfsBuildPlanResolverConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                    feature_profile_ref=self.config.feature_profile_ref,
                )
            )
            resolved_plan = phase3.resolve(intent=intent, run_key=run_key)
            plan_ref = phase3.emit_immutable(plan=resolved_plan)

            replay_evidence = _load_replay_evidence(inputs)
            phase4 = OfsReplayBasisResolver(
                config=OfsReplayBasisResolverConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                    eb_observations_ref=self.config.replay_eb_observations_ref,
                    archive_observations_ref=self.config.replay_archive_observations_ref,
                    discover_archive_events=self.config.replay_discover_archive_events,
                    require_complete_for_dataset_build=self.config.require_complete_for_dataset_build,
                )
            )
            replay_receipt = phase4.resolve(intent=intent, run_key=run_key, evidence=replay_evidence)
            replay_ref = phase4.emit_immutable(receipt=replay_receipt)

            replay_events = _load_replay_events(inputs)
            if not replay_events:
                replay_events = self._replay_events_from_archive(intent)
            if not replay_events:
                raise _RequestError("REPLAY_EVENTS_MISSING", "replay events missing")

            target_subjects = _load_target_subjects(inputs)
            if not target_subjects:
                target_subjects = _target_subjects_from_replay_events(intent.platform_run_id, replay_events)
            if not target_subjects:
                raise _RequestError("LABEL_SCOPE_EMPTY", "target_subjects resolved empty")

            phase5 = OfsLabelAsOfResolver(
                config=OfsLabelResolverConfig(
                    label_store_locator=self.config.label_store_locator,
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                )
            )
            label_receipt = phase5.resolve(intent=intent, target_subjects=target_subjects, run_key=run_key)
            label_ref = phase5.emit_immutable(receipt=label_receipt)

            phase6 = OfsDatasetDraftBuilder(
                config=OfsDatasetDraftBuilderConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                )
            )
            draft = phase6.build(
                intent=intent,
                resolved_feature_profile=resolved_plan.feature_profile,
                replay_events=replay_events,
                replay_receipt=replay_receipt.as_dict(),
                label_receipt=label_receipt.as_dict(),
                run_key=run_key,
            )
            draft_ref = phase6.emit_immutable(draft=draft)

            phase7 = OfsManifestPublisher(
                config=OfsManifestPublisherConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                )
            )
            publication = phase7.publish(
                intent=intent,
                draft=draft,
                replay_receipt=replay_receipt.as_dict(),
                label_receipt=label_receipt.as_dict(),
                draft_ref=draft_ref,
                replay_receipt_ref=replay_ref,
                label_receipt_ref=label_ref,
                run_key=run_key,
                supersedes_manifest_refs=supersedes,
                backfill_reason=backfill_reason,
            )
            self.control.mark_done(run_key=run_key, completed_at_utc=_utc_now(), result_ref=publication.manifest_ref)
            return {
                "status": "DONE",
                "run_key": run_key,
                "refs": {
                    "resolved_build_plan_ref": plan_ref,
                    "replay_receipt_ref": replay_ref,
                    "label_receipt_ref": label_ref,
                    "dataset_draft_ref": draft_ref,
                    "manifest_ref": publication.manifest_ref,
                    "publication_receipt_ref": _artifact_ref(self.config, publication.artifact_relative_path()),
                },
                "details": {"submission_outcome": submission_outcome, "publication_mode": publication.publication_mode},
            }
        except OfsPhase7PublishError as exc:
            self.control.mark_publish_pending(run_key=run_key, pending_at_utc=_utc_now(), reason_code=f"PHASE7_{exc.code}")
            return {
                "status": "PUBLISH_PENDING",
                "run_key": run_key,
                "error_code": exc.code,
                "error_message": exc.message,
                "details": {"submission_outcome": submission_outcome, "pending_reason": f"PHASE7_{exc.code}"},
            }
        except Exception as exc:  # noqa: BLE001
            try:
                self.control.mark_failed(run_key=run_key, failed_at_utc=_utc_now(), reason_code=_compact_reason(exc))
            except Exception:
                logger.exception("OFS mark_failed failed run_key=%s", run_key)
            raise

    def _execute_publish_retry(self, request_payload: Mapping[str, Any]) -> dict[str, Any]:
        run_key = _required_text(request_payload.get("run_key"), "REQUEST_INVALID", "run_key")
        publish_inputs = _mapping(request_payload.get("publish_inputs"), "REQUEST_INVALID", "publish_inputs")
        self.control.start_publish_retry(run_key=run_key, requested_at_utc=_utc_now(), started_at_utc=_utc_now())

        intent = OfsBuildIntent.from_payload(_mapping(publish_inputs.get("intent"), "REQUEST_INVALID", "publish_inputs.intent"))
        request_run_id = self._request_platform_run_id(request_payload)
        if intent.platform_run_id != request_run_id:
            raise _RequestError("RUN_SCOPE_INVALID", "publish retry request/intention scope mismatch")
        draft = _dataset_draft_from_payload(_mapping(publish_inputs.get("draft"), "REQUEST_INVALID", "publish_inputs.draft"))
        replay_receipt = _mapping(publish_inputs.get("replay_receipt"), "REQUEST_INVALID", "publish_inputs.replay_receipt")
        label_receipt = _mapping_or_empty(publish_inputs.get("label_receipt")) or None

        supersedes = tuple(sorted({str(item).strip() for item in _list_or_empty(publish_inputs.get("supersedes_manifest_refs")) if str(item).strip()}))
        backfill_reason = _none_if_blank(publish_inputs.get("backfill_reason"))

        phase7 = OfsManifestPublisher(
            config=OfsManifestPublisherConfig(
                object_store_root=self.config.object_store_root,
                object_store_endpoint=self.config.object_store_endpoint,
                object_store_region=self.config.object_store_region,
                object_store_path_style=self.config.object_store_path_style,
            )
        )
        try:
            publication = phase7.publish(
                intent=intent,
                draft=draft,
                replay_receipt=replay_receipt,
                label_receipt=label_receipt,
                run_key=run_key,
                supersedes_manifest_refs=supersedes,
                backfill_reason=backfill_reason,
            )
            self.control.mark_done(run_key=run_key, completed_at_utc=_utc_now(), result_ref=publication.manifest_ref)
            return {
                "status": "DONE",
                "run_key": run_key,
                "refs": {
                    "manifest_ref": publication.manifest_ref,
                    "publication_receipt_ref": _artifact_ref(self.config, publication.artifact_relative_path()),
                },
                "details": {"publication_mode": publication.publication_mode, "retry_mode": "publish_only"},
            }
        except OfsPhase7PublishError as exc:
            self.control.mark_publish_pending(run_key=run_key, pending_at_utc=_utc_now(), reason_code=f"PHASE7_{exc.code}")
            return {
                "status": "PUBLISH_PENDING",
                "run_key": run_key,
                "error_code": exc.code,
                "error_message": exc.message,
                "details": {"pending_reason": f"PHASE7_{exc.code}"},
            }
        except Exception as exc:  # noqa: BLE001
            try:
                self.control.mark_failed(run_key=run_key, failed_at_utc=_utc_now(), reason_code=_compact_reason(exc))
            except Exception:
                logger.exception("OFS publish-retry mark_failed failed run_key=%s", run_key)
            raise

    def _replay_events_from_archive(self, intent: OfsBuildIntent) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for basis in intent.replay_basis:
            prefix = (
                f"{intent.platform_run_id}/archive/events/"
                f"topic={_safe_token(basis.topic)}/partition={basis.partition}/offset_kind={_safe_token(basis.offset_kind)}"
            )
            for ref in self.store.list_files(prefix):
                payload = self._read_json_ref(ref)
                origin = _mapping_or_empty(payload.get("origin_offset"))
                topic = str(origin.get("topic") or "").strip()
                partition = _int_or_none(origin.get("partition"))
                offset_kind = str(origin.get("offset_kind") or "").strip()
                offset = str(origin.get("offset") or "").strip()
                if topic != basis.topic or partition != int(basis.partition) or offset_kind != basis.offset_kind:
                    continue
                offset_int = _int_or_none(offset)
                if offset_int is None or offset_int < int(basis.start_offset) or offset_int > int(basis.end_offset):
                    continue
                envelope = _mapping_or_empty(payload.get("envelope"))
                event_id = str(envelope.get("event_id") or "").strip()
                ts_utc = str(envelope.get("ts_utc") or "").strip()
                payload_hash = str(payload.get("payload_hash") or "").strip()
                if not event_id or not ts_utc or not payload_hash:
                    continue
                rows.append(
                    {
                        "topic": topic,
                        "partition": int(partition),
                        "offset_kind": offset_kind,
                        "offset": offset,
                        "event_id": event_id,
                        "ts_utc": ts_utc,
                        "payload_hash": payload_hash,
                        "payload": _mapping_or_empty(envelope.get("payload")),
                    }
                )
        rows.sort(key=lambda item: (_int_or_none(item.get("partition")) or 0, _int_or_none(item.get("offset")) or 0, str(item.get("event_id") or "")))
        return rows

    def _request_platform_run_id(self, payload: Mapping[str, Any]) -> str:
        return _required_text(payload.get("platform_run_id"), "REQUEST_INVALID", "platform_run_id")

    def _read_json_ref(self, ref: str) -> dict[str, Any]:
        text = str(ref or "").strip()
        if not text:
            raise _RequestError("REF_INVALID", "empty ref")
        parsed = urlparse(text)
        if parsed.scheme == "s3":
            root = str(self.config.object_store_root or "").strip()
            root_parsed = urlparse(root) if root.startswith("s3://") else None
            if root_parsed and root_parsed.netloc == parsed.netloc:
                prefix = root_parsed.path.lstrip("/").rstrip("/")
                key = parsed.path.lstrip("/")
                relative = key
                if prefix:
                    marker = f"{prefix}/"
                    if not key.startswith(marker):
                        raise _RequestError("REF_SCOPE_INVALID", "s3 ref is outside configured object store prefix")
                    relative = key[len(marker) :]
                return self.store.read_json(relative)
            s3_store = S3ObjectStore(
                bucket=parsed.netloc,
                prefix="",
                endpoint_url=self.config.object_store_endpoint,
                region_name=self.config.object_store_region,
                path_style=self.config.object_store_path_style,
            )
            return s3_store.read_json(parsed.path.lstrip("/"))
        path = Path(text)
        if path.is_absolute() and path.exists():
            return _load_json_mapping(path)
        return self.store.read_json(text)

    def _receipt(
        self,
        *,
        request_id: str,
        command: str,
        platform_run_id: str,
        status: str,
        started_at_utc: str,
        completed_at_utc: str,
        request_ref: str,
        run_key: str | None = None,
        refs: Mapping[str, Any] | None = None,
        details: Mapping[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "learning.ofs_job_invocation_receipt.v0",
            "request_id": request_id,
            "command": command,
            "platform_run_id": platform_run_id,
            "status": status,
            "started_at_utc": started_at_utc,
            "completed_at_utc": completed_at_utc,
            "request_ref": request_ref,
            "stream_id": self.config.stream_id,
            "launcher_policy": {
                "policy_id": self.config.launcher_policy_id,
                "revision": self.config.launcher_policy_revision,
            },
            "service_release_id": self.config.service_release_id,
            "run_config_digest": self.config.run_config_digest,
        }
        if run_key:
            payload["run_key"] = run_key
        if refs:
            payload["refs"] = _normalize_mapping(dict(refs))
        if details:
            payload["details"] = _normalize_mapping(dict(details))
        if error_code:
            payload["error"] = {
                "code": str(error_code),
                "message": str(error_message or error_code),
            }
        return _normalize_mapping(payload)

def load_worker_config(profile_path: Path) -> OfsWorkerConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("OFS_PROFILE_INVALID")

    profile_id = str(payload.get("profile_id") or "local").strip() or "local"
    top_wiring = payload.get("wiring") if isinstance(payload.get("wiring"), Mapping) else {}
    object_store = top_wiring.get("object_store") if isinstance(top_wiring.get("object_store"), Mapping) else {}

    ofs_payload = payload.get("ofs") if isinstance(payload.get("ofs"), Mapping) else {}
    ofs_policy = ofs_payload.get("policy") if isinstance(ofs_payload.get("policy"), Mapping) else {}
    ofs_wiring = ofs_payload.get("wiring") if isinstance(ofs_payload.get("wiring"), Mapping) else {}

    policy_ref = Path(str(_env(ofs_policy.get("launcher_policy_ref") or "config/platform/ofs/launcher_policy_v0.yaml")))
    launcher_policy = _load_launcher_policy(policy_ref)

    platform_run_id = _platform_run_id()
    required_platform_run_id = _none_if_blank(
        _env(
            ofs_wiring.get("required_platform_run_id")
            or os.getenv("OFS_REQUIRED_PLATFORM_RUN_ID")
            or platform_run_id
        )
    )
    stream_id = str(_env(ofs_wiring.get("stream_id") or "ofs.v0")).strip() or "ofs.v0"
    if required_platform_run_id and "::" not in stream_id:
        stream_id = f"{stream_id}::{required_platform_run_id}"

    object_store_root = str(
        _env(
            ofs_wiring.get("object_store_root")
            or os.getenv("PLATFORM_STORE_ROOT")
            or object_store.get("root")
            or "runs/fraud-platform"
        )
    ).strip()
    if profile_id == "local_parity" and not object_store_root.startswith("s3://"):
        raise RuntimeError("OFS_OBJECT_STORE_ROOT_INVALID_LOCAL_PARITY")

    run_ledger_locator = _resolve_run_ledger_locator(profile_id, ofs_wiring.get("run_ledger_locator"), "ofs/run_ledger.sqlite")
    label_store_locator = _resolve_label_store_locator(ofs_wiring.get("label_store_locator") or os.getenv("LABEL_STORE_LOCATOR"), "label_store/writer.sqlite")

    feature_profile_ref = str(
        _env(
            ofs_wiring.get("feature_profile_ref")
            or ((payload.get("ofp") or {}).get("policy") or {}).get("features_ref")
            or "config/platform/ofp/features_v0.yaml"
        )
    ).strip()

    request_prefix = str(_env(ofs_wiring.get("request_prefix") or "")).strip()
    if not request_prefix:
        if required_platform_run_id:
            request_prefix = f"{required_platform_run_id}/ofs/job_requests"
        elif platform_run_id:
            request_prefix = f"{platform_run_id}/ofs/job_requests"
        else:
            request_prefix = "ofs/job_requests"

    object_store_endpoint = _none_if_blank(_env(ofs_wiring.get("object_store_endpoint") or object_store.get("endpoint")))
    object_store_region = _none_if_blank(_env(ofs_wiring.get("object_store_region") or object_store.get("region")))
    object_store_path_style = _bool_env(_env(ofs_wiring.get("object_store_path_style") or object_store.get("path_style") or "true"))

    replay_eb_observations_ref = _none_if_blank(_env(ofs_wiring.get("replay_eb_observations_ref")))
    replay_archive_observations_ref = _none_if_blank(_env(ofs_wiring.get("replay_archive_observations_ref")))
    replay_discover_archive_events = _bool_env(_env(ofs_wiring.get("replay_discover_archive_events") or "true"))
    require_complete_for_dataset_build = _bool_env(_env(ofs_wiring.get("require_complete_for_dataset_build") or "true"))

    service_release_id = (
        _none_if_blank(
            _env(
                ofs_wiring.get("service_release_id")
                or os.getenv("OFS_CODE_RELEASE_ID")
                or os.getenv("SERVICE_RELEASE_ID")
            )
        )
        or "unknown"
    )

    max_publish_retry_attempts = _int_or_default(
        _env(ofs_wiring.get("max_publish_retry_attempts")),
        default=launcher_policy.max_publish_retry_attempts,
        minimum=1,
    )
    request_poll_seconds = _float_or_default(
        _env(ofs_wiring.get("request_poll_seconds")),
        default=launcher_policy.request_poll_seconds,
        minimum=0.1,
    )
    request_batch_limit = _int_or_default(
        _env(ofs_wiring.get("request_batch_limit")),
        default=launcher_policy.request_batch_limit,
        minimum=1,
    )

    run_config_digest = _run_config_digest(
        profile_payload=payload,
        profile_text=profile_path.read_text(encoding="utf-8"),
        launcher_policy=launcher_policy,
        launcher_policy_text=policy_ref.read_text(encoding="utf-8"),
        stream_id=stream_id,
        required_platform_run_id=required_platform_run_id,
        run_ledger_locator=run_ledger_locator,
        object_store_root=object_store_root,
        feature_profile_ref=feature_profile_ref,
        service_release_id=service_release_id,
    )

    return OfsWorkerConfig(
        profile_path=profile_path,
        policy_ref=policy_ref,
        profile_id=profile_id,
        stream_id=stream_id,
        platform_run_id=platform_run_id,
        required_platform_run_id=required_platform_run_id,
        run_ledger_locator=run_ledger_locator,
        object_store_root=object_store_root,
        object_store_endpoint=object_store_endpoint,
        object_store_region=object_store_region,
        object_store_path_style=object_store_path_style,
        request_prefix=request_prefix,
        request_poll_seconds=request_poll_seconds,
        request_batch_limit=request_batch_limit,
        max_publish_retry_attempts=max_publish_retry_attempts,
        feature_profile_ref=feature_profile_ref,
        label_store_locator=label_store_locator,
        replay_eb_observations_ref=replay_eb_observations_ref,
        replay_archive_observations_ref=replay_archive_observations_ref,
        replay_discover_archive_events=replay_discover_archive_events,
        require_complete_for_dataset_build=require_complete_for_dataset_build,
        service_release_id=service_release_id,
        launcher_policy_id=launcher_policy.policy_id,
        launcher_policy_revision=launcher_policy.revision,
        run_config_digest=run_config_digest,
    )


def enqueue_build_request(
    *,
    config: OfsWorkerConfig,
    intent_path: Path,
    replay_events_path: Path | None,
    target_subjects_path: Path | None,
    replay_evidence_path: Path | None,
    supersedes_manifest_refs: Sequence[str],
    backfill_reason: str | None,
    request_id_override: str | None,
) -> str:
    intent_payload = _load_json_mapping(intent_path)
    intent = OfsBuildIntent.from_payload(intent_payload)
    _ensure_run_scope(config, intent.platform_run_id)

    inputs: dict[str, Any] = {}
    if replay_events_path is not None:
        replay_events_payload = json.loads(replay_events_path.read_text(encoding="utf-8"))
        rows = replay_events_payload if isinstance(replay_events_payload, list) else replay_events_payload.get("replay_events")
        if not isinstance(rows, list):
            raise RuntimeError("OFS_REPLAY_EVENTS_INVALID")
        inputs["replay_events"] = rows
    if target_subjects_path is not None:
        target_subjects_payload = json.loads(target_subjects_path.read_text(encoding="utf-8"))
        rows = target_subjects_payload if isinstance(target_subjects_payload, list) else target_subjects_payload.get("target_subjects")
        if not isinstance(rows, list):
            raise RuntimeError("OFS_TARGET_SUBJECTS_INVALID")
        inputs["target_subjects"] = rows
    if replay_evidence_path is not None:
        replay_evidence_payload = json.loads(replay_evidence_path.read_text(encoding="utf-8"))
        rows = replay_evidence_payload if isinstance(replay_evidence_payload, list) else replay_evidence_payload.get("observations")
        if not isinstance(rows, list):
            raise RuntimeError("OFS_REPLAY_EVIDENCE_INVALID")
        inputs["replay_evidence"] = {"observations": rows}

    supersedes = sorted({str(item).strip() for item in supersedes_manifest_refs if str(item).strip()})
    if supersedes:
        inputs["supersedes_manifest_refs"] = supersedes
    if _none_if_blank(backfill_reason):
        inputs["backfill_reason"] = str(backfill_reason).strip()

    request_id = _none_if_blank(request_id_override) or intent.request_id
    if not request_id:
        raise RuntimeError("OFS_REQUEST_ID_REQUIRED")
    request_payload = _normalize_mapping(
        {
            "schema_version": _REQUEST_SCHEMA,
            "request_id": request_id,
            "command": _DATASET_BUILD,
            "platform_run_id": intent.platform_run_id,
            "submitted_at_utc": _utc_now(),
            "run_config_digest": config.run_config_digest,
            "intent": intent_payload,
            "inputs": inputs,
        }
    )
    store = build_object_store(
        root=config.object_store_root,
        s3_endpoint_url=config.object_store_endpoint,
        s3_region=config.object_store_region,
        s3_path_style=config.object_store_path_style,
    )
    artifact = store.write_json_if_absent(_request_relative_path(intent.platform_run_id, request_id), request_payload)
    return str(artifact.path)


def enqueue_publish_retry_request(
    *,
    config: OfsWorkerConfig,
    run_key: str,
    platform_run_id: str,
    intent_path: Path,
    draft_path: Path,
    replay_receipt_path: Path,
    label_receipt_path: Path | None,
    supersedes_manifest_refs: Sequence[str],
    backfill_reason: str | None,
    request_id_override: str | None,
) -> str:
    _ensure_run_scope(config, platform_run_id)
    intent_payload = _load_json_mapping(intent_path)
    intent = OfsBuildIntent.from_payload(intent_payload)
    if intent.platform_run_id != platform_run_id:
        raise RuntimeError("OFS_PUBLISH_RETRY_SCOPE_INVALID")

    publish_inputs: dict[str, Any] = {
        "intent": intent_payload,
        "draft": _load_json_mapping(draft_path),
        "replay_receipt": _load_json_mapping(replay_receipt_path),
    }
    if label_receipt_path is not None:
        publish_inputs["label_receipt"] = _load_json_mapping(label_receipt_path)
    supersedes = sorted({str(item).strip() for item in supersedes_manifest_refs if str(item).strip()})
    if supersedes:
        publish_inputs["supersedes_manifest_refs"] = supersedes
    if _none_if_blank(backfill_reason):
        publish_inputs["backfill_reason"] = str(backfill_reason).strip()

    request_id = _none_if_blank(request_id_override) or f"ofs.publish_retry.{run_key}.{_utc_compact()}"
    request_payload = _normalize_mapping(
        {
            "schema_version": _REQUEST_SCHEMA,
            "request_id": request_id,
            "command": _PUBLISH_RETRY,
            "platform_run_id": platform_run_id,
            "submitted_at_utc": _utc_now(),
            "run_config_digest": config.run_config_digest,
            "run_key": run_key,
            "publish_inputs": publish_inputs,
        }
    )
    store = build_object_store(
        root=config.object_store_root,
        s3_endpoint_url=config.object_store_endpoint,
        s3_region=config.object_store_region,
        s3_path_style=config.object_store_path_style,
    )
    artifact = store.write_json_if_absent(_request_relative_path(platform_run_id, request_id), request_payload)
    return str(artifact.path)

def _load_launcher_policy(path: Path) -> OfsLauncherPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("OFS_LAUNCHER_POLICY_INVALID")
    launcher = payload.get("launcher") if isinstance(payload.get("launcher"), Mapping) else {}
    return OfsLauncherPolicy(
        policy_id=str(payload.get("policy_id") or "ofs.launcher.v0").strip() or "ofs.launcher.v0",
        revision=str(payload.get("revision") or "r1").strip() or "r1",
        max_publish_retry_attempts=_int_or_default(launcher.get("max_publish_retry_attempts"), default=3, minimum=1),
        request_poll_seconds=_float_or_default(launcher.get("request_poll_seconds"), default=2.0, minimum=0.1),
        request_batch_limit=_int_or_default(launcher.get("request_batch_limit"), default=20, minimum=1),
    )


def _run_config_digest(
    *,
    profile_payload: Mapping[str, Any],
    profile_text: str,
    launcher_policy: OfsLauncherPolicy,
    launcher_policy_text: str,
    stream_id: str,
    required_platform_run_id: str | None,
    run_ledger_locator: str,
    object_store_root: str,
    feature_profile_ref: str,
    service_release_id: str,
) -> str:
    payload = {
        "recipe": "ofs.phase8.run_config_digest.v1",
        "profile": {
            "profile_id": str(profile_payload.get("profile_id") or ""),
            "digest": _sha256_text(profile_text),
        },
        "policy": {
            "policy_id": launcher_policy.policy_id,
            "revision": launcher_policy.revision,
            "digest": _sha256_text(launcher_policy_text),
        },
        "wiring": {
            "stream_id": stream_id,
            "required_platform_run_id": required_platform_run_id,
            "run_ledger_locator": run_ledger_locator,
            "object_store_root": object_store_root,
            "feature_profile_ref": feature_profile_ref,
            "service_release_id": service_release_id,
        },
    }
    return _sha256_payload(payload)


def _resolve_run_ledger_locator(profile_id: str, raw_value: Any, suffix: str) -> str:
    raw = str(_env(raw_value) or "").strip()
    if raw:
        if not raw.startswith("postgres://") and not raw.startswith("postgresql://") and not raw.startswith("s3://"):
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
        return raw
    if profile_id == "local_parity":
        raise RuntimeError("OFS_RUN_LEDGER_LOCATOR_MISSING_LOCAL_PARITY")
    resolved = resolve_run_scoped_path(None, suffix=suffix, create_if_missing=True)
    if not resolved:
        raise RuntimeError("OFS_RUN_LEDGER_LOCATOR_MISSING")
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def _resolve_label_store_locator(raw_value: Any, suffix: str) -> str:
    raw = str(_env(raw_value) or "").strip()
    if raw:
        if not raw.startswith("postgres://") and not raw.startswith("postgresql://") and not raw.startswith("s3://"):
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
        return raw
    resolved = resolve_run_scoped_path(None, suffix=suffix, create_if_missing=True)
    if not resolved:
        raise RuntimeError("OFS_LABEL_STORE_LOCATOR_MISSING")
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def _load_replay_evidence(inputs: Mapping[str, Any]) -> ReplayBasisEvidence | None:
    replay_evidence = inputs.get("replay_evidence")
    if replay_evidence is None:
        return None
    return ReplayBasisEvidence.from_payload(_mapping(replay_evidence, "REQUEST_INVALID", "inputs.replay_evidence"))


def _load_replay_events(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = inputs.get("replay_events")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise _RequestError("REQUEST_INVALID", "inputs.replay_events must be a list")
    return [_normalize_mapping(_mapping(item, "REQUEST_INVALID", "inputs.replay_events[]")) for item in rows]


def _load_target_subjects(inputs: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = inputs.get("target_subjects")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise _RequestError("REQUEST_INVALID", "inputs.target_subjects must be a list")
    normalized: list[dict[str, str]] = []
    for item in rows:
        row = _mapping(item, "REQUEST_INVALID", "inputs.target_subjects[]")
        normalized.append(
            {
                "platform_run_id": _required_text(row.get("platform_run_id"), "REQUEST_INVALID", "target_subjects[].platform_run_id"),
                "event_id": _required_text(row.get("event_id"), "REQUEST_INVALID", "target_subjects[].event_id"),
            }
        )
    return normalized


def _target_subjects_from_replay_events(platform_run_id: str, replay_events: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    subjects: dict[str, dict[str, str]] = {}
    for event in replay_events:
        event_id = _none_if_blank(event.get("event_id"))
        if event_id:
            subjects[event_id] = {"platform_run_id": platform_run_id, "event_id": event_id}
    return [subjects[key] for key in sorted(subjects)]


def _dataset_draft_from_payload(payload: Mapping[str, Any]) -> OfsDatasetDraft:
    rows: list[OfsFeatureDraftRow] = []
    for item in _list_or_empty(payload.get("rows")):
        row = _mapping(item, "REQUEST_INVALID", "publish_inputs.draft.rows[]")
        rows.append(
            OfsFeatureDraftRow(
                row_id=_required_text(row.get("row_id"), "REQUEST_INVALID", "draft.rows[].row_id"),
                platform_run_id=_required_text(row.get("platform_run_id"), "REQUEST_INVALID", "draft.rows[].platform_run_id"),
                event_id=_required_text(row.get("event_id"), "REQUEST_INVALID", "draft.rows[].event_id"),
                ts_utc=_required_text(row.get("ts_utc"), "REQUEST_INVALID", "draft.rows[].ts_utc"),
                topic=_required_text(row.get("topic"), "REQUEST_INVALID", "draft.rows[].topic"),
                partition=int(_required_text(row.get("partition"), "REQUEST_INVALID", "draft.rows[].partition")),
                offset_kind=_required_text(row.get("offset_kind"), "REQUEST_INVALID", "draft.rows[].offset_kind"),
                offset=_required_text(row.get("offset"), "REQUEST_INVALID", "draft.rows[].offset"),
                payload_hash=_required_text(row.get("payload_hash"), "REQUEST_INVALID", "draft.rows[].payload_hash"),
                feature_values=_mapping_or_empty(row.get("feature_values")),
            )
        )
    return OfsDatasetDraft(
        run_key=_required_text(payload.get("run_key"), "REQUEST_INVALID", "publish_inputs.draft.run_key"),
        request_id=_required_text(payload.get("request_id"), "REQUEST_INVALID", "publish_inputs.draft.request_id"),
        intent_kind=_required_text(payload.get("intent_kind"), "REQUEST_INVALID", "publish_inputs.draft.intent_kind"),
        platform_run_id=_required_text(payload.get("platform_run_id"), "REQUEST_INVALID", "publish_inputs.draft.platform_run_id"),
        generated_at_utc=_required_text(payload.get("generated_at_utc"), "REQUEST_INVALID", "publish_inputs.draft.generated_at_utc"),
        feature_profile=_mapping_or_empty(payload.get("feature_profile")),
        row_order_rules=tuple(str(item) for item in _list_or_empty(payload.get("row_order_rules"))),
        dedupe_stats={k: int(v) for k, v in _mapping_or_empty(payload.get("dedupe_stats")).items()},
        replay_status=_none_if_blank(payload.get("replay_status")),
        label_status=_none_if_blank(payload.get("label_status")),
        rows=tuple(rows),
        rows_digest=_required_text(payload.get("rows_digest"), "REQUEST_INVALID", "publish_inputs.draft.rows_digest"),
        parity_hash=_none_if_blank(payload.get("parity_hash")),
    )


def _ensure_run_scope(config: OfsWorkerConfig, platform_run_id: str) -> None:
    if config.required_platform_run_id and platform_run_id != config.required_platform_run_id:
        raise RuntimeError(f"OFS_RUN_SCOPE_INVALID:{platform_run_id}:{config.required_platform_run_id}")


def _request_relative_path(platform_run_id: str, request_id: str) -> str:
    return f"{platform_run_id}/ofs/job_requests/{_safe_token(request_id)}.json"


def _receipt_relative_path(platform_run_id: str, request_id: str) -> str:
    return f"{platform_run_id}/ofs/job_invocations/{_safe_token(request_id)}.json"


def _artifact_ref(config: OfsWorkerConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


def _safe_token(value: str) -> str:
    return _SAFE_TOKEN.sub("_", str(value or "").strip() or "_")


def _load_json_mapping(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError(f"JSON_MAPPING_REQUIRED:{path}")
    return dict(payload)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _utc_compact() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str))


def _required_text(value: Any, code: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise _RequestError(code, f"{field_name} is required")
    return text


def _mapping(value: Any, code: str, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _RequestError(code, f"{field_name} must be a mapping")
    return dict(value)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_or_default(value: Any, *, default: int, minimum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(minimum, parsed)


def _float_or_default(value: Any, *, default: float, minimum: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = float(default)
    return max(minimum, parsed)


def _bool_env(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(value)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _compact_reason(exc: Exception) -> str:
    compact = _safe_token(f"{exc.__class__.__name__}:{str(exc)[:120]}")
    return compact[:180] or "ERROR"


def _env(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    token = value.strip()
    match = _ENV_PATTERN.fullmatch(token)
    if not match:
        return value
    return os.getenv(match.group(1), match.group(2) or "")


def _platform_run_id() -> str | None:
    explicit = (os.getenv("ACTIVE_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID") or "").strip()
    if explicit:
        return explicit
    return resolve_platform_run_id(create_if_missing=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="OFS worker + launcher")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Run OFS worker")
    run_cmd.add_argument("--once", action="store_true", help="Process one poll cycle then exit")

    enqueue_build_cmd = sub.add_parser("enqueue-build", help="Enqueue dataset_build request")
    enqueue_build_cmd.add_argument("--intent-path", required=True)
    enqueue_build_cmd.add_argument("--replay-events-path")
    enqueue_build_cmd.add_argument("--target-subjects-path")
    enqueue_build_cmd.add_argument("--replay-evidence-path")
    enqueue_build_cmd.add_argument("--supersedes-manifest-ref", action="append", default=[])
    enqueue_build_cmd.add_argument("--backfill-reason")
    enqueue_build_cmd.add_argument("--request-id")

    enqueue_retry_cmd = sub.add_parser("enqueue-publish-retry", help="Enqueue publish-only retry request")
    enqueue_retry_cmd.add_argument("--run-key", required=True)
    enqueue_retry_cmd.add_argument("--platform-run-id", required=True)
    enqueue_retry_cmd.add_argument("--intent-path", required=True)
    enqueue_retry_cmd.add_argument("--draft-path", required=True)
    enqueue_retry_cmd.add_argument("--replay-receipt-path", required=True)
    enqueue_retry_cmd.add_argument("--label-receipt-path")
    enqueue_retry_cmd.add_argument("--supersedes-manifest-ref", action="append", default=[])
    enqueue_retry_cmd.add_argument("--backfill-reason")
    enqueue_retry_cmd.add_argument("--request-id")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    config = load_worker_config(Path(args.profile))

    if args.command == "run":
        worker = OfsJobWorker(config)
        if args.once:
            processed = worker.run_once()
            logger.info("OFS worker processed=%s", processed)
            return
        worker.run_forever()
        return
    if args.command == "enqueue-build":
        request_ref = enqueue_build_request(
            config=config,
            intent_path=Path(args.intent_path),
            replay_events_path=Path(args.replay_events_path) if args.replay_events_path else None,
            target_subjects_path=Path(args.target_subjects_path) if args.target_subjects_path else None,
            replay_evidence_path=Path(args.replay_evidence_path) if args.replay_evidence_path else None,
            supersedes_manifest_refs=tuple(args.supersedes_manifest_ref or ()),
            backfill_reason=args.backfill_reason,
            request_id_override=args.request_id,
        )
        print(json.dumps({"request_ref": request_ref}, sort_keys=True, ensure_ascii=True))
        return
    if args.command == "enqueue-publish-retry":
        request_ref = enqueue_publish_retry_request(
            config=config,
            run_key=str(args.run_key),
            platform_run_id=str(args.platform_run_id),
            intent_path=Path(args.intent_path),
            draft_path=Path(args.draft_path),
            replay_receipt_path=Path(args.replay_receipt_path),
            label_receipt_path=Path(args.label_receipt_path) if args.label_receipt_path else None,
            supersedes_manifest_refs=tuple(args.supersedes_manifest_ref or ()),
            backfill_reason=args.backfill_reason,
            request_id_override=args.request_id,
        )
        print(json.dumps({"request_ref": request_ref}, sort_keys=True, ensure_ascii=True))
        return


if __name__ == "__main__":
    main()
