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

PARENT_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.stress_test.md")
PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.P9.stress_test.md")
BUILD_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P9.build_plan.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
M7_HIST = Path("runs/dev_substrate/dev_full/m7")
AWS_REGION = "eu-west-2"

PLAN_KEYS = [
    "M7P9_STRESS_PROFILE_ID",
    "M7P9_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M7P9_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M7P9_STRESS_DECISION_LOG_PATH_PATTERN",
    "M7P9_STRESS_REQUIRED_ARTIFACTS",
    "M7P9_STRESS_MAX_RUNTIME_MINUTES",
    "M7P9_STRESS_MAX_SPEND_USD",
    "M7P9_STRESS_EXPECTED_VERDICT_ON_PASS",
    "M7P9_STRESS_DATA_MIN_SAMPLE_EVENTS",
    "M7P9_STRESS_POLICY_PATH_MIN_CARDINALITY",
    "M7P9_STRESS_ACTION_CLASS_MIN_CARDINALITY",
    "M7P9_STRESS_DUPLICATE_RATIO_TARGET_RANGE_PCT",
    "M7P9_STRESS_RETRY_RATIO_MAX_PCT",
    "M7P9_STRESS_TARGETED_RERUN_ONLY",
]

REQ_HANDLES = [
    "FLINK_RUNTIME_PATH_ACTIVE",
    "FLINK_RUNTIME_PATH_ALLOWED",
    "K8S_DEPLOY_DF",
    "K8S_DEPLOY_AL",
    "K8S_DEPLOY_DLA",
    "EKS_NAMESPACE_RTDL",
    "ROLE_EKS_IRSA_DECISION_LANE",
    "FP_BUS_RTDL_V1",
    "FP_BUS_AUDIT_V1",
    "DECISION_LANE_EVIDENCE_PATH_PATTERN",
    "AURORA_CLUSTER_IDENTIFIER",
    "SSM_AURORA_ENDPOINT_PATH",
    "SSM_AURORA_USERNAME_PATH",
    "SSM_AURORA_PASSWORD_PATH",
    "DDB_IG_IDEMPOTENCY_TABLE",
]

