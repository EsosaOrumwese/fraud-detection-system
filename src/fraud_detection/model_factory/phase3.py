"""MF Phase 3 input resolver and provenance-lock surfaces."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml

from fraud_detection.learning_registry.contracts import DatasetManifestContract
from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .contracts import MfTrainBuildRequest
from .run_ledger import deterministic_run_key


@dataclass(frozen=True)
class MfPhase3ResolverError(ValueError):
    """Raised when MF Phase 3 resolver checks fail."""

    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code or "").strip() or "UNKNOWN")
        object.__setattr__(self, "message", str(self.message or "").strip() or self.code)
        ValueError.__init__(self, f"{self.code}:{self.message}")


@dataclass(frozen=True)
class ResolvedDatasetManifest:
    manifest_ref: str
    schema_version: str
    dataset_manifest_id: str
    dataset_fingerprint: str
    platform_run_id: str
    feature_set_id: str
    feature_set_version: str
    payload_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_ref": self.manifest_ref,
            "schema_version": self.schema_version,
            "dataset_manifest_id": self.dataset_manifest_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "platform_run_id": self.platform_run_id,
            "feature_definition_set": {
                "feature_set_id": self.feature_set_id,
                "feature_set_version": self.feature_set_version,
            },
            "payload_digest": self.payload_digest,
        }


@dataclass(frozen=True)
class ResolvedTrainingProfile:
    profile_ref: str
    policy_id: str
    revision: str
    feature_set_id: str
    feature_set_version: str
    expected_manifest_schema_version: str
    profile_digest: str

    @property
    def resolved_revision(self) -> str:
        return f"{self.policy_id}@{self.revision}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_ref": self.profile_ref,
            "policy_id": self.policy_id,
            "revision": self.revision,
            "resolved_revision": self.resolved_revision,
            "feature_definition_set": {
                "feature_set_id": self.feature_set_id,
                "feature_set_version": self.feature_set_version,
            },
            "expected_manifest_schema_version": self.expected_manifest_schema_version,
            "profile_digest": self.profile_digest,
        }


@dataclass(frozen=True)
class ResolvedGovernanceProfile:
    profile_ref: str
    policy_id: str
    revision: str
    profile_digest: str

    @property
    def resolved_revision(self) -> str:
        return f"{self.policy_id}@{self.revision}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_ref": self.profile_ref,
            "policy_id": self.policy_id,
            "revision": self.revision,
            "resolved_revision": self.resolved_revision,
            "profile_digest": self.profile_digest,
        }


@dataclass(frozen=True)
class ResolvedTrainPlan:
    run_key: str
    request_id: str
    intent_kind: str
    platform_run_id: str
    dataset_manifests: tuple[ResolvedDatasetManifest, ...]
    training_profile: ResolvedTrainingProfile
    governance_profile: ResolvedGovernanceProfile
    input_refs: dict[str, Any]

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/mf/resolved_train_plan/{self.run_key}.json"

    def as_dict(self) -> dict[str, Any]:
        return _normalize_mapping(
            {
                "schema_version": "learning.mf_resolved_train_plan.v0",
                "run_key": self.run_key,
                "request_id": self.request_id,
                "intent_kind": self.intent_kind,
                "platform_run_id": self.platform_run_id,
                "dataset_manifests": [item.as_dict() for item in self.dataset_manifests],
                "training_profile": self.training_profile.as_dict(),
                "governance_profile": self.governance_profile.as_dict(),
                "input_refs": dict(self.input_refs),
            }
        )


@dataclass(frozen=True)
class MfTrainPlanResolverConfig:
    object_store_root: str = "runs"
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = None
    required_manifest_refs: tuple[str, ...] = ()
    expected_manifest_schema_version: str = "learning.dataset_manifest.v0"


class MfTrainPlanResolver:
    """Resolves MF Phase 3 inputs and emits immutable resolved train-plan artifacts."""

    def __init__(self, *, config: MfTrainPlanResolverConfig | None = None) -> None:
        self.config = config or MfTrainPlanResolverConfig()
        self._store = _build_store(self.config)

    def resolve(self, *, request: MfTrainBuildRequest, run_key: str | None = None) -> ResolvedTrainPlan:
        manifest_refs = _manifest_refs(request=request, config=self.config)
        if not manifest_refs:
            raise MfPhase3ResolverError("MANIFEST_REF_MISSING", "dataset_manifest_refs must contain at least one ref")
        resolved_run_key = str(run_key or deterministic_run_key(request))
        training_profile = _resolve_training_profile(request=request, store=self._store, config=self.config)
        governance_profile = _resolve_governance_profile(request=request, store=self._store, config=self.config)
        manifests = _resolve_manifests(
            manifest_refs=manifest_refs,
            request=request,
            training_profile=training_profile,
            store=self._store,
            config=self.config,
        )
        return ResolvedTrainPlan(
            run_key=resolved_run_key,
            request_id=request.request_id,
            intent_kind=request.intent_kind,
            platform_run_id=request.platform_run_id,
            dataset_manifests=tuple(manifests),
            training_profile=training_profile,
            governance_profile=governance_profile,
            input_refs={
                "dataset_manifest_refs": list(manifest_refs),
                "training_config_ref": request.training_config_ref,
                "governance_profile_ref": request.governance_profile_ref,
                "policy_revision": request.policy_revision,
                "config_revision": request.config_revision,
                "mf_code_release_id": request.mf_code_release_id,
            },
        )

    def emit_immutable(self, *, plan: ResolvedTrainPlan) -> str:
        relative_path = plan.artifact_relative_path()
        payload = plan.as_dict()
        try:
            ref = self._store.write_json_if_absent(relative_path, payload)
            return str(ref.path)
        except FileExistsError:
            existing = self._store.read_json(relative_path)
            if _normalize_mapping(existing) != payload:
                raise MfPhase3ResolverError(
                    "RESOLVED_TRAIN_PLAN_IMMUTABILITY_VIOLATION",
                    f"resolved train plan already exists with drift at {relative_path}",
                )
            return _artifact_ref(self.config, relative_path)


def _manifest_refs(*, request: MfTrainBuildRequest, config: MfTrainPlanResolverConfig) -> tuple[str, ...]:
    ordered: list[str] = []
    for item in list(request.dataset_manifest_refs) + list(config.required_manifest_refs):
        ref = _text_or_empty(item)
        if not ref or ref in ordered:
            continue
        ordered.append(ref)
    return tuple(ordered)


def _resolve_manifests(
    *,
    manifest_refs: tuple[str, ...],
    request: MfTrainBuildRequest,
    training_profile: ResolvedTrainingProfile,
    store: ObjectStore,
    config: MfTrainPlanResolverConfig,
) -> list[ResolvedDatasetManifest]:
    resolved: list[ResolvedDatasetManifest] = []
    by_id: dict[str, str] = {}
    for ref in manifest_refs:
        payload = _read_json_ref(ref=ref, store=store, config=config, code="MANIFEST_UNRESOLVED")
        try:
            contract = DatasetManifestContract.from_payload(payload)
        except Exception as exc:  # noqa: BLE001
            raise MfPhase3ResolverError("MANIFEST_INVALID", str(exc)) from exc
        body = contract.payload
        platform_run_id = _required_text(body.get("platform_run_id"), code="MANIFEST_INVALID", field_name="platform_run_id")
        if platform_run_id != request.platform_run_id:
            raise MfPhase3ResolverError(
                "RUN_SCOPE_INVALID",
                f"manifest platform_run_id {platform_run_id!r} does not match request {request.platform_run_id!r}",
            )
        schema_version = _required_text(body.get("schema_version"), code="MANIFEST_INVALID", field_name="schema_version")
        expected_schema = _text_or_empty(training_profile.expected_manifest_schema_version)
        if expected_schema and schema_version != expected_schema:
            raise MfPhase3ResolverError(
                "FEATURE_SCHEMA_INCOMPATIBLE",
                f"manifest schema_version {schema_version!r} does not match expected {expected_schema!r}",
            )
        feature_set = _mapping(body.get("feature_definition_set"), field_name="feature_definition_set", code="MANIFEST_INVALID")
        feature_set_id = _required_text(
            feature_set.get("feature_set_id"),
            code="MANIFEST_INVALID",
            field_name="feature_definition_set.feature_set_id",
        )
        feature_set_version = _required_text(
            feature_set.get("feature_set_version"),
            code="MANIFEST_INVALID",
            field_name="feature_definition_set.feature_set_version",
        )
        if feature_set_id != training_profile.feature_set_id or feature_set_version != training_profile.feature_set_version:
            raise MfPhase3ResolverError(
                "FEATURE_SCHEMA_INCOMPATIBLE",
                (
                    "manifest feature_definition_set mismatch with training profile: "
                    f"{feature_set_id}@{feature_set_version} != "
                    f"{training_profile.feature_set_id}@{training_profile.feature_set_version}"
                ),
            )
        manifest_id = _required_text(
            body.get("dataset_manifest_id"),
            code="MANIFEST_INVALID",
            field_name="dataset_manifest_id",
        )
        dataset_fingerprint = _required_text(
            body.get("dataset_fingerprint"),
            code="MANIFEST_INVALID",
            field_name="dataset_fingerprint",
        )
        prior = by_id.get(manifest_id)
        if prior and prior != dataset_fingerprint:
            raise MfPhase3ResolverError(
                "MANIFEST_IMMUTABILITY_VIOLATION",
                f"manifest id {manifest_id!r} resolved with conflicting dataset_fingerprint values",
            )
        by_id[manifest_id] = dataset_fingerprint
        resolved.append(
            ResolvedDatasetManifest(
                manifest_ref=ref,
                schema_version=schema_version,
                dataset_manifest_id=manifest_id,
                dataset_fingerprint=dataset_fingerprint,
                platform_run_id=platform_run_id,
                feature_set_id=feature_set_id,
                feature_set_version=feature_set_version,
                payload_digest=_sha256_payload(body),
            )
        )
    return resolved


def _resolve_training_profile(
    *,
    request: MfTrainBuildRequest,
    store: ObjectStore,
    config: MfTrainPlanResolverConfig,
) -> ResolvedTrainingProfile:
    payload = _read_mapping_ref(
        ref=request.training_config_ref,
        store=store,
        config=config,
        code="TRAINING_PROFILE_UNRESOLVED",
        field_name="training_config_ref",
    )
    policy_id = _required_text(
        payload.get("policy_id") or payload.get("training_policy_id"),
        code="TRAINING_PROFILE_UNRESOLVED",
        field_name="policy_id",
    )
    revision = _required_text(
        payload.get("revision") or payload.get("version"),
        code="TRAINING_PROFILE_UNRESOLVED",
        field_name="revision",
    )
    feature_set = _mapping(
        payload.get("feature_definition_set"),
        field_name="feature_definition_set",
        code="TRAINING_PROFILE_UNRESOLVED",
    )
    feature_set_id = _required_text(
        feature_set.get("feature_set_id"),
        code="TRAINING_PROFILE_UNRESOLVED",
        field_name="feature_definition_set.feature_set_id",
    )
    feature_set_version = _required_text(
        feature_set.get("feature_set_version"),
        code="TRAINING_PROFILE_UNRESOLVED",
        field_name="feature_definition_set.feature_set_version",
    )
    expected_manifest_schema_version = _text_or_empty(
        payload.get("expected_manifest_schema_version")
    ) or _text_or_empty(config.expected_manifest_schema_version)
    if not expected_manifest_schema_version:
        raise MfPhase3ResolverError(
            "TRAINING_PROFILE_UNRESOLVED",
            "expected_manifest_schema_version is required",
        )
    return ResolvedTrainingProfile(
        profile_ref=request.training_config_ref,
        policy_id=policy_id,
        revision=revision,
        feature_set_id=feature_set_id,
        feature_set_version=feature_set_version,
        expected_manifest_schema_version=expected_manifest_schema_version,
        profile_digest=_sha256_payload(payload),
    )


def _resolve_governance_profile(
    *,
    request: MfTrainBuildRequest,
    store: ObjectStore,
    config: MfTrainPlanResolverConfig,
) -> ResolvedGovernanceProfile:
    payload = _read_mapping_ref(
        ref=request.governance_profile_ref,
        store=store,
        config=config,
        code="GOVERNANCE_PROFILE_UNRESOLVED",
        field_name="governance_profile_ref",
    )
    policy_id = _required_text(
        payload.get("policy_id") or payload.get("governance_policy_id"),
        code="GOVERNANCE_PROFILE_UNRESOLVED",
        field_name="policy_id",
    )
    revision = _required_text(
        payload.get("revision") or payload.get("version"),
        code="GOVERNANCE_PROFILE_UNRESOLVED",
        field_name="revision",
    )
    return ResolvedGovernanceProfile(
        profile_ref=request.governance_profile_ref,
        policy_id=policy_id,
        revision=revision,
        profile_digest=_sha256_payload(payload),
    )


def _build_store(config: MfTrainPlanResolverConfig) -> ObjectStore:
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


def _artifact_ref(config: MfTrainPlanResolverConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


def _read_json_ref(
    *,
    ref: str,
    store: ObjectStore,
    config: MfTrainPlanResolverConfig,
    code: str,
) -> dict[str, Any]:
    value = _text_or_empty(ref)
    if not value:
        raise MfPhase3ResolverError(code, "artifact ref is required")
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
            raise MfPhase3ResolverError(code, str(exc)) from exc
    path = Path(value)
    try:
        if path.is_absolute():
            return json.loads(path.read_text(encoding="utf-8"))
        return store.read_json(value)
    except Exception as exc:  # noqa: BLE001
        raise MfPhase3ResolverError(code, str(exc)) from exc


def _read_mapping_ref(
    *,
    ref: str,
    store: ObjectStore,
    config: MfTrainPlanResolverConfig,
    code: str,
    field_name: str,
) -> dict[str, Any]:
    value = _text_or_empty(ref)
    if not value:
        raise MfPhase3ResolverError(code, f"{field_name} is required")
    text: str
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
            text = s3_store.read_text(parsed.path.lstrip("/"))
        except Exception as exc:  # noqa: BLE001
            raise MfPhase3ResolverError(code, str(exc)) from exc
    else:
        path = Path(value)
        try:
            if path.is_absolute() or path.exists():
                text = path.read_text(encoding="utf-8")
            else:
                text = store.read_text(value)
        except Exception as exc:  # noqa: BLE001
            raise MfPhase3ResolverError(code, str(exc)) from exc
    try:
        payload = yaml.safe_load(text) or {}
    except Exception as exc:  # noqa: BLE001
        raise MfPhase3ResolverError(code, str(exc)) from exc
    return _mapping(payload, field_name=field_name, code=code)


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_normalize_mapping(payload), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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


def _mapping(value: Any, *, field_name: str, code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MfPhase3ResolverError(code, f"{field_name} must be a mapping")
    return dict(value)


def _required_text(value: Any, *, code: str, field_name: str) -> str:
    text = _text_or_empty(value)
    if not text:
        raise MfPhase3ResolverError(code, f"{field_name} is required")
    return text


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()
