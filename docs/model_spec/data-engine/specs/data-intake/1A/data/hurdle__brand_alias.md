# What information is in `brand_alias`

# What we’re building (deliverables)

1. **`brands.parquet`** — 1 row per brand:
   `brand_id` (opaque), `brand_name` (display), `brand_slug` (normalized), `website_domain?`, `wikidata_qid?`, `status`, timestamps, `sources[]`.
2. **`brand_aliases.parquet`** — many-to-one aliases → brand_id:
   `alias`, `alias_norm`, `alias_type` (`poi_name|store_locator|wikidata_label|aka|legal|auto_variant`), `country_iso?`, `confidence`, `source`.
3. **`overrides.brand_aliases.yaml`** — small manual map for ambiguous or conflicting cases.
4. **`t0_manifest.json`** — inputs, digests, counts, coverage, collision report (for reproducibility).

> These are the only things T1–T3 (and ultimately the fits) require.

---

# Sources you can actually scrape (priority = legality + coverage + stability)

**Tier 1 — Open & structured (use first):**

* **Wikidata** (CC0): canonical label, **aliases** in many languages, **official website (domain)**, QID.
  *Why:* best free canonical + alias bundle; stable IDs for reconciliation.
* **Wikipedia** (CC-BY-SA) infobox + redirect titles: legal/AKA names, country scoping.
  *Why:* supplement for aliases in local languages; redirects often capture common nicknames.

**Tier 2 — OpenStreetMap (ODbL) via Overpass API:**

* Pull top brands per **category** (amenity/shop) and **country** using tags: `brand`, `brand:wikidata`, `operator`, `name`.
  *Why:* gives you **real-world presence counts** by brand—perfect for *prioritizing* which brands to include (coverage-first), and additional alias strings from POIs.

**Tier 3 — Official store locators (brand websites):**

* Most big chains expose store JSON endpoints (look for: `/stores`, `/locations`, `/api/locator`, `/sitemap.xml` pointing to store pages).
  *Why:* verifies **canonical name** and confirms **website domain** (a strong reconciliation signal).
  *Reminder:* obey robots.txt; use polite rate limits.

**Tier 4 — Corporate registers (evidence only):**

* Legal names from Companies House (UK), SEC EDGAR (US), OpenCorporates.
  *Why:* add “legal_name” as **low-priority** aliases; not used to form brand_slug.

> With **Tier 1 + Tier 2** you can bootstrap a strong registry; **Tier 3** is for confirmatory domain evidence; **Tier 4** is icing.

---

# Building branch alias

Brilliant—here’s a **single-file CLI** that bundles the whole **T0 Canonical Brand Registry** pipeline, driven by your **ISO** and **MCC** authorities. It includes subcommands to hunt Wikidata/OSM, build the canonical registry + aliases, reconcile with overrides, run QA/coverage, and publish with a manifest + gate hash.

* No hand-picked country/category lists in code—**everything** comes from:

  * `run_scope.yaml` (points to your **ISO parquet** and lists your run’s ISO subset)
  * `mcc_category_map.yaml` (governed **MCC→OSM/Wikidata mapping**)

---

## 0) Install (one-time)

```bash
python -m venv .venv && . .venv/bin/activate
pip install --upgrade pip
pip install pandas pyarrow pyyaml requests
# optional (for fuzzy ranking in reconcile; you can skip it):
pip install rapidfuzz
```

---

## 1) Config files you’ll need

### `run_scope.yaml`

```yaml
iso_parquet: "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet"
iso_filter:  # run universe (subset of your sealed ISO table)
  - GB
  - DE
  - FR
  - NL
  - BE
  - IE
  - ES
  - IT
  - PT
  - US
mcc_master: "reference/mcc/mcc_master.csv"   # not used directly here but good to keep
```

### `mcc_category_map.yaml`

```yaml
mcc_groups:
  "5411":
    osm: [{shop: supermarket}, {shop: convenience}]
    wikidata_classes: [Q180846, Q81931]
  "5812":
    osm: [{amenity: restaurant}]
    wikidata_classes: [Q57121505]
  "5814":
    osm: [{amenity: fast_food}]
    wikidata_classes: [Q1778821]
  "5541":
    osm: [{amenity: fuel}]
    wikidata_classes: [Q131734]
  "5912":
    osm: [{shop: pharmacy}, {amenity: pharmacy}]
    wikidata_classes: [Q43413524]
  "5732":
    osm: [{shop: electronics}]
    wikidata_classes: [Q740601]
```

### (Optional) `overrides.brand_aliases.yaml`

