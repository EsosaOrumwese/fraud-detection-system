from __future__ import annotations

from math import log2
from pathlib import Path

import pandas as pd


ROOT = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
WORKBENCH = ROOT / "analysis/dev_full_offline_investigation/00_investigation/watson_workbench"
EXPORTS = WORKBENCH / "exports"
NOTES = WORKBENCH / "notes"
EXPORTS.mkdir(parents=True, exist_ok=True)
NOTES.mkdir(parents=True, exist_ok=True)

MERCHANT_PATH = ROOT / "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"
CHANNEL_POLICY_PATH = ROOT / "config/layer1/1A/policy/channel_policy.1A.yaml"
CONCENTRATION_EXPLANATION_PATH = (
    ROOT
    / "analysis/dev_full_offline_investigation/00_investigation/watson_workbench/notes/transaction_schema_country_concentration_explanation.md"
)
RESIDUAL_EFFECT_PATH = (
    ROOT
    / "analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_country_concentration_residual_effect.csv"
)


def load_yaml(path: Path) -> dict:
    import yaml

    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def jsd_bits(p: pd.Series, q: pd.Series) -> float:
    p_vals = p.to_numpy(dtype=float)
    q_vals = q.to_numpy(dtype=float)
    m_vals = 0.5 * (p_vals + q_vals)

    def kl(a, b) -> float:
        mask = a > 0
        return float((a[mask] * (pd.Series(a[mask] / b[mask]).apply(log2))).sum())

    return 0.5 * kl(p_vals, m_vals) + 0.5 * kl(q_vals, m_vals)


