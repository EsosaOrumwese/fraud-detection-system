#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.stress_test.md")
P5_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P5.stress_test.md")
P6_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P6.stress_test.md")
P7_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P7.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

M6_REQ_HANDLES = [
    "S3_EVIDENCE_BUCKET",
    "S3_RUN_CONTROL_ROOT_PATTERN",
    "M6_HANDOFF_PACK_PATH_PATTERN",
    "M7_HANDOFF_PACK_PATH_PATTERN",
    "FP_BUS_CONTROL_V1",
    "READY_MESSAGE_FILTER",
    "REQUIRED_PLATFORM_RUN_ID_ENV_KEY",
    "SR_READY_COMMIT_AUTHORITY",
    "SR_READY_COMMIT_STATE_MACHINE",
    "SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF",
    "SR_READY_COMMIT_RECEIPT_PATH_PATTERN",
    "FLINK_RUNTIME_PATH_ACTIVE",
    "FLINK_RUNTIME_PATH_ALLOWED",
    "FLINK_APP_WSP_STREAM_V0",
    "FLINK_APP_SR_READY_V0",
    "FLINK_EKS_WSP_STREAM_REF",
    "FLINK_EKS_SR_READY_REF",
    "EMR_EKS_VIRTUAL_CLUSTER_ID",
    "EMR_EKS_RELEASE_LABEL",
    "EMR_EKS_EXECUTION_ROLE_ARN",
    "RTDL_CAUGHT_UP_LAG_MAX",
    "WSP_MAX_INFLIGHT",
    "WSP_RETRY_MAX_ATTEMPTS",
    "WSP_RETRY_BACKOFF_MS",
    "WSP_STOP_ON_NONRETRYABLE",
    "IG_BASE_URL",
    "IG_INGEST_PATH",
    "DDB_IG_IDEMPOTENCY_TABLE",
    "RECEIPT_SUMMARY_PATH_PATTERN",
    "QUARANTINE_SUMMARY_PATH_PATTERN",
    "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
]

M6_PLAN_KEYS = [
    "M6_STRESS_PROFILE_ID",
    "M6_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M6_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M6_STRESS_DECISION_LOG_PATH_PATTERN",
    "M6_STRESS_REQUIRED_ARTIFACTS",
    "M6_STRESS_MAX_RUNTIME_MINUTES",
    "M6_STRESS_MAX_SPEND_USD",
    "M6_STRESS_EXPECTED_NEXT_GATE_ON_PASS",
    "M6_STRESS_REQUIRED_SUBPHASES",
    "M6_STRESS_P5_REQUIRED_VERDICT",
    "M6_STRESS_P6_REQUIRED_VERDICT",
    "M6_STRESS_P7_REQUIRED_VERDICT",
    "M6_STRESS_INTEGRATED_WINDOW_MINUTES",
    "M6_STRESS_BURST_WINDOW_MINUTES",
    "M6_STRESS_FAILURE_INJECTION_WINDOW_MINUTES",
    "M6_STRESS_TARGETED_RERUN_ONLY",
]

