"""Dataset loaders for Segment 1B state-8 site_locations egress."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl

from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ..exceptions import err


@dataclass(frozen=True)
class S7SiteSynthesisPartition:
    """S7 synthesis rows scoped by seed/fingerprint/parameter hash."""

    path: Path
    frame: pl.DataFrame
    parameter_hash: str


def load_s7_site_synthesis(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> S7SiteSynthesisPartition:
    """Load S7 site synthesis rows for the target identity."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "s7_site_synthesis",
        base_path=base_path,
        template_args={
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
        },
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E801_ROW_MISSING",
            f"s7_site_synthesis partition missing at '{dataset_path}'",
        )

    frame = (
        pl.scan_parquet(str(dataset_path / "*.parquet"))
        .select(
            [
                pl.col("merchant_id").cast(pl.Int64),
                pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase(),
                pl.col("site_order").cast(pl.Int64),
                pl.col("lon_deg").cast(pl.Float64),
                pl.col("lat_deg").cast(pl.Float64),
            ]
        )
        .collect()
        .sort(["merchant_id", "legal_country_iso", "site_order"])
    )
    return S7SiteSynthesisPartition(path=dataset_path, frame=frame, parameter_hash=parameter_hash)


def resolve_site_locations_path(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object] | None = None,
) -> Path:
    """Resolve the egress path for site_locations."""

    dictionary = dictionary or load_dictionary()
    return resolve_dataset_path(
        "site_locations",
        base_path=base_path,
        template_args={
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
        },
        dictionary=dictionary,
    )


__all__ = ["S7SiteSynthesisPartition", "load_s7_site_synthesis", "resolve_site_locations_path"]
