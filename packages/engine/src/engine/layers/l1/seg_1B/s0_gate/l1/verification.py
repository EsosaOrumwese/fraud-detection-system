"""L1 helpers for Segment 1B S0 gate verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import polars as pl
import yaml
from jsonschema import Draft202012Validator, ValidationError

from ...shared import dictionary as dict_utils
from ...shared.dictionary import get_dataset_entry, get_repo_root
from ...shared.schema import load_schema
from ..exceptions import err
from ..l0.bundle import BundleIndex, compute_index_digest, load_index, read_pass_flag


@dataclass(frozen=True)
class VerifiedBundle:
    """Result of the validation bundle gate check."""

    bundle_dir: Path
    index: BundleIndex
    flag_sha256_hex: str


def verify_bundle(bundle_dir: Path) -> VerifiedBundle:
    """Verify the fingerprint-scoped validation bundle."""

    index = load_index(bundle_dir)
    computed = compute_index_digest(bundle_dir, index)
    declared = read_pass_flag(bundle_dir)
    if computed != declared:
        raise err(
            "E_FLAG_HASH_MISMATCH",
            "computed digest does not match _passed.flag",
        )
    return VerifiedBundle(bundle_dir=bundle_dir, index=index, flag_sha256_hex=declared)


def verify_outlet_catalogue_lineage(
    *,
    base_path: Path,
    dictionary: Mapping[str, object],
    manifest_fingerprint: str,
    seed: str,
) -> Path:
    """Assert the outlet catalogue partition exists and embeds lineage correctly."""

    path = dict_utils.resolve_dataset_path(
        "outlet_catalogue",
        base_path=base_path,
        template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    if not path.exists():
        raise err(
            "E_REFERENCE_SURFACE_MISSING",
            f"outlet_catalogue partition '{path}' missing",
        )

    dataset_pattern: str
    if path.is_dir():
        dataset_pattern = str(path / "*.parquet")
    elif path.suffix == ".parquet":
        dataset_pattern = str(path)
    else:
        raise err(
            "E_PARTITION_MISPLACED",
            f"outlet_catalogue path '{path}' is neither directory nor parquet file",
        )

    lazy_frame = pl.scan_parquet(dataset_pattern)
    columns = lazy_frame.collect_schema().names()
    if "manifest_fingerprint" not in columns:
        raise err(
            "E_PATH_EMBED_MISMATCH",
            "outlet_catalogue missing manifest_fingerprint column",
        )

    observed = (
        lazy_frame.select(pl.col("manifest_fingerprint").cast(str).unique())
        .collect()
        .get_column("manifest_fingerprint")
        .to_list()
    )
    if any(value != manifest_fingerprint for value in observed):
        raise err(
            "E_PATH_EMBED_MISMATCH",
            "outlet_catalogue manifest_fingerprint mismatch with path token",
        )

    if "global_seed" in columns:
        seeds = (
            lazy_frame.select(pl.col("global_seed").cast(str).unique())
            .collect()
            .get_column("global_seed")
            .to_list()
        )
        if any(value != str(seed) for value in seeds):
            raise err(
                "E_PATH_EMBED_MISMATCH",
                "outlet_catalogue global_seed mismatch with seed path token",
            )

    return path


def ensure_reference_surfaces(
    *,
    base_path: Path,
    dictionary: Mapping[str, object],
    manifest_fingerprint: str,
    parameter_hash: str,
) -> None:
    """Ensure static references declared for S0 exist."""

    required: Sequence[tuple[str, Mapping[str, object]]] = [
        ("iso3166_canonical_2024", {}),
        ("world_countries", {}),
        ("population_raster_2025", {}),
        ("tz_world_2025a", {}),
        ("s3_candidate_set", {"parameter_hash": parameter_hash}),
    ]
    for dataset_id, template_args in required:
        path = dict_utils.resolve_dataset_path(
            dataset_id,
            base_path=base_path,
            template_args=template_args,
            dictionary=dictionary,
        )
        if not path.exists():
            raise err(
                "E_REFERENCE_SURFACE_MISSING",
                f"required dataset '{dataset_id}' missing at '{path}'",
            )

    # Validation bundle path is derived when verifying the bundle; no extra check here.


def build_sealed_inputs(
    *,
    dictionary: Mapping[str, object],
) -> list[dict]:
    """Emit the sealed input list recorded in the receipt."""

    entries: Sequence[tuple[str, Iterable[str]]] = (
        ("outlet_catalogue", ("seed", "fingerprint")),
        ("s3_candidate_set", ("parameter_hash",)),
        ("iso3166_canonical_2024", ()),
        ("world_countries", ()),
        ("population_raster_2025", ()),
        ("tz_world_2025a", ()),
    )
    sealed: list[dict] = []
    for dataset_id, partitions in entries:
        entry = dict_utils.get_dataset_entry(dataset_id, dictionary=dictionary)
        schema_ref = entry.get("schema_ref")
        if not isinstance(schema_ref, str) or not schema_ref:
            raise err(
                "E_DICTIONARY_RESOLUTION_FAILED",
                f"dataset '{dataset_id}' missing schema_ref in dictionary",
            )
        payload: dict = {"id": dataset_id, "schema_ref": schema_ref}
        parts = [str(part) for part in partitions if part]
        if parts:
            payload["partition"] = parts
        sealed.append(payload)
    return sealed


def verify_license_map_coverage(
    *,
    sealed_inputs: Sequence[Mapping[str, object]],
    dictionary: Mapping[str, object],
) -> None:
    """Ensure sealed inputs declare a license present in license_map.yaml."""

    repo_root = get_repo_root()
    license_map_path = repo_root / "licenses" / "license_map.yaml"
    if not license_map_path.exists():
        raise err("E_LICENSE_MAP_MISSING", f"license map missing at '{license_map_path}'")

    payload = yaml.safe_load(license_map_path.read_text(encoding="utf-8")) or {}
    licenses = payload.get("licenses")
    if not isinstance(licenses, Mapping):
        raise err("E_LICENSE_MAP_INVALID", "license_map.yaml missing 'licenses' mapping")

    for entry in sealed_inputs:
        dataset_id = entry.get("id")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise err("E_LICENSE_MAP_INVALID", "sealed input missing dataset id")
        dataset_entry = get_dataset_entry(dataset_id, dictionary=dictionary)
        license_name = dataset_entry.get("license") if isinstance(dataset_entry, Mapping) else None
        if not isinstance(license_name, str) or not license_name.strip():
            raise err(
                "E_LICENSE_MAP_INVALID",
                f"sealed input '{dataset_id}' missing license declaration in dictionary",
            )
        license_block = licenses.get(license_name)
        if not isinstance(license_block, Mapping):
            raise err(
                "E_LICENSE_MAP_INVALID",
                f"license '{license_name}' for '{dataset_id}' not present in license_map.yaml",
            )
        text_path = license_block.get("text_path")
        if not isinstance(text_path, str) or not text_path.strip():
            raise err(
                "E_LICENSE_MAP_INVALID",
                f"license '{license_name}' missing text_path in license_map.yaml",
            )
        if not (repo_root / text_path).exists():
            raise err(
                "E_LICENSE_MAP_INVALID",
                f"license text file '{text_path}' missing for '{license_name}'",
            )


def validate_receipt_payload(payload: Mapping[str, object]) -> None:
    """Validate the payload against the canonical JSON schema."""

    schema = load_schema("#/validation/s0_gate_receipt")
    validator = Draft202012Validator(schema)
    try:
        validator.validate(payload)
    except ValidationError as exc:
        raise err(
            "E_RECEIPT_SCHEMA_INVALID",
            f"receipt schema violation: {exc.message}",
        ) from exc


__all__ = [
    "VerifiedBundle",
    "verify_bundle",
    "verify_outlet_catalogue_lineage",
    "ensure_reference_surfaces",
    "build_sealed_inputs",
    "verify_license_map_coverage",
    "validate_receipt_payload",
]
