"""Engine pull ingestion: frame engine outputs into canonical envelopes."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq

from .catalogue import OutputCatalogue
from .errors import IngestionError
from .ids import derive_engine_event_id

logger = logging.getLogger(__name__)

@dataclass
class EnginePuller:
    run_facts_view_path: Path
    catalogue: OutputCatalogue

    def iter_events(self) -> Iterable[dict[str, Any]]:
        facts = json.loads(self.run_facts_view_path.read_text(encoding="utf-8"))
        pins = facts.get("pins", {})
        output_roles = facts.get("output_roles", {})
        locators = facts.get("locators", [])
        locator_by_output = {loc["output_id"]: Path(loc["path"]) for loc in locators}
        for output_id, role in output_roles.items():
            if role != "business_traffic":
                continue
            if output_id not in locator_by_output:
                continue
            logger.info("IG engine_pull output_id=%s path=%s", output_id, locator_by_output[output_id])
            yield from self._events_from_output(output_id, locator_by_output[output_id], pins)

    def _events_from_output(
        self,
        output_id: str,
        path: Path,
        pins: dict[str, Any],
    ) -> Iterable[dict[str, Any]]:
        entry = self.catalogue.get(output_id)
        files = self._expand_paths(path)
        for file_path in files:
            for row in self._read_rows(file_path):
                event_id = derive_engine_event_id(output_id, entry.primary_key, row, pins)
                ts_utc = row.get("ts_utc")
                if ts_utc is None:
                    raise IngestionError("MISSING_EVENT_TIME")
                envelope = {
                    "event_id": event_id,
                    "event_type": output_id,
                    "ts_utc": ts_utc,
                    "manifest_fingerprint": pins.get("manifest_fingerprint"),
                    "parameter_hash": pins.get("parameter_hash"),
                    "seed": pins.get("seed"),
                    "scenario_id": pins.get("scenario_id"),
                    "run_id": pins.get("run_id"),
                    "producer": "engine",
                    "payload": row,
                }
                yield envelope

    def _expand_paths(self, path: Path) -> list[Path]:
        if "*" in path.name:
            return list(path.parent.glob(path.name))
        return [path]

    def _read_rows(self, path: Path) -> Iterable[dict[str, Any]]:
        if path.suffix == ".parquet":
            table = pq.read_table(path)
            for row in table.to_pylist():
                yield row
        elif path.suffix in (".jsonl", ".json"):
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for row in data:
                        yield row
                elif isinstance(data, dict):
                    yield data
            else:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if line.strip():
                            yield json.loads(line)
        else:
            raise ValueError("UNSUPPORTED_OUTPUT_FORMAT")
