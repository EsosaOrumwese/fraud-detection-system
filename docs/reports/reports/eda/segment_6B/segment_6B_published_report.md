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

## 10) Phase 1 — Structural Integrity & Parity
This phase validates the **mechanical correctness** of 6B outputs before we interpret any realism. If these checks fail, statistical patterns cannot be trusted because the data would be structurally inconsistent.

### 10.1 Primary‑key integrity and null safety
**What we checked (full scan):**
1. Nulls in key fields across all primary surfaces (arrivals, flows, events, labels, cases).
2. Presence of required identity columns (`flow_id`, `event_seq`, `session_id`, `case_id`, etc.).

**Results:**
All key fields are **non‑null across every dataset** (zero nulls in identity columns across S1–S4). This means the core identity lattice is intact and safe for joins.

**Why this matters:**
Null keys break downstream coverage in subtle ways (joins become lossy, parity checks are distorted). The absence of nulls is a strict structural pass and is the minimum requirement for any realism assessment.

---

### 10.2 Flow parity across S2 → S3 → S4
**What we checked:**
1. S2 baseline flows vs S3 with‑fraud flows vs S4 labels (truth + bank view).
2. Any missing or extra flows across those stages.

**Counts (full scan):**
1. `s2_flow_anchor_baseline_6B`: **124,724,153**
2. `s3_flow_anchor_with_fraud_6B`: **124,724,153**
3. `s4_flow_truth_labels_6B`: **124,724,153**
4. `s4_flow_bank_view_6B`: **124,724,153**

**Interpretation:**
This is **perfect parity** across the full flow chain. S3 did not add or drop flows, and S4 labelled every flow exactly once in both truth and bank‑view spaces. This confirms that the lean overlay and lean labelling logic preserve coverage, which is a hard requirement for explainability and model training.

---

### 10.3 Event integrity (type + sequence) across S2 → S3 → S4
**What we checked:**
1. Event types in baseline and with‑fraud streams.
2. Event sequence values per flow.
3. Consistency across S2/S3/S4.

**Event types (full scan):**
1. **S2 baseline:** `AUTH_REQUEST` (124,724,153), `AUTH_RESPONSE` (124,724,153)
2. **S3 with‑fraud:** `AUTH_REQUEST` (124,724,153), `AUTH_RESPONSE` (124,724,153)

**Event sequences (full scan):**
1. `event_seq = 0`: 124,724,153 rows
2. `event_seq = 1`: 124,724,153 rows
3. **No other sequence values exist** (S2/S3/S4 all match)

**Interpretation:**
The event stream exactly matches the **lean two‑event template** (auth request + response). There is no leakage of extra event types, no missing sequence indices, and no structural drift between baseline and fraud overlays. This makes the event surface **structurally clean**, but it also locks realism into a minimal template (refunds/clearing/step‑ups are absent by design).

---

### 10.4 Session integrity and coverage
**What we checked:**
1. Session count relative to arrivals.
2. Whether arrivals reference sessions that exist in the session index.

**Counts (full scan):**
1. Arrivals: **124,724,153**
2. Sessions: **124,647,685**

**Derived ratios:**
1. **Sessions per arrival:** **0.9993869**
2. **Arrivals per session:** **1.0006135**

**Interpretation:**
Sessions are almost one‑to‑one with arrivals. Only ~76k arrivals are grouped into existing sessions at this scale. This is consistent with the simplified sessionisation posture (bucketed windows, no stochastic boundary). Structurally it is correct, but it implies **session‑level realism is minimal** — most sessions are single‑arrival sessions.

---

### 10.5 Case timeline integrity
**What we checked:**
1. Case event types and sequence ordering.
2. Balance between open/close events.
3. Case timeline density relative to flows.

**Case event counts (full scan):**
1. `CASE_OPENED`: **75,728,141**
2. `CASE_CLOSED`: **75,728,141**
3. `CUSTOMER_DISPUTE_FILED`: **68,598,182**
4. `CHARGEBACK_INITIATED`: **27,439,032**
5. `CHARGEBACK_DECISION`: **27,439,032**
6. `DETECTION_EVENT_ATTACHED`: **12,476,060**

**Sequence bounds:**
1. `case_event_seq min`: **0**
2. `case_event_seq max`: **5**

