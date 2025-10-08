"""Build the settlement_shares_2024Q4 dataset using GDP-weighted approximations."""
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
REFERENCE_BASE = ROOT / "reference" / "network" / "settlement_shares"


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_iso_set(path: Path) -> set[str]:
    df = pl.read_parquet(path)
    return set(df["country_iso"].to_list())


def load_gdp_table(path: Path) -> Dict[str, float]:
    df = pl.read_parquet(path)
    if "gdp_pc_usd_2015" not in df.columns:
        raise ValueError("GDP table missing gdp_pc_usd_2015 column")
    return dict(zip(df["country_iso"].to_list(), df["gdp_pc_usd_2015"].to_list()))


@dataclass
class CurrencyConfig:
    iso: List[str]
    total_obs: int


def load_currency_policy(path: Path) -> Tuple[Dict[str, CurrencyConfig], Dict[str, float]]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    defaults = data.get("defaults", {})
    default_total_obs = int(defaults.get("total_obs", 100000))
    epsilon_share = float(defaults.get("epsilon_share", 1e-6))
    min_obs = int(defaults.get("min_obs_per_pair", 1))
    currencies: Dict[str, CurrencyConfig] = {}
    for code, cfg in data.get("currencies", {}).items():
        iso_list = [str(v).upper() for v in cfg.get("iso", [])]
        if not iso_list:
            raise ValueError(f"Currency {code} has empty ISO list")
        total_obs = int(cfg.get("total_obs", default_total_obs))
        currencies[code.upper()] = CurrencyConfig(iso=iso_list, total_obs=total_obs)
    return currencies, {"epsilon_share": epsilon_share, "min_obs_per_pair": max(1, min_obs)}


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


def build_rows(
    currency: str,
    cfg: CurrencyConfig,
    gdp_map: Dict[str, float],
    iso_set: set[str],
    epsilon: float,
    min_obs: int,
) -> Tuple[List[Dict[str, object]], Dict[str, float]]:
    weights: List[float] = []
    for iso in cfg.iso:
        if iso not in iso_set:
            raise ValueError(f"Currency {currency} references unknown ISO {iso}")
        value = gdp_map.get(iso)
        if value is None or value <= 0.0:
            value = epsilon
        weights.append(float(value))

    total = sum(weights)
    if total <= 0.0:
        weights = [1.0 for _ in weights]
        total = float(len(weights))

    raw_shares = [w / total for w in weights]
    share_ints = quantize(raw_shares, 10**6)
    shares = [i / 10**6 for i in share_ints]

    base_min = max(1, min_obs)
    if base_min * len(cfg.iso) > cfg.total_obs:
        base_min = 1
    counts = [base_min] * len(cfg.iso)
    remaining = cfg.total_obs - base_min * len(cfg.iso)
    if remaining < 0:
        remaining = 0
    extra_ints = quantize(shares, remaining) if remaining > 0 else [0] * len(cfg.iso)
    counts = [base + extra for base, extra in zip(counts, extra_ints)]
    delta = cfg.total_obs - sum(counts)
    if delta != 0:
        order = sorted(range(len(cfg.iso)), key=lambda idx: shares[idx], reverse=True)
        for idx in order:
            if delta == 0:
                break
            counts[idx] += 1 if delta > 0 else -1
            delta += -1 if delta > 0 else 1

    rows: List[Dict[str, object]] = []
    for iso, share, obs in zip(cfg.iso, shares, counts):
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
    parser.add_argument("--gdp-table", required=True, type=Path)
    parser.add_argument("--legal-tender", required=True, type=Path)
    args = parser.parse_args()

    iso_path = args.iso_table.resolve()
    gdp_path = args.gdp_table.resolve()
    policy_path = args.legal_tender.resolve()

    iso_set = load_iso_set(iso_path)
    gdp_map = load_gdp_table(gdp_path)
    currencies, defaults = load_currency_policy(policy_path)
    epsilon = defaults["epsilon_share"]
    min_obs = defaults["min_obs_per_pair"]

    output_dir = REFERENCE_BASE / args.version
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, object]] = []
    qa: Dict[str, Dict[str, float]] = {}
    for code, cfg in currencies.items():
        cur_rows, stats = build_rows(code, cfg, gdp_map, iso_set, epsilon, min_obs)
        rows.extend(cur_rows)
        qa[code] = stats

    df = pd.DataFrame(rows)
    df.sort_values(["currency", "share"], ascending=[True, False], inplace=True)

    for code, grp in df.groupby("currency"):
        if abs(grp["share"].sum() - 1.0) > 1e-6:
            raise ValueError(f"Share sum validation failed for {code}")

    csv_path = output_dir / "settlement_shares.csv"
    parquet_path = output_dir / "settlement_shares.parquet"
    qa_path = output_dir / "settlement_shares.qa.json"
    manifest_path = output_dir / "settlement_shares.manifest.json"
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
        "dataset_id": "settlement_shares_2024Q4",
        "version": args.version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/build_settlement_shares.py",
        "iso_table": str(iso_path.relative_to(ROOT)),
        "iso_table_sha256": sha256sum(iso_path),
        "gdp_table": str(gdp_path.relative_to(ROOT)),
        "gdp_table_sha256": sha256sum(gdp_path),
        "legal_tender_policy": str(policy_path.relative_to(ROOT)),
        "legal_tender_policy_sha256": sha256sum(policy_path),
        "output_csv": str(csv_path.relative_to(ROOT)),
        "output_csv_sha256": sha256sum(csv_path),
        "output_parquet": str(parquet_path.relative_to(ROOT)),
        "output_parquet_sha256": sha256sum(parquet_path),
        "qa_path": str(qa_path.relative_to(ROOT)),
        "qa_sha256": sha256sum(qa_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    sha_lines = [
        f"{manifest['legal_tender_policy_sha256']}  {manifest['legal_tender_policy']}",
        f"{manifest['iso_table_sha256']}  {manifest['iso_table']}",
        f"{manifest['gdp_table_sha256']}  {manifest['gdp_table']}",
        f"{manifest['output_csv_sha256']}  {manifest['output_csv']}",
        f"{manifest['output_parquet_sha256']}  {manifest['output_parquet']}",
        f"{manifest['qa_sha256']}  {manifest['qa_path']}",
    ]
    sha_path.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
