# State 2B.S6 — Virtual-merchant edge routing

## 1. **Document metadata & status (Binding)**

**Component:** Layer-1 · Segment **2B** — **State-6 (S6)** · *Virtual-merchant edge routing (branch)*
**Document ID:** `seg_2B.s6.virtual_edge_routing`
**Status:** `alpha` *(normative; semantics lock when marked `frozen`)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer-1 Governance**
**Effective date:** **2025-11-05 (UTC)**

**Authority chain (Binding).**
**JSON-Schema packs** are the **sole shape authorities**: 2B pack for policies and any S6 trace shape; Layer-1 pack for the RNG envelope/core logs. **Dataset Dictionary** governs ID→path/partitions/format. **Artefact Registry** is metadata only (ownership/licence/retention).   

**Normative cross-references (Binding).**
S6 SHALL treat the following surfaces as authoritative:

* **Prior state evidence (2B.S0):** `s0_gate_receipt_2B`, `sealed_inputs_v1` (fingerprint-scoped; proves sealed inputs for this fingerprint). *(S6 relies on the receipt; it does not re-hash upstream bundles.)* 
* **Routing policies (token-less; S0-sealed):**
  `route_rng_policy_v1` (declares Philox stream/substreams & budgets for **edge routing**),
  `virtual_edge_policy_v1` (eligible `edge_id`s, weights/attrs). *(Both referenced in the 2B schema pack’s policy section.)* 
* **Alias artefacts (context only in v1):** `s2_alias_index`, `s2_alias_blob` (integrity contracts live in 2B pack). 
* **Layer RNG envelope & core logs (run-scoped):** `schemas.layer1.yaml#/$defs/rng_envelope`, `#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log`. *(Partitions `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`.)* 

**Segment invariants (Binding).**

* **When S6 triggers.** S6 is a *branch* that runs **only** for arrivals where the merchant is flagged `is_virtual=1`; non-virtual arrivals are fully handled by S5 and **bypass** S6 (no draw, no edge). *(Consistent with S5’s runtime role and layer RNG law.)* 
* **Run identity (logs/evidence):** RNG **core logs** and **event streams** are always partitioned by **`[seed, parameter_hash, run_id]`**; S6 appends **one** trace row after **each** event append, per the layer law. 
* **Plan/egress reads:** Any 2B/2A tables S6 references (context) are selected at **`[seed, fingerprint]`** via **Dictionary-only** resolution (no literal paths, no network I/O). *(Same catalogue discipline as S5.)*  
* **Gate law:** **No PASS → No read.** S6 must see valid S0 receipt + sealed inventory for this fingerprint before any read. 

> With this header, S6 is anchored to the same authorities and identity rails as S0–S5: schemas govern **shape**, the Dictionary governs **selection & partitions**, the Registry governs **metadata**, and the **layer RNG envelope** governs evidence and counters.

---

## 2. **Purpose & scope (Binding)**

**Purpose.** Execute the **virtual-merchant edge router**: for any arrival belonging to a merchant flagged **`is_virtual = 1`**, choose a **network edge** (e.g., CDN/PoP or country edge) and attach `{edge_id, ip_country, edge_lat, edge_lon}` **without altering** S5’s decision surface (tz-group/site) or the merchant’s settlement clock. The operation is **RNG-bounded & reproducible** and consumes **exactly one** Philox single-uniform draw **per virtual arrival** (and **zero** draws for non-virtual arrivals). Evidence is emitted under the **layer run-scoped RNG envelope**. 

**Scope (included).** S6 SHALL:

* **Resolve authorities by Dataset Dictionary IDs only** (subset-of-S0 rule in force). Required inputs are **token-less** policy packs sealed at S0 — `route_rng_policy_v1` (declares the routing/edge stream, budgets, counter law) and **`virtual_edge_policy_v1`** (eligible `edge_id`s, weights/attrs). Selection is by the **exact S0-sealed** `path` + `sha256_hex`; no literal paths; no network I/O. *(Anchor for `virtual_edge_policy_v1` is defined in the 2B pack alongside other policy anchors.)*
* **Bypass non-virtual traffic.** If `is_virtual = 0`, S6 performs **no edge pick and consumes no RNG draws** (the arrival remains fully governed by S5). 
* **Virtual edge selection (v1).** Build (or read, if later approved as an option) a per-merchant edge distribution from the sealed edge policy; **draw exactly one** single-uniform from the **routing/edge stream** (declared in `route_rng_policy_v1`) and decode via alias mechanics to pick `edge_id`; then **attach attributes** from the sealed policy (`ip_country`, `edge_lat`, `edge_lon`). RNG events and core logs are written under **`[seed, parameter_hash, run_id]`** with the standard envelope and one **trace** append **after each event**. 
* **Identity & provenance.** `created_utc` for any diagnostic emission **echoes S0 `verified_at_utc`**; any optional S6 diagnostics (if later registered) must adopt the **run-scoped** partition law used by layer RNG logs. 

**Out of scope.** S6 does **not**: re-route physical merchants; recompute S5 group/site choices; modify S2 alias artefacts; alter 2A time-zone legality; perform audits/CI (S7) or publish a PASS bundle (S8); or read beyond Dictionary-declared assets sealed at S0. These authorities remain with **S5/S2/S4** and the **layer logging envelope**. 

**Determinism & numeric discipline.** IEEE-754 **binary64**, ties-to-even; stable serial reductions in any Σ; **open-interval** uniforms mapped from Philox counters; fixed **one-draw** budget per virtual arrival; counters strictly monotone (no reuse, no wrap) and reconciled via the programme’s **rng_trace_log** totals. 

---

## 3. **Preconditions & sealed inputs (Binding)**

**3.1 Gate & run-identity (must hold before any read)**

* **S0 evidence present** for this `manifest_fingerprint`: `s0_gate_receipt_2B` **and** `sealed_inputs_v1` exist at `[fingerprint]` and validate against the 2B schema pack; S6 **relies** on this receipt and **does not** re-hash upstream bundles. 
* **Subset-of-S0 rule.** Every asset S6 reads **must** appear in the **S0 sealed inventory** for this fingerprint. Resolution is **Dataset-Dictionary-only** (IDs below); **no literal paths**. 

**3.2 Inputs required by S6 (sealed; read-only)**
Resolve **by ID** under the run identity `{ seed, manifest_fingerprint }` fixed at S0.

* **Routing RNG policy (token-less; S0-sealed):**
  `route_rng_policy_v1` — declares the **routing_edge** stream/substreams and budgets (one single-uniform per **virtual** arrival). **Shape:** `schemas.2B.yaml#/policy/route_rng_policy_v1`. **Selection:** by the **exact S0-sealed** `path` **and** `sha256_hex` (policy files have `partition = {}`).

* **Virtual edge policy (token-less; S0-sealed):**
  **`virtual_edge_policy_v1`** — declares eligible `edge_id`s and their **weights** (or country→edge weights), plus attributes `{ip_country, edge_lat, edge_lon}` and any decode/layout hints if used. **Selection:** by the **exact S0-sealed** `path` **and** `sha256_hex`.
  *Catalogue note:* this ID is **registered** in the 2B **Dataset Dictionary** and **Artefact Registry** (token-less; selection by S0-sealed path + digest).

* **Context (read-only; optional in v1):**
  S6 **does not require** S2/S4 tables to run. If present, S6 may reference S2 alias artefacts **for integrity echo only** (no decoding in S6):
  `s2_alias_index@seed={seed}/fingerprint={manifest_fingerprint}` (**shape:** `#/plan/s2_alias_index`) and
  `s2_alias_blob@…` (**shape:** `#/binary/s2_alias_blob`). 

* **Runtime inputs (not sealed artefacts):**
  The S5 router supplies per-arrival fields `{merchant_id, utc_timestamp, utc_day, tz_group_id, site_id, is_virtual}` at runtime; they are **not** catalogue assets and carry the run lineage `{seed, parameter_hash, run_id}`. (RNG core logs and events remain **run-scoped**, never fingerprint-partitioned.) 

**3.3 Selection & partition discipline (binding)**

