# A Production Wiring Notes

## 2026-03-12 04:28:14 +00:00 - Reset the A-notebook around the interrogation method so the notes stay path-led, bounded, and systems-design oriented
The earlier note trail was useful for getting the initial framing straight, but it mixed exploratory discussion with the actual interrogation method. That is no longer the right posture for this notebook.

From this point forward, the notebook is reset around the flow plan captured in:

- [prod-wired.interrogation-approach.mmd](assets/prod-wired.interrogation-approach.mmd)
- [prod-wired.interrogation-approach.png](assets/prod-wired.interrogation-approach.png)

This flow plan is the working method for `A`.

It means the notebook should no longer drift into broad architecture commentary or a dressed-up component tour. The path from here is:

1. pin the boundary of `A`
2. freeze the evidence surfaces
3. derive obligation-led path groups
4. enumerate only real paths
5. interrogate each path through purpose, route, materialization, contract pressure, trade-offs, and necessity
6. extract claims
7. qualify the why and quantify the closure
8. keep `A` ambiguities and `Bi` pressure thoughts separated
9. synthesize only after the paths have earned their place in the argument

The practical consequence for the notes is that each future entry should serve the interrogation flow rather than bypass it. If an entry does not help establish:

- purpose
- necessity
- materialization
- contract obedience
- trade-off awareness
- or closure quality

then it probably does not belong in this notebook.

Judgment at this point:

- the `A` notebook is now reset onto a cleaner method
- the flow plan is the controlling interrogation frame for subsequent notes
- the next entry should begin the actual interrogation of the first group under that method: the Foundational Control path

## 2026-03-12 04:34:04 +00:00 - Pin the obligation inventory for A at the right level: above paths, below the meta-goal, and free from component naming
The first real interrogation step after resetting the notebook is to pin the obligation inventory for `A`.

The important boundary here is that obligations are not components and they are not yet the end-to-end path catalogue. They sit one level above paths. They answer:

- what must this platform be able to do, as a wired system, for it to count as a serious platform foundation at all?

That means the obligation inventory should not be written in cloud product names, and it should also not be reduced to proving concerns that belong more naturally to `Bi` or `Bii`. The point here is to pin the minimum obligation families that make the current wired `dev_full` platform a meaningful engineered system rather than a random graph.

The pinned obligation inventory for `A` is:

1. `Run authority and source-of-stream seating`
   - the platform must be able to establish a bounded run, bind that run to authoritative identity/correlation, and seat the upstream world correctly through a governed source-of-stream boundary rather than through ambiguous compute side effects

2. `Controlled admission of canonical traffic`
   - the platform must be able to admit only the correct engine outputs as traffic, apply canonical ingress rules, deduplicate/admit/quarantine appropriately, and publish admitted traffic into the platform transport network

3. `Runtime understanding and decisioning`
   - the platform must be able to turn admitted thin traffic into usable runtime context, features, and decisions by joining on platform-owned time-safe surfaces without future leakage

4. `Durable runtime audit and archive truth`
   - the platform must be able to append and preserve decision, action, lineage, and archive truth so runtime behavior is reconstructable rather than transient

5. `Operational case and label truth`
   - the platform must be able to turn relevant runtime outcomes into operational review truth: case-worthy signals, append-only case timelines, and authoritative label truth with clear ownership boundaries

6. `Learning, evaluation, and governed activation`
   - the platform must be able to turn runtime/archive truth and label truth into governed learning inputs, train/eval outputs, and explicit activation authority for runtime bundles

7. `Run governance and observability closure`
   - the platform must be able to emit run-scoped correlation, receipts, governance facts, and durable evidence so the run can later be reconstructed, diagnosed, and governed

These seven obligations are the right size for `A` because they are:

- higher than paths
- lower than the meta-goal
- wide enough to cover the whole current platform
- disciplined by contracts, truth boundaries, time-safety laws, and control laws rather than by implementation cosmetics

One thing that needs to stay explicit here is the hierarchy:

- obligations are the major things the wired system must be able to do
- paths are the end-to-end routes by which those obligations are realized
- components and resources are the concrete seats of those paths

That is why the path catalogue itself is not the obligation inventory. The path catalogue will come next, but only after the obligations are pinned. Otherwise the interrogation starts one layer too low and drifts back toward a component or flow tour.

This obligation inventory also fits the external data-engine and platform contracts more cleanly than a simpler "ingest / score / train" shape would. The platform is required to distinguish traffic from context from truth from evidence, to perform joins inside the platform, to respect time-safety laws, and to preserve clean truth ownership boundaries. Those obligations therefore need to appear directly in the inventory rather than being hidden under vague lifecycle labels.

Judgment at this point:

- the obligation inventory is now pinned at a level that is meaningful for `A`
- the interrogation can now move from obligation families down into path groups and then into real paths
- the next useful move is to derive the functional path groups under these obligations rather than jumping straight to components or proving questions

## 2026-03-12 04:50:42 +00:00 - First pass at the functional path groups: define the obligation-led group structure before deriving real paths
With the obligation inventory pinned, the next move is to define the functional path groups. These groups should still stay above paths and well above components. Their purpose is to organize the interrogation around major system obligations without collapsing back into plane buckets or cloud-product names.

The current first-pass group set is:

1. `Run and world-source authority`
   - this group covers how a run becomes legitimate at all: world identity, source-of-stream seating, run-state control, and authoritative activation / READY closure

2. `Canonical traffic admission and bus publication`
   - this group covers how valid traffic enters platform runtime: ingress, idempotency, quarantine/reject logic, and publication to the platform bus

3. `Runtime context formation and decisioning`
   - this is the core understand-and-decide group: thin-traffic join posture, RTDL-safe context formation, feature/context preparation, and decision/action routing

4. `Durable audit, archive, and replay truth`
   - this group covers append-only lineage, audit truth, archive persistence, and replay basis so runtime behavior is reconstructable after the fact

5. `Case and label operational truth`
   - this group covers how runtime outputs become operational review truth: case-worthy signals, case state evolution, and authoritative label truth

6. `Learning, evaluation, and governed activation`
   - this group covers the runtime-to-offline learning loop and the governed return to runtime authority: OFS dataset build, MF train/eval, and MPR promotion / rollback / active-bundle authority

7. `Run governance, observability, and evidence closure`
   - this group covers the meta obligation that makes the rest defensible: cross-runtime correlation, run-scoped evidence, blocker/verdict logic, cost-to-outcome, and final closure

The reason these groups are currently preferred is that they:

- align with the full platform lifecycle already latent in the docs
- preserve obligation-led thinking instead of component naming
- respect the contract distinction between traffic, context, truth, evidence, and telemetry
- stay in `A` by asking what the wired system must be able to do, not yet whether it survives production pressure

Just as importantly, this grouping avoids two common failures:

- reducing the platform to realization buckets such as `API Gateway`, `MSK`, `Flink`, `Aurora`, `CM`, or `SageMaker`
- collapsing audit/archive into generic governance, even though append-only audit and replay truth are first-class design concerns in this system

The current intended interrogation order is:

1. `Run and world-source authority`
2. `Canonical traffic admission and bus publication`
3. `Runtime context formation and decisioning`
4. `Durable audit, archive, and replay truth`
5. `Case and label operational truth`
6. `Learning, evaluation, and governed activation`
7. `Run governance, observability, and evidence closure`

This order follows the actual platform lifecycle while still keeping the meta layers visible.

Judgment at this point:

- the first-pass functional group structure is now pinned
- it is strong enough to begin downstream path derivation
- but the group stage is not yet fully closed until each group also has explicit inputs/outputs, governing laws, and broad design choice pinned

## 2026-03-12 04:52:47 +00:00 - Close the functional group stage by pinning obligation, necessity, inputs, outputs, and broad design idea for each group
The group stage is now closed by pinning the five things each functional group needed:

- obligation satisfied
- why it must exist
- what enters
- what exits
- the broad design idea

The pinned functional path groups for `A` are now:

1. `Run and world-source authority`
   - obligation:
     - establish a legitimate run and a legitimate source-of-stream basis for the whole platform
   - why it must exist:
     - `dev_full` is pinned as full-lifecycle, managed-first, no-laptop, with single active runtime path per phase/run, Step Functions as control authority, and Oracle Store as a read-only external source-of-stream boundary
   - inputs:
     - run identity and config (`platform_run_id`, `scenario_run_id`, config digest), Oracle/source references, and engine identity tokens such as `manifest_fingerprint`, `parameter_hash`, `seed`, and `scenario_id`
   - outputs:
     - committed run header / config basis, authoritative control / READY closure, and a bounded source basis that downstream groups can trust
   - broad design idea:
     - the system starts from explicit run legitimacy and source legitimacy, not from ad hoc compute effects or implicit state

2. `Canonical traffic admission and bus publication`
   - obligation:
     - accept only the right traffic, under the right rules, and publish it into authoritative platform transport surfaces
   - why it must exist:
     - the engine contract distinguishes canonical traffic from join surfaces, truth products, audit evidence, and telemetry, while the platform authority pins a concrete ingress edge, idempotency boundary, quarantine posture, and Kafka topic truth
   - inputs:
     - canonical behavioural streams plus ingress envelope / auth / dedupe context
   - outputs:
     - admitted traffic, reject / quarantine truth, offset or receipt truth, and authoritative publication onto the platform bus and context topics
   - broad design idea:
     - thin traffic is canonicalized at ingress, and admission truth is durable before downstream runtime consumes anything

3. `Runtime context formation and decisioning`
   - obligation:
     - turn admitted thin traffic into decisionable runtime truth
   - why it must exist:
     - the engine contract explicitly says traffic stays thin, joins happen inside the platform, and only time-safe context may be used for live decisions; the authority then seats stream-native projections and joins in the RTDL plane with Redis / Aurora / custom ownership logic where required
   - inputs:
     - admitted behavioural streams, RTDL-safe context surfaces, active bundle / policy identity, and low-latency state or cache where needed
   - outputs:
     - context / feature readiness, decisions, actions, and decision-linked runtime truth
   - broad design idea:
     - understanding is constructed inside the platform, not smuggled in from a fat event payload or from future-derived truth

4. `Durable audit, archive, and replay truth`
   - obligation:
     - make runtime behavior reconstructable, replayable, and defensible after the fact
   - why it must exist:
     - append-only truth, origin-offset evidence boundaries, durable evidence refs, archive truth, and replay basis are pinned laws rather than optional reporting conveniences
   - inputs:
     - decision, action, lineage, and runtime events from the hot path
   - outputs:
     - append-only audit truth, archive refs / immutable history, replay-usable truth surfaces, and durable evidence roots
   - broad design idea:
     - the platform does not merely decide; it turns decisions into authoritative historical truth that later audit, replay, learning, and governance can rely on

5. `Case and label operational truth`
   - obligation:
     - turn the right runtime outcomes into operational review truth and supervised truth
   - why it must exist:
     - the platform is not only a scorer; it also owns case-worthy escalation, case timelines, and authoritative labels with explicit writer boundaries and append-only behavior
   - inputs:
     - decision and audit outputs that are eligible to create operational work or supervision truth
   - outputs:
     - case triggers, case timeline truth, label commits, and label events for later readback and downstream use
   - broad design idea:
     - operational supervision is a first-class truth system, not an afterthought hanging off the side of decisioning

6. `Learning, evaluation, and governed activation`
   - obligation:
     - convert replayable runtime truth plus label truth into governed datasets, train/eval outputs, and active runtime authority
   - why it must exist:
     - `dev_full` is explicitly full-platform, not runtime-only, and the authority pins OFS, MF, and MPR with causal replay / as-of / maturity controls, Iceberg dataset identity, and explicit promotion / rollback governance
   - inputs:
     - archive/runtime truth, authoritative labels, replay basis, `feature_asof_utc`, `label_asof_utc`, maturity controls, and governed config / lineage identities
   - outputs:
     - dataset manifests and fingerprints, train/eval artifacts, candidate bundles, promotion / rollback events, and active bundle truth consumable by runtime
   - broad design idea:
     - learning is causal, governed, and lineage-bound, and activation is explicit rather than a shadow side effect

7. `Run governance, observability, and evidence closure`
   - obligation:
     - make the whole run diagnosable, governable, and closable as one platform story
   - why it must exist:
     - `dev_full` pins OTel-first cross-runtime correlation, run-scoped evidence bundles, cost-to-outcome receipts, blocker-free closure, final verdict publication, and idle-safe teardown as hard operating law
   - inputs:
     - lane-level telemetry, required correlation fields, proof artifacts, governance events, and cost posture artifacts from the other groups
   - outputs:
     - run bundles, non-regression packs, final verdicts, cost-to-outcome receipts, teardown / idle-safe evidence, and the exact story of what happened and why
   - broad design idea:
     - the platform is not judged by vague success; it is closed through explicit evidence and governance truth

At this point the group stage is complete enough for the interrogation flow:

- the obligation inventory is bounded
- the functional path groups are derived from it
- and each group now carries obligation, necessity, inputs, outputs, and broad design idea

Judgment at this point:

- the group stage is now closed
- the next step is to define what counts as a real path against these groups
- path enumeration should now start with Group 1: `Run and world-source authority`

## 2026-03-12 05:10:08 +00:00 - Pinning what counts as a real path for `A` before touching Group 1 enumeration

Before splitting Group 1 into candidate routes, I needed to pin what a "real path" actually means in this notebook. If I do not make that explicit first, then any visible route in the network can start pretending to be a path, and the interrogation loses its boundary immediately.

A real path for `A` is not just any visible route in the graph. It is a group-owned, end-to-end route in the current wired platform that satisfies all of these:

1. It has a clear entry surface.
2. It has a clear job tied to one obligation group.
3. It has a clear owned outcome:
   - a commit surface,
   - an authoritative publication,
   - or a handoff boundary to the next group.
4. It is interrogated against the current authoritative wired route for that obligation, not against a mixture of authoritative, fallback, and hypothetical routes.
5. It obeys the platform's binding laws:
   - traffic vs context vs truth vs evidence separation,
   - thin-traffic join posture,
   - no-future-leakage,
   - gate-before-read,
   - deterministic identity and correlation.
6. It is materially seated in concrete runtime and resource surfaces, not only described abstractly.
7. It passes a necessity test:
   remove it, and some platform obligation becomes impossible, unsafe, or unjustified.

The boundary rule I want to keep hard is this:

- a real path for `A` should usually end at the first authoritative group-owned outcome or handoff boundary
- it should not run across the whole platform as one giant chain

That boundary matters because I want each path to stay owned by one obligation group. The path should stop where the group has done its job and either committed truth or handed off to the next group.

The exclusion rule is equally important:

- if a candidate route does not have a clear entry, clear job, clear owned outcome, governing-law coherence, material seating, and necessity, then it is not yet a real path for `A`
- it belongs either in the `A` ambiguity register or should be treated as a helper surface, fallback, or component adjacency rather than as a real path

This gives me the right gate before Group 1 enumeration. I now have a bounded test for deciding whether something is a real path, a helper surface, or an unresolved ambiguity.

## 2026-03-12 05:30:32 +00:00 - Splitting Group 1 `Run and world-source authority` into its real paths

After tightening Group 1 against the authority, run-process, handles, implementation-note, and interface surfaces, I think Group 1 should be split into 3 real paths, not 2.

The reason is that Group 1 contains three distinct authoritative outcomes:

- run-boundary legitimacy
- source-of-stream / oracle realization legitimacy
- READY authority legitimacy

Those are different owned closures, so they should not be collapsed into one giant "run-to-ready" path.

In the reader-facing notebook I want the path names to stay self-describing rather than repo-dependent. So I will keep the Group 1 path set as:

- `Run legitimization path`
- `Source realization path`
- `Ready authorization path`

I want the path breakdown itself to stay inside this single entry:

1. `Run legitimization path`
   - entry:
     - operator intent arrives with `platform_run_id`, `scenario_run_id`, and config payload
   - job:
     - legitimize the run as a bounded execution, commit the run header once, and bind the run to an auditable config basis
   - owned outcome:
     - a committed run header plus committed config digest under the run evidence root; this is the first authoritative closure point for the whole platform
   - why it is a real path:
     - it has a clear entry, a clear job, and a clear owned outcome that belongs to Group 1
     - it is not just "setup"; it is the path that makes the rest of the platform legally and semantically one run rather than loose activity
     - the run-process pins run-header and config-digest commitment as closure evidence
     - the authority also requires run config digests to be emitted and validated across runtime and learning lanes
     - the engine interface gives the broader identity world this run sits inside: `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`, and `run_id`

2. `Source realization path`
   - entry:
     - a pinned external oracle source namespace and engine run identity, with the platform treating Oracle as a read-only producer-owned source world
   - job:
     - seat that world as the platform's authoritative source-of-stream basis and realize the usable source surfaces through the pinned oracle inlet contract
   - owned outcome:
     - canonical oracle-store basis plus managed-sort-derived `stream_view` / `truth_view` surfaces, manifests, receipts, and parity/readability evidence
   - why it is a real path:
     - this is not just "some data exists somewhere"
     - it is the path that makes the source world usable to the platform in a governed way
     - the authority explicitly says Oracle Store is a warm source-of-stream zone under the `oracle-store/` boundary, separate from archive and evidence, and that platform access is read-only while the producer remains write owner
     - the handles registry pins the inlet mode as `external_raw_upload_then_managed_sort`, requires managed distributed sort, forbids local execution, and requires sort receipt plus parity checks
     - the implementation notes reinforce that the active standard is now `raw -> managed sort -> parity`, precisely to remove copy-based ambiguity and keep the source boundary honest

3. `Ready authorization path`
   - entry:
     - a run that is already pinned, with source roots and source-realization prerequisites satisfied
   - job:
     - turn the run from pinned and source-legitimate into authoritatively ready through the control plane
   - owned outcome:
     - READY emitted to the control topic and READY receipt committed with a Step Functions execution reference, with duplicate or ambiguous READY prevented
   - why it is a real path:
     - READY is not just a byproduct of compute; it is its own authority closure
     - the authority explicitly says SR/WSP compute may run, but READY/control remains Kafka-backed and Step-Functions-controlled, and READY closure authority is Step Functions commit evidence
     - the implementation notes show this was a deliberate repin: Flink-only closure was rejected in favor of Step Functions-only commit authority
     - the run-process then makes that concrete by requiring READY receipt commitment with a Step Functions execution reference and explicitly rejecting compute-only closure as sufficient

What does not count as its own real path in Group 1:

A few things are visible in the docs but should not be treated as separate real paths here.

- A direct "Flink says READY, therefore we are ready" route is not a real path, because the owned outcome is invalid under the pinned authority. READY only closes when Step Functions commits it.
- A copy-oracle-locally or read-from-platform-owned-copy route is not a real path, because the source-of-stream contract forbids that as the active standard. The platform is read-only against the canonical source boundary, and the active inlet is external raw upload followed by managed sort.
- A mid-phase runtime-switch route is not a real path, because single active path per phase/run is pinned as law. Group 1 paths have to be interrogated against the current authoritative route, not a blended active-plus-fallback fantasy route.

So Group 1 is now pinned as:

- `Run legitimization path`
- `Source realization path`
- `Ready authorization path`

That is now a clean split. The next honest move is to take `Run legitimization path` and do the full path-level interrogation on it: entry, outcome, carried objects, route logic, concrete seating, design reasoning, constraints, and necessity.

## 2026-03-12 05:40:56 +00:00 - Path interrogation: `Run legitimization path`

This path exists to turn "I want to run the platform" into "this is now one bounded, auditable, authoritative run." In the run-process, that is the first real closure point of the platform. Before daemons are judged healthy, before oracle is judged ready, before ingress is judged ready, the run must already be pinned as a specific run with a specific config basis.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn operator intent into one bounded, auditable, authoritative run
   - make run legitimacy the first real closure point of the platform rather than a side effect discovered later
   - make later phases hang off a known run basis instead of inventing local run scope for themselves