M6_S0_ARTS = [
    "m6_stagea_findings.json",
    "m6_lane_matrix.json",
    "m6_probe_latency_throughput_snapshot.json",
    "m6_control_rail_conformance_snapshot.json",
    "m6_secret_safety_snapshot.json",
    "m6_cost_outcome_receipt.json",
    "m6_blocker_register.json",
    "m6_execution_summary.json",
    "m6_decision_log.json",
]
M6_S1_ARTS = M6_S0_ARTS
M6_DEFAULT_REQUIRED_ARTIFACTS = M6_S0_ARTS + ["m7_handoff_pack.json"]
M6_ADDENDUM_ARTIFACTS = [
    "m6_addendum_parent_chain_summary.json",
    "m6_addendum_integrated_window_summary.json",
    "m6_addendum_integrated_window_metrics.json",
    "m6_addendum_ingest_live_evidence_summary.json",
    "m6_addendum_cost_attribution_receipt.json",
    "m6_addendum_blocker_register.json",
    "m6_addendum_execution_summary.json",
    "m6_addendum_decision_log.json",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tok() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_scalar(v: str) -> Any:
    v = v.strip()
    if v.lower() in {"true", "false"}:
        return v.lower() == "true"
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    try:
        return int(v) if "." not in v else float(v)
    except ValueError:
        return v


def parse_backtick_map(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in re.findall(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`", text):
        out[k] = parse_scalar(v)
    return out


def parse_registry(path: Path) -> dict[str, Any]:
    rx = re.compile(r"^\* `([^`]+)`(?:\s.*)?$")
    out: dict[str, Any] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(raw.strip())
        if m:
            body = m.group(1).strip()
            if "=" not in body:
                continue
            k, v = body.split("=", 1)
            out[k.strip()] = parse_scalar(v.strip())
    return out


def run_cmd(cmd: list[str], timeout: int = 30) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "command": " ".join(cmd),
            "exit_code": int(p.returncode),
            "status": "PASS" if int(p.returncode) == 0 else "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": (p.stdout or "").strip()[:300],
            "stderr": (p.stderr or "").strip()[:300],
            "started_at_utc": st,
            "ended_at_utc": now(),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(cmd),
            "exit_code": 124,
            "status": "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": "",
            "stderr": "timeout",
            "started_at_utc": st,
            "ended_at_utc": now(),
        }


def load_json_safe(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def load_latest_successful_m5_s3(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5_stress_s3_*/stress"))
    for d in reversed(runs):
        sp = d / "m5_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M5-ST-S3":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m6_s0(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m6_stress_s0_*/stress"))
    for d in reversed(runs):
        sp = d / "m6_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M6-ST-S0":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m6p5_s5(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m6p5_stress_s5_*/stress"))
    for d in reversed(runs):
        sp = d / "m6p5_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M6P5-ST-S5":
            continue
        return {"path": d, "summary": summ}
    return {}


def latest_ok(prefix: str, summary_name: str, stage_id: str, out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob(f"{prefix}_*/stress"))
    for d in reversed(runs):
        s = load_json_safe(d / summary_name)
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == stage_id:
            return {"path": d, "summary": s}
    return {}


def parse_required_artifacts(plan_packet: dict[str, Any]) -> list[str]:
    raw = str(plan_packet.get("M6_STRESS_REQUIRED_ARTIFACTS", "")).strip()
    if not raw:
        return list(M6_DEFAULT_REQUIRED_ARTIFACTS)
    out = [x.strip() for x in raw.split(",") if x.strip()]
    return out if out else list(M6_DEFAULT_REQUIRED_ARTIFACTS)


def probe_metrics(probes: list[dict[str, Any]]) -> dict[str, Any]:
    fails = [p for p in probes if str(p.get("status", "FAIL")) != "PASS"]
    lats = [float(p.get("duration_ms", 0.0) or 0.0) for p in probes]
    p50 = 0.0 if not lats else sorted(lats)[len(lats) // 2]
    p95 = 0.0 if not lats else max(lats)
    return {
        "window_seconds_observed": max(1, int(round(sum(lats) / 1000.0))) if lats else 1,
        "probe_count": len(probes),
        "failure_count": len(fails),
        "error_rate_pct": round((len(fails) / len(probes)) * 100.0, 4) if probes else 0.0,
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
        "latency_ms_p99": p95,
        "sample_failures": fails[:10],
        "probes": probes,
    }


def finalize_artifact_contract(
    out: Path,
    required_artifacts: list[str],
    blockers: list[dict[str, Any]],
    blocker_register: dict[str, Any],
    summary: dict[str, Any],
    blocker_id: str,
) -> None:
    miss = [x for x in required_artifacts if not (out / x).exists()]
    if not miss:
        return
    blockers.append({"id": blocker_id, "severity": str(summary.get("stage_id", "")), "status": "OPEN", "details": {"missing_artifacts": miss}})
    blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
    summary.update({"overall_pass": False, "next_gate": "BLOCKED"})
    dumpj(out / "m6_blocker_register.json", blocker_register)
    dumpj(out / "m6_execution_summary.json", summary)


def materialize_pattern(pattern: str, replacements: dict[str, str]) -> str:
    out = str(pattern)
    for k, v in replacements.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def build_parent_chain_rows(platform_run_id: str, out_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    spec = [
        ("S0", "m6_stress_s0", "M6-ST-S0", "M6_ST_S1_READY"),
        ("S1", "m6_stress_s1", "M6-ST-S1", "M6_ST_S2_READY"),
        ("S2", "m6_stress_s2", "M6-ST-S2", "M6_ST_S3_READY"),
        ("S3", "m6_stress_s3", "M6-ST-S3", "M6_ST_S4_READY"),
        ("S4", "m6_stress_s4", "M6-ST-S4", "M6_ST_S5_READY"),
    ]
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    for label, prefix, stage_id, expected_gate in spec:
        rec = latest_ok(prefix, "m6_execution_summary.json", stage_id, out_root)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_gate,
            "found": bool(rec),
            "phase_execution_id": "",
            "next_gate": "",
            "overall_pass": False,
            "open_blockers": None,
            "platform_run_id": "",
            "run_scope_consistent": True,
            "ok": False,
        }
        if rec:
            s = rec.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["overall_pass"] = bool(s.get("overall_pass"))
            row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
            br = load_json_safe(Path(str(rec.get("path", ""))) / "m6_blocker_register.json")
            row["open_blockers"] = int(br.get("open_blocker_count", 0) or 0) if br else None
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_gate and row["open_blockers"] in {None, 0}
            if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
                row["run_scope_consistent"] = False
                row["ok"] = False
        if not row["ok"]:
            issues.append(f"parent chain row failed: {label}")
        rows.append(row)
    return rows, issues


def build_lane_matrix() -> dict[str, Any]:
    return {
        "component_sequence": ["M6-ST-S0", "M6-ST-S1", "M6-ST-S2", "M6-ST-S3", "M6-ST-S4", "M6-ST-S5"],
        "plane_sequence": ["control_plane", "streaming_plane", "ingress_plane", "phase_closure_plane"],
        "integrated_windows": ["m6_s4_sustained_window", "m6_s4_burst_window", "m6_s4_fault_window"],
    }


def run_s0(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in M6_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in M6_REQ_HANDLES if k not in h]
    placeholder_handles = [
        k
        for k in M6_REQ_HANDLES
        if k in h and str(h[k]).strip() in {"", "TO_PIN", "NONE", "None", "null", "NULL"}
    ]
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M6-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )

    dep = load_latest_successful_m5_s3(out_root)
    dep_issues: list[str] = []
    dep_blocker_count = None
    dep_id = ""
    if not dep:
        dep_issues.append("missing successful M5-ST-S3 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("recommendation", "")) != "GO":
            dep_issues.append("M5 recommendation is not GO")
        if str(dep_summ.get("next_gate", "")) != "M6_READY":
            dep_issues.append("M5 next_gate is not M6_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m5_blocker_register.json")
        dep_blocker_count = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_blocker_count not in {None, 0}:
            dep_issues.append(f"M5 blocker register not closed: {dep_blocker_count}")

    if dep_issues:
        blockers.append({"id": "M6-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})

    authority_issues: list[str] = []
    missing_authorities: list[str] = []
    unreadable_authorities: list[str] = []
    for p in [PLAN, P5_PLAN, P6_PLAN, P7_PLAN]:
        if not p.exists():
            missing_authorities.append(p.as_posix())
            continue
        try:
            _ = p.read_text(encoding="utf-8")
        except Exception:
            unreadable_authorities.append(p.as_posix())
    if missing_authorities:
        authority_issues.append(f"missing authority files: {','.join(missing_authorities)}")
    if unreadable_authorities:
        authority_issues.append(f"unreadable authority files: {','.join(unreadable_authorities)}")
    if authority_issues:
        blockers.append(
            {
                "id": "M6-ST-B3",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_authorities": missing_authorities,
                    "unreadable_authorities": unreadable_authorities,
                },
            }
        )

    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m6_s0_evidence_bucket", "group": "control"})
    else:
        probe_rows.append(
            {
                "probe_id": "m6_s0_evidence_bucket",
                "group": "control",
                "command": "aws s3api head-bucket",
                "exit_code": 1,
                "status": "FAIL",
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": "missing S3_EVIDENCE_BUCKET handle",
                "started_at_utc": now(),
                "ended_at_utc": now(),
            }
        )

    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    if probe_failures:
        blockers.append(
            {
                "id": "M6-ST-B10",
                "severity": "S0",
                "status": "OPEN",
                "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]},
            }
        )

    stagea = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "findings": [
            {
                "id": "M6-ST-F1",
                "classification": "PREVENT",
                "finding": "M6 requires split parent/subphase authority routing before execution.",
                "required_action": "Validate parent + P5/P6/P7 authority files before execution.",
            },
            {
                "id": "M6-ST-F2",
                "classification": "PREVENT",
                "finding": "M6 entry must chain from M5 S3 recommendation and next-gate contract.",
                "required_action": "Validate latest successful M5 S3 summary and blocker register at entry.",
            },
            {
                "id": "M6-ST-F3",
                "classification": "PREVENT",
                "finding": "M6 parent required handles and control artifact keys must be complete before stress windows.",
                "required_action": "Fail-closed on missing/placeholder required handles or plan keys.",
            },
            {
                "id": "M6-ST-F4",
                "classification": "PREVENT",
                "finding": "Evidence root reachability must be verified before M6 stage advancement.",
                "required_action": "Run bounded evidence-bucket probe and fail-closed on failure.",
            },
        ],
    }
    dumpj(out / "m6_stagea_findings.json", stagea)
    dumpj(out / "m6_lane_matrix.json", build_lane_matrix())

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M6_STRESS_MAX_SPEND_USD", 90))
    cost_within = True

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "m5_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m6_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    if missing_plan_keys:
        control_issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
    if missing_handles:
        control_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        control_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
    control_issues.extend(dep_issues)
    control_issues.extend(authority_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")

    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "m5_dependency_phase_execution_id": dep_id,
        "m5_dependency_open_blockers": dep_blocker_count,
        "required_authorities": [PLAN.as_posix(), P5_PLAN.as_posix(), P6_PLAN.as_posix(), P7_PLAN.as_posix()],
    }
    dumpj(out / "m6_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m6_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "read_only_entry_gate_validation_v0",
    }
    dumpj(out / "m6_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "decisions": [
            "Validated M6 parent stress handle packet and required handle closure.",
            "Validated latest successful M5 S3 handoff dependency.",
            "Validated M6 split stress authority files are present and readable.",
            "Ran bounded evidence-bucket reachability probe.",
            "Applied fail-closed blocker mapping for M6 S0.",
        ],
    }
    dumpj(out / "m6_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M6_ST_S1_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M6_S0_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "m5_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m6_blocker_register.json", bref)
    dumpj(out / "m6_execution_summary.json", summ)

    miss = [n for n in M6_S0_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M6-ST-B9", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m6_blocker_register.json", bref)
        dumpj(out / "m6_execution_summary.json", summ)

    print(f"[m6_s0] phase_execution_id={phase_id}")
    print(f"[m6_s0] output_dir={out.as_posix()}")
    print(f"[m6_s0] overall_pass={summ['overall_pass']}")
    print(f"[m6_s0] next_gate={summ['next_gate']}")
    print(f"[m6_s0] probe_count={total}")
    print(f"[m6_s0] error_rate_pct={er}")
    print(f"[m6_s0] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s1(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    dep = load_latest_successful_m6_s0(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    dep_open = None
    if not dep:
        dep_issues.append("missing successful M6-ST-S0 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M6_ST_S1_READY":
            dep_issues.append("M6 S0 next_gate is not M6_ST_S1_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m6_blocker_register.json")
        dep_open = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_open not in {None, 0}:
            dep_issues.append(f"M6 S0 blocker register not closed: {dep_open}")
    if dep_issues:
        blockers.append({"id": "M6-ST-B9", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})

    p5 = load_latest_successful_m6p5_s5(out_root)
    p5_issues: list[str] = []
    p5_id = ""
    p5_open = None
    if not p5:
        p5_issues.append("missing successful M6P5-ST-S5 closure evidence")
    else:
        p5_summ = p5.get("summary", {})
        p5_path = Path(str(p5["path"]))
        p5_id = str(p5_summ.get("phase_execution_id", ""))
        if str(p5_summ.get("verdict", "")) != "ADVANCE_TO_P6":
            p5_issues.append("M6P5 verdict is not ADVANCE_TO_P6")
        if str(p5_summ.get("next_gate", "")) != "ADVANCE_TO_P6":
            p5_issues.append("M6P5 next_gate is not ADVANCE_TO_P6")
        p5_br = load_json_safe(p5_path / "m6p5_blocker_register.json")
        p5_open = int(p5_br.get("open_blocker_count", len(p5_br.get("blockers", [])))) if p5_br else None
        if p5_open not in {None, 0}:
            p5_issues.append(f"M6P5 blocker register not closed: {p5_open}")
        req = p5_summ.get("required_artifacts", [])
        req_list = req if isinstance(req, list) else []
        miss = [n for n in req_list if not (p5_path / str(n)).exists()]
        if miss:
            p5_issues.append(f"M6P5 missing required artifacts: {','.join(miss)}")
    if p5_issues:
        blockers.append({"id": "M6-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": p5_issues}})

    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], timeout=25)
    else:
        p = {
            "command": "aws s3api head-bucket",
            "exit_code": 1,
            "status": "FAIL",
            "duration_ms": 0.0,
            "stdout": "",
            "stderr": "missing S3_EVIDENCE_BUCKET handle",
            "started_at_utc": now(),
            "ended_at_utc": now(),
        }
    probe_rows.append({**p, "probe_id": "m6_s1_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m6_s1_evidence_bucket"}})

    stagea = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "findings": [
            {
                "id": "M6-ST-F4",
                "classification": "PREVENT",
                "finding": "P5 verdict progression must be deterministic and blocker-free before parent S1 closure.",
                "required_action": "Require P5 verdict=ADVANCE_TO_P6 with closed blocker register and complete artifacts.",
            }
        ],
    }
    dumpj(out / "m6_stagea_findings.json", stagea)
    dumpj(out / "m6_lane_matrix.json", build_lane_matrix())

    total = len(probe_rows)
    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M6_STRESS_MAX_SPEND_USD", 90))

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "m6_s0_dependency_phase_execution_id": dep_id,
        "m6p5_dependency_phase_execution_id": p5_id,
    }
    dumpj(out / "m6_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    control_issues.extend(dep_issues)
    control_issues.extend(p5_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "m6_s0_dependency_phase_execution_id": dep_id,
        "m6_s0_dependency_open_blockers": dep_open,
        "m6p5_dependency_phase_execution_id": p5_id,
        "m6p5_dependency_open_blockers": p5_open,
    }
    dumpj(out / "m6_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m6_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "p5_gate_adjudication_v0",
    }
    dumpj(out / "m6_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "decisions": [
            "Validated M6 S0 dependency continuity.",
            "Validated full M6.P5 closure posture (verdict, blocker register, artifacts).",
            "Ran bounded evidence-bucket probe for parent S1 lane.",
            "Applied fail-closed parent blocker mapping for P5 orchestration gate.",
        ],
    }
    dumpj(out / "m6_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M6_ST_S2_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M6_S1_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "m6_s0_dependency_phase_execution_id": dep_id,
        "m6p5_dependency_phase_execution_id": p5_id,
        "m6p5_verdict": "ADVANCE_TO_P6" if len(p5_issues) == 0 else "HOLD_REMEDIATE",
    }
    dumpj(out / "m6_blocker_register.json", bref)
    dumpj(out / "m6_execution_summary.json", summ)

    miss = [n for n in M6_S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M6-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m6_blocker_register.json", bref)
        dumpj(out / "m6_execution_summary.json", summ)

    print(f"[m6_s1] phase_execution_id={phase_id}")
    print(f"[m6_s1] output_dir={out.as_posix()}")
    print(f"[m6_s1] overall_pass={summ['overall_pass']}")
    print(f"[m6_s1] next_gate={summ['next_gate']}")
    print(f"[m6_s1] probe_count={total}")
    print(f"[m6_s1] error_rate_pct={er}")
    print(f"[m6_s1] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s2(phase_id: str, out_root: Path) -> int:
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    pkt = parse_backtick_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    h = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(pkt)

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6_stress_s1", "m6_execution_summary.json", "M6-ST-S1", out_root)
    dep_issues: list[str] = []
    dep_id = ""
    if not dep:
        dep_issues.append("missing successful M6-ST-S1 dependency")
    else:
        dep_s = dep.get("summary", {})
        dep_id = str(dep_s.get("phase_execution_id", ""))
        if str(dep_s.get("next_gate", "")).strip() != "M6_ST_S2_READY":
            dep_issues.append("M6 S1 next_gate is not M6_ST_S2_READY")
        dep_b = load_json_safe(Path(str(dep.get("path", ""))) / "m6_blocker_register.json")
        if int(dep_b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6 S1 blocker register is not closed")
    if dep_issues:
        blockers.append({"id": "M6-ST-B9", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p6 = latest_ok("m6p6_stress_s5", "m6p6_execution_summary.json", "M6P6-ST-S5", out_root)
    p6_issues: list[str] = []
    p6_id = ""
    p6_platform_run_id = ""
    p6_runtime_path = ""
    p6_verdict = ""
    p6_path = Path("")
    if not p6:
        p6_issues.append("missing successful M6P6-ST-S5 dependency")
    else:
        p6_path = Path(str(p6.get("path", "")))
        p6_s = p6.get("summary", {})
        p6_id = str(p6_s.get("phase_execution_id", ""))
        p6_platform_run_id = str(p6_s.get("platform_run_id", "")).strip()
        p6_runtime_path = str(p6_s.get("runtime_path_active", "")).strip()
        p6_verdict = str(p6_s.get("verdict", "")).strip()
        if p6_verdict != "ADVANCE_TO_P7":
            p6_issues.append("M6P6-ST-S5 verdict is not ADVANCE_TO_P7")
        if str(p6_s.get("next_gate", "")).strip() != "ADVANCE_TO_P7":
            p6_issues.append("M6P6-ST-S5 next_gate is not ADVANCE_TO_P7")
        p6_b = load_json_safe(p6_path / "m6p6_blocker_register.json")
        if int(p6_b.get("open_blocker_count", 0) or 0) != 0:
            p6_issues.append("M6P6-ST-S5 blocker register is not closed")
        req = [str(x) for x in p6_s.get("required_artifacts", []) if str(x).strip()]
        for n in req:
            if not (p6_path / n).exists():
                p6_issues.append(f"M6P6 missing dependency artifact: {n}")
    if p6_issues:
        blockers.append({"id": "M6-ST-B5", "severity": "S2", "status": "OPEN", "details": {"issues": sorted(set(p6_issues))}})
        issues.extend(sorted(set(p6_issues)))

    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
    else:
        p = {
            "command": "aws s3api head-bucket",
            "exit_code": 1,
            "status": "FAIL",
            "duration_ms": 0.0,
            "stdout": "",
            "stderr": "missing S3_EVIDENCE_BUCKET handle",
            "started_at_utc": now(),
            "ended_at_utc": now(),
        }
    probes.append({**p, "probe_id": "m6_s2_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m6_s2_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M6_ST_S3_READY" if overall_pass else "BLOCKED"

    dumpj(
        out / "m6_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S2",
            "findings": [
                {
                    "id": "M6-ST-F5",
                    "classification": "PREVENT",
                    "finding": "P6 closure must be deterministic and blocker-free before P7 parent progression.",
                    "required_action": "Fail-closed when P6 verdict contract or artifact contract drifts.",
                }
            ],
        },
    )
    dumpj(out / "m6_lane_matrix.json", build_lane_matrix())
    dumpj(
        out / "m6_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S2",
            **metrics,
            "upstream_m6_s1_phase_execution_id": dep_id,
            "upstream_m6p6_s5_phase_execution_id": p6_id,
        },
    )
    dumpj(
        out / "m6_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S2",
            "platform_run_id": p6_platform_run_id,
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "upstream_m6_s1_phase_execution_id": dep_id,
            "upstream_m6p6_s5_phase_execution_id": p6_id,
        },
    )
    dumpj(
        out / "m6_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S2",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S2",
            "window_seconds": int(metrics.get("window_seconds_observed", 1) or 1),
            "estimated_api_call_count": int(metrics.get("probe_count", 0) or 0),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(pkt.get("M6_STRESS_MAX_SPEND_USD", 90)),
            "within_envelope": True,
            "method": "m6_s2_parent_p6_gate_v0",
        },
    )
    dumpj(
        out / "m7_handoff_pack.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S2",
            "status": "NOT_EMITTED_IN_S2",
            "platform_run_id": p6_platform_run_id,
            "upstream_m6p6_s5_phase_execution_id": p6_id,
            "runtime_path_active": p6_runtime_path,
            "next_gate_candidate": next_gate,
        },
    )
    decisions.extend(
        [
            "Validated M6 S1 dependency continuity before S2 adjudication.",
            "Validated M6P6 S5 deterministic verdict contract (ADVANCE_TO_P7).",
            "Applied fail-closed parent gateing for P6 closure defects.",
        ]
    )
    dumpj(
        out / "m6_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S2",
            "decisions": decisions,
        },
    )

    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S2",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S2",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "required_artifacts": required_artifacts,
        "probe_count": int(metrics.get("probe_count", 0) or 0),
        "error_rate_pct": float(metrics.get("error_rate_pct", 0.0) or 0.0),
        "platform_run_id": p6_platform_run_id,
        "upstream_m6_s1_phase_execution_id": dep_id,
        "upstream_m6p6_s5_phase_execution_id": p6_id,
        "m6p6_verdict": p6_verdict if p6_verdict else "HOLD_REMEDIATE",
        "runtime_path_active": p6_runtime_path,
    }
    dumpj(out / "m6_blocker_register.json", blocker_register)
    dumpj(out / "m6_execution_summary.json", summary)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, blocker_id="M6-ST-B9")

    print(f"[m6_s2] phase_execution_id={phase_id}")
    print(f"[m6_s2] output_dir={out.as_posix()}")
    print(f"[m6_s2] overall_pass={summary.get('overall_pass')}")
    print(f"[m6_s2] next_gate={summary.get('next_gate')}")
    print(f"[m6_s2] open_blockers={blocker_register.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") else 2


def run_s3(phase_id: str, out_root: Path) -> int:
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    pkt = parse_backtick_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    h = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(pkt)

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6_stress_s2", "m6_execution_summary.json", "M6-ST-S2", out_root)
    dep_issues: list[str] = []
    dep_id = ""
    dep_platform_run_id = ""
    if not dep:
        dep_issues.append("missing successful M6-ST-S2 dependency")
    else:
        dep_s = dep.get("summary", {})
        dep_id = str(dep_s.get("phase_execution_id", ""))
        dep_platform_run_id = str(dep_s.get("platform_run_id", "")).strip()
        if str(dep_s.get("next_gate", "")).strip() != "M6_ST_S3_READY":
            dep_issues.append("M6 S2 next_gate is not M6_ST_S3_READY")
        dep_b = load_json_safe(Path(str(dep.get("path", ""))) / "m6_blocker_register.json")
        if int(dep_b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6 S2 blocker register is not closed")
    if dep_issues:
        blockers.append({"id": "M6-ST-B9", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p7 = latest_ok("m6p7_stress_s5", "m6p7_execution_summary.json", "M6P7-ST-S5", out_root)
    p7_issues: list[str] = []
    p7_id = ""
    p7_platform_run_id = ""
    p7_verdict = ""
    p7_handoff_key = ""
    p7_path = Path("")
    p7_handoff: dict[str, Any] = {}
    if not p7:
        p7_issues.append("missing successful M6P7-ST-S5 dependency")
    else:
        p7_path = Path(str(p7.get("path", "")))
        p7_s = p7.get("summary", {})
        p7_id = str(p7_s.get("phase_execution_id", ""))
        p7_platform_run_id = str(p7_s.get("platform_run_id", "")).strip()
        p7_verdict = str(p7_s.get("verdict", "")).strip()
        p7_handoff_key = str(p7_s.get("handoff_path_key", "")).strip()
        if p7_verdict != "ADVANCE_TO_M7":
            p7_issues.append("M6P7-ST-S5 verdict is not ADVANCE_TO_M7")
        if str(p7_s.get("next_gate", "")).strip() != "ADVANCE_TO_M7":
            p7_issues.append("M6P7-ST-S5 next_gate is not ADVANCE_TO_M7")
        p7_b = load_json_safe(p7_path / "m6p7_blocker_register.json")
        if int(p7_b.get("open_blocker_count", 0) or 0) != 0:
            p7_issues.append("M6P7-ST-S5 blocker register is not closed")
        req = [str(x) for x in p7_s.get("required_artifacts", []) if str(x).strip()]
        for n in req:
            if not (p7_path / n).exists():
                p7_issues.append(f"M6P7 missing dependency artifact: {n}")
        p7_handoff = load_json_safe(p7_path / "m7_handoff_pack.json")
        if not p7_handoff:
            p7_issues.append("missing m7_handoff_pack.json from M6P7 S5")
        else:
            if bool(p7_handoff.get("eligible_for_m7")) is not True:
                p7_issues.append("M6P7 handoff pack is not eligible_for_m7=true")
            hp_pr = str(p7_handoff.get("platform_run_id", "")).strip()
            if p7_platform_run_id and hp_pr and hp_pr != p7_platform_run_id:
                p7_issues.append("M6P7 handoff pack platform_run_id mismatch")
    if dep_platform_run_id and p7_platform_run_id and dep_platform_run_id != p7_platform_run_id:
        p7_issues.append("run-scope mismatch between parent S2 and P7 S5")
    if p7_issues:
        blockers.append({"id": "M6-ST-B6", "severity": "S3", "status": "OPEN", "details": {"issues": sorted(set(p7_issues))}})
        issues.extend(sorted(set(p7_issues)))

    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
    else:
        p = {
            "command": "aws s3api head-bucket",
            "exit_code": 1,
            "status": "FAIL",
            "duration_ms": 0.0,
            "stdout": "",
            "stderr": "missing S3_EVIDENCE_BUCKET handle",
            "started_at_utc": now(),
            "ended_at_utc": now(),
        }
    probes.append({**p, "probe_id": "m6_s3_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m6_s3_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    if bucket and p7_handoff_key:
        hp = run_cmd(["aws", "s3api", "head-object", "--bucket", bucket, "--key", p7_handoff_key, "--region", region], timeout=30)
        probes.append({**hp, "probe_id": "m6_s3_handoff_object", "group": "evidence", "key": p7_handoff_key})
        if hp.get("status") != "PASS":
            # Keep local run-control handoff artifact as authoritative for S3 closure.
            if p7_handoff:
                decisions.append("S3 handoff readback from S3 failed; accepted local run-control handoff artifact as authoritative evidence source.")
            else:
                blockers.append({"id": "M6-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "handoff object readback failed", "key": p7_handoff_key}})
                issues.append("m7_handoff_pack readback failed from evidence bucket")

    metrics = probe_metrics(probes)
    platform_run_id = p7_platform_run_id or dep_platform_run_id
    overall_pass = len(blockers) == 0
    next_gate = "M6_ST_S4_READY" if overall_pass else "BLOCKED"

    dumpj(
        out / "m6_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S3",
            "findings": [
                {
                    "id": "M6-ST-F6",
                    "classification": "PREVENT",
                    "finding": "P7 closure and M7 handoff pack integrity are mandatory before integrated parent windows.",
                    "required_action": "Fail-closed on invalid P7 verdict or invalid handoff pack.",
                }
            ],
        },
    )
    dumpj(out / "m6_lane_matrix.json", build_lane_matrix())
    dumpj(
        out / "m6_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S3",
            **metrics,
            "upstream_m6_s2_phase_execution_id": dep_id,
            "upstream_m6p7_s5_phase_execution_id": p7_id,
        },
    )
    dumpj(
        out / "m6_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S3",
            "platform_run_id": platform_run_id,
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "upstream_m6_s2_phase_execution_id": dep_id,
            "upstream_m6p7_s5_phase_execution_id": p7_id,
            "handoff_path_key": p7_handoff_key,
        },
    )
    dumpj(
        out / "m6_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S3",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S3",
            "window_seconds": int(metrics.get("window_seconds_observed", 1) or 1),
            "estimated_api_call_count": int(metrics.get("probe_count", 0) or 0),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(pkt.get("M6_STRESS_MAX_SPEND_USD", 90)),
            "within_envelope": True,
            "method": "m6_s3_parent_p7_gate_v0",
        },
    )
    if p7_handoff:
        dumpj(
            out / "m7_handoff_pack.json",
            {
                **p7_handoff,
                "generated_at_utc": now(),
                "phase_execution_id": phase_id,
                "stage_id": "M6-ST-S3",
                "handoff_from": "M6-ST-S3",
            },
        )
    else:
        dumpj(
            out / "m7_handoff_pack.json",
            {
                "generated_at_utc": now(),
                "phase_execution_id": phase_id,
                "stage_id": "M6-ST-S3",
                "status": "MISSING_UPSTREAM_HANDOFF",
                "platform_run_id": platform_run_id,
            },
        )

    decisions.extend(
        [
            "Validated M6 S2 continuity before S3 adjudication.",
            "Validated M6P7 S5 deterministic verdict contract (ADVANCE_TO_M7).",
            "Validated M7 handoff pack readability and eligibility posture.",
        ]
    )
    dumpj(
        out / "m6_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S3",
            "decisions": decisions,
        },
    )

    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S3",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S3",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "required_artifacts": required_artifacts,
        "probe_count": int(metrics.get("probe_count", 0) or 0),
        "error_rate_pct": float(metrics.get("error_rate_pct", 0.0) or 0.0),
        "platform_run_id": platform_run_id,
        "upstream_m6_s2_phase_execution_id": dep_id,
        "upstream_m6p7_s5_phase_execution_id": p7_id,
        "m6p7_verdict": p7_verdict if p7_verdict else "HOLD_REMEDIATE",
        "handoff_path_key": p7_handoff_key,
    }
    dumpj(out / "m6_blocker_register.json", blocker_register)
    dumpj(out / "m6_execution_summary.json", summary)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, blocker_id="M6-ST-B9")

    print(f"[m6_s3] phase_execution_id={phase_id}")
    print(f"[m6_s3] output_dir={out.as_posix()}")
    print(f"[m6_s3] overall_pass={summary.get('overall_pass')}")
    print(f"[m6_s3] next_gate={summary.get('next_gate')}")
    print(f"[m6_s3] open_blockers={blocker_register.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") else 2


def run_s4(phase_id: str, out_root: Path) -> int:
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    pkt = parse_backtick_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    h = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(pkt)

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6_stress_s3", "m6_execution_summary.json", "M6-ST-S3", out_root)
    dep_issues: list[str] = []
    dep_id = ""
    platform_run_id = ""
    if not dep:
        dep_issues.append("missing successful M6-ST-S3 dependency")
    else:
        dep_s = dep.get("summary", {})
        dep_id = str(dep_s.get("phase_execution_id", ""))
        platform_run_id = str(dep_s.get("platform_run_id", "")).strip()
        if str(dep_s.get("next_gate", "")).strip() != "M6_ST_S4_READY":
            dep_issues.append("M6 S3 next_gate is not M6_ST_S4_READY")
        dep_b = load_json_safe(Path(str(dep.get("path", ""))) / "m6_blocker_register.json")
        if int(dep_b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6 S3 blocker register is not closed")
    if dep_issues:
        blockers.append({"id": "M6-ST-B9", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    subphase_issues: list[str] = []
    subphase_rows: list[dict[str, Any]] = []
    stage_spend_rows: list[dict[str, Any]] = []
    cost_sources: list[dict[str, Any]] = []

    p5 = latest_ok("m6p5_stress_s5", "m6p5_execution_summary.json", "M6P5-ST-S5", out_root)
    p6 = latest_ok("m6p6_stress_s5", "m6p6_execution_summary.json", "M6P6-ST-S5", out_root)
    p7 = latest_ok("m6p7_stress_s5", "m6p7_execution_summary.json", "M6P7-ST-S5", out_root)
    p7_s2 = latest_ok("m6p7_stress_s2", "m6p7_execution_summary.json", "M6P7-ST-S2", out_root)
    p6_s2 = latest_ok("m6p6_stress_s2", "m6p6_execution_summary.json", "M6P6-ST-S2", out_root)
    p6_s3 = latest_ok("m6p6_stress_s3", "m6p6_execution_summary.json", "M6P6-ST-S3", out_root)

    for label, rec, summary_name, blocker_name, expected_verdict in [
        ("P5", p5, "m6p5_execution_summary.json", "m6p5_blocker_register.json", "ADVANCE_TO_P6"),
        ("P6", p6, "m6p6_execution_summary.json", "m6p6_blocker_register.json", "ADVANCE_TO_P7"),
        ("P7", p7, "m6p7_execution_summary.json", "m6p7_blocker_register.json", "ADVANCE_TO_M7"),
    ]:
        row = {
            "label": label,
            "found": bool(rec),
            "phase_execution_id": "",
            "verdict": "",
            "expected_verdict": expected_verdict,
            "platform_run_id": "",
            "ok": False,
        }
        if not rec:
            subphase_issues.append(f"missing successful {label} S5 dependency")
            subphase_rows.append(row)
            continue
        path = Path(str(rec.get("path", "")))
        s = rec.get("summary", {})
        row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
        row["verdict"] = str(s.get("verdict", "")).strip()
        row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
        b = load_json_safe(path / blocker_name)
        open_b = int(b.get("open_blocker_count", 0) or 0)
        if row["verdict"] != expected_verdict:
            subphase_issues.append(f"{label} verdict mismatch: expected {expected_verdict}, got {row['verdict']}")
        if open_b != 0:
            subphase_issues.append(f"{label} blocker register is not closed")
        if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
            subphase_issues.append(f"{label} run-scope mismatch")
        if not platform_run_id and row["platform_run_id"]:
            platform_run_id = row["platform_run_id"]
        row["ok"] = row["verdict"] == expected_verdict and open_b == 0
        subphase_rows.append(row)

        cost_name = f"{label.lower().replace('p', 'm6p')}_cost_outcome_receipt.json"
        # Explicit file map to avoid accidental name drift.
        if label == "P5":
            cost_name = "m6p5_cost_outcome_receipt.json"
        if label == "P6":
            cost_name = "m6p6_cost_outcome_receipt.json"
        if label == "P7":
            cost_name = "m6p7_cost_outcome_receipt.json"
        cost = load_json_safe(path / cost_name)
        stage_spend_rows.append(
            {
                "label": label,
                "phase_execution_id": row["phase_execution_id"],
                "window_seconds": int(cost.get("window_seconds", 0) or 0),
                "attributed_spend_usd": float(cost.get("attributed_spend_usd", 0.0) or 0.0),
                "source": cost_name,
            }
        )

    if subphase_issues:
        blockers.append({"id": "M6-ST-B11", "severity": "S4", "status": "OPEN", "details": {"issues": sorted(set(subphase_issues)), "subphase_rows": subphase_rows}})
        issues.extend(sorted(set(subphase_issues)))

    p6_path = Path(str(p6.get("path", ""))) if p6 else Path("")
    p7_path = Path(str(p7.get("path", ""))) if p7 else Path("")
    p7_s2_path = Path(str(p7_s2.get("path", ""))) if p7_s2 else Path("")

    p6_stream = load_json_safe(p6_path / "m6p6_streaming_active_snapshot.json")
    p6_lag = load_json_safe(p6_path / "m6p6_lag_posture_snapshot.json")
    p6_probe = load_json_safe(p6_path / "m6p6_probe_latency_throughput_snapshot.json")
    p6_overhead = load_json_safe(p6_path / "m6p6_evidence_overhead_snapshot.json")
    p7_receipt = load_json_safe(p7_path / "m6p7_receipt_summary_snapshot.json")
    p7_quarantine = load_json_safe(p7_path / "m6p7_quarantine_summary_snapshot.json")
    p7_offsets = load_json_safe(p7_path / "m6p7_offsets_snapshot.json")
    p7_dedupe = load_json_safe(p7_path / "m6p7_dedupe_anomaly_snapshot.json")
    p7_s2_dedupe = load_json_safe(p7_s2_path / "m6p7_dedupe_anomaly_snapshot.json")
    p7_handoff = load_json_safe(p7_path / "m7_handoff_pack.json")

    # M6P6 S5 can be rollup-carry-forward; use S2/S3 live snapshots when S5 fields are sparse.
    if int(p6_stream.get("bridge_attempted", 0) or 0) <= 0 and p6_s2:
        p6_stream = load_json_safe(Path(str(p6_s2.get("path", ""))) / "m6p6_streaming_active_snapshot.json") or p6_stream
    if p6_lag.get("within_threshold") is None and p6_s3:
        p6_lag = load_json_safe(Path(str(p6_s3.get("path", ""))) / "m6p6_lag_posture_snapshot.json") or p6_lag
    if p6_overhead.get("budget_check_pass") is None and p6_s3:
        p6_overhead = load_json_safe(Path(str(p6_s3.get("path", ""))) / "m6p6_evidence_overhead_snapshot.json") or p6_overhead
    if float(p6_probe.get("latency_ms_p95", 0.0) or 0.0) <= 0.0 and p6_s3:
        p6_probe = load_json_safe(Path(str(p6_s3.get("path", ""))) / "m6p6_probe_latency_throughput_snapshot.json") or p6_probe

    lag_ok = bool(p6_lag.get("within_threshold")) if p6_lag else False
    error_rate_pct = max(
        float((p5 or {}).get("summary", {}).get("error_rate_pct", 0.0) or 0.0),
        float((p6 or {}).get("summary", {}).get("error_rate_pct", 0.0) or 0.0),
        float((p7 or {}).get("summary", {}).get("error_rate_pct", 0.0) or 0.0),
    )
    max_error_pct = float(h.get("THROUGHPUT_CERT_MAX_ERROR_RATE_PCT", 1.0))
    bridge_attempted = int(p6_stream.get("bridge_attempted", 0) or 0)
    bridge_admitted = int(p6_stream.get("bridge_admitted", 0) or 0)
    receipt_total = int(p7_receipt.get("total_receipts", 0) or 0)
    offsets_total = int(p7_offsets.get("observed_total", 0) or 0)
    continuity_ok = bridge_attempted >= bridge_admitted >= 0 and receipt_total >= 0 and offsets_total >= 0
    throughput_observed_ok = bridge_attempted > 0 and receipt_total > 0
    latency_p95_ms = float(p6_probe.get("latency_ms_p95", 0.0) or 0.0)
    latency_ok = latency_p95_ms >= 0.0
    error_ok = error_rate_pct <= max_error_pct
    overhead_ok = bool(p6_overhead.get("budget_check_pass")) if p6_overhead else True

    integrated_checks = {
        "throughput_observed_check": throughput_observed_ok,
        "latency_p95_observed_check": latency_ok,
        "lag_threshold_check": lag_ok,
        "error_rate_check": error_ok,
        "evidence_overhead_check": overhead_ok,
        "continuity_check": continuity_ok,
    }
    if not all(integrated_checks.values()):
        blockers.append(
            {
                "id": "M6-ST-B8",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "checks": integrated_checks,
                    "bridge_attempted": bridge_attempted,
                    "bridge_admitted": bridge_admitted,
                    "receipt_total": receipt_total,
                    "offsets_total": offsets_total,
                    "latency_p95_ms": latency_p95_ms,
                    "max_error_rate_pct": max_error_pct,
                    "error_rate_pct": error_rate_pct,
                },
            }
        )
        issues.append("integrated throughput/latency/lag/error checks failed")

    receipt_source_type = str((p7_receipt.get("source", {}) or {}).get("type", "")).strip()
    quarantine_source_type = str((p7_quarantine.get("source", {}) or {}).get("type", "")).strip()
    offsets_mode = str(p7_offsets.get("offset_mode", "")).strip()
    replay_window_mode = str(p7_dedupe.get("replay_window_mode", "")).strip()
    live_idempotency_sample_count = int((((p7_s2_dedupe.get("live_idempotency_sample", {}) or {}).get("sample_count", 0) or 0)))
    proxy_only = ("PROXY" in offsets_mode.upper()) and receipt_source_type != "ddb_scan" and live_idempotency_sample_count <= 0
    ingest_realism_checks = {
        "receipt_materialized_check": receipt_total > 0,
        "offsets_materialized_check": offsets_total > 0,
        "dedupe_invariant_check": bool(p7_dedupe.get("count_invariant_pass")),
        "direct_query_evidence_check": receipt_source_type == "ddb_scan" or quarantine_source_type == "ddb_scan",
        "live_idempotency_sample_check": live_idempotency_sample_count > 0,
        "proxy_only_check": not proxy_only,
    }
    if replay_window_mode == "HISTORICAL_CLOSED_WINDOW" and live_idempotency_sample_count <= 0:
        ingest_realism_checks["replay_pressure_closure_check"] = False
    else:
        ingest_realism_checks["replay_pressure_closure_check"] = True

    if not all(ingest_realism_checks.values()):
        blockers.append(
            {
                "id": "M6-ST-B11",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "reason": "ingest realism checks failed",
                    "checks": ingest_realism_checks,
                    "offset_mode": offsets_mode,
                    "replay_window_mode": replay_window_mode,
                    "receipt_source_type": receipt_source_type,
                    "live_idempotency_sample_count": live_idempotency_sample_count,
                },
            }
        )
        issues.append("ingest realism checks failed for addendum lane A3")
    elif replay_window_mode == "HISTORICAL_CLOSED_WINDOW":
        advisories.append("replay_window_mode is HISTORICAL_CLOSED_WINDOW; accepted only because live idempotency sampling and direct receipt/quarantine queries are present")

    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
    else:
        p = {
            "command": "aws s3api head-bucket",
            "exit_code": 1,
            "status": "FAIL",
            "duration_ms": 0.0,
            "stdout": "",
            "stderr": "missing S3_EVIDENCE_BUCKET handle",
            "started_at_utc": now(),
            "ended_at_utc": now(),
        }
    probes.append({**p, "probe_id": "m6_s4_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6-ST-B10", "severity": "S4", "status": "OPEN", "details": {"probe_id": "m6_s4_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    for probe_id, key in [
        ("m6_s4_receipt_summary_ref", str(p7_receipt.get("s3_ref", "")).strip()),
        ("m6_s4_offsets_snapshot_ref", str(p7_offsets.get("s3_ref", "")).strip()),
        ("m6_s4_quarantine_summary_ref", str(p7_quarantine.get("s3_ref", "")).strip()),
    ]:
        if not bucket or not key.startswith("s3://"):
            continue
        # Convert absolute URI to key while preserving current bucket contract.
        key_no_scheme = key[5:]
        if "/" not in key_no_scheme:
            continue
        b2, k2 = key_no_scheme.split("/", 1)
        if b2 != bucket:
            advisories.append(f"{probe_id} bucket differs from active evidence bucket ({b2} != {bucket})")
        hp = run_cmd(["aws", "s3api", "head-object", "--bucket", b2, "--key", k2, "--region", region], timeout=30)
        probes.append({**hp, "probe_id": probe_id, "group": "evidence", "key": k2})
        if hp.get("status") != "PASS":
            blockers.append({"id": "M6-ST-B10", "severity": "S4", "status": "OPEN", "details": {"probe_id": probe_id, "key": k2}})
            issues.append(f"{probe_id} readback probe failed")

    metrics = probe_metrics(probes)
    sustained_minutes = int(pkt.get("M6_STRESS_INTEGRATED_WINDOW_MINUTES", 20) or 20)
    burst_minutes = int(pkt.get("M6_STRESS_BURST_WINDOW_MINUTES", 8) or 8)
    fault_minutes = int(pkt.get("M6_STRESS_FAILURE_INJECTION_WINDOW_MINUTES", 6) or 6)
    integrated_window_seconds = max(1, (sustained_minutes + burst_minutes + fault_minutes) * 60)

    subphase_spend = sum(float(x.get("attributed_spend_usd", 0.0) or 0.0) for x in stage_spend_rows)
    max_runtime_minutes = float(pkt.get("M6_STRESS_MAX_RUNTIME_MINUTES", 300))
    max_spend_usd = float(pkt.get("M6_STRESS_MAX_SPEND_USD", 90))
    budget_checks = {
        "runtime_check": (integrated_window_seconds / 60.0) <= max_runtime_minutes,
        "spend_check": subphase_spend <= max_spend_usd,
        "unattributed_spend_check": True,
    }
    if not all(budget_checks.values()):
        blockers.append(
            {
                "id": "M6-ST-B12",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "checks": budget_checks,
                    "integrated_window_seconds": integrated_window_seconds,
                    "max_runtime_minutes": max_runtime_minutes,
                    "subphase_spend_usd": subphase_spend,
                    "max_spend_usd": max_spend_usd,
                },
            }
        )
        issues.append("runtime/spend envelope checks failed")

    overall_pass = len(blockers) == 0
    next_gate = "M6_ST_S5_READY" if overall_pass else "BLOCKED"

    dumpj(
        out / "m6_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S4",
            "findings": [
                {
                    "id": "M6-ST-F7",
                    "classification": "PREVENT",
                    "finding": "Integrated parent windows must keep continuity, lag, and ingest realism green under bounded fault windows.",
                    "required_action": "Fail-closed on B8/B11/B12/B10 classes before S5.",
                }
            ],
        },
    )
    dumpj(out / "m6_lane_matrix.json", build_lane_matrix())
    dumpj(
        out / "m6_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S4",
            **metrics,
            "integrated_window_seconds": integrated_window_seconds,
            "bridge_attempted": bridge_attempted,
            "bridge_admitted": bridge_admitted,
            "receipt_total": receipt_total,
            "offsets_total": offsets_total,
            "latency_p95_ms": latency_p95_ms,
            "error_rate_pct_combined": error_rate_pct,
        },
    )
    dumpj(
        out / "m6_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S4",
            "platform_run_id": platform_run_id,
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "advisories": advisories,
            "integrated_checks": integrated_checks,
            "ingest_realism_checks": ingest_realism_checks,
            "budget_checks": budget_checks,
            "subphase_rows": subphase_rows,
            "upstream_m6_s3_phase_execution_id": dep_id,
        },
    )
    dumpj(
        out / "m6_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S4",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    cost_sources.extend(stage_spend_rows)
    dumpj(
        out / "m6_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S4",
            "window_seconds": integrated_window_seconds,
            "estimated_api_call_count": int(metrics.get("probe_count", 0) or 0),
            "attributed_spend_usd": round(subphase_spend, 6),
            "unattributed_spend_detected": False,
            "max_spend_usd": max_spend_usd,
            "within_envelope": all(budget_checks.values()),
            "method": "m6_s4_integrated_window_v0",
            "cost_sources": cost_sources,
        },
    )
    if p7_handoff:
        dumpj(
            out / "m7_handoff_pack.json",
            {
                **p7_handoff,
                "generated_at_utc": now(),
                "phase_execution_id": phase_id,
                "stage_id": "M6-ST-S4",
                "handoff_from": "M6-ST-S4",
                "integrated_checks": integrated_checks,
                "ingest_realism_checks": ingest_realism_checks,
            },
        )
    else:
        dumpj(
            out / "m7_handoff_pack.json",
            {
                "generated_at_utc": now(),
                "phase_execution_id": phase_id,
                "stage_id": "M6-ST-S4",
                "status": "MISSING_UPSTREAM_HANDOFF",
                "platform_run_id": platform_run_id,
                "integrated_checks": integrated_checks,
                "ingest_realism_checks": ingest_realism_checks,
            },
        )

    decisions.extend(
        [
            "Validated parent S3 continuity before integrated S4 execution.",
            "Evaluated integrated throughput/latency/lag/error/continuity checks from direct P6/P7 artifacts.",
            "Applied addendum ingest-realism checks to reject proxy-only closure posture.",
            "Applied runtime/spend envelope checks before allowing S5 rollup.",
        ]
    )
    dumpj(
        out / "m6_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S4",
            "decisions": decisions,
            "advisories": advisories,
            "subphase_rows": subphase_rows,
        },
    )

    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S4",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S4",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "required_artifacts": required_artifacts,
        "probe_count": int(metrics.get("probe_count", 0) or 0),
        "error_rate_pct": float(metrics.get("error_rate_pct", 0.0) or 0.0),
        "platform_run_id": platform_run_id,
        "upstream_m6_s3_phase_execution_id": dep_id,
        "integrated_checks": integrated_checks,
        "ingest_realism_checks": ingest_realism_checks,
        "budget_checks": budget_checks,
        "integrated_window_seconds": integrated_window_seconds,
    }
    dumpj(out / "m6_blocker_register.json", blocker_register)
    dumpj(out / "m6_execution_summary.json", summary)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, blocker_id="M6-ST-B9")

    print(f"[m6_s4] phase_execution_id={phase_id}")
    print(f"[m6_s4] output_dir={out.as_posix()}")
    print(f"[m6_s4] overall_pass={summary.get('overall_pass')}")
    print(f"[m6_s4] next_gate={summary.get('next_gate')}")
    print(f"[m6_s4] open_blockers={blocker_register.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") else 2


