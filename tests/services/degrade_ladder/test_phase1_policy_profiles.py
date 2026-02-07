from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.degrade_ladder.config import DlConfigError, load_policy_bundle
from fraud_detection.degrade_ladder.contracts import MODE_SEQUENCE


def _bundle_path() -> Path:
    return Path("config/platform/dl/policy_profiles_v0.yaml")


def test_policy_bundle_loads_all_environment_profiles() -> None:
    bundle = load_policy_bundle(_bundle_path())
    assert bundle.schema_version == "v1"
    assert bundle.policy_rev.policy_id == "dl.policy.v0"
    assert bundle.policy_rev.revision == "r1"
    assert set(bundle.profiles) == {"local", "local_parity", "dev", "prod"}


def test_each_profile_contains_full_mode_sequence_and_masks() -> None:
    bundle = load_policy_bundle(_bundle_path())
    for profile_id in ("local", "local_parity", "dev", "prod"):
        profile = bundle.profile(profile_id)
        assert profile.mode_sequence == MODE_SEQUENCE
        assert profile.signal_policy.required_max_age_seconds == 120
        assert set(profile.signal_policy.required_signals) == {
            "ofp_health",
            "ieg_health",
            "eb_consumer_lag",
            "registry_health",
            "posture_store_health",
        }
        for mode in MODE_SEQUENCE:
            assert mode in profile.modes
            mask = profile.modes[mode].capabilities_mask
            assert mask.action_posture in {"NORMAL", "STEP_UP_ONLY"}


def test_unknown_profile_raises_config_error() -> None:
    bundle = load_policy_bundle(_bundle_path())
    with pytest.raises(DlConfigError):
        bundle.profile("qa")
