"""MF Phase 8 run/operate worker and launcher CLI."""

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
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml

from fraud_detection.platform_runtime import resolve_platform_run_id, resolve_run_scoped_path
from fraud_detection.scenario_runner.storage import S3ObjectStore, build_object_store

from .contracts import MfTrainBuildRequest
from .phase3 import (
    MfPhase3ResolverError,
    MfTrainPlanResolver,
    MfTrainPlanResolverConfig,
    ResolvedDatasetManifest,
    ResolvedGovernanceProfile,
    ResolvedTrainingProfile,
    ResolvedTrainPlan,
)
from .phase4 import MfPhase4ExecutionError, MfTrainEvalExecutor, MfTrainEvalExecutorConfig
from .phase5 import (
    MfGatePolicyConfig,
    MfGatePolicyEvaluator,
    MfGateReceipt,
    MfPhase5GateError,
    MfPhase5PolicyResult,
    MfPublishEligibilityReceipt,
)
from .phase6 import MfBundlePublisher, MfBundlePublisherConfig, MfPhase6PublishError
from .run_control import MfRunControl, MfRunControlPolicy
from .run_ledger import MfRunLedger, MfRunLedgerError

logger = logging.getLogger("fraud_detection.model_factory.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9_.:-]+")

_REQUEST_SCHEMA = "learning.mf_job_request.v0"
_TRAIN_BUILD = "train_build"
_PUBLISH_RETRY = "publish_retry"


@dataclass(frozen=True)
class _RequestError(RuntimeError):
    code: str
    message: str

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, f"{self.code}:{self.message}")


@dataclass(frozen=True)
class MfLauncherPolicy:
    policy_id: str
    revision: str
    max_publish_retry_attempts: int
    request_poll_seconds: float
    request_batch_limit: int


@dataclass(frozen=True)
class MfWorkerConfig:
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
    service_release_id: str
    launcher_policy_id: str
    launcher_policy_revision: str
    run_config_digest: str