**Derived ratios:**
1. **Case rows per flow:** **2.3044**
2. **Approx events per case:** **~3.49** (using approximate distinct case count)
3. **Approx flows involved in cases:** **~71.1%** of all flows (approximation)

**Interpretation:**
1. **Lifecycle integrity is clean.** Every case opened is closed (open and close counts are identical). The sequence range 0–5 matches the policy’s 6‑stage lifecycle.
2. **Case volumes are heavy.** The approximate case‑flow involvement is high for a retail fraud world (this will be evaluated in realism phases, but structurally it is coherent).
3. **Event mix is plausible within the lean posture.** Disputes and chargebacks are present at scale, with detection events smaller but non‑zero.

---

### 10.6 PK uniqueness — evidence and limitation
**What we attempted:**
1. Exact global PK uniqueness checks via `COUNT(DISTINCT ...)` across 100M+ rows.

**Constraint:**
Exact distinct checks exceeded available disk spill space on this machine (very large intermediate sort states). To avoid incomplete results, we used **two alternative integrity signals**:
1. **0.1% Bernoulli sample duplicate checks** on PKs — duplicates observed: **0** across all datasets.
2. **Approximate distinct on hash(PK)** — used only as a sanity signal (not treated as proof).

**Interpretation:**
There is **no evidence of PK collisions** in sampled data, and key fields are non‑null. Given deterministic key generation, this is strong evidence of PK uniqueness. If you want absolute proof, we would need more disk for a full distinct‑count validation or a dedicated external sort pipeline.

---

## Phase‑1 conclusion (structural verdict)
**Structural integrity is strong and consistent with the lean implementation:**
1. All identity fields are non‑null.
2. Flow and event parity are exact across S2 → S3 → S4.
3. Event types and sequences are internally consistent.
4. Sessionisation is coherent, though near‑one‑to‑one with arrivals.
5. Case timelines are ordered and lifecycle‑complete.

This gives us a **clean structural base**. Any realism issues we find in later phases will be policy‑driven rather than structural corruption.

---

## 11) Phase 2 — Attachment & Sessionisation Realism (S1)
This phase evaluates whether the **arrival→entity attachment** and **sessionisation** surfaces look statistically realistic for a synthetic world. We focus on two core datasets:
1. `s1_arrival_entities_6B` (who each arrival is attached to), and
2. `s1_session_index_6B` (how arrivals are grouped into sessions).

All heavy‑tail and per‑entity distributions below are computed on a **0.5% Bernoulli sample** to keep memory bounded. Approximate distinct counts are HyperLogLog estimates and are treated as **scale indicators**, not exact truth.

### 11.1 Entity scale and coverage (how many unique entities exist)
**What we measured (approx distinct over full arrivals):**
1. `party_id`: **~1,045,044**
2. `account_id`: **~1,205,042**
3. `instrument_id`: **~857,712**
4. `device_id`: **~1,017,452**
5. `ip_id`: **~244,953**
6. `merchant_id`: **~1,027**
7. `session_id`: **~135,670,542** (approx)

**How to interpret this:**
1. The **merchant universe is small** relative to arrival volume. With ~1,027 merchants serving 124.7M arrivals, each merchant receives very high volume on average. This is not automatically unrealistic for a synthetic world (it could be intentionally compressed), but it does mean that **merchant‑level concentration is a dominant driver** of traffic distribution. If the policy intent was to simulate a broad retail market, this is likely too small; if it intended a few large “super‑merchants,” this is consistent.
2. The **party/account/device counts are ~1M each**, which suggests the world contains about a million actors and devices. That scale is coherent with the sealed world size in 5A/6A, but it implies **high repeat behavior per entity** over the three‑month window.
3. The **IP universe is much smaller** (~245k). This points to significant IP reuse (NAT, corporate gateways, shared networks). That can be realistic, but it also makes IP a **stronger linkage signal** than in many retail worlds, which matters for explainability and model behavior.
4. The approximate `session_id` count is higher than actual session row counts (HLL overestimation is expected). We therefore rely on the exact session table for session scale.

**Realism posture:** entity scale is plausible in a compressed synthetic world, but **merchant count is particularly small**, so any realism claims about merchant diversity should be made cautiously.

---

