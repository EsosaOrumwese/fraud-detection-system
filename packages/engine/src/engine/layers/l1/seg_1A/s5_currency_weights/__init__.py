"""Layer 1 / Segment 1A State 5 currency→country weights package."""

from .builder import CurrencyResult, WeightRow, build_weights
from .contexts import MerchantCurrencyInput, S5DeterministicContext, S5PolicyMetadata
from .loader import (
    ShareSurface,
    LegalTender,
    ShareDataPaths,
    load_settlement_shares,
    load_ccy_country_shares,
    load_iso_legal_tender,
    DEFAULT_PATHS,
)
from .policy import (
    load_policy,
    PolicyValidationError,
    SmoothingPolicy,
)
from .merchant_currency import MerchantCurrencyRecord, derive_merchant_currency
from .persist import (
    PersistConfig,
    write_ccy_country_weights,
    write_sparse_flag,
    write_validation_receipt,
    write_merchant_currency,
)
from .runner import S5CurrencyWeightsRunner, S5RunOutputs
from .validate import (
    ValidationError,
    validate_weights_df,
)

__all__ = [
    "CurrencyResult",
    "WeightRow",
    "build_weights",
    "MerchantCurrencyInput",
    "S5DeterministicContext",
    "S5PolicyMetadata",
    "ShareSurface",
    "LegalTender",
    "ShareDataPaths",
    "load_settlement_shares",
    "load_ccy_country_shares",
    "load_iso_legal_tender",
    "DEFAULT_PATHS",
    "load_policy",
    "PolicyValidationError",
    "SmoothingPolicy",
    "PersistConfig",
    "write_ccy_country_weights",
    "write_sparse_flag",
    "write_validation_receipt",
    "write_merchant_currency",
    "MerchantCurrencyRecord",
    "derive_merchant_currency",
    "S5CurrencyWeightsRunner",
    "S5RunOutputs",
    "ValidationError",
    "validate_weights_df",
]
