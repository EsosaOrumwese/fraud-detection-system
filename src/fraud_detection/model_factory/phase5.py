"""MF Phase 5 gate receipt and publish-eligibility policy surfaces."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from fraud_detection.learning_registry.contracts import EvalReportContract
from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .phase3 import ResolvedTrainPlan
from .phase4 import MfTrainEvalReceipt


class MfPhase5GateError(ValueError):
    """Raised when MF Phase 5 gate and eligibility checks fail."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code or "").strip() or "UNKNOWN"
        self.message = str(message or "").strip() or self.code
        super().__init__(f"{self.code}:{self.message}")


@dataclass(frozen=True)
class MfGateReceipt:
    run_key: str
    request_id: str
    platform_run_id: str
    evaluated_at_utc: str
    gate_decision: str
    eval_report_id: str
    eval_report_ref: str
    evidence_refs: dict[str, str]
    gate_thresholds: dict[str, Any]

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/mf/train_runs/{self.run_key}/gate/gate_receipt.json"

    def as_dict(self) -> dict[str, Any]:
        return _normalize_mapping(
            {
                "schema_version": "learning.mf_gate_receipt.v0",
                "run_key": self.run_key,
                "request_id": self.request_id,
                "platform_run_id": self.platform_run_id,
                "evaluated_at_utc": self.evaluated_at_utc,
                "gate_decision": self.gate_decision,
                "eval_report_id": self.eval_report_id,
                "eval_report_ref": self.eval_report_ref,
                "evidence_refs": dict(self.evidence_refs),
                "gate_thresholds": dict(self.gate_thresholds),
            }
        )


@dataclass(frozen=True)
class MfPublishEligibilityReceipt:
    run_key: str
    request_id: str
    platform_run_id: str
    evaluated_at_utc: str
    decision: str
    eligible: bool
    reason_codes: tuple[str, ...]
    gate_receipt_ref: str
    eval_report_ref: str
    required_evidence_refs: dict[str, str]

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/mf/train_runs/{self.run_key}/gate/publish_eligibility.json"

    def as_dict(self) -> dict[str, Any]:
        return _normalize_mapping(
            {
                "schema_version": "learning.mf_publish_eligibility.v0",
                "run_key": self.run_key,
                "request_id": self.request_id,
                "platform_run_id": self.platform_run_id,
                "evaluated_at_utc": self.evaluated_at_utc,
                "decision": self.decision,
                "eligible": bool(self.eligible),
                "reason_codes": list(self.reason_codes),
                "gate_receipt_ref": self.gate_receipt_ref,
                "eval_report_ref": self.eval_report_ref,
                "required_evidence_refs": dict(self.required_evidence_refs),
            }
        )


@dataclass(frozen=True)
class MfPhase5PolicyResult:
    gate_receipt: MfGateReceipt
    publish_eligibility: MfPublishEligibilityReceipt
    gate_receipt_ref: str
    publish_eligibility_ref: str


@dataclass(frozen=True)
class MfGatePolicyConfig:
    object_store_root: str = "runs"
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = None
    required_evidence_fields: tuple[str, ...] = (
        "execution_record_ref",
        "train_artifact_ref",
        "eval_report_ref",
        "evidence_pack_ref",
    )