```yaml
# If an alias_norm collides across brands, force a decision here:
# - alias_norm: "tesco"
#   country_iso: null
#   force_brand_id: "Q12345"
#   reason: "conflict with legacy label"
```

---

## 2) CLI: `t0_cli.py`

> Save the following as `t0_cli.py` at your repo root. It creates `work/…` and `t0_out/…` directories as it runs.

```python
#!/usr/bin/env python3
"""
T0 Canonical Brand Registry – ISO+MCC-driven CLI
Commands:
  init              – sanity checks + folders
  hunt-wd           – Wikidata harvest (by MCC classes)
  hunt-osm          – OSM Overpass harvest (by ISO × MCC→OSM tags)
  build             – canonical brands + aliases (Wikidata + auto variants + OSM POI strings)
  reconcile         – apply overrides; collision pre/post reports
  qa                – coverage proxy per ISO×MCC; gaps report
  publish           – manifest + gate hash flag

Respect robots.txt and rate-limits. Set a real User-Agent in requests headers if you fork this.
"""

import argparse, os, sys, time, json, yaml, csv, hashlib, re, unicodedata
from pathlib import Path
from urllib.parse import urlparse

import requests
import pandas as pd

# Optional fuzzy ranking (only used to rank the manual queue)
try:
    from rapidfuzz import fuzz
    HAS_FUZZ = True
except Exception:
    HAS_FUZZ = False

# ---------- Helpers ----------
def nfkd(s:str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode()

LEGAL_SUFFIX = r"\b(inc|corp|co|ltd|llc|plc|gmbh|s\.a\.|s\.p\.a\.|sarl|srl|ag|bv|nv|oy|aps|ab|as)\b"

def norm_text(s: str) -> str:
    if not isinstance(s, str): return ""
    s = nfkd(s).lower()
    s = s.replace("&", " and ").replace("+"," and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(LEGAL_SUFFIX, "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def to_slug(s: str) -> str:
    return re.sub(r"\s+","-", norm_text(s))

def mint_id(label: str, site: str="") -> str:
    key=(label or "")+"|"+(site or "")
    return hashlib.sha256(key.encode()).hexdigest()[:26]

def get_domain(url: str) -> str:
    try:
        net = urlparse(url).netloc.split(".")
        return ".".join(net[-2:]) if len(net)>=2 else ""
    except Exception:
        return ""

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(1<<20), b""):
            h.update(ch)
    return h.hexdigest()

def ensure_dirs():
    Path("work/seed_wikidata").mkdir(parents=True, exist_ok=True)
    Path("work/osm").mkdir(parents=True, exist_ok=True)
    Path("t0_out").mkdir(parents=True, exist_ok=True)

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def rate_sleep(rate_hz):
    if rate_hz <= 0: return
    time.sleep(1.0/rate_hz)

# ---------- Commands ----------

def cmd_init(args):
    ensure_dirs()
    # light sanity
    for cfg in ["run_scope.yaml","mcc_category_map.yaml"]:
        if not Path(cfg).exists():
            print(f"[warn] {cfg} not found – please create it (see inline examples).")
    print("[ok] folders ready: work/, t0_out/")

def cmd_hunt_wd(args):
    """Harvest Wikidata brand candidates by MCC classes with aliases + official website."""
    ensure_dirs()
    cfg = load_yaml("mcc_category_map.yaml")
    wd_out = Path("work/seed_wikidata")
    rate = args.rate
    langs = args.langs.split(",")

    def sparql(class_qids):
        values = " ".join(f"wd:{q}" for q in class_qids)
        lang_filter = ",".join(f'"{l}"' for l in langs)
        q = f"""
        SELECT ?brand ?brandLabel ?site ?alt WHERE {{
          VALUES ?class {{ {values} }}
          ?brand wdt:P31 ?class .
          OPTIONAL {{ ?brand wdt:P856 ?site }}
          OPTIONAL {{ ?brand skos:altLabel ?alt FILTER(LANG(?alt) IN ({lang_filter})) }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}"""
        r = requests.get(
            "https://query.wikidata.org/sparql",
            params={"format":"json","query":q},
            headers={"User-Agent":"brand-registry/1.0 (+you@example.com)"}
        )
        r.raise_for_status()
        return r.json()["results"]["bindings"]

    for mcc, spec in cfg.get("mcc_groups",{}).items():
        cls = spec.get("wikidata_classes",[])
        if not cls: 
            print(f"[skip] MCC {mcc}: no wikidata_classes configured"); 
            continue
        print(f"[wd] MCC {mcc}: classes {cls}")
        data = sparql(cls); rate_sleep(rate)

        rows = {}
        for b in data:
            qid   = b["brand"]["value"].split("/")[-1]
            label = b.get("brandLabel",{}).get("value","")
            site  = b.get("site",{}).get("value","")
            alt   = b.get("alt",{}).get("value","")
            rows.setdefault(qid, {"qid":qid,"label":label,"site":site,"aliases":set(),"mcc":set()})
            if alt: rows[qid]["aliases"].add(alt)
            rows[qid]["mcc"].add(mcc)

        outpath = wd_out/f"wikidata_{mcc}.jsonl"
        with open(outpath,"w",encoding="utf-8") as f:
            for qid,row in rows.items():
                row["aliases"]=sorted(row["aliases"])
                row["mcc"]=sorted(row["mcc"])
                f.write(json.dumps(row, ensure_ascii=False)+"\n")
        print(f"[wd] wrote {outpath} ({len(rows)} rows)")
    print("[wd] done.")

def cmd_hunt_osm(args):
    """Harvest OSM POI strings per ISO×MCC via Overpass (brand, operator, name)."""
    ensure_dirs()
    scope = load_yaml("run_scope.yaml")
    cfg   = load_yaml("mcc_category_map.yaml")

    iso = pd.read_parquet(scope["iso_parquet"])
    target_iso = iso.query("country_iso in @scope['iso_filter']")["country_iso"].tolist()
    print(f"[osm] ISO list: {len(target_iso)}")

    out_csv = Path("work/osm/osm_brand_strings.csv")
    rows=[]
    rate = args.rate

    def overpass(iso2, key, value):
        q = f"""
        [out:json][timeout:180];
        area["ISO3166-1"="{iso2}"]->.a;
        ( node["{key}"="{value}"](area.a);
          way["{key}"="{value}"](area.a);
          relation["{key}"="{value}"](area.a); );
        out tags qt;"""
        r = requests.post("https://overpass-api.de/api/interpreter", data={"data":q},
                          headers={"User-Agent":"brand-registry/1.0 (+you@example.com)"})
        r.raise_for_status()
        return r.json()

    for iso2 in target_iso:
        for mcc, spec in cfg.get("mcc_groups",{}).items():
            for tag in spec.get("osm", []):
                (key, value), = tag.items()
                try:
                    data = overpass(iso2, key, value); rate_sleep(rate)
                    for el in data.get('elements',[]):
                        t = el.get('tags',{})
                        rows.append({
                            "country_iso": iso2, "mcc": mcc,
                            "key": key, "value": value,
                            "brand_wikidata": t.get("brand:wikidata",""),
                            "brand": t.get("brand",""),
                            "operator": t.get("operator",""),
                            "name": t.get("name","")
                        })
                except Exception as e:
                    rows.append({"country_iso": iso2,"mcc": mcc,"key":key,"value":value,"brand_wikidata":"ERR"})
                    print(f"[osm] error {iso2} {mcc} {key}={value}: {e}")

    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"[osm] wrote {out_csv} ({len(rows)} rows)")

def cmd_build(args):
    """Build brands.parquet + brand_aliases.parquet from Wikidata seeds + OSM strings."""
    ensure_dirs()
    wd_dir = Path("work/seed_wikidata")
    osm_csv = Path("work/osm/osm_brand_strings.csv")
    if not wd_dir.exists(): sys.exit("[build] seed_wikidata missing. Run hunt-wd.")
    if not osm_csv.exists(): sys.exit("[build] osm_brand_strings.csv missing. Run hunt-osm.")

    # Load WD seeds
    rows=[]
    for j in wd_dir.glob("wikidata_*.jsonl"):
        for line in open(j, "r", encoding="utf-8"):
            rows.append(json.loads(line))
    wd = pd.DataFrame(rows)  # qid,label,site,aliases[],mcc[]

    # Canonical brands
    wd["website_domain"] = wd["site"].map(get_domain)
    wd["brand_id"] = wd["qid"]
    # Mint internal ID when no QID
    wd.loc[wd["brand_id"].eq(""), "brand_id"] = wd.apply(lambda r: mint_id(r["label"], r["website_domain"]), axis=1)
    wd["brand_name"] = wd["label"]
    wd["brand_slug"] = wd["brand_name"].map(to_slug)
    wd["status"] = "active"
    brands = wd[["brand_id","brand_name","brand_slug","website_domain","qid","mcc"]].rename(
        columns={"qid":"wikidata_qid"}
    )
    # Sources col
    brands["sources"] = brands.apply(lambda r: [f"wikidata:{r['wikidata_qid']}", "site:"+str(r["website_domain"])], axis=1)

    # Aliases: WD altLabels
    alias_rows=[]
    for r in rows:
        qid = r["qid"]
        bid = brands.loc[(brands["wikidata_qid"]==qid) | (brands["brand_name"]==r["label"]), "brand_id"]
        if len(bid):
            for a in r.get("aliases",[]):
                alias_rows.append({"brand_id":bid.iloc[0], "alias":a, "alias_norm":norm_text(a),
                                   "alias_type":"wikidata_label", "confidence":0.98, "source":"wikidata"})

    # Aliases: auto variants from canonical name
    for _,b in brands.iterrows():
        base = norm_text(b["brand_name"])
        cands = { base, base.replace(" and ","&"), base.replace("'",""), base.replace(" and "," ") }
        for v in cands:
            alias_rows.append({"brand_id":b["brand_id"], "alias":v, "alias_norm":v,
                               "alias_type":"auto_variant", "confidence":0.99, "source":"auto"})

    # Aliases: OSM strings (brand/operator/name). Map to brand_id via brand:wikidata when present.
    osm = pd.read_csv(osm_csv)
    osm["alias"] = osm[["brand_wikidata","brand","operator","name"]].bfill(axis=1).iloc[:,0]
    osm["alias_norm"] = osm["alias"].map(norm_text)
    osm["alias_type"] = "poi_name"
    osm["confidence"] = 0.90
    osm["source"] = "osm"
    # join brand_id by wikidata
    osm = osm.merge(brands[["brand_id","wikidata_qid"]], left_on="brand_wikidata", right_on="wikidata_qid", how="left")
    osm_alias = osm[["brand_id","alias","alias_norm","alias_type","confidence","source","country_iso","mcc"]]
    # concat
    aliases = pd.concat([pd.DataFrame(alias_rows), osm_alias], ignore_index=True)
    # drop empties/dupes
    aliases = aliases.dropna(subset=["alias"]).drop_duplicates()

    # Write
    brands.to_parquet("t0_out/brands.parquet", index=False)
    aliases.to_parquet("t0_out/brand_aliases.parquet", index=False)
    print("[build] wrote t0_out/brands.parquet,", len(brands), "brands")
    print("[build] wrote t0_out/brand_aliases.parquet,", len(aliases), "aliases")

def cmd_reconcile(args):
    """Apply overrides; report collisions before/after (alias_norm → >1 brand)."""
    ensure_dirs()
    aliases = pd.read_parquet("t0_out/brand_aliases.parquet")
    brands  = pd.read_parquet("t0_out/brands.parquet")

    # collisions
    col_before = (aliases.groupby("alias_norm")["brand_id"].nunique()
                         .reset_index(name="n").query("n>1").sort_values("n", ascending=False))
    col_before.to_csv("t0_out/qa_collisions_before.csv", index=False)

    # apply overrides if present
    ovr_path = Path("overrides.brand_aliases.yaml")
    if ovr_path.exists():
        ovr = yaml.safe_load(open(ovr_path)) or []
        ovr_df = pd.DataFrame(ovr)
        if not ovr_df.empty:
            aliases = aliases.merge(
                ovr_df[["alias_norm","country_iso","force_brand_id"]],
                on=["alias_norm","country_iso"], how="left"
            )
            aliases["brand_id"] = aliases["force_brand_id"].fillna(aliases["brand_id"])
            aliases = aliases.drop(columns=["force_brand_id"])
    # collisions after
    col_after = (aliases.groupby("alias_norm")["brand_id"].nunique()
                        .reset_index(name="n").query("n>1").sort_values("n", ascending=False))
    col_after.to_csv("t0_out/qa_collisions_after.csv", index=False)

    aliases.to_parquet("t0_out/brand_aliases.parquet", index=False)
    print(f"[reconcile] collisions before: {len(col_before)}; after: {len(col_after)}")

def cmd_qa(args):
    """Coverage proxy per ISO×MCC using OSM strings; report gaps under threshold."""
    ensure_dirs()
    aliases = pd.read_parquet("t0_out/brand_aliases.parquet")
    osm     = pd.read_csv("work/osm/osm_brand_strings.csv")

    def norm(s):
        if not isinstance(s, str): return ""
        s = nfkd(s).lower().replace("&"," and ").replace("+"," and ")
        s = re.sub(r"[^\w\s]"," ", s); s = re.sub(r"\s+"," ", s).strip()
        return s

    osm["alias_norm"] = osm[["brand_wikidata","brand","operator","name"]].bfill(axis=1).iloc[:,0].map(norm)
    ali = aliases[["brand_id","alias_norm"]].drop_duplicates()
    join = osm.merge(ali, on="alias_norm", how="left").assign(hit=lambda d: d["brand_id"].notna())

    cov = (join.groupby(["country_iso","mcc"])["hit"].mean()
                .reset_index(name="coverage"))
    cov.to_csv("t0_out/qa_coverage_iso_mcc.csv", index=False)

    gaps = cov[cov["coverage"] < args.cov_threshold].sort_values(["coverage"])
    gaps.to_csv("t0_out/qa_gaps.csv", index=False)
    print(f"[qa] wrote qa_coverage_iso_mcc.csv (rows={len(cov)})")
    print(f"[qa] gaps < {args.cov_threshold}: {len(gaps)}")

def cmd_publish(args):
    """Write manifest + gate hash flag for reproducible publication."""
    ensure_dirs()
    out = Path("t0_out")
    need = ["brands.parquet","brand_aliases.parquet","qa_collisions_after.csv","qa_coverage_iso_mcc.csv"]
    for f in need:
        if not (out/f).exists():
            sys.exit(f"[publish] missing {f}; run previous steps first.")

    manifest = {
        "version": args.version,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "outputs": { f: sha256(out/f) for f in need },
        "inputs": {
            "run_scope":  sha256(Path("run_scope.yaml")),
            "mcc_map":    sha256(Path("mcc_category_map.yaml"))
        }
    }
    (out/"t0_manifest.json").write_text(json.dumps(manifest, indent=2))
    gate = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    (out/"_passed.flag").write_text(gate+"\n")
    print("[publish] manifest + _passed.flag written; gate hash:", gate)

# ---------- Entrypoint ----------

def main():
    ap = argparse.ArgumentParser(description="T0 Canonical Brand Registry CLI (ISO+MCC-driven)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p0 = sub.add_parser("init", help="make folders, sanity checks")
    p0.set_defaults(func=cmd_init)

    p1 = sub.add_parser("hunt-wd", help="Wikidata harvest by MCC classes")
    p1.add_argument("--rate", type=float, default=1.0, help="requests per second")
    p1.add_argument("--langs", default="en,fr,de,es,it,pt", help="altLabel languages (comma sep)")
    p1.set_defaults(func=cmd_hunt_wd)

    p2 = sub.add_parser("hunt-osm", help="OSM Overpass harvest by ISO×MCC")
    p2.add_argument("--rate", type=float, default=1.0, help="requests per second")
    p2.set_defaults(func=cmd_hunt_osm)

    p3 = sub.add_parser("build", help="Build brands.parquet + brand_aliases.parquet")
    p3.set_defaults(func=cmd_build)

    p4 = sub.add_parser("reconcile", help="Apply overrides; collisions before/after")
    p4.set_defaults(func=cmd_reconcile)

    p5 = sub.add_parser("qa", help="Coverage proxy per ISO×MCC and gaps")
    p5.add_argument("--cov-threshold", type=float, default=0.85, help="coverage threshold for gaps")
    p5.set_defaults(func=cmd_qa)

    p6 = sub.add_parser("publish", help="Write manifest + gate hash flag")
    p6.add_argument("--version", default="t0-1.0.0", help="manifest version string")
    p6.set_defaults(func=cmd_publish)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
```

