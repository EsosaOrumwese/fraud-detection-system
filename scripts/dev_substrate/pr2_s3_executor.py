#!/usr/bin/env python3
"""Deterministic PR2-S3 executor for road_to_prod (dev_full)."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def is_readable(path: Path) -> bool:
    if not path.exists():
        return False
    suffix = path.suffix.lower()
    try:
        with path.open("r", encoding="utf-8") as f:
            if suffix == ".json":
                json.load(f)
            elif suffix in {".yaml", ".yml"}:
                yaml.safe_load(f)
            else:
                _ = f.read(1)
        return True
    except Exception:
        return False


def rerun_boundary(blocker_id: str) -> str:
    if blocker_id.startswith("PR2.B0") or blocker_id.startswith("PR2.B01") or blocker_id.startswith("PR2.B02") or blocker_id.startswith("PR2.B03") or blocker_id.startswith("PR2.B04"):
        return "S0"
    if blocker_id.startswith("PR2.B05") or blocker_id.startswith("PR2.B06") or blocker_id.startswith("PR2.B07") or blocker_id.startswith("PR2.B08") or blocker_id.startswith("PR2.B09"):
        return "S1"
    if blocker_id.startswith("PR2.B10") or blocker_id.startswith("PR2.B11") or blocker_id.startswith("PR2.B12") or blocker_id.startswith("PR2.B13") or blocker_id.startswith("PR2.B14"):
        return "S2"
    return "S3"


def owner_lane(blocker_id: str) -> str:
    if blocker_id.startswith("PR2.B1"):
        return "run_control_pr2"
    if blocker_id.startswith("PR2.B0"):
        return "run_control_pr2"
    return "run_control_pr2"


def summary_schema_ok(summary: Dict[str, Any]) -> bool:
    required = {"verdict", "next_gate", "open_blockers", "blocker_ids", "contract_refs"}
    if not required.issubset(summary.keys()):
        return False
    if not isinstance(summary.get("contract_refs"), dict):
        return False
    if not isinstance(summary.get("blocker_ids"), list):
        return False
    return True


def activation_index_ok(index_payload: Dict[str, Any]) -> bool:
    required = {"phase", "state", "generated_at_utc", "generated_by", "version", "execution_id", "contract_refs", "validator_status"}
    if not required.issubset(index_payload.keys()):
        return False
    if not isinstance(index_payload.get("contract_refs"), dict):
        return False
    if not isinstance(index_payload.get("validator_status"), dict):
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute PR2-S3 activation rollup and verdict emission.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr2-execution-id", default="")
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    t0 = time.perf_counter()
    ts = now_utc()

    root = Path(args.run_control_root)
    if not root.exists():
        raise RuntimeError(f"Missing run-control root: {root}")

    execution_id = args.pr2_execution_id.strip() or str(load_json(root / "pr2_latest.json").get("execution_id", "")).strip()
    if not execution_id:
        raise RuntimeError("Unable to resolve PR2 execution id")
    run_root = root / execution_id

    s2 = load_json(run_root / "pr2_s2_execution_receipt.json")
    if str(s2.get("verdict")) != "PR2_S2_READY" or int(s2.get("open_blockers", 1)) != 0:
        raise RuntimeError("Upstream lock failed: PR2-S2 not READY")

    s0 = load_json(run_root / "pr2_s0_execution_receipt.json")
    s1 = load_json(run_root / "pr2_s1_execution_receipt.json")
    matrix = load_json(run_root / "pr2_activation_validation_matrix.json")
    runtime_validator = load_json(run_root / "pr2_runtime_contract_validator.json")
    opsgov_validator = load_json(run_root / "pr2_opsgov_contract_validator.json")
    threshold_sanity = load_json(run_root / "pr2_threshold_sanity_report.json")
    entry_lock = load_json(run_root / "pr2_entry_lock.json")

    contract_refs = {
        "runtime_contract": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_runtime_numeric_contract.rc2s.active.yaml",
        "opsgov_contract": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_opsgov_numeric_contract.rc2s.active.yaml",
        "runtime_validator": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_runtime_contract_validator.json",
        "opsgov_validator": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_opsgov_contract_validator.json",
        "threshold_sanity": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_threshold_sanity_report.json",
        "activation_matrix": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_activation_validation_matrix.json",
    }

    activation_index = {
        "phase": "PR2",
        "state": "S3",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "status": "ACTIVE",
        "upstream": {
            "entry_lock_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_entry_lock.json",
            "upstream_pr1_execution_id": str(entry_lock.get("upstream", {}).get("pr1_execution_id", "")),
            "state_receipts": {
                "S0": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_s0_execution_receipt.json",
                "S1": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_s1_execution_receipt.json",
                "S2": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_s2_execution_receipt.json",
            },
        },
        "contract_refs": contract_refs,
        "validator_status": {
            "runtime_contract_activatable": bool(runtime_validator.get("overall_valid")),
            "opsgov_contract_activatable": bool(opsgov_validator.get("overall_valid")),
            "threshold_sanity_pass": bool(threshold_sanity.get("overall_pass")),
            "anti_gaming_pass": bool(threshold_sanity.get("anti_gaming", {}).get("overall_pass")),
            "matrix_pass": bool(matrix.get("overall_pass")),
        },
    }

    upstream_blockers: List[Dict[str, Any]] = []
    for state_id, receipt in [("S0", s0), ("S1", s1), ("S2", s2)]:
        for bid in receipt.get("blocker_ids", []):
            upstream_blockers.append(
                {
                    "id": str(bid),
                    "severity": "CRITICAL",
                    "reason": f"Upstream {state_id} receipt reports open blocker.",
                    "owner": owner_lane(str(bid)),
                    "rerun_boundary": rerun_boundary(str(bid)),
                    "source_receipt": f"pr2_{state_id.lower()}_execution_receipt.json",
                }
            )

    blocker_ids = sorted({b["id"] for b in upstream_blockers})

    attributable_spend_usd = 0.0
    open_blockers = len(blocker_ids)
    verdict = "PR3_READY" if open_blockers == 0 else "HOLD_REMEDIATE"
    next_gate = "PR3_READY" if open_blockers == 0 else "PR2_REMEDIATE"

    execution_summary = {
        "phase": "PR2",
        "state": "S3",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "verdict": verdict,
        "next_gate": next_gate,
        "open_blockers": open_blockers,
        "blocker_ids": blocker_ids,
        "contract_refs": contract_refs,
        "state_refs": {
            "s0_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_s0_execution_receipt.json",
            "s1_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_s1_execution_receipt.json",
            "s2_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_s2_execution_receipt.json",
        },
        "attributable_spend_usd": attributable_spend_usd,
        "cost_envelope_usd": 5.0,
    }

    required_artifacts = [
        "pr2_entry_lock.json",
        "pr2_required_row_inventory.json",
        "pr2_gap_map.json",
        "pr2_runtime_numeric_contract.rc2s.active.yaml",
        "pr2_opsgov_numeric_contract.rc2s.active.yaml",
        "pr2_threshold_population_ledger.json",
        "pr2_calibration_traceability.json",
        "pr2_deferred_scope_register.json",
        "pr2_runtime_contract_validator.json",
        "pr2_opsgov_contract_validator.json",
        "pr2_threshold_sanity_report.json",
        "pr2_activation_validation_matrix.json",
        "pr2_numeric_contract_activation_index.json",
        "pr2_blocker_register.json",
        "pr2_execution_summary.json",
        "pr2_evidence_index.json",
        "pr2_s0_execution_receipt.json",
        "pr2_s1_execution_receipt.json",
        "pr2_s2_execution_receipt.json",
        "pr2_s3_execution_receipt.json",
    ]

    blocker_register = {
        "phase": "PR2",
        "state": "S3",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "open_blockers": upstream_blockers,
        "open_blocker_count": len(upstream_blockers),
    }

    dump_json(run_root / "pr2_numeric_contract_activation_index.json", activation_index)
    dump_json(run_root / "pr2_blocker_register.json", blocker_register)
    dump_json(run_root / "pr2_execution_summary.json", execution_summary)

    b15 = (run_root / "pr2_numeric_contract_activation_index.json").exists() and activation_index_ok(load_json(run_root / "pr2_numeric_contract_activation_index.json"))
    b16 = (run_root / "pr2_execution_summary.json").exists() and summary_schema_ok(load_json(run_root / "pr2_execution_summary.json"))
    b19 = isinstance(execution_summary.get("attributable_spend_usd"), (int, float)) and float(execution_summary.get("attributable_spend_usd")) >= 0.0

    blocker_ids_final = list(blocker_ids)
    if not b15:
        blocker_ids_final.append("PR2.B15_ACTIVATION_INDEX_MISSING")
    if not b16:
        blocker_ids_final.append("PR2.B16_SUMMARY_MISSING")
    if not b19:
        blocker_ids_final.append("PR2.B19_UNATTRIBUTED_SPEND")

    if len(blocker_ids_final) > 0:
        blocker_ids_final.append("PR2.B17_OPEN_BLOCKERS_NONZERO")

    blocker_ids_final = sorted(set(blocker_ids_final))
    open_blockers_final = len(blocker_ids_final)
    verdict_final = "PR3_READY" if open_blockers_final == 0 else "HOLD_REMEDIATE"
    next_gate_final = "PR3_READY" if open_blockers_final == 0 else "PR2_REMEDIATE"

    b18 = not (open_blockers_final == 0 and (verdict_final != "PR3_READY" or next_gate_final != "PR3_READY"))
    if not b18:
        blocker_ids_final = sorted(set(blocker_ids_final + ["PR2.B18_VERDICT_NOT_PR3_READY"]))
        open_blockers_final = len(blocker_ids_final)
        verdict_final = "HOLD_REMEDIATE"
        next_gate_final = "PR2_REMEDIATE"

    blocker_register_final = {
        "phase": "PR2",
        "state": "S3",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "open_blockers": [
            {
                "id": bid,
                "severity": "CRITICAL",
                "reason": "PR2 S3 fail-closed blocker.",
                "owner": owner_lane(bid),
                "rerun_boundary": rerun_boundary(bid),
            }
            for bid in blocker_ids_final
        ],
        "open_blocker_count": open_blockers_final,
    }

    execution_summary_final = {
        **execution_summary,
        "verdict": verdict_final,
        "next_gate": next_gate_final,
        "open_blockers": open_blockers_final,
        "blocker_ids": blocker_ids_final,
    }

    dump_json(run_root / "pr2_blocker_register.json", blocker_register_final)
    dump_json(run_root / "pr2_execution_summary.json", execution_summary_final)

    elapsed_minutes = round((time.perf_counter() - t0) / 60.0, 3)
    receipt = {
        "phase": "PR2",
        "state": "S3",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "verdict": "PR2_S3_READY" if open_blockers_final == 0 else "HOLD_REMEDIATE",
        "next_state": "PR3-S0" if open_blockers_final == 0 else "PR2-S3",
        "next_gate": next_gate_final,
        "open_blockers": open_blockers_final,
        "blocker_ids": blocker_ids_final,
        "checks": {
            "B15_activation_index_present": b15,
            "B16_summary_present": b16,
            "B17_open_blockers_zero": open_blockers_final == 0,
            "B18_verdict_pr3_ready": verdict_final == "PR3_READY" and next_gate_final == "PR3_READY",
            "B19_attributable_spend_present": b19,
        },
        "outputs": [
            "pr2_numeric_contract_activation_index.json",
            "pr2_blocker_register.json",
            "pr2_execution_summary.json",
            "pr2_evidence_index.json",
        ],
        "elapsed_minutes": elapsed_minutes,
        "runtime_budget_minutes": 10,
        "attributable_spend_usd": attributable_spend_usd,
        "cost_envelope_usd": 5.0,
        "advisory_ids": ["PR2.S2.AD01_BURST_GAP_EXPLICITLY_ROUTED_TO_PR3"],
    }

    dump_json(run_root / "pr2_s3_execution_receipt.json", receipt)

    evidence_records: List[Dict[str, Any]] = []
    for name in required_artifacts:
        p = run_root / name
        evidence_records.append(
            {
                "artifact": name,
                "path": str(p).replace("\\", "/"),
                "exists": p.exists(),
                "readable": is_readable(p),
            }
        )

    evidence_index = {
        "phase": "PR2",
        "state": "S3",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "required_artifacts": evidence_records,
        "missing_required": [r["artifact"] for r in evidence_records if not r["exists"]],
        "unreadable_required": [r["artifact"] for r in evidence_records if r["exists"] and not r["readable"]],
    }
    dump_json(run_root / "pr2_evidence_index.json", evidence_index)

    # Recompute once after writing index so the self-entry reflects actual on-disk state.
    evidence_records_final: List[Dict[str, Any]] = []
    for name in required_artifacts:
        p = run_root / name
        evidence_records_final.append(
            {
                "artifact": name,
                "path": str(p).replace("\\", "/"),
                "exists": p.exists(),
                "readable": is_readable(p),
            }
        )
    evidence_index_final = {
        **evidence_index,
        "required_artifacts": evidence_records_final,
        "missing_required": [r["artifact"] for r in evidence_records_final if not r["exists"]],
        "unreadable_required": [r["artifact"] for r in evidence_records_final if r["exists"] and not r["readable"]],
    }
    dump_json(run_root / "pr2_evidence_index.json", evidence_index_final)
    dump_json(
        root / "pr2_latest.json",
        {
            "phase": "PR2",
            "execution_id": execution_id,
            "latest_state": "S3",
            "latest_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_s3_execution_receipt.json",
            "updated_at_utc": now_utc(),
        },
    )

    print(
        json.dumps(
            {
                "execution_id": execution_id,
                "state": "S3",
                "verdict": receipt["verdict"],
                "next_state": receipt["next_state"],
                "next_gate": receipt["next_gate"],
                "open_blockers": receipt["open_blockers"],
                "blocker_ids": receipt["blocker_ids"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
