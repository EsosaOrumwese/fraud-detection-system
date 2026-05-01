from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[5]
BASE_EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "behavioural_streams"
)
EXPORT_DIR = BASE_EXPORT_DIR / "branches" / "event_grammar_and_grain"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(BASE_EXPORT_DIR / name)


def write_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(EXPORT_DIR / name, index=False)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    baseline_seq = read_csv("baseline_event_seq_summary.csv")
    with_fraud_seq = read_csv("with_fraud_event_seq_summary.csv")
    baseline_profile = read_csv("baseline_profile.csv").iloc[0]
    with_fraud_profile = read_csv("with_fraud_profile.csv").iloc[0]
    key_fingerprint = read_csv("stream_key_fingerprint.csv")
    fraud_by_event_type = read_csv("with_fraud_flag_by_event_type.csv")

    event_seq_type_shape = pd.concat(
        [
            baseline_seq.assign(stream_name="baseline"),
            with_fraud_seq.assign(stream_name="with_fraud"),
        ],
        ignore_index=True,
    )[
        ["stream_name", "event_seq", "event_type", "rows", "approx_flows"]
    ]
    event_seq_type_shape["row_share_within_stream"] = event_seq_type_shape.groupby("stream_name")["rows"].transform(
        lambda s: s / s.sum()
    )
    write_csv(event_seq_type_shape, "event_seq_type_shape.csv")

    grain_rows = []
    for stream_name, profile, seq_df in [
        ("baseline", baseline_profile, baseline_seq),
        ("with_fraud", with_fraud_profile, with_fraud_seq),
    ]:
        seq0_rows = int(seq_df.loc[seq_df["event_seq"] == 0, "rows"].iloc[0])
        seq1_rows = int(seq_df.loc[seq_df["event_seq"] == 1, "rows"].iloc[0])
        event_rows = int(profile["rows"])
        grain_rows.append(
            {
                "stream_name": stream_name,
                "event_rows": event_rows,
                "seq0_request_rows": seq0_rows,
                "seq1_response_rows": seq1_rows,
                "seq0_minus_seq1_rows": seq0_rows - seq1_rows,
                "implied_flows_from_balanced_sequence": seq0_rows,
                "event_rows_per_implied_flow": event_rows / seq0_rows,
                "event_types": int(profile["event_types"]),
                "min_event_seq": int(profile["min_event_seq"]),
                "max_event_seq": int(profile["max_event_seq"]),
                "distinct_event_seq": int(profile["distinct_event_seq"]),
            }
        )
    stream_grain = pd.DataFrame(grain_rows)
    write_csv(stream_grain, "stream_event_flow_grain.csv")

    # The event type summary is sequence-equivalent in this stream because seq 0 is
    # AUTH_REQUEST and seq 1 is AUTH_RESPONSE. This avoids another raw stream scan.
    baseline_type = read_csv("baseline_event_type_summary.csv").assign(stream_name="baseline")
    with_fraud_type = read_csv("with_fraud_event_type_summary.csv").assign(stream_name="with_fraud")
    amount_by_side = pd.concat([baseline_type, with_fraud_type], ignore_index=True)[
        ["stream_name", "event_type", "rows", "row_share", "mean_amount", "median_amount", "max_amount"]
    ]
    write_csv(amount_by_side, "amount_surface_by_event_side.csv")

    event_type_to_seq = {"AUTH_REQUEST": 0, "AUTH_RESPONSE": 1}
    fraud_balance = fraud_by_event_type.copy()
    fraud_balance["event_seq"] = fraud_balance["event_type"].map(event_type_to_seq)
    fraud_balance = fraud_balance[
        ["event_seq", "event_type", "fraud_flag", "rows", "approx_flows", "share_within_event_type"]
    ].sort_values(["event_seq", "fraud_flag"])
    write_csv(fraud_balance, "fraud_balance_by_event_side.csv")

    write_csv(key_fingerprint, "baseline_overlay_key_fingerprint.csv")

    summary = {
        "stream_event_flow_grain": stream_grain.to_dict(orient="records"),
        "event_seq_type_shape": event_seq_type_shape.to_dict(orient="records"),
        "amount_surface_by_event_side": amount_by_side.to_dict(orient="records"),
        "fraud_balance_by_event_side": fraud_balance.to_dict(orient="records"),
        "baseline_overlay_key_fingerprint": key_fingerprint.to_dict(orient="records"),
    }
    with (EXPORT_DIR / "event_grammar_and_grain_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