* **Token-less policies** (`route_rng_policy_v1`, **`virtual_edge_policy_v1`**) **must** be selected by the **exact S0-sealed** `path` **and** `sha256_hex`; their `partition` in S0 inventories is `{}` (schema allows empty maps). 
* **Partitioned datasets** (if consulted for echo) use **exactly** `[seed, fingerprint]` per the Dictionary; any embedded identity **must** byte-equal the path tokens. 

**3.4 Integrity & compatibility pre-checks (abort on failure)**

* **Gate evidence:** S0 receipt & inventory for this fingerprint exist and validate. 
* **Policy minima:** `virtual_edge_policy_v1` **must** declare, at minimum: a non-empty set of `edge_id`s; a probability law over those edges (or a country→edge mapping that induces one); and attributes for each edge: `ip_country` ∈ ISO-3166-1 alpha-2, `edge_lat ∈ [−90,90]`, `edge_lon ∈ (−180,180]`. (Row-level checks in §9.)
* **Catalogue discipline:** all reads resolve **by ID**; any literal path or non-sealed asset → `DICTIONARY_RESOLUTION_ERROR` / `PROHIBITED_LITERAL_PATH`. (Codes enumerated in §10.) 
* **RNG envelope readiness:** layer **core logs** (`rng_audit_log`, `rng_trace_log`) and event rows follow the **run-scoped** partition law `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` and carry the standard envelope. 

**3.5 Prohibitions (binding)**

* **No network I/O.**
* **No literal paths.**
* **No mutation** of any input artefact; S6 writes only RNG evidence (and an **optional** diagnostics log if later registered), following the run-scoped log envelope. 

**3.6 Notes on v1 scope (still binding on behaviour)**

* **Option-A only in v1.** S6 derives the edge distribution **from `virtual_edge_policy_v1`**; there are **no** approved prebuilt S6 edge-alias artefacts in the current Dictionary. If a future minor introduces `s6_edge_alias_index/blob`, S6 MAY read them without changing outcomes. 

> Net: S6 only runs when **`is_virtual=1`**, reads **token-less, S0-sealed policies** by **Dictionary ID**, emits RNG evidence under the **layer log envelope**, and never touches `[seed,fingerprint]` plan/egress surfaces. With `virtual_edge_policy_v1` registered in the catalogue, this section is **green** against your existing 2B contracts.

---

## 4. **Inputs & authority boundaries (Binding)**

**4.1 Authority chain (who governs what)**

* **JSON-Schema packs** are the **sole shape authorities**: 2B pack for S6 policies/trace; **Layer-1 pack** for RNG envelope/core logs; **2A pack** for `site_timezones` (context only).
* **Dataset Dictionary** is the **catalogue authority** (IDs → paths/partitions/format). **Resolve by ID only.** 
* **Artefact Registry** supplies ownership/licensing and does **not** override shapes/partitions. 
* **Gate law (subset-of-S0):** S6 may read **only** assets sealed in S0 for this fingerprint. 

**4.2 Inputs (read-only), partitions, shapes & exact use**
S6 SHALL read **only** the assets below; all are **sealed** and **Dictionary-resolved**:

* **`route_rng_policy_v1`** — token-less policy (**S0-sealed path + sha256**); declares the **routing_edge** stream/substreams and **one single-uniform draw per virtual arrival**. **Shape:** `schemas.2B.yaml#/policy/route_rng_policy_v1`. 
* **`virtual_edge_policy_v1`** — token-less policy (**S0-sealed path + sha256**); declares eligible `edge_id`s, edge weights (or country→edge weights), and attributes `{ip_country, edge_lat, edge_lon}`. **Catalogue note:** this ID is **present** in the **2B Dictionary/Registry** (token-less; selection by S0-sealed path + digest).
* **Context (optional, no decode in v1):** `s2_alias_index` / `s2_alias_blob` at **`[seed,fingerprint]`** may be inspected **only** for sealed integrity echo; S6 does **not** scan/guess inside the blob. **Shapes:** `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`. 
* **Runtime fields (from S5):** `{merchant_id, utc_timestamp, utc_day, tz_group_id, site_id, is_virtual}` are **not catalogue assets**; they carry run lineage `{seed, parameter_hash, run_id}`.

**4.3 Partition & identity discipline (binding)**

* **Token-less policies** (`route_rng_policy_v1`, `virtual_edge_policy_v1`) have `partition = {}` in receipts; selection is by the **exact S0-sealed** `path` **and** `sha256_hex`. 
* **Any partitioned read** (e.g., S2 context) MUST use **exactly** `[seed, fingerprint]` and obey **path↔embed equality** where identities appear. 

**4.4 RNG evidence boundary (binding)**

* **Core logs & envelope:** `rng_audit_log`, `rng_trace_log`, and event rows are **run-scoped** under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` and carry the **Layer-1 RNG envelope**.
* **Event family (S6):** exactly **one** single-uniform event per **virtual** arrival on the **routing_edge** stream (family **registered in the Layer-1 pack**); append **one** trace row **after each** event. (Shapes/partitioning follow the layer log law.) 

**4.5 Authority boundaries (what S6 SHALL NOT do)**

* Do **not** re-route physical merchants (`is_virtual=0`) or alter S5’s `(tz_group_id, site_id)` decision surface.
* Do **not** re-encode or modify S2 artefacts; use the index only for integrity echo. 
* **No literal paths. No network I/O.** Dictionary-only resolution; **write-once** behaviour applies only to S6 logs/events (and any optional S6 diagnostics if later registered). 

These boundaries keep S6’s reads **unambiguous, sealed, and replayable**, and its evidence **run-scoped** and consistent with the Layer-1 RNG logging posture. 

---

## 5. **Outputs (datasets) & identity (Binding)**

**5.1 Primary egress**
S6 is a **runtime branch**. It produces **no mandatory fingerprint-scoped egress**; S5/S2/S4 remain the authoritative tables. (S6 only augments virtual arrivals with an edge pick.) 

**5.2 RNG evidence (required for virtual arrivals)**
S6 **MUST** write RNG evidence under the **run-scoped** envelope:

* **Core logs (run identity):**
  `rng_audit_log` → `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`
  `rng_trace_log` → `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`
  *(Schema: layer pack core logs; partitions `[seed, parameter_hash, run_id]`.)* 

* **Event family (virtual edge picks):** one **single-uniform** event **per virtual arrival** on the **routing_edge** stream (**family registered in the Layer-1 pack**). Each row carries the **standard RNG envelope** (`before/after`, `blocks=1`, `draws="1"`), is partitioned by `[seed, parameter_hash, run_id]`, and S6 **appends exactly one** `rng_trace_log` row **after each event append**.

*Zero-virtual case:* if a run has no `is_virtual=1` arrivals, S6 writes **no edge-event rows**; core logs/trace remain valid (no new increments).

**5.3 Optional diagnostic dataset (policy-gated)**
If diagnostics are enabled and the **Dataset Dictionary registers** an ID, S6 **MAY** emit a per-arrival log:

* **ID (when registered):** `s6_edge_log` *(optional)*

* **Partitioning:** **`[seed, parameter_hash, run_id, utc_day]`** (run-scoped lineage, matching RNG logs).
  Include `manifest_fingerprint` as a **column** with **path↔embed equality**; **do not** use fingerprint as a partition key. Writer order = **arrival order**; format = `jsonl`; **write-once + atomic publish**.
  *(This mirrors S5’s optional selection log posture.)*

* **Row shape (owned by 2B pack):** `schemas.2B.yaml#/trace/s6_edge_log_row` *(fields-strict; defined in §6).*
  Minimum fields: `{ merchant_id, is_virtual, utc_timestamp, utc_day, tz_group_id, site_id, edge_id, ip_country, edge_lat, edge_lon, rng_stream_id, ctr_edge_hi, ctr_edge_lo, manifest_fingerprint, created_utc }`. (Types reuse Layer-1 `$defs`.) 

**5.4 Identity & immutability (binding)**

* **Run-scoped evidence only:** all RNG logs/events (and the optional `s6_edge_log`) are **run-scoped** under `[seed, parameter_hash, run_id]`; plan/egress reads remain at `[seed, fingerprint]`.
* **Write-once + atomic publish:** no partial files; retries must be **byte-identical** or use a **new `run_id`**. Path↔embed equality holds wherever lineage is embedded. 

**5.5 No other persisted outputs**
S6 **MUST NOT** write to fingerprint-scoped plan/egress surfaces (`s1_site_weights`, `s2_alias_*`, `s4_group_weights`, `site_timezones`). Those remain read-only. 

