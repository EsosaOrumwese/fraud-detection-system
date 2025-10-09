"""Design matrix construction utilities for the S0.4–S0.7 stages.

The fitting bundles ship frozen dictionaries and coefficient vectors; this
module converts those into strongly typed helpers that can build deterministic
design vectors, diagnostics, and parameter objects.  Keeping the logic here
means the orchestration layer stays declarative.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Mapping, Sequence, Tuple

import polars as pl

from ..exceptions import err
from .context import RunContext

_CHANNEL_ORDER = ("CP", "CNP")
_BUCKET_ORDER = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class DesignDictionaries:
    """Container storing the frozen categorical dictionaries used in models."""

    mcc: Tuple[int, ...]
    channel: Tuple[str, ...]
    gdp_bucket: Tuple[int, ...]

    @staticmethod
    def from_mapping(data: Mapping[str, Sequence]) -> "DesignDictionaries":
        """Construct dictionaries from a mapping typically loaded from YAML."""
        try:
            mcc = tuple(int(x) for x in data["mcc"])
            channel = tuple(str(x) for x in data["channel"])
            gdp_bucket = tuple(int(x) for x in data["gdp_bucket"])
        except KeyError as exc:  # pragma: no cover - configuration error
            raise err(
                "E_DSGN_DICT_MISSING", f"dictionary missing key {exc.args[0]}"
            ) from exc
        if channel != _CHANNEL_ORDER:
            raise err(
                "E_DSGN_UNKNOWN_CHANNEL", f"channel order must be {_CHANNEL_ORDER}"
            )
        if gdp_bucket != _BUCKET_ORDER:
            raise err(
                "E_DSGN_BUCKET_ORDER", f"GDP bucket order must be {_BUCKET_ORDER}"
            )
        if len(set(mcc)) != len(mcc):
            raise err("E_DSGN_DUP_MCC", "duplicate MCC entries in dictionary")
        return DesignDictionaries(mcc=mcc, channel=channel, gdp_bucket=gdp_bucket)

    def index_for_mcc(self, code: int) -> int:
        """Return the MCC index or raise a spec-aligned error."""
        try:
            return self.mcc.index(code)
        except ValueError as exc:
            raise err(
                "E_DSGN_UNKNOWN_MCC", f"MCC {code} missing from dictionary"
            ) from exc

    def index_for_channel(self, symbol: str) -> int:
        """Return the channel index or raise a spec-aligned error."""
        try:
            return self.channel.index(symbol)
        except ValueError as exc:  # pragma: no cover - guarded upstream
            raise err(
                "E_DSGN_UNKNOWN_CHANNEL", f"channel {symbol} missing from dictionary"
            ) from exc

    def index_for_bucket(self, bucket: int) -> int:
        """Return the GDP bucket index or raise if the bucket is unknown."""
        try:
            return self.gdp_bucket.index(bucket)
        except ValueError as exc:
            raise err(
                "E_DSGN_DOMAIN_BUCKET", f"bucket {bucket} not in dictionary"
            ) from exc


@dataclass(frozen=True)
class HurdleCoefficients:
    """Typed container for hurdle logistic coefficients."""

    dictionaries: DesignDictionaries
    beta: Tuple[float, ...]
    beta_mu: Tuple[float, ...]


@dataclass(frozen=True)
class DispersionCoefficients:
    """Typed container for negative-binomial dispersion coefficients."""

    dictionaries: DesignDictionaries
    beta_phi: Tuple[float, ...]


@dataclass(frozen=True)
class DesignVectors:
    """Immutable record describing the precomputed vectors per merchant."""

    merchant_id: int
    bucket: int
    gdp: float
    log_gdp: float
    x_hurdle: Tuple[float, ...]
    x_nb_mean: Tuple[float, ...]
    x_nb_dispersion: Tuple[float, ...]


def _ensure_finite(sequence: Sequence[float], *, error_code: str) -> Tuple[float, ...]:
    """Convert ``sequence`` to floats and ensure every element is finite."""
    values: List[float] = []
    for value in sequence:
        f = float(value)
        if not math.isfinite(f):
            raise err(error_code, f"non-finite coefficient {value}")
        values.append(f)
    return tuple(values)


def load_hurdle_coefficients(data: Mapping[str, object]) -> HurdleCoefficients:
    """Load hurdle coefficients from a decoded YAML mapping."""
    dicts = DesignDictionaries.from_mapping(data.get("dicts", {}))
    beta = data.get("beta")
    beta_mu = data.get("beta_mu")
    if not isinstance(beta, Sequence):
        raise err("E_DSGN_SCHEMA", "beta must be a sequence")
    if not isinstance(beta_mu, Sequence):
        raise err("E_DSGN_SCHEMA", "beta_mu must be a sequence")
    expected_beta_len = 1 + len(dicts.mcc) + len(dicts.channel) + len(dicts.gdp_bucket)
    expected_beta_mu_len = 1 + len(dicts.mcc) + len(dicts.channel)
    if len(beta) != expected_beta_len:
        raise err(
            "E_DSGN_SHAPE_MISMATCH",
            f"beta expected length {expected_beta_len}, got {len(beta)}",
        )
    if len(beta_mu) != expected_beta_mu_len:
        raise err(
            "E_DSGN_SHAPE_MISMATCH",
            f"beta_mu expected length {expected_beta_mu_len}, got {len(beta_mu)}",
        )
    beta_tuple = _ensure_finite(beta, error_code="E_DSGN_NONFINITE")
    beta_mu_tuple = _ensure_finite(beta_mu, error_code="E_DSGN_NONFINITE")
    return HurdleCoefficients(
        dictionaries=dicts, beta=beta_tuple, beta_mu=beta_mu_tuple
    )


def load_dispersion_coefficients(
    data: Mapping[str, object], *, reference: DesignDictionaries
) -> DispersionCoefficients:
    """Load dispersion coefficients, enforcing dictionary alignment."""
    dicts_data = data.get("dicts", {})
    dicts = DesignDictionaries(
        mcc=tuple(int(x) for x in dicts_data.get("mcc", [])) or reference.mcc,
        channel=tuple(str(x) for x in dicts_data.get("channel", []))
        or reference.channel,
        gdp_bucket=reference.gdp_bucket,
    )
    if dicts.mcc != reference.mcc:
        raise err(
            "E_DSGN_DICT_MISMATCH",
            "dispersion MCC dictionary must match hurdle dictionary",
        )
    if dicts.channel != reference.channel:
        raise err(
            "E_DSGN_DICT_MISMATCH",
            "dispersion channel dictionary must match hurdle dictionary",
        )
    beta_phi = data.get("beta_phi")
    if not isinstance(beta_phi, Sequence):
        raise err("E_DSGN_SCHEMA", "beta_phi must be a sequence")
    expected_len = 1 + len(dicts.mcc) + len(dicts.channel) + 1
    if len(beta_phi) != expected_len:
        raise err(
            "E_DSGN_SHAPE_MISMATCH",
            f"beta_phi expected length {expected_len}, got {len(beta_phi)}",
        )
    beta_phi_tuple = _ensure_finite(beta_phi, error_code="E_DSGN_NONFINITE")
    return DispersionCoefficients(dictionaries=dicts, beta_phi=beta_phi_tuple)


def _one_hot(index: int, size: int) -> List[float]:
    vector = [0.0] * size
    vector[index] = 1.0
    return vector


def iter_design_vectors(
    context: RunContext,
    *,
    hurdle: HurdleCoefficients,
    dispersion: DispersionCoefficients,
) -> Iterator[DesignVectors]:
    """Yield deterministic design vectors for each merchant in ``context``."""
    dicts = hurdle.dictionaries
    if (
        dispersion.dictionaries.mcc != dicts.mcc
        or dispersion.dictionaries.channel != dicts.channel
    ):
        raise err(
            "E_DSGN_DICT_MISMATCH",
            "dispersion dictionaries must align with hurdle dictionaries",
        )
    mcc_size = len(dicts.mcc)
    channel_size = len(dicts.channel)
    bucket_size = len(dicts.gdp_bucket)
    for row in context.merchants.merchants.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        mcc = int(row["mcc"])
        channel = str(row["channel_sym"])
        iso = str(row["home_country_iso"])
        g = context.gdp_per_capita[iso]
        if not g > 0.0:
            raise err("E_DSGN_DOMAIN_GDP", f"GDP for {iso} must be > 0")
        bucket = context.gdp_bucket[iso]
        if bucket not in dicts.gdp_bucket:
            raise err("E_DSGN_DOMAIN_BUCKET", f"bucket {bucket} not in dictionary")
        log_g = math.log(g)
        mcc_index = dicts.index_for_mcc(mcc)
        channel_index = dicts.index_for_channel(channel)
        bucket_index = dicts.index_for_bucket(bucket)

        hurdle_vec: List[float] = [1.0]
        hurdle_vec.extend(_one_hot(mcc_index, mcc_size))
        hurdle_vec.extend(_one_hot(channel_index, channel_size))
        hurdle_vec.extend(_one_hot(bucket_index, bucket_size))

        nb_mean_vec: List[float] = [1.0]
        nb_mean_vec.extend(_one_hot(mcc_index, mcc_size))
        nb_mean_vec.extend(_one_hot(channel_index, channel_size))

        nb_phi_vec: List[float] = [1.0]
        nb_phi_vec.extend(_one_hot(mcc_index, mcc_size))
        nb_phi_vec.extend(_one_hot(channel_index, channel_size))
        nb_phi_vec.append(log_g)

        yield DesignVectors(
            merchant_id=merchant_id,
            bucket=bucket,
            gdp=g,
            log_gdp=log_g,
            x_hurdle=tuple(hurdle_vec),
            x_nb_mean=tuple(nb_mean_vec),
            x_nb_dispersion=tuple(nb_phi_vec),
        )


def design_dataframe(vectors: Iterable[DesignVectors]) -> pl.DataFrame:
    """Materialise an iterable of design vectors into a Polars DataFrame."""
    rows = []
    for vector in vectors:
        rows.append(
            {
                "merchant_id": vector.merchant_id,
                "bucket": vector.bucket,
                "gdp_pc_usd_2015": vector.gdp,
                "log_gdp_pc_usd_2015": vector.log_gdp,
                "x_hurdle": vector.x_hurdle,
                "x_nb_mean": vector.x_nb_mean,
                "x_nb_dispersion": vector.x_nb_dispersion,
            }
        )
    return pl.from_dicts(
        rows,
        schema_overrides={
            "merchant_id": pl.UInt64,
            "bucket": pl.UInt8,
            "gdp_pc_usd_2015": pl.Float64,
            "log_gdp_pc_usd_2015": pl.Float64,
        },
    )


__all__ = [
    "DesignDictionaries",
    "HurdleCoefficients",
    "DispersionCoefficients",
    "DesignVectors",
    "load_hurdle_coefficients",
    "load_dispersion_coefficients",
    "iter_design_vectors",
    "design_dataframe",
]
