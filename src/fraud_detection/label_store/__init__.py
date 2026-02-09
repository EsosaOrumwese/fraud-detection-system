"""Label Store contract and identity surfaces (Phase 5.1)."""

from .contracts import (
    EVIDENCE_REF_TYPES,
    LABEL_TYPES,
    LABEL_VALUES_BY_TYPE,
    SOURCE_TYPES,
    EvidenceRef,
    LabelAssertion,
    LabelStoreContractError,
    LabelSubjectKey,
)
from .ids import (
    LABEL_ASSERTION_ID_RECIPE_V1,
    LABEL_ASSERTION_PAYLOAD_HASH_RECIPE_V1,
    canonical_label_assertion_payload_hash,
    deterministic_label_assertion_id,
)
from .writer_boundary import (
    LS_WRITE_ACCEPTED,
    LS_WRITE_REJECTED,
    REASON_ASSERTION_COMMITTED_NEW,
    REASON_ASSERTION_REPLAY_MATCH,
    REASON_CONTRACT_INVALID,
    REASON_DEDUPE_TUPLE_COLLISION,
    REASON_MISSING_EVIDENCE_REFS,
    REASON_PAYLOAD_HASH_MISMATCH,
    LabelAssertionWriteRecord,
    LabelStoreWriteResult,
    LabelStoreWriterBoundary,
    LabelStoreWriterError,
)

__all__ = [
    "EVIDENCE_REF_TYPES",
    "LABEL_ASSERTION_ID_RECIPE_V1",
    "LABEL_ASSERTION_PAYLOAD_HASH_RECIPE_V1",
    "LABEL_TYPES",
    "LABEL_VALUES_BY_TYPE",
    "SOURCE_TYPES",
    "EvidenceRef",
    "LabelAssertion",
    "LabelStoreContractError",
    "LabelStoreWriteResult",
    "LabelStoreWriterBoundary",
    "LabelStoreWriterError",
    "LabelAssertionWriteRecord",
    "LS_WRITE_ACCEPTED",
    "LS_WRITE_REJECTED",
    "REASON_ASSERTION_COMMITTED_NEW",
    "REASON_ASSERTION_REPLAY_MATCH",
    "REASON_CONTRACT_INVALID",
    "REASON_DEDUPE_TUPLE_COLLISION",
    "REASON_MISSING_EVIDENCE_REFS",
    "REASON_PAYLOAD_HASH_MISMATCH",
    "LabelSubjectKey",
    "canonical_label_assertion_payload_hash",
    "deterministic_label_assertion_id",
]