> Net effect: S6 adds **run-scoped RNG evidence** (one event per virtual arrival) and, if registered, an **optional** edge diagnostics log aligned with the Layer-1 logging envelope—while leaving all **authoritative** fingerprint-scoped datasets untouched.

---

## 6. **Dataset shapes & schema anchors (Binding)**

**6.1 Shape authority**
JSON-Schema is the **sole** shape authority. S6 binds to anchors in **`schemas.2B.yaml`** (policies + S6 trace row) and the **Layer-1 pack** for the RNG envelope/core logs. The **Dataset Dictionary** governs ID→path/partitions/format; the **Artefact Registry** is metadata only.   

---

**6.2 Referenced input anchors (read-only; sealed in S0)**
S6 SHALL resolve and consume exactly these shapes by **Dictionary ID**:

* **Routing RNG policy:** `schemas.2B.yaml#/policy/route_rng_policy_v1` — declares the **routing_edge** stream/substreams and budgets (one single-uniform per **virtual** arrival). Dict ID: `route_rng_policy_v1` (token-less file; selection = exact S0-sealed path + digest). 

* **Virtual edge policy:** **`schemas.2B.yaml#/policy/virtual_edge_policy_v1`** — declares eligible `edge_id`s, edge weights / country→edge weights, and attributes `{ip_country, edge_lat, edge_lon}`.
  **Catalogue note:** `virtual_edge_policy_v1` is **present** in the 2B Dictionary/Registry (token-less; selection by S0-sealed path + digest).  

* **(Context only, optional in v1)** S2 alias artefacts: `schemas.2B.yaml#/plan/s2_alias_index`, `#/binary/s2_alias_blob`. Dict IDs: `s2_alias_index`, `s2_alias_blob` at `[seed, fingerprint]`. **S6 does not decode** them; parity checks only if consulted.  

---

**6.3 Optional diagnostic dataset — `s6_edge_log` (policy-gated)**
This dataset is **optional**. It SHALL be emitted **only if** the Dataset Dictionary registers an ID `s6_edge_log` with the partition law below. When enabled, its **row shape** is owned by a 2B trace anchor:

* **Anchor (2B pack):** `schemas.2B.yaml#/trace/s6_edge_log_row` *(fields-strict).*
  **Required fields (non-nullable unless noted):**
  `merchant_id` (`id64`), `is_virtual` (bool), `utc_timestamp` (`rfc3339_micros`), `utc_day` (ISO date),
  `tz_group_id` (`iana_tzid`), `site_id` (`id64`),
  `edge_id` (string), `ip_country` (`iso2`), `edge_lat` (number), `edge_lon` (number),
  `rng_stream_id` (string), `ctr_edge_hi` (`uint64`), `ctr_edge_lo` (`uint64`),
  `manifest_fingerprint` (`hex64`), `created_utc` (`rfc3339_micros`).
  *(IDs/timestamps/counters/tz domains reuse Layer-1 `$defs`.)* 

* **Partitioning (Dictionary authority):** **`[seed, parameter_hash, run_id, utc_day]`** (run-scoped lineage, matching RNG logs). `manifest_fingerprint` **must** appear as a **column** and **byte-equal** the run fingerprint; **do not** use it as a partition key. Writer order = **arrival order**; format = `jsonl`; **write-once + atomic publish**. *(Mirrors S5’s optional selection log posture.)* 

> **Anchor note:** `#/trace/s6_edge_log_row` is defined in the 2B pack and reuses Layer-1 `$defs` (mirrors S5 trace row style).

---

**6.4 RNG evidence (Layer-1 catalog; authoritative shapes)**
S6 produces **one single-uniform event per virtual arrival** on the **routing_edge** stream. Event rows carry the standard **RNG envelope**; core logs follow the run-scoped law:

* **Envelope & core logs:**
  `schemas.layer1.yaml#/$defs/rng_envelope`, `#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log` — partitions **`[seed, parameter_hash, run_id]`**. S6 appends exactly **one** `rng_trace_log` row **after each** event append. 

* **Event family (registered in Layer-1 pack):** `rng_event.cdn_edge_pick` (single-uniform; `blocks=1`, `draws="1"`). S6 binds budgets/order to the layer rules.

---

**6.5 Common `$defs` reused by these anchors**
From **`schemas.layer1.yaml`**: `hex64`, `uint64`, `id64`, `rfc3339_micros`, `iana_tzid`, `iso2`.
From **`schemas.2B.yaml`**: `$defs.partition_kv` with **`minProperties: 0`** (token-less assets allowed in receipts/inventory).  

---

**6.6 Format & storage (Dictionary authority)**

* **Policies (token-less):** `route_rng_policy_v1` (present) and **`virtual_edge_policy_v1`** (present) — single files; selection by **exact S0-sealed path + digest**. 
* **S2 artefacts (context):** `s2_alias_index` (JSON) and `s2_alias_blob` (binary) at **`[seed, fingerprint]`**. 
* **Optional `s6_edge_log` (if registered):** `jsonl` at **`[seed, parameter_hash, run_id, utc_day]`** with schema-ref `schemas.2B.yaml#/trace/s6_edge_log_row`. *(If the Dictionary does not register it, S6 MUST NOT write it.)* 

---

**6.7 Structural & identity constraints (binding)**

* All rows bound by §6 are **fields-strict** (no extra properties).
* **Path↔embed equality** holds wherever lineage is embedded (e.g., `manifest_fingerprint` column in `s6_edge_log` equals the run fingerprint).
* Writer order for the optional log is **arrival order**; RNG events must preserve **event order** and append trace totals accordingly. 

---

## 7. **Deterministic algorithm (RNG-bounded) (Binding)**

**Overview.** S6 runs **only** for arrivals where `is_virtual = 1`. Each such arrival consumes **exactly one** Philox single-uniform draw to choose an `edge_id` from a **sealed, per-merchant edge distribution** declared in `virtual_edge_policy_v1`. All other work is RNG-free and deterministic.

---

### 7.1 Resolve authorities & initialise (RNG-free)

1. **Resolve sealed inputs (Dictionary-only; subset-of-S0).**
   Load `route_rng_policy_v1` and `virtual_edge_policy_v1` by **ID** (token-less; select by S0-sealed `path` + `sha256_hex`). No literal paths; no network I/O.

2. **Policy pre-flight (hard abort on failure).**

   * Parse `virtual_edge_policy_v1`; verify **minima**: non-empty `edge_id` set; valid weight law (either explicit per-edge probs that sum to 1±ε, or an equivalent rule that deterministically induces such a law); attributes for **every** edge (`ip_country` ISO-2; `edge_lat ∈ [−90,90]`; `edge_lon ∈ (−180,180]`).
   * Fix a **canonical, deterministic order** of edges per merchant (e.g., lexicographic by `edge_id`), and store the binary64 probability vector in that order.

3. **RNG wiring.**
   Obtain from `route_rng_policy_v1` the **routing_edge** stream/substream mapping and budgets (single-uniform). Event family name is reserved as **`cdn_edge_pick`**. Events and core logs use the **run-scoped** envelope `[seed, parameter_hash, run_id]`; **append one** `rng_trace_log` row **after each** event append.

4. **Deterministic caches (ephemeral).**

   * `EDGE_ALIAS[m]`: per-merchant alias arrays (`prob[]`, `alias[]`) over that merchant’s edge distribution.
     Build on first use from the policy’s canonical order; builders are **RNG-free**. Cache presence/eviction **must not** change outcomes.

---

### 7.2 Definitions (RNG-free)

* **Open-interval uniform** `u ∈ (0,1)`: mapped from Philox counters by the programme’s layer law (never 0 or 1).
* **Alias build** (Walker/Vose; deterministic): given binary64 probs `p_i>0` in canonical order, construct `prob[0..K−1]∈(0,1)` and `alias[0..K−1]∈{0..K−1}` with stable serial reductions (ties-to-even).
* **Alias decode (O(1))**: with `u`, let `j=⌊u·K⌋`, `r=u·K−j`; pick `j` if `r<prob[j]` else `alias[j]`.

---

### 7.3 Per-arrival procedure (Binding)

