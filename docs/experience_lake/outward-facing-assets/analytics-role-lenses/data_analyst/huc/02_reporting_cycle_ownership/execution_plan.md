# Execution Plan - Reporting Cycle Ownership Slice

As of `2026-04-03`

Purpose:
- turn the chosen HUC reporting-cycle-ownership slice into a concrete execution order tied to the bounded governed service-line views
- keep the work requirement-first, reporting-cycle-first, and bounded to one owned recurring pack
- prove service-line reporting ownership, KPI-definition control, repeatable pack structure, and rerun discipline without drifting back into a broader source-integration slice

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)
- bounded governed service-line outputs already created in HUC slice `01_multi_source_service_performance`
- governed local artefacts already available in `artefacts/analytics_slices/`

Primary rule:
- define the reporting requirement and audience need first
- define the KPI and period-comparison logic second
- package the owned recurring reporting pack third
- add rerun controls, caveats, and change discipline last

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the first HUC slice already provides a stable enough service-line KPI layer to serve as the reporting logic substrate
- one bounded weekly reporting cadence is sufficient to prove recurring reporting ownership for this slice
- the reporting lane can stay focused on one service-line analogue rather than trying to represent every HUC reporting audience
- operations and leadership are enough as the core audience pair for this proof
- the reporting cycle can be made rerunnable and controlled from bounded SQL and compact pack-generation logic

Working assumption about the reporting lane:
- the slice will own one weekly current-versus-prior service-line reporting pack
- the pack will answer a small performance question consistently from week to week
- the same KPI meaning will hold across executive, operational, and drill-through views

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the underlying KPI layer is not stable enough, fix the reporting logic first rather than pretending the reporting cycle is already ownable

## 2. Execution Center Of Gravity

This slice must stay distinct from HUC slice `01`.

That means:
- do not treat this as another proof of multi-source integration
- do not spend the center of gravity on new source reconciliation work unless a reporting-control issue forces it
- do not widen the KPI family beyond what the reporting lane needs
- do not build a broader BI estate

This slice should instead prove:
- one reporting lane has been defined clearly
- one small KPI family has been pinned to real reporting needs
- one recurring pack exists in a reusable format
- one rerun path, checklist, caveat layer, and change-control note exist

## 3. Best Execution Order

The execution order remains:
- `05 -> 01 -> 02 -> 09`

That means:
1. define the reporting need and audience structure
2. define the KPI and comparison logic underneath it
3. package the recurring reporting product
4. harden the cycle into a rerunnable owned process

## 4. First-Pass Objective

The first-pass objective is:

`build one repeatable weekly service-line reporting cycle with stable KPI definitions, one recurring three-page pack, and one rerun-control layer that another analyst could follow safely`

The proof object is:
- `reporting_cycle_ownership_v1`

The first-pass output family is:
- one reporting-requirements and stakeholder-view layer
- one KPI definition and period-comparison layer
- one recurring three-page reporting pack
- one `what changed` and intervention-summary pair
- one run checklist
- one caveat note
- one changelog
- one regeneration README

## 5. Requirement and Audience Gate

Before changing any visuals or pack logic, run a requirement-and-audience gate.

The first pass must answer:
- what exact reporting lane is being owned?
- what do operations need to see first?
- what does leadership need summarised first?
- which KPIs are headline KPIs and which belong only in drill-through?
- what counts as anomaly-worthy movement for this reporting lane?
- what needs to be stable between cycles?

Required outputs from this gate:
- one reporting requirements note
- one process map
- one stakeholder view matrix
- one KPI purpose note

Decision rule:
- if the reporting need is still vague, stop and sharpen the lane before composing the pack
- if the pack answer is already clear, proceed into KPI and period-comparison shaping

## 6. KPI and Comparison Strategy

This slice should reuse or lightly reshape the service-line KPI logic rather than rebuild the first HUC slice from scratch.

The KPI family must remain small and stable:
- volume or pressure
- conversion
- backlog or aging
- outcome quality

The period-comparison layer must answer:
- how did the current cycle move versus the prior cycle?
- which KPI moved materially?
- what is the most important anomaly or exception to highlight?
- what should operations do first?

Required outputs:
- one governed KPI view
- one current-versus-prior period-comparison view
- one `what changed` note
- one intervention note

Decision rule:
- every KPI in the pack must map back to a real reporting need
- if a KPI exists only because it is available, drop it

## 7. Reporting-Product Strategy

Once the requirement layer and KPI layer are stable, package the owned recurring reporting product.

Keep this to one recurring `3`-page pack:

### Page 1. Executive service-line overview

This page should answer:
- what changed at top line?
- what should leadership know first?
- is the issue structural, temporary, or improving?

