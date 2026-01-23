from __future__ import annotations

import argparse
import hashlib
from collections import OrderedDict
from math import exp, floor
from pathlib import Path

import yaml


CHANNEL_GROUPS = ["card_present", "card_not_present", "mixed"]


CLASS_BASE = {
    "office_hours": {
        "dow_weights": [1.0, 1.0, 1.0, 1.0, 1.0, 0.35, 0.30],
        "baseline_floor": 0.07,
        "power": 1.20,
        "components": [(600, 90, 1.0), (840, 90, 0.9)],
        "notes": "Weekday office hours with light weekend activity.",
    },
    "consumer_daytime": {
        "dow_weights": [1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.9],
        "baseline_floor": 0.08,
        "power": 1.10,
        "components": [(720, 120, 1.0), (1020, 140, 0.8)],
        "notes": "Daytime consumer activity with weekend continuity.",
    },
    "evening_weekend": {
        "dow_weights": [0.8, 0.8, 0.9, 1.0, 1.1, 1.6, 1.5],
        "baseline_floor": 0.08,
        "power": 1.30,
        "components": [(60, 120, 0.3), (1200, 110, 1.2), (1350, 120, 0.8)],
        "notes": "Evening peaks and weekend uplift.",
    },
    "always_on_local": {
        "dow_weights": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "baseline_floor": 0.25,
        "power": 0.85,
        "components": [(540, 180, 0.6), (1140, 180, 0.6)],
        "notes": "Broad, always-on profile with mild peaks.",
    },
    "online_24h": {
        "dow_weights": [1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.1],
        "baseline_floor": 0.20,
        "power": 0.90,
        "components": [(60, 150, 0.8), (1260, 160, 0.7)],
        "notes": "Online 24/7 with elevated night mass.",
    },
    "online_bursty": {
        "dow_weights": [0.9, 0.9, 0.9, 1.0, 1.1, 1.4, 1.3],
        "baseline_floor": 0.10,
        "power": 1.60,
        "components": [(90, 140, 0.4), (660, 70, 1.4), (1140, 80, 1.2)],
        "notes": "High-variance online bursts.",
    },
    "travel_hospitality": {
        "dow_weights": [0.8, 0.9, 1.0, 1.0, 1.1, 1.5, 1.4],
        "baseline_floor": 0.06,
        "power": 1.15,
        "components": [(540, 120, 1.0), (1080, 140, 0.9)],
        "notes": "Travel/hospitality with weekend uplift.",
    },
    "fuel_convenience": {
        "dow_weights": [1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.9],
        "baseline_floor": 0.07,
        "power": 1.10,
        "components": [(480, 90, 1.1), (1050, 100, 1.0)],
        "notes": "Fuel and convenience peaks around commute.",
    },
    "bills_utilities": {
        "dow_weights": [1.0, 1.0, 1.0, 1.0, 0.9, 0.5, 0.4],
        "baseline_floor": 0.05,
        "power": 1.05,
        "components": [(600, 100, 0.9), (840, 110, 0.7)],
        "notes": "Bills/utilities weekday bias.",
    },
    "low_volume_tail": {
        "dow_weights": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "baseline_floor": 0.10,
        "power": 0.80,
        "components": [(660, 200, 0.4)],
        "notes": "Sparse activity with non-flat shape.",
    },
}


def _grid(bucket_minutes: int) -> OrderedDict:
    t_day = 1440 // bucket_minutes
    t_week = 7 * t_day
    return OrderedDict(
        bucket_duration_minutes=bucket_minutes,
        week_start="monday_00_00_local",
        day_of_week_encoding="1=Mon,...,7=Sun",
        minutes_per_day=1440,
        days_per_week=7,
        T_week=t_week,
        bucket_index_law="k=(dow-1)*T_day + floor(minute/bucket_minutes)",
        derived_flags=OrderedDict(
            weekend_days=[6, 7],
            is_weekend_law="dow in weekend_days",
        ),
    )


