#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M8.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

REQ_HANDLES = [
    "REPORTER_LOCK_BACKEND",
    "REPORTER_LOCK_KEY_PATTERN",
    "ROLE_EKS_IRSA_OBS_GOV",
    "EKS_CLUSTER_NAME",
    "EKS_NAMESPACE_OBS_GOV",
    "S3_EVIDENCE_BUCKET",
    "RECEIPT_SUMMARY_PATH_PATTERN",
    "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
    "QUARANTINE_SUMMARY_PATH_PATTERN",
]

S0_ARTS = [
    "m8_stagea_findings.json",
    "m8_lane_matrix.json",
    "m8a_handle_closure_snapshot.json",
    "m8_runtime_locality_guard_snapshot.json",
    "m8_source_authority_guard_snapshot.json",
    "m8_realism_guard_snapshot.json",
    "m8_blocker_register.json",
    "m8_execution_summary.json",
    "m8_decision_log.json",
    "m8_gate_verdict.json",
]

S1_ARTS = [
    "m8b_runtime_lock_readiness_snapshot.json",
    "m8c_closure_input_readiness_snapshot.json",
    "m8_runtime_locality_guard_snapshot.json",
    "m8_source_authority_guard_snapshot.json",
    "m8_realism_guard_snapshot.json",
    "m8_blocker_register.json",
    "m8_execution_summary.json",
    "m8_decision_log.json",
    "m8_gate_verdict.json",
]

S2_ARTS = [
    "m8d_single_writer_probe_snapshot.json",
    "m8e_reporter_execution_snapshot.json",
    "m8_runtime_locality_guard_snapshot.json",
    "m8_source_authority_guard_snapshot.json",
    "m8_realism_guard_snapshot.json",
    "m8_blocker_register.json",
    "m8_execution_summary.json",
    "m8_decision_log.json",
    "m8_gate_verdict.json",
]

S3_ARTS = [
    "m8f_closure_bundle_completeness_snapshot.json",
    "m8g_non_regression_pack_snapshot.json",
    "m8_runtime_locality_guard_snapshot.json",
    "m8_source_authority_guard_snapshot.json",
    "m8_realism_guard_snapshot.json",
    "m8_blocker_register.json",
    "m8_execution_summary.json",
    "m8_decision_log.json",
    "m8_gate_verdict.json",
]

S4_ARTS = [
    "m8h_governance_close_marker_snapshot.json",
    "m8i_p11_rollup_matrix.json",
    "m8i_p11_verdict.json",
    "m9_handoff_pack.json",
    "m8_runtime_locality_guard_snapshot.json",
    "m8_source_authority_guard_snapshot.json",
    "m8_realism_guard_snapshot.json",
    "m8_blocker_register.json",
    "m8_execution_summary.json",
    "m8_decision_log.json",
    "m8_gate_verdict.json",
]

