# Interface-World Mapping: From the Data Interface Pack to the Live Fraud Platform

## Why this note exists

This note marks a deliberate change in investigative boundary.

Up to this point, a large part of the work had been structured around the internal authoring flow of the Data Engine: what existed before `1A.S0`, what `S0` produced, how `S1` and `S2` behaved, and how the governed world was progressively constructed inside the engine.

That line of work is still valuable, but it is no longer the primary boundary for the next stage of investigation.

From here, the engine is treated as a **sealed black box**. The question is no longer:

> how did the engine internally author this data world?

The question is now:

> what governed data world has the engine actually exposed to downstream consumers through the interface pack, and how does that exposed world map onto the operating parts of the live fraud platform?

This is the right posture for the analytical role we are now embodying.

We are assuming that the platform is live, the company is already operating across ingestion, decisioning, analytics, case management, governance, and observability, and our team has been handed the governed output world for January to March. In that posture, we do not begin by reopening the engine. We begin by reading the data world we have actually received.

## Working plan used in this mapping exercise

I approached the mapping in three steps:

1. **Fix the black-box authority**
   Use the interface pack rather than state-expanded internals as the governing inventory surface.
2. **Inventory the pinned run against the catalogue**
   Compare the interface catalogue with the actual outputs present under `runs/local_full_run-7\a3bd8cac9a4284cd36072c6b9624a0c1`.
3. **Map exposed outputs to platform operating zones**
   Group the present outputs by what part of the live platform would primarily consume them, and by when they are actually meaningful or available.

## Authority and support artefacts

Primary black-box references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`](../../../../../../docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml)
- [`docs/model_spec/data-engine/interface_pack/README.md`](../../../../../../docs/model_spec/data-engine/interface_pack/README.md)

Pinned run:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`](../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1)

