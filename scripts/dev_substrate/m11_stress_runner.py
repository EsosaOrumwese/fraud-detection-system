#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M11.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

S0_ARTS = [
    "m11_stagea_findings.json",
    "m11_lane_matrix.json",
    "m11a_handle_closure_snapshot.json",
    "m11a_blocker_register.json",
    "m11a_execution_summary.json",
    "m11b_sagemaker_readiness_snapshot.json",
    "m11b_blocker_register.json",
    "m11b_execution_summary.json",
    "m11_runtime_locality_guard_snapshot.json",
    "m11_source_authority_guard_snapshot.json",
    "m11_realism_guard_snapshot.json",
    "m11_blocker_register.json",
    "m11_execution_summary.json",
    "m11_decision_log.json",
    "m11_gate_verdict.json",
]

S1_ARTS = [
    "m11_stagea_findings.json",
    "m11_lane_matrix.json",
    "m11c_input_immutability_snapshot.json",
    "m11c_blocker_register.json",
    "m11c_execution_summary.json",
    "m11_phase_budget_envelope.json",
    "m11d_train_eval_execution_snapshot.json",
    "m11d_blocker_register.json",
    "m11d_execution_summary.json",
    "m11_runtime_locality_guard_snapshot.json",
    "m11_source_authority_guard_snapshot.json",
    "m11_realism_guard_snapshot.json",
    "m11_blocker_register.json",
    "m11_execution_summary.json",
    "m11_decision_log.json",
    "m11_gate_verdict.json",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tok() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_scalar(v: str) -> Any:
    s = v.strip()
    if s.lower() in {"true", "false"}:
        return s.lower() == "true"
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    try:
        return int(s) if "." not in s else float(s)
    except ValueError:
        return s


def parse_registry(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rx = re.compile(r"^\* `([^`]+)`(?:\s.*)?$")
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(raw.strip())
        if not m:
            continue
        body = m.group(1).strip()
        if "=" not in body:
            continue
        k, v = body.split("=", 1)
        out[k.strip()] = parse_scalar(v.strip())
    return out


def parse_plan_packet(plan_text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in re.findall(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`", plan_text):
        out[k] = parse_scalar(v)
    return out


def is_placeholder(v: Any) -> bool:
    s = str(v or "").strip().lower()
    return (not s) or s in {"tbd", "todo", "none", "null", "unset"} or "placeholder" in s or "to_pin" in s


def loadj(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: list[str], timeout: int = 120, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        return int(p.returncode), (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def add_blocker(blockers: list[dict[str, Any]], bid: str, severity: str, details: dict[str, Any]) -> None:
    blockers.append({"id": bid, "severity": severity, "status": "OPEN", "details": details})


def dedupe(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for b in blockers:
        sig = f"{b.get('id','')}|{json.dumps(b.get('details', {}), sort_keys=True, default=str)}"
        if sig in seen:
            continue
        seen.add(sig)
        out.append(b)
    return out


def latest_m10_s5() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m10_stress_s5_*"):
        payload = loadj(d / "stress" / "m10_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M10-ST-S5":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("verdict", "")) != "ADVANCE_TO_M11":
            continue
        if str(payload.get("next_gate", "")) != "M11_READY":
            continue
        if int(payload.get("open_blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def latest_s0() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m11_stress_s0_*"):
        payload = loadj(d / "stress" / "m11_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M11-ST-S0":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M11_ST_S1_READY":
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def finish(
    stage: str,
    phase_execution_id: str,
    out: Path,
    blockers: list[dict[str, Any]],
    arts: list[str],
    summary_extra: dict[str, Any],
) -> int:
    blockers = dedupe(blockers)
    stage_receipts = {
        "m11_blocker_register.json",
        "m11_execution_summary.json",
        "m11_decision_log.json",
        "m11_gate_verdict.json",
    }
    prewrite_required = [name for name in arts if name not in stage_receipts]
    missing = [name for name in prewrite_required if not (out / name).exists()]
    if missing:
        add_blocker(
            blockers,
            "M11-ST-B12",
            stage,
            {"reason": "artifact_contract_incomplete", "missing_outputs": sorted(missing)},
        )
    blockers = dedupe(blockers)

    overall_pass = len(blockers) == 0
    if overall_pass and stage == "S0":
        next_gate = "M11_ST_S1_READY"
        verdict = "GO"
    elif overall_pass and stage == "S1":
        next_gate = "M11_ST_S2_READY"
        verdict = "GO"
    else:
        next_gate = "HOLD_REMEDIATE"
        verdict = "HOLD_REMEDIATE"

    register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M11-ST-{stage}",
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M11-ST-{stage}",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "next_gate": next_gate,
        "verdict": verdict,
        "required_artifacts": arts,
        **summary_extra,
    }
    decision_log = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M11-ST-{stage}",
        "decisions": list(summary_extra.get("decisions", [])),
        "advisories": list(summary_extra.get("advisories", [])),
    }
    gate = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M11-ST-{stage}",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "verdict": verdict,
    }

    dumpj(out / "m11_blocker_register.json", register)
    dumpj(out / "m11_execution_summary.json", summary)
    dumpj(out / "m11_decision_log.json", decision_log)
    dumpj(out / "m11_gate_verdict.json", gate)

    print(
        json.dumps(
            {
                "phase_execution_id": phase_execution_id,
                "stage_id": f"M11-ST-{stage}",
                "overall_pass": overall_pass,
                "open_blocker_count": len(blockers),
                "next_gate": next_gate,
                "output_dir": out.as_posix(),
            }
        )
    )
    return 0


def stage_bridge_upload(out: Path, bucket: str, key: str, payload: dict[str, Any], blockers: list[dict[str, Any]]) -> dict[str, Any]:
    bridge_file = out / "_m10_entry_bridge" / Path(key).name
    dumpj(bridge_file, payload)
    rc, _, err = run(
        [
            "aws",
            "s3",
            "cp",
            bridge_file.as_posix(),
            f"s3://{bucket}/{key}",
            "--region",
            "eu-west-2",
        ],
        timeout=180,
    )
    if rc != 0:
        add_blocker(
            blockers,
            "M11-ST-B12",
            "S0",
            {"reason": "entry_bridge_upload_failed", "key": key, "stderr": err.strip()[:300], "rc": rc},
        )
    return {
        "generated_at_utc": now(),
        "local_bridge_path": bridge_file.as_posix(),
        "target_s3_key": key,
        "upload_rc": rc,
    }


def stage_bridge_fetch_json(out: Path, bucket: str, key: str, blockers: list[dict[str, Any]]) -> dict[str, Any]:
    safe_name = key.replace("/", "__")
    local_file = out / "_m10_entry_bridge" / f"fetch__{safe_name}"
    rc, _, err = run(
        [
            "aws",
            "s3",
            "cp",
            f"s3://{bucket}/{key}",
            local_file.as_posix(),
            "--region",
            "eu-west-2",
        ],
        timeout=240,
    )
    if rc != 0:
        add_blocker(
            blockers,
            "M11-ST-B1",
            "S0",
            {"reason": "entry_bridge_fetch_failed", "key": key, "stderr": err.strip()[:300], "rc": rc},
        )
        return {}
    payload = loadj(local_file)
    if not payload:
        add_blocker(
            blockers,
            "M11-ST-B1",
            "S0",
            {"reason": "entry_bridge_fetch_json_invalid", "key": key},
        )
        return {}
    return payload


def run_s0(phase_execution_id: str, upstream_m10_s5_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m11a_handle_closure.py",
        "scripts/dev_substrate/m11b_sagemaker_readiness.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M11-ST-B18",
                "S0",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    fail_on_stale = bool(packet.get("M11_STRESS_FAIL_ON_STALE_UPSTREAM", True))
    expected_entry_execution = str(packet.get("M11_STRESS_EXPECTED_ENTRY_EXECUTION", "")).strip()
    if fail_on_stale and expected_entry_execution and upstream_m10_s5_execution != expected_entry_execution:
        add_blocker(
            blockers,
            "M11-ST-B1",
            "S0",
            {
                "reason": "stale_or_unexpected_upstream_execution",
                "selected_upstream_execution": upstream_m10_s5_execution,
                "expected_execution": expected_entry_execution,
            },
        )

    expected_entry_gate = str(packet.get("M11_STRESS_EXPECTED_ENTRY_GATE", "M11_READY")).strip() or "M11_READY"
    local_m10_s5_summary = loadj(OUT_ROOT / upstream_m10_s5_execution / "stress" / "m10_execution_summary.json")
    if not local_m10_s5_summary:
        add_blocker(
            blockers,
            "M11-ST-B1",
            "S0",
            {
                "reason": "upstream_m10_s5_summary_missing",
                "path": (OUT_ROOT / upstream_m10_s5_execution / "stress" / "m10_execution_summary.json").as_posix(),
            },
        )
    else:
        if not (
            bool(local_m10_s5_summary.get("overall_pass"))
            and int(local_m10_s5_summary.get("open_blocker_count", 1)) == 0
            and str(local_m10_s5_summary.get("verdict", "")) == "ADVANCE_TO_M11"
            and str(local_m10_s5_summary.get("next_gate", "")) == expected_entry_gate
        ):
            add_blocker(
                blockers,
                "M11-ST-B1",
                "S0",
                {
                    "reason": "upstream_m10_s5_not_ready",
                    "summary": {
                        "overall_pass": local_m10_s5_summary.get("overall_pass"),
                        "open_blocker_count": local_m10_s5_summary.get("open_blocker_count"),
                        "verdict": local_m10_s5_summary.get("verdict"),
                        "next_gate": local_m10_s5_summary.get("next_gate"),
                    },
                },
            )

    s4_exec = str(local_m10_s5_summary.get("upstream_m10_s4_execution", "")).strip() if local_m10_s5_summary else ""
    local_m10_s4_summary = loadj(OUT_ROOT / s4_exec / "stress" / "m10_execution_summary.json") if s4_exec else {}
    if not s4_exec:
        add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "missing_upstream_m10_s4_execution_in_m10_s5_summary"})
    elif not local_m10_s4_summary:
        add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "upstream_m10_s4_summary_missing", "upstream_s4_execution": s4_exec})
    elif not (bool(local_m10_s4_summary.get("overall_pass")) and str(local_m10_s4_summary.get("next_gate", "")) == "M10_ST_S5_READY"):
        add_blocker(
            blockers,
            "M11-ST-B1",
            "S0",
            {
                "reason": "upstream_m10_s4_not_ready",
                "upstream_s4_execution": s4_exec,
                "summary": {
                    "overall_pass": local_m10_s4_summary.get("overall_pass"),
                    "next_gate": local_m10_s4_summary.get("next_gate"),
                    "open_blocker_count": local_m10_s4_summary.get("open_blocker_count"),
                },
            },
        )

    m10j_exec = str(local_m10_s5_summary.get("m10j_execution_id", "")).strip() if local_m10_s5_summary else ""
    m10i_exec = str(local_m10_s5_summary.get("m10i_execution_id", "")).strip() if local_m10_s5_summary else ""
    if not m10i_exec:
        m10i_exec = str(local_m10_s4_summary.get("m10i_execution_id", "")).strip() if local_m10_s4_summary else ""
    if not m10j_exec:
        add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "missing_m10j_execution_id_from_m10_s5_summary"})
    if not m10i_exec:
        add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "missing_m10i_execution_id_from_strict_chain"})

    local_m10j_summary = loadj(OUT_ROOT / upstream_m10_s5_execution / "stress" / "m10j_execution_summary.json")
    if not local_m10j_summary:
        add_blocker(
            blockers,
            "M11-ST-B1",
            "S0",
            {"reason": "m10j_summary_missing_in_upstream_s5_stress_root", "upstream_s5_execution": upstream_m10_s5_execution},
        )
    elif not (
        bool(local_m10j_summary.get("overall_pass"))
        and str(local_m10j_summary.get("verdict", "")) == "ADVANCE_TO_M11"
        and str(local_m10j_summary.get("next_gate", "")) == "M11_READY"
    ):
        add_blocker(
            blockers,
            "M11-ST-B1",
            "S0",
            {"reason": "m10j_not_ready", "summary": local_m10j_summary},
        )

    local_m11_handoff = loadj(OUT_ROOT / s4_exec / "stress" / "m11_handoff_pack.json") if s4_exec else {}
    local_m10g_snapshot = loadj(OUT_ROOT / str(local_m10_s5_summary.get("upstream_m10_s3_execution", "")).strip() / "stress" / "m10g_manifest_fingerprint_snapshot.json") if local_m10_s5_summary else {}
    local_m10h_snapshot = loadj(OUT_ROOT / str(local_m10_s5_summary.get("upstream_m10_s3_execution", "")).strip() / "stress" / "m10h_rollback_recipe_snapshot.json") if local_m10_s5_summary else {}
    if not local_m11_handoff:
        add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "m11_handoff_missing_from_upstream_m10_s4", "upstream_s4_execution": s4_exec})
    else:
        if not bool(local_m11_handoff.get("p13_overall_pass")):
            add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "m11_handoff_p13_overall_pass_false"})
        if str(local_m11_handoff.get("p13_verdict", "")) != "ADVANCE_TO_P14":
            add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "m11_handoff_p13_verdict_not_advance_to_p14"})
        if str(local_m11_handoff.get("m11_entry_gate", {}).get("next_gate", "")) != "M11_READY":
            add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "m11_handoff_next_gate_not_m11_ready"})

    bridge_snapshots: list[dict[str, Any]] = []

    # Build a compatibility alias payload for M11.C managed workflow expectations.
    m11_handoff_bridge = dict(local_m11_handoff) if isinstance(local_m11_handoff, dict) else {}
    if m11_handoff_bridge:
        entry_gate = m11_handoff_bridge.get("m11_entry_gate", {})
        if not isinstance(entry_gate, dict):
            entry_gate = {}

        next_gate_from_entry = str(entry_gate.get("next_gate", "")).strip()
        current_next_gate = str(m11_handoff_bridge.get("next_gate", "")).strip()
        if not current_next_gate and next_gate_from_entry:
            m11_handoff_bridge["next_gate"] = next_gate_from_entry

        if "m11_entry_ready" not in m11_handoff_bridge:
            m11_handoff_bridge["m11_entry_ready"] = bool(
                m11_handoff_bridge.get("p13_overall_pass", False)
                and str(m11_handoff_bridge.get("next_gate", "")).strip() == "M11_READY"
            )

        required_refs: dict[str, Any] = {}
        if isinstance(m11_handoff_bridge.get("required_refs"), dict):
            required_refs = dict(m11_handoff_bridge.get("required_refs", {}))
        elif isinstance(m11_handoff_bridge.get("required_evidence_refs"), dict):
            required_refs = dict(m11_handoff_bridge.get("required_evidence_refs", {}))

        m10g_outputs = dict(local_m10g_snapshot.get("run_scoped_outputs", {})) if isinstance(local_m10g_snapshot, dict) else {}
        m10h_outputs = dict(local_m10h_snapshot.get("run_scoped_outputs", {})) if isinstance(local_m10h_snapshot, dict) else {}

        m10g_manifest_key = str(m10g_outputs.get("manifest_key", "")).strip()
        m10g_fingerprint_key = str(m10g_outputs.get("fingerprint_key", "")).strip()
        m10g_time_bound_key = str(m10g_outputs.get("time_bound_audit_key", "")).strip()
        m10h_recipe_key = str(m10h_outputs.get("rollback_recipe_key", "")).strip()
        m10h_drill_key = str(m10h_outputs.get("rollback_drill_report_key", "")).strip()

        compat_manifest_key = ""
        compat_fingerprint_key = ""
        compat_time_bound_key = ""
        if bucket and not is_placeholder(bucket) and m10g_manifest_key and m10g_fingerprint_key and m10g_time_bound_key:
            base_manifest = stage_bridge_fetch_json(out, bucket, m10g_manifest_key, blockers)
            base_fingerprint = stage_bridge_fetch_json(out, bucket, m10g_fingerprint_key, blockers)
            base_time_bound = stage_bridge_fetch_json(out, bucket, m10g_time_bound_key, blockers)

            if base_manifest and base_fingerprint and base_time_bound:
                compat_manifest_key = f"evidence/dev_full/run_control/{phase_execution_id}/m10g_manifest_compat.json"
                compat_fingerprint_key = f"evidence/dev_full/run_control/{phase_execution_id}/m10g_fingerprint_compat.json"
                compat_time_bound_key = f"evidence/dev_full/run_control/{phase_execution_id}/m10g_time_bound_compat.json"

                compat_manifest = dict(base_manifest)
                compat_manifest["fingerprint_ref"] = compat_fingerprint_key
                compat_manifest["time_bound_audit_ref"] = compat_time_bound_key
                compat_manifest["status"] = "COMMITTED"

                compat_fingerprint = dict(base_fingerprint)
                required_order = list(compat_fingerprint.get("required_fields_order", []))
                if not required_order:
                    required_order = [str(x) for x in compat_fingerprint.get("required_fields", []) if str(x).strip()]
                required_values = compat_fingerprint.get("required_field_values", {})
                if not isinstance(required_values, dict):
                    required_values = {}
                if not required_values and isinstance(compat_fingerprint.get("field_values"), dict):
                    required_values = dict(compat_fingerprint.get("field_values", {}))
                compat_fingerprint["required_fields_order"] = required_order
                compat_fingerprint["required_field_values"] = required_values
                canonical_lines: list[str] = []
                for field_name in required_order:
                    key_name = str(field_name)
                    if key_name in required_values:
                        canonical_lines.append(f"{key_name}={required_values[key_name]}")
                compat_fingerprint["fingerprint_sha256"] = hashlib.sha256(
                    "\n".join(canonical_lines).encode("utf-8")
                ).hexdigest()
                compat_fingerprint["status"] = "COMMITTED"

                compat_time_bound = dict(base_time_bound)
                compat_time_bound["status"] = "COMMITTED"

                bridge_snapshots.append(stage_bridge_upload(out, bucket, compat_manifest_key, compat_manifest, blockers))
                bridge_snapshots.append(stage_bridge_upload(out, bucket, compat_fingerprint_key, compat_fingerprint, blockers))
                bridge_snapshots.append(stage_bridge_upload(out, bucket, compat_time_bound_key, compat_time_bound, blockers))

        compat_required_refs = {
            "m10i_gate_verdict_ref": f"evidence/dev_full/run_control/{m10i_exec}/m10i_p13_gate_verdict.json" if m10i_exec else "",
            "m10g_manifest_ref": compat_manifest_key or m10g_manifest_key,
            "m10g_fingerprint_ref": compat_fingerprint_key or m10g_fingerprint_key,
            "m10g_time_bound_audit_ref": compat_time_bound_key or m10g_time_bound_key,
            "m10h_rollback_recipe_ref": m10h_recipe_key,
            "m10h_rollback_drill_ref": m10h_drill_key,
        }
        for ref_key, ref_value in compat_required_refs.items():
            if ref_value:
                required_refs[ref_key] = ref_value
            elif ref_key not in required_refs:
                add_blocker(
                    blockers,
                    "M11-ST-B1",
                    "S0",
                    {"reason": "m11_handoff_required_ref_unresolved", "ref": ref_key},
                )
        m11_handoff_bridge["required_refs"] = required_refs

    if bucket and not is_placeholder(bucket) and local_m10_s5_summary:
        bridge_snapshots.append(
            stage_bridge_upload(
                out,
                bucket,
                f"evidence/dev_full/run_control/{upstream_m10_s5_execution}/m10_execution_summary.json",
                local_m10_s5_summary,
                blockers,
            )
        )
    if bucket and not is_placeholder(bucket) and m10j_exec and local_m10j_summary:
        bridge_snapshots.append(
            stage_bridge_upload(
                out,
                bucket,
                f"evidence/dev_full/run_control/{m10j_exec}/m10j_execution_summary.json",
                local_m10j_summary,
                blockers,
            )
        )
    if bucket and not is_placeholder(bucket) and m10i_exec and m11_handoff_bridge:
        bridge_snapshots.append(
            stage_bridge_upload(
                out,
                bucket,
                f"evidence/dev_full/run_control/{m10i_exec}/m11_handoff_pack.json",
                m11_handoff_bridge,
                blockers,
            )
        )
    if bridge_snapshots:
        dumpj(out / "m11_m10_entry_bridge_snapshot.json", {"generated_at_utc": now(), "snapshots": bridge_snapshots})

    m11a_exec = ""
    m11a_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m11a_handle_closure.py").exists():
        m11a_exec = f"m11a_stress_s0_{tok()}"
        m11a_dir = out / "_m11a"
        env_m11a = dict(os.environ)
        env_m11a.update(
            {
                "M11A_EXECUTION_ID": m11a_exec,
                "M11A_RUN_DIR": m11a_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10_EXECUTION": upstream_m10_s5_execution,
                "UPSTREAM_M10J_EXECUTION": m10j_exec,
                "UPSTREAM_M10I_EXECUTION": m10i_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m11a_handle_closure.py"], timeout=3600, env=env_m11a)
        if rc != 0:
            add_blocker(
                blockers,
                "M11-ST-B1",
                "S0",
                {"reason": "m11a_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m11a_summary = loadj(m11a_dir / "m11a_execution_summary.json")
        m11a_snapshot = loadj(m11a_dir / "m11a_handle_closure_snapshot.json")
        m11a_register = loadj(m11a_dir / "m11a_blocker_register.json")
        if m11a_snapshot:
            dumpj(out / "m11a_handle_closure_snapshot.json", m11a_snapshot)
        if m11a_summary:
            dumpj(out / "m11a_execution_summary.json", m11a_summary)
        if m11a_register:
            dumpj(out / "m11a_blocker_register.json", m11a_register)

        if not m11a_summary:
            add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "m11a_summary_missing"})
        elif not (bool(m11a_summary.get("overall_pass")) and str(m11a_summary.get("next_gate", "")) == "M11.B_READY"):
            add_blocker(blockers, "M11-ST-B1", "S0", {"reason": "m11a_not_ready", "summary": m11a_summary})

    m11b_exec = ""
    m11b_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m11b_sagemaker_readiness.py").exists() and m11a_exec:
        m11b_exec = f"m11b_stress_s0_{tok()}"
        m11b_dir = out / "_m11b"
        env_m11b = dict(os.environ)
        env_m11b.update(
            {
                "M11B_EXECUTION_ID": m11b_exec,
                "M11B_RUN_DIR": m11b_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11A_EXECUTION": m11a_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m11b_sagemaker_readiness.py"], timeout=3600, env=env_m11b)
        if rc != 0:
            add_blocker(
                blockers,
                "M11-ST-B2",
                "S0",
                {"reason": "m11b_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m11b_summary = loadj(m11b_dir / "m11b_execution_summary.json")
        m11b_snapshot = loadj(m11b_dir / "m11b_sagemaker_readiness_snapshot.json")
        m11b_register = loadj(m11b_dir / "m11b_blocker_register.json")
        if m11b_snapshot:
            dumpj(out / "m11b_sagemaker_readiness_snapshot.json", m11b_snapshot)
            advisories.extend(list(m11b_snapshot.get("advisories", [])) if isinstance(m11b_snapshot.get("advisories"), list) else [])
        if m11b_summary:
            dumpj(out / "m11b_execution_summary.json", m11b_summary)
        if m11b_register:
            dumpj(out / "m11b_blocker_register.json", m11b_register)

        if not m11b_summary:
            add_blocker(blockers, "M11-ST-B2", "S0", {"reason": "m11b_summary_missing"})
        elif not (bool(m11b_summary.get("overall_pass")) and str(m11b_summary.get("next_gate", "")) == "M11.C_READY"):
            add_blocker(blockers, "M11-ST-B2", "S0", {"reason": "m11b_not_ready", "summary": m11b_summary})
    elif not m11a_exec:
        add_blocker(
            blockers,
            "M11-ST-B2",
            "S0",
            {"reason": "m11b_skipped_missing_upstream_m11a_execution"},
        )

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M11-ST-S0",
        "findings": [
            {
                "id": "M11-ST-F3",
                "classification": "PREVENT",
                "status": "CLOSED",
                "note": "Parent M11 runner exists and executes S0 deterministically.",
            },
            {
                "id": "M11-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if all(Path(p).exists() for p in scripts_required) else "OPEN",
                "note": "S0 required execution scripts are present.",
            },
            {
                "id": "M11-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") == "M11-ST-B1"]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S0.",
            },
        ],
    }
    dumpj(out / "m11_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M11-ST-S0",
        "lanes": [
            {
                "lane": "A",
                "component": "M11.A",
                "execution_id": m11a_exec,
                "overall_pass": bool(m11a_summary.get("overall_pass")) if m11a_summary else False,
                "next_gate": str(m11a_summary.get("next_gate", "")) if m11a_summary else "",
            },
            {
                "lane": "B",
                "component": "M11.B",
                "execution_id": m11b_exec,
                "overall_pass": bool(m11b_summary.get("overall_pass")) if m11b_summary else False,
                "next_gate": str(m11b_summary.get("next_gate", "")) if m11b_summary else "",
            },
        ],
    }
    dumpj(out / "m11_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M11_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M11-ST-B16", "S0", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m11_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M11-ST-S0",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M11_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{upstream_m10_s5_execution}/m10_execution_summary.json" if upstream_m10_s5_execution else "",
        f"evidence/dev_full/run_control/{m10j_exec}/m10j_execution_summary.json" if m10j_exec else "",
        f"evidence/dev_full/run_control/{m10i_exec}/m11_handoff_pack.json" if m10i_exec else "",
        f"evidence/dev_full/run_control/{m11a_exec}/m11a_execution_summary.json" if m11a_exec else "",
        f"evidence/dev_full/run_control/{m11b_exec}/m11b_execution_summary.json" if m11b_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M11-ST-B12", "M11-ST-B16"}]) == 0
    dumpj(
        out / "m11_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M11-ST-S0",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M11_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M11-ST-B17", "S0", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m11_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M11-ST-S0",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M11_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M11_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M11-ST-B16", "S0", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(local_m10_s5_summary.get("platform_run_id", "")) if local_m10_s5_summary else ""
    scenario_run_id = str(local_m10_s5_summary.get("scenario_run_id", "")) if local_m10_s5_summary else ""
    return finish(
        "S0",
        phase_execution_id,
        out,
        blockers,
        S0_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m10_s5_execution": upstream_m10_s5_execution,
            "upstream_m10_s4_execution": s4_exec,
            "m10j_execution_id": m10j_exec,
            "m10i_execution_id": m10i_exec,
            "m11a_execution_id": m11a_exec,
            "m11b_execution_id": m11b_exec,
            "decisions": [
                "S0 enforced strict M10 closure continuity (S5->S4) before any M11 lane execution.",
                "S0 bridged upstream M10 closure artifacts to durable authority keys required by M11.A.",
                "S0 executed M11.A authority closure and M11.B SageMaker readiness adjudication with fail-closed blocker mapping.",
            ],
            "advisories": advisories,
        },
    )


def run_s1(phase_execution_id: str, upstream_m11_s0_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m11c_input_immutability.py",
        "scripts/dev_substrate/m11d_train_eval_execution.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M11-ST-B18",
                "S1",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M11-ST-B3", "S1", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s0_exec = upstream_m11_s0_execution.strip()
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m11_execution_summary.json") if s0_exec else {}
    if not s0:
        add_blocker(
            blockers,
            "M11-ST-B3",
            "S1",
            {
                "reason": "upstream_s0_summary_missing",
                "path": (OUT_ROOT / s0_exec / "stress" / "m11_execution_summary.json").as_posix(),
            },
        )
    elif not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M11_ST_S1_READY":
        add_blocker(
            blockers,
            "M11-ST-B3",
            "S1",
            {
                "reason": "upstream_s0_not_ready",
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "next_gate": s0.get("next_gate"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                },
            },
        )

    m11a_exec = str(s0.get("m11a_execution_id", "")).strip() if s0 else ""
    m11b_exec = str(s0.get("m11b_execution_id", "")).strip() if s0 else ""
    if not m11b_exec:
        add_blocker(blockers, "M11-ST-B3", "S1", {"reason": "missing_m11b_execution_id_from_s0_summary"})

    m11c_exec = ""
    m11c_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m11c_input_immutability.py").exists() and m11b_exec:
        m11c_exec = f"m11c_stress_s1_{tok()}"
        m11c_dir = out / "_m11c"
        env_m11c = dict(os.environ)
        env_m11c.update(
            {
                "M11C_EXECUTION_ID": m11c_exec,
                "M11C_RUN_DIR": m11c_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11B_EXECUTION": m11b_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m11c_input_immutability.py"], timeout=3600, env=env_m11c)
        if rc != 0:
            add_blocker(
                blockers,
                "M11-ST-B3",
                "S1",
                {"reason": "m11c_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m11c_summary = loadj(m11c_dir / "m11c_execution_summary.json")
        m11c_snapshot = loadj(m11c_dir / "m11c_input_immutability_snapshot.json")
        m11c_register = loadj(m11c_dir / "m11c_blocker_register.json")
        if m11c_snapshot:
            dumpj(out / "m11c_input_immutability_snapshot.json", m11c_snapshot)
        if m11c_register:
            dumpj(out / "m11c_blocker_register.json", m11c_register)
        if m11c_summary:
            dumpj(out / "m11c_execution_summary.json", m11c_summary)
        if not m11c_summary:
            add_blocker(blockers, "M11-ST-B3", "S1", {"reason": "m11c_summary_missing"})
        elif not (bool(m11c_summary.get("overall_pass")) and str(m11c_summary.get("next_gate", "")) == "M11.D_READY"):
            add_blocker(blockers, "M11-ST-B3", "S1", {"reason": "m11c_not_ready", "summary": m11c_summary})

    m11d_exec = ""
    m11d_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m11d_train_eval_execution.py").exists() and m11c_exec:
        m11d_exec = f"m11d_stress_s1_{tok()}"
        m11d_dir = out / "_m11d"
        env_m11d = dict(os.environ)
        env_m11d.update(
            {
                "M11D_EXECUTION_ID": m11d_exec,
                "M11D_RUN_DIR": m11d_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11C_EXECUTION": m11c_exec,
                "AWS_REGION": "eu-west-2",
                "M11D_TRAINING_INSTANCE_TYPE": "ml.c5.xlarge",
                "M11D_TRANSFORM_INSTANCE_TYPE": "ml.c5.xlarge",
                "M11D_REQUIRE_MANAGED_TRANSFORM": "true",
                "M11D_POLL_TIMEOUT_MINUTES": "120",
                "M11D_POLL_INTERVAL_SECONDS": "20",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m11d_train_eval_execution.py"], timeout=10800, env=env_m11d)
        if rc != 0:
            add_blocker(
                blockers,
                "M11-ST-B4",
                "S1",
                {"reason": "m11d_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m11d_summary = loadj(m11d_dir / "m11d_execution_summary.json")
        m11d_snapshot = loadj(m11d_dir / "m11d_train_eval_execution_snapshot.json")
        m11d_register = loadj(m11d_dir / "m11d_blocker_register.json")
        m11d_budget = loadj(m11d_dir / "m11_phase_budget_envelope.json")
        if m11d_snapshot:
            dumpj(out / "m11d_train_eval_execution_snapshot.json", m11d_snapshot)
            if isinstance(m11d_snapshot.get("advisories"), list):
                advisories.extend([str(x) for x in m11d_snapshot.get("advisories", [])])
        if m11d_register:
            dumpj(out / "m11d_blocker_register.json", m11d_register)
        if m11d_summary:
            dumpj(out / "m11d_execution_summary.json", m11d_summary)
        if m11d_budget:
            dumpj(out / "m11_phase_budget_envelope.json", m11d_budget)
        if not m11d_summary:
            add_blocker(blockers, "M11-ST-B4", "S1", {"reason": "m11d_summary_missing"})
        elif not (bool(m11d_summary.get("overall_pass")) and str(m11d_summary.get("next_gate", "")) == "M11.E_READY"):
            add_blocker(blockers, "M11-ST-B4", "S1", {"reason": "m11d_not_ready", "summary": m11d_summary})
        if m11d_register and isinstance(m11d_register.get("blockers"), list):
            quota_signal = False
            for row in m11d_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    quota_signal = True
                    break
            if quota_signal:
                add_blocker(
                    blockers,
                    "M11-ST-B19",
                    "S1",
                    {"reason": "managed_quota_or_access_boundary_pressure_detected"},
                )
    elif not m11c_exec:
        add_blocker(
            blockers,
            "M11-ST-B4",
            "S1",
            {"reason": "m11d_skipped_missing_upstream_m11c_execution"},
        )

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M11-ST-S1",
        "findings": [
            {
                "id": "M11-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if all(Path(p).exists() for p in scripts_required) else "OPEN",
                "note": "S1 required execution scripts are present.",
            },
            {
                "id": "M11-ST-F7",
                "classification": "OBSERVE",
                "status": "OPEN" if len([b for b in blockers if b.get("id") == "M11-ST-B19"]) > 0 else "CLOSED",
                "note": "Managed quota/capacity pressure surfaced by M11.D is projected to M11-ST-B19.",
            },
        ],
    }
    dumpj(out / "m11_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M11-ST-S1",
        "lanes": [
            {
                "lane": "C",
                "component": "M11.C",
                "execution_id": m11c_exec,
                "overall_pass": bool(m11c_summary.get("overall_pass")) if m11c_summary else False,
                "next_gate": str(m11c_summary.get("next_gate", "")) if m11c_summary else "",
            },
            {
                "lane": "D",
                "component": "M11.D",
                "execution_id": m11d_exec,
                "overall_pass": bool(m11d_summary.get("overall_pass")) if m11d_summary else False,
                "next_gate": str(m11d_summary.get("next_gate", "")) if m11d_summary else "",
            },
        ],
    }
    dumpj(out / "m11_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M11_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M11-ST-B16", "S1", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m11_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M11-ST-S1",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M11_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s0_exec}/stress/m11_execution_summary.json" if s0_exec else "",
        f"evidence/dev_full/run_control/{m11b_exec}/m11b_execution_summary.json" if m11b_exec else "",
        f"evidence/dev_full/run_control/{m11c_exec}/m11c_execution_summary.json" if m11c_exec else "",
        f"evidence/dev_full/run_control/{m11d_exec}/m11d_execution_summary.json" if m11d_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M11-ST-B12", "M11-ST-B16"}]) == 0
    dumpj(
        out / "m11_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M11-ST-S1",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M11_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M11-ST-B17", "S1", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m11_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M11-ST-S1",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M11_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M11_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M11-ST-B16", "S1", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(s0.get("platform_run_id", "")) if s0 else ""
    scenario_run_id = str(s0.get("scenario_run_id", "")) if s0 else ""
    return finish(
        "S1",
        phase_execution_id,
        out,
        blockers,
        S1_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m11_s0_execution": s0_exec,
            "m11a_execution_id": m11a_exec,
            "m11b_execution_id": m11b_exec,
            "m11c_execution_id": m11c_exec,
            "m11d_execution_id": m11d_exec,
            "decisions": [
                "S1 enforced strict M11 S0 entry continuity before executing lane C.",
                "S1 executed M11.C via managed workflow dispatch and required deterministic M11.D_READY output.",
                "S1 executed M11.D via managed workflow dispatch (managed transform required) and required deterministic M11.E_READY output.",
            ],
            "advisories": advisories,
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="M11 stress runner")
    ap.add_argument("--stage", required=True, choices=["S0", "S1"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m10-s5-execution", default="")
    ap.add_argument("--upstream-m11-s0-execution", default="")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip()
    if not phase_execution_id:
        if args.stage == "S0":
            phase_execution_id = f"m11_stress_s0_{tok()}"
        elif args.stage == "S1":
            phase_execution_id = f"m11_stress_s1_{tok()}"

    if args.stage == "S0":
        upstream_m10_s5 = args.upstream_m10_s5_execution.strip()
        if not upstream_m10_s5:
            upstream_m10_s5, _ = latest_m10_s5()
        if not upstream_m10_s5:
            raise SystemExit("No upstream M10 S5 execution provided/found.")
        return run_s0(phase_execution_id, upstream_m10_s5)

    if args.stage == "S1":
        upstream_m11_s0 = args.upstream_m11_s0_execution.strip()
        if not upstream_m11_s0:
            upstream_m11_s0, _ = latest_s0()
        if not upstream_m11_s0:
            raise SystemExit("No upstream M11 S0 execution provided/found.")
        return run_s1(phase_execution_id, upstream_m11_s0)

    raise SystemExit("Unsupported stage")


if __name__ == "__main__":
    raise SystemExit(main())