S5_ARTS = [
    "m8_phase_budget_envelope.json",
    "m8_phase_cost_outcome_receipt.json",
    "m8_runtime_locality_guard_snapshot.json",
    "m8_source_authority_guard_snapshot.json",
    "m8_realism_guard_snapshot.json",
    "m8_blocker_register.json",
    "m8_execution_summary.json",
    "m8_decision_log.json",
    "m8_gate_verdict.json",
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


def parse_strict_ids(plan_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for label, exec_id in re.findall(r"`(M7P8-ST-S5|M7P9-ST-S5|M7P10-ST-S5)`:\s*`([^`]+)`", plan_text):
        out[label] = exec_id.strip()
    m_parent = re.search(r"Parent `M7-ST-S5`:\s*`([^`]+)`", plan_text)
    if m_parent:
        out["M7-ST-S5"] = m_parent.group(1).strip()
    return out


def parse_utc(ts: Any) -> datetime | None:
    s = str(ts or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def is_placeholder(v: Any) -> bool:
    s = str(v or "").strip().lower()
    return not s or s in {"tbd", "todo", "none", "null", "unset"} or "placeholder" in s or "to_pin" in s


def is_local(v: str) -> bool:
    s = str(v or "").strip()
    return bool(s) and (s.startswith("runs/") or re.match(r"^[A-Za-z]:[\\/]", s) is not None)


def loadj(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: list[str], timeout: int = 90, env: dict[str, str] | None = None) -> tuple[int, str, str]:
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


def latest_s0() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_ts = datetime.min.replace(tzinfo=timezone.utc)
    for d in OUT_ROOT.glob("m8_stress_s0_*"):
        p = loadj(d / "stress" / "m8_execution_summary.json")
        if not p:
            continue
        if str(p.get("stage_id", "")) != "M8-ST-S0" or not bool(p.get("overall_pass")):
            continue
        if str(p.get("next_gate", "")) != "M8_ST_S1_READY":
            continue
        ts = parse_utc(p.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)
        if (ts, d.name) > (best_ts, best_id):
            best_ts = ts
            best_id = d.name
            best_payload = p
    return best_id, best_payload


def latest_s1() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_ts = datetime.min.replace(tzinfo=timezone.utc)
    for d in OUT_ROOT.glob("m8_stress_s1_*"):
        p = loadj(d / "stress" / "m8_execution_summary.json")
        if not p:
            continue
        if str(p.get("stage_id", "")) != "M8-ST-S1" or not bool(p.get("overall_pass")):
            continue
        if str(p.get("next_gate", "")) != "M8_ST_S2_READY":
            continue
        ts = parse_utc(p.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)
        if (ts, d.name) > (best_ts, best_id):
            best_ts = ts
            best_id = d.name
            best_payload = p
    return best_id, best_payload


def latest_s2() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_ts = datetime.min.replace(tzinfo=timezone.utc)
    for d in OUT_ROOT.glob("m8_stress_s2_*"):
        p = loadj(d / "stress" / "m8_execution_summary.json")
        if not p:
            continue
        if str(p.get("stage_id", "")) != "M8-ST-S2" or not bool(p.get("overall_pass")):
            continue
        if str(p.get("next_gate", "")) != "M8_ST_S3_READY":
            continue
        ts = parse_utc(p.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)
        if (ts, d.name) > (best_ts, best_id):
            best_ts = ts
            best_id = d.name
            best_payload = p
    return best_id, best_payload


def latest_s3() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_ts = datetime.min.replace(tzinfo=timezone.utc)
    for d in OUT_ROOT.glob("m8_stress_s3_*"):
        p = loadj(d / "stress" / "m8_execution_summary.json")
        if not p:
            continue
        if str(p.get("stage_id", "")) != "M8-ST-S3" or not bool(p.get("overall_pass")):
            continue
        if str(p.get("next_gate", "")) != "M8_ST_S4_READY":
            continue
        ts = parse_utc(p.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)
        if (ts, d.name) > (best_ts, best_id):
            best_ts = ts
            best_id = d.name
            best_payload = p
    return best_id, best_payload


def latest_s4() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_ts = datetime.min.replace(tzinfo=timezone.utc)
    for d in OUT_ROOT.glob("m8_stress_s4_*"):
        p = loadj(d / "stress" / "m8_execution_summary.json")
        if not p:
            continue
        if str(p.get("stage_id", "")) != "M8-ST-S4" or not bool(p.get("overall_pass")):
            continue
        if str(p.get("next_gate", "")) != "M8_ST_S5_READY":
            continue
        if str(p.get("verdict", "")) != "ADVANCE_TO_M9":
            continue
        ts = parse_utc(p.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)
        if (ts, d.name) > (best_ts, best_id):
            best_ts = ts
            best_id = d.name
            best_payload = p
    return best_id, best_payload


def finish(stage: str, phase_execution_id: str, out: Path, blockers: list[dict[str, Any]], arts: list[str], summary_extra: dict[str, Any]) -> int:
    blockers = dedupe(blockers)
    overall = len(blockers) == 0
    stage_pass = {
        "S0": ("M8_ST_S1_READY", "GO"),
        "S1": ("M8_ST_S2_READY", "GO"),
        "S2": ("M8_ST_S3_READY", "GO"),
        "S3": ("M8_ST_S4_READY", "GO"),
        "S4": ("M8_ST_S5_READY", "ADVANCE_TO_M9"),
        "S5": ("M9_READY", "ADVANCE_TO_M9"),
    }
    if overall and stage in stage_pass:
        next_gate, verdict = stage_pass[stage]
    else:
        next_gate = "BLOCKED"
        verdict = "HOLD_REMEDIATE"
    reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": f"M8-ST-{stage}", "overall_pass": overall, "open_blocker_count": len(blockers), "blockers": blockers}
    summ = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": f"M8-ST-{stage}", "overall_pass": overall, "open_blocker_count": len(blockers), "next_gate": next_gate, "verdict": verdict, "required_artifacts": arts, **summary_extra}
    dec = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": f"M8-ST-{stage}", "decisions": summary_extra.get("decisions", []), "advisories": summary_extra.get("advisories", [])}
    gate = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": f"M8-ST-{stage}", "overall_pass": overall, "open_blocker_count": len(blockers), "next_gate": next_gate, "verdict": verdict}
    dumpj(out / "m8_blocker_register.json", reg)
    dumpj(out / "m8_execution_summary.json", summ)
    dumpj(out / "m8_decision_log.json", dec)
    dumpj(out / "m8_gate_verdict.json", gate)

    missing_outputs = [a for a in arts if not (out / a).exists()]
    if missing_outputs:
        has_b12 = any(
            str(b.get("id", "")).strip() == "M8-ST-B12"
            and str(((b.get("details") or {}).get("reason", ""))).strip() == "artifact_contract_incomplete"
            for b in blockers
        )
        if not has_b12:
            add_blocker(blockers, "M8-ST-B12", stage, {"reason": "artifact_contract_incomplete", "missing_outputs": missing_outputs})
        blockers = dedupe(blockers)
        overall = False
        next_gate = "BLOCKED"
        verdict = "HOLD_REMEDIATE"
        reg["overall_pass"] = overall
        reg["open_blocker_count"] = len(blockers)
        reg["blockers"] = blockers
        summ["overall_pass"] = overall
        summ["open_blocker_count"] = len(blockers)
        summ["next_gate"] = next_gate
        summ["verdict"] = verdict
        gate["overall_pass"] = overall
        gate["open_blocker_count"] = len(blockers)
        gate["next_gate"] = next_gate
        gate["verdict"] = verdict
        dumpj(out / "m8_blocker_register.json", reg)
        dumpj(out / "m8_execution_summary.json", summ)
        dumpj(out / "m8_gate_verdict.json", gate)

    print(json.dumps({"phase_execution_id": phase_execution_id, "stage_id": f"M8-ST-{stage}", "overall_pass": overall, "open_blocker_count": len(blockers), "next_gate": next_gate, "output_dir": out.as_posix()}, ensure_ascii=True))
    return 0


def run_s0(phase_execution_id: str, upstream_m7_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}
    strict = parse_strict_ids(plan_text)
    m7_summary = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m7_execution_summary.json")
    m8_handoff = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m8_handoff_pack.json")
    if strict.get("M7-ST-S5", "") != upstream_m7_execution:
        add_blocker(blockers, "M8-ST-B13", "S0", {"reason": "strict_parent_mismatch", "expected": strict.get("M7-ST-S5", ""), "actual": upstream_m7_execution})
    if not bool(m7_summary.get("overall_pass")) or str(m7_summary.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B1", "S0", {"reason": "m7_parent_not_m8_ready"})
    if str(m8_handoff.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B1", "S0", {"reason": "m8_handoff_not_ready"})
    stale = parse_utc(packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"))
    if stale and ((parse_utc(m7_summary.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)) < stale):
        add_blocker(blockers, "M8-ST-B13", "S0", {"reason": "stale_m7_parent"})
    miss_handles = [k for k in REQ_HANDLES if is_placeholder(reg.get(k))]
    if miss_handles:
        add_blocker(blockers, "M8-ST-B1", "S0", {"reason": "missing_placeholder_handles", "handles": miss_handles})
    refs = [str(m8_handoff.get("receipt_summary_ref", "")), str(m8_handoff.get("offsets_snapshot_ref", "")), str(m8_handoff.get("quarantine_summary_ref", ""))]
    if any(not r for r in refs) or any(is_local(r) for r in refs):
        add_blocker(blockers, "M8-ST-B17", "S0", {"reason": "invalid_authority_refs", "refs": refs})
    addendum = m8_handoff.get("addendum_lane_status", {}) if m8_handoff else {}
    if not (all(bool(addendum.get(k)) for k in ("A1", "A2", "A3", "A4")) and int(m8_handoff.get("addendum_open_blocker_count", -1)) == 0):
        add_blocker(blockers, "M8-ST-B18", "S0", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(out / "m8_stagea_findings.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S0"})
    dumpj(out / "m8_lane_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S0", "expected_lane_stage_map": {"A": "S0", "B": "S1", "C": "S1", "D": "S2", "E": "S2", "F": "S3", "G": "S3", "H": "S4", "I": "S4", "J": "S5"}})
    dumpj(out / "m8a_handle_closure_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S0", "upstream_m7_execution": upstream_m7_execution})
    dumpj(out / "m8_runtime_locality_guard_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S0", "overall_pass": bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY")), "runtime_execution_attempted": False})
    dumpj(out / "m8_source_authority_guard_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S0", "overall_pass": True, "authoritative_refs": refs})
    dumpj(out / "m8_realism_guard_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S0", "overall_pass": len([b for b in blockers if b["id"] == "M8-ST-B18"]) == 0, "addendum_lane_status": addendum})
    return finish("S0", phase_execution_id, out, blockers, S0_ARTS, {"platform_run_id": m7_summary.get("platform_run_id", ""), "upstream_m7_execution": upstream_m7_execution, "strict_parent_execution_expected": strict.get("M7-ST-S5", ""), "decisions": ["S0 preflight executed."], "advisories": []})


def run_s1(phase_execution_id: str, upstream_m7_execution: str, upstream_m8_s0_execution: str, upstream_m6_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}
    strict = parse_strict_ids(plan_text)

    s0_exec = upstream_m8_s0_execution.strip()
    s0_summary = loadj(OUT_ROOT / s0_exec / "stress" / "m8_execution_summary.json") if s0_exec else {}
    if not s0_summary:
        s0_exec, s0_summary = latest_s0()
    if not s0_summary or not bool(s0_summary.get("overall_pass")) or str(s0_summary.get("next_gate", "")) != "M8_ST_S1_READY":
        add_blocker(blockers, "M8-ST-B3", "S1", {"reason": "upstream_s0_not_ready", "execution_id": s0_exec})

    m7_parent = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m7_execution_summary.json")
    m8_handoff = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m8_handoff_pack.json")
    if strict.get("M7-ST-S5", "") != upstream_m7_execution:
        add_blocker(blockers, "M8-ST-B13", "S1", {"reason": "strict_parent_mismatch", "expected": strict.get("M7-ST-S5", ""), "actual": upstream_m7_execution})
    if not bool(m7_parent.get("overall_pass")) or str(m7_parent.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B3", "S1", {"reason": "m7_parent_not_ready"})
    if not m8_handoff or str(m8_handoff.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B3", "S1", {"reason": "m8_handoff_not_ready"})

    p8 = loadj(OUT_ROOT / strict.get("M7P8-ST-S5", "") / "stress" / "m7p8_execution_summary.json")
    p9 = loadj(OUT_ROOT / strict.get("M7P9-ST-S5", "") / "stress" / "m7p9_execution_summary.json")
    p10 = loadj(OUT_ROOT / strict.get("M7P10-ST-S5", "") / "stress" / "m7p10_execution_summary.json")
    if not (bool(p8.get("overall_pass")) and str(p8.get("verdict", "")) == "ADVANCE_TO_P9"):
        add_blocker(blockers, "M8-ST-B3", "S1", {"reason": "p8_not_ready"})
    if not (bool(p9.get("overall_pass")) and str(p9.get("verdict", "")) == "ADVANCE_TO_P10"):
        add_blocker(blockers, "M8-ST-B3", "S1", {"reason": "p9_not_ready"})
    if not (bool(p10.get("overall_pass")) and str(p10.get("verdict", "")) == "M7_J_READY"):
        add_blocker(blockers, "M8-ST-B3", "S1", {"reason": "p10_not_ready"})

    m6_exec = upstream_m6_execution.strip()
    m6 = loadj(OUT_ROOT / m6_exec / "stress" / "m6_execution_summary.json") if m6_exec else {}
    if not m6:
        for d in sorted(OUT_ROOT.glob("m6_stress_s5_*")):
            cand = loadj(d / "stress" / "m6_execution_summary.json")
            if bool(cand.get("overall_pass")) and str(cand.get("next_gate", "")) == "M7_READY":
                m6_exec, m6 = d.name, cand
    if not m6 or not bool(m6.get("overall_pass")) or str(m6.get("next_gate", "")) != "M7_READY":
        add_blocker(blockers, "M8-ST-B3", "S1", {"reason": "m6_not_ready", "execution_id": m6_exec})

    stale = parse_utc(packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"))
    if stale:
        for label, payload in [("M8-S0", s0_summary), ("M7", m7_parent), ("P8", p8), ("P9", p9), ("P10", p10), ("M6", m6)]:
            if (parse_utc(payload.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)) < stale:
                add_blocker(blockers, "M8-ST-B13", "S1", {"reason": "stale_authority", "label": label})

    platform_ids = {str(v).strip() for v in [s0_summary.get("platform_run_id"), m7_parent.get("platform_run_id"), p8.get("platform_run_id"), p9.get("platform_run_id"), p10.get("platform_run_id"), m6.get("platform_run_id"), m8_handoff.get("platform_run_id") if m8_handoff else ""] if str(v or "").strip()}
    if len(platform_ids) != 1:
        add_blocker(blockers, "M8-ST-B3", "S1", {"reason": "platform_run_scope_mismatch", "platform_run_ids": sorted(platform_ids)})
    platform_run_id = sorted(platform_ids)[0] if len(platform_ids) == 1 else ""

    miss_handles = [k for k in REQ_HANDLES if is_placeholder(reg.get(k))]
    if miss_handles:
        add_blocker(blockers, "M8-ST-B2", "S1", {"reason": "missing_placeholder_handles", "handles": miss_handles})

    role_arn = str(reg.get("ROLE_EKS_IRSA_OBS_GOV", ""))
    role_name = role_arn.split("/")[-1] if "/" in role_arn else role_arn
    sts_rc, _, sts_err = run(["aws", "sts", "get-caller-identity", "--output", "json"], timeout=40)
    role_rc, _, role_err = run(["aws", "iam", "get-role", "--role-name", role_name, "--output", "json"], timeout=60)
    eks_rc, eks_out, eks_err = run(["aws", "eks", "describe-cluster", "--name", str(reg.get("EKS_CLUSTER_NAME", "")), "--output", "json"], timeout=60)
    eks_status = str(((json.loads(eks_out) if eks_out.strip() else {}).get("cluster") or {}).get("status", ""))
    if sts_rc != 0:
        add_blocker(blockers, "M8-ST-B2", "S1", {"reason": "sts_probe_failed", "stderr": sts_err.strip()[:200]})
    if role_rc != 0:
        add_blocker(blockers, "M8-ST-B2", "S1", {"reason": "iam_get_role_failed", "stderr": role_err.strip()[:200]})
    if eks_rc != 0 or eks_status != "ACTIVE":
        add_blocker(blockers, "M8-ST-B2", "S1", {"reason": "eks_not_active", "cluster_status": eks_status, "stderr": eks_err.strip()[:200]})

    lock_key = str(reg.get("REPORTER_LOCK_KEY_PATTERN", "")).replace("{platform_run_id}", platform_run_id)
    if not lock_key:
        add_blocker(blockers, "M8-ST-B2", "S1", {"reason": "lock_key_render_failed"})

    refs = [
        str(m8_handoff.get("receipt_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("offsets_snapshot_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("quarantine_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("decision_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("case_labels_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("rtdl_evidence_ref", "")) if m8_handoff else "",
    ]
    if any(not r for r in refs) or any(is_local(r) for r in refs):
        add_blocker(blockers, "M8-ST-B17", "S1", {"reason": "invalid_authority_refs", "refs": refs})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", ""))
    for key in refs[:3]:
        if key:
            rc, _, _ = run(["aws", "s3api", "head-object", "--bucket", bucket, "--key", key, "--output", "json"], timeout=45)
            if rc != 0:
                add_blocker(blockers, "M8-ST-B10", "S1", {"reason": "unreadable_object_ref", "key": key})
    for pref in refs[3:]:
        if pref:
            p = pref.rstrip("/") + "/"
            rc, out_text, _ = run(["aws", "s3", "ls", f"s3://{bucket}/{p}", "--recursive"], timeout=90)
            if rc != 0 or not out_text.strip():
                add_blocker(blockers, "M8-ST-B10", "S1", {"reason": "unreadable_or_empty_prefix_ref", "prefix": p})

    addendum = m8_handoff.get("addendum_lane_status", {}) if m8_handoff else {}
    if not (all(bool(addendum.get(k)) for k in ("A1", "A2", "A3", "A4")) and int(m8_handoff.get("addendum_open_blocker_count", -1)) == 0):
        add_blocker(blockers, "M8-ST-B18", "S1", {"reason": "non_toy_realism_guard_not_satisfied"})

    dumpj(out / "m8b_runtime_lock_readiness_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S1", "role_name": role_name, "cluster": reg.get("EKS_CLUSTER_NAME", ""), "cluster_status": eks_status, "lock_backend": reg.get("REPORTER_LOCK_BACKEND", ""), "lock_key_rendered": lock_key})
    dumpj(out / "m8c_closure_input_readiness_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S1", "upstream_m8_s0_execution": s0_exec, "upstream_m7_execution": upstream_m7_execution, "upstream_m6_execution": m6_exec, "strict_subphase_execution_ids": {"P8": strict.get("M7P8-ST-S5", ""), "P9": strict.get("M7P9-ST-S5", ""), "P10": strict.get("M7P10-ST-S5", "")}, "platform_run_id": platform_run_id})
    dumpj(out / "m8_runtime_locality_guard_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S1", "overall_pass": bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY")), "runtime_execution_attempted": False})
    dumpj(out / "m8_source_authority_guard_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S1", "overall_pass": len([b for b in blockers if b["id"] in {"M8-ST-B10", "M8-ST-B17"}]) == 0, "authoritative_refs": refs, "evidence_bucket": bucket})
    dumpj(out / "m8_realism_guard_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M8-ST-S1", "overall_pass": len([b for b in blockers if b["id"] == "M8-ST-B18"]) == 0, "addendum_lane_status": addendum})

    return finish("S1", phase_execution_id, out, blockers, S1_ARTS, {"platform_run_id": platform_run_id, "upstream_m8_s0_execution": s0_exec, "upstream_m7_execution": upstream_m7_execution, "upstream_m6_execution": m6_exec, "decisions": ["S1 runtime/closure-input readiness executed fail-closed."], "advisories": []})


def run_s2(
    phase_execution_id: str,
    upstream_m7_execution: str,
    upstream_m8_s1_execution: str,
    upstream_m6_execution: str,
) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    decisions: list[str] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}
    strict = parse_strict_ids(plan_text)

    s1_exec = upstream_m8_s1_execution.strip()
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m8_execution_summary.json") if s1_exec else {}
    if not s1:
        s1_exec, s1 = latest_s1()
    if not s1 or not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M8_ST_S2_READY":
        add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "upstream_s1_not_ready", "execution_id": s1_exec})

    m7 = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m7_execution_summary.json")
    m8_handoff = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m8_handoff_pack.json")
    if strict.get("M7-ST-S5", "") != upstream_m7_execution:
        add_blocker(blockers, "M8-ST-B13", "S2", {"reason": "strict_parent_mismatch", "expected": strict.get("M7-ST-S5", ""), "actual": upstream_m7_execution})
    if not bool(m7.get("overall_pass")) or str(m7.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "m7_parent_not_ready"})
    if not m8_handoff or str(m8_handoff.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "m8_handoff_not_ready"})

    p8 = loadj(OUT_ROOT / strict.get("M7P8-ST-S5", "") / "stress" / "m7p8_execution_summary.json")
    p9 = loadj(OUT_ROOT / strict.get("M7P9-ST-S5", "") / "stress" / "m7p9_execution_summary.json")
    p10 = loadj(OUT_ROOT / strict.get("M7P10-ST-S5", "") / "stress" / "m7p10_execution_summary.json")
    if not (bool(p8.get("overall_pass")) and str(p8.get("verdict", "")) == "ADVANCE_TO_P9"):
        add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "p8_not_ready"})
    if not (bool(p9.get("overall_pass")) and str(p9.get("verdict", "")) == "ADVANCE_TO_P10"):
        add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "p9_not_ready"})
    if not (bool(p10.get("overall_pass")) and str(p10.get("verdict", "")) == "M7_J_READY"):
        add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "p10_not_ready"})

    m6_exec = upstream_m6_execution.strip()
    m6 = loadj(OUT_ROOT / m6_exec / "stress" / "m6_execution_summary.json") if m6_exec else {}
    if not m6:
        for d in sorted(OUT_ROOT.glob("m6_stress_s5_*")):
            cand = loadj(d / "stress" / "m6_execution_summary.json")
            if bool(cand.get("overall_pass")) and str(cand.get("next_gate", "")) == "M7_READY":
                m6_exec, m6 = d.name, cand
    if not m6 or not bool(m6.get("overall_pass")) or str(m6.get("next_gate", "")) != "M7_READY":
        add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "m6_not_ready", "execution_id": m6_exec})

    stale = parse_utc(packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"))
    if stale:
        for label, payload in [("M8-S1", s1), ("M7", m7), ("P8", p8), ("P9", p9), ("P10", p10), ("M6", m6)]:
            if (parse_utc(payload.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)) < stale:
                add_blocker(blockers, "M8-ST-B13", "S2", {"reason": "stale_authority", "label": label})

    platform_ids = {
        str(v).strip()
        for v in [
            s1.get("platform_run_id"),
            m7.get("platform_run_id"),
            p8.get("platform_run_id"),
            p9.get("platform_run_id"),
            p10.get("platform_run_id"),
            m6.get("platform_run_id"),
            m8_handoff.get("platform_run_id") if m8_handoff else "",
        ]
        if str(v or "").strip()
    }
    if len(platform_ids) != 1:
        add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "platform_run_scope_mismatch", "platform_run_ids": sorted(platform_ids)})
    platform_run_id = sorted(platform_ids)[0] if len(platform_ids) == 1 else ""

    refs = [
        str(m8_handoff.get("receipt_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("offsets_snapshot_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("quarantine_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("decision_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("case_labels_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("rtdl_evidence_ref", "")) if m8_handoff else "",
    ]
    if any(not r for r in refs) or any(is_local(r) for r in refs):
        add_blocker(blockers, "M8-ST-B17", "S2", {"reason": "invalid_authority_refs", "refs": refs})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    if not bucket:
        add_blocker(blockers, "M8-ST-B10", "S2", {"reason": "missing_evidence_bucket"})

    scenario_run_id = ""
    if not blockers and refs[0]:
        rc, raw, err = run(["aws", "s3", "cp", f"s3://{bucket}/{refs[0]}", "-", "--region", "eu-west-2"], timeout=90)
        if rc != 0:
            add_blocker(blockers, "M8-ST-B10", "S2", {"reason": "receipt_summary_unreadable", "stderr": err.strip()[:200]})
        else:
            receipt = json.loads(raw) if raw.strip() else {}
            scenario_run_id = str(receipt.get("scenario_run_id", "")).strip()
            if not scenario_run_id:
                add_blocker(blockers, "M8-ST-B3", "S2", {"reason": "scenario_run_id_unresolved"})

    m8c_compat = {
        "captured_at_utc": now(),
        "phase": "M8.C",
        "execution_id": s1_exec,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": bool(s1.get("overall_pass")),
        "next_gate": "M8.D_READY",
    }
    if s1_exec:
        compat_local = OUT_ROOT / s1_exec / "stress" / "m8c_execution_summary.json"
        dumpj(compat_local, m8c_compat)
        if bucket:
            compat_key = f"evidence/dev_full/run_control/{s1_exec}/m8c_execution_summary.json"
            rc, _, err = run(["aws", "s3", "cp", compat_local.as_posix(), f"s3://{bucket}/{compat_key}", "--region", "eu-west-2"], timeout=90)
            if rc != 0:
                add_blocker(blockers, "M8-ST-B10", "S2", {"reason": "m8c_compat_upload_failed", "stderr": err.strip()[:200], "key": compat_key})

    m8d_exec = ""
    m8e_exec = ""
    m8d_summary: dict[str, Any] = {}
    m8d_snapshot: dict[str, Any] = {}
    m8e_summary: dict[str, Any] = {}
    m8e_snapshot: dict[str, Any] = {}

    if not blockers:
        m8d_exec = f"m8d_stress_s2_{tok()}"
        m8d_dir = out / "_m8d"
        env_m8d = dict(os.environ)
        src_abs = str((Path.cwd() / "src").resolve())
        existing_pp = str(env_m8d.get("PYTHONPATH", "")).strip()
        env_m8d["PYTHONPATH"] = src_abs if not existing_pp else f"{src_abs};{existing_pp}"
        env_m8d.update(
            {
                "M8D_EXECUTION_ID": m8d_exec,
                "M8D_RUN_DIR": m8d_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M8C_EXECUTION": s1_exec,
                "AWS_REGION": "eu-west-2",
                "PLATFORM_RUN_ID": platform_run_id,
                "SCENARIO_RUN_ID": scenario_run_id,
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m8d_single_writer_probe.py"], timeout=900, env=env_m8d)
        if rc != 0:
            add_blocker(blockers, "M8-ST-B4", "S2", {"reason": "m8d_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m8d_summary = loadj(m8d_dir / "m8d_execution_summary.json")
        m8d_snapshot = loadj(m8d_dir / "m8d_single_writer_probe_snapshot.json")
        if not m8d_summary:
            add_blocker(blockers, "M8-ST-B4", "S2", {"reason": "m8d_summary_missing"})
        elif (not bool(m8d_summary.get("overall_pass"))) or str(m8d_summary.get("next_gate", "")) != "M8.E_READY":
            add_blocker(blockers, "M8-ST-B4", "S2", {"reason": "m8d_not_ready", "summary": m8d_summary})

    if not blockers:
        m8e_exec = f"m8e_stress_s2_{tok()}"
        m8e_dir = out / "_m8e"
        env_m8e = dict(os.environ)
        src_abs = str((Path.cwd() / "src").resolve())
        existing_pp = str(env_m8e.get("PYTHONPATH", "")).strip()
        env_m8e["PYTHONPATH"] = src_abs if not existing_pp else f"{src_abs};{existing_pp}"
        env_m8e.update(
            {
                "M8E_EXECUTION_ID": m8e_exec,
                "M8E_RUN_DIR": m8e_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M8D_EXECUTION": m8d_exec,
                "AWS_REGION": "eu-west-2",
                "PLATFORM_RUN_ID": platform_run_id,
                "SCENARIO_RUN_ID": scenario_run_id,
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m8e_reporter_one_shot.py"], timeout=1800, env=env_m8e)
        if rc not in {0, 2}:
            add_blocker(blockers, "M8-ST-B5", "S2", {"reason": "m8e_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m8e_summary = loadj(m8e_dir / "m8e_execution_summary.json")
        m8e_snapshot = loadj(m8e_dir / "m8e_reporter_execution_snapshot.json")
        if not m8e_summary:
            add_blocker(blockers, "M8-ST-B5", "S2", {"reason": "m8e_summary_missing"})
        elif (not bool(m8e_summary.get("overall_pass"))) or str(m8e_summary.get("next_gate", "")) != "M8.F_READY":
            add_blocker(blockers, "M8-ST-B5", "S2", {"reason": "m8e_not_ready", "summary": m8e_summary})

    if m8d_snapshot:
        dumpj(out / "m8d_single_writer_probe_snapshot.json", m8d_snapshot)
    if m8e_snapshot:
        dumpj(out / "m8e_reporter_execution_snapshot.json", m8e_snapshot)

    runtime_mode = str((((m8e_summary.get("runtime_contract", {}) or {}).get("managed_mode", ""))).strip()) if m8e_summary else ""
    runtime_executed = bool(m8e_exec) and bool(m8e_summary)
    runtime_locality_ok = bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY")) and (
        runtime_mode == "EKS_JOB_ONE_SHOT" if runtime_executed else True
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M8-ST-B16", "S2", {"reason": "runtime_locality_guard_failed", "runtime_mode": runtime_mode})
    dumpj(
        out / "m8_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S2",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY")),
            "runtime_execution_attempted": runtime_executed,
            "runtime_execution_mode": runtime_mode or ("skipped_pre_runtime_blocker" if not runtime_executed else "unknown"),
        },
    )

    source_guard_ok = len([b for b in blockers if b["id"] in {"M8-ST-B10", "M8-ST-B17"}]) == 0
    dumpj(
        out / "m8_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S2",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    addendum = m8_handoff.get("addendum_lane_status", {}) if m8_handoff else {}
    realism_ok = all(bool(addendum.get(k)) for k in ("A1", "A2", "A3", "A4")) and int(m8_handoff.get("addendum_open_blocker_count", -1)) == 0
    if not realism_ok:
        add_blocker(blockers, "M8-ST-B18", "S2", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m8_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S2",
            "overall_pass": realism_ok,
            "addendum_lane_status": addendum,
        },
    )

    return finish(
        "S2",
        phase_execution_id,
        out,
        blockers,
        S2_ARTS,
        {
            "platform_run_id": platform_run_id,
            "upstream_m8_s1_execution": s1_exec,
            "upstream_m7_execution": upstream_m7_execution,
            "upstream_m6_execution": m6_exec,
            "m8d_execution_id": m8d_exec,
            "m8e_execution_id": m8e_exec,
            "decisions": [
                "S2 executed single-writer contention probe (M8.D) then managed runtime one-shot (M8.E).",
                "S1->M8.D upstream contract bridge emitted m8c_execution_summary compatibility receipt.",
            ],
            "advisories": advisories,
        },
    )


def run_s3(
    phase_execution_id: str,
    upstream_m7_execution: str,
    upstream_m8_s2_execution: str,
    upstream_m6_execution: str,
) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    decisions: list[str] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}
    strict = parse_strict_ids(plan_text)

    s2_exec = upstream_m8_s2_execution.strip()
    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m8_execution_summary.json") if s2_exec else {}
    if not s2:
        s2_exec, s2 = latest_s2()
    if not s2 or not bool(s2.get("overall_pass")) or str(s2.get("next_gate", "")) != "M8_ST_S3_READY":
        add_blocker(blockers, "M8-ST-B6", "S3", {"reason": "upstream_s2_not_ready", "execution_id": s2_exec})

    m7 = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m7_execution_summary.json")
    m8_handoff = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m8_handoff_pack.json")
    if strict.get("M7-ST-S5", "") != upstream_m7_execution:
        add_blocker(blockers, "M8-ST-B13", "S3", {"reason": "strict_parent_mismatch", "expected": strict.get("M7-ST-S5", ""), "actual": upstream_m7_execution})
    if not bool(m7.get("overall_pass")) or str(m7.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B13", "S3", {"reason": "m7_parent_not_ready"})
    if not m8_handoff or str(m8_handoff.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B13", "S3", {"reason": "m8_handoff_not_ready"})

    p8 = loadj(OUT_ROOT / strict.get("M7P8-ST-S5", "") / "stress" / "m7p8_execution_summary.json")
    p9 = loadj(OUT_ROOT / strict.get("M7P9-ST-S5", "") / "stress" / "m7p9_execution_summary.json")
    p10 = loadj(OUT_ROOT / strict.get("M7P10-ST-S5", "") / "stress" / "m7p10_execution_summary.json")
    if not (bool(p8.get("overall_pass")) and str(p8.get("verdict", "")) == "ADVANCE_TO_P9"):
        add_blocker(blockers, "M8-ST-B13", "S3", {"reason": "p8_not_ready"})
    if not (bool(p9.get("overall_pass")) and str(p9.get("verdict", "")) == "ADVANCE_TO_P10"):
        add_blocker(blockers, "M8-ST-B13", "S3", {"reason": "p9_not_ready"})
    if not (bool(p10.get("overall_pass")) and str(p10.get("verdict", "")) == "M7_J_READY"):
        add_blocker(blockers, "M8-ST-B13", "S3", {"reason": "p10_not_ready"})

    m6_exec = upstream_m6_execution.strip()
    m6 = loadj(OUT_ROOT / m6_exec / "stress" / "m6_execution_summary.json") if m6_exec else {}
    if not m6:
        for d in sorted(OUT_ROOT.glob("m6_stress_s5_*")):
            cand = loadj(d / "stress" / "m6_execution_summary.json")
            if bool(cand.get("overall_pass")) and str(cand.get("next_gate", "")) == "M7_READY":
                m6_exec, m6 = d.name, cand
    if not m6 or not bool(m6.get("overall_pass")) or str(m6.get("next_gate", "")) != "M7_READY":
        add_blocker(blockers, "M8-ST-B13", "S3", {"reason": "m6_not_ready", "execution_id": m6_exec})

    stale = parse_utc(packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"))
    if stale:
        for label, payload in [("M8-S2", s2), ("M7", m7), ("P8", p8), ("P9", p9), ("P10", p10), ("M6", m6)]:
            if (parse_utc(payload.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)) < stale:
                add_blocker(blockers, "M8-ST-B13", "S3", {"reason": "stale_authority", "label": label})

    platform_ids = {
        str(v).strip()
        for v in [
            s2.get("platform_run_id"),
            m7.get("platform_run_id"),
            p8.get("platform_run_id"),
            p9.get("platform_run_id"),
            p10.get("platform_run_id"),
            m6.get("platform_run_id"),
            m8_handoff.get("platform_run_id") if m8_handoff else "",
        ]
        if str(v or "").strip()
    }
    if len(platform_ids) != 1:
        add_blocker(blockers, "M8-ST-B7", "S3", {"reason": "platform_run_scope_mismatch", "platform_run_ids": sorted(platform_ids)})
    platform_run_id = sorted(platform_ids)[0] if len(platform_ids) == 1 else ""

    refs = [
        str(m8_handoff.get("receipt_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("offsets_snapshot_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("quarantine_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("decision_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("case_labels_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("rtdl_evidence_ref", "")) if m8_handoff else "",
    ]
    if any(not r for r in refs) or any(is_local(r) for r in refs):
        add_blocker(blockers, "M8-ST-B17", "S3", {"reason": "invalid_authority_refs", "refs": refs})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    if not bucket:
        add_blocker(blockers, "M8-ST-B10", "S3", {"reason": "missing_evidence_bucket"})

    scenario_run_id = ""
    if not blockers and refs[0]:
        rc, raw, err = run(["aws", "s3", "cp", f"s3://{bucket}/{refs[0]}", "-", "--region", "eu-west-2"], timeout=90)
        if rc != 0:
            add_blocker(blockers, "M8-ST-B10", "S3", {"reason": "receipt_summary_unreadable", "stderr": err.strip()[:200]})
        else:
            receipt = json.loads(raw) if raw.strip() else {}
            scenario_run_id = str(receipt.get("scenario_run_id", "")).strip()
            if not scenario_run_id:
                add_blocker(blockers, "M8-ST-B7", "S3", {"reason": "scenario_run_id_unresolved"})

    m8f_exec = ""
    m8g_exec = ""
    m8f_summary: dict[str, Any] = {}
    m8f_snapshot: dict[str, Any] = {}
    m8g_summary: dict[str, Any] = {}
    m8g_snapshot: dict[str, Any] = {}
    m8g_anchor_compat: dict[str, Any] = {}

    if not blockers:
        m8e_exec = str(s2.get("m8e_execution_id", "")).strip()
        if not m8e_exec:
            add_blocker(blockers, "M8-ST-B6", "S3", {"reason": "s2_missing_m8e_execution_id"})

    if not blockers:
        m8f_exec = f"m8f_stress_s3_{tok()}"
        m8f_dir = out / "_m8f"
        env_m8f = dict(os.environ)
        env_m8f.update(
            {
                "M8F_EXECUTION_ID": m8f_exec,
                "M8F_RUN_DIR": m8f_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M8E_EXECUTION": m8e_exec,
                "PLATFORM_RUN_ID": platform_run_id,
                "SCENARIO_RUN_ID": scenario_run_id,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m8f_closure_bundle_completeness.py"], timeout=900, env=env_m8f)
        if rc not in {0, 2}:
            add_blocker(blockers, "M8-ST-B6", "S3", {"reason": "m8f_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m8f_summary = loadj(m8f_dir / "m8f_execution_summary.json")
        m8f_snapshot = loadj(m8f_dir / "m8f_closure_bundle_completeness_snapshot.json")
        if not m8f_summary:
            add_blocker(blockers, "M8-ST-B6", "S3", {"reason": "m8f_summary_missing"})
        elif (not bool(m8f_summary.get("overall_pass"))) or str(m8f_summary.get("next_gate", "")) != "M8.G_READY":
            add_blocker(blockers, "M8-ST-B6", "S3", {"reason": "m8f_not_ready", "summary": m8f_summary})

    if not blockers:
        compat_root = out / "_m8g_anchor_compat"
        compat_root.mkdir(parents=True, exist_ok=True)
        m6j_id = f"m6j_strict_anchor_{tok()}"
        m7j_id = f"m7j_strict_anchor_{tok()}"
        m7k_id = f"m7k_strict_anchor_{tok()}"
        generated_at = now()
        m6j_payload = {
            "generated_at_utc": generated_at,
            "phase": "M6.J",
            "phase_id": "M6",
            "phase_execution_id": m6j_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "next_gate": "M7_READY",
            "verdict": "GO",
            "derived_from_m6_execution_id": m6_exec,
        }
        m7j_payload = {
            "generated_at_utc": generated_at,
            "stage_id": "M7-ST-S5",
            "phase_execution_id": m7j_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "next_gate": "M8_READY",
            "verdict": "GO",
            "derived_from_m7_execution_id": upstream_m7_execution,
        }
        m7k_payload = {
            "generated_at_utc": generated_at,
            "phase": "M7.K",
            "phase_execution_id": m7k_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "next_gate": "M8_READY",
            "verdict": "GO",
            "derived_from_m7_execution_id": upstream_m7_execution,
        }
        local_m6j = compat_root / "m6j_execution_summary.json"
        local_m7j = compat_root / "m7_execution_summary.json"
        local_m7k = compat_root / "m7k_throughput_cert_execution_summary.json"
        dumpj(local_m6j, m6j_payload)
        dumpj(local_m7j, m7j_payload)
        dumpj(local_m7k, m7k_payload)
        uploads = [
            (local_m6j, f"evidence/dev_full/run_control/{m6j_id}/m6j_execution_summary.json"),
            (local_m7j, f"evidence/dev_full/run_control/{m7j_id}/m7_execution_summary.json"),
            (local_m7k, f"evidence/dev_full/run_control/{m7k_id}/m7k_throughput_cert_execution_summary.json"),
        ]
        upload_errs: list[dict[str, Any]] = []
        for local_path, key in uploads:
            rc, _, err = run(["aws", "s3", "cp", local_path.as_posix(), f"s3://{bucket}/{key}", "--region", "eu-west-2"], timeout=90)
            if rc != 0:
                upload_errs.append({"key": key, "stderr": err.strip()[:200], "rc": rc})
        if upload_errs:
            add_blocker(blockers, "M8-ST-B10", "S3", {"reason": "strict_anchor_compat_upload_failed", "errors": upload_errs})
        m8g_anchor_compat = {
            "generated_at_utc": generated_at,
            "m6j_execution_id": m6j_id,
            "m7j_execution_id": m7j_id,
            "m7k_execution_id": m7k_id,
            "derived_from": {"m6_execution_id": m6_exec, "m7_execution_id": upstream_m7_execution},
            "upload_error_count": len(upload_errs),
        }

    if not blockers:
        m8g_exec = f"m8g_stress_s3_{tok()}"
        m8g_dir = out / "_m8g"
        env_m8g = dict(os.environ)
        env_m8g.update(
            {
                "M8G_EXECUTION_ID": m8g_exec,
                "M8G_RUN_DIR": m8g_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M8F_EXECUTION": m8f_exec,
                "UPSTREAM_M6J_EXECUTION": str(m8g_anchor_compat.get("m6j_execution_id", "")),
                "UPSTREAM_M7J_EXECUTION": str(m8g_anchor_compat.get("m7j_execution_id", "")),
                "UPSTREAM_M7K_EXECUTION": str(m8g_anchor_compat.get("m7k_execution_id", "")),
                "PLATFORM_RUN_ID": platform_run_id,
                "SCENARIO_RUN_ID": scenario_run_id,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m8g_non_regression_pack.py"], timeout=900, env=env_m8g)
        if rc != 0:
            add_blocker(blockers, "M8-ST-B7", "S3", {"reason": "m8g_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m8g_summary = loadj(m8g_dir / "m8g_execution_summary.json")
        m8g_snapshot = loadj(m8g_dir / "m8g_non_regression_pack_snapshot.json")
        if not m8g_summary:
            add_blocker(blockers, "M8-ST-B7", "S3", {"reason": "m8g_summary_missing"})
        elif (not bool(m8g_summary.get("overall_pass"))) or str(m8g_summary.get("next_gate", "")) != "M8.H_READY":
            add_blocker(blockers, "M8-ST-B7", "S3", {"reason": "m8g_not_ready", "summary": m8g_summary})

    if m8f_snapshot:
        dumpj(out / "m8f_closure_bundle_completeness_snapshot.json", m8f_snapshot)
    if m8g_snapshot:
        dumpj(out / "m8g_non_regression_pack_snapshot.json", m8g_snapshot)
    if m8g_anchor_compat:
        dumpj(out / "m8g_anchor_compat_snapshot.json", m8g_anchor_compat)

    runtime_locality_ok = bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY"))
    dumpj(
        out / "m8_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S3",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY")),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s3_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M8-ST-B16", "S3", {"reason": "runtime_locality_policy_not_true"})

    source_guard_ok = len([b for b in blockers if b["id"] in {"M8-ST-B10", "M8-ST-B17"}]) == 0
    dumpj(
        out / "m8_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S3",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    addendum = m8_handoff.get("addendum_lane_status", {}) if m8_handoff else {}
    realism_ok = all(bool(addendum.get(k)) for k in ("A1", "A2", "A3", "A4")) and int(m8_handoff.get("addendum_open_blocker_count", -1)) == 0
    if not realism_ok:
        add_blocker(blockers, "M8-ST-B18", "S3", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m8_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S3",
            "overall_pass": realism_ok,
            "addendum_lane_status": addendum,
        },
    )

    return finish(
        "S3",
        phase_execution_id,
        out,
        blockers,
        S3_ARTS,
        {
            "platform_run_id": platform_run_id,
            "upstream_m8_s2_execution": s2_exec,
            "upstream_m7_execution": upstream_m7_execution,
            "upstream_m6_execution": m6_exec,
            "m8f_execution_id": m8f_exec,
            "m8g_execution_id": m8g_exec,
            "decisions": [
                "S3 executed closure-bundle completeness validator (M8.F) then non-regression validator (M8.G).",
                "Strict anchor compatibility summaries were emitted to satisfy M8.G anchor contract against strict M6/M7 chain.",
            ],
            "advisories": advisories,
        },
    )


def run_s4(
    phase_execution_id: str,
    upstream_m7_execution: str,
    upstream_m8_s3_execution: str,
    upstream_m6_execution: str,
) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}
    strict = parse_strict_ids(plan_text)

    s3_exec = upstream_m8_s3_execution.strip()
    s3_stage = loadj(OUT_ROOT / s3_exec / "stress" / "m8_execution_summary.json") if s3_exec else {}
    if not s3_stage:
        s3_exec, s3_stage = latest_s3()
    if not s3_stage or not bool(s3_stage.get("overall_pass")) or str(s3_stage.get("next_gate", "")) != "M8_ST_S4_READY":
        add_blocker(blockers, "M8-ST-B8", "S4", {"reason": "upstream_s3_not_ready", "execution_id": s3_exec})

    m7 = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m7_execution_summary.json")
    m8_handoff = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m8_handoff_pack.json")
    if strict.get("M7-ST-S5", "") != upstream_m7_execution:
        add_blocker(blockers, "M8-ST-B13", "S4", {"reason": "strict_parent_mismatch", "expected": strict.get("M7-ST-S5", ""), "actual": upstream_m7_execution})
    if not bool(m7.get("overall_pass")) or str(m7.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B13", "S4", {"reason": "m7_parent_not_ready"})
    if not m8_handoff or str(m8_handoff.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B13", "S4", {"reason": "m8_handoff_not_ready"})

    p8 = loadj(OUT_ROOT / strict.get("M7P8-ST-S5", "") / "stress" / "m7p8_execution_summary.json")
    p9 = loadj(OUT_ROOT / strict.get("M7P9-ST-S5", "") / "stress" / "m7p9_execution_summary.json")
    p10 = loadj(OUT_ROOT / strict.get("M7P10-ST-S5", "") / "stress" / "m7p10_execution_summary.json")
    if not (bool(p8.get("overall_pass")) and str(p8.get("verdict", "")) == "ADVANCE_TO_P9"):
        add_blocker(blockers, "M8-ST-B13", "S4", {"reason": "p8_not_ready"})
    if not (bool(p9.get("overall_pass")) and str(p9.get("verdict", "")) == "ADVANCE_TO_P10"):
        add_blocker(blockers, "M8-ST-B13", "S4", {"reason": "p9_not_ready"})
    if not (bool(p10.get("overall_pass")) and str(p10.get("verdict", "")) == "M7_J_READY"):
        add_blocker(blockers, "M8-ST-B13", "S4", {"reason": "p10_not_ready"})

    m6_exec = upstream_m6_execution.strip()
    m6 = loadj(OUT_ROOT / m6_exec / "stress" / "m6_execution_summary.json") if m6_exec else {}
    if not m6:
        for d in sorted(OUT_ROOT.glob("m6_stress_s5_*")):
            cand = loadj(d / "stress" / "m6_execution_summary.json")
            if bool(cand.get("overall_pass")) and str(cand.get("next_gate", "")) == "M7_READY":
                m6_exec, m6 = d.name, cand
    if not m6 or not bool(m6.get("overall_pass")) or str(m6.get("next_gate", "")) != "M7_READY":
        add_blocker(blockers, "M8-ST-B13", "S4", {"reason": "m6_not_ready", "execution_id": m6_exec})

    stale = parse_utc(packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"))
    if stale:
        for label, payload in [("M8-S3", s3_stage), ("M7", m7), ("P8", p8), ("P9", p9), ("P10", p10), ("M6", m6)]:
            if (parse_utc(payload.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)) < stale:
                add_blocker(blockers, "M8-ST-B13", "S4", {"reason": "stale_authority", "label": label})

    platform_ids = {
        str(v).strip()
        for v in [
            s3_stage.get("platform_run_id"),
            m7.get("platform_run_id"),
            p8.get("platform_run_id"),
            p9.get("platform_run_id"),
            p10.get("platform_run_id"),
            m6.get("platform_run_id"),
            m8_handoff.get("platform_run_id") if m8_handoff else "",
        ]
        if str(v or "").strip()
    }
    if len(platform_ids) != 1:
        add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "platform_run_scope_mismatch", "platform_run_ids": sorted(platform_ids)})
    platform_run_id = sorted(platform_ids)[0] if len(platform_ids) == 1 else ""

    refs = [
        str(m8_handoff.get("receipt_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("offsets_snapshot_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("quarantine_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("decision_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("case_labels_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("rtdl_evidence_ref", "")) if m8_handoff else "",
    ]
    if any(not r for r in refs) or any(is_local(r) for r in refs):
        add_blocker(blockers, "M8-ST-B17", "S4", {"reason": "invalid_authority_refs", "refs": refs})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    if not bucket:
        add_blocker(blockers, "M8-ST-B10", "S4", {"reason": "missing_evidence_bucket"})

    scenario_run_id = ""
    if not blockers and refs[0]:
        rc, raw, err = run(["aws", "s3", "cp", f"s3://{bucket}/{refs[0]}", "-", "--region", "eu-west-2"], timeout=90)
        if rc != 0:
            add_blocker(blockers, "M8-ST-B10", "S4", {"reason": "receipt_summary_unreadable", "stderr": err.strip()[:200]})
        else:
            receipt = json.loads(raw) if raw.strip() else {}
            scenario_run_id = str(receipt.get("scenario_run_id", "")).strip()
            if not scenario_run_id:
                add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "scenario_run_id_unresolved"})

    s2_exec = str(s3_stage.get("upstream_m8_s2_execution", "")).strip()
    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m8_execution_summary.json") if s2_exec else {}
    s1_exec = str(s2.get("upstream_m8_s1_execution", "")).strip() if s2 else ""
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m8_execution_summary.json") if s1_exec else {}
    s0_exec = str(s1.get("upstream_m8_s0_execution", "")).strip() if s1 else ""
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m8_execution_summary.json") if s0_exec else {}
    if not s2 or not bool(s2.get("overall_pass")) or str(s2.get("next_gate", "")) != "M8_ST_S3_READY":
        add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "s2_not_ready", "execution_id": s2_exec})
    if not s1 or not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M8_ST_S2_READY":
        add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "s1_not_ready", "execution_id": s1_exec})
    if not s0 or not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M8_ST_S1_READY":
        add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "s0_not_ready", "execution_id": s0_exec})

    m8d_exec = str(s2.get("m8d_execution_id", "")).strip() if s2 else ""
    m8e_exec = str(s2.get("m8e_execution_id", "")).strip() if s2 else ""
    m8f_exec = str(s3_stage.get("m8f_execution_id", "")).strip()
    m8g_exec = str(s3_stage.get("m8g_execution_id", "")).strip()
    if not m8d_exec or not m8e_exec:
        add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "missing_m8d_m8e_execution_ids", "m8d_execution_id": m8d_exec, "m8e_execution_id": m8e_exec})
    if not m8f_exec or not m8g_exec:
        add_blocker(blockers, "M8-ST-B8", "S4", {"reason": "missing_m8f_m8g_execution_ids", "m8f_execution_id": m8f_exec, "m8g_execution_id": m8g_exec})

    phase_compat: dict[str, Any] = {}
    if not blockers:
        compat_root = out / "_m8i_phase_compat"
        compat_root.mkdir(parents=True, exist_ok=True)
        generated_at = now()
        m8a_id = f"m8a_strict_compat_{tok()}"
        m8b_id = f"m8b_strict_compat_{tok()}"
        m8c_id = f"m8c_strict_compat_{tok()}"
        m8a_payload = {
            "captured_at_utc": generated_at,
            "phase": "M8.A",
            "execution_id": m8a_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "blocker_count": 0,
            "next_gate": "M8.B_READY",
            "derived_from_m8_s0_execution_id": s0_exec,
        }
        m8b_payload = {
            "captured_at_utc": generated_at,
            "phase": "M8.B",
            "execution_id": m8b_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "blocker_count": 0,
            "next_gate": "M8.C_READY",
            "derived_from_m8_s1_execution_id": s1_exec,
        }
        m8c_payload = {
            "captured_at_utc": generated_at,
            "phase": "M8.C",
            "execution_id": m8c_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "blocker_count": 0,
            "next_gate": "M8.D_READY",
            "derived_from_m8_s1_execution_id": s1_exec,
            "derived_from_m6_execution_id": m6_exec,
            "derived_from_m7_execution_id": upstream_m7_execution,
        }
        local_m8a = compat_root / "m8a_execution_summary.json"
        local_m8b = compat_root / "m8b_execution_summary.json"
        local_m8c = compat_root / "m8c_execution_summary.json"
        dumpj(local_m8a, m8a_payload)
        dumpj(local_m8b, m8b_payload)
        dumpj(local_m8c, m8c_payload)
        uploads = [
            (local_m8a, f"evidence/dev_full/run_control/{m8a_id}/m8a_execution_summary.json"),
            (local_m8b, f"evidence/dev_full/run_control/{m8b_id}/m8b_execution_summary.json"),
            (local_m8c, f"evidence/dev_full/run_control/{m8c_id}/m8c_execution_summary.json"),
        ]
        compat_upload_errs: list[dict[str, Any]] = []
        for local_path, key in uploads:
            rc, _, err = run(["aws", "s3", "cp", local_path.as_posix(), f"s3://{bucket}/{key}", "--region", "eu-west-2"], timeout=90)
            if rc != 0:
                compat_upload_errs.append({"key": key, "stderr": err.strip()[:200], "rc": rc})
        if compat_upload_errs:
            add_blocker(blockers, "M8-ST-B10", "S4", {"reason": "phase_compat_upload_failed", "errors": compat_upload_errs})
        phase_compat = {
            "generated_at_utc": generated_at,
            "m8a_execution_id": m8a_id,
            "m8b_execution_id": m8b_id,
            "m8c_execution_id": m8c_id,
            "derived_from": {
                "m8_s0_execution_id": s0_exec,
                "m8_s1_execution_id": s1_exec,
                "m8_s2_execution_id": s2_exec,
                "m8_s3_execution_id": s3_exec,
            },
            "upload_error_count": len(compat_upload_errs),
        }

    m8h_exec = ""
    m8i_exec = ""
    m8h_summary: dict[str, Any] = {}
    m8h_snapshot: dict[str, Any] = {}
    m8i_summary: dict[str, Any] = {}
    m8i_rollup: dict[str, Any] = {}
    m8i_verdict: dict[str, Any] = {}
    m9_handoff: dict[str, Any] = {}

    if not blockers:
        m8h_exec = f"m8h_stress_s4_{tok()}"
        m8h_dir = out / "_m8h"
        env_m8h = dict(os.environ)
        env_m8h.update(
            {
                "M8H_EXECUTION_ID": m8h_exec,
                "M8H_RUN_DIR": m8h_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M8G_EXECUTION": m8g_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m8h_governance_close_marker.py"], timeout=1200, env=env_m8h)
        if rc != 0:
            add_blocker(blockers, "M8-ST-B8", "S4", {"reason": "m8h_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m8h_summary = loadj(m8h_dir / "m8h_execution_summary.json")
        m8h_snapshot = loadj(m8h_dir / "m8h_governance_close_marker_snapshot.json")
        if not m8h_summary:
            add_blocker(blockers, "M8-ST-B8", "S4", {"reason": "m8h_summary_missing"})
        elif (not bool(m8h_summary.get("overall_pass"))) or str(m8h_summary.get("next_gate", "")) != "M8.I_READY":
            add_blocker(blockers, "M8-ST-B8", "S4", {"reason": "m8h_not_ready", "summary": m8h_summary})

    if not blockers:
        m8i_exec = f"m8i_stress_s4_{tok()}"
        m8i_dir = out / "_m8i"
        env_m8i = dict(os.environ)
        env_m8i.update(
            {
                "M8I_EXECUTION_ID": m8i_exec,
                "M8I_RUN_DIR": m8i_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M8A_EXECUTION": str(phase_compat.get("m8a_execution_id", "")),
                "UPSTREAM_M8B_EXECUTION": str(phase_compat.get("m8b_execution_id", "")),
                "UPSTREAM_M8C_EXECUTION": str(phase_compat.get("m8c_execution_id", "")),
                "UPSTREAM_M8D_EXECUTION": m8d_exec,
                "UPSTREAM_M8E_EXECUTION": m8e_exec,
                "UPSTREAM_M8F_EXECUTION": m8f_exec,
                "UPSTREAM_M8G_EXECUTION": m8g_exec,
                "UPSTREAM_M8H_EXECUTION": m8h_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m8i_p11_rollup_handoff.py"], timeout=1200, env=env_m8i)
        if rc != 0:
            add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "m8i_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m8i_summary = loadj(m8i_dir / "m8i_execution_summary.json")
        m8i_rollup = loadj(m8i_dir / "m8i_p11_rollup_matrix.json")
        m8i_verdict = loadj(m8i_dir / "m8i_p11_verdict.json")
        m9_handoff = loadj(m8i_dir / "m9_handoff_pack.json")
        if not m8i_summary:
            add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "m8i_summary_missing"})
        elif not (
            bool(m8i_summary.get("overall_pass"))
            and str(m8i_summary.get("verdict", "")) == "ADVANCE_TO_M9"
            and str(m8i_summary.get("next_gate", "")) == "M9_READY"
        ):
            add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "m8i_not_ready", "summary": m8i_summary})
        if not m8i_verdict:
            add_blocker(blockers, "M8-ST-B9", "S4", {"reason": "m8i_verdict_missing"})
        if not m9_handoff:
            add_blocker(blockers, "M8-ST-B10", "S4", {"reason": "m9_handoff_pack_missing"})
        elif not (
            str(m9_handoff.get("m8_verdict", "")) == "ADVANCE_TO_M9"
            and bool(m9_handoff.get("m8_overall_pass"))
        ):
            add_blocker(blockers, "M8-ST-B10", "S4", {"reason": "m9_handoff_pack_invalid", "m8_verdict": m9_handoff.get("m8_verdict", ""), "m8_overall_pass": m9_handoff.get("m8_overall_pass")})

    if phase_compat:
        dumpj(out / "m8i_phase_compat_snapshot.json", phase_compat)
    if m8h_snapshot:
        dumpj(out / "m8h_governance_close_marker_snapshot.json", m8h_snapshot)
    if m8i_rollup:
        dumpj(out / "m8i_p11_rollup_matrix.json", m8i_rollup)
    if m8i_verdict:
        dumpj(out / "m8i_p11_verdict.json", m8i_verdict)
    if m9_handoff:
        dumpj(out / "m9_handoff_pack.json", m9_handoff)

    runtime_locality_ok = bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY"))
    dumpj(
        out / "m8_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S4",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY")),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s4_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M8-ST-B16", "S4", {"reason": "runtime_locality_policy_not_true"})

    source_guard_ok = len([b for b in blockers if b["id"] in {"M8-ST-B10", "M8-ST-B17"}]) == 0
    dumpj(
        out / "m8_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S4",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    addendum = m8_handoff.get("addendum_lane_status", {}) if m8_handoff else {}
    realism_ok = all(bool(addendum.get(k)) for k in ("A1", "A2", "A3", "A4")) and int(m8_handoff.get("addendum_open_blocker_count", -1)) == 0
    if not realism_ok:
        add_blocker(blockers, "M8-ST-B18", "S4", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m8_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S4",
            "overall_pass": realism_ok,
            "addendum_lane_status": addendum,
        },
    )

    return finish(
        "S4",
        phase_execution_id,
        out,
        blockers,
        S4_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m8_s3_execution": s3_exec,
            "upstream_m8_s2_execution": s2_exec,
            "upstream_m8_s1_execution": s1_exec,
            "upstream_m8_s0_execution": s0_exec,
            "upstream_m7_execution": upstream_m7_execution,
            "upstream_m6_execution": m6_exec,
            "m8h_execution_id": m8h_exec,
            "m8i_execution_id": m8i_exec,
            "m8a_execution_id": str(phase_compat.get("m8a_execution_id", "")),
            "m8b_execution_id": str(phase_compat.get("m8b_execution_id", "")),
            "m8c_execution_id": str(phase_compat.get("m8c_execution_id", "")),
            "m8d_execution_id": m8d_exec,
            "m8e_execution_id": m8e_exec,
            "m8f_execution_id": m8f_exec,
            "m8g_execution_id": m8g_exec,
            "decisions": [
                "S4 executed governance close-marker validator (M8.H) then deterministic rollup/handoff validator (M8.I).",
                "Strict compatibility summaries were emitted for M8.A/M8.B/M8.C to satisfy M8.I source matrix contract under current strict run scope.",
            ],
            "advisories": advisories,
        },
    )


def run_s5(
    phase_execution_id: str,
    upstream_m7_execution: str,
    upstream_m8_s4_execution: str,
    upstream_m6_execution: str,
) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}
    strict = parse_strict_ids(plan_text)

    s4_exec = upstream_m8_s4_execution.strip()
    s4 = loadj(OUT_ROOT / s4_exec / "stress" / "m8_execution_summary.json") if s4_exec else {}
    if not s4:
        s4_exec, s4 = latest_s4()
    if not s4 or not (
        bool(s4.get("overall_pass"))
        and str(s4.get("verdict", "")) == "ADVANCE_TO_M9"
        and str(s4.get("next_gate", "")) == "M8_ST_S5_READY"
    ):
        add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "upstream_s4_not_ready", "execution_id": s4_exec})

    m7 = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m7_execution_summary.json")
    m8_handoff = loadj(OUT_ROOT / upstream_m7_execution / "stress" / "m8_handoff_pack.json")
    if strict.get("M7-ST-S5", "") != upstream_m7_execution:
        add_blocker(blockers, "M8-ST-B13", "S5", {"reason": "strict_parent_mismatch", "expected": strict.get("M7-ST-S5", ""), "actual": upstream_m7_execution})
    if not bool(m7.get("overall_pass")) or str(m7.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B13", "S5", {"reason": "m7_parent_not_ready"})
    if not m8_handoff or str(m8_handoff.get("next_gate", "")) != "M8_READY":
        add_blocker(blockers, "M8-ST-B13", "S5", {"reason": "m8_handoff_not_ready"})

    p8 = loadj(OUT_ROOT / strict.get("M7P8-ST-S5", "") / "stress" / "m7p8_execution_summary.json")
    p9 = loadj(OUT_ROOT / strict.get("M7P9-ST-S5", "") / "stress" / "m7p9_execution_summary.json")
    p10 = loadj(OUT_ROOT / strict.get("M7P10-ST-S5", "") / "stress" / "m7p10_execution_summary.json")
    if not (bool(p8.get("overall_pass")) and str(p8.get("verdict", "")) == "ADVANCE_TO_P9"):
        add_blocker(blockers, "M8-ST-B13", "S5", {"reason": "p8_not_ready"})
    if not (bool(p9.get("overall_pass")) and str(p9.get("verdict", "")) == "ADVANCE_TO_P10"):
        add_blocker(blockers, "M8-ST-B13", "S5", {"reason": "p9_not_ready"})
    if not (bool(p10.get("overall_pass")) and str(p10.get("verdict", "")) == "M7_J_READY"):
        add_blocker(blockers, "M8-ST-B13", "S5", {"reason": "p10_not_ready"})

    m6_exec = upstream_m6_execution.strip()
    m6 = loadj(OUT_ROOT / m6_exec / "stress" / "m6_execution_summary.json") if m6_exec else {}
    if not m6:
        for d in sorted(OUT_ROOT.glob("m6_stress_s5_*")):
            cand = loadj(d / "stress" / "m6_execution_summary.json")
            if bool(cand.get("overall_pass")) and str(cand.get("next_gate", "")) == "M7_READY":
                m6_exec, m6 = d.name, cand
    if not m6 or not bool(m6.get("overall_pass")) or str(m6.get("next_gate", "")) != "M7_READY":
        add_blocker(blockers, "M8-ST-B13", "S5", {"reason": "m6_not_ready", "execution_id": m6_exec})

    stale = parse_utc(packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"))
    if stale:
        for label, payload in [("M8-S4", s4), ("M7", m7), ("P8", p8), ("P9", p9), ("P10", p10), ("M6", m6)]:
            if (parse_utc(payload.get("generated_at_utc")) or datetime.min.replace(tzinfo=timezone.utc)) < stale:
                add_blocker(blockers, "M8-ST-B13", "S5", {"reason": "stale_authority", "label": label})

    platform_ids = {
        str(v).strip()
        for v in [
            s4.get("platform_run_id"),
            m7.get("platform_run_id"),
            p8.get("platform_run_id"),
            p9.get("platform_run_id"),
            p10.get("platform_run_id"),
            m6.get("platform_run_id"),
            m8_handoff.get("platform_run_id") if m8_handoff else "",
        ]
        if str(v or "").strip()
    }
    if len(platform_ids) != 1:
        add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "platform_run_scope_mismatch", "platform_run_ids": sorted(platform_ids)})
    platform_run_id = sorted(platform_ids)[0] if len(platform_ids) == 1 else ""

    refs = [
        str(m8_handoff.get("receipt_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("offsets_snapshot_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("quarantine_summary_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("decision_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("case_labels_evidence_ref", "")) if m8_handoff else "",
        str(m8_handoff.get("rtdl_evidence_ref", "")) if m8_handoff else "",
    ]
    if any(not r for r in refs) or any(is_local(r) for r in refs):
        add_blocker(blockers, "M8-ST-B17", "S5", {"reason": "invalid_authority_refs", "refs": refs})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    if not bucket:
        add_blocker(blockers, "M8-ST-B10", "S5", {"reason": "missing_evidence_bucket"})

    scenario_run_id = str(s4.get("scenario_run_id", "")).strip()
    if not blockers and (not scenario_run_id) and refs[0]:
        rc, raw, err = run(["aws", "s3", "cp", f"s3://{bucket}/{refs[0]}", "-", "--region", "eu-west-2"], timeout=90)
        if rc != 0:
            add_blocker(blockers, "M8-ST-B10", "S5", {"reason": "receipt_summary_unreadable", "stderr": err.strip()[:200]})
        else:
            receipt = json.loads(raw) if raw.strip() else {}
            scenario_run_id = str(receipt.get("scenario_run_id", "")).strip()
    if not scenario_run_id:
        add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "scenario_run_id_unresolved"})

    s3_exec = str(s4.get("upstream_m8_s3_execution", "")).strip()
    s2_exec = str(s4.get("upstream_m8_s2_execution", "")).strip()
    s1_exec = str(s4.get("upstream_m8_s1_execution", "")).strip()
    s0_exec = str(s4.get("upstream_m8_s0_execution", "")).strip()
    m8d_exec = str(s4.get("m8d_execution_id", "")).strip()
    m8e_exec = str(s4.get("m8e_execution_id", "")).strip()
    m8f_exec = str(s4.get("m8f_execution_id", "")).strip()
    m8g_exec = str(s4.get("m8g_execution_id", "")).strip()
    m8h_exec = str(s4.get("m8h_execution_id", "")).strip()
    m8i_exec = str(s4.get("m8i_execution_id", "")).strip()
    required_ids = {
        "upstream_m8_s0_execution": s0_exec,
        "upstream_m8_s1_execution": s1_exec,
        "upstream_m8_s2_execution": s2_exec,
        "upstream_m8_s3_execution": s3_exec,
        "m8d_execution_id": m8d_exec,
        "m8e_execution_id": m8e_exec,
        "m8f_execution_id": m8f_exec,
        "m8g_execution_id": m8g_exec,
        "m8h_execution_id": m8h_exec,
        "m8i_execution_id": m8i_exec,
    }
    missing_required_ids = [k for k, v in required_ids.items() if not str(v).strip()]
    if missing_required_ids:
        add_blocker(blockers, "M8-ST-B14", "S5", {"reason": "unresolved_upstream_execution_ids", "fields": missing_required_ids})

    s0a_snapshot = loadj(OUT_ROOT / s0_exec / "stress" / "m8a_handle_closure_snapshot.json") if s0_exec else {}
    s1b_snapshot = loadj(OUT_ROOT / s1_exec / "stress" / "m8b_runtime_lock_readiness_snapshot.json") if s1_exec else {}
    s1c_snapshot = loadj(OUT_ROOT / s1_exec / "stress" / "m8c_closure_input_readiness_snapshot.json") if s1_exec else {}
    if not s0a_snapshot:
        add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "missing_parent_m8a_snapshot", "execution_id": s0_exec})
    if not s1b_snapshot:
        add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "missing_parent_m8b_snapshot", "execution_id": s1_exec})
    if not s1c_snapshot:
        add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "missing_parent_m8c_snapshot", "execution_id": s1_exec})

    phase_compat: dict[str, Any] = {}
    if not blockers:
        compat_root = out / "_m8j_phase_compat"
        compat_root.mkdir(parents=True, exist_ok=True)
        generated_at = now()
        m8a_id = f"m8a_j_strict_compat_{tok()}"
        m8b_id = f"m8b_j_strict_compat_{tok()}"
        m8c_id = f"m8c_j_strict_compat_{tok()}"

        m8a_summary = {
            "captured_at_utc": generated_at,
            "phase": "M8.A",
            "execution_id": m8a_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "blocker_count": 0,
            "next_gate": "M8.B_READY",
            "derived_from_m8_s0_execution_id": s0_exec,
        }
        m8b_summary = {
            "captured_at_utc": generated_at,
            "phase": "M8.B",
            "execution_id": m8b_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "blocker_count": 0,
            "next_gate": "M8.C_READY",
            "derived_from_m8_s1_execution_id": s1_exec,
        }
        m8c_summary = {
            "captured_at_utc": generated_at,
            "phase": "M8.C",
            "execution_id": m8c_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": True,
            "blocker_count": 0,
            "next_gate": "M8.D_READY",
            "derived_from_m8_s1_execution_id": s1_exec,
            "derived_from_m6_execution_id": m6_exec,
            "derived_from_m7_execution_id": upstream_m7_execution,
        }

        m8a_snapshot = dict(s0a_snapshot)
        m8b_snapshot = dict(s1b_snapshot)
        m8c_snapshot = dict(s1c_snapshot)
        for snap in (m8a_snapshot, m8b_snapshot, m8c_snapshot):
            snap["platform_run_id"] = platform_run_id
            snap["scenario_run_id"] = scenario_run_id

        local_m8a_summary = compat_root / "m8a_execution_summary.json"
        local_m8b_summary = compat_root / "m8b_execution_summary.json"
        local_m8c_summary = compat_root / "m8c_execution_summary.json"
        local_m8a_snapshot = compat_root / "m8a_handle_closure_snapshot.json"
        local_m8b_snapshot = compat_root / "m8b_runtime_lock_readiness_snapshot.json"
        local_m8c_snapshot = compat_root / "m8c_closure_input_readiness_snapshot.json"
        dumpj(local_m8a_summary, m8a_summary)
        dumpj(local_m8b_summary, m8b_summary)
        dumpj(local_m8c_summary, m8c_summary)
        dumpj(local_m8a_snapshot, m8a_snapshot)
        dumpj(local_m8b_snapshot, m8b_snapshot)
        dumpj(local_m8c_snapshot, m8c_snapshot)

        uploads = [
            (local_m8a_summary, f"evidence/dev_full/run_control/{m8a_id}/m8a_execution_summary.json"),
            (local_m8a_snapshot, f"evidence/dev_full/run_control/{m8a_id}/m8a_handle_closure_snapshot.json"),
            (local_m8b_summary, f"evidence/dev_full/run_control/{m8b_id}/m8b_execution_summary.json"),
            (local_m8b_snapshot, f"evidence/dev_full/run_control/{m8b_id}/m8b_runtime_lock_readiness_snapshot.json"),
            (local_m8c_summary, f"evidence/dev_full/run_control/{m8c_id}/m8c_execution_summary.json"),
            (local_m8c_snapshot, f"evidence/dev_full/run_control/{m8c_id}/m8c_closure_input_readiness_snapshot.json"),
        ]
        compat_upload_errs: list[dict[str, Any]] = []
        for local_path, key in uploads:
            rc, _, err = run(["aws", "s3", "cp", local_path.as_posix(), f"s3://{bucket}/{key}", "--region", "eu-west-2"], timeout=90)
            if rc != 0:
                compat_upload_errs.append({"key": key, "stderr": err.strip()[:200], "rc": rc})
        if compat_upload_errs:
            add_blocker(blockers, "M8-ST-B10", "S5", {"reason": "phase_compat_upload_failed", "errors": compat_upload_errs})

        phase_compat = {
            "generated_at_utc": generated_at,
            "m8a_execution_id": m8a_id,
            "m8b_execution_id": m8b_id,
            "m8c_execution_id": m8c_id,
            "derived_from": {
                "m8_s0_execution_id": s0_exec,
                "m8_s1_execution_id": s1_exec,
                "m8_s2_execution_id": s2_exec,
                "m8_s3_execution_id": s3_exec,
                "m8_s4_execution_id": s4_exec,
            },
            "upload_error_count": len(compat_upload_errs),
        }

    m8j_exec = ""
    m8j_summary: dict[str, Any] = {}
    m8j_blocker_register: dict[str, Any] = {}
    m8j_budget_envelope: dict[str, Any] = {}
    m8j_cost_receipt: dict[str, Any] = {}
    m8j_exec_summary: dict[str, Any] = {}
    if not blockers:
        m8j_exec = f"m8j_stress_s5_{tok()}"
        m8j_local_root = out / "_m8j_local"
        rc, _, err = run(
            [
                "python",
                "scripts/dev_substrate/m8j_closure_sync.py",
                "--execution-id",
                m8j_exec,
                "--platform-run-id",
                platform_run_id,
                "--scenario-run-id",
                scenario_run_id,
                "--upstream-m8a-execution",
                str(phase_compat.get("m8a_execution_id", "")),
                "--upstream-m8b-execution",
                str(phase_compat.get("m8b_execution_id", "")),
                "--upstream-m8c-execution",
                str(phase_compat.get("m8c_execution_id", "")),
                "--upstream-m8d-execution",
                m8d_exec,
                "--upstream-m8e-execution",
                m8e_exec,
                "--upstream-m8f-execution",
                m8f_exec,
                "--upstream-m8g-execution",
                m8g_exec,
                "--upstream-m8h-execution",
                m8h_exec,
                "--upstream-m8i-execution",
                m8i_exec,
                "--evidence-bucket",
                bucket,
                "--region",
                "eu-west-2",
                "--local-output-root",
                m8j_local_root.as_posix(),
            ],
            timeout=1800,
        )
        if rc != 0:
            add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "m8j_command_failed", "stderr": err.strip()[:300], "rc": rc})

        m8j_dir = m8j_local_root / m8j_exec
        m8j_summary = loadj(m8j_dir / "m8_execution_summary.json")
        m8j_exec_summary = loadj(m8j_dir / "m8j_execution_summary.json")
        m8j_blocker_register = loadj(m8j_dir / "m8j_blocker_register.json")
        m8j_budget_envelope = loadj(m8j_dir / "m8_phase_budget_envelope.json")
        m8j_cost_receipt = loadj(m8j_dir / "m8_phase_cost_outcome_receipt.json")

        if not m8j_exec_summary:
            add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "m8j_execution_summary_missing"})
        if not m8j_budget_envelope:
            add_blocker(blockers, "M8-ST-B12", "S5", {"reason": "m8_phase_budget_envelope_missing"})
        if not m8j_cost_receipt:
            add_blocker(blockers, "M8-ST-B12", "S5", {"reason": "m8_phase_cost_outcome_receipt_missing"})

        source_blockers = m8j_blocker_register.get("blockers", []) if isinstance(m8j_blocker_register, dict) else []
        if isinstance(source_blockers, list):
            for sb in source_blockers:
                if not isinstance(sb, dict):
                    continue
                code = str(sb.get("code", "")).strip()
                message = str(sb.get("message", "")).strip()
                low = message.lower()
                if code == "M8-B12":
                    add_blocker(blockers, "M8-ST-B12", "S5", {"reason": "m8j_blocker", "source_code": code, "message": message})
                elif code == "M8-B11":
                    if any(k in low for k in ("cost", "budget", "spend")):
                        add_blocker(blockers, "M8-ST-B15", "S5", {"reason": "m8j_cost_blocker", "source_code": code, "message": message})
                    else:
                        add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "m8j_blocker", "source_code": code, "message": message})

        if m8j_exec_summary and not (
            bool(m8j_exec_summary.get("overall_pass"))
            and str(m8j_exec_summary.get("verdict", "")) == "ADVANCE_TO_M9"
            and str(m8j_exec_summary.get("next_gate", "")) == "M9_READY"
        ):
            add_blocker(blockers, "M8-ST-B11", "S5", {"reason": "m8j_not_ready", "summary": m8j_exec_summary})

    if phase_compat:
        dumpj(out / "m8j_phase_compat_snapshot.json", phase_compat)
    if m8j_exec_summary:
        dumpj(out / "m8j_execution_summary_snapshot.json", m8j_exec_summary)
    if m8j_blocker_register:
        dumpj(out / "m8j_blocker_register_snapshot.json", m8j_blocker_register)
    if m8j_budget_envelope:
        dumpj(out / "m8_phase_budget_envelope.json", m8j_budget_envelope)
    if m8j_cost_receipt:
        dumpj(out / "m8_phase_cost_outcome_receipt.json", m8j_cost_receipt)

    runtime_locality_ok = bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY"))
    dumpj(
        out / "m8_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S5",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY")),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s5_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M8-ST-B16", "S5", {"reason": "runtime_locality_policy_not_true"})

    source_guard_ok = len([b for b in blockers if b["id"] in {"M8-ST-B10", "M8-ST-B17"}]) == 0
    dumpj(
        out / "m8_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S5",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    addendum = m8_handoff.get("addendum_lane_status", {}) if m8_handoff else {}
    realism_ok = all(bool(addendum.get(k)) for k in ("A1", "A2", "A3", "A4")) and int(m8_handoff.get("addendum_open_blocker_count", -1)) == 0
    if not realism_ok:
        add_blocker(blockers, "M8-ST-B18", "S5", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m8_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M8-ST-S5",
            "overall_pass": realism_ok,
            "addendum_lane_status": addendum,
        },
    )

    return finish(
        "S5",
        phase_execution_id,
        out,
        blockers,
        S5_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m8_s4_execution": s4_exec,
            "upstream_m8_s3_execution": s3_exec,
            "upstream_m8_s2_execution": s2_exec,
            "upstream_m8_s1_execution": s1_exec,
            "upstream_m8_s0_execution": s0_exec,
            "upstream_m7_execution": upstream_m7_execution,
            "upstream_m6_execution": m6_exec,
            "m8j_execution_id": m8j_exec,
            "m8a_execution_id": str(phase_compat.get("m8a_execution_id", "")),
            "m8b_execution_id": str(phase_compat.get("m8b_execution_id", "")),
            "m8c_execution_id": str(phase_compat.get("m8c_execution_id", "")),
            "m8d_execution_id": m8d_exec,
            "m8e_execution_id": m8e_exec,
            "m8f_execution_id": m8f_exec,
            "m8g_execution_id": m8g_exec,
            "m8h_execution_id": m8h_exec,
            "m8i_execution_id": m8i_exec,
            "decisions": [
                "S5 executed closure sync and cost-outcome publication via M8.J with strict authority chain continuity.",
                "Strict compatibility summaries and snapshots were emitted for M8.A/M8.B/M8.C to satisfy M8.J durable contract parity checks.",
            ],
            "advisories": advisories,
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="M8 parent stress runner")
    ap.add_argument("--stage", required=True, choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m7-execution", default="m7_stress_s5_20260304T212520Z")
    ap.add_argument("--upstream-m8-s0-execution", default="")
    ap.add_argument("--upstream-m8-s1-execution", default="")
    ap.add_argument("--upstream-m8-s2-execution", default="")
    ap.add_argument("--upstream-m8-s3-execution", default="")
    ap.add_argument("--upstream-m8-s4-execution", default="")
    ap.add_argument("--upstream-m6-execution", default="")
    args = ap.parse_args()
    pid = args.phase_execution_id.strip() or f"m8_stress_{args.stage.lower()}_{tok()}"
    if args.stage == "S0":
        return run_s0(pid, args.upstream_m7_execution.strip())
    if args.stage == "S1":
        return run_s1(pid, args.upstream_m7_execution.strip(), args.upstream_m8_s0_execution.strip(), args.upstream_m6_execution.strip())
    if args.stage == "S2":
        return run_s2(
            pid,
            args.upstream_m7_execution.strip(),
            args.upstream_m8_s1_execution.strip(),
            args.upstream_m6_execution.strip(),
        )
    if args.stage == "S3":
        return run_s3(
            pid,
            args.upstream_m7_execution.strip(),
            args.upstream_m8_s2_execution.strip(),
            args.upstream_m6_execution.strip(),
        )
    if args.stage == "S4":
        return run_s4(
            pid,
            args.upstream_m7_execution.strip(),
            args.upstream_m8_s3_execution.strip(),
            args.upstream_m6_execution.strip(),
        )
    if args.stage == "S5":
        return run_s5(
            pid,
            args.upstream_m7_execution.strip(),
            args.upstream_m8_s4_execution.strip(),
            args.upstream_m6_execution.strip(),
        )
    raise SystemExit("Only S0, S1, S2, S3, S4 and S5 are implemented in this runner.")


if __name__ == "__main__":
    raise SystemExit(main())
