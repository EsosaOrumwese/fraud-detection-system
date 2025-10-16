from __future__ import annotations

import textwrap

import pytest

from engine.layers.l1.seg_1A.s5_currency_weights.policy import (
    load_policy,
    PolicyValidationError,
)


def test_load_policy_success(tmp_path):
    path = _write_policy(
        tmp_path,
        """
        semver: "1.2.3"
        version: "2025-10-16"
        dp: 6
        defaults:
          blend_weight: 0.6
          alpha: 1.0
          obs_floor: 200
          min_share: 0.0005
          shrink_exponent: 1.0
        per_currency:
          USD:
            alpha: 1.5
            obs_floor: 400
        overrides:
          alpha_iso:
            USD:
              PR: 1.1
          min_share_iso:
            USD:
              PR: 0.05
        """,
    )

    policy = load_policy(path)

    assert policy.semver == "1.2.3"
    assert policy.version == "2025-10-16"
    assert policy.dp == 6
    assert pytest.approx(policy.defaults.blend_weight) == 0.6
    assert policy.per_currency["USD"].obs_floor == 400
    assert pytest.approx(policy.alpha_iso["USD"]["PR"]) == 1.1
    assert pytest.approx(policy.min_share_iso["USD"]["PR"]) == 0.05


def test_unknown_top_level_key(tmp_path):
    path = _write_policy(
        tmp_path,
        """
        semver: "1.0.0"
        version: "2025-10-16"
        dp: 4
        defaults:
          blend_weight: 0.5
          alpha: 1.0
          obs_floor: 10
          min_share: 0.001
          shrink_exponent: 1.0
        per_currency: {}
        overrides:
          alpha_iso: {}
          min_share_iso: {}
        unexpected: {}
        """,
    )

    with pytest.raises(PolicyValidationError, match="unknown top-level keys"):
        load_policy(path)


def test_invalid_semver(tmp_path):
    path = _write_policy(
        tmp_path,
        """
        semver: "1.0"
        version: "2025-10-16"
        dp: 4
        defaults:
          blend_weight: 0.5
          alpha: 1.0
          obs_floor: 10
          min_share: 0.001
          shrink_exponent: 1.0
        per_currency: {}
        overrides:
          alpha_iso: {}
          min_share_iso: {}
        """,
    )

    with pytest.raises(PolicyValidationError, match="semver must match"):
        load_policy(path)


def test_invalid_default_range(tmp_path):
    path = _write_policy(
        tmp_path,
        """
        semver: "1.0.0"
        version: "2025-10-16"
        dp: 4
        defaults:
          blend_weight: 1.2
          alpha: 1.0
          obs_floor: 10
          min_share: 0.001
          shrink_exponent: 1.0
        per_currency: {}
        overrides:
          alpha_iso: {}
          min_share_iso: {}
        """,
    )

    with pytest.raises(PolicyValidationError, match="defaults.blend_weight"):
        load_policy(path)


def test_min_share_sum_validation(tmp_path):
    path = _write_policy(
        tmp_path,
        """
        semver: "1.0.0"
        version: "2025-10-16"
        dp: 2
        defaults:
          blend_weight: 0.5
          alpha: 1.0
          obs_floor: 10
          min_share: 0.001
          shrink_exponent: 1.0
        per_currency: {}
        overrides:
          alpha_iso: {}
          min_share_iso:
            USD:
              US: 0.6
              PR: 0.5
        """,
    )

    with pytest.raises(PolicyValidationError, match="exceeds 1.0"):
        load_policy(path)


def _write_policy(tmp_path, text: str):
    path = tmp_path / "ccy_smoothing_params.yaml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path
