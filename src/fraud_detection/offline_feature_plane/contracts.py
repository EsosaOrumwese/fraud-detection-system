"""Phase 1 contracts for Offline Feature Plane."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

from fraud_detection.learning_registry.contracts import (
    DatasetManifestContract,
    load_ownership_boundaries,
)
from fraud_detection.learning_registry.schemas import (
    LearningRegistrySchemaError,
    LearningRegistrySchemaRegistry,
)

from .ids import dataset_fingerprint, deterministic_dataset_manifest_id


_INTENT_SCHEMA = "ofs_build_intent_v0.schema.yaml"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_INTENT_KINDS: set[str] = {"dataset_build", "parity_rebuild", "forensic_rebuild"}
_OWNERSHIP_PATH = Path("config/platform/learning_registry/ownership_boundaries_v0.yaml")


class OfsPhase1ContractError(ValueError):
    """Raised when OFS Phase 1 contract checks fail."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code or "").strip() or "UNKNOWN"
        self.message = str(message or "").strip() or self.code
        super().__init__(f"{self.code}:{self.message}")


@dataclass(frozen=True)
class ReplayBasisSlice:
    topic: str
    partition: int
    offset_kind: str
    start_offset: str
    end_offset: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ReplayBasisSlice":
        item = _mapping(payload, "replay_basis[]")
        topic = _required_text(item.get("topic"), "BASIS_UNRESOLVED", "replay_basis[].topic")
        partition = _required_non_negative_int(item.get("partition"), "BASIS_UNRESOLVED", "replay_basis[].partition")
        offset_kind = _required_text(item.get("offset_kind"), "BASIS_UNRESOLVED", "replay_basis[].offset_kind")
        start_offset = _required_text(item.get("start_offset"), "BASIS_UNRESOLVED", "replay_basis[].start_offset")
        end_offset = _required_text(item.get("end_offset"), "BASIS_UNRESOLVED", "replay_basis[].end_offset")
        return cls(
            topic=topic,
            partition=partition,
            offset_kind=offset_kind,
            start_offset=start_offset,
            end_offset=end_offset,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "partition": self.partition,
            "offset_kind": self.offset_kind,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
        }


@dataclass(frozen=True)
class LabelBasis:
    label_asof_utc: str
    resolution_rule: str
    maturity_days: int | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "LabelBasis":
        item = _mapping(payload, "label_basis")
        label_asof_utc = _required_text(item.get("label_asof_utc"), "LABEL_ASOF_MISSING", "label_basis.label_asof_utc")
        resolution_rule = _required_text(
            item.get("resolution_rule"),
            "LABEL_ASOF_MISSING",
            "label_basis.resolution_rule",
        )
        maturity_days_raw = item.get("maturity_days")
        maturity_days = None
        if maturity_days_raw not in (None, ""):
            maturity_days = _required_non_negative_int(
                maturity_days_raw,
                "LABEL_ASOF_MISSING",
                "label_basis.maturity_days",
            )
        return cls(
            label_asof_utc=label_asof_utc,
            resolution_rule=resolution_rule,
            maturity_days=maturity_days,
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "label_asof_utc": self.label_asof_utc,
            "resolution_rule": self.resolution_rule,
        }
        if self.maturity_days is not None:
            payload["maturity_days"] = self.maturity_days
        return payload


@dataclass(frozen=True)
class FeatureDefinitionSet:
    feature_set_id: str
    feature_set_version: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "FeatureDefinitionSet":
        item = _mapping(payload, "feature_definition_set")
        feature_set_id = _required_text(
            item.get("feature_set_id"),
            "FEATURE_PROFILE_UNRESOLVED",
            "feature_definition_set.feature_set_id",
        )
        feature_set_version = _required_text(
            item.get("feature_set_version"),
            "FEATURE_PROFILE_UNRESOLVED",
            "feature_definition_set.feature_set_version",
        )
        return cls(feature_set_id=feature_set_id, feature_set_version=feature_set_version)

    def as_dict(self) -> dict[str, str]:
        return {
            "feature_set_id": self.feature_set_id,
            "feature_set_version": self.feature_set_version,
        }


