"""RNG helpers for Segment 3A S3 (Dirichlet zone shares)."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    UINT64_MAX,
    add_u128,
    low64,
    philox2x64_10,
    u01,
    uer_string,
)


DOMAIN_MASTER = "mlr:3A.master"
DOMAIN_STREAM = "mlr:3A.zone_dirichlet"


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


def derive_master_material(manifest_fingerprint_bytes: bytes, seed: int) -> bytes:
    if len(manifest_fingerprint_bytes) != 32:
        raise ValueError("manifest_fingerprint_bytes must be 32 bytes.")
    payload = uer_string(DOMAIN_MASTER) + manifest_fingerprint_bytes + struct.pack("<Q", seed)
    return hashlib.sha256(payload).digest()


def _derive_substream(master_material: bytes, label: str, stream_id: str) -> tuple[int, int, int]:
    msg = uer_string(DOMAIN_STREAM) + uer_string(label) + uer_string(stream_id)
    digest = hashlib.sha256(master_material + msg).digest()
    key = low64(digest)
    counter_hi = int.from_bytes(digest[16:24], "big", signed=False)
    counter_lo = int.from_bytes(digest[24:32], "big", signed=False)
    return key, counter_hi, counter_lo


def derive_substream_state(master_material: bytes, label: str, stream_id: str) -> Substream:
    key, counter_hi, counter_lo = _derive_substream(master_material, label, stream_id)
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
    "u01_single",
    "u01_pair",
]
