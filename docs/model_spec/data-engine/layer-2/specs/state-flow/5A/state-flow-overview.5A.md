# Layer 2 — Segment 5A: Arrival Surfaces & Calendar (Deterministic)

Here’s a state-flow overview for **Layer 2 / Segment 5A** in the same spirit as your 1A–3B overviews, but deliberately non-binding and conceptual.

**Role in the engine**

Layer 1 has just finished: 1A–3B have sealed a fixed world of merchants, outlets, zones and edges, with their routing fabric and validation bundles in place.

**Segment 5A is the first piece of Layer 2.**
It does **not** generate events. Instead, it builds the **deterministic intensity surfaces** that say:

> “For this merchant in this zone, at this local time, under this scenario, how busy should we expect it to be on average?”

5A is fully RNG-free. All randomness in arrival mechanics is reserved for Segment 5B.

---

## State 5A.S0 — Gate & sealed inputs (RNG-free)

**Purpose**

Establish the trust boundary between Layer 1 and Layer 2, and freeze the configuration universe for 5A.

**Upstream dependencies**

* Layer-1 validation bundles + PASS flags for all the segments 5A cares about:

  * 1A: outlet catalogue, merchant universe.
  * 1B: site locations.
  * 2A: site timezones and tz timetable cache.
  * 2B: routing weights / alias tables (if used for volume priors).
  * 3A: zone allocations and routing universe hash.
  * 3B: virtual classification / settlement, edge catalogue, edge alias/universe hash.
* Layer-1 and Layer-2 contracts:

  * Layer-wide schemas, dataset dictionaries, artefact registries.
  * 5A’s own policy/config surfaces (demand priors, weekly-shape library config, calendar/scenario config).

**Behaviour**

* Verify that all required Layer-1 segments have PASSed for the current `manifest_fingerprint`:

  * Recompute hash of each upstream validation bundle; check the corresponding PASS flag.
  * Refuse to run if any upstream layer-1 segment is not green.
* Resolve and seal the set of artefacts 5A is allowed to touch:

  * Merchant-level priors (e.g. expected daily volumes, class priors).
  * Shape library definitions.
  * Scenario/calendar configs (paydays, holidays, campaigns).
  * Any classing rules / metadata used for demand classification.
* Record the resolved catalogue entries (ids, schema refs, paths, digests) as **sealed inputs** for Segment 5A.

**Outputs**

* `s0_gate_receipt_5A`
  A small, fingerprint-scoped receipt that says:

  * which Layer-1 bundles were checked and PASSed,
  * which dictionary/registry entries were resolved,
  * which parameter set (`parameter_hash`) 5A is bound to.

* `sealed_inputs_5A`
  A tabular inventory of everything 5A is authorised to read (ids, partitions, schema refs, digests).

**Notes**

* No RNG.
* Every later 5A state must treat `s0_gate_receipt_5A + sealed_inputs_5A` as the sole authority for what it can read from Layer 1 and from 5A’s own config universe.

---

## State 5A.S1 — Merchant & zone demand classification (RNG-free)

**Purpose**

Map each merchant and zone into a **demand class** plus scale factors, using only sealed Layer-1 reality and sealed priors.

**Inputs**

* From Layer 1:

  * Merchant universe and attributes (segment, country, type, size).
  * Zone universe per merchant (3A zone_alloc).
  * Optional usage statistics from previous real/sim runs, if you decide to feed them as priors.
* From sealed 5A configs:

  * Demand class definitions (e.g. small_local, medium_chain, big_box, virtual_24x7).
  * Class assignment rules (criteria on merchant attributes, country, zone).
  * Per-class volume priors (e.g. expected daily tx range by class).

**Behaviour**

* For each `(merchant, zone)` pair:

  * Assign a **demand class** (e.g. “UK small café”, “US 24/7 exchange”).
  * Attach a **volume scale** (e.g. expected daily/weekly counts, possibly by scenario family).
  * Attach any flags 5B will need for grouping (e.g. salary-sensitive, holiday-sensitive, weekend-heavy).

**Outputs**

* `s1_demand_classes_5A`
  A param-scoped classification table keyed by `(merchant_id, tzid)` (or `(merchant_id, zone_id)`), with:

  * `demand_class_id`
  * volume scale parameters
  * grouping flags / tags.

**Notes**

* No RNG.
* This is the **single authority** in Layer 2 for “what kind of demand pattern does this merchant×zone have?”.

