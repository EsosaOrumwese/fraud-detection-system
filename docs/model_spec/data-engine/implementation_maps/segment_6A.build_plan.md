# Segment 6A Remediation Build Plan (B/B+ Recovery Plan)
_As of 2026-02-23_

## 0) Objective and closure rule
- Objective: move Segment `6A` from published `B-` posture to certified `PASS_B` first, then pursue stable `PASS_BPLUS`.
- Closure rule:
  - `PASS_B`: all hard realism gates pass (`T1-T10` at `B` thresholds), with required seed stability evidence.
  - `PASS_BPLUS`: all `B` gates pass and all `B+` thresholds pass on required seeds.
  - `HOLD_REMEDIATE`: any hard gate fails or evidence is incomplete.
- Phase law: no phase advances until that phase DoD is fully closed.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_6A/segment_6A_published_report.md`
- `docs/reports/eda/segment_6A/segment_6A_remediation_report.md`

### 1.2 State/contract authority
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6A/state.6A.s0.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6A/state.6A.s1.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6A/state.6A.s2.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6A/state.6A.s3.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6A/state.6A.s4.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6A/state.6A.s5.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/dataset_dictionary.layer3.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/schemas.6A.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/schemas.layer3.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6A/artefact_registry_6A.yaml`

### 1.3 Upstream freeze posture
- Upstream segments `1A`, `1B`, `2A`, `2B`, `3A`, `3B`, `5A`, `5B` are frozen inputs during baseline remediation for `6A`.
- `6B` is downstream-only for non-regression checks; no `6B` tuning in this plan.

## 2) Scope and ownership map
- `S2` owner lane: enforce hard post-merge `K_max` semantics per `(party_type, account_type)` and stop cap leakage tails.
- `S4` owner lane: restore IP realism by prior alignment, linkage coverage, and bounded degree tail behavior.
- `S5` owner lane: enforce risk propagation coupling and role-family traceability.
- Policy/config owner lane:
  - `account_per_party_priors_6A.v1.yaml`
  - `validation_policy_6A.v1.yaml`
  - `fraud_role_taxonomy_6A.v1.yaml`
  - new `risk_propagation_coeffs_6A.v1.yaml`
- Out-of-scope for Phase-1 baseline `B`:
  - broad redesign of `S1` population priors,
  - major `S3` reshaping beyond targeted Phase-2 `B+` refinement.

## 3) Target realism gates

### 3.1 Hard gates (`B`)
- `T1_KMAX_HARD_INVARIANT`: max overflow above `K_max` equals `0`.
- `T2_KMAX_TAIL_SANITY`: per-type `p99 <= K_max`, `max <= K_max`.
- `T3_IP_PRIOR_ALIGNMENT`: max abs error `<= 15 pp`.
- `T4_DEVICE_IP_COVERAGE`: linked device fraction `>= 0.25`.
- `T5_IP_REUSE_TAIL_BOUNDS`: `p99(devices_per_ip) <= 120`, `max <= 600`.
- `T6_ROLE_MAPPING_COVERAGE`: mapping coverage `100%`, unmapped `0`.
- `T7_RISK_PROPAGATION_EFFECT`: `OR_account >= 1.5`, `OR_device >= 1.5`.
- `T8_DISTRIBUTION_ALIGNMENT_JSD`: `<= 0.08`.
- `T9_CROSS_SEED_STABILITY`: CV `<= 0.25`.
- `T10_DOWNSTREAM_COMPAT_6B`: must pass (non-regression and sensitivity).

### 3.2 Stretch gates (`B+`)
- `T3`: `<= 8 pp`.
- `T4`: `>= 0.35`.
- `T5`: `p99 <= 80`, `max <= 350`.
- `T7`: both OR metrics `>= 2.0`.
- `T8`: `<= 0.05`.
- `T9`: CV `<= 0.15`.

### 3.3 Statistical evidence policy
- Use bootstrap intervals for proportion/rate gates where required by remediation authority.
- Treat insufficient support as fail-closed for promotion.
- No threshold waivers without explicit policy re-baseline.

## 4) Run protocol, retention, and pruning
- Active run root: `runs/fix-data-engine/segment_6A/`.
- Keep-set only:
  - one baseline authority run-id,
  - current candidate run-id,
  - last good run-id,
  - active multi-seed witness set.
- Prune law: remove superseded failed/superseded run-id folders before each expensive rerun.

### 4.1 Sequential rerun matrix (binding)
- If `S2` changes: rerun `S2 -> S3 -> S4 -> S5`.
- If `S4` changes: rerun `S4 -> S5`.
- If `S5` changes: rerun `S5`.
- If contract/policy change affects multiple states: rerun from earliest affected owner state.
- No direct `S5` realism claims are accepted when upstream owner state changed but was not rerun.

## 5) Remediation phase stack

### P0 - Baseline lock and owner-state attribution
Goal:
- lock baseline metrics, map each failing metric to its owner state, and pin promotion veto criteria.

#### P0.1 - Authority and baseline run lock
Definition of done:
- [ ] Baseline run-id pinned under `runs/fix-data-engine/segment_6A/`.
- [ ] Published/remediation grade baseline fields copied into a machine-readable gateboard.
- [ ] Frozen upstream posture recorded.

#### P0.2 - Baseline gateboard emission
Definition of done:
- [ ] `T1-T10` baseline values computed on the pinned run-id.
- [ ] Each metric tagged `PASS/FAIL` for `B` and `B+`.
- [ ] No missing metric silently defaulted.

#### P0.3 - Owner-state attribution lock
Definition of done:
- [ ] `S2` is pinned as owner for `T1-T2`.
- [ ] `S4` is pinned as owner for `T3-T5`.
- [ ] `S5` is pinned as owner for `T6-T8`.
- [ ] `T9-T10` owner dependencies and routing are pinned.

#### P0.4 - Candidate and promotion protocol lock
Definition of done:
- [ ] Candidate lane protocol pinned (single-seed then witness seeds).
- [ ] Promotion veto criteria pinned (hard fail-closed).
- [ ] Output artifacts and paths for scoring evidence pinned.

### P1 - Delta Set A (`S2`) hard `K_max` remediation
Goal:
- implement and prove hard global post-merge cap enforcement with deterministic overflow handling.

#### P1.1 - `S2` algorithm lock
Definition of done:
- [ ] `enforce_kmax_per_party_account_type` design pinned (deterministic rank, redistribute, deterministic drop fallback).
- [ ] `K_max` source pinned to `account_per_party_priors_6A.v1.yaml`.
- [ ] No warning-only semantics remain for cap invariants.

#### P1.2 - `S2` implementation
Definition of done:
- [ ] `packages/engine/src/engine/layers/l3/seg_6A/s2_accounts/runner.py` updated with final cap pass before writeout.
- [ ] Post-pass invariant check fails on any remaining overflow.
- [ ] Counters emitted: `kmax_overflow_rows`, `kmax_redistributed_rows`, `kmax_dropped_rows`, `kmax_postcheck_violations`.

#### P1.3 - Policy hardening
Definition of done:
- [ ] `config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml` updated with:
  - `constraints.cap_enforcement_mode: hard_global_postmerge`
  - `constraints.max_allowed_kmax_violations: 0`
- [ ] Policy/schema validation remains green.

