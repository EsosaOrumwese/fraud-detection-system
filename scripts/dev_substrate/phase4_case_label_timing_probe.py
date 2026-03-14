#!/usr/bin/env python3
"""Derive run-scoped Phase 4 coupled timing directly from Case Mgmt and Label Store truth."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def run(cmd: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def pod_name(namespace: str, app: str) -> str:
    proc = run(
        [
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            f"app={app}",
            "-o",
            "json",
        ],
        timeout=120,
    )
    payload = json.loads(proc.stdout)
    items = list(payload.get("items") or [])
    running: list[tuple[str, str]] = []
    for item in items:
        status = dict(item.get("status") or {})
        name = str((item.get("metadata") or {}).get("name") or "").strip()
        phase = str(status.get("phase") or "").strip()
        if name and phase == "Running":
            running.append((name, phase))
    if not running:
        raise RuntimeError(f"PHASE4.TIMING.POD_NOT_RUNNING:{namespace}:{app}")
    running.sort()
    return running[0][0]


REMOTE_CASE_QUERY = r'''
import json
import psycopg
from pathlib import Path
from fraud_detection.case_mgmt.worker import load_worker_config

cfg = load_worker_config(Path('/runtime-profile/dev_full.yaml'))
platform_run_id = __import__('os').environ['PHASE4_PLATFORM_RUN_ID']
scenario_run_id = __import__('os').environ['PHASE4_SCENARIO_RUN_ID']

decision_rows = []
label_request_rows = []
with psycopg.connect(cfg.locator) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.case_id, c.created_at_utc, MIN(t.first_seen_at_utc) AS trigger_seen_at_utc
            FROM cm_cases c
            JOIN cm_case_trigger_intake t
              ON t.case_id = c.case_id
            WHERE c.pins_json::text LIKE %s
              AND c.pins_json::text LIKE %s
              AND t.trigger_json::text LIKE %s
              AND t.trigger_json::text LIKE %s
            GROUP BY c.case_id, c.created_at_utc
            ORDER BY c.created_at_utc ASC
            """,
            (f'%{platform_run_id}%', f'%{scenario_run_id}%', f'%{platform_run_id}%', f'%{scenario_run_id}%'),
        )
        decision_rows = [
            {
                'case_id': str(row[0]),
                'case_created_at_utc': str(row[1]),
                'trigger_seen_at_utc': str(row[2]),
            }
            for row in cur.fetchall()
        ]
        cur.execute(
            """
            SELECT label_assertion_id, case_id, first_requested_at_utc
            FROM cm_label_emissions
            WHERE assertion_json::text LIKE %s
              AND assertion_json::text LIKE %s
            ORDER BY first_requested_at_utc ASC
            """,
            (f'%{platform_run_id}%', f'%{scenario_run_id}%'),
        )
        for assertion_id, case_id, first_requested_at_utc in cur.fetchall():
            label_request_rows.append(
                {
                    'case_id': str(case_id),
                    'label_assertion_id': str(assertion_id),
                    'label_requested_at_utc': str(first_requested_at_utc),
                }
            )

print(json.dumps(
    {
        'locator': cfg.locator,
        'decision_rows': decision_rows,
        'label_request_rows': label_request_rows,
    },
    indent=2,
))
'''


REMOTE_LABEL_QUERY = r'''
import json
import psycopg
from pathlib import Path
from fraud_detection.label_store.worker import load_worker_config

cfg = load_worker_config(Path('/runtime-profile/dev_full.yaml'))
platform_run_id = __import__('os').environ['PHASE4_PLATFORM_RUN_ID']
scenario_run_id = __import__('os').environ['PHASE4_SCENARIO_RUN_ID']

