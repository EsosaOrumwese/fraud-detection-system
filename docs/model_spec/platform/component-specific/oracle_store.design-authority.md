# Oracle Store Design Authority

## A) What Oracle Store is (and is not)

Let’s lock the *concept* first, before we touch layout, seals, evidence, or env ladder.

### A1) What Oracle Store **is**

**Oracle Store is the sealed “outside-world ledger” for a synthetic world**: a by-ref artifact boundary that holds **engine-materialized world truth** (traffic tables + truth products + audit evidence + gate proofs) in an **immutable, addressable, reproducible** form.

Mentally: it’s the “universe” that exists outside the bank. The bank doesn’t *compute* it; it can only *observe* it through controlled interfaces.

**Core capabilities (conceptual, not implementation):**

* **Write-once world materializations** (immutability is the defining feature).
* **Addressability by locator + digest** (so reads are explicit and reproducible).
* **Sealing/readability contract** (so partial worlds don’t leak into runs).
* **By-ref consumption** (SR/WSP/etc. reference artifacts; they don’t “own” them).

**Position in the network (important):**

* Oracle Store is **not on the runtime fact-flow path**.
* Runtime flow remains: `SR (READY + run_facts_view) → WSP → IG → EB → …` 
* Oracle Store is the by-ref world source that SR and WSP *point at*; it never emits events itself.

### A2) What Oracle Store **owns** (authority boundary)

In v0 design authority, Oracle Store *owns* the following laws:

1. **Immutability law**

* Once a world materialization is sealed, it is never overwritten or mutated in place.

2. **Readability law**

* A world partition is either **READABLE** or **NOT READABLE** based on the sealing contract (not on “it looks mostly there”).

3. **Addressing law**

* Consumers read only via **explicit locators** (and digests when required).
* Oracle Store is not a “browseable catalogue” for downstream.

4. **Layout law**

* Oracle Store defines the environment-ladder **root/prefix family** for these artifacts (physical store may vary, but logical layout tokens cannot drift).

### A3) What Oracle Store **is not**

This is where drift usually starts—so I’ll be blunt.

Oracle Store is **not**:

* **Not a producer**
  It does not push facts, does not write to EB, does not “stream time.”

* **Not SR**
  It does not define run readiness, does not publish READY, does not decide what run is active. 

* **Not IG**
  It does not admit/duplicate/quarantine. It does not mint receipts. (Consumers decide outcomes.) 

* **Not a query service**
  No “give me all transactions for January” API. If you want queries later, that’s a *separate* projection layer (OFS, analytics store, etc.).

* **Not a “latest finder”**
  Absolutely no “scan for newest world/run.” The only entrypoint is SR’s join surface. 

* **Not a mutable datastore**
  No upserts, no compactions that change meaning, no “patching” worlds after sealing.

### A4) Critical conceptual clarification (so we don’t accidentally key it wrong)

Oracle Store holds **engine worlds**, not **platform runs**.

* A single engine world materialization can be **reused across many platform runs** (different `run_id`s), without changing bytes.
* Therefore: Oracle Store must not be mentally (or physically) organized as “run_id folders,” except maybe for *derived* convenience indexes elsewhere.

This is the key to keeping “oracle outside the bank” true.

### A5) The “only legal interaction” rule (high-level)

Even at the concept level, we should pin the access posture:

* Downstream components never “go to Oracle Store and find data.”
* They go to **SR’s `run_facts_view`**, which references oracle artifacts by locator (and required evidence).
* WSP then reads those locators to reveal `business_traffic` as a stream.
* IG pull mode (if it exists) uses the same locators; still no scanning.

---

## Minimal A-section pins (v0)

If we want a crisp “A is done” state, these are the v0 pins:

1. Oracle Store = **sealed, immutable by-ref world boundary**, not a runtime vertex.
2. Oracle Store never streams; **WSP streams**.
3. Oracle Store never decides admission/quarantine; **IG does**.
4. Oracle Store is never scanned by downstream; **SR join surface is the only entrypoint**. 
5. Oracle Store stores **engine worlds**, not “runs.”

---

## B) Identity: what key truly names an oracle world

This is the **drift-killer** section. If we get identity wrong, you end up with “worlds” keyed by `run_id`, accidental overwrites, or “latest scan” behavior.

### B1) First, separate the identities we keep mixing

**1) Platform Run Identity (bank’s operational run)**

* Platform rail says **ContextPins** include `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` and are used to join run-scoped things. 
* `run_id` here is *correlation + operational scope*.

**2) Engine World Realisation Identity (oracle world you are “observing”)**

* Engine invocation requires `{manifest_fingerprint, parameter_hash, seed, run_id, scenario_binding}`. 
* But critically: `run_id` “may partition logs/events but MUST NOT change bytes of outputs whose identity does not include run_id.”
  That means `run_id` is **not** part of the world’s deterministic identity for the sealed world outputs.

**3) Output/Artifact Identity (each dataset/log file)**

* Engine’s own promise is: output identity is defined by its **partition tokens** as declared in `engine_outputs.catalogue.yaml`, and those partitions are write-once/immutable.
* Some outputs are seed+scenario+manifest scoped (e.g., `arrival_events_5B`), others include `parameter_hash`, and run-scoped logs include `run_id`.
* Portable addressing is via `EngineOutputLocator` which carries `output_id`, resolved `path`, and relevant identity partitions (optional, output-dependent). 

**Key takeaway:** Oracle Store must support *all three*, but must not let them collapse into “run_id folders = worlds”.

---

### B2) The Oracle Store “world key” we should pin (v0 authority)

Because we want “the outside world” to be reusable across different platform runs:

**Authority Declaration (v0): OracleWorldKey = Engine invocation identity minus `run_id`.**

So, in canonical token form:

* **OracleWorldKey** = `{manifest_fingerprint, parameter_hash, scenario_id, seed}`
  (i.e., the “realisation” of a scenario + seed under a governed parameter pack and world fingerprint).

And we explicitly pin:

* **`run_id` is NOT part of OracleWorldKey**. It’s an execution correlation id that may appear only in **run-scoped engine outputs** (logs/audit traces).

Why this is coherent with what you’ve built:

* Engine determinism promise is “identity partition ⇒ byte-identical outputs” and `run_id` must not change bytes unless the output scope includes `run_id`.

---

### B3) What about outputs that don’t include all four tokens?

This is where implementers get confused, so we pin the distinction:

**Authority Declaration (v0):**

* **OracleWorldKey** is a *run/world selection key* used by SR/WSP reasoning and reuse decisions.
* **OracleArtifactKey** is **per output** and is exactly:
  `OracleArtifactKey = (output_id + the output’s partition tokens as declared in engine_outputs.catalogue.yaml)`

So:

* Some artifacts will be keyed by `{manifest_fingerprint}` only (validation bundles, sealed inputs).
* Some by `{seed, manifest_fingerprint, scenario_id}` (e.g., `arrival_events_5B`). 
* Some by `{seed, manifest_fingerprint, parameter_hash, scenario_id}` (many Layer-3 surfaces).
* Some logs by `{seed, parameter_hash, run_id}` (rng logs).

Oracle Store **doesn’t invent a new identity system**—it adopts the catalogue scopes for artifacts, while using OracleWorldKey for “world grouping / reuse”.

---

### B4) Scenario identity: `scenario_id` vs `scenario_binding`

Engine invocation supports `scenario_binding` as either a single `scenario_id` or an explicit `scenario_set`. 

**Authority Declaration (v0): OracleWorldKey uses a single `scenario_id` token.**

* If you later want multi-scenario bindings, we add a *normalized binding id* concept deliberately; we do not “half support” scenario_set in Oracle Store identity.

This keeps Oracle Store aligned with existing output scopes that use `scenario_id` partitions.

(We can keep “scenario_set” as an explicit open decision, but the v0 key should be single-scenario.)

---

### B5) The “reuse law” (how SR/WSP should think about identity)

Once OracleWorldKey is pinned, the platform gets a clean reuse posture:

* **SR may reuse** an already-sealed oracle world materialisation if OracleWorldKey matches and required gate evidence exists; it then records locators in `run_facts_view`.
* **WSP streams** only from those SR-declared locators; it never “discovers” worlds or chooses by run_id.
* If you re-run the engine with a new `run_id` but same `{manifest_fingerprint, parameter_hash, seed, scenario_id}`, the sealed outputs whose scope excludes `run_id` must be byte-identical; only run-scoped logs vary.

