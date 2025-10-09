"""Shared I/O helpers for loading the sealed S0 input datasets.

The functions here purposely stay small and defensive: they wrap Polars' I/O
with explicit error messages so that upstream orchestration code can present
clear failures when a dataset is missing or empty.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import polars as pl
from polars import exceptions as ple
import yaml

from ..exceptions import err


def load_parquet_table(path: Path) -> pl.DataFrame:
    """Load a Parquet dataset from a file or directory.

    S0 inputs may be published either as a single Parquet file or as a directory
    containing ``part-*.parquet`` shards.  This helper gracefully supports both
    layouts while surfacing a consistent error if the directory exists but
    contains no files.
    """

    def _read_parquet(target: Path) -> pl.DataFrame:
        if target.is_file():
            return pl.read_parquet(target)
        if target.is_dir():
            pattern = str(target / "*.parquet")
            lf = pl.scan_parquet(pattern)
            try:
                return lf.collect()
            except FileNotFoundError as exc:
                raise err(
                    "E_DATASET_EMPTY", f"no Parquet files found under '{target}'"
                ) from exc
        raise err("E_DATASET_NOT_FOUND", f"dataset path '{target}' does not exist")

    try:
        return _read_parquet(path)
    except Exception as exc:
        fallback = _attempt_csv_fallback(path, exc)
        if fallback is not None:
            return fallback
        detail = f"failed to load Parquet dataset '{path}': {exc}"
        raise err("E_DATASET_IO", detail) from exc


def load_yaml(path: Path) -> Dict[str, Any]:
    """Parse a YAML file and assert the root node is a mapping.

    Parameter bundles are treated as keyed documents (to line up with the
    schema specs), so anything else should be considered a configuration bug.
    """
    if not path.exists():
        raise err("E_PARAM_IO", f"YAML artefact '{path}' not found")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise err("E_YAML_ROOT", f"YAML artefact '{path}' must decode to a mapping")
    return data


def _attempt_csv_fallback(path: Path, cause: Exception) -> Optional[pl.DataFrame]:
    """Load a sibling CSV file when Parquet decoding hits unsupported INT128.

    Some upstream artefacts still ship fixed-length INT128 columns that Polars
    cannot decode yet. We fall back to the CSV manifest in that case so S0 can
    proceed deterministically while we push the data producers to emit proper
    parquet schema.
    """

    if not _looks_like_int128_issue(cause):
        return None

    csv_paths: Iterable[Path]
    if path.is_file():
        candidate = path.with_suffix(".csv")
        csv_paths = (candidate,) if candidate.exists() else ()
    elif path.is_dir():
        csv_paths = sorted(p for p in path.glob("*.csv"))
    else:
        csv_paths = ()

    frames: list[pl.DataFrame] = []
    for csv_path in csv_paths:
        try:
            frames.append(
                pl.read_csv(
                    csv_path,
                    schema_overrides={"merchant_id": pl.UInt64},
                )
            )
        except ple.ComputeError as exc:
            raise err(
                "E_DATASET_IO", f"failed to load CSV fallback '{csv_path}': {exc}"
            ) from exc

    if not frames:
        return None
    if len(frames) == 1:
        return frames[0]
    return pl.concat(frames, how="vertical_relaxed")


def _looks_like_int128_issue(err_obj: Exception) -> bool:
    """Heuristically detect the FixedLenByteArray→INT128 parquet failure."""

    message = " ".join(str(arg) for arg in getattr(err_obj, "args", ()) if arg)
    if not message and err_obj.__cause__ is not None:
        return _looks_like_int128_issue(err_obj.__cause__)  # pragma: no cover
    patterns = ("FixedLenByteArray(16)", "INT128", "Int128")
    return any(marker in message for marker in patterns)


__all__ = ["load_parquet_table", "load_yaml"]
