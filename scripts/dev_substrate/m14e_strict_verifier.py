#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REGISTRY = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
M14_LOCAL_ROOT = Path("runs/dev_substrate/dev_full/m14")
RUN_CONTROL_PREFIX = "evidence/dev_full/run_control"

DEFAULT_REGION = "eu-west-2"
DEFAULT_LAG_REF = (
    "s3://fraud-platform-dev-full-evidence/"
    "evidence/dev_full/run_control/m6f_p6b_streaming_active_20260225T175655Z/m6f_streaming_lag_posture.json"
)
DEFAULT_REPLAY_REF = (
    "s3://fraud-platform-dev-full-evidence/"
    "evidence/dev_full/run_control/m9c_p12_replay_basis_20260226T075941Z/m9c_replay_basis_receipt.json"
)

REQUIRED_HANDLES = [
    "FLINK_RUNTIME_PATH_ACTIVE",
    "FLINK_RUNTIME_PATH_ALLOWED",
    "FLINK_APP_RTDL_IEG_OFP_V0",
    "FLINK_APP_RTDL_IEG_OFP_SPLIT_POLICY",
    "FLINK_APP_RTDL_IEG_OFP_METRIC_NAMESPACES",
    "RTDL_CAUGHT_UP_LAG_MAX",
    "RTDL_CORE_CONSUMER_GROUP_ID",
    "S3_EVIDENCE_BUCKET",
    "ROLE_FLINK_EXECUTION",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run(cmd: list[str], timeout: int = 180) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return int(p.returncode), (p.stdout or ""), (p.stderr or "")


def parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if s.lower() in {"true", "false"}:
        return s.lower() == "true"
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def parse_registry(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rx = re.compile(r"^\*\s*`([^`]+)`")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(line.strip())
        if not m:
            continue
        body = m.group(1).strip()
        if "=" not in body:
            continue
        k, v = body.split("=", 1)
        out[k.strip()] = parse_scalar(v.strip())
    return out


def is_placeholder(value: Any) -> bool:
    s = str(value or "").strip().lower()
    return (not s) or s in {"tbd", "todo", "none", "null", "unset"} or "to_pin" in s or "placeholder" in s


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        return "", ""
    no_scheme = uri[5:]
    if "/" not in no_scheme:
        return "", ""
    bucket, key = no_scheme.split("/", 1)
    return bucket, key


def s3_head(bucket: str, key: str, region: str) -> tuple[bool, str]:
    rc, _, err = run(
        ["aws", "s3api", "head-object", "--bucket", bucket, "--key", key, "--region", region, "--output", "json"],
        timeout=120,
    )
    return (rc == 0), err.strip()


def s3_get_json(bucket: str, key: str, region: str, tmp_path: Path) -> tuple[dict[str, Any], str]:
    rc, _, err = run(
        ["aws", "s3api", "get-object", "--bucket", bucket, "--key", key, "--region", region, str(tmp_path)],
        timeout=180,
    )
    if rc != 0:
        return {}, err.strip()
    try:
        return json.loads(tmp_path.read_text(encoding="utf-8")), ""
    except Exception as exc:  # noqa: BLE001
        return {}, f"json_decode_failed:{type(exc).__name__}"


def aws_json(cmd: list[str], timeout: int = 180) -> tuple[int, dict[str, Any], str]:
    rc, out, err = run(cmd, timeout=timeout)
    if rc != 0:
        return rc, {}, err.strip()
    try:
        return rc, json.loads(out or "{}"), ""
    except Exception as exc:  # noqa: BLE001
        return 2, {}, f"json_decode_failed:{type(exc).__name__}"


def parse_aws_error(stderr: str) -> tuple[str, str]:
    m = re.search(r"An error occurred \(([^)]+)\) when calling .*?:\s*(.+)", stderr.strip(), re.DOTALL)
    if not m:
        return "UnknownError", stderr.strip()[:500]
    return m.group(1).strip(), m.group(2).strip()


def latest_m14d_pass() -> tuple[Path | None, dict[str, Any]]:
    best: tuple[str, Path, dict[str, Any]] | None = None
    for summary in M14_LOCAL_ROOT.glob("m14d_wsp_materialization_*/m14d_execution_summary.json"):
        payload = load_json(summary)
        if not payload:
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")).strip() != "M14.E_READY":
            continue
        if str(payload.get("m14d_verdict", "")).strip() != "ADVANCE_TO_M14_E":
            continue
        if int(payload.get("blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("captured_at_utc", ""))
        if best is None or stamp > best[0]:
            best = (stamp, summary, payload)
    if best is None:
        return None, {}
    return best[1], best[2]


def latest_p8_s5_pass() -> tuple[Path | None, dict[str, Any]]:
    base = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
    best: tuple[str, Path, dict[str, Any]] | None = None
    for summary in base.glob("m7p8_stress_s5_*/stress/m7p8_execution_summary.json"):
        payload = load_json(summary)
        if not payload:
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if int(payload.get("open_blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if best is None or stamp > best[0]:
            best = (stamp, summary, payload)
    if best is None:
        return None, {}
    return best[1], best[2]


def build_probe_app_name(base_app: str) -> str:
    suffix = f"m14e-probe-{token().lower()}"
    room = 120 - len(suffix) - 1
    prefix = base_app[: max(24, room)]
    name = f"{prefix}-{suffix}".strip("-")
    return name[:128]


def main() -> int:
    execution_id = f"m14e_rtdl_projection_{token()}"
    local_root = M14_LOCAL_ROOT / execution_id
    local_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = local_root / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    blockers: list[dict[str, Any]] = []
    advisories: list[dict[str, Any]] = []
    captured_at = now_utc()

    handles = parse_registry(REGISTRY)
    handle_matrix: list[dict[str, Any]] = []
    for key in REQUIRED_HANDLES:
        value = handles.get(key, "")
        ok = (key in handles) and (not is_placeholder(value))
        handle_matrix.append({"key": key, "value": value, "ok": ok})
        if not ok:
            blockers.append(
                {
                    "id": "M14-B2",
                    "lane": "handles",
                    "message": f"required handle unresolved: {key}",
                }
            )

    runtime_active = str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
    runtime_allowed = str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).strip()
    runtime_allowed_set = {p.strip() for p in runtime_allowed.split("|") if p.strip()}
    if runtime_active != "MSF_MANAGED":
        blockers.append(
            {
                "id": "M14-B2",
                "lane": "handles",
                "message": f"runtime active drift: expected MSF_MANAGED got {runtime_active or 'UNSET'}",
            }
        )
    if runtime_active and runtime_active not in runtime_allowed_set:
        blockers.append(
            {
                "id": "M14-B2",
                "lane": "handles",
                "message": "runtime active not in runtime allowed set",
            }
        )

    m14d_summary_path, m14d_summary = latest_m14d_pass()
    if not m14d_summary_path:
        blockers.append(
            {
                "id": "M14-B2",
                "lane": "entry",
                "message": "no valid M14.D pass summary found for M14.E entry",
            }
        )

    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    app_name = str(handles.get("FLINK_APP_RTDL_IEG_OFP_V0", "")).strip()
    role_arn = str(handles.get("ROLE_FLINK_EXECUTION", "")).strip()
    lag_max = int(handles.get("RTDL_CAUGHT_UP_LAG_MAX", 0) or 0)
    region = DEFAULT_REGION

    # MSF probe: pinned-handle create attempt plus ephemeral create/delete to prove capability.
    pinned_create_cmd = [
        "aws",
        "kinesisanalyticsv2",
        "create-application",
        "--region",
        region,
        "--application-name",
        app_name,
        "--runtime-environment",
        "FLINK-1_18",
        "--application-mode",
        "STREAMING",
        "--service-execution-role",
        role_arn,
    ]
    rc_pin, out_pin, err_pin = run(pinned_create_cmd, timeout=240)
    pin_code, pin_msg = parse_aws_error(err_pin) if rc_pin != 0 else ("", "")

    probe_app = build_probe_app_name(app_name or "fraud-platform-m14e")
    probe_create_cmd = [
        "aws",
        "kinesisanalyticsv2",
        "create-application",
        "--region",
        region,
        "--application-name",
        probe_app,
        "--runtime-environment",
        "FLINK-1_18",
        "--application-mode",
        "STREAMING",
        "--service-execution-role",
        role_arn,
    ]
    rc_probe, out_probe, err_probe = run(probe_create_cmd, timeout=240)
    probe_code, probe_msg = parse_aws_error(err_probe) if rc_probe != 0 else ("", "")

    probe_describe = {}
    probe_deleted = False
    if rc_probe == 0:
        _, probe_describe, _ = aws_json(
            [
                "aws",
                "kinesisanalyticsv2",
                "describe-application",
                "--region",
                region,
                "--application-name",
                probe_app,
                "--output",
                "json",
            ],
            timeout=120,
        )
        rc_del, _, _ = run(
            [
                "aws",
                "kinesisanalyticsv2",
                "delete-application",
                "--region",
                region,
                "--application-name",
                probe_app,
                "--create-timestamp",
                str(
                    probe_describe.get("ApplicationDetail", {}).get("CreateTimestamp", "")
                    if probe_describe
                    else ""
                ),
            ],
            timeout=120,
        )
        probe_deleted = rc_del == 0

    rc_list, list_payload, list_err = aws_json(
        ["aws", "kinesisanalyticsv2", "list-applications", "--region", region, "--output", "json"], timeout=120
    )
    rc_desc, desc_payload, desc_err = aws_json(
        [
            "aws",
            "kinesisanalyticsv2",
            "describe-application",
            "--region",
            region,
            "--application-name",
            app_name,
            "--output",
            "json",
        ],
        timeout=120,
    )

    listed_names = {str(x.get("ApplicationName", "")) for x in list_payload.get("ApplicationSummaries", [])}
    canonical_list_ok = rc_list == 0 and app_name in listed_names
    canonical_desc = desc_payload.get("ApplicationDetail", {})
    canonical_desc_ok = rc_desc == 0 and str(canonical_desc.get("ApplicationStatus", "")).strip() == "READY"

    runtime_effective = "MSF_MANAGED"
    canonical_probe_result = "UNKNOWN"
    if rc_probe == 0:
        canonical_probe_result = "CREATE_SUCCESS_EPHEMERAL"
    else:
        if probe_code == "UnsupportedOperationException" or "additional verification" in probe_msg.lower():
            canonical_probe_result = "CREATE_BLOCKED_EXTERNAL"
            if "EKS_FLINK_OPERATOR" in runtime_allowed_set:
                runtime_effective = "EKS_FLINK_OPERATOR"
                advisories.append(
                    {
                        "code": "M14E-AD1",
                        "message": "msf_account_verification_gate_active; fallback adjudication path used",
                    }
                )
            else:
                blockers.append(
                    {
                        "id": "M14-B2",
                        "lane": "runtime",
                        "message": "MSF external gate observed but fallback path not allowed",
                    }
                )
        else:
            canonical_probe_result = "CREATE_FAILED"
            blockers.append(
                {
                    "id": "M14-B2",
                    "lane": "runtime",
                    "message": f"MSF create probe failed: {probe_code or 'UnknownError'}",
                    "details": {"error_message": probe_msg},
                }
            )

    if runtime_effective == "MSF_MANAGED" and (not canonical_list_ok or not canonical_desc_ok):
        blockers.append(
            {
                "id": "M14-B2",
                "lane": "runtime",
                "message": "canonical app list/describe readiness check failed after managed probe",
                "details": {"list_error": list_err, "describe_error": desc_err},
            }
        )

    # Branch-separated evidence (IEG/OFP) and durable proof refs.
    p8_summary_path, p8_summary = latest_p8_s5_pass()
    branch_split_ok = False
    p8_rollup_ref = ""
    ieg_proof_ref = ""
    ofp_proof_ref = ""
    ieg_proof_readable = False
    ofp_proof_readable = False
    if not p8_summary_path:
        blockers.append({"id": "M14-B4", "lane": "branch_evidence", "message": "no valid P8 S5 summary found"})
    else:
        p8_dir = p8_summary_path.parent
        ieg_snapshot_path = p8_dir / "m7p8_ieg_snapshot.json"
        ofp_snapshot_path = p8_dir / "m7p8_ofp_snapshot.json"
        if not ieg_snapshot_path.exists() or not ofp_snapshot_path.exists():
            blockers.append(
                {
                    "id": "M14-B4",
                    "lane": "branch_evidence",
                    "message": "missing IEG/OFP snapshots in latest P8 S5 artifact set",
                }
            )
        else:
            ieg_snapshot = load_json(ieg_snapshot_path)
            ofp_snapshot = load_json(ofp_snapshot_path)
            ieg_proof_ref = str(ieg_snapshot.get("component_snapshot", {}).get("rtdl_core_component_proof_key", "")).strip()
            ofp_proof_ref = str(ofp_snapshot.get("component_snapshot", {}).get("rtdl_core_component_proof_key", "")).strip()
            if not ieg_proof_ref or not ofp_proof_ref:
                blockers.append(
                    {
                        "id": "M14-B4",
                        "lane": "branch_evidence",
                        "message": "IEG/OFP proof refs missing in branch snapshots",
                    }
                )
            else:
                ok_ieg, _ = s3_head(evidence_bucket, ieg_proof_ref, region)
                ok_ofp, _ = s3_head(evidence_bucket, ofp_proof_ref, region)
                ieg_proof_readable = ok_ieg
                ofp_proof_readable = ok_ofp
                branch_split_ok = ok_ieg and ok_ofp
                if not branch_split_ok:
                    blockers.append(
                        {
                            "id": "M14-B4",
                            "lane": "branch_evidence",
                            "message": "IEG/OFP proof refs not readable in durable evidence",
                        }
                    )
            p8_rollup_ref = f"s3://{evidence_bucket}/{RUN_CONTROL_PREFIX}/{p8_summary.get('phase_execution_id','')}/stress/m7p8_execution_summary.json"

    # Continuity evidence from durable refs (canonical chain).
    lag_ref = DEFAULT_LAG_REF
    replay_ref = DEFAULT_REPLAY_REF
    lag_bucket, lag_key = parse_s3_uri(lag_ref)
    replay_bucket, replay_key = parse_s3_uri(replay_ref)
    lag_payload: dict[str, Any] = {}
    replay_payload: dict[str, Any] = {}
    lag_ok = False
    replay_ok = False
    if not lag_bucket or not lag_key:
        blockers.append({"id": "M14-B4", "lane": "continuity", "message": "lag ref invalid"})
    else:
        lag_payload, lag_err = s3_get_json(lag_bucket, lag_key, region, tmp_dir / "lag.json")
        lag_measured = lag_payload.get("measured_lag")
        lag_within = bool(lag_payload.get("within_threshold"))
        lag_ok = (lag_measured is not None) and lag_within and int(lag_measured) <= lag_max
        if not lag_ok:
            blockers.append(
                {
                    "id": "M14-B4",
                    "lane": "continuity",
                    "message": "lag continuity gate failed",
                    "details": {"lag_error": lag_err, "measured_lag": lag_measured, "lag_max": lag_max},
                }
            )
    if not replay_bucket or not replay_key:
        blockers.append({"id": "M14-B4", "lane": "continuity", "message": "replay ref invalid"})
    else:
        replay_payload, replay_err = s3_get_json(replay_bucket, replay_key, region, tmp_dir / "replay.json")
        offset_count = int(replay_payload.get("origin_offset_range_count", 0) or 0)
        validation_errors = replay_payload.get("validation", {}).get("offset_validation_errors", [])
        replay_ok = offset_count > 0 and len(validation_errors or []) == 0
        if not replay_ok:
            blockers.append(
                {
                    "id": "M14-B4",
                    "lane": "continuity",
                    "message": "replay continuity gate failed",
                    "details": {"replay_error": replay_err, "origin_offset_range_count": offset_count},
                }
            )

    probe_receipt = {
        "captured_at_utc": captured_at,
        "application_name": app_name,
        "service_execution_role": role_arn,
        "runtime_environment": "FLINK-1_18",
        "pinned_handle_create_probe": {
            "command": " ".join(pinned_create_cmd),
            "result": "CREATE_SUCCESS" if rc_pin == 0 else "CREATE_FAILED",
            "error_code": pin_code,
            "error_message": pin_msg,
            "stdout_excerpt": out_pin.strip()[:300],
        },
        "ephemeral_create_probe": {
            "command": " ".join(probe_create_cmd),
            "probe_application_name": probe_app,
            "result": "CREATE_SUCCESS" if rc_probe == 0 else "CREATE_FAILED",
            "error_code": probe_code,
            "error_message": probe_msg,
            "deleted_after_probe": probe_deleted,
        },
        "canonical_app_surface": {
            "list_ok": canonical_list_ok,
            "describe_ok": canonical_desc_ok,
            "application_status": canonical_desc.get("ApplicationStatus", ""),
            "application_mode": canonical_desc.get("ApplicationMode", ""),
            "application_runtime": canonical_desc.get("RuntimeEnvironment", ""),
            "application_arn": canonical_desc.get("ApplicationARN", ""),
        },
        "result": canonical_probe_result,
    }

    dod = {
        "single_app_branch_separated_evidence": branch_split_ok,
        "lag_offset_replay_continuity_pass": lag_ok and replay_ok,
        "runtime_path_adjudication_explicit": canonical_probe_result in {
            "CREATE_SUCCESS_EPHEMERAL",
            "CREATE_BLOCKED_EXTERNAL",
            "CREATE_FAILED",
        },
        "m14e_artifacts_local_and_durable": False,
    }

    projection_snapshot = {
        "captured_at_utc": captured_at,
        "execution_id": execution_id,
        "phase": "M14.E",
        "phase_id": "P8",
        "blockers": blockers,
        "advisories": advisories,
        "m14d_entry": {
            "summary_path": str(m14d_summary_path.as_posix()) if m14d_summary_path else "",
            "execution_id": m14d_summary.get("execution_id", ""),
            "overall_pass": bool(m14d_summary.get("overall_pass", False)),
            "next_gate": m14d_summary.get("next_gate", ""),
            "verdict": m14d_summary.get("m14d_verdict", ""),
        },
        "runtime": {
            "canonical_application": app_name,
            "canonical_probe_result": canonical_probe_result,
            "runtime_path_active": runtime_active,
            "runtime_path_allowed": runtime_allowed,
            "runtime_path_effective": runtime_effective,
            "fallback_used": runtime_effective != "MSF_MANAGED",
        },
        "branch_evidence": {
            "branch_split_ok": branch_split_ok,
            "metric_namespace_pin": str(handles.get("FLINK_APP_RTDL_IEG_OFP_METRIC_NAMESPACES", "")),
            "p8_rollup_ref": p8_rollup_ref,
            "p8_rollup_overall_pass": bool(p8_summary.get("overall_pass", False)),
            "ieg_proof_ref": f"s3://{evidence_bucket}/{ieg_proof_ref}" if ieg_proof_ref else "",
            "ofp_proof_ref": f"s3://{evidence_bucket}/{ofp_proof_ref}" if ofp_proof_ref else "",
            "ieg_proof_readable": ieg_proof_readable,
            "ofp_proof_readable": ofp_proof_readable,
        },
        "continuity": {
            "lag_ref": lag_ref,
            "lag_ok": lag_ok,
            "lag_payload": lag_payload,
            "replay_ref": replay_ref,
            "replay_ok": replay_ok,
            "replay_payload": replay_payload,
        },
        "msf_probe": probe_receipt,
        "handle_matrix": handle_matrix,
    }

    blocker_register = {
        "captured_at_utc": captured_at,
        "execution_id": execution_id,
        "phase": "M14.E",
        "blocker_count": len(blockers),
        "blockers": blockers,
    }

    summary = {
        "captured_at_utc": captured_at,
        "execution_id": execution_id,
        "phase": "M14.E",
        "phase_id": "P8",
        "overall_pass": len(blockers) == 0,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "advisory_count": len(advisories),
        "advisories": advisories,
        "dod": dod,
        "m14e_verdict": "ADVANCE_TO_M14_F" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_gate": "M14.F_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
    }

    local_files = {
        "m14e_rtdl_projection_snapshot.json": projection_snapshot,
        "m14e_msf_probe_receipt.json": probe_receipt,
        "m14e_blocker_register.json": blocker_register,
        "m14e_execution_summary.json": summary,
    }
    for name, payload in local_files.items():
        write_json(local_root / name, payload)

    durable_failures: list[dict[str, str]] = []
    durable_refs: dict[str, str] = {}
    for name in local_files:
        src = local_root / name
        key = f"{RUN_CONTROL_PREFIX}/{execution_id}/{name}"
        uri = f"s3://{evidence_bucket}/{key}"
        rc_up, _, err_up = run(["aws", "s3", "cp", str(src), uri, "--region", region], timeout=180)
        if rc_up != 0:
            durable_failures.append({"artifact": name, "step": "upload", "error": err_up.strip()[:500]})
            continue
        ok_head, err_head = s3_head(evidence_bucket, key, region)
        if not ok_head:
            durable_failures.append({"artifact": name, "step": "head", "error": err_head[:500]})
            continue
        durable_refs[name] = uri

    if durable_failures:
        blockers.append(
            {
                "id": "M14-B6",
                "lane": "artifacts",
                "message": "local/durable artifact publication-readback failed",
                "details": {"failures": durable_failures},
            }
        )

    # Recompute final state with post-upload blockers.
    deduped_blockers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for b in blockers:
        sig = json.dumps(b, sort_keys=True, default=str)
        if sig in seen:
            continue
        seen.add(sig)
        deduped_blockers.append(b)
    blockers = deduped_blockers
    projection_snapshot["blockers"] = blockers
    projection_snapshot["advisories"] = advisories
    projection_snapshot["durable_refs"] = durable_refs
    blocker_register["blocker_count"] = len(blockers)
    blocker_register["blockers"] = blockers
    summary["overall_pass"] = len(blockers) == 0
    summary["blocker_count"] = len(blockers)
    summary["blockers"] = blockers
    summary["advisory_count"] = len(advisories)
    summary["advisories"] = advisories
    summary["dod"] = {
        "single_app_branch_separated_evidence": branch_split_ok,
        "lag_offset_replay_continuity_pass": lag_ok and replay_ok,
        "runtime_path_adjudication_explicit": canonical_probe_result in {
            "CREATE_SUCCESS_EPHEMERAL",
            "CREATE_BLOCKED_EXTERNAL",
            "CREATE_FAILED",
        },
        "m14e_artifacts_local_and_durable": len(durable_failures) == 0,
    }
    summary["m14e_verdict"] = "ADVANCE_TO_M14_F" if len(blockers) == 0 else "HOLD_REMEDIATE"
    summary["next_gate"] = "M14.F_READY" if len(blockers) == 0 else "HOLD_REMEDIATE"

    write_json(local_root / "m14e_rtdl_projection_snapshot.json", projection_snapshot)
    write_json(local_root / "m14e_blocker_register.json", blocker_register)
    write_json(local_root / "m14e_execution_summary.json", summary)

    # Best effort: mirror updated summary artifacts.
    for name in ["m14e_rtdl_projection_snapshot.json", "m14e_blocker_register.json", "m14e_execution_summary.json"]:
        src = local_root / name
        key = f"{RUN_CONTROL_PREFIX}/{execution_id}/{name}"
        uri = f"s3://{evidence_bucket}/{key}"
        run(["aws", "s3", "cp", str(src), uri, "--region", region], timeout=180)

    print(
        json.dumps(
            {
                "execution_id": execution_id,
                "local_root": str(local_root.as_posix()),
                "overall_pass": summary["overall_pass"],
                "blocker_count": summary["blocker_count"],
                "verdict": summary["m14e_verdict"],
                "next_gate": summary["next_gate"],
                "probe_result": canonical_probe_result,
                "runtime_path_effective": runtime_effective,
            },
            ensure_ascii=True,
        )
    )

    return 0 if summary["overall_pass"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        print(
            json.dumps(
                {
                    "overall_pass": False,
                    "blocker_count": 1,
                    "blockers": [{"id": "M14-B2", "lane": "runtime", "message": f"timeout:{exc.cmd}"}],
                },
                ensure_ascii=True,
            )
        )
        raise
