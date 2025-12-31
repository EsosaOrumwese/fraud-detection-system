from __future__ import annotations

import argparse
import hashlib
from collections import OrderedDict
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq
import yaml


CLASS_TABLE = [
    ("office_hours", 180, 2.2, 6000, False),
    ("consumer_daytime", 260, 2.0, 8000, False),
    ("evening_weekend", 240, 2.1, 7000, False),
    ("always_on_local", 320, 1.9, 9000, False),
    ("online_24h", 450, 1.6, 20000, False),
    ("online_bursty", 380, 1.4, 30000, True),
    ("travel_hospitality", 200, 2.0, 8000, False),
    ("fuel_convenience", 300, 1.9, 12000, False),
    ("bills_utilities", 150, 2.3, 6000, False),
    ("low_volume_tail", 40, 2.8, 2000, False),
]


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _to_builtin(value):
    if isinstance(value, OrderedDict):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    return value


def _hash_policy_bytes(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _u_det(stage: str, merchant_id: int, country_iso: str, tzid: str, parameter_hash: str) -> float:
    msg = f"5A.scale|{stage}|{merchant_id}|{country_iso}|{tzid}|{parameter_hash}"
    h = hashlib.sha256(msg.encode("utf-8")).digest()
    x = int.from_bytes(h[:8], "big")
    return (x + 0.5) / 2**64


def _per_site_weekly(u_det: float, median: float, pareto_alpha: float, clip_max: float) -> float:
    x_m = median / (2 ** (1.0 / pareto_alpha))
    q = x_m / (1.0 - u_det) ** (1.0 / pareto_alpha)
    return min(q, clip_max)


def _class_lookup() -> dict[str, dict[str, float | bool]]:
    params = {}
    for demand_class, median, pareto_alpha, clip_max, high_var in CLASS_TABLE:
        params[demand_class] = {
            "median_per_site_weekly": float(median),
            "pareto_alpha": float(pareto_alpha),
            "clip_max_per_site_weekly": float(clip_max),
            "ref_per_site_weekly": float(median),
            "high_variability_flag": bool(high_var),
        }
    return params


def _assign_demand_class(policy: dict, mcc: str, channel: str) -> str:
    sector = policy["mcc_sector_map"][mcc]
    channel_group = policy["channel_group_map"][channel]
    tree = policy["decision_tree_v1"]
    by_channel = tree["nonvirtual_branch"]["by_channel_group"][channel_group]["by_sector"]
    return by_channel.get(sector, tree["default_class"])


def _tzid_by_country(tz_world_path: Path) -> dict[str, str]:
    try:
        table = pq.read_table(tz_world_path, columns=["country_iso", "tzid"])
    except Exception:
        return {}
    tz_map: dict[str, str] = {}
    countries = table.column("country_iso").to_pylist()
    tzids = table.column("tzid").to_pylist()
    for country, tzid in zip(countries, tzids):
        if country is None or tzid is None:
            continue
        existing = tz_map.get(country)
        if existing is None or tzid < existing:
            tz_map[country] = tzid
    return tz_map


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merchant-path",
        type=Path,
        default=Path("reference/layer1/transaction_schema_merchant_ids/2025-12-31/transaction_schema_merchant_ids.parquet"),
    )
    parser.add_argument(
        "--policy-path",
        type=Path,
        default=Path("config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml"),
    )
    parser.add_argument(
        "--tz-world-path",
        type=Path,
        default=Path("reference/spatial/tz_world/2025a/tz_world.parquet"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("config/layer2/5A/policy/demand_scale_policy_5A.v1.yaml"),
    )
    parser.add_argument("--version", default="v1.0.0")
    args = parser.parse_args()

    policy = _load_yaml(args.policy_path)
    parameter_hash = _hash_policy_bytes(args.policy_path)

    merchant_df = pl.read_parquet(args.merchant_path).select(
        pl.col("merchant_id").cast(pl.UInt64),
        pl.col("mcc").cast(pl.Int64),
        pl.col("channel").cast(pl.Utf8),
        pl.col("home_country_iso").cast(pl.Utf8),
    )
    tz_map = _tzid_by_country(args.tz_world_path)

    class_params = _class_lookup()
    class_set = set(policy["demand_class_catalog"][i]["demand_class"] for i in range(len(policy["demand_class_catalog"])))
    missing = sorted(class_set.difference(class_params.keys()))
    if missing:
        raise ValueError(f"Missing class_params for: {missing}")

    zone_role_multipliers = {
        "primary_zone": 1.15,
        "secondary_zone": 1.00,
        "tail_zone": 0.85,
    }
    channel_group_multipliers = {
        "card_present": 1.00,
        "card_not_present": 1.15,
        "mixed": 1.05,
    }

    def preview_weekly_volume(row: dict, global_multiplier: float) -> float:
        mcc = f"{int(row['mcc']):04d}"
        demand_class = _assign_demand_class(policy, mcc, row["channel"])
        params = class_params[demand_class]
        tzid = tz_map.get(row["home_country_iso"], "UTC")
        u = _u_det("per_site", int(row["merchant_id"]), row["home_country_iso"], tzid, parameter_hash)
        per_site = _per_site_weekly(u, params["median_per_site_weekly"], params["pareto_alpha"], params["clip_max_per_site_weekly"])
        channel_group = policy["channel_group_map"][row["channel"]]
        return (
            global_multiplier
            * 1
            * per_site
            * zone_role_multipliers["primary_zone"]
            * 1.0
            * 1.0
            * channel_group_multipliers[channel_group]
        )

    preview_values = [
        preview_weekly_volume(row, 1.0)
        for row in merchant_df.iter_rows(named=True)
    ]
    mean_per_site_weekly = sum(preview_values) / len(preview_values)
    target_mean = 350.0
    global_multiplier = target_mean / mean_per_site_weekly if mean_per_site_weekly > 0 else 1.0
    global_multiplier = max(0.25, min(4.0, global_multiplier))

    class_params_list = []
    for demand_class in sorted(class_params.keys()):
        params = class_params[demand_class]
        class_params_list.append(
            OrderedDict(
                demand_class=demand_class,
                median_per_site_weekly=params["median_per_site_weekly"],
                pareto_alpha=params["pareto_alpha"],
                clip_max_per_site_weekly=params["clip_max_per_site_weekly"],
                ref_per_site_weekly=params["ref_per_site_weekly"],
                high_variability_flag=params["high_variability_flag"],
            )
        )

    output = OrderedDict(
        policy_id="demand_scale_policy_5A",
        version=args.version,
        weekly_volume_unit="arrivals_per_local_week",
        global_multiplier=round(global_multiplier, 6),
        brand_size_exponent=0.08,
        zone_role_multipliers=zone_role_multipliers,
        virtual_mode_multipliers={"NON_VIRTUAL": 1.00, "HYBRID": 1.10, "VIRTUAL_ONLY": 1.25},
        channel_group_multipliers=channel_group_multipliers,
        class_params=class_params_list,
        thresholds=OrderedDict(
            low_volume_weekly_lt=5,
            high_volume_weekly_ge=20000,
        ),
        realism_targets=OrderedDict(
            target_mean_per_site_weekly=350,
            mean_per_site_bounds=[150, 900],
            p99_p50_ratio_min=6,
            max_class_volume_share=0.60,
            max_weekly_volume_expected=5000000,
        ),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(_to_builtin(output), sort_keys=False)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")

    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    print(f"Wrote {args.output} (sha256={digest})")
    print(f"Calibrated global_multiplier={global_multiplier:.6f} (mean_per_site_weekly={mean_per_site_weekly:.2f})")


if __name__ == "__main__":
    main()