Given an arrival `(merchant_id=m, utc_timestamp=t, utc_day=d, tz_group_id, site_id, is_virtual)` from the S5 decision path:

**A) Bypass non-virtual arrivals (no RNG).**
If `is_virtual = 0` → **bypass**: do **not** pick an edge; **no** RNG draws; **no** S6 logs/events.

**B) Virtual edge pick (exactly one draw).**

1. **Ensure alias is available (RNG-free).**
   If `EDGE_ALIAS[m]` is missing, **build** it from the sealed policy’s per-merchant edge distribution in canonical edge order.

2. **Draw & decode.**
   Consume **one** single-uniform from the **routing_edge** stream (family `cdn_edge_pick`) at the next 128-bit counter; **decode** with `EDGE_ALIAS[m]` to select index `k` and thus `edge_id`.

3. **Attach attributes (RNG-free).**
   Look up `edge_id` in the sealed policy and attach:
   `ip_country`, `edge_lat`, `edge_lon`.

4. **Coherence checks (RNG-free; abort on failure).**

   * `edge_id` exists in the sealed policy’s edge set for merchant `m`.
   * `ip_country` is ISO-3166-1 alpha-2 (whitelisted by policy).
   * `edge_lat ∈ [−90,90]`, `edge_lon ∈ (−180,180]`.

5. **Emit evidence (ordered).**

   * **Append event row** to `cdn_edge_pick` (envelope: stream id, `before/after` counters, `blocks=1`, `draws="1"`).
   * **Append one** `rng_trace_log` row **after** the event append (cumulative totals).
   * **If diagnostics are enabled** and `s6_edge_log` is registered, append one JSONL row (partition `[seed, parameter_hash, run_id, utc_day]`) with:
     `{ merchant_id, is_virtual, utc_timestamp, utc_day, tz_group_id, site_id, edge_id, ip_country, edge_lat, edge_lon, rng_stream_id, ctr_edge_hi, ctr_edge_lo, manifest_fingerprint, created_utc }`,
     where `created_utc =` S0 `verified_at_utc` and writer order **equals arrival order**.

---

### 7.4 Determinism & numeric discipline (Binding)

* **One draw per virtual arrival** exactly; zero for non-virtual.
* **Open-interval** uniforms; binary64 arithmetic; stable serial reductions; no data-dependent reorders.
* **Cache behaviour** must not affect outcomes: building/evicting/rebuilding aliases yields identical edge choices for the same arrivals.
* **No scanning/guessing** inside any binary artefact; selections are from the **sealed** edge distribution only.

---

### 7.5 RNG accounting & reconciliation (Binding)

* **Budgets:** each virtual arrival emits **one** `cdn_edge_pick` row with envelope `blocks=1`, `draws="1"`.
* **Counters:** `after − before == 1` (128-bit), strictly increasing within the run; no wrap.
* **Trace totals:** for the run, `rng_trace_log.total_draws == #virtual_arrivals`.
* **Streams/substreams:** must match `route_rng_policy_v1` (routing_edge). Mis-wiring is a hard error.

---

### 7.6 Prohibitions (Binding)

* Do **not** alter S5’s `(tz_group_id, site_id)`; S6 only **adds** edge metadata for virtuals.
* Do **not** generate additional RNG draws (no hidden draws in alias builders or attribute lookup).
* Do **not** read beyond S0-sealed, Dictionary-declared assets; **no** network I/O; **no** literal paths.
* Do **not** write to any fingerprint-scoped plan/egress surface.

> Result: For fixed `{seed, manifest_fingerprint}` and sealed policy bytes, S6 yields **bit-replayable** edge selections—with **exactly one** event per virtual arrival—and preserves all Layer-1 identity, logging, and authority boundaries.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

**8.1 Lineage tokens & where they live (authoritative)**

* **Run identity (RNG logs/events):** `{ seed, parameter_hash, run_id }`. All RNG **core logs** and **event streams** are partitioned by this triple under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`. S6 follows the same envelope and partitions. 
* **Plan/egress identity (read surfaces):** `{ seed, manifest_fingerprint }`. S6 reads S1/S2/S3/S4 (and 2A `site_timezones` if consulted) strictly at **`[seed, fingerprint]`** per the Dictionary. 
* **Optional S6 diagnostics:** if `s6_edge_log` is registered, it is **run-scoped** at **`[seed, parameter_hash, run_id, utc_day]`** and includes `manifest_fingerprint` as a **column** (not a partition key). This mirrors S5’s optional selection log.

**8.2 Partition selection (binding)**

* All reads resolve **by Dataset Dictionary ID** at the **exact** partitions declared there; token-less policies are selected by the **S0-sealed** `path` + `sha256_hex` (their `partition` is `{}`). **No literal paths. No network I/O.**

**8.3 Path↔embed equality (binding)**
Where lineage appears **both** in path and payload (e.g., `manifest_fingerprint` column in the optional `s6_edge_log`), values **MUST** be byte-equal to the path tokens. Violations are hard errors. (Same law used in your Layer-1 specs.) 

**8.4 Writer order & file layout (binding)**

* **RNG evidence:** for each **virtual** arrival, append **one** `cdn_edge_pick` event row; **after each event append, append exactly one** `rng_trace_log` row (cumulative totals). Event rows must keep the same per-arrival order they were produced in. 
* **Optional `s6_edge_log`:** writer order **must equal arrival order** within each `(seed, parameter_hash, run_id, utc_day)` partition; single JSONL per partition is recommended (don’t rely on inter-file ordering). 

**8.5 Immutability & atomic publish (binding)**
All S6 outputs (events/logs and optional diagnostics) are **write-once** and published via **atomic move**. Any retry must produce **byte-identical** bytes; otherwise use a new `run_id`. 

**8.6 Merge discipline (binding)**

* **No cross-run merges.** Never merge files across different `{seed, parameter_hash, run_id}`.
* **No cross-partition merges.** Do not coalesce different `utc_day` partitions. If compaction is required, publish a brand-new partition atomically with **identical bytes** (idempotent rule). 

**8.7 Single-writer guarantee (binding)**
Each RNG event family path and each optional `s6_edge_log` partition MUST have a **single logical writer**. Parallelism is allowed only across **disjoint** partitions and must preserve arrival order within a partition. (Keeps trace reconciliation sound.) 

**8.8 Prohibitions (binding)**

* **No literal paths; no network I/O;** Dictionary-only resolution.
* **No writes** to fingerprint-scoped plan/egress surfaces (`s1_site_weights`, `s2_alias_*`, `s3_day_effects`, `s4_group_weights`, `site_timezones`). Those remain read-only.

**8.9 Evidence hooks (what validators will check)**

* Exact partition selection vs Dictionary; **path↔embed equality** on any embedded lineage; event ordering (per-arrival), and **trace-after-event** discipline; write-once + atomic publish; idempotent re-emit; and (if diagnostics enabled) arrival-order preservation and correct run-scoped partitions. These mirror the proven laws already enforced in S5 and the layer RNG envelope.

> Net: S6’s outputs are **run-scoped, append-only, immutable**, and its reads are **fingerprint-scoped** and sealed—perfectly aligned with your Layer-1 catalogue and logging posture.

---

## 9. **Acceptance criteria (validators) (Binding)**

> All validators are **mandatory** unless scoped to the **optional** `s6_edge_log`. Codes ⟨…⟩ refer to S6’s canonical error table (section 10).

**V-01 — Gate evidence present (S0)**

* **Check:** For this fingerprint, `s0_gate_receipt_2B` **and** `sealed_inputs_v1` exist at `[fingerprint]` and are schema-valid.
* **Fail →** ⟨2B-S6-001 S0_RECEIPT_MISSING⟩. 

**V-02 — Subset-of-S0 + token-less policy selection**

* **Check:** Every S6 input is in the **S0 sealed inventory**; token-less policies (`route_rng_policy_v1`, **`virtual_edge_policy_v1`**) are selected by **exact S0-sealed `path` + `sha256_hex`** (their `partition` is `{}`).
* **Fail →** ⟨2B-S6-020 DICTIONARY_RESOLUTION_ERROR⟩ / ⟨2B-S6-070 PARTITION_SELECTION_INCORRECT⟩. 

**V-03 — Dictionary-only resolution & exact partitions**

* **Check:** No literal paths; no network I/O. Any partitioned reads (context) use **exactly** `[seed,fingerprint]`. Policies are token-less.
* **Fail →** ⟨2B-S6-020⟩ / ⟨2B-S6-021 PROHIBITED_LITERAL_PATH⟩ / ⟨2B-S6-023 NETWORK_IO_ATTEMPT⟩. 

**V-04 — Policy minima (virtual edges)**

* **Check:** `virtual_edge_policy_v1` declares a **non-empty** `edge_id` set; a deterministic probability law (per-edge or country→edge induced) summing to **1 ± ε**; and attributes for each edge: `ip_country` ∈ ISO-3166-1 alpha-2, `edge_lat ∈ [−90,90]`, `edge_lon ∈ (−180,180]`.
* **Fail →** ⟨2B-S6-030 POLICY_SCHEMA_INVALID⟩ / ⟨2B-S6-031 POLICY_MINIMA_MISSING⟩.

**V-05 — Bypass law (non-virtual)**

* **Check:** If `is_virtual = 0`, S6 performs **no edge pick** and **emits no RNG event**.
* **Fail →** ⟨2B-S6-040 BYPASS_FLAG_INCOHERENT⟩.

**V-06 — Edge alias determinism (Option-A)**

* **Check:** Per-merchant edge alias is built **RNG-free** from the sealed policy in a **canonical edge order**; Σ(probabilities)=1±ε; decode law is standard O(1) alias.
* **Fail →** ⟨2B-S6-041 EDGE_ALIAS_DECODE_INCOHERENT⟩.

**V-07 — Edge attribute presence & domain**

* **Check:** For the chosen `edge_id`, policy provides `ip_country`, `edge_lat`, `edge_lon` and all lie in domain.
* **Fail →** ⟨2B-S6-060 EDGE_ATTR_MISSING⟩.

**V-08 — RNG budget: one single-uniform per **virtual** arrival**

* **Check:** Exactly **one** event row per virtual arrival on the **routing_edge** stream (family reserved as `cdn_edge_pick`), with envelope `blocks=1`, `draws="1"`. After **each** event append, **append exactly one** `rng_trace_log` row (cumulative).
* **Fail →** ⟨2B-S6-050 RNG_DRAWS_COUNT_MISMATCH⟩. 

**V-09 — Counters: monotone & no wrap**

* **Check:** For every event, `after − before == 1` (128-bit); counters strictly increase; no wrap within a run.
* **Fail →** ⟨2B-S6-051 RNG_COUNTER_NOT_MONOTONE⟩ / ⟨2B-S6-052 RNG_COUNTER_WRAP⟩. 

**V-10 — Streams/substreams match routing policy**

* **Check:** Event `rng_stream_id` (and any substream labels) match `route_rng_policy_v1`’s **routing_edge** declaration.
* **Fail →** ⟨2B-S6-053 RNG_STREAM_MISCONFIGURED⟩. 

**V-11 — Trace reconciliation (run-scoped)**

* **Check:** `rng_trace_log.total_draws == #virtual_arrivals` for the run; equals the count of `cdn_edge_pick` rows.
* **Fail →** ⟨2B-S6-050⟩. 

