from __future__ import annotations

import textwrap

import pytest

from engine.layers.l1.seg_1A.s5_currency_weights.builder import build_weights
from engine.layers.l1.seg_1A.s5_currency_weights.loader import ShareSurface
from engine.layers.l1.seg_1A.s5_currency_weights.policy import load_policy


_BASE_POLICY = """
semver: "1.0.0"
version: "2025-10-16"
dp: 4
defaults:
  blend_weight: 0.5
  alpha: 0.0
  obs_floor: 0
  min_share: 0.0
  shrink_exponent: 1.0
per_currency: {}
overrides:
  alpha_iso: {}
  min_share_iso: {}
"""


def test_basic_blend(tmp_path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(textwrap.dedent(_BASE_POLICY), encoding="utf-8")
    policy = load_policy(policy_path)

    settlement = [
        ShareSurface(currency="USD", country_iso="US", share=0.7, obs_count=100),
        ShareSurface(currency="USD", country_iso="CA", share=0.3, obs_count=100),
    ]
    ccy = [
        ShareSurface(currency="USD", country_iso="US", share=0.6, obs_count=50),
        ShareSurface(currency="USD", country_iso="CA", share=0.4, obs_count=50),
    ]

    results = build_weights(settlement, ccy, policy)
    assert len(results) == 1
    usd_result = results[0]
    weights = {row.country_iso: row.weight for row in usd_result.weights}

    assert pytest.approx(weights["US"], abs=1e-9) == 0.65
    assert pytest.approx(weights["CA"], abs=1e-9) == 0.35
    assert usd_result.degrade_mode == "none"


def test_degrade_when_one_surface_missing(tmp_path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(textwrap.dedent(_BASE_POLICY), encoding="utf-8")
    policy = load_policy(policy_path)

    settlement = []
    ccy = [
        ShareSurface(currency="EUR", country_iso="DE", share=0.8, obs_count=20),
        ShareSurface(currency="EUR", country_iso="FR", share=0.2, obs_count=20),
    ]

    results = build_weights(settlement, ccy, policy)
    assert len(results) == 1
    eur_result = results[0]
    assert eur_result.degrade_mode == "ccy_only"
    assert eur_result.degrade_reason == "SRC_MISSING_SETTLEMENT"
    weights = {row.country_iso: row.weight for row in eur_result.weights}
    assert pytest.approx(sum(weights.values()), abs=1e-12) == 1.0


def test_min_share_floor(tmp_path):
    policy_yaml = """
    semver: "1.0.0"
    version: "2025-10-16"
    dp: 3
    defaults:
      blend_weight: 0.5
      alpha: 0.0
      obs_floor: 0
      min_share: 0.05
      shrink_exponent: 1.0
    per_currency: {}
    overrides:
      alpha_iso: {}
      min_share_iso:
        USD:
          CA: 0.30
    """
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(textwrap.dedent(policy_yaml), encoding="utf-8")
    policy = load_policy(policy_path)

    settlement = [
        ShareSurface(currency="USD", country_iso="US", share=0.95, obs_count=10),
        ShareSurface(currency="USD", country_iso="CA", share=0.05, obs_count=10),
    ]
    ccy = [
        ShareSurface(currency="USD", country_iso="US", share=0.9, obs_count=10),
        ShareSurface(currency="USD", country_iso="CA", share=0.1, obs_count=10),
    ]

    results = build_weights(settlement, ccy, policy)
    weights = {row.country_iso: row.weight for row in results[0].weights}
    assert weights["CA"] >= 0.3
    assert pytest.approx(sum(weights.values()), abs=1e-12) == 1.0