class MfGatePolicyEvaluator:
    """Evaluates Phase 5 gate receipts and publish eligibility deterministically."""

    def __init__(self, *, config: MfGatePolicyConfig | None = None) -> None:
        self.config = config or MfGatePolicyConfig()
        self._store = _build_store(self.config)

    def evaluate(
        self,
        *,
        plan: ResolvedTrainPlan,
        train_eval_receipt: MfTrainEvalReceipt,
        evaluated_at_utc: str | None = None,
    ) -> MfPhase5PolicyResult:
        _assert_scope_alignment(plan=plan, receipt=train_eval_receipt)
        evidence_refs = _extract_evidence_refs(receipt=train_eval_receipt)
        _assert_required_evidence_refs(evidence_refs=evidence_refs, config=self.config)

        eval_payload = _read_json_ref(
            ref=train_eval_receipt.eval_report_ref,
            store=self._store,
            config=self.config,
            code="EVAL_REPORT_UNRESOLVED",
        )
        try:
            eval_contract = EvalReportContract.from_payload(eval_payload)
        except Exception as exc:  # noqa: BLE001
            raise MfPhase5GateError("EVAL_REPORT_INVALID", str(exc)) from exc
        eval_body = eval_contract.payload

        eval_report_id = _required_text(eval_body.get("eval_report_id"), code="EVAL_REPORT_INVALID", field_name="eval_report_id")
        if eval_report_id != train_eval_receipt.eval_report_id:
            raise MfPhase5GateError(
                "EVAL_REPORT_MISMATCH",
                f"eval_report_id {eval_report_id!r} does not match receipt {train_eval_receipt.eval_report_id!r}",
            )
        eval_gate_decision = _required_text(
            eval_body.get("gate_decision"),
            code="EVAL_REPORT_INVALID",
            field_name="gate_decision",
        ).upper()
        if eval_gate_decision != str(train_eval_receipt.gate_decision).upper():
            raise MfPhase5GateError(
                "GATE_DECISION_MISMATCH",
                (
                    "train/eval receipt gate_decision does not match EvalReport: "
                    f"{train_eval_receipt.gate_decision!r} != {eval_gate_decision!r}"
                ),
            )

        _validate_supporting_evidence(
            evidence_refs=evidence_refs,
            store=self._store,
            config=self.config,
        )

        resolved_evaluated_at = _text_or_empty(evaluated_at_utc) or _text_or_empty(train_eval_receipt.execution_completed_at_utc)
        if not resolved_evaluated_at:
            raise MfPhase5GateError("RUN_SCOPE_INVALID", "evaluated_at_utc is required")
        gate_thresholds = _resolve_gate_thresholds(eval_body)
        gate_receipt = MfGateReceipt(
            run_key=plan.run_key,
            request_id=plan.request_id,
            platform_run_id=plan.platform_run_id,
            evaluated_at_utc=resolved_evaluated_at,
            gate_decision=eval_gate_decision,
            eval_report_id=eval_report_id,
            eval_report_ref=train_eval_receipt.eval_report_ref,
            evidence_refs=evidence_refs,
            gate_thresholds=gate_thresholds,
        )
        gate_receipt_ref = _write_json_immutable(
            store=self._store,
            config=self.config,
            relative_path=gate_receipt.artifact_relative_path(),
            payload=gate_receipt.as_dict(),
            drift_code="GATE_RECEIPT_IMMUTABILITY_VIOLATION",
        )

        eligible = eval_gate_decision == "PASS"
        reason_codes: list[str] = ["PASS_READY"] if eligible else ["GATE_FAIL"]
        publish_eligibility = MfPublishEligibilityReceipt(
            run_key=plan.run_key,
            request_id=plan.request_id,
            platform_run_id=plan.platform_run_id,
            evaluated_at_utc=resolved_evaluated_at,
            decision="ELIGIBLE" if eligible else "INELIGIBLE",
            eligible=eligible,
            reason_codes=tuple(reason_codes),
            gate_receipt_ref=gate_receipt_ref,
            eval_report_ref=train_eval_receipt.eval_report_ref,
            required_evidence_refs=evidence_refs,
        )
        publish_eligibility_ref = _write_json_immutable(
            store=self._store,
            config=self.config,
            relative_path=publish_eligibility.artifact_relative_path(),
            payload=publish_eligibility.as_dict(),
            drift_code="PUBLISH_ELIGIBILITY_IMMUTABILITY_VIOLATION",
        )
        return MfPhase5PolicyResult(
            gate_receipt=gate_receipt,
            publish_eligibility=publish_eligibility,
            gate_receipt_ref=gate_receipt_ref,
            publish_eligibility_ref=publish_eligibility_ref,
        )


def _assert_scope_alignment(*, plan: ResolvedTrainPlan, receipt: MfTrainEvalReceipt) -> None:
    if receipt.run_key != plan.run_key:
        raise MfPhase5GateError(
            "RUN_SCOPE_INVALID",
            f"train/eval receipt run_key {receipt.run_key!r} does not match plan {plan.run_key!r}",
        )
    if receipt.platform_run_id != plan.platform_run_id:
        raise MfPhase5GateError(
            "RUN_SCOPE_INVALID",
            f"train/eval receipt platform_run_id {receipt.platform_run_id!r} does not match plan {plan.platform_run_id!r}",
        )
    if receipt.request_id != plan.request_id:
        raise MfPhase5GateError(
            "RUN_SCOPE_INVALID",
            f"train/eval receipt request_id {receipt.request_id!r} does not match plan {plan.request_id!r}",
        )


