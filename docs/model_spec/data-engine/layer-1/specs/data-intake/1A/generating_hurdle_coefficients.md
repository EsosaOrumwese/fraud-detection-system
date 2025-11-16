# Generating `hurdle_coefficients.yaml`

Below is a tight, one-person, region-bounded plan: what extra data to hunt, why it matters, and the exact “training tables” to add to your preview so you know what to collect.

---

## Lock-ins (project decisions)
These choices are **fixed** for this build so the trainer and the engine stay byte-aligned:
1) **Per‑MCC training granularity**: T1 rows are `(brand_id, country_iso, mcc)` (not just brand×country).  
2) **CNP identifiability**: do **both** routes — a small **online-only exemplar** list *and* a **single global CNP macro calibration** after fitting.  
3) **Dictionaries**: read MCC/channel/bucket dictionaries from the **engine’s dataset dictionary** and freeze them in T4; **never** infer order from map iteration.  
4) **Channel coverage (no synthetic duplicates)**: keep the observed channel as-is (one-hot CP or CNP). Ensure coverage by adding true **CNP exemplars** (T3-A) and calibrating a global **CNP offset** (T3-B). The engine’s 2-slot channel block is satisfied by the dictionary—no need to duplicate rows. 
5) **Intercept calibration is required**: adjust the hurdle intercept to match observed multi-site prevalence in-region on the training design.  
6) **QC gates are binding**: coverage floors, observed & fitted bucket monotonicity, brand-aware CV targets, and 10-row bit-match between trainer and engine loader must all pass before export.

These lock-ins keep the learned `beta` and `beta_mu` exactly in the shape S1/S2 expect while giving CNP a real, measurable effect.  ⟶ (T1/T3/T4/T6 sections below implement this.) 

---

## What the coefficients must encode (so your training data must reflect it)

* **Category (MCC) effect** on being **multi-site** and on the **mean number of outlets** when multi-site.
* **Channel (CP vs CNP)** effect (CP tends to be more multi-site; CNP less so).
* **Macro context (GDP bucket)** effect on being multi-site (hurdle only).

So you need **examples of “merchants” (brand–country–MCC tuples)** with:

1. a binary label **`is_multi`** (≥2 domestic outlets), and
2. for those with `is_multi=1`, the **count** of domestic outlets (**`outlet_count_domestic`**) to fit the NB mean.

---

## Additional training-only inputs to add to your preview (what to hunt)

> These do **not** go into the runtime engine. They exist to fit the two vectors (`beta`, `beta_mu`) and then disappear. You can list them under a new section like **“Training-only (not ingested at runtime)”** so your team knows to collect them.

### **T0. brand_aliases**  *(normalize brand identity; training-only)*

**Purpose:** collapse variant brand strings to a stable `brand_id` (prefer Wikidata QID) so counts/labels aren't fragmented.

**Processed schema (preview):**
```
brand_id : string        # canonical ID, e.g., QID where available
alias    : string        # raw 'brand'/'name'/'operator' from OSM / store locators
source   : string        # "OSM" | "STORE_LOCATOR" | "WIKIDATA"
```

**Acceptance:** every POI used in T1 must map to exactly one `brand_id`; unresolved aliases are dropped from the corpus.

---

### **T1. brand_country_mcc_outlet_census**  *(core labels; per‑MCC)*

**Purpose:** give you `is_multi` and `outlet_count_domestic` by **(brand, country_iso, mcc)**.
**Where to source:**

* **OpenStreetMap (ODbL)** POIs with retail/food/service tags; use `brand` / `brand:wikidata` / `operator`; map each POI to **MCC** using your governed **OSM→MCC** rules before aggregation.
* **Official store locators** for large brands (CSV/JSON/HTML where redistribution allows).
* **Wikidata** to normalize brands (QIDs) and infer country presence.

**Processed schema (preview):**

