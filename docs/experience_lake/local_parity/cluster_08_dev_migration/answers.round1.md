# Cluster 8 - Round 1 Answers

## Q1) State the migration goal in one line: what "dev_min Spine Green v0" means and what it must preserve from local_parity.

**One-line goal:**  
`dev_min Spine Green v0` means running the same proven local-parity spine lifecycle (`P0..P11`, plus `P12` teardown) on managed substrate and managed compute, with zero semantic drift.

### What this means in plain engineering terms

The migration is **not** "rewrite the platform for cloud."  
It is: **keep the platform laws identical, change only the wiring and runtime substrate**.

### What changes in dev_min (allowed change surface)

1. **Substrate changes:** event bus and durable stores are managed services instead of local shims.
2. **Runtime packaging changes:** platform services/jobs run as managed ephemeral compute, not laptop runtime processes.
3. **Operator flow changes:** bring-up/run/teardown is executed as a cloud demo program with durable evidence.

### What must be preserved from local_parity (non-negotiable)

1. **Same scope contract (Spine Green v0).**  
   In-scope remains Control+Ingress, RTDL, Case+Labels, and Run/Operate+Obs/Gov.  
   Learning/Registry remains out-of-scope for this baseline.

2. **Same phase-machine meaning.**  
   `P0..P11` must mean the same thing and close by the same gate logic as local parity.  
   No shortcut phase-skips to "make cloud green."

3. **Same run identity discipline.**  
   `platform_run_id` and `scenario_run_id` remain first-class correlation anchors across all lanes and evidence.

4. **Same ingress truth laws.**  
   IG keeps fail-closed admission semantics, canonical event identity, dedupe behavior, payload-hash anomaly handling, and receipt truth.

5. **Same append-only evidence posture.**  
   Receipts, audit truth, and label/case evidence remain append-only; no in-place mutation shortcuts.

6. **Same explicit degrade posture.**  
   Missing/late context must produce explicit degrade outcomes, not silent guessing.

7. **Same replay basis.**  
   Offset/anchor evidence must still support deterministic replay and run reconciliation.

8. **Same closure rigor.**  
   No unresolved ambiguity blockers at green close, and reporter/governance closeout remains single-writer/fail-closed.

### Practical definition you can defend in an interview

If local parity proved **semantic correctness**, then dev_min Spine Green v0 proves **semantic correctness under managed infrastructure constraints** (identity, secrets, network, cost, teardown, and durable evidence), without changing platform behavior.

## Q2) What are the non-negotiable guardrails (budget posture, demo->destroy, no NAT/LB, no laptop runtime compute)?

These guardrails are hard laws, not preferences. If any is violated, migration is not considered valid.

### 1) Budget posture guardrail (hard cap + alert ladder)

**Rule:** dev_min must run under a strict low-cost posture (target envelope around `£30/month`) with explicit stop thresholds.

Why this is non-negotiable:

1. This migration is a credibility rung, not a paid always-on environment.
2. If cost control is weak, "production-like" becomes financially non-repeatable.
3. Cost discipline is itself an operations signal recruiters care about.

Enforcement:

1. Budget alerts are pinned as part of substrate readiness (for example escalation thresholds like `£10 / £20 / £28`).
2. Demo resources are treated as ephemeral and are not allowed to idle.
3. Teardown proof is part of lifecycle closure, not an optional cleanup.

Fail condition:

- If budget posture cannot be shown as controlled, phase does not close green.

### 2) Demo -> destroy guardrail (default runtime posture)

**Rule:** expensive runtime resources are created for demo/run windows and destroyed immediately after; persistence is reserved for evidence/core control surfaces.

Why this is non-negotiable:

1. It prevents silent monthly cost creep.
2. It proves reproducible bring-up/teardown capability.
3. It forces infrastructure to be declarative and automation-safe.

Enforcement:

1. Infra is split into **persistent core** vs **ephemeral demo** surfaces.
2. Run lifecycle explicitly includes teardown closure (`P12`) and requires teardown evidence.
3. "Run complete" without teardown proof is considered incomplete from migration-governance perspective.

Fail condition:

- If demo resources remain after closure, the run is operationally non-compliant.

### 3) No NAT guardrail (cost-footgun prohibition)

**Rule:** NAT Gateway is prohibited for dev_min.

