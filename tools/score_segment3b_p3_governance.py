#!/usr/bin/env python3
"""Score Segment 3B P3 S4-governance closure (observe/enforce)."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl


REQUIRED_REALISM_TEST_TYPES = {
    "EDGE_HETEROGENEITY",
    "SETTLEMENT_COHERENCE",
    "CLASSIFICATION_EXPLAINABILITY",
    "ALIAS_FIDELITY",
}


def _parse_seed_list(raw: str) -> list[int]:
    out: list[int] = []
    for token in str(raw).split(","):
        token = token.strip()
        if token:
            out.append(int(token))
    if not out:
        raise ValueError("seed list is empty")
    return out


def _parse_seed_run(items: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in items:
        raw = str(item).strip()
        if ":" not in raw:
            raise ValueError(f"invalid --seed-run '{raw}' (expected seed:run_id)")
        seed_raw, run_id = raw.split(":", 1)
        out[int(seed_raw.strip())] = run_id.strip()
    return out


def _resolve_latest_seed_run(runs_root: Path, seed: int) -> str:
    candidates: list[tuple[float, str]] = []
    for receipt_path in runs_root.glob("*/run_receipt.json"):
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        if int(payload.get("seed", -1)) != int(seed):
            continue
        run_id = str(payload.get("run_id") or "")
        if not run_id:
            continue
        candidates.append((receipt_path.stat().st_mtime, run_id))
    if not candidates:
        raise FileNotFoundError(f"no run_receipt.json with seed={seed} under {runs_root}")
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _status_report(run_root: Path, seed: int, manifest: str, state: str) -> Path:
    return (
        run_root
        / "reports/layer1/3B"
        / f"state={state}"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest}"
        / "run_report.json"
    )


@dataclass(frozen=True)
class SeedContext:
    seed: int
    run_id: str
    manifest_fingerprint: str
    run_root: Path
    contract_path: Path
    s4_report_path: Path
    s5_report_path: Path


def _resolve_seed_context(runs_root: Path, seed: int, run_id: str) -> SeedContext:
    run_root = runs_root / run_id
    receipt_path = run_root / "run_receipt.json"
    if not receipt_path.exists():
        raise FileNotFoundError(f"missing run_receipt.json for run_id={run_id}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_seed = int(receipt.get("seed", -1))
    if receipt_seed != int(seed):
        raise ValueError(f"seed mismatch run_id={run_id}: receipt.seed={receipt_seed}, expected={seed}")
    manifest = str(receipt.get("manifest_fingerprint") or "")
    if not manifest:
        raise ValueError(f"missing manifest_fingerprint in run_id={run_id}")

    contract_path = (
        run_root
        / "data/layer1/3B/virtual_validation_contract"
        / f"manifest_fingerprint={manifest}"
        / "virtual_validation_contract_3B.parquet"
    )
    s4_report_path = _status_report(run_root, seed, manifest, "S4")
    s5_report_path = _status_report(run_root, seed, manifest, "S5")
    for p in (contract_path, s4_report_path, s5_report_path):
        if not p.exists():
            raise FileNotFoundError(f"missing required path for run_id={run_id}: {p}")

    return SeedContext(
        seed=seed,
        run_id=run_id,
        manifest_fingerprint=manifest,
        run_root=run_root,
        contract_path=contract_path,
        s4_report_path=s4_report_path,
        s5_report_path=s5_report_path,
    )


def _check_mode_rows(vv_df: pl.DataFrame, mode: str, test_type: str) -> dict[str, Any]:
    subset = vv_df.filter(pl.col("test_type") == test_type)
    row_count = int(subset.height)
    if row_count == 0:
        return {
            "present": False,
            "row_count": 0,
            "enabled_any": False,
            "blocking_any": False,
            "warning_any": False,
            "mode_pass": False,
            "severity_values": [],
        }

    enabled_any = bool(subset.select(pl.col("enabled").any()).item())
    blocking_any = bool(
        subset.filter((pl.col("enabled") == True) & (pl.col("severity") == "BLOCKING")).height > 0  # noqa: E712
    )
    warning_any = bool(
        subset.filter((pl.col("enabled") == True) & (pl.col("severity") == "WARNING")).height > 0  # noqa: E712
    )
    severity_values = sorted({str(v) for v in subset.get_column("severity").to_list() if v is not None})

    if mode == "enforce":
        mode_pass = enabled_any and blocking_any
    elif mode == "observe":
        mode_pass = enabled_any and warning_any and (not blocking_any)
    else:
        raise ValueError(f"unsupported mode={mode}")

    return {
        "present": True,
        "row_count": row_count,
        "enabled_any": enabled_any,
        "blocking_any": blocking_any,
        "warning_any": warning_any,
        "mode_pass": bool(mode_pass),
        "severity_values": severity_values,
    }


def _seed_score(ctx: SeedContext, mode: str) -> dict[str, Any]:
    vv_df = pl.read_parquet(ctx.contract_path)
    s4_report = json.loads(ctx.s4_report_path.read_text(encoding="utf-8"))
    s5_report = json.loads(ctx.s5_report_path.read_text(encoding="utf-8"))

    test_checks = {
        test_type: _check_mode_rows(vv_df, mode, test_type)
        for test_type in sorted(REQUIRED_REALISM_TEST_TYPES)
    }
    types_present = {test_type for test_type, check in test_checks.items() if check["present"]}
    all_required_present = REQUIRED_REALISM_TEST_TYPES.issubset(types_present)
    mode_gate_pass = all(check["mode_pass"] for check in test_checks.values())
    s4_pass = str(s4_report.get("status") or "") == "PASS"
    s5_pass = str(s5_report.get("status") or "") == "PASS"

    passed = all_required_present and mode_gate_pass and s4_pass and s5_pass
    return {
        "seed": int(ctx.seed),
        "run_id": ctx.run_id,
        "manifest_fingerprint": ctx.manifest_fingerprint,
        "mode": mode,
        "required_test_types": sorted(REQUIRED_REALISM_TEST_TYPES),
        "present_test_types": sorted(types_present),
        "test_checks": test_checks,
        "s4_status": str(s4_report.get("status") or "UNKNOWN"),
        "s5_status": str(s5_report.get("status") or "UNKNOWN"),
        "pass": bool(passed),
        "provenance": {
            "virtual_validation_contract_path": str(ctx.contract_path).replace("\\", "/"),
            "s4_run_report_path": str(ctx.s4_report_path).replace("\\", "/"),
            "s5_run_report_path": str(ctx.s5_report_path).replace("\\", "/"),
        },
    }


def _render_md(summary: dict[str, Any]) -> str:
    lines = [
        "# Segment 3B P3 Governance Summary",
        "",
        f"- mode: `{summary['mode']}`",
        f"- decision: `{summary['decision']}`",
        f"- overall_pass: `{summary['overall_pass']}`",
        "",
        "## Seed Results",
        "",
        "| seed | run_id | pass | s4_status | s5_status | missing_types |",
        "|---:|---|---|---|---|---|",
    ]
    for item in summary["seed_results"]:
        missing = sorted(set(summary["required_test_types"]) - set(item["present_test_types"]))
        missing_txt = ",".join(missing) if missing else "-"
        lines.append(
            f"| {item['seed']} | {item['run_id']} | {item['pass']} | "
            f"{item['s4_status']} | {item['s5_status']} | {missing_txt} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 3B P3 governance closure.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--seeds", default="42,101")
    parser.add_argument("--seed-run", action="append", default=[], help="seed:run_id (repeatable)")
    parser.add_argument("--mode", choices=["observe", "enforce"], required=True)
    parser.add_argument("--tag", default="p3_governance")
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    out_dir = Path(args.out_dir) if args.out_dir else runs_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = _parse_seed_list(args.seeds)
    seed_run_map = _parse_seed_run(args.seed_run or [])
    for seed in seeds:
        seed_run_map.setdefault(seed, _resolve_latest_seed_run(runs_root, seed))

    contexts = [_resolve_seed_context(runs_root, seed, seed_run_map[seed]) for seed in seeds]
    seed_results = [_seed_score(ctx, args.mode) for ctx in contexts]
    overall_pass = all(item["pass"] for item in seed_results)
    decision = "PASS" if overall_pass else "FAIL"

    summary = {
        "segment": "3B",
        "phase": "P3",
        "mode": args.mode,
        "tag": args.tag,
        "runs_root": str(runs_root).replace("\\", "/"),
        "required_test_types": sorted(REQUIRED_REALISM_TEST_TYPES),
        "seed_run_map": {str(seed): seed_run_map[seed] for seed in seeds},
        "seed_results": seed_results,
        "overall_pass": bool(overall_pass),
        "decision": decision,
    }

    stem = f"segment3b_p3_governance_{args.tag}_{args.mode}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    _write_json(json_path, summary)
    _write_text(md_path, _render_md(summary))
    print(str(json_path).replace("\\", "/"))
    print(str(md_path).replace("\\", "/"))
    print(f"decision={decision}")


if __name__ == "__main__":
    main()