2. entry:
   - the entry is operator intent plus explicit identity and config, not "runtime started doing things"
   - the operator sequence requires `platform_run_id`, `scenario_run_id`, and config payload
   - execution is also blocked if required handle classes are unresolved, so run legitimization begins from an explicit control contract rather than from best-effort runtime discovery

3. owned outcome:
   - the owned outcome is a committed run basis
   - more concretely, the pass condition is: run header committed once, `run_config_digest` committed, and phase evidence root exists
   - the evidence seating is also pinned rather than improvised at runtime:
     - `evidence/runs/{platform_run_id}/`
     - `evidence/runs/{platform_run_id}/run.json`
     - `evidence/runs/{platform_run_id}/run_pin/run_header.json`
   - that makes the outcome both semantic and material

4. what the path carries:
   - `platform_run_id`
   - `scenario_run_id`
   - config payload
   - derived `run_config_digest`
   - run evidence references
   - the implementation notes make clear that `platform_run_id` is intentionally explicit and auditable, while `scenario_run_id` is deterministic rather than random, derived from a scenario-equivalence seed tied to oracle/source handles and canonicalization rules
   - the same notes also make clear that config digest is not decorative; it is part of the authoritative run basis and is recomputed and matched against the seeded scenario-equivalence contract

5. broad route logic:
   - operator intent -> control-plane entry -> run identity lock -> config digest validation and commit -> durable run evidence surfaces
   - this is a control-plane path, not a data-plane path
   - the run-process pins the run-pinned phase to Step Functions run-state entry, and the implementation notes later pin run-lock identity on Step Functions execution posture rather than inventing a separate ad hoc lock authority
   - the path is therefore not "a service happened to start and therefore the run exists"; it is "the control plane authorized and materialized the run basis, therefore later phases can legitimately exist"

6. logical design reading:
   - logically, this path says the platform treats run legitimacy as a first-class concern
   - the system does not jump from "up" to "streaming" or "ready"
   - it forces a pinned run basis first, with explicit pass gates and durable evidence
   - the rest of the platform is therefore supposed to hang off a known run, not invent its own local sense of run scope later

7. concrete seating in the current wired system:
   - the control authority is Step Functions
   - the runbook names Step Functions as the primary runtime for the run-pinned phase
   - the broader design authority places Step Functions in the platform orchestration layer rather than treating orchestration as shell glue
   - the evidence seating is S3, with pinned run-level prefixes and pinned run-pin artifact locations in the handles registry
   - this path is therefore not conceptual only; it has a concrete control-plane runtime and concrete durable evidence surfaces

8. why the design looks like this:
   - the implementation notes show that config digest is deliberately committed because otherwise replay provenance becomes ambiguous; digest-changing edits are supposed to force a new `platform_run_id`, not silently mutate the meaning of the existing run
   - the digest is computed from a canonical payload and checked deterministically, precisely to stop drift between "what this run claims to be" and "what it actually binds to"
   - run-lock identity was deliberately pinned on orchestrator execution posture instead of inventing a separate lock subsystem, because that preserves a single control authority and avoids authority churn

9. external contract pressure shaping this path:
   - the data-engine interface reinforces why this path has to be careful about identity
   - the engine contract distinguishes sealed-world identity (`manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`) from execution correlation (`run_id`)
   - it also explicitly says that run-scoped logging correlation must not mutate the bytes of world outputs whose identity does not include the run
   - read another way, that pushes the platform toward a run-legitimization posture where run identity is about execution scope, control, and evidence, not about pretending the run itself creates a new source world
   - the same contract also reinforces immutability and gate-before-read discipline, which fits the "commit once, then treat as authoritative" posture of run pinning

10. trade-offs and constraints:
   - this path deliberately adds friction
   - you do not get to "just run it"
   - you need explicit IDs, explicit config, explicit evidence roots, and explicit handle closure before the run can even start
   - that is slower and more ceremony-heavy than a looser setup, but it buys auditability, replay provenance, and scope discipline
   - it also constrains later behavior: the runbook pins single active path per phase/run, prohibits in-phase switching, and treats identity/config drift as a reason to issue a new run rather than quietly mutate the old one

11. necessity test:
   - if this path is removed, the rest of the platform can still be drawn, but it stops being a serious engineered system
   - later phases would have no authoritative run basis to bind to, no stable config digest to explain what was actually run, no durable run-root to collect evidence under, and no clean way to distinguish a rerun from an identity mutation
   - in that world, daemons might still start and traffic might still flow, but the system would look accidental rather than governed
   - that is exactly the sort of weakness `A` is supposed to expose and reject

12. what this path proves for `A`:
   - purpose claim:
     - the platform explicitly treats run legitimacy as a required system job, not an operator habit
   - intentionality claim:
     - the basis of the run is established through the control plane, with Step Functions and durable evidence, rather than through accidental runtime side effects
   - materialization claim:
     - the evidence surfaces for the path are pinned in S3 path contracts
   - constraint-awareness claim:
     - config changes, lock semantics, and handle resolution are treated as hard boundaries, not optional hygiene
   - quantified closure claim:
     - one committed run header
     - one committed config digest
     - one run evidence root
     - zero ambiguity about run basis

Plainly stated, the `Run legitimization path` exists to make "this run" a real, governed object before the platform does anything else, and its current design shows that this is deliberate, materially seated, and provenance-aware.

The next clean move is the same treatment for the `Source realization path`.

## 2026-03-12 05:46:49 +00:00 - Path interrogation: `Source realization path`

This path exists to turn an external engine-owned world into a usable, governed source-of-stream basis for the platform. It is not just "put data in a bucket." It has to preserve the producer/platform ownership boundary, materialize the source world into the exact surfaces the platform is allowed to consume, and do so through a production-patterned route rather than a local shortcut.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn an external engine-owned world into a usable, governed source-of-stream basis for the platform
   - preserve the producer/platform ownership boundary while still materializing the source world into platform-readable surfaces
   - realize the source basis through a production-patterned route rather than a local shortcut

2. entry:
   - the entry is a declared external oracle source plus the handles needed to realize it
   - in the current pinned posture, that means a source namespace and engine run id under the oracle-store boundary, a raw input prefix that is declared and readable, and managed stream-sort handles that are resolved before closure can even be attempted
   - the implementation notes show this was deliberately repinned to `external_raw_upload_then_managed_sort`, with the canonical bucket moved to `fraud-platform-dev-full-object-store` and old dev-min copy remediation explicitly demoted to historical evidence rather than active standard

3. owned outcome:
   - the owned outcome is not merely "the platform can see some files"
   - the owned outcome is a canonical oracle basis with usable realized `stream_view` surfaces and proof that they are trustworthy
   - more concretely, that means:
     - raw upload receipt
     - managed stream-sort receipt
     - required outputs present
     - stream-view materialization checks passed
     - manifest and contract checks passed
     - canonical external source binding rather than an ad hoc duplicated copy
   - the run-process pins all of those as PASS requirements for oracle-source closure
   - the implementation notes and build-plan trail then sharpen the active standard further as `raw -> managed sort -> parity`
   - `truth_view` is also part of the current wired realization story, but the primary closure anchor of this path is the canonical oracle basis plus valid `stream_view` realization

4. what the path carries:
   - source identity:
     - oracle source namespace
     - oracle engine run id
     - the engine's sealed-world identity model such as `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`, and `run_id`
   - source materialization inputs:
     - raw uploaded oracle files under the oracle input prefix
   - realization outputs and proofs:
     - `stream_view` surfaces
     - manifests
     - stream-sort receipts
     - parity reports
     - required-output matrices
   - the handles registry makes the active required output set and sort-key map explicit, while the data-engine interface pins the identity and immutability rules the path must preserve

5. broad route logic:
   - external oracle world -> raw upload into oracle-store input boundary -> managed distributed sort -> realized source surfaces with receipts/manifests/parity -> platform-usable source basis
   - that broad route matters because it shows the platform is not meant to consume arbitrary engine files directly
   - it is also not meant to generate its own private copy-world informally
   - the current broad route is governed: external source world first, then an inlet contract, then managed realization, then explicit materialization proof
   - that is exactly why the implementation notes treat copy-based ambiguity as something to remove, not preserve

6. logical design reading:
   - logically, this path says the platform treats the engine world as a producer-owned external truth source and then creates a platform-readable realization layer from it
   - that is a very intentional design choice
   - it prevents two different kinds of drift:
     - the platform pretending it owns the oracle world
     - the platform consuming source data through informal, unreconciled, local transformations
   - the run-process and authority both pin the Oracle Store posture very clearly: warm source-of-stream zone in S3, platform read-only, producer write-owned, with source realization produced through managed distributed sort

7. concrete seating in the current wired system:
   - the oracle boundary is in S3 under `oracle-store/{oracle_source_namespace}/{oracle_engine_run_id}/input/`
   - the implementation notes explicitly repin the canonical bucket and input prefix
   - the realization step is materially seated in the managed sort lane, with the active contract requiring managed sort and forbidding local sort for the `dev_full` runtime path
   - the current realized outputs are also concrete, not abstract:
     - `stream_view/ts_utc/output_id=<output_id>/`
     - later `truth_view/ts_utc/output_id=<output_id>/` for truth-view preparation in the current wired system
   - the run-process then makes the expected closure artifacts concrete:
     - oracle readiness snapshot
     - required-output matrix

8. why the design looks like this:
   - the implementation notes make the reasoning very clear
   - this posture preserves the oracle ownership boundary: producer write-owned, platform read-only
   - it removes legacy copy-based ambiguity, which would otherwise blur what is canonical and what is merely a convenience mirror
   - it aligns with the production-pattern law and no-laptop-runtime posture, which is why local sort is forbidden and managed sort is required
   - it makes the oracle gate fail-closed on receipts and parity, rather than letting "looks readable" count as enough
   - those are architecture reasons, not performance excuses

9. external contract pressure shaping this path:
   - the data-engine interface is doing a lot of work here
   - it pins that world identity is defined by partition tokens and that outputs are immutable for a fixed identity
   - it distinguishes traffic from join surfaces, truth products, audit evidence, and ops telemetry
   - it also says "No PASS -> no read," meaning platform components must verify segment gates before treating gated outputs as authoritative
   - and it pins the platform join posture: traffic stays thin, joins happen inside the platform, and no future-leaking surfaces may be used for RTDL
   - that means the source realization path cannot be a vague "load everything and figure it out later" path; it has to produce the exact source surfaces the platform will later honor under those semantic rules

10. trade-offs and constraints:
   - this path deliberately chooses discipline over convenience
   - it is slower and more ceremony-heavy than an ad hoc local copy or local sort route, because it requires:
     - a declared oracle source boundary
     - raw upload receipt
     - managed sort receipt
     - manifest readability
     - required-output checks
     - parity checks
   - but that cost buys:
     - ownership clarity
     - source legitimacy
     - materialization legitimacy
     - replay and audit confidence
     - production-pattern alignment
   - the implementation notes also show the constraint side honestly: scheduler capacity issues, driver materialization timeout behavior, and later IAM/KMS permission issues surfaced in the managed sort lane and had to be handled at the IaC/runtime level rather than bypassed with manual shortcuts
   - that is useful context because it shows the design is not "managed sort because it sounds nice"; it is managed sort despite the friction, because that friction is part of the chosen production-shaped path

11. necessity test:
   - if this path is removed, the rest of the platform can still be described, but its source basis becomes muddy
   - without this path:
     - the platform loses a governed way to turn external engine truth into platform-usable source surfaces
     - the producer/platform ownership boundary becomes easy to violate
     - stream-view materialization loses its legitimacy
     - parity and manifest proof disappear
     - later runtime joins and learning surfaces rest on a weaker foundation
   - in plain terms, the platform would still have ingestion, decisioning, and learning boxes, but the source world they depend on would no longer be clearly realized or clearly justified
   - that would directly weaken `A`

12. what this path proves for `A`:
   - purpose claim:
     - the platform has a specific job for realizing the external source world, rather than hand-waving where source truth comes from
   - intentionality claim:
     - the route is explicitly external raw upload -> managed sort -> realized source surfaces, not accidental file placement
   - materialization claim:
     - the path is concretely seated in S3 oracle-store prefixes, managed sort runtime, and durable materialization/evidence outputs
   - contract claim:
     - the path preserves producer/platform ownership boundaries and the engine's identity, immutability, and gate laws
   - constraint-awareness claim:
     - copy-based ambiguity, local-sort convenience, and unmanaged shortcuts were explicitly rejected in favor of a stricter production-shaped route
   - quantified closure claim:
     - the authoritative repinned full-tree upload recorded `11,465` files and `92,622,942,077` bytes
     - later stream-view parity evidence was recorded for four required outputs with exact row parity matches
     - that is not `Bi`-style load proof; it is still `A`-relevant because it shows the path is materially realizing a non-trivial source world, not a toy sample

Plainly stated, the `Source realization path` exists to make the external engine world a governed, platform-usable source basis, and its current design shows that this is deliberate, materially seated, ownership-aware, and semantically constrained rather than informal.

The next clean move is the `Ready authorization path`.

## 2026-03-12 05:52:46 +00:00 - Path interrogation: `Ready authorization path`

This path exists to turn a run from "eligible to become ready" into "authoritatively declared ready." In the run-process, that is not a soft health signal; it is a formal closure point. Ready closure only happens when READY is emitted to the control topic, the READY receipt is committed, duplicate or ambiguous READY is prevented, and the commit authority is validated as Step Functions rather than Flink-only compute. The design authority says the same thing in broader architectural language: READY/control stays Kafka-backed, but closure authority stays with Step Functions.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn a run from eligible-to-become-ready into authoritatively declared ready
   - make readiness a formal closure point rather than a soft health signal
   - keep readiness under control-plane authority rather than letting compute alone close the gate

2. entry:
   - the entry is not "the stream lane looks healthy"
   - the entry is the narrower and more governed condition defined by the run-process:
     - SR joins and replay prerequisites already pass
     - the control-topic contract is already pinned
     - the required ready-closure handle set is resolved
     - the Step Functions authority surface resolves to a real active state machine
   - in executed prechecks, that meant validating run-continuity handoff, resolving the Step Functions handle chain, and confirming the control-topic anchors before READY publication was attempted

3. owned outcome:
   - the owned outcome is an authoritatively ready run, not merely a computed readiness hint
   - concretely, the pass condition is:
     - READY emitted to the control topic
     - READY receipt committed with a Step Functions execution reference
     - duplicate or ambiguous READY absent
     - authority proven to be Step Functions
   - in authoritative execution, that ended with a READY event on the control topic and a committed ready receipt under the run evidence root
   - later gate advance is downstream consequence, not the primary owned closure of this path

4. what the path carries:
   - run identity:
     - `platform_run_id`
     - `scenario_run_id`
   - run-scoped READY publication controls:
     - READY message filter
     - control-topic partitioning key
   - the READY signal itself
   - the Step Functions execution reference that makes the receipt authoritative
   - the broader run-process also pins the correlation contract around these kinds of transitions, requiring run-scoped identity continuity across orchestrator transitions and evidence emission

5. broad route logic:
   - SR prerequisites satisfied -> READY computed and published on the control bus -> Step Functions commits READY as control authority -> durable READY receipt becomes the authoritative proof
   - that broad route matters because it keeps compute and authority separate
   - Flink or other runtime surfaces may participate in producing the conditions for readiness, but the system is explicitly designed so that compute does not unilaterally close the gate
   - the control plane closes it

6. logical design reading:
   - logically, this path shows that the platform treats readiness as an authorization problem, not just a liveness problem
   - that is an important `A`-level design signal
   - the platform does not say "the lane emitted something, therefore we are ready"
   - it says "a run becomes ready only when the control plane, under the single-active-path law, records READY through the pinned authority"
   - that is exactly the kind of thing that makes the current wired system look governed rather than improvised

7. concrete seating in the current wired system:
  - the control surface is the Kafka control topic
   - the control-plane authority is the concrete Step Functions state machine `fraud-platform-dev-full-platform-run-v0`
   - the READY receipt lands in the run evidence surface under the run's S3 evidence root
   - the handle contract pins:
     - `READY_MESSAGE_FILTER = "platform_run_id=={platform_run_id}"`
     - `KAFKA_PARTITION_KEY_CONTROL = "platform_run_id"`
     - `SR_READY_COMMIT_RECEIPT_PATH_PATTERN = "evidence/runs/{platform_run_id}/sr/ready_commit_receipt.json"`
   - this is a very strong `A` signal because the path is not only conceptually designed; it is concretely realized

8. why the design looks like this:
   - the implementation notes make the design reasoning explicit
   - letting Flink-ready output implicitly close the ready gate was rejected
   - allowing dynamic runtime fallback mid-phase for convenience was rejected
   - both were rejected because they weaken deterministic gate closure, evidence attribution, and auditable control-plane ownership
   - so the current shape is intentional: Step Functions remains the sole READY commit authority, and the path must stay single and explicit during the phase
   - there is also a second layer of reasoning in the execution trail: when READY publication initially failed, the remediation did not weaken the proof rule, fake a receipt, or shift authority
   - instead, the system used bounded diagnostics, fixed the publisher defect, and then proved READY publication and receipt cleanly
   - that matters because it shows the path's design was preserved under friction rather than diluted

9. what larger contracts are shaping this path:
   - the main shaping pressure here is the platform's own control and evidence law more than the data-engine interface
   - the run-process requires explicit PASS gates and durable commit evidence for closure
   - the design authority requires one active runtime path per phase, forbids in-phase switching, and requires Step Functions-backed run-state orchestration
   - the observability contract requires run-scoped correlation across orchestrator transitions and evidence surfaces
   - so this path is shaped by the platform's governance law, not just by convenience or local runtime behavior

10. trade-offs and constraints:
   - this path deliberately adds ceremony and friction
   - READY cannot be implied
   - you need:
     - a control topic
     - a run-scoped filter
     - a Step Functions execution reference
     - duplicate and ambiguity checks
     - durable evidence
   - that is more demanding than a looser design, but it buys deterministic gate ownership and cleaner replay/audit semantics
   - it also constrains implementation choices: in-phase switching is prohibited, and even when publish-path defects appeared, the fix had to preserve the same authority and evidence model rather than bypass it

11. necessity test:
   - if this path is removed, the platform can still have running components and even source-realized data, but it loses a clean answer to a crucial question:
     - who said this run was ready, and what makes that claim authoritative?
   - without this path, readiness collapses into a vague runtime feeling
   - the platform would lose:
     - deterministic READY ownership
     - the committed ready receipt
     - duplicate and ambiguity discipline
     - the boundary between compute output and control-plane authorization
   - that would weaken `A` immediately, because a reviewer could fairly say the wired system is still hand-wavy at the exact moment it claims to become operational

12. what this path proves for `A`:
   - purpose claim:
     - the platform has a dedicated job for authorizing readiness, rather than treating readiness as an implicit side effect
   - intentionality claim:
     - the route is deliberately control-plane-backed, with Step Functions as sole commit authority
   - materialization claim:
     - the path is concretely seated in the control topic, state machine, and S3 receipt surfaces
   - constraint-awareness claim:
     - the design knowingly rejects convenience patterns like Flink-only closure or in-phase switching because they would weaken evidence attribution
   - quantified closure claim:
      - the entry precheck resolved all required ready-closure handles
     - the authority surface was active
     - the authoritative READY commit closed green with zero blockers before the rollup advanced the next gate

Plainly stated, the `Ready authorization path` exists to make "this run is now ready" an explicit, control-plane-owned, durable fact, and its current design shows that this is deliberate, materially seated, and governance-driven rather than accidental.

The next clean move is the `Canonical traffic admission and bus publication` group, starting with its first real path.

## 2026-03-12 08:50:56 +00:00 - Splitting Group 2 `Canonical traffic admission and bus publication` into its real paths

I would pin 4 real paths in the `Canonical traffic admission and bus publication` group.

That number feels right because this group has four distinct owned outcomes in the current wired system:

- traffic reaches the active ingress boundary
- traffic receives an admission or disposition decision
- admitted traffic reaches the authoritative bus topics
- the whole ingress act is turned into durable ingest truth

