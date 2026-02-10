"""Archive writer reconciliation artifact builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from fraud_detection.platform_runtime import RUNS_ROOT


@dataclass
class ArchiveWriterReconciliation:
    platform_run_id: str
    records: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        *,
        topic: str,
        partition: int,
        offset_kind: str,
        offset: str,
        outcome: str,
        payload_hash: str,
        archive_ref: str | None,
        scenario_run_id: str | None,
    ) -> None:
        self.records.append(
            {
                "topic": str(topic),
                "partition": int(partition),
                "offset_kind": str(offset_kind),
                "offset": str(offset),
                "outcome": str(outcome),
                "payload_hash": str(payload_hash),
                "archive_ref": str(archive_ref) if archive_ref else None,
                "scenario_run_id": str(scenario_run_id) if scenario_run_id else None,
            }
        )

    def summary(self) -> dict[str, Any]:
        outcome_counts: dict[str, int] = {}
        refs: list[dict[str, str]] = []
        for item in self.records:
            outcome = str(item.get("outcome") or "").strip()
            if outcome:
                outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
            ref = str(item.get("archive_ref") or "").strip()
            if ref:
                refs.append({"ref_type": "archive_ref", "ref_id": ref})
        totals = {
            "seen_total": len(self.records),
            "archived_total": int(outcome_counts.get("NEW", 0)),
            "duplicate_total": int(outcome_counts.get("DUPLICATE", 0)),
            "payload_mismatch_total": int(outcome_counts.get("PAYLOAD_MISMATCH", 0)),
        }
        return {
            "generated_at_utc": _utc_now(),
            "platform_run_id": self.platform_run_id,
            "totals": totals,
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "evidence_refs": refs[-200:],
        }

    def export(self) -> dict[str, Any]:
        payload = self.summary()
        path = RUNS_ROOT / self.platform_run_id / "archive" / "reconciliation" / "archive_writer_reconciliation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
