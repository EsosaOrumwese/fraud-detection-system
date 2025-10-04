## Hunting

Here’s what I’ve found so far for the World Bank GDP‑per‑capita dataset (constant 2015 US$) and its columns.  This matches the ingestion spec, so we can move into gathering next.

### Dataset‑level overview

* **Purpose:** Provide a macro lookup table that gives each country’s GDP per capita in 2015 US$ for **2024**.  The engine uses this to pre‑assign each merchant’s home country a macro `g_c` value, which drives the fixed Jenks‑5 GDP bucket and the `ln(g_c)` term in the NB‑dispersion model.
* **Source found:** The World Bank’s API exposes this indicator (`NY.GDP.PCAP.KD`).  A call like `https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.KD?format=json` returns data fields for each country including `countryiso3code`, `date`, and `value`.  The `indicator.id` in the JSON response confirms we are using the correct series (`NY.GDP.PCAP.KD`).
* **Shape expected:** One row per ISO‑2 country for the observation year 2024.  Values must be positive and non‑null.  We will need to convert the API’s ISO‑3 codes to ISO‑2 using our canonical ISO table.

### Column‑by‑column information & where to hunt

| Column name           | Information carried                                                                                                                  | Where/how to hunt                                                                                                                                           |
|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `country_iso` (ISO‑2) | The country code that joins GDP values to the merchant universe.  It ensures alignment across all engine artefacts.                  | The API provides `countryiso3code`; we’ll map these to ISO‑2 via our canonical ISO‑3166 dataset.  We’ll check that all merchant home countries are covered. |
| `observation_year`    | Indicates the year of the GDP value; for this run it is **2024**.  Fixing the year ensures deterministic replay.                     | In the API, the `date` field holds the year; we will filter for `date = 2024` and store it as a constant column `2024`.                                     |
| `gdp_pc_usd_2015`     | The actual GDP per capita figure in constant 2015 U.S. dollars.  It feeds the Jenks bucket and the dispersion model (via `ln(g_c)`). | From the API, the `value` field provides this measurement for each country.  We’ll extract the 2024 value and verify it’s >0.                               |
| `source_series`       | Semantic guardrail to prove we are using the right World Bank series.  It should always read `NY.GDP.PCAP.KD`.                       | In the API response, each record includes `indicator.id` equal to `NY.GDP.PCAP.KD`; we will set this constant for all rows.                                 |

### Next steps

1. **Gather:** Use the World Bank API to fetch all records for indicator `NY.GDP.PCAP.KD`.  Iterate through pages as needed to retrieve every country.
2. **Filter & transform:** Keep only records where `date = 2024`, convert `countryiso3code` → ISO‑2, add `observation_year = 2024`, and set `source_series = "NY.GDP.PCAP.KD"`.
3. **Validate:** Check that all merchant home countries have entries, ensure `gdp_pc_usd_2015 > 0`, and verify FK integrity against our ISO‑3166 canonical table.

Once you’re ready, I’ll move on to the gathering stage and begin pulling and processing the data accordingly.

## Gathering

Below is a detailed, step‑by‑step reproducible plan for gathering and preparing the **GDP per capita (constant 2015US$)** data for your data engine.  I’ve included links to the relevant sources so you can follow every step.

---

### 1. Identify the required information

The ingestion spec expects a lookup table keyed by ISO‑2 country codes with:

* **`gdp_pc_usd_2015`** – GDP per capita (constant 2015 US$) for **2024**.
* **`observation_year`** – a constant 2024.
* **`source_series`** – the World Bank indicator ID `NY.GDP.PCAP.KD`.
* **`country_iso`** – two‑letter ISO‑2 code (uppercase).

We need to build this table so the engine can derive Jenks‑5 GDP buckets and the dispersion model’s `ln(g_c)` term.

---

### 2. Locate and download the raw data

1. **World Bank API**
   The World Bank exposes the indicator via its REST API. A call such as `https://api.worldbank.org/v2/country/USA/indicator/NY.GDP.PCAP.KD?format=json` returns JSON containing `countryiso3code`, `date`, and `value` for each year; the `indicator.id` is `NY.GDP.PCAP.KD`, verifying we’re pulling the correct series.

