"""Constant values used across the S9 validation pipeline."""

from __future__ import annotations

from pathlib import Path

VALIDATION_DATASET_ID = "validation_bundle_1A"
DATASET_OUTLET_CATALOGUE = "outlet_catalogue"
DATASET_S3_CANDIDATE_SET = "s3_candidate_set"
DATASET_S3_INTEGERISED_COUNTS = "s3_integerised_counts"
DATASET_S3_SITE_SEQUENCE = "s3_site_sequence"
DATASET_S6_MEMBERSHIP = "s6_membership"

EVENT_FAMILY_NB_FINAL = "rng_event.nb_final"
EVENT_FAMILY_SEQUENCE_FINALIZE = "rng_event.sequence_finalize"
EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW = "rng_event.site_sequence_overflow"

TRACE_LOG_ID = "rng_trace_log"
AUDIT_LOG_ID = "rng_audit_log"

S6_RECEIPT_DATASET_ID = "s6_validation_receipt"

BUNDLE_FILES = {
    "MANIFEST.json",
    "parameter_hash_resolved.json",
    "manifest_fingerprint_resolved.json",
    "rng_accounting.json",
    "s9_summary.json",
    "egress_checksums.json",
    "index.json",
}

STAGE_LOG_ROOT = Path("logs/stages/s9_validation")
STAGE_LOG_FILENAME = "S9_STAGES.jsonl"

__all__ = [
    "VALIDATION_DATASET_ID",
    "DATASET_OUTLET_CATALOGUE",
    "DATASET_S3_CANDIDATE_SET",
    "DATASET_S3_INTEGERISED_COUNTS",
    "DATASET_S3_SITE_SEQUENCE",
    "DATASET_S6_MEMBERSHIP",
    "EVENT_FAMILY_NB_FINAL",
    "EVENT_FAMILY_SEQUENCE_FINALIZE",
    "EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW",
    "TRACE_LOG_ID",
    "AUDIT_LOG_ID",
    "S6_RECEIPT_DATASET_ID",
    "BUNDLE_FILES",
    "STAGE_LOG_ROOT",
    "STAGE_LOG_FILENAME",
]
