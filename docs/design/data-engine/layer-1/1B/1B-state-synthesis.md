Segment `1B` state synthesis

`1B` is the segment that turns the outlet-world authority from `1A` into a governed site-location world.

Its actual implemented design is not just:

- some tiling
- some weighting
- then random coordinates

It is a gated spatial-realism segment that does six things in order:

1. proves that `1A` egress is lawful to read at all
2. constructs the eligible tile universe that later states are not allowed to escape
3. turns that universe into deterministic tile mass authority
4. converts 1A outlet counts into quota-exact tile allocation
5. realizes site-level placement through controlled randomization and geometry acceptance
6. publishes a final order-free egress only after a fingerprint-scoped validation gate says it deserves to be read

That makes `1B` less like a coordinate generator and more like a staged topology-and-placement contract system:

- `S0` creates legal read authority
- `S1` and `S2` create the spatial universe and tile-mass authority
- `S3` and `S4` convert 1A site counts into tile quotas
- `S5` and `S6` create the actual site-level stochastic placement truths
- `S7` and `S8` synthesize and publish the final site surface
- `S9` decides whether that egress deserves downstream trust at all

The important recovery point is that the actual implemented design is much more remediation-shaped than the raw state docs alone suggest. The trail in `segment_1B.build_plan.md` and `segment_1B.impl_actual.md` shows that several states became materially different design objects in implementation:

- `S0` became a real gate-in boundary, not just setup
- `S1` became a realism-and-geometry authority with projection, invalid-geometry, and antimeridian posture made explicit
- `S2` became a governed realism lever, not just a deterministic cache
- `S4` became both the main topology authority and the main runtime-hardening hotspot
- `S5` became the main site-assignment truth boundary and later a major performance-remediation surface
- `S9` became the canonical publish-legitimacy authority for `1B`

So the right synthesis for `1B` is this:

`1B` is the segment that turns a validated outlet-world from `1A` into a certified site-location authority by first proving read legitimacy, then building the lawful tile universe and tile-mass basis, then converting outlet counts into exact tile quotas, then realizing site-level tile and coordinate assignment under explicit RNG and geometry rules, and finally revalidating the whole result through a fingerprint-scoped publish gate.

State by state, the actual design reads like this.

`S0 - gate-in and foundations`

`S0` is not just setup. It is the state that makes the whole segment lawful.

It verifies:

- the 1A validation bundle
- the 1A passed flag
- the exact manifest-fingerprint handoff
- the sealed input inventory that later 1B states are allowed to trust

Its core job is to convert `1A` readiness into a durable consumer authority for `1B`. The important implemented shift is that `S0` became a real gate-in proof surface with standardized `manifest_fingerprint` naming, explicit sealed inputs, and governance support like `license_map`, rather than a loose preparatory shell.

So `S0` is the read-legitimacy and sealed-input authority of `1B`.

`S1 - tile universe`

`S1` is where `1B` stops being abstract and becomes spatially lawful.

It owns:

- the eligible raster-cell universe per country
- `tile_index`
- `tile_bounds`
- the deterministic `tile_id` law

The implementation history matters a lot here. `S1` was not merely "enumerate cells." It had to be materially repinned around:

- `world_countries` rebuild and coverage
- PROJ runtime override
- invalid geometry enforcement
- antimeridian correctness
- PAT and open-files observability

So `S1` is the segment's spatial-universe authority, not just a preprocessing step.

`S2 - tile weights`

`S2` takes the lawful tile universe and converts it into deterministic mass authority.

It owns:

- the governed weighting basis
- fixed-dp quantization
- per-country tile mass
- `tile_weights`

The remediation trail shows that `S2` became one of the main realism control surfaces in the actual segment. `blend_v2`, floors, caps, and penalties changed what `1B` could mean downstream, because concentration and coverage realism depended on this state materially.

So `S2` is the segment's deterministic tile-weight authority and one of its main realism levers.

`S3 - requirements frame`

`S3` takes `1A outlet_catalogue` and converts it into a country-count frame for spatial realization.

It owns:

- exact `n_sites` per `(merchant_id, legal_country_iso)`
- `s3_requirements`
- the proof that each active country is actually covered by `tile_weights`

Its important design boundary is what it refuses to do:

- it does not allocate to tiles
- it does not create cross-country order
- it does not invent counts from anything other than `outlet_catalogue`

So `S3` is the segment's country-requirements authority, but not a topology or order authority.

