# Execution Plan - Governed and Explainable AI Delivery Slice

As of `2026-04-03`

Purpose:
- turn the chosen governed-and-explainable AI slice into an execution order tied to the local governed run
- keep the work bounded, SQL-first where appropriate, and explicitly reviewable
- preserve the real proof burden of this requirement: governed model use, explainability, model-choice discipline, threshold governance, and safe downstream use

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)

Primary rule:
- pin the governed use case first
- pin authoritative feature and target sources before training
- screen leakage before any model comparison
- compare only enough model complexity to justify a governed model-choice decision
- treat threshold, explanation, and caveat outputs as core deliverables, not as packaging added at the end

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- `flow_id` is still the right grain for the bounded governed scoring use case
- the local governed run contains the same core modelling surfaces already used successfully in the earlier flow-level work
- authoritative truth can be separated cleanly from comparison-only operational fields
- a simple interpretable baseline is likely to be viable before any challenger is considered

Candidate first-pass governed surfaces:
- `s2_flow_anchor_baseline_6B`
- `s4_flow_truth_labels_6B`
- `s4_flow_bank_view_6B`
- `s4_case_timeline_6B`

Working assumption about the use case:
- the score will predict bounded authoritative fraud outcome or equivalent high-value flow-level outcome
- the score is allowed to inform prioritisation support
- the score is not allowed to operate as a standalone autonomous decision

Important warning:
- these assumptions must be tested and restated in the governed use-case note
- if the local evidence does not justify a challenger model, the correct move is to omit it

## 2. Required Execution Order

This slice should follow the corrected execution order:
- `03 -> 07 -> 09 -> 08`

Meaning:
- first pin the governed modelling context
- then build and compare the bounded scoring logic
- then make the work reviewable and repeatable
- then package it for safe decision use

This order matters because model comparison is not credible until:
- source meaning is pinned
- target authority is pinned
- leakage boundaries are tested
- safe-use and non-use are stated clearly

## 3. First-Pass Objective

The first-pass objective is:

`build one reviewable flow-level risk scoring slice with explicit model-choice, threshold, and explanation governance`

The proof object is:
- `governed_explainable_ai_v1`

The first-pass output family is:
- one governed use-case pack
- one source-rules and fit-for-use pack
- one leakage-safe model-ready slice
- one interpretable baseline model
- one optional challenger comparison
- one model-selection decision note
- one threshold or risk-band note
- one explanation pack
- one assumptions, limits, and caveat pack
- one stakeholder decision brief
- one challenge-response note

## 4. Lens 03 Execution Block - Govern the Modelling Context

This block must run before any model training.

The first profiling pass must answer:
- what exactly is being predicted?
- what operational use is the score allowed to support?
- what is the score not allowed to decide on its own?
- which source is authoritative for the target?
- which fields are feature-allowed?
- which fields are truth-only or comparison-only?
- which fields create leakage or misleading shortcuts?

Required SQL checks:
- distinct `flow_id` coverage across anchor, truth, bank, and case surfaces
- target prevalence and target completeness
- critical null-rate checks for candidate feature families
- timestamp boundaries for bounded train, validation, and test windows
- comparison of authoritative truth and bank-view operational fields
- leakage screen over case and truth fields that should never enter the feature set

Required outputs from this block:
- `governed_model_use_case_v1.md`
- `model_source_rules_v1.md`
- `model_fit_for_use_checks_v1.md`
- `model_risk_note_v1.md`
- `model_lineage_and_join_path_v1.md`

Decision rule:
- if target authority, feature boundaries, and leakage posture are clean, proceed
- if feature or target posture is ambiguous, fix the governed modelling context before any model is trained

## 5. Candidate Governed Use Case

The first-pass use case should stay narrow and explicit.

Recommended prediction question:
- predict authoritative fraud truth or equivalent high-value flow outcome at `flow_id` level for bounded prioritisation support

Allowed use:
- ranking or banding flows for human-led review prioritisation
- supporting decision preparation and triage

Explicit non-use:
- no autonomous adjudication
- no truth-only or post-outcome fields in the feature set
- no bank-view field used as the target

This governed use-case statement should be written before modelling begins and should not drift casually during execution.

## 6. Candidate Source Chain

The first-pass source chain should stay bounded and explicit.

Each source should have one stated contribution:
- `s2_flow_anchor_baseline_6B`
  - canonical `flow_id`
  - anchor timestamps
  - stable structural context
  - low-risk first-pass features
- `s4_flow_truth_labels_6B`
  - authoritative target surface
- `s4_flow_bank_view_6B`
  - comparison-only operational signal for later explanation or assurance
- `s4_case_timeline_6B`
  - bounded case progression context only where it supports explanation without leaking future truth

Authoritative-source rule expected at plan stage:
- truth labels define the target
- bank view remains comparison-only
- case timeline is allowed only where bounded explanatory context stays leakage-safe

## 7. Lens 07 Execution Block - Build the Explainable Model Slice

This is the core analytical build once the governance gate is green.

### Step 1. Build the model-ready slice in SQL

Create one bounded SQL output:
- `flow_model_ready_slice_v1`

