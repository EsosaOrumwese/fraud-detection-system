"""RNG logging helpers for S0 foundations.

The design requires a structured audit/trace/event log for RNG usage.  This
module provides a small writer that materialises those logs in the contract
paths and a context manager that records the before/after counters for each
event.  Keeping it separate from the Philox implementation keeps the concerns
clean.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping, MutableMapping, Optional

from ..exceptions import err
from ..l1.rng import PhiloxState, PhiloxSubstream


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


@dataclass
class RNGLogWriter:
    """Materialise RNG audit, trace, and event logs in their governed paths."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str

    def __post_init__(self) -> None:  # pragma: no cover - simple validation
        self._events_root = (self.base_path / "events").resolve()
        self._trace_root = (self.base_path / "trace").resolve()
        self._ensure_dir(self._events_root)
        self._ensure_dir(self._trace_root)
        self._trace_totals: MutableMapping[tuple[str, str], int] = {}
        self._summary_path = (
            self._trace_root / self._seed_path / "rng_totals.json"
        ).resolve()
        self._events_total = 0
        self._draws_total = 0
        self._blocks_total = 0
        if self._summary_path.exists():
            try:
                summary = json.loads(self._summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                summary = None
            if isinstance(summary, Mapping):
                self._events_total = int(summary.get("events_total", 0) or 0)
                self._draws_total = int(summary.get("draws_total", 0) or 0)
                self._blocks_total = int(summary.get("blocks_total", 0) or 0)

    def log_event(
        self,
        *,
        family: str,
        module: str,
        substream_label: str,
        event: str,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks: int,
        draws: int,
        payload: Optional[Mapping[str, object]] = None,
    ) -> None:
        if blocks < 0 or draws < 0:
            raise err("E_RNG_COUNTER", "negative blocks or draws recorded")

        events_dir = self._events_root / family / self._seed_path
        self._ensure_dir(events_dir)
        event_file = events_dir / "part-00000.jsonl"
        record = {
            "ts_utc": _utc_timestamp(),
            "module": module,
            "substream_label": substream_label,
            "event": event,
            "rng_counter_before": {
                "hi": counter_before.counter_hi,
                "lo": counter_before.counter_lo,
            },
            "rng_counter_after": {
                "hi": counter_after.counter_hi,
                "lo": counter_after.counter_lo,
            },
            "blocks": blocks,
            "draws": str(draws),
            "payload": dict(payload or {}),
            "manifest_fingerprint": self.manifest_fingerprint,
            "parameter_hash": self.parameter_hash,
            "seed": self.seed,
            "run_id": self.run_id,
        }
        self._append_jsonl(event_file, record)
        self._events_total = min(self._events_total + 1, 2**64 - 1)
        self._draws_total = min(self._draws_total + max(0, int(draws)), 2**64 - 1)
        self._blocks_total = min(self._blocks_total + max(0, int(blocks)), 2**64 - 1)

        key = (module, substream_label)
        total_blocks = self._trace_totals.get(key, 0) + blocks
        self._trace_totals[key] = total_blocks
        trace_dir = self._trace_root / self._seed_path
        self._ensure_dir(trace_dir)
        trace_file = trace_dir / "rng_trace_log.jsonl"
        trace_record = {
            "ts_utc": record["ts_utc"],
            "module": module,
            "substream_label": substream_label,
            "blocks_total": total_blocks,
            "run_id": self.run_id,
            "seed": self.seed,
            "parameter_hash": self.parameter_hash,
        }
        self._append_jsonl(trace_file, trace_record)
        self._write_summary()

    @property
    def _seed_path(self) -> Path:
        return (
            Path(f"seed={self.seed}")
            / f"parameter_hash={self.parameter_hash}"
            / f"run_id={self.run_id}"
        )

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _append_jsonl(path: Path, record: Mapping[str, object]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")

    def _write_summary(self) -> None:
        self._ensure_dir(self._summary_path.parent)
        summary = {
            "seed": self.seed,
            "parameter_hash": self.parameter_hash,
            "manifest_fingerprint": self.manifest_fingerprint,
            "run_id": self.run_id,
            "events_total": self._events_total,
            "draws_total": self._draws_total,
            "blocks_total": self._blocks_total,
        }
        with self._summary_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, sort_keys=True)


@contextmanager
def rng_event(
    *,
    logger: RNGLogWriter,
    substream: PhiloxSubstream,
    module: str,
    family: str,
    event: str,
    substream_label: str,
    expected_blocks: Optional[int] = None,
    expected_draws: Optional[int] = None,
    payload: Optional[Mapping[str, object]] = None,
) -> Iterator[PhiloxSubstream]:
    """Context manager that logs Philox counters and payload for an event."""
    before_state = substream.snapshot()
    before_blocks = substream.blocks
    before_draws = substream.draws
    try:
        yield substream
    finally:
        after_state = substream.snapshot()
        blocks = substream.blocks - before_blocks
        draws = substream.draws - before_draws
        if blocks < 0 or draws < 0:
            raise err("E_RNG_COUNTER", "rng counters decreased across event")
        if expected_blocks is not None and blocks != expected_blocks:
            raise err(
                "E_RNG_BUDGET",
                f"event '{event}' expected {expected_blocks} blocks, observed {blocks}",
            )
        if expected_draws is not None and draws != expected_draws:
            raise err(
                "E_RNG_BUDGET",
                f"event '{event}' expected {expected_draws} draws, observed {draws}",
            )
        delta = after_state.counter_lo - before_state.counter_lo
        if delta != blocks:
            raise err(
                "E_RNG_COUNTER",
                "counter/blocks mismatch detected",
            )
        logger.log_event(
            family=family,
            module=module,
            substream_label=substream_label,
            event=event,
            counter_before=before_state,
            counter_after=after_state,
            blocks=blocks,
            draws=draws,
            payload=payload,
        )


__all__ = ["RNGLogWriter", "rng_event"]
