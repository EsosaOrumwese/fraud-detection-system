"""Synthetic corpus builder for hurdle/NB training."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import polars as pl

from .config import SimulationConfig
from .universe import MerchantUniverseSources, load_enriched_universe


@dataclass(frozen=True)
class SimulatedHurdleCorpus:
    logistic: pl.DataFrame
    nb_mean: pl.DataFrame
    brand_aliases: pl.DataFrame
    channel_roster: pl.DataFrame

    def summary(self) -> dict[str, float]:
        multi_rate = float(self.logistic["is_multi"].mean())
        avg_mu = (
            float(self.nb_mean["k_domestic"].mean())
            if self.nb_mean.height > 0
            else 0.0
        )
        return {
            "rows_logistic": float(self.logistic.height),
            "rows_nb": float(self.nb_mean.height),
            "overall_multi_rate": multi_rate,
            "avg_k_domestic": avg_mu,
        }


def simulate_hurdle_corpus(
    *,
    sources: MerchantUniverseSources,
    config: SimulationConfig,
) -> SimulatedHurdleCorpus:
    """Generate synthetic training frames for the hurdle model."""

    universe = load_enriched_universe(sources)
    universe = universe.sort(["country_iso", "mcc", "merchant_id"])

    rng = np.random.default_rng(config.rng.seed)

    brand_ids = _build_brand_ids(universe["merchant_id"])
    channels = universe["channel"].to_list()
    gdp_bucket = universe["gdp_bucket"].to_list()
    ln_gdp = universe["ln_gdp_pc_usd_2015"].to_numpy()
    mcc_codes = universe["mcc"].to_list()
    countries = universe["country_iso"].to_list()

    eta = _compute_hurdle_eta(
        config=config,
        channels=channels,
        buckets=gdp_bucket,
        mcc_codes=mcc_codes,
        rng=rng,
    )
    probs = 1.0 / (1.0 + np.exp(-eta))
    draws = rng.uniform(size=len(probs))
    is_multi = draws < probs

    mu = _compute_nb_mean(
        config=config,
        channels=channels,
        mcc_codes=mcc_codes,
        rng=rng,
    )
    phi = _compute_dispersion(
        config=config,
        channels=channels,
        mcc_codes=mcc_codes,
        ln_gdp=ln_gdp,
        rng=rng,
    )

    k_domestic = np.zeros(len(mu), dtype=np.int32)
    for idx, flag in enumerate(is_multi):
        if not flag:
            continue
        sampled = _sample_zero_truncated_nb(rng, mu[idx], phi[idx])
        k_domestic[idx] = sampled

    logistic_df = pl.DataFrame(
        {
            "brand_id": brand_ids,
            "country_iso": countries,
            "mcc": mcc_codes,
            "channel": channels,
            "gdp_bucket": gdp_bucket,
            "is_multi": is_multi,
        }
    )

    nb_df = pl.DataFrame(
        {
            "brand_id": brand_ids,
            "country_iso": countries,
            "mcc": mcc_codes,
            "channel": channels,
            "k_domestic": k_domestic,
        }
    ).filter(pl.col("k_domestic") > 0)

    alias_df = pl.DataFrame(
        {
            "brand_id": brand_ids,
            "merchant_id": universe["merchant_id"],
        }
    )

    channel_roster = (
        pl.DataFrame(
            {
                "brand_id": brand_ids,
                "channel": channels,
            }
        )
        .unique()
        .with_columns(
            pl.when(pl.col("channel") == "CNP")
            .then(pl.lit("SIMULATED_CNP"))
            .otherwise(pl.lit("SIMULATED_CP"))
            .alias("evidence")
        )
    )

    return SimulatedHurdleCorpus(
        logistic=logistic_df,
        nb_mean=nb_df,
        brand_aliases=alias_df,
        channel_roster=channel_roster,
    )


def _build_brand_ids(merchant_ids: pl.Series) -> list[str]:
    brand_ids: list[str] = []
    for idx, value in enumerate(merchant_ids):
        if value is None:
            base = idx
        else:
            base = int(value)
        brand_ids.append(f"SIM_BRAND_{base}")
    return brand_ids


def _compute_hurdle_eta(
    *,
    config: SimulationConfig,
    channels: list[str],
    buckets: list[int],
    mcc_codes: list[int],
    rng: np.random.Generator,
) -> np.ndarray:
    base = config.hurdle.base_logit
    noise = rng.normal(loc=0.0, scale=0.35, size=len(channels))
    eta = np.full(len(channels), base, dtype=float)
    eta += np.array([config.hurdle.channel_offset(ch) for ch in channels])
    eta += np.array([config.hurdle.bucket_offset(int(b)) for b in buckets])
    eta += np.array([config.hurdle.mcc_offset(int(code)) for code in mcc_codes])
    eta += noise
    return eta


def _compute_nb_mean(
    *,
    config: SimulationConfig,
    channels: list[str],
    mcc_codes: list[int],
    rng: np.random.Generator,
) -> np.ndarray:
    base = config.nb_mean.base_log_mean
    noise = rng.normal(loc=0.0, scale=0.25, size=len(channels))
    log_mu = np.full(len(channels), base, dtype=float)
    log_mu += np.array([config.nb_mean.channel_offset(ch) for ch in channels])
    log_mu += np.array([config.nb_mean.mcc_offset(int(code)) for code in mcc_codes])
    log_mu += noise
    return np.exp(log_mu).clip(min=1.2)


def _compute_dispersion(
    *,
    config: SimulationConfig,
    channels: list[str],
    mcc_codes: list[int],
    ln_gdp: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    base = config.dispersion.base_log_phi
    noise = rng.normal(loc=0.0, scale=0.1, size=len(channels))
    log_phi = np.full(len(channels), base, dtype=float)
    log_phi += config.dispersion.gdp_log_slope * ln_gdp
    log_phi += np.array([config.dispersion.channel_offset(ch) for ch in channels])
    log_phi += np.array([config.dispersion.mcc_offset(int(code)) for code in mcc_codes])
    log_phi += noise
    return np.exp(log_phi).clip(min=0.05, max=5.0)


def _sample_zero_truncated_nb(
    rng: np.random.Generator,
    mean: float,
    dispersion: float,
) -> int:
    mean = max(mean, 1.0)
    dispersion = max(dispersion, 1e-3)
    shape = 1.0 / dispersion
    prob = shape / (shape + mean)
    for _ in range(16):
        value = rng.negative_binomial(shape, prob)
        if value >= 2:
            return int(value)
    return 2
