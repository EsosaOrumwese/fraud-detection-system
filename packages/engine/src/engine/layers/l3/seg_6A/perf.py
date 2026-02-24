"""Performance instrumentation helpers for Segment 6A."""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro


SEGMENT_ID = "6A"
STATE_ORDER = ("S2", "S3", "S4", "S5")
STATE_BUDGET_SECONDS = {
    "S2": 120.0,
    "S3": 180.0,
    "S4": 90.0,
    "S5": 120.0,
}
SEGMENT_BUDGET_SECONDS = 540.0


def _perf_root(
    run_paths: RunPaths,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
) -> Path:
    return (
        run_paths.run_root
        / "reports"
        / "layer3"
        / "6A"
        / "perf"
        / f"seed={int(seed)}"
        / f"parameter_hash={parameter_hash}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / f"run_id={run_id}"
    )


def _write_text_atomic(path: Path, text: str) -> None:
    tmp_dir = path.parent / f"_tmp.perf.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    tmp_path.write_text(text, encoding="utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(path)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


class Segment6APerfRecorder:
    """Collect and emit substep timings for one Segment 6A state run."""

    def __init__(
        self,
        *,
        run_paths: RunPaths,
        run_id: str,
        seed: int,
        parameter_hash: str,
        manifest_fingerprint: str,
        state: str,
        logger,
    ) -> None:
        self._run_paths = run_paths
        self._run_id = run_id
        self._seed = int(seed)
        self._parameter_hash = parameter_hash
        self._manifest_fingerprint = manifest_fingerprint
        self._state = str(state).upper()
        self._logger = logger
        self._events: list[dict] = []
        self._sequence = 0

    @property
    def events_path(self) -> Path:
        return _perf_root(
            self._run_paths,
            self._seed,
            self._parameter_hash,
            self._manifest_fingerprint,
            self._run_id,
        ) / f"{self._state.lower()}_perf_events_6A.jsonl"

    @contextmanager
    def step(self, step_name: str) -> Iterator[None]:
        start = time.monotonic()
        status = "ok"
        error_type: Optional[str] = None
        try:
            yield
        except Exception as exc:
            status = "error"
            error_type = type(exc).__name__
            raise
        finally:
            self.record_elapsed(step_name, start, status=status, error_type=error_type)

    def record_elapsed(
        self,
        step_name: str,
        started_monotonic: float,
        *,
        status: str = "ok",
        error_type: Optional[str] = None,
    ) -> None:
        elapsed = max(time.monotonic() - started_monotonic, 0.0)
        self._sequence += 1
        event = {
            "segment": SEGMENT_ID,
            "state": self._state,
            "step": str(step_name),
            "sequence": int(self._sequence),
            "elapsed_s": float(elapsed),
            "status": str(status),
            "captured_utc": utc_now_rfc3339_micro(),
            "run_id": self._run_id,
            "seed": self._seed,
            "parameter_hash": self._parameter_hash,
            "manifest_fingerprint": self._manifest_fingerprint,
        }
        if error_type:
            event["error_type"] = error_type
        self._events.append(event)

    def write_events(self, *, raise_on_error: bool = False) -> Optional[Path]:
        if not self._events:
            return None
        try:
            payload = "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in self._events) + "\n"
            path = self.events_path
            _write_text_atomic(path, payload)
            self._logger.info(
                "S%s: wrote perf events (path=%s rows=%s)",
                self._state[1:] if self._state.startswith("S") else self._state,
                path,
                len(self._events),
            )
            return path
        except Exception:
            if raise_on_error:
                raise
            self._logger.warning("S%s: failed to write perf events", self._state, exc_info=True)
            return None


def write_segment6a_perf_summary_and_budget(
    *,
    run_paths: RunPaths,
    run_id: str,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    logger,
) -> tuple[Path, Path]:
    perf_root = _perf_root(run_paths, int(seed), parameter_hash, manifest_fingerprint, run_id)
    state_step_totals: dict[str, dict[str, float]] = {
        state: defaultdict(float) for state in STATE_ORDER
    }  # type: ignore[assignment]
    state_totals: dict[str, float] = {state: 0.0 for state in STATE_ORDER}
    parsed_rows = 0

    for state in STATE_ORDER:
        events_path = perf_root / f"{state.lower()}_perf_events_6A.jsonl"
        if not events_path.exists():
            continue
        with events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                row = json.loads(text)
                step = str(row.get("step") or "unknown")
                elapsed_s = float(row.get("elapsed_s") or 0.0)
                state_step_totals[state][step] += elapsed_s
                state_totals[state] += elapsed_s
                parsed_rows += 1

    hotspot_rows: list[dict] = []
    for state in STATE_ORDER:
        for step_name, elapsed_s in state_step_totals[state].items():
            hotspot_rows.append({"state": state, "step": step_name, "elapsed_s": float(elapsed_s)})
    hotspot_rows.sort(key=lambda row: row["elapsed_s"], reverse=True)

    summary_payload = {
        "segment": SEGMENT_ID,
        "run_id": run_id,
        "seed": int(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "captured_utc": utc_now_rfc3339_micro(),
        "event_rows_parsed": int(parsed_rows),
        "state_totals_s": {state: float(state_totals[state]) for state in STATE_ORDER},
        "state_step_totals_s": {
            state: {step: float(value) for step, value in sorted(state_step_totals[state].items())}
            for state in STATE_ORDER
        },
        "hotspot_ranking": hotspot_rows,
    }
    summary_path = perf_root / "perf_summary_6A.json"
    _write_text_atomic(summary_path, json.dumps(summary_payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n")

    state_budget_checks = {}
    state_all_pass = True
    for state in STATE_ORDER:
        elapsed = float(state_totals[state])
        budget = float(STATE_BUDGET_SECONDS[state])
        passed = elapsed <= budget
        state_budget_checks[state] = {
            "elapsed_s": elapsed,
            "budget_s": budget,
            "pass": bool(passed),
        }
        state_all_pass = state_all_pass and passed

    segment_elapsed = float(sum(state_totals.values()))
    segment_pass = segment_elapsed <= SEGMENT_BUDGET_SECONDS
    budget_payload = {
        "segment": SEGMENT_ID,
        "run_id": run_id,
        "seed": int(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "captured_utc": utc_now_rfc3339_micro(),
        "state_budget_checks": state_budget_checks,
        "segment_elapsed_s": segment_elapsed,
        "segment_budget_s": float(SEGMENT_BUDGET_SECONDS),
        "segment_budget_pass": bool(segment_pass),
        "overall_budget_pass": bool(state_all_pass and segment_pass),
    }
    budget_path = perf_root / "perf_budget_check_6A.json"
    _write_text_atomic(budget_path, json.dumps(budget_payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n")
    logger.info(
        "S5: wrote segment 6A perf summary+budget (summary=%s budget=%s)",
        summary_path,
        budget_path,
    )
    return summary_path, budget_path
