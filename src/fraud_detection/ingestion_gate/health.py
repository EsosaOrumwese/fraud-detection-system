"""Health probe and ingress control."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fraud_detection.event_bus import FileEventBusPublisher
from fraud_detection.platform_runtime import platform_run_prefix
from .ops_index import OpsIndex
from .store import ObjectStore


class HealthState(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


@dataclass(frozen=True)
class HealthResult:
    state: HealthState
    reasons: list[str]
    checked_at_utc: str


class HealthProbe:
    def __init__(
        self,
        store: ObjectStore,
        bus: Any,
        ops_index: OpsIndex,
        probe_interval_seconds: int = 30,
        max_publish_failures: int = 3,
        max_read_failures: int = 3,
        health_path: str | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.ops_index = ops_index
        self.probe_interval_seconds = probe_interval_seconds
        self.max_publish_failures = max_publish_failures
        self.max_read_failures = max_read_failures
        self._last_result: HealthResult | None = None
        self._last_checked_at: float | None = None
        self._publish_failures: int = 0
        self._read_failures: int = 0
        if health_path:
            self._health_path = health_path
        else:
            run_prefix = platform_run_prefix(create_if_missing=True)
            if not run_prefix:
                raise RuntimeError("PLATFORM_RUN_ID required for IG health probe path.")
            self._health_path = f"{run_prefix}/ig/health/last_probe.json"

    def check(self) -> HealthResult:
        now = datetime.now(tz=timezone.utc)
        if self._last_checked_at is not None:
            elapsed = (now.timestamp() - self._last_checked_at)
            if elapsed < self.probe_interval_seconds and self._last_result is not None:
                return self._last_result

        reasons: list[str] = []
        if not self._store_ok():
            reasons.append("OBJECT_STORE_UNHEALTHY")
        if self._read_failures >= self.max_read_failures:
            reasons.append("STORE_READ_UNHEALTHY")
        if not self.ops_index.probe():
            reasons.append("OPS_DB_UNHEALTHY")
        bus_reason = self._bus_ok()
        if bus_reason:
            reasons.append(bus_reason)

        if "OBJECT_STORE_UNHEALTHY" in reasons or "OPS_DB_UNHEALTHY" in reasons:
            state = HealthState.RED
        elif "STORE_READ_UNHEALTHY" in reasons:
            state = HealthState.RED
        elif "BUS_UNHEALTHY" in reasons:
            state = HealthState.RED
        elif reasons:
            state = HealthState.AMBER
        else:
            state = HealthState.GREEN

        result = HealthResult(state=state, reasons=reasons, checked_at_utc=now.isoformat())
        self._last_result = result
        self._last_checked_at = now.timestamp()
        return result

    def _store_ok(self) -> bool:
        try:
            self.store.write_json(self._health_path, {"ts": datetime.now(tz=timezone.utc).isoformat()})
            return True
        except Exception:
            return False

    def _bus_ok(self) -> str | None:
        if isinstance(self.bus, FileEventBusPublisher):
            try:
                Path(self.bus.root).mkdir(parents=True, exist_ok=True)
                return None
            except Exception:
                return "BUS_UNHEALTHY"
        if self._publish_failures >= self.max_publish_failures:
            return "BUS_UNHEALTHY"
        return "BUS_HEALTH_UNKNOWN"

    def record_publish_failure(self) -> None:
        self._publish_failures += 1

    def record_publish_success(self) -> None:
        self._publish_failures = 0

    def record_read_failure(self) -> None:
        self._read_failures += 1

    def record_read_success(self) -> None:
        self._read_failures = 0
