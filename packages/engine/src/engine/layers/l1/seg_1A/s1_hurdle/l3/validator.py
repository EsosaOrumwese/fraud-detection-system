"""Validation helpers for the S1 hurdle event stream."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterable, Sequence

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxEngine
from ..l1.probability import hurdle_probability
from ..l1.rng import (
    HURDLE_MODULE_NAME,
    HURDLE_SUBSTREAM_LABEL,
    counters,
    derive_hurdle_substream,
)
from ..l2.runner import HurdleDesignRow


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise err("E_DATASET_NOT_FOUND", f"expected JSONL dataset '{path}' missing")
    records: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        records.append(json.loads(raw))
    return records


def validate_hurdle_run(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    run_id: str,
    beta: Sequence[float],
    design_rows: Iterable[HurdleDesignRow],
) -> None:
    design_map: Dict[int, HurdleDesignRow] = {}
    for row in design_rows:
        if row.merchant_id in design_map:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"duplicate design row for merchant {row.merchant_id}",
            )
        design_map[row.merchant_id] = row

    if not design_map:
        raise err("E_DATASET_EMPTY", "no hurdle design rows supplied for validation")

    events_path = (
        base_path
        / "logs"
        / "layer1"
        / "1A"
        / "rng"
        / "events"
        / HURDLE_SUBSTREAM_LABEL
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
        / "part-00000.jsonl"
    )
    trace_path = (
        base_path
        / "logs"
        / "layer1"
        / "1A"
        / "rng"
        / "trace"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
        / "rng_trace_log.jsonl"
    )

    events = _load_jsonl(events_path)
    if not events:
        raise err("E_DATASET_EMPTY", "hurdle event stream produced no rows")

    engine = PhiloxEngine(seed=seed, manifest_fingerprint=manifest_fingerprint)

    seen_merchants: Dict[int, dict] = {}
    total_draws = 0
    total_blocks = 0

    for record in events:
        if record.get("module") != HURDLE_MODULE_NAME:
            raise err("E_VALIDATION_MISMATCH", f"unexpected module '{record.get('module')}'")
        if record.get("substream_label") != HURDLE_SUBSTREAM_LABEL:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"unexpected substream label '{record.get('substream_label')}'",
            )
        if record.get("run_id") != run_id or record.get("seed") != seed:
            raise err("E_VALIDATION_MISMATCH", "run_id or seed mismatch in event record")
        if record.get("parameter_hash") != parameter_hash:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"parameter_hash mismatch '{record.get('parameter_hash')}'",
            )
        if record.get("manifest_fingerprint") != manifest_fingerprint:
            raise err(
                "E_VALIDATION_MISMATCH",
                "manifest_fingerprint mismatch in event record",
            )

        merchant_id = int(record["merchant_id"])
        design_row = design_map.get(merchant_id)
        if design_row is None:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"hurdle event emitted for unknown merchant {merchant_id}",
            )
        if merchant_id in seen_merchants:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"duplicate hurdle event for merchant {merchant_id}",
            )

        draws = int(record["draws"])
        blocks = int(record["blocks"])
        deterministic = bool(record["deterministic"])
        is_multi = bool(record["is_multi"])
        u_value = record.get("u")

        probability = hurdle_probability(
            coefficients=beta,
            design_vector=design_row.design_vector,
        )
        if not math.isclose(probability.pi, float(record["pi"]), rel_tol=0.0, abs_tol=1e-12):
            raise err(
                "E_VALIDATION_MISMATCH",
                f"pi mismatch for merchant {merchant_id} "
                f"(expected {probability.pi}, observed {record['pi']})",
            )
        if not math.isclose(probability.eta, float(record["eta"]), rel_tol=0.0, abs_tol=1e-12):
            raise err(
                "E_VALIDATION_MISMATCH",
                f"eta mismatch for merchant {merchant_id} "
                f"(expected {probability.eta}, observed {record['eta']})",
            )
        if probability.deterministic != deterministic:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"deterministic flag mismatch for merchant {merchant_id}",
            )

        substream = derive_hurdle_substream(engine, merchant_id=merchant_id)
        before_state = substream.snapshot()
        if counters(before_state) != (
            int(record["rng_counter_before_hi"]),
            int(record["rng_counter_before_lo"]),
        ):
            raise err(
                "E_RNG_COUNTER",
                f"counter_before mismatch for merchant {merchant_id}",
            )

        blocks_before = substream.blocks
        draws_before = substream.draws

        if draws == 1:
            if deterministic:
                raise err(
                    "E_RNG_BUDGET",
                    f"deterministic row consumed a draw for merchant {merchant_id}",
                )
            regenerated = substream.uniform()
            if not (0.0 < regenerated < 1.0):
                raise err(
                    "E_RNG_BUDGET",
                    f"regenerated uniform out of bounds for merchant {merchant_id}",
                )
            if u_value is None or not math.isclose(
                regenerated, float(u_value), rel_tol=0.0, abs_tol=1e-15
            ):
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"uniform mismatch for merchant {merchant_id}",
                )
            expected_multi = regenerated < probability.pi
        else:
            if not deterministic:
                raise err(
                    "E_RNG_BUDGET",
                    f"stochastic row failed to consume uniform for merchant {merchant_id}",
                )
            if u_value is not None:
                raise err(
                    "E_RNG_BUDGET",
                    f"deterministic row recorded uniform for merchant {merchant_id}",
                )
            expected_multi = probability.pi == 1.0

        after_state = substream.snapshot()
        blocks_observed = substream.blocks - blocks_before
        draws_observed = substream.draws - draws_before
        if blocks_observed != blocks or draws_observed != draws:
            raise err(
                "E_RNG_COUNTER",
                f"draw/block mismatch for merchant {merchant_id} "
                f"(expected blocks={blocks}, draws={draws}; "
                f"observed blocks={blocks_observed}, draws={draws_observed})",
            )
        if counters(after_state) != (
            int(record["rng_counter_after_hi"]),
            int(record["rng_counter_after_lo"]),
        ):
            raise err(
                "E_RNG_COUNTER",
                f"counter_after mismatch for merchant {merchant_id}",
            )
        if expected_multi != is_multi:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"is_multi mismatch for merchant {merchant_id}",
            )

        seen_merchants[merchant_id] = record
        total_draws += draws
        total_blocks += blocks

    if len(seen_merchants) != len(design_map):
        missing = set(design_map.keys()) - set(seen_merchants.keys())
        raise err(
            "E_VALIDATION_MISMATCH",
            f"hurdle stream missing merchants {sorted(missing)}",
        )

    trace_records = _load_jsonl(trace_path)
    if not trace_records:
        raise err("E_DATASET_EMPTY", "rng trace log produced no rows")
    final_trace = trace_records[-1]
    if final_trace.get("module") != HURDLE_MODULE_NAME or final_trace.get("substream_label") != HURDLE_SUBSTREAM_LABEL:
        raise err("E_VALIDATION_MISMATCH", "trace log module/substream mismatch")
    if final_trace.get("run_id") != run_id or final_trace.get("seed") != seed:
        raise err("E_VALIDATION_MISMATCH", "trace log run_id/seed mismatch")
    if int(final_trace.get("draws_total", -1)) != total_draws:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"trace draws_total {final_trace.get('draws_total')} expected {total_draws}",
        )
    if int(final_trace.get("blocks_total", -1)) != total_blocks:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"trace blocks_total {final_trace.get('blocks_total')} expected {total_blocks}",
        )
    if int(final_trace.get("events_total", -1)) != len(events):
        raise err(
            "E_VALIDATION_MISMATCH",
            f"trace events_total {final_trace.get('events_total')} expected {len(events)}",
        )


__all__ = ["validate_hurdle_run"]
