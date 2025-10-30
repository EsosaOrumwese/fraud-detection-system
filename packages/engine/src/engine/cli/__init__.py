"""Command-line helpers for the engine package.

The CLI namespace is intentionally tiny; it only exposes the primitives we
expect automation to call.  ``run_s0_foundations`` and ``run_s1_hurdle`` are the
first entry points, and the module is structured so future layers can add their
own wrappers without inflating the public API.
"""

from .s0_foundations import main as run_s0_foundations
from .s1_hurdle import main as run_s1_hurdle
from .s2_tile_weights import main as run_s2_tile_weights
from .s2_nb_outlets import main as run_s2_nb_outlets
from .segment1b import main as run_segment1b
from .segment1a import main as run_segment1a

__all__ = ['run_s0_foundations', 'run_s1_hurdle', 'run_s2_nb_outlets', 'run_s2_tile_weights', 'run_segment1a', 'run_segment1b']