**V-12 — Optional `s6_edge_log` (only if registered)**

* **Check:** If the Dictionary registers `s6_edge_log`, rows conform to `schemas.2B.yaml#/trace/s6_edge_log_row`; partitions are **`[seed,parameter_hash,run_id,utc_day]`**; **writer order = arrival order**; column `manifest_fingerprint` exists and **byte-equals** the run fingerprint; `created_utc` echoes S0’s `verified_at_utc`.
* **Fail →** ⟨2B-S6-071 PATH_EMBED_MISMATCH⟩ / ⟨2B-S6-080 IMMUTABLE_OVERWRITE⟩ / ⟨2B-S6-081 NON_IDEMPOTENT_REEMIT⟩.

**V-13 — Immutability & atomic publish**

* **Check:** All S6 outputs (events/logs, optional diagnostics) are **write-once**; publish by atomic move; any retry must produce **byte-identical** bytes or use a **new `run_id`**.
* **Fail →** ⟨2B-S6-080⟩ / ⟨2B-S6-081⟩. 

**V-14 — No writes to fingerprint-scoped plan/egress surfaces**

* **Check:** S6 writes **only** run-scoped evidence; it does **not** write to `[seed,fingerprint]` datasets (`s1_site_weights`, `s2_alias_*`, `s3_day_effects`, `s4_group_weights`, `site_timezones`).
* **Fail →** ⟨2B-S6-090 PROHIBITED_WRITE⟩. 

**V-15 — Deterministic replay (spot-check)**

* **Check:** Replaying a deterministic sample of **virtual** arrivals yields identical `{edge_id, ip_country, edge_lat, edge_lon}` and identical RNG evidence bytes (given identical sealed policies and run identity).
* **Fail →** ⟨2B-S6-095 REPLAY_MISMATCH⟩.

**Notes / anchors these validators rely on:**

* **Layer RNG envelope & core logs** (run-scoped): `rng_audit_log`, `rng_trace_log`. 
* **2B Dictionary** (IDs, partitions): shows policy packs including `route_rng_policy_v1` and `virtual_edge_policy_v1`, plus the exact gate artefacts.
* **S5 optional log pattern** (for S6’s optional log lineage): run-scoped `[seed,parameter_hash,run_id,utc_day]`, path↔embed equality.

Passing **V-01…V-15** demonstrates S6 reads **only sealed, catalogued inputs**, emits **exactly one event per virtual arrival** under the **run-scoped RNG envelope**, preserves **identity & immutability**, and keeps outcomes **bit-replayable**.

---

## 10. **Failure modes & canonical error codes (Binding)**

> **Severity classes:** **Abort** (hard stop; S6 MUST NOT continue) and **Warn** (record + continue).
> **Where surfaced:** S6 **run-report** (STDOUT JSON), and—if enabled—`s6_edge_log` context fields. RNG-related failures also annotate the **RNG event rows** / **core logs** (audit/trace) which are run-scoped under `[seed, parameter_hash, run_id]` per the Layer-1 envelope.  

---

### 10.1 Gate & catalogue discipline

**2B-S6-001 — S0_RECEIPT_MISSING** · *Abort*
**Trigger:** `s0_gate_receipt_2B` and/or `sealed_inputs_v1` absent/invalid at `[fingerprint]`.
**Detect:** V-01. **Remedy:** publish valid S0 for this fingerprint; fix schema/partition. 

**2B-S6-020 — DICTIONARY_RESOLUTION_ERROR** · *Abort*
**Trigger:** Any input not resolved by **Dataset Dictionary ID** (wrong ID/path family/format).
**Detect:** V-02/V-03. **Remedy:** use Dictionary-only resolution (no literals). 

**2B-S6-021 — PROHIBITED_LITERAL_PATH** · *Abort*
**Trigger:** Literal filesystem/URL read attempted.
**Detect:** V-03. **Remedy:** replace with Dictionary ID resolution. 

**2B-S6-023 — NETWORK_IO_ATTEMPT** · *Abort*
**Trigger:** Any network access during S6.
**Detect:** V-03. **Remedy:** remove network I/O; consume only sealed artefacts. 

**2B-S6-070 — PARTITION_SELECTION_INCORRECT** · *Abort*
**Trigger:** A partitioned read isn’t **exactly** `[seed,fingerprint]`, or a token-less policy isn’t selected by **S0-sealed** `path`+`sha256_hex`.
**Detect:** V-02/V-03. **Remedy:** fix partition tokens / policy selection semantics. 

**2B-S6-071 — PATH_EMBED_MISMATCH** · *Abort*
**Trigger:** Any embedded lineage (e.g., `manifest_fingerprint` column in optional logs) differs from path tokens.
**Detect:** V-12. **Remedy:** echo path tokens byte-for-byte. 

---

### 10.2 Policy integrity & minima

**2B-S6-030 — POLICY_SCHEMA_INVALID** · *Abort*
**Trigger:** `virtual_edge_policy_v1` fails schema/parse.
**Detect:** V-04. **Remedy:** fix policy to match the 2B policy anchor. *(Both `route_rng_policy_v1` and `virtual_edge_policy_v1` are registered as token-less, S0-sealed policies selected by exact path + digest.)* 