def _extract_evidence_refs(*, receipt: MfTrainEvalReceipt) -> dict[str, str]:
    return {
        "execution_record_ref": _text_or_empty(receipt.execution_record_ref),
        "train_artifact_ref": _text_or_empty(receipt.train_artifact_ref),
        "eval_report_ref": _text_or_empty(receipt.eval_report_ref),
        "evidence_pack_ref": _text_or_empty(receipt.evidence_pack_ref),
    }


def _assert_required_evidence_refs(*, evidence_refs: Mapping[str, str], config: MfGatePolicyConfig) -> None:
    missing = [field for field in config.required_evidence_fields if not _text_or_empty(evidence_refs.get(field))]
    if missing:
        raise MfPhase5GateError(
            "EVIDENCE_REF_MISSING",
            f"required evidence refs are missing: {sorted(missing)}",
        )


def _validate_supporting_evidence(
    *,
    evidence_refs: Mapping[str, str],
    store: ObjectStore,
    config: MfGatePolicyConfig,
) -> None:
    for field, ref in evidence_refs.items():
        if field == "eval_report_ref":
            continue
        try:
            _read_json_ref(ref=ref, store=store, config=config, code="EVIDENCE_UNRESOLVED")
        except MfPhase5GateError as exc:
            raise MfPhase5GateError(
                "EVIDENCE_UNRESOLVED",
                f"{field} could not be resolved: {exc.message}",
            ) from exc


def _resolve_gate_thresholds(eval_body: Mapping[str, Any]) -> dict[str, Any]:
    metrics = eval_body.get("metrics")
    if not isinstance(metrics, Mapping):
        return {}
    thresholds = metrics.get("thresholds")
    if not isinstance(thresholds, Mapping):
        return {}
    return _normalize_mapping(thresholds)


def _write_json_immutable(
    *,
    store: ObjectStore,
    config: MfGatePolicyConfig,
    relative_path: str,
    payload: Mapping[str, Any],
    drift_code: str,
) -> str:
    normalized_payload = _normalize_mapping(payload)
    try:
        ref = store.write_json_if_absent(relative_path, normalized_payload)
        return str(ref.path)
    except FileExistsError:
        existing = store.read_json(relative_path)
        if _normalize_mapping(existing) != normalized_payload:
            raise MfPhase5GateError(drift_code, f"immutable artifact drift at {relative_path}")
        return _artifact_ref(config, relative_path)


def _build_store(config: MfGatePolicyConfig) -> ObjectStore:
    root = str(config.object_store_root or "").strip()
    if not root:
        raise ValueError("object_store_root is required")
    if root.startswith("s3://"):
        parsed = urlparse(root)
        return S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=config.object_store_endpoint,
            region_name=config.object_store_region,
            path_style=config.object_store_path_style,
        )
    return LocalObjectStore(Path(root))


def _artifact_ref(config: MfGatePolicyConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


def _read_json_ref(
    *,
    ref: str,
    store: ObjectStore,
    config: MfGatePolicyConfig,
    code: str,
) -> dict[str, Any]:
    value = _text_or_empty(ref)
    if not value:
        raise MfPhase5GateError(code, "artifact ref is required")
    if value.startswith("s3://"):
        parsed = urlparse(value)
        s3_store = S3ObjectStore(
            parsed.netloc,
            prefix="",
            endpoint_url=config.object_store_endpoint,
            region_name=config.object_store_region,
            path_style=config.object_store_path_style,
        )
        try:
            return s3_store.read_json(parsed.path.lstrip("/"))
        except Exception as exc:  # noqa: BLE001
            raise MfPhase5GateError(code, str(exc)) from exc
    path = Path(value)
    try:
        if path.is_absolute():
            return json.loads(path.read_text(encoding="utf-8"))
        return store.read_json(value)
    except Exception as exc:  # noqa: BLE001
        raise MfPhase5GateError(code, str(exc)) from exc


def _required_text(value: Any, *, code: str, field_name: str) -> str:
    text = _text_or_empty(value)
    if not text:
        raise MfPhase5GateError(code, f"{field_name} is required")
    return text


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _normalize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return _normalize_generic(dict(value))


def _normalize_generic(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_generic(val) for key, val in sorted(value.items(), key=lambda row: str(row[0]))}
    if isinstance(value, list):
        return [_normalize_generic(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
