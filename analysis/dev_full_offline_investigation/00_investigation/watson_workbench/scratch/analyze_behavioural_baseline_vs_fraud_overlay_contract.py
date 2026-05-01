from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[5]
SOURCE_EXPORT = (
    REPO_ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "behavioural_streams"
)
BRANCH_EXPORT = SOURCE_EXPORT / "branches" / "baseline_vs_fraud_overlay_contract"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(SOURCE_EXPORT / name)


def write_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(BRANCH_EXPORT / name, index=False)


def main() -> None:
    BRANCH_EXPORT.mkdir(parents=True, exist_ok=True)

    baseline_profile = read_csv("baseline_profile.csv")
    with_fraud_profile = read_csv("with_fraud_profile.csv")
    key_fingerprint = read_csv("stream_key_fingerprint.csv")
    overlay_summary = read_csv("with_fraud_overlay_summary.csv")
    fraud_rows_vs_baseline = read_csv("fraud_rows_vs_baseline.csv")
    fraud_by_event_type = read_csv("with_fraud_flag_by_event_type.csv")
    fraud_flow_shape = read_csv("with_fraud_flow_shape_by_flag.csv")
    campaign_summary = read_csv("with_fraud_campaign_summary.csv")
    baseline_nulls = read_csv("baseline_nulls.csv")
    with_fraud_nulls = read_csv("with_fraud_nulls.csv")
    baseline_schema = read_csv("baseline_schema.csv")
    with_fraud_schema = read_csv("with_fraud_schema.csv")

    profile_rows = []
    for stream, profile in [("baseline", baseline_profile), ("with_fraud", with_fraud_profile)]:
        row = profile.iloc[0]
        profile_rows.append(
            {
                "stream": stream,
                "rows": int(row["rows"]),
                "approx_flows": int(row["approx_flows"]),
                "event_types": int(row["event_types"]),
                "min_event_seq": int(row["min_event_seq"]),
                "max_event_seq": int(row["max_event_seq"]),
                "min_ts_utc": row["min_ts_utc"],
                "max_ts_utc": row["max_ts_utc"],
                "mean_amount": row["mean_amount"],
                "median_amount": row["median_amount"],
                "p95_amount": row["p95_amount"],
                "max_amount": row["max_amount"],
                "total_amount": row["total_amount"],
            }
        )
    stream_contract_profile = pd.DataFrame(profile_rows)
    write_csv(stream_contract_profile, "stream_contract_profile.csv")

    b = baseline_profile.iloc[0]
    w = with_fraud_profile.iloc[0]
    contract_delta = pd.DataFrame(
        [
            {
                "metric": "rows",
                "baseline": b["rows"],
                "with_fraud": w["rows"],
                "delta": w["rows"] - b["rows"],
            },
            {
                "metric": "approx_flows",
                "baseline": b["approx_flows"],
                "with_fraud": w["approx_flows"],
                "delta": w["approx_flows"] - b["approx_flows"],
            },
            {
                "metric": "event_types",
                "baseline": b["event_types"],
                "with_fraud": w["event_types"],
                "delta": w["event_types"] - b["event_types"],
            },
            {
                "metric": "total_amount",
                "baseline": b["total_amount"],
                "with_fraud": w["total_amount"],
                "delta": w["total_amount"] - b["total_amount"],
            },
            {
                "metric": "mean_amount",
                "baseline": b["mean_amount"],
                "with_fraud": w["mean_amount"],
                "delta": w["mean_amount"] - b["mean_amount"],
            },
            {
                "metric": "median_amount",
                "baseline": b["median_amount"],
                "with_fraud": w["median_amount"],
                "delta": w["median_amount"] - b["median_amount"],
            },
            {
                "metric": "p95_amount",
                "baseline": b["p95_amount"],
                "with_fraud": w["p95_amount"],
                "delta": w["p95_amount"] - b["p95_amount"],
            },
        ]
    )
    write_csv(contract_delta, "baseline_with_fraud_contract_delta.csv")

    baseline_cols = set(baseline_schema["column_name"])
    with_fraud_cols = set(with_fraud_schema["column_name"])
    schema_contract = pd.DataFrame(
        [
            {
                "column": col,
                "in_baseline": col in baseline_cols,
                "in_with_fraud": col in with_fraud_cols,
                "overlay_added_column": col in with_fraud_cols and col not in baseline_cols,
            }
            for col in sorted(baseline_cols | with_fraud_cols)
        ]
    )
    write_csv(schema_contract, "schema_overlay_contract.csv")

    write_csv(key_fingerprint, "stream_key_fingerprint.csv")
    write_csv(overlay_summary, "with_fraud_overlay_summary.csv")
    write_csv(fraud_rows_vs_baseline, "fraud_rows_vs_baseline.csv")
    write_csv(fraud_by_event_type, "fraud_flag_by_event_type.csv")
    write_csv(fraud_flow_shape, "fraud_flow_shape.csv")
    write_csv(campaign_summary, "campaign_overlay_summary.csv")
    write_csv(baseline_nulls, "baseline_nulls.csv")
    write_csv(with_fraud_nulls, "with_fraud_nulls.csv")

    fraud_row = overlay_summary[overlay_summary["fraud_flag"] == True].iloc[0]
    non_fraud_row = overlay_summary[overlay_summary["fraud_flag"] == False].iloc[0]
    join_row = fraud_rows_vs_baseline.iloc[0]
    flow_shape_row = fraud_flow_shape.iloc[0]

    summary = {
        "stream_contract_profile": stream_contract_profile.to_dict(orient="records"),
        "contract_delta": contract_delta.to_dict(orient="records"),
        "schema_overlay_contract": schema_contract.to_dict(orient="records"),
        "fraud_overlay": {
            "fraud_rows": int(fraud_row["rows"]),
            "non_fraud_rows": int(non_fraud_row["rows"]),
            "fraud_row_share": float(fraud_row["row_share"]),
            "campaign_count": int(fraud_row["campaigns"]),
            "fraud_mean_amount": float(fraud_row["mean_amount"]),
            "non_fraud_mean_amount": float(non_fraud_row["mean_amount"]),
        },
        "fraud_rows_vs_baseline": {
            "fraud_rows": int(join_row["fraud_rows"]),
            "matched_baseline_rows": int(join_row["matched_baseline_rows"]),
            "missing_baseline_rows": int(join_row["missing_baseline_rows"]),
            "same_event_type_rows": int(join_row["same_event_type_rows"]),
            "same_ts_rows": int(join_row["same_ts_rows"]),
            "same_amount_rows": int(join_row["same_amount_rows"]),
            "mean_amount_delta": float(join_row["mean_amount_delta"]),
            "min_amount_delta": float(join_row["min_amount_delta"]),
            "max_amount_delta": float(join_row["max_amount_delta"]),
        },
        "fraud_flow_shape": {
            "flows": int(flow_shape_row["flows"]),
            "min_events_per_flow": int(flow_shape_row["min_events_per_flow"]),
            "median_events_per_flow": float(flow_shape_row["median_events_per_flow"]),
            "max_events_per_flow": int(flow_shape_row["max_events_per_flow"]),
            "nonstandard_flow_shapes": int(flow_shape_row["nonstandard_flow_shapes"]),
        },
    }
    (BRANCH_EXPORT / "baseline_vs_fraud_overlay_contract_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
