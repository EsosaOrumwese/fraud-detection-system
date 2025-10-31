# 3B — Purely Virtual Merchants (state-overview, 6 states)

## S0 — Gate & environment seal (RNG-free)

**Goal.** Prove we’re authorised to read inputs and fix identities for this run.
**Must verify before any read.**

* Global contract: producers publish a **validation bundle + `_passed.flag`; consumers refuse to read otherwise** (“no PASS → no read”). Record `{seed, manifest_fingerprint}` at open. 
* Pin governed inputs you’ll rely on here: `mcc_channel_rules.yaml`, `virtual_settlement_coords.csv`, `cdn_country_weights.yaml`, HRSL raster, and (from 2A) the **tz-world/tzdata** digests you need to assign TZIDs to edges/settlement.

**Outputs.** S0 receipt (JSON) capturing the exact digests you’ll reference later:
`virtual_rules_digest, settlement_coord_digest, cdn_weights_digest, hrsl_digest, tz_overrides_digest?, tz_nudge_digest?, tzdata_archive_digest`.

---

## S1 — Identify virtuals & build the **settlement node** (RNG-free)

**Goal.** Decide which merchants are “virtual”, then create one **settlement node** per such merchant.
**Inputs (authority).**

* **`mcc_channel_rules.yaml`** (policy; `virtual_rules_digest` recorded).
* **`virtual_settlement_coords.csv`** with evidence URLs (governed; `settlement_coord_digest`).

**Algorithm essentials.**

* Flag virtuals via `mcc_channel_rules.yaml` (MCC/channel predicates).
* For each flagged merchant: create one settlement node with
  `site_id := SHA1(merchant_id, "SETTLEMENT")`, `(lat,lon)` from the CSV, and **never** use these coordinates as customer origin. 