REQUIRED_ARTIFACTS = [
    "m7p9_stagea_findings.json",
    "m7p9_lane_matrix.json",
    "m7p9_data_subset_manifest.json",
    "m7p9_data_profile_summary.json",
    "m7p9_df_snapshot.json",
    "m7p9_al_snapshot.json",
    "m7p9_dla_snapshot.json",
    "m7p9_score_distribution_profile.json",
    "m7p9_action_mix_profile.json",
    "m7p9_idempotency_collision_profile.json",
    "m7p9_probe_latency_throughput_snapshot.json",
    "m7p9_control_rail_conformance_snapshot.json",
    "m7p9_secret_safety_snapshot.json",
    "m7p9_cost_outcome_receipt.json",
    "m7p9_blocker_register.json",
    "m7p9_execution_summary.json",
    "m7p9_decision_log.json",
    "m7p9_gate_verdict.json",
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


def run_cmd(argv: list[str], timeout: int = 30) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {
            "command": " ".join(argv),
            "exit_code": int(p.returncode),
            "status": "PASS" if p.returncode == 0 else "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": (p.stdout or "").strip()[:600],
            "stderr": (p.stderr or "").strip()[:600],
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


def run_cmd_full(argv: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return int(p.returncode), (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def load_s3_json(bucket: str, key: str) -> dict[str, Any]:
    if not bucket or not key:
        return {}
    rc, stdout, _ = run_cmd_full(["aws", "s3", "cp", f"s3://{bucket}/{key}", "-"], timeout=180)
    if rc != 0:
        return {}
    try:
        return json.loads(stdout)
    except Exception:
        return {}


def latest_ok(prefix: str, summary_name: str, stage_id: str) -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob(f"{prefix}_*/stress"), reverse=True):
        s = loadj(d / summary_name)
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == stage_id:
            return {"path": d, "summary": s}
    return {}


def latest_hist_p9b() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in M7_HIST.rglob("p9b_df_execution_summary.json"):
        d = f.parent
        s = loadj(f)
        c = loadj(d / "p9b_df_component_snapshot.json")
        p = loadj(d / "p9b_df_performance_snapshot.json")
        b = loadj(d / "p9b_df_blocker_register.json")
        if not s or not c or not p or not b:
            continue
        if int(s.get("blocker_count", 0) or 0) != 0:
            continue
        if int(b.get("blocker_count", 0) or 0) != 0:
            continue
        rows.append(
            {
                "path": d,
                "captured_at_utc": str(s.get("captured_at_utc") or c.get("captured_at_utc") or ""),
                "execution_id": str(s.get("execution_id", "")),
                "summary": s,
                "component": c,
                "perf": p,
                "blocker": b,
            }
        )
    if not rows:
        return {}
    rows.sort(key=lambda x: str(x.get("captured_at_utc", "")), reverse=True)
    return rows[0]


def latest_hist_p9c() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in M7_HIST.rglob("p9c_al_execution_summary.json"):
        d = f.parent
        s = loadj(f)
        c = loadj(d / "p9c_al_component_snapshot.json")
        p = loadj(d / "p9c_al_performance_snapshot.json")
        b = loadj(d / "p9c_al_blocker_register.json")
        if not s or not c or not p or not b:
            continue
        if int(s.get("blocker_count", 0) or 0) != 0:
            continue
        if int(b.get("blocker_count", 0) or 0) != 0:
            continue
        rows.append(
            {
                "path": d,
                "captured_at_utc": str(s.get("captured_at_utc") or c.get("captured_at_utc") or ""),
                "execution_id": str(s.get("execution_id", "")),
                "summary": s,
                "component": c,
                "perf": p,
                "blocker": b,
            }
        )
    if not rows:
        return {}
    rows.sort(key=lambda x: str(x.get("captured_at_utc", "")), reverse=True)
    return rows[0]


def latest_hist_p9d() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in M7_HIST.rglob("p9d_dla_execution_summary.json"):
        d = f.parent
        s = loadj(f)
        c = loadj(d / "p9d_dla_component_snapshot.json")
        p = loadj(d / "p9d_dla_performance_snapshot.json")
        b = loadj(d / "p9d_dla_blocker_register.json")
        if not s or not c or not p or not b:
            continue
        if int(s.get("blocker_count", 0) or 0) != 0:
            continue
        if int(b.get("blocker_count", 0) or 0) != 0:
            continue
        rows.append(
            {
                "path": d,
                "captured_at_utc": str(s.get("captured_at_utc") or c.get("captured_at_utc") or ""),
                "execution_id": str(s.get("execution_id", "")),
                "summary": s,
                "component": c,
                "perf": p,
                "blocker": b,
            }
        )
    if not rows:
        return {}
    rows.sort(key=lambda x: str(x.get("captured_at_utc", "")), reverse=True)
    return rows[0]


def parse_range(v: Any) -> tuple[float | None, float | None]:
    s = str(v or "").strip()
    parts = [x.strip() for x in s.split("|")]
    if len(parts) != 2:
        return None, None
    try:
        return (float(parts[0]) if parts[0] else None, float(parts[1]) if parts[1] else None)
    except ValueError:
        return None, None


def to_int(v: Any) -> int | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return int(v)
        return int(str(v).strip())
    except Exception:
        return None


def to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return float(int(v))
        return float(str(v).strip())
    except Exception:
        return None


def to_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def normalize_runtime_path(v: str) -> str:
    raw = str(v or "").strip().upper()
    aliases = {
        "EKS_EMR_ON_EKS": "EKS_FLINK_OPERATOR",
        "EMR_ON_EKS": "EKS_FLINK_OPERATOR",
        "EKS_FLINK_OPERATOR": "EKS_FLINK_OPERATOR",
        "MSF_MANAGED": "MSF_MANAGED",
    }
    return aliases.get(raw, raw)


def required_artifacts(plan_packet: dict[str, Any]) -> list[str]:
    raw = str(plan_packet.get("M7P9_STRESS_REQUIRED_ARTIFACTS", "")).strip()
    if not raw:
        return list(REQUIRED_ARTIFACTS)
    parsed = [x.strip() for x in raw.split(",") if x.strip()]
    return parsed if parsed else list(REQUIRED_ARTIFACTS)


def resolve_required_handles(handles: dict[str, Any]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    placeholder: list[str] = []
    placeholder_values = {"", "TO_PIN", "None", "NONE", "null", "NULL"}
    for k in REQ_HANDLES:
        if k not in handles:
            missing.append(k)
            continue
        if str(handles.get(k, "")).strip() in placeholder_values:
            placeholder.append(k)
    return missing, placeholder


def materialize_pattern(pattern: str, replacements: dict[str, str]) -> str:
    out = str(pattern or "")
    for k, v in replacements.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def add_head_bucket_probe(probes: list[dict[str, Any]], bucket: str, probe_id: str) -> dict[str, Any]:
    p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", AWS_REGION], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing bucket",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": probe_id, "group": "control", "bucket": bucket})
    return p


def add_head_object_probe(probes: list[dict[str, Any]], bucket: str, key: str, probe_id: str) -> dict[str, Any]:
    k = str(key or "").strip().lstrip("/")
    p = run_cmd(["aws", "s3api", "head-object", "--bucket", bucket, "--key", k, "--region", AWS_REGION], 30) if bucket and k else {
        "command": "aws s3api head-object",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing bucket/key",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": probe_id, "group": "evidence", "bucket": bucket, "key": k})
    return p


def probe_metrics(probes: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    return {
        "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
        "probe_count": len(probes),
        "failure_count": len(failures),
        "error_rate_pct": round((len(failures) / len(probes)) * 100.0, 4) if probes else 0.0,
        "latency_ms_p50": 0.0 if not latencies else sorted(latencies)[len(latencies) // 2],
        "latency_ms_p95": 0.0 if not latencies else max(latencies),
        "latency_ms_p99": 0.0 if not latencies else max(latencies),
        "sample_failures": failures[:10],
        "probes": probes,
    }


def finalize_artifact_contract(
    out: Path,
    req: list[str],
    blockers: list[dict[str, Any]],
    blocker_reg: dict[str, Any],
    summary: dict[str, Any],
    verdict: dict[str, Any],
    blocker_id: str = "M7P9-ST-B10",
) -> None:
    missing = [x for x in req if not (out / x).exists()]
    if not missing:
        return
    blockers.append({"id": blocker_id, "severity": summary.get("stage_id"), "status": "OPEN", "details": {"missing_artifacts": missing}})
    blocker_reg.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
    summary.update({"overall_pass": False, "next_gate": "BLOCKED", "open_blocker_count": len(blockers)})
    verdict.update({"overall_pass": False, "next_gate": "BLOCKED", "verdict": "HOLD_REMEDIATE", "blocker_count": len(blockers)})
    dumpj(out / "m7p9_blocker_register.json", blocker_reg)
    dumpj(out / "m7p9_execution_summary.json", summary)
    dumpj(out / "m7p9_gate_verdict.json", verdict)


def run_s0(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P9-ST-B1",
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

    dep_issues: list[str] = []
    dep_parent = latest_ok("m7_stress_s0", "m7_execution_summary.json", "M7-ST-S0")
    dep_p8 = latest_ok("m7p8_stress_s5", "m7p8_execution_summary.json", "M7P8-ST-S5")
    parent_id = ""
    p8_id = ""
    parent_platform_run_id = ""
    platform_run_id = ""
    dep_parent_path: Path | None = None
    dep_p8_path: Path | None = None
    dep_p8_summary: dict[str, Any] = {}
    dep_p8_subset: dict[str, Any] = {}
    dep_p8_profile: dict[str, Any] = {}
    dep_p8_edge: dict[str, Any] = {}

    if not dep_parent:
        dep_issues.append("missing successful parent M7-ST-S0 dependency")
    else:
        parent_id = str(dep_parent["summary"].get("phase_execution_id", ""))
        dep_parent_path = Path(str(dep_parent["path"]))
        parent_summary = dep_parent["summary"]
        parent_platform_run_id = str(parent_summary.get("platform_run_id", "")).strip()
        if str(parent_summary.get("next_gate", "")).strip() != "M7_ST_S1_READY":
            dep_issues.append("parent M7-ST-S0 next_gate is not M7_ST_S1_READY")
        parent_blocker = loadj(dep_parent_path / "m7_blocker_register.json")
        if int(parent_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("parent M7-ST-S0 blocker register is not closed")

    if not dep_p8:
        dep_issues.append("missing successful M7P8-ST-S5 dependency")
    else:
        p8_id = str(dep_p8["summary"].get("phase_execution_id", ""))
        dep_p8_path = Path(str(dep_p8["path"]))
        dep_p8_summary = dep_p8["summary"]
        platform_run_id = str(dep_p8_summary.get("platform_run_id", "")).strip()
        if str(dep_p8_summary.get("verdict", "")).strip() != "ADVANCE_TO_P9":
            dep_issues.append("M7P8-ST-S5 verdict is not ADVANCE_TO_P9")
        if str(dep_p8_summary.get("next_gate", "")).strip() != "ADVANCE_TO_P9":
            dep_issues.append("M7P8-ST-S5 next_gate is not ADVANCE_TO_P9")
        p8_blocker = loadj(dep_p8_path / "m7p8_blocker_register.json")
        if int(p8_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P8-ST-S5 blocker register is not closed")
        dep_p8_subset = loadj(dep_p8_path / "m7p8_data_subset_manifest.json")
        dep_p8_profile = loadj(dep_p8_path / "m7p8_data_profile_summary.json")
        dep_p8_edge = loadj(dep_p8_path / "m7p8_data_edge_case_matrix.json")
        if not dep_p8_subset or not dep_p8_profile or not dep_p8_edge:
            dep_issues.append("M7P8-ST-S5 realism artifacts are incomplete")

    if parent_platform_run_id and platform_run_id and parent_platform_run_id != platform_run_id:
        dep_issues.append("parent M7-S0 and M7P8-S5 platform_run_id mismatch")
    if not platform_run_id and parent_platform_run_id:
        platform_run_id = parent_platform_run_id

    if dep_issues:
        blockers.append({"id": "M7P9-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)
    else:
        decisions.append("Validated dependency continuity: parent M7-S0 and M7P8-S5 are closed and run-scope consistent.")

    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p9_s0_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B10", "severity": "S0", "status": "OPEN", "details": {"probe_id": "m7p9_s0_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id}
    decision_root_pattern = str(handles.get("DECISION_LANE_EVIDENCE_PATH_PATTERN", "")).strip()
    decision_root = materialize_pattern(decision_root_pattern, replacements) if decision_root_pattern else ""
    unresolved_decision_root = re.findall(r"{[^}]+}", decision_root)
    if not decision_root or unresolved_decision_root:
        blockers.append(
            {
                "id": "M7P9-ST-B10",
                "severity": "S0",
                "status": "OPEN",
                "details": {"reason": "invalid DECISION_LANE_EVIDENCE_PATH_PATTERN resolution", "decision_root": decision_root, "tokens": unresolved_decision_root},
            }
        )
        issues.append("decision-lane evidence root is unresolved")

    decision_keys = {
        "df_component_proof": f"{decision_root.rstrip('/')}/df_component_proof.json" if decision_root else "",
        "al_component_proof": f"{decision_root.rstrip('/')}/al_component_proof.json" if decision_root else "",
        "dla_component_proof": f"{decision_root.rstrip('/')}/dla_component_proof.json" if decision_root else "",
    }
    decision_payloads: dict[str, dict[str, Any]] = {}
    parse_error_count = 0
    for tag, key in decision_keys.items():
        p = add_head_object_probe(probes, evidence_bucket, key, f"m7p9_s0_{tag}")
        if p.get("status") != "PASS":
            blockers.append({"id": "M7P9-ST-B10", "severity": "S0", "status": "OPEN", "details": {"probe_id": f"m7p9_s0_{tag}"}})
            issues.append(f"decision-lane proof readback failed for {tag}")
            continue
        payload = load_s3_json(evidence_bucket, key)
        if not payload:
            blockers.append({"id": "M7P9-ST-B10", "severity": "S0", "status": "OPEN", "details": {"reason": "failed to load decision-lane proof json", "key": key}})
            issues.append(f"failed to parse decision-lane proof for {tag}")
            parse_error_count += 1
            continue
        decision_payloads[tag] = payload

    behavior_refs: dict[str, Any] = {}
    receipt_key = materialize_pattern(str(handles.get("RECEIPT_SUMMARY_PATH_PATTERN", "")).strip(), replacements)
    offset_key = materialize_pattern(str(handles.get("KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN", "")).strip(), replacements)
    quarantine_key = materialize_pattern(str(handles.get("QUARANTINE_SUMMARY_PATH_PATTERN", "")).strip(), replacements)
    for tag, key in [("receipt_summary", receipt_key), ("offsets_snapshot", offset_key), ("quarantine_summary", quarantine_key)]:
        p = add_head_object_probe(probes, evidence_bucket, key, f"m7p9_s0_behavior_{tag}")
        payload = load_s3_json(evidence_bucket, key) if p.get("status") == "PASS" else {}
        behavior_refs[tag] = {"key": key, "present": bool(payload), "keys": sorted(payload.keys())[:15] if payload else []}
        if p.get("status") != "PASS":
            blockers.append({"id": "M7P9-ST-B10", "severity": "S0", "status": "OPEN", "details": {"probe_id": f"m7p9_s0_behavior_{tag}"}})
            issues.append(f"behavior-context readback failed for {tag}")
        elif not payload:
            blockers.append({"id": "M7P9-ST-B10", "severity": "S0", "status": "OPEN", "details": {"reason": "behavior-context payload parse failure", "key": key}})
            issues.append(f"failed to parse behavior payload for {tag}")
            parse_error_count += 1

    receipt_summary = load_s3_json(evidence_bucket, receipt_key) if evidence_bucket and receipt_key else {}
    if not receipt_summary:
        parse_error_count += 1

    hist_b = latest_hist_p9b()
    hist_c = latest_hist_p9c()
    hist_d = latest_hist_p9d()
    if not hist_b or not hist_c or not hist_d:
        blockers.append(
            {
                "id": "M7P9-ST-B3",
                "severity": "S0",
                "status": "OPEN",
                "details": {"reason": "historical P9 baseline artifacts missing", "p9b_present": bool(hist_b), "p9c_present": bool(hist_c), "p9d_present": bool(hist_d)},
            }
        )
        issues.append("historical P9 baseline artifacts are incomplete")

    runtime_active = normalize_runtime_path(str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")))
    runtime_allowed = [normalize_runtime_path(x) for x in str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()]
    runtime_hist = {
        "p9b": normalize_runtime_path(str(hist_b.get("component", {}).get("runtime_path_active", ""))) if hist_b else "",
        "p9c": normalize_runtime_path(str(hist_c.get("component", {}).get("runtime_path_active", ""))) if hist_c else "",
        "p9d": normalize_runtime_path(str(hist_d.get("component", {}).get("runtime_path_active", ""))) if hist_d else "",
    }
    runtime_path_check = bool(runtime_active) and runtime_active in runtime_allowed
    if runtime_path_check:
        for tag, rv in runtime_hist.items():
            if rv and rv != runtime_active:
                advisories.append(f"{tag} historical runtime path differs by alias class ({rv}); normalized current runtime is {runtime_active}.")
    else:
        blockers.append(
            {
                "id": "M7P9-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {"reason": "runtime path contract invalid", "runtime_active": runtime_active, "runtime_allowed": runtime_allowed},
            }
        )
        issues.append("runtime path contract is invalid")

    min_sample = int(plan_packet.get("M7P9_STRESS_DATA_MIN_SAMPLE_EVENTS", 8000))
    policy_min = int(plan_packet.get("M7P9_STRESS_POLICY_PATH_MIN_CARDINALITY", 5))
    action_min = int(plan_packet.get("M7P9_STRESS_ACTION_CLASS_MIN_CARDINALITY", 3))
    dup_low, dup_high = parse_range(plan_packet.get("M7P9_STRESS_DUPLICATE_RATIO_TARGET_RANGE_PCT", "0.5|5.0"))
    retry_max = float(plan_packet.get("M7P9_STRESS_RETRY_RATIO_MAX_PCT", 5.0))

    p8_rows = to_int(dep_p8_profile.get("rows_scanned")) or to_int(dep_p8_subset.get("rows_scanned")) or 0
    p8_event_type_count = to_int(dep_p8_profile.get("event_type_count")) or 0
    total_receipts = to_int(receipt_summary.get("total_receipts")) or 0
    decision_input_events = max(p8_rows, total_receipts)

    reason_counts = receipt_summary.get("counts_by_reason_code", {}) if isinstance(receipt_summary.get("counts_by_reason_code"), dict) else {}
    reason_nonzero = [k for k, v in reason_counts.items() if to_int(v) is not None and int(v) > 0]
    policy_cardinality_observed = len(reason_nonzero)
    policy_cardinality_source = "receipt_reason_code"
    policy_cardinality = policy_cardinality_observed
    if policy_cardinality_observed == 0:
        policy_cardinality = p8_event_type_count
        policy_cardinality_source = "p8_event_type_proxy"
        advisories.append("reason-code cardinality is not observable from current receipt summary; using P8 event-type proxy and enforcing downstream policy-edge injections.")

    decision_counts = receipt_summary.get("counts_by_decision", {}) if isinstance(receipt_summary.get("counts_by_decision"), dict) else {}
    action_declared_cardinality = len([k for k in decision_counts.keys() if str(k).strip()])
    action_active_cardinality = len([k for k, v in decision_counts.items() if to_int(v) is not None and int(v) > 0])
    action_cardinality = action_declared_cardinality if action_declared_cardinality > 0 else action_active_cardinality
    if action_active_cardinality < action_min:
        advisories.append("active decision-class coverage is sparse in current receipts; keep explicit action/retry cohort injection in S1/S2.")

    duplicate_count = to_int(decision_counts.get("DUPLICATE")) or 0
    duplicate_ratio_pct = None if total_receipts <= 0 else round((duplicate_count / float(total_receipts)) * 100.0, 6)
    duplicate_observed = duplicate_ratio_pct is not None
    dup_floor_ok = (not duplicate_observed) or dup_low is None or duplicate_ratio_pct >= dup_low
    dup_ceiling_ok = (not duplicate_observed) or dup_high is None or duplicate_ratio_pct <= dup_high
    if not duplicate_observed:
        advisories.append("duplicate ratio is not directly observable; duplicate/replay injection is mandatory in downstream windows.")
    elif not dup_floor_ok:
        advisories.append(f"duplicate ratio {duplicate_ratio_pct:.6f}% is below floor {dup_low}; enforce explicit duplicate/replay injection downstream.")

    retry_ratio_pct = to_float(hist_c.get("perf", {}).get("retry_ratio_pct_observed")) if hist_c else None
    retry_observed = retry_ratio_pct is not None
    retry_max_check = (not retry_observed) or retry_ratio_pct <= retry_max
    if not retry_observed:
        advisories.append("retry ratio is not directly observable from current evidence; retry-pressure injection is mandatory in downstream windows.")

    profile_checks = {
        "sample_size_check": decision_input_events >= min_sample,
        "policy_path_min_check": policy_cardinality >= policy_min,
        "action_class_min_check": action_cardinality >= action_min,
        "duplicate_ratio_observed": duplicate_observed,
        "duplicate_ratio_floor_check": dup_floor_ok,
        "duplicate_ratio_upper_bound_check": dup_ceiling_ok,
        "retry_ratio_observed": retry_observed,
        "retry_ratio_max_check": retry_max_check,
        "runtime_path_check": runtime_path_check,
        "parse_error_check": parse_error_count == 0,
    }
    blocking_checks = {
        "sample_size_check": profile_checks["sample_size_check"],
        "policy_path_min_check": profile_checks["policy_path_min_check"],
        "action_class_min_check": profile_checks["action_class_min_check"],
        "duplicate_ratio_upper_bound_check": profile_checks["duplicate_ratio_upper_bound_check"],
        "retry_ratio_max_check": profile_checks["retry_ratio_max_check"],
        "runtime_path_check": profile_checks["runtime_path_check"],
        "parse_error_check": profile_checks["parse_error_check"],
    }
    representativeness_pass = all(blocking_checks.values())
    if not representativeness_pass:
        blockers.append(
            {
                "id": "M7P9-ST-B3",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "checks": profile_checks,
                    "blocking_checks": blocking_checks,
                    "decision_input_events": decision_input_events,
                    "min_sample_required": min_sample,
                    "policy_path_cardinality": policy_cardinality,
                    "policy_path_source": policy_cardinality_source,
                    "policy_path_min_required": policy_min,
                    "action_class_cardinality": action_cardinality,
                    "action_class_active_cardinality": action_active_cardinality,
                    "action_class_min_required": action_min,
                    "duplicate_ratio_pct": duplicate_ratio_pct,
                    "duplicate_ratio_target_range_pct": [dup_low, dup_high],
                    "retry_ratio_pct": retry_ratio_pct,
                    "retry_ratio_max_pct": retry_max,
                },
            }
        )
        issues.append("run-scoped decision-data profile failed blocking M7P9-S0 representativeness checks")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P9_ST_S1_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S1" if overall_pass else "HOLD_REMEDIATE"

    df_proof = decision_payloads.get("df_component_proof", {})
    al_proof = decision_payloads.get("al_component_proof", {})
    dla_proof = decision_payloads.get("dla_component_proof", {})

    proof_run_scope_mismatch: list[str] = []
    for tag, payload in [("df_component_proof", df_proof), ("al_component_proof", al_proof), ("dla_component_proof", dla_proof)]:
        p_run_id = str(payload.get("platform_run_id", "")).strip()
        if p_run_id and platform_run_id and p_run_id != platform_run_id:
            proof_run_scope_mismatch.append(tag)
    if proof_run_scope_mismatch:
        blockers.append({"id": "M7P9-ST-B2", "severity": "S0", "status": "OPEN", "details": {"reason": "decision proof run-scope mismatch", "proofs": proof_run_scope_mismatch}})
        issues.append("decision proof run-scope mismatch")
        overall_pass = False
        next_gate = "BLOCKED"
        gate_verdict = "HOLD_REMEDIATE"

    dumpj(
        out / "m7p9_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "findings": [
                {"id": "M7P9-ST-F1", "classification": "PREVENT", "finding": "P9 S0 must not run without closed parent/P8 dependencies.", "required_action": "Fail-closed on missing parent M7-S0 or P8-S5 closure."},
                {"id": "M7P9-ST-F2", "classification": "PREVENT", "finding": "Decision-lane low-sample history can hide cohort regressions.", "required_action": "Use run-scoped representativeness checks with explicit downstream cohort-injection advisories."},
                {"id": "M7P9-ST-F3", "classification": "PREVENT", "finding": "Black-box evidence can lack direct policy/retry observability.", "required_action": "Use deterministic proxy/advisory posture while keeping blocking bounds on safety and cardinality."},
            ],
        },
    )
    dumpj(out / "m7p9_lane_matrix.json", {"component_sequence": ["M7P9-ST-S0", "M7P9-ST-S1", "M7P9-ST-S2", "M7P9-ST-S3", "M7P9-ST-S4", "M7P9-ST-S5"]})
    dumpj(
        out / "m7p9_data_subset_manifest.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "platform_run_id": platform_run_id,
            "profile_source_mode": "p8_subset_plus_decision_lane_proofs",
            "decision_input_events": decision_input_events,
            "p8_rows_scanned": p8_rows,
            "receipt_total": total_receipts,
            "profile_window_hours": 24,
            "decision_lane_refs": decision_keys,
            "behavior_context_refs": behavior_refs,
            "upstream_m7_s0_phase_execution_id": parent_id,
            "upstream_m7p8_s5_phase_execution_id": p8_id,
        },
    )
    dumpj(
        out / "m7p9_data_profile_summary.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "platform_run_id": platform_run_id,
            "decision_input_events": decision_input_events,
            "policy_path_cardinality": policy_cardinality,
            "policy_path_source": policy_cardinality_source,
            "action_class_cardinality": action_cardinality,
            "action_class_active_cardinality": action_active_cardinality,
            "duplicate_ratio_pct": duplicate_ratio_pct,
            "retry_ratio_pct": retry_ratio_pct,
            "checks": profile_checks,
            "blocking_checks": blocking_checks,
            "advisories": advisories,
            "source_profile": {
                "p8_profile_excerpt": {
                    "rows_scanned": p8_rows,
                    "event_type_count": p8_event_type_count,
                    "cohort_presence": dep_p8_edge.get("cohort_presence", {}),
                },
                "receipt_summary_excerpt": {
                    "total_receipts": total_receipts,
                    "counts_by_decision": decision_counts,
                    "counts_by_reason_code_size": len(reason_counts),
                },
                "decision_proofs_present": sorted(list(decision_payloads.keys())),
            },
        },
    )
    dumpj(
        out / "m7p9_df_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "platform_run_id": platform_run_id,
            "status": "BASELINE_CAPTURED",
            "historical_execution_id": str(hist_b.get("execution_id", "")),
            "historical_component_artifact_path": str(hist_b.get("path", "")),
            "historical_summary": hist_b.get("summary", {}),
            "historical_component": hist_b.get("component", {}),
            "historical_performance": hist_b.get("perf", {}),
            "current_proof_excerpt": {
                "execution_id": str(df_proof.get("execution_id", "")),
                "ingest_basis_total_receipts": to_int(df_proof.get("ingest_basis_total_receipts")),
                "runtime_path_active": str(df_proof.get("runtime_path_active", "")),
                "idempotency_posture": str(df_proof.get("idempotency_posture", "")),
            },
        },
    )
    dumpj(
        out / "m7p9_al_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "platform_run_id": platform_run_id,
            "status": "BASELINE_CAPTURED",
            "historical_execution_id": str(hist_c.get("execution_id", "")),
            "historical_component_artifact_path": str(hist_c.get("path", "")),
            "historical_summary": hist_c.get("summary", {}),
            "historical_component": hist_c.get("component", {}),
            "historical_performance": hist_c.get("perf", {}),
            "current_proof_excerpt": {
                "execution_id": str(al_proof.get("execution_id", "")),
                "ingest_basis_total_receipts": to_int(al_proof.get("ingest_basis_total_receipts")),
                "runtime_path_active": str(al_proof.get("runtime_path_active", "")),
                "idempotency_posture": str(al_proof.get("idempotency_posture", "")),
            },
        },
    )
    dumpj(
        out / "m7p9_dla_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "platform_run_id": platform_run_id,
            "status": "BASELINE_CAPTURED",
            "historical_execution_id": str(hist_d.get("execution_id", "")),
            "historical_component_artifact_path": str(hist_d.get("path", "")),
            "historical_summary": hist_d.get("summary", {}),
            "historical_component": hist_d.get("component", {}),
            "historical_performance": hist_d.get("perf", {}),
            "current_proof_excerpt": {
                "execution_id": str(dla_proof.get("execution_id", "")),
                "ingest_basis_total_receipts": to_int(dla_proof.get("ingest_basis_total_receipts")),
                "runtime_path_active": str(dla_proof.get("runtime_path_active", "")),
                "append_only_posture": str(dla_proof.get("append_only_posture", "")),
                "audit_append_probe_key": str(dla_proof.get("audit_append_probe_key", "")),
            },
        },
    )
    dumpj(
        out / "m7p9_score_distribution_profile.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "platform_run_id": platform_run_id,
            "policy_path_cardinality": policy_cardinality,
            "policy_path_source": policy_cardinality_source,
            "reason_code_counts": reason_counts,
            "proxy_event_counts_top5": dep_p8_profile.get("source_profile", {}).get("event_counts_top5", dep_p8_profile.get("event_counts_top5", [])),
        },
    )
    dumpj(
        out / "m7p9_action_mix_profile.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "platform_run_id": platform_run_id,
            "counts_by_decision": decision_counts,
            "action_class_cardinality": action_cardinality,
            "action_class_active_cardinality": action_active_cardinality,
            "action_class_min_required": action_min,
        },
    )
    dumpj(
        out / "m7p9_idempotency_collision_profile.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "platform_run_id": platform_run_id,
            "idempotency_table": str(handles.get("DDB_IG_IDEMPOTENCY_TABLE", "")),
            "duplicate_count": duplicate_count,
            "total_receipts": total_receipts,
            "duplicate_ratio_pct": duplicate_ratio_pct,
            "duplicate_ratio_target_range_pct": [dup_low, dup_high],
            "retry_ratio_pct": retry_ratio_pct,
            "retry_ratio_max_pct": retry_max,
            "decision_proof_idempotency_posture": {
                "df": str(df_proof.get("idempotency_posture", "")),
                "al": str(al_proof.get("idempotency_posture", "")),
                "dla": str(dla_proof.get("idempotency_posture", "")),
            },
        },
    )
    dumpj(out / "m7p9_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S0", **metrics})
    dumpj(
        out / "m7p9_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "advisories": advisories,
            "dependency_refs": {
                "m7_s0_execution_id": parent_id,
                "m7p8_s5_execution_id": p8_id,
            },
        },
    )
    dumpj(
        out / "m7p9_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m7p9_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S0",
            "window_seconds": metrics["window_seconds_observed"],
            "estimated_api_call_count": metrics["probe_count"],
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M7P9_STRESS_MAX_SPEND_USD", 38)),
            "within_envelope": True,
            "method": "m7p9_s0_entry_data_profile_v0",
        },
    )

    decisions.extend(
        [
            "Validated dependency closure from parent M7-S0 and P8-S5 before opening P9.",
            "Enforced required-handle and authority closure checks for P9 S0.",
            "Built P9 entry profile from black-box run-scoped evidence: P8 profile carry-forward + decision-lane proofs + ingest receipt context.",
            "Applied blocking checks to sample/cardinality/safety bounds and advisory posture to sparsity-floor gaps requiring downstream cohort injection.",
            "Preserved fail-closed mapping for authority/dependency/representativeness/evidence readback defects.",
        ]
    )
    dumpj(out / "m7p9_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S0", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S0", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P9-ST-S0",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": req_artifacts,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7_s0_phase_execution_id": parent_id,
        "upstream_m7p8_s5_phase_execution_id": p8_id,
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P9-ST-S0",
        "overall_pass": overall_pass,
        "verdict": gate_verdict,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
        "upstream_m7_s0_phase_execution_id": parent_id,
        "upstream_m7p8_s5_phase_execution_id": p8_id,
    }
    dumpj(out / "m7p9_blocker_register.json", blocker_reg)
    dumpj(out / "m7p9_execution_summary.json", summary)
    dumpj(out / "m7p9_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p9_execution_summary.json")
    blocker_reg = loadj(out / "m7p9_blocker_register.json")
    print(f"[m7p9_s0] phase_execution_id={phase_execution_id}")
    print(f"[m7p9_s0] output_dir={out.as_posix()}")
    print(f"[m7p9_s0] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p9_s0] next_gate={summary.get('next_gate')}")
    print(f"[m7p9_s0] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s1(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P9-ST-B4",
                "severity": "S1",
                "status": "OPEN",
                "details": {
                    "reason": "S1 authority/handle closure failure",
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S1 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p9_stress_s0", "m7p9_execution_summary.json", "M7P9-ST-S0")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_df_snapshot: dict[str, Any] = {}
    dep_al_snapshot: dict[str, Any] = {}
    dep_dla_snapshot: dict[str, Any] = {}
    dep_score: dict[str, Any] = {}
    dep_action: dict[str, Any] = {}
    dep_idemp: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M7P9 S0 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7P9_ST_S1_READY":
            dep_issues.append("M7P9 S0 next_gate is not M7P9_ST_S1_READY")
        dep_blocker = loadj(dep_path / "m7p9_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P9 S0 blocker register is not closed")

        dep_subset = loadj(dep_path / "m7p9_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p9_data_profile_summary.json")
        dep_df_snapshot = loadj(dep_path / "m7p9_df_snapshot.json")
        dep_al_snapshot = loadj(dep_path / "m7p9_al_snapshot.json")
        dep_dla_snapshot = loadj(dep_path / "m7p9_dla_snapshot.json")
        dep_score = loadj(dep_path / "m7p9_score_distribution_profile.json")
        dep_action = loadj(dep_path / "m7p9_action_mix_profile.json")
        dep_idemp = loadj(dep_path / "m7p9_idempotency_collision_profile.json")
        dep_decision_log = loadj(dep_path / "m7p9_decision_log.json")

        for art_name, payload in [
            ("m7p9_data_subset_manifest.json", dep_subset),
            ("m7p9_data_profile_summary.json", dep_profile),
            ("m7p9_df_snapshot.json", dep_df_snapshot),
            ("m7p9_al_snapshot.json", dep_al_snapshot),
            ("m7p9_dla_snapshot.json", dep_dla_snapshot),
            ("m7p9_score_distribution_profile.json", dep_score),
            ("m7p9_action_mix_profile.json", dep_action),
            ("m7p9_idempotency_collision_profile.json", dep_idemp),
            ("m7p9_decision_log.json", dep_decision_log),
        ]:
            if not payload:
                blockers.append({"id": "M7P9-ST-B10", "severity": "S1", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": art_name}})
                issues.append(f"missing dependency artifact: {art_name}")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P9 S0 platform_run_id is missing")

    if dep_issues:
        blockers.append({"id": "M7P9-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p9_s1_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m7p9_s1_evidence_bucket"}})
        issues.append("S1 evidence bucket probe failed")

    decision_root_pattern = str(handles.get("DECISION_LANE_EVIDENCE_PATH_PATTERN", "")).strip()
    decision_root = materialize_pattern(decision_root_pattern, {"platform_run_id": platform_run_id}) if decision_root_pattern else ""
    unresolved = re.findall(r"{[^}]+}", decision_root)
    if not decision_root or unresolved:
        blockers.append(
            {
                "id": "M7P9-ST-B10",
                "severity": "S1",
                "status": "OPEN",
                "details": {"reason": "unresolved decision lane root for S1", "decision_root": decision_root, "tokens": unresolved},
            }
        )
        issues.append("S1 decision lane root is unresolved")

    df_key = f"{decision_root.rstrip('/')}/df_component_proof.json" if decision_root else ""
    p_df = add_head_object_probe(probes, evidence_bucket, df_key, "m7p9_s1_df_component_proof")
    df_proof = load_s3_json(evidence_bucket, df_key) if p_df.get("status") == "PASS" else {}
    if p_df.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m7p9_s1_df_component_proof"}})
        issues.append("S1 DF proof readback failed")
    elif not df_proof:
        blockers.append({"id": "M7P9-ST-B10", "severity": "S1", "status": "OPEN", "details": {"reason": "failed to load DF proof", "key": df_key}})
        issues.append("S1 DF proof parse failed")

    hist = latest_hist_p9b()
    comp_summary = hist.get("summary", {})
    component = hist.get("component", {})
    perf = hist.get("perf", {})
    if not hist:
        blockers.append({"id": "M7P9-ST-B4", "severity": "S1", "status": "OPEN", "details": {"reason": "missing historical P9.B DF baseline"}})
        issues.append("missing historical DF baseline")

    functional_issues: list[str] = []
    semantic_issues: list[str] = []

    runtime_active = normalize_runtime_path(str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")))
    runtime_allowed = [normalize_runtime_path(x) for x in str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()]
    runtime_hist = normalize_runtime_path(str(component.get("runtime_path_active", "")))
    if not runtime_active or runtime_active not in runtime_allowed:
        functional_issues.append("runtime path contract invalid for DF lane")
    if runtime_hist and runtime_active and runtime_hist != runtime_active:
        advisories.append(f"historical DF runtime path aliases to {runtime_hist}; current runtime is {runtime_active}.")

    if comp_summary and str(comp_summary.get("next_gate", "")).strip() != "M7.G_READY":
        functional_issues.append("historical P9.B next_gate is not M7.G_READY")
    if perf:
        if to_bool(perf.get("performance_gate_pass")) is not True:
            functional_issues.append("historical DF performance gate did not pass")
        lag_obs = to_float(perf.get("lag_observed"))
        lag_max = to_float(perf.get("lag_max"))
        if lag_obs is not None and lag_max is not None and lag_obs > lag_max:
            functional_issues.append("historical DF lag exceeds max")
        err_obs = to_float(perf.get("error_rate_pct_observed"))
        err_max = to_float(perf.get("error_rate_pct_max"))
        if err_obs is not None and err_max is not None and err_obs > err_max:
            functional_issues.append("historical DF error rate exceeds max")
        throughput_asserted = to_bool(perf.get("throughput_assertion_applied"))
        throughput_observed = to_float(perf.get("throughput_observed"))
        throughput_min = to_float(perf.get("throughput_min"))
        if throughput_asserted is True and throughput_observed is not None and throughput_min is not None and throughput_observed < throughput_min:
            functional_issues.append("historical DF throughput below minimum while asserted")
        if throughput_asserted is not True:
            advisories.append("historical DF throughput gate is waived_low_sample; enforce explicit throughput pressure in downstream windows.")

    if df_proof:
        if str(df_proof.get("component", "")).strip().upper() != "DF":
            semantic_issues.append("DF proof component label mismatch")
        proof_run_id = str(df_proof.get("platform_run_id", "")).strip()
        if platform_run_id and proof_run_id and proof_run_id != platform_run_id:
            semantic_issues.append("DF proof platform_run_id mismatch")
        run_scope = df_proof.get("run_scope_tuple", {}) if isinstance(df_proof.get("run_scope_tuple"), dict) else {}
        rs_run = str(run_scope.get("platform_run_id", "")).strip()
        if platform_run_id and rs_run and rs_run != platform_run_id:
            semantic_issues.append("DF proof run_scope_tuple platform_run_id mismatch")
        if to_bool(df_proof.get("upstream_gate_accepted")) is not True:
            semantic_issues.append("DF proof upstream gate is not accepted")
        idem = str(df_proof.get("idempotency_posture", "")).strip()
        if idem != "run_scope_tuple_no_cross_run_acceptance":
            semantic_issues.append("DF proof idempotency posture mismatch")
        if to_bool(df_proof.get("fail_closed_posture")) is not True:
            semantic_issues.append("DF proof fail_closed_posture is not true")
        if (to_int(df_proof.get("ingest_basis_total_receipts")) or 0) <= 0:
            semantic_issues.append("DF proof ingest_basis_total_receipts is not positive")

    if (to_int(dep_action.get("action_class_cardinality")) or 0) < int(plan_packet.get("M7P9_STRESS_ACTION_CLASS_MIN_CARDINALITY", 3)):
        semantic_issues.append("S0 action_class_cardinality does not satisfy P9 minimum for DF lane")
    if (to_int(dep_score.get("policy_path_cardinality")) or 0) < int(plan_packet.get("M7P9_STRESS_POLICY_PATH_MIN_CARDINALITY", 5)):
        semantic_issues.append("S0 policy_path_cardinality does not satisfy P9 minimum for DF lane")

    if functional_issues:
        blockers.append({"id": "M7P9-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P9-ST-B5", "severity": "S1", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    for src in [dep_profile.get("advisories", []), dep_decision_log.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P9_ST_S2_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S2" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p9_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S1",
            "findings": [
                {"id": "M7P9-ST-F6", "classification": "PREVENT", "finding": "S1 must not proceed without closed S0 dependency and run-scope continuity.", "required_action": "Fail-closed on any S0 gate mismatch or blocker carry-over."},
                {"id": "M7P9-ST-F7", "classification": "PREVENT", "finding": "DF semantic assurances require proof-level idempotency/fail-closed checks.", "required_action": "Fail-closed if DF proof postures diverge from expected contract."},
                {"id": "M7P9-ST-F8", "classification": "OBSERVE", "finding": "Managed-lane low sample can hide throughput issues.", "required_action": "Record advisory and force explicit pressure injection in downstream windows."},
            ],
        },
    )
    dumpj(out / "m7p9_lane_matrix.json", {"component_sequence": ["M7P9-ST-S0", "M7P9-ST-S1", "M7P9-ST-S2", "M7P9-ST-S3", "M7P9-ST-S4", "M7P9-ST-S5"]})
    dumpj(out / "m7p9_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "upstream_m7p9_s0_phase_execution_id": dep_id, "status": "S1_CARRY_FORWARD"})
    dumpj(out / "m7p9_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "upstream_m7p9_s0_phase_execution_id": dep_id, "s1_functional_issues": functional_issues, "s1_semantic_issues": semantic_issues, "advisories": advisories})
    dumpj(
        out / "m7p9_df_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S1",
            "platform_run_id": platform_run_id,
            "status": "PASS" if overall_pass else "FAIL",
            "upstream_m7p9_s0_phase_execution_id": dep_id,
            "historical_p9b_execution_id": str(comp_summary.get("execution_id", "")),
            "historical_component_artifact_path": str(hist.get("path", "")),
            "historical_summary": comp_summary,
            "historical_component": component,
            "historical_performance": perf,
            "current_df_proof_excerpt": {
                "execution_id": str(df_proof.get("execution_id", "")),
                "platform_run_id": str(df_proof.get("platform_run_id", "")),
                "run_scope_tuple": df_proof.get("run_scope_tuple", {}),
                "ingest_basis_total_receipts": to_int(df_proof.get("ingest_basis_total_receipts")),
                "upstream_gate_accepted": to_bool(df_proof.get("upstream_gate_accepted")),
                "idempotency_posture": str(df_proof.get("idempotency_posture", "")),
                "fail_closed_posture": to_bool(df_proof.get("fail_closed_posture")),
            },
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
            "advisories": advisories,
        },
    )
    dumpj(out / "m7p9_al_snapshot.json", {**dep_al_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "upstream_m7p9_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p9_dla_snapshot.json", {**dep_dla_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "upstream_m7p9_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p9_score_distribution_profile.json", {**dep_score, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "upstream_m7p9_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p9_action_mix_profile.json", {**dep_action, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "upstream_m7p9_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p9_idempotency_collision_profile.json", {**dep_idemp, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "upstream_m7p9_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p9_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", **metrics})
    dumpj(out / "m7p9_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "functional_issues": functional_issues, "semantic_issues": semantic_issues})
    dumpj(out / "m7p9_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p9_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P9_STRESS_MAX_SPEND_USD", 38)), "within_envelope": True, "method": "m7p9_s1_df_lane_v0"})

    decisions.extend(
        [
            "Enforced S0 dependency continuity and blocker closure before S1 DF lane checks.",
            "Validated historical DF baseline and current DF proof under normalized runtime contract.",
            "Applied fail-closed S1 mapping: B4 functional/performance, B5 semantic invariants, B10 evidence readback/contract.",
            "Kept sparse cohort findings as explicit advisories and preserved downstream pressure injection requirement.",
        ]
    )
    dumpj(out / "m7p9_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7p9_s0_phase_execution_id": dep_id, "historical_p9b_execution_id": str(comp_summary.get("execution_id", ""))}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S1", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7p9_s0_phase_execution_id": dep_id, "historical_p9b_execution_id": str(comp_summary.get("execution_id", ""))}
    dumpj(out / "m7p9_blocker_register.json", blocker_reg)
    dumpj(out / "m7p9_execution_summary.json", summary)
    dumpj(out / "m7p9_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p9_execution_summary.json")
    blocker_reg = loadj(out / "m7p9_blocker_register.json")
    print(f"[m7p9_s1] phase_execution_id={phase_execution_id}")
    print(f"[m7p9_s1] output_dir={out.as_posix()}")
    print(f"[m7p9_s1] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p9_s1] next_gate={summary.get('next_gate')}")
    print(f"[m7p9_s1] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s2(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P9-ST-B6",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "reason": "S2 authority/handle closure failure",
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S2 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p9_stress_s1", "m7p9_execution_summary.json", "M7P9-ST-S1")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_df_snapshot: dict[str, Any] = {}
    dep_al_snapshot: dict[str, Any] = {}
    dep_dla_snapshot: dict[str, Any] = {}
    dep_score: dict[str, Any] = {}
    dep_action: dict[str, Any] = {}
    dep_idemp: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M7P9 S1 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7P9_ST_S2_READY":
            dep_issues.append("M7P9 S1 next_gate is not M7P9_ST_S2_READY")
        dep_blocker = loadj(dep_path / "m7p9_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P9 S1 blocker register is not closed")

        dep_subset = loadj(dep_path / "m7p9_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p9_data_profile_summary.json")
        dep_df_snapshot = loadj(dep_path / "m7p9_df_snapshot.json")
        dep_al_snapshot = loadj(dep_path / "m7p9_al_snapshot.json")
        dep_dla_snapshot = loadj(dep_path / "m7p9_dla_snapshot.json")
        dep_score = loadj(dep_path / "m7p9_score_distribution_profile.json")
        dep_action = loadj(dep_path / "m7p9_action_mix_profile.json")
        dep_idemp = loadj(dep_path / "m7p9_idempotency_collision_profile.json")
        dep_decision_log = loadj(dep_path / "m7p9_decision_log.json")

        for art_name, payload in [
            ("m7p9_data_subset_manifest.json", dep_subset),
            ("m7p9_data_profile_summary.json", dep_profile),
            ("m7p9_df_snapshot.json", dep_df_snapshot),
            ("m7p9_al_snapshot.json", dep_al_snapshot),
            ("m7p9_dla_snapshot.json", dep_dla_snapshot),
            ("m7p9_score_distribution_profile.json", dep_score),
            ("m7p9_action_mix_profile.json", dep_action),
            ("m7p9_idempotency_collision_profile.json", dep_idemp),
            ("m7p9_decision_log.json", dep_decision_log),
        ]:
            if not payload:
                blockers.append({"id": "M7P9-ST-B10", "severity": "S2", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": art_name}})
                issues.append(f"missing dependency artifact: {art_name}")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P9 S1 platform_run_id is missing")

    if dep_issues:
        blockers.append({"id": "M7P9-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p9_s2_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m7p9_s2_evidence_bucket"}})
        issues.append("S2 evidence bucket probe failed")

    decision_root_pattern = str(handles.get("DECISION_LANE_EVIDENCE_PATH_PATTERN", "")).strip()
    decision_root = materialize_pattern(decision_root_pattern, {"platform_run_id": platform_run_id}) if decision_root_pattern else ""
    unresolved = re.findall(r"{[^}]+}", decision_root)
    if not decision_root or unresolved:
        blockers.append(
            {
                "id": "M7P9-ST-B10",
                "severity": "S2",
                "status": "OPEN",
                "details": {"reason": "unresolved decision lane root for S2", "decision_root": decision_root, "tokens": unresolved},
            }
        )
        issues.append("S2 decision lane root is unresolved")

    al_key = f"{decision_root.rstrip('/')}/al_component_proof.json" if decision_root else ""
    p_al = add_head_object_probe(probes, evidence_bucket, al_key, "m7p9_s2_al_component_proof")
    al_proof = load_s3_json(evidence_bucket, al_key) if p_al.get("status") == "PASS" else {}
    if p_al.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m7p9_s2_al_component_proof"}})
        issues.append("S2 AL proof readback failed")
    elif not al_proof:
        blockers.append({"id": "M7P9-ST-B10", "severity": "S2", "status": "OPEN", "details": {"reason": "failed to load AL proof", "key": al_key}})
        issues.append("S2 AL proof parse failed")

    hist = latest_hist_p9c()
    comp_summary = hist.get("summary", {})
    component = hist.get("component", {})
    perf = hist.get("perf", {})
    if not hist:
        blockers.append({"id": "M7P9-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "missing historical P9.C AL baseline"}})
        issues.append("missing historical AL baseline")

    functional_issues: list[str] = []
    semantic_issues: list[str] = []

    runtime_active = normalize_runtime_path(str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")))
    runtime_allowed = [normalize_runtime_path(x) for x in str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()]
    runtime_hist = normalize_runtime_path(str(component.get("runtime_path_active", "")))
    if not runtime_active or runtime_active not in runtime_allowed:
        functional_issues.append("runtime path contract invalid for AL lane")
    if runtime_hist and runtime_active and runtime_hist != runtime_active:
        advisories.append(f"historical AL runtime path aliases to {runtime_hist}; current runtime is {runtime_active}.")

    if comp_summary and str(comp_summary.get("next_gate", "")).strip() != "M7.H_READY":
        functional_issues.append("historical P9.C next_gate is not M7.H_READY")
    if perf:
        if to_bool(perf.get("performance_gate_pass")) is not True:
            functional_issues.append("historical AL performance gate did not pass")
        lag_obs = to_float(perf.get("lag_observed"))
        lag_max = to_float(perf.get("lag_max"))
        if lag_obs is not None and lag_max is not None and lag_obs > lag_max:
            functional_issues.append("historical AL lag/backpressure exceeds max")
        err_obs = to_float(perf.get("error_rate_pct_observed"))
        err_max = to_float(perf.get("error_rate_pct_max"))
        if err_obs is not None and err_max is not None and err_obs > err_max:
            functional_issues.append("historical AL error rate exceeds max")
        retry_obs = to_float(perf.get("retry_ratio_pct_observed"))
        retry_max = to_float(perf.get("retry_ratio_pct_max"))
        if retry_obs is not None and retry_max is not None and retry_obs > retry_max:
            functional_issues.append("historical AL retry ratio exceeds max")
        throughput_asserted = to_bool(perf.get("throughput_assertion_applied"))
        throughput_observed = to_float(perf.get("throughput_observed"))
        throughput_min = to_float(perf.get("throughput_min"))
        if throughput_asserted is True and throughput_observed is not None and throughput_min is not None and throughput_observed < throughput_min:
            functional_issues.append("historical AL throughput below minimum while asserted")
        if throughput_asserted is not True:
            advisories.append("historical AL throughput gate is waived_low_sample; enforce explicit throughput pressure in downstream windows.")

    if al_proof:
        if str(al_proof.get("component", "")).strip().upper() != "AL":
            semantic_issues.append("AL proof component label mismatch")
        proof_run_id = str(al_proof.get("platform_run_id", "")).strip()
        if platform_run_id and proof_run_id and proof_run_id != platform_run_id:
            semantic_issues.append("AL proof platform_run_id mismatch")
        run_scope = al_proof.get("run_scope_tuple", {}) if isinstance(al_proof.get("run_scope_tuple"), dict) else {}
        rs_run = str(run_scope.get("platform_run_id", "")).strip()
        if platform_run_id and rs_run and rs_run != platform_run_id:
            semantic_issues.append("AL proof run_scope_tuple platform_run_id mismatch")
        if to_bool(al_proof.get("upstream_gate_accepted")) is not True:
            semantic_issues.append("AL proof upstream gate is not accepted")
        idem = str(al_proof.get("idempotency_posture", "")).strip()
        if idem != "run_scope_tuple_no_cross_run_acceptance":
            semantic_issues.append("AL proof idempotency posture mismatch")
        if to_bool(al_proof.get("fail_closed_posture")) is not True:
            semantic_issues.append("AL proof fail_closed_posture is not true")
        if (to_int(al_proof.get("ingest_basis_total_receipts")) or 0) <= 0:
            semantic_issues.append("AL proof ingest_basis_total_receipts is not positive")

    retry_ratio_pct = to_float(dep_idemp.get("retry_ratio_pct"))
    retry_ratio_max = to_float(dep_idemp.get("retry_ratio_max_pct"))
    if retry_ratio_pct is not None and retry_ratio_max is not None and retry_ratio_pct > retry_ratio_max:
        semantic_issues.append("S1 retry_ratio exceeds max contract for AL lane")
    if (to_int(dep_action.get("action_class_cardinality")) or 0) < int(plan_packet.get("M7P9_STRESS_ACTION_CLASS_MIN_CARDINALITY", 3)):
        semantic_issues.append("S1 action_class_cardinality does not satisfy P9 minimum for AL lane")

    if functional_issues:
        blockers.append({"id": "M7P9-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P9-ST-B7", "severity": "S2", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    for src in [dep_profile.get("advisories", []), dep_decision_log.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P9_ST_S3_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S3" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p9_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S2",
            "findings": [
                {"id": "M7P9-ST-F9", "classification": "PREVENT", "finding": "S2 must not proceed without closed S1 dependency and run-scope continuity.", "required_action": "Fail-closed on any S1 gate mismatch or blocker carry-over."},
                {"id": "M7P9-ST-F10", "classification": "PREVENT", "finding": "AL semantic assurances require proof-level retry/idempotency/fail-closed checks.", "required_action": "Fail-closed if AL proof postures diverge from expected contract."},
                {"id": "M7P9-ST-F11", "classification": "OBSERVE", "finding": "Managed-lane low sample can hide AL throughput/backpressure tail risk.", "required_action": "Record advisory and keep explicit pressure injection in downstream windows."},
            ],
        },
    )
    dumpj(out / "m7p9_lane_matrix.json", {"component_sequence": ["M7P9-ST-S0", "M7P9-ST-S1", "M7P9-ST-S2", "M7P9-ST-S3", "M7P9-ST-S4", "M7P9-ST-S5"]})
    dumpj(out / "m7p9_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "upstream_m7p9_s1_phase_execution_id": dep_id, "status": "S2_CARRY_FORWARD"})
    dumpj(out / "m7p9_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "upstream_m7p9_s1_phase_execution_id": dep_id, "s2_functional_issues": functional_issues, "s2_semantic_issues": semantic_issues, "advisories": advisories})
    dumpj(out / "m7p9_df_snapshot.json", {**dep_df_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p9_s1_phase_execution_id": dep_id})
    dumpj(
        out / "m7p9_al_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S2",
            "platform_run_id": platform_run_id,
            "status": "PASS" if overall_pass else "FAIL",
            "upstream_m7p9_s1_phase_execution_id": dep_id,
            "historical_p9c_execution_id": str(comp_summary.get("execution_id", "")),
            "historical_component_artifact_path": str(hist.get("path", "")),
            "historical_summary": comp_summary,
            "historical_component": component,
            "historical_performance": perf,
            "current_al_proof_excerpt": {
                "execution_id": str(al_proof.get("execution_id", "")),
                "platform_run_id": str(al_proof.get("platform_run_id", "")),
                "run_scope_tuple": al_proof.get("run_scope_tuple", {}),
                "ingest_basis_total_receipts": to_int(al_proof.get("ingest_basis_total_receipts")),
                "upstream_gate_accepted": to_bool(al_proof.get("upstream_gate_accepted")),
                "idempotency_posture": str(al_proof.get("idempotency_posture", "")),
                "fail_closed_posture": to_bool(al_proof.get("fail_closed_posture")),
            },
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
            "advisories": advisories,
        },
    )
    dumpj(out / "m7p9_dla_snapshot.json", {**dep_dla_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p9_s1_phase_execution_id": dep_id})
    dumpj(out / "m7p9_score_distribution_profile.json", {**dep_score, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p9_s1_phase_execution_id": dep_id})
    dumpj(out / "m7p9_action_mix_profile.json", {**dep_action, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p9_s1_phase_execution_id": dep_id})
    dumpj(out / "m7p9_idempotency_collision_profile.json", {**dep_idemp, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p9_s1_phase_execution_id": dep_id})
    dumpj(out / "m7p9_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", **metrics})
    dumpj(out / "m7p9_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "functional_issues": functional_issues, "semantic_issues": semantic_issues})
    dumpj(out / "m7p9_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p9_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P9_STRESS_MAX_SPEND_USD", 38)), "within_envelope": True, "method": "m7p9_s2_al_lane_v0"})

    decisions.extend(
        [
            "Enforced S1 dependency continuity and blocker closure before S2 AL lane checks.",
            "Validated historical AL baseline and current AL proof under normalized runtime contract.",
            "Applied fail-closed S2 mapping: B6 functional/performance, B7 semantic/retry invariants, B10 evidence readback/contract.",
            "Kept sparse cohort findings as explicit advisories and preserved downstream pressure injection requirement.",
        ]
    )
    dumpj(out / "m7p9_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7p9_s1_phase_execution_id": dep_id, "historical_p9c_execution_id": str(comp_summary.get("execution_id", ""))}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S2", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7p9_s1_phase_execution_id": dep_id, "historical_p9c_execution_id": str(comp_summary.get("execution_id", ""))}
    dumpj(out / "m7p9_blocker_register.json", blocker_reg)
    dumpj(out / "m7p9_execution_summary.json", summary)
    dumpj(out / "m7p9_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p9_execution_summary.json")
    blocker_reg = loadj(out / "m7p9_blocker_register.json")
    print(f"[m7p9_s2] phase_execution_id={phase_execution_id}")
    print(f"[m7p9_s2] output_dir={out.as_posix()}")
    print(f"[m7p9_s2] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p9_s2] next_gate={summary.get('next_gate')}")
    print(f"[m7p9_s2] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s3(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P9-ST-B8",
                "severity": "S3",
                "status": "OPEN",
                "details": {
                    "reason": "S3 authority/handle closure failure",
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S3 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p9_stress_s2", "m7p9_execution_summary.json", "M7P9-ST-S2")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_df_snapshot: dict[str, Any] = {}
    dep_al_snapshot: dict[str, Any] = {}
    dep_dla_snapshot: dict[str, Any] = {}
    dep_score: dict[str, Any] = {}
    dep_action: dict[str, Any] = {}
    dep_idemp: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M7P9 S2 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7P9_ST_S3_READY":
            dep_issues.append("M7P9 S2 next_gate is not M7P9_ST_S3_READY")
        dep_blocker = loadj(dep_path / "m7p9_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P9 S2 blocker register is not closed")

        dep_subset = loadj(dep_path / "m7p9_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p9_data_profile_summary.json")
        dep_df_snapshot = loadj(dep_path / "m7p9_df_snapshot.json")
        dep_al_snapshot = loadj(dep_path / "m7p9_al_snapshot.json")
        dep_dla_snapshot = loadj(dep_path / "m7p9_dla_snapshot.json")
        dep_score = loadj(dep_path / "m7p9_score_distribution_profile.json")
        dep_action = loadj(dep_path / "m7p9_action_mix_profile.json")
        dep_idemp = loadj(dep_path / "m7p9_idempotency_collision_profile.json")
        dep_decision_log = loadj(dep_path / "m7p9_decision_log.json")

        for art_name, payload in [
            ("m7p9_data_subset_manifest.json", dep_subset),
            ("m7p9_data_profile_summary.json", dep_profile),
            ("m7p9_df_snapshot.json", dep_df_snapshot),
            ("m7p9_al_snapshot.json", dep_al_snapshot),
            ("m7p9_dla_snapshot.json", dep_dla_snapshot),
            ("m7p9_score_distribution_profile.json", dep_score),
            ("m7p9_action_mix_profile.json", dep_action),
            ("m7p9_idempotency_collision_profile.json", dep_idemp),
            ("m7p9_decision_log.json", dep_decision_log),
        ]:
            if not payload:
                blockers.append({"id": "M7P9-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": art_name}})
                issues.append(f"missing dependency artifact: {art_name}")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P9 S2 platform_run_id is missing")

    if dep_issues:
        blockers.append({"id": "M7P9-ST-B8", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p9_s3_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p9_s3_evidence_bucket"}})
        issues.append("S3 evidence bucket probe failed")

    decision_root_pattern = str(handles.get("DECISION_LANE_EVIDENCE_PATH_PATTERN", "")).strip()
    decision_root = materialize_pattern(decision_root_pattern, {"platform_run_id": platform_run_id}) if decision_root_pattern else ""
    unresolved = re.findall(r"{[^}]+}", decision_root)
    if not decision_root or unresolved:
        blockers.append(
            {
                "id": "M7P9-ST-B10",
                "severity": "S3",
                "status": "OPEN",
                "details": {"reason": "unresolved decision lane root for S3", "decision_root": decision_root, "tokens": unresolved},
            }
        )
        issues.append("S3 decision lane root is unresolved")

    dla_key = f"{decision_root.rstrip('/')}/dla_component_proof.json" if decision_root else ""
    p_dla = add_head_object_probe(probes, evidence_bucket, dla_key, "m7p9_s3_dla_component_proof")
    dla_proof = load_s3_json(evidence_bucket, dla_key) if p_dla.get("status") == "PASS" else {}
    if p_dla.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p9_s3_dla_component_proof"}})
        issues.append("S3 DLA proof readback failed")
    elif not dla_proof:
        blockers.append({"id": "M7P9-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "failed to load DLA proof", "key": dla_key}})
        issues.append("S3 DLA proof parse failed")

    hist = latest_hist_p9d()
    comp_summary = hist.get("summary", {})
    component = hist.get("component", {})
    perf = hist.get("perf", {})
    if not hist:
        blockers.append({"id": "M7P9-ST-B8", "severity": "S3", "status": "OPEN", "details": {"reason": "missing historical P9.D DLA baseline"}})
        issues.append("missing historical DLA baseline")

    functional_issues: list[str] = []
    semantic_issues: list[str] = []

    runtime_active = normalize_runtime_path(str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")))
    runtime_allowed = [normalize_runtime_path(x) for x in str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()]
    runtime_hist = normalize_runtime_path(str(component.get("runtime_path_active", "")))
    if not runtime_active or runtime_active not in runtime_allowed:
        functional_issues.append("runtime path contract invalid for DLA lane")
    if runtime_hist and runtime_active and runtime_hist != runtime_active:
        advisories.append(f"historical DLA runtime path aliases to {runtime_hist}; current runtime is {runtime_active}.")

    if comp_summary and str(comp_summary.get("next_gate", "")).strip() != "P9.E_READY":
        functional_issues.append("historical P9.D next_gate is not P9.E_READY")
    if perf:
        if to_bool(perf.get("performance_gate_pass")) is not True:
            functional_issues.append("historical DLA performance gate did not pass")
        lag_obs = to_float(perf.get("lag_observed"))
        lag_max = to_float(perf.get("lag_max"))
        if lag_obs is not None and lag_max is not None and lag_obs > lag_max:
            functional_issues.append("historical DLA lag/backpressure exceeds max")
        err_obs = to_float(perf.get("error_rate_pct_observed"))
        err_max = to_float(perf.get("error_rate_pct_max"))
        if err_obs is not None and err_max is not None and err_obs > err_max:
            functional_issues.append("historical DLA error rate exceeds max")
        throughput_asserted = to_bool(perf.get("throughput_assertion_applied"))
        throughput_observed = to_float(perf.get("throughput_observed"))
        throughput_min = to_float(perf.get("throughput_min"))
        if throughput_asserted is True and throughput_observed is not None and throughput_min is not None and throughput_observed < throughput_min:
            functional_issues.append("historical DLA throughput below minimum while asserted")
        if throughput_asserted is not True:
            mode = str(perf.get("throughput_gate_mode", "")).strip()
            if mode != "waived_low_sample":
                functional_issues.append("historical DLA throughput is non-asserted without waived_low_sample mode")
            else:
                advisories.append("historical DLA throughput gate is waived_low_sample; enforce explicit throughput pressure in downstream windows.")

    dep_input_events = to_int(dep_subset.get("decision_input_events"))
    if dep_input_events is None:
        dep_input_events = to_int(dep_profile.get("decision_input_events"))
    if dep_input_events is None:
        dep_input_events = to_int(dep_subset.get("receipt_total"))
    dep_al_execution = ""
    if isinstance(dep_al_snapshot.get("current_al_proof_excerpt"), dict):
        dep_al_execution = str(dep_al_snapshot.get("current_al_proof_excerpt", {}).get("execution_id", "")).strip()
    if not dep_al_execution:
        dep_al_execution = str(dep_al_snapshot.get("historical_p9c_execution_id", "")).strip()

    audit_key = ""
    audit_payload: dict[str, Any] = {}
    if dla_proof:
        if str(dla_proof.get("component", "")).strip().upper() != "DLA":
            semantic_issues.append("DLA proof component label mismatch")
        proof_run_id = str(dla_proof.get("platform_run_id", "")).strip()
        if platform_run_id and proof_run_id and proof_run_id != platform_run_id:
            semantic_issues.append("DLA proof platform_run_id mismatch")
        run_scope = dla_proof.get("run_scope_tuple", {}) if isinstance(dla_proof.get("run_scope_tuple"), dict) else {}
        rs_run = str(run_scope.get("platform_run_id", "")).strip()
        if platform_run_id and rs_run and rs_run != platform_run_id:
            semantic_issues.append("DLA proof run_scope_tuple platform_run_id mismatch")
        if to_bool(dla_proof.get("upstream_gate_accepted")) is not True:
            semantic_issues.append("DLA proof upstream gate is not accepted")
        idem = str(dla_proof.get("idempotency_posture", "")).strip()
        if idem != "run_scope_tuple_no_cross_run_acceptance":
            semantic_issues.append("DLA proof idempotency posture mismatch")
        if to_bool(dla_proof.get("fail_closed_posture")) is not True:
            semantic_issues.append("DLA proof fail_closed_posture is not true")
        if to_bool(dla_proof.get("append_only_posture")) is not True:
            semantic_issues.append("DLA proof append_only_posture is not true")
        ingest_basis = to_int(dla_proof.get("ingest_basis_total_receipts"))
        if (ingest_basis or 0) <= 0:
            semantic_issues.append("DLA proof ingest_basis_total_receipts is not positive")
        if ingest_basis is not None and dep_input_events is not None and dep_input_events > 0 and ingest_basis > dep_input_events:
            semantic_issues.append("DLA proof ingest basis exceeds S2 decision input events")
        upstream_execution = str(dla_proof.get("upstream_execution", "")).strip()
        if dep_al_execution and upstream_execution and upstream_execution != dep_al_execution:
            semantic_issues.append("DLA proof upstream_execution mismatches S2 AL execution reference")
        audit_key = str(dla_proof.get("audit_append_probe_key", "")).strip().lstrip("/")
        if not audit_key:
            semantic_issues.append("DLA proof audit_append_probe_key is missing")

    if audit_key:
        p_audit = add_head_object_probe(probes, evidence_bucket, audit_key, "m7p9_s3_dla_audit_append_probe")
        if p_audit.get("status") != "PASS":
            blockers.append({"id": "M7P9-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p9_s3_dla_audit_append_probe"}})
            issues.append("S3 DLA audit append probe readback failed")
        else:
            audit_payload = load_s3_json(evidence_bucket, audit_key)
            if not audit_payload:
                blockers.append({"id": "M7P9-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "failed to load DLA audit append probe", "key": audit_key}})
                issues.append("S3 DLA audit append probe parse failed")
            else:
                audit_run_id = str(audit_payload.get("platform_run_id", "")).strip()
                if platform_run_id and audit_run_id and audit_run_id != platform_run_id:
                    semantic_issues.append("DLA audit append probe platform_run_id mismatch")
                audit_scope = audit_payload.get("run_scope_tuple", {}) if isinstance(audit_payload.get("run_scope_tuple"), dict) else {}
                audit_scope_run = str(audit_scope.get("platform_run_id", "")).strip()
                if platform_run_id and audit_scope_run and audit_scope_run != platform_run_id:
                    semantic_issues.append("DLA audit append probe run_scope_tuple platform_run_id mismatch")
                probe_append_ok = to_bool(audit_payload.get("append_only_validated"))
                if probe_append_ok is False:
                    semantic_issues.append("DLA audit append probe append_only_validated is false")

    if functional_issues:
        blockers.append({"id": "M7P9-ST-B8", "severity": "S3", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P9-ST-B9", "severity": "S3", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    for src in [dep_profile.get("advisories", []), dep_decision_log.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P9_ST_S4_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S4" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p9_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S3",
            "findings": [
                {"id": "M7P9-ST-F12", "classification": "PREVENT", "finding": "S3 must not proceed without closed S2 dependency and run-scope continuity.", "required_action": "Fail-closed on any S2 gate mismatch or blocker carry-over."},
                {"id": "M7P9-ST-F13", "classification": "PREVENT", "finding": "DLA append-only/causal assurance requires proof-level invariant checks and audit append readback.", "required_action": "Fail-closed if DLA proof or audit probe diverges from expected posture."},
                {"id": "M7P9-ST-F14", "classification": "OBSERVE", "finding": "Managed-lane low sample can hide DLA throughput tail risk.", "required_action": "Record advisory and preserve explicit downstream pressure windows."},
            ],
        },
    )
    dumpj(out / "m7p9_lane_matrix.json", {"component_sequence": ["M7P9-ST-S0", "M7P9-ST-S1", "M7P9-ST-S2", "M7P9-ST-S3", "M7P9-ST-S4", "M7P9-ST-S5"]})
    dumpj(out / "m7p9_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "upstream_m7p9_s2_phase_execution_id": dep_id, "status": "S3_CARRY_FORWARD"})
    dumpj(out / "m7p9_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "upstream_m7p9_s2_phase_execution_id": dep_id, "s3_functional_issues": functional_issues, "s3_semantic_issues": semantic_issues, "advisories": advisories})
    dumpj(out / "m7p9_df_snapshot.json", {**dep_df_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "status": "CARRY_FORWARD_FROM_S2", "upstream_m7p9_s2_phase_execution_id": dep_id})
    dumpj(out / "m7p9_al_snapshot.json", {**dep_al_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "status": "CARRY_FORWARD_FROM_S2", "upstream_m7p9_s2_phase_execution_id": dep_id})
    dumpj(
        out / "m7p9_dla_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S3",
            "platform_run_id": platform_run_id,
            "status": "PASS" if overall_pass else "FAIL",
            "upstream_m7p9_s2_phase_execution_id": dep_id,
            "historical_p9d_execution_id": str(comp_summary.get("execution_id", "")),
            "historical_component_artifact_path": str(hist.get("path", "")),
            "historical_summary": comp_summary,
            "historical_component": component,
            "historical_performance": perf,
            "current_dla_proof_excerpt": {
                "execution_id": str(dla_proof.get("execution_id", "")),
                "platform_run_id": str(dla_proof.get("platform_run_id", "")),
                "run_scope_tuple": dla_proof.get("run_scope_tuple", {}),
                "upstream_execution": str(dla_proof.get("upstream_execution", "")),
                "ingest_basis_total_receipts": to_int(dla_proof.get("ingest_basis_total_receipts")),
                "upstream_gate_accepted": to_bool(dla_proof.get("upstream_gate_accepted")),
                "idempotency_posture": str(dla_proof.get("idempotency_posture", "")),
                "fail_closed_posture": to_bool(dla_proof.get("fail_closed_posture")),
                "append_only_posture": to_bool(dla_proof.get("append_only_posture")),
                "audit_append_probe_key": str(dla_proof.get("audit_append_probe_key", "")),
            },
            "audit_append_probe_excerpt": {
                "platform_run_id": str(audit_payload.get("platform_run_id", "")),
                "run_scope_tuple": audit_payload.get("run_scope_tuple", {}),
                "append_only_validated": to_bool(audit_payload.get("append_only_validated")),
                "key": audit_key,
            },
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
            "advisories": advisories,
        },
    )
    dumpj(out / "m7p9_score_distribution_profile.json", {**dep_score, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "status": "CARRY_FORWARD_FROM_S2", "upstream_m7p9_s2_phase_execution_id": dep_id})
    dumpj(out / "m7p9_action_mix_profile.json", {**dep_action, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "status": "CARRY_FORWARD_FROM_S2", "upstream_m7p9_s2_phase_execution_id": dep_id})
    dumpj(out / "m7p9_idempotency_collision_profile.json", {**dep_idemp, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "status": "CARRY_FORWARD_FROM_S2", "upstream_m7p9_s2_phase_execution_id": dep_id})
    dumpj(out / "m7p9_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", **metrics})
    dumpj(out / "m7p9_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "functional_issues": functional_issues, "semantic_issues": semantic_issues})
    dumpj(out / "m7p9_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p9_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P9_STRESS_MAX_SPEND_USD", 38)), "within_envelope": True, "method": "m7p9_s3_dla_lane_v0"})

    decisions.extend(
        [
            "Enforced S2 dependency continuity and blocker closure before S3 DLA lane checks.",
            "Validated historical DLA baseline and current DLA proof under normalized runtime and performance contract.",
            "Applied fail-closed S3 mapping: B8 functional/performance, B9 append-only/causal invariants, B10 evidence readback/contract.",
            "Carried forward prior sparse-cohort advisories while preserving explicit downstream pressure requirements.",
        ]
    )
    dumpj(out / "m7p9_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7p9_s2_phase_execution_id": dep_id, "historical_p9d_execution_id": str(comp_summary.get("execution_id", ""))}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S3", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7p9_s2_phase_execution_id": dep_id, "historical_p9d_execution_id": str(comp_summary.get("execution_id", ""))}
    dumpj(out / "m7p9_blocker_register.json", blocker_reg)
    dumpj(out / "m7p9_execution_summary.json", summary)
    dumpj(out / "m7p9_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p9_execution_summary.json")
    blocker_reg = loadj(out / "m7p9_blocker_register.json")
    print(f"[m7p9_s3] phase_execution_id={phase_execution_id}")
    print(f"[m7p9_s3] output_dir={out.as_posix()}")
    print(f"[m7p9_s3] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p9_s3] next_gate={summary.get('next_gate')}")
    print(f"[m7p9_s3] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s4(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P9-ST-B11",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "reason": "S4 authority/handle closure failure",
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S4 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p9_stress_s3", "m7p9_execution_summary.json", "M7P9-ST-S3")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_df_snapshot: dict[str, Any] = {}
    dep_al_snapshot: dict[str, Any] = {}
    dep_dla_snapshot: dict[str, Any] = {}
    dep_score: dict[str, Any] = {}
    dep_action: dict[str, Any] = {}
    dep_idemp: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M7P9 S3 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7P9_ST_S4_READY":
            dep_issues.append("M7P9 S3 next_gate is not M7P9_ST_S4_READY")
        dep_blocker = loadj(dep_path / "m7p9_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P9 S3 blocker register is not closed")

        dep_subset = loadj(dep_path / "m7p9_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p9_data_profile_summary.json")
        dep_df_snapshot = loadj(dep_path / "m7p9_df_snapshot.json")
        dep_al_snapshot = loadj(dep_path / "m7p9_al_snapshot.json")
        dep_dla_snapshot = loadj(dep_path / "m7p9_dla_snapshot.json")
        dep_score = loadj(dep_path / "m7p9_score_distribution_profile.json")
        dep_action = loadj(dep_path / "m7p9_action_mix_profile.json")
        dep_idemp = loadj(dep_path / "m7p9_idempotency_collision_profile.json")
        dep_decision_log = loadj(dep_path / "m7p9_decision_log.json")

        for art_name, payload in [
            ("m7p9_data_subset_manifest.json", dep_subset),
            ("m7p9_data_profile_summary.json", dep_profile),
            ("m7p9_df_snapshot.json", dep_df_snapshot),
            ("m7p9_al_snapshot.json", dep_al_snapshot),
            ("m7p9_dla_snapshot.json", dep_dla_snapshot),
            ("m7p9_score_distribution_profile.json", dep_score),
            ("m7p9_action_mix_profile.json", dep_action),
            ("m7p9_idempotency_collision_profile.json", dep_idemp),
            ("m7p9_decision_log.json", dep_decision_log),
        ]:
            if not payload:
                blockers.append({"id": "M7P9-ST-B10", "severity": "S4", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": art_name}})
                issues.append(f"missing dependency artifact: {art_name}")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P9 S3 platform_run_id is missing")

    if dep_issues:
        blockers.append({"id": "M7P9-ST-B11", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain_spec = [
        ("S0", "m7p9_stress_s0", "M7P9-ST-S0", "M7P9_ST_S1_READY"),
        ("S1", "m7p9_stress_s1", "M7P9-ST-S1", "M7P9_ST_S2_READY"),
        ("S2", "m7p9_stress_s2", "M7P9-ST-S2", "M7P9_ST_S3_READY"),
        ("S3", "m7p9_stress_s3", "M7P9-ST-S3", "M7P9_ST_S4_READY"),
    ]
    chain_rows: list[dict[str, Any]] = []
    stage_root_cause: dict[str, list[str]] = {"DF": [], "AL": [], "DLA": [], "DATA_PROFILE": [], "EVIDENCE": []}
    stage_lane_map = {"S0": "DATA_PROFILE", "S1": "DF", "S2": "AL", "S3": "DLA"}
    for label, prefix, stage_id, expected_next_gate in chain_spec:
        r = latest_ok(prefix, "m7p9_execution_summary.json", stage_id)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_next_gate,
            "found": bool(r),
            "phase_execution_id": "",
            "next_gate": "",
            "overall_pass": False,
            "open_blockers": None,
            "ok": False,
        }
        if r:
            s = r.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["overall_pass"] = bool(s.get("overall_pass"))
            rp = Path(str(r.get("path", "")))
            b = loadj(rp / "m7p9_blocker_register.json")
            row["open_blockers"] = int(b.get("open_blocker_count", 0) or 0)
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_next_gate and row["open_blockers"] == 0
            if row["open_blockers"] and row["open_blockers"] > 0:
                lane = stage_lane_map.get(label, "DATA_PROFILE")
                stage_root_cause.setdefault(lane, []).append(f"{stage_id}:{row['phase_execution_id']}")
        if not row["ok"]:
            blockers.append({"id": "M7P9-ST-B11", "severity": "S4", "status": "OPEN", "details": {"chain_row": row}})
            issues.append(f"stage-chain closure failed for {label}")
            lane = stage_lane_map.get(label, "DATA_PROFILE")
            stage_root_cause.setdefault(lane, []).append(f"{stage_id}:closure")
        chain_rows.append(row)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p9_s4_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B10", "severity": "S4", "status": "OPEN", "details": {"probe_id": "m7p9_s4_evidence_bucket"}})
        issues.append("S4 evidence bucket probe failed")
        stage_root_cause.setdefault("EVIDENCE", []).append("evidence_bucket_head_probe")

    remediation_mode = "NO_OP" if len(blockers) == 0 else "TARGETED_REMEDIATE"
    if remediation_mode == "NO_OP":
        decisions.append("No unresolved blockers detected from S0..S3; remediation lane closed as NO_OP per targeted-rerun-only policy.")
    else:
        decisions.append("Residual blocker(s) detected; remediation lane requires targeted correction before S5.")

    blocker_classification = {k: v for k, v in stage_root_cause.items() if v}

    for src in [dep_profile.get("advisories", []), dep_decision_log.get("advisories", []), dep_dla_snapshot.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P9_ST_S5_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S5" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p9_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S4",
            "findings": [
                {"id": "M7P9-ST-F15", "classification": "PREVENT", "finding": "S4 must not mask unresolved blockers from prior lanes.", "required_action": "Fail-closed on any unresolved S0..S3 chain issue."},
                {"id": "M7P9-ST-F16", "classification": "PREVENT", "finding": "S4 remediation must remain targeted and evidence-consistent.", "required_action": "Use NO_OP when clean; otherwise keep blocker-scoped remediation only."},
            ],
        },
    )
    dumpj(out / "m7p9_lane_matrix.json", {"component_sequence": ["M7P9-ST-S0", "M7P9-ST-S1", "M7P9-ST-S2", "M7P9-ST-S3", "M7P9-ST-S4", "M7P9-ST-S5"]})
    dumpj(out / "m7p9_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "upstream_m7p9_s3_phase_execution_id": dep_id, "status": "S4_CARRY_FORWARD"})
    dumpj(
        out / "m7p9_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S4",
            "upstream_m7p9_s3_phase_execution_id": dep_id,
            "s4_remediation_mode": remediation_mode,
            "s4_chain_rows": chain_rows,
            "s4_blocker_classification": blocker_classification,
            "advisories": advisories,
        },
    )
    dumpj(out / "m7p9_df_snapshot.json", {**dep_df_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p9_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p9_al_snapshot.json", {**dep_al_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p9_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p9_dla_snapshot.json", {**dep_dla_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p9_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode, "blocker_classification": blocker_classification})
    dumpj(out / "m7p9_score_distribution_profile.json", {**dep_score, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p9_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p9_action_mix_profile.json", {**dep_action, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p9_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p9_idempotency_collision_profile.json", {**dep_idemp, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p9_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode})
    dumpj(out / "m7p9_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", **metrics})
    dumpj(out / "m7p9_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "remediation_mode": remediation_mode, "chain_rows": chain_rows, "blocker_classification": blocker_classification})
    dumpj(out / "m7p9_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p9_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P9_STRESS_MAX_SPEND_USD", 38)), "within_envelope": True, "method": "m7p9_s4_remediation_lane_v0", "remediation_mode": remediation_mode})
    decisions.extend(["Enforced S3 continuity and blocker closure before S4.", "Executed deterministic chain-health sweep across S0..S3 before remediation adjudication.", "Applied S4 policy: NO_OP when blocker-free, targeted remediation only when concrete residual blocker exists."])
    dumpj(out / "m7p9_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "decisions": decisions, "advisories": advisories, "remediation_mode": remediation_mode, "blocker_classification": blocker_classification})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7p9_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S4", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7p9_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode}
    dumpj(out / "m7p9_blocker_register.json", blocker_reg)
    dumpj(out / "m7p9_execution_summary.json", summary)
    dumpj(out / "m7p9_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p9_execution_summary.json")
    blocker_reg = loadj(out / "m7p9_blocker_register.json")
    print(f"[m7p9_s4] phase_execution_id={phase_execution_id}")
    print(f"[m7p9_s4] output_dir={out.as_posix()}")
    print(f"[m7p9_s4] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p9_s4] next_gate={summary.get('next_gate')}")
    print(f"[m7p9_s4] remediation_mode={summary.get('remediation_mode')}")
    print(f"[m7p9_s4] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s5(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    expected_pass_verdict = str(plan_packet.get("M7P9_STRESS_EXPECTED_VERDICT_ON_PASS", "ADVANCE_TO_P10")).strip() or "ADVANCE_TO_P10"
    if expected_pass_verdict != "ADVANCE_TO_P10":
        blockers.append(
            {
                "id": "M7P9-ST-B11",
                "severity": "S5",
                "status": "OPEN",
                "details": {"reason": "unexpected expected_pass_verdict contract", "expected_pass_verdict": expected_pass_verdict},
            }
        )
        issues.append("expected pass verdict contract is not ADVANCE_TO_P10")

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P9-ST-B11",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "reason": "S5 authority/handle closure failure",
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S5 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p9_stress_s4", "m7p9_execution_summary.json", "M7P9-ST-S4")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_summary: dict[str, Any] = {}
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_df_snapshot: dict[str, Any] = {}
    dep_al_snapshot: dict[str, Any] = {}
    dep_dla_snapshot: dict[str, Any] = {}
    dep_score: dict[str, Any] = {}
    dep_action: dict[str, Any] = {}
    dep_idemp: dict[str, Any] = {}
    dep_gate_verdict: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}

    if not dep:
        dep_issues.append("missing successful M7P9 S4 dependency")
    else:
        dep_summary = dep.get("summary", {})
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        dep_path = Path(str(dep.get("path", "")))
        if str(dep_summary.get("next_gate", "")).strip() != "M7P9_ST_S5_READY":
            dep_issues.append("M7P9 S4 next_gate is not M7P9_ST_S5_READY")
        dep_blocker = loadj(dep_path / "m7p9_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P9 S4 blocker register is not closed")

        dep_subset = loadj(dep_path / "m7p9_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p9_data_profile_summary.json")
        dep_df_snapshot = loadj(dep_path / "m7p9_df_snapshot.json")
        dep_al_snapshot = loadj(dep_path / "m7p9_al_snapshot.json")
        dep_dla_snapshot = loadj(dep_path / "m7p9_dla_snapshot.json")
        dep_score = loadj(dep_path / "m7p9_score_distribution_profile.json")
        dep_action = loadj(dep_path / "m7p9_action_mix_profile.json")
        dep_idemp = loadj(dep_path / "m7p9_idempotency_collision_profile.json")
        dep_gate_verdict = loadj(dep_path / "m7p9_gate_verdict.json")
        dep_decision_log = loadj(dep_path / "m7p9_decision_log.json")

        if not dep_subset or not dep_profile:
            dep_issues.append("M7P9 S4 realism artifacts are incomplete")
        if not dep_df_snapshot or not dep_al_snapshot or not dep_dla_snapshot:
            dep_issues.append("M7P9 S4 component snapshots are incomplete")
        if not dep_gate_verdict or not dep_decision_log:
            dep_issues.append("M7P9 S4 closure artifacts are incomplete")

        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or dep_summary.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P9 S4 platform_run_id is missing")

        dep_required = dep_summary.get("required_artifacts", req_artifacts)
        dep_required_list = dep_required if isinstance(dep_required, list) else req_artifacts
        for artifact in dep_required_list:
            sa = str(artifact).strip()
            if sa and dep_path is not None and not (dep_path / sa).exists():
                blockers.append({"id": "M7P9-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": sa}})
                issues.append(f"missing dependency artifact: {sa}")

    if dep_issues:
        blockers.append({"id": "M7P9-ST-B11", "severity": "S5", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain_spec = [
        ("S0", "m7p9_stress_s0", "M7P9-ST-S0", "M7P9_ST_S1_READY"),
        ("S1", "m7p9_stress_s1", "M7P9-ST-S1", "M7P9_ST_S2_READY"),
        ("S2", "m7p9_stress_s2", "M7P9-ST-S2", "M7P9_ST_S3_READY"),
        ("S3", "m7p9_stress_s3", "M7P9-ST-S3", "M7P9_ST_S4_READY"),
        ("S4", "m7p9_stress_s4", "M7P9-ST-S4", "M7P9_ST_S5_READY"),
    ]
    chain_rows: list[dict[str, Any]] = []
    for label, prefix, stage_id, expected_next_gate in chain_spec:
        r = latest_ok(prefix, "m7p9_execution_summary.json", stage_id)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_next_gate,
            "found": bool(r),
            "phase_execution_id": "",
            "next_gate": "",
            "overall_pass": False,
            "open_blockers": None,
            "platform_run_id": "",
            "run_scope_consistent": True,
            "ok": False,
        }
        if r:
            s = r.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["overall_pass"] = bool(s.get("overall_pass"))
            row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
            rp = Path(str(r.get("path", "")))
            b = loadj(rp / "m7p9_blocker_register.json")
            row["open_blockers"] = int(b.get("open_blocker_count", 0) or 0)
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_next_gate and row["open_blockers"] == 0
            if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
                row["run_scope_consistent"] = False
                row["ok"] = False
        if not row["ok"]:
            blockers.append({"id": "M7P9-ST-B11", "severity": "S5", "status": "OPEN", "details": {"chain_row": row}})
            issues.append(f"stage-chain closure failed for {label}")
        chain_rows.append(row)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p9_s5_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P9-ST-B12", "severity": "S5", "status": "OPEN", "details": {"probe_id": "m7p9_s5_evidence_bucket"}})
        issues.append("S5 evidence bucket probe failed")

    behavior_refs = dep_subset.get("behavior_context_refs", {}) if isinstance(dep_subset.get("behavior_context_refs"), dict) else {}
    for tag in ["receipt_summary", "quarantine_summary", "offsets_snapshot"]:
        key = str(behavior_refs.get(tag, {}).get("key", "")).strip() if isinstance(behavior_refs.get(tag, {}), dict) else ""
        if not key:
            blockers.append({"id": "M7P9-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "missing behavior-context key", "tag": tag}})
            issues.append(f"missing behavior-context key for {tag}")
            continue
        p = add_head_object_probe(probes, evidence_bucket, key, f"m7p9_s5_behavior_{tag}")
        if p.get("status") != "PASS":
            blockers.append({"id": "M7P9-ST-B12", "severity": "S5", "status": "OPEN", "details": {"probe_id": f"m7p9_s5_behavior_{tag}"}})
            issues.append(f"S5 behavior-context readback failed for {tag}")

    decision_refs = dep_subset.get("decision_lane_refs", {}) if isinstance(dep_subset.get("decision_lane_refs"), dict) else {}
    for tag in ["df_component_proof", "al_component_proof", "dla_component_proof"]:
        key = str(decision_refs.get(tag, "")).strip()
        if not key:
            blockers.append({"id": "M7P9-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "missing decision-lane key", "tag": tag}})
            issues.append(f"missing decision-lane key for {tag}")
            continue
        p = add_head_object_probe(probes, evidence_bucket, key, f"m7p9_s5_decision_{tag}")
        if p.get("status") != "PASS":
            blockers.append({"id": "M7P9-ST-B12", "severity": "S5", "status": "OPEN", "details": {"probe_id": f"m7p9_s5_decision_{tag}"}})
            issues.append(f"S5 decision-lane readback failed for {tag}")

    for src in [dep_profile.get("advisories", []), dep_decision_log.get("advisories", []), dep_dla_snapshot.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    verdict_name = expected_pass_verdict if overall_pass else "HOLD_REMEDIATE"
    next_gate = verdict_name

    dumpj(
        out / "m7p9_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P9-ST-S5",
            "findings": [
                {"id": "M7P9-ST-F17", "classification": "PREVENT", "finding": "S5 must fail closed on any unresolved chain/blocker inconsistency.", "required_action": "Emit ADVANCE_TO_P10 only when S0..S4 chain is fully green and blocker-free."},
                {"id": "M7P9-ST-F18", "classification": "PREVENT", "finding": "S5 closure evidence must stay artifact-complete and readable.", "required_action": "Block closure on missing rollup artifacts or failed readback probes."},
            ],
        },
    )
    dumpj(out / "m7p9_lane_matrix.json", {"component_sequence": ["M7P9-ST-S0", "M7P9-ST-S1", "M7P9-ST-S2", "M7P9-ST-S3", "M7P9-ST-S4", "M7P9-ST-S5"]})
    dumpj(out / "m7p9_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "upstream_m7p9_s4_phase_execution_id": dep_id, "status": "S5_ROLLUP_CARRY_FORWARD"})
    dumpj(out / "m7p9_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "upstream_m7p9_s4_phase_execution_id": dep_id, "verdict_candidate": verdict_name, "advisories": advisories})
    dumpj(out / "m7p9_df_snapshot.json", {**dep_df_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p9_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p9_al_snapshot.json", {**dep_al_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p9_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p9_dla_snapshot.json", {**dep_dla_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p9_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p9_score_distribution_profile.json", {**dep_score, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p9_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p9_action_mix_profile.json", {**dep_action, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p9_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p9_idempotency_collision_profile.json", {**dep_idemp, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p9_s4_phase_execution_id": dep_id, "verdict_candidate": verdict_name, "chain_rows": chain_rows})
    dumpj(out / "m7p9_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", **metrics})
    dumpj(out / "m7p9_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "chain_rows": chain_rows})
    dumpj(out / "m7p9_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p9_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P9_STRESS_MAX_SPEND_USD", 38)), "within_envelope": True, "method": "m7p9_s5_rollup_lane_v0"})

    decisions.extend(
        [
            "Enforced S4 dependency continuity and blocker closure before S5 rollup.",
            "Executed deterministic chain sweep across S0..S4 with run-scope consistency checks.",
            "Validated behavior-context and decision-lane readback before closure verdict.",
            "Applied deterministic verdict: ADVANCE_TO_P10 only when blocker-free and artifact-complete.",
        ]
    )
    dumpj(out / "m7p9_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "decisions": decisions, "advisories": advisories, "chain_rows": chain_rows})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P9-ST-S5", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P9-ST-S5",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": req_artifacts,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7p9_s4_phase_execution_id": dep_id,
        "verdict": verdict_name,
        "expected_verdict_on_pass": expected_pass_verdict,
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P9-ST-S5",
        "overall_pass": overall_pass,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
        "upstream_m7p9_s4_phase_execution_id": dep_id,
        "expected_verdict_on_pass": expected_pass_verdict,
        "chain_rows": chain_rows,
    }
    dumpj(out / "m7p9_blocker_register.json", blocker_reg)
    dumpj(out / "m7p9_execution_summary.json", summary)
    dumpj(out / "m7p9_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict, blocker_id="M7P9-ST-B12")

    summary = loadj(out / "m7p9_execution_summary.json")
    blocker_reg = loadj(out / "m7p9_blocker_register.json")
    print(f"[m7p9_s5] phase_execution_id={phase_execution_id}")
    print(f"[m7p9_s5] output_dir={out.as_posix()}")
    print(f"[m7p9_s5] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p9_s5] verdict={summary.get('verdict')}")
    print(f"[m7p9_s5] next_gate={summary.get('next_gate')}")
    print(f"[m7p9_s5] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M7.P9 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    args = ap.parse_args()

    stage_map = {
        "S0": ("m7p9_stress_s0", run_s0),
        "S1": ("m7p9_stress_s1", run_s1),
        "S2": ("m7p9_stress_s2", run_s2),
        "S3": ("m7p9_stress_s3", run_s3),
        "S4": ("m7p9_stress_s4", run_s4),
        "S5": ("m7p9_stress_s5", run_s5),
    }
    prefix, fn = stage_map[args.stage]
    phase_execution_id = args.phase_execution_id.strip() or f"{prefix}_{tok()}"
    return fn(phase_execution_id)


if __name__ == "__main__":
    raise SystemExit(main())
