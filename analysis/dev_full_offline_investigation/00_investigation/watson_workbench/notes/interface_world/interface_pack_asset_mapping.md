# Interface-World Mapping: The Downstream Operating Estate

## Black-box posture

The binding interface-pack docs are clear about the boundary:

- the interface pack exists so the platform can consume engine outputs **without importing segment/state internals**
- platform components are expected to operate from the interface contract, output catalogue, gate map, and boundary schemas
- the platform is not supposed to reason from engine-authoring layers such as `1A`, `1B`, `2A`, `2B`, `3A`, `3B`, `5A`, or `6A`

So for this investigation, the following are treated as **inside the black box**:

- `1A`
- `1B`
- `2A`
- `2B`
- `3A`
- `3B`
- `5A`
- `6A`

Those surfaces may exist in the run tree. They may even be highly informative to the builder. But for the downstream analytical posture we are now adopting, they are not part of the received operating data world.

## Operating-platform posture

For the rest of the interface-world investigation, we are treating the pinned run as the data estate behind a live AWS-hosted Fraud Decisioning Platform operated by a financial institution.

That means these notes are not only cataloguing datasets. Each surface is read in terms of its place in the operating platform:

- what part of the platform would emit or expose it
- whether it is streamed as business traffic or held as a join/context surface
- whether it is live-safe for real-time decisioning or only available after the fact
- which other surfaces it needs to be interpreted correctly
- what role it plays for analytics, data science, case review, learning, evaluation, or audit

The production-readiness posture matters here because the platform does not batch-absorb the whole Oracle Store per event. Oracle Store is the warm source-of-stream S3 zone; WSP streams run-pinned topic families from that source into the platform. Traffic and context topics move through the live operating run according to their event-time/order contract, while truth and case/label products belong to post-decision or offline authority. So the analysis must keep the operational distinction between streamed traffic, streamed/joined context, offline labels, and case history intact.

## Authority and support artefacts

Primary boundary references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`](../../../../../../docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml)
- [`docs/model_spec/data-engine/interface_pack/README.md`](../../../../../../docs/model_spec/data-engine/interface_pack/README.md)
- [`docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`](../../../../../../docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md)
- [`docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md`](../../../../../../docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md)
- [`docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.plan.md`](../../../../../../docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.plan.md)

Pinned run:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`](../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1)

Support script and exports:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/map_interface_world_outputs.py`](../../scratch/map_interface_world_outputs.py)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/interface_downstream_estate_inventory.csv`](../../exports/interface_world/interface_downstream_estate_inventory.csv)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/interface_downstream_estate_present_only.csv`](../../exports/interface_world/interface_downstream_estate_present_only.csv)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/interface_downstream_estate_summary.json`](../../exports/interface_world/interface_downstream_estate_summary.json)

## What the downstream estate actually contains

Under this black-box posture, the downstream operating estate resolves into a small set of named interface surfaces.

In the pinned run, the downstream estate contains exactly `17` present outputs:

- `1` traffic primitive
- `2` behavioural streams
- `4` behavioural-context surfaces
- `4` truth products
- `6` gate artefacts

By segment, that becomes:

- `5B`: `4` outputs
- `6B`: `13` outputs

The analytical estate we have actually been handed is **not** the whole run-visible interface world. It is a narrow `5B` / `6B` operating slice, plus the gate artefacts that authorize reads from that slice.

## The exposed source-of-stream estate

The interface-pack contract and the dev_full run process separate the Oracle Store source-of-stream estate from engine internals. WSP reads the stream-view/source roots for a run and publishes the relevant topic families into the platform. This is not a staged handoff where one dataset arrives, then another arrives later as a separate batch. It is a topic-family operating model.

The exposed source-of-stream estate is:

- `arrival_events_5B`
- `s1_arrival_entities_6B`
- `s1_session_index_6B`
- `s2_event_stream_baseline_6B`
- `s2_flow_anchor_baseline_6B`
- `s3_event_stream_with_fraud_6B`
- `s3_flow_anchor_with_fraud_6B`

This is the operationally meaningful answer to the question:

> what source surfaces and topic families would the platform operate from at the behavioural edge?

It is not outlet construction data. It is not merchant-authoring authority. It is not site synthesis or entity-world construction. It is this much thinner event-plus-context estate.

That is the downstream-facing world we should now investigate.

## Mapping by interface role

### 1. Traffic primitive

There is one traffic primitive:

- `arrival_events_5B`

This is the exposed arrival context primitive. It is event-like, but the interface contract is explicit that it is **not** the canonical business-traffic stream.

So its role is:

- arrival context topic/surface
- join surface for arrival-key, routing, and timezone context
- event-time companion to richer traffic/context topics

It matters because it gives the platform arrival/routing context without exposing the engine-authoring machinery that produced the world. It should not be read as "arrives first before other datasets exist"; it is one context family in the streamable operating estate.

### 2. Behavioural streams

There are two canonical behavioural streams:

- `s2_event_stream_baseline_6B`
- `s3_event_stream_with_fraud_6B`

These are the surfaces that sit closest to live business traffic in the platform.

They matter because they are the streams eligible for:

