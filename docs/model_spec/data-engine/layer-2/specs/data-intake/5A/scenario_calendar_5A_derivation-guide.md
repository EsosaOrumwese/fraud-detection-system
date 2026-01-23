## Derivation / Authoring Guide — `scenario_calendar_5A` (5A.S4 event list, non-toy v1)

### 0) Purpose

`scenario_calendar_5A` is the **sealed scenario event table** that 5A.S4 uses to apply overlays on top of baseline intensities. It must be:

* **Codex-no-input** (fully determinable from sealed upstream artefacts),
* **non-toy** (realistic volume, coverage, and diversity),
* **fail-closed** (no guessing if inputs don’t line up),
* **time-axis consistent** with `scenario_horizon_config_5A` and `scenario_overlay_policy_5A`.

> Contract note: the **path** for this artefact is pinned in the 5A contracts to `config/layer2/5A/scenario/calendar/...` and must not be relocated without updating those contracts.

---

### 1) Identity and output location (MUST)

* **Artefact ID:** `scenario_calendar_5A`
* **Format:** Parquet
* **Schema anchor:** `schemas.5A.yaml#/scenario/scenario_calendar_5A` *(permissive; this guide pins the real contract)*
* **Path template:**
  `config/layer2/5A/scenario/calendar/fingerprint={manifest_fingerprint}/scenario={scenario_id}/scenario_calendar_5A.parquet`
* **Partition keys:** `manifest_fingerprint`, `scenario_id`
* **Primary key:** `(manifest_fingerprint, scenario_id, event_id)`
* **Token-less posture:** do **not** embed any file digests inside the parquet; the sealing inventory records them.

---

### 2) Required columns (pinned by this guide)

Write exactly these columns (no extras) so S4 can be decision-free:

**Identity**

* `manifest_fingerprint` (string)
* `scenario_id` (string)
* `event_id` (string; stable; unique per scenario)

**Event definition**

* `event_type` (string; one of: `HOLIDAY`, `PAYDAY`, `CAMPAIGN`, `OUTAGE`, `STRESS`)
* `start_utc` (RFC3339 micros, `...Z`) — inclusive
* `end_utc` (RFC3339 micros, `...Z`) — exclusive
* `shape_kind` (string; one of: `constant`, `ramp`)

**Shape parameters**

* `amplitude` (float; used when `shape_kind=constant`, else null)
* `amplitude_peak` (float; used when `shape_kind=ramp`, else null)
* `ramp_in_buckets` (int; used when `shape_kind=ramp`, else null)
* `ramp_out_buckets` (int; used when `shape_kind=ramp`, else null)

**Scope predicates** (nullable, except global)

* `scope_global` (bool)
* `country_iso` (string nullable; ISO2)
* `tzid` (string nullable; IANA tzid)
* `demand_class` (string nullable; must match `merchant_class_policy_5A` catalog)
* `merchant_id` (uint64 nullable)

**Optional audit**

* `notes` (string nullable; deterministic; no timestamps)

---

### 3) Required inputs (MUST exist; fail closed)

Codex must read:

1. `scenario_horizon_config_5A`

   * provides `scenario_id`, `horizon_start_utc`, `horizon_end_utc`, `bucket_duration_minutes`, `is_baseline/is_stress`.

2. `scenario_overlay_policy_5A`

   * provides allowed `event_type` vocabulary, allowed `shape_kind`s, amplitude bounds per type, scope rules, and max event thresholds.

3. `merchant_class_policy_5A`

   * provides the authoritative set of `demand_class` IDs.

4. Upstream universes (for coverage + non-toy generation)

   * `zone_alloc` (3A) to get the set of `legal_country_iso` and `tzid` actually present in this run.

If any is missing → **FAIL CLOSED**.

---

### 4) Time axis rules (MUST)

All event timestamps MUST be:

* UTC (`Z`)
* **bucket-aligned** to the horizon grid:

  * seconds = 0, micros = 0
  * minute-of-hour divisible by `bucket_duration_minutes`

Also:

* `start_utc < end_utc`
* event interval must intersect the horizon window (else drop)
* **recommended**: clamp event interval to horizon bounds (but record the unclamped intent in `notes` if you do)

---

### 5) Scope rules (MUST; mirror overlay policy)

Each row MUST satisfy:

* At least one predicate is present:

  * either `scope_global=true` OR any of (`country_iso`, `tzid`, `demand_class`, `merchant_id`) non-null.
* If `scope_global=true`:

  * all other scope fields MUST be null.