```
brand_id            : string   # stable ID (prefer Wikidata QID if available)
brand_name          : string
country_iso         : ISO2
mcc                 : int32    # 4‑digit MCC assigned per POI before aggregation
outlet_count_domestic : int32  # count of physical POIs in the country **for this MCC**
is_multi            : int8     # 1 if outlet_count_domestic >= 2 else 0
source_mask         : string   # e.g., "OSM|WIKIDATA|STORE_LOCATOR"
asof_date           : date
licence             : string   # e.g., "ODbL-1.0", site TOS ref, etc.
```

**Naming note:** if this country dimension is *presence* rather than *origin*, you may name it `country_iso` in the training tables. The engine uses **merchant home ISO** for GDP bucket at runtime—keep semantics consistent across training and runtime.

**Acceptance:**
1. **POI de-dup (store-level):** within each `(brand_id, country_iso, mcc)` cluster, collapse POIs that either (a) share **identical address** OR (b) lie within **75 m** *and* share the same tag family (`shop` vs `amenity`) and any of `{opening_hours, phone}` if present — keep first-seen. **Dedup happens before aggregating** to `(brand, country, mcc)` counts.
2. **Country attribution:** 100% of POIs must resolve to a country via polygon clip; drop unresolved.  
3. **Brand normalisation:** all POIs must be mapped through **T0 brand_aliases** to a single `brand_id`.
4. **CNP presence rows:** for any `brand_id` that appears only in T3 (online-only) and not in T1, add a T1 stub per `(brand_id, country_iso)` in scope with `outlet_count_domestic=0`, `is_multi=0`, and the brand’s MCC (or a neutral MCC you govern for pure-online). This lets the logistic see true CNP negatives without duplicating rows.

---

### **T2. brand_to_mcc_map**  *(category signal / QC)*

**Purpose:** govern the **tag→MCC** rules and (optionally) brand‑level MCC hints. T1 already includes `mcc` per aggregated row; use T2 primarily to **validate coverage/consistency** and maintain the mapping rules as governed policy.
**Where to source:** MCC code lists (ISO 18245) + your own **tag→MCC** mapping.

**Processed schema (preview):**

```
brand_id         : string      # or a tag pattern, but normalize into brand_id where possible
mcc              : int32       # 4-digit MCC used by your engine
mapping_confidence: float32    # 0..1 (optional)
notes            : string
```

**Acceptance:** MCC must be one you plan to encode in the hurdle design. It’s fine if many brands map to a small MCC set at first; ridge/hierarchical shrinkage will handle sparsity.

---

### **T3. brand_channel_labels**  *(channel signal)*

**Purpose:** assign **CP** (has physical presence) or **CNP** (online-only) with **identifiable** signal.

**Where to source (both are required in this build):**
* From **T1**: if `outlet_count_domestic > 0` ⇒ **CP**.  
* **Online-only exemplars (A)** *and* **Macro anchor (B)**:

**Option A — Online-only exemplars (light list):** curate 30–50 `brand_id`s that are digital-only (marketplaces, fintech, ticketing, SaaS). Mark them `channel_token="CNP"` with `evidence="ONLINE_ONLY_LIST"`.

**Option B — Macro anchor (single global offset):** after fitting the hurdle, add a single additive offset $\Delta$ to the **CNP** coefficient so the model’s implied CNP share by country matches the public series. Concretely, choose $\Delta$ to minimize $\sum_{c} w_c \big(\hat{s}_{\mathrm{cnp}}(c;\,\beta + \Delta \cdot e_{\mathrm{CNP}}) - s^{\mathrm{pub}}_{\mathrm{cnp}}(c)\big)^2$ over countries $c$ (weights $w_c$ optional), then set $\beta_{\mathrm{CNP}} \leftarrow \beta_{\mathrm{CNP}} + \Delta$. Do **not** change other coefficients.

**Both A and B are mandatory** here: A pins the sign, B sets the magnitude as one global offset consistent with public evidence.

**Note on training rows for CNP:** if a brand is online-only (A) and has no POIs, emit T1 stubs as described above so the hurdle fit includes those negatives; do **not** duplicate CP/CNP rows.

