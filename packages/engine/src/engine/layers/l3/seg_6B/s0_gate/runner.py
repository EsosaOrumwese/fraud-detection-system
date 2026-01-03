"""Segment 6B S0 gate runner."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Iterable, Mapping, MutableMapping, Sequence

import polars as pl
import yaml

from engine.layers.l3.seg_6B.shared.control_plane import compute_sealed_inputs_digest, parse_partition_keys
from engine.layers.l3.seg_6B.shared.dictionary import (
    DictionaryError,
    get_dataset_entry,
    load_dictionary,
    repository_root,
    render_dataset_path,
)
from engine.layers.l3.shared.bundle import compute_index_digest, load_index_file, read_pass_flag

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class S0Inputs:
    """Configuration required to execute 6B S0."""

    base_path: Path
    output_base_path: Path
    manifest_fingerprint: str
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
    validation_bundle_5b: Path | None = None
    validation_bundle_6a: Path | None = None

    def __post_init__(self) -> None:
        base = Path(self.base_path).absolute()
        out = Path(self.output_base_path).absolute()
        object.__setattr__(self, "base_path", base)
        object.__setattr__(self, "output_base_path", out)
        if len(self.manifest_fingerprint) != 64:
            raise ValueError("manifest_fingerprint must be 64 hex characters")
        int(self.manifest_fingerprint, 16)
        if len(self.parameter_hash) != 64:
            raise ValueError("parameter_hash must be 64 hex characters")
        int(self.parameter_hash, 16)
        if not self.run_id:
            raise ValueError("run_id must be provided for 6B S0")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


@dataclass(frozen=True)
class S0Outputs:
    """Outputs from 6B S0 gate."""

    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    sealed_inputs_digest: str


class S0GateRunner:
    """High-level helper that wires together the 6B S0 workflow."""

    _UPSTREAM_SEGMENTS = ("1A", "1B", "2A", "2B", "3A", "3B", "5A", "5B", "6A")
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
            "index_id": "validation_bundle_index_5A",
            "flag_id": "validation_passed_flag_5A",
            "override_attr": "validation_bundle_5a",
        },
        "5B": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l2/seg_5B/layer2.5B.yaml",
            "index_id": "validation_bundle_index_5B",
            "flag_id": "validation_passed_flag_5B",
            "override_attr": "validation_bundle_5b",
        },
        "6A": {
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "index_id": "validation_bundle_index_6A",
            "flag_id": "validation_passed_flag_6A",
            "override_attr": "validation_bundle_6a",
        },
    }

    _SEALED_UPSTREAM_DATASETS: tuple[Mapping[str, str], ...] = (
        {
            "owner_layer": "1",
            "owner_segment": "1A",
            "dataset_id": "outlet_catalogue",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "1",
            "owner_segment": "1B",
            "dataset_id": "site_locations",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "1",
            "owner_segment": "2A",
            "dataset_id": "site_timezones",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "1",
            "owner_segment": "2A",
            "dataset_id": "tz_timetable_cache",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml",
            "role": "reference_data",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "1",
            "owner_segment": "3A",
            "dataset_id": "zone_alloc",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "1",
            "owner_segment": "3A",
            "dataset_id": "zone_alloc_universe_hash",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml",
            "role": "reference_data",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "1",
            "owner_segment": "3B",
            "dataset_id": "virtual_classification_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "1",
            "owner_segment": "3B",
            "dataset_id": "virtual_settlement_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "1",
            "owner_segment": "3B",
            "dataset_id": "edge_universe_hash_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "reference_data",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "1",
            "owner_segment": "3B",
            "dataset_id": "virtual_routing_policy_3B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml",
            "role": "contract",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "2",
            "owner_segment": "5A",
            "dataset_id": "merchant_zone_profile_5A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l2/seg_5A/layer2.5A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "2",
            "owner_segment": "5B",
            "dataset_id": "arrival_events_5B",
            "dictionary_rel_path": "contracts/dataset_dictionary/l2/seg_5B/layer2.5B.yaml",
            "role": "upstream_egress",
            "read_scope": "METADATA_ONLY",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s1_party_base_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s2_account_base_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s3_instrument_base_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s4_device_base_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s4_ip_base_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s4_device_links_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s4_ip_links_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s5_party_fraud_roles_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s5_account_fraud_roles_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s5_merchant_fraud_roles_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s5_device_fraud_roles_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
        {
            "owner_layer": "3",
            "owner_segment": "6A",
            "dataset_id": "s5_ip_fraud_roles_6A",
            "dictionary_rel_path": "contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml",
            "role": "upstream_egress",
            "read_scope": "ROW_LEVEL",
        },
    )

    _SEALED_CONFIG_DATASETS: tuple[str, ...] = (
        "attachment_policy_6B",
        "sessionisation_policy_6B",
        "behaviour_config_6B",
        "behaviour_prior_pack_6B",
        "rng_profile_layer3",
        "rng_policy_6B",
        "flow_shape_policy_6B",
        "amount_model_6B",
        "timing_policy_6B",
        "flow_rng_policy_6B",
        "fraud_campaign_catalogue_config_6B",
        "fraud_overlay_policy_6B",
        "fraud_rng_policy_6B",
        "truth_labelling_policy_6B",
        "bank_view_policy_6B",
        "delay_models_6B",
        "case_policy_6B",
        "label_rng_policy_6B",
        "segment_validation_policy_6B",
    )

    def __init__(self) -> None:
        self._dictionary_cache: dict[Path, Mapping[str, object] | Sequence[object]] = {}
        self._registry_cache: dict[str, Mapping[str, str]] = {}

    def run(self, inputs: S0Inputs) -> S0Outputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        repo_root = repository_root()
        run_started_at = datetime.now(timezone.utc)
        gate_timer = time.perf_counter()

        self._validation_bundle_1a = inputs.validation_bundle_1a
        self._validation_bundle_1b = inputs.validation_bundle_1b
        self._validation_bundle_2a = inputs.validation_bundle_2a
        self._validation_bundle_2b = inputs.validation_bundle_2b
        self._validation_bundle_3a = inputs.validation_bundle_3a
        self._validation_bundle_3b = inputs.validation_bundle_3b
        self._validation_bundle_5a = inputs.validation_bundle_5a
        self._validation_bundle_5b = inputs.validation_bundle_5b
        self._validation_bundle_6a = inputs.validation_bundle_6a

        upstream_bundles = self._verify_upstream_bundles(
            base_path=inputs.base_path,
            manifest_fingerprint=inputs.manifest_fingerprint,
        )
        gate_verify_ms = int(round((time.perf_counter() - gate_timer) * 1000))

        sealed_rows = self._collect_sealed_assets(
            inputs=inputs,
            upstream_bundles=upstream_bundles,
            repo_root=repo_root,
            dictionary=dictionary,
        )
        sealed_inputs_digest = compute_sealed_inputs_digest(
            sorted(sealed_rows, key=lambda row: (row["owner_layer"], row["owner_segment"], row["manifest_key"]))
        )
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
            gate_verify_ms=gate_verify_ms,
            run_started_at=run_started_at,
        )

        return S0Outputs(
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            receipt_path=receipt_path,
            sealed_inputs_path=sealed_inputs_path,
            sealed_inputs_digest=sealed_inputs_digest,
        )

    def _verify_upstream_bundles(
        self, *, base_path: Path, manifest_fingerprint: str
    ) -> dict[str, Mapping[str, object]]:
        results: dict[str, Mapping[str, object]] = {}
        for segment in self._UPSTREAM_SEGMENTS:
            spec = self._UPSTREAM_BUNDLE_SPECS.get(segment)
            if spec is None:
                continue
            if segment in {"5A", "5B"}:
                results[segment] = self._verify_layer2_bundle(
                    segment=segment,
                    base_path=base_path,
                    manifest_fingerprint=manifest_fingerprint,
                    dictionary_path=repository_root() / spec["dictionary_rel_path"],
                    bundle_id=spec.get("bundle_id"),
                    index_id=spec.get("index_id"),
                    override=getattr(self, spec["override_attr"], None),
                    flag_id=spec["flag_id"],
                )
                continue
            dictionary_path = repository_root() / spec["dictionary_rel_path"]
            override_attr = spec["override_attr"]
            override = getattr(self, override_attr, None)
            bundle_path, index_path = self._resolve_bundle_and_index(
                base_path=base_path,
                dictionary_path=dictionary_path,
                manifest_fingerprint=manifest_fingerprint,
                bundle_id=spec.get("bundle_id"),
                index_id=spec.get("index_id"),
                override=override,
            )
            if not bundle_path.exists() or not bundle_path.is_dir():
                raise FileNotFoundError(f"validation bundle missing for {segment}: {bundle_path}")
            if not index_path.exists():
                raise FileNotFoundError(f"validation bundle index missing for {segment}: {index_path}")
            index = load_index_file(index_path, bundle_path)
            bundle_digest = compute_index_digest(bundle_path, index)
            flag_path = self._resolve_dataset_path(
                base_path=base_path,
                dictionary_path=dictionary_path,
                dataset_id=spec["flag_id"],
                manifest_fingerprint=manifest_fingerprint,
            )
            if not flag_path.exists():
                raise FileNotFoundError(f"validation pass flag missing for {segment}: {flag_path}")
            flag_digest = read_pass_flag(flag_path.parent if flag_path.is_file() else flag_path)
            if flag_digest != bundle_digest:
                raise RuntimeError(f"validation bundle digest mismatch for {segment}")
            results[segment] = {
                "status": "PASS",
                "bundle_path": str(bundle_path),
                "bundle_sha256": bundle_digest,
                "flag_path": str(flag_path),
            }
        return results

    def _verify_layer2_bundle(
        self,
        *,
        segment: str,
        base_path: Path,
        manifest_fingerprint: str,
        dictionary_path: Path,
        bundle_id: str | None,
        index_id: str | None,
        override: Path | None,
        flag_id: str,
    ) -> Mapping[str, object]:
        bundle_path, index_path = self._resolve_bundle_and_index(
            base_path=base_path,
            dictionary_path=dictionary_path,
            manifest_fingerprint=manifest_fingerprint,
            bundle_id=bundle_id,
            index_id=index_id,
            override=override,
        )
        if not bundle_path.exists() or not bundle_path.is_dir():
            raise FileNotFoundError(f"validation bundle missing for {segment}: {bundle_path}")
        if not index_path.exists():
            raise FileNotFoundError(f"validation bundle index missing for {segment}: {index_path}")
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        entries = index_payload.get("entries") if isinstance(index_payload, dict) else None
        if not isinstance(entries, list):
            raise ValueError(f"{segment} validation index missing entries list: {index_path}")
        bundle_digest = self._compute_layer2_digest(segment, entries, base_path)
        flag_path = self._resolve_dataset_path(
            base_path=base_path,
            dictionary_path=dictionary_path,
            dataset_id=flag_id,
            manifest_fingerprint=manifest_fingerprint,
        )
        if not flag_path.exists():
            raise FileNotFoundError(f"validation pass flag missing for {segment}: {flag_path}")
        flag_payload = json.loads(flag_path.read_text(encoding="utf-8"))
        flag_digest = str(flag_payload.get("bundle_digest_sha256") or "")
        if flag_digest != bundle_digest:
            raise RuntimeError(f"validation bundle digest mismatch for {segment}")
        return {
            "status": "PASS",
            "bundle_path": str(bundle_path),
            "bundle_sha256": bundle_digest,
            "flag_path": str(flag_path),
        }

    @staticmethod
    def _compute_layer2_digest(
        segment: str, entries: Sequence[Mapping[str, object]], base_path: Path
    ) -> str:
        if segment == "5A":
            concat = "".join(str(entry.get("sha256_hex") or "") for entry in entries)
            return hashlib.sha256(concat.encode("ascii")).hexdigest()
        buffer = bytearray()
        for entry in entries:
            raw_path = str(entry.get("path") or "")
            target = Path(raw_path)
            if not target.is_absolute():
                target = base_path / raw_path
            buffer.extend(target.read_bytes())
        return hashlib.sha256(buffer).hexdigest()

    def _collect_sealed_assets(
        self,
        *,
        inputs: S0Inputs,
        upstream_bundles: Mapping[str, Mapping[str, object]],
        repo_root: Path,
        dictionary: Mapping[str, object] | Sequence[object],
    ) -> list[Mapping[str, object]]:
        rows: list[Mapping[str, object]] = []
        template_args = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "seed": str(inputs.seed),
        }

        for spec in self._SEALED_UPSTREAM_DATASETS:
            rows.extend(
                self._seal_dataset(
                    base_path=inputs.base_path,
                    repo_root=repo_root,
                    spec=spec,
                    template_args=template_args,
                    notes=None,
                )
            )

        for dataset_id in self._SEALED_CONFIG_DATASETS:
            entry = get_dataset_entry(dataset_id, dictionary=dictionary)
            path_template = str(entry.get("path") or "").strip()
            if not path_template:
                raise DictionaryError(f"dataset '{dataset_id}' missing path template")
            path = repo_root / path_template
            if not path.exists():
                raise FileNotFoundError(f"required config missing for 6B: {path}")
            sha256_hex = self._hash_paths([path])
            manifest_key = self._registry_manifest_key("6B", path_template)
            rows.append(
                {
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "owner_layer": 3,
                    "owner_segment": "6B",
                    "manifest_key": manifest_key or f"mlr.6B.config.{dataset_id}",
                    "path_template": path_template,
                    "partition_keys": list(parse_partition_keys(path_template)),
                    "schema_ref": str(entry.get("schema_ref") or ""),
                    "role": self._infer_role(dataset_id),
                    "status": self._normalise_status(entry.get("status")),
                    "read_scope": self._infer_read_scope(entry),
                    "sha256_hex": sha256_hex,
                }
            )

        rows.extend(self._seal_contracts(inputs.manifest_fingerprint))

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
        base_dir = repo_root if path_template.startswith(("config/", "contracts/")) else base_path
        glob_pattern = self._template_to_glob(path_template, template_args)
        paths = sorted(base_dir.glob(glob_pattern))
        if not paths:
            raise FileNotFoundError(f"sealed input '{dataset_id}' missing at {base_dir / glob_pattern}")
        sha256_hex = self._hash_paths(paths)
        manifest_key = self._registry_manifest_key(spec["owner_segment"], path_template)
        row = {
            "manifest_fingerprint": template_args.get("manifest_fingerprint"),
            "owner_layer": int(spec.get("owner_layer", "3")),
            "owner_segment": spec.get("owner_segment"),
            "manifest_key": manifest_key or f"mlr.{spec.get('owner_segment')}.dataset.{dataset_id}",
            "path_template": path_template,
            "partition_keys": list(parse_partition_keys(path_template)),
            "schema_ref": str(entry.get("schema_ref") or ""),
            "role": spec.get("role", "upstream_egress"),
            "status": self._normalise_status(entry.get("status")),
            "read_scope": spec.get("read_scope", "ROW_LEVEL"),
            "sha256_hex": sha256_hex,
            "upstream_bundle_id": f"validation_bundle_{spec.get('owner_segment')}",
        }
        if notes:
            row["notes"] = notes
        return [row]

    def _seal_contracts(self, manifest_fingerprint: str) -> list[Mapping[str, object]]:
        repo_root = repository_root()
        contract_specs = (
            {
                "logical_id": "schemas.layer3.yaml",
                "path": repo_root / "contracts/schemas/layer3/schemas.layer3.yaml",
                "schema_ref": "schemas.layer3.yaml",
                "role": "contract",
            },
            {
                "logical_id": "schemas.6B.yaml",
                "path": repo_root / "contracts/schemas/layer3/schemas.6B.yaml",
                "schema_ref": "schemas.6B.yaml",
                "role": "contract",
            },
            {
                "logical_id": "dataset_dictionary.layer3.6B.yaml",
                "path": repo_root / "contracts/dataset_dictionary/l3/seg_6B/layer3.6B.yaml",
                "schema_ref": "schemas.layer3.yaml",
                "role": "contract",
            },
            {
                "logical_id": "artefact_registry_6B.yaml",
                "path": repo_root / "contracts/artefact_registry/artefact_registry_6B.yaml",
                "schema_ref": "schemas.layer3.yaml",
                "role": "contract",
            },
        )
        rows: list[Mapping[str, object]] = []
        for spec in contract_specs:
            path = Path(spec["path"])
            if not path.exists():
                raise FileNotFoundError(f"missing 6B contract file: {path}")
            sha256_hex = self._hash_paths([path])
            path_template = str(path.relative_to(repo_root)).replace("\\", "/")
            rows.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "owner_layer": 3,
                    "owner_segment": "6B",
                    "manifest_key": f"mlr.6B.contract.{spec['logical_id']}",
                    "path_template": path_template,
                    "partition_keys": [],
                    "schema_ref": spec["schema_ref"],
                    "role": spec["role"],
                    "status": "REQUIRED",
                    "read_scope": "METADATA_ONLY",
                    "sha256_hex": sha256_hex,
                }
            )
        return rows
    def _resolve_bundle_and_index(
        self,
        *,
        base_path: Path,
        dictionary_path: Path,
        manifest_fingerprint: str,
        bundle_id: str | None,
        index_id: str | None,
        override: Path | None,
    ) -> tuple[Path, Path]:
        if override is not None:
            override = Path(override).absolute()
            if override.is_file():
                return override.parent, override
            return override, override / "index.json"

        template_args = {"manifest_fingerprint": manifest_fingerprint, "fingerprint": manifest_fingerprint}
        if index_id:
            entry = self._get_dataset_entry(self._load_dictionary(dictionary_path), index_id)
            index_template = str(entry.get("path") or "").strip()
            if not index_template:
                raise DictionaryError(f"dataset '{index_id}' missing path template")
            index_path = base_path / index_template.format(**template_args)
            return index_path.parent, index_path

        if not bundle_id:
            raise DictionaryError("bundle_id missing while resolving validation bundle")
        entry = self._get_dataset_entry(self._load_dictionary(dictionary_path), bundle_id)
        bundle_template = str(entry.get("path") or "").strip()
        if not bundle_template:
            raise DictionaryError(f"dataset '{bundle_id}' missing path template")
        bundle_path = base_path / bundle_template.format(**template_args)
        return bundle_path, bundle_path / "index.json"

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
        base_dir = repository_root() if rendered.startswith(("config/", "contracts/")) else base_path
        return base_dir / rendered

    def _write_sealed_inputs(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object] | Sequence[object],
        rows: Sequence[Mapping[str, object]],
        expected_digest: str,
    ) -> Path:
        output_path = inputs.output_base_path / render_dataset_path(
            dataset_id="sealed_inputs_6B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df = pl.DataFrame(rows)
        df.write_parquet(output_path)
        digest = compute_sealed_inputs_digest(
            df.sort(["owner_layer", "owner_segment", "manifest_key"]).to_dicts()
        )
        if digest != expected_digest:
            raise RuntimeError("sealed_inputs_6B digest mismatch after write")
        return output_path

    def _write_receipt(
        self,
        *,
        inputs: S0Inputs,
        dictionary: Mapping[str, object] | Sequence[object],
        upstream_bundles: Mapping[str, Mapping[str, object]],
        sealed_inputs_digest: str,
        gate_verify_ms: int,
        run_started_at: datetime,
    ) -> Path:
        payload = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "spec_version_6B": "1.0.0",
            "upstream_segments": upstream_bundles,
            "contracts_6B": self._contracts_payload(),
            "sealed_inputs_digest_6B": sealed_inputs_digest,
        }
        path_template = render_dataset_path(
            dataset_id="s0_gate_receipt_6B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        output_path = inputs.output_base_path / path_template
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        logger.info(
            "Segment6B S0 gate: verified %s upstream segments in %sms",
            len(upstream_bundles),
            gate_verify_ms,
        )
        logger.info("Segment6B S0 gate: sealed_inputs_digest=%s", sealed_inputs_digest)
        logger.info("Segment6B S0 gate: started_at=%s", run_started_at.isoformat())
        return output_path

    def _contracts_payload(self) -> Mapping[str, Mapping[str, str]]:
        repo_root = repository_root()
        contracts = {
            "schemas.layer3.yaml": repo_root / "contracts/schemas/layer3/schemas.layer3.yaml",
            "schemas.6B.yaml": repo_root / "contracts/schemas/layer3/schemas.6B.yaml",
            "dataset_dictionary.layer3.6B.yaml": repo_root / "contracts/dataset_dictionary/l3/seg_6B/layer3.6B.yaml",
            "artefact_registry_6B.yaml": repo_root / "contracts/artefact_registry/artefact_registry_6B.yaml",
        }
        payload: dict[str, Mapping[str, str]] = {}
        for logical_id, path in contracts.items():
            if not path.exists():
                raise FileNotFoundError(f"missing 6B contract file: {path}")
            payload[logical_id] = {
                "logical_id": logical_id,
                "path": str(path),
                "sha256_hex": self._hash_paths([path]),
                "schema_ref": "",
                "role": "contract",
            }
        return payload

    def _registry_manifest_key(self, segment: str, path_template: str) -> str | None:
        registry_path = repository_root() / "contracts" / "artefact_registry" / f"artefact_registry_{segment}.yaml"
        if not registry_path.exists():
            return None
        cache_key = str(registry_path)
        if cache_key not in self._registry_cache:
            registry_payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
            mapping: dict[str, str] = {}
            if isinstance(registry_payload, Sequence):
                for entry in registry_payload:
                    if isinstance(entry, Mapping):
                        path = entry.get("path_template") or entry.get("path")
                        manifest_key = entry.get("manifest_key")
                        if isinstance(path, str) and isinstance(manifest_key, str):
                            mapping[path.replace("\\", "/")] = manifest_key
            self._registry_cache[cache_key] = mapping
        return self._registry_cache[cache_key].get(path_template.replace("\\", "/"))

    def _load_dictionary(self, dictionary_path: Path) -> Mapping[str, object] | Sequence[object]:
        if dictionary_path not in self._dictionary_cache:
            payload = yaml.safe_load(dictionary_path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, (MutableMapping, list)):
                raise DictionaryError(f"dictionary '{dictionary_path}' must decode to a mapping or list")
            self._dictionary_cache[dictionary_path] = payload
        return self._dictionary_cache[dictionary_path]

    @staticmethod
    def _iter_entries(payload: Mapping[str, object] | Sequence[object]) -> Iterable[Mapping[str, object]]:
        if isinstance(payload, Mapping):
            for section_key in (
                "datasets",
                "reference_data",
                "policies",
                "artefacts",
                "validation",
                "reference",
                "model",
                "logs",
                "reports",
            ):
                section = payload.get(section_key)
                if isinstance(section, Mapping):
                    for entry in section.values():
                        if isinstance(entry, Mapping):
                            yield entry
                elif isinstance(section, Sequence) and not isinstance(section, (str, bytes)):
                    for entry in section:
                        if isinstance(entry, Mapping):
                            yield entry
        elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
            for entry in payload:
                if isinstance(entry, Mapping):
                    yield entry

    def _get_dataset_entry(
        self, dictionary: Mapping[str, object] | Sequence[object], dataset_id: str
    ) -> Mapping[str, object]:
        for entry in self._iter_entries(dictionary):
            if entry.get("id") == dataset_id:
                return entry
        raise DictionaryError(f"dataset '{dataset_id}' not present in dictionary")

    @staticmethod
    def _template_to_glob(template: str, template_args: Mapping[str, object]) -> str:
        rendered = S0GateRunner._partial_format_template(template, template_args)
        return re.sub(r"\{[^}]+\}", "*", rendered).replace("\\", "/")

    @staticmethod
    def _partial_format_template(template: str, template_args: Mapping[str, object]) -> str:
        formatter = Formatter()
        rendered: list[str] = []
        for literal, field, format_spec, _ in formatter.parse(template):
            rendered.append(literal)
            if field is None:
                continue
            if field in template_args:
                rendered.append(format(template_args[field], format_spec))
            else:
                rendered.append(f"{{{field}}}")
        return "".join(rendered)

    @staticmethod
    def _infer_read_scope(entry: Mapping[str, object]) -> str:
        fmt = str(entry.get("format") or "").lower()
        if fmt in {"yaml", "json", "text", "flag", "directory"}:
            return "METADATA_ONLY"
        return "ROW_LEVEL"

    @staticmethod
    def _infer_role(dataset_id: str) -> str:
        lowered = dataset_id.lower()
        if lowered.startswith("prior_"):
            return "prior"
        if lowered.startswith("taxonomy_"):
            return "taxonomy"
        if "policy" in lowered or "rules" in lowered:
            return "policy"
        return "config"

    @staticmethod
    def _normalise_status(raw_value: object) -> str:
        if isinstance(raw_value, str):
            candidate = raw_value.strip().upper()
            if candidate in {"REQUIRED", "OPTIONAL", "IGNORED"}:
                return candidate
        return "REQUIRED"

    def _hash_paths(self, paths: Iterable[Path]) -> str:
        items = []
        for path in paths:
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


__all__ = ["S0GateRunner", "S0Inputs", "S0Outputs"]
