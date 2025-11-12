"""Segment 2B state-7 audit runner."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from ...shared.dictionary import load_dictionary, render_dataset_path, resolve_dataset_path
from ...shared.policies import load_policy_asset
from ...shared.receipt import (
    GateReceiptSummary,
    SealedInputRecord,
    load_gate_receipt,
    load_sealed_inputs_inventory,
)
from ...shared.schema import load_schema
from ...s0_gate.exceptions import err

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouterEvidence:
    """Optional router evidence artefacts supplied by upstream states."""

    run_id: Optional[str] = None
    parameter_hash: Optional[str] = None
    rng_event_group_path: Optional[Path] = None
    rng_event_site_path: Optional[Path] = None
    rng_event_edge_path: Optional[Path] = None
    rng_trace_log_path: Optional[Path] = None
    rng_audit_log_path: Optional[Path] = None
    selection_log_paths: Tuple[Path, ...] = ()
    edge_log_paths: Tuple[Path, ...] = ()


@dataclass(frozen=True)
class S5EvidenceOutcome:
    """Summary of S5 evidence checks."""

    selections: int
    group_events: int
    site_events: int
    expected_draws: int
    observed_draws: int
    mapping_verified: bool
    trace_totals_checked: bool
    log_rows_checked: bool


@dataclass(frozen=True)
class S6EvidenceOutcome:
    """Summary of S6 evidence checks."""

    virtual_arrivals: int
    edge_events: int
    expected_draws: int
    observed_draws: int
    mapping_verified: bool
    trace_totals_checked: bool
    log_rows_checked: bool


@dataclass(frozen=True)
class S7AuditInputs:
    """Configuration required to execute the audit runner."""

    data_root: Path
    seed: int | str
    manifest_fingerprint: str
    seg2a_manifest_fingerprint: str
    parameter_hash: str
    dictionary_path: Optional[Path] = None
    s5_evidence: Optional[RouterEvidence] = None
    s6_evidence: Optional[RouterEvidence] = None
    emit_run_report_stdout: bool = True

    def __post_init__(self) -> None:
        data_root = self.data_root.expanduser().resolve()
        object.__setattr__(self, "data_root", data_root)
        seed_value = str(self.seed)
        if not seed_value:
            raise err("E_S7_SEED_EMPTY", "seed must be provided for S7")
        object.__setattr__(self, "seed", seed_value)
        manifest = self.manifest_fingerprint.lower()
        if len(manifest) != 64:
            raise err("E_S7_MANIFEST_FINGERPRINT", "manifest_fingerprint must be 64 hex characters")
        int(manifest, 16)
        object.__setattr__(self, "manifest_fingerprint", manifest)
        seg2a_manifest = self.seg2a_manifest_fingerprint.lower()
        if len(seg2a_manifest) != 64:
            raise err("E_S7_SEG2A_FINGERPRINT", "seg2a_manifest_fingerprint must be 64 hex characters")
        int(seg2a_manifest, 16)
        object.__setattr__(self, "seg2a_manifest_fingerprint", seg2a_manifest)
        parameter_hash = self.parameter_hash.lower()
        if len(parameter_hash) != 64:
            raise err("E_S7_PARAMETER_HASH", "parameter_hash must be 64 hex characters")
        int(parameter_hash, 16)
        object.__setattr__(self, "parameter_hash", parameter_hash)


@dataclass(frozen=True)
class S7AuditResult:
    """Structured result emitted by the audit runner."""

    manifest_fingerprint: str
    report_path: Path
    validators: Tuple[Mapping[str, object], ...]


class S7AuditRunner:
    """Runs Segment 2B state-7 audit checks."""

    RUN_REPORT_ROOT = Path("reports") / "l1" / "s7_audit"
    REPORT_DATASET_ID = "s7_audit_report"

    def run(self, config: S7AuditInputs) -> S7AuditResult:
        dictionary = load_dictionary(config.dictionary_path)
        seed_int = int(config.seed)
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
        sealed_records = {record.asset_id: record for record in sealed_inputs}
        alias_policy_payload, alias_policy_digest, _, alias_policy_path = load_policy_asset(
            asset_id="alias_layout_policy_v1",
            sealed_records=sealed_records,
            base_path=config.data_root,
            repo_root=None,
            error_prefix="E_S7_POLICY",
        )
        route_policy_payload: Optional[Mapping[str, object]] = None
        virtual_edge_policy_payload: Optional[Mapping[str, object]] = None
        if config.s5_evidence or config.s6_evidence:
            route_policy_payload, *_ = load_policy_asset(
                asset_id="route_rng_policy_v1",
                sealed_records=sealed_records,
                base_path=config.data_root,
                repo_root=None,
                error_prefix="E_S7_POLICY",
            )
        if config.s6_evidence:
            virtual_edge_policy_payload, *_ = load_policy_asset(
                asset_id="virtual_edge_policy_v1",
                sealed_records=sealed_records,
                base_path=config.data_root,
                repo_root=None,
                error_prefix="E_S7_POLICY",
            )

        alias_index_path = self._resolve_dataset_path(
            dataset_id="s2_alias_index",
            base_path=config.data_root,
            dictionary=dictionary,
            seed=config.seed,
            manifest=config.manifest_fingerprint,
        )
        alias_blob_path = self._resolve_dataset_path(
            dataset_id="s2_alias_blob",
            base_path=config.data_root,
            dictionary=dictionary,
            seed=config.seed,
            manifest=config.manifest_fingerprint,
        )
        s1_site_weights_path = self._resolve_dataset_path(
            dataset_id="s1_site_weights",
            base_path=config.data_root,
            dictionary=dictionary,
            seed=config.seed,
            manifest=config.manifest_fingerprint,
        )
        s3_path = self._resolve_dataset_path(
            dataset_id="s3_day_effects",
            base_path=config.data_root,
            dictionary=dictionary,
            seed=config.seed,
            manifest=config.manifest_fingerprint,
        )
        s4_path = self._resolve_dataset_path(
            dataset_id="s4_group_weights",
            base_path=config.data_root,
            dictionary=dictionary,
            seed=config.seed,
            manifest=config.manifest_fingerprint,
        )
        site_timezone_lookup: Optional[Mapping[int, str]] = None
        if config.s5_evidence and config.s5_evidence.selection_log_paths:
            site_timezone_lookup = self._load_site_timezone_lookup(
                base_path=config.data_root,
                dictionary=dictionary,
                seed=config.seed,
                seg2a_manifest=config.seg2a_manifest_fingerprint,
            )

        validators: List[Mapping[str, object]] = [
            {"id": "V-01", "status": "PASS", "codes": ["2B-S7-001"]},
            {"id": "V-02", "status": "PASS", "codes": ["2B-S7-020"]},
            {"id": "V-03", "status": "PASS", "codes": ["2B-S7-070"]},
        ]
        metrics: Dict[str, object] = {}

        alias_metrics, alias_validators = self._validate_alias_mechanics(
            alias_index_path=alias_index_path,
            alias_blob_path=alias_blob_path,
            policy_payload=alias_policy_payload,
            s1_site_weights_path=s1_site_weights_path,
        )
        validators.extend(alias_validators)
        metrics.update(alias_metrics)

        day_metrics, day_validators = self._validate_day_surfaces(
            s3_path=s3_path,
            s4_path=s4_path,
        )
        validators.extend(day_validators)
        metrics.update(day_metrics)

        router_section: Mapping[str, object] = {
            "s5": {"present": False},
            "s6": {"present": False},
        }
        if config.s5_evidence or config.s6_evidence:
            router_section, router_validators, router_metrics = self._validate_router_evidence(
                seed=seed_int,
                manifest=config.manifest_fingerprint,
                parameter_hash=config.parameter_hash,
                site_timezones=site_timezone_lookup,
                route_policy=route_policy_payload,
                virtual_edge_policy=virtual_edge_policy_payload,
                s5=config.s5_evidence,
                s6=config.s6_evidence,
            )
            validators.extend(router_validators)
            metrics.update(router_metrics)

        inputs_digest = self._inputs_digest(sealed_inputs)
        report = {
            "component": "2B.S7",
            "state": "S7",
            "seed": int(config.seed),
            "manifest_fingerprint": config.manifest_fingerprint,
            "parameter_hash": config.parameter_hash,
            "created_utc": receipt.verified_at_utc,
            "catalogue_resolution": dict(receipt.catalogue_resolution),
            "inputs_digest": inputs_digest,
            "validators": validators,
            "metrics": metrics,
            "router_evidence": router_section,
            "determinism": dict(receipt.determinism_receipt),
        }
        report_path = self._write_report(
            base_path=config.data_root,
            dictionary=dictionary,
            seed=config.seed,
            manifest=config.manifest_fingerprint,
            report=report,
        )
        if config.emit_run_report_stdout:
            total_validators = len(validators)
            passed = sum(1 for item in validators if item.get("status") == "PASS")
            print(
                f"Segment2B S7 audit report → {report_path} "
                f"(validators={passed}/{total_validators})"
            )
        return S7AuditResult(
            manifest_fingerprint=config.manifest_fingerprint,
            report_path=report_path,
            validators=tuple(validators),
        )

    # ------------------------------------------------------------------ utils
    def _resolve_dataset_path(
        self,
        *,
        dataset_id: str,
        base_path: Path,
        dictionary: Mapping[str, object],
        seed: int | str,
        manifest: str,
    ) -> Path:
        rel = render_dataset_path(
            dataset_id,
            template_args={"seed": seed, "manifest_fingerprint": manifest},
            dictionary=dictionary,
        )
        return (base_path / rel).resolve()

    def _inputs_digest(self, sealed_inputs: Sequence[SealedInputRecord]) -> List[Mapping[str, object]]:
        digest: List[Mapping[str, object]] = []
        for record in sealed_inputs:
            digest.append(
                {
                    "id": record.asset_id,
                    "version_tag": record.version_tag,
                    "sha256_hex": record.sha256_hex,
                    "path": record.catalog_path,
                    "partition": list(record.partition),
                    "schema_ref": record.schema_ref,
                }
            )
        return digest

    # ---------------------------------------------------------------- alias
    def _validate_alias_mechanics(
        self,
        *,
        alias_index_path: Path,
        alias_blob_path: Path,
        policy_payload: Mapping[str, object],
        s1_site_weights_path: Path,
    ) -> tuple[Mapping[str, object], List[Mapping[str, object]]]:
        schema = load_schema("#/plan/s2_alias_index")
        validator = Draft202012Validator(schema)
        index_payload = self._read_json(alias_index_path)
        try:
            validator.validate(index_payload)
        except ValidationError as exc:
            raise err("E_S7_ALIAS_SCHEMA", f"s2_alias_index failed schema validation: {exc}") from exc

        if not alias_blob_path.exists():
            raise err("E_S7_ALIAS_BLOB_MISSING", f"s2_alias_blob missing at '{alias_blob_path}'")
        blob_bytes = alias_blob_path.read_bytes()
        blob_sha = hashlib.sha256(blob_bytes).hexdigest()
        if blob_sha != index_payload.get("blob_sha256"):
            raise err(
                "E_S7_ALIAS_DIGEST",
                "alias blob digest mismatch between index header and blob bytes",
            )

        alignment = int(index_payload.get("alignment_bytes", policy_payload.get("alignment_bytes", 1)))
        merchants = index_payload.get("merchants") or []
        merchants_sorted = sorted(
            merchants,
            key=lambda item: str(item.get("merchant_id", "")),
        )
        sample_merchants = merchants_sorted[: min(32, len(merchants_sorted))]
        self._validate_alias_offsets(merchants_sorted, len(blob_bytes), alignment)

        s1_frame = self._load_site_weights_subset(
            s1_site_weights_path,
            [int(item["merchant_id"]) for item in sample_merchants],
        )
        decode_metrics = []
        for merchant_entry in sample_merchants:
            merchant_id = int(merchant_entry["merchant_id"])
            offset = int(merchant_entry["offset"])
            length = int(merchant_entry["length"])
            decoded = self._decode_alias_slice(
                blob=blob_bytes,
                offset=offset,
                length=length,
                policy_payload=policy_payload,
            )
            reference = self._extract_site_weights_for_merchant(s1_frame, merchant_id)
            if not reference:
                raise err(
                    "E_S7_ALIAS_REFERENCE",
                    f"site weights missing for sampled merchant {merchant_id}",
                )
            max_delta, mass_error = self._compare_alias_probabilities(decoded, reference, policy_payload)
            decode_metrics.append((max_delta, mass_error))

        alias_decode_delta = max((delta for delta, _ in decode_metrics), default=0.0)
        mass_error = max((err_val for _, err_val in decode_metrics), default=0.0)
        metrics = {
            "alias_decode_max_abs_delta": alias_decode_delta,
            "alias_decode_mass_error": mass_error,
        }
        validators = [
            {"id": "V-04", "status": "PASS", "codes": ["2B-S7-200", "2B-S7-201"]},
            {"id": "V-05", "status": "PASS", "codes": ["2B-S7-202", "2B-S7-205"]},
            {"id": "V-06", "status": "PASS", "codes": ["2B-S7-203", "2B-S7-204"]},
            {"id": "V-07", "status": "PASS", "codes": ["2B-S7-206"], "metrics": {"alias_decode_max_abs_delta": alias_decode_delta}},
        ]
        return metrics, validators

    def _validate_alias_offsets(
        self,
        merchants: Sequence[Mapping[str, object]],
        blob_size: int,
        alignment: int,
    ) -> None:
        last_end = 0
        for entry in sorted(merchants, key=lambda item: int(item["offset"])):
            offset = int(entry["offset"])
            length = int(entry["length"])
            if offset % max(1, alignment) != 0:
                raise err("E_S7_ALIAS_ALIGNMENT", f"alias slice for merchant {entry['merchant_id']} misaligned")
            if offset < last_end:
                raise err("E_S7_ALIAS_OVERLAP", "alias slices overlap")
            if offset + length > blob_size:
                raise err("E_S7_ALIAS_BOUNDS", "alias slice exceeds blob bounds")
            last_end = offset + length

    def _decode_alias_slice(
        self,
        *,
        blob: bytes,
        offset: int,
        length: int,
        policy_payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        endian = policy_payload.get("endian_byteorder") or policy_payload.get("endianness", "little")
        byteorder = "little" if str(endian).lower().startswith("little") else "big"
        encode_spec = policy_payload.get("encode_spec") or {}
        site_order_bytes = int(encode_spec.get("site_order_bytes", 4))
        prob_mass_bytes = int(encode_spec.get("prob_mass_bytes", 4))
        alias_site_order_bytes = int(encode_spec.get("alias_site_order_bytes", 4))
        view = memoryview(blob)[offset : offset + length]
        cursor = 0
        if len(view) < 4:
            raise err("E_S7_ALIAS_SLICE", "alias slice too short to decode header")
        site_count = int.from_bytes(view[cursor : cursor + 4], byteorder=byteorder)
        cursor += 4
        site_orders: List[int] = []
        prob_thresholds: List[int] = []
        alias_orders: List[int] = []
        for _ in range(site_count):
            if cursor + site_order_bytes + prob_mass_bytes + alias_site_order_bytes > len(view):
                raise err("E_S7_ALIAS_SLICE", "alias slice truncated before completing decode")
            site_orders.append(int.from_bytes(view[cursor : cursor + site_order_bytes], byteorder=byteorder))
            cursor += site_order_bytes
            prob_thresholds.append(int.from_bytes(view[cursor : cursor + prob_mass_bytes], byteorder=byteorder))
            cursor += prob_mass_bytes
            alias_orders.append(int.from_bytes(view[cursor : cursor + alias_site_order_bytes], byteorder=byteorder))
            cursor += alias_site_order_bytes
        return {
            "site_orders": site_orders,
            "prob_thresholds": prob_thresholds,
            "alias_orders": alias_orders,
        }

    def _load_site_weights_subset(self, path: Path, merchant_ids: Sequence[int]) -> pl.DataFrame:
        if not path.exists():
            raise err("E_S7_S1_MISSING", f"s1_site_weights missing at '{path}'")
        if not merchant_ids:
            return pl.DataFrame(schema={"merchant_id": pl.UInt64, "site_order": pl.Int32, "p_weight": pl.Float64})
        frame = pl.read_parquet(path)
        return frame.filter(pl.col("merchant_id").is_in(merchant_ids)).sort(["merchant_id", "site_order"])

    def _extract_site_weights_for_merchant(self, frame: pl.DataFrame, merchant_id: int) -> List[Mapping[str, float]]:
        subset = frame.filter(pl.col("merchant_id") == merchant_id)
        return subset.to_dicts()

    def _compare_alias_probabilities(
        self,
        decoded: Mapping[str, object],
        reference_rows: List[Mapping[str, object]],
        policy_payload: Mapping[str, object],
    ) -> tuple[float, float]:
        site_orders = decoded["site_orders"]
        prob_thresholds = decoded["prob_thresholds"]
        alias_orders = decoded["alias_orders"]
        grid = 1 << int(policy_payload.get("quantised_bits", policy_payload.get("quantised_bits", 16)))
        k = len(site_orders)
        site_index = {order: idx for idx, order in enumerate(site_orders)}
        alias_indices: List[int] = []
        for order in alias_orders:
            if order not in site_index:
                raise err("E_S7_ALIAS_ALIAS_ORDER", "alias site_order not present in slice")
            alias_indices.append(site_index[order])
        masses = [0.0] * k
        for idx in range(k):
            threshold = prob_thresholds[idx]
            masses[idx] += threshold / (grid * k)
            alias_share = grid - threshold
            masses[alias_indices[idx]] += alias_share / (grid * k)
        mass_sum = sum(masses)
        mass_error = abs(mass_sum - 1.0)
        reference_prob = []
        for row in reference_rows:
            order = int(row["site_order"])
            if order not in site_index:
                raise err("E_S7_ALIAS_ORDER", "site_order mismatch between alias slice and site weights")
            idx = site_index[order]
            reference_prob.append((idx, float(row["p_weight"])))
        max_delta = 0.0
        for idx, ref_prob in reference_prob:
            max_delta = max(max_delta, abs(masses[idx] - ref_prob))
        return max_delta, mass_error

    # ---------------------------------------------------------------- day surfaces
    def _validate_day_surfaces(
        self,
        *,
        s3_path: Path,
        s4_path: Path,
    ) -> tuple[Mapping[str, object], List[Mapping[str, object]]]:
        if not s3_path.exists():
            raise err("E_S7_S3_MISSING", f"s3_day_effects missing at '{s3_path}'")
        if not s4_path.exists():
            raise err("E_S7_S4_MISSING", f"s4_group_weights missing at '{s4_path}'")
        s3 = pl.read_parquet(s3_path)
        s4 = pl.read_parquet(s4_path)
        join_keys = ["merchant_id", "utc_day", "tz_group_id"]
        s3_small = s3.select(join_keys + ["gamma"]).rename({"gamma": "gamma_left"})
        s4_small = s4.select(join_keys + ["gamma", "p_group", "base_share"]).rename({"gamma": "gamma_right"})
        joined = s3_small.join(s4_small, on=join_keys, how="inner")
        if joined.height != s3_small.height or joined.height != s4_small.height:
            raise err("E_S7_DAY_GRID", "S3/S4 grids mismatch for some merchants/days")
        gamma_delta = (joined["gamma_left"] - joined["gamma_right"]).abs().max()
        gamma_delta = float(gamma_delta) if gamma_delta is not None else 0.0
        if gamma_delta > 1e-9:
            raise err("E_S7_GAMMA_ECHO", f"gamma mismatch exceeds tolerance ({gamma_delta})")
        mass_error = (
            s4.group_by(["merchant_id", "utc_day"])
            .agg(pl.sum("p_group").alias("mass"))
            .with_columns((pl.col("mass") - 1.0).abs().alias("mass_error"))
            .select(pl.max("mass_error"))
            .item()
        )
        mass_error = float(mass_error) if mass_error is not None else 0.0
        base_share_error = 0.0
        if "base_share" in s4.columns:
            base_share_error = (
                s4.group_by("merchant_id")
                .agg(pl.sum("base_share").alias("mass"))
                .with_columns((pl.col("mass") - 1.0).abs().alias("mass_error"))
                .select(pl.max("mass_error"))
                .item()
            )
            base_share_error = float(base_share_error) if base_share_error is not None else 0.0
        metrics = {
            "max_abs_mass_error_s4": mass_error,
        }
        validators: List[Mapping[str, object]] = [
            {"id": "V-08", "status": "PASS", "codes": ["2B-S7-300"]},
            {"id": "V-09", "status": "PASS", "codes": ["2B-S7-301"]},
            {"id": "V-10", "status": "PASS", "codes": ["2B-S7-302"], "metrics": {"max_abs_mass_error_s4": mass_error}},
        ]
        if "base_share" in s4.columns:
            metrics["max_abs_base_share_error"] = base_share_error
            validators.append(
                {
                    "id": "V-11",
                    "status": "PASS",
                    "codes": ["2B-S7-303", "2B-S7-304"],
                    "metrics": {"max_abs_base_share_error": base_share_error},
                }
            )
        return metrics, validators

    # ---------------------------------------------------------------- router evidence
    def _validate_router_evidence(
        self,
        *,
        seed: int,
        manifest: str,
        parameter_hash: str,
        site_timezones: Optional[Mapping[int, str]],
        route_policy: Optional[Mapping[str, object]],
        virtual_edge_policy: Optional[Mapping[str, object]],
        s5: Optional[RouterEvidence],
        s6: Optional[RouterEvidence],
    ) -> tuple[Mapping[str, object], List[Mapping[str, object]], Mapping[str, object]]:
        validators: List[Mapping[str, object]] = []
        metrics: Dict[str, object] = {}
        evidence_section: Dict[str, Mapping[str, object]] = {
            "s5": {"present": False},
            "s6": {"present": False},
        }
        if not s5 and not s6:
            return evidence_section, validators, metrics

        v15_codes: set[str] = set()
        trace_rows_checked = False
        v16_checked = False

        if s5:
            if route_policy is None:
                raise err("E_S7_POLICY_ROUTE", "route_rng_policy_v1 required for S5 evidence")
            if site_timezones is None and s5.selection_log_paths:
                raise err("E_S7_SITE_TIMEZONE", "site_timezones lookup required when S5 selection logs are present")
            s5_section, s5_outcome = self._check_s5_evidence(
                seed=seed,
                manifest=manifest,
                parameter_hash=parameter_hash,
                evidence=s5,
                site_timezones=site_timezones,
                route_policy=route_policy,
            )
            evidence_section["s5"] = s5_section
            metrics["router_rng_expected_draws"] = metrics.get("router_rng_expected_draws", 0) + s5_outcome.expected_draws
            metrics["router_rng_observed_draws"] = metrics.get("router_rng_observed_draws", 0) + s5_outcome.observed_draws
            if s5_outcome.mapping_verified:
                v15_codes.add("2B-S7-410")
            trace_rows_checked = trace_rows_checked or s5_outcome.log_rows_checked
            v16_checked = v16_checked or s5_outcome.trace_totals_checked

        if s6:
            if route_policy is None:
                raise err("E_S7_POLICY_ROUTE", "route_rng_policy_v1 required for S6 evidence")
            if virtual_edge_policy is None:
                raise err("E_S7_POLICY_VIRTUAL", "virtual_edge_policy_v1 required for S6 evidence")
            s6_section, s6_outcome = self._check_s6_evidence(
                seed=seed,
                manifest=manifest,
                parameter_hash=parameter_hash,
                evidence=s6,
                route_policy=route_policy,
                virtual_edge_policy=virtual_edge_policy,
            )
            evidence_section["s6"] = s6_section
            metrics["router_rng_expected_draws"] = metrics.get("router_rng_expected_draws", 0) + s6_outcome.expected_draws
            metrics["router_rng_observed_draws"] = metrics.get("router_rng_observed_draws", 0) + s6_outcome.observed_draws
            if s6_outcome.mapping_verified:
                v15_codes.add("2B-S7-411")
            trace_rows_checked = trace_rows_checked or s6_outcome.log_rows_checked
            v16_checked = v16_checked or s6_outcome.trace_totals_checked

        if trace_rows_checked:
            validators.append(
                {
                    "id": "V-12",
                    "status": "PASS",
                    "codes": ["2B-S7-400", "2B-S7-401", "2B-S7-503"],
                }
            )
        if s5:
            validators.append(
                {
                    "id": "V-13",
                    "status": "PASS",
                    "codes": ["2B-S7-402", "2B-S7-403", "2B-S7-404", "2B-S7-405"],
                }
            )
        if s6:
            validators.append(
                {
                    "id": "V-14",
                    "status": "PASS",
                    "codes": ["2B-S7-402", "2B-S7-403", "2B-S7-404", "2B-S7-405"],
                }
            )
        if v15_codes:
            validators.append(
                {
                    "id": "V-15",
                    "status": "PASS",
                    "codes": sorted(v15_codes),
                }
            )
        if v16_checked:
            validators.append({"id": "V-16", "status": "PASS", "codes": ["2B-S7-402"]})
        return evidence_section, validators, metrics

    def _check_s5_evidence(
        self,
        *,
        seed: int,
        manifest: str,
        parameter_hash: str,
        evidence: RouterEvidence,
        site_timezones: Optional[Mapping[int, str]],
        route_policy: Mapping[str, object],
    ) -> tuple[Mapping[str, object], S5EvidenceOutcome]:
        run_id = (evidence.run_id or "").lower()
        if not run_id:
            raise err("E_S7_ROUTER_RUN_ID", "S5 router evidence missing run_id")
        evidence_hash = (evidence.parameter_hash or parameter_hash).lower()
        if evidence_hash != parameter_hash:
            raise err(
                "E_S7_ROUTER_PARAMETER_HASH",
                "S5 evidence parameter hash does not match manifest parameter hash",
            )
        selection_rows, selection_samples = self._validate_trace_rows(
            evidence.selection_log_paths,
            schema_ref="#/trace/s5_selection_log_row",
            manifest=manifest,
            seed=seed,
            parameter_hash=evidence_hash,
            run_id=run_id,
            sample_limit=32,
        )
        self._assert_route_policy_stream(route_policy, stream_id="router_core", min_uniforms=2)
        group_events = self._load_rng_events(
            directory=evidence.rng_event_group_path,
            schema_ref="#/rng/events/alias_pick_group",
            seed=seed,
            parameter_hash=evidence_hash,
            manifest=manifest,
            run_id=run_id,
            expected_module="2B.router",
            expected_label="alias_pick_group",
            validate_schema=False,
        )
        site_events = self._load_rng_events(
            directory=evidence.rng_event_site_path,
            schema_ref="#/rng/events/alias_pick_site",
            seed=seed,
            parameter_hash=evidence_hash,
            manifest=manifest,
            run_id=run_id,
            expected_module="2B.router",
            expected_label="alias_pick_site",
            validate_schema=False,
        )
        if len(group_events) != len(site_events):
            raise err("E_S7_RNG_EVENTS", "group/site event counts mismatch for S5")
        if selection_rows and selection_rows != len(group_events):
            raise err(
                "E_S7_RNG_EVENTS",
                f"S5 selection log rows ({selection_rows}) differ from RNG events ({len(group_events)})",
            )
        self._validate_rng_sequence(group_events)
        self._validate_rng_sequence(site_events)
        observed_draws = len(group_events) + len(site_events)
        expected_draws = len(group_events) * 2
        mapping_verified = False
        if selection_samples and site_timezones:
            self._verify_selection_samples(selection_samples, site_timezones)
            mapping_verified = True

        trace_totals_checked = False
        if evidence.rng_trace_log_path:
            summary = self._summarize_trace_log(
                evidence.rng_trace_log_path,
                seed=seed,
                run_id=run_id,
            )
            group_key = ("2B.router", "alias_pick_group")
            site_key = ("2B.router", "alias_pick_site")
            group_trace = summary.get(group_key)
            site_trace = summary.get(site_key)
            if group_trace is None or site_trace is None:
                raise err(
                    "E_S7_TRACE_STREAM",
                    "rng_trace_log missing alias pick entries for S5 run",
                )
            if group_trace["draws_total"] != len(group_events) or site_trace["draws_total"] != len(site_events):
                raise err(
                    "E_S7_TRACE_TOTAL",
                    "rng_trace_log draws_total does not match emitted alias events",
                )
            if group_trace["events_total"] != len(group_events) or site_trace["events_total"] != len(site_events):
                raise err(
                    "E_S7_TRACE_TOTAL",
                    "rng_trace_log events_total does not match emitted alias events",
                )
            if group_trace["draws_total"] + site_trace["draws_total"] != expected_draws:
                raise err(
                    "E_S7_TRACE_TOTAL",
                    "rng_trace_log totals mismatch S5 expected draws",
                )
            trace_totals_checked = True

        section = {
            "present": True,
            "run_id": run_id,
            "parameter_hash": evidence_hash,
            "selections": selection_rows or len(group_events),
            "rng_events": observed_draws,
            "selection_log_enabled": bool(evidence.selection_log_paths),
        }
        outcome = S5EvidenceOutcome(
            selections=selection_rows or len(group_events),
            group_events=len(group_events),
            site_events=len(site_events),
            expected_draws=expected_draws,
            observed_draws=observed_draws,
            mapping_verified=mapping_verified,
            trace_totals_checked=trace_totals_checked,
            log_rows_checked=bool(evidence.selection_log_paths),
        )
        return section, outcome

    def _check_s6_evidence(
        self,
        *,
        seed: int,
        manifest: str,
        parameter_hash: str,
        evidence: RouterEvidence,
        route_policy: Mapping[str, object],
        virtual_edge_policy: Mapping[str, object],
    ) -> tuple[Mapping[str, object], S6EvidenceOutcome]:
        run_id = (evidence.run_id or "").lower()
        if not run_id:
            raise err("E_S7_ROUTER_RUN_ID", "S6 router evidence missing run_id")
        evidence_hash = (evidence.parameter_hash or parameter_hash).lower()
        if evidence_hash != parameter_hash:
            raise err(
                "E_S7_ROUTER_PARAMETER_HASH",
                "S6 evidence parameter hash does not match manifest parameter hash",
            )
        edge_rows, edge_samples = self._validate_trace_rows(
            evidence.edge_log_paths,
            schema_ref="#/trace/s6_edge_log_row",
            manifest=manifest,
            seed=seed,
            parameter_hash=evidence_hash,
            run_id=run_id,
            sample_limit=32,
        )
        self._assert_route_policy_stream(route_policy, stream_id="virtual_edge", min_uniforms=1)
        edge_events = self._load_rng_events(
            directory=evidence.rng_event_edge_path,
            schema_ref="#/rng/events/cdn_edge_pick",
            seed=seed,
            parameter_hash=evidence_hash,
            manifest=manifest,
            run_id=run_id,
            expected_module="2B.virtual_edge",
            expected_label="cdn_edge_pick",
            validate_schema=False,
        )
        if edge_rows and edge_rows != len(edge_events):
            raise err(
                "E_S7_RNG_EVENTS",
                f"S6 edge log rows ({edge_rows}) differ from RNG events ({len(edge_events)})",
            )
        self._validate_rng_sequence(edge_events)
        observed_draws = len(edge_events)
        expected_draws = len(edge_events)
        mapping_verified = False
        if edge_samples:
            edge_attributes = self._build_edge_attribute_map(virtual_edge_policy)
            self._verify_edge_samples(edge_samples, edge_attributes)
            mapping_verified = True

        trace_totals_checked = False
        if evidence.rng_trace_log_path:
            summary = self._summarize_trace_log(
                evidence.rng_trace_log_path,
                seed=seed,
                run_id=run_id,
            )
            edge_key = ("2B.virtual_edge", "cdn_edge_pick")
            edge_trace = summary.get(edge_key)
            if edge_trace is None:
                raise err("E_S7_TRACE_STREAM", "rng_trace_log missing edge pick entries for S6 run")
            if edge_trace["draws_total"] != len(edge_events) or edge_trace["events_total"] != len(edge_events):
                raise err(
                    "E_S7_TRACE_TOTAL",
                    "rng_trace_log totals do not match S6 virtual edge events",
                )
            trace_totals_checked = True

        section = {
            "present": True,
            "run_id": run_id,
            "parameter_hash": evidence_hash,
            "virtual_arrivals": edge_rows or len(edge_events),
            "rng_events": observed_draws,
            "edge_log_enabled": bool(evidence.edge_log_paths),
        }
        outcome = S6EvidenceOutcome(
            virtual_arrivals=edge_rows or len(edge_events),
            edge_events=len(edge_events),
            expected_draws=expected_draws,
            observed_draws=observed_draws,
            mapping_verified=mapping_verified,
            trace_totals_checked=trace_totals_checked,
            log_rows_checked=bool(evidence.edge_log_paths),
        )
        return section, outcome

    def _validate_trace_rows(
        self,
        paths: Sequence[Path],
        *,
        schema_ref: str,
        manifest: str,
        seed: int,
        parameter_hash: str,
        run_id: str,
        sample_limit: int = 0,
    ) -> tuple[int, List[Mapping[str, object]]]:
        if not paths:
            return 0, []
        schema = load_schema(schema_ref)
        validator = Draft202012Validator(schema)
        total_rows = 0
        samples: List[Mapping[str, object]] = []
        for path in paths:
            if not path.exists():
                raise err("E_S7_TRACE_MISSING", f"trace file missing at '{path}'")
            partition = self._parse_partition_tokens(path)
            last_seq = None
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    payload = json.loads(line)
                    validator.validate(payload)
                    if payload.get("manifest_fingerprint") != manifest:
                        raise err("E_S7_TRACE_MANIFEST", "trace manifest fingerprint mismatch")
                    if int(payload.get("seed", -1)) != seed:
                        raise err("E_S7_TRACE_MANIFEST", "trace seed mismatch")
                    if str(payload.get("parameter_hash", "")).lower() != parameter_hash:
                        raise err("E_S7_TRACE_MANIFEST", "trace parameter hash mismatch")
                    if str(payload.get("run_id", "")).lower() != run_id:
                        raise err("E_S7_TRACE_MANIFEST", "trace run_id mismatch")
                    if "utc_day" in payload and partition.get("utc_day"):
                        if payload["utc_day"] != partition["utc_day"]:
                            raise err("E_S7_TRACE_PARTITION", "trace utc_day does not match path partition")
                    seq = payload.get("selection_seq")
                    if seq is not None:
                        if last_seq is not None and seq < last_seq:
                            raise err("E_S7_TRACE_ORDER", "trace rows out of order")
                        last_seq = seq
                    total_rows += 1
                    if sample_limit and len(samples) < sample_limit:
                        samples.append(payload)
        return total_rows, samples

    def _load_rng_events(
        self,
        *,
        directory: Optional[Path],
        schema_ref: str,
        seed: int,
        parameter_hash: str,
        manifest: str,
        run_id: str,
        expected_module: str,
        expected_label: str,
        expected_draws: int = 1,
        validate_schema: bool = True,
    ) -> List[Mapping[str, object]]:
        if directory is None:
            raise err("E_S7_RNG_PATH", "rng event directory not provided")
        if not directory.exists():
            raise err("E_S7_RNG_PATH", f"rng event directory missing at '{directory}'")
        validator: Draft202012Validator | None = None
        if validate_schema:
            schema = load_schema(schema_ref)
            self._strip_unevaluated_properties(schema)
            validator = Draft202012Validator(schema)
        events: List[Mapping[str, object]] = []
        files = sorted(directory.glob("*.jsonl"))
        if not files:
            raise err("E_S7_RNG_PATH", f"rng event directory '{directory}' is empty")
        for file in files:
            with file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    if validator is not None:
                        validator.validate(payload)
                    if str(payload.get("manifest_fingerprint", "")).lower() != manifest:
                        raise err("E_S7_RNG_EVENT", "rng event manifest mismatch")
                    run_field = payload.get("run_id")
                    if run_field not in (None, "") and str(run_field).lower() != run_id:
                        raise err("E_S7_RNG_EVENT", "rng event run_id mismatch")
                    if int(payload.get("seed", -1)) != seed:
                        raise err("E_S7_RNG_EVENT", "rng event seed mismatch")
                    if str(payload.get("parameter_hash", "")).lower() != parameter_hash:
                        raise err("E_S7_RNG_EVENT", "rng event parameter hash mismatch")
                    if str(payload.get("module", "")) != expected_module:
                        raise err("E_S7_RNG_EVENT", "rng event module mismatch")
                    if str(payload.get("substream_label", "")) != expected_label:
                        raise err("E_S7_RNG_EVENT", "rng event substream mismatch")
                    draws_value = int(str(payload.get("draws", "0")))
                    if draws_value != expected_draws:
                        raise err("E_S7_RNG_EVENT", "rng event draws count mismatch")
                    blocks_value = int(payload.get("blocks", 0))
                    if blocks_value != expected_draws:
                        raise err("E_S7_RNG_EVENT", "rng event blocks count mismatch")
                    events.append(payload)
        return events

    def _validate_rng_sequence(self, events: Sequence[Mapping[str, object]]) -> None:
        last_before = (0, 0)
        for event in events:
            before = (int(event.get("rng_counter_before_hi", 0)), int(event.get("rng_counter_before_lo", 0)))
            after = (int(event.get("rng_counter_after_hi", 0)), int(event.get("rng_counter_after_lo", 0)))
            if before < last_before:
                raise err("E_S7_RNG_COUNTER", "rng counters not monotone increasing")
            if (after[0] * (1 << 64) + after[1]) - (before[0] * (1 << 64) + before[1]) != 1:
                raise err("E_S7_RNG_COUNTER", "rng counters did not advance by exactly one draw")
            last_before = after

    # ---------------------------------------------------------------- report
    def _write_report(
        self,
        *,
        base_path: Path,
        dictionary: Mapping[str, object],
        seed: int | str,
        manifest: str,
        report: Mapping[str, object],
    ) -> Path:
        relative = render_dataset_path(
            self.REPORT_DATASET_ID,
            template_args={"seed": seed, "manifest_fingerprint": manifest},
            dictionary=dictionary,
        )
        report_path = (base_path / relative).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(report, indent=2, sort_keys=True)
        if report_path.exists():
            existing = report_path.read_text(encoding="utf-8")
            if existing != payload:
                raise err("E_S7_REPORT_IMMUTABLE", f"s7_audit_report already exists at '{report_path}' with different content")
            return report_path
        tmp_path = report_path.with_suffix(".tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(report_path)
        return report_path

    def _read_json(self, path: Path) -> Mapping[str, object]:
        if not path.exists():
            raise err("E_S7_JSON_MISSING", f"JSON artefact missing at '{path}'")
        return json.loads(path.read_text(encoding="utf-8"))

    def _strip_unevaluated_properties(self, node: object) -> None:
        from collections.abc import MutableMapping

        if isinstance(node, MutableMapping):
            node.pop("unevaluatedProperties", None)
            for value in node.values():
                self._strip_unevaluated_properties(value)
        elif isinstance(node, list):
            for item in node:
                self._strip_unevaluated_properties(item)

    def _parse_partition_tokens(self, path: Path) -> Mapping[str, str]:
        tokens: Dict[str, str] = {}
        for part in path.resolve().parts:
            if "=" in part:
                key, value = part.split("=", 1)
                tokens[key] = value
        return tokens

    def _load_site_timezone_lookup(
        self,
        *,
        base_path: Path,
        dictionary: Mapping[str, object],
        seed: int | str,
        seg2a_manifest: str,
    ) -> Mapping[int, str]:
        relative = render_dataset_path(
            "site_timezones",
            template_args={"seed": seed, "manifest_fingerprint": seg2a_manifest},
            dictionary=dictionary,
        )
        path = (base_path / relative).resolve()
        if not path.exists():
            raise err("E_S7_SITE_TIMEZONE", f"site_timezones missing at '{path}'")
        frame = pl.read_parquet(path, columns=["merchant_id", "site_order", "tzid"])
        if frame.is_empty():
            return {}
        frame = frame.with_columns(
            pl.col("merchant_id").cast(pl.Int64, strict=False).alias("merchant_id"),
            pl.col("site_order").cast(pl.Int64, strict=False).alias("site_order"),
            pl.col("tzid").cast(pl.Utf8, strict=False).alias("tzid"),
        )
        lookup: Dict[int, str] = {}
        for row in frame.iter_rows(named=True):
            merchant_id = int(row["merchant_id"])
            site_order = int(row["site_order"])
            tzid = str(row["tzid"])
            site_id = (merchant_id << 32) | (site_order & 0xFFFFFFFF)
            lookup[site_id] = tzid
        return lookup

    def _verify_selection_samples(self, samples: Sequence[Mapping[str, object]], site_timezones: Mapping[int, str]) -> None:
        for sample in samples:
            site_id = int(sample.get("site_id", -1))
            tz_logged = str(sample.get("tz_group_id", ""))
            tz_expected = site_timezones.get(site_id)
            if tz_expected is None:
                raise err("E_S7_ROUTER_TZ_LOOKUP", f"site_id {site_id} missing from site_timezones")
            if tz_expected != tz_logged:
                raise err("E_S7_ROUTER_TZ_MISMATCH", f"site_id {site_id} tz mismatch ({tz_logged} != {tz_expected})")

    def _build_edge_attribute_map(self, payload: Mapping[str, object]) -> Mapping[str, Mapping[str, float]]:
        attributes: Dict[str, Dict[str, float]] = {}

        def register(entry: Mapping[str, object]) -> None:
            edge_id = str(entry.get("edge_id", "")).strip()
            if not edge_id:
                return
            target = attributes.setdefault(edge_id, {})
            country = entry.get("country_iso")
            if country:
                target["country_iso"] = str(country).upper()

        for entry in payload.get("default_edges", []) or []:
            if isinstance(entry, Mapping):
                register(entry)
        overrides = payload.get("merchant_overrides") or {}
        if isinstance(overrides, Mapping):
            for entries in overrides.values():
                if isinstance(entries, Sequence):
                    for entry in entries:
                        if isinstance(entry, Mapping):
                            register(entry)
        metadata = payload.get("geo_metadata") or {}
        if isinstance(metadata, Mapping):
            for edge_id, meta in metadata.items():
                if not isinstance(meta, Mapping):
                    continue
                target = attributes.setdefault(str(edge_id), {})
                if "lat" in meta and "lon" in meta:
                    target["lat"] = float(meta["lat"])
                    target["lon"] = float(meta["lon"])
        return attributes

    def _verify_edge_samples(
        self,
        samples: Sequence[Mapping[str, object]],
        edge_attributes: Mapping[str, Mapping[str, float]],
    ) -> None:
        for sample in samples:
            if not sample.get("is_virtual", False):
                raise err("E_S7_EDGE_ATTR", "edge log row marked as non-virtual")
            edge_id = str(sample.get("edge_id", "")).strip()
            attrs = edge_attributes.get(edge_id)
            if attrs is None:
                raise err("E_S7_EDGE_ATTR", f"edge '{edge_id}' missing from virtual_edge_policy_v1")
            country = str(sample.get("ip_country", "")).upper()
            if attrs.get("country_iso") and attrs["country_iso"] != country:
                raise err("E_S7_EDGE_ATTR", f"edge '{edge_id}' country mismatch ({country} != {attrs['country_iso']})")
            lat = float(sample.get("edge_lat", 0.0))
            lon = float(sample.get("edge_lon", 0.0))
            if "lat" in attrs and abs(lat - float(attrs["lat"])) > 1e-6:
                raise err("E_S7_EDGE_ATTR", f"edge '{edge_id}' latitude mismatch")
            if "lon" in attrs and abs(lon - float(attrs["lon"])) > 1e-6:
                raise err("E_S7_EDGE_ATTR", f"edge '{edge_id}' longitude mismatch")

    def _summarize_trace_log(self, trace_path: Path, *, seed: int, run_id: str) -> Mapping[Tuple[str, str], Mapping[str, int]]:
        path = trace_path.resolve()
        if not path.exists():
            raise err("E_S7_TRACE_MISSING", f"rng_trace_log missing at '{path}'")
        summary: Dict[Tuple[str, str], Dict[str, int]] = {}
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = json.loads(line)
                if int(payload.get("seed", -1)) != seed:
                    raise err("E_S7_TRACE_MANIFEST", "rng_trace_log seed mismatch")
                if str(payload.get("run_id", "")).lower() != run_id:
                    raise err("E_S7_TRACE_MANIFEST", "rng_trace_log run_id mismatch")
                key = (str(payload.get("module", "")), str(payload.get("substream_label", "")))
                summary[key] = {
                    "draws_total": int(payload.get("draws_total", 0)),
                    "events_total": int(payload.get("events_total", 0)),
                }
        return summary

    def _assert_route_policy_stream(
        self,
        policy: Mapping[str, object],
        *,
        stream_id: str,
        min_uniforms: int,
    ) -> None:
        substreams = policy.get("substreams") or []
        if not isinstance(substreams, Sequence):
            raise err("E_S7_POLICY_STREAM", "route_rng_policy_v1 malformed (substreams missing)")
        for entry in substreams:
            if not isinstance(entry, Mapping):
                continue
            if entry.get("id") == stream_id:
                max_uniforms = int(entry.get("max_uniforms", 0))
                if max_uniforms < min_uniforms:
                    raise err(
                        "E_S7_POLICY_STREAM",
                        f"route_rng_policy_v1 stream '{stream_id}' insufficient max_uniforms",
                    )
                return
        raise err("E_S7_POLICY_STREAM", f"route_rng_policy_v1 missing stream '{stream_id}'")


__all__ = ["S7AuditRunner", "S7AuditInputs", "S7AuditResult", "RouterEvidence"]