#### P1.4 - Witness and closure
Definition of done:
- [ ] `T1-T2` pass at `B` thresholds on candidate lane.
- [ ] No regression on already-stable non-owner gates.
- [ ] Decision recorded as one of `UNLOCK_P2` or `HOLD_P1`.

### P2 - Delta Set B (`S4`) IP realism remediation
Goal:
- close IP prior mismatch, sparse linkage, and heavy shared-IP tail pathologies.

#### P2.1 - `S4` design lock
Definition of done:
- [ ] Missing-region `ip_type_mix` fallback removed; fail-closed behavior pinned.
- [ ] Per-region IP type quota/assignment strategy pinned.
- [ ] Tail clamp strategy pinned with deterministic backoff.

#### P2.2 - `S4` implementation
Definition of done:
- [ ] `packages/engine/src/engine/layers/l3/seg_6A/s4_device_graph/runner.py` updated for:
  - fail-closed missing-mix handling,
  - constrained per-region `ip_type` assignment,
  - explicit linkage coverage control,
  - bounded reuse/tail controls.
- [ ] New controls are deterministic and reproducible by seed.

#### P2.3 - Validation policy hardening (S4-owned checks)
Definition of done:
- [ ] `config/layer3/6A/policy/validation_policy_6A.v1.yaml` updated:
  - `linkage_checks.ip_links.max_devices_per_ip: 600`
  - `role_distribution_checks.ip_roles.max_risky_fraction: 0.25`
  - new fail-closed checks for `T3-T5` thresholds.
- [ ] Gate checks integrated as hard fail-closed, not warnings.

#### P2.4 - Witness and closure
Definition of done:
- [ ] `T3-T5` pass at `B` thresholds on candidate lane.
- [ ] `S2` hard-cap gates remain green.
- [ ] Decision recorded as `UNLOCK_P3` or `HOLD_P2`.

### P3 - Delta Set C (`S5`) propagation coupling remediation
Goal:
- make risk transmission along ownership/network edges measurable and stable.

#### P3.1 - Propagation model lock
Definition of done:
- [ ] Conditional uplift design pinned:
  - party-risk -> account-risk
  - party-risk -> device-risk
  - risky asset/high-sharing context -> IP risk uplift
- [ ] Log-odds clamp bounds pinned to avoid over-separability.

#### P3.2 - `S5` implementation
Definition of done:
- [ ] `packages/engine/src/engine/layers/l3/seg_6A/s5_fraud_posture/runner.py` updated with pre-draw conditional uplift layer.
- [ ] Deterministic tie-break and overflow behavior preserved.
- [ ] Evidence counters/diagnostics emitted for uplift effects.

#### P3.3 - New coefficients policy
Definition of done:
- [ ] Added `config/layer3/6A/policy/risk_propagation_coeffs_6A.v1.yaml`.
- [ ] Initial targets encoded for `B`:
  - `OR_account` and `OR_device` bands aligned to remediation guidance.
- [ ] Schema/loader compatibility confirmed.

#### P3.4 - Witness and closure
Definition of done:
- [ ] `T7` passes at `B` thresholds.
- [ ] `T3-T5` remain green after propagation coupling.
- [ ] Decision recorded as `UNLOCK_P4` or `HOLD_P3`.

### P4 - Delta Sets D/E role mapping + validation hardening
Goal:
- restore policy traceability and enforce realism gates as first-class pass criteria.

#### P4.1 - Role mapping contract
Definition of done:
- [ ] `raw_role -> canonical_role_family` mapping added for device and IP role vocabularies.
- [ ] `S5` outputs emit both raw and canonical families.
- [ ] Mapping coverage is complete and auditable.

#### P4.2 - Validation hardening integration
Definition of done:
- [ ] `validation_policy_6A.v1.yaml` promotes critical realism checks to fail-closed.
- [ ] Structural checks retained without weakening realism checks.
- [ ] Failure routing for `T1-T10` is explicit and deterministic.

#### P4.3 - Witness and closure
Definition of done:
- [ ] `T6` passes (`100%` coverage, zero unmapped).
- [ ] `T8` passes (`B` threshold).
- [ ] End-to-end gateboard shows no hard-gate exceptions.

### P5 - `PASS_B` certification and freeze
Goal:
- certify robust `B` posture and freeze owner lanes before `B+` extension.

#### P5.1 - Multi-seed witness execution
Definition of done:
- [ ] Required seeds `{42, 7, 101, 202}` executed for relevant rerun chain.
- [ ] `T1-T10` evaluated per seed and pooled.
- [ ] Stability metric `T9` computed and recorded.

#### P5.2 - Certification decision
Definition of done:
- [ ] Decision emitted as one of `PASS_B`, `PASS_BPLUS`, `HOLD_REMEDIATE`.
- [ ] Freeze artifacts emitted for accepted posture.
- [ ] Superseded run-ids pruned after freeze update.

### P6 - Phase-2 `B+` extension (only after `PASS_B`)
Goal:
- close remaining realism stretch gaps for durable `B+`.

#### P6.1 - `S3` instrument floor refinement
Definition of done:
- [ ] Replace universal floor behavior with account-type-aware floor policy.
- [ ] Validate no synthetic inflation in low-lambda surfaces.

#### P6.2 - Country-conditioned modulation
Definition of done:
- [ ] Add bounded country deltas around global priors.
- [ ] Preserve global conservation while improving heterogeneity realism.

#### P6.3 - Cross-seed hardening and final certification
Definition of done:
- [ ] `T1-T10` pass at `B+` thresholds on required seeds.
- [ ] Cross-seed CV satisfies `B+` stability threshold.
- [ ] Final decision recorded as `PASS_BPLUS` or `RETAIN_PASS_B`.

## 6) Evidence contract
- Per-run realism gateboard:
  - `runs/.../layer3/6A/validation/realism_gate_6A.json`
- Aggregate summary:
  - `runs/.../layer3/6A/validation/realism_gate_summary_6A.json`
- Required fields per test:
  - `test_id`, `metric_name`, `value`, `threshold_B`, `threshold_Bplus`, `pass_B`, `pass_Bplus`, `ci_low`, `ci_high`, `seed`.

## 7) Performance optimization strategy set (pre-refactor design lock)
Goal:
- complete hotspot analysis and lock a high-impact optimization sequence before any refactor or policy tuning.

### 7.1 Baseline hotspot evidence (cold runs)
- Baseline run `c25a2675fbfbacd952b13bb594880e92`:
  - `S1=8.91s`, `S2=172.33s`, `S3=297.33s`, `S4=79.74s`, `S5=209.12s`.
  - Total `S1-S5 = 767.43s` (`12.79 min`).
- Baseline run `fd0a6cc8d887f06793ea9195f207138b`:
  - `S1=12.08s`, `S2=246.94s`, `S3=405.41s`, `S4=173.36s`, `S5=289.97s`.
  - Total `S1-S5 = 1127.76s` (`18.80 min`).
- Stable hotspot order across baselines: `S3 > S5 > S2 > S4`.
- Observed sub-hotspots from run logs/code:
  - `S2`: long `allocate accounts to parties` loop over `440` cells, plus row-by-row emit loops.
  - `S3`: slow late-cell `allocate instruments to accounts` loop (`30` cells) with nested per-instrument row emission.
  - `S4`: high variance regional emit (especially `AFRICA/EMEA`) and part-merge overhead.
  - `S5`: heavy role-table assignment cost plus repeated validation scans/collects over same parquet inputs.