class MfJobWorker:
    def __init__(self, config: MfWorkerConfig) -> None:
        self.config = config
        self.store = build_object_store(
            root=config.object_store_root,
            s3_endpoint_url=config.object_store_endpoint,
            s3_region=config.object_store_region,
            s3_path_style=config.object_store_path_style,
        )
        self.ledger = MfRunLedger(locator=config.run_ledger_locator)
        self.control = MfRunControl(
            ledger=self.ledger,
            policy=MfRunControlPolicy(max_publish_retry_attempts=config.max_publish_retry_attempts),
        )

    def run_once(self) -> int:
        processed = 0
        for request_ref in sorted(self.store.list_files(self.config.request_prefix)):
            request_payload = self._read_json_ref(request_ref)
            request_id = _required_text(request_payload.get("request_id"), "REQUEST_INVALID", "request_id")
            platform_run_id = self._request_platform_run_id(request_payload)
            receipt_rel = _receipt_relative_path(platform_run_id, request_id)
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
            if command == _TRAIN_BUILD:
                result = self._execute_train_build(request_payload)
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
        except (MfRunLedgerError, MfPhase3ResolverError, MfPhase4ExecutionError, MfPhase5GateError, MfPhase6PublishError) as exc:
            code = str(getattr(exc, "code", "WORKER_RUNTIME_ERROR") or "WORKER_RUNTIME_ERROR")
            message = str(getattr(exc, "message", str(exc)) or str(exc))
            return self._receipt(
                request_id=request_id,
                command=command,
                platform_run_id=platform_run_id,
                status="FAILED",
                started_at_utc=started,
                completed_at_utc=_utc_now(),
                request_ref=request_ref,
                error_code=code,
                error_message=message[:500],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("MF worker request failed request_id=%s", request_id)
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

    def _execute_train_build(self, request_payload: Mapping[str, Any]) -> dict[str, Any]:
        request_contract = MfTrainBuildRequest.from_payload(
            _mapping(request_payload.get("request"), "REQUEST_INVALID", "request")
        )
        request_run_id = self._request_platform_run_id(request_payload)
        if request_contract.platform_run_id != request_run_id:
            raise _RequestError("RUN_SCOPE_INVALID", "request platform_run_id does not match train build payload")

        submitted = self.control.enqueue(request=request_contract, queued_at_utc=_utc_now())
        run_key = submitted.run_key
        submission_outcome = str(submitted.outcome).upper()
        if submission_outcome == "DUPLICATE":
            prior = submitted.receipt
            prior_status = str(prior.status).upper()
            if prior_status in {"PUBLISHED", "PASS", "FAIL", "PUBLISH_PENDING"}:
                return {
                    "status": f"ALREADY_{prior_status}",
                    "run_key": run_key,
                    "refs": {
                        "eval_report_ref": str(prior.eval_report_ref or ""),
                        "gate_receipt_ref": str(prior.gate_receipt_ref or ""),
                        "bundle_publication_ref": str(prior.bundle_publication_ref or ""),
                    },
                    "details": {"submission_outcome": submission_outcome},
                }

        started_at = _utc_now()
        self.control.start_full_run(run_key=run_key, started_at_utc=started_at)
        try:
            phase3 = MfTrainPlanResolver(
                config=MfTrainPlanResolverConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                )
            )
            plan = phase3.resolve(request=request_contract, run_key=run_key)
            plan_ref = phase3.emit_immutable(plan=plan)

            phase4 = MfTrainEvalExecutor(
                config=MfTrainEvalExecutorConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                )
            )
            execution_started = _none_if_blank(request_payload.get("execution_started_at_utc")) or started_at
            train_eval = phase4.execute(plan=plan, execution_started_at_utc=execution_started)
            train_eval_receipt_ref = _artifact_ref(self.config, train_eval.artifact_relative_path())
            self.control.mark_eval_ready(
                run_key=run_key,
                eval_ready_at_utc=_utc_now(),
                eval_report_ref=train_eval.eval_report_ref,
            )

            phase5 = MfGatePolicyEvaluator(
                config=MfGatePolicyConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                )
            )
            phase5_result = phase5.evaluate(plan=plan, train_eval_receipt=train_eval, evaluated_at_utc=_utc_now())
            if str(phase5_result.gate_receipt.gate_decision).upper() != "PASS":
                self.control.mark_failed(run_key=run_key, failed_at_utc=_utc_now(), reason_code="GATE_FAIL")
                return {
                    "status": "GATE_FAIL",
                    "run_key": run_key,
                    "refs": {
                        "resolved_train_plan_ref": plan_ref,
                        "train_eval_receipt_ref": train_eval_receipt_ref,
                        "eval_report_ref": train_eval.eval_report_ref,
                        "gate_receipt_ref": phase5_result.gate_receipt_ref,
                        "publish_eligibility_ref": phase5_result.publish_eligibility_ref,
                    },
                    "details": {"submission_outcome": submission_outcome},
                }

            self.control.mark_pass(
                run_key=run_key,
                passed_at_utc=_utc_now(),
                gate_receipt_ref=phase5_result.gate_receipt_ref,
            )
            if not bool(request_contract.publish_allowed):
                return {
                    "status": "PASS_NO_PUBLISH",
                    "run_key": run_key,
                    "refs": {
                        "resolved_train_plan_ref": plan_ref,
                        "train_eval_receipt_ref": train_eval_receipt_ref,
                        "eval_report_ref": train_eval.eval_report_ref,
                        "gate_receipt_ref": phase5_result.gate_receipt_ref,
                        "publish_eligibility_ref": phase5_result.publish_eligibility_ref,
                    },
                    "details": {"submission_outcome": submission_outcome},
                }

            phase6 = MfBundlePublisher(
                config=MfBundlePublisherConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                )
            )
            published_at = _none_if_blank(request_payload.get("published_at_utc")) or _utc_now()
            publish_result = phase6.publish(plan=plan, phase5_result=phase5_result, published_at_utc=published_at)
            self.control.mark_published(
                run_key=run_key,
                published_at_utc=published_at,
                bundle_publication_ref=publish_result.bundle_publication.bundle_publication_ref,
            )
            return {
                "status": "DONE",
                "run_key": run_key,
                "refs": {
                    "resolved_train_plan_ref": plan_ref,
                    "train_eval_receipt_ref": train_eval_receipt_ref,
                    "eval_report_ref": train_eval.eval_report_ref,
                    "gate_receipt_ref": phase5_result.gate_receipt_ref,
                    "publish_eligibility_ref": phase5_result.publish_eligibility_ref,
                    "bundle_publication_ref": publish_result.bundle_publication.bundle_publication_ref,
                    "publish_receipt_ref": publish_result.publish_receipt_ref,
                    "registry_bundle_ref": publish_result.publish_receipt.registry_bundle_ref,
                    "registry_lifecycle_event_ref": publish_result.publish_receipt.registry_lifecycle_event_ref,
                },
                "details": {
                    "submission_outcome": submission_outcome,
                    "publication_status": publish_result.publish_receipt.publication_status,
                },
            }
        except MfPhase6PublishError as exc:
            self.control.mark_publish_pending(
                run_key=run_key,
                pending_at_utc=_utc_now(),
                reason_code=f"PHASE6_{exc.code}",
            )
            return {
                "status": "PUBLISH_PENDING",
                "run_key": run_key,
                "error_code": exc.code,
                "error_message": exc.message,
                "details": {"submission_outcome": submission_outcome},
            }
        except Exception as exc:  # noqa: BLE001
            try:
                self.control.mark_failed(run_key=run_key, failed_at_utc=_utc_now(), reason_code=_compact_reason(exc))
            except Exception:
                logger.exception("MF mark_failed failed run_key=%s", run_key)
            raise

    def _execute_publish_retry(self, request_payload: Mapping[str, Any]) -> dict[str, Any]:
        run_key = _required_text(request_payload.get("run_key"), "REQUEST_INVALID", "run_key")
        requested_at = _utc_now()
        _, decision = self.control.start_publish_retry(
            run_key=run_key,
            requested_at_utc=requested_at,
            started_at_utc=requested_at,
        )
        platform_run_id = self._request_platform_run_id(request_payload)
        publish_inputs = _mapping_or_empty(request_payload.get("publish_inputs"))
        resolved_train_plan_ref = _none_if_blank(publish_inputs.get("resolved_train_plan_ref")) or _artifact_ref(
            self.config,
            _resolved_train_plan_relative_path(platform_run_id=platform_run_id, run_key=run_key),
        )
        gate_receipt_ref = _none_if_blank(publish_inputs.get("gate_receipt_ref")) or _artifact_ref(
            self.config,
            _gate_receipt_relative_path(platform_run_id=platform_run_id, run_key=run_key),
        )
        publish_eligibility_ref = _none_if_blank(publish_inputs.get("publish_eligibility_ref")) or _artifact_ref(
            self.config,
            _publish_eligibility_relative_path(platform_run_id=platform_run_id, run_key=run_key),
        )

        try:
            plan_payload = self._read_json_ref(resolved_train_plan_ref)
            gate_payload = self._read_json_ref(gate_receipt_ref)
            eligibility_payload = self._read_json_ref(publish_eligibility_ref)
            plan = _resolved_train_plan_from_payload(plan_payload)
            if plan.run_key != run_key or plan.platform_run_id != platform_run_id:
                raise _RequestError("RUN_SCOPE_INVALID", "publish retry plan scope mismatch")
            phase5_result = _phase5_result_from_payload(
                gate_payload=gate_payload,
                gate_receipt_ref=gate_receipt_ref,
                publish_eligibility_payload=eligibility_payload,
                publish_eligibility_ref=publish_eligibility_ref,
            )
            phase6 = MfBundlePublisher(
                config=MfBundlePublisherConfig(
                    object_store_root=self.config.object_store_root,
                    object_store_endpoint=self.config.object_store_endpoint,
                    object_store_region=self.config.object_store_region,
                    object_store_path_style=self.config.object_store_path_style,
                )
            )
            published_at = _none_if_blank(request_payload.get("published_at_utc")) or _utc_now()
            publish_result = phase6.publish(plan=plan, phase5_result=phase5_result, published_at_utc=published_at)
            self.control.mark_published(
                run_key=run_key,
                published_at_utc=published_at,
                bundle_publication_ref=publish_result.bundle_publication.bundle_publication_ref,
            )
            return {
                "status": "DONE",
                "run_key": run_key,
                "refs": {
                    "resolved_train_plan_ref": resolved_train_plan_ref,
                    "gate_receipt_ref": gate_receipt_ref,
                    "publish_eligibility_ref": publish_eligibility_ref,
                    "bundle_publication_ref": publish_result.bundle_publication.bundle_publication_ref,
                    "publish_receipt_ref": publish_result.publish_receipt_ref,
                    "registry_bundle_ref": publish_result.publish_receipt.registry_bundle_ref,
                    "registry_lifecycle_event_ref": publish_result.publish_receipt.registry_lifecycle_event_ref,
                },
                "details": {
                    "retry_decision": decision.decision,
                    "attempts_used": decision.attempts_used,
                    "publication_status": publish_result.publish_receipt.publication_status,
                },
            }
        except MfPhase6PublishError as exc:
            self.control.mark_publish_pending(
                run_key=run_key,
                pending_at_utc=_utc_now(),
                reason_code=f"PHASE6_{exc.code}",
            )
            return {
                "status": "PUBLISH_PENDING",
                "run_key": run_key,
                "error_code": exc.code,
                "error_message": exc.message,
                "details": {"retry_decision": decision.decision, "attempts_used": decision.attempts_used},
            }
        except Exception as exc:  # noqa: BLE001
            try:
                self.control.mark_publish_pending(
                    run_key=run_key,
                    pending_at_utc=_utc_now(),
                    reason_code=f"PUBLISH_RETRY_RUNTIME_{_compact_reason(exc)}",
                )
            except Exception:
                logger.exception("MF mark_publish_pending failed during retry run_key=%s", run_key)
            raise

    def _request_platform_run_id(self, request_payload: Mapping[str, Any]) -> str:
        return _required_text(request_payload.get("platform_run_id"), "REQUEST_INVALID", "platform_run_id")

    def _read_json_ref(self, ref: str) -> dict[str, Any]:
        value = _none_if_blank(ref)
        if not value:
            raise _RequestError("REQUEST_INVALID", "artifact ref is required")
        if value.startswith("s3://"):
            parsed = urlparse(value)
            s3_store = S3ObjectStore(
                parsed.netloc,
                prefix="",
                endpoint_url=self.config.object_store_endpoint,
                region_name=self.config.object_store_region,
                path_style=self.config.object_store_path_style,
            )
            return _mapping(s3_store.read_json(parsed.path.lstrip("/")), "REQUEST_INVALID", "artifact_ref")
        path = Path(value)
        try:
            if path.is_absolute():
                return _mapping(json.loads(path.read_text(encoding="utf-8")), "REQUEST_INVALID", "artifact_ref")
            return _mapping(self.store.read_json(value), "REQUEST_INVALID", "artifact_ref")
        except Exception as exc:  # noqa: BLE001
            raise _RequestError("EVIDENCE_UNRESOLVED", str(exc)) from exc

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
            "schema_version": "learning.mf_job_invocation_receipt.v0",
            "request_id": request_id,
            "command": command,
            "platform_run_id": platform_run_id,
            "status": status,
            "started_at_utc": started_at_utc,
            "completed_at_utc": completed_at_utc,
            "request_ref": request_ref,
            "run_config_digest": self.config.run_config_digest,
            "worker": {
                "stream_id": self.config.stream_id,
                "service_release_id": self.config.service_release_id,
                "launcher_policy_id": self.config.launcher_policy_id,
                "launcher_policy_revision": self.config.launcher_policy_revision,
            },
            "refs": dict(refs or {}),
            "details": dict(details or {}),
        }
        if run_key:
            payload["run_key"] = run_key
        if error_code or error_message:
            payload["error"] = {
                "code": str(error_code or "WORKER_RUNTIME_ERROR"),
                "message": str(error_message or "worker error"),
            }
        return _normalize_mapping(payload)