with psycopg.connect(cfg.locator) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT label_assertion_id, event_id, first_committed_at_utc
            FROM ls_label_assertions
            WHERE platform_run_id = %s
              AND assertion_json::text LIKE %s
            ORDER BY first_committed_at_utc ASC
            """,
            (platform_run_id, f'%{scenario_run_id}%'),
        )
        rows = [
            {
                'label_assertion_id': str(row[0]),
                'event_id': str(row[1]),
                'label_committed_at_utc': str(row[2]),
            }
            for row in cur.fetchall()
        ]

print(json.dumps({'locator': cfg.locator, 'label_rows': rows}, indent=2))
'''


def exec_json(namespace: str, pod: str, script: str, env_map: dict[str, str], *, timeout: int = 300) -> dict[str, Any]:
    env_bits = [f"{key}={value}" for key, value in sorted(env_map.items())]
    proc = subprocess.run(
        ["kubectl", "exec", "-i", "-n", namespace, pod, "--", "env", *env_bits, "python", "-"],
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"kubectl_exec_failed:{namespace}:{pod}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    text = proc.stdout.strip()
    return json.loads(text) if text else {}


def parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty timestamp")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * pct
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    weight = position - lower
    return float(lower_value + (upper_value - lower_value) * weight)


def summarize_latency(rows: list[dict[str, Any]], *, value_key: str, sample_keys: list[str]) -> dict[str, Any]:
    values = [float(row[value_key]) for row in rows]
    negatives = [row for row in rows if float(row[value_key]) < 0.0]
    samples: list[dict[str, Any]] = []
    for row in rows[:10]:
        sample = {key: row.get(key) for key in sample_keys}
        sample[value_key] = float(row[value_key])
        samples.append(sample)
    return {
        "count": len(values),
        "min_seconds": min(values) if values else None,
        "p50_seconds": percentile(values, 0.50),
        "p95_seconds": percentile(values, 0.95),
        "p99_seconds": percentile(values, 0.99),
        "max_seconds": max(values) if values else None,
        "negative_count": len(negatives),
        "samples": samples,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Derive coupled Phase 4 timing from live case/label truth stores.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--scenario-run-id", required=True)
    ap.add_argument("--namespace", default="fraud-platform-case-labels")
    ap.add_argument("--case-mgmt-app", default="fp-pr3-case-mgmt")
    ap.add_argument("--label-store-app", default="fp-pr3-label-store")
    ap.add_argument("--decision-to-case-p95-max-seconds", type=float, default=5.0)
    ap.add_argument("--case-to-label-p95-max-seconds", type=float, default=10.0)
    ap.add_argument("--artifact-prefix", default="phase4_coupled")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    output_path = root / f"{str(args.artifact_prefix).strip()}_timing_probe.json"
    env_map = {
        "PHASE4_PLATFORM_RUN_ID": str(args.platform_run_id).strip(),
        "PHASE4_SCENARIO_RUN_ID": str(args.scenario_run_id).strip(),
    }

    blockers: list[str] = []
    case_mgmt_pod = pod_name(str(args.namespace).strip(), str(args.case_mgmt_app).strip())
    label_store_pod = pod_name(str(args.namespace).strip(), str(args.label_store_app).strip())
    case_payload = exec_json(str(args.namespace).strip(), case_mgmt_pod, REMOTE_CASE_QUERY, env_map, timeout=300)
    label_payload = exec_json(str(args.namespace).strip(), label_store_pod, REMOTE_LABEL_QUERY, env_map, timeout=300)

    decision_rows_raw = list(case_payload.get("decision_rows") or [])
    label_request_rows_raw = list(case_payload.get("label_request_rows") or [])
    label_rows_raw = list(label_payload.get("label_rows") or [])

    decision_rows: list[dict[str, Any]] = []
    for row in decision_rows_raw:
        try:
            decision_time = parse_utc(str(row.get("trigger_seen_at_utc") or ""))
            case_created = parse_utc(str(row.get("case_created_at_utc") or ""))
        except ValueError:
            continue
        decision_rows.append(
            {
                "case_id": str(row.get("case_id") or ""),
                "trigger_seen_at_utc": decision_time.isoformat().replace("+00:00", "Z"),
                "case_created_at_utc": case_created.isoformat().replace("+00:00", "Z"),
                "latency_seconds": (case_created - decision_time).total_seconds(),
            }
        )

    label_rows_by_id = {
        str(row.get("label_assertion_id") or "").strip(): row
        for row in label_rows_raw
        if str(row.get("label_assertion_id") or "").strip()
    }
    case_to_label_rows: list[dict[str, Any]] = []
    for row in label_request_rows_raw:
        assertion_id = str(row.get("label_assertion_id") or "").strip()
        label_row = label_rows_by_id.get(assertion_id)
        if not assertion_id or label_row is None:
            continue
        try:
            pending_time = parse_utc(str(row.get("label_requested_at_utc") or ""))
            label_time = parse_utc(str(label_row.get("label_committed_at_utc") or ""))
        except ValueError:
            continue
        case_to_label_rows.append(
            {
                "case_id": str(row.get("case_id") or ""),
                "label_assertion_id": assertion_id,
                "label_requested_at_utc": pending_time.isoformat().replace("+00:00", "Z"),
                "label_committed_at_utc": label_time.isoformat().replace("+00:00", "Z"),
                "event_id": str(label_row.get("event_id") or ""),
                "latency_seconds": (label_time - pending_time).total_seconds(),
            }
        )

    decision_to_case = summarize_latency(
        decision_rows,
        value_key="latency_seconds",
        sample_keys=["case_id", "trigger_seen_at_utc", "case_created_at_utc"],
    )
    case_to_label = summarize_latency(
        case_to_label_rows,
        value_key="latency_seconds",
        sample_keys=["case_id", "label_assertion_id", "label_requested_at_utc", "label_committed_at_utc", "event_id"],
    )

    if decision_to_case["count"] <= 0:
        blockers.append("PHASE4.B24_DECISION_TO_CASE_TIMING_MISSING")
    if case_to_label["count"] <= 0:
        blockers.append("PHASE4.B24_CASE_TO_LABEL_TIMING_MISSING")
    if (decision_to_case.get("negative_count") or 0) > 0:
        blockers.append("PHASE4.B24_DECISION_TO_CASE_TIMING_NEGATIVE")
    if (case_to_label.get("negative_count") or 0) > 0:
        blockers.append("PHASE4.B24_CASE_TO_LABEL_TIMING_NEGATIVE")

    d2c_p95 = decision_to_case.get("p95_seconds")
    if d2c_p95 is not None and float(d2c_p95) > float(args.decision_to_case_p95_max_seconds):
        blockers.append(
            f"PHASE4.B24_DECISION_TO_CASE_P95_BREACH:observed={float(d2c_p95):.6f}:max={float(args.decision_to_case_p95_max_seconds):.6f}"
        )
    c2l_p95 = case_to_label.get("p95_seconds")
    if c2l_p95 is not None and float(c2l_p95) > float(args.case_to_label_p95_max_seconds):
        blockers.append(
            f"PHASE4.B24_CASE_TO_LABEL_P95_BREACH:observed={float(c2l_p95):.6f}:max={float(args.case_to_label_p95_max_seconds):.6f}"
        )

    payload = {
        "phase": "PHASE4",
        "generated_at_utc": now_utc(),
        "execution_id": str(args.execution_id).strip(),
        "platform_run_id": str(args.platform_run_id).strip(),
        "scenario_run_id": str(args.scenario_run_id).strip(),
        "namespace": str(args.namespace).strip(),
        "pods": {
            "case_mgmt": case_mgmt_pod,
            "label_store": label_store_pod,
        },
        "locators": {
            "case_mgmt": str(case_payload.get("locator") or ""),
            "label_store": str(label_payload.get("locator") or ""),
        },
        "thresholds": {
            "decision_to_case_p95_max_seconds": float(args.decision_to_case_p95_max_seconds),
            "case_to_label_p95_max_seconds": float(args.case_to_label_p95_max_seconds),
        },
        "decision_to_case": decision_to_case,
        "case_to_label": case_to_label,
        "blocker_ids": sorted(set(blockers)),
        "overall_pass": len(set(blockers)) == 0,
        "notes": [
            "decision_to_case is derived as Case Management case created time minus earliest run-scoped CaseTrigger first-seen processing time for the same case_id.",
            "case_to_label is derived as Label Store first committed time minus Case Management label emission first requested time for the same label_assertion_id.",
            "The p95 thresholds are pinned from the already accepted case/label production targets: case-open <= 5s and label commit <= 10s.",
        ],
    }
    dump_json(output_path, payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