The clean Group 2 path set is:

- `Boundary access path`
- `Admission and disposition path`
- `Authoritative bus publication path`
- `Ingest commit truth path`

I want the path breakdown itself to stay inside this single entry:

1. `Boundary access path`
   - definition:
     - canonical behavioural traffic -> active ingress endpoint with the pinned auth and route contract -> boundary-accepted request envelope
   - why it is a real path:
     - this path turns canonical traffic into a valid request at the active ingress edge
     - only outputs that are actually allowed to behave as traffic may enter here; the engine contract is explicit that only `behavioural_streams` are canonical traffic, while `traffic_primitives`, `behavioural_context`, `truth_products`, `audit_evidence`, and `ops_telemetry` are not to be treated as business traffic
     - the current pinned ingress contract exposes the Execute API boundary as the active ingress edge, while the internal ALB path remains retained but non-primary
     - the ingress URL, ingest path, and API-key contract are all pinned
     - reaching the right front door under the right contract is a different owned outcome from being admitted, so this deserves its own path

2. `Admission and disposition path`
   - definition:
     - boundary-accepted request -> auth / throttling / idempotency / disposition logic -> admit or reject or quarantine or duplicate-safe truth
   - why it is a real path:
     - this path turns a boundary-accepted request into explicit ingress truth
     - the admission path must answer whether traffic can be accepted safely and deterministically through auth, identity, throttling, idempotency, and duplicate-safe handling
     - the implementation notes make the concrete boundary explicit: the IG Lambda computes a canonical dedupe basis from `(platform_run_id, event_class, event_id)`, writes a DynamoDB idempotency record with TTL and admission metadata, and fail-closes with `503` if the idempotency backend is unavailable
     - this is distinct from publication because an event can be correctly classified at ingress even before we ask where it was published

3. `Authoritative bus publication path`
   - definition:
     - admitted ingress event family -> authoritative publication to pinned traffic and context topics -> bus-visible runtime handoff
   - why it is a real path:
     - this path turns an admitted ingress event family into authoritative topic publication
   - the platform distinguishes traffic and context families:
      - the fraud traffic topic
      - the arrival-events context topic
      - the arrival-entities context topic
      - the flow-anchor context topic
     - the data-engine contract explains why that split exists: behavioural streams are intentionally thin traffic, while arrival/entity/flow-anchor surfaces are context to be joined inside the platform
     - this is a distinct owned outcome from merely deciding admission, because this is the first place where Group 2 hands truth over to downstream runtime via the event bus

4. `Ingest commit truth path`
   - definition:
     - admission + publication outcomes -> receipt summary / quarantine summary / offset-proof materialization -> committed ingest truth
   - why it is a real path:
     - this path turns admission and publication activity into durable ingress evidence
     - the run-process gives this a separate closure point: admit/quarantine summaries must be committed, an offset snapshot must be committed in a mode-aware way, and dedupe/anomaly checks must pass
     - the implementation notes reinforce that this is not optional reporting: they explicitly reject claiming pass from DynamoDB admissions alone, and they keep the lane fail-closed when broker offsets are not materially available, recording an explicit admission-index proxy snapshot instead of fabricating broker offsets
     - publication is not enough; the platform must later be able to prove what ingress did for the run

What I would not count as separate real paths here:

- the retained internal ALB ingress URL is not a real path for `A`, because it is a retained surface and not the active external front door of the current pinned ingress contract
- direct DynamoDB seed writes are not a real path, because the implementation notes explicitly reject them as bypassing the IG boundary and therefore failing to prove ingress semantics
- DLQ or quarantine is not a wholly separate canonical group path; it is a disposition and evidence surface inside Group 2, primarily belonging to the admission/disposition path and the ingest commit truth path rather than a standalone primary path

So the pinned Group 2 path set is:

- `Boundary access path`
- `Admission and disposition path`
- `Authoritative bus publication path`
- `Ingest commit truth path`

That is the clean split I want to use. The next step is to take `Boundary access path` and do the same full path-level interrogation used for the three Group 1 paths.

## 2026-03-12 08:58:54 +00:00 - Path interrogation: `Boundary access path`

This path exists to make sure that canonical platform traffic reaches one honest, active ingress boundary rather than some ambiguous or stale front door. In `A` terms, this is not yet the path that decides admit, reject, or quarantine. It is the path that answers a more basic design question:

What is the real external boundary for traffic entering the platform, and how does traffic reach it correctly?

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - make sure canonical platform traffic reaches one honest, active ingress boundary rather than an ambiguous or stale front door
   - answer the basic design question of what the real external traffic boundary is
   - establish the correct ingress edge before admission semantics begin

2. entry:
   - the entry is canonical traffic that is actually allowed to behave as traffic plus the correct ingress contract
   - the data-engine interface is decisive here:
     - only `behavioural_streams` are eligible for ingestion as production traffic
     - `traffic_primitives`, `behavioural_context`, `truth_products`, `audit_evidence`, and `ops_telemetry` are explicitly not canonical business traffic
   - the current traffic policy then narrows that further to the dual-stream default:
     - `s2_event_stream_baseline_6B`
     - `s3_event_stream_with_fraud_6B`
   - so the entry is not "some event-like engine output"
   - it is:
     - canonical behavioural traffic -> correct external ingress URL and route -> correct key and material contract
   - the proving notes also show that boundary targeting had to be made explicit so a stale internal ALB path could not be silently used instead

3. owned outcome:
   - the owned outcome is:
     - a request has reached the correct live ingress boundary under the correct route and auth contract, and is now eligible to be processed by the ingress runtime
   - that is deliberately narrower than "the event was admitted"
   - admission belongs to the next path
   - this path closes once traffic is at the right front door, not once the ingress runtime has classified it
   - the docs support that separation because they pin the active boundary as API Gateway to Lambda, then separately discuss downstream admission semantics, idempotency, and publication continuity as later concerns

4. what the path carries:
   - canonical behavioural event payloads
   - the ingress route contract:
     - stage `v1`
     - `POST /ingest/push`
   - the boundary auth and key material expected by the ingress runtime
   - the engine interface adds the payload-side rule:
     - anything emitted as `behavioural_streams` onto a bus must conform to the canonical event envelope contract
   - the edge-side contract is also explicit:
     - API-key authentication mode
     - the `X-IG-Api-Key` header
     - a pinned secret-backed API key contract
   - health-probe evidence supports the same boundary posture, but the pinned auth contract is already sufficient to show that the ingress runtime expects real key material at the boundary rather than an informal anonymous path

5. broad route logic:
   - canonical behavioural stream -> explicit execute-api ingress URL -> stage `v1` -> route `POST /ingest/push` -> IG Lambda boundary
   - that broad route matters because the design is making a strong statement
   - the platform should not rely on an operator's memory of a service URL, a retained internal ALB surface, or a vague "ingress exists somewhere" story
   - the route is meant to be singular and explicit
   - the proving notes even call the stale ALB path a drift hazard and patch the launcher so it cannot silently fall back there

6. logical design reading:
   - logically, this path shows that the platform treats the external ingress boundary as a first-class system object
   - that is important for `A`
   - the current wired system is not saying:
     - traffic eventually gets in somehow
   - it is saying:
     - traffic enters through this named, active, externally declared boundary
   - that makes the wiring legible
   - it also makes the rest of Group 2 meaningful, because admission, disposition, publication, and receipts only make sense if there is first a single honest answer to what the live ingress edge is
   - the current answer is intentionally singular: the pinned execute-api ingress URL with stage `v1`, route `POST /ingest/push`, and the IG Lambda handler behind it

7. concrete seating in the current wired system:
   - this path is materially seated in concrete infrastructure, not just described conceptually
   - the live handles identify:
     - API name `fraud-platform-dev-full-ig-edge`
     - ingress URL `https://ehwznd2uw7.execute-api.eu-west-2.amazonaws.com/v1`
     - route `POST /ingest/push`
     - Lambda `fraud-platform-dev-full-ig-handler`
   - the implementation notes also record ingress contract remediation that aligned the runtime to:
     - `GET /ops/health`
     - `POST /ingest/push`
   - later proving work then codified the API Gateway telemetry surface and kept the obsolete internal ingress path out of the accepted active-boundary story

8. why the design looks like this:
   - the design looks like this because ambiguity at the front door was treated as a real defect, not a cosmetic nuisance
   - the notes show three important design moves:
     - old stage and route drift was corrected to restore the canonical endpoint model
     - the launcher was patched to force the correct execute-api target instead of silently resolving a stale internal service URL
     - the retained internal ingress stack was treated as a drift hazard because it no longer served the accepted external boundary story
   - so this shape was not accidental
   - it is the result of deliberately narrowing ingress to one active front door

9. what larger contracts are shaping this path:
   - two larger contracts shape this path strongly
   - first, the data-engine interface shapes the entry side:
     - only `behavioural_streams` are traffic
     - non-traffic surfaces must not be treated as business traffic
     - traffic emitted at ingestion must conform to the canonical event-envelope contract
   - second, the platform authority shapes the boundary side:
     - networking is private-by-default, with explicit ingress only where boundary endpoints require it
     - secret and config access is governed through pinned handles like `/fraud-platform/dev_full/ig/api_key`
     - every phase uses one active runtime path per phase/run, with fail-closed governance on path selection
   - so the boundary-access path is shaped both by what traffic is allowed to be and by how the platform is allowed to expose a front door

10. trade-offs and constraints:
   - this path chooses clarity and governance over convenience
   - it is more convenient to let old service URLs linger, let helpers resolve whatever endpoint they find, or tolerate multiple ingress surfaces "for now"
   - but the current design rejects that because it makes the boundary story muddy
   - the cost of the chosen design is more explicitness:
     - explicit execute-api target
     - explicit route
     - explicit key contract
     - explicit exclusion of obsolete ingress surfaces from the accepted active-boundary story
     - explicit telemetry on the real front door
   - that adds ceremony, but it buys a much cleaner claim:
     - the platform has one real ingress boundary

11. necessity test:
   - if this path is removed, Group 2 loses its clean start
   - traffic might still reach something, but the platform could no longer honestly say:
     - what its real front door is
     - whether the old ALB path still counts
     - whether helpers are proving the active boundary or a stale one
     - whether boundary evidence and telemetry belong to the right surface
   - in other words, the system could still have admission logic, bus publication, and receipts, but the boundary those things supposedly begin from would be hand-wavy
   - that would directly weaken `A`, because a skeptical reviewer could say the ingress story is still ambiguous at the very first hop

12. what this path proves for `A`:
   - purpose claim:
     - the platform has a specific job for establishing the correct ingress boundary before admission semantics begin
   - intentionality claim:
     - the active external front door is singular and explicitly chosen, not just whatever surface happens to be reachable
   - materialization claim:
     - the boundary is concretely seated in the pinned execute-api ingress URL, stage `v1`, route `POST /ingest/push`, and the IG Lambda handler
   - contract claim:
     - the entry traffic is constrained by the engine's traffic taxonomy and canonical event-envelope rule
   - quantified closure claim:
     - one active external front door
     - one stage
     - one route
     - one handler
     - with the obsolete internal ingress path explicitly excluded from the accepted active-boundary story

Plainly stated, the `Boundary access path` exists to ensure that canonical traffic reaches one real, explicit, governed ingress edge, and its current design shows that the boundary is deliberate, materially seated, and no longer muddied by stale ingress alternatives.

The next clean move is the `Admission and disposition path`.

## 2026-03-12 09:14:51 +00:00 - Path interrogation: `Admission and disposition path`

This path exists to turn a request that has already reached the correct ingress boundary into truthful ingress decision. Its job is not "get traffic into the platform somehow." Its job is to decide, deterministically and at the ingress ownership boundary, whether the event is:

- admitted
- duplicate-safe
- rejected invalid
- explicitly marked ambiguous or retry-governed
- or quarantined

That separation is already visible in the docs: the control and ingress plane is supposed to admit valid traffic, reject invalid traffic, deduplicate repeated traffic, and keep failure classes explicit rather than mixing them together. Later, ingest-commit closure only happens when admit and quarantine summaries are committed and dedupe and anomaly checks pass, which means disposition truth is first-class thing, not incidental side effect.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn a boundary-valid request into truthful ingress decision
   - make the ingress ownership boundary decide the event's disposition explicitly rather than leaving it implicit
   - stop this path at ingress truth rather than letting it collapse into bus publication

2. entry:
   - the entry to this path is not raw engine data in general
   - it is request that has already crossed the active front door under the correct route and auth contract, carrying traffic that is actually allowed to behave as traffic
   - the engine interface is explicit that only `behavioural_streams` are canonical business traffic, and that anything emitted as `behavioural_streams` onto a bus must conform to the canonical event-envelope contract
   - the current traffic policy is the dual-stream posture:
     - `s2_event_stream_baseline_6B`
     - `s3_event_stream_with_fraud_6B`
   - on the platform side, the current ingress handles pin the active request contract as API Gateway base URL plus `POST /ingest/push` plus `X-IG-Api-Key`
   - so this path begins only after a boundary-valid traffic request exists

3. owned outcome:
   - the owned outcome is durable, truthful ingress disposition for this event under this run scope
   - that means the event is no longer just "in flight at the edge"
   - it now has ingress truth attached to it:
     - admitted
     - duplicate-safe
     - rejected invalid
     - quarantined
     - or explicitly marked ambiguous or retry-governed
   - with run-scoped evidence sufficient for later investigation
   - the bus handoff itself belongs to the next path
   - this path stops at the point where the ingress plane has done its own job and recorded its own truth
   - that matches both the ingress-shell criteria and the later ingest-commit closure rule, where admit and quarantine summaries and dedupe checks are committed separately from full downstream proof

4. what the path carries:
   - the path carries the minimum objects needed to make ingress truth real rather than implied:
     - run identity: `platform_run_id`
     - event identity: `event_class`, `event_id`
     - payload identity: payload hash
     - dedupe identity: canonical `dedupe_key`
     - retention and idempotency timing: TTL field
     - disposition metadata: state, admitted timestamp, and reason codes when present
   - the implementation notes make this concrete:
     - the selected IG patch computes deterministic SHA-256 dedupe key from `(platform_run_id, event_class, event_id)`
     - writes DynamoDB item keyed by that dedupe basis
     - stores minimal admission metadata
     - fail-closes with `503` when the idempotency backend is unavailable
   - the broader identity model from the engine interface also reinforces that execution and run identity and event identity must stay explicit rather than being inferred informally

5. broad route logic:
   - boundary-accepted request -> IG handler applies ingress contract -> canonical dedupe and admission basis is computed -> authoritative idempotency and admission state is written -> truthful disposition is then returned to the caller and made available for later evidence closure
   - the key point is that this path closes at disposition truth, not at bus truth
   - that is why it is separate from the next path
   - it is also why unknown publish outcome matters here without collapsing this path into publication:
     - ingress must decide how to classify ambiguity
     - the readiness criteria are explicit that unknown publish outcomes must become retry-governed or quarantined according to contract and must not be silently marked as success
   - that is still part of truthful disposition ownership, even though the actual authoritative topic handoff comes next

6. logical design reading:
   - logically, this path shows that the platform treats ingress truth as its own boundary-owned truth, not just prelude to Kafka
   - that is important for `A`
   - the system is not saying:
     - an event counts as handled once something downstream eventually sees it
   - it is saying:
     - the ingress plane itself owns deterministic dedupe and disposition judgment
   - that matches the broader semantic law in the readiness definition that truth ownership boundaries must be preserved, including the specific rule that ingress truth stays ingress truth
   - it also matches the ingress-plane requirement that there be one authoritative dedupe boundary

7. concrete seating in the current wired system:
  - this path is concretely seated in the current wired runtime, not just described abstractly
  - the design authority pins the default ingress posture as API Gateway plus Lambda plus DynamoDB idempotency store
  - the handles registry pins the live edge contract around the active ingress URL, ingest route, authentication mode, and secret-backed API key contract
   - the implementation notes then make the active runtime posture more specific:
     - the current IG edge runtime is the API Gateway -> Lambda -> DynamoDB ingress posture
     - the remediation work for active ingress progression was specifically about making the Lambda path persist idempotency and admission records into DynamoDB so the lane could produce non-zero, run-scoped admission truth

8. why the design looks like this:
   - the current shape is the result of very specific correction
   - before the patch, `/ingest/push` could return `202` without persisting any run-scoped admission or idempotency record
   - that was rejected as structurally wrong for the current wired platform because the ingress plane then had no durable proof of its own decision
   - the alternatives were also rejected for good reasons:
     - direct DynamoDB seed writes were rejected because they bypass the ingress boundary and would not prove runtime semantics
     - treating the issue as non-blocking was rejected because it would violate the fail-closed gate contract
   - so the selected fix was not cosmetic
   - it was boundary correction:
     - put truthful admission persistence inside the IG Lambda path itself

9. what larger contracts are shaping this path:
   - two larger contracts are strongly shaping it
   - first, the engine interface contract shapes what may even appear at ingress:
     - only `behavioural_streams` are canonical traffic
     - canonical traffic must conform to the event-envelope contract
     - non-traffic surfaces must not be treated as business traffic
   - second, the platform authority shapes how ingress is allowed to exist:
     - managed-first ingress posture
     - explicit dedupe identity and payload-hash anomaly law
     - explicit truth boundaries
     - no silent defaults or local or toy substitutes in pinned lanes
   - so this path is constrained both by what is allowed to enter and by how ingress truth is allowed to be owned

10. trade-offs and constraints:
   - this path deliberately accepts some hot-path ceremony in exchange for truthfulness
   - durable dedupe and admission ledger adds write pressure and cost to the ingress hot path
   - the later readiness notes show that this became real operational concern:
     - the idempotency table became dominant cost surface when full receipt bodies were stored inline
   - the platform did not solve that by abandoning the ledger boundary
  - instead, it kept the proven compact hot-table posture and compacted the stored receipt shape to the minimum fields needed for run attribution and lookup
   - that is a good example of the distinction that matters here:
     - the ownership boundary stayed the same
     - while the concrete implementation was tightened

11. necessity test:
   - if this path is removed, the ingress story becomes immediately weaker
   - the platform might still have front door, and it might still publish some things later, but it would lose clean answer to basic questions:
     - was this event first-seen or duplicate
     - was it admitted or quarantined
     - what run did that decision belong to
     - was the ingress plane itself behaving truthfully
     - is downstream starvation publication issue, or was the event never actually admitted
   - that is exactly why the docs keep returning to explicit disposition classes, dedupe correctness, and durable receipt and quarantine truth
   - without this path, downstream components would be forced to infer ingress truth after the fact, which would blur ownership and weaken `A`

12. what this path proves for `A`:
   - purpose claim:
     - ingress does not merely pass traffic through; it owns deterministic admission and disposition decision
   - intentionality claim:
     - the dedupe boundary and disposition logic are deliberate and explicit, not accidental consequences of downstream publish
   - materialization claim:
      - the path is concretely seated in the current API Gateway -> Lambda -> DynamoDB ingress posture with DynamoDB-backed idempotency and admission state
   - contract claim:
     - only the right traffic types are eligible, and ingress truth remains ingress truth
   - quantified closure claim:
     - later closure is not vague
      - the ingest-commit gate explicitly requires admit and quarantine summaries plus dedupe and anomaly checks, which means this path has named evidence closure downstream in the runbook

Plainly stated, the `Admission and disposition path` exists to make ingress truth explicit before event-bus truth begins, and its current design shows that this is deliberate, materially seated, and ownership-aware rather than hand-wavy.

The next path is the `Authoritative bus publication path`.

## 2026-03-12 09:21:41 +00:00 - Path interrogation: `Authoritative bus publication path`

This path exists to turn ingress truth into authoritative event-bus truth. The previous path decides whether an event is admitted, quarantined, rejected, or duplicate-safe. This path answers the next question:

For traffic that ingress has decided to admit, where does the platform authoritatively hand it off so runtime can begin?

