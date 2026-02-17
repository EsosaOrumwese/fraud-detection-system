# Data Engine Narrative Flow

## Overall Purpose of the Data Engine

The Data Engine exists to generate a statistically realistic, controllable, and replayable world that the fraud platform can trust as ground truth input. Its purpose is not just to produce rows, but to produce economically and behaviorally coherent structure: who merchants are, where they operate, how their footprint expands, and how those choices should look under explicit policy and statistical assumptions.

At platform level, this gives the fraud system three core benefits:

1. A reliable simulation substrate for control-ingress, decision, labeling, and case-handling rails.
2. Deterministic replay capability so regressions can be diagnosed as model, policy, or implementation changes rather than noise.
3. Governed data contracts that separate authority by state, so downstream components consume clear truths instead of inferred guesses.

Design-wise, the engine balances three goals at once:

- Statistical realism: distributions and constraints are chosen to mirror plausible merchant behavior.
- Operational rigor: lineage, scope, and gates prevent ambiguous consumption.
- Explainability of intent: each layer/segment/state owns a specific question and produces a bounded answer for the next state.

In short: the engine gives the fraud platform a realistic world to reason over, plus the governance needed to trust that world in production-style workflows.

## Segment 1A Narrative (Layer 1 Root Segment)

Segment 1A is the platform's merchant-footprint genesis segment. Its purpose is to convert ingress merchant identity plus external macro references into a validated outlet footprint surface that later platform flows can consume without re-deriving assumptions.

It is intentionally designed as a semantic pipeline: each state answers one bounded question, then hands that answer to the next state under explicit authority boundaries.

### S0: Freeze the world before any randomness

S0 establishes the fixed context for everything that follows. It seals the merchant universe from `transaction_schema_merchant_ids`, pins country authority from `iso3166_canonical_2024`, and brings in macro-economic context from `world_bank_gdp_per_capita_20250415` and `gdp_bucket_map_2024`.

Purpose: ensure all later modeling is grounded in one immutable run context, not ad hoc lookups.

S0 also sets deterministic numeric and identity law (`parameter_hash`, `manifest_fingerprint`, `run_id`), so downstream behavior is replayable and attributable to governed inputs rather than incidental runtime effects.

### S1: Decide single-site vs multi-site behavior

S1 applies a logistic hurdle model per merchant to decide whether the merchant should branch into the multi-site path.

Purpose: separate merchants that plausibly remain single-site from those that require richer cross-country outlet synthesis.

This branch decision is statistically meaningful, because it gates all heavier sampling work in S2-S7 and prevents inflating complexity for merchants that should remain simple.

### S2: Sample total outlet intensity for multi-site merchants

For merchants that pass the hurdle, S2 applies an NB2-style stochastic process (Poisson-Gamma construction with rejection policy) to produce an accepted total outlet count.

Purpose: generate realistic outlet-count variability (including heavy-tail behavior) while preserving deterministic replay under fixed lineage.

S2 answers "how many outlets should this merchant have before geography split," not "where those outlets go."

### S3: Build cross-country candidate universe and rank authority

S3 deterministically constructs the legal candidate country set and its contiguous cross-country rank (`candidate_rank`, home rank fixed at 0), using policy ladders and registry-governed references.

Purpose: make inter-country order explicit and authoritative once, so later states cannot invent conflicting order.

S3 may also emit deterministic priors and integerisation artefacts where configured, but its central platform value is order authority and admissibility clarity.

### S4: Set foreign-target count via ZTP logic

S4 uses a ZTP-based process to decide the foreign-country target count (`K_target`) for eligible multi-site merchants, with deterministic short-circuit behavior when no admissible foreign set exists.

Purpose: model how far a merchant expands internationally without choosing specific countries yet.

S4 is a "how many foreign countries" state, not a "which countries" state.

### S5: Build currency-to-country weight authority

S5 constructs `ccy_country_weights_cache` from external settlement surfaces, notably `settlement_shares_2024Q4` and `ccy_country_shares_2024Q4`, plus canonical ISO references and governed smoothing policy.

Purpose: provide a stable prior weight surface that downstream selection can use without re-synthesizing market priors each time.

This state is deterministic and parameter-scoped by design, because the goal is reusable authority, not stochastic behavior.

### S6: Select realized foreign membership

S6 combines S3 candidate authority, S4 `K_target`, and S5 weights to select the realized foreign country membership for each merchant.

Purpose: translate "target foreign breadth" into concrete foreign-country membership under reproducible selection rules.

Critically, S6 does not define inter-country order; it respects S3's authority and only resolves membership.

### S7: Allocate integer outlet counts across the legal set

S7 takes total outlets and distributes integer counts across home plus selected foreign countries with deterministic rounding/residual logic.

Purpose: turn high-level footprint intent into exact per-country counts that can be materialized.

S7 protects count integrity (`sum per-country counts = total count`) while preserving authority boundaries: no new order surface, no redefinition of weights.

