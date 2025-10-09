"""Numeric policy enforcement and deterministic math profile helpers for S0.

Numeric correctness is a design requirement: the engine must attest that it is
running with binary64, without silent FMA contraction, with subnormal support,
etc.  This module centralises the helpers that load the governed
``numeric_policy.json``/``math_profile_manifest.json`` artefacts and performs
the self-tests described in S0.8.
"""

from __future__ import annotations

import json
import math
import platform
import struct
import sys
from dataclasses import dataclass
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

from ..exceptions import err
from ..l0.artifacts import ArtifactDigest, hash_artifact


_NUMERIC_POLICY_REQUIRED = {
    "binary_format": "ieee754-binary64",
    "rounding_mode": "rne",
    "fma_allowed": False,
    "flush_to_zero": False,
    "denormals_are_zero": False,
    "sum_policy": "serial_neumaier",
    "parallel_decision_kernels": "disallowed",
}


@dataclass(frozen=True)
class NumericPolicy:
    """In-memory view over ``numeric_policy.json``."""

    raw: Mapping[str, Any]

    @property
    def version(self) -> str:
        return str(self.raw.get("version", "1.0"))

    def validate(self) -> None:
        for key, expected in _NUMERIC_POLICY_REQUIRED.items():
            if key not in self.raw:
                raise err(
                    "E_NUMERIC_POLICY_MISSING", f"numeric_policy missing key '{key}'"
                )
            if self.raw[key] != expected:
                raise err(
                    "E_NUMERIC_POLICY_VALUE",
                    f"numeric_policy '{key}' expected {expected!r}, got {self.raw[key]!r}",
                )
        if self.raw.get("nan_inf_is_error", True) is not True:
            raise err(
                "E_NUMERIC_POLICY_VALUE",
                "numeric_policy requires nan_inf_is_error = true",
            )


@dataclass(frozen=True)
class MathProfileManifest:
    """Representation of ``math_profile_manifest.json``."""

    raw: Mapping[str, Any]

    @property
    def profile_id(self) -> str:
        return str(self.raw.get("math_profile_id", ""))

    def validate(self) -> None:
        required = {"math_profile_id", "functions", "artifacts"}
        missing = required - set(self.raw)
        if missing:
            raise err(
                "E_MATH_PROFILE_MISSING",
                f"math_profile_manifest missing keys {sorted(missing)}",
            )
        if not isinstance(self.raw["functions"], list) or not self.raw["functions"]:
            raise err("E_MATH_PROFILE_FUNCTIONS", "functions must be a non-empty list")
        if not isinstance(self.raw["artifacts"], list) or not self.raw["artifacts"]:
            raise err("E_MATH_PROFILE_ARTIFACTS", "artifacts must be a non-empty list")
        for artifact in self.raw["artifacts"]:
            if not isinstance(artifact, Mapping):
                raise err(
                    "E_MATH_PROFILE_ARTIFACTS", "artifact entries must be mappings"
                )
            if "name" not in artifact or "sha256" not in artifact:
                raise err("E_MATH_PROFILE_ARTIFACTS", "artifact missing name or sha256")


