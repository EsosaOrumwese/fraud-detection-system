## What the GDP bucket map “is” (information payload)

* A **deterministic segmentation** of countries into **K=5** macro buckets using their **2024 GDP per capita (constant 2015 US$)**.
* It encodes a **coarse, non-linear macro context** that the engine uses as **dummy features** (bucket 1..5) in the **S1 Hurdle** model.
* It’s **not re-estimated at runtime**. You compute it once from the pinned GDP table and **freeze the result** (and the breakpoints) so training/serving are aligned.

In other words: it’s a frozen mapping

```
country_iso → bucket_id ∈ {1,2,3,4,5}
```

plus the **global breakpoints** that define each bucket’s numeric range.

---

## Do we need an external dataset?

**No.** You derive it from your **frozen GDP table** (the one we just built) and then publish two artefacts:

1. **Breaks sidecar** (metadata)

   * `year: 2024`
   * `series: NY.GDP.PCAP.KD`
   * `method: Fisher–Jenks (natural breaks), K=5`
   * `breakpoints`: `[b0, b1, b2, b3, b4, b5]` with `b0 = min(g)`, `b5 = max(g)`
   * `dp` (decimal places used when serialising), `rounding: half-even`
   * `population_weighted: false` (recommended)
   * `input_universe`: count of countries used (should match your GDP table’s coverage)
   * lineage anchors: reference to the GDP dataset’s parameter hash / manifest fingerprint

2. **Per-country bucket map** (the table the engine reads)

   * Columns:

     * `country_iso : ISO2 (PK)`
     * `bucket_id : int ∈ {1..5}`
     * (optional) `gdp_pc_usd_2015 : float64` (echoed for audit/replay)
   * Partitioning & lineage per your S0 rules.

---

## How to derive it (deterministically)

1. **Input universe**

   * Start from the **final GDP CSV** (the 2024 snapshot you just approved).
   * Use only rows with **valid, positive `gdp_pc_usd_2015`** and a valid **ISO-2**.
   * Resulting set size today is ~**177** (or **~184** if you include the few extra territories we can map via your canonical ISO file—e.g., `HK`, `MO`, `PR`, `PS`, `SX`, `TC`, `BM`—all with actual 2024 values).

2. **Compute breaks**

   * Use **Fisher–Jenks (a.k.a. Jenks natural breaks)** with **K=5** on the **unweighted** array of 2024 GDP values.
   * The Fisher–Jenks DP algorithm is **deterministic** for a fixed input; avoid heuristic/approximate variants.
   * **Tie rule:** if a value equals an internal breakpoint, assign it to the **upper** bucket (document this).
   * Store breakpoints with a fixed decimal precision (e.g., `dp=2` or `dp=1`), and record the **exact unrounded** values inside the sidecar for byte-replay.

3. **Assign buckets**

   * For each country: find the interval `[b_k, b_{k+1})` (or your tie rule) that contains `gdp_pc_usd_2015` and set `bucket_id = k+1`.
   * Emit one row per `country_iso`.

4. **Freeze & publish**

   * Publish the **breaks sidecar** and the **bucket map table** together.
   * Pin both to the **same vintage/year** as the GDP table; **do not recompute at runtime**.

---

## Why freeze (and not recompute)?

* Buckets are a **feature definition**, not dynamic data. Recomputing would change design matrices and silently drift your hurdle model’s behaviour.
* Freezing the breaks ensures any refits or replays see the **identical** bucket encoding.

---

## Coverage considerations (your 177 rows)

* The bucket map covers exactly the set with valid 2024 GDP values (e.g., 177 or 184 entries, depending on ISO mapping choice).
* **If** any merchant’s `home_country_iso` is **not** in that set, they won’t have a bucket—S1 dummies would be undefined.
* Remedy **only if needed** (i.e., if such merchants exist):

  1. **Prefer** adding them via a verified 2024 GDP value (some territories do have 2024 values and can be recovered by using your canonical ISO mapping).
  2. If no 2024 exists, you may (with explicit documentation):

     * carry-forward the **most recent** available year for that country; **or**
     * exclude those merchants from the universe for this run.

  * Do **not** impute from regional averages unless you explicitly accept the realism trade-off and record it in the sidecar; it changes the distribution and can shift breaks if you recompute.