---

## 3) Typical run sequence

```bash
# one-time
python t0_cli.py init

# hunt Wikidata (by MCC classes)
python t0_cli.py hunt-wd --rate 1.0

# hunt OSM (by ISO × MCC)
python t0_cli.py hunt-osm --rate 1.0

# build canonical registry + aliases
python t0_cli.py build

# reconcile (apply overrides if any; generate collision reports)
python t0_cli.py reconcile

# QA coverage proxy per ISO×MCC; see gaps under 0.85
python t0_cli.py qa --cov-threshold 0.85

# publish with manifest + gate hash
python t0_cli.py publish --version t0-1.0.0
```

---

## 4) What this gives you

* A **fully ISO+MCC-driven** registry pipeline from scratch—**no CSV assumed**, no hand-picked lists.
* Concrete, scrappable sources (Wikidata SPARQL, Overpass) and deterministic canonicalization.
* **Minimal linguistics:** hard keys (QID/domain) + simple normalization; tiny manual overrides when needed.
* Reproducible outputs (`brands.parquet`, `brand_aliases.parquet`) with **manifest & gate hash** for your lineage.

If you want, I can add:

* a small **store-locator probe** command (`hunt-store`) to confirm canonical domains for the top K brands only,
* a `--mcc-only` or `--iso-only` filter on hunts for incremental runs,
* or a micro **fuzzy ranker** in `reconcile` to print the **Top-N ambiguous aliases** that deserve a manual override entry.
