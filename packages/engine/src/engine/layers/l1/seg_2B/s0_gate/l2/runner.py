"""High-level orchestration for Segment 2B S0 gate."""

from __future__ import annotations

import json
import logging
import platform
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence

from ...shared.dictionary import (
    get_dataset_entry,
    load_dictionary,
    render_dataset_path,
    repository_root,
)
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
from ..l1.validation import validate_inventory_payload, validate_receipt_payload

logger = logging.getLogger(__name__)

_REQUIRED_POLICY_IDS: tuple[str, ...] = (
    "route_rng_policy_v1",
    "alias_layout_policy_v1",
    "day_effect_policy_v1",
    "virtual_edge_policy_v1",
)


@dataclass(frozen=True)
class GateInputs:
    """Configuration required to execute the 2B S0 gate."""

    data_root: Path
    seed: int | str
    manifest_fingerprint: str
    seg2a_manifest_fingerprint: str
    parameter_hash: str
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    validation_bundle_path: Optional[Path] = None
    notes: Optional[str] = None
    policy_asset_ids: tuple[str, ...] = _REQUIRED_POLICY_IDS
    pin_civil_time: bool = False

    def __post_init__(self) -> None:
        data_root = self.data_root.expanduser().resolve()
        object.__setattr__(self, "data_root", data_root)
        seed_value = str(self.seed)
        if not seed_value:
            raise err("E_SEED_EMPTY", "seed must be provided for S0")
        object.__setattr__(self, "seed", seed_value)
        manifest = self.manifest_fingerprint.lower()
        if len(manifest) != 64:
            raise err(
                "E_MANIFEST_FINGERPRINT",
                "manifest_fingerprint must be 64 hex characters",
            )
        int(manifest, 16)
        object.__setattr__(self, "manifest_fingerprint", manifest)
        parameter_hash = self.parameter_hash.lower()
        if len(parameter_hash) != 64:
            raise err(
                "E_PARAMETER_HASH",
                "parameter_hash must be 64 hex characters",
            )
        int(parameter_hash, 16)
        object.__setattr__(self, "parameter_hash", parameter_hash)
        seg2a_manifest = self.seg2a_manifest_fingerprint.lower()
        if len(seg2a_manifest) != 64:
            raise err(
                "E_SEG2A_FINGERPRINT",
                "seg2a_manifest_fingerprint must be 64 hex characters",
            )
        int(seg2a_manifest, 16)
        object.__setattr__(self, "seg2a_manifest_fingerprint", seg2a_manifest)
        git_hex = self.git_commit_hex.lower()
        if len(git_hex) not in (40, 64):
            raise err(
                "E_GIT_COMMIT_LEN",
                "git commit hex must be 40 (SHA1) or 64 (SHA256) characters",
            )
        int(git_hex, 16)
        object.__setattr__(self, "git_commit_hex", git_hex)


@dataclass(frozen=True)
class GateOutputs:
    """Result bundle emitted by :class:`S0GateRunner`."""

    manifest_fingerprint: str
    parameter_hash: str
    flag_sha256_hex: str
    receipt_path: Path
    inventory_path: Path
    sealed_assets: tuple[SealedAsset, ...]
    verified_at_utc: datetime


