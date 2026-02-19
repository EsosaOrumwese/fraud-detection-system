#!/usr/bin/env python3
"""Render Segment 3A P4 S1 policy variants from a baseline policy file."""

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


def _validate(theta_mix: float, site_count_lt: int, zone_count_country_ge: int, site_count_ge: int) -> None:
    if not (0.10 <= theta_mix <= 0.70):
        raise ValueError("theta_mix must be in [0.10, 0.70]")
    if not (2 <= site_count_lt <= 10):
        raise ValueError("site_count_lt must be in [2, 10]")
    if not (3 <= zone_count_country_ge <= 12):
        raise ValueError("zone_count_country_ge must be in [3, 12]")
    if not (20 <= site_count_ge <= 200):
        raise ValueError("site_count_ge must be in [20, 200]")
    if site_count_ge <= site_count_lt:
        raise ValueError("site_count_ge must be greater than site_count_lt")


def _parse_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def _render_smoothing(
    payload: dict[str, Any],
    enabled: bool,
    zone_count_min: int,
    zone_count_max: int,
    zone_prob_min: float,
    zone_prob_max: float,
    site_slope: float,
    site_cap: float,
) -> None:
    if not (2 <= zone_count_min <= 32):
        raise ValueError("smooth zone_count_min must be in [2, 32]")
    if not (3 <= zone_count_max <= 64):
        raise ValueError("smooth zone_count_max must be in [3, 64]")
    if zone_count_max <= zone_count_min:
        raise ValueError("smooth zone_count_max must be greater than zone_count_min")
    if not (0.0 <= zone_prob_min <= 1.0):
        raise ValueError("smooth zone_escalation_prob_min must be in [0.0, 1.0]")
    if not (0.0 <= zone_prob_max <= 1.0):
        raise ValueError("smooth zone_escalation_prob_max must be in [0.0, 1.0]")
    if zone_prob_max < zone_prob_min:
        raise ValueError("smooth zone_escalation_prob_max must be >= zone_escalation_prob_min")
    if not (0.0 <= site_slope <= 1.0):
        raise ValueError("smooth site_count_slope must be in [0.0, 1.0]")
    if not (0.0 <= site_cap <= 1.0):
        raise ValueError("smooth site_count_cap must be in [0.0, 1.0]")
    if site_cap < site_slope:
        raise ValueError("smooth site_count_cap must be >= site_count_slope")

    payload["s1_smoothing"] = {
        "enabled": bool(enabled),
        "zone_count_min": int(zone_count_min),
        "zone_count_max": int(zone_count_max),
        "zone_escalation_prob_min": round(float(zone_prob_min), 9),
        "zone_escalation_prob_max": round(float(zone_prob_max), 9),
        "site_count_slope": round(float(site_slope), 9),
        "site_count_cap": round(float(site_cap), 9),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Segment 3A P4 S1 policy variant.")
    parser.add_argument("--source", default="scratch_files/segment3a_p4_baseline/zone_mixture_policy.yaml")
    parser.add_argument("--out", default="config/layer1/3A/policy/zone_mixture_policy.yaml")
    parser.add_argument("--theta-mix", type=float, required=True)
    parser.add_argument("--site-count-lt", type=int, required=True)
    parser.add_argument("--zone-count-country-ge", type=int, required=True)
    parser.add_argument("--site-count-ge", type=int, required=True)
    parser.add_argument("--policy-version", default="")
    parser.add_argument("--smooth-enabled", default=None)
    parser.add_argument("--smooth-zone-count-min", type=int, default=None)
    parser.add_argument("--smooth-zone-count-max", type=int, default=None)
    parser.add_argument("--smooth-zone-prob-min", type=float, default=None)
    parser.add_argument("--smooth-zone-prob-max", type=float, default=None)
    parser.add_argument("--smooth-site-slope", type=float, default=None)
    parser.add_argument("--smooth-site-cap", type=float, default=None)
    args = parser.parse_args()

    _validate(
        theta_mix=float(args.theta_mix),
        site_count_lt=int(args.site_count_lt),
        zone_count_country_ge=int(args.zone_count_country_ge),
        site_count_ge=int(args.site_count_ge),
    )

    source = Path(args.source)
    out = Path(args.out)
    payload = _load_yaml(source)

    payload["theta_mix"] = round(float(args.theta_mix), 9)
    payload["rules"] = [
        {
            "metric": "site_count_lt",
            "threshold": int(args.site_count_lt),
            "decision_reason": "below_min_sites",
        },
        {
            "metric": "zone_count_country_le",
            "threshold": 1,
            "decision_reason": "forced_monolithic",
        },
        {
            "metric": "zone_count_country_ge",
            "threshold": int(args.zone_count_country_ge),
            "decision_reason": "forced_escalation",
        },
        {
            "metric": "site_count_ge",
            "threshold": int(args.site_count_ge),
            "decision_reason": "forced_escalation",
        },
    ]
    if args.policy_version:
        payload["version"] = str(args.policy_version)

    smooth_enabled = None if args.smooth_enabled is None else _parse_bool(args.smooth_enabled)
    smooth_inputs = [
        args.smooth_zone_count_min,
        args.smooth_zone_count_max,
        args.smooth_zone_prob_min,
        args.smooth_zone_prob_max,
        args.smooth_site_slope,
        args.smooth_site_cap,
    ]
    if smooth_enabled is None:
        if any(value is not None for value in smooth_inputs):
            raise ValueError("smooth knobs require --smooth-enabled")
    else:
        if any(value is None for value in smooth_inputs):
            raise ValueError("all smooth knobs must be set when --smooth-enabled is provided")
        _render_smoothing(
            payload=payload,
            enabled=smooth_enabled,
            zone_count_min=int(args.smooth_zone_count_min),
            zone_count_max=int(args.smooth_zone_count_max),
            zone_prob_min=float(args.smooth_zone_prob_min),
            zone_prob_max=float(args.smooth_zone_prob_max),
            site_slope=float(args.smooth_site_slope),
            site_cap=float(args.smooth_site_cap),
        )

    _dump_yaml(out, payload)
    print(str(out))


if __name__ == "__main__":
    main()
