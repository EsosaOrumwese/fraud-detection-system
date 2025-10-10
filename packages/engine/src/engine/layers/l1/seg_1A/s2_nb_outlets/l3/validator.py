"""Validation helpers for S2 NB outlet sampling."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxEngine
from ..l1 import rng as nb_rng
from ..l2.deterministic import S2DeterministicContext, S2DeterministicRow
from ..l2.runner import NBFinalRecord


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        records.append(json.loads(raw))
    return records


def _merchant_map(rows: Iterable[S2DeterministicRow]) -> Dict[int, S2DeterministicRow]:
    mapping: Dict[int, S2DeterministicRow] = {}
    for row in rows:
        if row.merchant_id in mapping:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"duplicate deterministic context for merchant {row.merchant_id}",
            )
        mapping[row.merchant_id] = row
    return mapping


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
    return root / "logs" / "rng" / "events" / stream / partition / "part-00000.jsonl"


def _trace_path(root: Path, *, seed: int, parameter_hash: str, run_id: str) -> Path:
    partition = (
        Path(f"seed={seed}")
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )
    return root / "logs" / "rng" / "trace" / partition / "rng_trace_log.jsonl"


def _counter_pair(record: Mapping[str, object], prefix: str) -> tuple[int, int]:
    return (
        int(record[f"{prefix}_hi"]),
        int(record[f"{prefix}_lo"]),
    )


def _sort_events(records: Iterable[dict]) -> list[dict]:
    return sorted(
        records,
        key=lambda rec: (
            int(rec["rng_counter_before_hi"]),
            int(rec["rng_counter_before_lo"]),
        ),
    )


def validate_nb_run(
    *,
    base_path: Path,
    deterministic: S2DeterministicContext,
    expected_finals: Sequence[NBFinalRecord] | None = None,
) -> None:
    """Replay the NB sampler to confirm envelope, RNG, and payload integrity."""

    root = base_path.expanduser().resolve()
    gamma_path = _partition_path(
        root,
        "gamma_component",
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )
    poisson_path = _partition_path(
        root,
        "poisson_component",
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )
    final_path = _partition_path(
        root,
        "nb_final",
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )

    gamma_records = _load_jsonl(gamma_path)
    poisson_records = _load_jsonl(poisson_path)
    final_records = _load_jsonl(final_path)

    expected_merchants = {row.merchant_id for row in deterministic.rows}
    if not expected_merchants:
        # No multi-site merchants => no RNG events expected.
        if gamma_records or poisson_records or final_records:
            raise err(
                "E_VALIDATION_MISMATCH",
                "S2 emitted RNG events despite having no multi-site merchants",
            )
        return

    if not final_records:
        raise err(
            "E_DATASET_EMPTY",
            f"nb_final dataset missing rows at '{final_path}'",
        )
    if not gamma_records:
        raise err(
            "E_DATASET_EMPTY",
            f"gamma_component dataset missing rows at '{gamma_path}'",
        )
    if not poisson_records:
        raise err(
            "E_DATASET_EMPTY",
            f"poisson_component dataset missing rows at '{poisson_path}'",
        )

    gamma_by_merchant: MutableMapping[int, list[dict]] = defaultdict(list)
    for record in gamma_records:
        merchant_id = int(record.get("merchant_id", -1))
        gamma_by_merchant[merchant_id].append(record)
    for records in gamma_by_merchant.values():
        records.sort(key=lambda rec: (int(rec["rng_counter_before_hi"]), int(rec["rng_counter_before_lo"])))

    poisson_by_merchant: MutableMapping[int, list[dict]] = defaultdict(list)
    for record in poisson_records:
        merchant_id = int(record.get("merchant_id", -1))
        poisson_by_merchant[merchant_id].append(record)
    for records in poisson_by_merchant.values():
        records.sort(key=lambda rec: (int(rec["rng_counter_before_hi"]), int(rec["rng_counter_before_lo"])))

    final_by_merchant: Dict[int, dict] = {}
    for record in final_records:
        merchant_id = int(record.get("merchant_id", -1))
        if merchant_id in final_by_merchant:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"duplicate nb_final event for merchant {merchant_id}",
            )
        final_by_merchant[merchant_id] = record

    observed_merchants = (
        set(gamma_by_merchant.keys())
        | set(poisson_by_merchant.keys())
        | set(final_by_merchant.keys())
    )
    extra_merchants = observed_merchants - expected_merchants
    if extra_merchants:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"unexpected S2 events for merchants {sorted(extra_merchants)}",
        )
    missing_merchants = expected_merchants - set(final_by_merchant.keys())
    if missing_merchants:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"nb_final missing for merchants {sorted(missing_merchants)}",
        )

    deterministic_map = _merchant_map(deterministic.rows)
    expected_map = (
        {record.merchant_id: record for record in expected_finals}
        if expected_finals is not None
        else {}
    )

    engine = PhiloxEngine(
        seed=deterministic.seed,
        manifest_fingerprint=deterministic.manifest_fingerprint,
    )

    for merchant_id in sorted(expected_merchants):
        deterministic_row = deterministic_map[merchant_id]
        gamma_events = gamma_by_merchant.get(merchant_id, [])
        poisson_events = poisson_by_merchant.get(merchant_id, [])
        final_event = final_by_merchant[merchant_id]

        if final_event.get("module") != nb_rng.FINAL_MODULE_NAME:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"nb_final module mismatch for merchant {merchant_id}",
            )
        if final_event.get("substream_label") != nb_rng.FINAL_SUBSTREAM_LABEL:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"nb_final substream mismatch for merchant {merchant_id}",
            )
        if int(final_event.get("blocks", -1)) != 0 or int(final_event.get("draws", "0")) != 0:
            raise err(
                "E_RNG_COUNTER",
                f"nb_final must be non-consuming for merchant {merchant_id}",
            )

        mu_recorded = float(final_event["mu"])
        phi_recorded = float(final_event["dispersion_k"])
        if not math.isclose(mu_recorded, deterministic_row.links.mu, rel_tol=0.0, abs_tol=1e-15):
            raise err(
                "E_VALIDATION_MISMATCH",
                f"nb_final.mu mismatch for merchant {merchant_id}",
            )
        if not math.isclose(phi_recorded, deterministic_row.links.phi, rel_tol=0.0, abs_tol=1e-15):
            raise err(
                "E_VALIDATION_MISMATCH",
                f"nb_final.dispersion_k mismatch for merchant {merchant_id}",
            )

        nb_rejections = int(final_event["nb_rejections"])
        n_outlets = int(final_event["n_outlets"])
        if n_outlets < 2:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"nb_final.n_outlets must be >= 2 for merchant {merchant_id}",
            )

        expected_attempts = nb_rejections + 1
        if len(gamma_events) != expected_attempts or len(poisson_events) != expected_attempts:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"attempt count mismatch for merchant {merchant_id}",
            )

        gamma_substream = nb_rng.derive_gamma_substream(engine, merchant_id=merchant_id)
        poisson_substream = nb_rng.derive_poisson_substream(engine, merchant_id=merchant_id)

        observed_rejections = 0
        accepted_attempt = None

        for attempt_index, (gamma_event, poisson_event) in enumerate(
            zip(gamma_events, poisson_events), start=1
        ):
            if gamma_event.get("module") != nb_rng.GAMMA_MODULE_NAME:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"gamma_component module mismatch for merchant {merchant_id}",
                )
            if gamma_event.get("substream_label") != nb_rng.GAMMA_SUBSTREAM_LABEL:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"gamma_component substream mismatch for merchant {merchant_id}",
                )
            if gamma_event.get("context") != "nb" or int(gamma_event.get("index", -1)) != 0:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"gamma_component payload mismatch for merchant {merchant_id}",
                )

            if poisson_event.get("module") != nb_rng.POISSON_MODULE_NAME:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"poisson_component module mismatch for merchant {merchant_id}",
                )
            if poisson_event.get("substream_label") != nb_rng.POISSON_SUBSTREAM_LABEL:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"poisson_component substream mismatch for merchant {merchant_id}",
                )
            if poisson_event.get("context") != "nb":
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"poisson_component context mismatch for merchant {merchant_id}",
                )

            if int(poisson_event.get("attempt", -1)) != attempt_index:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"poisson_component attempt mismatch for merchant {merchant_id}",
                )

            gamma_before = gamma_substream.snapshot()
            gamma_blocks_before = gamma_substream.blocks
            gamma_draws_before = gamma_substream.draws
            gamma_value = gamma_substream.gamma(deterministic_row.links.phi)
            gamma_after = gamma_substream.snapshot()
            gamma_blocks_used = gamma_substream.blocks - gamma_blocks_before
            gamma_draws_used = gamma_substream.draws - gamma_draws_before

            if nb_rng.counters(gamma_before) != _counter_pair(gamma_event, "rng_counter_before"):
                raise err(
                    "E_RNG_COUNTER",
                    f"gamma_component counter_before mismatch for merchant {merchant_id}",
                )
            if nb_rng.counters(gamma_after) != _counter_pair(gamma_event, "rng_counter_after"):
                raise err(
                    "E_RNG_COUNTER",
                    f"gamma_component counter_after mismatch for merchant {merchant_id}",
                )
            if gamma_blocks_used != int(gamma_event["blocks"]):
                raise err(
                    "E_RNG_COUNTER",
                    f"gamma_component blocks mismatch for merchant {merchant_id}",
                )
            if gamma_draws_used != int(gamma_event["draws"]):
                raise err(
                    "E_RNG_COUNTER",
                    f"gamma_component draws mismatch for merchant {merchant_id}",
                )
            if not math.isclose(float(gamma_event["gamma_value"]), gamma_value, rel_tol=0.0, abs_tol=1e-15):
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"gamma_component gamma_value mismatch for merchant {merchant_id}",
                )

            lam = (deterministic_row.links.mu / deterministic_row.links.phi) * gamma_value
            recorded_lambda = float(poisson_event["lambda"])
            if not math.isfinite(recorded_lambda) or recorded_lambda <= 0.0:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"poisson_component lambda invalid for merchant {merchant_id}",
                )
            if not math.isclose(recorded_lambda, lam, rel_tol=0.0, abs_tol=1e-12):
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"poisson_component lambda mismatch for merchant {merchant_id}",
                )

            poisson_before = poisson_substream.snapshot()
            poisson_blocks_before = poisson_substream.blocks
            poisson_draws_before = poisson_substream.draws
            k_value = poisson_substream.poisson(lam)
            poisson_after = poisson_substream.snapshot()
            poisson_blocks_used = poisson_substream.blocks - poisson_blocks_before
            poisson_draws_used = poisson_substream.draws - poisson_draws_before

            if nb_rng.counters(poisson_before) != _counter_pair(poisson_event, "rng_counter_before"):
                raise err(
                    "E_RNG_COUNTER",
                    f"poisson_component counter_before mismatch for merchant {merchant_id}",
                )
            if nb_rng.counters(poisson_after) != _counter_pair(poisson_event, "rng_counter_after"):
                raise err(
                    "E_RNG_COUNTER",
                    f"poisson_component counter_after mismatch for merchant {merchant_id}",
                )
            if poisson_blocks_used != int(poisson_event["blocks"]):
                raise err(
                    "E_RNG_COUNTER",
                    f"poisson_component blocks mismatch for merchant {merchant_id}",
                )
            if poisson_draws_used != int(poisson_event["draws"]):
                raise err(
                    "E_RNG_COUNTER",
                    f"poisson_component draws mismatch for merchant {merchant_id}",
                )
            if int(poisson_event["k"]) != k_value:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"poisson_component k mismatch for merchant {merchant_id}",
                )

            if k_value >= 2:
                accepted_attempt = attempt_index
                if k_value != n_outlets:
                    raise err(
                        "E_VALIDATION_MISMATCH",
                        f"nb_final.n_outlets mismatch for merchant {merchant_id}",
                    )
            else:
                observed_rejections += 1

        if accepted_attempt is None:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"no acceptance recorded for merchant {merchant_id}",
            )
        if accepted_attempt != expected_attempts:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"acceptance attempt index mismatch for merchant {merchant_id}",
            )
        if observed_rejections != nb_rejections:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"rejection count mismatch for merchant {merchant_id}",
            )

        if expected_map:
            expected_record = expected_map.get(merchant_id)
            if expected_record is None:
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"missing expected final record for merchant {merchant_id}",
                )
            if (
                expected_record.n_outlets != n_outlets
                or expected_record.nb_rejections != nb_rejections
            ):
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"expected final mismatch for merchant {merchant_id}",
                )

    if expected_map and set(expected_map.keys()) != set(final_by_merchant.keys()):
        missing = set(expected_map.keys()) - set(final_by_merchant.keys())
        raise err(
            "E_VALIDATION_MISMATCH",
            f"expected finals not found for merchants {sorted(missing)}",
        )

    trace_path = _trace_path(
        root,
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
    )
    if not trace_path.exists():
        raise err(
            "E_DATASET_NOT_FOUND",
            f"S2 RNG trace log missing at '{trace_path}'",
        )


__all__ = ["validate_nb_run"]
