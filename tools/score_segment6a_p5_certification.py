#!/usr/bin/env python3
"""Score Segment 6A P5 multi-seed certification posture."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


REQUIRED_SEEDS = (42, 7, 101, 202)
HARD_GATES = (
    "T1_KMAX_HARD_INVARIANT",
    "T2_KMAX_TAIL_SANITY",
    "T3_IP_PRIOR_ALIGNMENT",
    "T4_DEVICE_IP_COVERAGE",
    "T5_IP_REUSE_TAIL_BOUNDS",
    "T6_ROLE_MAPPING_COVERAGE",
    "T7_RISK_PROPAGATION_EFFECT",
    "T8_DISTRIBUTION_ALIGNMENT_JSD",
)
T9_METRICS = (
    "t3_value",
    "t4_value",
    "t5_p99_devices_per_ip",
    "t5_max_devices_per_ip",
    "t7_or_account",
    "t7_or_device",
    "t8_value",
)
T9_CV_FLOORS = {
    "t3_value": 0.15,
    "t4_value": 0.0025,
    "t5_p99_devices_per_ip": 1.2,
    "t5_max_devices_per_ip": 6.0,
    "t7_or_account": 0.015,
    "t7_or_device": 0.015,
    "t8_value": 0.0008,
}


@dataclass(frozen=True)
class SeedRun:
    seed: int
    run_id: str


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _cv(values: list[float], floor: float) -> tuple[float, float]:
    if not values:
        return float("inf"), float("nan")
    if len(values) == 1:
        return 0.0, abs(values[0])
    mu = mean(values)
    sigma = pstdev(values)
    denom = max(abs(mu), float(floor))
    if denom < 1e-12:
        return (0.0 if sigma < 1e-12 else float("inf")), denom
    return abs(sigma / denom), denom


def _parse_seed_run(text: str) -> SeedRun:
    if ":" not in text:
        raise ValueError(f"Invalid --seed-run '{text}', expected '<seed>:<run_id>'")
    seed_str, run_id = text.split(":", 1)
    seed = int(seed_str)
    run = run_id.strip()
    if not run:
        raise ValueError(f"Invalid --seed-run '{text}', run_id is empty")
    return SeedRun(seed=seed, run_id=run)


def _extract_t9_vector(gates: dict[str, Any]) -> dict[str, float]:
    t3 = _safe_float((gates.get("T3_IP_PRIOR_ALIGNMENT") or {}).get("value"))
    t4 = _safe_float((gates.get("T4_DEVICE_IP_COVERAGE") or {}).get("value"))
    t8 = _safe_float((gates.get("T8_DISTRIBUTION_ALIGNMENT_JSD") or {}).get("value"))

    t5_value = (gates.get("T5_IP_REUSE_TAIL_BOUNDS") or {}).get("value") or {}
    t5_p99 = _safe_float((t5_value or {}).get("p99_devices_per_ip"))
    t5_max = _safe_float((t5_value or {}).get("max_devices_per_ip"))

    t7_value = (gates.get("T7_RISK_PROPAGATION_EFFECT") or {}).get("value") or {}
    t7_account = _safe_float((t7_value or {}).get("or_account"))
    t7_device = _safe_float((t7_value or {}).get("or_device"))

    vals = {
        "t3_value": t3,
        "t4_value": t4,
        "t5_p99_devices_per_ip": t5_p99,
        "t5_max_devices_per_ip": t5_max,
        "t7_or_account": t7_account,
        "t7_or_device": t7_device,
        "t8_value": t8,
    }
    missing = [k for k, v in vals.items() if v is None]
    if missing:
        raise ValueError(f"Missing T9 vector values in gateboard: {missing}")
    return {k: float(v) for k, v in vals.items() if v is not None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 6A P5 multi-seed certification.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_6A")
    parser.add_argument("--reports-root", default="runs/fix-data-engine/segment_6A/reports")
    parser.add_argument(
        "--seed-run",
        action="append",
        default=[],
        help="Seed to run mapping as '<seed>:<run_id>'. Repeat for each required seed.",
    )
    parser.add_argument(
        "--downstream-report-6b",
        default=(
            "runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/"
            "data/layer3/6B/validation/"
            "manifest_fingerprint=c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8/"
            "s5_validation_report_6B.json"
        ),
    )
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    reports_root = Path(args.reports_root)
    reports_root.mkdir(parents=True, exist_ok=True)

    mappings = [_parse_seed_run(raw) for raw in args.seed_run]
    if not mappings:
        raise ValueError("At least one --seed-run mapping is required")

    by_seed = {m.seed: m for m in mappings}
    missing_required = [seed for seed in REQUIRED_SEEDS if seed not in by_seed]
    if missing_required:
        raise ValueError(f"Missing required seeds in run map: {missing_required}")

    seed_rows: list[dict[str, Any]] = []
    t9_values: dict[str, list[float]] = {metric: [] for metric in T9_METRICS}
    veto_reasons: list[str] = []

    for seed in REQUIRED_SEEDS:
        mapping = by_seed[seed]
        run_id = mapping.run_id
        run_root = runs_root / run_id
        if not run_root.exists():
            raise FileNotFoundError(f"Run root not found: {run_root}")

        receipt_path = run_root / "run_receipt.json"
        receipt = _load_json(receipt_path)
        receipt_seed = int(receipt.get("seed"))
        if receipt_seed != seed:
            raise ValueError(f"Run {run_id} has seed={receipt_seed}, expected seed={seed}")

        gateboard_path = reports_root / f"segment6a_p0_realism_gateboard_{run_id}.json"
        if not gateboard_path.exists():
            raise FileNotFoundError(f"Missing per-seed gateboard for seed={seed}: {gateboard_path}")
        gateboard = _load_json(gateboard_path)
        gates = gateboard.get("gates") or {}

        hard_fail_b = [gate for gate in HARD_GATES if not bool((gates.get(gate) or {}).get("pass_B"))]
        hard_fail_bplus = [gate for gate in HARD_GATES if not bool((gates.get(gate) or {}).get("pass_Bplus"))]
        t9_vector = _extract_t9_vector(gates)
        for metric, value in t9_vector.items():
            t9_values[metric].append(float(value))

        s5_report_path = (
            run_root
            / "data/layer3/6A/validation"
            / f"manifest_fingerprint={receipt.get('manifest_fingerprint')}"
            / "s5_validation_report_6A.json"
        )
        s5_status = "MISSING"
        if s5_report_path.exists():
            s5_payload = _load_json(s5_report_path)
            s5_status = str(s5_payload.get("overall_status") or "")
        if s5_status != "PASS":
            veto_reasons.append(f"seed={seed}:s5_status={s5_status}")
        if hard_fail_b:
            veto_reasons.append(f"seed={seed}:hard_fail_B={hard_fail_b}")

        seed_rows.append(
            {
                "seed": seed,
                "run_id": run_id,
                "hard_failures_b": hard_fail_b,
                "hard_failures_bplus": hard_fail_bplus,
                "s5_status": s5_status,
                "gateboard_path": str(gateboard_path),
                "t9_vector": t9_vector,
            }
        )

    t9_rows: list[dict[str, Any]] = []
    t9_cv_values: list[float] = []
    for metric in T9_METRICS:
        values = t9_values.get(metric) or []
        cv, denom = _cv(values, T9_CV_FLOORS.get(metric, 1e-9))
        finite = math.isfinite(cv)
        t9_rows.append(
            {
                "metric": metric,
                "seed_values": values,
                "cv": cv if finite else None,
                "cv_denom": denom,
                "cv_floor": T9_CV_FLOORS.get(metric, 1e-9),
            }
        )
        if finite:
            t9_cv_values.append(cv)

    t9_overall = max(t9_cv_values) if len(t9_cv_values) == len(T9_METRICS) else float("inf")
    t9_pass_b = bool(math.isfinite(t9_overall) and t9_overall <= 0.25)
    t9_pass_bplus = bool(math.isfinite(t9_overall) and t9_overall <= 0.15)

    downstream_path = Path(args.downstream_report_6b)
    if not downstream_path.exists():
        t10 = {
            "status": "INSUFFICIENT_EVIDENCE",
            "pass_B": False,
            "pass_Bplus": False,
            "details": {"reason": "downstream_6b_report_missing", "path": str(downstream_path)},
        }
        veto_reasons.append("t10:missing_downstream_6b_report")
    else:
        downstream = _load_json(downstream_path)
        checks = list(downstream.get("checks") or [])
        required_checks = [row for row in checks if str(row.get("severity") or "").upper() == "REQUIRED"]
        required_failures = [
            str(row.get("check_id") or "")
            for row in required_checks
            if str(row.get("result") or "").upper() != "PASS"
        ]
        overall = str(downstream.get("overall_status") or "").upper()
        pass_b = len(required_failures) == 0 and len(required_checks) > 0
        pass_bplus = pass_b and overall == "PASS"
        if not pass_b:
            veto_reasons.append(f"t10:required_failures={required_failures}")
        t10 = {
            "status": "PASS" if pass_b else "FAIL",
            "pass_B": pass_b,
            "pass_Bplus": pass_bplus,
            "details": {
                "downstream_path": str(downstream_path),
                "overall_status_6b": overall,
                "required_checks_total": len(required_checks),
                "required_failures": required_failures,
            },
        }

    all_seed_b = all(len(row["hard_failures_b"]) == 0 and row["s5_status"] == "PASS" for row in seed_rows)
    all_seed_bplus = all(len(row["hard_failures_bplus"]) == 0 and row["s5_status"] == "PASS" for row in seed_rows)

    if all_seed_bplus and t9_pass_bplus and t10.get("pass_Bplus"):
        decision = "PASS_BPLUS"
    elif all_seed_b and t9_pass_b and t10.get("pass_B"):
        decision = "PASS_B"
    else:
        decision = "HOLD_P5_REMEDIATE"

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    seed_gateboard_path = reports_root / f"segment6a_p5_seed_gateboard_{stamp}.json"
    t9_path = reports_root / f"segment6a_p5_t9_stability_{stamp}.json"
    closure_path = reports_root / f"segment6a_p5_closure_{stamp}.json"
    closure_md_path = reports_root / f"segment6a_p5_closure_{stamp}.md"

    seed_payload = {
        "generated_utc": _now_utc(),
        "phase": "P5.1B",
        "segment": "6A",
        "required_seeds": list(REQUIRED_SEEDS),
        "rows": seed_rows,
    }
    seed_gateboard_path.write_text(json.dumps(seed_payload, indent=2), encoding="utf-8")

    t9_payload = {
        "generated_utc": _now_utc(),
        "phase": "P5.1C",
        "segment": "6A",
        "required_seeds": list(REQUIRED_SEEDS),
        "metrics": t9_rows,
        "t9_overall_cv": t9_overall if math.isfinite(t9_overall) else None,
        "thresholds": {"B": 0.25, "BPLUS": 0.15},
        "pass_B": t9_pass_b,
        "pass_Bplus": t9_pass_bplus,
    }
    t9_path.write_text(json.dumps(t9_payload, indent=2), encoding="utf-8")

    closure_payload = {
        "generated_utc": _now_utc(),
        "phase": "P5.2A",
        "segment": "6A",
        "decision": decision,
        "required_seeds": list(REQUIRED_SEEDS),
        "selected_seed_run_map": {str(row["seed"]): str(row["run_id"]) for row in seed_rows},
        "summary": {
            "all_seed_hard_pass_B": all_seed_b,
            "all_seed_hard_pass_Bplus": all_seed_bplus,
            "t9_pass_B": t9_pass_b,
            "t9_pass_Bplus": t9_pass_bplus,
            "t10_pass_B": bool(t10.get("pass_B")),
            "t10_pass_Bplus": bool(t10.get("pass_Bplus")),
            "t9_overall_cv": t9_payload["t9_overall_cv"],
            "veto_reasons": veto_reasons,
        },
        "t10": t10,
        "artifacts": {
            "seed_gateboard": str(seed_gateboard_path),
            "t9_stability": str(t9_path),
        },
    }
    closure_path.write_text(json.dumps(closure_payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Segment 6A P5 Certification Closure",
        "",
        f"- Generated UTC: `{closure_payload['generated_utc']}`",
        f"- Decision: `{decision}`",
        f"- T9 overall CV: `{closure_payload['summary']['t9_overall_cv']}`",
        f"- T10 pass (B/B+): `{closure_payload['summary']['t10_pass_B']}` / `{closure_payload['summary']['t10_pass_Bplus']}`",
        "",
        "## Seed Summary",
        "| Seed | Run ID | S5 | Hard Failures B | Hard Failures B+ |",
        "|---:|---|:---:|---|---|",
    ]
    for row in seed_rows:
        md_lines.append(
            f"| {row['seed']} | `{row['run_id']}` | `{row['s5_status']}` | "
            f"`{row['hard_failures_b']}` | `{row['hard_failures_bplus']}` |"
        )
    md_lines.extend(
        [
            "",
            "## Veto Reasons",
            *(["- none"] if not veto_reasons else [f"- `{reason}`" for reason in veto_reasons]),
            "",
            "## Artifacts",
            f"- seed gateboard: `{seed_gateboard_path}`",
            f"- t9 stability: `{t9_path}`",
            f"- closure json: `{closure_path}`",
            "",
        ]
    )
    closure_md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"[segment6a-p5] seed_gateboard={seed_gateboard_path}")
    print(f"[segment6a-p5] t9_stability={t9_path}")
    print(f"[segment6a-p5] closure_json={closure_path}")
    print(f"[segment6a-p5] closure_md={closure_md_path}")
    print(f"[segment6a-p5] decision={decision}")


if __name__ == "__main__":
    main()
