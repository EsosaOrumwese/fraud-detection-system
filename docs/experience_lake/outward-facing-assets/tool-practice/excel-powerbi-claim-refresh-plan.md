# Excel and Power BI Claim Refresh Plan

As of `2026-04-08`

Purpose:

- tie the new `excel-mcp` and `powerbi-mcp` tooling to the actual outward-facing claims already made in resumes, recruiter-call notes, and responsibility-lens work
- keep the practice surface honest: stronger on governed reporting-product design, KPI logic, validation, and stakeholder-ready packs than on live enterprise admin claims
- define the analytical proof surfaces that should be rebuilt with Excel- and Power-BI-shaped outputs so those claims stay interview-defensible

## 1. What The Repeated Claims Actually Are

Across the outward-facing material, the recurring tool-shaped claims are not just tool names. They imply repeatable behaviours:

- `Excel` for reporting, checking, reconciliation, presentation, and dependable recurring output control
- `Power BI` for dashboards, stakeholder-facing reporting, KPI packaging, decision-support views, and mixed-source insight presentation
- `DAX` for reusable semantic measures rather than one-off spreadsheet arithmetic
- `Power Query M` for shaped, repeatable load logic rather than manual copy-and-paste assembly

The strongest recurring resume language appears in:

- [resume.txt](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/resume/job_ad_04_claire_house/resume.txt)
- [resume.txt](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/resume/job_ad_05_hertfordshire_partnership_university_nhs_ft/resume.txt)
- [resume.txt](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/resume/job_ad_06_the_money_and_pensions_service/resume.txt)
- [resume.txt](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/resume/job_ad_11_guys_and_st_thomas_nhs_foundation_trust/resume.txt)

The strongest responsibility lens for this tooling is:

- [02_bi-insight-reporting.md](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/analytics-role-lenses/02_bi-insight-reporting.md)

## 2. What You Should Be Ready To Defend In Interview

If an interviewer pushes on the claimed tools, the realistic probe areas are:

- how you move from governed source data to a reporting-ready workbook or dashboard model
- how you decide which KPIs belong on executive, operational, or analyst-facing views
- how you keep metric definitions stable across pages and packs
- how you validate and caveat reporting outputs before wider circulation
- how you use Excel for bounded QA, reconciliation, and pack assembly
- how you use Power BI for semantic measures, page structure, filters, drill paths, and audience-specific presentation

The current repo can support strong answers on those topics.

It should not overclaim:

- enterprise-wide Power BI administration
- fully automated tenant publishing
- live Microsoft 365 governance ownership
- deep XMLA / Tabular Editor model engineering

## 3. How The New MCP Servers Help

`excel-mcp` is for:

- workbook inspection
- sheet reads and writes
- workbook profiling
- governed KPI-pack generation
- Microsoft Graph workbook range access when a token is available

`powerbi-mcp` is for:

- workspace, dataset, report, and page metadata inspection
- refresh-history inspection
- semantic blueprint generation from governed repo datasets
- generated `DAX`, Power Query `M`, page specs, theme files, and QA notes

This means Codex can now help produce analytical proof surfaces in tool-shaped forms rather than only as markdown execution reports.

## 4. First Proof Surfaces To Rebuild With These Tools

These are the best first candidates because they already align with the strongest claimed responsibilities.

### 4.1 HUC

Base slice:

- [execution_report.md](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/analytics-role-lenses/data_analyst/huc/01_multi_source_service_performance/execution_report.md)

Tool-shaped rebuild:

- Excel recurring KPI pack
- Power BI operational trend and discrepancy blueprint

Why:

- multi-source service performance
- stable KPI family
- operational and leadership reporting

### 4.2 Claire House

Resume anchor:

- [resume.txt](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/resume/job_ad_04_claire_house/resume.txt)

Tool-shaped rebuild:

- Excel QA and release-control workbook
- Power BI leadership plus external-style reporting blueprint

Why:

- scheduled and ad hoc reporting
- board-pack style outputs
- data-quality and governance-linked reporting

### 4.3 Money and Pensions Service

Resume anchor:

- [resume.txt](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/resume/job_ad_06_the_money_and_pensions_service/resume.txt)

Tool-shaped rebuild:

- Excel mixed-evidence tracking workbook
- Power BI mixed-source dashboard blueprint with risk and framework pages

Why:

- mixed-source dashboarding
- KPI and framework measurement
- easy-to-digest stakeholder-facing insight

### 4.4 South Tyneside

Base slice:

- [execution_report.md](c:/Users/LEGION/Documents/Data%20Science/Python%20%26%20R%20Scripts/fraud-detection-system/docs/experience_lake/outward-facing-assets/analytics-role-lenses/data_analyst/south_tyneside_and_sunderland_nhs_foundation_trust/01_bi_reporting_product_and_reporting_platform_support/execution_report.md)

Tool-shaped rebuild:

- Excel anomaly-control workbook
- Power BI trusted-output and exception-review blueprint

Why:

- BI reporting-product support
- anomaly handling
- trusted-output control

## 5. Practical Interview Drill Loop

For each rebuilt proof surface:

1. Use `powerbi_generate_semantic_blueprint` to produce the table roles, measures, page specs, and `M` logic.
2. Use `excel_build_reporting_pack` to produce the workbook equivalent of the same governed lane.
3. Compare the Excel pack and Power BI blueprint and explain:
   - why the KPI family is stable
   - why the page structure fits the audience
   - what the trust conditions are
   - what caveats remain
4. Practice defending where the claim stops.

That last point matters. Strong interview answers here come from sounding exact rather than inflated.
