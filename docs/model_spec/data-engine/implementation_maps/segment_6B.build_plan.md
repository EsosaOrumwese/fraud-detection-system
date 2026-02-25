# Segment 6B Optimization + Remediation Build Plan (B/B+ Recovery Plan)
_As of 2026-02-25_

## 0) Objective and closure rule
- Objective: move Segment `6B` from published/remediation posture (`D+`) to certified `PASS_B` first, then stable `PASS_BPLUS`.
- Closure rule:
  - `PASS_B`: all critical realism gates pass at `B` thresholds across required seeds, runtime budgets pass, and no unresolved fail-closed validation checks.
  - `PASS_BPLUS`: all `B` gates pass plus `B+` thresholds on required seeds with cross-seed stability.
  - `HOLD_REMEDIATE`: any critical realism gate fails, evidence is incomplete, or runtime budgets regress.
- Phase law: no phase advances until its DoD is fully closed.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_6B/segment_6B_published_report.md`
- `docs/reports/eda/segment_6B/segment_6B_remediation_report.md`

### 1.2 State/contract authority
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s0.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s1.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s2.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s3.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s4.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.layer3.yaml`
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`

### 1.3 Upstream freeze posture
- Upstream segments `1A`, `1B`, `2A`, `2B`, `3A`, `3B`, `5A`, `5B`, and `6A` are frozen during baseline `6B` remediation.
- Upstream reopen is allowed only by explicit lane and must preserve frozen segment certification artifacts.

## 2) Scope and ownership map
- `S1` owner lane:
  - attachment/session realism and runtime hotspot control,
  - linkage diversity and singleton-session pressure (`T19`, `T20` support).
- `S2` owner lane:
  - amount realism and timing realism activation (`T11-T16`, `T21`).
- `S3` owner lane:
  - campaign multiplicity/targeting depth (`T17`, `T18`) and non-regressive fraud overlay behavior.
- `S4` owner lane:
  - truth-label correctness, bank-view stratification, case-timeline temporal validity (`T1-T10`, `T22`).
- `S5` owner lane:
  - fail-closed realism gate enforcement and deterministic certification artifacts.
- Out of scope for first closure attempt:
  - non-authority schema redesign,
  - downstream platform tuning outside 6B contracts.

## 3) Target gates

### 3.1 Hard realism gates (`B`)
- `T1`: `LEGIT share > 0`.
- `T2`: `is_fraud_truth_mean` in `[0.02, 0.30]` (unless explicitly versioned target differs).
- `T3`: `% non-overlay NONE rows mapped LEGIT >= 99.0%`.
- `T4`: `% campaign-tagged rows mapped non-LEGIT >= 99.0%`.
- `T5`: Cramer's V(`bank_view_outcome`, `merchant_class`) `>= 0.05`.
- `T6`: amount-vs-bank-view effect-size floor `>= 0.05`.
- `T7`: class-conditioned bank-fraud spread `>= 0.03`.
- `T8`: negative case-gap rate `= 0`.
- `T9`: fixed-spike share (`3600s + 86400/86401s`) `<= 0.50`.
- `T10`: non-monotonic case-event time rate `= 0`.
- `T11`: distinct amount values `>= 20`.
- `T12`: `p99/p50 amount >= 2.5`.
- `T13`: top-8 amount share `<= 0.85`.
- `T14`: auth latency median in `[0.3s, 8s]`.
- `T15`: auth latency `p99 > 30s`.
- `T16`: exact-zero latency share `<= 0.20`.
- `T21`: policy execution coverage `>= 2/3` (timing, delay, amount-tail branches).
- `T22`: truth-rule collision guard `= 0` collisions.

### 3.2 Stretch realism gates (`B+`)
- `T3 >= 99.5%`, `T4 >= 99.5%`.
- `T5 >= 0.08`, `T6 >= 0.08`, `T7 >= 0.05`.
- `T9 <= 0.25`.
- `T11 >= 40`, `T13 <= 0.70`.
- `T14` in `[0.5s, 5s]`, `T15 > 45s`, `T16 <= 0.05`.
- `T17`: campaign depth with strong targeting differentiation.
- `T18`: campaign geo depth with differentiated corridor profile.
- `T19 <= 0.75` singleton-session share.
- `T20`: stronger uplift over baseline attachment richness.
- `T21 = 3/3`.

### 3.3 Cross-seed and statistical evidence gates
- Required seeds: `{42, 7, 101, 202}`.
- Critical metrics (`T1-T16`, `T21`, `T22`) must pass on every required seed.
- Cross-seed CV targets:
  - `B`: `<= 0.25`.
  - `B+`: `<= 0.15`.
- Statistical tests:
  - chi-square + Cramer's V where applicable,
  - JSD limits for distributional surfaces (`B<=0.08`, `B+<=0.05`),
  - KS/Wasserstein checks for delay-shape realism.

### 3.4 Runtime gates (binding)
- Baseline authority run (`c25a2675fbfbacd952b13bb594880e92`) measured:
  - `S1=1333.75s`, `S2=142.45s`, `S3=371.67s`, `S4=563.20s`, `S5=5.20s`.
- Runtime targets for closure:
  - `S1 target<=800s`, stretch `<=900s`.
  - `S2 target<=120s`, stretch `<=150s`.
  - `S3 target<=300s`, stretch `<=360s`.
  - `S4 target<=420s`, stretch `<=500s`.
  - `S5 target<=10s`, stretch `<=12s`.
- Segment lane targets (changed-state onward):
  - candidate lane (`single seed`) target `<=22 min`, stretch `<=25 min`,
  - witness lane (`2 seeds`) target `<=45 min`, stretch `<=50 min`,
  - certification lane (`4 seeds`) target `<=95 min`, stretch `<=105 min`.

## 4) Run protocol, retention, and pruning
- Active run root: `runs/fix-data-engine/segment_6B/`.
- `runs/local_full_run-5/` is read-only authority evidence and must not be modified.
- Keep-set only:
  - one pinned baseline authority run-id,
  - current candidate run-id,
  - last good run-id,
  - active witness/certification run-set.
- Prune law: remove superseded run-id folders before each expensive rerun.

### 4.1 Sequential rerun matrix (binding)
- If `S1` changes: rerun `S1 -> S2 -> S3 -> S4 -> S5`.
- If `S2` changes: rerun `S2 -> S3 -> S4 -> S5`.
- If `S3` changes: rerun `S3 -> S4 -> S5`.
- If `S4` changes: rerun `S4 -> S5`.
- If `S5` policy/gates only: rerun `S5`.
- No `S5` closure claim is valid if an upstream owner changed without required downstream rerun.

## 5) Performance-first phase stack (`POPT`)

### POPT.0 - Baseline lock and hotspot decomposition
Goal:
- pin runtime and dataset-shape baseline as optimization authority.

Definition of done:
- [x] authority baseline run-id pinned and immutable.
- [x] per-state elapsed table and hotspot share emitted.
- [x] lane decomposition recorded (`input`, `compute`, `validation`, `write`).
- [x] part-shape evidence emitted for heavy datasets (`S3/S4` outputs).
- [x] optimization budget and expected gain ladder pinned.

POPT.0 expanded closure:

#### POPT.0.1 - Authority baseline pin
Definition of done:
- [x] authority run-id pinned: `c25a2675fbfbacd952b13bb594880e92`.
- [x] pin file emitted: `runs/fix-data-engine/segment_6B/POPT0_BASELINE_RUN_ID.txt`.
- [x] baseline authority source locked to read-only root: `runs/local_full_run-5/`.

#### POPT.0.2 - State elapsed extraction
Definition of done:
- [x] state elapsed artifact emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt0_state_elapsed_c25a2675fbfbacd952b13bb594880e92.csv`.
- [x] baseline lock note emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt0_baseline_lock_c25a2675fbfbacd952b13bb594880e92.md`.
- [x] all owner states `S0..S5` recorded with `PASS` status in baseline lock.

#### POPT.0.3 - Hotspot + lane decomposition
Definition of done:
- [x] hotspot JSON emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt0_hotspot_map_c25a2675fbfbacd952b13bb594880e92.json`.
- [x] hotspot markdown emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt0_hotspot_map_c25a2675fbfbacd952b13bb594880e92.md`.
- [x] ranked hotspot order pinned as `S1 -> S4 -> S3`.
- [x] lane decomposition confirms compute-dominant profile in `S1` and `S4`.

#### POPT.0.4 - Part-shape and I/O pressure evidence
Definition of done:
- [x] part-shape artifact emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt0_part_shape_c25a2675fbfbacd952b13bb594880e92.json`.
- [x] small-file hotspots pinned with evidence:
  - `s4_event_labels_6B`, `s3_event_stream_with_fraud_6B`,
  - `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`.