* If `merchant_id` is non-null:

  * `country_iso`, `tzid` MUST be null (merchant scope is exclusive).
* `country_iso` must match ISO2 uppercase.
* `tzid` must be a valid IANA tzid and must exist in this run’s `tzid` universe.
* `demand_class` must exist in the class catalog.

Violations → **FAIL CLOSED**.

---

### 6) Pinned event-id law (MUST; decision-free)

Compute `event_id` as:

* Build canonical string (UTF-8, LF, no spaces):

  ```
  type=<event_type>
  start=<start_utc>
  end=<end_utc>
  shape=<shape_kind>
  amp=<amplitude_or_null>
  peak=<amplitude_peak_or_null>
  rin=<ramp_in_or_null>
  rout=<ramp_out_or_null>
  global=<0/1>
  country=<country_or_null>
  tzid=<tzid_or_null>
  class=<demand_class_or_null>
  merchant=<merchant_id_or_null>
  ```
* `h = SHA256(canonical_bytes)`
* `event_id = "EVT-" + hex(h[0:12])`  *(12 bytes → 24 hex chars)*

If a collision ever occurs (shouldn’t), append `"-2"`, `"-3"` deterministically by checking existence and incrementing.

---

### 6.1 Placeholder resolution (MUST)

The angle-bracket tokens in the canonical string are placeholders for the row's actual values:

* `<event_type>` is the row's `event_type`.
* `<start_utc>` and `<end_utc>` are the row's UTC timestamps.
* `<shape_kind>` is the row's `shape_kind`.
* `<amplitude_or_null>`, `<amplitude_peak_or_null>`, `<ramp_in_or_null>`, `<ramp_out_or_null>` are the row values, rendered as `null` if absent.
* `<country_or_null>`, `<tzid_or_null>`, `<demand_class_or_null>`, `<merchant_id_or_null>` are rendered as `null` when the corresponding field is null.

Use the exact string rendering shown (no extra spaces) to keep hashes stable.

---

### 7) Deterministic generation algorithm (v1; non-toy)

#### 7.1 Setup

From `zone_alloc`, derive:

* `C = sorted(unique legal_country_iso)`
* `T = sorted(unique tzid)`

From horizon config:

* `H0 = horizon_start_utc`, `H1 = horizon_end_utc`
* `bucket_minutes`
* `scenario_id`, `is_baseline`, `is_stress`

From class catalog:

* `CL = set(demand_class ids)`

Define helper deterministic `u_det(stage, key...)`:

* `msg = UTF8("5A.calendar|" + scenario_id + "|" + stage + "|" + "|".join(keys) )`
* `x = uint64_be(SHA256(msg)[0:8])`
* `u = (x + 0.5)/2^64` in `(0,1)`

#### 7.2 PAYDAY events (country + demand_class scoped, ramp)

Goal: **monthly**, broad coverage, realistic uplift around paydays.

For each country `c ∈ C`, for each month intersecting `[H0,H1)`:

* determine payday day-of-month deterministically:

  * choose from `{15, 25, last_day}` using `u_det("payday_rule", c, YYYY-MM)`
* adjust if falls on weekend (Sat/Sun): shift back to Friday (deterministic)
* create a 48-hour window:

  * start at `00:00Z` on payday date
  * end at `00:00Z` + 48h
* create **3 demand_class-scoped rows** (non-toy heterogeneity):

  * `consumer_daytime` peak 1.25
  * `evening_weekend` peak 1.20
  * `online_24h` peak 1.30
    *(If any of those classes don’t exist in `CL`, fail closed — this forces taxonomy stability.)*
* `shape_kind=ramp`
* `ramp_in_buckets = max(2, 6 hours worth of buckets)`
* `ramp_out_buckets = max(4, 24 hours worth of buckets)`

#### 7.3 HOLIDAY events (country + demand_class scoped, constant)

Goal: frequent enough to matter, not “toy 2 holidays/year”.

For each country `c ∈ C`, for each month intersecting horizon:

* generate `n_holidays_month = 1 + (u_det("holiday_count", c, YYYY-MM) < 0.60)`
  (≈ 1–2 holidays per month per country)
* choose day-of-month deterministically (avoid payday window; avoid duplicates)
* window: 24 hours (`00:00Z` to `00:00Z+24h`)
* create **3 demand_class-scoped rows** with amplitudes within HOLIDAY bounds:

  * `office_hours` amplitude 0.65
  * `consumer_daytime` amplitude 0.85
  * `online_24h` amplitude 1.03
* `shape_kind=constant`

#### 7.4 CAMPAIGN events (global/country + demand_class scoped, ramp)

