"""Engine invocation adapter for SR."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import subprocess
import time
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
    stdout: str | None = None
    stderr: str | None = None


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


class LocalSubprocessInvoker(EngineInvoker):
    def __init__(self, command: list[str], cwd: str | None = None, timeout_seconds: int | None = None) -> None:
        self.command = command
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds

    def invoke(self, run_id: str, attempt_no: int, invocation: dict[str, Any]) -> EngineAttemptResult:
        attempt_id = attempt_id_for(run_id, attempt_no)
        engine_root = invocation.get("engine_run_root")
        invocation_json = json.dumps(invocation, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

        scenario_binding = invocation.get("scenario_binding") or {}
        placeholders = {
            "manifest_fingerprint": invocation.get("manifest_fingerprint"),
            "parameter_hash": invocation.get("parameter_hash"),
            "seed": invocation.get("seed"),
            "run_id": invocation.get("run_id"),
            "scenario_id": scenario_binding.get("scenario_id"),
            "scenario_set": ",".join(scenario_binding.get("scenario_set", []) or []),
            "engine_run_root": engine_root,
            "invocation_json": invocation_json,
        }

        def render(token: str) -> str:
            rendered = token
            for key, value in placeholders.items():
                if value is None:
                    continue
                rendered = rendered.replace(f"{{{key}}}", str(value))
            return rendered

        command = [render(token) for token in self.command]
        env = os.environ.copy()
        env["SR_ENGINE_INVOCATION_JSON"] = invocation_json
        if engine_root:
            env["SR_ENGINE_RUN_ROOT"] = engine_root

        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=self.cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            outcome = "SUCCEEDED" if result.returncode == 0 else "FAILED"
            reason = None if result.returncode == 0 else "ENGINE_EXIT_NONZERO"
            stdout = result.stdout
            stderr = result.stderr
        except FileNotFoundError:
            outcome = "FAILED"
            reason = "ENGINE_COMMAND_MISSING"
            stdout = None
            stderr = None
        except subprocess.TimeoutExpired as exc:
            outcome = "FAILED"
            reason = "ENGINE_TIMEOUT"
            stdout = exc.stdout
            stderr = exc.stderr
        duration_ms = int((time.monotonic() - started) * 1000)

        return EngineAttemptResult(
            run_id=run_id,
            attempt_id=attempt_id,
            attempt_no=attempt_no,
            outcome=outcome,
            reason_code=reason,
            engine_run_root=engine_root,
            invocation=invocation,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
        )
