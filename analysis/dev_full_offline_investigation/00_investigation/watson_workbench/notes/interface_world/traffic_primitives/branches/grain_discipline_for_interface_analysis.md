# Sub-Branch Investigation: Grain Discipline for Interface Analysis

## Branch question

The `arrival_events_5B` grain-and-identity branch exposed a broader rule: before we interpret a count, rate, share, average, or trend, we must know the grain at which the calculation is being made.

This sub-branch turns that rule into an explicit analytical discipline for the interface-world investigation.

The question is:

> When we analyse the interface pack, what unit of truth are we counting, and what question does that unit actually answer?

## Why this matters

The interface pack does not expose one kind of table. It exposes several operating surfaces from the live fraud decisioning platform: arrival context, event streams, flow anchors, session context, labels, bank views, and case timelines. These surfaces are related, but they do not all speak at the same grain.

That matters because a correct calculation can still answer the wrong question.

For example, a row-level fraud rate on an event stream answers a different question from a flow-level fraud rate. A merchant-weighted average answers a different question from an arrival-weighted average. A case-timeline count answers a different question from a label count, even if both are connected to the same underlying flow.

So the discipline is not academic. It protects the investigation from mixing meanings.

## Working definition

Grain is the level at which one row, one count, or one metric is true.

In practical terms:

- If one row represents one arrival, the grain is arrival-level.
- If one row represents one event in a request/response stream, the grain is event-level.
- If one row represents one flow, the grain is flow-level.
- If one row represents one merchant, the grain is merchant-level.
- If one row represents one case event, the grain is case-event-level.
- If one row represents one case, the grain is case-level.

The grain tells us what the denominator means.

That denominator is the source of the interpretation. `10% of rows`, `10% of merchants`, `10% of flows`, and `10% of cases` are not interchangeable statements.

## The main grains we expect to handle

| Grain | Unit being counted | Typical surface | What it can answer | What it cannot answer by itself |
|---|---|---|---|---|
| Arrival grain | One merchant-local arrival context observation | `arrival_events_5B` | Traffic exposure, arrival timing, route/channel context | Fraud truth, approval outcome, case outcome |
| Event grain | One stream event, such as request or response | Behavioural event streams | Event throughput, stream volume, request/response shape | Flow-level outcome without collapsing events |
| Flow grain | One transaction-flow unit | Flow anchors, flow truth, bank view | Per-flow labels, truth outcomes, bank outcomes | Event-level latency or case lifecycle by itself |
| Merchant grain | One merchant actor | Aggregations over arrival/flow surfaces | Typical merchant behaviour, merchant concentration, merchant exposure | Total platform load unless weighted by volume |
| Session grain | One session window or session aggregate | Session index/context surfaces | Session structure, session density, repeated activity | Individual event ordering without event detail |
| Label grain | One labelled flow or labelled event, depending on surface | Truth and event-label products | Supervision, target prevalence, label propagation | Case handling process by itself |
| Case-event grain | One event in a case timeline | Case timeline | Case lifecycle, investigation steps, time-to-action | Number of unique cases unless collapsed |
| Case grain | One case lifecycle collapsed to a case id/flow | Case aggregates derived from timeline | Case volume, case outcomes, case aging | Step-level process behaviour |

The important point is that these grains can be joined, but they should not be silently substituted for one another.

## The most common failure mode

The common failure mode is to compute a metric at one grain and describe it as though it belongs to another grain.

Examples:

- A row-weighted arrival average is described as a typical merchant average.
- An event-level count is described as a flow-level count, even though each flow may produce multiple events.
- A case-event count is described as a case count, even though one case can have several timeline events.
- A flow-label rate is applied to merchants without asking whether merchants are equally weighted or arrival/flow weighted.

These mistakes are easy to make because joins make the data look unified. The join gives access to more columns, but it does not erase the original grain.

## How to read row-weighted versus entity-weighted results

The `arrival_events_5B` branch showed why this distinction matters.

At row grain, high-volume merchants legitimately have more influence because they create more arrivals. This is correct for exposure questions:

- How much traffic did the platform see?
- Which channels carry the most arrivals?
- Which route lanes create the most operating load?
- How does traffic move across the horizon?

At merchant grain, each merchant has one vote. This is correct for actor questions:

- What does a typical merchant look like?
- How concentrated is traffic across merchants?
- Which merchants are unusually large or small?
- Do merchant-level patterns differ by channel or route context?

Neither view is automatically better. They answer different questions. The error is using one and describing it as the other.

## Working rules for the investigation

1. Every count must say what it is counting.

2. Every rate must name its denominator.

3. Every average must say whether it is row-weighted, merchant-weighted, flow-weighted, case-weighted, or otherwise weighted.

4. Every join must preserve awareness of the starting grain.

5. Every plot should make its grain visible through the title, axis labels, or surrounding text.

6. Every dashboard metric should be named in a way that exposes the grain, not hides it.

## Applying this to later interface analysis

When we move from traffic primitives into behavioural streams, the event stream will introduce event grain. If request and response events both exist per flow, counting event rows is not the same as counting flows.

When we move into behavioural context, session and flow-anchor surfaces will introduce additional grains. A session aggregate should not be read as an event stream, and a flow anchor should not be read as a merchant catalog.

When we move into truth products, flow-level truth, event-level labels, bank views, and case timelines will each need their own grain check. This will matter especially when calculating prevalence, recall-like quantities, case rates, and investigation workload.

The discipline from this branch should therefore travel with the whole investigation: before interpreting a metric, ask what unit is being counted and whether that unit matches the question.

## Working conclusion

Grain discipline is the guardrail that keeps the interface-world investigation honest.

The platform surfaces are connected, but they are not interchangeable. `arrival_events_5B` taught us this first because `236.7M` arrival rows sit over only `4,050` merchants. The same issue will recur in different forms as we move into events, flows, labels, sessions, and cases.

The practical standard is simple: no rate, average, share, or trend should be accepted until its grain is clear.
