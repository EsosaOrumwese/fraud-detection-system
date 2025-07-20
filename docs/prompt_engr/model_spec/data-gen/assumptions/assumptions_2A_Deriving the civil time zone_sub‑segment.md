Below is the full expository record of every premise, data source, numerical convention, guard‑rail and deterministic rule that governs **“Deriving the civil time zone.”** Nothing is left implicit: each statement names the artefact that stores the value, the code point that consumes it, the validation that defends it, and the knock‑on effect a change would cause. Every artefact mentioned here is already tracked in the repository; each has its SHA‑256 digest baked into the dataset manifest so that any alteration forces a rebuild and triggers continuous‑integration scrutiny.

---

### 1 Authoritative polygon source and reproducible spatial index

The only accepted legal mapping between geography and civil time is the shapefile **`tz_world_2025a.shp`** together with its companion files; the catalogue manifest key `tz_polygon_digest` preserves the shapefile’s SHA‑256. The file must report EPSG:4326 when opened via *Fiona*; a mismatch aborts the build. All polygons are loaded in lexical order by `TZID` and inserted into an STR‑tree. Because insertion order changes STR‑tree packing, determinism is guaranteed by that lexical ordering. An MD5 of the pickled STR‑tree is computed and stored as `tz_index_digest`; re‑runs reproduce bit‑for‑bit.

---

### 2 Deterministic point‑to‑zone mapping with numerically safe tie‑break

Every site coordinate is first filtered through STR‑tree bounding‑box search, then through `prepared_polygon.contains`. Zero‑hit outcome raises `TimeZoneLookupError` and halts the build because the site location must be invalid. Two‑hit outcome triggers the deterministic nudge: let $x$ be the coordinate, $P_\text{small}$ the smaller of the two candidate polygons, $c$ its centroid, and ε read from **`tz_nudge.yml`**; compute $x' = x + ε\frac{(c-x)}{\|c-x\|}$. The numerical value ε defaults to `0.0001_degree`; changing it modifies the manifest hash and invalidates all previously built downstream data. The vector components `nudge_lat`, `nudge_lon` are persisted per site for forensic reproduction.

---

### 3 Manual override governance

The registry **`tz_overrides.yaml`** contains structured objects:

```
scope:  country:CA | mcc:6011 | [merchant_id, site_id]
tzid:   America/Toronto
evidence_url: https://housebill.ca/…
expiry_yyyy_mm_dd: 2027-03-31
```

Git pre‑commit forbids empty `evidence_url` or `expiry`; nightly CI reloads the entire site catalogue, reapplies overrides, and checks that at least one row differs from the polygon‑only lookup. Zero differences imply obsolescence, blocking the merge until the stale override is deleted. Overrides cascade by specificity—site, then MCC, then country—and never stack; the first match wins.

---

### 4 Pinning the civil‑rule timeline

The civil‑rule timeline is extracted from the **IANA tzdata release whose literal version string lives in `zoneinfo_version.yml`** (initial value `tzdata2025a`). The code instantiates each `TZID` via `zoneinfo.ZoneInfo`. For every zone appearing in the catalogue the engine iterates transition datetimes, converts them to epoch seconds, and collects `(transition_epoch, offset_minutes)`. It truncates to `[sim_start, sim_end]`. The resulting arrays are run‑length encoded and stored in RAM during generation; their total memory footprint in bytes is written into the manifest field `tz_cache_bytes`. CI asserts that this footprint remains < 8 MiB; an unexpected jump points to database bloat or a logic error.

---

### 5 Legality filter for local timestamps

When the arrival engine later offers a local epoch second $t_{\text{local}}$ for a given site, the timetable is bisection‑searched:

\* If $t_{\text{local}}$ lies strictly in the forward gap $(t_i, t_i+\Delta)$ the engine rewrites it to $t_i+\Delta$, sets `dst_adjusted=True`, stores `gap_seconds = t_i+\Delta - t_{\text{local}}`, and returns `surplus_wait = gap_seconds` to the LGCP sampler so the inter‑arrival distribution remains intact.
\* If $t_{\text{local}}$ lies in the repeated fold hour $[t_i-\Delta, t_i)$ the engine chooses the fold bit by hashing `(global_seed, site_id, t_{\text{local}})` with SHA‑256, taking parity of the first byte. `fold` is set to 0 for the first occurrence, 1 for the second. The hash’s dependence on the global seed ensures global‑replay determinism.

Both decisions are pure functions of immutable inputs; no randomness beyond the seed enters.

---

### 6 Computation and storage of the UTC offset

After legality adjustment, the engine looks up the most recent offset $o$ in minutes and records

```
event_time_utc      = t_local - 60*o          (int64)
local_time_offset   = o                      (int16)
dst_adjusted        = {0|1}                  (bool)
fold                = {0|1} or NULL          (int8)
```

`event_time_utc` is stored as microseconds since Unix epoch in Parquet INT64 (`TIMESTAMP_MILLIS`) for Spark compatibility. `fold` is NULL except in repeat‑hour cases; this preserves bijection between UTC and civil time without bloating every row.

---

### 7 Validation chain

A Monte‑Carlo validator samples 1 000 000 rows from every nightly build, reconstructs `t_local` via `event_time_utc + 60*local_time_offset` and uses `tz_world_2025a` to infer the polygon zone. If the polygon `TZID` differs from the row’s `TZID`, and if no override covers the discrepancy, the validator raises `ZoneMismatchError` and CI fails. The validator separately counts rows flagged `dst_adjusted` or `fold` to produce reference rates; a spike greater than 2× the historical 30‑day mean triggers a manual review, preventing silent error cascades.

---

### 8 Random‑number‑stream independence

Although civil‑time logic is mostly deterministic, the fold parity hash reads the global seed but not the Philox counter. This satisfies stream isolation: changes in the order or quantity of random numbers drawn elsewhere do not alter fold assignment. `rng_proof.md` documents that property formally.

---

### 9 Memory‑safety and timetables beyond horizon

The timetable builder refuses to cache transitions that fall strictly outside `[sim_start, sim_end]`. If a developer extends the simulation horizon without regenerating timetables, the engine raises `TimeTableCoverageError` on the first lookup beyond coverage. The safeguard forces explicit regeneration with a new IANA version string or a new end date, thereby capturing the update in the manifest.

---

### 10 Licence provenance and legal sufficiency

`tz_world_2025a.shp` carries the CC‑BY 4.0 licence; the IANA tzdata and zoneinfo files are in the public domain under the IANA licence. Both licences are recorded verbatim in `LICENSES/`. Because no per‑person data flows into this stage, GDPR and CCPA concerns are nil; this premise is documented in the data‑provenance appendix.

---

Every constant—numerical or conceptual—now exists as a named artefact with a clear storage path and validation guard; every external dependency is version‑pinned; every edge path is deterministic; every concordance test is automated. Consequently, an implementation team can read this document and implement the stage verbatim without discovering hidden rules later, and an auditor can mutate any artefact, regenerate the build, and trace the impact through the manifest hash and CI reports.