- [x] file-count/avg-size evidence explicitly captured for S3/S4 writer lanes.

#### POPT.0.5 - Budget pin and handoff decision
Definition of done:
- [x] budget pin artifact emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt0_budget_pin_c25a2675fbfbacd952b13bb594880e92.json`.
- [x] baseline summary artifact emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt0_baseline_c25a2675fbfbacd952b13bb594880e92.json`.
- [x] candidate lane is `RED` versus budget; handoff decision is `GO_POPT.1`.
- [x] ordered optimization lane pinned: `S1 -> S4 -> S3 -> S2 -> S5`.

### POPT.1 - `S1` high-impact redesign
Goal:
- remove repeated join overhead and two-pass session consolidation bottleneck.

Definition of done:
- [x] pre-indexed gather path replaces repeated heavy joins for attachment.
- [x] session index consolidation reduced from two-pass temp-shard lane to deterministic single-pass/merge-light path.
- [x] `S1` runtime reduced by at least `40%` versus authority baseline.
- [x] deterministic outputs and contract schemas unchanged (semantic replay pass; byte-stable for arrival surface).

POPT.1 expanded execution plan:

#### POPT.1.1 - Design pin + pre-implementation invariants
Definition of done:
- [x] design note appended in `segment_6B.impl_actual.md` before code edits.
- [x] alternatives compared with explicit reject rationale:
  - retain join-chain + tune batch size only,
  - list-gather pre-index lane,
  - dictionary/UDF map lane.
