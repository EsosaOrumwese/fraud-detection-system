"""Lineage hashing helpers for S0.2."""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set, Tuple

from ..exceptions import err
from ..l0.artifacts import ArtifactDigest


def _encode_str(value: str) -> bytes:
    data = value.encode("utf-8")
    return struct.pack("<I", len(data)) + data


def _encode_u64(value: int) -> bytes:
    if not (0 <= value < 2 ** 64):
        raise err("E_UINT64_RANGE", f"value {value} outside [0, 2^64)")
    return struct.pack("<Q", value)


def _hash_sha256(payload: bytes) -> bytes:
    import hashlib

    return hashlib.sha256(payload).digest()


@dataclass(frozen=True)
class ParameterHashResult:
    parameter_hash: str
    parameter_hash_bytes: bytes
    artefacts: Tuple[ArtifactDigest, ...]


def compute_parameter_hash(artefacts: Sequence[ArtifactDigest]) -> ParameterHashResult:
    if not artefacts:
        raise err("E_PARAM_EMPTY", "parameter artefact set is empty")

    ordered = tuple(sorted(artefacts, key=lambda d: d.basename))
    tuples: List[bytes] = []
    for digest in ordered:
        payload = _encode_str(digest.basename) + digest.sha256_digest
        tuples.append(_hash_sha256(payload))
    concatenated = b"".join(tuples)
    hash_bytes = _hash_sha256(concatenated)
    return ParameterHashResult(
        parameter_hash=hash_bytes.hex(),
        parameter_hash_bytes=hash_bytes,
        artefacts=ordered,
    )


@dataclass(frozen=True)
class ManifestFingerprintResult:
    manifest_fingerprint: str
    manifest_fingerprint_bytes: bytes
    artefacts: Tuple[ArtifactDigest, ...]
    git_commit_hex: str


def normalise_git_commit(raw_bytes: bytes) -> bytes:
    if len(raw_bytes) == 32:
        return raw_bytes
    if len(raw_bytes) == 20:
        return b"\x00" * 12 + raw_bytes
    raise err("E_GIT_BYTES", f"git commit digest must be 20 or 32 bytes, got {len(raw_bytes)}")


def compute_manifest_fingerprint(
    artefacts: Sequence[ArtifactDigest],
    *,
    git_commit_raw: bytes,
    parameter_hash_bytes: bytes,
) -> ManifestFingerprintResult:
    if not artefacts:
        raise err("E_ARTIFACT_EMPTY", "manifest artefact set is empty")
    if len(parameter_hash_bytes) != 32:
        raise err("E_PARAM_HASH_ABSENT", "parameter hash must be 32 raw bytes")

    ordered = tuple(sorted(artefacts, key=lambda d: d.basename))
    tuples: List[bytes] = []
    for digest in ordered:
        payload = _encode_str(digest.basename) + digest.sha256_digest
        tuples.append(_hash_sha256(payload))
    git_bytes = normalise_git_commit(git_commit_raw)
    packed = b"".join(tuples) + git_bytes + parameter_hash_bytes
    fingerprint_bytes = _hash_sha256(packed)
    return ManifestFingerprintResult(
        manifest_fingerprint=fingerprint_bytes.hex(),
        manifest_fingerprint_bytes=fingerprint_bytes,
        artefacts=ordered,
        git_commit_hex=git_bytes.hex(),
    )


def compute_run_id(
    *,
    manifest_fingerprint_bytes: bytes,
    seed: int,
    start_time_ns: int,
    existing_ids: Iterable[str] = (),
    max_attempts: int = 2 ** 16,
) -> str:
    if len(manifest_fingerprint_bytes) != 32:
        raise err("E_RUNID_INPUT", "manifest fingerprint must be 32 raw bytes")
    attempts = 0
    used: Set[str] = set(existing_ids)
    timestamp = start_time_ns
    prefix = _encode_str("run:1A")
    while attempts < max_attempts:
        payload = prefix + manifest_fingerprint_bytes + _encode_u64(seed) + _encode_u64(timestamp)
        candidate = _hash_sha256(payload)[:16].hex()
        if candidate not in used:
            return candidate
        timestamp += 1
        attempts += 1
    raise err("E_RUNID_COLLISION_EXHAUSTED", f"exhausted {max_attempts} attempts computing run_id")


__all__ = [
    "ParameterHashResult",
    "ManifestFingerprintResult",
    "compute_parameter_hash",
    "compute_manifest_fingerprint",
    "compute_run_id",
    "normalise_git_commit",
]