- ingestion
- event-bus handling
- downstream feature-plane consumption
- transaction-style behavioural analysis

These are the production-shaped behavioural traffic topics. They do not wait for the arrival context to complete as a separate batch; they are interpreted alongside the relevant context surfaces through declared keys and time-safety rules.

### 3. Behavioural context

There are four behavioural-context surfaces:

- `s1_arrival_entities_6B`
- `s1_session_index_6B`
- `s2_flow_anchor_baseline_6B`
- `s3_flow_anchor_with_fraud_6B`

These are not traffic. They are the join surfaces needed to interpret or enrich the behavioural streams.

The downstream platform does not need deep world-building datasets in order to contextualize traffic. The interface pack already gives it constrained context families whose job is exactly that.

Within this group, the time-safety split matters:

- **RTDL-safe join surfaces**
  - `arrival_events_5B`
  - `s1_arrival_entities_6B`
  - `s2_flow_anchor_baseline_6B`
  - `s3_flow_anchor_with_fraud_6B`
- **Oracle-only / batch-only context**
  - `s1_session_index_6B`

The session index is the important caution surface here. The interface contract states that it contains future-closure information such as `session_end_utc` and `arrival_count`, so it is not live-safe for decision-time use even though it is useful analytically.

### 4. Truth products

There are four truth products:

- `s4_event_labels_6B`
- `s4_flow_truth_labels_6B`
- `s4_flow_bank_view_6B`
- `s4_case_timeline_6B`

These are explicitly offline surfaces.

They do not belong to:

- live traffic handling
- RTDL
- decision-time feature consumption

They do belong to:

- supervision
- evaluation
- case tooling
- investigative reconstruction
- post-hoc analytics

This is where the platform moves from “what traffic/context was moving through the operating run?” to “what became true about that traffic later?”

### 5. Gate artefacts

There are six read-authorizing gate artefacts in the downstream estate:

- `validation_bundle_5B`
- `validation_bundle_index_5B`
- `validation_passed_flag_5B`
- `validation_bundle_6B`
- `validation_bundle_index_6B`
- `validation_passed_flag_6B`

These are not analytical business datasets, but they are part of the downstream estate because the interface contract gives them operational force:

> no PASS -> no read

So in the platform operating story, they answer a separate but essential question:

> are we even allowed to treat these surfaces as authoritative?

They belong to governance and read authorization, not to traffic or truth themselves.

## What is available to what part of the live platform?

Within this boundary, the practical platform map becomes much cleaner.

| Live platform area | Downstream-facing surfaces that matter | Important caution |
|---|---|---|
| WSP / source-of-stream publication | `s2_event_stream_baseline_6B`, `s3_event_stream_with_fraud_6B`, `arrival_events_5B`, `s1_arrival_entities_6B`, selected flow-anchor context | stream-view/source roots are pinned for the run; topic families move under run identity |
| Ingestion / Event Bus | behavioural traffic topics and context topics such as `fp.bus.traffic.fraud.v1`, `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, `fp.bus.context.flow_anchor.fraud.v1` | only authoritative after relevant validation PASS and topic readiness |
| RTDL / feature enrichment | `arrival_events_5B`, `s1_arrival_entities_6B`, `s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B` | consumed as context/projections; `s1_session_index_6B` is not live-safe |
| Offline analytics / DS | all front-door streams and context plus `s4_*` truth products | must respect live-safe vs offline-only distinction |
| Case management / fraud ops | `s4_case_timeline_6B`, `s4_event_labels_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B` | these are post-hoc truth surfaces, not live traffic |
| Governance / access control | `validation_bundle_*`, `validation_bundle_index_*`, `validation_passed_flag_*` | no authoritative read without PASS |

This is the operating answer to the user’s question about what is available to what.

The platform is not handed one flat pile of data, and it does not receive one dataset completely before the next. It operates from:

- thin streamed traffic
- streamed/joined context topic families
- offline truth
- read-authorizing validation evidence

That is the real exposed world.

## What is explicitly not part of this downstream map

To keep the posture honest, it is important to say what we are **not** including:

- `1A` merchant and outlet-world construction
- `1B` site-world construction
- `2A` timezone-world authority
- `2B` alias and grouping-world authority
- `3A` zone-authoring authority
- `3B` routing / edge-world construction
- `5A` behavioural-authoring context
- `6A` entity-world construction

Those surfaces may still be useful to a builder trying to understand the platform. But if we are acting as a downstream analytical team handed the governed operating estate, those surfaces are still inside the black box and should not structure our first investigation.

## What this establishes for the notebook

We are mapping the **received downstream operating estate**:

1. traffic primitive  
2. behavioural streams  
3. behavioural context  
4. truth products  
5. read-authorizing gate artefacts  

That narrower framing is the right starting point for the next analytical move.

## Final working conclusion

The downstream analytical team has **not** been handed the engine’s world-building datasets. It has been handed a thin behavioural operating estate centered on `5B` and `6B`, plus the gate artefacts required to trust those surfaces.

So the next phase of notebook work should begin from those surfaces directly, letting their structure speak for itself, rather than importing hidden authority layers to explain them prematurely.
