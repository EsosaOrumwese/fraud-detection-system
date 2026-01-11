"""Engine error types used across modules."""


class EngineError(RuntimeError):
    """Base error for engine failures."""


class ContractError(EngineError):
    """Raised when contract sources or lookups fail."""


class InputResolutionError(EngineError):
    """Raised when required inputs cannot be resolved."""


class HashingError(EngineError):
    """Raised when hashing inputs fails or detects races."""
