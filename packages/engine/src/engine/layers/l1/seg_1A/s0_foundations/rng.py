"""RNG logging helpers for Segment 1A S0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from engine.core.time import utc_now_rfc3339_micro


@dataclass
class RngTraceTotals:
    draws_total: int = 0
    blocks_total: int = 0
    events_total: int = 0


@dataclass
class RngTraceAccumulator:
    totals: Dict[Tuple[str, str], RngTraceTotals] = field(default_factory=dict)

    def append_event(self, event: dict) -> dict:
        key = (event["module"], event["substream_label"])
        totals = self.totals.setdefault(key, RngTraceTotals())
        totals.draws_total += int(event["draws"])
        totals.blocks_total += int(event["blocks"])
        totals.events_total += 1
        return {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": event["run_id"],
            "seed": event["seed"],
            "module": event["module"],
            "substream_label": event["substream_label"],
            "rng_counter_before_lo": event["rng_counter_before_lo"],
            "rng_counter_before_hi": event["rng_counter_before_hi"],
            "rng_counter_after_lo": event["rng_counter_after_lo"],
            "rng_counter_after_hi": event["rng_counter_after_hi"],
            "draws_total": totals.draws_total,
            "blocks_total": totals.blocks_total,
            "events_total": totals.events_total,
        }


def build_anchor_event(
    seed: int, parameter_hash: str, manifest_fingerprint: str, run_id: str
) -> dict:
    return {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id,
        "seed": seed,
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "module": "1A.s0",
        "substream_label": "s0.anchor",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 0,
        "rng_counter_after_hi": 0,
        "blocks": 0,
        "draws": "0",
    }