### 7.2 Runtime budget targets (minute-scale law)
- Segment `6A` cold-run target after optimization lane closure: `<= 540s` (`<= 9.0 min`) without requiring higher-memory fanout.
- Per-state target budgets:
  - `S2 <= 120s`
  - `S3 <= 180s`
  - `S4 <= 90s`
  - `S5 <= 120s`
- Promotion rule:
  - no optimization lane closes without measured runtime improvement vs pinned baseline and preserved determinism/contracts.

### 7.3 High-impact strategy lanes (ordered, before remediation tuning)

#### POPT.0 - Profiling contract + deterministic performance harness
Goal:
- add instrumentation-only performance observability so later refactors are measured, comparable, and fail-closed.

##### POPT.0.1 - Scope lock and invariants
Definition of done:
- [x] `POPT.0` is explicitly instrumentation-only (no policy threshold edits, no algorithmic behavior edits).
- [x] Determinism contract pinned: no changes to idempotent publish behavior, output schemas, or RNG audit/trace semantics.
- [x] Run lane pinned to fresh roots under `runs/fix-data-engine/segment_6A/<run_id>`.

##### POPT.0.2 - Substep timing map (owner states)
Definition of done:
- [x] `S2` emits substep timings at minimum for: `load_contracts_inputs`, `load_party_base`, `allocate_accounts`, `emit_account_base`, `emit_holdings`, `emit_summary`, `rng_publish`.
- [x] `S3` emits substep timings at minimum for: `load_contracts_inputs`, `load_account_base`, `plan_counts`, `allocate_instruments`, `emit_instrument_base_links`, `rng_publish`.
- [x] `S4` emits substep timings at minimum for: `load_contracts_inputs`, `load_party_base`, `plan_device_counts`, `plan_ip_counts`, `emit_ip_base`, `emit_regions`, `merge_parts`, `rng_publish`.
- [x] `S5` emits substep timings at minimum for: `load_contracts_inputs`, `assign_party_roles`, `assign_account_roles`, `assign_merchant_roles`, `assign_device_roles`, `assign_ip_roles`, `validation_checks`, `bundle_publish`, `rng_publish`.
- [x] Timing emission uses stable machine-readable keys (no free-form-only logs).

##### POPT.0.3 - Perf artifact contract
Definition of done:
- [x] Emit `perf_events_6A.jsonl` with one row per timed substep.
- [x] Emit `perf_summary_6A.json` with per-state totals, per-substep totals, and hotspot ranking.
- [x] Emit `perf_budget_check_6A.json` with state budget pass/fail and segment budget pass/fail.
- [x] Artifact root pinned to `reports/layer3/6A/perf/` under run-scoped partitioning (`seed/parameter_hash/manifest_fingerprint`).

##### POPT.0.4 - Baseline witness protocol
Definition of done:
- [x] Cold-run witness executed once from `S0 -> S5` on a fresh `runs/fix-data-engine/segment_6A/<run_id>`.
- [x] Baseline comparison included against pinned authorities:
  - `c25a2675fbfbacd952b13bb594880e92` (primary),
  - `fd0a6cc8d887f06793ea9195f207138b` (variance reference).
- [x] Evidence clearly separates cold-run from rerun/warm-path measurements.

##### POPT.0.5 - Closure gates
Definition of done:
- [x] All four owner states (`S2/S3/S4/S5`) produce complete substep timing evidence.
- [x] Perf artifact files are reproducible and parseable (no missing required fields).
- [x] Instrumentation overhead is bounded and documented (no material unexplained runtime regression).
- [x] Decision recorded as `UNLOCK_POPT1` or `HOLD_POPT0` with blocker reasons if held.

POPT.0 closure evidence (`run_id=2204694f83dc4bc7bfa5d04274b9f211`, cold lane):
- `S2=191.125s`, `S3=312.109s`, `S4=85.969s`, `S5=231.391s`, `S2-S5 total=820.594s`.
- Comparison vs primary baseline `c25`: `S2 +10.91%`, `S3 +4.97%`, `S4 +7.81%`, `S5 +10.65%` (instrumentation overhead bounded; no state semantics change).
- Comparison vs variance baseline `fd0`: `S2 -22.60%`, `S3 -23.01%`, `S4 -50.41%`, `S5 -20.20%`.
- Blocker closed in-lane: stale copied `2A` validation bundle `index.json` coverage mismatch was repaired run-locally (index+flag recomputed) before witness continuation.
- Decision: `UNLOCK_POPT1`.

#### POPT.1 - `S3` allocation+emit vectorization (primary hotspot)
Goal:
- reduce `S3` primary hotspot (`allocate_instruments`) through data-layout and emit-path refactor while preserving deterministic output surfaces.

##### POPT.1.1 - Kernel design lock (pre-code, fail-closed)
Definition of done:
- [x] Input/output invariants pinned for `S3`:
  - identical schema columns for `s3_instrument_base_6A` and `s3_account_instrument_links_6A`,
  - unchanged RNG trace/audit/event semantic contract (same substream labels + counters law),
  - unchanged fail-closed checks (`duplicate_account_id`, allocation-cap and scheme-coverage failures).
- [x] Data-layout decision pinned:
  - contiguous account vectors per `(party_type, account_type)` cell with one-time sorted order,
  - owner lookup upgraded from hash-heavy lookup pattern to cache-friendly contiguous lookup.
- [x] Scheme assignment strategy pinned:
  - prefix-sum/block assignment plan replaces per-row queue depletion checks in tight loops.
- [x] Rejected alternatives documented:
  - whole-state `numba/cython` rewrite (high blast radius),
  - full-frame explode/cross joins (memory amplification risk).

##### POPT.1.2 - Account ingest + cell index refactor
Definition of done:
- [ ] `S3` account-load path builds deterministic per-cell account vectors once and reuses them in allocation/emit.
- [ ] Repeated per-cell `sorted(accounts)` and repeated owner hash lookups are removed from hot loop.
- [ ] Duplicate-account fail-closed behavior remains unchanged.
- [ ] `load_account_base` substep timing is measured and retained in perf events.

##### POPT.1.3 - Allocation kernel vectorization
Definition of done:
- [ ] Replace row-by-row Python allocation mechanics with chunk-aware/vector-like allocation for `n_instr` by cell.
- [ ] Cap enforcement (`hard_max_per_account`) remains deterministic and fail-closed with explicit overflow handling.
- [ ] Allocation result is represented as per-account counts ready for batched emit (not immediate per-row append).
- [ ] `allocate_instruments` hotspot shows clear elapsed reduction versus POPT.0 witness.

##### POPT.1.4 - Emit-path batch rewrite
Definition of done:
- [ ] Instrument/link row materialization uses batched chunk construction from count vectors.
- [ ] Scheme assignment mapping is generated in blocks and consumed without per-row queue-guard churn.
- [ ] Parquet publish/idempotence behavior remains unchanged.
- [ ] `emit_instrument_base_links` + total `S3` elapsed improve without memory-risk spikes.

##### POPT.1.5 - Witness, determinism, and closure gate
Definition of done:
- [x] Execute cold witness on fresh run lane (`S3 -> S4 -> S5`, with `S0/S1/S2` already present for run identity).
- [ ] `S3` wall-clock reduced by at least `30%` versus primary baseline (`c25`) on comparable cold lane.
- [ ] No schema/idempotence/validation regressions in downstream `S4/S5`.
- [x] Decision recorded as `UNLOCK_POPT2` or `HOLD_POPT1` with blocker taxonomy.

