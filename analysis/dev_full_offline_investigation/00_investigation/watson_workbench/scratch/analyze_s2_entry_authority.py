from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import yaml


ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
MANIFEST_FINGERPRINT = "76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460"
PARAMETER_HASH = "0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00"
SEED = "42"
RUN_ID = "a3bd8cac9a4284cd36072c6b9624a0c1"


def load_jsonl(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def normalize_channel(value: str) -> str:
    return {
        "card_present": "CP",
        "card_not_present": "CNP",
    }.get(value, value)


def main() -> None:
    hurdle_event_path = (
        RUN_ROOT
        / "logs"
        / "layer1"
        / "1A"
        / "rng"
        / "events"
        / "hurdle_bernoulli"
        / f"seed={SEED}"
        / f"parameter_hash={PARAMETER_HASH}"
        / f"run_id={RUN_ID}"
        / "part-00000.jsonl"
    )
    gamma_event_path = (
        RUN_ROOT
        / "logs"
        / "layer1"
        / "1A"
        / "rng"
        / "events"
        / "gamma_component"
        / f"seed={SEED}"
        / f"parameter_hash={PARAMETER_HASH}"
        / f"run_id={RUN_ID}"
        / "part-00000.jsonl"
    )
    poisson_event_path = (
        RUN_ROOT
        / "logs"
        / "layer1"
        / "1A"
        / "rng"
        / "events"
        / "poisson_component"
        / f"seed={SEED}"
        / f"parameter_hash={PARAMETER_HASH}"
        / f"run_id={RUN_ID}"
        / "part-00000.jsonl"
    )
    nb_final_path = (
        RUN_ROOT
        / "logs"
        / "layer1"
        / "1A"
        / "rng"
        / "events"
        / "nb_final"
        / f"seed={SEED}"
        / f"parameter_hash={PARAMETER_HASH}"
        / f"run_id={RUN_ID}"
        / "part-00000.jsonl"
    )
    sealed_inputs_path = (
        RUN_ROOT
        / "data"
        / "layer1"
        / "1A"
        / "sealed_inputs"
        / f"manifest_fingerprint={MANIFEST_FINGERPRINT}"
        / "sealed_inputs_1A.json"
    )
    merchant_path = (
        ROOT
        / "reference"
        / "layer1"
        / "transaction_schema_merchant_ids"
        / "2026-01-03"
        / "transaction_schema_merchant_ids.parquet"
    )
    gdp_path = (
        ROOT
        / "reference"
        / "economic"
        / "world_bank_gdp_per_capita"
        / "2025-04-15"
        / "gdp.parquet"
    )
    hurdle_coefficients_path = (
        ROOT
        / "config"
        / "layer1"
        / "1A"
        / "models"
        / "hurdle"
        / "exports"
        / "version=2026-02-14"
        / "20260214T173000Z"
        / "hurdle_coefficients.yaml"
    )
    nb_dispersion_coefficients_path = (
        ROOT
        / "config"
        / "layer1"
        / "1A"
        / "models"
        / "hurdle"
        / "exports"
        / "version=2026-02-14"
        / "20260214T173000Z"
        / "nb_dispersion_coefficients.yaml"
    )

    hurdle_df = load_jsonl(hurdle_event_path)
    gamma_df = load_jsonl(gamma_event_path)
    poisson_df = load_jsonl(poisson_event_path)
    nb_final_df = load_jsonl(nb_final_path)
    sealed_inputs = json.loads(sealed_inputs_path.read_text(encoding="utf-8"))
    merchant_df = pl.read_parquet(merchant_path).to_pandas()
    gdp_df = pl.read_parquet(gdp_path).to_pandas()
    hurdle_coefficients = yaml.safe_load(hurdle_coefficients_path.read_text(encoding="utf-8"))
    nb_dispersion_coefficients = yaml.safe_load(nb_dispersion_coefficients_path.read_text(encoding="utf-8"))

    merchant_df["channel_sym"] = merchant_df["channel"].map(normalize_channel)

    joined_df = (
        nb_final_df[["merchant_id", "mu", "dispersion_k", "n_outlets", "nb_rejections"]]
        .merge(
            merchant_df[["merchant_id", "mcc", "channel_sym", "home_country_iso"]],
            on="merchant_id",
            how="left",
        )
        .merge(
            gdp_df[["country_iso", "gdp_pc_usd_2015"]],
            left_on="home_country_iso",
            right_on="country_iso",
            how="left",
        )
    )

    beta_mu = np.array(hurdle_coefficients["beta_mu"], dtype=float)
    beta_phi = np.array(nb_dispersion_coefficients["beta_phi"], dtype=float)
    dict_mcc_mu = [int(value) for value in hurdle_coefficients["dict_mcc"]]
    dict_ch_mu = list(hurdle_coefficients["dict_ch"])
    dict_mcc_phi = [int(value) for value in nb_dispersion_coefficients["dict_mcc"]]
    dict_ch_phi = list(nb_dispersion_coefficients["dict_ch"])

    mcc_terms_mu = {mcc: beta_mu[1 + idx] for idx, mcc in enumerate(dict_mcc_mu)}
    channel_terms_mu = {
        channel: beta_mu[1 + len(dict_mcc_mu) + idx] for idx, channel in enumerate(dict_ch_mu)
    }
    joined_df["mu_recomputed"] = np.exp(
        beta_mu[0]
        + joined_df["mcc"].map(mcc_terms_mu).astype(float)
        + joined_df["channel_sym"].map(channel_terms_mu).astype(float)
    )

    mcc_terms_phi = {mcc: beta_phi[1 + idx] for idx, mcc in enumerate(dict_mcc_phi)}
    channel_terms_phi = {
        channel: beta_phi[1 + len(dict_mcc_phi) + idx] for idx, channel in enumerate(dict_ch_phi)
    }
    joined_df["phi_recomputed"] = np.exp(
        beta_phi[0]
        + joined_df["mcc"].map(mcc_terms_phi).astype(float)
        + joined_df["channel_sym"].map(channel_terms_phi).astype(float)
        + beta_phi[-1] * np.log(joined_df["gdp_pc_usd_2015"].astype(float))
    )

    joined_df["mu_abs_diff"] = (joined_df["mu"] - joined_df["mu_recomputed"]).abs()
    joined_df["phi_abs_diff"] = (joined_df["dispersion_k"] - joined_df["phi_recomputed"]).abs()

    hurdle_multi_df = hurdle_df.loc[hurdle_df["is_multi"], ["merchant_id", "pi"]].rename(
        columns={"pi": "s1_pi"}
    )
    entry_df = joined_df.merge(hurdle_multi_df, on="merchant_id", how="left")
    entry_df["ln_gdp_pc"] = np.log(entry_df["gdp_pc_usd_2015"].astype(float))

    print("SEALED INPUTS")
    for row in sealed_inputs:
        asset_id = row.get("asset_id")
        path = row.get("path")
        if asset_id in {
            "hurdle_coefficients.yaml",
            "nb_dispersion_coefficients.yaml",
            "transaction_schema_merchant_ids",
            "world_bank_gdp_per_capita_20250415",
        }:
            print(f"{asset_id}: {path}")

    print("\nENTRY COUNTS")
    print("hurdle rows:", len(hurdle_df))
    print("multi merchants:", int(hurdle_df["is_multi"].sum()))
    print("single merchants:", int((~hurdle_df["is_multi"]).sum()))
    print("gamma rows / merchants:", len(gamma_df), gamma_df["merchant_id"].nunique())
    print("poisson rows / merchants:", len(poisson_df), poisson_df["merchant_id"].nunique())
    print("nb_final rows / merchants:", len(nb_final_df), nb_final_df["merchant_id"].nunique())

    hurdle_multi = set(hurdle_df.loc[hurdle_df["is_multi"], "merchant_id"])
    hurdle_single = set(hurdle_df.loc[~hurdle_df["is_multi"], "merchant_id"])
    gamma_merchants = set(gamma_df["merchant_id"])
    poisson_merchants = set(poisson_df["merchant_id"])
    nb_final_merchants = set(nb_final_df["merchant_id"])

    print("\nBRANCH PURITY")
    print("gamma on singles:", len(gamma_merchants & hurdle_single))
    print("poisson on singles:", len(poisson_merchants & hurdle_single))
    print("nb_final on singles:", len(nb_final_merchants & hurdle_single))
    print("multi missing gamma:", len(hurdle_multi - gamma_merchants))
    print("multi missing poisson:", len(hurdle_multi - poisson_merchants))
    print("multi missing nb_final:", len(hurdle_multi - nb_final_merchants))

    print("\nRECOMPUTATION CHECK")
    print("mu abs diff mean/max:", joined_df["mu_abs_diff"].mean(), joined_df["mu_abs_diff"].max())
    print(
        "phi abs diff mean/max:",
        joined_df["phi_abs_diff"].mean(),
        joined_df["phi_abs_diff"].max(),
    )

    print("\nPARAMETER SUMMARIES")
    print("mu summary")
    print(joined_df["mu"].describe().to_string())
    print("\nphi summary")
    print(joined_df["dispersion_k"].describe().to_string())
    print("\nn_outlets summary")
    print(joined_df["n_outlets"].describe().to_string())
    print("\nnb_rejections distribution")
    print(joined_df["nb_rejections"].value_counts().sort_index().to_string())

    print("\nAUTHORITY STRUCTURE")
    print("beta_mu len:", len(beta_mu))
    print("beta_phi len:", len(beta_phi))
    print("mu intercept:", float(beta_mu[0]))
    print("phi intercept:", float(beta_phi[0]))
    print("mu channel terms:", channel_terms_mu)
    print("phi channel terms:", channel_terms_phi)
    print("phi ln_gdp coefficient:", float(beta_phi[-1]))

    print("\nENTRY POPULATION")
    print(entry_df["s1_pi"].describe().to_string())
    print("\nBy channel")
    print(
        entry_df.groupby("channel_sym")
        .agg(
            merchants=("merchant_id", "size"),
            mean_s1_pi=("s1_pi", "mean"),
            mean_mu=("mu", "mean"),
            mean_phi=("dispersion_k", "mean"),
            mean_n=("n_outlets", "mean"),
        )
        .to_string()
    )


if __name__ == "__main__":
    main()
