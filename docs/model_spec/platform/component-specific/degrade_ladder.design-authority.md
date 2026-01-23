# Degrade Ladder Design Authority

This file is a rough collection of design or brainstorm notes for the Degrade Ladder. It views the whole platform as a network and expands open the degrade ladder's position in this network and illuminates it.

---

Alright — we’ll treat **DL’s inner network as opaque** for now and pin **DL’s role + outer behavior** as a vertex in the larger platform graph, so the internal design later has a clear target to satisfy.

Everything below is **design-authoritative** unless it contradicts your already-pinned platform laws (those still win).

---

## DL’s role in the platform network

### Where DL sits

DL is a **hot-path control-plane module** inside the Real-Time Decision Loop:

`EB → (IEG, OFP, DL) → DF → AL → DLA`

### What DL is system-of-record for

DL is the **single authority** for:

* `degrade_mode`
* `capabilities_mask`
* `provenance` explaining *why* that posture was chosen

### What DL is NOT

DL does **not** decide fraud outcomes, compute features, validate events, or execute actions. It only **constrains** what DF is allowed to do.

---

## DL’s adjacency map (external edges + obligations)

### Inputs into DL

1. **Obs/Gov pipeline → DL**: DL consumes health signals (windowed snapshots), at minimum:

* OFP latency/error/lag
* IEG latency/error
* model serving / DF runtime latency/error
* EB consumer lag (and optionally IG/ingestion lag)

2. **Policy profile store → DL**: DL loads **threshold/corridor profiles** as *policy config* (versioned + auditable). DL must report which `policy_rev` it used.

### Outputs from DL

3. **DL → DF (J9)**: DL returns a **DegradeDecision** used at decision time.

4. **DF → DLA (J12)**: DF must embed/record the degrade posture it actually used so audit and later learning can reconstruct “what was allowed at that moment.”

5. **DL → (optional) bus.control.v1**: DL may emit low-volume control facts when posture changes (for ops/visibility), but DF must still record the decision it used.

---

## The J9 handshake: DL ↔ Decision Fabric

This is the **core contract of DL in the network**.

### What crosses the join (authoritative)

A **DegradeDecision** that is:

* explicit
* deterministic
* recordable/auditable
  and contains: `mode`, `capabilities_mask`, `provenance`, `decided_at_utc` (optional deterministic `degrade_decision_id`).

### DF’s non-negotiable obligations (pinned)

* DF treats `capabilities_mask` as **hard constraints**: if a capability is off, DF behaves as if that tool/model/action **doesn’t exist**.
* DF must **explicitly record** degrade posture in decision provenance (therefore in audit).
* If DL is unavailable/can’t decide, DF fails **toward safety** (stricter posture) and records that fallback.

### What DF “passes” to DL (design-level, not a spec)

To make DL usable without hidden assumptions, DF’s request should at least include:

* `event_time_utc` (the decision boundary time DF is operating under; avoids “hidden now” drift)
* optionally a **latency/SLO tier** (if you want DL to choose stricter posture for low-latency requests; optional v0) 

(We are not defining request schemas here — just pinning the semantic need: the decision boundary time must be explicit.)

---

## DL’s output semantics DF must obey

### Designer-locked v0 modes (ordered)

I’m locking the v0 ladder as:

`NORMAL → DEGRADED_1 → DEGRADED_2 → FAIL_CLOSED`

### Capabilities mask: what it *means* in the network

I’m also locking the v0 mask fields (because DF needs stable knobs):

* `allow_ieg`
* `allowed_feature_groups[]`
* `allow_model_primary`
* `allow_model_stage2`
* `allow_fallback_heuristics`
* `action_posture` (`NORMAL` | `STEP_UP_ONLY`)

And here is the **outer-network meaning** (how it constrains joins):

* **IEG join (DF ↔ IEG)**: if `allow_ieg=false`, DF must not call IEG at all (no “best effort”).
* **OFP join (DF ↔ OFP)**: DF may only request/use feature groups in `allowed_feature_groups` (if the mask restricts them).
* **Model execution inside DF**:

  * if `allow_model_primary=false`, DF must not run the primary model
  * if `allow_model_stage2=false`, DF must not run stage-2/escalation models
* **Fallback behavior**: if `allow_fallback_heuristics=false`, DF cannot “invent” a heuristic path; it must follow fail-safe posture and record missing capability.
* **Actions posture (DF → AL)**:

  * `NORMAL`: DF may emit the full action policy it would normally emit
  * `STEP_UP_ONLY`: DF may only emit *safer / more conservative* actions (no risky automation)

> This is how DL shapes the **whole loop** without touching other components directly: it constrains what DF is allowed to do at each join.

---

## DL’s evaluation posture as seen by the rest of the system

### Determinism + stability rules (outer guarantees)

Regardless of how DL is implemented internally, it must behave like:

* same signal snapshot + same policy profile ⇒ same `mode` and `mask`
* **downshift immediate**, **upshift only after quiet period**, one rung at a time
* missing/stale required signals are treated as unhealthy (contribute to downshift / block upshift)
* if DL cannot evaluate safely (policy missing/internal error), it outputs **FAIL_CLOSED** with provenance noting evaluation failure

### “Current posture” state

Operationally, DL maintains a **current posture** in a small `dl` store; it’s **derived/rebuildable** (not a primary truth).

This matters to the outer network because it enables:

* fast reads by DF
* hysteresis memory (quiet period / anti-flap) without inventing hidden coupling

---

## Recording & replay: why DL must be explicit

DL isn’t just an ops safety valve — it is part of the platform’s replay story:

* Decision provenance must include degrade posture so you can rebuild “what the system could have done” later.
* Learning/offline replay depends on “rebuild targets” including degrade posture at decision time.

So DL’s outer contract is not “choose a mode”; it is “choose a mode **and make it reconstructible**.”

---

## Policy/config governance around DL (outer network interface)

Because degrade thresholds/corridors are outcome-affecting, they are **policy config**:

* versioned artifact
* promoted via propose → approve → activate
* rollback exists
* DL must report the `policy_rev` it used in provenance/logs

Optional but aligned with your Run/Operate + governance pins:

* a config activation emits a governance fact (bus.control or `gov/…`) so “what rules were in force” is always answerable.

---

## Two canonical runtime sequences (outer behavior)

### 1) Decision-time use (J9)

`DF decision request/event → DL DegradeDecision → DF obeys → DF records → DLA persists`

### 2) Posture computation loop

`Obs signals + policy_rev → DL computes posture (with hysteresis) → updates dl.current_posture → (optional) emits posture-change fact`

---

Yes — there are a **small handful of DL “pre-join pins”** that are worth locking *before* we talk edges/handshakes, because they determine what the joins even mean. I’ll pin them now (designer-authoritative) and assume they stand unless you override.

## DL pre-join pins to lock now

### DL-PIN-01 — DL’s one-line mission + single-authority output

DL exists to select **“what level of service is safe right now”** and make it **explicit, deterministic, and auditable** via a single output object:
`DegradeDecision { mode, capabilities_mask, provenance, decided_at_utc }`.

### DL-PIN-02 — Mode vocabulary and ordering

We lock a simple ordered ladder (more degraded = safer):
`NORMAL → DEGRADED_1 → DEGRADED_2 → FAIL_CLOSED`.

### DL-PIN-03 — CapabilityMask vocabulary (the knobs DL controls)

We lock the *fields* DF must obey as hard constraints:
`allow_ieg`, `allowed_feature_groups[]`, `allow_model_primary`, `allow_model_stage2`, `allow_fallback_heuristics`, `action_posture`.

(Exact per-mode mapping can be refined later; but the *control surface* must be stable early.)

### DL-PIN-04 — Determinism + tie-break rule

Given the same **signal snapshot + policy profile**, DL must choose the same mode, and if multiple rungs are eligible it selects **the most degraded eligible** rung (safe, deterministic).

### DL-PIN-05 — Stability posture (anti-flap / hysteresis)

Lock the transition posture:

* **Downshift:** immediate when breached
* **Upshift:** only after a quiet period, **one rung at a time**
* **Missing/stale signals:** treated as unhealthy (can downshift; block upshift)

### DL-PIN-06 — Scope model (what DL decides *for*)

DL produces a decision for a **declared scope**, at minimum `manifest_fingerprint` (always present on the canonical envelope), and optionally narrower when pins exist (`parameter_hash/seed/scenario_id/run_id`).

This pin prevents later confusion about whether a single global mode should punish all worlds/runs.

### DL-PIN-07 — Policy/profile governance is part of the output

DL’s thresholds/corridors are **policy config** → versioned, auditable, and DL must cite the **policy revision** used in its provenance (so “what rules were in force?” is always answerable).

### DL-PIN-08 — Runtime shape (so joins have a concrete target)

DL is an always-on (or periodic) **evaluator unit** that:

* reads signals from the obs pipeline,
* maintains **`dl` current posture** in a small derived store,
* optionally emits posture-change facts to `fp.bus.control.v1`.

This doesn’t yet choose *how* DF queries it (API vs read-store vs consume control stream) — but it pins that DL is an evaluator with a current posture surface.

---

## What I would *not* pin yet (safe to defer)

* Exact numeric thresholds/corridors (config). 
* Exact metric aggregation choices (p95 vs p99 plumbing), scrape vs push.
* Whether DL supports “manual force mode” (incident override) — we can decide after we see the join story with governance/control.

---

Yes. If we treat **DL as an opaque vertex**, a production-ready platform still forces a very specific set of **external joins (edges), composite paths, and feedback loops** around it.

Below is the **full DL-centric “outer network”** that exists (or is explicitly allowed) in your pinned platform design.

---

## 1) All direct joins touching DL

### Inputs to DL

1. **Obs pipeline → DL**
   DL consumes *signals* (golden signals + lag/watermark signals) for the hot-path services (OFP, IEG, DF/model serving, EB consumer lag; optionally IG/ingestion lag).

2. **Policy/profile store → DL**
   DL consumes **threshold/corridor profiles** as *policy config*; these are versioned, governed, and DL must be able to cite the active `policy_rev`.

3. **Governance facts stream → (operators/RO) → policy activation → DL (indirect)**
   DL doesn’t need a bespoke “admin API” to change behavior: in your platform, **outcome-affecting changes are facts** (propose → approve → activate), so DL’s behavior changes when a new policy rev becomes active.

### Outputs from DL

4. **DL → DF (J9)**
   The primary join: DL produces an explicit **DegradeDecision** (`mode`, `capabilities_mask`, provenance, timestamp / optional id) and DF must treat the mask as **hard constraints** and record what it used.

5. **DL → dl state store**
   DL persists “current posture” (derived, rebuildable) for low-latency reads and hysteresis continuity.

6. **DL → fp.bus.control.v1 (optional)**
   DL may emit low-volume control facts on posture change (for visibility + cache invalidation patterns), but DF still must record the DegradeDecision actually used at decision time.

> Those are the **only “true direct edges”** around an opaque DL in a production platform under your pins.

---

## 2) All composite paths DL participates in (production reality)

These are “multi-hop” paths where DL is a node in the route, even if not directly wired to every hop.

### Path A — Normal decision-time path (hot loop)

`EB (facts) → DF (decision request) → (J9) DL → DF → (J8) OFP → DF → (J11) AL → (J12) DLA`

Why DL is in the middle: DF must obey degrade constraints while choosing whether it can query OFP/IEG, run certain models, or emit certain actions.

### Path B — Bundle resolution path (degrade constrains “what can run”)

`DF → (J9) DL → DF → (J10) Registry resolution (compat-aware incl. degrade constraints) → DF`

This is an important “hidden” path: registry resolution must be compatible with both feature version availability *and* degrade constraints; otherwise fail closed / safe fallback.

### Path C — Feature acquisition path under constraints

`DF → DL → DF → OFP get_features(as_of_time=event_time) → DF`
DL gates which feature groups DF is even allowed to request/use; DF must record snapshot provenance and degrade posture together for replay.

### Path D — Identity/context path under constraints

`DF → DL → DF → IEG (query or use graph_version) → DF`
If the mask forbids IEG usage, DF must behave as if IEG “doesn’t exist” for that decision, and record that constraint.

### Path E — Degrade posture observability path (control-plane visibility)

`DL posture change → fp.bus.control.v1 → Obs/Gov dashboards/alerts (+ optionally DF cache invalidation)`

### Path F — Audit reconstruction path

`DLA records (decision provenance incl. degrade posture) → investigations / offline analysis / parity tooling`
The key requirement is that “what mode/mask was used” is reconstructible from audit records (decision log is your flight recorder).

### Path G — Policy-change propagation path (governed change)

`Operator/automation proposes new DL threshold profile → approve → activate (governance fact) → DL loads new policy_rev → subsequent decisions cite new rev`

---

## 3) All feedback loops involving DL (the “production loops”)

These are the loops you get automatically in a real system—worth naming because they drive stability/hysteresis requirements.

### Loop 1 — Load-shedding loop (OFP)

`OFP latency/errors/lag → (Obs) → DL downshift → DF reduces OFP usage/feature groups → OFP load drops → metrics improve → DL upshift (after quiet period)`

### Loop 2 — Load-shedding loop (IEG)

`IEG availability/latency → DL → DF stops calling IEG (mask) → IEG load stabilizes → metrics improve → DL upshift`

### Loop 3 — Throughput loop (EB consumer lag / applied offsets)

`EB consumer lag / watermark drift → DL downshift → DF reduces compute (models/features) → DF catches up → lag improves → DL upshift`
This aligns with your “watermarks are the universal progress token” posture; lag/watermark signals are first-class.

### Loop 4 — Model/runtime loop (DF/model serving)

`model latency/error → DL → DF disables heavy model stage(s) / fallback posture → runtime stabilizes → DL upshift`

### Loop 5 — Action risk loop (AL)

Even if AL health isn’t a primary signal in v0, the loop exists operationally:
`action execution failures/latency → (Obs) → DL action_posture becomes conservative → AL load/risk drops → stability returns`
This fits your platform’s “actions are governed + auditable” posture (policy-controlled execution).

### Loop 6 — Governance tuning loop (humans + policy)

`DL posture events + decision/audit outcomes → operators adjust thresholds/corridors (new policy rev) → DL behavior changes under governed change control`

---

## 4) Two *allowed* DL consumption patterns (still opaque, but impacts paths)

Your own conceptual constraints allow either, *without changing semantics*:

* **Inline/per-request**: DF asks DL each time (J9 is a synchronous join).
* **Periodic + caching**: DL computes posture periodically, writes `dl.current_posture`, optionally emits control events; DF reads/caches.

Either way, **DF must record the DegradeDecision (or a resolvable linkage) it used**.

---

## 5) The minimal “complete set” summary (so nothing is missed)

If you want a single checklist: in a production-ready platform under your pins, DL necessarily participates in:

* **3 inbound channels**: obs signals, policy profile, governed activation (indirect).
* **3 outbound surfaces**: J9 to DF, persisted current posture, optional control events.
* **at least 7 composite paths** (decision, bundle resolution, OFP/IEG constrained calls, observability, audit reconstruction, policy-change propagation).
* **at least 6 real feedback loops** (OFP/IEG/EB lag/model runtime/action risk/governance tuning).

---

Here’s the **ordered expansion list** for **DL-as-opaque** in a production platform (joins first, then paths, then loops).

## A) Joins to expand first (direct edges)

1. **DL → DF**: `DegradeDecision` (mode + capabilities_mask + provenance).
2. **DF → DLA**: record the **exact degrade posture used** per decision (so audit/replay is reconstructible).
3. **Policy/Profile store → DL**: threshold/corridor profiles (policy_rev governed + cited).
4. **Obs/Gov signals → DL**: health snapshots (OFP/IEG/model/EB lag, etc.).
5. **DL → dl posture state**: derived “current posture” + hysteresis memory (rebuildable).
6. **DL → fp.bus.control.v1** (optional): posture-change facts for visibility/cache invalidation.
7. **DL → optional consumers** (optional): OFP/others may *read* mode for internal posture (must remain explicit, not stealth coupling).

## B) Paths to expand second (multi-hop routes DL participates in)

8. **Hot decision path**: `EB → (IEG/OFP/DL) → DF → AL → DLA`.
9. **Feature acquisition under constraints**: `DF (uses DL mask) → OFP → DF (records provenance)`.
10. **Identity context under constraints**: `DF (uses DL mask) → IEG → DF (records graph_version)`.
11. **Bundle resolution under constraints**: `DF (uses DL mask) → Registry → DF (compat-aware; fail-closed if incompatible)`.
12. **Control-plane visibility path**: `DL posture-change → control bus → Obs dashboards/alerts`.
13. **Audit reconstruction path**: `DLA → investigations/offline parity tooling` (replay “what was allowed then”).
14. **Governed policy-change path**: `propose→approve→activate policy_rev → DL loads → DF decisions cite rev`.

## C) Loops to expand last (feedback loops that exist in production)

15. **OFP load-shedding loop** (OFP health → DL downshift → DF reduces OFP usage → OFP recovers → DL upshift).
16. **IEG load-shedding loop** (IEG health → DL → DF stops IEG calls → recovery → upshift).
17. **EB lag/backpressure loop** (consumer lag → DL → DF reduces compute → lag improves → upshift).
18. **Model/runtime loop** (latency/error → DL → DF disables heavy stages → recovery → upshift).
19. **Action-risk loop** (execution failures → DL action_posture conservative → fewer risky actions → stability).
20. **Governance tuning loop** (DL posture history + outcomes → humans adjust thresholds → new policy_rev).

---

Great — we’ll expand the **four production joins** (DL still opaque), and for each one I’ll pin: **what crosses**, **what it means**, **who is responsible for what**, **freshness/staleness rules**, and **failure posture** (so there are no hidden assumptions).

---

## 1) Join: DL → DF (J9) — DegradeDecision delivery

### What crosses the join (hard pin)

A **DegradeDecision** that is **explicit, deterministic, and recordable**:
`mode + capabilities_mask + provenance + decided_at` (optional deterministic decision id). 

### Why this join exists (DL’s outer authority)

DL is not “advice”; it is **the platform’s safety posture selector**. DF must treat `capabilities_mask` as **hard constraints** (“tool doesn’t exist if disabled”). 

### How DF consumes it (two allowed patterns; same semantics)

DL can be consumed either way without changing meaning:

**Pattern A — inline read:** DF asks DL for a DegradeDecision at decision-time (per request).
**Pattern B — read-from-posture:** DL continuously evaluates and writes `dl.current_posture`; DF reads/caches that decision object.

Either is compatible with the platform, *but* the invariants below must remain identical.

### Freshness (pin: “no silent staleness”)

DL’s output must include **`decided_at_utc`**, and DF must apply a **max-age rule**:

* If the DegradeDecision is **older than `max_decision_age`** (policy-config), DF treats it as **untrusted** and fails toward safety (see below).
* “Max-age” is not a vendor detail; it’s the semantic guardrail that prevents DF from acting under a posture that might no longer be safe.

(We’re not picking the number here; we’re pinning the existence of the rule.)

### Failure posture (platform-pinned)

If DL is unavailable or cannot produce a decision, DF fails **toward safety** and records that fallback.

**Designer pin for v0 fallback:**
If DL is unavailable/invalid/stale → DF behaves as if the decision were `FAIL_CLOSED` for that decision and records `degrade_source = FALLBACK_DUE_TO_DL_UNAVAILABLE`.

This is consistent with “fail safe” and prevents silent “best effort” operation.

### Determinism surface (so audit/replay can trust it)

We pin that DL’s DegradeDecision can optionally carry a deterministic id (hash of the decision payload) so DF can reference it stably in logs/audit. This is explicitly allowed by your join text. 

### Scope pin (so the join can be correct in multi-run/world reality)

DF’s request to DL is **always for an explicit scope**, at minimum the platform’s ContextPins (or a declared “GLOBAL” scope), and DL’s decision must state which scope it applies to.

Reason: OFP/IEG/DF can be unhealthy in a scoped way; the join must not force everything into one global posture unless you explicitly decide “DL is global-only.”

(We can later decide how “global vs scoped” is evaluated internally; for the join we just pin: **scope is explicit**.)

---

## 2) Join: DF → DLA (J12) — record the exact degrade posture used

### What crosses the join (hard pin)

DLA receives **the minimum immutable facts needed to reproduce/justify a decision later** — and that set **must include degrade posture** (mode + enough to identify the mask used).

### The key production truth (pin)

Degrade must be **explicitly recorded** in decision provenance (and therefore audit), so later you can say: “this decision was made under posture X.”

### “Enough to identify the mask” — what I’m pinning as the minimal viable audit payload

DLA audit record must include one of these **two** completeness-safe options:

**Option 1 (preferred v0, simplest): inline the DegradeDecision**
DF includes the DegradeDecision object (mode + mask + provenance summary + decided_at + policy_rev) in the decision provenance it sends to DLA.

**Option 2 (by-ref, allowed later): decision linkage + resolvable ref**
DF includes: `degrade_mode + degrade_decision_id + decided_at_utc + policy_rev + signals_snapshot_ref`, and DLA (or an associated evidence store) can resolve the full DegradeDecision by that id.

**Why I prefer Option 1 for v0:** it avoids the “ref not resolvable” failure mode and keeps DLA’s quarantine rules clean.

### DLA ingestion rules that bind this join (already pinned)

* DLA is **append-only**.
* Ingest is **idempotent**.
* If provenance is incomplete, DLA **quarantines** rather than writing a half-truth.
* Corrections are a **supersedes chain**, not overwrites. 

**DL-specific pin for completeness:**
If DF omits degrade posture (or omits linkage sufficient to resolve it), DLA must quarantine the record as **incomplete provenance**. That’s consistent with your “no half-truth” posture. 

### Operational visibility (so drift shows up)

DF should expose metrics like “blocked by degrade mask rate” so operators can see when DL is constraining decisions. This is explicitly in your metrics baseline expectations. 

---

## 3) Join: Policy/Profile store → DL — threshold/corridor profiles

### What this join *is* in your platform

Thresholds/corridors are **policy config** (outcome-affecting), so they are:

* versioned artifacts
* promoted via propose → approve → activate
* roll-backable
* and runtime components must always report which `policy_rev` they are using.

### What DL must load (pin)

DL loads the **active threshold profile** (call it `dl_threshold_profile_rev`) which contains:

* mode ordering (already pinned elsewhere)
* entry/exit conditions per mode (numbers are config)
* quiet-period settings (config)
* required signal list (policy declares what is required vs optional)

### Atomicity + safety on change (important production pin)

When the active policy revision changes:

* DL must switch **atomically** (no “half old thresholds, half new thresholds”).
* If the new policy revision cannot be loaded/validated, DL must keep operating on the **last known good** revision and emit an error fact/metric indicating “policy update failed.”

### Validation posture (pin: invalid policy is not “best effort”)

If the active profile is malformed/missing required fields, DL treats evaluation as unsafe and will:

* either refuse to activate that profile (preferred operationally), or
* if forced into it, default to **FAIL_CLOSED** until a valid profile is active.

Either way, “invalid policy => optimistic behavior” is banned.

### Governance facts (outer network reality)

Promotion/activation of a new policy rev must emit an **auditable governance fact** (“policy rev X became active”) with actor/scope/reason.

### What DL must report downstream (hard pin)

Every DegradeDecision must cite the **policy revision** used.

---

## 4) Join: Obs/Gov signals → DL — health snapshot inputs

### What this join is

DL consumes **observability signals** as automation inputs: golden signals + platform-specific lag/watermark and staleness signals.

### The minimum production signal families DL must be able to consume

From your pinned baseline, the platform expects at least:

* **EB consumer lag / watermark age** (how far behind consumers are) 
* **OFP**: feature snapshot latency, staleness rate, missing-feature rate 
* **DF**: decision latency, fallback-rate, registry-resolution failures, “blocked by degrade mask” rate 
* **IEG**: (implied by golden signals) latency/error; and it already handles duplicates/out-of-order so health must be treated via metrics, not correctness assumptions

(We’re not enumerating an exhaustive metric name list yet; we’re pinning the *families* that must exist and be consumable.)

### Snapshot semantics (pin: DL evaluates on stable readings)

DL must evaluate using a **windowed snapshot** of readings, each carrying:

* signal identity (`signal_name`, `source_component`)
* observed value + unit
* window label (rolling 1m/5m)
* `observed_at_utc` 

### Missing/stale posture (hard pin)

Missing/stale required signals are treated as **unhealthy** (can cause downshift and block upshift).

This matters because it implies: **if the metrics pipeline fails**, DL fails safe (it doesn’t keep the system in NORMAL blindly).

### Staleness definition (pin: DL must be able to detect it)

DL must have a policy-configurable maximum age for readings. If `now - observed_at_utc > max_signal_age`, the reading is stale.

Again, no numeric choices here — just the semantic need.

### “No silent coupling” implication (important)

Signals can influence DL, but **only DL’s explicit output** can influence DF behavior. No other component is allowed to “infer degrade” from signals independently. This is the whole point of DL being a single authority.

---

## The stitched sequence (how these 4 joins compose in production)

1. **Signals snapshot arrives / is read** → DL evaluates against the active policy rev.
2. DL produces **DegradeDecision** (with `decided_at_utc` and `policy_rev`).
3. DF obeys the mask as hard constraints and **records the posture used** in decision provenance.
4. DLA ingests the decision record; if degrade posture/provenance is incomplete, it quarantines. 

---

### Pins we just established (so you can refer back)

* **J9 output must be fresh-enough** (max-age rule) or DF fails safe.
* **Audit must include degrade posture**; missing degrade => DLA quarantine. 
* **DL policy profiles are governed artifacts**; DL always cites `policy_rev`.
* **Missing/stale signals => unhealthy**; metrics pipeline failure leads to safe degradation, not silent NORMAL.

---

Absolutely — let’s open up **A5–A7** properly (DL still treated as an opaque vertex), and pin what each join *means* in a production platform.

---

## A5) Join: **DL → `dl` posture state** (derived “current posture” + hysteresis memory)

Your platform explicitly allows (and expects) a **small DL DB/kv** that stores *current degrade posture* and is **rebuildable**. Writer is DL; source is obs/health inputs; it’s a “safety control surface,” not primary truth.

### Why this join exists

This store is DL’s **fast-read surface** and **hysteresis continuity surface**:

* **Fast read:** DF (and optionally others) can obtain “current posture” without needing DL to recompute on-demand for every decision.
* **Hysteresis continuity:** DL needs minimal memory to avoid flapping (quiet period tracking, last transition time, etc.).
* **Derived, rebuildable:** if the store is lost/corrupted, it can be recomputed from policy + signals; it does *not* join the “can’t lose these” truths list.

### What is stored (designer-locked v0 shape)

Think of the `dl` store as containing exactly one conceptual record per **scope**:

**Key:** `scope_key`

* either `"GLOBAL"` or a canonical encoding of **ContextPins** `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` (and `seed` only if you intentionally choose seed-variant posture).

**Value:** `CurrentPostureRecord` (single atomic blob) containing:

1. **Decision payload (what DF needs)**

* `mode`
* `capabilities_mask`
* `decided_at_utc`
* `policy_rev` (threshold profile revision in force)

2. **Provenance summary (why we’re here)**

* `triggers[]` (signal, observed value, threshold, comparison, triggered_at)
* `signals_snapshot_ref` **or** inline “signals_used” summary (you already allow either shape conceptually)

3. **Hysteresis continuity (the minimal memory)**

* `last_transition_at_utc`
* `last_mode`
* `quiet_period_until_utc` (the next earliest time an upshift is even eligible)
* `posture_seq` (monotonic integer per scope; increments on every change)

> **Pin:** the store record must be **atomic and self-contained**: a reader either sees the whole posture or none of it (no “half-updated mode with old mask”).

### Write semantics (production behavior)

DL is an always-on/periodic evaluator in your production shape.
So the store writes follow this posture:

* **Write on change:** whenever `mode` or `capabilities_mask` changes, DL writes a new `CurrentPostureRecord` (same `scope_key`, incremented `posture_seq`).
* **Optional heartbeat refresh:** DL may also “touch” the record periodically even if unchanged, but must not lie: `decided_at_utc` is when the decision was computed, not when it was re-written.

### Read semantics (who reads it, and what it means)

* **Primary reader:** DF (it must obey DL posture).
* **Optional readers:** ops dashboards, run/operate tools, maybe cache layers.

**Critical rule:** any reader that uses it operationally must enforce **freshness** using `decided_at_utc` (no silent staleness). Your DL conceptual pins already treat stale/missing inputs as unhealthy and fail-closed on unsafe evaluation.

### Failure posture (store is down / empty / corrupted)

Because this store is rebuildable and not primary truth, the safe behavior is:

* If DL can’t write to `dl`, DL still computes internally; but DF must not be forced to trust an old record forever.
* If DF can’t read a valid/fresh posture, DF falls back toward safety (that’s already pinned at the DL→DF join level), and records that it used fallback.

### Multi-instance / scaling pin (so we don’t drift later)

To avoid “two DLs fighting”:

* For any given `scope_key`, there must be **at most one active writer** at a time (leader per scope). Read replicas are fine.
* If you ever run multiple DL instances, they must coordinate so `posture_seq` remains monotonic and “last write wins” cannot cause mode oscillation.

That’s enough to keep the join sane without specifying a particular leader-election tech.

---

## A6) Join: **DL → `fp.bus.control.v1`** (optional posture-change facts)

Your deployment map explicitly allows DL to emit **optional events** to `fp.bus.control.v1` specifically for “degrade posture changes,” and defines `fp.bus.control.v1` as the low-volume control-facts lane (READY signals, governance facts, lifecycle events, config activations, etc.).

### Why this join exists (when you actually want it)

This bus edge is *not required* for correctness, but it’s very valuable for:

1. **Visibility:** operators can see posture transitions as explicit facts (“no silent changes”).
2. **Cache invalidation:** DF instances that cache posture can subscribe and instantly invalidate/refresh on change.
3. **System coordination:** other control-plane automation (Run/Operate) can react (e.g., paging, throttling, incident annotations) without scraping DL’s DB.

### What is emitted (designer-locked v0 event semantics)

DL emits a **posture-change fact** only when posture materially changes:

* `mode` changes, or
* `capabilities_mask` changes, or
* `policy_rev` changes (because semantics changed), or
* DL enters “evaluation failure → FAIL_CLOSED” (also a posture change).

**Pinned payload meaning (conceptual):**

* `scope_key` (GLOBAL or ContextPins)
* `new_decision` (either full DegradeDecision or a by-ref id)
* `prev_decision_id` (optional but helpful)
* `posture_seq`
* `decided_at_utc`
* `policy_rev`
* `reason/triggers summary` (enough for “why did we change?”)

### Envelope / bus boundary (important to prevent drift)

Your platform pins that the **Canonical Event Envelope** is the bus boundary, and it already carries ContextPins fields as optional pins with `manifest_fingerprint` required.

So I’m pinning:

> **If DL emits on `fp.bus.control.v1`, it emits an envelope-shaped event** (CanonicalEventEnvelope), with `event_type` like `dl.posture_changed.v1`, and `ts_utc` = `decided_at_utc` (domain time for the posture decision).

This keeps control facts joinable and traceable just like everything else.

### Idempotency/dedup (so the control bus doesn’t become a chaos source)

Control facts still live in an at-least-once world.

So I’m pinning a simple rule:

* `event_id` should be **stable per posture transition**, derived from `(scope_key, posture_seq)` or from a deterministic `degrade_decision_id`.
* Partition key should be **scope-stable** (e.g., hash of `scope_key`) so ordering of posture changes is preserved per scope.

### What this event is *not*

