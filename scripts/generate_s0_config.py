#!/usr/bin/env python3
"""
Generate the S0 synthetic run configuration.

The script inspects the versioned artefacts that feed S0 (merchant ingress,
ISO canonical list, GDP tables, synthetic model exports, policies, etc.), picks
the latest available versions, and emits a JSON configuration that can be fed
directly into the S0 orchestrator.

Usage:
    python scripts/generate_s0_config.py \
        --output configs/runs/s0_synthetic_config.json

Optional flags let you override specific versions if you want to pin an older
artefact (see --help).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _latest_subdir(path: Path) -> Path:
    """Return the lexicographically latest sub-directory under ``path``."""
    candidates = sorted(
        [p for p in path.iterdir() if p.is_dir()],
        key=lambda p: p.name,
    )
    if not candidates:
        raise FileNotFoundError(f"no versioned directories found under {path}")
    return candidates[-1]


def discover_paths(
    *,
    merchant_version: str | None,
    iso_version: str | None,
    gdp_version: str | None,
    bucket_version: str | None,
    numeric_version: str | None,
    math_version: str | None,
    model_version: str | None,
    model_timestamp: str | None,
) -> dict[str, str]:
    """Resolve all artefact paths needed by S0."""

    # Merchant ingress
    merchant_root = ROOT / "reference" / "layer1" / "transaction_schema_merchant_ids"
    merchant_dir = (
        merchant_root / merchant_version
        if merchant_version
        else _latest_subdir(merchant_root)
    )
    merchant_path = merchant_dir / "transaction_schema_merchant_ids.parquet"

    # ISO canonical
    iso_root = ROOT / "reference" / "layer1" / "iso_canonical"
    iso_dir = (
        iso_root / iso_version
        if iso_version
        else _latest_subdir(iso_root)
    )
    iso_path = iso_dir / "iso_canonical.parquet"

    # GDP
    gdp_root = ROOT / "reference" / "economic" / "world_bank_gdp_per_capita"
    gdp_dir = (
        gdp_root / gdp_version
        if gdp_version
        else _latest_subdir(gdp_root)
    )
    gdp_path = gdp_dir / "gdp.parquet"

    # GDP bucket map
    bucket_root = ROOT / "reference" / "economic" / "gdp_bucket_map"
    bucket_dir = (
        bucket_root / bucket_version
        if bucket_version
        else _latest_subdir(bucket_root)
    )
    bucket_path = bucket_dir / "gdp_bucket_map.parquet"

    # Numeric policy
    numeric_root = ROOT / "reference" / "governance" / "numeric_policy"
    numeric_dir = (
        numeric_root / numeric_version
        if numeric_version
        else _latest_subdir(numeric_root)
    )
    numeric_path = numeric_dir / "numeric_policy.json"

    # Math profile
    math_root = ROOT / "reference" / "governance" / "math_profile"
    math_dir = (
        math_root / math_version
        if math_version
        else _latest_subdir(math_root)
    )
    math_path = math_dir / "math_profile_manifest.json"

    # Model exports (hurdle / dispersion)
    model_root = ROOT / "configs" / "models" / "hurdle" / "exports"
    version_dir = (
        model_root / f"version={model_version}"
        if model_version
        else _latest_subdir(model_root)
    )
    timestamp_dir = (
        version_dir / model_timestamp
        if model_timestamp
        else _latest_subdir(version_dir)
    )
    hurdle_yaml = timestamp_dir / "hurdle_coefficients.yaml"
    nb_disp_yaml = timestamp_dir / "nb_dispersion_coefficients.yaml"

    crossborder_policy = ROOT / "configs" / "policy/crossborder_hyperparams.yaml"

    return {
        "merchant_table": str(merchant_path.relative_to(ROOT)),
        "iso_table": str(iso_path.relative_to(ROOT)),
        "gdp_table": str(gdp_path.relative_to(ROOT)),
        "bucket_table": str(bucket_path.relative_to(ROOT)),
        "numeric_policy": str(numeric_path.relative_to(ROOT)),
        "math_profile_manifest": str(math_path.relative_to(ROOT)),
        "hurdle_coefficients": str(hurdle_yaml.relative_to(ROOT)),
        "nb_dispersion_coefficients": str(nb_disp_yaml.relative_to(ROOT)),
        "crossborder_policy": str(crossborder_policy.relative_to(ROOT)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=ROOT / "configs" / "runs" / "s0_synthetic_config.json",
        type=Path,
        help="Path to write the generated JSON config.",
    )
    parser.add_argument("--merchant-version")
    parser.add_argument("--iso-version")
    parser.add_argument("--gdp-version")
    parser.add_argument("--bucket-version")
    parser.add_argument("--numeric-version")
    parser.add_argument("--math-version")
    parser.add_argument("--model-version")
    parser.add_argument("--model-timestamp")
    parser.add_argument("--output-dir", default="artefacts/s0_runs/2025-10-09_synthetic")
    parser.add_argument("--seed", type=int, default=9248923)
    parser.add_argument("--git-commit", default="TODO")
    args = parser.parse_args()

    paths = discover_paths(
        merchant_version=args.merchant_version,
        iso_version=args.iso_version,
        gdp_version=args.gdp_version,
        bucket_version=args.bucket_version,
        numeric_version=args.numeric_version,
        math_version=args.math_version,
        model_version=args.model_version,
        model_timestamp=args.model_timestamp,
    )

    output_path = args.output.resolve()

    config = {
        **paths,
        "output_dir": args.output_dir,
        "git_commit": args.git_commit,
        "seed": args.seed,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    try:
        rel_path = output_path.relative_to(ROOT)
    except ValueError:
        rel_path = output_path
    print(f"wrote {rel_path}")


if __name__ == "__main__":
    main()
