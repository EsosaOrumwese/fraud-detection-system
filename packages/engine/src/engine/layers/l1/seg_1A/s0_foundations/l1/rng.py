"""Philox-based RNG scaffolding for S0.3."""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple

from ..exceptions import err
from .hashing import _hash_sha256 as _sha256

_MASK64 = (1 << 64) - 1
_PHILOX_MULT = 0xD2B74407B1CE6E93
_PHILOX_WEYL = 0x9E3779B97F4A7C15
_DOUBLE_SCALE = float.fromhex("0x1.0000000000000p-64")
_OPEN_INTERVAL_MAX = float.fromhex("0x1.fffffffffffffp-1")
_TAU = float.fromhex("0x1.921fb54442d18p+2")
_POISSON_THRESHOLD = 10.0


@dataclass(frozen=True)
class PhiloxState:
    key: int
    counter_hi: int
    counter_lo: int


def _mulhi_lo(x: int, y: int) -> Tuple[int, int]:
    product = (x & _MASK64) * (y & _MASK64)
    lo = product & _MASK64
    hi = (product >> 64) & _MASK64
    return hi, lo


def _add_u128(hi: int, lo: int, increment: int) -> Tuple[int, int]:
    total = ((hi & _MASK64) << 64) | (lo & _MASK64)
    total = (total + increment) % (1 << 128)
    new_hi = (total >> 64) & _MASK64
    new_lo = total & _MASK64
    return new_hi, new_lo


def philox2x64_10(key: int, counter: Tuple[int, int]) -> Tuple[int, int]:
    key = key & _MASK64
    ctr_hi, ctr_lo = counter
    c0 = ctr_lo & _MASK64
    c1 = ctr_hi & _MASK64
    k = key
    for _ in range(10):
        hi, lo = _mulhi_lo(_PHILOX_MULT, c0)
        n0 = (hi ^ k ^ c1) & _MASK64
        n1 = lo
        c0, c1 = n0, n1
        k = (k + _PHILOX_WEYL) & _MASK64
    return c0, c1


SubstreamComponent = Tuple[str, object]


def comp_u64(value: int) -> SubstreamComponent:
    if not (0 <= value < 2 ** 64):
        raise err("E_SUBSTREAM_U64", f"u64 component {value} outside [0, 2^64)")
    return ("u64", value)


def comp_index(value: int) -> SubstreamComponent:
    if not (0 <= value < 2 ** 32):
        raise err("E_SUBSTREAM_INDEX", f"index component {value} outside [0, 2^32)")
    return ("index", value)


def comp_iso(value: str) -> SubstreamComponent:
    if value is None:
        raise err("E_SUBSTREAM_ISO", "ISO component is null")
    upper = value.upper()
    if len(upper) != 2 or not upper.isascii():
        raise err("E_SUBSTREAM_ISO", f"ISO component '{value}' must be uppercase ASCII length 2")
    return ("iso", upper)


def _encode_component(component: SubstreamComponent) -> bytes:
    kind, value = component
    if kind == "u64":
        return struct.pack("<Q", int(value))
    if kind == "index":
        return struct.pack("<I", int(value))
    if kind == "iso":
        encoded = str(value).encode("utf-8")
        return struct.pack("<I", len(encoded)) + encoded
    if kind == "string":
        encoded = str(value).encode("utf-8")
        return struct.pack("<I", len(encoded)) + encoded
    raise err("E_SUBSTREAM_KIND", f"unsupported component kind '{kind}'")


def _encode_label(label: str) -> bytes:
    data = label.encode("utf-8")
    return struct.pack("<I", len(data)) + data


def _open_interval(u64_word: int) -> float:
    u = (float(u64_word + 1) * _DOUBLE_SCALE)
    if u == 1.0:
        return _OPEN_INTERVAL_MAX
    return u


