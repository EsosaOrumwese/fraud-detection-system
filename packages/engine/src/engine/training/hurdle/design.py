"""Design matrix construction for hurdle/NB fitting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Sequence

import numpy as np
import polars as pl

from .simulator import SimulatedHurdleCorpus


@dataclass(frozen=True)
class DesignDictionaries:
    mcc: Sequence[int]
    channel: Sequence[str]
    gdp_bucket: Sequence[int]


@dataclass(frozen=True)
class DesignMatrices:
    x_hurdle: np.ndarray
    y_hurdle: np.ndarray
    x_nb_mean: np.ndarray
    y_nb: np.ndarray
    x_dispersion: np.ndarray
    dictionaries: DesignDictionaries
    hurdle_brand_ids: Sequence[str]
    nb_brand_ids: Sequence[str]


def _default_dicts(logistic: pl.DataFrame) -> DesignDictionaries:
    mcc = sorted(int(x) for x in logistic["mcc"].unique().to_list())
    channel = [value for value in ["CP", "CNP"] if value in set(logistic["channel"].unique())]
    bucket = sorted(int(x) for x in logistic["gdp_bucket"].unique().to_list())
    return DesignDictionaries(mcc=mcc, channel=channel, gdp_bucket=bucket)


def _lookup_by_brand(
    logistic: pl.DataFrame,
) -> Dict[str, Dict[str, object]]:
    lookup = {}
    for row in logistic.select(
        ["brand_id", "gdp_bucket", "ln_gdp_pc_usd_2015"]
    ).unique(subset=["brand_id"]).iter_rows(named=True):
        lookup[str(row["brand_id"])] = {
            "gdp_bucket": int(row["gdp_bucket"]),
            "ln_gdp": float(row["ln_gdp_pc_usd_2015"]),
        }
    return lookup


def build_design_matrices(
    corpus: SimulatedHurdleCorpus,
    dictionaries: DesignDictionaries | None = None,
) -> DesignMatrices:
    logistic = corpus.logistic
    nb_mean_df = corpus.nb_mean

    dicts = dictionaries or _default_dicts(logistic)

    mcc_index = {code: idx for idx, code in enumerate(dicts.mcc)}
    channel_index = {channel: idx for idx, channel in enumerate(dicts.channel)}
    bucket_index = {bucket: idx for idx, bucket in enumerate(dicts.gdp_bucket)}

    # Hurdle design
    n_hurdle = logistic.height
    cols_hurdle = 1 + len(dicts.mcc) + len(dicts.channel) + len(dicts.gdp_bucket)
    x_hurdle = np.zeros((n_hurdle, cols_hurdle), dtype=np.float64)
    y_hurdle = logistic["is_multi"].cast(pl.Int8).to_numpy().astype(np.float64)

    hurdle_brand_ids = logistic["brand_id"].to_list()

    for row_idx, row in enumerate(logistic.iter_rows(named=True)):
        x_hurdle[row_idx, 0] = 1.0
        x_hurdle[row_idx, 1 + mcc_index[int(row["mcc"])]] = 1.0
        channel_offset = 1 + len(dicts.mcc)
        if row["channel"] in channel_index:
            x_hurdle[row_idx, channel_offset + channel_index[row["channel"]]] = 1.0
        bucket_offset = channel_offset + len(dicts.channel)
        x_hurdle[row_idx, bucket_offset + bucket_index[int(row["gdp_bucket"])]] = 1.0

    # NB mean design
    n_nb = nb_mean_df.height
    cols_nb = 1 + len(dicts.mcc) + len(dicts.channel)
    x_nb_mean = np.zeros((n_nb, cols_nb), dtype=np.float64)
    y_nb = nb_mean_df["k_domestic"].cast(pl.Float64).to_numpy()

    brand_lookup = _lookup_by_brand(logistic)
    nb_brand_ids = nb_mean_df["brand_id"].to_list()

    for row_idx, row in enumerate(nb_mean_df.iter_rows(named=True)):
        x_nb_mean[row_idx, 0] = 1.0
        x_nb_mean[row_idx, 1 + mcc_index[int(row["mcc"])]] = 1.0
        channel_offset = 1 + len(dicts.mcc)
        if row["channel"] in channel_index:
            x_nb_mean[row_idx, channel_offset + channel_index[row["channel"]]] = 1.0

    # Dispersion design
    cols_disp = 1 + len(dicts.mcc) + len(dicts.channel) + 1  # ln_gdp term
    x_dispersion = np.zeros((n_nb, cols_disp), dtype=np.float64)
    for row_idx, row in enumerate(nb_mean_df.iter_rows(named=True)):
        x_dispersion[row_idx, 0] = 1.0
        x_dispersion[row_idx, 1 + mcc_index[int(row["mcc"])]] = 1.0
        channel_offset = 1 + len(dicts.mcc)
        if row["channel"] in channel_index:
            x_dispersion[row_idx, channel_offset + channel_index[row["channel"]]] = 1.0
        bucket_info = brand_lookup[str(row["brand_id"])]
        ln_gdp = float(bucket_info["ln_gdp"])
        x_dispersion[row_idx, channel_offset + len(dicts.channel)] = ln_gdp

    return DesignMatrices(
        x_hurdle=x_hurdle,
        y_hurdle=y_hurdle,
        x_nb_mean=x_nb_mean,
        y_nb=y_nb,
        x_dispersion=x_dispersion,
        dictionaries=dicts,
        hurdle_brand_ids=hurdle_brand_ids,
        nb_brand_ids=nb_brand_ids,
    )