Why this is non-negotiable:

1. NAT is a known budget trap for low-cost demo environments.
2. It encourages hidden always-on network spend that violates demo->destroy posture.

Enforcement:

1. Network readiness gates explicitly check no-NAT posture.
2. If NAT appears in the environment, it is treated as a blocker, not a warning.

Fail condition:

- NAT presence blocks phase closure until removed.

### 4) No always-on load balancer dependency

**Rule:** dev_min must not rely on always-on ALB/NLB posture for normal operation.

Why this is non-negotiable:

1. Always-on LB introduces idle cost and pushes the stack toward permanent infra.
2. For this rung, the objective is managed-substrate proof with bounded spend, not full internet-exposed service mesh posture.

Enforcement:

1. Network/infra gates verify no forbidden always-on LB dependency.
2. Any LB usage must be bounded and justified, not a permanent baseline requirement.

Fail condition:

- If the platform requires always-on LB to be considered runnable, dev_min posture is considered drifted.

### 5) No laptop runtime compute

**Rule:** operator laptop may orchestrate and inspect, but platform runtime compute must execute on managed ephemeral infrastructure.

Why this is non-negotiable:

1. This is the key difference between local parity and migration proof.
2. Laptop runtime invalidates the claim that the spine runs in managed substrate.
3. It forces you to validate real identity/network/secret/runtime boundaries.

Enforcement:

1. Runtime jobs/services are expected to run as managed tasks/services (not local processes).
2. Phase gates explicitly reject laptop-only dependency proofs for runtime readiness.
3. Launch/readiness evidence must point to managed runtime artifacts.

Fail condition:

- If any required spine lane depends on laptop execution to be green, migration closure is blocked.

### 6) Guardrail interaction (how they work together)

These are designed as a coherent control system:

1. **No laptop compute** prevents fake cloud claims.
2. **No NAT / no always-on LB** prevents hidden infra creep.
3. **Demo->destroy** enforces ephemeral operations discipline.
4. **Budget alerts + teardown proof** make cost posture auditable.

So the migration isn’t just "running in cloud." It is "running in cloud under explicit operational law."

## Q3) What’s the authority stack for migration decisions (what wins when docs conflict)?

My migration decision model uses a **strict precedence stack**.  
If two documents disagree, I do not merge them informally; I resolve by rank and fail closed if still ambiguous.

### 1) Authority stack (highest to lowest)

1. **Core platform law (global semantics).**  
   These define what the platform is, independent of environment.

2. **Dev-min migration authority.**  
   This pins non-negotiable migration constraints (managed substrate, budget posture, forbidden infra, no-laptop runtime posture, drift discipline).

3. **Dev-min run process flow + handles registry.**  
   These are execution authorities for:
   - phase semantics translation (`P0..P11`, `P12`),
   - run lifecycle/gates,
   - concrete runtime handle identities (topics, buckets, SSM paths, role keys, service handles).

4. **Local-parity semantic source truth (phase/gate meaning).**  
   This is the reference for what "green" means and what each lane is supposed to prove.  
   Dev-min is required to preserve this meaning while swapping substrate.

5. **Component/platform pre-design decisions and implementation maps.**  
   These govern detailed implementation posture and recorded decision trail, but cannot override higher semantic pins.

6. **Build plans and execution notes.**  
   These are execution control documents (phase sequencing, DoD, evidence obligations).  
   They are binding for active execution but must remain subordinate to higher authorities.

### 2) Conflict rule (what wins)

When docs conflict, the higher layer wins, always.

Examples:

1. If a lower planning note suggests broadening baseline scope (for example adding Learning/Registry), but scope lock says Spine Green v0 excludes it, **scope lock wins**.
2. If a script/config uses a literal resource name that differs from registry handle values, **handles registry wins**.
3. If an execution shortcut weakens phase-gate meaning inherited from local parity, **phase semantics win** and shortcut is rejected.

### 3) What I treat as executable authority vs support material

Executable authority:

1. migration authority constraints,
2. run process flow phase/gate definitions,
3. handles registry values,
4. active phase build-plan DoD + blocker logic.

Support context (useful, but not tie-break authority):

1. brainstorming notes,
2. exploratory drafts,
3. convenience scripts that are not pinned in the active authority path.

### 4) Fail-closed procedure when conflict is unresolved

