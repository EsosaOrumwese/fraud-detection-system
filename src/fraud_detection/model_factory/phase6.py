"""MF Phase 6 bundle packaging and MPR publish-handshake surfaces."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from fraud_detection.learning_registry.contracts import (
    BundlePublicationContract,
    RegistryLifecycleEventContract,
)
from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .phase3 import ResolvedTrainPlan
from .phase5 import MfPhase5PolicyResult


class MfPhase6PublishError(ValueError):
    """Raised when MF Phase 6 bundle packaging/publish checks fail."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code or "").strip() or "UNKNOWN"
        self.message = str(message or "").strip() or self.code
        super().__init__(f"{self.code}:{self.message}")


@dataclass(frozen=True)
class MfBundlePublication:
    run_key: str
    request_id: str
    platform_run_id: str
    bundle_id: str
    bundle_version: str
    payload: dict[str, Any]
    bundle_publication_ref: str


@dataclass(frozen=True)
class MfPublishHandshakeReceipt:
    run_key: str
    request_id: str
    platform_run_id: str
    published_at_utc: str
    publication_status: str
    bundle_id: str
    bundle_version: str
    bundle_publication_ref: str
    registry_bundle_ref: str
    registry_lifecycle_event_ref: str

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/mf/train_runs/{self.run_key}/publish/publish_handshake_receipt.json"

    def as_dict(self) -> dict[str, Any]:
        return _normalize_mapping(
            {
                "schema_version": "learning.mf_publish_handshake_receipt.v0",
                "run_key": self.run_key,
                "request_id": self.request_id,
                "platform_run_id": self.platform_run_id,
                "published_at_utc": self.published_at_utc,
                "publication_status": self.publication_status,
                "bundle_id": self.bundle_id,
                "bundle_version": self.bundle_version,
                "bundle_publication_ref": self.bundle_publication_ref,
                "registry_bundle_ref": self.registry_bundle_ref,
                "registry_lifecycle_event_ref": self.registry_lifecycle_event_ref,
            }
        )


@dataclass(frozen=True)
class MfPhase6PublishResult:
    bundle_publication: MfBundlePublication
    publish_receipt: MfPublishHandshakeReceipt
    publish_receipt_ref: str


@dataclass(frozen=True)
class MfBundlePublisherConfig:
    object_store_root: str = "runs"
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = None
    registry_bundle_prefix: str = "registry/bundles"
    registry_event_prefix: str = "registry/events"
    system_actor_id: str = "SYSTEM::model_factory"
    input_contract_version: str = "learning.dataset_manifest.v0"


