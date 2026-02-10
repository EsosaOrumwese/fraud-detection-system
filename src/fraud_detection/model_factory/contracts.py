"""Phase 1 contracts for Model Factory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

from fraud_detection.learning_registry.contracts import load_ownership_boundaries
from fraud_detection.learning_registry.schemas import (
    LearningRegistrySchemaError,
    LearningRegistrySchemaRegistry,
)

from .ids import deterministic_train_run_id, train_run_key


_TRAIN_REQUEST_SCHEMA = "mf_train_build_request_v0.schema.yaml"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_INTENT_KINDS: set[str] = {
    "baseline_train",
    "backfill_retrain",
    "candidate_eval",
    "regression_check",
}
_OWNERSHIP_PATH = Path("config/platform/learning_registry/ownership_boundaries_v0.yaml")


class MfPhase1ContractError(ValueError):
    """Raised when MF Phase 1 contract checks fail."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code or "").strip() or "UNKNOWN"
        self.message = str(message or "").strip() or self.code
        super().__init__(f"{self.code}:{self.message}")


@dataclass(frozen=True)
class TargetScope:
    environment: str
    mode: str
    bundle_slot: str
    tenant_id: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "TargetScope":
        item = _mapping(payload, "target_scope")
        environment = _required_text(item.get("environment"), "TARGET_SCOPE_INVALID", "target_scope.environment")
        mode = _required_text(item.get("mode"), "TARGET_SCOPE_INVALID", "target_scope.mode")
        bundle_slot = _required_text(item.get("bundle_slot"), "TARGET_SCOPE_INVALID", "target_scope.bundle_slot")
        tenant_raw = item.get("tenant_id")
        tenant_id = _required_text(
            tenant_raw,
            "TARGET_SCOPE_INVALID",
            "target_scope.tenant_id",
        ) if tenant_raw not in (None, "") else None
        return cls(
            environment=environment,
            mode=mode,
            bundle_slot=bundle_slot,
            tenant_id=tenant_id,
        )

    def as_dict(self) -> dict[str, str]:
        payload = {
            "environment": self.environment,
            "mode": self.mode,
            "bundle_slot": self.bundle_slot,
        }
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        return payload


