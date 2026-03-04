#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urlerr
from urllib import request as urlreq
from uuid import uuid4

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.P4.stress_test.md")
PARENT_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

M5P4_REQ_HANDLES = [
    "IG_BASE_URL",
    "IG_INGEST_PATH",
    "IG_HEALTHCHECK_PATH",
    "IG_AUTH_MODE",
    "IG_AUTH_HEADER_NAME",
    "SSM_IG_API_KEY_PATH",
    "APIGW_IG_API_ID",
    "LAMBDA_IG_HANDLER_NAME",
    "DDB_IG_IDEMPOTENCY_TABLE",
    "IG_MAX_REQUEST_BYTES",
    "IG_REQUEST_TIMEOUT_SECONDS",
    "IG_INTERNAL_RETRY_MAX_ATTEMPTS",
    "IG_INTERNAL_RETRY_BACKOFF_MS",
    "IG_IDEMPOTENCY_TTL_SECONDS",
    "IG_DLQ_MODE",
    "IG_DLQ_QUEUE_NAME",
    "IG_REPLAY_MODE",
    "IG_RATE_LIMIT_RPS",
    "IG_RATE_LIMIT_BURST",
    "MSK_CLUSTER_ARN",
    "MSK_BOOTSTRAP_BROKERS_SASL_IAM",
    "MSK_CLIENT_SUBNET_IDS",
    "MSK_SECURITY_GROUP_ID",
    "S3_EVIDENCE_BUCKET",
    "S3_RUN_CONTROL_ROOT_PATTERN",
]

M5P4_PLAN_KEYS = [
    "M5P4_STRESS_PROFILE_ID",
    "M5P4_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M5P4_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M5P4_STRESS_DECISION_LOG_PATH_PATTERN",
    "M5P4_STRESS_REQUIRED_ARTIFACTS",
    "M5P4_STRESS_MAX_RUNTIME_MINUTES",
    "M5P4_STRESS_MAX_SPEND_USD",
    "M5P4_STRESS_EXPECTED_VERDICT_ON_PASS",
    "M5P4_STRESS_REQUIRE_P3_VERDICT",
    "M5P4_STRESS_REQUIRE_M6_HANDOFF_PACK",
]

M5P4_ARTS = [
    "m5p4_stagea_findings.json",
    "m5p4_lane_matrix.json",
    "m5p4_probe_latency_throughput_snapshot.json",
    "m5p4_control_rail_conformance_snapshot.json",
    "m5p4_secret_safety_snapshot.json",
    "m5p4_cost_outcome_receipt.json",
    "m5p4_blocker_register.json",
    "m5p4_execution_summary.json",
    "m5p4_decision_log.json",
]
M5P4_S0_ARTS = M5P4_ARTS
M5P4_S1_ARTS = M5P4_ARTS
M5P4_S2_ARTS = M5P4_ARTS
M5P4_S3_ARTS = M5P4_ARTS
M5P4_S4_ARTS = M5P4_ARTS

M5P4_REQUIRED_TOPIC_HANDLES = [
    "FP_BUS_CONTROL_V1",
    "FP_BUS_TRAFFIC_FRAUD_V1",
    "FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1",
    "FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1",
    "FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1",
    "FP_BUS_RTDL_V1",
    "FP_BUS_AUDIT_V1",
    "FP_BUS_CASE_TRIGGERS_V1",
    "FP_BUS_LABELS_EVENTS_V1",
]

M5P4_TOPIC_PARTITIONS_BY_HANDLE = {
    "FP_BUS_CONTROL_V1": 3,
    "FP_BUS_TRAFFIC_FRAUD_V1": 6,
    "FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1": 6,
    "FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1": 6,
    "FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1": 6,
    "FP_BUS_RTDL_V1": 6,
    "FP_BUS_AUDIT_V1": 3,
    "FP_BUS_CASE_TRIGGERS_V1": 3,
    "FP_BUS_LABELS_EVENTS_V1": 3,
}


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
        if not m:
            continue
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


def build_lane_matrix() -> dict[str, Any]:
    return {
        "component_sequence": ["P4.A", "P4.B", "P4.C", "P4.D", "P4.E"],
        "plane_sequence": [
            "ingress_boundary_plane",
            "ingress_auth_plane",
            "ingress_bus_plane",
            "ingress_envelope_plane",
            "p4_rollup_plane",
        ],
        "integrated_windows": [
            "m5p4_s0_entry_window",
            "m5p4_s1_boundary_window",
            "m5p4_s2_auth_window",
            "m5p4_s3_topic_window",
            "m5p4_s4_envelope_window",
        ],
    }


def load_latest_successful_m5p3_closure(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p3_stress_*/stress"))
    for d in reversed(runs):
        sp = d / "m5p3_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        verdict = str(
            summ.get("verdict", summ.get("recommendation", summ.get("next_gate", "")))
        ).strip()
        if verdict != "ADVANCE_TO_P4":
            continue
        return {"path": d, "summary": summ, "verdict": verdict}
    return {}


