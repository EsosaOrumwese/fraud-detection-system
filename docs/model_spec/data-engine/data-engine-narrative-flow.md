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

## Segment 2B Narrative (Arrival Routing and Throughput Realism Segment)

If Segment 2A answers "what local civil-time context applies to each site," Segment 2B answers "how arrivals are routed through that site network under realistic, policy-governed, and replayable randomness."

The purpose of 2B is to convert static site/time context into dynamic routing behavior that downstream fraud simulation can exercise at scale. It does this by freezing deterministic routing structures first, then applying tightly bounded RNG at the actual routing points.

At high level, 2B integrates:

- site coordinates from 1B (`site_locations`),
- site timezone assignments from 2A (`site_timezones`),
- sealed routing policy packs (`route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`, `virtual_edge_policy_v1`),
- deterministic gating and identity law inherited from prior segments.

### S0: Verify upstream gate and seal 2B routing environment

S0 verifies upstream PASS evidence and seals all 2B-required inputs and policy artefacts under one fingerprint-scoped receipt.

Purpose: ensure routing logic runs against one trusted and pinned environment, not mutable runtime assumptions.

This is the route-engine admission control that prevents mixed-version policy/data drift.

### S1: Freeze per-merchant site weights deterministically

S1 builds deterministic per-merchant weight surfaces from sealed site/time inputs and policy rules.

Purpose: establish stable routing mass before any RNG is introduced.

This isolates structural weighting decisions from stochastic routing draws.

### S2: Build alias tables for constant-time sampling

S2 compiles merchant-level alias structures (`index` + `blob`) for O(1) sampling.

Purpose: make runtime routing efficient and deterministic-to-structure while preserving exact probability semantics from S1.

This is the segment's performance hinge: expensive preparation once, cheap sampling many times.

### S3: Apply corporate-day modulation with bounded RNG

S3 introduces controlled stochastic modulation (gamma-based day effects) over routing groups by merchant/day context.

Purpose: model day-level demand/intensity variation without breaking replayability.

Design intent here is clear: randomness is recorded with provenance and bounded by state contracts.

### S4: Renormalize zone-group weights deterministically

S4 takes S3 effects and produces per-group weights that re-close to valid distributions for routing use.

Purpose: preserve mathematical validity after modulation so router draws remain coherent.

This keeps the pipeline stable: modulation can shift behavior, but probabilities stay well-formed.

### S5: Execute router core (group then site) with bounded RNG

S5 performs the main two-stage routing draw: first choose a group, then choose a site within that group, each via alias sampling.

Purpose: generate realistic site selection behavior at runtime while maintaining strict evidence and budget law for each draw family.

This is where 2B turns precomputed structures into operational routing decisions.

### S6: Route virtual-merchant edge branch

S6 handles virtual-merchant edge routing under its own bounded RNG policy branch.

Purpose: represent non-physical or edge-delivered routing behavior explicitly rather than forcing it into the same path as physical site picks.

This improves realism for channels where endpoint behavior differs from in-person merchant-site traffic.

### S7: Audit routing evidence and enforce CI-grade checks

S7 validates deterministic artefacts and RNG evidence coherence across S2-S6.

Purpose: prove that routing behavior matches intended laws (structure, budgets, identities) before final segment closure.

S7 is the quality barrier that catches silent routing drift.

### S8: Publish 2B validation bundle and PASS flag

S8 assembles the fingerprint-scoped validation bundle and emits the `_passed.flag` gate when all required checks close.

Purpose: convert routing outputs into consumption-safe routing truth for downstream segments.

As with previous segment finalizers, this is the hard stop against partial or contradictory state propagation.

## Why Segment 2B Matters to the Fraud Platform

Segment 2B gives the platform dynamic traffic realism on top of spatial and civil-time realism. It turns "where and when sites exist" into "how activity actually flows through them."

That supports stronger fraud experimentation in areas like:

