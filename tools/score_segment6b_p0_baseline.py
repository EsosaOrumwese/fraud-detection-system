#!/usr/bin/env python3
"""Emit Segment 6B remediation P0 baseline realism gateboard (T1..T22)."""

from __future__ import annotations

import argparse
import glob
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import duckdb
import yaml


DEFAULT_RUNS_ROOT = Path("runs/fix-data-engine/segment_6B")
DEFAULT_OUT_ROOT = Path("runs/fix-data-engine/segment_6B/reports")
DEFAULT_AUTHORITY_RUN_ID = "cee903d9ea644ba6a1824aa6b54a1692"

HARD_GATES = [
    "T1",
    "T2",
    "T3",
    "T4",
    "T5",
    "T6",
    "T7",
    "T8",
    "T9",
    "T10",
    "T11",
    "T12",
    "T13",
    "T14",
    "T15",
    "T16",
    "T21",
    "T22",
]
STRETCH_GATES = ["T17", "T18", "T19", "T20"]


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_root: Path
    seed: int
    manifest_fingerprint: str
    parameter_hash: str
    s1_arrival_scan: str
    s1_session_scan: str
    s2_flow_scan: str
    s2_event_scan: str
    s3_flow_scan: str
    s3_campaign_scan: str
    s4_truth_scan: str
    s4_bank_scan: str
    s4_case_scan: str
    s5_report_path: Path


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _to_posix(path_or_glob: str | Path) -> str:
    return str(path_or_glob).replace("\\", "/")


def _quote_sql(value: str) -> str:
    return value.replace("'", "''")


def _glob_has_files(pattern: str | Path) -> bool:
    return len(glob.glob(str(pattern), recursive=True)) > 0


def _scan_expr(pattern: str) -> str:
    return f"parquet_scan('{_quote_sql(pattern)}', hive_partitioning=true, union_by_name=true)"


def _scan_from_run(run_root: Path, rel_dataset: str) -> str:
    pattern = _to_posix(run_root / "data" / "layer3" / "6B" / rel_dataset / "**" / "*.parquet")
    if not _glob_has_files(pattern):
        raise FileNotFoundError(f"No parquet files found for dataset scan pattern: {pattern}")
    return _scan_expr(pattern)


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve_run_context(runs_root: Path, run_id: str) -> RunContext:
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root does not exist: {run_root}")
    receipt_path = run_root / "run_receipt.json"
    if not receipt_path.exists():
        raise FileNotFoundError(f"run_receipt.json missing: {receipt_path}")
    receipt = _load_json(receipt_path)
    seed = int(receipt.get("seed"))
    manifest = str(receipt.get("manifest_fingerprint"))
    parameter_hash = str(receipt.get("parameter_hash"))
    if not manifest or not parameter_hash:
        raise ValueError(f"run_receipt missing manifest_fingerprint/parameter_hash: {receipt_path}")

    s5_report_path = (
        run_root
        / "data/layer3/6B/validation"
        / f"manifest_fingerprint={manifest}"
        / "s5_validation_report_6B.json"
    )
    if not s5_report_path.exists():
        raise FileNotFoundError(f"S5 validation report missing: {s5_report_path}")

    return RunContext(
        run_id=run_id,
        run_root=run_root,
        seed=seed,
        manifest_fingerprint=manifest,
        parameter_hash=parameter_hash,
        s1_arrival_scan=_scan_from_run(run_root, "s1_arrival_entities_6B"),
        s1_session_scan=_scan_from_run(run_root, "s1_session_index_6B"),
        s2_flow_scan=_scan_from_run(run_root, "s2_flow_anchor_baseline_6B"),
        s2_event_scan=_scan_from_run(run_root, "s2_event_stream_baseline_6B"),
        s3_flow_scan=_scan_from_run(run_root, "s3_flow_anchor_with_fraud_6B"),
        s3_campaign_scan=_scan_from_run(run_root, "s3_campaign_catalogue_6B"),
        s4_truth_scan=_scan_from_run(run_root, "s4_flow_truth_labels_6B"),
        s4_bank_scan=_scan_from_run(run_root, "s4_flow_bank_view_6B"),
        s4_case_scan=_scan_from_run(run_root, "s4_case_timeline_6B"),
        s5_report_path=s5_report_path,
    )


def _safe_div(num: float, den: float) -> float:
    if abs(den) < 1e-12:
        return 0.0
    return float(num) / float(den)


def _format_pct(value: float) -> str:
    return f"{100.0 * float(value):.4f}%"


def _parse_ts_expr(col_name: str) -> str:
    return (
        f"COALESCE(try_strptime({col_name}, '%Y-%m-%dT%H:%M:%S.%fZ'), "
        f"try_strptime({col_name}, '%Y-%m-%dT%H:%M:%SZ'))"
    )


def _cohen_d(m1: float, s1: float, n1: int, m0: float, s0: float, n0: int) -> float:
    if n1 <= 1 or n0 <= 1:
        return 0.0
    pooled_num = (n1 - 1) * (s1**2) + (n0 - 1) * (s0**2)
    pooled_den = float(n1 + n0 - 2)
    if pooled_den <= 0:
        return 0.0
    pooled_std = math.sqrt(max(pooled_num / pooled_den, 0.0))
    if pooled_std <= 1e-12:
        return 0.0
    return abs(m1 - m0) / pooled_std


def _cramers_v(rows: list[tuple[str, str, int]]) -> float:
    if not rows:
        return 0.0
    row_totals: Counter[str] = Counter()
    col_totals: Counter[str] = Counter()
    matrix: dict[tuple[str, str], int] = {}
    total = 0
    for row_key, col_key, n in rows:
        n_int = int(n)
        if n_int <= 0:
            continue
        matrix[(row_key, col_key)] = matrix.get((row_key, col_key), 0) + n_int
        row_totals[row_key] += n_int
        col_totals[col_key] += n_int
        total += n_int
    if total <= 0:
        return 0.0
    r = len(row_totals)
    c = len(col_totals)
    if r <= 1 or c <= 1:
        return 0.0
    chi2 = 0.0
    for rk, rt in row_totals.items():
        for ck, ct in col_totals.items():
            obs = float(matrix.get((rk, ck), 0))
            exp = float(rt * ct) / float(total)
            if exp > 0:
                chi2 += ((obs - exp) ** 2) / exp
    denom = float(total) * float(min(r - 1, c - 1))
    if denom <= 0:
        return 0.0
    return math.sqrt(max(chi2 / denom, 0.0))


