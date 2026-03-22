Segment `6A` state synthesis

`6A` is the Layer-3 entity-and-static-risk segment that turns the sealed merchant, traffic, and arrival world from Layers 1 and 2 into a closed bank-like entity world.

Its actual implemented design is not just:

- create customers
- give them accounts and devices
- then assign some fraud labels

It is a tighter Layer-3 authority corridor that does six things in order:

1. seals the exact upstream world, contracts, priors, and policies that Layer-3 may depend on
2. realises the customer and party universe for that world
3. turns that party universe into an account and product world
4. turns the account world into payment credentials and instrument links
5. turns the entity world into a device/IP network graph
6. assigns static fraud posture and decides whether the entire segment deserves to be consumed at all

That makes `6A` less like a synthetic data convenience layer and more like a staged entity-world authority:

- `S0` seals the world
- `S1` defines who exists
- `S2` defines what products they hold
- `S3` defines what credentials and payment handles exist
- `S4` defines how the network graph is wired
- `S5` defines static fraud posture and final segment legitimacy

The important part of the recovery is that the actual implemented design is heavily shaped by remediation ownership.

The build plan and implementation notes show that `6A` was not merely implemented and left alone. It was re-asked around a clear owner-state structure:

- `S2` owned hard account-cap realism
- `S4` owned device/IP realism
- `S5` owned risk-propagation realism and final segment closure
- `S1` and `S3` remained important authority surfaces, but they were not the main recovery lanes

So the right synthesis for `6A` is this:

`6A` is the segment that turns a sealed upstream merchant and traffic world into a certified entity, product, graph, and static-risk world by separating gate authority, party creation, account/product creation, instrument creation, graph construction, and fraud-posture closure into distinct owned truths.

State by state, the actual design reads like this.

`S0 - gate and sealed inputs`

`S0` is not setup noise. It is what makes the rest of `6A` lawful.

It freezes:

- the Layer-1 and Layer-2 PASS world from `1A` through `5B`
- the exact upstream data surfaces that 6A is allowed to depend on
- the Layer-3 priors, taxonomies, linkage rules, and validation policies
- the sealed inventory that all later 6A states are forced to inherit

The important implemented shift is that `S0` became a strict Layer-3 multi-law gate rather than a thin contract reader. It had to understand all upstream bundle forms while still keeping control-plane work lightweight enough for a real segment gate. That produced a real design boundary:

- contracts and priors are content-validated and hashed
- very large upstream row-level surfaces are structurally sealed so S0 stays metadata-oriented

So `S0` is the lawful world-definition authority of `6A`, not a preamble.

`S1 - party-base authority`

`S1` owns the first real Layer-3 question:

- who exists in the synthetic bank world?
- and how are those parties statically segmented?

That makes it more than a population sampler. Every later 6A state depends on it:

- `S2` allocates products to these parties
- `S3` attaches credentials to their accounts
- `S4` wires devices and IPs to their graph
- `S5` assigns static fraud posture over this same entity world

The actual implemented posture matters because `S1` adopted a lean but still authoritative execution shape:

- aggregated RNG evidence instead of unrealistic per-party traces
- deterministic region mapping when no sealed country-to-region taxonomy existed
- streaming summaries instead of re-reading the whole world for reporting

So `S1` is the party-universe authority of `6A`.

`S2 - account and product authority`

`S2` takes the party world from `S1` and turns it into a bank-product world.

It owns:

- which accounts and products exist
- how many exist per type and cell
- who owns them
- the static account world later states must inherit

This is one of the most important states in the segment because the remediation trail made it the first main owner lane. The crucial implemented change is that `S2` stopped treating account-cap violations as something to observe or warn about. Hard global post-merge `K_max` enforcement became part of the actual design. That means account realism is no longer “usually capped.” It is:

- deterministically capped
- explicitly redistributed when possible
- explicitly dropped and counted when not
- fail-closed if violations remain

So `S2` is the account and product authority of `6A`, and the first major hard-invariant realism surface.

`S3 - instrument and credential authority`

`S3` takes the account world from `S2` and turns it into the credential world:

- cards
- bank-transfer handles
- wallets
- other static payment credentials

The important thing about the recovered design is what `S3` does not do.

It does not:

- reopen account realism
- own network-graph realism
- own static fraud posture

Instead, it stays narrower. It creates the credential layer that later graph and fraud states depend on, but it is not the main recovery lane. That is an important actual-design reading because it keeps the segment’s ownership map clean:

- `S2` owns product cardinality realism
- `S3` owns credential existence and attachment
- later states consume that credential truth rather than inventing alternatives

So `S3` is the instrument and credential authority of `6A`.

`S4 - device/IP graph authority`

`S4` is where `6A` becomes visibly network-shaped.

It takes:

- parties from `S1`
- accounts from `S2`
- instruments from `S3`

and turns them into:

- device identities
- IP identities
- static graph links across the entity world

This is where the implemented design diverged most strongly from a naive “sample some devices and IPs” reading.

The remediation program made `S4` the owner surface for:

- IP prior alignment
- device/IP linkage coverage
- bounded devices-per-IP tail behaviour

That means the graph is not accepted because some links exist. It is accepted because the implemented design removed permissive shortcuts, added deterministic coverage control, and enforced sharing bounds so graph realism is achieved by construction.

So `S4` is the device/IP and graph authority of `6A`.

`S5 - static fraud posture and final gate authority`

`S5` is where the whole Layer-3 entity world is judged and labelled.

It reads:

- the sealed world from `S0`
- the party world from `S1`
- the account/product world from `S2`
- the credential world from `S3`
- the device/IP graph world from `S4`

and then does two things:

- assigns static fraud posture over those entities
- decides whether the whole 6A world deserves a PASS gate

The important thing is that `S5` stayed much stronger than a receipt state. In the remediation plan it became an owner lane for risk propagation and role-family traceability. That means static fraud posture is not decorative metadata. It is part of the segment’s realism burden, and `S5` is where that burden is judged and sealed.

So `S5` is both the static fraud-posture authority and the final consumer-legitimacy boundary of `6A`.

The shortest honest synthesis of the whole segment is this:

`6A` is the Layer-3 segment that turns a sealed merchant and traffic world into a certified entity, product, graph, and static-risk world by separating party creation, product creation, credential creation, graph creation, fraud posture, and final read legitimacy into distinct owned truths.

That is why the segment matters architecturally.

It is not merely “bank entities after arrivals.”

It is the place where the engine proves that it can:

- turn upstream merchant and traffic truth into a coherent party universe
- keep account/product reality separate from credential reality
- keep credential reality separate from graph wiring
- keep graph wiring separate from static fraud posture
- and still reunify those surfaces into one downstream-readable entity world

The final implemented posture matters too.

`6A` did not stay at a weak `B-` posture. It was explicitly routed through owner-state remediation:

- `S2` closed hard account-cap invariants
- `S4` closed the main device/IP realism burdens
- `S5` closed risk-propagation realism and final segment closure

That tells you what the actual design became:

- `S0` is the strict Layer-3 world-definition rail
- `S1` is the party-universe authority
- `S2` is the hard account/product realism surface
- `S3` is the credential-extension authority
- `S4` is the network-realism authority
- `S5` is the static fraud and final PASS authority

That is the actual state design of `6A` as implemented.
