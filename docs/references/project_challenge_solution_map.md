# Project Challenge Solution Map (Batch Mode)

Purpose: map challenge IDs from `docs/references/project_challenge_inventory.md` to the actual solution adopted, with explicit status and evidence.

Status keys:
- `Resolved`: adopted and evidenced in repo history/implementation notes.
- `Partial`: direction was adopted, but implementation closure remained incomplete in the deprecated track (or was superseded mid-way).
- `Superseded`: old path replaced by a new architecture path (solution exists through replacement, not patching old code directly).
- `Open`: challenge is diagnosed and/or planned, but remediation execution evidence is not yet materialized.

---

## Batch 1 - Deprecated Data-Gen (IDs 1-12)

### ID 1 - Monolithic and rigid architecture
Solution adopted: moved from monolithic `TransactionSimulator` shape to split entry/core/CLI/catalog flow (`generate.py` legacy entrypoint calling modular core/CLI surfaces).
Status: `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:84`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:86`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:88`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:6`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:17`

### ID 2 - Data realism and schema fidelity gaps
Solution adopted: introduced dedicated catalog-prep and realism tracks (`v2` catalog generation path, catalog load/sampling surfaces) and later replaced with Data Engine realism/gate discipline.
Status: `Superseded` (deprecated generator) / `Open` realism debt (engine wave backlog).
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:122`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:124`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:126`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:128`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:65`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:82`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:93`

### ID 3 - Filename vs orchestrator identity mismatch
Solution adopted: old generator identified this as a fix item (`execution_date` alignment). Final production path moved to deterministic run identity in Data Engine/Platform rails instead of patching legacy naming flow.
Status: `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:109`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_former_data_gen.md:448`
- `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md:3300`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3129`

### ID 4 - CWD-relative schema path portability failures
Solution adopted: promoted config-driven loading (`--config`, validated config model) and then hardened schema-resolution behavior in the engine pipeline.
Status: `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:107`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:20`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:34`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:38`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:317`

### ID 5 - Validation approach not scale-safe (GE OOM)
Solution adopted: deprecated path flagged streaming/tunable validation direction; replacement path uses gate/receipt-based validation law instead of loading full datasets into a single in-memory validator flow.
Status: `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:140`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:18`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_map.md:13`

### ID 6 - Thin observability and drift detection
Solution adopted: structured metrics/logging was explicitly planned in deprecated backlog, then replaced by stronger gate receipts and audit-first evidence in engine/platform tracks.
Status: `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:133`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_map.md:83`

### ID 7 - Duplicated upload responsibilities
Solution adopted: deprecated backlog pinned sink abstraction; current split flow centralizes optional upload behavior under CLI-controlled post-processing path.
Status: `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:88`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:273`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:287`

### ID 8 - Hard-coded config instead of schema-driven controls
Solution adopted: config schema + validation + CLI override posture (`load_config`, validated config model, runtime overrides).
Status: `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:93`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:95`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:20`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:34`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:38`

### ID 9 - RNG reproducibility/debugging control weakness
Solution adopted: explicit task to remove global seeding and persist seed; in split flow, seed is carried through chunk-generation interfaces and logged in runtime settings.
Status: `Partial` in deprecated track, then `Superseded` by engine/path replacement.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:100`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:102`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:49`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:143`

### ID 10 - Path/naming deterministic hardening for orchestration
Solution adopted: explicit hardening items were pinned (robust schema path, execution-date alignment, idempotent upload behavior) and then absorbed into the replacement architecture path.
Status: `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:107`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:109`
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:111`

### ID 11 - Idempotency/retry posture underdefined for local-vs-S3
Solution adopted: explicit idempotent upload logic was planned; split architecture includes centralized optional upload + failure handling posture, while later platform tracks adopted stricter fail-closed/evidence-first delivery semantics.
Status: `Partial` in deprecated track, then `Superseded`.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:111`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:273`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:287`

### ID 12 - Repeated architecture switching before final direction
Solution adopted: formal migration from former monolithic architecture to staged current architecture, then full replacement by Data Engine contract/gate backbone.
Status: `Resolved` as an architectural transition.
Evidence:
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_former_data_gen.md:1`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:1`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:17`
- `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:65`

## Batch 2 - Data Engine Challenges (IDs 13-24)

### ID 13 - 6B strict schema-compliance gauntlet
Solution adopted: kept strict schema posture (`additionalProperties: false` style compliance) and iteratively corrected 6B policy/config payloads and schema-pack defects rather than loosening validators.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_6B.impl_actual.md:8`
- `docs/model_spec/data-engine/implementation_maps/segment_6B.impl_actual.md:130`
- `docs/model_spec/data-engine/implementation_maps/segment_6B.impl_actual.md:151`
- `docs/model_spec/data-engine/implementation_maps/segment_6B.impl_actual.md:173`
- `docs/model_spec/data-engine/implementation_maps/segment_6B.impl_actual.md:220`

### ID 14 - Border ambiguity in timezone assignment
Solution adopted: formalized deterministic handling path: retain override precedence, use country-singleton when valid, and avoid silent unresolved rows.
Status: `Resolved (with documented controlled deviation path)`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:696`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3030`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3036`

### ID 15 - Immutability collisions after timezone policy change
Solution adopted: locked identity posture to upstream `manifest_fingerprint` (audit digest separated), then used reseal/rerun workflow under write-once rules instead of mutating existing partitions.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:777`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:824`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:829`

### ID 16 - Deterministic nearest-polygon fallback
Solution adopted: implemented same-ISO nearest-polygon fallback with threshold derived from sealed epsilon, plus explicit audit/report counters and warning lanes.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3041`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3042`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3087`
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3096`

### ID 17 - world_countries ISO coverage gaps
Solution adopted: rebuilt reference coverage pipeline using robust ISO mapping fallback (ISO_A2/ISO_A3/ADM0_A3) plus synthetic fill for absent codes; regenerated 2024 reference artifacts to 251 ISO2 coverage.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:563`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:571`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:609`

### ID 18 - PROJ/GDAL runtime mismatch blocking CRS resolution
Solution adopted: added runtime guard to inspect `proj.db` layout and override `PROJ_LIB`/`PROJ_DATA` to pyproj’s bundled data when incompatible.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:621`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:642`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:648`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:651`

### ID 19 - Invalid geometry + antimeridian TopologyException
Solution adopted: split fix into data and algorithm lanes: enforce input geometry validity with deterministic error mapping, repair reference build pipeline, and normalize shifted 0..360 geometry during antimeridian split.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:732`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:741`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:778`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:786`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:793`
- `docs/model_spec/data-engine/implementation_maps/segment_1B.impl_actual.md:803`

### ID 20 - Repeated `IO_WRITE_CONFLICT` under write-once truth
Solution adopted: preserved write-once invariants; when sealed inputs changed, used explicit scoped cleanup + reseal flow for the affected fingerprint/run outputs rather than overwriting.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:631`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:635`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:643`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:808`

### ID 21 - Repeated reseal collisions in 2B (`2B-S0-080`)
Solution adopted: established deterministic rerun behavior by combining scoped re-emit cleanup with stable receipt timestamp sourcing from `run_receipt.created_utc`.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:417`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:423`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:3519`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:3530`

### ID 22 - `created_utc` coupling broke downstream validation after reseal
Solution adopted: required downstream S1-S4 regeneration after S0 reseal for run-local timestamp consistency before S5 progression.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:3504`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:3509`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:3512`

### ID 23 - Need for atomic JSON writes in late segments
Solution adopted: introduced shared stable latest-run-receipt selection helper and switched late-state JSON emission to tmp+replace atomic writes in 6A/6B.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_6A.impl_actual.md:1141`
- `docs/model_spec/data-engine/implementation_maps/segment_6A.impl_actual.md:1159`
- `docs/model_spec/data-engine/implementation_maps/segment_6B.impl_actual.md:1072`
- `docs/model_spec/data-engine/implementation_maps/segment_6B.impl_actual.md:1093`

### ID 24 - Early schema/config parse blockers before compute
Solution adopted: fixed malformed 5B schema-pack YAML structures (`group_id` indentation defects) so S0 validation can start instead of failing at parse time.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:484`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:491`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:501`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:513`

---

## Batch 3 - Data Engine Challenges (IDs 25-36)

### ID 25 - Repeated `BrokenProcessPool` crashes masking root causes
Solution adopted: converted silent worker death into actionable diagnostics by wrapping batch workers with structured error payloads (`type`, `message`, `traceback`) and propagating that context to the parent abort path; this exposed whether failures were Python errors or native/OOM crashes.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:2728`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:2931`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:2945`

### ID 26 - Host OOM at higher concurrency
Solution adopted: moved to a safe baseline for worker/inflight/buffer posture while keeping shared-map acceleration, then validated the stability-first defaults before further performance redesign.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3049`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3064`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3087`

### ID 27 - Pure-Python throughput missed target envelopes
Solution adopted: selected a compiled-kernel path (Numba) for the per-arrival hot loop, with deterministic RNG/routing invariants kept explicit in the plan.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3280`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3297`

### ID 28 - Toolchain dependency conflicts (Python/numba/numpy/feast)
Solution adopted: aligned dependency constraints and runtime environment to keep compiled execution viable (Py3.12-compatible numba range, numpy `<2.0`, env-level downgrade where required).
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3382`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3393`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:4831`

### ID 29 - Compiled-kernel implementation failures (overflow/typing/warmup-stall)
Solution adopted: applied layered hardening (numba-safe constants, compiled-only key matrices, warmup and progress instrumentation); when stall behavior persisted, added operational heartbeat/fallback posture so runs stayed diagnosable and forward progress continued while redesign proceeded.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3403`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3438`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3595`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:3622`

### ID 30 - Correctness/performance deviations had to be managed explicitly
Solution adopted: documented and enforced a controlled relaxation model: preserve deterministic input order, make strict ordering optional, and use explicit fallback routing paths (with counters/warnings) instead of hard aborting on incomplete group-weight coverage.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:4141`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:4423`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md:4432`

### ID 31 - 3B sealed-input digest mismatch blocked S0 gate
Solution adopted: recomputed Pelias sqlite digest, updated bundle manifest hash to match actual bytes, and reran S0 to restore sealed-input digest invariants.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_3B.impl_actual.md:2406`
- `docs/model_spec/data-engine/implementation_maps/segment_3B.impl_actual.md:2419`

### ID 32 - 2B.S5 day-grid drift (`group_weights_missing`)
Solution adopted: shifted arrival-roster day authority from hardcoded date to policy `start_day`, added `--utc-day` override, and normalized both `utc_day` and `utc_timestamp` during roster repair.
Status: `Partial` (change path documented/applied, but this entry set does not record final rerun PASS for the failing run).
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:4574`

### ID 33 - 2B.S7 alias header/policy mismatch (`slice_header_qbits_mismatch`)
Solution adopted: corrected S7 checks to compare header qbits against alias `record_layout.prob_qbits` (not policy `quantised_bits`) and aligned decode scaling to the same source.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:4074`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:4101`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:4154`

