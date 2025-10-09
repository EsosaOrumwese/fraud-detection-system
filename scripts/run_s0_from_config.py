#!/usr/bin/env python3
"""
Execute the S0 orchestrator using a JSON config file.

The config format matches ``configs/runs/s0_synthetic_config.json``: each entry
points to the artefact paths the run should seal and the destination output
directory.  This helper keeps the CLI invocation repeatable (``make run-s0``)
without requiring callers to spell out every argument manually.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ENGINE_SRC = ROOT / "packages" / "engine" / "src"
if str(ENGINE_SRC) not in sys.path:
    sys.path.insert(0, str(ENGINE_SRC))

from engine.layers.l1.seg_1A.s0_foundations import (
    S0FoundationsRunner,
    SchemaAuthority,
)
from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error


def _load_config(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config root must be an object")
    required = {
        "merchant_table",
        "iso_table",
        "gdp_table",
        "bucket_table",
        "hurdle_coefficients",
        "nb_dispersion_coefficients",
        "crossborder_policy",
        "output_dir",
        "git_commit",
        "seed",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"config missing keys: {missing}")
    return data


def _normalise_config_path(value: object) -> Path:
    """Return an absolute path from a JSON config value.

    The config files are authored with Windows-style path separators (``\\``)
    so we normalise them to POSIX (``/``) before handing them to ``Path``.
    Relative paths are interpreted relative to the repository root.
    """

    candidate = Path(str(value).replace("\\", "/")).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="JSON file describing the S0 run inputs.",
    )
    parser.add_argument(
        "--context-json",
        type=Path,
        help="Optional path to write {run_id, parameter_hash, manifest_fingerprint}.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip re-opening persisted artefacts after the run.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level for progress messages (default: INFO).",
    )
    args = parser.parse_args(argv)

    _configure_logging(args.log_level)

    config_path = args.config.expanduser().resolve()
    config = _load_config(config_path)

    def _as_path(key: str) -> Path:
        return _normalise_config_path(config[key])

    authority = SchemaAuthority(
        ingress_ref="l1/seg_1A/merchant_ids.schema.json",
        segment_ref="l1/seg_1A/s0_outputs.schema.json",
        rng_ref="layer1/schemas.layer1.yaml",
    )
    runner = S0FoundationsRunner(schema_authority=authority)

    parameter_files = {
        "hurdle_coefficients.yaml": _as_path("hurdle_coefficients"),
        "nb_dispersion_coefficients.yaml": _as_path("nb_dispersion_coefficients"),
        "crossborder_hyperparams.yaml": _as_path("crossborder_policy"),
    }

    numeric_policy_path = (
        _as_path("numeric_policy") if "numeric_policy" in config else None
    )
    math_profile_manifest_path = (
        _as_path("math_profile_manifest") if "math_profile_manifest" in config else None
    )

    try:
        result = runner.run_from_paths(
            base_path=_as_path("output_dir"),
            merchant_table_path=_as_path("merchant_table"),
            iso_table_path=_as_path("iso_table"),
            gdp_table_path=_as_path("gdp_table"),
            bucket_table_path=_as_path("bucket_table"),
            parameter_files=parameter_files,
            git_commit_hex=str(config["git_commit"]),
            seed=int(config["seed"]),
            numeric_policy_path=numeric_policy_path,
            math_profile_manifest_path=math_profile_manifest_path,
            validate=not args.no_validate,
        )
    except S0Error as exc:
        print(f"[run_s0] failed: {exc}", file=sys.stderr)
        return 1

    sealed = result.sealed
    print(
        "S0 run complete:\n"
        f"  run_id:             {result.run_id}\n"
        f"  parameter_hash:     {sealed.parameter_hash.parameter_hash}\n"
        f"  manifest_fingerprint: {sealed.manifest_fingerprint.manifest_fingerprint}\n"
        f"  output_dir:         {result.base_path}"
    )

    if args.context_json:
        payload = {
            "run_id": result.run_id,
            "parameter_hash": sealed.parameter_hash.parameter_hash,
            "manifest_fingerprint": sealed.manifest_fingerprint.manifest_fingerprint,
            "output_dir": str(result.base_path),
        }
        args.context_json.expanduser().resolve().write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