Support script and exported inventories:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/map_interface_world_outputs.py`](../../scratch/map_interface_world_outputs.py)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/interface_output_inventory.csv`](../../exports/interface_world/interface_output_inventory.csv)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/interface_output_inventory_present_only.csv`](../../exports/interface_world/interface_output_inventory_present_only.csv)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/interface_output_summary.json`](../../exports/interface_world/interface_output_summary.json)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/interface_output_mapping_by_area.json`](../../exports/interface_world/interface_output_mapping_by_area.json)

## What is actually exposed in the pinned run

The interface catalogue defines `340` outputs in total. In the pinned run, `243` of them are materially present under the run tree.

The present outputs break down as:

- `145` surfaces
- `59` streams
- `39` gate artefacts

By owner segment, the present output counts are:

- `1A`: `34`
- `1B`: `26`
- `2A`: `9`
- `2B`: `16`
- `3A`: `24`
- `3B`: `25`
- `5A`: `24`
- `5B`: `15`
- `6A`: `44`
- `6B`: `26`

The first important finding is that the exposed analytical world is **not** dominated by canonical traffic.

The primary role counts across the present outputs are:

- `59` audit-evidence outputs
- `52` structural authority surfaces
- `39` gate artefacts
- `29` operations-monitoring outputs
- `20` governance / validation surfaces
- `16` behavioural-generation surfaces
- `16` entity-context surfaces
- `4` behavioural-context surfaces
- `4` truth products
- `2` behavioural streams
- `1` traffic primitive
- `1` traffic-support surface

So the interface world we have been handed is much broader than “the event stream.” The event stream is only one narrow front door inside a much larger governed output world.

## The most important mapping result

The live traffic front door is small.

The exposed outputs that sit directly at the front of the live behavioural platform are only:

- `arrival_events_5B`
- `s1_arrival_entities_6B`
- `s1_session_index_6B`
- `s2_event_stream_baseline_6B`
- `s2_flow_anchor_baseline_6B`
- `s3_event_stream_with_fraud_6B`
- `s3_flow_anchor_with_fraud_6B`

Everything else either:

- helps construct or enrich that traffic,
- describes the structural world behind it,
- supplies offline truth and case products,
- or exists for audit, monitoring, and gate control.

That single fact changes the correct analytical posture.

If we were behaving like a downstream platform team in a live company, we would not think of the interface pack as “the event stream plus a few extras.” We would think of it as a **governed operating data estate** whose traffic-facing edge is thin, while its context, truth, and evidence layers are much larger.

## The platform-facing map

What follows is the practical operating map I would use when reading the interface world as a live platform consumer.

### 1. Structural world context

This is the deepest non-traffic layer of the exposed world. It contains the surfaces that describe the governed merchant, outlet, geography, timezone, alias, zone, and routing world on top of which later traffic is generated and interpreted.

Representative outputs include:

- `1A`: `outlet_catalogue`, `merchant_currency`, `crossborder_features`, `crossborder_eligibility_flags`, `hurdle_pi_probs`
- `1B`: `site_locations`, `tile_bounds`, `tile_index`, `tile_weights`, `s5_site_tile_assignment`, `s6_site_jitter`, `s7_site_synthesis`
- `2A`: `s1_tz_lookup`, `site_timezones`, `tz_timetable_cache`, `s4_legality_report`
- `2B`: `s1_site_weights`, `s2_alias_blob`, `s2_alias_index`, `s3_day_effects`, `s4_group_weights`
- `3A`: `s2_country_zone_priors`, `s3_zone_shares`, `s4_zone_counts`, `zone_alloc`
- `3B`: `edge_catalogue_3B`, `edge_alias_index_3B`, `virtual_classification_3B`, `virtual_routing_policy_3B`

These are not canonical live traffic, but they are critical to downstream understanding.

From a live-platform perspective, these surfaces primarily belong to:

- feature enrichment
- offline analytics
- fraud investigations
- explainability and model-context work

They are the governed structural context that helps explain **where** traffic came from, **what kind of merchant or outlet world** it belongs to, and **what routing or geographic constraints** shape it.

### 2. Behaviour and arrival context

This is the layer that sits between structural world authority and actual platform traffic.

Representative outputs are:

- `5A`: class and merchant zone profile surfaces such as `class_shape_catalogue_5A`, `merchant_zone_profile_5A`, `scenario_calendar_5A`
- `5B`: `s1_grouping_5B`, `s1_time_grid_5B`, `s2_realised_intensity_5B`, `s3_bucket_counts_5B`

These outputs are not themselves the final behavioural stream seen by ingestion. They are closer to the **behavioural authoring context** that explains how the timing, grouping, and intensity world is being shaped before the canonical stream is emitted.

For a downstream analytics team, this layer matters because it explains the temporal and intensity regime the traffic is emerging from. It belongs less to real-time traffic handling and more to:

- behavioural analysis
- simulation understanding
- feature reasoning
- model interpretation

### 3. Live traffic front door

This is the most operationally immediate part of the interface world.

It consists of:

- `arrival_events_5B` as the traffic primitive
- `s2_event_stream_baseline_6B` and `s3_event_stream_with_fraud_6B` as the two canonical behavioural streams
- `s1_arrival_entities_6B`, `s1_session_index_6B`, `s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B` as the context layer needed to enrich those streams

This is the clearest answer to the question:

> what is actually available to the ingestion / event handling / RTDL side of the live platform?

The answer is not “everything.”

At the live traffic boundary, the platform primarily has:

- thin behavioural streams
- thin arrival primitives
- a small number of context surfaces that can be joined onto those streams

This matches the interface pack’s own declared posture that traffic stays thin and context joins happen inside the platform.

### 4. Offline truth and case products

These are the outputs that become meaningful **after** traffic has already existed and been authored.

The key truth products are:

- `s4_event_labels_6B`
- `s4_flow_truth_labels_6B`
- `s4_flow_bank_view_6B`
- `s4_case_timeline_6B`

These outputs are not decision-time traffic.

They belong to:

- offline learning and evaluation
- fraud-review workflows
- investigative analytics
- case management and case reconstruction

This is the part of the interface world that lets the platform move from “what happened” to “what was true about what happened.”

It is therefore not available in the same sense as live traffic. It becomes meaningful later, once outcomes, labels, and case structures exist.

### 5. Entity and network analytical world

Layer `6A` exposes a second major analytical world that is not traffic-first, but entity-first.

Representative outputs include:

- parties: `s1_party_base_6A`, `s1_party_summary_6A`
- accounts: `s2_account_base_6A`, `s2_account_summary_6A`
- holdings: `s2_party_product_holdings_6A`, `s3_account_instrument_links_6A`
- instruments: `s3_instrument_base_6A`
- device and IP: `s4_device_base_6A`, `s4_device_links_6A`, `s4_ip_base_6A`, `s4_ip_links_6A`
- fraud roles: `s5_account_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A`, `s5_merchant_fraud_roles_6A`, `s5_party_fraud_roles_6A`

This is not the stream that would enter the event bus. It is the entity-and-relationship analytical estate that supports:

- graph-style fraud investigation
- post-hoc risk analysis
- network analysis
- offline model and feature work
- case support and fraud-role interpretation

In platform terms, this is the strongest evidence that the interface pack is not just exposing transaction traffic. It is also exposing a fraud-analysis world built around connected entities and roles.

### 6. Audit, operations, and governance world

This is the largest single role grouping in the pinned run.

It includes:

- RNG event streams
- RNG audit logs
- RNG trace logs
- gamma draw logs
- gate receipts
- validation bundles and `_passed.flag` artefacts
- sealed input receipts
- run reports and segment-state journals

This part of the interface world is not business traffic and not truth in the business sense either. It is the evidence plane used to answer:

- can this world be trusted?
- how was this world generated?
- what randomness was consumed?
- what state failed or passed?
- what exactly happened during the run?

For a live platform, these outputs primarily belong to:

- observability
- governance
- reproducibility
- forensic replay
- platform operations

This is important for our analytical posture because it tells us that the exposed interface world is heavily instrumented. We are not receiving only business-facing data products; we are also receiving the machine evidence needed to defend or audit them.

## What is available to what part of the live platform?

This is the cleanest operating summary of the mapping.

| Live platform area | What is primarily available to it from the interface world | What is not its primary working surface |
|---|---|---|
| Ingestion / Event Bus | `s2_event_stream_baseline_6B`, `s3_event_stream_with_fraud_6B`; upstream primitive `arrival_events_5B` | truth products, gate artefacts, most audit streams |
| RTDL / feature enrichment | behavioural streams + `s1_arrival_entities_6B`, `s1_session_index_6B`, `s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B`, plus selected structural context such as outlet/site/timezone authorities | post-hoc truth, case timelines, most validation evidence |
| Offline analytics / DS | structural world context (`1A`–`3B`), behaviour/intensity context (`5A`/`5B`), behavioural streams (`6B`), entity world (`6A`), truth products (`6B`) | none of the major data families are excluded here, but time-safe restrictions still matter when reasoning about live decisions |
| Case management / fraud ops | `s4_case_timeline_6B`, `s4_event_labels_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, plus `6A` fraud-role and entity-link surfaces | raw RNG evidence is supportive, not primary |
| Observability / forensics | `rng_audit_log_*`, `rng_trace_log_*`, `rng_event_*`, `gamma_draw_log_3B`, run reports, state-run journals | canonical business traffic is only one reference surface here |
| Governance / release control | gate receipts, validation bundles, `_passed.flag`, sealed inputs, validation reports / issue tables | behavioural streams are not authoritative without these passes |

This table is the practical answer to the user’s operating question:

not every surface is simultaneously available, relevant, or safe for every platform function.

The behavioural streams sit at the live edge. The context surfaces support them. The structural authorities explain them. The truth products evaluate them. The audit and gate artefacts defend them.

## The biggest analytical implication

The front-facing analytical world is not a single dataset family. It is a **layered operating estate**.

From this mapping exercise, the interface world resolves into six practical strata:

1. structural world context
2. behaviour and arrival context
3. live traffic front door
4. offline truth and case products
5. entity and network analytical world
6. audit / operations / governance evidence

This means the next notebook should not begin by randomly opening whatever parquet appears first. It should begin with a controlled inventory of the exposed world, using this layered operating map as the first orientation lens.

## What this establishes for the next stage

This mapping exercise has done its job if it changes how we think about the interface pack.

We should no longer think:

> the interface pack gives us “the data”.

We should instead think:

> the interface pack gives us a governed operating data estate, and different parts of that estate belong to different moments and responsibilities in the life of the live fraud platform.

That is the right foundation for the next notebook phase.

The immediate next analytical move should be to open the exposed inventory itself and decide which asset family we want to inspect first from the downstream consumer point of view.
