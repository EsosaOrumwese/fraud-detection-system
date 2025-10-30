"""Layer 1 / Segment 1A State 8 outlet catalogue package."""

from .constants import (
    DATASET_OUTLET_CATALOGUE,
    EVENT_FAMILY_SEQUENCE_FINALIZE,
    EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW,
    MODULE_NAME,
    SEQUENCE_FINALIZE_SCHEMA_REF,
    SITE_SEQUENCE_OVERFLOW_SCHEMA_REF,
    STAGE_LOG_FILENAME,
    STAGE_LOG_ROOT,
    SUBSTREAM_SEQUENCE_FINALIZE,
    SUBSTREAM_SITE_SEQUENCE_OVERFLOW,
    VALIDATION_BUNDLE_DIRNAME,
)
from .contexts import (
    CountrySequencingInput,
    MerchantSequencingInput,
    S8DeterministicContext,
    S8Metrics,
    ValidationBundlePaths,
)
from .kernel import build_outlet_catalogue
from .loader import load_deterministic_context
from .persist import (
    PersistConfig,
    write_outlet_catalogue,
    write_sequence_events,
    write_validation_bundle,
)
from .runner import S8RunOutputs, S8Runner
from .types import (
    OutletCatalogueRow,
    SequenceFinalizeEvent,
    SiteSequenceOverflowEvent,
)
from .validate import S8ValidationError, validate_outputs

__all__ = [
    "DATASET_OUTLET_CATALOGUE",
    "EVENT_FAMILY_SEQUENCE_FINALIZE",
    "EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW",
    "MODULE_NAME",
    "SEQUENCE_FINALIZE_SCHEMA_REF",
    "SITE_SEQUENCE_OVERFLOW_SCHEMA_REF",
    "STAGE_LOG_FILENAME",
    "STAGE_LOG_ROOT",
    "SUBSTREAM_SEQUENCE_FINALIZE",
    "SUBSTREAM_SITE_SEQUENCE_OVERFLOW",
    "VALIDATION_BUNDLE_DIRNAME",
    "CountrySequencingInput",
    "MerchantSequencingInput",
    "S8DeterministicContext",
    "S8Metrics",
    "ValidationBundlePaths",
    "build_outlet_catalogue",
    "load_deterministic_context",
    "PersistConfig",
    "write_outlet_catalogue",
    "write_sequence_events",
    "write_validation_bundle",
    "S8Runner",
    "S8RunOutputs",
    "OutletCatalogueRow",
    "SequenceFinalizeEvent",
    "SiteSequenceOverflowEvent",
    "S8ValidationError",
    "validate_outputs",
]
