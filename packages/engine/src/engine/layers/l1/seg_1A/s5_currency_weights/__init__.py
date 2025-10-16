"""Layer 1 / Segment 1A State 5 currency→country weights package."""

from .builder import CurrencyResult, WeightRow, build_weights
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
from .persist import (
    PersistConfig,
    write_ccy_country_weights,
    write_sparse_flag,
    write_validation_receipt,
)
from .validate import (
    ValidationError,
    validate_weights_df,
)
