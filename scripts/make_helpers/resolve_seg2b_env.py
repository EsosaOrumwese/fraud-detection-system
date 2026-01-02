"""Resolve environment variables needed by the Makefile `segment2b` target."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path


class ContextError(RuntimeError):
    """Raised when required artefacts are missing or malformed."""


def _load_summary(path: Path) -> dict:
    if not path.is_file():
        raise ContextError(f"summary '{path}' not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ContextError(f"summary '{path}' is not valid JSON") from exc


def _extract_gate_state(summary: dict) -> dict:
    try:
        gate_state = summary["s0"]
    except KeyError as exc:
        raise ContextError("summary missing 's0' entry") from exc
    required = {"manifest_fingerprint", "parameter_hash"}
    missing = required.difference(gate_state)
    if missing:
        raise ContextError(f"summary missing keys: {sorted(missing)}")
    return gate_state


def _quote_env(key: str, value: str) -> str:
    return f"{key}={shlex.quote(str(value))}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Emit shell-safe environment variables for Segment 2B runs.",
    )
    parser.add_argument(
        "--seg1a-summary",
        required=True,
        type=Path,
        help="Path to runs/.../summaries/segment1a_result.json.",
    )
    parser.add_argument(
        "--seg2a-summary",
        required=True,
        type=Path,
        help="Path to runs/.../summaries/segment2a_result.json.",
    )
    parser.add_argument(
        "--run-root",
        required=True,
        type=Path,
        help="Root directory where governed artefacts are materialised.",
    )
    parser.add_argument(
        "--seed",
        required=True,
        type=str,
        help="Seed used for the layer-1 run (string to preserve formatting).",
    )
    return parser


def _resolve_context(*, run_root: Path, seed: str, seg1a_path: Path, seg2a_path: Path) -> dict:
    seg1a_summary = _extract_gate_state(_load_summary(seg1a_path))
    seg2a_summary = _extract_gate_state(_load_summary(seg2a_path))

    param_hash = str(seg2a_summary["parameter_hash"])
    manifest_fingerprint = str(seg1a_summary["manifest_fingerprint"])
    seg2a_manifest = str(seg2a_summary["manifest_fingerprint"])

    site_locations = (
        run_root
        / "data"
        / "layer1"
        / "1B"
        / "site_locations"
        / f"seed={seed}"
        / f"fingerprint={manifest_fingerprint}"
    )
    if not site_locations.is_dir():
        raise ContextError(
            f"Segment 1B site_locations partition '{site_locations}' is missing",
        )

    validation_bundle = (
        run_root
        / "data"
        / "layer1"
        / "1B"
        / "validation"
        / f"fingerprint={manifest_fingerprint}"
    )
    if not validation_bundle.is_dir():
        raise ContextError(
            f"Segment 1B validation bundle '{validation_bundle}' is missing",
        )

    return {
        "MANIFEST_FINGERPRINT": manifest_fingerprint,
        "PARAM_HASH": param_hash,
        "SEG2A_MANIFEST_FINGERPRINT": seg2a_manifest,
        "VALIDATION_BUNDLE": validation_bundle.resolve(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    run_root = args.run_root.resolve()
    try:
        context = _resolve_context(
            run_root=run_root,
            seed=str(args.seed),
            seg1a_path=args.seg1a_summary.resolve(),
            seg2a_path=args.seg2a_summary.resolve(),
        )
    except ContextError as exc:
        parser.error(str(exc))

    lines = [_quote_env(key, str(value)) for key, value in context.items()]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
