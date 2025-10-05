Short verdict: **v2.1 is 95% there and will do the job**—it broadens seeds, guards OSM strings, emits **`routes`** (brand×country×MCC), and keeps everything reproducible. There’s one **blocking bug** left in the “OSM-only mint” path (explained + fixed below), plus two tiny hardening nits. Once you apply the mini-patch, you’re good to run at scale for “tens of thousands of routes.” 

---

## What’s correct (keep)

* **Broadened Wikidata seeds** (`P31 / P279*`) → higher recall per MCC.
* **OSM linking** prefers human labels, discards generic names, exact→(optional) fuzzy backfill.
* **`routes` emitter** publishes `(brand_id, country_iso, mcc, n_poi)` and is included in `publish` gate.
* **Overrides**: global + country-scoped; **manifest** digests overrides; parquet→CSV fallback; retry/backoff wrappers. 

---

## The one blocker to fix

### Symptom

When **Wikidata seeds are empty**, your “OSM-only mint” code creates new brands (`osm_minted`) and rewrites `brands`/`brand_aliases`—**but `routes` is built *before* minting** and is **not** rebuilt, and the OSM aliases are never re-joined to those newly minted brands. So minted brands don’t show up in `routes`. 

### Drop-in patch

Add the highlighted bits in your `cmd_build` after the minting block:

```diff
@@
     write_table_parquet_or_csv(routes, "t0_out/routes.parquet")
     print("[build] wrote t0_out/routes.parquet,", len(routes), "rows")

     # OPTIONAL: If WD was empty for this MCC/ISO, mint OSM-only brands from strong evidence
@@
-            if minted:
-                brands = pd.concat([brands, pd.DataFrame(minted)], ignore_index=True).drop_duplicates("brand_id")
-                write_table_parquet_or_csv(brands, "t0_out/brands.parquet")
-                # re-write aliases with minted rows included
-                write_table_parquet_or_csv(pd.concat([pd.DataFrame(alias_rows), osm_alias], ignore_index=True),
-                                           "t0_out/brand_aliases.parquet")
+            if minted:
+                brands = pd.concat([brands, pd.DataFrame(minted)], ignore_index=True).drop_duplicates("brand_id")
+                write_table_parquet_or_csv(brands, "t0_out/brands.parquet")
+                # rejoin minted aliases to OSM rows to populate brand_id
+                alias2 = pd.DataFrame(alias_rows)[["brand_id","alias_norm"]].dropna().drop_duplicates()
+                osm_alias = osm_alias.merge(alias2, on="alias_norm", how="left", suffixes=("","_mint"))
+                osm_alias["brand_id"] = osm_alias["brand_id"].fillna(osm_alias["brand_id_mint"])
+                osm_alias = osm_alias.drop(columns=["brand_id_mint"])
+                # rewrite aliases and REBUILD routes with minted matches included
+                all_alias = pd.concat([pd.DataFrame(alias_rows), osm_alias], ignore_index=True)
+                write_table_parquet_or_csv(all_alias, "t0_out/brand_aliases.parquet")
+                routes = (osm_alias.dropna(subset=["brand_id"])
+                                    .groupby(["brand_id","country_iso","mcc"], dropna=False)
+                                    .size().reset_index(name="n_poi"))
+                if not routes.empty and "country_iso" in routes:
+                    routes["country_iso"] = routes["country_iso"].astype("string").str.upper()
+                write_table_parquet_or_csv(routes, "t0_out/routes.parquet")
```

**Why this matters:** now OSM-minted brands **actually appear in `routes`** whenever WD is thin—exactly the case you created minting for.

---

## Two micro-hardening tweaks (optional but recommended)

1. **Constrain fuzzy with a safer MCC check** (works with NaN too):
   Replace the fuzzy MCC gate:

   ```diff
   ```

* mcc_ok = (not osm_alias.at[idx,"mcc"]) or (osm_alias.at[idx,"mcc"] in brand_mcc.get(cand,set()))

- mcc_val = osm_alias.at[idx, "mcc"]
- mcc_ok = (pd.isna(mcc_val)) or (mcc_val in brand_mcc.get(cand, set()))

  ```
  ```

2. **Tidy sources** (no `wikidata:None` / `site:` empties):

   ```python
   def _src(qid, dom):
       s = []
       if qid: s.append(f"wikidata:{qid}")
       if dom: s.append(f"site:{dom}")
       return s
   brands["sources"] = brands.apply(lambda r: _src(r["wikidata_qid"], r["website_domain"]), axis=1)
   ```

---

## Will this meet your “thousands per MCC / tens of thousands of routes” goal?

Yes—**with the patch above and a global run**, the high-density MCCs (restaurants 5812, fast food 5814, supermarkets 5411, fuel 5541, pharmacies 5912, electronics 5732) will generate **many tens of thousands of `routes` rows** across countries. The remaining practical limiter is harvest throughput:

### Throughput reality check

* Your Overpass query runs **per ISO × MCC × tag** with a country-wide bbox; for large/dense countries you’ll hit timeouts.
* Plan a follow-up change to **tile per country** (e.g., 4×4 or 8×8 grids for US/DE/GB/FR) with the same backoff wrapper, or add a `--backend=osmplanet` path (osmium/pyosmium over regional PBFs) later. The rest of this pipeline stays unchanged. 

---

## Quick acceptance checklist (what to look for after a real run)

* `t0_out/brands.(parquet|csv)` : O(10³–10⁴) rows globally for the six target MCCs.
* `t0_out/brand_aliases.(parquet|csv)` : O(10⁴–10⁵) alias rows.
* `t0_out/routes.(parquet|csv)` : **many tens of thousands** of rows (brand×country×MCC) with non-zero `n_poi`.
* `t0_out/qa_coverage_iso_mcc.csv` : `any_cov` high for countries with good OSM coverage; gaps flagged where coverage < threshold.
* `t0_out/_passed.flag` + `t0_out/t0_manifest.json` : inputs/outputs digested; overrides included if present.

---

### Bottom line

* **v2.1 does the job**; apply the small “minted-brands → routes” patch and you’re production-ready.
* From there, scale your harvest (tiling/planet mode) to hit your “thousands per MCC / tens of thousands of routes” target quickly—without changing the downstream engine contracts. 