- [x] invariants pinned:
  - no schema/dataset contract changes,
  - deterministic attachment/session IDs preserved,
  - rerun matrix remains `S1 -> S2 -> S3 -> S4 -> S5`.

#### POPT.1.2 - Attachment path refactor (`S1` owner lane)
Definition of done:
- [x] replace repeated `count-join + index-join` chain with pre-indexed gather:
  - party -> account list gather,
  - account -> instrument list gather,
  - party -> device list gather,
  - device -> ip list gather.
- [x] maintain existing attachment cardinality and null-safety guards.
- [x] preserve RNG accounting semantics (`rng_draws_entity_attach`, `rng_events_entity_attach`).

#### POPT.1.3 - Session consolidation refactor (`S1` owner lane)
Definition of done:
- [x] eliminate extra session-summary temp-shard pass for bucketization.
- [x] emit session summaries directly into deterministic bucket shards during batch loop.
- [x] retain bucket aggregation pass to final `s1_session_index_6B` with unchanged schema.

#### POPT.1.4 - Candidate witness execution + closure evidence
Definition of done:
- [x] fresh candidate run-id under `runs/fix-data-engine/segment_6B/<new_run_id>`.
- [x] execute sequential rerun `S1 -> S2 -> S3 -> S4 -> S5`.
- [x] emit runtime closure artifact with baseline-vs-candidate deltas for:
  - `S1 elapsed`,
  - lane elapsed (`S1..S5`),
  - session consolidation substep movement.
- [x] `S1` runtime reduction gate:
  - hard gate `>=40%` vs baseline `1333.75s`,
  - stretch gate `<=800s`.

#### POPT.1.5 - Determinism, structural parity, and handoff
Definition of done:
- [x] deterministic replay witness for `S1` on identical staged inputs (same run config, fresh run-id).
- [x] structural parity checks pinned for:
  - required output schemas,
  - non-empty constraints,
  - scenario partition continuity.
- [x] decision marker emitted:
  - `UNLOCK_POPT.2_CONTINUE` or `HOLD_POPT.1_REOPEN`.

POPT.1 closure evidence (authority):
- candidate run-id: `51496f8e24244f24a44077c57217b1ab`.
- replay witness run-id: `4ab118c87b614ee2b1384f17cd8a167b`.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt1_closure_51496f8e24244f24a44077c57217b1ab.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt1_closure_51496f8e24244f24a44077c57217b1ab.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt1_state_elapsed_51496f8e24244f24a44077c57217b1ab.csv`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt1_replay_witness_51496f8e24244f24a44077c57217b1ab_vs_4ab118c87b614ee2b1384f17cd8a167b.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt1_replay_witness_51496f8e24244f24a44077c57217b1ab_vs_4ab118c87b614ee2b1384f17cd8a167b.md`.
- phase decision: `UNLOCK_POPT.2_CONTINUE`.

### POPT.2 - `S4` label/timeline compute redesign
Goal:
- cut duplicate flow/event labelling work and lower timeline emission overhead.

Definition of done:
- [ ] flow-level truth/bank decisions computed once and safely propagated to event surface.
- [ ] case timeline emission rewritten to reduce repeated dataframe materialization.
- [ ] `S4` runtime reduced by at least `30%` versus authority baseline.
- [ ] `T1-T10` do not regress from pre-POPT witness baseline.

POPT.2 expanded execution plan:

#### POPT.2.1 - Design pin + invariants (before edits)
Definition of done:
- [x] implementation design note appended in `segment_6B.impl_actual.md` before code edits.
- [x] alternatives compared with explicit reject rationale:
  - keep duplicated flow/event labelling and only tune batch size,
  - full in-memory flow-label map for event join,
  - streamed flow-label propagation lane with bounded memory (selected).
- [x] invariants pinned:
  - no dataset/schema contract changes for `s4_*` outputs,
  - no changes to S4 policy semantics for truth/bank outcomes,
  - sequential rerun matrix remains `S4 -> S5` for this owner change.

