# Execution Plan - Data Quality Audit And Governance Support Slice

As of `2026-04-04`

Purpose:
- turn the chosen Claire House `3.E` slice into a concrete execution order tied to the trusted provision and maintained-layer outputs already available in the repo
- keep the work audit-first, findings-first, and recommendation-first rather than drifting into generic governance wording or passive quality commentary
- prove active data-quality monitoring, explicit audit findings, linked recommendations, and bounded governance support from one controlled analytical lane
- keep execution memory-safe by reusing the Claire House `3.A` and `3.D` compact outputs before considering any broader raw query footprint

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- the trusted provision lane already established in Claire House `3.A`
- the maintained analytical layer already established in Claire House `3.D`
- compact audit outputs and notes to be written under `artefacts/analytics_slices/data_analyst/claire_house/05_data_quality_audit_and_governance_support/`

Primary rule:
- confirm the exact bounded analytical lane inherited from Claire House `3.A` and `3.D` first
- define the audit scope and check families explicitly before packaging any findings
- produce one monitoring summary, one audit findings output, one recommendation set, and one governance-support note from that same bounded lane
- package governance support only after the findings and recommendations are real
- never load broad raw detailed surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact audit-ready outputs
- if figures are used later, they must be analytical plots that clarify the quality-audit truth, not explanatory diagrams or decorative governance graphics

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains a trustworthy analytical lane from Claire House `3.A` and `3.D` that can support one bounded quality-monitoring and audit pack honestly
- one compact set of repeatable checks can be stated over that lane without reopening broad raw analytical scope
- one useful findings-to-recommendation chain can be produced from the same bounded lane
- one governance-support note can be written from controls, caveats, and findings without pretending to own a governance or `IG` function

Candidate first-pass reusable foundations:
- Claire House `01_trusted_data_provision_and_integrity` provision-trust, source, and protection posture
- Claire House `04_data_infrastructure_models_and_process_improvement` maintained analytical layer, control profile, and release checks
- Claire House `02_reporting_dashboards_and_visualisation` only where downstream reporting quality is used as the protected consequence of the bounded lane

Working assumption about the bounded audit question:
- the audit should sit directly on the trusted provision and maintained-layer path
- the recommendation set should follow from actual control findings, not broad governance theory
- the slice should prove quality monitoring and governance support, not new analytical discovery

Important warning:
- these assumptions must be tested rather than carried forward casually
- if the inherited lane is too thin for one of the audit outputs, adapt by narrowing the audit scope rather than broadening the raw query footprint

## 2. Audit-First Posture

This slice must not begin as a recommendation-first or governance-language-first exercise.

The correct posture is:
- confirm the inherited bounded lane first
- define the audit scope first
- define the repeatable checks second
- build the monitoring summary third
- build the audit findings output fourth
- derive recommendations from those findings fifth
- write the governance-support note sixth
- use Python only after the SQL layer has already reduced the slice to compact audit-ready outputs

This matters because the Claire House responsibility here is about monitoring, auditing, recommending, and supporting governance, and the execution should read like real quality-assurance work rather than a soft governance memo.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The underlying run contains very large detailed surfaces, so the correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not rerun wide historical profiling if the audit question can be answered from Claire House `3.A` and `3.D` outputs plus one compact audit layer
- do not assume that a governance-support slice justifies reopening broad raw analytical scope

The correct query discipline is:
- start with summary-stats and audit-scope profiling before any new materialisation
- use `DuckDB` or SQL-style scans with predicate pushdown
- filter the reporting window at scan time
- project only the fields needed for audit checks, findings, recommendations, governance-support notes, and any later analytical plot
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw detailed source families

The default execution ceiling for this slice is:
- inherited trusted outputs first
- one compact monitoring summary second
- one compact findings output third
- one compact governance-support pack fourth

If a query starts behaving like broad exploratory auditing rather than bounded quality monitoring, stop and narrow it before proceeding.

The required first-pass summary profiling layer is:
- row counts for the inherited provision and maintained-layer bases
- field coverage needed to express the audit checks
- confirmation of which checks can be repeated consistently
- confirmation that one findings-to-recommendation chain can be created from the same bounded lane

