#!/usr/bin/env python
"""
profile_parquet.py ─ YData-Profiling on a sample of the Parquet.
usage:
    poetry run python scripts/profile_parquet.py <path-to-parquet>
"""
import sys
import pathlib
import polars as pl
from ydata_profiling import ProfileReport

# --- Argument validation ---
if len(sys.argv) < 2:
    print("Usage: python scripts/profile_parquet.py <path-to-parquet>")
    sys.exit(1)

fn = pathlib.Path(sys.argv[1])
if not fn.exists():
    print(f"Error: file {fn} does not exist.")
    sys.exit(1)

# --- Load a sample of up to 100k rows via Polars (lazy scan + sample) ---
df = pl.scan_parquet(fn).sample(100_000, seed=42).collect()

# --- Build a minimal-profile HTML report using YData-Profiling ---
profile = ProfileReport(df.to_pandas(), minimal=True, title=f"Profile {fn.name}")

# --- Decide output path (same base name, .html suffix) and write ---
out = fn.with_suffix(".html")
profile.to_file(out)

# --- Print a success message with file size in MB ---
size_mb = out.stat().st_size / 1_048_576
print(f"✓ wrote {out} ({size_mb:0.1f} MB)")