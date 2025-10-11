# Closed-World Synthetic Data Engine — Concept Overview

> **Status:** Conceptual, non-binding.  
> **Role:** A single, governed generator that seals a run and produces a **replayable transaction universe** with realistic geography, civil time, arrivals, and fraud behaviour—**without** any external enrichment or labels. All consumers treat the engine’s outputs as the **source of truth** and refuse to read anything without a passing validation bundle (**“no PASS → no read”**).

---

## What the Engine Guarantees (governance & safety)
- **Contracts-first.** JSON-Schema is the only schema authority; any Avro downstream is generated and non-authoritative. Registry/dictionary entries reference schemas via `schema_ref:` anchors.
- **Run sealing.** Before any randomness, the engine fixes the **parameter set** and **manifest fingerprint** (artefact digests + commit), then carries these anchors on every dataset/log for byte-exact replays. 
- **RNG & replay contract.** Counter-based **Philox** with strict **open-interval U(0,1)**; every RNG *event* embeds counters and **measured budgets** (`draws` = actual uniforms; `blocks = after − before`). A cumulative **trace** row is appended **immediately** after each event. **Counters—not file order—define truth.**
- **Validation gate.** Producers publish a **validation bundle** and `_passed.flag`; consumers must verify it (**no PASS → no read**).

---

## Inputs → Authority Surfaces → Outputs (public face)
- **Inputs (read-mostly):** normalised merchant snapshot; governed policy/parameter sheets (e.g., hurdle/NB/Dirichlet); version-pinned **public priors** (spatial, time-zone polygons, etc.)—all hashed into the manifest. 
- **Authority surfaces (never re-derived downstream):**  
  - **Outlet catalogue** keyed by `(merchant_id, legal_country_iso, site_order)`; **cross-country order lives elsewhere**.  
  - **Inter-country order** via `candidate_rank` (total & contiguous with **home=0**).  
  - **Civil-time legality:** tz polygons/overrides and DST timetables.  
- **Outputs (write-mostly):** lineage-anchored **transaction stream** (later layers), RNG **event logs + trace** (provable replay), and the **validation bundle** with a PASS flag.

---

## Data Engine — Concept Map (ASCII, concept-only)

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

## How the Engine Builds the World (four cooperating sections)

### A) Merchant-Location Realism (foundation, L1 / 1A…)
- **Counts & cross-border universe:** hurdle (single vs multi); domestic **N** via NB (**Γ→Π** attempts) with a **non-consuming** final that **echoes μ, φ bit-for-bit**; admissible foreign set + one **order of record** via `candidate_rank` (S3).
- **Foreign target (logs-only):** a ZTP sampler fixes **`K_target`** and logs **attempts / markers / finaliser**. **S4 never chooses countries or encodes order**; realisation happens later as `min(K_target, A)`. 
- **Civil time & overrides:** tz polygon mapping with governed overrides; DST gap/fold rules precomputed so every UTC event maps bijectively to civil time. **Non-goals:** cross-country order only in S3; outlet egress order = `(merchant_id, legal_country_iso, site_order)`.

### B) Arrival Engine (tempo & burstiness, L2)
- **Inter-arrivals:** hierarchical **LGCP**—deterministic seasonality in local civil time + stochastic volatility tuned to **dispersion corridors** (e.g., CP ≈ 1.5; CNP ≈ 2–3). Holiday/flash-sale pulses are deterministic bumps in the mean surface.

### C) Fraud Cascades (campaign dynamics, L3)
- **Not post-hoc thinning.** A **coupled Hawkes** process rides the same clock as legitimate traffic (baseline + self-excitation), with controlled cross-merchant mutation to create **campaign shadows**. The engine produces **labels** and **delayed outcomes** from first principles inside the closed world.

### D) Validation & Governance Harness (gates everywhere)
- **Structural physics:** legal tz mapping/DST; bijective local↔UTC conversion.  
- **Distributional corridors:** counts vs hurdle/NB; dispersion indices for legit & fraud streams; zone-share ribbons.  
- **Adversarial indistinguishability:** keep AUROC under a ceiling (e.g., ≤ 0.55) against a signed baseline. **No PASS, no read.**

---