> **Illustrative previews** for both A and B are included below (see: *Illustrative previews — do not commit as data*). They are blueprints to guide hunting/wrangling, **not** data to ship.
**Processed schema (preview):**

```
brand_id         : string
channel_token    : string   # "CP" or "CNP" (engine’s internal tokens)
evidence         : string   # "OSM_POI" | "ONLINE_ONLY_LIST" | "MACRO_CALIBRATION"
```

**Acceptance:** channel must be the engine’s **internal** tokens; no ingress strings.

---

### **T4. train_design_matrix.metadata**  *(freezes the dictionaries)*

**Purpose:** lock the exact **MCC order**, channel order, and GDP bucket order used at fit time. These **must match the engine’s dictionaries** for the target run; **read them directly from the engine’s dataset dictionary** (do not infer order from maps) to avoid drift.

**Processed schema (YAML preview):**

```yaml
dicts:
  channel: ["CP","CNP"]
  gdp_bucket: [1,2,3,4,5]
  mcc: [4111, 5411, 5732, 5812, 5942, 6011, ...]   # full order you train on
design_notes: "Region universe: GB+EEA+US+CA; GDP year 2024; buckets: Jenks-5"
```

---

### **T5. train_splits**  *(reproducible evaluation)*

**Purpose:** group-aware splits to avoid leakage (e.g., **by brand**).
**Processed schema (preview):**

```
brand_id         : string
split            : string   # "train" | "valid" | "test"
seed             : int32
```

---

### **T6. macro_join_cache**  *(GDP bucket join)*

**Purpose:** helper derived from your runtime GDP + bucket map for speed.
**Processed schema:**

```
country_iso       : ISO2
gdp_bucket        : int8  # 1..5
gdp_pc_usd_2015   : float64  # 2024
```

*(This can be derived on the fly from your runtime tables; caching is optional.)*

---

## Why the current runtime data isn’t enough to *train*

* Your runtime pack gives the **feature scaffolding** (ISO, GDP, buckets, MCC vocabulary, channel tokens) but **no labels** (`is_multi`, `outlet_count_domestic`) and **no brand-level rows**. Without labels, you can’t fit a logistic hurdle or a mean link.
* The training corpus above fills exactly that gap while keeping features **identical** to the engine’s design (MCC, channel, GDP bucket).

---

## How the training corpus turns into the two vectors your engine wants

1. **Assemble X, y for the hurdle**

   * Join **T1** (labels with `mcc`) ⟂ **T3** (channel) ⟂ **T6** (bucket). *(T2 is used for governed mapping/QC, not required for this join if T1 already has `mcc`.)*
   * Features `x = [1 | one-hot(MCC) | one-hot(channel CP,CNP) | one-hot(bucket 1..5)]`.
   * Target `y = is_multi`.
   * **Channel rows:** do **not** duplicate. Use the observed channel for each brand; add real **CNP** rows via the online-only list (T3-A), then apply the global **CNP** calibration (T3-B).

2. **Fit penalized logistic** (ridge or hierarchical).
   * If `is_multi` is rare, use **class weights** or stratified sampling.
   * **Reference coding (identifiability):** fit with a full‑rank design by dropping **one MCC** (baseline), dropping channel **CNP** (baseline), and dropping **bucket = 1**, while keeping the **intercept**.
   * **Expand to engine order:** after fitting, **insert zeros for the dropped baselines** and re‑order to the engine’s frozen dictionaries so `beta` length is **1 + C_mcc + 2 + 5** with blocks `[intercept | MCC block | CP | CNP | buckets 1..5]`.
   * **Intercept calibration (required):** adjust the logistic intercept so the model’s **mean π̂ over the training design** equals the **empirical multi-site rate** in-region (weighted by your class/country scheme if used); do **not** change any other coefficients.   
   * CV by **brand** or **brand×country** to avoid leakage.
   * Export **`beta`** in the frozen order from **T4**.