---

## State 5A.S2 — Weekly shape library (RNG-free)

**Purpose**

Own the reusable **weekly shape functions** that define the *shape* of demand over a week (ignoring absolute level and calendar shocks).

**Inputs**

* From sealed 5A configs:

  * Shape family definitions (e.g. “office-hours”, “commuter-rail”, “nightlife”, “24/7”).
  * Any hyperparameters or spline coefficients for those shapes.
* From classification (S1):

  * Which classes/zones need which shapes.

**Behaviour**

* For each relevant shape family and time zone:

  * Construct a **normalised weekly curve**, e.g. an array of 168 points (one per hour of week) or whatever time grid you adopt.
  * Ensure each curve is deterministic and integrates/sums to 1 over the week.
* Optionally derive more compact bases (e.g. factor models), but still produce explicit per-class/per-zone weekly shapes for downstream consumption.

**Outputs**

* `s2_shape_library_5A`
  A param-scoped library keyed by `(demand_class_id, tzid, hour_of_week)` (or equivalent), with:

  * `shape_value` (non-negative, sums to 1 per class×tz),
  * references back to the shape config that produced it.

**Notes**

* No RNG.
* 5A.S3 and 5B will treat this as the **sole authority** on within-week shape.

---

## State 5A.S3 — Baseline intensity surfaces (RNG-free)

**Purpose**

Combine **who you are** (S1) and **what your weekly shape looks like** (S2) into per-merchant, per-zone **baseline intensity surfaces**.

**Inputs**

* `s1_demand_classes_5A` — classification + volume scale per `(merchant, zone)`.
* `s2_shape_library_5A` — normalised weekly shape per `(demand_class, tzid)`.
* Optional additional priors (e.g. per-merchant caps or per-zone adjustments).

**Behaviour**

For each `(merchant, tzid)` and each discrete time point in your weekly grid:

* Look up:

  * the class id and volume scale from S1,
  * the shape value from S2.
* Compute `λ_base(m, tz, t)` such that:

  * over the week, the expected volume matches the scale, and
  * the intra-week pattern matches the class shape.

**Outputs**

* `s3_baseline_intensity_5A`
  Param-scoped baseline surfaces keyed by `(merchant_id, tzid, hour_of_week)` (or equivalent), with:

  * `lambda_base` (baseline intensity),
  * any decomposition you want (e.g. `scale × shape` columns, for debug and validation).

**Notes**

* No RNG.
* This is the baseline that would apply in a world with “no calendar shocks”.

---

## State 5A.S4 — Calendar overlays & published target surfaces (RNG-free)

**Purpose**

Warp the baseline surfaces through **calendar and scenario effects**, then publish the final **target intensity surfaces** for 5B.

**Inputs**

* `s3_baseline_intensity_5A` — baseline λ surfaces.
* From sealed configs:

  * Scenario calendar (global and per-region events).
  * Per-event / per-scenario effect definitions (multipliers, decay patterns, eligibility).
* From Layer 1 / other layers if desired:

  * Country/tz calendars (for local holidays/paydays).

**Behaviour**

* For each `(merchant, tzid, t)`:

  * Determine which calendar/scenario effects apply at time `t`:

    * salary day? weekend? public holiday? sale campaign? outage?
  * Construct a combined **scenario multiplier** `Γ(m, tz, t)` as a deterministic function of those events.
  * Compute final target intensity:

    ```text
    λ_target(m, tz, t) = λ_base(m, tz, t) × Γ(m, tz, t)
    ```

* Enforce simple sanity checks:

  * λ_target non-negative,
  * bounded ratios (e.g. events can’t arbitrarily blow up volume beyond governed limits),
  * scenario surfaces exist for the full run window.

**Outputs**

* `s4_intensity_surfaces_5A`
  Param-scoped final intensity surfaces keyed by `(merchant_id, tzid, time_bucket)` (or weekly grid + calendar window), with:

  * `lambda_target`,
  * decomposition (`lambda_base`, `calendar_factor`, `scenario_id`/tags).
* 5A validation bundle + PASS flag:

  * proving that surfaces are structurally sound, consistent with S1/S2/S3, and in allowable ranges.

**Notes**

* This is what Segment 5B will read as its **sole deterministic authority** on “how busy should this outlet be on average at this time, under this scenario”.
* No RNG here either; all randomness lives in 5B’s latent field / Poisson stages.

---

