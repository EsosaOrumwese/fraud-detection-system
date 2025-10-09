"""Public surface for Layer-1 Segment 1A state-2 NB outlet preparation."""

from .l1.links import NBLinks, compute_links_from_design, compute_nb_links

__all__ = ["NBLinks", "compute_nb_links", "compute_links_from_design"]
