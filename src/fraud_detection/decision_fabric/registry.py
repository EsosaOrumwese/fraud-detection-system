"""Decision Fabric registry resolution + compatibility gate (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from .posture import DfPostureStamp


RESOLUTION_RESOLVED = "RESOLVED"
RESOLUTION_FALLBACK = "FALLBACK"
RESOLUTION_FAIL_CLOSED = "FAIL_CLOSED"


class DecisionFabricRegistryError(ValueError):
    """Raised when DF registry policy/snapshot/resolution inputs are invalid."""


@dataclass(frozen=True)
class RegistryScopeKey:
    environment: str
    mode: str
    bundle_slot: str
    tenant_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "environment": self.environment,
            "mode": self.mode,
            "bundle_slot": self.bundle_slot,
        }
        if self.tenant_id:
            payload["tenant_id"] = self.tenant_id
        return payload

    def canonical_key(self) -> str:
        tenant = self.tenant_id or ""
        return "|".join([self.environment, self.mode, self.bundle_slot, tenant])

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RegistryScopeKey":
        environment = _non_empty(payload.get("environment"), "scope.environment")
        mode = _non_empty(payload.get("mode"), "scope.mode")
        bundle_slot = _non_empty(payload.get("bundle_slot"), "scope.bundle_slot")
        tenant = str(payload.get("tenant_id") or "").strip() or None
        return cls(environment=environment, mode=mode, bundle_slot=bundle_slot, tenant_id=tenant)


@dataclass(frozen=True)
class RegistryCompatibility:
    required_feature_groups: tuple[tuple[str, str], ...]
    require_ieg: bool
    require_model_primary: bool
    require_model_stage2: bool
    require_fallback_heuristics: bool
    required_action_posture: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RegistryCompatibility":
        groups_payload = payload.get("required_feature_groups") or {}
        if not isinstance(groups_payload, Mapping):
            raise DecisionFabricRegistryError("required_feature_groups must be a mapping")
        groups: list[tuple[str, str]] = []
        for key, value in groups_payload.items():
            name = _non_empty(key, "required_feature_groups.name")
            version = _non_empty(value, f"required_feature_groups.{name}")
            groups.append((name, version))
        required_action_posture = str(payload.get("required_action_posture") or "NORMAL").strip().upper()
        if required_action_posture not in {"NORMAL", "STEP_UP_ONLY"}:
            raise DecisionFabricRegistryError(
                "required_action_posture must be one of NORMAL, STEP_UP_ONLY"
            )
        return cls(
            required_feature_groups=tuple(sorted(groups)),
            require_ieg=bool(payload.get("require_ieg", False)),
            require_model_primary=bool(payload.get("require_model_primary", True)),
            require_model_stage2=bool(payload.get("require_model_stage2", False)),
            require_fallback_heuristics=bool(payload.get("require_fallback_heuristics", False)),
            required_action_posture=required_action_posture,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "required_feature_groups": {name: version for name, version in self.required_feature_groups},
            "require_ieg": self.require_ieg,
            "require_model_primary": self.require_model_primary,
            "require_model_stage2": self.require_model_stage2,
            "require_fallback_heuristics": self.require_fallback_heuristics,
            "required_action_posture": self.required_action_posture,
        }


@dataclass(frozen=True)
class RegistryPolicyRev:
    policy_id: str
    revision: str
    content_digest: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], *, field_name: str = "policy_rev") -> "RegistryPolicyRev":
        policy_id = _non_empty(payload.get("policy_id"), f"{field_name}.policy_id")
        revision = _non_empty(payload.get("revision"), f"{field_name}.revision")
        digest = str(payload.get("content_digest") or "").strip() or None
        return cls(policy_id=policy_id, revision=revision, content_digest=digest)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"policy_id": self.policy_id, "revision": self.revision}
        if self.content_digest:
            payload["content_digest"] = self.content_digest
        return payload


@dataclass(frozen=True)
class RegistryBundleRecord:
    scope_key: RegistryScopeKey
    bundle_ref: dict[str, str]
    compatibility: RegistryCompatibility
    registry_event_id: str
    activated_at_utc: str
    policy_rev: RegistryPolicyRev
    last_known_good_bundle_ref: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "scope": self.scope_key.as_dict(),
            "bundle_ref": dict(self.bundle_ref),
            "compatibility": self.compatibility.as_dict(),
            "registry_event_id": self.registry_event_id,
            "activated_at_utc": self.activated_at_utc,
            "policy_rev": self.policy_rev.as_dict(),
        }
        if self.last_known_good_bundle_ref:
            payload["last_known_good_bundle_ref"] = dict(self.last_known_good_bundle_ref)
        return payload


@dataclass(frozen=True)
class RegistrySnapshot:
    version: str
    snapshot_id: str
    generated_at_utc: str
    records_by_scope: dict[str, RegistryBundleRecord]
    snapshot_digest: str

    @classmethod
    def load(cls, path: Path) -> "RegistrySnapshot":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise DecisionFabricRegistryError("registry snapshot must be a mapping")
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RegistrySnapshot":
        version = _non_empty(payload.get("version"), "version")
        snapshot_id = _non_empty(payload.get("snapshot_id"), "snapshot_id")
        generated_at_utc = _non_empty(payload.get("generated_at_utc"), "generated_at_utc")
        records_payload = payload.get("records")
        if not isinstance(records_payload, list):
            raise DecisionFabricRegistryError("records must be a list")

        records_by_scope: dict[str, RegistryBundleRecord] = {}
        for index, item in enumerate(records_payload):
            if not isinstance(item, Mapping):
                raise DecisionFabricRegistryError(f"records[{index}] must be a mapping")
            record = _parse_record(item)
            scope_key = record.scope_key.canonical_key()
            if scope_key in records_by_scope:
                raise DecisionFabricRegistryError(f"duplicate active scope in snapshot: {scope_key}")
            records_by_scope[scope_key] = record

        canonical = _canonical_json(
            {
                "version": version,
                "snapshot_id": snapshot_id,
                "generated_at_utc": generated_at_utc,
                "records": [records_by_scope[key].as_dict() for key in sorted(records_by_scope)],
            }
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(
            version=version,
            snapshot_id=snapshot_id,
            generated_at_utc=generated_at_utc,
            records_by_scope=records_by_scope,
            snapshot_digest=digest,
        )


@dataclass(frozen=True)
class RegistryResolutionPolicy:
    version: str
    policy_rev: RegistryPolicyRev
    scope_axes: tuple[str, ...]
    require_feature_contract: bool
    require_capability_contract: bool
    allow_last_known_good: bool
    explicit_fallback_by_scope: dict[str, dict[str, str]]
    content_digest: str

    @classmethod
    def load(cls, path: Path) -> "RegistryResolutionPolicy":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise DecisionFabricRegistryError("registry resolution policy must be a mapping")
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RegistryResolutionPolicy":
        version = _non_empty(payload.get("version"), "version")
        policy_id = _non_empty(payload.get("policy_id"), "policy_id")
        revision = _non_empty(payload.get("revision"), "revision")
        scope_axes_payload = payload.get("scope_axes")
        if not isinstance(scope_axes_payload, list) or not scope_axes_payload:
            raise DecisionFabricRegistryError("scope_axes must be a non-empty list")
        scope_axes = tuple(str(item).strip() for item in scope_axes_payload if str(item).strip())
        expected_scope_axes = ("environment", "mode", "bundle_slot", "tenant_id")
        if scope_axes != expected_scope_axes:
            raise DecisionFabricRegistryError(
                f"scope_axes must be exactly {expected_scope_axes}; got {scope_axes}"
            )

        compatibility = payload.get("compatibility") or {}
        if not isinstance(compatibility, Mapping):
            raise DecisionFabricRegistryError("compatibility must be a mapping")
        require_feature_contract = bool(compatibility.get("require_feature_contract", True))
        require_capability_contract = bool(compatibility.get("require_capability_contract", True))

        fallback = payload.get("fallback") or {}
        if not isinstance(fallback, Mapping):
            raise DecisionFabricRegistryError("fallback must be a mapping")
        allow_last_known_good = bool(fallback.get("allow_last_known_good", False))
        explicit_payload = fallback.get("explicit_by_scope") or {}
        if not isinstance(explicit_payload, Mapping):
            raise DecisionFabricRegistryError("fallback.explicit_by_scope must be a mapping")
        explicit_by_scope: dict[str, dict[str, str]] = {}
        for raw_scope, raw_bundle in explicit_payload.items():
            scope_key = str(raw_scope).strip()
            if not scope_key:
                raise DecisionFabricRegistryError("fallback.explicit_by_scope contains empty scope key")
            explicit_by_scope[scope_key] = _parse_bundle_ref(raw_bundle, field_name=f"fallback.explicit_by_scope.{scope_key}")

        digest_payload = {
            "version": version,
            "policy_id": policy_id,
            "revision": revision,
            "scope_axes": list(scope_axes),
            "compatibility": {
                "require_feature_contract": require_feature_contract,
                "require_capability_contract": require_capability_contract,
            },
            "fallback": {
                "allow_last_known_good": allow_last_known_good,
                "explicit_by_scope": {key: explicit_by_scope[key] for key in sorted(explicit_by_scope)},
            },
        }
        canonical = _canonical_json(digest_payload)
        content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(
            version=version,
            policy_rev=RegistryPolicyRev(policy_id=policy_id, revision=revision, content_digest=content_digest),
            scope_axes=scope_axes,
            require_feature_contract=require_feature_contract,
            require_capability_contract=require_capability_contract,
            allow_last_known_good=allow_last_known_good,
            explicit_fallback_by_scope=explicit_by_scope,
            content_digest=content_digest,
        )


@dataclass(frozen=True)
class RegistryResolutionResult:
    outcome: str
    scope_key: RegistryScopeKey
    bundle_ref: dict[str, str] | None
    resolved_via: str
    reason_codes: tuple[str, ...]
    registry_event_id: str | None
    compatibility: dict[str, Any]
    policy_rev: RegistryPolicyRev
    snapshot_digest: str
    basis_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "scope_key": self.scope_key.as_dict(),
            "bundle_ref": None if self.bundle_ref is None else dict(self.bundle_ref),
            "resolved_via": self.resolved_via,
            "reason_codes": list(self.reason_codes),
            "registry_event_id": self.registry_event_id,
            "compatibility": self.compatibility,
            "policy_rev": self.policy_rev.as_dict(),
            "snapshot_digest": self.snapshot_digest,
            "basis_digest": self.basis_digest,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.as_dict())

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass
class RegistryResolver:
    policy: RegistryResolutionPolicy
    snapshot: RegistrySnapshot

    def resolve(
        self,
        *,
        scope_key: RegistryScopeKey,
        posture: DfPostureStamp,
        feature_group_versions: Mapping[str, str],
    ) -> RegistryResolutionResult:
        canonical_scope = scope_key.canonical_key()
        record = self.snapshot.records_by_scope.get(canonical_scope)
        if record is None:
            return self._fallback_or_fail(
                scope_key=scope_key,
                record=None,
                posture=posture,
                feature_group_versions=feature_group_versions,
                base_reasons=("SCOPE_NOT_FOUND",),
                compatibility={"scope_found": False},
            )

        compatibility = _evaluate_compatibility(
            record=record,
            posture=posture,
            feature_group_versions=feature_group_versions,
            require_feature_contract=self.policy.require_feature_contract,
            require_capability_contract=self.policy.require_capability_contract,
        )
        if compatibility["compatible"]:
            return self._build_result(
                outcome=RESOLUTION_RESOLVED,
                scope_key=scope_key,
                bundle_ref=record.bundle_ref,
                resolved_via="ACTIVE",
                reason_codes=("ACTIVE_BUNDLE_RESOLVED",),
                registry_event_id=record.registry_event_id,
                compatibility=compatibility,
                posture=posture,
                feature_group_versions=feature_group_versions,
            )

        reasons = tuple(sorted({"ACTIVE_BUNDLE_INCOMPATIBLE", *compatibility["reason_codes"]}))
        return self._fallback_or_fail(
            scope_key=scope_key,
            record=record,
            posture=posture,
            feature_group_versions=feature_group_versions,
            base_reasons=reasons,
            compatibility=compatibility,
        )

    def _fallback_or_fail(
        self,
        *,
        scope_key: RegistryScopeKey,
        record: RegistryBundleRecord | None,
        posture: DfPostureStamp,
        feature_group_versions: Mapping[str, str],
        base_reasons: tuple[str, ...],
        compatibility: dict[str, Any],
    ) -> RegistryResolutionResult:
        scope_token = scope_key.canonical_key()
        explicit = self.policy.explicit_fallback_by_scope.get(scope_token)
        if explicit is not None:
            reasons = tuple(sorted({"FALLBACK_EXPLICIT", *base_reasons}))
            return self._build_result(
                outcome=RESOLUTION_FALLBACK,
                scope_key=scope_key,
                bundle_ref=explicit,
                resolved_via="FALLBACK_EXPLICIT",
                reason_codes=reasons,
                registry_event_id=None if record is None else record.registry_event_id,
                compatibility=compatibility,
                posture=posture,
                feature_group_versions=feature_group_versions,
            )

        if self.policy.allow_last_known_good and record is not None and record.last_known_good_bundle_ref is not None:
            reasons = tuple(sorted({"FALLBACK_LAST_KNOWN_GOOD", *base_reasons}))
            return self._build_result(
                outcome=RESOLUTION_FALLBACK,
                scope_key=scope_key,
                bundle_ref=record.last_known_good_bundle_ref,
                resolved_via="FALLBACK_LAST_KNOWN_GOOD",
                reason_codes=reasons,
                registry_event_id=record.registry_event_id,
                compatibility=compatibility,
                posture=posture,
                feature_group_versions=feature_group_versions,
            )

        reasons = tuple(sorted({"FAIL_CLOSED_NO_COMPATIBLE_BUNDLE", *base_reasons}))
        return self._build_result(
            outcome=RESOLUTION_FAIL_CLOSED,
            scope_key=scope_key,
            bundle_ref=None,
            resolved_via="FAIL_CLOSED",
            reason_codes=reasons,
            registry_event_id=None if record is None else record.registry_event_id,
            compatibility=compatibility,
            posture=posture,
            feature_group_versions=feature_group_versions,
        )

    def _build_result(
        self,
        *,
        outcome: str,
        scope_key: RegistryScopeKey,
        bundle_ref: dict[str, str] | None,
        resolved_via: str,
        reason_codes: tuple[str, ...],
        registry_event_id: str | None,
        compatibility: dict[str, Any],
        posture: DfPostureStamp,
        feature_group_versions: Mapping[str, str],
    ) -> RegistryResolutionResult:
        basis = {
            "scope_key": scope_key.as_dict(),
            "posture_digest": posture.digest(),
            "feature_group_versions": {
                key: str(feature_group_versions[key]) for key in sorted(feature_group_versions)
            },
            "snapshot_digest": self.snapshot.snapshot_digest,
            "policy_rev": self.policy.policy_rev.as_dict(),
        }
        basis_digest = hashlib.sha256(_canonical_json(basis).encode("utf-8")).hexdigest()
        return RegistryResolutionResult(
            outcome=outcome,
            scope_key=scope_key,
            bundle_ref=bundle_ref,
            resolved_via=resolved_via,
            reason_codes=tuple(sorted(set(reason_codes))),
            registry_event_id=registry_event_id,
            compatibility=compatibility,
            policy_rev=self.policy.policy_rev,
            snapshot_digest=self.snapshot.snapshot_digest,
            basis_digest=basis_digest,
        )


def _evaluate_compatibility(
    *,
    record: RegistryBundleRecord,
    posture: DfPostureStamp,
    feature_group_versions: Mapping[str, str],
    require_feature_contract: bool,
    require_capability_contract: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    feature_mismatches: list[str] = []
    missing_features: list[str] = []
    capability_blocks: list[str] = []

    if require_feature_contract:
        for group_name, required_version in record.compatibility.required_feature_groups:
            actual = feature_group_versions.get(group_name)
            if actual is None:
                missing_features.append(group_name)
                reasons.append(f"FEATURE_GROUP_MISSING:{group_name}")
                continue
            if str(actual) != str(required_version):
                feature_mismatches.append(f"{group_name}:{actual}!={required_version}")
                reasons.append(f"FEATURE_GROUP_VERSION_MISMATCH:{group_name}")

    if require_capability_contract:
        mask = posture.capabilities_mask
        if record.compatibility.require_ieg and not mask.allow_ieg:
            capability_blocks.append("allow_ieg")
            reasons.append("CAPABILITY_MISMATCH:allow_ieg")
        if record.compatibility.require_model_primary and not mask.allow_model_primary:
            capability_blocks.append("allow_model_primary")
            reasons.append("CAPABILITY_MISMATCH:allow_model_primary")
        if record.compatibility.require_model_stage2 and not mask.allow_model_stage2:
            capability_blocks.append("allow_model_stage2")
            reasons.append("CAPABILITY_MISMATCH:allow_model_stage2")
        if record.compatibility.require_fallback_heuristics and not mask.allow_fallback_heuristics:
            capability_blocks.append("allow_fallback_heuristics")
            reasons.append("CAPABILITY_MISMATCH:allow_fallback_heuristics")
        if (
            record.compatibility.required_action_posture == "NORMAL"
            and mask.action_posture != "NORMAL"
        ):
            capability_blocks.append("action_posture")
            reasons.append("CAPABILITY_MISMATCH:action_posture")

    compatible = not reasons
    return {
        "compatible": compatible,
        "reason_codes": tuple(sorted(set(reasons))),
        "missing_features": sorted(missing_features),
        "feature_mismatches": sorted(feature_mismatches),
        "capability_blocks": sorted(capability_blocks),
    }


def _parse_record(payload: Mapping[str, Any]) -> RegistryBundleRecord:
    scope_payload = payload.get("scope")
    if not isinstance(scope_payload, Mapping):
        raise DecisionFabricRegistryError("record.scope must be a mapping")
    bundle_ref = _parse_bundle_ref(payload.get("bundle_ref"), field_name="record.bundle_ref")
    compatibility_payload = payload.get("compatibility") or {}
    if not isinstance(compatibility_payload, Mapping):
        raise DecisionFabricRegistryError("record.compatibility must be a mapping")
    registry_event_id = _non_empty(payload.get("registry_event_id"), "record.registry_event_id")
    activated_at_utc = _non_empty(payload.get("activated_at_utc"), "record.activated_at_utc")
    policy_payload = payload.get("policy_rev") or {}
    if not isinstance(policy_payload, Mapping):
        raise DecisionFabricRegistryError("record.policy_rev must be a mapping")
    lkg = payload.get("last_known_good_bundle_ref")
    last_known_good = None
    if lkg is not None:
        last_known_good = _parse_bundle_ref(lkg, field_name="record.last_known_good_bundle_ref")
    return RegistryBundleRecord(
        scope_key=RegistryScopeKey.from_payload(scope_payload),
        bundle_ref=bundle_ref,
        compatibility=RegistryCompatibility.from_payload(compatibility_payload),
        registry_event_id=registry_event_id,
        activated_at_utc=activated_at_utc,
        policy_rev=RegistryPolicyRev.from_payload(policy_payload, field_name="record.policy_rev"),
        last_known_good_bundle_ref=last_known_good,
    )


def _parse_bundle_ref(value: Any, *, field_name: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise DecisionFabricRegistryError(f"{field_name} must be a mapping")
    bundle_id = _non_empty(value.get("bundle_id"), f"{field_name}.bundle_id")
    bundle_version = str(value.get("bundle_version") or "").strip()
    registry_ref = str(value.get("registry_ref") or "").strip()
    payload = {"bundle_id": bundle_id}
    if bundle_version:
        payload["bundle_version"] = bundle_version
    if registry_ref:
        payload["registry_ref"] = registry_ref
    return payload


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionFabricRegistryError(f"{field_name} must be a non-empty string")
    return text


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
