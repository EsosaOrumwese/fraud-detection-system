"""Orchestrator for S9 validation (Layer 1 / Segment 1A)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from . import constants as c
from .contexts import S9DeterministicContext, S9ValidationResult
from .loader import load_deterministic_context
from .persist import PersistConfig, write_stage_log, write_validation_bundle
from .validate import validate_outputs

__all__ = ["S9Runner", "S9RunOutputs"]


@dataclass(frozen=True)
class S9RunOutputs:
    """Materialised artefacts emitted by the S9 runner."""

    deterministic: S9DeterministicContext
    result: S9ValidationResult
    bundle_path: Path
    passed_flag_path: Path | None
    stage_log_path: Path


class S9Runner:
    """Execute the S9 validation pipeline end-to-end."""

    def run(
        self,
        *,
        base_path: Path,
        seed: int,
        parameter_hash: str,
        manifest_fingerprint: str,
        run_id: str,
        dictionary: Mapping[str, object] | None = None,
    ) -> S9RunOutputs:
        stage_logger = _StageLogger(
            base_path=Path(base_path),
            seed=seed,
            parameter_hash=parameter_hash,
            run_id=run_id,
        )

        stage_logger.begin("load_inputs")
        deterministic = load_deterministic_context(
            base_path=base_path,
            seed=seed,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            run_id=run_id,
            dictionary=dictionary,
        )
        stage_logger.end("load_inputs")

        stage_logger.begin("validate")
        result = validate_outputs(deterministic)
        stage_logger.end("validate", extra={"passed": result.passed, "failure_count": len(result.failures)})

        stage_logger.begin("persist_bundle")
        bundle_path, flag_path = write_validation_bundle(
            context=deterministic,
            result=result,
            config=PersistConfig(base_path=deterministic.base_path, manifest_fingerprint=manifest_fingerprint),
        )
        stage_logger.end("persist_bundle")

        stage_log_path = deterministic.base_path / c.STAGE_LOG_ROOT / c.STAGE_LOG_FILENAME
        write_stage_log(path=stage_log_path, records=stage_logger.records)

        return S9RunOutputs(
            deterministic=deterministic,
            result=result,
            bundle_path=bundle_path,
            passed_flag_path=flag_path,
            stage_log_path=stage_log_path,
        )


class _StageLogger:
    """Structured stage logger for S9."""

    def __init__(self, *, base_path: Path, seed: int, parameter_hash: str, run_id: str) -> None:
        self._seed = seed
        self._parameter_hash = parameter_hash
        self._run_id = run_id
        self._base_path = Path(base_path).expanduser().resolve()
        self._start_ns = time.time_ns()
        self.records: list[dict[str, object]] = []
        self.begin("initialise")
        self.end("initialise")

    def begin(self, stage: str) -> None:
        self._append(stage=stage, status="begin")

    def end(self, stage: str, *, extra: Mapping[str, object] | None = None) -> None:
        self._append(stage=stage, status="end", extra=extra)

    def _append(self, *, stage: str, status: str, extra: Mapping[str, object] | None = None) -> None:
        record = {
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "stage": stage,
            "status": status,
            "seed": self._seed,
            "parameter_hash": self._parameter_hash,
            "run_id": self._run_id,
            "elapsed_ns": time.time_ns() - self._start_ns,
        }
        if extra:
            record["extra"] = dict(extra)
        self.records.append(record)

