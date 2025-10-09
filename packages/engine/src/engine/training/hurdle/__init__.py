"""Hurdle-model training helpers (simulation, fitting, export)."""

from .config import (
    DispersionPrior,
    HurdlePrior,
    NBMeanPrior,
    RNGConfig,
    SimulationConfig,
    load_simulation_config,
)
from .design import DesignDictionaries, DesignMatrices, build_design_matrices
from .persist import (
    SimulationArtefacts,
    load_persisted_corpus,
    materialise_simulated_corpus,
)
from .simulator import SimulatedHurdleCorpus, simulate_hurdle_corpus
from .validate import ValidationResult, validate_simulation_run
from .universe import MerchantUniverseSources, load_enriched_universe

__all__ = [
    "DispersionPrior",
    "HurdlePrior",
    "NBMeanPrior",
    "RNGConfig",
    "SimulationConfig",
    "load_simulation_config",
    "MerchantUniverseSources",
    "load_enriched_universe",
    "SimulatedHurdleCorpus",
    "simulate_hurdle_corpus",
    "SimulationArtefacts",
    "materialise_simulated_corpus",
    "load_persisted_corpus",
    "ValidationResult",
    "validate_simulation_run",
    "DesignDictionaries",
    "DesignMatrices",
    "build_design_matrices",
]
