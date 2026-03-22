Segment `3B` state synthesis

`3B` is the virtual-merchants and CDN-surfaces segment for the data engine.

Its actual implemented design is not just:

- classify some merchants as virtual
- place CDN edges
- then write alias tables

It is a much tighter contract system that does six things in order:

1. seals a lawful cross-segment environment for the virtual world
2. decides which merchants belong to that virtual world and where their legal settlement anchor is
3. builds the static edge topology that virtual routing is actually allowed to use
4. turns that edge world into a decode-ready alias representation with integrity closure
5. freezes the semantics of how routing and validation must interpret that world
6. decides whether the full virtual world deserves to be read at all

That makes `3B` less like a convenience add-on and more like a staged virtual-routing authority:

- `S0` seals the admissible world
- `S1` defines virtual membership and settlement semantics
- `S2` creates the actual CDN edge world
- `S3` packages that world for decode and integrity
- `S4` freezes its routing and validation meaning
- `S5` decides whether any of it is trustworthy enough to consume

The important part of the recovery is that the actual implemented design is much more shaped by remediation and freeze posture than the raw state specs alone suggest.

The build plan and implementation notes show that `3B` was not merely implemented and accepted. It was taken through a clear realism and governance program:

- `S1` had to become explainable and lineage-complete
- `S2` had to stop behaving like a degenerate global template and become a merchant-conditioned, settlement-coupled edge topology surface
- `S4` had to stop being a thin descriptive contract and become a real realism-governance surface
- `S3` and `S5` had to remain hard integrity rails throughout
- the final frozen posture was not just structural PASS, but certified realism with later freeze and recertification discipline

So the right synthesis for `3B` is this:

`3B` is the segment that turns a sealed merchant and geography world into a certified virtual-routing world by separating virtual membership, legal settlement anchors, static edge topology, alias representation, routing semantics, validation governance, and final PASS legitimacy into different owned truths.

State by state, the actual design reads like this.

`S0 - gate and environment seal`

`S0` is not setup noise. It is what makes the rest of `3B` lawful.

It freezes:

- upstream validation authority from `1A`, `1B`, `2A`, and `3A`
- the exact external policies and references the virtual/CDN segment may read
- the spatial and timezone surfaces that later states depend on
- the manifest-scoped sealed input inventory that all later states are forced to inherit

The important implemented shift is that `S0` became a real environment seal rather than a minimal gate. `3B` had to expand the sealed universe to include the actual spatial and timezone assets its downstream states needed, and it had to respect different upstream bundle laws correctly.

So `S0` is the lawful environment authority of `3B`, not a preamble.

`S1 - virtual classification and settlement authority`

`S1` owns the first real semantic question:

- which merchants are virtual for this manifest?
- and, for each such merchant, what is the legal settlement node?

That makes it more important than a classifier output. Every downstream virtual surface depends on it:

- `S2` must only build edges for the virtual merchant world that `S1` defined
- later routing and validation semantics must refer back to S1’s settlement anchor rather than inventing one

The actual implemented posture matters a lot here because `S1` was remediated for lineage realism. Rule IDs, versions, and rule diversity stopped being incidental metadata and became design burdens. Later, a bounded reopen also made `S1` the owner surface for hybrid-share shape when downstream proving exposed that the earlier binary posture was too restrictive.

So `S1` is the segment's virtual-membership and settlement-anchor authority.

`S2 - edge-topology authority`

`S2` is where `3B` becomes materially operational.

It takes:

- the virtual merchant world from `S1`
- the settlement anchors from `S1`
- sealed spatial, timezone, and policy surfaces from `S0`
- the reserved RNG policy for placement and jitter

and produces:

- the static edge catalogue
- the index over that catalogue
- the only legitimate RNG evidence for edge construction

This is the most important realism state in the segment.

The remediation trail shows exactly why. Early `3B` realism defects were not mainly about aliasing or bundle gates. They were concentrated in the edge world itself:

- too little merchant-to-merchant divergence
- weak settlement coupling
- degenerate geography

