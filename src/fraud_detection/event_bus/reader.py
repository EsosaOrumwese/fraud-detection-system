"""Local Event Bus reader (file-bus only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class EbRecord:
    topic: str
    partition: int
    offset: int
    record: dict[str, Any]


class EventBusReader:
    """Read-only tail/replay helper for the local file-bus."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def read(
        self,
        topic: str,
        *,
        partition: int = 0,
        from_offset: int = 0,
        max_records: int = 20,
    ) -> list[EbRecord]:
        if max_records <= 0:
            return []
        log_path = self._log_path(topic, partition)
        if not log_path.exists():
            return []
        records: list[EbRecord] = []
        with log_path.open("r", encoding="utf-8") as handle:
            for line_index, line in enumerate(handle):
                if line_index < from_offset:
                    continue
                if not line.strip():
                    continue
                payload = json.loads(line)
                records.append(
                    EbRecord(
                        topic=topic,
                        partition=partition,
                        offset=line_index,
                        record=payload,
                    )
                )
                if len(records) >= max_records:
                    break
        return records

    def iter_read(
        self,
        topic: str,
        *,
        partition: int = 0,
        from_offset: int = 0,
        max_records: int = 20,
    ) -> Iterable[EbRecord]:
        for record in self.read(
            topic,
            partition=partition,
            from_offset=from_offset,
            max_records=max_records,
        ):
            yield record

    def _log_path(self, topic: str, partition: int) -> Path:
        return self.root / topic / f"partition={partition}.jsonl"
