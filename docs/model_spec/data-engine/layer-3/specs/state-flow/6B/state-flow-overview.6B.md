# Layer 3 — Segment 6B: Behaviour & Fraud Cascades
Here’s a state-flow overview for **Layer 3 / Segment 6B** in the same style as 5A/5B and 6A — conceptual, non-binding, but structured and clear.

**Role in the engine**

By the time 6B runs:

* **Layer-1** has fixed the merchant/location/zone/edge world.
* **Layer-2** has produced a **stream of arrivals** (when and where traffic hits).
* **Layer-3 / 6A** has built the **entity & product world** (customers, accounts, instruments, devices, IPs, static fraud posture).

**Segment 6B** takes all of that and turns it into:

* event flows (auths, clearings, refunds, chargebacks…),
* fraud campaigns and abuse patterns,
* labels and outcomes that look like what a bank lives with.

It doesn’t change *when* arrivals happen or *where* they land; it decides **who is involved and what happens**.

---

## 6B.S0 — Gate & sealed inputs

**Purpose**

Set the trust boundary for Layer-3 behaviour and freeze the exact universe of inputs 6B is allowed to use.

**Upstream dependencies**

* PASSed validation bundles (and flags) for:

  * Layer-1 segments (1A–3B): merchant + routing world.
  * Layer-2 segments (5A/5B): arrival surfaces + skeleton arrivals.
  * Layer-3 / 6A: entity & product world.
* Layer-3 contracts:

  * schemas for 6B event/flow/label outputs,
  * dataset dictionary entries,
  * artefact registry entries for campaign/config surfaces.

**Behaviour**

* Verify that all required upstream segments have PASSed under the current `manifest_fingerprint`.
* Resolve and seal:

  * skeleton arrival stream from 5B,
  * entity graph from 6A (customers, accounts, instruments, devices, IPs, merchants),
  * behaviour priors (baseline spend profiles, channel mix, retry patterns),
  * fraud/abuse campaign configs (types, parameters, scenarios),
  * any label/outcome policies (e.g. dispute/chargeback delays).
* Produce an explicit inventory 6B may read; refuse to run if required artefacts are missing or mismatched.

**Outputs**

* `s0_gate_receipt_6B`
  – shows which Layer-1/2/6A bundles were honoured and which 6B policies were sealed.

* `sealed_inputs_6B`
  – table of all artefacts (ids, partitions, schema refs, digests) that 6B is allowed to touch.

---

## 6B.S1 — Entity & session assignment

**Purpose**

Attach each arrival from Layer-2 to **real synthetic entities** and group arrivals into **sessions/flows**.

**Inputs**

* Skeleton arrival stream from 5B (`arrival_id`, `utc_ts`, `merchant_id`, site/edge, scenario_id, etc.).
* Entity outputs from 6A:

  * customers, accounts, instruments, devices, IPs, their relationships.
* Behaviour priors:

  * channel preferences per customer/segment,
  * how often customers visit which merchant types,
  * typical session structures for each scenario.

**Behaviour**

For each arrival:

* Pick a plausible tuple:

  * `(customer_id, account_id, instrument_id, device_id, ip_id)`
    consistent with:

    * the scenario (POS, e-com, mobile, ATM, etc.),
    * the merchant type and region,
    * the customer’s past behaviour profile.
* Assign a **session_id** (or flow_id):

  * new session, or
  * continuation of an in-progress session from the same customer/channel.

Over the whole stream, ensure:

* realistic distribution of:

  * customers per merchant,
  * merchants per customer,
  * devices/IPs per account/merchant.

**Outputs**

* `s1_arrival_entities_6B`
  – arrival stream enriched with entity assignments and session/flow keys.

* Optional:

  * `s1_session_index_6B` summarising sessions (start/end, channel, merchant, customer).

---

## 6B.S2 — Baseline transactional flows (legitimate behaviour)

**Purpose**

Turn entity-attached arrivals into **baseline flows** of events that represent normal banking behaviour, assuming no fraud.

**Inputs**

* `s1_arrival_entities_6B` (arrivals with entities + session_id).
* Behaviour priors:

  * typical event sequences per scenario (e.g. POS, single e-com checkout, account login),
  * retry patterns (how often customers retry after a decline),
  * amount distributions, channel-specific quirks.

**Behaviour**

For each arrival / session:

* Decide what kind of flow it generates:

  * simple POS auth→clearing,
  * e-com checkout with multiple auth attempts,
  * login-only session with no monetary flow,
  * recurring bill payment, etc.
* For each flow:

  * Generate a **sequence of events**:

    * auth requests and responses,
    * possible 3-DS / step-up events,
    * clearing/settlement,
    * any immediate refunds or reversals,
  * Assign monetary amounts and currencies consistent with customer/product/merchant characteristics.

By the end of S2, you have a complete picture of what the bank would see **if everything were legitimate**.

**Outputs**

* `s2_event_stream_baseline_6B`
  – event-level table: one row per event in each flow, with:

  * timestamps,
  * event_type (AUTH_REQUEST, AUTH_RESPONSE, CLEARING, REFUND, etc.),
  * links to arrival_id, session_id, customer/account/instrument.

* `s2_flow_anchor_baseline_6B`
  – one row per flow/transaction anchor, summarising:

  * merchant, customer, amount, channel,
  * key timestamps (auth, clearing),
  * any baseline outcome (e.g. approved/declined for normal reasons).

---

