"""Helpers for virtual-merchant classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Set

import polars as pl

from ..s0_gate.exceptions import err


def _normalize_mcc(value: object) -> str:
    """Return a zero-padded MCC string."""

    if isinstance(value, int):
        return f"{value:04d}"
    text = str(value).strip()
    if not text:
        raise err("E_VIRTUAL_RULES_MCC", "mcc value must not be empty")
    if not text.isdigit():
        raise err("E_VIRTUAL_RULES_MCC", f"mcc '{text}' must contain only digits")
    return text.zfill(4)


@dataclass(frozen=True)
class VirtualRules:
    """Parsed representation of the virtual merchant policy."""

    version_tag: str
    default_virtual: bool
    mcc_map: Mapping[str, bool]

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "VirtualRules":
        version = str(payload.get("version_tag") or "").strip()
        if not version:
            raise err("E_VIRTUAL_RULES_VERSION", "virtual_rules_policy_v1 missing version_tag")
        default_virtual = bool(payload.get("default_virtual", False))
        mapping: dict[str, bool] = {}
        for value in payload.get("virtual_mccs") or []:
            mapping[_normalize_mcc(value)] = True
        for entry in payload.get("mcc_overrides") or []:
            if not isinstance(entry, Mapping):
                continue
            mcc = _normalize_mcc(entry.get("mcc"))
            mapping[mcc] = bool(entry.get("virtual"))
        return cls(version_tag=version, default_virtual=default_virtual, mcc_map=mapping)

    def is_virtual_mcc(self, mcc: str) -> bool:
        """Return True if the supplied MCC is virtual according to the policy."""

        normalized = _normalize_mcc(mcc)
        return self.mcc_map.get(normalized, self.default_virtual)


class VirtualMerchantClassifier:
    """Builds a merchant→virtual flag map from MCC data and the policy."""

    def __init__(self, *, merchant_map_path: Path, rules: VirtualRules) -> None:
        if not merchant_map_path.exists():
            raise err(
                "E_VIRTUAL_MCC_MAP",
                f"merchant_mcc_map not found at '{merchant_map_path}'",
            )
        try:
            frame = pl.read_parquet(merchant_map_path, columns=["merchant_id", "mcc"])
        except Exception as exc:  # pragma: no cover - polars I/O failure
            raise err("E_VIRTUAL_MCC_MAP_IO", f"failed to read merchant_mcc_map: {exc}") from exc
        if frame.is_empty():
            raise err("E_VIRTUAL_MCC_MAP_EMPTY", "merchant_mcc_map has zero rows")
        try:
            merchant_ids = frame["merchant_id"].to_list()
            mccs = frame["mcc"].to_list()
        except Exception as exc:  # pragma: no cover - polars failure
            raise err("E_VIRTUAL_MCC_MAP_SCHEMA", f"merchant_mcc_map schema error: {exc}") from exc
        self._merchant_count = len(merchant_ids)
        virtual_ids: Set[int] = set()
        for merchant_id, mcc in zip(merchant_ids, mccs):
            try:
                merchant_key = int(merchant_id)
            except (TypeError, ValueError) as exc:
                raise err(
                    "E_VIRTUAL_MCC_MAP_TYPE",
                    f"merchant_id '{merchant_id}' is not an integer",
                ) from exc
            is_virtual = rules.is_virtual_mcc(str(mcc))
            if is_virtual:
                virtual_ids.add(merchant_key)
        self._virtual_ids = virtual_ids

    @property
    def merchants_total(self) -> int:
        return self._merchant_count

    @property
    def virtual_merchants_total(self) -> int:
        return len(self._virtual_ids)

    def is_virtual(self, merchant_id: int) -> bool:
        return merchant_id in self._virtual_ids


__all__ = ["VirtualMerchantClassifier", "VirtualRules"]
