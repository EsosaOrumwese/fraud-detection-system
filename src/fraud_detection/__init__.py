"""
Top-level placeholder package for the fraud_detection project.

The actual engine code lives under `packages/engine/src/engine`. Installing the
project via Poetry exposes both this namespace package and the concrete
`engine` package so CLI entry points (engine.cli.*) remain importable.
"""

__all__: list[str] = []

