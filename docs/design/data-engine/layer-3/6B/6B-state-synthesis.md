Segment `6B` state synthesis

`6B` is the Layer-3 behavioural and supervision segment that turns the sealed arrival world from `5B` and the sealed entity world from `6A` into a closed flow, event, fraud, label, and case world.

Its actual implemented design is not just:

- attach transactions to customers
- generate some behaviour
- add fraud labels at the end

It is a tighter behavioural authority corridor that does six things in order:

1. seals the exact upstream world, contracts, and behavioural policies that `6B` may depend on
2. attaches every arrival to the Layer-3 entity world and defines session structure
3. turns that attached arrival world into a legitimate baseline flow and event world
4. overlays fraud and abuse behaviour with explicit campaign provenance
5. turns the overlaid behavioural world into truth labels, bank-view labels, event labels, and case chronology
6. decides whether the whole behavioural world deserves to be consumed at all

That makes `6B` less like a synthetic event expander and more like a staged behavioural-world authority:

- `S0` seals the world
- `S1` defines who each arrival belongs to and how sessions exist
- `S2` defines legitimate flows and event structure
- `S3` defines fraud campaign and abuse overlay truth
- `S4` defines supervision and case truth
- `S5` defines final segment legitimacy

The important recovery point is that the actual implemented design is shaped heavily by remediation ownership.

The build plan and implementation notes show that `6B` was not merely implemented and left alone. It was re-asked around a clear owner-state structure:

- `S1` owned attachment and session realism while also carrying the main runtime hotspot burden
- `S2` owned amount and timing realism for the legitimate baseline
- `S3` owned campaign multiplicity and targeting depth
- `S4` owned truth-label, bank-view, and case-timeline realism
- `S5` owned fail-closed certification and final behavioural-world legitimacy

So the right synthesis for `6B` is this:

`6B` is the segment that turns a sealed arrival and entity world into a certified behavioural, fraud, label, and case world by separating gate authority, arrival attachment, legitimate baseline synthesis, fraud overlay, supervision truth, and final read legitimacy into distinct owned truths.

State by state, the actual design reads like this.

`S0 - gate and sealed inputs`

`S0` is not setup noise. It is what makes the rest of `6B` lawful.

It freezes:

- the Layer-1 and Layer-2 PASS world from `1A` through `5B`
- the Layer-3 entity world from `6A`
- the exact upstream bundle references `6B` is allowed to depend on
- the behavioural contracts, RNG laws, label laws, and validation laws that all later `6B` states must inherit

The important implemented shift is that `S0` became a strict schema-and-config repair gate rather than a thin prerequisite checker. The implementation notes show that the segment could not even open honestly until contract shapes and bundle expectations were stabilized. But the actual design still kept `S0` lean:

- it verifies gates and sealed references
- it does not become a data-plane scan state
- it exists to define the lawful behavioural world for the rest of the segment

So `S0` is the lawful world-definition authority of `6B`.

`S1 - arrival attachment and session authority`

`S1` owns the first real behavioural question:

- which entity world does each arrival belong to?
- and which session does that arrival live inside?

That makes it more than a join step. Every later state depends on it:

- `S2` builds legitimate flows and events from these attached arrivals
- `S3` overlays fraud onto that same behavioural base
- `S4` later labels and cases the resulting flow world

The actual implemented posture matters because `S1` was deliberately repinned away from the heavier spec shape. The implemented design chose a lean deterministic attachment and sessionisation rail:

- vectorized attachment instead of expensive per-row scoring
- no stochastic session-boundary machinery
- home-country bias only when both sides exist
- merchant-linked device and IP preferred for POS and ATM, with party-linked fallback when needed

So `S1` is the attachment and session authority of `6B`, and a deliberately simplified but still authoritative one.

`S2 - baseline legitimate behavioural authority`

`S2` takes the attached arrival and session world from `S1` and turns it into a baseline legitimate flow and event world.

It owns:

- how arrivals become flows
- how flows expand into event sequences
- how amounts and timings behave before any fraud semantics exist
- the legitimate baseline that later states must inherit

