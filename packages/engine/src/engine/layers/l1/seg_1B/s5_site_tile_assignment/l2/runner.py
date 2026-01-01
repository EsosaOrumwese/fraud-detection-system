"""Runner for Segment 1B state-5 site→tile assignment."""

from __future__ import annotations

import json
import time
from typing import Mapping, Optional

from .aggregate import (
    AssignmentContext,
    AssignmentResult,
    build_assignment_context,
    compute_assignments,
)
from .config import RunnerConfig
from .materialise import S5RunResult, materialise_assignment
from .prepare import PreparedInputs, prepare_inputs
from ...shared.dictionary import load_dictionary, resolve_dataset_path


class S5SiteTileAssignmentRunner:
    """High-level orchestration for S5 assignments."""

    def run(self, config: RunnerConfig, /) -> S5RunResult:
        dictionary = config.dictionary or load_dictionary()
        try:
            prepared: PreparedInputs = prepare_inputs(config)
            context: AssignmentContext = build_assignment_context(prepared)
            assignment: AssignmentResult = compute_assignments(context)
        except Exception as exc:
            _emit_failure_event_from_config(config=config, dictionary=dictionary, failure=exc)
            raise
        return materialise_assignment(
            prepared=prepared,
            assignment=assignment,
            iso_version=prepared.iso_version,
        )


def _emit_failure_event_from_config(
    *,
    config: RunnerConfig,
    dictionary: Mapping[str, object],
    failure: Exception,
) -> None:
    try:
        event_path = resolve_dataset_path(
            "s5_failure_event",
            base_path=config.data_root,
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
                "parameter_hash": config.parameter_hash,
            },
            dictionary=dictionary,
        )
    except Exception:
        return
    event_path.parent.mkdir(parents=True, exist_ok=True)
    code = getattr(getattr(failure, "context", None), "code", None)
    payload = {
        "event": "S5_ERROR",
        "code": code if isinstance(code, str) else "E410_NONDETERMINISTIC_OUTPUT",
        "at": _utc_now_rfc3339_micros(),
        "seed": str(config.seed),
        "manifest_fingerprint": config.manifest_fingerprint,
        "parameter_hash": config.parameter_hash,
    }
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _utc_now_rfc3339_micros() -> str:
    now = time.time()
    seconds = time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime(now))
    micros = int((now % 1) * 1_000_000)
    return f"{seconds}{micros:06d}Z"


__all__ = ["S5SiteTileAssignmentRunner"]