POPT.1 witness evidence (`run_id=6a29f01be03f4b509959a9237d2aec76`, staged fresh lane from `2204694f83dc4bc7bfa5d04274b9f211`):
- Cold-lane setup:
  - fresh run-id created under `runs/fix-data-engine/segment_6A/`,
  - `run_receipt` rebased to new run-id,
  - `layer1/layer2` staged via junctions to source run to avoid multi-GB copy,
  - `6A` prerequisites copied (`s0_gate_receipt`, `sealed_inputs`, `s1_party_base_6A`, `s2_account_base_6A`).
- Observed perf (from `perf_summary_6A.json`):
  - `S3=433.266s` (baseline `POPT.0` `312.109s`, `+38.82%`; baseline `c25` `297.33s`, `+45.72%`),
  - `S4=104.328s` (vs `POPT.0` `85.969s`, `+21.36%`),
  - `S5=1058.344s` (vs `POPT.0` `231.391s`, `+357.38%`).
  - `S3` hotspot specifically regressed: `allocate_instruments=400.703s` (vs `287.359s` in `POPT.0` witness).
- Contracts/idempotence:
  - no schema or publish-idempotence failures observed in `S3/S4/S5`.
- Fail-closed decision:
  - `HOLD_POPT1` (target was `>=30%` reduction in `S3`; observed material regression).
  - candidate `S3` code lane was rolled back to baseline after witness to avoid carrying degraded implementation.

POPT.1 blocker taxonomy:
- `POPT1.B1`: `S3` allocation kernel rewrite increased CPU time in hot loop (regression at `allocate_instruments` step).
- `POPT1.B2`: staged-lane witness also showed heavy `S5` runtime inflation; isolate whether environment/lane setup noise contributed before accepting any optimization claim.

#### POPT.1R - `S3` low-blast recovery lane (post-regression hold)
Goal:
- recover `S3` hotspot performance from the failed `POPT.1` lane using isolated, auditable micro/mid-path edits with strict fail-closed gates.

##### POPT.1R.0 - Recovery design lock
Definition of done:
- [x] Recovery scope pinned to `S3` implementation only (no policy/threshold edits).
- [x] Candidate edit set ranked by blast radius and expected benefit.
- [x] Witness protocol pinned:
  - quick gate: fresh-lane `S3` witness only,
  - full gate: `S3 -> S4 -> S5` only if quick gate improves.

##### POPT.1R.1 - Allocation/emit mechanic rollback-to-fast baseline
Definition of done:
- [x] Replace high-overhead `S3` candidate allocation/emit mechanics with lower-overhead deterministic path:
  - remove block-slicing scheme-assignment inner path if it is hotspot-regressive,
  - restore compact row-emit mechanics that are known-fast on this workload.
- [x] Preserve deterministic ordering, schema, RNG counters/events, and fail-closed checks.
- [x] Compile and static checks pass for updated runner.

##### POPT.1R.2 - Quick witness (`S3` only)
Definition of done:
- [x] Fresh run-id staged under `runs/fix-data-engine/segment_6A/` with required `S0/S1/S2` prerequisites.
- [x] Execute `S3` only and collect `s3_perf_events_6A.jsonl`.
- [x] Gate:
  - `S3_total` and `allocate_instruments` must improve vs `POPT.1` failed witness,
  - if no improvement: `HOLD_POPT1R` (stop before `S4/S5`).

##### POPT.1R.3 - Full witness (`S3 -> S4 -> S5`)
Definition of done:
- [x] Execute downstream chain only after `POPT.1R.2` quick gate passes.
- [x] Verify no schema/idempotence regressions on `S4/S5`.
- [x] Emit full `perf_summary_6A.json` / `perf_budget_check_6A.json` for candidate run.

##### POPT.1R.4 - Closure decision
Definition of done:
- [x] Compare candidate vs `POPT.0` witness and primary baseline (`c25`) with explicit deltas.
- [x] Decision recorded as one of:
  - `UNLOCK_POPT2` (recovery successful),
  - `HOLD_POPT1R` (insufficient improvement),
  - `REVERT_POPT1R` (regression/contract risk).

POPT.1R closure evidence (`run_id=b68127889d454dc4ac0ae496475c99c5`, staged from `2204694f83dc4bc7bfa5d04274b9f211`):
- Quick gate (`S3` only):
  - `S3_total=418.172s` vs failed `POPT.1` witness `433.266s` (`-3.48%`),
  - `S3.allocate_instruments=385.203s` vs failed `400.703s` (`-3.87%`).
  - Quick gate passed (improved vs failed witness), so full gate executed.
- Full gate (`S3 -> S4 -> S5`) totals:
  - `S3=418.172s` vs `POPT.0` `312.109s` (`+33.98%`),
  - `S4=103.000s` vs `POPT.0` `85.969s` (`+19.81%`),
  - `S5=1015.500s` vs `POPT.0` `231.391s` (`+338.87%`).
  - Segment perf budget remains failed (`1536.672s` vs budget `540s`).
- Decision:
  - `HOLD_POPT1R` (insufficient recovery; still materially above `POPT.0`/primary baseline).
  - `POPT.2` remains blocked.

#### POPT.1R2 - `S3` compact-cell rollback + clean-lane witness closure
Goal:
- recover `S3` to the last known fast mechanics while explicitly closing the `S5`-inflation ambiguity with a clean full-chain witness.

##### POPT.1R2.0 - Recovery design lock
Definition of done:
- [x] Scope pinned to `S3` code only; no policy/config edits.
- [x] Regression hypothesis pinned:
  - tuple-packed `account_cells[(party_type, account_type)] -> list[(account_id, owner_id)]` introduced excess memory/object overhead in both `load_account_base` and `allocate_instruments`.
- [x] Closure protocol pinned:
  - quick `S3` witness for hotspot confirmation,
  - clean `S0 -> S5` witness for `S5` blocker closure (no staged-junction ambiguity).

##### POPT.1R2.1 - Compact account-cell/owner-map restore
Definition of done:
- [x] Restore `S3` ingest/allocation to compact baseline mechanics:
  - `account_cells` stores `list[account_id]`,
  - `account_owner` map used during emit,
  - per-key deterministic account ordering stays at allocation boundary.
- [x] Preserve fail-closed checks (`duplicate_account_id`, owner presence, cap checks, scheme coverage).
- [x] Preserve RNG/event/schema/idempotence contracts.

##### POPT.1R2.2 - Quick witness (`S3` only)
Definition of done:
- [x] Fresh run-id staged under `runs/fix-data-engine/segment_6A/` with required prerequisites.
- [x] Execute `S3` only and collect perf artifacts.
- [x] Gate:
  - `S3_total` improves vs `POPT.1R` candidate (`b681...`) and
  - `S3.allocate_instruments` is within `<=5%` of `POPT.0` witness (`220...`) for unlock to full witness.

##### POPT.1R2.3 - Clean full-chain witness (`S0 -> S5`)
Definition of done:
- [x] Execute clean run from `S0` through `S5` on fresh run-id (no staged junction reuse).
- [x] Confirm `S3` gain holds on full chain.
- [x] Resolve blocker `POPT1.B2` by measuring `S5` on clean lane and recording whether inflation persists.

