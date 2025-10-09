"""Export helpers for hurdle/NB coefficient bundles."""

from __future__ import annotations

import yaml
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from .design import DesignDictionaries, build_design_matrices
from .fit import HurdleFit, fit_hurdle_coefficients
from .persist import (
    SimulationArtefacts,
    load_persisted_corpus,
    materialise_simulated_corpus,
)
from .simulator import SimulatedHurdleCorpus
from .config import load_simulation_config
from .universe import MerchantUniverseSources


@dataclass(frozen=True)
class HurdleExportBundle:
    output_dir: Path
    hurdle_yaml: Path
    dispersion_yaml: Path
    manifest_path: Path
    fit: HurdleFit
    dictionaries: DesignDictionaries
    diagnostics: dict[str, object]


def _to_float_list(array: np.ndarray) -> list[float]:
    return [float(x) for x in array.tolist()]


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def generate_export_bundle(
    *,
    config_path: Path,
    sources: MerchantUniverseSources,
    run_base: Path,
    output_dir: Path,
    version: Optional[str] = None,
    semver: str = "0.1.0",
    timestamp: Optional[datetime] = None,
) -> HurdleExportBundle:
    """Simulate, fit, and export hurdle/NB coefficient YAML bundles."""

    timestamp = timestamp or datetime.now(timezone.utc)
    version = version or timestamp.strftime("%Y-%m-%d")
    ts_label = timestamp.strftime("%Y%m%dT%H%M%SZ")

    artefacts: SimulationArtefacts = materialise_simulated_corpus(
        output_base=run_base,
        config_path=config_path,
        sources=sources,
        timestamp=timestamp,
    )
    corpus: SimulatedHurdleCorpus = load_persisted_corpus(artefacts.manifest_path)
    matrices = build_design_matrices(corpus)
    fit = fit_hurdle_coefficients(matrices)

    export_dir = output_dir / f"version={version}" / ts_label
    export_dir.mkdir(parents=True, exist_ok=True)

    config = load_simulation_config(config_path)

    hurdle_payload = {
        "semver": semver,
        "version": version,
        "metadata": {
            "simulation_manifest": str(artefacts.manifest_path.resolve()),
            "rng_seed": config.rng.seed,
            "generated_at_utc": ts_label,
            "logistic_iterations": fit.diagnostics.logistic_iterations,
            "logistic_converged": fit.diagnostics.logistic_converged,
            "logistic_final_step": fit.diagnostics.logistic_final_step,
        },
        "dicts": {
            "mcc": [int(x) for x in matrices.dictionaries.mcc],
            "channel": list(matrices.dictionaries.channel),
            "gdp_bucket": [int(x) for x in matrices.dictionaries.gdp_bucket],
        },
        "beta": _to_float_list(fit.beta),
        "beta_mu": _to_float_list(fit.beta_mu),
    }

    dispersion_payload = {
        "semver": semver,
        "version": version,
        "metadata": {
            "simulation_manifest": str(artefacts.manifest_path.resolve()),
            "rng_seed": config.rng.seed,
            "generated_at_utc": ts_label,
        },
        "dicts": {
            "mcc": [int(x) for x in matrices.dictionaries.mcc],
            "channel": list(matrices.dictionaries.channel),
        },
        "design_order": {
            "intercept": True,
            "mcc_one_hot": True,
            "channel_block": True,
            "ln_gdp_pc_usd_2015": True,
        },
        "beta_phi": _to_float_list(fit.beta_phi),
    }

    hurdle_yaml = export_dir / "hurdle_coefficients.yaml"
    dispersion_yaml = export_dir / "nb_dispersion_coefficients.yaml"

    _write_yaml(hurdle_yaml, hurdle_payload)
    _write_yaml(dispersion_yaml, dispersion_payload)

    diagnostics = {
        "overall_multi_rate": float(corpus.logistic["is_multi"].mean()),
        "nb_rows": int(corpus.nb_mean.height),
        "logistic_rows": int(corpus.logistic.height),
    }

    return HurdleExportBundle(
        output_dir=export_dir,
        hurdle_yaml=hurdle_yaml,
        dispersion_yaml=dispersion_yaml,
        manifest_path=artefacts.manifest_path,
        fit=fit,
        dictionaries=matrices.dictionaries,
        diagnostics=diagnostics,
    )
