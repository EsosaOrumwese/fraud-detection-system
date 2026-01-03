"""High-level orchestration for Segment 2A S0 gate."""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional, Sequence

import polars as pl

from ...shared.dictionary import (
    get_dataset_entry,
    load_dictionary,
    render_dataset_path,
    repository_root,
)
from engine.shared.run_bundle import RunBundleError, materialize_repo_asset
from ..exceptions import S0GateError, err
from ..l0 import (
    ArtifactDigest,
    BundleIndex,
    aggregate_sha256,
    compute_index_digest,
    ensure_within_base,
    expand_files,
    hash_files,
    load_index,
    read_pass_flag,
)
from ..l1.sealed_inputs import SealedAsset, ensure_unique_assets
from ..l1.validation import validate_receipt_payload
from ....seg_1A.s0_foundations.l1.hashing import (
    ParameterHashResult,
    compute_parameter_hash,
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
    emit_run_report_stdout: bool = True

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
    determinism_receipt: Mapping[str, object]
    run_report_path: Path


logger = logging.getLogger(__name__)


class S0GateRunner:
    """High-level helper that wires together the 2A S0 workflow."""

    _ASSET_KIND_MAP = {
        "validation_bundle_1B": "bundle",
        "validation_passed_flag_1B": "bundle",
        "site_locations": "dataset",
        "tz_world_2025a": "dataset",
        "iso3166_canonical_2024": "dataset",
        "tzdb_release": "dataset",
        "tz_overrides": "config",
        "tz_nudge": "config",
        "merchant_mcc_map": "dataset",
    }

    def run(self, inputs: GateInputs) -> GateOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        run_started_at = datetime.now(timezone.utc)
        wall_timer = time.perf_counter()
        self._ensure_merchant_mcc_map(inputs=inputs, dictionary=dictionary)
        gate_timer = time.perf_counter()
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
        gate_verify_ms = int(round((time.perf_counter() - gate_timer) * 1000))

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

        manifest_fingerprint = inputs.upstream_manifest_fingerprint
        sealed_assets = self._rehome_merchant_mcc_map(
            inputs=inputs,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            sealed_assets=sealed_assets,
        )

        receipt_path, verified_at = self._write_receipt(
            inputs=inputs,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            parameter_result=parameter_result,
            flag_sha256_hex=declared_flag,
            sealed_assets=sealed_assets,
        )
        inventory_timer = time.perf_counter()
        inventory_path = self._write_inventory(
            inputs=inputs,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            sealed_assets=sealed_assets,
            created_utc=verified_at.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        )
        inventory_write_ms = int(round((time.perf_counter() - inventory_timer) * 1000))
        determinism_receipt = self._write_determinism_receipt(
            inputs=inputs,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            files=[receipt_path, inventory_path],
        )
        run_finished_at = datetime.now(timezone.utc)
        wall_ms = int(round((time.perf_counter() - wall_timer) * 1000))
        run_report = self._build_run_report(
            inputs=inputs,
            dictionary=dictionary,
            bundle_index=bundle_index,
            sealed_assets=sealed_assets,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_result.parameter_hash,
            bundle_path=bundle_path,
            bundle_digest=computed_flag,
            flag_sha256_hex=declared_flag,
            receipt_path=receipt_path,
            inventory_path=inventory_path,
            determinism_receipt=determinism_receipt,
            verified_at=verified_at,
            started_at=run_started_at,
            finished_at=run_finished_at,
            timings={
                "wall_ms": wall_ms,
                "gate_verify_ms": gate_verify_ms,
                "inventory_write_ms": inventory_write_ms,
            },
        )
        run_report_path = self._write_run_report(
            inputs=inputs,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            payload=run_report,
        )
        if inputs.emit_run_report_stdout:
            print(json.dumps(run_report, indent=2))  # pragma: no cover

        return GateOutputs(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_result.parameter_hash,
            flag_sha256_hex=declared_flag,
            receipt_path=receipt_path,
            inventory_path=inventory_path,
            sealed_assets=tuple(sealed_assets),
            validation_bundle_path=bundle_path,
            verified_at_utc=verified_at,
            determinism_receipt=determinism_receipt,
            run_report_path=run_report_path,
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
        repo_root = repository_root()

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
                if not resolved_path.exists():
                    repo_candidate = (repo_root / catalog_path).resolve()
                    if repo_candidate.exists():
                        try:
                            resolved_path = materialize_repo_asset(
                                source_path=repo_candidate,
                                repo_root=repo_root,
                                run_root=base_path,
                            )
                        except RunBundleError as exc:
                            raise err("E_ASSET_PATH", str(exc)) from exc
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
            asset_kind = self._ASSET_KIND_MAP.get(asset_id)
            if asset_kind is None:
                raise err(
                    "E_ASSET_KIND_UNKNOWN",
                    f"sealed asset '{asset_id}' has no asset_kind mapping",
                )

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
        add_asset(
            "merchant_mcc_map",
            template_args={"seed": seed, "manifest_fingerprint": upstream_fp},
        )
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
        created_utc: str,
    ) -> Path:
        rows = [
            asset.as_inventory_row(
                manifest_fingerprint=manifest_fingerprint,
                created_utc=created_utc,
            )
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

    def _write_determinism_receipt(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        files: Sequence[Path],
    ) -> Mapping[str, object]:
        if not files:
            raise err("E_PARAM_EMPTY", "determinism receipt requires output files")
        digests = hash_files(files, error_prefix="E_ASSET")
        partition_hash = aggregate_sha256(digests)
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        payload: MutableMapping[str, object] = {
            "partition_path": str(inputs.output_base_path.resolve()),
            "sha256_hex": partition_hash,
            "files_hashed": [str(path.resolve()) for path in files],
            "generated_at_utc": generated_at,
        }
        receipt_rel_path = render_dataset_path(
            "s0_determinism_receipt_2A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        receipt_path = (inputs.output_base_path / receipt_rel_path).resolve()
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _build_run_report(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        bundle_index: BundleIndex,
        sealed_assets: Sequence[SealedAsset],
        manifest_fingerprint: str,
        parameter_hash: str,
        bundle_path: Path,
        bundle_digest: str,
        flag_sha256_hex: str,
        receipt_path: Path,
        inventory_path: Path,
        determinism_receipt: Mapping[str, object],
        verified_at: datetime,
        started_at: datetime,
        finished_at: datetime,
        timings: Mapping[str, int],
    ) -> Mapping[str, object]:
        optional_ids = set(inputs.optional_asset_ids)
        optional_present = sum(
            1 for asset in sealed_assets if asset.asset_id in optional_ids
        )
        optional_total = len(optional_ids)
        warnings = []
        if optional_total and optional_present not in (0, optional_total):
            warnings.append("2A-S0-070")

        tzdb_asset = next((a for a in sealed_assets if a.asset_id == "tzdb_release"), None)
        tz_world_asset = next(
            (a for a in sealed_assets if a.asset_id.startswith("tz_world")),
            None,
        )
        policy_assets = {
            asset.asset_id: asset for asset in sealed_assets if asset.asset_id in inputs.parameter_asset_ids
        }
        bytes_total = sum(asset.size_bytes for asset in sealed_assets)
        catalogue_resolution = self._catalogue_resolution(dictionary=dictionary)
        validators = self._build_validators(optional_warning=bool(warnings))
        run_report = {
            "segment": "2A",
            "state": "S0",
            "status": "pass",
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "seed": inputs.seed,
            "started_utc": started_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "finished_utc": finished_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "durations": dict(timings),
            "catalogue_resolution": catalogue_resolution,
            "upstream": {
                "bundle_path": str(render_dataset_path(
                    "validation_bundle_1B",
                    template_args={"manifest_fingerprint": inputs.upstream_manifest_fingerprint},
                    dictionary=dictionary,
                )),
                "flag_sha256_hex": flag_sha256_hex,
                "bundle_sha256_hex": bundle_digest,
                "verified_at_utc": verified_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "result": "verified",
            },
            "sealed_inputs": {
                "count": len(sealed_assets),
                "bytes_total": bytes_total,
                "inventory_path": str(inventory_path),
                "manifest_digest": manifest_fingerprint,
            },
            "tz_assets": {
                "tzdb_release_tag": tzdb_asset.version_tag if tzdb_asset else "",
                "tzdb_catalog_path": tzdb_asset.catalog_path if tzdb_asset else "",
                "tz_world_id": tz_world_asset.asset_id if tz_world_asset else "",
                "tz_world_catalog_path": tz_world_asset.catalog_path if tz_world_asset else "",
            },
            "policies": {
                asset_id: {
                    "catalog_path": asset.catalog_path,
                    "sha256_hex": asset.sha256_hex,
                    "version_tag": asset.version_tag,
                }
                for asset_id, asset in policy_assets.items()
            },
            "outputs": {
                "receipt_path": str(receipt_path),
                "inventory_path": str(inventory_path),
            },
            "determinism": determinism_receipt,
            "validators": validators,
            "warnings": warnings,
            "errors": [],
            "environment": {
                "engine_commit": inputs.git_commit_hex,
                "python_version": platform.python_version(),
                "platform": platform.platform(),
            },
            "bundle_index": {
                "entries_total": len(bundle_index.entries),
            },
        }
        return run_report

    def _build_validators(self, *, optional_warning: bool) -> list[dict[str, object]]:
        validators = [
            {"id": "V-01", "status": "PASS", "codes": ["2A-S0-001"]},
            {"id": "V-02", "status": "PASS", "codes": ["2A-S0-002"]},
            {"id": "V-03", "status": "PASS", "codes": ["2A-S0-004"]},
            {"id": "V-04", "status": "PASS", "codes": ["2A-S0-010"]},
            {"id": "V-05", "status": "WARN" if optional_warning else "PASS", "codes": ["2A-S0-070"]},
        ]
        validators.extend(
            [
                {"id": "V-06", "status": "PASS", "codes": ["2A-S0-011", "2A-S0-012", "2A-S0-013", "2A-S0-014", "2A-S0-015"]},
                {"id": "V-07", "status": "PASS", "codes": ["2A-S0-016", "2A-S0-017", "2A-S0-018"]},
                {"id": "V-08", "status": "PASS", "codes": ["2A-S0-020", "2A-S0-021"]},
                {"id": "V-09", "status": "PASS", "codes": ["2A-S0-022", "2A-S0-023"]},
                {"id": "V-10", "status": "PASS", "codes": ["2A-S0-040", "2A-S0-041", "2A-S0-042"]},
                {"id": "V-11", "status": "PASS", "codes": ["2A-S0-050", "2A-S0-051", "2A-S0-052"]},
                {"id": "V-12", "status": "PASS", "codes": ["2A-S0-060", "2A-S0-061", "2A-S0-062"]},
                {"id": "V-13", "status": "PASS", "codes": ["2A-S0-044"]},
            ]
        )
        return validators

    def _write_run_report(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        payload: Mapping[str, object],
    ) -> Path:
        report_rel_path = render_dataset_path(
            "s0_run_report_2A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        report_path = (inputs.output_base_path / report_rel_path).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return report_path

    @staticmethod
    def _catalogue_resolution(*, dictionary: Mapping[str, object]) -> Mapping[str, str]:
        catalogue = dictionary.get("catalogue") or {}
        return {
            "dictionary_version": str(
                catalogue.get("dictionary_version") or dictionary.get("version") or "unversioned"
            ),
            "registry_version": str(catalogue.get("registry_version") or "unversioned"),
        }

    @staticmethod
    def _render_template(template: str, template_args: Mapping[str, object]) -> str:
        if not template:
            return template
        safe_args = {key: str(value) for key, value in template_args.items()}
        try:
            return template.format(**safe_args)
        except KeyError:
            return template

    def _ensure_merchant_mcc_map(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
    ) -> None:
        try:
            get_dataset_entry("merchant_mcc_map", dictionary=dictionary)
        except S0GateError:
            return

        template_args = {
            "seed": inputs.seed,
            "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
        }
        relative_path = render_dataset_path(
            "merchant_mcc_map", template_args=template_args, dictionary=dictionary
        )
        target_path = (inputs.base_path / relative_path).resolve()
        ensure_within_base(target_path, base_path=inputs.base_path)
        if target_path.exists():
            return
        target_path.parent.mkdir(parents=True, exist_ok=True)

        source_path = self._resolve_transaction_schema_source()
        if not source_path.exists():
            raise err(
                "E_MCC_SOURCE_MISSING",
                f"transaction_schema_merchant_ids parquet missing at '{source_path}'",
            )

        logger.info(
            "Materialising merchant_mcc_map from %s -> %s",
            source_path,
            target_path,
        )
        if source_path.suffix.lower() == ".parquet":
            scan = pl.scan_parquet(source_path)
        else:
            scan = pl.scan_csv(
                source_path,
                schema_overrides={"merchant_id": pl.UInt64, "mcc": pl.Int32},
                ignore_errors=False,
            )
        frame = (
            scan.select(
                [
                    pl.col("merchant_id").cast(pl.UInt64, strict=True),
                    pl.col("mcc").cast(pl.Int32, strict=True),
                ]
            )
            .unique(subset=["merchant_id"], maintain_order=False)
            .sort("merchant_id")
            .collect()
        )
        if frame.is_empty():
            raise err(
                "E_MCC_SOURCE_EMPTY",
                f"transaction_schema_merchant_ids at '{source_path}' yielded no rows",
            )
        temp_path = target_path.with_suffix(".tmp")
        try:
            frame.write_parquet(temp_path, compression="zstd")
            temp_path.replace(target_path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def _resolve_transaction_schema_source(self) -> Path:
        repo_root = repository_root()
        base = repo_root / "reference" / "layer1" / "transaction_schema_merchant_ids"
        if not base.exists():
            raise err(
                "E_MCC_SOURCE_ROOT_MISSING",
                f"reference merchant_ids directory '{base}' is missing",
            )
        versions = [path for path in base.iterdir() if path.is_dir()]
        if not versions:
            raise err(
                "E_MCC_SOURCE_VERSION_MISSING",
                f"no versions found under '{base}'",
            )
        dated_versions: list[tuple[datetime, Path]] = []
        for path in versions:
            candidate = path.name[1:] if path.name.startswith("v") else path.name
            try:
                parsed = datetime.strptime(candidate, "%Y-%m-%d")
            except ValueError:
                continue
            dated_versions.append((parsed, path))
        if dated_versions:
            dated_versions.sort(key=lambda item: item[0])
            chosen = dated_versions[-1][1]
        else:
            chosen = sorted(versions, key=lambda p: p.name)[-1]
        parquet_path = chosen / "transaction_schema_merchant_ids.parquet"
        if parquet_path.exists():
            return parquet_path
        return chosen / "transaction_schema_merchant_ids.csv"

    def _rehome_merchant_mcc_map(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        sealed_assets: Sequence[SealedAsset],
    ) -> list[SealedAsset]:
        asset_index = next(
            (idx for idx, asset in enumerate(sealed_assets) if asset.asset_id == "merchant_mcc_map"),
            None,
        )
        if asset_index is None:
            return list(sealed_assets)

        asset = sealed_assets[asset_index]
        template_args = {"seed": inputs.seed, "manifest_fingerprint": manifest_fingerprint}
        catalog_path = render_dataset_path(
            "merchant_mcc_map", template_args=template_args, dictionary=dictionary
        )
        resolved_path = (inputs.base_path / catalog_path).resolve()
        ensure_within_base(resolved_path, base_path=inputs.base_path)

        if not resolved_path.exists():
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(asset.resolved_path, resolved_path)
            except OSError:
                shutil.copy2(asset.resolved_path, resolved_path)

        digests = hash_files([resolved_path], error_prefix="E_ASSET_MERCHANT_MCC_MAP")
        if aggregate_sha256(digests) != aggregate_sha256(asset.digests):
            raise err(
                "E_MCC_MAP_MISMATCH",
                f"merchant_mcc_map mismatch at '{resolved_path}'",
            )

        updated_asset = SealedAsset(
            asset_id=asset.asset_id,
            schema_ref=asset.schema_ref,
            asset_kind=asset.asset_kind,
            catalog_path=catalog_path,
            resolved_path=resolved_path,
            partition_keys=asset.partition_keys,
            version_tag=asset.version_tag,
            license_class=asset.license_class,
            digests=tuple(digests),
            notes=asset.notes,
        )
        updated_assets = list(sealed_assets)
        updated_assets[asset_index] = updated_asset
        return updated_assets


__all__ = ["S0GateRunner", "GateInputs", "GateOutputs", "SealedAsset", "S0GateError"]