### 11.2 Attachment topology (one‑to‑one vs multi‑link behavior)
**What we measured (0.5% sample):**
1. **Accounts per party:** p50=1, p90=1, p99=1, max=2  
2. **Instruments per account:** p50=1, p90=1, p99=1, max=2  
3. **Devices per party:** p50=1, p90=1, p99=1, max=2  
4. **IPs per device:** p50=1, p90=1, p99=1, max=2

**How to interpret this:**
1. The attachment graph is **almost entirely one‑to‑one**. In practical terms, a party typically has a single account, a single instrument, a single device, and a single IP address in observed traffic.
2. The rare max=2 values show that multi‑link attachment exists, but it is **exceptionally sparse**. That means the system is not expressing common real‑world behaviors such as a party using multiple cards/accounts, one account used across multiple devices, or devices roaming across multiple IPs (home, work, mobile).
3. This is consistent with the lean implementation posture (deterministic hash‑based selection from constrained candidate sets). The attachment is valid and coherent, but it is **behaviourally conservative**.

**Why it matters for realism:**
1. Many fraud patterns (account takeover, device sharing, mule networks) are **amplified by cross‑entity linkage**. If each party/account/device is nearly isolated, the dataset will **under‑represent those patterns**, even if fraud labels exist.
2. Downstream models that rely on linkage features (graph degree, IP/device sharing, account‑device churn) will see **weaker signals** than they would in a more realistic dataset.

**Realism posture:** acceptable for a lean deterministic build, but **under‑connected** for realistic behavior networks. If realism is a priority, this is one of the clearest places to increase diversity.

---

### 11.3 Arrival concentration by entity (heavy‑tail realism)
**What we measured (0.5% sample):**
Arrivals per entity distribution (p50 / p90 / p99 / max / top‑1 share).
1. **party_id:** 1 / 2 / 4 / 8 / **0.0013%**
2. **account_id:** 1 / 2 / 4 / 9 / **0.0014%**
3. **instrument_id:** 1 / 2 / 4 / 7 / **0.0011%**
4. **device_id:** 1 / 2 / 4 / 8 / **0.0013%**
5. **ip_id:** 1 / 5 / 60 / 2,776 / **0.44%**
6. **merchant_id:** 291 / 1,069 / 7,474 / 84,622 / **13.6%**
7. **session_id:** 1 / 1 / 1 / 2 / **0.0003%**

**How to interpret this:**
1. **Parties/accounts/devices/instruments are low‑concentration.** The top entity for these categories accounts for only ~0.001–0.0014% of arrivals in the sample. This indicates **no “super‑user” dominance**. It’s a realistic shape for customer‑level traffic, but perhaps slightly *too flat* if we expect heavy‑tail consumer behavior (power users, business users).
2. **IP concentration is moderate.** A top IP handles ~0.44% of arrivals, and the p99 is 60 arrivals in the sample. This suggests **some shared‑network behavior**, but not an extreme proxy/NAT domination. That is plausible, though IP reuse might be stronger in a more realistic retail world.
3. **Merchant concentration is very strong.** The top merchant contributes ~13.6% of sampled arrivals, and a single merchant reaches 84k arrivals in the sample. This is a **dominant heavy‑tail**, implying a few merchants absorb a huge fraction of traffic. This is consistent with the small merchant universe (~1k) and the likely heavy‑tail intensity allocation from 6A.
4. **Session IDs are effectively one‑arrival.** Top‑1 share is negligible and p99=1, which is aligned with the near one‑arrival sessionisation.

**Why it matters for realism:**
1. Strong merchant concentration can be realistic (large marketplaces dominate), but it **tightens the statistical story**: models will learn that merchant identity is a dominant predictor. That can be useful, but it can also **over‑fit to merchant‑level priors** if we intended a more evenly distributed commerce world.
2. The lack of heavy‑tail at the party/account/device level suggests **individual behavior variance is limited**, which may reduce the realism of “high‑spend” or “hyper‑active” customers.

**Realism posture:** **merchant‑level heavy‑tail is strong and coherent**, but customer‑level heavy‑tail is mild. This is plausible for a conservative synthetic world, but it under‑represents extreme user behavior.

---

