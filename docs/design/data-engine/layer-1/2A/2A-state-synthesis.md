Segment `2A` state synthesis

`2A` is the segment that turns the spatial site world from `1B` into a governed civil-time world that downstream segments are allowed to trust.

Its actual implemented design is not just:

- look up a timezone
- maybe apply an override
- then emit a cache and a report

It is a gated civil-time legitimacy segment that does six things in order:

1. proves that `1B` egress is lawful to read at all
2. converts site coordinates into a deterministic provisional timezone world
3. turns that provisional world into final per-site timezone authority under explicit override governance
4. compiles the transition authority that later legality claims are allowed to depend on
5. proves that the final timezone world is actually legal against that transition authority
6. publishes a manifest-scoped PASS gate that downstream consumers must verify before reading `site_timezones`

That makes `2A` less like a timezone enrichment utility and more like a staged civil-time contract system:

- `S0` creates legal read and sealed-input authority
- `S1` creates provisional geometry-earned timezone authority
- `S2` creates final per-site timezone authority
- `S3` creates transition-cache authority
- `S4` creates legality proof authority
- `S5` creates downstream publish legitimacy

The important recovery point is that the actual implemented design is much more remediation-shaped than the raw state docs alone suggest.

The trail in `segment_2A.build_plan.md` and `segment_2A.impl_actual.md` shows that several states became materially different design objects in implementation:

- `S0` became a true cross-segment gate, not just setup
- `S1` and `S2` became governance and realism-control boundaries, not just lookup mechanics
- `S3` became a transition-horizon authority, especially after the bounded future-transition reopen
- `S5` became the real downstream contract surface for `2A`

So the right synthesis for `2A` is this:

`2A` is the segment that takes a validated site-location world from `1B`, binds it to a sealed civil-time authority set, turns each site into a final timezone-bearing site under deterministic geometry and governed override rules, proves that those timezone assignments are legally covered by a manifest-scoped transition cache, and then certifies the result through a fingerprint-scoped bundle gate before anyone is allowed to read `site_timezones`.

State by state, the actual design reads like this.

`S0 - gate and sealed inputs`

`S0` is not just preparatory work.

It verifies:

- the `1B` validation bundle
- the `1B` passed flag
- the exact `manifest_fingerprint` handoff
- the sealed civil-time input set that later `2A` states are allowed to trust

Its core job is to convert upstream `1B` readiness into a durable consumer authority for `2A`.

The important implemented shift is that `S0` became a real gate-in proof surface with deterministic receipt content, fixed `verified_at_utc`, and minimal-but-explicit sealing of the actual assets `2A` is allowed to use.

So `S0` is the read-legitimacy and sealed-input authority of `2A`.

`S1 - provisional timezone lookup`

`S1` is where the segment becomes civil-time specific.

It owns:

- geometry-only provisional timezone assignment
- single-pass epsilon nudge for border ambiguity
- ambiguity provenance
- `s1_tz_lookup`

But the implementation history matters more than the raw spec alone.

`S1` became a governance surface, not only a lookup surface. The actual design had to make fallback use explicit, measured, capped, and fail-closed. It also had to make ambiguity handling readable enough that later realism and governance scoring could trust what happened.

So `S1` is the segment's provisional timezone authority and first civil-time governance choke-point.

`S2 - final timezone assignment`

`S2` takes provisional timezone truth and converts it into final per-site timezone authority.

It owns:

- active override evaluation
- precedence `site > mcc > country`
- provenance completeness
- carry-through of `S1` nudge and assignment lineage
- `site_timezones`

The actual implemented design makes `S2` more important than “apply overrides.”

It became:

- the final governance boundary for timezone assignment
- the place where override caps and provenance completeness are enforced
- the segment’s final per-site civil-time authority

There was also a later experimental deterministic rebalance lane for downstream support, but that was deliberately removed from mainline after a bounded no-go.

So the canonical implemented design of `S2` remains final governed timezone assignment, not topology editing.

`S3 - transition cache`

`S3` takes the sealed tzdb release and turns it into transition authority.

It owns:

- the deterministic manifest-scoped transition index
- cache digest and publish discipline
- `tz_timetable_cache`

The recovered design point that matters most is that `S3` is not just “make a cache for faster lookups.”

In implementation it became:

- the authoritative transition horizon for the whole segment
- a major performance-hardening surface
- and later a real reopen boundary when downstream work proved the original horizon truncated too early for 2026 DST behavior

So `S3` is the segment’s transition-authority surface, not a convenience optimization.

`S4 - legality report`

`S4` takes the final timezone assignments and judges them against the transition authority.

It owns:

- cache coverage checks for all used tzids
- derived gap and fold legality counts
- per-seed PASS or FAIL evidence
- `s4_legality_report`

Its design boundary is sharp:

- it does not assign timezones
- it does not rebuild transitions
- it does not publish consumer legitimacy

It exists to prove that the civil-time world created by `S2` is actually legal against the manifest-scoped transition truth from `S3`.

So `S4` is the segment’s legality-proof authority.

`S5 - validation bundle and PASS gate`

`S5` turns all prior work into something downstream systems are allowed to trust.

It owns:

- seed discovery from `site_timezones`
- completeness of `S4` PASS evidence for every discovered seed
- `validation_bundle_2A`
- `index.json`
- `_passed.flag`

The actual recovered design makes `S5` much more central than a spec-only reading would suggest.

It is not just “bundle some evidence.”

It is the sole publish-legitimacy authority of `2A`:

- no PASS means no downstream read
- legality evidence has to exist for every discovered seed
- the manifest-scoped bundle becomes the consumer contract for `site_timezones`

So `S5` is the segment’s publish-legitimacy authority.

The shortest honest synthesis of the whole segment is this:

`2A` is the data-engine segment that takes a validated site-location world from `1B`, binds it to a sealed civil-time input set, earns a deterministic per-site timezone world through geometry and governed override rules, proves that world against manifest-scoped transition legality, and then certifies the result through a final validation bundle and PASS gate before any downstream read is allowed.

That is why the segment matters architecturally.

It is not merely “where timezones get attached.”

It is the place where the engine proves that it can:

- separate upstream read legitimacy from civil-time transformation
- separate provisional assignment, final assignment, transition authority, legality proof, and publish legitimacy into different owned truths
- keep civil-time governance explicit rather than implicit
- preserve causal lineage from `1B site_locations` to downstream-readable `site_timezones`
- and reunify all of that into one manifest-scoped consumer gate

That is the actual state design of `2A` as implemented.
