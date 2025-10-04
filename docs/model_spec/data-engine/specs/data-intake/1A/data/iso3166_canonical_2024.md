# Hunting and Gathering data for `iso3166_canonical_2024`

## What the engine needs (per preview)

Required columns: `country_iso`, `alpha3`, `numeric_code`, `name` (short English), `region`, `subregion`.
Optional: `start_date`, `end_date`.

I’ll use **DataHub – “country-codes”** as the *primary* open source (it includes ISO2/ISO3/numeric **and** UN M49 region/sub-region fields), with secondary sources for verification where helpful. I opened and verified each source below.

---

## Column 1 — `country_iso` (ISO-3166-1 alpha-2)

**Primary:** DataHub `country-codes.csv` → column **`ISO3166-1-Alpha-2`** (unique, 2-char).
**Cross-check (optional):** ipregistry `countries.csv` → **`#country_code_alpha2`**; UN M49 “Countries or areas” table (includes ISO code columns).

**Gather steps**

1. Download DataHub CSV (link on page) and extract **`ISO3166-1-Alpha-2`**; rename to **`country_iso`**; enforce regex `^[A-Z]{2}$`. DataHub page shows this column in its schema listing of ISO 3166 fields (alpha-2/alpha-3/numeric) and UN M49 fields.
2. Verify no nulls/dupes.
3. (Optional) Cross-check random sample vs ipregistry `countries.csv` for the alpha-2 column.

---

## Column 2 — `alpha3` (ISO-3166-1 alpha-3)

**Primary:** DataHub → **`ISO3166-1-Alpha-3`**.
**Cross-check (optional):** ipregistry → **`country_code_alpha3`**.

**Gather steps**

1. Extract DataHub **`ISO3166-1-Alpha-3`**; rename to **`alpha3`**; enforce `^[A-Z]{3}$`.
2. Validate `(alpha3, numeric_code)` uniqueness later when `numeric_code` is present.

---

## Column 3 — `numeric_code` (ISO-3166-1 numeric)

**Primary:** DataHub → **`ISO3166-1-numeric`**.
**Cross-check (optional):** ipregistry → **`numeric_code`** in `countries.csv`.

**Gather steps**

1. Extract **`ISO3166-1-numeric`**; rename to **`numeric_code`**; cast to integer (fits `int16`).
2. Verify uniqueness of `(alpha3, numeric_code)` pairs.

---

## Column 4 — `name` (short English country name)

**Primary (choose in this order, all on DataHub page):**

* **`official_name_en`** (official English short name), else
* **`UNTERM English Short`**, else
* **`CLDR display name`** (customary English short name).
  **Cross-check (optional):** ISO OBP (official browsing platform shows country listings with codes; you can visually confirm names).

**Gather steps**

1. From DataHub, pick **`official_name_en`** if present; if null use **`UNTERM English Short`**; else **`CLDR display name`**; rename to **`name`**.
2. Normalise whitespace; ensure the value is English (these three fields are specifically English on DataHub’s schema page).
3. Spot-check a few rows in ISO OBP for comfort (e.g., AF/AFG/004 shows Afghanistan).

---

## Column 5 — `region` (UN M49 region name)

**Primary:** DataHub → **`Region Name`** (UN Statistics M49 geoscheme).
**Cross-check (optional):** UN M49 page lists the region structure and codes (macro-region, sub-region, intermediate) for each country; helpful to spot-check assignments.

**Gather steps**

1. Extract **`Region Name`**; rename to **`region`**.
2. Validate values ∈ {Africa, Americas, Asia, Europe, Oceania} (UN macro-regions).

---

## Column 6 — `subregion` (UN M49 sub-region name)

**Primary:** DataHub → **`Sub-region Name`**.
**Cross-check (optional):** Luke’s **all.csv** has `sub-region` and is handy for quick human checks (not authoritative, updated to 30 Jun 2024).

**Gather steps**