The pinned topic contracts make that answer explicit: the bus surfaces are authoritative, and the ingress layer is the producer for the traffic and context topics that feed RTDL. The design authority names Kafka topics as authoritative bus surfaces, and the topic map pins the ingress layer as the producer for the fraud traffic topic, the arrival-events context topic, the arrival-entities context topic, and the flow-anchor context topic.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn ingress truth into authoritative event-bus truth
   - answer where admitted traffic is authoritatively handed off so runtime can begin
   - keep bus handoff truth separate from both admission truth and later ingest-commit truth

2. entry:
   - the entry is admitted ingress event family that has already crossed the boundary and received admit-worthy disposition
   - it is not raw source data in general, and it is not yet receipt truth
   - the data-engine contract is what makes the family structure intelligible:
     - only `behavioural_streams` are canonical traffic
     - arrival, entity, and flow-anchor surfaces are context, not traffic
     - traffic stays thin, and context is joined inside the platform rather than being smuggled into one fat payload
   - that is why the publish surface is not just one topic
   - it is family of traffic plus context topics

3. owned outcome:
   - the owned outcome is that the admitted ingress event family has been authoritatively handed off onto the pinned traffic and context topics that downstream RTDL is supposed to consume
   - that is narrower than the claim that the platform can later prove offsets and summaries
   - the durable offset and receipt rollup belongs to the next path, the ingest-commit-truth path
   - this path closes earlier, at the point where the bus handoff itself is the real truth
   - the docs support that split cleanly:
     - the design authority and handles registry pin the topics and producer and consumer roles
     - the readiness definition says admitted events must be published into the event transport network without ambiguity

4. what the path carries:
   - this path carries two kinds of things
   - first, it carries the admitted traffic family:
     - the canonical fraud traffic stream itself
     - the associated arrival and context surfaces that downstream RTDL needs
   - second, it carries the bus-level publication identity:
     - the pinned topic names
     - the partition-key rules
     - the producer and consumer contract
     - and, when publication is successful enough to be reconstructed later, topic, partition, and offset truth
   - the topic map pins the concrete topic family and the partition keys:
     - traffic and context both partition by `merchant_id`
   - that already tells us this is not arbitrary publish shape but deliberate continuity rule across the ingress-to-context boundary

5. broad route logic:
   - admitted ingress event family -> IG publish logic -> pinned traffic and context topics on MSK -> bus-visible handoff to RTDL ingress, context, and join consumers
   - that broad route matters because it shows the platform is not treating admitted as the same thing as downstream can now consume
   - there is real handoff boundary in between, and it is Kafka and MSK, not hidden in-memory continuation
   - the design authority is explicit that Kafka topics remain the authoritative bus surfaces, and the topic-continuity appendix pins IG as the producer and RTDL ingress, context, and join planes as the consumers

6. logical design reading:
   - logically, this path shows that the platform treats publish truth as its own truth boundary, not as casual extension of admission
   - that is strong `A`-level design signal
   - the system is not saying:
     - once ingress says admit, we can assume runtime got it
   - it is saying:
     - admit truth and publish truth are different, and the publish boundary must be explicit, authoritative, and reconstructable
   - that is exactly why the broader readiness language distinguishes admits valid traffic from publishes admitted events into the event transport network without ambiguity, and why truth-ownership boundaries are kept separate across planes

7. concrete seating in the current wired system:
   - this path is materially seated in concrete runtime and handles
   - the bus is AWS MSK Serverless
   - the producer boundary is IG
   - the topic family is pinned by name
   - the bootstrap and schema-registry handles are pinned
   - and the producer and consumer map is pinned as well:
     - the fraud traffic topic - ingress to RTDL ingress
     - the arrival-events context topic - ingress to RTDL context
     - the arrival-entities context topic - ingress to RTDL context
     - the flow-anchor context topic - ingress to the RTDL join plane
   - so this is not conceptual story like "messages eventually go somewhere"
   - the publish handoff is concretely seated in named managed bus, named topics, named partition rules, and named downstream consumers

8. why the design looks like this:
   - the design looks like this because the platform wants to preserve thin-traffic semantics while still giving RTDL enough context to work correctly
   - that is why the publish boundary is not just one giant canonical payload topic
   - the data-engine interface says traffic stays thin, joins happen inside the platform, and context surfaces like arrival events, arrival entities, and flow anchors are not to be treated as traffic
   - the pinned topic set mirrors that semantic split directly:
     - one traffic topic
     - plus context topics feeding different RTDL consumers
   - that is strong sign that the current bus shape is driven by system meaning, not by incidental implementation convenience

9. what larger contracts are shaping this path:
   - three larger contracts shape it
   - first, the data-engine contract shapes what may be published as traffic and what must remain context-only:
     - only behavioural streams are eligible as traffic
     - arrival, entity, and flow-anchor surfaces are context for enrichment
     - truth products and telemetry are not to be published as business traffic
   - second, the topic and contract continuity law shapes where those things are published and who owns them:
     - existing dev_min topic contracts remain authoritative unless explicitly repinned
     - any new topic or schema surface must be pinned in the handles registry first
   - that means the bus handoff is contract-governed, not ad hoc
   - third, the ingress and control plane law shapes failure behavior:
     - Kafka topics are authoritative bus surfaces
     - the edge must enforce pinned limits
     - fail-closed posture is part of the platform law
   - so if publish outcome is ambiguous, the system is not allowed to quietly pretend success

10. trade-offs and constraints:
   - this path deliberately chooses explicit bus truth over simpler but weaker alternatives
   - it would be easier to collapse admission and publish into one fuzzy notion of ingress handled it, or to publish only single flattened traffic topic and let downstream reconstruct context however it can
   - but the current design rejects that
   - it pays the cost of:
     - maintaining topic family rather than one topic
     - keeping producer and consumer contracts explicit
     - treating publish ambiguity as real error class
     - requiring schema and contract continuity rather than allowing silent reinterpretation
   - the runtime notes show that this discipline has real consequences
   - under more aggressive concurrency probe, the live ingress runtime surfaced `KAFKA_PUBLISH_TIMEOUT` and `PUBLISH_AMBIGUOUS`, and valid traffic was fail-closed into quarantine rather than being silently counted as successfully published
   - that is important design signal:
     - the platform would rather block than lie about bus truth

11. necessity test:
   - if this path is removed, the platform still has:
     - ingress edge
     - admission boundary
     - RTDL components drawn downstream
   - but it loses the clean truth that connects them
   - without this path, reviewer could not answer:
     - where admitted traffic actually enters the runtime network
     - whether the full event family reached downstream consumers
     - whether traffic and context separation was preserved
     - whether publish ambiguity was handled honestly
     - whether RTDL starvation is publish problem or downstream problem
   - that would weaken `A` immediately, because the system would start looking like graph with missing ownership boundary between ingress and runtime

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for turning ingress truth into authoritative bus truth
   - intentionality claim:
     - the bus handoff is not generic pub/sub; it is semantically split traffic and context family that mirrors the engine's thin-traffic join posture
   - materialization claim:
     - the handoff is concretely seated in MSK Serverless, pinned topic names, pinned partition keys, and pinned IG -> RTDL producer and consumer roles
   - contract claim:
     - the path is governed by topic continuity, traffic taxonomy, and fail-closed truth-boundary laws
   - constraint-awareness claim:
     - publish ambiguity is treated as real boundary defect, not silently absorbed as success

Plainly stated, the `Authoritative bus publication path` exists to turn admitted ingress traffic into explicit, semantically correct, contract-governed runtime handoff, and its current design shows that this handoff is deliberate, materially seated, and truth-boundary aware rather than implicit.

The next path is the `Ingest commit truth path`.

## 2026-03-12 09:28:56 +00:00 - Path interrogation: `Ingest commit truth path`

This path exists to turn what ingress did into durable, run-scoped ingest truth. The previous path made bus handoff authoritative; this path makes the results of ingestion committed and reconstructable. In the run-process, that is exactly what the ingest-commit closure means: once active ingestion exists, the platform must commit admit and quarantine summaries, commit an offset snapshot in the correct mode, and pass dedupe and anomaly checks before the phase can close.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn what ingress did into durable, run-scoped ingest truth
   - make ingest results committed and reconstructable rather than merely observed
   - close ingestion through evidence rather than through an impression that runtime activity probably happened

2. entry:
   - the entry is not that some requests hit ingress
   - it is narrower:
     - active ingestion counters are non-zero
     - or an explicit empty-run waiver exists
   - that means this path only begins once ingress has already been live enough to generate meaningful ingest basis
   - it is therefore downstream of boundary access, downstream of admission and disposition, and downstream of authoritative bus publication

3. owned outcome:
   - the owned outcome is committed ingest evidence set for this run consisting of:
     - admit and quarantine summaries
     - an offset-proof snapshot in the correct evidence mode
     - and dedupe and anomaly verdict that passes
   - that is the clean closure of the path
   - it is not just that ingress probably worked
   - and it is not yet that RTDL has caught up
   - it is specifically the point where ingress behavior has been turned into durable ingest truth

4. what the path carries:
   - this path carries the evidence objects that make ingest reconstructable:
     - `receipt_summary.json`
     - `quarantine_summary.json`
     - `kafka_offsets_snapshot.json`
     - and the rollup and execution artifacts that declare whether the ingest-commit lane passed or failed
   - in the current wired posture, it also carries the offset-proof mode itself, because the proof basis depends on the ingress edge mode
   - the handles registry pins that relationship directly:
     - the current API Gateway -> Lambda -> DynamoDB ingress posture uses an admission-index proxy proof mode
     - a direct Kafka ingress edge would use broker topic and partition offsets

5. broad route logic:
   - run-scoped ingress activity -> managed ingest-commit lane reads authoritative ingress evidence surfaces -> receipt, quarantine, and offset-proof artifacts are built -> ingest-commit verdict is computed and committed
   - that broad route matters because it shows this is control and evidence path, not hot-path runtime continuation
   - the implementation notes are explicit that these ingest-commit lanes were added as managed workflow surfaces, are control-plane heavy, and do not introduce long-lived runtime compute

6. logical design reading:
   - logically, this path shows that the platform treats ingest closure as evidence closure, not just runtime behavior
   - the system is not satisfied with:
     - admissions happened in DynamoDB
     - or messages probably made it to the bus
   - it requires bounded artifact set that later phases can read as ingest truth
   - that is why ingest closure has its own phase and its own blockers, rather than being swallowed by streaming activity or RTDL

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired system
   - the run-process and handles pin concrete ingest evidence artifacts under the run evidence root:
     - `evidence/runs/{platform_run_id}/ingest/receipt_summary.json`
     - `evidence/runs/{platform_run_id}/ingest/quarantine_summary.json`
     - `evidence/runs/{platform_run_id}/ingest/kafka_offsets_snapshot.json`
   - the path reads the live ingress basis from the current ingress edge posture and publishes durable truth into those pinned ingest evidence surfaces rather than leaving it trapped in live runtime stores
   - the proof rule is also concretely seated:
     - the current ingress posture uses admission-index proxy mode
     - while a direct Kafka ingress edge would use broker offset mode

8. why the design looks like this:
   - the design looks like this because the platform explicitly rejected weaker alternatives
   - the implementation notes are very clear:
     - claiming ingest-commit pass from DynamoDB admissions alone was rejected
     - running the lane locally from the operator shell was rejected
     - and forcing broker topic and partition offsets when the current ingress edge does not materially emit them was also rejected
   - instead, the chosen design kept fail-closed posture but made offset proof mode-aware
   - if direct broker offsets are available, use them
   - if not, and the current edge is the API Gateway -> Lambda -> DynamoDB posture, derive explicit and deterministic admission-index proxy snapshot instead
   - that is a very deliberate design move:
     - keep the truth boundary
     - adapt the proof mode to the actual wired edge
     - and never silently fabricate broker offsets

9. what larger contracts are shaping this path:
   - three larger contracts shape it
   - first, the run-process contract defines the closure rule for ingest commit:
     - summaries committed
     - mode-aware offset proof committed
     - dedupe and anomaly checks passing
   - second, the handles registry pins the ingress-edge-dependent proof rule
   - that means the path is not free to invent its own evidence semantics; the proof mode is pinned function of the wired ingress posture
   - third, the later replay-basis contract depends on this path
   - learning-input closure explicitly says replay basis must be pinned as origin-offset ranges, and it defines the semantics of admission-index proxy mode versus broker-offset mode
   - that means this path is not just local bookkeeping; it is upstream of later replayable learning truth

10. trade-offs and constraints:
   - this path deliberately accepts less pure proof mode in exchange for keeping the current ingress edge and preserving fail-closed semantics
   - in the current API Gateway -> Lambda -> DynamoDB posture, the ingress edge persists admissions in DynamoDB but does not emit broker topic and partition offsets into stored idempotency rows
   - the design did not weaken the path into admissions alone are enough
   - instead, it kept explicit offset proof, but allowed deterministic proxy mode for this edge
   - that is real design trade-off:
     - preserve the closure discipline
     - while admitting the current edge's evidence limitations honestly

11. necessity test:
   - if this path is removed, the platform still has ingress edge, admission logic, and bus publication, but it loses clean answer to:
     - what ingest actually committed for this run
     - what was admitted versus quarantined
     - what replay basis later lanes should trust
     - whether dedupe and anomaly checks actually passed
     - and whether ingest closure is grounded in durable artifacts or only inferred from live stores
   - that would weaken `A` immediately, because the ingress part of the system would stop looking governed and start looking observational
   - the docs themselves make this visible by treating missing receipt surfaces and dedupe drift as explicit blockers, not as later debugging concerns

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for turning ingress activity into committed ingest truth, not just letting ingress side effects accumulate
   - intentionality claim:
     - the path is deliberately evidence-driven, managed, and fail-closed, rather than best effort
   - materialization claim:
     - the path is concretely seated in explicit ingest evidence artifacts and pinned edge-dependent proof rule
   - contract claim:
     - the meaning of offset proof is governed by the run-process and the handles registry, and it later feeds the replay-basis semantics for learning input
   - constraint-awareness claim:
     - the current ingress posture cannot honestly supply broker offsets, so the system uses explicit proxy mode rather than pretending otherwise
   - closure signal:
     - the design enforces the truth boundary rather than treating it as decorative
     - when offset evidence is not materially available, the path fails closed
     - and the answer is to correct the proof mode honestly, not to weaken the closure into vagueness

Plainly stated, the `Ingest commit truth path` exists to turn ingress behavior into durable, mode-aware, replay-relevant ingest evidence, and its current design shows that this closure is deliberate, materially seated, and honest about the limits of the current ingress edge rather than hand-wavy.

At this point, Group 2 has all four real paths interrogated:

- `Boundary access path`
- `Admission and disposition path`
- `Authoritative bus publication path`
- `Ingest commit truth path`

## 2026-03-12 09:40:49 +00:00 - Enumerating the real paths in Group 3: `Runtime context formation and decisioning`

I want to pin 6 real paths in the runtime context formation and decisioning group.

I am choosing 6 because, before we get to audit and archive, the current RTDL story already exposes six distinct owned outcomes:

- entity and relationship projection
- joined context
- online feature readiness
- decision guardrail posture
- decision truth
- and action or outcome truth

That split also matches the way the RTDL docs separate the context-shaping, projection, feature, guardrail, decision, and action surfaces, while the run-process separately closes RTDL catch-up and the decision chain as distinct boundaries.

A second reason this split works is that the current wired system already pins the main seating and semantic constraints for these paths:

- IG publishes the traffic and context family onto the event bus
- RTDL consumes those topics
- the baseline wired RTDL path is seated across the RTDL namespace, workers, stores, and downstream handoff topics in the copied wired graphs
- and live runtime is only allowed to use the time-safe oracle outputs:
  - `s3_event_stream_with_fraud_6B`
  - `arrival_events_5B`
  - `s1_arrival_entities_6B`
  - `s3_flow_anchor_with_fraud_6B`
- while truth outputs and future-implying fields are forbidden

I want to pin the 6 real paths in Group 3 like this:

1. `Entity and relationship projection path`
   - definition:
     - admitted traffic and context topics -> RTDL entity update logic -> current entity and relationship projection truth
   - why it is a real path:
     - this path has its own distinct purpose:
       - build identity and entity relationship state from admitted platform data
     - the docs treat projection correctness, lag, checkpoint age, replay determinism, and apply correctness as its own boundary question rather than folding it into decisioning generically

2. `Joined context formation path`
   - definition:
     - admitted event family + projected entity and flow state + allowed time-safe context -> joined runtime context surface and readiness truth
   - why it is a real path:
     - this path has distinct owned outcome:
       - not just that projections exist, but that the right joined context exists for the event now being processed
     - I would not collapse this into projection, because having projections is not the same thing as having correct joined context for this event

3. `Online feature readiness path`
   - definition:
     - joined context + current RTDL state -> online feature state and feature availability truth for live decisions
   - why it is a real path:
     - this path has distinct owned outcome:
       - not merely that context exists, but that the decision can actually use the required feature groups with correct freshness and bounded restart behavior
     - the docs are explicit that partial key coverage, stale feature serving, and false missing-feature states are separate concerns here

4. `Decision guardrail path`
   - definition:
     - context, feature, and dependency posture -> adjudicated decision mode such as proceed, quarantine, fail-closed, or advisory posture
   - why it is a real path:
     - this path owns the runtime health and dependency posture for decisioning
     - the docs treat false fail-closed, dependency classification correctness, and recovery-to-normal as distinct responsibility
     - so this path has its own owned outcome:
       - safe and explicit decision posture

5. `Decision formation path`
   - definition:
     - joined context + online features + active bundle or policy resolution + guardrail posture -> decision truth
   - why it is a real path:
     - this path is where the platform actually produces the decision output
     - the docs make that distinct responsibility:
       - decisions must be correct for the actual context, feature state, and active bundle or policy in scope
       - with provenance and explainability complete enough to survive replay and audit
     - I want to keep active bundle or policy resolution inside this path for `A`, because the larger cross-plane feedback from registry to runtime is whole-platform handoff, while the Group 3 owned outcome here is still that decision truth was formed correctly

6. `Action and outcome emission path`
   - definition:
     - decision truth -> action logic and outcome commit or publish -> RTDL outcome truth for downstream use
   - why it is a real path:
     - this path owns distinct job after decision formation:
       - turn decisions into deterministic side effects or outcome surfaces without duplicate corruption or ambiguity leakage
     - the bus contract helps here:
       - the RTDL downstream topic is the pinned handoff surface
       - the decision and action surfaces are the producers
     - that gives this path concrete handoff boundary

What I do not want to count here:

- the audit append path
- the archive writer path

Even though the larger RTDL plane includes the decision log and audit corridor and the archive writer, those belong to the next group for this `A` structure:

- `Durable audit, archive, and replay truth`

because they own different obligation family:

- turning runtime behavior into append-only historical truth

I also do not want to make registry-to-runtime active bundle feedback its own Group 3 path right now. That is real cross-plane handoff in the whole-platform story, but inside Group 3's current wired job, the owned outcome I need to interrogate is still the decision formation path that consumes the active bundle or policy at runtime.

So the pinned Group 3 path set is:

1. `Entity and relationship projection path`
2. `Joined context formation path`
3. `Online feature readiness path`
4. `Decision guardrail path`
5. `Decision formation path`
6. `Action and outcome emission path`

That is the clean split I want to use before going back down into per-path interrogation.

## 2026-03-12 10:50:57 +00:00 - Path interrogation: `Audit append path`

This path exists to turn decision and action truth into authoritative audit and lineage truth for the real-time lane. Its job is not to form the decision, not to emit the action, and not yet to preserve immutable archive history. Its narrower job is to answer:

Once the platform has decided and acted, where does the authoritative append-only record of that fact get created?

The docs make that boundary explicit. The decision log and audit surface exists to append authoritative audit and lineage truth for the real-time lane, and the decision-chain closure only closes when append-only audit evidence is committed alongside decision and action evidence.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn decision and action truth into authoritative audit and lineage truth for the real-time lane
   - keep this path narrower than decision formation, action emission, and archive preservation
   - answer where the authoritative append-only record of runtime decisions and outcomes gets created

