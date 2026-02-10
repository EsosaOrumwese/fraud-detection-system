"""Model Factory Phase 1 surfaces."""

from .contracts import MfPhase1ContractError, MfTrainBuildRequest, TargetScope
from .ids import (
    MF_TRAIN_RUN_ID_RECIPE_V1,
    MF_TRAIN_RUN_KEY_RECIPE_V1,
    canonical_train_run_key_payload,
    deterministic_train_run_id,
    train_run_key,
)

__all__ = [
    "MfPhase1ContractError",
    "MfTrainBuildRequest",
    "TargetScope",
    "MF_TRAIN_RUN_KEY_RECIPE_V1",
    "MF_TRAIN_RUN_ID_RECIPE_V1",
    "canonical_train_run_key_payload",
    "train_run_key",
    "deterministic_train_run_id",
]