---

### B6) The questions we should explicitly answer in the Oracle Store doc

These are the only identity questions that matter enough to write down:

1. Do we treat OracleWorldKey as a **human-visible composite** (the four tokens), or do we also assign a **single derived `world_id`** (hash of those four) for convenience?
2. Do we allow multiple seeds per “world pack” (a folder containing several seeds), or is each seed a separate OracleWorldKey instance?
3. Are run-scoped engine logs (`run_id`-scoped outputs) considered part of Oracle Store, or do we store them in a separate “engine execution logs” namespace? (They *are* engine outputs; they just must not contaminate world identity.)
4. Do we freeze/record the **catalogue version** (and gate-map version) alongside each OracleWorldKey so future consumers interpret scopes consistently?

---

## C) Layout: paths/prefixes that cannot drift

This section is basically: **what parts of the path tree are “engine-law” vs “platform wiring,”** and how we structure the Oracle Store so we *never* reintroduce “scan latest” or accidentally key worlds by `run_id`.

### C1) The hard constraint we cannot violate

The engine interface already pins this:

* An `EngineOutputLocator.path` is a **fully-resolved location** and **must be consistent with** the output’s `path_template` in `engine_outputs.catalogue.yaml`.

So Oracle Store layout must be:

* **(a) a prefix/root we add**, plus
* **(b) the engine’s existing relative tree under that root** (the `data/...`, `config/...`, `reports/...` structure that the catalogue/templates already define).

If we “redesign” the internal tree, we break locator correctness and we break gate verification paths.

---

### C2) The simplest drift-proof model: Oracle Store as “sealed packs”

Instead of one giant shared bucket root that every engine run writes into (which risks collisions for `scope_global` outputs), treat Oracle Store as **a collection of sealed, immutable “packs.”**

* A **pack** is one engine world materialization instance stored under its own root prefix.
* Once sealed, nothing inside that pack root is rewritten.

This matches how your local `runs/local_full_run-5` behaves today as a self-contained run root (it’s conceptually a pack), and it avoids global-path collisions without asking the engine to behave “nicely.”

**Authority declaration (v0):**
Oracle Store layout = `oracle_root/<env>/packs/<oracle_pack_id>/` + engine’s normal `path_template` tree underneath.

**V0 transitional note (current repo reality):**
- Local materialized data already lives under `runs/local_full_run-5/<engine_run_id>/...` and **does not** yet use the `packs/<oracle_pack_id>` structure.
- For v0, treat the existing **engine run root** as a **pack‑root alias** (one sealed pack per run root), and treat `oracle_root` as **either**:
  - the pack root itself, **or**
  - a parent directory that contains pack roots.
- Locators remain **fully resolved** and must continue to work without migration. We do **not** re‑write paths during v0.

---

### C3) What lives *inside* a pack root (do not invent new subtrees)

Inside each pack root, the engine’s existing templates already define the canonical layout. Examples from the catalogue:

* Traffic/table-like outputs (multi-file parquet):

  * `data/layer2/5B/arrival_events/seed={seed}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet` 
  * `data/layer3/6B/s3_event_stream_with_fraud_6B/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet` 

* Gate bundles and markers:

  * `data/layer3/6B/validation/manifest_fingerprint={manifest_fingerprint}/index.json` and `_passed.flag` (fingerprint-scoped)
  * Gate map also hardcodes these templates for verification (passed flag path, bundle root, index path).

* “Global scope” deterministic artifacts (no partitions):

  * `config/layer2/5B/arrival_count_config_5B.yaml` 
  * `config/layer1/2B/policy/alias_layout_policy_v1.json` 

**Pin:** Oracle Store does **not** invent a new internal directory scheme. The only safe change is adding a *pack root prefix* in front of the engine’s existing relative paths.

---

### C4) Pack root naming: what must be stable (and what must NOT appear)

**What must NOT be used as the pack root key:** platform `run_id`.
`run_id` is correlation for execution and only belongs in *run-scoped* outputs (typically logs/events); it must not become “the world folder.” 

**What pack identity should be based on (v0):**

* A stable `oracle_pack_id` derived from **OracleWorldKey** (the four tokens) and an **engine release identifier** (so global config files don’t mix across engine versions).

Concretely:

* `oracle_pack_id = H(manifest_fingerprint, parameter_hash, scenario_id, seed, engine_release)`
  …and then store a tiny manifest file in the pack root so humans can read the key without reversing hashes.

This keeps paths clean while still aligning with the engine’s tokenized internal layout.

---

### C5) Two tiny Oracle Store–owned files at pack root (worth pinning)

To make sealing/readability unambiguous without turning Oracle Store into a service:

1. **Pack manifest (metadata, not data)**

* e.g. `_oracle_pack_manifest.json`
  Contains: `{oracle_pack_id, manifest_fingerprint, parameter_hash, scenario_id, seed, engine_release, produced_at_utc}`.

2. **Seal marker**

* e.g. `_SEALED.flag` (or `_SEALED.json` with minimal fields)
  Meaning: “this pack root is complete and now immutable.”

This makes “readable vs not readable” deterministic without scanning the interior. (Gate PASS evidence still lives where the engine writes it—inside `data/.../validation/...` per gate templates.)

---

### C6) Environment ladder wiring: same logical tree, different substrate

**Local**

* `oracle_root` is a filesystem directory (your current `runs/local_full_run-5` is a valid pack root). 
* Packs live under: `runs/oracle/local/packs/<oracle_pack_id>/...` (or whatever root you prefer).

**V0 allowance (important):**
- `oracle_root` may point **directly to a pack root** (e.g., `runs/local_full_run-5/<engine_run_id>`) or to a **parent of packs**.
- SR/WSP should **not** derive pack ids; they should consume fully resolved locators from SR.

**Dev/Prod**

* Oracle Store is an S3-compatible bucket/prefix:

  * `s3://fraud-platform-oracle/<env>/packs/<oracle_pack_id>/...`
* The **pack-internal** paths stay exactly the engine templates (`data/...`, `config/...`, `reports/...`).

---

### C7) “No scanning for latest” — how layout supports the rule

Layout alone doesn’t prevent scanning; discipline does. So we pin the access pattern:

* **Only SR’s `run_facts_view` may point to a pack root / locators.**
* WSP/IG pull/DLA etc never “list packs.” They only read by locator.

**Allowed listing (narrow exception):**
Listing *within a locator directory* to expand `part-*.parquet` (because many outputs are explicitly multi-part). That’s not “discovering worlds,” it’s resolving a materialization detail already implied by the locator.

---

## The pinned layout decisions (v0)

1. Oracle Store is organized as **sealed packs**: `<env>/packs/<oracle_pack_id>/...`
2. Inside each pack, paths follow the engine’s existing `path_template`s verbatim (`data/…`, `config/…`, `reports/…`).
3. Pack root is **not** keyed by platform `run_id`.
4. Two root markers exist: a pack manifest + a seal marker (minimal, deterministic).
5. No pack scanning: SR join surface references locators; downstream reads only by locator. 

---

## D) Sealing + readability: when is a world “safe to touch”

This section is the **anti-partial-write** contract. It answers:

* “Can I safely read this oracle world without accidentally seeing half-written data?”
* “Can SR/WSP/IG treat it as authoritative?”

### D1) Two different meanings: **read-safe** vs **authority-safe**

**1) Read-safe (Oracle Store concern)**
A pack is *read-safe* if it is **complete and immutable** — i.e., no more writes will happen inside it.

**2) Authority-safe (SR/IG/WSP concern)**
A pack (and specific outputs within it) are *authority-safe* only after:

* required **segment gate PASS** is verified using gate-specific rules, and
* for instance-scoped outputs, **instance proof** binds locator+digest.

Oracle Store should own (1). SR/IG/WSP own (2). This separation keeps Oracle Store from becoming a policy engine.

---

### D2) The core law: “root commit exists ⇒ pack is sealed”

Borrow the exact “root commit last” protocol your DLA already pins:

> **A thing is committed iff the root commit object exists. Everything else is staging until then.** 

**Authority Declaration (v0):** Oracle Store sealing uses the same pattern.

* Engine (or a thin “oracle packer” wrapper around engine) writes all pack contents first.
* It writes a single **root seal object** *last*, with a conditional “create-if-absent” semantics.
* **Pack is READABLE iff root seal object exists.**

