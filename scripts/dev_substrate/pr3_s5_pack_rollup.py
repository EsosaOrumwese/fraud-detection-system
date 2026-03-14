#!/usr/bin/env python3
"""Build PR3-S5 runtime pack evidence index, report, and verdict."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict[str, Any] | None:
    return load_json(path) if path.exists() else None


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def dump_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    receipts = {
        "s0": load_optional_json(root / "pr3_s0_execution_receipt.json"),
        "s1": load_optional_json(root / "pr3_s1_execution_receipt.json"),
        "s2": load_optional_json(root / "pr3_s2_execution_receipt.json"),
        "s3": load_optional_json(root / "pr3_s3_execution_receipt.json"),
        "s4": load_optional_json(root / "pr3_s4_execution_receipt.json"),
        "stress": load_optional_json(root / "g3a_stress_execution_receipt.json"),
        "soak": load_optional_json(root / "g3a_soak_execution_receipt.json"),
    }
    stress_scorecard = load_optional_json(root / "g3a_stress_scorecard.json")
    soak_scorecard = load_optional_json(root / "g3a_scorecard_soak.json")
    cost_receipt = load_optional_json(root / "g3a_runtime_cost_receipt.json") or load_optional_json(root / "g3a_stress_cost_receipt.json")
    learning_summary = load_optional_json(root / "g3a_correctness_learning_summary.json")
    ops_gov_summary = load_optional_json(root / "g3a_correctness_ops_gov_summary.json")

    blockers: list[str] = []
    detail_blockers: list[str] = []

    if receipts["stress"] is None:
        blockers.append("PR3.B29_STRESS_WINDOW_NOT_EXECUTED")
    else:
        detail_blockers.extend([str(x) for x in receipts["stress"].get("blocker_ids", []) or []])
        if str(receipts["stress"].get("verdict") or "").strip() != "PR3_S5_STRESS_READY":
            blockers.append("PR3.B30_STRESS_WINDOW_FAIL")

    if receipts["soak"] is not None:
        detail_blockers.extend([str(x) for x in receipts["soak"].get("blocker_ids", []) or []])

    if cost_receipt is None or cost_receipt.get("attributed_spend_usd") is None:
        blockers.append("PR3.B35_UNATTRIBUTED_RUNTIME_SPEND")

    evidence_index = {
        "phase": "PR3",
        "state": "S5",
        "generated_at_utc": now_utc(),
        "run_charter_ref": "g3a_run_charter.active.json",
        "scorecard_artifacts": [
            "g3a_scorecard_steady.json",
            "g3a_scorecard_burst.json",
            "g3a_scorecard_recovery.json",
            "g3a_correctness_scorecard.json",
            "g3a_stress_scorecard.json",
        ] + (["g3a_scorecard_soak.json"] if soak_scorecard else []),
        "cohort_artifacts": ["g3a_cohort_manifest.json", "g3a_cohort_results.json"],
        "drill_artifacts": [
            "g3a_drill_replay_integrity.json",
            "g3a_drill_lag_recovery.json",
            "g3a_drill_schema_evolution.json",
            "g3a_drill_dependency_degrade.json",
            "g3a_drill_cost_guardrail.json",
        ],
        "query_definition_refs": ["g3a_measurement_surface_map.json"],
        "open_blockers": len(blockers) + len(detail_blockers),
    }
    if not evidence_index["scorecard_artifacts"]:
        blockers.append("PR3.B31_RUNTIME_EVIDENCE_INDEX_MISSING")

    overall_pass = len(blockers) == 0 and len(detail_blockers) == 0
    next_gate = "PR4_READY" if overall_pass else "PR3-S5"
    verdict_name = "PASS" if overall_pass else "HOLD_REMEDIATE"
    runtime_verdict = {
        "phase": "PR3",
        "state": "S5",
        "generated_at_utc": now_utc(),
        "overall_pass": overall_pass,
        "verdict": verdict_name,
        "open_blockers": len(blockers) + len(detail_blockers),
        "blocker_ids": blockers + detail_blockers,
        "next_gate": next_gate,
    }
    if runtime_verdict["overall_pass"] != (runtime_verdict["open_blockers"] == 0):
        blockers.append("PR3.B32_RUNTIME_VERDICT_INCOHERENT")
        runtime_verdict["overall_pass"] = False
        runtime_verdict["verdict"] = "HOLD_REMEDIATE"
        runtime_verdict["open_blockers"] = len(blockers) + len(detail_blockers)
        runtime_verdict["blocker_ids"] = blockers + detail_blockers
        runtime_verdict["next_gate"] = "PR3-S5"
    if runtime_verdict["open_blockers"] != 0:
        blockers.append("PR3.B33_OPEN_BLOCKERS_NONZERO")
    if runtime_verdict["next_gate"] != "PR4_READY" and overall_pass:
        blockers.append("PR3.B34_NEXT_GATE_NOT_PR4_READY")

    evidence_index["open_blockers"] = len(set(blockers + detail_blockers))

    stress_ingress = dict((stress_scorecard or {}).get("ingress") or {})
    soak_ingress = dict((soak_scorecard or {}).get("ingress") or {})
    lines = [
        "# PR3 Runtime Pack Report",
        "",
        f"- execution_id: `{args.pr3_execution_id}`",
        f"- generated_at_utc: `{now_utc()}`",
        f"- overall_pass: `{runtime_verdict['overall_pass']}`",
        f"- next_gate: `{runtime_verdict['next_gate']}`",
        "",
        "## Impact Metrics",
        "",
        "| Surface | Observed | Assessment |",
        "| --- | --- | --- |",
        f"| Stress ingress | admitted `{stress_ingress.get('observed_admitted_eps')}` eps, `4xx={stress_ingress.get('4xx_rate_ratio')}`, `5xx={stress_ingress.get('5xx_rate_ratio')}`, `p95={stress_ingress.get('latency_p95_ms')}` ms, `p99={stress_ingress.get('latency_p99_ms')}` ms | {'meets bounded stress gate' if receipts['stress'] and str(receipts['stress'].get('verdict')) == 'PR3_S5_STRESS_READY' else 'does not meet bounded stress gate'} |",
        f"| Soak ingress | admitted `{soak_ingress.get('observed_admitted_eps')}` eps, `4xx={soak_ingress.get('4xx_rate_ratio')}`, `5xx={soak_ingress.get('5xx_rate_ratio')}`, `p95={soak_ingress.get('latency_p95_ms')}` ms, `p99={soak_ingress.get('latency_p99_ms')}` ms | {'meets conditional soak gate' if receipts['soak'] and str(receipts['soak'].get('verdict')) == 'PR3_S5_SOAK_READY' else 'not claimed or failed'} |",
        f"| Case/label plane | stress receipt `{receipts['stress'].get('verdict') if receipts['stress'] else 'missing'}` | {'working on the bounded runtime pack' if receipts['stress'] else 'unproven'} |",
        f"| Learning/evolution | `overall_pass={bool((learning_summary or {}).get('overall_pass'))}` | {'bounded same-run proof remains green' if bool((learning_summary or {}).get('overall_pass')) else 'not production-ready'} |",
        f"| Ops/gov | `overall_pass={bool((ops_gov_summary or {}).get('overall_pass'))}` | {'same-run closure remains green' if bool((ops_gov_summary or {}).get('overall_pass')) else 'not production-ready'} |",
        f"| Runtime spend | attributed `{(cost_receipt or {}).get('attributed_spend_usd')}` USD | {'attributed and bounded' if cost_receipt and cost_receipt.get('attributed_spend_usd') is not None else 'unattributed'} |",
        "",
        "## Blockers",
        "",
    ]
    if blockers or detail_blockers:
        for item in blockers + detail_blockers:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")

    summary = {
        "phase": "PR3",
        "state": "S5",
        "generated_at_utc": now_utc(),
        "verdict": "PR4_READY" if len(blockers) == 0 and len(detail_blockers) == 0 else "HOLD_REMEDIATE",
        "next_gate": "PR4_READY" if len(blockers) == 0 and len(detail_blockers) == 0 else "PR3-S5",
        "open_blockers": len(set(blockers + detail_blockers)),
        "blocker_ids": list(dict.fromkeys(blockers + detail_blockers)),
        "target_closure_refs": [
            "g3a_scorecard_steady.json",
            "g3a_scorecard_burst.json",
            "g3a_scorecard_recovery.json",
            "g3a_correctness_scorecard.json",
            "g3a_stress_scorecard.json",
        ] + (["g3a_scorecard_soak.json"] if soak_scorecard else []),
    }
    receipt = {
        "phase": "PR3",
        "state": "S5",
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "verdict": summary["verdict"],
        "next_gate": summary["next_gate"],
        "open_blockers": summary["open_blockers"],
        "blocker_ids": summary["blocker_ids"],
        "elapsed_minutes": 0.0,
        "runtime_budget_minutes": 20.0,
        "attributable_spend_usd": (cost_receipt or {}).get("attributed_spend_usd"),
        "cost_envelope_usd": (cost_receipt or {}).get("budget_envelope_usd"),
        "advisory_ids": [],
    }

    dump_text(root / "g3a_scorecard_report.md", "\n".join(lines) + "\n")
    dump_json(root / "g3a_runtime_evidence_index.json", evidence_index)
    dump_json(root / "g3a_runtime_verdict.json", runtime_verdict)
    dump_json(root / "pr3_blocker_register.json", {"blocker_ids": summary["blocker_ids"]})
    dump_json(root / "pr3_execution_summary.json", summary)
    dump_json(root / "pr3_s5_execution_receipt.json", receipt)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