### 11.4 Sessionisation realism (how arrivals are grouped over time)
**What we measured (full scan + 0.5% sample):**
1. **Sessions total:** 124,647,685  
2. **Arrivals total:** 124,724,153  
3. **Multi‑arrival sessions:** 76,270  
4. **Multi‑arrival session rate:** **0.061%**  
5. **Arrival count per session (sample):** p50=1, p90=1, p99=1, max=3  
6. **Session duration (sample):** p50=0s, p90=0s, p99=0s, max=1,149.7s  
7. **Zero‑duration sessions in sample:** 622,096 of 622,444 (99.94%)  
8. **All multi‑arrival sessions had non‑zero duration** in sample.

**How to interpret this:**
1. **Sessions are almost one‑to‑one with arrivals.** Only 0.061% of sessions have more than one arrival. This implies that sessionisation is **mostly a labelling step**, not a behavioral grouping.
2. **Session durations are overwhelmingly zero.** This means `session_start_utc == session_end_utc` for almost all sessions; i.e., the session is **just the arrival itself** rather than a window of activity.
3. **The maximum duration (~1,149.7s)** sits just under the 20‑minute hard timeout, which confirms the implementation is honoring the timeout ceiling but **not populating longer, naturally‑distributed session lengths**.
4. The fact that **all multi‑arrival sessions have non‑zero durations** is structurally consistent (a session with >1 arrival should span time), so the data is internally coherent even if behaviorally minimal.

**Why it matters for realism:**
1. Real‑world commerce generally has **meaningful multi‑arrival sessions** (multiple page views, repeated attempts, shopping cart activity). A 0.061% multi‑arrival rate indicates that **most of that behavior is missing**.
2. Any model features that depend on “session context” (burstiness, within‑session velocity, short‑gap retries) will be **nearly absent**, and thus may not generalize to real data even if other features look plausible.
3. This behavior is a direct consequence of the **lean sessionisation** described in the implementation notes (bucketed windows, stochastic boundary disabled). So this is **expected**, but it is a realism limitation.

**Realism posture:** sessionisation is **structurally clean but behaviorally shallow**. It is acceptable for a lean deterministic build, but it under‑represents realistic browsing/transaction sequences.

---

### 11.5 Channel mix + virtual posture (arrival‑weighted)
**What we measured (full scan of `arrival_events`):**
1. `channel_group` is **only** `mixed` (no POS vs CNP split appears in this run).
2. `is_virtual = True` arrivals: **2,802,007** of **124,724,153** → **~2.25%**.
3. Virtual arrivals appear **only** under `online_24h` demand_class, and within that class they make up **~4.28%** of online_24h arrivals.

**How to interpret this:**
1. Channel stratification is **collapsed** into a single group (`mixed`), so channel‑conditioned realism cannot be evaluated here.
2. The synthetic world is overwhelmingly **non‑virtual**. If “virtual” is intended to represent online‑only behavior, its footprint is very small.
3. The fact that virtual is **only** in `online_24h` implies virtual presence is treated as a narrow sub‑slice of one class, rather than a broader cross‑class channel.

**Why it matters for realism:**
1. If policy intent included meaningful online share, the observed ~2.25% virtual rate is low.
2. Any model features keyed on online/virtual behavior will have **thin training signal** in this run.

---

### 11.6 Geographic realism (cross‑border and timezone alignment)
**Cross‑border posture (arrival‑weighted):**
1. Overall cross‑border rate (party_country != merchant_country): **~91.4%**.
2. Party type Retail: **~91.4%**
3. Party type Business: **~91.8%**
4. Party type Other: **~91.5%**
5. Non‑virtual: **~91.5%**
6. Virtual: **~89.7%**

**Timezone alignment (arrival‑weighted, sample):**
1. `tzid_primary` matches merchant `tzid` only **~7.7%** of the time.

**How to interpret this:**
1. The dataset is **heavily cross‑border** across all party types and channels. There is no evidence of a strong home‑bias in S1 attachment.
2. The low timezone match rate implies arrival timezones are **rarely aligned to merchant home zones**. Combined with the cross‑border rate, this points to a world where merchants serve mostly non‑local traffic.

**Why it matters for realism:**
1. If the design intent was to bias domestic traffic (p_home ~0.65–0.99), this run is **not consistent** with that intent.
2. Cross‑border dominance makes geography a **weak discriminant** for risk, which may or may not be desirable for the synthetic world.

