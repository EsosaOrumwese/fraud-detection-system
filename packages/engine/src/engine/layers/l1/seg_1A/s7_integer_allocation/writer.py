"""Event writer for S7 integer allocation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, MutableMapping, Tuple

from ..s0_foundations.exceptions import err
from ..s0_foundations.l1.rng import PhiloxState
from . import constants as c

U64_MAX = 2**64 - 1
_ZERO_STATE = PhiloxState(0, 0, 0)

__all__ = ["S7EventWriter"]


def _utc_timestamp() -> str:
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


@dataclass
class S7EventWriter:
    """Emit S7 RNG events and maintain the cumulative trace log."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    _trace_totals: MutableMapping[Tuple[str, str], Dict[str, int]] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.base_path = self.base_path.expanduser().resolve()
        rng_root = self.base_path / "logs" / "rng"
        self._events_root = rng_root / "events"
        self._trace_root = rng_root / "trace"
        self._trace_totals = {}

    @property
    def residual_path(self) -> Path:
        return self._events_root / c.STREAM_RESIDUAL_RANK / self._partition("part-00000.jsonl")

    @property
    def dirichlet_path(self) -> Path:
        return self._events_root / c.STREAM_DIRICHLET_GAMMA / self._partition("part-00000.jsonl")

    @property
    def trace_path(self) -> Path:
        return self._trace_root / self._partition(c.TRACE_FILENAME)

    def write_residual_rank(
        self,
        *,
        merchant_id: int,
        country_iso: str,
        residual: float,
        residual_rank: int,
    ) -> None:
        """Emit a single residual_rank event (non-consuming)."""

        payload = {
            "merchant_id": int(merchant_id),
            "country_iso": str(country_iso),
            "residual": float(residual),
            "residual_rank": int(residual_rank),
        }
        self._write_event(
            module=c.MODULE_INTEGERISATION,
            substream=c.SUBSTREAM_LABEL_RESIDUAL,
            stream=c.STREAM_RESIDUAL_RANK,
            counter_before=_ZERO_STATE,
            counter_after=_ZERO_STATE,
            blocks=0,
            draws=0,
            payload=payload,
        )

    def write_dirichlet_gamma_vector(
        self,
        *,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks_used: int,
        draws_used: int,
        merchant_id: int,
        home_country_iso: str,
        country_isos: Tuple[str, ...],
        alpha: Tuple[float, ...],
        gamma_raw: Tuple[float, ...],
        weights: Tuple[float, ...],
        n_domestic: int | None,
    ) -> None:
        """Emit a dirichlet_gamma_vector event."""

        if blocks_used < 0 or draws_used < 0:
            raise err(
                "E_RNG_ENVELOPE",
                "dirichlet event must record non-negative blocks/draws",
            )
        payload: Dict[str, object] = {
            "merchant_id": int(merchant_id),
            "home_country_iso": str(home_country_iso),
            "country_isos": list(country_isos),
            "alpha": [float(value) for value in alpha],
            "gamma_raw": [float(value) for value in gamma_raw],
            "weights": [float(value) for value in weights],
        }
        if n_domestic is not None:
            payload["n_domestic"] = int(n_domestic)

        self._write_event(
            module=c.MODULE_DIRICHLET,
            substream=c.SUBSTREAM_LABEL_DIRICHLET,
            stream=c.STREAM_DIRICHLET_GAMMA,
            counter_before=counter_before,
            counter_after=counter_after,
            blocks=blocks_used,
            draws=draws_used,
            payload=payload,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers

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
        module: str,
        substream: str,
        stream: str,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        blocks: int,
        draws: int,
        payload: Mapping[str, object],
    ) -> None:
        record = {
            "ts_utc": _utc_timestamp(),
            "module": module,
            "substream_label": substream,
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
        _append_jsonl(self._events_root / stream / self._partition("part-00000.jsonl"), record)
        self._update_trace(
            module=module,
            substream=substream,
            draws=draws,
            blocks=blocks,
            ts_utc=record["ts_utc"],
        )

    def _update_trace(
        self,
        *,
        module: str,
        substream: str,
        draws: int,
        blocks: int,
        ts_utc: str,
    ) -> None:
        key = (module, substream)
        stats = self._trace_totals.setdefault(
            key, {"draws": 0, "blocks": 0, "events": 0}
        )
        stats["draws"] = min(stats["draws"] + draws, U64_MAX)
        stats["blocks"] = min(stats["blocks"] + blocks, U64_MAX)
        stats["events"] = min(stats["events"] + 1, U64_MAX)

        trace_record = {
            "ts_utc": ts_utc,
            "module": module,
            "substream_label": substream,
            "seed": int(self.seed),
            "run_id": str(self.run_id),
            "parameter_hash": str(self.parameter_hash),
            "manifest_fingerprint": str(self.manifest_fingerprint),
            "events_total": stats["events"],
            "draws_total": str(stats["draws"]),
            "blocks_total": str(stats["blocks"]),
        }
        _append_jsonl(self.trace_path, trace_record)