def load_worker_config(profile_path: Path) -> MfWorkerConfig:
    profile_text = profile_path.read_text(encoding="utf-8")
    profile_payload = yaml.safe_load(profile_text)
    if not isinstance(profile_payload, Mapping):
        raise RuntimeError("MF_PROFILE_INVALID")
    profile_id = str(profile_payload.get("profile_id") or "").strip() or "unknown"
    mf_block = _mapping(profile_payload.get("mf"), "MF_PROFILE_INVALID", "mf")
    policy_block = _mapping(mf_block.get("policy"), "MF_PROFILE_INVALID", "mf.policy")
    wiring_block = _mapping(mf_block.get("wiring"), "MF_PROFILE_INVALID", "mf.wiring")

    policy_ref_raw = _required_text(policy_block.get("launcher_policy_ref"), "MF_PROFILE_INVALID", "mf.policy.launcher_policy_ref")
    policy_ref = Path(str(_env(policy_ref_raw)))
    if not policy_ref.is_absolute() and not policy_ref.exists():
        policy_ref_from_profile = profile_path.parent / policy_ref
        if policy_ref_from_profile.exists():
            policy_ref = policy_ref_from_profile
    launcher_policy = _load_launcher_policy(policy_ref)
    launcher_policy_text = policy_ref.read_text(encoding="utf-8")

    stream_id = _required_text(_env(wiring_block.get("stream_id")), "MF_PROFILE_INVALID", "mf.wiring.stream_id")
    platform_run_id = _platform_run_id()
    required_platform_run_id = _none_if_blank(_env(wiring_block.get("required_platform_run_id"))) or platform_run_id

    object_store_root = _required_text(
        _env(wiring_block.get("object_store_root")),
        "MF_PROFILE_INVALID",
        "mf.wiring.object_store_root",
    )
    object_store_endpoint = _none_if_blank(_env(wiring_block.get("object_store_endpoint")))
    object_store_region = _none_if_blank(_env(wiring_block.get("object_store_region")))
    object_store_path_style = _bool_env(_env(wiring_block.get("object_store_path_style")))
    run_ledger_locator = _resolve_run_ledger_locator(
        profile_id=profile_id,
        raw_value=_env(wiring_block.get("run_ledger_locator")),
        suffix=f"{required_platform_run_id or 'default'}/learning/model_factory/mf_run_ledger.sqlite",
    )
    request_prefix = _none_if_blank(_env(wiring_block.get("request_prefix"))) or (
        f"{required_platform_run_id}/mf/job_requests" if required_platform_run_id else "mf/job_requests"
    )
    request_poll_seconds = _float_or_default(
        _env(wiring_block.get("request_poll_seconds")),
        default=launcher_policy.request_poll_seconds,
        minimum=0.1,
    )
    request_batch_limit = _int_or_default(
        _env(wiring_block.get("request_batch_limit")),
        default=launcher_policy.request_batch_limit,
        minimum=1,
    )
    max_publish_retry_attempts = _int_or_default(
        _env(wiring_block.get("max_publish_retry_attempts")),
        default=launcher_policy.max_publish_retry_attempts,
        minimum=1,
    )
    service_release_id = _none_if_blank(_env(wiring_block.get("service_release_id"))) or "git:local"

    run_config_digest = _run_config_digest(
        profile_payload=profile_payload,
        profile_text=profile_text,
        launcher_policy=launcher_policy,
        launcher_policy_text=launcher_policy_text,
        stream_id=stream_id,
        required_platform_run_id=required_platform_run_id,
        run_ledger_locator=run_ledger_locator,
        object_store_root=object_store_root,
        service_release_id=service_release_id,
    )

    return MfWorkerConfig(
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
        service_release_id=service_release_id,
        launcher_policy_id=launcher_policy.policy_id,
        launcher_policy_revision=launcher_policy.revision,
        run_config_digest=run_config_digest,
    )


