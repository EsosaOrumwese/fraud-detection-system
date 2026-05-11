# Dashboard Integration and Decision Support Execution Slice - Midlands Data Scientist Requirement

As of `2026-04-03`

Purpose:
- capture the chosen bounded slice for the Midlands requirement around dashboard integration and decision support
- keep the note aligned to the actual reporting-and-decision-support responsibility rather than drifting back into model-building or generic BI tooling talk
- preserve the distinction between this slice and the earlier predictive, governed-model, and analytical-product slices

Boundary:
- this note is not an accomplishment record
- this note is not a claim that a full Power BI estate or enterprise BI programme has already been implemented
- this note captures the chosen slice, why it fits the requirement, which lenses own it, and what the proof burden should be
- execution should work from governed data extracts or local bounded views rather than broad platform reruns

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [02_bi-insight-reporting-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\02_bi-insight-reporting-analytics.md)
- [08_stakeholder-translation-communication-influence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\08_stakeholder-translation-communication-influence.md)
- [04_analytics-engineering-data-product.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\04_analytics-engineering-data-product.md)
- [07_advanced-analytics-data-science.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\07_advanced-analytics-data-science.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the Midlands `Data Scientist` expectation around:
- integrating analytical outputs into dashboards and reporting surfaces
- making model and cohort outputs understandable to non-technical users
- supporting decision-making through clear KPI presentation, explanation, and visual packaging
- operationalising analytical work into stakeholder-facing decision-support products rather than leaving it as technical analysis only

The real meaning of this requirement in the fraud-platform world is:
- not stopping at model or cohort production
- not leaving prioritisation logic trapped in notebooks or technical notes
- turning governed analytical outputs into a reusable decision-support pack that executives, operations users, and reviewers can follow
- doing that without becoming tool-locked to Power BI before the reporting logic and audience structure are already sound

This note therefore exists to define one bounded slice that proves dashboard integration and decision support rather than vendor-first BI activity.

## 2. Lens Stack For This Requirement

The main lens stack for this requirement is:

**Primary owner**
- `02 - BI, Insight, and Reporting Analytics`

This is the main owner because the responsibility is about:
- shaping governed truth into dashboard and reporting surfaces
- choosing page structure and KPI presentation
- designing interpretable reporting outputs for different audiences
- turning analytical logic into reusable reporting logic rather than passive plots

**Co-primary support**
- `08 - Stakeholder Translation, Communication, and Decision Influence`

This is the second major owner because the responsibility is not only to show charts. It is also to:
- make analytical outputs understandable to non-technical readers
- connect model or cohort outputs to operational meaning
- frame caveats and action notes
- turn a reporting pack into a decision-support surface rather than a passive display

**Strong support**
- `04 - Analytics Engineering and Analytical Data Product`

This lens matters because the reporting pack should not sit on raw extracts. It owns:
- reporting-ready analytical views
- KPI-ready outputs
- reusable dimensional slices
- stable product layers that the reporting surface can trust

**Fourth lens for this slice**
- `07 - Advanced Analytics and Data Science`

This is the preferred fourth lens here because the chosen slice is model-led rather than purely operational-KPI-led. It provides:
- risk bands
- cohort logic
- prioritisation ordering
- explanation summaries worth surfacing in the dashboard pack

The practical mapping is:
- `02` owns the dashboard and reporting product
- `08` owns whether the pack is understandable and decision-useful
- `04` owns the reporting-ready substrate underneath
- `07` supplies the model and cohort outputs being operationalised

Ownership order:
- `02 -> 08 -> 04 -> 07`

Best execution order:
- `04 -> 07 -> 02 -> 08`

That execution order matters because the reporting-ready layer and analytical outputs should exist before the dashboard pack is composed and annotated.

## 3. Chosen Bounded Slice

The bounded slice chosen for this requirement is:

`A flow-level prioritisation and operations dashboard pack built from governed model and cohort outputs`

The proof object is:

`dashboard_decision_support_v1`

This means:
- one analytical unit at `flow_id`
- one decision question:
  - which suspicious flows or cohorts deserve attention first, and why?
- one compact dashboard pack with `3` pages or panels only
- one supporting decision brief for non-technical readers

The pack should surface:
- risk and cohort overview
- workflow, conversion, and backlog view
- explanation, drill-through, and action summary

Deployment meaning for this slice:
- not a full BI platform rollout
- not a commitment to Power BI first
- instead, a compact, regenerable, reporting-grade dashboard pack built from governed outputs and suitable for later porting into Power BI or an equivalent BI surface if needed

## 4. Why This Slice Was Chosen

This is the cleanest bounded proof for the requirement because it allows direct evidence of:
- model-to-reporting operationalisation
- audience-specific reporting design
- KPI consistency across views
- dashboard-style packaging of governed analytical outputs
- clear action framing for non-technical users

Just as importantly, it avoids the wrong kinds of drift.

The intention is not to:
- force Power BI as the proof before the reporting logic is actually sound
- produce a dense analyst dump and call it a dashboard
- repeat the earlier model slice and simply add a couple of charts
- claim a broad reporting estate when only one bounded decision-support pack is being built

The intention is to prove one sharper statement:
- I can turn governed model and cohort outputs into a compact reporting and decision-support product that different audiences can actually use

## 5. Execution Posture

The default execution stack for this slice is:
- `SQL` for reporting-ready base, summary, and drill-through views
- `Python` for compact dashboard-pack generation, annotated figures, scorecards, and briefing surfaces
- markdown briefing notes as the main audience-translation surface

The execution substrate should be:
- governed local extracts
- bounded local views
- reporting-ready analytical outputs derived from the governed world

The default local working assumption is that execution can begin from a bounded run such as:
- `runs/local_full_run-7`

That should still be treated as:
- a bounded governed extract
- not the whole world
- not permission to overclaim enterprise dashboard coverage

## 6. Lens-by-Lens Execution Checklist

### 6.1 Lens 04 - Build the reporting-ready product layer

This is the preparation layer that feeds the reporting pack.

1. Fix the analytical grain at `flow_id`.
2. Create one reporting-ready base view joining:
- flow context
- risk band
- cohort label
- case and outcome signals
- bounded time fields
- compact drill-through dimensions
3. Create one executive-summary view with headline KPI fields already shaped.
4. Create one drill-through view with enough row-level detail for explanation.
5. Write one short product contract:
- grain
- key fields
- allowed uses
- caveats

### 6.2 Lens 07 - Generate the analytical outputs worth surfacing

This lens supplies the model and cohort outputs that make the pack more than a static KPI wall.

1. Reuse the bounded flow-level model or cohort outputs already developed.
2. Produce only these analytical outputs:
- one risk band
- one cohort label
- one prioritisation score or ordering
3. Create one compact cohort summary:
- high-risk / high-yield
- high-burden / low-yield
- fast-converting / slow-converting
4. Add one short explanation table:
- main drivers of the high-risk group
- where operational value concentrates
- where burden is high but value is weak

### 6.3 Lens 02 - Build the dashboard and reporting pack

This is the main reporting owner.

For this bounded slice, the pack should contain only `3` pages:

**Page 1 - Executive overview**
- headline risk and workload KPIs
- one trend panel
- one cohort-concentration panel
- one short `what changed` note

**Page 2 - Workflow and prioritisation**
- conversion, throughput, or backlog view
- risk-band or cohort comparison
- one prioritisation table

**Page 3 - Explanation and drill-through**
- one detailed cohort or segment breakdown
- one explanation panel for why that group matters
- one drill-through table or filtered row set

Support tasks:
1. define KPI names and meanings
2. keep the same metric definitions across all pages
3. decide what each audience should see first
4. add page-level explanation notes

### 6.4 Lens 08 - Make it understandable and decision-ready

This is what turns the reporting pack into decision support.

1. Write one executive briefing note:
- what changed
- why it matters
- what should be monitored next
2. Write one operations note:
- which segment or cohort needs attention
- what the dashboard suggests should happen
3. Write one challenge-response note:
- why trust this metric?
- what does this cohort include?
- what caveats apply?
4. Annotate the dashboard pack so a non-technical reader can follow it without oral explanation.

## 7. Page Structure For This Slice

The dashboard pack should stay compact and deliberate.

The required page split is:
- `executive_overview`
- `workflow_and_prioritisation`
- `explanation_and_drillthrough`

This is preferred over a larger page estate because:
- it keeps the reporting pack audience-readable
- it forces KPI discipline
- it makes the pack easier to regenerate and defend
- it stops the slice from turning into a broad reporting programme

If the pack starts growing beyond three pages, the slice has likely drifted.

## 8. Minimum Proof Pack

The smallest credible proof pack for this requirement is:
- one reporting-ready base SQL view
- one risk or cohort summary view
- one 3-page dashboard pack
- one KPI definitions note
- one executive brief
- one operations or action note
- one challenge-response note

Suggested artefact names:
- `vw_flow_dashboard_base_v1.sql`
- `vw_flow_dashboard_summary_v1.sql`
- `vw_flow_dashboard_drillthrough_v1.sql`
- `flow_dashboard_product_contract_v1.md`
- `flow_risk_band_summary_v1.sql`
- `flow_cohort_summary_v1.sql`
- `dashboard_pack_v1`
- `dashboard_kpi_definitions_v1.md`
- `dashboard_executive_brief_v1.md`
- `dashboard_operations_note_v1.md`
- `dashboard_challenge_response_v1.md`

## 9. Definition Of Done

This slice should be considered complete when:
- one reporting-ready analytical layer exists
- one model or cohort output has been surfaced into a dashboard pack
- the pack has distinct executive, operational, and drill-through views
- KPI definitions are stable and documented
- a non-technical reader can understand what changed and why it matters
- at least one action or prioritisation recommendation is made explicit
- the pack can be regenerated from the same governed inputs

## 10. XYZ Claim Surfaces This Slice Is Aiming Toward

The strongest eventual claim shape for this slice is:

> Operationalised model and cohort outputs into decision-support reporting, as measured by delivery of `[N]` audience-specific dashboard views, consistent reuse of `[K]` governed KPI definitions across the pack, and regeneration of the reporting surfaces from controlled analytical views in `[T]` minutes, by shaping model-ready results into reporting-ready SQL views, building a compact executive, operational, and drill-through dashboard pack, and adding annotated briefs and action notes for non-technical stakeholders.

A shorter recruiter-readable version is:

> Turned governed analytical outputs into dashboard and decision-support products, as measured by consistent KPI reuse across multiple views and completion of executive, operational, and drill-through reporting surfaces, by packaging model and cohort results into reporting-ready views and annotated dashboard summaries for non-technical users.

A closer direct-response version is:

> Integrated analytical outputs into stakeholder-facing decision-support reporting, as measured by reusable dashboard views, documented KPI logic, and action-oriented summary notes for different audiences, by translating governed model and cohort outputs into clear reporting surfaces and explanation packs rather than leaving them as technical analysis only.

These claim shapes are aiming to answer the real employer question:
- can this person integrate analytical outputs into dashboards and decision-support reporting rather than leaving them as technical analysis only?

That means the eventual `Y` should focus on:
- audience-specific reporting views
- consistent KPI reuse
- regenerable reporting outputs
- action-oriented briefing and challenge-response material

The slice is strongest if the later claim can point to evidence such as:
- one compact multi-page reporting pack delivered
- shared KPI definitions reused across all pages
- executive, operational, and drill-through views completed
- regeneration from governed reporting views completed successfully
- action notes and challenge-response material completed alongside the visuals

The slice should not be used to claim:
- full enterprise BI rollout
- vendor-specific Power BI mastery from this slice alone
- a full reporting estate across every analytical output in the platform

## 11. Next Document

The next document for this slice should be:
- `execution_plan.md`

That plan should tie this definition to the actual bounded outputs already available from the governed modelling and cohort work, decide the exact reporting views to build, pin the KPI set and page structure, and define how the dashboard pack will be regenerated from the underlying governed views.
