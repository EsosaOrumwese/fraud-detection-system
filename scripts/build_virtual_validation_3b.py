"""Build 3B virtual validation policy (v1)."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CDN_PATH = "config/virtual/cdn_country_weights.yaml"
DEFAULT_OUT_PATH = "config/virtual/virtual_validation.yml"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdn-path", default=DEFAULT_CDN_PATH)
    parser.add_argument("--out-path", default=DEFAULT_OUT_PATH)
    parser.add_argument("--version", default="v1.0.0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cdn_path = ROOT / args.cdn_path
    out_path = ROOT / args.out_path

    payload = yaml.safe_load(cdn_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("cdn_country_weights.yaml is not a mapping")
    edge_scale = payload.get("edge_scale")
    if not isinstance(edge_scale, int):
        raise RuntimeError("edge_scale missing from cdn_country_weights.yaml")

    ip_country_tolerance = clamp(max(0.01, 5.0 / edge_scale), 0.01, 0.05)
    cutoff_tolerance_seconds = 1800

    if ip_country_tolerance < 0.005 or ip_country_tolerance > 0.08:
        raise RuntimeError("ip_country_tolerance outside realism floor")
    if cutoff_tolerance_seconds < 300 or cutoff_tolerance_seconds > 7200:
        raise RuntimeError("cutoff_tolerance_seconds outside realism floor")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"version: {args.version}",
        f"ip_country_tolerance: {ip_country_tolerance:.6f}",
        f"cutoff_tolerance_seconds: {cutoff_tolerance_seconds}",
        "notes: \"v1: ip_country_tolerance=max(0.01,5/E) clamped; cutoff_tolerance_seconds=1800\"",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
