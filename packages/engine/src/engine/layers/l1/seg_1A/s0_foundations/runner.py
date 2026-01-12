"""S0 foundations runner for Segment 1A."""

from __future__ import annotations

import datetime as dt
import re
import hashlib
import json
import math
import os
import platform
import shutil
import struct
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import polars as pl
import yaml

from engine.contracts.jsonschema_adapter import validate_dataframe
from engine.contracts.loader import (
    artifact_dependency_closure,
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import (
    ContractError,
    EngineFailure,
    HashingError,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.hashing import FileDigest, sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_ns, utc_now_rfc3339_micro
from engine.layers.l1.seg_1A.s0_foundations.context import MerchantUniverse, RunContext
from engine.layers.l1.seg_1A.s0_foundations.hashing import (
    NamedDigest,
    NamedPath,
    compute_manifest_fingerprint,
    compute_parameter_hash,
    compute_run_id,
)
from engine.layers.l1.seg_1A.s0_foundations.inputs import (
    InputAsset,
    resolve_reference_inputs,
)
from engine.layers.l1.seg_1A.s0_foundations.numeric_policy import run_numeric_self_tests
from engine.layers.l1.seg_1A.s0_foundations.outputs import (
    S0Outputs,
    write_gate_receipt,
    write_rng_logs,
    write_run_receipt,
    write_sealed_inputs,
)
from engine.layers.l1.seg_1A.s0_foundations.validation_bundle import (
    build_param_digest_log,
    write_failure_record,
    write_validation_bundle,
)
from engine.layers.l1.seg_1A.s0_foundations.rng import build_anchor_event
from engine.layers.l1.seg_1A.s0_foundations.eligibility import (
    build_eligibility_frame,
    load_eligibility_rules,
)


CHANNEL_MAP = {"card_present": "CP", "card_not_present": "CNP"}
_DATE_VERSION_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class S0RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    outputs: S0Outputs
    context: RunContext


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str) -> None:
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _schema_section(schema_pack: dict, section: str) -> dict:
    node = schema_pack.get(section)
    if not isinstance(node, dict):
        raise InputResolutionError(f"Schema pack missing section: {section}")
    subset = {"$id": schema_pack.get("$id", ""), "$defs": schema_pack.get("$defs", {})}
    subset.update(node)
    return subset


def _audit_schema_authority(dictionary: dict, registry: dict) -> None:
    def check_ref(ref: str, origin: str) -> None:
        if "avsc" in ref or "avro" in ref:
            raise InputResolutionError(f"Non-JSON schema reference in {origin}: {ref}")

    for section, entries in dictionary.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("schema_ref")
            if ref:
                check_ref(ref, f"dictionary:{entry.get('id', section)}")

    for subsegment in registry.get("subsegments", []):
        for artifact in subsegment.get("artifacts", []):
            ref = artifact.get("schema")
            if ref:
                check_ref(ref, f"registry:{artifact.get('name')}")


def _resolve_registry_path(
    path_template: str, repo_root: Path, artifact_name: Optional[str] = None
) -> Path:
    has_version_token = "{version}" in path_template
    if "{" not in path_template:
        return repo_root / path_template
    pattern = path_template
    for token in (
        "{config_version}",
        "{policy_version}",
        "{iso8601_timestamp}",
        "{version}",
    ):
        if token in pattern:
            pattern = pattern.replace(token, "*")
    matches = sorted(repo_root.glob(pattern))
    matches = [path for path in matches if path.exists()]
    if not matches:
        raise InputResolutionError(
            f"No files match registry path template: {path_template}"
        )
    if has_version_token:
        dated = []
        for path in matches:
            version_label = path.name if path.is_dir() else path.parent.name
            if _DATE_VERSION_RE.fullmatch(version_label):
                dated.append((version_label, path))
        if dated:
            resolved = sorted(dated, key=lambda item: item[0])[-1][1]
        else:
            resolved = matches[-1]
    else:
        resolved = matches[-1]
    if resolved.is_dir():
        if artifact_name:
            for suffix in (".parquet", ".csv", ".json", ".yaml", ".yml", ".jsonl"):
                candidate = resolved / f"{artifact_name}{suffix}"
                if candidate.exists():
                    return candidate
        parquet_files = sorted(resolved.glob("*.parquet"))
        if len(parquet_files) == 1:
            return parquet_files[0]
        files = sorted([path for path in resolved.iterdir() if path.is_file()])
        if len(files) == 1:
            return files[0]
        raise InputResolutionError(
            f"Registry path template resolved to directory with multiple files: {resolved}"
        )
    return resolved


def _resolve_param_files(
    registry: dict, repo_root: Path
) -> tuple[list[NamedPath], dict[str, str]]:
    mapping = {
        "hurdle_coefficients.yaml": "hurdle_coefficients",
        "nb_dispersion_coefficients.yaml": "nb_dispersion_coefficients",
        "crossborder_hyperparams.yaml": "crossborder_hyperparams",
        "ccy_smoothing_params.yaml": "ccy_smoothing_params",
        "policy.s3.rule_ladder.yaml": "policy.s3.rule_ladder.yaml",
        "s6_selection_policy.yaml": "s6_selection_policy",
        "s7_integerisation_policy.yaml": "s7_integerisation_policy",
        "policy.s3.base_weight.yaml": "policy.s3.base_weight.yaml",
        "policy.s3.thresholds.yaml": "policy.s3.thresholds.yaml",
    }
    params: list[NamedPath] = []
    resolved_map: dict[str, str] = {}
    for canonical_name, artifact_name in mapping.items():
        try:
            entry = find_registry_entry(registry, artifact_name)
        except ContractError:
            if canonical_name.startswith("policy.s3."):
                continue
            raise
        path_template = entry.get("path")
        if not path_template:
            raise ContractError(f"Registry entry missing path for {artifact_name}")
        resolved_path = _resolve_registry_path(path_template, repo_root, artifact_name)
        if not resolved_path.exists():
            if canonical_name.startswith("policy.s3."):
                continue
            raise InputResolutionError(f"Missing parameter file: {resolved_path}")
        params.append(NamedPath(name=canonical_name, path=resolved_path))
        resolved_map[canonical_name] = artifact_name
    return params, resolved_map


def find_registry_entry(registry: dict, name: str) -> dict:
    subsegments = registry.get("subsegments", [])
    for subsegment in subsegments:
        for artifact in subsegment.get("artifacts", []):
            if artifact.get("name") == name:
                return artifact
    raise ContractError(f"Registry entry not found: {name}")


def _load_seed(
    seed_override: Optional[int], repo_root: Path
) -> tuple[int, Optional[Path]]:
    if seed_override is not None:
        return seed_override, None
    seed_path = repo_root / "config" / "layer1" / "1A" / "rng" / "run_seed.yaml"
    if not seed_path.exists():
        raise InputResolutionError(f"Missing run seed config: {seed_path}")
    payload = _load_yaml(seed_path)
    if "seed" not in payload:
        raise InputResolutionError(f"run_seed.yaml missing 'seed' field: {seed_path}")
    return int(payload["seed"]), seed_path


def _resolve_git_bytes(repo_root: Path) -> bytes:
    env_hash = os.environ.get("ENGINE_GIT_COMMIT")
    if env_hash:
        return _git_hex_to_bytes(env_hash)
    git_file = repo_root / "ci" / "manifests" / "git_commit_hash.txt"
    if git_file.exists():
        return _git_hex_to_bytes(git_file.read_text(encoding="utf-8").strip())
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root)
        return _git_hex_to_bytes(output.decode("utf-8").strip())
    except Exception as exc:  # pragma: no cover - fallback when git unavailable
        raise InputResolutionError("Unable to resolve git commit hash.") from exc


