Segment `3A` state synthesis

`3A` is the zone-mixture realism segment for the data engine.

Its actual implemented design is not just:

- take outlet counts
- pick some zones
- then publish a zone allocation

It is a much tighter authority-building chain that does six things in order:

1. seals the lawful upstream outlet and civil-time world
2. decides which merchant-country pairs even deserve zone-mixture treatment
3. builds deterministic prior geometry for those escalated pairs
4. emits bounded stochastic zone-share dispersion with full provenance
5. turns those shares into conserved integer zone counts and readable egress
6. validates and seals whether that egress may be read downstream at all

That makes `3A` less like a generic sampler and more like a staged realism corridor:

- `S0` freezes the lawful upstream and policy world
- `S1` decides whether zone-mixture realism is in scope for a pair at all
- `S2`, `S3`, and `S4` are the real realism-shaping chain
- `S5` materialises the downstream-readable zone allocation
- `S6` and `S7` decide whether the segment deserves to be consumed

The important part of the recovery is that the actual implemented design is stricter than the raw state specs alone suggest. The remediation trail in `segment_3A.build_plan.md` and `segment_3A.impl_actual.md` shows that `3A` was not merely implemented and left alone. It was repeatedly re-asked around a clear realism corridor:

- `S2` prior geometry was treated as the first main tuning surface
- `S3` dispersion became the central sampled realism surface
- `S4` was deliberately kept narrow as conservation authority rather than turned into a free-form repair state
- `S1` later gained bounded deterministic smoothing, but only as support to the main realism chain
- `S6` and `S7` stayed veto rails, not optimization targets

So the right synthesis for `3A` is this:

`3A` is the segment that turns an already-certified outlet world into a gated zone-allocation authority by separating escalation, priors, sampled dispersion, integer conservation, readable egress, and publish legitimacy into different owned truths.

State by state, the actual design reads like this.

`S0 - gate and seal`

`S0` is not setup noise. It is what makes the rest of `3A` lawful.

It freezes:

- the upstream outlet world from `1A`
- the optional civil-time and legality context from `2A`
- the mixture and prior policies
- the manifest-scoped input seal that later stochastic states rely on

The important implemented shift is that `S0` became a real multi-upstream gate. `3A` does not treat outlet counts as sufficient on their own. It reads a sealed world in which outlet authority, time authority, and policy authority are already pinned.

So `S0` is the lawful-input authority of `3A`, not a preamble.

`S1 - escalation authority`

`S1` owns the first real design question:

- which merchant-country pairs should enter the zone-mixture realism corridor at all?

Its importance is larger than the queue itself because every later realism state is scoped by it. If `S1` does not escalate a pair, `S2` through `S4` must stay silent for that pair.

The recovered implementation posture matters here. `S1` remained deterministic and policy-bound, but later gained bounded smoothing on the `below_min_sites` branch. That means the implemented design is not merely “evaluate a static policy.” It is “preserve `S1` as sole escalation authority while allowing a narrow deterministic shape correction where the build plan proved it was needed.”

So `S1` is the segment's entry gate into zone realism.

`S2 - priors authority`

`S2` turns the escalated branch into the next core truth:

- the deterministic country-zone prior geometry

It owns:

- the country-to-zone prior basis
- floor and bump policy application
- the parameter-hash-scoped priors table that later sampled states are forced to inherit

The actual implemented posture matters a lot here because `P1` treated `S2` as the first main realism surface. So `S2` is not merely a lookup or translation state. It is the first place where the segment decides what a realistic zone distribution should look like before any RNG enters.

So `S2` is the priors authority surface of `3A`.

`S3 - sampled dispersion authority`

`S3` is where `3A` becomes stochastic in a controlled way.

It takes:

- the escalated pair set from `S1`
- the deterministic prior geometry from `S2`
- the manifest-scoped RNG stream

and emits:

- Dirichlet zone shares
- event logs
- trace and audit evidence

This is one of the most important states in the segment because it owns sampled dispersion without being allowed to blur provenance. The remediation trail shows exactly that: `S3` became the central merchant-dispersion surface, and even when final certification froze the segment below `B`, the remaining realism question still lived here rather than in later validation or publish states.

So `S3` is the zone-share dispersion authority of `3A`.

`S4 - integer conservation authority`

`S4` takes continuous share truth and turns it into integer counts.

Its design burden is very specific:

- preserve the upstream dispersion meaning from `S3`
- conserve totals for each `(merchant, country)`
- avoid inventing a new realism policy of its own

The actual implemented design stayed disciplined here. `P3` anti-collapse work ended as a bounded `NOOP` lock, which means `S4` remained what it should be: a deterministic conservation surface, not an open-ended repair layer.

So `S4` is the integerised allocation authority, but intentionally not a new sampled realism authority.

`S5 - egress and universe closure`

`S5` writes the downstream-readable `zone_alloc`, but the most important thing about its design is what it binds.

It owns:

- deterministic egress materialisation
- the `zone_alloc_universe_hash`
- the explicit statement of which world the published allocation actually covers

The recovered design matters here because in `v1` this surface intentionally contains escalated pairs only. That means `S5` is not pretending to publish a universal zone world. It publishes a bounded surface and then binds the exact universe hash so downstream consumers cannot silently widen its meaning.

So `S5` is the readable egress authority of `3A`, but not the segment's verdict authority.

`S6 - validation verdict authority`

`S6` is where the segment stops generating reality and starts judging it.

It reads:

- the escalation queue
- prior geometry
- sampled shares
- integer counts
- egress and audit surfaces

and publishes:

- the validation report
- issue tables
- the receipt that decides `PASS` or `FAIL`

The important design recovery here is that `S6` stayed a veto rail. The build plan explicitly treats `S0`, `S6`, and `S7` as contract and gate states, not realism-tuning states. That means `S6` should never be read as “the place where 3A gets fixed.” It is the place where 3A is judged.

So `S6` is the sole verdict authority of `3A`.

`S7 - publish legitimacy`

`S7` turns the verdict into a consumer contract.

Its job is not to add new realism. Its job is to publish:

- `validation_bundle_3A`
- `index.json`
- `_passed.flag`

so that downstream segments know whether `3A` outputs are actually consumable.

The implemented design makes this state more important than a simple receipt writer. It is the segment's publish-legitimacy boundary. Without `S7`, downstream consumers have an artefact set; with `S7`, they have an indexed declaration of whether the segment passed and may be trusted.

So `S7` is the read-authorisation boundary of `3A`.

The shortest honest synthesis of the whole segment is this:

`3A` is the data-engine segment that turns a sealed outlet-world into a bounded zone-allocation authority by separating escalation, deterministic priors, bounded stochastic dispersion, conserved integerisation, readable egress, and validation legitimacy into distinct owned truths.

That is why the segment matters architecturally.

It is not merely a random allocation stage.

It is the place where the engine proves that it can:

- keep policy scope separate from sampled realism
- keep sampled dispersion separate from deterministic conservation
- keep readable egress separate from verdict legitimacy
- and still reunify those surfaces into one downstream-usable, manifest-scoped zone-allocation world

The final implemented posture also matters.

`3A` did not close as a clean high-grade realism segment. It froze as a best-effort bounded authority below `B`, with the remaining burden concentrated in the realism corridor rather than in the gate states. That makes the implemented design even clearer:

- `S2`, `S3`, and `S4` are where realism is actually shaped
- `S1` is a bounded support lane
- `S6` and `S7` are where truth is judged and published, not repaired

That is the actual state design of `3A` as implemented.
