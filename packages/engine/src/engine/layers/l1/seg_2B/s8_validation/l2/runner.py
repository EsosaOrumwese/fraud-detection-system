"""Segment 2B state-8 validation bundle runner."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional, Sequence

from jsonschema import Draft202012Validator, ValidationError

from ...shared.dictionary import (
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
    repository_root,
)
from ...shared.receipt import (
    GateReceiptSummary,
    SealedInputRecord,
    load_gate_receipt,
    load_sealed_inputs_inventory,
)
from ...shared.schema import load_schema
from ...s0_gate.exceptions import err

logger = logging.getLogger(__name__)

POLICY_IDS: tuple[str, ...] = (
    "alias_layout_policy_v1",
    "route_rng_policy_v1",
    "virtual_edge_policy_v1",
)
PLAN_DATASETS: tuple[str, ...] = (
    "s2_alias_index",
    "s3_day_effects",
    "s4_group_weights",
)


@dataclass(frozen=True)
class S8ValidationInputs:
    """Configuration for executing Segment 2B S8."""

    data_root: Path
    manifest_fingerprint: str
    dictionary_path: Optional[Path] = None
    workspace_root: Optional[Path] = None
    emit_summary_stdout: bool = True

    def __post_init__(self) -> None:
        data_root = self.data_root.expanduser().resolve()
        object.__setattr__(self, "data_root", data_root)
        manifest = self._validate_hex64(self.manifest_fingerprint, field="manifest_fingerprint")
        object.__setattr__(self, "manifest_fingerprint", manifest)

    @staticmethod
    def _validate_hex64(value: str, *, field: str) -> str:
        lowered = value.lower()
        if len(lowered) != 64:
            raise err(
                "E_S8_INVALID_HEX",
                f"{field} must be 64 hex characters",
            )
        int(lowered, 16)
        return lowered


@dataclass(frozen=True)
class S8ValidationResult:
    """Structured result emitted by the S8 runner."""

    manifest_fingerprint: str
    bundle_path: Path
    index_path: Path
    flag_path: Path
    bundle_digest: str
    seeds: tuple[str, ...]
    run_report_path: Path


class S8ValidationRunner:
    """Assemble the Segment 2B validation bundle and `_passed.flag`."""

    REPORT_FILENAME = "s7_audit_report.json"

    def run(self, config: S8ValidationInputs) -> S8ValidationResult:
        dictionary = load_dictionary(config.dictionary_path)
        receipt = load_gate_receipt(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        sealed_inputs = load_sealed_inputs_inventory(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        policy_records = self._resolve_policy_records(sealed_inputs)
        seeds = self._discover_required_seeds(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        reports = {
            seed: self._load_s7_report(
                base_path=config.data_root,
                seed=seed,
                manifest_fingerprint=config.manifest_fingerprint,
                dictionary=dictionary,
            )
            for seed in seeds
        }

        workspace = self._prepare_workspace(config)
        bundle_dir = workspace
        try:
            self._stage_bundle(
                bundle_dir=bundle_dir,
                config=config,
                receipt=receipt,
                policy_records=policy_records,
                seeds=seeds,
                reports=reports,
                dictionary=dictionary,
                data_root=config.data_root,
            )
            index_entries = self._build_index(bundle_dir=bundle_dir)
            bundle_digest = self._write_pass_flag(bundle_dir=bundle_dir, index_entries=index_entries)
            self._validate_index_schema(index_entries=index_entries)
            self._validate_flag(bundle_dir=bundle_dir)

            bundle_path = self._publish_bundle(
                bundle_dir=bundle_dir,
                config=config,
                dictionary=dictionary,
            )
            index_path = bundle_path / "index.json"
            flag_path = bundle_path / "_passed.flag"
            run_report_path = self._write_run_report(
                data_root=config.data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                bundle_path=bundle_path,
                index_path=index_path,
                flag_path=flag_path,
                seeds=tuple(seeds),
                bundle_digest=bundle_digest,
                receipt=receipt,
                index_entries=index_entries,
            )
            result = S8ValidationResult(
                manifest_fingerprint=config.manifest_fingerprint,
                bundle_path=bundle_path,
                index_path=index_path,
                flag_path=flag_path,
                bundle_digest=bundle_digest,
                seeds=tuple(seeds),
                run_report_path=run_report_path,
            )
            if config.emit_summary_stdout:
                print(
                    f"Segment2B S8 validation bundle → {bundle_path} "
                    f"(seeds={len(seeds)}, digest={bundle_digest})"
                )
            logger.info(
                "Segment2B S8 published bundle (manifest=%s, seeds=%s, bundle=%s)",
                config.manifest_fingerprint,
                ",".join(seeds),
                bundle_path,
            )
            return result
        finally:
            if bundle_dir.exists() and not self._bundle_is_published(bundle_dir, config, dictionary):
                shutil.rmtree(bundle_dir, ignore_errors=True)

    # ------------------------------------------------------------------ prerequisites

    def _resolve_policy_records(
        self,
        sealed_inputs: Sequence[SealedInputRecord],
    ) -> Mapping[str, SealedInputRecord]:
        records: MutableMapping[str, SealedInputRecord] = {}
        for record in sealed_inputs:
            if record.asset_id in POLICY_IDS:
                records[record.asset_id] = record
        missing = sorted(asset_id for asset_id in POLICY_IDS if asset_id not in records)
        if missing:
            raise err(
                "E_S8_POLICY_MISSING",
                f"sealed_inputs_v1 missing policy assets: {', '.join(missing)}",
            )
        return records

    def _discover_required_seeds(
        self,
        *,
        base_path: Path,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> tuple[str, ...]:
        seed_sets = []
        for dataset_id in PLAN_DATASETS:
            seeds = self._dataset_seeds(
                base_path=base_path,
                dataset_id=dataset_id,
                manifest_fingerprint=manifest_fingerprint,
                dictionary=dictionary,
            )
            if not seeds:
                raise err(
                    "E_S8_SEED_DISCOVERY",
                    f"dataset '{dataset_id}' has no seed partitions for manifest {manifest_fingerprint}",
                )
            seed_sets.append(seeds)
        intersection = set(seed_sets[0])
        for extra in seed_sets[1:]:
            intersection &= extra
        if not intersection:
            raise err(
                "E_S8_SEED_INTERSECTION_EMPTY",
                "intersection of seeds across s2/s3/s4 datasets is empty",
            )
        return tuple(sorted(intersection))

    def _dataset_seeds(
        self,
        *,
        base_path: Path,
        dataset_id: str,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> set[str]:
        pattern = render_dataset_path(
            dataset_id,
            template_args={"seed": "*", "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        seeds: set[str] = set()
        for candidate in base_path.glob(pattern):
            seed_value = self._extract_partition_value(candidate, "seed")
            if seed_value is not None:
                seeds.add(seed_value)
        return seeds

    def _load_s7_report(
        self,
        *,
        base_path: Path,
        seed: str,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> tuple[Mapping[str, object], Path]:
        rel_path = render_dataset_path(
            "s7_audit_report",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        report_path = (base_path / rel_path).resolve()
        if not report_path.exists():
            raise err(
                "E_S8_S7_REPORT_MISSING",
                f"s7_audit_report missing for seed={seed}, manifest={manifest_fingerprint}",
            )
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise err(
                "E_S8_S7_REPORT_INVALID",
                f"s7_audit_report for seed={seed} is not valid JSON: {exc}",
            ) from exc
        schema = load_schema("#/validation/s7_audit_report_v1")
        validator = Draft202012Validator(schema)
        try:
            validator.validate(payload)
        except ValidationError as exc:
            raise err(
                "E_S8_S7_REPORT_INVALID",
                f"s7_audit_report for seed={seed} failed schema validation: {exc.message}",
            ) from exc
        status = (
            payload.get("summary", {}).get("overall_status")
            if isinstance(payload.get("summary"), Mapping)
            else None
        )
        if not status:
            validators = payload.get("validators") or []
            if isinstance(validators, Sequence) and validators:
                status = "PASS" if all(
                    isinstance(item, Mapping) and item.get("status") == "PASS"
                    for item in validators
                ) else "FAIL"
        if status != "PASS":
            raise err(
                "E_S8_S7_REPORT_NOT_PASS",
                f"s7 audit for seed={seed} is not PASS (status={status or 'UNKNOWN'})",
            )
        return payload, report_path

    # ------------------------------------------------------------------ staging

    def _prepare_workspace(self, config: S8ValidationInputs) -> Path:
        root = (
            config.workspace_root.expanduser().resolve()
            if config.workspace_root
            else config.data_root / "tmp" / "segment2b_s8"
        )
        root.mkdir(parents=True, exist_ok=True)
        workspace = root / f"{config.manifest_fingerprint}-{uuid.uuid4().hex}"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _stage_bundle(
        self,
        *,
        bundle_dir: Path,
        config: S8ValidationInputs,
        receipt: GateReceiptSummary,
        policy_records: Mapping[str, SealedInputRecord],
        seeds: Sequence[str],
        reports: Mapping[str, Mapping[str, object]],
        dictionary: Mapping[str, object],
        data_root: Path,
    ) -> None:
        self._stage_reports(bundle_dir=bundle_dir, seeds=seeds, reports=reports)
        self._stage_s0_evidence(
            bundle_dir=bundle_dir,
            manifest_fingerprint=config.manifest_fingerprint,
            data_root=data_root,
            dictionary=dictionary,
        )
        self._stage_policies(
            bundle_dir=bundle_dir,
            policy_records=policy_records,
            data_root=data_root,
        )

    def _stage_reports(
        self,
        *,
        bundle_dir: Path,
        seeds: Sequence[str],
        reports: Mapping[str, tuple[Mapping[str, object], Path]],
    ) -> None:
        reports_root = bundle_dir / "reports"
        for seed in seeds:
            report_dir = reports_root / f"seed={seed}"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / self.REPORT_FILENAME
            _, source_path = reports[seed]
            self._copy_file(source_path, report_path)

    def _stage_s0_evidence(
        self,
        *,
        bundle_dir: Path,
        manifest_fingerprint: str,
        data_root: Path,
        dictionary: Mapping[str, object],
    ) -> None:
        evidence_dir = bundle_dir / "evidence" / "s0"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        receipt_rel = render_dataset_path(
            "s0_gate_receipt_2B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        inventory_rel = render_dataset_path(
            "sealed_inputs_v1",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        self._copy_relative_file(
            source=(data_root / receipt_rel).resolve(),
            destination=evidence_dir / "s0_gate_receipt.json",
        )
        self._copy_relative_file(
            source=(data_root / inventory_rel).resolve(),
            destination=evidence_dir / "sealed_inputs_v1.json",
        )

    def _stage_policies(
        self,
        *,
        bundle_dir: Path,
        policy_records: Mapping[str, SealedInputRecord],
        data_root: Path,
    ) -> None:
        policies_dir = bundle_dir / "evidence" / "refs" / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)
        repo_root = repository_root()
        for asset_id, record in policy_records.items():
            source_path = self._resolve_catalog_path(
                record.catalog_path,
                data_root=data_root,
                repo_root=repo_root,
            )
            digest = self._sha256_file(source_path)
            if digest != record.sha256_hex:
                aggregated = hashlib.sha256(digest.encode("ascii")).hexdigest()
                if aggregated == record.sha256_hex:
                    digest = aggregated
                else:
                    raise err(
                        "E_S8_POLICY_DIGEST",
                        f"sealed digest mismatch for policy '{asset_id}'",
                    )
            destination = policies_dir / Path(record.catalog_path).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            self._copy_file(source_path, destination)

    # ------------------------------------------------------------------ indexing

    def _build_index(self, *, bundle_dir: Path) -> list[dict[str, str]]:
        entries = []
        for path in sorted(
            p for p in bundle_dir.rglob("*") if p.is_file() and p.name != "_passed.flag"
        ):
            relative = path.relative_to(bundle_dir).as_posix()
            digest = self._sha256_file(path)
            entries.append({"path": relative, "sha256_hex": digest})
        index_path = bundle_dir / "index.json"
        index_path.write_text(
            json.dumps(entries, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return entries

    def _write_pass_flag(
        self,
        *,
        bundle_dir: Path,
        index_entries: Sequence[Mapping[str, str]],
    ) -> str:
        digest = hashlib.sha256()
        for entry in sorted(index_entries, key=lambda item: item["path"]):
            target = bundle_dir / entry["path"]
            digest.update(target.read_bytes())
        bundle_digest = digest.hexdigest()
        flag_path = bundle_dir / "_passed.flag"
        flag_path.write_text(f"sha256_hex = {bundle_digest}\n", encoding="utf-8")
        return bundle_digest

    def _validate_index_schema(self, *, index_entries: Sequence[Mapping[str, str]]) -> None:
        schema = load_schema("#/validation/validation_bundle/index_schema")
        validator = Draft202012Validator(schema)
        try:
            validator.validate(index_entries)
        except ValidationError as exc:
            raise err("E_S8_INDEX_SCHEMA", f"index.json failed schema validation: {exc.message}") from exc

    def _validate_flag(self, *, bundle_dir: Path) -> None:
        schema = load_schema("#/validation/passed_flag")
        flag_path = bundle_dir / "_passed.flag"
        validator = Draft202012Validator(schema)
        try:
            validator.validate(flag_path.read_text(encoding="utf-8").strip())
        except ValidationError as exc:
            raise err("E_S8_FLAG_SCHEMA", f"_passed.flag failed schema validation: {exc.message}") from exc

    # ------------------------------------------------------------------ publish

    def _publish_bundle(
        self,
        *,
        bundle_dir: Path,
        config: S8ValidationInputs,
        dictionary: Mapping[str, object],
    ) -> Path:
        target_index_rel = render_dataset_path(
            "validation_bundle_2B",
            template_args={"manifest_fingerprint": config.manifest_fingerprint},
            dictionary=dictionary,
        )
        target_index_path = (config.data_root / target_index_rel).resolve()
        target_dir = target_index_path.parent
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            existing_index = target_index_path.read_bytes()
            new_index = (bundle_dir / "index.json").read_bytes()
            existing_flag = (target_dir / "_passed.flag").read_bytes()
            new_flag = (bundle_dir / "_passed.flag").read_bytes()
            if existing_index != new_index or existing_flag != new_flag:
                raise err(
                    "E_S8_IMMUTABLE_OVERWRITE",
                    "validation bundle already exists and differs from staged output",
                )
            shutil.rmtree(bundle_dir, ignore_errors=True)
            return target_dir
        bundle_dir.replace(target_dir)
        return target_dir

    def _bundle_is_published(
        self,
        bundle_dir: Path,
        config: S8ValidationInputs,
        dictionary: Mapping[str, object],
    ) -> bool:
        target_index_rel = render_dataset_path(
            "validation_bundle_2B",
            template_args={"manifest_fingerprint": config.manifest_fingerprint},
            dictionary=dictionary,
        )
        target_index_path = (config.data_root / target_index_rel).resolve()
        target_dir = target_index_path.parent
        return not bundle_dir.exists() and target_dir.exists()

    def _resolve_run_report_path(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
    ) -> Path:
        return (
            data_root
            / "reports"
            / "l1"
            / "s8_validation"
            / f"fingerprint={manifest_fingerprint}"
            / "run_report.json"
        ).resolve()

    def _write_run_report(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
        bundle_path: Path,
        index_path: Path,
        flag_path: Path,
        seeds: Sequence[str],
        bundle_digest: str,
        receipt: GateReceiptSummary,
        index_entries: Sequence[Mapping[str, str]],
    ) -> Path:
        path = self._resolve_run_report_path(
            data_root=data_root,
            manifest_fingerprint=manifest_fingerprint,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "segment": "2B",
            "state": "S8",
            "manifest_fingerprint": manifest_fingerprint,
            "bundle_path": str(bundle_path),
            "index_path": str(index_path),
            "flag_path": str(flag_path),
            "bundle_digest": bundle_digest,
            "seeds": list(seeds),
            "index_entries": len(index_entries),
            "determinism": dict(receipt.determinism_receipt),
            "catalogue_resolution": dict(receipt.catalogue_resolution),
            "created_utc": receipt.verified_at_utc,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    # ------------------------------------------------------------------ helpers

    def _extract_partition_value(self, path: Path, token: str) -> Optional[str]:
        for part in path.parts:
            if part.startswith(f"{token}="):
                value = part.split("=", 1)[1]
                if value.isdigit():
                    return value
        return None

    def _copy_relative_file(self, *, source: Path, destination: Path) -> None:
        if not source.exists():
            raise err("E_S8_ASSET_MISSING", f"required artefact '{source}' is missing")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._copy_file(source, destination)

    def _copy_file(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def _resolve_catalog_path(
        self,
        relative_path: str,
        *,
        data_root: Path | None,
        repo_root: Path,
    ) -> Path:
        candidates = []
        if data_root is not None:
            candidates.append((data_root / relative_path).resolve())
        candidates.append((repo_root / relative_path).resolve())
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise err(
            "E_S8_POLICY_PATH",
            f"unable to resolve sealed policy path '{relative_path}'",
        )

    def _sha256_file(self, path: Path) -> str:
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()

__all__ = ["S8ValidationInputs", "S8ValidationResult", "S8ValidationRunner"]
