# Dev Full Certification Handoff
_As of 2026-03-02 (UTC)_

## 1) Handoff Intent
This file is the clean start packet for the next chat/session to execute certification tracks after dev_full build closure.

Current authoritative posture:
1. `M15` is closed green.
2. Final gate is `CERTIFICATION_TRACKS_READY`.
3. Next work is certification only:
   - runtime certification track (`RC*`),
   - ops/governance certification track (`OC*`).

This handoff is intended to minimize context drift and prevent re-litigating build-phase decisions already closed.

## 2) Proven Closure State (Authoritative)
Primary closure execution:
1. `m15j_closure_sync_20260302T085244Z`

Authoritative outcomes:
1. `M15.J` summary:
   - `overall_pass=true`
   - `verdict=ADVANCE_TO_CERTIFICATION_TRACKS`
   - `next_gate=CERTIFICATION_TRACKS_READY`
2. Final `M15` summary:
   - `overall_pass=true`
   - `verdict=M15_COMPLETE_GREEN`
   - `next_gate=CERTIFICATION_TRACKS_READY`

Durable closure prefix:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15j_closure_sync_20260302T085244Z/`

Key closure artifacts:
1. `m15j_closure_sync_snapshot.json`
2. `m15j_handoff_pack.json`
3. `m15j_blocker_register.json`
4. `m15j_execution_summary.json`
5. `m15_blocker_register.json`
6. `m15_execution_summary.json`

## 3) Certification Entry Surfaces
Runtime certification:
1. Plan: `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.runtime_cert.plan.md`
2. Entry gate: `RC0_READY`

Ops/Gov certification:
1. Plan: `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.ops_gov_cert.plan.md`
2. Entry gate: `OC0_READY`

Certification truth anchor:
1. `docs/experience_lake/platform-production-standard.md`

## 4) Authority and Reading Order for Next Chat
Read in this exact order before executing certification:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/cert_handoff.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M15.build_plan.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.runtime_cert.plan.md`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.ops_gov_cert.plan.md`
6. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
7. `docs/logbook/03-2026/2026-03-02.md`
8. Readback closure artifacts under:
   - `runs/dev_substrate/dev_full/m15/m15j_closure_sync_20260302T085244Z/`
   - durable S3 prefix above.

## 5) Non-Negotiable Execution Laws (Certification Stage)
These are binding in the next session:
1. Fail-closed on ambiguity, drift, or missing evidence.
2. No certification claim without inspectable evidence artifact.
3. No silent waivers; all waivers must be explicit, time-bounded, and recorded.
4. Cost-control law remains active during certification (attribution and envelope discipline required).
5. Keep certification separate from build-phase ladder (do not reopen M* unless a proven blocker requires it).
6. Branch-governance and commit-scope laws remain active.

## 6) Known Semantic Baseline Notes to Preserve
1. `M15.I` aggregate counters were corrected to avoid double-counting:
   - `M15.H` remains in gate checks but is excluded from additive aggregate counters.
2. Authoritative M15 rollup execution for certification input:
   - `m15i_phase_rollup_20260302T084631Z`
   - use this, not superseded `m15i_phase_rollup_20260302T084528Z`.
3. M15 advisory posture retained (non-blocking):
   - `M15G-AD1` (`rewired_eval_only`) remains explicitly documented.

## 7) First-Step Checklist for New Chat
1. Verify `M15` closure artifacts local + durable are readable.
2. Reconfirm `M15_COMPLETE_GREEN` and `CERTIFICATION_TRACKS_READY`.
3. Activate runtime-cert plan at `RC0` (do not execute OC lanes yet unless parallelized intentionally).
4. Expand `RC0` to execution-grade, execute, and only then proceed sequentially.
5. Keep a live decision trail in:
   - `platform.impl_actual.md`
   - `docs/logbook`.

## 8) Expected Deliverables from Certification Stage
Runtime track must emit:
1. `runtime_claim_matrix.json`
2. `runtime_scorecard_profiles.json`
3. `runtime_drill_bundle.json`
4. `runtime_blocker_register.json`
5. `runtime_certification_verdict.json`

Ops/Gov track must emit:
1. `ops_gov_claim_matrix.json`
2. `ops_gov_drill_bundle.json`
3. `ops_gov_blocker_register.json`
4. `ops_gov_certification_verdict.json`
5. `ops_gov_release_corridor_receipt.json`
6. `ops_gov_cost_governance_receipt.json`

Joint stitched pack (after both tracks):
1. `dev_full_point_x_summary.md`
2. `tier0_claimability_table.json`
3. Links to both certification verdicts.

## 9) Explicit Session Handoff Statement
Build-phase progression is complete through `M15.J`.
The active objective is now certification execution and verdict hardening, beginning with runtime `RC0`.
