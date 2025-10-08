"""Build the population_raster_2025 dataset from a supplied GeoTIFF."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.shutil import copy as rio_copy


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_BASE = ROOT / "reference" / "spatial" / "population_raster"


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_stats(dataset: rasterio.DatasetReader) -> dict[str, float]:
    nodata = dataset.nodata
    data_sum = 0.0
    data_min = float("inf")
    data_max = float("-inf")
    count = 0
    nodata_count = 0

    for ji, window in dataset.block_windows(1):
        arr = dataset.read(1, window=window, masked=False)
        mask = np.full(arr.shape, False, dtype=bool)
        if nodata is not None:
            mask = arr == nodata
        valid = np.ma.array(arr, mask=mask)
        nodata_count += int(mask.sum())
        count += arr.size - mask.sum()
        if valid.count() > 0:
            data_sum += float(valid.sum())
            data_min = float(min(data_min, valid.min()))
            data_max = float(max(data_max, valid.max()))

    return {
        "sum": data_sum,
        "min": data_min if data_min != float("inf") else None,
        "max": data_max if data_max != float("-inf") else None,
        "valid_count": count,
        "nodata_count": nodata_count,
        "nodata": nodata,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2025")
    parser.add_argument("--input-tif", required=True, type=Path, help="Source GeoTIFF (population counts)")
    parser.add_argument("--output-name", default="population_raster_2025.tif")
    args = parser.parse_args()

    src_path = args.input_tif.resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"Input raster not found: {src_path}")

    output_dir = REFERENCE_BASE / args.version
    output_dir.mkdir(parents=True, exist_ok=True)

    output_tif = output_dir / args.output_name
    cog_profile = {
        "driver": "COG",
        "compress": "deflate",
        "blocksize": 512,
        "overview_resampling": "average",
    }
    rio_copy(src_path, output_tif, **cog_profile)

    with rasterio.open(output_tif) as dst:
        stats = compute_stats(dst)
        profile = dst.profile

    qa_path = output_dir / "population_raster_2025.qa.json"
    qa_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "width": profile["width"],
        "height": profile["height"],
        "crs": profile["crs"].to_string() if profile.get("crs") else None,
        "transform": list(profile["transform"]),
        "stats": stats,
    }
    qa_path.write_text(json.dumps(qa_payload, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "dataset_id": "population_raster_2025",
        "version": args.version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/build_population_raster.py",
        "source_tif": str(src_path.relative_to(ROOT)),
        "source_tif_sha256": sha256sum(src_path),
        "output_tif": str(output_tif.relative_to(ROOT)),
        "output_tif_sha256": sha256sum(output_tif),
        "qa_path": str(qa_path.relative_to(ROOT)),
        "qa_sha256": sha256sum(qa_path),
        "width": profile["width"],
        "height": profile["height"],
        "crs": profile["crs"].to_string() if profile.get("crs") else None,
    }
    (output_dir / "population_raster_2025.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    sha_lines = [
        f"{manifest['source_tif_sha256']}  {manifest['source_tif']}",
        f"{manifest['output_tif_sha256']}  {manifest['output_tif']}",
        f"{manifest['qa_sha256']}  {manifest['qa_path']}",
    ]
    (output_dir / "SHA256SUMS").write_text("\n".join(sha_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
