"""Engine invocation adapter for SR."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .ids import attempt_id_for


@dataclass(frozen=True)
class EngineAttemptResult:
    run_id: str
    attempt_id: str
    attempt_no: int
    outcome: str
    reason_code: str | None
    engine_run_root: str | None
    invocation: dict[str, Any]
    duration_ms: int | None = None
    run_receipt_ref: str | None = None
    logs_ref: str | None = None


class EngineInvoker:
    def invoke(self, run_id: str, attempt_no: int, invocation: dict[str, Any]) -> EngineAttemptResult:
        raise NotImplementedError


class LocalEngineInvoker(EngineInvoker):
    def __init__(self, default_engine_root: str | None = None) -> None:
        self.default_engine_root = default_engine_root

    def invoke(self, run_id: str, attempt_no: int, invocation: dict[str, Any]) -> EngineAttemptResult:
        attempt_id = attempt_id_for(run_id, attempt_no)
        engine_root = invocation.get("engine_run_root") or self.default_engine_root
        if not engine_root:
            return EngineAttemptResult(
                run_id=run_id,
                attempt_id=attempt_id,
                attempt_no=attempt_no,
                outcome="FAILED",
                reason_code="ENGINE_ROOT_MISSING",
                engine_run_root=None,
                invocation=invocation,
            )
        return EngineAttemptResult(
            run_id=run_id,
            attempt_id=attempt_id,
            attempt_no=attempt_no,
            outcome="SUCCEEDED",
            reason_code=None,
            engine_run_root=engine_root,
            invocation=invocation,
        )
