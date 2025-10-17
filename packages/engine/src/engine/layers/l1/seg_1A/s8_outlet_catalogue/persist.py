"""Persistence helpers for the S8 outlet catalogue pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, MutableMapping, Sequence

import pandas as pd

from ..s0_foundations.exceptions import err
from ..s0_foundations.l1.rng import PhiloxState
from ..s0_foundations.l2.output import refresh_validation_bundle_flag
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from .constants import (
    DATASET_OUTLET_CATALOGUE,
    EVENT_FAMILY_SEQUENCE_FINALIZE,
    EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW,
    MODULE_NAME,
    SUBSTREAM_SEQUENCE_FINALIZE,
    SUBSTREAM_SITE_SEQUENCE_OVERFLOW,
)
from .types import OutletCatalogueRow, SequenceFinalizeEvent, SiteSequenceOverflowEvent

U64_MAX = 2**64 - 1


@dataclass
class PersistConfig:
    """Configuration for persisting S8 outputs."""

    seed: int
    manifest_fingerprint: str
    output_dir: Path
    parameter_hash: str
    run_id: str


def write_outlet_catalogue(
    rows: Sequence[OutletCatalogueRow],
    *,
    config: PersistConfig,
    dictionary: Mapping[str, object] | None = None,
) -> Path:
    """Persist the `outlet_catalogue` parquet partition."""

    dictionary = dictionary or load_dictionary()
    target_path = resolve_dataset_path(
        DATASET_OUTLET_CATALOGUE,
        base_path=config.output_dir,
        template_args={
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
        },
        dictionary=dictionary,
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        frame = pd.DataFrame(
            columns=[
                "manifest_fingerprint",
                "merchant_id",
                "site_id",
                "home_country_iso",
                "legal_country_iso",
                "single_vs_multi_flag",
                "raw_nb_outlet_draw",
                "final_country_outlet_count",
                "site_order",
                "global_seed",
            ]
        )
    else:
        frame = pd.DataFrame([row.__dict__ for row in rows])
        frame = frame.sort_values(["merchant_id", "legal_country_iso", "site_order"]).reset_index(drop=True)

    frame.to_parquet(target_path, index=False, compression="zstd")
    return target_path


def write_sequence_events(
    *,
    sequence_finalize: Sequence[SequenceFinalizeEvent],
    overflow_events: Sequence[SiteSequenceOverflowEvent],
    config: PersistConfig,
    dictionary: Mapping[str, object] | None = None,
) -> Mapping[str, Path]:
    """Write RNG event streams produced by S8."""

    if not sequence_finalize and not overflow_events:
        return {}

    writer = _S8EventWriter(config=config, dictionary=dictionary)
    for event in sequence_finalize:
        writer.write_sequence_finalize(event)
    for event in overflow_events:
        writer.write_site_sequence_overflow(event)
    writer.flush()
    return writer.output_paths()


def write_validation_bundle(
    *,
    bundle_dir: Path,
    metrics_payload: Mapping[str, object],
    rng_accounting_payload: Mapping[str, object],
    catalogue_path: Path,
) -> Path:
    """Produce the validation artefacts mandated by the spec."""

    bundle_dir = bundle_dir.expanduser().resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    _write_json(bundle_dir / "rng_accounting.json", rng_accounting_payload)
    _write_json(bundle_dir / "s8_metrics.json", metrics_payload)
    _write_json(
        bundle_dir / "egress_checksums.json",
        _build_checksum_payload(catalogue_path=catalogue_path, metrics=metrics_payload),
    )
    refresh_validation_bundle_flag(bundle_dir)
    return bundle_dir / "_passed.flag"


def _build_checksum_payload(
    *,
    catalogue_path: Path,
    metrics: Mapping[str, object],
) -> Mapping[str, object]:
    if not catalogue_path.exists():
        raise err(
            "E_S8_EGRESS_MISSING",
            f"expected outlet_catalogue at '{catalogue_path}' for checksum generation",
        )
    file_hash = _sha256_file(catalogue_path)
    rows_total = int(metrics.get("rows_total", 0))
    return {
        "files": [
            {
                "path": catalogue_path.as_posix(),
                "sha256": file_hash,
                "size_bytes": catalogue_path.stat().st_size,
            }
        ],
        "rows_total": rows_total,
        "pk_hash_hex": metrics.get("pk_hash_hex", ""),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


class _S8EventWriter:
    """Emit S8 RNG event families and update the trace log."""

    def __init__(
        self,
        *,
        config: PersistConfig,
        dictionary: Mapping[str, object] | None,
    ) -> None:
        self._config = config
        self._dictionary = dictionary or load_dictionary()
        self._zero_state = PhiloxState(0, 0, 0)
        self._events_written: MutableMapping[tuple[str, str], Dict[str, int]] = self._load_existing_trace_totals()
        self._sequence_path: Path | None = None
        self._overflow_path: Path | None = None
        self._trace_path: Path | None = None

    def output_paths(self) -> Mapping[str, Path]:
        paths: dict[str, Path] = {}
        if self._sequence_path is not None:
            paths[EVENT_FAMILY_SEQUENCE_FINALIZE] = self._sequence_path
        if self._overflow_path is not None:
            paths[EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW] = self._overflow_path
        if self._trace_path is not None:
            paths["rng_trace_log"] = self._trace_path
        return paths

    def write_sequence_finalize(self, event: SequenceFinalizeEvent) -> None:
        record = {
            "merchant_id": int(event.merchant_id),
            "legal_country_iso": str(event.legal_country_iso),
            "site_order_start": int(event.site_order_start),
            "site_order_end": int(event.site_order_end),
            "site_count": int(event.site_count),
            "manifest_fingerprint": event.manifest_fingerprint,
        }
        self._write_event(
            dataset_id=EVENT_FAMILY_SEQUENCE_FINALIZE,
            substream=SUBSTREAM_SEQUENCE_FINALIZE,
            payload=record,
        )

    def write_site_sequence_overflow(self, event: SiteSequenceOverflowEvent) -> None:
        record = {
            "merchant_id": int(event.merchant_id),
            "legal_country_iso": str(event.legal_country_iso),
            "attempted_count": int(event.attempted_sequence),
            "max_seq": 999_999,
            "overflow_by": max(int(event.attempted_sequence) - 999_999, 0),
            "severity": "ERROR",
            "manifest_fingerprint": event.manifest_fingerprint,
        }
        self._write_event(
            dataset_id=EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW,
            substream=SUBSTREAM_SITE_SEQUENCE_OVERFLOW,
            payload=record,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers

    def _write_event(
        self,
        *,
        dataset_id: str,
        substream: str,
        payload: Mapping[str, object],
    ) -> None:
        event_path = self._resolve_event_path(dataset_id)
        event_path.parent.mkdir(parents=True, exist_ok=True)

        ts_utc = _utc_timestamp()
        envelope = {
            "ts_utc": ts_utc,
            "module": MODULE_NAME,
            "substream_label": substream,
            "seed": int(self._config.seed),
            "run_id": str(self._config.run_id),
            "parameter_hash": str(self._config.parameter_hash),
            "manifest_fingerprint": str(self._config.manifest_fingerprint),
            "rng_counter_before_hi": int(self._zero_state.counter_hi),
            "rng_counter_before_lo": int(self._zero_state.counter_lo),
            "rng_counter_after_hi": int(self._zero_state.counter_hi),
            "rng_counter_after_lo": int(self._zero_state.counter_lo),
            "blocks": 0,
            "draws": "0",
        }
        envelope.update(payload)

        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, sort_keys=True))
            handle.write("\n")

        self._update_trace(substream=substream, ts_utc=ts_utc)
        if dataset_id == EVENT_FAMILY_SEQUENCE_FINALIZE:
            self._sequence_path = event_path
        elif dataset_id == EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW:
            self._overflow_path = event_path

    def _resolve_event_path(self, dataset_id: str) -> Path:
        return resolve_dataset_path(
            dataset_id,
            base_path=self._config.output_dir,
            template_args={
                "seed": self._config.seed,
                "parameter_hash": self._config.parameter_hash,
                "run_id": self._config.run_id,
            },
            dictionary=self._dictionary,
        )

    def _trace_log_path(self) -> Path:
        if self._trace_path is None:
            self._trace_path = resolve_dataset_path(
                "rng_trace_log",
                base_path=self._config.output_dir,
                template_args={
                    "seed": self._config.seed,
                    "parameter_hash": self._config.parameter_hash,
                    "run_id": self._config.run_id,
                },
                dictionary=self._dictionary,
            )
        return self._trace_path

    def _update_trace(self, *, substream: str, ts_utc: str) -> None:
        key = (MODULE_NAME, substream)
        stats = self._events_written.setdefault(
            key, {"events": 0, "blocks": 0, "draws": 0}
        )
        stats["events"] = min(stats["events"] + 1, U64_MAX)
        trace_record = {
            "ts_utc": ts_utc,
            "module": MODULE_NAME,
            "substream_label": substream,
            "seed": int(self._config.seed),
            "run_id": str(self._config.run_id),
            "parameter_hash": str(self._config.parameter_hash),
            "manifest_fingerprint": str(self._config.manifest_fingerprint),
            "events_total": stats["events"],
            "draws_total": "0",
            "blocks_total": "0",
        }
        trace_path = self._trace_log_path()
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace_record, sort_keys=True))
            handle.write("\n")

    def _load_existing_trace_totals(self) -> MutableMapping[tuple[str, str], Dict[str, int]]:
        trace_path = resolve_dataset_path(
            "rng_trace_log",
            base_path=self._config.output_dir,
            template_args={
                "seed": self._config.seed,
                "parameter_hash": self._config.parameter_hash,
                "run_id": self._config.run_id,
            },
            dictionary=self._dictionary,
        )
        if not trace_path.exists():
            return {}

        totals: MutableMapping[tuple[str, str], Dict[str, int]] = {}
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:  # pragma: no cover - defensive
                    continue
                key = (record.get("module", ""), record.get("substream_label", ""))
                if key[0] != MODULE_NAME:
                    continue
                totals[key] = {
                    "events": int(record.get("events_total", 0)),
                    "blocks": int(str(record.get("blocks_total", "0"))),
                    "draws": int(str(record.get("draws_total", "0"))),
                }
        return totals

    def flush(self) -> None:  # pragma: no cover - nothing buffered
        return None


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


__all__ = [
    "PersistConfig",
    "write_outlet_catalogue",
    "write_sequence_events",
    "write_validation_bundle",
]
