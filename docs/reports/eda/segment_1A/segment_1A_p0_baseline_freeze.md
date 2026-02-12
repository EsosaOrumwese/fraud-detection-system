# Segment 1A P0 Baseline Freeze

- Run id: `7d5a4b519bb5bc68ee80b52b0a2eabeb`
- Manifest fingerprint: `ef344b90a93030e04dc0011c795ee9d19500239657b16e0ab3afa76b7b2f2b3d`
- Parameter hash: `56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`
- Seed: `42`

## Baseline metrics

| Surface | Metric | Value |
|---|---|---:|
| Merchant pyramid | single-site share | 0.0000 |
| Merchant pyramid | outlets/merchant median | 15.00 |
| Concentration | top-10% outlet share | 0.5010 |
| Concentration | Gini (outlets/merchant) | 0.5638 |
| Geo/legal | home!=legal row share | 0.4104 |
| Geo/legal | size gradient (pp) top decile - bottom deciles (1-3 mean) | 5.57 |
| Candidate realism | foreign candidate median | 37.00 |
| Candidate realism | candidate->membership Spearman | 0.1044 |
| Candidate realism | realization ratio median | 0.0000 |
| Dispersion realism | phi CV | 0.000530 |
| Dispersion realism | phi P95/P05 | 1.000042 |

## Hard-gate status (P0 baseline)

| Hard gate | Status |
|---|---|
| single_site_share_ge_0_25 | FAIL |
| candidate_foreign_median_le_15 | FAIL |
| phi_cv_ge_0_05 | FAIL |
| phi_p95_p05_ge_1_25 | FAIL |
| required_outputs_present | FAIL |
| determinism_replay_same_seed | FAIL (NOT_ASSESSED_IN_P0_SINGLE_RUN_BASELINE) |

- Hard gates passing now: **0/6**

## Required-output presence snapshot

| Output | Present |
|---|---|
| s3_integerised_counts | NO |
| s3_site_sequence | NO |
| sparse_flag | NO |
| merchant_abort_log | NO |
| hurdle_stationarity_tests | NO |

Artifacts:
- `runs/fix-data-engine/segment_1A/7d5a4b519bb5bc68ee80b52b0a2eabeb/reports/p0_baseline_metrics.json`
- `runs/fix-data-engine/segment_1A/7d5a4b519bb5bc68ee80b52b0a2eabeb/reports/p0_hard_gate_status.json`