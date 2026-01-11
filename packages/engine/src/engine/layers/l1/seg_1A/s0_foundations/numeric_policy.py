"""Numeric policy self-tests and attestation for S0.8."""

from __future__ import annotations

import json
import math
import platform
import struct
import sys
from decimal import Context
from pathlib import Path
from typing import Any

import numpy as np

from engine.core.errors import EngineFailure
from engine.core.hashing import sha256_file


def load_numeric_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_math_profile(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _float_to_u64(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def _ordered_u64(value: float) -> int:
    bits = _float_to_u64(value)
    if bits & 0x8000000000000000:
        return (~bits) & 0xFFFFFFFFFFFFFFFF
    return bits | 0x8000000000000000


def _ulp_diff(a: float, b: float) -> int:
    return abs(_ordered_u64(a) - _ordered_u64(b))


def _neumaier_sum(values: list[float]) -> float:
    total = 0.0
    c = 0.0
    for value in values:
        t = total + value
        if abs(total) >= abs(value):
            c += (total - t) + value
        else:
            c += (value - t) + total
        total = t
    return total + c


def _total_order(values: list[float]) -> list[float]:
    return sorted(values, key=_ordered_u64)


def _rounding_mode_ok() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes

            msvcrt = ctypes.CDLL("msvcrt")
            controlfp = msvcrt._controlfp
            controlfp.restype = ctypes.c_uint
            controlfp.argtypes = [ctypes.c_uint, ctypes.c_uint]
            value = controlfp(0, 0)
            rc_mask = 0x00000300
            return (value & rc_mask) == 0x00000000
        except Exception:
            return _rounding_tie_check()
    try:
        import ctypes

        libc = ctypes.CDLL(None)
        fegetround = libc.fegetround
        fegetround.restype = ctypes.c_int
        return fegetround() == 0
    except Exception:
        return _rounding_tie_check()


def _rounding_tie_check() -> bool:
    half_ulp = 2**-53
    return (1.0 + half_ulp == 1.0) and (-1.0 - half_ulp == -1.0)


def _subnormal_ok() -> bool:
    sub = float.fromhex("0x0.0000000000001p-1022")
    return sub != 0.0 and (sub * 1.0) == sub


def _fma_off_ok() -> bool:
    ctx = Context(prec=80)
    cases = [
        (1e308, 1e-308, -1.0),
        (1.0 + 2**-27, 1.0 + 2**-27, -1.0),
    ]
    for a, b, c in cases:
        non_fused = a * b + c
        da = ctx.create_decimal_from_float(a)
        db = ctx.create_decimal_from_float(b)
        dc = ctx.create_decimal_from_float(c)
        fused = float(ctx.add(ctx.multiply(da, db), dc))
        if non_fused != fused:
            return True
    return False


def _libm_profile_ok(math_profile: dict[str, Any]) -> bool:
    functions = math_profile.get("functions") or []
    try:
        import scipy  # type: ignore
    except Exception:
        return False
    try:
        import numpy  # type: ignore
    except Exception:
        return False
    version_ok = True
    for artifact in math_profile.get("artifacts") or []:
        name = artifact.get("name", "")
        if name.startswith("numpy-"):
            version_ok = version_ok and (numpy.__version__ == name.split("numpy-")[-1])
        if name.startswith("scipy-"):
            version_ok = version_ok and (scipy.__version__ == name.split("scipy-")[-1])
    for fn in functions:
        if fn == "numpy.sum" and not hasattr(np, "sum"):
            return False
        if fn == "numpy.dot" and not hasattr(np, "dot"):
            return False
        if fn == "scipy.special.logsumexp":
            if not hasattr(scipy, "special") or not hasattr(scipy.special, "logsumexp"):
                return False
    return version_ok


def _neumaier_ok() -> bool:
    values = [1.0, 1e-16] * 10_000 + [-1.0] * 10_000
    total = _neumaier_sum(values)
    expected = math.fsum(values)
    return _ulp_diff(total, expected) <= 1024


def _total_order_ok() -> bool:
    values = [float("-inf"), -1.0, -0.0, 0.0, 1.0, float("inf")]
    expected = [float("-inf"), -1.0, -0.0, 0.0, 1.0, float("inf")]
    ordered = _total_order(values)
    if len(ordered) != len(expected):
        return False
    for got, want in zip(ordered, expected):
        if math.isnan(got) or math.isnan(want):
            return False
        if got == want:
            if got == 0.0 and math.copysign(1.0, got) != math.copysign(1.0, want):
                return False
            continue
        return False
    return True


def run_numeric_self_tests(
    numeric_policy_path: Path,
    math_profile_path: Path,
    module: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    policy_digest = sha256_file(numeric_policy_path)
    profile_digest = sha256_file(math_profile_path)
    numeric_policy = load_numeric_policy(numeric_policy_path)
    math_profile = load_math_profile(math_profile_path)

    rounding_ok = _rounding_mode_ok()
    if not rounding_ok:
        raise EngineFailure(
            "F7",
            "rounding_mode_invalid",
            "S0.8",
            module,
            {"detail": "rounding_mode_not_rne"},
        )

    subnormals_ok = _subnormal_ok()
    if not subnormals_ok:
        raise EngineFailure(
            "F7",
            "ftz_detected",
            "S0.8",
            module,
            {"detail": "subnormal_flushed"},
        )

    fma_off_ok = _fma_off_ok()
    if not fma_off_ok:
        raise EngineFailure(
            "F7",
            "fma_detected",
            "S0.8",
            module,
            {"detail": "fma_candidate_equal"},
        )

    libm_regression_ok = _libm_profile_ok(math_profile)
    if not libm_regression_ok:
        raise EngineFailure(
            "F7",
            "libm_profile_mismatch",
            "S0.8",
            module,
            {"detail": "math_profile_version_or_function_mismatch"},
        )

    neumaier_ok = _neumaier_ok()
    if not neumaier_ok:
        raise EngineFailure(
            "F7",
            "neumaier_mismatch",
            "S0.8",
            module,
            {"detail": "neumaier_ulp_exceeded"},
        )

    total_order_ok = _total_order_ok()
    if not total_order_ok:
        raise EngineFailure(
            "F7",
            "total_order_violation",
            "S0.8",
            module,
            {"detail": "total_order_failed"},
        )

    passed = all(
        [
            rounding_ok,
            fma_off_ok,
            subnormals_ok,
            libm_regression_ok,
            neumaier_ok,
            total_order_ok,
        ]
    )

    attestation = {
        "passed": passed,
        "rounding_ok": rounding_ok,
        "fma_off_ok": fma_off_ok,
        "subnormals_ok": subnormals_ok,
        "libm_regression_ok": libm_regression_ok,
        "neumaier_ok": neumaier_ok,
        "total_order_ok": total_order_ok,
        "math_profile_id": math_profile.get("math_profile_id", ""),
        "profile_functions": math_profile.get("functions", []),
        "numeric_policy_version": numeric_policy.get("version"),
        "flags": {
            "rounding": numeric_policy.get("rounding"),
            "fma": numeric_policy.get("fma"),
            "ftz_daz": numeric_policy.get("ftz_daz"),
        },
        "platform": {
            "os": platform.system(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "digests": [
            {"name": numeric_policy_path.name, "sha256": policy_digest.sha256_hex},
            {"name": math_profile_path.name, "sha256": profile_digest.sha256_hex},
        ],
    }
    digest_map = {
        numeric_policy_path.name: policy_digest.sha256_hex,
        math_profile_path.name: profile_digest.sha256_hex,
    }
    return attestation, digest_map