3. **Assemble X, y for the NB-mean** (multi-site only)

   * Filter **T1** to `is_multi=1`; target `y = outlet_count_domestic`.
   * Features `x_mu = [1 | one-hot(MCC) | one-hot(channel)]` *(no bucket)*.
   * **Reference coding (identifiability):** fit a full‑rank model by dropping **one MCC** (baseline) and dropping channel **CNP** (baseline), keeping the **intercept**.
   * **Expand to engine order:** after fitting, **insert zeros for the dropped baselines** and re‑order to the engine’s frozen dictionaries so `beta_mu` length is **1 + C_mcc + 2** with blocks `[intercept | MCC block | CP | CNP]`.
   * Fit **Poisson GLM with ridge** (good for the mean coefficients); the separate `nb_dispersion_coefficients.yaml` will later handle over‑dispersion.
   * Export **`beta_mu`** in the same MCC & channel order.

4. **Package `hurdle_coefficients.yaml`**

   * Include **T4’s dictionaries** and the two vectors (`beta`, `beta_mu`).
   * Hit the engine’s acceptance checks: lengths, order, all finite, exact token sets.

---

## Minimal viable “hunt list” to start collecting now

* **OSM POI dump** for your region universe; extract **brand**, **country**, and **MCC**; count outlets per **brand×country×mcc** (deduped per the 75m rule).
* **A small list of online-only brands** to label **CNP** (even 30–50 well-known names is plenty to start).
* **Your MCC mapping** for the OSM tag space and large brands (begin with the MCCs you expect in your merchant seed).
* **GDP bucket year 2024** (already in your runtime pack).
* *(Optional)* A few **store-locator CSVs** for big chains to validate or augment OSM counts.

This is all doable by one person and gives you a credible, public-data proxy for the “essence” those coefficients need to encode. You can then iterate: add brands, refine MCC mapping, and re-fit.

---

## **Illustrative previews — do not commit as data**
These examples show the **shape** of two training-only aids discussed in T3. They are **blueprints** to guide hunting; do **not** treat them as authoritative inputs.

### Preview A — online-only exemplars (YAML shape)
```yaml
semver: "preview"
version: "example"
region_id: "R-EEA12@YYYY-MM-DD"
brands:
  - brand_id: "Q12345"
    display_name: "AcmePay"
    evidence_url: "https://en.wikipedia.org/wiki/AcmePay"
  - brand_id: "Q67890"
    display_name: "TicketNow"
    evidence_url: "https://en.wikipedia.org/wiki/TicketNow"
# When hunted, these entries feed T3 with:
#   channel_token: "CNP"
#   evidence: "ONLINE_ONLY_LIST"
```

### Preview B — macro anchor series (CSV shape)
```csv
country_iso,remote_share
AT,0.22
DE,0.20
FR,0.23
GB,0.31
SE,0.30
```
*Use any reputable public series consistent with your region (e.g., Eurostat online-shopper share, ECB remote card share). The trainer uses this **once** to calibrate a single global `beta_channel_CNP`.*

---

## From hunted data to three training tables (deterministic)

### 1) Logistic hurdle (learns `beta`) — **training frame preview**

**File (suggested):** `hurdle.training_rows.parquet`
**One row** = one *(brand, country_iso, mcc)* with the label `is_multi`.

**Columns (minimal, engine‑aligned):**

* `brand_id : string` — canonical ID (prefer Wikidata QID)
* `country_iso : string` — ISO2, uppercase
* `mcc : int32` — 4‑digit MCC in the engine dictionary
* `channel : string ∈ {"CP","CNP"}` — engine’s internal tokens
* `gdp_bucket : int8 ∈ {1,2,3,4,5}` — from your 2024 bucket map
* `is_multi : int8 ∈ {0,1}` — **label** (1 if domestic outlets ≥ 2)
* *(optional QC)* `asof_date`, `source_mask`

**Tiny example:**

```
brand_id  country_iso  mcc   channel  gdp_bucket  is_multi
Q12345    GB                5411  CP       5           1
Q67890    IE                5812  CP       4           1
Q99999    FR                5732  CP       3           0
Q77777    DE                5942  CNP      5           0
```

