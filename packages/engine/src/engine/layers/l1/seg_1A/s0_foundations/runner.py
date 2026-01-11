"""S0 foundations runner for Segment 1A."""

from __future__ import annotations

import os
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
from engine.core.errors import ContractError, InputResolutionError
from engine.core.hashing import FileDigest, sha256_file
from engine.core.logging import get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
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
from engine.layers.l1.seg_1A.s0_foundations.outputs import (
    S0Outputs,
    write_gate_receipt,
    write_rng_logs,
    write_sealed_inputs,
)
from engine.layers.l1.seg_1A.s0_foundations.rng import build_anchor_event


CHANNEL_MAP = {"card_present": "CP", "card_not_present": "CNP"}


@dataclass(frozen=True)
class S0RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    outputs: S0Outputs
    context: RunContext


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def _resolve_registry_path(path_template: str, repo_root: Path) -> Path:
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
    matches = [path for path in matches if path.is_file()]
    if not matches:
        raise InputResolutionError(
            f"No files match registry path template: {path_template}"
        )
    return matches[-1]


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
        resolved_path = _resolve_registry_path(path_template, repo_root)
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
    validate_dataframe(df.iter_rows(named=True), ingress_schema, "merchant_ids")
    bad_iso = (
        df.filter(~pl.col("home_country_iso").is_in(list(iso_set)))
        .select("home_country_iso")
        .unique()
    )
    if bad_iso.height > 0:
        raise InputResolutionError(
            f"Invalid home_country_iso values: {bad_iso.to_series().to_list()}"
        )
    return df


def _load_iso_set(path: Path) -> set[str]:
    df = pl.read_parquet(path)
    if "country_iso" not in df.columns:
        raise InputResolutionError("iso3166_canonical_2024 missing country_iso column.")
    return set(df["country_iso"].to_list())


def _load_gdp_map(path: Path) -> dict[str, float]:
    df = pl.read_parquet(path)
    if "country_iso" not in df.columns or "gdp_pc_usd_2015" not in df.columns:
        raise InputResolutionError(
            "world_bank_gdp_per_capita missing required columns."
        )
    df = df.sort("observation_year").group_by("country_iso").tail(1)
    return dict(zip(df["country_iso"].to_list(), df["gdp_pc_usd_2015"].to_list()))


def _load_gdp_bucket_map(path: Path) -> dict[str, int]:
    df = pl.read_parquet(path)
    if "country_iso" not in df.columns or "bucket_id" not in df.columns:
        raise InputResolutionError("gdp_bucket_map_2024 missing required columns.")
    return dict(zip(df["country_iso"].to_list(), df["bucket_id"].to_list()))


def _attach_channel_and_u64(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        [
            pl.col("channel")
            .map_elements(lambda value: CHANNEL_MAP[value], return_dtype=pl.Utf8)
            .alias("channel_sym"),
            pl.col("merchant_id")
            .map_elements(_merchant_u64, return_dtype=pl.UInt64)
            .alias("merchant_u64"),
        ]
    )


def _build_output_paths(
    run_paths: RunPaths,
    dictionary: dict,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
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
    )


def _run_id_in_use(
    repo_root: Path,
    dictionary: dict,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
) -> bool:
    run_paths = RunPaths(repo_root, run_id)
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
) -> S0RunResult:
    logger = get_logger("engine.s0")
    logger.info(
        "Contracts layout=%s root=%s", config.contracts_layout, config.contracts_root
    )
    source = ContractSource(root=config.contracts_root, layout=config.contracts_layout)
    dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
    registry_path, registry = load_artefact_registry(source, "1A")
    _audit_schema_authority(dictionary, registry)
    ingress_schema_path, ingress_schema = load_schema_pack(
        source, "1A", "ingress.layer1"
    )
    schema_1a_path, _schema_1a = load_schema_pack(source, "1A", "1A")
    schema_layer1_path, _schema_layer1 = load_schema_pack(source, "1A", "layer1")

    seed, seed_path = _load_seed(seed_override, config.repo_root)
    logger.info("Resolved seed=%s (path=%s)", seed, seed_path or "cli_override")
    ref_assets = resolve_reference_inputs(
        dictionary,
        run_paths=RunPaths(config.repo_root, run_id="pre-run"),
        external_roots=config.external_roots,
        merchant_ids_version=merchant_ids_version,
        allow_run_local=False,
    )
    logger.info("Resolved %d reference inputs.", len(ref_assets))

    iso_path = next(
        asset.path for asset in ref_assets if asset.asset_id == "iso3166_canonical_2024"
    )
    gdp_path = next(
        asset.path
        for asset in ref_assets
        if asset.asset_id == "world_bank_gdp_per_capita_20250415"
    )
    bucket_path = next(
        asset.path for asset in ref_assets if asset.asset_id == "gdp_bucket_map_2024"
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
    logger.info("Loaded merchant universe rows=%d", merchant_df.height)

    param_files, param_name_map = _resolve_param_files(registry, config.repo_root)
    logger.info("Resolved %d parameter files.", len(param_files))
    parameter_hash, parameter_hash_bytes, _param_digests = compute_parameter_hash(
        param_files
    )
    logger.info("Computed parameter_hash %s", parameter_hash)

    opened_artifacts: list[NamedDigest] = []
    opened_paths: dict[Path, FileDigest] = {}
    opened_path_set: set[Path] = set()

    registry_names = {asset.asset_id for asset in ref_assets}
    registry_names.update(param_name_map.values())
    if seed_path is not None:
        registry_names.add("run_seed")
    registry_entries = artifact_dependency_closure(registry, registry_names)
    registry_entry_map = {entry.name: entry.entry for entry in registry_entries}
    for entry in registry_entries:
        path_template = entry.entry.get("path")
        if not path_template:
            continue
        opened_path_set.add(_resolve_registry_path(path_template, config.repo_root))

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

    git_bytes = _resolve_git_bytes(config.repo_root)
    manifest_fingerprint, manifest_bytes = compute_manifest_fingerprint(
        opened_artifacts, git_bytes, parameter_hash_bytes
    )
    logger.info("Computed manifest_fingerprint %s", manifest_fingerprint)

    t_ns = time.time_ns()
    run_id = None
    for _ in range(2**16):
        candidate_run_id, _ = compute_run_id(manifest_bytes, seed, t_ns)
        if not _run_id_in_use(
            config.repo_root,
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
        raise InputResolutionError("Run ID collision exhausted.")
    run_paths = RunPaths(config.repo_root, run_id)

    outputs = _build_output_paths(
        run_paths,
        dictionary,
        seed=seed,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id=run_id,
    )
    logger.info("Output root: %s", run_paths.run_root)

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

    context = RunContext(
        merchants=MerchantUniverse(frame=merchant_df, iso_set=iso_set),
        gdp_per_capita=gdp_map,
        gdp_bucket_map=gdp_bucket_map,
        channel_map=CHANNEL_MAP,
    )
    logger.info("S0 foundations complete for run_id=%s", run_id)
    return S0RunResult(
        run_id=run_id,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        outputs=outputs,
        context=context,
    )
