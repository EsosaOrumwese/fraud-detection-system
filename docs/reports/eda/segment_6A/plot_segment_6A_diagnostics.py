from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import duckdb
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yaml


RUN_BASE = Path(r"runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data")
BASE_6A = RUN_BASE / "layer3/6A"
PRIORS_DIR = Path(r"config/layer3/6A/priors")
OUT_DIR = Path(r"docs/reports/eda/segment_6A/plots")


def _scan(ds: str) -> str:
    return f"parquet_scan('{(BASE_6A / ds).as_posix()}/**/*.parquet', hive_partitioning=true, union_by_name=true)"


def _read_yaml(name: str) -> dict:
    return yaml.safe_load((PRIORS_DIR / name).read_text(encoding="utf-8"))


def _setup_style() -> None:
    sns.set_theme(style="whitegrid", context="talk", font="DejaVu Sans")
    plt.rcParams["figure.dpi"] = 160
    plt.rcParams["savefig.dpi"] = 160
    plt.rcParams["axes.titleweight"] = "semibold"
    plt.rcParams["axes.titlesize"] = 20
    plt.rcParams["axes.labelsize"] = 15
    plt.rcParams["xtick.labelsize"] = 12
    plt.rcParams["ytick.labelsize"] = 12
    plt.rcParams["legend.fontsize"] = 12


def _party_region_weights(con: duckdb.DuckDBPyConnection) -> Dict[str, float]:
    df = con.execute(
        f"""
        SELECT region_id, count(*)::DOUBLE / sum(count(*)) OVER() AS w
        FROM {_scan("s1_party_base_6A")}
        GROUP BY 1
        """
    ).fetchdf()
    return dict(zip(df["region_id"], df["w"]))


