"""Event writer for the S4 ZTP sampler.

The writer owns JSONL persistence for all S4 RNG streams and enforces the
contractual identities (consuming vs non-consuming, partition discipline,
and trace adjacency). Higher layers provide Philox states plus measured
budget usage; this module turns those into persisted rows under the layout
defined in the dataset dictionary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, MutableMapping

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxState
from . import constants as c

U64_MAX = 2**64 - 1


def _utc_timestamp() -> str:
    """Return an RFC-3339 timestamp with exactly 6 fractional digits."""

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
    """Return the unsigned 128-bit counter delta between two Philox states."""

    before_value = (int(before.counter_hi) << 64) | int(before.counter_lo)
    after_value = (int(after.counter_hi) << 64) | int(after.counter_lo)
    if after_value < before_value:
        raise err(
            "E_RNG_COUNTER",
            "Philox counters decreased across event emission",
        )
    return after_value - before_value


def _assert_non_consuming(
    *,
    counter_before: PhiloxState,
    counter_after: PhiloxState,
    blocks_used: int,
    draws_used: int,
) -> None:
    """Ensure non-consuming rows do not advance counters or draw uniforms."""

    if blocks_used != 0 or draws_used != 0:
        raise err(
            "E_RNG_COUNTER",
            "non-consuming event must record zero blocks and draws",
        )
    if (
        int(counter_before.counter_hi) != int(counter_after.counter_hi)
        or int(counter_before.counter_lo) != int(counter_after.counter_lo)
    ):
        raise err(
            "E_RNG_COUNTER",
            "non-consuming event must reuse the Philox counter",
        )


def _assert_consuming(*, blocks_used: int, draws_used: int) -> None:
    """Ensure consuming rows advance the counter and draw at least one uniform."""

    if blocks_used <= 0 or draws_used <= 0:
        raise err(
            "E_RNG_BUDGET",
            f"consuming event requires positive blocks/draws "
            f"(blocks={blocks_used}, draws={draws_used})",
        )


@dataclass
class ZTPEventWriter:
    """Emit S4 RNG events and maintain the cumulative trace log."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    _trace_totals: MutableMapping[tuple[str, str], Dict[str, int]] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.base_path = self.base_path.resolve()
        rng_root = self.base_path / "logs" / "rng"
        self._events_root = rng_root / "events"
        self._trace_root = rng_root / "trace"
        self._trace_totals = {}

    # ------------------------------------------------------------------ #
    # Public accessors

    @property
    def poisson_events_path(self) -> Path:
        return self._event_path(c.STREAM_POISSON_COMPONENT)

    @property
    def rejection_events_path(self) -> Path:
        return self._event_path(c.STREAM_ZTP_REJECTION)

    @property
    def retry_exhausted_events_path(self) -> Path:
        return self._event_path(c.STREAM_ZTP_RETRY_EXHAUSTED)

    @property
    def final_events_path(self) -> Path:
        return self._event_path(c.STREAM_ZTP_FINAL)

    @property
    def trace_path(self) -> Path:
        return self._trace_root / self._partition(f"{c.STREAM_TRACE}.jsonl")

    # ------------------------------------------------------------------ #
    # Event emission

    def write_poisson_attempt(
        self,
        *,
        merchant_id: int,
        attempt_index: int,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks_used: int,
        draws_used: int,
        lam: float,
        k: int,
    ) -> None:
        """Persist a consuming Poisson attempt for the ZTP sampler."""

        if attempt_index < 1 or attempt_index > 64:
            raise err(
                "E_RNG_BUDGET",
                f"ztp attempt index must be 1..64, got {attempt_index}",
            )
        expected_blocks = _delta(counter_before, counter_after)
        if expected_blocks != blocks_used:
            raise err(
                "E_RNG_COUNTER",
                f"counter delta {expected_blocks} does not match blocks {blocks_used}",
            )
        _assert_consuming(blocks_used=blocks_used, draws_used=draws_used)
        payload = {
            "merchant_id": int(merchant_id),
            "context": c.CONTEXT,
            "lambda": float(lam),
            "k": int(k),
            "attempt": int(attempt_index),
        }
        self._write_event(
            stream=c.STREAM_POISSON_COMPONENT,
            substream_label=c.STREAM_POISSON_COMPONENT,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=blocks_used,
            draws=draws_used,
            payload=payload,
        )

    def write_ztp_rejection(
        self,
        *,
        merchant_id: int,
        attempt_index: int,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks_used: int,
        lambda_extra: float,
    ) -> None:
        """Persist the non-consuming ZTP rejection marker."""

        if attempt_index < 1 or attempt_index > 64:
            raise err(
                "E_RNG_BUDGET",
                f"ztp rejection attempt index must be 1..64, got {attempt_index}",
            )
        expected_blocks = _delta(counter_before, counter_after)
        if expected_blocks != blocks_used:
            raise err(
                "E_RNG_COUNTER",
                f"counter delta {expected_blocks} does not match blocks {blocks_used}",
            )
        _assert_non_consuming(
            counter_before=counter_before,
            counter_after=counter_after,
            blocks_used=blocks_used,
            draws_used=0,
        )
        payload = {
            "merchant_id": int(merchant_id),
            "context": c.CONTEXT,
            "lambda_extra": float(lambda_extra),
            "k": 0,
            "attempt": int(attempt_index),
        }
        self._write_event(
            stream=c.STREAM_ZTP_REJECTION,
            substream_label=c.STREAM_ZTP_REJECTION,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=blocks_used,
            draws=0,
            payload=payload,
        )

    def write_ztp_retry_exhausted(
        self,
        *,
        merchant_id: int,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks_used: int,
        lambda_extra: float,
        attempts: int,
        aborted: bool,
    ) -> None:
        """Persist the cap-hit marker (only emitted for policy == 'abort')."""

        expected_blocks = _delta(counter_before, counter_after)
        if expected_blocks != blocks_used:
            raise err(
                "E_RNG_COUNTER",
                f"counter delta {expected_blocks} does not match blocks {blocks_used}",
            )
        _assert_non_consuming(
            counter_before=counter_before,
            counter_after=counter_after,
            blocks_used=blocks_used,
            draws_used=0,
        )
        if int(attempts) != 64 or not bool(aborted):
            raise err(
                "E_RNG_BUDGET",
                "ztp_retry_exhausted must record attempts=64 and aborted=true",
            )
        payload = {
            "merchant_id": int(merchant_id),
            "context": c.CONTEXT,
            "lambda_extra": float(lambda_extra),
            "attempts": 64,
            "aborted": True,
        }
        self._write_event(
            stream=c.STREAM_ZTP_RETRY_EXHAUSTED,
            substream_label=c.STREAM_ZTP_RETRY_EXHAUSTED,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=blocks_used,
            draws=0,
            payload=payload,
        )

    def write_ztp_final(
        self,
        *,
        merchant_id: int,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks_used: int,
        lambda_extra: float,
        k_target: int,
        attempts: int,
        regime: str,
        exhausted: bool | None = None,
        reason: str | None = None,
    ) -> None:
        """Persist the non-consuming finaliser that fixes K_target."""

        expected_blocks = _delta(counter_before, counter_after)
        if expected_blocks != blocks_used:
            raise err(
                "E_RNG_COUNTER",
                f"counter delta {expected_blocks} does not match blocks {blocks_used}",
            )
        _assert_non_consuming(
            counter_before=counter_before,
            counter_after=counter_after,
            blocks_used=blocks_used,
            draws_used=0,
        )
        payload = {
            "merchant_id": int(merchant_id),
            "context": c.CONTEXT,
            "lambda_extra": float(lambda_extra),
            "K_target": int(k_target),
            "attempts": int(attempts),
            "regime": str(regime),
        }
        if exhausted is not None:
            payload["exhausted"] = bool(exhausted)
        if reason is not None:
            payload["reason"] = str(reason)
        self._write_event(
            stream=c.STREAM_ZTP_FINAL,
            substream_label=c.STREAM_ZTP_FINAL,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=blocks_used,
            draws=0,
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
        substream_label: str,
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
            "substream_label": substream_label,
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
            substream_label=substream_label,
        )

    def _update_trace(
        self,
        *,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        draws: int,
        blocks: int,
        ts_utc: str,
        substream_label: str,
    ) -> None:
        key = (c.MODULE_NAME, substream_label)
        stats = self._trace_totals.setdefault(
            key, {"draws": 0, "blocks": 0, "events": 0}
        )
        stats["draws"] = min(stats["draws"] + draws, U64_MAX)
        stats["blocks"] = min(stats["blocks"] + blocks, U64_MAX)
        stats["events"] = min(stats["events"] + 1, U64_MAX)

        trace_payload = {
            "ts_utc": ts_utc,
            "module": c.MODULE_NAME,
            "substream_label": substream_label,
            "seed": int(self.seed),
            "run_id": str(self.run_id),
            "rng_counter_before_hi": int(counter_before.counter_hi),
            "rng_counter_before_lo": int(counter_before.counter_lo),
            "rng_counter_after_hi": int(counter_after.counter_hi),
            "rng_counter_after_lo": int(counter_after.counter_lo),
            "draws_total": stats["draws"],
            "blocks_total": stats["blocks"],
            "events_total": stats["events"],
        }
        _append_jsonl(self.trace_path, trace_payload)


__all__ = ["ZTPEventWriter"]
