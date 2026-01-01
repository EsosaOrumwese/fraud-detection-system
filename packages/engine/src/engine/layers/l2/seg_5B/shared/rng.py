"""Philox RNG helpers for Segment 5B arrival generation."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxState, philox2x64_10

_MASK64 = (1 << 64) - 1
_TWO64 = float(1 << 64)
_U_SCALE = 1.0 / _TWO64
_TAU = float.fromhex("0x1.921fb54442d18p+2")
_ERFINV_A = 0.147


@dataclass(frozen=True)
class RNGEvent:
    key: int
    counter_before_hi: int
    counter_before_lo: int
    counter_after_hi: int
    counter_after_lo: int
    draws: int
    blocks: int
    u64s: tuple[int, ...]

    def before_state(self) -> PhiloxState:
        return PhiloxState(self.key, self.counter_before_hi, self.counter_before_lo)

    def after_state(self) -> PhiloxState:
        return PhiloxState(self.key, self.counter_after_hi, self.counter_after_lo)

    def uniforms(self) -> list[float]:
        return [u64_to_uniform(value) for value in self.u64s]


def derive_event(
    *,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
    family_id: str,
    domain_key: str,
    draws: int,
) -> RNGEvent:
    if draws < 0:
        raise ValueError("draws must be >= 0")
    key, counter_hi, counter_lo = _derive_key_counter(
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        seed=seed,
        scenario_id=scenario_id,
        family_id=family_id,
        domain_key=domain_key,
    )
    if draws == 0:
        return RNGEvent(
            key=key,
            counter_before_hi=counter_hi,
            counter_before_lo=counter_lo,
            counter_after_hi=counter_hi,
            counter_after_lo=counter_lo,
            draws=0,
            blocks=0,
            u64s=(),
        )
    u64s, after_hi, after_lo, blocks = _draw_u64s(
        key=key, counter_hi=counter_hi, counter_lo=counter_lo, draws=draws
    )
    return RNGEvent(
        key=key,
        counter_before_hi=counter_hi,
        counter_before_lo=counter_lo,
        counter_after_hi=after_hi,
        counter_after_lo=after_lo,
        draws=draws,
        blocks=blocks,
        u64s=tuple(u64s),
    )


def u64_to_uniform(value: int) -> float:
    return ((value & _MASK64) + 0.5) * _U_SCALE


def normal_icdf_erfinv(u: float) -> float:
    x = 2.0 * u - 1.0
    if x <= -1.0:
        return float("-inf")
    if x >= 1.0:
        return float("inf")
    ln = math.log(1.0 - x * x)
    term = 2.0 / (math.pi * _ERFINV_A) + ln / 2.0
    inner = term * term - ln / _ERFINV_A
    if inner < 0.0:
        inner = 0.0
    value = math.sqrt(math.sqrt(inner) - term)
    return math.copysign(value, x) * math.sqrt(2.0)


def box_muller_from_pair(u1: float, u2: float) -> float:
    radius = math.sqrt(-2.0 * math.log(u1))
    theta = _TAU * u2
    return radius * math.cos(theta)


def gamma_one_u_approx(mu: float, kappa: float, u: float) -> float:
    if mu <= 0.0:
        return 0.0
    kappa = max(kappa, 1e-12)
    sigma2 = math.log(1.0 + 1.0 / kappa)
    m = math.log(mu) - 0.5 * sigma2
    z = normal_icdf_erfinv(u)
    return math.exp(m + math.sqrt(sigma2) * z)


def poisson_one_u(
    *,
    u: float,
    lam: float,
    lam_exact_max: float,
    n_cap_exact: int,
    max_count: int,
) -> int:
    if lam <= 0.0:
        return 0
    if lam <= lam_exact_max:
        n = 0
        p = math.exp(-lam)
        cdf = p
        while cdf < u and n < n_cap_exact:
            n += 1
            p *= lam / n
            cdf += p
        if cdf < u:
            return max_count
        return n
    z = normal_icdf_erfinv(u)
    n = int(math.floor(lam + math.sqrt(lam) * z + 0.5))
    if n < 0:
        n = 0
    if n > max_count:
        n = max_count
    return n


def _derive_key_counter(
    *,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
    family_id: str,
    domain_key: str,
) -> tuple[int, int, int]:
    msg = b"".join(
        [
            _uer("5B.rng.v1"),
            _uer(family_id),
            _uer(manifest_fingerprint),
            _uer(parameter_hash),
            _le64(seed),
            _uer(scenario_id),
            _uer(domain_key),
        ]
    )
    digest = hashlib.sha256(msg).digest()
    key = _be64(digest[0:8])
    counter_hi = _be64(digest[8:16])
    counter_lo = _be64(digest[16:24])
    return key, counter_hi, counter_lo


def _draw_u64s(
    *,
    key: int,
    counter_hi: int,
    counter_lo: int,
    draws: int,
) -> tuple[list[int], int, int, int]:
    blocks = (draws + 1) // 2
    total_before = (counter_hi << 64) | counter_lo
    total_after = total_before + blocks
    if total_after >= (1 << 128):
        raise ValueError("philox counter wrapped")
    u64s: list[int] = []
    hi = counter_hi
    lo = counter_lo
    for _ in range(blocks):
        x0, x1 = philox2x64_10(key, (hi, lo))
        u64s.append(x0)
        u64s.append(x1)
        hi, lo = _add_u128(hi, lo, 1)
    return u64s[:draws], hi, lo, blocks


def _add_u128(hi: int, lo: int, increment: int) -> tuple[int, int]:
    total = ((hi & _MASK64) << 64) | (lo & _MASK64)
    total += increment
    new_hi = (total >> 64) & _MASK64
    new_lo = total & _MASK64
    return new_hi, new_lo


def _uer(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, "big") + encoded


def _le64(value: int) -> bytes:
    return int(value).to_bytes(8, "little", signed=False)


def _be64(chunk: bytes) -> int:
    return int.from_bytes(chunk, "big", signed=False)


__all__ = [
    "RNGEvent",
    "box_muller_from_pair",
    "derive_event",
    "gamma_one_u_approx",
    "normal_icdf_erfinv",
    "poisson_one_u",
    "u64_to_uniform",
]