2. **Bulk CSV download**
   For efficiency, use the CSV download link on the indicator page (click “CSV” under “Download” at the World Bank’s Data page).  The link has the form:

   ```
   https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.KD?downloadformat=csv
   ```

   It returns a ZIP archive containing:

   * `API_NY.GDP.PCAP.KD_DS2_en_csv_v2_*.csv` (main dataset)
   * `Metadata_Country_API_NY.GDP.PCAP.KD_DS2_en_csv_v2_*.csv` (metadata)
   * `Metadata_Indicator_API_NY.GDP.PCAP.KD_DS2_en_csv_v2_*.csv` (indicator description)

   The main dataset is wide: after a few metadata lines, the header row lists `Country Name`, `Country Code` (ISO‑3), `Indicator Name`, `Indicator Code`, followed by year columns (`1960`, `1961`, …, `2024`). Each row holds a country’s GDP per capita for all years.

3. **ISO‑code mapping**
   The CSV uses ISO‑3 codes (`USA`, `GBR`, etc.), but the engine needs ISO‑2.  Download the mapping file from the `world_countries` repository:

   ```
   https://raw.githubusercontent.com/stefangabos/world_countries/master/data/countries/en/countries.csv
   ```

   This simple CSV has columns `alpha2`, `alpha3`, and `name`.  We’ll use it to map ISO‑3 codes to uppercase ISO‑2 codes.

---

### 3. Processing workflow (scriptable)

1. **Extract and load**

   * Unzip the World Bank archive.
   * Skip the first four metadata lines in `API_NY.GDP.PCAP.KD_DS2_en_csv_v2_*.csv` and read the header row; use a data library (e.g. pandas).
   * Load the `countries.csv` mapping file and convert `alpha2`/`alpha3` to uppercase for consistent joins.

2. **Normalize country codes**

   * Rename `Country Code` to `iso3` and uppercase it.
   * Join to the ISO mapping on `iso3` → `alpha3` to create a new `iso2` column.
   * Drop any rows where `iso2` is missing; these are aggregate regions (e.g., “Arab World,” “Euro area”) or territories not in the engine’s ISO universe.

3. **Extract the 2024 value**

   * Convert the `2024` column to numeric.
   * Filter to rows with `gdp_pc_usd_2015 > 0` and non‑null.
   * Build the output columns:

     * `country_iso` = `iso2` (uppercase)
     * `gdp_pc_usd_2015` = 2024 value
     * `observation_year` = 2024
     * `source_series` = `NY.GDP.PCAP.KD`

4. **Quality checks**

   * Validate that there are no duplicate `country_iso` entries.
   * Check for any missing or zero GDP values; drop or flag them.
   * (Optional) Cross‑join with your merchant seed dataset to ensure every merchant home country has a GDP entry.

5. **Export**

   * Save the resulting table as a CSV (and optionally Parquet if your environment has `pyarrow`).
   * Document the script and commands used so the process can be reproduced.

#### Script