`S4 - allocation plan`

`S4` is where country counts become actual tile quotas.

It owns:

- deterministic integer allocation over eligible tiles
- largest-remainder quota closure
- exact sum-to-n conservation
- `s4_alloc_plan`

This is one of the clearest cases where design recovery matters more than the raw spec alone. In implementation, `S4` became:

- the main integer-topology authority
- the main anti-collapse and floor-aware realism surface
- and the main runtime-hardening hotspot for the whole segment

The performance work did not change its semantic burden. It changed what the actual implemented design had to include for the state to be usable: cache posture, allocation-kernel discipline, and fast-compute-safe determinism.

So `S4` is the segment's integer-topology authority, not just a rounding helper.

`S5 - site to tile assignment`

`S5` takes tile quotas and turns them into actual site-to-tile truth.

It owns:

- one row per site
- one draw per site
- exact preservation of S4 quotas
- `s5_site_tile_assignment`
- `rng_event_site_tile_assign`

Its design boundary is very sharp:

- `S4` owns counts
- `S5` owns which specific `site_order` fills those counts
- and `S5` is the only place where this assignment randomness is allowed to exist

The implementation history also made `S5` a major runtime and IO-remediation state. Signature-validated modes, buffered event emission, and reduced read amplification changed the actual design posture without changing its semantic authority.

So `S5` is the site-assignment truth boundary of `1B`.

`S6 - in-cell jitter`

`S6` takes assigned tiles and turns them into accepted within-country site positions.

It owns:

- in-pixel coordinate realization
- point-in-country acceptance
- bounded resample discipline
- `s6_site_jitter`
- `rng_event_in_cell_jitter`

The important recovered design point is that `S6` is not "make some coordinates." It is a governed spatial-acceptance state:

- one accepted realization per site
- one or more attempts per site
- explicit geometry authority
- explicit abort boundary if acceptance cannot be earned

So `S6` is the in-country spatial-realization authority of the segment.

`S7 - site synthesis`

`S7` joins the assignment and the accepted jitter back into final site rows.

It owns:

- reconstruction of final site coordinates
- inside-pixel conformance
- coverage parity back to `outlet_catalogue`
- `s7_site_synthesis`

This state matters because it converts the earlier stochastic truths into a final deterministic per-site synthesis while explicitly preserving the rule that 1B still has not created inter-country order.

So `S7` is the synthesized-site authority, but not the egress gate.

`S8 - egress publish`

`S8` publishes `site_locations`, but the most important thing about it is what it keeps narrow.

It creates:

- the final 1B egress surface
- the partition shift from parameter-scoped prep to seed+fingerprint egress
- an order-free downstream data surface

But it does not become a new semantic authority beyond publication of the rows already proven in `S7`. It also does not invent any cross-country order meaning.

So `S8` is the final data-surface materialization of `1B`, but not its legitimacy boundary.

`S9 - validation bundle and publish gate`

`S9` is the state that turns all prior work into something downstream systems are allowed to trust.

It owns:

- `validation_bundle_1B`
- `index.json`
- `_passed.flag`
- RNG accounting and reconciliation
- final parity and checksum proof over `site_locations`

The actual recovered design makes `S9` much more central than an implementation-only diagram would show. It is not just "bundle some receipts." It is the sole publish-legitimacy authority of the segment:

- no PASS means no downstream read
- the bundle is fingerprint-scoped
- parity, checksums, budgets, and trace reconciliation all have to agree

So `S9` is the segment's publish-legitimacy authority.

The shortest honest synthesis of the whole segment is this:

`1B` is the data-engine segment that takes a validated outlet-world from `1A`, builds a lawful tile universe and governed tile-mass basis, converts outlet counts into exact tile quotas, realizes those quotas into site-level tile and coordinate truth under explicit RNG and geometry rules, materializes an order-free site-location egress, and then certifies that egress through a fingerprint-scoped validation gate before anyone is allowed to read it.

That is why the segment matters architecturally.

It is not merely "where lat and lon get created."

It is the place where the engine proves that it can:

- separate upstream read legitimacy from downstream convenience
- separate tile universe, tile mass, quota, assignment, jitter, synthesis, and publish legitimacy into different owned truths
- keep RNG authority narrow and auditable
- preserve the rule that inter-country order still belongs to 1A
- and reunify all of that into one downstream-readable, gated site-location surface

That is the actual state design of `1B` as implemented.