class MfBundlePublisher:
    """Packages immutable bundles and performs idempotent publish handshake."""

    def __init__(self, *, config: MfBundlePublisherConfig | None = None) -> None:
        self.config = config or MfBundlePublisherConfig()
        self._store = _build_store(self.config)

    def publish(
        self,
        *,
        plan: ResolvedTrainPlan,
        phase5_result: MfPhase5PolicyResult,
        published_at_utc: str,
    ) -> MfPhase6PublishResult:
        _assert_publish_eligible(plan=plan, phase5_result=phase5_result)
        gate_payload = _read_json_ref(
            ref=phase5_result.gate_receipt_ref,
            store=self._store,
            config=self.config,
            code="EVIDENCE_UNRESOLVED",
        )
        gate_decision = _required_text(gate_payload.get("gate_decision"), code="GATE_INVALID", field_name="gate_decision").upper()
        if gate_decision != "PASS":
            raise MfPhase6PublishError("PUBLISH_NOT_ELIGIBLE", "publish requires PASS gate decision")

        eval_report_ref = _required_text(
            phase5_result.publish_eligibility.eval_report_ref,
            code="EVIDENCE_REF_MISSING",
            field_name="publish_eligibility.eval_report_ref",
        )
        _ = _read_json_ref(ref=eval_report_ref, store=self._store, config=self.config, code="EVIDENCE_UNRESOLVED")
        _validate_required_evidence(
            phase5_result.publish_eligibility.required_evidence_refs,
            store=self._store,
            config=self.config,
        )

        bundle_id, bundle_version = _bundle_identity(plan=plan, phase5_result=phase5_result)
        bundle_payload = _bundle_publication_payload(
            plan=plan,
            phase5_result=phase5_result,
            bundle_id=bundle_id,
            bundle_version=bundle_version,
            config=self.config,
        )
        try:
            BundlePublicationContract.from_payload(bundle_payload)
        except Exception as exc:  # noqa: BLE001
            raise MfPhase6PublishError("BUNDLE_PUBLICATION_INVALID", str(exc)) from exc

        bundle_publication_path = f"{plan.platform_run_id}/mf/train_runs/{plan.run_key}/bundle/bundle_publication.json"
        bundle_publication_ref = _write_json_immutable(
            store=self._store,
            config=self.config,
            relative_path=bundle_publication_path,
            payload=bundle_payload,
            drift_code="BUNDLE_PACKAGE_IMMUTABILITY_VIOLATION",
        )
        bundle_publication = MfBundlePublication(
            run_key=plan.run_key,
            request_id=plan.request_id,
            platform_run_id=plan.platform_run_id,
            bundle_id=bundle_id,
            bundle_version=bundle_version,
            payload=bundle_payload,
            bundle_publication_ref=bundle_publication_ref,
        )

        registry_relative_path = (
            f"{self.config.registry_bundle_prefix.strip('/')}/{bundle_id}/{bundle_version}/bundle_publication.json"
        )
        publication_status = "PUBLISHED"
        try:
            registry_ref = self._store.write_json_if_absent(registry_relative_path, bundle_payload).path
        except FileExistsError:
            existing = self._store.read_json(registry_relative_path)
            if _normalize_mapping(existing) != _normalize_mapping(bundle_payload):
                raise MfPhase6PublishError(
                    "PUBLISH_CONFLICT",
                    f"registry bundle publication conflict for {bundle_id}/{bundle_version}",
                )
            publication_status = "ALREADY_PUBLISHED"
            registry_ref = _artifact_ref(self.config, registry_relative_path)

        lifecycle_payload = _registry_lifecycle_payload(
            plan=plan,
            bundle_id=bundle_id,
            bundle_version=bundle_version,
            registry_bundle_ref=str(registry_ref),
            published_at_utc=published_at_utc,
            phase5_result=phase5_result,
            config=self.config,
        )
        try:
            RegistryLifecycleEventContract.from_payload(lifecycle_payload)
        except Exception as exc:  # noqa: BLE001
            raise MfPhase6PublishError("REGISTRY_EVENT_INVALID", str(exc)) from exc

        registry_event_path = (
            f"{self.config.registry_event_prefix.strip('/')}/{bundle_id}/{bundle_version}/bundle_published_event.json"
        )
        if publication_status == "ALREADY_PUBLISHED" and self._store.exists(registry_event_path):
            registry_lifecycle_event_ref = _artifact_ref(self.config, registry_event_path)
        else:
            registry_lifecycle_event_ref = _write_json_immutable(
                store=self._store,
                config=self.config,
                relative_path=registry_event_path,
                payload=lifecycle_payload,
                drift_code="REGISTRY_EVENT_IMMUTABILITY_VIOLATION",
            )

        publish_receipt = MfPublishHandshakeReceipt(
            run_key=plan.run_key,
            request_id=plan.request_id,
            platform_run_id=plan.platform_run_id,
            published_at_utc=published_at_utc,
            publication_status=publication_status,
            bundle_id=bundle_id,
            bundle_version=bundle_version,
            bundle_publication_ref=bundle_publication_ref,
            registry_bundle_ref=str(registry_ref),
            registry_lifecycle_event_ref=registry_lifecycle_event_ref,
        )
        publish_receipt_path = publish_receipt.artifact_relative_path()
        if publication_status == "ALREADY_PUBLISHED" and self._store.exists(publish_receipt_path):
            publish_receipt_ref = _artifact_ref(self.config, publish_receipt_path)
        else:
            publish_receipt_ref = _write_json_immutable(
                store=self._store,
                config=self.config,
                relative_path=publish_receipt_path,
                payload=publish_receipt.as_dict(),
                drift_code="PUBLISH_RECEIPT_IMMUTABILITY_VIOLATION",
            )
        return MfPhase6PublishResult(
            bundle_publication=bundle_publication,
            publish_receipt=publish_receipt,
            publish_receipt_ref=publish_receipt_ref,
        )


