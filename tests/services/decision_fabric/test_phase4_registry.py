from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.decision_fabric.posture import DfPostureStamp
from fraud_detection.decision_fabric.registry import (
    RESOLUTION_FAIL_CLOSED,
    RESOLUTION_FALLBACK,
    RESOLUTION_RESOLVED,
    DecisionFabricRegistryError,
    RegistryCompatibility,
    RegistryPolicyRev,
    RegistryResolutionPolicy,
    RegistryResolver,
    RegistryScopeKey,
    RegistrySnapshot,
)
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, PolicyRev


def _scope(*, mode: str = "fraud") -> RegistryScopeKey:
    return RegistryScopeKey(environment="local_parity", mode=mode, bundle_slot="primary")


def _posture_stamp(
    *,
    allow_ieg: bool = True,
    allow_model_primary: bool = True,
    allow_model_stage2: bool = True,
    allow_fallback_heuristics: bool = True,
    action_posture: str = "NORMAL",
) -> DfPostureStamp:
    return DfPostureStamp(
        scope_key="scope=GLOBAL",
        mode="NORMAL",
        capabilities_mask=CapabilitiesMask(
            allow_ieg=allow_ieg,
            allowed_feature_groups=("core_features", "velocity"),
            allow_model_primary=allow_model_primary,
            allow_model_stage2=allow_model_stage2,
            allow_fallback_heuristics=allow_fallback_heuristics,
            action_posture=action_posture,
        ),
        policy_rev=PolicyRev(policy_id="dl.policy.v0", revision="r1", content_digest="a" * 64),
        posture_seq=10,
        decided_at_utc="2026-02-07T11:12:00.000000Z",
        source="CURRENT_POSTURE",
        trust_state="TRUSTED",
        served_at_utc="2026-02-07T11:12:01.000000Z",
        reasons=("DL_SOURCE:CURRENT_POSTURE",),
    )


def _policy_payload() -> dict[str, object]:
    return {
        "version": "0.1.0",
        "policy_id": "df.registry_resolution.v0",
        "revision": "r1",
        "scope_axes": ["environment", "mode", "bundle_slot", "tenant_id"],
        "compatibility": {
            "require_feature_contract": True,
            "require_capability_contract": True,
        },
        "fallback": {"allow_last_known_good": False, "explicit_by_scope": {}},
    }


def _record_payload(*, compatibility: dict[str, object], scope: RegistryScopeKey | None = None) -> dict[str, object]:
    resolved_scope = scope or _scope()
    return {
        "scope": resolved_scope.as_dict(),
        "bundle_ref": {
            "bundle_id": "b" * 64,
            "bundle_version": "2026.02.07",
            "registry_ref": "registry://active/local_parity/fraud/primary",
        },
        "compatibility": compatibility,
        "registry_event_id": "reg_evt_1001",
        "activated_at_utc": "2026-02-07T11:10:00.000000Z",
        "policy_rev": {"policy_id": "mpr.policy.v0", "revision": "r9", "content_digest": "c" * 64},
    }


def _snapshot_payload(*, records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "version": "0.1.0",
        "snapshot_id": "snapshot_001",
        "generated_at_utc": "2026-02-07T11:12:00.000000Z",
        "records": records,
    }


def test_registry_resolution_policy_load_is_stable() -> None:
    path = Path("config/platform/df/registry_resolution_policy_v0.yaml")
    policy_a = RegistryResolutionPolicy.load(path)
    policy_b = RegistryResolutionPolicy.load(path)
    assert policy_a.policy_rev.policy_id == "df.registry_resolution.v0"
    assert policy_a.policy_rev.revision == "r1"
    assert policy_a.content_digest == policy_b.content_digest


def test_snapshot_rejects_duplicate_scope_records() -> None:
    compatibility = RegistryCompatibility(
        required_feature_groups=(("core_features", "v1"),),
        require_ieg=True,
        require_model_primary=True,
        require_model_stage2=False,
        require_fallback_heuristics=False,
        required_action_posture="NORMAL",
    ).as_dict()
    payload = _snapshot_payload(records=[_record_payload(compatibility=compatibility), _record_payload(compatibility=compatibility)])
    with pytest.raises(DecisionFabricRegistryError):
        RegistrySnapshot.from_payload(payload)


def test_resolver_is_deterministic_for_identical_basis() -> None:
    policy = RegistryResolutionPolicy.from_payload(_policy_payload())
    compatibility = RegistryCompatibility(
        required_feature_groups=(("core_features", "v1"),),
        require_ieg=True,
        require_model_primary=True,
        require_model_stage2=True,
        require_fallback_heuristics=False,
        required_action_posture="NORMAL",
    ).as_dict()
    snapshot = RegistrySnapshot.from_payload(_snapshot_payload(records=[_record_payload(compatibility=compatibility)]))
    resolver = RegistryResolver(policy=policy, snapshot=snapshot)
    result_a = resolver.resolve(
        scope_key=_scope(),
        posture=_posture_stamp(),
        feature_group_versions={"core_features": "v1"},
    )
    result_b = resolver.resolve(
        scope_key=_scope(),
        posture=_posture_stamp(),
        feature_group_versions={"core_features": "v1"},
    )
    assert result_a.outcome == RESOLUTION_RESOLVED
    assert result_a.digest() == result_b.digest()
    assert result_a.basis_digest == result_b.basis_digest


