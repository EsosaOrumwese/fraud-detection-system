"""Build 3B MCC x channel virtual-classification rules (v1)."""
from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Dict

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MCC_PATH = (
    "reference/industry/mcc_canonical/2025-12-31/mcc_canonical.parquet"
)
DEFAULT_MERCHANT_PATH = (
    "reference/layer1/transaction_schema_merchant_ids/2025-12-31/"
    "transaction_schema_merchant_ids.parquet"
)
DEFAULT_OUT_PATH = "config/virtual/mcc_channel_rules.yaml"

KW = {
    "digital",
    "online",
    "internet",
    "web",
    "software",
    "cloud",
    "streaming",
    "subscription",
    "telecom",
    "telephone",
    "communications",
    "data",
    "information services",
    "computer",
    "gaming",
    "video",
    "music",
    "app",
    "hosting",
    "saas",
    "direct marketing",
    "mail order",
    "e-commerce",
    "electronic",
}


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def score_description(description: str) -> int:
    normalized = normalize_text(description)
    hits = {kw for kw in KW if kw in normalized}
    return len(hits)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcc-path", default=DEFAULT_MCC_PATH)
    parser.add_argument("--merchant-path", default=DEFAULT_MERCHANT_PATH)
    parser.add_argument("--out-path", default=DEFAULT_OUT_PATH)
    parser.add_argument("--version", default="v1.0.0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mcc_path = ROOT / args.mcc_path
    merchant_path = ROOT / args.merchant_path
    out_path = ROOT / args.out_path

    mcc_df = pl.read_parquet(mcc_path)
    if "mcc" not in mcc_df.columns or "description" not in mcc_df.columns:
        raise RuntimeError("mcc_canonical missing required columns")
    mcc_df = mcc_df.select("mcc", "description")
    mcc_codes = mcc_df.get_column("mcc").to_list()
    descriptions = mcc_df.get_column("description").to_list()

    mcc_desc: Dict[str, str] = {}
    for code, desc in zip(mcc_codes, descriptions):
        mcc_str = f"{int(code):04d}"
        if mcc_str in mcc_desc:
            raise RuntimeError(f"Duplicate MCC in canonical list: {mcc_str}")
        mcc_desc[mcc_str] = "" if desc is None else str(desc)

    mcc_dom = sorted(mcc_desc.keys())
    if len(mcc_dom) < 200:
        raise RuntimeError("MCC domain too small for 3B rules")

    scores = {mcc: score_description(mcc_desc[mcc]) for mcc in mcc_dom}

    merchant_df = pl.read_parquet(merchant_path)
    for col in ("merchant_id", "mcc", "channel"):
        if col not in merchant_df.columns:
            raise RuntimeError("merchant_ids missing required columns")

    merchant_mccs = {
        f"{int(code):04d}" for code in merchant_df.get_column("mcc").to_list()
    }
    missing_mcc = sorted(merchant_mccs - set(mcc_dom))
    if missing_mcc:
        raise RuntimeError(f"merchant_ids contains unknown MCCs: {missing_mcc[:10]}")

    cnp_df = merchant_df.filter(pl.col("channel") == "card_not_present")
    total_cnp = cnp_df.height
    if total_cnp == 0:
        raise RuntimeError("No card_not_present merchants found")

    counts = cnp_df.group_by("mcc").len()
    count_by_mcc = {
        f"{int(row[0]):04d}": int(row[1]) for row in counts.iter_rows()
    }

    ranked = sorted(mcc_dom, key=lambda m: (-scores[m], m))
    p_min = 0.04
    p_max = 0.20
    p_target = 0.12

    cumulative = 0
    selected_k = None
    for idx, mcc in enumerate(ranked, start=1):
        cumulative += count_by_mcc.get(mcc, 0)
        share = cumulative / total_cnp
        if share >= p_target and share <= p_max:
            selected_k = idx
            break

    if selected_k is None:
        cumulative = 0
        for idx, mcc in enumerate(ranked, start=1):
            cumulative += count_by_mcc.get(mcc, 0)
            share = cumulative / total_cnp
            if share >= p_min and share <= p_max:
                selected_k = idx
                break

    if selected_k is None:
        raise RuntimeError("Unable to satisfy virtual share corridor for CNP")

    vset = set(ranked[:selected_k])
    cnp_virtual = sum(
        count_by_mcc.get(mcc, 0) for mcc in vset
    )
    cnp_share = cnp_virtual / total_cnp
    if not (p_min <= cnp_share <= p_max):
        raise RuntimeError("CNP virtual share outside corridor")

    total_merchants = merchant_df.height
    overall_share = cnp_virtual / total_merchants
    if not (0.01 <= overall_share <= 0.15):
        raise RuntimeError("Overall virtual share outside corridor")

    rules = []
    for mcc in mcc_dom:
        score = scores[mcc]
        decision = "virtual" if mcc in vset else "physical"
        rules.append(
            {
                "mcc": mcc,
                "channel": "card_not_present",
                "decision": decision,
                "notes": f"v1:cnp=>{decision};score={score}",
            }
        )
        rules.append(
            {
                "mcc": mcc,
                "channel": "card_present",
                "decision": "physical",
                "notes": "v1:card_present=>physical",
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"version: {args.version}", "rules:"]
    for rule in rules:
        lines.append(f"  - mcc: \"{rule['mcc']}\"")
        lines.append(f"    channel: {rule['channel']}")
        lines.append(f"    decision: {rule['decision']}")
        lines.append(f"    notes: \"{rule['notes']}\"")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
