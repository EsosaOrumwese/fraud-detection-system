# 1) Purpose & scope (closed world)

The Data Engine is a **single, governed generator** that turns a normalised **merchant snapshot** plus **public, version-pinned priors** into a **replayable transaction universe** with realistic geography, civil time, arrivals, and fraud behaviour. There is **no external enrichment and no external labels**: the engine is the only source of **events and outcomes**. All consumers treat the engine’s products as the **source of truth** and refuse to read anything that lacks a passing validation bundle (**“no PASS, no read”**). 

# 2) Contract authority & governance (what makes it safe)

* **Single source of truth for schemas:** JSON-Schema is authoritative; Avro, if needed downstream, is generated and never treated as source. Every dataset in the registry/dictionary uses **`schema_ref:` JSON Pointer anchors** to those schemas.
* **Run sealing:** before any draw, the engine fixes the **parameter set** and the **manifest fingerprint** (artefact digests + commit). Those anchors ride with every dataset/log so any row can be reproduced byte-for-byte later. 
* **RNG & replay contract:** counter-based **Philox** with strict **open-interval U(0,1)** mapping; every RNG **event** embeds counters and measured budgets (`draws` are actual uniforms; `blocks = after−before`). A cumulative **trace** row is appended **immediately** after each event; ordering is defined by counters, **not** file order. 

# 3) Inputs, authority surfaces, outputs (the public face)

* **Inputs (read-mostly):** the normalised **merchant snapshot**; policy/parameter sheets (e.g., hurdle/NB/Dirichlet/α-ledgers); and **public priors** (spatial, tz polygons, etc.), all version-pinned and hashed into the manifest. 
* **Authority surfaces (tables others never re-derive):**
  • Outlet catalogue keyed by `(merchant_id, legal_country_iso, site_order)`; **order across countries lives elsewhere**. 
  • **Inter-country order** via `s3_candidate_set.candidate_rank` (total, contiguous; **home=0**). 
  • Civil-time surfaces (tz polygons/overrides; DST timetables) and routing weights. 
* **Outputs (write-mostly):**
  • The **transaction stream** (later layers) with lineage and provenance.
  • RNG **event logs** + **trace** that make replay provable. 
  • **Validation bundle** with a PASS flag; consumers must check it before reading. 

# 4) How the engine builds the world (the four cooperating sections)

## A) Merchant-Location Realism (foundation)

Transforms each `merchant_id` into a **network of outlets, countries, zones, coordinates, and routing weights**—deterministically and auditably.

* **Counts & cross-border universe:** multi vs single (hurdle); domestic **N** via NB (Γ→Π attempts, then a **non-consuming** final that **echoes the parameters bit-for-bit**); admissible foreign set + **order of record** via `candidate_rank` (S3). 
* **Target foreign count (logs-only):** a ZTP sampler fixes **`K_target`** and logs **attempts/markers/finaliser**; S4 **never** chooses countries or encodes order; **realisation happens later** as `min(K_target, A)`.
* **Civil time & overrides:** tz polygon mapping with governed **override YAML**; DST gap/fold rules precomputed so every UTC event maps bijectively to civil time. 
* **Non-goals (authority boundaries):** inter-country order resides **only** in S3; outlet egress order is `["merchant_id","legal_country_iso","site_order"]`.

## B) Arrival engine (tempo & burstiness)

Generates realistic **inter-arrival times** at outlets using a **hierarchical Log-Gaussian Cox Process (LGCP)**: deterministic seasonality in local civil time plus OU volatility tuned to hit **Fano corridors** (e.g., CP ≈1.5; CNP ≈2–3). Holiday/flash-sale pulses are deterministic bumps in the mean surface. 

## C) Fraud cascades (campaign dynamics)

Fraud is **not** post-hoc thinning. It is a **coupled Hawkes process** that rides the same clock as legitimate traffic (baseline `p(t)·λᴸ(t)` + self-exciting kernel), with controlled cross-merchant mutation to create **campaign shadows** investigators expect. The engine therefore produces **labels** and **delayed outcomes** from first principles inside the closed world.

## D) Validation & governance harness (gates everywhere)

A multistage, deterministic battery runs on each build:

* **Structural physics:** legal tz mapping/DST; bijective local↔UTC conversion. 
* **Distributional corridors:** counts vs hurdle/NB bootstraps; dispersion indices for legitimate and fraud streams; zone-share ribbons. 
* **Adversarial indistinguishability:** keep AUROC under a ceiling (e.g., ≤0.55) against a signed baseline. **No PASS, no read.** 