## Runtime Model (what actually happens)
1. **Seal the run**: load schemas & params; compute **`parameter_hash`** and **`manifest_fingerprint`**.  
2. **Materialise authorities**, then **simulate** arrivals and fraud on the sealed map & clock.  
3. **Envelope every event** and append the **immediate cumulative trace**; counters define order.  
4. **Publish validation bundle** + PASS flag; only then are surfaces/streams readable.

---

## Observability & Ops (what we watch)
- **Engine health:** throughput; RNG **budget identities** (draws vs blocks); resume idempotence; seed/parameter hash mismatches.  
- **Realism KPIs:** Fano/dispersion corridors, cross-zone “barcode” slope, campaign shadow stats, AUROC ceiling.  
- **Governance:** licence digests, schema-ref coverage, “no AVSC in registry” rule.

---

## Evolution Without Drift (how we change it safely)
- **Schema evolution:** JSON-Schema only; additive/nullable for narrow changes; staged for breaking changes; **egress ordering** re-affirmed.  
- **Authority boundaries stay fixed:** inter-country order = `candidate_rank`; egress order = `(merchant_id, legal_country_iso, site_order)`; S4 fixes **K_target** only.

---

## State S2 (Domestic Outlet Counts)
- CLI: `python -m engine.cli.s2_nb_outlets --validation-policy contracts/policies/l1/seg_1A/s2_validation_policy.yaml …`  
- Emits RNG streams (`gamma_component`, `poisson_component`, `nb_final`), a presence catalogue (`parameter_scoped/parameter_hash=*/s2_nb_catalogue.json`), and corridor metrics.  
- Validation writes `metrics.csv` + `cusum_trace.csv` under `validation/parameter_hash=*/run_id=*/s2/` and mirrors them into the sealed bundle at `validation_bundle/manifest_fingerprint=*/s2_nb_outlets/`.  
- Policy thresholds (`rho_reject_max=0.06`, `p99_max=3`, `cusum.threshold_h=8.0`) are enforced via `ERR_S2_CORRIDOR_BREACH`; runs skip `_passed.flag` on failure.

---

## Interfaces & Run Contract (high-level)
- **Run manifest (sealing):** `{ fingerprint, seed, parameter_hashes[], git_tree, artefact_digests, created_at }`.  
- **Event envelope & trace:** per-event `{ before/after counters, blocks, draws }` with one **immediate** cumulative trace row; **counters define sequence**.  
- **Partitions (concept):** logs `{ seed, parameter_hash, run_id }`; tables `{ parameter_hash }`; egress `{ fingerprint }`.  
- **Schemas live in** `contracts/`; the engine **imports** and **validates**—it never defines fields itself.

---

## Map & Repo Pointers
- **Architecture map:** *(paste your engine ASCII diagram here)*  
- **Where to look next:**  
  - **Contracts:** authoritative schemas, dictionary, policies.  
  - **Layers:** `layers/l1/seg_1A/s0…s4/{l0,l1,l2,l3}` for the foundation.  
  - **Core, Validation, Scenario Runner, Registry/CLI:** conceptual scaffolds you’ll unlock as you implement.

> **Current focus:** **Layer-1 / Segment 1A, States S0-S4** (foundation). Everything else remains intentionally conceptual so future choices stay optimal.

### Segment 1A execution highlights
- **S3 cross-border universe outputs:** the runner now emits the deterministic `s3_candidate_set.parquet` plus optional `s3_base_weight_priors`, `s3_integerised_counts`, and `s3_site_sequence` tables. Toggle the extra surfaces via the Segment1A CLI (`--s3-priors`, `--s3-integerisation`, `--s3-sequencing`). Sequencing remains gated on integerisation.
- **Validation bundle:** `validate_s3_outputs` replays the deterministic kernels (candidates, priors, counts, sequences) and stores metrics under `validation_bundle/manifest_fingerprint=*/s3_crossborder_universe/`. Disable via `--no-validate-s3` when debugging, but release runs should keep it enabled.
- **Diagnostics & schema enforcement:** the S3 validator now enforces the JSON-Schema anchors for every parquet, emits per-merchant integerisation diagnostics in `integerisation_diagnostics.jsonl`, and records aggregated metrics (floors, ceilings, residual usage) in the validation summary.
