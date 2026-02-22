#!/usr/bin/env python3
"""Emit Segment 5B P2 contract-lock artifact."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RUN_ID_DEFAULT = "c25a2675fbfbacd952b13bb594880e92"

PRIMARY_GATES = ["T6", "T7"]
FROZEN_VETO_GATES = ["T1", "T2", "T3", "T4", "T5", "T11", "T12"]
CONTEXT_WATCH = ["T8", "T9"]


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 5B P2 contract lock artifact.")
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument(
        "--p1-gateboard-path",
        default="",
        help="Optional P1 gateboard path. Defaults to out_root/segment5b_p1_realism_gateboard_<run_id>.json",
    )
    args = parser.parse_args()

    run_id = args.run_id.strip() or RUN_ID_DEFAULT
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    if args.p1_gateboard_path:
        p1_path = Path(args.p1_gateboard_path)
    else:
        p1_path = out_root / f"segment5b_p1_realism_gateboard_{run_id}.json"
    if not p1_path.exists():
        raise FileNotFoundError(f"Missing P1 gateboard: {p1_path}")
    p1 = _load_json(p1_path)
    gates = p1.get("gates") or {}
    missing = [gid for gid in (PRIMARY_GATES + FROZEN_VETO_GATES + CONTEXT_WATCH) if gid not in gates]
    if missing:
        raise ValueError(f"P1 gateboard missing expected gates: {missing}")

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P2.1",
        "segment": "5B",
        "run_id": run_id,
        "source_gateboard_p1": str(p1_path),
        "target_ownership": {
            "primary": PRIMARY_GATES,
            "frozen_veto": FROZEN_VETO_GATES,
            "context_watch": CONTEXT_WATCH,
        },
        "closure_targets": {
            "T6": {"b": "<=0.72", "bplus": "<=0.62"},
            "T7": {"b": "0.03<=share<=0.08", "bplus": "0.05<=share<=0.12"},
        },
        "decision_vocabulary": [
            "UNLOCK_P3",
            "HOLD_P2_REOPEN",
            "UNLOCK_P2_UPSTREAM_REOPEN",
        ],
        "runtime_budgets": {
            "candidate_s4_s5_seconds_max": 540,
            "witness_two_seed_seconds_max": 1080,
            "runtime_regression_veto_fraction": 0.20,
        },
        "run_protocol": {
            "allowed_edit_surface": [
                "config/layer2/5B/arrival_routing_policy_5B.yaml",
                "config/layer2/5B/arrival_lgcp_config_5B.yaml (only if lane explicitly opened)",
                "packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/runner.py (conditional code lane only)",
            ],
            "rerun_matrix": {
                "policy_only": ["S4", "S5"],
                "conditional_code_lane": ["S4", "S5"],
            },
            "publish_hygiene": {
                "required_pre_rerun_cleanup": [
                    "data/layer2/5B/arrival_events/seed=<seed>/manifest_fingerprint=<mf>/scenario_id=baseline_v1",
                    "data/layer2/5B/validation/manifest_fingerprint=<mf>",
                ],
                "reason": "S4 skips publish on existing dir; S5 fails on non-identical existing bundle.",
            },
        },
        "current_posture_snapshot": {
            "T6": gates["T6"]["value"],
            "T7": gates["T7"]["value"],
            "frozen_gate_pass": {gid: bool((gates.get(gid) or {}).get("b_pass")) for gid in FROZEN_VETO_GATES},
        },
    }

    out_path = out_root / f"segment5b_p2_contract_lock_{run_id}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[segment5b-p2] contract_lock={out_path}")


if __name__ == "__main__":
    main()
