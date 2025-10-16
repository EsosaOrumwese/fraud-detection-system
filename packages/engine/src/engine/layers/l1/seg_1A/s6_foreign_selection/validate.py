"""Validation helpers for S6 foreign-set selection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

__all__ = ["S6ValidationError", "validate_outputs"]


class S6ValidationError(RuntimeError):
    """Raised when S6 validation receipts fail integrity checks."""


def validate_outputs(*, receipt_path: str | Path) -> dict:
    """Validate the S6 PASS receipt and return the parsed payload."""

    receipt_file = Path(receipt_path).expanduser().resolve()
    if receipt_file.is_dir():
        receipt_file = receipt_file / "S6_VALIDATION.json"
    if not receipt_file.exists():
        raise S6ValidationError(f"receipt not found at {receipt_file}")

    payload_text = receipt_file.read_text(encoding="utf-8")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise S6ValidationError(f"receipt JSON malformed: {exc}") from exc

    flag_path = receipt_file.with_name("_passed.flag")
    if not flag_path.exists():
        raise S6ValidationError(f"_passed.flag missing alongside {receipt_file}")

    expected_digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    flag_text = flag_path.read_text(encoding="ascii").strip()
    prefix = "sha256_hex="
    if not flag_text.startswith(prefix):
        raise S6ValidationError(f"_passed.flag contents malformed at {flag_path}")
    observed_digest = flag_text[len(prefix) :].strip()
    if observed_digest != expected_digest:
        raise S6ValidationError(
            "_passed.flag digest does not match S6_VALIDATION.json contents"
        )

    return payload
