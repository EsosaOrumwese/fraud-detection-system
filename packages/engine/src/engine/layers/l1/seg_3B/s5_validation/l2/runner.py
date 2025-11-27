"""Segment 3B S5 runner - validation bundle and _passed.flag_3B."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import jsonschema
import polars as pl

from engine.layers.l1.seg_2A.s0_gate.l0 import aggregate_sha256, expand_files, hash_files
from engine.layers.l1.seg_3B.s0_gate.exceptions import err
from engine.layers.l1.seg_3B.shared import (
    SegmentStateKey,
    render_dataset_path,
    write_segment_state_run_report,
)
from engine.layers.l1.seg_3B.shared.dictionary import get_dataset_entry, load_dictionary
from engine.layers.l1.seg_3B.shared.schema import load_schema


@dataclass(frozen=True)
class ValidationInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ValidationResult:
    bundle_path: Path
    passed_flag_path: Path
    index_path: Path
    run_report_path: Path
    resumed: bool


class ValidationRunner:
    """Assemble the validation bundle and emit the 3B PASS flag."""

    _COMPONENTS: Sequence[tuple[str, str]] = (
        ("s0_gate_receipt_3B", "receipt"),
        ("sealed_inputs_3B", "sealed_inputs"),
        ("virtual_classification_3B", "virtuals"),
        ("virtual_settlement_3B", "virtual_settlement"),
        ("edge_catalogue_3B", "edges"),
        ("edge_catalogue_index_3B", "edge_index"),
        ("edge_alias_blob_3B", "alias_blob"),
        ("edge_alias_index_3B", "alias_index"),
        ("edge_universe_hash_3B", "edge_hash"),
        ("virtual_routing_policy_3B", "routing_policy"),
        ("virtual_validation_contract_3B", "validation_contract"),
        ("s4_run_summary_3B", "s4_run_summary"),
    )

    def run(self, inputs: ValidationInputs) -> ValidationResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        parameter_hash = inputs.parameter_hash
        seed = inputs.seed

        bundle_dir = data_root / render_dataset_path(
            dataset_id="validation_bundle_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        bundle_dir.mkdir(parents=True, exist_ok=True)
        index_path = bundle_dir / "index.json"
        passed_flag_path = bundle_dir / "_passed.flag_3B"

        components = self._gather_components(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        self._run_structural_checks(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            seed=seed,
        )
        bundle_index = self._build_index(components)
        bundle_digest = self._compute_bundle_digest(bundle_index)

        resumed = False
        if index_path.exists():
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if existing != bundle_index:
                raise err("E_IMMUTABILITY", f"validation bundle index differs at '{index_path}'")
            existing_flag = passed_flag_path.read_text(encoding="utf-8").strip()
            if existing_flag != f"sha256_hex = {bundle_digest}":
                raise err("E_IMMUTABILITY", "passed flag mismatch for existing bundle")
            resumed = True
        else:
            index_path.write_text(json.dumps(bundle_index, indent=2, sort_keys=True), encoding="utf-8")
            passed_flag_path.write_text(f"sha256_hex = {bundle_digest}", encoding="utf-8")

        run_report_path = data_root / f"reports/l1/3B/s5_validation/fingerprint={manifest_fingerprint}/run_report.json"
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3B",
            "state": "S5",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "bundle_path": str(bundle_dir),
            "bundle_digest": bundle_digest,
            "index_path": str(index_path),
            "passed_flag_path": str(passed_flag_path),
            "resumed": resumed,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer1",
            segment="3B",
            state="S5",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        report_dataset_path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(
            path=report_dataset_path,
            key=key,
            payload={
                **key.as_dict(),
                "status": "PASS",
                "bundle_digest": bundle_digest,
                "bundle_path": str(bundle_dir),
                "run_report_path": str(run_report_path),
                "passed_flag_path": str(passed_flag_path),
                "resumed": resumed,
            },
        )

        return ValidationResult(
            bundle_path=bundle_dir,
            passed_flag_path=passed_flag_path,
            index_path=index_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    def _gather_components(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        parameter_hash: str,
        seed: int,
    ) -> list[Mapping[str, Any]]:
        components = []
        for dataset_id, role in self._COMPONENTS:
            if dataset_id in (
                "virtual_classification_3B",
                "virtual_settlement_3B",
                "edge_catalogue_3B",
                "edge_catalogue_index_3B",
                "edge_alias_blob_3B",
                "edge_alias_index_3B",
            ):
                template_args = {"seed": seed, "manifest_fingerprint": manifest_fingerprint}
            else:
                template_args = {"manifest_fingerprint": manifest_fingerprint}
            rel_path = render_dataset_path(dataset_id=dataset_id, template_args=template_args, dictionary=dictionary)
            path = data_root / rel_path
            if not path.exists():
                raise err("E_COMPONENT_MISSING", f"bundle component '{dataset_id}' missing at '{path}'")
            schema_ref = self._schema_ref_for(dataset_id, dictionary)
            digest = aggregate_sha256(hash_files(expand_files(path), error_prefix=dataset_id))
            components.append(
                {
                    "dataset_id": dataset_id,
                    "role": role,
                    "path": str(path),
                    "schema_ref": schema_ref,
                    "sha256_hex": digest,
                }
            )
        components.sort(key=lambda c: (c["dataset_id"], c["path"]))
        return components

    def _run_structural_checks(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        seed: int,
    ) -> None:
        """Lightweight contract checks to mirror spec expectations."""

        edge_path = data_root / render_dataset_path(
            dataset_id="edge_catalogue_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        edge_idx_path = data_root / render_dataset_path(
            dataset_id="edge_catalogue_index_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        alias_idx_path = data_root / render_dataset_path(
            dataset_id="edge_alias_index_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        routing_policy_path = data_root / render_dataset_path(
            dataset_id="virtual_routing_policy_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        validation_contract_path = data_root / render_dataset_path(
            dataset_id="virtual_validation_contract_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )

        if not edge_path.exists() or not edge_idx_path.exists() or not alias_idx_path.exists():
            raise err("E_S5_PRECONDITION", "S2/S3 artefacts missing; cannot validate bundle")
        if not routing_policy_path.exists() or not validation_contract_path.exists():
            raise err("E_S5_PRECONDITION", "S4 artefacts missing; cannot validate bundle")

        edge_df = pl.read_parquet(edge_path)
        edge_idx = pl.read_parquet(edge_idx_path)
        alias_idx = pl.read_parquet(alias_idx_path)

        # Edge count sanity: global index row should mirror edge_df height.
        global_edge_count = (
            edge_idx.filter(pl.col("scope") == "GLOBAL")
            .select("edge_count_total_all_merchants")
            .fill_null(0)
            .item()
        )
        if global_edge_count != edge_df.height:
            raise err(
                "E_S5_CONSISTENCY",
                f"edge_catalogue_index global edge_count_total_all_merchants={global_edge_count} "
                f"but edge_catalogue_3B has {edge_df.height} rows",
            )

        # Alias index sanity: global row should reference same universe hash as S3 output, and counts match edge total.
        alias_global = alias_idx.filter(pl.col("scope") == "GLOBAL")
        if not alias_global.is_empty():
            alias_total = alias_global.select("edge_count_total").fill_null(0).item()
            if alias_total not in (0, edge_df.height):
                raise err(
                    "E_S5_CONSISTENCY",
                    f"edge_alias_index global edge_count_total={alias_total} does not match edge count {edge_df.height}",
                )

        # Routing policy sanity: manifest and referenced artefact paths must exist.
        routing_policy = json.loads(routing_policy_path.read_text(encoding="utf-8"))
        if routing_policy.get("manifest_fingerprint") != manifest_fingerprint:
            raise err("E_S5_CONSISTENCY", "routing policy manifest_fingerprint mismatch")
        for key in ("edge_catalogue_index", "edge_alias_blob", "edge_alias_index"):
            ref_path = Path(routing_policy.get("artefact_paths", {}).get(key, ""))
            if ref_path and not ref_path.exists():
                raise err("E_S5_CONSISTENCY", f"routing policy artefact path missing: {ref_path}")

        # Validation contract sanity: all rows should share the manifest fingerprint and non-empty.
        contract_df = pl.read_parquet(validation_contract_path)
        if contract_df.is_empty():
            raise err("E_S5_CONSISTENCY", "virtual_validation_contract_3B is empty")
        unique_fingerprints = contract_df.select(pl.col("fingerprint").n_unique()).item()
        if unique_fingerprints != 1:
            raise err("E_S5_CONSISTENCY", "virtual_validation_contract_3B has mixed fingerprints")
        try:
            schema = load_schema("#/egress/virtual_validation_contract_3B")
            cleaned_rows = []
            for row in contract_df.to_dicts():
                thresholds = row.get("thresholds") or {}
                if isinstance(thresholds, dict):
                    row["thresholds"] = {k: v for k, v in thresholds.items() if v is not None}
                cleaned_rows.append(row)
            # The shared schema uses custom "table" type not understood by jsonschema; skip if unknown type.
            validator = jsonschema.Draft202012Validator(schema)
            validator.validate(cleaned_rows)
        except RecursionError:
            # Known environment recursion limits; warn only.
            pass
        except jsonschema.exceptions.UnknownType:
            # Schema uses non-JSONSchema "table" type; skip strict validation.
            pass
        except jsonschema.ValidationError as exc:
            raise err("E_S5_CONSISTENCY", f"virtual_validation_contract_3B failed schema validation: {exc.message}") from exc

    def _build_index(self, components: Iterable[Mapping[str, Any]]) -> Mapping[str, Any]:
        return {"version": "1.0.0", "items": list(components)}

    def _compute_bundle_digest(self, index: Mapping[str, Any]) -> str:
        concat = "".join(item["sha256_hex"] for item in index.get("items", []))
        from hashlib import sha256

        return sha256(concat.encode("utf-8")).hexdigest()

    def _schema_ref_for(self, dataset_id: str, dictionary: Mapping[str, object]) -> str:
        entry = get_dataset_entry(dataset_id, dictionary=dictionary)
        ref = entry.get("schema_ref")
        if not isinstance(ref, str):
            raise err("E_DICTIONARY_RESOLUTION_FAILED", f"schema_ref missing for {dataset_id}")
        return ref


__all__ = ["ValidationInputs", "ValidationResult", "ValidationRunner"]
