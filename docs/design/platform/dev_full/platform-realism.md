# Conversation about shifting from Runtime Certification to Stress Tests in search of Production Readiness

Pausing RC2 because “the platform can’t handle the data yet” was a **reasonable** call — but the fix isn’t “more random stress tests.” The fix is to run a **production-shaped performance + operability program** that ends in certification, not replaces it.

Stress testing is *part* of getting production-ready, but only when it’s tied to: **(a) a pinned workload envelope, (b) observability that locates bottlenecks, (c) a remediation loop, (d) a final scorecard + drill pack**.

Here’s what you need next, in the order a senior would do it.

---

## 1) Define the runtime envelope you’re certifying

Right now your RC2 floors are effectively “bank-scale,” but your platform is injecting ~5k events. That mismatch will always make it look like a toy.

You need two envelopes:

* **Dev_full operational envelope (RC2-S):** what you can realistically sustain now (still non-toy).
* **Stretch envelope (RC2-L):** the big numbers you grow into.

Production-ready doesn’t mean “max scale today.” It means: **meets stated SLOs under a stated envelope** + fails safely + recovers predictably.

---

## 2) Build bottleneck visibility before you “optimize”

You can’t tune what you can’t attribute. Before more load, ensure you have **end-to-end correlation + per-hop metrics**:

Minimum signals (must be attributable by component):

* IG: admit rate, reject/quarantine rate, p95/p99 latency, DDB hot partitions, throttles
* MSK: producer errors, consumer lag p95/p99
* Flink: checkpoint success/duration, backpressure, restart count, processing latency
* DB (Aurora): connection pool saturation, p95 query latency, deadlocks/timeouts
* Redis: hit rate, p95 latency
* Decision services: p95/p99 latency, error rate, queue depth
* Archive/audit: sink throughput, retry rate, backlog
* Cost: unit cost + idle burn

If those aren’t visible, stress tests just generate noise.

---

## 3) Create a real load generator (not “5k probe”)

Certification needs **steady/burst/soak** profiles that actually reach the envelope.

You need a repeatable “campaign generator” that can:

* produce steady for 15–30 min,
* burst 3–5× for a few minutes,
* soak for 30–60 min (dev_full), and
* generate a replay window big enough to prove correctness.

Also pin **where load is injected**:

* through **IG** (validates the truth boundary), or
* directly into **MSK** (validates hot path throughput).
  Both are legitimate, but they certify different things and must be labeled.

---

## 4) Run a structured bottleneck clearing loop (this is the core)

A senior does this iteratively:

1. **Baseline run** at RC2-S steady → capture scorecard snapshot
2. Identify top bottleneck (single biggest limiter)
3. Remediate (config, infra, placement, query/index, state sizing, parallelism)
4. Re-run baseline and prove improvement
5. Repeat until the bottleneck moves and you can hit the envelope consistently

This produces real evidence: “we improved throughput / reduced lag / reduced p99 / reduced cost” — which is exactly what senior engineers talk about.

---

## 5) Only then run “Operational Certification” (scorecard + drills)

Once the platform can sustain the RC2-S envelope:

* run **Scorecard Run** (steady→burst→recovery→soak) and freeze the metrics
* run the **Tier-0 drill pack** (rollback, replay integrity, lag recovery, schema evolution, dependency outage+degrade, audit drill, cost/idle-safe drill)

That’s what turns “it can handle data” into “it’s production-shaped and defensible.”

---

## 6) How this avoids “toy project” even before bank-scale

A toy project fails because it has no:

* explicit envelope,
* SLO posture,
* rollback/replay safety proofs,
* auditability,
* cost controls,
* or drill evidence.

If you can truthfully say:

> “Within envelope RC2-S, we meet SLOs, preserve replay correctness, can rollback, can audit decisions, and enforce cost guardrails”

…you are already far from toy, even if RC2-L is still a stretch target.

---

### What I’d want to see in your docs when you send them

To guide you fast, the most useful artifacts are:

1. **Bottleneck register** (what broke first, evidence, remediation, result)
2. **Load generator plan** (how you hit steady/burst/soak and where injected)
3. **Observability snapshot** (dashboards + key metrics you can actually read)
4. **Current RC2-S envelope proposal** (numbers you can afford and sustain)

If you’ve got those, we can immediately tell whether your stress testing is “senior-shaped progress” or just burning cycles.

You’re **in the right direction** — this is *not* “random stress testing,” it’s a **production-shaped hardening program** with the right senior signals: fail-closed gates, explicit evidence contracts, targeted reruns, cost envelopes, and a phase ladder that mirrors the build ladder.

### What you’re doing that’s *very* senior-shaped (keep this)

* **Stress-first as a program, not ad-hoc runs:** you explicitly pivoted to “stress harden first, certify after,” and made `platform.stress_test.md` the status owner. That’s how real teams avoid late-stage cert embarrassment.
* **Decision/Bottleneck pre-read (Stage A) + targeted reruns:** your M2/M3/M4/M5 execution shows the pattern “fail fast on deterministic drift, remediate the smallest thing, rerun only the failed window.” That’s exactly how you avoid wasting money/time.
* **Cost discipline is treated as a gate:** you’re producing cost receipts and even hardening Cost Explorer attribution in M6 addendum (A4R). That is a huge non-toy signal.
* **You correctly pivot at M7 to “data realism required”:** M7 explicitly blocks schema-only closure and requires subset profiling + skew/duplicate/out-of-order cohorts. That’s exactly what senior runtime engineers do.

### Where you’re still missing the mark (this is the part that can keep “toy vibes” alive)

You’re *hardening the platform correctly*, but the platform won’t feel “production-capable” until you close these gaps:

1. **Real throughput evidence is still the weak link.**
   A lot of your stress ladder (M2–M5) is control-plane correctness under probe pressure (good!), but “platform can handle the data that comes its way” will only be believable when you run **sustained** ingestion/streaming/decision windows at a declared envelope and show lag/latency distributions and recovery. Your own program acknowledges that M6/M7 are the phases where “no toy-profile closure” must be enforced.