def _expected_party_type_share(seg_prior: dict, region_weights: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for row in seg_prior["region_party_type_mix"]:
        r = row["region_id"]
        wr = float(region_weights.get(r, 0.0))
        for ptype, share in row["pi_type"].items():
            out[ptype] = out.get(ptype, 0.0) + wr * float(share)
    return out


def _expected_overall_account_share(product_prior: dict, observed_party_shares: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    base = product_prior["party_lambda_model"]["base_lambda_by_party_type"]
    for ptype, mixes in base.items():
        pt_weight = float(observed_party_shares.get(ptype, 0.0))
        total_lambda = float(sum(mixes.values())) if mixes else 0.0
        if total_lambda <= 0:
            continue
        for acct, lam in mixes.items():
            share = float(lam) / total_lambda
            out[acct] = out.get(acct, 0.0) + pt_weight * share
    return out


def _expected_ip_share(ip_prior: dict, region_weights: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    mix = ip_prior["ip_type_mix_model"]["pi_ip_type_by_region"]
    for row in mix:
        region = row["region_id"]
        wr = float(region_weights.get(region, 0.0))
        for item in row["pi_ip_type"]:
            ip_type = item["ip_type"]
            share = float(item["share"])
            out[ip_type] = out.get(ip_type, 0.0) + wr * share
    return out


def _topk_share(values: np.ndarray, pct: float) -> float:
    if values.size == 0:
        return 0.0
    k = max(1, int(np.ceil(values.size * pct)))
    return float(np.sort(values)[::-1][:k].sum() / values.sum())


def plot_01_policy_parity(con: duckdb.DuckDBPyConnection) -> None:
    seg = _read_yaml("segmentation_priors_6A.v1.yaml")
    prod = _read_yaml("product_mix_priors_6A.v1.yaml")
    inst = _read_yaml("instrument_mix_priors_6A.v1.yaml")
    ipc = _read_yaml("ip_count_priors_6A.v1.yaml")

    region_w = _party_region_weights(con)

    party_obs_df = con.execute(
        f"""
        SELECT party_type, count(*)::DOUBLE / sum(count(*)) OVER() AS share
        FROM {_scan("s1_party_base_6A")}
        GROUP BY 1
        """
    ).fetchdf()
    party_obs = dict(zip(party_obs_df["party_type"], party_obs_df["share"]))
    party_exp = _expected_party_type_share(seg, region_w)

    acct_obs_df = con.execute(
        f"""
        SELECT account_type, count(*)::DOUBLE / sum(count(*)) OVER() AS share
        FROM {_scan("s2_account_base_6A")}
        GROUP BY 1
        """
    ).fetchdf()
    acct_obs = dict(zip(acct_obs_df["account_type"], acct_obs_df["share"]))
    acct_exp = _expected_overall_account_share(prod, party_obs)

    ip_obs_df = con.execute(
        f"""
        SELECT ip_type, count(*)::DOUBLE / sum(count(*)) OVER() AS share
        FROM {_scan("s4_ip_base_6A")}
        GROUP BY 1
        """
    ).fetchdf()
    ip_obs = dict(zip(ip_obs_df["ip_type"], ip_obs_df["share"]))
    ip_exp = _expected_ip_share(ipc, region_w)

    lambda_obs_df = con.execute(
        f"""
        WITH per_acct AS (
          SELECT a.account_type, a.account_id, count(l.instrument_id) AS n_instr
          FROM {_scan("s2_account_base_6A")} a
          LEFT JOIN {_scan("s3_account_instrument_links_6A")} l USING(account_id)
          GROUP BY 1,2
        )
        SELECT account_type, avg(n_instr)::DOUBLE AS observed_lambda
        FROM per_acct
        GROUP BY 1
        """
    ).fetchdf()
    lambda_obs = dict(zip(lambda_obs_df["account_type"], lambda_obs_df["observed_lambda"]))
    lambda_exp = {
        row["account_type"]: float(row["lambda_total"])
        for row in inst["lambda_model"]["lambda_total_by_party_type_account_type"]
    }

    share_rows: List[Tuple[str, float, float]] = []
    for k in sorted(set(party_exp) | set(party_obs)):
        share_rows.append((f"party_share::{k}", party_exp.get(k, 0.0), party_obs.get(k, 0.0)))
    for k in sorted(set(acct_exp) | set(acct_obs)):
        share_rows.append((f"account_share::{k}", acct_exp.get(k, 0.0), acct_obs.get(k, 0.0)))
    for k in sorted(set(ip_exp) | set(ip_obs)):
        share_rows.append((f"ip_share::{k}", ip_exp.get(k, 0.0), ip_obs.get(k, 0.0)))
    share_df = pd.DataFrame(share_rows, columns=["metric", "target", "observed"])
    share_df["delta_pp"] = (share_df["observed"] - share_df["target"]) * 100.0
    share_df = share_df.sort_values("metric")

    lambda_rows: List[Tuple[str, float, float]] = []
    for k in sorted(set(lambda_exp) | set(lambda_obs)):
        lambda_rows.append((k, lambda_exp.get(k, 0.0), lambda_obs.get(k, 0.0)))
    lambda_df = pd.DataFrame(lambda_rows, columns=["account_type", "target_lambda", "observed_lambda"])
    lambda_df["delta"] = lambda_df["observed_lambda"] - lambda_df["target_lambda"]
    lambda_df = lambda_df.sort_values("account_type")

    fig, axes = plt.subplots(1, 2, figsize=(22, 14), gridspec_kw={"width_ratios": [1.35, 1.0]})
    s_mat = share_df.set_index("metric")[["target", "observed", "delta_pp"]]
    sns.heatmap(
        s_mat,
        ax=axes[0],
        cmap="coolwarm",
        center=0.0,
        annot=True,
        fmt=".3f",
        cbar_kws={"label": "value / delta_pp"},
    )
    axes[0].set_title("Policy vs Observed Parity Matrix (Shares + Delta pp)")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("metric")
    cbar0 = axes[0].collections[0].colorbar
    cbar0.ax.yaxis.set_label_position("left")
    cbar0.set_label("value / delta_pp", rotation=90, labelpad=10)

    l_mat = lambda_df.set_index("account_type")[["target_lambda", "observed_lambda", "delta"]]
    l_mat.index.name = ""
    sns.heatmap(
        l_mat,
        ax=axes[1],
        cmap="coolwarm",
        center=0.0,
        annot=True,
        fmt=".3f",
        cbar_kws={"label": "value / delta"},
    )
    axes[1].set_title("Instrument Lambda Target vs Observed")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("")
    axes[1].yaxis.label.set_visible(False)
    fig.subplots_adjust(wspace=0.42)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "01_policy_observed_parity_matrix.png")
    plt.close()


def plot_02_country_concentration(con: duckdb.DuckDBPyConnection) -> None:
    df = con.execute(
        f"""
        SELECT country_iso, count(*)::DOUBLE AS n
        FROM {_scan("s1_party_base_6A")}
        GROUP BY 1
        ORDER BY n DESC
        """
    ).fetchdf()
    vals = np.sort(df["n"].to_numpy())
    cum_y = np.concatenate([[0.0], np.cumsum(vals) / np.sum(vals)])
    cum_x = np.linspace(0, 1, len(cum_y))
    gini = 1.0 - 2.0 * np.trapezoid(cum_y, cum_x)
    topks = [0.01, 0.05, 0.10]
    topk_labels = ["top1%", "top5%", "top10%"]
    topk_vals = [_topk_share(df["n"].to_numpy(), k) for k in topks]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    axes[0].plot(cum_x, cum_y, color="#3E6FB0", linewidth=3, label="Country concentration")
    axes[0].plot([0, 1], [0, 1], "--", color="gray", linewidth=2, label="Equality")
    axes[0].set_title(f"Country Concentration Lorenz Curve (Gini={gini:.3f})")
    axes[0].set_xlabel("Cumulative share of countries")
    axes[0].set_ylabel("Cumulative share of parties")
    axes[0].legend()

    bars = axes[1].bar(topk_labels, topk_vals, color="#D6844F")
    axes[1].set_title("Country Top-k Share of Parties")
    axes[1].set_ylabel("share")
    axes[1].set_ylim(0, max(topk_vals) * 1.2)
    for b, v in zip(bars, topk_vals):
        axes[1].annotate(f"{v:.2%}", (b.get_x() + b.get_width() / 2, v), ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "02_country_concentration_lorenz_topk.png")
    plt.close()


def plot_03_country_segment_residual(con: duckdb.DuckDBPyConnection) -> None:
    top_countries_df = con.execute(
        f"""
        SELECT country_iso, count(*) AS n
        FROM {_scan("s1_party_base_6A")}
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 12
        """
    ).fetchdf()
    top_segments_df = con.execute(
        f"""
        SELECT segment_id, count(*) AS n
        FROM {_scan("s1_party_base_6A")}
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 10
        """
    ).fetchdf()
    countries = top_countries_df["country_iso"].tolist()
    segments = top_segments_df["segment_id"].tolist()

    obs_df = con.execute(
        f"""
        SELECT country_iso, segment_id, count(*)::DOUBLE AS n
        FROM {_scan("s1_party_base_6A")}
        WHERE country_iso IN ({",".join(repr(c) for c in countries)})
          AND segment_id IN ({",".join(repr(s) for s in segments)})
        GROUP BY 1,2
        """
    ).fetchdf()
    global_df = con.execute(
        f"""
        SELECT segment_id, count(*)::DOUBLE / sum(count(*)) OVER() AS g_share
        FROM {_scan("s1_party_base_6A")}
        WHERE segment_id IN ({",".join(repr(s) for s in segments)})
        GROUP BY 1
        """
    ).fetchdf()
    gmap = dict(zip(global_df["segment_id"], global_df["g_share"]))

    mat = obs_df.pivot(index="country_iso", columns="segment_id", values="n").fillna(0.0)
    mat = mat.div(mat.sum(axis=1), axis=0)
    for s in segments:
        mat[s] = mat[s] - gmap.get(s, 0.0)
    mat = mat.loc[countries, segments]

    plt.figure(figsize=(18, 10))
    ax = sns.heatmap(mat * 100.0, cmap="coolwarm", center=0.0, annot=True, fmt=".2f", cbar_kws={"label": "Residual pp"})
    plt.title("Country x Segment Residual Heatmap\n(Observed segment share - Global segment share)")
    plt.xlabel("segment_id")
    plt.ylabel("country_iso")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=60, ha="right")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "03_country_segment_residual_heatmap.png")
    plt.close()


