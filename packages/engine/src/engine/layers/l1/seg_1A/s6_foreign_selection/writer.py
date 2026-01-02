"""Event writer for S6 foreign-set selection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, MutableMapping

from ..s0_foundations.exceptions import err
from ..s0_foundations.l1.rng import PhiloxState
from . import constants as c

U64_MAX = 2**64 - 1


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


def _delta(before: PhiloxState, after: PhiloxState) -> int:
    before_value = (int(before.counter_hi) << 64) | int(before.counter_lo)
    after_value = (int(after.counter_hi) << 64) | int(after.counter_lo)
    if after_value < before_value:
        raise err(
            "E_RNG_COUNTER",
            "Philox counters decreased across event emission",
        )
    return after_value - before_value


def _assert_consuming(*, blocks_used: int, draws_used: int) -> None:
    if blocks_used <= 0 or draws_used <= 0:
        raise err(
            "E_RNG_BUDGET",
            f"consuming event requires positive blocks/draws "
            f"(blocks={blocks_used}, draws={draws_used})",
        )


@dataclass
class GumbelEventWriter:
    """Emit S6 RNG events and maintain the cumulative trace log."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    _trace_totals: MutableMapping[tuple[str, str], Dict[str, int]] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.base_path = self.base_path.expanduser().resolve()
        rng_root = self.base_path / "logs" / "rng"
        self._events_root = rng_root / "events"
        self._trace_root = rng_root / "trace"
        self._trace_totals = {}

    @property
    def events_path(self) -> Path:
        return self._event_path(c.STREAM_GUMBEL_KEY)

    @property
    def trace_path(self) -> Path:
        return self._trace_root / self._partition("rng_trace_log.jsonl")

    def write_gumbel_event(
        self,
        *,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks_used: int,
        draws_used: int,
        merchant_id: int,
        country_iso: str,
        weight: float,
        uniform: float | None,
        key: float | None,
        selected: bool,
        selection_order: int | None,
    ) -> None:
        """Persist a single `rng_event.gumbel_key` row."""

        expected_blocks = _delta(counter_before, counter_after)
        if expected_blocks != blocks_used:
            raise err(
                "E_RNG_COUNTER",
                f"counter delta {expected_blocks} does not match blocks {blocks_used}",
            )
        _assert_consuming(blocks_used=blocks_used, draws_used=draws_used)
        if blocks_used != 1 or draws_used != 1:
            raise err(
                "E_RNG_BUDGET",
                f"gumbel_key must consume exactly 1 block/1 draw (blocks={blocks_used}, draws={draws_used})",
            )
        if selected and selection_order is None:
            raise err("E_RNG_BUDGET", "selected gumbel_key requires selection_order")
        if (not selected) and selection_order is not None:
            raise err("E_RNG_BUDGET", "non-selected gumbel_key must omit selection_order")
        if float(weight) == 0.0:
            if key is not None or selected or selection_order is not None:
                raise err(
                    "E_RNG_BUDGET",
                    "zero-weight gumbel_key must have key=null and selected=false",
                )
        else:
            if key is None:
                raise err(
                    "E_RNG_BUDGET",
                    "non-zero gumbel_key must include key",
                )

        payload: Dict[str, object] = {
            "merchant_id": int(merchant_id),
            "country_iso": str(country_iso),
            "weight": float(weight),
            "selected": bool(selected),
            "key": float(key) if key is not None else None,
        }
        if uniform is None:
            raise err("E_RNG_BUDGET", "gumbel_key missing uniform draw")
        payload["u"] = float(uniform)
        if selection_order is not None:
            payload["selection_order"] = int(selection_order)

        self._write_event(
            stream=c.STREAM_GUMBEL_KEY,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=blocks_used,
            draws=draws_used,
            payload=payload,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers

    def _event_path(self, stream: str) -> Path:
        return self._events_root / stream / self._partition("part-00000.jsonl")

    def _partition(self, filename: str) -> Path:
        return (
            Path(f"seed={self.seed}")
            / f"parameter_hash={self.parameter_hash}"
            / f"run_id={self.run_id}"
            / filename
        )

    def _write_event(
        self,
        *,
        stream: str,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks: int,
        draws: int,
        payload: Mapping[str, object],
    ) -> None:
        if blocks < 0 or draws < 0:
            raise err("E_RNG_COUNTER", "blocks/draws must be non-negative")

        record = {
            "ts_utc": _utc_timestamp(),
            "module": c.MODULE_NAME,
            "substream_label": c.SUBSTREAM_LABEL_GUMBEL,
            "seed": int(self.seed),
            "run_id": str(self.run_id),
            "parameter_hash": str(self.parameter_hash),
            "manifest_fingerprint": str(self.manifest_fingerprint),
            "rng_counter_before_hi": int(counter_before.counter_hi),
            "rng_counter_before_lo": int(counter_before.counter_lo),
            "rng_counter_after_hi": int(counter_after.counter_hi),
            "rng_counter_after_lo": int(counter_after.counter_lo),
            "blocks": int(blocks),
            "draws": str(draws),
        }
        record.update(payload)
        _append_jsonl(self._event_path(stream), record)
        self._update_trace(
            counter_before=counter_before,
            counter_after=counter_after,
            draws=draws,
            blocks=blocks,
            ts_utc=record["ts_utc"],
        )

    def _update_trace(
        self,
        *,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        draws: int,
        blocks: int,
        ts_utc: str,
    ) -> None:
        key = (c.MODULE_NAME, c.SUBSTREAM_LABEL_GUMBEL)
        stats = self._trace_totals.setdefault(
            key, {"draws": 0, "blocks": 0, "events": 0}
        )
        stats["draws"] = min(stats["draws"] + draws, U64_MAX)
        stats["blocks"] = min(stats["blocks"] + blocks, U64_MAX)
        stats["events"] = min(stats["events"] + 1, U64_MAX)

        trace_payload = {
            "ts_utc": ts_utc,
            "module": c.MODULE_NAME,
            "substream_label": c.SUBSTREAM_LABEL_GUMBEL,
            "seed": int(self.seed),
            "run_id": str(self.run_id),
            "parameter_hash": str(self.parameter_hash),
            "manifest_fingerprint": str(self.manifest_fingerprint),
            "rng_counter_before_hi": int(counter_before.counter_hi),
            "rng_counter_before_lo": int(counter_before.counter_lo),
            "rng_counter_after_hi": int(counter_after.counter_hi),
            "rng_counter_after_lo": int(counter_after.counter_lo),
            "draws_total": stats["draws"],
            "blocks_total": stats["blocks"],
            "events_total": stats["events"],
        }
        _append_jsonl(self.trace_path, trace_payload)


__all__ = ["GumbelEventWriter"]