2. **You still have explicit “HOLD_REMEDIATE” posture at the program level for M6/M7.**
   Even though you’ve executed a lot, your own authority file is honest that strict “non-toy revalidation” is still mandatory before you treat M8 as claimable. That’s the correct posture — but it means you’re not “done” yet on the runtime truth you want to sell.

3. **The Managed Flink vs EKS fallback split must be closed with fresh evidence.**
   Your M4 stress shows you had to repin to EKS fallback due to Managed Flink account gating at the time; if you now truly have Managed Flink authorization, the senior move is: **repin to Managed Flink and rerun the relevant stress/cert windows** so “target = evidence” is true.

4. **Oracle stream-sort still carries “waiver-backed observations”** in your stress record.
   That’s fine during a cycle, but you eventually need a **real, managed, repeatable stream-sort run** on a representative window with receipts/parity fully green (no “we deferred the heavy rerun”). Otherwise the “source-to-stream” entry story stays vulnerable.

### My honest senior verdict

**Yes, you’re on the right track.** The structure you’ve built is exactly how a senior would harden a platform without burning cash and without lying to themselves.
But to stop the “toy project” feeling, you now need to spend most of your effort on **data-plane operational evidence**, not more control-plane probing.

### The shortest “you’re now production-shaped” path from here

* **Define a dev_full operational envelope (RC2-S)** that you can actually sustain within budget (keep the huge numbers as a later RC2-L stretch).
* **Build a real load campaign generator** (not a 5k probe) and run steady→burst→recovery→soak through the hot path.
* **Execute the Tier-0 drill pack** (rollback, replay/backfill integrity, lag recovery, schema evolution, audit drill, cost/idle-safe drill) and publish those bundles as your “alive platform” proof.
* **Close the runtime placement gap** (Managed Flink vs fallback) with fresh rerun evidence.
* **Clear the remaining waiver debt** (especially stream-sort receipts/parity).

If you paste (or upload) the **current M6/M7 “strict non-toy” rerun evidence summary** you consider authoritative, I’ll tell you exactly whether you’re now at “RC3-ready” (alive platform) or what single blocker is still keeping you from that claim.


You’re **right** that throughput/speed matters — but what I meant by “data-plane operational evidence vs control-plane probing” is this:

## What “control-plane probing” is

These are checks that prove **wiring, readiness, and contracts**, but **not** that the platform can *carry real volume end-to-end*.

Examples from your subphase plans:

* **Oracle boundary readiness** (read-only law, manifests readable, contract checks) — that’s correctness of the *boundary*, not runtime throughput. 
* **IG health/auth/envelope checks** (200/202 health, auth matrix, “413 payload too large”, throttles present) — that proves the edge is fail-closed, but doesn’t prove it can sustain your target EPS. 
* **READY publication correctness** (SFN authority, dedupe/ambiguity closure, receipt readback) — this proves your control messages are correct under retries, not that the hot path can process banking-like load. 

These are **necessary**, and your runbooks for them are excellent. But if you spend *most* of your cycles here, you can still end up with a platform that is “perfectly wired” but slow.

## What “data-plane operational evidence” is

This is evidence that **real volumes of real events** move through the system and the **hot path stays within declared limits**, including recovery and correctness under failure modes.

It includes:

* **Sustained steady load + burst load** (not 5k events) with **measured**:

  * consumer lag (p95/p99),
  * checkpoint health,
  * error/timeout rates,
  * end-to-end processing latency,
  * and recovery time back to stable.
* **Realistic cohorts** (duplicates, out-of-order, hotkey skew, payload size spikes) and proving invariants still hold.
* **Replay window integrity** (replay doesn’t double-write or corrupt state).
* **Cost per unit** under those loads (not just “we have cost receipts”).

Your own stress plans already *encode* this distinction:

* **M6.P6** is explicitly data-plane: it requires non-zero run-window progression, then steady/burst windows, lag thresholds, ambiguity closure, and overhead budgets. 
* **M6.P7** is data-plane: it’s currently `HOLD_REMEDIATE` specifically because historical/proxy closure isn’t accepted as “production-grade”; it demands fresh run-scoped commit evidence and reopens on “toy-profile” authority. 
* **M7.P8** is data-plane realism: it pins minimum sample sizes and explicit duplicate/out-of-order/hotkey targets, and it reopens on “waived_low_sample / advisory throughput.” 
* Same idea in **M7.P9** and **M7.P10**: they explicitly require representative cohorts and they only become “non-toy” once strict reruns close B13.

So you’re not “doing the wrong thing.” You’re doing **both** — but the “toy project” feeling persists when the program spends too much time proving that *switches and wiring work* (control-plane), and not enough time proving that *the conveyor belt moves fast enough under real load* (data-plane).

## The key point about throughput (this is the part that matters)

Throughput isn’t proven by “we have probes” — it’s proven by **a load campaign** that:

1. injects enough events to generate real distributions, and
2. exercises the actual bottlenecks (IG throttles, MSK throughput, Flink parallelism/checkpoints, Aurora/Redis saturation), and
3. produces a scorecard snapshot that you can compare between remediations.

Here’s a concrete example from your own docs:

* You’ve pinned IG throttles at **RPS=200 / Burst=400** in the envelope conformance checks. That’s a control-plane proof. 
* But if your runtime throughput target is 500 eps+ through IG, the data-plane run will *immediately* reveal you can’t physically hit it without changing those throttles (or injecting downstream). That’s the kind of “bottleneck discovery” control-plane probes can’t give you.

## So what should you do *now*?

Keep the control-plane stages as **preflight** (cheap, quick, fail-closed), but put your main effort into closing the **data-plane strict reruns** that your own plans mark as “non-toy enforcement”:

* **M6.P7 strict fresh rerun** (resolve B12: no historical/proxy closure authority). 
* **M7.P8 strict non-waived throughput rerun** (resolve B13 with real sample sizes/cohorts). 
* Continue the strict posture you already achieved for P9/P10 (that’s exactly the right direction).