**V0 local reality (interim rule):**
- Current local packs do **not** yet have explicit seal markers.
- Until a packer/seal step exists, SR’s READY + required gate PASS evidence is treated as the **practical read‑safe indicator** for local packs.
- This is a **temporary allowance**; seal markers become mandatory once packer tooling exists.

Why this is drift-resistant:

* It prevents “directory looks mostly there” reads.
* It gives you a single stable check: “does the seal object exist?”

---

### D3) Seal object: what it must assert (minimal but sufficient)

The seal object should be **small, immutable metadata** — not a copy of data.

Minimum fields to prevent drift:

* `oracle_pack_id` (derived from OracleWorldKey + engine_release)
* OracleWorldKey tokens: `{manifest_fingerprint, parameter_hash, scenario_id, seed}`
* `engine_release` / `interface_pack_version` (so future readers know what catalogue/gate-map to apply)
* `sealed_at_utc`
* `seal_status` ∈ `{SEALED_OK, SEALED_FAILED}` (so failure worlds can exist without being “usable”)

This does **not** replace SR readiness, it only says “the pack is complete and immutable.”

(If you want, the seal object can optionally include a digest of a pack-manifest file, but that’s extra, not required for the concept.)

---

### D4) What “SEALED_OK” vs “SEALED_FAILED” actually means

This is important because engine runs can fail and you’ll still want their artifacts for debugging.

**SEALED_OK means:**

* Pack is immutable.
* Engine finished “normally enough” to declare completion.
* It does **not** mean “every downstream-required gate passed.” That’s a separate (authority-safe) concept enforced by SR/IG.

**SEALED_FAILED means:**

* Pack is immutable (so you can investigate deterministically).
* SR/WSP/IG must treat it as **ineligible** for normal run usage.

This keeps the Oracle Store honest: it’s a boundary for artifacts, not a “pass/fail engine oracle.”

---

### D5) Optional outputs and “sealed with missing stuff”

SR already has a pinned stance: **missing optional outputs are non-blocking; required outputs block evidence**. 

So the Oracle Store sealing rule should align:

**Authority Declaration (v0):**

* A pack may be **SEALED_OK** with missing outputs **only if those outputs are declared optional** (by the catalogue / SR’s OutputEntry interpretation).
* Missing non-optional outputs should prevent SEALED_OK (or force SEALED_FAILED).

This prevents a subtle drift where “seal means nothing,” while still supporting the reality that some outputs are legitimately optional.

---

### D6) Gate artifacts do not define “seal” — they define “authority-safe reads”

Engine’s gates are fingerprint-scoped and expressed as `_passed.flag` + bundle + index; verification is gate-specific and declared in `engine_gates.map.yaml`.

Also, your portable gate receipt schema explicitly notes the on-disk `_passed.flag`/bundle bytes vary by segment, and consumers must treat the portable receipt as the standard object. 

So we pin the relationship:

* **Oracle Store sealing** says: “pack is complete/immutable.”
* **Gate PASS** says: “this segment’s outputs are authoritative to read.”
* **Instance proof** says: “this particular instance-scoped output is bound to exact bytes.”

This matches your “No PASS → no read” doctrine exactly. 

---

### D7) Who checks what (so nobody re-invents a policy engine)

**Oracle Store checks:**

* Seal object existence (READABLE vs NOT READABLE)
* (Optionally) seal object schema validity

**Scenario Runner checks:**

* Fail-closed evidence collection: required gate PASS verified using the gate-map methods before READY.
* Optional output handling (non-blocking) 
* Instance-proof receipts: either engine-emitted or SR-verifier receipts in SR store (engine remains black-box).

**WSP / IG (stream/pull) check:**

* They do **not** scan the oracle.
* They only follow SR’s `run_facts_view` refs and fail-closed if required proof refs are missing. 

---

### D8) The only “safe to touch” rule (final)

So, in one pinned statement:

> **A world pack is safe to touch (read bytes) iff it is SEALED (root seal object exists). A world pack is safe to use for the platform iff SR can produce a READY run context from it (required PASS + instance proof as needed).**

---

## E) Evidence model: PASS gates and instance proofs

This section pins **what “proof” exists**, **where it lives**, and **how it’s referenced**, without turning Oracle Store into a policy engine.

### E1) Two classes of evidence (don’t blend them)

#### 1) **Segment PASS evidence** (HashGates / validation gates)

This is the “world is internally consistent for this manifest” layer.

* Gate definitions live in `engine_gates.map.yaml` and each gate declares:

  * scope (almost always **fingerprint-scoped**),
  * `_passed.flag` path template,
  * bundle root + index path templates,
  * verification method (method-specific),
  * upstream gate dependencies,
  * which outputs it authorizes (`authorizes_outputs`),
  * and which components require it (e.g., `ingestion_gate`, `downstream_readers`, `observability_governance`).

**Key pin:** gate verification is **method-specific** (no ad hoc hashing). IG’s design explicitly locks this: implement exactly the method listed in the gate map; enforce dependency closure; fail closed.

#### 2) **Instance proof evidence** (binds a specific output instance)

This is the “these exact bytes are the ones for this output locator” layer.

IG’s design authority pins the rule: if an output’s identity scope includes any of `{seed, scenario_id, parameter_hash, run_id}`, then **instance proof is required**, and it must bind to **(engine_output_locator + content_digest)**; missing digest is an immediate failure. 

SR implementation notes also make this explicit and propose the receipt binding fields (`target_ref` + `target_digest`) and an `instance_receipts` surface in `run_facts_view`.

---

### E2) The three evidence artifacts we must distinguish

#### A) **On-disk gate artifacts** (engine-written, raw bytes)

These are the segment-specific, sometimes text/JSON files:

* `_passed.flag`
* `index.json` / `validation_bundle_index_*.json`
* validation bundle contents under the bundle root

The portable contract explicitly warns: these raw bytes may differ per segment; the portable receipt standardizes the *meaning*, not the file bytes. 

**Oracle Store responsibility:** store these artifacts *immutably* under the pack root, exactly where the gate map templates say they are.

#### B) **Portable GateReceipt objects** (standardized)

`gate_receipt.schema.yaml` defines a portable representation:

* `gate_id`
* `status` (`PASS`/`FAIL`; unknown/missing must fail closed)
* `scope` (always includes `manifest_fingerprint`, with optional narrower keys)
* optional pointers to authoritative on-disk artifacts (`validation_bundle_root`, `index_path`, `passed_flag_path`). 

**Design intent:** GateReceipt objects are what SR/IG/downstream use to reason deterministically, without needing to interpret raw `_passed.flag` formats. 

#### C) **Instance-proof receipts** (portable, per-output-instance binding)

These bind:

* `target_ref` (the locator: output_id + path + identity tokens)
* `target_digest` (must match `engine_output_locator.content_digest`)
  …and are written **write-once** (idempotent across retries). SR’s implementation notes even pin deterministic SR-side receipt storage under an SR prefix when the engine remains black-box.

---

### E3) Where evidence lives (Oracle Store vs SR store)

This is the most important “who writes what” boundary.

#### Oracle Store (engine-owned, by-ref boundary)

Oracle Store contains:

* **engine outputs** (traffic tables, surfaces, etc.)
* **gate artifacts** (`_passed.flag`, indexes, bundle contents) under the same pack root
* **optionally** engine-emitted receipts (if/when the engine emits standardized receipts)

Gate map templates tell you exactly where the on-disk artifacts live, fingerprint-scoped under `data/<layer>/<segment>/validation/manifest_fingerprint=.../…`.

#### SR Store (platform-owned truth for runs)

SR must publish a join surface (`run_facts_view`) that contains:

* which outputs are eligible (traffic targets),
* the **portable GateReceipt objects** (or refs to them),
* and, for instance-scoped outputs, the **instance-proof receipts** (or refs).

Because your constraint is “engine remains a black box,” SR may generate verifier instance receipts in **SR’s own object store**, not in oracle storage, using `write_json_if_absent` to keep them immutable.

> **Authority declaration (v0): Oracle Store holds raw gate artifacts; SR owns the portable evidence surfaces used by the platform (run_facts_view + SR verifier receipts when needed).**

This keeps Oracle Store from becoming a “policy service,” while still preserving strict evidence chains.

---

### E4) How verification works (without scanning)

#### Gate verification (segment PASS)

Both SR and IG (in pull mode) are pinned to:

* load the gate map as the authority,
* use the gate’s declared `verification_method` (no ad hoc rules),
* enforce upstream dependencies,
* and fail closed on missing artifacts or mismatches.