If a conflict cannot be resolved cleanly by stack order:

1. stop implementation,
2. log the conflict and impacted lanes,
3. request explicit repin,
4. resume only after authority is updated.

No silent assumptions, no "best-effort merge."

### 5) Why this matters in migration

In a local->dev migration, most regressions happen from document drift, not code syntax errors.  
This authority stack prevents semantic erosion while still letting implementation evolve quickly within pinned boundaries.

## Q4) Walk me through what "DONE" means for M0-M3: what you produced, what evidence artifacts exist, what the next phase consumes

For this program, `DONE` is not a status label. It means:

1. phase DoD checks are fully closed,
2. blockers are empty,
3. evidence artifacts are published (local + durable where required),
4. next-phase handoff contract is explicit and consumable.

### M0 - Mobilization + Authority Lock (`DONE`)

#### What was produced

1. migration execution governance model (single status owner, phase transition law, evidence template, anti-drift stop protocol),
2. deep-phase routing structure (main control plan + per-phase deep plans),
3. fail-closed progression discipline (no phase advancement on ambiguity).

#### Evidence artifacts that exist

1. control-plan roadmap and phase-state closure for M0,
2. deep M0 closure snapshot with completed governance checklist,
3. append-only decision/action trail entries proving M0 was executed as a control phase, not a runtime phase.

#### What M1 consumes

1. authoritative precedence stack,
2. phase/evidence template M1 must satisfy,
3. rule that M1 cannot claim closure without explicit immutable packaging evidence.

---

### M1 - Packaging Readiness (`DONE`)

#### What was produced

1. single-image packaging contract for Spine Green v0,
2. full entrypoint matrix for all required runtime lanes,
3. immutable provenance contract (`git tag -> digest -> run evidence`),
4. secret-injection contract (no baked secrets),
5. authoritative CI build workflow and gate validation surface.

#### Evidence artifacts that exist

1. run-scoped packaging evidence under `P(-1)` for `platform_20260213T114002Z`,
2. `packaging_provenance.json`,
3. `build_command_surface_receipt.json`,
4. `security_secret_injection_checks.json`,
5. CI output artifact binding immutable image identity:
   - tag: `git-799d398a7daf34857cf363c9a1a629c40ec25d5e`
   - digest: `sha256:d71cbe335ec0ced59a40721f0e1f6016b276ec17f34e52708d3fd02c04d79f56`.

#### What M2 consumes

1. immutable image identity and entrypoint handles,
2. proven build-driver execution contract,
3. secret-handling posture M2 must preserve during substrate provisioning/runtime wiring.

---

### M2 - Substrate Readiness (`DONE`)

#### What was produced

1. managed substrate closure across capability lanes:
   - Terraform state partitioning (`core`/`confluent`/`demo`),
   - handle resolution,
   - Confluent topic/auth readiness,
   - SSM secret materialization,
   - network posture validation (including no-NAT rule),
   - runtime DB readiness + migration lane,
   - budget + teardown viability controls.
2. explicit blocker model and recovery flow across M2 sub-phases.

#### Evidence artifacts that exist

1. authoritative M2 closeout package `m2_20260213T205715Z`,
2. `m2_exit_readiness_snapshot.json` (completeness + verdict),
3. `m3_handoff_pack.json` (next-phase substrate contract),
4. supporting M2 evidence families including:
   - apply snapshots (`core`/`demo`),
   - `handle_resolution_snapshot.json`,
   - `topic_readiness_snapshot.json`,
   - `secret_surface_check.json`,
   - `network_posture_snapshot.json` + no-NAT checks,
   - DB readiness and migration snapshots,
   - budget guardrail + teardown viability snapshots.

#### What M3 consumes

1. the resolved runtime handle map from `m3_handoff_pack.json`,
2. confirmed substrate readiness constraints for run pinning,
3. budget/teardown status that must remain clean before advancing to daemon bring-up.

---

### M3 - Run Pinning (`DONE`)

#### What was produced

1. collision-safe canonical `platform_run_id` generation contract,
2. deterministic run payload + config digest contract,
3. durable run anchors:
   - `run.json`
   - `run_started.json`,
4. runtime scope export for daemon lanes (`REQUIRED_PLATFORM_RUN_ID` handoff surface),
5. explicit binary verdict model (`ADVANCE_TO_M4` vs `HOLD_M3`),
6. final M4 handoff package.

