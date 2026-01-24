"""SR ledger persistence and commit ordering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import RunPlan, RunStatus, RunStatusState
from .schemas import SchemaRegistry
from .storage import ArtifactRef, LocalObjectStore


@dataclass(frozen=True)
class LedgerPaths:
    run_plan: str
    run_record: str
    run_status: str
    run_facts_view: str
    ready_signal: str
    record_index: str


class Ledger:
    def __init__(self, store: LocalObjectStore, prefix: str, schemas: SchemaRegistry | None = None) -> None:
        self.store = store
        self.prefix = prefix.rstrip("/")
        self.schemas = schemas

    def _paths(self, run_id: str) -> LedgerPaths:
        return LedgerPaths(
            run_plan=f"{self.prefix}/run_plan/{run_id}.json",
            run_record=f"{self.prefix}/run_record/{run_id}.jsonl",
            run_status=f"{self.prefix}/run_status/{run_id}.json",
            run_facts_view=f"{self.prefix}/run_facts_view/{run_id}.json",
            ready_signal=f"{self.prefix}/ready_signal/{run_id}.json",
            record_index=f"{self.prefix}/run_record_index/{run_id}.json",
        )

    def anchor_run(self, run_id: str, record_event: dict[str, Any]) -> tuple[ArtifactRef, ArtifactRef]:
        paths = self._paths(run_id)
        self._validate_record(record_event)
        self._append_record(paths, record_event)
        status = RunStatus(
            run_id=run_id,
            state=RunStatusState.OPEN,
            updated_at_utc=datetime.now(tz=timezone.utc),
            record_ref=paths.run_record,
        )
        status_payload = status.model_dump(mode="json", exclude_none=True)
        self._validate_payload("run_status.schema.yaml", status_payload)
        status_ref = self.store.write_json(paths.run_status, status_payload)
        return ArtifactRef(path=paths.run_record), status_ref

    def commit_plan(self, plan: RunPlan, record_event: dict[str, Any]) -> ArtifactRef:
        paths = self._paths(plan.run_id)
        plan_payload = plan.model_dump(mode="json", exclude_none=True)
        if self.store.exists(paths.run_plan):
            existing = self.store.read_json(paths.run_plan)
            if existing != plan_payload:
                raise RuntimeError("PLAN_DRIFT")
            return ArtifactRef(path=paths.run_plan)
        self._validate_payload("run_plan.schema.yaml", plan_payload)
        self._validate_record(record_event)
        self.store.write_json(paths.run_plan, plan_payload)
        self._append_record(paths, record_event)
        self._update_status(
            plan.run_id,
            RunStatusState.PLANNED,
            record_ref=paths.run_record,
        )
        return ArtifactRef(path=paths.run_plan)

    def commit_facts_view(self, run_id: str, facts_view: dict[str, Any]) -> ArtifactRef:
        paths = self._paths(run_id)
        if self.store.exists(paths.run_facts_view):
            existing = self.store.read_json(paths.run_facts_view)
            if existing != facts_view:
                raise RuntimeError("FACTS_VIEW_DRIFT")
            return ArtifactRef(path=paths.run_facts_view)
        self._validate_payload("run_facts_view.schema.yaml", facts_view)
        return self.store.write_json(paths.run_facts_view, facts_view)

    def commit_ready(self, run_id: str, record_event: dict[str, Any]) -> ArtifactRef:
        paths = self._paths(run_id)
        self._validate_record(record_event)
        self._update_status(
            run_id,
            RunStatusState.READY,
            record_ref=paths.run_record,
            facts_view_ref=paths.run_facts_view,
        )
        self._append_record(paths, record_event)
        return ArtifactRef(path=paths.run_status)

    def mark_executing(self, run_id: str, record_event: dict[str, Any]) -> ArtifactRef:
        paths = self._paths(run_id)
        self._validate_record(record_event)
        self._update_status(run_id, RunStatusState.EXECUTING, record_ref=paths.run_record)
        self._append_record(paths, record_event)
        return ArtifactRef(path=paths.run_status)

    def commit_terminal(self, run_id: str, state: RunStatusState, reason: str, record_event: dict[str, Any]) -> ArtifactRef:
        if state not in (RunStatusState.FAILED, RunStatusState.QUARANTINED):
            raise ValueError("terminal state must be FAILED or QUARANTINED")
        paths = self._paths(run_id)
        self._validate_record(record_event)
        self._update_status(run_id, state, reason_code=reason, record_ref=paths.run_record)
        self._append_record(paths, record_event)
        return ArtifactRef(path=paths.run_status)

    def commit_waiting(self, run_id: str, record_event: dict[str, Any]) -> ArtifactRef:
        paths = self._paths(run_id)
        self._validate_record(record_event)
        self._update_status(run_id, RunStatusState.WAITING_EVIDENCE, record_ref=paths.run_record)
        self._append_record(paths, record_event)
        return ArtifactRef(path=paths.run_status)

    def append_record(self, run_id: str, record_event: dict[str, Any]) -> ArtifactRef:
        paths = self._paths(run_id)
        self._validate_record(record_event)
        self._append_record(paths, record_event)
        return ArtifactRef(path=paths.run_record)

    def write_ready_signal(self, run_id: str, payload: dict[str, Any]) -> ArtifactRef:
        paths = self._paths(run_id)
        self._validate_payload("run_ready_signal.schema.yaml", payload)
        return self.store.write_json(paths.ready_signal, payload)

    def read_status(self, run_id: str) -> RunStatus | None:
        paths = self._paths(run_id)
        if not self.store.exists(paths.run_status):
            return None
        return RunStatus(**self.store.read_json(paths.run_status))

    def read_facts_view(self, run_id: str) -> dict[str, Any] | None:
        paths = self._paths(run_id)
        if not self.store.exists(paths.run_facts_view):
            return None
        return self.store.read_json(paths.run_facts_view)

    def _append_record(self, paths: LedgerPaths, record_event: dict[str, Any]) -> None:
        existing_ids = set()
        if self.store.exists(paths.record_index):
            existing_ids = set(self.store.read_json(paths.record_index).get("event_ids", []))
        event_id = record_event.get("event_id")
        if event_id and event_id in existing_ids:
            return
        self.store.append_jsonl(paths.run_record, [record_event])
        if event_id:
            existing_ids.add(event_id)
            self.store.write_json(paths.record_index, {"event_ids": sorted(existing_ids)})

    def _update_status(
        self,
        run_id: str,
        state: RunStatusState,
        record_ref: str,
        facts_view_ref: str | None = None,
        reason_code: str | None = None,
    ) -> None:
        paths = self._paths(run_id)
        current = self.read_status(run_id)
        if current and not self._allowed_transition(current.state, state):
            raise RuntimeError(f"Invalid transition {current.state} -> {state}")
        status = RunStatus(
            run_id=run_id,
            state=state,
            updated_at_utc=datetime.now(tz=timezone.utc),
            reason_code=reason_code,
            record_ref=record_ref,
            facts_view_ref=facts_view_ref or (current.facts_view_ref if current else None),
        )
        status_payload = status.model_dump(mode="json", exclude_none=True)
        self._validate_payload("run_status.schema.yaml", status_payload)
        self.store.write_json(paths.run_status, status_payload)

    def _allowed_transition(self, current: RunStatusState, next_state: RunStatusState) -> bool:
        allowed = {
            RunStatusState.OPEN: {RunStatusState.PLANNED, RunStatusState.FAILED, RunStatusState.QUARANTINED},
            RunStatusState.PLANNED: {RunStatusState.EXECUTING, RunStatusState.WAITING_EVIDENCE, RunStatusState.READY, RunStatusState.FAILED, RunStatusState.QUARANTINED},
            RunStatusState.EXECUTING: {RunStatusState.WAITING_EVIDENCE, RunStatusState.READY, RunStatusState.FAILED, RunStatusState.QUARANTINED},
            RunStatusState.WAITING_EVIDENCE: {RunStatusState.READY, RunStatusState.FAILED, RunStatusState.QUARANTINED},
            RunStatusState.READY: {RunStatusState.READY},
            RunStatusState.FAILED: {RunStatusState.FAILED},
            RunStatusState.QUARANTINED: {RunStatusState.QUARANTINED},
        }
        return next_state in allowed.get(current, set())

    def _validate_payload(self, schema_name: str, payload: dict[str, Any]) -> None:
        if self.schemas is None:
            return
        self.schemas.validate(schema_name, payload)

    def _validate_record(self, record_event: dict[str, Any]) -> None:
        self._validate_payload("run_record.schema.yaml", record_event)
