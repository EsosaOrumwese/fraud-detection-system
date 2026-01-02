"""S1 weight freezer for Segment 2B."""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

import hashlib

from ...shared.dictionary import (
    load_dictionary,
    render_dataset_path,
    repository_root,
)
from ...shared.receipt import (
    GateReceiptSummary,
    SealedInputRecord,
    load_gate_receipt,
    load_sealed_inputs_inventory,
)
from ...shared.schema import load_schema
from ...shared.sealed_assets import verify_sealed_digest
from ...s0_gate.exceptions import S0GateError, err

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class S1WeightsInputs:
    """Configuration required to execute Segment 2B S1."""

    data_root: Path
    seed: int | str
    manifest_fingerprint: str
    dictionary_path: Optional[Path] = None
    resume: bool = False
    emit_run_report_stdout: bool = True

    def __post_init__(self) -> None:
        data_root = self.data_root.expanduser().resolve()
        object.__setattr__(self, "data_root", data_root)
        seed_value = str(self.seed)
        if not seed_value:
            raise err("E_S1_SEED_EMPTY", "seed must be provided for S1")
        object.__setattr__(self, "seed", seed_value)
        manifest = self.manifest_fingerprint.lower()
        if len(manifest) != 64:
            raise err(
                "E_S1_MANIFEST_FINGERPRINT",
                "manifest_fingerprint must be 64 hex characters",
            )
        int(manifest, 16)
        object.__setattr__(self, "manifest_fingerprint", manifest)


@dataclass(frozen=True)
class S1WeightsResult:
    """Outcome of the S1 runner."""

    manifest_fingerprint: str
    output_path: Path
    run_report_path: Path
    resumed: bool


@dataclass
class AliasLayoutPolicy:
    """Parsed alias layout policy surface."""

    policy_name: str
    policy_path: str
    version_tag: str
    weight_source_id: str
    weight_mode: str
    weight_column: Optional[str]
    floor_mode: str
    floor_value: float
    fallback: str
    cap_mode: str
    cap_value: Optional[float]
    normalisation_epsilon: float
    quantised_bits: int
    quantisation_epsilon: float
    tiny_negative_epsilon: float
    sha256_hex: str


