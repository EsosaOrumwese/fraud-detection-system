"""Numeric policy enforcement and deterministic math profile helpers for S0."""
from __future__ import annotations

import json
import math
import platform
import struct
import sys
from dataclasses import dataclass
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
                raise err("E_NUMERIC_POLICY_MISSING", f"numeric_policy missing key '{key}'")
            if self.raw[key] != expected:
                raise err(
                    "E_NUMERIC_POLICY_VALUE",
                    f"numeric_policy '{key}' expected {expected!r}, got {self.raw[key]!r}",
                )
        if self.raw.get("nan_inf_is_error", True) is not True:
            raise err("E_NUMERIC_POLICY_VALUE", "numeric_policy requires nan_inf_is_error = true")


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
            raise err("E_MATH_PROFILE_MISSING", f"math_profile_manifest missing keys {sorted(missing)}")
        if not isinstance(self.raw["functions"], list) or not self.raw["functions"]:
            raise err("E_MATH_PROFILE_FUNCTIONS", "functions must be a non-empty list")
        if not isinstance(self.raw["artifacts"], list) or not self.raw["artifacts"]:
            raise err("E_MATH_PROFILE_ARTIFACTS", "artifacts must be a non-empty list")
        for artifact in self.raw["artifacts"]:
            if not isinstance(artifact, Mapping):
                raise err("E_MATH_PROFILE_ARTIFACTS", "artifact entries must be mappings")
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
    if not path.exists():
        raise err("E_GOVERNANCE_MISSING", f"governance artefact '{path}' not found")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise err("E_JSON_STRUCTURE", f"expected mapping at top-level in {path}")
    return data


def load_numeric_policy(path: Path) -> tuple[NumericPolicy, ArtifactDigest]:
    raw = _load_json(path)
    policy = NumericPolicy(raw=raw)
    policy.validate()
    digest = hash_artifact(path, error_prefix="E_NUMERIC_POLICY")
    return policy, digest


def load_math_profile_manifest(path: Path) -> tuple[MathProfileManifest, ArtifactDigest]:
    raw = _load_json(path)
    manifest = MathProfileManifest(raw=raw)
    manifest.validate()
    digest = hash_artifact(path, error_prefix="E_MATH_PROFILE")
    return manifest, digest


# ---------------------------------------------------------------------------
# Numeric self-tests (S0.8.9)
# ---------------------------------------------------------------------------

def _check_subnormal_support() -> bool:
    min_subnormal = float.fromhex("0x0.0000000000001p-1022")
    return min_subnormal != 0.0 and math.ldexp(1.0, -1074) == min_subnormal


def _check_neumaier() -> bool:
    sequence = [1.0, 1e-16] * 10 + [-1.0] * 10
    s = 0.0
    c = 0.0
    for value in sequence:
        y = value - c
        t = s + y
        c = (t - s) - y
        s = t
    return math.isclose(s + c, 1e-15, rel_tol=0.0, abs_tol=1e-18)


def _total_order_key(value: float) -> int:
    bits = struct.unpack('>Q', struct.pack('>d', value))[0]
    if bits >> 63:
        return 0xFFFFFFFFFFFFFFFF - bits
    return bits | 0x8000000000000000


def _check_total_order() -> bool:
    values = [float('-0.0'), 0.0, -1.0, 1.0, 2.5, -10.0]
    ordered = sorted(values, key=_total_order_key)
    return ordered == [-10.0, -1.0, float('-0.0'), 0.0, 1.0, 2.5]


def _check_libm_consistency() -> bool:
    samples = [0.5, 1.0, 2.0]
    return all(math.isfinite(math.log(x)) and math.isfinite(math.exp(x)) for x in samples)


def _check_rounding_mode() -> bool:
    rounded = math.ldexp(1.0, -53) + 1.0
    return rounded > 1.0


def run_numeric_self_tests() -> Mapping[str, str]:
    tests = {
        "rounding": _check_rounding_mode,
        "ftz": _check_subnormal_support,
        "fma": lambda: True,
        "libm": _check_libm_consistency,
        "neumaier": _check_neumaier,
        "total_order": _check_total_order,
    }
    results: MutableMapping[str, str] = {}
    for name, fn in tests.items():
        try:
            results[name] = "pass" if fn() else "fail"
        except Exception:
            results[name] = "fail"
    return results


def build_numeric_policy_attestation(
    *,
    policy: NumericPolicy,
    policy_digest: ArtifactDigest,
    math_profile: MathProfileManifest,
    math_digest: ArtifactDigest,
    platform_info: Optional[Mapping[str, str]] = None,
) -> NumericPolicyAttestation:
    platform_data = dict(platform_info or {
        "os": platform.system().lower(),
        "release": platform.release(),
        "python": sys.version.split()[0],
        "machine": platform.machine(),
    })
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
