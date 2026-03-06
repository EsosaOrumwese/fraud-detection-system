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


NATIVE_WHEEL_REQUIREMENTS = {"confluent-kafka"}
DEFAULT_DOCKER_IMAGE = "public.ecr.aws/lambda/python:3.12"

INCLUDE_PATHS = [
    ("src/fraud_detection", "fraud_detection"),
    ("config/platform", "config/platform"),
    ("docs/model_spec/platform/contracts", "docs/model_spec/platform/contracts"),
    ("docs/model_spec/data-engine/interface_pack", "docs/model_spec/data-engine/interface_pack"),
    ("docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml", "docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml"),
    ("docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml", "docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml"),
]


def copy_path(repo_root: Path, stage_root: Path, source_rel_path: str, target_rel_path: str) -> None:
    source = (repo_root / source_rel_path).resolve()
    if not source.exists():
        raise SystemExit(f"Missing bundle path: {source_rel_path}")
    target = (stage_root / target_rel_path).resolve()
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


def split_requirements(requirements_path: Path) -> tuple[list[str], list[str]]:
    generic: list[str] = []
    native: list[str] = []
    for raw in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        package_name = line.split("==", 1)[0].split(">=", 1)[0].split("[", 1)[0].strip().lower()
        if package_name in NATIVE_WHEEL_REQUIREMENTS:
            native.append(line)
        else:
            generic.append(line)
    return generic, native


def docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


def run_docker_build(*, repo_root: Path, output_path: Path, requirements_rel: str, image: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    repo_mount = repo_root.resolve()
    output_dir = output_path.parent.resolve()
    output_name = output_path.name
    subprocess.check_call(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{repo_mount.as_posix()}:/repo",
            "-v",
            f"{output_dir.as_posix()}:/out",
            "-w",
            "/repo",
            image,
            "python",
            "scripts/dev_substrate/build_ig_lambda_bundle.py",
            "--repo-root",
            "/repo",
            "--output",
            f"/out/{output_name}",
            "--requirements",
            requirements_rel,
            "--build-mode",
            "host",
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Build IG Lambda bundle")
    ap.add_argument("--output", required=True, help="Target zip path")
    ap.add_argument("--repo-root", default=".", help="Repository root")
    ap.add_argument(
        "--requirements",
        default="requirements/ig-lambda.requirements.txt",
        help="Pinned requirements file",
    )
    ap.add_argument("--build-mode", choices=["auto", "host", "docker"], default="auto", help="Bundle build execution mode")
    ap.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE, help="Container image used for Lambda-compatible builds")
    ap.add_argument("--target-platform", default="manylinux_2_28_x86_64", help="Wheel platform tag")
    ap.add_argument("--target-python-version", default="3.12", help="Target Python minor version")
    ap.add_argument("--target-abi", default="cp312", help="Target CPython ABI tag")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    requirements_path = (repo_root / args.requirements).resolve()
    if not requirements_path.exists():
        raise SystemExit(f"Missing requirements file: {requirements_path}")
    build_mode = str(args.build_mode).strip().lower()
    if build_mode == "auto":
        build_mode = "docker" if docker_available() else "host"
    if build_mode == "docker":
        run_docker_build(
            repo_root=repo_root,
            output_path=Path(args.output).resolve(),
            requirements_rel=args.requirements,
            image=str(args.docker_image),
        )
        return
    generic_requirements, native_requirements = split_requirements(requirements_path)

    with tempfile.TemporaryDirectory(prefix="ig-lambda-bundle-") as temp_dir:
        stage_root = Path(temp_dir) / "stage"
        stage_root.mkdir(parents=True, exist_ok=True)

        for source_rel, target_rel in INCLUDE_PATHS:
            copy_path(repo_root, stage_root, source_rel, target_rel)

        if generic_requirements:
            generic_requirements_path = Path(temp_dir) / "generic.requirements.txt"
            generic_requirements_path.write_text("\n".join(generic_requirements) + "\n", encoding="utf-8")
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "--target",
                    str(stage_root),
                    "--no-compile",
                    "-r",
                    str(generic_requirements_path),
                ]
            )

        for requirement in native_requirements:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "--only-binary=:all:",
                    "--platform",
                    str(args.target_platform),
                    "--implementation",
                    "cp",
                    "--python-version",
                    str(args.target_python_version),
                    "--abi",
                    str(args.target_abi),
                    "--target",
                    str(stage_root),
                    "--no-compile",
                    requirement,
                ]
            )

        for junk in stage_root.rglob("__pycache__"):
            shutil.rmtree(junk, ignore_errors=True)
        for junk in stage_root.rglob("*.pyc"):
            junk.unlink(missing_ok=True)

        build_zip(stage_root, Path(args.output).resolve())


if __name__ == "__main__":
    main()
