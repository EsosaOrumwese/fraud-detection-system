"""IG error taxonomy and helpers."""

from __future__ import annotations


class IngestionError(RuntimeError):
    """Stable, policy-safe error surfaced as a reason code."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        message = f"{code}:{detail}" if detail else code
        super().__init__(message)


def reason_code(exc: Exception) -> str:
    if isinstance(exc, IngestionError):
        return exc.code
    text = str(exc or "").strip()
    if text.isupper():
        return text
    if ":" in text:
        head = text.split(":", 1)[0].strip()
        if head.isupper():
            return head
    return "INTERNAL_ERROR"
