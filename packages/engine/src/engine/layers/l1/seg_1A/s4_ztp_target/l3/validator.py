"""Validation helpers for the S4 ZTP sampler."""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence

from ...s0_foundations.exceptions import err
from ..contexts import S4DeterministicContext
from ..l0 import constants as c
from ..l1.sampler import A_ZERO_REASON
from ..l2.runner import ZTPFinalRecord

logger = logging.getLogger(__name__)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        records.append(json.loads(raw))
    return records


def _partition_path(
    root: Path,
    stream: str,
    *,
    seed: int,
    parameter_hash: str,
    run_id: str,
) -> Path:
    partition = (
        Path(f"seed={seed}")
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )
    return (
        root
        / "logs"
        / "layer1"
        / "1A"
        / "rng"
        / "events"
        / stream
        / partition
        / "part-00000.jsonl"
    )


def _trace_path(root: Path, *, seed: int, parameter_hash: str, run_id: str) -> Path:
    partition = (
        Path(f"seed={seed}")
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )
    return (
        root
        / "logs"
        / "layer1"
        / "1A"
        / "rng"
        / "trace"
        / partition
        / "rng_trace_log.jsonl"
    )


def _group_attempts(records: Iterable[dict]) -> MutableMapping[int, list[dict]]:
    grouped: MutableMapping[int, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("module") != c.MODULE_NAME or record.get("context") != c.CONTEXT:
            continue
        merchant_id = int(record["merchant_id"])
        grouped[merchant_id].append(record)
    return grouped


def _group_events(records: Iterable[dict], *, expect_single: bool = False) -> MutableMapping[int, list[dict]]:
    grouped: MutableMapping[int, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("module") != c.MODULE_NAME or record.get("context") != c.CONTEXT:
            continue
        merchant_id = int(record["merchant_id"])
        grouped[merchant_id].append(record)
    if expect_single:
        for merchant_id, rows in grouped.items():
            if len(rows) > 1:
                raise err(
                    "ERR_S4_NUMERIC_INVALID",
                    f"multiple terminal records found for merchant {merchant_id}",
                )
    return grouped


def _merchant_lookup(context: S4DeterministicContext) -> Dict[int, S4MerchantTarget]:
    lookup: Dict[int, S4MerchantTarget] = {}
    for merchant in context.merchants:
        lookup[merchant.merchant_id] = merchant
    return lookup


def validate_s4_run(
    *,
    base_path: Path,
    deterministic: S4DeterministicContext,
    expected_outcomes: Sequence[ZTPFinalRecord] | None = None,
    output_dir: Path | None = None,
) -> Dict[str, float]:
    """Replay the S4 sampler to confirm envelope and payload integrity."""

    base_path = base_path.expanduser().resolve()
    attempts_path = _partition_path(
        base_path,
        c.STREAM_POISSON_COMPONENT,
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )
    rejection_path = _partition_path(
        base_path,
        c.STREAM_ZTP_REJECTION,
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )
    retry_path = _partition_path(
        base_path,
        c.STREAM_ZTP_RETRY_EXHAUSTED,
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )
    final_path = _partition_path(
        base_path,
        c.STREAM_ZTP_FINAL,
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )
    trace_path = _trace_path(
        base_path,
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )

    attempt_records = _group_attempts(_load_jsonl(attempts_path))
    rejection_records = _group_events(_load_jsonl(rejection_path))
    retry_records = _group_events(_load_jsonl(retry_path), expect_single=True)
    final_records = _group_events(_load_jsonl(final_path), expect_single=True)

    if not trace_path.exists():
        raise err("ERR_S4_NUMERIC_INVALID", f"S4 RNG trace log missing at '{trace_path}'")

    context_lookup = _merchant_lookup(deterministic)
    expected_map = {
        record.merchant_id: record for record in expected_outcomes or ()
    }

    merchant_metrics: list[tuple[int, int, int]] = []
    accept_count = 0
    downgrade_count = 0
    abort_count = 0
    short_circuit_count = 0

    # Ensure no stray merchants in logs.
    logged_merchants = (
        set(attempt_records.keys())
        | set(rejection_records.keys())
        | set(retry_records.keys())
        | set(final_records.keys())
    )
    unknown_merchants = logged_merchants - set(context_lookup.keys())
    if unknown_merchants:
        raise err(
            "ERR_S4_BRANCH_PURITY",
            f"logs contain merchants outside deterministic context: {sorted(unknown_merchants)}",
        )

    for merchant in deterministic.merchants:
        merchant_id = merchant.merchant_id
        attempts = sorted(
            attempt_records.get(merchant_id, []),
            key=lambda rec: int(rec["attempt"]),
        )
        rejections = rejection_records.get(merchant_id, [])
        retry = retry_records.get(merchant_id, [])
        final = final_records.get(merchant_id, [])
        final_record = final[0] if final else None
        retry_record = retry[0] if retry else None

        if not merchant.is_multi or not merchant.is_eligible:
            if attempts or rejections or final_record or retry_record:
                raise err(
                    "ERR_S4_BRANCH_PURITY",
                    f"merchant {merchant_id} is out of scope but has S4 events",
                )
            continue

        attempt_count = len(attempts)
        rejection_count = len(rejections)
        if attempts:
            expected_indices = list(range(1, attempt_count + 1))
            actual_indices = [int(rec["attempt"]) for rec in attempts]
            if actual_indices != expected_indices:
                raise err(
                    "ERR_S4_NUMERIC_INVALID",
                    f"merchant {merchant_id} attempt indices {actual_indices} are not contiguous starting at 1",
                )
        if rejection_count not in (0, max(0, attempt_count - 1)):
            raise err(
                "ERR_S4_NUMERIC_INVALID",
                f"merchant {merchant_id} rejection count {rejection_count} inconsistent with attempts {attempt_count}",
            )

        if final_record and retry_record:
            raise err(
                "ERR_S4_NUMERIC_INVALID",
                f"merchant {merchant_id} has both final and retry_exhausted records",
            )

        admissible = merchant.admissible_foreign_count
        policy = deterministic.hyperparams.exhaustion_policy

        if final_record:
            k_target = int(final_record.get("K_target", 0))
            attempts_reported = int(final_record.get("attempts", 0))
            exhausted_flag = bool(final_record.get("exhausted", False))
            reason = final_record.get("reason")

            if attempts_reported != attempt_count:
                raise err(
                    "ERR_S4_NUMERIC_INVALID",
                    f"merchant {merchant_id} final attempts {attempts_reported} "
                    f"mismatch recorded attempts {attempt_count}",
                )
            if attempt_count and rejection_count != attempt_count - 1 and k_target > 0:
                raise err(
                    "ERR_S4_NUMERIC_INVALID",
                    f"merchant {merchant_id} rejection tally inconsistent with accepted target",
                )

            if admissible == 0:
                if k_target != 0 or attempts_reported != 0 or reason != A_ZERO_REASON:
                    raise err(
                        "ERR_S4_NUMERIC_INVALID",
                        f"merchant {merchant_id} short-circuit should emit K_target=0, attempts=0, reason={A_ZERO_REASON!r}",
                    )
                short_circuit_count += 1
            elif exhausted_flag:
                if k_target != 0 or attempts_reported != deterministic.hyperparams.max_zero_attempts:
                    raise err(
                        "ERR_S4_NUMERIC_INVALID",
                        f"merchant {merchant_id} downgrade final inconsistent with exhaustion semantics",
                    )
                downgrade_count += 1
            else:
                if k_target <= 0:
                    raise err(
                        "ERR_S4_NUMERIC_INVALID",
                        f"merchant {merchant_id} final K_target must be positive for acceptance",
                    )
                accept_count += 1

            expected = expected_map.get(merchant_id)
            if expected is not None:
                if expected.k_target != k_target or expected.attempts != attempts_reported:
                    raise err(
                        "ERR_S4_NUMERIC_INVALID",
                        f"merchant {merchant_id} final mismatch with runner outcome",
                    )
        elif retry_record:
            attempts_reported = int(retry_record.get("attempts", 0))
            aborted_flag = bool(retry_record.get("aborted", False))
            if not aborted_flag or attempts_reported != deterministic.hyperparams.max_zero_attempts:
                raise err(
                    "ERR_S4_NUMERIC_INVALID",
                    f"merchant {merchant_id} retry_exhausted inconsistent with cap policy",
                )
            if policy != "abort":
                raise err(
                    "ERR_S4_NUMERIC_INVALID",
                    f"merchant {merchant_id} retried despite policy={policy}",
                )
            if expected_map.get(merchant_id) is not None:
                raise err(
                    "ERR_S4_NUMERIC_INVALID",
                    f"merchant {merchant_id} aborted but runner reported final outcome",
                )
            abort_count += 1
        else:
            raise err(
                "ERR_S4_NUMERIC_INVALID",
                f"merchant {merchant_id} missing terminal record (final or retry_exhausted)",
            )

        merchant_metrics.append((merchant_id, attempt_count, rejection_count))

    if expected_map:
        missing = set(expected_map.keys()) - {
            merchant.merchant_id for merchant in deterministic.merchants
            if merchant.is_multi and merchant.is_eligible
        }
        if missing:
            raise err(
                "ERR_S4_NUMERIC_INVALID",
                f"runner reported finals for merchants outside deterministic context: {sorted(missing)}",
            )

    if not merchant_metrics:
        raise err("ERR_S4_NUMERIC_INVALID", "no merchants processed by S4 validator")

    total_attempts = sum(metrics[1] for metrics in merchant_metrics)
    total_rejections = sum(metrics[2] for metrics in merchant_metrics)
    merchant_count = len(merchant_metrics)
    attempt_mean = total_attempts / merchant_count
    attempts_sorted = sorted(metric[1] for metric in merchant_metrics)
    p95_index = max(0, min(len(attempts_sorted) - 1, math.ceil(0.95 * merchant_count) - 1))
    p99_index = max(0, min(len(attempts_sorted) - 1, math.ceil(0.99 * merchant_count) - 1))
    metrics = {
        "merchant_count": float(merchant_count),
        "accept_count": float(accept_count),
        "downgrade_count": float(downgrade_count),
        "abort_count": float(abort_count),
        "short_circuit_count": float(short_circuit_count),
        "total_attempts": float(total_attempts),
        "total_rejections": float(total_rejections),
        "mean_attempts": float(attempt_mean),
        "p95_attempts": float(attempts_sorted[p95_index]),
        "p99_attempts": float(attempts_sorted[p99_index]),
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    logger.info(
        "S4 validator: merchants=%d accept=%d downgrade=%d abort=%d short_circuit=%d mean_attempts=%.2f",
        merchant_count,
        accept_count,
        downgrade_count,
        abort_count,
        short_circuit_count,
        attempt_mean,
    )
    return metrics


__all__ = ["validate_s4_run"]
