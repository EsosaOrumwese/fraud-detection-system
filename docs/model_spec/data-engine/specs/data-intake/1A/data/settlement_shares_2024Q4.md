## Reason we're approximating this dataset
Here’s a concise defence of why we chose the GDP‑weighted approximation for the settlement‑shares table and why it’s a reasonable substitute for unavailable “true” settlement data:

* **No public granular data exists.** Cross‑border settlement flows are proprietary; even the IMF working paper on currency usage notes that the U.S. dollar accounted for about **40 %** of SWIFT cross‑border flows in 2021, with the euro and a handful of other currencies making up most of the remainder—but the underlying data are not publicly released.  In this vacuum, we need a principled proxy.

* **Legal‑tender lists are authoritative.** We based the country lists on credible sources: Investopedia’s catalogue of U.S. dollar jurisdictions, the EU’s official list of euro countries, travel‑ and finance‑reference sites for sterling, and WorldData or central‑bank pages for currencies like CHF, SEK, DKK, NOK, CAD, JPY, HKD, AUD, SGD and CNY.  This ensures we aren’t fabricating the country universe.

* **GDP weighting reflects economic heft.** In the absence of settlement volumes, it is reasonable to assume that a currency’s cross‑border settlement activity correlates with the economic size of its legal‑tender countries.  Large economies generate more trade, investment and remittance flows; they also dominate FX turnover.  Weighting by GDP (and falling back to population when GDP is missing) therefore produces a distribution in which the U.S. accounts for ~99 % of USD settlement, Germany and France dominate the euro, and micro‑states contribute only tiny fractions.  This mirrors the reality that big economies wield outsized influence in global finance.

* **It’s a prior, not a hard rule.** The settlement‑shares table is used downstream to allocate currency‑denominated flows among eligible settlement countries, but it does not determine **whether** a merchant can go cross‑border (that’s governed by policy) or **how many** foreign countries they get (that comes from S4’s ZTP).  A skewed prior will tilt flows toward larger economies, but it won’t change the set of admissible countries or the number of sites—so realism is preserved, and the risk of unintended bias is limited.

* **Known limitations are minor and tractable.** Some offshore financial hubs (e.g. British Virgin Islands, Gibraltar) punch above their GDP weight.  In our proxy they receive tiny shares, which understates their role in finance.  If your merchant universe includes such jurisdictions or you have domain expertise suggesting different weights, you can override the default shares for those cases.  Likewise, micro‑states with zero GDP values have been given effectively zero share; a population‑based weighting could be used to assign them small but non-zero fractions.

In sum, a GDP‑weighted proxy is the **best available option** given the lack of open settlement data.  It relies on verifiable legal‑tender lists, aligns weights with economic reality, and serves merely as a starting prior for the engine.  While it isn’t perfect, it’s unlikely to degrade the project’s quality, and it can be refined if more granular data or expert judgement becomes available.

---

## Step‑by‑step method for building the GDP‑weighted settlement‑shares table

### 1. Compile legal‑tender lists

