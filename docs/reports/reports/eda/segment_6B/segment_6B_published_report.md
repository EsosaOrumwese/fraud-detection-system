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

## 8) Statistical overview / summary (pre‑assessment snapshot)
Run scope: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer3\6B`

### 8.1 Primary datasets — row counts
| Dataset | Rows | Files | Partition keys | Partitions |
| --- | --- | --- | --- | --- |
| `s1_arrival_entities_6B` | 124,724,153 | 591 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s1_session_index_6B` | 124,647,685 | 1 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s2_flow_anchor_baseline_6B` | 124,724,153 | 591 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s2_event_stream_baseline_6B` | 249,448,306 | 591 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s3_campaign_catalogue_6B` | 6 | 1 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s3_flow_anchor_with_fraud_6B` | 124,724,153 | 591 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s3_event_stream_with_fraud_6B` | 249,448,306 | 1,090 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s4_flow_truth_labels_6B` | 124,724,153 | 591 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s4_flow_bank_view_6B` | 124,724,153 | 591 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s4_event_labels_6B` | 249,448,306 | 1,090 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |
| `s4_case_timeline_6B` | 287,408,588 | 591 | manifest_fingerprint, parameter_hash, scenario_id, seed | 1 |

### 8.2 Partition coverage
1. `scenario_id`: `baseline_v1`
2. `seed`: `42`

### 8.3 Derived ratios (sanity posture)
1. **Flows per arrival:** 1.0000 (S2 flows = S1 arrivals exactly)
2. **Events per flow:** 2.0000 (both baseline and with‑fraud event streams)
3. **Sessions per arrival:** 0.9994 → **Arrivals per session:** 1.0006
4. **Case‑timeline rows per flow:** 2.3044

Interpretation: these ratios are consistent with the lean implementation (one flow per arrival, two events per flow, no S3 count inflation). The case timeline density suggests that, on average, each flow that opens a case yields a small fixed sequence of case events rather than long multi‑event investigations.

## 9) Phase 0 — Policy‑Aligned vs Implementation‑Aligned Posture
This phase locks the **exact run scope**, maps **policy packs to the surfaces they should shape**, and establishes two baselines we will use for realism judgement:
1. **Policy‑aligned posture** (what the full spec intends), and
2. **Implementation‑aligned posture** (what the lean build actually produces).

### 9.1 Run scope (sealed world)
1. `manifest_fingerprint`: `c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8`
2. `parameter_hash`: `56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`
3. `seed`: `42`
4. `scenario_id`: `baseline_v1`

### 9.2 Policy packs → surfaces (authorities)
**S1 (Attachment + Sessionisation)**
1. `attachment_policy_6B.yaml` — entity attachment rules and requiredness per channel.
2. `behaviour_prior_pack_6B.yaml` — geo/channel preferences (home vs global, device/terminal bias, account/instrument/ip weights).
3. `sessionisation_policy_6B.yaml` — session key, timeouts, and stochastic boundary rules.
4. `behaviour_config_6B.yaml` — feature flags + guardrails (what is enabled).
5. `rng_policy_6B.yaml`, `rng_profile_layer3.yaml` — RNG families and keying.

**S2 (Baseline flows + events)**
1. `flow_shape_policy_6B.yaml` — flow counts, flow types, event templates, branch logic.
2. `amount_model_6B.yaml` — price points + tail distribution for amounts.
3. `timing_policy_6B.yaml` — event timing offsets.
4. `flow_rng_policy_6B.yaml` — RNG families and budgets.
5. `behaviour_config_6B.yaml` — feature flags (refunds, reversals, partial clearing).

**S3 (Fraud overlay)**
1. `fraud_campaign_catalogue_config_6B.yaml` — templates, quotas, schedules.
2. `fraud_overlay_policy_6B.yaml` — mutation constraints.
3. `fraud_rng_policy_6B.yaml` — RNG families.

