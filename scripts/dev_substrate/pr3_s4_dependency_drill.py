#!/usr/bin/env python3
"""Materialize PR3-S4 dependency degrade drill evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def run(cmd: list[str], *, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def snap_component(snapshot: dict[str, Any], component: str) -> dict[str, Any]:
    return dict((((snapshot.get("components") or {}).get(component) or {}).get("summary")) or {})


def snapshot_component_payload(snapshot: dict[str, Any], component: str) -> dict[str, Any]:
    return dict(((snapshot.get("components") or {}).get(component)) or {})


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_reason_set(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def replay_advisory_only(summary: dict[str, Any], *, max_checkpoint_seconds: float) -> bool:
    reasons = normalize_reason_set(summary.get("health_reasons"))
    checkpoint_age = to_float(summary.get("checkpoint_age_seconds"))
    return (
        str(summary.get("health_state") or "").upper() == "RED"
        and reasons == {"WATERMARK_TOO_OLD"}
        and checkpoint_age is not None
        and checkpoint_age <= max_checkpoint_seconds
    )


def dl_signals_ok(summary: dict[str, Any]) -> bool:
    required_signal_states = dict(summary.get("required_signal_states") or {})
    required_keys = ("eb_consumer_lag", "ieg_health", "ofp_health")
    return all(str(required_signal_states.get(key) or "").strip().upper() == "OK" for key in required_keys)


def checkpoint_updated_at(component_payload: dict[str, Any]) -> datetime | None:
    checkpoints = {}
    for key in ("metrics_payload", "health_payload"):
        payload = dict(component_payload.get(key) or {})
        candidate = dict(payload.get("checkpoints") or {})
        if candidate:
            checkpoints = candidate
            break
    updated_at = str(checkpoints.get("updated_at_utc") or "").strip()
    if not updated_at:
        return None
    try:
        return parse_utc(updated_at)
    except ValueError:
        return None


def snapshot_component(
    *,
    pr3_execution_id: str,
    state_id: str,
    snapshot_label: str,
    namespace: str,
    case_labels_namespace: str,
    platform_run_id: str,
) -> dict[str, Any]:
    run(
        [
            "python",
            "scripts/dev_substrate/pr3_runtime_surface_snapshot.py",
            "--pr3-execution-id",
            pr3_execution_id,
            "--state-id",
            state_id,
            "--snapshot-label",
            snapshot_label,
            "--namespace",
            namespace,
            "--case-labels-namespace",
            case_labels_namespace,
            "--platform-run-id",
            platform_run_id,
        ],
        timeout=300,
    )
    root = Path("runs/dev_substrate/dev_full/road_to_prod/run_control") / pr3_execution_id
    return load_json(root / f"g3a_{str(state_id).strip().lower()}_component_snapshot_{snapshot_label}.json")


def _delta(end: dict[str, Any], start: dict[str, Any], field: str) -> float:
    return float((to_float(end.get(field)) or 0.0) - (to_float(start.get(field)) or 0.0))


def operational_recovery_ok(
    *,
    baseline_dl: dict[str, Any],
    pre_ieg: dict[str, Any],
    pre_ofp: dict[str, Any],
    pre_dl: dict[str, Any],
    recovered_ieg_payload: dict[str, Any],
    recovered_ofp_payload: dict[str, Any],
    recovered_ieg: dict[str, Any],
    recovered_ofp: dict[str, Any],
    recovered_dl: dict[str, Any],
    recover_started_at: datetime,
) -> tuple[bool, list[str], list[str]]:
    blockers: list[str] = []
    advisories: list[str] = []

    if not recovered_ieg or recovered_ieg.get("health_state") in (None, ""):
        blockers.append("IEG_SURFACE_UNREADABLE")
    else:
        ieg_reasons = normalize_reason_set(recovered_ieg.get("health_reasons"))
        ieg_delta = _delta(recovered_ieg, pre_ieg, "events_seen")
        ieg_checkpoint_updated_at = checkpoint_updated_at(recovered_ieg_payload)
        if ieg_checkpoint_updated_at is None:
            blockers.append("IEG_CHECKPOINT_UNREADABLE")
        elif ieg_checkpoint_updated_at < recover_started_at:
            blockers.append("IEG_CHECKPOINT_NOT_ADVANCED_IN_RECOVERY_WINDOW")
        elif ieg_reasons - {"WATERMARK_TOO_OLD"}:
            blockers.append("IEG_NOT_RECOVERED_TO_BASELINE")
        elif ieg_delta <= 0:
            blockers.append("IEG_NO_FRESH_ACTIVITY")
        elif (to_float(recovered_ieg.get("apply_failure_count")) or 0.0) > 0.0 or (to_float(recovered_ieg.get("backpressure_hits")) or 0.0) > 0.0:
            blockers.append("IEG_RECOVERY_FAILURES_PRESENT")

    if not recovered_ofp or recovered_ofp.get("health_state") in (None, ""):
        blockers.append("OFP_SURFACE_UNREADABLE")
    else:
        ofp_reasons = normalize_reason_set(recovered_ofp.get("health_reasons"))
        ofp_events_delta = _delta(recovered_ofp, pre_ofp, "events_applied")
        ofp_missing_delta = _delta(recovered_ofp, pre_ofp, "missing_features")
        ofp_checkpoint_updated_at = checkpoint_updated_at(recovered_ofp_payload)
        if ofp_checkpoint_updated_at is None:
            blockers.append("OFP_CHECKPOINT_UNREADABLE")
        elif ofp_checkpoint_updated_at < recover_started_at:
            blockers.append("OFP_CHECKPOINT_NOT_ADVANCED_IN_RECOVERY_WINDOW")
        elif ofp_reasons - {"WATERMARK_TOO_OLD", "MISSING_FEATURES_RED"}:
            blockers.append("OFP_NOT_RECOVERED_TO_BASELINE")
        elif ofp_events_delta <= 0:
            blockers.append("OFP_NO_FRESH_ACTIVITY")
        elif ofp_missing_delta > 0:
            blockers.append("OFP_SEMANTIC_MISSING_FEATURES_INCREASED")
        elif (to_float(recovered_ofp.get("snapshot_failures")) or 0.0) > 0.0:
            blockers.append("OFP_SNAPSHOT_FAILURES_PRESENT")
        elif "MISSING_FEATURES_RED" in ofp_reasons:
            advisories.append("OFP_MISSING_FEATURES_RED_ADVISORY")

    if not recovered_dl or recovered_dl.get("health_state") in (None, ""):
        blockers.append("DL_SURFACE_UNREADABLE")
    else:
        recovered_dl_mode = str(recovered_dl.get("decision_mode") or "").upper()
        if not dl_signals_ok(recovered_dl):
            blockers.append("DL_REQUIRED_SIGNALS_NOT_OK")
        elif _delta(recovered_dl, pre_dl, "posture_seq") <= 0:
            blockers.append("DL_POSTURE_NOT_ADVANCING")
        elif recovered_dl_mode in {"", "FAIL_CLOSED"}:
            blockers.append("DL_DECISION_MODE_NOT_OPERATIONAL")
        elif recovered_dl_mode != "NORMAL":
            advisories.append(f"DL_DECISION_MODE_RECOVERED_NON_NORMAL:{recovered_dl_mode}")

    return len(blockers) == 0, blockers, advisories


def warm_gate_advisory_only(warm_gate_payload: dict[str, Any]) -> bool:
    blocker_ids = {str(item).strip() for item in list(warm_gate_payload.get("blocker_ids") or []) if str(item).strip()}
    if not blocker_ids:
        return False
    allowed = {
        "PR3.S4.WARM.B12A_DL_BOOTSTRAP_PENDING",
        "PR3.S4.WARM.B12F_IEG_NOT_OPERATIONALLY_READY",
        "PR3.S4.WARM.B12K_OFP_NOT_OPERATIONALLY_READY",
    }
    return blocker_ids.issubset(allowed)


def dispatch_remote_pulse(
    *,
    pr3_execution_id: str,
    state_id: str,
    platform_run_id: str,
    scenario_run_id: str,
    manifest: dict[str, Any],
    artifact_prefix: str,
    window_label: str,
    blocker_prefix: str,
    duration_seconds: int,
    expected_window_eps: float,
    target_request_rate_eps: float,
    metric_settle_seconds: int,
) -> tuple[dict[str, Any], list[str]]:
    pulse_prefix = f"{artifact_prefix}_{window_label}"
    root = Path("runs/dev_substrate/dev_full/road_to_prod/run_control") / pr3_execution_id
    summary_path = root / f"{pulse_prefix}_wsp_runtime_summary.json"
    checkpoint_attempt_id = str((((manifest.get("campaign") or {}).get("checkpoint_attempt_id")) or "")).strip()
    lane_count = int((manifest.get("lane_count") or ((manifest.get("campaign") or {}).get("lane_count")) or 1))
    cmd = [
        "python",
        "scripts/dev_substrate/pr3_wsp_replay_dispatch.py",
        "--pr3-execution-id",
        pr3_execution_id,
        "--state-id",
        state_id,
        "--window-label",
        window_label,
        "--artifact-prefix",
        pulse_prefix,
        "--blocker-prefix",
        blocker_prefix,
        "--platform-run-id",
        platform_run_id,
        "--scenario-run-id",
        scenario_run_id,
        "--allow-runtime-identity-reuse",
        "--oracle-root",
        str((((manifest.get("oracle") or {}).get("oracle_root")) or "")).strip(),
        "--oracle-engine-run-root",
        str((((manifest.get("oracle") or {}).get("oracle_engine_run_root")) or "")).strip(),
        "--scenario-id",
        str((((manifest.get("identity") or {}).get("scenario_id")) or "baseline_v1")).strip(),
        "--traffic-output-ids",
        ",".join((((manifest.get("campaign") or {}).get("traffic_output_ids")) or ["s3_event_stream_with_fraud_6B"])),
        "--context-output-ids",
        ",".join((((manifest.get("campaign") or {}).get("context_output_ids")) or ["arrival_events_5B", "s1_arrival_entities_6B", "s3_flow_anchor_with_fraud_6B"])),
        "--stream-speedup",
        str((((manifest.get("campaign") or {}).get("stream_speedup")) or 51.2)),
        "--lane-count",
        str(max(1, lane_count)),
        "--duration-seconds",
        str(max(1, int(duration_seconds))),
        "--warmup-seconds",
        "0",
        "--early-cutoff-seconds",
        str(max(1, int(duration_seconds))),
        "--early-cutoff-floor-ratio",
        "0.5",
        "--expected-window-eps",
        str(expected_window_eps),
        "--target-request-rate-eps",
        str(target_request_rate_eps),
        "--metric-settle-seconds",
        str(max(0, int(metric_settle_seconds))),
        "--output-concurrency",
        "2",
        "--ig-push-concurrency",
        "2",
        "--http-pool-maxsize",
        "128",
    ]
    if checkpoint_attempt_id:
        cmd.extend(["--checkpoint-attempt-id", checkpoint_attempt_id])
    proc = run(cmd, timeout=1800, check=False)
    summary = load_json(summary_path) if summary_path.exists() else {}
    blockers: list[str] = []
    if proc.returncode != 0:
        blockers.append(f"{window_label.upper()}_EXECUTION_FAILED")
    if not summary or not summary.get("verdict"):
        blockers.append(f"{window_label.upper()}_SUMMARY_MISSING")
    elif int(summary.get("open_blockers", 0) or 0) > 0:
        blockers.append(f"{window_label.upper()}_BLOCKED")
    return summary, blockers


def main() -> None:
    ap = argparse.ArgumentParser(description="PR3-S4 dependency degrade drill")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S4")
    ap.add_argument("--artifact-prefix", default="g3a_correctness")
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--case-labels-namespace", default="")
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--profile-path", required=True)
    ap.add_argument("--deployment", default="fp-pr3-ofp")
    ap.add_argument("--recovery-timeout-seconds", type=int, default=300)
    ap.add_argument("--settle-seconds", type=int, default=30)
    ap.add_argument("--max-fresh-checkpoint-seconds", type=float, default=120.0)
    ap.add_argument("--post-refresh-settle-seconds", type=int, default=5)
    ap.add_argument("--prewarm-duration-seconds", type=int, default=0)
    ap.add_argument("--prewarm-expected-eps", type=float, default=6.0)
    ap.add_argument("--prewarm-target-eps", type=float, default=8.0)
    ap.add_argument("--prewarm-settle-seconds", type=int, default=5)
    ap.add_argument("--refresh-duration-seconds", type=int, default=20)
    ap.add_argument("--refresh-expected-eps", type=float, default=12.0)
    ap.add_argument("--refresh-target-eps", type=float, default=15.0)
    ap.add_argument("--refresh-settle-seconds", type=int, default=10)
    ap.add_argument("--run-warm-gate", action="store_true")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    manifest = load_json(root / f"{str(args.artifact_prefix).strip()}_wsp_runtime_manifest.json")
    platform_run_id = str(args.platform_run_id).strip()
    scenario_run_id = str((((manifest.get("identity") or {}).get("scenario_run_id")) or "")).strip()
    baseline_snapshot = load_json(root / "g3a_s4_component_snapshot_post.json")
    pre_snapshot = snapshot_component(
        pr3_execution_id=args.pr3_execution_id,
        state_id=args.state_id,
        snapshot_label="dependency_pre",
        namespace=args.namespace,
        case_labels_namespace=str(args.case_labels_namespace or args.namespace).strip(),
        platform_run_id=platform_run_id,
    )

    drill_started_utc = now_utc()
    run(["kubectl", "scale", f"deployment/{args.deployment}", "-n", args.namespace, "--replicas=0"], timeout=120)
    time.sleep(max(10, int(args.settle_seconds)))
    degrade_snapshot = snapshot_component(
        pr3_execution_id=args.pr3_execution_id,
        state_id=args.state_id,
        snapshot_label="dependency_degrade",
        namespace=args.namespace,
        case_labels_namespace=str(args.case_labels_namespace or args.namespace).strip(),
        platform_run_id=platform_run_id,
    )

    recover_started_utc = now_utc()
    run(["kubectl", "scale", f"deployment/{args.deployment}", "-n", args.namespace, "--replicas=1"], timeout=120)
    run(
        ["kubectl", "rollout", "status", f"deployment/{args.deployment}", "-n", args.namespace, f"--timeout={args.recovery_timeout_seconds}s"],
        timeout=args.recovery_timeout_seconds + 30,
    )
    prewarm_summary: dict[str, Any] = {}
    prewarm_blockers: list[str] = []
    if args.prewarm_duration_seconds > 0:
        prewarm_summary, prewarm_blockers = dispatch_remote_pulse(
            pr3_execution_id=args.pr3_execution_id,
            state_id=args.state_id,
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            manifest=manifest,
            artifact_prefix=str(args.artifact_prefix).strip(),
            window_label="dependency_prewarm",
            blocker_prefix=f"PR3.{args.state_id}.DEPENDENCY_PREWARM",
            duration_seconds=args.prewarm_duration_seconds,
            expected_window_eps=args.prewarm_expected_eps,
            target_request_rate_eps=args.prewarm_target_eps,
            metric_settle_seconds=args.prewarm_settle_seconds,
        )
    if args.post_refresh_settle_seconds > 0:
        time.sleep(args.post_refresh_settle_seconds)
    refresh_summary, refresh_blockers = dispatch_remote_pulse(
        pr3_execution_id=args.pr3_execution_id,
        state_id=args.state_id,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        manifest=manifest,
        artifact_prefix=str(args.artifact_prefix).strip(),
        window_label="dependency_refresh",
        blocker_prefix=f"PR3.{args.state_id}.DEPENDENCY_REFRESH",
        duration_seconds=args.refresh_duration_seconds,
        expected_window_eps=args.refresh_expected_eps,
        target_request_rate_eps=args.refresh_target_eps,
        metric_settle_seconds=args.refresh_settle_seconds,
    )
    if args.post_refresh_settle_seconds > 0:
        time.sleep(args.post_refresh_settle_seconds)
    recovered_immediate_snapshot = snapshot_component(
        pr3_execution_id=args.pr3_execution_id,
        state_id=args.state_id,
        snapshot_label="dependency_recovered_immediate",
        namespace=args.namespace,
        case_labels_namespace=str(args.case_labels_namespace or args.namespace).strip(),
        platform_run_id=platform_run_id,
    )
    if args.run_warm_gate:
        warm_gate_proc = run(
            [
                "python",
                "scripts/dev_substrate/pr3_runtime_warm_gate.py",
                "--pr3-execution-id",
                args.pr3_execution_id,
                "--state-id",
                args.state_id,
                "--namespace",
                args.namespace,
                "--case-labels-namespace",
                str(args.case_labels_namespace or args.namespace).strip(),
                "--platform-run-id",
                platform_run_id,
                "--profile-path",
                args.profile_path,
                "--settle-seconds",
                str(args.settle_seconds),
            ],
            timeout=600,
            check=False,
        )
        recovered_snapshot = snapshot_component(
            pr3_execution_id=args.pr3_execution_id,
            state_id=args.state_id,
            snapshot_label="dependency_recovered",
            namespace=args.namespace,
            case_labels_namespace=str(args.case_labels_namespace or args.namespace).strip(),
            platform_run_id=platform_run_id,
        )
    else:
        warm_gate_proc = subprocess.CompletedProcess(args=["warm_gate_skipped"], returncode=0, stdout="", stderr="")
        recovered_snapshot = recovered_immediate_snapshot

    degrade_ofp = snap_component(degrade_snapshot, "ofp")
    degrade_dl = snap_component(degrade_snapshot, "dl")
    baseline_dl = snap_component(baseline_snapshot, "dl")
    pre_ieg = snap_component(pre_snapshot, "ieg")
    pre_ofp = snap_component(pre_snapshot, "ofp")
    pre_dl = snap_component(pre_snapshot, "dl")
    recovered_ieg_payload = snapshot_component_payload(recovered_immediate_snapshot, "ieg")
    recovered_ofp_payload = snapshot_component_payload(recovered_immediate_snapshot, "ofp")
    recovered_ieg = snap_component(recovered_immediate_snapshot, "ieg")
    recovered_ofp = snap_component(recovered_immediate_snapshot, "ofp")
    recovered_dl = snap_component(recovered_immediate_snapshot, "dl")
    recovered_snapshot_generated_at = str(recovered_immediate_snapshot.get("generated_at_utc") or now_utc())
    recovery_seconds = (parse_utc(recovered_snapshot_generated_at) - parse_utc(recover_started_utc)).total_seconds()
    warm_gate_payload: dict[str, Any] = {}
    try:
        warm_gate_payload = json.loads(warm_gate_proc.stdout) if warm_gate_proc.stdout.strip() else {}
    except json.JSONDecodeError:
        warm_gate_payload = {}

    degrade_detected = (
        str(degrade_ofp.get("health_state") or "").upper() in {"RED", "FAILED", "UNHEALTHY", "UNKNOWN"}
        or bool(degrade_ofp.get("__missing__"))
        or str(degrade_dl.get("decision_mode") or "").upper() in {"FAIL_CLOSED", "DEGRADE"}
        or str(degrade_dl.get("health_state") or "").upper() in {"RED", "FAILED", "UNHEALTHY", "UNKNOWN"}
    )
    recovered_ok, recovery_blockers, recovery_advisories = operational_recovery_ok(
        baseline_dl=baseline_dl,
        pre_ieg=pre_ieg,
        pre_ofp=pre_ofp,
        pre_dl=pre_dl,
        recovered_ieg_payload=recovered_ieg_payload,
        recovered_ofp_payload=recovered_ofp_payload,
        recovered_ieg=recovered_ieg,
        recovered_ofp=recovered_ofp,
        recovered_dl=recovered_dl,
        recover_started_at=parse_utc(recover_started_utc),
    )
    drill_blockers: list[str] = []
    if not degrade_detected:
        drill_blockers.append("PR3.S4.B26A_DEPENDENCY_DEGRADE_NOT_VISIBLE")
    drill_blockers.extend(f"PR3.S4.B26B_{item}" for item in prewarm_blockers)
    drill_blockers.extend(f"PR3.S4.B26C_{item}" for item in refresh_blockers)
    if recovery_seconds > float(args.recovery_timeout_seconds):
        drill_blockers.append("PR3.S4.B26D_RECOVERY_TIMEOUT")
    drill_blockers.extend(f"PR3.S4.B26E_{item}" for item in recovery_blockers)
    warm_gate_is_advisory = warm_gate_advisory_only(warm_gate_payload)
    if warm_gate_proc.returncode != 0 and not warm_gate_is_advisory:
        drill_blockers.append("PR3.S4.B26F_WARM_GATE_RED")

    overall_pass = (
        degrade_detected
        and recovered_ok
        and recovery_seconds <= float(args.recovery_timeout_seconds)
        and not prewarm_blockers
        and not refresh_blockers
        and (warm_gate_proc.returncode == 0 or warm_gate_is_advisory)
    )

    payload = {
        "drill_id": "dependency_degrade",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "scenario": f"Scale {args.deployment} to zero after bounded correctness, verify degrade is visible, restore and recover within bound.",
        "expected_behavior": "Dependency loss becomes visible on runtime surfaces and the lane recovers cleanly after restore.",
        "observed_outcome": {
            "degrade_started_utc": drill_started_utc,
            "recover_started_utc": recover_started_utc,
            "recovery_seconds": recovery_seconds,
            "recovered_snapshot_generated_at_utc": recovered_snapshot_generated_at,
            "dependency_component": args.deployment,
            "degrade_ofp": degrade_ofp,
            "degrade_dl": degrade_dl,
            "baseline_dl": baseline_dl,
            "pre_ieg": pre_ieg,
            "pre_ofp": pre_ofp,
            "pre_dl": pre_dl,
            "recovered_ieg_payload": recovered_ieg_payload,
            "recovered_ofp_payload": recovered_ofp_payload,
            "recovered_ieg": recovered_ieg,
            "recovered_ofp": recovered_ofp,
            "recovered_dl": recovered_dl,
            "recovered_final_ieg": snap_component(recovered_snapshot, "ieg"),
            "recovered_final_ofp": snap_component(recovered_snapshot, "ofp"),
            "recovered_final_dl": snap_component(recovered_snapshot, "dl"),
            "manifest_platform_run_id": str((((manifest.get("identity") or {}).get("platform_run_id")) or "")).strip(),
            "prewarm_summary": prewarm_summary,
            "prewarm_blockers": prewarm_blockers,
            "refresh_summary": refresh_summary,
            "refresh_blockers": refresh_blockers,
            "warm_gate_returncode": int(warm_gate_proc.returncode),
            "warm_gate_is_advisory_only": warm_gate_is_advisory,
            "warm_gate_ran": bool(args.run_warm_gate),
            "warm_gate_stdout": warm_gate_proc.stdout,
            "warm_gate_stderr": warm_gate_proc.stderr,
            "recovery_blockers": recovery_blockers,
            "recovery_advisories": recovery_advisories,
        },
        "overall_pass": overall_pass,
        "blocker_ids": [] if overall_pass else sorted(set(drill_blockers)),
    }
    dump_json(root / "g3a_drill_dependency_degrade.json", payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