def _assert_publish_eligible(*, plan: ResolvedTrainPlan, phase5_result: MfPhase5PolicyResult) -> None:
    eligibility = phase5_result.publish_eligibility
    if not eligibility.eligible:
        raise MfPhase6PublishError(
            "PUBLISH_NOT_ELIGIBLE",
            f"publish eligibility decision is {eligibility.decision} with reasons {list(eligibility.reason_codes)}",
        )
    if eligibility.run_key != plan.run_key or eligibility.platform_run_id != plan.platform_run_id:
        raise MfPhase6PublishError("RUN_SCOPE_INVALID", "phase5 eligibility scope does not match resolved plan")
    if phase5_result.gate_receipt.gate_decision.upper() != "PASS":
        raise MfPhase6PublishError("PUBLISH_NOT_ELIGIBLE", "gate receipt decision must be PASS")


def _validate_required_evidence(
    evidence_refs: Mapping[str, str],
    *,
    store: ObjectStore,
    config: MfBundlePublisherConfig,
) -> None:
    for name, ref in evidence_refs.items():
        value = _text_or_empty(ref)
        if not value:
            raise MfPhase6PublishError("EVIDENCE_REF_MISSING", f"missing evidence ref: {name}")
        _ = _read_json_ref(ref=value, store=store, config=config, code="EVIDENCE_UNRESOLVED")


def _bundle_identity(*, plan: ResolvedTrainPlan, phase5_result: MfPhase5PolicyResult) -> tuple[str, str]:
    bundle_id = _sha256_payload(
        {
            "run_key": plan.run_key,
            "manifest_digests": [item.payload_digest for item in plan.dataset_manifests],
            "training_profile_digest": plan.training_profile.profile_digest,
            "governance_profile_digest": plan.governance_profile.profile_digest,
            "eval_report_ref": phase5_result.publish_eligibility.eval_report_ref,
            "gate_receipt_ref": phase5_result.gate_receipt_ref,
        }
    )
    version_digest = _sha256_payload(
        {
            "bundle_id": bundle_id,
            "policy_revision": _text_or_empty(plan.input_refs.get("policy_revision")),
            "config_revision": _text_or_empty(plan.input_refs.get("config_revision")),
        }
    )
    bundle_version = f"v0-{version_digest[:12]}"
    return bundle_id, bundle_version


def _bundle_publication_payload(
    *,
    plan: ResolvedTrainPlan,
    phase5_result: MfPhase5PolicyResult,
    bundle_id: str,
    bundle_version: str,
    config: MfBundlePublisherConfig,
) -> dict[str, Any]:
    required_capabilities = _required_capabilities_from_gate(phase5_result=phase5_result)
    payload = {
        "schema_version": "learning.bundle_publication.v0",
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
        "dataset_manifest_refs": [item.manifest_ref for item in plan.dataset_manifests],
        "eval_report_ref": phase5_result.publish_eligibility.eval_report_ref,
        "compatibility": {
            "feature_set_id": plan.training_profile.feature_set_id,
            "feature_set_version": plan.training_profile.feature_set_version,
            "input_contract_version": _text_or_empty(plan.training_profile.expected_manifest_schema_version)
            or config.input_contract_version,
            "required_capabilities": required_capabilities,
        },
        "provenance": {
            "mf_code_release_id": _required_text(
                plan.input_refs.get("mf_code_release_id"),
                code="BUNDLE_PUBLICATION_INVALID",
                field_name="input_refs.mf_code_release_id",
            ),
            "config_revision": _required_text(
                plan.input_refs.get("config_revision"),
                code="BUNDLE_PUBLICATION_INVALID",
                field_name="input_refs.config_revision",
            ),
        },
    }
    run_config_digest = _text_or_empty(plan.input_refs.get("run_config_digest"))
    if run_config_digest:
        payload["provenance"]["run_config_digest"] = run_config_digest
    return _normalize_mapping(payload)


