"""In-process metrics aggregation (log-flushed)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
narrative_logger = logging.getLogger("fraud_detection.platform_narrative")


@dataclass
class MetricsRecorder:
    flush_interval_seconds: int = 30
    counters: dict[str, int] = field(default_factory=dict)
    latencies: dict[str, list[float]] = field(default_factory=dict)
    last_flush_ts: float = field(default_factory=time.time)

    def record_decision(self, decision: str, reason_code: str | None = None) -> None:
        self._inc(f"decision.{decision}")
        if reason_code:
            self._inc(f"reason.{reason_code}")

    def record_latency(self, name: str, seconds: float) -> None:
        self.latencies.setdefault(name, []).append(seconds)

    def flush_if_due(self, context: dict[str, Any] | None = None) -> None:
        now = time.time()
        if (now - self.last_flush_ts) < self.flush_interval_seconds:
            return
        payload = {
            "counters": dict(self.counters),
            "latencies": {k: _summarize(v) for k, v in self.latencies.items()},
        }
        if context:
            payload["context"] = context
        logger.info("IG metrics %s", payload)
        if self.counters:
            narrative_logger.info(
                "IG summary admit=%s duplicate=%s quarantine=%s",
                self.counters.get("decision.ADMIT", 0),
                self.counters.get("decision.DUPLICATE", 0),
                self.counters.get("decision.QUARANTINE", 0),
            )
        self.counters.clear()
        self.latencies.clear()
        self.last_flush_ts = now

    def _inc(self, key: str, amount: int = 1) -> None:
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