That’s what makes the platform feel “production-shaped”: **real volumes, real cohorts, real lag/latency distributions, and proven recovery**, not just correct readiness gates.

If you want, paste your current **authoritative stress status summary** for M6.P7 and M7.P8 (the latest verdict + blockers), and I’ll tell you exactly which single missing proof is still keeping “non-toy” closed.

---

That’s a solid plan — and it’s exactly how a senior would sequence it:

1. **Finish control-plane / wiring stress** so you flush out hidden infra/handle/IAM/networking issues cheaply, and you don’t confuse “data-plane bottleneck” with “wiring broke.”
2. Then switch to **data-plane operational evidence** (steady/burst/soak + cohorts + drills) with confidence that failures are *real throughput/semantics issues*, not hidden plumbing.

A couple of guardrails so you don’t accidentally over-invest in control-plane probing:

### Keep the “wiring stress” scope tight

Use it to prove only these are stable:

* **Oracle boundary readiness** (read-only + stream_view availability)
* **IG boundary correctness** (auth/envelope/idempotency receipts)
* **Bus reachability** (MSK topics + IAM)
* **Flink app health / checkpoint wiring**
* **State stores reachable** (Aurora/Redis)
* **Evidence sinks writable** (S3 evidence/archive + parity/readback)
* **Teardown/idle-safe works**

Once those are consistently green, stop. Don’t try to “hit banking EPS” inside the wiring phase — that’s the data-plane phase.

### When you send the docs, include these 5 things (so we can move fast)

1. **Latest stress_test master status** (the file that is the status owner)
2. **Per-phase verdict summaries** (M2–M7 at least): verdict + blockers + what changed
3. **A single “wiring is now stable” receipt** you want to treat as the baseline
4. **Current runtime placement** (Managed Flink vs fallback, plus any repins you made)
5. **Your intended first data-plane envelope** (even rough: steady eps, burst multiplier, soak duration)

Then we’ll do what you want: treat wiring as settled, and focus on the **data realism phase**:

* data semantics realization (subset profiling)
* identifying the true hot-path bottlenecks
* deciding what belongs in IEG/feature projections
* archive/audit routing at real volume
* learning windows + label maturity realism
* and the dashboards/monitoring baselines that make sense for your actual data

So yes: **finish the wiring stress quickly, then we switch to data-plane with no guessing.**

---

Nice — that’s a clean cut.

Choosing to stop at **M1–M13 wiring stress** and pivot into **data realism** is totally defensible *as long as* we treat M14/M15 as “replaced by a data realism program” rather than “skipped.” In other words: we still need the outputs those phases were meant to guarantee (time-causal learning, meaningful IEG/entity choices, monitoring baselines), but we’ll get them via the data realism work instead of the formal M14/M15 gates.

### What I need from you next (minimal, so we don’t stall)

To move fast and avoid guessing, send:

1. **The final wiring stress summary doc** (the top-level status owner / rollup).
2. **Implementation notes** for the wiring stress (or the “authoritative latest” notes).
3. The **one “baseline run id”** you consider the stable reference (the run you trust).

With those, I’ll do two things in one pass:

* confirm you truly have “wiring stable” (no hidden infra blockers), and
* extract the *wiring invariants* we’ll assume while doing data realism (so we don’t re-litigate infrastructure).

### What the data realism phase should look like (so it replaces M14/M15 properly)

This is the senior-shaped program:

**A) Data Semantics Profile (small window first)**

* Pick a tight window (e.g., 24h or 7d) from the live stream tables.
* Measure:

  * key coverage/joinability (flow_id / entity keys)
  * duplicates and out-of-order rate
  * hot-key skew (top 0.1% keys)
  * null/missingness spikes
  * label availability + maturity distributions
  * “is this data meaningful or random?” sanity checks

**B) RTDL/IEG realism decisions**

* From the profiling, decide:

  * which entity relationships are real and stable enough to project
  * what the “minimum useful graph” is for IEG
  * which projections belong in Flink vs state store vs offline build

**C) Learning realism**

* Build one time-causal dataset:

  * as-of cutoff
  * label maturity cutoff
  * leakage guardrail checks
* Train/eval one baseline model (doesn’t need to be “best” yet)
* Produce a monitoring baseline: score distribution, drift candidates, fraud rate proxy, etc.

**D) Operational scorecard and drill integration**

* Use the same window to run a small steady/burst/recovery profile and capture:

  * lag p95/p99, checkpoint health
  * decision latency distribution
  * cost per unit
* This ties data realism back to your Tier-0 proof model.

### One important note (so you don’t accidentally re-create “toy vibes”)

Data realism is not “EDA for fun.” It’s **EDA with decisions**:

* every finding either becomes a pinned assumption, a contract, or a change request
* you end with: “we now know how to model entities, how to generate features, and what to monitor”

If you upload the wiring stress rollup + impl notes next, we’ll lock your “wiring stable” baseline and then design your first **data realism window** and the exact questions it must answer.

---

Yes — it’s the same overall path, just **one layer deeper** and sequenced now that you’ve finished wiring stress.

How they line up:

* **My “data realism phase” = the missing prerequisite that makes RC2-S meaningful.**
  It answers: *what’s in the data, what joins work, what cohorts exist (dupes/out-of-order/skew), what labels look like, what to monitor*. That’s what stops you from certifying “a platform that ran” rather than “a platform that ran on realistic data.”

* **RC2-S (dev_full operational envelope)** is still step 1 of “production-shaped,” but you should set its envelope using what you learn from the data realism window (so the envelope isn’t arbitrary).

* **Real load campaign generator + steady→burst→recovery→soak** is still the core of “data-plane operational evidence.”
  The difference is: you’ll now generate campaigns based on real observed distributions and cohorts, not just synthetic probes.

* **Tier-0 drill pack** is unchanged — it’s still the “non-toy proof” layer.

* **Close runtime placement gap (Managed Flink vs fallback)** is still required if it’s not already closed.

* **Clear waiver debt (especially stream-sort receipts/parity)** remains required; data realism will likely surface if stream-sort layout/partitioning needs adjustment.