class S0GateRunner:
    """High-level helper that wires together the 2B S0 workflow."""

    _CIVIL_OPTIONAL_IDS = ("site_timezones", "tz_timetable_cache")

    def run(self, inputs: GateInputs) -> GateOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        bundle_path = self._resolve_validation_bundle_path(inputs, dictionary=dictionary)
        bundle_index = load_index(bundle_path)
        bundle_digest = compute_index_digest(bundle_path, bundle_index)
        flag_digest = read_pass_flag(bundle_path)
        if bundle_digest != flag_digest:
            raise err(
                "E_FLAG_MISMATCH",
                "validation bundle digest does not match _passed.flag",
            )

        sealed_assets = self._collect_sealed_assets(
            inputs=inputs,
            dictionary=dictionary,
            bundle_path=bundle_path,
            bundle_index=bundle_index,
        )

        receipt_path, inventory_path, verified_at = self._write_outputs(
            inputs=inputs,
            dictionary=dictionary,
            sealed_assets=sealed_assets,
            bundle_path=bundle_path,
            flag_sha256_hex=flag_digest,
        )

        logger.info(
            "Segment2B S0 completed (manifest=%s, receipt=%s)",
            inputs.manifest_fingerprint,
            receipt_path,
        )

        return GateOutputs(
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            flag_sha256_hex=flag_digest,
            receipt_path=receipt_path,
            inventory_path=inventory_path,
            sealed_assets=tuple(sealed_assets),
            verified_at_utc=verified_at,
        )

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
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        return (inputs.data_root / rendered).resolve()

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
        manifest = inputs.manifest_fingerprint
        data_root = inputs.data_root
        repo_root = repository_root()

        def resolve_catalog_path(catalog_path: str) -> tuple[Path, Path]:
            candidate = (data_root / catalog_path).resolve()
            if candidate.exists():
                ensure_within_base(candidate, base_path=data_root)
                return candidate, data_root
            repo_candidate = (repo_root / catalog_path).resolve()
            if repo_candidate.exists():
                ensure_within_base(repo_candidate, base_path=repo_root)
                return repo_candidate, repo_root
            return candidate, data_root

        def add_asset(
            asset_id: str,
            *,
            template_args: Mapping[str, object],
            file_override: Optional[Sequence[Path]] = None,
            resolved_override: Optional[Path] = None,
            allow_missing: bool = False,
        ) -> None:
            try:
                entry = get_dataset_entry(asset_id, dictionary=dictionary)
            except S0GateError:
                if allow_missing:
                    return
                raise

            catalog_path = render_dataset_path(
                asset_id, template_args=template_args, dictionary=dictionary
            )
            if resolved_override is not None:
                resolved_path = resolved_override.resolve()
                base_for_path = data_root if resolved_path.is_relative_to(data_root) else repo_root
            else:
                resolved_path, base_for_path = resolve_catalog_path(catalog_path)
            ensure_within_base(resolved_path, base_path=base_for_path)

            if file_override is not None:
                files = list(file_override)
            else:
                files = expand_files(resolved_path)

            if not files:
                raise err(
                    "E_ASSET_EMPTY",
                    f"asset '{asset_id}' has no files",
                )

            digests = hash_files(files, error_prefix=f"E_ASSET_{asset_id}")
            partitioning = entry.get("partitioning") or []
            version_template = str(entry.get("version", ""))
            version = self._render_template(version_template, template_args)
            if not version:
                raise err(
                    "E_ASSET_VERSION_MISSING",
                    f"dictionary entry '{asset_id}' missing version",
                )
            assets.append(
                SealedAsset(
                    asset_id=asset_id,
                    schema_ref=str(entry.get("schema_ref", "")),
                    catalog_path=catalog_path,
                    resolved_path=resolved_path,
                    partition_keys=tuple(str(part) for part in partitioning),
                    version_tag=version,
                    digests=tuple(digests),
                )
            )

        bundle_files = [
            (bundle_path / entry.path).resolve() for entry in bundle_index.iter_entries()
        ]
        add_asset(
            "validation_bundle_1B",
            template_args={"manifest_fingerprint": manifest},
            file_override=bundle_files,
            resolved_override=bundle_path,
        )
        flag_override = (bundle_path / "_passed.flag").resolve()
        add_asset(
            "validation_passed_flag_1B",
            template_args={"manifest_fingerprint": manifest},
            file_override=[flag_override],
            resolved_override=flag_override,
        )
        add_asset(
            "site_locations",
            template_args={"seed": seed, "manifest_fingerprint": manifest},
        )
        for policy_id in inputs.policy_asset_ids:
            add_asset(policy_id, template_args={})

        if inputs.pin_civil_time:
            for asset_id in self._CIVIL_OPTIONAL_IDS:
                add_asset(
                    asset_id,
                    template_args={
                        "seed": seed,
                        "manifest_fingerprint": inputs.seg2a_manifest_fingerprint,
                    },
                    allow_missing=False,
                )

        return ensure_unique_assets(assets)

    def _write_outputs(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        sealed_assets: Sequence[SealedAsset],
        bundle_path: Path,
        flag_sha256_hex: str,
    ) -> tuple[Path, Path, datetime]:
        sealed_sorted = sorted(sealed_assets, key=lambda asset: (asset.asset_id, asset.catalog_path))
        rows = [asset.as_inventory_row() for asset in sealed_sorted]
        validate_inventory_payload(rows)

        inventory_rel = render_dataset_path(
            "sealed_inputs_v1",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        inventory_path = (inputs.data_root / inventory_rel).resolve()
        ensure_within_base(inventory_path, base_path=inputs.data_root)
        inventory_path.parent.mkdir(parents=True, exist_ok=True)

        temp_inventory = inventory_path.parent / f".tmp.{uuid.uuid4().hex}.json"
        try:
            temp_inventory.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            temp_inventory.replace(inventory_path)
        finally:
            if temp_inventory.exists():
                temp_inventory.unlink(missing_ok=True)

        sealed_entries = [asset.as_receipt_entry() for asset in sealed_sorted]
        catalogue_resolution = self._catalogue_resolution(dictionary)
        policy_ids, policy_digests = self._policy_digests(
            sealed_sorted, required_ids=inputs.policy_asset_ids
        )
        determinism_receipt = {
            "engine_commit": inputs.git_commit_hex,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "policy_ids": policy_ids,
            "policy_digests": policy_digests,
        }
        receipt_payload = {
            "segment": "2B",
            "state": "S0",
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "seed": str(inputs.seed),
            "parameter_hash": inputs.parameter_hash,
            "validation_bundle_path": str(bundle_path),
            "flag_sha256_hex": flag_sha256_hex,
            "verified_at_utc": _now_utc(),
            "sealed_inputs": sealed_entries,
            "catalogue_resolution": catalogue_resolution,
            "determinism_receipt": determinism_receipt,
        }
        if inputs.notes:
            receipt_payload["notes"] = inputs.notes
        validate_receipt_payload(receipt_payload)

        receipt_rel = render_dataset_path(
            "s0_gate_receipt_2B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        receipt_path = (inputs.data_root / receipt_rel).resolve()
        ensure_within_base(receipt_path, base_path=inputs.data_root)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)

        temp_receipt = receipt_path.parent / f".tmp.{uuid.uuid4().hex}.json"
        try:
            temp_receipt.write_text(
                json.dumps(receipt_payload, indent=2), encoding="utf-8"
            )
            temp_receipt.replace(receipt_path)
        finally:
            if temp_receipt.exists():
                temp_receipt.unlink(missing_ok=True)

        verified_at = datetime.strptime(
            receipt_payload["verified_at_utc"], "%Y-%m-%dT%H:%M:%S.%fZ"
        ).replace(tzinfo=timezone.utc)
        return receipt_path, inventory_path, verified_at

    def _catalogue_resolution(self, dictionary: Mapping[str, object]) -> dict[str, str]:
        catalogue = dictionary.get("catalogue") or {}
        dictionary_version = str(
            catalogue.get("dictionary_version") or dictionary.get("version") or "unversioned"
        )
        registry_version = str(
            catalogue.get("registry_version") or dictionary_version
        )
        return {
            "dictionary_version": dictionary_version,
            "registry_version": registry_version,
        }

    def _policy_digests(
        self,
        assets: Sequence[SealedAsset],
        *,
        required_ids: Sequence[str],
    ) -> tuple[list[str], list[str]]:
        digests: list[tuple[str, str]] = [
            (asset.asset_id, asset.sha256_hex)
            for asset in assets
            if asset.asset_id in required_ids
        ]
        missing = sorted(set(required_ids) - {item[0] for item in digests})
        if missing:
            raise err(
                "E_POLICY_MISSING",
                f"missing required policy assets: {', '.join(missing)}",
            )
        digests.sort(key=lambda item: item[0])
        ids = [item[0] for item in digests]
        values = [item[1] for item in digests]
        return ids, values

    @staticmethod
    def _render_template(template: str, template_args: Mapping[str, object]) -> str:
        if not template:
            return ""
        safe_args = {key: str(value) for key, value in template_args.items()}
        try:
            return template.format(**safe_args)
        except KeyError:
            return template


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


__all__ = ["GateInputs", "GateOutputs", "S0GateRunner"]