**Outputs (egress #1).**

* **`virtual_settlement.parquet`**: `[merchant_id, site_id, tzid_settlement, lat, lon, evidence_url]`, partitioned by `fingerprint={manifest_fingerprint}`. TZID is resolved using the same tz-world/override logic you use elsewhere, pinned by the tz digests captured in S0. 

---

## S2 — Build the **CDN edge-catalogue** (HRSL sampling) (RNG-bounded)

**Goal.** Instantiate a deterministic catalogue of CDN **edge nodes** per virtual merchant with weights by country.
**Inputs (authority).**

* **`cdn_country_weights.yaml`** (`cdn_weights_digest`), giving `country_iso → weight` and a global integer scale **E** (default 500) to size the catalogue.
* **HRSL raster** (`hrsl_100m.tif`, governed; `hrsl_digest`) for coordinate sampling.

**Algorithm essentials.**

* For each virtual merchant, expand YAML weights into **E × weight_c** edge counts per country via largest-remainder rounding; total catalogue 50–800 nodes typical.
* For each edge, **sample a coordinate** from HRSL within that country under your standard governed sampler (same replayable policy as 1B): counter-based RNG (Philox), open-interval mapping, and tagged sampling indices for exact replay. Resolve `tzid_operational` for each coordinate via tz-world.

**Outputs (egress #2).**

* **`edge_catalogue/<merchant_id>.parquet`** with
  `(edge_id=SHA1(merchant_id,country_iso,idx), country_iso, tzid_operational, lat, lon, edge_weight)`.
  Record **`edge_digest_<merchant_id>`** and update **`edge_catalogue_index.csv`** (digest `edge_catalogue_index_digest`). 

**RNG posture.** This state **consumes RNG** for coordinate sampling only; capture the RNG policy name and budget in the run header (family “CDN_EDGE”). The later selection of an edge **does not** happen here (that’s 2B). 

---

## S3 — Build **CDN alias tables** & freeze the **virtual universe hash** (RNG-free)

**Goal.** Make O(1) selection structures for edges and embed a **universe hash** so 2B can detect drift.
**Algorithm essentials.**

* Per merchant, compute `p_e = edge_weight / Σ edge_weight` and build `<merchant_id>_cdn_alias.npz` (`prob, alias`).
* Compute and embed **`universe_hash = SHA256(cdn_weights_digest ∥ edge_digest ∥ virtual_rules_digest)`** inside each alias. This mirrors the physical-routing universe hash pattern so open-time drift is caught instantly. 

**Outputs (egress #3).**

* **`cdn_alias/<merchant_id>_cdn_alias.npz`**, header contains `universe_hash` + manifest digests used. 

---

## S4 — Dual-TZ semantics & CI hooks (RNG-free)

**Goal.** Declare **operational vs settlement** time-zones and wire validation hooks that will run once arrivals exist.
**What to publish.**

* **`virtual_routing_policy.json`** (per merchant): references `cdn_key_digest` (seed derivation rule for 2B), the **two TZIDs** (`tzid_settlement` from S1 and per-edge `tzid_operational` from S2), and the daily settlement **cut-off** convention (“23:59:59 in settlement zone”).
* Extend the transaction schema notes: **`ip_latitude/ip_longitude`** fields are used for virtuals (customer-facing geo), separate from physical `latitude/longitude`. Downstream pipelines coalesce appropriately. 

**CI hooks (declared here, executed after L2 exists).**

* **IP-country mix test:** empirical `ip_country` (from chosen edges) within tolerance of YAML weights over 30 days.
* **Cut-off alignment test:** last UTC timestamp per day equals settlement 23:59:59 ± 5 s. Thresholds live in `virtual_validation.yml` (digest `virtual_validation_digest`). 

---

## S5 — Validation bundle & PASS gate (fingerprint-scoped)

**Goal.** Seal 3B so downstream readers can **hard-gate**.
**Bundle contents (minimum).**

* `MANIFEST.json` including: `seed, manifest_fingerprint, virtual_rules_digest, settlement_coord_digest, cdn_weights_digest, edge_catalogue_index_digest, cdn_alias_index_digest?, hrsl_digest, tz_index_digest?, tzdata_archive_digest?, cdn_key_digest, virtual_validation_digest`.
* Checksums for all published egress (edge catalogue files + alias files + settlement table), coverage counts (edges per country), and a legality summary (all edges resolve a single `tzid_operational`).
* `index.json` + **`_passed.flag`** (ASCII-lex over `index.json` entries, flag excluded). **Consumers: no PASS → no read.**

---

## Cross-state invariants (what keeps this green)

* **Authority & identity.** All 3B artefacts bind to `{seed, fingerprint}`; **path tokens must byte-equal embedded lineage**. Do not hard-code paths; rely on your registry + dictionary. 
* **RNG boundary.** Only **S2** consumes RNG (HRSL sampling). 2B will later consume RNG to **select an edge** at route time using `cdn_key_digest` and the alias files you froze here. 
* **Universe hash discipline.** CDN alias embeds `SHA256(cdn_weights_digest ∥ edge_digest ∥ virtual_rules_digest)` so 2B can fail fast on drift. 
* **Dual-TZ semantics.** Each row will carry both an **apparent** local offset (from the chosen edge’s zone) and a **settlement** UTC mapping for cut-offs; this split is explicitly documented and drives later CI. 
* **Fallbacks for zero support.** If a country’s HRSL has **zero support**, fall back to the pinned population raster, tagging the fallback and recording its digest (same policy used upstream). 

## Failure vocabulary (deterministic aborts)

* `VirtualRuleDigestMismatch` (mcc rules file digest mismatch). 
* `SettlementCoordMissing` / `SettlementTZIDResolveError`.
* `EdgeCatalogueDrift` (index digest mismatch or missing `edge_digest_<merchant_id>`). 
* `EdgeTZIDResolveError` (edge coord returns 0 or >1 owners after nudge/override flow). 
* `AliasUniverseHashMismatch` (alias open hash ≠ recomputed). 

---

### Why this is practical to implement

* It matches your **narrative**: settlement node → edge-catalogue → CDN alias → dual TZ → PASS, with specific bytes and digests to freeze.
* It keeps the **RNG line crisp** (S2 only), leaving per-event draws to 2B (edge selection keyed by policy). 
* The **validation hooks** (ip-country tolerance, settlement cut-off alignment) are declared here and governed by a YAML with a tracked digest, so reviewers can tighten thresholds **without code changes**. 