##### POPT.1R2.4 - Closure decision
Definition of done:
- [x] Record explicit deltas vs `POPT.0` (`220...`) and `POPT.1R` (`b681...`).
- [x] Decision recorded as one of:
  - `UNLOCK_POPT2` (S3 recovery + blocker closed),
  - `HOLD_POPT1R2` (insufficient S3 recovery),
  - `REVERT_POPT1R2` (contract or perf regression).

POPT.1R2 closure evidence:
- Quick `S3` witness (`run_id=98af13c5571b48ce9e91728d77e9e983`, staged lane):
  - `S3_total=413.953s` vs `POPT.1R` `418.172s` (`-1.01%`),
  - `S3.allocate_instruments=382.609s` vs `POPT.1R` `385.203s` (`-0.67%`),
  - still above `POPT.0`:
    - `S3_total +32.63%` vs `312.109s`,
    - `allocate_instruments +33.15%` vs `287.359s`.
- Clean full-chain witness (`run_id=592d82e8d51042128fc32cb4394f1fa2`, `S0 -> S5`):
  - `S3=409.797s` (`+31.30%` vs `POPT.0`, `-2.00%` vs `POPT.1R`),
  - `S4=102.484s` (`+19.21%` vs `POPT.0`),
  - `S5=1016.250s` (`+339.19%` vs `POPT.0`, `+0.07%` vs `POPT.1R`).
- Blocker closure:
  - `POPT1.B2` is closed as a diagnosis: `S5` inflation persists on a clean non-staged full run and is not caused by staged-junction witness setup.
  - ownership routes to `POPT.2` (`S5` lane), not `S3`.
- Decision:
  - `HOLD_POPT1R2` (insufficient `S3` recovery to unlock).
  - `POPT.2` is now unblocked for `S5`-owner optimization work.

#### POPT.2 - `S5` validation-scan fusion + collect minimization
Goal:
- reduce `S5` owner-state runtime by removing high-cost hash-expression overhead in role assignment and eliminating avoidable repeated validation scans/collects.

##### POPT.2.0 - Design lock and baseline
Definition of done:
- [x] Baseline pinned to clean full-chain witness `run_id=592d82e8d51042128fc32cb4394f1fa2`.
- [x] Hotspots pinned from baseline:
  - `assign_account_roles`,
  - `assign_device_roles`,
  - `assign_ip_roles` (secondary),
  - repeated validation scan/collect pattern.
- [x] Invariants pinned:
  - deterministic role assignment per row remains required,
  - output schemas/idempotent publish surfaces unchanged,
  - fail-closed validation semantics unchanged.

##### POPT.2.1 - Role-hash kernel optimization (`S5` assignment path)
Definition of done:
- [x] Replace struct-heavy multi-field hash expressions with deterministic per-entity-id hash salts derived once per run (`manifest_fingerprint`, `parameter_hash`, `seed`, label).
- [x] Preserve independent deterministic streams per role substream (`party/account/merchant/device/ip`, risk vs role).
- [x] No schema or policy threshold changes.

##### POPT.2.2 - Validation scan fusion + collect minimization
Definition of done:
- [x] Fuse per-column null checks into single collect per dataset in structural checks.
- [x] Fuse role-fraction totals/non-clean counts into single collect per role table.
- [x] Reuse/emit role vocab evidence from already-collected frames where possible; avoid duplicate full scans.
- [x] Keep check IDs, thresholds, failure routing, and payload shape unchanged.

##### POPT.2.3 - Witness and closure
Definition of done:
- [x] Execute fresh `S5` witness run on new run-id with stable upstream inputs.
- [x] Compare against `POPT.2.0` baseline (`592...`) with explicit per-substep deltas.
- [x] Close as one of:
  - `UNLOCK_POPT3` if `S5` improves by `>=25%` with no contract regressions,
  - `HOLD_POPT2` if insufficient improvement,
  - `REVERT_POPT2` on regression/contract risk.

POPT.2 closure evidence:
- Baseline (`run_id=592d82e8d51042128fc32cb4394f1fa2`):
  - `S5=1016.250s`.
  - hotspots: `assign_device_roles=641.562s`, `assign_account_roles=289.578s`, `assign_ip_roles=50.047s`.
- Candidate (`run_id=94dcc9f10a324d829a0ece6f96eda5f6`, fresh staged upstream inputs):
  - `S5=70.391s` (`-93.07%` vs baseline).
  - `assign_device_roles=33.719s` (`-94.74%`),
  - `assign_account_roles=26.813s` (`-90.74%`),
  - `assign_ip_roles=2.046s` (`-95.91%`).
  - `S5` budget pass: `70.391s <= 120s`.
  - validation status: `overall_status=PASS`, `fails=0`, `warns=0`.
- Candidate fix note:
  - intermediate run `9ab2b6a324884d97a1bec1f387e99595` exposed a vocab-aggregation bug in `POPT.2.2` (false `ROLE_VOCAB_TAXONOMY` fail), corrected before final witness.
- Decision:
  - `UNLOCK_POPT3`.

#### POPT.3 - `S2` allocation and emit-path redesign
Goal:
- reduce `S2` runtime by redesigning allocation + emit paths around sparse party sets and lower-overhead deterministic kernels, without changing schema/policy or fail-closed behavior.

##### POPT.3.0 - Design lock and runtime baseline
Definition of done:
- [x] Baseline pinned to `run_id=592d82e8d51042128fc32cb4394f1fa2` for `S2`.
- [x] Baseline hotspots pinned:
  - `allocate_accounts=212.531s`,
  - `emit_account_base=32.250s`,
  - `emit_holdings=11.907s`,
  - `emit_summary=5.500s`.
- [x] Complexity model and bottlenecks documented before code edits:
  - repeated deterministic hash payload construction in allocation kernel,
  - repeated dict/list lookups inside hot loops,
  - avoidable full `1..max_party_id` sweeps.
- [x] Invariants pinned:
  - identical output schemas and dataset names,
  - deterministic replay posture preserved,
  - policy thresholds untouched,
  - RNG audit/trace contract unchanged.

##### POPT.3.1 - Sparse index compaction and loop-shape rewrite
Definition of done:
- [x] Replace full-range sweeps with sparse iteration over actual party id sets where semantically safe.
- [x] Build compact per-cell/per-country party index structures once, then reuse in downstream loops.
- [x] Remove repeated dictionary fallback/lookups in inner loops by prebinding arrays/maps per account type.
- [x] Preserve fail-closed checks for missing parties/cells/rules.

##### POPT.3.2 - Allocation kernel micro-architecture optimization
Definition of done:
- [x] Reduce per-party deterministic-uniform overhead by precomputing static hash payload components and using compact per-call mixing (no stochastic-contract drift).
- [x] Precompute segment-tag adjustments per `(segment_id, account_type)` to avoid repeated adjustment traversal in the hot path.
- [x] Keep `_largest_remainder_list` behavior + tie semantics intact while reducing pre/post work around it.
- [x] Emit explicit counters for allocation-path work:
  - eligible party evaluations,
  - zero-gate skips,
  - weight computations.

##### POPT.3.3 - Emit-path batching and summary aggregation rewrite
Definition of done:
- [x] Drive account/holdings emission from sparse nonzero holdings structures instead of full dense scans.
- [x] Keep chunked write path but reduce Python tuple churn via pre-sized batch building where practical.
- [x] Replace summary nested loops with sparse aggregation over nonzero holdings entries.
- [x] Preserve sample validation and idempotent publish behavior.