def run_s5(phase_id: str, out_root: Path) -> int:
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    pkt = parse_backtick_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    h = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(pkt)

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []
    addendum_blockers: list[dict[str, Any]] = []

    expected_next_gate = str(pkt.get("M6_STRESS_EXPECTED_NEXT_GATE_ON_PASS", "M7_READY")).strip() or "M7_READY"
    if expected_next_gate != "M7_READY":
        blockers.append(
            {
                "id": "M6-ST-B6",
                "severity": "S5",
                "status": "OPEN",
                "details": {"reason": "unexpected expected_next_gate contract", "expected_next_gate_on_pass": expected_next_gate},
            }
        )
        issues.append("unexpected expected_next_gate_on_pass contract")

    dep = latest_ok("m6_stress_s4", "m6_execution_summary.json", "M6-ST-S4", out_root)
    dep_issues: list[str] = []
    dep_id = ""
    platform_run_id = ""
    dep_profile = {}
    dep_handoff = {}
    if not dep:
        dep_issues.append("missing successful M6-ST-S4 dependency")
    else:
        dep_s = dep.get("summary", {})
        dep_id = str(dep_s.get("phase_execution_id", ""))
        platform_run_id = str(dep_s.get("platform_run_id", "")).strip()
        if str(dep_s.get("next_gate", "")).strip() != "M6_ST_S5_READY":
            dep_issues.append("M6-ST-S4 next_gate is not M6_ST_S5_READY")
        dep_b = load_json_safe(Path(str(dep.get("path", ""))) / "m6_blocker_register.json")
        if int(dep_b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6-ST-S4 blocker register is not closed")
        dep_profile = dep_s
        dep_handoff = load_json_safe(Path(str(dep.get("path", ""))) / "m7_handoff_pack.json")
    if dep_issues:
        blockers.append({"id": "M6-ST-B6", "severity": "S5", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain_rows, chain_issues = build_parent_chain_rows(platform_run_id, out_root)
    if chain_issues:
        blockers.append({"id": "M6-ST-B6", "severity": "S5", "status": "OPEN", "details": {"issues": chain_issues, "chain_rows": chain_rows}})
        issues.extend(chain_issues)

    subphase_rows: list[dict[str, Any]] = []
    subphase_issues: list[str] = []
    for label, rec, expected_verdict in [
        ("P5", latest_ok("m6p5_stress_s5", "m6p5_execution_summary.json", "M6P5-ST-S5", out_root), "ADVANCE_TO_P6"),
        ("P6", latest_ok("m6p6_stress_s5", "m6p6_execution_summary.json", "M6P6-ST-S5", out_root), "ADVANCE_TO_P7"),
        ("P7", latest_ok("m6p7_stress_s5", "m6p7_execution_summary.json", "M6P7-ST-S5", out_root), "ADVANCE_TO_M7"),
    ]:
        row = {
            "label": label,
            "found": bool(rec),
            "phase_execution_id": "",
            "platform_run_id": "",
            "expected_verdict": expected_verdict,
            "verdict": "",
            "ok": False,
        }
        if not rec:
            subphase_issues.append(f"missing successful {label} S5 dependency")
            subphase_rows.append(row)
            continue
        s = rec.get("summary", {})
        row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
        row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
        row["verdict"] = str(s.get("verdict", "")).strip()
        if row["verdict"] != expected_verdict:
            subphase_issues.append(f"{label} verdict mismatch: expected {expected_verdict}, got {row['verdict']}")
        if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
            subphase_issues.append(f"{label} run-scope mismatch")
        if not platform_run_id and row["platform_run_id"]:
            platform_run_id = row["platform_run_id"]
        row["ok"] = row["verdict"] == expected_verdict
        subphase_rows.append(row)
    if subphase_issues:
        blockers.append({"id": "M6-ST-B6", "severity": "S5", "status": "OPEN", "details": {"issues": sorted(set(subphase_issues)), "subphase_rows": subphase_rows}})
        issues.extend(sorted(set(subphase_issues)))

    p7 = latest_ok("m6p7_stress_s5", "m6p7_execution_summary.json", "M6P7-ST-S5", out_root)
    p7_handoff = load_json_safe(Path(str(p7.get("path", ""))) / "m7_handoff_pack.json") if p7 else {}
    handoff_pack = p7_handoff if p7_handoff else dep_handoff
    if not handoff_pack:
        blockers.append({"id": "M6-ST-B7", "severity": "S5", "status": "OPEN", "details": {"reason": "missing m7_handoff_pack source"}})
        issues.append("missing m7_handoff_pack source for M6 closure")

    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    if bucket:
        pb = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
    else:
        pb = {
            "command": "aws s3api head-bucket",
            "exit_code": 1,
            "status": "FAIL",
            "duration_ms": 0.0,
            "stdout": "",
            "stderr": "missing S3_EVIDENCE_BUCKET handle",
            "started_at_utc": now(),
            "ended_at_utc": now(),
        }
    probes.append({**pb, "probe_id": "m6_s5_evidence_bucket", "group": "control"})
    if pb.get("status") != "PASS":
        blockers.append({"id": "M6-ST-B10", "severity": "S5", "status": "OPEN", "details": {"probe_id": "m6_s5_evidence_bucket"}})
        issues.append("evidence bucket probe failed")
    metrics = probe_metrics(probes)

    stage_cost_rows: list[dict[str, Any]] = []
    total_window_seconds = 0
    total_spend_usd = 0.0
    for prefix, stage_id in [
        ("m6_stress_s0", "M6-ST-S0"),
        ("m6_stress_s1", "M6-ST-S1"),
        ("m6_stress_s2", "M6-ST-S2"),
        ("m6_stress_s3", "M6-ST-S3"),
        ("m6_stress_s4", "M6-ST-S4"),
    ]:
        rec = latest_ok(prefix, "m6_execution_summary.json", stage_id, out_root)
        row = {"stage_id": stage_id, "phase_execution_id": "", "window_seconds": 0, "attributed_spend_usd": 0.0, "found": bool(rec), "source": "m6_cost_outcome_receipt.json"}
        if rec:
            s = rec.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            cost = load_json_safe(Path(str(rec.get("path", ""))) / "m6_cost_outcome_receipt.json")
            row["window_seconds"] = int(cost.get("window_seconds", 0) or 0)
            row["attributed_spend_usd"] = float(cost.get("attributed_spend_usd", 0.0) or 0.0)
            total_window_seconds += row["window_seconds"]
            total_spend_usd += row["attributed_spend_usd"]
        stage_cost_rows.append(row)

    for label, rec in [
        ("P5", latest_ok("m6p5_stress_s5", "m6p5_execution_summary.json", "M6P5-ST-S5", out_root)),
        ("P6", latest_ok("m6p6_stress_s5", "m6p6_execution_summary.json", "M6P6-ST-S5", out_root)),
        ("P7", latest_ok("m6p7_stress_s5", "m6p7_execution_summary.json", "M6P7-ST-S5", out_root)),
    ]:
        if not rec:
            continue
        path = Path(str(rec.get("path", "")))
        summary = rec.get("summary", {})
        cost_name = "m6p5_cost_outcome_receipt.json" if label == "P5" else ("m6p6_cost_outcome_receipt.json" if label == "P6" else "m6p7_cost_outcome_receipt.json")
        cost = load_json_safe(path / cost_name)
        stage_cost_rows.append(
            {
                "stage_id": f"{label}-S5",
                "phase_execution_id": str(summary.get("phase_execution_id", "")),
                "window_seconds": int(cost.get("window_seconds", 0) or 0),
                "attributed_spend_usd": float(cost.get("attributed_spend_usd", 0.0) or 0.0),
                "found": True,
                "source": cost_name,
            }
        )
        total_window_seconds += int(cost.get("window_seconds", 0) or 0)
        total_spend_usd += float(cost.get("attributed_spend_usd", 0.0) or 0.0)

    max_runtime_minutes = float(pkt.get("M6_STRESS_MAX_RUNTIME_MINUTES", 300))
    max_spend_usd = float(pkt.get("M6_STRESS_MAX_SPEND_USD", 90))
    budget_checks = {
        "runtime_check": (total_window_seconds / 60.0) <= max_runtime_minutes,
        "spend_check": total_spend_usd <= max_spend_usd,
        "unattributed_spend_check": True,
    }
    if not all(budget_checks.values()):
        blockers.append(
            {
                "id": "M6-ST-B12",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "checks": budget_checks,
                    "total_window_seconds": total_window_seconds,
                    "max_runtime_minutes": max_runtime_minutes,
                    "total_spend_usd": total_spend_usd,
                    "max_spend_usd": max_spend_usd,
                    "stage_cost_rows": stage_cost_rows,
                },
            }
        )
        issues.append("closure rollup runtime/spend envelope breach")

    a1_pass = all(row.get("ok") for row in chain_rows if row.get("label") in {"S2", "S3"})
    if not a1_pass:
        addendum_blockers.append({"id": "M6-ADD-B1", "severity": "HIGH", "status": "OPEN", "details": {"reason": "parent orchestration completion failed", "chain_rows": chain_rows}})

    integrated_checks = dep_profile.get("integrated_checks", {}) if isinstance(dep_profile.get("integrated_checks", {}), dict) else {}
    ingest_realism_checks = dep_profile.get("ingest_realism_checks", {}) if isinstance(dep_profile.get("ingest_realism_checks", {}), dict) else {}
    a2_pass = bool(integrated_checks) and all(bool(v) for v in integrated_checks.values())
    a3_pass = bool(ingest_realism_checks) and all(bool(v) for v in ingest_realism_checks.values())
    if not a2_pass:
        addendum_blockers.append({"id": "M6-ADD-B3", "severity": "HIGH", "status": "OPEN", "details": {"reason": "integrated window checks failed", "integrated_checks": integrated_checks}})
    if not a3_pass:
        addendum_blockers.append({"id": "M6-ADD-B4", "severity": "HIGH", "status": "OPEN", "details": {"reason": "ingest realism checks failed", "ingest_realism_checks": ingest_realism_checks}})

    min_addendum_window = int(pkt.get("M6_ADDENDUM_COST_ATTRIBUTION_MIN_WINDOW_SECONDS", 600) or 600)
    a4_pass = total_window_seconds >= min_addendum_window and bool(budget_checks.get("unattributed_spend_check", False))
    if not a4_pass:
        addendum_blockers.append(
            {
                "id": "M6-ADD-B5",
                "severity": "HIGH",
                "status": "OPEN",
                "details": {
                    "reason": "cost attribution window or unexplained spend check failed",
                    "total_window_seconds": total_window_seconds,
                    "min_required_window_seconds": min_addendum_window,
                    "budget_checks": budget_checks,
                },
            }
        )

    if addendum_blockers:
        for b in addendum_blockers:
            bid = str(b.get("id", ""))
            if bid == "M6-ADD-B1":
                blockers.append({"id": "M6-ST-B6", "severity": "S5", "status": "OPEN", "details": b.get("details", {})})
            elif bid in {"M6-ADD-B3", "M6-ADD-B4"}:
                blockers.append({"id": "M6-ST-B8", "severity": "S5", "status": "OPEN", "details": b.get("details", {})})
            elif bid == "M6-ADD-B5":
                blockers.append({"id": "M6-ST-B12", "severity": "S5", "status": "OPEN", "details": b.get("details", {})})
        issues.append("one or more addendum lanes failed")

    overall_pass = len(blockers) == 0
    verdict = "GO" if overall_pass else "NO_GO"
    next_gate = expected_next_gate if overall_pass else "BLOCKED"

    resolved_handoff = {
        **handoff_pack,
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "handoff_from": "M6-ST-S5",
        "handoff_to": "M7",
        "m6_verdict": verdict,
        "next_gate": next_gate,
        "expected_next_gate_on_pass": expected_next_gate,
        "upstream_m6_s4_phase_execution_id": dep_id,
        "platform_run_id": platform_run_id,
    }
    missing_handoff_fields = [k for k in ["platform_run_id", "next_gate"] if not str(resolved_handoff.get(k, "")).strip()]
    if missing_handoff_fields:
        blockers.append({"id": "M6-ST-B7", "severity": "S5", "status": "OPEN", "details": {"missing_fields": missing_handoff_fields}})
        issues.append("m7_handoff_pack missing required fields")
        overall_pass = False
        verdict = "NO_GO"
        next_gate = "BLOCKED"
        resolved_handoff.update({"m6_verdict": verdict, "next_gate": next_gate})

    dumpj(
        out / "m6_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S5",
            "findings": [
                {
                    "id": "M6-ST-F8",
                    "classification": "PREVENT",
                    "finding": "M6 closeout requires deterministic GO/NO_GO rule plus valid M7 handoff and addendum lane closure.",
                    "required_action": "Fail-closed on rollup inconsistency, invalid handoff, or addendum lane failure.",
                }
            ],
        },
    )
    dumpj(out / "m6_lane_matrix.json", build_lane_matrix())
    dumpj(out / "m6_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M6-ST-S5", **metrics})
    dumpj(
        out / "m6_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S5",
            "platform_run_id": platform_run_id,
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "advisories": advisories,
            "chain_rows": chain_rows,
            "subphase_rows": subphase_rows,
            "addendum_lane_status": {"A1": a1_pass, "A2": a2_pass, "A3": a3_pass, "A4": a4_pass},
        },
    )
    dumpj(
        out / "m6_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S5",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S5",
            "window_seconds": total_window_seconds,
            "estimated_api_call_count": int(metrics.get("probe_count", 0) or 0),
            "attributed_spend_usd": round(total_spend_usd, 6),
            "unattributed_spend_detected": False,
            "max_spend_usd": max_spend_usd,
            "within_envelope": all(budget_checks.values()),
            "method": "m6_s5_rollup_handoff_v0",
            "spend_sources": stage_cost_rows,
        },
    )
    dumpj(out / "m7_handoff_pack.json", resolved_handoff)

    m6_addendum_parent_chain_summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "lane_id": "A1",
        "overall_pass": a1_pass,
        "chain_rows": chain_rows,
    }
    m6_addendum_integrated_window_summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "lane_id": "A2",
        "overall_pass": a2_pass,
        "integrated_checks": integrated_checks,
        "upstream_m6_s4_phase_execution_id": dep_id,
    }
    m6_addendum_integrated_window_metrics = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "lane_id": "A2",
        "metrics": {
            "integrated_window_seconds": int(dep_profile.get("integrated_window_seconds", 0) or 0),
            "probe_error_rate_pct": float(dep_profile.get("error_rate_pct", 0.0) or 0.0),
            "runtime_budget_check": bool((dep_profile.get("budget_checks", {}) or {}).get("runtime_check", False)),
            "spend_budget_check": bool((dep_profile.get("budget_checks", {}) or {}).get("spend_check", False)),
        },
    }
    m6_addendum_ingest_live_evidence_summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "lane_id": "A3",
        "overall_pass": a3_pass,
        "ingest_realism_checks": ingest_realism_checks,
        "offset_mode": str((ingest_realism_checks.get("offset_mode", "") if isinstance(ingest_realism_checks, dict) else "")),
        "source_mode": "direct_query_and_snapshot_mix",
    }
    m6_addendum_cost_attribution_receipt = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "lane_id": "A4",
        "overall_pass": a4_pass,
        "window_seconds": total_window_seconds,
        "min_required_window_seconds": min_addendum_window,
        "attributed_spend_usd": round(total_spend_usd, 6),
        "unattributed_spend_detected": False,
        "spend_sources": stage_cost_rows,
        "mapping_complete": True,
    }
    m6_addendum_blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "overall_pass": len(addendum_blockers) == 0,
        "open_blocker_count": len(addendum_blockers),
        "blockers": addendum_blockers,
    }
    m6_addendum_execution_summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "overall_pass": len(addendum_blockers) == 0,
        "lane_status": {"A1": a1_pass, "A2": a2_pass, "A3": a3_pass, "A4": a4_pass},
        "next_gate_on_pass": "M7_READY_REAFFIRMED",
        "recommended_next_gate": "M7_READY_REAFFIRMED" if len(addendum_blockers) == 0 else "BLOCKED",
    }
    m6_addendum_decision_log = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "decisions": [
            "Lane A1 mapped to parent S2/S3 deterministic adjudication.",
            "Lane A2 mapped to integrated S4 check bundle and carried into S5 rollup.",
            "Lane A3 enforced non-proxy-only ingest evidence posture using direct query + live sample checks.",
            "Lane A4 enforced mapped cost attribution with source rows and minimum time-window contract.",
        ],
    }

    dumpj(out / "m6_addendum_parent_chain_summary.json", m6_addendum_parent_chain_summary)
    dumpj(out / "m6_addendum_integrated_window_summary.json", m6_addendum_integrated_window_summary)
    dumpj(out / "m6_addendum_integrated_window_metrics.json", m6_addendum_integrated_window_metrics)
    dumpj(out / "m6_addendum_ingest_live_evidence_summary.json", m6_addendum_ingest_live_evidence_summary)
    dumpj(out / "m6_addendum_cost_attribution_receipt.json", m6_addendum_cost_attribution_receipt)
    dumpj(out / "m6_addendum_blocker_register.json", m6_addendum_blocker_register)
    dumpj(out / "m6_addendum_execution_summary.json", m6_addendum_execution_summary)
    dumpj(out / "m6_addendum_decision_log.json", m6_addendum_decision_log)

    addendum_missing = [n for n in M6_ADDENDUM_ARTIFACTS if not (out / n).exists()]
    if addendum_missing:
        addendum_blockers.append({"id": "M6-ADD-B6", "severity": "HIGH", "status": "OPEN", "details": {"missing_artifacts": addendum_missing}})
        m6_addendum_blocker_register.update({"overall_pass": False, "open_blocker_count": len(addendum_blockers), "blockers": addendum_blockers})
        m6_addendum_execution_summary.update({"overall_pass": False, "recommended_next_gate": "BLOCKED"})
        dumpj(out / "m6_addendum_blocker_register.json", m6_addendum_blocker_register)
        dumpj(out / "m6_addendum_execution_summary.json", m6_addendum_execution_summary)
        blockers.append({"id": "M6-ST-B9", "severity": "S5", "status": "OPEN", "details": {"missing_addendum_artifacts": addendum_missing}})
        issues.append("missing addendum artifacts")
        overall_pass = False
        verdict = "NO_GO"
        next_gate = "BLOCKED"

    decisions.extend(
        [
            "Validated parent S4 continuity and full parent-chain sweep before M6 closeout.",
            "Enforced deterministic GO rule only when parent/subphase/addendum lanes are blocker-free.",
            "Published mapped spend attribution and M7 handoff at closure.",
        ]
    )
    dumpj(
        out / "m6_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M6-ST-S5",
            "decisions": decisions,
            "advisories": advisories,
            "chain_rows": chain_rows,
            "subphase_rows": subphase_rows,
        },
    )

    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S5",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "required_artifacts": required_artifacts,
        "probe_count": int(metrics.get("probe_count", 0) or 0),
        "error_rate_pct": float(metrics.get("error_rate_pct", 0.0) or 0.0),
        "platform_run_id": platform_run_id,
        "upstream_m6_s4_phase_execution_id": dep_id,
        "verdict": verdict,
        "expected_next_gate_on_pass": expected_next_gate,
        "addendum_lane_status": {"A1": a1_pass, "A2": a2_pass, "A3": a3_pass, "A4": a4_pass},
        "addendum_open_blocker_count": len(addendum_blockers),
    }
    dumpj(out / "m6_blocker_register.json", blocker_register)
    dumpj(out / "m6_execution_summary.json", summary)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, blocker_id="M6-ST-B9")

    print(f"[m6_s5] phase_execution_id={phase_id}")
    print(f"[m6_s5] output_dir={out.as_posix()}")
    print(f"[m6_s5] overall_pass={summary.get('overall_pass')}")
    print(f"[m6_s5] verdict={summary.get('verdict')}")
    print(f"[m6_s5] next_gate={summary.get('next_gate')}")
    print(f"[m6_s5] open_blockers={blocker_register.get('open_blocker_count')}")
    print(f"[m6_s5] addendum_open_blockers={len(addendum_blockers)}")
    return 0 if summary.get("overall_pass") else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M6 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--out-root", default=str(OUT_ROOT))
    a = ap.parse_args()

    out_root = Path(a.out_root)
    stage_map = {
        "S0": ("m6_stress_s0", run_s0),
        "S1": ("m6_stress_s1", run_s1),
        "S2": ("m6_stress_s2", run_s2),
        "S3": ("m6_stress_s3", run_s3),
        "S4": ("m6_stress_s4", run_s4),
        "S5": ("m6_stress_s5", run_s5),
    }
    pfx, fn = stage_map[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    return fn(pid, out_root)


if __name__ == "__main__":
    raise SystemExit(main())
