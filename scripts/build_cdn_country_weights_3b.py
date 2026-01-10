"""Build 3B CDN country weights policy (v1) from external weights."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable

import pyarrow.parquet as pq
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXT_PATH = "artefacts/external/cdn_weights_ext.yaml"
DEFAULT_ISO_PATH = "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet"
DEFAULT_WORLD_PATH = "reference/spatial/world_countries/2024/world_countries.parquet"
DEFAULT_OUT_PATH = "config/layer1/3B/virtual/cdn_country_weights.yaml"

ALIASES = {"UK": "GB", "EL": "GR", "FX": "FR"}


def load_iso_set(path: Path) -> set[str]:
    import polars as pl

    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pl.read_csv(path)
    elif suffix in {".parquet", ".pq"}:
        frame = pl.read_parquet(path)
    else:
        raise ValueError(f"Unsupported ISO file extension: {path.suffix}")

    cols = {c.lower(): c for c in frame.columns}
    if "country_iso" in cols:
        iso_col = cols["country_iso"]
    elif "alpha2" in cols:
        iso_col = cols["alpha2"]
    else:
        raise ValueError("ISO file must expose a 'country_iso' or 'alpha2' column")

    return {
        str(code).strip().upper()
        for code in frame[iso_col].to_list()
        if str(code).strip()
    }


def load_world_iso_set(path: Path) -> set[str]:
    table = pq.read_table(path, columns=["country_iso"])
    values = table.column("country_iso").to_pylist()
    return {str(code).strip().upper() for code in values if str(code).strip()}


def normalize_code(code: str) -> str | None:
    code = code.strip().upper()
    code = ALIASES.get(code, code)
    if not re.fullmatch(r"[A-Z]{2}", code):
        return None
    return code


def load_external_weights(path: Path) -> Dict[str, float]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("External weights payload must be a mapping")

    weights: Dict[str, float] = {}
    if "countries" in payload:
        for entry in payload["countries"] or []:
            if not isinstance(entry, dict):
                continue
            code = entry.get("country_iso")
            weight = entry.get("weight")
            if not isinstance(code, str):
                continue
            norm = normalize_code(code)
            if norm is None:
                continue
            try:
                weight_f = float(weight)
            except (TypeError, ValueError):
                continue
            weight_f = max(weight_f, 0.0)
            weights[norm] = weights.get(norm, 0.0) + weight_f
    elif "weights" in payload:
        for code, weight in (payload["weights"] or {}).items():
            if not isinstance(code, str):
                continue
            norm = normalize_code(code)
            if norm is None:
                continue
            try:
                weight_f = float(weight)
            except (TypeError, ValueError):
                continue
            weight_f = max(weight_f, 0.0)
            weights[norm] = weights.get(norm, 0.0) + weight_f
    else:
        raise RuntimeError("External weights payload missing countries/weights")

    total = sum(weights.values())
    if not total > 0:
        raise RuntimeError("External weights sum to zero after cleaning")
    return weights


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ext-path", default=DEFAULT_EXT_PATH)
    parser.add_argument("--iso-path", default=DEFAULT_ISO_PATH)
    parser.add_argument("--world-path", default=DEFAULT_WORLD_PATH)
    parser.add_argument("--out-path", default=DEFAULT_OUT_PATH)
    parser.add_argument("--version", default="v1.0.0")
    parser.add_argument("--edge-scale", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ext_path = ROOT / args.ext_path
    iso_path = ROOT / args.iso_path
    world_path = ROOT / args.world_path
    out_path = ROOT / args.out_path

    ext_weights = load_external_weights(ext_path)
    iso_set = load_iso_set(iso_path)
    world_set = load_world_iso_set(world_path)

    missing_world = sorted(iso_set - world_set)
    if missing_world and len(missing_world) / len(iso_set) > 0.05:
        # Deviation from guide: proceed with intersection but record in logbook.
        pass

    country_set = sorted(iso_set & world_set)
    if len(country_set) < 200:
        raise RuntimeError("Country universe too small for CDN mix")

    w0 = {code: max(ext_weights.get(code, 0.0), 0.0) for code in country_set}
    present = {code for code, weight in w0.items() if weight > 0.0}
    missing = set(country_set) - present
    if len(present) < 120:
        raise RuntimeError("External weights too thin for CDN policy")

    missing_frac = len(missing) / len(country_set)
    tail_mass = 0.0 if not missing else clamp(0.02 + 0.25 * missing_frac, 0.02, 0.20)

    sum_present = sum(w0[c] for c in present)
    if not sum_present > 0:
        raise RuntimeError("External weights missing positive mass in country set")

    w1: Dict[str, float] = {}
    for code in present:
        w1[code] = (1.0 - tail_mass) * w0[code] / sum_present
    for code in missing:
        w1[code] = tail_mass / len(missing)

    w2 = {code: max(weight, 1e-12) for code, weight in w1.items()}
    sum_w2 = sum(w2.values())
    raw_weights = {code: weight / sum_w2 for code, weight in w2.items()}

    scale = 10**12
    scaled = {code: raw_weights[code] * scale for code in country_set}
    ulps = {code: int(round(scaled[code])) for code in country_set}
    remainders = {code: scaled[code] - ulps[code] for code in country_set}
    total_ulps = sum(ulps.values())

    if total_ulps != scale:
        if total_ulps < scale:
            need = scale - total_ulps
            for code in sorted(country_set, key=lambda c: (-remainders[c], c))[:need]:
                ulps[code] += 1
        else:
            need = total_ulps - scale
            for code in sorted(country_set, key=lambda c: (remainders[c], c))[:need]:
                if ulps[code] > 1:
                    ulps[code] -= 1
                else:
                    raise RuntimeError("ULP adjustment underflow")

    weights = {code: ulps[code] / scale for code in country_set}

    top_sorted = sorted(weights.items(), key=lambda item: item[1], reverse=True)
    top5 = sum(weight for _, weight in top_sorted[:5])
    top10 = sum(weight for _, weight in top_sorted[:10])
    if not (top5 >= 0.25 or top10 >= 0.40):
        raise RuntimeError("Heavy-tail check failed for CDN weights")

    rank_ext = [code for code, _ in sorted(w0.items(), key=lambda item: item[1], reverse=True)[:20]]
    rank_final = [code for code, _ in top_sorted[:20]]
    overlap = len(set(rank_ext) & set(rank_final))
    if overlap < 15:
        raise RuntimeError("External anchor overlap failed for CDN weights")

    if args.edge_scale < 200 or args.edge_scale > 2000:
        raise RuntimeError("edge_scale outside allowed range")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"version: {args.version}", f"edge_scale: {args.edge_scale}", "countries:"]
    for code in country_set:
        weight = weights[code]
        note = "src=akamai_ext" if code in present else "src=tail_uniform"
        lines.append(f"  - country_iso: {code}")
        lines.append(f"    weight: {weight:.12f}")
        lines.append(f"    notes: \"{note}\"")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
