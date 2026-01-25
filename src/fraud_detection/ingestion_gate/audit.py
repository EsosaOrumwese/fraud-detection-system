"""Audit verification for pull runs (hash chain + checkpoints)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .admission import IngestionGate
from .pull_state import PullRunStore, _hash_event


@dataclass(frozen=True)
class AuditCheck:
    ok: bool
    reason: str | None = None
    detail: str | None = None


def verify_pull_run(gate: IngestionGate, run_id: str) -> dict[str, Any]:
    pull_store = gate.pull_store
    status = pull_store.read_status(run_id)
    if not status:
        report = {
            "run_id": run_id,
            "status": "FAIL",
            "checked_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "checks": {"status": {"ok": False, "reason": "STATUS_MISSING"}},
        }
        gate.governance.emit_audit_verification(report)
        return report

    chain = _verify_hash_chain(pull_store, run_id)
    checkpoints = _verify_checkpoints(pull_store, run_id, status)
    overall = "PASS" if chain.ok and checkpoints.ok else "FAIL"
    report = {
        "run_id": run_id,
        "status": overall,
        "checked_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "checks": {
            "hash_chain": _check_payload(chain),
            "checkpoints": _check_payload(checkpoints),
        },
    }
    gate.governance.emit_audit_verification(report)
    return report


def _verify_hash_chain(pull_store: PullRunStore, run_id: str) -> AuditCheck:
    events = pull_store.iter_events(run_id)
    if not events:
        return AuditCheck(ok=False, reason="EVENT_LOG_EMPTY")
    prev_hash = "0" * 64
    for idx, event in enumerate(events):
        stored_prev = event.get("prev_hash")
        stored_hash = event.get("event_hash")
        if not stored_hash:
            return AuditCheck(ok=False, reason="EVENT_HASH_MISSING", detail=f"idx={idx}")
        if stored_prev != prev_hash:
            return AuditCheck(ok=False, reason="PREV_HASH_MISMATCH", detail=f"idx={idx}")
        expected = _hash_event(prev_hash, event)
        if expected != stored_hash:
            return AuditCheck(ok=False, reason="EVENT_HASH_MISMATCH", detail=f"idx={idx}")
        prev_hash = stored_hash
    return AuditCheck(ok=True)


def _verify_checkpoints(pull_store: PullRunStore, run_id: str, status: dict[str, Any]) -> AuditCheck:
    output_ids = status.get("output_ids") or []
    checkpoints = pull_store.list_checkpoints(run_id)
    if output_ids and not checkpoints:
        return AuditCheck(ok=False, reason="CHECKPOINTS_MISSING")
    by_output: dict[str, list[dict[str, Any]]] = {}
    for payload in checkpoints:
        output_id = payload.get("output_id")
        if not output_id:
            continue
        by_output.setdefault(output_id, []).append(payload)
    for output_id in output_ids:
        entries = by_output.get(output_id, [])
        if not entries:
            return AuditCheck(ok=False, reason="OUTPUT_CHECKPOINT_MISSING", detail=output_id)
        shard_total = 0
        shard_ids: set[int] = set()
        for entry in entries:
            total = entry.get("shard_total")
            if isinstance(total, int) and total > shard_total:
                shard_total = total
            shard_id = entry.get("shard_id")
            if isinstance(shard_id, int):
                shard_ids.add(shard_id)
        if shard_total and len(shard_ids) < shard_total:
            return AuditCheck(ok=False, reason="SHARD_INCOMPLETE", detail=output_id)
    return AuditCheck(ok=True)


def _check_payload(check: AuditCheck) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": check.ok}
    if check.reason:
        payload["reason"] = check.reason
    if check.detail:
        payload["detail"] = check.detail
    return payload