---

## Minimal schema (what I recommend you freeze)

**A. Breaks sidecar (YAML/JSON)**

```yaml
gdp_bucket_breaks:
  year: 2024
  series: NY.GDP.PCAP.KD
  method: fisher-jenks
  k: 5
  breakpoints_unrounded: [b0, b1, b2, b3, b4, b5]
  breakpoints_dp: 2
  rounding: half-even
  population_weighted: false
  input_universe: 177    # or 184, depending on mapping choice
  lineage:
    gdp_dataset_parameter_hash: "<...>"
    gdp_dataset_manifest_fingerprint: "<...>"
```

**B. Bucket map table (Parquet/CSV)**

```
country_iso : string(ISO2, uppercase)  # PK
bucket_id   : int8  # {1..5}
# optional:
gdp_pc_usd_2015 : float64
```

---

## My judgement call

* **Derive internally** from your pinned GDP dataset (no external source).
* **Compute once, freeze, and pin** to the GDP vintage/year.
* **Unweighted Fisher–Jenks (K=5)**, document the tie rule, and store breakpoints + lineage in a sidecar.
* **Coverage is sufficient** if all merchant home countries appear in the GDP table; run a quick join to confirm. If gaps matter, add only the **few** countries with real 2024 values (recoverable via your canonical ISO mapping), and avoid imputation unless you must—and if you must, document it loudly.

---

## Implementation

Here’s a clean, deterministic, **Fisher–Jenks (natural breaks)** implementation that:

* reads your frozen GDP CSV (`country_iso,gdp_pc_usd_2015,observation_year,source_series`),
* computes **K** buckets (configurable),
* emits **(1)** a sidecar with exact + rounded breakpoints and lineage, and **(2)** a per-country **bucket map**,
* uses **half-even** rounding and a documented **tie-to-upper** rule,
* stays fast and fully reproducible (no heuristic libs needed).


> **Ingestion (schema) run**
>
> ```bash
> python gdp_bucket_map.py \
>   --gdp-csv /path/to/world_bank_gdp_pc_2024.csv \
>   --year 2024 \
>   --k 5 \
>   --out-dir ./out \
>   --labels preset \
>   --schema-mode \
>   --ingestion-path "reference/economic/gdp_bucket_map/{year}/gdp_bucket_map.parquet"
> ```
>
> Sidecar → `./out/gdp_bucket_breaks.Y2024.K5.yaml`
> Official table → `reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet`

> **Research run (non-schema)** — try different K, write CSV for quick eyeballing:
>
> ```bash
> python gdp_bucket_map.py --gdp-csv ./world_bank_gdp_pc_2024.csv --year 2024 --k 4 --out-dir ./scratch --labels none
> ```

---

