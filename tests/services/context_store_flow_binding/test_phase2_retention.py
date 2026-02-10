from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.context_store_flow_binding.store import (
    ContextStoreFlowBindingStoreError,
    load_retention_profile,
)


def test_phase2_retention_profile_loads_local_parity() -> None:
    policy = load_retention_profile(
        Path("config/platform/context_store_flow_binding/retention_v0.yaml"),
        profile="local_parity",
    )
    assert policy.profile == "local_parity"
    assert policy.join_frame_days == 2
    assert policy.checkpoint_days == 14


def test_phase2_retention_profile_missing_fails_closed() -> None:
    with pytest.raises(ContextStoreFlowBindingStoreError):
        load_retention_profile(
            Path("config/platform/context_store_flow_binding/retention_v0.yaml"),
            profile="missing-profile",
        )
