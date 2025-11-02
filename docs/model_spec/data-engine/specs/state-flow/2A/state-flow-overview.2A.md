# 2A — Deriving the civil time zone (state-overview, 6 states)

## S0 — Gate & environment seal (RNG-free)

**Goal.** Pin identities and prove we’re allowed to read inputs.
**Inputs (authority).**

* **`site_locations`** (1B egress; consumed by 2A) — ID→Schema from 1B; path/partition law `[seed, fingerprint]`; order-free.
  **What to assert now.**
* Schema conformance, **path↔embed equality**, partitions, writer sort; and verify 1B’s **validation bundle + `_passed.flag`** via the Dataset Dictionary before any read (**No PASS → No Read**).
  **Outputs.** Gate receipt (`s0_gate_receipt_2A`) and mandatory sealed-inputs inventory (`sealed_inputs_v1`), both fingerprint-scoped.
  **Determinism.** Fix `{seed, manifest_fingerprint}`; record artefact digests context at the run header.

---

## S1 — TZ polygon lookup (STR-tree + deterministic tie-break) (RNG-free)

**Goal.** Map each `(lat,lon)` to a **provisional `tzid`** via tz-world polygons; break border ties deterministically.
**Inputs.**

* **`site_locations`** (coords) from 1B. 
* **`tz_world_2025a`** polygons (GeoParquet), **EPSG:4326**, governed in ingress. Build a deterministic **STR-tree** and capture its digest in the manifest (`tz_index_digest`).
  **Algorithm essentials.**
* STR-tree shortlist → `prepared_polygon.contains(point)`; **0 owners ⇒ `TimeZoneLookupError`**, **2 owners ⇒ ε-nudge tie-break** with ε from governed `tz_nudge.yml`. Persist `nudge_lat/nudge_lon`.
  **Outputs.**
* **`s1_tz_lookup`** (plan table; proposed): key `[merchant_id, legal_country_iso, site_order]`, cols: `lat,lon, tzid_provisional, nudge_lat, nudge_lon`. Partition `[seed, fingerprint]`.
  **Determinism.** Index build order is lexicographic by `TZID`; ε comes from config (not RNG). 

---

## S2 — Overrides & finalisation (precedence: site → MCC → country) (RNG-free)

**Goal.** Apply governed **`tz_overrides.yaml`** to replace polygon results where evidence says so; emit **final `tzid`**.
**Inputs.**

* `s1_tz_lookup` (from S1).
* **`tz_overrides.yaml`** (scope, tzid, evidence_url, expiry; governed digest). Precedence: site-specific → MCC-wide → country-wide.
  **Outputs (egress #1).**
* **`site_timezones`** (egress; proposed): `[merchant_id, legal_country_iso, site_order]` + `tzid`, `tzid_source∈{polygon,override}`, `override_scope?`, `nudge_lat?`, `nudge_lon?`.
  Path family: `data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/`.
  **Checks.** override expiry valid; at least one active override still changes something (CI guard). 

---

## S3 — Build **tzdata** timetables (RLE cache) (RNG-free)

**Goal.** Freeze the **IANA zoneinfo** version and build compact per-TZID timetables for the simulation horizon.
**Inputs.**

* **`tzdata2025a`** archive (governed; `zoneinfo_version.yml`, digest). 
* Distinct `tzid` set from **`site_timezones`**.
  **Algorithm essentials.**
* Enumerate `_utc_transition_times` per TZ; write `(transition_epoch, offset_minutes)` and **run-length encode**. Record **exact cache byte size** for CI drift detection. 
  **Outputs (egress #2).**
* **`tz_timetable_cache`** (cache artefact; proposed): path `data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/` with a manifest listing `tzdata_archive_digest`, `rle_cache_bytes`, and `tz_index_digest`. 

---

## S4 — Civil-time legality & DST conformance (RNG-free)

**Goal.** Prove the **UTC↔local** mapping is unambiguous and lawful across gaps/folds; wire the **parity rule** for repeats.
**What to verify.**

* **Gap handling:** if `t_local` lies in a forward gap, shift by `Δ = (o_post−o_pre)×60` seconds; mark `dst_adjusted=True` and return gap budget to arrivals. 
* **Fold handling:** pick fold deterministically via `SHA256(global_seed‖site_id‖t_local) mod 2` (policy; still RNG-free). 
* **DST wafer tests:** for each DST site, 48-hour wafer around spring/fall: no illegal minutes, both folds present; else **abort** with reproducer pointers. 
  **Outputs.**
* **`s4_legality_report`** (validation evidence; proposed): counts, wafer failures (zero expected), coverage over all `tzid` in catalogue.

---

## S5 — Validation bundle & PASS gate (fingerprint-scoped)

**Goal.** Seal 2A outputs so 2B/3A/3B can hard-gate.
**Bundle contents (minimum).**

* MANIFEST (`seed, manifest_fingerprint, tzdata_version, tz_index_digest, tz_overrides_digest, tz_nudge_digest, rle_cache_bytes`).
* `legality_summary.json`, `coverage.json`, checksums for `site_timezones` and `tz_timetable_cache`, `index.json`, and **`_passed.flag`** = SHA-256 over files listed by `index.json` (ASCII-lex), flag excluded. **Consumers: no PASS → no read.** 

---

## Cross-state invariants (what keeps this green)

* **Inputs & lineage.** 2A reads only 1B’s `site_locations` and governed tz artefacts; all identities ride with `[seed, fingerprint]` and **path↔embed equality** holds.
* **RNG posture.** 2A is **RNG-free**. (Fold parity uses a hash function on fixed inputs; no random draws.) 
* **STR-tree reproducibility.** You record a binary **index digest** (`tz_index_digest`) to prove identical structure across machines. 
* **Override governance.** All overrides/evidence are digested; CI asserts they’re not obsolete. 
* **Zoneinfo pin.** Timetables come from a **pinned `tzdata20xxa`** archive recorded in the manifest. 

## Failure vocabulary (examples; deterministic aborts)

* `TimeZoneLookupError` (zero owners), `DSTLookupTieError` (post-nudge still double-owned), `ZoneMismatchError` / `TimeTableCoverageError` (legality coverage). All are **hard fail, no partial publish**.

---

### Why this is practical for implementation

* It matches your **ingress authorities** (tz-world, tzdata) and the **1B→2A hand-off** (`site_locations`).
* It produces exactly the two things downstream need: a **per-site `tzid` egress** and a **compact tz timetable cache**, both sealed by a **PASS bundle**. 
* The **DST edge passer** and **legality checks** are where bugs actually surface; keeping them pre-egress makes failures unambiguous and reproducible. 
