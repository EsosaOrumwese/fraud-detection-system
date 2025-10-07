"""State-0 universe resolution for Layer-1 Segment 1A."""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

import polars as pl

from ..exceptions import err
from .context import MerchantUniverse, RunContext, SchemaAuthority

_CHANNEL_MAP = {
    "card_present": "CP",
    "card_not_present": "CNP",
}

_ALLOWED_CHANNELS = frozenset(_CHANNEL_MAP.values())
_EXPECTED_MERCHANT_COLUMNS = {"merchant_id", "mcc", "channel", "home_country_iso"}
_GDP_OBSERVATION_YEAR = 2024
_BUCKET_RANGE = range(1, 6)


def _map_channel(raw: Optional[str], merchant_id: int) -> str:
    if raw is None:
        raise err("E_CHANNEL_VALUE", f"merchant {merchant_id} missing channel value")
    if raw not in _CHANNEL_MAP:
        raise err("E_CHANNEL_VALUE", f"merchant {merchant_id} has unsupported channel '{raw}'")
    return _CHANNEL_MAP[raw]


def _validate_iso(value: Optional[str], merchant_id: int, iso_set: frozenset[str]) -> str:
    if value is None:
        raise err("E_FK_HOME_ISO", f"merchant {merchant_id} missing home_country_iso")
    if len(value) != 2 or not value.isascii() or value.upper() != value:
        raise err("E_FK_HOME_ISO", f"merchant {merchant_id} has non-uppercase ISO '{value}'")
    if value not in iso_set:
        raise err("E_FK_HOME_ISO", f"merchant {merchant_id} references unknown ISO '{value}'")
    return value


def _validate_mcc(value: Optional[int], merchant_id: int) -> int:
    if value is None:
        raise err("E_MCC_OUT_OF_DOMAIN", f"merchant {merchant_id} missing MCC")
    ivalue = int(value)
    if not (0 <= ivalue <= 9999):
        raise err("E_MCC_OUT_OF_DOMAIN", f"merchant {merchant_id} has MCC {ivalue}")
    return ivalue


def _compute_merchant_u64(merchant_id: int) -> int:
    if not (0 <= merchant_id < 2 ** 64):
        raise err("E_MERCHANT_ID_RANGE", f"merchant_id {merchant_id} outside [0, 2^64)")
    le_bytes = merchant_id.to_bytes(length=8, byteorder="little", signed=False)
    digest = hashlib.sha256(le_bytes).digest()
    low64 = digest[24:32]
    return int.from_bytes(low64, byteorder="little", signed=False)


def _ensure_columns(df: pl.DataFrame) -> None:
    missing = _EXPECTED_MERCHANT_COLUMNS - set(df.columns)
    if missing:
        raise err("E_INGRESS_SCHEMA", f"merchant ingress missing columns {sorted(missing)}")


def _iso_set(table: pl.DataFrame) -> frozenset[str]:
    if "country_iso" not in table.columns:
        raise err("E_ISO_TABLE_SCHEMA", "country_iso column missing in ISO reference")
    iso_series = table.get_column("country_iso")
    iso_values: List[str] = []
    for value in iso_series.to_list():
        if value is None:
            raise err("E_ISO_TABLE_SCHEMA", "null country_iso entry")
        if len(value) != 2 or not value.isascii() or value.upper() != value:
            raise err("E_ISO_TABLE_SCHEMA", f"country_iso '{value}' must be uppercase ASCII")
        iso_values.append(value)
    return frozenset(iso_values)


