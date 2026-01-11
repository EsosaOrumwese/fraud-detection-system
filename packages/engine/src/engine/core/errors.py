"""Engine error types used across modules."""


class EngineError(RuntimeError):
    """Base error for engine failures."""


class ContractError(EngineError):
    """Raised when contract sources or lookups fail."""


class InputResolutionError(EngineError):
    """Raised when required inputs cannot be resolved."""


class HashingError(EngineError):
    """Raised when hashing inputs fails or detects races."""


class SchemaValidationError(InputResolutionError):
    """Raised when JSON Schema validation fails."""

    def __init__(self, message: str, errors: list[dict]) -> None:
        super().__init__(message)
        self.errors = errors


class EngineFailure(EngineError):
    """Raised for failures that require a deterministic failure record."""

    def __init__(
        self,
        failure_class: str,
        failure_code: str,
        state: str,
        module: str,
        detail: dict,
        dataset_id: str | None = None,
        merchant_id: str | None = None,
    ) -> None:
        message = f"{failure_class}:{failure_code} {state} {module}"
        super().__init__(message)
        self.failure_class = failure_class
        self.failure_code = failure_code
        self.state = state
        self.module = module
        self.detail = detail
        self.dataset_id = dataset_id
        self.merchant_id = merchant_id