- routing-path anomaly simulation,
- burst/day-effect stress scenarios,
- virtual-vs-physical channel divergence analysis,
- and reproducible throughput testing for downstream decision loops.

Without 2B, the platform has static world structure. With 2B, it has governed behavioral flow through that structure.

## Segment 3A Narrative (Zone Allocation and Routing-Universe Binding Segment)

If Segment 2B answers "how traffic is routed through the site network," Segment 3A answers "how each merchant-country footprint is split across legal time-zone zones, and which exact routing universe that split belongs to."

The purpose of 3A is to create a statistically credible, contract-governed zone-allocation surface that downstream routing and simulation components can trust without re-deriving mixture logic, priors, or hash lineage. It separates deterministic authority states from stochastic sampling states so randomness is controlled, replayable, and auditable.

At high level, 3A integrates:

- gated upstream structure from 1A/1B/2A (especially `outlet_catalogue`),
- structural references (`iso3166_canonical_2024`, `tz_world_2025a`),
- sealed statistical policy packs (`zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`),
- cross-segment routing context (`day_effect_policy_v1`) as part of universe binding.

### S0: Verify upstream gates and seal the 3A world

S0 re-verifies the upstream PASS bundles for 1A, 1B, and 2A, then seals the exact 3A input/policy inventory into `s0_gate_receipt_3A` and `sealed_inputs_3A`.

Purpose: prevent zone allocation from running on ambiguous or drifting upstream context.

This is 3A's admission control: no verified gate and sealed input universe, no 3A execution.

### S1: Classify merchant-country pairs into monolithic vs escalated

S1 reads 1A footprint totals and applies `zone_mixture_policy` to each `(merchant_id, legal_country_iso)` pair, emitting authoritative `s1_escalation_queue` decisions.

Purpose: decide where full zone-level splitting is statistically warranted and where monolithic handling is sufficient.

This avoids forcing high-variance zone sampling onto pairs that should remain simple by design.

### S2: Build country-zone prior surface with floor policy

S2 constructs deterministic country-to-zone prior concentrations from `country_zone_alphas`, then applies floor/bump rules from `zone_floor_policy`, producing `s2_country_zone_priors`.

Purpose: define the prior shape that governs later zone-share sampling.

This state is the policy-to-math bridge: priors are fixed by sealed inputs, not by ad hoc runtime behavior.

### S3: Sample zone shares for escalated pairs via Dirichlet

S3 runs bounded RNG for escalated pairs only, sampling share vectors over country zone universes and writing `s3_zone_shares` (with corresponding RNG evidence surfaces).

Purpose: inject realistic within-country zone variability while preserving deterministic replay under fixed run identity and parameters.

Design intent is explicit: randomness is allowed only in this bounded lane, with domain and accounting constrained by S1 and S2.

### S4: Integerize sampled shares into concrete zone counts

S4 deterministically converts S3 continuous shares into integer `s4_zone_counts`, with conservation checks against S1 site totals.

Purpose: move from probabilistic share surfaces to exact operational counts.

This is where statistical outputs become executable quantities for downstream consumers.

### S5: Publish zone allocation egress and universe hash

S5 writes `zone_alloc` and computes `zone_alloc_universe_hash`, binding priors, floor policy, day-effect policy digest, and zone-allocation data digest into one routing-universe identity.

Purpose: make zone allocation consumable and cryptographically tied to the exact policy/data universe used to produce it.

This is the cross-segment integrity hinge between 3A allocation semantics and downstream routing semantics.

### S6: Validate segment structure and consistency

S6 performs segment-level structural and cross-state validation, emitting `s6_validation_report_3A`, `s6_issue_table_3A`, and `s6_receipt_3A`.

Purpose: prove that domain coverage, count conservation, share behavior, and universe-hash consistency all hold before final gating.

This converts "pipeline ran" into "pipeline is internally coherent."

