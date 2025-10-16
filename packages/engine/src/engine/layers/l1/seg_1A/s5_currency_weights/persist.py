"""Persistence utilities for S5 outputs."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, List

import pandas as pd

from .builder import CurrencyResult
from .contexts import S5PolicyMetadata
from .merchant_currency import MerchantCurrencyRecord

PARTITION_FILENAME = "part-00000.parquet"

__all__ = [
    "PARTITION_FILENAME",
    "PersistConfig",
    "write_ccy_country_weights",
    "write_sparse_flag",
    "build_receipt_payload",
    "write_validation_receipt",
    "write_merchant_currency",
]


@dataclass
class PersistConfig:
    parameter_hash: str
    output_dir: Path
    emit_validation: bool = False
    emit_sparse_flag: bool = False


def write_ccy_country_weights(
    results: Iterable[CurrencyResult],
    config: PersistConfig,
) -> Path:
    """Persist the currency→country weights cache to parquet."""

    result_list = list(results)

    records: List[dict] = []
    for result in result_list:
        for row in result.weights:
            records.append(
                {
                    "parameter_hash": config.parameter_hash,
                    "currency": row.currency,
                    "country_iso": row.country_iso,
                    "weight": row.weight,
                    "obs_count": result.obs_count,
                }
            )

    df = pd.DataFrame.from_records(
        records,
        columns=["parameter_hash", "currency", "country_iso", "weight", "obs_count"],
    )
    df = df.sort_values(["currency", "country_iso"]).reset_index(drop=True)

    target_dir = (
        config.output_dir
        / "ccy_country_weights_cache"
        / f"parameter_hash={config.parameter_hash}"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / PARTITION_FILENAME
    df.to_parquet(path, index=False)

    if config.emit_sparse_flag:
        write_sparse_flag(result_list, config)

    return path


def write_merchant_currency(
    records: Iterable[MerchantCurrencyRecord],
    config: PersistConfig,
) -> Path:
    """Persist the merchant_currency cache."""

    rows = list(records)
    frame = pd.DataFrame.from_records(
        (
            {
                "parameter_hash": config.parameter_hash,
                "merchant_id": row.merchant_id,
                "kappa": row.kappa,
                "source": row.source,
                "tie_break_used": bool(row.tie_break_used),
            }
            for row in rows
        ),
        columns=["parameter_hash", "merchant_id", "kappa", "source", "tie_break_used"],
    )
    frame = frame.sort_values(["merchant_id"]).reset_index(drop=True)

    target_dir = (
        config.output_dir
        / "merchant_currency"
        / f"parameter_hash={config.parameter_hash}"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / PARTITION_FILENAME
    frame.to_parquet(path, index=False)
    return path


def write_sparse_flag(
    results: Iterable[CurrencyResult],
    config: PersistConfig,
) -> Path:
    """Persist the optional sparse_flag dataset."""

    records = []
    for result in results:
        records.append(
            {
                "parameter_hash": config.parameter_hash,
                "currency": result.currency,
                "is_sparse": bool(result.is_sparse),
                "obs_count": result.obs_count,
                "threshold": result.sparse_threshold,
            }
        )

    df = pd.DataFrame.from_records(
        records,
        columns=["parameter_hash", "currency", "is_sparse", "obs_count", "threshold"],
    )
    df = df.sort_values(["currency"]).reset_index(drop=True)

    target_dir = (
        config.output_dir
        / "sparse_flag"
        / f"parameter_hash={config.parameter_hash}"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / PARTITION_FILENAME
    df.to_parquet(path, index=False)
    return path


def build_receipt_payload(
    *,
    results: Sequence[CurrencyResult],
    parameter_hash: str,
    policy_metadata: S5PolicyMetadata,
    schema_refs: Mapping[str, str],
    rng_before: Mapping[str, int] | None = None,
    rng_after: Mapping[str, int] | None = None,
    currencies_total_inputs: int | None = None,
) -> dict:
    """Construct the spec-compliant S5 receipt payload."""

    rng_before = rng_before or {}
    rng_after = rng_after or {}

    currencies_processed = len(results)
    currency_codes = [result.currency for result in results]
    currencies_total = currencies_total_inputs if currencies_total_inputs is not None else len(set(currency_codes))
    rows_written = sum(len(result.weights) for result in results)

    sum_numeric_pass = sum(1 for result in results if result.sum_numeric_ok)
    sum_decimal_pass = sum(1 for result in results if result.sum_decimal_ok)
    ulp_values = [result.largest_remainder_ulps for result in results]
    largest_remainder_total_ulps = sum(ulp_values)
    overrides_applied_count = sum(result.overrides_total for result in results)
    floors_triggered_count = sum(result.floors_triggered for result in results)

    degrade_counter: Dict[str, int] = {
        "none": 0,
        "settlement_only": 0,
        "ccy_only": 0,
    }
    degraded_currencies: list[Mapping[str, object]] = []
    for result in results:
        mode = result.degrade_mode
        degrade_counter.setdefault(mode, 0)
        degrade_counter[mode] += 1
        if mode != "none":
            degraded_currencies.append(
                {
                    "currency": result.currency,
                    "mode": mode,
                    "reason_code": result.degrade_reason,
                }
            )

    coverage_union_pass = sum(
        1 for result in results if result.countries_output_count == result.countries_union_count
    )
    policy_narrowed_currencies = sorted(
        result.currency for result in results if result.policy_narrowed
    )
    coverage_policy_narrowed = len(policy_narrowed_currencies)

    rng_events_before = int(rng_before.get("events_total", 0))
    rng_events_after = int(rng_after.get("events_total", 0))
    rng_draws_before = int(rng_before.get("draws_total", 0))
    rng_draws_after = int(rng_after.get("draws_total", 0))

    degrade_mode_counts = {
        "none": int(degrade_counter.get("none", 0)),
        "settlement_only": int(degrade_counter.get("settlement_only", 0)),
        "ccy_only": int(degrade_counter.get("ccy_only", 0)),
    }

    payload = {
        "parameter_hash": parameter_hash,
        "policy_digest": policy_metadata.digest_hex,
        "producer": "1A.expand_currency_to_country",
        "schema_refs": dict(schema_refs),
        "currencies_total": currencies_total,
        "currencies_processed": currencies_processed,
        "rows_written": rows_written,
        "sum_numeric_pass": sum_numeric_pass,
        "sum_decimal_dp_pass": sum_decimal_pass,
        "largest_remainder_total_ulps": largest_remainder_total_ulps,
        "largest_remainder_ulps_quantiles": _quantile_summary(ulp_values),
        "overrides_applied_count": overrides_applied_count,
        "floors_triggered_count": floors_triggered_count,
        "degrade_mode_counts": degrade_mode_counts,
        "coverage_union_pass": coverage_union_pass,
        "coverage_policy_narrowed": coverage_policy_narrowed,
        "policy_narrowed_currencies": policy_narrowed_currencies,
        "degraded_currencies": degraded_currencies,
        "rng_trace_delta_events": rng_events_after - rng_events_before,
        "rng_trace_delta_draws": rng_draws_after - rng_draws_before,
        "generated_at": _utc_timestamp(),
    }

    payload["by_currency"] = [
        _currency_payload(result, parameter_hash, policy_metadata)
        for result in results
    ]
    payload["currencies"] = payload["by_currency"]

    return payload


def _currency_payload(
    result: CurrencyResult,
    parameter_hash: str,
    policy_metadata: S5PolicyMetadata,
) -> Mapping[str, object]:
    record: Dict[str, object] = {
        "currency": result.currency,
        "parameter_hash": parameter_hash,
        "policy_digest": policy_metadata.digest_hex,
        "countries_union_count": result.countries_union_count,
        "countries_output_count": result.countries_output_count,
        "policy_narrowed": result.policy_narrowed,
        "sum_numeric_ok": result.sum_numeric_ok,
        "sum_decimal_dp_ok": result.sum_decimal_ok,
        "largest_remainder_ulps": result.largest_remainder_ulps,
        "overrides_applied": {
            "alpha_iso": result.alpha_override_count,
            "min_share_iso": result.min_share_override_count,
            "per_currency": 1 if result.per_currency_override else 0,
        },
        "floors_triggered": result.floors_triggered,
        "degrade_mode": result.degrade_mode,
        "degrade_reason_code": result.degrade_reason,
        "N0": result.n0,
        "N_eff": result.n_eff,
        "dp": result.dp,
        "blend_weight": result.blend_weight,
        "obs_count": result.obs_count,
        "is_sparse": result.is_sparse,
        "sparse_threshold": result.sparse_threshold,
        "probability_sum": sum(result.probabilities.values()),
        "quantised_sum": sum(result.quantised.values()),
    }
    if result.policy_narrowed:
        record["narrowed_isos"] = list(result.narrowed_isos)
    return record


def _quantile_summary(values: Sequence[int]) -> Mapping[str, int]:
    if not values:
        return {"p50": 0, "p95": 0, "p99": 0}
    sorted_vals = sorted(values)
    return {
        "p50": _quantile(sorted_vals, 0.50),
        "p95": _quantile(sorted_vals, 0.95),
        "p99": _quantile(sorted_vals, 0.99),
    }


def _quantile(values: Sequence[int], q: float) -> int:
    if not values:
        return 0
    idx = max(0, min(len(values) - 1, math.ceil(q * len(values)) - 1))
    return int(values[idx])


def _utc_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def write_validation_receipt(
    *,
    payload: Mapping[str, object],
    config: PersistConfig,
    target_dir: Path | None = None,
) -> Path:
    """Write the S5 validation receipt alongside the weights cache."""

    dest_dir = (
        target_dir
        if target_dir is not None
        else config.output_dir
        / "ccy_country_weights_cache"
        / f"parameter_hash={config.parameter_hash}"
    )
    dest_dir.mkdir(parents=True, exist_ok=True)

    receipt_path = dest_dir / "S5_VALIDATION.json"
    receipt_text = json.dumps(payload, indent=2, sort_keys=True)
    receipt_path.write_text(receipt_text, encoding="utf-8")

    digest = hashlib.sha256(receipt_text.encode("utf-8")).hexdigest()
    passed_flag = dest_dir / "_passed.flag"
    passed_flag.write_text(f"sha256_hex={digest}\n", encoding="ascii")

    return receipt_path