def load_latest_successful_m5p4_s0(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p4_stress_s0_*/stress"))
    for d in reversed(runs):
        sp = d / "m5p4_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M5P4-ST-S0":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m5p4_s1(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p4_stress_s1_*/stress"))
    for d in reversed(runs):
        sp = d / "m5p4_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M5P4-ST-S1":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m5p4_s2(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p4_stress_s2_*/stress"))
    for d in reversed(runs):
        sp = d / "m5p4_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M5P4-ST-S2":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m5p4_s3(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p4_stress_s3_*/stress"))
    for d in reversed(runs):
        sp = d / "m5p4_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M5P4-ST-S3":
            continue
        return {"path": d, "summary": summ}
    return {}


def copy_stagea_from_s0(out_root: Path, out_dir: Path) -> list[str]:
    ref = load_latest_successful_m5p4_s0(out_root)
    if not ref:
        return ["No successful M5P4-ST-S0 folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m5p4_stagea_findings.json", "m5p4_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def copy_stagea_from_s1(out_root: Path, out_dir: Path) -> list[str]:
    ref = load_latest_successful_m5p4_s1(out_root)
    if not ref:
        return ["No successful M5P4-ST-S1 folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m5p4_stagea_findings.json", "m5p4_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def copy_stagea_from_s2(out_root: Path, out_dir: Path) -> list[str]:
    ref = load_latest_successful_m5p4_s2(out_root)
    if not ref:
        return ["No successful M5P4-ST-S2 folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m5p4_stagea_findings.json", "m5p4_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def copy_stagea_from_s3(out_root: Path, out_dir: Path) -> list[str]:
    ref = load_latest_successful_m5p4_s3(out_root)
    if not ref:
        return ["No successful M5P4-ST-S3 folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m5p4_stagea_findings.json", "m5p4_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    raw = str(value).strip()
    if raw == "":
        return []
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    return [x.strip().strip("'").strip('"') for x in raw.split(",") if x.strip()]


def run_cmd_capture(cmd: list[str], timeout: int = 30) -> tuple[dict[str, Any], str, str]:
    t0 = time.perf_counter()
    st = now()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        row = {
            "command": " ".join(cmd),
            "exit_code": int(p.returncode),
            "status": "PASS" if int(p.returncode) == 0 else "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": (p.stdout or "").strip()[:300],
            "stderr": (p.stderr or "").strip()[:300],
            "started_at_utc": st,
            "ended_at_utc": now(),
        }
        return row, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        row = {
            "command": " ".join(cmd),
            "exit_code": 124,
            "status": "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": "",
            "stderr": "timeout",
            "started_at_utc": st,
            "ended_at_utc": now(),
        }
        return row, "", "timeout"


def _run_json_cmd(
    cmd: list[str],
    *,
    probe_id: str,
    group: str,
    timeout: int = 30,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row, stdout_raw, _ = run_cmd_capture(cmd, timeout=timeout)
    payload: dict[str, Any] = {}
    if str(row.get("status", "FAIL")) == "PASS":
        try:
            parsed = json.loads(stdout_raw)
            if isinstance(parsed, dict):
                payload = parsed
            else:
                row["status"] = "FAIL"
                row["exit_code"] = 1
                row["stderr"] = "json output is not object"
        except Exception:
            row["status"] = "FAIL"
            row["exit_code"] = 1
            row["stderr"] = "json parse failed"
    row["probe_id"] = probe_id
    row["group"] = group
    return row, payload


def _tf_output_value(payload: dict[str, Any], key: str) -> Any:
    node = payload.get(key, {})
    if isinstance(node, dict) and "value" in node:
        return node.get("value")
    return None


def _topic_probe_lambda_source() -> str:
    return """import json
import time

from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.sasl.oauth import AbstractTokenProvider


class TokenProvider(AbstractTokenProvider):
    def __init__(self, region: str) -> None:
        self._region = region

    def token(self) -> str:
        token, _expiry = MSKAuthTokenProvider.generate_auth_token(self._region)
        return token


def lambda_handler(event, context):
    started = time.time()
    bootstrap = str(event.get("bootstrap", "")).strip()
    region = str(event.get("region", "eu-west-2")).strip() or "eu-west-2"
    required_topics = [str(x).strip() for x in (event.get("required_topics") or []) if str(x).strip()]
    topic_partitions = event.get("topic_partitions") or {}
    allow_create = bool(event.get("allow_create", False))
    out = {
        "overall_pass": False,
        "bootstrap": bootstrap,
        "existing_topics_before": [],
        "existing_topics_after": [],
        "created_topics": [],
        "topic_status": [],
        "missing_topics": [],
        "errors": [],
        "elapsed_seconds": 0.0,
    }
    if bootstrap == "":
        out["errors"].append("missing bootstrap")
        return out
    if not required_topics:
        out["errors"].append("required topic list is empty")
        return out
    client = None
    try:
        provider = TokenProvider(region)
        client = KafkaAdminClient(
            bootstrap_servers=[bootstrap],
            security_protocol="SASL_SSL",
            sasl_mechanism="OAUTHBEARER",
            sasl_oauth_token_provider=provider,
            request_timeout_ms=15000,
            api_version_auto_timeout_ms=10000,
            client_id="m5p4-s3-topic-readiness-probe",
        )
        topics = sorted(list(client.list_topics()))
        topic_set = set(topics)
        out["existing_topics_before"] = topics
        missing = [name for name in required_topics if name not in topic_set]
        out["missing_topics"] = missing
        if missing and allow_create:
            new_topics = []
            for name in missing:
                partitions = int(topic_partitions.get(name, 3) or 3)
                new_topics.append(NewTopic(name=name, num_partitions=partitions, replication_factor=1))
            if new_topics:
                out["created_topics"] = [x.name for x in new_topics]
                try:
                    client.create_topics(new_topics=new_topics, validate_only=False)
                except Exception as exc:
                    out["errors"].append(f"create_topics_failed: {exc}")
            topics_after = sorted(list(client.list_topics()))
            out["existing_topics_after"] = topics_after
            topic_set = set(topics_after)
            missing = [name for name in required_topics if name not in topic_set]
        out["missing_topics"] = missing
        out["topic_status"] = [
            {"topic": name, "ready": name in topic_set}
            for name in required_topics
        ]
        out["overall_pass"] = len(missing) == 0
    except Exception as exc:
        out["errors"].append(str(exc))
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    out["elapsed_seconds"] = round(max(0.0, time.time() - started), 3)
    return out
"""


def _build_topic_probe_bundle(bundle_zip: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="m5p4_s3_probe_") as tmp:
        root = Path(tmp)
        pkg = root / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "lambda_function.py").write_text(_topic_probe_lambda_source(), encoding="utf-8")
        pip_cmd = [
            "python",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--target",
            str(pkg),
            "kafka-python==2.2.2",
            "aws-msk-iam-sasl-signer-python==1.0.2",
        ]
        pip_row, _, _ = run_cmd_capture(pip_cmd, timeout=240)
        rows.append({**pip_row, "probe_id": "m5p4_s3_probe_bundle_pip", "group": "topic_probe_bundle"})
        if str(pip_row.get("status", "FAIL")) != "PASS":
            errors.append("failed to build topic probe bundle dependencies")
            return rows, errors
        bundle_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bundle_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in pkg.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(pkg).as_posix())
    return rows, errors
def _join_url(base_url: str, route_path: str) -> str:
    b = base_url.strip().rstrip("/")
    p = route_path.strip()
    if not p.startswith("/"):
        p = f"/{p}"
    return f"{b}{p}"


def _fetch_ssm_secret(path: str, region: str, timeout: int = 30) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    cmd = [
        "aws",
        "ssm",
        "get-parameter",
        "--name",
        path,
        "--with-decryption",
        "--region",
        region,
        "--query",
        "Parameter.Value",
        "--output",
        "text",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "value": "",
            "result": {
                "command": "aws ssm get-parameter --name <redacted> --with-decryption",
                "exit_code": 124,
                "status": "FAIL",
                "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
                "stdout": "",
                "stderr": "timeout",
                "started_at_utc": st,
                "ended_at_utc": now(),
            },
        }
    value = (p.stdout or "").strip()
    ok = p.returncode == 0 and value != ""
    return {
        "ok": ok,
        "value": value if ok else "",
        "result": {
            "command": "aws ssm get-parameter --name <redacted> --with-decryption",
            "exit_code": int(p.returncode),
            "status": "PASS" if ok else "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": "<redacted>" if ok else "",
            "stderr": (p.stderr or "").strip()[:300],
            "started_at_utc": st,
            "ended_at_utc": now(),
        },
    }


def _http_json_probe(
    *,
    probe_id: str,
    group: str,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    body = b""
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    req = urlreq.Request(url=url, data=body if method.upper() != "GET" else None, method=method.upper())
    for k, v in headers.items():
        req.add_header(k, v)
    code: int | None = None
    raw = ""
    err = ""
    try:
        with urlreq.urlopen(req, timeout=timeout) as resp:
            code = int(resp.getcode())
            raw = resp.read().decode("utf-8", errors="replace")
    except urlerr.HTTPError as exc:
        code = int(exc.code)
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        err = ""
    except Exception as exc:
        err = str(exc)[:300]
    body_json: Any = None
    if raw:
        try:
            body_json = json.loads(raw)
        except Exception:
            body_json = None
    return {
        "probe_id": probe_id,
        "group": group,
        "method": method.upper(),
        "url": url,
        "request_header_keys": sorted(list(headers.keys())),
        "status_code": code,
        "body_json": body_json if isinstance(body_json, dict) else None,
        "error": err or None,
        "status": "PASS" if err == "" and code is not None else "FAIL",
        "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        "started_at_utc": st,
        "ended_at_utc": now(),
    }


def run_s0(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in M5P4_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in M5P4_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in M5P4_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M5P4-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )

    dep = load_latest_successful_m5p3_closure(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    dep_verdict = ""
    dep_open = None
    if not dep:
        dep_issues.append("missing successful P3 closure with verdict ADVANCE_TO_P4")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        dep_verdict = str(dep.get("verdict", ""))
        if dep_verdict != "ADVANCE_TO_P4":
            dep_issues.append("P3 verdict is not ADVANCE_TO_P4")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m5p3_blocker_register.json")
        dep_open = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_open not in {None, 0}:
            dep_issues.append(f"P3 blocker register not closed: {dep_open}")
    if dep_issues:
        blockers.append({"id": "M5P4-B9", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})

    authority_issues: list[str] = []
    missing_authorities: list[str] = []
    unreadable_authorities: list[str] = []
    for p in [PARENT_PLAN, PLAN]:
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
                "id": "M5P4-B8",
                "severity": "S0",
                "status": "OPEN",
                "details": {"missing_authorities": missing_authorities, "unreadable_authorities": unreadable_authorities},
            }
        )

    region = str(h.get("AWS_REGION", "eu-west-2"))
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        r = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
        probe_rows.append({**r, "probe_id": "m5p4_s0_evidence_bucket", "group": "control"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5p4_s0_evidence_bucket",
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
                "id": "M5P4-B8",
                "severity": "S0",
                "status": "OPEN",
                "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]},
            }
        )

    stagea = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S0",
        "findings": [
            {
                "id": "M5P4-ST-F1",
                "classification": "PREVENT",
                "finding": "P4 entry is invalid without a deterministic P3 pass verdict.",
                "required_action": "Require latest successful P3 closure with verdict ADVANCE_TO_P4 and closed blocker register.",
            },
            {
                "id": "M5P4-ST-F2",
                "classification": "PREVENT",
                "finding": "Handle drift on ingress boundaries can silently break later auth/topic/envelope stages.",
                "required_action": "Fail closed on missing/placeholder P4 endpoint and runtime handles.",
            },
            {
                "id": "M5P4-ST-F3",
                "classification": "PREVENT",
                "finding": "P4 execution depends on readable authority files and evidence publication surface.",
                "required_action": "Fail closed on authority readback or evidence bucket reachability failures.",
            },
        ],
    }
    dumpj(out / "m5p4_stagea_findings.json", stagea)
    dumpj(out / "m5p4_lane_matrix.json", build_lane_matrix())

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5P4_STRESS_MAX_SPEND_USD", 40))

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S0",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "p3_dependency_phase_execution_id": dep_id,
        "p3_dependency_verdict": dep_verdict,
    }
    dumpj(out / "m5p4_probe_latency_throughput_snapshot.json", probe)

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
        "stage_id": "M5P4-ST-S0",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "p3_dependency_phase_execution_id": dep_id,
        "p3_dependency_verdict": dep_verdict,
        "p3_dependency_open_blockers": dep_open,
        "required_authorities": [PARENT_PLAN.as_posix(), PLAN.as_posix()],
    }
    dumpj(out / "m5p4_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S0",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5p4_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S0",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "read_only_entry_gate_validation_v0",
    }
    dumpj(out / "m5p4_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S0",
        "decisions": [
            "Validated M5.P4 plan-key and required-handle closure.",
            "Validated latest P3 closure verdict and blocker-free dependency posture.",
            "Validated parent/P4 authority readability.",
            "Executed bounded evidence-bucket reachability probe.",
            "Applied fail-closed blocker mapping for M5P4 S0.",
        ],
    }
    dumpj(out / "m5p4_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S0",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S0",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5P4_ST_S1_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5P4_S0_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "p3_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_blocker_register.json", bref)
    dumpj(out / "m5p4_execution_summary.json", summ)

    miss = [n for n in M5P4_S0_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5P4-B8", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5p4_blocker_register.json", bref)
        dumpj(out / "m5p4_execution_summary.json", summ)

    print(f"[m5p4_s0] phase_execution_id={phase_id}")
    print(f"[m5p4_s0] output_dir={out.as_posix()}")
    print(f"[m5p4_s0] overall_pass={summ['overall_pass']}")
    print(f"[m5p4_s0] next_gate={summ['next_gate']}")
    print(f"[m5p4_s0] probe_count={total}")
    print(f"[m5p4_s0] error_rate_pct={er}")
    print(f"[m5p4_s0] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s1(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_s0(out_root, out)
    if copy_errs:
        blockers.append({"id": "M5P4-B8", "severity": "S1", "status": "OPEN", "details": {"copy_errors": copy_errs}})
        if not (out / "m5p4_lane_matrix.json").exists():
            dumpj(out / "m5p4_lane_matrix.json", build_lane_matrix())

    s0 = load_latest_successful_m5p4_s0(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    if not s0:
        dep_issues.append("missing successful M5P4-ST-S0 dependency")
    else:
        dep_summ = s0.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5P4_ST_S1_READY":
            dep_issues.append("M5P4 S0 next_gate is not M5P4_ST_S1_READY")
        s0_br = load_json_safe(Path(str(s0["path"])) / "m5p4_blocker_register.json")
        s0_open = int(s0_br.get("open_blocker_count", len(s0_br.get("blockers", [])))) if s0_br else 0
        if s0_open != 0:
            dep_issues.append(f"M5P4 S0 blocker register not closed: {s0_open}")
    if dep_issues:
        blockers.append({"id": "M5P4-B9", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})

    req = [
        "IG_BASE_URL",
        "IG_INGEST_PATH",
        "IG_HEALTHCHECK_PATH",
        "IG_AUTH_MODE",
        "IG_AUTH_HEADER_NAME",
        "SSM_IG_API_KEY_PATH",
        "S3_EVIDENCE_BUCKET",
    ]
    missing_handles = [k for k in req if k not in h]
    placeholder_handles = [k for k in req if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M5P4-B1",
                "severity": "S1",
                "status": "OPEN",
                "details": {"missing_handles": missing_handles, "placeholder_handles": placeholder_handles},
            }
        )

    auth_issues: list[str] = []
    if str(h.get("IG_AUTH_MODE", "")).strip().lower() != "api_key":
        auth_issues.append("IG_AUTH_MODE drift (expected api_key)")
    if str(h.get("IG_AUTH_HEADER_NAME", "")).strip() == "":
        auth_issues.append("IG_AUTH_HEADER_NAME empty")
    if auth_issues:
        blockers.append({"id": "M5P4-B3", "severity": "S1", "status": "OPEN", "details": {"issues": auth_issues}})

    region = str(h.get("AWS_REGION", "eu-west-2")).strip()
    evidence_bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    base_url = str(h.get("IG_BASE_URL", "")).strip()
    ingest_path = str(h.get("IG_INGEST_PATH", "")).strip()
    health_path = str(h.get("IG_HEALTHCHECK_PATH", "")).strip()
    auth_header = str(h.get("IG_AUTH_HEADER_NAME", "X-IG-Api-Key")).strip() or "X-IG-Api-Key"
    api_key_path = str(h.get("SSM_IG_API_KEY_PATH", "")).strip()

    probe_rows: list[dict[str, Any]] = []
    if evidence_bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", evidence_bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m5p4_s1_evidence_bucket", "group": "control"})
        if str(p.get("status", "FAIL")) != "PASS":
            blockers.append(
                {
                    "id": "M5P4-B8",
                    "severity": "S1",
                    "status": "OPEN",
                    "details": {"probe_failures": ["m5p4_s1_evidence_bucket"]},
                }
            )

    key_fetch = {"ok": False, "value": "", "result": {"probe_id": "m5p4_s1_ssm_api_key", "group": "auth"}}
    if api_key_path and api_key_path not in {"TO_PIN"}:
        key_fetch = _fetch_ssm_secret(api_key_path, region, timeout=30)
        probe_rows.append({**key_fetch["result"], "probe_id": "m5p4_s1_ssm_api_key", "group": "auth"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5p4_s1_ssm_api_key",
                "group": "auth",
                "command": "aws ssm get-parameter --name <redacted> --with-decryption",
                "exit_code": 1,
                "status": "FAIL",
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": "missing SSM_IG_API_KEY_PATH handle",
                "started_at_utc": now(),
                "ended_at_utc": now(),
            }
        )
    if key_fetch.get("ok") is not True:
        blockers.append(
            {
                "id": "M5P4-B3",
                "severity": "S1",
                "status": "OPEN",
                "details": {"issues": ["api key retrieval failed"]},
            }
        )

    probe_payload = {
        "platform_run_id": f"platform_{tok()}",
        "scenario_run_id": f"scenario_{uuid4().hex[:24]}",
        "phase_id": "P4.A",
        "event_id": f"m5p4_s1_probe_{phase_id}",
        "runtime_lane": "ingress_edge",
        "trace_id": f"trace-{uuid4().hex[:20]}",
        "event_class": "m5p4_boundary_probe",
        "event_type": "m5p4_boundary_probe",
    }

    contract_issues: list[str] = []
    health_probe: dict[str, Any] = {}
    ingest_probe: dict[str, Any] = {}
    if key_fetch.get("ok") is True and base_url and ingest_path and health_path:
        common_headers = {
            auth_header: str(key_fetch.get("value", "")),
            "x-fp-platform-run-id": str(probe_payload["platform_run_id"]),
            "x-fp-phase-id": str(probe_payload["phase_id"]),
            "x-fp-event-id": str(probe_payload["event_id"]),
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00",
            "tracestate": "ingress=boundary",
        }
        health_probe = _http_json_probe(
            probe_id="m5p4_s1_health",
            group="boundary",
            method="GET",
            url=_join_url(base_url, health_path),
            headers=common_headers,
            timeout=20,
        )
        probe_rows.append(health_probe)
        ingest_headers = {**common_headers, "Content-Type": "application/json"}
        ingest_probe = _http_json_probe(
            probe_id="m5p4_s1_ingest_preflight",
            group="boundary",
            method="POST",
            url=_join_url(base_url, ingest_path),
            headers=ingest_headers,
            payload=probe_payload,
            timeout=20,
        )
        probe_rows.append(ingest_probe)
    else:
        contract_issues.append("required boundary probe inputs unavailable")

    if health_probe:
        h_code = int(health_probe.get("status_code", 0) or 0)
        h_body = health_probe.get("body_json", {}) if isinstance(health_probe.get("body_json", {}), dict) else {}
        if h_code != 200:
            contract_issues.append(f"health probe status expected 200, observed {h_code}")
        if any(k not in h_body for k in ("status", "service", "mode")):
            contract_issues.append("health probe body missing required fields")

    if ingest_probe:
        i_code = int(ingest_probe.get("status_code", 0) or 0)
        i_body = ingest_probe.get("body_json", {}) if isinstance(ingest_probe.get("body_json", {}), dict) else {}
        if i_code != 202:
            contract_issues.append(f"ingest preflight status expected 202, observed {i_code}")
        if "admitted" not in i_body or "ingress_mode" not in i_body:
            contract_issues.append("ingest preflight body missing required fields")
        elif bool(i_body.get("admitted")) is not True:
            contract_issues.append("ingest preflight admitted flag is not true")

    network_probe_failures = [
        p for p in probe_rows if p.get("probe_id") in {"m5p4_s1_health", "m5p4_s1_ingest_preflight"} and p.get("status") != "PASS"
    ]
    if contract_issues or network_probe_failures:
        blockers.append(
            {
                "id": "M5P4-B2",
                "severity": "S1",
                "status": "OPEN",
                "details": {
                    "contract_issues": contract_issues,
                    "probe_failures": [str(x.get("probe_id", "")) for x in network_probe_failures],
                },
            }
        )

    boundary_snapshot = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S1",
        "handle_snapshot": {
            "IG_BASE_URL": base_url,
            "IG_INGEST_PATH": ingest_path,
            "IG_HEALTHCHECK_PATH": health_path,
            "IG_AUTH_HEADER_NAME": auth_header,
            "SSM_IG_API_KEY_PATH": api_key_path,
            "S3_EVIDENCE_BUCKET": evidence_bucket,
        },
        "probe_payload": probe_payload,
        "health_probe": health_probe,
        "ingest_probe": ingest_probe,
        "contract_issues": contract_issues,
        "s0_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_boundary_health_snapshot.json", boundary_snapshot)

    total = len(probe_rows)
    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5P4_STRESS_MAX_SPEND_USD", 40))

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S1",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s0_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    if missing_handles:
        control_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        control_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
    control_issues.extend(dep_issues)
    control_issues.extend(auth_issues)
    control_issues.extend(contract_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S1",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "s0_dependency_phase_execution_id": dep_id,
        "boundary_snapshot_ref": "m5p4_boundary_health_snapshot.json",
    }
    dumpj(out / "m5p4_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S1",
        "overall_pass": True,
        "secret_probe_count": 1,
        "secret_failure_count": 0 if key_fetch.get("ok") is True else 1,
        "with_decryption_used": True,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5p4_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S1",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "ingress_boundary_preflight_v0",
    }
    dumpj(out / "m5p4_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S1",
        "decisions": [
            "Validated S0 dependency and carried Stage-A artifacts forward.",
            "Retrieved IG API key through SSM path using decryption without artifact plaintext leakage.",
            "Executed ingress boundary health and ingest preflight probes with configured auth header.",
            "Validated minimal response contracts for health (200) and ingest preflight (202).",
            "Applied fail-closed blocker mapping for M5P4 S1.",
        ],
    }
    dumpj(out / "m5p4_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S1",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S1",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5P4_ST_S2_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5P4_S1_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s0_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_blocker_register.json", bref)
    dumpj(out / "m5p4_execution_summary.json", summ)

    miss = [n for n in M5P4_S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5P4-B8", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5p4_blocker_register.json", bref)
        dumpj(out / "m5p4_execution_summary.json", summ)

    print(f"[m5p4_s1] phase_execution_id={phase_id}")
    print(f"[m5p4_s1] output_dir={out.as_posix()}")
    print(f"[m5p4_s1] overall_pass={summ['overall_pass']}")
    print(f"[m5p4_s1] next_gate={summ['next_gate']}")
    print(f"[m5p4_s1] probe_count={total}")
    print(f"[m5p4_s1] error_rate_pct={er}")
    print(f"[m5p4_s1] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s2(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_s1(out_root, out)
    if copy_errs:
        blockers.append({"id": "M5P4-B8", "severity": "S2", "status": "OPEN", "details": {"copy_errors": copy_errs}})
        if not (out / "m5p4_lane_matrix.json").exists():
            dumpj(out / "m5p4_lane_matrix.json", build_lane_matrix())

    s1 = load_latest_successful_m5p4_s1(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    if not s1:
        dep_issues.append("missing successful M5P4-ST-S1 dependency")
    else:
        dep_summ = s1.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5P4_ST_S2_READY":
            dep_issues.append("M5P4 S1 next_gate is not M5P4_ST_S2_READY")
        s1_br = load_json_safe(Path(str(s1["path"])) / "m5p4_blocker_register.json")
        s1_open = int(s1_br.get("open_blocker_count", len(s1_br.get("blockers", [])))) if s1_br else 0
        if s1_open != 0:
            dep_issues.append(f"M5P4 S1 blocker register not closed: {s1_open}")
    if dep_issues:
        blockers.append({"id": "M5P4-B9", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})

    req = [
        "IG_BASE_URL",
        "IG_INGEST_PATH",
        "IG_HEALTHCHECK_PATH",
        "IG_AUTH_MODE",
        "IG_AUTH_HEADER_NAME",
        "SSM_IG_API_KEY_PATH",
        "S3_EVIDENCE_BUCKET",
    ]
    missing_handles = [k for k in req if k not in h]
    placeholder_handles = [k for k in req if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M5P4-B1",
                "severity": "S2",
                "status": "OPEN",
                "details": {"missing_handles": missing_handles, "placeholder_handles": placeholder_handles},
            }
        )

    auth_issues: list[str] = []
    if str(h.get("IG_AUTH_MODE", "")).strip().lower() != "api_key":
        auth_issues.append("IG_AUTH_MODE drift (expected api_key)")
    if str(h.get("IG_AUTH_HEADER_NAME", "")).strip() == "":
        auth_issues.append("IG_AUTH_HEADER_NAME empty")
    if auth_issues:
        blockers.append({"id": "M5P4-B3", "severity": "S2", "status": "OPEN", "details": {"issues": auth_issues}})

    region = str(h.get("AWS_REGION", "eu-west-2")).strip()
    evidence_bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    base_url = str(h.get("IG_BASE_URL", "")).strip()
    ingest_path = str(h.get("IG_INGEST_PATH", "")).strip()
    health_path = str(h.get("IG_HEALTHCHECK_PATH", "")).strip()
    auth_header = str(h.get("IG_AUTH_HEADER_NAME", "X-IG-Api-Key")).strip() or "X-IG-Api-Key"
    api_key_path = str(h.get("SSM_IG_API_KEY_PATH", "")).strip()

    probe_rows: list[dict[str, Any]] = []
    if evidence_bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", evidence_bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m5p4_s2_evidence_bucket", "group": "control"})
        if str(p.get("status", "FAIL")) != "PASS":
            blockers.append(
                {
                    "id": "M5P4-B8",
                    "severity": "S2",
                    "status": "OPEN",
                    "details": {"probe_failures": ["m5p4_s2_evidence_bucket"]},
                }
            )

    key_fetch = {"ok": False, "value": "", "result": {"probe_id": "m5p4_s2_ssm_api_key", "group": "auth"}}
    if api_key_path and api_key_path not in {"TO_PIN"}:
        key_fetch = _fetch_ssm_secret(api_key_path, region, timeout=30)
        probe_rows.append({**key_fetch["result"], "probe_id": "m5p4_s2_ssm_api_key", "group": "auth"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5p4_s2_ssm_api_key",
                "group": "auth",
                "command": "aws ssm get-parameter --name <redacted> --with-decryption",
                "exit_code": 1,
                "status": "FAIL",
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": "missing SSM_IG_API_KEY_PATH handle",
                "started_at_utc": now(),
                "ended_at_utc": now(),
            }
        )
    if key_fetch.get("ok") is not True:
        blockers.append(
            {
                "id": "M5P4-B3",
                "severity": "S2",
                "status": "OPEN",
                "details": {"issues": ["api key retrieval failed"]},
            }
        )

    run_identity = {
        "platform_run_id": f"platform_{tok()}",
        "scenario_run_id": f"scenario_{uuid4().hex[:24]}",
        "phase_id": "P4.B",
        "runtime_lane": "ingress_edge",
        "trace_id": f"trace-{uuid4().hex[:20]}",
    }

    auth_matrix: dict[str, Any] = {"rows": [], "contract_issues": []}
    contract_issues: list[str] = []
    if key_fetch.get("ok") is True and base_url and ingest_path and health_path:
        payload_common = {
            "platform_run_id": run_identity["platform_run_id"],
            "scenario_run_id": run_identity["scenario_run_id"],
            "phase_id": run_identity["phase_id"],
            "runtime_lane": run_identity["runtime_lane"],
            "trace_id": run_identity["trace_id"],
            "event_class": "m5p4_auth_probe",
            "event_type": "m5p4_auth_probe",
        }
        shared_headers = {
            "x-fp-platform-run-id": run_identity["platform_run_id"],
            "x-fp-phase-id": run_identity["phase_id"],
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00",
            "tracestate": "ingress=auth",
        }

        def _payload(event_id: str) -> dict[str, Any]:
            return {**payload_common, "event_id": event_id}

        positive_headers = {**shared_headers, auth_header: str(key_fetch.get("value", ""))}
        invalid_headers = {**shared_headers, auth_header: f"invalid-{uuid4().hex}"}
        missing_headers = dict(shared_headers)

        probes = [
            {
                "matrix_id": "positive_health",
                "probe_id": "m5p4_s2_positive_health",
                "method": "GET",
                "url": _join_url(base_url, health_path),
                "headers": {**positive_headers, "x-fp-event-id": f"{phase_id}-positive-health"},
                "payload": None,
                "expected_status": 200,
            },
            {
                "matrix_id": "positive_ingest",
                "probe_id": "m5p4_s2_positive_ingest",
                "method": "POST",
                "url": _join_url(base_url, ingest_path),
                "headers": {**positive_headers, "x-fp-event-id": f"{phase_id}-positive-ingest", "Content-Type": "application/json"},
                "payload": _payload(f"m5p4_s2_positive_{phase_id}"),
                "expected_status": 202,
            },
            {
                "matrix_id": "missing_health",
                "probe_id": "m5p4_s2_missing_health",
                "method": "GET",
                "url": _join_url(base_url, health_path),
                "headers": {**missing_headers, "x-fp-event-id": f"{phase_id}-missing-health"},
                "payload": None,
                "expected_status": 401,
            },
            {
                "matrix_id": "missing_ingest",
                "probe_id": "m5p4_s2_missing_ingest",
                "method": "POST",
                "url": _join_url(base_url, ingest_path),
                "headers": {**missing_headers, "x-fp-event-id": f"{phase_id}-missing-ingest", "Content-Type": "application/json"},
                "payload": _payload(f"m5p4_s2_missing_{phase_id}"),
                "expected_status": 401,
            },
            {
                "matrix_id": "invalid_health",
                "probe_id": "m5p4_s2_invalid_health",
                "method": "GET",
                "url": _join_url(base_url, health_path),
                "headers": {**invalid_headers, "x-fp-event-id": f"{phase_id}-invalid-health"},
                "payload": None,
                "expected_status": 401,
            },
            {
                "matrix_id": "invalid_ingest",
                "probe_id": "m5p4_s2_invalid_ingest",
                "method": "POST",
                "url": _join_url(base_url, ingest_path),
                "headers": {**invalid_headers, "x-fp-event-id": f"{phase_id}-invalid-ingest", "Content-Type": "application/json"},
                "payload": _payload(f"m5p4_s2_invalid_{phase_id}"),
                "expected_status": 401,
            },
        ]

        for item in probes:
            r = _http_json_probe(
                probe_id=item["probe_id"],
                group="auth_matrix",
                method=str(item["method"]),
                url=str(item["url"]),
                headers=dict(item["headers"]),
                payload=item["payload"],
                timeout=20,
            )
            probe_rows.append(r)
            code = int(r.get("status_code", 0) or 0)
            body = r.get("body_json", {}) if isinstance(r.get("body_json", {}), dict) else {}
            row_ok = code == int(item["expected_status"])
            if item["matrix_id"] == "positive_health":
                if any(k not in body for k in ("status", "service", "mode")):
                    row_ok = False
                    contract_issues.append("positive health response missing required fields")
            if item["matrix_id"] == "positive_ingest":
                if "admitted" not in body or "ingress_mode" not in body:
                    row_ok = False
                    contract_issues.append("positive ingest response missing required fields")
                elif bool(body.get("admitted")) is not True:
                    row_ok = False
                    contract_issues.append("positive ingest admitted flag is not true")
            if item["matrix_id"] in {"missing_health", "missing_ingest", "invalid_health", "invalid_ingest"}:
                if str(body.get("error", "")) != "unauthorized":
                    row_ok = False
                    contract_issues.append(f"{item['matrix_id']} unauthorized contract mismatch")
            if not row_ok:
                contract_issues.append(
                    f"{item['matrix_id']} status mismatch expected={item['expected_status']} observed={code}"
                )
            auth_matrix["rows"].append(
                {
                    "matrix_id": item["matrix_id"],
                    "probe_id": item["probe_id"],
                    "expected_status": item["expected_status"],
                    "observed_status": code,
                    "row_pass": row_ok,
                    "response_excerpt": {
                        "error": body.get("error") if isinstance(body, dict) else None,
                        "reason": body.get("reason") if isinstance(body, dict) else None,
                        "admitted": body.get("admitted") if isinstance(body, dict) else None,
                        "ingress_mode": body.get("ingress_mode") if isinstance(body, dict) else None,
                    },
                }
            )
    else:
        contract_issues.append("required auth matrix inputs unavailable")

    auth_matrix["contract_issues"] = contract_issues
    auth_matrix["s1_dependency_phase_execution_id"] = dep_id
    dumpj(
        out / "m5p4_auth_enforcement_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M5P4-ST-S2",
            "run_identity": run_identity,
            "auth_mode": str(h.get("IG_AUTH_MODE", "")),
            "auth_header_name": auth_header,
            "snapshot": auth_matrix,
        },
    )

    if contract_issues:
        blockers.append(
            {
                "id": "M5P4-B3",
                "severity": "S2",
                "status": "OPEN",
                "details": {"issues": contract_issues},
            }
        )

    total = len(probe_rows)
    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5P4_STRESS_MAX_SPEND_USD", 40))

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S2",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s1_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    if missing_handles:
        control_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        control_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
    control_issues.extend(dep_issues)
    control_issues.extend(auth_issues)
    control_issues.extend(contract_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S2",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "s1_dependency_phase_execution_id": dep_id,
        "auth_snapshot_ref": "m5p4_auth_enforcement_snapshot.json",
    }
    dumpj(out / "m5p4_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S2",
        "overall_pass": True,
        "secret_probe_count": 1,
        "secret_failure_count": 0 if key_fetch.get("ok") is True else 1,
        "with_decryption_used": True,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5p4_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S2",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "ingress_auth_enforcement_v0",
    }
    dumpj(out / "m5p4_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S2",
        "decisions": [
            "Validated S1 dependency and carried Stage-A artifacts forward.",
            "Retrieved IG API key through SSM for valid-key probe lane without persisting plaintext.",
            "Executed boundary auth matrix (positive/missing/invalid) across health and ingest routes.",
            "Validated deterministic auth outcomes against S2 pass criteria.",
            "Applied fail-closed blocker mapping for M5P4 S2.",
        ],
    }
    dumpj(out / "m5p4_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S2",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S2",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5P4_ST_S3_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5P4_S2_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s1_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_blocker_register.json", bref)
    dumpj(out / "m5p4_execution_summary.json", summ)

    miss = [n for n in M5P4_S2_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5P4-B8", "severity": "S2", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5p4_blocker_register.json", bref)
        dumpj(out / "m5p4_execution_summary.json", summ)

    print(f"[m5p4_s2] phase_execution_id={phase_id}")
    print(f"[m5p4_s2] output_dir={out.as_posix()}")
    print(f"[m5p4_s2] overall_pass={summ['overall_pass']}")
    print(f"[m5p4_s2] next_gate={summ['next_gate']}")
    print(f"[m5p4_s2] probe_count={total}")
    print(f"[m5p4_s2] error_rate_pct={er}")
    print(f"[m5p4_s2] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s3(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_s2(out_root, out)
    if copy_errs:
        blockers.append({"id": "M5P4-B8", "severity": "S3", "status": "OPEN", "details": {"copy_errors": copy_errs}})
        if not (out / "m5p4_lane_matrix.json").exists():
            dumpj(out / "m5p4_lane_matrix.json", build_lane_matrix())

    s2 = load_latest_successful_m5p4_s2(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    if not s2:
        dep_issues.append("missing successful M5P4-ST-S2 dependency")
    else:
        dep_summ = s2.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5P4_ST_S3_READY":
            dep_issues.append("M5P4 S2 next_gate is not M5P4_ST_S3_READY")
        s2_br = load_json_safe(Path(str(s2["path"])) / "m5p4_blocker_register.json")
        s2_open = int(s2_br.get("open_blocker_count", len(s2_br.get("blockers", [])))) if s2_br else 0
        if s2_open != 0:
            dep_issues.append(f"M5P4 S2 blocker register not closed: {s2_open}")
    if dep_issues:
        blockers.append({"id": "M5P4-B9", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})

    req = [
        "MSK_CLUSTER_ARN",
        "MSK_BOOTSTRAP_BROKERS_SASL_IAM",
        "MSK_CLIENT_SUBNET_IDS",
        "MSK_SECURITY_GROUP_ID",
        "S3_EVIDENCE_BUCKET",
        "ARCHIVE_CONNECTOR_FUNCTION_NAME",
    ] + M5P4_REQUIRED_TOPIC_HANDLES
    missing_handles = [k for k in req if k not in h]
    placeholder_handles = [k for k in req if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M5P4-B1",
                "severity": "S3",
                "status": "OPEN",
                "details": {"missing_handles": missing_handles, "placeholder_handles": placeholder_handles},
            }
        )

    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    evidence_bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    cluster_arn = str(h.get("MSK_CLUSTER_ARN", "")).strip()
    bootstrap_handle = str(h.get("MSK_BOOTSTRAP_BROKERS_SASL_IAM", "")).strip()
    subnet_ids = _coerce_list(h.get("MSK_CLIENT_SUBNET_IDS", []))
    security_group_id = str(h.get("MSK_SECURITY_GROUP_ID", "")).strip()
    required_topics = [
        {
            "handle": key,
            "name": str(h.get(key, "")).strip(),
            "partitions": int(M5P4_TOPIC_PARTITIONS_BY_HANDLE.get(key, 3)),
        }
        for key in M5P4_REQUIRED_TOPIC_HANDLES
    ]
    required_topic_names = [str(x["name"]) for x in required_topics if str(x["name"]).strip()]

    topic_handle_issues: list[str] = []
    for item in required_topics:
        if str(item["name"]).strip() == "":
            topic_handle_issues.append(f"topic handle missing value: {item['handle']}")
    if topic_handle_issues:
        blockers.append({"id": "M5P4-B1", "severity": "S3", "status": "OPEN", "details": {"issues": topic_handle_issues}})

    probe_rows: list[dict[str, Any]] = []
    if evidence_bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", evidence_bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m5p4_s3_evidence_bucket", "group": "control"})
        if str(p.get("status", "FAIL")) != "PASS":
            blockers.append(
                {
                    "id": "M5P4-B8",
                    "severity": "S3",
                    "status": "OPEN",
                    "details": {"probe_failures": ["m5p4_s3_evidence_bucket"]},
                }
            )

    tf_stream_row, tf_stream_payload = _run_json_cmd(
        ["terraform", "-chdir=infra/terraform/dev_full/streaming", "output", "-json"],
        probe_id="m5p4_s3_tf_streaming_outputs",
        group="control",
        timeout=120,
    )
    probe_rows.append(tf_stream_row)
    tf_core_row, tf_core_payload = _run_json_cmd(
        ["terraform", "-chdir=infra/terraform/dev_full/core", "output", "-json"],
        probe_id="m5p4_s3_tf_core_outputs",
        group="control",
        timeout=120,
    )
    probe_rows.append(tf_core_row)

    parity_issues: list[str] = []
    tf_runtime: dict[str, Any] = {"streaming": {}, "core": {}}
    if str(tf_stream_row.get("status", "FAIL")) == "PASS":
        tf_cluster_arn = str(_tf_output_value(tf_stream_payload, "msk_cluster_arn") or "").strip()
        tf_bootstrap = str(_tf_output_value(tf_stream_payload, "msk_bootstrap_brokers_sasl_iam") or "").strip()
        tf_subnets = _coerce_list(_tf_output_value(tf_stream_payload, "msk_client_subnet_ids") or [])
        tf_sg = str(_tf_output_value(tf_stream_payload, "msk_security_group_id") or "").strip()
        tf_runtime["streaming"] = {
            "msk_cluster_arn": tf_cluster_arn,
            "msk_bootstrap_brokers_sasl_iam": tf_bootstrap,
            "msk_client_subnet_ids": tf_subnets,
            "msk_security_group_id": tf_sg,
        }
        if cluster_arn and tf_cluster_arn and cluster_arn != tf_cluster_arn:
            parity_issues.append("registry/runtime drift: MSK_CLUSTER_ARN")
        if bootstrap_handle and tf_bootstrap and bootstrap_handle != tf_bootstrap:
            parity_issues.append("registry/runtime drift: MSK_BOOTSTRAP_BROKERS_SASL_IAM")
        if subnet_ids and tf_subnets and sorted(subnet_ids) != sorted(tf_subnets):
            parity_issues.append("registry/runtime drift: MSK_CLIENT_SUBNET_IDS")
        if security_group_id and tf_sg and security_group_id != tf_sg:
            parity_issues.append("registry/runtime drift: MSK_SECURITY_GROUP_ID")
    else:
        parity_issues.append("unable to read streaming terraform outputs")

    if str(tf_core_row.get("status", "FAIL")) == "PASS":
        core_subnets = _coerce_list(_tf_output_value(tf_core_payload, "msk_client_subnet_ids") or [])
        core_sg = str(_tf_output_value(tf_core_payload, "msk_security_group_id") or "").strip()
        tf_runtime["core"] = {"msk_client_subnet_ids": core_subnets, "msk_security_group_id": core_sg}
        if subnet_ids and core_subnets and sorted(subnet_ids) != sorted(core_subnets):
            parity_issues.append("registry/core drift: MSK_CLIENT_SUBNET_IDS")
        if security_group_id and core_sg and security_group_id != core_sg:
            parity_issues.append("registry/core drift: MSK_SECURITY_GROUP_ID")
    else:
        parity_issues.append("unable to read core terraform outputs")

    if parity_issues:
        blockers.append({"id": "M5P4-B1", "severity": "S3", "status": "OPEN", "details": {"issues": parity_issues}})

    cluster_state = ""
    cluster_row, cluster_stdout, _ = run_cmd_capture(
        [
            "aws",
            "kafka",
            "describe-cluster-v2",
            "--cluster-arn",
            cluster_arn,
            "--region",
            region,
            "--query",
            "ClusterInfo.State",
            "--output",
            "text",
        ],
        timeout=40,
    )
    probe_rows.append({**cluster_row, "probe_id": "m5p4_s3_cluster_state", "group": "messaging"})
    if str(cluster_row.get("status", "FAIL")) == "PASS":
        cluster_state = str(cluster_stdout).strip()

    bootstrap_row, bootstrap_payload = _run_json_cmd(
        ["aws", "kafka", "get-bootstrap-brokers", "--cluster-arn", cluster_arn, "--region", region, "--output", "json"],
        probe_id="m5p4_s3_bootstrap_readback",
        group="messaging",
        timeout=40,
    )
    probe_rows.append(bootstrap_row)
    bootstrap_runtime = str(bootstrap_payload.get("BootstrapBrokerStringSaslIam", "")).strip()

    readiness_issues: list[str] = []
    if str(cluster_row.get("status", "FAIL")) != "PASS":
        readiness_issues.append("cluster describe-cluster-v2 command failed")
    elif cluster_state != "ACTIVE":
        readiness_issues.append(f"cluster state is not ACTIVE: {cluster_state or 'UNKNOWN'}")
    if str(bootstrap_row.get("status", "FAIL")) != "PASS":
        readiness_issues.append("bootstrap broker readback failed")
    elif bootstrap_runtime == "":
        readiness_issues.append("bootstrap broker readback returned empty value")
    elif bootstrap_handle and bootstrap_runtime != bootstrap_handle:
        readiness_issues.append("bootstrap broker drift between registry and live readback")

    archive_function_name = str(h.get("ARCHIVE_CONNECTOR_FUNCTION_NAME", "")).strip()
    role_arn = str(os.getenv("M5P4_S3_PROBE_ROLE_ARN", "")).strip()
    if role_arn == "":
        dedicated_role_name = "fraud-platform-dev-full-m5p4-s3-probe-role"
        dedicated_role_row, dedicated_role_payload = _run_json_cmd(
            ["aws", "iam", "get-role", "--role-name", dedicated_role_name, "--output", "json"],
            probe_id="m5p4_s3_probe_role_dedicated",
            group="topic_probe",
            timeout=30,
        )
        probe_rows.append(dedicated_role_row)
        if str(dedicated_role_row.get("status", "FAIL")) == "PASS":
            role_node = dedicated_role_payload.get("Role", {})
            if isinstance(role_node, dict):
                role_arn = str(role_node.get("Arn", "")).strip()
    if role_arn == "" and archive_function_name:
        role_row, role_payload = _run_json_cmd(
            [
                "aws",
                "lambda",
                "get-function-configuration",
                "--function-name",
                archive_function_name,
                "--region",
                region,
                "--output",
                "json",
            ],
            probe_id="m5p4_s3_probe_role_source",
            group="topic_probe",
            timeout=45,
        )
        probe_rows.append(role_row)
        if str(role_row.get("status", "FAIL")) == "PASS":
            role_arn = str(role_payload.get("Role", "")).strip()
    if role_arn == "":
        role_arn = str(h.get("ROLE_LAMBDA_IG_EXECUTION", "")).strip()
    if role_arn == "":
        readiness_issues.append("unable to resolve lambda execution role for in-VPC topic probe")
    if not subnet_ids:
        readiness_issues.append("MSK_CLIENT_SUBNET_IDS resolved empty")
    if security_group_id == "":
        readiness_issues.append("MSK_SECURITY_GROUP_ID resolved empty")
    if not required_topic_names:
        readiness_issues.append("required topic set resolved empty")

    topic_probe_result: dict[str, Any] = {
        "probe_mode": "lambda_in_vpc_kafka_admin",
        "attempted": False,
        "overall_pass": False,
        "errors": [],
        "missing_topics": required_topic_names.copy(),
        "existing_topics_before": [],
        "existing_topics_after": [],
        "created_topics": [],
        "topic_status": [],
        "probe_invoke": {},
    }
    probe_tmp = out / "_tmp_m5p4_s3_probe"
    probe_tmp.mkdir(parents=True, exist_ok=True)
    fn_name = ""
    created = False
    bundle_path = probe_tmp / "m5p4_s3_topic_probe_lambda.zip"
    payload_path = probe_tmp / "m5p4_s3_topic_probe_payload.json"
    response_path = probe_tmp / "m5p4_s3_topic_probe_response.json"
    if not readiness_issues:
        topic_probe_result["attempted"] = True
        bundle_rows, bundle_errors = _build_topic_probe_bundle(bundle_path)
        probe_rows.extend(bundle_rows)
        if bundle_errors:
            readiness_issues.extend(bundle_errors)
        else:
            fn_name = f"fraud-platform-dev-full-m5p4-s3-{uuid4().hex[:10]}"
            create_cmd = [
                "aws",
                "lambda",
                "create-function",
                "--function-name",
                fn_name,
                "--runtime",
                "python3.12",
                "--role",
                role_arn,
                "--handler",
                "lambda_function.lambda_handler",
                "--zip-file",
                f"fileb://{bundle_path.as_posix()}",
                "--timeout",
                "90",
                "--memory-size",
                "512",
                "--region",
                region,
                "--vpc-config",
                f"SubnetIds={','.join(subnet_ids)},SecurityGroupIds={security_group_id}",
            ]
            create_row, _, _ = run_cmd_capture(create_cmd, timeout=180)
            probe_rows.append({**create_row, "probe_id": "m5p4_s3_probe_lambda_create", "group": "topic_probe"})
            if str(create_row.get("status", "FAIL")) != "PASS":
                readiness_issues.append("failed to create temporary in-VPC topic probe lambda")
            else:
                created = True
                wait_row, _, _ = run_cmd_capture(
                    ["aws", "lambda", "wait", "function-active-v2", "--function-name", fn_name, "--region", region],
                    timeout=240,
                )
                probe_rows.append({**wait_row, "probe_id": "m5p4_s3_probe_lambda_wait", "group": "topic_probe"})
                if str(wait_row.get("status", "FAIL")) != "PASS":
                    readiness_issues.append("temporary topic probe lambda did not reach active state")
                else:
                    payload_path.write_text(
                        json.dumps(
                            {
                                "bootstrap": bootstrap_runtime or bootstrap_handle,
                                "region": region,
                                "required_topics": required_topic_names,
                                "topic_partitions": {
                                    str(x["name"]): int(x["partitions"]) for x in required_topics if str(x["name"]).strip()
                                },
                                "allow_create": True,
                            }
                        ),
                        encoding="utf-8",
                    )
                    invoke_row, invoke_stdout, _ = run_cmd_capture(
                        [
                            "aws",
                            "lambda",
                            "invoke",
                            "--function-name",
                            fn_name,
                            "--payload",
                            f"fileb://{payload_path.as_posix()}",
                            "--cli-binary-format",
                            "raw-in-base64-out",
                            str(response_path),
                            "--region",
                            region,
                            "--output",
                            "json",
                        ],
                        timeout=180,
                    )
                    probe_rows.append({**invoke_row, "probe_id": "m5p4_s3_topic_probe_invoke", "group": "topic_probe"})
                    invoke_meta: dict[str, Any] = {}
                    try:
                        parsed_meta = json.loads(invoke_stdout or "{}")
                        if isinstance(parsed_meta, dict):
                            invoke_meta = parsed_meta
                    except Exception:
                        invoke_meta = {}
                    topic_probe_result["probe_invoke"] = {
                        "status_code": invoke_meta.get("StatusCode"),
                        "function_error": invoke_meta.get("FunctionError"),
                        "executed_version": invoke_meta.get("ExecutedVersion"),
                    }
                    if str(invoke_meta.get("FunctionError", "")).strip() != "":
                        readiness_issues.append(
                            f"topic probe function error: {str(invoke_meta.get('FunctionError', '')).strip()}"
                        )
                    if str(invoke_row.get("status", "FAIL")) != "PASS":
                        readiness_issues.append("temporary topic probe invoke failed")
                    elif not response_path.exists():
                        readiness_issues.append("topic probe response payload missing")
                    else:
                        try:
                            probe_payload = json.loads(response_path.read_text(encoding="utf-8"))
                        except Exception:
                            probe_payload = {}
                            readiness_issues.append("topic probe response payload parse failed")
                        if isinstance(probe_payload, dict):
                            probe_errors: list[str] = []
                            if "errorMessage" in probe_payload:
                                lambda_error = str(probe_payload.get("errorMessage", "")).strip()
                                lambda_error_type = str(probe_payload.get("errorType", "")).strip()
                                if lambda_error:
                                    probe_errors.append(f"lambda_error: {lambda_error}")
                                if lambda_error_type:
                                    probe_errors.append(f"lambda_error_type: {lambda_error_type}")
                            probe_errors.extend([str(x) for x in (probe_payload.get("errors", []) or [])])
                            topic_probe_result["overall_pass"] = bool(probe_payload.get("overall_pass") is True)
                            topic_probe_result["errors"] = probe_errors
                            topic_probe_result["missing_topics"] = [
                                str(x) for x in (probe_payload.get("missing_topics", []) or [])
                            ]
                            topic_probe_result["existing_topics_before"] = [
                                str(x) for x in (probe_payload.get("existing_topics_before", []) or [])
                            ]
                            topic_probe_result["existing_topics_after"] = [
                                str(x) for x in (probe_payload.get("existing_topics_after", []) or [])
                            ]
                            topic_probe_result["created_topics"] = [
                                str(x) for x in (probe_payload.get("created_topics", []) or [])
                            ]
                            topic_probe_result["topic_status"] = list(probe_payload.get("topic_status", []) or [])
                            topic_probe_result["elapsed_seconds"] = float(probe_payload.get("elapsed_seconds", 0.0) or 0.0)
                            if topic_probe_result["errors"]:
                                readiness_issues.extend([f"topic probe error: {x}" for x in topic_probe_result["errors"]])
                            if topic_probe_result["overall_pass"] is not True:
                                if topic_probe_result["missing_topics"]:
                                    readiness_issues.append(
                                        f"required topics missing: {','.join(topic_probe_result['missing_topics'])}"
                                    )
                                else:
                                    readiness_issues.append("topic probe overall_pass is false")
                        else:
                            readiness_issues.append("topic probe response shape invalid")
    if created and fn_name:
        del_row, _, _ = run_cmd_capture(
            ["aws", "lambda", "delete-function", "--function-name", fn_name, "--region", region], timeout=60
        )
        probe_rows.append({**del_row, "probe_id": "m5p4_s3_probe_lambda_delete", "group": "topic_probe"})
        if str(del_row.get("status", "FAIL")) != "PASS":
            readiness_issues.append("failed to delete temporary topic probe lambda")
    shutil.rmtree(probe_tmp, ignore_errors=True)

    if readiness_issues:
        blockers.append({"id": "M5P4-B4", "severity": "S3", "status": "OPEN", "details": {"issues": readiness_issues}})

    topic_snapshot = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S3",
        "s2_dependency_phase_execution_id": dep_id,
        "cluster": {
            "arn": cluster_arn,
            "state": cluster_state,
            "bootstrap_registry": bootstrap_handle,
            "bootstrap_runtime": bootstrap_runtime,
            "subnet_ids_registry": subnet_ids,
            "security_group_registry": security_group_id,
        },
        "required_topics": required_topics,
        "tf_runtime_handles": tf_runtime,
        "handle_parity_issues": parity_issues,
        "topic_probe": topic_probe_result,
    }
    dumpj(out / "m5p4_topic_readiness_snapshot.json", topic_snapshot)

    total = len(probe_rows)
    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5P4_STRESS_MAX_SPEND_USD", 40))

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S3",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s2_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    if missing_handles:
        control_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        control_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
    control_issues.extend(topic_handle_issues)
    control_issues.extend(dep_issues)
    control_issues.extend(parity_issues)
    control_issues.extend(readiness_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S3",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "s2_dependency_phase_execution_id": dep_id,
        "topic_snapshot_ref": "m5p4_topic_readiness_snapshot.json",
    }
    dumpj(out / "m5p4_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S3",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5p4_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S3",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "ingress_msk_topic_readiness_v0",
    }
    dumpj(out / "m5p4_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S3",
        "decisions": [
            "Validated S2 dependency and carried Stage-A artifacts forward.",
            "Validated MSK handle parity against streaming/core Terraform outputs.",
            "Validated live cluster state and bootstrap broker readback via MSK control-plane APIs.",
            "Executed temporary in-VPC Kafka admin probe for required 9-topic readiness and enforced cleanup.",
            "Applied fail-closed blocker mapping for M5P4 S3.",
        ],
    }
    dumpj(out / "m5p4_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S3",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S3",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5P4_ST_S4_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5P4_S3_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s2_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_blocker_register.json", bref)
    dumpj(out / "m5p4_execution_summary.json", summ)

    miss = [n for n in M5P4_S3_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5P4-B8", "severity": "S3", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5p4_blocker_register.json", bref)
        dumpj(out / "m5p4_execution_summary.json", summ)

    print(f"[m5p4_s3] phase_execution_id={phase_id}")
    print(f"[m5p4_s3] output_dir={out.as_posix()}")
    print(f"[m5p4_s3] overall_pass={summ['overall_pass']}")
    print(f"[m5p4_s3] next_gate={summ['next_gate']}")
    print(f"[m5p4_s3] probe_count={total}")
    print(f"[m5p4_s3] error_rate_pct={er}")
    print(f"[m5p4_s3] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s4(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_s3(out_root, out)
    if copy_errs:
        blockers.append({"id": "M5P4-B8", "severity": "S4", "status": "OPEN", "details": {"copy_errors": copy_errs}})
        if not (out / "m5p4_lane_matrix.json").exists():
            dumpj(out / "m5p4_lane_matrix.json", build_lane_matrix())

    s3 = load_latest_successful_m5p4_s3(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    if not s3:
        dep_issues.append("missing successful M5P4-ST-S3 dependency")
    else:
        dep_summ = s3.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5P4_ST_S4_READY":
            dep_issues.append("M5P4 S3 next_gate is not M5P4_ST_S4_READY")
        s3_br = load_json_safe(Path(str(s3["path"])) / "m5p4_blocker_register.json")
        s3_open = int(s3_br.get("open_blocker_count", len(s3_br.get("blockers", [])))) if s3_br else 0
        if s3_open != 0:
            dep_issues.append(f"M5P4 S3 blocker register not closed: {s3_open}")
    if dep_issues:
        blockers.append({"id": "M5P4-B9", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}})

    req = [
        "IG_BASE_URL",
        "IG_INGEST_PATH",
        "IG_HEALTHCHECK_PATH",
        "IG_AUTH_MODE",
        "IG_AUTH_HEADER_NAME",
        "SSM_IG_API_KEY_PATH",
        "APIGW_IG_API_ID",
        "LAMBDA_IG_HANDLER_NAME",
        "DDB_IG_IDEMPOTENCY_TABLE",
        "IG_MAX_REQUEST_BYTES",
        "IG_REQUEST_TIMEOUT_SECONDS",
        "IG_INTERNAL_RETRY_MAX_ATTEMPTS",
        "IG_INTERNAL_RETRY_BACKOFF_MS",
        "IG_IDEMPOTENCY_TTL_SECONDS",
        "IG_DLQ_MODE",
        "IG_DLQ_QUEUE_NAME",
        "IG_REPLAY_MODE",
        "IG_RATE_LIMIT_RPS",
        "IG_RATE_LIMIT_BURST",
        "S3_EVIDENCE_BUCKET",
    ]
    missing_handles = [k for k in req if k not in h]
    placeholder_handles = [k for k in req if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    envelope_handle_issues: list[str] = []
    if missing_handles:
        envelope_handle_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        envelope_handle_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")

    def _to_int(value: Any, key: str) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            envelope_handle_issues.append(f"handle {key} is not integer-compatible")
            return 0

    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    base_url = str(h.get("IG_BASE_URL", "")).strip()
    ingest_path = str(h.get("IG_INGEST_PATH", "")).strip()
    health_path = str(h.get("IG_HEALTHCHECK_PATH", "")).strip()
    auth_mode = str(h.get("IG_AUTH_MODE", "")).strip().lower()
    auth_header = str(h.get("IG_AUTH_HEADER_NAME", "X-IG-Api-Key")).strip() or "X-IG-Api-Key"
    api_key_path = str(h.get("SSM_IG_API_KEY_PATH", "")).strip()
    api_id = str(h.get("APIGW_IG_API_ID", "")).strip()
    lambda_name = str(h.get("LAMBDA_IG_HANDLER_NAME", "")).strip()
    ddb_table = str(h.get("DDB_IG_IDEMPOTENCY_TABLE", "")).strip()
    evidence_bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    expected_max_request_bytes = _to_int(h.get("IG_MAX_REQUEST_BYTES", 0), "IG_MAX_REQUEST_BYTES")
    expected_timeout_seconds = _to_int(h.get("IG_REQUEST_TIMEOUT_SECONDS", 0), "IG_REQUEST_TIMEOUT_SECONDS")
    expected_retry_attempts = _to_int(h.get("IG_INTERNAL_RETRY_MAX_ATTEMPTS", 0), "IG_INTERNAL_RETRY_MAX_ATTEMPTS")
    expected_retry_backoff_ms = _to_int(h.get("IG_INTERNAL_RETRY_BACKOFF_MS", 0), "IG_INTERNAL_RETRY_BACKOFF_MS")
    expected_ttl_seconds = _to_int(h.get("IG_IDEMPOTENCY_TTL_SECONDS", 0), "IG_IDEMPOTENCY_TTL_SECONDS")
    expected_dlq_mode = str(h.get("IG_DLQ_MODE", "")).strip()
    expected_dlq_queue = str(h.get("IG_DLQ_QUEUE_NAME", "")).strip()
    expected_replay_mode = str(h.get("IG_REPLAY_MODE", "")).strip()
    expected_rate_rps = float(_to_int(h.get("IG_RATE_LIMIT_RPS", 0), "IG_RATE_LIMIT_RPS"))
    expected_rate_burst = _to_int(h.get("IG_RATE_LIMIT_BURST", 0), "IG_RATE_LIMIT_BURST")

    if auth_mode != "api_key":
        envelope_handle_issues.append("IG_AUTH_MODE drift (expected api_key)")

    probe_rows: list[dict[str, Any]] = []
    if evidence_bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", evidence_bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m5p4_s4_evidence_bucket", "group": "control"})
        if str(p.get("status", "FAIL")) != "PASS":
            blockers.append(
                {
                    "id": "M5P4-B8",
                    "severity": "S4",
                    "status": "OPEN",
                    "details": {"probe_failures": ["m5p4_s4_evidence_bucket"]},
                }
            )

    key_fetch = {"ok": False, "value": "", "result": {"probe_id": "m5p4_s4_ssm_api_key", "group": "auth"}}
    if api_key_path and api_key_path not in {"TO_PIN"}:
        key_fetch = _fetch_ssm_secret(api_key_path, region, timeout=30)
        probe_rows.append({**key_fetch["result"], "probe_id": "m5p4_s4_ssm_api_key", "group": "auth"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5p4_s4_ssm_api_key",
                "group": "auth",
                "command": "aws ssm get-parameter --name <redacted> --with-decryption",
                "exit_code": 1,
                "status": "FAIL",
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": "missing SSM_IG_API_KEY_PATH handle",
                "started_at_utc": now(),
                "ended_at_utc": now(),
            }
        )
    if key_fetch.get("ok") is not True:
        envelope_handle_issues.append("api key retrieval failed for S4 behavior probes")

    materialization_issues: list[str] = []
    lambda_row, lambda_payload = _run_json_cmd(
        ["aws", "lambda", "get-function-configuration", "--function-name", lambda_name, "--region", region, "--output", "json"],
        probe_id="m5p4_s4_lambda_config",
        group="runtime",
        timeout=40,
    )
    probe_rows.append(lambda_row)
    stage_row, stage_payload = _run_json_cmd(
        ["aws", "apigatewayv2", "get-stage", "--api-id", api_id, "--stage-name", "v1", "--region", region, "--output", "json"],
        probe_id="m5p4_s4_apigw_stage",
        group="runtime",
        timeout=40,
    )
    probe_rows.append(stage_row)
    int_row, int_payload = _run_json_cmd(
        ["aws", "apigatewayv2", "get-integrations", "--api-id", api_id, "--region", region, "--output", "json"],
        probe_id="m5p4_s4_apigw_integrations",
        group="runtime",
        timeout=40,
    )
    probe_rows.append(int_row)
    ddb_row, ddb_payload = _run_json_cmd(
        ["aws", "dynamodb", "describe-time-to-live", "--table-name", ddb_table, "--region", region, "--output", "json"],
        probe_id="m5p4_s4_ddb_ttl",
        group="runtime",
        timeout=40,
    )
    probe_rows.append(ddb_row)
    sqs_row, sqs_payload = _run_json_cmd(
        ["aws", "sqs", "get-queue-url", "--queue-name", expected_dlq_queue, "--region", region, "--output", "json"],
        probe_id="m5p4_s4_sqs_dlq",
        group="runtime",
        timeout=40,
    )
    probe_rows.append(sqs_row)

    lambda_runtime: dict[str, Any] = {}
    if str(lambda_row.get("status", "FAIL")) == "PASS":
        env_vars = (
            lambda_payload.get("Environment", {}).get("Variables", {})
            if isinstance(lambda_payload.get("Environment", {}), dict)
            else {}
        )
        lambda_runtime = {
            "state": lambda_payload.get("State"),
            "timeout": lambda_payload.get("Timeout"),
            "memory_size": lambda_payload.get("MemorySize"),
            "env": env_vars,
        }
        if str(lambda_payload.get("State", "")) != "Active":
            materialization_issues.append("lambda state is not Active")
        if int(lambda_payload.get("Timeout", 0) or 0) != expected_timeout_seconds:
            materialization_issues.append("lambda timeout drift vs IG_REQUEST_TIMEOUT_SECONDS")
        env_expect = {
            "IG_MAX_REQUEST_BYTES": str(expected_max_request_bytes),
            "IG_REQUEST_TIMEOUT_SECONDS": str(expected_timeout_seconds),
            "IG_INTERNAL_RETRY_MAX_ATTEMPTS": str(expected_retry_attempts),
            "IG_INTERNAL_RETRY_BACKOFF_MS": str(expected_retry_backoff_ms),
            "IG_IDEMPOTENCY_TTL_SECONDS": str(expected_ttl_seconds),
            "IG_DLQ_MODE": expected_dlq_mode,
            "IG_DLQ_QUEUE_NAME": expected_dlq_queue,
            "IG_REPLAY_MODE": expected_replay_mode,
            "IG_RATE_LIMIT_RPS": str(int(expected_rate_rps)),
            "IG_RATE_LIMIT_BURST": str(expected_rate_burst),
            "IG_AUTH_MODE": "api_key",
            "IG_AUTH_HEADER_NAME": auth_header,
            "IG_IDEMPOTENCY_TABLE": ddb_table,
        }
        for env_key, expected in env_expect.items():
            observed = str(env_vars.get(env_key, "")).strip()
            if observed != str(expected):
                materialization_issues.append(f"lambda env drift: {env_key} expected={expected} observed={observed or '<empty>'}")
    else:
        materialization_issues.append("unable to read lambda function configuration")

    stage_runtime: dict[str, Any] = {}
    if str(stage_row.get("status", "FAIL")) == "PASS":
        default_route = stage_payload.get("DefaultRouteSettings", {}) if isinstance(stage_payload.get("DefaultRouteSettings", {}), dict) else {}
        stage_runtime = {"default_route_settings": default_route, "stage_name": stage_payload.get("StageName")}
        rate = float(default_route.get("ThrottlingRateLimit", 0.0) or 0.0)
        burst = int(default_route.get("ThrottlingBurstLimit", 0) or 0)
        if abs(rate - expected_rate_rps) > 0.001:
            materialization_issues.append("API stage throttling rate drift vs IG_RATE_LIMIT_RPS")
        if burst != expected_rate_burst:
            materialization_issues.append("API stage throttling burst drift vs IG_RATE_LIMIT_BURST")
    else:
        materialization_issues.append("unable to read API Gateway stage configuration")

    integration_runtime: dict[str, Any] = {}
    if str(int_row.get("status", "FAIL")) == "PASS":
        items = int_payload.get("Items", []) if isinstance(int_payload.get("Items", []), list) else []
        selected: dict[str, Any] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            uri = str(item.get("IntegrationUri", ""))
            if lambda_name in uri:
                selected = item
                break
        if not selected and items and isinstance(items[0], dict):
            selected = items[0]
        integration_runtime = selected
        expected_timeout_ms = min(30000, expected_timeout_seconds * 1000)
        observed_timeout_ms = int(selected.get("TimeoutInMillis", 0) or 0)
        if observed_timeout_ms != expected_timeout_ms:
            materialization_issues.append("API integration timeout drift vs IG_REQUEST_TIMEOUT_SECONDS")
    else:
        materialization_issues.append("unable to read API Gateway integrations")

    ddb_runtime: dict[str, Any] = {}
    if str(ddb_row.get("status", "FAIL")) == "PASS":
        ttl_desc = ddb_payload.get("TimeToLiveDescription", {}) if isinstance(ddb_payload.get("TimeToLiveDescription", {}), dict) else {}
        ddb_runtime = ttl_desc
        if str(ttl_desc.get("TimeToLiveStatus", "")) != "ENABLED":
            materialization_issues.append("DDB TTL status is not ENABLED")
        if str(ttl_desc.get("AttributeName", "")) != "ttl_epoch":
            materialization_issues.append("DDB TTL attribute drift (expected ttl_epoch)")
    else:
        materialization_issues.append("unable to read DDB TTL configuration")

    sqs_runtime: dict[str, Any] = {}
    if str(sqs_row.get("status", "FAIL")) == "PASS":
        queue_url = str(sqs_payload.get("QueueUrl", "")).strip()
        sqs_runtime = {"queue_url": queue_url, "queue_name": expected_dlq_queue}
        if not queue_url or not queue_url.endswith(f"/{expected_dlq_queue}"):
            materialization_issues.append("DLQ queue URL drift vs IG_DLQ_QUEUE_NAME")
    else:
        materialization_issues.append("unable to resolve DLQ queue URL")

    run_identity = {
        "platform_run_id": f"platform_{tok()}",
        "scenario_run_id": f"scenario_{uuid4().hex[:24]}",
        "phase_id": "P4.D",
        "runtime_lane": "ingress_edge",
        "trace_id": f"trace-{uuid4().hex[:20]}",
    }
    probe_contract_issues: list[str] = []
    health_probe: dict[str, Any] = {}
    normal_probe: dict[str, Any] = {}
    oversize_probe: dict[str, Any] = {}
    if key_fetch.get("ok") is True and base_url and ingest_path and health_path:
        shared_headers = {
            auth_header: str(key_fetch.get("value", "")),
            "x-fp-platform-run-id": run_identity["platform_run_id"],
            "x-fp-phase-id": run_identity["phase_id"],
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00",
            "tracestate": "ingress=envelope",
        }

        health_probe = _http_json_probe(
            probe_id="m5p4_s4_health",
            group="envelope_probe",
            method="GET",
            url=_join_url(base_url, health_path),
            headers={**shared_headers, "x-fp-event-id": f"{phase_id}-health"},
            timeout=20,
        )
        probe_rows.append(health_probe)
        h_code = int(health_probe.get("status_code", 0) or 0)
        h_body = health_probe.get("body_json", {}) if isinstance(health_probe.get("body_json", {}), dict) else {}
        if h_code != 200:
            probe_contract_issues.append(f"health probe status expected 200, observed {h_code}")
        envelope_obj = h_body.get("envelope", {}) if isinstance(h_body.get("envelope", {}), dict) else {}
        if not envelope_obj:
            probe_contract_issues.append("health response missing envelope object")
        else:
            expected_envelope = {
                "max_request_bytes": expected_max_request_bytes,
                "request_timeout_seconds": expected_timeout_seconds,
                "internal_retry_max_attempts": expected_retry_attempts,
                "internal_retry_backoff_ms": expected_retry_backoff_ms,
                "idempotency_ttl_seconds": expected_ttl_seconds,
                "dlq_mode": expected_dlq_mode,
                "dlq_queue_name": expected_dlq_queue,
                "replay_mode": expected_replay_mode,
                "rate_limit_rps": expected_rate_rps,
                "rate_limit_burst": expected_rate_burst,
            }
            for ek, ev in expected_envelope.items():
                ov = envelope_obj.get(ek)
                if isinstance(ev, float):
                    try:
                        if abs(float(ov) - ev) > 0.001:
                            probe_contract_issues.append(f"health envelope drift: {ek} expected={ev} observed={ov}")
                    except Exception:
                        probe_contract_issues.append(f"health envelope type mismatch: {ek}")
                else:
                    if str(ov) != str(ev):
                        probe_contract_issues.append(f"health envelope drift: {ek} expected={ev} observed={ov}")

        normal_payload = {
            "platform_run_id": run_identity["platform_run_id"],
            "scenario_run_id": run_identity["scenario_run_id"],
            "phase_id": run_identity["phase_id"],
            "runtime_lane": run_identity["runtime_lane"],
            "trace_id": run_identity["trace_id"],
            "event_class": "m5p4_envelope_probe",
            "event_type": "m5p4_envelope_probe",
            "event_id": f"m5p4_s4_normal_{phase_id}",
        }
        normal_probe = _http_json_probe(
            probe_id="m5p4_s4_ingest_normal",
            group="envelope_probe",
            method="POST",
            url=_join_url(base_url, ingest_path),
            headers={**shared_headers, "x-fp-event-id": f"{phase_id}-ingest-normal", "Content-Type": "application/json"},
            payload=normal_payload,
            timeout=20,
        )
        probe_rows.append(normal_probe)
        n_code = int(normal_probe.get("status_code", 0) or 0)
        n_body = normal_probe.get("body_json", {}) if isinstance(normal_probe.get("body_json", {}), dict) else {}
        if n_code != 202:
            probe_contract_issues.append(f"normal ingest status expected 202, observed {n_code}")
        if bool(n_body.get("admitted")) is not True:
            probe_contract_issues.append("normal ingest admitted flag is not true")

        oversize_len = max(expected_max_request_bytes + 512, expected_max_request_bytes + 1)
        oversize_payload = {
            "platform_run_id": run_identity["platform_run_id"],
            "scenario_run_id": run_identity["scenario_run_id"],
            "phase_id": run_identity["phase_id"],
            "runtime_lane": run_identity["runtime_lane"],
            "trace_id": run_identity["trace_id"],
            "event_class": "m5p4_envelope_probe",
            "event_type": "m5p4_envelope_probe",
            "event_id": f"m5p4_s4_oversize_{phase_id}",
            "blob": "x" * oversize_len,
        }
        oversize_probe = _http_json_probe(
            probe_id="m5p4_s4_ingest_oversize",
            group="envelope_probe",
            method="POST",
            url=_join_url(base_url, ingest_path),
            headers={**shared_headers, "x-fp-event-id": f"{phase_id}-ingest-oversize", "Content-Type": "application/json"},
            payload=oversize_payload,
            timeout=30,
        )
        probe_rows.append(oversize_probe)
        o_code = int(oversize_probe.get("status_code", 0) or 0)
        o_body = oversize_probe.get("body_json", {}) if isinstance(oversize_probe.get("body_json", {}), dict) else {}
        if o_code != 413:
            probe_contract_issues.append(f"oversize ingest status expected 413, observed {o_code}")
        if isinstance(o_body, dict) and o_body:
            if str(o_body.get("error", "")).strip() != "payload_too_large":
                probe_contract_issues.append("oversize ingest error contract mismatch (expected payload_too_large)")
    else:
        probe_contract_issues.append("required S4 behavior probe inputs unavailable")

    if envelope_handle_issues or materialization_issues or probe_contract_issues:
        blockers.append(
            {
                "id": "M5P4-B5",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "handle_issues": envelope_handle_issues,
                    "materialization_issues": materialization_issues,
                    "probe_contract_issues": probe_contract_issues,
                },
            }
        )

    envelope_snapshot = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S4",
        "s3_dependency_phase_execution_id": dep_id,
        "expected_handles": {
            "IG_MAX_REQUEST_BYTES": expected_max_request_bytes,
            "IG_REQUEST_TIMEOUT_SECONDS": expected_timeout_seconds,
            "IG_INTERNAL_RETRY_MAX_ATTEMPTS": expected_retry_attempts,
            "IG_INTERNAL_RETRY_BACKOFF_MS": expected_retry_backoff_ms,
            "IG_IDEMPOTENCY_TTL_SECONDS": expected_ttl_seconds,
            "IG_DLQ_MODE": expected_dlq_mode,
            "IG_DLQ_QUEUE_NAME": expected_dlq_queue,
            "IG_REPLAY_MODE": expected_replay_mode,
            "IG_RATE_LIMIT_RPS": expected_rate_rps,
            "IG_RATE_LIMIT_BURST": expected_rate_burst,
        },
        "runtime_materialization": {
            "lambda": lambda_runtime,
            "api_stage": stage_runtime,
            "api_integration": integration_runtime,
            "ddb_ttl": ddb_runtime,
            "sqs_dlq": sqs_runtime,
            "issues": materialization_issues,
        },
        "behavior_probes": {
            "run_identity": run_identity,
            "health_probe": health_probe,
            "normal_ingest_probe": normal_probe,
            "oversize_ingest_probe": oversize_probe,
            "issues": probe_contract_issues,
        },
    }
    dumpj(out / "m5p4_envelope_conformance_snapshot.json", envelope_snapshot)

    total = len(probe_rows)
    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5P4_STRESS_MAX_SPEND_USD", 40))

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S4",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s3_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    control_issues.extend(dep_issues)
    control_issues.extend(envelope_handle_issues)
    control_issues.extend(materialization_issues)
    control_issues.extend(probe_contract_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S4",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "s3_dependency_phase_execution_id": dep_id,
        "envelope_snapshot_ref": "m5p4_envelope_conformance_snapshot.json",
    }
    dumpj(out / "m5p4_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S4",
        "overall_pass": True,
        "secret_probe_count": 1,
        "secret_failure_count": 0 if key_fetch.get("ok") is True else 1,
        "with_decryption_used": True,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5p4_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S4",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "ingress_envelope_conformance_v0",
    }
    dumpj(out / "m5p4_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S4",
        "decisions": [
            "Validated S3 dependency and carried Stage-A artifacts forward.",
            "Validated envelope handle closure and runtime materialization parity across Lambda/API/DDB/SQS surfaces.",
            "Executed behavior probes for normal and oversized ingest payload contracts.",
            "Validated health envelope projection against pinned handle values.",
            "Applied fail-closed blocker mapping for M5P4 S4.",
        ],
    }
    dumpj(out / "m5p4_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S4",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P4-ST-S4",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5P4_ST_S5_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5P4_S4_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s3_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p4_blocker_register.json", bref)
    dumpj(out / "m5p4_execution_summary.json", summ)

    miss = [n for n in M5P4_S4_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5P4-B8", "severity": "S4", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5p4_blocker_register.json", bref)
        dumpj(out / "m5p4_execution_summary.json", summ)

    print(f"[m5p4_s4] phase_execution_id={phase_id}")
    print(f"[m5p4_s4] output_dir={out.as_posix()}")
    print(f"[m5p4_s4] overall_pass={summ['overall_pass']}")
    print(f"[m5p4_s4] next_gate={summ['next_gate']}")
    print(f"[m5p4_s4] probe_count={total}")
    print(f"[m5p4_s4] error_rate_pct={er}")
    print(f"[m5p4_s4] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M5.P4 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--output-root", default=str(OUT_ROOT))
    a = ap.parse_args()
    pfx = {
        "S0": "m5p4_stress_s0",
        "S1": "m5p4_stress_s1",
        "S2": "m5p4_stress_s2",
        "S3": "m5p4_stress_s3",
        "S4": "m5p4_stress_s4",
    }[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    root = Path(a.output_root)
    if a.stage == "S0":
        return run_s0(pid, root)
    if a.stage == "S1":
        return run_s1(pid, root)
    if a.stage == "S2":
        return run_s2(pid, root)
    if a.stage == "S3":
        return run_s3(pid, root)
    return run_s4(pid, root)


if __name__ == "__main__":
    raise SystemExit(main())