def _gdp_map(table: pl.DataFrame, iso_set: frozenset[str]) -> Dict[str, float]:
    required_cols = {"country_iso", "observation_year", "gdp_pc_usd_2015"}
    missing = required_cols - set(table.columns)
    if missing:
        raise err("E_GDP_SCHEMA", f"GDP table missing columns {sorted(missing)}")
    mapping: Dict[str, float] = {}
    for row in table.iter_rows(named=True):
        country = row["country_iso"]
        year = row["observation_year"]
        value = row["gdp_pc_usd_2015"]
        if country not in iso_set:
            raise err("E_GDP_ISO_FK", f"GDP row ISO '{country}' not in run ISO set")
        if int(year) != _GDP_OBSERVATION_YEAR:
            continue  # Only pin the configured observation year
        if value is None or not float(value) > 0.0:
            raise err("E_GDP_NONPOS", f"GDP value for {country} must be > 0")
        if country in mapping:
            raise err("E_GDP_DUP", f"duplicate GDP row for ISO '{country}' at year {_GDP_OBSERVATION_YEAR}")
        mapping[country] = float(value)
    missing_countries = iso_set - mapping.keys()
    if missing_countries:
        raise err("E_GDP_MISSING", f"no GDP row for ISO(s) {sorted(missing_countries)} in {_GDP_OBSERVATION_YEAR}")
    return mapping


def _bucket_map(table: pl.DataFrame, iso_set: frozenset[str]) -> Dict[str, int]:
    required_cols = {"country_iso", "bucket"}
    missing = required_cols - set(table.columns)
    if missing:
        raise err("E_BUCKET_SCHEMA", f"bucket table missing columns {sorted(missing)}")
    mapping: Dict[str, int] = {}
    for row in table.iter_rows(named=True):
        country = row["country_iso"]
        bucket = row["bucket"]
        if country not in iso_set:
            raise err("E_BUCKET_ISO_FK", f"bucket row ISO '{country}' not in run ISO set")
        ibucket = int(bucket)
        if ibucket not in _BUCKET_RANGE:
            raise err("E_BUCKET_RANGE", f"bucket for {country} must be in 1..5")
        if country in mapping:
            raise err("E_BUCKET_DUP", f"duplicate bucket row for ISO '{country}'")
        mapping[country] = ibucket
    missing_iso = iso_set - mapping.keys()
    if missing_iso:
        raise err("E_BUCKET_MISSING", f"no bucket mapping for ISO(s) {sorted(missing_iso)}")
    return mapping


def build_run_context(
    *,
    merchant_table: pl.DataFrame,
    iso_table: pl.DataFrame,
    gdp_table: pl.DataFrame,
    bucket_table: pl.DataFrame,
    schema_authority: SchemaAuthority,
) -> RunContext:
    """Resolve the immutable run context for S0."""

    schema_authority.validate()
    _ensure_columns(merchant_table)
    iso_set = _iso_set(iso_table)

    records: List[Dict[str, object]] = []
    for row in merchant_table.iter_rows(named=True):
        raw_id = row["merchant_id"]
        if raw_id is None:
            raise err("E_INGRESS_SCHEMA", "null merchant_id encountered")
        merchant_id = int(raw_id)
        mcc = _validate_mcc(row["mcc"], merchant_id)
        channel_sym = _map_channel(row["channel"], merchant_id)
        home_iso = _validate_iso(row["home_country_iso"], merchant_id, iso_set)
        merchant_u64 = _compute_merchant_u64(merchant_id)
        records.append(
            {
                "merchant_id": merchant_id,
                "mcc": mcc,
                "channel_sym": channel_sym,
                "home_country_iso": home_iso,
                "merchant_u64": merchant_u64,
            }
        )

    merchants_df = pl.DataFrame(records, schema={
        "merchant_id": pl.Int64,
        "mcc": pl.Int32,
        "channel_sym": pl.String,
        "home_country_iso": pl.String,
        "merchant_u64": pl.UInt64,
    })

    merchant_universe = MerchantUniverse(merchants_df)
    gdp_map = _gdp_map(gdp_table, iso_set)
    bucket_map = _bucket_map(bucket_table, iso_set)

    return RunContext(
        merchants=merchant_universe,
        iso_countries=iso_set,
        gdp_per_capita=gdp_map,
        gdp_bucket=bucket_map,
        schema_authority=schema_authority,
    )


__all__ = ["build_run_context"]