#### Evidence artifacts that exist

1. authoritative M3 closeout package `m3_20260213T221631Z`,
2. run root artifacts for pinned run `platform_20260213T214223Z`,
3. `m3_f_verdict_snapshot.json` with verdict `ADVANCE_TO_M4`,
4. `m4_runtime_scope_bundle.json`,
5. `m3_run_pinning_snapshot.json`,
6. `m4_handoff_pack.json`.

(Supporting lane artifacts also exist for M3.A/M3.B/M3.C closure proofs, including handle closure, run-id generation snapshots, and digest snapshots.)

#### What M4 consumes

1. canonical `platform_run_id` and run anchor URIs,
2. required run-scope injection map for all daemon services,
3. M3 verdict proving P2 bring-up is authorized,
4. immutable provenance and digest context that M4 must preserve while launching services.

### Summary of "DONE" posture across M0-M3

Across these phases, `DONE` meant we moved from governance lock -> packaging immutability -> substrate closure -> run identity anchoring, with each phase producing machine-checkable artifacts that directly feed the next phase instead of relying on human memory.

## Q5) Packaging posture: single-image strategy? entrypoint matrix? provenance (sha/digest) binding?

### 1) Single-image strategy (yes, deliberately)

For dev_min Spine Green v0, I chose a **single platform image** strategy.

Why this was the right choice at this stage:

1. It reduces packaging drift across many daemon/job lanes during migration.
2. It makes provenance verification simpler (one immutable image identity per run posture).
3. It keeps the migration focus on substrate/runtime correctness, not multi-image orchestration complexity.

What I did to keep this safe:

1. Pinned an explicit image content contract (required include set + explicit excludes).
2. Blocked `COPY . .` style ambiguous Docker build surfaces.
3. Kept image build reproducibility under one authoritative CI driver contract.

So this is not "one image because easier." It is one image with strict boundary controls.

### 2) Entrypoint matrix posture (yes, fully pinned)

The single image is only valid because the **entrypoint matrix** was made explicit and executable.

I pinned invocation contracts for all in-scope runtime families, including:

1. Oracle lane jobs:
   - seed/pack,
   - stream-sort,
   - checker.
2. Control/Ingress:
   - SR,
   - WSP,
   - IG service.
3. RTDL core:
   - ArchiveWriter,
   - IEG,
   - OFP,
   - CSFB intake.
4. Decision lane:
   - DL,
   - DF,
   - AL,
   - DLA,
   - CaseTrigger.
5. Case/Label services:
   - CM,
   - LS.
6. Closure lane:
   - reporter.

Validation posture:

1. Each entrypoint had deterministic callability checks.
2. Missing or unresolved entrypoint handles were treated as blockers (not soft warnings).
3. We later used this rigor operationally; unresolved launch profiles in M4 were explicitly blocked until entrypoint handles were pinned.

### 3) Provenance binding (immutable and cross-anchored)

Provenance is bound through an immutable identity chain:

1. **source commit SHA** -> immutable `git-<sha>` image tag,
2. immutable tag -> resolved OCI digest (`sha256:...`),
3. CI run metadata -> packaging evidence artifacts,
4. packaging evidence -> run anchor (`run.json`) cross-check.

Required provenance fields were pinned, including:

1. image tag,
2. image digest,
3. git SHA,
4. build timestamp,
5. build actor,
6. repository/image reference metadata.

And this was enforced fail-closed:

1. if tag->digest resolution fails, packaging fails;
2. if `packaging_provenance.json` and `run.json` disagree, progression is blocked;
3. mutable convenience tags are non-authoritative and cannot be used as closure proof.

### 4) Concrete packaged result (authoritative example)

Authoritative packaging run produced immutable image identity:

1. tag: `git-799d398a7daf34857cf363c9a1a629c40ec25d5e`
2. digest: `sha256:d71cbe335ec0ced59a40721f0e1f6016b276ec17f34e52708d3fd02c04d79f56`

With corresponding packaging artifacts under the run-scoped `P(-1)` evidence path.

### 5) Packaging posture in one sentence

Packaging is **single-image, multi-entrypoint, immutable-provenance, fail-closed**; if any of those four breaks, migration progression stops.

