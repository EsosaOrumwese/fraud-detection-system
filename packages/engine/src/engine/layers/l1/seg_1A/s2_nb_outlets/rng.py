"""RNG helpers for Segment 1A S2 (Philox2x64-10 keyed substreams)."""

from __future__ import annotations

from dataclasses import dataclass

from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    UINT64_MAX,
    add_u128,
    derive_master_material,
    derive_substream,
    merchant_u64,
    philox2x64_10,
    u01,
)


@dataclass
class Substream:
    key: int
    base_hi: int
    base_lo: int
    index: int = 0

    def counter(self) -> tuple[int, int]:
        return add_u128(self.base_hi, self.base_lo, self.index)

    def block(self) -> tuple[int, int]:
        counter_hi, counter_lo = self.counter()
        x0, x1 = philox2x64_10(counter_hi, counter_lo, self.key)
        self.index += 1
        return x0, x1


def derive_substream_state(
    master_material: bytes, label: str, merchant_id: int
) -> Substream:
    key, counter_hi, counter_lo = derive_substream(
        master_material, label, merchant_u64(merchant_id)
    )
    return Substream(key=key, base_hi=counter_hi, base_lo=counter_lo)


def u01_single(stream: Substream) -> tuple[float, int, int]:
    x0, _x1 = stream.block()
    return u01(x0), 1, 1


def u01_pair(stream: Substream) -> tuple[float, float, int, int]:
    x0, x1 = stream.block()
    return u01(x0), u01(x1), 1, 2


__all__ = [
    "UINT64_MAX",
    "Substream",
    "derive_master_material",
    "derive_substream_state",
    "u01",
    "u01_pair",
    "u01_single",
]