def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


def _merchant_u64(merchant_id: int) -> int:
    payload = struct.pack("<Q", merchant_id)
    digest = __import__("hashlib").sha256(payload).digest()
    return int.from_bytes(digest[24:32], "little", signed=False)


def _validate_merchants(
    df: pl.DataFrame, iso_set: set[str], ingress_schema: dict
) -> pl.DataFrame:
    try:
        validate_dataframe(df.iter_rows(named=True), ingress_schema, "merchant_ids")
    except SchemaValidationError as exc:
        first = exc.errors[0] if exc.errors else {}
        raise EngineFailure(
            "F1",
            "ingress_schema_violation",
            "S0.1",
            "1A.s0_ingress",
            {
                "row_index": first.get("row_index"),
                "field": first.get("field"),
                "message": first.get("message"),
            },
        ) from exc
    bad_iso = (
        df.filter(~pl.col("home_country_iso").is_in(list(iso_set)))
        .select("home_country_iso")
        .unique()
    )
    if bad_iso.height > 0:
        raise EngineFailure(
            "F1",
            "home_iso_fk",
            "S0.1",
            "1A.s0_ingress",
            {"iso": bad_iso.to_series().to_list()},
        )
    return df


def _load_iso_set(path: Path) -> set[str]:
    df = pl.read_parquet(path)
    if "country_iso" not in df.columns:
        raise InputResolutionError("iso3166_canonical_2024 missing country_iso column.")
    return set(df["country_iso"].to_list())


def _load_gdp_map(path: Path) -> dict[str, float]:
    df = pl.read_parquet(path)
    required = {"country_iso", "gdp_pc_usd_2015", "observation_year"}
    if not required.issubset(set(df.columns)):
        raise InputResolutionError(
            "world_bank_gdp_per_capita missing required columns."
        )
    df = df.filter(pl.col("observation_year") == 2024)
    if df.is_empty():
        raise InputResolutionError("GDP per-capita missing observation_year=2024.")
    dupes = df.group_by("country_iso").len().filter(pl.col("len") > 1)
    if dupes.height > 0:
        raise InputResolutionError("GDP per-capita has duplicate country_iso rows.")
    return dict(zip(df["country_iso"].to_list(), df["gdp_pc_usd_2015"].to_list()))


def _load_gdp_bucket_map(path: Path) -> dict[str, int]:
    df = pl.read_parquet(path)
    if "country_iso" not in df.columns or "bucket_id" not in df.columns:
        raise InputResolutionError("gdp_bucket_map_2024 missing required columns.")
    dupes = df.group_by("country_iso").len().filter(pl.col("len") > 1)
    if dupes.height > 0:
        raise InputResolutionError(
            "gdp_bucket_map_2024 has duplicate country_iso rows."
        )
    return dict(zip(df["country_iso"].to_list(), df["bucket_id"].to_list()))


def _attach_gdp_features(
    df: pl.DataFrame,
    iso_set: set[str],
    gdp_map: dict[str, float],
    bucket_map: dict[str, int],
) -> pl.DataFrame:
    extra_gdp = sorted(set(gdp_map) - iso_set)
    if extra_gdp:
        raise EngineFailure(
            "F3",
            "gdp_iso_not_in_set",
            "S0.4",
            "1A.s0_gdp",
            {"iso": extra_gdp[:10], "count": len(extra_gdp)},
        )
    extra_bucket = sorted(set(bucket_map) - iso_set)
    if extra_bucket:
        raise EngineFailure(
            "F3",
            "bucket_iso_not_in_set",
            "S0.4",
            "1A.s0_gdp",
            {"iso": extra_bucket[:10], "count": len(extra_bucket)},
        )
    gdp_df = pl.DataFrame(
        {
            "home_country_iso": list(gdp_map.keys()),
            "gdp_per_capita": list(gdp_map.values()),
        }
    )
    bucket_df = pl.DataFrame(
        {
            "home_country_iso": list(bucket_map.keys()),
            "gdp_bucket_id": list(bucket_map.values()),
        }
    )
    merged = df.join(gdp_df, on="home_country_iso", how="left").join(
        bucket_df, on="home_country_iso", how="left"
    )
    missing_gdp = (
        merged.filter(pl.col("gdp_per_capita").is_null())
        .select("home_country_iso")
        .unique()
    )
    if missing_gdp.height > 0:
        raise EngineFailure(
            "F3",
            "gdp_missing",
            "S0.4",
            "1A.s0_gdp",
            {"iso": missing_gdp.to_series().to_list()},
        )
    nonpos_gdp = merged.filter(pl.col("gdp_per_capita") <= 0.0)
    if nonpos_gdp.height > 0:
        raise EngineFailure(
            "F3",
            "gdp_nonpositive",
            "S0.4",
            "1A.s0_gdp",
            {"count": nonpos_gdp.height},
        )
    missing_bucket = (
        merged.filter(pl.col("gdp_bucket_id").is_null())
        .select("home_country_iso")
        .unique()
    )
    if missing_bucket.height > 0:
        raise EngineFailure(
            "F3",
            "bucket_missing",
            "S0.4",
            "1A.s0_gdp",
            {"iso": missing_bucket.to_series().to_list()},
        )
    out_of_range = merged.filter(
        (pl.col("gdp_bucket_id") < 1) | (pl.col("gdp_bucket_id") > 5)
    )
    if out_of_range.height > 0:
        raise EngineFailure(
            "F3",
            "bucket_out_of_range",
            "S0.4",
            "1A.s0_gdp",
            {"count": out_of_range.height},
        )
    return merged.with_columns(
        [
            pl.col("gdp_bucket_id").cast(pl.Int8),
        ]
    )


