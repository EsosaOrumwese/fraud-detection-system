"""Build 3B CDN key digest policy (v1)."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CDN_PATH = "config/layer1/3B/virtual/cdn_country_weights.yaml"
DEFAULT_OUT_PATH = "config/layer1/3B/virtual/cdn_key_digest.yaml"


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

    source_version = payload.get("version")
    if not isinstance(source_version, str) or source_version.strip().lower() in {
        "test",
        "example",
        "todo",
        "tbd",
    }:
        raise RuntimeError("cdn_country_weights.yaml has placeholder version")

    edge_scale = payload.get("edge_scale")
    if not isinstance(edge_scale, int):
        raise RuntimeError("edge_scale missing from cdn_country_weights.yaml")
    if edge_scale < 200 or edge_scale > 2000:
        raise RuntimeError("edge_scale outside allowed range")

    countries = payload.get("countries")
    if not isinstance(countries, list) or len(countries) < 200:
        raise RuntimeError("cdn_country_weights.yaml has too few countries")

    seen = set()
    weights = []
    for entry in countries:
        if not isinstance(entry, dict):
            raise RuntimeError("cdn_country_weights.yaml has invalid country entry")
        iso = entry.get("country_iso")
        weight = entry.get("weight")
        if not isinstance(iso, str) or not re.fullmatch(r"[A-Z]{2}", iso):
            raise RuntimeError("Invalid country_iso in cdn_country_weights.yaml")
        if iso in seen:
            raise RuntimeError("Duplicate country_iso in cdn_country_weights.yaml")
        seen.add(iso)
        try:
            weight_f = float(weight)
        except (TypeError, ValueError):
            raise RuntimeError("Invalid weight in cdn_country_weights.yaml")
        if not weight_f > 0.0:
            raise RuntimeError("Non-positive weight in cdn_country_weights.yaml")
        weights.append((iso, weight_f))

    weight_sum = sum(weight for _, weight in weights)
    if abs(weight_sum - 1.0) > 1e-12:
        raise RuntimeError("cdn_country_weights.yaml weights do not sum to 1")

    top_sorted = sorted(weights, key=lambda item: item[1], reverse=True)
    top5 = sum(weight for _, weight in top_sorted[:5])
    top10 = sum(weight for _, weight in top_sorted[:10])
    if not (top5 >= 0.25 or top10 >= 0.40):
        raise RuntimeError("cdn_country_weights.yaml heavy-tail check failed")

    lines = [
        "policy_id=cdn_country_weights\n",
        f"policy_version={source_version}\n",
        f"edge_scale={edge_scale}\n",
    ]
    for iso, weight in sorted(weights, key=lambda item: item[0]):
        lines.append(f"country={iso}|weight={weight:.12f}\n")
    canonical = "".join(lines).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_lines = [
        f"version: {args.version}",
        "source_policy_id: cdn_country_weights",
        f"source_policy_version: {source_version}",
        f"edge_scale: {edge_scale}",
        f"cdn_key_digest: {digest}",
    ]
    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