def plot_04_accounts_ccdf(con: duckdb.DuckDBPyConnection) -> None:
    df = con.execute(
        f"""
        WITH acct AS (
          SELECT owner_party_id AS party_id, count(*) AS n_accounts
          FROM {_scan("s2_account_base_6A")}
          GROUP BY 1
        )
        SELECT p.party_type, coalesce(a.n_accounts, 0) AS n_accounts
        FROM {_scan("s1_party_base_6A")} p
        LEFT JOIN acct a ON p.party_id = a.party_id
        """
    ).fetchdf()

    plt.figure(figsize=(11, 7))
    for ptype, grp in df.groupby("party_type"):
        vals = grp["n_accounts"].to_numpy()
        zero_share = float(np.mean(vals == 0))
        vals = vals[vals > 0]
        if vals.size == 0:
            continue
        xs = np.sort(vals)
        ys = 1.0 - np.arange(1, len(xs) + 1) / len(xs)
        plt.plot(xs, ys, linewidth=2.2, label=f"{ptype} (zero={zero_share:.2%})")
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("accounts per party (nonzero)")
    plt.ylabel("CCDF: P(X >= x)")
    plt.title("Accounts-per-Party Tail by Party Type (CCDF, log-log)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_DIR / "04_accounts_per_party_ccdf_by_party_type.png")
    plt.close()


def plot_05_kmax_breaches(con: duckdb.DuckDBPyConnection) -> None:
    acc_prior = _read_yaml("account_per_party_priors_6A.v1.yaml")
    caps = {}
    for r in acc_prior["rules"]:
        acct = r["account_type"]
        caps[acct] = float(r["params"]["K_max"])

    obs = con.execute(
        f"""
        WITH per_party AS (
          SELECT account_type, owner_party_id, count(*) AS n
          FROM {_scan("s2_account_base_6A")}
          GROUP BY 1,2
        )
        SELECT account_type, max(n) AS observed_max, count(*) AS parties_with_type
        FROM per_party
        GROUP BY 1
        """
    ).fetchdf()
    breach = con.execute(
        f"""
        WITH per_party AS (
          SELECT account_type, owner_party_id, count(*) AS n
          FROM {_scan("s2_account_base_6A")}
          GROUP BY 1,2
        )
        SELECT account_type, count(*) AS breach_n
        FROM per_party
        GROUP BY 1
        """
    ).fetchdf()
    # recompute breach_n with cap in pandas
    per_party = con.execute(
        f"""
        SELECT account_type, owner_party_id, count(*) AS n
        FROM {_scan("s2_account_base_6A")}
        GROUP BY 1,2
        """
    ).fetchdf()
    per_party["kmax"] = per_party["account_type"].map(caps)
    per_party["breach"] = per_party["n"] > per_party["kmax"]
    breach_df = per_party.groupby("account_type", as_index=False).agg(
        breach_n=("breach", "sum"),
        parties_with_type=("breach", "count"),
        observed_max=("n", "max"),
    )
    breach_df["kmax"] = breach_df["account_type"].map(caps)
    breach_df["breach_rate"] = breach_df["breach_n"] / breach_df["parties_with_type"]
    breach_df = breach_df.sort_values("breach_rate", ascending=False)

    fig, axes = plt.subplots(2, 1, figsize=(16, 12), sharex=True)
    x = np.arange(len(breach_df))
    axes[0].vlines(x, breach_df["kmax"], breach_df["observed_max"], color="#E15759", alpha=0.7, linewidth=2)
    axes[0].scatter(x, breach_df["kmax"], color="#4E79A7", label="K_max (policy)", s=45)
    axes[0].scatter(x, breach_df["observed_max"], color="#D62728", label="Observed max", s=45)
    axes[0].set_ylabel("count per party")
    axes[0].set_title("Account K_max vs Observed Max by Account Type")
    axes[0].legend()

    bars = axes[1].bar(x, breach_df["breach_rate"], color="#F28E2B")
    axes[1].set_ylabel("breach rate")
    axes[1].set_title("K_max Breach Rate by Account Type")
    axes[1].set_ylim(0, min(1.0, breach_df["breach_rate"].max() * 1.2))
    axes[1].set_xticks(x, breach_df["account_type"], rotation=60, ha="right")
    for b, n in zip(bars, breach_df["breach_n"]):
        axes[1].annotate(f"{int(n):,}", (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "05_account_kmax_breaches.png")
    plt.close()


def plot_06_instrument_identity(con: duckdb.DuckDBPyConnection) -> None:
    inst_prior = _read_yaml("instrument_mix_priors_6A.v1.yaml")
    target_df = pd.DataFrame(inst_prior["lambda_model"]["lambda_total_by_party_type_account_type"])
    target_df = target_df[["account_type", "lambda_total"]].rename(columns={"lambda_total": "target_lambda"})

    obs_df = con.execute(
        f"""
        WITH per_acct AS (
          SELECT a.account_type, a.account_id, count(l.instrument_id) AS n_instr
          FROM {_scan("s2_account_base_6A")} a
          LEFT JOIN {_scan("s3_account_instrument_links_6A")} l USING(account_id)
          GROUP BY 1,2
        )
        SELECT account_type, avg(n_instr)::DOUBLE AS observed_lambda
        FROM per_acct
        GROUP BY 1
        """
    ).fetchdf()
    df = target_df.merge(obs_df, on="account_type", how="outer").fillna(0.0)
    df["party_type"] = df["account_type"].str.split("_").str[0]

    plt.figure(figsize=(12, 9))
    ax = sns.scatterplot(data=df, x="target_lambda", y="observed_lambda", hue="party_type", s=120)
    lim = max(df["target_lambda"].max(), df["observed_lambda"].max()) * 1.1
    plt.plot([0, lim], [0, lim], "--", color="gray")
    # Collision-avoidance label placement in data coordinates with leader lines.
    placed: List[Tuple[float, float]] = []
    dfl = df.sort_values(["target_lambda", "observed_lambda"]).reset_index(drop=True)
    x_tol = 0.10
    y_tol = 0.06
    base_dx = 0.03 * lim
    step_y = 0.045 * lim
    for _, r in dfl.iterrows():
        x = float(r["target_lambda"])
        y = float(r["observed_lambda"])
        lx = x + base_dx
        ly = y
        for k in range(24):
            conflict = any(abs(lx - px) < x_tol and abs(ly - py) < y_tol for px, py in placed)
            if not conflict:
                break
            # Alternate up/down and expand slightly right as collisions persist.
            amp = (k // 2 + 1) * step_y
            ly = y + (amp if k % 2 == 0 else -amp)
            ly = max(0.02 * lim, min(0.98 * lim, ly))
            lx = x + base_dx + (k // 6) * (0.02 * lim)
        placed.append((lx, ly))
        ax.annotate(
            r["account_type"],
            xy=(x, y),
            xytext=(lx, ly),
            textcoords="data",
            fontsize=8,
            ha="left",
            va="center",
            arrowprops={"arrowstyle": "-", "color": "#777777", "lw": 0.8, "shrinkA": 0, "shrinkB": 0},
        )
    plt.xlim(0, lim)
    plt.ylim(0, lim)
    plt.xlabel("Target lambda_total (policy)")
    plt.ylabel("Observed avg instruments/account")
    plt.title("Instrument Totals: Target vs Observed (Identity Plot)")
    ax.legend(loc="upper left", frameon=True, title="party_type")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "06_instrument_lambda_identity.png")
    plt.close()


def plot_07_instrument_mix_residual(con: duckdb.DuckDBPyConnection) -> None:
    inst_prior = _read_yaml("instrument_mix_priors_6A.v1.yaml")
    exp_rows = []
    for row in inst_prior["lambda_model"]["mix_by_party_type_account_type"]:
        acct = row["account_type"]
        for p in row["pi_instr"]:
            exp_rows.append((acct, p["instrument_type"], float(p["share"])))
    exp_df = pd.DataFrame(exp_rows, columns=["account_type", "instrument_type", "expected_share"])

    obs_df = con.execute(
        f"""
        SELECT a.account_type, l.instrument_type, count(*)::DOUBLE AS n
        FROM {_scan("s3_account_instrument_links_6A")} l
        JOIN {_scan("s2_account_base_6A")} a USING(account_id)
        GROUP BY 1,2
        """
    ).fetchdf()
    obs_df["observed_share"] = obs_df["n"] / obs_df.groupby("account_type")["n"].transform("sum")
    obs_df = obs_df[["account_type", "instrument_type", "observed_share"]]

    df = exp_df.merge(obs_df, on=["account_type", "instrument_type"], how="outer").fillna(0.0)
    df["residual_pp"] = (df["observed_share"] - df["expected_share"]) * 100.0

    pivot = df.pivot(index="account_type", columns="instrument_type", values="residual_pp").fillna(0.0)
    # Keep most informative columns for readability.
    top_cols = pivot.abs().mean(axis=0).sort_values(ascending=False).head(14).index.tolist()
    pivot = pivot[top_cols]

    plt.figure(figsize=(18, 9))
    ax = sns.heatmap(pivot, cmap="coolwarm", center=0.0, annot=True, fmt=".3f", cbar_kws={"label": "Residual pp"})
    plt.title("Instrument Composition Residuals\n(Observed share - Expected share) by Account Type")
    plt.xlabel("instrument_type")
    plt.ylabel("account_type")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=90)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "07_instrument_mix_residual_heatmap.png")
    plt.close()


def plot_08_device_ip_funnel(con: duckdb.DuckDBPyConnection) -> None:
    devices_total = int(con.execute(f"SELECT count(*) FROM {_scan('s4_device_base_6A')}").fetchone()[0])
    devices_with_ip = int(con.execute(f"SELECT count(distinct device_id) FROM {_scan('s4_ip_links_6A')}").fetchone()[0])
    ips_linked = int(con.execute(f"SELECT count(distinct ip_id) FROM {_scan('s4_ip_links_6A')}").fetchone()[0])
    ips_total = int(con.execute(f"SELECT count(*) FROM {_scan('s4_ip_base_6A')}").fetchone()[0])

    stages = ["Devices total", "Devices with IP", "Linked IPs", "IPs total"]
    vals = np.array([devices_total, devices_with_ip, ips_linked, ips_total], dtype=float)
    perc_total = vals / vals[0]

    plt.figure(figsize=(14, 7))
    bars = plt.barh(stages, vals, color=["#4E79A7", "#59A14F", "#F28E2B", "#9C755F"])
    plt.gca().invert_yaxis()
    plt.title("Device to IP Linkage Funnel")
    plt.xlabel("count")
    xmax = float(vals.max()) * 1.55
    plt.xlim(0, xmax)
    for b, p in zip(bars, perc_total):
        v = b.get_width()
        plt.text(v + 0.02 * xmax, b.get_y() + b.get_height() / 2, f"{int(v):,} ({p:.1%} of devices)", va="center")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "08_device_ip_linkage_funnel.png")
    plt.close()