def _template_variants(base: dict, channel_group: str) -> list[dict]:
    offsets = [-60, 0, 60]
    sigma_factors = [0.90, 1.00, 1.10]
    weekend_factors = [0.95, 1.00, 1.05]
    variants = []
    for idx, (offset, sigma_factor, weekend_factor) in enumerate(
        zip(offsets, sigma_factors, weekend_factors)
    ):
        dow_weights = list(base["dow_weights"])
        dow_weights[5] *= weekend_factor
        dow_weights[6] *= weekend_factor
        comps = []
        for center, sigma, amplitude in base["components"]:
            adjusted = max(0, min(1439, center + offset))
            comps.append(
                OrderedDict(
                    kind="gaussian_peak",
                    center_min=int(adjusted),
                    sigma_min=float(max(20.0, min(240.0, sigma * sigma_factor))),
                    amplitude=float(amplitude),
                )
            )
        variants.append(
            OrderedDict(
                channel_group=channel_group,
                dow_weights=[float(x) for x in dow_weights],
                baseline_floor=float(base["baseline_floor"]),
                power=float(base["power"]),
                daily_components=comps,
                notes=base["notes"],
            )
        )
    return variants


def _compile_template(template: dict, bucket_minutes: int) -> list[float]:
    t_day = 1440 // bucket_minutes
    t_week = 7 * t_day
    values = []
    for k in range(t_week):
        dow = 1 + (k // t_day)
        minute = (k % t_day) * bucket_minutes
        g = template["baseline_floor"]
        for comp in template["daily_components"]:
            sigma = comp["sigma_min"]
            g += comp["amplitude"] * exp(-0.5 * ((minute - comp["center_min"]) / sigma) ** 2)
        v = (template["dow_weights"][dow - 1] * g) ** template["power"]
        values.append(v)
    total = sum(values)
    if total <= 0:
        raise ValueError("Template has zero mass")
    return [v / total for v in values]


def _to_builtin(value):
    if isinstance(value, OrderedDict):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    return value


def _validate(templates: list[dict], bucket_minutes: int, constraints: dict, realism: dict) -> None:
    t_day = 1440 // bucket_minutes
    night_start = constraints["night_window_minutes"]["start_min"]
    night_end = constraints["night_window_minutes"]["end_min"]
    weekend_days = {6, 7}
    nonflat = 0

    weekend_required = {"evening_weekend", "travel_hospitality"}

    for template in templates:
        shape = _compile_template(template, bucket_minutes)
        ratio = max(shape) / max(min(shape), 1e-12)
        if ratio >= constraints["shape_nonflat_ratio_min"]:
            nonflat += 1

        night_mass = 0.0
        weekend_mass = 0.0
        office_mass = 0.0
        office_total = 0.0
        for k, value in enumerate(shape):
            dow = 1 + (k // t_day)
            minute = (k % t_day) * bucket_minutes
            if night_start <= minute < night_end:
                night_mass += value
            if dow in weekend_days:
                weekend_mass += value
            if dow <= 5:
                office_total += value
                if constraints["office_hours_window"]["weekday_start_min"] <= minute < constraints["office_hours_window"]["weekday_end_min"]:
                    office_mass += value

        if night_mass < constraints["min_mass_night"]:
            raise ValueError(f"Night mass too low for {template['template_id']}: {night_mass:.4f}")

        if template["demand_class"] in weekend_required and weekend_mass < constraints["min_weekend_mass_for_weekend_classes"]:
            raise ValueError(f"Weekend mass too low for {template['template_id']}: {weekend_mass:.4f}")

        if template["demand_class"] == "office_hours":
            office_ratio = office_mass / office_total if office_total > 0 else 0.0
            if office_ratio < constraints["office_hours_window"]["min_weekday_office_mass"]:
                raise ValueError(f"Office hours mass too low for {template['template_id']}: {office_ratio:.4f}")

        if template["demand_class"] == "online_24h":
            if night_mass < realism["min_night_mass_online24h"]:
                raise ValueError(f"Online night mass too low for {template['template_id']}: {night_mass:.4f}")

        if template["demand_class"] == "evening_weekend":
            if weekend_mass < realism["min_weekend_mass_evening_weekend"]:
                raise ValueError(f"Weekend mass too low for {template['template_id']}: {weekend_mass:.4f}")

    total_templates = len(templates)
    if total_templates < realism["min_total_templates"]:
        raise ValueError("Template count below realism floor")

    fraction_nonflat = nonflat / total_templates if total_templates else 0.0
    if fraction_nonflat < realism["min_nonflat_templates_fraction"]:
        raise ValueError("Nonflat template fraction below realism floor")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("config/layer2/5A/policy/shape_library_5A.v1.yaml"))
    parser.add_argument("--version", default="v1.0.0")
    parser.add_argument("--bucket-minutes", type=int, default=60)
    args = parser.parse_args()

    templates = []
    template_resolution_rules = []

    for demand_class in sorted(CLASS_BASE.keys()):
        base = CLASS_BASE[demand_class]
        for channel_group in CHANNEL_GROUPS:
            variants = _template_variants(base, channel_group)
            candidate_ids = []
            for idx, variant in enumerate(variants, start=1):
                template_id = f"{demand_class}.{channel_group}.v{idx}"
                candidate_ids.append(template_id)
                template = OrderedDict(
                    template_id=template_id,
                    demand_class=demand_class,
                    channel_group=channel_group,
                    shape_kind="daily_gaussian_mixture",
                    dow_weights=variant["dow_weights"],
                    daily_components=variant["daily_components"],
                    baseline_floor=variant["baseline_floor"],
                    power=variant["power"],
                    notes=variant["notes"],
                )
                templates.append(template)

            template_resolution_rules.append(
                OrderedDict(
                    demand_class=demand_class,
                    channel_group=channel_group,
                    candidate_template_ids=candidate_ids,
                    selection_law="u_det_pick_index_v1",
                )
            )

    templates = sorted(templates, key=lambda row: (row["demand_class"], row["channel_group"], row["template_id"]))
    template_resolution_rules = sorted(
        template_resolution_rules,
        key=lambda row: (row["demand_class"], row["channel_group"]),
    )

    constraints = OrderedDict(
        min_mass_night=0.02,
        night_window_minutes=OrderedDict(start_min=0, end_min=360),
        min_weekend_mass_for_weekend_classes=0.30,
        office_hours_window=OrderedDict(
            weekday_start_min=480,
            weekday_end_min=1080,
            min_weekday_office_mass=0.65,
        ),
        shape_nonflat_ratio_min=1.6,
    )
    realism_floors = OrderedDict(
        min_total_templates=40,
        min_templates_per_class_per_channel=2,
        require_all_classes_present=True,
        require_all_channel_groups_present=True,
        min_nonflat_templates_fraction=0.90,
        min_night_mass_online24h=0.08,
        min_weekend_mass_evening_weekend=0.30,
        min_weekday_mass_office_hours=0.65,
    )

    _validate(templates, args.bucket_minutes, constraints, realism_floors)

    grid = _grid(args.bucket_minutes)
    output = OrderedDict(
        policy_id="shape_library_5A",
        version=args.version,
        scenario_mode="scenario_agnostic",
        grid=grid,
        channel_groups=CHANNEL_GROUPS,
        zone_group_mode=OrderedDict(mode="tzid_hash_bucket_v1", buckets=8, zone_group_id_prefix="zg"),
        templates=templates,
        template_resolution=OrderedDict(
            mode="deterministic_choice_by_tzid_v1",
            default_template_id=templates[0]["template_id"],
            rules=template_resolution_rules,
        ),
        constraints=constraints,
        realism_floors=realism_floors,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(_to_builtin(output), sort_keys=False)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")

    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    print(f"Wrote {args.output} (sha256={digest})")


if __name__ == "__main__":
    main()
