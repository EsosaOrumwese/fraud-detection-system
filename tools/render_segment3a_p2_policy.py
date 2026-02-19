#!/usr/bin/env python3
"""Render Segment 3A P2 dispersion policy variants from a baseline policy file."""

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


def _validate_ranges(
    concentration_scale: float,
    alpha_temperature: float,
    merchant_jitter: float,
    merchant_jitter_clip: float,
    alpha_floor: float,
) -> None:
    if not (0.25 <= concentration_scale <= 1.50):
        raise ValueError("concentration_scale must be in [0.25, 1.50]")
    if not (0.50 <= alpha_temperature <= 1.50):
        raise ValueError("alpha_temperature must be in [0.50, 1.50]")
    if not (0.0 <= merchant_jitter <= 0.50):
        raise ValueError("merchant_jitter must be in [0.0, 0.50]")
    if not (0.0 <= merchant_jitter_clip <= 0.50):
        raise ValueError("merchant_jitter_clip must be in [0.0, 0.50]")
    if merchant_jitter_clip < merchant_jitter:
        raise ValueError("merchant_jitter_clip must be >= merchant_jitter")
    if not (0.0 < alpha_floor <= 0.01):
        raise ValueError("alpha_floor must be in (0, 0.01]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Segment 3A P2 dispersion policy variant.")
    parser.add_argument(
        "--source",
        default="scratch_files/segment3a_p2_baseline/zone_mixture_policy.yaml",
    )
    parser.add_argument(
        "--out",
        default="config/layer1/3A/policy/zone_mixture_policy.yaml",
    )
    parser.add_argument("--enabled", type=int, default=1)
    parser.add_argument("--concentration-scale", type=float, required=True)
    parser.add_argument("--alpha-temperature", type=float, default=1.0)
    parser.add_argument("--merchant-jitter", type=float, default=0.0)
    parser.add_argument("--merchant-jitter-clip", type=float, default=0.0)
    parser.add_argument("--alpha-floor", type=float, default=1.0e-6)
    parser.add_argument("--policy-version", default="")
    args = parser.parse_args()

    _validate_ranges(
        concentration_scale=float(args.concentration_scale),
        alpha_temperature=float(args.alpha_temperature),
        merchant_jitter=float(args.merchant_jitter),
        merchant_jitter_clip=float(args.merchant_jitter_clip),
        alpha_floor=float(args.alpha_floor),
    )

    source = Path(args.source)
    out = Path(args.out)

    payload = _load_yaml(source)
    payload["s3_dispersion"] = {
        "enabled": bool(int(args.enabled)),
        "concentration_scale": round(float(args.concentration_scale), 9),
        "alpha_temperature": round(float(args.alpha_temperature), 9),
        "merchant_jitter": round(float(args.merchant_jitter), 9),
        "merchant_jitter_clip": round(float(args.merchant_jitter_clip), 9),
        "alpha_floor": round(float(args.alpha_floor), 9),
    }
    if args.policy_version:
        payload["version"] = str(args.policy_version)

    _dump_yaml(out, payload)
    print(str(out))


if __name__ == "__main__":
    main()