def plot_09_ip_type_dumbbell(con: duckdb.DuckDBPyConnection) -> None:
    ip_prior = _read_yaml("ip_count_priors_6A.v1.yaml")
    region_w = _party_region_weights(con)
    expected = _expected_ip_share(ip_prior, region_w)

    obs = con.execute(
        f"""
        SELECT ip_type, count(*)::DOUBLE / sum(count(*)) OVER() AS share
        FROM {_scan("s4_ip_base_6A")}
        GROUP BY 1
        """
    ).fetchdf()
    observed = dict(zip(obs["ip_type"], obs["share"]))

    types = sorted(set(expected) | set(observed), key=lambda t: abs(observed.get(t, 0.0) - expected.get(t, 0.0)), reverse=True)
    df = pd.DataFrame(
        {
            "ip_type": types,
            "expected": [expected.get(t, 0.0) for t in types],
            "observed": [observed.get(t, 0.0) for t in types],
        }
    )

    y = np.arange(len(df))
    plt.figure(figsize=(11, 7))
    for i, r in df.iterrows():
        plt.plot([r["expected"], r["observed"]], [i, i], color="#9e9e9e", linewidth=2)
    plt.scatter(df["expected"], y, color="#4E79A7", label="expected", s=80)
    plt.scatter(df["observed"], y, color="#D62728", label="observed", s=80)
    plt.yticks(y, df["ip_type"])
    plt.gca().invert_yaxis()
    plt.xlabel("share")
    plt.title("IP Type Mix: Prior vs Observed (Dumbbell)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_DIR / "09_ip_type_prior_vs_observed_dumbbell.png")
    plt.close()


def plot_10_devices_per_ip_tail(con: duckdb.DuckDBPyConnection) -> None:
    deg = con.execute(
        f"""
        SELECT ip_id, count(distinct device_id)::DOUBLE AS degree
        FROM {_scan("s4_ip_links_6A")}
        GROUP BY 1
        """
    ).fetchdf()["degree"].to_numpy()
    deg = np.sort(deg)
    x = np.unique(deg)
    ccdf = np.array([np.mean(deg >= v) for v in x])
    p95, p99, p999 = np.quantile(deg, [0.95, 0.99, 0.999])

    plt.figure(figsize=(11, 7))
    plt.loglog(x, ccdf, color="#3E6FB0", linewidth=2.5, label="CCDF")
    for q, lbl, c in [(p95, "p95", "#59A14F"), (p99, "p99", "#F28E2B"), (p999, "p99.9", "#E15759")]:
        plt.axvline(q, color=c, linestyle="--", linewidth=1.8, label=f"{lbl}={q:.1f}")
    plt.xlabel("devices per IP (degree)")
    plt.ylabel("P(X >= x)")
    plt.title("Devices-per-IP Tail (CCDF, log-log)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_DIR / "10_devices_per_ip_ccdf_loglog.png")
    plt.close()


def plot_11_risk_propagation(con: duckdb.DuckDBPyConnection) -> None:
    role_df = con.execute(f"SELECT party_id, fraud_role_party FROM {_scan('s5_party_fraud_roles_6A')}").fetchdf()
    acct_df = con.execute(
        f"""
        SELECT a.owner_party_id AS party_id,
               avg(CASE WHEN r.fraud_role_account <> 'CLEAN_ACCOUNT' THEN 1 ELSE 0 END)::DOUBLE AS acct_nonclean_rate
        FROM {_scan("s2_account_base_6A")} a
        JOIN {_scan("s5_account_fraud_roles_6A")} r USING(account_id)
        GROUP BY 1
        """
    ).fetchdf()
    dev_df = con.execute(
        f"""
        SELECT d.primary_party_id AS party_id,
               avg(CASE WHEN r.fraud_role_device <> 'CLEAN_DEVICE' THEN 1 ELSE 0 END)::DOUBLE AS dev_nonclean_rate
        FROM {_scan("s4_device_base_6A")} d
        JOIN {_scan("s5_device_fraud_roles_6A")} r USING(device_id)
        GROUP BY 1
        """
    ).fetchdf()

    df = role_df.merge(acct_df, on="party_id", how="left").merge(dev_df, on="party_id", how="left")
    df["acct_nonclean_rate"] = df["acct_nonclean_rate"].fillna(0.0)
    df["dev_nonclean_rate"] = df["dev_nonclean_rate"].fillna(0.0)
    base_acct = float(df["acct_nonclean_rate"].mean())
    base_dev = float(df["dev_nonclean_rate"].mean())

    agg = df.groupby("fraud_role_party", as_index=False)[["acct_nonclean_rate", "dev_nonclean_rate"]].mean()
    agg["acct_uplift_pp"] = (agg["acct_nonclean_rate"] - base_acct) * 100.0
    agg["dev_uplift_pp"] = (agg["dev_nonclean_rate"] - base_dev) * 100.0
    agg = agg.sort_values("fraud_role_party")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    rate_mat = agg.set_index("fraud_role_party")[["acct_nonclean_rate", "dev_nonclean_rate"]]
    sns.heatmap(rate_mat * 100.0, annot=True, fmt=".2f", cmap="Blues", ax=axes[0], cbar_kws={"label": "Rate (%)"})
    axes[0].set_title("Non-clean Rate by Party Role")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("fraud_role_party")

    uplift_mat = agg.set_index("fraud_role_party")[["acct_uplift_pp", "dev_uplift_pp"]]
    sns.heatmap(uplift_mat, annot=True, fmt=".2f", cmap="coolwarm", center=0.0, ax=axes[1], cbar_kws={"label": "Uplift pp"})
    axes[1].set_title("Risk Propagation Uplift over Global Baseline")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "11_party_role_risk_propagation_heatmaps.png")
    plt.close()


def plot_12_ip_degree_enrichment(con: duckdb.DuckDBPyConnection) -> None:
    df = con.execute(
        f"""
        WITH deg AS (
          SELECT ip_id, count(distinct device_id)::DOUBLE AS degree
          FROM {_scan("s4_ip_links_6A")}
          GROUP BY 1
        ),
        roles AS (
          SELECT ip_id, CASE WHEN fraud_role_ip = 'HIGH_RISK_IP' THEN 1 ELSE 0 END AS is_high
          FROM {_scan("s5_ip_fraud_roles_6A")}
        ),
        joined AS (
          SELECT d.ip_id, d.degree, r.is_high
          FROM deg d
          JOIN roles r USING(ip_id)
        ),
        binned AS (
          SELECT ntile(20) OVER (ORDER BY degree) AS bin, degree, is_high
          FROM joined
        )
        SELECT bin,
               avg(degree)::DOUBLE AS mean_degree,
               avg(is_high)::DOUBLE AS high_share,
               count(*) AS n
        FROM binned
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchdf()
    global_high = con.execute(
        f"""
        SELECT avg(CASE WHEN fraud_role_ip = 'HIGH_RISK_IP' THEN 1 ELSE 0 END)::DOUBLE
        FROM {_scan("s5_ip_fraud_roles_6A")}
        """
    ).fetchone()[0]
    df["enrichment"] = df["high_share"] / global_high

    fig, ax1 = plt.subplots(figsize=(11, 7))
    ax1.plot(df["mean_degree"], df["high_share"] * 100.0, marker="o", color="#D62728", label="High-risk share (%)")
    ax1.set_xlabel("Mean devices/IP in percentile bin")
    ax1.set_ylabel("High-risk IP share (%)", color="#D62728")
    ax1.tick_params(axis="y", labelcolor="#D62728")
    ax1.set_title("IP Degree vs High-risk Enrichment (20 percentile bins)")

    ax2 = ax1.twinx()
    ax2.plot(df["mean_degree"], df["enrichment"], marker="s", color="#1F77B4", label="Enrichment vs global")
    ax2.set_ylabel("Enrichment ratio", color="#1F77B4")
    ax2.tick_params(axis="y", labelcolor="#1F77B4")
    ax2.axhline(1.0, color="gray", linestyle="--", linewidth=1.5)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "12_ip_degree_highrisk_enrichment_curve.png")
    plt.close()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _setup_style()
    con = duckdb.connect()

    plot_01_policy_parity(con)
    plot_02_country_concentration(con)
    plot_03_country_segment_residual(con)
    plot_04_accounts_ccdf(con)
    plot_05_kmax_breaches(con)
    plot_06_instrument_identity(con)
    plot_07_instrument_mix_residual(con)
    plot_08_device_ip_funnel(con)
    plot_09_ip_type_dumbbell(con)
    plot_10_devices_per_ip_tail(con)
    plot_11_risk_propagation(con)
    plot_12_ip_degree_enrichment(con)

    con.close()
    print("plots_written", 12)


if __name__ == "__main__":
    main()
