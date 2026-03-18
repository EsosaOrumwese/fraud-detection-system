Segment `2B` state synthesis

`2B` is the segment that turns the frozen spatial world from `1B` and the civil-time world from `2A` into a governed routing-realism system.

Its actual implemented design is not just:

- build alias tables
- run a router
- then bundle some receipts

It is a staged routing-authority segment that does nine things in order:

1. proves that upstream spatial and civil-time truth are lawful to read at all
2. freezes deterministic per-site mass for each merchant
3. converts those masses into byte-stable decode artefacts
4. adds bounded temporal modulation at the tz-group level
5. converts base shares plus modulation into day-level group-routing truth
6. runs the live two-stage router with explicit RNG budgets
7. optionally branches virtual merchants onto a separate edge-routing decision
8. audits all of that for artefact coherence and runtime evidence
9. publishes the final manifest-scoped PASS gate before any downstream consumer is allowed to trust the segment

That makes `2B` less like a “sampler” and more like a staged routing contract system:

- `S0` creates legal read and routing-policy authority
- `S1` creates deterministic site-mass authority
- `S2` creates decode authority
- `S3` creates temporal modulation authority
- `S4` creates per-day group-routing authority
- `S5` and `S6` create replayable live routing evidence
- `S7` creates audit legitimacy
- `S8` creates consumer publish legitimacy

The important recovery point is that the actual implemented design is much more remediation-shaped than the raw state docs alone suggest.

The trail in `segment_2B.build_plan.md` and `segment_2B.impl_actual.md` shows that different states carried very different kinds of responsibility in practice:

- `S0` became a true seal over both 1B site layout and 2A timezone truth
- `S1`, `S3`, and `S4` became the real realism-control surfaces
- `S2` stayed mostly a mechanical contract surface
- `S5` and `S6` became the runtime truth and replayability surfaces
- `S7` and `S8` became the legitimacy closure surfaces

So the right synthesis for `2B` is this:

`2B` is the segment that takes a validated site world and timezone world, freezes deterministic site mass, turns that into byte-stable routing decode truth, modulates it through bounded temporal and tz-group realism, executes a replayable per-arrival routing path, and then certifies the whole routing family through audit and a final PASS gate before any downstream consumer is allowed to rely on it.

State by state, the actual design reads like this.

`S0 - gate and environment seal`

`S0` is not just startup work.

It verifies:

- the `1B` validation bundle
- the `1B` passed flag
- the required `2A` pin surfaces
- the routing policy packs that define how later RNG-bounded states are allowed to behave

Its core job is to convert upstream `1B` and `2A` truth into a durable routing authority set for `2B`.

The important implemented shift is that `S0` became a real routing-environment seal. It does not just note that policies exist; it freezes the exact policy and upstream truth surfaces that make later routing evidence interpretable.

So `S0` is the read-legitimacy and routing-environment authority of `2B`.

`S1 - per-merchant weight freezing`

`S1` is where `2B` first becomes a routing segment instead of an input seal.

It owns:

- deterministic per-site merchant mass
- policy-driven floors and caps
- quantised site weights
- `s1_site_weights`

The implementation history shows that `S1` became the primary spatial heterogeneity control surface in remediation. That matters because it means `S1` is not only a technical precondition for alias tables; it is the first place where routing realism can either activate or collapse.

So `S1` is the segment’s site-mass authority and first realism lever.

`S2 - alias tables`

`S2` takes deterministic site mass and turns it into decodeable sampling artefacts.

It owns:

- `s2_alias_index`
- `s2_alias_blob`
- layout parity
- digest parity
- O(1) decode truth

The recovery point that matters most is that `S2` is not where realism is mainly shaped. It is where mechanical decode truth is frozen.

That is why the remediation trail treated `S2` as a non-regression support surface more than a realism target.

So `S2` is the segment’s byte-stable alias authority.

`S3 - corporate-day modulation`

`S3` introduces bounded temporal movement into the routing world.

It owns:

- per-merchant, per-day, per-tz-group gamma factors
- bounded Philox draws
- embedded RNG provenance
- `s3_day_effects`

The implemented design matters here because `S3` is not “noise.” It is a controlled temporal heterogeneity surface that perturbs routing in the short run while preserving long-run share truth.

So `S3` is the segment’s temporal modulation authority.

`S4 - zone-group renormalisation`

`S4` turns base site mass and gamma into actual group-routing truth.

It owns:

- aggregation of site mass by tzid
- multiplication by gamma
- cross-group renormalisation
- `s4_group_weights`

This is one of the clearest cases where design recovery matters more than the raw spec alone.

In implementation, `S4` became the main anti-collapse realism surface. It is where multi-group routing either exists in practice or collapses into single-group dominance. Later blocker analysis repeatedly surfaced here because this state exposes when the upstream topology does not actually support the realism target.

So `S4` is the segment’s group-routing authority and main anti-collapse surface.

`S5 - router core`

`S5` takes the day-level group mix and turns it into actual arrival-level routing truth.

It owns:

- Stage A group pick
- Stage B site pick
- exactly two draws per arrival
- event and trace evidence
- optional selection log

The recovered design point is that `S5` is not just “execute the sampler.”

It is the main live runtime truth surface of the segment:

- ordered
- replayable
- bounded by explicit Philox budgets
- reconciled through audit and trace logs

So `S5` is the segment’s live routing authority.

`S6 - virtual edge routing`

`S6` is a branch, not a second router.

It owns:

- the virtual-merchant-only edge pick
- exactly one additional draw for virtual arrivals
- zero draws for non-virtual arrivals
- edge-routing evidence

That matters because `S6` proves the segment can support a special routing branch without corrupting the core `S5` routing truth.

So `S6` is the bounded exception authority of the segment.

`S7 - audits and CI gate`

`S7` is where the segment asks whether all earlier artefacts and, when present, runtime logs, still agree as one coherent routing story.

It owns:

- alias parity checks
- S3/S4 coherence checks
- optional S5/S6 evidence reconciliation
- `s7_audit_report`

The important recovered design point is that `S7` does not depend on runtime logs being present in order to audit the segment’s core truth. It can validate artefact coherence first, then incorporate runtime evidence when available.

So `S7` is the segment’s audit-legitimacy authority.

`S8 - validation bundle and PASS flag`

`S8` is the state that turns the segment from “audited” into “downstream-readable.”

It owns:

- `validation_bundle_2B`
- `index.json`
- `_passed.flag`
- manifest-scoped consumer legitimacy

Its actual implemented meaning is much stronger than “bundle some reports.”

It is the sole publish-legitimacy authority of `2B`:

- no PASS means no downstream read
- all discovered seeds must have PASS audits
- the segment’s legitimacy becomes one indexed, hashed proof surface

So `S8` is the publish-legitimacy authority of `2B`.

The shortest honest synthesis of the whole segment is this:

`2B` is the data-engine segment that takes a validated site world from `1B` and a validated timezone world from `2A`, freezes deterministic site mass, turns it into byte-stable routing decode truth, adds bounded temporal and group-level realism, executes replayable arrival routing under explicit RNG laws, and then certifies the whole routing family through audit and a final PASS gate before any downstream consumer is allowed to trust it.

That is why the segment matters architecturally.

It is not merely “where requests get routed.”

It is the place where the engine proves that it can:

- separate upstream environment authority from routing authority
- separate deterministic plan surfaces from live runtime evidence surfaces
- keep realism shaping and mechanical decode truth in different owned states
- keep RNG bounded, attributable, and replayable
- and reunify all of that into one downstream-readable legitimacy gate

That is the actual state design of `2B` as implemented.
