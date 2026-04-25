from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import yaml


ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
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
    nb_final_df = load_jsonl(nb_final_path)
    merchant_df = pl.read_parquet(merchant_path).to_pandas()
    gdp_df = pl.read_parquet(gdp_path).to_pandas()
    hurdle_coefficients = yaml.safe_load(hurdle_coefficients_path.read_text(encoding="utf-8"))
    nb_dispersion_coefficients = yaml.safe_load(
        nb_dispersion_coefficients_path.read_text(encoding="utf-8")
    )

    merchant_df["channel_sym"] = merchant_df["channel"].map(normalize_channel)
    entry_df = (
        nb_final_df[["merchant_id", "mu", "dispersion_k", "n_outlets", "nb_rejections"]]
        .merge(
            hurdle_df.loc[hurdle_df["is_multi"], ["merchant_id", "pi"]].rename(
                columns={"pi": "s1_pi"}
            ),
            on="merchant_id",
            how="left",
        )
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
    entry_df["ln_gdp_pc"] = np.log(entry_df["gdp_pc_usd_2015"].astype(float))

    beta_mu = np.array(hurdle_coefficients["beta_mu"], dtype=float)
    beta_phi = np.array(nb_dispersion_coefficients["beta_phi"], dtype=float)

    mu_mcc_terms = {
        int(mcc): beta_mu[1 + idx] for idx, mcc in enumerate(hurdle_coefficients["dict_mcc"])
    }
    mu_channel_terms = {
        channel: beta_mu[1 + len(hurdle_coefficients["dict_mcc"]) + idx]
        for idx, channel in enumerate(hurdle_coefficients["dict_ch"])
    }
    phi_mcc_terms = {
        int(mcc): beta_phi[1 + idx]
        for idx, mcc in enumerate(nb_dispersion_coefficients["dict_mcc"])
    }
    phi_channel_terms = {
        channel: beta_phi[1 + len(nb_dispersion_coefficients["dict_mcc"]) + idx]
        for idx, channel in enumerate(nb_dispersion_coefficients["dict_ch"])
    }
    phi_gdp_coef = float(beta_phi[-1])

    entry_df["eta_mu_intercept"] = beta_mu[0]
    entry_df["eta_mu_mcc"] = entry_df["mcc"].map(mu_mcc_terms).astype(float)
    entry_df["eta_mu_channel"] = entry_df["channel_sym"].map(mu_channel_terms).astype(float)
    entry_df["eta_mu"] = (
        entry_df["eta_mu_intercept"] + entry_df["eta_mu_mcc"] + entry_df["eta_mu_channel"]
    )
    entry_df["mu_recomputed"] = np.exp(entry_df["eta_mu"])

    entry_df["eta_phi_intercept"] = beta_phi[0]
    entry_df["eta_phi_mcc"] = entry_df["mcc"].map(phi_mcc_terms).astype(float)
    entry_df["eta_phi_channel"] = entry_df["channel_sym"].map(phi_channel_terms).astype(float)
    entry_df["eta_phi_gdp"] = phi_gdp_coef * entry_df["ln_gdp_pc"]
    entry_df["eta_phi"] = (
        entry_df["eta_phi_intercept"]
        + entry_df["eta_phi_mcc"]
        + entry_df["eta_phi_channel"]
        + entry_df["eta_phi_gdp"]
    )
    entry_df["phi_recomputed"] = np.exp(entry_df["eta_phi"])

    entry_df["mu_abs_diff"] = (entry_df["mu"] - entry_df["mu_recomputed"]).abs()
    entry_df["phi_abs_diff"] = (entry_df["dispersion_k"] - entry_df["phi_recomputed"]).abs()

    print("COVERAGE")
    print("entry rows:", len(entry_df))
    print("missing mu mcc terms:", int(entry_df["eta_mu_mcc"].isna().sum()))
    print("missing mu channel terms:", int(entry_df["eta_mu_channel"].isna().sum()))
    print("missing phi mcc terms:", int(entry_df["eta_phi_mcc"].isna().sum()))
    print("missing phi channel terms:", int(entry_df["eta_phi_channel"].isna().sum()))
    print("missing phi gdp terms:", int(entry_df["eta_phi_gdp"].isna().sum()))
    print("distinct entrant MCCs:", entry_df["mcc"].nunique())
    print("entrant channels:", entry_df["channel_sym"].value_counts().to_dict())

    print("\nRECONSTRUCTION")
    print("mu diff max:", entry_df["mu_abs_diff"].max())
    print("phi diff max:", entry_df["phi_abs_diff"].max())

    print("\nETA MU COMPONENTS")
    print(entry_df[["eta_mu_intercept", "eta_mu_mcc", "eta_mu_channel", "eta_mu"]].describe().to_string())

    print("\nETA PHI COMPONENTS")
    print(
        entry_df[
            ["eta_phi_intercept", "eta_phi_mcc", "eta_phi_channel", "eta_phi_gdp", "eta_phi"]
        ]
        .describe()
        .to_string()
    )

    phi = entry_df["dispersion_k"]
    mu = entry_df["mu"]
    print("\nHETEROGENEITY")
    print("phi cv:", float(phi.std() / phi.mean()))
    print("phi p95/p05:", float(phi.quantile(0.95) / phi.quantile(0.05)))
    print("mu cv:", float(mu.std() / mu.mean()))
    print("mu p95/p05:", float(mu.quantile(0.95) / mu.quantile(0.05)))

    print("\nCOMPONENT CORRELATIONS")
    print("eta_mu_mcc -> mu:", entry_df["eta_mu_mcc"].corr(entry_df["mu"]))
    print("eta_mu_channel -> mu:", entry_df["eta_mu_channel"].corr(entry_df["mu"]))
    print("eta_phi_mcc -> phi:", entry_df["eta_phi_mcc"].corr(entry_df["dispersion_k"]))
    print("eta_phi_channel -> phi:", entry_df["eta_phi_channel"].corr(entry_df["dispersion_k"]))
    print("eta_phi_gdp -> phi:", entry_df["eta_phi_gdp"].corr(entry_df["dispersion_k"]))

    print("\nBY CHANNEL")
    print(
        entry_df.groupby("channel_sym")
        .agg(
            merchants=("merchant_id", "size"),
            mean_eta_mu=("eta_mu", "mean"),
            mean_mu=("mu", "mean"),
            mean_eta_phi=("eta_phi", "mean"),
            mean_phi=("dispersion_k", "mean"),
            mean_gdp_term=("eta_phi_gdp", "mean"),
        )
        .to_string()
    )

    entry_df["gdp_q5"] = pd.qcut(entry_df["gdp_pc_usd_2015"], 5, labels=False, duplicates="drop") + 1
    print("\nBY GDP QUINTILE")
    print(
        entry_df.groupby("gdp_q5")
        .agg(
            merchants=("merchant_id", "size"),
            gdp_min=("gdp_pc_usd_2015", "min"),
            gdp_max=("gdp_pc_usd_2015", "max"),
            mean_eta_phi_gdp=("eta_phi_gdp", "mean"),
            mean_phi=("dispersion_k", "mean"),
            mean_mu=("mu", "mean"),
        )
        .to_string()
    )

    mu_mcc_series = pd.Series(mu_mcc_terms).sort_values()
    phi_mcc_series = pd.Series(phi_mcc_terms).sort_values()
    print("\nMCC EXTREMES MU")
    print("bottom 10")
    print(mu_mcc_series.head(10).to_string())
    print("top 10")
    print(mu_mcc_series.tail(10).to_string())

    print("\nMCC EXTREMES PHI")
    print("bottom 10")
    print(phi_mcc_series.head(10).to_string())
    print("top 10")
    print(phi_mcc_series.tail(10).to_string())

    print("\nREMEDIATION METADATA")
    print("beta_mu remediation:", hurdle_coefficients.get("metadata", {}).get("remediation", {}))
    print(
        "beta_phi remediation:",
        nb_dispersion_coefficients.get("metadata", {}).get("remediation", {}),
    )


if __name__ == "__main__":
    main()