## 6B.S3 — Fraud & abuse campaigns overlay

**Purpose**

Overlay **fraud and abuse patterns** onto the baseline flows to create realistic fraud stories and abnormal behaviour.

**Inputs**

* Baseline flows from S2:

  * `s2_event_stream_baseline_6B`,
  * `s2_flow_anchor_baseline_6B`.
* 6A fraud posture:

  * static roles (mules, synthetic IDs, risky merchants).
* Fraud campaign configs:

  * card-testing templates,
  * account takeover templates,
  * merchant collusion scenarios,
  * refund/chargeback abuse patterns.

**Behaviour**

* Instantiate **campaigns** based on their configs:

  * decide which time windows, regions, merchant classes, and entity segments each campaign targets.
* For each campaign:

  * select affected flows and/or spawn new flows:

    * card testing flows at low-value merchants,
    * high-value fraud at electronics merchants,
    * waves of logins from suspicious devices/IPs,
    * unusual refund patterns at flagged merchants.
  * mutate baseline flows where needed:

    * flip amounts, change locations, alter device/IP usage, increase attempt counts, etc.
* Tag all affected events/flows with:

  * `campaign_id`,
  * `fraud_pattern_type`,
  * any internal fields needed for validation and analysis.

**Outputs**

* `s3_event_stream_with_fraud_6B`
  – event stream with both baseline and fraud-modified events, including campaign tags.

* `s3_flow_anchor_with_fraud_6B`
  – updated flow anchors with flags/fields indicating participation in fraud/abuse.

* `s3_campaign_catalogue_6B`
  – table of campaign instances (start/end, type, target, intensity parameters).

---

## 6B.S4 — Labels, decisions & life-cycle assembly

**Purpose**

Assign **truth labels** and **bank-view outcomes** to flows, and assemble the life-cycle for each transaction in a bank-realistic way.

**Inputs**

* `s3_flow_anchor_with_fraud_6B` and associated events (`s3_event_stream_with_fraud_6B`).
* Bank decision logic config:

  * what rules or model outputs you want to simulate,
  * how disputes and chargebacks arise,
  * typical time-to-chargeback distributions.

**Behaviour**

For each flow / transaction anchor:

1. **Truth label**

   * Determine a ground-truth classification:

     * LEGIT,
     * FRAUD_AUTH (fraud caught at auth),
     * FRAUD_SETTLED (fraud that clears and later chargebacks),
     * ABUSE (e.g. refund abuse, friendly fraud),
     * other nuanced labels as needed.

2. **Bank-view dynamic label**

   * Simulate how the bank *perceives* the transaction over time:

     * initial decision at auth (approve/decline),
     * whether a dispute or chargeback is filed,
     * whether the case is investigated and reclassified.

3. **Life-cycle stitching**

   * Attach timestamps and reasons for:

     * disputes,
     * chargebacks,
     * refunds,
     * write-offs.

**Outputs**

* `s4_event_stream_final_6B`
  – final event stream with labels and bank-view outcomes attached where relevant.

* `s4_flow_labels_6B`
  – label surface keyed by flow/transaction anchor:

  * truth label,
  * bank-view label,
  * campaign_id (if any).

* Optional:

  * `s4_case_timeline_6B` for disputes/chargebacks (one record per case).

---

## 6B.S5 — Validation & bundle (RNG-free)

**Purpose**

Validate the behaviour & fraud layer and publish a **Layer-3 validation bundle + PASS flag** that downstream models and tools can rely on.

**Inputs**

* All 6B outputs:

  * arrival-to-entity assignment (S1),
  * baseline and fraud-overlaid flows (S2/S3),
  * labels/outcomes (S4),
  * RNG logs for 6B (campaign draws, assignment draws, flow variations).
* 6A outputs (entity graph, fraud roles).
* Upstream context (L1/L2 bundles as needed for cross-layer checks).

**Behaviour**

* **Structural sanity**

  * Check referential integrity between arrivals, entities, flows and events.
  * Confirm no impossible state transitions (e.g. chargebacks without prior clearing).
  * Ensure label surfaces are consistent with events (truth vs bank-view timelines).

* **Statistical sanity**

  * Compare realised fraud rates by segment against configured targets.
  * Check that campaign intensity and targeting match their parameters.
  * Confirm distributional properties (e.g. chargeback delays, refund rates) are within expected bands.

* **RNG & replay**

  * Reconcile 6B RNG logs:

    * numbers of draws,
    * counter monotonicity,
    * correct labelling of RNG events by module/stream.

* **Bundle**

  * Assemble a `validation_bundle_6B` directory with:

    * index file listing evidence and their checksums,
    * summary reports and metrics,
    * any diagnostic slices.
  * Compute SHA-256 over indexed evidence and write `_passed.flag_6B` with that digest.

**Outputs**

* `validation_bundle_6B`
  – evidence package for 6B’s behaviour & fraud realism.

* `_passed.flag_6B`
  – PASS flag; downstream consumers must enforce “no 6B PASS → no read of 6B outputs”.

---

**After 6B**

At the end of Segment 6B you have:

* A **behavioural event stream** reflecting normal and abnormal flows.
* A **transaction/flow anchor surface** summarising each story.
* **Ground truth** and **bank-view** labels that reflect realistic fraud and dispute dynamics.
* A Layer-3 validation bundle that proves those outputs are structurally and statistically sane.

That’s the point where your engine’s outputs start to look like what a real bank’s data science and fraud teams handle day to day.