* It is **not** the thing DF uses as decision provenance. DF still must record the posture it actually used per decision into DLA.
* It is **not** a stealth control lever. It’s a fact stream, not a command channel.

---

## A7) Join: **DL → optional consumers** (readers of posture)

This is the edge that can create **stealth coupling** if we don’t pin it properly — your platform explicitly says DL must be “no silent coupling,” and DL is the truth owner for degrade posture.

So here’s the safe production meaning:

### Who are “optional consumers”?

Any component that **reads** DL posture without being the authoritative decisioner:

* **Ops/Run-Operate/Governance** tooling
* **Dashboards/alerting**
* **Case Workbench** (display-only)
* **OFP / IEG** (only for *internal* load posture, if allowed)
* **DF cache layer** (if DF uses caching)

### Allowed uses (what this join is permitted to do)

I’m pinning three allowed categories:

1. **Visibility / reporting**

* Show current mode/mask/policy_rev and transition history.

2. **Cache invalidation / refresh**

* A reader can use posture-change events or `posture_seq` to refresh its local cached copy.

3. **Internal performance posture that does not change truth semantics**

* Example: OFP may adjust internal queue limits, sampling frequency, or prioritization under heavy load.
* Example: IEG may adjust internal caching/backoff.

**Key constraint:** internal tuning is fine **only if it does not change the component’s externally observed contract in a way that affects outcomes “silently.”**

### Banned uses (stealth coupling killers)

These are explicitly **not allowed**:

* Any consumer **derives its own degrade mode** from metrics (DL is the single authority).
* OFP/IEG use DL to silently change **what features/identity** they return in ways not already visible through their own health signals and DL’s mask.
* Any consumer treats DL mode as a “permission to skip audit/provenance.” (Audit must stay reconstructible.)

### How optional consumers obtain posture (three sanctioned read paths)

Any optional consumer may read posture via:

1. **Read `dl.current_posture` store** (fast polling read)
2. **Subscribe to `fp.bus.control.v1` posture-change facts** (event-driven)
3. **Call DL service API** (if you choose to expose one; still the same semantics)

And every consumer must apply the same basic safety rule: **don’t act on stale posture** (using `decided_at_utc`).

### The “DF exception” (the only mandatory consumer)

DF is *not* an optional consumer — it’s the **mandatory enforcement point**: it must obey the mask and record posture used.

---

## Pins we just locked for A5–A7 (so you can reference them)

* **A5:** `dl` store is a **derived, rebuildable** per-scope posture record; **DL is sole writer**; atomic record includes mode/mask/provenance summary + hysteresis continuity + `posture_seq`.
* **A6:** If DL emits on `fp.bus.control.v1`, it emits **envelope-shaped** `dl.posture_changed.v1` facts, idempotent per transition, used for visibility + invalidation, not as provenance-of-record.
* **A7:** Optional consumers may read DL posture only for visibility/caching/internal tuning; **they may not create stealth coupling or their own degrade logic**.

---

Cool — expanding **B8–B11** now (DL remains an opaque vertex; we’re describing *outer-network production paths* and the invariants they must satisfy).

---

## B8) Hot decision path

`EB admitted_events → (IEG/OFP/DL) → DF → AL → DLA`

### What this path *is* in production

It’s the platform’s “real-time decision loop,” where **EB is the replay spine**, **IEG/OFP/DL are context providers**, **DF is the only decisioner**, **AL is execution authority**, and **DLA is the flight recorder**.

### The canonical sequence (designer-authoritative v0 ordering)

I’m pinning the v0 orchestration ordering inside DF like this because it kills drift and makes provenance reconstructible:

1. **Read event from EB**

   * DF consumes admitted events from EB (at-least-once delivery, ordered only within a partition). 
   * The only universal “position” is `(stream_name, partition_id, offset)` and consumer progress is tracked as **exclusive-next offsets** (checkpoint.offset = next offset to apply).

2. **Get DL posture (J9) before choosing any “expensive/optional” work**

   * DF obtains **DegradeDecision** and treats `capabilities_mask` as hard constraints.
   * If DL is unavailable → DF fails toward safety and records that fallback.

3. **Resolve bundle (J10) using degrade constraints**

   * Registry resolution is deterministic and **compatibility-aware**, including compatibility with the **current degrade mask**.
   * If no compatible bundle exists → DF follows safe fallback posture and records why.

4. **Acquire features (J8) with pinned time semantics**

   * DF treats **`event_time` as the decision boundary** and calls OFP with `as_of_time_utc = event_time_utc` (no hidden “now”).
   * DF may only request/use feature groups allowed by degrade + bundle requirements.

5. **(Optional) acquire identity context from IEG**

   * Only if allowed by `capabilities_mask.allow_ieg`.
   * If consulted, DF must record the `graph_version` used (see B10).

6. **Compute decision and emit ActionIntents to AL (J11)**

   * DF emits ActionIntents with a deterministic idempotency key; AL enforces effectively-once execution on `(ContextPins, idempotency_key)`.
   * DL may additionally constrain action posture (e.g., “STEP_UP_ONLY”), which DF must obey.

7. **Record to DLA (J12) as the flight recorder**

   * DLA must receive the minimum immutable facts: event reference basis, feature snapshot hash + input_basis, graph_version if used, degrade posture, resolved bundle ref, action intents, etc.
   * DLA is append-only; idempotent ingest; quarantine on incomplete provenance.

### Production “gotchas” this ordering avoids

* **No hidden coupling / no silent degrade:** only DL output can constrain DF.
* **No “feature now”:** OFP uses event_time boundary, not wall clock. 
* **Replay parity:** feature snapshots and identity context are reconstructible by recording input_basis and graph_version.

---

## B9) Feature acquisition under constraints

`DF (uses DL mask) → OFP → DF (records provenance)`

### What this path must guarantee

**OFP is a deterministic snapshot service**, and DF must be able to prove what snapshot it used later.

**Pinned provenance contract of a served snapshot** (non-negotiable):

* ContextPins
* `feature_snapshot_hash` (deterministic)
* group versions used + freshness/stale posture
* `as_of_time_utc` (explicit)
* `graph_version` (if IEG consulted)
* `input_basis` watermark vector (applied offsets)
  …and the snapshot hash deterministically covers the relevant blocks.

### How DL constrains this path (outer semantics)

DL’s capabilities mask constrains DF in two ways:

1. **Which feature groups DF is allowed to request/use**
   DF must obey `allowed_feature_groups` (treat as hard constraints).

2. **Whether OFP may rely on IEG**
   OFP can optionally consult IEG to resolve canonical keys and capture graph_version.
   If `allow_ieg=false`, then **this decision path must behave as if IEG doesn’t exist**—meaning DF must ensure the OFP request is formed in a way that does not require/trigger IEG help (details in B10).

### DF’s recording obligation (what makes this “replayable”)

DF must record in decision provenance what OFP gave it:

* `feature_snapshot_hash`
* group versions
* freshness/stale flags
* `input_basis`
* and `graph_version` if relevant.

### Failure posture (no invented context)

If required features are missing/stale, DF does not invent context; it records unavailability and follows pinned fail-safe posture — **and still must obey degrade constraints while doing so**.

---

## B10) Identity context under constraints

`DF (uses DL mask) → IEG → DF (records graph_version)`

### What IEG means in your platform

IEG is a run/world-scoped projection derived from EB admitted events, built to tolerate duplicates and out-of-order delivery.

**Pinned replay safety rule:**
IEG applies events idempotently using an `update_key` derived from **ContextPins + event_id + pinned semantics id**.

**Pinned meaning of graph_version:**
A monotonic token representing “what EB facts have been applied” for a given ContextPins graph — concretely a per-partition applied-offset watermark vector (exclusive next offsets) plus stream_name.

### How DL constrains this path

* If `capabilities_mask.allow_ieg=false` → DF **must not** call IEG (hard constraint).
* If IEG is used as context, downstream **must record** the `graph_version` used so the decision context can be replayed/audited later.

### The crucial production nuance: “IEG can lag EB”

Because IEG’s `graph_version` is derived from *applied* EB offsets, it may not include the most recent EB event DF is deciding on (especially under lag/backpressure). That’s fine — but it must be **made explicit** in provenance (graph_version + input_basis).

### The safe fallback when IEG is disallowed/unavailable

DF must:

* proceed using event-local identifiers only (whatever the event carries),
* record “IEG not used” + reason (disabled by DL vs failure),
* and follow its safe posture if the resolved bundle requires IEG context that is not available.

(Notice how B10 and B11 couple: “bundle requires IEG but DL disables it” must be caught deterministically.)

---

## B11) Bundle resolution under constraints

`DF (uses DL mask) → Registry → DF (compat-aware; fail-closed if incompatible)`

### What this path is responsible for

Registry answers: **“what should DF use for this decision right now?”** as an **ActiveBundleRef** (bundle id + immutable artifact refs + compatibility metadata).

### Pinned truths at this join

* Resolution is **deterministic** (no “latest”). For a given scope, DF gets one active bundle by rule. 
* DF must record the resolved bundle reference in provenance.
* Compatibility is enforced at the join: if the active bundle is not compatible with current feature definitions **or the current degrade mask**, DF must fall back safely and record why.

### What “compatibility-aware including degrade” really means (outer semantics)

A bundle is only “executable” if it is satisfiable under:

* the current **feature definition versions** (serving + offline + bundle agree),
* and the current **capabilities mask** (e.g., requires IEG but `allow_ieg=false`; requires stage2 but stage2 disabled; requires feature groups not in allowlist).

So in production, registry resolution must effectively be:

> `ActiveBundleRef = Resolve(scope, event_type, policy_state, feature_defs, degrade_constraints)`
> …and the output must be deterministic.

### The two allowable outcomes (no silent “best effort”)

1. **Return a compatible ActiveBundleRef** (the normal case).
2. **Fail closed / route to a defined safe fallback** (must be explicit and recorded; never silently proceed with an incompatible bundle).

---

## The key “stitch” across B8–B11 (what we’ve implicitly pinned)

To keep the whole hot loop coherent and drift-proof, **DL must be consulted before bundle resolution and before feature/IEG calls**, because degrade constraints are part of compatibility and allowable context acquisition.

---

Absolutely — here are **B12–B14 expanded** in a production-ready way (DL still treated as opaque; we’re defining what the *outer network* around it must do).

---

## B12) Control-plane visibility path

`DL posture-change → fp.bus.control.v1 → Obs/Gov dashboards + alerts (+ optional cache invalidation)`

### Purpose of this path (why it exists)

This path exists so the platform can always answer **“Are we healthy enough to act?”** and **“What changed?”** without scraping internal state or relying on silent behavior shifts.

Your deployment mapping explicitly allows DL to emit **degrade posture changes** onto the **low-volume control topic** `fp.bus.control.v1`.

### Participants

* **Producer:** DL (on posture transitions).
* **Transport:** `fp.bus.control.v1` (control facts stream).
* **Consumers:**

  * Obs/Gov pipeline + dashboards/alerts (time-in-mode, trigger summaries).
  * Run/Operate automation (incident annotations / governance joins).
  * Optional: DF cache invalidation (if DF caches DL posture). (Still optional; semantics unchanged.)

### What is emitted (outer-network semantics)

If DL emits events, they **must be canonical-envelope shaped**, because the envelope is the pinned bus boundary shape.

**Canonical envelope requirements** (hard):
`{event_id, event_type, ts_utc, manifest_fingerprint}` are required, with optional pins `{parameter_hash, seed, scenario_id, run_id}` and optional `emitted_at_utc`, tracing fields, and `payload`.

So, a DL posture change event is conceptually:

* `event_type`: `dl.posture_changed.v1`
* `ts_utc`: **domain time of the posture decision** (i.e., “this posture became true at …”)
* `emitted_at_utc`: optional “producer clock”
* `producer`: `"DL"`
* `payload`: `{scope, mode, capabilities_mask, policy_rev, posture_seq, triggers_summary, decided_at_utc, prev_decision_ref?}`

### Scope + manifest_fingerprint (one small pin we need for “global” facts)

Because the envelope requires `manifest_fingerprint`, we must ensure control facts are always representable:

* For **scoped** posture changes (recommended default): include the actual scope pins (manifest_fingerprint + optional run pins). This is already aligned with “ContextPins everywhere.”
* For **global** control facts (e.g., “policy profile activated platform-wide”), we need a reserved envelope-compatible value.

**Designer pin (platform-safe):** reserve a single sentinel
`manifest_fingerprint = 0000000000000000000000000000000000000000000000000000000000000000`
to mean “platform-global control scope.”
This keeps the envelope valid while preserving the meaning that it’s not a world identity.

### Idempotency + ordering (so this path is safe under at-least-once)

Your platform assumes at-least-once delivery everywhere, so control facts must tolerate duplicates.

**Pinned production posture for this path:**

* DL assigns `event_id` deterministically per transition, e.g. derived from `(scope_key, posture_seq)` or from a deterministic decision hash.
* Events are partitioned by `scope_key` so posture transitions are ordered **per scope** (ordering is only guaranteed within a partition).

### What consumers do with it (and what they must NOT do)

**Allowed uses**

* dashboards: time-in-mode, transition history, per-scope posture
* alerts: entering `FAIL_CLOSED`, or “stuck degraded for N minutes”, or “rapid flapping” signals
* cache invalidation: DF refreshes its cached posture on `dl.posture_changed.v1`

**Banned use (no stealth coupling)**
No component is allowed to “infer degrade” from metrics or from this stream; the only behavioral authority is still DL’s explicit decision surface consumed by DF, and DF must record the posture used.

### Failure posture

If `fp.bus.control.v1` is unavailable:

* DL does **not** become unable to constrain DF (that remains via J9 / dl-store read); you only lose visibility and event-driven invalidation.
* DL must still expose posture through its primary surface (`dl` store / J9) and emit telemetry through the observability pipeline (logs/metrics) so the platform doesn’t go blind.

---

## B13) Audit reconstruction path

`DLA (dla/audit/…) → investigations / case tooling / offline parity & analysis`
(replay: “what was allowed then, and why?”)

### Purpose of this path

DLA is the platform’s **immutable flight recorder**. It exists so you can reconstruct decisions later without relying on mutable service state or “best effort memories.”

### Where the audit truth lives (and how tools access it)

Your deployment mapping pins:

* primary audit truth in object storage: `dla/audit/...` (immutable records)
* optional `audit_index` DB for search/lookup
* optional pointer events to `fp.bus.audit.v1` (not required for core truth)

**Primary consumers** include Case Workbench and offline analysis tooling.

### What an audit record must contain (the “reconstruction kit”)

Your J12 pins this explicitly: an audit record must carry **by-ref / hashed pointers** to the minimum immutable facts needed to reproduce/justify the decision later.

At minimum (as pinned):

* **event reference basis** (what was decided on)
* `feature_snapshot_hash` + `input_basis` (watermark vector)
* `graph_version` (if used)
* **degrade posture** (mode + enough to identify mask used)
* resolved bundle reference (registry active bundle ref)
* actions (idempotency keys) + outcomes linkage
* audit metadata (`ingested_at`, and `supersedes` link on correction)

And this ties directly to your replay rails:

* replay/progress tokens are EB coordinates (offset/watermark basis)
* ledger-like truths are append-only + supersedes chains
* degrade is explicit, enforced, and recorded

### The reconstruction workflow (what an investigator/offline tool actually does)

Given a `decision_id` (or event correlation keys), tooling does:

1. **Locate the canonical audit record** (via index or object key convention).
2. **Follow supersedes chain** to the latest correction (never overwrite; corrections are new records).
3. Extract the “decision context kit”:

   * which event basis was used
   * which feature snapshot hash + input_basis
   * which graph_version (if any)
   * which degrade posture + policy_rev
   * which active bundle ref
4. **Optionally reproduce**:

   * replay the same admitted facts from EB/archive using the recorded basis (offset/watermark vectors)
   * rebuild the OFP snapshot at the recorded as-of boundary (using `input_basis`) and confirm the snapshot hash
   * rebuild IEG to the recorded `graph_version` and confirm identity context parity
   * confirm DF/AL behavior is explainable under the recorded degrade mask (“what was allowed then?”)

### Quarantine posture (critical for truth integrity)

Pinned rule: if provenance is incomplete, DLA **quarantines** the audit record rather than writing a half-truth.

So the reconstruction path includes a sibling branch:

* **AuditQuarantine → tooling** so operators can see *why* a record couldn’t be made canonical and reprocess/repair upstream.

### Why DL matters here (explicitly)

Without DL being recorded, you cannot answer the simplest post-incident question:

> “Was the system in a degraded posture when it made this decision?”

That’s why degrade posture is pinned as required provenance in audit.

---

## B14) Governed policy-change path

`propose → approve → activate policy_rev → DL loads → DF decisions cite rev → DLA records`

### Purpose of this path

Policy/config changes are **outcome-affecting** in your platform, so “someone changed a threshold” must become an **auditable fact** with a lifecycle, not a hidden environment tweak.

DL thresholds/corridors are explicitly called out as **policy config** and must follow this governed lifecycle.

### The pinned lifecycle (production truth)

Policy config promotion is pinned as:

* **propose new revision**
* **approval step**
* **activation step**
* **rollback path**
  …and every activation emits a governance fact.

Policy config is also pinned as a **versioned artifact** with:

* stable `policy_id`
* content digest
* monotonic revision/tag
  …and runtime components must report which revision they are using.

### What happens, step-by-step (outer-network behavior)

1. **Propose**

* A new DL threshold profile artifact is produced (new `policy_rev`, new digest).
* It’s stored as an immutable-ish artifact (by-ref posture).

2. **Validate**

* CI validates schema/lints/consistency and can run an integration flow on the production-shaped local stack.

3. **Approve**

* A human or controlled automation approves the revision.
* This approval is itself an attributable governance act.

4. **Activate**

* Run/Operate flips the environment’s **policy profile** to point at the approved revision (no code forks; profile selection).
* Activation emits a **governance fact** onto `fp.bus.control.v1` (control facts stream includes config activations).

5. **DL loads**

* DL detects the active revision (polls a pointer, reads a governed store, and/or consumes the governance fact).
* DL switches policy **atomically** (no partial table) and begins emitting decisions citing the new `policy_rev`.
* If DL cannot load/validate the active revision, it must not “half-apply”; it either sticks to last-known-good or fails closed, and emits an error signal/governance note (safe ops posture).

6. **DF decisions cite rev**

* DL decisions include the threshold profile revision, and DF records degrade posture (therefore policy_rev) in decision provenance.

7. **DLA records**

* DLA persists the canonical audit record including degrade posture and enough linkage to identify the mask and policy revision used.

8. **Rollback**

* A rollback is just another governed activation back to a prior revision, with an auditable governance fact.

### The two key guarantees this path provides

1. You can always answer: **“What rules were in force when this decision happened?”** (policy_rev is recorded).
2. You can always answer: **“What changed?”** (activation is an auditable governance fact on the control stream).

---

Got it. Here are **C15–C20** expanded as **production feedback loops** around DL (still treating DL as opaque), with the **exact “cause → DL → DF constraints → system effect → recovery”** shape pinned.

Before the individual loops, one cross-cutting pin (applies to **all** of them):

* DL evaluates a **windowed signal snapshot** and emits one **authoritative** `DegradeDecision {mode, capabilities_mask, provenance, decided_at_utc}`; tie-break is deterministic (choose the **most degraded eligible**), **downshift is immediate**, **upshift requires quiet period and is one rung at a time**, **missing/stale signals are unhealthy**, and if DL can’t evaluate it **fails closed**.
* DF treats the mask as **hard constraints** and audit must record the degrade posture used (“no silent coupling”).

---

## C15) OFP load-shedding loop

### The loop

**OFP health worsens → DL downshifts → DF reduces OFP usage → OFP stabilizes → DL upshifts (after quiet period).**

### What DL watches (signal families)

* OFP latency / error rate / lag, plus “freshness/stale posture” surfaces.

### What DL does (constraints that create load shedding)

When OFP is the pressure source, DL’s effective control is: **reduce feature demand**.

* Constrain `allowed_feature_groups[]` to a minimal allowlist (or tighten it further as you go down rungs).
* Optionally forbid “optional expensive groups” by policy (the precise allowlist is policy config; the existence of the constraint is the pin).

### What DF must do (enforcement point)

* DF must request/use **only** allowed feature groups and must not “invent missing context” if restricted groups are unavailable; it records unavailability and follows fail-safe posture.
* DF must still keep the replay/provenance bridge: OFP returns `feature_snapshot_hash` + `input_basis` watermark vector, and DF records them.

### Why this loop is stable (not flappy)

* Downshift fast reduces OFP workload quickly. Upshift slow (quiet period + one rung) avoids oscillation while OFP recovers.
* If OFP telemetry goes missing/stale, DL treats it as unhealthy → conservative behavior rather than “pretend healthy.”

### What must be visible/auditable

* DL provenance includes triggers (which OFP thresholds breached).
* Decisions during degradation must show: `degrade_mode`, mask, and the OFP snapshot provenance (`feature_snapshot_hash`, `input_basis`, group versions/freshness).

---

## C16) IEG load-shedding loop

### The loop

**IEG health worsens → DL downshifts → DF stops calling IEG → IEG stabilizes → DL upshifts.**

### What DL watches

* IEG latency / error.

### What DL does

* Flip `allow_ieg=false` (at the appropriate rung) to shed load and remove dependence on a struggling graph query surface.

### What DF must do

* If `allow_ieg=false`, DF **must not** call IEG—treat it as if it doesn’t exist.
* If IEG **is** used, DF must record the `graph_version` used so context is replayable/auditable.

### Why this loop is safe under replay/backpressure

IEG is built assuming **duplicates/out-of-order** and applies events idempotently via an `update_key`; its `graph_version` is a watermark vector (applied offsets). That means:

* Turning IEG off doesn’t break determinism—it just removes one source of context.
* When IEG comes back, upshift is controlled by quiet period, so DF doesn’t hammer it the moment it twitches back to life.

### What must be visible/auditable

* Provenance must show whether IEG was used and (if used) which `graph_version`; if not used due to DL, that should be explicit.

---

## C17) EB lag / backpressure loop

### The loop

**EB consumer lag rises → DL downshifts → DF reduces compute per event → DF catches up → lag falls → DL upshifts.**

### Why EB lag is a first-class trigger in your platform

EB is the replay spine; progress is only meaningful as `(stream, partition, offset)` and checkpoints are **exclusive-next offsets** (watermark basis).

So “lag” is not just ops noise—it’s a signal that the decision loop is failing to keep up with admitted facts.

### What DL watches

* EB consumer lag for the admitted_events consumption path.

### What DL does (the compute dial)

To reduce per-event cost (so consumers catch up), DL can tighten multiple mask knobs together:

* restrict `allowed_feature_groups[]`
* `allow_ieg=false` (avoid graph queries)
* `allow_model_stage2=false` and possibly `allow_model_primary=false` at deeper rungs
* optionally `action_posture=STEP_UP_ONLY` (reduce risky automation when context is thin)

### What DF must do

* DF must obey these constraints deterministically and record them in provenance.
* DF must not hide the fact that it is running “thin” (e.g., missing features / no IEG); it records unavailability and uses safe fallback posture.

### Why this loop converges

* Reducing compute per event increases processing throughput, which reduces lag/watermark age.
* Upshift is slow + rung-by-rung, so you don’t immediately re-enable expensive steps the moment lag dips.

### The important “watermarks don’t lie” nuance

Backfills/late arrivals create *new offsets*; they don’t “rewind time.” DL should treat lag based on watermarks as monotonic progress indicators, not interpret backfill as “system recovered then got worse.”

---

## C18) Model/runtime loop (DF + model serving)

### The loop

**Model serving / DF runtime latency/errors rise → DL downshifts → DF disables heavy model stages → runtime stabilizes → DL upshifts.**

### What DL watches

* “model serving latency/error” and potentially DF internal golden signals.

### What DL does

Primary control is to **remove the expensive/fragile decision steps**:

* `allow_model_stage2=false` first (common: stage2 is heavier / optional escalation)
* if pressure persists, `allow_model_primary=false` (only at deeper rung; this is effectively “decision without model”)

Whether heuristics are allowed is also explicitly gated (`allow_fallback_heuristics`).

### What DF must do

* DF must not execute disabled inference stages and must not “secretly substitute” alternative logic if `allow_fallback_heuristics=false`.
* DF records the degrade posture used so later you can tell whether the model was even permitted at that time.

### Why this loop is safe

* It’s a pure *capability subtraction* loop: disable expensive inference to restore SLOs and reduce error propagation.
* Recovery is intentionally conservative (quiet period + one rung) so transient model spikes don’t thrash the system.

---

## C19) Action-risk loop (AL execution safety)

### The loop

**Action execution failures/latency rise (or action authz becomes uncertain) → DL makes action posture conservative → DF issues fewer risky actions → stability returns.**

### What DL watches

* AL execution failures, denied outcomes due to policy, latency (golden signals + policy outcome rates).

### What DL does

* Set `action_posture=STEP_UP_ONLY` at the rung where it’s unsafe to auto-approve/allow.
* Potentially also tighten upstream context knobs (feature groups, IEG) if the risk is being caused by “thin context” rather than AL itself.

The key is: DL doesn’t execute actions; it constrains what DF is allowed to request.

### What DF + AL do (together)

* DF must obey the posture: under STEP_UP_ONLY, it cannot emit permissive actions; only conservative/holding/step-up actions are allowed (as per the pinned meaning you’ve already outlined).
* AL enforces idempotency on `(ContextPins, idempotency_key)` and emits an immutable ActionOutcome recording actor principal + policy rev used (so “why did we block this?” is defensible).

### Why this loop matters even when compute is fine

You can be “healthy” in latency terms but still be unsafe to act (e.g., degraded inputs, policy uncertainty, or elevated denial/failure rates). This loop prevents the system from making high-impact mistakes when confidence is compromised.

---

## C20) Governance tuning loop (humans + policy rev)

### The loop

**DL posture history + outcomes → humans/automation adjust thresholds/corridors → new policy_rev activated → DL behavior changes (governed, auditable).**

### What feeds the tuning loop

* Time-in-mode, trigger histories, flapping rate (from DL provenance and optional control facts).
* Downstream outcome impact: decision quality, action outcomes, quarantine rates, EB lag trajectories.

### How tuning must happen (pinned governance shape)

Degrade thresholds are **policy config**, so changes are:

* versioned artifacts with monotonic revisions
* proposed → validated → approved → activated
* every activation/rollback emits a governance fact
* runtime components report which `policy_rev` they are using

### What this loop guarantees

You can answer, for any decision/event:

* “what degrade thresholds were in force?” (policy_rev recorded)
* “what changed?” (governance fact)
* “why did DL move?” (trigger provenance)

---

## One final production pin across C15–C20: loop interactions

These loops can fire simultaneously (OFP + EB lag + model spikes). The platform-safe rule is:

* DL evaluates all triggers, and if multiple modes are eligible, it selects the **most degraded eligible** mode; provenance lists the triggers that justified it.
* Recovery must respect hysteresis (quiet period, one rung), and any missing/stale signal blocks upshift.

That’s what prevents loops from fighting each other and keeps the system predictable.

---

Yes — the **environment ladder** is *especially* important for DL, because DL’s whole job is “operational safety posture,” and it’s very easy for teams to accidentally make **local/dev behave differently** from prod and then discover the real loops only in prod (worst-case).

Your ladder pin is explicit: **local, dev, prod run the same platform graph + the same rails/join semantics; environments differ only in operational envelope** (scale/retention/security/reliability/observability), and promotion is profile selection, not semantic forking.

Below is what that means **for the DL joins/paths/loops we just mapped**.

---

## What must stay identical across environments for DL (no-drift invariants)

### 1) The join semantics do not change

Across local/dev/prod, DL must still be the same vertex with the same outer edges:

* **Reads:** obs pipeline signals + threshold policy profiles
* **Writes:** `dl` current posture store + optional posture-change facts to `fp.bus.control.v1`

Even if local “collapses” deployment units (run multiple services in one process), the **roles and authority boundaries** must not change.

### 2) “Rails bite” the same way everywhere

The environment ladder doc explicitly lists the rails that must be identical everywhere — and it calls out **degrade mask as hard constraint** alongside the rest (ContextPins discipline, canonical envelope, no-PASS-no-read, watermarks, idempotency, append-only/supersedes, deterministic registry resolution, as-of semantics).

So the DL-specific invariants that must never change across environments are:

* DL output is **explicit** and DF treats the mask as **hard constraints** (not “advice”).
* Missing/invalid DL posture must cause **fail-toward-safety** behavior (no “best effort normal”).
* DF must **record** the degrade posture it used (audit/replay truth is not optional in prod only).

### 3) Policy vs wiring separation is not optional

The ladder pins “policy config vs wiring config”:

* DL thresholds/corridors are **policy config** → versioned + auditable; DL decisions cite `policy_rev`.
* Endpoints/timeouts/resources are **wiring** → can vary without claiming semantic change.

This directly governs our **B14 loop (policy-change propagation)**: it must exist in local/dev as a mechanism even if approvals are lightweight locally.

---

## What is allowed to differ across environments without breaking DL semantics

Your ladder allows differences in **operational envelope** only (scale, retention/archive, security strictness, reliability, observability depth, cost).
Translated into DL terms:

### 1) Different DL *policy revisions* per environment (same semantics)

You may (and should) run different threshold profiles across environments:

* **Local:** lenient thresholds / shorter windows so you can iterate without constant downshift (or alternatively, *very sensitive* thresholds if you’re trying to demo flapping and hysteresis).
* **Dev:** “real enough” thresholds that catch integration failures (unauthorized changes, missing policy rev, missing signals) and exercise the loops.
* **Prod:** meaningful corridor/SLO checks with strict triggers.

Key: the *mode meanings, mask meanings, and failure posture* don’t change — only the numbers do.

### 2) Observability depth changes, but **signals must exist locally**

Because DL depends on the obs pipeline, local must still run production-shaped observability (OTel collector + metrics/traces/logs stack) so DL is not operating on pretend inputs.

Local can make dashboards/alerts “debuggy,” but the **signal contract** has to be real.

### 3) Security strictness changes, not the mechanism

Local can use permissive allowlists and dev credentials, but dev/prod must enforce authn/authz and approval gates so the same failures prod would catch are caught in dev (including policy activations, quarantine access, registry lifecycle privileges).

For DL specifically: who can activate a new threshold profile rev is stricter in prod; the fact that activation is a governed act remains identical.

### 4) Retention/HA/indexing can vary

Local can have short retention and may skip optional indexes; prod needs longer retention, archive continuity, HA, backups. DL semantics are unaffected as long as:

* DF still records degrade posture in provenance, and
* audit is still written to the same substrate shape (even if local retention is short).

---

## What the loops mean in each environment (practical consequences)

### Local

Problem: many loops (OFP load shedding, EB lag backpressure) won’t naturally trigger at laptop scale.

So for local to be production-shaped **without faking semantics**, you need one of these **valid** approaches:

1. **Fault/load injection** (preferred): drive OFP/IEG/model latency or lag with a test harness so real signals change and DL reacts.
2. **Test policy profile revs**: use an alternate threshold profile that intentionally makes the system enter/exit rungs under small loads — but still as a **policy_rev** (not “if local then…” code).

Both preserve the rule: *same code, different profile*.

### Dev

Dev is where you prove that the **end-to-end hot path** respects DL:

* DL posture changes propagate (via `dl` store and optionally `fp.bus.control.v1`).
* DF obeys the mask and records the posture used.
* DLA flight recorder remains reconstructible.