### ID 34 - Polars streaming panics in 2B audit/reconciliation
Solution adopted: removed fragile streaming collection paths in affected 2B flows and used non-streaming parquet reads/collects where dataset size and scope allowed.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:3489`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:4123`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md:4154`

### ID 35 - 5A circular dependency (S0 requiring downstream S1-S3 outputs)
Solution adopted: removed in-segment outputs from S0 required/sealed gate list, then made downstream sealed-row presence optional where appropriate while keeping actual parquet presence + schema checks hard.
Status: `Resolved`.
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md:3212`
- `docs/model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md:3236`
- `docs/model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md:3268`

### ID 36 - 5A policy guardrail mismatch loops with sealed-input immutability
Solution adopted: treated failures as policy-envelope mismatches (not data corruption), adjusted caps/soft-cap behavior in policy + S1 logic, and preserved S0 immutability by requiring reseal/new-run workflow when policy hash changes caused output conflicts.
Status: `Partial` (solution mechanics are implemented, but the cited loop shows iterative tuning with rerun closure still evolving in the recorded thread).
Evidence:
- `docs/model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md:3308`
- `docs/model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md:3323`
- `docs/model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md:3355`
- `docs/model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md:3459`

---

## Batch 4 - Post-Build Realism Program (IDs 37-46)

### ID 37 - Engine realism regraded to `D+` despite structural completion
Solution adopted: formalized a staged realism remediation program (diagnose -> hypothesis/gates -> backlog -> wave runbooks) instead of ad-hoc tuning, treating the `D+` outcome as a governed defect baseline.
Status: `Partial` (program is defined; remediation runs are pending).
Evidence:
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:39`
- `docs/reports/eda/engine_realism_step2_root_cause_trace.md:1`
- `docs/reports/eda/engine_realism_step4_execution_backlog.md:11`

### ID 38 - Critical 6B truth/bank/timeline blockers
Solution adopted: isolated these as Wave-0 blockers (`WP-001..WP-003`) with hard fail-closed gates and strict scope lock to 6B truth surfaces before any downstream wave is allowed.
Status: `Open`.
Evidence:
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:75`
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:76`
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:77`
- `docs/reports/eda/engine_realism_step4_execution_backlog.md:35`
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md:46`

### ID 39 - Critical 3B substrate blockers (uniform edges, weak settlement coherence)
Solution adopted: mapped to explicit high-propagation wave work packages and acceptance gates (merchant-conditioned edge diversity + settlement coherence uplift), intentionally blocked behind Wave-0 completion.
Status: `Open`.
Evidence:
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:62`
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:63`
- `docs/reports/eda/engine_realism_step4_execution_backlog.md:55`

### ID 40 - Broad high-severity realism gaps across many segments
Solution adopted: converted dispersed issues into a single engine-wide severity ledger + ordered execution framework with per-gap gates and cross-wave dependency control.
Status: `Partial` (framework complete; fixes not yet closed).
Evidence:
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:47`
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:54`
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:68`
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:71`
- `docs/reports/eda/engine_realism_baseline_gap_ledger.md:78`
- `docs/reports/eda/engine_realism_step4_execution_backlog.md:11`

### ID 41 - Need explicit root-cause trace (not ad-hoc fixes)
Solution adopted: completed a dedicated Step-2 root-cause trace document for every Critical/High gap with confidence and falsification checks.
Status: `Resolved`.
Evidence:
- `docs/reports/eda/engine_realism_step2_root_cause_trace.md:1`
- `docs/reports/eda/engine_realism_step2_root_cause_trace.md:50`
- `docs/reports/eda/engine_realism_step2_root_cause_trace.md:158`

### ID 42 - Need one-to-one hypotheses + acceptance tests with fail-closed gating
Solution adopted: completed Step-3 hypothesis/acceptance plan covering all gap IDs (`1.1..2.21`) with numeric thresholds and explicit fail-closed run-gating rules.
Status: `Resolved`.
Evidence:
- `docs/reports/eda/engine_realism_step3_hypothesis_acceptance_plan.md:21`
- `docs/reports/eda/engine_realism_step3_hypothesis_acceptance_plan.md:260`
- `docs/reports/eda/engine_realism_step3_hypothesis_acceptance_plan.md:272`

### ID 43 - Need executable remediation scope (not just analysis)
Solution adopted: operationalized remediation into a 26-package backlog with strict dependency-locked wave sequencing and per-wave artifact requirements.
Status: `Resolved`.
Evidence:
- `docs/reports/eda/engine_realism_step4_execution_backlog.md:11`
- `docs/reports/eda/engine_realism_step4_execution_backlog.md:35`
- `docs/reports/eda/engine_realism_step4_execution_backlog.md:39`

### ID 44 - Wave-0 must block all downstream work until critical truth gates clear
Solution adopted: locked Wave-0 runbook with platform-blocking posture, explicit hard-fail criteria, and PASS_WITH_RISK hold behavior that prevents Wave-1 start.
Status: `Resolved` (governance lock defined).
Evidence:
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md:23`
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md:46`
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md:175`
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md:188`

### ID 45 - Wave progression blocked by unresolved risk holds/preconditions
Solution adopted: encoded explicit precondition gates in Wave-1/Wave-2 runbooks so progression cannot happen unless prior waves are PASS with no unresolved risk holds.
Status: `Open`.
Evidence:
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md:188`
- `docs/reports/eda/engine_realism_step6_wave1_execution_runbook.md:25`
- `docs/reports/eda/engine_realism_step7_wave2_execution_runbook.md:28`

### ID 46 - Missing wave execution evidence directory
Solution adopted: mandatory evidence artifact contracts were defined for each wave path (`wave_0/1/2`) under `docs/reports/eda/engine_realism_wave_evidence/`, but repository check still shows the base path absent.
Status: `Open`.
Evidence:
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md:156`
- `docs/reports/eda/engine_realism_step6_wave1_execution_runbook.md:184`
- `docs/reports/eda/engine_realism_step7_wave2_execution_runbook.md:179`
- local path check result: `MISSING docs/reports/eda/engine_realism_wave_evidence`

---

## Batch 5 - Local Parity Control & Ingress (IDs 47-58)

### ID 47 - Event Bus ownership boundary initially blurred
Solution adopted: moved EB contract/interface ownership out of IG into a shared `event_bus` module, and locked receipt shape for cross-adapter compatibility (file-bus + Kinesis).
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:54`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:131`

### ID 48 - EB offset recovery stale-head correctness risk
Solution adopted: hardened file-bus recovery so append log is source of truth (head is rebuilt/ignored when inconsistent), preventing stale offset resurrection.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:195`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:255`

### ID 49 - EB publish failure accounting lacked explicit degrade posture
Solution adopted: instrumented IG-side publish-failure accounting for both handled/unhandled failures and preserved ACK timestamps in duplicate flows so health can degrade deterministically.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:345`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:361`

### ID 50 - Oracle Store truth-ownership boundary drift risk
Solution adopted: reasserted Oracle Store as external immutable engine truth, with explicit Engine -> Oracle -> WSP chain and removal of SR-coupled oracle pathways.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:19`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:254`

### ID 51 - Seal strictness needed environment split without breaking fail-closed intent
Solution adopted: enforced environment-sensitive posture: local parity allows transitional seal warnings, while dev/prod default to strict seal enforcement with explicit reason codes.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:91`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:107`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:122`

### ID 52 - Oracle packer idempotency/collision handling under write-once law
Solution adopted: implemented create-if-absent write-once manifest/seal behavior, fail-on-different-content conflicts, then fixed idempotency comparison to ignore non-identity timestamps.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:202`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:219`

### ID 53 - Object-store endpoint/credential wiring failures in Oracle sync/seal flow
Solution adopted: made endpoint/credential propagation explicit in make targets and simplified operator flow with a dedicated `platform-oracle-sync` path for MinIO parity runs.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:334`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:354`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:362`

### ID 54 - Oracle stream-sort overflow/timeout/reliability risks
Solution adopted: hardened stream-view builder with configurable S3 timeout/retry controls, key-flexible deterministic ordering (including non-`ts_utc` outputs), and memory-safe chunked sorting fallbacks.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:654`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:690`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:792`

### ID 55 - WSP needed fail-closed oracle-boundary hardening
Solution adopted: rebuilt WSP as engine-rooted with explicit world selection and hard fail checks for missing receipt/scenario/gate/traffic-output evidence.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:132`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:180`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:218`

### ID 56 - IG pull-era PARTIAL/time-budget exhaustion pressure
Solution adopted: after bounded-time sharding/uncapped attempts still failed for completion, execution posture was explicitly migrated to push-only ingestion and legacy pull was retired from v0 direction.
Status: `Superseded` (pull path replaced by push-only architecture).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1287`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1337`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1363`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1387`

### ID 57 - IG push-chain schema compatibility failures before stabilization
Solution adopted: fixed row-vs-array schema targeting, fragment `$defs` resolution, docs-root ref loading, and nullable normalization, then validated green admission with no new schema/internal errors.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1786`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1812`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1894`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1911`

### ID 58 - IG parity publish failed due to unresolved env placeholders + endpoint strategy
Solution adopted: resolved env placeholders at profile load, added explicit bus endpoint/region wiring for parity, and confirmed Kinesis publish + receipts in parity smoke.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1998`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2006`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2015`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2027`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2046`

---

## Batch 6 - Local Parity Advanced Ingress + RTDL Foundations (IDs 59-69)

### ID 59 - IG dedupe semantics insufficient for corridor law
Solution adopted: implemented corridor-aligned semantic dedupe tuple (`platform_run_id`, `event_class`, `event_id`), payload-hash anomaly quarantine, and explicit publish state machine (`PUBLISH_IN_FLIGHT` -> `ADMITTED` / `PUBLISH_AMBIGUOUS`).
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2294`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2306`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2307`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2346`

### ID 60 - IG health stayed `BUS_HEALTH_UNKNOWN` for Kinesis
Solution adopted: added active Kinesis describe-mode health probing (`health_bus_probe_mode=describe`) with explicit GREEN/RED behavior and profile wiring support.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2397`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2450`

### ID 61 - IG receipt provenance drift (`pins.platform_run_id` vs `receipt_ref`)
Solution adopted: bound receipt/quarantine artifact prefixes to envelope `platform_run_id` (not stale service env run id), restoring run-scope provenance coherence.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2458`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2461`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2485`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2491`

### ID 62 - RTDL family misclassification risk in IG (`action_outcome` treated as traffic)
Solution adopted: added startup fail-fast coherence guards validating RTDL class-map/schema-policy alignment and required-pin expectations, with targeted validation tests.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2659`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2667`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2710`

### ID 63 - Scenario Runner parity closure required repeated drift fixes
Solution adopted: closed successive drift threads across parity testing: contract mismatch checks, re-emit fetch semantics, lease-collision handling, WAITING_EVIDENCE catalogue-path normalization, and run-identity/READY idempotency alignment.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2764`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3185`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3203`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3302`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3967`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3999`

### ID 64 - IEG run-scope contamination + missing `platform_run_id` attribution risk
Solution adopted: implemented run-scope hardening at intake/store/query layers (platform_run_id enforcement, run-scoped stream identity, run-scoped dedupe/persistence, graph-scope exposure), then aligned dedupe identity tuple semantics.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:433`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:451`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:482`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:720`

### ID 65 - IEG Postgres crash on reserved identifier `offset`
Solution adopted: quoted reserved identifier usage in IEG migrations/store SQL and revalidated live projector runtime.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:796`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:807`

### ID 66 - CSFB parity wiring needed fail-fast DSN posture
Solution adopted: removed silent SQLite fallback in parity path; missing projection locator now fails fast, preventing backend-class drift.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:85`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1124`

### ID 67 - CSFB needed payload-hash mismatch + replay pin mismatch protections
Solution adopted: enforced transactional dedupe/payload-hash anomaly handling and replay pin mismatch fail-closed ledgering (`REPLAY_PINS_MISMATCH`) with explicit basis-driven replay semantics.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:384`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:470`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:590`

