#!/usr/bin/env python3
"""Score a bounded Phase 3 Case + Label correctness slice."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict[str, Any] | None:
    return load_json(path) if path.exists() else None


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summary_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    return to_float((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))


def summary_text(snapshot: dict[str, Any], component: str, field: str) -> str:
    value = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))
    return str(value or "").strip()


def health_state(snapshot: dict[str, Any], component: str) -> str:
    return str((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_state") or "UNKNOWN")


def health_reasons(snapshot: dict[str, Any], component: str) -> list[str]:
    raw = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_reasons"))
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def is_missing(snapshot: dict[str, Any], component: str) -> bool:
    payloads = ((snapshot.get("components") or {}).get(component) or {})
    for key in ("metrics_payload", "health_payload"):
        payload = payloads.get(key) or {}
        if payload.get("__missing__") or payload.get("__unreadable__"):
            return True
    return False


def delta(pre: dict[str, Any], post: dict[str, Any], component: str, field: str) -> float | None:
    start = summary_value(pre, component, field)
    end = summary_value(post, component, field)
    if end is None:
        return None
    if start is None:
        start = 0.0
    return float(end - start)


def replay_advisory_only(snapshot: dict[str, Any], component: str, max_checkpoint: float, max_lag: float) -> bool:
    if component not in {"csfb", "ieg", "ofp"}:
        return False
    if health_state(snapshot, component).upper() not in {"RED", "FAILED", "UNHEALTHY"}:
        return False
    reasons = set(health_reasons(snapshot, component))
    checkpoint = summary_value(snapshot, component, "checkpoint_age_seconds")
    if checkpoint is None or checkpoint > max_checkpoint:
        return False
    lag = summary_value(snapshot, component, "lag_seconds")
    if lag is not None and lag > max_lag:
        return False
    if component == "csfb":
        if reasons != {"WATERMARK_TOO_OLD"}:
            return False
        return (summary_value(snapshot, component, "join_misses") or 0.0) == 0.0 and (
            summary_value(snapshot, component, "binding_conflicts") or 0.0
        ) == 0.0 and (summary_value(snapshot, component, "apply_failures_hard") or 0.0) == 0.0
    if component == "ofp":
        if reasons == {"WATERMARK_TOO_OLD"}:
            return lag is not None and lag <= max_lag
        if reasons != {"WATERMARK_TOO_OLD", "MISSING_FEATURES_RED"}:
            return False
        if (summary_value(snapshot, component, "snapshot_failures") or 0.0) > 0.0:
            return False
        if (summary_value(snapshot, "df", "missing_context_total") or 0.0) > 0.0:
            return False
        if (summary_value(snapshot, "df", "hard_fail_closed_total") or 0.0) > 0.0:
            return False
        if summary_text(snapshot, "dl", "decision_mode").upper() not in {"NORMAL", "STEP_UP_ONLY"}:
            return False
        return lag is not None and lag <= max_lag
    if reasons != {"WATERMARK_TOO_OLD"}:
        return False
    return (summary_value(snapshot, component, "apply_failure_count") or 0.0) == 0.0 and (
        summary_value(snapshot, component, "backpressure_hits") or 0.0
    ) == 0.0


def latest_snapshot(snapshots: list[dict[str, Any]], label: str) -> dict[str, Any]:
    target = str(label).strip().lower()
    for row in snapshots:
        if str(row.get("snapshot_label", "")).strip().lower() == target:
            return row
    return snapshots[-1]


def select_snapshots(root: Path, *, state_id: str, platform_run_id: str) -> list[dict[str, Any]]:
    snapshots = sorted(
        [
            load_json(path)
            for path in root.glob(f"g3a_{str(state_id).strip().lower()}_component_snapshot_*.json")
            if str(load_json(path).get("platform_run_id") or "").strip() == platform_run_id
        ],
        key=lambda row: str(row.get("generated_at_utc", "")),
    )
    labels = {str(row.get("snapshot_label", "")).strip().lower() for row in snapshots}
    if not snapshots or "pre" not in labels or "post" not in labels:
        raise RuntimeError("PHASE3.B22_COMPONENT_SNAPSHOTS_INCOMPLETE")
    return snapshots


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Phase 3 Case + Label bounded correctness rollup.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--state-id", default="P3")
    ap.add_argument("--artifact-prefix", default="phase3_case_label")
    ap.add_argument("--bootstrap-summary-name", default="phase3_control_plane_bootstrap.json")
    ap.add_argument("--expected-correctness-eps", type=float, default=3000.0)
    ap.add_argument("--min-processed-events", type=float, default=100000.0)
    ap.add_argument("--max-error-rate-ratio", type=float, default=0.002)
    ap.add_argument("--max-4xx-ratio", type=float, default=0.002)
    ap.add_argument("--max-5xx-ratio", type=float, default=0.0)
    ap.add_argument("--max-latency-p95-ms", type=float, default=350.0)
    ap.add_argument("--max-latency-p99-ms", type=float, default=700.0)
    ap.add_argument("--max-lag-p99-seconds", type=float, default=5.0)
    ap.add_argument("--max-checkpoint-p99-seconds", type=float, default=120.0)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    prefix = str(args.artifact_prefix).strip()
    summary = load_optional_json(root / f"{prefix}_wsp_runtime_summary.json")
    manifest = load_optional_json(root / f"{prefix}_wsp_runtime_manifest.json")
    bootstrap = load_optional_json(root / str(args.bootstrap_summary_name).strip()) or {"overall_pass": False}
    charter = load_optional_json(root / "g3a_run_charter.active.json") or {}

    platform_run_id = str((((manifest or {}).get("identity") or {}).get("platform_run_id") or "")).strip()
    if not platform_run_id:
        platform_run_id = str(bootstrap.get("platform_run_id") or "").strip()

    blockers: list[str] = []
    notes: list[str] = [
        "Phase 3 rollup is plane-scoped: it scores the Case + Label plane and the immediate promoted upstream path only.",
        "Learning and ops/governance remain later coupled proofs and are intentionally not closure prerequisites here.",
    ]

    if summary is None or manifest is None:
        blockers.append("PHASE3.B21_CORRECTNESS_WINDOW_NOT_EXECUTED")
    if not bool(bootstrap.get("overall_pass")):
        blockers.append("PHASE3.B20_CONTROL_BOOTSTRAP_FAIL")

    selected: list[dict[str, Any]] = []
    pre: dict[str, Any] = {}
    post: dict[str, Any] = {}
    if not blockers:
        try:
            selected = select_snapshots(root, state_id=args.state_id, platform_run_id=platform_run_id)
            pre = latest_snapshot(selected, "pre")
            post = latest_snapshot(selected, "post")
        except RuntimeError as exc:
            blockers.append(str(exc))

    observed = dict((summary or {}).get("observed") or {})
    admitted_eps = float(observed.get("observed_admitted_eps", 0.0) or 0.0)
    admitted_total = float(observed.get("admitted_request_count", 0.0) or 0.0)
    error_rate = float(observed.get("error_rate_ratio", 0.0) or 0.0)
    error_4xx = float(observed.get("4xx_rate_ratio", 0.0) or 0.0)
    error_5xx = float(observed.get("5xx_rate_ratio", 0.0) or 0.0)
    p95 = to_float(observed.get("latency_p95_ms"))
    p99 = to_float(observed.get("latency_p99_ms"))

    if summary is not None and manifest is not None:
        if admitted_eps < float(args.expected_correctness_eps):
            blockers.append(
                f"PHASE3.B21_CORRECTNESS_EPS_SHORTFALL:observed={admitted_eps:.3f}:target={float(args.expected_correctness_eps):.3f}"
            )
        if admitted_total < float(args.min_processed_events):
            blockers.append(
                f"PHASE3.B21_SAMPLE_MINIMA_SHORTFALL:observed={admitted_total:.0f}:required={float(args.min_processed_events):.0f}"
            )
        if error_rate > float(args.max_error_rate_ratio):
            blockers.append(
                f"PHASE3.B21_ERROR_RATE_BREACH:observed={error_rate:.6f}:max={float(args.max_error_rate_ratio):.6f}"
            )
        if error_4xx > float(args.max_4xx_ratio):
            blockers.append(
                f"PHASE3.B21_4XX_BREACH:observed={error_4xx:.6f}:max={float(args.max_4xx_ratio):.6f}"
            )
        if error_5xx > float(args.max_5xx_ratio):
            blockers.append(
                f"PHASE3.B21_5XX_BREACH:observed={error_5xx:.6f}:max={float(args.max_5xx_ratio):.6f}"
            )
        if p95 is None or p95 > float(args.max_latency_p95_ms):
            blockers.append(
                f"PHASE3.B21_P95_LATENCY_BREACH:observed={p95}:max={float(args.max_latency_p95_ms):.3f}"
            )
        if p99 is None or p99 > float(args.max_latency_p99_ms):
            blockers.append(
                f"PHASE3.B21_P99_LATENCY_BREACH:observed={p99}:max={float(args.max_latency_p99_ms):.3f}"
            )

    metrics: dict[str, float | None] = {}
    integrity: dict[str, float | None] = {}
    cross_plane = {
        "control_bootstrap": "PASS" if bool(bootstrap.get("overall_pass")) else "HOLD_REMEDIATE",
        "promoted_upstream_base": "HOLD_REMEDIATE",
        "case_trigger": "HOLD_REMEDIATE",
        "case_management": "HOLD_REMEDIATE",
        "label_store": "HOLD_REMEDIATE",
    }

    if pre and post:
        for component in ("csfb", "ieg", "ofp", "df", "al", "dla", "archive_writer", "case_trigger", "case_mgmt", "label_store"):
            if is_missing(post, component):
                blockers.append(f"PHASE3.B22_COMPONENT_MISSING:{component}")
                continue
            state = health_state(post, component).upper()
            if state in {"RED", "FAILED", "UNHEALTHY"} and not replay_advisory_only(
                post, component, float(args.max_checkpoint_p99_seconds), float(args.max_lag_p99_seconds)
            ):
                blockers.append(f"PHASE3.B22_COMPONENT_HEALTH_RED:{component}:{state}")

        metrics = {
            "df_decisions_total_delta": delta(pre, post, "df", "decisions_total"),
            "al_intake_total_delta": delta(pre, post, "al", "intake_total"),
            "dla_append_success_total_delta": delta(pre, post, "dla", "append_success_total"),
            "archive_archived_total_delta": delta(pre, post, "archive_writer", "archived_total"),
            "case_trigger_triggers_seen_delta": delta(pre, post, "case_trigger", "triggers_seen"),
            "case_trigger_published_delta": delta(pre, post, "case_trigger", "published"),
            "case_mgmt_case_triggers_delta": delta(pre, post, "case_mgmt", "case_triggers"),
            "case_mgmt_cases_created_delta": delta(pre, post, "case_mgmt", "cases_created"),
            "case_mgmt_timeline_events_delta": delta(pre, post, "case_mgmt", "timeline_events"),
            "case_mgmt_timeline_events_appended_delta": delta(pre, post, "case_mgmt", "timeline_events_appended"),
            "case_mgmt_labels_accepted_delta": delta(pre, post, "case_mgmt", "labels_accepted"),
            "label_store_accepted_delta": delta(pre, post, "label_store", "accepted"),
            "label_store_timeline_rows_delta": delta(pre, post, "label_store", "timeline_rows"),
        }
        integrity = {
            "df_hard_fail_closed_delta": delta(pre, post, "df", "hard_fail_closed_total"),
            "df_publish_quarantine_delta": delta(pre, post, "df", "publish_quarantine_total"),
            "al_publish_quarantine_delta": delta(pre, post, "al", "publish_quarantine_total"),
            "al_publish_ambiguous_delta": delta(pre, post, "al", "publish_ambiguous_total"),
            "dla_append_failure_delta": delta(pre, post, "dla", "append_failure_total"),
            "dla_replay_divergence_delta": delta(pre, post, "dla", "replay_divergence_total"),
            "archive_write_error_delta": delta(pre, post, "archive_writer", "write_error_total"),
            "archive_payload_mismatch_delta": delta(pre, post, "archive_writer", "payload_mismatch_total"),
            "case_trigger_duplicates_delta": delta(pre, post, "case_trigger", "duplicates"),
            "case_trigger_quarantine_delta": delta(pre, post, "case_trigger", "quarantine"),
            "case_trigger_publish_ambiguous_delta": delta(pre, post, "case_trigger", "publish_ambiguous_total"),
            "case_trigger_payload_mismatch_delta": delta(pre, post, "case_trigger", "payload_mismatch_total"),
            "case_mgmt_payload_mismatches_delta": delta(pre, post, "case_mgmt", "payload_mismatches"),
            "case_mgmt_anomalies_total_delta": delta(pre, post, "case_mgmt", "anomalies_total"),
            "case_mgmt_labels_rejected_delta": delta(pre, post, "case_mgmt", "labels_rejected"),
            "case_mgmt_evidence_pending_delta": delta(pre, post, "case_mgmt", "evidence_pending"),
            "case_mgmt_evidence_unavailable_delta": delta(pre, post, "case_mgmt", "evidence_unavailable"),
            "label_store_pending_delta": delta(pre, post, "label_store", "pending"),
            "label_store_rejected_delta": delta(pre, post, "label_store", "rejected"),
            "label_store_duplicate_delta": delta(pre, post, "label_store", "duplicate"),
            "label_store_payload_hash_mismatch_delta": delta(pre, post, "label_store", "payload_hash_mismatch"),
            "label_store_dedupe_tuple_collision_delta": delta(pre, post, "label_store", "dedupe_tuple_collision"),
            "label_store_missing_evidence_refs_delta": delta(pre, post, "label_store", "missing_evidence_refs"),
            "label_store_anomalies_total_delta": delta(pre, post, "label_store", "anomalies_total"),
        }

        required_positive = (
            "df_decisions_total_delta",
            "al_intake_total_delta",
            "dla_append_success_total_delta",
            "case_trigger_triggers_seen_delta",
            "case_trigger_published_delta",
            "case_mgmt_case_triggers_delta",
            "case_mgmt_cases_created_delta",
            "case_mgmt_timeline_events_appended_delta",
            "label_store_accepted_delta",
            "label_store_timeline_rows_delta",
        )
        for key in required_positive:
            if (metrics.get(key) or 0.0) <= 0.0:
                blockers.append(f"PHASE3.B22_PARTICIPATION_UNPROVEN:{key}")

        if (metrics.get("case_mgmt_cases_created_delta") or 0.0) > (metrics.get("case_mgmt_case_triggers_delta") or 0.0):
            blockers.append("PHASE3.B24_CASE_IDEMPOTENCY_UNPROVEN:cases_created_exceeds_triggers")

        if (metrics.get("label_store_accepted_delta") or 0.0) < (metrics.get("case_mgmt_labels_accepted_delta") or 0.0):
            blockers.append("PHASE3.B24_LABEL_COMMIT_UNDERCOUNT:label_store_below_case_mgmt")

        for key, value in integrity.items():
            if value is None:
                blockers.append(f"PHASE3.B24_INTEGRITY_SIGNAL_UNREADABLE:{key}")
                continue
            if key == "case_mgmt_evidence_pending_delta":
                if value > 0.0:
                    blockers.append("PHASE3.B24_EVIDENCE_PENDING_PRESENT")
                continue
            if key == "label_store_pending_delta":
                if value > 0.0:
                    blockers.append("PHASE3.B24_LABEL_PENDING_PRESENT")
                continue
            if value > 0.0:
                blockers.append(f"PHASE3.B24_INTEGRITY_BREACH:{key}:{value:.0f}")

        if not any(item.startswith("PHASE3.B22") for item in blockers if ":case_trigger" not in item):
            cross_plane["promoted_upstream_base"] = "PASS"
        if (metrics.get("case_trigger_triggers_seen_delta") or 0.0) > 0.0 and (
            (integrity.get("case_trigger_duplicates_delta") or 0.0) == 0.0
            and (integrity.get("case_trigger_quarantine_delta") or 0.0) == 0.0
            and (integrity.get("case_trigger_publish_ambiguous_delta") or 0.0) == 0.0
            and (integrity.get("case_trigger_payload_mismatch_delta") or 0.0) == 0.0
        ):
            cross_plane["case_trigger"] = "PASS"
        if (metrics.get("case_mgmt_cases_created_delta") or 0.0) > 0.0 and (
            (integrity.get("case_mgmt_payload_mismatches_delta") or 0.0) == 0.0
            and (integrity.get("case_mgmt_anomalies_total_delta") or 0.0) == 0.0
            and (integrity.get("case_mgmt_labels_rejected_delta") or 0.0) == 0.0
            and (integrity.get("case_mgmt_evidence_pending_delta") or 0.0) == 0.0
            and (integrity.get("case_mgmt_evidence_unavailable_delta") or 0.0) == 0.0
        ):
            cross_plane["case_management"] = "PASS"
        if (metrics.get("label_store_accepted_delta") or 0.0) > 0.0 and (
            (integrity.get("label_store_pending_delta") or 0.0) == 0.0
            and (integrity.get("label_store_rejected_delta") or 0.0) == 0.0
            and (integrity.get("label_store_duplicate_delta") or 0.0) == 0.0
            and (integrity.get("label_store_payload_hash_mismatch_delta") or 0.0) == 0.0
            and (integrity.get("label_store_dedupe_tuple_collision_delta") or 0.0) == 0.0
            and (integrity.get("label_store_missing_evidence_refs_delta") or 0.0) == 0.0
            and (integrity.get("label_store_anomalies_total_delta") or 0.0) == 0.0
        ):
            cross_plane["label_store"] = "PASS"

    overall_pass = len(set(blockers)) == 0
    assessment = (
        "Phase 3 bounded Case + Label correctness is green on the promoted upstream production path."
        if overall_pass
        else "Phase 3 bounded Case + Label correctness is not green yet; only the failed boundary should be remediated."
    )

    scorecard = {
        "phase": "PHASE3",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "window_label": str((summary or {}).get("window_label") or "phase3_case_label"),
        "control_bootstrap": {
            "overall_pass": bool(bootstrap.get("overall_pass")),
            "scenario_run_id": bootstrap.get("scenario_run_id"),
            "facts_view_ref": ((bootstrap.get("sr") or {}).get("facts_view_ref")),
            "status_ref": ((bootstrap.get("sr") or {}).get("status_ref")),
        },
        "ingress": {
            "observed_admitted_eps": admitted_eps,
            "admitted_request_count": admitted_total,
            "error_rate_ratio": error_rate,
            "4xx_rate_ratio": error_4xx,
            "5xx_rate_ratio": error_5xx,
            "latency_p95_ms": p95,
            "latency_p99_ms": p99,
            "covered_metric_seconds": ((summary or {}).get("performance_window") or {}).get("covered_metric_seconds"),
        },
        "component_deltas": metrics,
        "integrity": integrity,
        "cross_plane": cross_plane,
        "charter": {
            "mission_binding": dict(charter.get("mission_binding") or {}),
            "slice": dict(charter.get("phase3_slice") or {}),
        },
        "assessment": assessment,
        "overall_pass": overall_pass,
        "blocker_ids": sorted(set(blockers)),
        "notes": notes,
    }
    report = {
        "phase": "PHASE3",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "cross_plane": cross_plane,
        "component_deltas": metrics,
        "integrity": integrity,
        "control_bootstrap": bootstrap,
        "assessment": assessment,
        "notes": notes,
    }
    receipt = {
        "phase": "PHASE3",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "verdict": "PHASE3_READY" if overall_pass else "HOLD_REMEDIATE",
        "next_phase": "PHASE4" if overall_pass else "PHASE3",
        "open_blockers": len(set(blockers)),
        "blocker_ids": sorted(set(blockers)),
    }

    dump_json(root / "phase3_case_label_scorecard.json", scorecard)
    dump_json(root / "phase3_case_label_cross_plane_report.json", report)
    dump_json(root / "phase3_execution_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
