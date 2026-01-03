from __future__ import annotations

import argparse
import hashlib
from collections import OrderedDict
from pathlib import Path

import polars as pl
import yaml


SECTOR_KEYWORDS = {
    "digital_services": [
        "digital",
        "online",
        "internet",
        "software",
        "cloud",
        "streaming",
        "subscription",
        "hosting",
        "telecom",
    ],
    "general_retail": [
        "retail",
        "store",
        "apparel",
        "merchandise",
        "shopping",
        "department",
    ],
    "grocery_pharmacy": [
        "grocery",
        "supermarket",
        "food",
        "pharmacy",
        "drug",
    ],
    "fuel_auto": [
        "fuel",
        "gas",
        "gasoline",
        "petroleum",
        "auto",
        "automotive",
        "service station",
    ],
    "travel_hospitality": [
        "airline",
        "travel",
        "hotel",
        "lodging",
        "car rental",
        "railway",
        "cruise",
    ],
    "dining_entertainment": [
        "restaurant",
        "dining",
        "bar",
        "nightclub",
        "cinema",
        "entertainment",
        "gambling",
        "amusement",
    ],
    "cash_fin_services": [
        "atm",
        "financial",
        "bank",
        "money",
        "securities",
        "insurance",
        "cash",
    ],
    "utilities_bills": [
        "utility",
        "electric",
        "gas utility",
        "water",
        "telecommunications bill",
        "cable",
        "internet bill",
    ],
    "government_education": [
        "government",
        "tax",
        "tuition",
        "education",
        "university",
        "school",
    ],
}

SECTOR_PRIORITY = [
    "digital_services",
    "cash_fin_services",
    "travel_hospitality",
    "dining_entertainment",
    "grocery_pharmacy",
    "fuel_auto",
    "utilities_bills",
    "government_education",
    "general_retail",
    "other",
]


def _score_sector(description: str) -> str:
    desc = description.lower()
    scores = {}
    for sector, keywords in SECTOR_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in desc:
                score += 1
        scores[sector] = score
    max_score = max(scores.values()) if scores else 0
    if max_score == 0:
        return "other"
    tied = [sector for sector, score in scores.items() if score == max_score]
    for sector in SECTOR_PRIORITY:
        if sector in tied:
            return sector
    return "other"


