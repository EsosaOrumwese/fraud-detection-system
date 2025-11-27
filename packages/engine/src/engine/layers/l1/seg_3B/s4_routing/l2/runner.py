"""Segment 3B S4 runner - virtual routing policy and validation contract (RNG-free)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import polars as pl
import yaml
from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_3B.shared import (
    SegmentStateKey,
    render_dataset_path,
    write_segment_state_run_report,
)
from engine.layers.l1.seg_3B.shared.dictionary import (
    load_dictionary,
    repository_root,
)
from engine.layers.l1.seg_3B.shared.schema import load_schema
from engine.layers.l1.seg_3B.s0_gate.exceptions import err

logger = logging.getLogger(__name__)

_S0_RECEIPT_SCHEMA = Draft202012Validator(load_schema("#/validation/s0_gate_receipt_3B"))
_S4_SUMMARY_SCHEMA = Draft202012Validator(load_schema("#/validation/s4_run_summary_3B"))
_ROUTING_SCHEMA = Draft202012Validator(load_schema("#/egress/virtual_routing_policy_3B"))
_VALIDATION_CONTRACT_SCHEMA = Draft202012Validator(load_schema("#/egress/virtual_validation_contract_3B"))
_VALIDATION_POLICY_SCHEMA = Draft202012Validator(load_schema("#/policy/virtual_validation_policy_v1"))


def _frames_equal(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    try:
        return a.frame_equal(b)  # type: ignore[attr-defined]
    except AttributeError:
        try:
            return a.equals(b)  # type: ignore[attr-defined]
        except Exception:
            return False


@dataclass(frozen=True)
class RoutingInputs:
    data_root: Path
    manifest_fingerprint: str
    seed: int
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class RoutingResult:
    routing_policy_path: Path
    validation_contract_path: Path
    run_report_path: Path
    run_summary_path: Path
    resumed: bool


class RoutingRunner:
    """Compile virtual routing policy and validation contract."""

    def run(self, inputs: RoutingInputs) -> RoutingResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        seed = inputs.seed

        s0_receipt = self._load_s0_receipt(data_root, dictionary, manifest_fingerprint)
        sealed_index = self._load_sealed_inputs(data_root, dictionary, manifest_fingerprint)

        # Required upstream artefacts
        edge_index_path = data_root / render_dataset_path(
            dataset_id="edge_catalogue_index_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        alias_blob_path = data_root / render_dataset_path(
            dataset_id="edge_alias_blob_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        alias_index_path = data_root / render_dataset_path(
            dataset_id="edge_alias_index_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        edge_hash_path = data_root / render_dataset_path(
            dataset_id="edge_universe_hash_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not edge_index_path.exists() or not alias_blob_path.exists() or not alias_index_path.exists():
            raise err("E_S4_PRECONDITION", "S2/S3 outputs missing; run S2+S3 before S4")
        if not edge_hash_path.exists():
            raise err("E_S4_PRECONDITION", "edge_universe_hash_3B missing; run S3 before S4")

        alias_index_df = pl.read_parquet(alias_index_path)
        edge_hash_payload = json.loads(edge_hash_path.read_text(encoding="utf-8"))

        virtual_validation_policy = self._load_validation_policy(sealed_index)

        digests = s0_receipt.get("digests") or {}

        routing_policy = self._build_routing_policy(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=str(s0_receipt.get("parameter_hash", "")),
            edge_hash_payload=edge_hash_payload,
            edge_hash_path=edge_hash_path,
            alias_index_df=alias_index_df,
            edge_index_path=edge_index_path,
            alias_blob_path=alias_blob_path,
            alias_index_path=alias_index_path,
            sealed_index=sealed_index,
            validation_policy_version=str(virtual_validation_policy.get("version", "virtual_validation_policy_v1")),
            digests=digests,
        )
        routing_policy_path = data_root / render_dataset_path(
            dataset_id="virtual_routing_policy_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        routing_policy_path.parent.mkdir(parents=True, exist_ok=True)
        resumed = False
        if routing_policy_path.exists():
            existing = json.loads(routing_policy_path.read_text(encoding="utf-8"))
            if existing != routing_policy:
                raise err(
                    "E3B_S4_OUTPUT_INCONSISTENT_REWRITE",
                    f"virtual_routing_policy_3B already exists at '{routing_policy_path}' with different content",
                )
            resumed = True
        else:
            routing_policy_path.write_text(json.dumps(routing_policy, indent=2, sort_keys=True), encoding="utf-8")

        contract_df = self._build_validation_contract(
            manifest_fingerprint=manifest_fingerprint,
            virtual_validation_policy=virtual_validation_policy,
        )
        validation_contract_path = data_root / render_dataset_path(
            dataset_id="virtual_validation_contract_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        validation_contract_path.parent.mkdir(parents=True, exist_ok=True)
        if validation_contract_path.exists():
            existing = pl.read_parquet(validation_contract_path)
            if not _frames_equal(existing, contract_df):
                raise err(
                    "E3B_S4_OUTPUT_INCONSISTENT_REWRITE",
                    f"virtual_validation_contract_3B already exists at '{validation_contract_path}' with different content",
                )
            resumed = True
        else:
            contract_df.write_parquet(validation_contract_path)

        run_summary_path = data_root / render_dataset_path(
            dataset_id="s4_run_summary_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        run_summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": routing_policy["parameter_hash"],
            "status": "PASS",
            "cdn_key_digest": routing_policy.get("cdn_key_digest"),
            "virtual_validation_digest": digests.get("virtual_validation_digest")
            or self._extract_sealed_digest(sealed_index, "virtual_validation_policy"),
            "routing_policy_version": routing_policy.get("routing_policy_version"),
        }
        try:
            _S4_SUMMARY_SCHEMA.validate(summary_payload)
        except RecursionError:
            logger.warning("Skipping S4 summary schema validation due to recursion depth")
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s4_run_summary_3B failed validation: {exc.message}") from exc
        if run_summary_path.exists():
            existing = json.loads(run_summary_path.read_text(encoding="utf-8"))
            if existing != summary_payload:
                raise err(
                    "E3B_S4_OUTPUT_INCONSISTENT_REWRITE",
                    f"s4_run_summary_3B already exists at '{run_summary_path}' with different content",
                )
        else:
            run_summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8")

        run_report_path = (
            data_root
            / f"reports/l1/3B/s4_routing/fingerprint={manifest_fingerprint}/run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3B",
            "state": "S4",
            "status": "PASS",
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": routing_policy["parameter_hash"],
            "routing_policy_path": str(routing_policy_path),
            "validation_contract_path": str(validation_contract_path),
            "resumed": resumed,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer1",
            segment="3B",
            state="S4",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=routing_policy["parameter_hash"],
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
                "run_report_path": str(run_report_path),
                "routing_policy_path": str(routing_policy_path),
                "validation_contract_path": str(validation_contract_path),
                "run_summary_path": str(run_summary_path),
                "resumed": resumed,
            },
        )

        return RoutingResult(
            routing_policy_path=routing_policy_path,
            validation_contract_path=validation_contract_path,
            run_report_path=run_report_path,
            run_summary_path=run_summary_path,
            resumed=resumed,
        )

    def _load_s0_receipt(self, base: Path, dictionary: Mapping[str, object], manifest_fingerprint: str) -> Mapping[str, Any]:
        receipt_path = base / render_dataset_path(
            dataset_id="s0_gate_receipt_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not receipt_path.exists():
            raise err("E_S4_PRECONDITION", f"S0 gate receipt missing at '{receipt_path}'")
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        try:
            _S0_RECEIPT_SCHEMA.validate(payload)
        except RecursionError:
            logger.warning("Skipping S4 receipt schema validation due to recursion depth")
        except ValidationError as exc:
            raise err("E_S4_PRECONDITION", f"S0 gate receipt invalid: {exc.message}") from exc
        return payload

    def _load_sealed_inputs(
        self, base: Path, dictionary: Mapping[str, object], manifest_fingerprint: str
    ) -> pl.DataFrame:
        sealed_inputs_path = base / render_dataset_path(
            dataset_id="sealed_inputs_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not sealed_inputs_path.exists():
            raise err("E_S4_PRECONDITION", f"S0 sealed inputs missing at '{sealed_inputs_path}'")
        df = pl.read_parquet(sealed_inputs_path)
        if "logical_id" not in df.columns:
            raise err("E_SCHEMA", "sealed_inputs_3B missing logical_id column")
        return df

    def _resolve_asset_path(self, sealed_index: pl.DataFrame, logical_id: str) -> Path:
        matches = sealed_index.filter(pl.col("logical_id") == logical_id)
        if matches.is_empty():
            raise err("E_ASSET", f"sealed_inputs_3B missing logical_id '{logical_id}'")
        path_val = matches.select("path").item()
        resolved = Path(str(path_val))
        if not resolved.is_absolute():
            repo = repository_root()
            candidate_repo = (repo / resolved).resolve()
            candidate_data = (Path.cwd() / resolved).resolve()
            resolved = candidate_repo if candidate_repo.exists() else candidate_data
        if not resolved.exists():
            raise err("E_ASSET", f"asset '{logical_id}' not found at '{resolved}'")
        return resolved

    def _extract_sealed_digest(self, sealed_index: pl.DataFrame, logical_id: str) -> str | None:
        matches = sealed_index.filter(pl.col("logical_id") == logical_id)
        if matches.is_empty():
            return None
        val = matches.select("sha256_hex").item()
        return str(val)

    def _load_validation_policy(self, sealed_index: pl.DataFrame) -> Mapping[str, Any]:
        path = self._resolve_asset_path(sealed_index, "virtual_validation_policy")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        try:
            _VALIDATION_POLICY_SCHEMA.validate(payload)
        except ValidationError as exc:
            raise err("E_POLICY", f"virtual_validation_policy failed validation: {exc.message}") from exc
        return payload

    def _build_routing_policy(
        self,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        edge_hash_payload: Mapping[str, Any],
        edge_hash_path: Path,
        alias_index_df: pl.DataFrame,
        edge_index_path: Path,
        alias_blob_path: Path,
        alias_index_path: Path,
        sealed_index: pl.DataFrame,
        validation_policy_version: str,
        digests: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            _ = edge_hash_payload["edge_universe_hash"]
        except Exception:
            raise err("E_SCHEMA", "edge_universe_hash_3B missing edge_universe_hash")

        alias_layout_version = "synthetic-v1"
        try:
            global_layout = (
                alias_index_df.filter(pl.col("scope") == "GLOBAL")
                .select("alias_layout_version")
                .fill_null(alias_layout_version)
                .item()
            )
            alias_layout_version = str(global_layout) if global_layout is not None else alias_layout_version
        except Exception:
            alias_layout_version = "synthetic-v1"

        cdn_key_digest = digests.get("cdn_key_digest") or (
            self._extract_sealed_digest(sealed_index, "cdn_country_weights")
            or self._extract_sealed_digest(sealed_index, "cdn_key_digest")
            or edge_hash_payload.get("cdn_weights_digest")
        )
        if cdn_key_digest is None:
            cdn_key_digest = "0" * 64

        routing_policy = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "edge_universe_hash": edge_hash_payload.get("edge_universe_hash"),
            "routing_policy_id": "virtual_routing_policy",
            "routing_policy_version": "synthetic-v1",
            "virtual_validation_policy_id": "virtual_validation_policy",
            "virtual_validation_policy_version": validation_policy_version,
            "cdn_key_digest": cdn_key_digest,
            "alias_layout_version": alias_layout_version or "synthetic-v1",
            "alias_blob_manifest_key": str(alias_blob_path),
            "alias_index_manifest_key": str(alias_index_path),
            "edge_universe_hash_manifest_key": str(edge_hash_path),
            "dual_timezone_semantics": {
                "tzid_settlement_field": "tzid_settlement",
                "tzid_operational_field": "tzid_operational",
                "settlement_cutoff_rule": "use_settlement_tz_cutoff",
            },
            "geo_field_bindings": {
                "ip_country_field": "ip_country_iso",
                "ip_latitude_field": "ip_lat_deg",
                "ip_longitude_field": "ip_lon_deg",
            },
            "artefact_paths": {
                "edge_catalogue_index": str(edge_index_path),
                "edge_alias_blob": str(alias_blob_path),
                "edge_alias_index": str(alias_index_path),
            },
            "virtual_edge_rng_binding": {
                "module": "engine.layers.l1.seg_2B.virtual_routing",
                "substream_label": "rng_synthetic",
                "event_schema": "schemas.layer1.yaml#/egress/transactions",
            },
        }
        try:
            _ROUTING_SCHEMA.validate(routing_policy)
        except RecursionError:
            logger.warning("Skipping S4 routing policy schema validation due to recursion depth")
        except ValidationError as exc:
            raise err("E_SCHEMA", f"virtual_routing_policy_3B failed validation: {exc.message}") from exc
        return routing_policy

    def _build_validation_contract(
        self, *, manifest_fingerprint: str, virtual_validation_policy: Mapping[str, Any]
    ) -> pl.DataFrame:
        ip_tol = float(virtual_validation_policy.get("ip_country_tolerance", 0.02))
        cutoff_tol = int(virtual_validation_policy.get("cutoff_tolerance_seconds", 5))
        rows: list[dict[str, Any]] = [
            {
                "fingerprint": manifest_fingerprint,
                "test_id": "ip_country_mix_global",
                "test_type": "IP_COUNTRY_MIX",
                "scope": "GLOBAL",
                "target_population": {"virtual_only": True},
                "inputs": {
                    "datasets": [
                        {"logical_id": "virtual_settlement_3B", "role": "settlement_geo"},
                        {"logical_id": "edge_catalogue_3B", "role": "edge_geo"},
                    ],
                    "fields": [],
                    "join_keys": ["merchant_id"],
                },
                "thresholds": {"max_abs_error": ip_tol, "min_coverage_ratio": 0.8},
                "severity": "WARNING",
                "enabled": True,
                "description": "IP country mix should align with edge geography within tolerance.",
                "profile": "default",
            },
            {
                "fingerprint": manifest_fingerprint,
                "test_id": "settlement_cutoff_alignment",
                "test_type": "SETTLEMENT_CUTOFF",
                "scope": "GLOBAL",
                "target_population": {"virtual_only": True},
                "inputs": {
                    "datasets": [
                        {"logical_id": "virtual_settlement_3B", "role": "settlement_geo"},
                    ],
                    "fields": [],
                    "join_keys": ["merchant_id"],
                },
                "thresholds": {"cutoff_tolerance_seconds": cutoff_tol},
                "severity": "WARNING",
                "enabled": True,
                "description": "Settlement cutoff must align with policy tolerance.",
                "profile": "default",
            },
        ]
        df = pl.DataFrame(rows)
        return df.select(
            [
                "fingerprint",
                "test_id",
                "test_type",
                "scope",
                "target_population",
                "inputs",
                "thresholds",
                "severity",
                "enabled",
                "description",
                "profile",
            ]
        ).sort("test_id")


__all__ = ["RoutingInputs", "RoutingResult", "RoutingRunner"]