@dataclass(frozen=True)
class OfsBuildIntent:
    request_id: str
    intent_kind: str
    platform_run_id: str
    scenario_run_ids: tuple[str, ...]
    replay_basis: tuple[ReplayBasisSlice, ...]
    label_basis: LabelBasis
    feature_definition_set: FeatureDefinitionSet
    join_scope: dict[str, Any]
    filters: dict[str, Any]
    run_facts_ref: str
    policy_revision: str
    config_revision: str
    ofs_code_release_id: str
    non_training_allowed: bool
    parity_anchor_ref: str | None = None

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        registry: LearningRegistrySchemaRegistry | None = None,
        ownership_path: Path | str = _OWNERSHIP_PATH,
    ) -> "OfsBuildIntent":
        body = _mapping(payload, "ofs_build_intent")
        schema_registry = registry or LearningRegistrySchemaRegistry()
        try:
            schema_registry.validate(_INTENT_SCHEMA, body)
        except LearningRegistrySchemaError as exc:
            code = _schema_error_code(str(exc))
            raise OfsPhase1ContractError(code, str(exc)) from exc

        request_id = _required_text(body.get("request_id"), "REQUEST_ID_INVALID", "request_id")
        if not _REQUEST_ID_RE.fullmatch(request_id):
            raise OfsPhase1ContractError(
                "REQUEST_ID_INVALID",
                "request_id must match [A-Za-z0-9_.:-]{8,128}",
            )

        intent_kind = _required_text(body.get("intent_kind"), "INTENT_KIND_UNSUPPORTED", "intent_kind")
        if intent_kind not in _INTENT_KINDS:
            raise OfsPhase1ContractError(
                "INTENT_KIND_UNSUPPORTED",
                f"intent_kind must be one of {sorted(_INTENT_KINDS)}",
            )

        platform_run_id = _required_text(body.get("platform_run_id"), "RUN_SCOPE_INVALID", "platform_run_id")
        scenario_run_ids = tuple(_non_empty_strings(body.get("scenario_run_ids")))
        replay_basis_rows = body.get("replay_basis")
        if not isinstance(replay_basis_rows, list) or not replay_basis_rows:
            raise OfsPhase1ContractError("BASIS_UNRESOLVED", "replay_basis must contain at least one slice")
        replay_basis = tuple(ReplayBasisSlice.from_payload(item) for item in replay_basis_rows)

        label_basis = LabelBasis.from_payload(body.get("label_basis") or {})
        feature_definition_set = FeatureDefinitionSet.from_payload(body.get("feature_definition_set") or {})

        run_facts_ref = _required_text(body.get("run_facts_ref"), "RUN_FACTS_UNAVAILABLE", "run_facts_ref")
        policy_revision = _required_text(body.get("policy_revision"), "POLICY_REVISION_MISSING", "policy_revision")
        config_revision = _required_text(body.get("config_revision"), "CONFIG_REVISION_MISSING", "config_revision")
        ofs_code_release_id = _required_text(
            body.get("ofs_code_release_id"),
            "CODE_RELEASE_MISSING",
            "ofs_code_release_id",
        )
        join_scope = _mapping_or_empty(body.get("join_scope"))
        filters = _mapping_or_empty(body.get("filters"))
        parity_anchor_ref_raw = body.get("parity_anchor_ref")
        parity_anchor_ref = _required_text(
            parity_anchor_ref_raw,
            "PARITY_ANCHOR_INVALID",
            "parity_anchor_ref",
        ) if parity_anchor_ref_raw not in (None, "") else None
        non_training_allowed = bool(body.get("non_training_allowed", False))

        _assert_ownership_boundaries(ownership_path)

        return cls(
            request_id=request_id,
            intent_kind=intent_kind,
            platform_run_id=platform_run_id,
            scenario_run_ids=scenario_run_ids,
            replay_basis=replay_basis,
            label_basis=label_basis,
            feature_definition_set=feature_definition_set,
            join_scope=join_scope,
            filters=filters,
            run_facts_ref=run_facts_ref,
            policy_revision=policy_revision,
            config_revision=config_revision,
            ofs_code_release_id=ofs_code_release_id,
            non_training_allowed=non_training_allowed,
            parity_anchor_ref=parity_anchor_ref,
        )

    def dataset_identity_payload(self) -> dict[str, Any]:
        return {
            "platform_run_id": self.platform_run_id,
            "scenario_run_ids": list(self.scenario_run_ids),
            "replay_basis": [item.as_dict() for item in self.replay_basis],
            "label_basis": self.label_basis.as_dict(),
            "feature_definition_set": self.feature_definition_set.as_dict(),
            "join_scope": dict(self.join_scope),
            "filters": dict(self.filters),
            "policy_revision": self.policy_revision,
            "config_revision": self.config_revision,
            "ofs_code_release_id": self.ofs_code_release_id,
        }

    def dataset_fingerprint(self) -> str:
        return dataset_fingerprint(self.dataset_identity_payload())

    def to_dataset_manifest(self, *, dataset_manifest_id: str | None = None) -> DatasetManifestContract:
        fingerprint = self.dataset_fingerprint()
        manifest_id = dataset_manifest_id or deterministic_dataset_manifest_id(fingerprint)
        payload = {
            "schema_version": "learning.dataset_manifest.v0",
            "dataset_manifest_id": manifest_id,
            "dataset_fingerprint": fingerprint,
            "platform_run_id": self.platform_run_id,
            "scenario_run_ids": list(self.scenario_run_ids),
            "replay_basis": [item.as_dict() for item in self.replay_basis],
            "label_basis": self.label_basis.as_dict(),
            "feature_definition_set": self.feature_definition_set.as_dict(),
            "provenance": {
                "ofs_code_release_id": self.ofs_code_release_id,
                "config_revision": self.config_revision,
                "run_config_digest": self.policy_revision,
            },
        }
        return DatasetManifestContract.from_payload(payload)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "learning.ofs_build_intent.v0",
            "request_id": self.request_id,
            "intent_kind": self.intent_kind,
            "platform_run_id": self.platform_run_id,
            "replay_basis": [item.as_dict() for item in self.replay_basis],
            "label_basis": self.label_basis.as_dict(),
            "feature_definition_set": self.feature_definition_set.as_dict(),
            "join_scope": dict(self.join_scope),
            "filters": dict(self.filters),
            "run_facts_ref": self.run_facts_ref,
            "policy_revision": self.policy_revision,
            "config_revision": self.config_revision,
            "ofs_code_release_id": self.ofs_code_release_id,
            "non_training_allowed": self.non_training_allowed,
        }
        if self.scenario_run_ids:
            payload["scenario_run_ids"] = list(self.scenario_run_ids)
        if self.parity_anchor_ref is not None:
            payload["parity_anchor_ref"] = self.parity_anchor_ref
        return payload


