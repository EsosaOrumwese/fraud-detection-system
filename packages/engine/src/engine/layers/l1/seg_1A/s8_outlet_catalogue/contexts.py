"""Context objects shared across the S8 outlet catalogue pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CountrySequencingInput:
    """Per-country data required to materialise outlet stubs."""

    legal_country_iso: str
    candidate_rank: int
    allocated_count: int
    is_home: bool


@dataclass(frozen=True)
class MerchantSequencingInput:
    """All deterministic inputs needed to emit outlet rows for a merchant."""

    merchant_id: int
    home_country_iso: str
    single_vs_multi_flag: bool
    raw_nb_outlet_draw: int
    global_seed: int
    domain: Sequence[CountrySequencingInput]


@dataclass(frozen=True)
class S8DeterministicContext:
    """Immutable execution context shared across S8 steps."""

    parameter_hash: str
    manifest_fingerprint: str
    seed: int
    run_id: str
    merchants: Sequence[MerchantSequencingInput]
    candidate_lookup: Mapping[int, Mapping[str, int]] | None = None
    membership_lookup: Mapping[int, Mapping[str, bool]] | None = None
    counts_source: str = "s7_in_memory"
    source_paths: Mapping[str, Path] | None = None


@dataclass
class S8Metrics:
    """Accumulator for S8 observability metrics."""

    merchants_in_egress: int = 0
    blocks_with_rows: int = 0
    rows_total: int = 0
    rows_total_by_country: dict[str, int] = field(default_factory=dict)
    hist_final_country_outlet_count: dict[str, int] = field(default_factory=dict)
    domain_size_distribution: dict[str, int] = field(default_factory=dict)
    overflow_merchant_ids: tuple[int, ...] = ()
    sum_law_mismatch_count: int = 0
    s3_membership_miss_count: int = 0
    iso_fk_violation_count: int = 0
    pk_hash_hex: str = ""


@dataclass(frozen=True)
class ValidationBundlePaths:
    """Filesystem paths populated by the validator."""

    bundle_dir: Path
    rng_accounting_path: Path
    metrics_path: Path
    checksums_path: Path
    passed_flag_path: Path


__all__ = [
    "CountrySequencingInput",
    "MerchantSequencingInput",
    "S8DeterministicContext",
    "S8Metrics",
    "ValidationBundlePaths",
]
