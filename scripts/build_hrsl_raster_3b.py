"""Acquire and build the 3B HRSL 100m-class raster (3 arcseconds)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
import requests


ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "artefacts/rasters/hrsl_100m.tif"
PROV_PATH = ROOT / "artefacts/rasters/hrsl_100m.provenance.json"
VRT_URL = (
    "https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/"
    "hrsl_general/hrsl_general-latest.vrt"
)
TR_DEG = 3.0 / 3600.0
LOCAL_ROOT = ROOT / "artefacts/rasters/source/hrsl_general"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:  # noqa: PTH123
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, path: Path) -> None:
    response = requests.get(url, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} for {url}")
    path.write_bytes(response.content)


def download_vrt(vrt_path: Path, vrt_url: str) -> None:
    aws_cli = shutil.which("aws")
    if aws_cli:
        s3_path = "s3://dataforgood-fb-data/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt"
        result = subprocess.run(
            [aws_cli, "s3", "cp", "--no-sign-request", s3_path, str(vrt_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"AWS CLI download failed: {result.stderr.strip() or result.stdout.strip()}"
            )
        return

    download_file(vrt_url, vrt_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vintage", required=True)
    parser.add_argument("--semver", required=True)
    parser.add_argument("--vrt-url", default=VRT_URL)
    parser.add_argument("--local-root", default=str(LOCAL_ROOT))
    parser.add_argument("--log-every", type=int, default=200)
    parser.add_argument("--log-seconds", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "YES")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.vrt")
    os.environ.setdefault("GDAL_NUM_THREADS", "ALL_CPUS")
    proj_db = None
    rasterio_root = Path(rasterio.__file__).resolve().parent
    candidate = rasterio_root / "proj_data" / "proj.db"
    if candidate.exists():
        proj_db = candidate
    if proj_db is not None:
        os.environ["PROJ_LIB"] = str(proj_db.parent)
        os.environ["PROJ_DATA"] = str(proj_db.parent)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROV_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_out_path = OUT_PATH.with_suffix(".tmp.tif")
    if temp_out_path.exists():
        temp_out_path.unlink()

    local_root = Path(args.local_root)
    if local_root.exists():
        local_vrt = local_root / "hrsl_general-latest.vrt"
        if not local_vrt.exists():
            raise RuntimeError(
                f"Local root missing hrsl_general-latest.vrt: {local_root}"
            )
        vrt_path = local_vrt
        vrt_sha256 = sha256_path(vrt_path)
        vrt_bytes = vrt_path.stat().st_size
    else:
        local_root = None
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            vrt_path = tmp_path / "hrsl_general.vrt"
            download_vrt(vrt_path, args.vrt_url)
            vrt_sha256 = sha256_path(vrt_path)
            vrt_bytes = vrt_path.stat().st_size
            vrt_text = vrt_path.read_text(encoding="utf-8")
            base_url = "https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/hrsl_general/"
            vrt_text = vrt_text.replace(
                'relativeToVRT="1">', f'relativeToVRT="0">/vsicurl/{base_url}'
            )
            vrt_path.write_text(vrt_text, encoding="utf-8")

    with rasterio.open(vrt_path) as src:
        if src.crs is None:
            raise RuntimeError("VRT missing CRS")
        bounds = src.bounds
        width = int(math.ceil((bounds.right - bounds.left) / TR_DEG))
        height = int(math.ceil((bounds.top - bounds.bottom) / TR_DEG))
        transform = from_origin(bounds.left, bounds.top, TR_DEG, TR_DEG)

        profile = {
            "driver": "GTiff",
            "height": height,
            "width": width,
            "count": 1,
            "dtype": "float32",
            "crs": "EPSG:4326",
            "transform": transform,
            "nodata": 0.0,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "compress": "deflate",
            "predictor": 2,
            "bigtiff": "YES",
        }

        with WarpedVRT(
            src,
            crs="EPSG:4326",
            transform=transform,
            width=width,
            height=height,
            resampling=Resampling.average,
            nodata=0.0,
            dtype="float32",
        ) as vrt:
            with rasterio.open(temp_out_path, "w", **profile) as dst:
                blocks_x = math.ceil(width / profile["blockxsize"])
                blocks_y = math.ceil(height / profile["blockysize"])
                total_blocks = blocks_x * blocks_y
                start_time = time.time()
                last_log = start_time
                log_every = max(1, int(args.log_every))
                log_seconds = max(1, int(args.log_seconds))
                completed = 0
                for _, window in dst.block_windows(1):
                    data = vrt.read(
                        1,
                        window=window,
                        out_dtype="float32",
                        fill_value=0.0,
                    )
                    data = data * 9.0
                    data = np.where(data < 0.0, 0.0, data)
                    dst.write(data, 1, window=window)
                    completed += 1
                    now = time.time()
                    if completed % log_every == 0 or (now - last_log) >= log_seconds:
                        elapsed = now - start_time
                        rate = completed / elapsed if elapsed > 0 else 0.0
                        remaining = total_blocks - completed
                        eta = remaining / rate if rate > 0 else 0.0
                        pct = (completed / total_blocks) * 100 if total_blocks else 0.0
                        print(
                            (
                                f"[hrsl] {completed}/{total_blocks} blocks "
                                f"({pct:.2f}%) elapsed={elapsed:.0f}s "
                                f"eta={eta:.0f}s rate={rate:.2f} blocks/s"
                            ),
                            flush=True,
                        )
                        last_log = now

                dst.build_overviews([2, 4, 8, 16], Resampling.average)
                dst.update_tags(ns="rio_overview", resampling="average")

    if OUT_PATH.exists():
        OUT_PATH.unlink()
    temp_out_path.replace(OUT_PATH)

    file_bytes = OUT_PATH.stat().st_size
    if file_bytes < 200 * 1024 * 1024:
        raise RuntimeError("HRSL output file too small for realism floor")

    with rasterio.open(OUT_PATH) as raster:
        if raster.crs is None or raster.crs.to_string() != "EPSG:4326":
            raise RuntimeError("Output CRS mismatch for HRSL raster")
        tr_x, tr_y = raster.res
        if abs(tr_x - TR_DEG) > 1e-12 or abs(tr_y - TR_DEG) > 1e-12:
            raise RuntimeError("Output resolution mismatch for HRSL raster")
        if raster.width < 50000 or raster.height < 25000:
            raise RuntimeError("Output raster dimensions below realism floor")

    output_sha256 = sha256_path(OUT_PATH)
    provenance = {
        "dataset_id": "hrsl_raster",
        "vintage": args.vintage,
        "semver": args.semver,
        "source": {
            "aws_registry_entry": "dataforgood-fb-hrsl",
            "bucket": "s3://dataforgood-fb-data/hrsl-cogs/",
            "vrt_url": args.vrt_url,
            "vrt_sha256": vrt_sha256,
            "vrt_bytes": vrt_bytes,
        },
        "build": {
            "tr_deg": TR_DEG,
            "resampling_law": "avg_then_times_9",
            "nodata": 0.0,
            "toolchain": {
                "rasterio": rasterio.__version__,
                "gdal": rasterio.__gdal_version__,
            },
        },
        "output": {
            "path": str(OUT_PATH.relative_to(ROOT)),
            "sha256": output_sha256,
            "bytes": file_bytes,
        },
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    PROV_PATH.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