## 3. First-Pass Objective

The first-pass objective is:

`build one repeatable data-quality monitoring and audit pack over the bounded Claire House analytical lane, then turn the resulting findings into one recommendation set and one bounded governance-support note`

The proof object is:
- `data_quality_audit_and_governance_support_v1`

The first-pass output family is:
- one audit-scope note
- one data-quality monitoring summary
- one audit findings output
- one recommendation note
- one governance-support note
- one audit-check output
- one caveat and regeneration pack

## 4. Early Scope Gate

Before building either findings or recommendations, run a bounded audit-scope gate.

The first profiling pass must answer:
- which exact Claire House `3.A` and `3.D` outputs define the bounded audit lane?
- what check families can be monitored repeatedly across that lane?
- which earlier control improvement from Claire House `3.D` should now be audited explicitly?
- what downstream quality consequence should be kept in view while auditing the lane?
- what do the row counts, field coverage, and control coverage say about the safe scope of the audit pack before any findings are issued?

Required checks:
- coverage and stability of the inherited trusted provision lane
- coverage and stability of the maintained analytical layer
- continuity of the fields needed for the audit checks
- continuity of the fields needed for the recommendation set
- ability to state one bounded governance-support consequence from the findings

Those checks should be implemented as:
- aggregate-only SQL probes
- inherited compact outputs where available
- no broad row materialisation into memory

Decision rule:
- if the inherited analytical lane is strong enough, proceed with the bounded audit pack
- if not, add one compact audit layer rather than broadening the query footprint

## 5. Candidate Audit Base

The first-pass audit base should stay bounded and explicit.

Each component should have one stated purpose:
- provision-trust layer
  - define what quality conditions are inherited from Claire House `3.A`
- maintained-layer control layer
  - define what quality conditions are inherited from Claire House `3.D`
- monitoring layer
  - define the repeatable checks
- findings layer
  - define what the audit actually found
- recommendation layer
  - define what should be strengthened next

If inherited outputs do not support one of those components cleanly, adapt by narrowing the audit claim rather than stretching earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. inherited-lane confirmation and audit-scope checks
2. monitoring-summary materialisation
3. audit-findings materialisation
4. recommendation derivation
5. governance-support and audit-check packaging

The transformations should not be hidden inside one-off notebook rewriting or manual copy-paste logic.

## 7. Bounded SQL Build Order

### Step 1. Confirm the inherited audit lane and check coverage

Build small aggregate or profile queries only for:
- the trusted provision fields needed for audit coverage
- the maintained-layer control fields needed for repeatable checks
- the protected downstream consequence fields if needed
- audit-support fields needed for findings and recommendations

Goal:
- define the audit pack honestly
- prove that the monitoring and findings question can be answered from the inherited Claire House `3.A` and `3.D` surfaces without broad raw reconstruction

### Step 2. Materialise the monitoring summary

Create one bounded output, for example:
- `data_quality_monitoring_summary_v1`

This output should:
- summarise the key checks in scope
- show current quality status across the bounded lane
- remain compact enough to act as the monitoring surface rather than a broad quality dashboard

### Step 3. Materialise the audit findings output

Create one bounded output, for example:
- `data_quality_audit_findings_v1`

This output should:
- show where the lane is strong
- show where quality or control risk remains
- identify one or more findings that genuinely support recommendations

### Step 4. Materialise the audit-check output

Create one bounded output, for example:
- `data_quality_audit_checks_v1`

This output should:
- confirm the audit pack is internally consistent
- confirm the findings match the monitored checks
- confirm the audit remains tied to the bounded lane

## 8. Findings And Governance-Support Strategy

The quality pack must remain small in conceptual scope but strong in audit posture.

The first-pass findings strategy should answer:
- what exactly was monitored?
- what exactly was found?
- what should be strengthened next?
- how does that help the Data & Insight Manager in a bounded governance or `IG` support sense?

Decision rule:
- every retained field must earn its place in either:
  - monitoring
  - findings
  - recommendation
  - governance-support posture
