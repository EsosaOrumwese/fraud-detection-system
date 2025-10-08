"""Command-line helpers for the engine package.

The CLI namespace is intentionally tiny; it only exposes the primitives we
expect automation to call.  ``run_s0_foundations`` is the first such entry
point, but the module is structured so future layers can add their own wrappers
without inflating the public API.
"""

from .s0_foundations import main as run_s0_foundations

__all__ = ["run_s0_foundations"]
