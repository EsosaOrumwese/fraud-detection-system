"""Persistence helpers for simulated hurdle corpora."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

import polars as pl

from .config import SimulationConfig, load_simulation_config
from .simulator import SimulatedHurdleCorpus, simulate_hurdle_corpus
from .validate import validate_simulation_run
from .universe import MerchantUniverseSources


@dataclass(frozen=True)
class SimulationArtefacts:
    base_path: Path
    run_path: Path
    manifest_path: Path
    dataset_paths: Mapping[str, Path]


def _write_parquet(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path, compression="zstd")


def _manifest_payload(
    *,
    config: SimulationConfig,
    config_path: Path,
    sources: MerchantUniverseSources,
    corpus: SimulatedHurdleCorpus,
    dataset_paths: Mapping[str, Path],
    generated_at: str,
    run_dir: Path,
) -> dict:
    return {
        "simulation_config": {
            "version": config.version,
            "semver": config.semver,
            "config_path": str(config_path),
            "rng": {"algorithm": config.rng.algorithm, "seed": config.rng.seed},
        },
        "sources": {
            "merchant_table": str(sources.merchant_table),
            "iso_table": str(sources.iso_table),
            "gdp_table": str(sources.gdp_table),
            "bucket_table": str(sources.bucket_table),
        },
        "generated_at_utc": generated_at,
        "datasets": {
            name: str(path.relative_to(run_dir)) if path.is_relative_to(run_dir) else str(path)
            for name, path in dataset_paths.items()
        },
        "summary": corpus.summary(),
    }


def materialise_simulated_corpus(
    *,
    output_base: Path,
    config_path: Path,
    sources: MerchantUniverseSources,
    timestamp: Optional[datetime] = None,
) -> SimulationArtefacts:
    """Run the simulator and persist artefacts under ``output_base``."""
    config = load_simulation_config(config_path)
    corpus = simulate_hurdle_corpus(sources=sources, config=config)

    ts = timestamp or datetime.now(timezone.utc)
    ts_label = ts.strftime("%Y%m%dT%H%M%SZ")
    run_dir = (
        output_base
        / f"simulation_version={config.version}"
        / f"seed={config.rng.seed}"
        / ts_label
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    datasets: dict[str, Path] = {
        "logistic": run_dir / "logistic.parquet",
        "nb_mean": run_dir / "nb_mean.parquet",
        "brand_aliases": run_dir / "brand_aliases.parquet",
        "channel_roster": run_dir / "channel_roster.parquet",
    }

    _write_parquet(corpus.logistic, datasets["logistic"])
    _write_parquet(corpus.nb_mean, datasets["nb_mean"])
    _write_parquet(corpus.brand_aliases, datasets["brand_aliases"])
    _write_parquet(corpus.channel_roster, datasets["channel_roster"])

    manifest_path = run_dir / "manifest.json"
    manifest_payload = _manifest_payload(
        config=config,
        config_path=config_path,
        sources=sources,
        corpus=corpus,
        dataset_paths=datasets,
        generated_at=ts_label,
        run_dir=run_dir,
    )
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True), encoding="utf-8")

    validation = validate_simulation_run(run_dir)
    if not validation.ok:
        detailed = "\n".join(f"- {msg}" for msg in validation.messages)
        raise ValueError(f"persisted corpus failed validation:\n{detailed}")

    return SimulationArtefacts(
        base_path=output_base,
        run_path=run_dir,
        manifest_path=manifest_path,
        dataset_paths=datasets,
    )


def load_persisted_corpus(manifest_path: Path) -> SimulatedHurdleCorpus:
    """Re-open a persisted synthetic corpus from a manifest.json path."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    datasets = manifest.get("datasets", {})
    base_dir = manifest_path.parent

    def _resolve(name: str) -> Path:
        raw = datasets.get(name)
        if raw is None:
            raise ValueError(f"manifest missing dataset entry for '{name}'")
        path = Path(raw)
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"dataset '{name}' not found at {path}")
        return path

    logistic = pl.read_parquet(_resolve("logistic"))
    nb_mean = pl.read_parquet(_resolve("nb_mean"))
    aliases = pl.read_parquet(_resolve("brand_aliases"))
    channel_roster = pl.read_parquet(_resolve("channel_roster"))
    return SimulatedHurdleCorpus(
        logistic=logistic,
        nb_mean=nb_mean,
        brand_aliases=aliases,
        channel_roster=channel_roster,
    )