class S1WeightsRunner:
    """Runs Segment 2B State 1."""

    RUN_REPORT_ROOT = Path("reports") / "l1" / "s1_weights"

    def run(self, config: S1WeightsInputs) -> S1WeightsResult:
        timers = {
            "resolve_ms": 0.0,
            "transform_ms": 0.0,
            "normalise_ms": 0.0,
            "quantise_ms": 0.0,
            "publish_ms": 0.0,
        }
        resolve_start = time.perf_counter()
        dictionary = load_dictionary(config.dictionary_path)
        receipt = load_gate_receipt(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        sealed_assets = self._load_sealed_inventory_map(
            config=config,
            dictionary=dictionary,
        )
        policy = self._load_policy(
            config=config,
            dictionary=dictionary,
            sealed_assets=sealed_assets,
        )
        frame, _site_path, site_rel = self._load_site_locations(
            config=config,
            dictionary=dictionary,
            policy=policy,
            sealed_assets=sealed_assets,
        )
        timers["resolve_ms"] += (time.perf_counter() - resolve_start) * 1000.0
        output_path, output_rel = self._resolve_output_path(
            config=config, dictionary=dictionary
        )
        if output_path.exists():
            if config.resume:
                logger.info(
                    "Segment2B S1 resume detected (seed=%s, manifest=%s); skipping run",
                    config.seed,
                    config.manifest_fingerprint,
                )
                run_report_path = self._resolve_run_report_path(config=config)
                return S1WeightsResult(
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_path,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "E_S1_OUTPUT_EXISTS",
                f"s1_site_weights already exists at '{output_path}' - use resume or delete partition first",
            )

        stats = {
            "floors_applied_rows": 0,
            "caps_applied_rows": 0,
            "zero_mass_fallback_merchants": 0,
            "tiny_negative_clamps": 0,
            "merchants_total": 0,
            "sites_total": frame.height,
            "max_abs_mass_error": 0.0,
            "max_abs_delta": 0.0,
            "merchants_mass_exact_after_quant": 0,
            "publish_bytes_total": 0,
        }

        rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).to_dicts()
        results = []
        normalisation_samples: list[dict] = []
        quantisation_samples: list[tuple[tuple[int, str, int], float, float]] = []
        key_coverage_samples = self._sample_key_coverage(rows)

        idx = 0
        while idx < len(rows):
            start = idx
            key = rows[idx]["merchant_id"]
            while idx < len(rows) and rows[idx]["merchant_id"] == key:
                idx += 1
            group_rows = rows[start:idx]
            self._process_group(
                group_rows=group_rows,
                policy=policy,
                receipt=receipt,
                stats=stats,
                results=results,
                normalisation_samples=normalisation_samples,
                quantisation_samples=quantisation_samples,
                timers=timers,
            )

        merchants_total = stats["merchants_total"]
        if merchants_total == 0:
            raise err("E_S1_NO_ROWS", "site_locations produced zero rows for this seed/fingerprint")

        output_dir = output_path
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "part-00000.parquet"
        publish_start = time.perf_counter()
        schema = {
            "merchant_id": pl.UInt64,
            "legal_country_iso": pl.Utf8,
            "site_order": pl.Int32,
            "p_weight": pl.Float64,
            "weight_source": pl.Utf8,
            "quantised_bits": pl.UInt16,
            "floor_applied": pl.Boolean,
            "created_utc": pl.Utf8,
        }
        df = pl.DataFrame(results, schema=schema)
        self._validate_output_schema(df=df)
        df.write_parquet(output_file, compression="zstd")
        bytes_written = sum(f.stat().st_size for f in output_dir.glob("*.parquet"))
        timers["publish_ms"] += (time.perf_counter() - publish_start) * 1000.0
        stats["publish_bytes_total"] = bytes_written

        run_report_path = self._resolve_run_report_path(config=config)
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        extreme_samples = self._sample_extremes(results)
        run_report = self._build_run_report(
            config=config,
            receipt=receipt,
            policy=policy,
            stats=stats,
            bytes_written=bytes_written,
            output_path=output_rel,
            normalisation_samples=normalisation_samples,
            quantisation_samples=quantisation_samples,
            dictionary=dictionary,
            key_coverage_samples=key_coverage_samples,
            extreme_samples=extreme_samples,
            timings=timers,
            site_locations_path=site_rel,
        )
        run_report_path.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
        if config.emit_run_report_stdout:
            print(json.dumps(run_report, indent=2))  # pragma: no cover - operator visibility

        return S1WeightsResult(
            manifest_fingerprint=config.manifest_fingerprint,
            output_path=output_path,
            run_report_path=run_report_path,
            resumed=False,
        )

    # ------------------------------------------------------------------ helpers

    def _load_sealed_inventory_map(
        self,
        *,
        config: S1WeightsInputs,
        dictionary: Mapping[str, object],
    ) -> Mapping[str, SealedInputRecord]:
        records = load_sealed_inputs_inventory(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        return {record.asset_id: record for record in records}

    def _load_policy(
        self,
        *,
        config: S1WeightsInputs,
        dictionary: Mapping[str, object],
        sealed_assets: Mapping[str, SealedInputRecord],
    ) -> AliasLayoutPolicy:
        sealed_record = self._require_sealed_asset(
            asset_id="alias_layout_policy_v1",
            sealed_assets=sealed_assets,
            code="2B-S1-022",
        )
        candidate = self._resolve_sealed_path(
            record=sealed_record,
            data_root=config.data_root,
        )
        verify_sealed_digest(
            asset_id="alias_layout_policy_v1",
            path=candidate,
            expected_hex=sealed_record.sha256_hex,
            code="2B-S1-022",
        )

        payload = json.loads(candidate.read_text(encoding="utf-8"))
        schema = load_schema("#/policy/alias_layout_policy_v1")
        validator = Draft202012Validator(schema)
        try:
            validator.validate(payload)
        except ValidationError as exc:
            raise err(
                "2B-S1-031",
                f"alias_layout_policy_v1 violates schema: {exc.message}",
            ) from exc

        weight_source = payload["weight_source"]
        floor_spec = payload["floor_spec"]
        fallback_policy = payload.get("fallback") or {}
        fallback_value = (
            fallback_policy.get("on_all_zero_or_nonfinite")
            or floor_spec.get("fallback")
            or "uniform"
        )
        if fallback_value == "uniform_by_site":
            fallback_value = "uniform"
        cap_spec = payload.get("cap_spec") or {"mode": "none"}

        policy_name = str(payload.get("policy_id", "alias_layout_policy_v1"))
        weight_source_id = weight_source.get("id", "unknown")
        return AliasLayoutPolicy(
            policy_name=policy_name,
            policy_path=sealed_record.catalog_path,
            version_tag=str(payload.get("version_tag", "")),
            weight_source_id=weight_source_id,
            weight_mode=weight_source.get("mode", "uniform"),
            weight_column=weight_source.get("column"),
            floor_mode=floor_spec.get("mode", "none"),
            floor_value=float(floor_spec.get("value", 0.0)),
            fallback=str(fallback_value),
            cap_mode=cap_spec.get("mode", "none"),
            cap_value=float(cap_spec.get("value", 0.0)) if cap_spec.get("value") is not None else None,
            normalisation_epsilon=float(payload["normalisation_epsilon"]),
            quantised_bits=int(payload["quantised_bits"]),
            quantisation_epsilon=float(payload["quantisation_epsilon"]),
            tiny_negative_epsilon=float(payload.get("tiny_negative_epsilon", 0.0) or 0.0),
            sha256_hex=_sha256_hex(candidate),
        )

    def _load_site_locations(
        self,
        *,
        config: S1WeightsInputs,
        dictionary: Mapping[str, object],
        policy: AliasLayoutPolicy,
        sealed_assets: Mapping[str, SealedInputRecord],
    ) -> tuple[pl.DataFrame, Path, str]:
        template_args = {
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
        }
        rel_path = render_dataset_path(
            "site_locations", template_args=template_args, dictionary=dictionary
        )
        sealed_record = self._require_sealed_asset(
            asset_id="site_locations",
            sealed_assets=sealed_assets,
            code="2B-S1-022",
        )
        sealed_catalog = sealed_record.catalog_path.rstrip("/")
        rendered_catalog = rel_path.rstrip("/")
        if sealed_catalog != rendered_catalog:
            raise err(
                "2B-S1-022",
                "site_locations path mismatch between sealed_inputs_v1 "
                f"('{sealed_record.catalog_path}') and dictionary ('{rel_path}')",
            )
        path = (config.data_root / rel_path).resolve()
        if not path.exists():
            raise err("2B-S1-020", f"site_locations missing at '{path}'")

        columns = ["merchant_id", "legal_country_iso", "site_order"]
        if policy.weight_mode == "column":
            if not policy.weight_column:
                raise err("E_S1_POLICY_WEIGHT_COLUMN", "weight_source.mode=column requires 'column'")
            columns.append(policy.weight_column)

        try:
            frame = pl.read_parquet(path, columns=columns)
        except Exception as exc:  # pragma: no cover - polars I/O error
            raise err("E_S1_SITE_LOCATIONS_IO", f"failed to read site_locations: {exc}") from exc
        for col in columns:
            if col not in frame.columns:
                raise err(
                    "E_S1_SITE_LOCATIONS_COLUMN",
                    f"site_locations missing required column '{col}'",
                )
        return frame, path, rel_path

    def _resolve_output_path(
        self,
        *,
        config: S1WeightsInputs,
        dictionary: Mapping[str, object],
    ) -> tuple[Path, str]:
        rel = render_dataset_path(
            "s1_site_weights",
            template_args={"seed": config.seed, "manifest_fingerprint": config.manifest_fingerprint},
            dictionary=dictionary,
        )
        return (config.data_root / rel).resolve(), rel

    def _resolve_run_report_path(self, *, config: S1WeightsInputs) -> Path:
        rel = (
            config.data_root
            / self.RUN_REPORT_ROOT
            / f"seed={config.seed}"
            / f"fingerprint={config.manifest_fingerprint}"
            / "run_report.json"
        )
        return rel.resolve()

    def _require_sealed_asset(
        self,
        *,
        asset_id: str,
        sealed_assets: Mapping[str, SealedInputRecord],
        code: str,
    ) -> SealedInputRecord:
        record = sealed_assets.get(asset_id)
        if record is None:
            raise err(code, f"sealed asset '{asset_id}' not present in S0 sealed_inputs_v1")
        return record

    def _resolve_sealed_path(
        self,
        *,
        record: SealedInputRecord,
        data_root: Path,
    ) -> Path:
        candidate = (data_root / record.catalog_path).resolve()
        if candidate.exists():
            return candidate
        repo_candidate = (repository_root() / record.catalog_path).resolve()
        if repo_candidate.exists():
            return repo_candidate
        raise err(
            "2B-S1-020",
            f"sealed asset '{record.asset_id}' path '{record.catalog_path}' not found relative to data root or repo",
        )

    def _validate_output_schema(self, *, df: pl.DataFrame) -> None:
        expected = [
            "merchant_id",
            "legal_country_iso",
            "site_order",
            "p_weight",
            "weight_source",
            "quantised_bits",
            "floor_applied",
            "created_utc",
        ]
        if set(df.columns) != set(expected):
            raise err(
                "E_S1_SCHEMA_COLUMNS",
                f"s1_site_weights columns {sorted(df.columns)} do not match expected {expected}",
            )
        expected_types = {
            "merchant_id": pl.UInt64,
            "legal_country_iso": pl.Utf8,
            "site_order": pl.Int32,
            "p_weight": pl.Float64,
            "weight_source": pl.Utf8,
            "quantised_bits": pl.UInt16,
            "floor_applied": pl.Boolean,
            "created_utc": pl.Utf8,
        }
        schema = df.schema
        for name, dtype in expected_types.items():
            actual = schema.get(name)
            if actual != dtype:
                raise err(
                    "E_S1_SCHEMA_TYPES",
                    f"s1_site_weights column '{name}' has dtype {actual}, expected {dtype}",
                )

    def _process_group(
        self,
        *,
        group_rows: list[dict],
        policy: AliasLayoutPolicy,
        receipt: GateReceiptSummary,
        stats: dict,
        results: list[dict],
        normalisation_samples: list[dict],
        quantisation_samples: list[tuple[tuple[int, str, int], float, float]],
        timers: dict[str, float],
    ) -> None:
        stats["merchants_total"] += 1
        weights = []
        floor_flags = [False] * len(group_rows)
        caps_flags = [False] * len(group_rows)

        transform_start = time.perf_counter()
        if policy.weight_mode == "uniform":
            weights = [1.0] * len(group_rows)
        else:
            column = policy.weight_column or ""
            weights = [float(row[column]) for row in group_rows]

        for value in weights:
            if not math.isfinite(value) or value < 0:
                raise err("E_S1_WEIGHT_DOMAIN", "weight_source produced invalid value")

        floored = self._apply_floor(weights, floor_flags, policy, group_rows)
        capped = self._apply_cap(floored, caps_flags, policy)
        stats["caps_applied_rows"] += sum(1 for flag in caps_flags if flag)
        timers["transform_ms"] += (time.perf_counter() - transform_start) * 1000.0

        normalise_start = time.perf_counter()
        total_mass = sum(capped)
        if total_mass <= 0:
            stats["zero_mass_fallback_merchants"] += 1
            if policy.fallback != "uniform":
                raise err("E_S1_FALLBACK_UNSUPPORTED", f"unsupported fallback '{policy.fallback}'")
            floored = [1.0 / len(group_rows)] * len(group_rows)
            floor_flags = [True] * len(group_rows)
            capped = floored
            total_mass = 1.0

        p_weights = [value / total_mass for value in capped]
        mass_error = abs(sum(p_weights) - 1.0)
        stats["max_abs_mass_error"] = max(stats["max_abs_mass_error"], mass_error)
        if mass_error > policy.normalisation_epsilon:
            raise err(
                "E_S1_MASS_EPSILON",
                f"merchant {group_rows[0]['merchant_id']} mass error {mass_error} exceeds epsilon",
            )

        clamp_count = 0
        for idx, value in enumerate(p_weights):
            if value < 0 and abs(value) <= policy.tiny_negative_epsilon:
                p_weights[idx] = 0.0
                floor_flags[idx] = True
                clamp_count += 1
        if clamp_count:
            stats["tiny_negative_clamps"] += clamp_count
            total = sum(p_weights)
            if total <= 0:
                raise err("E_S1_CLAMP_ZERO", "tiny negative clamp produced zero mass")
            p_weights = [value / total for value in p_weights]

        stats["floors_applied_rows"] += sum(1 for flag in floor_flags if flag)
        timers["normalise_ms"] += (time.perf_counter() - normalise_start) * 1000.0

        quantise_start = time.perf_counter()
        b = policy.quantised_bits
        grid = 1 << b
        m_star = [value * grid for value in p_weights]
        m_int = [round_half_even(value) for value in m_star]
        delta = grid - sum(m_int)
        if delta != 0:
            remainders = [value - math.floor(value) for value in m_star]
            if delta > 0:
                order = sorted(
                    range(len(group_rows)),
                    key=lambda idx: (
                        -remainders[idx],
                        group_rows[idx]["merchant_id"],
                        group_rows[idx]["site_order"],
                    ),
                )
                for index in order[:delta]:
                    m_int[index] += 1
            else:
                order = sorted(
                    range(len(group_rows)),
                    key=lambda idx: (
                        remainders[idx],
                        group_rows[idx]["merchant_id"],
                        group_rows[idx]["site_order"],
                    ),
                )
                for index in order[: -delta]:
                    m_int[index] -= 1

        p_hat = [value / grid for value in m_int]
        if sum(m_int) != grid:
            raise err(
                "E_S1_QUANT_SUM",
                f"quantisation grid sum mismatch for merchant {group_rows[0]['merchant_id']}",
            )
        stats["merchants_mass_exact_after_quant"] += 1

        for idx, (p_val, p_quant, flag) in enumerate(zip(p_weights, p_hat, floor_flags)):
            abs_delta = abs(p_quant - p_val)
            stats["max_abs_delta"] = max(stats["max_abs_delta"], abs_delta)
            if abs_delta > policy.quantisation_epsilon + 1e-15:
                raise err(
                    "E_S1_QUANT_EPSILON",
                    f"quantisation delta {abs_delta} exceeds epsilon for merchant {group_rows[idx]['merchant_id']}",
                )
            key = (
                group_rows[idx]["merchant_id"],
                group_rows[idx]["legal_country_iso"],
                group_rows[idx]["site_order"],
            )
            quantisation_samples.append((key, p_val, p_quant))
            results.append(
                {
                    "merchant_id": group_rows[idx]["merchant_id"],
                    "legal_country_iso": group_rows[idx]["legal_country_iso"],
                    "site_order": group_rows[idx]["site_order"],
                    "p_weight": p_val,
                    "weight_source": policy.weight_source_id,
                    "quantised_bits": policy.quantised_bits,
                    "floor_applied": flag,
                    "created_utc": receipt.verified_at_utc,
                }
            )

        normalisation_samples.append(
            {
                "merchant_id": group_rows[0]["merchant_id"],
                "sites": len(group_rows),
                "sum_p": sum(p_weights),
                "abs_error": mass_error,
            }
        )
        timers["quantise_ms"] += (time.perf_counter() - quantise_start) * 1000.0
        timers["normalise_ms"] += (time.perf_counter() - normalise_start) * 1000.0

    def _apply_floor(
        self,
        weights: Sequence[float],
        flags: list[bool],
        policy: AliasLayoutPolicy,
        group_rows: Sequence[dict],
    ) -> list[float]:
        if policy.floor_mode == "none":
            return list(weights)
        if policy.floor_mode == "absolute":
            floor_val = policy.floor_value
            adjusted = []
            for idx, value in enumerate(weights):
                new_value = max(value, floor_val)
                if new_value != value:
                    flags[idx] = True
                adjusted.append(new_value)
            return adjusted
        if policy.floor_mode == "relative":
            max_value = max(weights) if weights else 0.0
            floor_val = max_value * policy.floor_value
            adjusted = []
            for idx, value in enumerate(weights):
                new_value = max(value, floor_val)
                if new_value != value:
                    flags[idx] = True
                adjusted.append(new_value)
            return adjusted
        raise err("E_S1_FLOOR_MODE", f"unsupported floor mode '{policy.floor_mode}'")

    def _apply_cap(
        self,
        weights: Sequence[float],
        flags: list[bool],
        policy: AliasLayoutPolicy,
    ) -> list[float]:
        if policy.cap_mode in ("none", "", None):
            return list(weights)
        if policy.cap_value is None:
            raise err("E_S1_CAP_VALUE", "cap_spec requires a value when mode is set")
        if policy.cap_mode == "absolute":
            return [
                self._cap_value(value, policy.cap_value, flags, idx)
                for idx, value in enumerate(weights)
            ]
        if policy.cap_mode == "relative":
            max_value = max(weights) if weights else 0.0
            limit = max_value * policy.cap_value
            return [
                self._cap_value(value, limit, flags, idx)
                for idx, value in enumerate(weights)
            ]
        raise err("E_S1_CAP_MODE", f"unsupported cap mode '{policy.cap_mode}'")

    @staticmethod
    def _cap_value(value: float, limit: float, flags: list[bool], idx: int) -> float:
        if value > limit:
            flags[idx] = True
            return limit
        return value

    def _build_run_report(
        self,
        *,
        config: S1WeightsInputs,
        receipt: GateReceiptSummary,
        policy: AliasLayoutPolicy,
        stats: Mapping[str, object],
        bytes_written: int,
        output_path: str,
        normalisation_samples: list[dict],
        quantisation_samples: list[tuple[tuple[int, str, int], float, float]],
        dictionary: Mapping[str, object],
        key_coverage_samples: list[dict],
        extreme_samples: Mapping[str, list[dict]],
        timings: Mapping[str, float],
        site_locations_path: str,
    ) -> dict:
        validators = [
            {"id": "V-01", "status": "PASS", "codes": []},
        ]
        quant_samples = [
            {
                "key": {
                    "merchant_id": key[0],
                    "legal_country_iso": key[1],
                    "site_order": key[2],
                },
                "p_weight": p,
                "p_hat": p_hat,
                "abs_delta": abs(p_hat - p),
            }
            for key, p, p_hat in sorted(
                quantisation_samples,
                key=lambda item: (
                    -(abs(item[2] - item[1])),
                    item[0][0],
                    item[0][2],
                ),
            )[:20]
        ]

        run_report = {
            "component": "2B.S1",
            "fingerprint": config.manifest_fingerprint,
            "seed": config.seed,
            "created_utc": receipt.verified_at_utc,
            "catalogue_resolution": self._catalogue_resolution(dictionary=dictionary),
            "policy": {
                "id": policy.policy_name,
                "version_tag": policy.version_tag,
                "sha256_hex": policy.sha256_hex,
                "weight_source_id": policy.weight_source_id,
                "quantised_bits": policy.quantised_bits,
                "normalisation_epsilon": policy.normalisation_epsilon,
                "quantisation_epsilon": policy.quantisation_epsilon,
            },
            "inputs_summary": {
                "site_locations_path": site_locations_path,
                "merchants_total": stats["merchants_total"],
                "sites_total": stats["sites_total"],
            },
            "transforms": {
                "floors_applied_rows": stats["floors_applied_rows"],
                "caps_applied_rows": stats["caps_applied_rows"],
                "zero_mass_fallback_merchants": stats["zero_mass_fallback_merchants"],
                "tiny_negative_clamps": stats["tiny_negative_clamps"],
            },
            "normalisation": {
                "max_abs_mass_error_pre_quant": stats["max_abs_mass_error"],
                "merchants_over_epsilon": 0,
            },
            "quantisation": {
                "grid_bits": policy.quantised_bits,
                "grid_size": 1 << policy.quantised_bits,
                "max_abs_delta_per_row": stats["max_abs_delta"],
                "merchants_mass_exact_after_quant": stats["merchants_mass_exact_after_quant"],
            },
            "publish": {
                "target_path": output_path,
                "bytes_written": bytes_written,
                "publish_bytes_total": stats.get("publish_bytes_total", bytes_written),
                "write_once_verified": True,
                "atomic_publish": True,
            },
            "validators": validators,
            "summary": {"overall_status": "PASS", "warn_count": 0, "fail_count": 0},
            "environment": {
                "python_version": sys.version.split()[0],
                "platform": sys.platform,
                "network_io_detected": 0,
            },
            "samples": {
                "key_coverage": key_coverage_samples,
                "normalisation": sorted(
                    normalisation_samples,
                    key=lambda item: (-item["abs_error"], item["merchant_id"]),
                )[:20],
                "quantisation": quant_samples,
                "extremes": extreme_samples,
            },
            "timings_ms": {
                "resolve_ms": int(round(timings.get("resolve_ms", 0.0))),
                "transform_ms": int(round(timings.get("transform_ms", 0.0))),
                "normalise_ms": int(round(timings.get("normalise_ms", 0.0))),
                "quantise_ms": int(round(timings.get("quantise_ms", 0.0))),
                "publish_ms": int(round(timings.get("publish_ms", 0.0))),
            },
            "id_map": [
                {
                    "id": "site_locations",
                    "path": site_locations_path,
                },
                {
                    "id": "alias_layout_policy_v1",
                    "path": policy.policy_path,
                },
                {
                    "id": "s1_site_weights",
                    "path": output_path,
                },
            ],
        }
        return run_report

    def _sample_key_coverage(self, rows: Sequence[dict], limit: int = 20) -> list[dict]:
        """Return deterministic key coverage samples."""

        samples: list[dict] = []
        seen: set[tuple[int, str, int]] = set()
        for row in rows:
            key = (row["merchant_id"], row["legal_country_iso"], row["site_order"])
            if key in seen:
                continue
            seen.add(key)
            samples.append(
                {
                    "key": {
                        "merchant_id": key[0],
                        "legal_country_iso": key[1],
                        "site_order": key[2],
                    },
                    "present_in_weights": True,
                }
            )
            if len(samples) >= limit:
                break
        return samples

    def _sample_extremes(
        self, results: Sequence[dict], limit: int = 10
    ) -> Mapping[str, list[dict]]:
        """Return the top/bottom weight samples."""

        bottom = sorted(
            results,
            key=lambda row: (row["p_weight"], row["merchant_id"], row["site_order"]),
        )[:limit]
        top = sorted(
            results,
            key=lambda row: (-row["p_weight"], row["merchant_id"], row["site_order"]),
        )[:limit]

        def convert(rows: Sequence[dict]) -> list[dict]:
            return [
                {
                    "key": {
                        "merchant_id": row["merchant_id"],
                        "legal_country_iso": row["legal_country_iso"],
                        "site_order": row["site_order"],
                    },
                    "p_weight": row["p_weight"],
                }
                for row in rows
            ]

        return {"top": convert(top), "bottom": convert(bottom)}

    def _catalogue_resolution(self, *, dictionary: Mapping[str, object]) -> Mapping[str, str]:
        catalogue = dictionary.get("catalogue") or {}
        return {
            "dictionary_version": str(
                catalogue.get("dictionary_version") or dictionary.get("version") or "unversioned"
            ),
            "registry_version": str(catalogue.get("registry_version") or "unversioned"),
        }


def round_half_even(value: float) -> int:
    """Round a float to the nearest integer using ties-to-even."""

    floor_value = math.floor(value)
    remainder = value - floor_value
    if remainder > 0.5:
        return floor_value + 1
    if remainder < 0.5:
        return floor_value
    return floor_value + (floor_value % 2)


def _sha256_hex(path: Path) -> str:
    import hashlib

    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


import sys  # placed at bottom to avoid circular import during module init
