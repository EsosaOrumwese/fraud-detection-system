"""Receipt and quarantine persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .store import ObjectStore


@dataclass
class ReceiptWriter:
    store: ObjectStore
    prefix: str

    def write_receipt(self, receipt_id: str, payload: dict[str, Any]) -> str:
        path = f"{self.prefix}/receipts/{receipt_id}.json"
        try:
            ref = self.store.write_json_if_absent(path, payload)
            return ref.path
        except FileExistsError:
            return path

    def write_quarantine(self, quarantine_id: str, payload: dict[str, Any]) -> str:
        path = f"{self.prefix}/quarantine/{quarantine_id}.json"
        try:
            ref = self.store.write_json_if_absent(path, payload)
            return ref.path
        except FileExistsError:
            return path
