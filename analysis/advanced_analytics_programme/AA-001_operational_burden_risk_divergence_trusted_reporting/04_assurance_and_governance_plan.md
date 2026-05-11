# AA-001 Assurance and Governance Plan

## Purpose

This document defines the assurance, reconciliation, caveat, and responsible-use controls for `AA-001`.

The project’s value depends on trust. A reporting product over a high-volume decisioning service is only useful if stakeholders can understand which metrics are reliable, which metrics need caveats, and which interpretations are not permitted.

This plan ensures that QA and governance are not treated as final polish. They are part of the delivery method.

## Assurance Principles

The following principles are binding for execution.

| Principle | Meaning |
|---|---|
| Grain before metric | Every metric must declare whether it counts flows, events, cases, case events, sessions, entities, or exposure. |
| Reconcile before reporting | Source-to-output counts must be checked before stakeholder-facing tables are produced. |
| Caveat near the claim | Limitations must appear where the metric or finding is used, not only in an appendix. |
| Separate labels | Truth, bank view, campaign marker, and case lifecycle must remain distinct. |
| Prove joins | Joins must use the contract keys or a documented alternative proven during execution. |
| Reject unsafe metrics | A metric that cannot declare its denominator, source, or caveat should not enter the reporting pack. |
| Document realism concerns | If the synthetic operating world creates unrealistic analytical limits, those limits must be recorded rather than hidden. |

## QA Control Register

The following controls are required before the final reporting pack.

| Control ID | Control | Purpose | Required evidence |
|---|---|---|---|
| QA-001 | Source inventory check | Confirm the exact surfaces, paths, row counts, and schemas used. | Source inventory extract and source reconnaissance note. |
| QA-002 | Flow anchor uniqueness check | Confirm the mart base is one row per flow. | Duplicate-count check on flow key. |
| QA-003 | Event-to-flow grammar check | Prevent event rows from being misused as flow counts. | Event rows per flow distribution and exception table. |
| QA-004 | Flow anchor to arrival join check | Confirm arrival/routing context joins safely to flow anchors. | Join coverage and unmatched-key counts. |
| QA-005 | Arrival to entity join check | Confirm entity handles attach at arrival grain without duplicate inflation. | Join coverage, duplicate profile, row inflation check. |
| QA-006 | Truth join coverage check | Confirm truth labels cover the intended flow universe. | Matched/unmatched flow counts and label distribution. |
| QA-007 | Bank view join coverage check | Confirm bank view covers the intended flow universe. | Matched/unmatched flow counts and bank-label distribution. |
| QA-008 | Truth-bank reconciliation check | Confirm truth-bank cells sum to the expected flow universe. | Truth-bank matrix and total reconciliation. |
| QA-009 | Case-to-flow bridge proof | Confirm case timeline can be safely summarized at flow grain. | Bridge evidence, unmatched cases/flows, duplication check. |
| QA-010 | Case timeline rollup check | Confirm case-event rows roll into case and flow summaries correctly. | Case-event totals, case counts, case-depth distribution. |
| QA-011 | Structural null check | Distinguish expected nullness from data-quality defects. | Null profile with physical/virtual/campaign structural rules. |
| QA-012 | Reporting-period boundary check | Handle April spillover or period-edge rows explicitly. | Boundary counts, timestamp ranges, reporting rule. |
| QA-013 | Session leakage check | Prevent completed-session facts from being treated as live-safe. | Field classification and rejected-use notes. |
| QA-014 | Approximation caveat check | Prevent approximate distinct counts or quantiles from being presented as exact. | Metric caveat flags and method notes. |
| QA-015 | Dashboard export reconciliation | Confirm dashboard-ready extracts match validated metrics. | Export row counts and metric totals compared to metric layer. |

## Canonical Assurance Artifacts

The canonical QA deliverable is:

- `execution/reports/qa_assurance_pack.md`

That report is the sign-off document. It should collect or reference the source checks, join reconciliation, metric reconciliation, case-bridge proof, structural-null checks, boundary checks, leakage checks, caveats, anomalies, and final assurance verdict.

Supporting artifacts are:

| Artifact | Role |
|---|---|
| `execution/sql/qa_join_reconciliation.sql` | Reproducible SQL for join and coverage checks. |
| `execution/sql/qa_metric_reconciliation.sql` | Reproducible SQL for metric totals and denominator checks where needed. |
| `execution/extracts/join_reconciliation_*` | Compact join evidence tables. |
| `execution/extracts/data_quality_checks.*` | Machine-readable QA check results used by the assurance pack. |
| `execution/reports/caveat_register.md` | Running caveat register. |
| `execution/reports/anomaly_register.md` | Running anomaly register. |
| `execution/reports/realism_concern_register.md` | Synthetic realism concerns and treatment. |

Older or narrower notes such as a standalone join reconciliation note should not become competing QA authorities. If created during execution, they should be treated as supporting notes and summarized into `qa_assurance_pack.md`.

## Source Assurance

Execution must begin with source assurance.

For each in-scope surface, record:

- physical path
- file format
- row count
- column count
- relevant lineage columns
- time columns
- key columns
- expected grain
- known caveats from prior investigation

If a source surface has a schema mismatch or missing key, execution must pause that source’s use until the issue is classified.

Possible classifications:

- acceptable schema variation
- missing optional field
- blocking missing field
- grain mismatch
- unresolved source defect

## Join Assurance

Join assurance must follow the binding join keys from `02_data_scope_and_metric_contract.md`.

Each join check must report:

- left row count
- right row count
- matched row count
- unmatched left rows
- unmatched right rows where relevant
- duplicate keys on each side
- row-count change after join
- whether the join is approved, caveated, or rejected

The project should not rely on visual inspection or a small sample to approve a join.

## Case Timeline Assurance

The case timeline requires special treatment because it is case-centric.

Before `case_summary_by_flow` is used, execution must prove:

- how case records connect to flows
- whether one case can map to one flow or multiple flows
- whether one flow can map to one case or multiple cases
- whether case-event counts reconcile after rollup
- whether case depth is measured per case, per flow, or both

If the case-to-flow bridge is not proven, case timeline analysis must remain case-grain or case-event-grain and must not be merged into the flow mart.

## Metric Assurance

Every stakeholder-facing metric must pass the metric definition requirements from `02_data_scope_and_metric_contract.md`.

Metric approval statuses:

| Status | Meaning |
|---|---|
| Approved | Metric has source, numerator, denominator, grain, caveat, and reconciliation evidence. |
| Caveated | Metric is useful but has a stated limitation that must travel with it. |
| Rejected | Metric is misleading, under-defined, unreconciled, or unsafe for stakeholder reporting. |
| Deferred | Metric may be useful later but is not needed or not ready for v0. |

Rejected metrics should remain in the record. The rejection is part of the assurance evidence because it shows that the reporting product was not built by accepting every requested number.

## Caveat Register

The project must maintain a caveat register during execution.

Each caveat should include:

- caveat ID
- affected metric or table
- source surface
- issue type
- explanation
- severity
- stakeholder impact
- reporting treatment
- owner or next action

Initial caveat categories:

| Category | Example |
|---|---|
| Grain caveat | Event rows are not flow counts. |
| Label caveat | Bank view is not ground truth. |
| Structural-null caveat | `campaign_id` nullness can represent non-campaign traffic. |
| Offline-only caveat | Completed-session fields are not live-safe. |
| Boundary caveat | Some response events may spill over the nominal reporting window. |
| Realism caveat | Synthetic fraud prevalence or fraud amount profile may limit stakeholder-facing fraud conclusions. |
| Approximation caveat | Approximate distinct counts cannot prove exact set equality. |

## Responsible-Use Classification

Fields and derived metrics must be classified according to permitted use.

| Classification | Permitted use | Prohibited use |
|---|---|---|
| Live-compatible | Retrospective reporting and possible future live-feature consideration if sourced from online/as-of state. | Treating offline copies as proof of live availability without platform validation. |
| Offline-only | Retrospective analysis, reporting, model evaluation, and audit context. | Live decision-time scoring or real-time intervention logic. |
| Reporting-only outcome | Supervised evaluation, operational review, dashboard reporting. | Live scoring input. |
| Caveated reporting | Stakeholder reporting with visible caveat. | Unqualified headline metric. |
| Rejected for reporting | Internal investigation record only. | Dashboard, briefing, or KPI use. |

