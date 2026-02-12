# Segment 1A Remediation Build Plan (State Phases + DoD)
_As of 2026-02-12_

## Execution Rule
- Every evaluation/remediation run executes sequentially:  
  `S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9`
- We do not skip upstream states; we prioritize which states get changed.

## Remediation Phases

### Phase 0: Baseline Lock
Focus states:
- none (run-only)

Run-through states:
- `S0..S9`

Definition of Done:
- [ ] Baseline run exists under `runs/fix-data-engine/segment_1A/...`.
- [ ] Baseline values captured for:
  - single-site share
  - candidate-count distribution
  - `home!=legal` share + decile gradient
  - `phi` spread (`CV`, `P95/P05`)
- [ ] Baseline artifact presence/absence recorded.

---

### Phase 1: Population Shape Recovery
Focus states:
- `S8` (primary)
- `S1` (conditional only if needed)

Definition of Done:
- [ ] Single-site merchants are materially present (`P(outlet_count=1) >= 0.25`).
- [ ] Outlet pyramid no longer chain-collapsed.
- [ ] `single_vs_multi_flag` behavior aligns with generated population shape.

---

### Phase 2: Candidate Universe Recovery
Focus states:
- `S3` (primary)

Definition of Done:
- [ ] Candidate breadth no longer near-global (`median(candidate_count) <= 15`).
- [ ] Candidate generation is profile-conditioned (small/local not treated as global).
- [ ] `s3_integerised_counts` and `s3_site_sequence` emitted.

---

### Phase 3: Realization + Domicile Recovery
Focus states:
- `S6` (primary)
- `S8` (conditional expression fix only if needed)

Definition of Done:
- [ ] `home!=legal` in target corridor (`B`: `0.10..0.25`).
- [ ] Mismatch is size-stratified (top decile at least `+5pp` vs bottom deciles).
- [ ] Candidate->realization coupling materially improved.

---

### Phase 4: Dispersion Recovery
Focus states:
- `S2` (primary)
- `S1` (conditional only if coupled drift appears)

Definition of Done:
- [ ] Dispersion not near-flat:
  - `CV(phi) >= 0.05`
  - `P95/P05(phi) >= 1.25`
- [ ] Heterogeneity visible across merchant strata.

---

### Phase 5: Integration and Closeout
Focus states:
- targeted retunes only where residual defects remain.

Definition of Done:
- [ ] All target data surfaces pass in the same run.
- [ ] Required artifacts are present:
  - `s3_integerised_counts`
  - `s3_site_sequence`
  - `sparse_flag`
  - `merchant_abort_log`
  - `hurdle_stationarity_tests`
- [ ] Segment 1A accepted for progression (`B` minimum, `B+` if achieved).

## State Role Matrix
Legend:
- `run`: always executes.
- `focus`: primary remediation target in phase.
- `conditional`: edit only if required by observed data outcomes.
- `check`: consistency/non-regression only.

| State | P0 | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|---|
| S0 | run | run/check | run/check | run/check | run/check | run/check |
| S1 | run | run/conditional | run/check | run/check | run/conditional | run/conditional |
| S2 | run | run/check | run/check | run/check | run/focus | run/conditional |
| S3 | run | run/check | run/focus | run/check | run/check | run/conditional |
| S4 | run | run/check | run/check | run/check | run/check | run/check |
| S5 | run | run/check | run/check | run/check | run/check | run/check |
| S6 | run | run/check | run/check | run/focus | run/check | run/conditional |
| S7 | run | run/check | run/check | run/check | run/check | run/check |
| S8 | run | run/focus | run/check | run/conditional | run/check | run/conditional |
| S9 | run | run/check | run/check | run/check | run/check | run/check |

## Run Isolation
- Baseline evidence (read-only):
  - `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/...`
- Active remediation runs:
  - `runs/fix-data-engine/segment_1A/...`

