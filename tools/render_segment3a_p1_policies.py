#!/usr/bin/env python3
"""Render Segment 3A P1 policy variants from frozen baseline files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be object: {path}")
    return payload


def _dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=160)
    path.write_text(text, encoding="utf-8")


def _blend_country_alphas(alpha_payload: dict[str, Any], blend_lambda: float) -> dict[str, Any]:
    if blend_lambda < 0.0 or blend_lambda > 1.0:
        raise ValueError("blend_lambda must be in [0, 1]")
    countries = alpha_payload.get("countries")
    if not isinstance(countries, dict):
        raise ValueError("country_zone_alphas missing countries object")

    for country_iso, country_entry in countries.items():
        if not isinstance(country_entry, dict):
            raise ValueError(f"country entry must be object: {country_iso}")
        tzid_alphas = country_entry.get("tzid_alphas")
        if not isinstance(tzid_alphas, list) or not tzid_alphas:
            raise ValueError(f"country tzid_alphas must be non-empty list: {country_iso}")
        alpha_values = [float(row["alpha"]) for row in tzid_alphas]
        alpha_sum = sum(alpha_values)
        if alpha_sum <= 0.0:
            raise ValueError(f"country alpha sum must be positive: {country_iso}")
        n = float(len(alpha_values))
        uniform = 1.0 / n
        for row, alpha in zip(tzid_alphas, alpha_values):
            share = alpha / alpha_sum
            blended_share = ((1.0 - blend_lambda) * share) + (blend_lambda * uniform)
            new_alpha = blended_share * alpha_sum
            # Preserve strictly-positive alpha invariant.
            row["alpha"] = round(max(new_alpha, 1.0e-9), 9)
    return alpha_payload


def _transform_floor_policy(
    floor_payload: dict[str, Any],
    floor_scale: float,
    threshold_shift: float,
    force_threshold: float | None,
) -> dict[str, Any]:
    if floor_scale <= 0.0:
        raise ValueError("floor_scale must be > 0")
    floors = floor_payload.get("floors")
    if not isinstance(floors, list) or not floors:
        raise ValueError("zone_floor_policy missing floors array")

    for row in floors:
        if not isinstance(row, dict):
            raise ValueError("floor row must be object")
        floor_value = float(row["floor_value"]) * floor_scale
        if force_threshold is None:
            bump_threshold = float(row["bump_threshold"]) + threshold_shift
        else:
            bump_threshold = force_threshold
        row["floor_value"] = round(max(floor_value, 0.0), 9)
        row["bump_threshold"] = round(min(max(bump_threshold, 0.0), 1.0), 9)
    return floor_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Segment 3A P1 policy variants.")
    parser.add_argument(
        "--alpha-source",
        default="scratch_files/segment3a_p1_baseline/country_zone_alphas.yaml",
    )
    parser.add_argument(
        "--alpha-out",
        default="config/layer1/3A/allocation/country_zone_alphas.yaml",
    )
    parser.add_argument(
        "--floor-source",
        default="scratch_files/segment3a_p1_baseline/zone_floor_policy.yaml",
    )
    parser.add_argument(
        "--floor-out",
        default="config/layer1/3A/allocation/zone_floor_policy.yaml",
    )
    parser.add_argument("--blend-lambda", type=float, required=True)
    parser.add_argument("--floor-scale", type=float, default=1.0)
    parser.add_argument("--threshold-shift", type=float, default=0.0)
    parser.add_argument("--force-threshold", type=float, default=None)
    parser.add_argument("--alpha-version", default="")
    parser.add_argument("--floor-version", default="")
    args = parser.parse_args()

    alpha_source = Path(args.alpha_source)
    alpha_out = Path(args.alpha_out)
    floor_source = Path(args.floor_source)
    floor_out = Path(args.floor_out)

    alpha_payload = _load_yaml(alpha_source)
    floor_payload = _load_yaml(floor_source)

    alpha_payload = _blend_country_alphas(alpha_payload, blend_lambda=float(args.blend_lambda))
    floor_payload = _transform_floor_policy(
        floor_payload,
        floor_scale=float(args.floor_scale),
        threshold_shift=float(args.threshold_shift),
        force_threshold=None if args.force_threshold is None else float(args.force_threshold),
    )

    if args.alpha_version:
        alpha_payload["version"] = str(args.alpha_version)
    if args.floor_version:
        floor_payload["version"] = str(args.floor_version)

    _dump_yaml(alpha_out, alpha_payload)
    _dump_yaml(floor_out, floor_payload)

    print(str(alpha_out))
    print(str(floor_out))


if __name__ == "__main__":
    main()
