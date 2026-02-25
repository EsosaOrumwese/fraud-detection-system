# Platform Handoff Lawbook
Generated: 2026-02-25 13:41:44 +00:00  
Scope: This file is the dedicated operating contract for any new chat taking over this workspace.

## 0) How To Use This Lawbook
1. Read this file fully before running commands.
2. Treat all `LAW` entries as fail-closed requirements.
3. Treat all `GUIDE` entries as mandatory working posture unless superseded by a newer explicit user direction.
4. For any conflict: preserve safety, preserve pinned decisions, preserve runtime truth ownership, then ask user to resolve the conflict.
5. Do not mark any phase green if any fail-closed law is violated.

## 1) Law Inventory (Count = 24)

### A) Binding laws from AGENTS and platform authority (14)

#### LAW 1: Scope Boundary (Engine Black Box)
Source: `AGENTS.md` scope section  
Rule: Treat Data Engine as sealed/black-box for platform work unless user explicitly asks for engine changes.  
Must do: Use `docs/model_spec/data-engine/interface_pack` as boundary contract.  
Fail-closed trigger: You need engine internals for platform closure without explicit user approval.

#### LAW 2: Platform Focus
Source: `AGENTS.md` scope/focus  
Rule: Prioritize dev substrate migration/promotion work while preserving existing rails/contracts/truth ownership boundaries.  
Must do: Keep work aligned to active track and phase plans.  
Fail-closed trigger: Work drifts into unrelated refactors without authority.

#### LAW 3: Drift Sentinel
Source: `AGENTS.md` 2.5  
Rule: Continuously assess design-intent vs runtime behavior at each substantial step.  
Must do: Cross-check against design flow, pinned decisions, active phase DoDs.  
Fail-closed trigger: Material mismatch detected or suspected.

#### LAW 4: Drift Escalation (Stop-On-Drift)
Source: `AGENTS.md` 2.5  
Rule: On detected/suspected drift, stop implementation and escalate immediately.  
Must do: Report severity, impacted components/planes, runtime consequence, and wait for user go/no-go.  
Fail-closed trigger: Continuing execution after drift detection.

#### LAW 5: Decision Completeness (No Assumptions)
Source: `AGENTS.md` 2.5  
Rule: When user says “proceed”, verify all required decisions/inputs are pinned first.  
Must do: List unresolved holes and block execution until closed.  
Fail-closed trigger: Defaulting/improvising missing decisions.

#### LAW 6: Phase Coverage (Anti-Cram)
Source: `AGENTS.md` 2.5  
Rule: Expose all required capability lanes before execution starts.  
Must do: Cover authority/handles, IAM, network, storage, messaging, secrets, observability/evidence, rollback/rerun, teardown, budget.  
Fail-closed trigger: Discovering missing lane mid-execution and continuing anyway.

#### LAW 7: Branch Governance (User Controlled)
Source: `AGENTS.md` 2.5  
Rule: No branch-history operation without explicit user go-ahead and confirmed branch method.  
Must do: Restate exact branch sequence and wait for confirmation.  
Fail-closed trigger: Any branch create/switch/merge/rebase/cherry-pick/reset/push/PR operation without explicit user approval.

#### LAW 8: Performance-First
Source: `AGENTS.md` 2.6  
Rule: Performance is first-class and designed before coding.  
Must do: Document complexity, data structures, IO/memory model, alternatives rejected, expected budgets.  
Fail-closed trigger: Accepting long runtime without bottleneck analysis or optimization plan.

#### LAW 9: Runtime Budget Gate
Source: `AGENTS.md` 2.6  
Rule: Every phase needs runtime budgets and measured elapsed evidence.  
Must do: Track before/after evidence and improvement trajectory.  
Fail-closed trigger: Closing phase without speed evidence or explicit waiver.

#### LAW 10: Cost-Control First-Class
Source: `AGENTS.md` 2.7  
Rule: Green means correctness plus spend discipline.  
Must do: Publish spend envelope and closure receipt mapping spend to outcomes.  
Fail-closed trigger: Advancing phase with unexplained/unattributed spend.

#### LAW 11: Idle-Safe Default
Source: `AGENTS.md` 2.7  
Rule: Non-active lanes must be stopped (`desired_count=0` or equivalent).  
Must do: Teardown/stop inactive resources in dev windows.  
Fail-closed trigger: Leaving cost-bearing idle runtime up without approved exception.

#### LAW 12: Cross-Platform Billing Visibility
Source: `AGENTS.md` 2.7  
Rule: Capture all in-scope billing surfaces, not AWS-only when others are active.  
Must do: Include Confluent/Databricks when in scope.  
Fail-closed trigger: Cost guardrail run missing an active billing surface.

#### LAW 13: Implementation-Map Audit Trail
Source: `AGENTS.md` implementation maps section  
Rule: Record detailed reasoning trail during execution, append-only.  
Must do: Capture assumptions, alternatives, decision criteria, mechanics, risks, validations as work progresses.  
Fail-closed trigger: Retrospective-only summaries with missing live decision trail.

#### LAW 14: Logbook Discipline
Source: `AGENTS.md` implementation maps section  
Rule: Log every decision/action in `docs/logbook` with local time.  
Must do: Keep logbook and implementation-map entries synchronized with real execution.  
Fail-closed trigger: Unlogged execution steps that materially alter runtime posture.