### ID 68 - CSFB live intake Postgres reserved identifier crash
Solution adopted: quoted `offset` in CSFB DDL and SQL write/read paths, then validated join-plane runtime evidence under parity runs.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1127`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1141`

### ID 69 - OFP parity-only backend drift (filesystem defaults vs DB posture)
Solution adopted: pinned local-parity OFP operational path to Postgres-default DSN wiring (profile + launcher + runbook), while preserving explicit SQLite override for non-parity testing.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:9`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:19`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1136`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1159`

---

## Batch 7 - OFP/DF/DLA + Case Trigger (IDs 70-79)

### ID 70 - OFP Phase-8 integration initially blocked by missing DF/DL dependencies
Solution adopted: implemented explicit split-closure governance (`8A` complete now, `8B` blocked on DF/DL) so progress could be safely recorded without pretending full integration closure.
Status: `Resolved` (as managed partial-closure pattern).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:718`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:733`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:744`

### ID 71 - OFP semantic dedupe identity drift (stream-dependent tuple)
Solution adopted: migrated semantic dedupe identity to stream-independent corridor tuple (`platform_run_id`, `event_class`, `event_id`) while retaining transport-level stream dedupe separately.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:989`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1012`

### ID 72 - OFP needed DF-family ignore logic on shared traffic stream
Solution adopted: added explicit early suppression for DF output families (`decision_response`, `action_intent`) with checkpoint advance + ignored counters, preventing unintended OFP mutation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1039`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1075`

### ID 73 - OFP live projector reserved-identifier crash + parity undercount caveat
Solution adopted: fixed reserved SQL identifier handling (`"offset"`), diagnosed early-record loss under `LATEST`, then hardened parity start position to `trim_horizon` and validated 200/200 recovery.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1162`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1176`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1207`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1228`

### ID 74 - OFP health counters produced false red/amber under bounded high-speed replays
Solution adopted: recalibrated local-parity run/operate threshold policy (without changing OFP core semantics) to avoid bounded-run false gating and validated all-green closure on repeated 200-event runs.
Status: `Resolved` (local-parity policy scope).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1291`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1308`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1333`

### ID 75 - DF drift closures (identity/scope/context/replay/schema alignment)
Solution adopted: executed coordinated DF hardening across identity recipe stability, inlet collision guards, scope canonicalization, schema alignment for provenance fields, and local-parity compatibility posture updates.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/decision_fabric.impl_actual.md:963`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_fabric.impl_actual.md:1032`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_fabric.impl_actual.md:1097`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_fabric.impl_actual.md:1242`

### ID 76 - DLA replay safety required divergence detection + checkpoint blocking
Solution adopted: added replay observation ledger semantics (`NEW`/`DUPLICATE`/`DIVERGENCE`) and hard divergence gate (`REPLAY_DIVERGENCE`) that writes anomaly evidence while blocking unsafe checkpoint advancement.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:687`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:740`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:778`

### ID 77 - DLA lineage-scope digest mismatch fail-closed handling
Solution adopted: introduced explicit lineage conflict reasons (`RUN_SCOPE_MISMATCH` vs `RUN_CONFIG_DIGEST_MISMATCH`), persisted digest across lineage/query surfaces, and validated fail-closed mismatch behavior.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1026`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1044`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1057`

### ID 78 - DLA mixed-stream `UNKNOWN_EVENT_FAMILY` noise required lane isolation
Solution adopted: moved local-parity DLA intake to dedicated RTDL stream (`fp.bus.rtdl.v1`) and updated IG routing/policy/runbook wiring accordingly.
Status: `Partial` (wiring and test suite closure done; fresh 200-event runtime evidence for noise reduction explicitly noted as pending).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1166`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1169`

### ID 79 - Case Trigger deterministic collision + retry/checkpoint ambiguity hardening
Solution adopted: implemented replay ledger collision semantics (`NEW`/`REPLAY_MATCH`/`PAYLOAD_MISMATCH`), deterministic checkpoint gating for retry-safe publish outcomes, and parity validation matrix proofs including negative-path evidence.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/case_trigger.impl_actual.md:241`
- `docs/model_spec/platform/implementation_maps/local_parity/case_trigger.impl_actual.md:423`
- `docs/model_spec/platform/implementation_maps/local_parity/case_trigger.impl_actual.md:757`

---

## Batch 8 - Case Mgmt / Label Store / Action Layer / DL / OFS (IDs 80-89)

### ID 80 - Case Mgmt SQLite nested-write hazard in CM->LS handshake
Solution adopted: redesigned handshake sequencing to remove nested write transactions, enforce pending-first semantics, and keep LS outcome ambiguity fail-closed without deadlock-prone coupling.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:474`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:499`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:502`

### ID 81 - Case Mgmt post-closure robustness gap for JSON decode on lookup paths
Solution adopted: hardened lookup parsing with defensive JSON decode handling (`JSONDecodeError` -> safe empty map) plus targeted regression validation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:172`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:177`

### ID 82 - Label Store strict idempotent writer + fail-closed mismatch + conflict timeline handling
Solution adopted: implemented LS writer-boundary idempotency corridor, explicit append-only timeline/read surfaces, and deterministic as-of conflict posture (`RESOLVED/CONFLICT/NOT_FOUND`) with stable precedence rules.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:91`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:223`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:345`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:373`

### ID 83 - Action Layer semantic idempotency, mismatch quarantine, bounded retries, replay/checkpoint gates
Solution adopted: delivered phased AL hardening: semantic idempotency ledger + mismatch quarantine, bounded execution/retry semantics, and explicit checkpoint/replay modules that block commit on ambiguity and preserve replay determinism.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/action_layer.impl_actual.md:166`
- `docs/model_spec/platform/implementation_maps/local_parity/action_layer.impl_actual.md:286`
- `docs/model_spec/platform/implementation_maps/local_parity/action_layer.impl_actual.md:538`
- `docs/model_spec/platform/implementation_maps/local_parity/action_layer.impl_actual.md:573`

### ID 84 - Degrade Ladder missing run-scoped observability exports (`4.6L-02`)
Solution adopted: added worker-tick emission of run-scoped DL metrics/health artifacts with deterministic health-state derivation and validated artifact presence in runtime smoke.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1083`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1111`

### ID 85 - OFS drift risk from missing component build-plan authority
Solution adopted: created and locked a full component-scoped OFS build plan with explicit phased authority gates (including meta-layer blockers), converting platform-level intent into auditable component execution sequence.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:12`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:52`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:61`

### ID 86 - OFS run-control semantics initially underdefined
Solution adopted: implemented durable run ledger + explicit run-state machine + bounded publish-only retry semantics with separate attempt counters to prevent hidden retrain drift.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:168`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:200`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:203`

### ID 87 - OFS fail-closed hardening for replay/feature-profile/immutability drift
Solution adopted: enforced fail-closed replay-basis mismatch handling, feature-profile version locks, and immutable publication corridors for manifests and dataset artifacts (with explicit immutability violation codes).
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:434`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:621`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:666`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:670`

### ID 88 - OFS governance bypass risk in protected-ref enforcement
Solution adopted: applied unconditional fail-closed protected-ref enforcement regardless of config toggle, while retaining audit emission behavior.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:924`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:927`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:940`

### ID 89 - OFS Phase-8 fixture mismatches (`LABEL_TYPE_SCOPE_UNRESOLVED`, `RUN_NOT_FOUND` vs `RETRY_NOT_PENDING`)
Solution adopted: corrected Phase-8 test setup by supplying `filters.label_types` in build intent fixtures and seeding valid non-pending ledger state for retry-negative-path assertions.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:799`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:801`

---

## Batch 9 - Model Factory / Archive Writer / Platform Anti-Drift + Realism Governance (IDs 90-96)

### ID 90 - MF strict request-id mismatch fail-closed + bounded publish-only retry
Solution adopted: implemented MF run-control + durable run-ledger semantics enforcing idempotent submission, hard fail-closed payload drift under same request id (`REQUEST_ID_PAYLOAD_MISMATCH`), and publish-only bounded retries that do not increment full-run attempt counters.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:241`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:259`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:261`

### ID 91 - MF unresolved refs/run-scope/schema incompatibility leakage risk
Solution adopted: introduced explicit by-ref DatasetManifest resolution with contract validation, fail-closed run-scope checks, feature/schema compatibility guards, and immutable resolved-plan publication (`resolved_train_plan`) prior to train/eval execution.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:340`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:354`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:361`

### ID 92 - MF publish handshake identity conflict semantics
Solution adopted: implemented append-only bundle publish handshake keyed by `(bundle_id, bundle_version)` with deterministic idempotent convergence for identical payloads and fail-closed divergence (`PUBLISH_CONFLICT`) for same identity with different bytes.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:623`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:644`

### ID 93 - Archive Writer Postgres reserved identifier crash (`offset`)
Solution adopted: renamed reserved ledger column usage from `offset` to `offset_value` across schema/query surfaces, then revalidated daemon startup and run/operate readiness in local parity.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/archive_writer.impl_actual.md:61`
- `docs/model_spec/platform/implementation_maps/local_parity/archive_writer.impl_actual.md:64`
- `docs/model_spec/platform/implementation_maps/local_parity/archive_writer.impl_actual.md:73`

### ID 94 - Platform anti-drift closure pressure (evidence-first progression blockers)
Solution adopted: codified repeated platform-level pre-change locks and continuation locks that block phase progression unless closure evidence is explicit (not matrix-only), with drift-sentinel checkpoints on MF/OFS corridor transitions.
Status: `Resolved` (as operating governance posture).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:10029`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:10148`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:10424`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:10524`

### ID 95 - Segment remediation packages exist but remain execution-wave work
Solution adopted: authored segment-level remediation specs with exact code/policy deltas, sequence ordering, invariants, and grade-target framing for later execution waves (3A/5B/6A/6B), creating auditable implementation handbooks rather than vague recommendations.
Status: `Planned` (specification complete; execution not yet applied in engine code here).
Evidence:
- `docs/reports/eda/segment_3A/segment_3A_remediation_report.md:325`
- `docs/reports/eda/segment_5B/segment_5B_remediation_report.md:250`
- `docs/reports/eda/segment_6A/segment_6A_remediation_report.md:217`
- `docs/reports/eda/segment_6B/segment_6B_remediation_report.md:245`

### ID 96 - Realism-governance challenge (prove uplift without regression)
Solution adopted: defined wave runbook governance with mandatory cross-seed stability checks, regression-guard packs, ablation attribution rules, and hard stop/go policies before promotion between waves.
Status: `Partial` (governance framework authored; full wave execution evidence still required to close).
Evidence:
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md:185`
- `docs/reports/eda/engine_realism_step6_wave1_execution_runbook.md:172`
- `docs/reports/eda/engine_realism_step7_wave2_execution_runbook.md:168`

