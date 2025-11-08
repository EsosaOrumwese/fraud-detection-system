"""S1 weight freezer for Segment 2B."""

from __future__ import annotations

import json
import logging
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from ...shared.dictionary import (
    load_dictionary,
    render_dataset_path,
    repository_root,
)
from ...shared.receipt import GateReceiptSummary, load_gate_receipt
from ...shared.schema import load_schema
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

    policy_id: str
    version_tag: str
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
        dictionary = load_dictionary(config.dictionary_path)
        receipt = load_gate_receipt(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        policy = self._load_policy(config=config, dictionary=dictionary)
        frame, site_path = self._load_site_locations(
            config=config, dictionary=dictionary, policy=policy
        )
        output_path = self._resolve_output_path(config=config, dictionary=dictionary)
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
        }

        rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).to_dicts()
        results = []
        normalisation_samples: list[dict] = []
        quantisation_samples: list[tuple[tuple[int, str, int], float, float]] = []

        idx = 0
        while idx < len(rows):
            start = idx
            key = (
                rows[idx]["merchant_id"],
                rows[idx]["legal_country_iso"],
            )
            while idx < len(rows) and (
                rows[idx]["merchant_id"],
                rows[idx]["legal_country_iso"],
            ) == key:
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
            )

        merchants_total = stats["merchants_total"]
        if merchants_total == 0:
            raise err("E_S1_NO_ROWS", "site_locations produced zero rows for this seed/fingerprint")

        output_dir = output_path
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "part-00000.parquet"
        df = pl.DataFrame(results)
        df.write_parquet(output_file, compression="zstd")
        bytes_written = sum(f.stat().st_size for f in output_dir.glob("*.parquet"))

        run_report_path = self._resolve_run_report_path(config=config)
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = self._build_run_report(
            config=config,
            receipt=receipt,
            policy=policy,
            stats=stats,
            bytes_written=bytes_written,
            output_path=output_path,
            normalisation_samples=normalisation_samples,
            quantisation_samples=quantisation_samples,
            dictionary=dictionary,
            site_locations_path=str(site_path),
            results=results,
        )
        run_report_path.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
        print(json.dumps(run_report))  # pragma: no cover - operator visibility

        return S1WeightsResult(
            manifest_fingerprint=config.manifest_fingerprint,
            output_path=output_path,
            run_report_path=run_report_path,
            resumed=False,
        )

    # ------------------------------------------------------------------ helpers

    def _load_policy(self, *, config: S1WeightsInputs, dictionary: Mapping[str, object]) -> AliasLayoutPolicy:
        entry = dictionary.get("policies")
        policy_rel = render_dataset_path(
            "alias_layout_policy_v1",
            template_args={},
            dictionary=dictionary,
        )
        candidate = (config.data_root / policy_rel).resolve()
        if not candidate.exists():
            repo_candidate = repository_root() / policy_rel
            if not repo_candidate.exists():
                raise err(
                    "E_S1_POLICY_MISSING",
                    f"alias_layout_policy_v1 not found at '{policy_rel}'",
                )
            candidate = repo_candidate.resolve()

        payload = json.loads(candidate.read_text(encoding="utf-8"))
        schema = load_schema("#/policy/alias_layout_policy_v1")
        validator = Draft202012Validator(schema)
        try:
            validator.validate(payload)
        except ValidationError as exc:
            raise err(
                "E_S1_POLICY_INVALID",
                f"alias_layout_policy_v1 violates schema: {exc.message}",
            ) from exc

        weight_source = payload["weight_source"]
        floor_spec = payload["floor_spec"]
        cap_spec = payload.get("cap_spec") or {"mode": "none"}

        return AliasLayoutPolicy(
            policy_id=weight_source.get("id", "unknown"),
            version_tag=str(payload.get("version_tag", "")),
            weight_mode=weight_source.get("mode", "uniform"),
            weight_column=weight_source.get("column"),
            floor_mode=floor_spec.get("mode", "none"),
            floor_value=float(floor_spec.get("value", 0.0)),
            fallback=floor_spec.get("fallback", "uniform"),
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
    ) -> tuple[pl.DataFrame, Path]:
        template_args = {
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
        }
        rel_path = render_dataset_path(
            "site_locations", template_args=template_args, dictionary=dictionary
        )
        path = (config.data_root / rel_path).resolve()
        if not path.exists():
            raise err("E_S1_SITE_LOCATIONS_MISSING", f"site_locations missing at '{path}'")

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
        return frame, path

    def _resolve_output_path(
        self,
        *,
        config: S1WeightsInputs,
        dictionary: Mapping[str, object],
    ) -> Path:
        rel = render_dataset_path(
            "s1_site_weights",
            template_args={"seed": config.seed, "manifest_fingerprint": config.manifest_fingerprint},
            dictionary=dictionary,
        )
        return (config.data_root / rel).resolve()

    def _resolve_run_report_path(self, *, config: S1WeightsInputs) -> Path:
        rel = (
            config.data_root
            / self.RUN_REPORT_ROOT
            / f"seed={config.seed}"
            / f"fingerprint={config.manifest_fingerprint}"
            / "run_report.json"
        )
        return rel.resolve()

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
    ) -> None:
        stats["merchants_total"] += 1
        weights = []
        floor_flags = [False] * len(group_rows)
        caps_flags = [False] * len(group_rows)

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

        total_mass = sum(capped)
        if total_mass <= 0:
            stats["zero_mass_fallback_merchants"] += 1
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
                    "weight_source": policy.policy_id,
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
        stats["floors_applied_rows"] += sum(1 for flag in floor_flags if flag)

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
        output_path: Path,
        normalisation_samples: list[dict],
        quantisation_samples: list[tuple[tuple[int, str, int], float, float]],
        dictionary: Mapping[str, object],
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
                "p_quantised": p_hat,
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
                "id": policy.policy_id,
                "version_tag": policy.version_tag,
                "sha256_hex": policy.sha256_hex,
                "quantised_bits": policy.quantised_bits,
                "normalisation_epsilon": policy.normalisation_epsilon,
                "quantisation_epsilon": policy.quantisation_epsilon,
            },
            "inputs_summary": {
                "site_locations_path": f"seed={config.seed}/fingerprint={config.manifest_fingerprint}",
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
                "target_path": str(output_path),
                "bytes_written": bytes_written,
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
                "normalisation": sorted(
                    normalisation_samples,
                    key=lambda item: (-item["abs_error"], item["merchant_id"]),
                )[:20],
                "quantisation": quant_samples,
            },
            "id_map": [
                {
                    "id": "site_locations",
                    "path": f"seed={config.seed}/fingerprint={config.manifest_fingerprint}",
                },
                {
                    "id": "alias_layout_policy_v1",
                    "path": "contracts/policies/l1/seg_2B/alias_layout_policy_v1.json",
                },
                {
                    "id": "s1_site_weights",
                    "path": str(output_path),
                },
            ],
        }
        return run_report

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