### B) Mandatory operating guides from AGENTS (6)

#### GUIDE 15: Reading-Order Bootstrapping
Source: `AGENTS.md` reading order  
Rule: Rehydrate context through platform-wide docs, interface pack, narratives, component authorities, implementation maps, and repo scan.  
Execution intent: Avoid local optimization decisions that contradict system architecture.

#### GUIDE 16: Test-Yourself Ownership
Source: `AGENTS.md` test-yourself policy  
Rule: Own and run a design-validating test plan; do not rely on implicit validation.  
Execution intent: Every phase closure should have explicit evidence.

#### GUIDE 17: Production-Pattern Bias
Source: `AGENTS.md` + user direction  
Rule: For dev_full, choose production-pattern managed/hybrid lanes unless explicitly pinned otherwise.  
Execution intent: Avoid “toy” posture and preserve production parity trajectory.

#### GUIDE 18: Truth-Ownership Preservation
Source: `AGENTS.md` implementation doctrine  
Rule: Respect ownership boundaries across SR/IG/EB/DLA/LS/Registry/AL/etc.  
Execution intent: No hidden coupling or responsibility bleed between components.

#### GUIDE 19: Provenance-First Outputs
Source: `AGENTS.md` implementation doctrine  
Rule: Cross-component outputs must carry pins/version/evidence refs for replay/audit.  
Execution intent: Deterministic reruns and post-hoc forensics remain possible.

#### GUIDE 20: Sensitive Artifact Hygiene
Source: `AGENTS.md` sensitive artifacts section  
Rule: Never commit or paste secrets/capability tokens from runtime artifacts to docs/logs/plans.  
Execution intent: Preserve operational security and secret hygiene.

### C) Repeated chat-derived directives (hard constraints in this workspace) (4)

#### DIRECTIVE 21: Continuous Documentation During Work
Source: repeated user instruction across phases  
Rule: Document reasoning and alternatives during implementation, not just before/after.  
Must do: Add entries as decisions evolve.  
Fail-closed trigger: Long execution windows with no trail until completion.

#### DIRECTIVE 22: No Branch Rigmarole
Source: repeated user branch constraints  
Rule: Do not branch-hop or perform branch operations unless explicitly asked and confirmed.  
Must do: Stay on active branch by default.  
Fail-closed trigger: Any unapproved branch-history operation.

#### DIRECTIVE 23: Commit Scope Discipline
Source: repeated user correction  
Rule: Commit only the files relevant to the active task; avoid unrelated files.  
Must do: Keep commits atomic and conventional (`fix:`, `ci:`, etc.) when committing is requested.  
Fail-closed trigger: Committing user-unrelated files or surprise scope.

#### DIRECTIVE 24: Managed-Path Execution Preference
Source: repeated user correction during migration phases  
Rule: For managed substrate phases, prefer IaC/workflow/runtime lanes; avoid ad-hoc local scripts for core runtime behavior.  
Must do: Use managed controls to prove phase semantics.  
Fail-closed trigger: Closing managed-lane phase with local-only shortcuts.

## 2) Branching Principle For Workflow Merges To Main
This is the preserved branch method that keeps forward merges viable and avoids branch-history damage.

### Canonical path
1. Start workflow work on `migrate-dev`.
2. Commit workflow changes on `migrate-dev`.
3. Merge `migrate-dev` forward into `dev`.
4. Push `dev` to `origin/dev`.
5. Open PR `origin/dev -> origin/main` and merge on GitHub.
6. Sync local `main` from `origin/main` (fast-forward preferred).
7. Merge `main` back into `dev` (to absorb PR merge commit history).
8. Merge `dev` back into `migrate-dev` so the chain remains aligned.

### Guardrails
1. Never push workflow changes directly from `migrate-dev` to `main`.
2. Never delete `main`, `dev`, or `migrate-dev`.
3. Never perform branch-hop/rebase/reset/cherry-pick without explicit user confirmation.
4. If merge conflict or divergence appears, stop and ask user before recovery operations.

### Post-merge verification
1. Branch topology still supports forward merge: `migrate-dev -> dev -> main`.
2. Local branches track intended remotes (`origin/migrate-dev`, `origin/dev`, `origin/main`).
3. No stale temporary remote branches remain after `git fetch --all --prune`.

## 3) Branch State Resolution Snapshot (this handoff)
1. Local branches present:
   - `migrate-dev`
   - `dev`
   - `main`
2. Remote branches present:
   - `origin/migrate-dev`
   - `origin/dev`
   - `origin/main`
3. `git fetch --all --prune` was run and stale `origin/ops/m9g-workflow-only` tracking reference was removed.
4. Forward-merge route remains intact.

## 4) Quick Execution Contract for the Next Chat
1. Rehydrate context from AGENTS + active track build plans before making changes.
2. Ask “what is still unpinned?” before every `proceed`.
3. Keep branch operations blocked unless user explicitly approves exact sequence.
4. Append implementation-map and logbook entries as decisions are made.
5. Enforce performance and cost gates as closure criteria, not post-processing.
6. Keep non-active resources down unless explicitly approved to stay up.
7. Fail closed on drift, ambiguous ownership, or missing evidence.

