#!/usr/bin/env python3
"""Score Segment 2A P2 cohort-aware realism and certification verdict."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


REQUIRED_SEEDS_DEFAULT = [42, 7, 101, 202]

B_THRESHOLDS = {
    "c_multi_share_distinct_ge2_min": 0.70,
    "c_multi_median_top1_share_max": 0.92,
    "c_multi_median_top1_top2_gap_max": 0.85,
    "c_multi_median_entropy_norm_min": 0.20,
    "c_large_share_top1_lt_095_min": 0.80,
    "fallback_rate_max": 0.0005,
    "override_rate_max": 0.0020,
    "stability_cv_max": 0.30,
}

BPLUS_THRESHOLDS = {
    "c_multi_share_distinct_ge2_min": 0.85,
    "c_multi_median_top1_share_max": 0.80,
    "c_multi_median_top1_top2_gap_max": 0.65,
    "c_multi_median_entropy_norm_min": 0.35,
    "c_large_share_top1_lt_095_min": 0.95,
    "fallback_rate_max": 0.0001,
    "override_rate_max": 0.0005,
    "stability_cv_max": 0.20,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


def _normalize_country(value: object) -> str:
    if value is None:
        return "UNK"
    country = str(value).strip().upper()
    return country if country else "UNK"


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 0.0
    return float(numerator) / float(denominator)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def _cv(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = float(statistics.fmean(values))
    if abs(mean) <= 1.0e-12:
        return 0.0 if all(abs(v) <= 1.0e-12 for v in values) else float("inf")
    if len(values) < 2:
        return 0.0
    return float(statistics.pstdev(values) / mean)


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if not files:
        raise FileNotFoundError(f"No parquet files found under {root}")
    return files


def _load_tz_world_support_counts(tz_world_path: Path) -> dict[str, int]:
    table = pq.read_table(tz_world_path, columns=["country_iso", "tzid"])
    support: dict[str, set[str]] = defaultdict(set)
    for row in table.to_pylist():
        country = _normalize_country(row.get("country_iso"))
        tzid = str(row.get("tzid") or "").strip()
        if tzid:
            support[country].add(tzid)
    return {country: len(tzids) for country, tzids in support.items()}


def _find_report_path(run_root: Path, state: str, seed: int, manifest_fingerprint: str) -> Path:
    state_lower = state.lower()
    base = run_root / "reports" / "layer1" / "2A" / f"state={state}"
    if state in {"S1", "S2", "S4"}:
        return base / f"seed={seed}" / f"manifest_fingerprint={manifest_fingerprint}" / f"{state_lower}_run_report.json"
    return base / f"manifest_fingerprint={manifest_fingerprint}" / f"{state_lower}_run_report.json"


def _load_report_if_present(run_root: Path, state: str, seed: int, manifest_fingerprint: str) -> dict[str, Any] | None:
    path = _find_report_path(run_root, state, seed, manifest_fingerprint)
    if not path.exists():
        return None
    return _load_json(path)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_root: Path
    seed: int
    manifest_fingerprint: str
    receipt_mtime_ns: int


def _load_run_contexts(runs_root: Path) -> list[RunContext]:
    contexts: list[RunContext] = []
    for receipt_path in runs_root.glob("*/run_receipt.json"):
        try:
            payload = _load_json(receipt_path)
            run_id = str(payload["run_id"])
            seed = int(payload["seed"])
            manifest = str(payload["manifest_fingerprint"])
            contexts.append(
                RunContext(
                    run_id=run_id,
                    run_root=receipt_path.parent,
                    seed=seed,
                    manifest_fingerprint=manifest,
                    receipt_mtime_ns=receipt_path.stat().st_mtime_ns,
                )
            )
        except Exception:
            continue
    contexts.sort(key=lambda ctx: ctx.receipt_mtime_ns, reverse=True)
    return contexts


def _is_complete_2a_run(ctx: RunContext) -> bool:
    site_timezones_root = (
        ctx.run_root
        / "data"
        / "layer1"
        / "2A"
        / "site_timezones"
        / f"seed={ctx.seed}"
        / f"manifest_fingerprint={ctx.manifest_fingerprint}"
    )
    if not site_timezones_root.exists():
        return False
    for state in ("S1", "S2", "S3", "S4", "S5"):
        if not _find_report_path(ctx.run_root, state, ctx.seed, ctx.manifest_fingerprint).exists():
            return False
    return True


def _select_seed_run_map(
    runs_root: Path, required_seeds: list[int], explicit_seed_run_map: dict[int, str]
) -> tuple[dict[int, RunContext], list[int]]:
    contexts = _load_run_contexts(runs_root)
    by_run_id = {ctx.run_id: ctx for ctx in contexts}
    selected: dict[int, RunContext] = {}
    missing: list[int] = []

    for seed in required_seeds:
        explicit_run_id = explicit_seed_run_map.get(seed)
        if explicit_run_id:
            ctx = by_run_id.get(explicit_run_id)
            if ctx is None or ctx.seed != seed:
                missing.append(seed)
                continue
            selected[seed] = ctx
            continue

        candidate = None
        for ctx in contexts:
            if ctx.seed != seed:
                continue
            candidate = ctx
            break
        if candidate is None:
            missing.append(seed)
            continue
        selected[seed] = candidate

    return selected, missing


def _build_country_counts(site_timezones_root: Path) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    files = _list_parquet_files(site_timezones_root)
    for file_path in files:
        parquet_file = pq.ParquetFile(file_path)
        try:
            table = parquet_file.read(columns=["legal_country_iso", "tzid"])
            for row in table.to_pylist():
                country = _normalize_country(row.get("legal_country_iso"))
                tzid = str(row.get("tzid") or "").strip()
                if tzid:
                    counts[country][tzid] += 1
        finally:
            parquet_file.close()
    return counts


def _gate_failures(checks: dict[str, bool]) -> list[str]:
    return sorted([name for name, passed in checks.items() if not bool(passed)])


def _evaluate_seed(
    ctx: RunContext,
    tz_support_counts: dict[str, int],
    c_multi_min_sites: int,
    c_large_min_sites: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run_root = ctx.run_root
    seed = ctx.seed
    manifest = ctx.manifest_fingerprint

    s1 = _load_report_if_present(run_root, "S1", seed, manifest)
    s2 = _load_report_if_present(run_root, "S2", seed, manifest)
    s3 = _load_report_if_present(run_root, "S3", seed, manifest)
    s4 = _load_report_if_present(run_root, "S4", seed, manifest)
    s5 = _load_report_if_present(run_root, "S5", seed, manifest)

    if s1 is None:
        seed_payload = {
            "seed": seed,
            "run_id": ctx.run_id,
            "manifest_fingerprint": manifest,
            "cohorts": {
                "definition": {
                    "c_multi": {"tz_world_support_count_min": 2, "site_count_min": c_multi_min_sites},
                    "c_large": {"site_count_min": c_large_min_sites},
                },
                "counts": {"country_total": 0, "c_multi": 0, "c_large": 0},
            },
            "metrics": {
                "c_multi_share_distinct_ge2": None,
                "c_multi_median_top1_share": None,
                "c_multi_median_top1_top2_gap": None,
                "c_multi_median_entropy_norm": None,
                "c_large_share_top1_lt_095": None,
                "fallback_rate": None,
                "override_rate": None,
                "fallback_country_violations": None,
                "provenance_missing": None,
            },
            "checks": {"B": {"s1_report_present": False}, "BPLUS": {"s1_report_present": False}},
            "failing_gates": {"B": ["s1_report_present"], "BPLUS": ["s1_report_present"]},
            "verdict": "FAIL_REALISM",
        }
        return seed_payload, []

    s1_counts = s1.get("counts", {})
    s2_counts = (s2 or {}).get("counts", {})
    s1_checks = s1.get("checks", {})
    s2_checks = (s2 or {}).get("checks", {})

    site_timezones_root = (
        run_root
        / "data"
        / "layer1"
        / "2A"
        / "site_timezones"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest}"
    )
    metrics_available = bool(site_timezones_root.exists() and s2 is not None and s3 is not None and s4 is not None and s5 is not None)
    country_tz_counts: dict[str, Counter[str]] = {}
    if metrics_available:
        country_tz_counts = _build_country_counts(site_timezones_root)

    country_rows: list[dict[str, Any]] = []
    c_multi_rows: list[dict[str, Any]] = []
    c_large_rows: list[dict[str, Any]] = []
    for country in sorted(country_tz_counts.keys()):
        tz_counter = country_tz_counts[country]
        total = int(sum(tz_counter.values()))
        if total <= 0:
            continue
        ordered = sorted(tz_counter.values(), reverse=True)
        top1_share = _safe_rate(ordered[0], total)
        top2_share = _safe_rate(ordered[1], total) if len(ordered) > 1 else 0.0
        top1_top2_gap = top1_share - top2_share if len(ordered) > 1 else 1.0
        support_count = int(tz_support_counts.get(country, 0))
        entropy_norm = 0.0
        if support_count >= 2:
            h = 0.0
            for value in ordered:
                p = _safe_rate(value, total)
                if p > 0.0:
                    h -= p * math.log(p)
            entropy_norm = _safe_rate(h, math.log(float(support_count)))
        distinct_tzid_count = int(len(tz_counter))
        row = {
            "seed": seed,
            "run_id": ctx.run_id,
            "country_iso": country,
            "site_count": total,
            "tz_world_support_count": support_count,
            "distinct_tzid_count": distinct_tzid_count,
            "top1_share": round(top1_share, 8),
            "top1_top2_gap": round(top1_top2_gap, 8),
            "entropy_norm": round(entropy_norm, 8),
            "is_c_multi": bool(support_count >= 2 and total >= c_multi_min_sites),
            "is_c_large": bool(total >= c_large_min_sites),
        }
        country_rows.append(row)
        if row["is_c_multi"]:
            c_multi_rows.append(row)
        if row["is_c_large"]:
            c_large_rows.append(row)

    c_multi_country_count = len(c_multi_rows)
    c_large_country_count = len(c_large_rows)
    c_multi_share_distinct_ge2 = _safe_rate(
        sum(1 for row in c_multi_rows if int(row["distinct_tzid_count"]) >= 2),
        c_multi_country_count,
    )
    c_multi_median_top1_share = _median([float(row["top1_share"]) for row in c_multi_rows])
    c_multi_median_top1_top2_gap = _median([float(row["top1_top2_gap"]) for row in c_multi_rows])
    c_multi_median_entropy_norm = _median([float(row["entropy_norm"]) for row in c_multi_rows])
    c_large_share_top1_lt_095 = _safe_rate(
        sum(1 for row in c_large_rows if float(row["top1_share"]) < 0.95),
        c_large_country_count,
    )

    s1_gov = s1.get("governance", {})
    s2_gov = (s2 or {}).get("governance", {})
    fallback_rate = float(
        (s1_gov.get("rates") or {}).get(
            "fallback_rate",
            _safe_rate(
                float(s1_counts.get("fallback_nearest_within_threshold", 0))
                + float(s1_counts.get("fallback_nearest_outside_threshold", 0)),
                float(s1_counts.get("sites_total", 0)),
            ),
        )
    )
    if s2 is None:
        override_rate = 1.0
    else:
        override_rate = float(
            (s2_gov.get("rates") or {}).get(
                "override_rate",
                _safe_rate(
                    float(s2_counts.get("overridden_total", 0)),
                    float(s2_counts.get("sites_total", 0)),
                ),
            )
        )
    fallback_country_violations = list(s1_gov.get("fallback_country_violations") or [])
    provenance_missing = int(s2_counts.get("provenance_missing", 0))

    structural_checks = {
        "complete_2a_chain": bool(metrics_available),
        "s1_status_pass": str(s1.get("status", "")).lower() == "pass",
        "s2_status_pass": bool(s2 is not None and str(s2.get("status", "")).lower() == "pass"),
        "s3_status_pass": bool(s3 is not None and str(s3.get("status", "")).lower() == "pass"),
        "s4_status_pass": bool(s4 is not None and str(s4.get("status", "")).lower() == "pass"),
        "s5_status_pass": bool(s5 is not None and str(s5.get("status", "")).lower() == "pass"),
        "s1_pk_duplicates_zero": int(s1_checks.get("pk_duplicates", 1)) == 0,
        "s2_pk_duplicates_zero": int(s2_checks.get("pk_duplicates", 1)) == 0,
        "s1_row_parity": int(s1_counts.get("rows_emitted", -1)) == int(s1_counts.get("sites_total", -2)),
        "s2_row_parity": int(s2_counts.get("rows_emitted", -1)) == int(s2_counts.get("sites_total", -2)),
        "s1_s2_sites_total_match": int(s1_counts.get("sites_total", -1)) == int(s2_counts.get("sites_total", -2)),
        "s4_missing_tzids_zero": bool(
            s4 is not None and int((s4.get("coverage") or {}).get("missing_tzids_count", 1)) == 0
        ),
        "s5_digest_matches_flag": bool(s5 is not None and bool((s5.get("digest") or {}).get("matches_flag", False))),
        "s5_flag_format_exact": bool(s5 is not None and bool((s5.get("flag") or {}).get("format_exact", False))),
        "s5_index_root_scoped": bool(
            s5 is not None and bool((s5.get("bundle") or {}).get("index_path_root_scoped", False))
        ),
    }

    governance_b_checks = {
        "fallback_rate_b": fallback_rate <= B_THRESHOLDS["fallback_rate_max"],
        "override_rate_b": override_rate <= B_THRESHOLDS["override_rate_max"],
        "fallback_country_violations_empty": len(fallback_country_violations) == 0,
        "provenance_missing_zero": provenance_missing == 0,
    }
    governance_bplus_checks = {
        "fallback_rate_bplus": fallback_rate <= BPLUS_THRESHOLDS["fallback_rate_max"],
        "override_rate_bplus": override_rate <= BPLUS_THRESHOLDS["override_rate_max"],
        "fallback_country_violations_empty": len(fallback_country_violations) == 0,
        "provenance_missing_zero": provenance_missing == 0,
    }

    realism_b_checks = {
        "cohort_metrics_available": bool(metrics_available),
        "c_multi_nonempty": c_multi_country_count > 0,
        "c_large_nonempty": c_large_country_count > 0,
        "c_multi_share_distinct_ge2_b": c_multi_share_distinct_ge2 >= B_THRESHOLDS["c_multi_share_distinct_ge2_min"],
        "c_multi_median_top1_share_b": c_multi_median_top1_share <= B_THRESHOLDS["c_multi_median_top1_share_max"],
        "c_multi_median_top1_top2_gap_b": c_multi_median_top1_top2_gap
        <= B_THRESHOLDS["c_multi_median_top1_top2_gap_max"],
        "c_multi_median_entropy_norm_b": c_multi_median_entropy_norm
        >= B_THRESHOLDS["c_multi_median_entropy_norm_min"],
        "c_large_share_top1_lt_095_b": c_large_share_top1_lt_095 >= B_THRESHOLDS["c_large_share_top1_lt_095_min"],
    }
    realism_bplus_checks = {
        "cohort_metrics_available": bool(metrics_available),
        "c_multi_nonempty": c_multi_country_count > 0,
        "c_large_nonempty": c_large_country_count > 0,
        "c_multi_share_distinct_ge2_bplus": c_multi_share_distinct_ge2
        >= BPLUS_THRESHOLDS["c_multi_share_distinct_ge2_min"],
        "c_multi_median_top1_share_bplus": c_multi_median_top1_share
        <= BPLUS_THRESHOLDS["c_multi_median_top1_share_max"],
        "c_multi_median_top1_top2_gap_bplus": c_multi_median_top1_top2_gap
        <= BPLUS_THRESHOLDS["c_multi_median_top1_top2_gap_max"],
        "c_multi_median_entropy_norm_bplus": c_multi_median_entropy_norm
        >= BPLUS_THRESHOLDS["c_multi_median_entropy_norm_min"],
        "c_large_share_top1_lt_095_bplus": c_large_share_top1_lt_095
        >= BPLUS_THRESHOLDS["c_large_share_top1_lt_095_min"],
    }

    b_checks = {}
    b_checks.update(structural_checks)
    b_checks.update(governance_b_checks)
    b_checks.update(realism_b_checks)

    bplus_checks = {}
    bplus_checks.update(structural_checks)
    bplus_checks.update(governance_bplus_checks)
    bplus_checks.update(realism_bplus_checks)

    b_hard_pass = all(bool(v) for v in b_checks.values())
    bplus_hard_pass = all(bool(v) for v in bplus_checks.values())
    if bplus_hard_pass:
        verdict = "PASS_BPLUS"
    elif b_hard_pass:
        verdict = "PASS_B"
    else:
        verdict = "FAIL_REALISM"

    seed_payload = {
        "seed": seed,
        "run_id": ctx.run_id,
        "manifest_fingerprint": manifest,
        "cohorts": {
            "definition": {
                "c_multi": {"tz_world_support_count_min": 2, "site_count_min": c_multi_min_sites},
                "c_large": {"site_count_min": c_large_min_sites},
            },
            "counts": {
                "country_total": len(country_rows),
                "c_multi": c_multi_country_count,
                "c_large": c_large_country_count,
            },
        },
        "metrics": {
            "c_multi_share_distinct_ge2": round(c_multi_share_distinct_ge2, 8),
            "c_multi_median_top1_share": round(c_multi_median_top1_share, 8),
            "c_multi_median_top1_top2_gap": round(c_multi_median_top1_top2_gap, 8),
            "c_multi_median_entropy_norm": round(c_multi_median_entropy_norm, 8),
            "c_large_share_top1_lt_095": round(c_large_share_top1_lt_095, 8),
            "fallback_rate": round(fallback_rate, 8),
            "override_rate": round(override_rate, 8),
            "fallback_country_violations": len(fallback_country_violations),
            "provenance_missing": provenance_missing,
        },
        "checks": {
            "B": b_checks,
            "BPLUS": bplus_checks,
        },
        "failing_gates": {
            "B": _gate_failures(b_checks),
            "BPLUS": _gate_failures(bplus_checks),
        },
        "verdict": verdict,
    }
    return seed_payload, country_rows


def _parse_seed_list(raw: str) -> list[int]:
    result: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        result.append(int(token))
    return result


def _parse_seed_run_overrides(items: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in items:
        token = item.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"Invalid --seed-run format '{token}', expected seed:run_id")
        seed_raw, run_id = token.split(":", 1)
        out[int(seed_raw.strip())] = run_id.strip()
    return out


def _write_country_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "seed",
        "run_id",
        "country_iso",
        "site_count",
        "tz_world_support_count",
        "distinct_tzid_count",
        "top1_share",
        "top1_top2_gap",
        "entropy_norm",
        "is_c_multi",
        "is_c_large",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def score_p2(
    runs_root: Path,
    output_dir: Path,
    tz_world_path: Path,
    required_seeds: list[int],
    c_multi_min_sites: int,
    c_large_min_sites: int,
    explicit_seed_run_map: dict[int, str],
) -> dict[str, Any]:
    tz_support_counts = _load_tz_world_support_counts(tz_world_path)
    seed_run_map, missing_seeds = _select_seed_run_map(runs_root, required_seeds, explicit_seed_run_map)

    seed_payloads: list[dict[str, Any]] = []
    country_rows_all: list[dict[str, Any]] = []
    for seed in required_seeds:
        ctx = seed_run_map.get(seed)
        if ctx is None:
            continue
        seed_payload, country_rows = _evaluate_seed(
            ctx=ctx,
            tz_support_counts=tz_support_counts,
            c_multi_min_sites=c_multi_min_sites,
            c_large_min_sites=c_large_min_sites,
        )
        seed_payloads.append(seed_payload)
        country_rows_all.extend(country_rows)

    metric_series = {
        "c_multi_share_distinct_ge2": [float(p["metrics"]["c_multi_share_distinct_ge2"]) for p in seed_payloads],
        "c_multi_median_top1_share": [float(p["metrics"]["c_multi_median_top1_share"]) for p in seed_payloads],
        "c_multi_median_top1_top2_gap": [float(p["metrics"]["c_multi_median_top1_top2_gap"]) for p in seed_payloads],
        "c_multi_median_entropy_norm": [float(p["metrics"]["c_multi_median_entropy_norm"]) for p in seed_payloads],
    }
    stability = {name: _cv(values) for name, values in metric_series.items()}
    stability_b_pass = all(value <= B_THRESHOLDS["stability_cv_max"] for value in stability.values())
    stability_bplus_pass = all(value <= BPLUS_THRESHOLDS["stability_cv_max"] for value in stability.values())

    all_seed_b_pass = all(p["verdict"] in {"PASS_B", "PASS_BPLUS"} for p in seed_payloads)
    all_seed_bplus_pass = all(p["verdict"] == "PASS_BPLUS" for p in seed_payloads)
    full_seed_coverage = len(missing_seeds) == 0 and len(seed_payloads) == len(required_seeds)

    b_all = bool(full_seed_coverage and all_seed_b_pass and stability_b_pass)
    bplus_all = bool(full_seed_coverage and all_seed_bplus_pass and stability_bplus_pass)

    if bplus_all:
        status = "PASS_BPLUS"
    elif b_all:
        status = "PASS_B"
    else:
        status = "FAIL_REALISM"

    failing: list[str] = []
    if missing_seeds:
        failing.append("required_seed_coverage")
    if not stability_b_pass:
        failing.append("stability_cv_b")
    if not stability_bplus_pass and status != "PASS_BPLUS":
        failing.append("stability_cv_bplus")
    for payload in seed_payloads:
        if payload["verdict"] == "FAIL_REALISM":
            failing.append(f"seed_{payload['seed']}_hard_gates")

    runset_suffix = "_".join([f"{p['seed']}-{str(p['run_id'])[:8]}" for p in seed_payloads]) or "no_seeds"
    country_csv = output_dir / f"segment2a_p2_country_diagnostics_{runset_suffix}.csv"
    _write_country_csv(country_csv, country_rows_all)

    seeds_json = output_dir / f"segment2a_p2_seed_metrics_{runset_suffix}.json"
    seeds_payload = {
        "generated_utc": _now_utc(),
        "phase": "P2",
        "segment": "2A",
        "required_seeds": required_seeds,
        "selected_seed_run_map": {int(p["seed"]): str(p["run_id"]) for p in seed_payloads},
        "missing_seeds": missing_seeds,
        "seed_results": seed_payloads,
    }
    _write_json(seeds_json, seeds_payload)

    cert_payload = {
        "generated_utc": _now_utc(),
        "phase": "P2",
        "segment": "2A",
        "status": status,
        "required_seeds": required_seeds,
        "selected_seed_run_map": {int(p["seed"]): str(p["run_id"]) for p in seed_payloads},
        "missing_seeds": missing_seeds,
        "thresholds": {
            "B": B_THRESHOLDS,
            "BPLUS": BPLUS_THRESHOLDS,
        },
        "stability": {
            "cv_metrics": {name: round(value, 8) for name, value in stability.items()},
            "checks": {
                "B": stability_b_pass,
                "BPLUS": stability_bplus_pass,
            },
        },
        "seed_verdicts": {int(p["seed"]): str(p["verdict"]) for p in seed_payloads},
        "diagnostics": {
            "country_csv": str(country_csv),
            "seed_metrics_json": str(seeds_json),
        },
        "failing_gates": sorted(set(failing)),
        "cohort_contract": {
            "c_multi_site_count_min": c_multi_min_sites,
            "c_large_site_count_min": c_large_min_sites,
            "c_multi_support_min": 2,
            "entropy_norm_formula": "H / ln(tz_world_support_count)",
        },
    }
    cert_json = output_dir / f"segment2a_p2_certification_{runset_suffix}.json"
    _write_json(cert_json, cert_payload)
    return {
        "cert_json": cert_json,
        "seed_json": seeds_json,
        "country_csv": country_csv,
        "cert_payload": cert_payload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 2A P2 cohort-aware realism certification.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2A")
    parser.add_argument("--output-dir", default="runs/fix-data-engine/segment_2A/reports")
    parser.add_argument("--tz-world-path", default="reference/spatial/tz_world/2025a/tz_world.parquet")
    parser.add_argument("--required-seeds", default="42,7,101,202")
    parser.add_argument("--c-multi-min-sites", type=int, default=100)
    parser.add_argument("--c-large-min-sites", type=int, default=500)
    parser.add_argument(
        "--seed-run",
        action="append",
        default=[],
        help="Optional seed:run_id override (repeatable).",
    )
    args = parser.parse_args()

    required_seeds = _parse_seed_list(args.required_seeds)
    seed_run_overrides = _parse_seed_run_overrides(args.seed_run)
    result = score_p2(
        runs_root=Path(args.runs_root),
        output_dir=Path(args.output_dir),
        tz_world_path=Path(args.tz_world_path),
        required_seeds=required_seeds,
        c_multi_min_sites=int(args.c_multi_min_sites),
        c_large_min_sites=int(args.c_large_min_sites),
        explicit_seed_run_map=seed_run_overrides,
    )
    print(str(result["cert_json"]))


if __name__ == "__main__":
    main()