That is why `S2` became the dominant realism lane and also the dominant performance lane. Its implemented design had to be repinned both statistically and operationally:

- merchant-conditioned topology replaced the earlier global-template behaviour
- settlement-coupled weighting became part of the real design
- tile-surface preparation had to be redesigned repeatedly to remove memory collapse without changing contracts

So `S2` is the edge-topology authority and the real realism engine of `3B`.

`S3 - alias and integrity representation authority`

`S3` takes the static edge world from `S2` and turns it into something a routing runtime can consume efficiently:

- a packed alias blob
- an alias index
- a universe hash that binds the representation back to the sealed world

The key thing about the recovered design is what `S3` does not do.

It does not:

- invent new edge semantics
- change edge weights
- add new randomness
- become another realism-tuning surface

Instead, it is intentionally narrow. It packages S2’s edge world into a deterministic decode surface and then seals the integrity of that representation. The implementation notes reinforce that posture through digest-law clarification, layout compatibility fixes, and an explicit guardrail for forbidden RNG use.

So `S3` is the representation and integrity authority of `3B`, not a generator.

`S4 - routing-semantics and governance authority`

`S4` is where `3B` stops generating virtual reality and starts defining what that reality must mean downstream.

It freezes:

- how virtual routing must interpret settlement versus operational clocks
- how 2B must use alias and universe-hash surfaces
- which validation families and thresholds must be applied later to judge the virtual path

This is where actual design recovery matters a lot.

In the raw spec posture, `S4` can look like a contract writer. In the implemented posture, it became much stronger than that. The build plan made `S4` one of the three main remediation surfaces, and `P3` explicitly turned it into a realism-governance lane:

- observe and enforce semantics were added
- validation families expanded so unrealistic virtual runs could fail closed
- `S1` through `S3` stayed frozen while `S4` took ownership of governance coverage

So `S4` is the routing-semantics and realism-governance authority of `3B`.

`S5 - validation bundle and PASS authority`

`S5` is where the whole virtual world is judged.

It reads:

- the sealed environment from `S0`
- all semantic and topology outputs from `S1` through `S4`
- the RNG evidence emitted by `S2`

and then decides whether `3B` deserves to be read downstream at all.

Its design role is strict:

- re-audit the full 3B world
- package evidence
- emit the PASS gate

The important thing is that `S5` remained an integrity rail even while the segment was being remediated. Realism was shaped in `S1`, `S2`, and `S4`. `S5` existed to judge and seal, not to rescue.

That later mattered again when freeze closure discovered stale certification artefacts. The accepted repair was scoring-only recertification, which restored the authoritative `S5` evidence surface without mutating already-accepted state outputs. That is a strong signal about the actual design: `S5` is the certification and consumer-legitimacy boundary, not another modeling surface.

So `S5` is the PASS authority of `3B`.

The shortest honest synthesis of the whole segment is this:

`3B` is the data-engine segment that turns a sealed upstream merchant world into a governed virtual-routing world by separating virtual membership, settlement anchors, edge topology, alias representation, routing semantics, validation governance, and final read legitimacy into distinct owned truths.

That is why the segment matters architecturally.

It is not merely the place where virtual merchants get “extra infra.”

It is the place where the engine proves that it can:

- distinguish legal settlement truth from apparent operational geography
- distinguish static edge-world construction from runtime routing
- distinguish representation fidelity from realism shaping
- distinguish governance and validation semantics from the generation surfaces they judge
- and still reunify all of those surfaces into one downstream-readable virtual world

The final implemented posture matters too.

`3B` did not stay a weak experimental virtual lane. It was taken through a full remediation stack, reached `PASS_B`, then `PASS_BPLUS`, and later entered freeze with scoring-only recertification discipline. That tells you what the real design became:

- `S1` is a living owner surface for virtual classification shape
- `S2` is the dominant realism and performance engine
- `S3` and `S5` are integrity rails
- `S4` is the semantic and governance bridge that makes the whole virtual world accountable

That is the actual state design of `3B` as implemented.