This output should include:
- `flow_id`
- selected feature columns
- authoritative target flag
- split marker
- compact explanatory dimensions for later interpretation

This slice must be:
- explicit
- leakage-screened
- documented
- reusable

### Step 2. Train the interpretable baseline

Required baseline:
- one clearly explainable model such as logistic regression

This baseline should be the default candidate, not a placeholder to discard immediately.

### Step 3. Optionally train one stronger challenger

The challenger is allowed only if:
- the baseline is materially weak
- the challenger adds real useful lift
- the comparison helps justify a governed selection decision

Only one challenger is allowed.
The point is governed comparison, not benchmark chasing.

### Step 4. Evaluate with a compact metric set

Primary metrics:
- high-risk band lift or yield
- capture of positive or higher-value outcomes
- bounded-window stability across validation and test

Secondary metrics:
- threshold behaviour
- score separation by band
- compact baseline-versus-challenger comparison

### Step 5. Build the explanation layer

The first-pass explanation set should cover:
- main score drivers for the selected model
- score distribution and band behaviour
- why some flows are ranked above others
- where explanation reduces confidence in use

### Step 6. Make the explicit model-choice decision

Expected outcome:
- baseline selected
- challenger selected
- or challenger rejected

The decision note should justify the choice against:
- performance
- explainability
- stability
- operational risk
- downstream usability

### Step 7. Make the threshold decision

The first-pass threshold strategy should answer:
- what threshold or banding rule creates usable prioritisation support?
- what trade-off exists between reviewed volume and yield?
- where should human review inspect or override the score?

Required outputs from this block:
- `flow_governed_model_base_v1.py`
- `flow_governed_model_compare_v1.py`
- `flow_model_explanation_pack_v1.md`
- `flow_model_selection_decision_v1.md`
- `flow_model_threshold_note_v1.md`

## 8. Split Strategy

The split strategy should be time-based, not random.

Reason:
- the slice needs to support a governed delivery claim, not just a convenient modelling result
- time-based validation better fits threshold and explanation review
- random splits weaken the bounded operational-use story

First-pass split posture:
- earliest bounded window: training
- middle bounded window: validation
- latest bounded window: test

The exact boundaries should only be pinned after SQL timestamp profiling confirms coverage and prevalence.

## 9. Lens 09 Execution Block - Make It Reviewable And Repeatable

This block turns the slice into something safe to circulate.

The first-pass review pack should stabilise:
- target meaning
- feature-set meaning
- threshold or band meaning
- in-scope time window
- approved downstream use

The first-pass review pack should also document:
- what the model is for
- what the model is not for
- what caveats apply
- where confidence is weaker
- what drift would invalidate earlier outputs

Required regeneration notes:
- how to rerun the slice
- which inputs are required
- which outputs must be checked before recirculation
- what would count as a material model or meaning change

Required outputs from this block:
- `model_definition_pack_v1.md`
- `model_assumptions_and_limits_v1.md`
- `README_model_regeneration_v1.md`
- `MODEL_CHANGELOG.md`
- `model_handover_summary_v1.md`

## 10. Lens 08 Execution Block - Explain It For Safe Decision Use

This block must make the score understandable without overselling it.

The stakeholder pack should contain:
- one decision brief
- one challenge-response note
- one annotated summary surface
- one action note

The decision brief should answer:
- what the score predicts
- what the threshold means
- which flows deserve attention
- what the model helps with
- what it does not replace

The challenge-response note should answer:
- why trust this score?
- why not trust it blindly?
- why not choose a less explainable alternative if one exists?
- what happens when the model is wrong?
- when should humans override the score?

Required outputs from this block:
- `flow_model_decision_brief_v1.md`
- `flow_model_challenge_response_v1.md`
- `flow_model_annotated_summary_v1`
- `flow_model_action_note_v1.md`

## 11. Minimum Proof Pack To Deliver

The smallest credible proof pack for this slice is:
- one governed modelling slice
- one interpretable baseline model
- one optional challenger comparison
- one model-choice decision note
- one threshold or risk-band note
- one explanation pack
- one assumptions, limits, and caveat pack
- one stakeholder decision brief

If execution produces only model metrics and scores, the slice has under-delivered.

## 12. Artefact Destinations

Execution artefacts:
- `artefacts/analytics_slices/data_scientist/midlands_partnership_nhs_ft/05_governed_explainable_ai/`

Documentation:
- `docs/experience_lake/outward-facing-assets/analytics-role-lenses/data_scientist/midlands_partnership_nhs_ft/05_governed_explainable_ai/`

## 13. Definition Of A Successful First Pass

The first pass should be considered successful if:
- the governed prediction question is pinned clearly
- authoritative feature and target sources are pinned clearly
- leakage boundaries are documented and respected
- one interpretable baseline is trained and evaluated
- one explicit decision is made on whether a challenger is worth using
- one threshold or banding decision is written down
- one explanation pack makes the score reviewable
- one assumptions and limits pack makes the slice safe to circulate
- one stakeholder decision brief explains how the model should and should not be used

If the work only proves that a model can score flows, the slice has drifted back into generic predictive modelling.
