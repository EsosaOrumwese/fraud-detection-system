"""
Prune run-id folders under a runs root, keeping an explicit allowlist.

Why this exists:
- The engine remediation workflow can create many run-id folders (each with large parquet outputs).
- Storage is limited, so we need a deterministic way to delete superseded run-id folders while
  preserving the few authorities we still need.

Safety posture:
- Dry-run by default. Requires --yes to actually delete.
- Only deletes direct children of runs_root whose folder name matches 32 hex chars.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _iter_run_id_dirs(runs_root: Path) -> list[Path]:
    if not runs_root.exists():
        return []
    out: list[Path] = []
    for child in runs_root.iterdir():
        if not child.is_dir():
            continue
        if RUN_ID_RE.match(child.name):
            out.append(child)
    return sorted(out, key=lambda p: p.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", required=True, help="e.g. runs/fix-data-engine/segment_1B")
    ap.add_argument(
        "--keep",
        required=True,
        action="append",
        help="Run-id to keep (can be repeated).",
    )
    ap.add_argument("--yes", action="store_true", help="Actually delete. Default is dry-run.")
    args = ap.parse_args()

    runs_root = Path(args.runs_root)
    keep = {str(k).strip() for k in (args.keep or []) if str(k).strip()}

    candidates = [p for p in _iter_run_id_dirs(runs_root) if p.name not in keep]
    print(f"[prune-keep-set] runs_root={runs_root}")
    print(f"[prune-keep-set] keep_count={len(keep)} keep={sorted(keep)}")
    print(f"[prune-keep-set] candidate_count={len(candidates)}")

    for p in candidates:
        if args.yes:
            try:
                shutil.rmtree(p)
                print(f"[prune-keep-set] removed: {p}")
            except Exception as exc:  # pragma: no cover
                print(f"[prune-keep-set] warning: failed to remove {p}: {exc}")
        else:
            print(f"[prune-keep-set] would_remove: {p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

