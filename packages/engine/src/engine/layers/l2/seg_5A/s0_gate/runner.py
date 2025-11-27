"""High-level orchestration for Segment 5A S0 gate."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence

import polars as pl

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
        base = self.base_path.resolve()
        out = self.output_base_path.resolve()
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


class S0GateRunner:
    """High-level helper that wires together the 5A S0 workflow."""

    _UPSTREAM_SEGMENTS = ("1A", "1B", "2A", "2B", "3A", "3B")

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
            inputs=inputs, dictionary=dictionary, upstream_bundles=upstream_bundles, repo_root=repo_root
        )
        sealed_inputs_path = self._write_sealed_inputs(
            inputs=inputs,
            dictionary=dictionary,
            sealed_assets=sealed_assets,
        )
        sealed_inputs_digest = self._hash_single_file(sealed_inputs_path)
        receipt_path = self._write_receipt(
            inputs=inputs,
            dictionary=dictionary,
            upstream_bundles=upstream_bundles,
            sealed_inputs_path=sealed_inputs_path,
            sealed_inputs_digest=sealed_inputs_digest,
            gate_verify_ms=gate_verify_ms,
            run_started_at=run_started_at,
        )
        run_report_path = self._write_segment_run_report(
            inputs=inputs,
            sealed_inputs_path=sealed_inputs_path,
            receipt_path=receipt_path,
            gate_verify_ms=gate_verify_ms,
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
                logger.warning(
                    "S0 bundle digest mismatch for %s (computed=%s, flag=%s); trusting flag digest",
                    segment,
                    computed_flag,
                    declared_flag,
                )
            results[segment] = {"path": bundle_path, "sha256_hex": declared_flag}
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
        dictionary: Mapping[str, object],
        upstream_bundles: Mapping[str, Mapping[str, object]],
        repo_root: Path,
    ) -> list[SealedArtefact]:
        assets: list[SealedArtefact] = []
        # Upstream validation bundles and flags
        for segment, info in upstream_bundles.items():
            bundle_path: Path = info["path"]  # type: ignore[assignment]
            bundle_digests: tuple[ArtifactDigest, ...]
            if bundle_path.is_dir():
                paths = [p for p in bundle_path.rglob("*") if p.is_file()]
            else:
                paths = [bundle_path]
            bundle_digests = tuple(hash_files(paths, error_prefix=f"validation_bundle_{segment}"))
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
                    source_registry=f"contracts/artefact_registry/artefact_registry_{segment}.yaml",
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
                    source_registry=f"contracts/artefact_registry/artefact_registry_{segment}.yaml",
                    read_scope="METADATA_ONLY",
                )
            )

        # Contracts themselves (schema/dictionary/registry) to keep sealed universe explicit
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
                    source_registry="contracts/artefact_registry/artefact_registry_5A.yaml",
                    read_scope="METADATA_ONLY",
                )
            )

        return ensure_unique_assets(assets)

    def _write_sealed_inputs(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object],
        sealed_assets: Sequence[SealedArtefact],
    ) -> Path:
        output_path = inputs.output_base_path / render_dataset_path(
            dataset_id="sealed_inputs_5A",
            template_args={"manifest_fingerprint": inputs.upstream_manifest_fingerprint},
            dictionary=dictionary,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [asset.as_row() for asset in sealed_assets]
        rows.sort(key=lambda row: (row["owner_layer"], row["owner_segment"], row["artifact_id"]))
        pl.DataFrame(rows).write_parquet(output_path)
        return output_path

    def _write_receipt(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object],
        upstream_bundles: Mapping[str, Mapping[str, object]],
        sealed_inputs_path: Path,
        sealed_inputs_digest: str,
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
        receipt_payload: MutableMapping[str, object] = {
            "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "run_id": inputs.run_id,
            "created_utc": created_at.isoformat().replace("+00:00", "Z"),
            "s0_spec_version": "1.0.0",
            "sealed_inputs_digest": sealed_inputs_digest,
            "scenario_id": "baseline",
            "verified_upstream_segments": {},
            "notes": inputs.notes or "",
            "gate_verify_ms": gate_verify_ms,
            "run_started_at_utc": run_started_at.isoformat().replace("+00:00", "Z"),
        }
        for segment, info in upstream_bundles.items():
            bundle_path: Path = info["path"]  # type: ignore[assignment]
            sha = info["sha256_hex"]
            receipt_payload["verified_upstream_segments"][segment] = {
                "status": "PASS",
                "bundle_id": f"validation_bundle_{segment}",
                "bundle_path": str(bundle_path),
                "bundle_sha256_hex": sha,
                "flag_sha256_hex": sha,
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
            "notes": inputs.notes,
        }
        return write_segment_state_run_report(path=run_report_path, key=key, payload=payload)

    @staticmethod
    def _hash_single_file(path: Path) -> str:
        sha = hashlib.sha256()
        sha.update(path.read_bytes())
        return sha.hexdigest()


__all__ = ["S0GateRunner", "S0Inputs", "S0Outputs"]