So: your quoted list is the **operational certification program**, and what I just described is the **data semantics + realism program that feeds it**. They’re complementary, not conflicting.

---

Yep — this is exactly the sequencing you want, and your docs now **prove** you’ve flushed out most “hidden wiring” problems *before* doing serious data-plane work.

### 1) Where you actually are now (based on the files)

* **M6:** the strict rerun chain is closed and the parent rerun is green; it ends with `verdict=GO` and `next_gate=M7_READY` (after a targeted handoff readback fix).
* **M7:** strict “non-toy” closure is green and the parent emits `verdict=GO` / `next_gate=M8_READY` with the data-realism machinery (subset/profile, cohort stress, integrated windows).
* **M8–M13:** all show `S5_GREEN` / deterministic handoffs through learning, promotion/rollback, final verdict + teardown/idle-safe + cost guardrails.

So: your “wiring stress” effort *did* its job — you’ve got a stable platform spine and governance corridor to build on.

---

### 2) What I meant by “data-plane operational evidence vs control-plane probing”

You’re correct that you probe to ensure speed/throughput — **but not all probing actually tests throughput.**

**Control-plane probing** = proving the *platform can start and stay correct*:

* handles resolve, IAM works, Step Functions commits READY correctly, IG enforces auth/envelope, evidence is publish/readback safe, teardown works, etc.
  This prevents hidden wiring bugs from being mistaken as throughput issues.

Your M6/M8 docs have tons of this (authority gates, readback proofs, deterministic rollups, locality/source-authority guards).

**Data-plane operational evidence** = proving the *conveyor belt moves fast enough under realistic cohorts*:

* sustained **steady → burst → recovery → soak** windows
* measured **lag p95/p99**, checkpoint health, error rates, end-to-end latency distributions
* **semantic** correctness under duplicates/out-of-order/hotkeys/replay windows
* before/after bottleneck fixes with comparable profiles

Your M7 stress plan is explicitly doing this: it forces a run-scoped subset/profile, cohort stress (normal mix + edge cohorts), integrated windows, and blocks “waived_low_sample / advisory-only” closure. 

So when I said “focus more on data-plane evidence,” I meant:

* don’t spend most cycles re-checking readiness gates once they’re stable
* spend cycles running *real campaigns* and using the resulting metrics to find/clear bottlenecks

---

### 3) The one remaining risk (and how to avoid “guessing”)

Even with wiring stable, you can still get “toy vibes” if the **load campaign is too small** or doesn’t reflect your actual data’s cohort mix.

The good news: your M7 plan already anticipates this and requires:

* a **24h profile window**
* **min sample events**
* explicit duplicate/out-of-order/hotkey targets and cohort windows 

So you’ve built the right guardrail: *don’t certify on tiny probes.*

---

### 4) What to do next (your “data realism phase”)

Given you’re skipping M14/M15 formally, treat “data realism” as a replacement program that produces the same outcomes:

1. **Real subset extraction + profiling (week/day window)**

   * joinability/coverage of keys you care about for IEG
   * skew/hotkeys, duplicates, out-of-order rates (measured, not assumed)
   * label availability and maturity distribution (for time-causal learning)

2. **IEG decisions based on observed data**

   * what entity nodes/edges are actually meaningful and stable
   * what gets projected in RTDL vs persisted in stores

3. **Operational load campaign based on that subset**

   * steady/burst/soak using the real cohort mix (plus injected cohorts where needed)
   * measure lag/latency/cost per unit and clear bottlenecks

4. **Only then resume runtime certification / scorecard**

   * now your RC2-style thresholds are based on reality, not speculation

---

If you want one crisp confirmation: **you’re no longer “guessing”** about wiring — your strict M6→M13 chain has already forced deterministic handoffs, readback proofs, cost receipts, and replay/leakage guardrails. Now the productive work is to make the platform “alive” on realistic data and load profiles.

---

Here’s how I’d run the **data realism phase** in a senior, production-shaped way — and the specific things to watch for in **each data-reliant plane** (Oracle → stream-sort → IG/MSK/Flink → IEG/OFP → DF/AL/DLA → Case/Labels → OFS/MF/MPR), plus platform-wide hazards.

The goal isn’t “do some EDA.” The goal is to produce **pinned, evidence-backed decisions** that make your runtime + learning behave correctly on real content: correct ordering, correct joins, bounded state, meaningful entity graph, sensible monitoring baselines, and time-causal learning (no future Oracle).

---

## 0) What “data realism” should produce (deliverables)

You’ll know you’re doing the right thing if you end with a **Data Realism Pack** containing:

1. **Reality Profile** (per table + per join): nulls, duplicates, skew, key coverage, out-of-order rates, payload sizes, cardinalities, label maturity distribution
2. **Pinned Decisions** that update platform behavior:

   * IEG entity nodes/edges and TTLs
   * stream ordering + watermarks/allowed lateness
   * partition keys for MSK, Flink parallelism targets
   * archive routing and partitioning scheme
   * monitoring baselines + alert thresholds
3. **Load Campaign Spec** derived from real cohorts (steady/burst/soak + “evil cohorts”: duplicates, out-of-order, hot keys)
4. **Learning Window Spec** (as-of + maturity) and a first baseline feature set that is demonstrably time-causal

That pack becomes the foundation for your operational certification runs.

---

## 1) Start with a slice window (don’t boil the ocean)

Pick a **small but representative** window:

* **24 hours** if you want speed
* **7 days** if you want stability (recommended)
* Include at least one “busier” period (if traffic varies by time of day)

**Watch out for:** choosing a window that’s too quiet; it will hide skew, duplicates, and backlog behavior.

**Output:** `window_charter.json`

* start/end, expected row counts (rough), and which tables are included.

---

## 2) Live stream content sanity (what comes in “as a live stream”)

For each live stream table (arrival/events/entities/anchors), compute:

### A) Time behavior

* Distribution of `ts_utc` (min/max, gaps, outliers)
* Out-of-order rate: how often an event arrives with `ts_utc` < prior event time (by key and globally)
* Time granularity: seconds/millis? (very common to assume wrong)

