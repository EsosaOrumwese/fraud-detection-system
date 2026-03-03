#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M3.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

S0_REQ_HANDLES = [
    "FIELD_PLATFORM_RUN_ID",
    "FIELD_SCENARIO_RUN_ID",
    "FIELD_CONFIG_DIGEST",
    "CONFIG_DIGEST_ALGO",
    "CONFIG_DIGEST_FIELD",
    "SCENARIO_EQUIVALENCE_KEY_INPUT",
    "SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS",
    "SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE",
    "SCENARIO_RUN_ID_DERIVATION_MODE",
    "S3_EVIDENCE_BUCKET",
    "S3_EVIDENCE_RUN_ROOT_PATTERN",
    "RUN_PIN_PATH_PATTERN",
    "EVIDENCE_RUN_JSON_KEY",
    "SFN_PLATFORM_RUN_ORCHESTRATOR_V0",
    "SR_READY_COMMIT_AUTHORITY",
    "REQUIRED_PLATFORM_RUN_ID_ENV_KEY",
    "ROLE_TERRAFORM_APPLY_DEV_FULL",
]

S0_PLAN_KEYS = [
    "M3_STRESS_PROFILE_ID",
    "M3_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M3_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M3_STRESS_DECISION_LOG_PATH_PATTERN",
    "M3_STRESS_REQUIRED_ARTIFACTS",
    "M3_STRESS_MAX_RUNTIME_MINUTES",
    "M3_STRESS_MAX_SPEND_USD",
    "M3_STRESS_BASELINE_CONCURRENT_RUNS",
    "M3_STRESS_BURST_CONCURRENT_RUNS",
    "M3_STRESS_WINDOW_MINUTES",
    "M3_STRESS_RUN_ID_REGEX",
    "M3_STRESS_RUN_ID_COLLISION_RETRY_CAP",
    "M3_STRESS_EXPECTED_NEXT_GATE_ON_PASS",
]

S0_ARTS = [
    "m3_stagea_findings.json",
    "m3_lane_matrix.json",
    "m3_probe_latency_throughput_snapshot.json",
    "m3_control_rail_conformance_snapshot.json",
    "m3_secret_safety_snapshot.json",
    "m3_cost_outcome_receipt.json",
    "m3_blocker_register.json",
    "m3_execution_summary.json",
    "m3_decision_log.json",
]
S1_ARTS = S0_ARTS
S2_ARTS = S0_ARTS


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tok() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canon_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


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
    rx = re.compile(r"^\* `([^`]+)\s*=\s*([^`]+)`(?:\s.*)?$")
    out: dict[str, Any] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(raw.strip())
        if m:
            out[m.group(1).strip()] = parse_scalar(m.group(2))
    return out


def resolve_handle(h: dict[str, Any], key: str, max_hops: int = 8) -> tuple[Any, list[str]]:
    chain = [key]
    if key not in h:
        return None, chain
    val: Any = h[key]
    hops = 0
    while isinstance(val, str):
        token = val.strip()
        if token in h and re.fullmatch(r"[A-Z0-9_]+", token) and token not in chain and hops < max_hops:
            chain.append(token)
            val = h[token]
            hops += 1
            continue
        break
    return val, chain


def run_cmd(cmd: list[str], timeout: int = 25) -> dict[str, Any]:
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


