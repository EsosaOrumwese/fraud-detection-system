#!/usr/bin/env python3
"""Emit bounded ops/governance proof for PR3-S4 on the active run scope."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fraud_detection.scenario_runner.storage import build_object_store


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict[str, Any] | None:
    return load_json(path) if path.exists() else None


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_registry(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    pattern = re.compile(r"^\*\s*`([^`]+)`")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw_line.strip())
        if not match:
            continue
        body = match.group(1)
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        payload[key.strip()] = value.strip().strip('"')
    return payload


def ensure_s3_ref(ref: str, object_store_root: str) -> str:
    value = str(ref or "").strip()
    if value.startswith("s3://"):
        return value
    if not value:
        return value
    return f"{object_store_root.rstrip('/')}/{value.lstrip('/')}"


def relative_path(ref: str, object_store_root: str) -> str:
    normalized = ensure_s3_ref(ref, object_store_root)
    root = object_store_root.rstrip("/") + "/"
    if normalized.startswith(root):
        return normalized[len(root) :]
    parsed = urlparse(normalized)
    return parsed.path.lstrip("/")


def read_store_json_ref(store: Any, *, ref: str, object_store_root: str, blocker_prefix: str) -> dict[str, Any]:
    normalized = ensure_s3_ref(ref, object_store_root)
    if not normalized:
        raise RuntimeError(f"{blocker_prefix}:REF_EMPTY")
    return store.read_json(relative_path(normalized, object_store_root))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr3-execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    parser.add_argument("--summary-name", default="g3a_correctness_ops_gov_summary.json")
    args = parser.parse_args()

    run_root = Path(args.run_control_root) / args.pr3_execution_id
    summary_path = run_root / args.summary_name
    blockers: list[str] = []
    notes: list[str] = []

    try:
        registry = parse_registry(REGISTRY_PATH)
        object_store_root = f"s3://{str(registry['S3_OBJECT_STORE_BUCKET']).strip()}"
        store = build_object_store(object_store_root, s3_region=str(registry.get("AWS_REGION", "eu-west-2")).strip(), s3_path_style=False)
        bootstrap = load_json(run_root / "g3a_control_plane_bootstrap.json")
        if not bool(bootstrap.get("overall_pass")):
            raise RuntimeError("PR3.B30_OPS_GOV_BOUND_FAIL:CONTROL_BOOTSTRAP_NOT_GREEN")

        facts_ref = ensure_s3_ref(str(((bootstrap.get("sr") or {}).get("facts_view_ref")) or ""), object_store_root)
        status_ref = ensure_s3_ref(str(((bootstrap.get("sr") or {}).get("status_ref")) or ""), object_store_root)
        facts_payload = read_store_json_ref(
            store,
            ref=facts_ref,
            object_store_root=object_store_root,
            blocker_prefix="PR3.B30_OPS_GOV_BOUND_FAIL:FACTS_VIEW",
        )
        status_payload = read_store_json_ref(
            store,
            ref=status_ref,
            object_store_root=object_store_root,
            blocker_prefix="PR3.B30_OPS_GOV_BOUND_FAIL:STATUS_VIEW",
        )
        if str(status_payload.get("state") or "").strip().upper() != "READY":
            raise RuntimeError(f"PR3.B30_OPS_GOV_BOUND_FAIL:SR_STATUS_NOT_READY:{status_payload.get('state')}")

        learning_summary = load_optional_json(run_root / "g3a_correctness_learning_summary.json")
        if not learning_summary or not bool(learning_summary.get("overall_pass")):
            raise RuntimeError("PR3.B30_OPS_GOV_BOUND_FAIL:LEARNING_PROOF_NOT_GREEN")

        snapshots = sorted(
            [
                load_json(path)
                for path in run_root.glob("g3a_s4_component_snapshot_*.json")
                if str(load_json(path).get("platform_run_id") or "").strip() == args.platform_run_id
            ],
            key=lambda row: str(row.get("generated_at_utc", "")),
        )
        snapshot_labels = {str(row.get("snapshot_label") or "").strip().lower() for row in snapshots}
        if not {"pre", "post"}.issubset(snapshot_labels):
            raise RuntimeError("PR3.B30_OPS_GOV_BOUND_FAIL:CASE_LABEL_SNAPSHOTS_INCOMPLETE")
        latest_snapshot = snapshots[-1]
        for component in ("case_trigger", "case_mgmt", "label_store"):
            if not isinstance((latest_snapshot.get("components") or {}).get(component), dict):
                raise RuntimeError(f"PR3.B30_OPS_GOV_BOUND_FAIL:CASE_LABEL_COMPONENT_MISSING:{component}")

        required_prefixes = {
            "sr": f"{args.platform_run_id}/sr/",
            "ig": f"{args.platform_run_id}/ig/",
            "archive": f"{args.platform_run_id}/archive/",
            "online_feature_plane": f"{args.platform_run_id}/online_feature_plane/",
            "ofs": f"{args.platform_run_id}/ofs/",
            "mf": f"{args.platform_run_id}/mf/",
            "obs": f"{args.platform_run_id}/obs/",
        }
        prefix_counts: dict[str, int] = {}
        for name, prefix in required_prefixes.items():
            count = len(store.list_files(prefix))
            prefix_counts[name] = count
            if count <= 0:
                raise RuntimeError(f"PR3.B30_OPS_GOV_BOUND_FAIL:MISSING_RUN_ROOT:{name}")

        learning_refs = {
            "ofs_manifest_ref": str(((learning_summary.get("refs") or {}).get("ofs_manifest_ref")) or "").strip(),
            "mf_eval_report_ref": str(((learning_summary.get("refs") or {}).get("mf_eval_report_ref")) or "").strip(),
            "mf_gate_receipt_ref": str(((learning_summary.get("refs") or {}).get("mf_gate_receipt_ref")) or "").strip(),
            "mf_bundle_publication_ref": str(((learning_summary.get("refs") or {}).get("mf_bundle_publication_ref")) or "").strip(),
            "mf_registry_lifecycle_event_ref": str(((learning_summary.get("refs") or {}).get("mf_registry_lifecycle_event_ref")) or "").strip(),
        }
        readable_learning_refs: dict[str, str] = {}
        for key, ref in learning_refs.items():
            read_store_json_ref(
                store,
                ref=ref,
                object_store_root=object_store_root,
                blocker_prefix=f"PR3.B30_OPS_GOV_BOUND_FAIL:{key.upper()}",
            )
            readable_learning_refs[key] = ensure_s3_ref(ref, object_store_root)

        observability_payload = {
            "generated_at_utc": now_utc(),
            "platform_run_id": args.platform_run_id,
            "mode": "pr3_s4_dev_full_whole_platform_observability",
            "status": "PASS",
            "checks": [
                {"check_id": "sr_control_continuity", "status": "PASS"},
                {"check_id": "required_run_roots_present", "status": "PASS", "details": {"counts": prefix_counts}},
                {"check_id": "case_label_snapshot_coverage", "status": "PASS", "details": {"snapshot_labels": sorted(snapshot_labels)}},
                {
                    "check_id": "learning_ref_readback",
                    "status": "PASS",
                    "details": {"refs": readable_learning_refs},
                },
            ],
            "profiles": {"active_track": "dev_full", "proof_mode": "same_run_whole_platform"},
        }

        governance_receipt = {
            "generated_at_utc": now_utc(),
            "platform_run_id": args.platform_run_id,
            "status": "PASS",
            "control_continuity": {
                "status_ref": status_ref,
                "facts_view_ref": facts_ref,
                "scenario_run_id": str(facts_payload.get("run_id") or ""),
                "status_state": str(status_payload.get("state") or ""),
            },
            "runtime_root_counts": prefix_counts,
            "case_label_snapshot_labels": sorted(snapshot_labels),
            "case_label_components_present": ["case_trigger", "case_mgmt", "label_store"],
            "learning_refs": readable_learning_refs,
            "environment_conformance_ref": f"{object_store_root}/{args.platform_run_id}/obs/environment_conformance.json",
        }
        store.write_json(f"{args.platform_run_id}/obs/environment_conformance.json", observability_payload)
        store.write_json(f"{args.platform_run_id}/obs/governance_closure_receipt.json", governance_receipt)
        notes.append(
            "Ops/gov bounded proof is now scored against same-run dev_full whole-platform evidence continuity rather than static local_parity/dev/prod profile parity."
        )
        notes.append(
            "This remains a bounded S4 proof only; broader PR4 promotion/governance drills remain separate."
        )

        summary = {
            "phase": "PR3",
            "state": "S4",
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": args.platform_run_id,
            "overall_pass": True,
            "blocker_ids": [],
            "impact_metrics": {
                "required_run_roots_present": sum(1 for count in prefix_counts.values() if count > 0),
                "required_run_root_total": len(prefix_counts),
                "learning_refs_readable": len(readable_learning_refs),
                "learning_ref_total": len(learning_refs),
                "case_label_snapshot_labels_present": len(snapshot_labels),
                "sr_status_state": str(status_payload.get("state") or ""),
            },
            "assessment": (
                "Meets the bounded PR3-S4 ops/gov goal: same-run control continuity, whole-platform observability roots, "
                "case/label snapshot coverage, and learning-evolution readbacks are all present on dev_full."
            ),
            "refs": {
                "environment_conformance_ref": f"{object_store_root}/{args.platform_run_id}/obs/environment_conformance.json",
                "governance_closure_receipt_ref": f"{object_store_root}/{args.platform_run_id}/obs/governance_closure_receipt.json",
                "facts_view_ref": facts_ref,
                "status_ref": status_ref,
            },
            "runtime_root_counts": prefix_counts,
            "notes": notes,
        }
    except Exception as exc:  # noqa: BLE001
        blockers.append(str(exc))
        summary = {
            "phase": "PR3",
            "state": "S4",
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": args.platform_run_id,
            "overall_pass": False,
            "blocker_ids": blockers,
            "notes": notes,
            "error": str(exc),
        }
        dump_json(summary_path, summary)
        raise SystemExit(1)

    dump_json(summary_path, summary)


if __name__ == "__main__":
    main()