**2B-S6-031 — POLICY_MINIMA_MISSING** · *Abort*
**Trigger:** `virtual_edge_policy_v1` does not declare a non-empty `edge_id` set, a probability law that sums to `1±ε`, or required attributes (`ip_country`, `edge_lat`, `edge_lon`) for every edge.
**Detect:** V-04. **Remedy:** supply minima; re-seal in S0.

---

### 10.3 Bypass & decode coherence

**2B-S6-040 — BYPASS_FLAG_INCOHERENT** · *Abort*
**Trigger:** Arrival marked `is_virtual=0` yet S6 produced an edge pick (or drew RNG), or vice-versa.
**Detect:** V-05. **Remedy:** fix bypass gating so physical merchants skip S6.

**2B-S6-041 — EDGE_ALIAS_DECODE_INCOHERENT** · *Abort*
**Trigger:** Per-merchant edge alias built from policy is invalid (empty slice / out-of-range decode / Σp not ≈1).
**Detect:** V-06. **Remedy:** fix policy edge set or weights; rebuild alias deterministically.

**2B-S6-060 — EDGE_ATTR_MISSING** · *Abort*
**Trigger:** Chosen `edge_id` lacks `ip_country` or geographic attributes, or they fall outside domain.
**Detect:** V-07. **Remedy:** complete attributes in the sealed policy.

---

### 10.4 RNG budgets, counters, streams

**2B-S6-050 — RNG_DRAWS_COUNT_MISMATCH** · *Abort*
**Trigger:** Draws per **virtual** arrival ≠ **1**, or `rng_trace_log.total_draws ≠ #virtual_arrivals`.
**Detect:** V-08/V-11. **Remedy:** emit exactly one `cdn_edge_pick` event per virtual arrival and reconcile trace totals. 

**2B-S6-051 — RNG_COUNTER_NOT_MONOTONE** · *Abort*
**Trigger:** 128-bit counter not strictly increasing (`after − before ≠ 1`) within a run.
**Detect:** V-09. **Remedy:** one increment per event; fix counter mapping. 

**2B-S6-052 — RNG_COUNTER_WRAP** · *Abort*
**Trigger:** 128-bit counter overflow/wrap.
**Detect:** V-09. **Remedy:** adjust counter ranges/sharding; never reuse counters. 

**2B-S6-053 — RNG_STREAM_MISCONFIGURED** · *Abort*
**Trigger:** Event `rng_stream_id`/substreams don’t match the `routing_edge` declaration in `route_rng_policy_v1`.
**Detect:** V-10. **Remedy:** bind to routing-edge stream as per policy anchor. 

---

### 10.5 Identity, immutability & logging (optional dataset included)

**2B-S6-080 — IMMUTABLE_OVERWRITE** · *Abort*
**Trigger:** Target run-scoped partition already exists and bytes differ (events/logs or optional `s6_edge_log`).
**Detect:** V-13/V-12. **Remedy:** write-once; retries must be byte-identical or use a new `run_id`. 

**2B-S6-081 — NON_IDEMPOTENT_REEMIT** · *Abort*
**Trigger:** Re-publishing produces byte-different output for identical inputs.
**Detect:** V-13/V-12. **Remedy:** ensure idempotent re-emit or bump `run_id`. 

**2B-S6-082 — ATOMIC_PUBLISH_FAILED** · *Abort*
**Trigger:** Staging/rename not atomic, or post-publish verification failed for events/logs.
**Detect:** V-13/V-12. **Remedy:** stage → fsync → single atomic move; verify final bytes. 

**2B-S6-090 — PROHIBITED_WRITE** · *Abort*
**Trigger:** Any write to fingerprint-scoped plan/egress surfaces (`s1_site_weights`, `s2_alias_*`, `s3_day_effects`, `s4_group_weights`, `site_timezones`).
**Detect:** V-14. **Remedy:** S6 writes only run-scoped logs/events (and optional diagnostics). 

---

### 10.6 Determinism & replay

**2B-S6-095 — REPLAY_MISMATCH** · *Abort*
**Trigger:** Replaying a deterministic sample of **virtual** arrivals yields non-identical `{edge_id, ip_country, edge_lat, edge_lon}` or non-identical RNG evidence bytes under the same sealed inputs.
**Detect:** V-15. **Remedy:** fix stream wiring, stable ordering, and cache semantics until bit-replay passes. 

---

### 10.7 Code ↔ validator map (authoritative)

| Validator (from §9)                                 | Codes on fail                              |
|-----------------------------------------------------|--------------------------------------------|
| **V-01 Gate evidence present**                      | 2B-S6-001                                  |
| **V-02 Subset-of-S0 + token-less policy selection** | 2B-S6-020, 2B-S6-070                       |
| **V-03 Dictionary-only & exact partitions**         | 2B-S6-020, 2B-S6-021, 2B-S6-023, 2B-S6-070 |
| **V-04 Policy minima (virtual edges)**              | 2B-S6-030, 2B-S6-031                       |
| **V-05 Bypass law (non-virtual)**                   | 2B-S6-040                                  |
| **V-06 Edge alias determinism (Option-A)**          | 2B-S6-041                                  |
| **V-07 Edge attribute presence & domain**           | 2B-S6-060                                  |
| **V-08 RNG budget: one per virtual arrival**        | 2B-S6-050                                  |
| **V-09 Counters: monotone / no wrap**               | 2B-S6-051, 2B-S6-052                       |
| **V-10 Streams/substreams match policy**            | 2B-S6-053                                  |
| **V-11 Trace reconciliation**                       | 2B-S6-050                                  |
| **V-12 Optional `s6_edge_log` lineage**             | 2B-S6-071, 2B-S6-080, 2B-S6-081            |
| **V-13 Immutability & atomic publish**              | 2B-S6-080, 2B-S6-081, 2B-S6-082            |
| **V-14 No writes to plan/egress surfaces**          | 2B-S6-090                                  |
| **V-15 Deterministic replay**                       | 2B-S6-095                                  |

These codes align S6 with your existing **Dictionary** (IDs/partitions), **2B schema pack** (policy anchors), and **Layer-1 RNG envelope** (core logs/events), ensuring sealed reads at `[seed,fingerprint]` and run-scoped evidence at `[seed,parameter_hash,run_id]`.

---

## 11. **Observability & run-report (Binding)**

### 11.1 Purpose

Emit one **structured JSON run-report to STDOUT** that proves what S6 **read** (sealed policies), what it **did** (1 draw per *virtual* arrival), and what **evidence** it wrote (RNG core logs + the `cdn_edge_pick` event stream, and—if registered—the optional `s6_edge_log`). The report is **diagnostic (non-authoritative)**; authoritative shapes for RNG evidence live in the **Layer-1 schema pack**, and ID→paths/partitions are governed by the **Dataset Dictionary**.

### 11.2 Emission

* S6 **MUST** print the run-report to **STDOUT** exactly once at successful completion (and on abort, if possible). Persisting a copy is allowed but **non-authoritative**; downstream MUST NOT depend on it. 

### 11.3 Top-level shape (fields-strict)

The run-report **MUST** contain exactly the keys below (no extras). Timestamps/IDs use Layer-1 `$defs`.