### S8: Materialize outlet stubs and within-country sequencing

S8 writes `outlet_catalogue`, producing concrete outlet rows per merchant-country with contiguous `site_order` and deterministic site identifiers.

Purpose: create the platform-consumable outlet footprint egress.

Design intent here is explicit: egress carries within-country sequence only; cross-country order remains externalized to S3 `candidate_rank`.

### S9: Validate replay and publish the consumption gate

S9 replays and validates S0-S8 commitments, then publishes fingerprint-scoped validation artefacts and PASS gate semantics.

Purpose: convert "data was written" into "data is safe to consume."

Even at high level, this matters for platform benefit: it keeps downstream fraud workflows from consuming ambiguous or partial worlds.

## Why Segment 1A Matters to the Fraud Platform

Segment 1A gives the platform a coherent merchant-footprint world with explicit statistical semantics:

- who expands,
- how much they expand,
- where they can legally operate,
- how foreign exposure is chosen,
- and how those outcomes are materialized for downstream decision and governance flows.

That means later platform layers can focus on fraud intelligence, detection, and operational actions rather than reconstructing market topology assumptions. In effect, 1A is the foundation that makes the rest of the platform analytically meaningful.

## Segment 1B Narrative (Spatial Realization Segment)

If Segment 1A answers "how many outlets exist and under which countries," Segment 1B answers "where those outlets plausibly live in space, as concrete coordinates, under deterministic and gated rules."

The purpose of 1B is to transform 1A footprint structure into geospatially valid site locations that the fraud platform can use for realistic transaction simulation, geo-behavior checks, and downstream analytics. It binds geospatial realism to explicit authority boundaries so that location synthesis remains explainable and replayable.

At high level, 1B integrates:

- 1A outlet structure (`outlet_catalogue`) and 1A gate status.
- Country geometry and ISO domain references (`world_countries`, `iso3166_canonical_2024`).
- Population and tile priors (`population_raster_2025`) where weighted tiling is configured.
- Deterministic and RNG states that are clearly separated by role.

### S0: Gate-in and seal read authority from 1A

S0 for 1B does not synthesize geography yet; it verifies that 1A is genuinely PASS for the target fingerprint and seals the allowed read surfaces for 1B.

Purpose: prevent spatial synthesis from starting on untrusted upstream egress.

This state turns 1A gate verification into a durable 1B receipt (`s0_gate_receipt_1B`) so later 1B states can rely on a clean "gate already proven" contract.

### S1: Build the eligible spatial tile universe

S1 constructs `tile_index` and `tile_bounds`, defining where placement is legally possible at tile granularity.

Purpose: create a deterministic spatial lattice over country geometry that downstream states can target without re-running expensive geo eligibility logic.

Here, external geospatial references matter directly: country polygons define legal containment, while raster surfaces define tile-level spatial basis.

### S2: Convert tile universe into deterministic tile weights

S2 takes S1 tiles and computes fixed-decimal, parameter-scoped tile weights per country (`tile_weights`) without RNG.

Purpose: convert spatial eligibility into a reproducible probability-like mass surface that can drive later integer allocation.

This is where statistical design intent appears as spatial prior design: if two runs have the same sealed inputs and parameters, their tile mass surface is identical.

### S3: Derive country-level site requirements from 1A egress

S3 reads gated `outlet_catalogue` and derives per `(merchant_id, legal_country_iso)` required counts (`s3_requirements`).

Purpose: bridge 1A merchant-country counts into the 1B spatial pipeline.

S3 remains RNG-free and intentionally does not define inter-country order; it respects 1A as the order authority and only extracts requirements.

### S4: Integerize requirements onto tiles

S4 distributes each country requirement count across that country's eligible tiles, using S2 fixed-dp weights and deterministic largest-remainder style integerization into `s4_alloc_plan`.

Purpose: produce exact per-tile integer quotas that sum perfectly to each country requirement.

This is the count-conservation hinge between probabilistic spatial mass and concrete site assignment.

### S5: Assign each site to a tile with controlled randomness

S5 performs RNG-based site-to-tile assignment under the fixed per-tile quotas from S4.

Purpose: randomize which specific site keys occupy each tile while preserving all deterministic count constraints from earlier states.

In other words, S5 introduces permutation-level randomness, not structural randomness; totals and quotas remain invariant.

### S6: Apply in-cell jitter and enforce point-in-country validity

S6 generates jitter within assigned pixels and enforces point-in-country acceptance, with bounded retry rules and RNG evidence.

Purpose: move from tile-level placeholders to plausible point coordinates while preserving geographic legality.

This is critical for fraud simulation realism because site points should not cluster unnaturally on centroids and should not spill across country boundaries.

### S7: Synthesize and reconcile final per-site records

S7 deterministically composes S5 assignment + S6 jitter + S1 geometry checks into a conformed per-site synthesis table.

Purpose: guarantee one coherent, validated record per expected site key before egress publication.

