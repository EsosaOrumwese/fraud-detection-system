"""
Score Segment 3B P1 witness gates without mutating P0 lock artifacts.

P1 scope:
- Core gates: V08, V09, V10
- Guardrails: virtual-rate drift, S10, V11
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import polars as pl


@dataclass(frozen=True)
class SeedMetrics:
    seed: int
    run_id: str
    manifest_fingerprint: str
    rule_id_non_null_rate: float
    rule_version_non_null_rate: float
    active_rule_id_count: int
    virtual_rate: float
    settlement_tzid_top1_share: float
    alias_max_abs_delta: float


def _parse_seed_runs(items: list[str]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for item in items:
        raw = str(item).strip()
        if ":" not in raw:
            raise ValueError(f"Invalid --seed-run '{raw}'. Expected format seed:run_id.")
        seed_s, run_id = raw.split(":", 1)
        seed = int(seed_s.strip())
        run_id = run_id.strip()
        if len(run_id) != 32:
            raise ValueError(f"Invalid run_id in --seed-run '{raw}'.")
        out[seed] = run_id
    return out


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_partition(root: Path, seed: int, manifest_fingerprint: str) -> Path:
    part = root / f"seed={seed}" / f"manifest_fingerprint={manifest_fingerprint}"
    if not part.exists():
        raise FileNotFoundError(f"Missing partition: {part}")
    return part


def _read_receipt(run_root: Path) -> dict:
    receipt_path = run_root / "run_receipt.json"
    if not receipt_path.exists():
        raise FileNotFoundError(f"Missing run_receipt.json at {receipt_path}")
    return _load_json(receipt_path)


def _read_s3_delta(run_root: Path, seed: int, manifest_fingerprint: str) -> float:
    report_path = (
        run_root
        / "reports"
        / "layer1"
        / "3B"
        / "state=S3"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "run_report.json"
    )
    payload = _load_json(report_path)
    return float(payload.get("decode", {}).get("max_abs_delta", 0.0))


def _seed_metrics(runs_root: Path, seed: int, run_id: str) -> SeedMetrics:
    run_root = runs_root / run_id
    receipt = _read_receipt(run_root)
    manifest = str(receipt["manifest_fingerprint"])

    vc_part = _resolve_partition(run_root / "data" / "layer1" / "3B" / "virtual_classification", seed, manifest)
    vs_part = _resolve_partition(run_root / "data" / "layer1" / "3B" / "virtual_settlement", seed, manifest)
    vc_df = pl.read_parquet(sorted(vc_part.glob("*.parquet")))
    vs_df = pl.read_parquet(sorted(vs_part.glob("*.parquet")))

    rows_total = int(vc_df.height)
    if rows_total <= 0:
        raise ValueError(f"virtual_classification_3B empty for seed={seed}, run_id={run_id}")

    rule_id_non_null = int(vc_df.select(pl.col("rule_id").is_not_null().sum()).item())
    rule_version_non_null = int(vc_df.select(pl.col("rule_version").is_not_null().sum()).item())
    active_rule_id_count = int(vc_df.select(pl.col("rule_id").drop_nulls().n_unique()).item())
    virtual_rows = int(vc_df.select(pl.col("is_virtual").cast(pl.Int64).sum()).item())
    virtual_rate = float(virtual_rows / rows_total)

    settlement_rows = int(vs_df.height)
    if settlement_rows > 0:
        top_count = int(vs_df.group_by("tzid_settlement").len().sort("len", descending=True).head(1)["len"][0])
        settlement_tzid_top1_share = float(top_count / settlement_rows)
    else:
        settlement_tzid_top1_share = 0.0

    alias_max_abs_delta = _read_s3_delta(run_root, seed, manifest)
    return SeedMetrics(
        seed=seed,
        run_id=run_id,
        manifest_fingerprint=manifest,
        rule_id_non_null_rate=float(rule_id_non_null / rows_total),
        rule_version_non_null_rate=float(rule_version_non_null / rows_total),
        active_rule_id_count=active_rule_id_count,
        virtual_rate=virtual_rate,
        settlement_tzid_top1_share=settlement_tzid_top1_share,
        alias_max_abs_delta=alias_max_abs_delta,
    )


def _verdict_for_seed(m: SeedMetrics, baseline_virtual_rate: float) -> dict:
    checks = {
        "3B-V08": m.rule_id_non_null_rate >= 0.99,
        "3B-V09": m.rule_version_non_null_rate >= 0.99,
        "3B-V10": m.active_rule_id_count >= 3,
        "P1-G01-virtual_rate_drift": abs(m.virtual_rate - baseline_virtual_rate) <= 0.0020,
        "P1-G02-3B-S10": m.settlement_tzid_top1_share <= 0.18,
        "P1-G03-3B-V11": m.alias_max_abs_delta <= 1e-6,
    }
    return {
        "checks": checks,
        "core_pass": checks["3B-V08"] and checks["3B-V09"] and checks["3B-V10"],
        "guardrails_pass": checks["P1-G01-virtual_rate_drift"] and checks["P1-G02-3B-S10"] and checks["P1-G03-3B-V11"],
        "seed_pass": all(checks.values()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    ap.add_argument("--witness-seeds", default="42,101")
    ap.add_argument("--seed-run", action="append", required=True, help="seed:run_id (repeatable)")
    ap.add_argument("--tag", default="", help="Artifact suffix tag; defaults to p1_<seed>_<seed> map.")
    args = ap.parse_args()

    runs_root = Path(args.runs_root)
    witness_seeds = [int(x.strip()) for x in str(args.witness_seeds).split(",") if x.strip()]
    seed_run_map = _parse_seed_runs(args.seed_run or [])

    for seed in witness_seeds:
        if seed not in seed_run_map:
            raise ValueError(f"Missing --seed-run mapping for witness seed {seed}")

    baseline_metrics: dict[int, dict] = {}
    for seed in witness_seeds:
        p = runs_root / "reports" / f"3B_validation_metrics_seed_{seed}.json"
        baseline_metrics[seed] = _load_json(p)

    metrics: dict[int, SeedMetrics] = {}
    seed_results: dict[int, dict] = {}
    manifests = set()
    for seed in witness_seeds:
        m = _seed_metrics(runs_root, seed, seed_run_map[seed])
        metrics[seed] = m
        manifests.add(m.manifest_fingerprint)
        baseline_virtual_rate = float(baseline_metrics[seed]["metrics"]["virtual_rate"])
        seed_results[seed] = _verdict_for_seed(m, baseline_virtual_rate)

    overall_core_pass = all(seed_results[s]["core_pass"] for s in witness_seeds)
    overall_guardrails_pass = all(seed_results[s]["guardrails_pass"] for s in witness_seeds)
    overall_pass = all(seed_results[s]["seed_pass"] for s in witness_seeds)
    decision = "UNLOCK_P2" if overall_pass else "HOLD_P1_REOPEN"

    tag = args.tag.strip()
    if not tag:
        tag = "p1_" + "_".join(str(s) for s in witness_seeds)

    out_dir = runs_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / f"segment3b_p1_witness_summary_{tag}.json"
    summary_md_path = out_dir / f"segment3b_p1_witness_summary_{tag}.md"

    payload = {
        "phase": "P1",
        "witness_seeds": witness_seeds,
        "seed_run_map": {str(k): v for k, v in seed_run_map.items()},
        "manifests_observed": sorted(manifests),
        "core_pass": overall_core_pass,
        "guardrails_pass": overall_guardrails_pass,
        "overall_pass": overall_pass,
        "decision": decision,
        "seeds": {
            str(seed): {
                "metrics": {
                    "rule_id_non_null_rate": metrics[seed].rule_id_non_null_rate,
                    "rule_version_non_null_rate": metrics[seed].rule_version_non_null_rate,
                    "active_rule_id_count": metrics[seed].active_rule_id_count,
                    "virtual_rate": metrics[seed].virtual_rate,
                    "settlement_tzid_top1_share": metrics[seed].settlement_tzid_top1_share,
                    "alias_max_abs_delta": metrics[seed].alias_max_abs_delta,
                },
                "baseline": {
                    "virtual_rate": float(baseline_metrics[seed]["metrics"]["virtual_rate"]),
                },
                "checks": seed_results[seed]["checks"],
                "core_pass": seed_results[seed]["core_pass"],
                "guardrails_pass": seed_results[seed]["guardrails_pass"],
                "seed_pass": seed_results[seed]["seed_pass"],
            }
            for seed in witness_seeds
        },
    }
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Segment 3B P1 Witness Summary",
        "",
        f"- decision: `{decision}`",
        f"- core_pass: `{overall_core_pass}`",
        f"- guardrails_pass: `{overall_guardrails_pass}`",
        f"- overall_pass: `{overall_pass}`",
        "",
        "| seed | run_id | V08 | V09 | V10 | G01(vrate) | G02(S10) | G03(V11) |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for seed in witness_seeds:
        checks = seed_results[seed]["checks"]
        lines.append(
            "| {seed} | {run_id} | {v08} | {v09} | {v10} | {g01} | {g02} | {g03} |".format(
                seed=seed,
                run_id=seed_run_map[seed],
                v08="PASS" if checks["3B-V08"] else "FAIL",
                v09="PASS" if checks["3B-V09"] else "FAIL",
                v10="PASS" if checks["3B-V10"] else "FAIL",
                g01="PASS" if checks["P1-G01-virtual_rate_drift"] else "FAIL",
                g02="PASS" if checks["P1-G02-3B-S10"] else "FAIL",
                g03="PASS" if checks["P1-G03-3B-V11"] else "FAIL",
            )
        )
    summary_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[segment3b-p1] summary_json={summary_path.as_posix()}")
    print(f"[segment3b-p1] summary_md={summary_md_path.as_posix()}")
    print(f"[segment3b-p1] decision={decision}")


if __name__ == "__main__":
    main()
