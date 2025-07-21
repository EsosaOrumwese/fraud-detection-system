## Assumptions

Below is the full expository record of every premise, data‑source dependency, numerical convention, guard‑rail and deterministic rule that governs **“Deriving the civil time zone.”** Nothing is implicit: each statement names the artefact that stores the value, the code point that consumes it, the validation that defends it, and the effect a change would cause. Every artefact mentioned is tracked in the repository with its SHA‑256 digest baked into the dataset manifest so that any alteration forces a rebuild and triggers CI scrutiny.

---

### 1 Authoritative polygon source and reproducible spatial index

The shapefile and its companion files (`tz_world_2025a.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`) reside under `artefacts/priors/tz_world/2025a/`. Each file declares metadata `semver` and `sha256_digest` under manifest keys `tz_world_shp_digest`, `tz_world_shx_digest`, etc., aggregated into `tz_polygon_digest`; Fiona must open them with CRS EPSG:4326 or the build aborts. All polygons load in lexical order by `TZID` into an STR‑tree; the index is serialized via Python 3.10’s pickle protocol 5, hashed with SHA‑256 (not MD5), and stored as `tz_index_digest`, ensuring consistent index reproduction across environments.

---

### 2 Deterministic point‑to‑zone mapping with numerically safe tie‑break

Each site coordinate is filtered through STR‑tree and then `prepared_polygon.contains`. Zero hits raise `TimeZoneLookupError` (latitude, longitude, `prior_tag`), halting the build. Two hits trigger a deterministic nudge: let \$x\$ be the coordinate and \$c\$ the centroid of the smaller polygon; \$x' = x + ε,(c-x)/|c-x|\$, where ε is read from `config/timezone/tz_nudge.yml` (fields `semver`, `sha256_digest`, `nudge_distance_degrees: 0.0001`). That file’s digest is recorded as `tz_nudge_digest` and any ε change bumps semver. The nudge vector (`nudge_lat`, `nudge_lon`) is persisted per site for forensic replay.

---

### 3 Manual override governance

The governed artefact `config/timezone/tz_overrides.yaml` (fields `semver`, `sha256_digest`, `overrides`) lists entries with `scope` (`country:CA` | `mcc:6011` | \[`merchant_id`,`site_id`]), `tzid`, `evidence_url`, and `expiry_yyyy_mm_dd`. Git pre‑commit validates URL and date formats. Nightly CI reloads the site catalogue, reapplies overrides in specificity order (site → MCC → country), and asserts at least one row would change compared to polygon‐only lookup; zero differences block the merge. Any modification updates `tz_overrides_digest`.

---

### 4 Pinning the civil‑rule timeline

The tzdata archive `artefacts/priors/tzdata/tzdata2025a.tar.gz` is declared in `zoneinfo_version.yml` (`semver`, `tzdata_version: tzdata2025a`) and its SHA‑256 is recorded as `tzdata_archive_digest`. The code loads zones via `zoneinfo.ZoneInfo`. For each `TZID` in the catalogue, the engine extracts `(transition_epoch, offset_minutes)`, truncates the arrays to the configured horizon `[sim_start, sim_end]` (values read from `config/timezone/simulation_horizon.yml`, fields `semver`, `sha256_digest`, `sim_start_iso8601`, `sim_end_iso8601`, stored as `tz_horizon_digest`), applies run‑length encoding, and stores as bytes. CI asserts that `tz_cache_bytes` (manifest field) remains < 8 MiB; any increase triggers a build failure.

---

### 5 Legality filter for local timestamps

When the LGCP sampler proposes a local epoch second \$t\_{\text{local}}\$, the engine locates the most recent transition \$t\_i\$ and offset \$o\_i\$.

* If \$t\_{\text{local}}\$ lies in the forward gap \$(t\_i, t\_i+\Delta)\$, with \$\Delta=(o\_{i+1}-o\_i)\times60\$ (seconds difference of pre/post offsets), it resets \$t\_{\text{local}}\$ to \$t\_i+\Delta\$, sets `dst_adjusted=True`, computes `gap_seconds = (t_i+\Delta) - t_{\text{local}}`, and returns `surplus_wait=gap_seconds` for the arrival engine.
* If \$t\_{\text{local}}\$ lies in the fall‑back fold, it computes \$h=\mathrm{SHA256}(\mathit{global\_seed}\parallel\mathit{site\_id}\parallel t\_{\text{local}})\$ and sets `fold = h[0]\bmod2`.

These definitions ensure pure functions of immutable inputs.

---

### 6 Computation and storage of the UTC offset

After legality adjustment, the engine records:

```
event_time_utc    = floor((t_local - o*60) * 1000)    (int64, milliseconds since epoch)  
local_time_offset = o                                (int16, minutes)  
dst_adjusted      = {0|1}                            (bool)  
fold              = {0|1} or NULL                    (int8)  
```

Sub‑millisecond fractions in `event_time_utc` are truncated to align with Parquet logical type `TIMESTAMP_MILLIS`.

