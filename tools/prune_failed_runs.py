#!/usr/bin/env python3
"""Prune failed run-id folders under a runs root.

A run is considered failed when a `_FAILED.SENTINEL.json` marker exists
somewhere under its directory tree.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _find_run_root(marker: Path, runs_root: Path) -> Path | None:
    for parent in marker.parents:
        if parent == runs_root:
            break
        if RUN_ID_RE.fullmatch(parent.name):
            # Safety: only delete immediate run-id children of runs_root.
            if parent.parent == runs_root:
                return parent
            return None
    return None


def _dir_size_bytes(root: Path) -> int:
    total = 0
    for file_path in root.rglob("*"):
        if file_path.is_file():
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        required=True,
        help="Root directory containing run-id folders.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    runs_root = Path(args.runs_root).resolve()

    if not runs_root.exists():
        print(f"[prune-failed-runs] runs_root not found, skipping: {runs_root}")
        return 0

    sentinels = list(runs_root.rglob("_FAILED.SENTINEL.json"))
    if not sentinels:
        print(f"[prune-failed-runs] no failed sentinels found under: {runs_root}")
        return 0

    run_roots: set[Path] = set()
    for marker in sentinels:
        run_root = _find_run_root(marker, runs_root)
        if run_root is not None:
            run_roots.add(run_root)

    if not run_roots:
        print(
            "[prune-failed-runs] sentinels found but no safe run-id roots resolved; "
            "skipping deletion."
        )
        return 0

    reclaimed_bytes = 0
    removed = 0
    errors = 0
    for run_root in sorted(run_roots):
        run_size = _dir_size_bytes(run_root)
        try:
            shutil.rmtree(run_root)
            reclaimed_bytes += run_size
            removed += 1
            print(f"[prune-failed-runs] removed: {run_root}")
        except OSError as exc:
            errors += 1
            print(
                f"[prune-failed-runs] warning: failed to remove {run_root}: {exc}",
                file=sys.stderr,
            )

    reclaimed_mb = reclaimed_bytes / (1024 * 1024)
    print(
        "[prune-failed-runs] summary: "
        f"removed={removed} errors={errors} reclaimed_mb={reclaimed_mb:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
