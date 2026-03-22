Segment `1A` state synthesis

`1A` is the root realism segment for the data engine.

Its actual implemented design is not just:

- merchant ingress
- some stochastic branching
- then outlet rows

It is a tightly staged authority-building segment that does five things in order:

1. freezes the run's lawful universe and deterministic lineage basis
2. decides whether a merchant is single-site or multi-site
3. fixes the total multi-site outlet count
4. builds the legal cross-border domain and foreign-target structure
5. materialises a gated, replayable egress surface that downstream segments are allowed to trust

That makes `1A` less like a simple generator and more like a layered contract system:

- S0 creates the lawful run basis
- S1 and S2 create the first stochastic truths
- S3 through S7 progressively convert those truths into structured geographic and count decisions
- S8 materialises the egress
- S9 decides whether that egress deserves to be read at all

The important part of the recovery is that the actual implemented design is stricter and more operationally shaped than the raw state specs alone suggest. The remediation trail in `segment_1A.build_plan.md` and `segment_1A.impl_actual.md` shows that several surfaces became real design boundaries in implementation:

- `S9` became the canonical validation publisher
- `S5` and `S6` became gated authority surfaces with explicit pass receipts
- `S3` became the explicit single source of inter-country order authority
- the accepted `P1`, `P2`, `P3`, `P4`, and `P5` closures changed what `1A` actually is, because the segment was not merely implemented, it was remediated, frozen, and certified against realism and determinism burdens

So the right synthesis for `1A` is this:

`1A` is the segment that turns a sealed merchant world into a certified outlet-world authority through deterministic lineage control, branch-gated stochastic realism, explicit cross-border order authority, deterministic country-weight and allocation bridges, fingerprint-scoped egress, and final replay validation.

State by state, the actual design reads like this.

`S0 - foundations`

`S0` is not just setup. It is the state that makes the rest of `1A` lawful.

It freezes:

- the merchant universe
- reference authority
- schema authority
- parameter lineage
- manifest lineage
- deterministic precompute surfaces

Its core design job is to make every later stochastic state replayable and attributable. The important implemented shift is that `S0` stopped trying to act as the canonical validation publisher. `validation_bundle_1A` emission was moved out of its default posture so that `S9` could own publish legitimacy cleanly.

So `S0` is best understood as the lineage and precompute authority of `1A`, not just a preamble.

`S1 - hurdle`

`S1` owns the first real stochastic decision:

- does this merchant enter the multi-site world or not?

Its design importance is larger than the Bernoulli draw itself, because it becomes the sole branch authority for everything downstream. If `S1` says `is_multi=false`, downstream multi-site states must remain silent for that merchant.

The actual implemented design hardened this state around:

- strict shape alignment between design matrix and coefficients
- exact replay discipline
- trace strictness
- one-event-per-merchant authority

So `S1` is the segment's branch gate, not just a logistic sampler.

`S2 - NB outlets`

`S2` takes the multi-site branch and converts it into the second core truth:

- the accepted total outlet count `N`

Its design is a disciplined decomposition:

- deterministic link evaluation
- Gamma mixture component
- Poisson component
- accepted NB finaliser

The actual implemented posture matters here because `S2` was later remediated and frozen through `P1`. That means the implemented design is not merely "NB exists," but "NB mean and dispersion were corrected, locked, and then treated as frozen upstream realism authority for later states."

So `S2` is the total-count authority surface for `1A`.

`S3 - candidate universe`

`S3` is where `1A` stops being mainly about merchant realism and starts being about structured geographic realism.

It owns:

- which foreign countries are admissible
- why they are admissible
- and in what total inter-country order they must be read

This is one of the most important design states in the whole segment because `candidate_rank` becomes the sole inter-country order authority. Later states may select, allocate, and materialise, but they are not allowed to invent a different cross-country order.

The actual implemented design shifted `S3` materially through `P2`:

- away from a near-global open-world candidate posture
- toward profile-conditioned candidate breadth
- and toward a more realistic coupling between candidate breadth and later realization

So `S3` is the segment's legal-domain and inter-country-order authority.

`S4 - ZTP target`