Required components:
- headline KPI cards
- current-versus-prior movement
- one short issue summary

### Page 2. Operational performance view

This page should answer:
- how is the lane performing operationally?
- where is the pressure, backlog, or quality issue?
- what anomaly deserves attention?

Required components:
- conversion view
- backlog or aging view
- outcome-quality view
- one anomaly highlight

### Page 3. Drill-through and detail

This page should answer:
- which segment or slice is driving the movement?
- what exception or issue is important?
- what should the reader conclude from the detail?

Required components:
- segment breakdown
- one issue note
- one interpretation note

Create:
- `service_line_reporting_pack_v1`
- `service_line_kpi_definition_sheet_v1.md`
- `service_line_page_notes_v1.md`

## 8. Reporting-Cycle Control Strategy

This is what makes the slice about ownership rather than one-off output.

The first-pass control layer should include:
- one report-run checklist
- one caveat note
- one changelog
- one regeneration README

Those outputs must answer:
- what inputs are needed for the cycle?
- what order should the run follow?
- what checks should be completed before release?
- what caveats must travel with the pack?
- what changed from the previous pack version?
- can another analyst rerun it safely?

Required outputs:
- `service_line_report_run_checklist_v1.md`
- `service_line_reporting_caveats_v1.md`
- `service_line_reporting_changelog_v1.md`
- `README_service_line_reporting_regeneration.md`

## 9. Reuse Strategy

This slice should reuse bounded artefacts from HUC slice `01` where that helps prove recurring ownership.

Permitted reuse:
- service-line KPI logic
- current-versus-prior comparison logic
- pack rendering logic where it remains aligned to the new reporting-ownership proof
- existing page notes or briefing structures if they are promoted into cycle-controlled reporting assets

But the proof burden must shift from:
- `can we produce one bounded service-line pack?`

to:
- `can we own, define, rerun, and control the reporting cycle itself?`

## 10. Planned Deliverables

Requirement and design:
- one reporting requirements note
- one process map
- one stakeholder view matrix
- one KPI purpose note

KPI and comparison logic:
- one KPI SQL layer
- one period-comparison SQL layer
- one `what changed` note
- one intervention note

Reporting product:
- one recurring three-page service-line reporting pack
- one KPI definition sheet
- one page-notes document

Reporting-cycle controls:
- one run checklist
- one changelog
- one caveat note
- one regeneration README

Expected output bundle for the first pass:
- one owned recurring service-line reporting pack
- one stable KPI-definition layer
- one current-versus-prior interpretation layer
- one explicit rerun and release-control layer

## 11. What To Measure For The Claim

For this requirement, the strongest measures are ownership, repeatability, and reporting usefulness.

Primary measure categories:
- number of KPI families defined and reused consistently
- number of audience-specific views delivered in one cycle
- time to rerun the reporting pack from controlled logic
- number of documented release or review checks
- number of anomaly or exception items surfaced with explanation

Secondary measure categories:
- one stable KPI-definition sheet used across the pack
- one changelog proving definition continuity
- one handover-ready rerun path

## 12. Execution Order

1. Finalise the folder structure for this HUC reporting-ownership lane.
2. Write the reporting requirements, process-map, audience, and KPI-purpose layer.
3. Reuse or reshape the KPI and period-comparison logic for the reporting lane.
4. Build the recurring three-page reporting pack.
5. Write the `what changed` and intervention notes.
6. Write the KPI-definition sheet and page notes.
7. Add the report-run checklist, caveat note, changelog, and regeneration README.
8. Write the execution report and claim surfaces only after the evidence is real.

## 13. Stop Conditions

Stop and reassess if any of the following happens:
- the reporting lane is still too vague to define ownership cleanly
- the KPI family keeps expanding beyond what the reporting question needs
- the pack relies on unstable or unclear KPI meaning
- the reporting cycle cannot be rerun without manual hidden steps
- the slice starts drifting back into multi-source integration proof instead of recurring reporting ownership

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the reporting lane if needed
- simplify the pack if needed
- preserve the center of gravity around owned recurring reporting rather than raw analysis

## 14. What This Plan Is And Is Not

This is:
- a concrete execution plan for the second HUC responsibility slice
- requirement-first
- reporting-cycle-first
- bounded
- aligned to recurring reporting ownership, KPI-definition control, and rerun discipline

This is not:
- the execution report
- another proof of source integration
- a broad BI programme
- permission to assume the reporting cycle is ownable without documenting the controls

The first operational move after this plan should be:
- write the reporting requirements and stakeholder-view layer and use that to pin the final recurring pack structure before any further pack rendering work starts