**Watch out for:**

* timestamps that are not actually monotonic per key, even if they look monotonic globally
* weird bursts of identical timestamps (forces tie-break keys)

### B) Duplicate semantics

* Duplicate rate on your intended dedupe key(s)
* “Near duplicates”: same key but different payloads (hash mismatch)
* Collision risks (two distinct real events sharing a key)

**Watch out for:**

* “dedupe key” that works in theory but collides in practice
* duplicates concentrated in a small subset (retry storms)

### C) Key coverage + stability

For every key you *think* you’ll use (flow_id, entity_id, account_id, device_id, merchant_id, etc.):

* % of rows with the key present (coverage)
* cardinality per day and churn rate (how often new IDs appear)
* “fanout”: average number of events per key (skew indicator)

**Watch out for:**

* low coverage keys (break IEG/feature joins)
* extreme skew (one merchant_id or device_id dominating)

---

## 3) Entity graph realism (IEG) — how to choose what to store

IEG should be driven by **observed joinability and stability**, not by what sounds cool.

### The senior way to decide IEG nodes/edges

1. Define candidate nodes: user/account/payment instrument/device/ip/merchant/terminal/flow/session (whatever your data actually has).
2. Define candidate edges from actual columns (e.g., device→account, ip→device, merchant→terminal).
3. Measure for each edge:

   * edge coverage (% events that can form the edge)
   * edge stability (does it flip often? collisions?)
   * connected component size distribution (do you get “mega-components”?)
   * degree distribution (hot nodes)

**Watch out for:**

* “mega-node” entities (e.g., one IP or merchant connecting everything) that blow up graph usefulness
* edges that are too noisy (device_id changes per event, etc.)
* state blow-up: graph features that require unbounded history in Flink state

**Outcome decisions you want to pin:**

* the **minimum viable entity graph** (only edges that are stable + useful)
* state TTLs (how long you keep edges in RTDL state)
* which parts are computed in Flink vs stored in Aurora/Redis vs computed offline

---

## 4) Stream processing realism (MSK + Flink RTDL)

Your RTDL “production-ness” will live or die on these:

### A) Partitioning and skew

* Identify which key you should partition by (to distribute load): flow_id often works; entity_id might skew
* Measure “top 0.1% keys” share of volume
* Decide if you need:

  * key salting for hot keys,
  * separate topics for different event types,
  * or per-merchant partitions

**Watch out for:**
one hot key causing a single partition to become the bottleneck → lag spikes → missed SLO.

### B) Watermarks / allowed lateness

You need an explicit stance:

* allowed lateness (seconds/minutes)
* what happens when late events arrive (drop, side output, reprocess window)

**Watch out for:**
global sorting assumptions. In production you don’t “sort the stream”; you do **event-time windows** + watermarks.

### C) State and checkpoints

Measure or estimate:

* state size growth (per key)
* checkpoint duration and failure rates
* backpressure indicators

**Watch out for:**
state blow-up from joins that expand cardinality (entity join fanouts).

---

## 5) Archive + audit routing realism (how truth gets to offline storage)

This is not “write everything everywhere.” It’s about **timely, partitioned, queryable truth**.

### What to decide

* Which streams/topics must be persisted (raw admitted events, derived projections, decisions, audit events)
* S3 layout:

  * partition by `event_date/hour`
  * file sizing targets (avoid tiny files)
* If using MSK Connect sinks, decide rotation/flush behavior and error handling.

**Watch out for:**

* tiny-file explosion (kills Athena/Glue/Databricks performance)
* backpressure from sinks (archive writer slowing hot path)
* missing correlation context in archived records (breaks audit drill later)

---

## 6) Decision semantics and explainability (DF/AL/DLA)

You don’t need SHAP on day one, but you do need **reasonability**.

### A) Reason codes first

Define “reason codes” that are grounded in observed fields:

* velocity anomalies
* unusual device/IP reuse
* merchant outliers
* amount anomalies relative to historical quantiles (as-of)

**Watch out for:**
storing reasons that aren’t derivable from real available fields at decision time.

### B) Audit record completeness

Verify that for a sample of decisions you can reconstruct:

* input event id + timestamps
* model/version used
* key features used (or feature set id)
* reason codes
* action taken

**Watch out for:**
audit logs that are “technically written” but missing the fields you’ll need for the audit drill.

---

## 7) Learning/Evolution realism (OFS/MF/MPR) — what matters before fancy features

This is where “toy project” often shows up, so keep it disciplined:

### A) Time-causal dataset build (non-negotiable)

For each training window:

* enforce `event_ts <= as_of_time`
* enforce `label_available_ts <= as_of_time - maturity_lag`
* prove no “future rows” entered the dataset (hard check report)

**Watch out for:**
labels whose timestamp is event time, not availability time. For leakage prevention, maturity should use “when label becomes knowable.”

### B) Baseline features that always work

Start with a small baseline feature set that is:

* available at inference time
* stable under missingness
* cheap enough to compute in RTDL/OFS

Then you can evolve.

### C) Monitoring baselines

From real distributions, define:

* prediction score distribution baseline
* data drift candidates (key distributions that move)
* label-based metrics latency (how long until you can compute precision/recall)

**Watch out for:**
invented thresholds. Baselines must come from the reality profile.

---

## 8) Platform-wide watch-outs (things that break “production feel”)

These are the common traps:

1. **Misattributing bottlenecks**
   If your observability can’t localize “IG vs MSK vs Flink vs Aurora,” you’ll tune blindly.

2. **Certifying on tiny samples**
   You already fought this. Keep enforcing minimum sample size and distribution reporting (p50/p95/p99).

3. **Skew and hotspots**
   One hot key can dominate everything. You need explicit skew handling policy.

4. **Schema says one thing, content does another**
   Null spikes, weird cardinalities, inconsistent key semantics — treat these as first-class findings.

5. **Leaky learning**
   The “no future Oracle access” rule must be proven on real windows with evidence, not assumed.

---

## 9) How to sequence it (tight and efficient)

