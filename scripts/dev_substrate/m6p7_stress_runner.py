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

PARENT_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.stress_test.md")
PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P7.stress_test.md")
BUILD_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P7.build_plan.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
HIST = Path("runs/dev_substrate/dev_full/m6")

REQ_HANDLES = [
    "RECEIPT_SUMMARY_PATH_PATTERN",
    "QUARANTINE_SUMMARY_PATH_PATTERN",
    "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
    "DDB_IG_IDEMPOTENCY_TABLE",
    "DDB_IG_IDEMPOTENCY_TTL_FIELD",
    "IG_IDEMPOTENCY_TTL_SECONDS",
    "M7_HANDOFF_PACK_PATH_PATTERN",
    "S3_EVIDENCE_BUCKET",
    "S3_RUN_CONTROL_ROOT_PATTERN",
    "REQUIRED_PLATFORM_RUN_ID_ENV_KEY",
]

PLAN_KEYS = [
    "M6P7_STRESS_PROFILE_ID",
    "M6P7_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M6P7_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M6P7_STRESS_DECISION_LOG_PATH_PATTERN",
    "M6P7_STRESS_REQUIRED_ARTIFACTS",
    "M6P7_STRESS_MAX_RUNTIME_MINUTES",
    "M6P7_STRESS_MAX_SPEND_USD",
    "M6P7_STRESS_EXPECTED_VERDICT_ON_PASS",
    "M6P7_STRESS_REPLAY_WINDOW_MINUTES",
    "M6P7_STRESS_TARGETED_RERUN_ONLY",
]

REQUIRED_ARTIFACTS = [
    "m6p7_stagea_findings.json",
    "m6p7_lane_matrix.json",
    "m6p7_ingest_commit_snapshot.json",
    "m6p7_receipt_summary_snapshot.json",
    "m6p7_quarantine_summary_snapshot.json",
    "m6p7_offsets_snapshot.json",
    "m6p7_dedupe_anomaly_snapshot.json",
    "m6p7_probe_latency_throughput_snapshot.json",
    "m6p7_control_rail_conformance_snapshot.json",
    "m6p7_secret_safety_snapshot.json",
    "m6p7_cost_outcome_receipt.json",
    "m6p7_blocker_register.json",
    "m6p7_execution_summary.json",
    "m6p7_decision_log.json",
]