IG’s design also pins that proof artifacts are resolved from **proof refs provided in `run_facts_view`**, not by scanning storage.

SR’s implementation notes further show the real-world nuance: verification often depends on index-defined evidence sets and path-base rules; SR aligned its verifier to those gate-map methods (index-driven, raw-bytes digest, etc.) to remain black-box compatible.

#### Instance proof (per-output)

IG’s design pins the classifier and binder:

* If output scope includes instance keys → instance proof required
* `content_digest` is mandatory
* receipt must bind locator + digest exactly
* fail closed on any mismatch or missing. 

SR’s notes explicitly describe the platform-compatible plan:

* add an `instance_receipts` array to run facts view (optional for backward compatibility),
* store receipts deterministically (write-once),
* bind to `locator.content_digest`.

---

### E5) Consumption rules (so downstream can’t cheat)

**Pinned access law (re-stated in evidence terms):**

* Oracle Store is never scanned directly.
* Consumers only read evidence and data via **SR’s join surface** (run_facts_view).
* Missing required evidence refs ⇒ treat as not usable (fail closed).
* Oracle Store itself never “quarantines”; downstream boundaries decide outcomes. (IG quarantines; SR marks WAIT/FAIL).

A tight conceptual flow:

```text
Engine writes raw artifacts → Oracle Store (pack root)
SR verifies (gate-map methods) → emits GateReceipts + instance receipts → SR run_facts_view
WSP streams only traffic targets declared in run_facts_view (and only when evidence is COMPLETE)
IG admits traffic (push) / verifies proofs (pull) using run_facts_view evidence; quarantines on missing/mismatch
```

---

### E6) The minimal E-section “pins” (v0)

1. **Gate artifacts live in Oracle Store** exactly at gate-map template paths; immutable.
2. **Portable GateReceipt objects are the standardized proof surface**; raw `_passed.flag` bytes are not a portable contract. 
3. **Gate verification is method-specific + dependency-closed** per `engine_gates.map.yaml`; fail closed.
4. **Instance-scoped outputs require instance proof binding to (locator + content_digest)**; missing digest/receipt fails closed.
5. **SR is the platform attester**: it publishes run_facts_view containing the evidence map (and SR verifier receipts when engine is black-box).
6. **No scanning**: proof artifacts are resolved from run_facts_view proof refs; storage listing is permitted only within a locator’s own part-glob scope.

---

## F) Access semantics: how consumers are allowed to use Oracle Store

This section pins **who may read** from Oracle Store, **how** they may read, and what is **forbidden** so we never drift back into “scan for latest world” or “treat oracle like a query DB.”

### F1) The entrypoint law (applies to everyone)

**[PIN] Nobody starts at Oracle Store.**
Downstream must start from **SR’s join surface** (`READY` → `sr/run_facts_view`), then follow explicit refs/locators. Scanning engine outputs or inferring “latest” is forbidden.

This is the same law SR and IG already state for the platform: SR publishes the join surface; downstream follows refs; no discovery-by-storage.

---

### F2) The only allowed access pattern: keyed reads (no list/search)

We reuse the platform’s verifier posture as the general Oracle Store access rule:

**[PIN] Oracle Store access is “keyed resolver only.”**
Allowed operations are:

* `HEAD exact object key`
* `GET exact object key` (bounded / streaming where possible)
* “id → deterministic key mapping” only when the mapping is fixed and explicit

**Forbidden:**

* list prefixes
* wildcard search
* “latest”
* bucket scans

This is the same “no-scan enforcer” pattern the DLA Evidence Attachment Verifier uses. 

**Narrow exception (only when the locator itself implies it):**
If an `EngineOutputLocator.path` explicitly targets a multipart materialization (e.g., `part-*.parquet`), listing **within that single locator directory** to expand concrete part files is permitted. This is *not discovery*; it’s resolving a materialization detail already declared by the locator. (But listing beyond that directory is still forbidden.)

---

### F3) Who is allowed to read Oracle Store, and for what

Oracle Store is by-ref world truth. Different components are allowed to read it for different reasons, but all must obey the same entrypoint + keyed-access laws.

#### 1) **Scenario Runner (SR)**

SR may read Oracle Store to:

* assemble output locators
* verify required PASS evidence (gate-map methods)
* bind instance-proof receipts (in SR store if engine is black-box)
  …and then publish the **only** join surface (`sr/run_facts_view`).

**SR is the attester**: READY is meaningless without the persisted join surface artifacts.

#### 2) **World Stream Producer (WSP)**

WSP may read Oracle Store **only** to stream **engine `business_traffic`** that SR has explicitly declared as traffic targets in `run_facts_view`.
WSP must not:

* read truth_products/audit_evidence as traffic
* discover outputs by scanning
* stream anything not allowlisted by the run join surface

#### 3) **Ingestion Gate (IG)** — *only in legacy pull mode*

IG may read Oracle Store **only** when it is running the **engine pull ingestion job**, and even then:

* it ingests only traffic targets listed in `run_facts_view`
* it never “discovers traffic” by scanning engine directories
* it must verify `No PASS → no read` using gate-specific rules from the gate map
* it must enforce instance-proof binding for instance-scoped outputs

(If `traffic_delivery_mode=STREAM`, IG should not be reading Oracle Store for traffic at all—WSP is supplying the by-value events.)

#### 4) **Decision Log & Audit (DLA)**

DLA may read Oracle Store **only** for a fenced “engine evidence attachment” lane (e.g., engine `audit_evidence` attachments), and only by explicit refs with gate proofs—never scanning, never guessing. The verifier is keyed, bounded, fail-closed, and has retry budgets for transient object-store visibility.

#### 5) **Case Management / Workbench (CM)** — optional “oracle lane”

CM may read Oracle Store **only** via an `EngineOracleRef` in the **ORACLE_REFERENCE lane**, which must:

* be obtained via SR join surface (no scanning)
* carry required PASS proof pointers
* never be treated as business traffic
* never silently override investigator truth

#### 6) **Offline Feature Shadow (OFS)** — optional world/context surfaces

OFS must **not** read engine datasets directly for traffic; it replays EB/Archive.
It may optionally read static world/context surfaces **only via SR-provided locators/receipts** (by-ref, PASS-evidenced), and it is forbidden from scanning for “latest.”

---

### F4) Bounded reads (so verification doesn’t become a giant IO sink)

**[PIN] Any Oracle Store read for verification must be bounded/streamed where possible.**
The platform already pins this in evidence verification: streaming hashing, strict max sizes, and avoiding turning verification into heavy IO. 

This is especially important for:

* gate verification reads
* digest verification for instance proofs
* evidence attachment verification in DLA

---

### F5) Failure semantics: Oracle Store doesn’t “quarantine,” consumers do

Oracle Store returns “readable/unreadable” outcomes at the storage level (missing key, access denied, etc.).
**Quarantine is a consumer outcome**:

* IG quarantines ingestion items (with receipts + evidence pointers)
* DLA recommends quarantine/omit based on verification verdicts
* CM returns explicit evidence statuses (PENDING/UNAVAILABLE/QUARANTINED/FORBIDDEN) rather than fabricating content

**[PIN] Fail closed:** missing/invalid proofs or missing objects never degrade into “best effort read anyway.”

---

## F-section pins (v0)

1. **Entry point:** all Oracle Store use must start from `SR READY → sr/run_facts_view` (no scanning).
2. **Keyed-only access:** HEAD/GET exact keys; no prefix listing/search/latest.
3. **Allowed readers:** SR (attester), WSP (traffic streaming), IG (pull mode only), DLA (engine evidence lane), CM (optional oracle lane), OFS (optional world surfaces)—each by explicit refs with proofs.
4. **Listing exception:** only within a locator’s own multipart scope (e.g., `part-*`), never beyond.
5. **Bounded IO:** verification reads must be bounded/streamed; avoid heavy IO sinks. 
6. **Oracle Store doesn’t quarantine:** consumers do; always fail-closed on missing proofs/objects.

---

## G) Oracle Store ↔ SR join surface: hard boundary

This is the **“no scanning, no guessing”** contract that makes Oracle Store usable without becoming a runtime vertex.

### G1) The boundary in one sentence

**Oracle Store holds immutable world artifacts; SR publishes the only *joinable map* to those artifacts.**
Downstream is never allowed to “browse the oracle.” It must start from **SR READY → `run_facts_view`** and follow explicit refs.

---

