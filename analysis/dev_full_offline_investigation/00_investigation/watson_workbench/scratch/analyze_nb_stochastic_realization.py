from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
PARAMETER_HASH = "0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00"
SEED = "42"
RUN_ID = "a3bd8cac9a4284cd36072c6b9624a0c1"


def load_jsonl_files(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    row["_part"] = path.name
                    rows.append(row)
    return pd.DataFrame(rows)


def pair_counter(hi: int, lo: int) -> int:
    return (int(hi) << 64) | int(lo)


def alpha_from_mu_phi(mu: float, phi: float) -> float:
    p = phi / (phi + mu)
    p0 = p**phi
    p1 = phi * (1.0 - p) * (p**phi)
    return 1.0 - p0 - p1


def main() -> None:
    events_root = RUN_ROOT / "logs" / "layer1" / "1A" / "rng" / "events"
    gamma_df = load_jsonl_files(
        sorted(
            (
                events_root
                / "gamma_component"
                / f"seed={SEED}"
                / f"parameter_hash={PARAMETER_HASH}"
                / f"run_id={RUN_ID}"
            ).rglob("part-*.jsonl")
        )
    )
    poisson_all_df = load_jsonl_files(
        sorted(
            (
                events_root
                / "poisson_component"
                / f"seed={SEED}"
                / f"parameter_hash={PARAMETER_HASH}"
                / f"run_id={RUN_ID}"
            ).rglob("part-*.jsonl")
        )
    )
    nb_final_df = load_jsonl_files(
        sorted(
            (
                events_root
                / "nb_final"
                / f"seed={SEED}"
                / f"parameter_hash={PARAMETER_HASH}"
                / f"run_id={RUN_ID}"
            ).rglob("part-*.jsonl")
        )
    )

    poisson_nb_df = poisson_all_df.loc[
        (poisson_all_df["context"] == "nb")
        & (poisson_all_df["module"] == "1A.nb_poisson_component")
        & (poisson_all_df["substream_label"] == "poisson_nb")
    ].copy()
    poisson_ztp_df = poisson_all_df.loc[poisson_all_df["context"] == "ztp"].copy()

    sort_cols = [
        "merchant_id",
        "rng_counter_before_hi",
        "rng_counter_before_lo",
        "rng_counter_after_hi",
        "rng_counter_after_lo",
    ]
    gamma_df = gamma_df.sort_values(sort_cols).copy()
    gamma_df["attempt_recon"] = gamma_df.groupby("merchant_id").cumcount() + 1

    poisson_nb_df = poisson_nb_df.sort_values(sort_cols).copy()
    poisson_nb_df["attempt_recon"] = poisson_nb_df.groupby("merchant_id").cumcount() + 1

    per_merchant_df = pd.DataFrame(
        {
            "gamma_n": gamma_df.groupby("merchant_id").size(),
            "poisson_n": poisson_nb_df.groupby("merchant_id").size(),
            "final_n": nb_final_df.groupby("merchant_id").size(),
            "nb_rejections": nb_final_df.set_index("merchant_id")["nb_rejections"],
            "mu": nb_final_df.set_index("merchant_id")["mu"],
            "phi": nb_final_df.set_index("merchant_id")["dispersion_k"],
            "n_outlets": nb_final_df.set_index("merchant_id")["n_outlets"],
        }
    ).reset_index()
    per_merchant_df["attempts"] = per_merchant_df["nb_rejections"] + 1
    per_merchant_df["alpha_accept"] = [
        alpha_from_mu_phi(mu=float(mu), phi=float(phi))
        for mu, phi in zip(per_merchant_df["mu"], per_merchant_df["phi"])
    ]
    per_merchant_df["expected_rejections"] = (
        1.0 - per_merchant_df["alpha_accept"]
    ) / per_merchant_df["alpha_accept"]
    per_merchant_df["conditional_accept_mean"] = (
        per_merchant_df["mu"]
        - (
            per_merchant_df["phi"]
            * (1.0 - (per_merchant_df["phi"] / (per_merchant_df["phi"] + per_merchant_df["mu"])))
            * ((per_merchant_df["phi"] / (per_merchant_df["phi"] + per_merchant_df["mu"])) ** per_merchant_df["phi"])
        )
    ) / per_merchant_df["alpha_accept"]

    attempt_df = poisson_nb_df.merge(
        gamma_df[
            [
                "merchant_id",
                "attempt_recon",
                "alpha",
                "gamma_value",
                "draws",
                "blocks",
            ]
        ].rename(columns={"draws": "gamma_draws", "blocks": "gamma_blocks"}),
        on=["merchant_id", "attempt_recon"],
        how="left",
    ).merge(
        per_merchant_df[
            [
                "merchant_id",
                "nb_rejections",
                "n_outlets",
                "mu",
                "phi",
                "alpha_accept",
                "expected_rejections",
                "conditional_accept_mean",
            ]
        ],
        on="merchant_id",
        how="left",
    )
    attempt_df["is_accepted_attempt"] = attempt_df["attempt_recon"] == (
        attempt_df["nb_rejections"] + 1
    )
    attempt_df["lambda_calc"] = (attempt_df["mu"] / attempt_df["phi"]) * attempt_df["gamma_value"]
    attempt_df["lambda_abs_diff"] = (attempt_df["lambda"] - attempt_df["lambda_calc"]).abs()
    attempt_df["alpha_phi_abs_diff"] = (attempt_df["alpha"] - attempt_df["phi"]).abs()
    attempt_df["lambda_over_mu"] = attempt_df["lambda"] / attempt_df["mu"]
    attempt_df["gamma_over_phi"] = attempt_df["gamma_value"] / attempt_df["phi"]

    last_attempt_df = (
        attempt_df.sort_values(["merchant_id", "attempt_recon"])
        .groupby("merchant_id")
        .tail(1)[["merchant_id", "attempt_recon", "k", "lambda"]]
        .rename(
            columns={
                "attempt_recon": "final_attempt_index",
                "k": "accepted_k",
                "lambda": "accepted_lambda",
            }
        )
    )
    final_check_df = per_merchant_df.merge(last_attempt_df, on="merchant_id", how="left")
    final_check_df["n_vs_k_diff"] = final_check_df["n_outlets"] - final_check_df["accepted_k"]

    for df in (gamma_df, poisson_nb_df, nb_final_df):
        df["counter_before"] = [
            pair_counter(hi, lo)
            for hi, lo in zip(df["rng_counter_before_hi"], df["rng_counter_before_lo"])
        ]
        df["counter_after"] = [
            pair_counter(hi, lo)
            for hi, lo in zip(df["rng_counter_after_hi"], df["rng_counter_after_lo"])
        ]

    def check_monotone_non_overlapping(df: pd.DataFrame) -> bool:
        for _, merchant_df in df.sort_values(["merchant_id", "counter_before"]).groupby("merchant_id"):
            prev_after: int | None = None
            for row in merchant_df.itertuples(index=False):
                if int(row.counter_after) <= int(row.counter_before):
                    return False
                if prev_after is not None and int(row.counter_before) < prev_after:
                    return False
                prev_after = int(row.counter_after)
        return True

    gamma_draws = pd.to_numeric(gamma_df["draws"])
    gamma_blocks = pd.to_numeric(gamma_df["blocks"])
    poisson_draws = pd.to_numeric(poisson_nb_df["draws"])
    poisson_blocks = pd.to_numeric(poisson_nb_df["blocks"])
    final_draws = pd.to_numeric(nb_final_df["draws"])
    final_blocks = pd.to_numeric(nb_final_df["blocks"])

    alpha_decile_df = per_merchant_df.copy()
    alpha_decile_df["alpha_decile"] = (
        pd.qcut(alpha_decile_df["alpha_accept"], 10, labels=False, duplicates="drop") + 1
    )

    print("STREAM IDENTIFICATION")
    print("gamma rows:", len(gamma_df))
    print("poisson all rows:", len(poisson_all_df))
    print("poisson nb rows:", len(poisson_nb_df))
    print("poisson ztp rows:", len(poisson_ztp_df))
    print("nb_final rows:", len(nb_final_df))

    print("\nCARDINALITY AND COVERAGE")
    print("gamma merchants:", gamma_df["merchant_id"].nunique())
    print("poisson nb merchants:", poisson_nb_df["merchant_id"].nunique())
    print("nb_final merchants:", nb_final_df["merchant_id"].nunique())
    print("gamma == poisson per merchant:", bool((per_merchant_df["gamma_n"] == per_merchant_df["poisson_n"]).all()))
    print(
        "attempts == nb_rejections + 1:",
        bool((per_merchant_df["gamma_n"] == per_merchant_df["attempts"]).all()),
    )
    print("exactly one nb_final per merchant:", bool((per_merchant_df["final_n"] == 1).all()))
    print("max attempts:", int(per_merchant_df["attempts"].max()))
    print("rejection distribution:")
    print(per_merchant_df["nb_rejections"].value_counts().sort_index().to_string())

    print("\nIDENTITY CHECKS")
    print("max |lambda - (mu/phi)*gamma|:", float(attempt_df["lambda_abs_diff"].max()))
    print("max |alpha - phi|:", float(attempt_df["alpha_phi_abs_diff"].max()))
    print("accepted k equals nb_final.n_outlets:", bool((final_check_df["n_vs_k_diff"] == 0).all()))
    print(
        "final attempt index equals nb_rejections + 1:",
        bool((final_check_df["final_attempt_index"] == final_check_df["attempts"]).all()),
    )

    print("\nCOUNTER DISCIPLINE")
    print("gamma monotone and non-overlapping:", check_monotone_non_overlapping(gamma_df))
    print("poisson monotone and non-overlapping:", check_monotone_non_overlapping(poisson_nb_df))
    print("nb_final all non-consuming:", bool((nb_final_df["counter_before"] == nb_final_df["counter_after"]).all()))
    print("nb_final all zero draws:", bool((final_draws == 0).all()))
    print("nb_final all zero blocks:", bool((final_blocks == 0).all()))

    print("\nREGIMES")
    print("gamma alpha < 1:", int((gamma_df["alpha"] < 1).sum()))
    print("poisson lambda < 10:", int((poisson_nb_df["lambda"] < 10).sum()))
    print("poisson lambda >= 10:", int((poisson_nb_df["lambda"] >= 10).sum()))

    print("\nDRAW BUDGETS")
    print(
        "gamma draws total/mean/p95/max:",
        int(gamma_draws.sum()),
        float(gamma_draws.mean()),
        float(gamma_draws.quantile(0.95)),
        int(gamma_draws.max()),
    )
    print(
        "poisson draws total/mean/p95/max:",
        int(poisson_draws.sum()),
        float(poisson_draws.mean()),
        float(poisson_draws.quantile(0.95)),
        int(poisson_draws.max()),
    )
    print(
        "gamma draws distribution:",
        gamma_draws.value_counts().sort_index().to_dict(),
    )
    print(
        "poisson draws quantiles:",
        poisson_draws.quantile([0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0]).to_dict(),
    )

    print("\nATTEMPT OUTCOME SHAPE")
    print(
        "accepted attempts / rejected attempts:",
        int(attempt_df["is_accepted_attempt"].sum()),
        int((~attempt_df["is_accepted_attempt"]).sum()),
    )
    print(
        "rejected k distribution:",
        attempt_df.loc[~attempt_df["is_accepted_attempt"], "k"].value_counts().sort_index().to_dict(),
    )
    print("accepted lambda summary")
    print(attempt_df.loc[attempt_df["is_accepted_attempt"], "lambda"].describe().to_string())
    print("rejected lambda summary")
    print(attempt_df.loc[~attempt_df["is_accepted_attempt"], "lambda"].describe().to_string())

    print("\nMEAN-PRESERVING MIXTURE READ")
    print("mean gamma:", float(attempt_df["gamma_value"].mean()))
    print("mean phi:", float(attempt_df["phi"].mean()))
    print("mean gamma/phi:", float(attempt_df["gamma_over_phi"].mean()))
    print("median gamma/phi:", float(attempt_df["gamma_over_phi"].median()))
    print("mean lambda:", float(attempt_df["lambda"].mean()))
    print("mean mu:", float(attempt_df["mu"].mean()))
    print("mean lambda/mu:", float(attempt_df["lambda_over_mu"].mean()))
    print("median lambda/mu:", float(attempt_df["lambda_over_mu"].median()))

    print("\nREALIZED COUNT WORLD")
    print("mean mu:", float(per_merchant_df["mu"].mean()))
    print("mean conditional accepted expectation:", float(per_merchant_df["conditional_accept_mean"].mean()))
    print("mean realized n_outlets:", float(per_merchant_df["n_outlets"].mean()))
    print(
        "mean realized minus conditional expectation:",
        float((per_merchant_df["n_outlets"] - per_merchant_df["conditional_accept_mean"]).mean()),
    )
    print("corr(mu, n_outlets):", float(per_merchant_df["mu"].corr(per_merchant_df["n_outlets"])))
    realized_ratio = per_merchant_df["n_outlets"] / per_merchant_df["mu"]
    print(
        "realized ratio p05/median/p95:",
        float(realized_ratio.quantile(0.05)),
        float(realized_ratio.median()),
        float(realized_ratio.quantile(0.95)),
    )

    print("\nRETRY CONCENTRATION")
    print("accepted first attempt:", int((per_merchant_df["nb_rejections"] == 0).sum()))
    print("accepted after retry:", int((per_merchant_df["nb_rejections"] > 0).sum()))
    print("retry share:", float((per_merchant_df["nb_rejections"] > 0).mean()))
    print("overall rejection share of attempts:", float(per_merchant_df["nb_rejections"].sum() / len(attempt_df)))
    print("alpha min/p05/median/p95/max:")
    print(
        float(per_merchant_df["alpha_accept"].min()),
        float(per_merchant_df["alpha_accept"].quantile(0.05)),
        float(per_merchant_df["alpha_accept"].median()),
        float(per_merchant_df["alpha_accept"].quantile(0.95)),
        float(per_merchant_df["alpha_accept"].max()),
    )
    print("expected rejection mean/p95/max:")
    print(
        float(per_merchant_df["expected_rejections"].mean()),
        float(per_merchant_df["expected_rejections"].quantile(0.95)),
        float(per_merchant_df["expected_rejections"].max()),
    )
    print("alpha decile retry concentration")
    print(
        alpha_decile_df.groupby("alpha_decile")
        .agg(
            merchants=("merchant_id", "size"),
            retries=("nb_rejections", "sum"),
            merchants_with_retry=("nb_rejections", lambda values: int((values > 0).sum())),
            alpha_min=("alpha_accept", "min"),
            alpha_max=("alpha_accept", "max"),
        )
        .to_string()
    )


if __name__ == "__main__":
    main()
