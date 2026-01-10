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
from typing import Dict, IO, Iterator, Mapping, MutableMapping, Optional

from ..exceptions import err
from ..l1.rng import PhiloxState, PhiloxSubstream
from ...shared.dictionary import (
    load_dictionary,
    resolve_rng_event_path,
    resolve_rng_trace_path,
)


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


U64_MAX = 2**64 - 1


@dataclass
class RNGLogWriter:
    """Materialise RNG audit, trace, and event logs in their governed paths."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    summary_flush_every: int = 10000
    io_flush_every: int = 10000
    emit_trace: bool = True
    emit_summary: bool = True
    event_filename: str = "part-00000.jsonl"
    trace_filename: str = "rng_trace_log.jsonl"
    summary_filename: str = "rng_totals.json"

    def __post_init__(self) -> None:  # pragma: no cover - simple validation
        self.base_path = self.base_path.expanduser().resolve()
        self._dictionary = load_dictionary()
        self._trace_path = resolve_rng_trace_path(
            base_path=self.base_path,
            seed=self.seed,
            parameter_hash=self.parameter_hash,
            run_id=self.run_id,
            dictionary=self._dictionary,
        )
        self._trace_totals: MutableMapping[tuple[str, str], Dict[str, int]] = {}
        self._summary_path = (self._trace_path.parent / self.summary_filename).resolve()
        self._event_handles: MutableMapping[Path, IO[str]] = {}
        self._trace_handle: Optional[IO[str]] = None
        self._events_since_summary = 0
        self._events_since_flush = 0
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

        event_file = resolve_rng_event_path(
            family,
            base_path=self.base_path,
            seed=self.seed,
            parameter_hash=self.parameter_hash,
            run_id=self.run_id,
            dictionary=self._dictionary,
        )
        record = {
            "ts_utc": _utc_timestamp(),
            "module": module,
            "substream_label": substream_label,
            "rng_counter_before_hi": counter_before.counter_hi,
            "rng_counter_before_lo": counter_before.counter_lo,
            "rng_counter_after_hi": counter_after.counter_hi,
            "rng_counter_after_lo": counter_after.counter_lo,
            "blocks": blocks,
            "draws": str(draws),
            "manifest_fingerprint": self.manifest_fingerprint,
            "parameter_hash": self.parameter_hash,
            "seed": self.seed,
            "run_id": self.run_id,
        }
        record.update(payload or {})
        self._append_jsonl_handle(self._open_event_handle(event_file), record)
        self._events_total = min(self._events_total + 1, 2**64 - 1)
        self._draws_total = min(self._draws_total + max(0, int(draws)), 2**64 - 1)
        self._blocks_total = min(self._blocks_total + max(0, int(blocks)), 2**64 - 1)

        if self.emit_trace:
            key = (module, substream_label)
            totals = self._trace_totals.setdefault(
                key, {"events": 0, "blocks": 0, "draws": 0}
            )
            totals["events"] = min(totals["events"] + 1, U64_MAX)
            totals["blocks"] = min(totals["blocks"] + blocks, U64_MAX)
            totals["draws"] = min(totals["draws"] + max(0, int(str(draws))), U64_MAX)
            trace_record = {
                "ts_utc": record["ts_utc"],
                "module": module,
                "substream_label": substream_label,
                "events_total": totals["events"],
                "blocks_total": totals["blocks"],
                "draws_total": totals["draws"],
                "rng_counter_before_hi": counter_before.counter_hi,
                "rng_counter_before_lo": counter_before.counter_lo,
                "rng_counter_after_hi": counter_after.counter_hi,
                "rng_counter_after_lo": counter_after.counter_lo,
                "run_id": self.run_id,
                "seed": self.seed,
            }
            self._append_jsonl_handle(
                self._open_trace_handle(self._trace_path), trace_record
            )
            self._events_since_summary += 1
            self._events_since_flush += 1
            if (
                self.emit_summary
                and self._events_since_summary >= self.summary_flush_every
            ):
                self._write_summary()
                self._events_since_summary = 0
            if self._events_since_flush >= self.io_flush_every:
                self._flush_handles()
                self._events_since_flush = 0

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _append_jsonl_handle(handle: IO[str], record: Mapping[str, object]) -> None:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")

    def _open_event_handle(self, path: Path) -> IO[str]:
        handle = self._event_handles.get(path)
        if handle is None:
            self._ensure_dir(path.parent)
            handle = path.open("a", encoding="utf-8")
            self._event_handles[path] = handle
        return handle

    def _open_trace_handle(self, path: Path) -> IO[str]:
        if self._trace_handle is None:
            self._ensure_dir(path.parent)
            self._trace_handle = path.open("a", encoding="utf-8")
        return self._trace_handle

    def _flush_handles(self) -> None:
        for handle in self._event_handles.values():
            handle.flush()
        if self._trace_handle is not None:
            self._trace_handle.flush()

    def _write_summary(self) -> None:
        if not self.emit_summary:
            return
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

    def close(self) -> None:
        self._write_summary()
        self._flush_handles()
        for handle in self._event_handles.values():
            handle.close()
        self._event_handles.clear()
        if self._trace_handle is not None:
            self._trace_handle.close()
            self._trace_handle = None


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