S7 is a data integrity stitch state: it ensures there are no dropped or duplicated site keys before egress.

### S8: Publish order-free geospatial egress

S8 publishes `site_locations` under seed + fingerprint partitions, with deterministic writer discipline and no implied inter-country ordering.

Purpose: provide the platform's consumable spatial site egress.

Design intent remains explicit: 1B egress is for location truth, not order truth; any cross-country ordering still comes from 1A authority surfaces.

### S9: Validate 1B end-to-end and issue the PASS gate

S9 verifies S7-to-S8 parity, RNG accounting from S5/S6, checksum integrity, and bundle completeness, then emits the fingerprint-scoped PASS flag if and only if all checks close.

Purpose: convert geospatial synthesis into consumption-safe geospatial truth.

This gate is what allows downstream platform components to use `site_locations` confidently in production-like runs.

## Why Segment 1B Matters to the Fraud Platform

Segment 1B gives the platform operationally credible geography. It takes abstract outlet structure and turns it into governed, validated coordinates that can support:

- geospatial fraud pattern simulation,
- channel and jurisdiction-aware behavioral synthesis,
- realistic proximity, routing, and region-based scenario testing,
- and stronger downstream explainability when events are tied back to location provenance.

Without 1B, the platform would know "how many and in which countries." With 1B, it knows "where, plausibly and reproducibly."

## Segment 2A Narrative (Civil Time Realization Segment)

If Segment 1B answers "where each site is," Segment 2A answers "what legal civil time context each site operates under, and whether that context is time-law valid."

The purpose of 2A is to bind geospatial site coordinates to trustworthy IANA time-zone assignment and legality checks so that downstream fraud simulations are not just spatially plausible, but temporally plausible. In practice, this means site behavior can be replayed against correct local time semantics, including DST edge behavior.

At high level, 2A integrates:

- gated site coordinates from 1B (`site_locations`),
- tz boundary geometry (`tz_world_2025a`),
- governed civil-time policy (`tz_overrides`, `tz_nudge`),
- sealed tzdb release material (`tzdb_release`),
- deterministic identity and gate law inherited from earlier segments.

### S0: Verify upstream PASS and seal civil-time inputs

S0 verifies 1B validation PASS for the target fingerprint and seals the exact 2A input set into a gate receipt and sealed manifest.

Purpose: guarantee that every later civil-time decision is grounded in one fixed, auditable input universe.

This is the segment's admission control: no trusted upstream gate, no civil-time processing.

### S1: Perform provisional timezone lookup from geometry

S1 maps each site coordinate to a provisional `tzid` using `tz_world` polygons, with deterministic nudge and ambiguity fallback rules when border cases occur.

Purpose: create a geometry-first time-zone assignment that is explainable and reproducible.

Design intent here is strict: one site in, one provisional assignment out, with no randomness.

### S2: Apply governed overrides and finalize per-site tzid

S2 consumes S1 provisional assignments and applies sealed override policy (site, mcc, country precedence) to produce final `site_timezones`.

Purpose: convert pure geometric assignment into operational assignment that can encode approved business/governance exceptions.

This state is where policy meets geometry: overrides are explicit, deterministic, and provenance-captured rather than ad hoc edits.

### S3: Compile timezone timetable/cache from sealed tzdb

S3 builds `tz_timetable_cache` from the sealed tzdb release for the target fingerprint, including deterministic index/digest evidence.

Purpose: provide downstream legality checks with a stable transition authority for each tzid, instead of requiring repeated raw tzdb parsing.

This improves both reliability and runtime posture: downstream states consume one canonical cache surface.

### S4: Evaluate legality against DST gaps and folds

S4 combines `site_timezones` and `tz_timetable_cache` to detect gap/fold legality conditions and produce a seed+fingerprint legality report.

Purpose: ensure assigned civil times are not silently invalid under real timezone transition rules.

This is the temporal realism checkpoint: location plus tzid must still be legal in the calendar/offset system that the platform claims to model.

### S5: Publish 2A validation bundle and PASS gate

S5 verifies required evidence closure across S2-S4, assembles the fingerprint-scoped validation bundle, and emits the `_passed.flag` gate using canonical index hashing rules.

Purpose: convert civil-time processing from "completed" to "safe to consume."

As with prior segment finalizers, this is what prevents downstream reads from drifting onto partial or inconsistent state.

## Why Segment 2A Matters to the Fraud Platform

Segment 2A gives the platform credible temporal semantics for every synthesized site. It makes local-time behavior defensible by combining geometry, policy, and tzdb transition law under one deterministic pipeline.

That unlocks stronger fraud realism in areas like:

- local-time transaction rhythm simulation,
- cross-region temporal anomaly detection,
- DST transition edge-case testing,
- and jurisdiction-aware investigations where "what local time did this event occur in" must be trustworthy.

Without 2A, the platform has site coordinates but weak time semantics. With 2A, each site is both spatially and temporally grounded.
