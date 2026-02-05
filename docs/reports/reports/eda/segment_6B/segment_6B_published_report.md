# Segment 6B — Design vs Implementation Observations (Behaviour & Labels)
Date: 2026-02-05  
Run: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92`  
Scope: Design intent vs implementation notes for Segment 6B (S0–S5) prior to statistical assessment.

---

## 0) Why this report exists
Segment 6B converts the sealed world into **behavioural data**: it attaches arrivals to entities, builds flows, overlays fraud campaigns, and assigns truth/bank‑view labels. If 6B’s behaviour and labels are statistically unrealistic, then downstream models will learn brittle or misleading patterns even if 5A/5B/6A are strong. This report anchors three things before analysis:
1. **Design intent** (what 6B should do).
2. **Implementation posture** (what we actually built, including lean tradeoffs).
3. **Datasets of interest** (what will be examined for realism).

---

## 1) Design intent (what 6B should do)
1. **S0 — Behavioural universe gate & sealed inputs**  
   Verify upstream HashGates (1A–3B, 5A–5B, 6A), validate 6B contract packs, and publish `s0_gate_receipt_6B` + `sealed_inputs_6B` so downstream states know exactly what they may read.
2. **S1 — Arrival‑to‑entity attachment & sessionisation**  
   Attach each arrival to a party/account/instrument/device/IP consistent with 6A link rules and behaviour priors, then group arrivals into sessions.
3. **S2 — Baseline flow synthesis**  
   Convert attached arrivals into baseline (all‑legit) transactional flows and event sequences, with amounts, timing, and outcomes governed by flow‑shape and timing policies.
4. **S3 — Fraud/abuse overlay**  
   Realise fraud campaigns and overlay them onto baseline flows and events, producing campaign‑aware “with‑fraud” behavioural canvases.
5. **S4 — Truth & bank‑view labelling**  
   Convert behavioural canvases into truth labels and bank‑view outcomes, including case timelines and detection/chargeback lifecycles.
6. **S5 — Segment validation & HashGate**  
   Validate chain integrity across S0–S4, enforce policy checks, and publish the 6B validation bundle + `_passed.flag` gate.

---

## 2) Priority datasets (realism‑relevant)
Primary realism surfaces:
1. `s1_arrival_entities_6B` (arrival→entity attachment realism)
2. `s1_session_index_6B` (session structure realism)
3. `s2_flow_anchor_baseline_6B` (baseline flow realism)
4. `s2_event_stream_baseline_6B` (baseline event realism)
5. `s3_campaign_catalogue_6B` (campaign mix, intensity, targeting realism)
6. `s3_flow_anchor_with_fraud_6B` (fraud overlay realism)
7. `s3_event_stream_with_fraud_6B` (fraud event realism)
8. `s4_flow_truth_labels_6B` (truth label realism)
9. `s4_flow_bank_view_6B` (bank‑view realism)
10. `s4_event_labels_6B` (event‑level label realism)
11. `s4_case_timeline_6B` (case lifecycle realism)

Evidence/control surfaces (important for constraints, not realism):
1. `s0_gate_receipt_6B`, `sealed_inputs_6B`
2. `validation_bundle_6B` + `_passed.flag`

---

## 3) Implementation observations (what is actually done)
Based on `docs\model_spec\data-engine\implementation_maps\segment_6B.impl_actual.md` and the 6B expanded specs.

### 3.1 S0 — Gate & sealed inputs
Observed posture: **strict schema compliance** with a **lean HashGate**.
1. **Schema enforcement is strict.** All 6B policy/config packs are validated against `schemas.6B.yaml`; missing anchors or extra fields cause S0 to fail.
2. **HashGate verification is lean.** Upstream bundles are checked via `_passed.flag` digests and index presence, not full bundle rehashing.
3. **Structural digests for large data.** Large row‑level artefacts are sealed by structural digests (path/schema/partition keys), not full content hashes.
4. **Sealed‑inputs fallbacks for upstream outputs.** When upstream sealed_inputs manifests do not list egress outputs (e.g., `arrival_events_5B`), S0 falls back to path‑existence checks with wildcard support.
5. **Contract gaps were patched.** A 6B copy of `schemas.layer3.yaml` was added so gate anchors resolve; several policy configs were trimmed to match strict schemas.

### 3.2 S1 — Arrival→entity attachment & sessionisation
Observed posture: **deterministic, vectorized attachment** with simplified sessionisation.
1. **Hash‑based attachment, not heavy scoring.** Entities are chosen from valid 6A candidate sets via deterministic hash‑derived indices (no per‑row RNG, no multi‑feature scoring).
2. **Candidate sets are constrained.** Accounts are limited to those with instruments; devices are limited to those with IP links. This enforces feasibility but narrows behavioural diversity.
3. **Sessionisation is simplified.** Stochastic boundaries are disabled; sessions are derived via hard time windows and deterministic bucketing, not full gap‑based logic.
4. **Streaming batches replace global sorts.** Arrival attachment is done in batches to avoid full in‑memory sorts; session index aggregation is bucketed to avoid memory spikes.
5. **Lean RNG logging.** RNG logs are aggregated per family (no per‑row event logs); session boundary draws are zero because stochasticity is disabled.

### 3.3 S2 — Baseline flow synthesis
Observed posture: **one‑flow‑per‑arrival with minimal event templates**.
1. **Flow mapping is one‑arrival‑to‑one‑flow.** This avoids multi‑flow session planning and keeps O(N) streaming.
2. **Event stream is minimal.** Only `AUTH_REQUEST` and `AUTH_RESPONSE` events are produced; no clearing, refunds, or step‑up flows.
3. **Timing is fixed to arrival timestamps.** No timing distributions or RNG‑driven gaps are applied.
4. **Amounts are deterministic and discrete.** Amounts are hash‑selected from `price_points_minor`, converted to major units; no heavy‑tail sampling.
5. **Flow shape/timing policies are validated but not used.** The policies exist for contract compliance but are not executed in the lean path.

### 3.4 S3 — Fraud/abuse overlay
Observed posture: **tag‑only fraud overlay with bounded amount shifts**.
1. **No new flows or event shape changes.** S3 does not add extra events or flows; it tags existing flows/events.
2. **Campaigns are deterministic and minimal.** One campaign instance per template; target selection is hash‑based without rich targeting filters when fields are missing.
3. **Fraud effect is a small amount upshift.** Fraud flows get a bounded multiplier; no routing or timing anomalies are introduced.
4. **No multi‑campaign stacking.** A flow is assigned to at most one campaign.
5. **RNG logs are non‑consuming.** RNG envelopes are written for accounting, but no stochastic draws are used.

### 3.5 S4 — Truth & bank‑view labelling
Observed posture: **campaign‑driven deterministic labels** with simplified case logic.
1. **Truth labels derive directly from campaign types.** If `campaign_id` exists, the flow is mapped via `direct_pattern_map`; otherwise it is LEGIT.
2. **Bank‑view decisions are hash‑deterministic.** Auth/detect/dispute/chargeback outcomes are derived from hash‑uniform draws, not RNG state.
3. **Case logic is simplified.** One case per flow when case is opened; no cross‑flow grouping or reopen logic.
4. **Delays are fixed to minimums.** Delay models are applied as fixed minimum offsets, not sampled distributions.
5. **Event labels are recomputed, not joined.** Event‑level labels are derived from flow‑level decisions to avoid heavy joins.

### 3.6 S5 — Segment validation & HashGate
Observed posture: **lean validation with metadata‑first checks**.
1. **Validation is lightweight.** Uses parquet metadata and samples; does not perform full scans or deep RNG budget checks.
2. **Upstream HashGate verification is shallow.** Uses S0 receipt + `_passed.flag` presence rather than full recompute.
3. **PK uniqueness and parity checks are sampled.** Row‑count parity is from metadata; PK uniqueness is sampled.
4. **Realism checks are WARN‑only.** Corridor checks report warnings but do not block `_passed.flag` if required checks pass.
5. **Bundle contains only report + issue table.** `_passed.flag` is excluded from the bundle as required by hashing law.

---

## 4) Design vs implementation deltas (material)
1. **S0 gate verification is lean.** The spec expects deep bundle verification; implementation uses `_passed.flag` + index presence and structural digests for large datasets.
2. **S1 attachment is deterministic and simplified.** Heavy scoring, stochastic session boundaries, and merchant‑specific device/IP logic are reduced or skipped; sessionisation uses bucketed windows for scale.
3. **S2 baseline flows are minimal.** One flow per arrival and two events per flow; no clearing/refund/step‑up flows and no timing distributions.
4. **S3 overlays are tags, not structural mutations.** Fraud is expressed via `campaign_id` + a bounded amount shift rather than timing/routing anomalies or new events.
5. **S4 labels are campaign‑driven and deterministic.** Collateral rules, posture‑based overrides, and stochastic delay sampling are not applied.
6. **S5 validation is metadata‑first.** Full data‑plane checks and RNG‑budget enforcement are replaced by sampled and parity‑based checks; WARN can still emit PASS.

---

## 5) Expectations before statistical analysis
Given the lean implementation posture, we should expect:
1. **Flow counts match arrival counts.** One flow per arrival in S2, so `flow_count ≈ arrival_count` per scenario.
2. **Event counts are exactly 2× flows.** Only auth request/response are emitted in baseline and in with‑fraud overlays.
3. **Fraud overlays do not change counts.** S3 should preserve flow and event counts; it only tags and optionally shifts amounts.
4. **Fraud rates align with campaign targets.** Campaign targeting should yield deterministic fractions consistent with quota models and clamp guardrails.
5. **Labels follow campaigns.** Truth labels should map cleanly from campaign types; flows without campaign_id should be LEGIT.
6. **Bank‑view signals are deterministic.** Outcomes should be stable for the same world/seed/config because hash‑deterministic rules are used.
7. **Case timelines are sparse and per‑flow.** A case is opened only when detection/review/dispute triggers it; no multi‑flow case grouping exists.

---

## 6) Implications for realism assessment
1. **Realism is policy‑driven, not emergent.** We should evaluate distributions against policy targets and guardrails rather than expecting natural variation.
2. **Event‑type realism is intentionally minimal.** Any assessment of refund/clearing realism will necessarily be “missing by design” in this lean build.
3. **Fraud realism is mostly signal‑injection.** The overlay is a tag + amount shift, so realism should focus on campaign coverage, targeting diversity, and label coherence rather than complex fraud mechanics.

---

## 7) Next step
Proceed to statistical realism assessment of the priority datasets listed above, starting with flow/event counts, campaign distributions, and label alignment.
