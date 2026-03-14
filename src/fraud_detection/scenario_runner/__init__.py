"""Scenario Runner package.

Keep package exports lazy so importing submodules such as ``storage`` does not
eagerly drag full runner/schema dependencies into unrelated runtime lanes.
"""

from __future__ import annotations

from importlib import import_module


__all__ = ["ScenarioRunner", "RunRequest", "RunResponse", "ReemitRequest", "ReemitResponse"]


def __getattr__(name: str):
    if name == "ScenarioRunner":
        module = import_module(".runner", __name__)
        return getattr(module, name)
    if name in {"RunRequest", "RunResponse", "ReemitRequest", "ReemitResponse"}:
        module = import_module(".models", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