A senior sequence that avoids rework:

1. **Reality profile (24h/7d)** → find assumption breakers
2. **Pin IEG/RTDL decisions** (edges, keys, watermarks, TTLs)
3. **Pin archive layout** (partitioning + file sizing)
4. **Build one time-causal OFS dataset** → train one baseline model
5. **Define monitoring baselines** from real distributions
6. **Derive your first load campaign** (steady/burst/soak + cohorts)
7. Only then run your operational certification runs

If you want, tell me which window you’re choosing first (24h or 7d), and I’ll give you a concrete checklist of the exact metrics to compute per table and the exact cohort definitions (dupe/out-of-order/hotkey) that should become your “campaign generator” inputs.

---

Great — a **24-hour window** is the right first move. It’s small enough to run cheaply, but big enough to surface the “assumption breakers” (skew, duplicates, out-of-order, missing keys, label maturity weirdness) that make platforms feel toy-ish.

Below is a **senior-style 24h Data Realism playbook** that is explicitly grounded in your Data Engine interface rules: traffic vs context vs truth roles, the dual-stream policy, the binding join map, and the time-safety constraints (“no future Oracle”). 

---

## 1) Pin the 24h window the way production does

Pick one 24h window and pin it as the **single source of truth** for this phase.

### What to pin

* **World identity:** `manifest_fingerprint`, `seed`, `scenario_id` (and `parameter_hash` if needed).
* **Window:** `start_ts_utc`, `end_ts_utc` (24h).
* **For learning:** `as_of_time_utc` (usually `end_ts_utc`) and `maturity_lag` (days/hours).

### What to watch out for

* Don’t choose a window that’s too “quiet.” If you can, pick a day with higher volume.
* Treat this window as **repeatable**: you will rerun it after remediation to prove improvements.

---

## 2) Choose the correct tables for the window (by role)

This is where your interface doc is extremely helpful: it tells you what is allowed to behave like traffic and what must never be treated as traffic. 

### A) Runtime traffic (what WSP should emit)

* **behavioural_streams** only:

  * `s2_event_stream_baseline_6B`
  * `s3_event_stream_with_fraud_6B` 

### B) Runtime join context (RTDL-eligible context surfaces)

* `s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B`
* `arrival_events_5B`
* `s1_arrival_entities_6B` 

### C) Batch-only (not RTDL-safe)

* `s1_session_index_6B` (contains session_end_utc / arrival_count → implies future aggregation) 

### D) Offline truth products (learning / evaluation only; never live decisions)

* `s4_event_labels_6B`
* `s4_flow_truth_labels_6B`
* `s4_flow_bank_view_6B`
* `s4_case_timeline_6B` 

**Watch out for:** accidentally “helping” the runtime with truth tables (even indirectly). Your rule forbids it, and your interface doc explicitly marks truth products as offline. 

---

## 3) Build a “Reality Profile” for each table (content, not schema)

For each table in the 24h window, compute the same basic profile so you can compare apples-to-apples.

### Minimum profile metrics (per table)

**Volume & time**

* row count
* min/max `ts_utc` (or derived time)
* distinct counts of core keys (flow_id, merchant_id, etc.)

**Nulls/missingness**

* % missing for each join key and candidate entity key

**Duplicates**

* duplicate rate on the table’s natural key (or intended dedupe key)

**Skew**

* top 0.1% keys share of total rows (for flow_id, merchant_id, entity_id candidates)
* max events per key

**Out-of-order**

* for event streams: violations where `ts_utc` decreases when ordered by `event_seq` within a flow (or where `event_seq` itself is non-monotonic)

### What to watch out for

* **Join keys not actually present at high coverage** (IEG and OFP will suffer).
* **Extreme skew** (one merchant_id/flow_id dominating) → this breaks partitioning and makes Flink state explode.
* **Duplicate “identity” keys** where payload differs → forces you to decide whether to quarantine, dedupe, or accept as retried event.

---

## 4) Build the “Join Coverage Matrix” (this drives IEG/OFP feasibility)

Your interface doc already pins the join map. In this phase you test whether the joins are *actually good* in real content. 

### Mandatory joins to validate (for the 24h window)

1. **Event stream → Flow anchor**

* `s3_event_stream_with_fraud_6B` ↔ `s3_flow_anchor_with_fraud_6B`
  keys: `seed, manifest_fingerprint, scenario_id, flow_id` 

2. **Flow anchor → Arrival skeleton**

* `s3_flow_anchor_with_fraud_6B` ↔ `arrival_events_5B`
  keys: `seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq` 

3. **Arrival skeleton → Entity attachments**

* `arrival_events_5B` ↔ `s1_arrival_entities_6B`
  keys: `seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq` 

4. **Truth products → Traffic (learning only)**

* `s4_event_labels_6B` ↔ `s3_event_stream_with_fraud_6B`
  keys: `seed, manifest_fingerprint, scenario_id, flow_id, event_seq` 

### For each join, compute:

* **unmatched rate** (left keys missing on right)
* **fanout** (1→many explosions)
* **duplicate key rate** on both sides
* **join stability**: do you see key collisions?

### What to watch out for

* A join that is “valid by schema” but unmatched by content → RTDL will be full of nulls.
* Fanout joins that turn one event into 20+ context rows → state and cost blow up.
* High unmatched rates on truth joins → labels aren’t usable yet; maturity policy needs adjusting.

---

## 5) Derive RTDL “time-safe allowlist” from the data, not guesswork

Your interface doc already gives the rule: some surfaces/fields imply future knowledge and are batch-only. 

### What you produce in this step

A small “RTDL allowlist” artifact:

* **Allowed datasets** (arrival_events, arrival_entities, flow_anchor)
* **Forbidden datasets** (session_index, all `s4_*` truth)
* **Field-level forbidden list**: anything like session_end, arrival_count, post-hoc labels, future aggregates

### What to watch out for

Fields that “look harmless” but encode future aggregation (counts over a session, end timestamps, “final” flags). These must be blocked from RTDL even if the table itself is used. 

---

## 6) Decide the IEG content based on observed entities (not theory)