## Q6) IaC posture: what’s in Terraform vs scripts, how you prevent drift, how teardown is proven

### 1) Terraform vs scripts (clear ownership split)

I use a strict split:

1. **Terraform owns desired infrastructure state.**
2. **Scripts own verification, orchestration glue, and evidence publication.**

#### Terraform-owned surfaces

Terraform is authoritative for resource existence/configuration across split stacks:

1. **Core stack** (persistent, low-cost baseline):
   - tfstate backend surfaces,
   - evidence/core storage primitives,
   - budget/guardrail anchors,
   - shared control identities.
2. **Confluent stack** (managed Kafka control surfaces):
   - cluster/environment artifacts,
   - topic/credential materialization contract surfaces.
3. **Demo stack** (ephemeral runtime surfaces):
   - managed runtime compute surfaces,
   - runtime DB/network role bindings,
   - launch-time handles needed by run phases.

This split is deliberate: it enables demo->destroy without losing persistent control/evidence backbone.

#### Script-owned surfaces

Scripts are not allowed to "replace Terraform." They do:

1. preflight checks,
2. handle/readiness verifications (topics, secrets, IAM, network, DB),
3. phase evidence generation and publication,
4. controlled run orchestration actions,
5. blocker diagnostics/reporting.

So scripts verify and operate; Terraform defines.

### 2) Drift prevention posture (fail-closed)

I treat drift as a first-class failure mode and use multiple controls:

1. **No manual console drift policy.**  
   Infrastructure mutations must be codified in Terraform; ad hoc console changes are not accepted as closure.

2. **State partition + locking discipline.**  
   Core/confluent/demo state keys are separated and lock-protected, which prevents cross-stack accidental overwrite and concurrent mutation errors.

3. **Handle registry as executable contract.**  
   Runtime/resource identifiers are pinned in a central handle registry.  
   Unknown or missing required handles fail phases closed.

4. **Phase blocker model.**  
   Every phase has explicit blocker taxonomy; unresolved blockers block progression by policy.

5. **Evidence-backed closure only.**  
   A phase is not "green" because commands ran. It is green only when required artifacts exist and checks are pass in evidence snapshots.

6. **Authoritative status ownership.**  
   One control plan owns phase status transitions, preventing hidden side-status drift between docs.

### 3) Teardown proof posture (not optional cleanup)

Teardown is a governed requirement, not operator etiquette.

#### How teardown is proven

1. **Pre-destroy viability checks** are run and recorded before claiming destroy-safe posture.
2. **Destroy command surfaces** are pinned and bounded to demo scope.
3. **Post-destroy checks** verify no forbidden cost-bearing demo resources remain.
4. **Teardown evidence artifacts** are published as phase proof objects.

In practice, teardown viability and budget posture were explicitly evidenced in M2 closeout snapshots and then carried forward as gating logic for later phases.

#### What fails teardown posture

1. leftover demo compute/services,
2. forbidden cost-footgun resources still present,
3. missing teardown evidence artifact,
4. unresolved budget-stop condition.

Any of the above blocks phase closure.

### 4) Why this IaC posture is strong

This model gives the right balance:

1. Terraform remains the single source of infra truth.
2. Scripts provide operational rigor and auditable checks.
3. Drift and teardown are enforced by gates, not trust.

That is exactly the posture you want for a migration story that claims production-like operational discipline.

## Q7) Secrets/bootstrap: how secrets are materialized, what is forbidden, how least privilege is verified

### 1) Secret materialization model (who creates, where it lives, how runtime consumes)

I use a strict three-layer model:

1. **Provision layer (Terraform/apply lanes).**  
   Required secret locator handles are pinned and materialized to canonical SSM paths for dev_min, including:
   - Confluent runtime connectivity/auth handles:
     - `SSM_CONFLUENT_BOOTSTRAP_PATH`
     - `SSM_CONFLUENT_API_KEY_PATH`
     - `SSM_CONFLUENT_API_SECRET_PATH`
   - ingress auth handle:
     - `SSM_IG_API_KEY_PATH`
   - runtime DB auth handles:
     - `SSM_DB_USER_PATH`
     - `SSM_DB_PASSWORD_PATH`
   - optional DSN mode surface (only when explicitly selected):
     - `SSM_DB_DSN_PATH`