## Label Governance

The project must enforce label separation.

| Label-like field | Governance rule |
|---|---|
| `fraud_flag` | Treat as overlay/campaign marker, not final truth. |
| Truth label | Treat as supervised outcome surface, not institutional action. |
| Bank view | Treat as institutional judgement/action, not ground truth. |
| Case timeline | Treat as operational lifecycle, not standalone label truth. |
| Campaign ID | Treat as campaign grouping marker; semantics require catalogue or documented context. |

Any analysis that uses the word "fraud" must state which field or concept it means.

## Structural Null Governance

Nulls must be interpreted through operating logic before being called defects.

Required checks:

- `site_id` and `edge_id` physical/virtual route pattern
- `campaign_id` structural non-campaign nullness
- optional fields by source surface
- impossible-null fields required for keys or mart joins

Structural nulls should be documented in the data dictionary and dashboard caveats so BI users do not create false data-quality incidents.

## Realism Concern Register

Because the platform uses a synthetic operating world, the project must record realism concerns that affect interpretation.

A realism concern does not automatically invalidate the project. It becomes a problem when it prevents a defensible stakeholder conclusion.

Each realism concern should include:

- concern
- observed evidence
- affected analyses
- severity
- whether the project can still proceed
- recommended treatment

Examples already anticipated from investigation:

- very low explicit fraud marker prevalence may limit model-building or fraud-rate conclusions
- small fraud amounts may weaken stakeholder-facing claims about financial fraud exposure
- synthetic case or bank behaviour may be useful for operational analytics but still needs caveats

## Anomaly Register

The anomaly register is for observed issues that may be data defects, expected structural behaviour, or analysis risks.

Each anomaly should include:

- anomaly ID
- surface
- description
- evidence
- classification
- severity
- decision
- follow-up

Valid classifications:

- expected structural behaviour
- reporting caveat
- source defect
- join defect
- metric defect
- synthetic realism concern
- unresolved

## Dashboard Governance

Dashboard-ready tables and visuals must follow these rules:

- show grain and denominator in the table metadata or dashboard documentation
- separate flow, event, case, and case-event counts
- do not label `fraud_flag` as final fraud truth
- do not hide caveats in a separate technical document only
- do not expose rejected metrics
- do not use completed-session fields in live-safe pages
- keep executive summaries plain enough for senior stakeholders but traceable enough for analysts

## Sign-Off Gates

The project should use the following gates.

| Gate | Required before passing |
|---|---|
| Gate 1: Scope signed off | Planning docs complete and interface boundary confirmed. |
| Gate 2: Source signed off | Source inventory, schemas, row counts, and grains documented. |
| Gate 3: Join signed off | Required joins proven or rejected with reasons. |
| Gate 4: Mart signed off | Flow mart uniqueness and source-to-target mapping validated. |
| Gate 5: Metric signed off | P0 metrics defined, computed, reconciled, and caveated. |
| Gate 6: Analysis signed off | Burden/divergence findings tied to evidence and caveats. |
| Gate 7: Reporting signed off | Dashboard-ready extracts reconcile to metric layer and include caveats. |
| Gate 8: Briefing signed off | Stakeholder briefing distinguishes findings, limitations, and recommendations. |

## Assurance Deliverables

The assurance work should produce:

- source inventory
- schema profile
- join reconciliation outputs
- metric definition pack
- QA checklist
- caveat register
- anomaly register
- responsible-use classification table
- realism concern register
- dashboard export reconciliation
- `qa_assurance_pack.md` as the canonical final assurance summary

## Assurance Conclusion

The assurance plan exists to make the final reporting product defensible.

For `AA-001`, correctness is not only whether the SQL runs. Correctness means the data is joined at the right grain, the metrics say what they claim to say, caveats are visible, and stakeholders are prevented from drawing conclusions the data cannot support.