@dataclass(frozen=True)
class MfTrainBuildRequest:
    request_id: str
    intent_kind: str
    platform_run_id: str
    dataset_manifest_refs: tuple[str, ...]
    training_config_ref: str
    governance_profile_ref: str
    requester_principal: str
    target_scope: TargetScope
    policy_revision: str
    config_revision: str
    mf_code_release_id: str
    publish_allowed: bool

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        registry: LearningRegistrySchemaRegistry | None = None,
        ownership_path: Path | str = _OWNERSHIP_PATH,
    ) -> "MfTrainBuildRequest":
        body = _mapping(payload, "mf_train_build_request")
        schema_registry = registry or LearningRegistrySchemaRegistry()
        try:
            schema_registry.validate(_TRAIN_REQUEST_SCHEMA, body)
        except LearningRegistrySchemaError as exc:
            code = _schema_error_code(str(exc))
            raise MfPhase1ContractError(code, str(exc)) from exc

        request_id = _required_text(body.get("request_id"), "REQUEST_ID_INVALID", "request_id")
        if not _REQUEST_ID_RE.fullmatch(request_id):
            raise MfPhase1ContractError(
                "REQUEST_ID_INVALID",
                "request_id must match [A-Za-z0-9_.:-]{8,128}",
            )

        intent_kind = _required_text(body.get("intent_kind"), "INTENT_KIND_UNSUPPORTED", "intent_kind")
        if intent_kind not in _INTENT_KINDS:
            raise MfPhase1ContractError(
                "INTENT_KIND_UNSUPPORTED",
                f"intent_kind must be one of {sorted(_INTENT_KINDS)}",
            )

        platform_run_id = _required_text(body.get("platform_run_id"), "RUN_SCOPE_INVALID", "platform_run_id")
        dataset_manifest_refs = tuple(_non_empty_strings(body.get("dataset_manifest_refs")))
        if not dataset_manifest_refs:
            raise MfPhase1ContractError("MANIFEST_REF_MISSING", "dataset_manifest_refs must contain at least one ref")
        training_config_ref = _required_text(
            body.get("training_config_ref"),
            "TRAIN_CONFIG_MISSING",
            "training_config_ref",
        )
        governance_profile_ref = _required_text(
            body.get("governance_profile_ref"),
            "GOVERNANCE_PROFILE_MISSING",
            "governance_profile_ref",
        )
        requester_principal = _required_text(
            body.get("requester_principal"),
            "REQUESTER_MISSING",
            "requester_principal",
        )
        policy_revision = _required_text(body.get("policy_revision"), "POLICY_REVISION_MISSING", "policy_revision")
        config_revision = _required_text(body.get("config_revision"), "CONFIG_REVISION_MISSING", "config_revision")
        mf_code_release_id = _required_text(
            body.get("mf_code_release_id"),
            "CODE_RELEASE_MISSING",
            "mf_code_release_id",
        )
        target_scope = TargetScope.from_payload(body.get("target_scope") or {})
        publish_allowed = bool(body.get("publish_allowed", False))

        _assert_ownership_boundaries(ownership_path)

        return cls(
            request_id=request_id,
            intent_kind=intent_kind,
            platform_run_id=platform_run_id,
            dataset_manifest_refs=dataset_manifest_refs,
            training_config_ref=training_config_ref,
            governance_profile_ref=governance_profile_ref,
            requester_principal=requester_principal,
            target_scope=target_scope,
            policy_revision=policy_revision,
            config_revision=config_revision,
            mf_code_release_id=mf_code_release_id,
            publish_allowed=publish_allowed,
        )

    def train_run_key_payload(self) -> dict[str, Any]:
        return {
            "intent_kind": self.intent_kind,
            "platform_run_id": self.platform_run_id,
            "dataset_manifest_refs": list(self.dataset_manifest_refs),
            "training_config_ref": self.training_config_ref,
            "governance_profile_ref": self.governance_profile_ref,
            "target_scope": self.target_scope.as_dict(),
            "policy_revision": self.policy_revision,
            "config_revision": self.config_revision,
            "mf_code_release_id": self.mf_code_release_id,
        }

    def deterministic_train_run_key(self) -> str:
        return train_run_key(self.train_run_key_payload())

    def deterministic_train_run_id(self) -> str:
        return deterministic_train_run_id(self.deterministic_train_run_key())

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "learning.mf_train_build_request.v0",
            "request_id": self.request_id,
            "intent_kind": self.intent_kind,
            "platform_run_id": self.platform_run_id,
            "dataset_manifest_refs": list(self.dataset_manifest_refs),
            "training_config_ref": self.training_config_ref,
            "governance_profile_ref": self.governance_profile_ref,
            "requester_principal": self.requester_principal,
            "target_scope": self.target_scope.as_dict(),
            "policy_revision": self.policy_revision,
            "config_revision": self.config_revision,
            "mf_code_release_id": self.mf_code_release_id,
            "publish_allowed": self.publish_allowed,
        }
        return payload


def _assert_ownership_boundaries(path: Path | str) -> None:
    try:
        boundaries = load_ownership_boundaries(path)
    except Exception as exc:
        raise MfPhase1ContractError("OWNERSHIP_BOUNDARY_VIOLATION", str(exc)) from exc
    owners = boundaries.get("owners")
    outputs = boundaries.get("outputs")
    if not isinstance(owners, Mapping) or "mf" not in owners:
        raise MfPhase1ContractError("OWNERSHIP_BOUNDARY_VIOLATION", "owners.mf is required")
    if not isinstance(outputs, list) or "eval_report" not in outputs or "bundle_publication" not in outputs:
        raise MfPhase1ContractError(
            "OWNERSHIP_BOUNDARY_VIOLATION",
            "outputs must include eval_report and bundle_publication",
        )


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MfPhase1ContractError("SCHEMA_INVALID", f"{field_name} must be a mapping")
    return dict(value)


def _required_text(value: Any, code: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MfPhase1ContractError(code, f"{field_name} is required")
    return text


def _non_empty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            output.append(text)
    return output


def _schema_error_code(message: str) -> str:
    text = str(message or "")
    mapping = (
        ("request_id", "REQUEST_ID_INVALID"),
        ("intent_kind", "INTENT_KIND_UNSUPPORTED"),
        ("platform_run_id", "RUN_SCOPE_INVALID"),
        ("dataset_manifest_refs", "MANIFEST_REF_MISSING"),
        ("training_config_ref", "TRAIN_CONFIG_MISSING"),
        ("governance_profile_ref", "GOVERNANCE_PROFILE_MISSING"),
        ("requester_principal", "REQUESTER_MISSING"),
        ("target_scope", "TARGET_SCOPE_INVALID"),
        ("policy_revision", "POLICY_REVISION_MISSING"),
        ("config_revision", "CONFIG_REVISION_MISSING"),
        ("mf_code_release_id", "CODE_RELEASE_MISSING"),
    )
    for token, code in mapping:
        if token in text:
            return code
    return "SCHEMA_INVALID"