### S7: Publish final validation bundle and PASS flag

S7 bundles required 3A artefacts, computes bundle digests, and publishes the final `_passed.flag` gate for the manifest fingerprint.

Purpose: enforce the no-PASS-no-read law for 3A outputs.

Downstream components should treat `zone_alloc` as trusted only when this final gate closes.

## Why Segment 3A Matters to the Fraud Platform

Segment 3A is where merchant footprint realism becomes routing-ready zone realism. It gives the fraud platform:

- statistically shaped zone distribution behavior (not flat or arbitrary splits),
- deterministic replay under pinned policies and parameters,
- explicit universe identity (`zone_alloc_universe_hash`) for cross-segment consistency,
- safer downstream consumption via final PASS-gated closure.

Without 3A, routing layers inherit merchant-country counts but lack governed zone-distribution truth. With 3A, zone allocation is both behaviorally plausible and contract-trustworthy.

## Segment 3B Narrative (Virtual Merchant and CDN Edge Realization Segment)

If Segment 3A answers "how merchant-country footprint is distributed across zones," Segment 3B answers "how virtual merchants are represented operationally, and through which edge universe their traffic appears to flow."

The purpose of 3B is to turn virtual-channel intent into governed, replayable edge infrastructure surfaces that downstream routing can use directly. It defines virtual merchant identity, legal settlement anchors, operational edge geography, alias-ready edge selection surfaces, and the final contract that binds those pieces together.

At high level, 3B integrates:

- gated upstream outputs from 1A/1B/2A/3A (`outlet_catalogue`, `site_locations`, `site_timezones`, `zone_alloc`),
- virtual and CDN policy packs (`mcc_channel_rules`, `cdn_country_weights`, `route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`),
- settlement/geospatial references (`virtual_settlement_coords`, `hrsl_raster`, `pelias_cached_sqlite` and bundle),
- strict no-pass-no-read gate posture for downstream consumers.

### S0: Verify upstream gates and seal the virtual-edge environment

S0 verifies upstream PASS bundles (1A, 1B, 2A, 3A) and seals the exact 3B input universe into `s0_gate_receipt_3B` and `sealed_inputs_3B`.

Purpose: prevent virtual/CDN synthesis from running on partial or drifting upstream state.

This gives all later 3B states one closed world to read from.

### S1: Classify virtual merchants and create settlement nodes

S1 deterministically classifies merchants as virtual vs non-virtual using governed rules, then creates exactly one legal settlement node per virtual merchant in `virtual_settlement_3B` (with stable settlement identity and timezone).

Purpose: separate legal/accounting settlement truth from physical outlet truth and make virtual-merchant scope explicit.

This is the semantic authority for "who is virtual" and "where legal settlement lives."

### S2: Construct CDN edge catalogue with bounded RNG

S2 builds the static edge universe for virtual merchants by applying edge budget and geography policies, then uses bounded RNG for edge placement/jitter to produce `edge_catalogue_3B` and its index.

Purpose: generate realistic operational edge geography without losing replay control.

This is where virtual traffic gets plausible operational origins (country, coordinates, operational tz) under governed randomness.

### S3: Compile edge alias tables and edge-universe hash

S3 is RNG-free: it converts S2 edge weights into alias surfaces (`edge_alias_blob_3B`, `edge_alias_index_3B`) and emits `edge_universe_hash_3B` that binds key policy and edge artefacts.

Purpose: make runtime edge selection fast and integrity-bound.

This allows downstream routing to sample edges efficiently while still proving it is using the correct edge universe.

### S4: Publish virtual routing semantics and validation contract

S4 is also RNG-free: it codifies how virtual routing must interpret settlement vs operational clocks and emits explicit `virtual_routing_policy_3B` plus `virtual_validation_contract_3B`.

Purpose: convert built artefacts into enforceable runtime and validation rules.

This state answers "how virtual flows must behave" and "how we will test that behavior."

