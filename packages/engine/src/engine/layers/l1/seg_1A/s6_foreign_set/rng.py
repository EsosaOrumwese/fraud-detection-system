"""RNG helpers for Segment 1A S6 (Philox2x64-10 keyed substreams)."""

from __future__ import annotations

import hashlib

from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    UINT64_MAX,
    add_u128,
    derive_master_material,
    low64,
    merchant_u64,
    philox2x64_10,
    ser_u64,
    u01,
    uer_string,
)


def derive_substream(
    master_material: bytes, label: str, merchant_u64_value: int, country_iso: str
) -> tuple[int, int, int]:
    msg = (
        uer_string("mlr:1A")
        + uer_string(label)
        + ser_u64(merchant_u64_value)
        + uer_string(country_iso)
    )
    digest = hashlib.sha256(master_material + msg).digest()
    key = low64(digest)
    counter_hi = int.from_bytes(digest[16:24], "big", signed=False)
    counter_lo = int.from_bytes(digest[24:32], "big", signed=False)
    return key, counter_hi, counter_lo


def u01_single(counter_hi: int, counter_lo: int, key: int) -> tuple[float, int, int]:
    x0, _x1 = philox2x64_10(counter_hi, counter_lo, key)
    return u01(x0), 1, 1


__all__ = [
    "UINT64_MAX",
    "add_u128",
    "derive_master_material",
    "derive_substream",
    "merchant_u64",
    "philox2x64_10",
    "u01",
    "u01_single",
]
