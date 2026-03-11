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