#### POPT.2.2 - Event-labelling dedupe lane
Definition of done:
- [ ] remove duplicate truth/bank policy recomputation in event loop.
- [ ] propagate event labels from flow-level S4 outputs via deterministic flow-id linkage.
- [ ] preserve `s4_event_labels_6B` row-count parity with `s3_event_stream_with_fraud_6B`.
- [ ] preserve RNG trace/audit semantics and module coverage for S5 checks.

#### POPT.2.3 - Case-timeline emission optimization lane
Definition of done:
- [ ] replace repeated per-event-type filter/concat case assembly with vectorized long-form expansion.
- [ ] retain case ordering semantics (`CASE_OPENED`..`CASE_CLOSED`) and timestamp monotonic guards.
- [ ] preserve `s4_case_timeline_6B` schema and deterministic row cardinality logic.

#### POPT.2.4 - Fresh candidate witness run (`S4 -> S5`)
Definition of done:
- [x] fresh run-id created under `runs/fix-data-engine/segment_6B/<new_run_id>`.
- [x] upstream `S0..S3` surfaces staged from last-good POPT.1 run-id without mutating source run.
- [x] execute `S4` then `S5` only (per owner rerun matrix).
- [x] capture run-log elapsed evidence for `S4`, `S5`, and lane `S4..S5`.

#### POPT.2.5 - Closure scoring + handoff
Definition of done:
- [x] closure artifacts emitted:
  - `segment6b_popt2_closure_<run_id>.json`,
  - `segment6b_popt2_closure_<run_id>.md`,
  - `segment6b_popt2_state_elapsed_<run_id>.csv`.
- [ ] `S4` runtime gate:
  - hard gate `>=30%` reduction vs baseline `563.20s`,
  - target gate `<=420s` (stretch `<=500s`).
- [x] non-regression gate:
  - S5 required-check set remains PASS,
  - key S4 signature metrics (truth/bank/case share metrics used in POPT witness) do not materially regress.
- [x] phase decision emitted:
  - `UNLOCK_POPT.3_CONTINUE` or `HOLD_POPT.2_REOPEN`.

POPT.2 execution status (current authority):
- candidate execution run-ids:
  - `c32a6b3d20064b37b559902ad5738398` (`S4=642.91s`; staged blockers cleared for RNG, but hashgate staging was incomplete and `S5` failed),
  - `7f80bd1057dd4e47956d7b94ba03dc09` (`S4=641.33s`; `S5` PASS with required checks all PASS).
  - `f621ee01bdb3428f84f7c7c1afde8812` (`S4=570.62s`; bounded runtime knobs `batch_rows=500000`, `compression=snappy`; required checks all PASS; best current runtime witness).
  - `7b8cbd9c59644d3ea17eeb62b41f496a` (`S4=869.47s`; rejected row-group append writer redesign lane, rolled back immediately).
  - `0a997a2d51fb4b0a8def9f89aa2483f2` (`S4=685.38s`; rejected case-timestamp subset-compute lane, rolled back immediately).
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_7f80bd1057dd4e47956d7b94ba03dc09.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_7f80bd1057dd4e47956d7b94ba03dc09.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_state_elapsed_7f80bd1057dd4e47956d7b94ba03dc09.csv`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_f621ee01bdb3428f84f7c7c1afde8812.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_f621ee01bdb3428f84f7c7c1afde8812.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_state_elapsed_f621ee01bdb3428f84f7c7c1afde8812.csv`.
- phase decision: `HOLD_POPT.2_REOPEN` (runtime gate miss only).

### POPT.2R - `S4` runtime recovery lane (options 1/2/3)
Goal:
- clear the remaining `S4` runtime blocker using bounded-memory compute-path redesign without changing output contracts or policy semantics.

Definition of done:
- [x] option 1 implemented: partitioned flow-label carry lane replaces event-side full policy recomputation.
- [x] option 2 implemented: event lane rewritten to boolean-only projection from carried flow labels (string-heavy derivation removed from event path).
- [x] option 3 implemented: case timeline emission compacted to a single vectorized expansion lane (no repeated per-flag filter/concat scans).
- [x] fresh staged `S4 -> S5` witness run passes all required S5 checks.
- [ ] `S4` elapsed improves versus current POPT.2 witness (`570.62s`) with no realism regression in S5 warning metrics.
- [x] phase decision emitted: `UNLOCK_POPT.3_CONTINUE` or `HOLD_POPT.2_REOPEN`.

POPT.2R expanded execution plan:

#### POPT.2R.1 - Option 1: partitioned label-carry lane
Definition of done:
- [x] during flow processing, emit a compact carry surface per scenario with only:
  - `flow_id`, `is_fraud_truth`, `is_fraud_bank_view`, and deterministic shard key.
