# Layer 2 — Segment 5B: Arrival Realisation (LGCP + Routing)

Here’s a matching state-flow overview for **Layer 2 / Segment 5B** in the same style: conceptual, non-binding, but precise enough that someone knows what to expect.

**Role in the engine**

Segment 5A has just finished building deterministic **intensity surfaces** `λ_target(m, tz, t)` for every merchant×zone×time bucket.

**Segment 5B is where time actually “ticks”.**
It takes those surfaces and the Layer-1 routing fabric and **draws real arrivals**:

> “How many arrivals really happen? At what exact times? At which site or edge do they land?”

5B is where the LGCP / Poisson machinery lives and where the RNG budget is consumed. It still doesn’t know anything about fraud or transaction outcomes; it only generates the **skeleton event stream** Layer 3 will decorate.

---

## 5B.S0 — Gate & sealed inputs (RNG-free)

**Purpose**

Establish the run boundary for Layer 2 and freeze everything 5B is allowed to depend on.

**Inputs**

From Layer 1 & 5A:

* Validation bundles + PASS flags for:

  * 1A–3B (Layer-1 world + routing).
  * 5A (arrival surfaces & calendar).

From Layer 2 contracts:

* Layer-2 schemas, dictionary, registry.
* LGCP / arrival realisation config:

  * bucket size and horizon,
  * LGCP hyperparameters (covariance kernels, variance scales),
  * optional grouping structure (merchant clusters, zone clusters).

**Behaviour**

* Verify upstream segments are green:

  * Re-hash required validation bundles, check PASS flags.
* Resolve and seal:

  * 5A’s intensity surfaces and metadata,
  * Layer-1 routing artefacts (alias tables, zone allocations, virtual edge catalogues),
  * LGCP / arrival config for 5B.
* Record a canonical list of sealed inputs for this `{parameter_hash, manifest_fingerprint}`.

**Outputs**

* `s0_gate_receipt_5B`
  – run-scoped receipt recording which bundles and config artefacts were checked and bound.

* `sealed_inputs_5B`
  – tabular list of all artefacts 5B may read, with versioning/digests.

**Notes**

* RNG-free.
* Every later 5B state must treat this sealed set as its authority for inputs; no ad-hoc reads.

---

## 5B.S1 — Time grid & grouping plan (RNG-free)

**Purpose**

Define **how time is discretised** and how merchants/zones are grouped for shared latent variation.

**Inputs**

* `s0_gate_receipt_5B` + `sealed_inputs_5B`.
* 5A’s intensity surfaces (`λ_target` over some time horizon).
* LGCP config:

  * bucket duration (e.g. 5/15 minutes),
  * total duration (e.g. N days),
  * grouping rules for merchants/zones.

**Behaviour**

* Define a **time grid** over the run horizon:

  * e.g. `[start_utc, start_utc + Δ, …, end_utc)`.
  * Map each bucket to:

    * `utc_day`, `bucket_index`, and a link into 5A’s time coordinate (hour-of-week / scenario window).
* Apply grouping rules to set up **LGCP groups**:

  * e.g. clusters of merchants/zones that share a latent field (by region, class, or scenario).

**Outputs**

* `s1_time_grid_5B`
  – a deterministic table describing each time bucket: start/end UTC, the corresponding local time features and scenario tags.

* `s1_grouping_5B`
  – mapping from `(merchant_id, tzid)` to a **group id** for LGCP purposes (or “self-grouped” if independent).

**Notes**

* RNG-free; pure geometry in time and grouping.
* 5A surfaces are never changed here; S1 just decides how they’ll be sampled.

---

## 5B.S2 — Latent intensity fields (LGCP core, RNG-bearing)

**Purpose**

Introduce **correlated stochastic variation** around 5A’s deterministic intensity surfaces.

**Inputs**

* `s1_time_grid_5B` and `s1_grouping_5B`.
* 5A target surfaces (`λ_target(m, tz, t)`).
* LGCP hyperparameters:

  * per-group variance,
  * temporal correlation structure (kernel parameters).

**Behaviour**

For each group (or merchant×zone, depending on design):

* Construct a **latent Gaussian field** over the time grid:

  * sample a multivariate normal with a governed covariance (e.g. OU, RBF kernel over time).
* Convert this latent field into multiplicative noise:

  * e.g. `ξ = exp(G)` where `G` is the Gaussian field, calibrated so `E[ξ] ≈ 1`.
* Combine with 5A’s intensity:

  * `λ_realised(m, tz, bucket) = λ_target(m, tz, bucket) × ξ(group, bucket)`.

**Outputs**

* `s2_latent_fields_5B`
  – a run-scoped per-bucket latent field (or implicit if you only keep the resulting `λ_realised`).

* `s2_realised_intensity_5B`
  – per `(merchant, tz, bucket)` effective intensity after latent noise.

* RNG logs:

  * LGCP draw events (one event per group per “field draw”), with Philox counters, labels and trace entries.

**Notes**

* This is where **burstiness and co-movement** come from; 5A just gives average levels.
* 5B.S2 consumes a significant chunk of the RNG budget; the Philox streams and budgets should be explicitly defined.

---

## 5B.S3 — Bucket-level arrival counts (RNG-bearing)

**Purpose**

Turn `λ_realised` into **actual counts** per time bucket.

**Inputs**