IEG should reflect what your data actually provides.

### Process (senior way)

1. Enumerate candidate entity IDs present in `s1_arrival_entities_6B` and flow anchors (device-like, account-like, user-like, merchant-like, IP-like).
2. For each candidate:

   * coverage (% events with this ID)
   * churn (new IDs/day)
   * reuse (events per ID)
   * collision risk (same ID associated with many unrelated flows)
3. Choose a **minimum viable entity graph**:

   * nodes: only those with high coverage + stable behavior
   * edges: only those with good join coverage and manageable fanout

### What to watch out for

* “Mega nodes” (one ID connects everything) → destroys graph usefulness and blows up state.
* IDs that change too frequently → poor entity stability → noisy features.
* Edges that require scanning Oracle per event → forbidden by your platform join posture (“joins occur inside platform using projections; do not scan Oracle per event”). 

---

## 7) Archive/audit routing: decide what must be persisted and how

This is where you ensure the platform is explainable and reconstructable later.

### What to decide from the 24h window

* Which streams must be persisted: admitted events, decisions, audit events, key projections (minimum set)
* S3 layout for archive:

  * partition by `event_date/hour`
  * target file sizes (avoid tiny files)
* Whether sinks backpressure the hot path

### What to watch out for

* Tiny file explosions (makes Athena/Glue/Databricks slow).
* Archival sinks slowing the hot path (a production killer).
* Missing correlation IDs in archived records (breaks audit drill).

---

## 8) Learning/Evolution: do one time-causal dataset build + baseline model

You do **not** need “best model” here. You need proof that the learning loop is real and leakage-safe.

### What to do in the 24h pass

* Define `as_of_time_utc` = end of window
* Define `label_maturity_cutoff` = `as_of_time_utc - maturity_lag`
* Build one dataset where:

  * `event_ts <= as_of_time`
  * `label_available_ts <= maturity_cutoff` (or nearest equivalent you have)
* Run a baseline train/eval:

  * produce eval report
  * produce lineage/provenance
  * produce a monitoring baseline (score distribution, feature missingness, label rate)

### What to watch out for

* Labels keyed to **event time** rather than **availability time** → causes leakage unless maturity is defined correctly.
* Very low label coverage within 24h → you may need a longer label window even if event window is 24h (that’s normal in fraud).

---

## 9) Convert the 24h findings into the first real load campaign

This is the “anti-toy” pivot: use real distributions to define steady/burst/cohort tests.

### From the 24h profile, derive:

* steady eps target that’s realistic for dev_full
* burst multiplier based on observed spikes
* “evil cohorts” you must include:

  * duplicates %
  * out-of-order rate
  * hot key prevalence
  * oversize payload rate

### What to watch out for

* certifying on a cohort mix that is too “clean” (everything looks great until real skew shows up).

---

## What you should do next (concrete)

If you want the fastest path:

1. Pick the exact 24h window start/end (UTC).
2. Run the **Reality Profile** + **Join Coverage Matrix** first.
3. Only then decide:

   * IEG minimal graph
   * RTDL allowlist
   * learning maturity lag
   * load campaign envelope

If you tell me **which date** you want for the 24h window and whether you’re profiling **baseline (s2) only**, **fraud overlay (s3) only**, or **both**, I can give you a very concrete checklist of the exact computations to run per table and per join (including the key definitions from the interface). 

---

Cool — a **7-day window** is where this stops feeling like “EDA” and starts feeling like **production readiness work**, because you’ll see:

* weekly seasonality and key churn (IDs appear/disappear)
* meaningful skew/hot keys (the stuff that kills RTDL)
* label maturity reality (how delayed “truth” really is)
* whether your IEG graph is stable or turns into a mega-component mess

Below is how I’d run the **7d data realism phase** in a senior way, and what to watch for across the whole platform.

---

## 1) First pin what “7d window” means (you need two clocks)

For the platform, the 7d window isn’t one thing — it’s two related windows:

### A) Runtime window (traffic + context)

This is the **event-time window** you want to simulate as “what happened in the world.”

Use only the RTDL-safe tables:

* behavioural traffic streams (`s2_event_stream_baseline_6B`, `s3_event_stream_with_fraud_6B`)
* RTDL join context (`s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B`, `arrival_events_5B`, `s1_arrival_entities_6B`)

### B) Learning “as-of” window (delayed supervision)

Learning is time-causal and must not access “future Oracle.” That means you choose:

* `as_of_time_utc` (often end of the 7d runtime window)
* `maturity_lag` (so labels must satisfy `label_ts <= as_of_time - maturity_lag`)

**Watch out:** if maturity lag is large, you may only have usable labels for the *earlier* part of the 7 days. That’s fine and realistic, but you must measure it and accept it.

---

## 2) Confirm the “allowed vs forbidden” surfaces (don’t leak truth)

Your interface doc already gives you the biggest landmine: some data is explicitly **batch-only** because it implies “future aggregation.”

* **Do NOT use `s1_session_index_6B` in RTDL** (contains session_end_utc / arrival_count, so it encodes future state). 
* **Do NOT use any `s4_*` truth products in runtime** (labels/bank view/case timeline are offline-only). 

This isn’t optional. It’s the main difference between “production-shaped” and “leaky toy.”

---

## 3) Build the 7d “Reality Profile” (per table)

For each table in the 7d window, compute these:

### A) Time behavior (critical for stream-sort + Flink windows)

* min/max `ts_utc`
* timestamp granularity (seconds vs ms)
* gap distribution (periods of no events)
* outlier spikes (sudden surges)
* “same timestamp” density (how often many events share exact `ts_utc` → you need stable tie-break keys)

**Watch out:** a stream can be “time sorted” and still be useless if 50% of records share identical timestamps and you don’t have a deterministic secondary key.

### B) Key coverage (this drives join success)

For each key you expect to use:

* % present / % null
* distinct count
* churn (new IDs per day)
* fanout (events per key)

**Watch out:** a key can exist in schema and still be missing in 30% of real rows → your IEG/OFP projections become sparse and noisy.

