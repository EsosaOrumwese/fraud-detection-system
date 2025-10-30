"""Helpers for writing RNG trace logs shared across Segment 1B states."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from ..s0_gate.exceptions import err


def append_trace_records(
    trace_path: Path,
    *,
    events: Iterable[Mapping[str, object]],
    seed: int,
    run_id: str,
) -> None:
    """Append RNG trace records, continuing existing cumulative totals when present."""

    trace_path = trace_path.resolve()
    trace_path.parent.mkdir(parents=True, exist_ok=True)

    totals: dict[tuple[str, str], dict[str, int]] = {}
    if trace_path.exists():
        existing_text = trace_path.read_text(encoding="utf-8")
        if existing_text.strip():
            try:
                parsed_records = [
                    json.loads(line)
                    for line in existing_text.splitlines()
                    if line.strip()
                ]
            except json.JSONDecodeError as exc:
                raise err("E611_LOG_PARTITION_LAW", f"rng trace log at '{trace_path}' is not valid JSONL") from exc
            else:
                for payload in parsed_records:
                    key = (str(payload.get("module", "")), str(payload.get("substream_label", "")))
                    totals[key] = {
                        "events": int(payload.get("events_total", 0)),
                        "blocks": int(payload.get("blocks_total", 0)),
                        "draws": int(str(payload.get("draws_total", "0"))),
                    }

    records_to_append: list[Mapping[str, object]] = []
    for event in events:
        module = str(event.get("module", ""))
        substream_label = str(event.get("substream_label", ""))
        key = (module, substream_label)
        stats = totals.setdefault(key, {"events": 0, "blocks": 0, "draws": 0})
        blocks = int(event.get("blocks", 0))
        draws = int(event.get("draws", "0"))
        stats["events"] += 1
        stats["blocks"] += blocks
        stats["draws"] += draws
        records_to_append.append(
            {
                "ts_utc": event.get("ts_utc"),
                "run_id": run_id,
                "seed": seed,
                "module": module,
                "substream_label": substream_label,
                "draws_total": stats["draws"],
                "blocks_total": stats["blocks"],
                "events_total": stats["events"],
                "rng_counter_before_lo": int(event.get("rng_counter_before_lo", 0)),
                "rng_counter_before_hi": int(event.get("rng_counter_before_hi", 0)),
                "rng_counter_after_lo": int(event.get("rng_counter_after_lo", 0)),
                "rng_counter_after_hi": int(event.get("rng_counter_after_hi", 0)),
            }
        )

    if not records_to_append:
        return

    with trace_path.open("a", encoding="utf-8") as handle:
        for record in records_to_append:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")


__all__ = ["append_trace_records"]