### G2) Who owns what truth (so nobody drifts)

**Oracle Store truth (engine-owned):**

* “These bytes exist at these object keys.”
* “This pack is SEALED (read-safe).”

**SR truth (platform-owned):**

* “This run is READY.”
* “This is the authoritative mapping for the run: pins + locators + required PASS evidence.”

**Critical pin:** SR is *system-of-record* for run readiness and the downstream join surface. If SR can’t evidence it, SR can’t READY it.

---

### G3) The *only* legal entrypoint (re-stated as a rule)

The platform blueprint pins this as law:

* `run_ready_signal` is the **trigger**
* `run_facts_view` is the **map**
* Downstream is forbidden from scanning engine outputs / inferring “latest run.”

So Oracle Store must be treated as **non-discoverable** by downstream. The *only* discoverable object is `sr/run_facts_view` (via READY).

---

### G4) What SR must publish in `run_facts_view` (meaning, not schema)

SR’s design authority defines `run_facts_view` as:

> “pins + engine evidence pointers + output locators + PASS receipts needed to treat refs as admissible.”

To make Oracle Store actually usable (and avoid downstream invention), the facts view must include, at minimum:

#### (1) Run context pins

* ContextPins + seed: `{scenario_id, run_id, manifest_fingerprint, parameter_hash, seed}`
* Explicit run time/window keys (SR pin: “time semantics never collapse; runs carry explicit time/window keys”).

#### (2) Oracle reference anchor

A stable pointer that says “this run references this sealed oracle materialization”, e.g.:

* `oracle_pack_ref` (pack root pointer or pack id → base prefix)
* optionally: `oracle_pack_seal_ref` (so consumers can fail-closed if not sealed)

(Important: this is an *anchor*, not a discovery tool.)

#### (3) Output locators (by-ref)

For every intended output SR is exposing:

* portable `engine_output_locator` (output_id + resolved path + required identity fields)
* SR hard law: locator path must be consistent with the catalogue template.

#### (4) Role classification + traffic allowlist

SR must classify outputs as:

* `business_traffic | truth_products | audit_evidence | ops_telemetry`
  and **only `business_traffic`** is eligible for ingestion.

This is what prevents “oracle truth products accidentally became traffic.”

#### (5) Proof references (fail-closed)

To enforce “No PASS → no read” and instance binding:

* required `gate_receipt[]` (PASS/FAIL) with evidence refs
* instance-proof refs where required
* plus `engine_output_locator.content_digest` for instance-scoped outputs (hard law: missing digest ⇒ FAIL/UNBINDABLE).

This is exactly what IG expects from the join surface: proof refs come from `run_facts_view`; no proof discovery by scanning.

#### (6) Traffic targets list (the “who may be streamed/ingested” subset)

IG’s pull plan join (`RunIngestPlan`) makes it explicit what a traffic target needs to include:

* `engine_output_locator`
* `declared_role` (must be business_traffic)
* `proof_refs` (+ instance proof refs if required)
* `content_digest` (when required)
* framing hints like **`event_type = output_id`**

Even with WSP streaming, the facts view should still carry a clean `traffic_targets[]` subset so **both**:

* WSP (STREAM mode) and
* IG pull worker (PULL mode)
  …can follow the same “declared traffic set” without inventing rules.

---

### G5) SR publish ordering (why READY is trustworthy)

SR’s design authority pins the write ordering as production-critical:

1. write `run_facts_view` (complete map)
2. write `run_status = READY`
3. only then emit READY on `fp.bus.control.v1`

**Meaning:** READY without a readable facts view is “meaningless” and downstream must wait/retry, never guess.

This is the core reason Oracle Store can stay “dumb storage”: SR provides the atomic join surface.

---

### G6) Reuse, correction, and “no mutation” across the boundary

SR has pinned monotonicity:

* READY is monotonic (no silent undo)
* Corrections happen as a **new declared state** / **superseding run story**, not by mutating history.

That means:

* Oracle Store packs remain immutable forever.
* If SR decides a prior run’s mapping was wrong, it publishes a **new** run (new run_id) with a new facts view and records the relationship (supersedes), rather than rewriting any oracle artifacts or old facts views.

---

### G7) WSP-era addition (the minimum to prevent “double ingestion” drift)

Because we now support **STREAM** (WSP) and may keep **PULL** (IG) as a fallback, the join surface must be the place where the run declares which delivery mode is active—otherwise READY could trigger both.

We already have the pattern: IG treats READY as the trigger and `run_facts_view` as the map.

So the design-authority pin for the SR join surface in the WSP world is:

* `traffic_delivery_mode ∈ {STREAM, PULL}`
* `traffic_targets[]` is still the allowlist either way
* downstream must never infer mode from environment or config

(We can treat this as a WSP-driven extension to the SR facts view meaning, not an Oracle Store responsibility.)

---

## G-section v0 pins

1. **Oracle Store is not discoverable by downstream.** Downstream starts from SR READY + `run_facts_view`.
2. **SR owns run readiness + the join surface map.** READY is meaningless without persisted ledger artifacts.
3. **`run_facts_view` must carry enough refs + proofs** for WSP/IG to act without scanning: locators, roles, gate receipts, instance-proof refs/digests, traffic_targets.
4. **Publish ordering is a commit protocol:** facts view → status READY → READY bus signal.

---

## H) Environment ladder: local/dev/prod storage posture (Oracle Store)

The Oracle Store has to obey the **same rails everywhere** (by-ref, immutable-ish objects, no scanning; SR join surface is the entrypoint), and only differ by **operational envelope** (size, retention, security, HA).

### H1) What must be identical across environments

**These are the “no drift” invariants for Oracle Store:**

* **Same logical layout tokens** and path conventions (no env-specific “special” structure).
* **Write-once / sealed** posture (sealed packs are immutable; corrections create *new* identity, not overwrite). 
* **No discovery-by-scanning**: nobody lists “latest world.” The only legal entrypoint is `SR READY → sr/run_facts_view → locators`.
* **Same substrate semantics**: “S3-ish object store” semantics locally too, so digest+locator verification behaves the same.

---

### H2) Recommended substrate wiring (aligned to your tooling notes)

Your reference local stack already pins: **MinIO (S3-compatible)** for by-ref artifacts, and a single bucket layout with stable prefixes.

**v0 practical mapping:**

* Oracle Store lives under the object store’s **`engine/` prefix** (engine outputs + gate receipts). 
* SR ledgers/join surface live under **`sr/`** (run_plan/run_record/run_status/run_facts_view).

So in the “single bucket `fraud-platform`” reference layout, Oracle Store is:

```text
s3://fraud-platform/engine/packs/<oracle_pack_id>/...
s3://fraud-platform/sr/run_facts_view/...
```

(Exact pack internals remain engine templates; SR points to locators.)

---

### H3) Local / Dev / Prod posture (what changes, and only what changes)

#### Local (laptop)

* **Store**: MinIO (recommended) or filesystem shim, but must preserve S3-ish addressing/digest verification semantics.
* **Oracle content**: *small curated packs* (tiny windows / fewer entities) to keep iteration fast.
* **Retention**: short / manual cleanup is fine (because this is for iteration), but sealed-vs-unsealed semantics still apply. 
* **Security**: minimal friction, but don’t bypass the concept of “engine is the only writer” (otherwise you’ll build impossible behavior). 

#### Dev (shared integration)

* **Store**: MinIO/S3 with the same prefix family.
* **Oracle content**: medium packs; enough volume to surface scaling issues (but still bounded).
* **Retention**: days/weeks; cleanup is governed-ish (at least a run launcher policy), not “anyone deletes.”
* **Security**: “real enough” auth policies so permission issues show up here, not in prod. 

#### Prod (hardened runtime)

* **Store**: managed S3-compatible with strong security + HA.
* **Oracle content**: policy-driven retention; long-horizon packs for reproducibility.
* **Immutability enforcement**: stronger guarantees (e.g., object versioning / WORM-like posture / deny overwrites) to make “sealed means immutable” mechanically true.
* **Deletion**: explicit and auditable (no “oops we deleted the world”). This mirrors your platform pin that immutable truths aren’t silently mutated and operations are declared facts.

---

### H4) Two topology options (pick one as v0 so Codex doesn’t invent)

#### Option A — **Per-env isolated Oracle Store** (recommended v0)

* Each env has its own bucket/prefix root (`fraud-platform` bucket in local/dev, separate prod bucket/prefix).
* Worlds do not “accidentally leak” across envs.

