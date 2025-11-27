"""High-level orchestration for Segment 5A S0 gate."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Mapping, MutableMapping, Sequence

import polars as pl
import yaml

from engine.layers.l1.seg_2A.s0_gate.l0.bundle import BundleIndex, IndexEntry
from engine.layers.l1.seg_3A.s0_gate.l0 import (
    ArtifactDigest,
    compute_index_digest,
    hash_files,
    load_index,
)
from engine.layers.l2.seg_5A.shared.dictionary import (
    DictionaryError,
    default_dictionary_path,
    load_dictionary,
    render_dataset_path,
    repository_root,
)
from engine.layers.l2.seg_5A.shared.run_report import SegmentStateKey, write_segment_state_run_report
from engine.layers.l2.seg_5A.s0_gate.inputs import SealedArtefact, ensure_unique_assets

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class S0Inputs:
    """Configuration required to execute 5A S0."""

    base_path: Path
    output_base_path: Path
    upstream_manifest_fingerprint: str
    parameter_hash: str
    run_id: str
    dictionary_path: Path | None = None
    validation_bundle_1a: Path | None = None
    validation_bundle_1b: Path | None = None
    validation_bundle_2a: Path | None = None
    validation_bundle_2b: Path | None = None
    validation_bundle_3a: Path | None = None
    validation_bundle_3b: Path | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        base = Path(self.base_path).absolute()
        out = Path(self.output_base_path).absolute()
        object.__setattr__(self, "base_path", base)
        object.__setattr__(self, "output_base_path", out)
        if len(self.upstream_manifest_fingerprint) != 64:
            raise ValueError("upstream manifest fingerprint must be 64 hex characters")
        int(self.upstream_manifest_fingerprint, 16)
        if len(self.parameter_hash) != 64:
            raise ValueError("parameter_hash must be 64 hex characters")
        int(self.parameter_hash, 16)
        if not self.run_id:
            raise ValueError("run_id must be provided for 5A S0")


@dataclass(frozen=True)
class S0Outputs:
    """Result bundle emitted by :class:`S0GateRunner`."""

    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    sealed_inputs_digest: str
    run_report_path: Path


@dataclass(frozen=True)
class CandidateSpec:
    """Declarative description of a dataset that must be sealed for 5A."""

    owner_layer: str
    owner_segment: str
    dataset_id: str
    dictionary_rel_path: str
    role: str = "upstream_egress"
    status: str = "REQUIRED"
    read_scope: str = "ROW_LEVEL"
    manifest_scope: str = "fingerprint"
    manifest_key: str | None = None
    base: str = "base"


_UPSTREAM_DATASET_SPECS: tuple[CandidateSpec, ...] = (
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="1A",
        dataset_id="outlet_catalogue",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="1B",
        dataset_id="site_locations",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="2A",
        dataset_id="site_timezones",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="2A",
        dataset_id="tz_timetable_cache",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml",
        read_scope="METADATA_ONLY",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="2B",
        dataset_id="s1_site_weights",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="2B",
        dataset_id="s2_alias_index",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
        read_scope="METADATA_ONLY",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="2B",
        dataset_id="s2_alias_blob",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
        read_scope="METADATA_ONLY",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="2B",
        dataset_id="s3_day_effects",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="2B",
        dataset_id="s4_group_weights",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3A",
        dataset_id="zone_alloc",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3A",
        dataset_id="zone_alloc_universe_hash",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml",
        read_scope="METADATA_ONLY",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3B",
        dataset_id="virtual_classification_3B",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3B",
        dataset_id="virtual_settlement_3B",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3B",
        dataset_id="edge_catalogue_3B",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3B",
        dataset_id="edge_alias_index_3B",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
        read_scope="METADATA_ONLY",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3B",
        dataset_id="edge_alias_blob_3B",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
        read_scope="METADATA_ONLY",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3B",
        dataset_id="edge_universe_hash_3B",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
        read_scope="METADATA_ONLY",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3B",
        dataset_id="virtual_routing_policy_3B",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
        read_scope="METADATA_ONLY",
    ),
    CandidateSpec(
        owner_layer="layer1",
        owner_segment="3B",
        dataset_id="virtual_validation_contract_3B",
        dictionary_rel_path="contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
        read_scope="METADATA_ONLY",
    ),
)


class S0GateRunner:
    """High-level helper that wires together the 5A S0 workflow."""

    _UPSTREAM_SEGMENTS = ("1A", "1B", "2A", "2B", "3A", "3B")

    def __init__(self) -> None:
        self._dictionary_cache: dict[Path, Mapping[str, object]] = {}
        self._dictionary_index_cache: dict[Path, dict[str, Mapping[str, object]]] = {}
        self._registry_cache: dict[str, Mapping[str, str]] = {}

    def run(self, inputs: S0Inputs) -> S0Outputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        repo_root = repository_root()
        run_started_at = datetime.now(timezone.utc)
        gate_timer = time.perf_counter()

        # Allow overrides for upstream bundles when manifest fingerprints differ
        self._validation_bundle_1a = inputs.validation_bundle_1a
        self._validation_bundle_1b = inputs.validation_bundle_1b
        self._validation_bundle_2a = inputs.validation_bundle_2a
        self._validation_bundle_2b = inputs.validation_bundle_2b
        self._validation_bundle_3a = inputs.validation_bundle_3a
        self._validation_bundle_3b = inputs.validation_bundle_3b

        upstream_bundles = self._verify_upstream_bundles(
            base_path=inputs.base_path, manifest_fingerprint=inputs.upstream_manifest_fingerprint
        )
        gate_verify_ms = int(round((time.perf_counter() - gate_timer) * 1000))

        sealed_assets = self._collect_sealed_assets(
            inputs=inputs,
            upstream_bundles=upstream_bundles,
            repo_root=repo_root,
        )
        sealed_rows = self._prepare_sealed_rows(sealed_assets)
        sealed_inputs_digest = self._compute_sealed_inputs_digest(sealed_rows)
        sealed_inputs_path = self._write_sealed_inputs(
            inputs=inputs,
            dictionary=dictionary,
            rows=sealed_rows,
            expected_digest=sealed_inputs_digest,
        )
        receipt_path = self._write_receipt(
            inputs=inputs,
            dictionary=dictionary,
            upstream_bundles=upstream_bundles,
            sealed_inputs_digest=sealed_inputs_digest,
            sealed_rows=sealed_rows,
            gate_verify_ms=gate_verify_ms,
            run_started_at=run_started_at,
        )
        run_report_path = self._write_segment_run_report(
            inputs=inputs,
            sealed_inputs_path=sealed_inputs_path,
            receipt_path=receipt_path,
            gate_verify_ms=gate_verify_ms,
            sealed_inputs_digest=sealed_inputs_digest,
        )

        return S0Outputs(
            manifest_fingerprint=inputs.upstream_manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            receipt_path=receipt_path,
            sealed_inputs_path=sealed_inputs_path,
            sealed_inputs_digest=sealed_inputs_digest,
            run_report_path=run_report_path,
        )

    # -------------------- helpers --------------------
    def _verify_upstream_bundles(
        self, *, base_path: Path, manifest_fingerprint: str
    ) -> dict[str, Mapping[str, object]]:
        results: dict[str, Mapping[str, object]] = {}
        overrides = {
            "1A": getattr(self, "_validation_bundle_1a", None),
            "1B": getattr(self, "_validation_bundle_1b", None),
            "2A": getattr(self, "_validation_bundle_2a", None),
            "2B": getattr(self, "_validation_bundle_2b", None),
            "3A": getattr(self, "_validation_bundle_3a", None),
            "3B": getattr(self, "_validation_bundle_3b", None),
        }
        for segment in self._UPSTREAM_SEGMENTS:
            override_path = overrides.get(segment)
            bundle_path = (
                override_path
                if isinstance(override_path, Path)
                else base_path / f"data/layer1/{segment}/validation/fingerprint={manifest_fingerprint}"
            )
            logger.info("S0 bundle check: segment=%s, bundle_path=%s", segment, bundle_path)
            bundle_path = self._resolve_bundle_path(bundle_path)
            if not bundle_path.exists() or not bundle_path.is_dir():
                raise FileNotFoundError(f"{segment} validation bundle missing at {bundle_path}")
            try:
                index = load_index(bundle_path)
            except Exception:
                index = self._load_index_lenient(bundle_path)
            computed_flag = self._compute_digest_for_segment(segment, bundle_path, index)
            declared_flag = self._read_pass_flag(bundle_path)
            if computed_flag != declared_flag:
                raise ValueError(f"{segment} computed digest does not match _passed.flag")
        results[segment] = {
            "path": bundle_path,
            "bundle_sha256_hex": computed_flag,
            "flag_sha256_hex": declared_flag,
            "manifest_fingerprint": self._extract_manifest_fingerprint(bundle_path),
        }
        return results

    @staticmethod
    def _resolve_bundle_path(bundle_path: Path) -> Path:
        """Resolve a validation bundle directory even if the caller points to parent/child paths."""

        candidates = [bundle_path]
        if bundle_path.name == "bundle":
            candidates.append(bundle_path.parent)
        else:
            candidates.append(bundle_path / "bundle")
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                if (candidate / "index.json").exists():
                    return candidate
        return bundle_path

    @staticmethod
    def _read_pass_flag(bundle_path: Path) -> str:
        flag_path = S0GateRunner._find_flag_file(bundle_path)
        content = flag_path.read_text(encoding="utf-8").strip()
        if "=" in content:
            content = content.split("=", 1)[1].strip()
        return content

    @staticmethod
    def _find_flag_file(bundle_path: Path) -> Path:
        candidates = list(bundle_path.glob("_passed.flag*"))
        if not candidates:
            # also look one level down for historical layouts
            candidates = list((bundle_path / "bundle").glob("_passed.flag*"))
        if not candidates:
            raise FileNotFoundError(f"validation bundle missing _passed.flag at {bundle_path}")
        return sorted(candidates)[0]

    def _compute_digest_for_segment(self, segment: str, bundle_path: Path, index: BundleIndex) -> str:
        """Honor per-segment hashing laws when known."""

        if segment == "3B":
            index_path = bundle_path / "index.json"
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            items = []
            if isinstance(payload, dict):
                items = payload.get("items") or payload.get("artifacts") or payload.get("files") or []
            elif isinstance(payload, list):
                items = payload
            digests = [
                item.get("sha256_hex")
                for item in items
                if isinstance(item, Mapping) and isinstance(item.get("sha256_hex"), str)
            ]
            if digests:
                return hashlib.sha256("".join(digests).encode("utf-8")).hexdigest()
        return compute_index_digest(bundle_path, index)

    @staticmethod
    def _load_index_lenient(bundle_path: Path) -> BundleIndex:
        """Parse index.json while tolerating extra non-indexed files such as suffix pass flags."""

        index_path = bundle_path / "index.json"
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        items = None
        version = None
        if isinstance(payload, dict):
            version = payload.get("version") if isinstance(payload.get("version"), str) else None
            for key in ("items", "artifacts", "files"):
                if isinstance(payload.get(key), list):
                    items = payload[key]
                    break
        if items is None:
            items = payload if isinstance(payload, list) else []
        entries: list[IndexEntry] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            path_value = item.get("path")
            artifact_id = item.get("artifact_id") or path_value
            if isinstance(artifact_id, str) and isinstance(path_value, str):
                entries.append(IndexEntry(artifact_id=artifact_id, path=path_value, raw=item))
        return BundleIndex(entries=entries, version=version)

    def _collect_sealed_assets(
        self,
        *,
        inputs: S0Inputs,
        upstream_bundles: Mapping[str, Mapping[str, object]],
        repo_root: Path,
    ) -> list[SealedArtefact]:
        assets: list[SealedArtefact] = []
        assets.extend(self._seal_upstream_validation_assets(inputs=inputs, upstream_bundles=upstream_bundles))
        assets.extend(self._seal_candidate_datasets(inputs=inputs, repo_root=repo_root, upstream_bundles=upstream_bundles))
        assets.extend(self._seal_contract_assets(inputs=inputs, repo_root=repo_root))
        return ensure_unique_assets(assets)

    def _seal_upstream_validation_assets(
        self,
        *,
        inputs: S0Inputs,
        upstream_bundles: Mapping[str, Mapping[str, object]],
    ) -> list[SealedArtefact]:
        assets: list[SealedArtefact] = []
        for segment, info in upstream_bundles.items():
            bundle_path: Path = info["path"]  # type: ignore[assignment]
            if bundle_path.is_dir():
                bundle_files = [p for p in bundle_path.rglob("*") if p.is_file()]
            else:
                bundle_files = [bundle_path]
            bundle_digests = tuple(hash_files(bundle_files, error_prefix=f"validation_bundle_{segment}"))
            assets.append(
                SealedArtefact(
                    manifest_fingerprint=inputs.upstream_manifest_fingerprint,
                    parameter_hash=inputs.parameter_hash,
                    owner_layer="layer1",
                    owner_segment=segment,
                    artifact_id=f"validation_bundle_{segment}",
                    manifest_key=f"mlr.{segment}.validation.bundle",
                    role="validation_bundle",
                    schema_ref="schemas.layer1.yaml#/validation/validation_bundle",
                    path_template=f"data/layer1/{segment}/validation/fingerprint={{manifest_fingerprint}}",
                    partition_keys=("manifest_fingerprint",),
                    version=inputs.upstream_manifest_fingerprint,
                    digests=bundle_digests,
                    source_dictionary=f"contracts/dataset_dictionary/l1/seg_{segment}/layer1.{segment}.yaml",
                    source_registry=self._registry_rel_path(segment),
                )
            )
            flag_path = self._find_flag_file(bundle_path)
            flag_digests = tuple(hash_files([flag_path], error_prefix=f"passed_flag_{segment}"))
            assets.append(
                SealedArtefact(
                    manifest_fingerprint=inputs.upstream_manifest_fingerprint,
                    parameter_hash=inputs.parameter_hash,
                    owner_layer="layer1",
                    owner_segment=segment,
                    artifact_id=f"passed_flag_{segment}",
                    manifest_key=f"mlr.{segment}.validation.passed_flag",
                    role="validation_flag",
                    schema_ref="schemas.layer1.yaml#/validation/passed_flag",
                    path_template=f"data/layer1/{segment}/validation/fingerprint={{manifest_fingerprint}}/_passed.flag",
                    partition_keys=("manifest_fingerprint",),
                    version=inputs.upstream_manifest_fingerprint,
                    digests=flag_digests,
                    source_dictionary=f"contracts/dataset_dictionary/l1/seg_{segment}/layer1.{segment}.yaml",
                    source_registry=self._registry_rel_path(segment),
                    read_scope="METADATA_ONLY",
                )
            )
        return assets

    def _seal_candidate_datasets(
        self,
        *,
        inputs: S0Inputs,
        repo_root: Path,
        upstream_bundles: Mapping[str, Mapping[str, object]],
    ) -> list[SealedArtefact]:
        assets: list[SealedArtefact] = []
        template_args = {
            "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
        }
        for spec in _UPSTREAM_DATASET_SPECS:
            if spec.owner_segment in self._UPSTREAM_SEGMENTS and spec.owner_segment not in upstream_bundles:
                continue
            entry = self._dictionary_entry(spec.dictionary_rel_path, spec.dataset_id)
            path_template = self._extract_path_template(entry, spec)
            partition_keys = tuple(entry.get("partitioning") or entry.get("partition_keys") or ())
            schema_ref = entry.get("schema_ref")
            if not isinstance(schema_ref, str) or not schema_ref.strip():
                raise DictionaryError(
                    f"dictionary entry '{spec.dataset_id}' in '{spec.dictionary_rel_path}' is missing schema_ref"
                )
            template_values: MutableMapping[str, object] = {
                "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
                "fingerprint": inputs.upstream_manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            }
            segment_info = upstream_bundles.get(spec.owner_segment)
            if segment_info and segment_info.get("manifest_fingerprint"):
                segment_fp = segment_info["manifest_fingerprint"]
                template_values["manifest_fingerprint"] = segment_fp
                template_values["fingerprint"] = segment_fp
            base_dir = inputs.base_path if spec.base == "base" else repo_root
            files = self._expand_dataset_files(
                base_path=base_dir,
                template=path_template,
                template_args=template_values,
                dataset_id=spec.dataset_id,
            )
            digests = tuple(hash_files(files, error_prefix=spec.dataset_id))
            manifest_key = spec.manifest_key or self._registry_manifest_key(spec.owner_segment, path_template)
            assets.append(
                SealedArtefact(
                    manifest_fingerprint=inputs.upstream_manifest_fingerprint,
                    parameter_hash=inputs.parameter_hash,
                    owner_layer=spec.owner_layer,
                    owner_segment=spec.owner_segment,
                    artifact_id=spec.dataset_id,
                    manifest_key=manifest_key or f"mlr.{spec.owner_segment.lower()}.{spec.dataset_id}",
                    role=spec.role,
                    schema_ref=schema_ref.strip(),
                    path_template=path_template,
                    partition_keys=partition_keys,
                    version=self._resolve_version(spec, inputs),
                    digests=digests,
                    source_dictionary=spec.dictionary_rel_path,
                    source_registry=self._registry_rel_path(spec.owner_segment),
                    status=spec.status,
                    read_scope=spec.read_scope,
                )
            )
        return assets

    def _seal_contract_assets(self, *, inputs: S0Inputs, repo_root: Path) -> list[SealedArtefact]:
        assets: list[SealedArtefact] = []
        contract_assets = [
            ("schemas.layer2.yaml", repo_root / "contracts" / "schemas" / "layer2" / "schemas.layer2.yaml"),
            ("schemas.5A.yaml", repo_root / "contracts" / "schemas" / "layer2" / "schemas.5A.yaml"),
            ("dataset_dictionary_5A", default_dictionary_path()),
            ("artefact_registry_5A", repo_root / "contracts" / "artefact_registry" / "artefact_registry_5A.yaml"),
        ]
        for logical_id, path in contract_assets:
            if not path.exists():
                raise DictionaryError(f"contract asset '{logical_id}' not found at {path}")
            digests = tuple(hash_files([path], error_prefix=logical_id))
            assets.append(
                SealedArtefact(
                    manifest_fingerprint=inputs.upstream_manifest_fingerprint,
                    parameter_hash=inputs.parameter_hash,
                    owner_layer="layer2",
                    owner_segment="5A",
                    artifact_id=logical_id,
                    manifest_key=f"mlr.5A.contract.{logical_id}",
                    role="contract",
                    schema_ref="schemas.layer2.yaml#/contracts/file",
                    path_template=str(path.relative_to(repo_root)),
                    partition_keys=(),
                    version="1.0.0",
                    digests=digests,
                    source_dictionary=str(default_dictionary_path().relative_to(repo_root)),
                    source_registry=self._registry_rel_path("5A"),
                    read_scope="METADATA_ONLY",
                )
            )
        return assets

    @staticmethod
    def _prepare_sealed_rows(sealed_assets: Sequence[SealedArtefact]) -> list[Mapping[str, object]]:
        rows = [asset.as_row() for asset in sealed_assets]
        rows.sort(key=lambda row: (row["owner_layer"], row["owner_segment"], row["artifact_id"]))
        return rows

    @staticmethod
    def _compute_sealed_inputs_digest(rows: Sequence[Mapping[str, object]]) -> str:
        sorted_rows = sorted(
            rows,
            key=lambda row: (
                row.get("owner_layer", ""),
                row.get("owner_segment", ""),
                row.get("artifact_id", ""),
                row.get("manifest_key", ""),
            ),
        )
        buffer = bytearray()
        for row in sorted_rows:
            buffer.extend(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
        return hashlib.sha256(buffer).hexdigest()


    def _write_sealed_inputs(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object],
        rows: Sequence[Mapping[str, object]],
        expected_digest: str,
    ) -> Path:
        output_path = inputs.output_base_path / render_dataset_path(
            dataset_id="sealed_inputs_5A",
            template_args={"manifest_fingerprint": inputs.upstream_manifest_fingerprint},
            dictionary=dictionary,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            existing_rows = pl.read_parquet(output_path).to_dicts()
            existing_digest = self._compute_sealed_inputs_digest(existing_rows)
            if existing_digest == expected_digest:
                return output_path
            raise RuntimeError(
                "sealed_inputs_5A already exists with different content; rerun after removing stale outputs"
            )
        pl.DataFrame(rows).write_parquet(output_path)
        return output_path

    def _write_receipt(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object],
        upstream_bundles: Mapping[str, Mapping[str, object]],
        sealed_inputs_digest: str,
        sealed_rows: Sequence[Mapping[str, object]],
        gate_verify_ms: int,
        run_started_at: datetime,
    ) -> Path:
        output_dir = (
            inputs.output_base_path
            / render_dataset_path(
                dataset_id="s0_gate_receipt_5A",
                template_args={"manifest_fingerprint": inputs.upstream_manifest_fingerprint},
                dictionary=dictionary,
            )
        ).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc)
        role_counts = Counter(row.get("role", "unknown") for row in sealed_rows)
        receipt_payload: MutableMapping[str, object] = {
            "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "run_id": inputs.run_id,
            "created_utc": created_at.isoformat().replace("+00:00", "Z"),
            "s0_spec_version": "1.0.0",
            "sealed_inputs_digest": sealed_inputs_digest,
            "sealed_inputs_total": len(sealed_rows),
            "sealed_inputs_roles": dict(sorted(role_counts.items())),
            "scenario_id": ["baseline"],
            "verified_upstream_segments": {},
            "notes": inputs.notes or "",
            "gate_verify_ms": gate_verify_ms,
            "run_started_at_utc": run_started_at.isoformat().replace("+00:00", "Z"),
        }
        for segment, info in upstream_bundles.items():
            bundle_path: Path = info["path"]  # type: ignore[assignment]
            bundle_sha = info["bundle_sha256_hex"]
            flag_sha = info["flag_sha256_hex"]
            receipt_payload["verified_upstream_segments"][segment] = {
                "status": "PASS",
                "bundle_id": f"validation_bundle_{segment}",
                "bundle_path": str(bundle_path),
                "bundle_sha256_hex": bundle_sha,
                "flag_sha256_hex": flag_sha,
            }

        receipt_path = output_dir / "s0_gate_receipt_5A.json"
        receipt_path.write_text(json.dumps(receipt_payload, indent=2))
        return receipt_path

    def _write_segment_run_report(
        self,
        *,
        inputs: S0Inputs,
        sealed_inputs_path: Path,
        receipt_path: Path,
        gate_verify_ms: int,
        sealed_inputs_digest: str,
    ) -> Path:
        run_report_path = inputs.output_base_path / "reports/l2/segment_states/segment_state_runs.jsonl"
        key = SegmentStateKey(
            layer="layer2",
            segment="5A",
            state="S0",
            manifest_fingerprint=inputs.upstream_manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            run_id=inputs.run_id,
        )
        payload = {
            **key.as_dict(),
            "status": "PASS",
            "attempt": 1,
            "run_started_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "elapsed_ms": gate_verify_ms,
            "sealed_inputs_path": str(sealed_inputs_path),
            "receipt_path": str(receipt_path),
            "sealed_inputs_digest": sealed_inputs_digest,
            "notes": inputs.notes,
        }
        return write_segment_state_run_report(path=run_report_path, key=key, payload=payload)

    def _dictionary_entry(self, rel_path: str, dataset_id: str) -> Mapping[str, object]:
        repo_root = repository_root()
        path = (repo_root / rel_path).resolve()
        dictionary = self._dictionary_cache.get(path)
        if dictionary is None:
            if not path.exists():
                raise DictionaryError(f"dataset dictionary '{path}' missing")
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, MutableMapping):
                raise DictionaryError(f"dataset dictionary '{path}' must decode to a mapping")
            dictionary = payload
            self._dictionary_cache[path] = dictionary
            self._dictionary_index_cache[path] = self._build_dictionary_index(dictionary)
        entry = self._dictionary_index_cache[path].get(dataset_id)
        if entry is None:
            raise DictionaryError(f"dataset '{dataset_id}' not present in dictionary '{path}'")
        return entry

    @staticmethod
    def _build_dictionary_index(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
        index: dict[str, Mapping[str, object]] = {}

        def visit(node: object, key_hint: str | None = None) -> None:
            if isinstance(node, Mapping):
                dataset_id = node.get("id")
                if isinstance(dataset_id, str):
                    key_hint = dataset_id
                path_value = node.get("path")
                if key_hint and isinstance(path_value, str) and key_hint not in index:
                    index[key_hint] = node
                for key, value in node.items():
                    next_hint = key if isinstance(key, str) else key_hint
                    visit(value, next_hint)
            elif isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
                for item in node:
                    visit(item, None)

        visit(payload)
        return index

    @staticmethod
    def _extract_path_template(entry: Mapping[str, object], spec: CandidateSpec) -> str:
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise DictionaryError(f"dictionary entry '{spec.dataset_id}' missing path template")
        return raw_path.strip()

    def _expand_dataset_files(
        self,
        *,
        base_path: Path,
        template: str,
        template_args: Mapping[str, object],
        dataset_id: str,
    ) -> list[Path]:
        glob_pattern = self._template_to_glob(template, template_args)
        matches = sorted(base_path.glob(glob_pattern))
        if not matches:
            raise FileNotFoundError(f"no artefacts found for '{dataset_id}' using pattern '{glob_pattern}'")
        files: list[Path] = []
        for match in matches:
            if match.is_file():
                files.append(match)
            elif match.is_dir():
                files.extend([p for p in match.rglob("*") if p.is_file()])
        if not files:
            raise FileNotFoundError(f"dataset '{dataset_id}' resolved to empty directory '{glob_pattern}'")
        return files

    def _template_to_glob(self, template: str, template_args: Mapping[str, object]) -> str:
        partially_rendered = self._partial_format_template(template, template_args)
        pattern = re.sub(r"\{[^}]+\}", "*", partially_rendered)
        return pattern.replace("\\", "/").strip()

    @staticmethod
    def _partial_format_template(template: str, template_args: Mapping[str, object]) -> str:
        formatter = Formatter()
        rendered = []
        for literal, field, format_spec, _ in formatter.parse(template):
            rendered.append(literal)
            if field is None:
                continue
            if field in template_args:
                rendered.append(format(template_args[field], format_spec))
            else:
                rendered.append(f"{{{field}}}")
        return "".join(rendered)

    def _registry_manifest_key(self, segment: str, path_template: str) -> str | None:
        manifest_map = self._registry_manifest_map(segment)
        normalized = self._normalize_contract_path(path_template)
        return manifest_map.get(normalized)

    def _registry_manifest_map(self, segment: str) -> Mapping[str, str]:
        cached = self._registry_cache.get(segment)
        if cached is not None:
            return cached
        repo_root = repository_root()
        candidates = [
            repo_root / "contracts" / "artefact_registry" / f"artefact_registry_{segment}.yaml",
            repo_root / f"contracts/artefact_registry_{segment}.yaml",
        ]
        manifest_map: Mapping[str, str] = {}
        for candidate in candidates:
            if candidate.exists():
                payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
                manifest_map = self._extract_manifest_map(payload)
                break
        self._registry_cache[segment] = manifest_map
        return manifest_map

    @staticmethod
    def _extract_manifest_map(payload: Mapping[str, object]) -> Mapping[str, str]:
        manifest: dict[str, str] = {}
        subsegments = payload.get("subsegments")
        if not isinstance(subsegments, Sequence):
            return manifest
        for block in subsegments:
            if not isinstance(block, Mapping):
                continue
            artifacts = block.get("artifacts")
            if not isinstance(artifacts, Sequence):
                continue
            for artifact in artifacts:
                if not isinstance(artifact, Mapping):
                    continue
                path_value = artifact.get("path")
                manifest_key = artifact.get("manifest_key")
                if isinstance(path_value, str) and isinstance(manifest_key, str):
                    manifest[S0GateRunner._normalize_contract_path(path_value)] = manifest_key
        return manifest

    def _registry_rel_path(self, segment: str) -> str:
        repo_root = repository_root()
        candidates = [
            repo_root / "contracts" / "artefact_registry" / f"artefact_registry_{segment}.yaml",
            repo_root / f"contracts/artefact_registry_{segment}.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate.relative_to(repo_root))
        return ""

    @staticmethod
    def _normalize_contract_path(raw: str) -> str:
        return raw.replace("\\", "/").strip()

    @staticmethod
    def _resolve_version(spec: CandidateSpec, inputs: S0Inputs) -> str:
        if spec.manifest_scope == "parameter_hash":
            return inputs.parameter_hash
        if spec.manifest_scope == "fingerprint":
            return inputs.upstream_manifest_fingerprint
        return spec.manifest_scope

    @staticmethod
    def _extract_manifest_fingerprint(path: Path) -> str | None:
        match = re.search(r"fingerprint=([a-f0-9]{64})", str(path))
        return match.group(1) if match else None

__all__ = ["S0GateRunner", "S0Inputs", "S0Outputs"]
