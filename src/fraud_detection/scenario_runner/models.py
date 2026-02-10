"""SR request/response and ledger models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Strategy(str, Enum):
    AUTO = "AUTO"
    FORCE_INVOKE = "FORCE_INVOKE"
    FORCE_REUSE = "FORCE_REUSE"


class RunStatusState(str, Enum):
    OPEN = "OPEN"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    WAITING_EVIDENCE = "WAITING_EVIDENCE"
    READY = "READY"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"


class EvidenceStatus(str, Enum):
    COMPLETE = "COMPLETE"
    WAITING = "WAITING"
    FAIL = "FAIL"
    CONFLICT = "CONFLICT"


class ScenarioBinding(BaseModel):
    scenario_id: Optional[str] = None
    scenario_set: Optional[list[str]] = None

    @model_validator(mode="after")
    def _require_binding(self) -> "ScenarioBinding":
        if bool(self.scenario_id) == bool(self.scenario_set):
            raise ValueError("Provide exactly one of scenario_id or scenario_set")
        return self


class RunWindow(BaseModel):
    window_start_utc: datetime
    window_end_utc: datetime
    window_tz: str = "UTC"

    @model_validator(mode="after")
    def _check_order(self) -> "RunWindow":
        if self.window_start_utc >= self.window_end_utc:
            raise ValueError("window_start_utc must be < window_end_utc")
        if not self.window_start_utc.tzinfo or not self.window_end_utc.tzinfo:
            raise ValueError("window_start_utc and window_end_utc must be timezone-aware")
        return self


class RunRequest(BaseModel):
    request_id: Optional[str] = None
    run_equivalence_key: str = Field(..., min_length=1)
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    scenario: ScenarioBinding
    window: RunWindow
    requested_strategy: Optional[Strategy] = None
    output_ids: Optional[list[str]] = None
    engine_run_root: Optional[str] = None
    notes: Optional[str] = None
    invoker: Optional[str] = None

    @field_validator("manifest_fingerprint", "parameter_hash")
    @classmethod
    def _hex64(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("Expected hex64 string")
        return value


class CanonicalRunIntent(BaseModel):
    request_id: Optional[str] = None
    run_equivalence_key: str
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    scenario_id: str
    scenario_set: Optional[list[str]] = None
    window_start_utc: datetime
    window_end_utc: datetime
    window_tz: str
    requested_strategy: Optional[Strategy] = None
    output_ids: Optional[list[str]] = None
    engine_run_root: Optional[str] = None
    notes: Optional[str] = None
    invoker: Optional[str] = None


class RunPlan(BaseModel):
    run_id: str
    plan_hash: str
    policy_rev: dict[str, Any]
    strategy: Strategy
    intended_outputs: list[str]
    required_gates: list[str]
    evidence_deadline_utc: datetime
    attempt_limit: int
    created_at_utc: datetime


class RunStatus(BaseModel):
    run_id: str
    state: RunStatusState
    updated_at_utc: datetime
    reason_code: Optional[str] = None
    record_ref: Optional[str] = None
    facts_view_ref: Optional[str] = None


class RunResponse(BaseModel):
    run_id: str
    state: RunStatusState
    status_ref: Optional[str] = None
    record_ref: Optional[str] = None
    facts_view_ref: Optional[str] = None
    message: Optional[str] = None


class ReemitKind(str, Enum):
    READY_ONLY = "READY_ONLY"
    TERMINAL_ONLY = "TERMINAL_ONLY"
    BOTH = "BOTH"


class ReemitRequest(BaseModel):
    run_id: str
    reemit_kind: ReemitKind = ReemitKind.BOTH
    reason: Optional[str] = None
    requested_by: Optional[str] = None
    dry_run: bool = False


class ReemitResponse(BaseModel):
    run_id: str
    status_state: Optional[RunStatusState] = None
    published: list[str] = Field(default_factory=list)
    message: Optional[str] = None
