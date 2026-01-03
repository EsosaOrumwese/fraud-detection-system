"""Segment 5B S0 gate runner."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping

import polars as pl
import yaml

from engine.layers.l1.seg_3A.s0_gate.l0 import compute_index_digest, load_index, read_pass_flag
from engine.layers.l2.seg_5B.shared.control_plane import compute_sealed_inputs_digest, parse_partition_keys
from engine.layers.l2.seg_5B.shared.dictionary import (
    DictionaryError,
    default_dictionary_path,
    load_dictionary,
    repository_root,
    render_dataset_path,
)
from engine.layers.l2.seg_5B.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class S0Inputs:
    """Configuration required to execute 5B S0."""

    base_path: Path
    output_base_path: Path
    upstream_manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None
    validation_bundle_1a: Path | None = None
    validation_bundle_1b: Path | None = None
    validation_bundle_2a: Path | None = None
    validation_bundle_2b: Path | None = None
    validation_bundle_3a: Path | None = None
    validation_bundle_3b: Path | None = None
    validation_bundle_5a: Path | None = None

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
            raise ValueError("run_id must be provided for 5B S0")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


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
class SealedAsset:
    owner_layer: str
    owner_segment: str
    artifact_id: str
    manifest_key: str
    role: str
    schema_ref: str
    path_template: str
    partition_keys: tuple[str, ...]
    sha256_hex: str
    status: str
    read_scope: str
    notes: str | None = None
    owner_team: str | None = None
    source_manifest: str | None = None


class S0GateRunner:
    """High-level helper that wires together the 5B S0 workflow."""

    _UPSTREAM_SEGMENTS = ("1A", "1B", "2A", "2B", "3A", "3B", "5A")
    _UPSTREAM_BUNDLE_SPECS: Mapping[str, Mapping[str, str]] = {
        "1A": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml",
            "bundle_id": "validation_bundle_1A",
            "flag_id": "validation_passed_flag_1A",
            "override_attr": "validation_bundle_1a",
        },
        "1B": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml",
            "bundle_id": "validation_bundle_1B",
            "flag_id": "validation_passed_flag_1B",
            "override_attr": "validation_bundle_1b",
        },
        "2A": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml",
            "bundle_id": "validation_bundle_2A",
            "flag_id": "validation_passed_flag_2A",
            "override_attr": "validation_bundle_2a",
        },
        "2B": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
            "bundle_id": "validation_bundle_2B",
            "flag_id": "validation_passed_flag_2B",
            "override_attr": "validation_bundle_2b",
        },
        "3A": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml",
            "bundle_id": "validation_bundle_3A",
            "flag_id": "validation_passed_flag_3A",
            "override_attr": "validation_bundle_3a",
        },
        "3B": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "bundle_id": "validation_bundle_3B",
            "flag_id": "validation_passed_flag_3B",
            "override_attr": "validation_bundle_3b",
        },
        "5A": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l2/seg_5A/layer2.5A.yaml",
            "bundle_id": "validation_bundle_index_5A",
            "flag_id": "validation_passed_flag_5A",
            "override_attr": "validation_bundle_5a",
        },
    }

    _SEALED_UPSTREAM_DATASETS: tuple[Mapping[str, str], ...] = (
        {
            "owner_layer": "layer1",
            "owner_segment": "1A",
            "dataset_id": "outlet_catalogue",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "1B",
            "dataset_id": "site_locations",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "2A",
            "dataset_id": "site_timezones",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "2A",
            "dataset_id": "tz_timetable_cache",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml",
            "role": "reference_data",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "2B",
            "dataset_id": "s1_site_weights",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "2B",
            "dataset_id": "s2_alias_index",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
            "role": "upstream_egress",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "2B",
            "dataset_id": "s2_alias_blob",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
            "role": "upstream_egress",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "2B",
            "dataset_id": "route_rng_policy_v1",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
            "role": "contract",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "2B",
            "dataset_id": "alias_layout_policy_v1",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
            "role": "contract",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "2B",
            "dataset_id": "s4_group_weights",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3A",
            "dataset_id": "zone_alloc",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3A",
            "dataset_id": "zone_alloc_universe_hash",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml",
            "role": "reference_data",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3B",
            "dataset_id": "virtual_classification_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3B",
            "dataset_id": "virtual_settlement_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3B",
            "dataset_id": "edge_catalogue_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3B",
            "dataset_id": "edge_alias_index_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "upstream_egress",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3B",
            "dataset_id": "edge_alias_blob_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "upstream_egress",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3B",
            "dataset_id": "edge_universe_hash_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "reference_data",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer1",
            "owner_segment": "3B",
            "dataset_id": "virtual_routing_policy_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "contract",
            "read_scope": "METADATA_ONLY",
        },
    )

    _SEALED_LAYER2_DATASETS: tuple[Mapping[str, str], ...] = (
        {
            "owner_layer": "layer2",
            "owner_segment": "5A",
            "dataset_id": "scenario_manifest_5A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l2/seg_5A/layer2.5A.yaml",
            "role": "reference_data",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "layer2",
            "owner_segment": "5A",
            "dataset_id": "merchant_zone_profile_5A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l2/seg_5A/layer2.5A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "layer2",
            "owner_segment": "5A",
            "dataset_id": "merchant_zone_scenario_local_5A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l2/seg_5A/layer2.5A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
    )

    _SEALED_CONFIG_DATASETS: tuple[str, ...] = (
        "time_grid_policy_5B",
        "grouping_policy_5B",
        "arrival_lgcp_config_5B",
        "arrival_count_config_5B",
        "arrival_time_placement_policy_5B",
        "arrival_routing_policy_5B",
        "arrival_rng_policy_5B",
        "validation_policy_5B",
    )

    def __init__(self) -> None:
        self._dictionary_cache: dict[Path, Mapping[str, object]] = {}
        self._dictionary_index_cache: dict[Path, dict[str, Mapping[str, object]]] = {}
        self._registry_cache: dict[str, Mapping[str, str]] = {}

    def run(self, inputs: S0Inputs) -> S0Outputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        repo_root = repository_root()
        run_started_at = datetime.now(timezone.utc)
        run_start = time.perf_counter()
        gate_timer = time.perf_counter()
        logger.info("5B.S0 gate start upstream_manifest=%s", inputs.upstream_manifest_fingerprint)

        self._validation_bundle_1a = inputs.validation_bundle_1a
        self._validation_bundle_1b = inputs.validation_bundle_1b
        self._validation_bundle_2a = inputs.validation_bundle_2a
        self._validation_bundle_2b = inputs.validation_bundle_2b
        self._validation_bundle_3a = inputs.validation_bundle_3a
        self._validation_bundle_3b = inputs.validation_bundle_3b
        self._validation_bundle_5a = inputs.validation_bundle_5a
        # Mirror override bundles to the names expected by _UPSTREAM_BUNDLE_SPECS.
        self.validation_bundle_1a = inputs.validation_bundle_1a
        self.validation_bundle_1b = inputs.validation_bundle_1b
        self.validation_bundle_2a = inputs.validation_bundle_2a
        self.validation_bundle_2b = inputs.validation_bundle_2b
        self.validation_bundle_3a = inputs.validation_bundle_3a
        self.validation_bundle_3b = inputs.validation_bundle_3b
        self.validation_bundle_5a = inputs.validation_bundle_5a

        upstream_bundles = self._verify_upstream_bundles(
            base_path=inputs.base_path,
            manifest_fingerprint=inputs.upstream_manifest_fingerprint,
        )
        gate_verify_ms = int(round((time.perf_counter() - gate_timer) * 1000))

        scenario_ids = self._load_scenario_ids(
            base_path=inputs.base_path,
            manifest_fingerprint=inputs.upstream_manifest_fingerprint,
        )
        sealed_rows = self._collect_sealed_assets(
            inputs=inputs,
            upstream_bundles=upstream_bundles,
            repo_root=repo_root,
            dictionary=dictionary,
            scenario_ids=scenario_ids,
        )
        sort_cols = [
            "owner_layer",
            "owner_segment",
            "artifact_id",
            "manifest_key",
            "role",
            "schema_ref",
            "path_template",
            "sha256_hex",
            "status",
            "read_scope",
        ]
        sealed_df = pl.DataFrame(sealed_rows).sort(sort_cols)
        sealed_rows = sealed_df.to_dicts()
        sealed_inputs_digest = compute_sealed_inputs_digest(sealed_rows)
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
            sealed_inputs_row_count=len(sealed_rows),
            gate_verify_ms=gate_verify_ms,
            run_started_at=run_started_at,
            scenario_ids=scenario_ids,
        )
        run_report_path = self._write_segment_run_report(
            inputs=inputs,
            dictionary=dictionary,
            sealed_inputs_path=sealed_inputs_path,
            receipt_path=receipt_path,
            gate_verify_ms=gate_verify_ms,
            sealed_inputs_digest=sealed_inputs_digest,
        )
        run_elapsed = time.perf_counter() - run_start
        logger.info(
            "5B.S0 gate complete manifest=%s sealed_inputs=%d scenarios=%d elapsed=%.2fs",
            inputs.upstream_manifest_fingerprint,
            len(sealed_rows),
            len(scenario_ids),
            run_elapsed,
        )

        return S0Outputs(
            manifest_fingerprint=inputs.upstream_manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            receipt_path=receipt_path,
            sealed_inputs_path=sealed_inputs_path,
            sealed_inputs_digest=sealed_inputs_digest,
            run_report_path=run_report_path,
        )

    def _verify_upstream_bundles(
        self, *, base_path: Path, manifest_fingerprint: str
    ) -> dict[str, Mapping[str, object]]:
        results: dict[str, Mapping[str, object]] = {}
        for segment in self._UPSTREAM_SEGMENTS:
            spec = self._UPSTREAM_BUNDLE_SPECS.get(segment)
            if spec is None:
                continue
            dictionary_path = repository_root() / spec["dictionary_rel_path"]
            bundle_id = spec["bundle_id"]
            flag_id = spec["flag_id"]
            override_attr = spec["override_attr"]
            bundle_override = getattr(self, override_attr, None)
            if bundle_override is None:
                bundle_override = getattr(self, f"_{override_attr}", None)
            bundle_path = self._resolve_bundle_path(
                base_path=base_path,
                dictionary_path=dictionary_path,
                bundle_id=bundle_id,
                manifest_fingerprint=manifest_fingerprint,
                override=bundle_override,
            )
            if segment == "5A":
                index_path = bundle_path
                if index_path.is_dir():
                    index_path = index_path / "validation_bundle_index_5A.json"
                if not index_path.exists():
                    raise FileNotFoundError(
                        f"validation bundle index missing for {segment}: {index_path}"
                    )
                bundle_digest = self._compute_5a_bundle_digest(index_path)
                if bundle_override is not None:
                    flag_path = index_path.parent / "_passed.flag"
                else:
                    flag_path = self._resolve_dataset_path(
                        base_path=base_path,
                        dictionary_path=dictionary_path,
                        dataset_id=flag_id,
                        manifest_fingerprint=manifest_fingerprint,
                    )
                if not flag_path.exists():
                    raise FileNotFoundError(
                        f"validation pass flag missing for {segment}: {flag_path}"
                    )
                flag_digest = self._read_5a_pass_flag(flag_path)
                if flag_digest != bundle_digest:
                    raise RuntimeError(f"validation bundle digest mismatch for {segment}")
                results[segment] = {
                    "status": "PASS",
                    "bundle_path": str(index_path.parent),
                    "flag_path": str(flag_path),
                    "bundle_digest": bundle_digest,
                    "flag_digest": flag_digest,
                }
                continue

            index_path = bundle_path / "index.json"
            if not index_path.exists():
                raise FileNotFoundError(f"validation bundle index missing for {segment}: {index_path}")
            if segment == "2B":
                index_payload = json.loads(index_path.read_text(encoding="utf-8"))
                if not isinstance(index_payload, list):
                    raise RuntimeError("2B validation bundle index must be a JSON array")
                digest = hashlib.sha256()
                for entry in sorted(index_payload, key=lambda item: str(item.get("path", ""))):
                    path_value = entry.get("path") if isinstance(entry, Mapping) else None
                    if not isinstance(path_value, str) or not path_value:
                        raise RuntimeError("2B validation bundle index entry missing path")
                    target = (bundle_path / path_value).resolve()
                    if not target.exists() or not target.is_file():
                        raise RuntimeError(
                            f"2B validation bundle missing file while computing digest: {path_value}"
                        )
                    digest.update(target.read_bytes())
                bundle_digest = digest.hexdigest()
            elif segment == "3B":
                index_payload = json.loads(index_path.read_text(encoding="utf-8"))
                if not isinstance(index_payload, Mapping):
                    raise RuntimeError("3B validation bundle index must be a JSON object")
                members = index_payload.get("members")
                if not isinstance(members, list):
                    raise RuntimeError("3B validation bundle index missing members list")
                concat = "".join(
                    str(entry["sha256_hex"])
                    for entry in sorted(members, key=lambda item: item.get("path", ""))
                )
                bundle_digest = hashlib.sha256(concat.encode("ascii")).hexdigest()
            else:
                index = load_index(bundle_path)
                bundle_digest = compute_index_digest(bundle_path, index)
            if bundle_override is not None:
                flag_path = bundle_path / "_passed.flag"
                flag_dir = bundle_path
            else:
                flag_path = self._resolve_dataset_path(
                    base_path=base_path,
                    dictionary_path=dictionary_path,
                    dataset_id=flag_id,
                    manifest_fingerprint=manifest_fingerprint,
                )
                flag_dir = flag_path.parent
            if not flag_path.exists():
                raise FileNotFoundError(f"validation pass flag missing for {segment}: {flag_path}")
            flag_digest = read_pass_flag(flag_dir)
            if flag_digest != bundle_digest:
                raise RuntimeError(f"validation bundle digest mismatch for {segment}")
            results[segment] = {
                "status": "PASS",
                "bundle_path": str(bundle_path),
                "flag_path": str(flag_path),
                "bundle_digest": bundle_digest,
                "flag_digest": flag_digest,
            }
        return results

    def _compute_5a_bundle_digest(self, index_path: Path) -> str:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise RuntimeError("5A validation bundle index must be a JSON object")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise RuntimeError("5A validation bundle index missing entries list")
        items: list[tuple[str, str]] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise RuntimeError("5A validation bundle index entry must be an object")
            path = entry.get("path")
            sha = entry.get("sha256_hex")
            if not isinstance(path, str) or not path:
                raise RuntimeError("5A validation bundle index entry missing path")
            if not isinstance(sha, str) or len(sha) != 64:
                raise RuntimeError("5A validation bundle index entry missing sha256_hex")
            items.append((path, sha.lower()))
        items.sort(key=lambda item: item[0])
        concat = "".join(sha for _, sha in items)
        return hashlib.sha256(concat.encode("ascii")).hexdigest()

    def _read_5a_pass_flag(self, flag_path: Path) -> str:
        payload = json.loads(flag_path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise RuntimeError("5A passed flag must be a JSON object")
        digest = payload.get("bundle_digest_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise RuntimeError("5A passed flag missing bundle_digest_sha256")
        return digest.lower()

    def _load_scenario_ids(self, *, base_path: Path, manifest_fingerprint: str) -> list[str]:
        dictionary_path = repository_root() / "contracts/dataset_dictionary/l2/seg_5A/layer2.5A.yaml"
        manifest_path = self._resolve_dataset_path(
            base_path=base_path,
            dictionary_path=dictionary_path,
            dataset_id="scenario_manifest_5A",
            manifest_fingerprint=manifest_fingerprint,
        )
        if not manifest_path.exists():
            fallback = str(manifest_path)
            token = f"fingerprint={manifest_fingerprint}"
            if token in fallback:
                fallback = fallback.replace(token, "fingerprint=baseline", 1)
            fallback_path = Path(fallback)
            if fallback_path.exists():
                manifest_path = fallback_path
        if not manifest_path.exists():
            return ["baseline"]
        df = pl.read_parquet(manifest_path)
        scenario_ids = sorted({str(val) for val in df["scenario_id"].to_list() if val})
        return scenario_ids or ["baseline"]

    def _collect_sealed_assets(
        self,
        *,
        inputs: S0Inputs,
        upstream_bundles: Mapping[str, Mapping[str, object]],
        repo_root: Path,
        dictionary: Mapping[str, object],
        scenario_ids: Iterable[str],
    ) -> list[Mapping[str, object]]:
        rows: list[Mapping[str, object]] = []
        template_args = {
            "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "seed": str(inputs.seed),
        }
        bundle_fingerprints: dict[str, str] = {}
        for segment, info in upstream_bundles.items():
            bundle_path = str(info.get("bundle_path", ""))
            match = re.search(r"fingerprint=([a-f0-9]{64})", bundle_path)
            if match:
                bundle_fingerprints[segment] = match.group(1)
        for spec in self._SEALED_UPSTREAM_DATASETS:
            segment = spec.get("owner_segment", "")
            segment_fingerprint = bundle_fingerprints.get(segment)
            spec_args = (
                {**template_args, "manifest_fingerprint": segment_fingerprint}
                if segment_fingerprint
                else template_args
            )
            sealed_rows = self._seal_dataset(
                base_path=inputs.base_path,
                repo_root=repo_root,
                spec=spec,
                template_args=spec_args,
                notes=f"source_manifest={segment_fingerprint}" if segment_fingerprint else None,
            )
            if segment_fingerprint:
                for row in sealed_rows:
                    row["manifest_fingerprint"] = inputs.upstream_manifest_fingerprint
            rows.extend(sealed_rows)

        for spec in self._SEALED_LAYER2_DATASETS:
            if spec["dataset_id"] == "merchant_zone_scenario_local_5A":
                for scenario_id in scenario_ids:
                    rows.extend(
                        self._seal_dataset(
                            base_path=inputs.base_path,
                            repo_root=repo_root,
                            spec=spec,
                            template_args={**template_args, "scenario_id": scenario_id},
                            notes=f"scenario_id={scenario_id}",
                        )
                    )
            else:
                rows.extend(
                    self._seal_dataset(
                        base_path=inputs.base_path,
                        repo_root=repo_root,
                        spec=spec,
                        template_args=template_args,
                    )
                )

        for dataset_id in self._SEALED_CONFIG_DATASETS:
            entry = self._get_dataset_entry(dictionary, dataset_id)
            path_template = str(entry.get("path") or "").strip()
            if not path_template:
                raise DictionaryError(f"dataset '{dataset_id}' missing path template")
            path = (repo_root / path_template) if path_template.startswith("config/") else inputs.base_path / path_template
            if not path.exists():
                raise FileNotFoundError(f"required config missing for 5B: {path}")
            sha256_hex = self._hash_paths([path])
            manifest_key = self._registry_manifest_key("5B", path_template)
            rows.append(
                {
                    "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
                    "parameter_hash": inputs.parameter_hash,
                    "owner_layer": "layer2",
                    "owner_segment": "5B",
                    "artifact_id": dataset_id,
                    "manifest_key": manifest_key or f"mlr.5B.config.{dataset_id}",
                    "role": "config",
                    "schema_ref": str(entry.get("schema_ref") or ""),
                    "path_template": path_template,
                    "partition_keys": list(parse_partition_keys(path_template)),
                    "sha256_hex": sha256_hex,
                    "status": "REQUIRED",
                    "read_scope": "METADATA_ONLY",
                }
            )

        return rows

    def _seal_dataset(
        self,
        *,
        base_path: Path,
        repo_root: Path,
        spec: Mapping[str, str],
        template_args: Mapping[str, object],
        notes: str | None = None,
    ) -> list[Mapping[str, object]]:
        dictionary_path = repo_root / spec["dictionary_rel_path"]
        dataset_id = spec["dataset_id"]
        entry = self._get_dataset_entry(self._load_dictionary(dictionary_path), dataset_id)
        path_template = str(entry.get("path") or "").strip()
        if not path_template:
            raise DictionaryError(f"dataset '{dataset_id}' missing path template")
        rendered = path_template.format(**template_args)
        base_dir = repo_root if rendered.startswith("config/") or rendered.startswith("contracts/") else base_path
        paths = sorted(base_dir.glob(rendered))
        if not paths:
            raise FileNotFoundError(f"sealed input '{dataset_id}' missing at {base_dir / rendered}")
        sha256_hex = self._hash_paths(paths)
        manifest_key = self._registry_manifest_key(spec["owner_segment"], path_template)
        row = {
            "manifest_fingerprint": template_args.get("manifest_fingerprint"),
            "parameter_hash": template_args.get("parameter_hash"),
            "owner_layer": spec.get("owner_layer"),
            "owner_segment": spec.get("owner_segment"),
            "artifact_id": dataset_id,
            "manifest_key": manifest_key or f"mlr.{spec.get('owner_segment')}.dataset.{dataset_id}",
            "role": spec.get("role", "upstream_egress"),
            "schema_ref": str(entry.get("schema_ref") or ""),
            "path_template": path_template,
            "partition_keys": list(parse_partition_keys(path_template)),
            "sha256_hex": sha256_hex,
            "status": "REQUIRED",
            "read_scope": spec.get("read_scope", "ROW_LEVEL"),
        }
        if notes:
            row["notes"] = notes
        return [row]

    def _resolve_bundle_path(
        self,
        *,
        base_path: Path,
        dictionary_path: Path,
        bundle_id: str,
        manifest_fingerprint: str,
        override: Path | None,
    ) -> Path:
        if override is not None:
            return Path(override).absolute()
        return self._resolve_dataset_path(
            base_path=base_path,
            dictionary_path=dictionary_path,
            dataset_id=bundle_id,
            manifest_fingerprint=manifest_fingerprint,
        )

    def _resolve_dataset_path(
        self,
        *,
        base_path: Path,
        dictionary_path: Path,
        dataset_id: str,
        manifest_fingerprint: str,
    ) -> Path:
        dictionary = self._load_dictionary(dictionary_path)
        entry = self._get_dataset_entry(dictionary, dataset_id)
        path_template = str(entry.get("path") or "").strip()
        if not path_template:
            raise DictionaryError(f"dataset '{dataset_id}' missing path template")
        rendered = path_template.format(manifest_fingerprint=manifest_fingerprint)
        base_dir = repository_root() if rendered.startswith("config/") or rendered.startswith("contracts/") else base_path
        return base_dir / rendered

    def _write_sealed_inputs(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object],
        rows: list[Mapping[str, object]],
        expected_digest: str,
    ) -> Path:
        path_template = render_dataset_path(
            dataset_id="sealed_inputs_5B",
            template_args={"manifest_fingerprint": inputs.upstream_manifest_fingerprint},
            dictionary=dictionary,
        )
        output_path = inputs.output_base_path / path_template
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df = pl.DataFrame(rows)
        sort_cols = [
            "owner_layer",
            "owner_segment",
            "artifact_id",
            "manifest_key",
            "role",
            "schema_ref",
            "path_template",
            "sha256_hex",
            "status",
            "read_scope",
        ]
        df = df.sort(sort_cols)
        df.write_parquet(output_path)
        digest = compute_sealed_inputs_digest(df.to_dicts())
        if digest != expected_digest:
            raise RuntimeError("sealed_inputs_5B digest mismatch after write")
        return output_path

    def _write_receipt(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object],
        upstream_bundles: Mapping[str, Mapping[str, object]],
        sealed_inputs_digest: str,
        sealed_inputs_row_count: int,
        gate_verify_ms: int,
        run_started_at: datetime,
        scenario_ids: Iterable[str],
    ) -> Path:
        payload = {
            "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "seed": inputs.seed,
            "run_id": inputs.run_id,
            "created_utc": run_started_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "upstream_segments": upstream_bundles,
            "scenario_set": list(scenario_ids),
            "sealed_inputs_digest": sealed_inputs_digest,
            "sealed_inputs_row_count": sealed_inputs_row_count,
            "spec_version": "1.0.0",
            "gate_verify_ms": gate_verify_ms,
        }
        path_template = render_dataset_path(
            dataset_id="s0_gate_receipt_5B",
            template_args={"manifest_fingerprint": inputs.upstream_manifest_fingerprint},
            dictionary=dictionary,
        )
        output_path = inputs.output_base_path / path_template
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return output_path

    def _write_segment_run_report(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object],
        sealed_inputs_path: Path,
        receipt_path: Path,
        gate_verify_ms: int,
        sealed_inputs_digest: str,
    ) -> Path:
        path_template = render_dataset_path(
            dataset_id="segment_state_runs",
            template_args={},
            dictionary=dictionary,
        )
        output_path = inputs.output_base_path / path_template
        payload = {
            "layer": "layer2",
            "segment": "5B",
            "state": "S0",
            "parameter_hash": inputs.parameter_hash,
            "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            "run_id": inputs.run_id,
            "status": "PASS",
            "sealed_inputs_path": sealed_inputs_path.as_posix(),
            "sealed_inputs_digest": sealed_inputs_digest,
            "receipt_path": receipt_path.as_posix(),
            "gate_verify_ms": gate_verify_ms,
        }
        key = SegmentStateKey(
            layer="layer2",
            segment="5B",
            state="S0",
            manifest_fingerprint=inputs.upstream_manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            run_id=inputs.run_id,
        )
        return write_segment_state_run_report(path=output_path, key=key, payload=payload)

    def _registry_manifest_key(self, segment: str, path_template: str) -> str | None:
        registry_path = repository_root() / "contracts" / "artefact_registry" / f"artefact_registry_{segment}.yaml"
        if not registry_path.exists():
            return None
        cache_key = str(registry_path)
        if cache_key not in self._registry_cache:
            registry_payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
            artefacts = registry_payload.get("artefacts")
            mapping: dict[str, str] = {}
            if isinstance(artefacts, Iterable):
                for entry in artefacts:
                    if not isinstance(entry, Mapping):
                        continue
                    path = entry.get("path")
                    manifest_key = entry.get("manifest_key")
                    if isinstance(path, str) and isinstance(manifest_key, str):
                        mapping[path] = manifest_key
            self._registry_cache[cache_key] = mapping
        return self._registry_cache[cache_key].get(path_template)

    def _load_dictionary(self, dictionary_path: Path) -> Mapping[str, object]:
        if dictionary_path not in self._dictionary_cache:
            payload = yaml.safe_load(dictionary_path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, MutableMapping):
                raise DictionaryError(f"dictionary '{dictionary_path}' must decode to a mapping")
            self._dictionary_cache[dictionary_path] = payload
        return self._dictionary_cache[dictionary_path]

    def _get_dataset_entry(
        self, dictionary: Mapping[str, object], dataset_id: str
    ) -> Mapping[str, object]:
        for section_key in (
            "datasets",
            "reference_data",
            "policies",
            "artefacts",
            "validation",
            "reference",
            "egress",
            "parameters",
            "ingress",
            "model",
            "logs",
            "reports",
        ):
            section = dictionary.get(section_key)
            if isinstance(section, Mapping):
                entry = section.get(dataset_id)
                if isinstance(entry, Mapping):
                    return entry
            elif isinstance(section, Iterable):
                for item in section:
                    if isinstance(item, Mapping) and item.get("id") == dataset_id:
                        return item
        raise DictionaryError(f"dataset '{dataset_id}' not present in dictionary")

    def _hash_paths(self, paths: Iterable[Path]) -> str:
        items = []
        for path in paths:
            if path.is_dir():
                for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
                    digest = self._hash_file(file_path)
                    items.append((file_path.as_posix(), digest))
            else:
                digest = self._hash_file(path)
                items.append((path.as_posix(), digest))
        items.sort()
        sha = hashlib.sha256()
        for path_str, digest in items:
            sha.update(path_str.encode("utf-8"))
            sha.update(digest.encode("utf-8"))
        return sha.hexdigest()

    @staticmethod
    def _hash_file(path: Path) -> str:
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        return sha.hexdigest()


def _sealed_inputs_sort_key(row: Mapping[str, object]) -> tuple[str, ...]:
    return (
        str(row.get("owner_layer") or ""),
        str(row.get("owner_segment") or ""),
        str(row.get("artifact_id") or ""),
        str(row.get("manifest_key") or ""),
        str(row.get("role") or ""),
        str(row.get("schema_ref") or ""),
        str(row.get("path_template") or ""),
        str(row.get("sha256_hex") or ""),
        str(row.get("status") or ""),
        str(row.get("read_scope") or ""),
    )


__all__ = ["S0GateRunner", "S0Inputs", "S0Outputs"]