---

## Batch 10 - Platform Operational Blockers (IDs 97-104)

### ID 97 - Full dev-completion runs not feasible on local hardware
Solution adopted: formalized the environment-ladder split where local is smoke-only and full completion is executed on stronger dev infrastructure (or future chunked execution), instead of forcing unreliable local completion attempts.
Status: `Resolved` (as explicit operating policy).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:527`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:530`

### ID 98 - Parity smoke IG process using stale installed code (PYTHONPATH drift)
Solution adopted: introduced a dedicated platform runner wrapper with `PYTHONPATH=src` (`PY_PLATFORM`) and switched platform targets to use repo-source execution consistently.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:733`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:742`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:771`

### ID 99 - IG handler regression from methods nested under `_build_indices`
Solution adopted: restored IG class structure by moving `_build_indices` out of accidental nesting and reinstating missing runtime handlers before parity rerun.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:756`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:763`

### ID 100 - WSP READY failure from missing control-bus stream env propagation
Solution adopted: exported `CONTROL_BUS_STREAM/REGION/ENDPOINT_URL` in parity Make targets (plus runbook troubleshooting guidance) so WSP READY consumption has complete control-bus wiring.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1058`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1065`

### ID 101 - WSP READY checkpointing failure from missing checkpoint DSN env
Solution adopted: added and exported `WSP_CHECKPOINT_DSN` parity defaults in WSP ready-consumer targets and documented the failure mode in runbook guidance.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1077`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1084`

### ID 102 - Stream-view identity mismatch between local and MinIO-S3 roots
Solution adopted: made explicit oracle wiring authoritative for parity WSP (`ORACLE_ENGINE_RUN_ROOT`/`ORACLE_ROOT`/`ORACLE_SCENARIO_ID`) and ensured targets export those envs so stream-view identity stays deterministic.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1199`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1202`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1207`

### ID 103 - Run identity correction for WSP envelopes (`scenario_run_id`)
Solution adopted: corrected WSP envelope generation to carry SR `scenario_run_id` while retaining engine `run_id` for provenance, then revalidated end-to-end receipt propagation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1890`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1893`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1912`

### ID 104 - RTDL runtime caveats required explicit root-cause pinning
Solution adopted: recorded a concrete root-cause split with evidence-backed reasons (`schema_version` omission vs IG quarantine causes) and locked an open-drift closure sequence instead of treating caveats as generic runtime noise.
Status: `Resolved` (diagnostic/root-cause pin), with remediation wave explicitly tracked afterward.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3081`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3121`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3122`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3132`

---

## Batch 11 - Platform Runtime Blockers and Recovery (IDs 105-112)

### ID 105 - Cross-component Postgres `offset` identifier bug blocked 200-event RTDL validation
Solution adopted: treated as a cross-plane blocker and patched IEG/OFP/CSFB SQL surfaces to use safe quoted `"offset"` identifiers, then reran live validation and component regressions.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3279`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3305`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3360`

### ID 106 - OFP 194/200 gap from startup-position race
Solution adopted: diagnosed missing first-sequence offsets as start-at-`LATEST` race, changed parity OFP live default to `trim_horizon`, then executed run-scoped replay reconciliation to recover `200/200`.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3399`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3407`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3419`

### ID 107 - Orchestrated launch ownership conflict from stale manual ingress process
Solution adopted: enforced runtime hygiene by terminating non-orchestrated IG listeners occupying ingress port and reasserting orchestrator-owned lifecycle before validation runs.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3847`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3854`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3870`

### ID 108 - Orchestrated packs using system Python caused missing dependency crashes
Solution adopted: introduced env-driven interpreter pinning (`RUN_OPERATE_PYTHON`) in process packs and replaced raw `python` launcher tokens so workers run under project `.venv` by default.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3885`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3888`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3896`

### ID 109 - Run-scope precedence drift (`PLATFORM_RUN_ID` overriding active run truth)
Solution adopted: hardened run-id resolution to prefer `ACTIVE_RUN_ID` sources over stale shell env values, patched make targets/SR reuse flow, and validated active-run artifact scoping after patch.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3936`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3943`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8750`

### ID 110 - Drift sentinel detected incomplete meta-layer coverage before full-platform live run
Solution adopted: executed fail-closed escalation (paused run), then onboarded missing Case/Label and obs/gov daemon coverage into run/operate packs before proceeding with full-platform 20/200 validation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:7828`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:7857`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8201`

### ID 111 - Strict all-green 20/200 validation failed (`OFP`/`DL` red from stale signals/artifact gaps)
Solution adopted: performed staged drift closure (IEG artifact-emission reliability + OFP threshold/env posture fixes in local-parity pack) and repeated 20/200 runs until strict all-green closeout was achieved.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8009`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8017`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8078`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8249`

### ID 112 - DLA decision-lane blocked by Postgres placeholder contract mismatch
Solution adopted: identified DLA Postgres placeholder incompatibility as a hard parity blocker, patched SQL placeholder behavior to backend-correct binding semantics, then continued parity gates only after this unblock.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8430`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8441`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8455`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8501`

---

## Batch 12 - Control-Bus/Backlog and Postgres Lifecycle Hardening (IDs 113-120)

### ID 113 - WSP control-bus starvation from repeated TRIM_HORIZON head-page reads
Solution adopted: diagnosed control-bus iterator starvation semantics and hardened READY-consumption behavior to preserve iterator progress/paging continuity, with focused WSP reader tests and subsequent parity gate confirmation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8465`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8489`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8624`

### ID 114 - RTDL backlog starvation + inflated `LATE_CONTEXT_EVENT` noise from trim-horizon traversal
Solution adopted: treated local-parity backlog traversal as runtime-drift risk, adopted active-run-focused start-position posture for bounded validation windows, and carried it forward with shared consumer resilience so current-run processing no longer starves behind historical backlog.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8498`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8512`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8522`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8999`

### ID 115 - CaseMgmt/LabelStore shared Postgres SQL-rendering drift in parity
Solution adopted: performed a Case/Label SQL-renderer sweep to backend-correct placeholder semantics (`%s` postgres / `?` sqlite with ordered binding), fixed transaction-abort edge in optional queries, and validated via service suites plus fresh 20/200 parity reruns.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8628`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8643`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8673`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8706`

### ID 116 - Evidence scoping drift from stale `PLATFORM_RUN_ID` overriding active run
Solution adopted: changed run-id precedence in make targets to prefer `ACTIVE_RUN_ID` and only fallback to `PLATFORM_RUN_ID`, then validated artifact emission under active run even with stale shell env still set.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8711`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8717`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8728`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8755`

### ID 117 - Need for shared Kinesis consumer resilience against stale-sequence/transient reader faults
Solution adopted: hardened shared `KinesisEventBusReader` (`list_shards`/`read`) with transient-failure non-crash handling, stale-sequence fallback/reset logic, and suppression of repetitive stale warnings; validated with dedicated resilience tests and strict 20/200 runtime gates.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8934`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8942`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8947`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9002`

### ID 118 - Platform-wide P0: Postgres connect churn collapsing daemon packs
Solution adopted: raised as P0 and executed platform-wide DB lifecycle hardening plan using shared thread-local Postgres runtime connector + adapter migration + transient loop resilience, then revalidated live-pack stability.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9006`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9015`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9042`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9128`

### ID 119 - First connector pass caused transaction-lifecycle side effects (`idle in transaction`/lock waits)
Solution adopted: corrected shared connector exit semantics to mirror psycopg context behavior (`commit` on success, `rollback` on exception, drop broken cached connection) and reran focused suites.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9179`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9185`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9189`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9205`

### ID 120 - Strict 20->200 parity stability only achieved after Postgres lifecycle hardening
Solution adopted: executed final strict 20->200 full-stream validation after connector lifecycle corrections, with post-stream idle liveness checks showing all packs green and no recurrence of the prior Postgres collapse signature.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9207`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9244`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9250`

---

## Batch 13 - Plan-Level Closure Pressure and Authority Corrections (IDs 121-128)

### ID 121 - Control & Ingress carried open pins into RTDL planning (cross-phase pressure)
Solution adopted: explicitly documented unresolved C&I pins as deferred RTDL/partition-alignment decisions instead of forcing premature closure, then advanced only after downstream closure posture was synchronized.
Status: `Resolved` (by explicit deferred-then-closed gating discipline).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:298`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:299`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1011`

### ID 122 - Phase sequencing enforced hard meta-layer gate before Phase 5
Solution adopted: pinned an explicit blocking rule that Phase 5 cannot proceed until Phase 4.6 (Run/Operate + Obs/Gov) passes, with formal handoff criteria and later status synchronization showing 4.6 closure.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:865`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:867`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:956`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1511`

### ID 123 - Full parity run surfaced explicit remaining-open `4.6.L` TODO closure set
Solution adopted: converted residual drift into explicit `4.6.L` checklist items with objective closure criteria (`TODO-4.6L-01..04`) and synchronized matrix/status truth once closed.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:982`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1005`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1011`

### ID 124 - Inserted `5.10` throughput/efficiency blocker before Learning/Registry
Solution adopted: added a dedicated cross-cutting gate with strict 20->200 budgets, explicit scope boundaries, and a hard block on Phase 6 until pass or risk acceptance; later closed with recorded PASS status.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1188`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1190`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1216`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1513`

### ID 125 - Learning plane completion constrained by mandatory `6.6/6.7` meta-layer gates
Solution adopted: explicitly retained mandatory run/operate and obs/gov onboarding gates as non-negotiable plane-closure conditions, preventing premature “Phase 6 done” assertions despite OFS/MF progress.
Status: `Partial` (gate policy is in force; plane closure still active).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1409`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1418`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1531`

### ID 126 - Phase 6.8 formal integration closure gate blocks Phase 7 on fail
Solution adopted: defined explicit end-to-end and negative-path learning-loop proof requirements plus block-on-fail promotion posture (`Phase 7` blocked until PASS or explicit risk acceptance).
Status: `Planned` (gate defined; closure execution pending).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1427`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md:1439`

### ID 127 - Authority hierarchy ambiguity between core platform notes and supplemental guardrails
Solution adopted: corrected authority hierarchy in routing guidance: core platform-wide notes remain primary authority; supplemental platform-wide docs are guardrails and cannot override core notes.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:536`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:542`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:546`

### ID 128 - Runtime boundary doctrine correction (Oracle Store external to platform runtime graph)
Solution adopted: explicitly pinned Oracle Store as external engine truth boundary and clarified platform runtime artifacts cannot be treated as oracle inputs, preserving ownership/truth separation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:574`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:577`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:581`

---

