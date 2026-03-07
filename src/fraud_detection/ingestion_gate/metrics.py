"""In-process metrics aggregation (log-flushed)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)
narrative_logger = logging.getLogger("fraud_detection.platform_narrative")


@dataclass
class MetricsRecorder:
    flush_interval_seconds: int = 30
    counters: dict[str, int] = field(default_factory=dict)
    latencies: dict[str, list[float]] = field(default_factory=dict)
    last_flush_ts: float = field(default_factory=time.time)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def record_decision(self, decision: str, reason_code: str | None = None) -> None:
        with self._lock:
            self._inc_unlocked(f"decision.{decision}")
            if reason_code:
                self._inc_unlocked(f"reason.{reason_code}")

    def record_latency(self, name: str, seconds: float) -> None:
        with self._lock:
            self.latencies.setdefault(name, []).append(seconds)

    def flush_if_due(self, context: dict[str, Any] | None = None) -> None:
        now = time.time()
        with self._lock:
            if (now - self.last_flush_ts) < self.flush_interval_seconds:
                return
            counters_snapshot = dict(self.counters)
            latencies_snapshot = {key: list(values) for key, values in self.latencies.items()}
            self.counters.clear()
            self.latencies.clear()
            self.last_flush_ts = now
        payload = {
            "counters": counters_snapshot,
            "latencies": {k: _summarize(v) for k, v in latencies_snapshot.items()},
        }
        if context:
            payload["context"] = context
        logger.info("IG metrics %s", payload)
        if counters_snapshot:
            narrative_logger.info(
                "IG summary admit=%s duplicate=%s quarantine=%s",
                counters_snapshot.get("decision.ADMIT", 0),
                counters_snapshot.get("decision.DUPLICATE", 0),
                counters_snapshot.get("decision.QUARANTINE", 0),
            )

    def _inc(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self._inc_unlocked(key, amount)

    def _inc_unlocked(self, key: str, amount: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + amount


def _summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0}
    values_sorted = sorted(values)
    count = len(values_sorted)
    return {
        "count": count,
        "min": values_sorted[0],
        "max": values_sorted[-1],
        "p50": values_sorted[count // 2],
        "p95": values_sorted[int(count * 0.95) - 1],
    }