* `s2_realised_intensity_5B` (intensity per bucket).
* `s1_time_grid_5B` for bucket durations.
* LGCP/Poisson config (e.g. which approximation method is used).

**Behaviour**

For each `(merchant, tz, bucket)`:

* Compute expected count for the bucket:
  `μ = λ_realised × Δ_t`.
* Draw `N ~ Poisson(μ)` (or use thinning/etc. as decided by the spec).
* Record `N` and the RNG event.

**Outputs**

* `s3_bucket_counts_5B`
  – run-scoped table keyed by `(merchant_id, tzid, bucket)`, with:

  * `count`,
  * `lambda_realised`,
  * references to LGCP parameters if needed.

* RNG logs:

  * one Poisson event per bucket (or per bucket/group, depending on design), with proper Philox envelope and trace.

**Notes**

* This is the discrete “how many arrivals?” stage; no micro-timing yet.
* Algebra here must be checkable in S5 by re-deriving Poisson probabilities and reconciling counts.

---

## 5B.S4 — Micro-time & routing to sites/edges (RNG-bearing)

**Purpose**

Expand bucket-level counts into **individual arrivals** and route them through Layer-1’s fabric.

**Inputs**

* `s3_bucket_counts_5B`.
* `s1_time_grid_5B`.
* Layer-1 routing artefacts:

  * 2B alias tables (physical site routing),
  * 3A `zone_alloc` (zone shares),
  * 3B edge catalogue + alias (virtual routing).
* 5A scenario info (to tag arrivals with scenario_ids).

**Behaviour**

For each `(merchant, tz, bucket)` with `N > 0`:

1. **Micro-time within bucket**

   * Draw `N` intra-bucket times:

     * simplest: uniform in `[bucket_start, bucket_end)`,
     * or use a simple within-bucket shape if you want (e.g. slight “shoulders” at the start/end of bucket).
   * Convert `utc_ts` to local time for each arrival via `site_timezones` + tz timetable.

2. **Routing to sites/edges**

   * For physical merchants:

     * Use 2B site alias tables and 3A zone_alloc to pick a `(site_id, tzid)` for each arrival.
   * For virtual merchants:

     * Use 3B’s edge alias tables / catalogue to pick an `(edge_id, ip_country, edge_lat, edge_lon)`, consistent with virtual routing policy.

3. **Tagging**

   * Attach scenario tags from 5A (e.g. `scenario_id`, `is_payday`, `is_holiday`, etc).

**Outputs**

* `s4_arrivals_5B`
  – the **skeleton arrival stream** with one row per arrival:

  * `arrival_id` (unique per run),
  * `utc_ts`,
  * `merchant_id`,
  * `site_id` or `edge_id`,
  * `tzid`,
  * optional `zone_id`,
  * `scenario_id` / flags.

* RNG logs:

  * intra-bucket time draws,
  * site/edge alias picks, with envelopes and trace.

**Notes**

* This is the first place you see one row per *event*; everything before was per-bucket or per-group.
* All constraints from Layer-1 (zone coverage, site ordering, virtual semantics) must be respected here.

---

## 5B.S5 — Validation & bundle (RNG-free)

**Purpose**

Prove that 5B behaved as specified and produce a **Layer-2 validation bundle + PASS flag** that downstream layers and tools can gate on.

**Inputs**

* All 5B outputs:

  * `s1_time_grid_5B`, `s2_latent_fields_5B`/`s2_realised_intensity_5B`,
  * `s3_bucket_counts_5B`,
  * `s4_arrivals_5B`,
  * RNG logs for LGCP, Poisson, intra-bucket and routing draws.
* Sealed inputs from S0 (5A surfaces, L1 routing artefacts).

**Behaviour**

* **Structural checks**

  * Rebuild bucket counts by grouping `s4_arrivals_5B`; confirm they match `s3_bucket_counts_5B`.
  * Check routing invariants:

    * all arrivals land on valid `(merchant,site)` or `(merchant,edge)` pairs from L1,
    * zone and tz mappings remain consistent.

* **Algebra / expectation checks**

  * For sample subsets, verify realised counts are plausible given λ_target / LGCP settings (simple tests for extreme deviations, not full statistical testing).

* **RNG checks**

  * Reconcile RNG logs:

    * expected vs actual event counts,
    * monotone counters, no budget overrun.

* **Bundle**

  * Pack evidence (reports, summaries, slices of RNG accounting) into a **validation bundle** under `.../validation/fingerprint={manifest_fingerprint}/`.
  * Produce a `index.json` with file paths + SHA-256s.
  * Compute bundle SHA-256 and write `_passed.flag_5B` with `sha256_hex = ...`.

**Outputs**

* `validation_bundle_5B`
  – L2 bundle with index and evidence (exact shape defined in Layer-2 contracts).

* `_passed.flag_5B`
  – single-line PASS flag that downstream layers must check:
  “No PASS → No read” for any 5B outputs.

**Notes**

* RNG-free; pure replay/validation + hashing.
* This is the Layer-2 equivalent of 1A.S9 / 3A.S7: it’s the gate that Layer-3 and any offline analysis should obey.

---

That’s the 5B state-flow overview: S0–S5, clear responsibilities, deterministic vs RNG split, and a natural continuation of the S0 + validation bundle pattern you established in Layer-1.
