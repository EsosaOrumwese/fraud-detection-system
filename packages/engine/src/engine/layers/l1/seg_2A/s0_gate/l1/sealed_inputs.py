"""Dataclasses describing the sealed inputs manifest for 2A S0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..exceptions import err, S0GateError


@dataclass(frozen=True)
class SealedInput:
    """Lightweight view of a sealed asset recorded in the receipt."""

    asset_id: str
    schema_ref: str
    partition_keys: tuple[str, ...] = field(default_factory=tuple)

    def require_non_empty(self) -> None:
        """Ensure the asset identity is populated."""

        if not self.asset_id:
            raise err("E_ASSET_ID_MISSING", "sealed input asset_id must be non-empty")


def normalise_inputs(inputs: Iterable[SealedInput]) -> list[SealedInput]:
    """Return a list that enforces the most basic invariants.

    Later phases will enrich this with dictionary lookups and digest capture.
    """

    result: list[SealedInput] = []
    seen: set[str] = set()
    for item in inputs:
        item.require_non_empty()
        if item.asset_id in seen:
            raise err("E_ASSET_DUPLICATE", f"duplicate sealed input '{item.asset_id}'")
        seen.add(item.asset_id)
        result.append(item)
    return result


__all__ = ["SealedInput", "normalise_inputs", "S0GateError"]