def _gate_payload(
    title: str,
    gate_class: str,
    b_target: str,
    bplus_target: str,
    value: Any,
    value_fmt: str,
    b_pass: bool,
    bplus_pass: bool,
    source: str,
    owners: list[str],
    insufficient: bool = False,
    note: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "title": title,
        "class": gate_class,
        "b_target": b_target,
        "bplus_target": bplus_target,
        "value": value,
        "value_fmt": value_fmt,
        "b_pass": bool(b_pass),
        "bplus_pass": bool(bplus_pass),
        "owners": owners,
        "source": source,
    }
    if insufficient:
        out["insufficient_evidence"] = True
    if note:
        out["note"] = note
    if details:
        out.update(details)
    return out


def _load_truth_policy_collision_risk(policy_path: Path, t3_legit_rate: float) -> dict[str, Any]:
    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    entries = list(payload.get("direct_pattern_map") or [])
    by_pattern: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        match = row.get("match") or {}
        pattern = str(match.get("fraud_pattern_type", "UNKNOWN"))
        by_pattern[pattern].append(row)
    collision_keys = {k: v for k, v in by_pattern.items() if len(v) > 1}
    raw_collision_key_count = len(collision_keys)
    observed_collapse = t3_legit_rate < 0.99
    effective_collision_count = raw_collision_key_count if observed_collapse else 0
    return {
        "raw_collision_key_count": raw_collision_key_count,
        "effective_collision_count": effective_collision_count,
        "collision_keys": sorted(collision_keys.keys()),
        "observed_collapse": observed_collapse,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    run = payload["run"]
    summary = payload["summary"]
    gates = payload["gates"]
    lines: list[str] = [
        "# Segment 6B P0 Baseline Gateboard",
        "",
        f"- generated_utc: `{payload['generated_utc']}`",
        f"- run_id: `{run['run_id']}`",
        f"- seed: `{run['seed']}`",
        f"- overall_verdict: `{summary['overall_verdict']}`",
        f"- phase_decision: `{summary['phase_decision']}`",
        "",
        "## Hard Failures",
    ]
    hard_failures = summary.get("hard_failures") or []
    if hard_failures:
        for gid in hard_failures:
            g = gates[gid]
            lines.append(f"- `{gid}` {g['title']}: `{g['value_fmt']}` (owners: `{','.join(g['owners'])}`)")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Stretch Failures",
        ]
    )
    stretch_failures = summary.get("stretch_failures") or []
    if stretch_failures:
        for gid in stretch_failures:
            g = gates[gid]
            lines.append(f"- `{gid}` {g['title']}: `{g['value_fmt']}` (owners: `{','.join(g['owners'])}`)")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Owner Map (Failing/Insufficient)",
        ]
    )
    owner_map = summary.get("owner_failure_map") or {}
    if owner_map:
        for owner in sorted(owner_map.keys()):
            lines.append(f"- `{owner}`: `{', '.join(owner_map[owner])}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Wave Routing",
            f"- `P1`: `{', '.join(summary['wave_routing']['P1']) or 'none'}`",
            f"- `P2`: `{', '.join(summary['wave_routing']['P2']) or 'none'}`",
            f"- `P3`: `{', '.join(summary['wave_routing']['P3']) or 'none'}`",
            f"- `P4`: `{', '.join(summary['wave_routing']['P4']) or 'none'}`",
            "",
        ]
    )
    return "\n".join(lines)