class PhiloxSubstream:
    """Stateful substream that enforces lane policy and budgeting."""

    def __init__(self, label: str, key: int, counter_hi: int, counter_lo: int) -> None:
        self.label = label
        self.key = key & _MASK64
        self.counter_hi = counter_hi & _MASK64
        self.counter_lo = counter_lo & _MASK64
        self._blocks_consumed = 0
        self._draws_consumed = 0

    def snapshot(self) -> PhiloxState:
        return PhiloxState(self.key, self.counter_hi, self.counter_lo)

    @property
    def blocks(self) -> int:
        return self._blocks_consumed

    @property
    def draws(self) -> int:
        return self._draws_consumed

    def _next_block(self) -> Tuple[int, int]:
        x0, x1 = philox2x64_10(self.key, (self.counter_hi, self.counter_lo))
        self.counter_hi, self.counter_lo = _add_u128(self.counter_hi, self.counter_lo, 1)
        self._blocks_consumed += 1
        return x0, x1

    def uniform(self) -> float:
        x0, _ = self._next_block()
        self._draws_consumed += 1
        return _open_interval(x0)

    def uniform_pair(self) -> Tuple[float, float]:
        x0, x1 = self._next_block()
        self._draws_consumed += 2
        return _open_interval(x0), _open_interval(x1)

    def normal_box_muller(self) -> float:
        u1, u2 = self.uniform_pair()
        r = math.sqrt(-2.0 * math.log(u1))
        theta = _TAU * u2
        return r * math.cos(theta)

    def gamma(self, alpha: float) -> float:
        if alpha <= 0.0:
            raise err("E_GAMMA_ALPHA", f"alpha must be > 0, got {alpha}")
        if alpha < 1.0:
            g_prime = self.gamma(alpha + 1.0)
            u = self.uniform()
            return g_prime * (u ** (1.0 / alpha))
        d = alpha - 1.0 / 3.0
        c = 1.0 / math.sqrt(9.0 * d)
        while True:
            n = self.normal_box_muller()
            x = 1.0 + c * n
            if x <= 0.0:
                continue
            v = x * x * x
            u = self.uniform()
            threshold = 0.5 * n * n + d - d * v + d * math.log(v)
            if math.log(u) < threshold:
                return d * v

    def poisson(self, lam: float) -> int:
        if lam < 0.0:
            raise err("E_POISSON_LAMBDA", f"lambda must be >= 0, got {lam}")
        if lam == 0.0:
            return 0
        if lam < _POISSON_THRESHOLD:
            exp_neg = math.exp(-lam)
            k = 0
            prod = 1.0
            while True:
                prod *= self.uniform()
                if prod <= exp_neg:
                    return k
                k += 1
        # PTRS regime
        sq = math.sqrt(lam)
        b = 0.931 + 2.53 * sq
        a = -0.059 + 0.02483 * b
        inv_alpha = 1.1239 + 1.1328 / (b - 3.4)
        v_r = 0.9277 - 3.6224 / (b - 2.0)
        u_cut = 0.86
        log_lambda = math.log(lam)
        while True:
            u, v = self.uniform_pair()
            if u <= u_cut and v <= v_r:
                k = int(math.floor(b * v / u + lam + 0.43))
                return k
            u_s = 0.5 - abs(u - 0.5)
            if u_s <= 0.0:
                continue
            candidate = (2.0 * a / u_s + b) * v + lam + 0.43
            k = int(math.floor(candidate))
            if k < 0:
                continue
            lhs = math.log(v * inv_alpha / (a / (u_s * u_s) + b))
            rhs = -lam + k * log_lambda - math.lgamma(k + 1.0)
            if lhs <= rhs:
                return k


class PhiloxEngine:
    """Produces deterministic substreams following the S0.3 contract."""

    def __init__(self, *, seed: int, manifest_fingerprint: bytes | str) -> None:
        if not (0 <= seed < 2 ** 64):
            raise err("E_SEED_RANGE", f"seed {seed} outside [0, 2^64)")
        if isinstance(manifest_fingerprint, str):
            manifest_bytes = bytes.fromhex(manifest_fingerprint)
        else:
            manifest_bytes = manifest_fingerprint
        if len(manifest_bytes) != 32:
            raise err("E_MANIFEST_BYTES", "manifest fingerprint must be 32 bytes")
        prefix = _encode_label("mlr:1A.master")
        payload = prefix + manifest_bytes + struct.pack("<Q", seed)
        self._master = _sha256(payload)
        self._root_key = int.from_bytes(self._master[24:32], byteorder="little")
        self._root_counter_hi = int.from_bytes(self._master[16:24], byteorder="big")
        self._root_counter_lo = int.from_bytes(self._master[24:32], byteorder="big")

    @property
    def root_state(self) -> PhiloxState:
        return PhiloxState(self._root_key, self._root_counter_hi, self._root_counter_lo)

    def derive_substream(self, label: str, components: Sequence[SubstreamComponent]) -> PhiloxSubstream:
        msg = _encode_label("mlr:1A") + _encode_label(label)
        for component in components:
            msg += _encode_component(component)
        seed_material = self._master + msg
        digest = _sha256(seed_material)
        key = int.from_bytes(digest[24:32], byteorder="little")
        counter_hi = int.from_bytes(digest[16:24], byteorder="big")
        counter_lo = int.from_bytes(digest[24:32], byteorder="big")
        return PhiloxSubstream(label, key, counter_hi, counter_lo)


__all__ = [
    "PhiloxEngine",
    "PhiloxSubstream",
    "PhiloxState",
    "comp_u64",
    "comp_iso",
    "comp_index",
    "philox2x64_10",
]