### S5: Re-audit 3B and publish final PASS gate

S5 re-validates S0-S4 coherence (including S2 RNG evidence accounting), publishes `validation_bundle_3B`, and emits `_passed.flag`.

Purpose: convert 3B from generated artefacts into trustable segment truth.

Downstream virtual routing and validation flows should consume 3B surfaces only when this final gate closes.

## Why Segment 3B Matters to the Fraud Platform

Segment 3B gives the platform production-shaped virtual-channel realism. It creates the operational model for card-not-present style flows where legal settlement identity and apparent network edge identity differ by design.

That enables stronger fraud simulation and detection in areas like:

- virtual vs physical behavior separation without semantic drift,
- edge-country and edge-timezone variation under controlled policy,
- replayable edge selection behavior for debugging and model comparison,
- explicit policy-bound validation of virtual routing assumptions.

Without 3B, virtual traffic is typically approximated as a flat extension of physical outlets. With 3B, virtual traffic has a governed edge universe, legal settlement anchors, and enforceable runtime contracts.

## Segment 5A Narrative (Deterministic Intensity Modeling Segment)

If Segment 3B answers "how virtual and physical world structure is represented for routing realism," Segment 5A answers "what expected demand intensity should exist across merchant-zone time buckets before stochastic realization."

The purpose of 5A is to produce deterministic, policy-governed intensity surfaces that convert Layer-1 world structure into scenario-ready expected traffic volume. It sits between structural world generation and stochastic event realization: no randomness, no arrivals, just validated expected-intensity truth.

At high level, 5A integrates:

- upstream Layer-1 world gates and egresses (1A through 3B),
- classing and scale policies,
- weekly shape library and time-grid policies,
- scenario horizon and overlay policies for calendar/stress effects,
- strict HashGate closure before downstream consumption.

### S0: Verify upstream readiness and seal 5A input universe

S0 verifies upstream PASS status for required Layer-1 segments and seals the exact 5A admissible input set into `s0_gate_receipt_5A` and `sealed_inputs_5A`.

Purpose: create a closed world so 5A modeling cannot drift onto ungoverned or missing inputs.

This is a control-plane state only: no modeling outputs, no RNG, just trust boundary setup.

### S1: Classify merchant-zone demand profile and base scale

S1 deterministically assigns each in-scope `(merchant, zone)` a demand class and base scale profile, materialized in `merchant_zone_profile_5A`.

Purpose: define traffic persona and magnitude priors before any temporal shaping.

This state is the sole authority for class/scale identity used by downstream intensity construction.

### S2: Build class-zone weekly shape library on fixed grid

S2 defines the local-week bucket grid and produces normalized unit-mass shapes per class-zone combination in `class_zone_shape_5A` with companion grid definition artefacts.

Purpose: encode "how demand is distributed over a week" independent of merchant-specific scale.

This separates pattern shape from volume magnitude so later composition stays interpretable and stable.

### S3: Compose baseline local-time intensities (scale x shape)

S3 combines S1 scale with S2 shapes to produce deterministic baseline expected intensity `merchant_zone_baseline_local_5A` over local-week buckets.

Purpose: create the pre-scenario baseline lambda surface that captures ordinary weekly behavior.

No overlays or shocks are applied yet; this is the neutral baseline reference.

### S4: Apply calendar/scenario overlays over horizon buckets

S4 maps scenario calendar events and overlay policies onto the baseline surface to generate scenario-adjusted intensity outputs such as `merchant_zone_scenario_local_5A`.

Purpose: convert baseline weekly behavior into horizon-specific expected demand under explicit scenario assumptions.

This is where holidays, pay cycles, campaigns, and stress policies modify intensity, still deterministically and without sampling events.

### S5: Validate cross-state coherence and publish 5A PASS gate

S5 re-audits S0-S4 contracts, builds `validation_bundle_5A`, computes index-linked digests, and publishes final `_passed.flag`.

