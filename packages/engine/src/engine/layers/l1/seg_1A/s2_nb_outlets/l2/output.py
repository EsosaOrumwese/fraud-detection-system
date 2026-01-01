"""Persistence helpers for S2 RNG events."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, MutableMapping

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxState
from ..l1 import rng as nb_rng


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
    """Return the u128 counter delta derived from (before, after)."""

    before_value = (int(before.counter_hi) << 64) | int(before.counter_lo)
    after_value = (int(after.counter_hi) << 64) | int(after.counter_lo)
    if after_value < before_value:
        raise err(
            "E_RNG_COUNTER",
            "Philox counters decreased across event emission",
        )
    return after_value - before_value


@dataclass
class NBEventWriter:
    """Emit gamma/poisson/final RNG events and maintain cumulative trace logs."""

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
        self._events_root = self.base_path / "logs" / "rng" / "events"
        self._trace_root = self.base_path / "logs" / "rng" / "trace"
        self._trace_totals = {}

    @property
    def gamma_events_path(self) -> Path:
        return self._event_path("gamma_component")

    @property
    def poisson_events_path(self) -> Path:
        return self._event_path("poisson_component")

    @property
    def final_events_path(self) -> Path:
        return self._event_path("nb_final")

    @property
    def trace_path(self) -> Path:
        return self._trace_root / self._partition("rng_trace_log.jsonl")

    def write_gamma_component(
        self,
        *,
        merchant_id: int,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks_used: int,
        draws_used: int,
        alpha: float,
        gamma_value: float,
    ) -> None:
        """Persist a gamma_component event for a single attempt."""

        if blocks_used < 0 or draws_used <= 0:
            raise err(
                "E_RNG_BUDGET",
                f"gamma_component must consume draws > 0 (draws={draws_used})",
            )

        payload = {
            "merchant_id": int(merchant_id),
            "context": "nb",
            "index": 0,
            "alpha": float(alpha),
            "gamma_value": float(gamma_value),
        }
        self._write_event(
            stream="gamma_component",
            module=nb_rng.GAMMA_MODULE_NAME,
            substream_label=nb_rng.GAMMA_SUBSTREAM_LABEL,
            merchant_id=merchant_id,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=blocks_used,
            draws=draws_used,
            payload=payload,
        )

    def write_poisson_component(
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
        """Persist a poisson_component event for the same attempt."""

        if blocks_used < 0 or draws_used <= 0:
            raise err(
                "E_RNG_BUDGET",
                f"poisson_component must consume draws > 0 (draws={draws_used})",
            )
        if attempt_index < 1:
            raise err(
                "E_S2_ATTEMPT_INDEX",
                f"attempt index must be >= 1, got {attempt_index}",
            )

        payload = {
            "merchant_id": int(merchant_id),
            "context": "nb",
            "lambda": float(lam),
            "k": int(k),
            "attempt": int(attempt_index),
        }
        self._write_event(
            stream="poisson_component",
            module=nb_rng.POISSON_MODULE_NAME,
            substream_label=nb_rng.POISSON_SUBSTREAM_LABEL,
            merchant_id=merchant_id,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=blocks_used,
            draws=draws_used,
            payload=payload,
        )

    def write_final_event(
        self,
        *,
        merchant_id: int,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        mu: float,
        phi: float,
        n_outlets: int,
        nb_rejections: int,
    ) -> None:
        """Emit the non-consuming nb_final record."""

        if nb_rejections < 0:
            raise err(
                "E_S2_REJECTIONS_NEGATIVE",
                f"nb_rejections must be >= 0, got {nb_rejections}",
            )
        if n_outlets < 2:
            raise err(
                "E_S2_ACCEPT_INVALID",
                f"accepted outlet count must be >= 2, got {n_outlets}",
            )

        if _delta(counter_before, counter_after) != 0:
            raise err(
                "E_RNG_COUNTER",
                "nb_final substream must be non-consuming (before == after)",
            )

        payload = {
            "merchant_id": int(merchant_id),
            "mu": float(mu),
            "dispersion_k": float(phi),
            "n_outlets": int(n_outlets),
            "nb_rejections": int(nb_rejections),
            "method": "poisson_gamma_mixture",
        }
        self._write_event(
            stream="nb_final",
            module=nb_rng.FINAL_MODULE_NAME,
            substream_label=nb_rng.FINAL_SUBSTREAM_LABEL,
            merchant_id=merchant_id,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=0,
            draws=0,
            payload=payload,
        )

    # --------------------------------------------------------------------- #
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
        module: str,
        substream_label: str,
        merchant_id: int,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks: int,
        draws: int,
        payload: Mapping[str, object],
    ) -> None:
        if blocks < 0 or draws < 0:
            raise err("E_RNG_COUNTER", "blocks/draws must be non-negative")

        expected_delta = _delta(counter_before, counter_after)
        if expected_delta != blocks:
            raise err(
                "E_RNG_COUNTER",
                f"counter delta {expected_delta} does not match blocks {blocks}",
            )

        record = {
            "ts_utc": _utc_timestamp(),
            "module": module,
            "substream_label": substream_label,
            "seed": int(self.seed),
            "run_id": str(self.run_id),
            "parameter_hash": str(self.parameter_hash),
            "manifest_fingerprint": str(self.manifest_fingerprint),
            "rng_counter_before_hi": int(counter_before.counter_hi),
            "rng_counter_before_lo": int(counter_before.counter_lo),
            "rng_counter_after_hi": int(counter_after.counter_hi),
            "rng_counter_after_lo": int(counter_after.counter_lo),
            "draws": str(draws),
            "blocks": int(blocks),
        }
        record.update(payload)
        _append_jsonl(self._event_path(stream), record)
        self._update_trace(
            module=module,
            substream_label=substream_label,
            counter_before=counter_before,
            counter_after=counter_after,
            draws=draws,
            blocks=blocks,
            ts_utc=str(record["ts_utc"]),
        )

    def _update_trace(
        self,
        module: str,
        substream_label: str,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        draws: int,
        blocks: int,
        ts_utc: str,
    ) -> None:
        key = (module, substream_label)
        stats = self._trace_totals.setdefault(
            key, {"draws": 0, "blocks": 0, "events": 0}
        )
        stats["draws"] = min(stats["draws"] + draws, 2**64 - 1)
        stats["blocks"] = min(stats["blocks"] + blocks, 2**64 - 1)
        stats["events"] = min(stats["events"] + 1, 2**64 - 1)

        trace_payload = {
            "ts_utc": ts_utc,
            "module": module,
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


__all__ = ["NBEventWriter"]
