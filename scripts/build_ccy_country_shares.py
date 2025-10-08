"""Build the ccy_country_shares_2024Q4 dataset using blended priors."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import polars as pl
import yaml


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_BASE = ROOT / "reference" / "network" / "ccy_country_shares"


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_iso_set(path: Path) -> set[str]:
    df = pl.read_parquet(path)
    return set(df["country_iso"].to_list())


def load_shares(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)


@dataclass
class CurrencyOverride:
    iso: List[str]
    weights: Dict[str, float]


def load_overrides(path: Path | None) -> Dict[str, CurrencyOverride]:
    if path is None:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    overrides: Dict[str, CurrencyOverride] = {}
    for currency, cfg in data.get("currencies", {}).items():
        iso_list = [str(v).upper() for v in cfg.get("iso", [])]
        weights = {str(k).upper(): float(v) for k, v in cfg.get("weights", {}).items()}
        overrides[currency.upper()] = CurrencyOverride(iso=iso_list, weights=weights)
    return overrides


def quantize(values: List[float], scale: int) -> List[int]:
    raw = [v * scale for v in values]
    floors = [math.floor(x) for x in raw]
    residuals = [x - math.floor(x) for x in raw]
    remainder = scale - sum(floors)
    order = sorted(range(len(values)), key=lambda idx: residuals[idx], reverse=True)
    for idx in order:
        if remainder <= 0:
            break
        floors[idx] += 1
        remainder -= 1
    return floors


def blend_shares(
    currency: str,
    settlement_df: pl.DataFrame,
    overrides: Dict[str, CurrencyOverride],
    iso_set: set[str],
) -> Tuple[List[Dict[str, object]], Dict[str, float]]:
    base = settlement_df.filter(pl.col("currency") == currency)
    if base.height == 0:
        raise ValueError(f"No settlement shares for currency {currency}")

    iso_list = base["country_iso"].to_list()
    shares = base["share"].to_list()
    obs_counts = base["obs_count"].to_list()

    override_cfg = overrides.get(currency)
    if override_cfg:
        weight_map = override_cfg.weights
        iso_list_override = override_cfg.iso or iso_list
        weights = [weight_map.get(iso, 1.0) for iso in iso_list_override]
        total = sum(weights)
        if total <= 0:
            weights = [1.0 for _ in weights]
            total = float(len(weights))
        shares = [w / total for w in weights]
        iso_list = iso_list_override
        obs_counts = [max(1, int(total * share)) for share in shares]

    quantized = quantize(shares, 10**6)
    shares = [q / 10**6 for q in quantized]

    rows: List[Dict[str, object]] = []
    for iso, share, obs in zip(iso_list, shares, obs_counts):
        if iso not in iso_set:
            raise ValueError(f"Currency {currency} references unknown ISO {iso}")
        rows.append(
            {
                "currency": currency,
                "country_iso": iso,
                "share": share,
                "obs_count": int(obs),
            }
        )
    return rows, {"sum_share": round(sum(shares), 6)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2025-10-08")
    parser.add_argument("--iso-table", required=True, type=Path)
    parser.add_argument("--settlement-shares", required=True, type=Path)
    parser.add_argument("--overrides", type=Path, default=None)
    args = parser.parse_args()

    iso_path = args.iso_table.resolve()
    settlement_path = args.settlement_shares.resolve()
    overrides_path = args.overrides.resolve() if args.overrides else None

    iso_set = load_iso_set(iso_path)
    settlement_df = load_shares(settlement_path)
    overrides = load_overrides(overrides_path)

    output_dir = REFERENCE_BASE / args.version
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, object]] = []
    qa: Dict[str, Dict[str, float]] = {}
    for currency in settlement_df.select("currency").unique().sort("currency")["currency"].to_list():
        cur_rows, stats = blend_shares(currency, settlement_df, overrides, iso_set)
        rows.extend(cur_rows)
        qa[currency] = stats

    df = pd.DataFrame(rows)
    df.sort_values(["currency", "share"], ascending=[True, False], inplace=True)

    for code, grp in df.groupby("currency"):
        if abs(grp["share"].sum() - 1.0) > 1e-6:
            raise ValueError(f"Share sum validation failed for {code}")

    csv_path = output_dir / "ccy_country_shares.csv"
    parquet_path = output_dir / "ccy_country_shares.parquet"
    qa_path = output_dir / "ccy_country_shares.qa.json"
    manifest_path = output_dir / "ccy_country_shares.manifest.json"
    sha_path = output_dir / "SHA256SUMS"

    df.to_csv(csv_path, index=False)
    pl.from_pandas(df).write_parquet(parquet_path, compression="zstd", statistics=True)

    qa_payload = {
        "row_count": int(len(df)),
        "currency_count": int(df["currency"].nunique()),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "per_currency": qa,
    }
    qa_path.write_text(json.dumps(qa_payload, indent=2), encoding="utf-8")

    manifest = {
        "dataset_id": "ccy_country_shares_2024Q4",
        "version": args.version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/build_ccy_country_shares.py",
        "iso_table": str(iso_path.relative_to(ROOT)),
        "iso_table_sha256": sha256sum(iso_path),
        "settlement_shares": str(settlement_path.relative_to(ROOT)),
        "settlement_shares_sha256": sha256sum(settlement_path),
    }
    if overrides_path:
        manifest["overrides"] = str(overrides_path.relative_to(ROOT))
        manifest["overrides_sha256"] = sha256sum(overrides_path)

    manifest.update(
        {
            "output_csv": str(csv_path.relative_to(ROOT)),
            "output_csv_sha256": sha256sum(csv_path),
            "output_parquet": str(parquet_path.relative_to(ROOT)),
            "output_parquet_sha256": sha256sum(parquet_path),
            "qa_path": str(qa_path.relative_to(ROOT)),
            "qa_sha256": sha256sum(qa_path),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    sha_lines = [
        f"{manifest['iso_table_sha256']}  {manifest['iso_table']}",
        f"{manifest['settlement_shares_sha256']}  {manifest['settlement_shares']}",
        f"{manifest['output_csv_sha256']}  {manifest['output_csv']}",
        f"{manifest['output_parquet_sha256']}  {manifest['output_parquet']}",
        f"{manifest['qa_sha256']}  {manifest['qa_path']}",
    ]
    if overrides_path:
        sha_lines.append(f"{manifest['overrides_sha256']}  {manifest['overrides']}")
    sha_path.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
