"""Resolve S0 inputs using the dataset dictionary and run isolation rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

from engine.contracts.loader import DatasetEntry, find_dataset_entry
from engine.core.errors import InputResolutionError
from engine.core.paths import RunPaths, resolve_input_path


@dataclass(frozen=True)
class InputAsset:
    asset_id: str
    path: Path
    schema_ref: Optional[str]
    version_tag: str
    partition: Mapping[str, str]


def _pick_version(path_root: Path, preferred: Optional[str]) -> str:
    if preferred:
        return preferred
    if not path_root.exists():
        raise InputResolutionError(f"Reference root missing: {path_root}")
    candidates = sorted([p.name for p in path_root.iterdir() if p.is_dir()])
    if not candidates:
        raise InputResolutionError(f"No version directories found under {path_root}")
    return candidates[-1]


def _select_data_file(dataset_id: str, dataset_path: Path) -> Path:
    if dataset_path.is_file():
        return dataset_path
    if not dataset_path.exists():
        raise InputResolutionError(f"Dataset path does not exist: {dataset_path}")
    if not dataset_path.is_dir():
        raise InputResolutionError(f"Dataset path is not a file or dir: {dataset_path}")
    explicit = dataset_path / f"{dataset_id}.parquet"
    if explicit.exists():
        return explicit
    parquet_files = sorted(dataset_path.glob("*.parquet"))
    if len(parquet_files) == 1:
        return parquet_files[0]
    raise InputResolutionError(
        f"Unable to resolve dataset file in {dataset_path}; "
        f"expected {explicit.name} or a single parquet file."
    )


def resolve_dataset_input(
    dataset_entry: DatasetEntry,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    version_override: Optional[str] = None,
    tokens: Optional[Mapping[str, str]] = None,
) -> InputAsset:
    entry = dataset_entry.entry
    path_template = entry.get("path")
    if not path_template:
        raise InputResolutionError(
            f"Dataset entry missing path: {dataset_entry.dataset_id}"
        )
    token_map = dict(tokens or {})
    version = entry.get("version")
    if version and version not in ("TBD", "null"):
        token_map.setdefault("version", str(version))
    if "{version}" in path_template:
        base_root = Path(path_template.split("{version}")[0])
        base_root = resolve_input_path(str(base_root), run_paths, external_roots)
        token_map["version"] = _pick_version(
            base_root, version_override or token_map.get("version")
        )
    for key, value in token_map.items():
        path_template = path_template.replace(f"{{{key}}}", value)
    resolved = resolve_input_path(path_template, run_paths, external_roots)
    data_file = _select_data_file(dataset_entry.dataset_id, resolved)
    partition = {}
    partition_keys = entry.get("partitioning") or []
    for key in partition_keys:
        if key in token_map:
            partition[key] = token_map[key]
    return InputAsset(
        asset_id=dataset_entry.dataset_id,
        path=data_file,
        schema_ref=entry.get("schema_ref"),
        version_tag=token_map.get("version", entry.get("version") or "unknown"),
        partition=partition,
    )


def resolve_reference_inputs(
    dictionary: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    merchant_ids_version: Optional[str],
) -> list[InputAsset]:
    assets = []
    for dataset_id in (
        "transaction_schema_merchant_ids",
        "iso3166_canonical_2024",
        "world_bank_gdp_per_capita_20250415",
        "gdp_bucket_map_2024",
    ):
        entry = find_dataset_entry(dictionary, dataset_id)
        version_override = (
            merchant_ids_version
            if dataset_id == "transaction_schema_merchant_ids"
            else None
        )
        assets.append(
            resolve_dataset_input(
                entry,
                run_paths=run_paths,
                external_roots=external_roots,
                version_override=version_override,
            )
        )
    return assets
