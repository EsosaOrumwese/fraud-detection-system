"""Deterministic builder for the transaction_schema_merchant_ids reference dataset.

The tool downloads open MCC and ISO sources, generates a reproducible merchant
universe, validates it against the intake spec, and materialises CSV + Parquet
outputs accompanied by a manifest and SHA256 fingerprints.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

import polars as pl
import requests

# ----------------------------- Configuration ---------------------------------

VERSION = "2025-10-07"  # version label for artefact partitioning
REFERENCE_VERSION = f"v{VERSION}"
DATASET_ID = "transaction_schema_merchant_ids"
RAW_SOURCES = {
    "mcc_codes": {
        "url": "https://raw.githubusercontent.com/greggles/mcc-codes/master/mcc_codes.csv",
        "filename": "mcc_codes.csv",
        "sha256": None,
    },
    "iso_country_codes": {
        "url": "https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv",
        "filename": "iso_country_codes.csv",
        "sha256": None,
    },
}

# Deterministic keyword heuristics for channel assignment
CNP_KEYWORDS = {
    "mail order",
    "direct marketing",
    "internet",
    "online",
    "catalog",
    "catalogue",
    "telecom",
    "telephone",
    "subscription",
    "digital",
    "streaming",
    "software",
    "web",
}
CNP_MCC_OVERRIDES = {
    4814,  # Telecommunication Service
    4816,  # Computer Network/Information Services
    4818,  # Telecommunication Equipment including Sell calling cards
    4829,  # Money Transfer
    4899,  # Cable, Satellite, and Other Pay Television
    5960,  # Direct Marketing—Insurance
    5962,  # Direct Marketing—Travel Related
    5963,  # Door-to-Door Sales
    5964,  # Direct Marketing—Catalog Merchant
    5965,  # Direct Marketing—Combination Catalog and Retail Merchant
    5966,  # Direct Marketing—Outbound Telemarketing Merchant
    5967,  # Direct Marketing—Inbound Teleservices Merchant
    5968,  # Direct Marketing—Continuity/Subscription Merchant
    5969,  # Direct Marketing—Other Direct Marketers
    5977,  # Cosmetic Stores (often self-service / online)
    5994,  # News Dealers and Newsstands (digital subscriptions)
    5999,  # Miscellaneous Retail Stores (CNP leaning for aggregated marketplaces)
    7299,  # Miscellaneous Personal Services
    7994,  # Video Game Arcades (digital/online)
    7995,  # Betting (online/wagering)
    8398,  # Charitable and Social Service Organisations (recurring donations)
    8651,  # Political Organisations
}

ROOT = Path(__file__).resolve().parents[1]
ARTEFACT_BASE = ROOT / "artefacts" / "data-intake" / "1A" / DATASET_ID / VERSION
RAW_DIR = ARTEFACT_BASE / "raw"
REFERENCE_DIR = ROOT / "reference" / "layer1" / DATASET_ID / REFERENCE_VERSION
REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

CSV_PATH = REFERENCE_DIR / f"{DATASET_ID}.csv"
PARQUET_PATH = REFERENCE_DIR / f"{DATASET_ID}.parquet"
MANIFEST_PATH = REFERENCE_DIR / f"{DATASET_ID}.manifest.json"
SHA_PATH = REFERENCE_DIR / "SHA256SUMS"

# ----------------------------- Utility helpers ------------------------------


def sha256sum(path: Path) -> str:
    """Compute the SHA-256 digest for the given file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_download(url: str, destination: Path) -> None:
    """Download *url* to *destination* if the file does not yet exist."""
    if destination.exists():
        return
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    destination.write_bytes(response.content)


@dataclass(frozen=True)
class MerchantRecord:
    merchant_id: int
    mcc: int
    channel: str
    home_country_iso: str


# ----------------------------- Core pipeline ---------------------------------


def load_mcc_table(path: Path) -> pl.DataFrame:
    df = pl.read_csv(path, infer_schema_length=0, ignore_errors=False)
    if "mcc" not in df.columns:
        raise ValueError("mcc column missing in MCC codes dataset")
    desc_cols = [
        col
        for col in (
            "edited_description",
            "combined_description",
            "usda_description",
            "irs_description",
        )
        if col in df.columns
    ]
    if not desc_cols:
        raise ValueError("No description column found in MCC dataset")
    desc_expr = pl.col(desc_cols[0])
    for col in desc_cols[1:]:
        desc_expr = desc_expr.fill_null(pl.col(col))
    df = df.with_columns(
        pl.col("mcc").cast(pl.Int32),
        desc_expr.fill_null("").alias("description"),
    )
    if df.height == 0:
        raise ValueError("MCC codes dataset is empty")
    return df


def load_iso_table(path: Path) -> pl.DataFrame:
    df = pl.read_csv(path, infer_schema_length=0, ignore_errors=False)
    alpha2_col = None
    for cand in ("ISO3166-1-Alpha-2", "ISO3166-1-Alpha-2 code", "Alpha-2 code"):
        if cand in df.columns:
            alpha2_col = cand
            break
    if alpha2_col is None:
        raise ValueError("Alpha-2 ISO column not found in ISO dataset")
    df = df.select(
        pl.col(alpha2_col).alias("iso2"),
        pl.col("CLDR display name").alias("name").fill_null(pl.col("official_name_en")),
        pl.col("Region Name").alias("region").fill_null("")
    )
    df = df.filter(pl.col("iso2").str.len_bytes() == 2)
    df = df.filter(pl.col("iso2").str.contains(r"^[A-Z]{2}$"))
    return df.unique("iso2").sort("iso2")