```
{
  "component": "2B.S6",
  "fingerprint": "<hex64>",
  "seed": "<uint64>",
  "parameter_hash": "<hex64>",
  "run_id": "<hex32>",
  "created_utc": "<rfc3339_micros>",                  // echo S0.receipt.verified_at_utc
  "catalogue_resolution": {
    "dictionary_version": "<semver>",
    "registry_version": "<semver>"
  },
  "policy": {                                         // routing RNG policy (token-less; S0-sealed)
    "id": "route_rng_policy_v1",
    "version_tag": "<string>",
    "sha256_hex": "<hex64>",
    "rng_engine": "philox",
    "rng_stream_id": "<routing_edge>",
    "draws_per_virtual": 1
  },
  "policy_edge": {                                     // virtual edge policy (token-less; S0-sealed)
    "id": "virtual_edge_policy_v1",
    "version_tag": "<string>",
    "sha256_hex": "<hex64>",
    "edges_declared": <int>                            // count of edge_ids in sealed policy
  },
  "inputs_summary": {                                  // all Dictionary-resolved
    "alias_index_path": "<.../s2_alias_index/...>",    // if consulted (context only)
    "alias_blob_path":  "<.../s2_alias_blob/...>"      // if consulted (context only)
  },
  "rng_accounting": {
    "events_edge": <uint64>,                           // #cdn_edge_pick rows
    "events_total": <uint64>,                          // == events_edge
    "draws_total": <uint64>,                           // == virtual_arrivals
    "first_counter": {"hi": "<uint64>", "lo": "<uint64>"},
    "last_counter":  {"hi": "<uint64>", "lo": "<uint64>"}
  },
  "counts": {
    "arrivals_total": <uint64>,
    "virtual_arrivals": <uint64>,                      // MUST == draws_total
    "non_virtual_bypassed": <uint64>
  },
  "logging": {
    "edge_log_enabled": <bool>,
    "edge_log_partition?": "[seed,parameter_hash,run_id,utc_day]"   // present iff enabled
  },
  "validators": [ { "id": "V-01", "status": "PASS|FAIL|WARN", "codes": ["2B-S6-0xx", ...] }, ... ],
  "samples": {                                         // bounded, deterministic
    "selections": [                                    // <= 20 rows
      {"merchant_id": "<id64>", "utc_day": "YYYY-MM-DD",
       "site_id": "<id64>", "edge_id": "<string>", "ip_country": "<ISO2>"}
      ...
    ]
  },
  "summary": { "overall_status": "PASS|FAIL", "warn_count": <int>, "fail_count": <int> },
  "environment": { "engine_commit?": "<string>", "python_version": "<string>", "platform": "<string>", "network_io_detected": <int> }
}
```

* **Partition law for RNG evidence (authoritative):** all event/core-log paths are **run-scoped** under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`.
* **Core logs:** `rng_audit_log`, `rng_trace_log` shapes and partitioning are fixed by the **Layer-1** pack; S6 must append **one** trace row **after each** event append. 
* **Event stream:** `cdn_edge_pick` is a **single-uniform** family (**registered in the Layer-1 pack**), so each row’s envelope **must** show `blocks=1`, `draws="1"`. (Same envelope law as other layer events.) 

### 11.4 Deterministic samples (bounded)

* `samples.selections` includes at most **20** edge picks chosen by a deterministic sampler (e.g., fixed stride over the event stream). These samples are **replayable** for the same sealed inputs and run identity. (Do **not** include counters here—those are already reported in `rng_accounting`.) 

### 11.5 Reconciliations (MUST hold)

* `events_total == events_edge`.
* `draws_total == virtual_arrivals`.
* `rng_trace_log.total_draws == draws_total`.
  Any mismatch is a **hard FAIL** (validator V-11 / code ⟨2B-S6-050⟩). 

### 11.6 Optional diagnostics (`s6_edge_log`, if registered)

* If the Dictionary registers `s6_edge_log`, the report **MUST** state `edge_log_enabled=true` and echo its partition template **`[seed,parameter_hash,run_id,utc_day]`**. Rows **must** follow the 2B trace row anchor (`#/trace/s6_edge_log_row`), preserve **arrival order**, be **write-once**, and obey **path↔embed equality** on `manifest_fingerprint`. (If not registered, S6 **must not** write it.) 

### 11.7 No new authorities

This section creates **no** new dataset authorities. Shapes remain governed by the **Layer-1** RNG pack (envelope/core logs) and the **2B** pack (policy and optional S6 trace row); ID→path/partition is governed by the **Dataset Dictionary**; the **Artefact Registry** stays metadata-only.

> Net: the S6 run-report is a tight, fields-strict **STDOUT JSON** that proves sealed policy selection, **1 draw per virtual arrival**, run-scoped RNG evidence (`audit`/`trace` + `cdn_edge_pick`), and—if enabled—the optional `s6_edge_log` lineage, all aligned to the layer logging envelope.

---

## 12. **Performance & scalability (Informative)**

**Goal.** Keep S6 cost **O(1)** per **virtual** arrival (exactly one alias decode + one RNG event), with deterministic caches and run-scoped logging that scale across merchants, days, and workers—without touching any fingerprint-scoped plan/egress surfaces. 

### 12.1 Cost model (asymptotics)

Let:

* `V` = number of **virtual** arrivals in the run.
* `K_m` = number of edges declared for merchant *m* in `virtual_edge_policy_v1`.

Then:

* **Alias builds (first use per merchant):** `∑_m O(K_m)` from the sealed policy (RNG-free).
* **Per virtual arrival:** `O(1)` (one single-uniform draw + one alias decode).
* **Non-virtual arrivals:** bypass S6 → **O(0)** work, **0** draws.
  Evidence writes (event row + one trace append) are run-scoped and independent of fingerprint. 

### 12.2 Caching (deterministic, RNG-free)

* **`EDGE_ALIAS[m]`**: per-merchant alias (`prob[]`, `alias[]`) over edges declared by policy; built on first use in a canonical order (e.g., lexicographic by `edge_id`).
* **Determinism requirement:** cache presence/eviction **must not** change outcomes; re-building yields identical picks (stable serial reductions; binary64 ties-to-even).
* **Memory envelope (rule of thumb):** two arrays per merchant, size `K_m` (float64 + minimal-width int). Use **LRU by bytes** if needed; rebuild deterministically when evicted.

### 12.3 I/O pattern

* **Cold start:** load token-less policies (`route_rng_policy_v1`, `virtual_edge_policy_v1`) by **Dictionary ID** (selected via S0-sealed path + digest). No network I/O; no literal paths. 
* **Hot loop:** only touches in-memory `EDGE_ALIAS[m]` and appends run-scoped RNG evidence (event row + trace). No reads of `[seed,fingerprint]` tables are required to run S6. 

### 12.4 RNG evidence overhead

* **Exactly one** event per **virtual** arrival (`cdn_edge_pick`; `blocks=1`, `draws="1"`), plus **one** `rng_trace_log` append **after each** event append. Paths are **`…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`**. 
* End-to-end reconciliation: `draws_total == #virtual_arrivals` and equals the count of `cdn_edge_pick` rows (the run-report MUST check this). 

### 12.5 Concurrency & sharding (safe patterns)

* **Partitioning:** RNG core logs/events are **run-scoped** (`[seed, parameter_hash, run_id]`), so sharding is safe **across** `run_id` or by disjoint **utc_day** partitions within the same run—as long as each partition has a **single logical writer** and per-partition arrival order is preserved. 
* **Counters:** ensure substreams/counter ranges are disjoint per worker as declared in the routing policy; counters remain strictly monotone and never wrap. 

### 12.6 Throughput posture

* **Decode cost:** constant time (index, compare, fallback) per virtual arrival.
* **Builder cost:** linear in `K_m`, paid once per merchant per process lifetime (amortised by cache).
* **Net:** steady-state throughput is dominated by one uniform draw + one alias decode + two log appends (event + trace).

### 12.7 Impact of policy size/shape

* Larger `K_m` increases **first-use** build time and memory for `EDGE_ALIAS[m]`, but does **not** affect per-arrival decode.
* Country→edge policies merely add a constant-time lookup to produce the edge distribution; attribute attaches (`ip_country`, `edge_lat`, `edge_lon`) are O(1) per selection. (Attributes come from the sealed policy; no external lookups.) 

### 12.8 Optional diagnostics cost

* If `s6_edge_log` is registered and enabled, write amplification is **O(V)** with partitions **`[seed, parameter_hash, run_id, utc_day]`**, writer order = arrival order, write-once + atomic publish. Disable by default for production; enable for CI/replay only. 

### 12.9 Failure-free degradation

* **Memory pressure:** evict `EDGE_ALIAS` entries (LRU by bytes) and rebuild on demand; outcomes unchanged.
* **Policy parse errors:** fail fast during cold start (policy minima validator) before producing any RNG evidence.
* **Zero-virtual runs:** skip event emission; core logs/trace remain valid (no increments), keeping reconciliation trivial. 

> Summary: S6 achieves **O(1)** steady-state cost for virtual arrivals through deterministic per-merchant alias caches, emits evidence under the **run-scoped layer envelope**, and preserves the same identity/ordering/immutability laws used in S5—so it scales linearly with **virtual** traffic and is operationally predictable.

---

## 13. **Change control & compatibility (Binding)**

**13.1 Versioning (SemVer)**

