#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


CONTRACT_PATTERNS = (
    "layer-*/specs/contracts/**/*",
    "interface_pack/**/*",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_pack(source_root: Path, dest_root: Path, tag: str, force: bool) -> None:
    dest_dir = dest_root / tag
    manifest_path = dest_root / f"{tag}.manifest.json"

    if dest_dir.exists():
        if not force:
            raise SystemExit(f"Destination exists: {dest_dir} (use --force to overwrite)")
        shutil.rmtree(dest_dir)
    if manifest_path.exists() and force:
        manifest_path.unlink()

    files: list[Path] = []
    for pattern in CONTRACT_PATTERNS:
        files.extend(sorted(source_root.glob(pattern)))

    files = [path for path in files if path.is_file()]
    files.sort(key=lambda path: path.as_posix())

    entries = []
    total_bytes = 0
    for src in files:
        rel = src.relative_to(source_root)
        dest = dest_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        size_bytes = src.stat().st_size
        total_bytes += size_bytes
        entries.append(
            {
                "source": rel.as_posix(),
                "sha256": sha256_file(src),
                "size_bytes": size_bytes,
            }
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "tag": tag,
        "source_root": source_root.as_posix(),
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "files": entries,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dest_root / "LATEST").write_text(f"{tag}\n", encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build consolidated contracts pack from docs/model_spec.")
    parser.add_argument("--tag", default="latest", help="Pack tag under contracts/model_spec/<tag>.")
    parser.add_argument(
        "--source-root",
        default="docs/model_spec/data-engine",
        help="Source root containing specs/contracts and interface_pack.",
    )
    parser.add_argument(
        "--dest-root",
        default="contracts/model_spec",
        help="Destination root for generated packs.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing pack output.")
    args = parser.parse_args()

    source_root = (repo_root / args.source_root).resolve()
    dest_root = (repo_root / args.dest_root).resolve()

    if not source_root.exists():
        raise SystemExit(f"Source root does not exist: {source_root}")

    dest_root.mkdir(parents=True, exist_ok=True)
    build_pack(source_root, dest_root, args.tag, args.force)


if __name__ == "__main__":
    main()