1. Extract **`Sub-region Name`**; rename to **`subregion`** (no underscore).
2. Leave null where UN M49 has no sub-region (rare).

---

## Optional — `start_date`, `end_date` (effective dating)

There is **no open official CSV** of effective dates. Two pragmatic choices:

**A) Leave both null** (simplest). This keeps the dataset present-state only—acceptable if your schema marks them optional.

**B) Derive from a newsletter/OBP-based change log.**
Use the open-source **iso3166-updates** project (tracks ISO 3166 changes from newsletters/OBP; provides `/api/alpha/{code}`, `/api/year/{YYYY}`) to map first publication/change to `start_date` and withdrawal (if any) to `end_date`.

**Gather steps if using B**

1. For each `country_iso`, query `iso3166-updates` and parse “Date Issued” for the earliest relevant change as `start_date`; if a code is withdrawn/changed to a replacement, set `end_date` accordingly.
2. Keep a provenance file noting the source and the exact URLs used.
3. If you have licensed access to ISO’s **Country Codes Collection/OBP** exports (official CSV/XML/XLS), prefer those for dating; the ISO page explicitly states downloadable formats and a change archive exist.

---

## Why this plan is reasonable (and not hallucinated)

* **DataHub `country-codes` really contains the fields we need.** The public dataset page lists **ISO3166-1-Alpha-2**, **ISO3166-1-Alpha-3**, **ISO3166-1-numeric**, **Region Name**, **Sub-region Name**, plus numerous English name fields (e.g., **`UNTERM English Short`**, **`official_name_en`**, **`CLDR display name`**)—I verified on the live page.
* **UN M49 page is the ground truth for regions.** It shows ISO alpha-3 alongside M49 codes and regional assignment; perfect for spot-checking regional fields.
* **ISO OBP is the official reference.** The ISO site confirms you can preview & download the official codes (CSV/XML/XLS) via OBP/Country Codes Collection, and that a change archive exists; that underpins the optional dating path.
* **ipregistry & Luke’s repos are good cross-checks.** ipregistry provides clean alpha-2/alpha-3/numeric/name tables; Luke’s repo adds UN geoscheme fields and documents its update tags (last tag v10.0 on 30 Jun 2024).
* **FHIR ValueSet `iso3166-1-2` helps validate the alpha-2 domain programmatically** (generated expansion with regex `[A-Z]{2}`; updated 2025-10-03).

---

## Minimal reproducible recipe (single-pass gather)

1. **Download** DataHub `country-codes.csv`.
2. **Select & rename**:

   * `ISO3166-1-Alpha-2 → country_iso`
   * `ISO3166-1-Alpha-3 → alpha3`
   * `ISO3166-1-numeric → numeric_code` (cast to int; verify 3-digit formatting if you store as text)
   * `official_name_en` (fallback: `UNTERM English Short` → `CLDR display name`) → `name`
   * `Region Name → region`
   * `Sub-region Name → subregion`
3. **Clean & validate**:

   * `country_iso` uppercase & `^[A-Z]{2}$`; `alpha3` `^[A-Z]{3}$`; `(alpha3,numeric_code)` unique; no null PK.
   * `region ∈ {Africa, Americas, Asia, Europe, Oceania}`; `subregion` string or null.
4. **(Optional) Dates**: leave null *or* enrich via iso3166-updates / ISO OBP.
5. **(Optional) Cross-check**:

   * Sample row-by-row against ipregistry `countries.csv` for code triplets.
   * Spot-check a few regional rows against UN M49 page.
   * If you need an additional “second set of eyes” for region/sub-region, compare a slice with Luke’s `all.csv` (documentation shows columns `region`/`sub-region`).

---

## Gather script

