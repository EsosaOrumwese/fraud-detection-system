"""Hurdle-model training helpers (simulation, fitting, export)."""

from .config import (
    DispersionPrior,
    HurdlePrior,
    NBMeanPrior,
    RNGConfig,
    SimulationConfig,
    load_simulation_config,
)
from .persist import SimulationArtefacts, materialise_simulated_corpus
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
    "ValidationResult",
    "validate_simulation_run",
]