2. **Runtime injection layer (managed tasks/services).**  
   Services do not read plaintext secret values from repo config or image defaults.  
   Runtime resolves pinned SSM paths and injects values into task runtime environment.

3. **Evidence layer (non-secret only).**  
   Evidence artifacts record **path names, presence checks, role simulation outcomes, and pass/fail verdicts**.  
   They never persist decrypted secret values.

This gives deterministic bootstrap while preserving secret hygiene and auditability.

### 2) What is forbidden (hard fail, not warning)

The migration posture explicitly prohibits baked-secret patterns.  
If any occurs, phase closure is blocked.

Forbidden surfaces:

1. Secret literals embedded in Docker `ARG`/`ENV` at build time.
2. Copying `.env`, `.env.*`, ad hoc credential files, or token dumps into image layers.
3. Printing secret material into build logs/artifacts.
4. Treating execution-role credentials as application secret-read authority.
5. Publishing decrypted values in evidence JSON, logbooks, or implementation docs.

Packaging and security checks were pinned to detect these conditions and fail closed.

### 3) Role boundary model for secret access (least-privilege intent)

Role boundaries are explicit:

1. **Execution role boundary (`ROLE_ECS_TASK_EXECUTION`).**  
   Pull/log role only; it is **not** an app secret-read role.

2. **App/runtime role boundary (lane/task roles).**  
   App roles get path-scoped `ssm:GetParameter` only for required pinned secret paths.

3. **Provision role boundary (Terraform/apply roles).**  
   Provisioning roles can materialize/update required paths but do not become runtime app principals.

This prevents the common anti-pattern where broad execution roles silently become secret superusers.

### 4) How least privilege is verified (not assumed)

I used both existence checks and policy-behavior checks.

#### A) Required secret surface exists

Checks validate required SSM paths are present/readable at canonical handles for the active environment.

#### B) Role boundary behavior is simulated

IAM simulation was run against pinned secret parameter ARNs:

1. app role allowed count: `6/6`,
2. execution role allowed count: `0/6` (`implicitDeny`).

This is the strongest proof that least privilege is real, not just declared in a policy file.

#### C) Evidence artifacts capture results

Two key artifacts were produced:

1. `security_secret_injection_checks.json` (packaging-time anti-leak + runtime secret contract checks),
2. `secret_surface_check.json` (M2 secret materialization + IAM boundary verification snapshot).

These artifacts are published in local and durable evidence roots and are non-secret by design.

### 5) Fail-closed behavior on secret/bootstrap violations

Secret/bootstrap is a blocker lane.  
Progression halts when any of the following is true:

1. required SSM path missing/unreadable,
2. role boundary not verifiable,
3. execution role has unexpected secret-read allowance,
4. leakage/baked-secret signal detected in packaging surfaces.

Operationally, this happened in M2.E: missing DB/IG SSM paths and absent runtime roles blocked closure until demo stack materialized required paths/roles and IAM simulation passed.

### 6) Why this is strong migration engineering

This is not "we stored secrets in cloud."  
It is a complete secret/bootstrap control system:

1. canonical secret handles,
2. strict prohibition of baked secrets,
3. explicit runtime vs execution role boundaries,
4. machine-checkable least-privilege verification,
5. non-secret evidence artifacts for audit and replay.

That is the exact posture recruiters expect when they ask whether migration security and operations were handled rigorously.

## Q8) Give one migration incident: what broke, how you detected it, what changed, what evidence proved closure

I’ll use a real M4 incident because it captures the core migration risk: **declaring runtime readiness before IAM wiring is truly materialized**.

### Incident summary (one line)

At M4.C (IAM binding validation), the run failed closed because service->role handles were pinned in design but **not materialized as real IAM roles** in the substrate yet.

### 1) What broke

Run context:

1. M4 working run: `m4_20260214T121004Z`.
2. Validation lane: `M4.C` (service-role binding + dependency access posture checks).

Failure posture:

1. `overall_pass=false` on first M4.C execution.
2. Active blockers:
   - `M4C-B4`: unmaterialized lane role handles (`ROLE_IG_SERVICE`, `ROLE_RTDL_CORE`, `ROLE_DECISION_LANE`, `ROLE_CASE_LABELS`, `ROLE_ENV_CONFORMANCE`),
   - `M4C-B1`: invalid/unresolved mapped app-role bindings,
   - `M4C-B2`: dependency access policy posture not verifiable while roles are missing.

