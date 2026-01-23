from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine.layers.l1.seg_1A.s6_foreign_selection.policy import (
    PolicyValidationError,
    SelectionPolicy,
    load_policy,
)


def test_load_policy_defaults(tmp_path):
    policy_path = Path("config/layer1/1A/policy.s6.selection.yaml").resolve()
    policy = load_policy(policy_path)

    assert isinstance(policy, SelectionPolicy)
    assert policy.log_all_candidates is True
    assert policy.emit_membership_dataset is False

    usd_overrides = policy.resolve_for_currency("USD")
    assert usd_overrides.emit_membership_dataset is True
    assert usd_overrides.max_candidates_cap == 10
    assert usd_overrides.zero_weight_rule == "exclude"


def test_policy_validation_rejects_unknown_keys(tmp_path):
    payload = {
        "policy_semver": "0.1.0",
        "policy_version": "2025-10-16",
        "defaults": {
            "emit_membership_dataset": False,
            "log_all_candidates": True,
            "max_candidates_cap": 0,
            "zero_weight_rule": "exclude",
        },
        "per_currency": {
            "EUR": {"unknown": True}
        },
    }
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(PolicyValidationError):
        load_policy(path)