Purpose: ensure intensity surfaces are structurally, mathematically, and contractually safe to consume.

Downstream components must treat 5A outputs as authoritative only when this final gate is verified.

## Why Segment 5A Matters to the Fraud Platform

Segment 5A gives the fraud platform a controlled demand expectation layer. It turns static world structure into explainable expected traffic intensity that later stochastic and routing stages can realize without semantic ambiguity.

That enables stronger platform outcomes such as:

- clean separation between deterministic demand design and stochastic realization,
- scenario testing with explicit, policy-traceable overlay effects,
- reproducible baseline-vs-scenario comparisons for model/debug workflows,
- safer downstream simulation because intensity truth is PASS-gated and digest-bound.

Without 5A, later stages would mix shape assumptions, scenario logic, and randomness in one step. With 5A, expected demand is explicit, governed, and replayable before any event sampling occurs.

## Segment 5B Narrative (Stochastic Arrival Realization and Routing Segment)

If Segment 5A answers "what expected intensity should exist by merchant-zone over time," Segment 5B answers "which concrete arrivals actually occur, when they occur, and where they route under governed randomness."

The purpose of 5B is to transform deterministic scenario intensity surfaces into replayable, event-level arrival streams that the fraud platform can consume as operational reality. It introduces stochastic realization in controlled layers, while preserving gate discipline, count conservation, and routing authority boundaries from earlier segments.

At high level, 5B integrates:

- upstream world and routing authorities from Layer-1 (1A-3B),
- deterministic intensity/scenario outputs from 5A,
- Layer-2 arrival RNG and latent-field policies,
- final validation bundle law for no-PASS-no-read consumption of `arrival_events_5B`.

### S0: Verify upstream gates and seal 5B input universe

S0 verifies required upstream PASS gates (Layer-1 plus 5A), binds the scenario set, and emits `s0_gate_receipt_5B` with `sealed_inputs_5B`.

Purpose: lock 5B to one trusted world and one admissible input universe before any stochastic realization begins.

This state is metadata-only and RNG-free.

### S1: Build time grid and grouping plan

S1 deterministically defines the realization grid and grouping structure (`s1_time_grid_5B`, `s1_grouping_5B`) used by downstream stochastic states.

Purpose: establish one authoritative bucket structure and grouping keyspace so S2-S4 can align draws, counts, and routing without ambiguity.

This state turns scenario scope into executable realization scaffolding.

### S2: Apply latent stochastic field to produce realized intensities

S2 is the first RNG state. It combines 5A target intensity with governed latent stochastic factors (LGCP-style where configured) to emit `s2_realised_intensity_5B` (and optional latent-field artefacts), alongside RNG evidence events.

Purpose: introduce realistic intensity variability around deterministic demand expectations while preserving replay and policy-bound RNG accounting.

This is the bridge from deterministic intensity design to stochastic intensity realization.

### S3: Realize integer bucket counts from realized intensities

S3 performs RNG-based bucket-count realization, producing `s3_bucket_counts_5B` and corresponding RNG event/audit traces.

Purpose: convert continuous realized intensity into integer event counts per bucket and entity.

This state establishes the count-conservation contract that S4 must honor exactly.

### S4: Expand counts into arrival events and apply routing picks

S4 expands each realized count into concrete event rows in `arrival_events_5B`, applying bounded RNG for intra-bucket timestamp jitter and routing picks (site/edge) according to physical/virtual routing authorities.

Purpose: materialize final event-level arrivals with correct timing, channel semantics, and routing lineage.

This is the operational output state where modeled demand becomes consumable fraud-platform events.

### S5: Validate 5B coherence and publish final PASS gate

S5 re-validates S0-S4 contracts, including RNG accounting and cross-state conservation checks, then publishes `validation_bundle_5B` and final `_passed.flag`.

