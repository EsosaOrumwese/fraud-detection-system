Segment `5A` state synthesis

`5A` is the Layer-2 traffic-modelling segment that turns the sealed Layer-1 merchant world into deterministic demand-intensity authority.

Its actual implemented design is not just:

- classify merchant behaviour
- attach a weekly shape
- add some calendar effects

It is a tighter Layer-2 contract system that does six things in order:

1. seals the exact Layer-1 and Layer-2 world that 5A is allowed to read
2. decides what kind of demand persona each merchant-zone belongs to and how large it is
3. fixes the unit-mass local-week template those personas should follow
4. composes scale and shape into baseline weekly intensity truth
5. projects that baseline into a scenario horizon under deterministic overlay laws
6. decides whether the whole intensity world deserves to be consumed at all

That makes `5A` less like a simple forecasting helper and more like a staged intensity-authority corridor:

- `S0` seals the world and the rules
- `S1` defines merchant-zone demand identity
- `S2` defines class-zone weekly form
- `S3` creates baseline weekly mass
- `S4` creates scenario-horizon mass
- `S5` decides whether downstream may trust any of it

The important part of the recovery is that the implemented design is shaped heavily by remediation and freeze posture.

The build plan and implementation notes show that `5A` was not merely implemented and accepted. It was repeatedly re-asked around a clear realism program:

- concentration and class realism belonged to `S1`
- weekly-shape authority remained deterministic and template-level in `S2`
- tail richness and baseline weekly composition became the key `S3` burden
- DST residual structure and overlay fairness became the key `S4` burden
- `S5` stayed the final validation rail and later carried integrated freeze and recertification authority

So the right synthesis for `5A` is this:

`5A` is the segment that turns a sealed merchant, zone, and virtual-world substrate into a certified deterministic demand-intensity world by separating demand class, weekly shape, baseline weekly mass, scenario horizon overlays, and final PASS legitimacy into different owned truths.

State by state, the actual design reads like this.

`S0 - gate and sealed inputs`

`S0` is not setup noise. It is what makes the rest of `5A` lawful.

It freezes:

- the Layer-1 PASS world from `1A` through `3B`
- the exact Layer-1 egress surfaces 5A may depend on
- the Layer-2 classing, shaping, baseline, and scenario policy packs
- the sealed inventory that all later 5A states are forced to inherit

The important implemented shift is that `S0` became a real Layer-2 multi-law gate rather than a dictionary lookup pass. It had to understand different upstream validation forms, including `3B`’s `members`-style bundle index, and it had to make the segment’s real fail-fast split explicit:

- `S0` may record FAIL or MISSING statuses
- but `S1+` must not run unless all required upstream segments are PASS

So `S0` is the lawful world-definition authority of `5A`, not a preamble.

`S1 - merchant-zone demand identity authority`

`S1` owns the first real modelling question:

- what demand class does each `(merchant, zone)` belong to?
- and how large is its baseline weekly scale?

That makes it more than a profile writer. Every downstream intensity surface depends on it:

- `S2` needs its class domain
- `S3` needs its base scale
- later validation and freeze work judge concentration partly by the world that `S1` created

The implemented design matters a lot here because `S1` had to pull in a sealed merchant snapshot from ingress rather than guess from Layer-1 egress. MCC and channel truth were not otherwise available in a contract-safe way. Later, when integrated seed-pack proving showed concentration failures, `S1` became the owner surface for that closure. That means `S1` is not merely descriptive; it is the accepted place where classing and scale realism are shaped.

So `S1` is the merchant-zone demand identity authority of `5A`.

`S2 - weekly shape authority`

`S2` takes the class and zone world from `S1` and turns it into deterministic weekly form.

It owns:

- the local-week bucket grid
- the unit-mass shape templates over that grid
- the mapping from class-zone combinations to those templates

The important thing about the recovered design is what `S2` does not do.

It does not:

- become merchant-specific
- apply calendar effects
- introduce randomness
- try to correct concentration or tail behaviour directly at the event level