def _attach_channel_and_u64(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        [
            pl.col("channel").replace_strict(CHANNEL_MAP).alias("channel_sym"),
            pl.col("merchant_id")
            .map_elements(_merchant_u64, return_dtype=pl.UInt64)
            .alias("merchant_u64"),
        ]
    )


def _build_crossborder_features(
    merchant_df: pl.DataFrame,
    parameter_hash: str,
    manifest_fingerprint: str,
) -> pl.DataFrame:
    bucket_col = pl.col("gdp_bucket_id")
    bucket_missing = bucket_col.is_null()
    bucket_value = pl.when(bucket_missing).then(1).otherwise(bucket_col).cast(pl.Int8)
    base_expr = (
        pl.when(bucket_value == 1)
        .then(0.06)
        .when(bucket_value == 2)
        .then(0.12)
        .when(bucket_value == 3)
        .then(0.20)
        .when(bucket_value == 4)
        .then(0.28)
        .when(bucket_value == 5)
        .then(0.35)
        .otherwise(0.06)
    )
    channel_expr = (
        pl.when(pl.col("channel") == "card_present")
        .then(-0.04)
        .when(pl.col("channel") == "card_not_present")
        .then(0.08)
        .otherwise(None)
    )
    mcc_col = pl.col("mcc").cast(pl.Int32)
    digital_band = (
        ((mcc_col >= 4810) & (mcc_col <= 4899))
        | ((mcc_col >= 5960) & (mcc_col <= 5969))
        | ((mcc_col >= 5815) & (mcc_col <= 5818))
    )
    travel_band = ((mcc_col >= 3000) & (mcc_col <= 3999)) | mcc_col.is_in(
        [4111, 4121, 4131, 4411, 4511, 4722, 4789, 7011]
    )
    retail_band = (
        ((mcc_col >= 5000) & (mcc_col <= 5999))
        | ((mcc_col >= 5300) & (mcc_col <= 5399))
        | ((mcc_col >= 5400) & (mcc_col <= 5599))
    )
    tilt_expr = (
        pl.when(digital_band)
        .then(0.10)
        .when(travel_band)
        .then(0.06)
        .when(retail_band)
        .then(0.03)
        .otherwise(0.0)
    )
    openness_expr = (
        (base_expr + channel_expr + tilt_expr).clip(0.0, 1.0).cast(pl.Float32)
    )
    source_expr = (
        pl.when(bucket_missing)
        .then(pl.lit("heuristic_v1:gdp_bucket_missing+channel+mcc"))
        .otherwise(pl.lit("heuristic_v1:gdp_bucket+channel+mcc"))
    )
    features_df = merchant_df.select(
        [
            pl.col("merchant_id").cast(pl.UInt64),
            openness_expr.alias("openness"),
            source_expr.alias("source"),
            pl.lit(parameter_hash).alias("parameter_hash"),
            pl.lit(manifest_fingerprint).alias("produced_by_fingerprint"),
        ]
    ).sort("merchant_id")
    if features_df.height != merchant_df.height:
        raise EngineFailure(
            "F3",
            "crossborder_row_mismatch",
            "S0.6",
            "1A.s0_crossborder_features",
            {"expected": merchant_df.height, "got": features_df.height},
        )
    if features_df["merchant_id"].n_unique() != features_df.height:
        raise EngineFailure(
            "F3",
            "crossborder_duplicate_merchant",
            "S0.6",
            "1A.s0_crossborder_features",
            {"count": features_df.height},
        )
    bad_openness = features_df.filter(
        pl.col("openness").is_null()
        | pl.col("openness").is_nan()
        | pl.col("openness").is_infinite()
        | (pl.col("openness") < 0.0)
        | (pl.col("openness") > 1.0)
    )
    if bad_openness.height > 0:
        raise EngineFailure(
            "F3",
            "crossborder_openness_invalid",
            "S0.6",
            "1A.s0_crossborder_features",
            {"count": bad_openness.height},
        )
    return features_df


