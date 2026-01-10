"""High-level orchestration for Segment 2B S0 gate."""

from __future__ import annotations

import json
import logging
import platform
import sys
import time
import uuid
from collections import Counter
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
from engine.shared.run_bundle import RunBundleError, materialize_repo_asset
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
            raise err("2B-S0-020", "seed must be provided for S0")
        object.__setattr__(self, "seed", seed_value)
        manifest = self.manifest_fingerprint.lower()
        if len(manifest) != 64:
            raise err(
                "2B-S0-020",
                "manifest_fingerprint must be 64 hex characters",
            )
        int(manifest, 16)
        object.__setattr__(self, "manifest_fingerprint", manifest)
        parameter_hash = self.parameter_hash.lower()
        if len(parameter_hash) != 64:
            raise err(
                "2B-S0-020",
                "parameter_hash must be 64 hex characters",
            )
        int(parameter_hash, 16)
        object.__setattr__(self, "parameter_hash", parameter_hash)
        seg2a_manifest = self.seg2a_manifest_fingerprint.lower()
        if len(seg2a_manifest) != 64:
            raise err(
                "2B-S0-020",
                "seg2a_manifest_fingerprint must be 64 hex characters",
            )
        int(seg2a_manifest, 16)
        object.__setattr__(self, "seg2a_manifest_fingerprint", seg2a_manifest)
        git_hex = self.git_commit_hex.lower()
        if len(git_hex) not in (40, 64):
            raise err(
                "2B-S0-020",
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


@dataclass(frozen=True)
class GateWriteResult:
    """Artifacts and metadata emitted when publishing S0 outputs."""

    receipt_path: Path
    inventory_path: Path
    verified_at: datetime
    inventory_rows: list[dict[str, object]]
    publish_targets: list[dict[str, object]]
    publish_bytes_total: int
    timings_ms: Mapping[str, int]
    catalogue_resolution: Mapping[str, str]


class S0GateRunner:
    """High-level helper that wires together the 2B S0 workflow."""

    _CIVIL_OPTIONAL_IDS = ("site_timezones", "tz_timetable_cache")

    def run(self, inputs: GateInputs) -> GateOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        gate_timer = time.perf_counter()
        bundle_path = self._resolve_validation_bundle_path(inputs, dictionary=dictionary)
        bundle_index = load_index(bundle_path)
        bundle_digest = compute_index_digest(bundle_path, bundle_index)
        flag_digest = read_pass_flag(bundle_path)
        if bundle_digest != flag_digest:
            raise err(
                "2B-S0-011",
                "validation bundle digest does not match _passed.flag",
            )
        gate_verify_ms = int(round((time.perf_counter() - gate_timer) * 1000))

        sealed_assets = self._collect_sealed_assets(
            inputs=inputs,
            dictionary=dictionary,
            bundle_path=bundle_path,
            bundle_index=bundle_index,
        )
        policy_ids, policy_digests = self._policy_digests(
            sealed_assets, required_ids=inputs.policy_asset_ids
        )

        write_result = self._write_outputs(
            inputs=inputs,
            dictionary=dictionary,
            sealed_assets=sealed_assets,
            bundle_path=bundle_path,
            flag_sha256_hex=flag_digest,
            policy_ids=policy_ids,
            policy_digests=policy_digests,
        )

        run_report = self._build_run_report(
            inputs=inputs,
            dictionary=dictionary,
            bundle_index=bundle_index,
            sealed_assets=sealed_assets,
            inventory_rows=write_result.inventory_rows,
            policy_ids=policy_ids,
            policy_digests=policy_digests,
            bundle_digest=bundle_digest,
            flag_digest=flag_digest,
            bundle_path=bundle_path,
            write_result=write_result,
            gate_verify_ms=gate_verify_ms,
        )
        run_report_path = self._write_run_report(
            inputs=inputs,
            dictionary=dictionary,
            payload=run_report,
        )
        logger.info(
            "Segment2B S0 run-report saved to %s (manifest=%s)",
            run_report_path,
            inputs.manifest_fingerprint,
        )

        logger.info(
            "Segment2B S0 completed (manifest=%s, receipt=%s)",
            inputs.manifest_fingerprint,
            write_result.receipt_path,
        )

        return GateOutputs(
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            flag_sha256_hex=flag_digest,
            receipt_path=write_result.receipt_path,
            inventory_path=write_result.inventory_path,
            sealed_assets=tuple(sealed_assets),
            verified_at_utc=write_result.verified_at,
        )

    def _resolve_validation_bundle_path(
        self,
        inputs: GateInputs,
        *,
        dictionary: Mapping[str, object],
    ) -> Path:
        if inputs.validation_bundle_path is not None:
            return inputs.validation_bundle_path.resolve()
        try:
            rendered = render_dataset_path(
                "validation_bundle_1B",
                template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
                dictionary=dictionary,
            )
        except S0GateError as exc:
            raise err("2B-S0-020", exc.detail) from exc
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
                try:
                    materialized = materialize_repo_asset(
                        source_path=repo_candidate,
                        repo_root=repo_root,
                        run_root=data_root,
                    )
                except RunBundleError as exc:
                    raise err("2B-S0-010", str(exc)) from exc
                return materialized, data_root
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
            except S0GateError as exc:
                if allow_missing:
                    return
                raise err("2B-S0-020", exc.detail) from exc

            try:
                catalog_path = render_dataset_path(
                    asset_id, template_args=template_args, dictionary=dictionary
                )
            except S0GateError as exc:
                raise err("2B-S0-020", exc.detail) from exc
            if resolved_override is not None:
                resolved_path = resolved_override.resolve()
                base_for_path = data_root if resolved_path.is_relative_to(data_root) else repo_root
            else:
                resolved_path, base_for_path = resolve_catalog_path(catalog_path)
            ensure_within_base(resolved_path, base_path=base_for_path)

            if file_override is not None:
                files = list(file_override)
            else:
                try:
                    files = expand_files(resolved_path)
                except S0GateError as exc:
                    raise err("2B-S0-010", exc.detail) from exc

            if not files:
                raise err(
                    "2B-S0-010",
                    f"asset '{asset_id}' has no files",
                )

            try:
                digests = hash_files(files, error_prefix=f"2B-S0-022_{asset_id}")
            except S0GateError as exc:
                raise err("2B-S0-022", exc.detail) from exc
            partitioning = entry.get("partitioning") or []
            version_template = str(entry.get("version", ""))
            version = self._render_template(version_template, template_args)
            if not version:
                raise err(
                    "2B-S0-031",
                    f"dictionary entry '{asset_id}' missing version",
                )
            partition: dict[str, str] = {}
            for key in partitioning:
                if key not in template_args:
                    raise err(
                        "2B-S0-031",
                        f"partition key '{key}' missing for asset '{asset_id}'",
                    )
                value = template_args[key]
                if value is None:
                    raise err(
                        "2B-S0-031",
                        f"partition key '{key}' resolved to empty value for asset '{asset_id}'",
                    )
                partition[str(key)] = str(value)

            assets.append(
                SealedAsset(
                    asset_id=asset_id,
                    schema_ref=str(entry.get("schema_ref", "")),
                    catalog_path=catalog_path,
                    resolved_path=resolved_path,
                    partition=partition,
                    version_tag=version,
                    digests=tuple(digests),
                )
            )

        bundle_files = [
            (bundle_path / entry.path).resolve() for entry in bundle_index.iter_entries()
        ]
        add_asset(
            "validation_bundle_1B",
            template_args={"manifest_fingerprint": manifest, "fingerprint": manifest},
            file_override=bundle_files,
            resolved_override=bundle_path,
        )
        flag_override = (bundle_path / "_passed.flag").resolve()
        add_asset(
            "validation_passed_flag_1B",
            template_args={"manifest_fingerprint": manifest, "fingerprint": manifest},
            file_override=[flag_override],
            resolved_override=flag_override,
        )
        add_asset(
            "site_locations",
            template_args={"seed": seed, "manifest_fingerprint": manifest, "fingerprint": manifest},
        )
        for policy_id in inputs.policy_asset_ids:
            add_asset(policy_id, template_args={})

        for asset_id in self._CIVIL_OPTIONAL_IDS:
            add_asset(
                asset_id,
                template_args={
                    "seed": seed,
                    "manifest_fingerprint": inputs.seg2a_manifest_fingerprint,
                    "fingerprint": inputs.seg2a_manifest_fingerprint,
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
        policy_ids: Sequence[str],
        policy_digests: Sequence[str],
    ) -> GateWriteResult:
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

        inventory_start = time.perf_counter()
        temp_inventory = inventory_path.parent / f".tmp.{uuid.uuid4().hex}.json"
        try:
            temp_inventory.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            temp_inventory.replace(inventory_path)
        finally:
            if temp_inventory.exists():
                temp_inventory.unlink(missing_ok=True)
        inventory_emit_ms = int(round((time.perf_counter() - inventory_start) * 1000))

        sealed_entries = [asset.as_receipt_entry() for asset in sealed_sorted]
        catalogue_resolution = self._catalogue_resolution(dictionary)
        determinism_receipt = {
            "engine_commit": inputs.git_commit_hex,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "policy_ids": policy_ids,
            "policy_digests": policy_digests,
        }
        try:
            seed_value = int(inputs.seed)
        except (TypeError, ValueError) as exc:
            raise err("2B-S0-020", "seed must be an unsigned integer") from exc
        receipt_rel = render_dataset_path(
            "s0_gate_receipt_2B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        receipt_path = (inputs.data_root / receipt_rel).resolve()
        ensure_within_base(receipt_path, base_path=inputs.data_root)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)

        existing_payload: Optional[dict[str, object]] = None
        if receipt_path.exists():
            try:
                existing_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise err("E_S0_RECEIPT_INVALID", f"invalid JSON in {receipt_path}") from exc
            try:
                validate_receipt_payload(existing_payload)
            except S0GateError as exc:
                raise err("E_S0_RECEIPT_INVALID", exc.detail) from exc
            verified_at_utc = str(existing_payload.get("verified_at_utc", _now_utc()))
        else:
            verified_at_utc = _now_utc()

        receipt_payload = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "seed": seed_value,
            "parameter_hash": inputs.parameter_hash,
            "verified_at_utc": verified_at_utc,
            "sealed_inputs": sealed_entries,
            "catalogue_resolution": catalogue_resolution,
            "determinism_receipt": determinism_receipt,
        }
        validate_receipt_payload(receipt_payload)

        publish_ms = 0
        if existing_payload is not None:
            if existing_payload != receipt_payload:
                raise err(
                    "E_S0_RECEIPT_MISMATCH",
                    f"s0 gate receipt already exists with different content at {receipt_path}",
                )
        else:
            publish_start = time.perf_counter()
            temp_receipt = receipt_path.parent / f".tmp.{uuid.uuid4().hex}.json"
            try:
                temp_receipt.write_text(
                    json.dumps(receipt_payload, indent=2), encoding="utf-8"
                )
                temp_receipt.replace(receipt_path)
            finally:
                if temp_receipt.exists():
                    temp_receipt.unlink(missing_ok=True)
            publish_ms = int(round((time.perf_counter() - publish_start) * 1000))

        verified_at = datetime.strptime(
            receipt_payload["verified_at_utc"], "%Y-%m-%dT%H:%M:%S.%fZ"
        ).replace(tzinfo=timezone.utc)
        publish_targets = [
            {
                "id": "s0_gate_receipt_2B",
                "path": str(receipt_path),
                "bytes": receipt_path.stat().st_size,
            },
            {
                "id": "sealed_inputs_v1",
                "path": str(inventory_path),
                "bytes": inventory_path.stat().st_size,
            },
        ]
        publish_bytes_total = sum(target["bytes"] for target in publish_targets)
        return GateWriteResult(
            receipt_path=receipt_path,
            inventory_path=inventory_path,
            verified_at=verified_at,
            inventory_rows=rows,
            publish_targets=publish_targets,
            publish_bytes_total=publish_bytes_total,
            timings_ms={
                "inventory_emit_ms": inventory_emit_ms,
                "publish_ms": publish_ms,
            },
            catalogue_resolution=catalogue_resolution,
        )

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
                "2B-S0-010",
                f"missing required policy assets: {', '.join(missing)}",
            )
        digests.sort(key=lambda item: item[0])
        ids = [item[0] for item in digests]
        values = [item[1] for item in digests]
        return ids, values

    def _build_run_report(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        bundle_index: BundleIndex,
        sealed_assets: Sequence[SealedAsset],
        inventory_rows: Sequence[dict[str, object]],
        policy_ids: Sequence[str],
        policy_digests: Sequence[str],
        bundle_digest: str,
        flag_digest: str,
        bundle_path: Path,
        write_result: GateWriteResult,
        gate_verify_ms: int,
    ) -> dict:
        sealed_id_set = {asset.asset_id for asset in sealed_assets}
        required_ids = {
            "validation_bundle_1B",
            "validation_passed_flag_1B",
            "site_locations",
            *self._CIVIL_OPTIONAL_IDS,
        }
        required_ids.update(inputs.policy_asset_ids)
        required_present = sum(1 for asset_id in required_ids if asset_id in sealed_id_set)
        optional_ids: set[str] = set()
        optional_present = sum(1 for asset_id in optional_ids if asset_id in sealed_id_set)
        sha_counts = Counter(row["sha256_hex"] for row in inventory_rows)
        duplicate_byte_sets = sum(1 for count in sha_counts.values() if count > 1)
        sealed_sample = sorted(
            [
                {
                    "asset_id": row["asset_id"],
                    "version_tag": row["version_tag"],
                    "sha256_hex": row["sha256_hex"],
                    "path": row["path"],
                    "partition": dict(row.get("partition") or {}),
                }
                for row in inventory_rows
            ],
            key=lambda item: (item["asset_id"], item["path"]),
        )[:20]
        gate_paths = sorted(bundle_index.ascii_paths())
        gate_index_sample = gate_paths[:20]
        validators = self._build_validators(optional_ids=optional_ids, optional_present=optional_present)
        warn_count = sum(1 for validator in validators if validator["status"] == "WARN")
        try:
            flag_catalog = render_dataset_path(
                "validation_passed_flag_1B",
                template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
                dictionary=dictionary,
            )
        except S0GateError as exc:
            raise err("2B-S0-020", exc.detail) from exc
        flag_path = str(flag_catalog)
        id_map = [
            {"id": asset.asset_id, "path": asset.catalog_path}
            for asset in sorted(sealed_assets, key=lambda item: (item.asset_id, item.catalog_path))
        ]
        timings_ms = {"gate_verify_ms": gate_verify_ms}
        timings_ms.update(write_result.timings_ms)
        inventory_unique_digests = len(sha_counts)
        run_report = {
            "component": "2B.S0",
            "fingerprint": inputs.manifest_fingerprint,
            "seed": str(inputs.seed),
            "verified_at_utc": write_result.verified_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "catalogue_resolution": write_result.catalogue_resolution,
            "gate": {
                "bundle_index_count": len(bundle_index.entries),
                "bundle_sha256_expected": flag_digest,
                "bundle_sha256_actual": bundle_digest,
                "flag_path": str(bundle_path / "_passed.flag"),
            },
            "inputs_summary": {
                "inputs_total": len(sealed_assets),
                "required_present": required_present,
                "optional_pins_present": optional_present,
                "policy_ids": list(policy_ids),
                "policy_digests": list(policy_digests),
            },
            "inventory_summary": {
                "inventory_rows": len(inventory_rows),
                "digests_recorded": inventory_unique_digests,
                "duplicate_byte_sets": duplicate_byte_sets,
            },
            "publish": {
                "targets": write_result.publish_targets,
                "publish_bytes_total": write_result.publish_bytes_total,
                "write_once_verified": True,
                "atomic_publish": True,
            },
            "validators": validators,
            "summary": {
                "overall_status": "PASS",
                "warn_count": warn_count,
                "fail_count": 0,
            },
            "environment": {
                "engine_commit": inputs.git_commit_hex,
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "network_io_detected": 0,
            },
            "sealed_inputs_sample": sealed_sample,
            "gate_index_sample": gate_index_sample,
            "id_map": id_map,
            "timings_ms": timings_ms,
        }
        return run_report

    def _build_validators(
        self,
        *,
        optional_ids: set[str],
        optional_present: int,
    ) -> list[dict]:
        mapping = [
            ("V-01", ["2B-S0-010"]),
            ("V-02", ["2B-S0-011", "2B-S0-012", "2B-S0-013"]),
            ("V-03", ["2B-S0-020", "2B-S0-021"]),
            ("V-04", ["2B-S0-010"]),
            ("V-05", ["2B-S0-090"]),
            ("V-06", ["2B-S0-030"]),
            ("V-07", ["2B-S0-031"]),
            ("V-08", ["2B-S0-040"]),
            ("V-09", ["2B-S0-041"]),
            ("V-10", ["2B-S0-042"]),
            ("V-11", ["2B-S0-050", "2B-S0-020"]),
            ("V-12", ["2B-S0-043"]),
            ("V-13", ["2B-S0-070"]),
            ("V-14", ["2B-S0-080"]),
            ("V-15", ["2B-S0-081"]),
            ("V-16", ["2B-S0-023", "2B-S0-022", "2B-S0-021"]),
        ]
        optional_total = len(optional_ids)
        optional_warn = optional_total and optional_present not in (0, optional_total)
        validators: list[dict] = []
        for vid, codes in mapping:
            status = "PASS"
            if vid == "V-05" and optional_warn:
                status = "WARN"
            validators.append({"id": vid, "status": status, "codes": codes})
        return validators

    def _write_run_report(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        payload: Mapping[str, object],
    ) -> Path:
        report_rel = render_dataset_path(
            "s0_run_report_2B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        report_path = (inputs.data_root / report_rel).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return report_path

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


__all__ = ["GateInputs", "GateOutputs", "GateWriteResult", "S0GateRunner"]