def _assert_ownership_boundaries(path: Path | str) -> None:
    try:
        boundaries = load_ownership_boundaries(path)
    except Exception as exc:
        raise OfsPhase1ContractError("OWNERSHIP_BOUNDARY_VIOLATION", str(exc)) from exc
    owners = boundaries.get("owners")
    outputs = boundaries.get("outputs")
    if not isinstance(owners, Mapping) or "ofs" not in owners:
        raise OfsPhase1ContractError("OWNERSHIP_BOUNDARY_VIOLATION", "owners.ofs is required")
    if not isinstance(outputs, list) or "dataset_manifest" not in outputs:
        raise OfsPhase1ContractError(
            "OWNERSHIP_BOUNDARY_VIOLATION",
            "outputs must include dataset_manifest",
        )


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OfsPhase1ContractError("SCHEMA_INVALID", f"{field_name} must be a mapping")
    return dict(value)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _required_text(value: Any, code: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise OfsPhase1ContractError(code, f"{field_name} is required")
    return text


def _required_non_negative_int(value: Any, code: str, field_name: str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:
        raise OfsPhase1ContractError(code, f"{field_name} must be an integer") from exc
    if parsed < 0:
        raise OfsPhase1ContractError(code, f"{field_name} must be >= 0")
    return parsed


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
        ("replay_basis", "BASIS_UNRESOLVED"),
        ("label_basis.label_asof_utc", "LABEL_ASOF_MISSING"),
        ("label_basis.resolution_rule", "LABEL_ASOF_MISSING"),
        ("feature_definition_set.feature_set_id", "FEATURE_PROFILE_UNRESOLVED"),
        ("feature_definition_set.feature_set_version", "FEATURE_PROFILE_UNRESOLVED"),
        ("run_facts_ref", "RUN_FACTS_UNAVAILABLE"),
    )
    for token, code in mapping:
        if token in text:
            return code
    return "SCHEMA_INVALID"