- [x] carry surface is partitioned into bounded shard count and stored under run-local temp only.
- [x] event lane consumes carry partitions by shard, avoiding full in-memory label maps.
- [x] fail-closed guard added: missing carried labels for any event row raises a state failure.

#### POPT.2R.2 - Option 2: event-lane boolean rewrite
Definition of done:
- [x] remove event-side campaign/truth/bank string derivation path.
- [x] event output built from carried booleans + event identity columns only.
- [x] row-count parity preserved against `s3_event_stream_with_fraud_6B`.
- [x] deterministic replay invariants preserved (`run_id`, `seed`, hashes, scenario partition continuity).

#### POPT.2R.3 - Option 3: case-lane compaction
Definition of done:
- [x] replace repeated conditional dataframe filters with a compact vectorized case-event expansion lane.
- [x] preserve event ordering (`CASE_OPENED -> ... -> CASE_CLOSED`) and timestamp monotonic intent.
- [x] preserve `s4_case_timeline_6B` schema and deterministic case cardinality logic.

#### POPT.2R.4 - Witness run, score, and closure decision
Definition of done:
- [x] stage fresh run-id from last-good prerequisites using `tools/stage_segment6b_popt2_lane.py`.
- [x] run `S4` then `S5` only on staged run-id.
- [x] score closure via `tools/score_segment6b_popt2_closure.py`.
- [ ] emit decision and retention/prune action for superseded candidate runs.

POPT.2R execution status (current authority):
- staged candidate run-id: `54192649481242ba8611d710d80fd0b7` (from source `f621ee01bdb3428f84f7c7c1afde8812`).
- lane results:
  - `S4=4070.62s` (hard regression vs baseline `563.20s` and current witness `570.62s`),
  - `S5=60.69s`, required checks all PASS,
  - warning metrics stable vs witness (no realism regression signal in S5 warnings).
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_54192649481242ba8611d710d80fd0b7.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_54192649481242ba8611d710d80fd0b7.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_state_elapsed_54192649481242ba8611d710d80fd0b7.csv`.
- decision: `HOLD_POPT.2_REOPEN`.
- disposition: option bundle rejected for runtime posture and code reverted to pre-POPT.2R implementation.

### POPT.2S - `S4` safer reopen lane (column-pruning + constant materialization)
Goal:
- reduce `S4` runtime with low-blast I/O+CPU optimization only, avoiding any new surfaces or join-path redesign.

Definition of done:
- [x] flow/event parquet batch reads drop redundant constant metadata columns from source scan.
- [x] output metadata columns (`seed`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`) are materialized from run/scenario constants with unchanged values.
- [x] no policy or label logic changes for truth/bank/case decisions.
- [x] fresh staged `S4 -> S5` witness executes and required S5 checks stay PASS.
- [x] closure scorer emitted and decision recorded (`UNLOCK_POPT.3_CONTINUE` or `HOLD_POPT.2_REOPEN`).

POPT.2S expanded execution plan:

#### POPT.2S.1 - Design pin and invariants
Definition of done:
- [x] implementation-map entry added before code edits (problem, alternatives, chosen lane).
- [x] invariants pinned:
  - no schema/path changes,
  - same row cardinalities and label semantics,
  - same RNG trace/audit posture.

#### POPT.2S.2 - Flow/event source column pruning
Definition of done:
- [x] flow scan uses only required computational columns (`flow_id`, `campaign_id`, `ts_utc`).
- [x] event scan uses only required computational columns (`flow_id`, `event_seq`, `campaign_id`).
- [x] run/scenario metadata added as literals during output projection.

#### POPT.2S.3 - Witness run and closure scoring
Definition of done:
- [x] stage fresh run-id from `f621ee01bdb3428f84f7c7c1afde8812`.
- [x] run `S4` then `S5`.
- [x] score with `tools/score_segment6b_popt2_closure.py`.
- [ ] update disposition:
  - keep lane if runtime improves with non-regression,
  - otherwise rollback immediately and keep current witness authority.

