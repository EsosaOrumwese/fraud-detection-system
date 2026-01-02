"""Exception helpers for Segment 2B state-0 gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class S0GateError(Exception):
    """Structured error raised by the 2B gate."""

    code: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.detail}"


_LEGACY_TO_CANONICAL: dict[str, str] = {
    # ------------------------------------------------------------------ shared / S0
    "E_ASSET_DUPLICATE": "2B-S0-043",
    "E_ASSET_EMPTY": "2B-S0-010",
    "E_ASSET_EMPTY_DIGESTS": "2B-S0-041",
    "E_ASSET_ID_MISSING": "2B-S0-010",
    "E_ASSET_MISSING": "2B-S0-010",
    "E_ASSET_SCHEMA_MISSING": "2B-S0-031",
    "E_DICTIONARY_RESOLUTION_FAILED": "2B-S0-020",
    "E_FLAG_FORMAT_INVALID": "2B-S0-013",
    "E_INDEX_INVALID": "2B-S0-012",
    "E_INDEX_IO": "2B-S0-012",
    "E_INDEX_MISSING": "2B-S0-010",
    "E_INVENTORY_SCHEMA_INVALID": "2B-S0-031",
    "E_PASS_MISSING": "2B-S0-010",
    "E_PATH_ESCAPE": "2B-S0-021",
    "E_RECEIPT_SCHEMA_INVALID": "2B-S0-030",
    "E_S0_RECEIPT_INVALID": "2B-S0-030",
    "E_S0_RECEIPT_MISMATCH": "2B-S0-040",
    "E_S0_RECEIPT_MISSING": "2B-S0-001",
    "E_SCHEMA_RESOLUTION_FAILED": "2B-S0-020",
    "E_SEALED_INPUTS_INVALID": "2B-S0-031",
    "E_SEALED_INPUTS_MISSING": "2B-S0-010",
    # ------------------------------------------------------------------ S1 weights
    "E_S1_CAP_MODE": "2B-S1-031",
    "E_S1_CAP_VALUE": "2B-S1-032",
    "E_S1_CLAMP_ZERO": "2B-S1-052",
    "E_S1_FALLBACK_UNSUPPORTED": "2B-S1-053",
    "E_S1_FLOOR_MODE": "2B-S1-031",
    "E_S1_MANIFEST_FINGERPRINT": "2B-S1-071",
    "E_S1_MASS_EPSILON": "2B-S1-051",
    "E_S1_NO_ROWS": "2B-S1-042",
    "E_S1_OUTPUT_EXISTS": "2B-S1-080",
    "E_S1_POLICY_WEIGHT_COLUMN": "2B-S1-033",
    "E_S1_QUANT_EPSILON": "2B-S1-052",
    "E_S1_QUANT_SUM": "2B-S1-051",
    "E_S1_SCHEMA_COLUMNS": "2B-S1-040",
    "E_S1_SCHEMA_TYPES": "2B-S1-040",
    "E_S1_SEED_EMPTY": "2B-S1-070",
    "E_S1_SITE_LOCATIONS_COLUMN": "2B-S1-020",
    "E_S1_SITE_LOCATIONS_IO": "2B-S1-020",
    "E_S1_WEIGHT_DOMAIN": "2B-S1-050",
    # ------------------------------------------------------------------ S2 alias index
    "E_S2_EMPTY_MERCHANT": "2B-S2-050",
    "E_S2_INDEX_SCHEMA": "2B-S2-040",
    "E_S2_MANIFEST_FINGERPRINT": "2B-S2-071",
    "E_S2_NO_ROWS": "2B-S2-050",
    "E_S2_OUTPUT_EXISTS": "2B-S2-080",
    "E_S2_QUANT_BITS_MISMATCH": "2B-S2-058",
    "E_S2_SEED_EMPTY": "2B-S2-070",
    "E_S2_SITE_WEIGHTS_IO": "2B-S2-020",
    # ------------------------------------------------------------------ S5 router
    "E_S5_ALIAS_ARTEFACTS_MISSING": "2B-S5-041",
    "E_S5_ALIAS_DIGEST_MISMATCH": "2B-S5-046",
    "E_S5_ALIAS_EMPTY": "2B-S5-041",
    "E_S5_ALIAS_INDEX_INVALID": "2B-S5-041",
    "E_S5_ALIAS_POLICY_MISMATCH": "2B-S5-041",
    "E_S5_ALIAS_TOTAL": "2B-S5-040",
    "E_S5_GROUP_MISSING": "2B-S5-040",
    "E_S5_HEX_FIELD": "2B-S5-051",
    "E_S5_IMMUTABLE_LOG": "2B-S5-080",
    "E_S5_NO_ARRIVALS": "2B-S5-050",
    "E_S5_PARTITION_MISSING": "2B-S5-070",
    "E_S5_POLICY_STREAM": "2B-S5-053",
    "E_S5_RNG_BUDGET": "2B-S5-050",
    "E_S5_RUN_ID": "2B-S5-071",
    "E_S5_SEED_EMPTY": "2B-S5-070",
    "E_S5_SELECTION_LOG_IMMUTABLE": "2B-S5-080",
    "E_S5_SITE_LOOKUP_EMPTY": "2B-S5-041",
    "E_S5_SITE_MISSING": "2B-S5-060",
    "E_S5_TRACE_INVALID": "2B-S5-056",
    "E_S5_TZ_INCOHERENT": "2B-S5-041",
    # ------------------------------------------------------------------ S6 virtual edge
    "E_S6_ALIAS_EMPTY": "2B-S6-041",
    "E_S6_ALIAS_TOTAL": "2B-S6-041",
    "E_S6_ARRIVALS_MISSING": "2B-S6-060",
    "E_S6_EDGE_LOG_IMMUTABLE": "2B-S6-080",
    "E_S6_HEX_FIELD": "2B-S6-051",
    "E_S6_IMMUTABLE_LOG": "2B-S6-080",
    "E_S6_POLICY_MINIMA": "2B-S6-031",
    "E_S6_POLICY_STREAM": "2B-S6-053",
    "E_S6_RNG_BUDGET": "2B-S6-050",
    "E_S6_RUN_ID": "2B-S6-071",
    "E_S6_SEED_EMPTY": "2B-S6-070",
    "E_VIRTUAL_MCC_MAP": "2B-S6-060",
    "E_VIRTUAL_MCC_MAP_EMPTY": "2B-S6-060",
    "E_VIRTUAL_MCC_MAP_IO": "2B-S6-020",
    "E_VIRTUAL_MCC_MAP_SCHEMA": "2B-S6-030",
    "E_VIRTUAL_MCC_MAP_TYPE": "2B-S6-030",
    "E_VIRTUAL_RULES_MCC": "2B-S6-031",
    "E_VIRTUAL_RULES_VERSION": "2B-S6-031",
    # ------------------------------------------------------------------ S7 audit
    "E_S7_ALIAS_ALIAS_ORDER": "2B-S7-206",
    "E_S7_ALIAS_ALIGNMENT": "2B-S7-204",
    "E_S7_ALIAS_BLOB_MISSING": "2B-S7-200",
    "E_S7_ALIAS_BOUNDS": "2B-S7-203",
    "E_S7_ALIAS_DIGEST": "2B-S7-202",
    "E_S7_ALIAS_ORDER": "2B-S7-303",
    "E_S7_ALIAS_OVERLAP": "2B-S7-203",
    "E_S7_ALIAS_REFERENCE": "2B-S7-303",
    "E_S7_ALIAS_SCHEMA": "2B-S7-200",
    "E_S7_ALIAS_SLICE": "2B-S7-206",
    "E_S7_DAY_GRID": "2B-S7-300",
    "E_S7_EDGE_ATTR": "2B-S7-411",
    "E_S7_GAMMA_ECHO": "2B-S7-301",
    "E_S7_JSON_MISSING": "2B-S7-500",
    "E_S7_MANIFEST_FINGERPRINT": "2B-S7-503",
    "E_S7_PARAMETER_HASH": "2B-S7-070",
    "E_S7_POLICY_ROUTE": "2B-S7-020",
    "E_S7_POLICY_STREAM": "2B-S7-405",
    "E_S7_POLICY_VIRTUAL": "2B-S7-020",
    "E_S7_REPORT_IMMUTABLE": "2B-S7-501",
    "E_S7_RNG_COUNTER": "2B-S7-403",
    "E_S7_RNG_EVENT": "2B-S7-402",
    "E_S7_RNG_EVENTS": "2B-S7-402",
    "E_S7_RNG_PATH": "2B-S7-503",
    "E_S7_ROUTER_PARAMETER_HASH": "2B-S7-070",
    "E_S7_ROUTER_RUN_ID": "2B-S7-070",
    "E_S7_ROUTER_TZ_LOOKUP": "2B-S7-303",
    "E_S7_ROUTER_TZ_MISMATCH": "2B-S7-303",
    "E_S7_S1_MISSING": "2B-S7-001",
    "E_S7_S3_MISSING": "2B-S7-300",
    "E_S7_S4_MISSING": "2B-S7-300",
    "E_S7_SEED_EMPTY": "2B-S7-070",
    "E_S7_SEG2A_FINGERPRINT": "2B-S7-503",
    "E_S7_SITE_TIMEZONE": "2B-S7-411",
    "E_S7_TRACE_MANIFEST": "2B-S7-400",
    "E_S7_TRACE_MISSING": "2B-S7-400",
    "E_S7_TRACE_ORDER": "2B-S7-401",
    "E_S7_TRACE_PARTITION": "2B-S7-503",
    "E_S7_TRACE_STREAM": "2B-S7-405",
    "E_S7_TRACE_TOTAL": "2B-S7-402",
    # ------------------------------------------------------------------ S8 validation
    "E_S8_ASSET_MISSING": "2B-S8-030",
    "E_S8_FLAG_SCHEMA": "2B-S8-052",
    "E_S8_IMMUTABLE_OVERWRITE": "2B-S8-080",
    "E_S8_INDEX_SCHEMA": "2B-S8-040",
    "E_S8_INVALID_HEX": "2B-S8-051",
    "E_S8_POLICY_DIGEST": "2B-S8-033",
    "E_S8_POLICY_MISSING": "2B-S8-033",
    "E_S8_POLICY_PATH": "2B-S8-020",
    "E_S8_S7_REPORT_INVALID": "2B-S8-031",
    "E_S8_S7_REPORT_MISSING": "2B-S8-032",
    "E_S8_S7_REPORT_NOT_PASS": "2B-S8-031",
    "E_S8_SEED_DISCOVERY": "2B-S8-030",
    "E_S8_SEED_INTERSECTION_EMPTY": "2B-S8-030",
}


def _translate(code: str) -> str:
    if code.startswith("2B-"):
        return code
    return _LEGACY_TO_CANONICAL.get(code, code)


def err(code: str, detail: str) -> S0GateError:
    """Factory to create a :class:`S0GateError` with consistent formatting."""

    return S0GateError(code=_translate(code), detail=detail)


__all__ = ["S0GateError", "err"]

