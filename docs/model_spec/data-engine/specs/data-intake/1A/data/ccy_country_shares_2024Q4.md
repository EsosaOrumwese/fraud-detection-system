Below is a reproducible blueprint for how the **currency_country_shares_2024Q4.csv** file was created.  It describes the data sources, decisions made, and the exact steps needed to rebuild the dataset yourself.  The approach uses a GDP‑weighted proxy because there is no publicly downloadable dataset giving currency‑usage shares by country.  Each currency’s share is distributed over its legal‑tender countries in proportion to their economic size (or population when GDP is missing).  Should more granular invoicing or payment‑flow data become available, you can replace the proxy weights in Step 3.

---

## 1. Identify legal‑tender countries per currency

1. **List the currencies present in the engine’s settlement‑shares dataset**, which include USD, EUR, GBP, CHF, SEK, DKK, NOK, CAD, JPY, HKD, AUD, SGD and CNY.
2. **Compile a list of countries/territories where each currency is legal tender**, using authoritative sources:

   * *USD:* U.S. territories and dollarized nations such as Puerto Rico, Guam, El Salvador and Ecuador.
   * *EUR:* The 20 Eurozone members plus Andorra, Monaco, San Marino, Vatican City, Kosovo and Montenegro. [1](https://european-union.europa.eu/institutions-law-budget/euro/countries-using-euro_en#:~:text=,95)[,2](https://en.wikipedia.org/wiki/Euro#:~:text=The%2020%20participating%20members%20are%3A)
   * *GBP:* UK and its Crown dependencies and overseas territories (e.g., Jersey, Guernsey, Falkland Islands, Gibraltar). [3](https://everything-everywhere.com/british-pound/#:~:text=)
   * *CHF:* Switzerland and Liechtenstein. [4](https://www.worlddata.info/currencies/chf-swiss-franc.php#:~:text=The%20Swiss%20franc%20was%20established,is%20devided%20into%20100%20Rappen)
   * *SEK:* Sweden only. [5](https://www.worlddata.info/currencies/sek-swedish-krona.php#:~:text=The%20Swedish%20Krona)
   * *DKK:* Denmark and Greenland; sources also show the Faroe Islands use DKK. [6](https://www.worlddata.info/currencies/dkk-danish-krone.php#:~:text=Distribution%20of%20the%20Danish%20krone)[,7](https://www.ceifx.com/news/5-currency-facts-you-probably-didnt-know-about-the-danish-krone#:~:text=Not%20only%20the%20official%20currency,Greenland%20and%20the%20Faroe%20Islands)
   * *NOK:* Norway. [8](https://www.investopedia.com/terms/n/nok.asp#:~:text=The%20Norwegian%20krone%20,regulated%20by%20the%20Norges%20Bank)
   * *CAD:* Canada. [9](https://www.worlddata.info/currencies/cad-canadian-dollar.php#:~:text=The%20Canadian%20Dollar)
   * *JPY:* Japan. [10](https://www.worlddata.info/currencies/jpy-japanese-yen.php#:~:text=The%20Japanese%20Yen)
   * *HKD:* Hong Kong and Macau. [11](https://www.oanda.com/currency-converter/en/currencies/majors/hkd/#:~:text=Introduced%20in%201863%2C%20the%20Hong,patacan%20is%20pegged%20to%20HKD)
   * *AUD:* Australia plus Christmas Island, Cocos Islands, Norfolk Island, Nauru, Tuvalu and Kiribati. [12](https://www.oanda.com/currency-converter/en/currencies/majors/aud/#:~:text=Established%20in%201966%2C%20the%20Australian,traded%20currency%20in%20the%20world)
   * *SGD:* Singapore (and, by treaty, interchangeable with Brunei’s currency). [13](https://www.worlddata.info/currencies/sgd-singapore-dollar.php#:~:text=The%20Singapore%20Dollar)[,14](https://www.mas.gov.sg/currency/brunei-singapore-currency-interchangeability-agreement)
   * *CNY:* Only China officially uses the renminbi; it circulates informally in some neighbours.
3. **Map each two‑letter ISO country code to its three‑letter ISO‑3 code** using your canonical ISO table (e.g., iso3166_canonical_2024).  This is needed for World Bank API queries.

---

## 2. Gather proxy data for weighting

1. **Use the World Bank API** to fetch each legal‑tender country’s 2024 **GDP in current USD** (indicator `NY.GDP.MKTP.CD`).

   * Example call:

     ```
     https://api.worldbank.org/v2/country/USA/indicator/NY.GDP.MKTP.CD?format=json&per_page=100
     ```
   * Extract the 2024 `value`.
2. **Fallback to population** (`SP.POP.TOTL`) if GDP is missing for a country.
3. Record each country’s proxy value (P_i) and the currency it belongs to.

---

## 3. Compute per‑currency shares

For each currency (c):

1. Let (C_c) be the set of legal‑tender countries from Step 1.
2. Compute the total proxy weight
   $$
   S_c = \sum_{i \in C_c} P_i.
   $$
3. For each country (i) in (C_c), compute its share
   $$
   \text{share}_{c,i} = \frac{P_i}{S_c}.
   $$
   If (S_c = 0), set all shares to zero.
4. **Round** each share to six decimal places to match engine precision.
5. Set `obs_count = 1` for all rows (indicating one data source per row).

---

## 4. Build the CSV

1. Create a table with columns **(exact)**: `currency`, `country_iso`, `share`, `obs_count`  — **PK**: (`currency`,`country_iso`).
2. For each currency $c$ and country $i \in C_c$, add a row:

   ```
   currency      country_iso   share       obs_count
   USD           US            0.987654    1
   USD           EC            0.005123    1
   …             …             …           …
   ```
3. Ensure rows are unique on (`currency`,`country_iso`).  
4. Domain & FK:  
   - `currency` matches `^[A-Z]{3}$` (ISO-4217 alpha-3)  
   - `country_iso` matches `^[A-Z]{2}$` (ISO-3166 alpha-2) and **FK → sealed ISO** (`iso3166_canonical_2024.country_iso`)  
5. Per-currency sum: **Σ share = 1.0** with tolerance **≤ 10^(−dp)** (tie this to the rounding precision you use for `share`, e.g., dp=8 ⇒ 1e-8).
6. Save the file as `ccy_country_shares_2024Q4.csv`.

---

## 5. Practical script outline (Python example)

Here is a simplified Python outline (you can run it outside this environment) to reproduce the dataset:

```python
import pandas as pd
import requests

# ISO mapping
iso_df = pd.read_csv('iso3166_canonical_2024.csv')  # includes country_iso and alpha3
iso2_to_iso3 = dict(zip(iso_df['country_iso'], iso_df['alpha3']))

# Define legal-tender countries per currency (from Step 1)
currency_countries = {
    'USD': ['US','PR','GU','AS','MP','VI','TC','VG','EC','SV','TL','FM','PW','MH','BQ'],
    'EUR': [ … ],
    …
}

def get_indicator(iso3, indicator):
    url = f'https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}?format=json&per_page=100'
    data = requests.get(url).json()
    for entry in data[1]:
        if entry['date'] == '2024':
            return entry['value']
    return None

rows = []
dp = 8          # fixed-dp for share strings; Σ tolerance uses 10^(−dp)
epsilon = 1e-6  # floor for non-zero entries; avoids brittle hard-zeros
for currency, iso2_list in currency_countries.items():
    proxies = []
    temp = []
    for iso2 in iso2_list:
        iso3 = iso2_to_iso3[iso2]
        gdp = get_indicator(iso3, 'NY.GDP.MKTP.CD')
        if gdp is None:
            gdp = get_indicator(iso3, 'SP.POP.TOTL')
        proxies.append(gdp or 0)
        temp.append((iso2, gdp or 0))
    total = sum(proxies)
    if total == 0.0 and proxies:
        # governed fallback: uniform over the legal-tender set
        proxies = [1.0/len(proxies) for _ in proxies]
        total = 1.0
    # epsilon floor for non-zeros then renormalize
    adj = [max(p, epsilon) if p>0 else 0.0 for p in proxies]
    s = sum(adj)
    shares = [(p/s if s>0 else 0.0) for p in adj]
    for (iso2, _value), share in zip(temp, shares):
        rows.append({
            'currency': currency,
            'country_iso': iso2,
            'share': f"{share:.{dp}f}",  # fixed-dp base-10 string
            'obs_count': 1
        })

df = pd.DataFrame(rows, columns=['currency','country_iso','share','obs_count'])
# Regex & FK checks
assert df['currency'].str.match(r'^[A-Z]{3}$').all(), "bad ISO-4217 in currency"
assert df['country_iso'].str.match(r'^[A-Z]{2}$').all(), "bad ISO-3166 in country_iso"
assert set(df['country_iso']).issubset(set(iso_df['country_iso'].str.upper())), "FK→ISO failed"
# Σ=1 per currency at dp tolerance
assert (df.groupby('currency')['share'].astype(float).sum().sub(1.0).abs()
        .le(10**(-dp))).all(), "Σ share != 1 within 10^(−dp)"
# Deterministic order then write
df = df.sort_values(['currency','country_iso'], kind='mergesort').reset_index(drop=True)
df.to_csv('ccy_country_shares_2024Q4.csv', index=False)
```

Replace the `currency_countries` lists with the legal‑tender country codes you compiled.

### CLI wrapper (drop-in, parity with other gathers)

```python
#!/usr/bin/env python3
import argparse, json, os, sys, hashlib
from datetime import datetime, timezone
import pandas as pd
try:
    import pyarrow as pa, pyarrow.parquet as pq
except Exception:
    pa = pq = None

def _sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1<<20), b""): h.update(ch)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description="Build CCY→Country Shares 2024Q4")
    ap.add_argument("--iso-path", required=True, help="Sealed ISO table (CSV/Parquet) with country_iso")
    ap.add_argument("--currency-universe", required=True, help="File with one ISO-4217 per line (sealed for this run)")
    ap.add_argument("--out-parquet", required=True, help="Parquet path for {currency,country_iso,share,obs_count}")
    ap.add_argument("--out-manifest", required=True, help="Manifest JSON path")
    ap.add_argument("--dp", type=int, default=8, help="Fixed decimals for shares (default 8)")
    ap.add_argument("--epsilon-floor", type=float, default=1e-6, help="Floor for non-zero shares then renorm")
    ap.add_argument("--coverage-policy", choices=["fail","none"], default="fail",
                    help="fail (default) or warn if produced currencies != sealed set")
    ap.add_argument("--overrides-csv", default="", help="Optional CSV {currency,country_iso,delta}")
    args = ap.parse_args()
    # Build the 'out' DataFrame exactly as in the outline above (same logic):
    #   - legal_tender_map  : dict[currency -> list[ISO2]]
    #   - gdp_2024, pop_2024: dict[ISO2 -> float]
    #   - generate rows: {currency,country_iso,share=f"{sh:.{args.dp}f}",obs_count=1}
    #
    # For parity with the rest of the pipeline, we now seal coverage, write Parquet, and emit a manifest.

    # 1) Load sealed currency universe (list of ISO-4217 codes, one per line)
    with open(args.currency_universe, "r", encoding="utf-8") as f:
        currency_universe = [ln.strip().upper() for ln in f if ln.strip()]

    # 2) OUT: DataFrame constructed per the outline (paste/import your outline code above this point)
    #    Expected schema: ["currency","country_iso","share","obs_count"]
    #    The name 'out' must refer to that final DataFrame.
    #    Example final line in the outline:
    #    out = pd.DataFrame(rows, columns=["currency","country_iso","share","obs_count"])

    # 3) Coverage parity: produced currencies must match the sealed set
    produced_currencies = sorted(out["currency"].unique().tolist())
    if set(produced_currencies) != set(currency_universe):
        extra   = sorted(set(produced_currencies) - set(currency_universe))
        missing = sorted(set(currency_universe) - set(produced_currencies))
        msg = f"produced != sealed: extra={extra} missing={missing}"
        if args.coverage_policy == "fail":
            raise ValueError(msg)
        else:
            print("[WARN]", msg, file=sys.stderr)

    # 4) Deterministic Parquet write with explicit dtypes
    if pa is None or pq is None:
        raise RuntimeError("pyarrow required to write Parquet (pip install pyarrow)")
    out = out.sort_values(["currency","country_iso"], kind="mergesort").reset_index(drop=True)
    out["currency"]    = out["currency"].astype("string")
    out["country_iso"] = out["country_iso"].astype("string")
    out["share"]       = out["share"].astype("string")   # fixed-dp strings (dp = args.dp)
    out["obs_count"]   = out["obs_count"].astype("int32")
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), args.out_parquet)

    # 5) Manifest with overrides provenance (if used)
    ov_path = os.path.abspath(args.overrides_csv) if args.overrides_csv else ""
    ov_sha  = _sha256(ov_path) if args.overrides_csv else ""
    man = {
        "dataset_id": "ccy_country_shares_2024Q4",
        "sealed_currency_universe": currency_universe,
        "currency_universe_path": os.path.abspath(args.currency_universe),
        "currency_universe_sha256": _sha256(args.currency_universe),
        "sealed_iso_path": os.path.abspath(args.iso_path),
        "output_parquet": os.path.abspath(args.out_parquet),
        "output_parquet_sha256": _sha256(args.out_parquet),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "pyarrow": pa.__version__
        },
        "dp": args.dp,
        "epsilon_floor": args.epsilon_floor,
        "coverage_policy": args.coverage_policy,
        "overrides_csv_path": ov_path,
        "overrides_csv_sha256": ov_sha,
        "produced_currencies": produced_currencies,
        "produced_currency_count": len(produced_currencies)
    }
    os.makedirs(os.path.dirname(args.out_manifest) or ".", exist_ok=True)
    with open(args.out_manifest, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, ensure_ascii=False)
    print("[DONE] shares →", args.out_parquet, "manifest →", args.out_manifest)
```

---

## 6. Limitations and future improvements

* This dataset is a **proxy**; shares reflect economic size, not actual trade or invoicing volumes.  Per‑country currency usage data are confidential or proprietary, as the IMF’s COFER dataset only publishes aggregate reserves. [15](https://data.imf.org/en/datasets/IMF.STA:COFER)
* Where partial data exist (e.g. [Eurostat’s invoicing shares](https://ec.europa.eu/eurostat/databrowser/view/ext_lt_invcur__custom_16975589/default/table) or [UK trade tables](https://www.gov.uk/government/statistics/uk-trade-in-goods-by-declared-currency-of-invoice-2024/uk-trade-in-goods-by-declared-currency-of-invoice-2024#:~:text=27,the%20declared%20currency%20of%20invoice)), you could use those figures instead of GDP weights for the relevant countries. 
* If you gain access to the ECB/IMF [“Patterns of Invoicing Currency” dataset (132 countries, 1990–2023)](https://www.ecb.europa.eu/press/other-publications/ire/article/html/ecb.ireart202506_02~a8e66f5ea3.en.html#:~:text=ECB%20and%20IMF%20staff%20have,euro%2C%20renminbi%20and%20other%20currencies), you can replace the proxies with the empirical shares for currencies covered there.

---