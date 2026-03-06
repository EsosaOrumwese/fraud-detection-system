#!/usr/bin/env python3
"""Build a remote-deployable Lambda bundle for the dev_full ingress edge."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


INCLUDE_PATHS = [
    "src/fraud_detection",
    "config/platform",
    "docs/model_spec/platform/contracts",
    "docs/model_spec/data-engine/interface_pack",
    "docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml",
    "docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml",
]


def copy_path(repo_root: Path, stage_root: Path, rel_path: str) -> None:
    source = (repo_root / rel_path).resolve()
    if not source.exists():
        raise SystemExit(f"Missing bundle path: {rel_path}")
    target = (stage_root / rel_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)


def build_zip(source_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            rel = file_path.relative_to(source_dir).as_posix()
            info = ZipInfo(rel)
            info.date_time = (2026, 3, 6, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, file_path.read_bytes())


def main() -> None:
    ap = argparse.ArgumentParser(description="Build IG Lambda bundle")
    ap.add_argument("--output", required=True, help="Target zip path")
    ap.add_argument("--repo-root", default=".", help="Repository root")
    ap.add_argument(
        "--requirements",
        default="requirements/ig-lambda.requirements.txt",
        help="Pinned requirements file",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    requirements_path = (repo_root / args.requirements).resolve()
    if not requirements_path.exists():
        raise SystemExit(f"Missing requirements file: {requirements_path}")

    with tempfile.TemporaryDirectory(prefix="ig-lambda-bundle-") as temp_dir:
        stage_root = Path(temp_dir) / "stage"
        stage_root.mkdir(parents=True, exist_ok=True)

        for rel in INCLUDE_PATHS:
            copy_path(repo_root, stage_root, rel)

        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--target",
                str(stage_root),
                "-r",
                str(requirements_path),
            ]
        )

        for junk in stage_root.rglob("__pycache__"):
            shutil.rmtree(junk, ignore_errors=True)
        for junk in stage_root.rglob("*.pyc"):
            junk.unlink(missing_ok=True)

        build_zip(stage_root, Path(args.output).resolve())


if __name__ == "__main__":
    main()