**Why this is safest:** it prevents cross-env drift and accidental “prod reading dev worlds.”

#### Option B — **Shared read-only World Library + per-env caches**

* A single “world library” bucket holds sealed packs (read-only).
* Local/dev/prod can explicitly “import” packs (copy or reference) for runs.

**Why you might want it later:** promotion of worlds becomes like promotion of immutable artifacts (but it needs governance to stay safe).

**My v0 authority call:** choose **Option A** now (isolated per env), and add an explicit “import pack” operation later if you need it.

---

### H5) The minimal “wiring knobs” vs “policy knobs” split (so the ladder stays honest)

Borrowing your ladder doctrine: differences should be profiles, not code forks.

**Wiring (non-semantic) knobs per env**

* `ORACLE_BUCKET`
* `ORACLE_BASE_PREFIX` (e.g., `engine/`)
* `ORACLE_PACKS_PREFIX` (e.g., `engine/packs/`)
* endpoints/credentials/timeouts

**Policy (outcome-affecting) knobs per env**

* retention duration for sealed packs
* allowed pack sizes / windows
* who can write new packs
* whether deletion requires approval/audit fact

---

### H6) What this implies for how you “store the oracle set”

In plain terms:

* In each env, you keep a **library of sealed oracle packs** under `engine/packs/<oracle_pack_id>/...` in the object store. 
* SR picks one pack (or reuses it) and publishes locators in `sr/run_facts_view`.
* WSP never “chooses from the oracle set”; it only follows SR’s locators.

---

## I) Retention, archive, and reproducibility (Oracle Store)

This section pins how long oracle packs live, how they “leave,” and how we keep runs reproducible **years later** without turning Oracle Store into a query system or mutable DB.

### I1) The core retention law (what we are protecting)

**[PIN] Oracle Store exists to preserve reproducibility.**
If we delete worlds casually, we delete the ability to explain decisions, replay history, and validate model training provenance.

So retention is not “storage hygiene.” It’s a **platform truth preservation** policy.  

---

### I2) What “archive” means for Oracle Store

Oracle Store is **by-ref artifacts** (engine outputs + gate artifacts) in object storage.  

So “archive” should mean:

* **Tier movement** (hot → warm → cold) while preserving keys/locators, or
* **Explicit export** to an archive bucket/prefix with a stable archive reference.

**[PIN] Archive must not change the logical addressability contract.**
SR/WSP must still be able to read by locator (or by a deterministic archive indirection that SR records in `run_facts_view`). 

---

### I3) Minimal lifecycle states for oracle packs (drift-resistant)

We keep this simple and declarative (no service required):

* **STAGING**: pack root exists, not readable
* **SEALED_OK**: pack is readable/immutable (seal marker exists)
* **SEALED_FAILED**: pack is readable for debugging, ineligible for normal runs
* **ARCHIVED**: pack exists but may be cold/slow; still addressable
* **TOMBSTONED**: pack deleted/unavailable, but a tombstone record exists explaining the deletion

**[PIN] Nothing ever transitions “backwards.”** No unseal. No overwrite. No “fix in place.” 

---

### I4) Environment ladder retention defaults (policy knobs, not code forks)

These are *defaults* you can tune, but the key is: the ladder changes **duration + tier**, not semantics. 

#### Local

* Retain: **short**
* Goal: iteration, not audit
* Allowed: manual cleanup
* Still required: sealed-vs-unsealed semantics (so local doesn’t develop impossible behaviors)

#### Dev

* Retain: **medium** (days/weeks)
* Goal: integration realism + regression replay
* Cleanup: automated TTL (but declared and traceable)

#### Prod

* Retain: **long** (months/years depending on audit policy)
* Archive: hot→cold tiering rather than deletion
* Deletion: rare and explicitly governed (see I6)

---

### I5) Reproducibility requirements (what must be frozen with a pack)

A sealed pack must carry enough metadata to let a future reader interpret it *correctly*, even if code evolves.

**[PIN] Every SEALED_OK pack must record a “Repro Manifest” at pack root** (small JSON/YAML), containing at minimum:

1. **World identity tokens**: `{manifest_fingerprint, parameter_hash, scenario_id, seed}`
2. **Engine release / build identity** (so global-scope config files aren’t misinterpreted)
3. **Interface pack versions** used to interpret the contents:

   * `engine_outputs.catalogue` version (or digest)
   * `engine_gates.map` version (or digest)
   * schema pack versions (or digests) for key outputs (at least the canonical envelope + locator/receipt schemas if you treat them as part of the interface bundle)   

This is *not* a duplicate catalogue. It’s a small “what interpretation rules apply” anchor.

Why this matters: your gate verification is **method-specific** and depends on the gate map; future code must know exactly which map/version was used.

---

### I6) Deletion and tombstoning (how to avoid silent loss)

**[PIN] Deletion is never silent.**
If a pack becomes unavailable, there must be a durable tombstone explaining:

* which pack (`oracle_pack_id`)
* when deleted
* by whom / under what authority (ticket/change-id)
* why (retention policy / legal / corruption)
* whether an archive replacement exists

Where does the tombstone live?

* Preferred: **a separate governance store** (SR/ops ledger) so the tombstone itself isn’t lost when the pack is deleted.
* Minimum v0: a tombstone object at the pack root *before* deletion, plus an SR/ops record referencing it.

**[PIN] SR must not emit READY for a run whose referenced oracle pack is TOMBSTONED or unreadable.**

---

### I7) Relationship to bus archive and offline stores (avoid mixing duties)

Oracle Store is **world truth artifacts**, not the platform’s operational history.

So:

* EB archive retains **admitted traffic facts** (what the bank observed). 
* Oracle Store retains **world materialization truth** (what the outside world was capable of emitting).
* Offline stores retain **derived projections/features/models**.

**[PIN] Do not replace EB archive with Oracle Store, and do not treat Oracle Store as a replay log.** WSP is the replay mechanism from oracle → platform; EB is the platform’s fact spine.

---

### I8) Minimal pinned decisions for this section (v0)

1. Oracle packs have a small lifecycle: STAGING → SEALED_OK/FAILED → ARCHIVED → TOMBSTONED (monotonic).
2. Retention differs by env only in **duration/tiering**, never in semantics. 
3. Every SEALED_OK pack writes a **Repro Manifest** recording interpretation versions (engine release + catalogue/gate-map/schema digests).
4. Deletion is governed: **tombstone required**, SR must fail-closed if a referenced pack is missing/tombstoned.
5. Oracle Store is not EB archive and not a replay log; it’s the by-ref world boundary.

---

## J) Failure modes: fail-closed without turning Oracle Store into a service

This section pins **what can go wrong**, **how we classify it**, and **who must react**—while keeping Oracle Store as a *sealed boundary* (storage + rules), not a policy engine.

### J1) The governing principle

**[PIN] Oracle Store never “makes decisions.”**
Oracle Store only yields storage-level outcomes (“readable / not readable / bytes mismatch / access denied”). **Decision outcomes** (RUN_NOT_READY, QUARANTINE, SKIP, PAUSE) belong to the caller (SR/WSP/IG/DLA/CM).

**[PIN] Fail-closed always.**
No fallback to scanning, no “best effort” reads when proofs/digests/seal are missing.

---

### J2) The failure taxonomy (keep it small + composable)

#### Class 1 — **Readability failures (pack-level)**

These answer: “is this oracle pack safe to touch at all?”

* **PACK_NOT_FOUND**: pack root/key doesn’t exist
* **PACK_NOT_SEALED**: seal object missing (still STAGING)
* **PACK_SEALED_FAILED**: seal exists but marked failed/ineligible
* **PACK_TOMBSTONED**: deletion recorded (pack intentionally unavailable)

**Interpretation:** do **not** read interior objects. Treat as “oracle unreadable.”

#### Class 2 — **Addressability failures (object-level)**

These happen even if the pack is sealed:

* **OBJECT_MISSING**: locator key doesn’t exist
* **ACCESS_DENIED**: authz failure to read object
* **TIMEOUT / THROTTLED**: storage transient failures
* **LISTING_FORBIDDEN**: attempt to list beyond locator scope (policy violation)

**Interpretation:** the caller decides retry vs terminal outcome. No scanning fallback.

#### Class 3 — **Integrity failures (bytes don’t match the proof story)**

These are the “this is dangerous” outcomes:

