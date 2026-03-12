#!/usr/bin/env python3
"""Emit the coupled Phase 6 proof for governed bundle resolution on the promoted runtime path."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fraud_detection.decision_fabric.posture import DfPostureStamp  # noqa: E402
from fraud_detection.decision_fabric.registry import (  # noqa: E402
    RESOLUTION_RESOLVED,
    RegistryResolutionPolicy,
    RegistryResolver,
    RegistryScopeKey,
    RegistrySnapshot,
)
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, PolicyRev  # noqa: E402


SNAPSHOT_PATH = Path("config/platform/df/registry_snapshot_dev_full_v0.yaml")
POLICY_PATH = Path("config/platform/df/registry_resolution_policy_v0.yaml")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def resolve_scope(
    resolver: RegistryResolver,
    *,
    mode: str,
    posture: DfPostureStamp,
    feature_group_versions: dict[str, str],
) -> dict[str, Any]:
    result = resolver.resolve(
        scope_key=RegistryScopeKey(environment="dev_full", mode=mode, bundle_slot="primary"),
        posture=posture,
        feature_group_versions=feature_group_versions,
    )
    return result.as_dict()


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit coupled Phase 6 learning/runtime proof.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--source-execution-id", required=True)
    ap.add_argument("--phase5b-execution-id", required=True)
    ap.add_argument("--source-receipt-name", default="phase4_coupled_readiness_receipt.json")
    ap.add_argument("--phase5b-receipt-name", default="phase5_learning_bound_receipt.json")
    ap.add_argument("--phase5b-summary-name", default="phase5_learning_bound_summary.json")
    ap.add_argument("--summary-name", default="phase6_learning_coupled_summary.json")
    ap.add_argument("--receipt-name", default="phase6_learning_coupled_receipt.json")
    args = ap.parse_args()

    run_root = Path(args.run_control_root) / args.execution_id
    source_root = Path(args.run_control_root) / args.source_execution_id
    phase5b_root = Path(args.run_control_root) / args.phase5b_execution_id

    phase4_receipt = load_json(source_root / str(args.source_receipt_name).strip())
    phase5b_receipt = load_json(phase5b_root / str(args.phase5b_receipt_name).strip())
    phase5b_summary = load_json(phase5b_root / str(args.phase5b_summary_name).strip())

    blockers: list[str] = []
    notes: list[str] = []

    if str(phase4_receipt.get("verdict") or "").strip().upper() != "PHASE4_READY":
        blockers.append("PHASE6.A01_SOURCE_PHASE4_NOT_GREEN")
    if str(phase5b_receipt.get("verdict") or "").strip().upper() != "PHASE5_READY":
        blockers.append("PHASE6.A02_PHASE5_NOT_GREEN")

    snapshot = RegistrySnapshot.load(SNAPSHOT_PATH)
    policy = RegistryResolutionPolicy.load(POLICY_PATH)
    resolver = RegistryResolver(policy=policy, snapshot=snapshot)

    policy_rev = PolicyRev(
        policy_id=policy.policy_rev.policy_id,
        revision=policy.policy_rev.revision,
        content_digest=policy.policy_rev.content_digest,
    )
    capabilities_mask = CapabilitiesMask(
        allow_ieg=False,
        allowed_feature_groups=("core_features",),
        allow_model_primary=True,
        allow_model_stage2=False,
        allow_fallback_heuristics=True,
        action_posture="STEP_UP_ONLY",
    )
    decided_at = now_utc()
    posture = DfPostureStamp(
        scope_key="dev_full|runtime|primary|",
        mode="NORMAL",
        capabilities_mask=capabilities_mask,
        policy_rev=policy_rev,
        posture_seq=1,
        decided_at_utc=decided_at,
        source="phase6_learning_coupled_readiness",
        trust_state="TRUSTED",
        served_at_utc=decided_at,
        reasons=("PHASE6_RUNTIME_GOVERNED_RESOLUTION",),
    )

    feature_group_versions = {"core_features": "v1"}
    fraud_result = resolve_scope(resolver, mode="fraud", posture=posture, feature_group_versions=feature_group_versions)
    baseline_result = resolve_scope(
        resolver,
        mode="baseline",
        posture=posture,
        feature_group_versions=feature_group_versions,
    )
    if str(fraud_result.get("outcome") or "").strip().upper() != RESOLUTION_RESOLVED:
        blockers.append("PHASE6.A03_FRAUD_SCOPE_NOT_RESOLVED")
    if str(baseline_result.get("outcome") or "").strip().upper() != RESOLUTION_RESOLVED:
        blockers.append("PHASE6.A04_BASELINE_SCOPE_NOT_RESOLVED")

    phase5_candidate_bundle_ref = str(
        ((((phase5b_summary.get("managed_corridor") or {}).get("candidate_bundle_ref")) or ""))
    ).strip()
    if not phase5_candidate_bundle_ref:
        blockers.append("PHASE6.A05_PHASE5_CANDIDATE_BUNDLE_UNRESOLVED")

    snapshot_refs = {
        "fraud": str((((fraud_result.get("bundle_ref") or {})).get("registry_ref")) or "").strip(),
        "baseline": str((((baseline_result.get("bundle_ref") or {})).get("registry_ref")) or "").strip(),
    }
    if snapshot_refs["fraud"] and phase5_candidate_bundle_ref and snapshot_refs["fraud"] != phase5_candidate_bundle_ref:
        blockers.append("PHASE6.A06_FRAUD_SCOPE_BUNDLE_REF_DRIFT")
    if snapshot_refs["baseline"] and phase5_candidate_bundle_ref and snapshot_refs["baseline"] != phase5_candidate_bundle_ref:
        blockers.append("PHASE6.A07_BASELINE_SCOPE_BUNDLE_REF_DRIFT")

    explicit_fallbacks = policy.explicit_fallback_by_scope
    if explicit_fallbacks.get("dev_full|fraud|primary|", {}).get("registry_ref") != phase5_candidate_bundle_ref:
        blockers.append("PHASE6.A08_POLICY_FRAUD_FALLBACK_DRIFT")
    if explicit_fallbacks.get("dev_full|baseline|primary|", {}).get("registry_ref") != phase5_candidate_bundle_ref:
        blockers.append("PHASE6.A09_POLICY_BASELINE_FALLBACK_DRIFT")

    m12f_runtime_ok = bool(
        ((((phase5b_summary.get("managed_corridor") or {}).get("artifacts") or {}).get("m12f") or {}).get("overall_pass"))
    )
    if not m12f_runtime_ok:
        blockers.append("PHASE6.A10_M12F_CHAIN_NOT_GREEN")
    else:
        notes.append("Runtime DF registry resolution stays aligned with the governed active bundle truth proven on the managed learning corridor.")

    summary = {
        "phase": "PHASE6",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_execution_id": args.source_execution_id,
        "phase5b_execution_id": args.phase5b_execution_id,
        "platform_run_id": str(phase4_receipt.get("platform_run_id") or "").strip(),
        "posture_stamp": posture.as_dict(),
        "feature_group_versions": feature_group_versions,
        "policy_rev": policy.policy_rev.as_dict(),
        "snapshot_digest": snapshot.snapshot_digest,
        "fraud_resolution": fraud_result,
        "baseline_resolution": baseline_result,
        "phase5_candidate_bundle_ref": phase5_candidate_bundle_ref,
        "policy_explicit_fallbacks": explicit_fallbacks,
        "notes": notes,
        "blocker_ids": blockers,
        "open_blockers": len(blockers),
        "overall_pass": len(blockers) == 0,
    }
    receipt = {
        "phase": "PHASE6",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "platform_run_id": summary["platform_run_id"],
        "verdict": "PHASE6_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_phase": "PHASE7" if len(blockers) == 0 else "PHASE6_REMEDIATE",
        "open_blockers": len(blockers),
        "blocker_ids": blockers,
    }

    dump_json(run_root / str(args.summary_name).strip(), summary)
    dump_json(run_root / str(args.receipt_name).strip(), receipt)


if __name__ == "__main__":
    main()