**Why this is sufficient:**
S1 builds the feature vector in this order:
$$
x = [1 \ \vert\ \text{one‑hot(MCC)} \ \vert\ \text{one‑hot(channel: CP,CNP)} \ \vert\ \text{one‑hot(bucket 1..5)}]
$$
and applies $\pi=\sigma(\beta^\top x)$. Your frame provides **exactly** those fields + the binary label. No other columns are needed. 

---

### 2) NB mean (learns `beta_mu`) — **training frame preview**

**File (suggested):** `nb_mean.training_rows.parquet`
**Filter:** take the **multi‑site subset** from the hurdle frame (`is_multi=1`), and expose counts.

**Columns (minimal, engine‑aligned):**

* `brand_id : string`
* `country_iso : string`
* `mcc : int32`
* `channel : "CP"|"CNP"`
* `k_domestic : int32` — **target** (domestic outlet count, **≥ 2**)

**Tiny example:**

```
brand_id  country_iso  mcc   channel  k_domestic
Q12345    GB                5411  CP       12
Q67890    IE                5812  CP       3
Q22222    DE                5942  CNP      2
```

**Why this is sufficient:**
S2’s mean link uses
$$
x_\mu = [1 \ \vert\ \text{one‑hot(MCC)} \ \vert\ \text{one‑hot(channel)}]
$$
to learn $\mu=\exp(\beta_\mu^\top x_\mu)$. Buckets are **not** used here (by design). This table gives the count target `k_domestic` and exactly those covariates. 

---

### 10‑second validity check against your engine contracts

* **Logistic (`beta`) length identity:** $1 + C_\text{mcc} + 2 + 5$. Your frame supplies MCC, channel (CP,CNP order), and 5 buckets. ✔︎ 
* **NB mean (`beta_mu`) length identity:** $1 + C_\text{mcc} + 2$. Your frame supplies MCC and channel only. ✔︎ 
* **Token vocabularies:** channel uses **internal** `["CP","CNP"]`; MCC values come from the engine dictionary and will be frozen into the YAML dicts; buckets are **1..5**. ✔︎ 
* **No synthetic CP/CNP duplication:** you keep observed channel and add genuine CNP exemplars via your roster; that’s exactly what we locked earlier. ✔︎ 

---

### (Optional) design‑matrix view (if you prefer a “wide” fit table)

If your trainer likes a pre‑expanded matrix, you can emit:

**File:** `hurdle.design_matrix.parquet`
**Columns:**
`intercept=1`, `mcc__{code}∈{0,1}...`, `channel__CP`, `channel__CNP`, `bucket__1..bucket__5`, **label** `is_multi`.

And similarly for **`nb_mean.design_matrix.parquet`** with
`intercept`, `mcc__*`, `channel__CP`, `channel__CNP`, **target** `k_domestic`.

This is just a different *presentation* of the two frames above; the information content is identical.

---

## QC gates before exporting YAML  *(objective pass/fail)*

* **Coverage floors (per country in region):** sum of `n_outlets` over top-20 brands ≥ **100** (catches empty/partial extracts). **Fail build** if not met.
* **Observed bucket monotonicity:** empirical multi-site rate should weakly increase from bucket 1→5 (allow small deviations). **Warn** on small violations; **fail** on systematic reversals.
* **Fitted bucket monotonicity:** enforce/post-process `β_bucket` to be non-decreasing (use isotonic regression on bucket effects if needed). **Fail** if post-processed order still violates monotonicity.
* **Hold-out metrics (brand-level CV):** hurdle **AUC ≥ 0.70**, **Brier ≤ 0.20**; NB-mean **log-MAE ≤ 0.6** on the multi subset. **Fail** if thresholds are missed.
* **Deterministic alignment:** pick 10 **brand×country×mcc** cases and verify $\pi$ and $\mu$ computed by your trainer match the YAML loader **bit-for-bit** (shortest round-trip printing). **Fail** on any mismatch.