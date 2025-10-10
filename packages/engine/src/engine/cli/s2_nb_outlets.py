"""CLI wrapper for running Layer-1 Segment 1A state-2 NB outlet sampling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import polars as pl
import yaml

from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error, err
from engine.layers.l1.seg_1A.s0_foundations.l1.design import (
    DesignVectors,
    HurdleCoefficients,
    load_dispersion_coefficients,
    load_hurdle_coefficients,
)
from engine.layers.l1.seg_1A.s1_hurdle.l1.rng import HURDLE_MODULE_NAME, HURDLE_SUBSTREAM_LABEL
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets import (
    S2NegativeBinomialRunner,
    build_deterministic_context,
    validate_nb_run,
)


def _load_context(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _hurdle_events_path(
    *,
    output_dir: Path,
    seed: int,
    parameter_hash: str,
    run_id: str,
) -> Path:
    partition = (
        Path(f"seed={seed}")
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )
    return (
        output_dir
        / "logs"
        / "rng"
        / "events"
        / HURDLE_SUBSTREAM_LABEL
        / partition
        / "part-00000.jsonl"
    )


def _design_vectors_from_parquet(path: Path) -> tuple[DesignVectors, ...]:
    frame = pl.read_parquet(path)
    required = {
        "merchant_id",
        "bucket",
        "gdp_pc_usd_2015",
        "log_gdp_pc_usd_2015",
        "x_hurdle",
        "x_nb_mean",
        "x_nb_dispersion",
    }
    missing = required - set(frame.columns)
    if missing:
        raise err(
            "E_DATASET_NOT_FOUND",
            f"design matrix missing columns {sorted(missing)}",
        )
    vectors = []
    for record in frame.iter_rows(named=True):
        vectors.append(
            DesignVectors(
                merchant_id=int(record["merchant_id"]),
                bucket=int(record["bucket"]),
                gdp=float(record["gdp_pc_usd_2015"]),
                log_gdp=float(record["log_gdp_pc_usd_2015"]),
                x_hurdle=tuple(float(x) for x in record["x_hurdle"]),
                x_nb_mean=tuple(float(x) for x in record["x_nb_mean"]),
                x_nb_dispersion=tuple(float(x) for x in record["x_nb_dispersion"]),
            )
        )
    if not vectors:
        raise err("E_DATASET_EMPTY", "design matrix produced no rows for S2")
    return tuple(vectors)


def _load_coefficients(path: Path) -> HurdleCoefficients:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise err("E_JSON_STRUCTURE", "hurdle coefficients YAML must decode to a mapping")
    return load_hurdle_coefficients(data)


def _load_dispersion(path: Path, *, hurdle: HurdleCoefficients):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise err("E_JSON_STRUCTURE", "dispersion coefficients YAML must decode to a mapping")
    return load_dispersion_coefficients(data, reference=hurdle.dictionaries)


def _load_hurdle_decisions(path: Path) -> tuple[HurdleDecision, ...]:
    if not path.exists():
        raise err("E_DATASET_NOT_FOUND", f"hurdle event log missing at '{path}'")
    decisions: list[HurdleDecision] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        if record.get("module") != HURDLE_MODULE_NAME or record.get("substream_label") != HURDLE_SUBSTREAM_LABEL:
            raise err(
                "E_VALIDATION_MISMATCH",
                "unexpected module/substream in hurdle event log",
            )
        decisions.append(
            HurdleDecision(
                merchant_id=int(record["merchant_id"]),
                eta=float(record["eta"]),
                pi=float(record["pi"]),
                deterministic=bool(record["deterministic"]),
                is_multi=bool(record["is_multi"]),
                u=float(record["u"]) if record.get("u") is not None else None,
                rng_counter_before=(
                    int(record["rng_counter_before_hi"]),
                    int(record["rng_counter_before_lo"]),
                ),
                rng_counter_after=(
                    int(record["rng_counter_after_hi"]),
                    int(record["rng_counter_after_lo"]),
                ),
                draws=int(record["draws"]),
                blocks=int(record["blocks"]),
            )
        )
    if not decisions:
        raise err("E_DATASET_EMPTY", f"hurdle event log at '{path}' contained no rows")
    return tuple(decisions)


def _multi_ids(decisions: Sequence[HurdleDecision]) -> tuple[int, ...]:
    return tuple(sorted({decision.merchant_id for decision in decisions if decision.is_multi}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Layer-1 Segment 1A state-2 NB outlet sampler over sealed inputs.",
    )
    parser.add_argument("--output-dir", type=Path, help="Root directory that houses logs and parameter-scoped outputs.")
    parser.add_argument("--design-matrix", required=True, type=Path, help="Path to the hurdle design matrix parquet emitted by S0.")
    parser.add_argument("--hurdle-coeff", required=True, type=Path, help="Path to hurdle_coefficients.yaml.")
    parser.add_argument("--dispersion-coeff", required=True, type=Path, help="Path to nb_dispersion_coefficients.yaml.")
    parser.add_argument("--parameter-hash", help="Parameter hash for the run (overrides context JSON).")
    parser.add_argument("--manifest-fingerprint", help="Manifest fingerprint for the run (overrides context JSON).")
    parser.add_argument("--run-id", help="Run identifier (overrides context JSON).")
    parser.add_argument("--seed", type=int, help="Philox seed (overrides context JSON).")
    parser.add_argument("--context-json", type=Path, help="Optional JSON produced by S0/S1 CLI with run metadata.")
    parser.add_argument("--result-json", dest="result_json", type=Path, help="Optional JSON file to persist S2 run summary.")
    parser.add_argument("--no-validate", dest="validate", action="store_false", help="Skip validation of emitted S2 events.")

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

    design_matrix_path = args.design_matrix.expanduser().resolve()
    hurdle_coeff_path = args.hurdle_coeff.expanduser().resolve()
    dispersion_coeff_path = args.dispersion_coeff.expanduser().resolve()

    design_vectors = _design_vectors_from_parquet(design_matrix_path)
    hurdle_coefficients = _load_coefficients(hurdle_coeff_path)
    dispersion_coefficients = _load_dispersion(dispersion_coeff_path, hurdle=hurdle_coefficients)

    hurdle_events = _hurdle_events_path(
        output_dir=output_dir,
        seed=seed,
        parameter_hash=str(parameter_hash),
        run_id=str(run_id),
    )
    decisions = _load_hurdle_decisions(hurdle_events)
    multi_ids = _multi_ids(decisions)

    deterministic_context = build_deterministic_context(
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        run_id=str(run_id),
        seed=seed,
        multi_merchant_ids=multi_ids,
        decisions=decisions,
        design_vectors=design_vectors,
        hurdle=hurdle_coefficients,
        dispersion=dispersion_coefficients,
    )

    runner = S2NegativeBinomialRunner()
    try:
        result = runner.run(
            base_path=output_dir,
            deterministic=deterministic_context,
        )
    except S0Error as exc:  # pragma: no cover - exercised in integration tests
        print(f"[s2-run] failed: {exc}", file=sys.stderr)
        return 1

    if args.validate:
        validate_nb_run(
            base_path=output_dir,
            deterministic=deterministic_context,
            expected_finals=result.finals,
        )

    if args.result_json:
        summary = {
            "run_id": result.deterministic.run_id,
            "parameter_hash": result.deterministic.parameter_hash,
            "manifest_fingerprint": result.deterministic.manifest_fingerprint,
            "seed": result.deterministic.seed,
            "gamma_events_path": str(result.gamma_events_path),
            "poisson_events_path": str(result.poisson_events_path),
            "nb_final_path": str(result.final_events_path),
            "trace_path": str(result.trace_path),
            "finals": [
                {
                    "merchant_id": record.merchant_id,
                    "mu": record.mu,
                    "phi": record.phi,
                    "n_outlets": record.n_outlets,
                    "nb_rejections": record.nb_rejections,
                    "attempts": record.attempts,
                }
                for record in result.finals
            ],
        }
        args.result_json.expanduser().resolve().write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