### C) Duplicates and near-duplicates

* duplicate rate on natural keys (e.g., `flow_id,event_seq` for event stream; `merchant_id,arrival_seq` for arrival tables)
* near-duplicates: same key, different payload hash
* distribution of duplicates (uniform vs concentrated in hot keys)

**Watch out:** if duplicates concentrate around hot keys, they become both a correctness risk and a throughput killer (idempotency store pressure).

### D) Skew (the RTDL killer)

* top 0.1% keys share of total volume (flow_id, merchant_id, device-like IDs, etc.)
* max rows per key
* gini-like unevenness (even rough) to decide partitioning strategy

**Watch out:** one hot merchant_id or flow_id dominating partitions causes lag spikes regardless of overall EPS.

---

## 4) Build the Join Coverage Matrix (this decides if RTDL is “real”)

Your interface doc pins the join map. The 7d job is to measure if those joins are healthy. 

### Mandatory join validations (7d)

1. `s3_event_stream_with_fraud_6B` ↔ `s3_flow_anchor_with_fraud_6B`
   Keys: `seed, manifest_fingerprint, scenario_id, flow_id` 

2. `s3_flow_anchor_with_fraud_6B` ↔ `arrival_events_5B`
   Keys: `seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq` 

3. `arrival_events_5B` ↔ `s1_arrival_entities_6B`
   Keys: `seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq` 

4. Learning-only: `s4_event_labels_6B` ↔ `s3_event_stream_with_fraud_6B`
   Keys: `seed, manifest_fingerprint, scenario_id, flow_id, event_seq` 

For each join compute:

* unmatched rate (left rows with no right match)
* fanout explosion (1→many)
* duplicate key rate on both sides
* stability (do collisions occur?)

**Watch out:** fanout joins that explode cardinality are where Flink state blows up and Aurora gets hammered.

---

## 5) IEG realism: choose the graph from observed entity behavior

Don’t design IEG first. **Measure it first.**

### What you do in 7d

From `s1_arrival_entities_6B`:

* enumerate candidate entity IDs (device-like, account-like, user-like, IP-like, etc.)
* compute for each:

  * coverage (% events with ID)
  * reuse (events per ID)
  * churn (new IDs/day)
  * “mega-node risk” (IDs linking too many flows/accounts)

From that, decide:

* minimum viable node set
* edge set that’s stable + high-coverage
* TTL policy for edges/state (how long to retain links)

**Watch out:** mega-nodes (e.g., one IP linking huge portions) make the “graph” less meaningful and more expensive.

---

## 6) RTDL compute realism (MSK + Flink): partitioning, watermarks, state

Your 7d analysis should tell you:

### A) Best partition key choice

* which key gives best distribution (flow_id often better than merchant_id, but you must measure)
* whether hot keys exist → do you need salting or special handling?

### B) Watermarks and allowed lateness

A real stream is never perfectly ordered. Decide:

* allowed lateness (seconds/minutes)
* what happens to late events (drop, side output, reprocess later)

**Watch out:** trying to “globally sort the stream” is a trap. Production systems use event-time windows + watermarks.

### C) State sizing

Measure/estimate:

* average and p99 state per key
* checkpoint duration and failure probability under load
* backpressure triggers

**Watch out:** state blow-up is the most common “it can’t handle data” failure mode, not raw CPU.

---

## 7) Archive/Audit routing realism (so it’s explainable and doesn’t choke hot path)

From the 7d window estimate:

* bytes/day per topic class (traffic, decision, audit)
* file sizing targets (avoid tiny files)
* partitioning strategy (event_date/hour)
* sink backlog risk (is archive writing slowing the hot path?)

**Watch out:** tiny file explosion and backpressure from sinks. If archive writing hurts SLO, you need buffering/connector tuning.

---

## 8) Learning realism on 7d (time-causal + “do we have labels?”)

This is where the 7d window really helps.

### A) Label maturity distribution

For truth tables (`s4_*`) compute:

* label availability (what % of events get labels)
* label latency distribution (how delayed truth is)
* choose a maturity lag (p50/p90, depending on how strict you want)

**Watch out:** if labels are sparse within 7d, you’ll need:

* either a longer window for labels,
* or accept that the labelled subset is earlier within the window.

### B) Build one dataset and train one baseline

Goal isn’t “best model.” Goal is to prove:

* time-causal dataset build works
* training/eval works
* eval reports are interpretable
* monitoring baselines exist (score distribution, feature missingness, drift candidates)

---

## 9) Convert 7d findings into a real load campaign (this kills toy vibes)

Once you have:

* real event rate distribution
* skew profile
* duplicate/out-of-order rates
* payload size distribution

…you can generate a load campaign that is not arbitrary:

* steady profile based on typical rate
* burst multiplier based on observed spikes
* cohort injection that matches real “evil cohorts”
* replay window sized to prove correctness invariants

**Watch out:** certifying on “clean cohorts” makes everything look good until reality hits.

---

# Practical recommendation for running the 7d window without blowing budget

Split execution into two modes:

### Mode 1: Batch profiling (cheap, fast)

Use Athena/Databricks/Spark to compute profiles and joins without streaming everything.

### Mode 2: Streaming simulation (targeted)

Don’t try to stream all 7d end-to-end unless you have very high EPS. Instead:

* stream representative segments (e.g., 2× 2-hour peak slices + 2× 2-hour quiet slices)
* plus injected cohorts (duplicates/out-of-order/hotkeys)

This gives “production behavior” without requiring you to push ~7 days of raw events through WSP in real time.

---

## What I need from you to make this concrete

Pick one of these:

1. The exact **start/end UTC** for the 7d window you want, or
2. Tell me “pick a mid-range week” and I’ll propose a reasonable default based on your Jan–Apr timeline.

And tell me whether you want to profile:

* **fraud overlay (s3)** only (recommended), or
* both baseline (s2) and fraud overlay (s3).

Then I’ll give you the exact “checklist run” for the 7d window: the precise metrics to compute per table and per join, and the cohort definitions to use in the first real load campaign.