This aligns with your pinned integration test expectation: dev should run the full golden flow (SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA) and should additionally exercise degrade behaviors, schema evolution, upgrades/backfills.

### Prod

Prod is where thresholds/corridors become operationally meaningful and governance must be strict:

* DL policy activations and rollbacks must be governed, attributable facts.
* Observability must be good enough that “missing metrics” is itself detectable and drives safe posture rather than silent normal.
* No “human memory”: posture and policy rev must be provable from audit/provenance.

---

## The one DL-specific environment-ladder warning I’d pin

**Do not allow “local shortcuts” that bypass DL’s need for real signals.**
If local doesn’t run a real observability intake + produces no meaningful lag/latency/error signals, you’ll end up implementing DL as a stub and only discover the real behavior under prod load. Your notes explicitly warn against this: local must still obey rails; local should run the OTel/Grafana stack.

---

If you want, the next tight move is to define a **DL environment profile matrix** (local/dev/prod) for just three things:

1. which `policy_rev` is active,
2. max-age for signals/decisions (freshness),
3. whether posture-change events to `fp.bus.control.v1` are enabled.

That locks the environment ladder behavior without drifting into implementation.

---

Yep — here are the **environment-profile knobs** (and the few other “deployment-reality” facts) you should have in your head *before* we crack DL open.

Everything below is aligned to your environment ladder pin: **same graph + same rails/join semantics everywhere; only operational envelope + profiles differ**.

---

## 0) Deployment reality of DL as a unit (what it “is” when it runs)

DL is a **hot-path-adjacent, always-on (or periodic) evaluator unit**. It’s not a job. It continuously computes posture that constrains DF.

**Reads**

* **Obs pipeline signals** (metrics/lag/errors) + **policy threshold profiles**.

**Writes**

* **DB `dl` current posture** (derived/rebuildable)
* optional posture-change facts → **`fp.bus.control.v1`**

So when you “deploy DL,” you’re really deploying:

1. an evaluator loop,
2. a small durable posture store,
3. optional control-fact publisher,
4. full observability (because DL depends on signals).

---

## 1) The DL environment profile knobs (grouped the way your platform thinks about config)

Your platform explicitly separates **policy config** (outcome-affecting) from **wiring config** (non-semantic endpoints/resources). DL has both, and they must be treated differently across environments.

### A) Policy profile knobs (versioned + auditable artifacts)

These are “what constitutes safe operation” → they **must be versioned, promoted, and cited** by DL decisions.

Core DL policy knobs:

* **Active threshold profile revision** (`dl_threshold_profile_rev`) — this is *the* knob per environment.
* **Required signals list** (which signals are mandatory vs optional).
* **Mode ladder vocabulary + ordering** (the meanings don’t change per env; numbers do).
* **Entry condition corridors/thresholds per mode** (numbers differ by env; semantics don’t).
* **Hysteresis posture knobs**: quiet-period duration, minimum time-in-mode (if used), one-rung-upshift rule.
* **Staleness policy**: max allowed age for readings (`max_signal_age`) and the pinned rule “stale/missing ⇒ unhealthy.”
* **Default safe behavior on evaluation failure**: pinned `FAIL_CLOSED`.
* **Capability mapping table**: mode → capabilities_mask (the table can evolve via policy revision; DF semantics remain “hard constraints”).

**Why this matters for your ladder:** this is how you change DL between local/dev/prod *without creating three different platforms*: you activate different **policy revisions**, not different code.

### B) Wiring profile knobs (endpoints/resources; not semantic)

These are allowed to differ freely by environment (still logged for ops), because they don’t change the meaning of DL decisions.

* Metrics/telemetry intake endpoints (OTel collector address, metric backend URLs).
* DB connection for `dl` posture store (Postgres URL/creds; schema name).
* Control bus endpoints/topic names (Kafka/Redpanda broker URLs; `fp.bus.control.v1`).
* Timeouts/retries/backoff for reading signals and writing posture.
* Resource limits / scaling (threads, memory, replicas).

### C) Operational envelope knobs (allowed to vary; still shouldn’t change meaning)

These change “how often/at what scale” DL runs, not what it means.

* **Evaluation cadence** (poll interval / schedule).
* **Window labels you expect to be present** (rolling_1m/5m etc).
* **Max decision age** (how stale a DegradeDecision may be before DF must treat it as unsafe). (This is the *companion* to signal staleness; same idea.)
* **History retention for posture-change facts** (control stream retention differs by env; semantics don’t).
* Local/dev may run single instance; prod may run HA — but “one active writer per scope” is the intent.

### D) Visibility knobs (optional features that must not become correctness dependencies)

* **Emit posture-change facts to `fp.bus.control.v1`**: on/off by environment (I’d keep it *on* in dev/prod; optional in local).
* Log verbosity / trace sampling (local debug heavy; prod sampled).

If enabled, any DL-emitted control facts must obey the **Canonical Event Envelope** (required: `event_id, event_type, ts_utc, manifest_fingerprint`).

---

## 2) Practical “profile matrix” (directional defaults)

This is intentionally non-specific (no numbers), but it’s the right mental model.

### Local (laptop)

* **Policy rev**: “easy-to-trigger” or “easy-to-recover” profile (your choice), but *still a policy_rev artifact*, not code forks.
* **Signals**: must be real enough to exercise DL; run the OTel+Grafana stack locally so DL isn’t flying blind.
* **Emit control facts**: optional (nice for debugging, not required).

### Dev (shared integration)

* **Policy rev**: “prod-shaped semantics” with thresholds that catch integration breakage (missing signals, invalid policy rev, unauthorized changes).
* **Emit control facts**: on (helps teams see posture transitions and cache invalidation).
* **Goal**: dev must catch the kinds of failures prod would catch.

### Prod (hardened)

* **Policy rev**: strict corridor checks; meaningful degrade triggers.
* **Governance**: activation/rollback of DL policy rev is a governed fact (no “human memory”).
* **Emit control facts**: on.

---

## 3) Other deployment-info you should keep handy before we “enter DL”

### A) DL must be testable on the local “prod-shaped substrate”

Your deployment notes explicitly push a reference local stack (Kafka-ish bus, S3-ish store, Postgres, OTel stack) so hot-path semantics are real. DL depends on that reality (consumer lag signals, error rates, etc.).

### B) DL has to live inside the “config promotion lanes”

Your CI/CD story treats policy configs (including **degrade thresholds**) as promoted artifacts with approvals and governance facts. DL should be designed so a policy rev can be validated in CI, activated in dev, then activated in prod.

### C) DL control events must be envelope-valid

If we emit `dl.posture_changed.v1`, it’s a canonical envelope event (with required fields) on `fp.bus.control.v1`.

---

## 4) Minimal knob set I’d want you to *actually* hold onto right now

If you only remember **7 knobs**, make them these:

1. `dl.policy_rev_active` (threshold profile revision)
2. `dl.eval_interval` (cadence)
3. `dl.max_signal_age` (staleness threshold; stale ⇒ unhealthy is pinned) 
4. `dl.quiet_period` (hysteresis recovery posture) 
5. `dl.posture_store` (Postgres schema/table for current posture) 
6. `dl.emit_control_events` (on/off; topic = `fp.bus.control.v1`)
7. `dl.default_on_error = FAIL_CLOSED` (pinned)

That set is enough to keep the environment ladder honest while we still treat DL as opaque.

---

## USER: PAUSE FOR REFLECTION

Absolutely. Here’s the **outer-network “freeze frame”** for **DL-as-a-vertex**—the stuff we’ve already exposed and must **not drift** from when we step inside DL.

I’m going to treat this as the **authoritative outer contract** for DL (bounded by your platform pins + environment ladder).

---

## 1) DL’s position and authority in the platform graph

### DL’s role

DL is **control-plane authority embedded in the hot path**:

* It is the **sole authority** for:
  `degrade_mode + capabilities_mask + provenance`
* It does **not** decide fraud outcomes; it **constrains what DF is allowed to do**.

### Non-negotiable enforcement point

**DF is the mandatory enforcement point**:

* DF treats `capabilities_mask` as **hard constraints** (disabled = “does not exist”).
* DF **records the exact posture used** into decision provenance → DLA (audit).

---

## 2) Complete DL adjacency map (direct joins only)

### Inbound joins (what DL depends on)

1. **Obs/Gov Signals → DL**
   Windowed health/lag/error signals (OFP, IEG, DF/model, EB lag/watermarks, AL risk if you include it).

2. **Policy/Profile Store → DL**
   Versioned threshold/corridor profiles (policy config).

3. **Governed activation stream (indirect)**
   Policy rev activation is a governed fact; DL behavior changes via active `policy_rev`.

### Outbound joins (what DL produces)

4. **DL → DF (J9)**
   Returns `DegradeDecision` (mode + mask + provenance + decided_at + policy_rev).

5. **DL → dl.current_posture store**
   Derived, rebuildable posture state (atomic per scope) used for fast reads + hysteresis continuity.

6. **DL → fp.bus.control.v1** (optional)
   Emits posture-change facts (`dl.posture_changed.v1`) for visibility + cache invalidation.
   If emitted, it must be **Canonical Event Envelope shaped**.

7. **DL → optional readers** (optional)
   Dashboards/tools may read posture for visibility/caching/internal tuning **only**—no stealth coupling.

---

## 3) Production paths DL participates in (multi-hop)

### B8 Hot decision path (canonical)

`EB → DF → (DL posture) → Registry(bundle) → OFP/IEG (if allowed) → DF → AL → DLA`

**Pinned ordering inside DF (drift killer):**

1. Get DL posture **before** choosing expensive/optional work
2. Resolve bundle **compat-aware with degrade constraints**
3. Get OFP features using **event_time as boundary**
4. Use IEG only if allowed; record graph_version if used
5. Emit actions obeying action_posture
6. Record everything (including degrade posture used) into audit

### B9 Feature acquisition under constraints

`DF (obeys mask) → OFP → DF (records feature snapshot provenance)`

### B10 Identity context under constraints

`DF (obeys mask) → IEG (optional) → DF (records graph_version)`

### B11 Bundle resolution under constraints

`DF (obeys mask) → Registry → DF (records ActiveBundleRef; fail-closed if incompatible)`

### B12–B14 Control visibility + audit + policy-change

* `DL posture-change → fp.bus.control.v1 → dashboards/alerts/invalidations` (optional)
* `DLA → investigations/offline parity` (audit reconstruction)
* `policy propose→approve→activate → DL loads policy_rev → DF decisions cite rev → DLA records`

---

## 4) Production feedback loops around DL (the “why hysteresis exists”)

These loops **must** exist conceptually even if they’re not always triggered at small scale:

* **C15 OFP load-shedding**: OFP unhealthy → DL restricts feature groups → OFP load drops → recovery → DL upshifts
* **C16 IEG shedding**: IEG unhealthy → DL disables IEG → recovery → upshifts
* **C17 EB lag/backpressure**: lag up → DL reduces per-event compute (features/models/IEG) → catch up → upshift
* **C18 Model/runtime**: model/DF slow → DL disables heavy stages → recovery → upshift
* **C19 Action-risk**: AL failures/risk → DL sets conservative action_posture → fewer risky actions → stabilize
* **C20 Governance tuning**: posture history/outcomes → new policy_rev → DL behavior changes under governed activation

---

## 5) Outer-network pins we must preserve when we “enter DL”

These are the **drift tripwires**:

### A) Single authority / no stealth coupling

Only DL decides degrade posture; nobody else infers it from metrics. DF must enforce.

### B) Explicit + auditable

Every decision can answer: *what degrade posture was used and why?*
(DF records posture used → DLA).

### C) Fail toward safety

If DL is missing/unavailable/stale/invalid → DF behaves conservatively and records fallback.

### D) Deterministic + stable

Same snapshot + same policy_rev ⇒ same output; downshift fast, upshift slow (quiet period, one rung).

### E) Policy profile is governed

Thresholds/corridors are policy config: versioned, promoted, activated, rollbackable; decisions cite policy_rev.

### F) Environment ladder constraint

Same semantics everywhere; environment differences are **profiles** (policy_rev, thresholds, staleness) + operational envelope, not “if prod then…”.

### G) Control events (if used) must be envelope-valid

Any posture-change event on control bus must conform to the canonical envelope.

---

## 6) What’s still intentionally “loose” (safe to decide inside DL later)

These are *not* outer-network commitments (we can decide them as we illuminate internals):

* whether DF calls DL synchronously vs reads `dl.current_posture` (both allowed; semantics identical)
* exact threshold numbers/corridors (policy config)
* exact signal aggregation math (p95/p99; window lengths)
* whether control-bus posture-change events are always on vs profile-toggled (semantics unchanged either way)

---

## 7) Minimal drift-checklist for the next stage (entering DL)

When we start illuminating DL internals, every internal module must ultimately satisfy:

1. **Produce a DegradeDecision** (mode/mask/provenance/decided_at/policy_rev)
2. **Maintain posture state** (derived, atomic per scope; hysteresis continuity)
3. **Consume governed policy revs** correctly (atomic switch, cite rev)
4. **Consume signals as snapshots** with staleness handling (stale/missing ⇒ unhealthy)
5. Optionally **emit envelope-valid posture-change facts** to control bus
6. Never create hidden “second sources of degrade truth” anywhere else

That’s the outer network locked.

---

Yep — one level deeper, **DL’s internal network** can be cleanly decomposed into a small set of **internal subnetworks (modules)** that map 1:1 onto the outer joins we froze. We’ll keep each subnetwork **opaque** for now.

## DL internal subnetworks (opaque boxes)

### S1) Signal Plane

**Purpose:** turn raw observability into a **stable, windowed SignalSnapshot** (with staleness handling).
**Consumes:** Obs/Gov metrics/signals (A4).
**Produces:** `SignalSnapshot(scope, window, observed_at_utc, readings[])` to the evaluator.

---

### S2) Policy Plane

**Purpose:** load/validate the **active threshold profile** (policy config) and expose it as a **PolicyContext**.
**Consumes:** policy/profile store + activation pointer (A3/B14).
**Produces:** `PolicyContext(policy_rev, thresholds/corridors, required_signals, hysteresis params)`.

*(This subnetwork is where “policy vs wiring” separation lives: only policy_rev + policy artifact changes behavior; wiring doesn’t.)*

---

### S3) Scope & Partition Plane

**Purpose:** define “**what posture are we deciding for**” and enforce **one-writer-per-scope** semantics.
**Consumes:** scope requests (GLOBAL vs ContextPins), plus optional partitioning/election signals.
**Produces:** canonical `scope_key` + any coordination decision (“I am the active evaluator for this scope”).

*(This keeps us honest about whether posture is global or scoped, without bleeding scope logic everywhere.)*

---

### S4) Evaluation & Hysteresis Plane

**Purpose:** the **brain**: take `SignalSnapshot + PolicyContext + PriorPostureState` and produce the next **DegradeDecision** deterministically.
**Consumes:** S1 + S2 + S5 (prior state).
**Produces:** `DegradeDecision(mode, mask, provenance, decided_at_utc, policy_rev, posture_seq?)`.

*(This is the only place allowed to “decide mode.” It’s also where fail-closed is enforced if inputs are missing/stale/invalid.)*

---

### S5) Posture State Plane

**Purpose:** maintain the **derived, rebuildable** posture store and hysteresis continuity.
**Consumes:** DegradeDecision + minimal continuity fields.
**Produces:** atomic `dl.current_posture(scope_key)`, plus read access for DF / tools.

*(This subnetwork owns atomicity, monotonic posture_seq, and “freshness fields exist.”)*

---

### S6) Serving Plane (DF Join Surface)

**Purpose:** provide the **J9-facing read** of posture to DF with freshness semantics.
**Consumes:** S5 (current posture) and optionally S4 (if you allow inline compute).
**Produces:** “GetDegradeDecision(scope, event_time)” → DegradeDecision (fresh-enough or fail-safe).

*(Critically: serving does **not** invent decisions; it either returns a valid decision or returns/forces the fail-safe posture.)*

---

### S7) Control Emission Plane (optional)

**Purpose:** emit **posture-change facts** on `fp.bus.control.v1` when enabled.
**Consumes:** posture-change events from S5/S4.
**Produces:** `dl.posture_changed.v1` (canonical envelope shaped), idempotent per transition.

*(This is visibility + invalidation only; never the source of truth.)*

---

### S8) DL Self-Health & Telemetry Plane

**Purpose:** ensure DL itself is observable and **fails safe** when blind or broken.
**Consumes:** internal health (can’t read signals, can’t load policy, can’t write state, clock skew).
**Produces:** metrics/logs/traces + “DL unhealthy → force conservative posture” signals into S4/S6.

*(This is how we prevent “DL silently dead but system stays NORMAL.”)*

---

## How these subnetworks connect (still opaque inside each)

```
Obs Signals ---> [S1 Signal Plane] ----+
                                      |
Policy Store --> [S2 Policy Plane] ---+----> [S4 Eval & Hysteresis] ---> [S5 Posture State]
                                      |                                  |         |
Scope reqs ---> [S3 Scope/Partition] -+                                  |         +--> [S7 Control Emission] (optional)
                                                                         |
                                                                         +--> [S6 Serving Plane] ---> DF (J9)

                     [S8 Self-Health/Telemetry] feeds safety posture into S4/S6
```

## Why this breakdown is “drift-resistant”

* Every outer join has a **single internal owner**:

  * A4 signals → **S1**
  * A3 policy → **S2**
  * A5 posture store → **S5**
  * J9 to DF → **S6**
  * A6 control events → **S7**
* “Who decides mode?” is unambiguous: **only S4**.
* Fail-safe posture can’t “leak away”: **S8 → S4/S6** ensures “blind ⇒ conservative.”

---

Yep — here’s the **internal DL network** in production terms, one level deep: **subnetworks S1–S8 are opaque nodes**, and we’re just identifying the **joins (edges), paths (multi-hop routes), and loops (feedback cycles)** *inside* DL.

I’ll use the subnetwork names we already pinned:

* **S1** Signal Plane
* **S2** Policy Plane
* **S3** Scope & Partition Plane
* **S4** Evaluation & Hysteresis Plane
* **S5** Posture State Plane
* **S6** Serving Plane (DF join surface)
* **S7** Control Emission Plane (optional)
* **S8** Self-Health & Telemetry Plane

---

## 1) Internal joins (direct edges) in production

Here are the **complete internal edges** DL needs (some optional, marked):

### JI-01: SignalSnapshot

**S1 -> S4**
Payload: `SignalSnapshot{scope_key, window_id, observed_at_utc, readings[], staleness_flags}`
Invariant: snapshot is **stable + timestamped** so evaluation isn’t “hidden now”.

### JI-02: PolicyContext

**S2 -> S4**
Payload: `PolicyContext{policy_rev, thresholds/corridors, required_signals, hysteresis_params, max_signal_age}`
Invariant: policy is **versioned** and evaluation cites the rev.

### JI-03: ScopeKey / Ownership

**S3 -> (S1, S4, S5, S6)**
Payload: `ScopeContext{scope_key, pins/global, writer_role}`
Invariant: “what posture are we deciding for?” is explicit; (in prod) one-writer-per-scope is enforced.

### JI-04: PriorPostureState (hysteresis memory)

**S5 -> S4**
Payload: `PriorState{last_mode, last_mask, last_transition_at, quiet_period_until, posture_seq}`
Invariant: minimal memory only; store remains **derived/rebuildable**.

### JI-05: DecisionCommit (atomic write)

**S4 -> S5**
Payload: `DegradeDecision + continuity{posture_seq++, quiet_period_until}`
Invariant: write is **atomic**, posture_seq is **monotonic per scope**, decision includes `decided_at_utc` + `policy_rev`.

### JI-06: CurrentPostureRead

**S5 -> S6**
Payload: `CurrentPostureRecord{decision, decided_at_utc, policy_rev, posture_seq}`
Invariant: S6 must be able to enforce freshness using `decided_at_utc`.

### JI-07 (optional): InlineEvaluate

**S6 -> S4**
Trigger: serving detects **missing/stale** posture and is allowed to force a compute.
Invariant: serving never “invents” a decision; it either returns a valid decision or forces safe fallback.

### JI-08 (optional): PostureChangedNotify

**S5 -> S7** (and optionally **S4 -> S7** if you publish immediately on decision)
Payload: `PostureChanged{scope_key, new_decision, prev_ref, posture_seq}`
Invariant: notification only when posture materially changes.

### JI-09: TelemetryFeed

**(S1,S2,S3,S4,S5,S6,S7) -> S8**
Payload: health counters, error events, timings, “can’t read signals”, “can’t load policy”, “can’t write state”, etc.

### JI-10: SafetyGate / ForceFailSafe

**S8 -> (S4, S6)**
Payload: `HealthGate{dl_health_state, forced_mode?=FAIL_CLOSED, reason}`
Invariant: if DL is blind/broken, the system moves **toward safety**, not silent normal.

### JI-11 (optional): RebuildTrigger

**S8 -> (S5 and/or S4)**
Trigger: store corruption, missing posture for hot scopes, policy mismatch, etc.
Invariant: rebuild is allowed because posture store is derived.

---

## 2) Internal paths (multi-hop routes) in production

Think of these as the “traffic patterns” *inside* DL.

### IP-01: Periodic evaluation cycle (steady state)

`S1 signals -> S4`
`S2 policy   -> S4`
`S3 scope    -> S4`
`S5 prior    -> S4`
`S4 decide   -> S5 commit`
`S5 (optional) -> S7 publish`
This is the canonical “DL keeps posture current” path.

### IP-02: Decision-time serving path (DF-facing)

`S6 receive request -> S5 read current posture -> S6 return decision`

* If stale/missing: either

  * **(a)** `S6 -> S4 inline evaluate -> S5 commit -> S6 return` (if allowed), or
  * **(b)** `S6 return FAIL_CLOSED (with provenance: DL unavailable/stale)`.

### IP-03: Signal refresh path

`S1 pulls/receives new readings -> produces SignalSnapshot -> S4 eval path`
This is basically “signals changed, recompute posture”.

### IP-04: Policy activation / policy refresh path

`S2 observes active policy_rev change -> emits new PolicyContext -> S4 eval -> S5 commit -> (optional S7 publish)`
Key point: policy changes cause **explicit posture changes** (and must be auditable via policy_rev in the decision).

### IP-05: Posture change publication path (optional)

`S5 commit posture change -> S7 emit dl.posture_changed -> (telemetry to S8)`
This is visibility + invalidation only; correctness remains via S5/S6.

### IP-06: Startup / restart path

`S2 load active policy -> S1 warm signals -> S5 read last posture (if any) -> S4 evaluate -> S5 commit -> S6 begin serving`
This is where “derived store” and “fail-safe” must behave predictably.

### IP-07: DL self-health fail-safe path (internal safety)

`S8 detects blindness/breakage -> S8 gate -> S4/S6 force FAIL_CLOSED -> S5 commit (optional) -> S6 serves conservative posture`
This ensures “DL failure is visible and safe”.

---

## 3) Internal loops (feedback cycles) that exist in production

These are the internal loops that matter because they affect stability, flapping, and safety.

### IL-01: Hysteresis loop (anti-flap core)

`S4 uses prior_state from S5 -> decides -> writes next_state to S5 -> becomes next prior_state`
This is why DL’s posture is stable (quiet period, one-rung recovery).

### IL-02: Serving freshness loop

`S6 reads S5 -> detects staleness -> (optional) triggers S4 inline -> S5 refreshes posture -> S6 returns fresh`
If inline compute is disabled, the loop becomes: stale -> serve FAIL_CLOSED.

### IL-03: Signal staleness / blindness loop

`S1 sees stale/missing signals -> marks unhealthy -> S4 downshifts -> S5 commits -> S6 serves more conservative`
This loop is what prevents “metrics pipeline died but system stayed NORMAL”.

### IL-04: Policy churn stabilization loop

`S2 policy_rev changes -> S4 recalculates -> S5 commits -> (optional) S7 publishes -> S8 observes`
This is the “governed change becomes operational posture” loop.

### IL-05: Scope ownership / single-writer loop

`S3 maintains writer_role per scope -> only active writer commits in S5 -> prevents posture thrash`
This loop exists whenever you run multiple DL instances for HA.

### IL-06 (optional): Control publish retry loop

`S7 publish fails -> retries with same stable event_id -> eventual publish -> S8 observes`
Important only if you want strong visibility; it must be idempotent.

### IL-07: DL self-healing loop

`S8 detects internal faults -> triggers rebuild / safe posture -> DL stabilizes -> S8 clears gate`
This is the “DL doesn’t silently rot” loop.

---

## 4) A compact internal network sketch (opaque nodes, labeled edges)

```text
Obs signals --> [S1] --JI-01--> [S4] --JI-05--> [S5] --JI-06--> [S6] --> (DF boundary)
Policy rev ----> [S2] --JI-02--> [S4]            |  \
Scope reqs ---> [S3] --JI-03--> [S4,S5,S6]       |   \--JI-08--> [S7] --> (control bus boundary, optional)
                                                  \
All modules -----------------JI-09---------------> [S8] --JI-10--> [S4,S6]
```

---

Cool — we’ll **stay one level deep**: illuminate **JI-01 → JI-04** as *internal edges* between opaque subnetworks, and I’ll **pin what crosses each join + who owns what + the invariants** so we don’t drift.

Here’s the little slice of the internal graph we’re opening:

```
          [S3 Scope/Partition]
              |        |            |
              v        v            v
[S1 Signal Plane]   [S2 Policy]   [S5 Posture State]
        |               |               |
        +------JI-01----+------JI-02----+
                        |
                        v
              [S4 Eval & Hysteresis]
                    ^ 
                    |
                 JI-04
```

---

# JI-01 — **SignalSnapshot** (S1 → S4)

## Boundary decision

**S1 is allowed to normalize/derive signals. S1 is NOT allowed to decide degrade.**
So: S1 can say “this reading is stale/missing,” but S1 cannot say “therefore mode=DEGRADED_2.”

## Why this join exists

S4 must make a **deterministic decision** from a **stable snapshot**, not from “whatever the metrics backend returns right now” (hidden-now bug).

## What crosses the join (pinned payload shape)

`SignalSnapshot` is a *closed bundle* for one evaluation tick:

* `scope_key` (from S3; even if most signals are global)
* `snapshot_window` (e.g., `rolling_1m`, `rolling_5m`)
* `snapshot_end_utc` (the anchor time this snapshot represents)
* `observed_at_utc` (when S1 assembled it)
* `readings[]` where each reading has:

  * `signal_name` (stable ID)
  * `source_component` (OFP/IEG/DF/EB/AL/etc.)
  * `stat` (gauge / rate / p95 / etc. — whatever your signal catalogue uses)
  * `value` + `unit`
  * `quality` ∈ `{OK, STALE, MISSING, ERROR}`
  * `sample_time_utc` (time of the underlying sample, if available)
* `snapshot_id` (optional but I’m pinning it as recommended): deterministic hash of canonicalized readings + snapshot_end_utc + scope_key

### Determinism rule (hard)

S4 must never depend on S1’s *iteration order* or backend quirks.
So S1 must output readings in **stable canonical order** (lexicographic by `signal_name`, then `stat`, then `source_component`).

## Staleness/missing semantics (hard)

S1 must **never drop** a required reading silently.

* If a signal is absent → include it with `quality=MISSING`
* If the latest sample is too old (policy sets `max_signal_age`) → `quality=STALE`
* If backend/query failed → include `quality=ERROR` and an error code (string ok)

This is critical because S4’s rule is “missing/stale ⇒ unhealthy” (can downshift, blocks upshift). That rule belongs to S4/policy, but it only works if S1 is explicit.

## Scope rule (important)

Even if signals are globally scoped (e.g., EB consumer lag), the snapshot is still **scoped**:

* S1 either *replicates global readings* into each scope snapshot, or
* S1 emits a `GLOBAL` snapshot and S4 merges it with the scope snapshot.

**Designer pin:** do **not** let S4 query two places ad hoc. Pick one consistent approach.
My v0 pick: **S1 emits “scope snapshots” that already include the needed global readings**, so S4 consumes exactly **one** snapshot input.

## Failure posture at this join

If S1 can’t assemble a snapshot, it must still emit a snapshot with:

* `quality=ERROR/MISSING` for required signals
* a `snapshot_build_status = FAILED`

That way S4 can deterministically fail toward safety rather than “no data so do nothing.”

---

# JI-02 — **PolicyContext** (S2 → S4)

## Boundary decision

**S2 owns policy loading, validation, and atomicity. S2 does NOT evaluate.**
S2 delivers “the rules”; S4 applies them.

## Why this join exists

S4 must always know **exactly which policy revision** it used, and must never evaluate against a half-updated profile.

## What crosses the join (pinned payload shape)

`PolicyContext` (atomic, self-contained):

* `policy_rev` (stable revision identifier)
* `policy_digest` (content hash of the policy artifact)
* `effective_from_utc` (optional; helps with audit/debug)
* `required_signals[]` (stable list of `signal_name` that must be present/OK to allow upshift)
* `thresholds/corridors` expressed as:

  * per-mode *entry conditions*
  * per-mode *exit conditions*
  * tie-break posture: “most degraded eligible”
* `hysteresis_params`:

  * downshift: immediate
  * upshift: quiet period + one rung at a time
  * per-rung quiet period durations (or a shared one)
* `max_signal_age` (staleness threshold used by S1/S4)
* `max_decision_age` (freshness threshold used by S6/DF-side safety)
* `mode_to_capabilities_mask` mapping table (mode ⇒ mask)

## Atomicity rule (hard)

S2 must guarantee **single-rev evaluation**:

* S4 sees either the *old* PolicyContext or the *new* one, never a mix.
* If a new rev is invalid/unloadable, S2 must **not** hand it to S4.

**Designer pin:** “last-known-good policy” is a first-class concept in S2.

## Failure posture at this join (hard)

If S2 cannot provide a valid PolicyContext:

* it emits `PolicyContext{status=UNAVAILABLE}` (with reason)
* S4 must treat that as **evaluation unsafe** ⇒ produce FAIL_CLOSED (via S8→S4 gate or S4’s own rule)

No “best effort thresholds” in code.

---

# JI-03 — **ScopeContext / Ownership** (S3 → S1/S4/S5/S6)

## Boundary decision

**S3 is the only place that defines scope keys and writer ownership.**
No other subnetwork should invent scope encoding, sentinel values, or leadership rules.

## Why this join exists

Without this join, you get silent drift like:

* “some parts think DL is global”
* “some parts think DL is per-run”
* “two DL instances both write posture_seq”

## What crosses the join (pinned payload shape)

`ScopeContext`:

* `scope_kind` ∈ `{GLOBAL, MANIFEST, RUN}` (v0 set; extendable)
* `pins` (ContextPins-like fields; for RUN you include run_id etc.)
* `scope_key` (canonical string encoding; **the** key used everywhere)
* `writer_role` ∈ `{ACTIVE, STANDBY, READONLY}`
* `lease` (if ACTIVE): `{lease_id, lease_expires_at_utc}`

### Canonical encoding rule (hard)

`scope_key` must be:

* stable across processes
* stable across envs
* stable across time

**Designer pin:** every place that needs a key consumes it from S3; no re-encoding.

### Global sentinel rule (hard)

DL needs a global scope for some signals/decisions. S3 must provide a **single sanctioned GLOBAL scope_key**, not ad hoc strings.

## Ownership rule (hard)

For each `scope_key` there is **at most one ACTIVE writer** committing posture to S5 at a time.
(How S3 achieves that is implementation—lease/election—but the network law is non-negotiable.)

## How S3 fans out