What this meant operationally:

1. We could not defensibly claim managed daemon readiness.
2. Advancing to M4.D/M4.E would have been a false-green progression.

### 2) How I detected it

Detection was deterministic, not manual impression:

1. M4.C consumed the already-closed M4.B service map and checked each mapped service against materialized IAM role surfaces.
2. It produced `m4_c_iam_binding_snapshot.json` with fail-closed verdict and explicit blocker list.
3. AWS role presence checks showed only baseline roles existed; lane-specific roles required by the service map were absent.

So the failure wasn’t “one service won’t start.”  
It was a structural migration contradiction: **authority says these services exist, substrate lacks the identities they require**.

### 3) What I changed

I fixed it at substrate and registry levels, not by weakening the gate.

#### A) Terraform demo-stack expansion (materialization fix)

1. Added deterministic lane-role resources for all required role handles.
2. Added lane-scoped app-role secret-read policies (path-scoped, not broad wildcard reads).
3. Exposed concrete role outputs so M4.C can validate against live materialized values.

#### B) Registry/runtime handle closure

1. Pinned concrete lane role values into migration authority handles.
2. Explicitly included `ROLE_ENV_CONFORMANCE` for `SVC_ENV_CONFORMANCE` to close an ambiguity gap before rerun.

#### C) Gate discipline preserved

1. I did **not** bypass M4.C.
2. I re-ran M4.C against live Terraform outputs and AWS IAM state after materialization.

### 4) What evidence proved closure

The closure proof is a sequence, not one file:

1. **Fail snapshot (before fix):**
   - `runs/dev_substrate/m4/20260214T121004Z/m4_c_iam_binding_snapshot.json`
   - showed `overall_pass=false` with `M4C-B1/B2/B4`.

2. **Materialization evidence (during fix):**
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_role_materialization.plan.txt`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_role_materialization.apply.txt`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_demo_outputs_after_apply.json`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_lane_role_policy_surface.json`

3. **Pass snapshot (after fix):**
   - updated M4.C pass evidence for same control run lane (blockers cleared),
   - fresh verification rerun:
     - `runs/dev_substrate/m4/20260214T134520Z/m4_c_iam_binding_snapshot.json`
   - showed PASS maintained with empty blocker set.

4. **Durable evidence mirrors** were published to the dev_min evidence bucket under matching M4 execution prefixes.

### 5) Why this incident is a strong migration signal

This incident demonstrates the exact behavior recruiters look for:

1. **Fail-closed governance under pressure** (no progression with unresolved identity contracts).
2. **Root-cause correction at the right layer** (Terraform + role policy surfaces), not ad hoc runtime hacks.
3. **Executable proof of closure** (fail snapshot -> materialization artifacts -> pass rerun), not narrative-only claims.

In plain terms: I prevented a cloud migration false-positive by enforcing identity realism before runtime launch, then proved the fix with replayable evidence.

## Recruiter Pin Patch (Round 1 Closure)

### 1) Authority stack file pins (exact filenames)

1. Core platform law:
   - `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
   - `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`
2. Dev-min migration authority:
   - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
   - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
3. Local-parity semantic source truth:
   - `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
   - `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
   - `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`

### 2) M0-M3 closeout roots (exact paths)

1. M0 closure is governance/doc-first (no runtime `runs/dev_substrate/m0/...` root was produced):
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
2. M1 closeout root:
   - `runs/dev_substrate/m1_build_go/20260213T114002Z/`
3. M2 closeout root:
   - `runs/dev_substrate/m2_j/20260213T205715Z/`
4. M3 closeout root:
   - `runs/dev_substrate/m3/20260213T221631Z/`

### 3) M1 packaging evidence (full paths)

1. `runs/dev_substrate/m1_build_go/20260213T114002Z/packaging_provenance.json`
2. `runs/dev_substrate/m1_build_go/20260213T114002Z/build_command_surface_receipt.json`
3. `runs/dev_substrate/m1_build_go/20260213T114002Z/security_secret_injection_checks.json`
4. `runs/dev_substrate/m1_build_go/20260213T114002Z/ci_m1_outputs.json`

### 4) Terraform stacks and evidence-script roots (repo paths)

1. `infra/terraform/dev_min/core`
2. `infra/terraform/dev_min/confluent`
3. `infra/terraform/dev_min/demo`
4. `tools/dev_substrate`

### 5) Secret/IAM simulation evidence roots (exact paths)

1. M2 secret surface + IAM simulation:
   - `runs/dev_substrate/m2_e/20260213T141419Z/secret_surface_check.json`
   - key pass counters in-file:
     - `checks.iam_simulation.app_role_allowed_count = 6`
     - `checks.iam_simulation.execution_role_allowed_count = 0`
2. M1 anti-leak + secret-injection packaging checks:
   - `runs/dev_substrate/m1_build_go/20260213T114002Z/security_secret_injection_checks.json`
   - key pass field:
     - `verdict = "PASS"`

### 6) M4.C pass snapshot closure keys (exact path + fields)

1. Pass snapshot:
   - `runs/dev_substrate/m4/20260214T134520Z/m4_c_iam_binding_snapshot.json`
2. Closure keys:
   - `overall_pass = true`
   - `blockers = []`
3. Durable mirror:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m4_20260214T134520Z/m4_c_iam_binding_snapshot.json`

