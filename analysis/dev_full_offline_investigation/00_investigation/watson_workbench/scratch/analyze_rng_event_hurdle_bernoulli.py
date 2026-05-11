from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import yaml


REPO = Path(__file__).resolve().parents[5]
WORKBENCH = REPO / "analysis" / "dev_full_offline_investigation" / "00_investigation" / "watson_workbench"
EXPORTS = WORKBENCH / "exports" / "rng_event_hurdle_bernoulli"
EXPORTS.mkdir(parents=True, exist_ok=True)

RUN_ID = "a3bd8cac9a4284cd36072c6b9624a0c1"
SEED = 42
PARAMETER_HASH = "0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00"
MANIFEST_FINGERPRINT = "76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460"

RUN_DIR = REPO / "runs" / "local_full_run-7" / RUN_ID
EVENT_PATH = (
    RUN_DIR
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
TRACE_PATH = (
    RUN_DIR
    / "logs"
    / "layer1"
    / "1A"
    / "rng"
    / "trace"
    / f"seed={SEED}"
    / f"parameter_hash={PARAMETER_HASH}"
    / f"run_id={RUN_ID}"
    / "rng_trace_log.jsonl"
)
DESIGN_PATH = (
    RUN_DIR
    / "data"
    / "layer1"
    / "1A"
    / "hurdle_design_matrix"
    / f"parameter_hash={PARAMETER_HASH}"
    / "part-00000.parquet"
)
PI_PATH = (
    RUN_DIR
    / "data"
    / "layer1"
    / "1A"
    / "hurdle_pi_probs"
    / f"parameter_hash={PARAMETER_HASH}"
    / "part-00000.parquet"
)
MERCHANT_PATH = REPO / "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"
ACTIVE_BUNDLE = REPO / "config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml"


def load_jsonl(path: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def normalize_channel(value: str) -> str:
    if value == "card_present":
        return "CP"
    if value == "card_not_present":
        return "CNP"
    return value


def sigmoid(x: np.ndarray) -> np.ndarray:
    out = np.empty_like(x, dtype=float)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    exp_x = np.exp(x[~pos])
    out[~pos] = exp_x / (1.0 + exp_x)
    return out


def recompute_pi(design: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    dict_mcc = [int(x) for x in bundle["dict_mcc"]]
    dict_ch = list(bundle["dict_ch"])
    dict_dev5 = [int(x) for x in bundle["dict_dev5"]]
    beta = np.array(bundle["beta"], dtype=float)

    mcc_start = 1
    ch_start = mcc_start + len(dict_mcc)
    bucket_start = ch_start + len(dict_ch)

    mcc_terms = {mcc: beta[mcc_start + idx] for idx, mcc in enumerate(dict_mcc)}
    ch_terms = {ch: beta[ch_start + idx] for idx, ch in enumerate(dict_ch)}
    bucket_terms = {bucket: beta[bucket_start + idx] for idx, bucket in enumerate(dict_dev5)}

    channel_norm = design["channel"].map(normalize_channel)
    eta = (
        beta[0]
        + design["mcc"].map(mcc_terms).astype(float)
        + channel_norm.map(ch_terms).astype(float)
        + design["gdp_bucket_id"].map(bucket_terms).astype(float)
    )
    return pd.DataFrame(
        {
            "merchant_id": design["merchant_id"],
            "recomputed_logit": eta,
            "recomputed_pi": sigmoid(eta.to_numpy(dtype=float)),
        }
    )


def summarize_stratum(df: pd.DataFrame, keys: list[str], *, top_n: int | None = None) -> pd.DataFrame:
    grouped = (
        df.groupby(keys, dropna=False)
        .agg(
            merchants=("merchant_id", "size"),
            expected_multi=("event_pi", "sum"),
            realized_multi=("is_multi", "sum"),
            mean_pi=("event_pi", "mean"),
            variance=("event_pi", lambda s: float(np.sum(s.to_numpy() * (1.0 - s.to_numpy())))),
        )
        .reset_index()
    )
    grouped["realized_rate"] = grouped["realized_multi"] / grouped["merchants"]
    grouped["expected_rate"] = grouped["expected_multi"] / grouped["merchants"]
    grouped["residual_count"] = grouped["realized_multi"] - grouped["expected_multi"]
    grouped["residual_rate_pp"] = (grouped["realized_rate"] - grouped["expected_rate"]) * 100.0
    grouped["residual_z"] = grouped.apply(
        lambda row: row["residual_count"] / math.sqrt(row["variance"]) if row["variance"] > 0 else np.nan,
        axis=1,
    )
    grouped = grouped.sort_values(["merchants", "expected_multi"], ascending=[False, False])
    if top_n is not None:
        grouped = grouped.head(top_n)
    return grouped


def main() -> None:
    events = load_jsonl(EVENT_PATH)
    trace = load_jsonl(TRACE_PATH)
    design = pl.read_parquet(DESIGN_PATH).to_pandas()
    pi_probs = pl.read_parquet(PI_PATH).to_pandas()
    merchant = pl.read_parquet(MERCHANT_PATH).to_pandas()
    bundle = yaml.safe_load(ACTIVE_BUNDLE.read_text(encoding="utf-8"))

    events = events.rename(columns={"pi": "event_pi"})
    events["draws_int"] = events["draws"].astype(int)
    events["decision_from_u"] = events["u"] < events["event_pi"]

    scored = recompute_pi(design, bundle)
    joined = (
        events.merge(design, on="merchant_id", how="left", suffixes=("", "_design"))
        .merge(pi_probs.rename(columns={"logit": "diag_logit", "pi": "diag_pi"}), on="merchant_id", how="left")
        .merge(scored, on="merchant_id", how="left")
        .merge(merchant[["merchant_id", "home_country_iso"]], on="merchant_id", how="left")
    )

    joined["pi_minus_diag_pi"] = joined["event_pi"] - joined["diag_pi"]
    joined["pi_minus_recomputed_pi"] = joined["event_pi"] - joined["recomputed_pi"]
    joined["logit_minus_recomputed_logit"] = joined["recomputed_logit"] - joined["diag_logit"]
    joined["counter_delta_hi"] = joined["rng_counter_after_hi"] - joined["rng_counter_before_hi"]
    joined["counter_delta_lo"] = joined["rng_counter_after_lo"] - joined["rng_counter_before_lo"]

    variance = float(np.sum(joined["event_pi"].to_numpy() * (1.0 - joined["event_pi"].to_numpy())))
    expected_multi = float(joined["event_pi"].sum())
    realized_multi = int(joined["is_multi"].sum())
    residual = realized_multi - expected_multi

    hurdle_trace = trace.loc[trace["substream_label"] == "hurdle_bernoulli"].copy()

    summary = {
        "paths": {
            "event": str(EVENT_PATH.relative_to(REPO)).replace("\\", "/"),
            "trace": str(TRACE_PATH.relative_to(REPO)).replace("\\", "/"),
            "design_matrix": str(DESIGN_PATH.relative_to(REPO)).replace("\\", "/"),
            "pi_probs": str(PI_PATH.relative_to(REPO)).replace("\\", "/"),
            "active_bundle": str(ACTIVE_BUNDLE.relative_to(REPO)).replace("\\", "/"),
        },
        "coverage": {
            "event_rows": int(len(events)),
            "event_distinct_merchants": int(events["merchant_id"].nunique()),
            "design_rows": int(len(design)),
            "design_distinct_merchants": int(design["merchant_id"].nunique()),
            "pi_rows": int(len(pi_probs)),
            "pi_distinct_merchants": int(pi_probs["merchant_id"].nunique()),
            "merchant_rows": int(len(merchant)),
            "merchant_distinct_merchants": int(merchant["merchant_id"].nunique()),
            "missing_design_rows_after_join": int(joined["mcc"].isna().sum()),
            "missing_pi_rows_after_join": int(joined["diag_pi"].isna().sum()),
            "missing_country_after_join": int(joined["home_country_iso"].isna().sum()),
        },
        "lineage": {
            "seed_values": sorted(events["seed"].dropna().unique().tolist()),
            "parameter_hash_values": sorted(events["parameter_hash"].dropna().unique().tolist()),
            "manifest_fingerprint_values": sorted(events["manifest_fingerprint"].dropna().unique().tolist()),
            "run_id_values": sorted(events["run_id"].dropna().unique().tolist()),
            "module_values": sorted(events["module"].dropna().unique().tolist()),
            "substream_label_values": sorted(events["substream_label"].dropna().unique().tolist()),
        },
        "branch_surface": {
            "expected_multi": expected_multi,
            "realized_multi": realized_multi,
            "single_site": int(len(joined) - realized_multi),
            "expected_multi_rate": expected_multi / len(joined),
            "realized_multi_rate": realized_multi / len(joined),
            "residual_count": residual,
            "residual_rate_pp": (realized_multi / len(joined) - expected_multi / len(joined)) * 100.0,
            "bernoulli_variance": variance,
            "bernoulli_sd": math.sqrt(variance),
            "residual_z": residual / math.sqrt(variance),
            "pi_min": float(joined["event_pi"].min()),
            "pi_p05": float(joined["event_pi"].quantile(0.05)),
            "pi_median": float(joined["event_pi"].median()),
            "pi_mean": float(joined["event_pi"].mean()),
            "pi_p95": float(joined["event_pi"].quantile(0.95)),
            "pi_max": float(joined["event_pi"].max()),
        },
        "rng_accounting": {
            "deterministic_true": int(joined["deterministic"].sum()),
            "deterministic_false": int((~joined["deterministic"]).sum()),
            "draws_0": int((joined["draws_int"] == 0).sum()),
            "draws_1": int((joined["draws_int"] == 1).sum()),
            "blocks_0": int((joined["blocks"] == 0).sum()),
            "blocks_1": int((joined["blocks"] == 1).sum()),
            "u_null": int(joined["u"].isna().sum()),
            "u_non_null": int(joined["u"].notna().sum()),
            "u_min": float(joined["u"].min()),
            "u_mean": float(joined["u"].mean()),
            "u_median": float(joined["u"].median()),
            "u_max": float(joined["u"].max()),
            "decision_mismatches": int((joined["decision_from_u"] != joined["is_multi"]).sum()),
            "counter_hi_delta_nonzero": int((joined["counter_delta_hi"] != 0).sum()),
            "counter_lo_delta_not_one": int((joined["counter_delta_lo"] != 1).sum()),
        },
        "probability_alignment": {
            "max_abs_event_minus_diag_pi": float(joined["pi_minus_diag_pi"].abs().max()),
            "mean_abs_event_minus_diag_pi": float(joined["pi_minus_diag_pi"].abs().mean()),
            "max_abs_event_minus_recomputed_pi": float(joined["pi_minus_recomputed_pi"].abs().max()),
            "mean_abs_event_minus_recomputed_pi": float(joined["pi_minus_recomputed_pi"].abs().mean()),
            "max_abs_logit_recomputed_minus_diag": float(joined["logit_minus_recomputed_logit"].abs().max()),
        },
        "trace": {
            "trace_rows": int(len(trace)),
            "hurdle_trace_rows": int(len(hurdle_trace)),
            "trace_module_values": sorted(trace["module"].dropna().unique().tolist()) if not trace.empty else [],
            "trace_substream_values": sorted(trace["substream_label"].dropna().unique().tolist()) if not trace.empty else [],
            "hurdle_events_total_max": int(hurdle_trace["events_total"].max()) if "events_total" in hurdle_trace.columns else None,
            "hurdle_draws_total_max": int(hurdle_trace["draws_total"].astype(str).astype(int).max()) if "draws_total" in hurdle_trace.columns else None,
            "hurdle_blocks_total_max": int(hurdle_trace["blocks_total"].astype(str).astype(int).max()) if "blocks_total" in hurdle_trace.columns else None,
        },
    }

    by_channel = summarize_stratum(joined, ["channel"])
    by_bucket = summarize_stratum(joined, ["gdp_bucket_id"])
    by_channel_bucket = summarize_stratum(joined, ["channel", "gdp_bucket_id"])
    by_country = summarize_stratum(joined, ["home_country_iso"], top_n=25)
    by_mcc = summarize_stratum(joined, ["mcc"], top_n=25)
    decile_source = joined.sort_values("event_pi").copy()
    decile_source["pi_decile"] = pd.qcut(decile_source["event_pi"], q=10, labels=False, duplicates="drop") + 1
    by_decile = summarize_stratum(decile_source, ["pi_decile"]).sort_values("pi_decile")

    by_channel.to_csv(EXPORTS / "rng_event_hurdle_bernoulli_by_channel.csv", index=False)
    by_bucket.to_csv(EXPORTS / "rng_event_hurdle_bernoulli_by_gdp_bucket.csv", index=False)
    by_channel_bucket.to_csv(EXPORTS / "rng_event_hurdle_bernoulli_by_channel_bucket.csv", index=False)
    by_country.to_csv(EXPORTS / "rng_event_hurdle_bernoulli_top_country_summary.csv", index=False)
    by_mcc.to_csv(EXPORTS / "rng_event_hurdle_bernoulli_top_mcc_summary.csv", index=False)
    by_decile.to_csv(EXPORTS / "rng_event_hurdle_bernoulli_pi_deciles.csv", index=False)
    (EXPORTS / "rng_event_hurdle_bernoulli_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote: {EXPORTS.relative_to(REPO)}")


if __name__ == "__main__":
    main()