def _required_capabilities_from_gate(*, phase5_result: MfPhase5PolicyResult) -> list[str]:
    capabilities: list[str] = []
    thresholds = phase5_result.gate_receipt.gate_thresholds
    if thresholds:
        capabilities.append("eval_thresholds_present")
    capabilities.append("pass_gate_required")
    return sorted(set(capabilities))


def _registry_lifecycle_payload(
    *,
    plan: ResolvedTrainPlan,
    bundle_id: str,
    bundle_version: str,
    registry_bundle_ref: str,
    published_at_utc: str,
    phase5_result: MfPhase5PolicyResult,
    config: MfBundlePublisherConfig,
) -> dict[str, Any]:
    scope = {
        "environment": plan.input_refs.get("target_scope", {}).get("environment")
        if isinstance(plan.input_refs.get("target_scope"), Mapping)
        else "local_parity",
        "mode": plan.input_refs.get("target_scope", {}).get("mode")
        if isinstance(plan.input_refs.get("target_scope"), Mapping)
        else "fraud",
        "bundle_slot": plan.input_refs.get("target_scope", {}).get("bundle_slot")
        if isinstance(plan.input_refs.get("target_scope"), Mapping)
        else "primary",
    }
    # target_scope is not in current Phase 3 input_refs; derive sane defaults from request intent path.
    if not _text_or_empty(scope["environment"]):
        scope["environment"] = "local_parity"
    if not _text_or_empty(scope["mode"]):
        scope["mode"] = "fraud"
    if not _text_or_empty(scope["bundle_slot"]):
        scope["bundle_slot"] = "primary"
    registry_event_id = f"reg_evt_{_sha256_payload({'bundle_id': bundle_id, 'bundle_version': bundle_version})[:24]}"
    return _normalize_mapping(
        {
            "schema_version": "learning.registry_lifecycle.v0",
            "registry_event_id": registry_event_id,
            "event_type": "BUNDLE_PUBLISHED",
            "scope_key": scope,
            "bundle_ref": {
                "bundle_id": bundle_id,
                "bundle_version": bundle_version,
                "registry_ref": registry_bundle_ref,
            },
            "actor": {
                "actor_id": config.system_actor_id,
                "source_type": "SYSTEM",
            },
            "ts_utc": published_at_utc,
            "evidence_refs": [
                {"ref_type": "mf_gate_receipt", "ref_id": phase5_result.gate_receipt_ref},
                {"ref_type": "mf_eval_report", "ref_id": phase5_result.publish_eligibility.eval_report_ref},
                {"ref_type": "mf_publish_eligibility", "ref_id": phase5_result.publish_eligibility_ref},
            ],
        }
    )


def _write_json_immutable(
    *,
    store: ObjectStore,
    config: MfBundlePublisherConfig,
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
            raise MfPhase6PublishError(drift_code, f"immutable artifact drift at {relative_path}")
        return _artifact_ref(config, relative_path)


def _build_store(config: MfBundlePublisherConfig) -> ObjectStore:
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


def _artifact_ref(config: MfBundlePublisherConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


def _read_json_ref(
    *,
    ref: str,
    store: ObjectStore,
    config: MfBundlePublisherConfig,
    code: str,
) -> dict[str, Any]:
    value = _text_or_empty(ref)
    if not value:
        raise MfPhase6PublishError(code, "artifact ref is required")
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
            raise MfPhase6PublishError(code, str(exc)) from exc
    path = Path(value)
    try:
        if path.is_absolute():
            return json.loads(path.read_text(encoding="utf-8"))
        return store.read_json(value)
    except Exception as exc:  # noqa: BLE001
        raise MfPhase6PublishError(code, str(exc)) from exc


def _required_text(value: Any, *, code: str, field_name: str) -> str:
    text = _text_or_empty(value)
    if not text:
        raise MfPhase6PublishError(code, f"{field_name} is required")
    return text


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


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
