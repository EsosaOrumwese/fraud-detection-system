"""Score Segment 1B P1 candidate run against P0 baseline authority."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from scipy.spatial import cKDTree


EARTH_RADIUS_M = 6_371_008.8
TOP_FRACTIONS = {"top1": 0.01, "top5": 0.05, "top10": 0.10}
REGION_KEYS = (
    "Africa",
    "Asia",
    "Europe",
    "North America",
    "South America",
    "Oceania",
    "Other",
)


@dataclass(frozen=True)
class RunContext:
    run_root: Path
    run_id: str
    seed: int
    manifest_fingerprint: str
    parameter_hash: str


def _now_utc() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _gini(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(v for v in values if v >= 0)
    total = float(sum(vals))
    n = len(vals)
    if n == 0 or total <= 0:
        return 0.0
    weighted = sum((2 * (idx + 1) - n - 1) * value for idx, value in enumerate(vals))
    return float(weighted / (n * total))


def _top_share(values_desc: list[float], fraction: float) -> float:
    if not values_desc:
        return 0.0
    total = float(sum(values_desc))
    if total <= 0:
        return 0.0
    k = max(1, math.ceil(fraction * len(values_desc)))
    return float(sum(values_desc[:k]) / total)


def _nn_distances_m(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    if lat_deg.size < 2:
        return np.array([], dtype=np.float64)
    lat_rad = np.radians(lat_deg.astype(np.float64))
    lon_rad = np.radians(lon_deg.astype(np.float64))
    cos_lat = np.cos(lat_rad)
    xyz = np.column_stack(
        (
            cos_lat * np.cos(lon_rad),
            cos_lat * np.sin(lon_rad),
            np.sin(lat_rad),
        )
    )
    tree = cKDTree(xyz)
    distances, _ = tree.query(xyz, k=2)
    chord = np.clip(distances[:, 1], 0.0, 2.0)
    arc = 2.0 * np.arcsin(np.clip(chord / 2.0, 0.0, 1.0))
    return arc * EARTH_RADIUS_M


def _quantile(values: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    return float(np.quantile(values, q))


def _load_run_context(runs_root: Path, run_id: str) -> RunContext:
    run_root = runs_root / run_id
    receipt = json.loads((run_root / "run_receipt.json").read_text(encoding="utf-8"))
    return RunContext(
        run_root=run_root,
        run_id=run_id,
        seed=int(receipt["seed"]),
        manifest_fingerprint=str(receipt["manifest_fingerprint"]),
        parameter_hash=str(receipt["parameter_hash"]),
    )


def _resolve_site_locations(ctx: RunContext) -> Path:
    root = (
        ctx.run_root
        / "data"
        / "layer1"
        / "1B"
        / "site_locations"
        / f"seed={ctx.seed}"
        / f"manifest_fingerprint={ctx.manifest_fingerprint}"
    )
    return next(root.glob("*.parquet"))


def _resolve_report(ctx: RunContext, state: str, filename: str) -> Path:
    reports_root = ctx.run_root / "reports" / "layer1" / "1B"
    if state == "S2":
        return reports_root / "state=S2" / f"parameter_hash={ctx.parameter_hash}" / filename
    if state == "S4":
        return (
            reports_root
            / "state=S4"
            / f"seed={ctx.seed}"
            / f"parameter_hash={ctx.parameter_hash}"
            / f"manifest_fingerprint={ctx.manifest_fingerprint}"
            / filename
        )
    if state == "S8":
        return (
            reports_root
            / "state=S8"
            / f"seed={ctx.seed}"
            / f"manifest_fingerprint={ctx.manifest_fingerprint}"
            / filename
        )
    raise ValueError(f"Unsupported state: {state}")


def _macro_region(region: str, subregion: str) -> str:
    region_s = (region or "").strip()
    subregion_s = (subregion or "").strip().lower()
    if region_s in {"Africa", "Asia", "Europe", "Oceania"}:
        return region_s
    if region_s == "Americas":
        if "south" in subregion_s or "latin america" in subregion_s:
            return "South America"
        return "North America"
    if "south america" in subregion_s or "latin america" in subregion_s:
        return "South America"
    if "north america" in subregion_s or "caribbean" in subregion_s:
        return "North America"
    return "Other"


def _load_region_lookup(repo_root: Path) -> dict[str, str]:
    candidates = [
        repo_root
        / "reference"
        / "_untracked"
        / "reference"
        / "layer1"
        / "iso_canonical"
        / "v2025-10-09"
        / "iso_canonical.csv",
        repo_root
        / "reference"
        / "_untracked"
        / "reference"
        / "layer1"
        / "iso_canonical"
        / "v2025-10-08"
        / "iso_canonical.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        mapping: dict[str, str] = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                iso = (row.get("country_iso") or "").strip().upper()
                if not iso:
                    continue
                mapping[iso] = _macro_region(
                    row.get("region") or "",
                    row.get("subregion") or "",
                )
        if mapping:
            return mapping

    iso_path = repo_root / "reference" / "iso" / "iso3166_canonical" / "2024-12-31" / "iso3166.parquet"
    if iso_path.exists():
        df = pl.read_parquet(iso_path, columns=["country_iso", "region", "subregion"])
        return {
            str(row["country_iso"]).upper(): _macro_region(
                str(row.get("region") or ""),
                str(row.get("subregion") or ""),
            )
            for row in df.to_dicts()
        }
    return {}


def _site_metrics(site_path: Path, eligible_countries_total: int) -> dict[str, float]:
    site_df = pl.read_parquet(site_path).select(["legal_country_iso", "lat_deg", "lon_deg"])
    country_counts_df = (
        site_df.group_by("legal_country_iso")
        .len()
        .rename({"legal_country_iso": "country_iso", "len": "site_count"})
        .sort("site_count", descending=True)
    )
    counts = [float(v) for v in country_counts_df["site_count"].to_list()]
    nn = _nn_distances_m(site_df["lat_deg"].to_numpy(), site_df["lon_deg"].to_numpy())
    q50 = _quantile(nn, 0.50)
    q99 = _quantile(nn, 0.99)
    total_sites = int(site_df.height)
    return {
        "country_gini": _gini(counts),
        "top1_share": _top_share(counts, TOP_FRACTIONS["top1"]),
        "top5_share": _top_share(counts, TOP_FRACTIONS["top5"]),
        "top10_share": _top_share(counts, TOP_FRACTIONS["top10"]),
        "eligible_country_nonzero_share": (
            float(len(counts) / eligible_countries_total) if eligible_countries_total > 0 else 0.0
        ),
        "southern_hemisphere_share": (
            float((site_df["lat_deg"] < 0.0).sum() / total_sites) if total_sites > 0 else 0.0
        ),
        "nn_p99_p50_ratio": float(q99 / q50) if q50 > 0 else 0.0,
        "site_count_total": float(total_sites),
        "active_country_count": float(len(counts)),
    }


def _baseline_s2_proxy(
    baseline_run_root: Path,
    parameter_hash: str,
    region_lookup: dict[str, str],
) -> dict[str, Any]:
    path = (
        baseline_run_root
        / "reports"
        / "layer1"
        / "1B"
        / "state=S2"
        / f"parameter_hash={parameter_hash}"
        / "s2_run_report.json"
    )
    report = json.loads(path.read_text(encoding="utf-8"))
    summaries = report.get("country_summaries") or []
    country_mass: list[tuple[str, float]] = []
    for row in summaries:
        iso = str(row.get("country_iso") or "")
        mass = float(row.get("mass_sum") or 0.0)
        if iso:
            country_mass.append((iso, mass))
    masses = [v for _, v in country_mass]
    total = float(sum(masses))
    shares = [(iso, (mass / total if total > 0 else 0.0)) for iso, mass in country_mass]
    share_values_desc = sorted([v for _, v in shares], reverse=True)

    region_share = {key: 0.0 for key in REGION_KEYS}
    for iso, share in shares:
        region = region_lookup.get(iso, "Other")
        if region not in region_share:
            region = "Other"
        region_share[region] += float(share)
    return {
        "country_gini_proxy": _gini(share_values_desc),
        "country_share_topk": {
            key: _top_share(share_values_desc, frac) for key, frac in TOP_FRACTIONS.items()
        },
        "region_share_vector": region_share,
        "countries_total": len(share_values_desc),
    }


def score_candidate(
    repo_root: Path,
    runs_root: Path,
    run_id: str,
    baseline_json_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    baseline = json.loads(baseline_json_path.read_text(encoding="utf-8"))
    baseline_metrics = baseline["metrics"]
    baseline_authority = baseline["baseline_authority"]
    baseline_run_root = Path(baseline_authority["run_root"])
    baseline_parameter_hash = str(baseline_authority["parameter_hash"])

    ctx = _load_run_context(runs_root, run_id)
    region_lookup = _load_region_lookup(repo_root)
    site_path = _resolve_site_locations(ctx)
    s2_report_path = _resolve_report(ctx, "S2", "s2_run_report.json")
    s4_report_path = _resolve_report(ctx, "S4", "s4_run_report.json")
    s8_report_path = _resolve_report(ctx, "S8", "s8_run_summary.json")

    s2_report = json.loads(s2_report_path.read_text(encoding="utf-8"))
    s4_report = json.loads(s4_report_path.read_text(encoding="utf-8"))
    s8_report = json.loads(s8_report_path.read_text(encoding="utf-8"))

    baseline_s2_proxy = _baseline_s2_proxy(
        baseline_run_root=baseline_run_root,
        parameter_hash=baseline_parameter_hash,
        region_lookup=region_lookup,
    )
    candidate_site_metrics = _site_metrics(
        site_path,
        eligible_countries_total=int(s2_report.get("countries_total", 0)),
    )

    candidate_topk = s2_report.get("country_share_topk", {})
    candidate_region_share = s2_report.get("region_share_vector", {})
    blend_diag = s2_report.get("blend_v2_diagnostics", {})
    region_floor_share = blend_diag.get("region_floor_share", {})
    floor_breaches: list[dict[str, float | str]] = []
    for key in REGION_KEYS:
        floor = float(region_floor_share.get(key, 0.0))
        observed = float(candidate_region_share.get(key, 0.0))
        if floor > 0.0 and observed + 1.0e-12 < floor:
            floor_breaches.append({"region": key, "floor": floor, "observed": observed})

    checks = {
        "blend_v2_enabled": bool(s2_report.get("blend_v2_enabled", False)),
        "s2_diagnostics_present": all(
            key in s2_report for key in ("country_share_topk", "country_gini_proxy", "region_share_vector")
        ),
        "s2_gini_proxy_improved_vs_p0_s2": float(s2_report.get("country_gini_proxy", 1.0))
        < float(baseline_s2_proxy["country_gini_proxy"]),
        "s2_top10_proxy_improved_vs_p0_s2": float(candidate_topk.get("top10", 1.0))
        < float(baseline_s2_proxy["country_share_topk"]["top10"]),
        "s2_region_floor_breaches_none": len(floor_breaches) == 0,
        "s8_concentration_not_worse_than_p0": (
            candidate_site_metrics["country_gini"] <= float(baseline_metrics["country_gini"]) + 1.0e-12
            and candidate_site_metrics["top10_share"] <= float(baseline_metrics["top10_share"]) + 1.0e-12
            and candidate_site_metrics["top5_share"] <= float(baseline_metrics["top5_share"]) + 1.0e-12
            and candidate_site_metrics["top1_share"] <= float(baseline_metrics["top1_share"]) + 1.0e-12
        ),
        "s8_parity_ok": bool(
            s8_report.get("parity_ok", False)
            or (s8_report.get("sizes") or {}).get("parity_ok", False)
        ),
        "s4_alloc_sum_equals_requirements": bool(s4_report.get("alloc_sum_equals_requirements", False)),
    }

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P1",
        "segment": "1B",
        "candidate": {
            "run_id": ctx.run_id,
            "seed": ctx.seed,
            "manifest_fingerprint": ctx.manifest_fingerprint,
            "parameter_hash": ctx.parameter_hash,
            "run_root": str(ctx.run_root.resolve()),
        },
        "baseline_authority": baseline_authority,
        "artifacts": {
            "candidate_s2_report": str(s2_report_path.resolve()),
            "candidate_s4_report": str(s4_report_path.resolve()),
            "candidate_s8_report": str(s8_report_path.resolve()),
            "candidate_site_locations": str(site_path.resolve()),
            "baseline_scorecard": str(baseline_json_path.resolve()),
        },
        "s2_proxy": {
            "baseline": baseline_s2_proxy,
            "candidate": {
                "country_gini_proxy": float(s2_report.get("country_gini_proxy", 0.0)),
                "country_share_topk": {
                    "top1": float(candidate_topk.get("top1", 0.0)),
                    "top5": float(candidate_topk.get("top5", 0.0)),
                    "top10": float(candidate_topk.get("top10", 0.0)),
                },
                "region_share_vector": {
                    key: float(candidate_region_share.get(key, 0.0)) for key in REGION_KEYS
                },
                "blend_v2_diagnostics": blend_diag,
            },
            "floor_breaches": floor_breaches,
        },
        "s8_metrics": {
            "baseline": baseline_metrics,
            "candidate": candidate_site_metrics,
            "delta_candidate_minus_baseline": {
                key: float(candidate_site_metrics.get(key, 0.0) - float(baseline_metrics.get(key, 0.0)))
                for key in (
                    "country_gini",
                    "top1_share",
                    "top5_share",
                    "top10_share",
                    "eligible_country_nonzero_share",
                    "southern_hemisphere_share",
                    "nn_p99_p50_ratio",
                )
            },
        },
        "checks": checks,
        "checks_all_pass": all(checks.values()),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"segment1b_p1_candidate_{run_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2), encoding="utf-8")
    return {"payload": payload, "out_path": out_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 1B P1 candidate run.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root.",
    )
    parser.add_argument(
        "--runs-root",
        default="runs/fix-data-engine/segment_1B",
        help="Runs root containing candidate run-id.",
    )
    parser.add_argument("--run-id", required=True, help="Candidate run_id.")
    parser.add_argument(
        "--baseline-json",
        required=True,
        help="P0 baseline scorecard JSON path.",
    )
    parser.add_argument(
        "--output-dir",
        default="runs/fix-data-engine/segment_1B/reports",
        help="Output directory for P1 scorecard.",
    )
    args = parser.parse_args()

    result = score_candidate(
        repo_root=Path(args.repo_root),
        runs_root=Path(args.runs_root),
        run_id=args.run_id,
        baseline_json_path=Path(args.baseline_json),
        output_dir=Path(args.output_dir),
    )
    print(str(result["out_path"]))


if __name__ == "__main__":
    main()
