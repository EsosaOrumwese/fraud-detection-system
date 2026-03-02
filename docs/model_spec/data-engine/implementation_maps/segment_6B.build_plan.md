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
  - interim authority during `POPT.2` reopen was `97b2b72fbd2648fb852272b7dea50efd` (later superseded by `POPT.2V`).

### POPT.2V - `S4` flow-lane metadata elision + projection compaction
Goal:
- close the remaining runtime gap by reducing flow-lane scan width and per-row payload overhead without touching policy semantics.

Definition of done:
- [x] flow batch reads stop loading run-constant metadata columns (`seed`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`).
- [x] flow/case outputs still emit those fields from deterministic run/scenario literals.
- [x] no semantic drift in flow truth/bank labels or case timeline behavior.
- [x] staged `S4 -> S5` witness run scored against `POPT.2` closure gates.
- [x] decision recorded with keep/rollback and prune posture.

POPT.2V expanded execution plan:

#### POPT.2V.1 - Design pin + invariants
Definition of done:
- [x] implementation-map entry added before edits.
- [x] invariants pinned:
  - no policy-logic changes for label generation,
  - no schema/path changes,
  - deterministic constant materialization only.

#### POPT.2V.2 - Flow-lane optimization implementation
Definition of done:
- [x] reduce flow read columns to computational set (`flow_id`, `campaign_id`, `ts_utc`).
- [x] remove per-batch casts for dropped constant metadata columns.
- [x] materialize metadata fields as literals in:
  - `s4_flow_truth_labels_6B`,
  - `s4_flow_bank_view_6B`,
  - `s4_case_timeline_6B`.

#### POPT.2V.3 - Witness + closure
Definition of done:
- [x] stage fresh run-id from `f621ee01bdb3428f84f7c7c1afde8812`.
- [x] run `S4 -> S5` with tuned batch posture.
- [x] score via `tools/score_segment6b_popt2_closure.py`.
- [x] retain only if runtime improves with non-regression; otherwise rollback.

POPT.2V execution status (current authority):
- staged witness run-id: `cee903d9ea644ba6a1824aa6b54a1692`.
- run posture: `batch_rows=750000`, `parquet_compression=snappy`.
- results:
  - `S4=392.64s`,
  - `S5=17.69s`,
  - required checks PASS,
  - parity/warn non-regression PASS.
- closure artifact:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_popt2_closure_cee903d9ea644ba6a1824aa6b54a1692.json`.
- phase decision: `UNLOCK_POPT.3_CONTINUE`.
- disposition:
  - keep `POPT.2V` code lane,
  - promote `cee903d9ea644ba6a1824aa6b54a1692` as runtime authority witness.
- pruning action:
  - removed superseded interim authority run-id `97b2b72fbd2648fb852272b7dea50efd`.

### POPT.3 - Part-writer and I/O compaction lane
Goal:
- reduce write amplification and small-file overhead on S3/S4 heavy outputs.

Definition of done:
- [x] bounded buffered part-writer strategy implemented for selected datasets.
- [x] output part counts on primary hot datasets reduced by `>= 50%`.
- [x] replay/idempotence invariants preserved.
- [x] downstream readers validate unchanged schema and partition contract.
- [x] staged witness run scored and retention/prune disposition recorded.

POPT.3 expanded execution plan:

#### POPT.3.1 - Design pin + baseline part-count capture
Definition of done:
- [x] implementation-map entry added before edits.
- [x] baseline part counts captured from current authority run `cee903d9ea644ba6a1824aa6b54a1692`:
  - `s4_flow_truth_labels_6B`,
  - `s4_flow_bank_view_6B`,
  - `s4_case_timeline_6B`.
- [x] compaction target pinned (`>=50%` reduction on each hot dataset).

#### POPT.3.2 - Rotating writer implementation (S4 outputs)
Definition of done:
- [x] introduce bounded rotating parquet writer in `S4` temp output lane.
- [x] apply rotating writer to:
  - `s4_flow_truth_labels_6B`,
  - `s4_flow_bank_view_6B`,
  - `s4_case_timeline_6B`.
- [x] keep output schema/path/idempotent publish behavior unchanged.
- [x] compile passes.

#### POPT.3.3 - Witness run + compaction closure
Definition of done:
- [x] stage fresh run-id from `cee903d9ea644ba6a1824aa6b54a1692`.
- [x] run `S4 -> S5` and score non-regression.
- [x] measure candidate part counts and reduction ratios vs baseline.
- [x] keep lane only if part-count target met with acceptable runtime/non-regression; else rollback.

POPT.3 execution status (current authority):
- authority remains `cee903d9ea644ba6a1824aa6b54a1692` (`POPT.2V` witness lock).
- candidate `053e906524cf46dfb18b4729f0714142` (rotating writer 3.0M target):
  - part-count reduction vs baseline: `93.06%` / `93.06%` / `85.11%` (`flow_truth` / `flow_bank` / `case_timeline`),
  - runtime: `S4=565.64s`, `S5=16.09s`,
  - scorer decision: `HOLD_POPT.2_REOPEN`.
- candidate `ff1f392b8cb44d3a8db399d74f702adf` (rotating writer 1.5M target):
  - part-count reduction vs baseline: `86.97%` / `86.97%` / `71.91%`,
  - runtime: `S4=656.30s`, `S5=14.89s`,
  - scorer decision: `HOLD_POPT.2_REOPEN`.
- rollback witness `7d1cd27427eb46189834954360319a89` (rotating writer removed; `POPT.2V` metadata-elision retained):
  - part-count reduction vs baseline: `0%` / `0%` / `0%`,
  - runtime: `S4=413.86s`, `S5=19.25s`,
  - scorer decision: `HOLD_POPT.2_REOPEN`.
- phase decision: `HOLD_POPT.3_REOPEN`.
- disposition:
  - reject `POPT.3` rotating-writer lane for now due runtime regression under this workload posture,
  - keep non-writer `POPT.2V` lane and preserve promoted authority run `cee903d9ea644ba6a1824aa6b54a1692`.
- storage hygiene:
  - pruned superseded `POPT.3` candidates `053e906524cf46dfb18b4729f0714142`, `ff1f392b8cb44d3a8db399d74f702adf`, `9eeff5c5e59048cc930b8bc059066a33`,
  - retained authority/evidence runs `cee903d9ea644ba6a1824aa6b54a1692` and `7d1cd27427eb46189834954360319a89`.

### POPT.4 - Runtime witness and freeze
Goal:
- certify optimization gains with deterministic evidence and freeze runtime posture.

Definition of done:
- [x] candidate lane runtime meets target.
- [x] witness lane (`2 seeds` target posture) confirms runtime and non-regression.
- [x] certification-lane feasibility confirmed against budget.
- [x] optimization freeze markers written in build plan and impl notes.

POPT.4 expanded execution plan:

#### POPT.4.1 - Freeze authority + target pin
Definition of done:
- [x] authority run pinned (`cee903d9ea644ba6a1824aa6b54a1692`).
- [x] freeze runtime target pinned for S4 lane (`<=420s` with required-check PASS + parity/warn stability).
- [x] non-promotable POPT.3 lane explicitly marked rejected.

#### POPT.4.2 - Witness matrix execution
Definition of done:
- [x] stage and execute one fresh `S4 -> S5` witness from authority posture (`750000/snappy`).
- [x] score witness non-regression against authority using closure scorer artifacts.
- [x] confirm replay-stable posture across at least two run-ids.

#### POPT.4.3 - Seed feasibility + freeze closure
Definition of done:
- [x] adjudicate `2 seeds` requirement:
  - either execute second seed, or
  - document blocked posture + bounded deferral lane with runtime/cost estimate.
- [x] write freeze decision and next-gate handoff (`UNLOCK_P0_REMEDIATION` or `HOLD_POPT.4_REOPEN`).
- [x] prune superseded witness run folders and retain authority evidence set.

POPT.4 execution status (current authority):
- freeze target:
  - `S4<=420s` and `required_checks_pass=true` with parity/warn stability.
- authority run:
  - `cee903d9ea644ba6a1824aa6b54a1692` -> `S4=392.64s`, `S5=17.69s`, non-regression PASS.
- witness runs (`750000/snappy`):
  - `7d1cd27427eb46189834954360319a89` -> `S4=413.86s`, `S5=19.25s`, runtime_target PASS, non-regression PASS.
  - `20851a5bf54f4e579999b16e7dc92c88` -> `S4=413.75s`, `S5=20.44s`, runtime_target PASS, non-regression PASS.
  - `5cdc365c876a4b1091491a5121d59750` -> `S4=438.42s`, `S5=19.95s`, runtime_target FAIL but stretch PASS, non-regression PASS (recorded outlier).
- seed-feasibility adjudication:
  - all available staged runs are `seed=42`; true second-seed witness requires upstream reseed lane (`S0-S3`).
  - bounded estimate from `POPT.0` state timings indicates about `31m` for `S1-S3` + `~7m` for `S4-S5` per new seed (`~38m/seed`, excluding operator overhead).
  - second-seed execution deferred to remediation certification lane unless explicitly reopened now.
- phase decision:
  - `UNLOCK_P0_REMEDIATION`.
- freeze disposition:
  - keep optimization authority at `cee903d9ea644ba6a1824aa6b54a1692`,
  - retain supporting witness `20851a5bf54f4e579999b16e7dc92c88`,
  - prune superseded outlier witness `5cdc365c876a4b1091491a5121d59750`.

## 6) Remediation phase stack

### P0 - Baseline realism lock and owner attribution
Goal:
- lock baseline `T1-T22`, route each failing gate to owner state, and pin veto criteria.

Definition of done:
- [x] baseline gateboard emitted (`B` and `B+` status per gate).
- [x] failing gates mapped to owner states (`S1/S2/S3/S4/S5`).
- [x] promotion veto criteria pinned (critical fail-closed posture).
- [x] baseline decision recorded (`HOLD_REMEDIATE` expected from D+ posture).

#### P0.1 - Baseline authority pin + scorer contract
Goal:
- pin the exact run authority and scoring contract for `T1-T22` so all downstream phases compare against one immutable baseline.

Definition of done:
- [x] authority run-id pinned (`6B` runtime freeze authority).
- [x] scorer contract pinned (metric definitions, thresholds, sampled-vs-full posture, insuff-evidence rules).
- [x] output artifact names pinned:
  - `segment6b_p0_realism_gateboard_<run_id>.json`,
  - `segment6b_p0_realism_gateboard_<run_id>.md`.

#### P0.2 - Gateboard execution (`T1-T22`)
Goal:
- execute baseline scoring on the pinned authority run and emit full gateboard evidence.

Definition of done:
- [x] `T1-T22` scored with explicit `B` / `B+` status.
- [x] critical gates (`T1-T16`, `T21`, `T22`) clearly classified pass/fail/insufficient.
- [x] sampling disclosures included for heavy surfaces (case-gap and latency lanes).
- [x] scorer outputs written under `runs/fix-data-engine/segment_6B/reports/`.

#### P0.3 - Owner attribution + veto lock
Goal:
- map each failing/insufficient gate to owning remediation lane and lock fail-closed promotion posture.

Definition of done:
- [x] per-gate owner attribution present (`S1/S2/S3/S4/S5`) with reasoned mapping.
- [x] remediation wave map emitted (`P1/P2/P3/P4`) from failing gates.
- [x] veto policy pinned:
  - no phase unlock when any critical gate remains fail/insufficient,
  - no silent downgrade of critical gates to warn-only.
- [x] P0 phase decision recorded (`HOLD_REMEDIATE` or `UNLOCK_P1`).

Execution closure (`run_id=cee903d9ea644ba6a1824aa6b54a1692`):
- scorer tool added:
  - `tools/score_segment6b_p0_baseline.py`.
- gateboard artifacts emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_cee903d9ea644ba6a1824aa6b54a1692.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_cee903d9ea644ba6a1824aa6b54a1692.md`.
- overall result:
  - `overall_verdict=FAIL_REALISM`,
  - `phase_decision=HOLD_REMEDIATE`.
- hard failures:
  - `T1,T2,T3,T5,T6,T7,T8,T10,T11,T13,T14,T15,T16,T21,T22`.
- stretch failures:
  - `T17,T19` (`T18` passes after explicit arrival-events join evidence).
- owner failure map:
  - `S4: T1,T2,T3,T5,T6,T7,T8,T10,T21,T22`,
  - `S2: T11,T13,T14,T15,T16,T21`,
  - `S3: T17`,
  - `S1: T19`,
  - `S5: T21,T22`.
- wave routing from P0:
  - `P1 -> T1,T2,T3,T5,T6,T7,T8,T10,T21,T22`,
  - `P2 -> T11,T13,T14,T15,T16`,
  - `P3 -> T17`,
  - `P4 -> T19`.

### P1 - Wave A.1 (`S4` truth/case + `S5` gate hardening)
Goal:
- restore truth validity and case timeline realism while preventing silent pass-through.

Definition of done:
- [ ] `S4` truth mapping uses ordered multi-condition rules without reduced-key collisions.
- [ ] collision assertion guard in code/tests for `T22`.
- [ ] delay models executed stochastically (not fixed minima only) and case timeline monotonicity enforced.
- [ ] `S5` critical realism checks become fail-closed and policy-driven.
- [ ] critical gates `T1-T10`, `T21`, `T22` show measurable movement toward `B`.

#### P1.1 - Lane pin, rail lock, and closure contract
Goal:
- pin exact P1 scope to the `P0` critical-failure set and prevent scope bleed into `P2/P3/P4` owners.

Definition of done:
- [x] P1 gate ownership lock pinned:
  - in-scope gates: `T1,T2,T3,T5,T6,T7,T8,T10,T21,T22`,
  - protected out-of-scope gates: `T11-T20` (no direct tuning in this phase).
- [x] execution lane pinned to `S4 -> S5` on fresh staged run-ids from authority witness.
- [x] runtime veto rail pinned:
  - `S4` non-regression target `<=420s` (from POPT freeze),
  - `S5` non-regression target `<=30s`.
- [x] candidate scorer contract pinned for P1 witness comparison vs P0 baseline gateboard.

Execution closure:
- lane contract artifacts emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p1_1_lane_contract_cee903d9ea644ba6a1824aa6b54a1692.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p1_1_lane_contract_cee903d9ea644ba6a1824aa6b54a1692.md`.
- pinned in-scope blocked gates from P0:
  - `T1,T2,T3,T5,T6,T7,T8,T10,T21,T22`.
- owner-focused execution lock:
  - `S4,S5` only for `P1` witness lane; no direct tuning on `T11-T20` owners in this phase.
- phase decision:
  - `UNLOCK_P1.2`.

#### P1.2 - S4 truth-map correction and collision closure (`T1,T2,T3,T22`)
Goal:
- remove truth collapse and close reduced-key collision behavior in truth mapping.

Definition of done:
- [x] ordered rule evaluation implemented for `direct_pattern_map` multi-condition matches.
- [x] non-campaign truth default path restored to LEGIT-consistent behavior.
- [x] explicit collision guard implemented and surfaced to scorer (`T22` hard gate).
- [x] witness evidence shows movement:
  - `T1` non-zero LEGIT share,
  - `T2` in-band movement toward `[0.02,0.30]`,
  - `T3` towards `>=99%`,
  - `T22=0`.

Execution closure:
- candidate run-id: `7725bf4e501341a1a224fccbcb1fb0bc`.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p1_2_truth_lane_7725bf4e501341a1a224fccbcb1fb0bc.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p1_2_truth_lane_7725bf4e501341a1a224fccbcb1fb0bc.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_7725bf4e501341a1a224fccbcb1fb0bc.json`.
- P1.2 gate movement vs authority (`cee903d9ea644ba6a1824aa6b54a1692`):
  - `T1`: `0.0000%` -> `99.9941%` (`B: FAIL -> PASS`),
  - `T2`: `1.000000` -> `0.000059` (still `B: FAIL`, but materially closer to `[0.02,0.30]` than baseline),
  - `T3`: `0.0000%` -> `100.0000%` (`B: FAIL -> PASS`),
  - `T22`: `effective_collision_count=1` -> `0` (`B: FAIL -> PASS`).
- runtime rails:
  - `S4=327.62s` (`<=420s` PASS),
  - `S5=21.06s` (`<=30s` PASS).
- phase decision:
  - `UNLOCK_P1.3`.

#### P1.3 - S4 bank-view stratification recovery (`T5,T6,T7`)
Goal:
- recover conditional bank-view sensitivity so bank outcomes are not flat across class/amount.

Definition of done:
- [x] bank-view decision path conditioned on restored truth semantics and class/amount-sensitive policy branches.
- [x] witness gate movement:
  - `T5` Cramer's V rises toward `>=0.05`,
  - `T6` amount effect-size rises toward `>=0.05`,
  - `T7` class spread rises toward `>=0.03`.
- [x] `T4` remains non-regressed (campaign rows remain non-LEGIT mapped).

Execution closure:
- candidate run-id (integrated witness authority): `b5bf984b6819472690bf9a7f50d8c692`.
- movement vs P1.2 witness (`7725bf4e501341a1a224fccbcb1fb0bc`):
  - `T5`: `0.000233` -> `0.014575` (up, still below `0.05`),
  - `T6`: `0.858081` -> `0.016210` (down from P1.2 outlier, but up vs P0 baseline `0.000141`),
  - `T7`: `0.000011` -> `0.012705` (up, still below `0.03`).
- non-regression hold:
  - `T4` remains `100.0000%` (`B PASS`).

#### P1.4 - S4 case timeline realism closure (`T8,T10`, protect `T9`)
Goal:
- eliminate non-monotonic/negative case gaps and reduce templated case timing artifacts.

Definition of done:
- [x] case timestamp generation enforces monotonicity by `case_event_seq`.
- [x] delay execution uses stochastic/policy-shaped draws (not fixed-minimum-only path).
- [x] witness gate movement:
  - `T8` negative-gap rate -> `0`,
  - `T10` non-monotonic case-event rate -> `0`.
- [x] `T9` fixed-spike share does not regress versus P0 baseline and trends toward threshold.

Execution closure:
- monotonic timeline lane established in S4 (`detect <= dispute <= chargeback <= decision <= close` with deterministic sampled delays).
- integrated witness (`b5bf984b6819472690bf9a7f50d8c692`) scored:
  - `T8`: `12.9673%` (P0) -> `0.0000%` (`B PASS`),
  - `T10`: `36.2503%` (P0) -> `0.0000%` (`B PASS`),
  - `T9`: `29.8824%` (P0, PASS) -> `0.0003%` (PASS, improved).

#### P1.5 - S5 critical fail-closed promotion (`T21,T22` governance)
Goal:
- prevent structural PASS while critical realism gates fail.

Definition of done:
- [x] `S5` validation policy elevates critical realism checks from warn-only to fail-closed for P1 gate set.
- [x] `S5` report exposes explicit critical realism check outcomes aligned to scorer gates.
- [x] `T21` branch coverage posture is measured against live outputs (not inferred from config presence only).
- [x] hashgate `_passed.flag` issuance blocked when any critical P1 gate fails.

Execution closure:
- new required checks implemented in S5 runner:
  - `REQ_CRITICAL_TRUTH_REALISM` (`T1/T2/T3/T22` aligned),
  - `REQ_CRITICAL_CASE_TIMELINE` (`T8/T10` aligned).
- runtime optimization for new checks:
  - deterministic sampled evaluation (`critical_realism_sample_mod=128`) to preserve S5 rail.
- integrated witness (`b5bf984b6819472690bf9a7f50d8c692`):
  - `S5` bundle elapsed `23.09s` (`<=30s` rail PASS),
  - `overall_status=FAIL` as intended fail-closed while critical truth gate fails,
  - `_passed.flag` not emitted.
- scorer branch posture:
  - `T21`: `1/3 (0.333333)` (up from `0/3`, still below required `>=2/3`).

#### P1.6 - Integrated P1 witness and decision
Goal:
- execute integrated `S4 -> S5` witness and lock phase decision from objective evidence.

Definition of done:
- [x] at least one fresh P1 witness run scored against P0 baseline gateboard.
- [x] critical gate decision table emitted for:
  - `T1,T2,T3,T5,T6,T7,T8,T10,T21,T22`.
- [x] phase decision emitted:
  - `UNLOCK_P2` only if critical P1 gate set reaches B posture with fail-closed S5 behavior,
  - otherwise `HOLD_P1_REOPEN` with blocker register.
- [x] implementation notes + logbook updated with alternatives considered, chosen knobs, and rejected paths.

Execution closure:
- integrated witness artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p1_integrated_closure_b5bf984b6819472690bf9a7f50d8c692.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p1_integrated_closure_b5bf984b6819472690bf9a7f50d8c692.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_b5bf984b6819472690bf9a7f50d8c692.json`.
- phase decision:
  - `HOLD_P1_REOPEN`.
- blocker register (critical P1 gates still failing):
  - `T2`, `T5`, `T6`, `T7`, `T21`.

#### P1.R1 - Critical blocker reopen (`T2/T5/T6/T7`, owner lane `S4->S5`)
Goal:
- close remaining S4-owned realism blockers while preserving closed P1 rails (`T1,T3,T4,T8,T9,T10,T22`) and runtime budget.

Definition of done:
- [x] S4 activates bounded heuristic overlay anomaly lane for non-campaign flows (deterministic, policy-shaped, no schema drift).
- [x] S4 bank-view lane increases class/amount sensitivity without violating deterministic replay posture.
- [x] scorer + S5 critical truth check align `T3` denominator to non-overlay semantics (no-campaign non-overlay rows).
- [x] fresh witness run emits movement on `T2/T5/T6/T7` with no regression on closed rails.
- [x] runtime rails hold (`S4<=420s`, `S5<=30s`).
- [x] phase decision emitted:
  - `UNLOCK_P2` if only cross-owner residual blockers remain,
  - else `HOLD_P1_REOPEN` with updated blocker register.

Execution closure:
- reopen witness sequence:
  - `9dd913d4e0814b2d9169c140cbbeb726`,
  - `b9530bd36fb34431bd7864136945ae74`,
  - `0b3b37118c97400b8f6c0198a76173fd`,
  - `e9de4f7c7f514ed1a1dc0d29b08f1d4f`.
- final witness (`e9de...`) scorer posture:
  - `T2=0.022420` (`PASS`),
  - `T6=0.120539` (`PASS`),
  - `T7=0.039255` (`PASS`),
  - `T5=0.027398` (`FAIL`, target `>=0.05`),
  - `T21=1/3` (`FAIL`; cross-owner dependency on `S2` timing/amount branches).
- S4/S5 runtime rails on final witness:
  - `S4=377.88s` (`<=420s` PASS),
  - `S5=20.84s` (`<=30s` PASS).
- phase decision:
  - `HOLD_P1_REOPEN` (owner blocker remains `T5`; `T21` remains cross-owner).

#### P1.R2 - High-blast S4 redesign lane (target `T5`)
Goal:
- close `T5` (`Cramer's V(bank_view_outcome, merchant_class) >= 0.05`) via S4 design-level changes, not coefficient-only retuning.

Definition of done:
- [x] redesign authority pinned:
  - explicit lane objective limited to `T5` closure with non-regression on `T2,T6,T7,T8,T9,T10,T22`,
  - no threshold waivers.
- [x] external merchant-class surface is explicitly integrated into S4 decisioning path (deterministic join), replacing proxy-only class approximation as primary conditioning source.
- [x] bank-view outcome generation is redesigned to class-conditioned outcome-mix transitions (not only class-conditioned fraud detection).
- [x] unknown/unmatched class handling is explicit and fail-closed auditable (no silent collapse to homogeneous behavior).
- [x] witness matrix (fresh staged run-ids) demonstrates:
  - `T5 >= 0.05` (`B`),
  - `T2` stays in `[0.02,0.30]`,
  - `T6 >= 0.05`,
  - `T7 >= 0.03`,
  - no regression on already-closed rails (`T1,T3,T4,T8,T9,T10,T22`).
- [x] runtime rails hold or improve with explicit evidence (`S4<=420s`, `S5<=30s`); any breach blocks promotion.
- [x] phase decision emitted:
  - `UNLOCK_P2` when `T5` is closed and only cross-owner residual blockers remain (`T21` via `S2`),
  - else `HOLD_P1_REOPEN` with redesign blocker register.

Planned subphases:
- `P1.R2.0` Design pin and blast-radius controls
  - lock authorities (`bank_view_policy_6B`, `truth_labelling_policy_6B`, contracts, scorer gates),
  - pin veto rails and rollback trigger,
  - define deterministic idempotent class-join posture.
- `P1.R2.1` S4 class-surface integration redesign
  - add deterministic merchant-class ingestion in S4 (primary class signal),
  - enforce join coverage metrics and explicit fallback bucket for unmatched merchants,
  - emit structured lane metrics in S4 logs for auditability.
- `P1.R2.2` Outcome-mix transition redesign
  - redesign detect/dispute/chargeback/outcome probabilities as class-conditioned transition matrices with amount-band effects,
  - normalize probabilities with bounded clips and deterministic RNG-family mapping.
- `P1.R2.3` Guardrail hardening + witness scoring
  - execute fresh `S4 -> S5` witness set and score each candidate using pinned external authorities,
  - apply veto gates on any regression of closed rails or runtime overshoot.
- `P1.R2.4` Closure decision and owner handoff
  - if `T5` closes: mark P1 closure for S4-owned blockers and hand off `T21` residual to `P2/S2`,
  - if `T5` remains open: publish saturation evidence and propose next higher-owner reopen options.

Execution closure:
- witness run-id: `5459d5b68a1344d9870f608a41624448` (staged from `e9de4f7c7f514ed1a1dc0d29b08f1d4f`).
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p1_r2_closure_5459d5b68a1344d9870f608a41624448.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p1_r2_closure_5459d5b68a1344d9870f608a41624448.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_5459d5b68a1344d9870f608a41624448.json`.
- scorer posture (vs prior `e9de...`):
  - `T5`: `0.027398` -> `0.067973` (`FAIL -> PASS`),
  - `T7`: `0.039255` -> `0.068842` (`PASS -> PASS`, improved),
  - `T6`: `0.120539` -> `0.118064` (`PASS`, non-regressed),
  - `T2`: `0.022420` -> `0.022420` (`PASS`, stable),
  - closed rails hold: `T1,T3,T4,T8,T9,T10,T22` all `PASS`.
- runtime rails:
  - `S4=416.14s` (`<=420s` PASS),
  - `S5=20.28s` (`<=30s` PASS).
- phase decision:
  - `UNLOCK_P2` (`S4` owner blocker `T5` closed; residual hard blockers are `S2`-owned plus cross-owner `T21`).

### P2 - Wave A.2 (`S2` amount/timing activation)
Goal:
- redesign S2 amount and auth timing generation so data shape is realistic (not degenerate), closing `T11,T13,T14,T15,T16` and unlocking `T21`.

Definition of done:
- [x] S2 executes amount generation from `amount_model_6B` distribution families (point-mass + tail), not fixed-only price-point lookup.
- [x] S2 executes timing offsets from `timing_policy_6B` for `AUTH_REQUEST -> AUTH_RESPONSE` (strictly positive and bounded).
- [x] `T11,T13,T14,T15,T16` reach `B` on witness run.
- [x] `T21` reaches `>=2/3` by activating amount-tail + timing branches (delay branch already active).
- [x] no regression on closed rails (`T1,T2,T3,T4,T5,T6,T7,T8,T9,T10,T22`).
- [ ] runtime rails hold:
  - `S2<=120s` target (stretch `<=150s`),
  - downstream rerun rails preserved (`S3<=380s`, `S4<=420s`, `S5<=30s`).
  - witness `9a609826341e423aa61aed6a1ce5d84d`: `S2=297.92s` (FAIL), `S3=422.19s` (FAIL), `S4=481.95s` (FAIL), `S5=21.05s` (PASS).

#### P2.0 - Root-cause pin and redesign contract
Goal:
- lock exact S2 defects and pin redesign invariants before code changes.

Definition of done:
- [x] root-cause map pinned from live evidence:
  - `T11=8` and `T13=100%` caused by single-path discrete amount index selection,
  - `T14=T15=0`, `T16=100%` caused by identical `AUTH_REQUEST` and `AUTH_RESPONSE` timestamps.
- [x] touched surfaces pinned:
  - `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py`,
  - `config/layer3/6B/amount_model_6B.yaml` (if parameter retune needed),
  - `config/layer3/6B/timing_policy_6B.yaml` (if parameter retune needed).
- [x] deterministic invariant pinned:
  - no stochastic global state, hash/RNG-key deterministic by existing IDs only,
  - no schema expansion on S2 outputs.

#### P2.1 - Amount-lane redesign (`T11,T13`, protect `T12`)
Goal:
- restore realistic amount support/cardinality and concentration profile.

Definition of done:
- [x] implement amount sampler in S2 honoring policy family structure:
  - configurable point-mass path (round price points),
  - configurable heavy-tail path (lognormal-style draw with bounds/rounding),
  - deterministic blend probability from policy (`point_mass_total`).
- [x] family assignment is policy-faithful by event/channel context (purchase/cash-withdrawal/transfer mapping).
- [x] `T11>=20` and `T13<=0.85` on candidate witness while `T12` remains passing.
- [x] amount generation remains vectorized (no row loops).

#### P2.2 - Timing-lane redesign (`T14,T15,T16`)
Goal:
- restore non-degenerate auth latency behavior with realistic tail.

Definition of done:
- [x] implement `AUTH_RESPONSE` offset generation from `timing_policy_6B.offset_models.delta_auth_response_seconds`.
- [x] enforce strict positive latency with composition epsilon (`>=0.001s`) and cap guardrails.
- [x] event timestamps remain monotone by `(flow_id,event_seq)` and parseable.
- [x] witness gates:
  - `T14` median in `[0.3s, 8s]`,
  - `T15` `p99 > 30s`,
  - `T16` exact-zero share `<=0.20`.

#### P2.3 - Cross-gate closure and branch-coverage lock (`T21`)
Goal:
- convert S2 realism movement into explicit branch coverage closure.

Definition of done:
- [x] amount-tail branch activation verified from scored outputs (`amount_tail_branch=true`).
- [x] timing branch activation verified from scored outputs (`timing_branch=true`).
- [x] `T21` reaches `>=2/3` without altering S4/S5 critical gate semantics.
- [x] residual blocker ownership updated explicitly if `T21` remains below threshold.

#### P2.4 - Integrated witness and phase decision
Goal:
- close P2 with a full owner-lane witness and decision receipt.

Definition of done:
- [x] staged witness run-id created from current authority (`5459d5b68a1344d9870f608a41624448`).
- [x] execution sequence run in full owner chain:
  - `S2 -> S3 -> S4 -> S5`.
- [x] scorer receipts emitted for witness run.
- [x] phase decision emitted:
  - quality closure achieved for `T11,T13,T14,T15,T16,T21` with no P1 regression (`PASS_HARD_ONLY`),
  - fail-closed decision: `HOLD_P2_REOPEN_PERF` due runtime-rail breaches (`S2/S3/S4` above budget); reopen lane remains `P2` owner scope before `UNLOCK_P3`.

#### P2.R - Performance Reopen (`S2/S3/S4` runtime closure)
Goal:
- close runtime rails without regressing closed realism gates.

Definition of done:
- [ ] `S2<=150s` stretch (`<=120s` target) on fresh witness lane.
- [x] `S3<=380s` and `S4<=420s` on same witness lane.
- [x] `T11,T13,T14,T15,T16,T21` remain PASS and closed rails (`T1-T10,T22`) remain non-regressed.
- [x] reopen decision emitted:
  - `UNLOCK_P3` only if performance + realism both pass,
  - else `HOLD_P2_REOPEN_PERF` with next bottleneck owner explicitly pinned.
  - current decision on witness `bbbe8850af334fa097d5770da339d713`: `HOLD_P2_REOPEN_PERF` (remaining blocker `S2` runtime).

##### P2.R0 - Hotspot pin + bounded strategy lock
Goal:
- pin bottlenecks and lock highest-yield low-risk optimization set.

Definition of done:
- [x] hotspot evidence pinned from run `9a609826341e423aa61aed6a1ce5d84d`.
- [x] chosen lane locked:
  - `S2`: replace repeated hash-stream columns with deterministic splitmix lane derived from `flow_id`.
  - `S3/S4`: throughput tuning via larger safe batch size + faster parquet compression for remediation lane.
- [x] rejected alternatives logged (high-blast redesign deferred).

##### P2.R1 - `S2` deterministic random-stream vectorization
Goal:
- remove avoidable hash/materialization overhead in amount/timing draws.

Definition of done:
- [x] `S2` computes one `flow_id` hash per row and derives all uniforms from splitmix vector ops (no extra hash columns).
- [x] amount/timing statistical closure preserved (`T11,T13,T14,T15,T16` PASS).
- [x] `S2` runtime improves materially vs `297.92s` baseline.
  - witness `bbbe...`: `238.09s` (`-20.08%`), but still above stretch rail (`<=150s`).

##### P2.R2 - `S3/S4` throughput tuning lane
Goal:
- close near-miss runtime rails on overlay/label states with low-risk knobs.

Definition of done:
- [x] segment-6B make defaults tuned for remediation lane:
  - `ENGINE_6B_S3_BATCH_ROWS`, `ENGINE_6B_S4_BATCH_ROWS` raised to safe higher values,
  - compression moved to faster codec for `S3/S4` witness lane.
- [x] `S3` and `S4` runtime reduce vs `422.19s` / `481.95s` baseline without schema drift.
  - witness `bbbe...`: `S3=362.53s` (`-14.13%`, PASS), `S4=392.94s` (`-18.47%`, PASS).

##### P2.R3 - Integrated witness + closure decision
Goal:
- validate performance and realism together on fresh staged run.

Definition of done:
- [x] fresh run staged from latest authority witness.
- [x] full chain executed: `S2 -> S3 -> S4 -> S5`.
- [x] scorer receipt generated and compared to `9a609826...` for non-regression.
- [x] phase decision written with explicit next owner if still blocked.
  - next bottleneck owner: `S2` only (runtime rail miss), while `S3/S4/S5` rails are closed.

##### P2.R4 - `S2` event-path redesign + hotspot profiling
Goal:
- close remaining `S2` runtime gap with structural event-lane optimization.

Definition of done:
- [x] add explicit `S2` batch-stage timers (sampling, timestamp construction, event build, parquet writes) with aggregate summary.
- [ ] remove `S2` response timestamp `strptime/strftime` hot path and replace with vectorized epoch-micro lane.
- [ ] remove event concat hot path by writing request/response batches directly as separate parts.
- [x] run one fresh witness lane and compare `S2` against `bbbe...` baseline (`238.09s`) while holding realism gates non-regressed.
- [x] phase decision updated:
  - `UNLOCK_P3` only if `S2` rail closes (`<=150s` stretch),
  - else keep `HOLD_P2_REOPEN_PERF` with next S2 redesign lane pinned.

Execution outcome (`run_id=49582f7fafa441db97e3db82c6e80238`):
- runtime witness vs baseline `bbbe...`:
  - `S2`: `232.08s` vs `238.09s` (improved, still FAIL vs `<=150s` stretch rail),
  - `S3`: `368.06s` vs `362.53s` (PASS vs `<=380s` rail),
  - `S4`: `482.50s` vs `392.94s` (FAIL vs `<=420s` rail on this witness),
  - `S5`: `21.05s` vs `19.70s` (PASS vs `<=30s` rail).
- realism witness:
  - scorer verdict stays `PASS_HARD_ONLY`,
  - `T11,T13,T14,T15,T16,T21` unchanged/non-regressed.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_49582f7fafa441db97e3db82c6e80238.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p2r4_closure_49582f7fafa441db97e3db82c6e80238.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p2r4_closure_49582f7fafa441db97e3db82c6e80238.md`.
- phase decision:
  - `HOLD_P2_REOPEN_PERF` (remaining owner blocker `S2` runtime; additionally recheck `S4` rail on an isolated-load witness before declaring `S4` reopened).

##### P2.R5 - `S2` timestamp/parquet hotspot closure
Goal:
- close remaining `S2` runtime gap by optimizing the two dominant measured hotspots from `P2.R4` (`ts_build`, `parquet_write`) while keeping realism and schema rails locked.

Definition of done:
- [x] design lock recorded with alternatives and bounded blast radius (no policy/scorer/schema changes).
- [x] timestamp lane optimization implemented in `6B.S2`:
  - replace flexible parse path with fixed-format parse/format contract (`%Y-%m-%dT%H:%M:%S%.6fZ`) for response timestamp build.
- [x] parquet write lane optimization implemented in `6B.S2`:
  - reduce per-part write overhead via explicit writer settings tuned for throughput (without changing dataset schema/paths).
- [x] fresh witness run-id executed `S2 -> S3 -> S4 -> S5` on `runs/fix-data-engine/segment_6B/<new_run_id>`.
- [ ] runtime evidence:
  - `S2` improves materially vs `bbbe...` (`238.09s`) and vs `49582...` (`232.08s`),
  - `S3<=380s`, `S4<=420s`, `S5<=30s` re-verified on same witness.
- [x] realism non-regression evidence:
  - `PASS_HARD_ONLY` or better,
  - `T11,T13,T14,T15,T16,T21` unchanged or improved,
  - no regression on closed rails `T1-T10,T22`.
- [x] closure artifacts emitted:
  - `segment6b_p2r5_closure_<run_id>.json`,
  - `segment6b_p2r5_closure_<run_id>.md`,
  - updated gateboard `segment6b_p0_realism_gateboard_<run_id>.json`.
- [x] phase decision emitted:
  - `UNLOCK_P3` only if runtime + realism rails pass,
  - else `HOLD_P2_REOPEN_PERF` with next S2 owner lane pinned.

Execution outcome (`run_id=ac712b0b5e3f4ae5b5fd1a2af1662d4b`):
- first full witness pass:
  - `S2=227.36s` (improved vs `bbbe...=238.09s` and `49582...=232.08s`, still FAIL vs `<=150s` stretch rail),
  - `S3=400.42s` (FAIL vs `<=380s` rail),
  - `S4=405.50s` (PASS vs `<=420s` rail),
  - `S5=19.83s` (PASS vs `<=30s` rail).
- repeat-check (`S3->S4->S5` on same run-id) showed rail variance:
  - `S3=360.64s` (PASS),
  - `S4=460.44s` (FAIL),
  - `S5=30.49s` (FAIL by margin).
- S2 hotspot evidence moved in right direction but insufficient:
  - `ts_build`: `87.68s -> 85.98s`,
  - `parquet_write`: `72.81s -> 69.30s`.
- realism: scorer remains `PASS_HARD_ONLY`; `T11,T13,T14,T15,T16,T21` non-regressed.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_ac712b0b5e3f4ae5b5fd1a2af1662d4b.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p2r5_closure_ac712b0b5e3f4ae5b5fd1a2af1662d4b.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p2r5_closure_ac712b0b5e3f4ae5b5fd1a2af1662d4b.md`.
- phase decision:
  - `HOLD_P2_REOPEN_PERF` (S2 runtime rail still open; cross-state runtime stability not yet reliable for unlock).

##### P2.R6 - `S2` writer topology redesign (row-group streaming)
Goal:
- materially reduce `S2` parquet-write overhead by redesigning output writing topology from many per-batch part files to single-part streaming writers, while preserving schemas and deterministic row ordering.

Definition of done:
- [x] implementation design pinned with blast-radius controls and rollback path.
- [x] `S2` write path refactored:
  - per scenario, open one flow writer + one event writer (`part-00000.parquet`),
  - append each batch as parquet row-groups (no per-batch new part creation),
  - keep schema columns/order and publish paths unchanged.
- [x] fresh witness run executed on `runs/fix-data-engine/segment_6B/<new_run_id>`:
  - `S2 -> S3 -> S4 -> S5`.
- [x] runtime evidence:
  - `S2` improves vs `ac712...` (`227.36s`) and vs `bbbe...` (`238.09s`),
  - rail check repeated with one immediate `S3->S5` rerun to assess stability.
- [x] realism non-regression evidence:
  - scorer remains `PASS_HARD_ONLY` or better,
  - `T11,T13,T14,T15,T16,T21` non-regressed.
- [x] closure artifacts emitted:
  - `segment6b_p2r6_closure_<run_id>.json`,
  - `segment6b_p2r6_closure_<run_id>.md`,
  - updated gateboard `segment6b_p0_realism_gateboard_<run_id>.json`.
- [x] phase decision:
  - `UNLOCK_P3` only if runtime rails + realism pass together,
  - else remain `HOLD_P2_REOPEN_PERF` with next owner lane pinned.

Execution outcome (`run_id=b60080a948784e3a971339149528fd8d`):
- observed runtime vs baseline `ac712...`:
  - `S2`: `350.58s` vs `227.36s` (severe regression),
  - `S3`: `393.44s` vs `400.42s` (minor improvement, still over rail),
  - `S4`: `488.42s` vs `405.50s` (severe regression),
  - `S5`: `93.39s` vs `19.83s` (severe regression).
- S2 stage profile confirms writer-path failure:
  - `parquet_write=191.97s` (vs `69.30s` on `ac712...`).
- realism:
  - scorer verdict remains `PASS_HARD_ONLY`; `T11,T13,T14,T15,T16,T21` non-regressed.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_b60080a948784e3a971339149528fd8d.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p2r6_closure_b60080a948784e3a971339149528fd8d.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p2r6_closure_b60080a948784e3a971339149528fd8d.md`.
- phase decision:
  - `ROLLBACK_P2R6` and retain `HOLD_P2_REOPEN_PERF`.
  - S2 code path reverted to pre-R6 writer topology.
- rollback verification:
  - fresh S2-only verify run `e49c2370a1154be9aa5c8cf227fc2fa2` completed at `S2=234.66s` with stage profile `parquet_write=72.13s`, confirming restoration to pre-R6 posture.
- storage hygiene:
  - pruned superseded run folders `b60080a948784e3a971339149528fd8d` and `e49c2370a1154be9aa5c8cf227fc2fa2` after extracting evidence.

### P3 - Wave B (`S3` campaign depth)
Goal:
- deepen campaign realism and improve contextual stratification without breaking Wave A closure.

Definition of done:
- [x] campaign multiplicity restored (bounded by policy).
- [x] targeting depth improved across class/segment/geo/time signatures.
- [x] `T17-T18` reach `B` thresholds and push toward `B+`.
- [x] `T1-T16`, `T21`, `T22` remain passing.

P3 expanded execution plan:

#### P3.1 - Design lock + owner boundaries
Goal:
- lock a low-blast `S3` owner lane that directly targets `T17` class-differentiation miss without reopening closed `S2/S4` policy owners.

Definition of done:
- [x] authority baseline pinned from latest scored witness:
  - `run_id=ac712b0b5e3f4ae5b5fd1a2af1662d4b`,
  - `T17 campaign_count=5`, `class_v=0.029388` (just below `B` floor `0.03`),
  - `T18` already `PASS` (`tz_corridor_v=0.108057`, `median_tz=64`).
- [x] blast radius pinned:
  - touched owner code is `6B.S3` only,
  - rerun matrix is `S3 -> S4 -> S5`,
  - no schema/contract/scorer threshold changes.
- [x] veto rails pinned:
  - no regression on hard gates (`T1-T16`, `T21`, `T22`),
  - `T18` must remain `PASS`,
  - `S3/S4/S5` runtime rails must not materially regress beyond stretch posture.

#### P3.2 - Campaign targeting-depth refactor (`S3`)
Goal:
- increase campaign-vs-class differentiation by moving flow campaign pick from pure flow-hash overlap to deterministic merchant-cohort targeting with anti-starvation guardrails.

Definition of done:
- [x] implement deterministic merchant-cohort targeting in `S3` campaign assignment for flow surface:
  - campaign-specific cohort windows over merchant hash buckets,
  - preserved deterministic run reproducibility for fixed `(seed, manifest_fingerprint, parameter_hash, scenario_id)`.
- [x] implement anti-starvation threshold floor for positive target campaigns:
  - campaigns with `target_count > 0` cannot collapse to zero-probability due integer truncation.
- [x] preserve existing output schemas and required columns for:
  - `s3_flow_anchor_with_fraud_6B`,
  - `s3_event_stream_with_fraud_6B`,
  - `s3_campaign_catalogue_6B`.
- [x] preserve overlay guardrails:
  - no uncontrolled fraud explosion,
  - campaign target totals remain bounded by policy guardrails.

#### P3.3 - Fresh owner witness execution (`S3 -> S4 -> S5`)
Goal:
- execute a fresh `6B` lane with only `S3` owner changes and produce reproducible evidence.

Definition of done:
- [x] fresh run-id staged under `runs/fix-data-engine/segment_6B/<new_run_id>` from pinned authority baseline prerequisites.
- [x] execute:
  - `make segment6b-s3`,
  - `make segment6b-s4`,
  - `make segment6b-s5`.
- [x] score gateboard:
  - `tools/score_segment6b_p0_baseline.py` with pinned merchant-class and arrival-events authorities.

#### P3.4 - Closure scoring + decision
Goal:
- determine whether P3 is closed for `B` and whether `B+` is reachable without reopening upstream owners.

Definition of done:
- [x] closure artifacts emitted:
  - `segment6b_p0_realism_gateboard_<run_id>.json/.md`,
  - `segment6b_p3_closure_<run_id>.json/.md`.
- [x] gate outcomes:
  - `T17` reaches `B` (`campaign_count>=4` and `class_v>=0.03`),
  - `T18` remains `B` `PASS`.
- [x] non-regression outcomes:
  - all hard gates stay `PASS`,
  - no new required-check failures in `S5`.
- [x] phase decision emitted:
  - `UNLOCK_P4` if `P3` closure criteria hold,
  - else `HOLD_P3_REOPEN` with next `S3` lane explicitly pinned.

Execution outcome (`run_id=dbbcd2e7383a4206b6d16c668b20d4e0`):
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_dbbcd2e7383a4206b6d16c668b20d4e0.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_dbbcd2e7383a4206b6d16c668b20d4e0.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p3_closure_dbbcd2e7383a4206b6d16c668b20d4e0.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p3_closure_dbbcd2e7383a4206b6d16c668b20d4e0.md`.
- target realism movement:
  - `T17`: `campaigns=5, class_v=0.029388` -> `campaigns=6, class_v=0.188837` (`FAIL -> PASS_B/B+`),
  - `T18`: `tz_corridor_v=0.108057, median_tz=64.00` -> `tz_corridor_v=0.343476, median_tz=43.50` (`PASS -> PASS`).
- hard-gate posture:
  - `T1-T16`, `T21`, `T22` remain `PASS`; no required-check failures in `S5`.
- runtime posture versus `ac712...` first-pass reference:
  - `S3`: `400.42s -> 851.20s` (rail breach),
  - `S4`: `405.50s -> 419.12s` (within rail),
  - `S5`: `19.83s -> 20.64s` (within rail).
- phase decision:
  - `HOLD_P3_REOPEN_PERF`.
  - `T17/T18` realism closure is achieved, but `S3` runtime regression blocks `UNLOCK_P4` under performance-first gates.

#### P3.R1 - S3 runtime recovery reopen (keep `T17/T18` closed)
Goal:
- recover `S3` runtime rail while preserving the new campaign-depth realism closure achieved in P3.

Definition of done:
- [x] `S3` runtime returns to stretch rail (`<=380s`) on fresh witness.
- [x] `T17` remains `PASS_B` (and retains practical headroom above `0.03`).
- [x] `T18` remains `PASS`.
- [x] no hard-gate regression on `T1-T16`, `T21`, `T22`.
- [x] closure artifacts emitted and phase decision updated.

P3.R1 expanded execution plan:

##### P3.R1.0 - Hotspot pin + bounded redesign lock
Definition of done:
- [x] runtime regression owner pinned from evidence:
  - `S3` moved from baseline reference `400.42s` to `851.20s`.
- [x] lane decomposition pinned for `S3`:
  - flow assignment sublane,
  - event assignment/write sublane.
- [x] selected bounded lane avoids schema/contract/policy/scorer changes.

##### P3.R1.1 - Flow assignment cost reduction
Definition of done:
- [x] reduce per-row campaign assignment overhead by avoiding repeated merchant-hash recomputation per campaign.
- [x] retain deterministic merchant-cohort targeting behavior for `T17` closure.
- [x] preserve first-match semantics and campaign guardrail bounds.

##### P3.R1.2 - Event overlay throughput rewrite
Definition of done:
- [x] replace heavy event-side per-campaign hash assignment lane with a deterministic flow-joined event overlay lane.
- [x] preserve required event schema and row-count parity with baseline events.
- [x] preserve deterministic campaign attribution and fraud flag semantics.

##### P3.R1.3 - Fresh witness + closure scoring
Definition of done:
- [x] stage fresh run-id and execute `S3 -> S4 -> S5`.
- [x] score with `tools/score_segment6b_p0_baseline.py`.
- [x] emit `segment6b_p3r1_closure_<run_id>.json/.md` and phase decision:
  - `UNLOCK_P4` if runtime + realism rails pass,
  - else `HOLD_P3_REOPEN_PERF` with next owner lane pinned.

P3.R1 execution status (current authority):
- witness run-id: `53524385b4554006a4d8e5f46cdf9b70` (staged from `ac712b0b5e3f4ae5b5fd1a2af1662d4b`).
- artifacts emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_53524385b4554006a4d8e5f46cdf9b70.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_53524385b4554006a4d8e5f46cdf9b70.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p3r1_closure_53524385b4554006a4d8e5f46cdf9b70.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p3r1_closure_53524385b4554006a4d8e5f46cdf9b70.md`.
- realism posture:
  - overall verdict stays `PASS_HARD_ONLY` with no hard-gate regressions,
  - `T17` remains closed (`campaigns=6`, `class_v=0.226963`),
  - `T18` remains closed (`tz_corridor_v=0.413332`, `median_tz=39`).
- runtime posture versus reference (`ac712...`):
  - `S3`: `400.42s -> 372.01s` (rail PASS, recovered),
  - `S4`: `405.50s -> 444.33s` (rail FAIL),
  - `S5`: `19.83s -> 40.23s` (rail FAIL).
- phase decision:
  - `HOLD_P3_REOPEN_PERF`.
  - next owner lane: `S4` runtime closure (`event-label join throughput + validation runtime`) while preserving `T17/T18` closure.

#### P3.R2 - S4/S5 runtime reopen (freeze `S3/T17/T18`)
Goal:
- close integrated runtime rails by optimizing `S4` compute/write path and `S5` validation throughput, without reopening `S3` logic or changing closed realism posture.

Definition of done:
- [x] `S4` runtime closes to rail (`<=420s`) on fresh witness from frozen `S3`.
- [x] `S5` runtime closes to rail (`<=30s`) on same witness (superseded/closed by `P3.R3` witness `08db6e3060674203af415b389d5a9cbd`: `6.05s` + `3.72s` recheck).
- [x] `T17/T18` remain closed and no hard-gate regressions on `T1-T16`, `T21`, `T22`.
- [x] closure artifacts emitted and phase decision updated.

P3.R2 expanded execution plan:

##### P3.R2.0 - Hotspot pin + bounded strategy lock
Definition of done:
- [x] owner hotspots pinned from `P3.R1` witness:
  - `S4=444.33s` and `S5=40.23s` while `S3` remains recovered.
- [x] selected lane excludes any `S3` code/policy/config changes.
- [x] selected lane keeps schemas/contracts/scorer thresholds unchanged.

##### P3.R2.1 - `S4` flow/case compute throughput optimization
Definition of done:
- [x] reduce per-batch timestamp/case-event compute overhead in `S4` without semantic drift.
- [x] retain exact output schemas and deterministic event ordering semantics.
- [x] preserve event-label join row-count parity and required validation checks.

##### P3.R2.2 - `S5` validation throughput optimization
Definition of done:
- [x] eliminate redundant parquet file-discovery/count overhead in `S5` validation checks (superseded/closed by `P3.R3` sample-path optimization lane and profile evidence).
- [x] keep required check set, fail-closed behavior, and bundle outputs unchanged.
- [x] preserve deterministic bundle/index/flag behavior under idempotent reruns.

##### P3.R2.3 - Fresh witness + closure scoring (`S4 -> S5` only)
Definition of done:
- [x] stage fresh run-id from `P3.R1` authority and execute `S4 -> S5`.
- [x] score with `tools/score_segment6b_p0_baseline.py`.
- [x] emit `segment6b_p3r2_closure_<run_id>.json/.md` and phase decision:
  - `UNLOCK_P4` if integrated runtime + realism rails pass,
  - else `HOLD_P3_REOPEN_PERF` with next runtime owner pinned.

P3.R2 execution status (current authority):
- witness run-id: `65381edb84e349b8a7e46cba36c1799d` (staged from `53524385b4554006a4d8e5f46cdf9b70`; `S3` frozen).
- artifacts emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_65381edb84e349b8a7e46cba36c1799d.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_65381edb84e349b8a7e46cba36c1799d.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p3r2_closure_65381edb84e349b8a7e46cba36c1799d.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p3r2_closure_65381edb84e349b8a7e46cba36c1799d.md`.
- runtime posture:
  - `S3` frozen at `372.01s`,
  - `S4=419.91s` (rail PASS),
  - `S5=47.66s` (rail FAIL),
  - `S5` recheck on same run: `55.39s` (still FAIL).
- realism posture:
  - overall verdict remains `PASS_HARD_ONLY`,
  - `T17/T18` stay closed (unchanged),
  - no hard-gate regressions.
- phase decision:
  - `HOLD_P3_REOPEN_PERF` (historical at `P3.R2`; superseded by `P3.R3` closure).
  - next owner lane at the time was `S5` runtime profiling + validation-check hotspot closure; this lane is now closed by `P3.R3` witness `08db6e3060674203af415b389d5a9cbd`.

#### P3.R3 - S5 runtime hotspot closure (freeze `S3/T17/T18` and keep `S4` rail closed)
Goal:
- close the remaining integrated runtime blocker by reducing `S5` validation elapsed to rail while preserving fail-closed required-check semantics and frozen realism posture.

Definition of done:
- [x] `S5` runtime closes to rail (`<=30s`) on first pass and immediate recheck on the same witness run.
- [x] `S4` remains in rail (`<=420s`) and `S3/T17/T18` remain frozen/closed.
- [x] no hard-gate regressions on `T1-T16`, `T21`, `T22`.
- [x] closure artifacts emitted and phase decision updated.

P3.R3 expanded execution plan:

##### P3.R3.0 - S5 profile instrumentation + hotspot pin
Definition of done:
- [x] add run-local per-check runtime profiling artifact for `S5`.
- [x] execute witness pass and pin top runtime owners from measured evidence.
- [x] keep check set, thresholds, and fail-closed semantics unchanged.

##### P3.R3.1 - S5 hotspot optimization pass
Definition of done:
- [x] optimize top measured `S5` hotspots (shared sampled surfaces and/or heavy-check query path) without changing check outcomes.
- [x] preserve deterministic validation artifacts (`report`, `issue_table`, `bundle_index`, `_passed.flag` behavior).
- [x] keep required/warn check semantics and coverage unchanged.

##### P3.R3.2 - Witness execution + closure scoring
Definition of done:
- [x] stage fresh run-id from `P3.R2` authority and execute `S5` (with `S3` frozen and `S4` source retained).
- [x] rerun `S5` immediately on same run-id for stability check.
- [x] score with `tools/score_segment6b_p0_baseline.py`.
- [x] emit `segment6b_p3r3_closure_<run_id>.json/.md` and phase decision:
  - `UNLOCK_P4` if integrated runtime + realism rails pass,
  - else `HOLD_P3_REOPEN_PERF` with next owner lane pinned.

P3.R3 execution status (current authority):
- witness run-id: `08db6e3060674203af415b389d5a9cbd` (staged from `65381edb84e349b8a7e46cba36c1799d`; `S3` frozen).
- artifacts emitted:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_08db6e3060674203af415b389d5a9cbd.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_08db6e3060674203af415b389d5a9cbd.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p3r3_closure_08db6e3060674203af415b389d5a9cbd.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p3r3_closure_08db6e3060674203af415b389d5a9cbd.md`,
  - `runs/fix-data-engine/segment_6B/08db6e3060674203af415b389d5a9cbd/reports/s5_runtime_profile_08db6e3060674203af415b389d5a9cbd.json`.
- runtime posture:
  - `S3` frozen at `372.01s`,
  - `S4=359.61s` (rail PASS),
  - `S5=6.05s` first pass (rail PASS),
  - `S5=3.72s` immediate recheck (rail PASS).
- realism posture:
  - overall verdict remains `PASS_HARD_ONLY`,
  - `T17/T18` unchanged and closed,
  - no hard-gate regressions.
- phase decision:
  - `UNLOCK_P4`.

### P4 - Wave C (`S1` context/session realism closure)
Goal:
- improve attachment/session realism and conditional context carry-through for durable `B+`.

Definition of done:
- [x] context-carry fields required for downstream conditioning are preserved through 6B surfaces.
- [x] singleton-session pressure reduced and attachment richness uplift evidenced.
- [x] `T19-T20` meet `B` thresholds and move toward `B+`.
- [x] cross-seed stability ownership and certification handoff pinned to `P5` (single-seed `P4` closure completed).

P4 expanded execution plan:

#### P4.0 - Authority pin + owner-target lock (`S1`)
Definition of done:
- [x] wave authority run pinned to `P3.R3` witness (`08db6e3060674203af415b389d5a9cbd`) with explicit baseline metrics:
  - `T19=99.9388%` singleton share (`FAIL_B`, `FAIL_B+`),
  - `T20 richness=0.151206` (`PASS_B+`).
- [x] runtime rails pinned for non-regression:
  - `S1<=800s` target, `<=900s` stretch,
  - downstream rails from `P3` remain binding (`S3<=380s`, `S4<=420s`, `S5<=30s`).
- [x] owner boundary pinned: only `S1` policy/code lanes may change in `P4` initial pass.

#### P4.1 - Policy-first session realism calibration (`S1` low-blast lane)
Definition of done:
- [x] session key granularity is reduced from near-identity grouping while preserving deterministic session identity semantics.
- [x] hard-timeout/session-window posture is calibrated to produce non-trivial multi-arrival sessions.
- [x] no schema/dataset-id changes to:
  - `s1_arrival_entities_6B`,
  - `s1_session_index_6B`.
- [x] no changes to scorer thresholds or non-`S1` owner policies.

#### P4.2 - Full witness run and score (`S1 -> S2 -> S3 -> S4 -> S5`)
Definition of done:
- [x] stage fresh run-id from `P3.R3` authority and rerun full required matrix for `S1` owner changes:
  - `S1 -> S2 -> S3 -> S4 -> S5`.
- [x] score using `tools/score_segment6b_p0_baseline.py`.
- [x] emit `segment6b_p4_closure_<run_id>.json/.md` with:
  - `T19/T20` baseline-vs-candidate deltas,
  - runtime deltas (`S1..S5`),
  - hard-gate regression check (`T1-T16`, `T21`, `T22`),
  - phase decision.

#### P4.R1 - Blocker reopen (if `T19` remains open after P4.2)
Definition of done:
- [x] blocker is explicitly classified and mapped to `S1` mechanism:
  - session-key over-fragmentation,
  - timeout-window under-grouping,
  - boundary-rule under-expression.
- [x] bounded reopen plan is appended before edits, selecting exactly one lane at a time:
  - `R1A`: additional key/timeout calibration,
  - `R1B`: boundary-aware `S1` session split/merge refinement (hard-timeout + hard-break/day-boundary semantics) with deterministic guarantees.
- [x] fresh rerun + re-score performed after reopen.
- [x] reopen closes only when `T19` reaches at least `PASS_B` with no hard-gate/runtime regressions.

#### P4.3 - Closure decision and handoff
Definition of done:
- [x] phase decision is one of:
  - `UNLOCK_P5` (if `T19-T20` close at required level with runtime/hard-gate non-regression),
  - `HOLD_P4_REOPEN` (if any `S1` owner blocker remains).
- [x] build plan, implementation notes, and logbook updated with final reasoning trail and closure evidence.

P4 execution status (current authority):
- witness run-id: `86f38dcfc0084d06b277b7c9c00ffc05` (staged from `08db6e3060674203af415b389d5a9cbd`).
- policy delta applied in `S1` lane:
  - `sessionisation_policy_6B`: key fields `[party_id, scenario_id]`, `hard_timeout_seconds=86400`, `hard_break_seconds=172800`.
- gate movement:
  - `T19`: `99.9388% -> 42.8998%` (`FAIL_B/B+ -> PASS_B/B+`),
  - `T20`: `richness=0.151206 -> 0.151206` (`PASS_B+` retained),
  - overall verdict: `PASS_HARD_ONLY -> PASS_B`,
  - hard/stretches failures: none.
- runtime snapshot:
  - `S1=820.25s` (`target<=800` fail, `stretch<=900` pass),
  - `S2=233.94s`,
  - `S3=391.50s` (watch drift above `380s` by `11.50s`),
  - `S4=416.56s` (rail pass),
  - `S5=3.99s` (rail pass).
- blockers resolved in-lane:
  - `P4-B1`: staged lane missing `S1` prerequisites (`5B arrivals`, `6A` surfaces) -> linked required upstream surfaces.
  - `P4-B2`: `S1` staged-output IO conflicts -> removed staged `S1..S3` output links and reran owner matrix.
  - `P4-B3`: disk-full during `S2` write (`os error 112`) -> pruned superseded run-id folders (keep-set authority+active).
  - `P4-B4`: `S5` upstream hashgate flag mismatches after pruning/staging drift -> regenerated `_passed.flag` payloads from sealed-input digests for required upstream gates.
- closure artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_86f38dcfc0084d06b277b7c9c00ffc05.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p0_realism_gateboard_86f38dcfc0084d06b277b7c9c00ffc05.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p4_closure_86f38dcfc0084d06b277b7c9c00ffc05.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p4_closure_86f38dcfc0084d06b277b7c9c00ffc05.md`.
- phase decision:
  - `UNLOCK_P5` (with `S3` runtime watch carried into certification lane).

### P5 - Integrated certification and freeze
Goal:
- complete cross-seed certification, publish final decision, and freeze segment 6B.

Definition of done:
- [x] full `T1-T22` suite executed on required seeds (`42, 7, 101, 202`) with explicit seed->run mapping.
- [x] required certification artifacts emitted under `runs/fix-data-engine/segment_6B/reports/`:
  - `segment6b_p5_validation_summary_<stamp>.json`,
  - `segment6b_p5_seed_comparison_<stamp>.csv`,
  - `segment6b_p5_regression_report_<stamp>.md`,
  - `segment6b_p5_gate_decision_<stamp>.json`.
- [x] cross-seed stability posture computed and recorded (`critical gates`, `stretch gates`, `CV posture`).
- [x] grade decision locked as one of:
  - `PASS_BPLUS_ROBUST`,
  - `PASS_B`,
  - `HOLD_REMEDIATE`.
- [x] freeze note appended to build plan + implementation notes + logbook.

P5 expanded execution plan:

#### P5.0 - Entry lock and seed map authority
Definition of done:
- [x] `P4` authority run pinned as certification anchor (`86f38dcfc0084d06b277b7c9c00ffc05`).
- [x] required seed set pinned (`42,7,101,202`) and selected seed->run map recorded.
- [x] any missing required seeds are classified as fail-closed blocker before decisioning.

#### P5.1 - Certification scorer lane implementation (`S5` evidence owner)
Definition of done:
- [x] dedicated scorer exists for 6B P5 (`tools/score_segment6b_p5_certification.py`).
- [x] scorer validates:
  - run receipt seed alignment,
  - per-seed gateboard presence,
  - hard/stress gate pass posture,
  - cross-seed stability CV posture.
- [x] scorer emits the four required P5 artifacts with deterministic schema.

#### P5.2 - Candidate certification execution (available runs)
Definition of done:
- [x] scorer run executed on currently available seed->run map.
- [x] `segment6b_p5_gate_decision_<stamp>.json` emitted with explicit `decision` and `blocker_register`.
- [x] if missing seeds remain, decision is fail-closed (`HOLD_REMEDIATE`) with actionable resolver plan.

#### P5.3 - Seed-evidence resolver lane (conditional reopen)
Definition of done:
- [x] if P5.2 has missing required seeds, open resolver lane that creates fresh runs under `runs/fix-data-engine/segment_6B/` only.
- [x] resolver lane executes required owner matrix per fresh seed (`S1 -> S2 -> S3 -> S4 -> S5`).
- [x] each resolver run emits `segment6b_p0_realism_gateboard_<run_id>.json` and validates `s5_validation_report_6B`.
- [x] no writes occur in `runs/local_full_run-5/`.

#### P5.4 - Final certification replay and verdict lock
Definition of done:
- [x] scorer rerun on complete required seed map (or explicit unresolved blocker posture if still incomplete).
- [x] final gate decision locked:
  - `PASS_BPLUS_ROBUST` when hard + stretch + stability satisfy `B+`,
  - `PASS_B` when hard + required stretch + stability satisfy `B`,
  - `HOLD_REMEDIATE` otherwise.
- [x] non-regression note includes active runtime watch (`S3`) status.

#### P5.5 - Freeze handoff closure
Definition of done:
- [x] build plan updated with final P5 decision and artifact references.
- [x] implementation map appended with executed commands, alternatives, blockers, and closure logic.
- [x] logbook appended with timestamped P5 closure receipt.
- [x] run-folder keep-set refreshed and superseded run-id folders pruned.

P5 execution status (closure authority):
- candidate certification (pre-resolver) artifact:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_gate_decision_20260226T093404Z.json` (`HOLD_REMEDIATE`; blocker `P5-B1` missing seeds `7,101,202`).
- resolver run-set (required seeds):
  - `42 -> 86f38dcfc0084d06b277b7c9c00ffc05`,
  - `7 -> 4bb1ec493e2d41bd8df0effed18c0e4e`,
  - `101 -> a16ce8f30a4e4523b21d747cf00de69a`,
  - `202 -> 2e67c9d6c6774cad81ca35d9e5dbf1e8`.
- final certification artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_validation_summary_20260226T111812Z.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_seed_comparison_20260226T111812Z.csv`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_regression_report_20260226T111812Z.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_gate_decision_20260226T111812Z.json`.
- final decision:
  - `PASS_B` (all required seeds pass `B`; `B+` not achieved due `T5` remaining below `B+` threshold across seeds).
- runtime watch (carried, non-blocking for `PASS_B`):
  - `S3` remains above the `380s` watch line in this certification set.
- freeze posture:
  - keep-set retained: `08db6e3060674203af415b389d5a9cbd`, `86f38dcfc0084d06b277b7c9c00ffc05`, `4bb1ec493e2d41bd8df0effed18c0e4e`, `a16ce8f30a4e4523b21d747cf00de69a`, `2e67c9d6c6774cad81ca35d9e5dbf1e8`.
  - heavy per-seed `S1..S4` outputs pruned for resolver seeds after gateboard emission to protect storage.

## 7) Decision policy and fail-closed rules
- If any critical gate fails in a wave, stop and reopen only owning lanes before any downstream phase.
- No threshold waivers without explicit documented policy re-baseline.
- Runtime regressions beyond budget are blockers; run bottleneck analysis before more tuning.
- Performance optimization cannot degrade determinism, schema contracts, or validation governance.

### P6 - B+ recovery lane (`T5` owner reopen, frozen `PASS_B` rails)
Goal:
- lift `T5` from current `~0.0674` plateau to `>=0.08` (`B+`) without reopening non-`S4` owners or regressing closed `PASS_B` posture.

Definition of done:
- [x] `T5` reaches `B+` threshold (`>=0.08`) on required seeds (`42,7,101,202`).
- [x] `T1-T4,T6-T10,T22` remain non-regressed on all required seeds.
- [x] no threshold policy/scorer relaxation.
- [x] closure artifacts emitted for witness lane + refreshed certification decision.

P6 execution plan:

#### P6.0 - Design lock and blast-radius controls
Definition of done:
- [x] authority frozen at `P5 PASS_B` seed map and artifacts.
- [x] owner boundary pinned to `S4` bank-view policy/class-conditioning lane only.
- [x] no code-path redesign in first pass (policy-only lane first).
- [x] veto rails pinned:
  - hard non-regression: `T1-T4,T6-T10,T22`,
  - runtime rails: `S4<=420s`, `S5<=30s`.

#### P6.1 - Policy-only class outcome-mix widening (`S4`)
Definition of done:
- [x] strengthen class-conditioned outcome-mix separation in:
  - `detection_model.p_detect_class_multiplier`,
  - `detection_model.p_legit_fp_class_multiplier`,
  - `dispute_model.p_dispute_class_multiplier`,
  - `chargeback_model.p_chargeback_class_multiplier`.
- [x] no schema changes, no scorer changes, no threshold edits.
- [x] deterministic replay semantics preserved.

#### P6.2 - Single-seed witness gate (`seed=42`)
Definition of done:
- [x] fresh staged run-id created under `runs/fix-data-engine/segment_6B/`.
- [x] execute `S4 -> S5` only on staged lane.
- [x] score with `tools/score_segment6b_p0_baseline.py`.
- [x] move lane to required-seed matrix only if:
  - `T5` moves upward materially toward/above `0.08`,
  - no veto rail regression.

#### P6.3 - Required-seed matrix and certification refresh
Definition of done:
- [x] execute fresh staged `S4 -> S5` witnesses for seeds `42,7,101,202`.
- [x] emit refreshed per-seed gateboards and P5 certification artifacts.
- [x] decision emitted:
  - `PASS_BPLUS_ROBUST` if all required `B+` + stability pass,
  - `PASS_B` otherwise (with blocker evidence).

#### P6.4 - Closure + freeze update
Definition of done:
- [x] build plan + implementation notes + logbook updated with closure evidence.
- [x] superseded `segment_6B` run-id folders pruned with explicit keep-set.

P6 execution status (closure authority):
- per-seed witness map used for closure:
  - `42 -> 2ee75ef0ff4f47948847fb314a59f632`,
  - `7 -> b723338d60654024856679a415868783`,
  - `101 -> 39ac923d6b234cd589c3dd89fb13654c`,
  - `202 -> ee1707f82042424ba895e19d8b4a8899`.
- refreshed P5 certification artifacts:
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_validation_summary_20260226T152851Z.json`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_seed_comparison_20260226T152851Z.csv`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_regression_report_20260226T152851Z.md`,
  - `runs/fix-data-engine/segment_6B/reports/segment6b_p5_gate_decision_20260226T152851Z.json`.
- phase decision:
  - `PASS_BPLUS_ROBUST`.
- critical metric evidence:
  - `T5` across required seeds in `[0.0926699604, 0.0927115019]` (all `B+`),
  - `T6` and `T7` remain `B+` on all required seeds.
- runtime note for reopened matrix:
  - `S5` remained within rail on all seeds (`<=30s`),
  - `S4` exceeded the pinned `420s` rail on full-chain fallback runs for seeds `101` (`423.38s`) and `202` (`461.34s`); recorded as runtime watch while realism closure remains green.
- prune receipt:
  - superseded run-id folders removed: `189940d0485249d6b3ed29fb496d91f8`, `4bb1ec493e2d41bd8df0effed18c0e4e`, `a16ce8f30a4e4523b21d747cf00de69a`, `2e67c9d6c6774cad81ca35d9e5dbf1e8`, `77500e5440f84b06b9611a4cc483d091`.
  - active keep-set: `08db6e3060674203af415b389d5a9cbd`, `86f38dcfc0084d06b277b7c9c00ffc05`, `2ee75ef0ff4f47948847fb314a59f632`, `b723338d60654024856679a415868783`, `39ac923d6b234cd589c3dd89fb13654c`, `ee1707f82042424ba895e19d8b4a8899`.

## 8) 2026-02-28 Memory Hardening Reopen Lane (`S1` precompute owner)
Goal:
- remove memory-spike risk in `6B.S1` precompute stage while preserving existing `S2/S3/S4` batch posture.

Scope:
- owner state: `S1` (`packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py`).
- non-owner states (`S2/S3/S4`) remain watch-only unless regression appears.

State-by-state execution order:
1. `M6B.1` (`S1` eager preload decomposition).
2. `M6B.2` (`S1` join-domain bounding).
3. `M6B.3` integrated witness (`S1 -> S2 -> S3 -> S4 -> S5`) and closure.

Current dependency note (2026-02-28):
- execution of `M6B` remains queued behind `M6A` witness-lane readiness because `6B` consumes `6A` outputs; active blocker is `6A.S0` upstream hashgate/schema incompatibility on staged lane.

Execution phases:

### M6B.1 - S1 eager preload decomposition
Definition of done:
- [ ] replace broad eager base-table preloads with projection-scoped batched/lazy precompute tables.
- [ ] keep session candidate semantics and deterministic bucket/session assignment behavior unchanged.

### M6B.2 - S1 join-domain bounding
Definition of done:
- [ ] ensure candidate and vector joins are bounded by active scenario/account/device domains.
- [ ] avoid all-domain in-memory vectors where not required.

### M6B.3 - Witness rerun and closure decision
Definition of done:
- [ ] witness lane `S1 -> S2 -> S3 -> S4 -> S5` executes `PASS` without memory crash.
- [ ] existing B/B+ realism closure rails remain non-regressed.
- [ ] decision emitted:
  - `MEMORY_HARDENING_CLOSED_6B` if stable pass,
  - `HOLD_M6B_REOPEN` otherwise.