* **MAJOR** when any binding interface changes: input IDs or their partition law; RNG **engine/stream/event family name**; **draws per virtual arrival** (≠1) or event **order**; logging envelope (`[seed,parameter_hash,run_id]`); bypass semantics for `is_virtual`; or gate/identity laws. 
* **MINOR** for backwards-compatible additions: optional diagnostics/fields; registering an **optional** `s6_edge_log` dataset; adding optional policy attributes that do not change outcomes. 
* **PATCH** for wording/typo fixes only (no behaviour/shape change). (SemVer posture mirrors earlier states.) 

**13.2 Compatibility surface (stable within a major)**
Consumers MAY rely on the following remaining stable across the S6 v1.x line:

* **Inputs & selection:** S6 reads only token-less policies `route_rng_policy_v1` and `virtual_edge_policy_v1`, selected by the **exact S0-sealed** `path` + `sha256_hex` (their `partition = {}`). No literal paths; no network I/O. 
* **RNG evidence:** exactly **one** single-uniform `cdn_edge_pick` **per virtual arrival**, with the **Layer-1** RNG envelope and run-scoped partitions **`[seed,parameter_hash,run_id]`**; a single `rng_trace_log` append follows **each** event append.
* **Bypass law:** non-virtual (`is_virtual=0`) arrivals **bypass** S6 and consume **zero** draws. (S5 remains the sole site router.) 
* **Optional diagnostics:** if registered, `s6_edge_log` is **run-scoped** at **`[seed,parameter_hash,run_id,utc_day]`**, includes `manifest_fingerprint` as a **column** (path↔embed equality), writer order = arrival order, write-once + atomic publish. (Identity & lineage mirror S5’s optional log.) 

**13.3 Backward-compatible (MINOR) changes**
Allowed without breaking consumers:

* Add **optional** fields to the S6 run-report; add **optional** properties to S6-related anchors (required keys remain fields-strict). 
* Register `s6_edge_log` as an **optional** Dictionary ID (off by default) using the partition law above and a `schemas.2B.yaml#/trace/s6_edge_log_row` anchor. 
* Extend `virtual_edge_policy_v1` with **non-behavioural** metadata (e.g., display names) or optional attributes; outcomes must remain bit-identical.

**13.4 Breaking (MAJOR) changes**
Require a new S6 **major** and coordinated updates to packs:

* Change **draws per virtual arrival** (≠1), RNG engine, event family name (`cdn_edge_pick`), or event ordering; or alter the run-scoped logging envelope. 
* Change input IDs, path families, or partitioning; make `s6_edge_log` **mandatory** or alter its partition law; write to fingerprint-scoped plan/egress surfaces. 
* Alter how the edge distribution is derived such that outcomes change for the same sealed policy bytes.

**13.5 Coordination with neighbouring states**

* **S5** may evolve internally so long as its outputs (runtime `(tz_group_id, site_id)` and RNG evidence) and envelope rules remain stable; S6 only augments **virtual** arrivals and must not alter S5 decisions. 
* **S2/S4/2A** changes are compatible if their anchors/partitions remain stable; S6 does **not** depend on them to run (policy-only), and any context reads remain `[seed,fingerprint]`. 

**13.6 Policy/Registry/Dictionary coordination**

* Adding the token-less policy ID **`virtual_edge_policy_v1`** to the **Dataset Dictionary** and **Artefact Registry** is a **MINOR** for S6; changing existing policy IDs, path families, or selection semantics is **MAJOR**. Registry metadata edits (owner/licence/retention) are compatible; edits affecting **existence** of required artefacts are breaking.

**13.7 Validator/code namespace stability**
Validator IDs (`V-01…`) and canonical codes (`2B-S6-…`) are **reserved**; adding new codes is allowed; changing meanings or reusing IDs is **breaking**. (Follows S1/S3/S4/S5 precedent.)

**13.8 Deprecation & migration protocol**
Publish a change log with impact, validator diffs, new anchors, and migration plan; prefer **dual-publish** (old & new side-by-side) or a consumer shim window for MAJOR transitions. 

**13.9 Rollback policy**
All S6 outputs are **write-once**; rollback = publish a new `{seed,fingerprint}`/policy bytes that reproduce last-known-good behaviour, or use a new `run_id` for evidence. No in-place mutation. 

**13.10 No new authorities**
This section adds **no** new dataset authorities. Shapes remain governed by **`schemas.2B.yaml`** (policy/trace) and the **Layer-1** pack (RNG envelope/core logs); ID→paths/partitions remain governed by the **Dataset Dictionary**; the **Artefact Registry** stays metadata-only.

> Net: within a major, S6 stays a **policy-driven, one-draw** virtual edge router with run-scoped RNG evidence and optional diagnostics aligned to the Layer-1 logging law; changes outside that scope require a coordinated **major**.

---

## Appendix A — Normative cross-references *(Informative)*

**A.1 Shape authorities (packs)**

* **2B schema pack:** `schemas.2B.yaml` — policy anchors (S6), plan/binary anchors (S2 context), and the **optional** S6 trace row anchor (if emitted). 
* **Layer-1 RNG pack:** `schemas.layer1.yaml` — **RNG envelope** (`#/$defs/rng_envelope`) and **core logs** (`#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log`).
* **2A pack (context):** `schemas.2A.yaml#/egress/site_timezones` (if consulted). *(Cited via Registry/Dictionary below.)* 

---

**A.2 2B policy anchors (token-less; S0-sealed)**

* `schemas.2B.yaml#/policy/route_rng_policy_v1` — declares **routing_edge** stream/substreams & **one single-uniform per virtual arrival**. 
* `schemas.2B.yaml#/policy/virtual_edge_policy_v1` - **edge set + weights/attrs** (`edge_id`, `ip_country`, `edge_lat`, `edge_lon`). *(Registered in 2B Dictionary/Registry; token-less; selection by exact S0-sealed path+digest.)* 

---

**A.3 S2 context (read-only; no decode in S6 v1)**

* `schemas.2B.yaml#/plan/s2_alias_index` — alias directory & blob digest. 
* `schemas.2B.yaml#/binary/s2_alias_blob` — raw alias bytes; integrity only (no scanning). 

---

**A.4 Layer RNG evidence (authoritative)**

* Envelope + IDs: `schemas.layer1.yaml#/$defs/rng_envelope`. 
* Core logs (run-scoped): `#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log`. *(S6 appends **one** trace row **after each** event append.)* 
* Event family (registered in Layer-1 pack; single-uniform): **`rng_event.cdn_edge_pick`** (`blocks=1`, `draws="1"`). 

---

**A.5 Optional diagnostics (only if registered)**

* **Row shape:** `schemas.2B.yaml#/trace/s6_edge_log_row` *(fields-strict; mirrors S5 trace style and Layer-1 `$defs`)*. 
* **Dictionary ID (when present):** `s6_edge_log` → partition **`[seed, parameter_hash, run_id, utc_day]`**; include `manifest_fingerprint` **as a column** (path↔embed equality). *(Do not use fingerprint as a partition key.)* 

---

**A.6 Dataset Dictionary IDs & partitions (catalogue authority)**
*(Resolve **by ID only**; policies are token-less and selected by S0-sealed path+digest.)*

* `route_rng_policy_v1` *(policy; token-less)* — **present**. 
* `virtual_edge_policy_v1` *(policy; token-less)* - **present** in Dictionary/Registry. 
* `s2_alias_index` @ **`[seed, fingerprint]`** — **present**. 
* `s2_alias_blob` @ **`[seed, fingerprint]`** — **present**. 
* `site_timezones` @ **`[seed, fingerprint]`** *(context; 2A egress)* — **present**. 
* *(Optional)* `s6_edge_log` @ **`[seed, parameter_hash, run_id, utc_day]`** — **register if diagnostics are desired**. 

---

**A.7 Artefact Registry (metadata only; owners/licensing/roles)**

* Policy packs (current): `route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`, **`virtual_edge_policy_v1`** — all show schema refs & owners.

> Cross-refs above are consistent with the live **2B Dictionary/Registry** and the **Layer-1 RNG pack**. The S6 catalogue is complete; **`virtual_edge_policy_v1`** is registered, and **`s6_edge_log`** remains optional (register only if diagnostics are desired).

---