Goal: include real marketing bursts; heavier for stress scenarios.

Create:

* **Global online campaigns**: 1 per month within horizon

  * scope: `scope_global=true`, `demand_class=online_bursty`
  * duration: 7 days
  * peak amplitude:

    * baseline: 1.35
    * stress: 1.80
  * `shape_kind=ramp`, ramp in/out = 24h each

Plus **major-market campaigns** (stress only):

* pick top `K=20` countries deterministically by `u_det("major_market_rank", c)` (stable)
* for each selected country: 1 campaign within horizon

  * scope: `country_iso=c`, `demand_class=online_24h`
  * peak 1.55
  * duration 5 days, ramp 12h in/out

#### 7.5 OUTAGE events (tzid scoped, constant)

Goal: rare disruptions.

Let `N_outage = ceil(days(horizon) * 0.6)` (≈ 0.6 outages/day globally).
For `i=1..N_outage`:

* pick tzid: `tzid = T[ floor(u_det("outage_tzid", str(i)) * |T| ) ]`
* pick start bucket: `h = floor(u_det("outage_start", tzid, str(i)) * H)`
* duration: choose from {2h, 4h, 8h} deterministically
* amplitude = 0.05
* scope: `tzid=...` only
* `shape_kind=constant`

#### 7.6 STRESS events (stress only, constant)

If `is_stress=true`, generate **2–4** stress windows:

* 1 global stress window (14–21 days) with amplitude 1.60
* 1–3 country stress windows (7–14 days) for deterministically chosen countries with amplitude 1.85
* scope: global OR country only
* `shape_kind=constant`

---

### 8) Validation checklist (MUST; fail closed)

After generating, Codex MUST validate:

**8.1 Schema/field validity**

* All columns present, correct types, no extra columns.
* Every event type is in overlay policy vocab.
* Shape params are consistent with `shape_kind`.
* Amplitudes respect per-type bounds from `scenario_overlay_policy_5A`.

**8.2 Horizon validity**

* All `start_utc/end_utc` bucket-aligned.
* Every event intersects horizon (drop non-intersecting rows; if too many drop, fail).

**8.3 Scope validity**

* Scope rules from §5 all satisfied.
* For `country_iso`: must be in `C`.
* For `tzid`: must be in `T`.
* For `demand_class`: must be in `CL`.

**8.4 Uniqueness**

* `(manifest_fingerprint, scenario_id, event_id)` unique.

**8.5 Non-toy realism floors**
Let `D = horizon_days`, `|C| = #countries`, `H = #horizon buckets`.

MUST satisfy:

* Event count per scenario:
  `2000 ≤ N_events ≤ max_events_per_scenario` (from overlay policy)
* Coverage:

  * PAYDAY events exist for ≥ 90% of countries present in `C`
  * HOLIDAY events exist for ≥ 90% of countries present in `C`
* Diversity:

  * at least 3 event types present in baseline scenarios (`PAYDAY`, `HOLIDAY`, and one of `CAMPAIGN/OUTAGE`)
  * in stress scenarios: all of `PAYDAY`, `HOLIDAY`, `CAMPAIGN`, `OUTAGE`, `STRESS` present
* Overlap guard (cheap check):

  * sample exactly 1,000 row-bucket pairs deterministically; observed overlaps ≤ `max_overlap_events_per_row_bucket` from overlay policy

  Pinned sampling law (MUST; decision-free):
    Let `N = number of rows in scenario_calendar_5A` and `H = number of horizon buckets`.
    For i = 1..1000:
      - pick row index: `r_i = floor(u_det("overlap_row", str(i)) * N)`
      - pick bucket index: `h_i = floor(u_det("overlap_bucket", str(i)) * H)`
      - evaluate overlap count at (row=r_i, bucket=h_i) using the same "active-at-bucket" law as S4.
    Use `u_det` defined in §7.1 (5A.calendar|scenario_id|stage|keys...), so this sampling is stable and reproducible.

If any realism floor fails → **FAIL CLOSED**.

---

### 9) Provenance sidecar (MANDATORY)

Write next to the parquet:

`scenario_calendar_5A.provenance.json`

Include:

* `manifest_fingerprint`, `scenario_id`
* digests/versions of input artefacts:

  * horizon config, overlay policy, class policy, zone_alloc
* generation parameters (counts, amplitudes, duration choices)
* summary stats:

  * total events, events by type
  * coverage by country and tzid
  * max overlap observed in validation sample

No timestamps inside the calendar itself; timestamps allowed in provenance.

---