def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 6B remediation P0 baseline gateboard.")
    parser.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    parser.add_argument("--run-id", default=DEFAULT_AUTHORITY_RUN_ID)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument(
        "--merchant-class-glob",
        default="",
        help="Optional parquet glob for merchant class profile (primary_demand_class).",
    )
    parser.add_argument(
        "--arrival-events-glob",
        default="",
        help="Optional parquet glob for 5B arrival events with tzid_primary (for T18).",
    )
    parser.add_argument("--case-sample-mod", type=int, default=20)
    parser.add_argument("--latency-sample-mod", type=int, default=100)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = str(args.run_id).strip() or _resolve_latest_run_id(runs_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    ctx = _resolve_run_context(runs_root, run_id)

    merchant_class_glob = args.merchant_class_glob.strip()
    merchant_class_available = False
    if merchant_class_glob:
        merchant_class_available = _glob_has_files(merchant_class_glob)
        merchant_class_glob = _to_posix(merchant_class_glob)
    else:
        auto_mc = _to_posix(ctx.run_root / "data/layer2/5A/merchant_class_profile/**/*.parquet")
        if _glob_has_files(auto_mc):
            merchant_class_glob = auto_mc
            merchant_class_available = True

    arrival_events_glob = args.arrival_events_glob.strip()
    arrival_events_available = bool(arrival_events_glob) and _glob_has_files(arrival_events_glob)
    if arrival_events_available:
        arrival_events_glob = _to_posix(arrival_events_glob)

    con = duckdb.connect()
    con.execute(f"PRAGMA threads={int(args.threads)};")
    con.execute("PRAGMA enable_progress_bar=false;")

    gates: dict[str, dict[str, Any]] = {}

    t1_t2 = con.execute(
        f"""
        SELECT
          AVG(CASE WHEN (NOT is_fraud_truth) OR UPPER(COALESCE(fraud_label, ''))='LEGIT' THEN 1.0 ELSE 0.0 END) AS legit_share,
          AVG(CASE WHEN is_fraud_truth THEN 1.0 ELSE 0.0 END) AS truth_mean,
          COUNT(*) AS flow_count
        FROM {ctx.s4_truth_scan}
        """
    ).fetchone()
    legit_share = float(t1_t2[0] or 0.0)
    truth_mean = float(t1_t2[1] or 0.0)
    flow_count = int(t1_t2[2] or 0)

    gates["T1"] = _gate_payload(
        title="LEGIT share > 0",
        gate_class="hard",
        b_target="> 0",
        bplus_target="> 0",
        value=legit_share,
        value_fmt=_format_pct(legit_share),
        b_pass=legit_share > 0.0,
        bplus_pass=legit_share > 0.0,
        source="s4_flow_truth_labels_6B full scan",
        owners=["S4"],
    )
    gates["T2"] = _gate_payload(
        title="is_fraud_truth mean in [0.02, 0.30]",
        gate_class="hard",
        b_target="[0.02, 0.30]",
        bplus_target="[0.02, 0.30]",
        value=truth_mean,
        value_fmt=f"{truth_mean:.6f}",
        b_pass=(0.02 <= truth_mean <= 0.30),
        bplus_pass=(0.02 <= truth_mean <= 0.30),
        source="s4_flow_truth_labels_6B full scan",
        owners=["S4"],
    )

    t3_t4 = con.execute(
        f"""
        WITH j AS (
          SELECT
            s3.campaign_id,
            s4.fraud_label,
            s4.is_fraud_truth
          FROM {ctx.s3_flow_scan} s3
          JOIN {ctx.s4_truth_scan} s4 USING(flow_id)
        )
        SELECT
          SUM(CASE WHEN campaign_id IS NULL THEN 1 ELSE 0 END) AS no_campaign_total,
          SUM(CASE WHEN campaign_id IS NULL AND (UPPER(COALESCE(fraud_label,''))='LEGIT' OR NOT is_fraud_truth) THEN 1 ELSE 0 END) AS no_campaign_legit,
          SUM(CASE WHEN campaign_id IS NOT NULL THEN 1 ELSE 0 END) AS campaign_total,
          SUM(CASE WHEN campaign_id IS NOT NULL AND UPPER(COALESCE(fraud_label,''))!='LEGIT' THEN 1 ELSE 0 END) AS campaign_non_legit
        FROM j
        """
    ).fetchone()
    no_campaign_total = int(t3_t4[0] or 0)
    no_campaign_legit = int(t3_t4[1] or 0)
    campaign_total = int(t3_t4[2] or 0)
    campaign_non_legit = int(t3_t4[3] or 0)
    t3_rate = _safe_div(float(no_campaign_legit), float(no_campaign_total))
    t4_rate = _safe_div(float(campaign_non_legit), float(campaign_total))

    gates["T3"] = _gate_payload(
        title="% non-overlay NONE rows mapped LEGIT",
        gate_class="hard",
        b_target=">= 99.0%",
        bplus_target=">= 99.5%",
        value=t3_rate,
        value_fmt=_format_pct(t3_rate),
        b_pass=t3_rate >= 0.99,
        bplus_pass=t3_rate >= 0.995,
        source="s3_flow_anchor_with_fraud_6B + s4_flow_truth_labels_6B full scan",
        owners=["S4"],
        details={"no_campaign_total": no_campaign_total},
    )
    gates["T4"] = _gate_payload(
        title="% campaign-tagged rows mapped non-LEGIT",
        gate_class="hard",
        b_target=">= 99.0%",
        bplus_target=">= 99.5%",
        value=t4_rate,
        value_fmt=_format_pct(t4_rate),
        b_pass=t4_rate >= 0.99,
        bplus_pass=t4_rate >= 0.995,
        source="s3_flow_anchor_with_fraud_6B + s4_flow_truth_labels_6B full scan",
        owners=["S4"],
        details={"campaign_total": campaign_total},
    )

    t6_stats = con.execute(
        f"""
        WITH j AS (
          SELECT s3.amount, b.is_fraud_bank_view
          FROM {ctx.s3_flow_scan} s3
          JOIN {ctx.s4_bank_scan} b USING(flow_id)
        )
        SELECT
          AVG(CASE WHEN is_fraud_bank_view THEN amount END) AS m1,
          STDDEV_SAMP(CASE WHEN is_fraud_bank_view THEN amount END) AS s1,
          SUM(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END) AS n1,
          AVG(CASE WHEN NOT is_fraud_bank_view THEN amount END) AS m0,
          STDDEV_SAMP(CASE WHEN NOT is_fraud_bank_view THEN amount END) AS s0,
          SUM(CASE WHEN NOT is_fraud_bank_view THEN 1 ELSE 0 END) AS n0
        FROM j
        """
    ).fetchone()
    m1, s1, n1, m0, s0, n0 = (
        float(t6_stats[0] or 0.0),
        float(t6_stats[1] or 0.0),
        int(t6_stats[2] or 0),
        float(t6_stats[3] or 0.0),
        float(t6_stats[4] or 0.0),
        int(t6_stats[5] or 0),
    )
    t6_d = _cohen_d(m1=m1, s1=s1, n1=n1, m0=m0, s0=s0, n0=n0)
    gates["T6"] = _gate_payload(
        title="amount-vs-bank-view effect-size floor",
        gate_class="hard",
        b_target=">= 0.05",
        bplus_target=">= 0.08",
        value=t6_d,
        value_fmt=f"{t6_d:.6f}",
        b_pass=t6_d >= 0.05,
        bplus_pass=t6_d >= 0.08,
        source="s3_flow_anchor_with_fraud_6B + s4_flow_bank_view_6B full scan",
        owners=["S4"],
        details={"bank_true_n": n1, "bank_false_n": n0},
    )

    if merchant_class_available:
        mc_scan = _scan_expr(merchant_class_glob)
        t5_rows = con.execute(
            f"""
            WITH j AS (
              SELECT
                COALESCE(mc.primary_demand_class, '__UNK__') AS merchant_class,
                COALESCE(b.bank_label, '__UNK__') AS bank_outcome
              FROM {ctx.s3_flow_scan} s3
              JOIN {ctx.s4_bank_scan} b USING(flow_id)
              LEFT JOIN {mc_scan} mc USING(merchant_id)
            )
            SELECT merchant_class, bank_outcome, COUNT(*) AS n
            FROM j
            GROUP BY 1,2
            """
        ).fetchall()
        t5_v = _cramers_v([(str(r[0]), str(r[1]), int(r[2])) for r in t5_rows])

        t7_rows = con.execute(
            f"""
            WITH j AS (
              SELECT
                COALESCE(mc.primary_demand_class, '__UNK__') AS merchant_class,
                b.is_fraud_bank_view
              FROM {ctx.s3_flow_scan} s3
              JOIN {ctx.s4_bank_scan} b USING(flow_id)
              LEFT JOIN {mc_scan} mc USING(merchant_id)
            )
            SELECT
              merchant_class,
              AVG(CASE WHEN is_fraud_bank_view THEN 1.0 ELSE 0.0 END) AS bank_rate
            FROM j
            GROUP BY 1
            """
        ).fetchall()
        bank_rates = [float(r[1]) for r in t7_rows if r[1] is not None]
        t7_spread = (max(bank_rates) - min(bank_rates)) if bank_rates else 0.0

        gates["T5"] = _gate_payload(
            title="Cramer's V(bank_view_outcome, merchant_class)",
            gate_class="hard",
            b_target=">= 0.05",
            bplus_target=">= 0.08",
            value=t5_v,
            value_fmt=f"{t5_v:.6f}",
            b_pass=t5_v >= 0.05,
            bplus_pass=t5_v >= 0.08,
            source="s3_flow + s4_flow_bank_view + merchant_class_profile",
            owners=["S4"],
        )
        gates["T7"] = _gate_payload(
            title="class-conditioned bank-fraud spread",
            gate_class="hard",
            b_target=">= 0.03",
            bplus_target=">= 0.05",
            value=t7_spread,
            value_fmt=f"{t7_spread:.6f}",
            b_pass=t7_spread >= 0.03,
            bplus_pass=t7_spread >= 0.05,
            source="s3_flow + s4_flow_bank_view + merchant_class_profile",
            owners=["S4"],
            details={"class_count": len(bank_rates)},
        )
    else:
        note = "merchant_class_profile source unavailable in staged run lane; provide --merchant-class-glob for strict evaluation."
        gates["T5"] = _gate_payload(
            title="Cramer's V(bank_view_outcome, merchant_class)",
            gate_class="hard",
            b_target=">= 0.05",
            bplus_target=">= 0.08",
            value=None,
            value_fmt="insufficient_evidence",
            b_pass=False,
            bplus_pass=False,
            source="merchant_class_profile missing",
            owners=["S4", "S0"],
            insufficient=True,
            note=note,
        )
        gates["T7"] = _gate_payload(
            title="class-conditioned bank-fraud spread",
            gate_class="hard",
            b_target=">= 0.03",
            bplus_target=">= 0.05",
            value=None,
            value_fmt="insufficient_evidence",
            b_pass=False,
            bplus_pass=False,
            source="merchant_class_profile missing",
            owners=["S4", "S0"],
            insufficient=True,
            note=note,
        )

    case_sample_mod = max(1, int(args.case_sample_mod))
    t8_t10 = con.execute(
        f"""
        WITH ct AS (
          SELECT
            case_id,
            case_event_seq,
            {_parse_ts_expr('ts_utc')} AS ts
          FROM {ctx.s4_case_scan}
          WHERE MOD(ABS(HASH(case_id)), {case_sample_mod}) = 0
        ),
        g AS (
          SELECT
            case_id,
            DATE_DIFF('second', LAG(ts) OVER (PARTITION BY case_id ORDER BY case_event_seq), ts) AS gap_sec
          FROM ct
        )
        SELECT
          (SELECT COUNT(DISTINCT case_id) FROM ct) AS cases_sampled,
          SUM(CASE WHEN gap_sec IS NOT NULL THEN 1 ELSE 0 END) AS gaps_total,
          SUM(CASE WHEN gap_sec < 0 THEN 1 ELSE 0 END) AS neg_gaps,
          SUM(CASE WHEN gap_sec IN (3600, 86400, 86401) THEN 1 ELSE 0 END) AS fixed_spike_gaps,
          COUNT(DISTINCT CASE WHEN gap_sec IS NOT NULL THEN case_id END) AS cases_with_gaps,
          COUNT(DISTINCT CASE WHEN gap_sec < 0 THEN case_id END) AS cases_with_neg_gaps,
          COUNT(DISTINCT gap_sec) AS distinct_gap_values
        FROM g
        """
    ).fetchone()
    cases_sampled = int(t8_t10[0] or 0)
    gaps_total = int(t8_t10[1] or 0)
    neg_gaps = int(t8_t10[2] or 0)
    fixed_spike_gaps = int(t8_t10[3] or 0)
    cases_with_gaps = int(t8_t10[4] or 0)
    cases_with_neg = int(t8_t10[5] or 0)
    distinct_gap_values = int(t8_t10[6] or 0)
    neg_gap_rate = _safe_div(float(neg_gaps), float(gaps_total))
    fixed_spike_share = _safe_div(float(fixed_spike_gaps), float(gaps_total))
    nonmono_case_rate = _safe_div(float(cases_with_neg), float(cases_with_gaps))
    case_insufficient = gaps_total == 0

    gates["T8"] = _gate_payload(
        title="negative case-gap rate",
        gate_class="hard",
        b_target="= 0",
        bplus_target="= 0",
        value=neg_gap_rate,
        value_fmt=_format_pct(neg_gap_rate),
        b_pass=(not case_insufficient) and neg_gap_rate == 0.0,
        bplus_pass=(not case_insufficient) and neg_gap_rate == 0.0,
        source="s4_case_timeline sampled gap lane",
        owners=["S4"],
        insufficient=case_insufficient,
        details={"sample_mod": case_sample_mod, "cases_sampled": cases_sampled, "gaps_total": gaps_total},
    )
    gates["T9"] = _gate_payload(
        title="fixed-spike share (3600s + 86400/86401s)",
        gate_class="hard",
        b_target="<= 0.50",
        bplus_target="<= 0.25",
        value=fixed_spike_share,
        value_fmt=_format_pct(fixed_spike_share),
        b_pass=(not case_insufficient) and fixed_spike_share <= 0.50,
        bplus_pass=(not case_insufficient) and fixed_spike_share <= 0.25,
        source="s4_case_timeline sampled gap lane",
        owners=["S4"],
        insufficient=case_insufficient,
        details={"sample_mod": case_sample_mod, "distinct_gap_values": distinct_gap_values},
    )
    gates["T10"] = _gate_payload(
        title="non-monotonic case-event time rate",
        gate_class="hard",
        b_target="= 0",
        bplus_target="= 0",
        value=nonmono_case_rate,
        value_fmt=_format_pct(nonmono_case_rate),
        b_pass=(not case_insufficient) and nonmono_case_rate == 0.0,
        bplus_pass=(not case_insufficient) and nonmono_case_rate == 0.0,
        source="s4_case_timeline sampled case-level monotonicity lane",
        owners=["S4"],
        insufficient=case_insufficient,
        details={"sample_mod": case_sample_mod, "cases_with_gaps": cases_with_gaps},
    )

    t11_t13 = con.execute(
        f"""
        WITH f AS (
          SELECT amount FROM {ctx.s2_flow_scan}
        ),
        freq AS (
          SELECT amount, COUNT(*) AS n
          FROM f
          GROUP BY 1
        ),
        ranked AS (
          SELECT amount, n, ROW_NUMBER() OVER (ORDER BY n DESC, amount DESC) AS rn
          FROM freq
        )
        SELECT
          (SELECT COUNT(*) FROM f) AS flow_total,
          (SELECT COUNT(DISTINCT amount) FROM f) AS distinct_amount_values,
          (SELECT QUANTILE_CONT(amount, 0.50) FROM f) AS amount_p50,
          (SELECT QUANTILE_CONT(amount, 0.99) FROM f) AS amount_p99,
          (SELECT SUM(CASE WHEN rn <= 8 THEN n ELSE 0 END) FROM ranked) AS top8_n
        """
    ).fetchone()
    s2_total = int(t11_t13[0] or 0)
    distinct_amount_values = int(t11_t13[1] or 0)
    amount_p50 = float(t11_t13[2] or 0.0)
    amount_p99 = float(t11_t13[3] or 0.0)
    top8_n = int(t11_t13[4] or 0)
    p99_p50 = _safe_div(amount_p99, amount_p50)
    top8_share = _safe_div(float(top8_n), float(s2_total))

    gates["T11"] = _gate_payload(
        title="distinct amount values",
        gate_class="hard",
        b_target=">= 20",
        bplus_target=">= 40",
        value=distinct_amount_values,
        value_fmt=str(distinct_amount_values),
        b_pass=distinct_amount_values >= 20,
        bplus_pass=distinct_amount_values >= 40,
        source="s2_flow_anchor_baseline_6B full scan",
        owners=["S2"],
    )
    gates["T12"] = _gate_payload(
        title="amount p99/p50 ratio",
        gate_class="hard",
        b_target=">= 2.5",
        bplus_target=">= 3.0",
        value=p99_p50,
        value_fmt=f"{p99_p50:.6f}",
        b_pass=p99_p50 >= 2.5,
        bplus_pass=p99_p50 >= 3.0,
        source="s2_flow_anchor_baseline_6B full scan",
        owners=["S2"],
    )
    gates["T13"] = _gate_payload(
        title="top-8 amount share",
        gate_class="hard",
        b_target="<= 0.85",
        bplus_target="<= 0.70",
        value=top8_share,
        value_fmt=_format_pct(top8_share),
        b_pass=top8_share <= 0.85,
        bplus_pass=top8_share <= 0.70,
        source="s2_flow_anchor_baseline_6B full scan",
        owners=["S2"],
        details={"flow_total": s2_total},
    )

    latency_sample_mod = max(1, int(args.latency_sample_mod))
    t14_t16 = con.execute(
        f"""
        WITH e AS (
          SELECT
            flow_id,
            event_seq,
            {_parse_ts_expr('ts_utc')} AS ts
          FROM {ctx.s2_event_scan}
          WHERE event_seq IN (0, 1)
            AND MOD(ABS(HASH(flow_id)), {latency_sample_mod}) = 0
        ),
        p AS (
          SELECT
            flow_id,
            MAX(CASE WHEN event_seq = 0 THEN ts END) AS t0,
            MAX(CASE WHEN event_seq = 1 THEN ts END) AS t1
          FROM e
          GROUP BY 1
        ),
        l AS (
          SELECT DATE_DIFF('millisecond', t0, t1) / 1000.0 AS latency_s
          FROM p
          WHERE t0 IS NOT NULL AND t1 IS NOT NULL
        )
        SELECT
          COUNT(*) AS sample_flows,
          QUANTILE_CONT(latency_s, 0.50) AS latency_p50,
          QUANTILE_CONT(latency_s, 0.99) AS latency_p99,
          AVG(CASE WHEN latency_s = 0 THEN 1.0 ELSE 0.0 END) AS zero_share,
          COUNT(DISTINCT latency_s) AS distinct_latency_values
        FROM l
        """
    ).fetchone()
    latency_n = int(t14_t16[0] or 0)
    latency_p50 = float(t14_t16[1] or 0.0)
    latency_p99 = float(t14_t16[2] or 0.0)
    zero_share = float(t14_t16[3] or 0.0)
    distinct_latency_values = int(t14_t16[4] or 0)
    latency_insufficient = latency_n == 0

    gates["T14"] = _gate_payload(
        title="auth latency median",
        gate_class="hard",
        b_target="[0.3s, 8s]",
        bplus_target="[0.5s, 5s]",
        value=latency_p50,
        value_fmt=f"{latency_p50:.6f}s",
        b_pass=(not latency_insufficient) and (0.3 <= latency_p50 <= 8.0),
        bplus_pass=(not latency_insufficient) and (0.5 <= latency_p50 <= 5.0),
        source="s2_event_stream_baseline_6B sampled auth latency lane",
        owners=["S2"],
        insufficient=latency_insufficient,
        details={"sample_mod": latency_sample_mod, "sample_flows": latency_n},
    )
    gates["T15"] = _gate_payload(
        title="auth latency p99",
        gate_class="hard",
        b_target="> 30s",
        bplus_target="> 45s",
        value=latency_p99,
        value_fmt=f"{latency_p99:.6f}s",
        b_pass=(not latency_insufficient) and (latency_p99 > 30.0),
        bplus_pass=(not latency_insufficient) and (latency_p99 > 45.0),
        source="s2_event_stream_baseline_6B sampled auth latency lane",
        owners=["S2"],
        insufficient=latency_insufficient,
        details={"distinct_latency_values": distinct_latency_values},
    )
    gates["T16"] = _gate_payload(
        title="exact-zero auth latency share",
        gate_class="hard",
        b_target="<= 0.20",
        bplus_target="<= 0.05",
        value=zero_share,
        value_fmt=_format_pct(zero_share),
        b_pass=(not latency_insufficient) and (zero_share <= 0.20),
        bplus_pass=(not latency_insufficient) and (zero_share <= 0.05),
        source="s2_event_stream_baseline_6B sampled auth latency lane",
        owners=["S2"],
        insufficient=latency_insufficient,
    )

    t17_core = con.execute(
        f"""
        SELECT
          COUNT(*) AS campaign_flow_count,
          COUNT(DISTINCT campaign_id) AS campaign_count
        FROM {ctx.s3_flow_scan}
        WHERE campaign_id IS NOT NULL
        """
    ).fetchone()
    campaign_flow_count = int(t17_core[0] or 0)
    campaign_count = int(t17_core[1] or 0)

    t17_class_v = 0.0
    t17_median_merchants = 0.0
    t17_insufficient = (campaign_flow_count == 0) or (campaign_count == 0)
    if (not t17_insufficient) and merchant_class_available:
        mc_scan = _scan_expr(merchant_class_glob)
        t17_rows = con.execute(
            f"""
            WITH cf AS (
              SELECT campaign_id, merchant_id
              FROM {ctx.s3_flow_scan}
              WHERE campaign_id IS NOT NULL
            )
            SELECT
              cf.campaign_id,
              COALESCE(mc.primary_demand_class, '__UNK__') AS merchant_class,
              COUNT(*) AS n
            FROM cf
            LEFT JOIN {mc_scan} mc USING(merchant_id)
            GROUP BY 1,2
            """
        ).fetchall()
        t17_class_v = _cramers_v([(str(r[0]), str(r[1]), int(r[2])) for r in t17_rows])
        t17_merchants = con.execute(
            f"""
            SELECT MEDIAN(merchant_cnt)
            FROM (
              SELECT campaign_id, COUNT(DISTINCT merchant_id) AS merchant_cnt
              FROM {ctx.s3_flow_scan}
              WHERE campaign_id IS NOT NULL
              GROUP BY 1
            )
            """
        ).fetchone()
        t17_median_merchants = float(t17_merchants[0] or 0.0)
    elif not merchant_class_available:
        t17_insufficient = True

    gates["T17"] = _gate_payload(
        title="campaign depth with class targeting differentiation",
        gate_class="stretch",
        b_target="campaign_count>=4 and class_v>=0.03",
        bplus_target="campaign_count>=6 and class_v>=0.05",
        value={
            "campaign_count": campaign_count,
            "class_v": t17_class_v,
            "median_merchants_per_campaign": t17_median_merchants,
        },
        value_fmt=f"campaigns={campaign_count}, class_v={t17_class_v:.6f}, median_merchants={t17_median_merchants:.2f}",
        b_pass=(not t17_insufficient) and (campaign_count >= 4) and (t17_class_v >= 0.03),
        bplus_pass=(not t17_insufficient) and (campaign_count >= 6) and (t17_class_v >= 0.05),
        source="s3_flow_anchor_with_fraud_6B (+ merchant_class_profile)",
        owners=["S3"],
        insufficient=t17_insufficient,
        note=None if merchant_class_available else "merchant_class_profile unavailable for campaign-depth class differentiation.",
    )

    if arrival_events_available and campaign_flow_count > 0:
        ae_scan = _scan_expr(arrival_events_glob)
        t18_rows = con.execute(
            f"""
            WITH cf AS (
              SELECT scenario_id, merchant_id, arrival_seq, campaign_id
              FROM {ctx.s3_flow_scan}
              WHERE campaign_id IS NOT NULL
            ),
            cg AS (
              SELECT
                cf.campaign_id,
                COALESCE(ae.tzid_primary, '__UNK__') AS tzid_primary,
                COUNT(*) AS n
              FROM cf
              JOIN {ae_scan} ae
                ON cf.scenario_id = ae.scenario_id
               AND cf.merchant_id = ae.merchant_id
               AND cf.arrival_seq = ae.arrival_seq
              GROUP BY 1,2
            )
            SELECT campaign_id, tzid_primary, n
            FROM cg
            """
        ).fetchall()
        t18_v = _cramers_v([(str(r[0]), str(r[1]), int(r[2])) for r in t18_rows])
        t18_med_tz = con.execute(
            f"""
            WITH cf AS (
              SELECT scenario_id, merchant_id, arrival_seq, campaign_id
              FROM {ctx.s3_flow_scan}
              WHERE campaign_id IS NOT NULL
            )
            SELECT MEDIAN(tz_cnt)
            FROM (
              SELECT
                cf.campaign_id,
                COUNT(DISTINCT ae.tzid_primary) AS tz_cnt
              FROM cf
              JOIN {ae_scan} ae
                ON cf.scenario_id = ae.scenario_id
               AND cf.merchant_id = ae.merchant_id
               AND cf.arrival_seq = ae.arrival_seq
              GROUP BY 1
            )
            """
        ).fetchone()
        med_tz = float(t18_med_tz[0] or 0.0)
        gates["T18"] = _gate_payload(
            title="campaign geo depth with differentiated corridor profile",
            gate_class="stretch",
            b_target="tz_corridor_v>=0.03 and median_tz_per_campaign>=2",
            bplus_target="tz_corridor_v>=0.05 and median_tz_per_campaign>=3",
            value={"tz_corridor_v": t18_v, "median_tz_per_campaign": med_tz},
            value_fmt=f"tz_corridor_v={t18_v:.6f}, median_tz={med_tz:.2f}",
            b_pass=(t18_v >= 0.03) and (med_tz >= 2.0),
            bplus_pass=(t18_v >= 0.05) and (med_tz >= 3.0),
            source="s3_flow campaign join to arrival_events tzid_primary",
            owners=["S3", "S1"],
        )
    else:
        gates["T18"] = _gate_payload(
            title="campaign geo depth with differentiated corridor profile",
            gate_class="stretch",
            b_target="tz_corridor_v>=0.03 and median_tz_per_campaign>=2",
            bplus_target="tz_corridor_v>=0.05 and median_tz_per_campaign>=3",
            value=None,
            value_fmt="insufficient_evidence",
            b_pass=False,
            bplus_pass=False,
            source="arrival_events source missing",
            owners=["S3", "S1", "S0"],
            insufficient=True,
            note="arrival_events source not provided; pass --arrival-events-glob to evaluate campaign geo/corridor depth.",
        )

    t19 = con.execute(
        f"""
        SELECT
          COUNT(*) AS session_total,
          SUM(CASE WHEN arrival_count = 1 THEN 1 ELSE 0 END) AS singleton_sessions
        FROM {ctx.s1_session_scan}
        """
    ).fetchone()
    session_total = int(t19[0] or 0)
    singleton_sessions = int(t19[1] or 0)
    singleton_share = _safe_div(float(singleton_sessions), float(session_total))
    gates["T19"] = _gate_payload(
        title="singleton-session share",
        gate_class="stretch",
        b_target="<= 0.90",
        bplus_target="<= 0.75",
        value=singleton_share,
        value_fmt=_format_pct(singleton_share),
        b_pass=singleton_share <= 0.90,
        bplus_pass=singleton_share <= 0.75,
        source="s1_session_index_6B full scan",
        owners=["S1"],
    )

    t20 = con.execute(
        f"""
        SELECT
          (
            SELECT AVG(CASE WHEN parties > 1 THEN 1.0 ELSE 0.0 END)
            FROM (
              SELECT device_id, COUNT(DISTINCT party_id) AS parties
              FROM {ctx.s1_arrival_scan}
              GROUP BY 1
            )
          ) AS device_multi_party_share,
          (
            SELECT AVG(CASE WHEN devices > 1 THEN 1.0 ELSE 0.0 END)
            FROM (
              SELECT ip_id, COUNT(DISTINCT device_id) AS devices
              FROM {ctx.s1_arrival_scan}
              GROUP BY 1
            )
          ) AS ip_multi_device_share,
          (
            SELECT AVG(CASE WHEN instruments > 1 THEN 1.0 ELSE 0.0 END)
            FROM (
              SELECT account_id, COUNT(DISTINCT instrument_id) AS instruments
              FROM {ctx.s1_arrival_scan}
              GROUP BY 1
            )
          ) AS account_multi_instrument_share
        """
    ).fetchone()
    device_multi_party_share = float(t20[0] or 0.0)
    ip_multi_device_share = float(t20[1] or 0.0)
    account_multi_instrument_share = float(t20[2] or 0.0)
    richness_score = mean([device_multi_party_share, ip_multi_device_share, account_multi_instrument_share])
    gates["T20"] = _gate_payload(
        title="attachment richness uplift score",
        gate_class="stretch",
        b_target=">= 0.05",
        bplus_target=">= 0.10",
        value={
            "richness_score": richness_score,
            "device_multi_party_share": device_multi_party_share,
            "ip_multi_device_share": ip_multi_device_share,
            "account_multi_instrument_share": account_multi_instrument_share,
        },
        value_fmt=f"richness={richness_score:.6f}",
        b_pass=richness_score >= 0.05,
        bplus_pass=richness_score >= 0.10,
        source="s1_arrival_entities_6B full-scan linkage diversity",
        owners=["S1"],
    )

    amount_tail_branch = bool(gates["T11"]["b_pass"] and gates["T12"]["b_pass"] and gates["T13"]["b_pass"])
    timing_branch = bool(gates["T14"]["b_pass"] and gates["T15"]["b_pass"] and gates["T16"]["b_pass"])
    delay_branch = bool(gates["T8"]["b_pass"] and gates["T9"]["b_pass"] and gates["T10"]["b_pass"])
    coverage_count = int(amount_tail_branch) + int(timing_branch) + int(delay_branch)
    coverage_ratio = coverage_count / 3.0
    gates["T21"] = _gate_payload(
        title="policy execution coverage (amount/timing/delay branches)",
        gate_class="hard",
        b_target=">= 2/3",
        bplus_target="= 3/3",
        value={"coverage_count": coverage_count, "coverage_ratio": coverage_ratio},
        value_fmt=f"{coverage_count}/3 ({coverage_ratio:.6f})",
        b_pass=coverage_count >= 2,
        bplus_pass=coverage_count == 3,
        source="derived from T8-T16 branch activation gates",
        owners=["S2", "S4", "S5"],
        details={
            "amount_tail_branch": amount_tail_branch,
            "timing_branch": timing_branch,
            "delay_branch": delay_branch,
        },
    )

    truth_policy_path = Path("config/layer3/6B/truth_labelling_policy_6B.yaml")
    collision = _load_truth_policy_collision_risk(truth_policy_path, t3_legit_rate=t3_rate)
    collision_count = int(collision["effective_collision_count"])
    gates["T22"] = _gate_payload(
        title="truth-rule collision guard",
        gate_class="hard",
        b_target="collision_count = 0",
        bplus_target="collision_count = 0",
        value={
            "effective_collision_count": collision_count,
            "raw_collision_key_count": int(collision["raw_collision_key_count"]),
            "collision_keys": collision["collision_keys"],
            "observed_collapse": bool(collision["observed_collapse"]),
        },
        value_fmt=f"effective_collision_count={collision_count}",
        b_pass=collision_count == 0,
        bplus_pass=collision_count == 0,
        source="truth_labelling_policy_6B direct_pattern_map collision-risk audit + T3 collapse signal",
        owners=["S4", "S5"],
    )

    hard_failures = [gid for gid in HARD_GATES if not gates[gid]["b_pass"]]
    stretch_failures = [gid for gid in STRETCH_GATES if not gates[gid]["b_pass"]]
    hard_insufficient = [gid for gid in HARD_GATES if bool(gates[gid].get("insufficient_evidence", False))]
    stretch_insufficient = [gid for gid in STRETCH_GATES if bool(gates[gid].get("insufficient_evidence", False))]

    owner_failure_map: dict[str, list[str]] = defaultdict(list)
    for gid, gate in gates.items():
        if gate["b_pass"] and not gate.get("insufficient_evidence", False):
            continue
        for owner in gate.get("owners", []):
            owner_failure_map[str(owner)].append(gid)

    for owner in owner_failure_map:
        owner_failure_map[owner] = sorted(set(owner_failure_map[owner]), key=lambda x: int(x[1:]))

    wave_routing = {
        "P1": [g for g in hard_failures if g in {"T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T21", "T22"}],
        "P2": [g for g in hard_failures if g in {"T11", "T12", "T13", "T14", "T15", "T16"}],
        "P3": [g for g in (stretch_failures + stretch_insufficient) if g in {"T17", "T18"}],
        "P4": [g for g in (stretch_failures + stretch_insufficient) if g in {"T19", "T20"}],
    }
    for phase in wave_routing:
        wave_routing[phase] = sorted(set(wave_routing[phase]), key=lambda x: int(x[1:]))

    all_hard_b = len(hard_failures) == 0
    all_hard_bplus = all(gates[g]["bplus_pass"] for g in HARD_GATES)
    all_stretch_b = all(gates[g]["b_pass"] for g in STRETCH_GATES)
    all_stretch_bplus = all(gates[g]["bplus_pass"] for g in STRETCH_GATES)

    if all_hard_bplus and all_stretch_bplus:
        overall_verdict = "PASS_BPLUS"
    elif all_hard_b and all_stretch_b:
        overall_verdict = "PASS_B"
    elif all_hard_b:
        overall_verdict = "PASS_HARD_ONLY"
    else:
        overall_verdict = "FAIL_REALISM"

    phase_decision = "UNLOCK_P1" if all_hard_b else "HOLD_REMEDIATE"
    s5_report = _load_json(ctx.s5_report_path)

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P0",
        "segment": "6B",
        "run": {
            "run_id": ctx.run_id,
            "runs_root": _to_posix(runs_root),
            "run_root": _to_posix(ctx.run_root),
            "seed": ctx.seed,
            "manifest_fingerprint": ctx.manifest_fingerprint,
            "parameter_hash": ctx.parameter_hash,
        },
        "baseline_sources": {
            "s5_validation_report_6B": _to_posix(ctx.s5_report_path),
            "merchant_class_glob": merchant_class_glob if merchant_class_available else None,
            "arrival_events_glob": arrival_events_glob if arrival_events_available else None,
            "truth_policy_path": _to_posix(truth_policy_path),
            "authority_reports": [
                "docs/reports/eda/segment_6B/segment_6B_published_report.md",
                "docs/reports/eda/segment_6B/segment_6B_remediation_report.md",
            ],
        },
        "gates": gates,
        "summary": {
            "hard_failures": hard_failures,
            "hard_insufficient": hard_insufficient,
            "stretch_failures": stretch_failures,
            "stretch_insufficient": stretch_insufficient,
            "overall_verdict": overall_verdict,
            "phase_decision": phase_decision,
            "owner_failure_map": dict(owner_failure_map),
            "wave_routing": wave_routing,
            "flow_count": flow_count,
            "s5_overall_status": s5_report.get("overall_status"),
            "sampling": {
                "case_sample_mod": case_sample_mod,
                "latency_sample_mod": latency_sample_mod,
            },
            "critical_veto_policy": {
                "critical_gate_set": HARD_GATES,
                "fail_closed": True,
                "unresolved_critical_blocks_promotion": True,
            },
        },
    }

    out_json = out_root / f"segment6b_p0_realism_gateboard_{ctx.run_id}.json"
    out_md = out_root / f"segment6b_p0_realism_gateboard_{ctx.run_id}.md"
    _write_json(out_json, payload)
    _write_text(out_md, _render_markdown(payload))

    print(f"[segment6b-p0] gateboard_json={_to_posix(out_json)}")
    print(f"[segment6b-p0] gateboard_md={_to_posix(out_md)}")
    print(f"[segment6b-p0] overall_verdict={overall_verdict}")
    print(f"[segment6b-p0] phase_decision={phase_decision}")


if __name__ == "__main__":
    main()