2. entry:
   - the entry is not raw RTDL traffic and not generic runtime health
   - the entry is current-run decision and action truth after the RTDL plane has already crossed its main catch-up boundary
   - the run-process is clear:
     - the decision-chain closure opens only after RTDL catch-up closure is green
     - and then requires three distinct closure elements:
       - decision lane committed
       - action and outcome evidence committed
       - append-only audit evidence committed
   - so this path begins after Group 3's decision and action paths have already produced their own truth

3. owned outcome:
   - the owned outcome is append-only audit and lineage truth for the current run and current runtime event chain
   - that outcome is deliberately narrower than audit consumers saw it and narrower than archive history is preserved
   - this path closes when the real-time lane has an authoritative audit append, not when that audit truth has later been published or archived
   - the audit definition itself reinforces that split:
     - append-only behavior
     - replay divergence
     - lineage completeness
     - unresolved-lineage age
     - and readback integrity
     - are the properties of this boundary

4. what the path carries:
   - this path carries the minimum things needed to make the audit record authoritative rather than decorative:
     - decision identity
     - action and outcome identity
     - run identity
     - lineage links from decision to outcome to audit artifact
     - enough provenance for later replay, incident review, and downstream learning support
   - the RTDL explainability posture is useful here because it shows what must survive into later truth surfaces:
     - every decision must be traceable to run identity
     - context surfaces
     - feature groups
     - policy and bundle used
     - action emitted
     - audit entry appended
     - and archive and evidence refs
   - the audit surface then narrows that into its own boundary by requiring lineage completeness from decision to outcome to audit artifact

5. broad route logic:
   - decision truth + action and outcome truth -> audit append writer -> append-only audit and lineage truth -> later publication and archive consumers
   - that broad route matters because it shows the audit append surface is not more logging
   - it is the first place where the hot path becomes an authoritative historical truth boundary
   - the path stops at append-only audit truth
   - it does not yet include the later audit-topic handoff or archive preservation
   - that is exactly why this group is split into separate paths

6. logical design reading:
   - logically, this path shows that the platform treats audit truth as first-class owned append-only surface, not as something that can be reconstructed later from side effects if needed
   - that is strong `A`-level design signal
   - the system is not saying:
     - if we have the decision and the action, we can probably infer the audit story later
   - it is saying:
     - there is dedicated runtime boundary whose job is to append authoritative audit and lineage truth
     - and the decision chain is not considered committed without it
   - that makes the current wired system look governed rather than hand-wavy

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired system
   - the copied baseline wired graphs show the audit surface as a distinct deployment in the RTDL namespace
   - they also show required run pins flowing to that surface
   - the run-process phase map places the decision, action, and audit surfaces together inside the live RTDL decision corridor rather than treating audit as later offline convenience
   - the broader authority keeps the decision, action, and audit surfaces in the RTDL ownership-logic corridor, with the audit surface retained as distinct ownership-heavy runtime boundary unless semantic parity is proven elsewhere
   - the live implementation trail also shows the audit surface present in the active RTDL runtime set, and bounded proof snapshots recorded concrete counters such as:
     - `append_success_total`
     - `append_failure_total`
     - `replay_divergence_total`

8. why the design looks like this:
   - the design looks like this because the platform refuses to let auditability be implied by runtime success
   - two choices matter here
   - first, the decision-chain closure explicitly separates decision, action, and audit into three closure elements
   - that means audit append is not allowed to hide inside generic claim that the hot path passed
   - second, the audit surface was deliberately not collapsed into managed replacement by default; the broader authority keeps it as custom-runtime until full semantic parity is proven
   - that tells us the current shape is being driven by truth ownership and append semantics, not just by convenience or simplification pressure

9. what larger contracts are shaping this path:
   - three larger contracts shape it strongly
   - first, the audit component contract defines what this boundary must mean:
     - append-only behavior under replay and duplicate pressure
     - zero replay divergence on the same bounded basis
     - lineage completeness
     - bounded unresolved-lineage age
     - readback integrity
   - second, the decision-chain closure contract shapes it from the run-process side:
     - no decision-chain closure without append-only audit evidence
   - third, the append-only ownership law shapes it from the global discipline side:
     - append-only ownership violations are stop-the-line conditions
   - that is important because it tells us the platform is treating this as hard truth boundary, not soft reporting surface

10. trade-offs and constraints:
   - this path deliberately adds another explicit truth boundary to the hot path
   - that costs complexity, because the system must preserve:
     - append-only discipline
     - duplicate and replay safety
     - lineage completeness
     - unresolved-lineage surfacing
     - readback integrity
   - it also explains why the audit surface has not simply been replaced with cheaper generic sink yet:
     - the authority is prioritizing semantic parity over simplification
   - but that cost buys something important:
     - later case handling, evidence sinks, replay, and learning do not need to infer audit history from scattered clues
     - they can depend on named append-only audit boundary

11. necessity test:
   - if this path is removed, the platform can still:
     - ingest traffic
     - build context
     - materialize features
     - classify guardrail posture
     - form decisions
     - and emit actions
   - but it loses clean answer to:
     - where authoritative runtime audit truth comes from
     - whether lineage from decision to outcome is durably preserved
     - whether replay divergence is visible
     - and whether later reviewers are reading true audit record or just reconstructing history from fragments
   - that would weaken `A` immediately, because reviewer could fairly say the system has runtime behavior but no explicit owner for the append-only truth that makes that behavior explainable later
   - the docs themselves state this plainly:
     - without the audit surface, you may have decisions but not authoritative audit truth

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for appending authoritative runtime audit and lineage truth
   - intentionality claim:
     - audit append is required closure element in the decision chain, not optional afterthought
   - materialization claim:
     - the audit surface is concrete live runtime workload in the RTDL plane, not just conceptual box
   - contract claim:
     - this path is governed by append-only discipline, replay-divergence expectations, lineage completeness, and readback integrity
   - constraint-awareness claim:
     - the system already knows this boundary is semantically delicate, which is why the audit surface is retained as custom-runtime until managed replacement can prove full parity
   - material participation evidence:
     - in richer bounded RTDL proof after the repin fix, the live runtime recorded `append_success_total = 2494`, `append_failure_total = 0`, and `replay_divergence_total = 0`
     - that is not, by itself, a full readiness claim for the plane
     - but it is strong `A`-style evidence that the boundary is real, active, and instrumented, not just drawn on graph

Plainly stated, the `Audit append path` exists to turn runtime decisions and outcomes into authoritative append-only audit truth, and its current design shows that this boundary is deliberate, materially seated, and governed by truth-ownership rules rather than left implicit.

The next path in this group is the `Audit publication and durable reference path`.

## 2026-03-12 10:52:04 +00:00 - Path interrogation: `Audit publication and durable reference path`

This path exists to turn already appended audit truth into downstream-consumable audit truth plus durable audit references. Its job is not to create the append-only audit record, and it is not yet to preserve immutable archive history for replay. Its narrower job is to answer:

Once the audit surface has appended authoritative audit truth, how does that truth become consumable by the rest of the platform in durable, referenceable way?

That is a real boundary in the docs. The copied baseline graph pins the audit topic as an explicit audit handoff surface, with the audit layer publishing into it and downstream operational and evidence-consuming surfaces reading from that side of the network. At the same time, the broader audit authority is clear that durable by-ref evidence remains authoritative and audit-topic publication is a distribution convenience rather than the truth source itself.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn already appended audit truth into downstream-consumable audit truth plus durable audit references
   - keep this path narrower than audit append and narrower than archive preservation
   - answer how authoritative audit truth becomes consumable by the rest of the platform in durable, referenceable way

2. entry:
   - the entry is not raw runtime traffic and not the decision itself
   - the entry is the append-only audit truth that already exists after the decision chain has closed its audit-append requirement
   - the run-process is explicit that the decision-chain closure only closes when:
     - decision truth
     - action and outcome truth
     - and append-only audit evidence
     - are all committed
   - and the audit surface definition says its purpose is to append authoritative audit and lineage truth for the real-time lane

3. owned outcome:
   - the owned outcome is audit truth that is no longer only appended inside the audit surface, but is now published and referenceable for downstream consumers and evidence surfaces
   - I want to keep that outcome distinct from archive preservation
   - the topic contract gives the publication boundary:
     - the audit topic
     - with the audit surface as producer
     - and downstream operational and evidence-consuming side of the network on the other side
   - the design authority also keeps by-ref evidence contracts authoritative
   - which means this path is not just send an audit event somewhere, but make audit truth available through explicit handoff surfaces and durable references

4. what the path carries:
   - this path carries the things needed to make audit publication useful and later reconstructable:
     - run identity
     - decision and action lineage
     - policy, bundle, config, and release identifiers
     - and the durable by-ref evidence surfaces that later consumers will follow rather than infer
   - that is grounded in two explicit laws
   - first, the design authority says every cross-plane output carries the policy, bundle, config, and release identifiers required for replay and audit
   - second, it says origin-offset and by-ref evidence contracts remain authoritative
   - so the publication and reference path is carrying more than audit message; it is carrying the traceable reference structure that lets later consumers use audit truth safely

5. broad route logic:
   - decision and action truth -> append-only audit truth -> audit-topic handoff -> downstream operational and evidence consumers -> durable audit refs and evidence surfaces
   - that broad route matters because it shows there is real post-append handoff boundary
   - the current wired system is not treating audit truth as trapped inside the audit surface
   - it is explicitly handed off and durably surfaced
   - but the path also keeps the ordering honest:
     - append-only audit truth comes first
     - publication and reference distribution happen after that
     - and durable evidence refs remain the authoritative thing being pointed to rather than replaced by the topic itself

6. logical design reading:
   - logically, this path shows that the platform treats audit exists and audit is consumable and referenceable as two different truth boundaries
   - that is strong `A`-level design signal
   - the system is not saying:
     - once the audit surface writes, later consumers can figure things out however they want
   - it is saying:
     - there is dedicated handoff from append-only audit truth into explicit audit publication and durable evidence and reference surfaces
   - that separation is visible in the docs themselves:
     - the audit surface is one component with one purpose
     - the archive writer is another with a different purpose
     - and the topic contract explicitly names the audit handoff rather than leaving downstream audit usage implicit

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired system
  - the publication side is concretely seated on the audit topic
   - the copied baseline wired graph shows:
     - the audit surface publishing lineage audit into that topic
     - the topic transported by MSK
     - and the downstream case and evidence-consuming side attached to that audit lane
   - the durable-reference side is concretely seated on the platform's pinned evidence substrate:
     - object storage remains the durable truth, evidence, and archive substrate
     - and by-ref evidence contracts remain authoritative
   - so this path is not merely conceptual
   - it has both named bus boundary and named durable evidence substrate

8. why the design looks like this:
   - the design looks like this because the platform wants the hot path to be explainable later and wants downstream operational work to consume audit truth, not guesses
   - the audit and lineage framing exists so important decisions can be reconstructed and explained later
   - the case escalation path explicitly begins from RTDL decision and audit outputs
   - and the cross-plane provenance law ensures those outputs carry the identity needed for replay and audit
   - so the current design is trying to guarantee that audit truth is not only written, but actually propagated in a form the rest of the platform can trust

9. what larger contracts are shaping this path:
   - several larger contracts shape it strongly
   - the topic continuity contract shapes where audit publication happens and who owns it:
     - the audit topic
     - the audit surface as producer
     - downstream operational and evidence consumers on the other side
   - the append-only truths law shapes what kind of audit truth may be published at all:
     - it must remain append-only
   - the by-ref evidence law shapes how later consumers are supposed to follow evidence:
     - by durable references, not by informal reconstruction
   - and the provenance law shapes what must survive the handoff:
     - policy, bundle, config, and release identifiers for replay and audit

10. trade-offs and constraints:
   - this path deliberately adds one more explicit boundary after audit append
   - that costs extra structure:
     - an audit topic contract
     - consumer ownership boundaries
     - durable evidence and reference surfaces
     - and provenance fields that must survive publication
   - but that cost buys something important:
     - later case-handling and evidence and reporting surfaces do not need to reverse-engineer audit history from raw runtime traces or from archive files alone
     - they can consume explicit audit handoff
   - the design is therefore choosing clear cross-plane ownership and reconstructability over simpler but blurrier model of append once and let everyone else scrape it

11. necessity test:
   - if this path is removed, the platform can still:
     - decide
     - act
     - append audit truth
     - and later archive event history
   - but it loses clean answer to:
     - how downstream operational work sees audit truth as an input
     - how evidence and reporting sinks consume audit truth
     - where durable audit references come from
     - and how downstream consumers avoid reconstructing the audit story from scattered internal stores
   - that would weaken `A` immediately, because reviewer could fairly say the system has audit append but no explicit owner for the distribution and durable referencing of that audit truth across planes
   - the docs themselves already imply that this handoff matters:
     - the audit path ends in durable refs and evidence
     - and the case path begins from RTDL decision and audit outputs

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for turning appended audit truth into consumable audit publication and durable references
   - intentionality claim:
     - the handoff is explicit:
       - named topic
       - named producer
       - downstream consumer side
       - named evidence laws
     - rather than left implicit
   - materialization claim:
     - the path is concretely seated in the audit topic plus object-storage-backed durable evidence surfaces
   - contract claim:
     - this path is governed by append-only truth, by-ref evidence, and provenance laws
   - constraint-awareness claim:
     - the platform already knows that downstream consumers must not invent their own audit truth, which is why the handoff boundary is explicitly owned

Plainly stated, the `Audit publication and durable reference path` exists to turn append-only audit truth into explicit downstream handoff and durable reference surface, and its current design shows that this boundary is deliberate, materially seated, and cross-plane governed rather than implicit.

The next path in this group is the `Immutable archive preservation path`.

## 2026-03-12 10:57:11 +00:00 - Path interrogation: `Immutable archive preservation path`

Before interrogating the path itself, I want to pin one important nuance:

the archive path has a target posture and a current wired posture, and for `A` I should interrogate the current wired posture honestly.

The broader authority and build-plan target says the archive corridor is meant to be a managed sink or connector to S3 lane, but the current adjudicated wired posture is an ECS MSK batch-consumer-to-S3 route with run-scope proof by object path plus payload readback. That is the object I want to explain in `A`, while still noting that the design intent was managed connector-style archive preservation with replay and offset continuity proof.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn runtime event history into durably preserved, immutable archive history that later replay, audit, and learning can trust
   - keep this path narrower than append-only audit truth and narrower than later replay-basis closure for learning input
   - answer where the platform preserves runtime events as immutable archive history and refs
   - the production-readiness definition states that the archive writer exists to durably preserve immutable event history and refs for replay and audit
   - and the run-process treats archive closure as distinct requirement of RTDL catch-up closure, not as side effect of RTDL being alive

2. entry:
   - the honest system-design entry is current-run runtime event history that the archive lane is responsible for preserving
   - that is the system-design answer
   - but the docs also show important proving nuance:
     - the archive cutover lane used control-topic probe records as bounded continuity proof
     - because the lane objective was archive sink cutover plus continuity proof, not full semantic proof of every upstream producer
   - so the system-design entry is runtime event history, while the cutover proof entry for validation was narrower probe source

3. owned outcome:
   - the owned outcome is immutable archived event history, under the platform's run-scoped archive surface, with continuity evidence that later consumers can resolve
   - that is narrower than replay-basis closure and narrower than later learning-input readiness
   - it closes when runtime history is durably preserved in archive objects under the run-scoped archive prefix, and the lane has enough continuity proof to claim that those objects actually correspond to the source records it was responsible for preserving
   - the current handles pin:
     - archive prefix as `archive/{platform_run_id}/events/`
     - and proof mode as object-path-plus-payload-readback

4. what the path carries:
   - this path carries:
     - runtime records to be preserved
     - run identity
     - continuity metadata
     - and enough payload and readback information to prove that what landed in object storage is the right run-scoped archive history
   - the current closure contract makes that explicit
   - the archive path is not just write files somewhere
   - it carries:
     - proof mode
     - source topic
     - starting-position rule
     - batch and window settings
     - and run-scope readback strategy
   - later learning-input closure depends on archive plus replay references being resolved from spine closure, which shows that archive history is not only retained for human inspection but also for later causal replay

5. broad route logic:
   - runtime or probe source records on MSK -> archive-consumer runtime -> object-storage archive prefix -> run-scoped archive objects with payload and readback continuity proof
   - that broad route matters because it makes archive preservation real handoff boundary, not just some component also wrote an object
   - the current wired route is explicitly bus-based, consumer-based, and object-store-targeted, with the archive sink prefix and proof mode pinned in the handles

6. logical design reading:
   - logically, this path shows that the platform treats immutable runtime history as different from both:
     - append-only audit truth
     - and later replay-basis selection for learning
   - that is strong `A`-level design signal
   - the system is not saying:
     - audit append is enough, and replay can infer history later
   - it is saying:
     - there is separate archive-preservation boundary whose job is to preserve immutable runtime history and refs in durable object storage
   - that separation is visible in the docs themselves:
     - the audit surface has one purpose
     - the archive writer has another
     - RTDL catch-up closure requires archive closure evidence
     - and later learning-input closure depends on archive plus replay references as input

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired system
   - the copied baseline wired graphs show:
     - a live `archive_writer` deployment in the RTDL namespace
     - the archive writer writing immutable history to the archive prefix
     - and the archive writer storing archive receipts in evidence
   - the durable archive substrate is object storage, with archive objects under `archive/{platform_run_id}/events/`
   - the current runtime handle set pins:
     - the archive connector mode
     - the source cluster
     - the source topic
     - the batch and window controls
     - and the run-scope proof mode
   - the live runtime truth also shows the archive writer as concrete RTDL workload, and later bounded proof notes record the archive writer as green while the rest of the RTDL diagnosis continued
   - that is strong `A`-style evidence that this path is materially present in the system, not only planned

8. why the design looks like this:
   - the design looks like this because the platform wanted managed, production-shaped archive sink with explicit continuity proof, but the exact runtime route had to be adjudicated through real constraints
   - the implementation trail is clear here
   - the lane tried:
     - Firehose with MSK source
     - then Lambda MSK event-source mapping
   - and both hit real blocker classes or service and runtime constraints
   - before the lane was closed green after repinning the current mode to ECS batch-consumer to S3
   - the objective did not change:
     - preserve run-scoped archive sink semantics
     - and preserve continuity proof
   - but the concrete runtime route did
   - that is why, for `A`, the right story is not only that the authority once wanted managed connector-to-S3
   - it is that the current wired archive path is the adjudicated route that kept the semantic objective intact under real constraints

9. what larger contracts are shaping this path:
   - several larger contracts shape it
   - the design authority says the archive writer is part of the audit and archive runtime posture and must preserve replay and offset continuity proof
   - the run-process says RTDL catch-up closure cannot close without archive-writer closure evidence and archive closure marker
   - then later learning-input closure says learning input cannot even begin until archive plus labels plus replay references are resolved from spine closure
   - so this path is shaped by:
     - archive preservation
     - closure evidence
     - and future replay-resolvability
     - all at once

10. trade-offs and constraints:
   - this path deliberately adds one more explicit truth boundary to the runtime side of the platform
   - that costs:
     - one more runtime consumer and sink lane
     - one more object-store continuity proof contract
     - and one more distinction the platform has to explain
   - it also forced uncomfortable but honest runtime choices
   - the lane did not get to declare green on Firehose because the MSK-source path was blocked
   - and it did not get to declare green on Lambda mapping when probe publication existed but no archive objects were produced
   - the lane stayed fail-closed until the current route could actually show probe-to-sink continuity
   - that is very strong design signal, because it means the archive boundary was treated as real rather than decorative

