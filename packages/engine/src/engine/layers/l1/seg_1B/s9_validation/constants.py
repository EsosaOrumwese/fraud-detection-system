"""Constant definitions used by the Segment 1B S9 validation pipeline."""

from __future__ import annotations

from pathlib import Path

BUNDLE_ROOT_DATASET_ID = "validation_bundle_1B"
BUNDLE_FLAG_DATASET_ID = "validation_passed_flag_1B"

DATASET_S7_SITE_SYNTHESIS = "s7_site_synthesis"
DATASET_SITE_LOCATIONS = "site_locations"

RNG_EVENT_SITE_TILE_ASSIGN = "rng_event_site_tile_assign"
RNG_EVENT_IN_CELL_JITTER = "rng_event_in_cell_jitter"
RNG_TRACE_LOG = "rng_trace_log"
RNG_AUDIT_LOG = "rng_audit_log"

RNG_EVENT_FAMILIES = (
    RNG_EVENT_SITE_TILE_ASSIGN,
    RNG_EVENT_IN_CELL_JITTER,
)

BUNDLE_REQUIRED_FILES = (
    "MANIFEST.json",
    "parameter_hash_resolved.json",
    "manifest_fingerprint_resolved.json",
    "rng_accounting.json",
    "s9_summary.json",
    "egress_checksums.json",
    "index.json",
)

INDEX_SCHEMA_REF = "schemas.1A.yaml#/validation/validation_bundle.index_schema"

STAGE_LOG_ROOT = Path("logs/stages/s9_validation/segment_1B")
STAGE_LOG_FILENAME = "S9_STAGES.jsonl"

__all__ = [
    "BUNDLE_ROOT_DATASET_ID",
    "BUNDLE_FLAG_DATASET_ID",
    "BUNDLE_REQUIRED_FILES",
    "DATASET_S7_SITE_SYNTHESIS",
    "DATASET_SITE_LOCATIONS",
    "INDEX_SCHEMA_REF",
    "RNG_AUDIT_LOG",
    "RNG_EVENT_FAMILIES",
    "RNG_EVENT_IN_CELL_JITTER",
    "RNG_EVENT_SITE_TILE_ASSIGN",
    "RNG_TRACE_LOG",
    "STAGE_LOG_FILENAME",
    "STAGE_LOG_ROOT",
]