1. Identify the currencies you need to cover (USD, EUR, GBP, CHF, SEK, DKK, NOK, CAD, JPY, HKD, AUD, SGD, CNY).
2. For each currency, find authoritative sources listing the countries/territories where it is the official currency:

   * **USD:** Investopedia’s list of U.S. territories and foreign nations using the dollar.
   * **EUR:** The EU’s [“Countries using the euro” page](https://european-union.europa.eu/institutions-law-budget/euro/countries-using-euro_en#:~:text=,95) for the 20 Eurozone members, plus the Euro article for microstates and unilateral adopters.
   * **GBP:** A travel resource listing the UK, its Crown dependencies, and certain overseas territories [source](https://everything-everywhere.com/british-pound/#:~:text=).
   * **CHF:** [WorldData](https://www.worlddata.info/currencies/chf-swiss-franc.php#:~:text=The%20Swiss%20franc%20was%20established,is%20devided%20into%20100%20Rappen) noting that only Switzerland and Liechtenstein use the Swiss franc.
   * **SEK:** [WorldData](https://www.worlddata.info/currencies/sek-swedish-krona.php#:~:text=The%20Swedish%20Krona) stating the Swedish krona is used only in Sweden.
   * **DKK:** [WorldData](https://www.worlddata.info/currencies/dkk-danish-krone.php#:~:text=Distribution%20of%20the%20Danish%20krone) for Denmark and Greenland plus other sources confirming the Faroe Islands also use the Danish krone. [1](https://www.ceifx.com/news/5-currency-facts-you-probably-didnt-know-about-the-danish-krone#:~:text=Not%20only%20the%20official%20currency,Greenland%20and%20the%20Faroe%20Islands), [2](https://wise.com/us/currency-converter/currencies/dkk-danish-krone)
   * **NOK:** [Investopedia](https://www.investopedia.com/terms/n/nok.asp#:~:text=The%20Norwegian%20krone%20,regulated%20by%20the%20Norges%20Bank) confirming the Norwegian krone is Norway’s sole currency.
   * **CAD:** [WorldData](https://www.worlddata.info/currencies/cad-canadian-dollar.php#:~:text=The%20Canadian%20Dollar) stating the Canadian dollar is used only in Canada.
   * **JPY:** [WorldData](https://www.worlddata.info/currencies/jpy-japanese-yen.php#:~:text=The%20Japanese%20Yen) stating the yen is used only in Japan.
   * **HKD:** [Oanda](https://www.oanda.com/currency-converter/en/currencies/majors/hkd/#:~:text=Introduced%20in%201863%2C%20the%20Hong,patacan%20is%20pegged%20to%20HKD) noting that the Hong Kong dollar is used in Hong Kong and Macau.
   * **AUD:** [Oanda](https://www.oanda.com/currency-converter/en/currencies/majors/aud/#:~:text=Established%20in%201966%2C%20the%20Australian,traded%20currency%20in%20the%20world) listing Australia and several Pacific islands/territories for the Australian dollar.
   * **SGD:** [WorldData](https://www.worlddata.info/currencies/sgd-singapore-dollar.php#:~:text=The%20Singapore%20Dollar) noting the Singapore dollar is used in Singapore; the [MAS](https://www.mas.gov.sg/currency/brunei-singapore-currency-interchangeability-agreement) explains the Brunei dollar and Singapore dollar are interchangeable.
   * **CNY:** The renminbi is legal tender only in China, though it circulates informally in neighbors.
3. From these sources, compile a mapping of `ccy_alpha3 → [ISO‑2 country codes]`.

### 2. Prepare ISO code lookup

1. Load your canonical ISO‑3166 table (for example, `iso3166_canonical_2024.csv`) containing alpha‑2 and alpha‑3 codes.
2. Create a dictionary mapping alpha‑2 to alpha‑3 codes.  The World Bank API uses ISO‑3 codes for country identifiers.

### 3. Fetch proxy data (GDP and population)

1. For each currency’s country list:

   * Convert each alpha‑2 code to alpha‑3.
   * Use the World Bank API to fetch **GDP (current US$)**: indicator `NY.GDP.MKTP.CD` for year 2024.
   * If GDP is missing, fall back to **Population**: indicator `SP.POP.TOTL` for the same year.
   * Example API call: `https://api.worldbank.org/v2/country/USA/indicator/NY.GDP.MKTP.CD?format=json&per_page=100`.
2. Record the numeric value (GDP or population) for each country.

### 4. Compute per‑currency weights

1. For each currency ( c ), sum the proxy values across its countries: ( S_c = \sum_{i} P_i ).
2. Compute each country’s share: ( \text{share}_{c,i} = P_i / S_c ) (use zero if ( S_c ) is zero).
3. Round shares to **six decimals**.
4. Create rows with columns:

   * `ccy_alpha3`
   * `country_iso` (alpha‑2)
   * `share`
   * `obs_count` (set to 1 because we used a single proxy source per row).
5. Verify that the shares for each currency sum to 1 (allow a small rounding error).

### 5. Assemble and save the dataset

1. Combine all rows into a single CSV or DataFrame.
2. Save the file as `settlement_shares_2024Q4_gdp_weighted.csv` (or a similar name).
3. Optionally, compute a hash and record the date/time to track provenance.

### 6. Validate against the ingestion schema

1. Ensure the CSV has exactly the four required columns: `ccy_alpha3`, `country_iso`, `share`, `obs_count`.
2. Check that `country_iso` codes are uppercase and present in your canonical ISO table.
3. Ensure each currency’s shares sum to 1 with tolerance **≤ 10^(-dp)** (e.g., dp=8 ⇒ tolerance ≤ 1e-8).
4. Confirm that the dataset covers every currency used in your merchant universe; add missing ones if needed.
5. **Sealed currency universe (this run):** enforce that all merchant `settlement_currency` values lie in a governed `shares_currency_universe` list (sealed in S0) and that every currency in this list has a share vector here. If a merchant currency is not covered, apply the governed **fallback** (see §9) or fail fast (policy).
6. **Epsilon floor (optional):** after normalization, apply a tiny floor (e.g., `1e-6`) to non-zero entries then **renormalize** within each currency to avoid unintended hard zeros; serialize `share` as fixed-dp strings (e.g., dp=8) to prevent float drift when S3 writes priors.

### 7. Iterate as better data becomes available

* If you obtain more granular data (e.g., trade invoicing shares or SWIFT settlement shares), replace or blend the proxy values accordingly.
* You can also experiment with **population‑based weighting** by substituting `SP.POP.TOTL` for `NY.GDP.MKTP.CD` in step 3.

### 8. Example Python outline (for automation)

If you wish to automate the above steps, here is a simplified code outline:

```python
import pandas as pd
import requests

# Load ISO mapping
iso_df = pd.read_csv('iso3166_canonical_2024.csv')
iso2_to_iso3 = dict(zip(iso_df['country_iso'], iso_df['alpha3']))

# Define currency→country list based on the sources above
currency_countries = {
    'USD': ['US','PR','GU','AS','MP','VI','TC','VG','EC','SV','TL','FM','PW','MH','BQ'],
    # … other currencies …
}

def get_value(iso3, indicator, year):
    url = f'https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}?format=json&per_page=100'
    data = requests.get(url).json()
    if len(data) > 1 and data[1]:
        for entry in data[1]:
            if entry['date'] == str(year):
                return entry['value']
    return None

shares_currency_universe = set([ "GBP","EUR","USD","SGD","AUD","CHF","DKK","SEK","NOK","JPY","CAD","HKD","CNY" ])  # sealed in S0 (example)

rows = []
for currency, iso2_list in currency_countries.items():
    if shares_currency_universe and currency not in shares_currency_universe:
        continue  # skip currencies outside the sealed universe for this run
    proxies = []
    tmp = []
    for iso2 in iso2_list:
        iso3 = iso2_to_iso3.get(iso2)
        val = get_value(iso3, 'NY.GDP.MKTP.CD', 2024)
        if not val:
            val = get_value(iso3, 'SP.POP.TOTL', 2024)
        proxies.append(val or 0)
        tmp.append((iso2, val or 0))
    total = sum(proxies)
    # Optional fallback + epsilon floor to avoid hard zeros
    if total == 0 and proxies:
        # fallback: uniform over the legal-tender set (document if you choose a different policy)
        proxies = [1.0/len(proxies)] * len(proxies)
        total = 1.0
    floor = 1e-6
    adj = [(p if p > 0 else 0.0) for p in proxies]
    # apply floor only where p>0 to preserve intentional zeroes, then renormalize
    adj = [max(p, floor) if p > 0 else 0.0 for p in adj]
    s = sum(adj)
    shares_vec = [(p/s if s > 0 else 0.0) for p in adj]
    for (iso2, _val), share in zip(tmp, shares_vec):
        rows.append({'currency': currency,
                     'country_iso': iso2,
                     'share': round(share, 6),
                     'obs_count': 1})

df = pd.DataFrame(rows)
df.to_csv('settlement_shares_2024Q4_gdp_weighted.csv', index=False)
```

This script encapsulates steps 2–5: it loads the ISO mapping, looks up GDP (or population) values, computes weights, and writes the CSV.

### 9. Sealed currency universe & fallback (this run)

For this project we constrain to a sealed set of currencies (e.g., `["GBP","EUR","USD","SGD","AUD","CHF","DKK","SEK","NOK","JPY","CAD","HKD","CNY"]`).
This list (`shares_currency_universe`) is sealed in S0 and referenced by S3.

**Policy:**
* If a merchant’s `settlement_currency ∉ shares_currency_universe` → either **fail** or apply a governed **fallback**: `uniform` over legal-tender set, or `GDP-weighted` (same method as above), or a small **home-biased uniform** (documented).
* In S3, left-join priors to candidates; when a currency is missing, apply the fallback **on the candidate set** and **renormalize**.
* Record the chosen fallback + currency coverage in the shares manifest for provenance.

---

### 10. CLI wrapper (drop-in)

The outline above can be wrapped in a small CLI so this dataset behaves like ISO/GDP/IDs.

```python
#!/usr/bin/env python3
import argparse, json, os, sys, hashlib
from datetime import datetime, timezone
import pandas as pd
try:
    import pyarrow as pa, pyarrow.parquet as pq
except Exception:
    pa = pq = None

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(1<<20), b""): h.update(ch)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description="Build Settlement Shares 2024Q4")
    ap.add_argument("--iso-path", required=True, help="Sealed ISO table (CSV/Parquet) with country_iso")
    ap.add_argument("--currency-universe", required=True, help="Text/CSV with one ISO-4217 per line used in this run")
    ap.add_argument("--out-parquet", required=True, help="Parquet path for {currency,country_iso,share,obs_count}")
    ap.add_argument("--out-manifest", required=True, help="Manifest JSON path")
    ap.add_argument("--dp", type=int, default=8, help="Fixed decimal places for shares (default 8)")
    ap.add_argument("--epsilon-floor", type=float, default=1e-6, help="Floor for non-zero shares before renorm")
    ap.add_argument("--coverage-policy", choices=["fail","none"], default="fail",
                    help="fail (default) or warn if a required currency has no vector")
    ap.add_argument("--overrides-csv", default="", help="Optional CSV {ccy_alpha3,country_iso,delta} to tweak weights")
    args = ap.parse_args()

    # 1) Load inputs
    iso = (pd.read_parquet(args.iso_path) if args.iso_path.lower().endswith(".parquet")
           else pd.read_csv(args.iso_path, dtype=str, keep_default_na=False))
    iso_set = set(iso["country_iso"].astype(str).str.upper())
    with open(args.currency_universe, "r", encoding="utf-8") as f:
        currency_universe = [ln.strip().upper() for ln in f if ln.strip()]

    # 2) Build legal-tender map and GDP/POP lookups (per your outline sections 3–5)
    #    legal_tender: dict[str, list[str]], gdp_map: dict[ISO2->float], pop_map: dict[ISO2->float]
    #    (Reuse your existing helper snippets; omitted here for brevity.)

    # 3) Compute shares (GDP primary, POP fallback) with epsilon floor and renormalize
    rows = []
    for ccy in currency_universe:
        countries = legal_tender.get(ccy, [])
        if not countries:
            msg = f"No legal-tender list for {ccy}"
            if args.coverage_policy == "fail": raise ValueError(msg)
            else: print("[WARN]", msg, file=sys.stderr); continue

        # keep only sealed ISO countries
        countries = [x.upper() for x in countries if x.upper() in iso_set]
        proxies = []
        for iso2 in countries:
            v = gdp_map.get(iso2) or pop_map.get(iso2) or 0.0
            proxies.append(max(v, 0.0))
        total = sum(proxies)
        if total == 0.0:
            # uniform fallback
            proxies = [1.0/len(countries) for _ in countries]
            total = 1.0
        # epsilon floor for nonzero entries, then renormalize
        eps = args.epsilon_floor
        adj = [max(p, eps) if p>0 else 0.0 for p in proxies]
        s = sum(adj)
        shares = [(p/s if s>0 else 0.0) for p in adj]

        # apply overrides (optional)
        # If --overrides-csv provided, expect columns: ccy_alpha3,country_iso,delta
        if args.overrides_csv:
            ov = pd.read_csv(args.overrides_csv, dtype=str, keep_default_na=False)
            ov["ccy_alpha3"] = ov["ccy_alpha3"].str.upper()
            ov["country_iso"] = ov["country_iso"].str.upper()
            # build a delta map for this currency
            deltas = {row["country_iso"]: float(row["delta"])
                      for _, row in ov[ov["ccy_alpha3"]==ccy].iterrows()}
            # add deltas, clip at >=0, then renormalize
            adj2 = []
            for iso2, p in zip(countries, shares):
                p2 = max(p + deltas.get(iso2, 0.0), 0.0)
                adj2.append(p2)
            s2 = sum(adj2)
            shares = [(p/s2 if s2>0 else 0.0) for p in adj2]

        for iso2, sh in zip(countries, shares):
            rows.append({"ccy_alpha3": ccy,
                         "country_iso": iso2,
                         "share": f"{sh:.{args.dp}f}",
                         "obs_count": 1})

    out = pd.DataFrame(rows, columns=["ccy_alpha3","country_iso","share","obs_count"])
    # FK and group-sum checks
    assert out["country_iso"].str.match(r"^[A-Z]{2}$").all()
    for ccy, grp in out.groupby("ccy_alpha3"):
        s = grp["share"].astype(float).sum()
        assert abs(s - 1.0) <= 10**(-args.dp), f"group sum != 1 for {ccy}: {s}"

    # 4) Write Parquet with explicit types
    if pa is None or pq is None: raise RuntimeError("pyarrow required: pip install pyarrow")
    out["ccy_alpha3"] = out["ccy_alpha3"].astype("string")
    out["country_iso"] = out["country_iso"].astype("string")
    out["share"] = out["share"].astype("string")  # fixed-dp strings
    out["obs_count"] = out["obs_count"].astype("int32")
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), args.out_parquet)

    # 5) Manifest
    os.makedirs(os.path.dirname(args.out_manifest) or ".", exist_ok=True)
    produced_currencies = sorted(out["ccy_alpha3"].unique().tolist())
    man = {
        "dataset_id": "settlement_shares_2024Q4",
        "sealed_currency_universe": currency_universe,
        "sealed_iso_path": os.path.abspath(args.iso_path),
        "output_parquet": os.path.abspath(args.out_parquet),
        "output_parquet_sha256": _sha256(args.out_parquet),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": sys.version.split()[0], "pandas": pd.__version__,
                    "pyarrow": pa.__version__},
        "dp": args.dp, "epsilon_floor": args.epsilon_floor,
        "coverage_policy": args.coverage_policy,
        "produced_currencies": produced_currencies,
        "produced_currency_count": len(produced_currencies)
    }
    with open(args.out_manifest, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, ensure_ascii=False)
    print("[DONE] shares →", args.out_parquet, "manifest →", args.out_manifest)

if __name__ == "__main__":
    main()
```

---

### 11. Bulk WDI download & caching (faster, reproducible)

To avoid many per-country API calls, fetch **bulk CSV/ZIP** once per indicator and cache it with a SHA-256.

*Indicators (2024):*  
- GDP (current US$): `NY.GDP.MKTP.CD` (or GDP per capita if you prefer)  
- Population: `SP.POP.TOTL`

*Steps:*  
1) Download bulk ZIP(s) for the indicator(s) and year into `cache/wdi/` and log their SHA-256.  
2) Extract the country-level CSV, build a dict `{ISO2 → value}` for 2024, and reuse across runs until the ZIP changes.  
3) Keep the ZIP SHA(s) in your **shares manifest** for full provenance.

```python
import io, zipfile, requests, hashlib, os, pandas as pd

def fetch_wdi_zip(indicator: str, cache_dir="cache/wdi"):
    os.makedirs(cache_dir, exist_ok=True)
    url = f"https://api.worldbank.org/v2/en/indicator/{indicator}?downloadformat=csv"
    r = requests.get(url, stream=True); r.raise_for_status()
    zbytes = r.content; sha = hashlib.sha256(zbytes).hexdigest()
    zip_path = os.path.join(cache_dir, f"{indicator}-{sha[:12]}.zip")
    if not os.path.exists(zip_path):
        with open(zip_path, "wb") as f: f.write(zbytes)
    zf = zipfile.ZipFile(io.BytesIO(zbytes))
    # find country data file (World Bank names it like: API_{indicator}_..._Data.csv)
    name = [n for n in zf.namelist() if n.endswith("_Data.csv")][0]
    df = pd.read_csv(zf.open(name), dtype=str, keep_default_na=False)
    return df, sha
```

This lets your shares build be **fast and replayable** with exact input hashes in the manifest.