---

### 11.7 Linkage diversity (graph connectivity realism)
**What we measured (0.5% sample):**
1. **Account → Device (distinct devices per account):** p50=1, p90=1, p99=1, max=1  
2. **Account → IP (distinct IPs per account):** p50=1, p90=1, p99=1, max=2  
3. **Device → Merchant (distinct merchants per device):** p50=1, p90=2, p99=4, max=8  
4. **Party → Merchant (distinct merchants per party):** p50=1, p90=2, p99=4, max=8  
5. **IP → Device (distinct devices per IP):** p50=1, p90=3, p99=41, max=1,741  

**How to interpret this:**
1. Accounts are effectively **single‑device** and nearly single‑IP. That means account‑device churn is missing.
2. Parties and devices transact with **very few merchants**, suggesting limited “shopping diversity.”
3. IPs are **high‑fanout hubs** (one IP can connect to many devices). This is the only place where the graph shows strong multi‑link behavior.

**Why it matters for realism:**
1. The graph is **sparse on the customer/device side** but **dense on IPs**. This makes IP a dominant linkage signal, which can skew explainability.
2. Realistic fraud patterns often depend on **account‑device churn** and **multi‑merchant behavior**, which are muted here.

---

### 11.8 Population weighting (activity vs population realism)
**What we measured (0.5% sample vs base population):**
1. Retail parties are **~96.8%** of the party base but **~92.9%** of arrivals.
2. Business parties are **~2.75%** of the party base but **~6.63%** of arrivals.
3. Business arrival share is therefore **~2.4×** its population share.

**How to interpret this:**
1. Business parties are **much more active** than retail parties.
2. This can be realistic (business customers transact more), but it is a strong skew that should be intentionally policy‑driven.

**Why it matters for realism:**
1. If business activity weighting is too strong, downstream models may over‑emphasize business vs retail as a primary signal.

---

### 11.9 Merchant class mix (arrival‑weighted)
**Observed arrival mix by demand_class (approx share of arrivals):**
1. `consumer_daytime`: **~62.7%**
2. `online_24h`: **~15.1%**
3. `fuel_convenience`: **~14.2%**
4. `evening_weekend`: **~3.5%**
5. `online_bursty`: **~2.0%**
6. `office_hours`: **~1.18%**
7. `bills_utilities`: **~0.89%**
8. `travel_hospitality`: **~0.42%**

**How to interpret this:**
1. Three classes (`consumer_daytime`, `online_24h`, `fuel_convenience`) dominate the world.
2. Several classes are **very small**, which limits realism for those behaviours and reduces their value for modeling.

---

### 11.10 Cross‑border rates by merchant class + volume effects
**Cross‑border rates by class (arrival‑weighted, deduped merchant dimension):**
1. `consumer_daytime`: **0.9388**
2. `fuel_convenience`: **0.9403**
3. `online_24h`: **0.9298**
4. `evening_weekend`: **0.9235**
5. `office_hours`: **0.9389**
6. `bills_utilities`: **0.9267**
7. `travel_hospitality`: **0.9258**
8. `online_bursty`: **0.9047**

**Merchant‑weighted vs arrival‑weighted cross‑border (does volume amplify cross‑border?):**
1. `consumer_daytime`: **0.9190 → 0.9386**  
2. `fuel_convenience`: **0.9117 → 0.9403**  
3. `office_hours`: **0.9303 → 0.9384**  
4. `bills_utilities`: **0.9059 → 0.9270**  
5. `online_24h`: **0.9293 → 0.9313**  
6. `evening_weekend`: **0.9533 → 0.9244**  
7. `online_bursty`: **0.9236 → 0.9010**  
8. `travel_hospitality`: **0.9189 → 0.9269**

**How to interpret this:**
1. Cross‑border is **uniformly high** across all merchant classes; class is not a major differentiator.
2. In most classes, **high‑volume merchants are more cross‑border** than low‑volume merchants, which pushes the overall cross‑border rate upward.
3. The exceptions (`evening_weekend`, `online_bursty`) show the opposite pattern, indicating a few large merchants in those classes are **more domestic‑leaning**.