def test_resolver_has_no_implicit_latest_scope_fallback() -> None:
    policy = RegistryResolutionPolicy.from_payload(_policy_payload())
    compatibility = RegistryCompatibility(
        required_feature_groups=(("core_features", "v1"),),
        require_ieg=False,
        require_model_primary=True,
        require_model_stage2=False,
        require_fallback_heuristics=False,
        required_action_posture="NORMAL",
    ).as_dict()
    snapshot = RegistrySnapshot.from_payload(_snapshot_payload(records=[_record_payload(compatibility=compatibility, scope=_scope(mode="fraud"))]))
    resolver = RegistryResolver(policy=policy, snapshot=snapshot)
    result = resolver.resolve(
        scope_key=_scope(mode="baseline"),
        posture=_posture_stamp(),
        feature_group_versions={"core_features": "v1"},
    )
    assert result.outcome == RESOLUTION_FAIL_CLOSED
    assert "SCOPE_NOT_FOUND" in result.reason_codes


def test_capability_mismatch_fails_closed() -> None:
    policy = RegistryResolutionPolicy.from_payload(_policy_payload())
    compatibility = RegistryCompatibility(
        required_feature_groups=(("core_features", "v1"),),
        require_ieg=True,
        require_model_primary=True,
        require_model_stage2=True,
        require_fallback_heuristics=False,
        required_action_posture="NORMAL",
    ).as_dict()
    snapshot = RegistrySnapshot.from_payload(_snapshot_payload(records=[_record_payload(compatibility=compatibility)]))
    resolver = RegistryResolver(policy=policy, snapshot=snapshot)
    result = resolver.resolve(
        scope_key=_scope(),
        posture=_posture_stamp(allow_model_stage2=False),
        feature_group_versions={"core_features": "v1"},
    )
    assert result.outcome == RESOLUTION_FAIL_CLOSED
    assert "CAPABILITY_MISMATCH:allow_model_stage2" in result.reason_codes


def test_feature_version_mismatch_fails_closed() -> None:
    policy = RegistryResolutionPolicy.from_payload(_policy_payload())
    compatibility = RegistryCompatibility(
        required_feature_groups=(("core_features", "v2"),),
        require_ieg=False,
        require_model_primary=True,
        require_model_stage2=False,
        require_fallback_heuristics=False,
        required_action_posture="NORMAL",
    ).as_dict()
    snapshot = RegistrySnapshot.from_payload(_snapshot_payload(records=[_record_payload(compatibility=compatibility)]))
    resolver = RegistryResolver(policy=policy, snapshot=snapshot)
    result = resolver.resolve(
        scope_key=_scope(),
        posture=_posture_stamp(),
        feature_group_versions={"core_features": "v1"},
    )
    assert result.outcome == RESOLUTION_FAIL_CLOSED
    assert "FEATURE_GROUP_VERSION_MISMATCH:core_features" in result.reason_codes


def test_explicit_fallback_is_bounded_and_selected() -> None:
    scope_key = _scope()
    payload = _policy_payload()
    payload["fallback"] = {
        "allow_last_known_good": False,
        "explicit_by_scope": {
            scope_key.canonical_key(): {
                "bundle_id": "f" * 64,
                "bundle_version": "fallback.v1",
                "registry_ref": "registry://fallback/local_parity/fraud/primary",
            }
        },
    }
    policy = RegistryResolutionPolicy.from_payload(payload)
    compatibility = RegistryCompatibility(
        required_feature_groups=(("core_features", "v1"),),
        require_ieg=True,
        require_model_primary=True,
        require_model_stage2=True,
        require_fallback_heuristics=False,
        required_action_posture="NORMAL",
    ).as_dict()
    snapshot = RegistrySnapshot.from_payload(_snapshot_payload(records=[_record_payload(compatibility=compatibility)]))
    resolver = RegistryResolver(policy=policy, snapshot=snapshot)
    result = resolver.resolve(
        scope_key=scope_key,
        posture=_posture_stamp(allow_model_stage2=False),
        feature_group_versions={"core_features": "v1"},
    )
    assert result.outcome == RESOLUTION_FALLBACK
    assert result.resolved_via == "FALLBACK_EXPLICIT"
    assert "FALLBACK_EXPLICIT" in result.reason_codes
    assert result.bundle_ref is not None
    assert result.bundle_ref["bundle_version"] == "fallback.v1"
