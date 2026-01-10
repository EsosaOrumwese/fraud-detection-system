"""Constant values used across the S8 outlet catalogue pipeline."""

from __future__ import annotations

from pathlib import Path

MODULE_NAME = "1A.site_id_allocator"
SUBSTREAM_SEQUENCE_FINALIZE = "sequence_finalize"
SUBSTREAM_SITE_SEQUENCE_OVERFLOW = "site_sequence_overflow"

EVENT_FAMILY_SEQUENCE_FINALIZE = "rng_event_sequence_finalize"
EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW = "rng_event_site_sequence_overflow"

SEQUENCE_FINALIZE_SCHEMA_REF = "schemas.layer1.yaml#/rng/events/sequence_finalize"
SITE_SEQUENCE_OVERFLOW_SCHEMA_REF = "schemas.layer1.yaml#/rng/events/site_sequence_overflow"

DATASET_OUTLET_CATALOGUE = "outlet_catalogue"

VALIDATION_BUNDLE_DIRNAME = "validation_bundle_1A"

STAGE_LOG_ROOT = Path("logs/stages/s8_outlet_catalogue")
STAGE_LOG_FILENAME = "S8_STAGES.jsonl"

__all__ = [
    "MODULE_NAME",
    "SUBSTREAM_SEQUENCE_FINALIZE",
    "SUBSTREAM_SITE_SEQUENCE_OVERFLOW",
    "EVENT_FAMILY_SEQUENCE_FINALIZE",
    "EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW",
    "SEQUENCE_FINALIZE_SCHEMA_REF",
    "SITE_SEQUENCE_OVERFLOW_SCHEMA_REF",
    "DATASET_OUTLET_CATALOGUE",
    "VALIDATION_BUNDLE_DIRNAME",
    "STAGE_LOG_ROOT",
    "STAGE_LOG_FILENAME",
]