```python
#!/usr/bin/env python3
"""
Gather GDP per capita (constant 2015 USD) data for a fixed year and
produce a tidy lookup table keyed by ISO‑2 country codes.

This script was written for the merchant‑location realism engine. It
downloads raw GDP per‑capita data from the World Bank and maps ISO‑3
country codes to ISO‑2 codes using the `world_countries` dataset.

Steps performed:

1. **Download the GDP dataset** — The World Bank provides a bulk ZIP
   file for the indicator `NY.GDP.PCAP.KD` at:
   https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.KD?downloadformat=csv .
   The ZIP contains a wide CSV where each row represents a country and
   each column represents a year (1960–present). The first four lines
   of the CSV contain metadata and are skipped.

2. **Download the ISO mapping** — The `world_countries` project
   publishes a CSV listing `alpha2` and `alpha3` codes for every
   country:
   https://raw.githubusercontent.com/stefangabos/world_countries/master/data/countries/en/countries.csv .

3. **Process the data** — The script renames and uppercases the
   ISO‑3 codes, joins them to the ISO‑2 mapping, extracts the value
   for the specified year, filters out aggregate regions (which lack
   ISO‑2 codes) and non‑positive values, and constructs the final
   fields:
   `country_iso`, `gdp_pc_usd_2015`, `observation_year`, and
   `source_series`.

4. **Write the result** — The resulting DataFrame is written to
   `world_bank_gdp_pc_{year}.csv` in the current working directory.

Usage:

    python gdp_gather_script.py            # Downloads and processes 2024
    python gdp_gather_script.py --year 2023

This script requires the `pandas` and `requests` libraries.
"""

import argparse
import io
import os
import zipfile
from typing import Optional

import pandas as pd
import requests
import json, os, hashlib, subprocess
from datetime import datetime, timezone

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()

def _git_sha_short() -> str:
    try:
        return subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
    except Exception:
        return ""


def download_world_bank_gdp_zip(url: str = None) -> pd.DataFrame:
    """Download and parse the World Bank GDP per‑capita ZIP.

    Args:
        url: Optional override for the World Bank CSV download URL.

    Returns:
        DataFrame containing the wide GDP per‑capita data with ISO‑3
        codes and year columns.

    Raises:
        HTTPError if the download fails or the ZIP lacks the expected
        CSV file.
    """
    default_url = (
        "https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.KD"
        "?downloadformat=csv"
    )
    download_url = url or default_url
    # Fetch the ZIP archive from the World Bank.
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    # Load ZIP content into an in-memory buffer and compute SHA-256.
    _zip_bytes = response.content
    _source_zip_sha256 = hashlib.sha256(_zip_bytes).hexdigest()
    with zipfile.ZipFile(io.BytesIO(_zip_bytes)) as zf:
        # Locate the main CSV containing the GDP data.
        csv_name: Optional[str] = None
        for name in zf.namelist():
            lower_name = name.lower()
            if (
                lower_name.startswith("api_ny.gdp.pcap.kd")
                and lower_name.endswith(".csv")
                and "metadata" not in lower_name
            ):
                csv_name = name
                break
        if not csv_name:
            raise RuntimeError(
                "Failed to find the main GDP CSV in the downloaded ZIP"
            )
        # Read the CSV, skipping the first four lines of metadata.
        with zf.open(csv_name) as csv_file:
            gdp_df = pd.read_csv(csv_file, skiprows=4)
    # Return both the dataframe and the source archive SHA for manifesting
    return gdp_df, _source_zip_sha256


def download_iso_mapping(url: str = None) -> pd.DataFrame:
    """Download and prepare the ISO‑3 to ISO‑2 mapping.

    Args:
        url: Optional override for the ISO mapping URL.

    Returns:
        DataFrame with columns `alpha3` and `alpha2` in uppercase.
    """
    default_url = (
        "https://raw.githubusercontent.com/stefangabos/world_countries/"
        "master/data/countries/en/countries.csv"
    )
    mapping_url = url or default_url
    mapping_df = pd.read_csv(mapping_url)
    # Standardise case for join.
    mapping_df["alpha3"] = mapping_df["alpha3"].str.upper()
    mapping_df["alpha2"] = mapping_df["alpha2"].str.upper()
    return mapping_df


def build_gdp_dataset(
    gdp_df: pd.DataFrame,
    iso_df: pd.DataFrame,
    year: int = 2024,
) -> pd.DataFrame:
    """Transform raw GDP data into the engine's tidy format.

    Args:
        gdp_df: DataFrame returned from `download_world_bank_gdp_zip()`.
        iso_df: ISO mapping DataFrame from `download_iso_mapping()`.
        year: Observation year to extract.

    Returns:
        Tidy DataFrame with columns `country_iso`, `gdp_pc_usd_2015`,
        `observation_year` and `source_series`.
    """
    # Rename and uppercase the ISO‑3 codes.
    gdp_df = gdp_df.rename(columns={"Country Code": "iso3"})
    gdp_df["iso3"] = gdp_df["iso3"].str.upper()
    # Create a lookup dictionary for ISO‑3 → ISO‑2.
    iso_map = dict(zip(iso_df["alpha3"], iso_df["alpha2"]))
    gdp_df["country_iso"] = gdp_df["iso3"].map(iso_map)
    # Extract the year column as numeric.
    year_col = str(year)
    gdp_df["gdp_pc_usd_2015"] = pd.to_numeric(
        gdp_df.get(year_col), errors="coerce"
    )
    # Keep only rows with a valid ISO‑2 code and a positive GDP value.
    tidy_df = gdp_df[
        gdp_df["country_iso"].notnull()
        & (gdp_df["gdp_pc_usd_2015"] > 0)
    ].copy()
    tidy_df = tidy_df[["country_iso", "gdp_pc_usd_2015"]]
    tidy_df["observation_year"] = year
    tidy_df["source_series"] = "NY.GDP.PCAP.KD"
    # Ensure uppercase ISO‑2 codes.
    tidy_df["country_iso"] = tidy_df["country_iso"].str.upper()
    return tidy_df


def write_output(df: pd.DataFrame, year: int, output_dir: str = ".") -> str:
    """Write the tidy DataFrame to a CSV file.

    Args:
        df: DataFrame returned from `build_gdp_dataset()`.
        year: Observation year used in the file name.
        output_dir: Directory to write the CSV file to.

    Returns:
        The path to the written CSV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"world_bank_gdp_pc_{year}.csv"
    path = os.path.join(output_dir, filename)
    df.to_csv(path, index=False)
    return path


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Download and process World Bank GDP per capita (constant "
            "2015 USD) data for a specified year."
        )
    )
    parser.add_argument(
        "--year", type=int, default=2024, help="Observation year to extract"
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where the output CSV will be written",
    )
    parser.add_argument(
        "--iso-path",
        default="",
        help="Sealed ISO canonical file (CSV or Parquet) with column 'country_iso' "
             "(filters GDP to sealed universe and enforces coverage).",
    )
    parser.add_argument(
        "--coverage-policy",
        default="fail",
        choices=["fail", "none"],
        help="Coverage gate: 'fail' (default) aborts if any sealed ISO country is missing; "
             "'none' only warns.",
    )
    parser.add_argument(
        "--out-parquet",
        default="",
        help="Optional Parquet output path (writes alongside CSV if provided)",
    )
    parser.add_argument(
        "--out-manifest",
        default="",
        help="Optional path to write a manifest JSON with provenance (source, SHA-256, git/runtime, coverage).",
    )
    parser.add_argument(
        "--version",
        default="",
        help="Dataset version tag (e.g., v2024-12-31) for provenance.",
    )
    ## --source-url "https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.KD?downloadformat=csv"
    parser.add_argument(
        "--source-url",
        default="",
        help="Optional source URL/identifier (e.g., World Bank WDI export URL) for manifest.",
    )    
    args = parser.parse_args()
    # Download raw data.
    print("Downloading World Bank GDP data…")
    gdp_df, source_zip_sha256 = download_world_bank_gdp_zip()
    print("Downloading ISO mapping…")
    iso_df = download_iso_mapping()
    # Transform into tidy format.
    print(f"Building dataset for year {args.year}…")
    tidy_df = build_gdp_dataset(gdp_df, iso_df, year=args.year)

    # ---- Seal to ISO universe & coverage gate (177 or whatever is sealed) ----
    if args.iso_path:
        # Read sealed ISO (CSV or Parquet), expect a 'country_iso' column (ISO2).
        if args.iso_path.lower().endswith(".parquet"):
            try:
                import pyarrow.parquet as pq
                iso_tbl = pq.read_table(args.iso_path)
                iso_sealed = iso_tbl.to_pandas()
            except Exception as e:
                raise RuntimeError("pyarrow required to read Parquet ISO file") from e
        else:
            iso_sealed = pd.read_csv(args.iso_path, dtype=str, keep_default_na=False)
        if "country_iso" not in iso_sealed.columns:
            raise ValueError(f"Sealed ISO file missing 'country_iso': {args.iso_path}")
        # Optional: if tidy_df has country_alpha3 and ISO has alpha3, map alpha3 -> ISO2 to repair/normalise
        if "alpha3" in iso_sealed.columns and "country_alpha3" in tidy_df.columns:
            a3_map = (iso_sealed[["alpha3","country_iso"]]
                      .dropna()
                      .assign(alpha3=lambda d: d["alpha3"].str.upper()))
            tidy_df["country_alpha3"] = tidy_df["country_alpha3"].astype(str).str.upper()
            tidy_df = tidy_df.merge(a3_map.rename(columns={"country_iso":"_iso2_from_a3"}),
                                    how="left", left_on="country_alpha3", right_on="alpha3")
            # fill country_iso where empty or malformed using the map
            mask_fill = (~tidy_df["_iso2_from_a3"].isna()) & (~tidy_df["country_alpha3"].eq(""))
            tidy_df.loc[mask_fill, "country_iso"] = tidy_df.loc[mask_fill, "_iso2_from_a3"]
            tidy_df.drop(columns=[c for c in ["alpha3","_iso2_from_a3"] if c in tidy_df.columns], inplace=True)        
        iso_set = set(iso_sealed["country_iso"].astype(str).str.upper())

        # Uppercase tidy ISO2, filter to sealed set, and check coverage.
        tidy_df["country_iso"] = tidy_df["country_iso"].astype(str).str.upper()
        _pre_filter_set = set(tidy_df["country_iso"])
        extras_pre_filter = sorted(_pre_filter_set - iso_set)
        tidy_df = tidy_df[tidy_df["country_iso"].isin(iso_set)].copy()
        gdp_set = set(tidy_df["country_iso"])
        missing = sorted(iso_set - gdp_set)
        extras  = sorted(gdp_set - iso_set)
        if missing or extras:
            msg = (f"Coverage mismatch vs sealed ISO: sealed={len(iso_set)}, "
                   f"GDP kept={len(gdp_set)}, missing={len(missing)}, extras={len(extras)}; "
                   f"missing[:10]={missing[:10]} extras[:10]={extras[:10]}")
            if args.coverage_policy == "fail":
                raise ValueError(msg)
            else:
                print("[WARN]", msg)
    else:
        print("[WARN] --iso-path not provided; skipping sealed-universe coverage gate.")

    # Optional: strict ISO-2 regex guard
    assert tidy_df["country_iso"].str.match(r"^[A-Z]{2}$").all(), \
        "country_iso must be uppercase ISO-2"

    # Final sanity: uniqueness & deterministic order
    assert tidy_df["country_iso"].is_unique, "duplicate country_iso rows after sealing"
    assert tidy_df[["country_iso","observation_year"]].drop_duplicates().shape[0] == len(tidy_df), \
        "duplicate (country_iso, observation_year) pairs"
    tidy_df = tidy_df.sort_values(["country_iso"], kind="mergesort").reset_index(drop=True)

    # Write the result.
    output_path = write_output(tidy_df, args.year, args.output_dir)
    print(f"Wrote {len(tidy_df)} rows to {output_path}")

    # Optional Parquet publish (explicit dtypes)
    if args.out_parquet:
        try:
            import pyarrow as pa, pyarrow.parquet as pq
        except Exception as e:
            raise RuntimeError("pyarrow required to write Parquet (pip install pyarrow)") from e
        df_parq = tidy_df.copy()
        df_parq["country_iso"] = df_parq["country_iso"].astype("string")
        df_parq["source_series"] = df_parq["source_series"].astype("string")
        df_parq["observation_year"] = df_parq["observation_year"].astype("int16")
        df_parq["gdp_pc_usd_2015"] = df_parq["gdp_pc_usd_2015"].astype("float64")
        table = pa.Table.from_pandas(df_parq, preserve_index=False)
        pq.write_table(table, args.out_parquet)
        print(f"Wrote Parquet: {args.out_parquet}")

    # ---- Manifest (provenance) ----
    if args.out_manifest:
        # Gather coverage snapshot if ISO was provided
        try:
            sealed_size = len(iso_set)      # from coverage block
            kept_size   = len(tidy_df)
            missing_cnt = len(missing)
            extras_cnt  = len(extras)
            extras_pre_cnt = len(extras_pre_filter)
            extras_pre_examples = extras_pre_filter[:10]
            coverage_pct = round(100.0 * kept_size / max(1, sealed_size), 2)
        except NameError:
            sealed_size = kept_size = missing_cnt = extras_cnt = None
            extras_pre_cnt = None
            extras_pre_examples = None
            coverage_pct = None
        mf = {
            "dataset_id": "world_bank_gdp_pc_2024",
            "version": args.version,
            "source_url": args.source_url,
            "source_archive_sha256": source_zip_sha256,
            "source_archive_format": "zip",
            "sealed_iso_path": os.path.abspath(args.iso_path) if args.iso_path else "",
            "output_csv": os.path.abspath(output_path),
            "output_csv_sha256": _sha256(output_path),
            "output_parquet": os.path.abspath(args.out_parquet) if args.out_parquet else "",
            "output_parquet_sha256": _sha256(args.out_parquet) if args.out_parquet else "",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "generator_script": "scripts/world_bank_gdp_pc_2024.py",
            "generator_git_sha": _git_sha_short(),
            "runtime": {
                "python": sys.version.split()[0],
                "pandas": pd.__version__,
                "pyarrow": pa.__version__ if args.out_parquet else ""
            },
            "expect_series": "NY.GDP.PCAP.KD",
            "expect_year": int(args.year),
            "sealed_iso_size": sealed_size,
            "gdp_kept_rows": kept_size,
            "coverage_pct": coverage_pct,
            "missing_count": missing_cnt,
            "extras_count": extras_cnt,
            "extras_pre_filter_count": extras_pre_cnt,
            "extras_pre_filter_examples": extras_pre_examples
        }
        os.makedirs(os.path.dirname(args.out_manifest) or ".", exist_ok=True)
        with open(args.out_manifest, "w", encoding="utf-8") as f:
            json.dump(mf, f, indent=2, ensure_ascii=False)
        print("Wrote manifest:", args.out_manifest)


if __name__ == "__main__":
    main()
```

---

### 4. Final notes

* The World Bank’s indicator page also describes the series and provides the CC‑BY‑4.0 licence.
* The API call example shows the fields we rely on (`countryiso3code`, `date`, `value`).
* The ISO mapping file contains the necessary alpha‑2/alpha‑3 pairs for each country.

Following these steps with the provided links will let you reproduce the GDP‑per‑capita dataset exactly as needed for the ingestion stage. If you’d like help packaging the processing script or verifying coverage against your merchant list, let me know!

---