def _load_hurdle_coefficients(path: Path) -> tuple[dict[str, list], list[float]]:
    payload = _load_yaml(path)
    dict_mcc = payload.get("dict_mcc")
    dict_ch = payload.get("dict_ch")
    dict_dev5 = payload.get("dict_dev5")
    beta = payload.get("beta")
    if (
        not isinstance(dict_mcc, list)
        or not isinstance(dict_ch, list)
        or not isinstance(dict_dev5, list)
    ):
        raise EngineFailure(
            "F3",
            "design_dict_missing",
            "S0.5",
            "1A.s0_design",
            {"path": path.as_posix()},
        )
    if dict_ch != ["CP", "CNP"]:
        raise EngineFailure(
            "F3",
            "design_channel_mismatch",
            "S0.5",
            "1A.s0_design",
            {"dict_ch": dict_ch},
        )
    if dict_dev5 != [1, 2, 3, 4, 5]:
        raise EngineFailure(
            "F3",
            "design_bucket_mismatch",
            "S0.5",
            "1A.s0_design",
            {"dict_dev5": dict_dev5},
        )
    if not isinstance(beta, list):
        raise EngineFailure(
            "F3",
            "design_beta_missing",
            "S0.5",
            "1A.s0_design",
            {"path": path.as_posix()},
        )
    expected = 1 + len(dict_mcc) + len(dict_ch) + len(dict_dev5)
    if len(beta) != expected:
        raise EngineFailure(
            "F3",
            "design_shape_mismatch",
            "S0.5",
            "1A.s0_design",
            {"expected": expected, "got": len(beta)},
        )
    return (
        {
            "dict_mcc": [int(value) for value in dict_mcc],
            "dict_ch": [str(value) for value in dict_ch],
            "dict_dev5": [int(value) for value in dict_dev5],
        },
        [float(value) for value in beta],
    )


def _load_nb_dispersion_coefficients(path: Path) -> tuple[dict[str, list], list[float]]:
    payload = _load_yaml(path)
    dict_mcc = payload.get("dict_mcc")
    dict_ch = payload.get("dict_ch")
    beta_phi = payload.get("beta_phi")
    if not isinstance(dict_mcc, list) or not isinstance(dict_ch, list):
        raise EngineFailure(
            "F3",
            "design_dict_missing",
            "S0.5",
            "1A.s0_design",
            {"path": path.as_posix()},
        )
    if dict_ch != ["CP", "CNP"]:
        raise EngineFailure(
            "F3",
            "design_channel_mismatch",
            "S0.5",
            "1A.s0_design",
            {"dict_ch": dict_ch},
        )
    if not isinstance(beta_phi, list):
        raise EngineFailure(
            "F3",
            "design_beta_missing",
            "S0.5",
            "1A.s0_design",
            {"path": path.as_posix()},
        )
    expected = 1 + len(dict_mcc) + len(dict_ch) + 1
    if len(beta_phi) != expected:
        raise EngineFailure(
            "F3",
            "design_shape_mismatch",
            "S0.5",
            "1A.s0_design",
            {"expected": expected, "got": len(beta_phi)},
        )
    return (
        {
            "dict_mcc": [int(value) for value in dict_mcc],
            "dict_ch": [str(value) for value in dict_ch],
        },
        [float(value) for value in beta_phi],
    )