## Batch 14 - Architecture/Sequencing Churn and Meta-Layer Gating (IDs 129-136)

### ID 129 - Local-vs-dev substrate drift pressure required a maximum-parity migration program
Solution adopted: designed and executed a dedicated local maximum-parity stack (MinIO + LocalStack/Kinesis + Postgres) with profile wiring, make targets, and docs so parity validation uses production-shape backends while preserving fast local smoke mode.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:616`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:637`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:700`

### ID 130 - Stream-view contract reversals (initial, bucketed, then flat layout)
Solution adopted: iteratively hardened stream-view semantics and converged on explicit per-output flat layout consumption, while retaining manifest/receipt integrity controls and removing ambiguous mode toggles.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1129`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1152`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1170`

### ID 131 - Traffic/context channel policy oscillation across multiple corrections
Solution adopted: repeatedly corrected policy posture as assumptions were invalidated, ending with explicit locked behavior that WSP streams traffic + context with mode-aligned flow-anchor semantics and EB exposure of both classes.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1586`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1651`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1673`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1714`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:1731`

### ID 132 - Phase status drift (4.3 effectively complete but marked in-progress)
Solution adopted: reclassified platform status to `component-complete, integration-pending`, marked 4.4 as planning-active, and synchronized rolling status to avoid misleading phase posture.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2052`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2058`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2070`

### ID 133 - Phase 4.4 was too placeholder-level for safe execution
Solution adopted: expanded 4.4 from placeholder bullets into phased executable DoD sections (`4.4.A..4.4.L`) to remove interpretation drift and make DF/DL closure auditable.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2079`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2132`

### ID 134 - RTDL integration A/B drifts required added phase insertion and structural map split
Solution adopted: closed A-side IG onboarding gaps for DF outputs, inserted explicit Phase `4.3.5` for shared join-plane duties, and created dedicated Context Store/Flow Binding component maps to prevent platform-prose mixing.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2329`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2365`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2399`

### ID 135 - Pre-runtime hardening needed to prevent shared-stream semantic mutation drift
Solution adopted: applied reviewer-confirmed patchset before 4.3.5 runtime work (IG run-axis hardening + OFP suppression of DF families + IEG irrelevant classification + targeted tests + v0 semantic pin).
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2421`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:2458`

### ID 136 - Meta-layer closure promoted to explicit blocking phase before Case/Label
Solution adopted: inserted Phase `4.6` as a formal blocking meta-layer gate (Run/Operate + Obs/Gov) ahead of Phase 5, with explicit DoD sections and updated rolling status/sequence.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3544`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3578`

---

## Batch 15 - Orchestration Hardening, Matrix Governance Drift, and Decision-Lane Runtime Blockers (IDs 137-144)

### ID 137 - Run/Operate DoD hardening needed to enforce plane-agnostic orchestration
Solution adopted: hardened the platform build-plan with explicit plane-agnostic orchestration contract gates (`4.6.J`) plus objective quality gate criteria (`4.6.K`), while correcting contradictory plan wording that could mislead implementation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3610`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3675`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3710`

### ID 138 - Orchestrator rollout exposed hidden validation defects (Windows YAML path + probe port parsing)
Solution adopted: fixed test-pack YAML generation on Windows (`yaml.safe_dump` path handling) and deferred probe-port coercion until env interpolation in orchestrator runtime resolution.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3814`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3826`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3832`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:3836`

### ID 139 - Validation-matrix bookkeeping drift (`4.6.B` wording stale after new evidence)
Solution adopted: corrected matrix evidence text to acknowledge newly proven `EVIDENCE_REF_RESOLVED` signals while preserving FAIL status until corridor-access controls were actually implemented.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4398`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4405`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4410`

### ID 140 - Evidence-corridor parallel probes caused governance append contention (`S3_APPEND_CONFLICT`)
Solution adopted: treated contention as non-functional collection race and switched to serialized probe/evidence collection posture for canonical validation artifacts.
Status: `Resolved` (operational evidence procedure fix).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4556`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4557`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4560`

### ID 141 - Phase 4.6 matrix failures from test-harness dependency drift (`werkzeug.__version__`)
Solution adopted: applied a minimal test-local compatibility shim in IG auth/rate tests (without production-code changes), then reran targeted matrix to green and completed 4.6 gate posture update.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4682`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4691`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4720`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4722`

### ID 142 - Decision-lane daemonization gap (DL/DF/AL/DLA matrix-only while live packs ran core only)
Solution adopted: implemented and onboarded dedicated decision-lane run/operate pack with daemon workers, lifecycle targets, config alignment, and runbook synchronization, then validated pack and service suites.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:4894`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5115`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5120`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5163`

### ID 143 - Decision-lane onboarding failure on missing projection DSN contract
Solution adopted: diagnosed DF worker crash (`CSFB projection_db_dsn is required`), patched decision-lane pack defaults with required projection DSNs, and re-smoked to all workers `running ready`.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5148`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5153`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5155`

### ID 144 - SR live-run blocked by missing `WiringProfile.profile_id`
Solution adopted: applied minimal schema-compatible runtime fix by adding `profile_id` to SR wiring model and explicit profile IDs in SR wiring YAMLs, unblocking READY commit path for requested live run.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5222`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5231`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5254`

---

## Batch 16 - AL/DF Runtime Drift, Phase-6 Planning Pressure, and Scenario Runner JSON-Safety Fixes (IDs 145-152)

### ID 145 - AL outcome publish lane P0 timestamp contract defect (`+00:00` vs `...Z`)
Solution adopted: implemented canonical UTC timestamp normalization across AL outcome generation/authz/publish boundaries and added targeted regression tests for normalization and invalid-shape rejection.
Status: `Partial` (code/test closure complete; direct live-lane recovery in same window remained coupled to upstream DF posture).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5506`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5508`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5590`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5629`

### ID 146 - DF fail-closed traced to cross-run WSP checkpoint cohort drift
Solution adopted: shifted WSP checkpointing to run-scoped keying so new runs no longer reuse prior-run cursor state, restoring traffic/context cohort overlap and CSFB join parity before DF evaluation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5634`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5644`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5646`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:5728`

### ID 147 - Phase-6 planning was too coarse and created drift risk
Solution adopted: replaced single-block Phase-6 posture with granular gated sections (`6.1..6.8`) that explicitly include meta-layer onboarding and closure semantics.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9289`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9290`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9347`

### ID 148 - Archive dependency had to be elevated to explicit blocking `6.0` gate
Solution adopted: introduced Phase `6.0` as a blocking archive-readiness precondition (contract, immutable archive fields, replay-integrity fail-closed posture, and obs/gov visibility) before deeper learning-plane progression.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9364`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9416`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:9493`

