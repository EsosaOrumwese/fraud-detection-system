"""CLI wrapper for running Layer-1 Segment 1A state-1 hurdle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl
import yaml

from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error, err
from engine.layers.l1.seg_1A.s0_foundations.l1.design import load_hurdle_coefficients
from engine.layers.l1.seg_1A.s1_hurdle import HurdleDesignRow, S1HurdleRunner
from engine.layers.l1.seg_1A.s1_hurdle.l3.validator import validate_hurdle_run


def _load_design_rows(path: Path) -> list[HurdleDesignRow]:
    frame = pl.read_parquet(path)
    if "x_hurdle" not in frame.columns or "merchant_id" not in frame.columns:
        raise err("E_DATASET_NOT_FOUND", "design matrix missing required columns")
    bucket_col = "bucket" if "bucket" in frame.columns else "gdp_bucket_id"
    if bucket_col not in frame.columns:
        raise err("E_DATASET_NOT_FOUND", "design matrix missing GDP bucket column")
    rows: list[HurdleDesignRow] = []
    for record in frame.iter_rows(named=True):
        vector = tuple(float(value) for value in record["x_hurdle"])
        rows.append(
            HurdleDesignRow(
                merchant_id=int(record["merchant_id"]),
                bucket_id=int(record[bucket_col]),
                design_vector=vector,
            )
        )
    return rows


def _load_beta(path: Path) -> tuple[float, ...]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    coefficients = load_hurdle_coefficients(data)
    return coefficients.beta


def _load_context(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Layer-1 Segment 1A state-1 hurdle over a sealed S0 dataset.",
    )
    parser.add_argument("--output-dir", type=Path, help="Root directory that houses logs and parameter-scoped outputs.")
    parser.add_argument("--design-matrix", required=True, type=Path, help="Path to the hurdle design matrix parquet emitted by S0.")
    parser.add_argument("--hurdle-coeff", required=True, type=Path, help="Path to hurdle_coefficients.yaml.")
    parser.add_argument("--parameter-hash", help="Parameter hash for the run (overrides context JSON).")
    parser.add_argument("--manifest-fingerprint", help="Manifest fingerprint for the run (overrides context JSON).")
    parser.add_argument("--run-id", help="Run identifier (overrides context JSON).")
    parser.add_argument("--seed", type=int, help="Philox seed (overrides context JSON).")
    parser.add_argument("--context-json", type=Path, help="Optional JSON produced by S0 CLI with run metadata.")
    parser.add_argument("--result-json", dest="result_json", type=Path, help="Optional JSON file to persist S1 run summary.")
    parser.add_argument("--no-validate", dest="validate", action="store_false", help="Skip validation of emitted hurdle events.")

    args = parser.parse_args(argv)

    context = _load_context(args.context_json.expanduser().resolve() if args.context_json else None)

    output_dir_raw = args.output_dir or context.get("output_dir")
    if output_dir_raw is None:
        parser.error("--output-dir or context output_dir must be provided")
    output_dir = Path(output_dir_raw).expanduser().resolve()

    parameter_hash = args.parameter_hash or context.get("parameter_hash")
    if parameter_hash is None:
        parser.error("--parameter-hash or context parameter_hash must be provided")

    manifest_fingerprint = args.manifest_fingerprint or context.get("manifest_fingerprint")
    if manifest_fingerprint is None:
        parser.error("--manifest-fingerprint or context manifest_fingerprint must be provided")

    run_id = args.run_id or context.get("run_id")
    if run_id is None:
        parser.error("--run-id or context run_id must be provided")

    seed_value = args.seed if args.seed is not None else context.get("seed")
    if seed_value is None:
        parser.error("--seed or context seed must be provided")
    seed = int(seed_value)

    design_rows = _load_design_rows(args.design_matrix.expanduser().resolve())
    beta = _load_beta(args.hurdle_coeff.expanduser().resolve())

    runner = S1HurdleRunner()
    try:
        result = runner.run(
            base_path=output_dir,
            manifest_fingerprint=str(manifest_fingerprint),
            parameter_hash=str(parameter_hash),
            beta=beta,
            design_rows=design_rows,
            seed=seed,
            run_id=str(run_id),
        )
    except S0Error as exc:
        print(f"[s1-run] failed: {exc}", file=sys.stderr)
        return 1

    if args.validate:
        validate_hurdle_run(
            base_path=output_dir,
            manifest_fingerprint=str(manifest_fingerprint),
            parameter_hash=str(parameter_hash),
            seed=seed,
            run_id=str(run_id),
            beta=beta,
            design_rows=design_rows,
        )

    if args.result_json:
        summary = {
            "run_id": result.run_id,
            "parameter_hash": result.parameter_hash,
            "manifest_fingerprint": result.manifest_fingerprint,
            "seed": result.seed,
            "events_path": str(result.events_path),
            "trace_path": str(result.trace_path),
            "catalogue_path": str(result.catalogue_path),
            "multi_merchant_ids": list(result.multi_merchant_ids),
            "gated_streams": [
                {
                    "dataset_id": stream.dataset_id,
                    "path": stream.path,
                    "predicate": stream.predicate,
                    "also_requires": list(stream.also_requires),
                    "owner": stream.owner,
                    "section": stream.section,
                }
                for stream in result.gated_streams
            ],
        }
        args.result_json.expanduser().resolve().write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
