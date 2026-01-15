black-box framing:
{
""""
Through a modular lens, **Authority Surfaces (RO)** are best seen as a **world-pinned “truth pack”** with a tiny set of responsibility chunks (these are *sections/facets*, not 5 separate docs):

## Level 0

**Input:** `manifest_fingerprint` (optionally also `parameter_hash` for scoping rules)
**Output:** “the exact reference truths for this world” + how to find them

## Level 1 responsibility chunks

1. **Catalogue / Discovery**

* A single **AuthoritySurfacesCatalogue** for a given `manifest_fingerprint`
* Lists what surfaces exist and how to fetch them:

  * `surface_name`, `surface_version`, `schema_version`
  * `ref/locator`, `digest`
  * **join_keys** (the canonical keys consumers must use)

2. **Surface Retrieval**

* The rule: **fetch by ref** (prefer by-ref everywhere)
* Caching is allowed, but must not change semantics

3. **Join-Key Registry**

* The “don’t re-derive truth” guardrail
* For each surface: publish the **exact join key(s)** and any canonicalization rules

4. **Pinning + Versioning Rules**

* Selection is **world-pinned** (no implicit “latest”)
* Defines how a consumer knows it’s looking at the right version for this run/world

5. **Integrity / Evidence**

* Consumers can verify a surface matches the catalogue (digest check)
* (If you want) a lightweight “PASS evidence” idea: SR can pin catalogue digest in run ledger; downstream can refuse if mismatch

## Level 2 how it shows up operationally

* **SR** pins the world (`manifest_fingerprint`) and can record a **catalogue ref/digest** in `run_facts_view`
* **IG/EB/IEG/OFP/DF/OFS** read surfaces as needed, but **never create substitutes**

### Tiny picture

```
manifest_fingerprint
   → AuthoritySurfacesCatalogue (names + refs + digests + join_keys)
       → fetch surface by ref (RO) → join deterministically
```

""""
}


tighten vs loose split
{
""""
Here’s what I’d **tighten vs leave loose** for **Authority Surfaces (RO)**, in the **1-doc + 1-schema** posture.

## What needs tightening (pin this)

### 1) Authority boundary rules

* RO surfaces are **authoritative truth** for consumers.
* Consumers **MUST NOT** re-derive substitutes.
* Surfaces are **read-only** in the platform runtime (no downstream writes).

### 2) World pinning and selection semantics

* Surfaces are selected **by `manifest_fingerprint`** (and only by that unless you explicitly add more pins).
* **No implicit “latest”**: selection must be explicit and/or pinned by the run ledger.
* SR/Run ledger should be able to point to: **catalogue ref + digest** (optional but powerful).

### 3) Catalogue contract (this is the core contract)

Pin a single `AuthoritySurfacesCatalogue` object with required fields such as:

* `manifest_fingerprint`
* `catalogue_version` (or schema version)
* `surfaces[]` entries containing:

  * `surface_name`
  * `surface_version`
  * `schema_version`
  * `ref` (locator)
  * `digest` + `digest_alg`
  * `join_keys[]` (canonical join keys)

### 4) Join keys and canonicalization

* For each surface, publish the **exact join key(s)** (names + types).
* Any canonicalization rules (e.g., normalization, casing) must be pinned (or explicitly “none”).

### 5) Locator/ref semantics

* “Fetch by ref” rule.
* Ref is immutable for a given `manifest_fingerprint + surface_name + surface_version`.
* Addressing convention: if you use path templates, pin `fingerprint={manifest_fingerprint}` usage.

### 6) Integrity verification and mismatch behaviour

* Consumers may verify `digest` against fetched content.
* If digest/schema mismatch occurs: define whether consumer **must fail closed** or may degrade (pick one posture for v0).

### 7) Versioning posture

* Difference between `surface_version` vs `schema_version` must be clear.
* Compatibility rule: adding a new surface is allowed; changing an existing surface’s schema must bump `schema_version` (or similar).

### 8) Minimal failure/availability semantics

* What happens if a required surface is missing/unavailable:

  * fail the run, or block the consumer, or use a defined fallback (prefer fail-closed unless you explicitly allow fallbacks).

### 9) Acceptance checks (tiny)

* Given a `manifest_fingerprint`, a consumer can:

  1. fetch catalogue
  2. fetch one surface by ref
  3. join using published keys
  4. verify digest (if enabled)

---

## What can stay loose (implementation freedom)

* Storage backend (files/object store/db)
* File formats (Parquet/JSON/CSV) and compression
* How surfaces are authored/acquired (pipelines, ETL)
* How catalogue is served (static file vs API)
* Caching and replication strategy
* Indexing/query acceleration mechanics
* Operational deployment details

---

### The minimal deliverable

* **1 doc**: `authority_surfaces_ro.md` (covers the tightened rules above)
* **1 schema**: `authority_surfaces_catalogue_v0.schema.json` (catalogue + entry shapes)


""""
}


proposed doc plan + contract pack + repo layout
{
""""
Here’s a **Authority Surfaces (RO) v0-thin package** with a **small doc set (not 5)** + **1 contracts file** + **file tree**.

## AS v0-thin doc set

### **AS1 — Charter & Authority Boundaries**

* What Authority Surfaces are (RO truth sidecars)
* What they are **authoritative** for (reference truths) and **not** (no derivations, no writes)
* World-pinning rule (`manifest_fingerprint` governs selection)
* Non-goals (no pipeline authoring details, no heavy ops spec)

### **AS2 — Catalogue, Locators, Join Keys, Versioning**

* The **AuthoritySurfacesCatalogue** contract (what surfaces exist for a fingerprint)
* Entry fields: `surface_name`, `surface_version`, `schema_version`, `ref`, `digest`, `join_keys[]`
* “Fetch by ref” semantics + immutability expectations
* Join key canonicalization rules (if any)
* Versioning/compatibility rules (surface_version vs schema_version)
* Optional: how SR pins catalogue ref/digest in run ledger (informative)

### **AS3 — Integrity, Failure Posture, Acceptance**

* Digest verification posture + mismatch behavior (fail-closed vs degrade)
* Missing surface behavior
* Minimal security/access posture (read permissions)
* Acceptance checks (“given fingerprint → fetch catalogue → fetch surface → join keys → verify digest”)

## 1 contracts file (v0)

* `authority_surfaces_catalogue_v0.schema.json`

  * `$defs/AuthoritySurfacesCatalogue`
  * `$defs/AuthoritySurfaceEntry`
  * `$defs/JoinKeySpec`
  * `$defs/SurfaceRef` (locator shape)

## File tree

```text
docs/
└─ model_spec/
   └─ control_and_ingress/
      └─ authority_surfaces_ro/
         ├─ README.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ AS1_charter_and_authority_boundaries.md
         │  ├─ AS2_catalogue_locators_join_keys_versioning.md
         │  └─ AS3_integrity_failures_acceptance.md
         │
         └─ contracts/
            └─ authority_surfaces_catalogue_v0.schema.json
```

(As usual: examples/diagrams/decisions live **inside** AS2/AS3 appendices.)

""""
}
