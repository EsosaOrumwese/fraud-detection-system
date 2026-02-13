"""RNG helpers for Segment 1A S1 (Philox2x64-10 keyed substreams)."""

from __future__ import annotations

import hashlib
import struct
from typing import Tuple


UINT64_MASK = 0xFFFFFFFFFFFFFFFF
UINT64_MAX = UINT64_MASK

PHILOX_M0 = 0xD2B74407B1CE6E93
PHILOX_W0 = 0x9E3779B97F4A7C15

TWO_NEG_64 = float.fromhex("0x1.0000000000000p-64")
ONE_MINUS_EPS = float.fromhex("0x1.fffffffffffffp-1")


def uer_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def ser_u64(value: int) -> bytes:
    if value < 0 or value > UINT64_MAX:
        raise ValueError("u64 out of range")
    return struct.pack("<Q", value)


def low64(digest: bytes) -> int:
    if len(digest) != 32:
        raise ValueError("Expected 32-byte SHA-256 digest.")
    return int.from_bytes(digest[24:32], "little", signed=False)


def derive_master_material(seed_material_bytes: bytes, seed: int) -> bytes:
    if len(seed_material_bytes) != 32:
        raise ValueError("seed_material_bytes must be 32 bytes.")
    payload = (
        uer_string("mlr:1A.master")
        + seed_material_bytes
        + struct.pack("<Q", seed)
    )
    return hashlib.sha256(payload).digest()


def derive_substream(
    master_material: bytes, label: str, merchant_u64: int
) -> tuple[int, int, int]:
    msg = uer_string("mlr:1A") + uer_string(label) + ser_u64(merchant_u64)
    digest = hashlib.sha256(master_material + msg).digest()
    key = low64(digest)
    counter_hi = int.from_bytes(digest[16:24], "big", signed=False)
    counter_lo = int.from_bytes(digest[24:32], "big", signed=False)
    return key, counter_hi, counter_lo


def merchant_u64(merchant_id: int) -> int:
    payload = struct.pack("<Q", merchant_id)
    digest = hashlib.sha256(payload).digest()
    return low64(digest)


def _mul_hi_lo(a: int, b: int) -> tuple[int, int]:
    product = a * b
    lo = product & UINT64_MASK
    hi = (product >> 64) & UINT64_MASK
    return hi, lo


def philox2x64_10(counter_hi: int, counter_lo: int, key: int) -> tuple[int, int]:
    # Low lane corresponds to the counter low word (lo); high lane is counter high (hi).
    c0 = counter_lo & UINT64_MASK
    c1 = counter_hi & UINT64_MASK
    k0 = key & UINT64_MASK
    for _ in range(10):
        hi, lo = _mul_hi_lo(PHILOX_M0, c0)
        c0 = (hi ^ k0 ^ c1) & UINT64_MASK
        c1 = lo
        k0 = (k0 + PHILOX_W0) & UINT64_MASK
    return c0, c1


def u01(x: int) -> float:
    u = ((float(x) + 1.0) * TWO_NEG_64)
    if u == 1.0:
        return ONE_MINUS_EPS
    return u


def add_u128(counter_hi: int, counter_lo: int, increment: int) -> tuple[int, int]:
    if increment < 0:
        raise ValueError("Increment must be non-negative.")
    total_lo = counter_lo + increment
    new_lo = total_lo & UINT64_MASK
    carry = total_lo >> 64
    new_hi = (counter_hi + carry) & UINT64_MASK
    return new_hi, new_lo
