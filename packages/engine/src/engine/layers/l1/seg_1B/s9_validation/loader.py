"""Input resolution helpers for Segment 1B S9 validation."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

import pandas as pd
import polars as pl

from ..shared import dictionary as dict_utils
from . import constants as c
from .contexts import S9DeterministicContext, S9InputSurfaces
from .exceptions import err

__all__ = ["load_deterministic_context"]


def load_deterministic_context(
    *,
    base_path: Path,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
    dictionary: Mapping[str, object] | None = None,
) -> S9DeterministicContext:
    """Resolve governed artefacts and build the deterministic S9 context."""

    base_path = Path(base_path).expanduser().resolve()
    dictionary = dictionary or dict_utils.load_dictionary()

    s7_path = dict_utils.resolve_dataset_path(
        c.DATASET_S7_SITE_SYNTHESIS,
        base_path=base_path,
        template_args={
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
        },
        dictionary=dictionary,
    )
    s7_frame, s7_files = _read_parquet_partition(s7_path, error_code="E901_ROW_MISSING")

    s8_path = dict_utils.resolve_dataset_path(
        c.DATASET_SITE_LOCATIONS,
        base_path=base_path,
        template_args={
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
        },
        dictionary=dictionary,
    )
    s8_frame, s8_files = _read_parquet_partition(s8_path, error_code="E902_ROW_EXTRA")

    rng_event_frames: dict[str, pd.DataFrame] = {}
    rng_event_paths: dict[str, Sequence[Path]] = {}
    for dataset_id in c.RNG_EVENT_FAMILIES:
        frame, files = _read_jsonl_partition(
            dataset_id=dataset_id,
            base_path=base_path,
            seed=seed,
            parameter_hash=parameter_hash,
            run_id=run_id,
            dictionary=dictionary,
        )
        rng_event_frames[dataset_id] = frame
        rng_event_paths[dataset_id] = files

    audit_frame, audit_files = _read_jsonl_partition(
        dataset_id=c.RNG_AUDIT_LOG,
        base_path=base_path,
        seed=seed,
        parameter_hash=parameter_hash,
        run_id=run_id,
        dictionary=dictionary,
        allow_empty=True,
    )

    trace_frame, trace_files = _read_jsonl_partition(
        dataset_id=c.RNG_TRACE_LOG,
        base_path=base_path,
        seed=seed,
        parameter_hash=parameter_hash,
        run_id=run_id,
        dictionary=dictionary,
        allow_empty=True,
    )

    surfaces = S9InputSurfaces(
        s7_site_synthesis=s7_frame,
        site_locations=s8_frame,
        rng_events=MappingProxyType(rng_event_frames),
        rng_audit_log=audit_frame if not audit_frame.empty else None,
        rng_trace_log=trace_frame if not trace_frame.empty else None,
    )

    source_paths: dict[str, Sequence[Path]] = {
        c.DATASET_S7_SITE_SYNTHESIS: s7_files,
        c.DATASET_SITE_LOCATIONS: s8_files,
    }
    for dataset_id, files in rng_event_paths.items():
        if files:
            source_paths[dataset_id] = files
    if audit_files:
        source_paths[c.RNG_AUDIT_LOG] = audit_files
    if trace_files:
        source_paths[c.RNG_TRACE_LOG] = trace_files

    return S9DeterministicContext(
        base_path=base_path,
        seed=seed,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id=run_id,
        dictionary=dictionary,
        surfaces=surfaces,
        source_paths=MappingProxyType(source_paths),
        lineage_paths={},
    )


def _read_parquet_partition(path: Path, *, error_code: str) -> tuple[pl.DataFrame, Sequence[Path]]:
    files = _discover_partition_files(path, suffix=".parquet")
    if not files:
        raise err(error_code, f"expected parquet files under '{path}'")
    frames = [pl.read_parquet(file_path) for file_path in files]
    frame = pl.concat(frames, how="vertical") if len(frames) > 1 else frames[0]
    return frame, tuple(files)


def _read_jsonl_partition(
    *,
    dataset_id: str,
    base_path: Path,
    seed: int,
    parameter_hash: str,
    run_id: str,
    dictionary: Mapping[str, object],
    allow_empty: bool = False,
) -> tuple[pd.DataFrame, Sequence[Path]]:
    template_args = {
        "seed": seed,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
    }
    dataset_path = dict_utils.resolve_dataset_path(
        dataset_id,
        base_path=base_path,
        template_args=template_args,
        dictionary=dictionary,
    )
    files = _discover_partition_files(dataset_path, suffix=".jsonl")
    if not files:
        if allow_empty:
            return pd.DataFrame(), ()
        raise err("E907_RNG_BUDGET_OR_COUNTERS", f"expected JSONL files under '{dataset_path}'")
    frames = [pd.read_json(file_path, orient="records", lines=True) for file_path in files]
    frame = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    return frame, tuple(files)


def _discover_partition_files(path: Path, *, suffix: str) -> list[Path]:
    directory = path if path.is_dir() else path.parent
    pattern = "*" + suffix.lstrip("*")
    files = sorted(directory.glob(pattern))
    return [file_path for file_path in files if file_path.suffix == suffix]
