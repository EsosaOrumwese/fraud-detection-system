"""Command-line helpers for the engine package.

The CLI namespace is intentionally tiny; it only exposes the primitives we
expect automation to call.  ``run_s0_foundations`` and ``run_s1_hurdle`` are the
first entry points, and the module is structured so future layers can add their
own wrappers without inflating the public API.
"""

from .s0_foundations import main as run_s0_foundations
from .s1_hurdle import main as run_s1_hurdle

__all__ = ["run_s0_foundations", "run_s1_hurdle"]