**S4 (Truth + bank‑view labels)**
1. `truth_labelling_policy_6B.yaml` — fraud pattern → truth labels.
2. `bank_view_policy_6B.yaml` — auth/detect/dispute/chargeback probabilities.
3. `delay_models_6B.yaml` — detection/dispute/chargeback/case close delay distributions.
4. `case_policy_6B.yaml` — case grouping, timelines, guardrails.
5. `label_rng_policy_6B.yaml` — RNG families.

**S5 (Validation gate)**
1. `segment_validation_policy_6B.yaml` — required checks + realism corridors.

### 9.3 Policy‑aligned statistical posture (full‑spec intent)
**S1 — Attachment + sessionisation**
1. Party selection should be **home‑biased** by segment/channel (p_home ~0.65–0.99).
2. Instrument is optional for `BANK_RAIL`, required elsewhere.
3. POS/ATM should often use merchant terminals (terminal bias ~0.88 POS, ~0.97 ATM).
4. Session windows: hard timeout 20 mins, hard break 3 hours; stochastic boundary enabled.

**S2 — Baseline flows + events**
1. Multi‑flow sessions expected (1–3 flows per session with p={0.78,0.18,0.04}).
2. Flow types vary by channel (auth/clear, declines, step‑up, ATM, transfers).
3. Event templates include clearing, step‑up, refunds, reversals.
4. Amounts draw from discrete price points + lognormal tail.
5. Timing offsets govern auth→clear/refund events.

**S3 — Fraud overlay**
1. Six templates: CARD_TESTING, ATO, REFUND_ABUSE, MERCHANT_COLLUSION, PROMO_FRAUD, BONUS_ABUSE.
2. Quota models determine target counts; guardrails cap targets at 200k/seed‑scenario.
3. Mutation rules allow amount, time, routing changes (bounded by max multipliers).

**S4 — Labels + cases**
1. Truth labels map directly from fraud pattern type; unknown patterns should fail.
2. Bank‑view outcomes follow probabilistic auth/detect/dispute/chargeback rules.
3. Delays are heavy‑tailed (not fixed), with realism target ranges.
4. Case grouping is multi‑flow with 3‑day window and reopen gaps.

### 9.4 Implementation‑aligned statistical posture (lean build)
**S1**
1. Attachment is **deterministic hash‑based**; scoring + geo bias mostly bypassed if arrival lacks country.
2. Devices are limited to those with IP links; merchant terminal logic may be skipped.
3. Sessionisation uses **fixed bucketed windows**; stochastic boundary disabled.

**S2**
1. **One flow per arrival** (no multi‑flow sessions).
2. **Only two events per flow**: `AUTH_REQUEST` + `AUTH_RESPONSE`.
3. Amounts drawn deterministically from discrete price points; tails unused.
4. Timing uses arrival `ts_utc`; no offsets.

**S3**
1. Fraud overlay is **tags + bounded amount upshift** only (no new flows/events).
2. One deterministic campaign instance per template; targeting is hash‑based.
3. Filters/tactics requiring missing fields are skipped.

**S4**
1. Truth labels derive directly from campaign_id (no collateral/posture rules).
2. Bank‑view outcomes are deterministic hash‑draws; no RNG state.
3. Delays use fixed minimums, not sampled distributions.
4. Case timelines are **one‑case‑per‑flow** (no grouping).

**S5**
1. Validation is metadata‑first; realism corridors are WARN‑only and do not block PASS.

### 9.5 Interpretation for realism assessment
1. We will judge **statistical realism against the implementation‑aligned posture**, not the full‑spec posture, because the lean build intentionally omits several spec features (refunds, step‑ups, multi‑flow sessions).
2. Spec‑level gaps will still be documented as **design vs implementation deltas**, but they will not be treated as statistical failures if they are explicit lean tradeoffs.
3. Where policies define explicit targets (fraud prevalence, detection rates, case involvement ranges), those targets remain **binding for realism** even in the lean build and will be checked directly.
