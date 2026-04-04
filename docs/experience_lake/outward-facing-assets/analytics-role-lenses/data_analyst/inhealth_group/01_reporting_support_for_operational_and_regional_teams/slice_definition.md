# Reporting Support For Operational And Regional Teams Execution Slice - InHealth Group Data Analyst Requirement

As of `2026-04-04`

Purpose:
- capture the chosen bounded slice for the InHealth requirement around dependable monthly and ad hoc reporting support for operational and regional teams
- keep the note aligned to the actual InHealth responsibility rather than drifting into broad BI ownership, generic dashboarding, or abstract service-improvement language
- preserve the distinction between this InHealth slice and the earlier HUC reporting-cycle slice, even where some reusable reporting logic already exists

Boundary:
- this note is not an accomplishment record
- this note is not a claim that an InHealth-style reporting estate has already been built
- this note captures the chosen slice, why it fits the requirement, which lenses own it, and what the proof burden should be
- execution should begin from governed bounded outputs and already established analytical views where appropriate, rather than re-running broad platform scope unnecessarily

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer lanes over time
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [02_bi-insight-reporting-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\02_bi-insight-reporting-analytics.md)
- [01_operational-performance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\01_operational-performance-analytics.md)
- [09_analytical-delivery-operating-discipline.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\09_analytical-delivery-operating-discipline.md)
- [08_stakeholder-translation-communication-influence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\08_stakeholder-translation-communication-influence.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the InHealth `Data Analyst` expectation around:
- producing monthly reports
- producing ad hoc reports
- supporting operational and regional teams through reporting outputs
- making those outputs timely and usable rather than merely extract-based

This maps directly to the InHealth candidate-profile requirement that the analyst should be able to describe:
- supporting operational services through dependable monthly and ad hoc reporting
- structuring reporting outputs for stakeholders who need timely and usable information
- supporting regional or distributed teams through consistent reporting outputs
- understanding what different stakeholders need from the same dataset

This note exists because that requirement is easy to under-read as generic reporting, when in fact the employer is asking for a narrower but still meaningful form of reporting ownership:
- dependable recurring delivery
- responsive ad hoc support
- operational usefulness
- reporting built from stable logic rather than one-off manual handling

## 2. Lens Stack For This Requirement

The best lens combination for this requirement is:

**Primary**
- `02 - BI, Insight, and Reporting Analytics`

**Strong support**
- `01 - Operational Performance Analytics`

**Support**
- `09 - Analytical Delivery Operating Discipline`

**Optional light support**
- `08 - Stakeholder Translation, Communication, and Decision Influence`

Why this stack fits:

The requirement itself is about:
- dependable monthly reporting
- ad hoc reporting support
- outputs usable by operational and regional teams
- reporting delivery that remains accurate and consistent under recurring use

That makes `02` the main owner because it is the lens for:
- recurring reporting products
- KPI and reporting page structure
- stakeholder-ready reporting outputs
- summary packs and ad hoc cuts built from the same governed logic
- turning governed analytical truth into usable reporting rather than isolated extracts

`01` is the next most important lens because the reporting still has to carry operational meaning. The employer is not asking for empty report production. The reporting must help teams understand programme performance, which means the slice still needs:
- operational KPI logic
- trend reading
- issue visibility
- enough performance interpretation to make the outputs useful to the teams running the service

`09` matters because this requirement is fundamentally about dependable delivery:
- monthly recurring reporting
- ad hoc outputs that do not break consistency
- controlled regeneration
- stable KPI meanings
- release and run discipline

`08` is not a main owner here, but it becomes useful if the slice needs to make the distinction between operational and regional audience usability more explicit. The burden is not persuasion-first storytelling. It is reporting support that people can actually read and use.

So the practical reading is:
- `02` owns the reporting product and output structure
- `01` makes sure the reports actually represent operational performance meaningfully
- `09` makes the reporting cycle repeatable and dependable
- `08` helps where the same governed output has to be legible to more than one audience

Ownership order:
- `02 -> 01 -> 09 -> 08`

Best execution order:
- `01 -> 02 -> 09 -> 08`

That execution order matters because the reporting has to rest on a bounded operational KPI view first, and only then be hardened into recurring and ad hoc reporting with stable control notes and rerun posture.

## 3. Chosen Bounded Slice

The cleanest bounded slice for this InHealth requirement is:

`One monthly operational reporting cycle plus one ad hoc follow-up cut for a single programme lane`

In the fraud-platform analogue, that means:
- select one bounded programme-style lane rather than a broad service estate
- define one monthly reporting pack from governed existing outputs
- produce one ad hoc follow-up cut from the same underlying KPI logic
- keep the KPI family intentionally small
- support two audiences only:
  - operational team
  - regional or programme oversight

To keep the slice concrete and truthful, the monthly reporting cycle should answer one narrow question:
- `what is the current monthly operational position for this bounded lane, and what exception or follow-up cut would an operational or regional team reasonably need next?`

That means the slice should produce:
- one bounded monthly KPI view
- one monthly reporting pack
- one ad hoc follow-up cut from the same governed logic
- one KPI definition note
- one run or release checklist
- one short audience-usage note

This slice is the best analogue for the InHealth requirement because it proves:
- recurring monthly reporting support
- ad hoc reporting responsiveness
- stable reporting logic
- audience usability for operational and regional teams
- dependable reporting discipline rather than one-off manual report creation

## 4. Why This Slice Was Chosen

This slice was chosen because it gives direct room for:
- proving recurring reporting delivery without overclaiming broad reporting ownership
- proving that ad hoc requests can be answered from the same governed reporting base
- showing that one reporting output can support more than one operational audience without redefining the logic each time
- making reporting support look dependable and practical rather than decorative

It also avoids the wrong kinds of drift.

The intention is not to:
- build a wide dashboard estate
- recreate the HUC reporting-cycle slice under a different label
- turn this into a dataset-stewardship slice, which belongs more naturally to InHealth `3.C`
- overemphasise storytelling when the main burden here is dependable reporting support
- produce generic charts that do not materially support the reporting claim

The intention is to prove one sharper statement:
- I can support operational and regional teams through dependable monthly and ad hoc reporting built from stable governed logic, with outputs that remain usable and consistent under recurring use

## 5. Relationship To Earlier Slices

This slice may build upon already established reporting foundations where that is the honest and efficient choice.

Most importantly, it can legitimately reuse ideas from:
- HUC `02_reporting_cycle_ownership`
- HUC `04_issue_to_action_briefing`

But this slice is not a copy of either one.

The difference is:
- HUC `02` proved ownership of a recurring reporting cycle in a broader service-line posture
- HUC `04` proved issue-to-action communication around a bounded operational issue
- InHealth `3.A` is narrower and more support-oriented:
  - dependable monthly reporting
- ad hoc follow-up reporting
  - operational and regional audience usefulness

So reuse is appropriate where it reduces unnecessary work, but the slice still needs its own bounded proof object and its own claim surface.

## 6. Execution Posture

The default execution stack for this slice is:
- `SQL` for bounded KPI shaping, monthly summary preparation, and ad hoc filtered or exception cuts
- `SQL` for bounded KPI shaping, monthly summary preparation, and ad hoc follow-up cuts
- `Python` for compact reporting-pack generation and lightweight figure production where useful
- markdown notes for KPI definitions, audience usage guidance, rerun controls, and reporting caveats

The execution substrate should be:
- governed bounded outputs
- compact extracts already produced by earlier slices where they are suitable
- lightly extended reporting-ready views rather than broad new analytical rebuilds

The reporting posture should remain:
- figure-supportive rather than dashboard-forcing
- compact and operationally useful
- consistent between monthly and ad hoc outputs

## 7. Lens-by-Lens Execution Checklist

### 7.1 Lens 01 - Define the operational reporting logic

This lens matters because the reporting needs to represent a real operational picture, not just table production.

Keep it bounded to `3` or `4` KPI families only:
- volume or pressure
- conversion or progression
- backlog or aging where relevant
- one downstream quality or yield signal if needed

Tasks:
1. Fix the reporting grain as one monthly period plus one comparison baseline.
2. Define one bounded lane and one segment or exception dimension.
3. Build one monthly KPI view from governed logic.
4. Build one ad hoc follow-up cut from the same KPI layer.
5. Write one short `what changed` note.
6. Write one short `what needs attention next` note.

### 7.2 Lens 02 - Build the monthly and ad hoc reporting outputs

This is the main ownership lens for the requirement.

Keep the reporting product to:
- one monthly reporting pack
- one ad hoc follow-up cut

The monthly pack should contain only what the requirement needs:

**Monthly operational summary**
- headline KPIs
- current versus prior movement
- one short operational note

**Audience split**
- one operational view emphasis
- one regional or programme oversight emphasis

The ad hoc follow-up cut should contain:
- one realistic follow-up lens driven by the same monthly reporting logic
- the same KPI meanings as the monthly pack
- only the detail needed to answer a realistic reporting follow-up

Tasks:
1. Define the reporting layout and what belongs in the monthly pack.
2. Keep KPI naming and logic identical between monthly and ad hoc outputs.
3. Make the same governed logic readable to both operational and regional audiences.
4. Add page or usage notes so the outputs can stand without oral walkthrough.

### 7.3 Lens 09 - Make the cycle dependable and rerunnable

This is what turns the slice from one report example into credible reporting support.

Tasks:
1. Stabilise the KPI definitions.
2. Record the period, comparison, and exception rules.
3. Create one report-run checklist.
4. Record one caveat note for what the reporting does and does not answer.
5. Make sure the ad hoc follow-up cut can be regenerated from the same controlled logic as the monthly output.

### 7.4 Lens 08 - Make the outputs clearly usable

This lens is optional support, not the core owner.

Tasks:
1. Write one short audience note explaining what the operational audience should look at first.
2. Write one short audience note explaining what the regional audience should look at first.
3. Add one challenge-response note if the reporting needs a simple `how should this be read?` clarification.

## 8. Suggested Artifact Pack

The minimum credible proof pack for this slice is:
- one reporting requirements note
- one monthly KPI view
- one monthly reporting pack
- one ad hoc follow-up cut
- one KPI definition note
- one audience-usage note
- one report-run checklist

That is enough to prove:
- dependable monthly reporting support
- responsive ad hoc reporting support
- stable reporting logic
- audience usability for operational and regional teams
- controlled regeneration rather than manual report recreation

## 9. Suggested Artifact Names

These names are placeholders, not fixed schema requirements.

Reporting logic and monthly output assets:
- `programme_monthly_reporting_requirements_v1.md`
- `vw_programme_monthly_kpis_v1.sql`
- `programme_monthly_reporting_pack_v1.md`
- `programme_monthly_summary_v1.parquet`

Ad hoc and usage assets:
- `programme_ad_hoc_follow_up_cut_v1.sql`
- `programme_ad_hoc_follow_up_pack_v1.md`
- `programme_kpi_definition_note_v1.md`
- `programme_audience_usage_note_v1.md`

Control assets:
- `programme_reporting_run_checklist_v1.md`
- `programme_reporting_caveats_v1.md`
- `README_programme_reporting_regeneration.md`

## 10. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- one bounded monthly reporting lane has been defined
- one shared KPI layer exists for that reporting lane
- one monthly reporting pack exists
- one ad hoc follow-up cut exists from the same governed logic
- KPI meanings are stable between recurring and ad hoc outputs
- one audience-usage note exists for operational and regional readers
- one rerun or release checklist exists

## 11. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the execution path is defined
- the bounded proof object has been chosen

The correct claim is not:
- that the reporting cycle has already been executed
- that InHealth-style programme reporting has already been implemented
- that operational and regional teams are already using the outputs
- that patient-level dataset stewardship has already been proved through this slice

This note therefore exists to protect against overclaiming while still preserving a fast path toward a defensible claim.

## 12. What To Measure For The Eventual `Y`

For this requirement, the strongest `Y` values are:
- monthly reporting pack delivered from one stable governed logic base
- number of ad hoc reporting follow-up requests answered from the same governed logic
- number of KPI families defined and reused consistently between monthly and ad hoc outputs
- number of release or quality checks passed before issue
- time to regenerate the monthly pack and ad hoc follow-up cut

A strong small `Y` set would be:
- one monthly reporting pack delivered from controlled logic
- `[N]` ad hoc reporting follow-up outputs answered from the same governed base
- `[K]` KPI families reused consistently across monthly and ad hoc reporting outputs
- monthly pack and ad hoc follow-up cut regenerated from controlled logic in `[T]` minutes
- `[M]` release or quality checks passed before output issue

## 13. XYZ Claim Surfaces This Slice Is Aiming Toward

This section is included here because the slice definition needs to preserve the exact claim shape the execution is aiming toward, not just the structural checklist.

### 13.1 Full flagship `X by Y by Z` version

> Supported operational and regional teams through dependable monthly and ad hoc reporting, as measured by delivery of one monthly reporting pack and `[N]` ad hoc follow-up outputs from the same governed logic base, consistent reuse of `[K]` KPI definitions across recurring and follow-up outputs, and regeneration of the reporting pack and follow-up cut in `[T]` minutes, by shaping bounded operational performance data into a controlled monthly reporting cycle and responsive follow-up outputs that remained accurate, usable, and repeatable.

### 13.2 Shorter recruiter-readable version

> Delivered dependable monthly and ad hoc operational reporting, as measured by stable KPI logic, reusable follow-up reporting from the same governed base, and repeatable regeneration from controlled reporting views, by turning governed programme data into recurring and follow-up reporting outputs that operational and regional teams could use confidently.

### 13.3 Closest direct response to the InHealth requirement

> Supported operational and regional teams through accurate monthly and ad hoc reporting, as measured by reusable KPI definitions, consistent recurring and follow-up outputs, and controlled rerun capability, by shaping governed reporting views into dependable programme reporting and responsive follow-up cuts rather than one-off manual extracts.

## 14. Immediate Next-Step Order

The correct build order remains:
1. define the bounded monthly KPI and comparison layer
2. shape the monthly reporting pack from that governed logic
3. build one ad hoc follow-up cut from the same reporting base
4. add usage notes, caveats, and rerun controls

That order matters because it prevents the slice from collapsing into ad hoc output production without a stable recurring reporting core underneath it.