* **To S1:** tells it which scopes to build snapshots for (and whether to include global readings inline)
* **To S4:** tells it which scope is being evaluated (and whether this evaluator is allowed to commit)
* **To S5:** tells it which key to store under + whether it should accept writes from this instance
* **To S6:** tells it how to interpret requests (“GLOBAL vs RUN posture”)

---

# JI-04 — **PriorPostureState** (S5 → S4)

## Boundary decision

**S5 owns stored continuity; S4 treats it as memory, not truth.**
S4 uses it only for hysteresis + monotonic posture sequencing.

## Why this join exists

This join is what makes DL **stable** (anti-flap) without turning the store into a primary source of truth.

## What crosses the join (pinned payload shape)

`PriorState` (minimal hysteresis memory):

* `last_mode`
* `last_mask_digest` (or a compact fingerprint of the last mask)
* `last_decided_at_utc`
* `last_transition_at_utc`
* `quiet_period_until_utc`
* `posture_seq` (monotonic integer per scope)
* `prior_state_status` ∈ `{PRESENT, MISSING, CORRUPT}`

### Minimality rule (hard)

No heavy history, no metric payloads, no policy blobs.
Just enough to:

* prevent flapping
* compute the next posture_seq
* detect “real change vs re-write”

## Missing/corrupt state posture (hard)

If PriorState is missing/corrupt:

* S4 must still evaluate using **current snapshot + policy**
* and S5 will be seeded with a fresh record on first commit

**Safety pin:** until a valid posture exists, S6/DF must behave conservativelyF-like safe fallback (FAIL_CLOSED or stricter) rather than assume NORMAL.

## Monotonic sequence rule (hard)

`posture_seq` is owned by S5 and must only move forward.

* S4 may propose “next_seq = prior_seq + 1”
* but S5 is the final authority that enforces monotonicity (especially under HA).

---

## Quick “what’s in / what’s out” across these joins

**IN (allowed at this layer):**

* S1 derives/normalizes metrics into explicit readings + quality flags
* S2 delivers atomic policy contexts with rev+digest
* S3 defines scopes + writer ownership via leases
* S5 provides minimal hysteresis memory + monotonic sequencing

**OUT (not allowed, would violate boundaries):**

* S1 or S2 choosing degrade_mode
* S4 querying metrics/policy directly (bypassing S1/S2)
* Any module inventing its own scope encoding
* Any module treating S5 as primary truth (instead of derived continuity)

---

Great — we’ll illuminate **JI-05 → JI-08** as *internal joins* (S4–S7 remain opaque), and I’ll **pin what crosses, who owns what, and the production invariants** so this layer can’t drift later.

Quick internal slice:

```
[S4 Eval/Hysteresis] --JI-05--> [S5 Posture State] --JI-06--> [S6 Serving]
          ^                           |
          |                           +--JI-08--> [S7 Control Emission] (optional)
          +-----------JI-07-----------+
              (Serving-triggered eval, optional)
```

---

# JI-05 — DecisionCommit (S4 → S5)

## Boundary decision (authority)

* **S4 decides** *what* the posture should be (mode/mask/provenance).
* **S5 owns** *committing* posture safely (atomicity, monotonic seq, idempotency on retries).

S4 is not allowed to “write around” S5; all durable posture state flows through JI-05.

## What crosses the join (pinned commit payload)

`CommitRequest{ scope_key, decision, continuity, commit_id }`

Where:

### `decision` (the DF-facing truth we’re committing)

* `mode`
* `capabilities_mask`
* `provenance` (or a compact provenance summary + refs)
* `policy_rev` (+ optional digest)
* `snapshot_id` (from S1; ties decision to a specific snapshot)
* `decided_at_utc` (domain time of the evaluation)

### `continuity` (minimal hysteresis state to persist)

* `quiet_period_until_utc`
* `last_transition_at_utc`
* `prior_seq` (the seq S4 read via JI-04)
* `material_change` (boolean: “mode/mask/policy_rev changed?”)

### `commit_id` (idempotency key for retries)

A stable id derived from `(scope_key, snapshot_id, policy_rev)` or an explicit `degrade_decision_id`.
This exists so if S4 retries the same commit, S5 can treat it as **idempotent**.

## S5’s response (pinned “commit receipt”)

S5 returns:

`CommitResult{ status, scope_key, posture_seq, stored_record_ref?, reason? }`

* `status ∈ {COMMITTED, NOOP, CONFLICT, REJECTED}`
* `posture_seq` is the authoritative monotonically increasing sequence for **material changes**.

## Commit semantics (hard pins)

### 1) Atomic record write

S5 must update the “current posture record” **atomically**:

* mode/mask/provenance/policy_rev/decided_at **and**
* continuity fields (quiet period, last transition, seq)
  …as one unit.

### 2) Monotonic `posture_seq` only on material change

**Pin:** `posture_seq` increments **only when posture materially changes**:

* mode changes, or
* capabilities_mask changes, or
* policy_rev changes, or
* evaluation transitions into/out of “forced fail-safe” (treated as a posture change)

If S4 re-evaluates and gets the **same** posture:

* S5 returns `NOOP`
* S5 may update “last_evaluated_at_utc” / “decided_at_utc” to keep freshness honest **without** incrementing seq
* S7 publish is **not triggered** (see JI-08)

This keeps the control stream quiet and makes “posture transitions” distinct from “posture refreshed.”

### 3) Compare-and-swap to avoid split-brain writers

S5 treats `prior_seq` as a CAS guard:

* If `prior_seq` matches current → accept commit
* If not → return `CONFLICT` (S4 must reread JI-04 and decide again)

This is the internal enforcement that prevents two writers (or stale evaluators) from bouncing posture.

### 4) Fail-safe on rejected commits

If S5 cannot commit (storage error/corruption):

* that condition must surface to **S8** (telemetry)
* and S6/DF must not be tricked into trusting stale posture forever (JI-06/JI-07 handle this)

---

# JI-06 — CurrentPostureRead (S5 → S6)

## Boundary decision (authority)

* **S5 is the source** of “current posture record” (derived but authoritative *within DL*).
* **S6 is a pure serving layer**: it enforces freshness and returns the posture; it does not decide.

## What crosses the join (pinned read payload)

`CurrentPostureRecord{ scope_key, decision, posture_seq, continuity, record_meta }`

Minimum required fields:

### `decision`

* `mode`
* `capabilities_mask`
* `policy_rev`
* `decided_at_utc`
* `snapshot_id`
* `provenance` (full or summary)

### `record_meta`

* `record_status ∈ {OK, MISSING, CORRUPT}`
* `last_write_at_utc` (store time; optional)
* `etag` or `record_digest` (optional; helps caching)

### `continuity` (optional for serving, but safe to include)

* `quiet_period_until_utc`
* `last_transition_at_utc`

## Freshness rule (hard)

S6 must evaluate freshness using the **request’s decision boundary time**, not hidden wall-clock:

`age = request.decision_time_utc - record.decided_at_utc`

If `age > policy.max_decision_age` → treat posture as **stale**.

*(This keeps determinism in tests/replay harnesses and avoids “S6’s clock drift” becoming behavior.)*

## Missing/corrupt posture rule (hard)

If `record_status != OK`, S6 must **not** guess. It either:

* triggers JI-07 (if allowed), or
* serves safe fallback (FAIL_CLOSED posture with provenance “NO_POSTURE/STALE/STORE_ERROR”).

---

# JI-07 — InlineEvaluate trigger (S6 → S4) — optional but production-real

## Boundary decision (authority)

* S6 **requests** evaluation; S4 **performs** it.
* S6 never computes posture; it only decides whether it needs a refresh.

## When S6 is allowed to trigger it (pinned triggers)

S6 triggers JI-07 only when:

1. posture is **missing**
2. posture is **stale** beyond `max_decision_age`
3. posture exists but S6 detects **policy mismatch** (record.policy_rev != active.policy_rev) and serving requires immediate convergence

## What crosses the join (pinned request payload)

`EvaluateNowRequest{ scope_key, decision_time_utc, reason, deadline_utc, singleflight_key }`

* `decision_time_utc`: the boundary S6 must serve under
* `deadline_utc`: if S4 can’t respond by this, S6 will fail safe (don’t block hot path)
* `singleflight_key`: ensures only one in-flight eval per scope (prevents thundering herd)

## Response shape (pinned)

`EvaluateNowResult{ status, decision?, commit_ref?, reason? }`

* `status ∈ {EVALUATED_AND_COMMITTED, EVALUATED_BUT_NOT_COMMITTED, FAILED}`
* In v0, we prefer **EVALUATED_AND_COMMITTED** (so S5 remains the single posture source).

## Failure posture (hard)

If inline evaluation can’t finish by deadline (or S4 unavailable):

* S6 returns **FAIL_CLOSED** (with explicit provenance: “INLINE_EVAL_TIMEOUT/FAILED”)
* and S8 telemetry must reflect that DL is struggling (so ops sees it)

**Designer pin:** inline evaluation is an *escape hatch*, not the primary mechanism. Periodic eval should keep posture fresh; inline eval prevents catastrophic staleness after restarts.

---

# JI-08 — PostureChangedNotify (S5 → S7) — optional control emission

## Boundary decision (authority)

* S5 is the **only source** of “posture changed” events (because it owns material-change detection + seq).
* S7 is a **publisher** only; it must not decide what counts as change.

## What crosses the join (pinned notify payload)

`PostureChanged{ scope_key, posture_seq, new_decision_ref, prev_decision_ref?, decided_at_utc, policy_rev, change_kind }`

Where `change_kind` might be:

* `MODE_CHANGED`
* `MASK_CHANGED`
* `POLICY_REV_CHANGED`
* `FORCED_FAILSAFE_ENTERED/EXITED`

## Change detection rule (hard)

**Only** material changes (as defined in JI-05) trigger JI-08.

No-op refreshes (same posture) do **not** notify S7.

## Reliability rule (production-real, without overspec)

Publishing must not block committing:

* S5 commits posture regardless of bus availability.
* S7 publishes from a **durable pending queue/outbox** *or* retries idempotently.

**Designer pin:** if you implement control events, you must not lose them silently on process crash right after commit. (Outbox is the clean mental model; exact tech is implementer choice.)

## Idempotency rule (hard)

S7 must publish events idempotently:

* stable `event_id` derived from `(scope_key, posture_seq)` (or decision_id)
* ordering guaranteed **per scope** by partitioning on scope_key
* duplicates are acceptable; consumers must dedupe by event_id

## Envelope compliance (hard)

If emitted to `fp.bus.control.v1`, the event must be **canonical-envelope shaped** (including required identity fields).
Global scope uses the sanctioned “global control scope” approach we already pinned; S3/S7 must not invent alternatives.

---

## Summary pins for JI-05 → JI-08 (so we don’t drift)

1. **S5 is the commit authority**: atomic writes + CAS + monotonic `posture_seq` on material change only.
2. **S6 is a serving gate**: enforces freshness using request boundary time; never guesses on missing/corrupt.
3. **Inline eval is an escape hatch** with deadlines + singleflight; failure → serve FAIL_CLOSED.
4. **Control publishing is optional** but if enabled must be envelope-valid, idempotent, and non-blocking to commits.

---

Perfect — **S8 (Self-Health & Telemetry Plane)** is the part of DL that stops the entire platform from drifting into *silent normal* when DL is blind, broken, stale, or split-brain. These joins are where we pin that *mechanically*.

We’ll illuminate **JI-09 → JI-11** at the same level as before: **subnetworks stay opaque**, we just define the **internal boundary contracts** between them.

---

# JI-09 — TelemetryFeed

**(S1,S2,S3,S4,S5,S6,S7) → S8**

## Boundary decision (authority)

* Every subnetwork is responsible for **reporting its own health truth**.
* **Only S8** is responsible for **turning that into “DL can/can’t be trusted”** and issuing safety gates (JI-10) / rebuild triggers (JI-11).

This prevents each module from “handling failures” in ad hoc ways that would drift the outer network semantics.

## What crosses the join (pinned payload family)

I’m pinning that JI-09 carries two kinds of telemetry payloads:

### 1) **HealthEvents** (edge-triggered, low volume)

Used when something *changes state* (e.g., policy load failed, store write failing, leader lease lost).

`HealthEvent{`

* `source_module` ∈ {S1..S7}
* `scope_key` (optional; present when the issue is scope-specific)
* `kind` (enumerated; see catalogue below)
* `severity` ∈ {INFO, WARN, ERROR, CRITICAL}
* `observed_at_utc`
* `details` (small structured blob: error_code, retryable?, counts, last_success_at_utc, etc.)
  `}`

### 2) **HealthStats** (level-triggered, periodic summary)

Used for rates/latencies and “still broken/still healthy.”

`HealthStats{`

* `source_module`
* `scope_key` (optional)
* `window_id` (rolling_1m/5m)
* `observed_at_utc`
* `metrics[]` (name, value, unit)
  `}`

**Designer pin:** S8 consumes *both*, but **never requires high-volume raw logs** to make safety decisions. If you need more detail, it should be optional observability, not a correctness dependency.

## HealthEvent catalogue (what S8 must be able to hear)

Here’s the minimum event taxonomy to keep DL safe in production:

### From S1 (Signal Plane)

* `SIGNAL_BACKEND_UNREACHABLE`
* `SIGNAL_QUERY_FAILED`
* `SIGNAL_STALE_REQUIRED` (required signal stale/missing beyond max_age)
* `SIGNAL_SNAPSHOT_BUILD_FAILED`

### From S2 (Policy Plane)

* `POLICY_POINTER_UNAVAILABLE`
* `POLICY_LOAD_FAILED`
* `POLICY_INVALID`
* `POLICY_REV_CHANGED` (not a failure, but important)

### From S3 (Scope/Partition Plane)

* `LEASE_ACQUIRED`, `LEASE_LOST`, `LEASE_CONFLICT`
* `SCOPE_SET_CHANGED` (new scope discovered/active scope removed)

### From S4 (Eval/Hysteresis)

* `EVAL_FAILED` (with reason: inputs missing vs internal error)
* `EVAL_TIMEOUT` (if you ever allow bounded evaluation)
* `EVAL_FORCED_FAILSAFE` (S8 forcing fail-closed)

### From S5 (Posture State)

* `POSTURE_STORE_READ_FAILED`
* `POSTURE_STORE_WRITE_FAILED`
* `POSTURE_RECORD_CORRUPT`
* `POSTURE_POLICY_MISMATCH` (record.policy_rev != active policy_rev)

### From S6 (Serving)

* `SERVE_STALE_POSTURE`
* `SERVE_FALLBACK_FAILCLOSED`
* `INLINE_EVAL_THROTTLED` (singleflight engaged / overload)

### From S7 (Control emission, optional)

* `CONTROL_PUBLISH_FAILED`
* `CONTROL_OUTBOX_BACKLOG_HIGH`

## Internal invariant (hard)

**No subnetwork is allowed to silently suppress failure.**
If it cannot do its job, it must emit a HealthEvent/Stats to S8.

That’s what makes the safety gate enforceable and keeps the platform from “looking healthy” when it isn’t.

---

# JI-10 — SafetyGate / ForceFailSafe

**S8 → (S4, S6)**

This is the internal join that **enforces fail-toward-safety** inside DL even when DL itself is impaired.

## Boundary decision (authority)

* **S8 decides DL self-trust** (can we evaluate? can we serve?).
* **S4 decides posture** *only when not overridden*.
* **S6 serves posture** *only when it is fresh and not overridden*.

## What crosses the join (pinned payload)

`HealthGate{`

* `dl_health_state`
* `forced_mode` (optional; when present it overrides S4/S6 output)
* `forced_capabilities_mask` (optional; usually implied by forced_mode)
* `reason_codes[]` (from the HealthEvent catalogue)
* `effective_at_utc`
* `ttl_until_utc` (optional; forces periodic revalidation)
* `scope_key` (optional; can be global or per-scope)
  `}`

### dl_health_state (designer-locked states)

I’m pinning this simple v0 lattice:

* `HEALTHY` — DL can evaluate and serve normally
* `IMPAIRED` — DL can still evaluate/serve but must be conservative about upshifts (e.g., missing non-required signals)
* `BLIND` — DL cannot trust inputs (signals/policy) ⇒ must force fail-closed
* `BROKEN` — DL cannot serve reliably (store corruption, split-brain, persistent internal failure) ⇒ must force fail-closed

**Important:** `BLIND` and `BROKEN` both imply **forced fail-closed**.

## Precedence rules (hard)

These prevent ambiguous behavior:

1. **Forced gate overrides everything**

* If `forced_mode` is present, S4 must treat it as the final decision for that scope.
* If S6 sees forced_mode present, it returns that posture regardless of store freshness.

2. **BLIND/BROKEN implies forced_mode=FAIL_CLOSED**

* Even if the last stored posture is NORMAL, S6 must not keep serving it if S8 says BLIND.

3. **Gate is monotone toward safety**

* Gate can tighten immediately (HEALTHY → BLIND instantly).
* Gate loosens only after an explicit recovery criterion (see below).

## What triggers forcing fail-closed (core triggers)

S8 must force fail-closed when any of these are true (global or per-scope):

* **Policy unavailable/invalid** (S2 failures)
* **Required signals missing/stale beyond max age** (S1 failures)
* **Posture store unreadable/corrupt** *and* serving cannot safely recompute within deadline (S5/S6 failures)
* **Split-brain writer evidence** (S3 lease conflict + S5 CAS conflicts)
* **Time sanity failure** (clock skew / non-monotone time severe enough to break staleness semantics)

## Recovery criteria (how you un-force fail-closed)

To avoid flapping and to keep it deterministic:

* S8 only clears BLIND/BROKEN when:

  * policy is loadable and valid **and**
  * required signals are present and within max age **and**
  * posture store is readable/writable **or** DL can successfully recompute and commit a posture for the scope

**Designer pin:** recovery is explicit. No “it seems fine now” without evidence.

---

# JI-11 — RebuildTrigger (optional but production-real)

**S8 → (S5 and/or S4)**

This join exists because **S5 is derived/rebuildable**, and in production you *will* have restarts, schema bumps, store corruption, policy rev jumps, and new scopes appearing.

## Boundary decision (authority)

* **S8 decides that a rebuild is required** (based on health evidence).
* **S4 performs evaluation** (compute a posture).
* **S5 commits posture** (atomic, monotone, CAS).

S8 does not rebuild itself; it triggers a coordinated internal workflow.

## What crosses the join (pinned payload)

`RebuildRequest{`

* `scope_key` or `scope_set`
* `reason` (corrupt record / missing posture / policy mismatch / after startup / new scope)
* `urgency` ∈ {BACKGROUND, PRIORITY}
* `target_policy_rev` (optional; usually “active”)
* `deadline_utc` (optional; if urgent)
* `singleflight_key` (prevents repeated rebuild storms)
  `}`

## When rebuild is triggered (core cases)

I’m pinning these as the production-necessary rebuild triggers:

1. **Startup cold state**

* posture missing for scopes that DF is requesting (or known hot scopes)

2. **Store corruption**

* record_digest mismatch, parse failure, missing required fields

3. **Policy mismatch**

* stored posture cites policy_rev that is no longer active (and convergence is required)

4. **Split-brain symptoms**

* persistent CAS conflicts / lease churn for a scope

5. **Scope set changes**

* a new scope becomes active (new run/world) and needs posture seeded

## Rebuild invariants (hard)

* Rebuild must be **idempotent** (multiple rebuild requests for same scope lead to same end posture, not oscillation).
* Rebuild must **not block the hot path**: if rebuild cannot complete in time, **S6 serves fail-closed** under S8 gate and records that posture in audit via DF (outer invariant).
* Rebuild does not “repair history.” It only restores **current posture truth**.

---

# What we’ve now pinned (so we don’t drift later)

### JI-09 pins

* All internal subnetworks emit **explicit health events/stats**; failures cannot be silent.
* S8 receives enough structured info to decide DL self-trust without relying on raw logs.

### JI-10 pins

* S8 can **force fail-closed** (BLIND/BROKEN) and that override has top priority for S4/S6.
* Recovery is evidence-based and monotone toward safety.

### JI-11 pins

* Because posture store is derived, rebuild triggers are valid and expected.
* Rebuild is coordinated (S8 triggers → S4 evaluates → S5 commits), idempotent, and non-blocking to the hot path.

---

Alright — we’ll illuminate **IP-01 → IP-04** as **internal production paths** that stitch together the joins we just pinned (**JI-01…JI-11**), while keeping **S1–S8 opaque**.

I’ll describe each path in terms of: **trigger → sequence (edges) → invariants → failure posture**.

---

## IP-01 — Periodic evaluation cycle (steady state)

### Trigger

* Runs on a cadence `dl.eval_interval` (env-profile knob), with small jitter to avoid synchronized spikes.
* Also re-runs opportunistically when **scope set changes** (new run/world becomes active) and when **policy_rev changes** (but that’s IP-04).

### Sequence (internal edges)

For each evaluation tick:

1. **S3 produces ScopeContext** (JI-03)

   * scope set (GLOBAL + any active scoped keys)
   * writer_role per scope (ACTIVE/STANDBY)

2. **S2 produces PolicyContext** (JI-02)

   * active `policy_rev`, hysteresis params, required signals list, staleness rules

3. **For each scope where writer_role=ACTIVE** (parallelizable per scope):

   * **S1 builds SignalSnapshot(scope)** (JI-01)
     includes required signals + explicit `OK/STALE/MISSING/ERROR`
   * **S5 provides PriorPostureState(scope)** (JI-04)
     minimal continuity + `posture_seq`
   * **S4 evaluates** using {snapshot + policy + prior + scope}
     (still opaque: it produces a DegradeDecision)
   * **S4 → S5 commit** (JI-05)
     atomic write; CAS on prior_seq; posture_seq increments only on **material change**
   * **S5 → S7 notify** (JI-08, optional)
     only if material change

4. **S8 receives telemetry** (JI-09) and can gate (JI-10) / rebuild-trigger (JI-11) if needed.

### Invariants (what must be true)

* **One active writer per scope** (S3’s responsibility; S5 enforces with CAS conflicts).
* **Snapshot-stable evaluation**: S4 never “re-queries the world”; it only uses the snapshot bundle.
* **Atomic posture record** per scope (mode/mask/provenance/policy_rev/decided_at + continuity).
* **Monotone posture_seq on material change only** (keeps control stream quiet and semantics clean).
* **Downshift immediate; upshift gated** (implemented in S4, but IP-01 is where it’s exercised reliably).

### Failure posture

* If signals are missing/stale/error → S1 marks them explicitly; S4 deterministically downshifts / blocks upshift (not “skip tick”).
* If policy unavailable/invalid and no last-known-good → S8 forces fail-closed (JI-10).
* If commit fails (store write failures/corruption) → S8 treats DL as BROKEN/BLIND and forces fail-closed (JI-10), while rebuild may be triggered (JI-11).

---

## IP-02 — Decision-time serving path (DF-facing)

### Trigger

* DF requests posture for a decision: `GetDegradeDecision(scope_key, decision_time_utc, …)`.

### Sequence (internal edges)

1. **S6 receives request** and first checks **S8 gate** (JI-10)

   * If forced_mode present (BLIND/BROKEN), return **FAIL_CLOSED** immediately with explicit provenance.

2. **S6 reads current posture from S5** (JI-06)

   * If `record_status=OK`, compute freshness using **request decision_time**:
     `age = decision_time_utc - decided_at_utc`
   * If `age <= max_decision_age` → return decision.

3. If posture is **missing/stale/corrupt**:

   * **Option (a) inline refresh** (only if enabled and deadline allows):
     **S6 → S4 EvaluateNow** (JI-07 singleflight) → **S4 → S5 commit** (JI-05) → **S6 rereads** (JI-06) → return.
   * **Option (b) serve safe fallback**:
     return `FAIL_CLOSED` DegradeDecision with provenance `STALE_OR_MISSING_POSTURE` (and S8 telemetry reflects this).

### Invariants

* S6 **never invents posture**; it returns either a valid stored decision or a deterministic safe fallback.
* Freshness uses **decision boundary time**, not hidden wall-clock.
* Inline evaluation is bounded by a **deadline**; otherwise DL could become the bottleneck of DF’s hot path.

### Failure posture

* If S5 read fails or inline evaluation times out → serve **FAIL_CLOSED** and emit telemetry (so “DL hurting” is visible).

---

## IP-03 — Signal refresh path (signals changed → posture recompute)

This is the “fast react” path. It may be implemented as event-driven, poll-driven, or both — but the **semantics** must match.

### Trigger

* S1 observes updated readings (or detects that a required signal crossed from OK→STALE/MISSING/ERROR, or vice versa).

### Sequence (internal edges)

Two equivalent production patterns (choose one; don’t mix ad hoc inside S4):

**Pattern 1 (coalesced into the periodic loop)**

* S1 updates its internal cache; the next IP-01 tick picks up the new snapshot(s).
* Good for stability and simpler scheduling.

**Pattern 2 (event-driven kick with throttling)**

1. **S1 builds a new SignalSnapshot(scope)** (JI-01)
2. S1 schedules an evaluation run for that scope (internal queue)
3. Evaluation follows the same core chain:
   **S5 prior** (JI-04) → **S4 eval** → **S5 commit** (JI-05) → optional **S7 publish** (JI-08)

### Invariants

* Signal refresh must be **coalesced**: multiple rapid signal updates should not cause posture thrash.
  (Singleflight/coalesce per scope is sufficient.)
* Signal refresh cannot bypass policy/hysteresis: S4 still applies quiet periods, one-rung upshift, etc.

### Failure posture

* If the signal backend is unreachable, the “refresh” is actually “signals stale” — S1 marks required signals as STALE/ERROR, which pushes posture toward safety on the next evaluation.

---

## IP-04 — Policy activation / policy refresh path (policy_rev changes)

This is the “governed change becomes operational posture” internal route.

### Trigger

* S2 detects the active `policy_rev` has changed (via pointer update, activation fact, or periodic refresh).

### Sequence (internal edges)

1. **S2 loads/validates the new policy rev** and emits **PolicyContext** atomically (JI-02).

   * If invalid/unloadable: **do not emit** it as active; keep last-known-good and raise CRITICAL telemetry.

2. **S4 evaluation fan-out** (high priority)

   * For each active scope (from S3, JI-03):
     **S1 snapshot** (JI-01) + **S5 prior** (JI-04) + **new PolicyContext** (JI-02) → evaluate → **commit** (JI-05)

3. **Commit rules** (important nuance)

* If mode/mask unchanged but policy_rev changed:
  **material change = true** *or* you treat it as a distinct “policy change change_kind”.
  **Designer call (v0): treat policy_rev change as material** so posture_seq advances and control visibility can reflect “rules changed” even if outcome stayed same.

4. Optional: **S7 publishes posture-change facts** (JI-08) for the scopes whose posture materially changed (including policy_rev changes, per the above).

### Invariants

* No half-policy: S4 always evaluates under a single PolicyContext.
* “Last-known-good policy” is first-class: policy update failure must not silently flip DL into undefined behavior.
* Decisions **cite policy_rev** so audit/replay can answer “what rules were in force?”.

### Failure posture

* If there is **no last-known-good policy** (fresh boot + policy load fails), S8 forces fail-closed (JI-10).
* If policy loads but commit fails (store broken), S8 forces fail-closed until store is healthy/rebuilt.

---

## What we’ve pinned by illuminating IP-01…IP-04

* DL stays correct whether it is **periodic-first** (IP-01 dominant) or **event-driven** (IP-03 kick), because both flow through the same JI chain and S4 hysteresis.
* Serving (IP-02) is safe under restart/staleness: **bounded inline refresh** or **fail-closed**, never “unknown”.
* Policy changes (IP-04) are operationally explicit: **atomic policy context**, **fan-out recompute**, and **policy_rev treated as a posture-visible change**.

---

Perfect — illuminating **IP-05 → IP-07** now. Same approach: **subnetworks remain opaque**, we’re pinning the **internal routes** and the **production invariants** so we don’t drift when we later dive deeper.

---

## IP-05 — Posture change publication path (optional)

### Purpose (what this path is *for*)

This path exists for **visibility + cache invalidation**, not correctness. DL correctness remains anchored on:

* **S5 atomic posture record** and
* **S6 serving semantics** (freshness + fail-closed).

If IP-05 is disabled or broken, DF still must get posture via S5/S6 and record what it used.

### Trigger

* A **material posture change** is committed by S5 (mode/mask/policy_rev/forced-failsafe change), i.e. **posture_seq increments**.

### Sequence (internal edges)

1. **S4 → S5 Commit** (JI-05)
2. S5 detects **material change** and emits **PostureChangedNotify** (JI-08)
3. **S7 publishes** `dl.posture_changed.v1` to `fp.bus.control.v1` (optional outer edge)
4. **S7 → S8 telemetry** (JI-09) about publish success/failure/backlog

### Hard invariants

* **Only S5 can trigger publishes** (because only S5 owns “material change + posture_seq”).
* **No publish on NOOP** refreshes (no posture_seq bump, no event).
* **Publish must be idempotent**: stable `event_id` derived from `(scope_key, posture_seq)` (or decision_id).
* **Publish must not block commit**: S5 commits even if bus is down.

### Reliability stance (production-real, not overspecified)

I’m pinning the “outbox mindset” without mandating implementation tech:

* S5 (or S7) maintains a **durable pending publish queue** so that a crash right after commit doesn’t lose the posture-change fact.
* S7 retries publishing with the same stable event_id until it succeeds or is superseded.

### Failure posture

* If publishing fails, DL remains correct; you lose:

  * dashboards/alerts timeliness
  * event-driven DF cache invalidation
* S8 must surface `CONTROL_PUBLISH_FAILED` / backlog warnings so ops sees the degradation.

---

## IP-06 — Startup / restart path (cold start & rolling restart)

This path is where most production drift happens, so we pin it carefully.

### Purpose

After a restart, DL must become safe **immediately** and become accurate **as soon as inputs allow**, without ever serving “silent NORMAL” due to missing data.

### Trigger

* DL process starts (or a new DL instance joins during HA/rolling deploy).

### Sequence (internal edges)

1. **S8 comes up first** (conceptually) with a conservative default health gate:

   * until proven otherwise, treat DL as **IMPAIRED/BLIND** for serving (so fail-closed is available).
     *(This is a safety stance, not an implementation ordering requirement.)*

2. **S2 loads active policy** (JI-02)

   * if policy pointer/load invalid → S8 remains BLIND and will force FAIL_CLOSED (IP-07 overlaps)

3. **S3 establishes scope context + writer role** (JI-03)

   * in HA, only ACTIVE writers will commit for a scope

4. **S1 warms signals** (build initial snapshots) (JI-01)

   * signals can be OK or stale/missing; but snapshot must be explicit either way

5. **S5 reads existing posture records** (JI-06 / JI-04)

   * read current posture (for serving) + prior state (for eval/hysteresis)
   * records may be missing (fresh deployment) — that’s allowed

6. **S4 evaluates and S5 commits** (JI-04 → JI-05)

   * for each ACTIVE scope, compute a posture using (policy + snapshot + prior state)
   * commit atomic record

7. **S6 begins serving** (JI-06 + JI-10)

   * once S8 gate is HEALTHY/IMPAIRED and posture is fresh enough, S6 serves it
   * otherwise S6 serves FAIL_CLOSED (with provenance “startup not ready / posture stale”)

8. Optional: **S7 publishes posture change** if commits caused material changes (IP-05)

### Hard invariants