11. necessity test:
   - if this path is removed, the platform can still:
     - ingest traffic
     - make decisions
     - emit actions
     - append audit truth
     - and even produce later governance bundles
   - but it loses clean answer to:
     - where immutable runtime history is preserved
     - what object-backed archive later replay should depend on
     - how replay and offset continuity is grounded
     - and whether later learning input is built on actual archived runtime truth or inferred fragments
   - that would weaken `A` immediately, because reviewer could fairly say the platform has runtime behavior and audit append, but no explicit owner for the immutable event history that later replay and audit rely on
   - the docs themselves make that dependency explicit by requiring archive closure at RTDL catch-up closure and replay references at learning-input closure

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for preserving immutable runtime history for replay and audit
   - intentionality claim:
     - archive preservation is named closure requirement with its own continuity proof, not accidental object-store side effect
   - materialization claim:
     - the path is concretely seated in archive prefixes, pinned connector and runtime handles, and a live archive-writer workload
   - contract claim:
     - the path is governed by archive closure evidence, replay-reference expectations, and run-scope readback proof
   - constraint-awareness claim:
     - the current wired route is the result of fail-closed runtime adjudication across multiple attempted sink modes, not casual implementation detail
   - material participation evidence:
     - the archive cutover lane only closed green after probe-to-sink continuity closure under the run-scoped archive prefix
     - and later richer RTDL proof notes still recorded the archive writer as green while diagnosing other components
     - that is not full readiness claim for the whole path
     - but it is strong evidence that the boundary is live, instrumented, and doing real work in the current wired platform

Plainly stated, the `Immutable archive preservation path` exists to turn runtime event history into durable, run-scoped archive truth for replay and audit, and its current design shows that this boundary is deliberate, materially seated, and continuity-aware rather than implicit.

The next path in this group is the `Archive closure and replay-reference path`.

## 2026-03-12 11:03:27 +00:00 - Path interrogation: `Archive closure and replay-reference path`

This path exists to turn preserved archive history into closure-complete, replay-referenceable archive truth. The previous path preserved immutable runtime history under the run-scoped archive surface. This path answers the next question: when does that preserved history become formally closed enough that later replay and learning can rely on it? The run-process makes that boundary explicit in two places. RTDL catch-up closure is not allowed to close without archive-writer closure evidence, and its commit evidence must include an archive closure marker. Then learning-input closure is not allowed to start until archive, labels, and replay references are resolved from spine closure.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn preserved archive history into closure-complete, replay-referenceable archive truth
   - keep this path narrower than the full learning-input basis and narrower than later OFS dataset construction
   - answer when preserved archive history becomes formally closed enough that later replay and learning can rely on it

2. entry:
   - the entry is not raw runtime events anymore, and it is not merely that some archive objects exist
   - the entry is run-scoped archived runtime history plus the continuity metadata needed to prove that this archive surface is the one later lanes should trust
   - that is why the archive connector handles pin not just the object-store prefix, but also the source topic, starting position, proof mode, and probe mode
   - the current closure contract expects archive history under `archive/{platform_run_id}/events/`
   - and uses object-path-plus-payload-readback as the run-scope proof mode

3. owned outcome:
   - the owned outcome is closed archive surface for the run, with replay-reference continuity explicit enough that downstream learning-input closure can bind to it
   - this path stops once archive truth is closure-complete and replay-referenceable
   - the run-process supports that separation:
     - RTDL catch-up closure closes on the archive closure marker
     - while learning-input closure later consumes archive plus replay references as part of learning-input readiness

4. what the path carries:
   - this path carries:
     - the run-scoped archive object set
     - the continuity proof that ties the archive sink back to its source records
     - the archive closure marker
     - and the replay-reference semantics that later lanes will read as source-offset ranges
   - those semantics are not left implicit
  - the run-process says replay basis at learning-input closure must be pinned as source-offset ranges with explicit mode-aware meaning
   - and the handles registry separately pins the archive connector's proof mode as object-path-plus-payload-readback

5. broad route logic:
   - run-scoped archive objects plus continuity proof -> archive closure marker -> replay-reference resolution from spine closure -> downstream learning-input lane can trust the archive basis
   - that broad route matters because it shows the platform is not satisfied with archive exists
   - it wants second truth boundary:
     - archive exists
     - then archive is closure-complete and referenceable for replay
   - that distinction is exactly what the RTDL catch-up closure and learning-input closure split is doing

6. logical design reading:
   - logically, this path shows that the platform treats archive preservation and archive usability for replay as different owned truths
   - that is strong `A`-level design signal
   - the system is not saying:
     - once objects land in object storage, later replay can figure it out
   - it is saying:
     - there is explicit closure boundary where archive history becomes replay-referenceable
     - and later learning is blocked until that boundary is satisfied

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired platform
   - the archive surface is concretely pinned to `archive/{platform_run_id}/events/`
   - the current runtime contract for the archive lane is pinned to ECS batch-consumer-to-object-storage posture
  - with the control topic as the source topic
   - a run-scope proof mode of object-path-plus-payload-readback
   - and explicit probe emit mode using ECS MSK producer task
   - the current archive cutover closure says this lane only closed green after probe-to-sink continuity closure, where admitted probe ids were present in the run-scoped archive objects

8. why the design looks like this:
   - the design looks like this because the platform refused to equate archive sink wrote objects with archive closure is trustworthy
   - the run-process requires archive-writer closure evidence at RTDL catch-up closure, not just activity
   - the later learning-input gate requires archive plus replay references to be resolved from spine closure, not guessed from whatever files happen to be present
   - and the archive cutover closure shows the same attitude in implementation:
     - the lane stayed fail-closed until it could prove probe-to-sink continuity under the run-scoped archive prefix

9. what larger contracts are shaping this path:
   - three larger contracts shape this path strongly
   - the run-process closure law shapes it through RTDL catch-up closure:
     - archive-writer closure evidence must be present
     - and the commit evidence must include archive closure marker
   - the learning-input law shapes it through learning-input closure:
     - replay basis must be pinned as source-offset ranges with explicit mode-aware semantics
     - and learning cannot start until archive, labels, and replay references are resolved from spine closure
   - the archive connector contract shapes it concretely through the handles:
     - run-scoped archive prefix
     - proof mode
     - source topic
     - and consumer settings are all pinned rather than left to runtime discovery

10. trade-offs and constraints:
   - this path deliberately adds another explicit truth boundary after archive writing
   - that costs more ceremony:
     - closure evidence
     - closure marker semantics
     - replay-reference semantics
     - and clear distinction between preserved history and replay-ready history
   - but that cost buys something important:
     - later learning and replay lanes do not need to infer their basis from ad hoc object inspection
     - they can depend on named closure outcome
   - the current archive cutover closure makes this especially clear:
     - the lane did not go green merely because sink existed
     - it went green after runtime-path adjudication and probe-to-sink continuity closure

11. necessity test:
   - if this path is removed, the platform can still:
     - preserve archive objects
     - append audit truth
     - and later attempt replay or learning
   - but it loses clean answer to:
     - when the archive became closure-complete
     - which replay references later lanes should trust
     - whether replay basis came from spine closure or from informal guess
     - and whether learning-input closure is anchored to true archive basis or only to object presence
   - that would weaken `A` immediately, because reviewer could fairly say the platform preserves runtime history but has no explicit owner for turning that history into replay-referenceable basis
   - the run-process itself rejects that looseness by making archive closure and replay-reference resolution formal gates

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for turning preserved archive history into replay-referenceable closure truth
   - intentionality claim:
     - replay references are not inferred opportunistically
     - they are resolved from spine closure under explicit gate semantics
   - materialization claim:
     - the path is concretely seated in the run-scoped archive prefix, the pinned archive connector contract, and the archive-closure marker requirement
   - contract claim:
     - this path is governed by archive-closure rules, replay-basis rules, and mode-aware source-offset semantics
   - constraint-awareness claim:
     - the current wired route only counts as closed when continuity proof is explicit
     - which is why the archive cutover lane was pinned to probe-to-sink continuity rather than vague archive looks okay posture

Plainly stated, the `Archive closure and replay-reference path` exists to turn preserved archive history into formally closed, replay-referenceable basis for later learning and replay, and its current design shows that this boundary is deliberate, materially seated, and continuity-aware rather than implicit.

That finishes the per-path interrogation for Group 4.

## 2026-03-12 09:49:59 +00:00 - Path interrogation: `Entity and relationship projection path`

This path exists to turn admitted live platform data into current entity and relationship truth that the rest of RTDL can trust. Its job is not yet to build joined context, not yet to materialize online features, and not yet to make decision. Its job is narrower and more foundational: take the incoming platform data and maintain current identity and entity graph whose state is good enough that downstream context and decision truth are not built on guesswork. The RTDL framing makes that explicit by giving the identity and entity graph surface its own purpose: build identity and entity relationship state from the incoming platform data, and by saying downstream decision truth is polluted if that graph is wrong.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn admitted live platform data into current entity and relationship truth that the rest of RTDL can trust
   - keep this path narrower than joined context, online features, or decisioning
   - ensure downstream context and decision truth are not built on guesswork about relationships

2. entry:
   - the entry to this path is not raw engine output in general
   - it is the admitted traffic and context family already published onto the platform bus from Group 2
   - in the current wired system, that family is concretely split into:
     - the fraud traffic topic
     - arrival-events context
     - arrival-entities context
     - flow-anchor context
   - that split is consistent with the runtime data law:
     - only the live-runtime-allowed oracle surfaces are permitted in runtime
     - truth-only and future-implying surfaces are forbidden from live use
   - the handles registry pins exactly four live-runtime-allowed oracle outputs for runtime:
     - `s3_event_stream_with_fraud_6B`
     - `arrival_events_5B`
     - `s1_arrival_entities_6B`
     - `s3_flow_anchor_with_fraud_6B`

3. owned outcome:
   - the owned outcome of this path is current entity and relationship projection truth for the active run
   - that means this path closes when RTDL has more than raw events
   - it now has graph and projection state that downstream context formation can read as authoritative current surface
   - the broader run-process supports this split because RTDL catch-up closure requires inlet and projection closure as part of its pass gate before the decision chain is even allowed to count as committed
   - and in the current operator surfaces, the entity and graph layer is not treated as black box; it exposes distinct graph-oriented status surface with fields like `graph_version`, checkpoint age, and apply state, which shows this path closes on its own projection truth rather than being just pass-through feed

4. what the path carries:
   - this path carries the minimum things needed to mutate entity and relationship state deterministically:
     - admitted traffic and context events
     - the identity and relationship references inside those events
     - event-time ordering surfaces
     - run-scoped correlation
     - and the platform's rules about which source families are allowed in runtime
   - it is also shaped by the later semantic-hardening work pinned for `A`
   - that work says entity relationship posture must be pinned from observed data behavior such as:
     - joinability
     - key stability
     - late-arrival behavior
   - rather than schema-only assumptions
   - that is important because it tells us this path is not just syntactic projection
   - it is meant to carry enough meaning to support real relationship state

5. broad route logic:
   - admitted traffic and context topics -> RTDL runtime -> entity and graph update logic -> current graph and projection state -> downstream-readable projection truth
   - that broad route matters because it shows the platform is not treating entity truth as something pre-baked into the event payload
   - the event bus hands off the admitted event family, the RTDL runtime consumes it, and the entity and graph layer constructs relationship state inside the platform
   - that route is also concretely bounded by the platform's topic and runtime contracts rather than being implied in-memory continuation

6. logical design reading:
   - logically, this path shows that the platform treats entity truth as something it computes and owns, not something it merely receives
   - that is one of the strongest `A`-level design signals in this group
   - the platform is not saying:
     - the schema already tells us what the entity relationships are
   - it is saying:
     - relationship posture has to be earned from observed data behavior and then projected into current runtime graph
   - that is exactly why the semantic-hardening work included entity-map candidate hypotheses and why the posture explicitly says entity relationship posture must be pinned from observed data behavior, not schema assumptions
   - this makes the path clearly intentional rather than accidental

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired system
   - in the copied baseline wired graphs, the path is seated across:
     - the admitted traffic and context topics on the event bus
     - the RTDL namespace and worker surfaces
     - the entity and graph and feature surfaces
     - and the state stores those surfaces write into
   - concretely, the copied baseline graphs show:
     - the traffic and context topics consumed by the RTDL runtime
     - the RTDL namespace running the context, entity and graph, and feature components
     - and the entity and feature state being written into Aurora
   - the handles registry also pins the RTDL consumer group and commit policy:
     - one RTDL consumer group
     - commit after durable write
   - that means this path is not only conceptually stream-based; it is concretely realized as event-bus intake plus RTDL worker surfaces plus durable state seating
   - the broader repo authority also declares managed Flink runtime surfaces for RTDL stream processing, but in this notebook's copied baseline wired view those managed surfaces are retained rather than the primary reader-facing active output path

8. why the design looks like this:
   - the design looks like this because the platform deliberately chose to make entity and relationship projection first-class RTDL responsibility instead of scattering projection work across generic services or assuming relationships from schema alone
   - two design choices stand out
   - first, the path is intentionally seated inside the RTDL runtime and store topology rather than hidden inside downstream context builders
   - second, the semantic-hardening posture explicitly says entity relationship posture must be pinned from observed data behavior rather than schema-only assumptions
   - so the current path shape is not random implementation convenience
   - it is consciously chosen runtime projection design with explicit semantic discipline

9. what larger contracts are shaping this path:
   - several larger contracts shape this path strongly
   - the runtime data contract says live runtime may use only the four allowed oracle output families, while truth-only outputs and future-implying fields are forbidden
   - that constrains what this path is allowed to project from
   - the semantic-hardening posture then says entity relationship posture must be based on observed data behavior, not schema-only assumptions
   - and the run-process says RTDL projection closure must be real enough to contribute to RTDL catch-up closure
   - so this path sits under combination of runtime data law, semantic realism law, and RTDL closure law

10. trade-offs and constraints:
   - this path deliberately accepts structure and discipline in exchange for cleaner runtime truth
   - it would be easier to:
     - collapse entity logic into downstream context builders
     - assume schema-level relationships
     - or scatter this work across loosely governed services
   - but the current design rejects that
   - it chooses:
     - one active RTDL runtime posture
     - explicit runtime-allowed source families
     - explicit downstream dependence on projection correctness
   - that adds discipline and constrains shortcuts, but it buys much clearer claim:
     - entity truth is constructed intentionally inside RTDL
   - it also means the path inherits stream-runtime constraints such as checkpoint behavior, lag posture, and replay safety rather than being able to hide behind vague eventual-consistency language

11. necessity test:
   - if this path is removed, the platform can still ingest traffic, still publish to the bus, and still draw downstream boxes like context formation, feature readiness, and decisioning
   - but it loses clean answer to:
     - where current entity truth comes from
     - how relationship state is formed
     - what downstream context is anchored on
     - and why later decision truth should be trusted
   - that is exactly why the entity and graph purpose statement matters so much:
     - if the entity and graph layer is wrong, entity truth becomes unreliable and every downstream decision is polluted
   - without this path, the rest of RTDL starts to look like decision system built on unowned relationship assumptions
   - that would weaken `A` immediately

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for building current entity and relationship truth from admitted live data
   - intentionality claim:
     - that truth is constructed in dedicated RTDL projection lane, not left implicit in raw events or schema assumptions
   - materialization claim:
     - the path is concretely seated in the event bus, the RTDL runtime surfaces, the RTDL consumer group and commit policy, and the durable state stores behind projection truth
   - contract claim:
     - the path is constrained by runtime-allowed output families, no-future rules, and observed-data entity-mapping posture
   - constraint-awareness claim:
     - the system knowingly avoids schema-only convenience and keeps projection state as first-class runtime responsibility

Plainly stated, the `Entity and relationship projection path` exists to turn admitted platform events into current graph truth that the rest of RTDL can stand on, and its current design shows that this is deliberate, materially seated, and semantically constrained rather than hand-wavy.

The next clean move is the `Joined context formation path`.

## 2026-03-12 10:02:49 +00:00 - Path interrogation: `Joined context formation path`

This path exists to turn admitted live traffic plus the already projected runtime state into joined context surface that the rest of RTDL can actually use. Its job is not yet to materialize online features, not yet to choose decision posture, and not yet to emit decision. Its narrower job is to answer:

Does the platform now understand enough about this event, in the right time-safe way, to let downstream runtime continue honestly?

The RTDL definition makes that boundary explicit by giving the context-store and flow-binding surface its own purpose:

- create the joined context surface the downstream RTDL graph depends on

while forbidding false-ready from partial or mis-scoped context and forbidding silent missing-context drift from masquerading as later decision problem.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn admitted live traffic plus already projected runtime state into joined context surface that the rest of RTDL can actually use
   - keep this path narrower than feature readiness, decision posture, or decision emission
   - answer whether the platform now understands enough about this event, in the right time-safe way, to let downstream runtime continue honestly

2. entry:
   - the entry is not raw oracle data in general, and it is not raw engine traffic alone
   - the entry is the admitted event family already handed off to the runtime bus from Group 2, interpreted through the platform's pinned join posture
   - the engine interface says:
     - traffic is intentionally thin
     - joins occur inside the platform
     - the relevant time-safe context surfaces for RTDL are `arrival_events_5B`, `s1_arrival_entities_6B`, and the flow-anchor surfaces
   - it also gives the binding join map:
     - event stream to flow anchor
     - flow anchor to arrival skeleton
     - arrival skeleton to entity attachments
   - in the current wired posture, the live-runtime-allowed oracle output set is pinned to exactly four surfaces:
     - `s3_event_stream_with_fraud_6B`
     - `arrival_events_5B`
     - `s1_arrival_entities_6B`
     - `s3_flow_anchor_with_fraud_6B`

3. owned outcome:
   - the owned outcome is joined, time-safe runtime context surface with honest readiness posture for downstream RTDL consumers
   - that outcome is intentionally narrower than features are ready and narrower than decision was formed
   - it closes when the platform has bound the admitted event into the right arrival, flow, and entity context and can expose that context truthfully to the next RTDL boundaries
   - that is why the RTDL readiness framing gives joined-context creation its own component purpose and its own failure semantics
   - and why the run-process later treats inlet and projection closure as part of RTDL catch-up closure before the decision chain is allowed to count as committed

4. what the path carries:
   - this path carries the objects needed to bind one admitted runtime event into usable context:
     - the admitted behavioural stream event
     - the flow-anchor context for that flow
     - the arrival skeleton for routing, timezone, and arrival context
     - the arrival-entity attachments
     - and the current entity and relationship projection state produced by the previous path
   - it is also constrained by role and join correctness:
     - the RTDL docs explicitly require correct role references
     - forbid false-ready from partial or mis-scoped joins
     - and the interface contract forbids inferring semantics from physical file order and binds joins to declared keys only

5. broad route logic:
   - admitted event family on the runtime bus -> consume traffic plus allowed context surfaces -> bind them through the pinned join map and current projection state -> expose joined runtime context and readiness truth to the downstream RTDL graph
   - that broad route matters because it shows that context is not assumed to be pre-baked into the event payload
   - the engine contract is explicit that traffic stays thin and joins happen inside the platform
   - and the RTDL framing is explicit that joined context is its own distinct boundary question inside the plane

6. logical design reading:
   - logically, this path shows that the platform treats context as constructed runtime truth, not as accidental by-product of ingestion and not as something decisioning should just figure out later
   - that is strong `A`-level design signal
   - the design is saying:
     - admitted traffic alone is not enough
     - the system must deliberately bind flow-level, arrival-level, and entity-level context into joined surface
     - and it must do so honestly enough that downstream components are not fooled by partial or stale context
   - that is exactly why the RTDL docs emphasize false-ready, missing-context drift, role-reference correctness, and fanout bounds at this boundary

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired system
   - in the copied baseline wired graphs, the path is seated across:
     - the admitted traffic and context topics on the runtime bus
     - the RTDL namespace and worker surfaces
     - the context-store and flow-binding surface
     - and the downstream handoff from that context surface into the entity and graph and feature surfaces
   - concretely, the copied baseline graphs show:
     - the traffic topic consumed by the context-store and flow-binding surface
     - the arrival-events, arrival-entities, and flow-anchor context topics consumed by that same surface
     - the RTDL namespace running the context-store and flow-binding component
     - and the joined context being projected onward to the entity and graph and feature components
   - that means joined-context formation is not just conceptual logic
   - it is concretely realized as event-bus intake plus RTDL worker surface plus downstream context handoff
   - the broader repo authority also declares managed stream-processing surfaces for RTDL, but in this notebook's copied baseline wired view those are retained surfaces rather than the primary reader-facing active output path

