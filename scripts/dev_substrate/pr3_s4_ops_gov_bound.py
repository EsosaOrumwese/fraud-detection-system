#!/usr/bin/env python3
"""Emit bounded ops/governance proof for PR3-S4 on the active run scope."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fraud_detection.platform_conformance.checker import run_environment_conformance
from fraud_detection.scenario_runner.storage import build_object_store


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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

        os.environ["PLATFORM_RUN_ID"] = args.platform_run_id
        os.environ["ACTIVE_PLATFORM_RUN_ID"] = args.platform_run_id
        local_obs_dir = Path("runs/fraud-platform") / args.platform_run_id / "obs"
        local_obs_dir.mkdir(parents=True, exist_ok=True)
        local_conformance_path = local_obs_dir / "environment_conformance.json"
        conformance = run_environment_conformance(
            local_parity_profile="config/platform/profiles/local_parity.yaml",
            dev_profile="config/platform/profiles/dev.yaml",
            prod_profile="config/platform/profiles/prod.yaml",
            platform_run_id=args.platform_run_id,
            output_path=str(local_conformance_path),
        )
        if str(conformance.status).upper() != "PASS":
            raise RuntimeError("PR3.B30_OPS_GOV_BOUND_FAIL:ENVIRONMENT_CONFORMANCE_FAIL")

        facts_ref = ensure_s3_ref(str(((bootstrap.get("sr") or {}).get("facts_view_ref")) or ""), object_store_root)
        status_ref = ensure_s3_ref(str(((bootstrap.get("sr") or {}).get("status_ref")) or ""), object_store_root)
        facts_payload = store.read_json(relative_path(facts_ref, object_store_root))
        status_payload = store.read_json(relative_path(status_ref, object_store_root))
        if str(status_payload.get("state") or "").strip().upper() != "READY":
            raise RuntimeError(f"PR3.B30_OPS_GOV_BOUND_FAIL:SR_STATUS_NOT_READY:{status_payload.get('state')}")

        required_prefixes = {
            "sr": f"{args.platform_run_id}/sr/",
            "ig": f"{args.platform_run_id}/ig/",
            "archive": f"{args.platform_run_id}/archive/",
            "online_feature_plane": f"{args.platform_run_id}/online_feature_plane/",
        }
        prefix_counts: dict[str, int] = {}
        for name, prefix in required_prefixes.items():
            count = len(store.list_files(prefix))
            prefix_counts[name] = count
            if count <= 0:
                raise RuntimeError(f"PR3.B30_OPS_GOV_BOUND_FAIL:MISSING_RUN_ROOT:{name}")

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
            "environment_conformance_ref": f"{object_store_root}/{args.platform_run_id}/obs/environment_conformance.json",
        }
        store.write_json(f"{args.platform_run_id}/obs/environment_conformance.json", conformance.payload)
        store.write_json(f"{args.platform_run_id}/obs/governance_closure_receipt.json", governance_receipt)
        notes.append("Ops/gov bounded proof is direct for run-scoped control continuity and observability roots; broader PR4 governance drills remain separate.")

        summary = {
            "phase": "PR3",
            "state": "S4",
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": args.platform_run_id,
            "overall_pass": True,
            "blocker_ids": [],
            "impact_metrics": {
                "environment_conformance_status": conformance.status,
                "observability_roots_present": sum(1 for count in prefix_counts.values() if count > 0),
                "observability_root_total": len(prefix_counts),
                "sr_status_state": str(status_payload.get("state") or ""),
            },
            "refs": {
                "environment_conformance_local_path": str(local_conformance_path),
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