def _channel_group_map(channels: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for channel in sorted(channels):
        value = channel.lower()
        if "not_present" in value or value == "ecom":
            mapping[channel] = "card_not_present"
        elif "present" in value or value == "pos":
            mapping[channel] = "card_present"
        elif value == "mixed":
            mapping[channel] = "mixed"
        else:
            raise ValueError(f"Unsupported channel value: {channel}")
    return mapping


def _demand_class_catalog() -> list[dict[str, str]]:
    classes = [
        ("office_hours", "Business/office hours; weekday daytime concentration.", "office_weekly"),
        ("consumer_daytime", "Daytime consumer spending; lunch/afternoon bias.", "consumer_weekly"),
        ("evening_weekend", "Evening + weekend spending; nightlife/entertainment skew.", "evening_weekly"),
        ("always_on_local", "Always-on local; near-continuous baseline.", "always_weekly"),
        ("online_24h", "Online spending; 24/7 with mild circadian structure.", "online_weekly"),
        ("online_bursty", "Online bursty; campaign-like spikes / high variance.", "bursty_weekly"),
        ("travel_hospitality", "Travel/hospitality; weekend/season effects via overlays.", "travel_weekly"),
        ("fuel_convenience", "Fuel/convenience; commute peaks.", "fuel_weekly"),
        ("bills_utilities", "Bills/utilities; steady weekday bias.", "bills_weekly"),
        ("low_volume_tail", "Very low activity; sparse across week.", "low_weekly"),
    ]
    rows = []
    for demand_class, description, family in classes:
        rows.append(
            OrderedDict(
                demand_class=demand_class,
                description=description,
                intended_shape_family=family,
            )
        )
    return sorted(rows, key=lambda row: row["demand_class"])


def _decision_tree() -> OrderedDict:
    card_present = OrderedDict(
        digital_services="office_hours",
        general_retail="consumer_daytime",
        grocery_pharmacy="consumer_daytime",
        fuel_auto="fuel_convenience",
        travel_hospitality="travel_hospitality",
        dining_entertainment="evening_weekend",
        cash_fin_services="office_hours",
        utilities_bills="bills_utilities",
        government_education="office_hours",
        other="consumer_daytime",
    )
    card_not_present = OrderedDict(
        digital_services="online_24h",
        general_retail="online_24h",
        grocery_pharmacy="online_24h",
        fuel_auto="online_bursty",
        travel_hospitality="online_bursty",
        dining_entertainment="online_bursty",
        cash_fin_services="online_bursty",
        utilities_bills="bills_utilities",
        government_education="office_hours",
        other="online_24h",
    )
    return OrderedDict(
        virtual_branch=OrderedDict(
            virtual_only_class="online_24h",
            hybrid_class="online_24h",
        ),
        nonvirtual_branch=OrderedDict(
            by_channel_group=OrderedDict(
                card_present=OrderedDict(by_sector=card_present),
                card_not_present=OrderedDict(by_sector=card_not_present),
                mixed=OrderedDict(by_sector=card_present),
            )
        ),
        default_class="consumer_daytime",
        subclass_rules=OrderedDict(
            zone_role=OrderedDict(
                primary_share_ge=0.60,
                tail_share_le=0.10,
            )
        ),
    )


def _realism_targets() -> OrderedDict:
    return OrderedDict(
        max_class_share=0.55,
        min_nontrivial_classes=6,
        min_class_share_for_nontrivial=0.02,
        min_virtual_share_if_virtual_present=0.01,
        max_single_country_share_within_class=0.35,
    )


def build_policy(merchant_path: Path, mcc_path: Path, version: str) -> OrderedDict:
    merchant_df = pl.read_parquet(merchant_path)
    if not {"mcc", "channel", "home_country_iso"}.issubset(merchant_df.columns):
        raise ValueError("merchant_ids missing required columns")

    mcc_df = pl.read_parquet(mcc_path)
    if not {"mcc", "description"}.issubset(mcc_df.columns):
        raise ValueError("mcc_canonical missing required columns")

    merchant_df = merchant_df.select(
        pl.col("mcc").cast(pl.Int64),
        pl.col("channel").cast(pl.Utf8),
    )
    mcc_df = mcc_df.select(
        pl.col("mcc").cast(pl.Int64),
        pl.col("description").cast(pl.Utf8),
    )

    mcc_set = merchant_df.select(pl.col("mcc").unique().sort()).to_series().to_list()
    mcc_lookup = {row["mcc"]: row["description"] for row in mcc_df.iter_rows(named=True)}

    mcc_counts = (
        merchant_df.group_by("mcc")
        .len()
        .with_columns((pl.col("len") / pl.sum("len")).alias("share"))
    )
    mcc_share = {row["mcc"]: row["share"] for row in mcc_counts.iter_rows(named=True)}

    mcc_sector_map: dict[str, str] = {}
    for mcc in mcc_set:
        if mcc not in mcc_lookup:
            raise ValueError(f"Missing MCC description for {mcc}")
        description = mcc_lookup[mcc] or ""
        sector = _score_sector(description)
        if sector == "other" and mcc_share.get(mcc, 0) > 0.05:
            sector = "general_retail"
        mcc_sector_map[f"{mcc:04d}"] = sector

    channel_values = merchant_df.select(pl.col("channel").unique().sort()).to_series().to_list()
    channel_group_map = _channel_group_map(channel_values)

    policy = OrderedDict(
        policy_id="merchant_class_policy_5A",
        version=version,
        demand_class_catalog=_demand_class_catalog(),
        mcc_sector_map=OrderedDict(sorted(mcc_sector_map.items(), key=lambda item: item[0])),
        channel_group_map=OrderedDict(sorted(channel_group_map.items(), key=lambda item: item[0])),
        decision_tree_v1=_decision_tree(),
        realism_targets=_realism_targets(),
    )
    return policy


def _to_builtin(value):
    if isinstance(value, OrderedDict):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    return value


class _QuoteDumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.nodes.ScalarNode:
    if value.isdigit():
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="'")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_QuoteDumper.add_representer(str, _represent_str)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merchant-path",
        type=Path,
        default=Path("reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"),
    )
    parser.add_argument(
        "--mcc-path",
        type=Path,
        default=Path("reference/industry/mcc_canonical/2025-12-31/mcc_canonical.parquet"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml"),
    )
    parser.add_argument("--version", default="v1.0.0")
    args = parser.parse_args()

    policy = build_policy(args.merchant_path, args.mcc_path, args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.dump(_to_builtin(policy), Dumper=_QuoteDumper, sort_keys=False)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")

    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    print(f"Wrote {args.output} (sha256={digest})")


if __name__ == "__main__":
    main()

