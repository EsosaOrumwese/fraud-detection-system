"""Runner scaffolding for Segment 1B S9 validation."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from . import constants as c
from .contexts import S9DeterministicContext, S9ValidationResult
from .loader import load_deterministic_context
from .persist import PersistConfig, write_stage_log, write_validation_bundle
from .validator import validate_outputs

INDEX_IDS = {
    "MANIFEST.json": "manifest",
    "parameter_hash_resolved.json": "param_hash",
    "manifest_fingerprint_resolved.json": "fingerprint",
    "rng_accounting.json": "rng_accounting",
    "s9_summary.json": "s9_summary",
    "egress_checksums.json": "egress_checksums",
    "index.json": "bundle_index",
}


@dataclass(frozen=True)
class RunnerConfig:
    """Identity inputs required to execute S9."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    dictionary: Mapping[str, object] | None = None


@dataclass(frozen=True)
class S9RunResult:
    """Outcome of the S9 runner."""

    context: S9DeterministicContext
    result: S9ValidationResult
    bundle_path: Path
    flag_path: Path | None
    stage_log_path: Path


class S9ValidationRunner:
    """High-level orchestrator for S9."""

    def run(self, config: RunnerConfig) -> S9RunResult:
        stage_logger = _StageLogger(
            base_path=Path(config.base_path),
            seed=config.seed,
            parameter_hash=config.parameter_hash,
            run_id=config.run_id,
        )

        stage_logger.begin("load_inputs")
        context = load_deterministic_context(
            base_path=config.base_path,
            seed=config.seed,
            parameter_hash=config.parameter_hash,
            manifest_fingerprint=config.manifest_fingerprint,
            run_id=config.run_id,
            dictionary=config.dictionary,
        )
        stage_logger.end("load_inputs")

        stage_logger.begin("validate")
        result = validate_outputs(context)
        stage_logger.end(
            "validate",
            extra={
                "passed": result.passed,
                "failure_count": len(result.failures),
            },
        )

        stage_logger.begin("persist_bundle")
        artifacts = _prepare_bundle_artifacts(context, result)
        bundle_path, flag_path = write_validation_bundle(
            artifacts=artifacts,
            config=PersistConfig(
                base_path=config.base_path,
                manifest_fingerprint=config.manifest_fingerprint,
                dictionary=context.dictionary,
            ),
            passed=result.passed,
        )
        stage_logger.end(
            "persist_bundle",
            extra={
                "flag_emitted": flag_path is not None,
            },
        )

        stage_log_path = Path(config.base_path) / c.STAGE_LOG_ROOT / c.STAGE_LOG_FILENAME
        write_stage_log(path=stage_log_path, records=stage_logger.records)

        return S9RunResult(
            context=context,
            result=result,
            bundle_path=bundle_path,
            flag_path=flag_path,
            stage_log_path=stage_log_path,
        )


class _StageLogger:
    """Structured stage logger mirroring Segment 1A posture."""

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


def _prepare_bundle_artifacts(
    context: S9DeterministicContext,
    result: S9ValidationResult,
) -> Mapping[str, bytes]:
    artifacts: dict[str, bytes] = {}

    def _add_json(path: str, payload: Mapping[str, object] | Sequence[object]) -> None:
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        artifacts[path] = data

    manifest_payload = {
        "identity": {
            "seed": context.seed,
            "parameter_hash": context.parameter_hash,
            "manifest_fingerprint": context.manifest_fingerprint,
            "run_id": context.run_id,
        },
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "source_paths": {
            dataset: [path.relative_to(context.base_path).as_posix() for path in paths]
            for dataset, paths in context.source_paths.items()
        },
    }
    _add_json("MANIFEST.json", manifest_payload)

    _add_json("parameter_hash_resolved.json", {"parameter_hash": context.parameter_hash})
    _add_json("manifest_fingerprint_resolved.json", {"manifest_fingerprint": context.manifest_fingerprint})
    _add_json("s9_summary.json", result.summary)
    _add_json("rng_accounting.json", result.rng_accounting)

    egress_checksums = _compute_egress_checksums(context)
    _add_json("egress_checksums.json", egress_checksums)

    index_entries = []
    for path in (
        "MANIFEST.json",
        "parameter_hash_resolved.json",
        "manifest_fingerprint_resolved.json",
        "rng_accounting.json",
        "s9_summary.json",
        "egress_checksums.json",
    ):
        index_entries.append(
            {
                "artifact_id": INDEX_IDS[path],
                "kind": "summary",
                "path": path,
                "mime": "application/json",
                "notes": None,
            }
        )

    index_entries.append(
        {
            "artifact_id": INDEX_IDS["index.json"],
            "kind": "summary",
            "path": "index.json",
            "mime": "application/json",
            "notes": None,
        }
    )
    index_entries = sorted(index_entries, key=lambda item: item["path"])
    index_bytes = json.dumps(index_entries, indent=2, sort_keys=True).encode("utf-8")
    artifacts["index.json"] = index_bytes

    return artifacts


def _compute_egress_checksums(context: S9DeterministicContext) -> Mapping[str, object]:
    files = sorted(context.source_paths.get(c.DATASET_SITE_LOCATIONS, ()))
    entries = []
    composite = hashlib.sha256()
    for file_path in files:
        payload = file_path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        composite.update(payload)
        try:
            relative = file_path.relative_to(context.base_path).as_posix()
        except ValueError:
            relative = file_path.as_posix()
        entries.append({"path": relative, "sha256_hex": digest})
    return {
        "files": entries,
        "composite_sha256_hex": composite.hexdigest() if entries else "",
    }


__all__ = ["RunnerConfig", "S9RunResult", "S9ValidationRunner"]
