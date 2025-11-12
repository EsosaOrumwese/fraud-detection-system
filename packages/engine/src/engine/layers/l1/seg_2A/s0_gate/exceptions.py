"""Exception helpers for Segment 2A state-0 gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class S0GateError(Exception):
    """Structured error raised by the 2A gate."""

    code: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.detail}"


_LEGACY_TO_CANONICAL: dict[str, str] = {
    # ------------------------------------------------------------------ shared / S0
    "E_SEED_EMPTY": "2A-S0-010",
    "E_UPSTREAM_FINGERPRINT": "2A-S0-004",
    "E_GIT_COMMIT_LEN": "2A-S0-010",
    "E_TZDB_RELEASE_EMPTY": "2A-S0-022",
    "E_BUNDLE_MISSING": "2A-S0-003",
    "E_BUNDLE_INVALID": "2A-S0-041",
    "E_FLAG_HASH_MISMATCH": "2A-S0-002",
    "E_FLAG_FORMAT_INVALID": "2A-S0-042",
    "E_PARAM_EMPTY": "2A-S0-010",
    "E_DICTIONARY_RESOLUTION_FAILED": "2A-S0-012",
    "E_ASSET_ID_MISSING": "2A-S0-010",
    "E_ASSET_SCHEMA_MISSING": "2A-S0-011",
    "E_ASSET_EMPTY": "2A-S0-010",
    "E_ASSET_EMPTY_DIGESTS": "2A-S0-015",
    "E_ASSET_DUPLICATE": "2A-S0-016",
    "E_PASS_MISSING": "2A-S0-001",
    "E_PATH_MISSING": "2A-S0-012",
    "E_PATH_OUT_OF_SCOPE": "2A-S0-041",
    "E_RECEIPT_EXISTS": "2A-S0-060",
    "E_RECEIPT_SCHEMA_INVALID": "2A-S0-043",
    "E_S0_RECEIPT_MISSING": "2A-S0-001",
    "E_S0_RECEIPT_INVALID": "2A-S0-043",
    "E_S0_RECEIPT_MISMATCH": "2A-S0-043",
    "E_INVENTORY_EXISTS": "2A-S0-062",
    "E_SCHEMA_RESOLUTION_FAILED": "2A-S0-011",
    "E_INDEX_INVALID": "2A-S0-003",
    "E_INDEX_MISSING": "2A-S0-003",
    "E_INDEX_IO": "2A-S0-003",
    "E_MCC_SOURCE_MISSING": "2A-S0-010",
    "E_MCC_SOURCE_EMPTY": "2A-S0-010",
    "E_MCC_SOURCE_ROOT_MISSING": "2A-S0-012",
    "E_MCC_SOURCE_VERSION_MISSING": "2A-S0-014",
    "E_TZ_ADJUSTMENTS_INVALID_JSON": "2A-S3-030",
    "E_TZ_ADJUSTMENTS_SCHEMA": "2A-S3-030",
    "E_TZ_ADJUSTMENTS_MISMATCH": "2A-S3-053",
    "E_UNSAFE": "2A-S0-080",
    "E_VALIDATOR": "2A-S5-040",
    # ------------------------------------------------------------------ S1
    "E_S1_OUTPUT_EXISTS": "2A-S1-041",
    "E_S1_ASSET_MISSING": "2A-S1-001",
    "E_S1_NUDGE_POLICY_INVALID": "2A-S1-021",
    "E_S1_INVALID_CHUNK_SIZE": "2A-S1-010",
    "E_S1_INPUT_EMPTY": "2A-S1-050",
    "E_S1_INPUT_INVALID": "2A-S1-010",
    "E_S1_INPUT_SHAPE": "2A-S1-030",
    "E_S1_TZ_WORLD_INVALID": "2A-S1-020",
    "E_S1_NUDGE_PAIR_VIOLATION": "2A-S1-054",
    "E_S1_ASSIGN_BOUNDS": "2A-S1-055",
    "E_S1_ASSIGN_FAILED": "2A-S1-055",
    "E_S1_BORDER_AMBIGUITY": "2A-S1-055",
    # ------------------------------------------------------------------ S2
    "E_S2_OUTPUT_EXISTS": "2A-S2-041",
    "E_S2_RECEIPT_MISSING_ASSET": "2A-S2-001",
    "E_S2_OVERRIDES_MISSING": "2A-S2-020",
    "E_S2_OVERRIDES_INVALID": "2A-S2-020",
    "E_S2_OVERRIDES_DUPLICATE_SCOPE_TARGET": "2A-S2-021",
    "E_S2_MCC_MAP_INVALID": "2A-S2-022",
    "E_S2_TZ_WORLD_MISSING": "2A-S2-010",
    "E_S2_TZ_WORLD_EMPTY": "2A-S2-057",
    "E_S2_UNKNOWN_TZID": "2A-S2-053",
    "E_S2_TZID_NOT_IN_TZ_WORLD": "2A-S2-057",
    "E_S2_NULL_TZID": "2A-S2-052",
    "E_S2_OVERRIDE_NO_EFFECT": "2A-S2-055",
    "E_S2_COVERAGE_MISMATCH": "2A-S2-050",
    "E_S2_PK_DUPLICATE": "2A-S2-051",
    "E_S2_NO_INPUT_ROWS": "2A-S2-050",
    "E_S2_NUDGE_PAIR_VIOLATION": "2A-S2-056",
    "E_S2_UNEXPECTED": "2A-S2-080",
    # ------------------------------------------------------------------ S3
    "E_S3_ADJUSTMENTS_MISSING": "2A-S3-060",
    "E_S3_ADJUSTMENTS_EXISTS": "2A-S3-041",
    "E_S3_OUTPUT_EXISTS": "2A-S3-041",
    "E_S3_UNEXPECTED": "2A-S3-080",
    "E_S3_TZ_WORLD_EMPTY": "2A-S3-053",
    "E_S3_TZDB_ARCHIVE_MISSING": "2A-S3-010",
    "E_S3_TZDB": "2A-S3-013",
    "E_S3_INVENTORY_MISSING": "2A-S3-001",
    "E_S3_TZDB_ROW_MISSING": "2A-S3-001",
    "E_S3_TZWORLD_ROW_MISSING": "2A-S3-012",
    # ------------------------------------------------------------------ S4
    "E_S4_OUTPUT_EXISTS": "2A-S4-041",
    "E_S4_UNEXPECTED": "2A-S4-080",
    "E_S4_SITE_TZ_MISSING": "2A-S4-010",
    "E_S4_SITE_TZ_EMPTY": "2A-S4-024",
    "E_S4_CACHE_MISSING": "2A-S4-023",
    "E_S4_CACHE_FORMAT": "2A-S4-020",
    # ------------------------------------------------------------------ S5
    "E_S5_BUNDLE_EXISTS": "2A-S5-060",
    "E_S5_NO_EVIDENCE": "2A-S5-030",
    "E_S5_S4_MISSING": "2A-S5-030",
    "E_S5_S4_NOT_PASS": "2A-S5-030",
    "E_S5_S4_INVALID": "2A-S5-030",
    "E_S5_S4_SCHEMA": "2A-S5-030",
    "E_S5_S4_MISMATCH": "2A-S5-030",
    "E_S5_S4_SEED_MISMATCH": "2A-S5-011",
    "E_S5_TZ_MANIFEST_MISSING": "2A-S5-010",
    "E_S5_TZ_MANIFEST_INVALID": "2A-S5-020",
    "E_S5_TZ_MANIFEST_SCHEMA": "2A-S5-020",
    "E_S5_TZ_MANIFEST_EMPTY": "2A-S5-020",
    "E_S5_TZ_MANIFEST_RLE": "2A-S5-020",
    "E_S5_TZ_MANIFEST_FINGERPRINT": "2A-S5-011",
    "E_S5_INDEX_PATH_INVALID": "2A-S5-042",
    "E_S5_UNEXPECTED": "2A-S5-080",
}


def _translate(code: str) -> str:
    if code.startswith("2A-"):
        return code
    return _LEGACY_TO_CANONICAL.get(code, code)


def err(code: str, detail: str) -> S0GateError:
    """Factory to create a :class:`S0GateError` with consistent formatting."""

    return S0GateError(code=_translate(code), detail=detail)


__all__ = ["S0GateError", "err"]
