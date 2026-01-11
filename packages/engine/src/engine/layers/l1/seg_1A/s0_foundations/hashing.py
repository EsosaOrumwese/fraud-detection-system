"""Hashing utilities for Segment 1A S0."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from engine.core.errors import HashingError
from engine.core.hashing import FileDigest, sha256_file


REQUIRED_PARAM_BASENAMES = {
    "hurdle_coefficients.yaml",
    "nb_dispersion_coefficients.yaml",
    "crossborder_hyperparams.yaml",
    "ccy_smoothing_params.yaml",
    "policy.s3.rule_ladder.yaml",
    "s6_selection_policy.yaml",
}

OPTIONAL_PARAM_BASENAMES = {
    "policy.s3.base_weight.yaml",
    "policy.s3.thresholds.yaml",
}


@dataclass(frozen=True)
class NamedPath:
    name: str
    path: Path


@dataclass(frozen=True)
class NamedDigest:
    name: str
    digest: FileDigest


def _uer_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def _validate_ascii_basenames(names: Iterable[str]) -> list[str]:
    names_list = list(names)
    for name in names_list:
        try:
            name.encode("ascii")
        except UnicodeEncodeError as exc:
            raise HashingError(f"Non-ASCII basename for hashing: {name}") from exc
    if len(set(names_list)) != len(names_list):
        raise HashingError("Duplicate basenames detected for hashing inputs.")
    return names_list


def _concat_named_digests(named: Iterable[NamedDigest]) -> list[bytes]:
    items = sorted(named, key=lambda item: item.name)
    basenames = _validate_ascii_basenames([item.name for item in items])
    parts: list[bytes] = []
    for name, item in zip(basenames, items):
        parts.append(
            hashlib.sha256(
                _uer_string(name) + bytes.fromhex(item.digest.sha256_hex)
            ).digest()
        )
    return parts


def load_param_digests(param_paths: Iterable[NamedPath]) -> list[NamedDigest]:
    digests = []
    for param in param_paths:
        digests.append(NamedDigest(name=param.name, digest=sha256_file(param.path)))
    return digests


def compute_parameter_hash(
    param_paths: Iterable[NamedPath],
) -> tuple[str, bytes, list[NamedDigest]]:
    paths = list(param_paths)
    names = {param.name for param in paths}
    missing = REQUIRED_PARAM_BASENAMES - names
    if missing:
        raise HashingError(f"Missing required parameter files: {sorted(missing)}")
    allowed = set(REQUIRED_PARAM_BASENAMES) | set(OPTIONAL_PARAM_BASENAMES)
    extra = names - allowed
    if extra:
        raise HashingError(f"Unexpected parameter files: {sorted(extra)}")
    named = load_param_digests(paths)
    parts = _concat_named_digests(named)
    parameter_hash_bytes = hashlib.sha256(b"".join(parts)).digest()
    return parameter_hash_bytes.hex(), parameter_hash_bytes, named


def compute_manifest_fingerprint(
    artifact_digests: Iterable[NamedDigest], git_32: bytes, parameter_hash_bytes: bytes
) -> tuple[str, bytes]:
    if len(git_32) != 32:
        raise HashingError("git_32 must be 32 raw bytes.")
    parts = _concat_named_digests(artifact_digests)
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part)
    hasher.update(git_32)
    hasher.update(parameter_hash_bytes)
    manifest_fingerprint_bytes = hasher.digest()
    return manifest_fingerprint_bytes.hex(), manifest_fingerprint_bytes


def compute_run_id(
    manifest_fingerprint_bytes: bytes, seed: int, t_ns: int
) -> tuple[str, bytes]:
    payload = (
        _uer_string("run:1A")
        + manifest_fingerprint_bytes
        + struct.pack("<Q", seed)
        + struct.pack("<Q", t_ns)
    )
    run_id_bytes = hashlib.sha256(payload).digest()[:16]
    return run_id_bytes.hex(), run_id_bytes