---

### 7 Error‑handling contract

On validation failures—`TimeZoneLookupError`, `ZoneMismatchError`, or `TimeTableCoverageError`—the engine raises the corresponding exception, cleans up temporary files, flushes audit logs, and aborts without writing any new site rows. This atomic rollback ensures no partial or corrupted outputs persist.

---

### 8 Random‑number‑stream independence

Fold‑bit hashing reads `global_seed` but not Philox counters, preserving RNG isolation. The formal proof in `docs/rng_proof.md` (SHA‑256 in manifest as `rng_proof_digest`) documents this property and is version‑controlled.

---

### 9 Memory‑safety and timetable horizon

The engine refuses to cache transitions outside `[sim_start, sim_end]`, raising `TimeTableCoverageError` on first access beyond those bounds. This forces explicit regeneration with updated horizon or tzdata version and captures the update in the manifest.

---

### 10 Licence provenance and data privacy

All shapefiles and tzdata archives carry licences in `LICENSES/` (CC BY 4.0 for `tz_world`, public domain for IANA). No personal data is used, so GDPR/CCPA concerns are addressed; see data‑provenance appendix.

---


## Appendix A – Mathematical Definitions & Conventions

### A.1 Run‑Length Encoding (RLE) of Transition Tables

**Purpose:** compress repeated offset values in the timetable.
**Code:** `timezone/cache.py:encode_rle`
**Artefact:** in‑memory Python bytes stored in the singleton `tz_cache`.

Given an array of length‑$n$ offsets in minutes

$$
V = [v_1, v_2, \dots, v_n],\quad v_i\in\mathbb{Z}\ \text{(minutes)}
$$

define runs $\{(c_j,\ell_j)\}_{j=1}^m$ where

$$
k_1 = 1,\quad k_{j+1} = k_j + \ell_j,
$$

$$
c_j = v_{k_j},\quad
\ell_j = \max\{\,r\ge1 : v_{k_j+r-1}=v_{k_j}\}
$$

Store two arrays:

$$
C = [c_1,\dots,c_m]\quad(\mathrm{int16}),\quad
L = [\ell_1,\dots,\ell_m]\quad(\mathrm{int32}).
$$

**Example:**

$$
V=[0,0,0,60,60,120,120,120]\;\longrightarrow\;
C=[0,60,120],\;L=[3,2,3].
$$

---

### A.2 Simulation Horizon Conversion & Truncation

**Files:**

* `config/timezone/simulation_horizon.yml`
  (fields `sim_start_iso8601`, `sim_end_iso8601`, `semver`, `sha256_digest`)
* Manifest key: `tz_horizon_digest`

Parse ISO 8601 bounds to integer seconds:

$$
s = \bigl\lfloor\mathrm{parseISO}(\mathtt{sim\_start\_iso8601})\times10^3\bigr\rfloor,
\quad
e = \bigl\lfloor\mathrm{parseISO}(\mathtt{sim\_end\_iso8601})\times10^3\bigr\rfloor
$$

($\mathrm{parseISO}$ returns seconds since epoch).
Given full transition list $\{t_i\}$ (int64 seconds), truncate:

$$
T = \{\,t_i : s \le t_i \le e\}.
$$

These $T$ feed into RLE (A.1).

---

### A.3 Forward‑Gap Duration $\Delta$

**Code:** `timezone/local_time.py:compute_gap`
**Definition:**
For each DST transition index $i$, let

$$
o_i,\;o_{i+1}\in\mathbb{Z}\quad(\text{minutes}),
$$

then

$$
\Delta = (o_{i+1} - o_i)\times60
\quad(\text{seconds}).
$$

**Stored as:** `gap_seconds` (int64).
**Example:** $o_i=120$, $o_{i+1}=180$ min ⇒ $\Delta=(180-120)\times60=3600$ s (1 h).

---

### A.4 Local‑to‑UTC Conversion & Gap Adjustment

**Code:**

* `timezone/local_time.py:to_utc`
* `timezone/local_time.py:adjust_gap`

Given local epoch second $t_{\mathrm{local}}$ and offset $o_i$ (minutes):

1. **Naïve UTC**

   $$
     t_{\mathrm{utc}} = t_{\mathrm{local}} - 60\,o_i
     \quad(\text{seconds})
   $$

2. **Forward‑Gap Case** ($t_i < t_{\mathrm{local}} < t_i+\Delta$):

   $$
     t_{\mathrm{utc}} = t_i + \Delta,\quad
     \mathrm{dst\_adjusted} = 1,\quad
     \mathrm{gap\_seconds} = (t_i + \Delta) - t_{\mathrm{local}}.
   $$

3. **Fall‑Back Fold Case** (disambiguation in A.5).

---

### A.5 Fall‑Back Fold‑Bit Hashing

**Code:** `timezone/local_time.py:determine_fold`
**Artefacts:**

* `manifest.json` → `global_seed` (128‑bit hex)
* `docs/rng_proof.md` → `rng_proof_digest`

