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
   - the run-process pins all of those as PASS requirements for `ORACLE_READY`
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

This path exists to turn a run from "eligible to become ready" into "authoritatively declared ready." In the run-process, that is not a soft health signal; it is a formal closure point. `P5 READY_PUBLISHED` only closes when READY is emitted to the control topic, the READY receipt is committed, duplicate or ambiguous READY is prevented, and the commit authority is validated as Step Functions rather than Flink-only compute. The design authority says the same thing in broader architectural language: READY/control stays Kafka-backed, but closure authority stays with Step Functions.

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
     - the required P5 handle set is resolved
     - the Step Functions authority surface resolves to a real active state machine
   - in executed prechecks, that meant validating run-continuity handoff, resolving the Step Functions handle chain, and confirming the control-topic anchors before READY publication was attempted

3. owned outcome:
   - the owned outcome is an authoritatively ready run, not merely a computed readiness hint
   - concretely, the pass condition is:
     - READY emitted to `fp.bus.control.v1`
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
   - the control surface is the Kafka control topic `fp.bus.control.v1`
   - the control-plane authority is the concrete Step Functions state machine `fraud-platform-dev-full-platform-run-v0`
   - the READY receipt lands in the run evidence surface under the run's S3 evidence root
   - the handle contract pins:
     - `READY_MESSAGE_FILTER = "platform_run_id=={platform_run_id}"`
     - `KAFKA_PARTITION_KEY_CONTROL = "platform_run_id"`
     - `SR_READY_COMMIT_RECEIPT_PATH_PATTERN = "evidence/runs/{platform_run_id}/sr/ready_commit_receipt.json"`
   - this is a very strong `A` signal because the path is not only conceptually designed; it is concretely realized

8. why the design looks like this:
   - the implementation notes make the design reasoning explicit
   - letting Flink-ready output implicitly close `P5` was rejected
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
     - the entry precheck resolved all required P5 handles
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
       - `fp.bus.traffic.fraud.v1`
       - `fp.bus.context.arrival_events.v1`
       - `fp.bus.context.arrival_entities.v1`
       - `fp.bus.context.flow_anchor.fraud.v1`
     - the data-engine contract explains why that split exists: behavioural streams are intentionally thin traffic, while arrival/entity/flow-anchor surfaces are context to be joined inside the platform
     - this is a distinct owned outcome from merely deciding admission, because this is the first place where Group 2 hands truth over to downstream runtime via the event bus

4. `Ingest commit truth path`
   - definition:
     - admission + publication outcomes -> receipt summary / quarantine summary / offset-proof materialization -> committed ingest truth
   - why it is a real path:
     - this path turns admission and publication activity into durable ingress evidence
     - the run-process gives this a separate closure point in `P7 INGEST_COMMITTED`: admit/quarantine summaries must be committed, an offset snapshot must be committed in a mode-aware way, and dedupe/anomaly checks must pass
     - the implementation notes reinforce that this is not optional reporting: they explicitly reject claiming pass from DynamoDB admissions alone, and they keep the lane fail-closed when Kafka offsets are not materially available, recording `IG_ADMISSION_INDEX_PROXY` instead of fabricating broker offsets
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
     - `IG_AUTH_MODE = "api_key"`
     - `IG_AUTH_HEADER_NAME = "X-IG-Api-Key"`
     - `SSM_IG_API_KEY_PATH = "/fraud-platform/dev_full/ig/api_key"`
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

That separation is already visible in the docs: the control and ingress plane is supposed to admit valid traffic, reject invalid traffic, deduplicate repeated traffic, and keep failure classes explicit rather than mixing them together. Later, `P7 INGEST_COMMITTED` closes only when admit and quarantine summaries are committed and dedupe and anomaly checks pass, which means disposition truth is first-class thing, not incidental side effect.

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
   - that matches both the ingress-shell criteria and the later `P7` closure rule, where admit and quarantine summaries and dedupe checks are committed separately from full downstream proof

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
   - the handles registry pins the live edge contract around `IG_BASE_URL`, `IG_INGEST_PATH`, `IG_AUTH_MODE`, and `SSM_IG_API_KEY_PATH`
   - the implementation notes then make the active runtime posture more specific:
     - the current IG edge runtime is `apigw_lambda_ddb`
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
   - instead, it kept the proven fast `ddb_hot` posture and compacted the stored receipt shape to the minimum fields needed for run attribution and lookup
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
     - the path is concretely seated in the current `apigw_lambda_ddb` posture with DynamoDB-backed idempotency and admission state
   - contract claim:
     - only the right traffic types are eligible, and ingress truth remains ingress truth
   - quantified closure claim:
     - later closure is not vague
     - `P7` explicitly requires admit and quarantine summaries plus dedupe and anomaly checks, which means this path has named evidence closure downstream in the runbook

Plainly stated, the `Admission and disposition path` exists to make ingress truth explicit before event-bus truth begins, and its current design shows that this is deliberate, materially seated, and ownership-aware rather than hand-wavy.

The next path is the `Authoritative bus publication path`.

## 2026-03-12 09:21:41 +00:00 - Path interrogation: `Authoritative bus publication path`

This path exists to turn ingress truth into authoritative event-bus truth. The previous path decides whether an event is admitted, quarantined, rejected, or duplicate-safe. This path answers the next question:

For traffic that ingress has decided to admit, where does the platform authoritatively hand it off so runtime can begin?

The pinned topic contracts make that answer explicit: the bus surfaces are authoritative, and IG is the producer for the traffic and context topics that feed RTDL. The design authority names Kafka topics as authoritative bus surfaces, and the topic map pins IG as the producer for `fp.bus.traffic.fraud.v1`, `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, and `fp.bus.context.flow_anchor.fraud.v1`.

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
     - `fp.bus.traffic.fraud.v1` - IG -> RTDL ingress
     - `fp.bus.context.arrival_events.v1` - IG -> RTDL context
     - `fp.bus.context.arrival_entities.v1` - IG -> RTDL context
     - `fp.bus.context.flow_anchor.fraud.v1` - IG -> RTDL join plane
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