# 5) Runtime model (how it actually runs)

1. **Seal the run** (schemas, parameters, artefacts → `parameter_hash`, `manifest_fingerprint`).
2. **Emit** deterministic authority surfaces (S3 order, civil-time tables), then **simulate** arrivals and fraud couched in local civil time.
3. **Log envelopes & trace** for every random action; **file order is non-authoritative**—counters are the truth. 
4. **Write** the validation bundle and PASS flag; only then are authority tables/streams considered readable. 

# 6) Observability & ops (what we watch)

* **Engine health:** event throughput; RNG **budget identities** (draws vs blocks); resume idempotence; seed/parameter hash mismatches. 
* **Realism KPIs:** Fano corridors, cross-zone “barcode” slope, campaign shadow statistics, AUROC ceiling. 
* **Governance:** licence digests, schema-ref coverage, “no AVSC in registry” rule. 

# 7) Evolution without drift (how we change it safely)

* **Schema evolution:** JSON-Schema only; narrow changes are additive/nullable; breaking changes are staged, and **egress ordering** is re-affirmed. 
* **Authority boundaries stay fixed:** inter-country order = `candidate_rank`; outlet egress order = `(merchant_id, legal_country_iso, site_order)`; S4 fixes **K_target** only.

# 8) Data Engine — Concept Map (ASCII, concept-only)

```
                                   DATA ENGINE — SEALED, GOVERNED GENERATOR
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CROSS-CUTTING RAILS:  JSON-Schema authority · run sealing (parameter_set + manifest_fingerprint)         │
│ RNG envelopes + immediate trace · counters define order · validation gates (NO PASS → NO READ)           │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘

    Inputs (read-mostly)                    Cooperating Sections                             Outputs (write-mostly)
┌───────────────────────────┐      ┌───────────────────────────────────────────┐      ┌───────────────────────────────┐
│ Merchant snapshot         │      │ A) MERCHANT-LOCATION REALISM (foundation) │      │ Transaction stream (with      │
│ Policy/parameter sheets   │      │  • Counts: hurdle → NB (Γ→Π) + non-cons.  │      │ lineage + scenario markers)   │
│ Public priors (spatial,   │      │    final that echoes parameters           │      ├───────────────────────────────┤
│ tz polygons, etc.)        │      │  • Cross-border admissible set +          │      │ RNG EVENT LOGS + TRACE        │
└──────────────┬────────────┘      │    inter-country order via candidate_rank │      │ (counters, budgets, adjacency)│
               │                   │  • Civil time legality (tz/overrides/DST) │      ├───────────────────────────────┤
               │                   ├───────────────────────────────────────────┤      │ AUTHORITY SURFACES (read-only)│
               │                   │ B) ARRIVAL ENGINE (tempo & burstiness)    │      │ • Outlet catalogue (within-   │
               │                   │  • Local-time seasonality + variability   │      │   country order)              │
               │                   ├───────────────────────────────────────────┤      │ • Inter-country order (rank)  │
               │                   │ C) FRAUD CASCADES (campaign dynamics)     │      │ • Civil-time tables/overrides │
               │                   │  • Coupled processes on same clock        │      ├───────────────────────────────┤
               │                   ├───────────────────────────────────────────┤      │ VALIDATION BUNDLE + PASS FLAG │
               │                   │ D) VALIDATION HARNESS (gates everywhere)  │      │ (gate for downstream readers) │
               │                   │  • Structural · distributional · adv.     │      └───────────────────────────────┘
               │                   └───────────────────────────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ RUN SEALING  │  (fix parameter_set + manifest_fingerprint; freeze schemas/priors; start counters at truth)
        └─────┬────────┘
              │
              ▼
        [Simulate world on the sealed map & clock; envelope every event; append immediate cumulative trace]
              │
              ▼
        [Publish validation bundle; PASS → surfaces/streams readable; otherwise closed]
```

---

**In one paragraph:** The Data Engine is a closed-world, contract-driven generator that **seals a run**, materialises a **geographically and civil-time correct** merchant world, drives **LGCP arrivals** and **Hawkes fraud cascades** against that world, and proves realism with a deterministic validation harness. Every stochastic step is **enveloped, traced, and replayable**; every consumer reads **only after PASS**; and authority boundaries (schemas, order, time) are explicit so nothing downstream can “helpfully” re-derive them. This is the foundation your enterprise stack can trust.