Instead, it stays a template surface. The implementation notes show one especially important actual-design choice: although the specs allowed more dimensional flexibility, the implemented world locked to a mixed-channel output posture. So `S2` became the place where shape diversity is intentionally represented in a compressed, deterministic form rather than as a fully expanded channel lattice.

So `S2` is the weekly-shape authority of `5A`.

`S3 - baseline weekly intensity authority`

`S3` is where `5A` becomes materially quantitative.

It takes:

- base scale from `S1`
- weekly unit-mass shape from `S2`

and composes them into:

- baseline merchant-zone weekly intensity truth

This is one of the most important states in the segment because it is the first place where the full merchant-zone × bucket world is materialized. The implementation notes show that this was also the first major performance hotspot and later the accepted owner surface for tail-zone richness. That means `S3` is not just a multiplication step. It is the state where weekly mass, zone breadth, and bucket coverage actually become real and judgeable.

So `S3` is the baseline weekly intensity authority of `5A`.

`S4 - scenario horizon overlay authority`

`S4` takes the baseline world from `S3` and asks the next Layer-2 question:

- what should that world look like over the actual scenario horizon once calendar, campaign, payout, outage, DST, and other overlay effects are applied?

It owns:

- horizon mapping
- event-surface construction
- deterministic factor composition
- scenario-intensity output

This is where the implemented design diverged most strongly from a simple “apply multipliers” reading.

In the remediation program, `S4` became the owner surface for:

- DST residual structure
- overlay-country fairness

and later, in operational hardening, it also became a memory-safe execution boundary. That second point matters. The actual `S4` design is not only about semantics; it is also about how those semantics can be computed at the real output scale without crashing. The implemented design therefore includes chunked and reduced-residency composition as part of the segment’s actual posture, not as an incidental optimization.

So `S4` is the scenario-horizon overlay authority of `5A`.

`S5 - segment validation and PASS authority`

`S5` is where the whole Layer-2 traffic world is judged.

It reads:

- the sealed world from `S0`
- the class and scale world from `S1`
- the weekly-shape world from `S2`
- the baseline weekly world from `S3`
- the scenario-horizon world from `S4`

and then decides whether that full world deserves a `PASS` gate.

The important thing is that `S5` stayed an integrity rail throughout. It did not become a modelling rescue state. Realism and robustness were fixed in `S1`, `S3`, and `S4`; `S5` existed to judge, package evidence, and sign the result. That later mattered again during freeze and recertification: integrated `PASS_B`, then later `PASS_BPLUS_ROBUST`, were carried by `S5` without reopening accepted modelling outputs unnecessarily.

So `S5` is the PASS authority of `5A`.

The shortest honest synthesis of the whole segment is this:

`5A` is the Layer-2 segment that turns a sealed Layer-1 merchant world into a certified deterministic demand-intensity world by separating demand classification, weekly shape, baseline composition, scenario overlays, and final read legitimacy into distinct owned truths.

That is why the segment matters architecturally.

It is not merely “time series after Layer-1.”

It is the place where the engine proves that it can:

- turn merchant and zone semantics into deterministic traffic personas
- keep weekly form separate from weekly magnitude
- keep baseline mass separate from scenario overlay effects
- keep modelling surfaces separate from validation and freeze authority
- and still reunify those surfaces into one downstream-readable intensity world

The final implemented posture matters too.

`5A` did not stay at a provisional “good enough” state. It was taken through repeated remediation, froze at `PASS_B`, later reopened for bounded stretch recovery, and then reached `PASS_BPLUS_ROBUST`. That tells you what the actual design became:

- `S1` is the owner surface for concentration and demand identity
- `S2` is the deterministic template rail
- `S3` is the baseline mass and tail-richness surface
- `S4` is both the scenario-realism surface and the memory-safe execution boundary
- `S5` is the final certification and consumer-legitimacy boundary

That is the actual state design of `5A` as implemented.