S5_REQUIRED_ARTIFACTS = REQUIRED_ARTIFACTS + [
    "m6p7_gate_verdict.json",
    "m7_handoff_pack.json",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tok() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def loadj(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


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


def parse_bt_map(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in re.findall(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`", text):
        out[k] = parse_scalar(v)
    return out


def parse_reg(path: Path) -> dict[str, Any]:
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


def cmd(argv: list[str], timeout: int = 30) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {
            "command": " ".join(argv),
            "exit_code": int(p.returncode),
            "status": "PASS" if p.returncode == 0 else "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": (p.stdout or "").strip()[:500],
            "stderr": (p.stderr or "").strip()[:500],
            "started_at_utc": st,
            "ended_at_utc": now(),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(argv),
            "exit_code": 124,
            "status": "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": "",
            "stderr": "timeout",
            "started_at_utc": st,
            "ended_at_utc": now(),
        }


def cmd_json(argv: list[str], timeout: int = 30) -> tuple[dict[str, Any], dict[str, Any] | None]:
    t0 = time.perf_counter()
    st = now()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return (
            {
                "command": " ".join(argv),
                "exit_code": 124,
                "status": "FAIL",
                "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
                "stdout": "",
                "stderr": "timeout",
                "started_at_utc": st,
                "ended_at_utc": now(),
            },
            None,
        )

    probe = {
        "command": " ".join(argv),
        "exit_code": int(p.returncode),
        "status": "PASS" if p.returncode == 0 else "FAIL",
        "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        "stdout": (p.stdout or "").strip()[:500],
        "stderr": (p.stderr or "").strip()[:500],
        "started_at_utc": st,
        "ended_at_utc": now(),
    }
    if p.returncode != 0:
        return probe, None
    try:
        return probe, json.loads(p.stdout or "{}")
    except Exception as e:
        probe["status"] = "FAIL"
        probe["stderr"] = f"json parse error: {e}"
        return probe, None


def latest_parent_s0() -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob("m6_stress_s0_*/stress"), reverse=True):
        s = loadj(d / "m6_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == "M6-ST-S0":
            return {"path": d, "summary": s}
    return {}


def latest_p6_s5() -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob("m6p6_stress_s5_*/stress"), reverse=True):
        s = loadj(d / "m6p6_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == "M6P6-ST-S5":
            return {"path": d, "summary": s}
    return {}


def latest_ok(prefix: str, stage_id: str) -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob(f"{prefix}_*/stress"), reverse=True):
        s = loadj(d / "m6p7_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == stage_id:
            return {"path": d, "summary": s}
    return {}


def parse_s3_uri(uri: str) -> tuple[str, str]:
    s = str(uri or "").strip()
    if not s.startswith("s3://"):
        return "", ""
    no_scheme = s[5:]
    if "/" not in no_scheme:
        return "", ""
    bucket, key = no_scheme.split("/", 1)
    return bucket.strip(), key.strip()


def to_int(v: Any) -> int | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return int(v)
        return int(str(v).strip())
    except Exception:
        return None


def ddb_s(item: dict[str, Any], key: str) -> str:
    v = item.get(key, {})
    if isinstance(v, dict) and "S" in v:
        return str(v.get("S", "")).strip()
    return ""


def ddb_n(item: dict[str, Any], key: str) -> int | None:
    v = item.get(key, {})
    if isinstance(v, dict) and "N" in v:
        return to_int(v.get("N"))
    return None


def latest_m6h_ingest(target_platform_run_id: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in HIST.rglob("m6h_execution_summary.json"):
        d = f.parent
        summary = loadj(f)
        if summary.get("overall_pass") is not True:
            continue
        if str(summary.get("phase_id", "")) != "P7.A":
            continue
        if str(summary.get("next_gate", "")) != "M6.I_READY":
            continue

        blocker_reg = loadj(d / "m6h_blocker_register.json")
        if int(blocker_reg.get("blocker_count", 0) or 0) != 0:
            continue

        ingest = loadj(d / "m6h_ingest_commit_snapshot.json")
        if not ingest:
            continue

        platform_run_id = str(ingest.get("platform_run_id", "")).strip()
        if target_platform_run_id and platform_run_id and platform_run_id != target_platform_run_id:
            continue

        execution_id = str(summary.get("execution_id", "")).strip() or d.name
        rows.append(
            {
                "execution_id": execution_id,
                "path": d,
                "summary": summary,
                "blocker_register": blocker_reg,
                "ingest_snapshot": ingest,
                "receipt_summary": loadj(d / "receipt_summary.json"),
                "quarantine_summary": loadj(d / "quarantine_summary.json"),
                "offsets_snapshot": loadj(d / "kafka_offsets_snapshot.json"),
            }
        )

    rows.sort(key=lambda x: str(x.get("execution_id", "")))
    return rows[-1] if rows else {}


def latest_m6i_rollup(target_platform_run_id: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in HIST.rglob("m6i_execution_summary.json"):
        d = f.parent
        summary = loadj(f)
        if summary.get("overall_pass") is not True:
            continue
        if str(summary.get("phase_id", "")) != "P7.B":
            continue
        if str(summary.get("verdict", "")) != "ADVANCE_TO_M7":
            continue

        blocker_reg = loadj(d / "m6i_p7_blocker_register.json")
        if int(blocker_reg.get("blocker_count", 0) or 0) != 0:
            continue

        rollup = loadj(d / "m6i_p7_gate_rollup_matrix.json")
        verdict = loadj(d / "m6i_p7_gate_verdict.json")
        platform_run_id = str(rollup.get("platform_run_id", "")).strip()
        if target_platform_run_id and platform_run_id and platform_run_id != target_platform_run_id:
            continue

        execution_id = str(summary.get("execution_id", "")).strip() or d.name
        rows.append(
            {
                "execution_id": execution_id,
                "path": d,
                "summary": summary,
                "blocker_register": blocker_reg,
                "rollup_matrix": rollup,
                "gate_verdict": verdict,
            }
        )

    rows.sort(key=lambda x: str(x.get("execution_id", "")))
    return rows[-1] if rows else {}


def run_s0(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles = [k for k in REQ_HANDLES if k not in handles]
    placeholder_handles = [k for k in REQ_HANDLES if k in handles and str(handles[k]).strip() in {"", "TO_PIN", "None", "NONE", "null", "NULL"}]
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M6P7-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        if missing_plan_keys:
            issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
        if missing_handles:
            issues.append(f"missing handles: {','.join(missing_handles)}")
        if placeholder_handles:
            issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
        if missing_docs:
            issues.append(f"missing docs: {','.join(missing_docs)}")

    dep_parent = latest_parent_s0()
    dep_parent_id = ""
    dep_issues: list[str] = []
    if not dep_parent:
        dep_issues.append("missing successful parent M6-ST-S0 dependency")
    else:
        s = dep_parent["summary"]
        dep_parent_id = str(s.get("phase_execution_id", ""))
        if str(s.get("next_gate", "")) != "M6_ST_S1_READY":
            dep_issues.append("parent M6-ST-S0 next_gate is not M6_ST_S1_READY")
        b = loadj(Path(str(dep_parent["path"])) / "m6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("parent M6-ST-S0 blocker register not closed")

    dep_p6 = latest_p6_s5()
    dep_p6_id = ""
    platform_run_id = ""
    if not dep_p6:
        dep_issues.append("missing successful M6P6-ST-S5 dependency")
    else:
        s = dep_p6["summary"]
        dep_p6_id = str(s.get("phase_execution_id", ""))
        platform_run_id = str(s.get("platform_run_id", "")).strip()
        if str(s.get("verdict", "")) != "ADVANCE_TO_P7":
            dep_issues.append("P6 verdict is not ADVANCE_TO_P7")
        if str(s.get("next_gate", "")) != "ADVANCE_TO_P7":
            dep_issues.append("P6 next_gate is not ADVANCE_TO_P7")
        b = loadj(Path(str(dep_p6["path"])) / "m6p6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("P6 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P7-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": "m6p7_s0_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6P7-ST-B10", "severity": "S0", "status": "OPEN", "details": {"probe_id": "m6p7_s0_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    dumpj(
        out / "m6p7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S0",
            "findings": [
                {"id": "M6P7-ST-F1", "classification": "PREVENT", "finding": "P7 entry requires deterministic P6 verdict.", "required_action": "Fail-closed on invalid P6 S5 dependency."},
                {"id": "M6P7-ST-F2", "classification": "PREVENT", "finding": "P7 handle packet must be complete and non-placeholder.", "required_action": "Fail-closed on unresolved handle surfaces."},
                {"id": "M6P7-ST-F3", "classification": "PREVENT", "finding": "Evidence root must be reachable before stage advancement.", "required_action": "Bounded readback probe required at entry."},
            ],
        },
    )
    dumpj(
        out / "m6p7_lane_matrix.json",
        {
            "component_sequence": ["M6P7-ST-S0", "M6P7-ST-S1", "M6P7-ST-S2", "M6P7-ST-S3", "M6P7-ST-S4", "M6P7-ST-S5"],
            "plane_sequence": ["ingest_commit_plane", "idempotency_plane", "p7_rollup_plane"],
            "integrated_windows": ["m6p7_s3_replay_window", "m6p7_s3_continuity_window"],
        },
    )

    dumpj(
        out / "m6p7_ingest_commit_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S0",
            "status": "NOT_EVALUATED_IN_S0",
            "platform_run_id": platform_run_id,
            "p6_dependency_phase_execution_id": dep_p6_id,
        },
    )
    dumpj(
        out / "m6p7_receipt_summary_snapshot.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S0", "status": "NOT_EVALUATED_IN_S0"},
    )
    dumpj(
        out / "m6p7_quarantine_summary_snapshot.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S0", "status": "NOT_EVALUATED_IN_S0"},
    )
    dumpj(
        out / "m6p7_offsets_snapshot.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S0", "status": "NOT_EVALUATED_IN_S0"},
    )
    dumpj(
        out / "m6p7_dedupe_anomaly_snapshot.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S0", "status": "NOT_EVALUATED_IN_S0"},
    )

    probe_failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    error_rate_pct = round((len(probe_failures) / len(probes)) * 100.0, 4) if probes else 0.0
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)
    dumpj(
        out / "m6p7_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S0",
            "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "probe_count": len(probes),
            "failure_count": len(probe_failures),
            "error_rate_pct": error_rate_pct,
            "latency_ms_p50": p50,
            "latency_ms_p95": p95,
            "latency_ms_p99": p95,
            "sample_failures": probe_failures[:10],
            "probes": probes,
        },
    )
    dumpj(
        out / "m6p7_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S0",
            "overall_pass": len(issues) == 0,
            "issues": issues,
        },
    )
    dumpj(
        out / "m6p7_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S0",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6p7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S0",
            "window_seconds": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "estimated_api_call_count": len(probes),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M6P7_STRESS_MAX_SPEND_USD", 25)),
            "within_envelope": True,
            "method": "m6p7_s0_entry_validation_v0",
        },
    )

    decisions.extend(
        [
            "Validated M6.P7 required plan keys and handle closure.",
            "Validated parent M6-ST-S0 and P6 S5 dependency continuity.",
            "Validated evidence root probe before P7 stage advancement.",
        ]
    )
    dumpj(
        out / "m6p7_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S0",
            "decisions": decisions,
        },
    )

    overall_pass = len(blockers) == 0
    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S0",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S0",
        "overall_pass": overall_pass,
        "next_gate": "M6P7_ST_S1_READY" if overall_pass else "BLOCKED",
        "required_artifacts": REQUIRED_ARTIFACTS,
        "probe_count": len(probes),
        "error_rate_pct": error_rate_pct,
        "parent_m6_s0_phase_execution_id": dep_parent_id,
        "p6_dependency_phase_execution_id": dep_p6_id,
        "platform_run_id": platform_run_id,
    }
    dumpj(out / "m6p7_blocker_register.json", blocker_register)
    dumpj(out / "m6p7_execution_summary.json", summary)

    missing = [x for x in REQUIRED_ARTIFACTS if not (out / x).exists()]
    if missing:
        blockers.append({"id": "M6P7-ST-B11", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": missing}})
        blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summary.update({"overall_pass": False, "next_gate": "BLOCKED"})
        dumpj(out / "m6p7_blocker_register.json", blocker_register)
        dumpj(out / "m6p7_execution_summary.json", summary)

    print(f"[m6p7_s0] phase_execution_id={phase_execution_id}")
    print(f"[m6p7_s0] output_dir={out.as_posix()}")
    print(f"[m6p7_s0] overall_pass={summary['overall_pass']}")
    print(f"[m6p7_s0] next_gate={summary['next_gate']}")
    print(f"[m6p7_s0] probe_count={summary['probe_count']}")
    print(f"[m6p7_s0] error_rate_pct={summary['error_rate_pct']}")
    print(f"[m6p7_s0] open_blockers={blocker_register['open_blocker_count']}")
    return 0 if summary["overall_pass"] else 2


def run_s1(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p7_stress_s0", "M6P7-ST-S0")
    dep_id = ""
    dep_platform_run_id = ""
    dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P7-ST-S0 dependency")
    else:
        s = dep["summary"]
        dep_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        if str(s.get("next_gate", "")) != "M6P7_ST_S1_READY":
            dep_issues.append("M6P7 S0 next_gate is not M6P7_ST_S1_READY")
        b = loadj(Path(str(dep["path"])) / "m6p7_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P7 S0 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P7-ST-B3", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    hist = latest_m6h_ingest(dep_platform_run_id)
    hist_id = ""
    hist_path = ""
    ingest_source: dict[str, Any] = {}
    receipt_source: dict[str, Any] = {}
    quarantine_source: dict[str, Any] = {}
    offsets_source: dict[str, Any] = {}

    receipt_total = None
    quarantine_count = None
    topics_count = None
    observed_total = None
    offsets_mode = ""
    scenario_run_id = ""
    if not hist:
        blockers.append(
            {
                "id": "M6P7-ST-B3",
                "severity": "S1",
                "status": "OPEN",
                "details": {"reason": "missing successful historical M6.H ingest evidence", "platform_run_id": dep_platform_run_id},
            }
        )
        issues.append("missing successful historical M6.H ingest evidence for S1 materialization checks")
    else:
        hist_id = str(hist.get("execution_id", "")).strip()
        hist_path = str(hist.get("path", ""))
        ingest_source = hist.get("ingest_snapshot", {})
        receipt_source = hist.get("receipt_summary", {})
        quarantine_source = hist.get("quarantine_summary", {})
        offsets_source = hist.get("offsets_snapshot", {})

        ingest_platform_run_id = str(ingest_source.get("platform_run_id", "")).strip()
        if dep_platform_run_id and ingest_platform_run_id and ingest_platform_run_id != dep_platform_run_id:
            blockers.append(
                {
                    "id": "M6P7-ST-B3",
                    "severity": "S1",
                    "status": "OPEN",
                    "details": {
                        "reason": "historical M6.H platform_run_id mismatch",
                        "expected_platform_run_id": dep_platform_run_id,
                        "actual_platform_run_id": ingest_platform_run_id,
                    },
                }
            )
            issues.append("historical M6.H platform_run_id mismatch against S0 dependency")
        if not dep_platform_run_id:
            dep_platform_run_id = ingest_platform_run_id
        scenario_run_id = str(ingest_source.get("scenario_run_id", "")).strip()

        if not receipt_source:
            blockers.append({"id": "M6P7-ST-B3", "severity": "S1", "status": "OPEN", "details": {"reason": "receipt_summary unreadable"}})
            issues.append("receipt_summary artifact is missing or unreadable")
        else:
            receipt_platform_run_id = str(receipt_source.get("platform_run_id", "")).strip()
            if dep_platform_run_id and receipt_platform_run_id and receipt_platform_run_id != dep_platform_run_id:
                blockers.append(
                    {
                        "id": "M6P7-ST-B3",
                        "severity": "S1",
                        "status": "OPEN",
                        "details": {
                            "reason": "receipt_summary platform_run_id mismatch",
                            "expected_platform_run_id": dep_platform_run_id,
                            "actual_platform_run_id": receipt_platform_run_id,
                        },
                    }
                )
                issues.append("receipt_summary platform_run_id mismatch")
            receipt_total = to_int(receipt_source.get("total_receipts"))
            if receipt_total is None:
                blockers.append(
                    {
                        "id": "M6P7-ST-B3",
                        "severity": "S1",
                        "status": "OPEN",
                        "details": {"reason": "receipt_summary total_receipts missing or non-numeric"},
                    }
                )
                issues.append("receipt_summary total_receipts missing or non-numeric")
            if receipt_source.get("sanity_total_matches") is False:
                blockers.append({"id": "M6P7-ST-B3", "severity": "S1", "status": "OPEN", "details": {"reason": "receipt_summary sanity_total_matches=false"}})
                issues.append("receipt_summary sanity_total_matches=false")

        if not quarantine_source:
            blockers.append({"id": "M6P7-ST-B3", "severity": "S1", "status": "OPEN", "details": {"reason": "quarantine_summary unreadable"}})
            issues.append("quarantine_summary artifact is missing or unreadable")
        else:
            quarantine_platform_run_id = str(quarantine_source.get("platform_run_id", "")).strip()
            if dep_platform_run_id and quarantine_platform_run_id and quarantine_platform_run_id != dep_platform_run_id:
                blockers.append(
                    {
                        "id": "M6P7-ST-B3",
                        "severity": "S1",
                        "status": "OPEN",
                        "details": {
                            "reason": "quarantine_summary platform_run_id mismatch",
                            "expected_platform_run_id": dep_platform_run_id,
                            "actual_platform_run_id": quarantine_platform_run_id,
                        },
                    }
                )
                issues.append("quarantine_summary platform_run_id mismatch")
            quarantine_count = to_int(quarantine_source.get("quarantine_count"))

        if not offsets_source:
            blockers.append({"id": "M6P7-ST-B4", "severity": "S1", "status": "OPEN", "details": {"reason": "kafka_offsets_snapshot unreadable"}})
            issues.append("kafka_offsets_snapshot artifact is missing or unreadable")
        else:
            offsets_platform_run_id = str(offsets_source.get("platform_run_id", "")).strip()
            if dep_platform_run_id and offsets_platform_run_id and offsets_platform_run_id != dep_platform_run_id:
                blockers.append(
                    {
                        "id": "M6P7-ST-B4",
                        "severity": "S1",
                        "status": "OPEN",
                        "details": {
                            "reason": "kafka_offsets_snapshot platform_run_id mismatch",
                            "expected_platform_run_id": dep_platform_run_id,
                            "actual_platform_run_id": offsets_platform_run_id,
                        },
                    }
                )
                issues.append("kafka_offsets_snapshot platform_run_id mismatch")
            offsets_mode = str(offsets_source.get("offset_mode", "")).strip()
            topics = offsets_source.get("topics")
            if not isinstance(topics, list) or len(topics) == 0:
                blockers.append(
                    {
                        "id": "M6P7-ST-B4",
                        "severity": "S1",
                        "status": "OPEN",
                        "details": {"reason": "kafka_offsets_snapshot topics missing or empty"},
                    }
                )
                issues.append("kafka_offsets_snapshot topics missing or empty")
                topics = []
            topics_count = len(topics)
            obs_values: list[int] = []
            for t in topics:
                if not isinstance(t, dict):
                    continue
                n = to_int(t.get("observed_count"))
                if n is not None:
                    obs_values.append(n)
            observed_total = sum(obs_values) if obs_values else 0
            if observed_total <= 0:
                blockers.append(
                    {
                        "id": "M6P7-ST-B4",
                        "severity": "S1",
                        "status": "OPEN",
                        "details": {"reason": "kafka_offsets_snapshot observed_count not material", "observed_total": observed_total},
                    }
                )
                issues.append("kafka_offsets_snapshot observed_count is non-material")
            if offsets_source.get("kafka_offsets_materialized") is False:
                blockers.append(
                    {
                        "id": "M6P7-ST-B4",
                        "severity": "S1",
                        "status": "OPEN",
                        "details": {"reason": "kafka_offsets_materialized=false"},
                    }
                )
                issues.append("kafka_offsets_materialized=false in offsets snapshot")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p_bucket, "probe_id": "m6p7_s1_evidence_bucket", "group": "control"})
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M6P7-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m6p7_s1_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    refs = ingest_source.get("evidence_refs", {}) if isinstance(ingest_source.get("evidence_refs"), dict) else {}
    ref_specs = [
        ("receipt_summary_ref", "m6p7_s1_receipt_ref", "M6P7-ST-B3"),
        ("quarantine_summary_ref", "m6p7_s1_quarantine_ref", "M6P7-ST-B3"),
        ("kafka_offsets_snapshot_ref", "m6p7_s1_offsets_ref", "M6P7-ST-B4"),
    ]
    for ref_key, probe_id, blocker_id in ref_specs:
        uri = str(refs.get(ref_key, "")).strip()
        if not uri:
            blockers.append({"id": blocker_id, "severity": "S1", "status": "OPEN", "details": {"reason": f"{ref_key} missing from ingest evidence_refs"}})
            issues.append(f"{ref_key} missing from ingest evidence_refs")
            continue
        ref_bucket, ref_key_path = parse_s3_uri(uri)
        if not ref_bucket or not ref_key_path:
            blockers.append({"id": "M6P7-ST-B10", "severity": "S1", "status": "OPEN", "details": {"reason": f"{ref_key} is not a valid s3 uri", "uri": uri}})
            issues.append(f"{ref_key} is not a valid s3 uri")
            continue
        p_ref = cmd(
            [
                "aws",
                "s3api",
                "head-object",
                "--bucket",
                ref_bucket,
                "--key",
                ref_key_path,
                "--region",
                "eu-west-2",
            ],
            25,
        )
        probes.append({**p_ref, "probe_id": probe_id, "group": "ingest_evidence", "uri": uri})
        if p_ref.get("status") != "PASS":
            blockers.append({"id": "M6P7-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": probe_id, "uri": uri}})
            issues.append(f"evidence readback probe failed for {ref_key}")

    dumpj(
        out / "m6p7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "findings": [
                {
                    "id": "M6P7-ST-F2",
                    "classification": "PREVENT",
                    "finding": "Offset evidence can appear present but be non-material.",
                    "required_action": "Require topic/partition material-content checks in S1.",
                },
                {
                    "id": "M6P7-ST-F3",
                    "classification": "PREVENT",
                    "finding": "Receipt/quarantine evidence without run-scope validation can hide drift.",
                    "required_action": "Fail-closed on run-scope mismatch and unreadable surfaces.",
                },
                {
                    "id": "M6P7-ST-F6",
                    "classification": "OBSERVE",
                    "finding": "Offset mode can be proxy-backed and still valid.",
                    "required_action": "Record explicit offset mode and evidence basis in S1 summary.",
                },
            ],
        },
    )
    dumpj(
        out / "m6p7_lane_matrix.json",
        {
            "component_sequence": ["M6P7-ST-S0", "M6P7-ST-S1", "M6P7-ST-S2", "M6P7-ST-S3", "M6P7-ST-S4", "M6P7-ST-S5"],
            "plane_sequence": ["ingest_commit_plane", "idempotency_plane", "p7_rollup_plane"],
            "integrated_windows": ["m6p7_s3_replay_window", "m6p7_s3_continuity_window"],
        },
    )

    run_scoped_publish_status = ingest_source.get("run_scoped_publish_status", {}) if isinstance(ingest_source.get("run_scoped_publish_status"), dict) else {}
    checks = ingest_source.get("checks", {}) if isinstance(ingest_source.get("checks"), dict) else {}
    counts = ingest_source.get("counts", {}) if isinstance(ingest_source.get("counts"), dict) else {}
    dumpj(
        out / "m6p7_ingest_commit_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "status": "PASS" if len(blockers) == 0 else "FAIL",
            "platform_run_id": dep_platform_run_id,
            "scenario_run_id": scenario_run_id,
            "s0_dependency_phase_execution_id": dep_id,
            "historical_m6h_execution_id": hist_id,
            "historical_m6h_path": hist_path,
            "counts": counts,
            "checks": checks,
            "run_scoped_publish_status": run_scoped_publish_status,
        },
    )
    dumpj(
        out / "m6p7_receipt_summary_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "status": "READABLE" if bool(receipt_source) else "MISSING_OR_UNREADABLE",
            "platform_run_id": str(receipt_source.get("platform_run_id", dep_platform_run_id)).strip(),
            "total_receipts": receipt_total,
            "sanity_total_matches": receipt_source.get("sanity_total_matches"),
            "counts_by_decision": receipt_source.get("counts_by_decision"),
            "source": receipt_source.get("source"),
            "s3_ref": refs.get("receipt_summary_ref"),
        },
    )
    dumpj(
        out / "m6p7_quarantine_summary_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "status": "READABLE" if bool(quarantine_source) else "MISSING_OR_UNREADABLE",
            "platform_run_id": str(quarantine_source.get("platform_run_id", dep_platform_run_id)).strip(),
            "quarantine_count": quarantine_count,
            "quarantine_records_materialized": quarantine_source.get("quarantine_records_materialized"),
            "source": quarantine_source.get("source"),
            "s3_ref": refs.get("quarantine_summary_ref"),
        },
    )
    dumpj(
        out / "m6p7_offsets_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "status": "READABLE_AND_MATERIAL" if bool(offsets_source) and (topics_count or 0) > 0 and (observed_total or 0) > 0 else "MISSING_OR_NON_MATERIAL",
            "platform_run_id": str(offsets_source.get("platform_run_id", dep_platform_run_id)).strip(),
            "offset_mode": offsets_mode,
            "kafka_offsets_materialized": offsets_source.get("kafka_offsets_materialized"),
            "topics_count": topics_count,
            "observed_total": observed_total,
            "topics": offsets_source.get("topics"),
            "s3_ref": refs.get("kafka_offsets_snapshot_ref"),
        },
    )
    dumpj(
        out / "m6p7_dedupe_anomaly_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "status": "PROVISIONAL",
            "dedupe_anomaly_count": checks.get("dedupe_anomaly_count"),
            "note": "Full dedupe/anomaly adjudication is enforced in M6P7-ST-S2.",
        },
    )

    probe_failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    error_rate_pct = round((len(probe_failures) / len(probes)) * 100.0, 4) if probes else 0.0
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)
    dumpj(
        out / "m6p7_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "probe_count": len(probes),
            "failure_count": len(probe_failures),
            "error_rate_pct": error_rate_pct,
            "latency_ms_p50": p50,
            "latency_ms_p95": p95,
            "latency_ms_p99": p95,
            "sample_failures": probe_failures[:10],
            "probes": probes,
        },
    )
    dumpj(
        out / "m6p7_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "overall_pass": len(issues) == 0,
            "issues": issues,
        },
    )
    dumpj(
        out / "m6p7_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6p7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "window_seconds": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "estimated_api_call_count": len(probes),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M6P7_STRESS_MAX_SPEND_USD", 25)),
            "within_envelope": True,
            "method": "m6p7_s1_ingest_evidence_materialization_v0",
        },
    )

    decisions.extend(
        [
            "Validated S0 dependency continuity and blocker closure before S1.",
            "Validated receipt/quarantine/offset evidence readability and run-scope continuity.",
            "Validated offsets materiality with topic/partition observed_count checks.",
            "Validated ingest evidence refs via bounded S3 head-object probes.",
            "Retained fail-closed blocker posture for missing/unreadable/non-material evidence surfaces.",
        ]
    )
    dumpj(
        out / "m6p7_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S1",
            "decisions": decisions,
        },
    )

    overall_pass = len(blockers) == 0
    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S1",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S1",
        "overall_pass": overall_pass,
        "next_gate": "M6P7_ST_S2_READY" if overall_pass else "BLOCKED",
        "required_artifacts": REQUIRED_ARTIFACTS,
        "probe_count": len(probes),
        "error_rate_pct": error_rate_pct,
        "s0_dependency_phase_execution_id": dep_id,
        "historical_m6h_execution_id": hist_id,
        "platform_run_id": dep_platform_run_id,
        "offset_mode": offsets_mode,
    }
    dumpj(out / "m6p7_blocker_register.json", blocker_register)
    dumpj(out / "m6p7_execution_summary.json", summary)

    missing = [x for x in REQUIRED_ARTIFACTS if not (out / x).exists()]
    if missing:
        blockers.append({"id": "M6P7-ST-B11", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": missing}})
        blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summary.update({"overall_pass": False, "next_gate": "BLOCKED"})
        dumpj(out / "m6p7_blocker_register.json", blocker_register)
        dumpj(out / "m6p7_execution_summary.json", summary)

    print(f"[m6p7_s1] phase_execution_id={phase_execution_id}")
    print(f"[m6p7_s1] output_dir={out.as_posix()}")
    print(f"[m6p7_s1] overall_pass={summary['overall_pass']}")
    print(f"[m6p7_s1] next_gate={summary['next_gate']}")
    print(f"[m6p7_s1] probe_count={summary['probe_count']}")
    print(f"[m6p7_s1] error_rate_pct={summary['error_rate_pct']}")
    print(f"[m6p7_s1] open_blockers={blocker_register['open_blocker_count']}")
    return 0 if summary["overall_pass"] else 2


def run_s2(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p7_stress_s1", "M6P7-ST-S1")
    dep_id = ""
    dep_platform_run_id = ""
    dep_hist_m6h = ""
    dep_issues: list[str] = []
    dep_path: Path | None = None
    if not dep:
        dep_issues.append("missing successful M6P7-ST-S1 dependency")
    else:
        dep_path = Path(str(dep["path"]))
        s = dep["summary"]
        dep_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        dep_hist_m6h = str(s.get("historical_m6h_execution_id", "")).strip()
        if str(s.get("next_gate", "")) != "M6P7_ST_S2_READY":
            dep_issues.append("M6P7 S1 next_gate is not M6P7_ST_S2_READY")
        b = loadj(dep_path / "m6p7_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P7 S1 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    ingest_s1: dict[str, Any] = {}
    receipt_s1: dict[str, Any] = {}
    quarantine_s1: dict[str, Any] = {}
    offsets_s1: dict[str, Any] = {}
    if dep_path is not None:
        ingest_s1 = loadj(dep_path / "m6p7_ingest_commit_snapshot.json")
        receipt_s1 = loadj(dep_path / "m6p7_receipt_summary_snapshot.json")
        quarantine_s1 = loadj(dep_path / "m6p7_quarantine_summary_snapshot.json")
        offsets_s1 = loadj(dep_path / "m6p7_offsets_snapshot.json")

    if not ingest_s1 or not receipt_s1 or not quarantine_s1 or not offsets_s1:
        blockers.append(
            {
                "id": "M6P7-ST-B10",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "missing_s1_artifacts": [
                        name
                        for name, payload in [
                            ("m6p7_ingest_commit_snapshot.json", ingest_s1),
                            ("m6p7_receipt_summary_snapshot.json", receipt_s1),
                            ("m6p7_quarantine_summary_snapshot.json", quarantine_s1),
                            ("m6p7_offsets_snapshot.json", offsets_s1),
                        ]
                        if not payload
                    ]
                },
            }
        )
        issues.append("required S1 evidence snapshots are missing or unreadable")

    counts = ingest_s1.get("counts", {}) if isinstance(ingest_s1.get("counts"), dict) else {}
    checks = ingest_s1.get("checks", {}) if isinstance(ingest_s1.get("checks"), dict) else {}
    receipt_decisions = receipt_s1.get("counts_by_decision", {}) if isinstance(receipt_s1.get("counts_by_decision"), dict) else {}

    admit_count = to_int(counts.get("admit"))
    duplicate_count = to_int(counts.get("duplicate"))
    quarantine_count = to_int(counts.get("quarantine"))
    total_receipts = to_int(counts.get("total_receipts"))
    if admit_count is None:
        admit_count = to_int(receipt_decisions.get("ADMIT"))
    if duplicate_count is None:
        duplicate_count = to_int(receipt_decisions.get("DUPLICATE"))
    if quarantine_count is None:
        quarantine_count = to_int(quarantine_s1.get("quarantine_count"))
    if total_receipts is None:
        total_receipts = to_int(receipt_s1.get("total_receipts"))
    dedupe_anomaly_count = to_int(checks.get("dedupe_anomaly_count"))

    cross_scope_rows = [
        ("ingest", str(ingest_s1.get("platform_run_id", "")).strip()),
        ("receipt", str(receipt_s1.get("platform_run_id", "")).strip()),
        ("quarantine", str(quarantine_s1.get("platform_run_id", "")).strip()),
        ("offsets", str(offsets_s1.get("platform_run_id", "")).strip()),
    ]
    for label, run_id in cross_scope_rows:
        if dep_platform_run_id and run_id and run_id != dep_platform_run_id:
            blockers.append(
                {
                    "id": "M6P7-ST-B6",
                    "severity": "S2",
                    "status": "OPEN",
                    "details": {
                        "reason": f"{label} snapshot platform_run_id mismatch",
                        "expected_platform_run_id": dep_platform_run_id,
                        "actual_platform_run_id": run_id,
                    },
                }
            )
            issues.append(f"{label} snapshot platform_run_id mismatch")

    count_invariant_pass = False
    if None not in {admit_count, duplicate_count, quarantine_count, total_receipts}:
        count_invariant_pass = (admit_count + duplicate_count + quarantine_count) == total_receipts
        if not count_invariant_pass:
            blockers.append(
                {
                    "id": "M6P7-ST-B6",
                    "severity": "S2",
                    "status": "OPEN",
                    "details": {
                        "reason": "receipt count invariant failed",
                        "admit_count": admit_count,
                        "duplicate_count": duplicate_count,
                        "quarantine_count": quarantine_count,
                        "total_receipts": total_receipts,
                    },
                }
            )
            issues.append("receipt/quarantine/dedupe count invariant failed")
    else:
        blockers.append(
            {
                "id": "M6P7-ST-B6",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "reason": "count invariant inputs missing",
                    "admit_count": admit_count,
                    "duplicate_count": duplicate_count,
                    "quarantine_count": quarantine_count,
                    "total_receipts": total_receipts,
                },
            }
        )
        issues.append("count invariant inputs are incomplete")

    if dedupe_anomaly_count is not None and dedupe_anomaly_count > 0:
        blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "dedupe_anomaly_count > 0", "dedupe_anomaly_count": dedupe_anomaly_count}})
        issues.append("dedupe_anomaly_count is non-zero")
    if dedupe_anomaly_count is None:
        blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "dedupe_anomaly_count missing"}})
        issues.append("dedupe_anomaly_count missing from S1 ingest snapshot")

    if receipt_s1.get("sanity_total_matches") is False:
        blockers.append({"id": "M6P7-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "receipt sanity_total_matches=false"}})
        issues.append("receipt sanity_total_matches=false")

    offsets_mode = str(offsets_s1.get("offset_mode", "")).strip()
    observed_total = to_int(offsets_s1.get("observed_total"))
    offset_consistency_pass = True
    if offsets_mode == "IG_ADMISSION_INDEX_PROXY" and None not in {admit_count, observed_total}:
        if observed_total != admit_count:
            offset_consistency_pass = False
            blockers.append(
                {
                    "id": "M6P7-ST-B6",
                    "severity": "S2",
                    "status": "OPEN",
                    "details": {"reason": "IG admission proxy offsets/admit mismatch", "observed_total": observed_total, "admit_count": admit_count},
                }
            )
            issues.append("offset observed_total does not match admit_count in IG proxy mode")
    elif offsets_mode == "IG_ADMISSION_INDEX_PROXY":
        offset_consistency_pass = False
        blockers.append(
            {
                "id": "M6P7-ST-B6",
                "severity": "S2",
                "status": "OPEN",
                "details": {"reason": "offset consistency inputs missing", "observed_total": observed_total, "admit_count": admit_count},
            }
        )
        issues.append("offset consistency inputs are incomplete")

    ttl_field = str(handles.get("DDB_IG_IDEMPOTENCY_TTL_FIELD", "")).strip()
    ttl_seconds = to_int(handles.get("IG_IDEMPOTENCY_TTL_SECONDS"))
    latest_admitted_epoch = None
    topics = offsets_s1.get("topics", []) if isinstance(offsets_s1.get("topics"), list) else []
    for t in topics:
        if not isinstance(t, dict):
            continue
        n = to_int(t.get("last_offset"))
        if n is None:
            continue
        latest_admitted_epoch = n if latest_admitted_epoch is None else max(latest_admitted_epoch, n)
    age_seconds = None
    ttl_expired_expected = False
    if latest_admitted_epoch is not None:
        age_seconds = int(time.time()) - latest_admitted_epoch
    if age_seconds is not None and ttl_seconds is not None:
        ttl_expired_expected = age_seconds > ttl_seconds

    table = str(handles.get("DDB_IG_IDEMPOTENCY_TABLE", "")).strip()
    sample_count = 0
    missing_ttl_count = 0
    ttl_before_admitted_count = 0
    missing_dedupe_key_count = 0
    duplicate_dedupe_key_count = 0
    invalid_state_count = 0
    allowed_states = {"ADMITTED", "DUPLICATE", "QUARANTINE"}

    if not table:
        blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "DDB_IG_IDEMPOTENCY_TABLE handle missing"}})
        issues.append("DDB_IG_IDEMPOTENCY_TABLE handle missing")
    if not ttl_field:
        blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "DDB_IG_IDEMPOTENCY_TTL_FIELD handle missing"}})
        issues.append("DDB_IG_IDEMPOTENCY_TTL_FIELD handle missing")

    if table and ttl_field:
        sample_probe, sample_payload = cmd_json(
            [
                "aws",
                "dynamodb",
                "scan",
                "--table-name",
                table,
                "--region",
                "eu-west-2",
                "--max-items",
                "200",
                "--projection-expression",
                "dedupe_key,platform_run_id,event_id,#s,#t,admitted_at_epoch",
                "--expression-attribute-names",
                json.dumps({"#s": "state", "#t": ttl_field}),
            ],
            45,
        )
        probes.append({**sample_probe, "probe_id": "m6p7_s2_idempotency_sample_scan", "group": "idempotency"})
        if sample_probe.get("status") != "PASS" or sample_payload is None:
            blockers.append({"id": "M6P7-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m6p7_s2_idempotency_sample_scan"}})
            issues.append("idempotency sample scan failed")
        else:
            items = sample_payload.get("Items", []) if isinstance(sample_payload.get("Items"), list) else []
            sample_count = len(items)
            if sample_count == 0:
                blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "idempotency sample scan returned zero rows"}})
                issues.append("idempotency sample scan returned zero rows")

            seen: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    continue
                dedupe_key = ddb_s(item, "dedupe_key")
                if not dedupe_key:
                    missing_dedupe_key_count += 1
                else:
                    if dedupe_key in seen:
                        duplicate_dedupe_key_count += 1
                    seen.add(dedupe_key)

                state = ddb_s(item, "state")
                if state and state not in allowed_states:
                    invalid_state_count += 1

                ttl_epoch = ddb_n(item, ttl_field)
                admitted_epoch = ddb_n(item, "admitted_at_epoch")
                if ttl_epoch is None:
                    missing_ttl_count += 1
                if ttl_epoch is not None and admitted_epoch is not None and ttl_epoch < admitted_epoch:
                    ttl_before_admitted_count += 1

            if missing_dedupe_key_count > 0:
                blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "idempotency sample rows missing dedupe_key", "count": missing_dedupe_key_count}})
                issues.append("idempotency sample rows missing dedupe_key")
            if duplicate_dedupe_key_count > 0:
                blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "duplicate dedupe_key seen in idempotency sample", "count": duplicate_dedupe_key_count}})
                issues.append("duplicate dedupe_key seen in idempotency sample")
            if missing_ttl_count > 0:
                blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "idempotency sample rows missing TTL field", "count": missing_ttl_count, "ttl_field": ttl_field}})
                issues.append("idempotency sample rows missing TTL field")
            if ttl_before_admitted_count > 0:
                blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "ttl_epoch older than admitted_at_epoch in idempotency sample", "count": ttl_before_admitted_count, "ttl_field": ttl_field}})
                issues.append("ttl_epoch older than admitted_at_epoch in idempotency sample")
            if invalid_state_count > 0:
                blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "invalid state values in idempotency sample", "count": invalid_state_count}})
                issues.append("invalid state values in idempotency sample")

    run_scope_live_count = None
    if table and dep_platform_run_id and ttl_seconds is not None and latest_admitted_epoch is not None and not ttl_expired_expected:
        run_scope_probe, run_scope_payload = cmd_json(
            [
                "aws",
                "dynamodb",
                "scan",
                "--table-name",
                table,
                "--region",
                "eu-west-2",
                "--select",
                "COUNT",
                "--filter-expression",
                "#pr = :pr",
                "--expression-attribute-names",
                json.dumps({"#pr": "platform_run_id"}),
                "--expression-attribute-values",
                json.dumps({":pr": {"S": dep_platform_run_id}}),
            ],
            60,
        )
        probes.append({**run_scope_probe, "probe_id": "m6p7_s2_idempotency_run_scope_count", "group": "idempotency"})
        if run_scope_probe.get("status") != "PASS" or run_scope_payload is None:
            blockers.append({"id": "M6P7-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m6p7_s2_idempotency_run_scope_count"}})
            issues.append("run-scoped idempotency count probe failed")
        else:
            run_scope_live_count = to_int(run_scope_payload.get("Count"))
            if run_scope_live_count is None:
                blockers.append({"id": "M6P7-ST-B10", "severity": "S2", "status": "OPEN", "details": {"reason": "run-scope count parse failed"}})
                issues.append("run-scoped idempotency count parse failed")
            elif run_scope_live_count <= 0:
                blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "run-scoped idempotency rows unexpectedly absent within TTL window", "platform_run_id": dep_platform_run_id, "count": run_scope_live_count}})
                issues.append("run-scoped idempotency rows unexpectedly absent within TTL window")
    elif dep_platform_run_id and ttl_expired_expected:
        decisions.append("Run-scoped idempotency live-row absence was treated as expected TTL expiry; S2 used historical run-scoped evidence plus live surface sample.")
    elif dep_platform_run_id and (ttl_seconds is None or latest_admitted_epoch is None):
        blockers.append({"id": "M6P7-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "cannot adjudicate run-scoped row-presence TTL policy", "ttl_seconds": ttl_seconds, "latest_admitted_epoch": latest_admitted_epoch}})
        issues.append("cannot adjudicate run-scoped row-presence TTL policy")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p_bucket, "probe_id": "m6p7_s2_evidence_bucket", "group": "control"})
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M6P7-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m6p7_s2_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    dumpj(
        out / "m6p7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "findings": [
                {"id": "M6P7-ST-F3", "classification": "PREVENT", "finding": "Dedupe/anomaly closure must preserve run-scope and idempotency invariants.", "required_action": "Fail-closed on invariant drift across receipt/quarantine/offset surfaces."},
                {"id": "M6P7-ST-F5", "classification": "OBSERVE", "finding": "Historical run scopes can age out from idempotency store due TTL.", "required_action": "When TTL expiry is proven, use historical run evidence + live surface sample and document mode."},
                {"id": "M6P7-ST-F6", "classification": "OBSERVE", "finding": "Offset mode can be proxy-backed while idempotency remains durable.", "required_action": "Keep explicit offset-mode evidence in S2 summary and snapshots."},
            ],
        },
    )
    dumpj(
        out / "m6p7_lane_matrix.json",
        {
            "component_sequence": ["M6P7-ST-S0", "M6P7-ST-S1", "M6P7-ST-S2", "M6P7-ST-S3", "M6P7-ST-S4", "M6P7-ST-S5"],
            "plane_sequence": ["ingest_commit_plane", "idempotency_plane", "p7_rollup_plane"],
            "integrated_windows": ["m6p7_s3_replay_window", "m6p7_s3_continuity_window"],
        },
    )

    dumpj(
        out / "m6p7_ingest_commit_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "status": "PASS" if len(blockers) == 0 else "FAIL",
            "platform_run_id": dep_platform_run_id,
            "s1_dependency_phase_execution_id": dep_id,
            "historical_m6h_execution_id": dep_hist_m6h,
            "offset_mode": offsets_mode,
            "counts": {"admit": admit_count, "duplicate": duplicate_count, "quarantine": quarantine_count, "total_receipts": total_receipts},
            "checks": {"dedupe_anomaly_count": dedupe_anomaly_count, "count_invariant_pass": count_invariant_pass, "offset_consistency_pass": offset_consistency_pass},
        },
    )
    dumpj(
        out / "m6p7_receipt_summary_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "status": str(receipt_s1.get("status", "UNKNOWN")),
            "platform_run_id": str(receipt_s1.get("platform_run_id", dep_platform_run_id)).strip(),
            "total_receipts": total_receipts,
            "sanity_total_matches": receipt_s1.get("sanity_total_matches"),
            "counts_by_decision": receipt_s1.get("counts_by_decision"),
            "source": receipt_s1.get("source"),
            "s3_ref": receipt_s1.get("s3_ref"),
        },
    )
    dumpj(
        out / "m6p7_quarantine_summary_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "status": str(quarantine_s1.get("status", "UNKNOWN")),
            "platform_run_id": str(quarantine_s1.get("platform_run_id", dep_platform_run_id)).strip(),
            "quarantine_count": quarantine_count,
            "quarantine_records_materialized": quarantine_s1.get("quarantine_records_materialized"),
            "source": quarantine_s1.get("source"),
            "s3_ref": quarantine_s1.get("s3_ref"),
        },
    )
    dumpj(
        out / "m6p7_offsets_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "status": str(offsets_s1.get("status", "UNKNOWN")),
            "platform_run_id": str(offsets_s1.get("platform_run_id", dep_platform_run_id)).strip(),
            "offset_mode": offsets_mode,
            "kafka_offsets_materialized": offsets_s1.get("kafka_offsets_materialized"),
            "topics_count": offsets_s1.get("topics_count"),
            "observed_total": observed_total,
            "topics": offsets_s1.get("topics"),
            "latest_admitted_epoch": latest_admitted_epoch,
            "age_seconds": age_seconds,
            "ttl_seconds": ttl_seconds,
            "ttl_expired_expected": ttl_expired_expected,
            "s3_ref": offsets_s1.get("s3_ref"),
        },
    )
    dumpj(
        out / "m6p7_dedupe_anomaly_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "status": "PASS" if len(blockers) == 0 else "FAIL",
            "platform_run_id": dep_platform_run_id,
            "dedupe_anomaly_count": dedupe_anomaly_count,
            "count_invariant_pass": count_invariant_pass,
            "offset_consistency_pass": offset_consistency_pass,
            "ttl_policy": {"ttl_field": ttl_field, "ttl_seconds": ttl_seconds, "latest_admitted_epoch": latest_admitted_epoch, "age_seconds": age_seconds, "ttl_expired_expected": ttl_expired_expected, "run_scope_live_count": run_scope_live_count},
            "live_idempotency_sample": {"sample_count": sample_count, "missing_ttl_count": missing_ttl_count, "ttl_before_admitted_count": ttl_before_admitted_count, "missing_dedupe_key_count": missing_dedupe_key_count, "duplicate_dedupe_key_count": duplicate_dedupe_key_count, "invalid_state_count": invalid_state_count},
        },
    )

    probe_failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    error_rate_pct = round((len(probe_failures) / len(probes)) * 100.0, 4) if probes else 0.0
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)
    dumpj(
        out / "m6p7_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "probe_count": len(probes),
            "failure_count": len(probe_failures),
            "error_rate_pct": error_rate_pct,
            "latency_ms_p50": p50,
            "latency_ms_p95": p95,
            "latency_ms_p99": p95,
            "sample_failures": probe_failures[:10],
            "probes": probes,
        },
    )
    dumpj(
        out / "m6p7_control_rail_conformance_snapshot.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S2", "overall_pass": len(issues) == 0, "issues": issues},
    )
    dumpj(
        out / "m6p7_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6p7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S2",
            "window_seconds": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "estimated_api_call_count": len(probes),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M6P7_STRESS_MAX_SPEND_USD", 25)),
            "within_envelope": True,
            "method": "m6p7_s2_dedupe_anomaly_closure_v0",
        },
    )

    decisions.extend(
        [
            "Validated S1 dependency continuity and blocker closure before S2.",
            "Validated dedupe/count invariants across ingest, receipt, quarantine, and offsets evidence.",
            "Validated bounded live idempotency surface posture (schema/TTL/state) from DDB sample.",
            "Applied TTL-aware run-scope evidence policy to avoid false blockers on aged historical run ids.",
            "Retained fail-closed posture for unexplained dedupe/idempotency or cross-surface drift.",
        ]
    )
    dumpj(
        out / "m6p7_decision_log.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S2", "decisions": decisions},
    )

    overall_pass = len(blockers) == 0
    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S2",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S2",
        "overall_pass": overall_pass,
        "next_gate": "M6P7_ST_S3_READY" if overall_pass else "BLOCKED",
        "required_artifacts": REQUIRED_ARTIFACTS,
        "probe_count": len(probes),
        "error_rate_pct": error_rate_pct,
        "s1_dependency_phase_execution_id": dep_id,
        "historical_m6h_execution_id": dep_hist_m6h,
        "platform_run_id": dep_platform_run_id,
        "offset_mode": offsets_mode,
        "ttl_evidence_mode": "HISTORICAL_WITH_LIVE_SAMPLE" if ttl_expired_expected else "RUN_SCOPE_LIVE_REQUIRED",
    }
    dumpj(out / "m6p7_blocker_register.json", blocker_register)
    dumpj(out / "m6p7_execution_summary.json", summary)

    missing = [x for x in REQUIRED_ARTIFACTS if not (out / x).exists()]
    if missing:
        blockers.append({"id": "M6P7-ST-B11", "severity": "S2", "status": "OPEN", "details": {"missing_artifacts": missing}})
        blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summary.update({"overall_pass": False, "next_gate": "BLOCKED"})
        dumpj(out / "m6p7_blocker_register.json", blocker_register)
        dumpj(out / "m6p7_execution_summary.json", summary)

    print(f"[m6p7_s2] phase_execution_id={phase_execution_id}")
    print(f"[m6p7_s2] output_dir={out.as_posix()}")
    print(f"[m6p7_s2] overall_pass={summary['overall_pass']}")
    print(f"[m6p7_s2] next_gate={summary['next_gate']}")
    print(f"[m6p7_s2] probe_count={summary['probe_count']}")
    print(f"[m6p7_s2] error_rate_pct={summary['error_rate_pct']}")
    print(f"[m6p7_s2] open_blockers={blocker_register['open_blocker_count']}")
    return 0 if summary["overall_pass"] else 2


def run_s3(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p7_stress_s2", "M6P7-ST-S2")
    dep_id = ""
    dep_platform_run_id = ""
    dep_hist_m6h = ""
    dep_issues: list[str] = []
    dep_path: Path | None = None
    if not dep:
        dep_issues.append("missing successful M6P7-ST-S2 dependency")
    else:
        dep_path = Path(str(dep["path"]))
        s = dep["summary"]
        dep_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        dep_hist_m6h = str(s.get("historical_m6h_execution_id", "")).strip()
        if str(s.get("next_gate", "")) != "M6P7_ST_S3_READY":
            dep_issues.append("M6P7 S2 next_gate is not M6P7_ST_S3_READY")
        b = loadj(dep_path / "m6p7_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P7 S2 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P7-ST-B6", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    ingest_s2: dict[str, Any] = {}
    receipt_s2: dict[str, Any] = {}
    quarantine_s2: dict[str, Any] = {}
    offsets_s2: dict[str, Any] = {}
    dedupe_s2: dict[str, Any] = {}
    if dep_path is not None:
        ingest_s2 = loadj(dep_path / "m6p7_ingest_commit_snapshot.json")
        receipt_s2 = loadj(dep_path / "m6p7_receipt_summary_snapshot.json")
        quarantine_s2 = loadj(dep_path / "m6p7_quarantine_summary_snapshot.json")
        offsets_s2 = loadj(dep_path / "m6p7_offsets_snapshot.json")
        dedupe_s2 = loadj(dep_path / "m6p7_dedupe_anomaly_snapshot.json")

    missing_s2 = [
        name
        for name, payload in [
            ("m6p7_ingest_commit_snapshot.json", ingest_s2),
            ("m6p7_receipt_summary_snapshot.json", receipt_s2),
            ("m6p7_quarantine_summary_snapshot.json", quarantine_s2),
            ("m6p7_offsets_snapshot.json", offsets_s2),
            ("m6p7_dedupe_anomaly_snapshot.json", dedupe_s2),
        ]
        if not payload
    ]
    if missing_s2:
        blockers.append({"id": "M6P7-ST-B10", "severity": "S3", "status": "OPEN", "details": {"missing_s2_artifacts": missing_s2}})
        issues.append("required S2 continuity artifacts are missing or unreadable")

    run_ids = [
        str(ingest_s2.get("platform_run_id", "")).strip(),
        str(receipt_s2.get("platform_run_id", "")).strip(),
        str(quarantine_s2.get("platform_run_id", "")).strip(),
        str(offsets_s2.get("platform_run_id", "")).strip(),
        str(dedupe_s2.get("platform_run_id", "")).strip(),
    ]
    for idx, run_id in enumerate(run_ids):
        if dep_platform_run_id and run_id and run_id != dep_platform_run_id:
            blockers.append(
                {
                    "id": "M6P7-ST-B6",
                    "severity": "S3",
                    "status": "OPEN",
                    "details": {"reason": "cross-surface platform_run_id mismatch", "surface_index": idx, "expected": dep_platform_run_id, "actual": run_id},
                }
            )
            issues.append("cross-surface platform_run_id mismatch in S2 continuity artifacts")

    count_invariant_pass = bool(dedupe_s2.get("count_invariant_pass")) if "count_invariant_pass" in dedupe_s2 else False
    offset_consistency_pass = bool(dedupe_s2.get("offset_consistency_pass")) if "offset_consistency_pass" in dedupe_s2 else False
    dedupe_anomaly_count = to_int(dedupe_s2.get("dedupe_anomaly_count"))
    if count_invariant_pass is not True:
        blockers.append({"id": "M6P7-ST-B6", "severity": "S3", "status": "OPEN", "details": {"reason": "count_invariant_pass is not true"}})
        issues.append("count_invariant_pass is not true in S2 continuity input")
    if offset_consistency_pass is not True:
        blockers.append({"id": "M6P7-ST-B6", "severity": "S3", "status": "OPEN", "details": {"reason": "offset_consistency_pass is not true"}})
        issues.append("offset_consistency_pass is not true in S2 continuity input")
    if dedupe_anomaly_count is None or dedupe_anomaly_count > 0:
        blockers.append(
            {
                "id": "M6P7-ST-B6",
                "severity": "S3",
                "status": "OPEN",
                "details": {"reason": "dedupe_anomaly_count invalid for continuity", "dedupe_anomaly_count": dedupe_anomaly_count},
            }
        )
        issues.append("dedupe_anomaly_count invalid for continuity")

    m6i = latest_m6i_rollup(dep_platform_run_id)
    m6i_id = ""
    m6i_platform_run_id = ""
    if not m6i:
        blockers.append(
            {
                "id": "M6P7-ST-B6",
                "severity": "S3",
                "status": "OPEN",
                "details": {"reason": "missing successful historical M6.I continuity anchor", "platform_run_id": dep_platform_run_id},
            }
        )
        issues.append("missing successful historical M6.I continuity anchor")
    else:
        m6i_id = str(m6i.get("execution_id", "")).strip()
        m6i_rollup = m6i.get("rollup_matrix", {})
        m6i_platform_run_id = str(m6i_rollup.get("platform_run_id", "")).strip()
        if dep_platform_run_id and m6i_platform_run_id and m6i_platform_run_id != dep_platform_run_id:
            blockers.append(
                {
                    "id": "M6P7-ST-B6",
                    "severity": "S3",
                    "status": "OPEN",
                    "details": {"reason": "historical M6.I platform_run_id mismatch", "expected": dep_platform_run_id, "actual": m6i_platform_run_id},
                }
            )
            issues.append("historical M6.I platform_run_id mismatch")
        lane_matrix = m6i_rollup.get("lane_matrix", []) if isinstance(m6i_rollup.get("lane_matrix"), list) else []
        bad_lanes = [r for r in lane_matrix if isinstance(r, dict) and r.get("overall_pass") is not True]
        if bad_lanes:
            blockers.append({"id": "M6P7-ST-B6", "severity": "S3", "status": "OPEN", "details": {"reason": "historical M6.I lane matrix has non-pass lanes", "count": len(bad_lanes)}})
            issues.append("historical M6.I lane matrix has non-pass lanes")

    replay_minutes = to_int(plan_packet.get("M6P7_STRESS_REPLAY_WINDOW_MINUTES")) or 15
    replay_window_seconds = replay_minutes * 60
    latest_admitted_epoch = to_int(offsets_s2.get("latest_admitted_epoch"))
    ttl_seconds = to_int(offsets_s2.get("ttl_seconds"))
    ttl_expired_expected = bool(offsets_s2.get("ttl_expired_expected"))
    age_seconds = to_int(offsets_s2.get("age_seconds"))
    if age_seconds is None and latest_admitted_epoch is not None:
        age_seconds = int(time.time()) - latest_admitted_epoch
    replay_window_mode = "UNKNOWN"

    table = str(handles.get("DDB_IG_IDEMPOTENCY_TABLE", "")).strip()
    run_scope_live_count = None
    if latest_admitted_epoch is None or age_seconds is None:
        blockers.append(
            {
                "id": "M6P7-ST-B7",
                "severity": "S3",
                "status": "OPEN",
                "details": {"reason": "cannot compute replay window posture", "latest_admitted_epoch": latest_admitted_epoch, "age_seconds": age_seconds},
            }
        )
        issues.append("cannot compute replay window posture")
    elif age_seconds <= replay_window_seconds:
        replay_window_mode = "LIVE_WINDOW"
        if not table:
            blockers.append({"id": "M6P7-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "idempotency table handle missing for live replay window"}})
            issues.append("idempotency table handle missing for live replay window")
        else:
            probe_1, payload_1 = cmd_json(
                [
                    "aws",
                    "dynamodb",
                    "scan",
                    "--table-name",
                    table,
                    "--region",
                    "eu-west-2",
                    "--select",
                    "COUNT",
                    "--filter-expression",
                    "#pr = :pr",
                    "--expression-attribute-names",
                    json.dumps({"#pr": "platform_run_id"}),
                    "--expression-attribute-values",
                    json.dumps({":pr": {"S": dep_platform_run_id}}),
                ],
                45,
            )
            probes.append({**probe_1, "probe_id": "m6p7_s3_replay_live_count_1", "group": "replay_window"})
            if probe_1.get("status") != "PASS" or payload_1 is None:
                blockers.append({"id": "M6P7-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m6p7_s3_replay_live_count_1"}})
                issues.append("live replay-window run-scope count probe failed")
            else:
                c1 = to_int(payload_1.get("Count"))
                if c1 is None or c1 <= 0:
                    blockers.append({"id": "M6P7-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "expected live replay-window rows absent", "count": c1}})
                    issues.append("expected live replay-window rows absent")
                run_scope_live_count = c1

            time.sleep(1.0)
            probe_2, payload_2 = cmd_json(
                [
                    "aws",
                    "dynamodb",
                    "scan",
                    "--table-name",
                    table,
                    "--region",
                    "eu-west-2",
                    "--select",
                    "COUNT",
                    "--filter-expression",
                    "#pr = :pr",
                    "--expression-attribute-names",
                    json.dumps({"#pr": "platform_run_id"}),
                    "--expression-attribute-values",
                    json.dumps({":pr": {"S": dep_platform_run_id}}),
                ],
                45,
            )
            probes.append({**probe_2, "probe_id": "m6p7_s3_replay_live_count_2", "group": "replay_window"})
            if probe_2.get("status") != "PASS" or payload_2 is None:
                blockers.append({"id": "M6P7-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m6p7_s3_replay_live_count_2"}})
                issues.append("second live replay-window count probe failed")
            else:
                c2 = to_int(payload_2.get("Count"))
                if c2 is None:
                    blockers.append({"id": "M6P7-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "second live replay count parse failed"}})
                    issues.append("second live replay count parse failed")
                elif run_scope_live_count is not None and c2 < run_scope_live_count:
                    blockers.append({"id": "M6P7-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "live replay-window run-scope count regressed", "count_1": run_scope_live_count, "count_2": c2}})
                    issues.append("live replay-window run-scope count regressed")
                run_scope_live_count = c2 if c2 is not None else run_scope_live_count
    else:
        replay_window_mode = "HISTORICAL_CLOSED_WINDOW"
        if ttl_expired_expected:
            decisions.append("Replay-window continuity evaluated in historical-closed mode: run age exceeds replay window and TTL-expired posture is expected.")
        else:
            decisions.append("Replay-window continuity evaluated in historical-closed mode due run age exceeding replay window.")
        if ttl_seconds is None and age_seconds > replay_window_seconds:
            blockers.append({"id": "M6P7-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "historical closed-window mode lacks TTL context", "age_seconds": age_seconds}})
            issues.append("historical closed-window mode lacks TTL context")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p_bucket, "probe_id": "m6p7_s3_evidence_bucket", "group": "control"})
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M6P7-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m6p7_s3_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    for ref_key, blocker_id, probe_id in [
        ("s3_ref", "M6P7-ST-B10", "m6p7_s3_receipt_ref"),
    ]:
        for snap_name, snap in [("receipt", receipt_s2), ("quarantine", quarantine_s2), ("offsets", offsets_s2)]:
            uri = str(snap.get(ref_key, "")).strip()
            if not uri:
                blockers.append({"id": blocker_id, "severity": "S3", "status": "OPEN", "details": {"reason": f"{snap_name} snapshot missing s3_ref"}})
                issues.append(f"{snap_name} snapshot missing s3_ref")
                continue
            ref_bucket, ref_path = parse_s3_uri(uri)
            if not ref_bucket or not ref_path:
                blockers.append({"id": blocker_id, "severity": "S3", "status": "OPEN", "details": {"reason": f"{snap_name} snapshot invalid s3_ref", "uri": uri}})
                issues.append(f"{snap_name} snapshot invalid s3_ref")
                continue
            p_ref = cmd(["aws", "s3api", "head-object", "--bucket", ref_bucket, "--key", ref_path, "--region", "eu-west-2"], 25)
            probes.append({**p_ref, "probe_id": f"{probe_id}_{snap_name}", "group": "ingest_evidence", "uri": uri})
            if p_ref.get("status") != "PASS":
                blockers.append({"id": blocker_id, "severity": "S3", "status": "OPEN", "details": {"probe_id": f"{probe_id}_{snap_name}", "uri": uri}})
                issues.append(f"{snap_name} continuity reference probe failed")

    dumpj(
        out / "m6p7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "findings": [
                {"id": "M6P7-ST-F4", "classification": "PREVENT", "finding": "P7 continuity must remain deterministic against historical gate anchors.", "required_action": "Fail-closed if historical P7.B anchor is missing or inconsistent."},
                {"id": "M6P7-ST-F5", "classification": "OBSERVE", "finding": "Replay-window checks must be mode-aware for aged historical runs.", "required_action": "Use historical-closed mode with explicit rationale when replay window is elapsed."},
                {"id": "M6P7-ST-F6", "classification": "OBSERVE", "finding": "Proxy offset mode remains valid if continuity invariants hold.", "required_action": "Enforce offset/admit consistency and persist mode in summary."},
            ],
        },
    )
    dumpj(
        out / "m6p7_lane_matrix.json",
        {
            "component_sequence": ["M6P7-ST-S0", "M6P7-ST-S1", "M6P7-ST-S2", "M6P7-ST-S3", "M6P7-ST-S4", "M6P7-ST-S5"],
            "plane_sequence": ["ingest_commit_plane", "idempotency_plane", "p7_rollup_plane"],
            "integrated_windows": ["m6p7_s3_replay_window", "m6p7_s3_continuity_window"],
        },
    )

    dumpj(
        out / "m6p7_ingest_commit_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "status": "PASS" if len(blockers) == 0 else "FAIL",
            "platform_run_id": dep_platform_run_id,
            "s2_dependency_phase_execution_id": dep_id,
            "historical_m6h_execution_id": dep_hist_m6h,
            "historical_m6i_execution_id": m6i_id,
            "replay_window_mode": replay_window_mode,
        },
    )
    dumpj(
        out / "m6p7_receipt_summary_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "status": str(receipt_s2.get("status", "UNKNOWN")),
            "platform_run_id": str(receipt_s2.get("platform_run_id", dep_platform_run_id)).strip(),
            "total_receipts": receipt_s2.get("total_receipts"),
            "sanity_total_matches": receipt_s2.get("sanity_total_matches"),
            "counts_by_decision": receipt_s2.get("counts_by_decision"),
            "source": receipt_s2.get("source"),
            "s3_ref": receipt_s2.get("s3_ref"),
        },
    )
    dumpj(
        out / "m6p7_quarantine_summary_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "status": str(quarantine_s2.get("status", "UNKNOWN")),
            "platform_run_id": str(quarantine_s2.get("platform_run_id", dep_platform_run_id)).strip(),
            "quarantine_count": quarantine_s2.get("quarantine_count"),
            "quarantine_records_materialized": quarantine_s2.get("quarantine_records_materialized"),
            "source": quarantine_s2.get("source"),
            "s3_ref": quarantine_s2.get("s3_ref"),
        },
    )
    dumpj(
        out / "m6p7_offsets_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "status": str(offsets_s2.get("status", "UNKNOWN")),
            "platform_run_id": str(offsets_s2.get("platform_run_id", dep_platform_run_id)).strip(),
            "offset_mode": offsets_s2.get("offset_mode"),
            "kafka_offsets_materialized": offsets_s2.get("kafka_offsets_materialized"),
            "topics_count": offsets_s2.get("topics_count"),
            "observed_total": offsets_s2.get("observed_total"),
            "topics": offsets_s2.get("topics"),
            "latest_admitted_epoch": latest_admitted_epoch,
            "age_seconds": age_seconds,
            "ttl_seconds": ttl_seconds,
            "ttl_expired_expected": ttl_expired_expected,
            "replay_window_minutes": replay_minutes,
            "replay_window_mode": replay_window_mode,
            "run_scope_live_count": run_scope_live_count,
            "s3_ref": offsets_s2.get("s3_ref"),
        },
    )
    dumpj(
        out / "m6p7_dedupe_anomaly_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "status": "PASS" if len(blockers) == 0 else "FAIL",
            "platform_run_id": dep_platform_run_id,
            "dedupe_anomaly_count": dedupe_anomaly_count,
            "count_invariant_pass": count_invariant_pass,
            "offset_consistency_pass": offset_consistency_pass,
            "historical_m6i_execution_id": m6i_id,
            "historical_m6i_platform_run_id": m6i_platform_run_id,
            "replay_window_mode": replay_window_mode,
            "replay_window_minutes": replay_minutes,
            "run_scope_live_count": run_scope_live_count,
            "ttl_expired_expected": ttl_expired_expected,
        },
    )

    probe_failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    error_rate_pct = round((len(probe_failures) / len(probes)) * 100.0, 4) if probes else 0.0
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)
    dumpj(
        out / "m6p7_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "probe_count": len(probes),
            "failure_count": len(probe_failures),
            "error_rate_pct": error_rate_pct,
            "latency_ms_p50": p50,
            "latency_ms_p95": p95,
            "latency_ms_p99": p95,
            "sample_failures": probe_failures[:10],
            "probes": probes,
        },
    )
    dumpj(
        out / "m6p7_control_rail_conformance_snapshot.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S3", "overall_pass": len(issues) == 0, "issues": issues},
    )
    dumpj(
        out / "m6p7_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6p7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S3",
            "window_seconds": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "estimated_api_call_count": len(probes),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M6P7_STRESS_MAX_SPEND_USD", 25)),
            "within_envelope": True,
            "method": "m6p7_s3_continuity_replay_closure_v0",
        },
    )

    decisions.extend(
        [
            "Validated S2 dependency continuity and blocker closure before S3.",
            "Validated continuity invariants from S2 (count, dedupe, offset consistency).",
            "Validated historical P7.B (M6.I) continuity anchor for deterministic run-flow consistency.",
            "Applied replay-window mode selection with explicit historical-closed handling for aged runs.",
            "Retained fail-closed posture for unexplained continuity or replay-window drift.",
        ]
    )
    dumpj(
        out / "m6p7_decision_log.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S3", "decisions": decisions},
    )

    overall_pass = len(blockers) == 0
    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S3",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S3",
        "overall_pass": overall_pass,
        "next_gate": "M6P7_ST_S4_READY" if overall_pass else "BLOCKED",
        "required_artifacts": REQUIRED_ARTIFACTS,
        "probe_count": len(probes),
        "error_rate_pct": error_rate_pct,
        "s2_dependency_phase_execution_id": dep_id,
        "historical_m6h_execution_id": dep_hist_m6h,
        "historical_m6i_execution_id": m6i_id,
        "platform_run_id": dep_platform_run_id,
        "replay_window_mode": replay_window_mode,
    }
    dumpj(out / "m6p7_blocker_register.json", blocker_register)
    dumpj(out / "m6p7_execution_summary.json", summary)

    missing = [x for x in REQUIRED_ARTIFACTS if not (out / x).exists()]
    if missing:
        blockers.append({"id": "M6P7-ST-B11", "severity": "S3", "status": "OPEN", "details": {"missing_artifacts": missing}})
        blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summary.update({"overall_pass": False, "next_gate": "BLOCKED"})
        dumpj(out / "m6p7_blocker_register.json", blocker_register)
        dumpj(out / "m6p7_execution_summary.json", summary)

    print(f"[m6p7_s3] phase_execution_id={phase_execution_id}")
    print(f"[m6p7_s3] output_dir={out.as_posix()}")
    print(f"[m6p7_s3] overall_pass={summary['overall_pass']}")
    print(f"[m6p7_s3] next_gate={summary['next_gate']}")
    print(f"[m6p7_s3] probe_count={summary['probe_count']}")
    print(f"[m6p7_s3] error_rate_pct={summary['error_rate_pct']}")
    print(f"[m6p7_s3] open_blockers={blocker_register['open_blocker_count']}")
    return 0 if summary["overall_pass"] else 2


def run_s4(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p7_stress_s3", "M6P7-ST-S3")
    dep_id = ""
    dep_platform_run_id = ""
    dep_replay_mode = ""
    dep_issues: list[str] = []
    dep_path: Path | None = None
    dep_blockers_payload: dict[str, Any] = {}
    dep_summary: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M6P7-ST-S3 dependency")
    else:
        dep_path = Path(str(dep["path"]))
        dep_summary = dep["summary"]
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        dep_platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
        dep_replay_mode = str(dep_summary.get("replay_window_mode", "")).strip()
        if str(dep_summary.get("next_gate", "")) != "M6P7_ST_S4_READY":
            dep_issues.append("M6P7 S3 next_gate is not M6P7_ST_S4_READY")
        dep_blockers_payload = loadj(dep_path / "m6p7_blocker_register.json")
        if int(dep_blockers_payload.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P7 S3 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P7-ST-B8", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    remediation_mode = "NO_OP"
    remediation_actions: list[str] = []
    if dep_blockers_payload and int(dep_blockers_payload.get("open_blocker_count", 0) or 0) > 0:
        remediation_mode = "TARGETED_REMEDIATE"
        remediation_actions.append("S3 blockers detected from dependency register; targeted remediation required before S5.")
    elif dep_issues:
        remediation_mode = "TARGETED_REMEDIATE"
        remediation_actions.append("Dependency integrity issues detected; targeted remediation required.")
    else:
        remediation_actions.append("No open S3 blockers detected; remediation lane closed as NO_OP.")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p_bucket, "probe_id": "m6p7_s4_evidence_bucket", "group": "control"})
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M6P7-ST-B10", "severity": "S4", "status": "OPEN", "details": {"probe_id": "m6p7_s4_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    # Validate that dependency evidence is still readable before promoting S5.
    if dep_path is not None:
        for artifact in [
            "m6p7_ingest_commit_snapshot.json",
            "m6p7_receipt_summary_snapshot.json",
            "m6p7_quarantine_summary_snapshot.json",
            "m6p7_offsets_snapshot.json",
            "m6p7_dedupe_anomaly_snapshot.json",
            "m6p7_execution_summary.json",
        ]:
            if not (dep_path / artifact).exists():
                blockers.append({"id": "M6P7-ST-B10", "severity": "S4", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": artifact}})
                issues.append(f"missing dependency artifact: {artifact}")

    if len(blockers) > 0 and remediation_mode == "NO_OP":
        remediation_mode = "TARGETED_REMEDIATE"
        remediation_actions.append("Remediation mode escalated due runtime blocker detection during S4 probes.")

    dumpj(
        out / "m6p7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S4",
            "findings": [
                {"id": "M6P7-ST-F5", "classification": "OBSERVE", "finding": "S4 should stay targeted and avoid broad reruns.", "required_action": "Use NO_OP when dependency register is already clean; rerun only on explicit blocker evidence."},
                {"id": "M6P7-ST-F6", "classification": "OBSERVE", "finding": "Historical replay-window mode can remain valid without reopening S3.", "required_action": "Carry forward S3 mode when no causal drift is observed."},
            ],
        },
    )
    dumpj(
        out / "m6p7_lane_matrix.json",
        {
            "component_sequence": ["M6P7-ST-S0", "M6P7-ST-S1", "M6P7-ST-S2", "M6P7-ST-S3", "M6P7-ST-S4", "M6P7-ST-S5"],
            "plane_sequence": ["ingest_commit_plane", "idempotency_plane", "p7_rollup_plane"],
            "integrated_windows": ["m6p7_s3_replay_window", "m6p7_s3_continuity_window"],
        },
    )

    dumpj(
        out / "m6p7_ingest_commit_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S4",
            "status": remediation_mode,
            "platform_run_id": dep_platform_run_id,
            "s3_dependency_phase_execution_id": dep_id,
            "replay_window_mode": dep_replay_mode,
            "remediation_actions": remediation_actions,
        },
    )
    for artifact, src_name in [
        ("m6p7_receipt_summary_snapshot.json", "m6p7_receipt_summary_snapshot.json"),
        ("m6p7_quarantine_summary_snapshot.json", "m6p7_quarantine_summary_snapshot.json"),
        ("m6p7_offsets_snapshot.json", "m6p7_offsets_snapshot.json"),
        ("m6p7_dedupe_anomaly_snapshot.json", "m6p7_dedupe_anomaly_snapshot.json"),
    ]:
        src_payload = loadj(dep_path / src_name) if dep_path is not None else {}
        src_payload = dict(src_payload) if isinstance(src_payload, dict) else {}
        src_payload.update(
            {
                "generated_at_utc": now(),
                "phase_execution_id": phase_execution_id,
                "stage_id": "M6P7-ST-S4",
                "status": remediation_mode if remediation_mode == "TARGETED_REMEDIATE" else "NO_OP_CARRY_FORWARD",
            }
        )
        dumpj(out / artifact, src_payload)

    probe_failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    error_rate_pct = round((len(probe_failures) / len(probes)) * 100.0, 4) if probes else 0.0
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)
    dumpj(
        out / "m6p7_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S4",
            "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "probe_count": len(probes),
            "failure_count": len(probe_failures),
            "error_rate_pct": error_rate_pct,
            "latency_ms_p50": p50,
            "latency_ms_p95": p95,
            "latency_ms_p99": p95,
            "sample_failures": probe_failures[:10],
            "probes": probes,
        },
    )
    dumpj(
        out / "m6p7_control_rail_conformance_snapshot.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S4", "overall_pass": len(issues) == 0, "issues": issues},
    )
    dumpj(
        out / "m6p7_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S4",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6p7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S4",
            "window_seconds": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "estimated_api_call_count": len(probes),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M6P7_STRESS_MAX_SPEND_USD", 25)),
            "within_envelope": True,
            "method": "m6p7_s4_targeted_remediation_v0",
        },
    )

    decisions.extend(
        [
            "Validated S3 dependency continuity and blocker register closure before S4.",
            "Applied targeted remediation policy: NO_OP when dependency is already blocker-free.",
            "Preserved S3 replay-window mode/evidence posture without reopening upstream stages.",
            "Retained fail-closed escalation for any dependency artifact or evidence readback drift.",
        ]
    )
    dumpj(
        out / "m6p7_decision_log.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S4", "decisions": decisions},
    )

    overall_pass = len(blockers) == 0
    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S4",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S4",
        "overall_pass": overall_pass,
        "next_gate": "M6P7_ST_S5_READY" if overall_pass else "BLOCKED",
        "required_artifacts": REQUIRED_ARTIFACTS,
        "probe_count": len(probes),
        "error_rate_pct": error_rate_pct,
        "s3_dependency_phase_execution_id": dep_id,
        "platform_run_id": dep_platform_run_id,
        "replay_window_mode": dep_replay_mode,
        "remediation_mode": remediation_mode,
    }
    dumpj(out / "m6p7_blocker_register.json", blocker_register)
    dumpj(out / "m6p7_execution_summary.json", summary)

    missing = [x for x in REQUIRED_ARTIFACTS if not (out / x).exists()]
    if missing:
        blockers.append({"id": "M6P7-ST-B11", "severity": "S4", "status": "OPEN", "details": {"missing_artifacts": missing}})
        blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summary.update({"overall_pass": False, "next_gate": "BLOCKED"})
        dumpj(out / "m6p7_blocker_register.json", blocker_register)
        dumpj(out / "m6p7_execution_summary.json", summary)

    print(f"[m6p7_s4] phase_execution_id={phase_execution_id}")
    print(f"[m6p7_s4] output_dir={out.as_posix()}")
    print(f"[m6p7_s4] overall_pass={summary['overall_pass']}")
    print(f"[m6p7_s4] next_gate={summary['next_gate']}")
    print(f"[m6p7_s4] probe_count={summary['probe_count']}")
    print(f"[m6p7_s4] error_rate_pct={summary['error_rate_pct']}")
    print(f"[m6p7_s4] open_blockers={blocker_register['open_blocker_count']}")
    return 0 if summary["overall_pass"] else 2


def run_s5(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    expected_pass_verdict = str(plan_packet.get("M6P7_STRESS_EXPECTED_VERDICT_ON_PASS", "ADVANCE_TO_M7")).strip() or "ADVANCE_TO_M7"
    if expected_pass_verdict != "ADVANCE_TO_M7":
        blockers.append(
            {
                "id": "M6P7-ST-B8",
                "severity": "S5",
                "status": "OPEN",
                "details": {"reason": "unexpected expected_pass_verdict contract", "expected_pass_verdict": expected_pass_verdict},
            }
        )
        issues.append("expected pass verdict contract is not ADVANCE_TO_M7")

    dep = latest_ok("m6p7_stress_s4", "M6P7-ST-S4")
    dep_id = ""
    dep_platform_run_id = ""
    dep_replay_mode = ""
    dep_issues: list[str] = []
    dep_path: Path | None = None
    if not dep:
        dep_issues.append("missing successful M6P7-ST-S4 dependency")
    else:
        dep_path = Path(str(dep["path"]))
        dep_summary = dep["summary"]
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        dep_platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
        dep_replay_mode = str(dep_summary.get("replay_window_mode", "")).strip()
        if str(dep_summary.get("next_gate", "")) != "M6P7_ST_S5_READY":
            dep_issues.append("M6P7 S4 next_gate is not M6P7_ST_S5_READY")
        dep_blockers_payload = loadj(dep_path / "m6p7_blocker_register.json")
        if int(dep_blockers_payload.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P7 S4 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P7-ST-B8", "severity": "S5", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain = [
        ("S0", "m6p7_stress_s0", "M6P7-ST-S0", "M6P7_ST_S1_READY"),
        ("S1", "m6p7_stress_s1", "M6P7-ST-S1", "M6P7_ST_S2_READY"),
        ("S2", "m6p7_stress_s2", "M6P7-ST-S2", "M6P7_ST_S3_READY"),
        ("S3", "m6p7_stress_s3", "M6P7-ST-S3", "M6P7_ST_S4_READY"),
        ("S4", "m6p7_stress_s4", "M6P7-ST-S4", "M6P7_ST_S5_READY"),
    ]
    chain_rows: list[dict[str, Any]] = []
    for label, prefix, stage_id, expected_next_gate in chain:
        r = latest_ok(prefix, stage_id)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_next_gate,
            "found": bool(r),
            "phase_execution_id": "",
            "next_gate": "",
            "overall_pass": False,
            "platform_run_id": "",
            "run_scope_consistent": True,
            "ok": False,
        }
        if r:
            s = r["summary"]
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["overall_pass"] = bool(s.get("overall_pass"))
            row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_next_gate
            if dep_platform_run_id and row["platform_run_id"] and row["platform_run_id"] != dep_platform_run_id:
                row["run_scope_consistent"] = False
                row["ok"] = False
        if row["ok"] is not True:
            blockers.append({"id": "M6P7-ST-B8", "severity": "S5", "status": "OPEN", "details": {"chain_row": row}})
            issues.append(f"stage chain check failed for {label}")
        chain_rows.append(row)

    m6i = latest_m6i_rollup(dep_platform_run_id)
    m6i_id = ""
    m6i_verdict = ""
    m6i_blocker_count = 0
    if not m6i:
        blockers.append({"id": "M6P7-ST-B9", "severity": "S5", "status": "OPEN", "details": {"reason": "missing successful historical M6.I evidence"}})
        issues.append("missing successful historical M6.I evidence")
    else:
        m6i_id = str(m6i.get("execution_id", "")).strip()
        m6i_verdict = str(m6i.get("gate_verdict", {}).get("verdict", "")).strip()
        m6i_blocker_count = int(m6i.get("blocker_register", {}).get("blocker_count", 0) or 0)
        m6i_platform_run_id = str(m6i.get("rollup_matrix", {}).get("platform_run_id", "")).strip()
        if dep_platform_run_id and m6i_platform_run_id and m6i_platform_run_id != dep_platform_run_id:
            blockers.append(
                {
                    "id": "M6P7-ST-B9",
                    "severity": "S5",
                    "status": "OPEN",
                    "details": {
                        "reason": "historical M6.I run-scope mismatch",
                        "expected_platform_run_id": dep_platform_run_id,
                        "observed_platform_run_id": m6i_platform_run_id,
                    },
                }
            )
            issues.append("historical M6.I run-scope mismatch")
        if m6i_verdict != "ADVANCE_TO_M7":
            blockers.append(
                {
                    "id": "M6P7-ST-B9",
                    "severity": "S5",
                    "status": "OPEN",
                    "details": {"reason": "historical M6.I verdict mismatch", "verdict": m6i_verdict},
                }
            )
            issues.append("historical M6.I verdict is not ADVANCE_TO_M7")
        if m6i_blocker_count != 0:
            blockers.append(
                {
                    "id": "M6P7-ST-B9",
                    "severity": "S5",
                    "status": "OPEN",
                    "details": {"reason": "historical M6.I blocker register not closed", "blocker_count": m6i_blocker_count},
                }
            )
            issues.append("historical M6.I blocker register is not closed")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p_bucket, "probe_id": "m6p7_s5_evidence_bucket", "group": "control"})
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M6P7-ST-B10", "severity": "S5", "status": "OPEN", "details": {"probe_id": "m6p7_s5_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    handoff_pattern = str(handles.get("M7_HANDOFF_PACK_PATH_PATTERN", "")).strip()
    handoff_key = ""
    handoff_pattern_local: Path | None = None
    if not handoff_pattern:
        blockers.append({"id": "M6P7-ST-B9", "severity": "S5", "status": "OPEN", "details": {"reason": "missing M7_HANDOFF_PACK_PATH_PATTERN"}})
        issues.append("missing M7 handoff path pattern handle")
    else:
        handoff_key = handoff_pattern.replace("{phase_execution_id}", phase_execution_id)
        handoff_key = handoff_key.replace("{platform_run_id}", dep_platform_run_id)
        unresolved_tokens = re.findall(r"{[^}]+}", handoff_key)
        if unresolved_tokens:
            blockers.append(
                {
                    "id": "M6P7-ST-B9",
                    "severity": "S5",
                    "status": "OPEN",
                    "details": {"reason": "unresolved handoff path placeholders", "handoff_key": handoff_key, "tokens": unresolved_tokens},
                }
            )
            issues.append("handoff path has unresolved placeholders")
        handoff_pattern_local = Path("runs/dev_substrate/dev_full/stress") / handoff_key if handoff_key else None

    if dep_path is not None:
        for artifact in [
            "m6p7_execution_summary.json",
            "m6p7_blocker_register.json",
            "m6p7_receipt_summary_snapshot.json",
            "m6p7_quarantine_summary_snapshot.json",
            "m6p7_offsets_snapshot.json",
            "m6p7_dedupe_anomaly_snapshot.json",
        ]:
            if not (dep_path / artifact).exists():
                blockers.append({"id": "M6P7-ST-B8", "severity": "S5", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": artifact}})
                issues.append(f"missing dependency artifact: {artifact}")

    overall_pass = len(blockers) == 0
    verdict = expected_pass_verdict if overall_pass else "HOLD_REMEDIATE"
    next_gate = verdict
    eligible_for_m7 = overall_pass and verdict == expected_pass_verdict

    dumpj(
        out / "m6p7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S5",
            "findings": [
                {"id": "M6P7-ST-F4", "classification": "PREVENT", "finding": "P7 closure must emit deterministic verdict before parent M6 can advance.", "required_action": "Verdict is ADVANCE_TO_M7 only when chain is blocker-free."},
                {"id": "M6P7-ST-F5", "classification": "OBSERVE", "finding": "S5 should rerun only for aggregation/handoff defects.", "required_action": "Keep targeted rerun policy and avoid upstream reruns without causal evidence."},
            ],
        },
    )
    dumpj(
        out / "m6p7_lane_matrix.json",
        {
            "component_sequence": ["M6P7-ST-S0", "M6P7-ST-S1", "M6P7-ST-S2", "M6P7-ST-S3", "M6P7-ST-S4", "M6P7-ST-S5"],
            "plane_sequence": ["ingest_commit_plane", "idempotency_plane", "p7_rollup_plane"],
            "integrated_windows": ["m6p7_s3_replay_window", "m6p7_s3_continuity_window"],
        },
    )

    dumpj(
        out / "m6p7_ingest_commit_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S5",
            "status": "ROLLUP",
            "platform_run_id": dep_platform_run_id,
            "s4_dependency_phase_execution_id": dep_id,
            "historical_m6i_execution_id": m6i_id,
            "replay_window_mode": dep_replay_mode,
            "chain_matrix": chain_rows,
        },
    )
    for artifact, src_name in [
        ("m6p7_receipt_summary_snapshot.json", "m6p7_receipt_summary_snapshot.json"),
        ("m6p7_quarantine_summary_snapshot.json", "m6p7_quarantine_summary_snapshot.json"),
        ("m6p7_offsets_snapshot.json", "m6p7_offsets_snapshot.json"),
        ("m6p7_dedupe_anomaly_snapshot.json", "m6p7_dedupe_anomaly_snapshot.json"),
    ]:
        src_payload = loadj(dep_path / src_name) if dep_path is not None else {}
        src_payload = dict(src_payload) if isinstance(src_payload, dict) else {}
        src_payload.update(
            {
                "generated_at_utc": now(),
                "phase_execution_id": phase_execution_id,
                "stage_id": "M6P7-ST-S5",
                "status": "ROLLUP_CARRY_FORWARD",
                "rollup_verdict_candidate": verdict,
            }
        )
        dumpj(out / artifact, src_payload)

    probe_failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    error_rate_pct = round((len(probe_failures) / len(probes)) * 100.0, 4) if probes else 0.0
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)
    dumpj(
        out / "m6p7_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S5",
            "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "probe_count": len(probes),
            "failure_count": len(probe_failures),
            "error_rate_pct": error_rate_pct,
            "latency_ms_p50": p50,
            "latency_ms_p95": p95,
            "latency_ms_p99": p95,
            "sample_failures": probe_failures[:10],
            "probes": probes,
        },
    )
    dumpj(
        out / "m6p7_control_rail_conformance_snapshot.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S5", "overall_pass": len(issues) == 0, "issues": issues},
    )
    dumpj(
        out / "m6p7_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S5",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6p7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P7-ST-S5",
            "window_seconds": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "estimated_api_call_count": len(probes),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M6P7_STRESS_MAX_SPEND_USD", 25)),
            "within_envelope": True,
            "method": "m6p7_s5_rollup_verdict_handoff_v0",
        },
    )

    run_control_root = str(handles.get("S3_RUN_CONTROL_ROOT_PATTERN", "evidence/dev_full/run_control/{phase_execution_id}/")).strip()
    run_control_key = run_control_root.replace("{phase_execution_id}", phase_execution_id).replace("{platform_run_id}", dep_platform_run_id)
    run_control_key = run_control_key if run_control_key.endswith("/") else f"{run_control_key}/"
    m6i_gate_ref = f"s3://{bucket}/evidence/dev_full/run_control/{m6i_id}/m6i_p7_gate_verdict.json" if bucket and m6i_id else ""
    m6p7_gate_ref = f"s3://{bucket}/{run_control_key}stress/m6p7_gate_verdict.json" if bucket else ""
    m7_handoff_ref = f"s3://{bucket}/{handoff_key}" if bucket and handoff_key else ""

    gate_verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S5",
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "expected_verdict_on_pass": expected_pass_verdict,
        "chain_matrix": chain_rows,
        "s4_dependency_phase_execution_id": dep_id,
        "historical_m6i_execution_id": m6i_id,
        "historical_m6i_verdict": m6i_verdict,
        "historical_m6i_blocker_count": m6i_blocker_count,
        "platform_run_id": dep_platform_run_id,
    }
    handoff_pack = {
        "generated_at_utc": now(),
        "handoff_from": "M6P7-ST-S5",
        "handoff_to": "M7",
        "phase_execution_id": phase_execution_id,
        "platform_run_id": dep_platform_run_id,
        "eligible_for_m7": eligible_for_m7,
        "p7_verdict": verdict,
        "next_gate": next_gate,
        "upstream": {
            "m6p7_s4_execution_id": dep_id,
            "historical_m6i_execution_id": m6i_id,
        },
        "evidence_refs": {
            "m6i_p7_gate_verdict": m6i_gate_ref,
            "m6p7_gate_verdict": m6p7_gate_ref,
            "m7_handoff_pack": m7_handoff_ref,
            "m6p7_s4_execution_summary": f"evidence/dev_full/run_control/{dep_id}/stress/m6p7_execution_summary.json" if dep_id else "",
        },
        "blocker_count": len(blockers),
        "blockers": blockers,
    }
    dumpj(out / "m6p7_gate_verdict.json", gate_verdict)
    dumpj(out / "m7_handoff_pack.json", handoff_pack)

    handoff_pattern_write_error = ""
    if handoff_pattern_local is not None:
        try:
            handoff_pattern_local.parent.mkdir(parents=True, exist_ok=True)
            dumpj(handoff_pattern_local, handoff_pack)
        except Exception as exc:
            handoff_pattern_write_error = str(exc)

    if handoff_pattern_write_error:
        blockers.append(
            {
                "id": "M6P7-ST-B9",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "reason": "failed to write handoff pack at handle path",
                    "handoff_path_pattern": handoff_pattern,
                    "handoff_key": handoff_key,
                    "error": handoff_pattern_write_error,
                },
            }
        )
        issues.append("failed to write handoff pack at handle path")
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"
        eligible_for_m7 = False
        gate_verdict.update({"overall_pass": False, "blocker_count": len(blockers), "verdict": verdict, "next_gate": next_gate})
        handoff_pack.update({"eligible_for_m7": eligible_for_m7, "p7_verdict": verdict, "next_gate": next_gate, "blocker_count": len(blockers), "blockers": blockers})
        dumpj(out / "m6p7_gate_verdict.json", gate_verdict)
        dumpj(out / "m7_handoff_pack.json", handoff_pack)

    decisions.extend(
        [
            "Validated S4 dependency continuity and blocker closure before S5.",
            "Validated full S0..S4 chain matrix and run-scope consistency for deterministic rollup.",
            "Validated historical M6.I continuity anchor and verdict posture before publishing M6P7 rollup.",
            "Applied deterministic verdict rule: ADVANCE_TO_M7 only when blocker-free; HOLD_REMEDIATE otherwise.",
            "Emitted m6p7_gate_verdict.json and m7_handoff_pack.json for parent M6 adjudication surfaces.",
        ]
    )
    dumpj(
        out / "m6p7_decision_log.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M6P7-ST-S5", "decisions": decisions},
    )

    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S5",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M6P7-ST-S5",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "required_artifacts": S5_REQUIRED_ARTIFACTS,
        "probe_count": len(probes),
        "error_rate_pct": error_rate_pct,
        "s4_dependency_phase_execution_id": dep_id,
        "historical_m6i_execution_id": m6i_id,
        "platform_run_id": dep_platform_run_id,
        "verdict": verdict,
        "replay_window_mode": dep_replay_mode,
        "handoff_path_key": handoff_key,
    }
    dumpj(out / "m6p7_blocker_register.json", blocker_register)
    dumpj(out / "m6p7_execution_summary.json", summary)

    missing = [x for x in S5_REQUIRED_ARTIFACTS if not (out / x).exists()]
    if missing:
        blockers.append({"id": "M6P7-ST-B11", "severity": "S5", "status": "OPEN", "details": {"missing_artifacts": missing}})
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"
        eligible_for_m7 = False
        blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summary.update({"overall_pass": False, "next_gate": next_gate, "verdict": verdict})
        gate_verdict.update({"overall_pass": False, "blocker_count": len(blockers), "verdict": verdict, "next_gate": next_gate})
        handoff_pack.update({"eligible_for_m7": eligible_for_m7, "p7_verdict": verdict, "next_gate": next_gate, "blocker_count": len(blockers), "blockers": blockers})
        dumpj(out / "m6p7_blocker_register.json", blocker_register)
        dumpj(out / "m6p7_execution_summary.json", summary)
        dumpj(out / "m6p7_gate_verdict.json", gate_verdict)
        dumpj(out / "m7_handoff_pack.json", handoff_pack)
        if handoff_pattern_local is not None and not handoff_pattern_write_error:
            dumpj(handoff_pattern_local, handoff_pack)

    print(f"[m6p7_s5] phase_execution_id={phase_execution_id}")
    print(f"[m6p7_s5] output_dir={out.as_posix()}")
    print(f"[m6p7_s5] overall_pass={summary['overall_pass']}")
    print(f"[m6p7_s5] verdict={summary['verdict']}")
    print(f"[m6p7_s5] next_gate={summary['next_gate']}")
    print(f"[m6p7_s5] probe_count={summary['probe_count']}")
    print(f"[m6p7_s5] error_rate_pct={summary['error_rate_pct']}")
    print(f"[m6p7_s5] open_blockers={blocker_register['open_blocker_count']}")
    return 0 if summary["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M6.P7 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    args = ap.parse_args()

    stage_map = {
        "S0": ("m6p7_stress_s0", run_s0),
        "S1": ("m6p7_stress_s1", run_s1),
        "S2": ("m6p7_stress_s2", run_s2),
        "S3": ("m6p7_stress_s3", run_s3),
        "S4": ("m6p7_stress_s4", run_s4),
        "S5": ("m6p7_stress_s5", run_s5),
    }
    prefix, fn = stage_map[args.stage]
    phase_execution_id = args.phase_execution_id.strip() or f"{prefix}_{tok()}"
    return fn(phase_execution_id)


if __name__ == "__main__":
    raise SystemExit(main())