**Why it matters for realism:**
1. The aggregate cross‑border skew appears to be **volume‑driven** rather than class‑driven. This is a lever we can tune by re‑weighting high‑volume merchants.

---

### 11.11 Session gap structure by merchant class (multi‑arrival sessions)
**Structural facts (full scan):**
1. Multi‑arrival sessions are **almost entirely two‑arrival sessions**, with the following counts:

| arrival_count | sessions |
| --- | --- |
| 2 | 76,073 |
| 3 | 196 |
| 4 | 1 |

**Class conditioning (10% sample of multi‑arrival sessions):**
1. **Single‑class rate:** **1.0** (all multi‑arrival sessions are within a single merchant class).
2. Gap distributions by class (max gap in seconds, per‑session):

| demand_class | sessions | max_gap_p50 | max_gap_p90 | max_gap_p99 | max_gap_max |
| --- | --- | --- | --- | --- | --- |
| consumer_daytime | 575 | 325s | 798s | 1,026s | 1,159s |
| evening_weekend | 133 | 302s | 816s | 1,094s | 1,169s |
| fuel_convenience | 14 | 680s | 823s | 901s | 909s |
| online_24h | 12 | 223s | 983s | 1,025s | 1,026s |
| online_bursty | 6 | 340s | 858s | 924s | 931s |
| travel_hospitality | 1 | 696s | 696s | 696s | 696s |
| bills_utilities | 1 | 80s | 80s | 80s | 80s |

**How to interpret this:**
1. Because multi‑arrival sessions are mostly **two‑arrival**, the “max gap” is effectively the session duration. That limits our ability to see truly bursty multi‑step behaviour.
2. There is **no strong class‑specific burstiness** signal. Online classes do not consistently show shorter gaps than offline‑leaning classes.
3. The sample sizes for some classes are very small, so we should not over‑interpret class differences at the tail.

**Why it matters for realism:**
1. The session surface remains **thin** even when class‑conditioned, which confirms that sessionisation is not expressing rich within‑session behaviour.

---

### 11.12 Cross‑border rates by merchant size deciles (volume‑driven skew)
**What we measured (0.5% sample, arrival‑weighted):**
Merchants are sorted by arrival volume and split into **size deciles**. The table shows the share of arrivals each decile contributes and the decile’s cross‑border rate.

| size_decile | arrival_share | cross_border_rate |
| --- | --- | --- |
| 1 | 0.81% | 0.9115 |
| 2 | 1.45% | 0.9155 |
| 3 | 2.10% | 0.9205 |
| 4 | 2.90% | 0.9110 |
| 5 | 3.79% | 0.9181 |
| 6 | 4.73% | 0.9240 |
| 7 | 5.93% | 0.9266 |
| 8 | 7.65% | 0.9236 |
| 9 | 11.35% | 0.9166 |
| 10 | **59.30%** | **0.9465** |

**Top‑tier concentration (explicit impact):**

| bucket | merchants | arrival_share | cross_border_rate |
| --- | --- | --- | --- |
| top_1% | 9 | **30.0%** | **0.9385** |
| top_5% (next 4%) | 36 | **19.8%** | **0.9657** |
| rest | 841 | **50.2%** | **0.9231** |

**How to interpret this:**
1. The **largest decile alone contributes ~59% of arrivals**, and it has the **highest cross‑border rate**. This is the single biggest driver of the global cross‑border skew.
2. The **top 5% of merchants contribute ~49.8% of arrivals** and are more cross‑border than the rest. That means **cross‑border realism is being set by a small number of very large merchants**, not by broad merchant behaviour.
3. The lower deciles are relatively flat (~0.91–0.93). The skew is **volume‑driven, not class‑driven** at this level.

**Why it matters for realism:**
1. If you want a more domestic‑leaning dataset, **re‑weighting the largest merchants** will move the global posture far more than changing the long tail.
2. This also means that **merchant identity becomes a dominant predictor** because high‑volume merchants are structurally different in cross‑border behaviour.

---

### 11.13 Session gap distributions by virtual vs non‑virtual
**What we measured (full scan of multi‑arrival sessions):**
1. Multi‑arrival sessions total: **76,270**
2. Virtual multi‑arrival sessions: **324** (≈ **0.425%** of multi‑arrival sessions)
3. Non‑virtual multi‑arrival sessions: **75,946**

