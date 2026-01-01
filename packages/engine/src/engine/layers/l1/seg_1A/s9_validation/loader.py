"""Load governed artefacts required for the S9 validation pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

import pandas as pd
import polars as pl

from ..s0_foundations.exceptions import err
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from ..shared.passed_flag import parse_passed_flag
from .contexts import S9DeterministicContext, S9InputSurfaces
from . import constants as c

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
    """Resolve upstream artefacts and build the immutable S9 context."""

    base_path = Path(base_path).expanduser().resolve()
    dictionary = dictionary or load_dictionary()

    outlet_path = resolve_dataset_path(
        c.DATASET_OUTLET_CATALOGUE,
        base_path=base_path,
        template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    outlet_df, outlet_files = _read_parquet_partition(outlet_path)

    candidate_path = resolve_dataset_path(
        c.DATASET_S3_CANDIDATE_SET,
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    candidate_df, candidate_files = _read_parquet_partition(candidate_path)

    counts_df = None
    counts_files: Sequence[Path] = ()
    try:
        counts_path = resolve_dataset_path(
            c.DATASET_S3_INTEGERISED_COUNTS,
            base_path=base_path,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
    except Exception:
        counts_path = None

    if counts_path is not None:
        if counts_path.exists() or counts_path.parent.exists():
            counts_df, counts_files = _read_parquet_partition(counts_path)

    membership_df = None
    membership_files: Sequence[Path] = ()
    membership_path = None
    try:
        membership_path = resolve_dataset_path(
            c.DATASET_S6_MEMBERSHIP,
            base_path=base_path,
            template_args={"seed": seed, "parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
    except Exception:
        membership_path = None

    if membership_path is not None and (membership_path.exists() or membership_path.parent.exists()):
        _verify_s6_pass_receipt(
            base_path=base_path,
            seed=seed,
            parameter_hash=parameter_hash,
            dictionary=dictionary,
        )
        membership_df, membership_files = _read_parquet_partition(membership_path)

    site_sequence_df = None
    site_sequence_files: Sequence[Path] = ()
    try:
        site_sequence_path = resolve_dataset_path(
            c.DATASET_S3_SITE_SEQUENCE,
            base_path=base_path,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
    except Exception:
        site_sequence_path = None

    if site_sequence_path is not None and (site_sequence_path.exists() or site_sequence_path.parent.exists()):
        site_sequence_df, site_sequence_files = _read_parquet_partition(site_sequence_path)

    audit_df, audit_files = _read_jsonl_partition(
        dataset_id=c.AUDIT_LOG_ID,
        base_path=base_path,
        seed=seed,
        parameter_hash=parameter_hash,
        run_id=run_id,
        dictionary=dictionary,
    )

    trace_df, trace_files = _read_jsonl_partition(
        dataset_id=c.TRACE_LOG_ID,
        base_path=base_path,
        seed=seed,
        parameter_hash=parameter_hash,
        run_id=run_id,
        dictionary=dictionary,
    )

    rng_event_frames: dict[str, pd.DataFrame] = {}
    rng_event_paths: dict[str, Sequence[Path]] = {}
    for dataset_id in c.RNG_EVENT_DATASETS:
        frame, files = _read_jsonl_partition(
            dataset_id=dataset_id,
            base_path=base_path,
            seed=seed,
            parameter_hash=parameter_hash,
            run_id=run_id,
            dictionary=dictionary,
        )
        rng_event_frames[dataset_id] = frame if frame is not None else pd.DataFrame()
        rng_event_paths[dataset_id] = files

    surfaces = S9InputSurfaces(
        outlet_catalogue=outlet_df,
        s3_candidate_set=candidate_df,
        s3_integerised_counts=counts_df,
        s3_site_sequence=site_sequence_df,
        s6_membership=membership_df,
        nb_final_events=rng_event_frames.get(c.EVENT_FAMILY_NB_FINAL),
        sequence_finalize_events=rng_event_frames.get(c.EVENT_FAMILY_SEQUENCE_FINALIZE),
        rng_audit_log=audit_df if audit_df is not None else pd.DataFrame(),
        rng_trace_log=trace_df if trace_df is not None else pd.DataFrame(),
        rng_events=MappingProxyType(rng_event_frames),
    )

    upstream_manifest = _load_upstream_manifest(
        base_path=base_path,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
    )

    source_paths = {
        c.DATASET_OUTLET_CATALOGUE: outlet_files,
        c.DATASET_S3_CANDIDATE_SET: candidate_files,
    }
    if counts_files:
        source_paths[c.DATASET_S3_INTEGERISED_COUNTS] = counts_files
    if membership_files:
        source_paths[c.DATASET_S6_MEMBERSHIP] = membership_files
    if site_sequence_files:
        source_paths[c.DATASET_S3_SITE_SEQUENCE] = site_sequence_files
    source_paths[c.AUDIT_LOG_ID] = audit_files
    source_paths[c.TRACE_LOG_ID] = trace_files
    for dataset_id, files in rng_event_paths.items():
        source_paths[dataset_id] = files

    lineage_paths = _discover_lineage_paths(
        base_path=base_path,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
    )

    return S9DeterministicContext(
        base_path=base_path,
        seed=seed,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id=run_id,
        surfaces=surfaces,
        upstream_manifest=upstream_manifest,
        source_paths=source_paths,
        lineage_paths=lineage_paths,
    )


def _read_parquet_partition(path: Path) -> tuple[pl.DataFrame, Sequence[Path]]:
    paths = _discover_partition_files(path, suffix=".parquet")
    if not paths:
        raise err("E_S9_INPUT_MISSING", f"expected parquet files under {path.parent}")
    frames = [pl.read_parquet(file_path) for file_path in paths]
    frame = pl.concat(frames, how="vertical") if len(frames) > 1 else frames[0]
    return frame, tuple(paths)


def _read_jsonl_partition(
    *,
    dataset_id: str,
    base_path: Path,
    seed: int,
    parameter_hash: str,
    run_id: str,
    dictionary: Mapping[str, object],
) -> tuple[pd.DataFrame | None, Sequence[Path]]:
    try:
        path = resolve_dataset_path(
            dataset_id,
            base_path=base_path,
            template_args={
                "seed": seed,
                "parameter_hash": parameter_hash,
                "run_id": run_id,
            },
            dictionary=dictionary,
        )
    except Exception:
        return None, ()

    files = _discover_partition_files(path, suffix=".jsonl")
    if not files:
        return None, ()
    records: list[dict] = []
    for file_path in files:
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:  # pragma: no cover - malformed upstream
                    raise err(
                        "E_S9_JSON_INVALID",
                        f"failed to decode JSON line in {file_path}: {exc}",
                    ) from exc
    frame = pd.DataFrame.from_records(records) if records else pd.DataFrame()
    return frame, tuple(files)


def _discover_partition_files(path: Path, *, suffix: str) -> Sequence[Path]:
    """Return all files for a partition, handling template placeholders."""

    path = Path(path)
    if path.is_file():
        return (path,)

    parent = path.parent
    if not parent.exists():
        return ()
    pattern = path.name
    if "*" not in pattern:
        if path.exists():
            return (path,)
        pattern = "part-*.parquet" if suffix == ".parquet" else "part-*.jsonl"
    candidates = sorted(parent.glob(pattern.replace("00000", "*")))
    return [candidate for candidate in candidates if candidate.suffix == suffix]


def _verify_s6_pass_receipt(
    *,
    base_path: Path,
    seed: int,
    parameter_hash: str,
    dictionary: Mapping[str, object],
) -> None:
    receipt_dir = resolve_dataset_path(
        c.S6_RECEIPT_DATASET_ID,
        base_path=base_path,
        template_args={"seed": seed, "parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    receipt_path = receipt_dir / "S6_VALIDATION.json"
    flag_path = receipt_dir / "_passed.flag"
    if not receipt_path.exists() or not flag_path.exists():
        raise err(
            "E_S9_S6_RECEIPT_MISSING",
            f"S6 PASS receipt missing under {receipt_dir}",
        )

    payload = receipt_path.read_text(encoding="utf-8")
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    try:
        actual = parse_passed_flag(flag_path.read_text(encoding="ascii"))
    except ValueError as exc:
        raise err("E_S9_S6_RECEIPT_INVALID", f"six _passed.flag malformed at {flag_path}") from exc
    if expected != actual:
        raise err(
            "E_S9_S6_RECEIPT_INVALID",
            "S6 PASS receipt digest mismatch",
        )


def _load_upstream_manifest(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> Mapping[str, object] | None:
    """Load the upstream S0 manifest for context reuse when present."""

    bundle_dir = resolve_dataset_path(
        c.VALIDATION_DATASET_ID,
        base_path=base_path,
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    manifest_path = bundle_dir / "MANIFEST.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - indicates upstream corruption
        raise err(
            "E_S9_UPSTREAM_MANIFEST_INVALID",
            f"failed to decode upstream MANIFEST.json: {exc}",
        ) from exc


def _discover_lineage_paths(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> Mapping[str, Path]:
    bundle_dir = resolve_dataset_path(
        c.VALIDATION_DATASET_ID,
        base_path=base_path,
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    paths: dict[str, Path] = {}
    for name in ("param_digest_log.jsonl", "fingerprint_artifacts.jsonl", "MANIFEST.json"):
        candidate = bundle_dir / name
        if candidate.exists():
            paths[name] = candidate
    return MappingProxyType(paths)