* **No “startup gap = NORMAL”**: until policy is valid *and* posture is available/fresh, serving must be conservative.
* **Derived store doesn’t imply trust**: an old posture record doesn’t mean it’s still safe; S6 must enforce freshness using `decided_at_utc` and the request decision boundary time.
* **Policy mismatch is explicit**: if stored posture cites a policy_rev that differs from active, DL must converge quickly (IP-04) and treat that mismatch as posture-visible (posture_seq bump).

### Failure posture

* If policy fails to load: DL remains BLIND ⇒ serve FAIL_CLOSED (via IP-07).
* If signals are stale/missing: DL can still produce conservative posture (fail-safe downshift), but upshift is blocked until signals recover.
* If store is corrupt/unreadable: DL becomes BROKEN ⇒ serve FAIL_CLOSED and trigger rebuild (JI-11).

---

## IP-07 — DL self-health fail-safe path (internal safety)

This is the “DL can’t be trusted → system must still be safe” internal route.

### Purpose

Guarantee: **DL failure cannot silently widen capabilities**. DL failure must *only* push toward safety and be visible.

### Trigger conditions (what makes S8 gate)

S8 enters BLIND/BROKEN when any of these occur (global or per-scope):

* policy unavailable/invalid
* required signals missing/stale beyond max age
* store corruption or persistent write/read failures
* split-brain symptoms (lease conflict + CAS conflicts)
* severe time sanity failure (breaks staleness semantics)

### Sequence (internal edges)

1. **Modules emit HealthEvents/Stats → S8** (JI-09)

2. **S8 emits HealthGate → S4/S6** (JI-10)

   * sets `forced_mode=FAIL_CLOSED` (and implied conservative mask)

3. **S6 serving path** immediately returns forced posture (even if store says NORMAL)

4. Optional: **S4/S5 commit forced posture** (JI-05)

   * This is optional but useful: it makes the “fail-safe posture” visible in posture store and eligible for control-bus notification.

5. Optional: **S7 publishes posture-change fact** (IP-05)

   * event says “forced fail-safe entered” with reason codes

6. Optional: **S8 triggers rebuild** (JI-11) when appropriate (corrupt/missing posture, policy mismatch, etc.)

### Hard invariants

* **Gate has top priority**: forced posture overrides evaluation and serving.
* **Fail-safe is monotone**: can tighten immediately, loosens only after explicit recovery evidence.
* **Visibility is explicit**: even if you don’t publish control events, S8 must emit telemetry indicating “DL forced fail-safe” so operators can see it.

### Failure posture (in the failure posture path)

If DL is in a deep failure where it can’t write state and can’t publish control events:

* The minimum acceptable outcome is still: **S6 serves FAIL_CLOSED** (because that’s the only safety guarantee needed for downstream correctness).
* Everything else becomes “degraded observability,” which must be visible via whatever telemetry is still functioning.

---

## Pins we just locked for IP-05–IP-07

1. **Control events are optional and never correctness dependencies** (visibility/invalidation only).
2. **Startup is conservative by default**; no posture/policy/signal ⇒ fail-closed, not normal.
3. **Self-health gating overrides everything** and is monotone toward safety; recovery is evidence-based.
4. **If forced fail-safe happens, it should be representable** in S5 (and optionally on control bus) to avoid “invisible safety clamp.”

---

Absolutely — illuminating **IL-01 → IL-04** now. These are the **internal feedback loops** that make DL stable, safe, and production-real. We’ll keep subnetworks opaque, but we’ll pin the *loop mechanics* (what causes a loop to advance, and what prevents flapping or silent failure).

---

# IL-01 — Hysteresis loop (anti-flap core)

`S5(prior_state) → S4(decide) → S5(commit next_state) → S5 becomes next prior_state`

## Why this loop exists

Without IL-01, DL will **flap** between rungs as metrics jitter, causing DF to alternately enable/disable expensive capabilities—exactly the kind of drift and instability your platform is trying to prevent.

## The loop variables (what “state” actually is at this boundary)

IL-01’s entire memory is the **minimal continuity set** in `PriorPostureState`:

* `last_mode`
* `last_transition_at_utc`
* `quiet_period_until_utc`
* `posture_seq`
* (optional) last_mask_digest / policy_rev (for “material change” detection)

Everything else must come from current snapshot + policy.

## Loop update law (designer-locked)

This is the core hysteresis rule-set that IL-01 enforces:

1. **Downshift is immediate**
   If current snapshot makes a more degraded rung eligible, S4 selects the most degraded eligible rung *now*, regardless of quiet period.

2. **Upshift is gated**
   S4 may only upshift if:

* `now_or_decision_time >= quiet_period_until_utc`, and
* all **required** signals are `OK` (not stale/missing/error), and
* the target (less degraded) rung is eligible.

3. **Upshift is one rung at a time**
   Even if NORMAL would be eligible, you can only move from `DEGRADED_2 → DEGRADED_1`, not straight to NORMAL.

4. **Tie-break is deterministic**
   If multiple rungs are eligible simultaneously, select the **most degraded eligible** (safe, stable).

## What closes the loop (commit semantics)

S5’s commit rules (JI-05) make IL-01 stable:

* `posture_seq` increments **only on material changes**
* “Same posture, re-evaluated” is a **NOOP** (no seq bump, no control event)
* CAS guard prevents stale evaluators from overwriting newer posture

## Failure posture inside the loop

If prior state is missing/corrupt:

* S4 still decides from snapshot + policy
* S5 seeds continuity on first commit
* Serving remains conservative until a fresh posture exists

---

# IL-02 — Serving freshness loop

`S6(read posture) → stale? → (optional S6→S4 inline eval) → S5(commit) → S6 returns fresh`

## Why this loop exists

This loop prevents DF from operating under **stale posture** after:

* restarts
* store wipe
* evaluation stalls
* policy rev changes

It’s the “posture is always fresh enough or safely clamped” guarantee.

## Loop trigger (staleness detection law)

Staleness is computed using the **request decision boundary time**, not wall clock:

`age = decision_time_utc - current_posture.decided_at_utc`

If `age > policy.max_decision_age` → posture is stale.

This pins determinism in replay/tests and avoids hidden clock drift.

## Two loop modes (pinned)

### Mode A — Inline refresh enabled

1. S6 reads stale/missing posture
2. S6 triggers **EvaluateNow** (JI-07) with:

   * scope_key
   * decision_time_utc
   * deadline_utc
   * singleflight_key (prevents stampede)
3. S4 evaluates, S5 commits
4. S6 rereads and returns fresh posture

### Mode B — Inline refresh disabled (simpler)

1. S6 reads stale/missing posture
2. S6 returns **FAIL_CLOSED** posture immediately (explicit provenance)
3. Periodic evaluation (IP-01) eventually refreshes posture

## Loop stability rules

* **Singleflight per scope**: only one inline eval in-flight per scope_key
* **Deadline-bound**: never block DF beyond the allowed budget
* **No guessing**: missing/corrupt posture can never result in optimistic behavior

## Failure posture

* If inline eval times out/fails → serve FAIL_CLOSED
* Telemetry must explicitly show `SERVE_FALLBACK_FAILCLOSED` / `INLINE_EVAL_TIMEOUT` so ops sees degraded DL serving

---

# IL-03 — Signal staleness / blindness loop

`S1 sees stale/missing → marks unhealthy → S4 downshifts → S5 commits → S6 serves conservative`

## Why this loop exists

This loop ensures the platform never enters the dangerous state:

> “Observability died, so DL stopped changing, so DF kept acting as NORMAL.”

Instead: **blindness itself becomes an unhealthy signal**.

## The key loop variable: `quality`

S1’s explicit per-signal `quality ∈ {OK, STALE, MISSING, ERROR}` is what drives IL-03.

**No silent drops**: required signals must appear even if missing (as MISSING).

## Loop update laws (designer-locked)

1. **Required-signal staleness blocks upshift**
   If any required signal is STALE/MISSING/ERROR, S4 cannot upshift.

2. **Required-signal failure can cause downshift**
   Policy may specify that certain missing required signals immediately force a deeper rung (commonly FAIL_CLOSED or DEGRADED_2).

3. **If S1 cannot build a snapshot, it builds a “failed snapshot”**
   That snapshot is explicitly unhealthy and triggers safe posture.

## “Blindness escalation” (ties into S8)

If S1 repeatedly cannot read the signal backend or required signals remain stale beyond a hard limit:

* S8 may mark DL as **BLIND**
* JI-10 forces FAIL_CLOSED regardless of stored posture

This keeps “metrics pipeline down” from being treated as just “a bad day” forever.

## Failure posture

* The loop always moves toward safety when signals degrade.
* Recovery requires signals to become OK and remain OK long enough for quiet period to expire (ties back to IL-01).

---

# IL-04 — Policy churn stabilization loop

`S2 policy_rev changes → S4 recalculates → S5 commits → (optional S7 publishes) → S8 observes`

## Why this loop exists

Policy changes are **outcome-affecting** and must become:

* operationally applied **atomically**, and
* visible/auditable as “rules changed”.

This loop enforces “governed change becomes posture” rather than “someone edited a config and we hope.”

## Loop triggers

* `POLICY_REV_CHANGED` event emitted by S2
* or periodic policy pointer refresh detects active revision change

## Loop update laws (designer-locked)

1. **Atomic policy context**
   S4 evaluates under exactly one policy_rev at a time (old or new), never mixed.

2. **Convergence fan-out**
   On policy_rev change, S4 must recompute posture for relevant scopes promptly (priority over normal cadence).

3. **Policy_rev change counts as “material”**
   Even if mode/mask do not change, S5 treats a policy_rev change as a posture-visible change:

* posture_seq increments
* (optional) control event can be emitted with `change_kind=POLICY_REV_CHANGED`

This is crucial for audit + incident clarity.

4. **Invalid new policy never partially applies**
   If the new policy cannot be validated/loaded:

* S2 keeps last-known-good active
* S8 surfaces CRITICAL telemetry
* (optionally) DL can force conservative posture if policy confidence is compromised

## Failure posture

* If there is no last-known-good policy (fresh system + policy load fails): DL is BLIND → force FAIL_CLOSED.
* If policy loads but store commit fails: DL is BROKEN → force FAIL_CLOSED until healed/rebuilt.

---

## The important interaction between loops (so we don’t drift later)

These loops are not isolated:

* **IL-03 feeds IL-01**: stale signals block upshift and can force downshift.
* **IL-02 is the serving counterpart of IL-01**: even if evaluation is healthy, serving must enforce freshness or clamp.
* **IL-04 can override the “same posture” notion**: policy_rev change is a material transition even if rung stays the same.

That’s the internal stability story pinned.

---

Alright — illuminating **IL-05 → IL-07** now. These are the “production reality” internal loops: **HA ownership**, **optional control publication reliability**, and **self-healing**. We’ll keep S3/S5/S7/S8 opaque, but pin the loop mechanics so drift is impossible later.

---

# IL-05 — Scope ownership / single-writer loop (HA stability)

**Loop:** `S3 writer_role/lease → S5 commit acceptance (CAS) → feedback to S3/S8 → stable single writer per scope`

## Why this loop exists

If you ever run >1 DL instance (dev/prod HA, rolling deploys), you *will* get split-brain opportunities. Without IL-05 you’ll see:

* posture_seq oscillation,
* rapid mode flipping,
* or “last write wins” races that break determinism and invalidate audit interpretations.

IL-05 ensures: **for any scope_key, at most one ACTIVE writer can change posture at a time**.

## Loop participants (roles)

* **S3**: assigns `writer_role` per scope (ACTIVE/STANDBY) via leases.
* **S5**: enforces commit safety via CAS (`prior_seq`) and “accept writes only from current lease holder” (conceptually).
* **S8**: observes lease churn / conflicts and can force fail-closed if split-brain is suspected.

## Loop mechanics (pinned laws)

### 1) Lease is the authority signal (S3 → everyone)

For each scope_key, S3 outputs:

* `writer_role`
* `lease_id`
* `lease_expires_at_utc`

**Pin:** Only ACTIVE with a live lease is allowed to attempt JI-05 commits.

### 2) Commit is guarded (S5 enforces)

S5 only accepts a commit if:

* the `prior_seq` matches current (CAS), **and**
* the commit carries the current `lease_id` (or equivalently, S5 can validate the writer identity in a way that prevents stale writers).

If either fails → `CONFLICT/REJECTED`.

This gives the loop its “hard edge”: even if S3 momentarily misbehaves, S5 blocks harmful writes.

### 3) Conflict feedback drives stabilization

When S4/S5 sees repeated conflicts:

* S5 emits HealthEvents: `LEASE_CONFLICT` / `CAS_CONFLICT_RATE_HIGH`
* S8 consumes them and can:

  * mark the scope as unstable,
  * force fail-closed for that scope (JI-10),
  * and/or trigger a rebuild after lease stabilizes (JI-11).

### 4) Rolling deploy safety (practical pin)

During deployments you may temporarily have two instances thinking they’re ACTIVE. IL-05’s guardrails ensure:

* only one instance successfully commits,
* the other detects conflict and backs off (becomes STANDBY).

### 5) Ownership changes do not imply posture changes

When leadership changes hands:

* the new ACTIVE writer must **read** current posture (JI-04/JI-06), **then** continue evaluation.
* It must not “reset posture” just because it became leader.

## Failure posture

If lease churn persists (e.g., flapping leadership) or S5 sees inconsistent commits:

* S8 should force **FAIL_CLOSED** for affected scopes until stability returns.
  This matches the platform’s “fail toward safety” posture: better conservative than oscillating.

---

# IL-06 — Control publish retry loop (optional, visibility reliability)

**Loop:** `S5 posture change → S7 publish attempt → fail? retry with same event_id → succeed → S8 observes`

## Why this loop exists

If you enable control events, they’re useful only if they are:

* **not silently dropped**
* **idempotent**
* and **ordered per scope**.

IL-06 makes control events “eventually visible” even under broker blips, without making them correctness-critical.

## Loop mechanics (pinned laws)

### 1) Event identity is stable per transition

For a posture change, event_id is derived from:

* `(scope_key, posture_seq)` (preferred), or
* `degrade_decision_id` if you mint one.

**Pin:** retries must reuse the same event_id. No new ids on retry.

### 2) Outbox mindset (durability without overspec)

Publishing must be resilient to “crash after commit”:

* the fact that “posture_seq advanced” must create a durable “pending publish” item,
* S7 drains this queue and retries.

Implementation can be outbox table, durable queue, etc. The rule is: **don’t lose change facts silently**.

### 3) Retry/backoff is bounded and observable

* Retries use exponential backoff (implementation detail), but crucially:
* S7 emits telemetry to S8: backlog size, oldest pending age, publish error rate.

### 4) Ordering per scope is preserved

Partition key on control bus is derived from `scope_key`. This ensures per-scope ordering of posture-change facts.

### 5) Publish failures never block posture correctness

S5 commit is independent. If control bus is down:

* posture store still updates,
* DF still reads posture (S5→S6),
* only visibility/invalidation is delayed.

## Failure posture

If backlog grows too large or oldest pending age exceeds a threshold:

* S8 marks DL as **IMPAIRED** (visibility degraded),
* but does not force FAIL_CLOSED unless the system depends on control events for correctness (which we explicitly forbid).

---

# IL-07 — DL self-healing loop (detect → clamp safe → rebuild → recover)

**Loop:** `S8 detects faults → gate to safe posture (JI-10) → trigger rebuild (JI-11) → posture stabilizes → S8 clears gate`

## Why this loop exists

Production reality: stores corrupt, policies misactivate, signal backends hiccup, leases churn, deploys roll. DL must not:

* silently rot,
* stay stuck forever,
* or “recover” without evidence.

IL-07 ensures DL is **self-correcting** and **monotone-safe**.

## Loop mechanics (pinned laws)

### Phase 1 — Detect and classify

S8 consumes HealthEvents/Stats (JI-09) and classifies DL per scope (or globally):

* `HEALTHY`
* `IMPAIRED`
* `BLIND` (inputs not trustworthy: policy/signals)
* `BROKEN` (cannot serve/commit reliably: store corruption, split-brain)

### Phase 2 — Clamp toward safety immediately

If BLIND or BROKEN:

* S8 emits HealthGate forcing `FAIL_CLOSED` (JI-10).
* S6 serves forced posture regardless of stored NORMAL (top priority override).

### Phase 3 — Repair / rebuild actions (idempotent)

S8 triggers RebuildRequest (JI-11) when repair is plausible:

* `POSTURE_RECORD_CORRUPT` → rebuild posture record
* `POLICY_REV_CHANGED` → converge posture under new policy
* `MISSING_POSTURE_FOR_HOT_SCOPE` → seed posture
* `LEASE_STABILIZED_AFTER_CHURN` → rebuild to known-good

Rebuild is:

* bounded (doesn’t block serving; serving stays fail-closed until resolved),
* idempotent (singleflight per scope).

### Phase 4 — Evidence-based recovery

S8 only clears the forced gate when it sees:

* policy valid and loaded,
* required signals OK and within max age,
* store reads/writes succeeding (or successful recompute+commit),
* lease stable (no churn/conflicts).

Then S8 transitions:

* `BLIND/BROKEN → IMPAIRED → HEALTHY` (optionally through IMPAIRED).

### Phase 5 — Post-recovery stabilization

After clearing the gate:

* S4 still respects hysteresis (quiet periods), so DL doesn’t “upshift instantly” the moment it recovers.
* If recovery causes a material posture change, S5 commits and S7 may publish a posture-change fact (optional).

## Failure posture

If DL cannot self-heal (e.g., policy remains invalid, signals remain absent):

* it remains forced FAIL_CLOSED indefinitely (safe),
* and the system is explicitly observable as “DL forced failsafe active” via telemetry and (if enabled) control events.

---

## Pins we just locked for IL-05–IL-07

1. **Single-writer per scope is enforced twice**: by S3 leases and by S5 commit guards (CAS + lease identity).
2. **Control events are eventually-visible, idempotent facts** (stable event_id, outbox-like durability), but never correctness dependencies.
3. **Self-healing is monotone-safe**: detect → force fail-closed → rebuild → evidence-based recovery → hysteresis-stable operation.

---

Yep — there *are* “non-join” things that matter for DL that aren’t edges/paths/loops, but **they’re still part of the vertex boundary discipline**. Think: **internal laws, canonical objects, time/scope semantics, determinism rules, and operational guardrails**.

Below is the **DL non-join inventory** I’m declaring *in-bounds* (i.e., these must hold even before we deep-dive any subnetwork internals). I’ll also call out a few things that are **explicitly out-of-bounds** (so we don’t accidentally drag other components inside DL).

---

## DL non-join pins inside the vertex boundary

### NJ-01 — Canonical objects and “shape stability”

DL’s internal network must consistently speak a **small set of canonical objects** (even if field-level schemas come later):

* `SignalSnapshot` (what DL observed)
* `PolicyContext` (what rules were in force)
* `DegradeDecision` (what posture DL selected)
* `CurrentPostureRecord` (what DL is currently serving)
* `HealthGate / HealthEvents` (DL self-trust + fail-safe clamp)

**Pin:** These objects must be **self-contained and order-stable** (no dependence on iteration order, backend response order, etc.). This is critical because the platform is deterministic + replay-safe in an at-least-once world.

---

### NJ-02 — Time semantics never collapse (DL edition)

Your platform pins “time semantics never collapse” globally. DL must preserve that discipline internally too.

**DL’s required time concepts:**

* `decision_boundary_time_utc` = the time DF is deciding under (normally the event’s `ts_utc`, not “now”).
* `snapshot_end_utc` = what moment the SignalSnapshot represents.
* `observed_at_utc` = when S1 assembled the snapshot.
* `decided_at_utc` = when S4 decided the posture (domain time for DL posture).

**Pin:** DL must never use an implicit “now()” in a way that changes the posture outcome without being represented in these fields.

---

### NJ-03 — Scope semantics are explicit and canonical

DL must not “silently be global” or “silently be per-run”. The scope model is a *non-join truth* that prevents chaos later.

**Pin:**

* DL decisions are keyed by a **canonical `scope_key`** produced by the Scope/Partition plane (S3).
* Scope kinds in v0: `GLOBAL`, `MANIFEST`, `RUN` (extendable later).

**Corollary:** any DL-facing store key, cache key, event partition key, and audit reference uses the **same** `scope_key`.

---

### NJ-04 — Material change definition (what “posture changed” means)

We already used this in commits/publishing, but it’s a non-join rule worth pinning explicitly:

A posture is a **material change** if *any* of the following changed:

* `mode`
* `capabilities_mask` (structural or effective change)
* `policy_rev` (rules changed, even if outcome didn’t)
* forced fail-safe entered/exited (S8 clamp state)

**Pin:** only material changes bump `posture_seq` and are eligible for control publication. Everything else is a “refresh”.

---

### NJ-05 — Deterministic evaluation contract (tie-break + safety)

This is “the math” without doing any math yet:

* Same `(SignalSnapshot, PolicyContext, PriorState)` ⇒ same `DegradeDecision`.
* If multiple rungs are eligible, select the **most degraded eligible** rung.
* Downshift is immediate; upshift is gated by quiet period and moves one rung at a time.
* Missing/stale required signals are treated as unhealthy.

This is the deterministic spine that makes all the loops predictable.

---

### NJ-06 — Freshness rules are first-class (two separate TTLs)

DL must enforce two distinct freshness notions:

1. **Signal freshness** (`max_signal_age`)
   If a required signal’s sample is older than this ⇒ `STALE` (unhealthy).

2. **Decision freshness** (`max_decision_age`)
   If a stored posture’s `decided_at_utc` is too old relative to the DF request boundary ⇒ posture is **stale** and cannot be trusted.

**Pin:** staleness never becomes “unknown”; it becomes explicit and drives the system toward safety.

---

### NJ-07 — “Fail-safe clamp” precedence is absolute

S8’s HealthGate has absolute precedence:

* If S8 says **BLIND/BROKEN**, DL must serve **FAIL_CLOSED** regardless of whatever is currently stored.
* Recovery is evidence-based and monotone (can tighten instantly; loosen only when policy + required signals + store health are proven good).

This is the internal mechanism that ensures “DL failure cannot silently widen capabilities.”

---

### NJ-08 — Idempotency and canonicalization rules

Even before we choose storage tech, we pin that DL must be safe under retries:

* `commit_id` (for S4→S5 commits) is stable for the same evaluated decision.
* `event_id` (for posture-change control facts) is stable per transition: derived from `(scope_key, posture_seq)` or equivalent.
* Any digests/hashes DL emits must be computed over **canonical ordering** (e.g., sorted readings by stable keys).

This aligns with the platform’s “determinism + replay safety in an at-least-once world.”

---

### NJ-09 — Posture state store is derived, minimal, and atomic

DL’s posture store is allowed and expected, but it must stay “derived” and not morph into a second system-of-record.

**Pin:**

* Store only **current posture + minimal continuity** (hysteresis memory, posture_seq, timestamps, policy_rev).
* Record updates are atomic.
* History is not primarily stored here; history comes from audit / control facts (if enabled), consistent with platform truth ownership.

---

### NJ-10 — Policy-plane “last-known-good” is mandatory

Because thresholds/corridors are policy config and governed, DL must treat policy loading as a first-class safety surface.

**Pin:**

* DL never partially applies a policy revision.
* If the active revision is invalid/unloadable, DL continues on **last-known-good** and emits critical telemetry.
* If there is **no** last-known-good (cold start + policy unavailable), DL becomes BLIND and clamps FAIL_CLOSED.

---

### NJ-11 — Environment ladder discipline (DL-specific)

Same semantics everywhere; only profiles differ.

**Pin for DL:**

* Local/dev/prod use the same DL code and the same meaning of mode/mask.
* Differences are expressed via **policy_rev and profile knobs** (eval interval, TTLs, retention, observability depth), not conditional behavior.

---

### NJ-12 — Observability obligations (DL must be diagnosable)

This is not a join, but it’s required for production:

Minimum DL-exposed metrics:

* time-in-mode per scope
* posture change rate / flapping rate
* forced fail-safe activations (by reason code)
* percentage of evaluations blocked by stale/missing required signals
* posture serving staleness rate / fallback fail-closed rate
* control publish backlog age (if enabled)

This ensures that when loops fire (OFP shedding, EB lag, etc.) you can prove why.

---

## Things explicitly *not* inside DL’s boundary (to avoid accidental “vertex creep”)

### OUT-01 — DL does not interpret business payloads

DL is signal-driven. It does not inspect transaction payloads, compute features, or derive entity truth. (Those live in OFP/IEG/DF.)

### OUT-02 — DL does not own governance lifecycle

DL **consumes** governed policy revisions; it does not implement approvals or promotions itself (Run/Operate/Governance does).

### OUT-03 — DL does not become the hot-path bottleneck

Serving must be bounded (fresh store read or fail-safe); inline evaluation is an escape hatch with deadlines, not an open-ended compute path.

---

## The only “non-join” open decision I’d surface now

Whether you want an **emergency manual override** (force a rung) is not a join we *must* add, but it’s a production reality question.

**Designer stance (v0):** if you want override, it must be implemented as a **governed policy activation** (a special override policy_rev / overlay), not an ad hoc runtime knob—so it stays auditable and environment-ladder-consistent.

---

## USER: PAUSE FOR REFLECTION

Yep. Here’s the **consolidated “design freeze frame”** of everything we’ve established so far — the **platform-facing DL vertex**, its **outer network**, and the **first-layer internal network** (subnetworks still opaque), plus the **internal joins/paths/loops** we’ve illuminated and the **non-join laws** that hold the whole thing together.

I’m writing this as a **drift-prevention anchor**: if we later “enter” DL and something contradicts this, we treat that as drift unless we explicitly re-pin a decision.

---

# 1) DL’s role and authority in the platform network

## DL’s mission (pinned)

DL exists to select **“what level of service is safe right now”** and make it **explicit, deterministic, and auditable** as a single output:

* **DegradeDecision** = `mode + capabilities_mask + provenance + decided_at_utc (+ policy_rev)`
  DL is **not advice**; it is an explicit constraint surface.

## Enforcement point (pinned)

**DF is the mandatory enforcement point**:

* DF treats `capabilities_mask` as **hard constraints** (“disabled = doesn’t exist”).
* DF **records the exact posture used** into provenance so it becomes part of audit (DLA).

## “No stealth coupling” (pinned)

No other component is allowed to infer degrade from metrics. Only DL decides degrade posture. Everyone else can *observe* posture, not derive it.

---

# 2) DL outer adjacency map (direct joins)

## Inbound

A4) **Obs/Gov signals → DL** (windowed health/lag/error signals; stale/missing matters)
A3) **Policy/profile store → DL** (active threshold profile revision; governed)
B14) **Governed activation** exists as an indirect dependency (policy rev changes are auditable facts)

## Outbound

A1/J9) **DL → DF** DegradeDecision (fresh-enough or DF fails safe)
A5) **DL → dl.current_posture** (derived/rebuildable store; atomic record per scope)
A6) **DL → fp.bus.control.v1** (optional posture-change facts; envelope-valid; visibility/invalidation)
A7) **DL → optional consumers** (read-only posture for visibility/caching/internal tuning only)

---

# 3) DL outer production paths (multi-hop)

## B8 Hot decision path (canonical)

`EB → DF → (DL posture) → Registry(bundle) → OFP/IEG (if allowed) → DF → AL → DLA`

Pinned ordering inside DF (drift killer):

1. get DL posture **before** expensive/optional work
2. bundle resolution is **compat-aware including degrade constraints**
3. OFP uses **event_time boundary**, not hidden “now”
4. IEG only if allowed; record graph_version if used
5. action posture obeys DL constraints
6. DLA records degrade posture used

## B9 Feature acquisition under constraints

`DF (mask obeyed) → OFP → DF records snapshot provenance`

## B10 Identity context under constraints

`DF (mask obeyed) → IEG (optional) → DF records graph_version`

## B11 Bundle resolution under constraints

`DF (mask obeyed) → Registry → DF records ActiveBundleRef; fail-closed if incompatible`

## B12 Control-plane visibility

`DL posture changes → control bus → dashboards/alerts + optional cache invalidation`

## B13 Audit reconstruction

`DLA → investigations/offline parity tooling`
Must be able to reconstruct “what was allowed then” (degrade posture + policy_rev + other context).

## B14 Governed policy-change propagation

`propose → approve → activate policy_rev → DL loads → decisions cite rev → DLA records`

---

# 4) DL outer production feedback loops (C15–C20)

These loops are why hysteresis + deterministic tie-breaks are not optional:

* C15 **OFP load-shedding**: OFP unhealthy → DL restricts feature groups → OFP recovers → DL upshift (slow)
* C16 **IEG shedding**: IEG unhealthy → DL disables IEG → recovery → upshift
* C17 **EB lag/backpressure**: lag rises → DL reduces per-event compute → catch up → upshift
* C18 **Model/runtime**: model/DF slow → DL disables heavy stages → recovery → upshift
* C19 **Action-risk**: action failures/risk rise → DL conservative action_posture → fewer risky actions → stabilize
* C20 **Governance tuning**: posture history/outcomes → new thresholds (policy_rev) → DL behavior changes under governed activation

---

# 5) Environment ladder implications (what must *not* drift by env)

## Must be identical across local/dev/prod

* Same graph, same join semantics, same rails: **mask is hard constraint**, **audit records posture**, **fail-toward-safety**, **deterministic behavior**, **no stealth coupling**.
* No “if prod then…” logic forks.

## Allowed differences

Only via **profiles** and operational envelope:

* `dl.policy_rev_active` (different thresholds per env, same meaning)
* eval cadence, TTLs (`max_signal_age`, `max_decision_age`)
* retention/observability depth
* whether control bus emission is enabled (optional)

## Directional env posture

* Local: still run a prod-shaped substrate; use policy revs or fault injection to exercise loops
* Dev: must catch prod-like breakage (missing signals/policy, invalid rev, store issues)
* Prod: strict governance + auditable activations/rollbacks

---

# 6) DL first-layer internal subnetworks (opaque modules)

We decomposed DL into these internal subnetworks (still opaque inside each):

* **S1 Signal Plane** (build stable SignalSnapshot; explicit staleness)
* **S2 Policy Plane** (load/validate active policy_rev; atomic; last-known-good)
* **S3 Scope & Partition Plane** (canonical scope_key; one-writer-per-scope semantics)
* **S4 Evaluation & Hysteresis Plane** (the only place mode is decided)
* **S5 Posture State Plane** (atomic current posture + minimal continuity; derived/rebuildable)
* **S6 Serving Plane** (DF join surface; freshness gate; fail-safe serving)
* **S7 Control Emission Plane** (optional; publish posture-change facts idempotently)
* **S8 Self-Health & Telemetry Plane** (decides DL self-trust; clamps fail-safe; triggers rebuild)

---

# 7) Internal joins we illuminated (JI-01–JI-11)

## JI-01 S1→S4 SignalSnapshot

Stable, timestamped, canonically ordered readings with explicit quality: `{OK, STALE, MISSING, ERROR}`. No silent drops.

## JI-02 S2→S4 PolicyContext

Atomic `policy_rev + digest + thresholds/corridors + required_signals + hysteresis params + TTLs + mode→mask table`. No partial apply; last-known-good is first-class.

## JI-03 S3→(S1,S4,S5,S6) ScopeContext

Canonical `scope_key` + scope_kind + writer_role + (lease). No other module invents scope encoding.

## JI-04 S5→S4 PriorPostureState

Minimal continuity only: last_mode, quiet_period_until, posture_seq, timestamps, status present/missing/corrupt. Store is memory, not truth.

## JI-05 S4→S5 DecisionCommit