```python
#!/usr/bin/env python3
# gdp_bucket_map.py  —  schema-conformant GDP bucket derivation

"""
Derive a frozen country→bucket map from a pinned GDP-per-capita snapshot (constant 2015 USD).

Input CSV (engine GDP table):
  country_iso,gdp_pc_usd_2015,observation_year,source_series
  AO,2364.84659101208,2024,NY.GDP.PCAP.KD
  ...

Outputs:
  1) Sidecar YAML: gdp_bucket_breaks.Y{year}.K{k}.yaml
     - exact & rounded breakpoints (half-even), tie rule, input universe, lineage
  2) Official table (schema mode):
     - reference/economic/gdp_bucket_map/{year}/gdp_bucket_map.parquet
       Columns (per schema.ingress.layer1.yaml#/gdp_bucket_map_2024):
         country_iso (PK, ISO2, FK to iso3166_canonical_2024)
         bucket_id   (int32, 1..5)
         bucket_label (string, nullable)  # optional readable label
         method      (string, const "jenks")
         k           (int8,    const 5)
         source_year (int16,   = year)
  3) Research table (non-schema mode): CSV in --out-dir (country_iso,bucket_id[,gdp])

Determinism:
- Exact Fisher–Jenks (DP), unweighted; tie: equals internal breakpoint → upper bucket.
- Stable sort; outputs are reproducible for fixed input.
"""

from __future__ import annotations
import argparse, csv, hashlib, os, sys
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import List, Tuple
import numpy as np
import pandas as pd
import yaml

# ---------------- Utilities ----------------

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def round_half_even(x: float, dp: int) -> str:
    getcontext().prec = 50
    q = Decimal(10) ** (-dp)
    return str(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_EVEN))

def atomic_write_parquet(df: pd.DataFrame, dest_path: str) -> None:
    """
    Write Parquet atomically. Requires pyarrow or fastparquet.
    Falls back to CSV (same dest basename + .csv) with a warning.
    """
    tmp = dest_path + ".tmp"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        # Prefer pyarrow
        try:
            import pyarrow  # noqa: F401
            engine = "pyarrow"
        except Exception:
            import fastparquet  # noqa: F401
            engine = "fastparquet"
        df.to_parquet(tmp, index=False, engine=engine)
        os.replace(tmp, dest_path)
    except Exception as e:
        # Fallback to CSV when parquet engine is unavailable
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass
        csv_fallback = os.path.splitext(dest_path)[0] + ".csv"
        print(f"[warn] Parquet engine not available or failed ({e}). Falling back to CSV: {csv_fallback}")
        df.to_csv(csv_fallback, index=False, quoting=csv.QUOTE_MINIMAL)

# ---------------- Jenks DP ----------------

@dataclass(frozen=True)
class JenksResult:
    starts: List[int]
    ends: List[int]

def _wss_prefix(s1: np.ndarray, s2: np.ndarray, a: int, b: int) -> float:
    n = b - a + 1
    sumx = s1[b] - s1[a - 1]
    sumx2 = s2[b] - s2[a - 1]
    return float(sumx2 - (sumx * sumx) / n)

def jenks_fisher(x_sorted: np.ndarray, k: int) -> JenksResult:
    n = x_sorted.size
    s1 = np.zeros(n + 1, dtype=np.float64)
    s2 = np.zeros(n + 1, dtype=np.float64)
    s1[1:] = np.cumsum(x_sorted)
    s2[1:] = np.cumsum(x_sorted * x_sorted)

    F = np.full((k + 1, n + 1), np.inf, dtype=np.float64)
    B = np.zeros((k + 1, n + 1), dtype=np.int32)

    for i in range(1, n + 1):
        F[1, i] = _wss_prefix(s1, s2, 1, i)
        B[1, i] = 1

    for c in range(2, k + 1):
        for i in range(c, n + 1):
            best_cost = np.inf
            best_m = c - 1
            for m in range(c - 1, i):
                cost = F[c - 1, m] + _wss_prefix(s1, s2, m + 1, i)
                if cost < best_cost:
                    best_cost = cost
                    best_m = m
            F[c, i] = best_cost
            B[c, i] = best_m + 1

    starts, ends = [0]*k, [0]*k
    i = n
    for c in range(k, 0, -1):
        start = int(B[c, i])
        starts[c - 1] = start
        ends[c - 1] = i
        i = start - 1
    return JenksResult(starts=starts, ends=ends)

def compute_breaks_from_classes(x_sorted: np.ndarray, jr: JenksResult) -> Tuple[List[float], List[float]]:
    k = len(jr.starts)
    E = [float(x_sorted[jr.starts[0] - 1])]
    class_mins = [float(x_sorted[jr.starts[c] - 1]) for c in range(k)]
    for c in range(1, k):
        E.append(float(x_sorted[jr.starts[c] - 1]))
    E.append(float(x_sorted[jr.ends[-1] - 1]))
    return E, class_mins

def assign_buckets_by_index(n: int, jr: JenksResult) -> np.ndarray:
    k = len(jr.starts)
    bucket = np.zeros(n, dtype=np.int16)
    for c in range(k):
        s = jr.starts[c] - 1
        e = jr.ends[c] - 1
        bucket[s:e + 1] = c + 1
    return bucket

# ---------------- Main ----------------

def main():
    ap = argparse.ArgumentParser(description="Derive country→GDP bucket map (schema-conformant).")
    ap.add_argument("--gdp-csv", required=True, help="Input GDP CSV with columns: country_iso,gdp_pc_usd_2015,observation_year,source_series")
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--k", type=int, default=5, help="Number of buckets (research mode). Schema mode enforces k=5.")
    ap.add_argument("--dp", type=int, default=2, help="Decimal places for breakpoints in sidecar (rounded).")
    ap.add_argument("--out-dir", default=".", help="Where to write the sidecar and (optionally) research CSV.")
    ap.add_argument("--labels", choices=["preset","none"], default="preset", help="Write human labels (preset) or NULLs (none).")
    ap.add_argument("--schema-mode", action="store_true", help="Emit official ingestion table per schema (method, k=5, source_year).")
    ap.add_argument("--ingestion-path", default="reference/economic/gdp_bucket_map/{year}/gdp_bucket_map.parquet",
                    help="Destination path for official Parquet (schema mode). {year} is substituted.")
    ap.add_argument("--emit-research-csv", action="store_true", help="Also write research CSV to --out-dir (country_iso,bucket_id[,gdp]).")
    ap.add_argument("--echo-gdp", action="store_true", help="If writing research CSV, include gdp_pc_usd_2015.")
    ap.add_argument(
        "--iso-path",
        default="",
        help="Sealed ISO canonical file (CSV or Parquet) with column 'country_iso' (applies sealed-universe coverage gate)."
    )
    ap.add_argument(
        "--coverage-policy",
        default="fail",
        choices=["fail","none"],
        help="fail (default) aborts if sealed ISO coverage < 100%; none only warns."
    )

    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    df = pd.read_csv(args.gdp_csv, dtype={"country_iso": "string", "source_series": "string"})
    required = {"country_iso","gdp_pc_usd_2015","observation_year","source_series"}
    miss = required - set(df.columns)
    if miss:
        raise ValueError(f"Input missing columns: {sorted(miss)}")

    df = df[df["observation_year"] == args.year].copy()
    df["gdp_pc_usd_2015"] = pd.to_numeric(df["gdp_pc_usd_2015"], errors="coerce")
    df = df[df["gdp_pc_usd_2015"].notna() & (df["gdp_pc_usd_2015"] > 0)]
    df["country_iso"] = df["country_iso"].str.upper()
    df = df[df["country_iso"].str.fullmatch(r"[A-Z]{2}")]
    df = df.sort_values(["country_iso","gdp_pc_usd_2015"], ascending=[True, False]).drop_duplicates("country_iso")

    # --- semantic guards on GDP slice (series & year) ---
    if "source_series" not in df.columns or "observation_year" not in df.columns:
        raise ValueError("GDP CSV must contain: country_iso,gdp_pc_usd_2015,observation_year,source_series")
    bad_series = df.loc[df["source_series"] != "NY.GDP.PCAP.KD", "source_series"].unique()
    if bad_series.size:
        raise ValueError(f"Unexpected source_series in GDP CSV: {bad_series[:5]}")
    bad_year = df.loc[df["observation_year"].astype(str) != str(args.year), "observation_year"].unique()
    if bad_year.size:
        raise ValueError(f"Unexpected observation_year in GDP CSV: {bad_year[:5]} (expected {args.year})")

    # --- sealed-universe coverage gate (parity with GDP job) ---
    sealed_size = kept_size = None
    missing = extras = None
    if args.iso_path:
        if args.iso_path.lower().endswith(".parquet"):
            try:
                import pyarrow.parquet as pq  # local import; optional
                iso_tbl = pq.read_table(args.iso_path)
                iso_df = iso_tbl.to_pandas()
            except Exception as e:
                raise RuntimeError("pyarrow required to read sealed ISO Parquet") from e
        else:
            iso_df = pd.read_csv(args.iso_path, dtype=str, keep_default_na=False)
        if "country_iso" not in iso_df.columns:
            raise ValueError(f"Sealed ISO file missing 'country_iso': {args.iso_path}")
        iso_set = set(iso_df["country_iso"].astype(str).str.upper())
        df["country_iso"] = df["country_iso"].astype(str).str.upper()
        pre_set = set(df["country_iso"])
        extras_pre = sorted(pre_set - iso_set)  # QA only
        df = df[df["country_iso"].isin(iso_set)].copy()
        sealed_size = len(iso_set)
        kept_size   = len(df)
        gdp_set     = set(df["country_iso"])
        missing     = sorted(iso_set - gdp_set)
        extras      = sorted(gdp_set - iso_set)
        if missing or extras:
            msg = (f"Coverage mismatch vs sealed ISO: sealed={sealed_size}, kept={kept_size}, "
                   f"missing={len(missing)}, extras={len(extras)}; "
                   f"missing[:10]={missing[:10]} extras_pre[:10]={extras_pre[:10]}")
            if args.coverage_policy == "fail":
                raise ValueError(msg)
            else:
                print("[warn]", msg)
    else:
        print("[warn] --iso-path not provided; skipping sealed-universe coverage gate.")

    vals = df["gdp_pc_usd_2015"].to_numpy(dtype=np.float64)
    if vals.size < 2:
        raise ValueError("Not enough countries with valid GDP values.")
    unique_vals = np.unique(vals).size

    # Enforce schema K=5 in schema mode; allow variable K in research mode.
    if args.schema_mode and args.k != 5:
        raise ValueError("Schema mode requires K=5 (schema constant). Use non-schema mode for experiments.")
    k = min(args.k, max(2, unique_vals))

    order = np.argsort(vals, kind="mergesort")
    x_sorted = vals[order]
    idx_sorted = df.index.to_numpy()[order]

    jr = jenks_fisher(x_sorted, k)
    bucket_sorted = assign_buckets_by_index(x_sorted.size, jr)
    bucket_by_row = pd.Series(bucket_sorted, index=idx_sorted, dtype="int16")
    df["bucket_id"] = bucket_by_row.reindex(df.index).astype("int32")  # schema says int32
    # QA: ensure all 5 buckets are populated (helps catch pathological inputs)
    _counts = df["bucket_id"].value_counts().reindex([1,2,3,4,5], fill_value=0)
    assert _counts.min() > 0, f"Empty bucket(s) detected: {_counts.to_dict()}"

    breaks_unrounded, class_mins = compute_breaks_from_classes(x_sorted, jr)
    breaks_rounded = [float(round_half_even(b, args.dp)) for b in breaks_unrounded]

    # Sidecar
    sidecar = {
        "gdp_bucket_breaks": {
            "year": args.year,
            "series": "NY.GDP.PCAP.KD",
            "method": "jenks",
            "k": k,
            "breakpoints_unrounded": [float(b) for b in breaks_unrounded],
            "breakpoints_rounded": [round_half_even(b, args.dp) for b in breaks_unrounded],
            "breakpoints_dp": args.dp,
            "rounding": "half-even",
            "population_weighted": False,
            "tie_rule": "equals_internal_breakpoint_goes_to_upper_bucket",
            "class_mins": [float(c) for c in class_mins],
            "input_universe": int(vals.size),
            "lineage": {
                "gdp_csv_path": os.path.abspath(args.gdp_csv),
                "gdp_csv_sha256": sha256_file(args.gdp_csv),
            },
        }
    }
    sidecar_path = os.path.join(args.out_dir, f"gdp_bucket_breaks.Y{args.year}.K{k}.yaml")
    with open(sidecar_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(sidecar, f, sort_keys=False, allow_unicode=True)

    # Optional bucket labels (schema allows nullable)
    if args.labels == "preset":
        preset = {1:"Very Low", 2:"Low", 3:"Medium", 4:"High", 5:"Very High"}
        df["bucket_label"] = df["bucket_id"].map(preset).astype("string")
    else:
        df["bucket_label"] = pd.Series([None]*len(df), dtype="string")

    # ----- Emit official ingestion table (schema mode) -----
    if args.schema_mode:
        out = df[["country_iso","bucket_id","bucket_label"]].copy()
        out["method"] = "jenks"
        out["k"] = np.int8(5)   # schema const
        out["source_year"] = np.int16(args.year)

        dest = args.ingestion_path.format(year=args.year)
        atomic_write_parquet(out.sort_values("country_iso").reset_index(drop=True), dest)
        print(f"[ok] Ingestion table written → {dest}")

        # ---- Manifest (provenance) ----
        parquet_sha = sha256_file(dest) if os.path.exists(dest) else ""
        sidecar_sha = sha256_file(sidecar_path) if os.path.exists(sidecar_path) else ""
        try:
            coverage_pct = round(100.0 * kept_size / max(1, sealed_size), 2) if sealed_size else None
        except Exception:
            coverage_pct = None
        manifest = {
            "dataset_id": "gdp_bucket_map_2024",
            "version": str(args.year),
            "input_gdp_csv_path": os.path.abspath(args.gdp_csv),
            "input_gdp_csv_sha256": sha256_file(args.gdp_csv),
            "sealed_iso_path": os.path.abspath(args.iso_path) if args.iso_path else "",
            "output_parquet": os.path.abspath(dest),
            "output_parquet_sha256": parquet_sha,
            "breaks_sidecar": os.path.abspath(sidecar_path),
            "breaks_sidecar_sha256": sidecar_sha,
            "generated_at_utc": pd.Timestamp.utcnow().isoformat(),
            "runtime": { "python": sys.version.split()[0], "pandas": pd.__version__ },
            "method": "jenks",
            "k": int(k),
            "breakpoints_unrounded": [float(b) for b in breaks_unrounded],
            "breakpoints_rounded": [round_half_even(b, args.dp) for b in breaks_unrounded],
            "breakpoints_dp": int(args.dp),
            "tie_rule": "equals_internal_breakpoint_goes_to_upper_bucket",
            "sealed_iso_size": sealed_size,
            "bucketmap_rows": int(out.shape[0]),
            "coverage_pct": coverage_pct,
            "missing_count": len(missing) if missing is not None else None,
            "extras_count": len(extras) if extras is not None else None
        }
        man_path = os.path.join(os.path.dirname(dest), "_manifest.json")
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"[ok] Manifest written → {man_path}")

    # ----- Emit research CSV (optional) -----
    if args.emit_research_csv:
        cols = ["country_iso","bucket_id"]
        if args.echo_gdp:
            cols.append("gdp_pc_usd_2015")
        research = df[cols].sort_values("country_iso").reset_index(drop=True)
        csv_path = os.path.join(args.out_dir, f"gdp_bucket_map.Y{args.year}.K{k}.csv")
        research.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        print(f"[ok] Research CSV written → {csv_path}")

    bmin = breaks_rounded[0]
    bmax = breaks_rounded[-1]
    print(f"[ok] Buckets computed (K={k}) for {args.year}. Universe={vals.size}. Breaks [{bmin} … {bmax}]")
    print(f"[ok] Sidecar → {sidecar_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(2)
```

---


### Notes & knobs you can tweak

* `--k` controls the number of buckets (defaults to **5**).
* `--dp` controls how many decimals the **rounded** breakpoints carry in the sidecar (exact unrounded values are preserved as well).
* Classification uses the **DP class memberships** directly (no float threshold ambiguity). The **sidecar** records a tie rule: “equals internal breakpoint → upper bucket.”
* If you later enhance coverage (e.g., add `HK`, `MO`, `PR`, …) and rerun this script on the updated GDP CSV, the buckets will be recomputed deterministically for the new universe — pin the resulting sidecar to your run/vintage and freeze it.