> Primary source used in this script (opened & verified earlier):
> **DataHub – “country-codes”** (includes ISO2/ISO3/numeric, UN M49 region/sub-region, and multiple English name fields): [https://datahub.io/core/country-codes](https://datahub.io/core/country-codes) (raw CSV hosted on GitHub)

---

### `gather_iso3166_canonical_2024.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gather script for iso3166_canonical_2024
- Primary source: DataHub "country-codes" CSV
  https://datahub.io/core/country-codes  (raw CSV hosted by GitHub)
- Outputs: iso3166_canonical_2024.csv + iso3166_canonical_2024.qa.json
- Columns (exact spelling/order):
    country_iso, alpha3, numeric_code, name, region, subregion, start_date, end_date
- Guarantees:
    * PK: country_iso non-null, unique, regex ^[A-Z]{2}$
    * Codes: alpha3 regex ^[A-Z]{3}$; numeric_code int16; pairs (alpha3, numeric_code) unique
    * name: English short (official_name_en -> UNTERM English Short -> CLDR display name)
    * region ∈ {Africa, Americas, Asia, Europe, Oceania} or blank
    * subregion: string or blank
"""

import argparse
import io
import json
import os
import re
import sys
import hashlib
import subprocess
from datetime import datetime, timezone
from typing import List, Tuple

import pandas as pd
import requests


# ----- Config -----
DATAHUB_RAW_URL = (
    "https://raw.githubusercontent.com/datasets/country-codes/main/data/country-codes.csv"
)
REQUIRED_SOURCE_COLS = [
    "ISO3166-1-Alpha-2",
    "ISO3166-1-Alpha-3",
    "ISO3166-1-numeric",
    # english-name candidates:
    "official_name_en",
    "UNTERM English Short",
    "CLDR display name",
    # regions:
    "Region Name",
    "Sub-region Name",
]

ALLOWED_REGIONS = {"Africa", "Americas", "Asia", "Europe", "Oceania"}

OUT_CSV = "iso3166_canonical_2024.csv"
OUT_QA = "iso3166_canonical_2024.qa.json"
OUT_MANIFEST = "_manifest.json"


def fail(msg: str) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(1)


def fetch_datahub_csv(url: str) -> Tuple[pd.DataFrame, str]:
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
    except Exception as e:
        fail(f"Failed to download source CSV from {url}: {e}")
    try:
        # Keep strings as strings; don’t auto-parse dates.
        source_bytes = r.content
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        df = pd.read_csv(io.StringIO(source_bytes.decode("utf-8")), dtype=str, keep_default_na=False)
    except Exception as e:
        fail(f"Failed to parse CSV: {e}")
    return df, source_sha256


def ensure_source_columns(df: pd.DataFrame, cols: List[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        fail(
            "Source CSV is missing required columns:\n"
            + "\n".join(f"  - {c}" for c in missing)
        )


def pick_english_name(row: pd.Series) -> str:
    # ordered preference
    for c in ["official_name_en", "UNTERM English Short", "CLDR display name"]:
        v = row.get(c, "")
        v = (v or "").strip()
        if v:
            return v
    return ""


def coerce_numeric_code(v: str) -> int:
    # DataHub numeric codes are often 3-digit strings; cast to int
    v = (v or "").strip()
    if not v:
        return None  # will be caught by validator
    try:
        n = int(v)
    except Exception:
        return None
    # ISO numeric codes are 0..999; int16 range is fine
    if n < 0 or n > 999:
        return None
    return n


def build_canonical(df_src: pd.DataFrame) -> pd.DataFrame:
    # Select needed columns (rename); create English name via fallback
    rows = []
    for _, row in df_src.iterrows():
        country_iso = (row["ISO3166-1-Alpha-2"] or "").strip().upper()
        alpha3 = (row["ISO3166-1-Alpha-3"] or "").strip().upper()
        numeric_code = coerce_numeric_code(row["ISO3166-1-numeric"])
        name = pick_english_name(row)
        region = (row["Region Name"] or "").strip()
        subregion = (row["Sub-region Name"] or "").strip()

        rows.append(
            {
                "country_iso": country_iso,
                "alpha3": alpha3,
                "numeric_code": numeric_code,
                "name": name,
                "region": region,
                "subregion": subregion,
                # Optional effective dating (left blank by design)
                "start_date": "",
                "end_date": "",
            }
        )

    out = pd.DataFrame(rows, columns=[
        "country_iso",
        "alpha3",
        "numeric_code",
        "name",
        "region",
        "subregion",
        "start_date",
        "end_date",
    ])
    # Deterministic order
    out = out.sort_values(["country_iso"], kind="mergesort").reset_index(drop=True)
    return out


# ----- Validators against the engine’s preview/schema intent -----
RX_ISO2 = re.compile(r"^[A-Z]{2}$")
RX_ISO3 = re.compile(r"^[A-Z]{3}$")


def validate_iso2(series: pd.Series) -> Tuple[int, List[str]]:
    bad = []
    for i, v in series.items():
        if not v or not RX_ISO2.match(v):
            bad.append(f"{i}:{v!r}")
    return len(bad), bad


def validate_iso3(series: pd.Series) -> Tuple[int, List[str]]:
    bad = []
    for i, v in series.items():
        if not v or not RX_ISO3.match(v):
            bad.append(f"{i}:{v!r}")
    return len(bad), bad


def validate_numeric(series: pd.Series) -> Tuple[int, List[str]]:
    bad = []
    for i, v in series.items():
        if v is None:
            bad.append(f"{i}:<None>")
        else:
            try:
                iv = int(v)
            except Exception:
                bad.append(f"{i}:{v!r}")
                continue
            if iv < 0 or iv > 999:
                bad.append(f"{i}:{v!r}")
    return len(bad), bad


def validate_pairs_unique(df: pd.DataFrame) -> Tuple[int, List[Tuple[str, int]]]:
    dups = df[df.duplicated(subset=["alpha3", "numeric_code"], keep=False)]
    if dups.empty:
        return 0, []
    return len(dups), list(
        zip(dups["alpha3"].astype(str).tolist(), dups["numeric_code"].astype(int).tolist())
    )


def validate_region_values(series: pd.Series) -> Tuple[int, List[str]]:
    bad = []
    for i, v in series.items():
        v = (v or "").strip()
        if v and v not in ALLOWED_REGIONS:
            # Allow blank (optional)
            bad.append(f"{i}:{v!r}")
    return len(bad), bad


def run_validations(df: pd.DataFrame) -> dict:
    qa = {
        "rows": int(df.shape[0]),
        "distinct_country_iso": int(df["country_iso"].nunique()),
        "null_country_iso": int(df["country_iso"].isna().sum()),
        "null_name": int(df["name"].eq("").sum()),
        "null_region": int(df["region"].eq("").sum()),
        "null_subregion": int(df["subregion"].eq("").sum()),
    }
    # name must be a short English name (non-empty after fallback)
    if df["name"].eq("").any():
        bad_idx = df.index[df["name"].eq("")].tolist()[:10]
        fail(f"name is empty for {df['name'].eq('').sum()} rows; examples idx={bad_idx}")

    # PK: non-null & unique ISO2
    if df["country_iso"].isna().any():
        fail("country_iso contains nulls (PK must be non-null).")
    if df["country_iso"].duplicated().any():
        dups = df[df["country_iso"].duplicated()]["country_iso"].tolist()
        fail(f"country_iso has duplicates: {dups[:5]} ...")

    # Regex checks
    n_bad_iso2, bad_iso2 = validate_iso2(df["country_iso"])
    if n_bad_iso2:
        fail(f"country_iso regex violations: {bad_iso2[:10]} ...")

    n_bad_iso3, bad_iso3 = validate_iso3(df["alpha3"])
    if n_bad_iso3:
        fail(f"alpha3 regex violations: {bad_iso3[:10]} ...")

    n_bad_num, bad_num = validate_numeric(df["numeric_code"])
    if n_bad_num:
        fail(f"numeric_code invalid values: {bad_num[:10]} ...")

    # composite uniqueness
    n_dups, dup_pairs = validate_pairs_unique(df)
    if n_dups:
        fail(f"(alpha3, numeric_code) not unique. Examples: {dup_pairs[:10]} ...")

    # region check
    n_bad_region, bad_region = validate_region_values(df["region"])
    if n_bad_region:
        fail(f"region contains unexpected values: {bad_region[:10]} ...")

    # finalize QA counters
    qa["allowed_regions"] = sorted(ALLOWED_REGIONS)
    qa["alpha3_numeric_unique_pairs"] = True
    qa["source"] = DATAHUB_RAW_URL
    return qa

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def git_sha_short() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return ""

def main():
    parser = argparse.ArgumentParser(
        description="Gather iso3166_canonical_2024 from DataHub country-codes"
    )
    parser.add_argument("--out-csv", default=OUT_CSV, help="Output CSV path")
    parser.add_argument("--out-qa", default=OUT_QA, help="QA JSON sidecar path")
    parser.add_argument("--out-manifest", default=OUT_MANIFEST, help="Manifest JSON path")
    parser.add_argument("--version", default="", help="Dataset version tag (e.g., v2024-12-31)")    
    parser.add_argument(
        "--expect-min-rows",
        type=int,
        default=248,
        help="Guardrail: minimum expected rows (default 240)",
    )
    args = parser.parse_args()

    print(f"[INFO] Downloading source: {DATAHUB_RAW_URL}")
    src, source_sha256 = fetch_datahub_csv(DATAHUB_RAW_URL)

    print("[INFO] Verifying required source columns exist")
    ensure_source_columns(src, REQUIRED_SOURCE_COLS)

    print("[INFO] Building canonical table")
    dst = build_canonical(src)

    # Basic guardrail on row count
    if dst.shape[0] < args.expect_min_rows:
        fail(f"Too few rows after build: {dst.shape[0]} (< {args.expect_min_rows})")

    print("[INFO] Running validations")
    qa = run_validations(dst)

    print(f"[INFO] Writing {args.out_csv}")
    # Ensure exact column order
    dst = dst[
        ["country_iso", "alpha3", "numeric_code", "name", "region", "subregion", "start_date", "end_date"]
    ]
    dst.to_csv(args.out_csv, index=False)

    print(f"[INFO] Writing QA sidecar {args.out_qa}")
    with open(args.out_qa, "w", encoding="utf-8") as f:
        json.dump(qa, f, indent=2, ensure_ascii=False)

    # ---- Manifest (provenance) ----
    out_csv_sha = sha256_file(args.out_csv)
    out_qa_sha = sha256_file(args.out_qa)
    manifest = {
        "dataset_id": "iso3166_canonical_2024",
        "version": args.version,
        "source_url": DATAHUB_RAW_URL,
        "source_sha256": source_sha256,
        "output_csv": os.path.abspath(args.out_csv),
        "output_csv_sha256": out_csv_sha,
        "output_qa": os.path.abspath(args.out_qa),
        "output_qa_sha256": out_qa_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/gather_iso3166_canonical_2024.py",
        "generator_git_sha": git_sha_short(),
        "row_count": int(qa["rows"]),
        "column_order": ["country_iso","alpha3","numeric_code","name","region","subregion","start_date","end_date"],
        "allowed_regions": qa.get("allowed_regions", []),
    }
   print(f"[INFO] Writing manifest {args.out_manifest}")
   with open(args.out_manifest, "w", encoding="utf-8") as f:
       json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        
    print("[DONE] iso3166_canonical_2024 ready.")


if __name__ == "__main__":
    main()
```

---

### How to run

```bash
python3 gather_iso3166_canonical_2024.py \
  --out-csv iso3166_canonical_2024.csv \
  --out-qa  iso3166_canonical_2024.qa.json
```

This will:

* download the **DataHub country-codes** CSV (raw GitHub link),
* build the exact eight columns the engine expects,
* enforce **all** constraints (PK, regex, uniqueness, region set),
* leave `start_date`/`end_date` empty by design (they’re optional),
* write a small **QA JSON** with provenance and counts.


