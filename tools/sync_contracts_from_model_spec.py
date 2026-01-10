#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


SOURCE_PATTERNS = ("layer-*/specs/contracts/**/*.yaml",)

DATASET_RE = re.compile(r"^dataset_dictionary\.layer(?P<layer>\d)\.(?P<segment>[A-Za-z0-9]+)\.yaml$")
SCHEMA_LAYER_RE = re.compile(r"^schemas\.(ingress\.)?layer(?P<layer>\d)\.yaml$")
SCHEMA_SEGMENT_RE = re.compile(r"^schemas\.(?P<segment>[A-Za-z0-9]+)\.yaml$")
REGISTRY_RE = re.compile(r"^artefact_registry_(?P<segment>[A-Za-z0-9]+)\.yaml$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_layer_id(path: Path) -> str:
    for part in path.parts:
        if part.startswith("layer-"):
            return part.split("-", 1)[1]
    raise ValueError(f"unable to infer layer id from {path}")


def map_contract_path(src: Path, *, source_root: Path, dest_root: Path) -> Path:
    rel = src.relative_to(source_root)
    layer_id = discover_layer_id(rel)
    name = src.name

    match = DATASET_RE.match(name)
    if match:
        file_layer = match.group("layer")
        if file_layer != layer_id:
            raise ValueError(f"layer id mismatch for {rel}: {file_layer} vs {layer_id}")
        segment = match.group("segment")
        return (
            dest_root
            / "dataset_dictionary"
            / f"l{layer_id}"
            / f"seg_{segment}"
            / f"layer{layer_id}.{segment}.yaml"
        )

    match = SCHEMA_LAYER_RE.match(name)
    if match:
        file_layer = match.group("layer")
        if file_layer != layer_id:
            raise ValueError(f"layer id mismatch for {rel}: {file_layer} vs {layer_id}")
        return dest_root / "schemas" / f"layer{layer_id}" / name

    match = SCHEMA_SEGMENT_RE.match(name)
    if match:
        return dest_root / "schemas" / f"layer{layer_id}" / name

    match = REGISTRY_RE.match(name)
    if match:
        return dest_root / "artefact_registry" / name

    raise ValueError(f"unmapped contract file: {rel}")


def sync_contracts(
    *,
    source_root: Path,
    dest_root: Path,
    manifest_path: Path,
    force: bool,
    dry_run: bool,
) -> None:
    source_root = source_root.resolve()
    dest_root = dest_root.resolve()
    manifest_path = manifest_path.resolve()

    if not source_root.exists():
        raise SystemExit(f"source root does not exist: {source_root}")

    entries: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    files: list[Path] = []
    for pattern in SOURCE_PATTERNS:
        files.extend(sorted(source_root.glob(pattern)))
    files = [path for path in files if path.is_file()]
    files.sort(key=lambda path: path.as_posix())

    for src in files:
        rel = src.relative_to(source_root)
        try:
            dest = map_contract_path(src, source_root=source_root, dest_root=dest_root)
        except ValueError as exc:
            failures.append({"source": rel.as_posix(), "error": str(exc)})
            continue

        if not dest.exists() or force:
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

        entries.append(
            {
                "source": rel.as_posix(),
                "destination": dest.relative_to(dest_root).as_posix(),
                "sha256": sha256_file(src),
                "size_bytes": src.stat().st_size,
            }
        )

    if not dry_run:
        manifest = {
            "source_root": source_root.as_posix(),
            "dest_root": dest_root.as_posix(),
            "file_count": len(entries),
            "files": entries,
            "unmapped": failures,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Sync root contracts/ from model_spec layer contracts."
    )
    parser.add_argument(
        "--source-root",
        default="docs/model_spec/data-engine",
        help="Source root containing layer-*/specs/contracts.",
    )
    parser.add_argument(
        "--dest-root",
        default="contracts",
        help="Destination root for generated contracts.",
    )
    parser.add_argument(
        "--manifest-path",
        default="contracts/_mirror_manifest.json",
        help="Manifest output path for generated files.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files.")
    args = parser.parse_args()

    sync_contracts(
        source_root=repo_root / args.source_root,
        dest_root=repo_root / args.dest_root,
        manifest_path=repo_root / args.manifest_path,
        force=args.force,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