POPT.2S execution status (current authority):
- staged candidate run-id: `d9269a8788aa42c1957b886095118b63` (from source `f621ee01bdb3428f84f7c7c1afde8812`).
- lane results:
  - `S4=579.45s` (regression vs current witness `570.62s`),
  - `S5=8.23s`, required checks all PASS,
  - warning metrics stable vs witness.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_d9269a8788aa42c1957b886095118b63.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_d9269a8788aa42c1957b886095118b63.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_state_elapsed_d9269a8788aa42c1957b886095118b63.csv`.
- decision: `HOLD_POPT.2_REOPEN`.
- disposition: safer lane rejected for runtime posture; code rolled back to pre-POPT.2S implementation.

### POPT.2T - `S4` targeted reopen (campaign-map expression lane)
Goal:
- remove low-value per-batch join overhead in `S4` by using deterministic expression maps for campaign-to-truth derivation.

Definition of done:
- [x] flow/event lanes no longer join per batch to `campaign_map_df` for campaign-type derivation.
- [x] truth label/subtype derivation uses direct deterministic `campaign_id -> truth_*` expressions.
- [x] no policy semantic drift; output schemas and row cardinalities remain unchanged.
- [x] staged `S4 -> S5` witness run and closure scorer completed.
- [x] decision recorded with keep/rollback disposition.

POPT.2T expanded execution plan:

#### POPT.2T.1 - Design pin and invariants
Definition of done:
- [x] implementation-map entry appended before code edits.
- [x] invariants pinned:
  - no new temp surfaces,
  - no writer/path changes,
  - no label semantics drift.

#### POPT.2T.2 - Targeted S4 expression rewrite
Definition of done:
- [x] precompute `campaign_id -> truth_label` and `campaign_id -> truth_subtype` maps once per scenario.
- [x] replace per-batch campaign join with `_map_enum_expr("campaign_id", ...)` in flow and event loops.
- [x] compile checks pass.

#### POPT.2T.3 - Witness run and closure decision
Definition of done:
- [x] stage fresh run-id from `f621ee01bdb3428f84f7c7c1afde8812`.
- [x] run `S4` then `S5` with bounded knobs (`batch_rows=500000`, `compression=snappy`).
- [x] closure score emitted.
- [x] keep if runtime improves and checks stay PASS, else rollback immediately.

POPT.2T execution status (current authority):
- run `b2d2624c686e4fe7a602b564930c49b0`:
  - `S4=422.53s` but semantic drift detected (`flow fraud_true` collapsed and case volume collapsed),
  - rejected immediately as invalid witness for closure.
- corrective semantic patch applied to preserve `campaign_type=NONE` default behavior, reran as:
  - `e1206e898bdc4bc58db8402f2ffd72a5`,
  - `S4=620.19s`, `S5=7.86s`, required checks PASS,
  - closure decision `HOLD_POPT.2_REOPEN`.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_e1206e898bdc4bc58db8402f2ffd72a5.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_e1206e898bdc4bc58db8402f2ffd72a5.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_state_elapsed_e1206e898bdc4bc58db8402f2ffd72a5.csv`.
- disposition: targeted lane rejected for runtime posture; code rolled back to pre-POPT.2T implementation.

### POPT.2R2 - `S4` runtime recovery lane (bounded knobs only)
Goal:
- recover `S4` runtime through low-blast execution knob tuning only (`batch_rows`, parquet compression), with zero semantic/code-path edits.

Definition of done:
- [x] fresh staged run-id(s) created from current authority source run.
- [x] bounded candidate matrix executed:
  - `batch_rows` sweep (`500000`, `750000`, `1000000`),
  - compression sweep (`snappy`, `lz4`) with at most one alternative per batch setting.
- [x] each candidate runs `S4 -> S5` and passes required S5 checks.
- [x] closure scored with `tools/score_segment6b_popt2_closure.py`.
- [x] decision recorded:
  - keep only if runtime improves vs current witness (`S4=570.62s`) with non-regression,
  - else reject lane and retain current witness authority.

POPT.2R2 expanded execution plan:

#### POPT.2R2.1 - Lane pin and constraints
Definition of done:
- [x] implementation-map entry appended before execution.
- [x] constraints pinned:
  - no changes to `S4` policy logic, label logic, writer semantics, schema, or paths,
  - no new temp surfaces or carry datasets,
  - fail-closed on any required-check failure.

#### POPT.2R2.2 - Staged witness matrix execution
Definition of done:
- [x] stage at least one fresh run-id from `f621ee01bdb3428f84f7c7c1afde8812`.
- [x] execute bounded candidate matrix on staged run-id(s):
  - `ENGINE_6B_S4_BATCH_ROWS=<candidate>`,
  - `ENGINE_6B_S4_PARQUET_COMPRESSION=<candidate>`,
  - run `make segment6b-s4 segment6b-s5`.
- [x] capture elapsed and required-check posture per candidate.

#### POPT.2R2.3 - Closure scoring and disposition
Definition of done:
- [x] run closure scorer for best candidate.
- [x] record decision with explicit keep/rollback retention.
- [x] prune superseded run-id folders for rejected candidates.