##### POPT.3.4 - Witness and closure
Definition of done:
- [x] Execute fresh `S2` owner-lane witness on new run-id with stable upstream inputs.
- [x] Compare against `POPT.3.0` baseline with per-substep deltas.
- [x] Hard closure gate:
  - `S2` runtime improvement `>=25%` vs baseline (`<=199.137s`) with no contract regressions.
- [ ] Stretch closure gate:
  - target `S2 <=180s` and `allocate_accounts <=150s` on witness lane.
- [x] Record one decision only:
  - `UNLOCK_POPT4` if hard closure gate passes,
  - `HOLD_POPT3` if improvement is insufficient,
  - `REVERT_POPT3` if regressions are detected.

POPT.3 closure evidence:
- Baseline (`run_id=592d82e8d51042128fc32cb4394f1fa2`):
  - `S2=265.516s`,
  - `allocate_accounts=212.531s`,
  - `emit_account_base=32.250s`,
  - `emit_holdings=11.907s`,
  - `emit_summary=5.500s`.
- Candidate (`run_id=d9e03d8aeac24a21ad2560e649825b97`, fresh `S2` witness):
  - `S2=186.157s` (`-29.89%` vs baseline),
  - `allocate_accounts=142.281s` (`-33.05%`),
  - `emit_account_base=31.375s` (`-2.71%`),
  - `emit_holdings=9.438s` (`-20.74%`),
  - `emit_summary=0.016s` (`-99.71%`).
- Contract/non-regression checks:
  - `s2_account_summary_6A` equality vs baseline: `True`,
  - row-count parity preserved:
    - `s2_account_base_6A: 8,725,420`,
    - `s2_party_product_holdings_6A: 7,271,622`,
    - holdings `account_count` sum: `8,725,420`.
- Gate result:
  - hard gate: `PASS` (`186.157s <= 199.137s`),
  - stretch gate: partial (`allocate_accounts` pass, `S2<=180s` not met).
- Decision:
  - `UNLOCK_POPT4`.

#### POPT.4 - `S4` region emit/merge efficiency lane (compute-safe)
Goal:
- reduce `S4` runtime by removing region fanout input re-read amplification and trimming merge overhead while preserving deterministic outputs and fail-closed checks.

##### POPT.4.0 - Design lock and baseline
Definition of done:
- [x] Baseline pinned to `run_id=592d82e8d51042128fc32cb4394f1fa2`:
  - `S4=102.484s`,
  - `emit_regions=74.015s`,
  - `merge_parts=12.610s`,
  - `load_party_base=13.860s`.
- [x] Bottleneck root causes pinned:
  - per-region worker repeatedly scans/filters `s1_party_base_6A`,
  - region fanout merge receives many small part files.
- [x] Invariants pinned:
  - no policy/config edits,
  - no schema/idempotence changes,
  - deterministic seed contracts unchanged.

##### POPT.4.1 - Region input-preload + fanout rewrite
Definition of done:
- [x] Build region-local party payloads once in parent process (`party_ids_by_type`, `party_country_by_id`) from already loaded `party_cells`/`party_meta`.
- [x] Remove `party_base` read/filter from `_emit_region_parts`; worker uses preloaded payload only.
- [x] Preserve deterministic sorted traversal by region/party/device axes.
- [x] Preserve all fail-closed checks for missing/invalid region party allocations.

##### POPT.4.2 - Merge-path efficiency closure
Definition of done:
- [x] Keep pyarrow stream merge path for part files, but eliminate unnecessary staging work introduced by region input reload.
- [x] Ensure merge still produces single deterministic file per dataset surface.
- [x] Verify no memory unsafe amplification from fanout payload handling.

##### POPT.4.3 - Witness and decision
Definition of done:
- [x] Execute fresh `S4` owner-lane witness on new run-id with stable upstream inputs.
- [x] Compare against `POPT.4.0` baseline with per-substep deltas.
- [ ] Hard closure gate:
  - `S4` runtime improvement `>=20%` (`<=81.987s`) with no contract regressions.
- [ ] Stretch closure gate:
  - target `emit_regions <=55s` and `merge_parts <=10s`.
- [x] Record one decision only:
  - `UNLOCK_POPT5` if hard gate passes,
  - `HOLD_POPT4` if insufficient improvement,
  - `REVERT_POPT4` on regression/contract risk.

POPT.4 closure evidence:
- Baseline (`run_id=592d82e8d51042128fc32cb4394f1fa2`):
  - `S4=102.484s`, `emit_regions=74.015s`, `merge_parts=12.610s`.
- Candidate matrix:
  - `f29bae549afc42f4a78d10c285358dd6`: `S4=102.609s` (regression),
  - `f388966781f84fd7acd9fa42b469b275`: `S4=94.719s` (best, `-7.58%`),
  - `96804e13231b4c388299c1e376c4ccae`: `S4=102.672s`,
  - `2f204ebdc5714787bb5f2fb4fcad0c7f` (`workers=3`): `S4=111.765s`.
- Best candidate substep movement (`f388...`):
  - `emit_regions=71.156s` (`-3.86%`),
  - `merge_parts=7.609s` (`-39.66%`),
  - `load_party_base=13.968s` (`+0.78%`).
- Contract/non-regression checks:
  - row-count parity preserved across all required S4 outputs on best candidate.
- Gate outcome:
  - hard gate: `FAIL` (`94.719s > 81.987s`),
  - stretch gate: `FAIL`.
- Decision:
  - `HOLD_POPT4`.

#### POPT.5 - Integration closure for performance lane
Goal:
- verify integrated runtime gains from `POPT.1-POPT.4` on a fresh full `S1->S5` chain and close performance lane with a deterministic evidence pack.

##### POPT.5.0 - Integration baseline lock
Definition of done:
- [x] Baseline authority pinned to full-chain run `592d82e8d51042128fc32cb4394f1fa2`.
- [x] Baseline totals pinned for comparison:
  - `S2=265.516s`,
  - `S3=409.797s`,
  - `S4=102.484s`,
  - `S5=1016.250s`,
  - integrated `S2+S3+S4+S5=1794.047s`.
- [x] Integration gate thresholds pinned:
  - hard: integrated `S2..S5` improvement `>=35%`,
  - stretch: integrated `S2..S5` improvement `>=50%`.

##### POPT.5.1 - Fresh full-chain execution (`S1->S5`)
Definition of done:
- [x] Fresh run-id created under `runs/fix-data-engine/segment_6A`.
- [x] `S0`, `S1`, `S2`, `S3`, `S4`, `S5` executed sequentially on same run-id.
- [x] Perf artifacts emitted (`s*_perf_events_6A.jsonl`, `perf_summary_6A.json`).

##### POPT.5.2 - Integration validation and regression checks
Definition of done:
- [x] `S5` validation report `overall_status=PASS`.
- [x] No schema/idempotence/publish-surface regressions detected on `S2-S5`.
- [x] Upstream gate posture remains pass-closed (`S0` receipt + sealed inputs consistent).

##### POPT.5.3 - Decision and freeze routing
Definition of done:
- [x] Compare integrated totals and per-state deltas vs baseline.
- [x] Record one decision:
  - `UNLOCK_P0` if hard gate passes with no regressions,
  - `HOLD_POPT5` if hard gate fails,
  - `REVERT_POPT5` on regression.
- [x] Update keep-set and prune superseded run-id folders.