def _build_output_paths(
    run_paths: RunPaths,
    dictionary: dict,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
    utc_day: Optional[str] = None,
) -> S0Outputs:
    def dataset_path(dataset_id: str) -> Path:
        entry = find_dataset_entry(dictionary, dataset_id).entry
        path = entry["path"]
        for key, value in {
            "seed": str(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id,
        }.items():
            path = path.replace(f"{{{key}}}", value)
        return run_paths.run_root / path

    return S0Outputs(
        sealed_inputs_path=dataset_path("sealed_inputs_1A"),
        gate_receipt_path=dataset_path("s0_gate_receipt_1A"),
        rng_anchor_path=dataset_path("rng_event_anchor").with_name("part-00000.jsonl"),
        rng_audit_path=dataset_path("rng_audit_log"),
        rng_trace_path=dataset_path("rng_trace_log"),
        hurdle_design_root=dataset_path("hurdle_design_matrix"),
        crossborder_features_root=dataset_path("crossborder_features"),
        crossborder_flags_root=dataset_path("crossborder_eligibility_flags"),
        hurdle_pi_probs_root=dataset_path("hurdle_pi_probs"),
        validation_bundle_root=dataset_path("validation_bundle_1A"),
        segment_state_runs_path=(
            _segment_state_runs_path(run_paths, dictionary, utc_day)
            if utc_day
            else None
        ),
    )


def _write_parquet_partition(
    df: pl.DataFrame, target_root: Path, tmp_root: Path, dataset_id: str
) -> None:
    tmp_dir = tmp_root / f"{dataset_id}_{uuid.uuid4().hex}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / "part-00000.parquet"
    df.write_parquet(tmp_file)
    target_root.parent.mkdir(parents=True, exist_ok=True)
    if target_root.exists():
        shutil.rmtree(target_root)
    tmp_dir.replace(target_root)


def _require_param_hash_column(
    df: pl.DataFrame, parameter_hash: str, dataset_id: str
) -> None:
    if "parameter_hash" not in df.columns:
        raise EngineFailure(
            "F5",
            "partition_mismatch",
            "S0.10",
            "1A.s0_validation",
            {
                "dataset_id": dataset_id,
                "path_key": parameter_hash,
                "embedded_key": None,
            },
        )
    mismatch = df.filter(pl.col("parameter_hash") != parameter_hash)
    if mismatch.height > 0:
        raise EngineFailure(
            "F5",
            "partition_mismatch",
            "S0.10",
            "1A.s0_validation",
            {
                "dataset_id": dataset_id,
                "path_key": parameter_hash,
                "embedded_key": "mismatch",
            },
        )


def _segment_state_runs_path(
    run_paths: RunPaths, dictionary: dict, utc_day: str
) -> Path:
    entry = find_dataset_entry(dictionary, "segment_state_runs").entry
    path_template = entry["path"]
    path = path_template.replace("{utc_day}", utc_day)
    return run_paths.run_root / path


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        handle.write("\n")


def _neumaier_sum(values: tuple[float, ...]) -> float:
    total = 0.0
    c = 0.0
    for value in values:
        t = total + value
        if abs(total) >= abs(value):
            c += (total - t) + value
        else:
            c += (value - t) + total
        total = t
    return total + c


def _logistic(eta: float) -> float:
    if eta >= 0.0:
        z = math.exp(-eta)
        return 1.0 / (1.0 + z)
    z = math.exp(eta)
    return z / (1.0 + z)


def _run_id_in_use(
    runs_root: Path,
    dictionary: dict,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
) -> bool:
    run_paths = RunPaths(runs_root, run_id)
    outputs = _build_output_paths(
        run_paths,
        dictionary,
        seed=seed,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id=run_id,
    )
    log_dirs = {
        outputs.rng_audit_path.parent,
        outputs.rng_trace_path.parent,
        outputs.rng_anchor_path.parent,
    }
    if any(path.exists() for path in log_dirs):
        return True
    return run_paths.run_root.exists()


def run_s0(
    config: EngineConfig,
    seed_override: Optional[int] = None,
    merchant_ids_version: Optional[str] = None,
    emit_hurdle_pi_probs: bool = True,
) -> S0RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s0_foundations.l2.runner")
    timer = _StepTimer(logger)
    timer.info("S0: run initialised")
    logger.info(
        "Contracts layout=%s root=%s", config.contracts_layout, config.contracts_root
    )

    seed: Optional[int] = None
    seed_path: Optional[Path] = None
    parameter_hash: Optional[str] = None
    parameter_hash_bytes: Optional[bytes] = None
    manifest_fingerprint: Optional[str] = None
    manifest_bytes: Optional[bytes] = None
    run_id: Optional[str] = None
    run_paths: Optional[RunPaths] = None
    outputs: Optional[S0Outputs] = None
    opened_paths: dict[Path, FileDigest] = {}
    opened_artifacts: list[NamedDigest] = []
    param_digests: list[NamedDigest] = []
    attestation_payload: Optional[dict] = None
    attestation_bytes: Optional[bytes] = None
    attestation_digest_hex: Optional[str] = None

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        if outputs is None or outputs.segment_state_runs_path is None:
            return
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S0",
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id,
            "status": status,
            "ts_utc": utc_now_rfc3339_micro(),
        }
        if detail:
            payload["detail"] = detail
        _append_jsonl(outputs.segment_state_runs_path, payload)

    def _record_failure(exc: Exception, failure: EngineFailure) -> None:
        if (
            seed is None
            or parameter_hash is None
            or manifest_fingerprint is None
            or run_id is None
            or run_paths is None
        ):
            logger.error("Failure before run_id; skipping failure record: %s", exc)
            return
        payload = {
            "failure_class": failure.failure_class,
            "failure_code": failure.failure_code,
            "state": failure.state,
            "module": failure.module,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "seed": seed,
            "run_id": run_id,
            "ts_utc": utc_now_ns(),
            "detail": failure.detail,
        }
        if failure.dataset_id:
            payload["dataset_id"] = failure.dataset_id
        if failure.merchant_id is not None:
            payload["merchant_id"] = str(failure.merchant_id)
        failure_root = (
            run_paths.run_root
            / "data/layer1/1A/validation/failures"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / f"seed={seed}"
            / f"run_id={run_id}"
        )
        write_failure_record(failure_root, payload)
        _emit_state_run("failed")

    try:
        source = ContractSource(
            root=config.contracts_root, layout=config.contracts_layout
        )
        dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
        registry_path, registry = load_artefact_registry(source, "1A")
        _audit_schema_authority(dictionary, registry)
        ingress_schema_path, ingress_schema = load_schema_pack(
            source, "1A", "ingress.layer1"
        )
        schema_1a_path, _schema_1a = load_schema_pack(source, "1A", "1A")
        schema_layer1_path, _schema_layer1 = load_schema_pack(source, "1A", "layer1")

        seed, seed_path = _load_seed(seed_override, config.repo_root)
        timer.info(f"S0: resolved seed={seed} (path={seed_path or 'cli_override'})")
        ref_assets = resolve_reference_inputs(
            dictionary,
            run_paths=RunPaths(config.runs_root, run_id="pre-run"),
            external_roots=config.external_roots,
            merchant_ids_version=merchant_ids_version,
            allow_run_local=False,
        )
        timer.info(f"S0: resolved {len(ref_assets)} reference inputs")

        iso_path = next(
            asset.path
            for asset in ref_assets
            if asset.asset_id == "iso3166_canonical_2024"
        )
        gdp_path = next(
            asset.path
            for asset in ref_assets
            if asset.asset_id == "world_bank_gdp_per_capita_20250415"
        )
        bucket_path = next(
            asset.path
            for asset in ref_assets
            if asset.asset_id == "gdp_bucket_map_2024"
        )

        iso_set = _load_iso_set(iso_path)
        gdp_map = _load_gdp_map(gdp_path)
        gdp_bucket_map = _load_gdp_bucket_map(bucket_path)

        merchant_asset = next(
            asset
            for asset in ref_assets
            if asset.asset_id == "transaction_schema_merchant_ids"
        )
        merchant_df = (
            pl.read_parquet(merchant_asset.path)
            if merchant_asset.path.suffix == ".parquet"
            else pl.read_csv(merchant_asset.path)
        )
        merchant_df = _validate_merchants(merchant_df, iso_set, ingress_schema)
        merchant_df = _attach_channel_and_u64(merchant_df)
        merchant_df = _attach_gdp_features(
            merchant_df, iso_set, gdp_map, gdp_bucket_map
        )
        timer.info(f"S0: loaded merchant universe rows={merchant_df.height}")

        param_files, param_name_map = _resolve_param_files(registry, config.repo_root)
        timer.info(f"S0: resolved {len(param_files)} parameter files")
        parameter_hash, parameter_hash_bytes, param_digests = compute_parameter_hash(
            param_files
        )
        timer.info(f"S0: computed parameter_hash={parameter_hash}")
        param_path_map = {param.name: param.path for param in param_files}

        numeric_policy_entry = find_registry_entry(registry, "numeric_policy_profile")
        numeric_policy_path = _resolve_registry_path(
            numeric_policy_entry["path"], config.repo_root, "numeric_policy_profile"
        )
        math_profile_entry = find_registry_entry(registry, "math_profile_manifest")
        math_profile_path = _resolve_registry_path(
            math_profile_entry["path"], config.repo_root, "math_profile_manifest"
        )
        attestation_payload, _digests = run_numeric_self_tests(
            numeric_policy_path, math_profile_path, "1A.s0_numeric_policy"
        )
        attestation_bytes = json.dumps(
            attestation_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        attestation_digest_hex = hashlib.sha256(attestation_bytes).hexdigest()
        attestation_digest = FileDigest(
            path=Path("numeric_policy_attest.json"),
            size_bytes=len(attestation_bytes),
            mtime_ns=0,
            sha256_hex=attestation_digest_hex,
        )

        opened_path_set: set[Path] = set()
        registry_names = {asset.asset_id for asset in ref_assets}
        registry_names.update(param_name_map.values())
        registry_names.update(
            {
                "numeric_policy_profile",
                "math_profile_manifest",
                "validation_policy",
                "settlement_shares_2024Q4",
                "ccy_country_shares_2024Q4",
                "ccy_smoothing_params",
                "license_map",
                "iso_legal_tender_2024",
            }
        )
        if seed_path is not None:
            registry_names.add("run_seed")
        registry_entries = artifact_dependency_closure(registry, registry_names)
        registry_entry_map = {entry.name: entry.entry for entry in registry_entries}
        for entry in registry_entries:
            path_template = entry.entry.get("path")
            if not path_template:
                continue
            opened_path_set.add(
                _resolve_registry_path(path_template, config.repo_root, entry.name)
            )

        opened_path_set.update(asset.path for asset in ref_assets)
        opened_path_set.update(param.path for param in param_files)
        opened_path_set.update(
            {
                dictionary_path,
                registry_path,
                ingress_schema_path,
                schema_1a_path,
                schema_layer1_path,
            }
        )
        if seed_path is not None:
            opened_path_set.add(seed_path)

        for path in sorted(opened_path_set):
            digest = sha256_file(path)
            opened_paths[path] = digest
            opened_artifacts.append(NamedDigest(name=path.name, digest=digest))

        opened_artifacts.append(
            NamedDigest(name="numeric_policy_attest.json", digest=attestation_digest)
        )

        git_bytes = _resolve_git_bytes(config.repo_root)
        manifest_fingerprint, manifest_bytes = compute_manifest_fingerprint(
            opened_artifacts, git_bytes, parameter_hash_bytes
        )
        timer.info(f"S0: computed manifest_fingerprint={manifest_fingerprint}")

        t_ns = time.time_ns()
        for _ in range(2**16):
            candidate_run_id, _ = compute_run_id(manifest_bytes, seed, t_ns)
            if not _run_id_in_use(
                config.runs_root,
                dictionary,
                seed=seed,
                parameter_hash=parameter_hash,
                manifest_fingerprint=manifest_fingerprint,
                run_id=candidate_run_id,
            ):
                run_id = candidate_run_id
                break
            t_ns += 1
        if run_id is None:
            raise EngineFailure(
                "F2",
                "runid_collision_exhausted",
                "S0.2.4",
                "1A.s0_run_id",
                {"detail": "run_id_collision_exhausted"},
            )
        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        timer.info(f"S0: run log initialized at {run_log_path}")

        utc_day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        outputs = _build_output_paths(
            run_paths,
            dictionary,
            seed=seed,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            run_id=run_id,
            utc_day=utc_day,
        )
        _emit_state_run("started")
        timer.info(f"S0: output root ready at {run_paths.run_root}")

        write_run_receipt(
            run_paths.run_root / "run_receipt.json",
            run_id=run_id,
            seed=seed,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            contracts_layout=config.contracts_layout,
            contracts_root=config.contracts_root,
            runs_root=config.runs_root,
            external_roots=config.external_roots,
            created_utc=utc_now_rfc3339_micro(),
        )

        sealed_assets: list[InputAsset] = []
        sealed_assets.extend(ref_assets)
        for param in param_files:
            registry_name = param_name_map.get(param.name)
            schema_ref = "unknown"
            version_tag = "unknown"
            if registry_name and registry_name in registry_entry_map:
                entry = registry_entry_map[registry_name]
                schema_ref = entry.get("schema") or "unknown"
                version_tag = str(entry.get("version") or "unknown")
            sealed_assets.append(
                InputAsset(
                    asset_id=param.name,
                    path=param.path,
                    schema_ref=schema_ref,
                    version_tag=version_tag,
                    partition={},
                )
            )
        ref_asset_ids = {asset.asset_id for asset in ref_assets}
        param_registry_names = set(param_name_map.values())
        for entry in registry_entries:
            if entry.name in ref_asset_ids or entry.name in param_registry_names:
                continue
            path_template = entry.entry.get("path")
            if not path_template:
                continue
            resolved_path = _resolve_registry_path(path_template, config.repo_root)
            sealed_assets.append(
                InputAsset(
                    asset_id=entry.name,
                    path=resolved_path,
                    schema_ref=entry.entry.get("schema") or "unknown",
                    version_tag=str(entry.entry.get("version") or "unknown"),
                    partition={},
                )
            )
        for contract_path in (
            dictionary_path,
            registry_path,
            ingress_schema_path,
            schema_1a_path,
            schema_layer1_path,
        ):
            sealed_assets.append(
                InputAsset(
                    asset_id=contract_path.name,
                    path=contract_path,
                    schema_ref="unknown",
                    version_tag="unknown",
                    partition={},
                )
            )

        unique_assets: dict[tuple[str, Path], InputAsset] = {}
        for asset in sealed_assets:
            unique_assets[(asset.asset_id, asset.path)] = asset
        sealed_assets = list(unique_assets.values())

        write_sealed_inputs(outputs.sealed_inputs_path, sealed_assets, opened_paths)
        write_gate_receipt(
            outputs.gate_receipt_path,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            run_id=run_id,
            sealed_assets=sealed_assets,
        )

        anchor_event = build_anchor_event(
            seed, parameter_hash, manifest_fingerprint, run_id
        )
        audit_entry = {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id,
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "algorithm": "philox2x64-10",
            "build_commit": git_bytes.hex(),
            "code_digest": None,
            "hostname": None,
            "platform": None,
            "notes": None,
        }
        write_rng_logs(
            outputs.rng_anchor_path,
            outputs.rng_audit_path,
            outputs.rng_trace_path,
            anchor_event=anchor_event,
            audit_entry=audit_entry,
        )

        coeff_meta, beta = _load_hurdle_coefficients(
            param_path_map["hurdle_coefficients.yaml"]
        )
        nb_meta, _nb_beta = _load_nb_dispersion_coefficients(
            param_path_map["nb_dispersion_coefficients.yaml"]
        )
        if coeff_meta["dict_mcc"] != nb_meta["dict_mcc"]:
            raise EngineFailure(
                "F3",
                "design_mcc_mismatch",
                "S0.5",
                "1A.s0_design",
                {"detail": "dict_mcc mismatch between hurdle and nb dispersion"},
            )
        if coeff_meta["dict_ch"] != nb_meta["dict_ch"]:
            raise EngineFailure(
                "F3",
                "design_channel_mismatch",
                "S0.5",
                "1A.s0_design",
                {"detail": "dict_ch mismatch between hurdle and nb dispersion"},
            )

        missing_mcc = (
            merchant_df.filter(~pl.col("mcc").is_in(coeff_meta["dict_mcc"]))
            .select("mcc")
            .unique()
        )
        if missing_mcc.height > 0:
            raise EngineFailure(
                "F3",
                "design_unknown_mcc",
                "S0.5",
                "1A.s0_design",
                {"mcc": missing_mcc.to_series().to_list()},
            )
        bad_channel = (
            merchant_df.filter(~pl.col("channel_sym").is_in(coeff_meta["dict_ch"]))
            .select("channel_sym")
            .unique()
        )
        if bad_channel.height > 0:
            raise EngineFailure(
                "F3",
                "design_unknown_channel",
                "S0.5",
                "1A.s0_design",
                {"channel": bad_channel.to_series().to_list()},
            )

        design_df = merchant_df.select(
            [
                pl.col("merchant_id"),
                pl.col("mcc").cast(pl.Int32),
                pl.col("channel"),
                pl.col("gdp_bucket_id").cast(pl.Int8),
                pl.lit(1.0, dtype=pl.Float32).alias("intercept"),
            ]
        )
        _write_parquet_partition(
            design_df,
            outputs.hurdle_design_root,
            run_paths.tmp_root,
            "hurdle_design_matrix",
        )
        timer.info("S0.5: hurdle design matrix emitted")

        rule_set_id, default_allow, rules = load_eligibility_rules(
            param_path_map["crossborder_hyperparams.yaml"].as_posix(), iso_set
        )
        eligibility_df = build_eligibility_frame(
            merchant_df,
            rules,
            rule_set_id,
            default_allow,
            parameter_hash,
            manifest_fingerprint,
            logger,
        )
        _require_param_hash_column(
            eligibility_df, parameter_hash, "crossborder_eligibility_flags"
        )
        _write_parquet_partition(
            eligibility_df,
            outputs.crossborder_flags_root,
            run_paths.tmp_root,
            "crossborder_eligibility_flags",
        )
        timer.info("S0.6: crossborder eligibility flags emitted")

        model_schema = _schema_section(_schema_1a, "model")
        features_df = _build_crossborder_features(
            merchant_df, parameter_hash, manifest_fingerprint
        )
        validate_dataframe(
            features_df.iter_rows(named=True),
            model_schema,
            "crossborder_features",
        )
        _require_param_hash_column(features_df, parameter_hash, "crossborder_features")
        _write_parquet_partition(
            features_df,
            outputs.crossborder_features_root,
            run_paths.tmp_root,
            "crossborder_features",
        )
        timer.info(
            f"S0.6: crossborder features emitted (openness heuristic_v1; merchants={features_df.height})"
        )

        if emit_hurdle_pi_probs:
            dict_mcc = coeff_meta["dict_mcc"]
            dict_ch = coeff_meta["dict_ch"]
            dict_dev5 = coeff_meta["dict_dev5"]
            offset_mcc = 1
            offset_ch = offset_mcc + len(dict_mcc)
            offset_dev = offset_ch + len(dict_ch)
            beta_intercept = beta[0]
            beta_mcc = {
                value: beta[offset_mcc + idx] for idx, value in enumerate(dict_mcc)
            }
            beta_ch = {
                value: beta[offset_ch + idx] for idx, value in enumerate(dict_ch)
            }
            beta_dev = {
                value: beta[offset_dev + idx] for idx, value in enumerate(dict_dev5)
            }
            rows = []
            total = merchant_df.height
            progress_every = max(1, min(10_000, total // 10 if total else 1))
            start_time = time.monotonic()
            for idx, row in enumerate(
                merchant_df.select(
                    ["merchant_id", "mcc", "channel_sym", "gdp_bucket_id"]
                ).iter_rows(),
                start=1,
            ):
                merchant_id, mcc, channel_sym, bucket_id = row
                if int(mcc) not in beta_mcc:
                    raise EngineFailure(
                        "F3",
                        "design_unknown_mcc",
                        "S0.7",
                        "1A.s0_hurdle_pi",
                        {"mcc": int(mcc)},
                        merchant_id=str(merchant_id),
                    )
                if str(channel_sym) not in beta_ch:
                    raise EngineFailure(
                        "F3",
                        "design_unknown_channel",
                        "S0.7",
                        "1A.s0_hurdle_pi",
                        {"channel": str(channel_sym)},
                        merchant_id=str(merchant_id),
                    )
                if int(bucket_id) not in beta_dev:
                    raise EngineFailure(
                        "F3",
                        "design_bucket_mismatch",
                        "S0.7",
                        "1A.s0_hurdle_pi",
                        {"bucket_id": int(bucket_id)},
                        merchant_id=str(merchant_id),
                    )
                eta = _neumaier_sum(
                    (
                        beta_intercept,
                        beta_mcc[int(mcc)],
                        beta_ch[str(channel_sym)],
                        beta_dev[int(bucket_id)],
                    )
                )
                if not math.isfinite(eta):
                    raise EngineFailure(
                        "F3",
                        "hurdle_nonfinite",
                        "S0.7",
                        "1A.s0_hurdle_pi",
                        {"field": "logit", "value": str(eta)},
                        merchant_id=str(merchant_id),
                    )
                pi = _logistic(eta)
                if not math.isfinite(pi):
                    raise EngineFailure(
                        "F3",
                        "hurdle_nonfinite",
                        "S0.7",
                        "1A.s0_hurdle_pi",
                        {"field": "pi", "value": str(pi)},
                        merchant_id=str(merchant_id),
                    )
                rows.append(
                    {
                        "parameter_hash": parameter_hash,
                        "produced_by_fingerprint": manifest_fingerprint,
                        "merchant_id": int(merchant_id),
                        "logit": float(np.float32(eta)),
                        "pi": float(np.float32(pi)),
                    }
                )
                if idx % progress_every == 0 or idx == total:
                    elapsed = time.monotonic() - start_time
                    rate = (idx / elapsed) if elapsed > 0.0 else 0.0
                    eta = ((total - idx) / rate) if rate > 0.0 else 0.0
                    logger.info(
                        "S0.7: emitted hurdle_pi_probs %d/%d (elapsed=%.2fs, rate=%.1f/s, eta=%.2fs)",
                        idx,
                        total,
                        elapsed,
                        rate,
                        eta,
                    )
            pi_schema = {
                "parameter_hash": pl.Utf8,
                "produced_by_fingerprint": pl.Utf8,
                "merchant_id": pl.UInt64,
                "logit": pl.Float32,
                "pi": pl.Float32,
            }
            pi_df = pl.DataFrame(rows, schema=pi_schema)
            _require_param_hash_column(pi_df, parameter_hash, "hurdle_pi_probs")
            _write_parquet_partition(
                pi_df,
                outputs.hurdle_pi_probs_root,
                run_paths.tmp_root,
                "hurdle_pi_probs",
            )
            timer.info("S0.7: hurdle_pi_probs emitted")

        param_digest_log = build_param_digest_log(
            [(item.name, item.digest) for item in param_digests]
        )
        parameter_hash_resolved = {
            "parameter_hash": parameter_hash,
            "filenames_sorted": sorted([item.name for item in param_digests]),
            "artifact_count": len(param_digests),
        }
        manifest_fingerprint_resolved = {
            "manifest_fingerprint": manifest_fingerprint,
            "artifact_count": len(opened_artifacts),
            "git_commit_hex": git_bytes.hex(),
            "parameter_hash": parameter_hash,
        }
        fingerprint_artifacts = []
        for path, digest in opened_paths.items():
            fingerprint_artifacts.append(
                {
                    "path": path.as_posix(),
                    "sha256": digest.sha256_hex,
                    "size_bytes": digest.size_bytes,
                }
            )
        fingerprint_artifacts.append(
            {
                "path": "numeric_policy_attest.json",
                "sha256": attestation_digest_hex,
                "size_bytes": len(attestation_bytes or b""),
            }
        )
        fingerprint_artifacts.sort(key=lambda item: item["path"])

        flags = attestation_payload.get("flags", {}) if attestation_payload else {}
        compiler_flags = {
            "fma": flags.get("fma") not in ("off", False, None),
            "ftz": flags.get("ftz_daz") not in ("off", False, None),
            "rounding": flags.get("rounding") or "RNE",
            "fast_math": False,
            "blas": "none",
        }
        manifest_payload = {
            "version": "1A.validation.v1",
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "git_commit_hex": git_bytes.hex(),
            "artifact_count": len(opened_artifacts),
            "math_profile_id": attestation_payload.get("math_profile_id")
            if attestation_payload
            else "",
            "compiler_flags": compiler_flags,
            "created_utc_ns": utc_now_ns(),
        }
        run_environ = {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "build_commit": git_bytes.hex(),
        }
        index_entries = [
            {"artifact_id": "MANIFEST", "kind": "summary", "path": "MANIFEST.json"},
            {
                "artifact_id": "parameter_hash_resolved",
                "kind": "table",
                "path": "parameter_hash_resolved.json",
            },
            {
                "artifact_id": "manifest_fingerprint_resolved",
                "kind": "table",
                "path": "manifest_fingerprint_resolved.json",
            },
            {
                "artifact_id": "param_digest_log",
                "kind": "table",
                "path": "param_digest_log.jsonl",
            },
            {
                "artifact_id": "fingerprint_artifacts",
                "kind": "table",
                "path": "fingerprint_artifacts.jsonl",
            },
            {
                "artifact_id": "numeric_policy_attest",
                "kind": "summary",
                "path": "numeric_policy_attest.json",
            },
            {
                "artifact_id": "run_environ",
                "kind": "summary",
                "path": "run_environ.json",
            },
            {"artifact_id": "index", "kind": "summary", "path": "index.json"},
        ]
        write_validation_bundle(
            outputs.validation_bundle_root,
            manifest_payload,
            parameter_hash_resolved,
            manifest_fingerprint_resolved,
            param_digest_log,
            fingerprint_artifacts,
            attestation_payload,
            run_environ,
            index_entries,
        )
        timer.info("S0.10: validation bundle emitted")

        context = RunContext(
            merchants=MerchantUniverse(frame=merchant_df, iso_set=iso_set),
            gdp_per_capita=gdp_map,
            gdp_bucket_map=gdp_bucket_map,
            channel_map=CHANNEL_MAP,
        )
        _emit_state_run("completed")
        timer.info(f"S0: foundations complete (run_id={run_id})")
        return S0RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            outputs=outputs,
            context=context,
        )
    except EngineFailure as exc:
        _record_failure(exc, exc)
        raise
    except (ContractError, InputResolutionError, HashingError) as exc:
        failure = EngineFailure(
            "F2",
            "input_resolution_error",
            "S0",
            "1A.s0",
            {"message": str(exc)},
        )
        _record_failure(exc, failure)
        raise