This is one of the most important states in the segment because the remediation trail made it a main owner lane. The build plan explicitly puts amount realism and timing realism on `S2`, which means the implemented design is much stronger than “generate some flows.” The actual design became:

- controlled baseline generation with explicit RNG evidence
- latent or intensity-shaped behavioural structure
- fraud-free baseline semantics by construction

So `S2` is the legitimate behavioural authority of `6B`.

`S3 - fraud overlay and campaign authority`

`S3` takes the baseline world from `S2` and turns it into a fraud-bearing world.

It owns:

- which campaigns exist
- which flows or events are targeted
- how abuse overlays are applied
- how campaign provenance remains readable

The important recovered design point is what `S3` does not do.

It does not:

- mutate `S2` in place
- erase the distinction between legitimate baseline and fraud overlay
- own final supervision truth

Instead, it stays narrow and authoritative. The build plan made campaign multiplicity and targeting depth explicit owner burdens, so `S3` became a real realism lane rather than a cosmetic fraud-tagging step.

So `S3` is the campaign and fraud-overlay authority of `6B`.

`S4 - supervision and case authority`

`S4` is where the behavioural world becomes supervision-ready.

It reads:

- the overlaid flow and event world from `S3`
- campaign provenance
- label, delay, and case policies

and turns that into:

- truth labels
- bank-view labels
- event labels
- case timelines

This is the most important downstream authority surface in the segment because the build plan made `S4` the owner of:

- truth-label correctness
- bank-view stratification
- case-timeline validity

That means `S4` is not a downstream report layer. It is the sole place where the engine decides:

- what actually happened
- what the bank would have seen
- what case chronology exists downstream

So `S4` is the supervision-truth and case authority of `6B`.

`S5 - final behavioural legitimacy authority`

`S5` is where the whole behavioural world is judged.

It reads:

- the sealed world from `S0`
- the attachment and session world from `S1`
- the baseline world from `S2`
- the fraud-overlay world from `S3`
- the label and case world from `S4`
- the RNG evidence and audit traces emitted across the segment

and then does two things:

- validates that the behavioural world is structurally and semantically lawful
- decides whether the whole `6B` segment deserves a PASS gate

The important thing is that `S5` stayed much stronger than a receipt state. In the remediation plan it became the fail-closed realism gate for the entire segment. That means `S5` does not repair weak worlds after the fact. It judges them and either certifies them or refuses them.

So `S5` is both the final validation authority and the final consumer-legitimacy boundary of `6B`.

The shortest honest synthesis of the whole segment is this:

`6B` is the Layer-3 segment that turns a sealed arrival and entity world into a certified behavioural, fraud, label, and case world by separating attachment truth, legitimate baseline truth, campaign-overlay truth, supervision truth, and final read legitimacy into distinct owned authorities.

That is why the segment matters architecturally.

It is not merely “simulate behaviour after entities.”

It is the place where the engine proves that it can:

- turn arrivals into an entity-bound behavioural world
- keep legitimate baseline behaviour separate from fraud overlay
- keep fraud overlay separate from truth and bank-view labels
- keep labels separate from case chronology
- and still reunify those surfaces into one downstream-readable behavioural world

The final implemented posture matters too.

`6B` did not stay at a weak realism posture. It was explicitly routed through owner-state remediation:

- `S1` closed the attachment and session realism boundary in a lean deterministic way
- `S2` closed the legitimate amount and timing realism burden
- `S3` closed fraud campaign and targeting depth
- `S4` closed truth-label, bank-view, and case realism
- `S5` closed fail-closed certification and consumer legitimacy

That tells you what the actual design became:

- `S0` is the strict behavioural-world gate
- `S1` is the arrival-attachment and session authority
- `S2` is the baseline legitimate flow and event authority
- `S3` is the fraud-overlay and campaign authority
- `S4` is the supervision and case authority
- `S5` is the final PASS authority

That is the actual state design of `6B` as implemented.