POPT.2R2 execution status (current authority):
- source authority run-id: `f621ee01bdb3428f84f7c7c1afde8812` (`S4=570.62s`).
- staged candidates:
  - `6748b78b535e41a0838eb0ddb6f0e68f` (`batch_rows=500000`, `compression=snappy`) -> `S4=633.64s`, `S5=9.64s`, required checks PASS.
  - `723b5dcb53494ebca816b84cc9375ac4` (`batch_rows=750000`, `compression=snappy`) -> `S4=694.56s`, `S5=10.20s`, required checks PASS.
  - `a49febe17a574f4387de91b99fa5f3e1` (`batch_rows=1000000`, `compression=snappy`) -> `S4=653.20s`, `S5=9.59s`, required checks PASS.
  - `4e4cde10d4b14741badeb817e0362e63` (`batch_rows=750000`, `compression=lz4`) -> `S4=647.67s`, `S5=9.33s`, required checks PASS.
- non-regression posture:
  - parity counts stable across candidates,
  - warning metrics stable across candidates.
- best candidate by S4 elapsed: `6748b78b535e41a0838eb0ddb6f0e68f` at `633.64s` (still regressive vs authority witness).
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_6748b78b535e41a0838eb0ddb6f0e68f.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_723b5dcb53494ebca816b84cc9375ac4.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_a49febe17a574f4387de91b99fa5f3e1.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_4e4cde10d4b14741badeb817e0362e63.json`.
- pruned superseded run-id folders:
  - `723b5dcb53494ebca816b84cc9375ac4`,
  - `a49febe17a574f4387de91b99fa5f3e1`,
  - `4e4cde10d4b14741badeb817e0362e63`.
- decision: `HOLD_POPT.2_REOPEN`.
- disposition: reject `POPT.2R2` lane and retain `f621ee01bdb3428f84f7c7c1afde8812` as runtime authority.

### POPT.2U - `S4` algorithmic event-path reopen (flow-label reuse join)
Goal:
- remove duplicate per-event policy recomputation by deriving event labels from already-computed flow labels using a deterministic flow-id join.

Definition of done:
- [x] implementation notes pinned before edits with explicit invariants and fallback plan.
- [x] `S4` event path no longer recomputes truth/bank policy branches per event row.
- [x] event labels are built from:
  - event identity columns (`flow_id`, `event_seq`),
  - joined flow booleans (`is_fraud_truth`, `is_fraud_bank_view`),
  - run/scenario constants for metadata columns.
- [x] fail-closed guard present for missing flow-label coverage after join.
- [x] fresh staged `S4 -> S5` witness run scored.
- [x] decision recorded with keep/rollback.

POPT.2U expanded execution plan:

#### POPT.2U.1 - Design pin + invariants
Definition of done:
- [x] no policy semantic change for flow truth/bank labeling.
- [x] no schema/path contract change for `s4_event_labels_6B`.
- [x] fail-closed on any join coverage gap (`event rows` without matched flow labels).

#### POPT.2U.2 - Event-path algorithmic rewrite
Definition of done:
- [x] implement event-label build using one join lane against flow labels.
- [x] remove event-side recomputation of:
  - campaign-type mapping,
  - truth label/subtype derivation,
  - detect/dispute/chargeback probability branch logic.
- [x] keep deterministic ordering and idempotent publish behavior.

#### POPT.2U.3 - Witness + closure
Definition of done:
- [x] stage fresh run-id from `f621ee01bdb3428f84f7c7c1afde8812`.
- [x] run `S4 -> S5` with bounded knob posture.
- [x] score via `tools/score_segment6b_popt2_closure.py`.
- [x] retain only on runtime improvement with non-regression; else rollback and keep authority witness.

POPT.2U execution status (current authority):
- first staged run (blocked then fixed):
  - `56b20e1ef3374f05aa9addcb96fe588c` failed with `S4_EVENT_LABEL_JOIN_INPUT_MISSING`,
  - corrective patch switched event-join source from tmp parts to published flow output paths.
- scored witness matrix (all required checks PASS; parity and warn metrics stable):
  - `4b0214b471ce4089b7859391985a3957` (`500000`, `snappy`) -> `S4=411.66s`, reduction `26.91%`.
  - `ec5c8509cac1405f9403c086fe7799eb` (`500000`, `lz4`) -> `S4=413.61s`, reduction `26.56%`.
  - `97b2b72fbd2648fb852272b7dea50efd` (`750000`, `snappy`) -> `S4=403.78s`, reduction `28.31%` (best).
  - `3af2f6e7a77546c39cc1f19214b53bb0` (`1000000`, `snappy`) -> `S4=414.62s`, reduction `26.38%`.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_4b0214b471ce4089b7859391985a3957.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_ec5c8509cac1405f9403c086fe7799eb.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_97b2b72fbd2648fb852272b7dea50efd.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_3af2f6e7a77546c39cc1f19214b53bb0.json`.