Commit request with decision + continuity + idempotent commit_id. S5 owns atomicity, CAS, monotonic posture_seq on **material change** only.

## JI-06 S5→S6 CurrentPostureRead

Serving receives current posture record + metadata and enforces freshness.

## JI-07 S6→S4 InlineEvaluate (optional)

Escape hatch when posture missing/stale; bounded by deadline + singleflight; failure → serve FAIL_CLOSED.

## JI-08 S5→S7 PostureChangedNotify (optional)

Only on material change (seq bump); S7 publishes envelope-valid, idempotent events.

## JI-09 (All→S8) TelemetryFeed

Structured HealthEvents + HealthStats; no silent failure allowed.

## JI-10 S8→(S4,S6) SafetyGate

S8 can force FAIL_CLOSED (BLIND/BROKEN) with absolute precedence; recovery is evidence-based.

## JI-11 S8→(S4/S5) RebuildTrigger (optional)

Idempotent rebuild workflow (derived store): startup seeding, corruption recovery, policy mismatch convergence, scope onboarding.

---

# 8) Internal paths we illuminated (IP-01–IP-07)

* **IP-01** periodic evaluation cycle (scopes + policy + snapshot + prior → decide → commit → optional publish)
* **IP-02** decision-time serving (read posture → freshness gate → optional inline eval → else FAIL_CLOSED)
* **IP-03** signal refresh (coalesced kicks or periodic pickup; never bypass S4 hysteresis)
* **IP-04** policy activation refresh (atomic new policy → converge scopes; policy_rev change treated as material)
* **IP-05** posture-change publication path (optional; outbox mindset; never blocks commit)
* **IP-06** startup/restart path (conservative by default; no silent NORMAL)
* **IP-07** self-health fail-safe path (detect → clamp safe → rebuild → recover)

---

# 9) Internal loops we illuminated (IL-01–IL-07)

* **IL-01** hysteresis anti-flap core (downshift immediate, upshift gated + one rung)
* **IL-02** serving freshness loop (stale posture → inline refresh or FAIL_CLOSED)
* **IL-03** signal staleness/blindness loop (metrics failure drives conservative posture)
* **IL-04** policy churn stabilization (atomic policy switch; policy_rev change visible)
* **IL-05** single-writer per scope (leases + CAS guard; split-brain → clamp safe)
* **IL-06** control publish retry loop (optional; idempotent retries; visibility only)
* **IL-07** self-healing loop (detect → clamp → rebuild → evidence-based recovery)

---

# 10) Non-join laws we pinned (the “glue”)

Key non-join constraints that must remain true:

* Canonical object shapes (Snapshot/PolicyContext/Decision/PostureRecord/HealthGate)
* Explicit time semantics (decision boundary time, snapshot_end, observed_at, decided_at)
* Explicit scope semantics (scope_key everywhere; global sentinel handled centrally)
* Deterministic evaluation and tie-break (“most degraded eligible”)
* Dual freshness: signal TTL vs decision TTL
* Material change definition (mode/mask/policy_rev/forced clamp)
* S8 gate precedence is absolute; fail-safe is monotone
* Idempotency rules (commit_id, event_id, canonical ordering for digests)
* Posture store is derived/minimal/atomic; history is not stored there
* Policy last-known-good is mandatory; invalid policy cannot partially apply
* Environment ladder: differences expressed via profiles, not code semantics
* DL must be diagnosable (metrics for time-in-mode, forced clamp, staleness, fallback rates)

---

# 11) The “drift tripwires” to carry forward

If any future internal design proposes these, it’s drift unless we explicitly re-pin:

1. **Anything besides DL deciding degrade posture**
2. DF treating mask as advice (not hard constraint)
3. Any path where missing/stale posture results in optimistic operation
4. Any hidden time (“now()”) changing posture without being represented
5. Any non-canonical scope key invention or multiple writers per scope
6. Policy rev applying partially or without being cited in decisions/audit
7. Control events becoming correctness dependencies

---

Yep — **this is the right moment** to pin the *deployment + environment-ladder posture* for DL **before** we open any subnetwork internals, because otherwise Codex will be forced to invent runtime shape and you’ll get drift.

Below are the **designer-authoritative deployment pins** for DL (still treating S1–S8 as opaque internal nodes).

---

## 1) DL deployment-unit shape

### DL-PIN-DU-01 — DL is an always-on evaluator unit

In production shape, DL runs as an **always-on (or periodic) service/worker**, not a job. It continuously computes posture that constrains DF.

### DL-PIN-DU-02 — Single “dl-service” deployment unit in v0 (collapse-friendly)

For v0, Codex should implement DL as **one deployable unit** (“dl-service”) that *contains* S1–S8 as internal modules (threads/tasks).
Local/dev can “collapse” further (same process as other components), but the **unit roles** must remain distinct (signal ingest, policy load, evaluate, posture-store, serving, control publish, self-health).

### DL-PIN-DU-03 — Optional publisher split is allowed, not required

If you want stronger delivery guarantees for posture-change facts, DL may split into:

* `dl-core` (S1–S6, S8)
* `dl-publisher` (S7 outbox drain)
  …but this is **optional** and must not change correctness (control facts remain visibility-only).

---

## 2) DL runtime dependencies and how they must behave

### DL depends on four substrates (all envs)

1. **Observability signals intake** (OTel/metrics backend): S1 must be able to read/assemble windowed snapshots.
2. **Policy artifact store + active pointer**: S2 must load a versioned profile, validate it, and provide last-known-good.
3. **Posture state store**: S5 writes/reads `dl.current_posture` (derived + rebuildable).
4. **Control bus** (optional): S7 may emit posture-change facts to `fp.bus.control.v1`.

### DL-PIN-DEP-01 — Posture store is derived/rebuildable, minimal, atomic

`dl.current_posture` is *not* primary truth. It holds:

* current DegradeDecision + minimal hysteresis continuity + posture_seq
  and must be **atomic** per scope record.

### DL-PIN-DEP-02 — DL must be safe when dependencies fail

DL is not allowed to “quietly keep NORMAL” when:

* policy can’t be loaded/validated,
* required signals are stale/missing,
* posture store is corrupt/unreadable,
* split-brain is suspected.

Instead, S8 must clamp serving/evaluation toward **FAIL_CLOSED**.

---

## 3) Environment ladder pins for DL

### DL-PIN-ENV-01 — Same semantics everywhere (no code forks)

Local/dev/prod must share the **same meaning** of:

* modes, masks, fail-safe clamp, staleness semantics, scope_key semantics
  Differences are profile knobs only.

### DL-PIN-ENV-02 — Policy config vs wiring config separation is mandatory

* **Policy config (outcome-affecting):** thresholds/corridors, required signals list, hysteresis params, mode→mask mapping
  → must be **versioned + auditable** and DL decisions must cite `policy_rev`.
* **Wiring config (non-semantic):** endpoints, ports, DB URLs, timeouts, replicas
  → can vary by env without claiming semantics changed.

### DL-PIN-ENV-03 — Promotion is “profile switch + policy rev activation”

Promoting DL behavior from local→dev→prod is:

* same binaries/code,
* different env profile (wiring + envelope),
* and a governed activation of a stronger **policy_rev**.

---

## 4) The environment profile knobs Codex must implement

Think of these as the **only knobs** that differ across envs; everything else stays semantically identical.

### A) Policy knobs (versioned artifacts)

* `dl.policy_rev_active` (the active threshold profile revision)
* `dl.required_signals[]` (declared by policy)
* `dl.mode_entry/exit corridors` (per mode)
* `dl.mode_to_capabilities_mask` mapping
* `dl.hysteresis.quiet_period` (per rung or global)
* `dl.max_signal_age` (staleness TTL)
* `dl.max_decision_age` (serving freshness TTL)
* `dl.default_on_error = FAIL_CLOSED` (pinned)

### B) Runtime envelope knobs (allowed operational variation)

* `dl.eval_interval` (cadence)
* `dl.inline_eval_enabled` (escape hatch on/off)
* `dl.inline_eval_deadline_ms` (bounded serving refresh)
* `dl.scope_kinds_enabled` (e.g., GLOBAL + RUN; keep the same semantics everywhere, just control which scopes you actually operate on)
* `dl.emit_control_events` (on/off)

### C) Wiring knobs (endpoints/resources)

* metrics backend endpoint(s), auth
* posture store DSN/schema/table
* control bus brokers/topic name (`fp.bus.control.v1`)
* retry/backoff/timeouts
* CPU/memory/replicas

---

## 5) HA/scaling posture (so Codex doesn’t invent drift)

### DL-PIN-HA-01 — One active writer per scope

If multiple DL instances exist, the system must guarantee:

* S3 assigns ACTIVE/STANDBY via leases (or equivalent), and
* S5 enforces **CAS + lease identity** so stale writers cannot commit.

### DL-PIN-HA-02 — Scale unit is “scope”

DL scales by:

* more scopes evaluated in parallel (or
* more partitions of scope keys)
  —not by multiple writers for the same scope.

### DL-PIN-HA-03 — Serving must tolerate restarts

S6 must always be able to:

* read fresh posture from S5, or
* inline-refresh within deadline (optional), or
* serve FAIL_CLOSED (never block hot path indefinitely).

---

## 6) Readiness, liveness, and “what does healthy mean?”

### DL-PIN-OPS-01 — Readiness must be meaningful

DL should not advertise “ready” unless it can safely serve posture. At minimum:

* a valid policy_rev is loaded (or last-known-good exists)
* posture store is readable/writable OR serving is clamped fail-safe explicitly
* signal plane is functioning OR DL is explicitly clamped (BLIND → FAIL_CLOSED)

### DL-PIN-OPS-02 — DL must expose self-health as first-class signals

Codex must expose metrics/events for:

* forced FAIL_CLOSED clamp active (with reason codes)
* serve fallback rate (stale/missing posture)
* signal staleness rate (required signals)
* policy load/validation failures
* posture store read/write failures
* lease churn / CAS conflict rate
* time-in-mode and flapping rate

This is crucial because DL is a control surface: operators must *see* what it’s doing.

---

## 7) Local/dev/prod “directional defaults” (so your ladder is practical)

### Local

* Use either **fault injection** or a “quick-trigger policy_rev” to exercise all loops without load.
* Keep `emit_control_events` optional, but keep observability real (don’t stub signals).

### Dev

* Control events ON (helps debugging caching/invalidation and visibility).
* Policy_rev should be “prod-shaped”: it must catch missing signals, invalid policy revs, store issues.

### Prod

* Strict governance for policy activations/rollbacks.
* Control events ON.
* Strong alerts on forced fail-safe and prolonged degraded operation.

---

## 8) Codex guardrails (implementation must not violate these)

* Do **not** implement environment-specific semantic forks (“if prod then…”). Use policy_rev + profile knobs only.
* Treat `dl.current_posture` as **derived** and **rebuildable**; never make it primary truth.
* Serving must be **bounded**; never block DF indefinitely.
* Any time-based decision must use **explicit timestamps** (decision boundary time, decided_at_utc, observed_at_utc); avoid hidden wall clock dependence.
* If DL can’t evaluate safely, it must clamp to **FAIL_CLOSED** and make that visible.

---

Yes — that assumption is the *right* one: **illumination should not change the network**, it should only reveal what’s inside each box that makes the already-pinned joins/paths/loops possible. The only time we’d “change the network” is if we discover a hidden constraint that *forces* a new edge/authority boundary; in that case we’ll treat it as a **drift/red-flag** and handle it explicitly (pin a decision or reject it), rather than letting it silently reshape the design.

## DL internal nodes (opaque subnetworks)

* **S1 — Signal Plane**
* **S2 — Policy Plane**
* **S3 — Scope & Partition Plane**
* **S4 — Evaluation & Hysteresis Plane**
* **S5 — Posture State Plane**
* **S6 — Serving Plane** (DF join surface)
* **S7 — Control Emission Plane** (optional)
* **S8 — Self-Health & Telemetry Plane**

## Order I want us to illuminate (drift-minimizing)

1. **S3 Scope & Partition** — locks canonical `scope_key`, scope kinds, one-writer semantics (everything else depends on this being stable).
2. **S2 Policy Plane** — locks policy_rev handling, last-known-good, atomic switch, and the “mode→mask” mapping surface.
3. **S1 Signal Plane** — locks signal catalogue shape, snapshot semantics, staleness/missing rules.
4. **S5 Posture State** — locks the atomic record shape, CAS/seq behavior, derived/rebuildable posture store.
5. **S4 Eval & Hysteresis** — now we can safely define eligibility logic, tie-breaks, hysteresis mechanics, provenance composition.
6. **S6 Serving** — freshness rules, request boundary time semantics, inline-eval escape hatch vs fail-closed behavior.
7. **S8 Self-Health & Telemetry** — map concrete failure modes from S1/S2/S5/S6 into BLIND/BROKEN gating + rebuild triggers.
8. **S7 Control Emission (optional)** — outbox/retry/idempotent control facts; visibility only (never correctness).

---

Absolutely — we’ll **open S3 (Scope & Partition Plane)** and expose the machinery inside it, **without changing the already-pinned DL network**. This is purely: “what’s inside S3 that makes the existing joins/paths/loops possible.”

Below is **designer-authoritative** for S3.

---

# S3 Scope & Partition Plane

## 1) What S3 is responsible for

S3 is the **sole internal authority** for:

1. **Scope semantics**

   * what “scope” means in DL (GLOBAL vs MANIFEST vs RUN)
   * how scopes relate (hierarchy)
   * how scopes are named and keyed (canonical `scope_key`)

2. **Partitioning / ownership semantics (HA safety)**

   * ensuring “**one active writer per scope**”
   * producing `writer_role` + `lease` signals consumed by S1/S4/S5/S6
   * stabilizing ownership during membership churn (rolling deploys)

3. **Scope-set management**

   * which scopes exist “right now” that DL should evaluate periodically
   * how new scopes are discovered and how old scopes expire

S3 **does not** load signals, load policy, decide posture, or store posture.

---

## 2) S3 internal subnetworks (inside S3)

We’ll treat these as S3’s own internal opaque nodes (one more layer down):

* **S3-A Scope Model & Hierarchy** (defines scope kinds + parent chain)
* **S3-B Scope Key Canonicalizer** (creates canonical `scope_key`)
* **S3-C Scope Registry** (active scope set + TTL/aging)
* **S3-D Ownership / Lease Manager** (ACTIVE/STANDBY per scope; lease acquire/renew/release)
* **S3-E Membership & Shard Mapper** (tracks DL instances; maps scopes → owners; optional)

Mini internal sketch:

```
           +------------------+
           | S3-E Membership  |
           +--------+---------+
                    |
   ScopeRequests     v            Policy/Signals don't touch S3
  (from S6/S8) -> [S3-C Registry] ----+
                    |                 |
                    v                 v
         [S3-A Scope Model]     [S3-B Canonicalizer]
                    |                 |
                    +--------+--------+
                             v
                    [S3-D Lease/Owner]
                             |
                             v
                    ScopeContext output
            (scope_key + kind + parent + writer_role + lease)
```

---

## 3) Canonical scope model (what “scope” means)

### Scope kinds (v0)

S3 supports exactly these three kinds in v0:

1. **GLOBAL**

   * posture applies platform-wide for DL’s safety clamp
   * used when dependencies are broadly unhealthy (metrics backend down, policy invalid, store corrupt, etc.)

2. **MANIFEST**

   * posture applies to a “world” keyed by `manifest_fingerprint`

3. **RUN**

   * posture applies to a specific run (or decision stream) within a manifest
   * keyed by `(manifest_fingerprint, run_id)`

> Pin: We do **not** introduce “seed scope” or “scenario scope” in v0 unless forced later. Those remain *data pins* carried for audit/provenance, but **not scope keys**.

### Scope hierarchy (parent chain)

Every scope has a **parent scope**:

* `RUN → MANIFEST → GLOBAL`

S3 must surface this as part of ScopeContext so serving can do safe fallback logic *without inventing new scope semantics later*.

---

## 4) Canonical scope_key (stable naming law)

### ScopeDescriptor (input concept)

S3 takes a descriptor that is either explicit or derived:

* `scope_kind` (GLOBAL/MANIFEST/RUN)
* `pins`:

  * for MANIFEST: `{manifest_fingerprint}`
  * for RUN: `{manifest_fingerprint, run_id}`
  * for GLOBAL: `{}`

### Canonicalization rules (hard)

* Key format must be stable across:

  * processes
  * environments (local/dev/prod)
  * time
* No module besides S3 is allowed to “re-encode” a scope.

### v0 scope_key format (designer-pinned)

Use a simple stable token string:

* **GLOBAL**
  `scope=GLOBAL`

* **MANIFEST**
  `scope=MANIFEST|manifest_fingerprint=<mf>`

* **RUN**
  `scope=RUN|manifest_fingerprint=<mf>|run_id=<rid>`

Where:

* tokens are ordered exactly as shown
* separators are literal `|` and `=`
* values are normalized:

  * `manifest_fingerprint` = lowercase hex
  * `run_id` = lowercase canonical string (uuid or whatever you already use)

### Parent keys

Derived deterministically:

* parent(MANIFEST) = GLOBAL
* parent(RUN) = its MANIFEST

---

## 5) ScopeContext (what S3 outputs to the rest of DL)

S3 emits:

`ScopeContext{`

* `scope_kind`
* `scope_key`
* `parent_scope_key` (or full chain)
* `pins` (normalized)
* `writer_role` ∈ `{ACTIVE, STANDBY, READONLY}`
* `lease` (present iff ACTIVE): `{lease_id, expires_at_utc}`
* `scope_source` (why this scope exists: serving demand vs configured vs rebuild)
* `scope_ttl_until_utc` (registry expiry)
  `}`

**Pin:** Every internal join that needs scope uses this object, not ad hoc fields.

---

## 6) Scope discovery and scope-set management (S3-C Registry)

### Why S3 needs a registry

DL must keep posture current for scopes that matter. In production, scopes appear dynamically (new runs/worlds, new tenants, etc.). We keep this simple and deterministic.

### How scopes enter the registry (allowed inputs)

S3 accepts scope registrations from internal sources only:

1. **Serving demand** (from S6)

   * When DF asks for posture for a scope, S6 registers that scope with S3.

2. **Rebuild demand** (from S8)

   * When S8 needs a posture seeded/rebuilt, it registers/refreshes that scope.

3. **Optional static config**

   * always include GLOBAL
   * optionally include a limited set of MANIFEST scopes (if you have known “hot” worlds)

> Pin: DL does **not** depend on SR/IG/EB to discover scopes directly. It can be purely demand-driven.

### Registry behavior (hard)

* **GLOBAL is always present**
* Registered scopes have a TTL (e.g., “active for N minutes since last request”)
* Registry periodically prunes expired scopes
* Registry emits “scope set changed” to the rest of S3 so ownership can adjust

This prevents runaway growth of evaluated scopes.

---

## 7) Ownership / lease semantics (S3-D)

This is where S3 enforces “one active writer per scope” in HA.

### Writer roles

* **ACTIVE**: allowed to evaluate and commit posture for that scope
* **STANDBY**: may read/evaluate for warm cache but **must not commit**
* **READONLY**: only used in single-instance/no-lease mode or special tooling

### Leases (hard semantics, tech-agnostic)

For each `(scope_key)` there is at most one valid lease at a time:

* `lease_id` (unique token)
* `owner_instance_id`
* `expires_at_utc`

ACTIVE writer must renew before expiry; if it can’t renew, it must transition to STANDBY.

### How S3 prevents split-brain (double guard)

1. **Lease-based role** (S3 decides ACTIVE/STANDBY)
2. **Commit guard** in S5 (already pinned)

   * commits include lease identity / CAS; stale writers are rejected

S3 and S5 together enforce safety even during deploy churn.

### Membership changes (S3-E)

S3 must maintain a live set of DL instances (membership), so it can:

* reassign ownership if an instance disappears
* avoid two actives on the same scope after a rolling deploy

How membership is tracked is implementation, but the semantics are:

* join/leave events exist
* stable instance identifiers exist
* assignment converges

---

## 8) Partitioning strategy (how scopes are distributed)

S3 supports two patterns; we pick one as the v0 intent:

### v0 intent: **Shard-by-scope_key**

* S3 maps each `scope_key` to an owner using a stable mapping (consistent hash / rendezvous / etc.)
* owner attempts to hold leases for the scopes mapped to it
* mapping changes only on membership change

This keeps per-scope coordination bounded and predictable.

> Pin: Regardless of mapping algorithm, correctness depends only on **lease + commit guard**, not on hash math.

---

## 9) How S3 connects to the already-pinned DL network (no drift)

S3’s outputs drive the internal joins we already established:

* **S3 → S1**: “build SignalSnapshot for these scope_keys”
* **S3 → S4**: “you are ACTIVE/STANDBY for this scope; evaluate accordingly”
* **S3 → S5**: “accept commits only from ACTIVE lease holder”
* **S3 → S6**: “this is the canonical scope_key; here is the parent chain”
* **S3 → S8**: emits health telemetry about lease churn/conflicts and scope-set changes

No new external edges are introduced.

---

## 10) Environment ladder posture for S3 (deployment-shaped but non-forking)

### Local (single instance)

* S3 runs in **single-instance mode**:

  * always ACTIVE for all scopes
  * leases are “synthetic” (still represented in ScopeContext, but no external coordination needed)
* Canonical scope_key semantics **must remain identical**.

### Dev/Prod (HA-capable)

* S3 uses real membership + lease semantics.
* Same role outputs, same scope_key format, same hierarchy.
* Differences are only operational envelope: number of instances, lease TTLs, registry TTLs.

> Pin: no env-specific semantic forks. Only wiring and TTL knobs differ.

---

## 11) What S3 must expose (so the system is diagnosable)

Minimum observability surfaces S3 must emit (to S8 / metrics):

* `active_scopes_count` (by kind)
* `lease_acquire_success/failure` rates
* `lease_renew_failure` rate
* `lease_churn` (how often scopes change owners)
* `cas_conflict_rate` (from S5 feedback, surfaced via S8)
* `scope_registry_size` and prune rate

This is how you detect split-brain risk early.

---

## 12) Non-negotiable “don’ts” (drift tripwires for S3)

S3 must **not**:

* infer degrade posture
* depend on SR/IG/EB to discover scopes as a hard dependency
* allow multiple encodings of the same scope
* allow two ACTIVE writers for the same scope without surfacing it as a critical health fault
* “drop” a scope silently that DF is actively requesting (registry TTL must be refreshed on demand)

---

If you’re happy with S3 as defined, the next move is to illuminate **S2 Policy Plane** (because it pins policy_rev atomicity and last-known-good), then **S1 Signal Plane** (signal catalogue + snapshot construction), and we’ll keep the same “no network change, only internal machinery reveal” discipline.

---

Absolutely — we’ll open **S2 (Policy Plane)** and expose the machinery inside it, **without changing the DL network we’ve already pinned**. S2’s job is to make “policy config is governed + versioned + auditable” *real* at runtime, and to hand S4 an **atomic, validated PolicyContext** (with last-known-good safety).

---

# S2 Policy Plane

## 1) What S2 is responsible for

S2 is the **sole internal authority** for:

1. **Resolving the active DL policy revision** (`policy_rev`) for this environment (and optionally for a scope kind).
2. **Fetching policy artifacts** by revision (by-ref; no “latest scanning”).
3. **Validating** policy artifacts (schema + semantic validation).
4. **Publishing an atomic PolicyContext** to S4 (no partial apply).
5. Maintaining **Last-Known-Good (LKG)** and safe fallback posture:

   * “new rev invalid/unloadable” never partially applies
   * “no LKG” implies DL is **BLIND → FAIL_CLOSED** (via S8 gate)

S2 does **not** evaluate degrade, does not interpret signals, and does not store posture.

---

## 2) S2 internal subnetworks (inside S2)

We’ll treat these as S2’s own internal opaque boxes (one level deeper):

* **S2-A Active Revision Resolver**
  Determines *which* `policy_rev` is active (from profiles + governance facts).

* **S2-B Artifact Locator & Fetcher**
  Turns `(policy_id, policy_rev)` into a by-ref locator and fetches the artifact.

* **S2-C Policy Validator**
  Validates structure + semantics (the “this cannot be nonsense” gate).

* **S2-D PolicyContext Builder**
  Normalizes the artifact into an in-memory `PolicyContext` ready for evaluation.

* **S2-E Atomic Switch + LKG Vault**
  Owns “current policy pointer,” last-known-good persistence, and safe rollback.

* **S2-F Change Notifier (to S8 + telemetry)**
  Emits `POLICY_REV_CHANGED`, `POLICY_LOAD_FAILED`, `POLICY_INVALID`, etc.

### S2 internal sketch

```
     (profiles + governed activation facts)
            |
            v
     [S2-A Active Rev Resolver]
            |
            v
     [S2-B Fetcher] ---> (by-ref artifact store: profiles/...)
            |
            v
     [S2-C Validator]
            |
            v
     [S2-D Context Builder]
            |
            v
 [S2-E Atomic Switch + LKG Vault] ---> (S2 emits PolicyContext to S4)
            |
            v
      [S2-F Notifier] ---> (S8 + metrics/logs)
```

---

## 3) The policy artifact “shape” S2 expects (design-level)

S2 consumes **policy config as a versioned artifact** (never “environment state”). The artifact must carry enough identity to be cited in provenance.

### Mandatory identity fields

* `policy_id` (stable identity, e.g., `dl_thresholds`)
* `policy_rev` (monotonic tag/revision)
* `policy_digest` (content hash; computed deterministically)

### Mandatory behavioral fields

* **Mode ladder** (ordered list): `NORMAL → DEGRADED_1 → DEGRADED_2 → FAIL_CLOSED`
* **Mode → capabilities_mask mapping** (the enforcement surface DF obeys)
* **Signal requirements**

  * required signal names (the set that can block upshift / force fail-safe)
  * optional signal names (may influence downshift but aren’t required)
* **Eligibility rules** (entry/exit corridors per rung)
* **Hysteresis params**

  * downshift immediate
  * upshift quiet period
  * one-rung upshift
* **Freshness params**

  * `max_signal_age` (stale/missing ⇒ unhealthy)
  * `max_decision_age` (serving freshness; stale posture ⇒ unsafe)

> That’s “policy config” (outcome-affecting), so S2 must treat it as governed and cite `policy_rev` in every PolicyContext it emits.

---

## 4) PolicyContext (what S2 emits to S4)

S2 emits **one atomic PolicyContext** at a time:

`PolicyContext {`

* `policy_id, policy_rev, policy_digest`
* `effective_from_utc` (optional)
* `mode_order[]`
* `mode_to_mask` (mapping table)
* `required_signals[]` (+ optional signal catalogue metadata)
* `eligibility_rules` (entry/exit conditions per mode)
* `hysteresis_params`
* `max_signal_age`
* `max_decision_age`
* `status ∈ {OK, UNAVAILABLE}` + reason codes
  `}`

**Hard pin:** S4 sees either the old PolicyContext or the new one, **never half/half**.

---

## 5) How S2 resolves the “active” policy_rev (S2-A)

This is where we make the **governed activation** real, without inventing new platform edges.

### Inputs S2 may use (two-channel, production-shaped)

S2-A can resolve “active policy_rev” from:

1. **Environment profile pointer**
   e.g., `dl.policy_rev_active` pinned in the environment profile (local/dev/prod), which itself is a versioned artifact.

2. **Governance activation facts (control lane)**
   A control-plane fact like “policy rev X became active” (auditable).
   S2 consumes it for fast convergence, but still polls the pointer for eventual consistency.

**Designer pin (v0):** Use **both**:

* control facts = *fast notification*
* polling pointer = *source of truth / eventual converge*

This makes S2 robust under missed events while staying governance-shaped.

---

## 6) Validation (S2-C) — what makes a policy “acceptable”

S2-C performs two layers of validation:

### A) Structural validation (schema-like)

* required fields present
* types correct
* mode names known (or explicitly declared and ordered)

### B) Semantic validation (drift killers)

* mode ladder is strictly ordered, includes `FAIL_CLOSED`
* mode→mask mapping is total (every mode has a mask)
* required_signals list is non-empty if policy claims upshift gating
* eligibility rules are well-formed and do not reference unknown signals
* hysteresis params are internally consistent (quiet period non-negative, etc.)
* `policy_rev` monotonicity rules (at least “comparable”; exact ordering mechanism is your choice)

**Hard pin:** If validation fails, the candidate policy_rev is **not eligible** to become active in S2-E.

---

## 7) Atomic switching + last-known-good (S2-E)

S2-E is the “safety vault.”

### Core rules

1. **Two-phase apply (stage then swap)**

* stage candidate `PolicyContextCandidate`
* validate fully
* swap `current_policy_context` atomically

2. **Last-known-good is mandatory**

* on successful swap, persist the new policy as LKG
* on failure to load/validate a new rev, continue using LKG (and emit telemetry)

3. **No LKG on cold start ⇒ BLIND**
   If there is no LKG and active policy cannot be loaded:

* S2 emits `PolicyContext{status=UNAVAILABLE}`
* S8 clamps DL to FAIL_CLOSED

### LKG persistence (deployment-shaped but minimal)

LKG should survive DL restarts. Acceptable persistence surfaces:

* local disk (per instance) **plus** “re-verify active pointer at boot”
* or a small row in the `dl` schema (still “derived-ish” but practical)
* or object-store ref under `profiles/` for the last applied rev

We don’t need to choose tech now; we just pin “LKG survives restart.”

---

## 8) Change notifier (S2-F → S8)

S2 must emit explicit health/change events:

* `POLICY_REV_CHANGED` (candidate accepted and swapped)
* `POLICY_LOAD_FAILED` (fetch error)
* `POLICY_INVALID` (validation failed)
* `POLICY_POINTER_UNAVAILABLE` (can’t resolve active rev)
* `POLICY_MISMATCH` (stored posture cites old rev; convergence needed)

These feed S8’s gate logic (BLIND/BROKEN) and rebuild triggers (seed posture after policy change).

---

## 9) Environment ladder posture for S2 (deployment pins)

### What must never change across envs

* Same PolicyContext semantics
* Same last-known-good behavior
* Same “invalid/unavailable ⇒ clamp FAIL_CLOSED” rule
* Same rule that decisions cite `policy_rev`

### What can differ by env profile

* `dl.policy_rev_active`
* strictness of thresholds/corridors inside the policy artifact
* polling intervals / cache TTLs
* whether control-fact consumption is enabled (still recommended in dev/prod)

**Important:** No “if prod then strict” logic in code. Strictness is a **policy artifact**, selected by profile and activated via governance.

---

## 10) Drift tripwires for S2 (explicit “don’ts”)

S2 must **not**:

* infer posture or look at signals (that’s S4/S1)
* partially apply a policy revision
* treat “missing policy” as “keep NORMAL”
* embed secrets in policy artifacts or in PolicyContext/provenance
* allow “latest artifact” scanning (policy selection is by ref + rev)

---

If you’re happy with S2, the next best node to open is **S1 (Signal Plane)** (signal catalogue + snapshot assembly), because S2 and S1 together define *the full input basis* for S4 without leaving hidden assumptions.

---

Absolutely — we’ll open **S1 (Signal Plane)** and expose the machinery inside it, **without changing the DL network**. S1’s job is to turn “observability world” into a **stable, explicit, deterministic SignalSnapshot** that S4 can evaluate without hidden assumptions.

I’ll keep this designer-authoritative and production-shaped, but still at “module design” level (not full spec).

---

# S1 Signal Plane

## 1) What S1 is responsible for

S1 is the sole internal authority for:

1. **Defining and maintaining a DL Signal Catalogue** (what signals DL knows about).
2. **Fetching / ingesting raw signal readings** from the observability substrate.
3. **Normalizing** readings into a canonical shape (name, unit, scope, window, stat).
4. **Quality classification** (`OK / STALE / MISSING / ERROR`) per reading.
5. **Assembling a stable, timestamped SignalSnapshot** for a given scope_key and window.
6. **Guaranteeing “no silent drops”** (required signals appear even when missing).

S1 does **not** decide mode, does not load policy, and does not store posture.

---

## 2) S1 internal subnetworks (inside S1)

We’ll treat these as S1’s own inner opaque boxes:

* **S1-A Signal Catalogue Manager**
  Defines signal IDs, units, aggregation stats, scope applicability.

* **S1-B Signal Backend Adapter(s)**
  Talks to the actual metrics backend(s) (PromQL/OTel/whatever). (Multiple adapters allowed.)

* **S1-C Reading Normalizer**
  Converts backend-specific responses into canonical `SignalReading` (unit conversion, naming, dimensions).

* **S1-D Quality & Staleness Classifier**
  Applies `max_signal_age`, handles missing/failed queries, marks quality.

* **S1-E Snapshot Assembler**
  Produces a deterministic `SignalSnapshot` bundle: stable ordering + snapshot_id.

* **S1-F Cache / Coalescer (optional)**
  Avoids hammering the backend; allows event-driven refresh semantics without flapping.

* **S1-G Telemetry Emitter**
  Sends HealthEvents/Stats to S8 (JI-09) about snapshot build success/failure, stale required signals, etc.

### S1 internal sketch

```
   PolicyContext (from S2) provides max_signal_age + required_signals list
                 |
                 v
     [S1-A Catalogue] ----+
                           \
   ScopeContext (from S3)   \
                 |           v
                 v     [S1-B Adapters] --> raw query results / errors
           [S1-E Snapshot Assembler] <--- [S1-C Normalizer] <---+
                 ^                         |
                 |                         v
                 +------------------- [S1-D Quality/Staleness]
                                        |
                                        v
                                    [S1-G Telemetry] --> S8
```

*(Note: S1 consumes “required signals list” from policy so it knows which absences are severe.)*

---

## 3) Canonical “signal identity” model (the Signal Catalogue)

### Why a catalogue is mandatory

Without a catalogue, DL becomes brittle: metric name drift, unit drift, and “missing signals treated as absent rather than unhealthy.” The catalogue is what makes SignalSnapshot stable and deterministic.

### SignalID (designer-pinned)

Every DL signal is identified by a stable ID:

`SignalID := <component>.<signal_family>.<metric_name>.<stat>`

Examples (illustrative, not exhaustive):

* `ofp.latency.feature_snapshot.p95`
* `ofp.errors.feature_snapshot.rate_1m`
* `ieg.latency.query.p95`
* `df.latency.decision.p95`
* `eb.lag.consumer_offsets.max`
* `al.errors.execute.rate_1m`

**Pin:** DL does not rely on backend metric names directly. Backend metric names map to these stable SignalIDs via the catalogue.

### SignalSpec (catalogue entry)

Each SignalID has:

* `signal_id` (stable)
* `source_component` (OFP/IEG/DF/EB/AL/etc.)
* `unit` (ms, ratio, count, seconds, etc.)
* `stat` (p50/p95/p99/rate/max/min/gauge)
* `scope_applicability` ∈ {GLOBAL_ONLY, SCOPE_COMPATIBLE}
* `required_by_policy` (boolean; policy can override required set)
* `query_template` (backend-specific; can be abstracted)

**Pin:** the catalogue defines what “correct unit and stat” mean; S1 normalizes to it.

---

## 4) Scope handling inside S1 (global vs scoped readings)

S1 must support the scope model pinned by S3: `GLOBAL`, `MANIFEST`, `RUN`.

### Two categories of signals

1. **GLOBAL_ONLY signals**
   Examples: metrics backend health, DL store health, EB consumer lag for the DF consumer group.

2. **SCOPE_COMPATIBLE signals**
   Examples: OFP “freshness/staleness rate for this run/world”, IEG “query latency for this scope”, etc.

### Designer pin (v0): S1 emits scope snapshots that include global signals

S4 should consume **one input snapshot** per evaluation. So:

* S1 assembles a snapshot for `scope_key`
* it includes:

  * all global signals (replicated into every scope snapshot), and
  * any scope-compatible signals available for that scope

This avoids “S4 merges two snapshots” complexity and drift.

---

## 5) Windowing and snapshot semantics

### Snapshot timing fields (pinned)

A SignalSnapshot includes:

* `snapshot_window` (e.g., `rolling_1m`, `rolling_5m`)
* `snapshot_end_utc` (the anchor time the snapshot represents)
* `observed_at_utc` (when S1 assembled it)

**Pin:** S4 evaluates against `snapshot_end_utc` as the “time of observation,” not the process wall clock. (This prevents hidden-now drift and makes replay/test harnesses plausible.)

### Snapshot assembly rules

S1 may:

* query the backend for the latest windowed stats “as of now”
* but it must stamp the snapshot with:

  * `snapshot_end_utc` = the backend sample time if available, else `observed_at_utc`

---

## 6) Canonical SignalReading shape (what S1 outputs to S4)

S1 outputs `SignalSnapshot{ readings[] }` where each reading is:

`SignalReading{`

* `signal_id` (stable from catalogue)
* `source_component`
* `stat`
* `value` (float)
* `unit`
* `sample_time_utc` (if backend provides)
* `quality` ∈ `{OK, STALE, MISSING, ERROR}`
* `error_code` (optional)
* `raw_ref` (optional debug pointer; not required for correctness)
  `}`

### Deterministic ordering (hard pin)

Readings must be output in stable order:

* sort by `signal_id` lexicographically (then `stat` if needed)

No backend response order leakage.

---

## 7) Missing / stale / error semantics (the most important part)

This is where the platform’s “fail toward safety” becomes concrete.

### Staleness definition (hard pin)

A reading is `STALE` if:

`(snapshot_end_utc - sample_time_utc) > policy.max_signal_age`

If sample_time is missing:

* treat it as `STALE` unless the backend explicitly guarantees recency (rare)

### Missing definition (hard pin)

A reading is `MISSING` if:

* backend returns “no data” for the query, or
* the signal is not available for that scope/window

**Pin:** required signals must still appear as `MISSING` readings — never omitted.

### Error definition (hard pin)

A reading is `ERROR` if:

* query failed (timeout, auth, backend unavailable)
* parse/normalization failed

### Required vs optional (who decides?)

Policy (S2) defines which signals are required **for upshift gating** and potentially for hard fail-safe triggers.

S1’s role is:

* classify quality per signal
* highlight “required signals degraded” in telemetry to S8
  It does **not** decide the posture impact; that remains S4 + policy.

### Snapshot build failure (still returns a snapshot)

If S1 cannot assemble a complete snapshot due to backend failure, it still produces a snapshot with:

* required signals as `ERROR` (or `MISSING`)
* `snapshot_build_status=FAILED`
  so S4 can deterministically move toward safety rather than “no input.”

---

## 8) Backend adapters (S1-B) — production-shape without overbinding tech

S1-B is allowed to support multiple backends, but must present a uniform interface:

`FetchReadings(scope_key, window_id, signal_ids[]) -> { reading_results[], fetch_status }`

**Pins:**

* adapters must return sample timestamps when available
* adapters must return explicit “no data” vs “error”
* adapters must not silently downsample or change stats (p95 must be p95)

---

## 9) Cache / coalescer (S1-F) — to avoid hammering metrics backends

Because DL may evaluate per scope and may also have inline refresh, S1 needs a coalescer:

* cache recent readings per `(signal_id, scope_key, window_id)`
* TTL shorter than `max_signal_age`
* coalesce repeated requests within a tick
* still preserve explicit staleness (cache can return “STALE” if TTL exceeded)

**Pin:** caching must never turn unknown into OK; it can only preserve or worsen quality as time passes.

---

## 10) Telemetry emission to S8 (S1-G)

S1 must emit HealthEvents/Stats to S8 (JI-09), including:

* `SIGNAL_BACKEND_UNREACHABLE` / `SIGNAL_QUERY_FAILED`
* `SIGNAL_STALE_REQUIRED` (which required signals stale/missing)
* `SIGNAL_SNAPSHOT_BUILD_FAILED`
* snapshot build latency / success rate

This is essential for S8 to classify DL as BLIND when signals are untrustworthy.

---

## 11) Environment ladder posture for S1

### Must remain identical across envs

* same SignalSnapshot semantics
* same quality classification logic
* same “required signals appear even when missing”
* same deterministic ordering

### What can vary via profile knobs

* which signal backends you use (wiring)
* query timeouts
* eval cadence (affects how frequently S1 is called)
* in local/dev you may use fault injection to exercise staleness/missing logic, but **never code forks**.

---

## 12) Drift tripwires for S1 (explicit “don’ts”)

S1 must **not**:

* decide degrade mode or mask
* hide missing signals by omission
* treat backend failures as “assume healthy”
* change the meaning of stats/units silently (unit conversion must be explicit and correct)
* output unstable ordering

---

If you’re happy with S1, the next node to open is **S5 (Posture State Plane)** because it’s the “atomic truth inside DL” that serving and control publication depend on.

---

Absolutely — we’ll open **S5 (Posture State Plane)** and expose the machinery inside it. This is the “spine” inside DL: it’s the **atomic current posture record + minimal continuity memory**, with **CAS/monotonic sequencing**, and it’s explicitly **derived + rebuildable** (not a primary system-of-record).

Everything below is designer-authoritative for S5, and it is designed to satisfy the joins/paths/loops we already pinned (JI-04/05/06/08, IP-01/02/06/07, IL-01/02/05/07).

---

# S5 Posture State Plane

## 1) What S5 is responsible for

S5 is the sole authority inside DL for:

1. **The current posture record per scope** (`dl.current_posture[scope_key]`)
2. **Atomic updates** of that record
3. **Minimal continuity memory** for hysteresis (prior state)
4. **Monotonic `posture_seq`** increments on **material change**
5. **Commit idempotency** (retry-safe DecisionCommit)
6. **CAS enforcement** to prevent stale writers / split-brain updates
7. **Material-change detection** (so control publishing is consistent)
8. Providing read surfaces:

   * `ReadCurrentPosture` (for S6 serving)
   * `ReadPriorState` (for S4 hysteresis)

S5 does **not** decide posture (S4 does), does **not** load policy (S2), and does **not** fetch signals (S1).

---

## 2) S5 internal subnetworks (inside S5)

We’ll treat these as S5’s own inner opaque boxes:

* **S5-A Record Model & Canonicalizer**
  Defines the record schema and canonical digest logic.

* **S5-B Store Adapter**
  Reads/writes the underlying store (Postgres/kv/etc.) with atomic semantics.

* **S5-C Commit Engine (CAS + Idempotency)**
  Implements JI-05 semantics: CAS, lease guard, idempotent commits.

* **S5-D Sequencer & Change Detector**
  Determines material change; increments posture_seq; sets change_kind.

* **S5-E Read APIs**
  Serves:

  * current posture record (JI-06)
  * prior posture state (JI-04)

* **S5-F Outbox / Notify Hook (optional)**
  Creates “pending publish” items for S7 when posture changes (JI-08/IP-05).

* **S5-G Health & Integrity Monitor**
  Detects corruption, digest mismatch, read/write failures; emits telemetry to S8 (JI-09).

### S5 internal sketch

```
         JI-05 CommitRequest (from S4)
                    |
                    v
        [S5-C Commit Engine] ---> [S5-D Sequencer/ChangeDetect]
                    |                    |
                    v                    v
             [S5-B Store Adapter] <-> [S5-A Model/Canonicalizer]
                    |
      +-------------+--------------+
      |                            |
      v                            v
 [S5-E Read APIs]            [S5-F Outbox] (optional)
      |
      v
  JI-04 PriorState  &  JI-06 CurrentPostureRecord

 All health -> [S5-G] -> S8 telemetry
```

---

## 3) The core data model: `CurrentPostureRecord`

### Key

* `scope_key` (canonical from S3; **only** key)

### Value (atomic blob)

`CurrentPostureRecord` must contain:

#### A) Decision payload (what DF ultimately uses via S6)

* `mode`
* `capabilities_mask` (full object)
* `policy_rev` (+ `policy_digest` recommended)
* `decided_at_utc` (domain time of posture decision)
* `snapshot_id` (ties to S1 snapshot)
* `provenance` (full or compact summary + refs)

#### B) Continuity (minimal hysteresis memory)

* `last_mode`
* `last_transition_at_utc`
* `quiet_period_until_utc`
* `posture_seq` (monotonic integer per scope)
* `last_material_change_at_utc` (optional convenience)

#### C) Store metadata (helps serving/caching/integrity)

* `record_digest` (deterministic digest of the canonical record)
* `last_write_at_utc` (store time)
* `writer_instance_id` (optional)
* `lease_id` (optional but strongly recommended if HA)

#### D) Status

* `record_status ∈ {OK, CORRUPT}` (computed/validated at read time)
* `schema_version` (for migrations; optional but practical)

**Pin:** The record is **atomic**: readers never see “new mode with old seq,” etc.

---

## 4) `PriorPostureState` view (JI-04)

S5 exposes a minimal view extracted from `CurrentPostureRecord`:

`PriorPostureState{`

* `last_mode` (or `mode` as last known)
* `last_transition_at_utc`
* `quiet_period_until_utc`
* `posture_seq`
* `policy_rev` (optional; helps detect mismatch quickly)
* `status ∈ {PRESENT, MISSING, CORRUPT}`
  `}`

**Pin:** PriorState is read-only and minimal — no history.

---

## 5) Commit semantics (JI-05) — the Commit Engine (S5-C)

S5 receives:

`CommitRequest{ scope_key, decision, continuity, commit_id, prior_seq, lease_id? }`

### 5.1 CAS guard (hard)

S5 must enforce **compare-and-swap** on `prior_seq`:

* If `prior_seq == current.posture_seq` → eligible to commit
* Else → `CONFLICT` (caller must reread prior state and retry evaluation)

This is the internal wall against stale writers and races.

### 5.2 Lease guard (hard in HA, no-op in single instance)

If HA is enabled:

* CommitRequest must include `lease_id`
* Store record carries current `lease_id`
* Commit is accepted only if lease matches and not expired (conceptually)

If local/single-instance:

* lease guard is trivially satisfied

### 5.3 Idempotency (hard)

Commits must be retry-safe:

* `commit_id` is a stable idempotency key for a computed decision (e.g., derived from `scope_key + snapshot_id + policy_rev`).
* If the same commit_id arrives again, S5 returns the same result (COMMITTED or NOOP) without creating new posture_seq increments.

### 5.4 Material change detection (hard)

S5 determines `material_change` by comparing the candidate to the current record:

Material change if any changed:

* `mode`
* `capabilities_mask` (effective equality, not pointer equality)
* `policy_rev`
* forced failsafe entered/exited

If **not** material:

* return `NOOP`
* optionally update `decided_at_utc` / `last_write_at_utc` to keep freshness honest (but do not bump seq)

### 5.5 Sequencing rule (hard)

If material change:

* `posture_seq := current.posture_seq + 1` (or 1 if missing record)
* `last_transition_at_utc := decision.decided_at_utc`
* `quiet_period_until_utc := decision.decided_at_utc + policy.quiet_period_for_this_rung` (computed by S4; S5 stores it)

**Pin:** posture_seq increments **only** on material change.

### 5.6 Commit result (pinned)

S5 returns:

`CommitResult{ status, scope_key, posture_seq, change_kind?, record_digest?, reason? }`

* `status ∈ {COMMITTED, NOOP, CONFLICT, REJECTED}`
* `change_kind` ∈ {MODE_CHANGED, MASK_CHANGED, POLICY_REV_CHANGED, FORCED_FAILSAFE_ENTERED, FORCED_FAILSAFE_EXITED}

---

## 6) Reads for serving (JI-06) — the Read APIs (S5-E)

S5 exposes:

### `ReadCurrentPosture(scope_key) -> CurrentPostureRecord`

* Returns `MISSING` if no record exists
* Validates `record_digest` (if present) and marks `CORRUPT` if mismatch/parse failure

### `ReadPriorState(scope_key) -> PriorPostureState`

* Extracts continuity fields
* Marks `MISSING` / `CORRUPT` similarly

**Pin:** S5 never “manufactures” a record; missing is explicit.

---

## 7) Corruption detection and rebuild readiness (S5-G + JI-11)

S5 must detect:

* parse failures
* missing required fields
* digest mismatch
* impossible timestamps (e.g., quiet_period_until < last_transition_at)
* negative seq or seq rollback

On detection, S5:

* emits `POSTURE_RECORD_CORRUPT` to S8 (JI-09)
* returns `CORRUPT` status to readers
* rejects commits if state is unrecoverably inconsistent (or accepts commits that overwrite with a known-good seed; design choice)

**Designer pin (safe):**

* If corruption is detected, treat DL as **BROKEN** for that scope and clamp FAIL_CLOSED until rebuild completes.
* Rebuild is triggered via S8 (JI-11) and results in a fresh commit from S4→S5.

---

## 8) The outbox hook for control publishing (S5-F, optional)

If control events are enabled (A6 / IP-05), S5 is the only correct place to decide “posture changed” because it owns `posture_seq` and material-change detection.

So on `COMMITTED` with material change:

* S5 creates an **OutboxItem** keyed by `(scope_key, posture_seq)` with stable `event_id`.
* S7 drains and publishes.

**Pin:** outbox creation is atomic with posture commit (or logically coupled) so a crash cannot lose the fact that a posture change occurred.

---

## 9) Environment ladder posture for S5

### Must be identical across envs

* atomic record semantics
* CAS semantics
* material change definition
* posture_seq monotonicity rules
* derived/rebuildable stance (not primary truth)

### Allowed to differ by env profile

* underlying store type (Postgres vs embedded kv in local)
* retention / vacuum / compaction
* HA replication / backups

But semantics must remain unchanged.

---

## 10) Drift tripwires for S5 (explicit don’ts)

S5 must **not**:

* store “history” as a primary log (history comes from audit/control facts)
* accept commits without CAS/lease guard (in HA)
* bump posture_seq on every refresh (would cause event storms + false transitions)
* silently “repair” corruption without surfacing it to S8
* become a place where policy decisions are made (mode/mask remains S4)

---

## 11) Minimal interfaces S5 provides to the rest of DL

To keep Codex implementation clean, S5 exposes only these conceptual calls:

* `ReadCurrentPosture(scope_key) -> CurrentPostureRecord|MISSING|CORRUPT`
* `ReadPriorState(scope_key) -> PriorPostureState|MISSING|CORRUPT`
* `CommitPosture(scope_key, prior_seq, lease_id?, commit_id, decision, continuity) -> CommitResult`

Everything else (publishing, serving, self-health gating) composes around these.

---

If you’re happy with S5, the next node to illuminate is **S4 (Evaluation & Hysteresis Plane)**, because now we have the full input basis (S1 snapshot + S2 policy + S5 prior state + S3 scope) and the commit semantics (S5) pinned — so we can define mode eligibility + provenance assembly without “mystery dependencies.”

---

Absolutely — we’ll open **S4 (Evaluation & Hysteresis Plane)** and expose the machinery inside it. This is the **only place inside DL that is allowed to decide mode/mask**. Everything else feeds it (signals/policy/prior state/scope) or persists/serves its result.

What follows is **designer-authoritative** for S4, and it is written to *fit the already-pinned internal joins/paths/loops* (JI-01…JI-11, IP-01…IP-07, IL-01…IL-07) without changing the DL network.

---

# S4 Evaluation & Hysteresis Plane

## 1) What S4 is responsible for

S4 is the sole internal authority for:

1. **Evaluating posture** deterministically from:

   * `SignalSnapshot` (S1)
   * `PolicyContext` (S2)
   * `PriorPostureState` (S5)
   * `ScopeContext` (S3)
   * `HealthGate` (S8)

2. Applying the **transition laws**:

   * downshift immediate
   * upshift gated by quiet period + required-signal health
   * one rung per upshift
   * deterministic tie-break (“most degraded eligible”)

3. Producing a **DegradeDecision** + minimal continuity update for commit:

   * `mode`
   * `capabilities_mask`
   * `provenance`
   * `decided_at_utc` + `policy_rev` + `snapshot_id`

S4 does **not** read metrics backends, does **not** load policy artifacts, and does **not** write stores directly.

---

## 2) S4 internal subnetworks (inside S4)

Think of S4 as these internal opaque modules (we can dive into them later if needed):

* **S4-A EvalContext Binder**
  Binds inputs into one evaluation context (scope, times, policy, snapshot, prior).

* **S4-B Predicate & Eligibility Engine**
  Computes per-signal predicate outcomes and per-mode eligibility.

* **S4-C Transition Engine (Hysteresis)**
  Chooses the next mode using prior state, quiet periods, and rung rules.

* **S4-D Mask Resolver**
  Maps `mode → capabilities_mask` (policy-driven; no invention).

* **S4-E Provenance Composer**
  Builds compact, deterministic “why” information.

* **S4-F Commit Proposal Builder**
  Produces `CommitRequest` pieces: commit_id, continuity fields, proposed change kind.

* **S4-G Eval Telemetry Emitter**
  Emits `EVAL_FAILED`, `EVAL_FORCED_FAILSAFE`, etc. to S8 (JI-09).

Internal sketch:

```
Inputs (S1,S2,S3,S5,S8)
        |
        v
  [S4-A Binder] -> [S4-B Eligibility] -> [S4-C Transition] -> [S4-D Mask]
                                           |
                                           v
                                  [S4-E Provenance]
                                           |
                                           v
                                  [S4-F CommitProposal] -> (JI-05 to S5)
                                           |
                                           v
                                  [S4-G Telemetry] -> S8
```

---

## 3) S4 input contract (what it consumes)

S4 consumes a single **EvalInput**:

### EvalInput

* `scope_context` (scope_key + parent chain + writer_role + lease)
* `policy_context` (must be atomic; status OK or UNAVAILABLE)
* `signal_snapshot` (stable readings + qualities + snapshot_id)
* `prior_state` (present/missing/corrupt; posture_seq; quiet_period_until)
* `health_gate` (may force FAIL_CLOSED)

**Hard rule:** S4 never re-queries anything. It only uses what it was handed.

---

## 4) S4 output contract (what it produces)

S4 produces an **EvalResult** suitable for JI-05 commit:

### EvalResult (core)

* `decision` (DegradeDecision candidate)
* `continuity_update` (quiet_period_until, last_transition_at, etc.)
* `commit_id` (idempotency key)
* `eval_status` ∈ `{OK, FORCED_FAILSAFE, UNSAFE_INPUTS}`

S5 remains the final authority for:

* atomic commit
* CAS acceptance
* posture_seq assignment on material change

---

# 5) The evaluation algorithm (production semantics, deterministic)

## Step 0 — Apply HealthGate override (S8 has top priority)

If `health_gate.forced_mode` is present (BLIND/BROKEN), S4 **does not evaluate** eligibility. It emits:

* `mode = FAIL_CLOSED`
* `capabilities_mask = policy.mode_to_mask[FAIL_CLOSED]` (or a minimal conservative mask)
* provenance: `forced_by = S8`, include reason_codes
* continuity_update: treat as a material transition (so it can be committed/published if desired)

This is how “DL failure cannot widen capabilities” becomes mechanical.

---

## Step 1 — Bind the evaluation anchor times (no hidden “now”)

S4 chooses a single evaluation anchor time:

* `decided_at_utc := signal_snapshot.snapshot_end_utc`
  (If not available, fall back to `observed_at_utc`.)

This is **the** time that appears in the decision and continuity. It prevents “wall clock drift” from silently affecting posture.

---

## Step 2 — Compute predicate outcomes (the raw material)

S4 evaluates **policy-declared predicates** against the snapshot readings.

### Predicate model (policy-driven)

A predicate is a boolean test like:

* `signal_id(window=W).quality == OK`
* `signal_id(window=W).value <= threshold`
* `signal_id(window=W).value >= threshold`
* composite: `ALL_OF([...])`, `ANY_OF([...])`

**Pinned rule:** if the referenced signal reading is `MISSING/STALE/ERROR`, the predicate outcome is **false** unless the predicate explicitly tests for that quality.

This keeps “missing data” from being treated as “healthy by default.”

---

## Step 3 — Determine per-mode eligibility (policy provides the ladder logic)

For each mode `m` in the ordered ladder:
`NORMAL → DEGRADED_1 → DEGRADED_2 → FAIL_CLOSED`

S4 computes:

* `eligible[m]` (boolean)
* `explanations[m]` (which predicates passed/failed)

### How policy expresses eligibility

Policy supplies, per mode:

* `eligibility_predicate[m]` (a boolean expression over predicate outcomes)

This is deliberately general: it can encode:

* strict NORMAL requirements
* looser degraded requirements
* “fail closed if required signals are missing” requirements

**Pinned tie-break:** If multiple modes are eligible, “most degraded eligible” is always preferred when selecting a safe fallback.

---

## Step 4 — Apply transition laws (hysteresis & one-rung recovery)

This is the heart of S4-C.

Let:

* `current_mode := prior_state.last_mode` (if missing/corrupt, treat current_mode as the **mode stored in current posture** if available; otherwise treat as `FAIL_CLOSED` for safety)
* `worst_eligible := most degraded mode with eligible[m]=true`
* `best_eligible  := least degraded mode with eligible[m]=true`

Now choose `next_mode`:

### 4.1 Downshift rule (immediate)

If `worst_eligible` is **more degraded** than `current_mode`:

* `next_mode = worst_eligible` (immediate downshift)

No quiet period can block a downshift.

### 4.2 No-change rule

If `current_mode` is eligible and no more degraded mode is required:

* `next_mode = current_mode`

### 4.3 Upshift rule (gated, one rung)

If `best_eligible` is **less degraded** than `current_mode`:

* Up-shift is permitted only if:

  1. `decided_at_utc >= prior_state.quiet_period_until_utc`
  2. all `policy.required_signals` have `quality=OK` in the snapshot

If permitted:

* candidate = the **next less degraded rung** above current_mode
  (one rung only)
* if `eligible[candidate] == true` then `next_mode = candidate`
  else remain in `current_mode`

If not permitted:

* `next_mode = current_mode`

This is exactly the “slow recovery” posture we pinned.

---

## Step 5 — Resolve the capabilities mask (policy-mapped, no invention)

S4-D sets:

* `capabilities_mask := policy.mode_to_mask[next_mode]`

**Pinned:** S4 does not “tweak” masks ad hoc. If you want a tweak, it must be expressed as policy.

---

## Step 6 — Compose provenance (deterministic, compact, useful)

S4-E produces provenance that explains:

* identity:

  * `policy_rev` (+ digest)
  * `snapshot_id`
  * `scope_key`
  * `decided_at_utc`
* transition:

  * `prior_mode`
  * `next_mode`
  * `transition_type ∈ {DOWNSHIFT, UPSHIFT, STAY, FORCED_FAILSAFE}`
  * `quiet_period_until_utc` (for transparency)
* triggers:

  * a deterministic, sorted list of **failed predicates** that caused downshift **or** blocked upshift
  * for each trigger: `signal_id`, `window_id`, `observed_value`, `threshold`, `operator`, `quality`

**Pinned ordering:** triggers are sorted lexicographically by `signal_id`, then `window_id`, then `operator`. No “whatever order evaluation ran.”

**Pinned privacy:** provenance must not include secrets; only IDs, digests, and observed values.

---

## Step 7 — Build commit proposal (retry-safe)

S4-F prepares:

* `commit_id` (stable idempotency key)
  Recommended: hash of `(scope_key, snapshot_id, policy_rev, next_mode, mask_digest)`
* `continuity_update`:

  * `last_transition_at_utc = decided_at_utc` if material change
  * `quiet_period_until_utc = decided_at_utc + policy.quiet_period_for(next_mode)`
    (applied on any material change so you can’t immediately upshift again)
* `prior_seq` echoed from `prior_state.posture_seq` (CAS guard)
* `lease_id` forwarded from ScopeContext (HA guard)

S5 will re-check material change and enforce monotonic `posture_seq`.

---

# 6) What happens on “unsafe inputs” (policy missing, snapshot failed, etc.)

S4 must behave deterministically under bad inputs:

### If `policy_context.status=UNAVAILABLE`

S4 emits `eval_status=UNSAFE_INPUTS` and produces `FAIL_CLOSED` posture with provenance `reason=POLICY_UNAVAILABLE`.

### If required signals are missing/stale/error

This does not cause S4 to “skip”; it causes eligibility to reflect reality:

* Normal will likely be ineligible
* degraded/fail-closed may be eligible (policy decides)
* upshift will be blocked by required-signal gating

### If prior state is corrupt/missing

S4 evaluates using snapshot + policy, but treats upshift conservatively because:

* if prior is unknown, “current_mode” is treated as FAIL_CLOSED (safe default) unless you have a known stored posture to use
* first committed posture becomes the new anchor for hysteresis

S4 emits telemetry about prior_state quality to S8 (JI-09).

---

# 7) Environment ladder posture for S4

S4’s semantics **do not change** across local/dev/prod:

* same transition laws
* same tie-break
* same staleness handling
* same provenance shape

Only policy/profile knobs change:

* thresholds/corridors
* required signals list
* quiet periods
* TTLs (`max_signal_age`, `max_decision_age`)

No “if prod then…” logic.

---

# 8) Drift tripwires for S4 (explicit don’ts)

S4 must **not**:

* query metrics backends or policy stores directly
* use implicit wall clock in a way that changes decisions without explicit timestamps
* invent capabilities not in policy mapping
* upshift more than one rung
* allow upshift while required signals are stale/missing/error
* produce non-deterministic provenance ordering

---

If you’re happy with S4, the next node to illuminate is **S6 (Serving Plane)** (freshness enforcement + request boundary time + inline-eval escape hatch vs fail-closed), because now we’ve pinned exactly what a decision *is* and how it is computed.

---

Absolutely — we’ll open **S6 (Serving Plane / DF join surface)** and expose the machinery inside it. S6 is the **J9 boundary realization** inside DL: it’s what DF interacts with to obtain a **fresh-enough DegradeDecision**, and it is where we enforce “missing/stale posture ⇒ fail-safe” *without ever inventing posture*.

Everything below is designer-authoritative for S6 and is designed to satisfy the already-pinned joins/paths/loops (JI-06/07/10, IP-02, IL-02, plus the outer J9 contract).

---

# S6 Serving Plane

## 1) What S6 is responsible for

S6 is the sole internal authority for:

1. **Serving DegradeDecision to DF** (and optionally other read-only consumers).
2. Enforcing **freshness semantics** using **explicit decision boundary time** (no hidden “now”).
3. Applying **S8 HealthGate precedence** (forced FAIL_CLOSED overrides all).
4. Choosing between:

   * serving from stored posture (S5), or
   * triggering bounded inline refresh (S6→S4, optional), or
   * returning deterministic safe fallback (FAIL_CLOSED) when it can’t be safe.
5. Preventing **thundering herd** (singleflight per scope).
6. Producing **serving provenance** (explicitly stating whether served-from-store, inline refreshed, or fallback).

S6 does **not** decide mode/mask (S4 does), does **not** store posture (S5 does), and does **not** publish control events (S7 does).

---

## 2) S6 internal subnetworks (inside S6)

We’ll treat these as S6’s internal nodes:

* **S6-A Request Normalizer & Scope Resolver**
  Validates requests, derives canonical `scope_key`, and determines fallback chain (RUN→MANIFEST→GLOBAL).

* **S6-B HealthGate Enforcer**
  Consults S8 gate; applies forced fail-safe precedence.

* **S6-C Posture Reader & Freshness Evaluator**
  Reads from S5 and decides if it is fresh enough for the request boundary time.

* **S6-D Inline Refresh Orchestrator (optional)**
  Singleflight + deadline-bound inline evaluation via S4→S5 commit.

* **S6-E Fallback Constructor**
  Constructs deterministic FAIL_CLOSED DegradeDecision with explicit provenance when serving cannot be safe.

* **S6-F Response Composer & Audit Hooks**
  Returns DegradeDecision + serving metadata; emits telemetry to S8.

Internal sketch:

```
DF request -> [S6-A Scope Resolver] -> [S6-B Gate]
                                   -> [S6-C Read+Freshness] -> ok? -> [S6-F Response]
                                               |
                                               v (stale/missing/corrupt)
                                       [S6-D Inline Refresh] (optional)
                                               |
                                      success? v fail/timeout
                                         [S6-F]       [S6-E Fallback] -> [S6-F]
```

---

## 3) The request contract S6 expects (design-level)

We are not writing a full schema, but S6 requires these semantic inputs:

### Required

* **`scope_descriptor`** (or already-canonical `scope_key`)

  * if descriptor: `{scope_kind, pins}` (from S3 semantics)
* **`decision_time_utc`**
  The explicit decision boundary time DF is operating under (usually event `ts_utc`).

### Optional (useful)

* `request_id` / trace id (for telemetry)
* `max_wait_ms` (bounded serving budget; otherwise use a profile default)
* `require_scope_exact` (rare; default false)
* `caller_kind` (DF vs tool vs dashboard; affects permissiveness on fallback chain)

**Hard pin:** Serving freshness is evaluated relative to `decision_time_utc`. Never hidden wall clock.

---

## 4) Scope resolution and fallback chain (S6-A)

### Canonical rule

S6 must resolve request scope using **S3-produced canonicalization**. If request supplies a descriptor, S6 calls S3-B canonicalizer conceptually and obtains:

* `scope_key`
* `parent_scope_key` chain (RUN→MANIFEST→GLOBAL)

### Fallback chain (designer-pinned)

In v0, S6 is allowed to fallback along the chain **only if it results in a more conservative posture**, and the fallback is explicitly recorded in serving provenance.

Order:

1. Try exact `scope_key`
2. If missing/stale/corrupt, try parent
3. Continue until GLOBAL
4. If still missing or gated, return FAIL_CLOSED

**Pin:** fallback chain is a serving strategy; it **must never widen capabilities**. If a parent posture is *less degraded* than the requested scope would require, that’s unsafe — so we apply a “monotone safety” rule:

> Only accept a fallback posture if it is **>= as degraded** as what you’d be comfortable applying at the requested scope.

Because S6 can’t know “what requested scope would require” without evaluating, the safe v0 rule becomes:

* If falling back, you are allowed to use parent posture only when the requested posture is unavailable, but you must treat it as “uncertain” and may clamp further if policy says so.

**Practical v0 pin:** fallback to parent is allowed only when:

* parent posture is **not NORMAL** (i.e., already conservative), **or**
* inline refresh is disabled and you must choose between parent vs FAIL_CLOSED; in that case choose the **more conservative** of the two (usually FAIL_CLOSED wins unless parent is already FAIL_CLOSED).

---

## 5) HealthGate precedence (S6-B)

S6 must consult S8’s `HealthGate` before doing anything else.

### Precedence rules (hard)

1. If `HealthGate` indicates **BLIND/BROKEN** (forced_mode present):

   * Return **FAIL_CLOSED** immediately (no store read required).
   * Provenance says `forced_by=S8`, with reason codes.

2. If `HealthGate` is IMPAIRED:

   * Serving is allowed, but inline refresh may be disabled/throttled.
   * Upshift is generally discouraged by S4 anyway; S6 just follows freshness rules.

3. If `HealthGate` is HEALTHY:

   * Normal serving path.

This is the internal enforcement of “DL failure cannot widen capabilities.”

---

## 6) Freshness evaluation (S6-C) — the core serving law

S6 reads posture from S5 (JI-06) and evaluates whether it’s safe to use for this request.

### Freshness computation (hard)

Let:

* `T_req = decision_time_utc`
* `T_dec = posture.decided_at_utc`

Compute:

* `age = T_req - T_dec`

Rules:

* If `age < 0` (posture decided after decision boundary): treat as **fresh** (it’s still safe), but record a “time inversion” note in provenance (this can happen under clock skew or if decision_time is historical).
* If `age <= policy.max_decision_age`: **fresh enough**
* Else: **stale**

**Pin:** `max_decision_age` comes from PolicyContext (S2). It is policy config, not wiring.

### Missing/corrupt posture (hard)

If S5 returns `MISSING` or `CORRUPT`, treat as “unservable” and proceed to inline refresh or fallback.

---

## 7) Inline refresh orchestrator (S6-D) — optional escape hatch

Inline refresh exists to prevent “cold start” or “posture store cleared” from forcing prolonged FAIL_CLOSED when evaluation could quickly restore posture.

### When inline refresh is allowed

Inline refresh may be attempted only if:

* profile `dl.inline_eval_enabled=true`, and
* request budget allows (deadline), and
* S8 gate is not BLIND/BROKEN, and
* singleflight for scope isn’t already in flight (or the in-flight one can be awaited briefly)

### Singleflight (hard)

There must be at most one inline evaluation per `scope_key` at a time.

* key: `singleflight_key = scope_key`
* others either wait briefly or fall back.

### Deadline-bound (hard)

Inline refresh must be bounded by:

* `deadline_utc = now + max_wait_ms` (or computed from request budget)

If inline eval can’t finish by deadline → fallback.

### What inline refresh does (sequence)

1. S6 triggers EvaluateNow (JI-07) to S4:

   * includes `scope_key`, `decision_time_utc`, reason (`STALE/MISSING/CORRUPT`), deadline
2. S4 evaluates and commits to S5 via JI-05 (atomic)
3. S6 rereads S5 and re-checks freshness
4. Serve fresh posture if available; otherwise fallback

**Pin:** even inline refresh never returns a “direct result” that bypasses S5 — S5 remains the single posture source for serving.

---

## 8) Deterministic fail-safe fallback (S6-E)

When S6 cannot safely obtain a posture (or cannot inline-refresh in time), it must return **FAIL_CLOSED**, explicitly.

### Fallback decision construction (pinned)

Return a DegradeDecision with:

* `mode = FAIL_CLOSED`
* `capabilities_mask = policy.mode_to_mask[FAIL_CLOSED]` if policy is available
  otherwise a minimal hard-coded conservative mask (still FAIL_CLOSED)
* `policy_rev` if known (LKG or active); else `policy_rev=UNKNOWN`
* `decided_at_utc = decision_time_utc` (serving boundary; this is a “serving-time decision”)
* provenance:

  * `fallback_reason ∈ {DL_FORCED_GATE, POSTURE_MISSING, POSTURE_STALE, POSTURE_CORRUPT, INLINE_EVAL_TIMEOUT, POLICY_UNAVAILABLE}`
  * any relevant details (scope_key, requested time, record age)

**Pin:** Fallback must be **recordable** and consistent: same inputs → same fallback output shape.

---

## 9) Response composition and telemetry (S6-F)

S6 returns to DF:

### Response (conceptual)

* `degrade_decision` (the object DF uses and records)
* `serving_meta` (not required for DF, but useful):

  * `served_from ∈ {STORE, INLINE_REFRESH, FALLBACK, GATE_FORCED}`
  * `scope_used` (exact, or parent scope if fallback chain was used)
  * `posture_seq` (if from store)
  * `decision_age_ms` (optional)

### Telemetry to S8 (hard)

S6 must emit:

* `SERVE_STALE_POSTURE` (when staleness encountered)
* `SERVE_FALLBACK_FAILCLOSED` (whenever fallback is served)
* `INLINE_EVAL_TIMEOUT/FAILED/THROTTLED`
* `SCOPE_FALLBACK_USED` (RUN→MANIFEST→GLOBAL fallback)

This is critical to diagnose DL’s effect on the platform and to detect when DL is masking deeper issues.

---

## 10) Environment ladder posture for S6

### Must remain identical across envs

* freshness semantics and use of `decision_time_utc`
* precedence of S8 HealthGate
* fallback is FAIL_CLOSED (never optimistic)
* singleflight + deadline semantics if inline eval is enabled

### Allowed profile differences

* `inline_eval_enabled`
* default serving budget `max_wait_ms`
* max_decision_age (policy config)
* caching (if added) — but caching must not violate freshness rules

---

## 11) Drift tripwires for S6 (explicit don’ts)

S6 must **not**:

* use wall clock “now” as the decision boundary for freshness without explicit timestamps
* serve stale posture as if it were fresh
* silently switch scopes without stating it (fallback chain must be explicit)
* return “best effort NORMAL” when posture/policy is missing
* return a decision computed by S4 without committing it to S5 (S5 remains the single source)

---

## 12) Minimal S6 interfaces Codex should implement

Conceptually, S6 needs just:

* `GetDegradeDecision(scope_descriptor_or_key, decision_time_utc, budget_ms?) -> DegradeDecision`
* (optional internal) `TryInlineRefresh(scope_key, decision_time_utc, deadline) -> {ok/fail}`

Everything else composes around that.

---

If you’re happy with S6, the next node to illuminate is **S8 (Self-Health & Telemetry Plane)** because it’s the final “safety clamp” that guarantees DL cannot silently widen capabilities when its own internals are unhealthy.

---

Absolutely — we’ll open **S8 (Self-Health & Telemetry Plane)** and expose the machinery inside it. S8 is DL’s **internal safety governor**: it turns “module health facts” into a **monotone safety clamp** (HealthGate) and **rebuild orchestration**, so DL can *never* silently widen capabilities when it is blind/broken.

Everything below stays inside the network we already pinned (JI-09/10/11, IP-07, IL-07). No new edges. No change of authority boundaries.

---

# S8 Self-Health & Telemetry Plane

## 1) What S8 is responsible for

S8 is the sole internal authority for:

1. **Ingesting structured health facts** from S1–S7 (JI-09).
2. Maintaining **health state** (global + per scope) over time (not just point events).
3. Classifying DL into one of the pinned health states:

   * `HEALTHY`, `IMPAIRED`, `BLIND`, `BROKEN`
4. Emitting a **HealthGate** (JI-10) to S4/S6 that can **force FAIL_CLOSED** with absolute precedence.
5. Issuing **RebuildRequests** (JI-11) when repair is possible/required.
6. Emitting DL’s own observability (health metrics, clamp reasons, rebuild outcomes).

S8 does **not** decide degrade mode on normal inputs (S4 does). S8 only **overrides** via fail-safe clamp when DL cannot be trusted.

---

## 2) S8 internal subnetworks (inside S8)

* **S8-A Health Ingest & Normalizer**
  Consumes HealthEvents/HealthStats; normalizes them into a common internal format.

* **S8-B Health State Store**
  Tracks current state and evidence per `scope_key` and for `GLOBAL`.

* **S8-C Rule Engine / Classifier**
  Evaluates evidence → emits `dl_health_state` and reason codes (global and per-scope).

* **S8-D Gate Manager**
  Produces HealthGate objects (monotone; precedence rules; TTL; hold-down).

* **S8-E Rebuild Orchestrator**
  Singleflight rebuild triggers; dedup; backoff; “don’t storm the system.”

* **S8-F Time Sanity & Consistency Monitor**
  Detects clock skew / non-monotone time that would break staleness semantics.

* **S8-G Telemetry Exporter**
  Emits metrics/logs/traces and (optionally) control-plane “DL unhealthy” facts (visibility only).

Internal sketch:

```
S1..S7 --JI-09--> [S8-A] -> [S8-B] -> [S8-C] -> [S8-D] --JI-10--> (S4,S6)
                               |         |
                               |         +--> [S8-E] --JI-11--> (S4/S5)
                               |
                               +--> [S8-F] (time sanity)
                               |
                               +--> [S8-G] telemetry
```

---

## 3) What S8 ingests (JI-09), in “evidence” form

S8 does not ingest raw logs. It ingests **structured evidence** that modules already emit:

### Evidence primitives

* `HealthEvent(source_module, scope_key?, kind, severity, observed_at_utc, details)`
* `HealthStats(source_module, scope_key?, window_id, observed_at_utc, metrics[])`

### Evidence categories (minimum set S8 must understand)

**Inputs not trustworthy (→ BLIND):**

* Policy plane unavailable/invalid (S2): `POLICY_POINTER_UNAVAILABLE`, `POLICY_LOAD_FAILED`, `POLICY_INVALID`
* Required signals stale/missing/error beyond TTL (S1): `SIGNAL_STALE_REQUIRED`, `SIGNAL_BACKEND_UNREACHABLE`, `SIGNAL_SNAPSHOT_BUILD_FAILED`

**Serving/commit not trustworthy (→ BROKEN):**

* Posture store failures/corruption (S5): `POSTURE_STORE_READ_FAILED`, `POSTURE_STORE_WRITE_FAILED`, `POSTURE_RECORD_CORRUPT`
* Persistent CAS/lease conflicts (S3/S5): `LEASE_CONFLICT`, high `CAS_CONFLICT_RATE`
* Serving falling back excessively (S6): sustained `SERVE_FALLBACK_FAILCLOSED` due to store errors

**Visibility-only degradation (→ IMPAIRED):**

* Control publish backlog (S7): `CONTROL_PUBLISH_FAILED`, `CONTROL_OUTBOX_BACKLOG_HIGH`

**Time sanity failures (→ BLIND or BROKEN depending):**

* clock drift detected vs monotone constraints (S8-F)

---

## 4) S8’s internal state model (what it remembers)

S8 maintains two levels of state:

### A) GlobalHealthState

`GlobalHealthState{ state, since_utc, reasons[], evidence_counters, last_ok_utc }`

Global is used when a failure affects **all scopes** (e.g., policy unavailable).

### B) PerScopeHealthState

`ScopeHealthState{ scope_key, state, since_utc, reasons[], counters, last_ok_utc, hold_down_until_utc }`

This lets S8 clamp only a specific scope if needed (e.g., scope-specific signal series missing), without punishing unrelated scopes.

**Important:** S8’s state is **derived**. It can be held in memory and optionally checkpointed, but it must be safe if lost (loss just makes S8 conservative until evidence reappears).

---

## 5) The classifier (S8-C): how S8 decides HEALTHY / IMPAIRED / BLIND / BROKEN

### Primary rule: “monotone toward safety”

S8 can tighten immediately; it loosens only with explicit recovery evidence.

### Health state meanings (v0, pinned)

* **HEALTHY:** policy valid, required signals fresh, posture store readable/writable, no split-brain symptoms.
* **IMPAIRED:** DL still safe, but some non-critical surfaces degraded (e.g., control publish failing), or minor intermittent issues that don’t invalidate posture correctness.
* **BLIND:** DL cannot trust its **inputs** (policy/signals/time), so any posture it would compute is untrustworthy → must clamp FAIL_CLOSED.
* **BROKEN:** DL cannot reliably **serve/commit** posture (store corruption, persistent write/read failure, split-brain), so posture surface is untrustworthy → must clamp FAIL_CLOSED.

### Classification rules (designer-authoritative v0)

S8 computes state using **evidence thresholds over windows**, not single blips.

#### Enter BLIND if any are true (global or per scope):

1. `PolicyContext.status != OK` (and no last-known-good)
2. Any **required** signal for that scope is `STALE/MISSING/ERROR` beyond `max_signal_age` *for longer than a short grace period*
3. Time sanity failure that breaks staleness math (S8-F says time unreliable)

#### Enter BROKEN if any are true:

1. Posture store corruption detected for that scope (`POSTURE_RECORD_CORRUPT`)
2. Store read/write failures exceed threshold over window
3. Persistent CAS conflicts / lease churn indicates split-brain risk
4. Serving cannot obtain fresh posture and inline refresh repeatedly fails due to internal faults

#### Enter IMPAIRED if:

* Control publishing degraded (S7 backlog) OR
* transient non-required signal failures OR
* transient store slowness but still correct

#### HEALTHY requires:

* policy OK
* required signals OK (fresh)
* store OK
* lease/ownership stable (if HA enabled)

---

## 6) HealthGate output (JI-10): what S8 sends to S4/S6

### HealthGate (pinned shape)

`HealthGate{`

* `dl_health_state` (global or scoped)
* `forced_mode?` (present iff BLIND/BROKEN)
* `forced_mask?` (optional; usually implied by forced_mode)
* `reason_codes[]`
* `effective_at_utc`
* `ttl_until_utc` (optional)
* `scope_key?` (if scoped gate; else GLOBAL)
  `}`

### Precedence rules (hard)

1. If `forced_mode` present ⇒ **override** everything:

   * S6 serves forced FAIL_CLOSED immediately.
   * S4 yields forced FAIL_CLOSED (no eligibility evaluation).
2. Global gate applies unless a stricter per-scope gate exists.
3. Clearing a gate requires recovery evidence (below).

### Recovery evidence (hard, monotone)

S8 clears BLIND/BROKEN only when it observes, for the relevant scope/global:

* policy valid and loaded (or LKG active)
* required signals fresh/OK (within max age)
* store reads/writes OK (or a successful rebuild commit)
* no lease churn / split-brain indicators (if HA)

Additionally, S8 applies a **hold-down** (small quiet period) to avoid gate flapping.

---

## 7) Rebuild orchestration (JI-11): how S8 triggers repair without storms

S8 triggers rebuild because S5 is derived and because certain failures should be auto-repaired.

### RebuildRequest (pinned)

`RebuildRequest{ scope_key or scope_set, reason, urgency, deadline?, singleflight_key }`

### When S8 triggers rebuild (v0 set)

* `POSTURE_RECORD_CORRUPT` → rebuild that scope’s posture record
* `MISSING_POSTURE_FOR_HOT_SCOPE` (scope requested by DF) → seed posture
* `POLICY_REV_CHANGED` → priority converge scopes under new policy_rev
* Split-brain stabilized → rebuild after lease stability returns

### How S8 prevents rebuild storms

* **Singleflight per scope**: one rebuild in-flight per `scope_key`
* **Backoff per reason**: repeated failures slow down, not speed up
* **Priority lanes**:

  * PRIORITY: scopes actively requested by DF, global policy change convergence
  * BACKGROUND: periodic health repairs, long-tail scopes

### What a rebuild “means” internally (no new edges)

S8 does not rebuild itself; it triggers the existing chain:

* request S4 to evaluate (possibly under forced safe posture)
* S4 commits to S5
* success clears corruption/missing posture
* S6 can serve fresh posture again

If the store is globally broken, rebuild cannot complete; S8 keeps the fail-safe clamp active.

---

## 8) Time sanity monitor (S8-F): preventing hidden-time drift from breaking safety

S8-F watches for:

* non-monotone `decided_at_utc` regressions (per scope)
* huge discontinuities between snapshot times and serving decision_time
* impossible negative ages beyond tolerance

If time sanity is violated, S8 escalates to BLIND (or BROKEN if it looks like store corruption) because staleness logic becomes meaningless.

This is critical because DL’s safety relies on TTLs.

---

## 9) Telemetry exporter (S8-G): what must be visible in production

S8 must emit at minimum:

* current `dl_health_state` (global + per scope counts)
* forced FAIL_CLOSED clamp active (rate + duration + reason codes)
* rebuild attempts/success/failure by reason
* lease churn / CAS conflict rate (if HA)
* store read/write error rates
* required signal staleness rate
* serve fallback fail-closed rate (from S6)

This ensures operators can prove “DL is clamping because X,” and governance tuning can reason about stability.

---

## 10) Environment ladder posture for S8 (deployment pins)

### Must not change across envs

* state meanings (HEALTHY/IMPAIRED/BLIND/BROKEN)
* forced clamp semantics (BLIND/BROKEN ⇒ FAIL_CLOSED)
* monotone tightening and evidence-based recovery
* singleflight rebuild behavior

### Can vary by profile (operational envelope)

* evidence window lengths (how many seconds/minutes before escalating)
* thresholds (e.g., number of consecutive failures before BLIND)
* rebuild backoff parameters
* per-scope gating enabled/disabled (but semantics identical if enabled)

**Important:** These are **runtime safety profile knobs**, not ad hoc code forks. If you want them governed like policy, they can live in the same `PolicyContext` artifact under an `s8_guardrails` section (v0-friendly, minimal-doc).

---

## 11) Drift tripwires for S8 (explicit don’ts)

S8 must **not**:

* silently suppress errors (it must surface them and clamp safely)
* “clear gates” just because time passed (recovery must be evidence-based)
* require control-bus publishing for correctness (visibility only)
* make nuanced posture decisions beyond forced fail-safe (normal posture selection remains S4)

---

If you’re happy with S8, the only remaining node (optional) is **S7 Control Emission Plane**—and that one is deliberately last because it must never become correctness-critical.

---

Absolutely — we’ll open **S7 (Control Emission Plane)** and expose the machinery inside it. This is the optional “visibility + invalidation” lane: it publishes **posture-change facts** to `fp.bus.control.v1` and **must never become correctness-critical**.

Everything below is designer-authoritative for S7 and stays within the already-pinned network: it consumes **PostureChangedNotify (JI-08)** from S5 and emits envelope-valid control facts (optional outer edge). It also emits telemetry to S8 (JI-09).

---

# S7 Control Emission Plane

## 1) What S7 is responsible for

S7 is the sole internal authority for:

1. Turning **posture transitions** (as defined by S5 material change + `posture_seq`) into **control-plane facts**.
2. Ensuring publication is **idempotent**, **ordered per scope**, and **eventually visible** under retries.
3. Ensuring publishing is **non-blocking** to posture commits (S5 correctness must not depend on S7).
4. Maintaining a **bounded, durable “outbox”** or equivalent retry mechanism.
5. Emitting control-plane publishing telemetry to S8 (success/fail/backlog).

S7 does **not** decide posture, does **not** write posture state, and does **not** change DF behavior directly.

---

## 2) S7 internal subnetworks (inside S7)

* **S7-A Intake & Canonicalizer**
  Receives PostureChangedNotify from S5; canonicalizes event payload; assigns stable event_id.

* **S7-B Outbox Store Adapter**
  Reads pending publish items and marks them delivered (or advances status).

* **S7-C Publisher Adapter**
  Publishes to `fp.bus.control.v1` using canonical envelope shape.

* **S7-D Retry & Backoff Scheduler**
  Drives retries, prevents publish storms, enforces ordering.

* **S7-E Deduper / Idempotency Guard**
  Ensures “same posture transition → same event_id → safe retry.”

* **S7-F Telemetry Emitter**
  Sends publish failure/backlog metrics and events to S8.

Internal sketch:

```
(S5) JI-08 PostureChangedNotify
          |
          v
     [S7-A Canonicalize + event_id]
          |
          v
     [S7-B Outbox] <----> [S7-D Retry Scheduler]
          |
          v
     [S7-C Publisher] ---> fp.bus.control.v1
          |
          v
     [S7-F Telemetry] ---> S8
```

---

## 3) What S7 consumes (JI-08)

S7 consumes **only** what S5 emits, because S5 is the authority for “material change” and `posture_seq`.

### PostureChangedNotify (minimum fields)

* `scope_key`
* `posture_seq`
* `decided_at_utc`
* `policy_rev`
* `change_kind` (MODE_CHANGED / MASK_CHANGED / POLICY_REV_CHANGED / FORCED_FAILSAFE_ENTERED / EXITED)
* `new_decision_ref` (either full decision, or pointer/digest; v0 prefers full-ish summary)
* `prev_decision_ref?` (optional)
* `reason/triggers summary` (optional but recommended)

**Pin:** S7 must not recompute change detection or posture_seq.

---

## 4) What S7 emits (control-bus fact)

### Envelope requirement (hard)

If S7 publishes to `fp.bus.control.v1`, it **must** emit a canonical-envelope event.

Minimum envelope fields (from your schema):

* `event_id`
* `event_type`
* `ts_utc`
* `manifest_fingerprint` (required by envelope; see global handling below)
* optional pins: `run_id`, etc.
* `payload`

### Event taxonomy (designer-pinned)

* `event_type = dl.posture_changed.v1`

### Domain timestamp (hard)

* `ts_utc = decided_at_utc` (the posture decision’s domain time)
* `emitted_at_utc` can exist separately (producer clock)

### Payload contents (v0)

`payload` includes:

* `scope_key`
* `scope_kind` (GLOBAL/MANIFEST/RUN)
* `posture_seq`
* `mode`
* `capabilities_mask` (or a digest + subset; but v0 can carry full mask)
* `policy_rev` (+ digest)
* `change_kind`
* `triggers_summary` (compact)
* `served_as_of` fields if helpful (optional)

---

## 5) Stable identity, idempotency, and ordering (the core of S7)

### 5.1 Stable `event_id` (hard)

S7 must produce a deterministic event id for each posture transition:

* `event_id = hash(scope_key + "|" + posture_seq)` (or equivalent)

**Pin:** retries reuse the same event_id. Never mint new IDs on retry.

### 5.2 Ordering per scope (hard)

Partition key on the control bus must be derived from `scope_key`, ensuring:

* posture change events are ordered per scope (bus only guarantees per-partition order)

### 5.3 Deduplication posture

* Consumers dedupe on `event_id`.
* S7 ensures duplicates are harmless and expected.

---

## 6) Outbox/retry model (eventual visibility without correctness dependency)

### Why an outbox exists

We pinned: “a crash after commit must not silently lose the posture-change fact.”

So S7 must use an outbox-like mechanism where:

* S5 commit produces a durable pending publish item (or S7 persists it upon intake)
* S7 drains pending items until published

### Outbox item shape (conceptual)

* `outbox_key = (scope_key, posture_seq)`
* `event_id`
* `event_payload` (canonical envelope + payload)
* `status ∈ {PENDING, IN_FLIGHT, SENT, DEAD_LETTER}`
* `attempt_count`
* `next_attempt_at_utc`
* `last_error_code`

### Retry rules (pinned)

* Exponential backoff with jitter (implementation)
* Bounded max in-flight publishes
* Never reorder events within a scope:

  * if posture_seq=10 is pending, posture_seq=11 should not publish first for that scope

### Dead-letter posture (optional but realistic)

If publish fails for too long:

* mark as `DEAD_LETTER`
* emit CRITICAL telemetry to S8
* BUT: DL correctness remains unaffected (store + serving still works)

---

## 7) Global scope and envelope’s manifest_fingerprint requirement

Your canonical envelope requires `manifest_fingerprint`. For GLOBAL posture-change facts we must remain envelope-valid.

**Designer pin (consistent with earlier):**

* Global control events use a single sanctioned sentinel:

  * `manifest_fingerprint = 0000...0000` (64 hex zeros)
* Payload still carries `scope_kind=GLOBAL` and `scope_key=scope=GLOBAL`

No other module invents a different global encoding.

---

## 8) What S7 must emit to S8 (telemetry)

S7 emits HealthEvents/Stats (JI-09):

* `CONTROL_PUBLISH_FAILED` (with error codes)
* `CONTROL_OUTBOX_BACKLOG_HIGH` (oldest pending age, count)
* publish latency / success rate
* dead-letter count

**Pin:** These generally put DL into **IMPAIRED**, not BLIND/BROKEN, because S7 is visibility-only.

---

## 9) Environment ladder posture for S7

### Must not change across envs

* event type and envelope compliance
* stable event_id semantics
* ordering per scope
* outbox retry semantics (if enabled)

### Allowed per environment

* `dl.emit_control_events` (on/off)
* retention, topic config, broker addresses
* publish retry aggressiveness / batch sizes

**Important:** turning S7 off must not change DL correctness — only visibility/invalidation.

---

## 10) Drift tripwires for S7 (explicit don’ts)

S7 must **not**:

* block S5 commits or S6 serving
* become required for DF to function (no “DF listens to control bus for posture” as sole mechanism)
* publish non-envelope-shaped events
* mint new event_ids on retry
* reorder posture transitions within a scope
* decide “material change” itself (S5 owns that)

---

## 11) Minimal interfaces S7 needs (so Codex can implement cleanly)

S7 only needs:

* `EnqueuePostureChange(PostureChangedNotify)`
  (or consume from S5 outbox directly)

* `DrainAndPublish()` loop
  (pull pending, publish, mark sent, retry on failure)

That’s it.

---

## USER: PAUSE FOR REFLECTION

Absolutely. Here’s the “pause-and-hold” view — not new design, just a clean mental model of what we’ve built so we don’t lose the thread when implementation starts.

## What makes this vertex complex (in the *right* way)

DL isn’t complex because it has lots of features; it’s complex because it sits at the intersection of:

* **Safety authority** (one component decides what’s allowed)
* **Hot-path constraints** (DF must obey it per decision)
* **Replay/audit truth** (posture used must be reconstructible forever)
* **At-least-once + partial failure reality** (signals can go missing, stores can corrupt, instances can race)
* **Environment ladder discipline** (same semantics everywhere; only profiles differ)

So DL has to be “boringly deterministic” under chaos.

## The network, at a glance

### Outer network (platform graph)

* Inputs: **Signals + Policy Rev**
* Outputs: **DegradeDecision → DF (hard constraints)** + **Audit recording**
* Optional visibility: **control bus posture-change facts**
* Feedback loops: OFP/IEG/EB lag/model/action-risk/governance tuning

That alone forces deterministic posture, fail-closed behavior, and auditability.

### Inner network (DL’s internal graph)

We decomposed DL into 8 opaque-but-now-illuminated subnetworks that map cleanly to those obligations:

* **S1** makes a stable *SignalSnapshot* (explicit OK/STALE/MISSING/ERROR)
* **S2** makes an atomic *PolicyContext* (versioned + last-known-good)
* **S3** makes canonical *scope_key* + single-writer ownership
* **S4** is the *only* decision brain (eligibility + hysteresis + provenance)
* **S5** is the atomic posture spine (CAS + posture_seq + derived store)
* **S6** is the serving gate (freshness by decision boundary time; inline-refresh or FAIL_CLOSED)
* **S7** optionally publishes posture-change facts (idempotent outbox; visibility-only)
* **S8** is the self-trust governor (BLIND/BROKEN ⇒ forced FAIL_CLOSED; rebuild orchestration)

The key thing: **each join has exactly one owner**. That’s why it won’t drift.

## The “complexity budget” is spent on three necessary tensions

1. **Freshness vs availability**
   Serving must be fast; posture must be fresh. When it can’t be both, we clamp **FAIL_CLOSED** rather than guess.

2. **HA vs determinism**
   Multiple instances must not race. That’s why we have *two* guards:

   * S3 leases (role)
   * S5 CAS/seq (enforcement)

3. **Visibility vs correctness**
   Control events are useful, but they must never become required. That’s why S7 is optional and “outbox + idempotency” is for visibility only.

## The single most important drift-preventer we created

**Everything is explicit and timestamped:**

* snapshots have `snapshot_end_utc`
* decisions have `decided_at_utc`
* serving uses `decision_time_utc`
* staleness is computed, never implied
* policy rev is always cited

That’s what keeps replay/audit truthful and stops “hidden now()” bugs.

---

If you want one final “anchor line” before Codex starts:
**DL is a deterministic safety governor whose only job is to constrain DF explicitly, with rebuildable state and a monotone fail-closed clamp when it can’t trust its own inputs.**

---