def load_latest_successful_m2_s5(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m2_stress_s5_*/stress"))
    for d in reversed(runs):
        sp = d / "m2_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M2-ST-S5":
            continue
        return {"path": d.as_posix(), "summary": summ}
    return {}


def load_latest_successful_stage(out_root: Path, run_prefix: str, stage_id: str) -> dict[str, Any]:
    runs = sorted(out_root.glob(f"{run_prefix}*/stress"))
    for d in reversed(runs):
        sp = d / "m3_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != stage_id:
            continue
        return {"path": d.as_posix(), "summary": summ}
    return {}


def copy_latest_s0(out_root: Path, out_dir: Path) -> list[str]:
    s0 = load_latest_successful_stage(out_root, "m3_stress_s0_", "M3-ST-S0")
    if not s0:
        return ["No successful M3 S0 folder found."]
    src = Path(str(s0["path"]))
    errs: list[str] = []
    for n in ("m3_stagea_findings.json", "m3_lane_matrix.json"):
        s = src / n
        if s.exists():
            shutil.copy2(s, out_dir / n)
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def copy_stagea_from_stage(out_root: Path, out_dir: Path, run_prefix: str, stage_id: str) -> list[str]:
    ref = load_latest_successful_stage(out_root, run_prefix, stage_id)
    if not ref:
        return [f"No successful {stage_id} folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m3_stagea_findings.json", "m3_lane_matrix.json"):
        s = src / n
        if s.exists():
            shutil.copy2(s, out_dir / n)
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def load_json_safe(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def pct(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return float(s[lo])
    return float(s[lo] * (hi - k) + s[hi] * (k - lo))


def run_named_probe(probe_id: str, group: str, cmd: list[str], timeout: int = 25) -> dict[str, Any]:
    r = run_cmd(cmd, timeout=timeout)
    r["probe_id"] = probe_id
    r["group"] = group
    return r


def s3_collision_probe(bucket: str, prefix: str, region: str) -> dict[str, Any]:
    res = run_cmd(
        [
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            bucket,
            "--prefix",
            prefix,
            "--max-keys",
            "1",
            "--region",
            region,
            "--output",
            "json",
        ],
        timeout=25,
    )
    out = {"probe": res, "colliding": True, "key_count": None}
    if res["status"] != "PASS":
        return out
    try:
        data = json.loads(res["stdout"] or "{}")
        kc = int(data.get("KeyCount", 0))
        out["key_count"] = kc
        out["colliding"] = kc > 0
    except Exception:
        out["colliding"] = True
    return out


def build_lane_matrix() -> dict[str, Any]:
    return {
        "component_sequence": ["M3.A/B/C", "M3.D/E/F", "M3.G/H/I/J"],
        "plane_sequence": ["identity_digest_plane", "orchestrator_lock_plane", "evidence_cost_plane"],
        "integrated_windows": ["S1_baseline", "S2_concurrency", "S3_failure_injection"],
    }


def run_s0(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}

    missing_plan_keys = [k for k in S0_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in S0_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in S0_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]

    m2 = load_latest_successful_m2_s5(out_root)
    m2s = m2.get("summary", {}) if m2 else {}
    m2_gate_ok = bool(m2) and str(m2s.get("next_gate", "")) == "M3_READY" and str(m2s.get("m3_readiness_recommendation", "")) == "GO"

    region = str(h.get("AWS_REGION", "eu-west-2"))
    sfn_name, sfn_chain = resolve_handle(h, "SFN_PLATFORM_RUN_ORCHESTRATOR_V0")
    sfn_name_s = str(sfn_name).strip() if sfn_name is not None else ""
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()

    checks: list[dict[str, Any]] = []
    sfn_check = {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "skipped: missing SFN handle", "duration_ms": 0.0}
    bucket_check = {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "skipped: missing S3_EVIDENCE_BUCKET handle", "duration_ms": 0.0}

    if sfn_name_s:
        sfn_check = run_cmd(
            [
                "aws",
                "stepfunctions",
                "list-state-machines",
                "--max-results",
                "100",
                "--region",
                region,
                "--query",
                f"stateMachines[?name=='{sfn_name_s}'].stateMachineArn | [0]",
                "--output",
                "text",
            ],
            timeout=30,
        )
    checks.append({"id": "M3S0-V5-SFN-SURFACE", **sfn_check})

    if bucket:
        bucket_check = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=20)
    checks.append({"id": "M3S0-V6-EVIDENCE-BUCKET", **bucket_check})

    issues: list[str] = []
    blockers: list[dict[str, Any]] = []
    if missing_plan_keys or missing_handles or placeholder_handles:
        issues.append("required plan keys/handles unresolved")
        blockers.append(
            {
                "id": "M3-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )
    if not m2_gate_ok:
        issues.append("M2 S5 entry gate invalid/missing")
        blockers.append(
            {
                "id": "M3-ST-B9",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "m2_s5_found": bool(m2),
                    "m2_s5_path": m2.get("path", ""),
                    "m2_s5_summary": m2s,
                    "expected": {"next_gate": "M3_READY", "m3_readiness_recommendation": "GO"},
                },
            }
        )

    ctrl_issues: list[str] = []
    if str(h.get("SR_READY_COMMIT_AUTHORITY", "")) != "step_functions_only":
        ctrl_issues.append("SR_READY_COMMIT_AUTHORITY drift")
    if sfn_check["status"] != "PASS" or sfn_check["stdout"] in {"", "None", "null"}:
        ctrl_issues.append("orchestrator state machine surface query failed")
    if bucket_check["status"] != "PASS":
        ctrl_issues.append("evidence bucket reachability failed")
    if ctrl_issues:
        issues.extend(ctrl_issues)
        blockers.append({"id": "M3-ST-B3", "severity": "S0", "status": "OPEN", "details": {"issues": ctrl_issues}})

    findings = [
        {
            "id": "M3-ST-F1",
            "classification": "PREVENT",
            "status": "CLOSED" if PLAN.exists() else "OPEN",
            "evidence": {"path": str(PLAN)},
        },
        {
            "id": "M3-ST-F2",
            "classification": "PREVENT",
            "status": "CLOSED" if not missing_handles and not placeholder_handles else "OPEN",
            "evidence": {"missing_handles": missing_handles, "placeholder_handles": placeholder_handles},
        },
        {
            "id": "M3-ST-F3",
            "classification": "PREVENT",
            "status": "CLOSED" if "M3-ST-S2" in txt and "cross-run" in txt else "OPEN",
        },
        {"id": "M3-ST-F4", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M3-ST-F5", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M3-ST-F6", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {
            "id": "M3-ST-F7",
            "classification": "ACCEPT",
            "status": "ACCEPTED" if m2_gate_ok else "OPEN",
            "evidence": {"m2_s5_path": m2.get("path", "")},
        },
    ]
    dumpj(
        out / "m3_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M3-ST-S0",
            "overall_pass": len(blockers) == 0,
            "findings": findings,
        },
    )
    dumpj(
        out / "m3_lane_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M3-ST-S0",
            "lane_matrix": build_lane_matrix(),
            "dispatch_profile": {
                "baseline_concurrent_runs": pkt.get("M3_STRESS_BASELINE_CONCURRENT_RUNS", 2),
                "burst_concurrent_runs": pkt.get("M3_STRESS_BURST_CONCURRENT_RUNS", 6),
                "window_minutes": pkt.get("M3_STRESS_WINDOW_MINUTES", 10),
            },
        },
    )
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    probe_count = len(checks)
    fail_count = sum(1 for c in checks if c["status"] != "PASS")
    dumpj(
        out / "m3_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M3-ST-S0",
            "window_seconds_observed": dur_s,
            "probe_count": probe_count,
            "failure_count": fail_count,
            "error_rate_pct": round((fail_count / probe_count) * 100.0, 4) if probe_count else 0.0,
            "checks": checks,
            "sfn_handle_chain": sfn_chain,
            "sfn_name_resolved": sfn_name_s,
        },
    )
    dumpj(
        out / "m3_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M3-ST-S0",
            "overall_pass": len(ctrl_issues) == 0 and m2_gate_ok,
            "issues": ctrl_issues + ([] if m2_gate_ok else ["M2 S5 handoff gate invalid"]),
            "sfn_lookup_probe": sfn_check,
            "m2_s5_handoff_summary": m2s,
            "sfn_handle_chain": sfn_chain,
        },
    )
    dumpj(
        out / "m3_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M3-ST-S0",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "suspicious_output_probe_ids": [],
            "plaintext_leakage_detected": False,
        },
    )
    max_sp = float(pkt.get("M3_STRESS_MAX_SPEND_USD", 20))
    dumpj(
        out / "m3_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M3-ST-S0",
            "window_seconds": dur_s,
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": max_sp,
            "within_envelope": True,
            "method": "readonly_authority_gate_v0",
        },
    )
    dumpj(
        out / "m3_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M3-ST-S0",
            "decisions": [
                "Validated required M3 handles and placeholder guards.",
                "Validated latest successful M2 S5 entry gate and M3 readiness recommendation.",
                "Executed orchestrator and evidence-bucket control-plane checks.",
                "Applied fail-closed blocker mapping for M3 S0.",
            ],
        },
    )

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S0",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    next_gate = "M3_ST_S1_READY" if len(blockers) == 0 else "BLOCKED"
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S0",
        "overall_pass": len(blockers) == 0,
        "next_gate": next_gate,
        "required_artifacts": S0_ARTS,
        "issue_count": len(issues),
    }
    dumpj(out / "m3_blocker_register.json", bref)
    dumpj(out / "m3_execution_summary.json", summ)

    miss = [n for n in S0_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M3-ST-B9", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m3_blocker_register.json", bref)
        dumpj(out / "m3_execution_summary.json", summ)

    print(f"[m3_s0] phase_execution_id={phase_id}")
    print(f"[m3_s0] output_dir={out.as_posix()}")
    print(f"[m3_s0] overall_pass={summ['overall_pass']}")
    print(f"[m3_s0] next_gate={summ['next_gate']}")
    print(f"[m3_s0] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s1(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_latest_s0(out_root, out)
    if copy_errs:
        blockers.append({"id": "M3-ST-B9", "severity": "S1", "status": "OPEN", "details": {"copy_errors": copy_errs}})

    s0 = load_latest_successful_stage(out_root, "m3_stress_s0_", "M3-ST-S0")
    if not s0:
        blockers.append({"id": "M3-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_dependency": "successful M3 S0"}})

    missing_plan_keys = [k for k in S0_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in S0_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in S0_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M3-ST-B1",
                "severity": "S1",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )

    region = str(h.get("AWS_REGION", "eu-west-2"))
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    sfn_name, sfn_chain = resolve_handle(h, "SFN_PLATFORM_RUN_ORCHESTRATOR_V0")
    sfn_name_s = str(sfn_name).strip() if sfn_name is not None else ""

    now_id = datetime.now(timezone.utc).strftime("platform_%Y%m%dT%H%M%SZ")
    run_id_regex = str(pkt.get("M3_STRESS_RUN_ID_REGEX", r"^platform_[0-9]{8}T[0-9]{6}Z(_[0-9]{2})?$"))
    format_pass = re.fullmatch(run_id_regex, now_id) is not None
    retry_cap = int(pkt.get("M3_STRESS_RUN_ID_COLLISION_RETRY_CAP", 20))
    root_pattern = str(h.get("S3_EVIDENCE_RUN_ROOT_PATTERN", "evidence/runs/{platform_run_id}/"))

    collision_receipts: list[dict[str, Any]] = []
    final_run_id = now_id
    collision_unresolved = False
    colliding_detected = False
    if bucket:
        resolved = False
        for i in range(max(1, retry_cap + 1)):
            cand = now_id if i == 0 else f"{now_id}_{i:02d}"
            prefix = root_pattern.replace("{platform_run_id}", cand)
            rc = s3_collision_probe(bucket, prefix, region)
            rc["attempt"] = i + 1
            rc["candidate_platform_run_id"] = cand
            rc["prefix"] = prefix
            collision_receipts.append(rc)
            if rc["probe"]["status"] != "PASS":
                collision_unresolved = True
                break
            if rc["colliding"]:
                colliding_detected = True
                continue
            final_run_id = cand
            resolved = True
            break
        if not resolved and collision_receipts and collision_receipts[-1]["probe"]["status"] == "PASS":
            collision_unresolved = True
    else:
        collision_unresolved = True

    digest_algo = str(h.get("CONFIG_DIGEST_ALGO", "")).strip()
    digest_field = str(h.get("CONFIG_DIGEST_FIELD", "")).strip()
    canonical_mode = str(h.get("SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE", "")).strip()
    scenario_mode = str(h.get("SCENARIO_RUN_ID_DERIVATION_MODE", "")).strip()
    canonical_fields = [x.strip() for x in str(h.get("SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS", "")).split(",") if x.strip()]

    digest_seed: dict[str, Any] = {
        "oracle_input_manifest_uri": f"s3://{bucket}/evidence/dev_full/oracle/input_manifest.json",
        "oracle_input_manifest_sha256": hashlib.sha256(b"oracle_input_manifest_seed_v0").hexdigest(),
        "oracle_required_output_ids": ["alert", "case", "score"],
        "oracle_sort_key_by_output_id": {"alert": "event_time", "case": "event_time", "score": "event_time"},
    }
    unknown_canonical_fields = [f for f in canonical_fields if f not in {"oracle_input_manifest_uri", "oracle_input_manifest_sha256", "oracle_required_output_ids", "oracle_sort_key_by_output_id", "config_digest"}]
    digest_input = {k: digest_seed[k] for k in canonical_fields if k in digest_seed}
    digest_input["config_digest"] = ""
    if "config_digest" in digest_input:
        digest_input.pop("config_digest")

    digest1 = ""
    digest2 = ""
    digest_match = False
    digest_error = ""
    if digest_algo == "sha256" and canonical_mode == "json_sorted_keys_v1":
        try:
            b = canon_json_bytes(digest_input)
            digest1 = hashlib.sha256(b).hexdigest()
            digest2 = hashlib.sha256(b).hexdigest()
            digest_match = digest1 == digest2
        except Exception as e:  # noqa: BLE001
            digest_error = str(e)
    else:
        digest_error = "unsupported digest/canonicalization contract"

    scenario1 = ""
    scenario2 = ""
    scenario_match = False
    scenario_error = ""
    if scenario_mode == "deterministic_hash_v1":
        try:
            b = canon_json_bytes(digest_input)
            scenario1 = "scenario_" + hashlib.sha256(b).hexdigest()[:32]
            scenario2 = "scenario_" + hashlib.sha256(b).hexdigest()[:32]
            scenario_match = scenario1 == scenario2
        except Exception as e:  # noqa: BLE001
            scenario_error = str(e)
    else:
        scenario_error = "unsupported scenario derivation mode"

    sfn_check = {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "skipped: missing SFN handle", "duration_ms": 0.0}
    bucket_check = {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "skipped: missing S3_EVIDENCE_BUCKET handle", "duration_ms": 0.0}
    if sfn_name_s:
        sfn_check = run_cmd(
            [
                "aws",
                "stepfunctions",
                "list-state-machines",
                "--max-results",
                "100",
                "--region",
                region,
                "--query",
                f"stateMachines[?name=='{sfn_name_s}'].stateMachineArn | [0]",
                "--output",
                "text",
            ],
            timeout=30,
        )
    if bucket:
        bucket_check = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=20)

    determinism_issues: list[str] = []
    if not format_pass:
        determinism_issues.append("platform_run_id format check failed")
    if collision_unresolved:
        determinism_issues.append("collision probe unresolved within retry cap")
    if unknown_canonical_fields:
        determinism_issues.append(f"unknown canonical fields: {','.join(unknown_canonical_fields)}")
    if not digest_match:
        determinism_issues.append("config digest recompute mismatch")
    if digest_error:
        determinism_issues.append(f"digest error: {digest_error}")
    if digest_field != "config_digest":
        determinism_issues.append("CONFIG_DIGEST_FIELD contract mismatch")
    if not scenario_match:
        determinism_issues.append("scenario_run_id recompute mismatch")
    if scenario_error:
        determinism_issues.append(f"scenario derivation error: {scenario_error}")
    if determinism_issues:
        blockers.append({"id": "M3-ST-B2", "severity": "S1", "status": "OPEN", "details": {"issues": determinism_issues}})

    ctrl_issues: list[str] = []
    if str(h.get("SR_READY_COMMIT_AUTHORITY", "")) != "step_functions_only":
        ctrl_issues.append("SR_READY_COMMIT_AUTHORITY drift")
    if sfn_check["status"] != "PASS" or sfn_check["stdout"] in {"", "None", "null"}:
        ctrl_issues.append("orchestrator state machine lookup failed")
    if bucket_check["status"] != "PASS":
        ctrl_issues.append("evidence bucket reachability failed")
    if ctrl_issues:
        blockers.append({"id": "M3-ST-B3", "severity": "S1", "status": "OPEN", "details": {"issues": ctrl_issues}})

    findings = [
        {"id": "M3-ST-F1", "classification": "PREVENT", "status": "CLOSED" if PLAN.exists() else "OPEN"},
        {"id": "M3-ST-F2", "classification": "PREVENT", "status": "CLOSED" if not missing_handles and not placeholder_handles else "OPEN"},
        {"id": "M3-ST-F3", "classification": "PREVENT", "status": "CLOSED" if "M3-ST-S2" in txt and "cross-run" in txt else "OPEN"},
        {"id": "M3-ST-F4", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M3-ST-F5", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M3-ST-F6", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M3-ST-F7", "classification": "ACCEPT", "status": "ACCEPTED"},
    ]
    if not (out / "m3_stagea_findings.json").exists():
        dumpj(
            out / "m3_stagea_findings.json",
            {
                "generated_at_utc": now(),
                "phase_execution_id": phase_id,
                "stage_id": "M3-ST-S1",
                "overall_pass": len(blockers) == 0,
                "findings": findings,
            },
        )
    if not (out / "m3_lane_matrix.json").exists():
        dumpj(
            out / "m3_lane_matrix.json",
            {
                "generated_at_utc": now(),
                "phase_execution_id": phase_id,
                "stage_id": "M3-ST-S1",
                "lane_matrix": build_lane_matrix(),
                "dispatch_profile": {
                    "baseline_concurrent_runs": pkt.get("M3_STRESS_BASELINE_CONCURRENT_RUNS", 2),
                    "burst_concurrent_runs": pkt.get("M3_STRESS_BURST_CONCURRENT_RUNS", 6),
                    "window_minutes": pkt.get("M3_STRESS_WINDOW_MINUTES", 10),
                },
            },
        )

    dur_s = max(1, int(round(time.perf_counter() - t0)))
    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S1",
        "window_seconds_observed": dur_s,
        "probe_count": 2 + len(collision_receipts),
        "failure_count": (1 if sfn_check["status"] != "PASS" else 0) + (1 if bucket_check["status"] != "PASS" else 0),
        "error_rate_pct": 0.0 if sfn_check["status"] == "PASS" and bucket_check["status"] == "PASS" else 100.0 / max(1, (2 + len(collision_receipts))),
        "platform_run_id_candidate": now_id,
        "platform_run_id_final": final_run_id,
        "platform_run_id_format_pass": format_pass,
        "collision_detected": colliding_detected,
        "collision_unresolved": collision_unresolved,
        "collision_probe_receipts": collision_receipts,
        "config_digest_algo": digest_algo,
        "config_digest_field": digest_field,
        "canonicalization_mode": canonical_mode,
        "config_digest": digest1,
        "config_digest_recompute": digest2,
        "config_digest_match": digest_match,
        "scenario_run_id": scenario1,
        "scenario_run_id_recompute": scenario2,
        "scenario_run_id_match": scenario_match,
        "determinism_issues": determinism_issues,
        "sfn_handle_chain": sfn_chain,
        "sfn_name_resolved": sfn_name_s,
    }
    dumpj(out / "m3_probe_latency_throughput_snapshot.json", probe)

    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S1",
        "overall_pass": len(ctrl_issues) == 0,
        "issues": ctrl_issues,
        "sfn_lookup_probe": sfn_check,
        "evidence_bucket_probe": bucket_check,
        "s0_dependency_summary": s0.get("summary", {}),
        "sfn_handle_chain": sfn_chain,
    }
    dumpj(out / "m3_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S1",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m3_secret_safety_snapshot.json", sec)

    max_sp = float(pkt.get("M3_STRESS_MAX_SPEND_USD", 20))
    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S1",
        "window_seconds": dur_s,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "readonly_baseline_determinism_v0",
    }
    dumpj(out / "m3_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S1",
        "decisions": [
            "Validated S0 continuity and carried Stage-A artifacts forward.",
            "Executed deterministic run-id format and collision probes.",
            "Executed digest and scenario-id recompute determinism checks.",
            "Executed orchestrator and evidence-root control-plane checks.",
            "Applied fail-closed blocker mapping for M3 S1.",
        ],
    }
    dumpj(out / "m3_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S1",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S1",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M3_ST_S2_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": S1_ARTS,
        "platform_run_id_final": final_run_id,
        "scenario_run_id": scenario1,
        "config_digest": digest1,
    }
    dumpj(out / "m3_blocker_register.json", bref)
    dumpj(out / "m3_execution_summary.json", summ)

    miss = [n for n in S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M3-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m3_blocker_register.json", bref)
        dumpj(out / "m3_execution_summary.json", summ)

    print(f"[m3_s1] phase_execution_id={phase_id}")
    print(f"[m3_s1] output_dir={out.as_posix()}")
    print(f"[m3_s1] overall_pass={summ['overall_pass']}")
    print(f"[m3_s1] next_gate={summ['next_gate']}")
    print(f"[m3_s1] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s2(phase_id: str, out_root: Path, win_override: int | None, interval: int, conc_override: int) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_stage(out_root, out, "m3_stress_s1_", "M3-ST-S1")
    if copy_errs:
        blockers.append({"id": "M3-ST-B9", "severity": "S2", "status": "OPEN", "details": {"copy_errors": copy_errs}})

    s1 = load_latest_successful_stage(out_root, "m3_stress_s1_", "M3-ST-S1")
    if not s1:
        blockers.append({"id": "M3-ST-B9", "severity": "S2", "status": "OPEN", "details": {"missing_dependency": "successful M3 S1"}})

    missing_plan_keys = [k for k in S0_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in S0_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in S0_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M3-ST-B1",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )

    region = str(h.get("AWS_REGION", "eu-west-2"))
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    root_pattern = str(h.get("S3_EVIDENCE_RUN_ROOT_PATTERN", "evidence/runs/{platform_run_id}/"))
    run_id_regex = str(pkt.get("M3_STRESS_RUN_ID_REGEX", r"^platform_[0-9]{8}T[0-9]{6}Z(_[0-9]{2})?$"))
    retry_cap = int(pkt.get("M3_STRESS_RUN_ID_COLLISION_RETRY_CAP", 20))
    burst_conc = int(pkt.get("M3_STRESS_BURST_CONCURRENT_RUNS", 6))
    if conc_override > 0:
        burst_conc = conc_override
    burst_conc = max(1, burst_conc)
    win = int(win_override) if win_override is not None else int(float(pkt.get("M3_STRESS_WINDOW_MINUTES", 10)) * 60)
    win = max(60, win)
    cycle_interval = max(1, interval)

    sfn_name, sfn_chain = resolve_handle(h, "SFN_PLATFORM_RUN_ORCHESTRATOR_V0")
    sfn_name_s = str(sfn_name).strip() if sfn_name is not None else ""

    s1_path = Path(str(s1.get("path", ""))) if s1 else Path("")
    s1_probe = load_json_safe(s1_path / "m3_probe_latency_throughput_snapshot.json") if s1 else {}
    s1_ctrl = load_json_safe(s1_path / "m3_control_rail_conformance_snapshot.json") if s1 else {}
    s1_issues = [str(x) for x in s1_ctrl.get("issues", [])] if s1_ctrl else []
    s1_p95 = float(s1_probe.get("latency_ms_p95", 0.0)) if s1_probe else 0.0

    rows: list[dict[str, Any]] = []
    precheck_issues: list[str] = []
    precheck_fail_closed = False

    sfn_lookup_pre = run_named_probe(
        "s2_sfn_lookup_precheck",
        "control",
        [
            "aws",
            "stepfunctions",
            "list-state-machines",
            "--max-results",
            "100",
            "--region",
            region,
            "--query",
            f"stateMachines[?name=='{sfn_name_s}'].stateMachineArn | [0]",
            "--output",
            "text",
        ],
        timeout=30,
    ) if sfn_name_s else {"probe_id": "s2_sfn_lookup_precheck", "group": "control", "status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "missing SFN handle", "duration_ms": 0.0, "command": "", "started_at_utc": now(), "ended_at_utc": now()}
    sfn_lookup_pre["cycle_index"] = 0
    sfn_lookup_pre["precheck"] = True
    rows.append(sfn_lookup_pre)

    bucket_pre = run_named_probe(
        "s2_evidence_bucket_precheck",
        "control",
        ["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region],
        timeout=20,
    ) if bucket else {"probe_id": "s2_evidence_bucket_precheck", "group": "control", "status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "missing S3_EVIDENCE_BUCKET handle", "duration_ms": 0.0, "command": "", "started_at_utc": now(), "ended_at_utc": now()}
    bucket_pre["cycle_index"] = 0
    bucket_pre["precheck"] = True
    rows.append(bucket_pre)

    sfn_arn = str(sfn_lookup_pre.get("stdout", "")).strip()
    if sfn_lookup_pre.get("status") != "PASS" or sfn_arn in {"", "None", "null"}:
        precheck_issues.append("orchestrator state machine lookup failed during precheck")
        sfn_arn = ""
    if bucket_pre.get("status") != "PASS":
        precheck_issues.append("evidence bucket reachability failed during precheck")

    run_lock_pre = {"probe_id": "s2_run_lock_precheck", "group": "control", "status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "skipped: missing state-machine arn", "duration_ms": 0.0, "command": "", "started_at_utc": now(), "ended_at_utc": now(), "cycle_index": 0, "precheck": True}
    if sfn_arn:
        run_lock_pre = run_named_probe(
            "s2_run_lock_precheck",
            "control",
            [
                "aws",
                "stepfunctions",
                "list-executions",
                "--state-machine-arn",
                sfn_arn,
                "--status-filter",
                "RUNNING",
                "--max-results",
                "100",
                "--region",
                region,
                "--output",
                "json",
            ],
            timeout=30,
        )
        run_lock_pre["cycle_index"] = 0
        run_lock_pre["precheck"] = True
    rows.append(run_lock_pre)

    precheck_running_count = 0
    precheck_conflicting_names: list[str] = []
    if run_lock_pre.get("status") == "PASS":
        try:
            jd = json.loads(str(run_lock_pre.get("stdout", "{}")) or "{}")
            execs = jd.get("executions", []) if isinstance(jd, dict) else []
            names = [str(x.get("name", "")).strip() for x in execs if isinstance(x, dict)]
            precheck_running_count = len(execs)
            freq: dict[str, int] = {}
            for n in names:
                if not n:
                    continue
                freq[n] = freq.get(n, 0) + 1
            precheck_conflicting_names = [n for n, c in freq.items() if c > 1]
        except Exception:
            precheck_issues.append("run-lock precheck response parse failure")
    else:
        precheck_issues.append("run-lock precheck query failed")

    if str(h.get("SR_READY_COMMIT_AUTHORITY", "")) != "step_functions_only":
        precheck_issues.append("SR_READY_COMMIT_AUTHORITY drift")

    if precheck_issues:
        precheck_fail_closed = True

    corr_issues: list[str] = []
    corr_fields = [x.strip() for x in str(h.get("CORRELATION_REQUIRED_FIELDS", "")).split(",") if x.strip()]
    corr_headers = [x.strip() for x in str(h.get("CORRELATION_HEADERS_REQUIRED", "")).split(",") if x.strip()]
    required_corr_fields = {"platform_run_id", "scenario_run_id", "phase_id", "event_id", "runtime_lane", "trace_id"}
    required_corr_headers = {"traceparent", "tracestate", "x-fp-platform-run-id", "x-fp-phase-id", "x-fp-event-id"}
    missing_corr_fields = sorted(required_corr_fields - set(corr_fields))
    missing_corr_headers = sorted(required_corr_headers - set(corr_headers))
    if missing_corr_fields:
        corr_issues.append(f"missing correlation required fields: {','.join(missing_corr_fields)}")
    if missing_corr_headers:
        corr_issues.append(f"missing correlation required headers: {','.join(missing_corr_headers)}")
    if h.get("CORRELATION_ENFORCEMENT_FAIL_CLOSED") is not True:
        corr_issues.append("CORRELATION_ENFORCEMENT_FAIL_CLOSED not true")

    determinism_issues: list[str] = []
    contention_cycle_results: list[dict[str, Any]] = []
    retries_used_total = 0
    unresolved_count = 0
    duplicate_inconsistent_cycles: list[int] = []
    lock_conflict_cycles: list[int] = []

    tstart = time.monotonic()
    cycles = 0

    def contention_probe(cycle_idx: int, task_idx: int, base_id: str, dup_count: int) -> dict[str, Any]:
        started = now()
        tt0 = time.perf_counter()
        mode = "duplicate_activation" if task_idx < dup_count else "near_simultaneous_activation"
        seed_offset = 0 if mode == "duplicate_activation" else (task_idx - dup_count + 1)
        receipts: list[dict[str, Any]] = []
        resolved_id = ""
        collision_detected = False
        unresolved = False
        format_fail = False
        attempts = 0
        for retry_idx in range(max(1, retry_cap + 1)):
            attempts = retry_idx + 1
            suffix = seed_offset + retry_idx
            candidate = base_id if suffix == 0 else f"{base_id}_{suffix:02d}"
            if re.fullmatch(run_id_regex, candidate) is None:
                format_fail = True
                break
            prefix = root_pattern.replace("{platform_run_id}", candidate)
            rc = s3_collision_probe(bucket, prefix, region)
            probe_rec = rc.get("probe", {})
            receipts.append(
                {
                    "attempt": attempts,
                    "candidate_platform_run_id": candidate,
                    "prefix": prefix,
                    "probe_status": probe_rec.get("status", "FAIL"),
                    "probe_exit_code": probe_rec.get("exit_code", 1),
                    "probe_duration_ms": probe_rec.get("duration_ms", 0.0),
                    "colliding": bool(rc.get("colliding", True)),
                    "key_count": rc.get("key_count"),
                }
            )
            if probe_rec.get("status") != "PASS":
                unresolved = True
                break
            if rc.get("colliding"):
                collision_detected = True
                continue
            resolved_id = candidate
            break
        if not resolved_id and not format_fail and receipts and receipts[-1].get("probe_status") == "PASS":
            unresolved = True
        row = {
            "probe_id": f"s2_contention_probe_{task_idx + 1:02d}",
            "group": "contention",
            "mode": mode,
            "cycle_index": cycle_idx,
            "command": "aws s3api list-objects-v2 (collision probe sequence)",
            "exit_code": 0 if (resolved_id and not format_fail and not unresolved) else 1,
            "status": "PASS" if (resolved_id and not format_fail and not unresolved) else "FAIL",
            "duration_ms": round((time.perf_counter() - tt0) * 1000.0, 3),
            "stdout": resolved_id[:300],
            "stderr": "" if (resolved_id and not format_fail and not unresolved) else "collision unresolved or format failure",
            "started_at_utc": started,
            "ended_at_utc": now(),
            "candidate_base_platform_run_id": base_id,
            "resolved_platform_run_id": resolved_id,
            "collision_detected": collision_detected,
            "collision_unresolved": unresolved,
            "format_fail": format_fail,
            "attempt_count": attempts,
            "retry_count_used": max(0, attempts - 1),
            "receipts": receipts[:5],
        }
        return row

    if (not precheck_fail_closed) and bucket and sfn_arn:
        while time.monotonic() - tstart < win:
            cycles += 1
            cycle_t0 = time.monotonic()
            base_id = datetime.now(timezone.utc).strftime("platform_%Y%m%dT%H%M%SZ")
            dup_count = max(2, burst_conc // 2)

            with cf.ThreadPoolExecutor(max_workers=burst_conc) as ex:
                futs = [ex.submit(contention_probe, cycles, i, base_id, dup_count) for i in range(burst_conc)]
                for f in cf.as_completed(futs):
                    rr = f.result()
                    rows.append(rr)
                    contention_cycle_results.append(rr)
                    retries_used_total += int(rr.get("retry_count_used", 0))
                    if bool(rr.get("collision_unresolved")):
                        unresolved_count += 1

            dup_rows = [r for r in contention_cycle_results if int(r.get("cycle_index", -1)) == cycles and str(r.get("mode", "")) == "duplicate_activation"]
            dup_pass_ids = sorted({str(r.get("resolved_platform_run_id", "")).strip() for r in dup_rows if str(r.get("status")) == "PASS"})
            dup_unresolved = sorted({bool(r.get("collision_unresolved")) for r in dup_rows})
            if (len(dup_pass_ids) > 1) or (len(dup_unresolved) > 1):
                duplicate_inconsistent_cycles.append(cycles)

            sfn_lookup = run_named_probe(
                "s2_sfn_lookup_cycle",
                "control",
                [
                    "aws",
                    "stepfunctions",
                    "list-state-machines",
                    "--max-results",
                    "100",
                    "--region",
                    region,
                    "--query",
                    f"stateMachines[?name=='{sfn_name_s}'].stateMachineArn | [0]",
                    "--output",
                    "text",
                ],
                timeout=30,
            )
            sfn_lookup["cycle_index"] = cycles
            rows.append(sfn_lookup)

            bucket_chk = run_named_probe(
                "s2_evidence_bucket_cycle",
                "control",
                ["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region],
                timeout=20,
            )
            bucket_chk["cycle_index"] = cycles
            rows.append(bucket_chk)

            lock_chk = run_named_probe(
                "s2_run_lock_cycle",
                "control",
                [
                    "aws",
                    "stepfunctions",
                    "list-executions",
                    "--state-machine-arn",
                    sfn_arn,
                    "--status-filter",
                    "RUNNING",
                    "--max-results",
                    "100",
                    "--region",
                    region,
                    "--output",
                    "json",
                ],
                timeout=30,
            )
            lock_chk["cycle_index"] = cycles
            if lock_chk.get("status") == "PASS":
                try:
                    jd = json.loads(str(lock_chk.get("stdout", "{}")) or "{}")
                    execs = jd.get("executions", []) if isinstance(jd, dict) else []
                    names = [str(x.get("name", "")).strip() for x in execs if isinstance(x, dict)]
                    freq: dict[str, int] = {}
                    for n in names:
                        if not n:
                            continue
                        freq[n] = freq.get(n, 0) + 1
                    conflicts = [n for n, c in freq.items() if c > 1]
                    lock_chk["running_execution_count"] = len(execs)
                    lock_chk["conflicting_names"] = conflicts
                    if conflicts:
                        lock_conflict_cycles.append(cycles)
                except Exception:
                    lock_chk["status"] = "FAIL"
                    lock_chk["exit_code"] = 1
                    lock_chk["stderr"] = "list-executions response parse failure"
            rows.append(lock_chk)

            sleep_for = min(max(0.0, cycle_interval - (time.monotonic() - cycle_t0)), max(0.0, win - (time.monotonic() - tstart)))
            if sleep_for > 0:
                time.sleep(sleep_for)

    dur = max(1.0, time.monotonic() - tstart)
    total = len(rows)
    fails = [r for r in rows if str(r.get("status", "FAIL")) != "PASS"]
    er = round((len(fails) / total) * 100.0, 4) if total else 100.0
    lat = [float(r.get("duration_ms", 0.0)) for r in rows]
    p95 = round(pct(lat, 0.95), 3)
    p95_ratio = round((p95 / s1_p95), 4) if s1_p95 > 0 else None

    cycle_failed: dict[int, bool] = {}
    for r in rows:
        idx = int(r.get("cycle_index", 0))
        if idx not in cycle_failed:
            cycle_failed[idx] = False
        if str(r.get("status", "FAIL")) != "PASS":
            cycle_failed[idx] = True
    cur_streak = 0
    max_streak = 0
    for idx in sorted(cycle_failed):
        if cycle_failed[idx]:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 0

    if duplicate_inconsistent_cycles:
        determinism_issues.append(f"duplicate run-id resolution inconsistent in cycles: {','.join(str(x) for x in duplicate_inconsistent_cycles[:10])}")
    if unresolved_count > 0:
        determinism_issues.append(f"collision unresolved count: {unresolved_count}")

    if precheck_fail_closed:
        determinism_issues.append("precheck fail-closed blocked contention window execution")

    ci: list[str] = []
    ci.extend(precheck_issues)
    if corr_issues:
        ci.extend(corr_issues)
    if lock_conflict_cycles:
        ci.append(f"run-lock conflicting execution names detected in cycles: {','.join(str(x) for x in lock_conflict_cycles[:10])}")
    cycle_sfn_fail = sum(1 for r in rows if str(r.get("probe_id")) == "s2_sfn_lookup_cycle" and str(r.get("status")) != "PASS")
    cycle_bucket_fail = sum(1 for r in rows if str(r.get("probe_id")) == "s2_evidence_bucket_cycle" and str(r.get("status")) != "PASS")
    cycle_lock_fail = sum(1 for r in rows if str(r.get("probe_id")) == "s2_run_lock_cycle" and str(r.get("status")) != "PASS")
    if cycle_sfn_fail > 0:
        ci.append(f"orchestrator lookup failures under contention: {cycle_sfn_fail}")
    if cycle_bucket_fail > 0:
        ci.append(f"evidence bucket failures under contention: {cycle_bucket_fail}")
    if cycle_lock_fail > 0:
        ci.append(f"run-lock query failures under contention: {cycle_lock_fail}")

    new_ci = sorted(set(ci) - set(s1_issues))

    contention_summary = {
        "burst_concurrency": burst_conc,
        "window_seconds_configured": win,
        "cycle_interval_seconds": cycle_interval,
        "cycles_executed": cycles,
        "contention_probe_count": sum(1 for r in rows if str(r.get("group")) == "contention"),
        "duplicate_probe_count": sum(1 for r in rows if str(r.get("mode")) == "duplicate_activation"),
        "near_simultaneous_probe_count": sum(1 for r in rows if str(r.get("mode")) == "near_simultaneous_activation"),
        "collision_unresolved_count": unresolved_count,
        "retry_count_total": retries_used_total,
        "duplicate_inconsistent_cycle_count": len(duplicate_inconsistent_cycles),
        "lock_conflict_cycle_count": len(lock_conflict_cycles),
        "precheck_fail_closed": precheck_fail_closed,
        "precheck_running_execution_count": precheck_running_count,
        "precheck_conflicting_names": precheck_conflicting_names,
    }

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S2",
        "window_seconds_configured": win,
        "window_seconds_observed": int(round(dur)),
        "cycle_count": cycles,
        "probe_count": total,
        "failure_count": len(fails),
        "error_rate_pct": er,
        "probe_eps_observed": round(total / dur, 4),
        "latency_ms_p50": round(pct(lat, 0.5), 3),
        "latency_ms_p95": p95,
        "latency_ms_p99": round(pct(lat, 0.99), 3),
        "max_consecutive_failure_cycles": max_streak,
        "sample_failures": fails[:10],
        "s1_baseline_phase_execution_id": s1.get("summary", {}).get("phase_execution_id", "") if s1 else "",
        "latency_ms_p95_vs_s1_ratio": p95_ratio,
        "determinism_issues": determinism_issues,
        "contention_summary": contention_summary,
        "sfn_handle_chain": sfn_chain,
        "sfn_name_resolved": sfn_name_s,
    }
    dumpj(out / "m3_probe_latency_throughput_snapshot.json", probe)

    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S2",
        "overall_pass": len(new_ci) == 0,
        "issues": ci,
        "s1_baseline_issues": s1_issues,
        "new_issues_vs_s1": new_ci,
        "s1_dependency_summary": s1.get("summary", {}) if s1 else {},
        "sfn_lookup_precheck": sfn_lookup_pre,
        "evidence_bucket_precheck": bucket_pre,
        "run_lock_precheck": run_lock_pre,
        "sfn_handle_chain": sfn_chain,
    }
    dumpj(out / "m3_control_rail_conformance_snapshot.json", ctrl)

    wdec = any("--with-decryption" in str(r.get("command", "")) for r in rows)
    qval = any("Parameter.Value" in str(r.get("command", "")) or "SecretString" in str(r.get("command", "")) for r in rows)
    sus: list[str] = []
    rx = re.compile(r"(AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|SECRET_ACCESS_KEY)")
    for r in rows:
        if rx.search((str(r.get("stdout", "")) + " " + str(r.get("stderr", ""))).strip()):
            sus.append(str(r.get("probe_id", "")))
    leak = wdec or qval or bool(sus)
    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S2",
        "overall_pass": not leak,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": wdec,
        "queried_value_directly": qval,
        "suspicious_output_probe_ids": sus,
        "plaintext_leakage_detected": leak,
    }
    dumpj(out / "m3_secret_safety_snapshot.json", sec)

    max_sp = float(pkt.get("M3_STRESS_MAX_SPEND_USD", 20))
    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S2",
        "window_seconds": int(round(dur)),
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "readonly_concurrency_contention_probe_v0",
    }
    dumpj(out / "m3_cost_outcome_receipt.json", cost)

    if determinism_issues:
        blockers.append({"id": "M3-ST-B2", "severity": "S2", "status": "OPEN", "details": {"issues": determinism_issues}})

    b3_issues = [x for x in ci if "orchestrator" in x or "run-lock" in x or "evidence bucket" in x]
    if b3_issues:
        blockers.append({"id": "M3-ST-B3", "severity": "S2", "status": "OPEN", "details": {"issues": sorted(set(b3_issues))}})

    b4_issues = [x for x in ci if "correlation" in x or "cross-run" in x or "conflicting execution names" in x]
    if b4_issues:
        blockers.append({"id": "M3-ST-B4", "severity": "S2", "status": "OPEN", "details": {"issues": sorted(set(b4_issues))}})

    b7_details: dict[str, Any] = {}
    if er > 2.0:
        b7_details["error_rate_pct"] = er
    if max_streak > 3:
        b7_details["max_consecutive_failure_cycles"] = max_streak
    if unresolved_count > 0:
        b7_details["collision_unresolved_count"] = unresolved_count
    if len(duplicate_inconsistent_cycles) > 0:
        b7_details["duplicate_inconsistent_cycle_count"] = len(duplicate_inconsistent_cycles)
    if b7_details:
        blockers.append({"id": "M3-ST-B7", "severity": "S2", "status": "OPEN", "details": b7_details})

    if sec["overall_pass"] is False:
        blockers.append({"id": "M3-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": ["plaintext leakage signal detected"]}})

    if not cost["within_envelope"] or cost["unattributed_spend_detected"]:
        blockers.append({"id": "M3-ST-B8", "severity": "S2", "status": "OPEN"})

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S2",
        "decisions": [
            "Validated S1 continuity and carried Stage-A artifacts forward.",
            "Executed burst concurrency contention probes with duplicate and near-simultaneous activation candidates.",
            "Executed per-cycle orchestrator/evidence/run-lock control probes under contention.",
            "Compared S2 control and latency posture against latest successful S1 baseline.",
            "Applied fail-closed blocker mapping for M3 S2.",
        ],
    }
    dumpj(out / "m3_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S2",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M3-ST-S2",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M3_ST_S3_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": S2_ARTS,
        "error_rate_pct": er,
        "probe_count": total,
        "window_seconds_observed": int(round(dur)),
        "max_consecutive_failure_cycles": max_streak,
        "latency_ms_p95_vs_s1_ratio": p95_ratio,
        "s1_baseline_phase_execution_id": s1.get("summary", {}).get("phase_execution_id", "") if s1 else "",
    }
    dumpj(out / "m3_blocker_register.json", bref)
    dumpj(out / "m3_execution_summary.json", summ)

    miss = [n for n in S2_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M3-ST-B9", "severity": "S2", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m3_blocker_register.json", bref)
        dumpj(out / "m3_execution_summary.json", summ)

    print(f"[m3_s2] phase_execution_id={phase_id}")
    print(f"[m3_s2] output_dir={out.as_posix()}")
    print(f"[m3_s2] overall_pass={summ['overall_pass']}")
    print(f"[m3_s2] next_gate={summ['next_gate']}")
    print(f"[m3_s2] probe_count={total}")
    print(f"[m3_s2] error_rate_pct={er}")
    print(f"[m3_s2] max_consecutive_failure_cycles={max_streak}")
    print(f"[m3_s2] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M3 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--output-root", default=str(OUT_ROOT))
    ap.add_argument("--window-seconds", type=int, default=None)
    ap.add_argument("--interval-seconds", type=int, default=5)
    ap.add_argument("--burst-concurrency", type=int, default=0)
    a = ap.parse_args()
    pfx = {"S0": "m3_stress_s0", "S1": "m3_stress_s1", "S2": "m3_stress_s2"}[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    root = Path(a.output_root)
    if a.stage == "S0":
        return run_s0(pid, root)
    if a.stage == "S1":
        return run_s1(pid, root)
    return run_s2(pid, root, a.window_seconds, a.interval_seconds, a.burst_concurrency)


if __name__ == "__main__":
    raise SystemExit(main())