### ID 149 - Implementation-trail scalability forced local_parity/dev_substrate split
Solution adopted: formalized track separation by splitting implementation maps into baseline `local_parity` and active `dev_substrate` lanes, with explicit routing continuity entries to preserve audit traceability.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:10618`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:10621`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:10659`

### ID 150 - Scenario Runner ingress schema failed on Python-native dumps
Solution adopted: switched SR ingress validation to JSON-safe payload serialization (`model_dump(mode=\"json\", exclude_none=True)`) so datetime/null handling matches JSON Schema contracts.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:235`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:240`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:260`

### ID 151 - Scenario Runner ledger writes had the same JSON-compatibility defect
Solution adopted: applied JSON-safe serialization for plan/status persistence paths (`anchor_run`, `commit_plan`, `_update_status`) to avoid datetime/null schema and writer failures.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:272`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:278`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:281`

### ID 152 - `RunPlan.plan_hash` serialization fragility with datetimes
Solution adopted: changed plan-hash computation to JSON-safe dump mode, preventing datetime serialization errors and stabilizing deterministic hash derivation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:509`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:515`

---

## Batch 17 - Scenario Runner Gate-Law, Resolver Hardening, Runtime Security, and Contract-Compat Alignment (IDs 153-160)

### ID 153 - SR gate verification drifted from engine law for Segment 6B hashing
Solution adopted: realigned SR gate verification to engine policy by introducing index-driven raw-byte hashing for `gate.layer3.6B.validation` (`sha256_index_json_ascii_lex_raw_bytes`) and excluding `_passed.flag`/`index.json` per segment validation law.
Status: `Resolved` (with follow-up noted to extend law-specific mapping if other segments adopt index-driven hashing).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1247`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1253`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1257`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1261`

### ID 154 - Deprecated `jsonschema.RefResolver` threatened forward compatibility and strict resolution posture
Solution adopted: migrated SR schema validation to `referencing.Registry`/`Resource` with a custom `file://` retriever, preserved the interface-pack path shim, and kept fail-closed semantics on unknown/unsupported URIs.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1274`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1283`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1300`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1302`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1309`

### ID 155 - Relative `$id` patterns still broke resolution after resolver migration
Solution adopted: normalized schema base URIs in-memory by overriding relative `$id` values with file URIs at validation time, preserving source schema files while restoring relative-ref resolution behavior.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1410`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1413`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1414`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1418`

### ID 156 - Full 6B parity reuse exposed upstream multi-segment gate conflicts
Solution adopted: scoped Phase-3 parity reuse test to a real `1A` output path (`sealed_inputs_1A`) to preserve real artifact/gate/evidence flow while deferring broader multi-segment gate-law derivation (`2A/2B/3B/5A/5B/6A`) to later hardening.
Status: `Partial` (short-term test strategy resolved Phase-3 DoD, deeper 6B closure explicitly deferred).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1424`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1428`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1430`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1433`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:1437`

### ID 157 - Re-emit response semantics could misclassify attempted failures as not-applicable
Solution adopted: corrected response logic to track publish-attempt state and only emit `REEMIT_NOT_APPLICABLE` when no publish was attempted; attempted failures now return explicit failure response with `REEMIT_FAILED` audit detail.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2204`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2207`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2210`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2211`

### ID 158 - Windows concurrency regression during atomic replace caused follower read failures
Solution adopted: added bounded retry logic for `LocalObjectStore` reads (`read_json`/`read_text` via `_read_text_with_retry`) on transient `PermissionError`/`FileNotFoundError`, preserving fail-closed behavior after retry budget exhaustion.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2255`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2258`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2280`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2281`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2288`

### ID 159 - Lease-token files in SR runtime artifacts created sensitive-material exposure risk
Solution adopted: implemented targeted security posture change by untracking exposed token artifacts, narrowing `.gitignore` to SR sensitive runtime subpaths (without ignoring all `artefacts/`), and adding explicit operator warnings in docs/runtime logs.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2695`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2696`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2700`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2704`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:2706`

### ID 160 - Contract-compat resolver assumed repo-root refs instead of interface-pack-relative style
Solution adopted: aligned contract-compat resolver with interface-pack reference style by resolving refs relative to `interface_pack` first, falling back to repo-root only as secondary path, and normalizing fragment-pointer handling.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3001`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3004`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3005`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3008`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3052`

---

## Batch 18 - Scenario Runner Contract-Compat Depth, Parity Runtime Hardening, and IG Path/Pull Stabilization (IDs 161-168)

### ID 161 - Compatibility checks needed schema/dictionary resolution beyond strict pointer assumptions
Solution adopted: extended contract-compat resolver rules to handle bare schema filenames via segment-to-layer context and to interpret bare dictionary fragments as dataset-id lookups rather than strict JSON-pointer paths.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3014`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3019`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3021`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3024`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3027`

### ID 162 - Schema resolution still failed on `$id` anchors and cross-layer references
Solution adopted: hardened resolver with `$id`-anchor fallback matching when JSON-pointer traversal fails, plus global engine-contract filename search when segment-layer resolution is insufficient, while preserving ambiguity fail-closed behavior.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3034`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3039`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3040`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3043`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3052`

### ID 163 - LocalStack re-emit E2E had idempotency-key ambiguity in envelope fetch logic
Solution adopted: updated E2E fetch helper to wait/filter by `attributes.kind` instead of first `message_id` hit so READY re-emit assertions target the re-emitted envelope without breaking same-key idempotency semantics.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3185`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3188`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3190`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3197`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3199`

### ID 164 - Parity reuse tests collided with durable lease state via fixed equivalence key reuse
Solution adopted: switched parity integration to per-run unique `run_equivalence_key` values (UUID-suffixed) so durable lease authority remains intact while tests avoid cross-run lease collisions.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3205`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3207`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3210`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3213`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3221`

### ID 165 - Trailing newline in `arrival_events_5B` path template caused false WAITING_EVIDENCE
Solution adopted: hardened SR catalogue ingestion by normalizing `path_template` with whitespace stripping on load, added regression coverage, and validated by rerunning reuse flow to READY.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3302`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3310`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3313`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3328`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3335`

### ID 166 - SR/WSP path-contract drift (`RUN_FACTS_INVALID`) from extra `sr/` prefix placement
Solution adopted: aligned SR `object_store_root` to bucket root (`s3://fraud-platform`) so SR relative refs resolve to canonical `fraud-platform/<platform_run_id>/sr/...` layout consumed by WSP.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3836`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3839`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3842`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3843`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md:3850`

### ID 167 - IG smoke validation faced repeated SR artifact-root churn across temp/repo paths
Solution adopted: converged smoke-path authority to explicit env override plus repo-local default (`artefacts/fraud-platform/sr`), removed temp fallbacks, and documented deterministic search order.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:506`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:512`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:540`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:545`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:559`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:562`

### ID 168 - IG pull hit `INTERNAL_ERROR` from `pyarrow` parquet dataset schema-merge behavior
Solution adopted: replaced dataset-style parquet reads with direct `ParquetFile(...).read()` in IG pull path to avoid merge conflicts on engine files; subsequent bounded smoke observed no recurring schema-merge `INTERNAL_ERROR`.
Status: `Resolved` (error class fixed; run-time budget remained a separate throughput concern).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1185`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1189`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1192`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1205`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1207`

---

## Batch 19 - IG Throughput Constraints, Schema-Resolution Hardening, and Runtime Integrity Fixes (IDs 169-176)

### ID 169 - 10-minute smoke runs could not finish ingestion after parquet-read fix
Solution adopted: introduced explicit local pull time-budget controls with deterministic `TIME_BUDGET_EXCEEDED` partial posture, then added sharded/re-emit workflow and split profiles (`local` smoke vs `dev_local` completion) to separate bounded validation from completion attempts.
Status: `Resolved` (as an operational control posture for smoke validation, not as full local completion).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1251`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1256`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1287`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1324`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1341`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1355`

### ID 170 - Even uncapped local completion attempts timed out (2-hour run), exposing hardware/runtime limits
Solution adopted: after confirming uncapped local pull still failed to complete, documented infra/algorithm options and then pivoted platform direction to push-only IG (retiring pull as primary runtime path) to remove persistent local completion blockage from the critical lane.
Status: `Resolved` (closure by architecture/posture decision; legacy pull completion on local hardware remained non-viable).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1367`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1370`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1372`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1387`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1388`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1391`

### ID 171 - `arrival_events_5B` rows were quarantined because policy used array schema against per-row payloads
Solution adopted: preserved IG per-row ingestion contract and repointed schema policy from array wrapper to the `items` row schema fragment for `arrival_events_5B`.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1789`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1794`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1796`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1804`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1805`

### ID 172 - Fragment schema loading dropped `$defs`, causing internal resolver failures
Solution adopted: first grafted root `$defs`/`$id`/`$schema` onto fragment targets, then hardened further to registry-backed fragment validation (`$ref` wrapper + referencing registry) so internal and cross-file refs resolve correctly.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1816`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1820`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1823`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1827`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1840`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1847`

### ID 173 - Real engine contracts required multi-step schema resolution hardening
Solution adopted: implemented chained resolver hardening across base-URI normalization (`$id` assignment), data-engine tree filename fallback search, and repo-root handling for `docs/` schema refs.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1857`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1860`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1872`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1876`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1888`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1892`

### ID 174 - Engine `nullable: true` semantics were incompatible with Draft 2020-12
Solution adopted: added schema preprocessing to normalize OpenAPI-style `nullable: true` into JSON Schema null unions (`type` expansion / `anyOf`), then revalidated end-to-end traffic admission with no recurring schema/internal errors.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1898`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1902`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1906`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1914`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1915`

### ID 175 - IG parity smoke imported stale installed modules instead of workspace code
Solution adopted: enforced workspace-source precedence by routing service targets through `PYTHONPATH=src` wrapper (`PY_PLATFORM`) so runtime processes load current repo code.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1968`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1972`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1975`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1977`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2046`

### ID 176 - Class indentation regression detached core IG methods at runtime
Solution adopted: restored class/module structure by moving `_build_indices` back to module scope after class definition and reattaching admission handlers as proper `IngestionGate` methods.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1984`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1986`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1990`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:1991`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2001`

---

## Batch 20 - IG Event-Bus/Provenance Guardrails and Early WSP Runtime Hardening (IDs 177-184)

### ID 177 - Unresolved env placeholders in IG wiring caused live publish failures and config drift
Solution adopted: updated IG wiring load path to resolve env placeholders for `event_bus_path` and `admission_db_path` at profile load time, eliminating literal placeholder leakage (for example `${EVENT_BUS_STREAM}`) into runtime publish paths.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2001`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2002`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2006`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2008`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2011`

### ID 178 - IG Kinesis publisher initially targeted default AWS instead of LocalStack
Solution adopted: first pinned parity service startup with LocalStack env (`AWS_ENDPOINT_URL`, `AWS_DEFAULT_REGION`), then hardened further by adding explicit event-bus endpoint/region fields in IG wiring and passing them directly into publisher construction.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2018`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2022`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2031`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2034`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2039`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2046`

### ID 179 - IG receipt provenance drifted across run scopes (pins vs artifact path)
Solution adopted: bound receipt/quarantine write prefixes to `envelope.platform_run_id` (source-of-truth pins) via per-call writer prefix override, so `receipt_ref` and pins always share run scope even when service env is stale.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2461`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2464`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2472`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2495`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2498`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2509`

### ID 180 - IG needed fail-fast runtime guards for RTDL class-map/schema-policy incoherence
Solution adopted: implemented startup-time RTDL coherence assertions in IG (`event_type` mapping, schema-policy class match, schema-version/pins rules, explicit `run_id` exclusion posture), with fail-fast behavior when RTDL is partially/misconfigured.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2659`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2667`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2686`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2692`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2695`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md:2710`

### ID 181 - DLA audit quality degraded under mixed traffic stream intake (`UNKNOWN_EVENT_FAMILY` noise)
Solution adopted: isolated DLA local-parity intake onto dedicated RTDL stream (`fp.bus.rtdl.v1`) and aligned IG RTDL partitioning plus profile/runbook wiring to that lane.
Status: `Partial` (config/test posture closed; runtime noise-reduction closure explicitly pending fresh parity replay evidence).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1169`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1172`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1176`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1180`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1182`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1194`

### ID 182 - WSP READY tests failed due missing object-store root creation in test setup
Solution adopted: fixed test profile setup to explicitly create `store_root` before allowlist/config writes, restoring valid filesystem assumptions for local object-store tests.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:651`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:654`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:655`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:658`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:659`

### ID 183 - WSP MinIO integration failed from incompatible `pyarrow` S3 argument (`path_style_access`)
Solution adopted: replaced unsupported parameter usage with `force_virtual_addressing=False` under path-style configuration, matching PyArrow/MinIO behavior in parity mode.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:876`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:879`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:883`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:886`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:915`

### ID 184 - WSP emitted non-canonical timestamps that triggered IG `ENVELOPE_INVALID`
Solution adopted: normalized WSP `ts_utc` emission to fixed RFC3339 microsecond format (`YYYY-MM-DDTHH:MM:SS.ffffffZ`) before IG push, aligning with canonical envelope contract.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:896`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:899`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:902`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:905`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:921`

---

## Batch 21 - WSP Pin/Envelope Contract Corrections and IEG Run-Scope/Runtime Hardening (IDs 185-192)

### ID 185 - WSP used engine `run_id` as `scenario_run_id`, breaking Control/Ingress pin semantics
Solution adopted: propagated SR `scenario_run_id` from READY/run-facts into WSP stream runner and forced envelope `scenario_run_id` from SR while preserving engine receipt identity in envelope `run_id`.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1211`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1214`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1218`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1235`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1236`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1259`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1260`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1273`

### ID 186 - WSP did not reliably guarantee `schema_version` on emitted envelopes
Solution adopted: enforced source-side `schema_version: v1` stamping on stream-view envelope construction and added defensive send-path fallback in `_push_to_ig` for legacy/non-stream-view emitters.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1278`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1285`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1289`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1301`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1303`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1315`

### ID 187 - Full-run orchestration required explicit WSP dependency gates before streaming
Solution adopted: added READY dependency gating in WSP against required run/operate packs (with run-match/liveness checks and deferred status when unmet), plus orchestrator run-scope drift guard and lifecycle ordering updates in Makefile.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1325`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1328`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1331`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1334`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1336`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1349`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md:1350`

### ID 188 - IEG targeted non-existent traffic stream (`fp.bus.traffic.v1`)
Solution adopted: corrected IEG topic configuration to consume the actual split traffic streams (`fp.bus.traffic.fraud.v1`, `fp.bus.traffic.baseline.v1`) instead of legacy single-stream name.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:178`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:181`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:184`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:423`

### ID 189 - IEG parity revealed cross-run contamination risk in intake/dedupe/checkpoints/failures
Solution adopted: implemented run-scope hardening end-to-end: enforced platform-run intake guards, run-scoped stream identity, platform-run-aware dedupe/failure attribution, and graph-scope surfacing in query/reconcile outputs.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:434`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:437`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:462`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:464`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:482`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:486`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:487`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:501`

### ID 190 - IEG dedupe semantics drifted by including `scenario_run_id` in identity tuple
Solution adopted: realigned dedupe tuple to corridor law by using `(platform_run_id, event_class, event_id)` while retaining `scenario_run_id` as required provenance pin outside semantic dedupe identity.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:696`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:705`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:720`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:726`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:731`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:740`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:743`

### ID 191 - IEG parity crashed on reserved SQL identifier usage (`offset`)
Solution adopted: quoted reserved identifier `"offset"` in IEG migration DDL and apply-failure write statements for SQLite/Postgres branches, then revalidated live parity projector behavior.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:796`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:799`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:807`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:810`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:811`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:823`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:827`

### ID 192 - IEG health artifact emission was incorrectly gated on late scenario-lock timing
Solution adopted: moved scenario-scope capture earlier in projector flow and hardened operational artifact emission to no longer require settled scenario lock before writing run-scoped health/metrics artifacts.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:836`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:840`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:842`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:847`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:849`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:858`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:861`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:876`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:877`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:885`

---

## Batch 22 - IEG Backlog Posture, OFP Runtime Hardening, and CSFB Parity Fail-Closed Store Controls (IDs 193-200)

### ID 193 - IEG trim-horizon-only Kinesis posture delayed bounded parity closure
Solution adopted: proposed explicit IEG start-position wiring (`trim_horizon|latest`) for bounded parity runs, but in immediate closure windows the team explicitly deferred that change as non-blocking and prioritized other blockers; runtime posture remained trim-horizon with run-scope filtering.
Status: `Partial` (design decision captured; feature not implemented in this documented window).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:889`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:892`
- `docs/model_spec/platform/implementation_maps/local_parity/identity_entity_graph.impl_actual.md:894`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8108`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8134`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md:8140`

### ID 194 - OFP semantic dedupe identity incorrectly included `stream_id`
Solution adopted: migrated semantic dedupe identity to corridor-aligned tuple `(platform_run_id, event_class, event_id)`, retained transport dedupe semantics unchanged, and added migration/regression coverage for stream-independent semantic idempotency.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:989`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:998`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1018`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1021`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1024`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1031`

### ID 195 - OFP parity startup crashed on reserved SQL identifier (`offset`)
Solution adopted: hardened OFP store SQL by quoting `"offset"` in applied-events DDL and insert/conflict SQL across SQLite/Postgres code paths, then validated live parity startup behavior.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1165`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1168`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1176`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1179`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1180`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1183`

### ID 196 - OFP 194/200 undercount from `LATEST` start-position startup race
Solution adopted: changed parity live default start-position to `trim_horizon` (with explicit `latest` override retained), then replayed run-scoped state to prove complete 200/200 application with zero missing offsets.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1191`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1215`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1218`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1232`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1238`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1250`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1258`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1264`

### ID 197 - OFP daemon mode ignored runtime threshold overrides, causing false-red health
Solution adopted: refactored observability reporter construction to source thresholds from runtime/env in daemon path (`from_runtime(...)`), added regression test, and preserved projection semantics.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1270`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1276`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1278`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1282`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1284`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1287`

### ID 198 - OFP bounded parity acceptance needed repeated `missing_features` threshold tuning
Solution adopted: iteratively tuned local-parity pack-level OFP `missing_features` health thresholds to non-gating bands for bounded replay acceptance, then closed with full-green run evidence under run-scoped artifacts.
Status: `Resolved` (environment-policy closure for local parity; core OFP semantics unchanged).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1308`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1312`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1332`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1333`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1336`
- `docs/model_spec/platform/implementation_maps/local_parity/online_feature_plane.impl_actual.md:1341`

### ID 199 - CSFB policy loader risked silent SQLite fallback when DSN wiring was absent
Solution adopted: hardened parity store posture to remove silent fallback behavior by requiring explicit projection locator/DSN resolution from profile or environment, aligned to parity/dev/prod backend expectations.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:77`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:82`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:85`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1105`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1110`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1124`

### ID 200 - CSFB needed explicit projection-locator fail-closed guards before run-scoping
Solution adopted: implemented explicit projection-locator pre-check in `CsfbInletPolicy.load` and fail-closed `ValueError` when neither wiring nor env provides a non-empty locator; retained run-scoped rewriting only for explicit locators.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1109`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1111`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1116`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1117`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1120`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1121`

---

## Batch 23 - CSFB SQL Hardening, EB Durability/Scope Corrections, and Oracle Store Boundary + Stream-View Reorientation (IDs 201-208)

### ID 201 - CSFB live intake failed on reserved SQL identifier usage (`offset`)
Solution adopted: hardened CSFB apply-failure schema/write paths by quoting `"offset"` in SQLite/Postgres DDL and read/write SQL statements, then validated parity join-plane evidence under live run scope.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1130`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1133`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1144`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1145`
- `docs/model_spec/platform/implementation_maps/local_parity/context_store_flow_binding.impl_actual.md:1160`

### ID 202 - EB local durability risk: stale `head.json` could resurrect offsets when log was missing
Solution adopted: enforced log-first precedence in offset recovery (`_load_next_offset` checks log existence before head state); when log is missing, offset resets to `0` regardless of `head.json`.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:255`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:258`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:261`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:264`

### ID 203 - Platform smoke orchestration broke repeatedly on Windows shell quoting
Solution adopted: removed fragile nested quoting by replacing Python one-liner run-equivalence key generation with shell-native `date +%Y%m%dT%H%M%SZ` in `platform-smoke`.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:480`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:483`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:491`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:494`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:497`

### ID 204 - EB stream scope drifted between traffic-only and traffic+context postures
Solution adopted: after temporary traffic-only narrowing, explicitly restored parity provisioning for both traffic and context streams to match clarified WSP->IG->EB runtime flow intent.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:674`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:677`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:692`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:695`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md:699`

### ID 205 - Oracle pack sealing idempotency treated timestamps as identity-critical
Solution adopted: hardened packer idempotency comparator to ignore timestamp fields and compare only identity-critical manifest/seal fields, preventing false divergence on repeated seals.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:222`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:223`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:227`

### ID 206 - Oracle boundary required removal of SR-based sealing inputs
Solution adopted: executed decisive boundary correction to remove SR `run_facts_view` sealing/checking paths and rebuild Oracle tooling around engine-root inputs only (`engine_run_root`, `run_receipt.json`, optional `scenario_id`).
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:253`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:256`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:275`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:282`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:292`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:308`

### ID 207 - Stream-view integrity checks hit DuckDB overflow (`hash_sum2`)
Solution adopted: redesigned order-invariant receipt aggregates to avoid UINT64 overflow by using bounded aggregate forms (modular secondary sum) while preserving same-rowset integrity signal.
Status: `Resolved` (overflow class closed; later deterministic-stat refinements tracked separately).
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:509`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:513`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:517`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:520`

### ID 208 - Stream-view requirement was misread as unified global flow instead of per-output sorted datasets
Solution adopted: corrected Oracle stream-view design to independent per-output sorted datasets (no cross-output union), with output-specific roots consumed separately by WSP.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:528`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:531`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:533`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:537`

---

## Batch 24 - Oracle Stream-View Layout/Performance Stabilization and CaseMgmt Resilience Hardening (IDs 209-216)

### ID 209 - Stream-view layout semantics required multiple corrections before stabilization
Solution adopted: iteratively corrected layout contract from path-segmented/bucketed variants to stabilized per-output flat roots, keeping `stream_view_id` in receipt/manifest integrity metadata while removing it from filesystem path semantics.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:568`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:572`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:638`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:640`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:650`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:728`

### ID 210 - Per-bucket write loops became operationally infeasible
Solution adopted: replaced N-scan per-bucket write loops with single-pass DuckDB copy strategy to keep deterministic ordering while eliminating repeated full scans; retained single-pass principle through later layout refinements.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:603`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:607`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:611`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:613`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:648`

### ID 211 - MinIO stream-view reliability needed explicit timeout/retry controls
Solution adopted: introduced configurable S3 client timeout/retry settings (`OBJECT_STORE_READ_TIMEOUT`, `OBJECT_STORE_CONNECT_TIMEOUT`, `OBJECT_STORE_MAX_ATTEMPTS`) and applied them consistently to object-store paths used in stream-view operations.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:657`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:660`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:662`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:665`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:667`

### ID 212 - Float-based integrity aggregation (`hash_sum`) was nondeterministic
Solution adopted: replaced floating aggregation with integer deterministic stats (`HUGEINT` sum for `hash_sum`) while keeping modular secondary sum, eliminating drift from floating-rounding behavior.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:674`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:678`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:679`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:682`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:683`

### ID 213 - Missing `bucket_index` in some outputs blocked stream sorting
Solution adopted: narrowed required sort assumptions to deterministic keys actually needed (`ts_utc` + tie-breakers), removing hard dependency on `bucket_index` and preserving schema without synthetic column derivation.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:690`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:693`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:695`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:698`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:699`

### ID 214 - Large 6B flow-anchor sorts hit DuckDB OOM under full-range ordering
Solution adopted: added chunked day-window sorting (`STREAM_SORT_CHUNK_DAYS`) with sequential part emission to preserve global chronological order while reducing peak memory pressure.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:706`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:710`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:714`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:716`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:717`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md:729`

### ID 215 - CaseMgmt lookup path lacked defensive JSON decode handling
Solution adopted: hardened lookup deserialization by catching `json.JSONDecodeError` in `_json_to_dict(...)` and defaulting to `{}` to avoid crashes on corrupted/partial legacy rows.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:172`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:177`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:180`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:181`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:183`

### ID 216 - Timeline replay/mismatch counters had a legacy stats-row gap
Solution adopted: added stats-row bootstrap logic in `_append_timeline_tx` so existing timeline rows missing `cm_case_timeline_stats` receive initialized counters/metadata before duplicate or mismatch handling.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:298`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:303`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:305`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:307`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:309`

---

## Batch 25 - CaseMgmt/CaseTrigger/LabelStore Guardrails and DLA/Degrade-Ladder Runtime Closure (IDs 217-224)

### ID 217 - CM->LS handshake exposed SQLite nested-write lock and sequencing inconsistency risk
Solution adopted: reworked handshake sequencing to remove nested write transactions by splitting emission-state writes and timeline appends into short isolated phases, with explicit pending-first/outcome-after-durable-write semantics and exception mapping to deterministic pending posture.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:477`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:479`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:482`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:485`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:491`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:502`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:533`
- `docs/model_spec/platform/implementation_maps/local_parity/case_mgmt.impl_actual.md:539`

### ID 218 - CaseTrigger policy accepted arbitrary evidence-ref type tokens (vocabulary drift risk)
Solution adopted: added strict config-time validation of `required_evidence_ref_types` against supported CM evidence vocabulary and backed it with regression tests that fail policy load on unknown tokens.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/case_trigger.impl_actual.md:141`
- `docs/model_spec/platform/implementation_maps/local_parity/case_trigger.impl_actual.md:145`
- `docs/model_spec/platform/implementation_maps/local_parity/case_trigger.impl_actual.md:146`
- `docs/model_spec/platform/implementation_maps/local_parity/case_trigger.impl_actual.md:150`
- `docs/model_spec/platform/implementation_maps/local_parity/case_trigger.impl_actual.md:153`

### ID 219 - Label Store lacked explicit resolved-view conflict posture and stable read contracts
Solution adopted: implemented and validated explicit LS as-of/resolved query surfaces with deterministic precedence and conflict signaling (`RESOLVED|CONFLICT|NOT_FOUND`), giving consumers stable contract semantics.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:332`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:345`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:373`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:381`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:386`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:393`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:410`

### ID 220 - Label Store lacked deterministic bulk as-of slice boundary for OFS training joins
Solution adopted: introduced Phase-7 bulk slice builder with mandatory explicit basis (`observed_as_of`, target universe, basis digest), deterministic slice digests, run-scope safety, and dataset coverage/conflict gate signals aligned with OFS consumption needs.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:703`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:707`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:719`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:726`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:774`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:780`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:787`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:815`

### ID 221 - LS Phase-7 artifact handling needed fail-closed immutability enforcement
Solution adopted: enforced artifact immutability in slice export path: existing artifact path with digest mismatch now triggers explicit fail-closed violation instead of overwrite.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:782`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:784`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:800`
- `docs/model_spec/platform/implementation_maps/local_parity/label_store.impl_actual.md:806`

### ID 222 - DLA provenance vocabulary/digest propagation drift (`origin_offset`, `run_config_digest`)
Solution adopted: closed runtime drift by adding additive `origin_offset` alias while retaining compatibility fields, persisting/exposing chain-level `run_config_digest`, and enforcing explicit digest-mismatch fail-closed lineage conflicts.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:34`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:35`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1014`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1023`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1029`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1036`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1048`
- `docs/model_spec/platform/implementation_maps/local_parity/decision_log_audit.impl_actual.md:1057`

### ID 223 - Degrade Ladder contract helpers threw non-contract exceptions on malformed nested payloads
Solution adopted: removed eager nested `dict(...)` coercion and routed malformed nested payloads through typed validation so failures consistently raise `DegradeContractError`.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:168`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:171`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:174`

### ID 224 - Degrade Ladder runtime closure blocked by missing run-scoped health/metrics artifacts
Solution adopted: implemented run-scoped DL observability emission directly in worker tick (`last_metrics.json`, `last_health.json`) with deterministic health derivation and targeted tests, restoring matrix-required artifact availability.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1083`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1097`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1111`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1116`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1118`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1130`
- `docs/model_spec/platform/implementation_maps/local_parity/degrade_ladder.impl_actual.md:1139`

---

## Batch 26 - Model Factory/OFS/Archive Hardening and Early Dev-Migration Strategy Decisions (IDs 225-232)

### ID 225 - Model Factory launcher policy path resolution rewrote valid refs incorrectly
Solution adopted: corrected worker policy-path resolution to preserve configured repo-relative paths first (CWD/repo semantics), falling back to profile-relative rewriting only when the configured path does not exist.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:883`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:885`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:887`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:889`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:893`
- `docs/model_spec/platform/implementation_maps/local_parity/model_factory.impl_actual.md:894`

### ID 226 - OFS Phase-3 resolver leaked unstable raw I/O/parsing failures
Solution adopted: wrapped resolver failure paths into deterministic fail-closed error taxonomy codes (`RUN_FACTS_UNAVAILABLE`, `FEATURE_PROFILE_UNRESOLVED`, `PARITY_ANCHOR_INVALID`) for stable governance/runtime handling.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:343`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:349`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:346`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:354`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:358`

### ID 227 - OFS protected-ref enforcement could be weakened via `evidence_ref_strict=false`
Solution adopted: hardened worker corridor logic to enforce unconditional fail-closed protected-reference denial (`REF_ACCESS_DENIED`) whenever corridor status is non-`RESOLVED`, independent of strict-mode toggle.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:927`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:931`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:933`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:936`
- `docs/model_spec/platform/implementation_maps/local_parity/offline_feature_plane.impl_actual.md:940`

### ID 228 - Archive Writer parity startup failed on reserved SQL identifier usage
Solution adopted: remediated ledger schema/query naming by replacing reserved `offset` identifier with `offset_value` across archive-writer storage paths, restoring parity worker startup readiness.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/local_parity/archive_writer.impl_actual.md:60`
- `docs/model_spec/platform/implementation_maps/local_parity/archive_writer.impl_actual.md:61`
- `docs/model_spec/platform/implementation_maps/local_parity/archive_writer.impl_actual.md:64`
- `docs/model_spec/platform/implementation_maps/local_parity/archive_writer.impl_actual.md:65`
- `docs/model_spec/platform/implementation_maps/local_parity/archive_writer.impl_actual.md:73`

### ID 229 - Migration framing trap: semantics build + substrate build treated as one job
Solution adopted: explicitly separated environment ladder intent so `local_parity` remains semantics/correctness harness while managed-substrate promotion is executed as a distinct track, preventing substrate work from diluting semantics closure.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:79`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:82`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:90`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:91`

### ID 230 - Needed mental-model shift for what migration actually means
Solution adopted: formalized migration as unchanged-law replatforming (`local_parity` correctness harness -> `dev_min` managed-substrate proof), with explicit rung semantics rather than “rebuild everything” posture.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:90`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:91`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:142`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:144`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:146`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:150`

### ID 231 - Migration scope risked overkill stack explosion (`K8s+Flink+Temporal+full MLOps`)
Solution adopted: constrained migration to minimum credible managed stack (Kafka + S3 + managed Postgres + Terraform/CI/OTel + deployable logic services) and explicitly rejected “everything at once” stack expansion that would stall delivery.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:261`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:262`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:264`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:266`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:270`

### ID 232 - Budget reality became a first-class migration constraint
Solution adopted: treated cost guardrails as design inputs by choosing demo-destroy operational mode, avoiding known cloud bill traps (for example NAT/always-on patterns), and selecting budget-compatible Kafka strategy for dev progression.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:534`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:538`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:541`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:556`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:604`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:606`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:619`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:672`

---

## Batch 27 - Dev-Substrate Kafka/Networking Strategy and Early Authority/Planning Corrections (IDs 233-240)

### ID 233 - Kafka choice was blocked by budget-vs-iteration friction
Solution adopted: chose Confluent Cloud as the day-to-day Kafka surface (with AWS for the rest) to preserve fast local iteration and avoid early VPC connectivity overhead.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:562`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:569`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:570`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:574`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:627`

### ID 234 - Needed AWS-native Kafka credibility without making MSK the daily velocity bottleneck
Solution adopted: pinned a dual-lane strategy: run Confluent Cloud for everyday progress, then execute limited MSK Serverless demo runs for AWS-native evidence and destroy immediately after capture.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:633`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:635`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:636`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:672`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:694`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:697`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:700`

### ID 235 - NAT gateway spend trap threatened dev-substrate affordability
Solution adopted: explicitly avoided NAT-by-default posture for demos, preferring no-NAT/public-IP paths or VPC endpoints to prevent hidden hourly + data-processing charges.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:604`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:606`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:607`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:609`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:610`

### ID 236 - Always-on load balancers and “leave everything running” posture risked silent budget drift
Solution adopted: enforced demo-window activation only for costly ingress surfaces and made teardown the default operating habit instead of persistent idle infra.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:614`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:615`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:617`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md:619`

### ID 237 - Early dev-min migration authority still had unresolved internal contradictions
Solution adopted: ran a corrective closure lock to enumerate and close residual authority holes (path mismatch, open-decision language drift, missing pinned profile/contract artifacts) in one atomic pass.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:90`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:95`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:99`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:100`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:101`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:104`

### ID 238 - Migration authority lacked concrete pinned artifacts for executable implementation certainty
Solution adopted: completed the closure pass by patching authority references, creating the missing profile/schema artifacts, and validating wording/file-existence/YAML parse consistency.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:131`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:136`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:140`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:141`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:147`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:155`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:159`

### ID 239 - Track split caused documentation routing ambiguity (legacy vs active impl map path)
Solution adopted: migrated continuity to the active `dev_substrate` impl map and removed the legacy root impl file to prevent dual-authority drift.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:119`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:122`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:125`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:126`

### ID 240 - Migration execution plan was too coarse to run as a real program
Solution adopted: replaced the broad placeholder plan with a full wave-gated program containing explicit phases, hard DoD gates, embedded meta-layer saturation, and final acceptance/drift-audit closure.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:167`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:173`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:184`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:190`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:199`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:206`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:212`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:221`

---

## Batch 28 - Dev-Substrate Phase 0/Contract Simplification and Phase 1 Bootstrap Gate Hardening (IDs 241-248)

### ID 241 - Phase 0 documentation surface became noisy and duplicative
Solution adopted: simplified Phase 0 to an authority-first posture by removing auxiliary artifacts and keeping closure evidence anchored to pre-design authority plus local-parity implementation history.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:296`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:302`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:310`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:317`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:325`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:337`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:348`

### ID 242 - Auxiliary `dev_min` contract family created migration friction and duplicate contract authority
Solution adopted: removed the auxiliary `dev_min` contract set and repinned migration evidence closure to existing platform contract families already proven in local-parity.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:355`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:361`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:362`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:366`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:376`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:382`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:395`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:400`

### ID 243 - Phase 1 bootstrap plan was too coarse for secure execution
Solution adopted: expanded Phase 1 from broad bullets into explicit sections (`1.A`-`1.F`) with tightened auditable DoD gates for identity, secrets, operator preflight, hygiene, and recovery.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:406`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:411`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:415`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:432`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:439`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:446`

### ID 244 - Phase 1 needed executable guardrails, not just plan text
Solution adopted: implemented fail-closed Phase 1 tooling (`phase1_preflight.ps1`, `phase1_seed_ssm.ps1`, make targets) and ran positive/negative drills with sanitized evidence to validate readiness controls.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:460`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:475`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:489`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:492`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:500`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:517`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:521`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:530`

### ID 245 - Strict Phase 1 closure blocked because required Kafka secret material was absent in execution context
Solution adopted: kept fail-closed behavior explicit, narrowed the blocker to missing `DEV_MIN_KAFKA_*` materialization, and defined deterministic reseed/re-preflight unblock steps.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:537`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:540`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:546`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:547`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:551`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:557`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:564`

### ID 246 - Ambient shell/env inheritance made Phase 1 secret bootstrap non-deterministic
Solution adopted: introduced dedicated local `.env.dev_min` sourcing via `DEV_MIN_ENV_FILE`, updated make targets to load it explicitly, and validated the path with isolated drill runs and cleanup.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:567`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:573`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:580`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:597`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:601`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:617`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:624`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:636`

### ID 247 - Strict preflight produced a false-negative by probing Confluent management-plane IAM instead of Kafka-plane readiness
Solution adopted: identified probe mismatch as design-intent drift, with diagnostics showing handles/material shape present while IAM endpoint auth still failed (`401`), triggering correction.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:643`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:654`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:666`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:683`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:698`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:704`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:710`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:718`

### ID 248 - Credential gate needed realignment to event-bus readiness semantics
Solution adopted: replaced IAM list-keys dependency with Kafka-plane checks (material present, parse, DNS, TCP reachability), updated plan wording, and closed strict Phase 1 gate on PASS.
Status: `Resolved`.
Evidence:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:710`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:721`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:728`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:739`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:742`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:751`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:759`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md:763`

---

Next batch target (pending your direction): IDs `249-256` from budget-sentinel formalization and Phase 2 terraform lifecycle implementation/verification (including teardown and budget-alert gates).