8. why the design looks like this:
   - the design looks like this because the platform deliberately chose thin-traffic, in-platform-join posture
   - it rejected the easier alternatives:
     - putting too much context into the traffic payload
     - using batch-only or future-implying fields like `session_end_utc` or `arrival_count`
     - or collapsing context truth into downstream feature or decision logic
   - instead, the interface contract pins time-safe context surfaces and binding join map
   - while the RTDL framing pins joined-context creation as its own truth boundary with its own false-ready discipline
   - so the current shape exists because the platform is trying to keep traffic thin, context explicit, and timing semantics honest

9. what larger contracts are shaping this path:
   - several larger contracts shape this path strongly
   - the engine interface shapes the semantic side:
     - only behavioural streams are traffic
     - joins occur inside the platform
     - only time-safe context surfaces may be used in RTDL
     - batch-only truth products and future-implying fields are forbidden for live decisions
   - the run-process shapes the closure side by giving RTDL inlet and projection closure explicit phase boundary in RTDL catch-up closure
   - and the RTDL plan shapes the observability side by treating false-ready, join completeness, unmatched joins, and fanout bounds as key proof surfaces for this boundary

10. trade-offs and constraints:
   - this path deliberately chooses more structure in exchange for cleaner runtime truth
   - it would be easier to flatten more context into the event, or to let downstream components infer missing context opportunistically
   - but the current design rejects that, because it would blur the truth boundary and make later errors hard to interpret
   - the cost of the chosen design is:
     - more explicit join discipline
     - more state and projection dependence
     - stricter readiness semantics
   - it also forbids apparently convenient inputs like `s1_session_index_6B` in live runtime, because those fields imply future knowledge and would corrupt temporal correctness

11. necessity test:
   - if this path is removed, the platform can still ingest traffic, still maintain entity projection, and still draw later boxes like online feature readiness, decision guardrail, and decision formation
   - but it loses clean answer to:
     - how admitted event becomes the specific runtime context downstream components actually consume
     - whether the flow, arrival, and entity bindings are complete
     - whether ready means full context or only partial context
     - and whether missing context is context problem or decision problem
   - that is exactly why this path matters:
     - without it, the rest of RTDL would start looking like decision system built on unowned or implicit context assumptions
   - that would weaken `A` immediately

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for creating joined runtime context surface before feature or decision work begins
   - intentionality claim:
     - context is built from thin traffic plus explicit time-safe join surfaces using pinned join map, not by accident or by payload bloat
   - materialization claim:
     - the path is concretely seated in the runtime bus topics, the RTDL namespace and context-store surface, the downstream handoff into the entity and graph and feature surfaces, and the RTDL catch-up phase boundary
   - contract claim:
     - the path is constrained by the live-runtime-allowed output set, no-future rules, and join-key discipline
   - quantified closure claim:
     - the current runtime context boundary is built from bounded four-surface live-runtime set rather than unbounded or hand-wavy source world

Plainly stated, the `Joined context formation path` exists to turn admitted thin traffic plus current projection state into honest, time-safe runtime context surface, and its current design shows that this is deliberate, materially seated, and semantically governed rather than implicit.

The next clean move is the `Online feature readiness path`.

## 2026-03-12 10:07:16 +00:00 - Path interrogation: `Online feature readiness path`

This path exists to turn already joined runtime context into online feature state that the live decision path can actually use. Its job is not to decide, not to guardrail, and not to append audit truth. Its narrower job is to answer:

Does the platform now have usable feature truth for this event, with honest readiness and freshness semantics, rather than merely having upstream data somewhere?

The RTDL component framing says this directly: the online feature plane exists to materialize online feature state for the live decision path, and it is the place where the data exists becomes the decision can actually use it.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn already joined runtime context into online feature state that the live decision path can actually use
   - keep this path narrower than decisioning, guardrail posture, or audit truth
   - answer whether the platform now has usable feature truth for this event with honest readiness and freshness semantics

2. entry:
   - the entry is not raw source data and not traffic alone
   - for this interrogation, the entry is the event and context state already bound by the earlier RTDL paths:
     - admitted behavioural traffic
     - joined context
     - current entity and relationship state
   - all of that sits under the runtime data contract that keeps traffic thin and requires context to be joined inside the platform
   - the engine interface pins the allowed runtime semantic world tightly:
     - `behavioural_streams` are the traffic side
     - `arrival_events_5B`, `s1_arrival_entities_6B`, and flow-anchor outputs are context and join surfaces
     - `s4_*` truth products are not live runtime inputs
   - the current wired runtime handle set mirrors that by pinning the active required output scope to exactly four oracle outputs:
     - `s3_event_stream_with_fraud_6B`
     - `arrival_events_5B`
     - `s1_arrival_entities_6B`
     - `s3_flow_anchor_with_fraud_6B`

3. owned outcome:
   - the owned outcome of this path is feature-ready runtime truth
   - that means the platform can now say:
     - which feature groups are available for this event
     - whether freshness and readiness are real
     - and whether missing features are truly missing rather than key-shape or partial-coverage artifact
   - that is why the online feature plane is separate path and not just late step inside decision formation
   - the docs are explicit that this boundary must not let:
     - partial key coverage masquerade as total feature absence
     - freshness truth stay implicit
     - stale feature serving count as healthy
     - or fresh state be declared only because the platform forgot older events

4. what the path carries:
   - this path carries more than raw feature values
   - it carries:
     - lookup keys
     - current projection state
     - feature-group request semantics
     - and the freshness and readiness posture that downstream decisioning will rely on
   - the runtime evidence shows that this is not theoretical
   - the seam between the online feature plane and decisioning was sensitive to:
     - graph-version shape
     - and feature-request key shape
   - one live diagnosis showed disagreement because graph-version came back in shape that downstream resolution did not accept
   - another narrowed warning noise to redundant `event_id:*` requests when the projector already keyed traffic by `flow_id` first
   - that tells us this path carries explicit boundary contracts, not just data blobs

5. broad route logic:
   - joined runtime context + current entity and relationship state -> online feature materialization and serve surface -> feature-ready truth for the live decision path
   - the design is therefore not context exists, so decisions can happen
   - it is:
     - context must be transformed into feature state
     - and that transformation has its own owned boundary
   - the RTDL path framing already distinguishes context formation from the later decision path, and the runtime authority pins a distinct feature boundary rather than burying it inside generic decision worker

6. logical design reading:
   - logically, this path shows that the platform treats feature truth as different from context truth
   - that is strong `A`-level design signal
   - the system is not saying once context exists, the decision can use it
   - it is saying there is separate boundary where context becomes feature-ready state, and that boundary must be honest about availability, freshness, and missingness
   - that is exactly why the online feature section focuses on:
     - required feature-group availability
     - freshness truth
     - and false missing-feature posture
   - as distinct concerns

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired platform
   - in the copied baseline wired graphs, the path is seated across:
     - the runtime bus topics feeding RTDL
     - the RTDL namespace and worker surfaces
     - the online feature surface itself
     - the shared RTDL state stores
     - and the downstream handoff into the later decision boundary
   - concretely, the copied baseline graphs show:
     - the online feature surface running in the RTDL namespace
     - joined context being projected onward from the context boundary into the online feature and entity surfaces
     - and online feature state being written into Aurora, with a handle-based read seam to Redis
   - the broader repo authority also declares managed stream-processing surfaces for RTDL feature materialization, but in this notebook's copied baseline wired view those managed surfaces remain retained rather than the primary reader-facing active output path
   - this path is therefore not some logic in the middle
   - it is visible as distinct feature-serving and readiness surface with its own live counters such as applied events, missing-feature signals, snapshot failures, and checkpoint age

8. why the design looks like this:
   - the design looks like this because the platform deliberately chose to make feature state explicit rather than leaving it implicit inside downstream code
   - it also pins feature engineering to observed data behavior rather than schema-only assumptions
   - and when feature defects appeared, they were handled as explicit contract seams:
     - graph-version payload shape
     - requester and projector key-shape alignment
     - missing-key telemetry
   - rather than being hidden behind vague feature red language
   - that is the opposite of accidental design

9. what larger contracts are shaping this path:
   - this path is shaped by three larger contracts
   - first, the data-engine contract keeps traffic thin and forces the platform to join context internally rather than smuggling truth into the payload
   - second, the runtime and learning separation contract forbids truth-product leakage and future-only fields from live runtime surfaces:
     - the runtime path is explicitly past and present only
     - and `s4_*` truth products are learning-only
   - third, the RTDL component law says the online feature plane must be semantically correct, time-correct, replay-safe, and observable
   - that means freshness, checkpoint age, restart behavior, and missing-feature truth are all part of the boundary, not optional diagnostics

10. trade-offs and constraints:
   - this path deliberately adds one more explicit boundary to the RTDL graph
   - that costs:
     - more state
     - more health and readiness surface
     - and more requester and projector contract edges
   - but it buys something important:
     - the system can distinguish context exists from features are truly usable
     - and can tell whether a red posture is coming from:
       - actual missing feature state
       - freshness issues
       - or contract-shape mismatch like the graph-version or redundant-key seam already found
   - that is meaningful trade-off:
     - more boundary discipline in exchange for less semantic ambiguity

11. necessity test:
   - if this path is removed, the platform can still ingest traffic, still build joined context, and still draw boxes called decision guardrail and decision formation
   - but it loses clean answer to crucial runtime questions:
     - are the required features actually present
     - are they fresh enough
     - is missing real, or just partial key coverage
     - is decisioning failing because inputs are insufficient, or because the online feature plane never made the feature state usable
   - without this path, decisioning would sit on top of unowned feature boundary
   - that would weaken `A` immediately, because reviewer could fairly say the system has context and decisions but no explicit owner for the thing that connects them

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for turning context into usable feature state
   - intentionality claim:
     - the online feature plane is not accident of downstream code; it is named, contract-governed boundary
   - materialization claim:
     - the path is concretely seated in the runtime bus, the RTDL namespace and online feature surface, the bounded four-surface runtime oracle set, the shared state stores, and the live feature-readiness counters
   - contract claim:
     - the path is governed by thin-traffic semantics, no-future and runtime-truth separation, and explicit requester and projector compatibility
   - constraint-awareness claim:
     - the design already knows this boundary can fail semantically even when the rest of RTDL looks alive, which is why missing-feature truth and key-shape and graph-version seams are surfaced rather than hidden
   - material participation signal:
     - not as readiness proof yet, but as participation proof
     - the online feature surface is visibly processing current-run events and exposing missing-feature, snapshot-failure, and checkpoint-age signals as first-class surfaces rather than hand-waving feature state away

Plainly stated, the `Online feature readiness path` exists to turn joined runtime context into feature state that the live decision path can honestly use, and its current design shows that this boundary is deliberate, materially seated, and contract-governed rather than implicit.

The next clean move is the `Decision guardrail path`.

## 2026-03-12 10:08:43 +00:00 - Path interrogation: `Decision guardrail path`

This path exists to turn upstream RTDL state into decision posture that is safe to act on. Its job is not to build context, not to materialize features, and not to produce the decision itself. Its narrower job is to answer:

Given the current dependency and health posture of the RTDL graph, should the platform proceed normally, hold back, or fail closed?

The RTDL definition makes that boundary explicit: the degrade ladder exists to adjudicate runtime health and dependency posture for decisioning, and it matters because if that guardrail is wrong, the platform either makes unsafe decisions or blocks good traffic for the wrong reason.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn upstream RTDL state into decision posture that is safe to act on
   - keep this path narrower than context formation, feature readiness, or decision formation itself
   - answer whether the platform should proceed normally, hold back, or fail closed given the current dependency and health posture

2. entry:
   - the entry is not raw traffic and not raw context alone
   - the entry is the current RTDL truth surfaces that decisioning depends on:
     - joined-context readiness
     - feature readiness and freshness
     - projection health
     - checkpoint age
     - required-signal health
     - and run-scoped component participation
   - the RTDL telemetry and proof posture is explicit that the plane should expose exactly those kinds of things:
     - feature freshness and feature-ready counters
     - degrade-reason breakdown
     - run-scope adoption in every RTDL worker
     - and early fail-fast triggers when feature readiness stays dark or fail-closed spikes from an otherwise healthy upstream window

3. owned outcome:
   - the owned outcome is adjudicated decision mode for the current run and current event posture
   - in other words, this path must produce trustworthy answer to whether downstream decisioning should proceed under normal conditions or treat the current posture as insufficiently trusted
   - the docs show that this is real owned boundary rather than vague mood signal
   - in bounded proofs, the guardrail has emitted concrete posture such as:
     - `decision_mode = NORMAL` with required signals `OK`
     - and in other coupled proofs it has flipped to `FAIL_CLOSED` with explicit reason like `required_signal_gap:ofp_health`
   - that means the path closes on guardrail judgment, not merely on the existence of upstream component health artifacts

4. what the path carries:
   - this path carries the signals that determine whether decisioning is trustworthy enough to continue:
     - required-signal health from upstream RTDL components
     - checkpoint and freshness posture
     - dependency-availability posture
     - run-scoped component participation
     - and the reasons why component is healthy, advisory, stale, or insufficient
   - the implementation trail shows why this matters
   - in one bounded proof, the entity and feature surfaces could be actively processing the current run while still surfacing replay-era watermark advisories, and the guardrail remained `NORMAL` with required signals `OK`
   - in another proof, the guardrail flipped to `FAIL_CLOSED` on `required_signal_gap:ofp_health`
   - so this path is clearly carrying more than binary health pings; it is carrying typed dependency posture that has to be interpreted correctly

5. broad route logic:
   - current RTDL context, feature, and dependency signals -> guardrail classification logic -> decision posture truth -> downstream decision formation consumes that posture
   - that broad route matters because it separates what upstream surfaces say from what the platform is allowed to do next
   - the design is not saying that decision formation should infer trustworthiness for itself from every upstream symptom
   - it is saying there is dedicated guardrail boundary between feature and context truth and actual decision formation

6. logical design reading:
   - logically, this path shows that the platform treats degrade and insufficiency judgment as first-class runtime truth, not as side effect of decision formation
   - that is strong `A`-level design signal
   - the system is not saying:
     - if the feature or entity surfaces look odd, decisioning will just figure it out
   - it is saying:
     - there is dedicated guardrail that distinguishes true dependency outage from semantic-quality advisory and benign lag
     - and only fails closed when the runtime really lacks sufficient trusted inputs
   - that is exactly the distinction the guardrail definition insists on

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired system
   - the copied baseline wired graphs show active degrade-ladder deployment alongside the context, entity, feature, decision, action, and audit surfaces inside the RTDL namespace
   - they also show the downstream handoff:
     - the degrade ladder hands adjudication input to the decision surface
   - the handles registry keeps an explicit runtime deployment reference for the degrade-ladder surface
   - so the guardrail is not conceptual box only
   - it is concrete runtime workload in the live RTDL plane

8. why the design looks like this:
   - the design looks like this because the platform deliberately refuses to let raw component health or stale artifacts decide the safety posture directly
   - the implementation trail gives strong examples
   - when replay-era watermark signals made projector health look red even while current-run mutation and checkpoints were healthy, the fix was not to treat all red surfaces as hard failure
   - the guardrail recovered to `NORMAL` with required signals `OK`
   - later, when coupled proof genuinely hit `required_signal_gap:ofp_health`, the guardrail flipped to `FAIL_CLOSED` and the blocker was treated as real
   - that is exactly the behavior wanted from guardrail:
     - advisories stay advisories
     - insufficiency becomes fail-closed
     - and the distinction is explicit

9. what larger contracts are shaping this path:
   - this path is shaped by the larger RTDL contract, not by local convenience
   - the RTDL production-readiness definition says each component must be semantically correct, time-correct, replay-safe, observable, and explainable
   - for the guardrail specifically, that becomes very specific contract:
     - it must distinguish outage from advisory
     - fail closed only on real insufficiency
     - avoid sticky false-red from stale artifacts
     - and recover promptly when dependencies recover
   - the RTDL proof plan then turns that into concrete focus metrics such as false fail-closed rate and degrade-reason breakdown

10. trade-offs and constraints:
   - this path deliberately adds another explicit boundary to the RTDL graph
   - that costs complexity, because now the system has to maintain and explain:
     - upstream health semantics
     - the guardrail's own classification logic
     - and the difference between upstream red artifact and true decision-blocking insufficiency
   - but that complexity buys something important:
     - decision formation no longer has to invent its own safety posture from scattered upstream clues
     - and the platform can explain why it proceeded, stayed normal, or failed closed
   - the implementation notes already show why that matters:
     - without this boundary, replay-watermark advisories and genuine feature-health gaps would be much easier to confuse

11. necessity test:
   - if this path is removed, the platform can still ingest traffic, still build projections, still materialize features, and still produce decisions
   - but it loses clean answer to:
     - whether the runtime had sufficient trusted inputs at decision time
     - whether upstream issue was merely advisory or genuinely blocking
     - why run failed closed
     - and whether decision formation is failing because the inputs are unsafe or because the guardrail boundary does not exist
   - that would weaken `A` immediately, because the reviewer could fairly say the platform has no explicit owner for the most important question between feature truth exists and decision is allowed

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for adjudicating dependency posture before decisioning proceeds
   - intentionality claim:
     - advisories, insufficiency, and fail-closed are deliberately separated rather than collapsed into one crude red and green status
   - materialization claim:
     - the degrade ladder is concrete live runtime workload in the current RTDL plane, not just diagram idea
   - contract claim:
     - this path is governed by explicit requirements around false fail-closed, dependency classification correctness, recovery-to-normal, and decision-mode stability
   - constraint-awareness claim:
     - the system already knows this boundary can be semantically tricky, which is why the implementation trail keeps distinguishing replay advisory, feature-health insufficiency, and proof-harness defects rather than calling all of them the same thing

Plainly stated, the `Decision guardrail path` exists to turn upstream RTDL state into trustworthy decision posture, and its current design shows that this boundary is deliberate, materially seated, and semantically discriminating rather than hand-wavy.

The next clean move is the `Decision formation path`.

## 2026-03-12 10:10:11 +00:00 - Path interrogation: `Decision formation path`

This path exists to turn live runtime understanding into the actual decision truth of the platform. Its job is not to build context, not to materialize features, and not to decide whether the platform should proceed at all; that was the guardrail path. Its narrower job is to answer:

Given the current context, current feature state, current guardrail posture, and the active runtime bundle or policy, what is the actual decision?

The platform framing makes that boundary explicit. The decision path is defined as:

context -> online features -> active bundle or policy resolution -> decision fabric -> action logic -> decision outcome

and the decision fabric exists to produce the actual decision output from live context, features, and active bundle or policy.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn live runtime understanding into actual decision truth of the platform
   - keep this path narrower than context formation, feature materialization, or guardrail posture
   - answer what the actual decision is given current context, current feature state, current guardrail posture, and the active runtime bundle or policy

2. entry:
   - the entry is not raw traffic and not raw RTDL health
   - the entry is the set of things that make decision legitimately formable:
     - joined runtime context
     - online feature readiness
     - guardrail posture
     - active runtime bundle or policy resolution
   - that last part matters
   - the platform explicitly treats registry-to-runtime feedback as real cross-plane path whose question is whether runtime resolves the right active bundle and includes the right bundle or policy identity in decision provenance
   - so the decision-formation path begins only once that authority is consumable at runtime, rather than leaving which model or policy was used as afterthought

3. owned outcome:
   - the owned outcome is decision truth for the current event under the current run, with identity, provenance, and explanation fields complete enough to survive downstream action, audit, and replay
   - that outcome is deliberately narrower than action and outcome truth and narrower than audit truth
   - the run-process supports that split clearly:
     - the decision-chain closure only happens when the decision lane, action and outcome evidence, and append-only audit evidence are all committed
   - which means the decision itself is only one distinct part of the larger chain
   - this path therefore closes at decision truth, not at the later side effects