Purpose: enforce that realized arrivals are structurally coherent, auditable, and safe to consume.

Downstream systems should treat `arrival_events_5B` as authoritative only when this 5B gate is verified.

## Why Segment 5B Matters to the Fraud Platform

Segment 5B is where the platform moves from expected demand surfaces to concrete synthetic reality. It provides the event stream that downstream detection, case, and learning loops actually operate on.

That enables:

- realistic variability without losing replay control,
- explicit separation of deterministic expectation vs stochastic realization,
- strong auditability through RNG event families and final validation gating,
- trustworthy event-level routing behavior across physical and virtual channels.

Without 5B, the platform has expected traffic but not executable arrivals. With 5B, it gets governed, replayable, event-level flow suitable for end-to-end fraud simulation and evaluation.

## Segment 6A Narrative (Entity, Account, Instrument, and Graph World Segment)

If Segment 5B answers "what concrete arrivals exist in the world," Segment 6A answers "which entities, financial objects, and network relationships those arrivals can legitimately involve."

The purpose of 6A is to build the synthetic bank's static world model: parties, accounts, instruments, devices, IPs, and baseline fraud posture. It converts upstream merchant/arrival reality into a governed entity graph that downstream behavioral/fraud states can use as immutable context.

At high level, 6A integrates:

- upstream sealed worlds from Layer-1 (1A-3B) and Layer-2 (5A-5B),
- Layer-3 priors/taxonomies for population, products, instruments, devices, and IPs,
- linkage and eligibility policies for graph construction,
- final segment validation and HashGate closure before any downstream reads.

### S0: Verify upstream gates and seal 6A input universe

S0 verifies required upstream PASS evidence and seals all admissible 6A inputs into `s0_gate_receipt_6A` and `sealed_inputs_6A`.

Purpose: enforce a closed, trusted world before entity synthesis starts.

This state is control-plane and RNG-free; it establishes dependency authority, not business objects.

### S1: Realize party/customer base population

S1 creates the party universe (`s1_party_base_6A`) with deterministic identity law plus RNG-governed count/attribute realization under population and segmentation priors.

Purpose: answer "who exists in this bank world" and with which static segment context.

This is the sole 6A authority for party identity and high-level party segmentation.

### S2: Realize accounts and product holdings

S2 takes S1 parties and creates the account universe (`s2_account_base_6A`) and party-product holdings under product mix and eligibility rules.

Purpose: answer "what financial accounts/products exist and who owns them."

This establishes ownership topology and account-level static attributes used by later states.

### S3: Realize instruments and account-instrument links

S3 creates payment credentials/instruments (`s3_instrument_base_6A`) and their link surfaces to accounts and parties.

Purpose: represent usable payment credentials as first-class world objects.

This state is the authority on instrument existence, type mix, and ownership linkage.

### S4: Realize devices, IP endpoints, and static interaction graph

S4 constructs device and IP bases plus linkage tables that connect parties, accounts, instruments, merchants, and network endpoints.

Purpose: provide the static network-graph substrate that behavioral and fraud logic can act on later.

This introduces shared-device/shared-IP structure without simulating temporal sessions yet.

### S5: Assign static fraud posture and close 6A with HashGate

S5 assigns static fraud-role posture across entity classes (party/account/merchant/instrument/device/IP), validates S1-S4 coherence, builds the 6A validation bundle, and emits final `_passed.flag`.

Purpose: convert the generated entity graph into a trusted, role-annotated world ready for downstream fraud-flow modeling.

No downstream component should read 6A surfaces unless this final gate is verified.

## Why Segment 6A Matters to the Fraud Platform

Segment 6A is the platform's identity and topology backbone. It provides the static bank world that makes later fraud behavior simulation meaningful rather than free-floating.

That enables:

- realistic ownership chains (party -> account -> instrument),
- realistic network context (device/IP sharing and linkage patterns),
- explicit static fraud posture priors for downstream dynamic behavior states,
- strong replay/debugability because world structure is sealed and HashGate-validated.

