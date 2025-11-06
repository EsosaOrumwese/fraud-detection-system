"""High-level orchestration for Segment 2A S0 gate."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import polars as pl

from ...shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path
from ..exceptions import S0GateError, err
from ..l0 import (
    ArtifactDigest,
    BundleIndex,
    compute_index_digest,
    ensure_within_base,
    expand_files,
    hash_files,
    load_index,
    read_pass_flag,
)
from ..l1.sealed_inputs import SealedAsset, ensure_unique_assets
from ..l1.validation import validate_receipt_payload
from ...seg_1A.s0_foundations.l1.hashing import (
    ParameterHashResult,
    compute_manifest_fingerprint,
    compute_parameter_hash,
    normalise_git_commit,
)


@dataclass(frozen=True)
class GateInputs:
    """Configuration required to execute the 2A S0 gate."""

    base_path: Path
    output_base_path: Path
    seed: int | str
    upstream_manifest_fingerprint: str
    tzdb_release_tag: str
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    validation_bundle_path: Optional[Path] = None
    notes: Optional[str] = None
    parameter_asset_ids: tuple[str, ...] = field(
        default_factory=lambda: ("tz_overrides", "tz_nudge")
    )
    optional_asset_ids: tuple[str, ...] = field(
        default_factory=lambda: ("iso3166_canonical_2024",)
    )

    def __post_init__(self) -> None:
        base = self.base_path.resolve()
        output = self.output_base_path.resolve()
        object.__setattr__(self, "base_path", base)
        object.__setattr__(self, "output_base_path", output)
        seed_str = str(self.seed)
        if not seed_str:
            raise err("E_SEED_EMPTY", "seed must be provided for S0")
        object.__setattr__(self, "seed", seed_str)
        if len(self.upstream_manifest_fingerprint) != 64:
            raise err(
                "E_UPSTREAM_FINGERPRINT",
                "upstream manifest fingerprint must be 64 hex characters",
            )
        git_hex = self.git_commit_hex.lower()
        if len(git_hex) not in (40, 64):
            raise err(
                "E_GIT_COMMIT_LEN",
                "git commit hex must be 40 (SHA1) or 64 (SHA256) characters",
            )
        int(git_hex, 16)  # raises ValueError if not hex
        object.__setattr__(self, "git_commit_hex", git_hex)
        if not self.tzdb_release_tag:
            raise err("E_TZDB_RELEASE_EMPTY", "tzdb_release_tag must be provided")


@dataclass(frozen=True)
class GateOutputs:
    """Result bundle emitted by :class:`S0GateRunner`."""

    manifest_fingerprint: str
    parameter_hash: str
    flag_sha256_hex: str
    receipt_path: Path
    inventory_path: Path
    sealed_assets: tuple[SealedAsset, ...]
    validation_bundle_path: Path
    verified_at_utc: datetime


class S0GateRunner:
    """High-level helper that wires together the 2A S0 workflow."""

    _ASSET_KIND_MAP = {
        "validation_bundle_1B": "validation",
        "validation_passed_flag_1B": "validation",
        "site_locations": "reference",
        "tz_world_2025a": "reference",
        "iso3166_canonical_2024": "reference",
        "tzdb_release": "artefact",
        "tz_overrides": "policy",
        "tz_nudge": "policy",
    }

    def run(self, inputs: GateInputs) -> GateOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        bundle_path = self._resolve_validation_bundle_path(inputs, dictionary=dictionary)
        if not bundle_path.exists():
            raise err("E_BUNDLE_MISSING", f"validation bundle '{bundle_path}' not found")
        if not bundle_path.is_dir():
            raise err(
                "E_BUNDLE_INVALID",
                f"validation bundle path '{bundle_path}' must be a directory",
            )

        bundle_index = load_index(bundle_path)
        computed_flag = compute_index_digest(bundle_path, bundle_index)
        declared_flag = read_pass_flag(bundle_path)
        if computed_flag != declared_flag:
            raise err(
                "E_FLAG_HASH_MISMATCH",
                "computed digest does not match upstream _passed.flag",
            )

        sealed_assets = self._collect_sealed_assets(
            inputs=inputs,
            dictionary=dictionary,
            bundle_path=bundle_path,
            bundle_index=bundle_index,
        )

        parameter_assets = [
            asset for asset in sealed_assets if asset.asset_id in inputs.parameter_asset_ids
        ]
        if not parameter_assets:
            raise err(
                "E_PARAM_EMPTY",
                "no parameter assets found when computing parameter hash",
            )

        parameter_digests: list[ArtifactDigest] = []
        for asset in parameter_assets:
            parameter_digests.extend(asset.digests)
        parameter_result = compute_parameter_hash(parameter_digests)

        manifest_digests = self._collect_manifest_digests(sealed_assets)
        git_bytes = normalise_git_commit(bytes.fromhex(inputs.git_commit_hex))
        manifest_result = compute_manifest_fingerprint(
            manifest_digests,
            git_commit_raw=git_bytes,
            parameter_hash_bytes=bytes.fromhex(parameter_result.parameter_hash),
        )

        receipt_path, verified_at = self._write_receipt(
            inputs=inputs,
            dictionary=dictionary,
            manifest_fingerprint=manifest_result.manifest_fingerprint,
            parameter_result=parameter_result,
            flag_sha256_hex=declared_flag,
            sealed_assets=sealed_assets,
        )
        inventory_path = self._write_inventory(
            inputs=inputs,
            dictionary=dictionary,
            manifest_fingerprint=manifest_result.manifest_fingerprint,
            sealed_assets=sealed_assets,
        )

        return GateOutputs(
            manifest_fingerprint=manifest_result.manifest_fingerprint,
            parameter_hash=parameter_result.parameter_hash,
            flag_sha256_hex=declared_flag,
            receipt_path=receipt_path,
            inventory_path=inventory_path,
            sealed_assets=tuple(sealed_assets),
            validation_bundle_path=bundle_path,
            verified_at_utc=verified_at,
        )

    # ------------------------------------------------------------------ helpers

    def _resolve_validation_bundle_path(
        self,
        inputs: GateInputs,
        *,
        dictionary: Mapping[str, object],
    ) -> Path:
        if inputs.validation_bundle_path is not None:
            return inputs.validation_bundle_path.resolve()
        rendered = render_dataset_path(
            "validation_bundle_1B",
            template_args={
                "manifest_fingerprint": inputs.upstream_manifest_fingerprint
            },
            dictionary=dictionary,
        )
        return (inputs.base_path / rendered).resolve()

    def _collect_sealed_assets(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        bundle_path: Path,
        bundle_index: BundleIndex,
    ) -> list[SealedAsset]:
        assets: list[SealedAsset] = []
        seed = str(inputs.seed)
        base_path = inputs.base_path
        upstream_fp = inputs.upstream_manifest_fingerprint

        def add_asset(
            asset_id: str,
            *,
            template_args: Mapping[str, object],
            file_override: Optional[Sequence[Path]] = None,
            resolved_override: Optional[Path] = None,
        ) -> None:
            try:
                entry = get_dataset_entry(asset_id, dictionary=dictionary)
            except S0GateError:
                if asset_id in inputs.optional_asset_ids:
                    return
                raise

            catalog_path = render_dataset_path(
                asset_id, template_args=template_args, dictionary=dictionary
            )
            if resolved_override is not None:
                resolved_path = resolved_override.resolve()
            else:
                resolved_path = (base_path / catalog_path).resolve()
            ensure_within_base(resolved_path, base_path=base_path)

            if file_override is not None:
                files = list(file_override)
            else:
                files = expand_files(resolved_path)

            if asset_id == "validation_bundle_1B" and files:
                files = [
                    path for path in files if path.name != "_passed.flag"
                ]

            for file_path in files:
                ensure_within_base(file_path, base_path=base_path)

            digests = hash_files(files, error_prefix=f"E_ASSET_{asset_id}")
            partitioning = entry.get("partitioning") or []
            if not isinstance(partitioning, Iterable):
                raise err(
                    "E_DICTIONARY_RESOLUTION_FAILED",
                    f"dictionary entry '{asset_id}' has invalid partitioning",
                )
            version_template = str(entry.get("version", ""))
            version = self._render_template(version_template, template_args)
            license_class = str(entry.get("license", ""))
            notes = entry.get("notes")
            asset_kind = self._ASSET_KIND_MAP.get(asset_id, "unknown")

            assets.append(
                SealedAsset(
                    asset_id=asset_id,
                    schema_ref=str(entry.get("schema_ref", "")),
                    asset_kind=asset_kind,
                    catalog_path=catalog_path,
                    resolved_path=resolved_path,
                    partition_keys=tuple(str(part) for part in partitioning),
                    version_tag=version,
                    license_class=license_class,
                    digests=tuple(digests),
                    notes=str(notes) if notes else None,
                )
            )

        bundle_files = [
            (bundle_path / entry.path).resolve() for entry in bundle_index.iter_entries()
        ]
        add_asset(
            "validation_bundle_1B",
            template_args={"manifest_fingerprint": upstream_fp},
            file_override=bundle_files,
            resolved_override=bundle_path,
        )
        flag_override = (bundle_path / "_passed.flag").resolve()
        add_asset(
            "validation_passed_flag_1B",
            template_args={"manifest_fingerprint": upstream_fp},
            file_override=[flag_override],
            resolved_override=flag_override,
        )
        add_asset(
            "site_locations",
            template_args={"seed": seed, "manifest_fingerprint": upstream_fp},
        )
        add_asset("tz_world_2025a", template_args={})
        add_asset("tzdb_release", template_args={"release_tag": inputs.tzdb_release_tag})
        add_asset("tz_overrides", template_args={})
        add_asset("tz_nudge", template_args={})
        for optional_id in inputs.optional_asset_ids:
            if optional_id not in {asset.asset_id for asset in assets}:
                add_asset(optional_id, template_args={})

        return ensure_unique_assets(assets)

    def _collect_manifest_digests(
        self, assets: Iterable[SealedAsset]
    ) -> Sequence[ArtifactDigest]:
        manifest_map: dict[Path, ArtifactDigest] = {}
        for asset in assets:
            for digest in asset.digests:
                manifest_map[digest.path] = digest
        return sorted(
            manifest_map.values(),
            key=lambda d: (d.basename, str(d.path)),
        )

    def _write_receipt(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        parameter_result: ParameterHashResult,
        flag_sha256_hex: str,
        sealed_assets: Sequence[SealedAsset],
    ) -> tuple[Path, datetime]:
        sealed_entries = [
            asset.as_receipt_entry() for asset in sorted(sealed_assets, key=lambda a: a.asset_id)
        ]
        bundle_path_template = render_dataset_path(
            "validation_bundle_1B",
            template_args={"manifest_fingerprint": inputs.upstream_manifest_fingerprint},
            dictionary=dictionary,
        )
        timestamp = (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        payload: dict[str, object] = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_result.parameter_hash,
            "validation_bundle_path": bundle_path_template,
            "flag_sha256_hex": flag_sha256_hex,
            "verified_at_utc": timestamp,
            "sealed_inputs": sealed_entries,
        }
        if inputs.notes:
            payload["notes"] = inputs.notes

        validate_receipt_payload(payload)

        receipt_rel_path = render_dataset_path(
            "s0_gate_receipt_2A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        receipt_path = (inputs.output_base_path / receipt_rel_path).resolve()
        ensure_within_base(receipt_path, base_path=inputs.output_base_path)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        payload_bytes = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"

        if receipt_path.exists():
            existing_bytes = receipt_path.read_bytes()
            if existing_bytes == payload_bytes:
                return receipt_path, datetime.fromisoformat(
                    payload["verified_at_utc"].replace("Z", "+00:00")
                )
            raise err(
                "E_RECEIPT_EXISTS",
                f"receipt already exists at '{receipt_path}' with different content",
            )

        temp_path = receipt_path.parent / f".tmp.{uuid.uuid4().hex}.json"
        try:
            temp_path.write_bytes(payload_bytes)
            temp_path.replace(receipt_path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

        return receipt_path, datetime.fromisoformat(
            payload["verified_at_utc"].replace("Z", "+00:00")
        )

    def _write_inventory(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        sealed_assets: Sequence[SealedAsset],
    ) -> Path:
        rows = [
            asset.as_inventory_row(manifest_fingerprint=manifest_fingerprint)
            for asset in sorted(sealed_assets, key=lambda a: (a.asset_kind, a.asset_id))
        ]
        frame = pl.DataFrame(rows)

        inventory_rel_path = render_dataset_path(
            "sealed_inputs_v1",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        inventory_path = (inputs.output_base_path / inventory_rel_path).resolve()
        ensure_within_base(inventory_path, base_path=inputs.output_base_path)
        inventory_path.parent.mkdir(parents=True, exist_ok=True)

        if inventory_path.exists():
            existing = pl.read_parquet(inventory_path)
            if existing.frame_equal(frame):
                return inventory_path
            raise err(
                "E_INVENTORY_EXISTS",
                f"sealed_inputs_v1 already exists at '{inventory_path}' with different content",
            )

        temp_path = inventory_path.parent / f".tmp.{uuid.uuid4().hex}.parquet"
        try:
            frame.write_parquet(temp_path, compression="zstd")
            temp_path.replace(inventory_path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
        return inventory_path

    @staticmethod
    def _render_template(template: str, template_args: Mapping[str, object]) -> str:
        if not template:
            return template
        safe_args = {key: str(value) for key, value in template_args.items()}
        try:
            return template.format(**safe_args)
        except KeyError:
            return template


__all__ = ["S0GateRunner", "GateInputs", "GateOutputs", "SealedAsset", "S0GateError"]
