"""Typed state containers and authority helpers for S0 foundations."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import FrozenSet, Mapping, Optional, Tuple

import polars as pl

from ..exceptions import err
from .numeric import MathProfileManifest, NumericPolicy, NumericPolicyAttestation

_CHANNEL_SYMBOLS = {"CP", "CNP"}


@dataclass(frozen=True)
class SchemaRef:
    """Resolved schema reference with optional JSON pointer."""

    path: Path
    pointer: Tuple[str, ...] | None = None

    def load(self) -> object:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError as exc:  # pragma: no cover - guarded upstream
            raise err("E_SCHEMA_NOT_FOUND", f"schema '{self.path}' missing") from exc
        except json.JSONDecodeError as exc:
            raise err(
                "E_SCHEMA_FORMAT",
                f"schema '{self.path}' is not valid JSON: {exc.msg}",
            ) from exc

        if not self.pointer:
            return data

        node: object = data
        for token in self.pointer:
            if isinstance(node, dict) and token in node:
                node = node[token]
                continue
            raise err(
                "E_SCHEMA_POINTER",
                f"schema '{self.path}' missing json-pointer '/{'/'.join(self.pointer)}'",
            )
        return node


def _normalise_pointer(pointer: str) -> Tuple[str, ...]:
    if not pointer:
        return tuple()
    tokens = []
    for raw in pointer.lstrip("/").split("/"):
        if not raw:
            continue
        token = raw.replace("~1", "/").replace("~0", "~")
        tokens.append(token)
    return tuple(tokens)


@dataclass(frozen=True)
class SchemaAuthority:
    """Records the authoritative JSON-Schema anchors for S0."""

    ingress_ref: Optional[str]
    segment_ref: Optional[str]
    rng_ref: Optional[str]
    contracts_root: Path = Path("contracts/schemas")

    def validate(self) -> None:
        """Ensure referenced schemas exist, are JSON, and load cleanly."""

        for label, ref in (
            ("ingress", self.ingress_ref),
            ("segment", self.segment_ref),
            ("rng", self.rng_ref),
        ):
            if ref is None:
                continue
            schema_ref = self._resolve(ref)
            if schema_ref.path.suffix.lower() != ".json":
                raise err(
                    "E_AUTHORITY_BREACH",
                    f"{label} schema '{schema_ref.path.name}' must be JSON",
                )
            schema_ref.load()  # ensures JSON parses and pointer resolves

    def ingress_schema(self) -> SchemaRef:
        if self.ingress_ref is None:
            raise err("E_AUTHORITY_BREACH", "ingress schema reference is required")
        return self._resolve(self.ingress_ref)

    def _resolve(self, ref: str) -> SchemaRef:
        base, pointer = ref.split("#", 1) if "#" in ref else (ref, "")
        root = self.contracts_root.resolve()
        path = (self.contracts_root / base).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise err(
                "E_SCHEMA_NOT_FOUND",
                f"schema reference '{ref}' escapes contracts root {root}",
            ) from exc
        if not path.is_file():
            raise err("E_SCHEMA_NOT_FOUND", f"schema '{path}' not found")
        tokens = _normalise_pointer(pointer)
        return SchemaRef(path=path, pointer=tokens or None)


@dataclass(frozen=True)
class MerchantUniverse:
    """In-memory representation of the merchant ingress table."""

    table: pl.DataFrame

    def __post_init__(self) -> None:  # type: ignore[override]
        expected = {
            "merchant_id",
            "mcc",
            "channel_sym",
            "home_country_iso",
            "merchant_u64",
        }
        missing = expected - set(self.table.columns)
        if missing:
            raise err("E_INGRESS_SCHEMA", f"missing columns {sorted(missing)}")
        allowed_mask = self.table.get_column("channel_sym").is_in(
            sorted(_CHANNEL_SYMBOLS)
        )
        if not bool(allowed_mask.all()):
            bad_rows = (
                self.table.filter(
                    ~pl.col("channel_sym").is_in(sorted(_CHANNEL_SYMBOLS))
                )
                .select("merchant_id", "channel_sym")
                .to_dicts()
            )
            raise err("E_CHANNEL_VALUE", f"unexpected channel symbols {bad_rows}")

    @property
    def merchants(self) -> pl.DataFrame:
        return self.table


@dataclass(frozen=True)
class RunContext:
    """Immutable bundle handed from S0.1 into later states."""

    merchants: MerchantUniverse
    iso_countries: FrozenSet[str]
    gdp_per_capita: Mapping[str, float]
    gdp_bucket: Mapping[str, int]
    schema_authority: SchemaAuthority
    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    numeric_policy: Optional[NumericPolicy] = None
    math_profile: Optional[MathProfileManifest] = None
    numeric_attestation: Optional[NumericPolicyAttestation] = None

    def with_lineage(
        self,
        *,
        parameter_hash: Optional[str],
        manifest_fingerprint: Optional[str],
        numeric_policy: Optional[NumericPolicy] = None,
        math_profile: Optional[MathProfileManifest] = None,
        numeric_attestation: Optional[NumericPolicyAttestation] = None,
    ) -> "RunContext":
        if parameter_hash is None or manifest_fingerprint is None:
            raise err(
                "E_LINEAGE_INCOMPLETE",
                "parameter_hash and manifest_fingerprint required",
            )
        return replace(
            self,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            numeric_policy=numeric_policy or self.numeric_policy,
            math_profile=math_profile or self.math_profile,
            numeric_attestation=numeric_attestation or self.numeric_attestation,
        )


__all__ = ["SchemaAuthority", "SchemaRef", "MerchantUniverse", "RunContext"]