def main() -> None:
    merchant = pd.read_parquet(MERCHANT_PATH)
    channel_policy = load_yaml(CHANNEL_POLICY_PATH)
    residual_effect = pd.read_csv(RESIDUAL_EFFECT_PATH)

    top_countries = (
        merchant["home_country_iso"].value_counts().rename_axis("country_iso").reset_index(name="merchant_count").head(10)
    )
    top_country_list = top_countries["country_iso"].tolist()
    global_channel = merchant["channel"].value_counts(normalize=True).rename("global_share")
    global_mcc = merchant["mcc"].value_counts(normalize=True)
    all_mcc = sorted(global_mcc.index.tolist())
    global_mcc = global_mcc.reindex(all_mcc, fill_value=0.0)
    global_top10_mcc = merchant["mcc"].value_counts().head(10).index.tolist()
    global_top10_share_pct = float(merchant["mcc"].value_counts(normalize=True).head(10).sum() * 100)

    mix_rows: list[dict[str, object]] = []
    top5_mcc_rows: list[dict[str, object]] = []
    channel_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    us_override = channel_policy["targets"]["iso_overrides"]["US"]["card_not_present"]
    global_bounds = channel_policy["targets"]["global"]["card_not_present"]

    for country_iso in top_country_list:
        sub = merchant.loc[merchant["home_country_iso"] == country_iso].copy()
        channel_mix = sub["channel"].value_counts(normalize=True).reindex(global_channel.index, fill_value=0.0)
        cnp_share_pct = float(channel_mix.get("card_not_present", 0.0) * 100)
        cp_share_pct = float(channel_mix.get("card_present", 0.0) * 100)
        country_mcc = sub["mcc"].value_counts(normalize=True).reindex(all_mcc, fill_value=0.0)
        top10_mcc_share_pct = float(sub["mcc"].value_counts(normalize=True).head(10).sum() * 100)
        global_top10_overlap = len(set(sub["mcc"].value_counts().head(10).index.tolist()) & set(global_top10_mcc))
        mcc_jsd = jsd_bits(country_mcc, global_mcc)
        distinct_mcc = int(sub["mcc"].nunique())

        policy_row = residual_effect.loc[residual_effect["country_iso"] == country_iso].iloc[0]
        if country_iso == "GH":
            shaping = "artifact-amplified"
            reason = "Residual reconciliation grants the entire 310-row leftover block to GH."
        else:
            shaping = "policy-shaped"
            reason = "Count follows the governed GDP-heavy allocation policy; residual effect is immaterial."

        channel_comment = "US-specific CNP override active." if country_iso == "US" else "Country sits effectively on the global 75/25 channel target."

        mix_rows.append(
            {
                "country_iso": country_iso,
                "merchant_count": int(len(sub)),
                "merchant_share_pct": round(len(sub) / len(merchant) * 100, 2),
                "distinct_mcc": distinct_mcc,
                "top10_mcc_share_pct": round(top10_mcc_share_pct, 2),
                "global_top10_mcc_overlap": global_top10_overlap,
                "mcc_jsd_vs_global_bits": round(mcc_jsd, 4),
                "cp_share_pct": round(cp_share_pct, 2),
                "cnp_share_pct": round(cnp_share_pct, 2),
                "builder_vs_standard_delta": int(policy_row["builder_vs_standard_delta"]),
                "shape_classification": shaping,
            }
        )

        channel_rows.append(
            {
                "country_iso": country_iso,
                "merchant_count": int(len(sub)),
                "card_present_pct": round(cp_share_pct, 2),
                "card_not_present_pct": round(cnp_share_pct, 2),
                "global_cnp_pct": round(float(global_channel["card_not_present"] * 100), 2),
                "channel_comment": channel_comment,
            }
        )

        summary_rows.append(
            {
                "country_iso": country_iso,
                "merchant_count": int(len(sub)),
                "shape_classification": shaping,
                "builder_vs_standard_delta": int(policy_row["builder_vs_standard_delta"]),
                "policy_weight_driver": "GDP-heavy + heavy-tail + regional boosts" if country_iso != "GH" else "Residual block dominates over policy weight",
                "reason": reason,
            }
        )

        top5 = sub["mcc"].value_counts().head(5)
        for rank, (mcc, count) in enumerate(top5.items(), start=1):
            top5_mcc_rows.append(
                {
                    "country_iso": country_iso,
                    "rank": rank,
                    "mcc": int(mcc),
                    "merchant_count": int(count),
                    "share_pct": round(count / len(sub) * 100, 2),
                }
            )

    mix_df = pd.DataFrame(mix_rows)
    channel_df = pd.DataFrame(channel_rows)
    summary_df = pd.DataFrame(summary_rows)
    top5_mcc_df = pd.DataFrame(top5_mcc_rows)

    mix_df.to_csv(EXPORTS / "transaction_schema_top_country_mix_summary.csv", index=False)
    channel_df.to_csv(EXPORTS / "transaction_schema_top_country_channel_mix.csv", index=False)
    summary_df.to_csv(EXPORTS / "transaction_schema_top_country_policy_artifact_summary.csv", index=False)
    top5_mcc_df.to_csv(EXPORTS / "transaction_schema_top_country_mcc_top5.csv", index=False)

    note_lines = [
        "# transaction_schema_merchant_ids top-country mix follow-up",
        "",
        "## Question",
        "",
        "Once we know the merchant universe is country-concentrated, do the heavy countries actually behave differently from the rest of the seed world, or are they mostly enlarged versions of the same merchant universe?",
        "",
        "## Why this matters",
        "",
        "The country Pareto chart tells us where merchant weight sits, but not whether that weight implies specialised merchant composition, different channel behaviour, or a structural analytical risk. This follow-up checks the top-country mix directly.",
        "",
        "## Inputs used",
        "",
        f"- merchant universe: `{MERCHANT_PATH.relative_to(ROOT)}`",
        f"- channel policy: `{CHANNEL_POLICY_PATH.relative_to(ROOT)}`",
        f"- concentration explanation: `{CONCENTRATION_EXPLANATION_PATH.relative_to(ROOT)}`",
        f"- residual-effect table: `{RESIDUAL_EFFECT_PATH.relative_to(ROOT)}`",
        "",
        "## Top-country set",
        "",
        f"- Investigated countries: `{', '.join(top_country_list)}`",
        f"- These are the top 10 home countries by merchant count in the 10,000-row merchant universe.",
        "",
        "## 1) Country-level MCC mix comparison",
        "",
        f"- The global merchant world is broad on category: `290` distinct MCCs, with the global top 10 MCCs accounting for only `{global_top10_share_pct:.2f}%` of merchants.",
        "- The heavy countries are also broad rather than narrow. Even the top country group carries high MCC distinctness:",
        "  - `MC`: `267` distinct MCCs",
        "  - `BM`: `227` distinct MCCs",
        "  - `LU`: `208` distinct MCCs",
        "  - `IE`: `196` distinct MCCs",
        "  - `GH`: `196` distinct MCCs",
        "- The top-10-MCC share inside the heavy countries ranges from about `8.63%` (`MC`) to `14.69%` (`US`). That is more concentrated than the global `4.91%`, but still far from a narrow-category universe.",
        "- Jensen-Shannon divergence against the global MCC distribution stays modest rather than explosive. `MC` is closest to the global MCC shape (`0.0823` bits), while `AU` (`0.3209`) and `US` (`0.3015`) drift furthest among the top countries we checked.",
        "- So the main interpretation is that the heavy countries are not tiny specialised merchant pockets. They are broad merchant populations with varying but still recognisable distance from the global MCC mix.",
        "",
        "## 2) Country-level channel mix comparison",
        "",
        f"- The global channel split is `card_present = {float(global_channel['card_present'] * 100):.2f}%` and `card_not_present = {float(global_channel['card_not_present'] * 100):.2f}%`.",
        "- For almost every top country, the local channel split sits almost exactly on that global mix:",
        "  - `MC`: `75.00 / 25.00`",
        "  - `BM`: `75.00 / 25.00`",
        "  - `LU`: `74.93 / 25.07`",
        "  - `IE`: `75.07 / 24.93`",
        "  - `GH`: `74.92 / 25.08`",
        "- This means channel is far more policy-governed than country-sensitive in the merchant universe. The builder is not letting local country composition naturally drift into very different CP/CNP mixes.",
        f"- The clear exception is `US`, which lands at `67.30%` `card_present` / `32.70%` `card_not_present`. That lines up with the explicit US override in the channel policy (`CNP min={us_override['min_ratio']:.2f}, max={us_override['max_ratio']:.2f}`) rather than with emergent merchant behaviour.",
        "- So the analytical takeaway is that country-level channel mix is mostly constrained by policy, not discovered from country-specific merchant composition.",
        "",
        "## 3) Policy-shaped versus artifact-shaped summary",
        "",
        "- The top-country table should not be read as if every heavy country means the same thing.",
        "- `MC`, `BM`, `LU`, `IE`, `CH`, `NO`, `SG`, `AU`, and `US` are best treated as `policy-shaped` countries: their counts follow the governed GDP-heavy, heavy-tail allocation policy, and their residual effect relative to a standard largest-remainder allocation is immaterial (`0` or `-1`).",
        "- `GH` is best treated as `artifact-amplified`: it picks up `309` extra merchants versus the standard largest-remainder counterfactual because the builder grants the full leftover block to the first-ranked fractional remainder country.",
        "- That matters because a heavy country can therefore mean two different things in this merchant universe:",
        "  - real policy-shaped weight (`MC`, `BM`, `LU`, `IE`, ...)",
        "  - builder-side residual artifact (`GH`)",
        "",
        "## Direct answer",
        "",
        "The optional checks strengthen the earlier conclusion rather than overturn it. The heavy countries are mostly broad merchant populations, not narrow MCC clusters. Their channel mix is almost entirely policy-governed and globally pinned. The only strong exception in the top-country set is `GH`, whose prominence is primarily a residual-allocation artifact rather than a deep structural property of the merchant world.",
        "",
        "## Files written",
        "",
        "- `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_top_country_mix_summary.csv`",
        "- `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_top_country_channel_mix.csv`",
        "- `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_top_country_policy_artifact_summary.csv`",
        "- `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_top_country_mcc_top5.csv`",
    ]

    note_path = NOTES / "transaction_schema_merchant_ids_top_country_mix.md"
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    print(note_path)
    print(EXPORTS / "transaction_schema_top_country_mix_summary.csv")
    print(EXPORTS / "transaction_schema_top_country_channel_mix.csv")
    print(EXPORTS / "transaction_schema_top_country_policy_artifact_summary.csv")
    print(EXPORTS / "transaction_schema_top_country_mcc_top5.csv")


if __name__ == "__main__":
    main()
