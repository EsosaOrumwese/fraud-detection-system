from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from engine.layers.l1.seg_1A.s7_integer_allocation.policy import (
    IntegerisationPolicy,
    PolicyLoadingError,
    load_policy,
)


def _write_yaml(path: Path, payload: str) -> Path:
    path.write_text(payload, encoding="utf-8")
    return path


def test_load_policy_with_bounds_and_dirichlet(tmp_path: Path) -> None:
    bounds_path = _write_yaml(
        tmp_path / "policy.s7.bounds.yaml",
        (
            "policy_semver: '1.0.0'\n"
            "version: '2025-10-16'\n"
            "dp_resid: 8\n"
            "floors:\n"
            "  US: 1\n"
            "ceilings:\n"
            "  US: 5\n"
        ),
    )
    policy_path = _write_yaml(
        tmp_path / "s7_integerisation_policy.yaml",
        (
            "policy_semver: '1.2.3'\n"
            "policy_version: '2025-10-16'\n"
            "dp_resid: 8\n"
            "dirichlet_lane:\n"
            "  enabled: true\n"
            "  alpha0: 2.5\n"
            "bounds_lane:\n"
            "  enabled: true\n"
            f"  policy_path: '{bounds_path.as_posix()}'\n"
        ),
    )

    policy = load_policy(policy_path)

    assert isinstance(policy, IntegerisationPolicy)
    assert policy.dirichlet_enabled is True
    assert policy.dirichlet_alpha0 == pytest.approx(2.5)
    assert policy.bounds_enabled is True
    assert policy.bounds is not None
    assert policy.bounds.path == bounds_path.resolve()
    assert policy.bounds.lower_bound("US") == 1
    assert policy.bounds.upper_bound("US") == 5
    assert policy.bounds.upper_bound("DE") is None

    digests = policy.digests
    assert str(bounds_path.resolve()) in digests
    expected_digest = hashlib.sha256(bounds_path.read_bytes()).hexdigest()
    assert digests[str(bounds_path.resolve())] == expected_digest


def test_load_policy_requires_alpha_when_dirichlet_enabled(tmp_path: Path) -> None:
    policy_path = _write_yaml(
        tmp_path / "s7_integerisation_policy.yaml",
        (
            "policy_semver: '1.0.0'\n"
            "policy_version: '2025-10-16'\n"
            "dirichlet_lane:\n"
            "  enabled: true\n"
        ),
    )

    with pytest.raises(PolicyLoadingError):
        load_policy(policy_path)
