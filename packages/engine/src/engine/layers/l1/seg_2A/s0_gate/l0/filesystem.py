"""Filesystem helpers for Segment 2A S0 implementation.

The functions defined here provide typed structure for future sealing logic.
Concrete behaviour (hashing, schema validation, manifest emission) will be
layered in during later phases of the build.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Protocol


@dataclass(frozen=True)
class ResolvedAsset:
    """Represents an artefact resolved via the dataset dictionary."""

    asset_id: str
    path: Path
    schema_ref: str
    partition_keys: tuple[str, ...]


class DigestComputer(Protocol):
    """Protocol for computing content digests.

    The concrete engine will wire the Segment 1A hashing utilities here so the
    2A gate can reuse the same fingerprint law.  Phase 1 keeps the contract
    focused on types so downstream wiring is easier.
    """

    def __call__(self, paths: Iterable[Path]) -> Mapping[Path, str]:
        ...


def resolve_asset(asset_id: str) -> ResolvedAsset:
    """Resolve ``asset_id`` using the dataset dictionary (placeholder).

    The implementation will mirror Segment 1B's dictionary helpers once the 2A
    dictionary is wired into the runtime.  Returning ``NotImplemented`` keeps
    the import surface intact without pretending the behaviour already exists.
    """

    raise NotImplementedError("Dictionary resolution for 2A is implemented in later phases.")


def compute_digests(paths: Iterable[Path], *, computer: DigestComputer) -> Mapping[Path, str]:
    """Delegate digest computation to the injected callable.

    Parameters
    ----------
    paths:
        Files that belong to the sealed manifest.
    computer:
        Callable compatible with the Segment 1A hashing utilities.
    """

    return computer(paths)


__all__ = ["ResolvedAsset", "DigestComputer", "resolve_asset", "compute_digests"]