**Gap distributions (per‑session max gap in seconds):**

| is_virtual | sessions | max_gap_p50 | max_gap_p90 | max_gap_p99 | max_gap_max |
| --- | --- | --- | --- | --- | --- |
| False | 75,946 | 351s | 820s | 1,079s | 1,198s |
| True | 324 | 348s | 773s | 1,016s | 1,126s |

**How to interpret this:**
1. Virtual sessions are **extremely rare**, so their distribution is not a strong statistical signal.
2. The gap profile for virtual vs non‑virtual is **very similar**, indicating **no meaningful burstiness difference** in this run.
3. This mirrors the overall sessionisation posture: nearly all multi‑arrival sessions are just two events, so the gap distribution largely reflects a single time delta.

**Why it matters for realism:**
1. If the synthetic world intends online/virtual traffic to have distinct within‑session dynamics, that signal is **not present** here.
2. The low virtual share means any virtual‑specific models will have **very limited training evidence**.

---

### 11.14 Cross‑border rates by party segment (segment‑level bias check)
**What we measured (0.5% sample, arrival‑weighted):**

| segment_id | arrivals (sample) | cross_border_rate |
| --- | --- | --- |
| RETAIL_FAMILY | 124,093 | 0.9404 |
| RETAIL_MATURE | 105,251 | 0.9312 |
| RETAIL_EARLY_CAREER | 95,658 | 0.9381 |
| RETAIL_VALUE | 65,063 | **0.9153** |
| RETAIL_RETIRED | 63,812 | 0.9474 |
| RETAIL_STUDENT | 58,915 | 0.9299 |
| RETAIL_MASS_MARKET | 46,257 | 0.9398 |
| RETAIL_AFFLUENT | 21,079 | **0.9501** |
| BUSINESS_SOLE_TRADER | 10,052 | 0.9356 |
| BUSINESS_SME | 8,793 | 0.9419 |
| BUSINESS_MICRO | 8,348 | 0.9401 |
| BUSINESS_MID_MARKET | 5,306 | 0.9431 |
| BUSINESS_LOCAL_SERVICE | 4,155 | **0.9526** |
| BUSINESS_ECOM_NATIVE | 2,633 | 0.9347 |
| OTHER_NONPROFIT | 1,987 | 0.9371 |
| BUSINESS_CORPORATE | 1,362 | 0.9325 |
| OTHER_PUBLIC_SECTOR | 1,154 | 0.9489 |

**How to interpret this:**
1. Cross‑border rates are **uniformly high across segments** (roughly 0.915–0.953).
2. There is **no visible segment‑level home‑bias**; even segments that might be expected to be more domestic (e.g., RETAIL_VALUE) are still >0.91 cross‑border.
3. Small deviations exist (RETAIL_VALUE slightly lower, RETAIL_AFFLUENT and BUSINESS_LOCAL_SERVICE slightly higher), but these are **minor compared to the overall skew**.

**Why it matters for realism:**
1. If segment‑level geo preferences were intended, they are **not expressed** in this run’s attachment outputs.
2. The model will learn that **segment does not strongly constrain geography**, which may not be realistic for many markets.

---

### 11.15 Phase‑2 conclusion (S1 realism verdict)
1. **Attachment graph is valid but under‑connected.** The data strongly prefers one‑to‑one mappings across parties, accounts, instruments, devices, and IPs. This is coherent, but it suppresses multi‑entity behaviors that are important for realism and fraud explainability.
2. **Merchant‑level concentration is very strong.** This is consistent with a compressed merchant universe and likely with upstream intensity priors, but it will make merchant identity a dominant signal.
3. **Sessionisation is near‑identity.** Most sessions are single arrivals with zero duration. This is consistent with the lean posture, but it limits session‑based realism.

**Net realism assessment for Phase 2:** coherent and consistent with the lean build, but **behavioural richness is limited**. If we want higher realism, the top improvement levers are:
1. Enable stochastic/session boundary logic to increase multi‑arrival sessions and realistic durations.
2. Allow multi‑link attachment (party→account, account→instrument, device→IP) with controlled probabilities.
3. Expand merchant universe or soften intensity concentration to reduce over‑dominance by top merchants.