4. what the path carries:
   - this path carries the minimum things needed to make the decision itself meaningful and reconstructable:
     - the joined runtime context
     - the current online feature state
     - the guardrail posture from the degrade ladder
     - the resolved active bundle or policy identity
     - decision identity and provenance fields
     - explanation fields sufficient for later audit and replay
   - the decision fabric definition is explicit about what has to be carried across this boundary:
     - decisions must be correct for the actual context, online features, and active bundle or policy in scope
     - fail-closed must happen only on real insufficiency or unsafe ambiguity
     - quarantine must happen only on real ambiguity
     - and decision identity, provenance, and explanation fields must be complete enough to survive audit and replay

5. broad route logic:
   - joined context + online features + guardrail posture + active bundle or policy resolution -> decision fabric -> decision truth -> downstream action and audit lanes
   - that broad route matters because it shows the decision fabric is not merely the model call
   - it is the point where multiple upstream truths are composed into one runtime judgment
   - the platform is therefore not saying:
     - we had some context and some features, so decision naturally happened
   - it is saying:
     - there is distinct boundary where runtime inputs plus governed policy and bundle authority become decision truth

6. logical design reading:
   - logically, this path shows that the platform treats decision truth as first-class owned surface, not as invisible side effect between online features and action logic
   - that is strong `A`-level design signal
   - the system is not saying:
     - actions downstream imply what the decision probably was
   - it is saying:
     - the actual decision has its own truth boundary, and that boundary must carry correctness, provenance, explainability, and policy identity explicitly
   - that is why decision formation is separated from the guardrail, action, and audit surfaces in the RTDL framing, and why the run-process gives the whole decision chain its own closure phase instead of burying it inside generic streaming health

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired system
   - the live RTDL runtime posture in the copied baseline wired graphs includes concrete decision deployment alongside the context, entity, feature, guardrail, action, and audit surfaces, all in the active RTDL namespace
   - that means the decision fabric is not just design box; it is concrete runtime workload in the live RTDL plane
   - the run-process and earlier implementation notes reinforce that materiality from the proving side too:
     - the decision-chain closure was expanded into component-granular lanes for decision formation, action, and audit
     - with separate component proofs emitted rather than one lumped claim that decisioning is fine
   - that is another strong sign that the decision fabric is treated as its own owned boundary in the current wired system

8. why the design looks like this:
   - the design looks like this because the platform deliberately refuses to let decision correctness, bundle or policy correctness, and explainability be implied by downstream success
   - several choices in the docs point that way:
     - the decision fabric is defined as its own component with its own purpose and proof surfaces
     - the registry and runtime feedback path explicitly requires that runtime resolve the right active bundle and include bundle or policy identity in decision provenance
     - the run-process separates RTDL catch-up closure from decision-chain closure, which means the RTDL plane being alive is not enough; the decision chain must still close on its own evidence
   - so the current shape exists because the platform wants decision truth to be:
     - explicit
     - governed
     - attributable
     - and replay and audit survivable

9. what larger contracts are shaping this path:
   - three larger contracts shape this path strongly
   - first, the RTDL contract shapes the input side:
     - context must be semantically correct
     - features must be actually present and fresh
     - guardrail posture must distinguish advisory from real insufficiency
   - second, the registry and runtime contract shapes the authority side:
     - runtime must resolve the right active bundle or policy
     - promotion and rollback changes must apply deterministically
     - provenance must include runtime bundle or policy identity
   - third, the decision-chain closure contract shapes the evidence side:
     - the decision lane must be committed
     - action and outcome evidence must be committed
     - append-only audit evidence must be committed
   - so this path is not free to invent its own semantics
   - it is constrained by upstream runtime truth, governed runtime authority, and downstream auditability

10. trade-offs and constraints:
   - this path deliberately adds one more explicit truth boundary to the RTDL graph
   - that costs complexity, because now the platform must carry and preserve:
     - active bundle or policy identity
     - decision provenance
     - explanation coverage
     - fail-closed versus quarantine semantics
     - and duplicate-safe decision commit discipline
   - but that complexity buys something important:
     - the platform can later answer why this decision happened, under what authority, and whether it was the right kind of non-normal outcome
   - without this boundary, the system might still produce actions, but the actual decision logic would be much harder to defend
   - the docs make those trade-offs visible by explicitly naming:
     - fail-closed rate
     - quarantine rate
     - hard fail-closed count
     - decision completeness and provenance completeness
     - policy and bundle resolution correctness
     - explainability coverage
     - duplicate-safe decision commit
     - as the things that matter here

11. necessity test:
   - if this path is removed, the platform can still:
     - ingest traffic
     - form joined context
     - materialize features
     - classify dependency posture
     - and even emit actions later
   - but it loses clean answer to:
     - what the actual decision was
     - which bundle or policy authority produced it
     - whether fail-closed or quarantine was semantically correct
     - whether the decision itself was complete enough to audit
     - and whether downstream action and audit surfaces are acting on explicit decision truth or inferred behavior
   - that would weaken `A` immediately, because reviewer could fairly say the system has all the ingredients of decisioning without explicit owner for the most important truth in the RTDL plane:
     - the decision itself

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for turning context, feature state, guardrail posture, and runtime authority into actual decision truth
   - intentionality claim:
     - the decision boundary is explicit and governed, not inferred from downstream action success
   - materialization claim:
     - the decision fabric is concrete runtime workload in the live RTDL plane, and the decision lane is treated as its own proofable part of the decision-chain closure
   - contract claim:
     - this path is governed by policy and bundle resolution correctness, provenance completeness, explainability coverage, and bounded fail-closed and quarantine semantics
   - constraint-awareness claim:
     - the platform already knows this boundary can be semantically wrong even when upstream runtime looks healthy, which is why it treats decision completeness and bundle or policy correctness as first-class concerns rather than assuming them

Plainly stated, the `Decision formation path` exists to turn runtime understanding plus governed runtime authority into explicit decision truth, and its current design shows that this boundary is deliberate, materially seated, and provenance-aware rather than implicit.

The next clean move is the `Action and outcome emission path`.

## 2026-03-12 10:12:19 +00:00 - Path interrogation: `Action and outcome emission path`

This path exists to turn decision truth into action and outcome truth. Its job is not to form the decision itself, and it is not yet the append-only audit path. Its narrower job is to answer:

Once the platform has decided, how does that decision start affecting the rest of the system in a way that is deterministic, duplicate-safe, and attributable?

The readiness definition makes that boundary explicit: the action layer exists to commit and/or publish action and outcome surfaces from decisions, and it matters because this is where decisions begin affecting the rest of the system.

I want to keep the interrogation of this path inside one entry:

1. what this path is trying to achieve:
   - turn decision truth into action and outcome truth
   - keep this path narrower than decision formation and narrower than append-only audit truth
   - answer how a decision begins affecting the rest of the system in a deterministic, duplicate-safe, and attributable way

2. entry:
   - the entry is not raw traffic, and it is not just generic RTDL health
   - the entry is decision truth that has already been formed under the current run scope, after the RTDL plane has reached its catch-up boundary and the decision chain is allowed to proceed
   - the run-process says the decision-chain closure only opens once RTDL catch-up closure is green, and then requires:
     - the decision lane
     - the action and outcome evidence
     - and the append-only audit evidence
     - as distinct closure elements
   - that means this path begins after decision formation, not before it

3. owned outcome:
   - the owned outcome is deterministic action and outcome truth attributable to the right decision, run, bundle, and policy context
   - this is narrower than audit truth and narrower than case and label truth
   - it closes when action commits or publishes have happened in the platform's owned way, and when ambiguity has been recorded rather than silently leaked
   - the readiness definition for the action layer is precise here:
     - side effects must be duplicate-safe under at-least-once reality
     - action commits must be deterministic
     - no ambiguity may leak into operational outcomes without being recorded
     - and outcomes must remain attributable to the right decision, run, bundle, and policy context

4. what the path carries:
   - this path carries the decision output plus the identity and provenance needed to make side effects reconstructable later
   - in the docs, that means at least:
     - the decision itself
     - the run context
     - the policy and bundle context
     - and the trace from decision to action
   - the same action-layer section names the concrete proof concerns here as:
     - action commit success rate
     - duplicate side-effect error rate
     - ambiguity and quarantine rate
     - action latency
     - and decision-to-action trace completeness
   - that tells us this boundary is carrying more than a bare allow or deny flag

5. broad route logic:
   - decision truth -> action layer -> committed and/or published outcome surfaces -> downstream RTDL and cross-plane consumers
   - that broad route matters because the topic contract makes it concrete:
      - the RTDL downstream topic is the named handoff surface
     - and its producers are the decision and action surfaces
   - which means the action layer is not merely an internal helper after decision formation
   - it is one of the explicit producers of downstream RTDL truth
   - that makes this a real handoff boundary rather than a hidden in-process step

6. logical design reading:
   - logically, this path shows that the platform treats side effects and outcomes as their own truth boundary, not as invisible consequence of decisioning
   - the system is not saying once decision formation produced a decision, the world will somehow be affected
   - it is saying there is dedicated layer that owns how decision truth becomes action and outcome truth under the platform's at-least-once and ambiguity rules
   - that is strong `A`-level design signal because it makes the hot path legible beyond mere scoring

7. concrete seating in the current wired system:
   - this path is materially seated in the current wired platform
   - the copied baseline wired graphs show live action deployment alongside the context, entity, feature, guardrail, decision, audit, and archive surfaces in the RTDL namespace
   - so the action layer is not just design box on graph
   - it is concrete live workload in the current RTDL plane
   - the same baseline network also shows the downstream handoff:
     - the decision and action surfaces publish to the RTDL downstream topic
   - so the path is visible both as runtime workload and as named downstream transport boundary

8. why the design looks like this:
   - the design looks like this because the platform refuses to let decision correctness and side-effect correctness collapse into one fuzzy notion that the hot path worked
   - the run-process separates the decision chain into three closure elements:
     - decision lane
     - action and outcome evidence
     - and append-only audit evidence
   - which means action and outcome truth is intentionally given its own owned closure
   - the readiness definition then sharpens why:
     - duplicate safety
     - deterministic action commits
     - ambiguity recording
     - and trace completeness
     - are treated as first-class properties rather than operator cleanup after the fact

9. what larger contracts are shaping this path:
   - three larger contracts shape it
   - first, the RTDL plane contract says actions and audit outputs must be correct, not just the decisions
   - second, the action-layer contract says side effects must be duplicate-safe, deterministic, attributable, and ambiguity-aware
   - third, the bus and topic contract says the decision and action surfaces are explicit producers of the RTDL downstream topic, which means action and outcome emission participates in named downstream handoff rather than undefined local effect

10. trade-offs and constraints:
   - this path deliberately adds another explicit boundary to the hot path
   - that costs complexity, because the platform must preserve:
     - duplicate-safe semantics
     - ambiguity recording instead of burying it
     - and decision-to-action attribution
   - but that complexity buys much stronger system-design property:
     - later case, label, audit, and replay paths can treat action and outcome truth as something explicit and owned, rather than inferring it from side effects that probably happened
   - the docs are very clear that this platform is not allowed to mix ambiguity with normal outcomes or depend on operator cleanup to make actions look deterministic

11. necessity test:
   - if this path is removed, the platform can still ingest traffic, form context, materialize features, classify guardrail posture, and even produce decision
   - but it loses clean answer to:
     - what concrete outcome followed from that decision
     - whether it was committed safely under duplicates and retries
     - and whether that outcome can be traced back to the right decision, run, bundle, and policy
   - without this path, the RTDL plane would have decision boundary but no explicit owner for how decisions become platform effects
   - that would weaken `A` immediately

12. what this path proves for `A`:
   - purpose claim:
     - the platform has distinct job for turning decisions into action and outcome truth
   - intentionality claim:
     - duplicate safety, ambiguity recording, and attribution are designed properties, not accidental behavior
   - materialization claim:
     - the action layer is a live named workload in the current RTDL plane, and action and outcome evidence is required part of the decision-chain closure
   - contract claim:
     - this path is governed by duplicate-safe side-effect rules, decision-to-action trace completeness, and the decision-and-action to RTDL-topic contract
   - constraint-awareness claim:
     - the platform already knows that side effects are dangerous under at-least-once conditions, which is why the action layer is defined around duplicate safety and ambiguity discipline rather than convenience

Plainly stated, the `Action and outcome emission path` exists to turn decision truth into explicit platform effects that are duplicate-safe, attributable, and ambiguity-aware, and its current design shows that this boundary is deliberate, materially seated, and ownership-aware rather than implicit.

## 2026-03-12 10:47:37 +00:00 - Enumerating the real paths in Group 4: `Durable runtime audit and archive truth`

I want to pin 4 real paths in the durable runtime audit and archive truth group.

That feels like the right split because this group has four distinct owned outcomes in the current wired system:

- append-only audit truth exists
- audit truth is handed off to the right downstream consumers and evidence surfaces
- immutable archive history is durably preserved
- and archive closure produces durable refs that later replay and learning can resolve

The audit and archive surfaces are also explicitly separate RTDL components in the current wired system. The broader authority keeps their posture distinct:

- the decision log and audit surface remains a distinct ownership-heavy runtime corridor
- while the archive corridor is separately governed around immutable preservation and replay continuity

I want to pin the 4 real paths in Group 4 like this:

1. `Audit append path`
   - definition:
     - decision and action truth -> decision log and audit surface -> append-only audit and lineage truth
   - why it is a real path:
     - this path has its own distinct purpose:
       - append authoritative audit and lineage truth for the real-time lane
     - the decision-chain closure treats append-only audit evidence as a distinct closure requirement
     - that means the audit entry existing append-only is its own owned outcome, not just part of decisioning or archive

2. `Audit publication and durable reference path`
   - definition:
     - appended audit truth -> audit bus and durable audit refs -> downstream operational and evidence consumers
   - why it is a real path:
     - this path is distinct from append itself because the topic contract pins an explicit audit handoff topic with the audit surface as producer and downstream operational and evidence consumers on the other side
     - in the copied baseline wired graph, that downstream handoff is visible through the audit topic and the case-trigger/evidence-consuming side of the network
     - so there is distinct handoff boundary after append-only audit truth exists
     - append truth and downstream audit handoff are related, but they are not the same owned outcome

3. `Immutable archive preservation path`
   - definition:
     - runtime decision and action event history -> archive writer -> immutable archived event history in object storage
   - why it is a real path:
     - this path has its own distinct purpose:
       - durably preserve immutable event history and refs for replay and audit
     - that is different from the append-only audit job
     - in the copied baseline wired graph, the archive writer is a distinct RTDL runtime surface that writes immutable history into the archive prefix and stores archive receipts in evidence
     - the broader authority also treats the archive corridor as separately governed around replay and offset continuity, which reinforces that archive preservation is its own runtime-owned path rather than just more audit

4. `Archive closure and replay-reference path`
   - definition:
     - archived runtime truth + continuity metadata -> archive closure marker + durable replay-ready refs
   - why it is a real path:
     - the platform does not stop at files were written
     - RTDL catch-up closure requires archive-writer closure evidence present and emits archive closure marker
     - and later learning-input closure requires archive plus labels plus replay references resolved from spine closure before learning input can begin
     - so there is distinct owned outcome here:
       - not just preserved archive history, but archive truth that is closure-complete and replay-resolvable
     - for `A`, I want to stop this path at replay-ready refs, not at the later learning-input pin

What I do not want to count here:

- decision formation
- action and outcome emission

Those were already closed in Group 3.

I also do not want to count:

- case trigger or case escalation here

even though case handling can consume audit truth, because that belongs to the next group.

And I do not want to count:

- governance append or closure marker here

because that belongs to the later run governance, observability, and evidence-closure group rather than the runtime audit and archive group.

So the pinned Group 4 path set is:

- `Audit append path`
- `Audit publication and durable reference path`
- `Immutable archive preservation path`
- `Archive closure and replay-reference path`

That is the clean split I want to use before going back down into per-path interrogation.

## 2026-03-12 11:07:34 +00:00 - Enumerating the real paths in Group 5: Operational case and label truth

I want to pin 4 real paths in the operational case and label truth group.

That feels like the right split because, even though the plane has only 3 core components, the docs and the live proving notes show 4 distinct owned outcomes inside the group:

- case-intent truth exists
- append-only case truth exists
- case truth has been handed off into label-request or label-pending boundary
- authoritative label truth exists with readback, as-of, and maturity visibility

That split is already latent in the readiness definition, which separates correct escalation, clean truth ownership, bounded latency, and auditability and learning-readiness across the case-trigger surface, case management, and label store. It is also reinforced by the live timing notes, which distinguish first case-trigger intake from case creation, and then distinguish case creation from the later label-request or label-pending handoff. That shows case creation and label handoff are not the same closure point.

I want to pin the 4 real paths in Group 5 like this:

1. `Case-intent escalation path`
   - definition:
     - RTDL decision and audit outputs -> case-trigger surface -> case-intent truth and case-trigger handoff
   - why it is a real path:
     - this path has its own distinct owned job:
       - turn decision-worthy and audit-worthy runtime signals into case-intent signals
     - the plane-level readiness docs treat the first step of escalation separately:
       - the right RTDL outputs must become the right case-worthy signals before case truth even begins
     - the copied baseline wired graph also supports this as a real handoff boundary:
       - the case-trigger topic is pinned as a named transport surface
       - the case-trigger surface publishes into it
       - and case management consumes from it

2. `Case creation and timeline append path`
   - definition:
     - case-intent truth -> case management -> deterministic case identity plus append-only case timeline truth
   - why it is a real path:
     - this path has a distinct owned outcome that is not merely that a case exists
     - it owns the append-only operational case timeline
     - the docs are explicit that case identity must be deterministic, case creation idempotent, transitions append-only and auditable, and later reconstruction possible
     - the implementation notes strengthen this split by showing the authoritative processing clock for case open as intake first-seen to case-created time
     - that is a real case-truth boundary, not just internal implementation detail

3. `Case-to-label handoff path`
   - definition:
     - case or adjudication outcome plus case timeline state -> label request or label-pending handshake -> label-store intake truth
   - why it is a real path:
     - case management does not own label truth, but the plane still needs a distinct handoff from case truth into supervision truth
     - the docs imply that split in two ways:
       - the whole-plane definition says the right cases must eventually produce authoritative labels
       - and the coupled-network phase names case management to label store as its own critical cross-plane path
     - the live timing notes then make the handoff concrete by distinguishing first label request time from the earlier case timeline timestamp
     - that is exactly the kind of separate owned outcome that qualifies as a real path

4. `Authoritative label commit and visibility path`
   - definition:
     - label request or label-intake truth -> label store -> append-only authoritative label truth plus readback, as-of, and maturity visibility
   - why it is a real path:
     - this path owns stronger outcome than some label was written
     - it owns authoritative label truth
     - the docs are explicit that label assertions must be append-only, idempotent, conflict-visible, provenance-complete, and queryable by as-of and maturity, with future-label leakage at zero
     - the copied baseline wired graph also gives this path downstream handoff surface:
       - the label-events topic is pinned as named transport boundary
       - the label store publishes into it
       - and later learning and reporting consumers read from that side of the network
     - that confirms this is not just database write; it is real truth boundary with later consumers

What I do not want to count here:

- the broader RTDL, case, and label auditability path as a separate internal path of this group
  - that is broader cross-plane path, and the later coupled-network phase already names it separately from the core RTDL -> case-trigger -> case management -> label store chain
- the later label-truth path into future learning use inside this group
  - that is later cross-plane handoff, not an owned truth boundary inside the operational case and label plane itself

So the pinned Group 5 path set is:

- `Case-intent escalation path`
- `Case creation and timeline append path`
- `Case-to-label handoff path`
- `Authoritative label commit and visibility path`

That is the clean split I want to use before dropping back down into per-path interrogation.