`S4` does not choose countries. It does something narrower:

- it fixes the foreign-count target `K_target`

Its design is deliberately logs-only:

- parameterise intensity
- run ZTP attempts
- reject zero draws
- emit a non-consuming finaliser that fixes `K_target`

That matters because `S4` defines a foreign-count ambition without becoming a selection state. It hands a count target forward while leaving country identity and order outside its scope.

So `S4` is the foreign-count authority, not the foreign-membership authority.

`S5 - weight authority`

`S5` is one of the clearest examples of actual design recovery mattering more than raw spec reading.

In the recovered design, `S5` is not just a deterministic cache. It is the state that turns currency surfaces into a reusable country-weight authority and then makes that authority gateable for downstream use.

It owns:

- `merchant_currency`
- `ccy_country_weights_cache`
- `sparse_flag`
- and an explicit pass receipt for downstream reads

The remediation history shows that `S5` became a real bridge state during `P2`, because support sparsity and coverage realism materially affected whether the later foreign-realisation story could hold.

So `S5` is the segment's deterministic weight authority and support-feasibility bridge.

`S6 - foreign selection`

`S6` takes:

- the ordered candidate world from `S3`
- the target count from `S4`
- the weight authority from `S5`

and turns them into actual foreign membership.

Its design boundary is subtle but important:

- it selects membership
- but it does not become a new order authority
- and it does not become a new weight authority

That is why the recovered design keeps `S6` narrow:

- order still belongs to `S3`
- weights still belong to `S5`
- `S6` owns only the realized membership choice

The implemented design also made `S6` operationally stronger by introducing a convenience membership surface plus a receipt gate, but without letting that convenience surface replace event-level truth.

So `S6` is the membership authority sitting between order and allocation.

`S7 - integer allocation`

`S7` turns the selected country domain into integer per-country counts that sum exactly to `N`.

Its design burden is:

- preserve the domain from `S6`
- preserve the order boundary from `S3`
- preserve the weight authority from `S5`
- and still allocate deterministic integers without inventing a new authority surface

That is why `residual_rank` matters so much in the recovered design. It is not just an internal helper. It is the replayable evidence for the largest-remainder allocation discipline.

So `S7` is the integer allocation authority, but intentionally not a new order or weight authority.

`S8 - egress materialisation`

`S8` writes `outlet_catalogue`, but the most important thing about its design is what it refuses to do.

It creates:

- outlet stubs
- within-country sequencing
- site IDs

But it does not encode cross-country order in the egress. That boundary is central to the actual `1A` design:

- `outlet_catalogue` is readable egress
- but inter-country order still has to be recovered by joining `S3 candidate_rank`

So `S8` is the materialisation state, but not the full semantic authority of the outlet world on its own.

`S9 - replay validation and publish gate`

`S9` is the state that turns all prior work into something downstream systems are allowed to trust.

Its job is not to generate more reality. Its job is to re-derive and verify the realities already claimed by `S0` through `S8`, then publish:

- `validation_bundle_1A`
- `index.json`
- `_passed.flag`

The actual recovered design makes `S9` much more central than the earlier DAGs could show, because it became the canonical publisher of validation legitimacy after `S0` stopped trying to do that by default. In other words, `S9` is not just a final nice-to-have receipt state. It is the segment's read-authorisation boundary.

So `S9` is the publish-legitimacy authority of `1A`.

The shortest honest synthesis of the whole segment is this:

`1A` is the data-engine segment that establishes a lawful merchant world, turns that world into branch-gated and count-gated outlet realism, constructs an ordered cross-border domain, realises foreign membership and per-country allocation without blurring order and weight authorities, materialises outlet egress without encoding forbidden cross-country meaning, and then validates the whole result through a fingerprint-scoped publish gate.

That is why the segment matters architecturally.

It is not merely first in the build order.

It is the first place where the engine proves that it can:

- separate authority from convenience
- separate stochastic decision from deterministic lineage
- separate domain/order/weight/membership/allocation/materialisation into different owned truths
- and still reunify them into one downstream-readable, replayable, gated egress surface

That is the actual state design of `1A` as implemented.
