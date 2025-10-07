"""Typed state containers for S0 foundations."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import FrozenSet, Mapping, Optional

import polars as pl

from ..exceptions import err
from .numeric import MathProfileManifest, NumericPolicy, NumericPolicyAttestation

_CHANNEL_SYMBOLS = {"CP", "CNP"}


@dataclass(frozen=True)
class SchemaAuthority:
    """Records the authoritative JSON-Schema anchors for S0."""

    ingress_ref: str
    segment_ref: str
    rng_ref: str

    def validate(self) -> None:
        for ref in (self.ingress_ref, self.segment_ref, self.rng_ref):
            base = ref.split("#", 1)[0]
            if not base.endswith(".yaml"):
                raise err("E_AUTHORITY_BREACH", f"non YAML schema ref '{ref}'")


@dataclass(frozen=True)
class MerchantUniverse:
    """In-memory representation of the merchant ingress table."""

    table: pl.DataFrame

    def __post_init__(self) -> None:  # type: ignore[override]
        expected = {"merchant_id", "mcc", "channel_sym", "home_country_iso", "merchant_u64"}
        missing = expected - set(self.table.columns)
        if missing:
            raise err("E_INGRESS_SCHEMA", f"missing columns {sorted(missing)}")
        allowed_mask = self.table.get_column("channel_sym").is_in(sorted(_CHANNEL_SYMBOLS))
        if not bool(allowed_mask.all()):
            bad_rows = (
                self.table
                .filter(~pl.col("channel_sym").is_in(sorted(_CHANNEL_SYMBOLS)))
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
            raise err("E_LINEAGE_INCOMPLETE", "parameter_hash and manifest_fingerprint required")
        return replace(
            self,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            numeric_policy=numeric_policy or self.numeric_policy,
            math_profile=math_profile or self.math_profile,
            numeric_attestation=numeric_attestation or self.numeric_attestation,
        )


__all__ = ["SchemaAuthority", "MerchantUniverse", "RunContext"]
