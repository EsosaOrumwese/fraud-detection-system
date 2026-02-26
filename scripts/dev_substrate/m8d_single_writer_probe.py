#!/usr/bin/env python3
"""Managed M8.D single-writer contention probe artifact builder."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from fraud_detection.platform_reporter import worker as reporter_worker


HANDLES_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_handles(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rx = re.compile(r"^\* `([^`=]+?)\s*=\s*([^`]+)`")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(line.strip())
        if not m:
            continue
        key = m.group(1).strip()
        raw = m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            value: Any = raw[1:-1]
        elif raw.lower() == "true":
            value = True
        elif raw.lower() == "false":
            value = False
        else:
            try:
                value = int(raw) if "." not in raw else float(raw)
            except ValueError:
                value = raw
        out[key] = value
    return out


def is_placeholder(value: Any) -> bool:
    s = str(value).strip()
    s_lower = s.lower()
    if s == "":
        return True
    if s_lower in {"tbd", "todo", "none", "null", "unset"}:
        return True
    if "to_pin" in s_lower or "placeholder" in s_lower:
        return True
    if "<" in s and ">" in s:
        return True
    return False


def s3_get_json(s3_client: Any, bucket: str, key: str) -> dict[str, Any]:
    body = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return json.loads(body)


def s3_put_json(s3_client: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3_client.head_object(Bucket=bucket, Key=key)


def write_local_artifacts(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def dedupe_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for blocker in blockers:
        code = str(blocker.get("code", "")).strip()
        message = str(blocker.get("message", "")).strip()
        sig = (code, message)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"code": code, "message": message})
    return out


def build_postgres_dsn(*, endpoint: str, username: str, password: str, db_name: str) -> str:
    host = endpoint.strip()
    if not host:
        raise RuntimeError("AURORA_ENDPOINT_EMPTY")
    if ":" not in host:
        host = f"{host}:5432"
    user_q = quote_plus(username)
    pass_q = quote_plus(password)
    db_q = quote_plus(db_name)
    return f"postgresql://{user_q}:{pass_q}@{host}/{db_q}?sslmode=require&connect_timeout=5"


def probe_single_writer(
    *,
    profile_path: Path,
    platform_run_id: str,
    lock_backend: str,
    lock_key_pattern: str,
    hold_seconds: float,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    holder_ready = threading.Event()
    holder_done = threading.Event()
    state: dict[str, Any] = {
        "holder_acquired": False,
        "holder_error": None,
        "contender_denied": False,
        "contender_unexpected_acquire": False,
        "contender_error": None,
        "post_release_reacquire": False,
        "post_release_error": None,
    }

    def _event(name: str, **kwargs: Any) -> None:
        events.append(
            {
                "ts_utc": now_utc(),
                "event": name,
                **kwargs,
            }
        )

    def holder() -> None:
        try:
            with reporter_worker._single_writer_lock(
                profile_path=profile_path,
                run_id=platform_run_id,
                lock_backend=lock_backend,
                lock_key_pattern=lock_key_pattern,
            ):
                state["holder_acquired"] = True
                _event("holder_lock_acquired")
                holder_ready.set()
                time.sleep(hold_seconds)
                _event("holder_lock_releasing")
        except Exception as exc:  # pragma: no cover - defensive
            state["holder_error"] = f"{type(exc).__name__}:{str(exc)[:256]}"
            _event("holder_error", error=state["holder_error"])
            holder_ready.set()
        finally:
            holder_done.set()

    holder_thread = threading.Thread(target=holder, daemon=True)
    started_at = time.time()
    holder_thread.start()

    if not holder_ready.wait(timeout=15.0):
        state["holder_error"] = "holder_wait_timeout"
        _event("holder_wait_timeout")
        holder_done.set()

    if state["holder_acquired"]:
        try:
            with reporter_worker._single_writer_lock(
                profile_path=profile_path,
                run_id=platform_run_id,
                lock_backend=lock_backend,
                lock_key_pattern=lock_key_pattern,
            ):
                state["contender_unexpected_acquire"] = True
                _event("contender_unexpected_acquire")
        except Exception as exc:  # expected lock denial path
            msg = str(exc)
            if "REPORTER_LOCK_NOT_ACQUIRED:" in msg:
                state["contender_denied"] = True
                _event("contender_lock_denied", error=f"{type(exc).__name__}:{msg[:256]}")
            else:
                state["contender_error"] = f"{type(exc).__name__}:{msg[:256]}"
                _event("contender_error", error=state["contender_error"])
    else:
        _event("contender_skipped_due_to_holder_failure")

    holder_done.wait(timeout=max(20.0, hold_seconds + 10.0))
    holder_thread.join(timeout=2.0)

    if state["holder_acquired"]:
        try:
            with reporter_worker._single_writer_lock(
                profile_path=profile_path,
                run_id=platform_run_id,
                lock_backend=lock_backend,
                lock_key_pattern=lock_key_pattern,
            ):
                state["post_release_reacquire"] = True
                _event("post_release_reacquire_success")
        except Exception as exc:
            state["post_release_error"] = f"{type(exc).__name__}:{str(exc)[:256]}"
            _event("post_release_reacquire_error", error=state["post_release_error"])

    elapsed = time.time() - started_at
    return {"state": state, "events": events, "elapsed_seconds": round(elapsed, 3)}


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M8D_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M8D_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m8c_execution = env.get("UPSTREAM_M8C_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"
    hold_seconds = float(env.get("M8D_LOCK_HOLD_SECONDS", "8"))

    if not execution_id:
        raise SystemExit("M8D_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M8D_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m8c_execution:
        raise SystemExit("UPSTREAM_M8C_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)
    ssm = boto3.client("ssm", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []
    remediation_notes: list[str] = []

    upstream_key = f"evidence/dev_full/run_control/{upstream_m8c_execution}/m8c_execution_summary.json"
    upstream_summary: dict[str, Any] | None = None
    try:
        upstream_summary = s3_get_json(s3, bucket, upstream_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": upstream_key, "error": type(exc).__name__})
        blockers.append({"code": "M8-B4", "message": "Upstream M8.C summary is unreadable."})

    platform_run_id = env.get("PLATFORM_RUN_ID", "").strip()
    scenario_run_id = env.get("SCENARIO_RUN_ID", "").strip()
    upstream_ok = False
    if upstream_summary:
        upstream_ok = bool(upstream_summary.get("overall_pass")) and str(upstream_summary.get("next_gate", "")).strip() == "M8.D_READY"
        if not upstream_ok:
            blockers.append({"code": "M8-B4", "message": "M8.C upstream gate is not M8.D_READY."})
        if not platform_run_id:
            platform_run_id = str(upstream_summary.get("platform_run_id", "")).strip()
        if not scenario_run_id:
            scenario_run_id = str(upstream_summary.get("scenario_run_id", "")).strip()

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M8-B4", "message": "Active run scope is unresolved for M8.D."})

    required_handles = [
        "REPORTER_LOCK_BACKEND",
        "REPORTER_LOCK_KEY_PATTERN",
        "SSM_AURORA_ENDPOINT_PATH",
        "SSM_AURORA_USERNAME_PATH",
        "SSM_AURORA_PASSWORD_PATH",
        "AURORA_DB_NAME",
    ]

    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    resolved_values: dict[str, Any] = {}
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            continue
        resolved_values[key] = value
        if is_placeholder(value):
            placeholder_handles.append(key)

    if missing_handles or placeholder_handles:
        blockers.append({"code": "M8-B4", "message": "Required M8.D handles are missing or placeholder-valued."})

    lock_backend = str(handles.get("REPORTER_LOCK_BACKEND", "")).strip().lower()
    lock_key_pattern = str(handles.get("REPORTER_LOCK_KEY_PATTERN", "")).strip()
    lock_probe: dict[str, Any] = {
        "backend": lock_backend,
        "lock_key_pattern": lock_key_pattern,
        "rendered_lock_key": "",
        "lock_id_signed_int64": None,
    }
    if platform_run_id and lock_key_pattern:
        try:
            rendered = reporter_worker._render_lock_key(pattern=lock_key_pattern, run_id=platform_run_id)
            lock_id = reporter_worker._lock_id_from_key(rendered)
            lock_probe["rendered_lock_key"] = rendered
            lock_probe["lock_id_signed_int64"] = lock_id
            lock_probe["lock_key_sha256_prefix"] = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]
        except Exception as exc:
            blockers.append({"code": "M8-B4", "message": f"Lock key rendering failed: {type(exc).__name__}"})

    dsn = str(env.get("IG_ADMISSION_DSN", "")).strip()
    endpoint_preview = ""
    ssm_surfaces: dict[str, Any] = {"aurora_endpoint_path": "", "aurora_username_path": "", "aurora_password_path": ""}
    if not dsn:
        endpoint_path = str(handles.get("SSM_AURORA_ENDPOINT_PATH", "")).strip()
        username_path = str(handles.get("SSM_AURORA_USERNAME_PATH", "")).strip()
        password_path = str(handles.get("SSM_AURORA_PASSWORD_PATH", "")).strip()
        db_name = str(handles.get("AURORA_DB_NAME", "")).strip() or "fraud_platform"
        ssm_surfaces = {
            "aurora_endpoint_path": endpoint_path,
            "aurora_username_path": username_path,
            "aurora_password_path": password_path,
        }
        try:
            endpoint = ssm.get_parameter(Name=endpoint_path, WithDecryption=True)["Parameter"]["Value"].strip()
            username = ssm.get_parameter(Name=username_path, WithDecryption=True)["Parameter"]["Value"].strip()
            password = ssm.get_parameter(Name=password_path, WithDecryption=True)["Parameter"]["Value"]
            endpoint_preview = endpoint[:128]
            if endpoint.endswith(".cluster.local") or endpoint.endswith(".cluster.internal"):
                remediation_notes.append("aurora_endpoint_looks_seeded_non_routable")
            dsn = build_postgres_dsn(endpoint=endpoint, username=username, password=password, db_name=db_name)
            os.environ["IG_ADMISSION_DSN"] = dsn
        except Exception as exc:
            blockers.append({"code": "M8-B4", "message": f"Aurora SSM/DSN materialization failed: {type(exc).__name__}"})

    profile_path = Path(env.get("M8D_PROFILE_PATH", "config/platform/profiles/dev_full.yaml"))
    if not profile_path.exists():
        blockers.append({"code": "M8-B4", "message": f"Reporter profile path not found: {profile_path}"})

    probe_result: dict[str, Any] = {"state": {}, "events": [], "elapsed_seconds": 0.0}
    if not blockers:
        if lock_backend not in {"db_advisory_lock", "aurora_advisory_lock"}:
            blockers.append({"code": "M8-B4", "message": f"Unsupported lock backend for M8.D: {lock_backend}"})
        else:
            try:
                probe_result = probe_single_writer(
                    profile_path=profile_path,
                    platform_run_id=platform_run_id,
                    lock_backend=lock_backend,
                    lock_key_pattern=lock_key_pattern,
                    hold_seconds=hold_seconds,
                )
            except Exception as exc:
                blockers.append({"code": "M8-B4", "message": f"Contention probe execution failed: {type(exc).__name__}"})
                remediation_notes.append(str(exc)[:256])

    state = probe_result.get("state", {})
    holder_acquired = bool(state.get("holder_acquired"))
    contender_denied = bool(state.get("contender_denied"))
    contender_unexpected_acquire = bool(state.get("contender_unexpected_acquire"))
    post_release_reacquire = bool(state.get("post_release_reacquire"))
    no_orphan_lock = post_release_reacquire

    if not holder_acquired:
        blockers.append({"code": "M8-B4", "message": "Holder lock acquisition failed; lock path is not executable."})
    if contender_unexpected_acquire:
        blockers.append({"code": "M8-B4", "message": "Second writer unexpectedly acquired lock during contention window."})
    if not contender_denied:
        blockers.append({"code": "M8-B4", "message": "Second writer denial signal missing under contention window."})
    if not no_orphan_lock:
        blockers.append({"code": "M8-B4", "message": "No-orphan-lock proof failed after release check."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M8.E_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M8.D",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m8c_execution": upstream_m8c_execution,
        "upstream_m8c_summary_key": upstream_key,
        "upstream_ok": upstream_ok,
        "required_handle_count": len(required_handles),
        "resolved_handle_count": len(required_handles) - len(missing_handles),
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "resolved_handle_values": resolved_values,
        "lock_probe": lock_probe,
        "contention_probe_window_seconds": hold_seconds,
        "contention_events": probe_result.get("events", []),
        "contention_state": state,
        "contention_outcome_checks": {
            "holder_acquired": holder_acquired,
            "contender_denied": contender_denied,
            "contender_unexpected_acquire": contender_unexpected_acquire,
            "post_release_reacquire": post_release_reacquire,
            "no_orphan_lock": no_orphan_lock,
        },
        "dsn_surface": {
            "profile_path": str(profile_path),
            "aurora_endpoint_preview": endpoint_preview,
            "ssm_paths": ssm_surfaces,
            "dsn_set_via_env": bool(os.environ.get("IG_ADMISSION_DSN")),
        },
        "remediation_notes": remediation_notes,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M8.D",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": captured,
        "phase": "M8.D",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m8d_single_writer_probe_snapshot.json": snapshot,
        "m8d_blocker_register.json": register,
        "m8d_execution_summary.json": summary,
    }

    write_local_artifacts(run_dir, artifacts)

    prefix = f"evidence/dev_full/run_control/{execution_id}"
    for name, payload in artifacts.items():
        key = f"{prefix}/{name}"
        try:
            s3_put_json(s3, bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "error": type(exc).__name__, "key": key})

    if upload_errors:
        register["upload_errors"] = upload_errors
        register["blockers"].append({"code": "M8-B12", "message": "Failed to publish/readback one or more M8.D artifacts."})
        register["blocker_count"] = len(register["blockers"])
        summary["overall_pass"] = False
        summary["next_gate"] = "HOLD_REMEDIATE"
        summary["blocker_count"] = register["blocker_count"]
        write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": summary["overall_pass"],
        "blocker_count": summary["blocker_count"],
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{bucket}/{prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