def derive_channel(description: str, mcc: int) -> str:
    if description is None:
        description = ""
    lowered = description.lower()
    if mcc in CNP_MCC_OVERRIDES:
        return "card_not_present"
    if any(keyword in lowered for keyword in CNP_KEYWORDS):
        return "card_not_present"
    return "card_present"


def build_channel_map(mcc_df: pl.DataFrame) -> Dict[int, str]:
    channels = {}
    for row in mcc_df.iter_rows(named=True):
        mcc = int(row["mcc"])
        desc = row.get("description") or ""
        channel = derive_channel(desc, mcc)
        channels[mcc] = channel
    return channels


def deterministic_int(seed_text: str, modulo: int, offset: int = 0) -> int:
    value = int.from_bytes(hashlib.sha256(seed_text.encode("utf-8")).digest()[:8], "big")
    return offset + (value % modulo)


def generate_merchants(iso_df: pl.DataFrame, mcc_list: List[int], channel_map: Dict[int, str]) -> List[MerchantRecord]:
    records: List[MerchantRecord] = []
    total_mcc = len(mcc_list)
    if total_mcc == 0:
        raise ValueError("No MCC codes available for merchant generation")
    for iso_index, iso_code in enumerate(iso_df["iso2"].to_list(), start=1):
        merchant_count = 2 + deterministic_int(f"count::{iso_code}", modulo=4, offset=0)
        for local_idx in range(merchant_count):
            mcc_idx = deterministic_int(f"mcc::{iso_code}::{local_idx}", modulo=total_mcc)
            mcc = mcc_list[mcc_idx]
            channel = channel_map.get(mcc, "card_present")
            merchant_id = iso_index * 10_000 + local_idx + 1
            records.append(
                MerchantRecord(
                    merchant_id=merchant_id,
                    mcc=mcc,
                    channel=channel,
                    home_country_iso=iso_code,
                )
            )
    return records


def validate_records(records: Iterable[MerchantRecord], iso_df: pl.DataFrame, mcc_set: set[int]) -> None:
    seen_ids = set()
    iso_set = set(iso_df["iso2"].to_list())
    allowed_channels = {"card_present", "card_not_present"}
    for rec in records:
        if rec.merchant_id in seen_ids:
            raise ValueError(f"Duplicate merchant_id detected: {rec.merchant_id}")
        seen_ids.add(rec.merchant_id)
        if rec.mcc not in mcc_set:
            raise ValueError(f"Unknown MCC code: {rec.mcc}")
        if rec.home_country_iso not in iso_set:
            raise ValueError(f"Unknown ISO country code: {rec.home_country_iso}")
        if rec.channel not in allowed_channels:
            raise ValueError(f"Invalid channel value: {rec.channel}")


# ----------------------------- Manifest builder ------------------------------


def git_commit_hex() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "unknown"


def write_manifest(
    *,
    row_count: int,
    iso_df: pl.DataFrame,
    records_df: pl.DataFrame,
    artefact_digests: Dict[str, str],
    output_digests: Dict[str, str],
) -> None:
    channel_counts = (
        records_df.group_by("channel")
        .len()
        .sort("channel")
        .to_dict(as_series=False)
    )
    manifest = {
        "dataset_id": DATASET_ID,
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/build_transaction_schema_merchant_ids.py",
        "git_commit_hex": git_commit_hex(),
        "row_count": row_count,
        "distinct_iso": records_df.select(pl.col("home_country_iso").n_unique()).item(),
        "distinct_mcc": records_df.select(pl.col("mcc").n_unique()).item(),
        "channel_counts": dict(zip(channel_counts["channel"], channel_counts["len"])),
        "iso_coverage": iso_df["iso2"].to_list(),
        "input_artifacts": artefact_digests,
        "output_files": output_digests,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


# ----------------------------- Main entrypoint -------------------------------


def build_dataset() -> None:
    # Acquire raw artefacts
    for source in RAW_SOURCES.values():
        ensure_download(source["url"], RAW_DIR / source["filename"])

    # Load canonical tables
    mcc_df = load_mcc_table(RAW_DIR / RAW_SOURCES["mcc_codes"]["filename"])
    iso_df = load_iso_table(RAW_DIR / RAW_SOURCES["iso_country_codes"]["filename"])

    # Build deterministic merchants
    channel_map = build_channel_map(mcc_df)
    records = generate_merchants(iso_df, mcc_df["mcc"].to_list(), channel_map)
    validate_records(records, iso_df, set(channel_map.keys()))

    records_df = pl.DataFrame(records).sort("merchant_id")

    # Persist outputs
    records_df.write_csv(CSV_PATH, include_header=True)
    records_df.write_parquet(PARQUET_PATH, compression="zstd", statistics=True)

    artefact_digests = {
        str((RAW_DIR / data["filename"]).relative_to(ROOT)): sha256sum(RAW_DIR / data["filename"])
        for data in RAW_SOURCES.values()
    }
    output_digests = {
        str(CSV_PATH.relative_to(ROOT)): sha256sum(CSV_PATH),
        str(PARQUET_PATH.relative_to(ROOT)): sha256sum(PARQUET_PATH),
    }
    write_manifest(
        row_count=records_df.height,
        iso_df=iso_df,
        records_df=records_df,
        artefact_digests=artefact_digests,
        output_digests=output_digests,
    )

    # Collate SHA256 sums for convenience
    combined = {**artefact_digests, **output_digests}
    sha_lines = [f"{digest}  {name}" for name, digest in sorted(combined.items())]
    SHA_PATH.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force regeneration by deleting existing outputs before running",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rebuild:
        for path in (CSV_PATH, PARQUET_PATH, MANIFEST_PATH, SHA_PATH):
            if path.exists():
                path.unlink()
    build_dataset()


if __name__ == "__main__":
    main()
