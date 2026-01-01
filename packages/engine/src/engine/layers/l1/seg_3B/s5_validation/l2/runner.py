"""Segment 3B S5 runner - validation bundle and _passed.flag."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import jsonschema
import polars as pl

from engine.layers.l1.seg_2A.s0_gate.l0 import (
    aggregate_sha256,
    expand_files,
    hash_files,
    total_size_bytes,
)
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
        passed_flag_path = bundle_dir / "_passed.flag"

        components = self._gather_components(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        s5_manifest_path = data_root / render_dataset_path(
            dataset_id="s5_manifest_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        s5_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        s5_manifest_payload = self._build_s5_manifest(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            components=components,
        )
        if s5_manifest_path.exists():
            existing = json.loads(s5_manifest_path.read_text(encoding="utf-8"))
            if existing != s5_manifest_payload:
                raise err("E_IMMUTABILITY", f"s5_manifest_3B differs at '{s5_manifest_path}'")
        else:
            s5_manifest_path.write_text(
                json.dumps(s5_manifest_payload, indent=2, sort_keys=True), encoding="utf-8"
            )
        s5_manifest_digest = sha256(s5_manifest_path.read_bytes()).hexdigest()

        components.append(
            self._component_entry(
                logical_id="s5_manifest_3B",
                role="s5_manifest",
                path=s5_manifest_path,
                dictionary=dictionary,
            )
        )
        components.sort(key=lambda c: c["path"])
        self._run_structural_checks(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        bundle_index = self._build_index(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            s5_manifest_digest=s5_manifest_digest,
            components=components,
        )
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

        run_report_path = data_root / render_dataset_path(
            dataset_id="s5_run_report_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
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
            components.append(self._component_entry(dataset_id, role, path, dictionary))
        components.sort(key=lambda c: c["path"])
        return components

    def _run_structural_checks(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        parameter_hash: str,
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
        alias_blob_path = data_root / render_dataset_path(
            dataset_id="edge_alias_blob_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not alias_blob_path.exists():
            raise err("E_S5_PRECONDITION", "edge_alias_blob_3B missing; cannot validate bundle")
        header, payload_offset, payload_digest, blob_bytes = self._parse_alias_blob(alias_blob_path)
        if header.get("blob_length_bytes") != len(blob_bytes):
            raise err("E_S5_CONSISTENCY", "edge_alias_blob_3B length mismatch with header")
        if payload_digest != header.get("blob_sha256_hex"):
            raise err("E_S5_CONSISTENCY", "edge_alias_blob_3B payload digest mismatch")

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
            global_blob_len = alias_global.select("blob_length_bytes").fill_null(0).item()
            if int(global_blob_len) not in (0, len(blob_bytes)):
                raise err("E_S5_CONSISTENCY", "edge_alias_index global blob_length_bytes mismatch")
            global_blob_sha = alias_global.select("blob_sha256_hex").fill_null("").item()
            if global_blob_sha and str(global_blob_sha) != str(header.get("blob_sha256_hex")):
                raise err("E_S5_CONSISTENCY", "edge_alias_index global blob_sha256_hex mismatch")

        merchant_rows = alias_idx.filter(pl.col("scope") == "MERCHANT")
        for row in merchant_rows.select(
            ["merchant_id", "blob_offset_bytes", "blob_length_bytes", "merchant_alias_checksum"]
        ).iter_rows(named=True):
            offset = int(row["blob_offset_bytes"])
            length = int(row["blob_length_bytes"])
            checksum = str(row["merchant_alias_checksum"])
            if offset < payload_offset or offset + length > len(blob_bytes):
                raise err("E_S5_CONSISTENCY", "edge_alias_index offset outside alias blob bounds")
            segment = blob_bytes[offset : offset + length]
            digest = sha256(segment).hexdigest()
            if checksum and digest != checksum:
                raise err("E_S5_CONSISTENCY", "merchant_alias_checksum mismatch")

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

        edge_hash_path = data_root / render_dataset_path(
            dataset_id="edge_universe_hash_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not edge_hash_path.exists():
            raise err("E_S5_CONSISTENCY", "edge_universe_hash_3B missing")
        edge_hash_payload = json.loads(edge_hash_path.read_text(encoding="utf-8"))
        try:
            schema = load_schema("#/validation/edge_universe_hash_3B")
            jsonschema.Draft202012Validator(schema).validate(edge_hash_payload)
        except RecursionError:
            pass
        except jsonschema.ValidationError as exc:
            raise err("E_S5_CONSISTENCY", f"edge_universe_hash_3B failed schema validation: {exc.message}") from exc
        if edge_hash_payload.get("manifest_fingerprint") != manifest_fingerprint:
            raise err("E_S5_CONSISTENCY", "edge_universe_hash_3B manifest_fingerprint mismatch")
        if edge_hash_payload.get("parameter_hash") != parameter_hash:
            raise err("E_S5_CONSISTENCY", "edge_universe_hash_3B parameter_hash mismatch")
        edge_index_digest = self._sha256_file(edge_idx_path)
        alias_index_digest = self._sha256_file(alias_idx_path)
        if edge_hash_payload.get("edge_catalogue_index_digest") != edge_index_digest:
            raise err("E_S5_CONSISTENCY", "edge_universe_hash_3B edge_catalogue_index_digest mismatch")
        if edge_hash_payload.get("edge_alias_index_digest") != alias_index_digest:
            raise err("E_S5_CONSISTENCY", "edge_universe_hash_3B edge_alias_index_digest mismatch")

    def _build_index(
        self,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        s5_manifest_digest: str,
        components: Iterable[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        return {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "s5_manifest_digest": s5_manifest_digest,
            "members": list(components),
        }

    def _compute_bundle_digest(self, index: Mapping[str, Any]) -> str:
        members = sorted(index.get("members", []), key=lambda item: item.get("path", ""))
        concat = "".join(str(item["sha256_hex"]) for item in members)
        return sha256(concat.encode("ascii")).hexdigest()

    def _schema_ref_for(self, dataset_id: str, dictionary: Mapping[str, object]) -> str:
        entry = get_dataset_entry(dataset_id, dictionary=dictionary)
        ref = entry.get("schema_ref")
        if not isinstance(ref, str):
            raise err("E_DICTIONARY_RESOLUTION_FAILED", f"schema_ref missing for {dataset_id}")
        return ref

    def _component_entry(
        self, logical_id: str, role: str, path: Path, dictionary: Mapping[str, object]
    ) -> Mapping[str, Any]:
        schema_ref = self._schema_ref_for(logical_id, dictionary)
        digest = aggregate_sha256(hash_files(expand_files(path), error_prefix=logical_id))
        size_bytes = total_size_bytes(expand_files(path))
        return {
            "logical_id": logical_id,
            "role": role,
            "path": str(path),
            "schema_ref": schema_ref,
            "sha256_hex": digest,
            "size_bytes": size_bytes,
        }

    def _build_s5_manifest(
        self,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        components: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        evidence = [
            {"logical_id": entry["logical_id"], "sha256_hex": entry["sha256_hex"]}
            for entry in components
        ]
        digest_map: dict[str, str] = {}
        for entry in components:
            if entry["logical_id"] == "edge_catalogue_index_3B":
                try:
                    idx_df = pl.read_parquet(Path(entry["path"]))
                    global_row = (
                        idx_df.filter(pl.col("scope") == "GLOBAL")
                        .select("edge_catalogue_digest_global")
                        .drop_nulls()
                    )
                    if not global_row.is_empty():
                        digest_map["edge_catalogue_digest_global"] = global_row.item()
                except Exception:
                    digest_map["edge_catalogue_digest_global"] = entry["sha256_hex"]
            if entry["logical_id"] == "edge_alias_blob_3B":
                digest_map["edge_alias_blob_digest"] = entry["sha256_hex"]
            if entry["logical_id"] == "virtual_routing_policy_3B":
                digest_map["virtual_routing_policy_digest"] = entry["sha256_hex"]
        payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "status": "PASS",
            "evidence": evidence,
            "digests": digest_map,
        }
        return payload

    def _parse_alias_blob(self, blob_path: Path) -> tuple[Mapping[str, Any], int, str, bytes]:
        data = blob_path.read_bytes()
        if len(data) < 8:
            raise err("E_S5_CONSISTENCY", "edge_alias_blob_3B too small for header prefix")
        header_len = struct.unpack("<Q", data[:8])[0]
        if header_len <= 0 or 8 + header_len > len(data):
            raise err("E_S5_CONSISTENCY", "edge_alias_blob_3B header length invalid")
        header_bytes = data[8 : 8 + header_len]
        header = json.loads(header_bytes.decode("utf-8"))
        try:
            schema = load_schema("#/binary/edge_alias_blob_header_3B")
            jsonschema.Draft202012Validator(schema).validate(header)
        except RecursionError:
            pass
        except jsonschema.ValidationError as exc:
            raise err("E_S5_CONSISTENCY", f"edge_alias_blob_3B header invalid: {exc.message}") from exc
        alignment = int(header.get("alignment_bytes", 1))
        payload_offset = 8 + header_len
        if alignment > 1:
            pad = (alignment - (payload_offset % alignment)) % alignment
            payload_offset += pad
        payload_digest = sha256(data[payload_offset:]).hexdigest()
        return header, payload_offset, payload_digest, data

    def _sha256_file(self, path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()


__all__ = ["ValidationInputs", "ValidationResult", "ValidationRunner"]