* **DIGEST_MISMATCH**: computed/observed digest ≠ expected digest
* **INSTANCE_PROOF_MISMATCH**: instance receipt binds locator+digest, but digest doesn’t match locator bytes
* **GATE_EVIDENCE_MISMATCH**: gate receipt says PASS but on-disk gate artifacts don’t verify under the gate-map method

**Interpretation:** treat as **terminal integrity breach** (not “retry until it works”).

#### Class 4 — **Evidence completeness failures (proof missing or insufficient)**

These are “can’t be authority-safe” failures:

* **REQUIRED_GATE_RECEIPT_MISSING**
* **REQUIRED_GATE_NOT_PASS**
* **INSTANCE_PROOF_REQUIRED_BUT_MISSING**
* **CONTENT_DIGEST_REQUIRED_BUT_MISSING**

**Interpretation:** fail-closed; caller must not proceed.

---

### J3) Caller-specific behavior (who reacts how)

#### (1) Scenario Runner (SR) — *attester; must not READY on uncertainty*

SR is the one component that can safely “block” the platform by refusing READY.

**SR must:**

* Treat **any** required-evidence failure as **RUN_NOT_READY** (or RUN_FAILED) and **never** emit READY.
* Distinguish **transient** storage failures (timeout/throttle) from **terminal** failures (not sealed, digest mismatch).
* Persist an explicit failure record (run_status + reason codes + minimal pointers), so downstream never guesses.

**SR must never:**

* “Pick another pack” by scanning.
* Mark READY and hope WSP/IG “sort it out.”

#### (2) World Stream Producer (WSP) — *pause safely; don’t invent progress*

WSP’s job is to stream; it cannot turn oracle problems into “fake traffic.”

**WSP must:**

* On **pack-level unreadable** (not sealed / missing / tombstoned): **PAUSE the run stream** and surface a clear incident (no retries forever).
* On **transient object-store** failures: backoff + retry, without advancing the stream cursor (receipt-gated progress).
* On **integrity failures** (digest mismatch): **STOP/PAUSE with terminal error** (do not keep streaming other windows as if nothing happened—this is a world corruption signal).

**WSP must never:**

* Buffer the month and keep going (“bulk ETL” behavior).
* Skip missing objects and “continue” without recording a terminal outcome.

#### (3) Ingestion Gate (IG) — *quarantine is the truth outcome at the boundary*

IG has two modes:

* **STREAM mode (WSP push):** IG generally doesn’t need to read Oracle Store for traffic bytes, but it must enforce run-joinability and policy allowlists.

  * If SR join surface is missing/unreadable: quarantine the pushed events as **RUN_CONTEXT_UNAVAILABLE** (fail-closed).
  * If event_type not in traffic_targets for that run: quarantine as **NOT_DECLARED_TRAFFIC_TARGET**.
  * If pins mismatch SR run pins: **PIN_MISMATCH** quarantine.

* **PULL mode (legacy):** IG reads oracle bytes and must enforce gate-map verification + instance proof.

  * Missing proof artifacts / gate mismatch / digest mismatch ⇒ **quarantine** (plan-level or item-level, depending on the unit), and do not publish to EB.

**IG must never:**

* Admit traffic on “best effort” oracle reads.
* Treat “storage transient” as “accept anyway.”

#### (4) Decision Log & Audit (DLA) — *evidence attachment is optional but must be truthful*

DLA’s engine-evidence lane is explicitly fenced: attach by-ref, verify fail-closed, but **do not block the primary decision record**.

**DLA should:**

* If an evidence attachment read fails: record attachment status as `UNAVAILABLE`/`FORBIDDEN`/`MISMATCH` and keep the decision record valid.
* Never “fill in missing evidence.”
* Provide enough pointers so an operator can retry later (by-ref keys + expected digest).

#### (5) Case Mgmt (CM) oracle lane — *show “oracle unavailable”, not “oracle says no fraud”*

If oracle truth products are used as an optional reference lane:

**CM must:**

* Surface “oracle unavailable” states explicitly.
* Never treat missing oracle truth as negative evidence.
* Never silently substitute “latest available” oracle outputs.

#### (6) Offline Shadow (OFS)

OFS should not read oracle traffic; it replays EB. If it reads world/context surfaces by-ref:

**OFS must:**

* Fail-closed when proofs/objects missing.
* Prefer “skip surface + mark incomplete features” rather than inventing values.

---

### J4) Retry posture (transient vs terminal)

**Transient (retryable):**

* storage timeout / throttling
* temporary 404 due to eventual visibility (rare, but treat carefully)
* temporary permission propagation delays in dev

**Terminal (non-retryable without human action):**

* PACK_NOT_SEALED (unless you’re waiting for engine completion; SR should own this)
* DIGEST_MISMATCH / PROOF_MISMATCH
* PACK_TOMBSTONED
* POLICY_FORBIDDEN / ACCESS_DENIED (unless credentials change)

**[PIN] Retrying must not change identity.**
No “new event_id to get through.” Same logical reference ⇒ same identity.

---

### J5) Evidence capture for failures (minimal but reproducible)

When a failure is recorded (SR run failure, IG quarantine, DLA attachment failure), the evidence should be:

* the **locator/ref** that was attempted
* the **expected digest** (if applicable)
* the **observed digest** (if computed)
* the **seal status** observed (sealed/unsealed/tombstoned)
* the **gate_id** + receipt ref (if applicable)
* timestamps + actor identity

**[PIN] Don’t copy huge payloads into evidence bundles.**
Store pointers; keep bundles small; make reproduction possible by replaying the keyed reads.

---

### J6) The “no repair by overwrite” law

If something is wrong with a sealed pack (missing objects, digest mismatch), the fix is not “patch the pack.”

**[PIN] Correction = new pack + new SR run mapping.**
Old packs stay immutable; SR emits a new `run_facts_view` pointing to the corrected world.

---

### J7) A minimal failure matrix (what callers do)

* **PACK_NOT_SEALED**

  * SR: not READY (wait)
  * WSP: don’t start (pause)
  * IG: if push events arrive anyway → quarantine as RUN_NOT_READY

* **OBJECT_MISSING (required traffic target)**

  * SR: not READY if required; otherwise mark optional missing
  * WSP: pause with incident (don’t skip silently)
  * IG pull: quarantine/abort plan

* **DIGEST_MISMATCH / INSTANCE_PROOF_MISMATCH**

  * SR: run FAILED (terminal)
  * WSP: stop/pause terminal
  * IG pull: quarantine terminal
  * DLA/CM: mark evidence invalid/unavailable

---

## K) Minimal governance pins to prevent drift (Oracle Store)

This section pins *who is allowed to do what* around Oracle Store so it stays a sealed boundary and never turns into “a bucket people mess with.”

### K1) Writer authority: who can write oracle packs

**[PIN] Only the Data Engine (or an Engine-controlled packer wrapper) may write to Oracle Store pack roots.**

* “Controlled wrapper” means a thin runner that executes engine invocations and performs sealing, but it must be **functionally equivalent to engine write authority** and must not rewrite or edit artifacts after the fact.

**Explicit non-authority:**

* SR must never write engine outputs or gate artifacts into Oracle Store.
* WSP must never write to Oracle Store.
* IG must never write to Oracle Store (except possibly for *its own* derived debug artifacts elsewhere, never into oracle pack roots).
* Humans/tools must not “fix” packs by overwriting objects.

This directly supports the “sealed world boundary” and keeps provenance clean.

---

### K2) Immutability enforcement: how we prevent overwrite “accidents”

We can enforce immutability at three layers. v0 doesn’t need all three, but we should pin the intended posture.

**Layer 1 — Naming / partitioning discipline (logical immutability)**

* Packs are under unique pack roots (`packs/<oracle_pack_id>/...`).
* Pack id is derived from OracleWorldKey (+ engine release), so reruns either:

  * reuse the exact same pack (idempotent), or
  * produce a new pack id deliberately (new identity).
    This prevents “same path, different content” by construction.

**Layer 2 — Storage policy (mechanical immutability)**

* Dev/prod: deny `PutObject` overwrite within sealed pack roots; allow only “create-if-absent” semantics for objects.
* Optionally enable bucket versioning/object lock for WORM-like guarantees (prod posture).

**Layer 3 — Seal protocol (commit guard)**

* Seal object is written last; once seal exists, no further writes are allowed under that prefix.
* Any attempt to write after seal is treated as a governance violation.

**[PIN] v0 minimum:** Layer 1 + seal protocol.
**Prod target:** add Layer 2 for mechanical enforcement.