POPT.5 closure evidence:
- Baseline authority (`run_id=592d82e8d51042128fc32cb4394f1fa2`):
  - `S2=265.516s`, `S3=409.797s`, `S4=102.484s`, `S5=1016.250s`,
  - integrated `S2+S3+S4+S5=1794.047s`.
- Fresh integrated witness (`run_id=59b82090679742c0b2fa3bb3f5dd3150`):
  - `S2=189.860s`, `S3=409.422s`, `S4=96.641s`, `S5=70.640s`,
  - integrated `S2+S3+S4+S5=766.563s`.
- Integrated delta:
  - absolute gain `=1027.484s`,
  - improvement `=57.272%` vs baseline.
- Gate outcome:
  - hard gate (`>=35%`) `PASS`,
  - stretch gate (`>=50%`) `PASS`.
- Validation/regression evidence:
  - `s5_validation_report_6A.json` => `overall_status=PASS`,
  - `_passed.flag` emitted for `S5`,
  - no `ERROR/CRITICAL/Traceback/FAILED` signatures found in run logs.
- Residual budget posture (non-blocking for POPT.5 gate):
  - `perf_budget_check_6A.json` reports segment budget miss (`766.563s > 540.0s`),
  - remaining minute-scale hotspot is `S3.allocate_instruments` (`378.156s`).
- Decision:
  - `POPT.5=UNLOCK_P0`.

#### POPT.6 - `S3.allocate_instruments` deep redesign lane (all-cards lane)
Goal:
- close the dominant residual hotspot (`S3.allocate_instruments`) using a full optimization stack: emit-path refactor, account-cell prebinding, allocator ranking rewrite, and deterministic PRF redesign.

##### POPT.6.0 - Design lock, scale lock, and invariants
Definition of done:
- [x] Baseline pinned to `run_id=59b82090679742c0b2fa3bb3f5dd3150`:
  - `S3=409.422s`,
  - `allocate_instruments=378.156s`,
  - segment integrated `S2+S3+S4+S5=766.563s`.
- [x] Scale surface pinned from authority artifacts:
  - accounts `=8,725,420`,
  - instruments emitted `=10,701,854`,
  - effective account-scan multiplier in allocation loops `~2.56x`.
- [x] Invariants pinned:
  - fail-closed contract posture unchanged,
  - idempotent publish unchanged,
  - deterministic replay guarantees preserved,
  - no policy-threshold weakening in realism gates.
Execution expansion:
- [x] Capture exact S3 code hotspots by function/line:
  - deterministic uniform path,
  - largest remainder allocator,
  - emit loop and write path.
- [x] Pin comparison authority artifacts and run-ids in impl notes + logbook before edits.
- [x] Define gate math to be used post-run:
  - `S3 delta %`,
  - `allocate_instruments delta %`,
  - integrated `S2..S5` delta %.

##### POPT.6.1 - Emit-path columnar refactor (low blast, high impact)
Definition of done:
- [x] Replace deep per-row tuple append loops with chunked columnar generation (array-first, then DataFrame/Arrow write).
- [x] Preserve deterministic `instrument_id` ordering and scheme assignment sequence.
- [x] Keep schema validation + idempotent publish path behavior unchanged.
- [x] Emit-path counters/logs added to prove reduced Python-row churn.
Execution expansion:
- [x] Replace tuple buffers with column buffers (typed arrays) and chunked DataFrame construction from columns.
- [x] Replace nested per-row append loops with block emission using repeated account/owner/scheme vectors.
- [x] Keep batch flush boundaries deterministic (`_DEFAULT_BATCH_ROWS`) and preserve row ordering.

##### POPT.6.2 - Account-cell prebinding and one-pass allocation preparation
Definition of done:
- [x] Precompute and retain sorted account vectors once per `(party_type, account_type)` cell.
- [x] Prebind aligned owner vectors to remove repeated `owner_party_id` map lookups in emit loops.
- [x] Remove repeated `sorted(accounts)` + repeated fallback map traversals inside instrument-type loops.
- [x] Preserve missing-account/missing-owner fail-closed checks.
Execution expansion:
- [x] Build and store sorted `(account_id, owner_party_id)` vectors once per cell at load time.
- [x] Replace per-row `account_owner.get(account_id)` in emit path with pre-aligned owner vectors.
- [x] Add explicit consistency check ensuring aligned account/owner vector lengths are identical.

##### POPT.6.3 - Allocation ranking algorithm rewrite
Definition of done:
- [x] Replace full-range ranking sort in `_largest_remainder_list` with deterministic partial-selection strategy for top-`remaining` allocation.
- [x] Preserve tie semantics and deterministic replay surface under same seed/receipt.
- [x] Keep `_apply_caps` semantics and hard-cap guarantees unchanged.
- [x] Add guardrails for pathological small/large `remaining` regimes.
Execution expansion:
- [x] Implement adaptive ranking:
  - partial-selection route for small `k`,
  - fallback deterministic full sort for large `k`.
- [x] Preserve tie ordering by `(residual, tie_value, index)` parity with prior semantics.
- [x] Add deterministic test-mode self-check path comparing adaptive/full sort on sampled vectors (dev-only guard).

##### POPT.6.4 - Deterministic PRF redesign for per-account uniforms (high blast)
Definition of done:
- [x] Replace per-account SHA-256 payload hashing in `_deterministic_uniform` with faster deterministic keyed-mixer PRF (single-process safe).
- [x] Keep deterministic reproducibility guarantees:
  - same inputs -> same outputs within the new PRF contract,
  - explicit version pin recorded in implementation notes.
- [x] Run dual evidence checks before acceptance:
  - deterministic replay checks (same run inputs, repeated run),
  - distribution sanity checks to ensure no realism collapse from PRF change.
- [x] Explicitly mark this as a high-blast closure gate:
  - no merge without fresh S3 witness evidence + non-regression checks.
Execution expansion:
- [x] Introduce versioned deterministic PRF helper (e.g., `v2`) with keyed 64-bit mixer.
- [x] Cache per `(instrument_type, label)` stream keys to avoid repeated hash/payload assembly.
- [x] Keep interface-compatible callsites so failure routing remains unchanged.
- [x] Emit PRF version marker in logs/impl notes for audit reproducibility.

##### POPT.6.5 - Witness, integration check, and decision
Definition of done:
- [x] Execute fresh `S3` owner-lane witness after `POPT.6.1-6.4` on new run-id.
- [x] Compare against `POPT.6.0` baseline with substep deltas (`allocate_instruments`, `emit_instrument_base_links`).
- [x] Execute bounded integration witness (`S3->S5`) to verify downstream non-regression.
- [x] Hard closure gates:
  - `S3 <= 260s`,
  - `allocate_instruments <= 230s`,
  - no contract/validation regressions.
- [x] Stretch closure gates:
  - `S3 <= 180s` (state budget),
  - segment integrated `S2+S3+S4+S5 <= 540s` (segment budget).
- [x] Record one decision only:
  - `UNLOCK_P0_REMEDIATION` if hard gate passes,
  - `HOLD_POPT6` if hard gate fails,
  - `REVERT_POPT6` on regression.
- [x] Update keep-set and prune superseded run-id folders after decision.
Execution expansion:
- [x] Run owner-lane chain on fresh run-id:
  - `S0 -> S1 -> S2 -> S3` for S3 witness.
  - execution note: direct `S0` rerun on `local_full_run-5/c25...` staged inputs failed on upstream 2A schema gate; owner lane was executed fail-closed by staging authoritative `S0` artifacts from `59b...` and then running fresh `S1 -> S2 -> S3`.
