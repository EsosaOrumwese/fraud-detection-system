from __future__ import annotations

from fraud_detection.decision_fabric.posture import DfPostureStamp
from fraud_detection.decision_fabric.registry import (
    RESOLUTION_FAIL_CLOSED,
    RegistryCompatibility,
    RegistryResolutionPolicy,
    RegistryResolver,
    RegistryScopeKey,
    RegistrySnapshot,
)
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, PolicyRev
from fraud_detection.decision_log_audit.intake import DLA_INTAKE_REPLAY_DIVERGENCE
from fraud_detection.platform_governance.anomaly_taxonomy import classify_anomaly


def test_anomaly_taxonomy_classifies_required_categories() -> None:
    assert classify_anomaly("PUBLISH_AMBIGUOUS") == "PUBLISH_AMBIGUOUS"
    assert classify_anomaly("REF_ACCESS_DENIED") == "REF_ACCESS_DENIED"
    assert classify_anomaly(DLA_INTAKE_REPLAY_DIVERGENCE) == "REPLAY_BASIS_MISMATCH"
    assert classify_anomaly("PINS_MISSING") == "SCHEMA_POLICY_MISSING"
    assert classify_anomaly("FEATURE_GROUP_VERSION_MISMATCH:core_features") == "INCOMPATIBILITY"


def test_registry_boundary_fail_closed_maps_to_incompatibility() -> None:
    policy = RegistryResolutionPolicy.from_payload(
        {
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
    )
    compatibility = RegistryCompatibility(
        required_feature_groups=(("core_features", "v2"),),
        require_ieg=False,
        require_model_primary=True,
        require_model_stage2=False,
        require_fallback_heuristics=False,
        required_action_posture="NORMAL",
    ).as_dict()
    snapshot = RegistrySnapshot.from_payload(
        {
            "version": "0.1.0",
            "snapshot_id": "snapshot_001",
            "generated_at_utc": "2026-02-07T11:12:00.000000Z",
            "records": [
                {
                    "scope": {
                        "environment": "local_parity",
                        "mode": "fraud",
                        "bundle_slot": "primary",
                    },
                    "bundle_ref": {
                        "bundle_id": "b" * 64,
                        "bundle_version": "2026.02.07",
                        "registry_ref": "registry://active/local_parity/fraud/primary",
                    },
                    "compatibility": compatibility,
                    "registry_event_id": "reg_evt_1001",
                    "activated_at_utc": "2026-02-07T11:10:00.000000Z",
                    "policy_rev": {
                        "policy_id": "mpr.policy.v0",
                        "revision": "r9",
                        "content_digest": "c" * 64,
                    },
                }
            ],
        }
    )
    resolver = RegistryResolver(policy=policy, snapshot=snapshot)
    result = resolver.resolve(
        scope_key=RegistryScopeKey(environment="local_parity", mode="fraud", bundle_slot="primary"),
        posture=DfPostureStamp(
            scope_key="scope=GLOBAL",
            mode="NORMAL",
            capabilities_mask=CapabilitiesMask(
                allow_ieg=True,
                allowed_feature_groups=("core_features",),
                allow_model_primary=True,
                allow_model_stage2=True,
                allow_fallback_heuristics=True,
                action_posture="NORMAL",
            ),
            policy_rev=PolicyRev(policy_id="dl.policy.v0", revision="r1", content_digest="a" * 64),
            posture_seq=1,
            decided_at_utc="2026-02-07T11:12:00.000000Z",
            source="CURRENT_POSTURE",
            trust_state="TRUSTED",
            served_at_utc="2026-02-07T11:12:01.000000Z",
            reasons=("DL_SOURCE:CURRENT_POSTURE",),
        ),
        feature_group_versions={"core_features": "v1"},
    )
    assert result.outcome == RESOLUTION_FAIL_CLOSED
    category = classify_anomaly(None, reason_codes=result.reason_codes)
    assert category == "INCOMPATIBILITY"