Let
$\mathtt{seed}\in\{0,1\}^{128}$,
$\mathtt{site\_id}\in\text{UTF-8 bytes of zero‑padded ID}$,
$t_{\mathrm{local}}\in\mathbb{Z}$ ($\mathrm{ms}$ since epoch).
Concatenate big‑endian bytes:

$$
B = \mathtt{seed}\,\|\,\mathtt{site\_id}\,\|\,\mathrm{BE}_{8}(t_{\mathrm{local}}).
$$

Compute

$$
h = \mathrm{SHA256}(B)\in\{0..255\}^{32},\quad
\mathrm{fold} = h[0]\bmod2\in\{0,1\}.
$$

**Example:** If $h[0]=0x8A=138$, then $\mathrm{fold}=0$.

---

### A.6 Event Time Storage in Parquet

**Schema:**

```yaml
event_time_utc:
  type: INT64
  logicalType: TIMESTAMP_MILLIS
```

**Computation:**

$$
\mathrm{event\_time\_utc}
=\bigl\lfloor (t_{\mathrm{local}} - 60\,o)\times10^3\bigr\rfloor
\quad(\text{milliseconds since epoch}).
$$

Sub-millisecond fractions are truncated.

---

### A.7 Memory Gauge & Cache Limit

**Code:** `timezone/cache.py:gauge_memory`
**Manifest Field:** `tz_cache_bytes` (int64)
**CI Rule:**

$$
\mathrm{tz\_cache\_bytes} = \mathrm{sizeof}(tz\_cache)\quad(\text{bytes}),
\qquad
\text{assert }\mathrm{tz\_cache\_bytes}<8\times2^{20}.
$$

If violated, raise `TimeTableCoverageError`.

---

### A.8 Exception Types & Atomic Rollback

| Exception                | Trigger                                      | Effect                       |
| ------------------------ | -------------------------------------------- | ---------------------------- |
| `TimeZoneLookupError`    | no polygon contains point                    | abort build, no rows written |
| `DSTLookupTieError`      | two polygons after nudge                     | abort build, no rows written |
| `TimeTableCoverageError` | cache limit breach or access outside `[s,e]` | abort build, no rows written |

On any exception, clean up `*.parquet.tmp`, flush audit logs, and exit atomically.

---

## Governed Artefact Registry

Append the table below to the end of **Assumptions.txt**. Every entry must appear in `spatial_manifest.json` (or the main manifest) with the listed metadata; any change to the file, its semver field or its digest triggers a new manifest digest and CI enforcement.

| ID / Key                       | Path Pattern                                       | Role                                                 | Semver Field                 | Digest Field                                                                                                                                          |
| ------------------------------ | -------------------------------------------------- | ---------------------------------------------------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **tz\_world\_polygons\_2025a** | `artefacts/priors/tz_world/2025a/tz_world_2025a.*` | IANA time‑zone polygon shapefile and companion files | `semver` (in sidecar)        | `tz_world_shp_digest`, `tz_world_shx_digest`, `tz_world_dbf_digest`, `tz_world_prj_digest`, `tz_world_cpg_digest` aggregated into `tz_polygon_digest` |
| **tz\_nudge**                  | `config/timezone/tz_nudge.yml`                     | Deterministic nudge distance ε                       | `semver`                     | `tz_nudge_digest`                                                                                                                                     |
| **tz\_overrides**              | `config/timezone/tz_overrides.yaml`                | Manual mapping overrides for exceptional zones       | `semver`                     | `tz_overrides_digest`                                                                                                                                 |
| **zoneinfo\_version**          | `zoneinfo_version.yml`                             | IANA tzdata version descriptor                       | `semver` (`tzdata_version`)  | `tz_horizon_digest` (see horizon below)                                                                                                               |
| **tzdata\_archive**            | `artefacts/priors/tzdata/tzdata2025a.tar.gz`       | Official IANA tzdata release archive                 | (in `zoneinfo_version.yml`)  | `tzdata_archive_digest`                                                                                                                               |
| **simulation\_horizon**        | `config/timezone/simulation_horizon.yml`           | Simulation start/end bounds for timeline extraction  | `semver`                     | `tz_horizon_digest`                                                                                                                                   |
| **rng\_proof**                 | `docs/rng_proof.md`                                | Formal proof of RNG‑stream isolation                 | Git commit (ref in manifest) | `rng_proof_digest`                                                                                                                                    |

**Notes:**

* The `tz_world_polygons_2025a.*` pattern covers `.shp`, `.shx`, `.dbf`, `.prj` and `.cpg`; each must declare `semver` and `sha256_digest` in its sidecar or manifest entry.
* The `zoneinfo_version.yml` file holds both the tzdata version string and governs horizon defaults; its `tz_horizon_digest` covers both the tzdata version and the simulation bounds.
* Any addition, removal, or version bump of these artefacts must follow semver rules and will automatically refresh the overall manifest digest via CI.
* Pattern matching is case‑sensitive; path separators use Unix‑style forward slashes.