- if a field does not support one of those purposes, drop it

## 9. Documentation And Control Strategy

The slice is not complete unless another analyst could rerun the audit responsibly.

The documentation and control pack should answer:
- what the audit covered
- what was monitored
- what was found
- what recommendations follow from the findings
- what the governance-support note is for
- what the audit does and does not answer

Create:
- `data_quality_audit_scope_note_v1.md`
- `data_quality_improvement_recommendations_v1.md`
- `governance_support_note_v1.md`
- `data_quality_audit_checklist_v1.md`
- `data_quality_audit_caveats_v1.md`
- `README_data_quality_audit_regeneration.md`
- `CHANGELOG_data_quality_audit.md`

## 10. Reproducibility Strategy

This slice is not complete unless the audit pack and its controls can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL monitoring-summary logic
- versioned SQL audit-findings logic
- versioned SQL audit-check logic
- one compact Python script only if needed for note assembly or later figure render
- one caveat or changelog note

The Python layer must remain:
- compact-output only
- not a substitute for broad analytical processing

That should be strong enough that another analyst could:
- understand the audit scope
- rerun the monitoring summary
- rerun the findings output
- understand the recommendation and governance-support posture

## 11. Planned Deliverables

SQL and shaped data:
- one audit-scope and field-coverage query pack
- one monitoring-summary query
- one findings query
- one audit-check query
- one compact monitoring output
- one compact findings output
- one compact audit-check output

Documentation:
- one audit scope note
- one recommendations note
- one governance-support note
- one audit checklist
- one caveats note
- one regeneration README

Reporting outputs:
- no new reporting pack by default
- analytical plots only if they help clarify the audit truth later

Expected output bundle for the first pass:
- one bounded audit-and-monitoring pack
- one compact findings-and-recommendation pack
- one compact governance-support proof

## 12. What To Measure For The Claim

For this requirement, the strongest measures are monitoring coverage, findings, recommendations, and audit controls rather than analytical novelty.

Primary measure categories:
- number of quality checks monitored across the bounded lane
- number of audit findings produced
- number of recommendations linked to those findings
- number of audit checks passed before issue

Secondary measure categories:
- one completed governance-support note
- regeneration time for the audit pack
- one completed caveat and rerun pack

## 13. Execution Order

1. Finalise the folder structure for this Claire House responsibility lane.
2. Run the inherited-lane and audit-scope gate.
3. Decide the check families for the bounded audit pack.
4. Materialise the monitoring summary.
5. Materialise the audit findings output.
6. Materialise the audit-check layer.
7. Write the recommendations note, governance-support note, checklist, caveats, changelog, and regeneration note.
8. Produce analytical plots only after the audit pack is stable.
9. Write the execution report and final claim surfaces only after the evidence is real.

## 14. Stop Conditions

Stop and reassess if any of the following happens:
- the Claire House `3.A` and `3.D` bases are too thin to support one honest audit pack
- the chosen checks do not produce defensible findings
- the recommendation set starts sounding like a broad governance programme rather than bounded improvement support
- the slice starts drifting into formal governance administration or `IG` ownership
- the query posture starts requiring broad raw-data loads or memory-heavy dataframe work that should have been handled in bounded SQL instead
- the figures start becoming decorative rather than analytical support for the audit truth

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the audit or governance-support claim if needed
- preserve the center of gravity around one bounded monitoring-and-findings pack plus one recommendation and governance-support layer

## 15. What This Plan Is And Is Not

This is:
- a concrete execution plan for the fifth Claire House responsibility slice
- audit-first
- findings-first
- bounded
- aligned to data-quality monitoring, audit, recommendation, and governance support

This is not:
- the execution report
- a broad governance programme
- a whole `IG` administration plan
- a full organisational data-quality framework
- permission to force governance language where the bounded evidence does not support it

The first operational move after this plan should be:
- run the inherited-lane and audit-scope gate and decide whether the Claire House `3.A` and `3.D` outputs can support one honest monitoring-and-audit pack plus one recommendation and governance-support layer without reopening a broad raw analytical rebuild