- pruned superseded POPT.2U run-id folders:
  - `56b20e1ef3374f05aa9addcb96fe588c`,
  - `4b0214b471ce4089b7859391985a3957`,
  - `ec5c8509cac1405f9403c086fe7799eb`,
  - `3af2f6e7a77546c39cc1f19214b53bb0`.
- phase decision from scorer: `HOLD_POPT.2_REOPEN` (30% reduction gate miss).
- disposition:
  - keep `POPT.2U` code lane (material runtime gain with non-regression),
  - promote `97b2b72fbd2648fb852272b7dea50efd` as best current runtime authority witness for `POPT.2` reopen context.

### POPT.3 - Part-writer and I/O compaction lane
Goal:
- reduce write amplification and small-file overhead on S3/S4 heavy outputs.

Definition of done:
- [ ] bounded buffered part-writer strategy implemented for selected datasets.
- [ ] output part counts on primary hot datasets reduced by `>= 50%`.
- [ ] replay/idempotence invariants preserved.
- [ ] downstream readers validate unchanged schema and partition contract.

### POPT.4 - Runtime witness and freeze
Goal:
- certify optimization gains with deterministic evidence and freeze runtime posture.

Definition of done:
- [ ] candidate lane runtime meets target.
- [ ] witness lane (`2 seeds`) confirms runtime and non-regression.
- [ ] certification-lane feasibility confirmed against budget.
- [ ] optimization freeze markers written in build plan and impl notes.

## 6) Remediation phase stack

### P0 - Baseline realism lock and owner attribution
Goal:
- lock baseline `T1-T22`, route each failing gate to owner state, and pin veto criteria.

Definition of done:
- [ ] baseline gateboard emitted (`B` and `B+` status per gate).
- [ ] failing gates mapped to owner states (`S1/S2/S3/S4/S5`).
- [ ] promotion veto criteria pinned (critical fail-closed posture).
- [ ] baseline decision recorded (`HOLD_REMEDIATE` expected from D+ posture).

### P1 - Wave A.1 (`S4` truth/case + `S5` gate hardening)
Goal:
- restore truth validity and case timeline realism while preventing silent pass-through.

Definition of done:
- [ ] `S4` truth mapping uses ordered multi-condition rules without reduced-key collisions.
- [ ] collision assertion guard in code/tests for `T22`.
- [ ] delay models executed stochastically (not fixed minima only) and case timeline monotonicity enforced.
- [ ] `S5` critical realism checks become fail-closed and policy-driven.
- [ ] critical gates `T1-T10`, `T21`, `T22` show measurable movement toward `B`.

### P2 - Wave A.2 (`S2` amount/timing activation)
Goal:
- activate policy-faithful amount and timing behavior to close `T11-T16`.

Definition of done:
- [ ] `S2` timing policy offsets are executed (non-degenerate auth latency).
- [ ] amount model uses configured family/tail behavior, not fixed-point-only hash pick.
- [ ] `T11-T16` meet `B` thresholds on candidate seed.
- [ ] no regression on already closed Wave A.1 critical gates.

### P3 - Wave B (`S3` campaign depth)
Goal:
- deepen campaign realism and improve contextual stratification without breaking Wave A closure.

Definition of done:
- [ ] campaign multiplicity restored (bounded by policy).
- [ ] targeting depth improved across class/segment/geo/time signatures.
- [ ] `T17-T18` reach `B` thresholds and push toward `B+`.
- [ ] `T1-T16`, `T21`, `T22` remain passing.

### P4 - Wave C (`S1` context/session realism closure)
Goal:
- improve attachment/session realism and conditional context carry-through for durable `B+`.

Definition of done:
- [ ] context-carry fields required for downstream conditioning are preserved through 6B surfaces.
- [ ] singleton-session pressure reduced and attachment richness uplift evidenced.
- [ ] `T19-T20` meet `B` thresholds and move toward `B+`.
- [ ] cross-seed stability improves on critical and high gates.

### P5 - Integrated certification and freeze
Goal:
- complete cross-seed certification, publish final decision, and freeze segment 6B.

Definition of done:
- [ ] full `T1-T22` suite executed on required seeds.
- [ ] certification artifacts produced:
  - `validation_summary.json`,
  - `seed_comparison.csv`,
  - `regression_report.md`,
  - `gate_decision.json`.
- [ ] grade decision locked as one of:
  - `PASS_BPLUS_ROBUST`,
  - `PASS_B`,
  - `HOLD_REMEDIATE`.
- [ ] freeze note appended to build plan + implementation notes + logbook.

## 7) Decision policy and fail-closed rules
- If any critical gate fails in a wave, stop and reopen only owning lanes before any downstream phase.
- No threshold waivers without explicit documented policy re-baseline.
- Runtime regressions beyond budget are blockers; run bottleneck analysis before more tuning.
- Performance optimization cannot degrade determinism, schema contracts, or validation governance.
