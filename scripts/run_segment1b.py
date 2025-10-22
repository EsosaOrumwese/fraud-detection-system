#!/usr/bin/env python3
"""
Execute Segment 1B (S0 → S2) for one or more parameter hashes using a YAML config.

The config file contains a list named ``runs`` where each entry supplies the
arguments accepted by ``python -m engine.cli.segment1b run``. This wrapper keeps
nightly orchestration repeatable without requiring long CLI invocations.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENGINE_SRC = ROOT / "packages" / "engine" / "src"

for candidate in (str(ROOT), str(ENGINE_SRC)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from engine.cli import segment1b as s1b_cli  # noqa: E402


def _load_runs(config_path: Path) -> Iterable[Dict[str, Any]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "runs" not in payload:
        raise ValueError("config must be a mapping with a 'runs' key")
    runs = payload["runs"]
    if not isinstance(runs, list):
        raise ValueError("'runs' must be a list of run descriptors")
    validated: list[Dict[str, Any]] = []
    for entry in runs:
        if not isinstance(entry, dict):
            raise ValueError("run entries must be mappings")
        if "parameter_hash" not in entry:
            raise ValueError("run entry missing 'parameter_hash'")
        validated.append(entry)
    return validated


def _build_cli_args(run: Dict[str, Any]) -> list[str]:
    args: list[str] = ["run"]
    args.extend(["--parameter-hash", str(run["parameter_hash"])])
    data_root = Path(run.get("data_root", "."))
    args.extend(["--data-root", str(data_root)])
    if "basis" in run:
        args.extend(["--basis", str(run["basis"])])
    if "dp" in run:
        args.extend(["--dp", str(run["dp"])])
    if "dictionary" in run:
        args.extend(["--dictionary", str(run["dictionary"])])
    if "manifest_fingerprint" in run:
        args.extend(["--manifest-fingerprint", str(run["manifest_fingerprint"])])
    if "seed" in run:
        args.extend(["--seed", str(run["seed"])])
    if "validation_bundle" in run:
        args.extend(["--validation-bundle", str(run["validation_bundle"])])
    if "notes" in run:
        args.extend(["--notes", str(run["notes"])])
    if run.get("skip_s0"):
        args.append("--skip-s0")
    return args


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="YAML file describing one or more Segment 1B runs.",
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        help="Optional path to write the orchestrator summaries.",
    )
    args = parser.parse_args(argv)

    config_path = args.config.expanduser().resolve()
    runs = list(_load_runs(config_path))
    summaries: list[Dict[str, Any]] = []

    for run_spec in runs:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = s1b_cli.main(_build_cli_args(run_spec))
        if exit_code != 0:
            sys.stderr.write(buffer.getvalue())
            return exit_code
        try:
            summary = json.loads(buffer.getvalue())
        except json.JSONDecodeError:
            summary = None
        if summary:
            summaries.append(summary)
        else:
            print(buffer.getvalue(), end="", flush=True)

    if args.results_json and summaries:
        args.results_json.expanduser().resolve().write_text(
            json.dumps(summaries, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())