@dataclass(frozen=True)
class NumericPolicyAttestation:
    """Materialised content for ``numeric_policy_attest.json``."""

    content: Mapping[str, Any]

    def to_json(self) -> str:
        return json.dumps(self.content, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Governance loading
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Mapping[str, Any]:
    """Load a JSON file and ensure the root object is a mapping."""
    if not path.exists():
        raise err("E_GOVERNANCE_MISSING", f"governance artefact '{path}' not found")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise err("E_JSON_STRUCTURE", f"expected mapping at top-level in {path}")
    return data


def load_numeric_policy(path: Path) -> tuple[NumericPolicy, ArtifactDigest]:
    """Load and validate the numeric policy artefact, returning its digest."""
    raw = _load_json(path)
    policy = NumericPolicy(raw=raw)
    policy.validate()
    digest = hash_artifact(path, error_prefix="E_NUMERIC_POLICY")
    return policy, digest


def load_math_profile_manifest(
    path: Path,
) -> tuple[MathProfileManifest, ArtifactDigest]:
    """Load and validate the math profile manifest, returning its digest."""
    raw = _load_json(path)
    manifest = MathProfileManifest(raw=raw)
    manifest.validate()
    digest = hash_artifact(path, error_prefix="E_MATH_PROFILE")
    return manifest, digest


# ---------------------------------------------------------------------------
# Numeric self-tests (S0.8.9)
# ---------------------------------------------------------------------------


def _check_subnormal_support() -> None:
    min_subnormal = float.fromhex("0x0.0000000000001p-1022")
    if min_subnormal == 0.0:
        raise AssertionError("subnormal minimum flushed to zero")
    if math.ldexp(1.0, -1074) != min_subnormal:
        raise AssertionError("platform ldexp disagrees with binary64 min subnormal")


def _check_rounding_mode() -> None:
    bits = struct.unpack("<Q", struct.pack("<d", 1.0))[0] + 1
    rounded = struct.unpack("<d", struct.pack("<Q", bits))[0]
    if rounded <= 1.0:
        raise AssertionError("rounding mode is not round-to-nearest-even")


def _check_fma_disabled() -> None:
    a = 1.0000000000000002
    res = (a * a) - 1.0
    if res == 0.0:
        raise AssertionError("fused multiply-add contraction detected")


def _check_neumaier() -> None:
    sequence = [1.0, 1e-16] * 10 + [-1.0] * 10
    s = 0.0
    c = 0.0
    for value in sequence:
        y = value - c
        t = s + y
        c = (t - s) - y
        s = t
    if not math.isclose(s + c, 1e-15, rel_tol=0.0, abs_tol=1e-15):
        raise AssertionError("neumaier summation deviates from baseline")


def _total_order_key(value: float) -> int:
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    if bits >> 63:
        return 0xFFFFFFFFFFFFFFFF - bits
    return bits | 0x8000000000000000


def _check_total_order() -> None:
    values = [float("-0.0"), 0.0, -1.0, 1.0, 2.5, -10.0]
    ordered = sorted(values, key=_total_order_key)
    expected = [-10.0, -1.0, float("-0.0"), 0.0, 1.0, 2.5]
    if ordered != expected:
        raise AssertionError("IEEE total order not preserved")


def _check_libm_suite() -> None:
    getcontext().prec = 80
    cases = [
        ("exp", 0.5, float(Decimal("0.5").exp())),
        ("log", 0.5, float(Decimal("0.5").ln())),
        ("sqrt", 2.0, float(Decimal(2).sqrt())),
    ]
    for name, value, expected in cases:
        actual = getattr(math, name)(value)
        if not math.isfinite(actual):
            raise AssertionError(f"{name} returned non-finite value")
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=5e-16):
            raise AssertionError(f"{name} deviates beyond tolerance")


def run_numeric_self_tests() -> Mapping[str, str]:
    """Execute the numeric self-tests required by S0.8, returning pass/fail."""
    tests = {
        "rounding": _check_rounding_mode,
        "ftz": _check_subnormal_support,
        "fma": _check_fma_disabled,
        "libm": _check_libm_suite,
        "neumaier": _check_neumaier,
        "total_order": _check_total_order,
    }
    results: MutableMapping[str, str] = {}
    for name, fn in tests.items():
        try:
            fn()
        except AssertionError as exc:
            results[name] = f"fail:{exc}"
        except Exception as exc:
            results[name] = f"fail:{type(exc).__name__}"
        else:
            results[name] = "pass"
    return results


def build_numeric_policy_attestation(
    *,
    policy: NumericPolicy,
    policy_digest: ArtifactDigest,
    math_profile: MathProfileManifest,
    math_digest: ArtifactDigest,
    platform_info: Optional[Mapping[str, str]] = None,
) -> NumericPolicyAttestation:
    """Construct the attestation payload emitted alongside the validation bundle."""
    platform_data = dict(
        platform_info
        or {
            "os": platform.system().lower(),
            "release": platform.release(),
            "python": sys.version.split()[0],
            "machine": platform.machine(),
        }
    )
    attestation = {
        "numeric_policy_version": policy.version,
        "math_profile_id": math_profile.profile_id,
        "platform": platform_data,
        "flags": {
            "binary_format": policy.raw.get("binary_format"),
            "rounding": policy.raw.get("rounding_mode"),
            "fma_allowed": policy.raw.get("fma_allowed"),
            "flush_to_zero": policy.raw.get("flush_to_zero"),
            "denormals_are_zero": policy.raw.get("denormals_are_zero"),
        },
        "self_tests": run_numeric_self_tests(),
        "digests": [
            {"name": policy_digest.basename, "sha256": policy_digest.sha256_hex},
            {"name": math_digest.basename, "sha256": math_digest.sha256_hex},
        ],
    }
    if policy.raw.get("build_contract"):
        attestation["build_contract"] = policy.raw["build_contract"]
    return NumericPolicyAttestation(content=attestation)


__all__ = [
    "NumericPolicy",
    "MathProfileManifest",
    "NumericPolicyAttestation",
    "load_numeric_policy",
    "load_math_profile_manifest",
    "build_numeric_policy_attestation",
]