Without 6A, arrivals exist but have weak entity context. With 6A, every downstream fraud flow can be grounded in a coherent, governed synthetic bank graph.

## Segment 6B Narrative (Behavioural Flow, Fraud Overlay, and Labelling Segment)

If Segment 6A answers "who and what exists in the synthetic bank world," Segment 6B answers "how that world behaves over transactions, fraud campaigns, and bank-response outcomes."

The purpose of 6B is to convert sealed arrivals plus sealed entity topology into end-to-end behavioural datasets: attached sessions, baseline transactional flows, fraud/abuse overlays, and final truth/bank-view labels. It is the segment where fraud stories are operationalized and labeled for downstream evaluation and learning.

At high level, 6B integrates:

- upstream arrivals from 5B,
- sealed entity graph and static posture from 6A,
- behavioural, flow, fraud, and labelling policy packs,
- strict segment HashGate closure before any consumer can trust 6B outputs.

### S0: Verify behavioural-universe gate and seal 6B inputs

S0 verifies PASS gates for required upstream segments (Layer-1, Layer-2, and 6A), then materializes `s0_gate_receipt_6B` and `sealed_inputs_6B`.

Purpose: define the exact behavioural universe 6B may read and enforce no-reach-around input discipline.

This state is metadata-only and RNG-free.

### S1: Attach arrivals to entities and build sessions

S1 maps each 5B arrival to concrete entity context (party/account/instrument/device/IP) and assigns session identity, producing `s1_arrival_entities_6B` and `s1_session_index_6B`.

Purpose: lift anonymous arrival rows into attributable user/entity behaviour streams.

This state is where "traffic exists" becomes "someone did something from somewhere."

### S2: Synthesize baseline all-legit transactional flows

S2 transforms S1 sessions into structured baseline transaction flows/events (`s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`) under legitimate-behaviour assumptions.

Purpose: build the non-fraud behavioural canvas that later overlay logic can corrupt or augment.

No fraud semantics are introduced here; it is the clean baseline world.

### S3: Overlay fraud and abuse campaigns

S3 instantiates configured campaign types, targets entities/flows, and emits fraud-augmented behaviour surfaces (`s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`) plus campaign catalogue provenance.

Purpose: convert baseline behaviour into realistic adversarial patterns with explicit campaign lineage.

This is the segment's behavioural corruption layer, not the final labeling authority.

### S4: Assign truth labels and bank-view lifecycle labels

S4 labels each flow/event/case in two views: world-truth (what actually happened) and bank-view (what the bank detected/decided and when), emitting label and case timeline surfaces.

Purpose: separate objective fraud truth from institutional perception and operational outcomes.

This state is the only authority for final fraud/abuse labeling and case lifecycle representation.

### S5: Validate end-to-end 6B coherence and publish final HashGate

S5 validates S0-S4 structure, coverage, provenance, and RNG accounting; builds `validation_bundle_6B`; and publishes final `_passed.flag`.

Purpose: ensure behavioural outputs are internally consistent, auditable, and fit for downstream consumption.

No downstream consumer should treat 6B datasets as authoritative unless this gate verifies.

## Why Segment 6B Matters to the Fraud Platform

Segment 6B is where the platform becomes supervision-ready. It turns arrivals and entity context into labeled behavioural truth with realistic fraud narratives and bank-response timelines.

That enables:

- end-to-end fraud scenario generation with campaign provenance,
- controlled separation of baseline behaviour vs adversarial overlays,
- dual-ground-truth evaluation (truth view vs bank-view),
- reproducible labelled datasets for model testing, policy tuning, and operations simulation.

Without 6B, the system has events and entities but weak fraud-behaviour supervision. With 6B, it has coherent, policy-traceable behavioural and labeling surfaces suitable for robust fraud-platform evaluation.