def enqueue_train_build_request(
    *,
    config: MfWorkerConfig,
    request_path: Path,
    request_id_override: str | None,
) -> str:
    request_payload = _load_json_mapping(request_path)
    if _none_if_blank(request_id_override):
        request_payload["request_id"] = str(request_id_override).strip()
    request = MfTrainBuildRequest.from_payload(request_payload)
    _ensure_run_scope(config, request.platform_run_id)
    request_id = request.request_id
    envelope = _normalize_mapping(
        {
            "schema_version": _REQUEST_SCHEMA,
            "request_id": request_id,
            "command": _TRAIN_BUILD,
            "platform_run_id": request.platform_run_id,
            "submitted_at_utc": _utc_now(),
            "run_config_digest": config.run_config_digest,
            "request": request.as_dict(),
        }
    )
    store = build_object_store(
        root=config.object_store_root,
        s3_endpoint_url=config.object_store_endpoint,
        s3_region=config.object_store_region,
        s3_path_style=config.object_store_path_style,
    )
    artifact = store.write_json_if_absent(_request_relative_path(request.platform_run_id, request_id), envelope)
    return str(artifact.path)


def enqueue_publish_retry_request(
    *,
    config: MfWorkerConfig,
    run_key: str,
    platform_run_id: str,
    request_id_override: str | None,
    resolved_train_plan_ref: str | None,
    gate_receipt_ref: str | None,
    publish_eligibility_ref: str | None,
) -> str:
    _ensure_run_scope(config, platform_run_id)
    request_id = _none_if_blank(request_id_override) or f"mf.publish_retry.{run_key}.{_utc_compact()}"
    publish_inputs: dict[str, Any] = {}
    if _none_if_blank(resolved_train_plan_ref):
        publish_inputs["resolved_train_plan_ref"] = str(resolved_train_plan_ref).strip()
    if _none_if_blank(gate_receipt_ref):
        publish_inputs["gate_receipt_ref"] = str(gate_receipt_ref).strip()
    if _none_if_blank(publish_eligibility_ref):
        publish_inputs["publish_eligibility_ref"] = str(publish_eligibility_ref).strip()
    envelope = _normalize_mapping(
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
    artifact = store.write_json_if_absent(_request_relative_path(platform_run_id, request_id), envelope)
    return str(artifact.path)


def _load_launcher_policy(path: Path) -> MfLauncherPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("MF_LAUNCHER_POLICY_INVALID")
    launcher = payload.get("launcher") if isinstance(payload.get("launcher"), Mapping) else {}
    return MfLauncherPolicy(
        policy_id=str(payload.get("policy_id") or "mf.launcher.v0").strip() or "mf.launcher.v0",
        revision=str(payload.get("revision") or "r1").strip() or "r1",
        max_publish_retry_attempts=_int_or_default(launcher.get("max_publish_retry_attempts"), default=3, minimum=1),
        request_poll_seconds=_float_or_default(launcher.get("request_poll_seconds"), default=2.0, minimum=0.1),
        request_batch_limit=_int_or_default(launcher.get("request_batch_limit"), default=20, minimum=1),
    )


def _run_config_digest(
    *,
    profile_payload: Mapping[str, Any],
    profile_text: str,
    launcher_policy: MfLauncherPolicy,
    launcher_policy_text: str,
    stream_id: str,
    required_platform_run_id: str | None,
    run_ledger_locator: str,
    object_store_root: str,
    service_release_id: str,
) -> str:
    payload = {
        "recipe": "mf.phase8.run_config_digest.v1",
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
        raise RuntimeError("MF_RUN_LEDGER_LOCATOR_MISSING_LOCAL_PARITY")
    resolved = resolve_run_scoped_path(None, suffix=suffix, create_if_missing=True)
    if not resolved:
        raise RuntimeError("MF_RUN_LEDGER_LOCATOR_MISSING")
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def _phase5_result_from_payload(
    *,
    gate_payload: Mapping[str, Any],
    gate_receipt_ref: str,
    publish_eligibility_payload: Mapping[str, Any],
    publish_eligibility_ref: str,
) -> MfPhase5PolicyResult:
    gate_receipt = MfGateReceipt(
        run_key=_required_text(gate_payload.get("run_key"), "REQUEST_INVALID", "gate_receipt.run_key"),
        request_id=_required_text(gate_payload.get("request_id"), "REQUEST_INVALID", "gate_receipt.request_id"),
        platform_run_id=_required_text(gate_payload.get("platform_run_id"), "REQUEST_INVALID", "gate_receipt.platform_run_id"),
        evaluated_at_utc=_required_text(gate_payload.get("evaluated_at_utc"), "REQUEST_INVALID", "gate_receipt.evaluated_at_utc"),
        gate_decision=_required_text(gate_payload.get("gate_decision"), "REQUEST_INVALID", "gate_receipt.gate_decision"),
        eval_report_id=_required_text(gate_payload.get("eval_report_id"), "REQUEST_INVALID", "gate_receipt.eval_report_id"),
        eval_report_ref=_required_text(gate_payload.get("eval_report_ref"), "REQUEST_INVALID", "gate_receipt.eval_report_ref"),
        evidence_refs={str(k): str(v) for k, v in _mapping_or_empty(gate_payload.get("evidence_refs")).items()},
        gate_thresholds=_mapping_or_empty(gate_payload.get("gate_thresholds")),
    )
    eligibility = MfPublishEligibilityReceipt(
        run_key=_required_text(publish_eligibility_payload.get("run_key"), "REQUEST_INVALID", "publish_eligibility.run_key"),
        request_id=_required_text(publish_eligibility_payload.get("request_id"), "REQUEST_INVALID", "publish_eligibility.request_id"),
        platform_run_id=_required_text(
            publish_eligibility_payload.get("platform_run_id"),
            "REQUEST_INVALID",
            "publish_eligibility.platform_run_id",
        ),
        evaluated_at_utc=_required_text(
            publish_eligibility_payload.get("evaluated_at_utc"),
            "REQUEST_INVALID",
            "publish_eligibility.evaluated_at_utc",
        ),
        decision=_required_text(publish_eligibility_payload.get("decision"), "REQUEST_INVALID", "publish_eligibility.decision"),
        eligible=bool(publish_eligibility_payload.get("eligible")),
        reason_codes=tuple(str(item) for item in _list_or_empty(publish_eligibility_payload.get("reason_codes"))),
        gate_receipt_ref=_required_text(
            publish_eligibility_payload.get("gate_receipt_ref"),
            "REQUEST_INVALID",
            "publish_eligibility.gate_receipt_ref",
        ),
        eval_report_ref=_required_text(
            publish_eligibility_payload.get("eval_report_ref"),
            "REQUEST_INVALID",
            "publish_eligibility.eval_report_ref",
        ),
        required_evidence_refs={
            str(k): str(v)
            for k, v in _mapping_or_empty(publish_eligibility_payload.get("required_evidence_refs")).items()
        },
    )
    return MfPhase5PolicyResult(
        gate_receipt=gate_receipt,
        publish_eligibility=eligibility,
        gate_receipt_ref=gate_receipt_ref,
        publish_eligibility_ref=publish_eligibility_ref,
    )


def _resolved_train_plan_from_payload(payload: Mapping[str, Any]) -> ResolvedTrainPlan:
    dataset_manifests = []
    for item in _list_or_empty(payload.get("dataset_manifests")):
        row = _mapping(item, "REQUEST_INVALID", "resolved_train_plan.dataset_manifests[]")
        feature_def = _mapping(row.get("feature_definition_set"), "REQUEST_INVALID", "feature_definition_set")
        dataset_manifests.append(
            ResolvedDatasetManifest(
                manifest_ref=_required_text(row.get("manifest_ref"), "REQUEST_INVALID", "manifest_ref"),
                schema_version=_required_text(row.get("schema_version"), "REQUEST_INVALID", "schema_version"),
                dataset_manifest_id=_required_text(
                    row.get("dataset_manifest_id"),
                    "REQUEST_INVALID",
                    "dataset_manifest_id",
                ),
                dataset_fingerprint=_required_text(
                    row.get("dataset_fingerprint"),
                    "REQUEST_INVALID",
                    "dataset_fingerprint",
                ),
                platform_run_id=_required_text(row.get("platform_run_id"), "REQUEST_INVALID", "platform_run_id"),
                feature_set_id=_required_text(feature_def.get("feature_set_id"), "REQUEST_INVALID", "feature_set_id"),
                feature_set_version=_required_text(
                    feature_def.get("feature_set_version"),
                    "REQUEST_INVALID",
                    "feature_set_version",
                ),
                payload_digest=_required_text(row.get("payload_digest"), "REQUEST_INVALID", "payload_digest"),
            )
        )
    training_profile_payload = _mapping(payload.get("training_profile"), "REQUEST_INVALID", "training_profile")
    training_feature = _mapping(
        training_profile_payload.get("feature_definition_set"),
        "REQUEST_INVALID",
        "training_profile.feature_definition_set",
    )
    training_profile = ResolvedTrainingProfile(
        profile_ref=_required_text(training_profile_payload.get("profile_ref"), "REQUEST_INVALID", "training_profile.profile_ref"),
        policy_id=_required_text(training_profile_payload.get("policy_id"), "REQUEST_INVALID", "training_profile.policy_id"),
        revision=_required_text(training_profile_payload.get("revision"), "REQUEST_INVALID", "training_profile.revision"),
        feature_set_id=_required_text(training_feature.get("feature_set_id"), "REQUEST_INVALID", "training_profile.feature_set_id"),
        feature_set_version=_required_text(
            training_feature.get("feature_set_version"),
            "REQUEST_INVALID",
            "training_profile.feature_set_version",
        ),
        expected_manifest_schema_version=_required_text(
            training_profile_payload.get("expected_manifest_schema_version"),
            "REQUEST_INVALID",
            "training_profile.expected_manifest_schema_version",
        ),
        profile_digest=_required_text(training_profile_payload.get("profile_digest"), "REQUEST_INVALID", "training_profile.profile_digest"),
    )
    governance_profile_payload = _mapping(payload.get("governance_profile"), "REQUEST_INVALID", "governance_profile")
    governance_profile = ResolvedGovernanceProfile(
        profile_ref=_required_text(governance_profile_payload.get("profile_ref"), "REQUEST_INVALID", "governance_profile.profile_ref"),
        policy_id=_required_text(governance_profile_payload.get("policy_id"), "REQUEST_INVALID", "governance_profile.policy_id"),
        revision=_required_text(governance_profile_payload.get("revision"), "REQUEST_INVALID", "governance_profile.revision"),
        profile_digest=_required_text(governance_profile_payload.get("profile_digest"), "REQUEST_INVALID", "governance_profile.profile_digest"),
    )
    return ResolvedTrainPlan(
        run_key=_required_text(payload.get("run_key"), "REQUEST_INVALID", "resolved_train_plan.run_key"),
        request_id=_required_text(payload.get("request_id"), "REQUEST_INVALID", "resolved_train_plan.request_id"),
        intent_kind=_required_text(payload.get("intent_kind"), "REQUEST_INVALID", "resolved_train_plan.intent_kind"),
        platform_run_id=_required_text(
            payload.get("platform_run_id"),
            "REQUEST_INVALID",
            "resolved_train_plan.platform_run_id",
        ),
        dataset_manifests=tuple(dataset_manifests),
        training_profile=training_profile,
        governance_profile=governance_profile,
        input_refs={str(k): v for k, v in _mapping_or_empty(payload.get("input_refs")).items()},
    )


def _resolved_train_plan_relative_path(*, platform_run_id: str, run_key: str) -> str:
    return f"{platform_run_id}/mf/resolved_train_plan/{run_key}.json"


def _gate_receipt_relative_path(*, platform_run_id: str, run_key: str) -> str:
    return f"{platform_run_id}/mf/train_runs/{run_key}/gate/gate_receipt.json"


def _publish_eligibility_relative_path(*, platform_run_id: str, run_key: str) -> str:
    return f"{platform_run_id}/mf/train_runs/{run_key}/gate/publish_eligibility.json"


def _ensure_run_scope(config: MfWorkerConfig, platform_run_id: str) -> None:
    if config.required_platform_run_id and platform_run_id != config.required_platform_run_id:
        raise RuntimeError(f"MF_RUN_SCOPE_INVALID:{platform_run_id}:{config.required_platform_run_id}")


def _request_relative_path(platform_run_id: str, request_id: str) -> str:
    return f"{platform_run_id}/mf/job_requests/{_safe_token(request_id)}.json"


def _receipt_relative_path(platform_run_id: str, request_id: str) -> str:
    return f"{platform_run_id}/mf/job_invocations/{_safe_token(request_id)}.json"


def _artifact_ref(config: MfWorkerConfig, relative_path: str) -> str:
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
    parser = argparse.ArgumentParser(description="MF worker + launcher")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Run MF worker")
    run_cmd.add_argument("--once", action="store_true", help="Process one poll cycle then exit")

    enqueue_train_cmd = sub.add_parser("enqueue-train-build", help="Enqueue train_build request")
    enqueue_train_cmd.add_argument("--request-path", required=True)
    enqueue_train_cmd.add_argument("--request-id")

    enqueue_retry_cmd = sub.add_parser("enqueue-publish-retry", help="Enqueue publish-only retry request")
    enqueue_retry_cmd.add_argument("--run-key", required=True)
    enqueue_retry_cmd.add_argument("--platform-run-id", required=True)
    enqueue_retry_cmd.add_argument("--request-id")
    enqueue_retry_cmd.add_argument("--resolved-train-plan-ref")
    enqueue_retry_cmd.add_argument("--gate-receipt-ref")
    enqueue_retry_cmd.add_argument("--publish-eligibility-ref")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    config = load_worker_config(Path(args.profile))

    if args.command == "run":
        worker = MfJobWorker(config)
        if args.once:
            processed = worker.run_once()
            logger.info("MF worker processed=%s", processed)
            return
        worker.run_forever()
        return
    if args.command == "enqueue-train-build":
        request_ref = enqueue_train_build_request(
            config=config,
            request_path=Path(args.request_path),
            request_id_override=args.request_id,
        )
        print(json.dumps({"request_ref": request_ref}, sort_keys=True, ensure_ascii=True))
        return
    if args.command == "enqueue-publish-retry":
        request_ref = enqueue_publish_retry_request(
            config=config,
            run_key=str(args.run_key),
            platform_run_id=str(args.platform_run_id),
            request_id_override=args.request_id,
            resolved_train_plan_ref=args.resolved_train_plan_ref,
            gate_receipt_ref=args.gate_receipt_ref,
            publish_eligibility_ref=args.publish_eligibility_ref,
        )
        print(json.dumps({"request_ref": request_ref}, sort_keys=True, ensure_ascii=True))
        return


if __name__ == "__main__":
    main()
