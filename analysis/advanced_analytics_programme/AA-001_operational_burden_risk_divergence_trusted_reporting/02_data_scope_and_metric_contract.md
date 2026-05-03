# AA-001 Data Scope and Metric Contract

## Purpose

This document defines the data scope, grain rules, join rules, and first-pass metric contract for `AA-001`.

The project is not allowed to treat the interface estate as a pile of interchangeable tables. Each surface exists at a specific operational grain and answers a specific kind of question. The reporting model must preserve those meanings or it will create false workload, false risk, or false quality conclusions.

The contract here is the guardrail for all later SQL, Python, notebooks, dashboard-ready tables, QA checks, and stakeholder briefing material.

## Analytical Boundary

`AA-001` uses the downstream interface estate available to the advanced analytics function.

The project may use earlier investigation notes to understand the operating meaning of surfaces, but the reporting product itself must be built from the interface-pack data rather than hidden Data Engine authoring artifacts.

The pinned local source is:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`](../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1)

## In-Scope Source Surfaces

The initial project scope is limited to downstream operational and reporting surfaces that can support burden, divergence, quality, and responsible-use analysis.

| Surface group | Surface | Primary grain | Project role |
|---|---|---:|---|
| Arrival context | `arrival_events_5B` | Arrival row | Route, channel, zone, time, physical/virtual endpoint context. |
| Behavioural streams | `s2_event_stream_baseline_6B` | Event row | Baseline two-event authorization grammar and event-time profile. |
| Behavioural streams | `s3_event_stream_with_fraud_6B` | Event row | Post-overlay event stream used to inspect what changed after the fraud overlay. |
| Flow anchors | `s2_flow_anchor_baseline_6B` | Flow row | Baseline flow-level bridge from thin event stream to merchant, amount, entity, IP, and arrival context. |
| Flow anchors | `s3_flow_anchor_with_fraud_6B` | Flow row | Post-overlay flow-level bridge including amount and overlay changes. |
| Entity context | `s1_arrival_entities_6B` | Arrival/entity binding row | Entity handles attached to arrivals: party, account, instrument, device, IP, session. |
| Session context | `s1_session_index_6B` | Completed session row | Offline completed-session reconstruction; useful for reporting context, unsafe as live-time feature source. |
| Truth products | `s4_flow_truth_labels_6B` | Flow row | Final supervised truth label surface. |
| Truth products | `s4_flow_bank_view_6B` | Flow row | Institutional judgement/action surface, not ground truth. |
| Truth products | `s4_event_labels_6B` | Event row | Event-level label alignment where event-grain analysis is required. |
| Truth products | `s4_case_timeline_6B` | Case-event row | Operational case history and case-handling burden. |

## Out-of-Scope Source Surfaces for v0 Reporting

These sources are not part of the v0 stakeholder reporting contract unless a later decision explicitly promotes them.

| Source type | Status | Reason |
|---|---|---|
| Data Engine authoring artifacts | Out of scope for reporting inputs | They belong to world construction, not the operating interface available to the analytics team. |
| Hurdle/NB coefficients, priors, RNG streams | Out of scope for stakeholder reporting | Useful for engine investigation, but not valid operational reporting inputs. |
| Hidden catalogues and builder policies | Out of scope for stakeholder reporting | They expose the constructed world rather than the operating estate. |
| New ML model outputs | Out of scope for v0 | The project is a trusted analytics/reporting delivery, not a model-build project. |
| Platform runtime logs outside the interface estate | Out of scope for v0 | May support a future platform observability project, but not the first reporting mart. |

## Grain Contract

The reporting model must declare the grain of every source, intermediate table, and metric.

| Grain | Meaning | Common surfaces | Reporting risk |
|---|---|---|---|
| Arrival | One arrival/routing context row. | `arrival_events_5B`, `s1_arrival_entities_6B` | Arrival context is not automatically the same as a scored flow unless joined through the correct anchor. |
| Event | One authorization event row. | `s2_event_stream_baseline_6B`, `s3_event_stream_with_fraud_6B`, `s4_event_labels_6B` | Event rows can double-count flows because request and response are separate rows. |
| Flow | One authorization flow. | `s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B` | Flow is the preferred base for stakeholder burden/divergence reporting. |
| Case | One case attached to a flow or operational review object. | Derived from `s4_case_timeline_6B` | Case counts must not be confused with case-event counts. |
| Case event | One lifecycle event inside a case. | `s4_case_timeline_6B` | Case-event volume measures workload depth, not case count. |
| Session | One completed session. | `s1_session_index_6B` | Completed-session facts are offline-only and can leak future knowledge if used as live-time features. |
| Entity handle | A party/account/instrument/device/IP/session identifier attached to an arrival or flow. | `s1_arrival_entities_6B`, flow anchors | Entity reuse and concentration require careful denominators; entity counts are not flow counts. |

## Canonical Reporting Grain

The main analytical mart for `AA-001` must be flow-grain.

The intended primary table is:

> `flow_operational_mart`: one row per flow, carrying flow anchor context, truth label, bank view, case summary, safe arrival/channel/route context, selected entity handles, and documented caveats.

Flow grain is the correct reporting base because the central business problem asks how operational handling and eventual truth relate to the transaction/authorization unit that later becomes a case or risk judgement object.

Event-grain, case-event-grain, session-grain, and entity-grain views may exist, but they must either:

- roll up into flow-grain fields before entering the main mart, or
- remain separate supporting tables with explicit grain labels.

## Required Derived Tables

The following tables are the minimum expected data model for execution.

| Table | Grain | Purpose |
|---|---:|---|
| `flow_operational_mart` | Flow | Main reporting and analysis base. |
| `case_summary_by_flow` | Flow | Rolls case timeline into case coverage, depth, path, and burden fields. |
| `truth_bank_alignment_summary` | Flow-group aggregate | Summarizes truth/bank agreement and disagreement cells. |
| `case_burden_metrics` | Segment aggregate | Summarizes case coverage, case depth, and case-event burden by valid segments. |
| `data_quality_checks` | Check row | Reconciliation and caveat outputs used for QA sign-off. |
| `dashboard_export_*` | Dashboard-specific grain | Dashboard-ready tables with grain and filters declared in each export. |

## Join Contract

Joins must be designed around lineage and grain, not convenience.

### Preferred Flow-Level Base

The preferred base for `flow_operational_mart` is the post-overlay flow anchor:

- `s3_flow_anchor_with_fraud_6B`

This surface carries the flow-level context needed to connect event streams, arrival context, entity context, truth, bank view, and case summaries without using event rows as the denominator.

### Required Join Principles

- Join flow-level truth labels to the flow anchor at flow grain.
- Join bank view to the flow anchor at flow grain.
- Aggregate case timeline to flow grain before joining it into the main mart.
- Aggregate event streams to flow grain before using event counts in flow-level reporting.
- Treat arrival/entity/session context as contextual surfaces, not as automatic reporting bases.
- Preserve lineage keys where available; if a compact analysis uses a pinned single-lineage context, the report must say so.

### Unsafe Join Patterns

The following patterns are prohibited unless a specific QA check proves the result is safe:

- joining event rows directly to case timeline and reporting the result as flow count
- counting `AUTH_REQUEST` and `AUTH_RESPONSE` rows as separate transactions
- joining completed session fields into a live-safe feature set
- treating `fraud_flag`, truth label, bank view, and case outcome as interchangeable fraud fields
- treating `campaign_id` nulls as generic missingness without checking structural meaning
- treating `site_id` / `edge_id` nullness as a quality defect without preserving physical/virtual route semantics
- using approximate cardinalities as exact set-equality proof

## Label and Semantics Contract

The project must keep these concepts separate.

| Concept | Meaning in this project | Not allowed to mean |
|---|---|---|
| `fraud_flag` | Upstream overlay/campaign marker exposed in stream or anchor context. | Final fraud truth. |
| Truth label | Final supervised truth surface used for outcome analysis. | Institutional decision, case outcome, or campaign marker. |
| Bank view | Institutional judgement/action surface. | Ground truth. |
| Case timeline | Operational history and workload surface. | Label table by itself. |
| Case coverage | Share of flows represented in case history. | Share of truth-positive flows unless explicitly filtered. |
| Case depth | Number of lifecycle events per case or flow, depending on declared denominator. | Case count. |
| Event count | Count of authorization events. | Flow count. |
| Flow count | Count of distinct authorization flows. | Event rows, arrivals, or case events. |

## Structural Null Contract

The project must distinguish structural nulls from defects.

Known structural-null patterns include:

- physical routing rows may carry `site_id` and no `edge_id`
- virtual routing rows may carry `edge_id` and no `site_id`
- `campaign_id` nullness can represent non-campaign traffic rather than missing campaign assignment

A null can only be called a quality defect after the expected structural rule has been checked.

## Live-Safe and Offline-Only Contract

The project is primarily an offline analytics and reporting project, but it must still classify fields according to safe use.

| Category | Meaning | Examples |
|---|---|---|
| Live-compatible context | Fields that could be available at or before decision time if sourced from online/as-of state. | Merchant, amount, channel, route, arrival timestamp, entity handles. |
| Offline-only context | Fields only known after the fact or after a lifecycle closes. | Completed session duration, `session_end_utc`, final arrival count, truth labels, case outcomes. |
| Reporting-only outcome | Fields suitable for retrospective analysis and reporting, not live scoring. | Truth label, bank view, case lifecycle, chargeback path. |

The mart may include offline-only/reporting-only fields, but they must be labelled so they are not reused as live decision-time features by mistake.

## First-Pass Metric Contract

The first execution pass should define these metrics before producing stakeholder-facing views.

| Metric | Numerator | Denominator | Grain | Primary source | Main caveat |
|---|---|---:|---:|---|---|
| Total flows | Count of flow rows | N/A | Flow | `flow_operational_mart` | Must not be replaced by event-row count. |
| Total event rows | Count of event rows | N/A | Event | Event streams | Not a transaction count. |
| Implied event rows per flow | Event rows | Flows | Flow/event aggregate | Event streams + anchors | Expected grammar must be understood before interpreting exceptions. |
| Truth-positive rate | Truth-positive flows | Total flows | Flow | Truth labels | Depends on truth definition; not same as `fraud_flag`. |
| Bank-positive rate | Bank-positive flows | Total flows | Flow | Bank view | Institutional judgement, not ground truth. |
| Truth-bank agreement rate | Flows where truth and bank align | Total flows | Flow | Truth + bank | Requires explicit truth/bank cell definitions. |
| Truth-positive / bank-negative rate | Truth-positive and bank-negative flows | Total flows | Flow | Truth + bank | Candidate under-action cell, not automatically confirmed failure. |
| Truth-negative / bank-positive rate | Truth-negative and bank-positive flows | Total flows | Flow | Truth + bank | Candidate over-action/friction cell, not automatically incorrect action. |
| Case coverage rate | Flows with at least one case event | Total flows | Flow | Case summary | Case presence is operational history, not truth by itself. |
| Case events per case | Case-event rows | Cases | Case/case-event | Case timeline summary | Measures lifecycle depth, not case incidence. |
| Case events per 1,000 flows | Case-event rows | Total flows / 1,000 | Flow/case-event aggregate | Case summary | Exposure-weighted burden measure. |
| Deep-case rate | Cases above selected depth threshold | Cases | Case | Case summary | Threshold must be declared. |
| Chargeback-path rate | Cases with chargeback progression | Cases | Case | Case summary | Requires case-level path derivation. |
| Dispute-path rate | Cases with dispute progression | Cases | Case | Case summary | Requires case-level path derivation. |
| Amount exposure | Sum of flow amount | Total flows or segment flows | Flow | Flow anchor | Currency and segment filters must be declared. |
| Case amount exposure | Sum of amount for flows with case history | Total case flows | Flow | Mart + case summary | Not equivalent to loss unless a loss field exists. |
| Channel burden rate | Case-covered flows by channel | Total flows by channel | Flow segment | Mart | Channel must not be confused with physical/virtual route. |
| Route burden rate | Case-covered flows by route mode | Total flows by route mode | Flow segment | Mart | `site_id`/`edge_id` structure must be preserved. |
| Merchant burden concentration | Case burden by merchant or merchant cohort | Total flow/case burden | Merchant aggregate | Mart | Row-weighted result may describe exposure, not a typical merchant. |

## Metric Definition Requirements

Every metric that enters a notebook, extract, dashboard, or briefing must declare:

- metric name
- business question it answers
- numerator
- denominator
- grain
- source surfaces
- required filters
- caveats
- expected user or stakeholder
- example interpretation

If a metric cannot declare its denominator, it is not ready for stakeholder reporting.

## Dashboard and Reporting Rules

Dashboard-ready outputs must not require the reader to know internal engine terminology.

Each dashboard table or page must state:

- the grain of the data
- the reporting period
- whether counts are flows, events, cases, or case events
- whether labels are truth, bank view, campaign marker, or case outcome
- whether fields are live-compatible, offline-only, or reporting-only
- whether nulls are structural or unresolved quality issues

## QA and Reconciliation Requirements

The following checks are mandatory before stakeholder-facing conclusions.

| Check | Purpose |
|---|---|
| Flow anchor row count reconciliation | Confirm the mart base is not losing or duplicating flow rows. |
| Event-to-flow grammar check | Prevent event rows from being misreported as flows. |
| Truth join coverage | Confirm truth labels cover the intended flow universe. |
| Bank view join coverage | Confirm institutional view covers the intended flow universe. |
| Truth-bank cell reconciliation | Confirm agreement/disagreement cells sum back to total flows. |
| Case timeline rollup reconciliation | Confirm case-event rows roll into case/flow summaries correctly. |
| Structural null checks | Separate physical/virtual/campaign structural nulls from defects. |
| Reporting-period boundary check | Handle spillover or boundary rows explicitly. |
| Session leakage check | Prevent completed-session facts from being treated as live-safe. |
| Approximation caveat check | Label approximate distinct counts and quantiles as approximate. |

## Acceptance Criteria

This contract is satisfied when execution produces:

- a documented flow-level mart design
- a source-to-target mapping for all in-scope surfaces used
- metric definitions for all stakeholder-facing metrics
- QA checks that reconcile source counts to derived outputs
- explicit caveats for truth, bank view, case timeline, fraud markers, structural nulls, and session fields
- dashboard-ready extracts with grain and denominator rules attached

If execution discovers that a planned metric is not defensible, the correct result is to reject or caveat the metric rather than force it into the reporting product.

## Contract Conclusion

The analytical contract for `AA-001` is flow-centred, assurance-led, and caveat-aware.

The project can still use event streams, arrival context, entity context, sessions, truth products, bank view, and case timeline, but each must enter the analysis through the correct grain and meaning. This is what turns the interface estate from a collection of surfaces into a trusted operational insight product.
