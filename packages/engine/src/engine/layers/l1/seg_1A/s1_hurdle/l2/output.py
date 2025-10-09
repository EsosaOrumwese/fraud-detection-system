"""Persistence helpers for S1 hurdle events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxState
from ..l1.rng import HURDLE_MODULE_NAME, HURDLE_SUBSTREAM_LABEL


def _utc_timestamp() -> str:
    """Return an RFC-3339 timestamp with microsecond precision."""

    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


def _append_jsonl(path: Path, record: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")


def _u128_state(state: PhiloxState) -> int:
    return (int(state.counter_hi) << 64) | int(state.counter_lo)


@dataclass
class HurdleEventWriter:
    """Write hurdle Bernoulli events and maintain the cumulative trace."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    module: str = HURDLE_MODULE_NAME
    substream_label: str = HURDLE_SUBSTREAM_LABEL

    def __post_init__(self) -> None:
        events_dir = (
            self.base_path
            / "events"
            / self.substream_label
            / f"seed={self.seed}"
            / f"parameter_hash={self.parameter_hash}"
            / f"run_id={self.run_id}"
        )
        self._events_path = events_dir / "part-00000.jsonl"
        trace_dir = (
            self.base_path
            / "trace"
            / f"seed={self.seed}"
            / f"parameter_hash={self.parameter_hash}"
            / f"run_id={self.run_id}"
        )
        self._trace_path = trace_dir / "rng_trace_log.jsonl"
        self._draws_total = 0
        self._blocks_total = 0
        self._events_total = 0

    @property
    def events_path(self) -> Path:
        return self._events_path

    @property
    def trace_path(self) -> Path:
        return self._trace_path

    def write_event(
        self,
        *,
        merchant_id: int,
        pi: float,
        eta: float,
        deterministic: bool,
        is_multi: bool,
        u_value: Optional[float],
        bucket_id: int,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        draws: int,
        blocks: int,
    ) -> None:
        if draws not in (0, 1):
            raise err("E_RNG_BUDGET", f"draws must be 0 or 1, got {draws}")
        if blocks not in (0, 1):
            raise err("E_RNG_BUDGET", f"blocks must be 0 or 1, got {blocks}")
        if blocks != draws:
            raise err(
                "E_RNG_COUNTER",
                f"counter budget mismatch (blocks={blocks}, draws={draws})",
            )
        if deterministic and u_value is not None:
            raise err("E_RNG_BUDGET", "deterministic hurdle rows must omit 'u'")
        if (not deterministic) and u_value is None:
            raise err("E_RNG_BUDGET", "stochastic hurdle rows require 'u'")

        delta = _u128_state(counter_after) - _u128_state(counter_before)
        if delta != blocks:
            raise err(
                "E_RNG_COUNTER",
                f"counter delta {delta} does not match blocks {blocks}",
            )

        ts_utc = _utc_timestamp()
        event_record = {
            "ts_utc": ts_utc,
            "module": self.module,
            "substream_label": self.substream_label,
            "seed": self.seed,
            "run_id": self.run_id,
            "parameter_hash": self.parameter_hash,
            "manifest_fingerprint": self.manifest_fingerprint,
            "rng_counter_before_hi": counter_before.counter_hi,
            "rng_counter_before_lo": counter_before.counter_lo,
            "rng_counter_after_hi": counter_after.counter_hi,
            "rng_counter_after_lo": counter_after.counter_lo,
            "draws": str(draws),
            "blocks": blocks,
            "merchant_id": int(merchant_id),
            "pi": float(pi),
            "eta": float(eta),
            "deterministic": bool(deterministic),
            "is_multi": bool(is_multi),
            "u": u_value,
            "gdp_bucket_id": int(bucket_id),
        }
        _append_jsonl(self._events_path, event_record)

        self._events_total = min(self._events_total + 1, 2**64 - 1)
        self._draws_total = min(self._draws_total + draws, 2**64 - 1)
        self._blocks_total = min(self._blocks_total + blocks, 2**64 - 1)

        trace_record = {
            "ts_utc": ts_utc,
            "module": self.module,
            "substream_label": self.substream_label,
            "seed": self.seed,
            "run_id": self.run_id,
            "rng_counter_before_hi": counter_before.counter_hi,
            "rng_counter_before_lo": counter_before.counter_lo,
            "rng_counter_after_hi": counter_after.counter_hi,
            "rng_counter_after_lo": counter_after.counter_lo,
            "draws_total": self._draws_total,
            "blocks_total": self._blocks_total,
            "events_total": self._events_total,
        }
        _append_jsonl(self._trace_path, trace_record)


__all__ = ["HurdleEventWriter"]
