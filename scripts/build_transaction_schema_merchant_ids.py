"""Policy-driven builder for the transaction_schema_merchant_ids dataset.

The script consumes versioned governance artefacts (GDP tables, bucket map,
channel and allocation policies, numeric gates) to deterministically generate
the merchant ingress universe required by S0. Outputs are written under the
reference tree with accompanying manifests and SHA256 sums.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import polars as pl
import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
DATASET_ID = "transaction_schema_merchant_ids"
REFERENCE_BASE = ROOT / "reference" / "layer1" / DATASET_ID
ARTEFACT_BASE = ROOT / "artefacts" / "data-intake" / "1A" / DATASET_ID


RAW_SOURCES = {
    "mcc_codes": {
        "url": "https://raw.githubusercontent.com/greggles/mcc-codes/master/mcc_codes.csv",
        "filename": "mcc_codes.csv",
    },
    "iso_country_codes": {
        "url": "https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv",
        "filename": "iso_country_codes.csv",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2025-10-07", help="Version tag for output partition")
    parser.add_argument("--iso-version", default="2025-10-08", help="ISO canonical version")
    parser.add_argument("--gdp-version", default="2025-10-07", help="GDP reference version")
    parser.add_argument("--bucket-version", default="2025-10-07", help="GDP bucket map version")
    parser.add_argument("--channel-policy", default="config/policy/channel_policy.1A.yaml")
    parser.add_argument("--allocation-policy", default="config/policy/merchant_allocation.1A.yaml")
    parser.add_argument("--numeric-policy", default="reference/governance/numeric_policy/2025-10-07/numeric_policy.json")
    parser.add_argument("--rebuild", action="store_true", help="Remove existing outputs before building")
    return parser.parse_args()


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_download(url: str, destination: Path) -> None:
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    destination.write_bytes(resp.content)


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_mcc_table(path: Path) -> List[int]:
    table = pl.read_csv(path, infer_schema_length=0, ignore_errors=False)
    if "mcc" not in table.columns:
        raise ValueError("MCC table missing 'mcc' column")
    return sorted(table["mcc"].cast(pl.Int32).to_list())


def load_gdp_table(version: str) -> pl.DataFrame:
    path = ROOT / "reference" / "economic" / "world_bank_gdp_per_capita" / version / "gdp.parquet"
    if not path.exists():
        raise FileNotFoundError(f"GDP parquet not found: {path}")
    return pl.read_parquet(path).select(
        pl.col("country_iso").alias("iso"),
        pl.col("gdp_pc_usd_2015").alias("gdp_pc"),
    )


def load_bucket_map(version: str) -> Dict[str, int]:
    path = ROOT / "reference" / "economic" / "gdp_bucket_map" / version / "gdp_bucket_map.parquet"
    if not path.exists():
        raise FileNotFoundError(f"GDP bucket map missing: {path}")
    df = pl.read_parquet(path).select("country_iso", "bucket_id")
    return dict(zip(df["country_iso"].to_list(), df["bucket_id"].to_list()))


def load_iso_set(version: str) -> set[str]:
    path = ROOT / "reference" / "layer1" / "iso_canonical" / f'v{version}' / 'iso_canonical.parquet'
    if not path.exists():
        raise FileNotFoundError(f"ISO canonical parquet not found: {path}")
    df = pl.read_parquet(path).select("country_iso")
    return set(df["country_iso"].to_list())


def compute_weights(gdp_df: pl.DataFrame, allocation_policy: dict) -> Dict[str, float]:
    exponent = float(allocation_policy["weighting"]["exponent"])
    weights = {row[0]: max(row[1], 0.0) ** exponent for row in gdp_df.iter_rows()}

    total = sum(weights.values())
    if total <= 0:
        raise ValueError("GDP weights sum to zero")
    for iso in weights:
        weights[iso] /= total

    adjustments = allocation_policy.get("regional_adjustments", {}) or {}
    for cfg in adjustments.values():
        iso_codes = cfg.get("iso_codes", [])
        multiplier = float(cfg.get("multiplier", 1.0))
        if multiplier == 1.0:
            continue
        for iso in iso_codes:
            if iso in weights:
                weights[iso] *= multiplier
        total = sum(weights.values())
        weights = {iso: weight / total for iso, weight in weights.items()}

    heavy_tail = float(allocation_policy["weighting"].get("heavy_tail", 0.0))
    if heavy_tail > 0:
        iso_sorted = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
        top_n = max(1, int(len(iso_sorted) * heavy_tail))
        boost = 1.0 + heavy_tail
        for iso, _ in iso_sorted[:top_n]:
            weights[iso] *= boost
        total = sum(weights.values())
        weights = {iso: weight / total for iso, weight in weights.items()}

    return weights


def allocate_merchants(weights: Dict[str, float], allocation_policy: dict) -> Dict[str, int]:
    total_merchants = int(allocation_policy["total_merchants"])
    min_per_iso = int(allocation_policy["min_per_iso"])
    max_per_iso = int(allocation_policy["max_per_iso"])

    iso_list = sorted(weights.keys())
    baseline_total = min_per_iso * len(iso_list)
    if baseline_total > total_merchants:
        raise ValueError("Total merchants below minimum per ISO requirement")

    counts = {iso: min_per_iso for iso in iso_list}
    remaining = total_merchants - baseline_total

    if remaining == 0:
        return counts

    capacity = {iso: max(0, max_per_iso - counts[iso]) for iso in iso_list}
    if sum(capacity.values()) < remaining:
        raise ValueError("Total merchants exceed available capacity given max_per_iso")

    usable_weights = {iso: weights[iso] if capacity[iso] > 0 else 0.0 for iso in iso_list}
    total_weight = sum(usable_weights.values())
    if total_weight <= 0:
        raise ValueError("No weight available for allocation")

    raw_extra = {iso: (usable_weights[iso] / total_weight) * remaining for iso in iso_list}
    extra = {iso: min(capacity[iso], math.floor(raw_extra[iso])) for iso in iso_list}
    leftover = remaining - sum(extra.values())

    if leftover > 0:
        fractional = {
            iso: raw_extra[iso] - math.floor(raw_extra[iso]) if capacity[iso] > extra[iso] else 0.0
            for iso in iso_list
        }
        eligible = [iso for iso in iso_list if capacity[iso] > extra[iso]]
        eligible.sort(key=lambda iso: (-fractional[iso], iso))
        for iso in eligible:
            if leftover <= 0:
                break
            counts_available = capacity[iso] - extra[iso]
            grant = min(counts_available, leftover)
            extra[iso] += grant
            leftover -= grant

    if leftover != 0:
        raise RuntimeError("Unable to reconcile merchant allocation totals")

    for iso in iso_list:
        counts[iso] += extra[iso]

    return counts


def deterministic_id(iso: str, idx: int, seed: str) -> int:
    payload = f"{iso}:{idx}:{seed}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big")


def assign_mcc_sequence(count: int, mccs: List[int], iso: str, bucket: int, seed: str) -> List[int]:
    total = len(mccs)
    if total == 0:
        raise ValueError("No MCC codes available")
    assigned = []
    for idx in range(count):
        payload = hashlib.sha256(f"{iso}:{bucket}:{seed}:{idx}:mcc".encode("utf-8")).digest()
        assigned.append(mccs[int.from_bytes(payload[:4], "big") % total])
    return assigned


def initial_channel(mcc: int, policy: dict) -> str:
    default = policy.get("default_channel", "card_present")
    for band in policy.get("targets", {}).get("mcc_bands", []):
        start, end = band.get("range", [0, 0])
        if start <= mcc <= end:
            return band.get("default_channel", default)
    return default


def adjust_iso_channels(records: List[Dict[str, object]], iso: str, policy: dict) -> None:
    total = len(records)
    if total == 0:
        return
    tol = float(policy["tolerance"]["channel_ratio_abs"])
    global_bounds = policy["targets"]["global"]["card_not_present"]
    override = policy["targets"].get("iso_overrides", {}).get(iso)
    bounds = override.get("card_not_present") if override else global_bounds
    min_ratio = float(bounds["min_ratio"])
    max_ratio = float(bounds["max_ratio"])

    min_count = max(0, math.floor((min_ratio - tol) * total))
    max_count = min(total, math.ceil((max_ratio + tol) * total))
    target_ratio = (min_ratio + max_ratio) / 2
    desired = min(max(round(target_ratio * total), min_count), max_count)
    current = sum(1 for rec in records if rec["channel"] == "card_not_present")

    if desired == current:
        return

    delta = desired - current

    if delta > 0:
        candidates = [rec for rec in records if rec["channel"] == "card_present"]
        if len(candidates) < delta:
            raise ValueError(f"ISO {iso} lacks CP merchants to reach CNP target")
        ordered = sorted(
            candidates,
            key=lambda rec: hashlib.sha256(f"{rec['merchant_id']}:flip-up".encode("utf-8")).digest(),
        )
        for rec in ordered[:delta]:
            rec["channel"] = "card_not_present"
    elif delta < 0:
        amount = -delta
        candidates = [rec for rec in records if rec["channel"] == "card_not_present"]
        if len(candidates) < amount:
            raise ValueError(f"ISO {iso} lacks CNP merchants to reduce")
        ordered = sorted(
            candidates,
            key=lambda rec: hashlib.sha256(f"{rec['merchant_id']}:flip-down".encode("utf-8")).digest(),
        )
        for rec in ordered[:amount]:
            rec["channel"] = "card_present"

    final = sum(1 for rec in records if rec["channel"] == "card_not_present")
    if not (min_count <= final <= max_count):
        raise ValueError(f"ISO {iso} channel adjustment failed to reach bounds")


def compute_channel_mix(records: List[Dict[str, object]]) -> Dict[str, float]:
    counts = defaultdict(int)
    for rec in records:
        counts[rec["channel"]] += 1
    total = len(records)
    return {channel: count / total for channel, count in counts.items()}


def enforce_global_mix(records: List[Dict[str, object]], policy: dict) -> None:
    mix = compute_channel_mix(records)
    tol = float(policy["tolerance"]["channel_ratio_abs"])
    for channel, bounds in policy["targets"]["global"].items():
        ratio = mix.get(channel, 0.0)
        if not (bounds["min_ratio"] - tol <= ratio <= bounds["max_ratio"] + tol):
            raise ValueError(f"Global channel mix for {channel} out of bounds: {ratio:.4f}")


def git_commit_hex() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "unknown"


def build_dataset(args: argparse.Namespace) -> None:
    output_dir = REFERENCE_BASE / f"v{args.version}"
    raw_dir = ARTEFACT_BASE / args.version / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / f"{DATASET_ID}.csv"
    parquet_path = output_dir / f"{DATASET_ID}.parquet"
    manifest_path = output_dir / f"{DATASET_ID}.manifest.json"
    sha_path = output_dir / "SHA256SUMS"

    if args.rebuild:
        for path in (csv_path, parquet_path, manifest_path, sha_path):
            if path.exists():
                path.unlink()

    # Acquire raw artefacts
    for spec in RAW_SOURCES.values():
        ensure_download(spec["url"], raw_dir / spec["filename"])

    mccs = load_mcc_table(raw_dir / RAW_SOURCES["mcc_codes"]["filename"])
    iso_set = load_iso_set(args.iso_version)
    gdp_df = load_gdp_table(args.gdp_version)
    bucket_map = load_bucket_map(args.bucket_version)

    valid_iso = sorted(set(bucket_map.keys()) & iso_set)
    if not valid_iso:
        raise ValueError("No overlapping ISO codes between canonical list and bucket map")

    gdp_df = gdp_df.filter(pl.col("iso").is_in(valid_iso))
    bucket_map = {iso: bucket_map[iso] for iso in valid_iso}

    channel_policy = load_yaml(ROOT / args.channel_policy)
    allocation_policy = load_yaml(ROOT / args.allocation_policy)
    numeric_policy = load_json(ROOT / args.numeric_policy)

    weights = compute_weights(gdp_df, allocation_policy)
    weights = {iso: weight for iso, weight in weights.items() if iso in valid_iso}
    counts = allocate_merchants(weights, allocation_policy)

    missing_buckets = [iso for iso in counts if iso not in bucket_map]
    if missing_buckets:
        raise ValueError(f"Bucket map missing ISO entries: {missing_buckets[:5]}")

    seed = allocation_policy.get("seed", f"{DATASET_ID}.seed")
    records: List[Dict[str, object]] = []
    iso_records: Dict[str, List[Dict[str, object]]] = {}
    seen_ids: set[int] = set()

    for iso in sorted(counts.keys()):
        count = counts[iso]
        assigned_mccs = assign_mcc_sequence(count, mccs, iso, bucket_map[iso], seed)
        iso_list: List[Dict[str, object]] = []
        for idx, mcc in enumerate(assigned_mccs):
            merchant_id = deterministic_id(iso, idx, seed)
            if merchant_id in seen_ids:
                raise ValueError(f"Duplicate merchant_id generated: {merchant_id}")
            seen_ids.add(merchant_id)
            iso_list.append(
                {
                    "merchant_id": merchant_id,
                    "mcc": int(mcc),
                    "channel": initial_channel(mcc, channel_policy),
                    "home_country_iso": iso,
                }
            )
        adjust_iso_channels(iso_list, iso, channel_policy)
        iso_records[iso] = iso_list
        records.extend(iso_list)

    enforce_global_mix(records, channel_policy)

    df = pl.DataFrame(records).sort("merchant_id")

    # Policy gates from numeric manifest
    merchants_policy = numeric_policy.get("merchants", {})
    if df.height < merchants_policy.get("total_min", 0):
        raise ValueError("Merchant count below numeric policy gate")
    iso_counts = df.group_by("home_country_iso").len()
    min_iso = iso_counts["len"].min()
    max_iso = iso_counts["len"].max()
    if min_iso < merchants_policy.get("min_per_iso", 0):
        raise ValueError("Per-ISO merchant minimum violated")
    if max_iso > merchants_policy.get("max_per_iso", 10**9):
        raise ValueError("Per-ISO merchant maximum violated")

    # Persist outputs
    df.write_csv(csv_path)
    df.write_parquet(parquet_path, compression="zstd", statistics=True)

    channel_mix = compute_channel_mix(records)
    channel_counts = df.group_by("channel").len().sort("channel").to_dict(as_series=False)

    channel_policy_numeric = numeric_policy.get("channel", {})
    cnp_ratio = channel_mix.get("card_not_present", 0.0)
    if "card_not_present_min" in channel_policy_numeric and cnp_ratio < channel_policy_numeric["card_not_present_min"]:
        raise ValueError("Global card_not_present ratio below numeric governance minimum")
    if "card_not_present_max" in channel_policy_numeric and cnp_ratio > channel_policy_numeric["card_not_present_max"]:
        raise ValueError("Global card_not_present ratio above numeric governance maximum")

    iso_stats = {
        "iso_count": iso_counts.height,
        "min_merchants_per_iso": int(min_iso),
        "max_merchants_per_iso": int(max_iso),
    }

    artefact_digests = {}
    for spec in RAW_SOURCES.values():
        path = raw_dir / spec["filename"]
        artefact_digests[str(path.relative_to(ROOT))] = sha256sum(path)

    policy_paths = {
        str((ROOT / args.channel_policy).relative_to(ROOT)): sha256sum(ROOT / args.channel_policy),
        str((ROOT / args.allocation_policy).relative_to(ROOT)): sha256sum(ROOT / args.allocation_policy),
        str((ROOT / args.numeric_policy).relative_to(ROOT)): sha256sum(ROOT / args.numeric_policy),
        f"reference/economic/world_bank_gdp_per_capita/{args.gdp_version}/gdp.parquet": sha256sum(
            ROOT / "reference" / "economic" / "world_bank_gdp_per_capita" / args.gdp_version / "gdp.parquet"
        ),
        f"reference/economic/gdp_bucket_map/{args.bucket_version}/gdp_bucket_map.parquet": sha256sum(
            ROOT / "reference" / "economic" / "gdp_bucket_map" / args.bucket_version / "gdp_bucket_map.parquet"
        ),
        f"reference/layer1/iso_canonical/{args.iso_version}/iso_canonical.parquet": sha256sum(
            ROOT / "reference" / "layer1" / "iso_canonical" / f"v{args.iso_version}" / "iso_canonical.parquet"
        ),
    }

    output_digests = {
        str(csv_path.relative_to(ROOT)): sha256sum(csv_path),
        str(parquet_path.relative_to(ROOT)): sha256sum(parquet_path),
    }

    manifest = {
        "dataset_id": DATASET_ID,
        "version": args.version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/build_transaction_schema_merchant_ids.py",
        "git_commit_hex": git_commit_hex(),
        "row_count": int(df.height),
        "distinct_iso": int(df.select(pl.col("home_country_iso").n_unique()).item()),
        "distinct_mcc": int(df.select(pl.col("mcc").n_unique()).item()),
        "channel_counts": dict(zip(channel_counts.get("channel", []), channel_counts.get("len", []))),
        "channel_mix": channel_mix,
        "iso_stats": iso_stats,
        "input_artifacts": {**artefact_digests, **policy_paths},
        "output_files": output_digests,
        "gdp_version": args.gdp_version,
        "bucket_version": args.bucket_version,
        "iso_version": args.iso_version,
        "allocation_policy": allocation_policy,
        "channel_policy": {
            "policy_version": channel_policy.get("policy_version"),
            "targets": channel_policy.get("targets", {}).get("global"),
        },
    }
    (output_dir / f"{DATASET_ID}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    combined = {**artefact_digests, **policy_paths, **output_digests}
    sha_lines = [f"{digest}  {path}" for path, digest in sorted(combined.items())]
    sha_path.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    build_dataset(args)


if __name__ == "__main__":
    main()
