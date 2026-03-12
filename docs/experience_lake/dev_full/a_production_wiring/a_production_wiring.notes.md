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
