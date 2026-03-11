# A Production Wiring Notes

## 2026-03-11 17:41:02 +00:00 - Opening the A-notebook means pinning the baseline foundation before readiness-era reasoning starts to distort it
The first thing that needs to stay disciplined in this notebook is the boundary between `A` and `Bi`.

`A` is not the current readiness-shaped platform. It is the baseline engineered foundation that was wired to make the full `dev_full` platform exist as a real system in the first place. That means the notes here need to stay anchored to the baseline wiring object and the wiring-era decision trail, even when later readiness work gives better hindsight about why some choices mattered.

The immediate source set for this notebook is therefore:

- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.impl_actual.md`
- relevant `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M*.build_plan.md` files where the original wiring choices, path selections, and tradeoffs were made explicit

The working object this notebook will keep interrogating is the baseline wired platform:

- what paths had to exist for `dev_full` to be a serious platform foundation at all
- why those paths were wired in that shape
- why those concrete services and runtime surfaces were selected
- what truth boundaries were being protected
- what constraints and tradeoffs were already known and accepted at wiring time

One thing is already clear from the build record: the baseline platform was not wired as a loose collection of services. It was wired under a small number of strong operating laws that explain much of the shape of the network:

- managed-first runtime posture
- no laptop runtime compute
- fail-closed progression
- single active runtime path per phase/run
- Oracle Store seated as read-only warm source-of-stream boundary
- explicit run identity and control authority
- separated truth ownership across ingress, RTDL, case, label, learning, registry, and governance surfaces

That matters because it means the baseline graph should be read as a path-governed foundation, not as an inventory diagram. The next useful move is to walk the baseline platform path by path and keep asking four questions of each path:

1. what real platform job does this path exist to do
2. why is it wired this way rather than some simpler or more fashionable alternative
3. what truth does it own or protect
4. what tradeoff or constraint is already visible in the wiring choice

Judgment at this point:

- the notebook is now pinned to the correct evidential object for `A`
- the build ledger will be used as the reasoning trail behind the baseline network
- readiness-era graphs and hardening deltas should not be allowed to rewrite the foundation story inside this file

## 2026-03-11 17:51:48 +00:00 - The baseline wired platform was given consideration as a full path system, not just as an ingress-to-decision hot lane
The first useful narrowing question was to ask what paths were actually being considered in the baseline wiring rather than starting from components. The path-centric graph makes it clear that the platform was not wired only for a single fraud-scoring lane. It was wired as a set of coordinated path families that together make the platform governable, useful, safe, and operable.

The complete set of path families given explicit consideration in the baseline wiring is:

1. `Control`
   - `GitHub Actions -> Step Functions -> run identity pins`
2. `AP` admission path
   - replay basis -> ingress edge -> ingress gate -> dedupe / quarantine / receipts
3. `HP` hot / decision path
   - ingress publication -> transport -> RTDL -> decisions / audit / downstream trigger
4. `CL` case + label path
   - RTDL truth -> CaseTrigger -> Case Management -> Label Store
5. `LP` learning path
   - archive + labels + learning requests -> Databricks -> SageMaker -> MLflow -> active bundle resolution
6. `RC` recovery path
   - restart / lag catch-up / stable re-entry / decision recovery evidence
7. `DG` degrade path
   - fail-closed, quarantine, and degraded-decision evidence surfaces
8. `RP` replay path
   - archived or oracle basis -> replay -> compare against bounded evidence
9. `RB` rollback path
   - registry / active bundle resolution -> restore prior active bundle
10. `OP` observability path
   - edge, ingress, transport, RTDL, state, and evidence feeding operator visibility
11. `CP` cost-control path
   - budget envelope, spend evidence, teardown or idle action

That inventory matters because it shows the baseline platform was already being reasoned about as more than "event in, decision out". The wiring had to account for control, admission, decisioning, case operations, label truth, learning, recovery, degrade behavior, replay, rollback, observability, and cost posture.

The next useful step was to classify those paths by the job they do in the platform rather than by which components they touch. The cleanest classification for `A` is:

- primary product paths:
  - `AP`
  - `HP`
  - `CL`
  - `LP`
- foundational control path:
  - `Control`
- safety and resilience paths:
  - `RC`
  - `DG`
  - `RP`
  - `RB`
- operational and governance paths:
  - `OP`
  - `CP`

This classification helps because it shows the baseline wiring was trying to satisfy four distinct kinds of engineering need at the same time:

- produce the actual fraud-platform lifecycle
- govern the system coherently as one platform
- preserve correctness outside the happy path
- make the platform diagnosable, auditable, and economically controllable

There is one nuance worth preserving here. `AP` is slightly special because it is both a primary product path and a boundary-protection path. It is the first place where the platform stops merely receiving traffic and starts asserting its own truth through admission, dedupe, quarantine, and receipt behavior.

Judgment at this point:

- the baseline wiring should be defended as a multi-path engineered foundation rather than a component stack
- the path classification gives a better structure for explaining `A` than plane-by-plane inventory alone
- the next discussion should probably walk these groups in order, beginning with the foundational control path and then the primary product paths

## 2026-03-11 17:56:57 +00:00 - The path groups only become useful for A once they are read in terms of purpose: A-goal -> group-goal -> path-goal
The next clarification was necessary because classification by itself is still too static. To make the path groups useful for `A`, they have to be read in terms of purpose.

The global goal of `A` is:

- establish that the current wired platform is already a real engineered foundation
- show that the foundation is path-justified rather than component-accidental
- show that the platform was wired with explicit control, truth, operational, and lifecycle thinking
- make it credible that this base could later support readiness work and then operational proof

Once that global goal is fixed, each path group can be understood by the specific part of `A` that it helps carry.

### 1. Foundational control path
Group goal:

- make the platform a governed system rather than a loose collection of runtimes

How this group contributes to `A`:

- it shows there was already explicit thinking about authority, orchestration, run scope, and control continuity
- it proves the platform was wired as one coordinated system with a shared execution story

Path contribution inside the group:

- `Control`
  - path goal:
    - establish bounded-run authority, dispatch, run identity, and cross-path scope continuity
  - contribution to group goal:
    - this is the path that gives the rest of the platform one authoritative control story instead of many disconnected local executions

### 2. Primary product paths
Group goal:

- realize the actual fraud-platform lifecycle from inbound traffic to decisioning, operations, and learning

How this group contributes to `A`:

- it shows the foundation was already non-trivial and materially useful
- it proves the platform was not wired for a demo hot path only, but for the broader runtime-to-learning lifecycle

Paths and their contributions inside the group:

- `AP`
  - path goal:
    - turn inbound traffic into platform-owned admission truth through dedupe, quarantine, and receipts
  - contribution to group goal:
    - creates the trustworthy starting boundary for every later path

- `HP`
  - path goal:
    - turn admitted traffic into context, features, decisions, actions, and audit truth
  - contribution to group goal:
    - delivers the real-time decisioning capability that makes the platform operationally meaningful

- `CL`
  - path goal:
    - turn runtime decision truth into operational cases and authoritative labels
  - contribution to group goal:
    - extends the platform beyond scoring into operational follow-through and supervision truth

- `LP`
  - path goal:
    - turn runtime history and label truth into governed datasets, train/eval outputs, and active bundle resolution
  - contribution to group goal:
    - closes the lifecycle so the platform is not just online runtime but also supports learning and evolution

There is still a useful nuance here:

- `AP` belongs in the primary product group because it starts the real platform lifecycle
- but it also acts as a boundary-protection path because this is where the platform first asserts its own truth

### 3. Safety and resilience paths
Group goal:

- preserve semantic correctness, continuity, and reversibility outside the happy path

How this group contributes to `A`:

- it shows the baseline wiring already considered failure, rerun, degraded operation, and reversal
- it makes the foundation feel engineered rather than naive

Paths and their contributions inside the group:

- `RC`
  - path goal:
    - support bounded restart, lag catch-up, stable re-entry, and recovery evidence
  - contribution to group goal:
    - shows the system was wired to recover without silently changing truth

- `DG`
  - path goal:
    - provide fail-closed, quarantine, or degraded behavior when inputs or dependencies become insufficient
  - contribution to group goal:
    - shows the system was not designed to pretend success under uncertainty

- `RP`
  - path goal:
    - enable replay and bounded comparison against expected evidence
  - contribution to group goal:
    - shows correctness was expected to be testable and re-runnable, not one-shot only

- `RB`
  - path goal:
    - restore a prior active bundle or policy state when a later promoted state must be reversed
  - contribution to group goal:
    - shows reversibility was part of the baseline platform story, not only a later production hardening concern

### 4. Operational and governance paths
Group goal:

- make the platform observable, explainable, auditable, and economically governable

How this group contributes to `A`:

- it shows that the baseline foundation already included operator visibility and cost discipline
- it helps prove the platform was engineered with reviewability and runtime accountability in mind

Paths and their contributions inside the group:

- `OP`
  - path goal:
    - expose behavior across edge, ingress, transport, RTDL, state, and evidence surfaces to operators
  - contribution to group goal:
    - shows the platform was wired to be diagnosable and reconstructable

- `CP`
  - path goal:
    - connect budget, spend evidence, and teardown or idle control to explicit operating decisions
  - contribution to group goal:
    - shows the platform was wired with economic posture in mind rather than assuming endless runtime slack

The main value of this purpose-led reading is that it keeps `A` from collapsing into either a service inventory or a generic "platform has many concerns" statement. Instead the structure becomes:

- `A` needs to prove real engineered foundation
- each path group carries one major dimension of that proof
- each path carries a smaller but necessary part of the group claim

Judgment at this point:

- the four groups are best treated as four supporting arguments for `A`
- each path should now be read as a local contribution to one of those supporting arguments
- this gives a much stronger way to discuss the baseline wiring than listing services or planes in isolation

## 2026-03-11 18:43:22 +00:00 - The first useful A-primer is now in place: the baseline network is being read through shared components with path meaning overlaid on the flows
The discussion so far has materially changed the posture of this notebook. The baseline wired platform is no longer being approached as a plane inventory or as a giant component map that has to be read all at once. The working interpretation is now:

- the system should first be read through its paths
- those paths should be grouped by the major kind of work they do for the platform
- and those groups should be understood by how they contribute to the global goal of `A`

That means the current working structure for `A` is:

- foundational control path
- primary product paths
- safety and resilience paths
- operational and governance paths

This has already clarified two things that were getting mixed together before:

1. planes and paths are not the same thing
   - planes partition the platform structurally
   - paths explain what the platform is trying to achieve across those structural partitions
2. path thinking is the stronger primary lens for `A`
   - because `A` is trying to prove the baseline platform is a real engineered foundation
   - and purpose is a better way to prove that than component inventory alone

Another important clarification also landed during this pass: paths do not imply isolated components. Shared components are expected. What changes from one path to another is not the existence of an entirely different service set, but the role those shared components are playing in achieving a different purpose. That was the reason for shifting the simplified graph work away from path-as-boxes and toward shared components with path meaning carried on the connecting flows.

The current baseline asset set supporting that simplification work is:

- `docs/experience_lake/dev_full/a_production_wiring/assets/wired.platform_network_current.mermaid.mmd`
- `docs/experience_lake/dev_full/a_production_wiring/assets/wired.platform_resources_current.mermaid.mmd`
- `docs/experience_lake/dev_full/a_production_wiring/assets/wired.path_overlay.network_overview.mermaid.mmd`
- `docs/experience_lake/dev_full/a_production_wiring/assets/wired.path_overlay.resources_overview.mermaid.mmd`

The overlay graphs are not meant to replace the baseline network/resource references. Their job is only to prime understanding by showing:

- the shared component surfaces
- the major bundled boundaries
- and how the different path families traverse overlapping parts of the same baseline system

Judgment at this point:

- the `A` discussion now has a stable purpose-led frame
- the simplified overlays are good enough to serve as priming views before deeper path-by-path analysis
- the next useful move is to begin the actual path walk in increasing depth, starting from foundational control and then moving into the primary product paths

## 2026-03-11 20:16:22 +00:00 - The first group-specific extraction has now been made from the baseline wiring: Foundational Control-path is isolated as its own network and resource view
The next step was to stop working only from the full baseline wiring views and extract the first group-specific slice from them so the path can be interrogated without the rest of the platform crowding the picture.

The extraction was made from:

- `docs/experience_lake/dev_full/a_production_wiring/assets/wired.platform_network_current.mermaid.mmd`
- `docs/experience_lake/dev_full/a_production_wiring/assets/wired.platform_resources_current.mermaid.mmd`

The resulting control-specific views are:

- `docs/experience_lake/dev_full/a_production_wiring/assets/wired.control_path.network.mermaid.mmd`
- `docs/experience_lake/dev_full/a_production_wiring/assets/wired.control_path.resources.mermaid.mmd`

These are not intended to be new authority graphs. They are reduced views derived from the baseline wiring so the Foundational Control path can be studied in isolation while still remaining faithful to the original network and resource commitments.

The extraction keeps the control story explicit:

- control entry and delivery surfaces
- run authority surfaces
- run identity and runtime-path governance
- run-control receipts and durable evidence
- immediate governed downstream boundaries

It intentionally does not expand the downstream internals of ingress, RTDL, case/label, or learning inside this slice because the point right now is not to re-read the whole platform. The point is to see what the control path itself is trying to do and what parts of the wider platform it governs.

With that extraction in place, the active focus of the notebook now shifts from general path framing into detailed inspection of the first group:

- `Foundational Control path`

Judgment at this point:

- the baseline network and resource views are now supporting group-specific extractions cleanly
- the Foundational Control path has a stable isolated view for questioning its design decisions
- the next work should stay inside this group long enough to understand its internal subpaths, control laws, tradeoffs, and why they were necessary for `A`