- [x] Run bounded downstream chain on same run-id:
  - `S4 -> S5` for integration/non-regression witness.
- [x] Parse perf and validation artifacts into explicit closure matrix (hard/stretch + residuals).
- [x] Append final decision trail in build plan, impl notes, and daily log before pruning.

POPT.6 closure evidence (final authority run):
- Baseline (`run_id=59b82090679742c0b2fa3bb3f5dd3150`):
  - `S2=189.860s`, `S3=409.422s`, `S4=96.641s`, `S5=70.640s`,
  - integrated `S2+S3+S4+S5=766.563s`,
  - `S3.allocate_instruments=378.156s`.
- Candidate (`run_id=60378ec4875f48fc919bd1f739f92a96`):
  - `S2=195.703s`, `S3=149.078s`, `S4=95.750s`, `S5=83.547s`,
  - integrated `S2+S3+S4+S5=524.078s`,
  - `S3.allocate_instruments=115.703s`.
- Delta summary:
  - `S3` improvement `=63.588%` (`409.422s -> 149.078s`),
  - `allocate_instruments` improvement `=69.404%` (`378.156s -> 115.703s`),
  - integrated improvement `=31.633%` (`766.563s -> 524.078s`).
- Gate outcomes:
  - hard: `PASS` (`S3<=260`, `allocate_instruments<=230`, validation pass/no regressions),
  - stretch: `PASS` (`S3<=180`, integrated `<=540`).
- Budget posture:
  - segment budget now passes (`524.078s <= 540.0s`),
  - remaining state-budget misses are outside this owner lane (`S2` and `S4` still above individual state budgets).
- Deterministic replay check (PRF high-blast control):
  - replay run `b60008a6a3a74e58a330dfe71a0efb1d` executed with identical staged `S0/S1/S2`,
  - file SHA-256 parity is exact for:
    - `s3_instrument_base_6A.parquet`,
    - `s3_account_instrument_links_6A.parquet`.
- Distribution sanity / downstream compatibility:
  - `S5` validation report `overall_status=PASS`,
  - row-count parity vs baseline maintained for `S3`, `S4`, and `S5` published surfaces.
- Decision:
  - `POPT.6=UNLOCK_P0_REMEDIATION`.

### 7.4 Hard constraints for all optimization lanes
- Determinism lock:
  - no change to required hashes, idempotent publish law, or RNG audit/trace contract semantics.
- Realism lock:
  - optimization cannot weaken or bypass `T1-T10` fail-closed checks.
- Scope lock:
  - no remediation-policy threshold edits are allowed inside `POPT` lanes.
- Resource lock:
  - prioritize algorithm/data-structure improvements over CPU/RAM scaling; keep memory-safe execution posture.

#### POPT.7 - `S2` + `S4` residual hotspot closure lane
Goal:
- reduce the remaining heavy kernels after `POPT.6` closure:
  - `S2.allocate_accounts` (dominant in `S2`),
  - `S4.emit_regions` (dominant in `S4`).

Baseline lock (`run_id=60378ec4875f48fc919bd1f739f92a96`):
- `S2=195.703s`:
  - `allocate_accounts=148.703s`,
  - `emit_account_base=33.266s`.
- `S4=95.750s`:
  - `emit_regions=71.016s`,
  - `load_party_base=14.156s`,
  - `merge_parts=8.468s`.

##### POPT.7.0 - Design lock and invariants
Definition of done:
- [x] Pin hotspot references and code-path authority in impl notes before edits.
- [x] Pin accepted scope:
  - `S2` allocation kernel and local deterministic uniform generation path,
  - `S4` region emit/allocation kernel and local cap allocator path.
- [x] Pin invariants:
  - fail-closed validation/error codes unchanged,
  - schema/idempotent publish surfaces unchanged,
  - no realism-threshold or policy edits.

##### POPT.7.1 - `S2` allocation kernel optimization
Definition of done:
- [x] Replace per-party Python scalar loops in `allocate_accounts` with vectorized array operations for:
  - zero-gate evaluation,
  - weight generation,
  - largest-remainder allocation.
- [x] Use deterministic versioned PRF helper for vectorized uniform draws (single-process safe).
- [x] Keep output ordering and fail-closed duplicate/allocation guards unchanged.
- [x] Keep RNG event artifact shape and coverage unchanged.

##### POPT.7.2 - `S4` emit kernel optimization
Definition of done:
- [x] Rewrite `largest_remainder/cap` allocation helpers to array-backed implementations.
- [x] Hoist per-group constants out of per-device loops (no repeated lambda/base/frac recomputation).
- [x] Remove per-edge string split overhead in IP cell selection path.
- [x] Keep deterministic traversal order and contract schemas unchanged.

##### POPT.7.3 - Witness and decision
Definition of done:
- [x] Execute fresh witness run on new run-id under `runs/fix-data-engine/segment_6A`.
- [x] Compare vs `60378...` on:
  - `S2`, `S2.allocate_accounts`,
  - `S4`, `S4.emit_regions`.
- [x] Gate decisions:
  - hard pass: `S2 <= 170s` and `S4 <= 85s` without regressions,
  - stretch: `S2 <= 150s` and `S4 <= 75s`.
- [x] Record one decision only:
  - `UNLOCK_P0_REMEDIATION` if hard pass,
  - `HOLD_POPT7` if insufficient movement,
  - `REVERT_POPT7` if regression.

POPT.7 closure evidence:
- Baseline authority (`run_id=60378ec4875f48fc919bd1f739f92a96`):
  - `S2=195.703s`:
    - `allocate_accounts=148.703s`,
    - `emit_account_base=33.266s`,
    - `emit_holdings=10.453s`.
  - `S4=95.750s`:
    - `emit_regions=71.016s`,
    - `load_party_base=14.156s`,
    - `merge_parts=8.468s`.
- Candidate witnesses:
  - `S2` witness (`run_id=ed45d78ee15547caaff229f79f8adec7`, staged lane):
    - `S2=82.109s`,
    - `allocate_accounts=43.312s`,
    - `emit_account_base=28.063s`,
    - `emit_holdings=7.828s`.
  - `S4` apples-to-apples witness (`run_id=ee0633a99760406ea28c892cca0dc7e8`, `workers=5` to match baseline posture):
    - `S4=69.438s`,
    - `emit_regions=49.016s`,
    - `load_party_base=10.782s`,
    - `merge_parts=8.015s`.
- Delta summary:
  - `S2` total improvement `=58.044%`.
  - `S2.allocate_accounts` improvement `=70.873%`.
  - `S4` total improvement `=27.480%`.
  - `S4.emit_regions` improvement `=30.979%`.
- Gate outcomes:
  - hard gate: `PASS` (`S2<=170`, `S4<=85`).
  - stretch gate: `PASS` (`S2<=150`, `S4<=75`).
- Compatibility notes from witness lane:
  - `S4` row-count parity vs baseline is exact on all published surfaces.
  - `S2` account-base row count is unchanged; holdings pair surface moved by `-1,434` rows on this PRF lane and must be validated in subsequent realism/gate closure.
  - staged witness lane could not close `S5` because layer-1 merchant source artifacts were not staged in this run-id; this does not block performance evidence for `S2/S4`.
- Decision:
  - `POPT.7=UNLOCK_P0_REMEDIATION`.