### 7) Budget and teardown snapshot pins (exact filenames)

1. M2.I budget guardrail snapshot:
   - `runs/dev_substrate/m2_i/20260213T201427Z/budget_guardrail_snapshot.json`
2. M2.I teardown viability snapshot:
   - `runs/dev_substrate/m2_i/20260213T201427Z/teardown_viability_snapshot.json`
3. Cost guardrail snapshot family (supporting budget evidence):
   - `runs/dev_substrate/cost_guardrail/20260213T201456Z/cost_guardrail_snapshot.json`

## Embedded Evidence Index (Answer-Doc Native)

This section embeds the key evidence anchors directly in this answer doc so review does not depend on a separate file.

### Authority files

1. `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
2. `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
4. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
5. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
6. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
7. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`

### M0-M3 evidence roots

1. M0 governance closure (doc-first):
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
2. M1:
   - `runs/dev_substrate/m1_build_go/20260213T114002Z/`
3. M2:
   - `runs/dev_substrate/m2_j/20260213T205715Z/`
4. M3:
   - `runs/dev_substrate/m3/20260213T221631Z/`

### M1 packaging evidence

1. `runs/dev_substrate/m1_build_go/20260213T114002Z/packaging_provenance.json`
2. `runs/dev_substrate/m1_build_go/20260213T114002Z/build_command_surface_receipt.json`
3. `runs/dev_substrate/m1_build_go/20260213T114002Z/security_secret_injection_checks.json`
4. `runs/dev_substrate/m1_build_go/20260213T114002Z/ci_m1_outputs.json`

### Terraform and script roots

1. `infra/terraform/dev_min/core`
2. `infra/terraform/dev_min/confluent`
3. `infra/terraform/dev_min/demo`
4. `tools/dev_substrate`

### Secret and IAM evidence

1. `runs/dev_substrate/m2_e/20260213T141419Z/secret_surface_check.json`
2. `runs/dev_substrate/m1_build_go/20260213T114002Z/security_secret_injection_checks.json`
3. Key fields:
   - `checks.iam_simulation.app_role_allowed_count = 6`
   - `checks.iam_simulation.execution_role_allowed_count = 0`
   - `overall_pass = true`
   - `verdict = "PASS"`

### M4.C incident closure chain

1. Fail:
   - `runs/dev_substrate/m4/20260214T121004Z/m4_c_iam_binding_snapshot.json`
2. Materialization:
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_role_materialization.plan.txt`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_role_materialization.apply.txt`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_demo_outputs_after_apply.json`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_lane_role_policy_surface.json`
3. Pass:
   - `runs/dev_substrate/m4/20260214T134520Z/m4_c_iam_binding_snapshot.json`
   - `overall_pass = true`
   - `blockers = []`
4. Durable pass mirror:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m4_20260214T134520Z/m4_c_iam_binding_snapshot.json`

### Budget and teardown evidence

1. `runs/dev_substrate/m2_i/20260213T201427Z/budget_guardrail_snapshot.json`
2. `runs/dev_substrate/m2_i/20260213T201427Z/teardown_viability_snapshot.json`
3. `runs/dev_substrate/cost_guardrail/20260213T201456Z/cost_guardrail_snapshot.json`