---

### K3) Change control: what must be governed as explicit “facts”

Oracle Store isn’t a streaming system, but it is **truth infrastructure**, so changes that affect reproducibility must be explicit.

**Governed changes:**

1. **Adding new engine outputs** to the catalogue (changes what “a world” contains).
2. **Changing gate verification methods** (changes what PASS means).
3. **Changing the oracle pack layout tokens** (breaks locators).
4. **Retention/deletion policy changes** (affects ability to replay/audit).
5. **Promotion/import of packs across environments** (if you add a shared library later).

These should follow the same governance posture you pinned platform-wide: versioned, auditable, no silent mutation.

---

### K4) Provenance: what must be recorded so packs stay interpretable

**[PIN] Every sealed pack must carry a small repro manifest at root** (see section I), containing:

* OracleWorldKey tokens
* engine release/build
* digests/versions of:

  * `engine_outputs.catalogue.yaml`
  * `engine_gates.map.yaml`
  * key schemas (at least locator + gate receipt + canonical envelope)

This prevents “we have the bytes but don’t know how to interpret them.”

---

### K5) Access control: who can read oracle packs (and how)

We already pinned “keyed reads only” and “entrypoint is SR join surface.” Governance adds:

* **Read principals**:

  * SR verifier principal (read evidence + outputs)
  * WSP principal (read traffic targets + part files)
  * IG pull principal (if PULL mode enabled)
  * DLA evidence principal (if evidence lane enabled)
  * CM oracle lane principal (if enabled; restricted)
* **Least privilege**:

  * WSP should not have permission to read non-traffic oracle outputs by default.
  * CM should only read specific truth_products outputs (if oracle lane enabled).
  * Only SR should read gate bundles broadly (attester role).

**[PIN] Writer principal is the most restricted and most audited.**
Writes are rare; reads are frequent.

---

### K6) The “no ad hoc tooling” rule (how drift happens in practice)

**[PIN] Humans and ad hoc scripts must not modify Oracle Store pack contents.**
If you need to debug or explore:

* copy data **out** to a scratch area, or
* read by locator in a read-only way.

If you need to “fix” a world:

* generate a **new** pack (new identity),
* publish a **new** SR run mapping,
* never patch the old pack.

This is the immutable truth story.

---

### K7) Minimal K-section pins (v0)

1. **Engine-only writer** for Oracle Store packs.
2. **No overwrites after seal**; seal written last; pack immutable thereafter.
3. **Pack repro manifest** must record interpretation versions (catalogue/gate map/schemas).
4. **Least-privilege readers**; WSP reads traffic only; SR reads evidence broadly; CM/DLA are fenced lanes.
5. **No ad hoc mutation**; correction is new pack + new SR mapping.

---

## L) Relationship to WSP (materialized oracle world → outside-world stream)

This section pins the **interface boundary** between Oracle Store and WSP so:

* WSP can stream *correctly* and *cheaply*,
* Oracle Store stays a sealed boundary (not a query system),
* and we don’t drift back into “bulk ETL.”

### L1) The one-sentence relationship

**Oracle Store holds the sealed world; WSP reveals the sealed world as a paced stream, but only through SR’s declared refs.**

Or even tighter:

> Oracle Store is the *tape*; WSP is the *tape head*; SR tells WSP which tape to mount.

### L2) What WSP is allowed to assume Oracle Store guarantees

**[PIN] Oracle Store guarantees only storage + immutability properties, not semantic convenience.**

WSP may assume:

1. **Immutability**

* Once a pack is SEALED_OK, the bytes at referenced keys do not change.

2. **Locator addressability**

* SR-provided `engine_output_locator.path` resolves to actual objects under the pack root (or is explicitly missing/optional).
* If the locator uses a multipart pattern (`part-*`), the part files exist under that directory (or the output is absent/optional).

3. **Gate artifacts exist where the engine/gate-map says they exist**

* Oracle Store contains raw gate bundles/flags/index files at the expected paths (it doesn’t validate them; it stores them).

4. **Pack root has a tiny “repro manifest”**

* WSP can read it if needed to confirm interpretation versions (usually SR already did this; WSP might only need it for diagnostics).

That’s it. No more.

### L3) What WSP must NOT assume (drift bans)

This is where “bulk ETL” creeps back in.

**WSP must not assume:**

* It can “list all packs” or “find latest pack.”
  It must never browse the oracle. Entry is via SR join surface only.

* It can query “give me all events for January” as a server-side operation.
  Oracle Store isn’t a query service.

* Physical file order is meaningful.
  Parquet part ordering is not a semantic ordering.

* It can read huge spans “just to be safe.”
  That turns streaming into batch.

### L4) What WSP needs from SR to use Oracle Store safely

WSP should not “figure out” oracle interpretation. SR is the attester and map owner.

So WSP requires SR’s `run_facts_view` to provide, at minimum:

* **traffic allowlist**: which engine outputs are eligible to become traffic
  - **v0:** use `output_roles` + `locators` (only `business_traffic` outputs with locators)
  - **planned:** `traffic_targets[]` (explicit allowlist) and `traffic_delivery_mode`
* **resolved locators** for those outputs (full path, not templates)
* **pins** `{manifest_fingerprint, parameter_hash, scenario_id, run_id, seed}`
* **proof completeness cues**:

  * required gate receipts exist and PASS (or refs to them)
  * instance-proof binding exists when required
  * `content_digest` present when required

WSP’s stance: “If SR says READY and facts view is complete, I can stream. If not, I pause/fail-closed.”

### L5) The minimal per-output “streamability” contract

For each traffic target output, WSP needs two things to stream without semantic parsing:

1. **Domain time extraction**

* WSP needs a deterministic way to extract `ts_utc` for pacing/windowing.

**Authority pin (v0):**

* Prefer a column literally named `ts_utc`.
* If not present, SR/run policy must provide a **time_column mapping per output_id** (WSP does not guess).
  - **v0:** we assume `ts_utc` is present for traffic outputs in the current engine catalogue.

2. **Stable row identity for event_id**

* WSP must mint deterministic `event_id` using `row_pk_tuple`.

**Authority pin (v0):**

* The PK definition must come from the engine catalogue (or SR’s extracted copy of it for that output_id).
* WSP does not use row index, file position, or arrival order as identity.

This keeps WSP from becoming “a semantic engine.”

### L6) How WSP reads oracle artifacts without turning into batch

**[PIN] WSP reads in bounded windows + bounded in-flight.**

Operationally, that means:

* WSP never reads beyond its current simulated-time window (“no future leakage”).
* WSP never buffers unbounded future events.
* WSP is allowed to list/expand part files **only within the locator directory** (for `part-*` outputs), then reads them incrementally.
* Cursor/progress is receipt-gated: WSP advances only when IG outcomes are terminal.

### L7) Optional optimization: derived streaming indices (but not in Oracle Store)

If performance becomes an issue (e.g., “to emit a 1-second window I must scan many parquet row groups”), we can add *derived* indices — but not by mutating Oracle Store.

**Authority pin:**

* Any indexing acceleration is a **derived cache** owned by WSP (or an auxiliary “indexer” component), stored outside Oracle Store pack roots.
* Oracle Store remains immutable; indices can be deleted/rebuilt.

This preserves the boundary: Oracle Store = truth bytes, WSP = delivery.

### L8) The compatibility story with legacy IG pull

If you keep `PULL` mode as a fallback:

* Oracle Store’s contract supports it naturally (IG pull reads by locator too).
* WSP’s event shaping is designed to match IG’s existing engine-pull framing conventions (`event_type=output_id`, deterministic `event_id`, standardized payload provenance blocks), so downstream can’t tell which mode delivered the traffic (except via operational metadata).

**Critical pin:** the run declares `traffic_delivery_mode` so IG pull and WSP stream never run together.

### L9) Minimal L-section pins (v0)

1. Oracle Store provides immutable bytes; WSP provides paced streaming.
2. WSP never scans packs; SR join surface is the only entrypoint.
3. WSP reads only SR-declared `business_traffic` targets by resolved locator.
4. Streamability requires deterministic `ts_utc` extraction + deterministic PK-based `event_id`.
5. WSP reads bounded windows; no future leakage; bounded in-flight; receipt-gated progress.
6. Any performance indices are derived caches outside Oracle Store, never mutations inside it.
7. Legacy IG pull remains compatible, but mode is exclusive per run.

---
