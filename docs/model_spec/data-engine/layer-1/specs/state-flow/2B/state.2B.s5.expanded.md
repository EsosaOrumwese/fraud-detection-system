# State 2B.S5 — Router core (two-stage O(1): group → site)

## 1. **Document metadata & status (Binding)**

**Component:** Layer-1 · Segment **2B** — **State-5 (S5)** · *Router core (two-stage O(1): group → site)*
**Document ID:** `seg_2B.s5.router_core`
**Version (semver):** `v1.0.1-alpha`
**Status:** `alpha` *(normative; semantics lock at `frozen` in a ratified release)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer-1 Governance**
**Effective date:** **2025-11-05 (UTC)**
**Canonical location:** `contracts/specs/l1/seg_2B/state.2B.s5.expanded.v1.0.1.txt`

**Authority chain (Binding):**
**JSON-Schema pack** = shape authority → `schemas.2B.yaml`. **Dataset Dictionary** = IDs → path/partitions/format → `dataset_dictionary.layer1.2B.yaml`. **Artefact Registry** = existence/licence/retention → `artefact_registry_2B.yaml`.

**Normative cross-references (Binding):**
Upstream evidence & inputs that S5 SHALL treat as authoritative:

* **Prior state evidence (2B.S0):** `s0_gate_receipt_2B` and `sealed_inputs_2B` (manifest_fingerprint-scoped; S5 verifies presence, identity, catalogue versions). 
* **Alias artefacts (2B.S2):** `s2_alias_index` (directory & decode invariants) and `s2_alias_blob` (raw bytes; digest echoed in index). 
* **Day effects (2B.S3):** `s3_day_effects` (γ per merchant×UTC-day×tz-group). 
* **Group mixes (2B.S4):** `s4_group_weights` (RNG-free probabilities used to pick tz-group). 
* **Time-zone mapping (2A egress):** `site_timezones` (per-site IANA `tzid`, `[seed, manifest_fingerprint]`). 
* **Policies (captured/sealed at S0):** `route_rng_policy_v1` (Philox sub-streams/budgets for routing), `alias_layout_policy_v1` (alias layout/endianness/alignment). 

**Segment invariants (Binding):**

* **Run identity:** `{ seed, manifest_fingerprint }` fixed by S0; S5 resolves all IDs via the **Dictionary only** (no literal paths), enforcing Dictionary-only resolution and the **S0-evidence rule** (see §3.1).
* **Partition posture (referenced inputs):** `s4_group_weights`, `s3_day_effects`, `s1_site_weights`, and `site_timezones` are selected at **`[seed, manifest_fingerprint]`**; `s2_alias_index` and `s2_alias_blob` likewise sit under **`[seed, manifest_fingerprint]`**.
* **Gate law:** **No PASS → No read** remains in force across the segment; S5 relies on the S0 receipt (does **not** re-hash bundles). 
* **RNG posture:** **RNG-bounded, reproducible** — counter-based **Philox** with governed sub-streams per `route_rng_policy_v1`; reconciliation against the programme’s RNG trace/audit posture (events → trace totals) follows the layer-1 logs convention.
* **Numeric discipline:** binary64, round-to-nearest-even; stable serial reductions (as in S3/S4).

> With this header in place, S5 is anchored to the same authorities and identity/gate rails as S0-S4, and all cross-refs point to already-ratified surfaces and anchors.

---

### Contract Card (S5) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3.2 for full list):**
* `s0_gate_receipt_2B` - scope: FINGERPRINT_SCOPED; source: 2B.S0
* `s4_group_weights` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 2B.S4
* `s1_site_weights` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 2B.S1
* `site_timezones` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: required
* `s2_alias_index` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 2B.S2
* `s2_alias_blob` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; source: 2B.S2
* `alias_layout_policy_v1` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `route_rng_policy_v1` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required

**Authority / ordering:**
* Routing RNG envelopes + alias policy are the sole decode authorities for S5.

**Outputs:**
* `rng_event_alias_pick_group` - scope: LOG_SCOPED; gate emitted: none
* `rng_event_alias_pick_site` - scope: LOG_SCOPED; gate emitted: none
* `rng_audit_log` - scope: LOG_SCOPED; gate emitted: none (shared append-only log)
* `rng_trace_log` - scope: LOG_SCOPED; gate emitted: none (shared append-only log)
* `s5_selection_log` - scope: LOG_SCOPED; gate emitted: none (optional)

**Sealing / identity:**
* External inputs (2A egress + token-less policy packs) MUST appear in `sealed_inputs_2B` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or RNG envelope violations -> abort; no outputs published.

## 2. **Purpose & scope (Binding)**

**Purpose.** Execute the **per-arrival router** for a merchant *m* at UTC day *d* as a **two-stage O(1)** procedure:
(A) pick a **tz-group** using the **RNG-free** day mix `p_group(m,d,group)` from **S4**; then
(B) pick a **site** **within that group** via alias decode governed by the **S2** alias artefacts + policy. Results are **replayable** (counter-based Philox) and **byte-identical** under identical sealed inputs.  

**Scope (included).** S5 SHALL:

* **Resolve authorities by Dictionary IDs only**, under the run identity `{seed, manifest_fingerprint}` established at S0 (S0-evidence rule). Inputs are:
  `s4_group_weights@{seed,manifest_fingerprint}`, `s2_alias_index@{seed,manifest_fingerprint}`, `s2_alias_blob@{seed,manifest_fingerprint}`, `site_timezones@{seed,manifest_fingerprint}`, and the token-less `route_rng_policy_v1` (selected by the **S0-sealed** path/digest).  
* **Stage-A (group pick):** use S4’s `p_group` for *m,d* to build a tiny alias over that merchant’s groups and draw **exactly one** uniform to select `tz_group_id`. (S4 provides the canonical `p_group` table.) 
* **Stage-B (site pick, O(1)):** deterministically **filter S1 masses by tzid via `site_timezones`** to the chosen group and decode with the **S2 policy/layout**; draw **exactly one** uniform to select `site_id`. *(v1 binds this Option-A path; S2 does not expose group slices.)*  
* **RNG posture:** counter-based **Philox** with **two single-uniform draws per arrival** (one for group, one for site); counters are strictly monotone, reconciled against the programme’s RNG trace/audit law used in S3. 
* **Decode authority:** S5 MUST treat **`s2_alias_index` as the sole directory** and verify `blob_sha256` against the raw bytes of `s2_alias_blob` before any decode; **no scanning/guessing inside the blob.** Layout/endianness/alignment come from the index/policy echo. 
* **Mapping coherence:** enforce `tz_group_id(site_id)` from `site_timezones` equals the group picked in Stage-A. 

**Out of scope.** S5 does **not**: re-compute S4 mixes; re-encode alias tables; modify S2 artefacts; perform audits/CI (S7) or PASS bundling (S8); read beyond the inputs above; use network I/O; or resolve literal paths. Those are governed by S2/S3/S4/S7–S8 and the layer identity/gate laws.  

**Determinism & numeric discipline.** Binary64, ties-to-even; no data-dependent reorder that changes outcomes; replay with the same sealed inputs (including policy bytes) yields identical selections and, if logging is enabled, identical rows. (Mirrors S2/S3/S4’s numeric and immutability posture.)  

---

## 3. **Preconditions & sealed inputs (Binding)**

**3.1 Gate & run-identity (must be true before any read)**

* **S0 evidence present** for this `manifest_fingerprint`: `s0_gate_receipt_2B` **and** `sealed_inputs_2B`, partitioned by `[manifest_fingerprint]`. Path↔embed equality **must** hold. S5 **relies** on this receipt; it does **not** re-hash upstream bundles.  
* **S0-evidence rule.** Cross-layer/policy assets **MUST** appear in S0’s `sealed_inputs_2B`;
  within-segment datasets (`s1_site_weights`, `s2_alias_index`, `s2_alias_blob`,
  `s4_group_weights`, `site_timezones`) are **NOT** S0-sealed but **MUST** be read by
  Dictionary ID at exactly `[seed, manifest_fingerprint]`. Literal paths are forbidden.

**3.2 Inputs required by S5 (sealed; read-only)**
Resolve **by ID** under the run identity `{ seed, manifest_fingerprint }` fixed at S0.

* **Day mixes (group stage):**
  `s4_group_weights@seed={seed}/manifest_fingerprint={manifest_fingerprint}` (Parquet; PK `[merchant_id, utc_day, tz_group_id]`). **Shape:** `schemas.2B.yaml#/plan/s4_group_weights`. Used as the **sole** probability law to pick the tz-group.  

* **Per-site masses (site stage):**
  `s1_site_weights@seed={seed}/manifest_fingerprint={manifest_fingerprint}` (Parquet; writer order = PK). **Shape:** `#/plan/s1_site_weights`. Used to build the **per-group alias** (v1). 

* **Site → tz mapping (coherence):**
  `site_timezones@seed={seed}/manifest_fingerprint={manifest_fingerprint}` (Parquet; 2A egress). **Shape:** `schemas.2A.yaml#/egress/site_timezones`. Used to (i) filter S1 masses to the chosen group and (ii) assert `tz_group_id(site_id) == chosen tz_group_id`. 

* **Alias policy (layout/endianness/alignment/bit-depth):**
  `alias_layout_policy_v1` (single file; **no partition tokens**). **Shape:** `schemas.2B.yaml#/policy/alias_layout_policy_v1`. S5 uses it as the **encode/decode law** and compatibility surface for alias mechanics (even though v1 builds per-group alias in-process). Selection is by the **exact S0-sealed path + digest**.  

* **Routing RNG policy (streams/budgets):**
  `route_rng_policy_v1` (single file; **no partition tokens**). **Shape:** `schemas.2B.yaml#/policy/route_rng_policy_v1`. Declares the Philox stream/sub-stream layout and budgets for **two single-uniform draws per arrival** (group pick, site pick). Selection is by the **exact S0-sealed path + digest**.  

* **Alias artefacts (compatibility echo; presence & integrity):**
  `s2_alias_index@seed={seed}/manifest_fingerprint={manifest_fingerprint}` (JSON) and `s2_alias_blob@seed={seed}/manifest_fingerprint={manifest_fingerprint}` (binary). **Shapes:** `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`. S5 **does not** decode merchant tables in v1, but **must** verify header parity and blob integrity (pre-flight):
  `index.policy_digest == digest(alias_layout_policy_v1)` and `index.blob_sha256 == SHA256(raw bytes of s2_alias_blob)`. Abort on mismatch.  

**3.3 Selection & partition discipline (binding rules)**

* **Partitioned datasets** (`s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s4_group_weights`, `site_timezones`) **must** be selected at **exactly** `[seed={seed}, manifest_fingerprint={manifest_fingerprint}]`; path tokens **must** equal any embedded identity.  
* **Token-less policies** (`route_rng_policy_v1`, `alias_layout_policy_v1`) carry `partition = {}` in receipts/inventories (per schema); selection is by the **exact** S0-sealed `path` **and** `sha256_hex`.  

**3.4 Integrity & compatibility pre-checks (abort on failure)**

* **Gate evidence present:** the S0 receipt & inventory for this manifest_fingerprint exist and validate against `schemas.2B.yaml#/validation/*`. 
* **Alias artefact parity:** `s2_alias_index.header.layout_version`, `endianness`, `alignment_bytes`, and `quantised_bits` **must** equal the `alias_layout_policy_v1` echo; `blob_sha256` **must** equal the digest of `s2_alias_blob` raw bytes. 
* **Catalogue discipline:** all reads resolve **by ID**; any literal path or non-sealed asset → `2B-S5-020 DICTIONARY_RESOLUTION_ERROR / 2B-S5-070 PARTITION_SELECTION_INCORRECT`. (Code names per S5’s failure table.)
* **Created-time provenance:** downstream logs (if enabled) **must** echo S0 `verified_at_utc` as `created_utc`. 

**3.5 Prohibitions (binding)**

* **No network I/O.**
* **No literal paths.**
* **No mutation** of any input (S5 is a runtime decision fabric; any optional `s5_selection_log` is write-once, atomic publish, if enabled). Identity/immutability posture matches S3/S4.  

**3.6 Notes on v1 scope (informative, still binding on behaviour)**

* **Option-A only.** S5 v1 **builds per-group alias in-process** from S1 masses filtered by `site_timezones`. S2’s artefacts are sealed and integrity-checked but **not** used for per-group decode in this version (group-slice offsets are not exposed in S2 v1).  

> With these preconditions and sealed-input rules, S5 inherits the same gate, identity, and catalogue discipline as S0–S4, and all inputs are unambiguous, immutable, and reproducible for byte-identical replays.

---

## 4. **Inputs & authority boundaries (Binding)**

**4.1 Authority chain (who governs what)**

* **JSON-Schema** is the **sole shape authority**: S5 binds to anchors in `schemas.2B.yaml` (S1/S2/S4 shapes) and `schemas.2A.yaml` (2A egress). Fields, domains, PK/partitions, and strictness come **only** from these anchors. 
* **Dataset Dictionary** is the **catalogue authority** (IDs → path families, partitions, formats). S5 SHALL resolve every input **by ID only** (no literal paths). 
* **Artefact Registry** carries **existence/licence/retention/ownership**; it does **not** change shapes or partitions. 
* **Gate & S0-evidence rule.** S5 reads **only** cross-layer/policy assets sealed in **S0** for this manifest_fingerprint; evidence is the S0 receipt + sealed-inputs inventory. Within-segment reads are Dictionary-only at `[seed, manifest_fingerprint]` (S5 does **not** re-hash 1B bundles.) 

**4.2 Inputs (Dictionary IDs), partitions, shapes, and exact use (read-only)**
S5 SHALL read **exactly** these inputs, under the run identity `{seed, manifest_fingerprint}`:

* **`s4_group_weights@{seed,manifest_fingerprint}`** — day mixes per merchant×UTC-day×tz-group.
  Shape: `schemas.2B.yaml#/plan/s4_group_weights`. **Sole probability law** for Stage-A (group pick).

* **`s1_site_weights@{seed,manifest_fingerprint}`** — per-site masses used to build per-group alias (v1).
  Shape: `#/plan/s1_site_weights`; PK/writer order from the anchor.

* **`site_timezones@{seed,manifest_fingerprint}`** — site→tzid mapping (2A egress).
  Shape: `schemas.2A.yaml#/egress/site_timezones`. Used to (i) filter S1 to the chosen group and (ii) assert mapping coherence. 

* **`s2_alias_index@{seed,manifest_fingerprint}`** + **`s2_alias_blob@{seed,manifest_fingerprint}`** — alias directory + raw bytes.
  Shapes: `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`. S5 **must** pre-flight: `index.blob_sha256 == SHA256(blob)` and decode policy echo matches `alias_layout_policy_v1`; S5 **must not** scan/guess inside the blob.

* **`route_rng_policy_v1`** (single file, **no tokens**) — Philox streams/substreams & budgets for **two single-uniform draws per arrival** (group, site). Selection is by the **S0-sealed path+digest**. Shape: `#/policy/route_rng_policy_v1`. 

* **`alias_layout_policy_v1`** (single file, **no tokens**) — layout/endianness/alignment/bit-depth; referenced for S2 echo & S5 decode semantics. Selection is by the **S0-sealed path+digest**. Shape: `#/policy/alias_layout_policy_v1`. 

**4.3 Partition & identity discipline (binding)**

* **Exact partitions:** All partitioned reads use **exactly** `[seed, manifest_fingerprint]` per the Dictionary; token-less policies carry `partition = {}` in receipts/inventory (schema allows empty maps). **Path↔embed equality** MUST hold wherever identity is embedded.
* **Evidence:** Cross-layer/policy assets appear in `sealed_inputs_2B`; within-segment datasets are
  selected exactly at `[seed, manifest_fingerprint]` by ID (no literals, no wildcards). 

**4.4 Authority boundaries (what S5 SHALL NOT do)**

* **Do not** re-normalise or alter `p_group`; S4 is the **sole** authority for group probabilities. 
* **Do not** re-encode/modify S2 artefacts; S2 index is the **sole directory** and its `blob_sha256` pins the blob bytes. 
* **Do not** infer time-zone legality; `site_timezones` is authoritative for site→tzid membership. 
* **No literal paths**; **no network I/O**; **Dictionary-only** resolution. Violations are `DICTIONARY_RESOLUTION_ERROR` / `PROHIBITED_LITERAL_PATH` / `NETWORK_IO`.

**4.5 Optional diagnostics boundary (if `s5_selection_log` is enabled)**

* Logging (if policy enables it) is a **diagnostic** dataset separate from plan/egress surfaces. When present, its partitioning SHALL align with the layer RNG log envelope: **`[seed, parameter_hash, run_id, utc_day]`**, and MUST carry `manifest_fingerprint` as a column with path↔embed equality. This mirrors `rng_audit_log`/`rng_trace_log` lineage used across Layer-1.

> These boundaries make S5’s reads **unambiguous, immutable, and replayable**, and they preserve the programme’s authority split: **Schema governs shapes**, **Dictionary governs selection**, **Registry governs metadata**, and **S0** governs what is allowed to be read at all.

---

## 5. **Outputs (datasets) & identity (Binding)**

**5.1 Primary egress**
S5 is a **runtime decision fabric**. It produces **no mandatory persisted egress**: the router returns `(tz_group_id, site_id)` to the caller; stateful artefacts remain S2/S3/S4. (This mirrors your S0–S4 posture where identity comes from S0 and probability/alias authority comes from S2–S4.)

**5.2 RNG events & core logs (required when routing runs)**
S5 **MUST** append RNG evidence under the **layer RNG envelope**; partitions and lineage follow the existing law:

* **Core logs (run-scoped):**
  `rng_audit_log` → `logs/layer1/2B/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`
  `rng_trace_log` → `logs/layer1/2B/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`
  *(Append exactly **one** cumulative trace row **after each event append**.)*

* **Event families (per-arrival):** **two single-uniform streams** (group pick, site pick), each partitioned by
  `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` and carrying the standard envelope (`before/after` counters, `blocks=1`, `draws="1"`).
  *Naming note:* family names are reserved for the layer catalog and will be registered alongside their schemas; S5 consumes **two events per selection** and reconciles totals via `rng_trace_log`. 

**Identity implications.** RNG logs/layer1/2B/events are **never manifest_fingerprint-partitioned**; they bind to the run via `{seed, parameter_hash, run_id}` (manifest_fingerprint is echoed only where a schema requires it). This matches Layer-1 precedent. 

**5.3 Optional diagnostic dataset (policy-gated)**
If routing diagnostics are enabled by policy, S5 **MAY** emit a per-arrival selection log:

* **ID (when present):** `s5_selection_log` *(optional)*
* **Partitioning:** `[seed, parameter_hash, run_id, utc_day]` (router/log lineage).
  **`manifest_fingerprint` MUST appear as a column** and **byte-equal** any embedded lineage; **do not** use it as a partition key. 
* **Format:** `jsonl` (log semantics, arrival-ordered appends).
* **Writer order:** exact **arrival order** within each `(seed, parameter_hash, run_id, utc_day)` partition.
* **Schema (forward ref):** `schemas.2B.yaml#/trace/s5_selection_log_row` *(declared in §6; fields include `{merchant_id, utc_timestamp, utc_day, tz_group_id, site_id, rng_stream_id, ctr_group_hi, ctr_group_lo, ctr_site_hi, ctr_site_lo, created_utc}`).*
* **Catalogue law:** This dataset is **emitted only if** the **Dataset Dictionary** registers `s5_selection_log` with the partition spec above and that schema anchor; otherwise **MUST NOT** write. *(Dictionary governs IDs→paths/partitions; schema governs shape.)* 

**5.4 Run-report (diagnostic; non-authoritative)**
S5 **SHALL** print a **STDOUT JSON** run-report (non-authoritative): policy ids/digests, seeds/days processed, `selections_processed`, and RNG accounting (`draws_total = 2 × selections_logged`), plus first/last counters and a small deterministic sample of `{merchant_id, utc_day, tz_group_id, site_id}`. Created-time provenance **must** echo S0’s `verified_at_utc` (`created_utc`) to match S3/S4 provenance law.

**5.5 Identity, partitions, ordering & immutability (binding)**

* **Logs/events (required):** `[seed, parameter_hash, run_id]`; **write-once**, **atomic publish**, record-append only; append exactly one `rng_trace_log` row **after each** event append. 
* **Optional `s5_selection_log` (if enabled):** `[seed, parameter_hash, run_id, utc_day]`; writer order = arrival order; **write-once + atomic publish**; **path↔embed equality** wherever lineage appears. 
* **No other persisted egress** is produced by S5; probability/alias authority remains S4/S2 respectively (selected by `[seed, manifest_fingerprint]`). 

> Net effect: S5 leaves authoritative state in **S2/S3/S4**, emits **RNG evidence** under the layer log envelope, and (optionally) a **diagnostic selection log** with run-scoped partitions. This stays perfectly aligned with your existing Dictionary/Registry posture and Layer-1 identity rules.

---

## 6. **Dataset shapes & schema anchors (Binding)**

**6.1 Shape authority**
JSON-Schema is the **sole** shape authority. S5 binds to anchors in **`schemas.2B.yaml`** (2B shapes/policies) and **`schemas.2A.yaml`** (cross-segment `site_timezones`). The **Dataset Dictionary** governs ID→path/partitions/format; the **Artefact Registry** carries ownership/licence/retention only.

---

**6.2 Referenced input anchors (read-only)**
S5 SHALL resolve and consume exactly these shapes:

* **Group mixes (S4):** `schemas.2B.yaml#/plan/s4_group_weights` — per-merchant×day×tz-group probabilities. Dict ID `s4_group_weights` at `[seed, manifest_fingerprint]`. 
* **Per-site masses (S1):** `#/plan/s1_site_weights` — long-run site weights used to build per-group alias (v1). Dict ID `s1_site_weights` at `[seed, manifest_fingerprint]`. 
* **Alias artefacts (S2):** `#/plan/s2_alias_index` (directory) and `#/binary/s2_alias_blob` (raw bytes). Dict IDs `s2_alias_index`/`s2_alias_blob` at `[seed, manifest_fingerprint]`. 
* **Site→tz mapping (2A egress):** `schemas.2A.yaml#/egress/site_timezones` — membership + provenance. Dict ID `site_timezones` at `[seed, manifest_fingerprint]`. 
* **Policies (S0-sealed, token-less):** `#/policy/route_rng_policy_v1`, `#/policy/alias_layout_policy_v1`. Selection is by **exact S0-sealed path+digest**. 

---

**6.3 Optional diagnostic dataset — `s5_selection_log` (policy-gated)**
This dataset is **optional**. It SHALL be emitted **only if** the Dataset Dictionary registers an ID `s5_selection_log` with the partition law below. When enabled, its **row shape** is owned by a 2B trace anchor:

* **Anchor (2B pack):** `schemas.2B.yaml#/trace/s5_selection_log_row` *(fields-strict; anchor present in the 2B schema pack).* 
  **Required fields (non-nullable unless noted):**
  `merchant_id` (`id64`), `utc_timestamp` (`rfc3339_micros`), `utc_day` (ISO date),
  `tz_group_id` (IANA tzid), `site_id` (`id64`),
  `rng_stream_id` (string),
  `ctr_group_hi` (`uint64`), `ctr_group_lo` (`uint64`),
  `ctr_site_hi` (`uint64`), `ctr_site_lo` (`uint64`),
  `manifest_fingerprint` (`hex64`),
  `created_utc` (`rfc3339_micros`).
  *(Timestamps/IDs and numerics reuse layer defs; see `schemas.layer1.yaml#/$defs/*`.)* 

* **Partitioning (Dictionary authority):** `[seed, parameter_hash, run_id, utc_day]` (router/log lineage). `manifest_fingerprint` **must** appear as a column and **byte-equal** any embedded lineage; do **not** use it as a partition key. Pattern aligns with **rng_audit_log / rng_trace_log**. 

* **Writer policy:** append-only JSONL; writer order == **arrival order**; write-once; atomic publish. (Mirror Layer-1 log posture.) 

---

**6.4 RNG evidence (Layer-1 catalog; shapes in the layer pack)**
S5 produces **two single-uniform events per arrival** (group pick, site pick). Event rows must carry the standard **RNG envelope** from the layer schema; core logs follow the run-scoped law:

* **Envelope & core logs (authoritative shapes):**
  `schemas.layer1.yaml#/$defs/rng_envelope`,
  `#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log`; partitions `{seed, parameter_hash, run_id}`.

* **Event families (names reserved, single-uniform):**
  `rng_event.alias_pick_group`, `rng_event.alias_pick_site` — each row: envelope + event payload as defined by the layer event anchors when registered; `blocks=1`, `draws="1"`. *(Registration mirrors existing Layer-1 families and inherits their partitioning and trace-append discipline.)* 

---

**6.5 Common `$defs` reused by these anchors**
From **`schemas.layer1.yaml`** unless otherwise stated:

* `hex64` (manifest_fingerprints), `uint64` (counters), `id64` (merchant/site IDs), `rfc3339_micros` (timestamps), `iana_tzid` (tz identifiers). 
* From **`schemas.2B.yaml`**: `$defs.partition_kv` with **`minProperties: 0`** (token-less assets allowed in receipts/inventory). 

---

**6.6 Format & storage (Dictionary authority)**

* **Referenced inputs:** `s4_group_weights`, `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `site_timezones` — all partitioned by **`[seed, manifest_fingerprint]`**; formats per their entries (parquet/json/binary). 
* **Optional `s5_selection_log` (if registered):** `jsonl` at **`[seed, parameter_hash, run_id, utc_day]`** with schema-ref `schemas.2B.yaml#/trace/s5_selection_log_row`. (If not registered, S5 **MUST NOT** write it.) 

---

**6.7 Structural & identity constraints (binding)**

* All tables/log rows above are **fields-strict** (no extra columns).
* **Path↔embed equality** holds wherever lineage is embedded (e.g., `manifest_fingerprint` column == path token).
* Writer order: plan tables follow their PK; selection log (if enabled) preserves **arrival order**. 

> Net effect: S5 reads **only** shapes already ratified in 2B/2A, emits RNG evidence under the **layer log envelope**, and—if policy enables it—writes an **optional** diagnostics log whose shape and partitions are explicit and consistent with your Layer-1 logging posture.

---

## 7. **Deterministic algorithm (RNG-bounded) (Binding)**

**Overview.** S5 routes each arrival `(merchant_id=m, utc_timestamp=t)` via a **two-stage O(1)** procedure, using **exactly two single-uniform draws** (group, then site). All other steps are RNG-free and deterministic under the sealed inputs from §3–§4.

---

### 7.1 Resolve authorities & initialise (RNG-free)

1. **Resolve inputs by ID (S0-evidence rule):**
   `s4_group_weights@{seed,manifest_fingerprint}`, `s1_site_weights@{seed,manifest_fingerprint}`, `s2_alias_index@{seed,manifest_fingerprint}`, `s2_alias_blob@{seed,manifest_fingerprint}`, `site_timezones@{seed,manifest_fingerprint}`, `route_rng_policy_v1`, `alias_layout_policy_v1`.

2. **Pre-flight integrity (once per run):**
   Verify **S2 parity** before any decode:
   `s2_alias_index.blob_sha256 == SHA256(bytes(s2_alias_blob))` and the policy echo (layout_version, endianness, alignment_bytes, quantised_bits/encode_spec) matches `alias_layout_policy_v1`. **Abort** on mismatch.

3. **RNG stream wiring:**
   From `route_rng_policy_v1`, obtain the **routing stream** and two **event families**:
   `alias_pick_group` and `alias_pick_site`. Both are **single-uniform** (`blocks=1`, `draws="1"`), partitioned under `[seed, parameter_hash, run_id]` with the standard RNG envelope (counters `before/after`).
   The policy defines sub-stream derivation from `{seed, parameter_hash, run_id}`; counters are **strictly monotone** and **never reused**.

4. **Caches (ephemeral, deterministic):**

   * `GROUP_ALIAS[m, d]` → per-merchant/UTC-day tiny alias over tz-groups from **S4**.
   * `SITE_ALIAS[m, d, tz_group_id]` → per-group alias built from **S1** masses filtered by **2A** `site_timezones`.
     Both caches are **RNG-free**, built on first use, keyed exactly as shown, and may be evicted/rebuilt without changing outcomes.

---

### 7.2 Definitions used below (RNG-free)

* **UTC day**: `d = floor_UTC_day(t)` (00:00:00–23:59:59.999999 UTC).
* **Stable orderings**:
  • For groups, **read S4 rows in PK order** `(merchant_id, utc_day, tz_group_id)`; the index `g∈{0..G−1}` follows that order.
  • For sites, **read S1 rows in PK order**, then **filter** to sites whose `tzid` (from `site_timezones`) equals the chosen `tz_group_id`; the index `k∈{0..N−1}` follows that filtered order.
* **Alias builder (deterministic):** classic Walker/Vose. Given weights `w_i>0`, let `p_i = w_i / Σw` (binary64) with a **stable serial reduction** (PK order). Build `prob[0..N−1]∈(0,1)` and `alias[0..N−1]∈{0..N−1}` deterministically (no RNG).
* **Alias decode (O(1))** with **open-interval** `u∈(0,1)`:
  `j = ⌊u·N⌋`, `r = u·N − j`; **pick** `j` if `r < prob[j]` else `alias[j]`.

---

### 7.3 Per-arrival router (Binding)

Given arrival `(m, t)`:

**A) Group pick (1 uniform).**

1. Compute `d = floor_UTC_day(t)`.
2. Ensure `GROUP_ALIAS[m,d]` exists; if not, **build** from **S4** rows for `(m,d,*)` (stable PK order). **Do not** renormalise beyond S4’s values except the necessary Σ1 division described above.
3. **Draw** one uniform via **`alias_pick_group`** (routing stream).
4. **Decode** with the group alias to obtain `tz_group_id`.
5. If diagnostics are enabled, remember the group index and RNG envelope counters for the selection log row (no writes yet).

**B) Site pick within the chosen group (1 uniform).**

6. Ensure `SITE_ALIAS[m,d,tz_group_id]` exists; if not, **build** from **S1** rows for `(m,*)` **filtered** by the chosen `tz_group_id` using **`site_timezones`**.

   * **Filtering law:** keep exactly those sites whose `tzid` equals the chosen `tz_group_id`.
   * **Weights:** use **S1** `p_weight` (or equivalent) of the retained sites; compute `p_i = w_i/Σw` with **stable serial sum** in PK order.
   * **Build** deterministic alias `(prob, alias)` as in §7.2.
   * **Abort** if the filtered set is empty (no eligible sites for the chosen group).
7. **Draw** one uniform via **`alias_pick_site`** (routing stream).
8. **Decode** with the per-group alias to obtain `site_id`.
9. **Mapping coherence check (must):** assert that `tz_group_id(site_id)` from **`site_timezones`** equals the chosen `tz_group_id`. **Abort** on mismatch.

**C) Emit evidence (ordered; Binding).**

10. **Append events** in order: first `alias_pick_group`, then `alias_pick_site`. After **each** append, update `rng_trace_log` **once** (cumulative totals).
11. If `s5_selection_log` is enabled by policy, **append** one JSONL row with:
    `{ merchant_id=m, utc_timestamp=t, utc_day=d, tz_group_id, site_id, rng_stream_id, ctr_group_hi, ctr_group_lo, ctr_site_hi, ctr_site_lo, manifest_fingerprint, created_utc }`, partitioned by `[seed, parameter_hash, run_id, utc_day]`.

    * `created_utc =` S0 `verified_at_utc` (identity law).
    * Writer order **must** match **arrival order**.

---

### 7.4 Determinism & numeric discipline (Binding)

* **Two draws per arrival** exactly; no additional draws in builders or joins.
* **Open-interval uniforms** only; implementation **must** use the programme’s layer mapping from counters to `u∈(0,1)` (never generate 0 or 1).
* **Stable serial reductions** (ties-to-even; binary64) for all Σ operations; no data-dependent reorderings.
* **Cache behaviour** must not affect outcomes: building/evicting/rebuilding aliases yields **byte-identical** selections for the same arrivals.
* **No renormalisation** of **S4** `p_group` other than alias construction; **S2** artefacts are integrity-checked but **not** used for per-group decode in v1 (no group slices).

---

### 7.5 RNG accounting & reconciliation (Binding)

* **Event budgets:** each of `alias_pick_group` and `alias_pick_site` emits exactly one row with envelope `blocks=1`, `draws="1"`.
* **Counters:** per event, `after − before == 1` (in 128-bit space); counters are **strictly increasing** and **never wrap** within a run.
* **Trace reconciliation:** `rng_trace_log.total_draws == 2 × (#selections_emitted)` for the run, and equals the sum over both families.
* **Streams/substreams:** must match `route_rng_policy_v1` (names/IDs as declared); misuse is an error.

---

### 7.6 Prohibitions (Binding)

* No literal paths; no network I/O; no mutation of any input artefact.
* Do **not** re-derive or modify time-zone legality; **2A** `site_timezones` is authoritative.
* Do **not** re-encode or alter **S2** alias artefacts; use the index solely for integrity/compatibility checks.
* Do **not** change the number of draws per arrival or the event ordering.

> Result: For a fixed `{seed, manifest_fingerprint}` and sealed policy bytes, S5 yields **bit-replayable** selections and **exact RNG evidence** with two events per arrival, while preserving all Layer-1 identity and authority boundaries.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

**8.1 Lineage tokens & where they live (authoritative)**

* **Run identity (routing/log lineage):** `{ seed, parameter_hash, run_id }` — used by **RNG core logs** and **RNG events**. These surfaces are *never* manifest_fingerprint-partitioned; they sit under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`. 
* **Plan/egress identity (read surfaces):** `{ seed, manifest_fingerprint }` — used by **S1/S2/S3/S4 tables** (and 2A `site_timezones`). S5 reads them at **exactly** `[seed, manifest_fingerprint]` per the Dictionary. 
* **Optional selection log (if enabled):** partitions are **`[seed, parameter_hash, run_id, utc_day]`**, and the row **must carry** `manifest_fingerprint` as a column with **path↔embed equality**. (Aligns with your Layer-1 RNG envelope.) 

**8.2 Partition selection (binding)**

* S5 **MUST** resolve all inputs **by Dataset Dictionary ID** at the **exact** partitions declared there (no extra/missing tokens):
  `s4_group_weights@{seed,manifest_fingerprint}`, `s1_site_weights@{seed,manifest_fingerprint}`, `s2_alias_index@{seed,manifest_fingerprint}`, `s2_alias_blob@{seed,manifest_fingerprint}`, `site_timezones@{seed,manifest_fingerprint}`. Policies are token-less (selected by **S0-sealed path + digest**). **Abort** on any mismatch.

**8.3 Path↔embed equality (binding)**
Wherever lineage appears **both** in the path and in a payload/row (e.g., `manifest_fingerprint` column in selection log, or embedded identities in S2/S4), the values **MUST** be byte-equal to the path tokens. Violation is a hard error.

**8.4 Writer order & file layout (binding)**

* **RNG events:** event append order is **group pick first, then site pick** for each arrival; after **each** append, update `rng_trace_log` exactly once. 
* **Optional `s5_selection_log`:** writer order **must equal arrival order** within each `(seed, parameter_hash, run_id, utc_day)` partition. Use a **single JSONL file per partition** to avoid relying on inter-file ordering. 
* **Plan tables (S1–S4 reads):** their writer order remains their PK (S5 **does not** write these). 

**8.5 Immutability & atomic publish (binding)**

* **Write-once + atomic publish** applies to any S5-produced artefact (logs/layer1/2B/events) and to optional `s5_selection_log`. No partial files; publish by atomic move into the final path. **No in-place mutation.** 
* **Idempotent re-emit:** Re-emitting a partition (e.g., retry) is only permitted if the resulting bytes are **identical**. Otherwise, use a **new `run_id`** (and/or a new `{seed, manifest_fingerprint}` if upstream identity changed). 

**8.6 Merge discipline (binding)**

* **No cross-run merges.** Never merge files across different `{seed, parameter_hash, run_id}`. Each run produces its **own** log/event tree. 
* **No cross-partition merges.** Never coalesce different `utc_day` partitions. If compaction is required, write a **brand-new** partition atomically with the **same bytes** (idempotent rule) or a **new run_id**. 

**8.7 Single-writer guarantee (binding)**
For each `(seed, parameter_hash, run_id, utc_day)` selection-log partition (if enabled) and each RNG event family path, S5 **MUST** behave as a single logical writer. Parallelisation is allowed **only** if it targets disjoint partitions and preserves the arrival-order guarantee in each. 

**8.8 Prohibitions (binding)**

* **No literal paths**; **no network I/O**; **no writes** outside the log envelope (and optional selection log) for S5. Input plan tables remain read-only at `[seed, manifest_fingerprint]`. 

**8.9 Evidence hooks (what validators will check)**

* Exact partition selection vs Dictionary, path↔embed equality, writer order, atomic-publish & immutability, idempotent re-emit, event ordering, and trace reconciliation (`draws_total = 2 × selections_logged`). These checks mirror the law already used in S2–S4 and Layer-1 RNG logging.

> Net effect: S5’s outputs (RNG evidence, optional selection log) are **run-scoped, append-only, and immutable**, while all read surfaces remain **manifest_fingerprint-scoped plan/egress tables**. This keeps S5 perfectly aligned with your Layer-1 identity and catalogue discipline.

---

## 9. **Acceptance criteria (validators) (Binding)**

> The suite below is **PASS/FAIL**. Every validator is **mandatory** unless it’s explicitly scoped to the **optional** `s5_selection_log`. Where a code is shown in ⟨…⟩ it references S5’s canonical error codes table (section 10).

**V-01 — Gate evidence present (S0)**

* **Checks:** For this `manifest_fingerprint`, `s0_gate_receipt_2B` **and** `sealed_inputs_2B` exist at `[manifest_fingerprint]` and are schema-valid; path↔embed equality holds.
* **Fail →** ⟨2B-S5-001 S0_RECEIPT_MISSING⟩. 

**V-02 — S0-evidence & exact selection**

* **Checks:** All cross-layer/policy assets appear in **S0’s sealed inventory** for this manifest_fingerprint; all within-segment inputs are resolved by **Dictionary ID** at exactly `[seed, manifest_fingerprint]`. Policies (`route_rng_policy_v1`, `alias_layout_policy_v1`) must match the **exact** S0-sealed `path` and `sha256_hex` (token-less → `partition={}`).
* **Fail →** ⟨2B-S5-020 DICTIONARY_RESOLUTION_ERROR⟩ / ⟨2B-S5-070 PARTITION_SELECTION_INCORRECT⟩. 

**V-03 — Dictionary-only resolution & exact partitions**

* **Checks:** All reads resolve **by Dataset Dictionary ID**, with **exact** partitions:
  `s4_group_weights@seed,manifest_fingerprint`; `s1_site_weights@seed,manifest_fingerprint`; `s2_alias_index@seed,manifest_fingerprint`; `s2_alias_blob@seed,manifest_fingerprint`; `site_timezones@seed,manifest_fingerprint`. No literal paths; no network I/O.
* **Fail →** ⟨2B-S5-020⟩ / ⟨2B-S5-021 PROHIBITED_LITERAL_PATH⟩ / ⟨2B-S5-023 NETWORK_IO⟩. 

**V-04 — S2 artefact parity (pre-flight)**

* **Checks:** `s2_alias_index.header.blob_sha256 == SHA256(raw bytes of s2_alias_blob)` and `s2_alias_index.header.policy_digest` equals the sealed digest of `alias_layout_policy_v1`.
* **Fail →** ⟨2B-S5-041 SITE_ALIAS_DECODE_INCOHERENT⟩. 

**V-05 — Group-pick law (uses S4 as sole authority)**

* **Checks:** For each `(merchant_id, utc_day)`, the **group alias** is built from S4 rows in PK order and encodes exactly S4’s `p_group`. No extra renormalisation beyond binary64 Σ=1 construction.
* **Fail →** ⟨2B-S5-040 GROUP_PROBABILITY_MISMATCH⟩. 

**V-06 — Site-alias build (Option-A only, v1)**

* **Checks:** The **per-group** site alias is built from `s1_site_weights` filtered by `site_timezones` to the chosen `tz_group_id`. Σ of retained weights > 0; builder is RNG-free and deterministic; **no** reliance on group slices from S2 v1.
* **Fail →** ⟨2B-S5-041 SITE_ALIAS_DECODE_INCOHERENT⟩ (empty/invalid slice).

**V-07 — Mapping coherence (group ⇄ site)**

* **Checks:** The selected `site_id` maps (via 2A `site_timezones`) to the **same** `tz_group_id` chosen in Stage-A, for every selection.
* **Fail →** ⟨2B-S5-060 GROUP_SITE_MISMATCH⟩. 

**V-08 — RNG event budgets (two singles per arrival)**

* **Checks:** For each arrival, exactly **two** events are appended, **in order**: `alias_pick_group`, then `alias_pick_site`. Each row carries the standard RNG envelope with `blocks=1`, `draws="1"`. After **each** event append, one `rng_trace_log` row is appended (cumulative).
* **Fail →** ⟨2B-S5-050 RNG_DRAWS_COUNT_MISMATCH⟩ / ⟨2B-S5-056 EVENT_ORDER⟩. 

**V-09 — RNG counters: monotone & no wrap**

* **Checks:** For every event row, `after − before == 1` (128-bit), counters strictly increasing within the run; no wrap.
* **Fail →** ⟨2B-S5-051 RNG_COUNTER_NOT_MONOTONE⟩ / ⟨2B-S5-052 RNG_COUNTER_WRAP⟩. 

**V-10 — RNG streams/substreams match policy**

* **Checks:** `rng_stream_id`/substream fields on both families match `route_rng_policy_v1` (routing stream).
* **Fail →** ⟨2B-S5-053 RNG_STREAM_MISCONFIGURED⟩. 

**V-11 — Trace reconciliation**

* **Checks:** For the run, `rng_trace_log.total_draws == 2 × (#selections_emitted)` and equals the sum across the two families.
* **Fail →** ⟨2B-S5-050⟩. 

**V-12 — Optional `s5_selection_log` shape & lineage (only if enabled)**

* **Checks:** If the Dictionary registers `s5_selection_log`, rows conform to `schemas.2B.yaml#/trace/s5_selection_log_row`; partitions are `[seed, parameter_hash, run_id, utc_day]`; **writer order = arrival order**; column `manifest_fingerprint` exists and **byte-equals** the run manifest_fingerprint; `created_utc` equals S0 `verified_at_utc`.
* **Fail →** ⟨2B-S5-071 PATH_EMBED_MISMATCH⟩ / ⟨2B-S5-080 IMMUTABLE_OVERWRITE⟩ / ⟨2B-S5-081 NON_IDEMPOTENT_REEMIT⟩. 

**V-13 — Immutability & atomic publish**

* **Checks:** All S5 writes (events/logs, and `s5_selection_log` if enabled) are **write-once** and published via atomic move. Any second publish must be **byte-identical** or use a **new `run_id`**.
* **Fail →** ⟨2B-S5-080⟩ / ⟨2B-S5-081⟩. 

**V-14 — No mutation of plan surfaces**

* **Checks:** S5 performs **no writes** to `[seed, manifest_fingerprint]` plan/egress datasets (`s1_site_weights`, `s2_alias_*`, `s4_group_weights`, `site_timezones`).
* **Fail →** ⟨2B-S5-090 PROHIBITED_WRITE⟩.

**V-15 — Deterministic replay (spot-check)**

* **Checks:** Re-run the router for a deterministic sample of arrivals and assert **bit-identical** `(tz_group_id, site_id)` and (if logging enabled) identical log rows and RNG evidence. (Relies on S0 identity, sealed policy bytes, and Philox counters.)
* **Fail →** ⟨2B-S5-095 REPLAY_MISMATCH⟩.

**V-16 — Evidence that S4 is echoed, not recomputed**

* **Checks:** S5 **must not** recompute or re-normalise `p_group` beyond alias construction. Compare the group alias probabilities against S4’s `p_group` vector; they must match within binary64 tolerance.
* **Fail →** ⟨2B-S5-040⟩. 

---

### Inputs/anchors these validators rely on

* **Dictionary (partitions & IDs):** `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s4_group_weights`, `site_timezones`, policies. 
* **Schema pack (shapes):** `#/plan/s1_site_weights`, `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`, `#/plan/s4_group_weights`, 2A `#/egress/site_timezones`.
* **Gate law:** S0 receipt & sealed inventory. 

> Passing **V-01…V-16** proves S5 uses **only sealed, catalogued inputs**, preserves **identity and ordering**, emits **exact RNG evidence (2 events/arrival)**, and respects **authority boundaries** (S4 probabilities, S2 alias artefacts, 2A tz mapping).

---

## 10. **Failure modes & canonical error codes (Binding)**

> **Severity classes:** **Abort** (hard stop; S5 must not continue) and **Warn** (record + continue).
> **Where errors surface:** S5 run-report (STDOUT JSON), and—if enabled—`s5_selection_log` context fields. RNG-related failures also annotate the **RNG core logs** / **event rows**. Shapes, partitions, and gate rules referenced here are owned by your S0/S2/S3/S4 specs, the 2B schema pack, the 2B dictionary, and the layer log envelope.

---

### 10.1 Gate & catalogue discipline

**2B-S5-001 — S0_RECEIPT_MISSING** · *Abort*
**Trigger:** `s0_gate_receipt_2B` and/or `sealed_inputs_2B` absent or schema-invalid at `[manifest_fingerprint]`.
**Detect:** V-01. **Remedy:** (i) produce S0 for this manifest_fingerprint; (ii) fix schema/partition; re-run. 

**2B-S5-020 — DICTIONARY_RESOLUTION_ERROR** · *Abort*
**Trigger:** Any input not resolved by **Dataset Dictionary ID** (wrong ID, wrong format, wrong path family).
**Detect:** V-02/V-03. **Remedy:** use Dictionary-only resolution; correct ID/path family. 

**2B-S5-021 — PROHIBITED_LITERAL_PATH** · *Abort*
**Trigger:** Literal filesystem/URL read attempted.
**Detect:** V-03. **Remedy:** replace with Dictionary ID resolution. 

**2B-S5-023 — NETWORK_IO** · *Abort*
**Trigger:** Any network access during S5.
**Detect:** V-03. **Remedy:** remove network I/O; use sealed artefacts only. 

**2B-S5-070 — PARTITION_SELECTION_INCORRECT** · *Abort*
**Trigger:** A partitioned read is not **exactly** `[seed, manifest_fingerprint]`, or a token-less policy is not selected by **S0-sealed** `path`+`sha256_hex`.
**Detect:** V-02/V-03. **Remedy:** fix partition tokens / policy selection semantics. 

**2B-S5-071 — PATH_EMBED_MISMATCH** · *Abort*
**Trigger:** Any embedded lineage (e.g., `manifest_fingerprint` column in optional logs) differs from path tokens.
**Detect:** V-12. **Remedy:** correct writer to echo path tokens byte-for-byte. 

---

### 10.2 S2 alias integrity & decode coherence

**2B-S5-041 — SITE_ALIAS_DECODE_INCOHERENT** · *Abort*
**Trigger (either):**
(a) `s2_alias_index.header.blob_sha256 ≠ SHA256(raw s2_alias_blob)` or policy echo mismatch; **or**
(b) per-group site slice (from S1×2A filter) is empty / invalid for the chosen group.
**Detect:** V-04 (a), V-06 (b). **Remedy:** (a) republish S2 artefacts per contract; (b) fix inputs so each chosen group has ≥1 site. 

**2B-S5-040 — GROUP_PROBABILITY_MISMATCH** · *Abort*
**Trigger:** The group alias encodes probabilities different to S4’s `p_group` (beyond binary64 tolerance).
**Detect:** V-05/V-16. **Remedy:** use S4 `s4_group_weights` verbatim; remove extra renormalisation. 

---

### 10.3 RNG budgets, counters, streams

**2B-S5-050 — RNG_DRAWS_COUNT_MISMATCH** · *Abort*
**Trigger:** Per-arrival draws ≠ **2** (one `alias_pick_group` + one `alias_pick_site`), or `rng_trace_log.total_draws ≠ 2×selections`.
**Detect:** V-08/V-11. **Remedy:** ensure exactly two single-uniform events per selection and reconcile trace totals. 

**2B-S5-056 — EVENT_ORDER** · *Abort*
**Trigger:** Event append order isn’t **group first, then site** for a selection.
**Detect:** V-08. **Remedy:** enforce fixed ordering before trace append. 

**2B-S5-051 — RNG_COUNTER_NOT_MONOTONE** · *Abort*
**Trigger:** 128-bit counter not strictly increasing (`after − before ≠ 1`) within a run.
**Detect:** V-09. **Remedy:** fix counter mapping; one increment per event. 

**2B-S5-052 — RNG_COUNTER_WRAP** · *Abort*
**Trigger:** 128-bit counter overflow/wrap.
**Detect:** V-09. **Remedy:** adjust counter ranges/sharding; never reuse counters. 

**2B-S5-053 — RNG_STREAM_MISCONFIGURED** · *Abort*
**Trigger:** `rng_stream_id` / substream fields don’t match `route_rng_policy_v1`.
**Detect:** V-10. **Remedy:** bind to policy-declared routing stream/substreams. 

---

### 10.4 Identity, immutability & logging (optional dataset included)

**2B-S5-080 — IMMUTABLE_OVERWRITE** · *Abort*
**Trigger:** Target partition not empty and bytes differ (events/logs or optional `s5_selection_log`).
**Detect:** V-13/V-12. **Remedy:** write-once; if retrying, bytes must be identical or use a new `run_id`. 

**2B-S5-081 — NON_IDEMPOTENT_REEMIT** · *Abort*
**Trigger:** Re-publish produced byte-different output for identical inputs.
**Detect:** V-13/V-12. **Remedy:** ensure idempotent re-emit; otherwise bump `run_id`. 

**2B-S5-082 — ATOMIC_PUBLISH_FAILED** · *Abort*
**Trigger:** Staging/rename not atomic, or post-publish verification failed.
**Detect:** V-13/V-12. **Remedy:** stage → fsync → single atomic move; verify final bytes. 

**2B-S5-086 — CREATED_UTC_MISMATCH** · *Abort*
**Trigger:** In optional `s5_selection_log`, `created_utc ≠` S0 `verified_at_utc`.
**Detect:** V-12. **Remedy:** stamp created time from S0 receipt. 

**2B-S5-090 — PROHIBITED_WRITE** · *Abort*
**Trigger:** Any write to plan/egress tables at `[seed, manifest_fingerprint]` (`s1_site_weights`, `s2_alias_*`, `s4_group_weights`, `site_timezones`).
**Detect:** V-14. **Remedy:** treat these as read-only; S5 writes only logs/layer1/2B/events (and optional `s5_selection_log`). 

---

### 10.5 Determinism & replay

**2B-S5-095 — REPLAY_MISMATCH** · *Abort*
**Trigger:** Replaying a deterministic sample of arrivals yields non-identical `(tz_group_id, site_id)` or non-identical event/log bytes under the same sealed inputs.
**Detect:** V-15. **Remedy:** fix RNG stream wiring, stable ordering, and cache semantics until bit-replay passes. 

---

### 10.6 Code ↔ validator map (authoritative)

| Validator (from §9)                          | Codes on fail                              |
|----------------------------------------------|--------------------------------------------|
| **V-01 Gate evidence present**               | 2B-S5-001                                  |
| **V-02 S0-evidence & exact selection**       | 2B-S5-020, 2B-S5-070                       |
| **V-03 Dictionary-only & exact partitions**  | 2B-S5-020, 2B-S5-021, 2B-S5-023, 2B-S5-070 |
| **V-04 S2 artefact parity**                  | 2B-S5-041                                  |
| **V-05 Group-pick law**                      | 2B-S5-040                                  |
| **V-06 Site-alias build (Option-A)**         | 2B-S5-041                                  |
| **V-07 Mapping coherence**                   | 2B-S5-060                                  |
| **V-08 RNG budgets & event order**           | 2B-S5-050, 2B-S5-056                       |
| **V-09 RNG counters monotone/no wrap**       | 2B-S5-051, 2B-S5-052                       |
| **V-10 RNG streams match policy**            | 2B-S5-053                                  |
| **V-11 Trace reconciliation**                | 2B-S5-050                                  |
| **V-12 Optional `s5_selection_log` lineage** | 2B-S5-071, 2B-S5-080, 2B-S5-081, 2B-S5-086 |
| **V-13 Immutability & atomic publish**       | 2B-S5-080, 2B-S5-081, 2B-S5-082            |
| **V-14 No mutation of plan surfaces**        | 2B-S5-090                                  |
| **V-15 Deterministic replay**                | 2B-S5-095                                  |
| **V-16 S4 echo, not recompute**              | 2B-S5-040                                  |

All codes above are **Binding** for S5 v1 and rely on contracts already ratified in S0/S2/S3/S4, the 2B schema pack and dictionary, and the layer log envelope.

---

## 11. **Observability & run-report (Binding)**

### 11.1 Purpose

Emit one **structured JSON run-report** that proves what S5 **read**, how it **routed** (two events per arrival), and what **evidence** it wrote (RNG core logs / event families, and the optional selection log). The report is **diagnostic (non-authoritative)**; S2/S3/S4 remain the sources of truth and the RNG envelope shapes live in the layer pack.

### 11.2 Emission

* S5 **MUST** write the run-report to **STDOUT** as a single JSON document on successful completion (and on abort, if possible). This mirrors S2/S3/S4 practice.
* Persisted copies (if any) are **non-authoritative**; downstream contracts **MUST NOT** depend on them. 

### 11.3 Top-level shape (fields-strict)

The run-report **MUST** contain exactly these top-level keys:

* `component`: `"2B.S5"`
* `manifest_fingerprint`: `<hex64>`; `seed`: `<uint64>`; `parameter_hash`: `<hex64>`; `run_id`: `<hex32>`
* `created_utc`: RFC-3339 micros — **echo S0 `verified_at_utc`** (provenance law)
* `catalogue_resolution`: `{ dictionary_version: <semver>, registry_version: <semver> }`
* `policy`:
  `{ id: "route_rng_policy_v1", version_tag: <string>, sha256_hex: <hex64>, rng_engine: <string>, rng_stream_id: <string>, draws_per_selection: 2 }`
* `inputs_summary`:
  `{ group_weights_path, site_weights_path, site_timezones_path, alias_index_path, alias_blob_path }` — **Dictionary-resolved** paths at `[seed, manifest_fingerprint]` (policies are token-less and selected by S0-sealed path + digest).
* `rng_accounting`:
  `{ events_group: <uint64>, events_site: <uint64>, events_total: <uint64>, draws_total: <uint64>, first_counter: {hi,lo}, last_counter: {hi,lo} }`
  *Invariant:* `draws_total == 2 × selections_logged`. Core logs’ partitioning is `[seed, parameter_hash, run_id]`. 
* `logging`:
  `{ selection_log_enabled: <bool>, selection_log_partition?: "[seed,parameter_hash,run_id,utc_day]" }` (present only if enabled). 
* `validators`: `[ { id: "V-01", status: "PASS|FAIL|WARN", codes: [ "2B-S5-0XX", … ] } … ]`
* `summary`: `{ overall_status: "PASS|FAIL", warn_count: <int>, fail_count: <int> }`
* `environment`: `{ engine_commit?: <string>, python_version: <string>, platform: <string>, network_io_detected: <int> }`

*(Fields-strict: no extra keys. Timestamps/IDs use layer-wide `$defs`.)* 

### 11.4 Evidence & samples (bounded, deterministic)

Provide **bounded** samples sufficient for offline verification; all samples are **deterministic** given the sealed inputs:

* `samples.selections` — up to **20** routed arrivals:
  `{ merchant_id, utc_day, tz_group_id, site_id }`.
* `samples.inputs` — echo the **Dictionary-resolved** paths used for `s4_group_weights`, `s1_site_weights`, `site_timezones`, `s2_alias_index`, `s2_alias_blob`. 

### 11.5 RNG evidence coupling (canonical law)

* S5 **MUST** emit **two single-uniform events per arrival**: `alias_pick_group`, then `alias_pick_site`; after **each** append, **append one** `rng_trace_log` row (cumulative). Core logs and events are partitioned by `[seed, parameter_hash, run_id]` and carry the standard **RNG envelope**.
* The run-report **MUST** reconcile:
  `events_total == events_group + events_site` and `draws_total == 2 × selections_logged`. 

### 11.6 Optional selection log (if enabled by policy)

* Partitioning: **`[seed, parameter_hash, run_id, utc_day]`**; column `manifest_fingerprint` **must** equal the run manifest_fingerprint; **writer order = arrival order**; **write-once + atomic publish**. The run-report **MUST** state `selection_log_partition`. 

### 11.7 No new authorities

This section does **not** create new dataset authorities. Shapes come from the **2B schema pack** and **layer pack**; ID→path/partitions come from the **Dataset Dictionary**; ownership/retention comes from the **Artefact Registry** (metadata only).

> With this run-report, S5 mirrors S2/S3/S4 observability: single **STDOUT JSON**, strict fields, Dictionary-echoed inputs, and RNG accounting tied to the **layer** core logs and envelope—making replay and audit straightforward.

---

## 12. **Performance & scalability (Informative)**

**Goal.** Keep per-arrival routing **O(1)** (two alias decodes), with deterministic caches and I/O patterns that scale across merchants, days, and workers—without violating S0–S4 identity and catalogue laws.

### 12.1 Cost model (asymptotics)

Let:

* `S` = routed arrivals in the run;
* `G_{m,d}` = # tz-groups for merchant `m` on UTC day `d` (from **S4**);
* `N_{m,d,g}` = # sites for merchant `m` in group `g` (via **S1** ∩ **site_timezones**).

Then the **total work** over a run is:

* **Group alias builds (first use):** `∑_{m,d} O(G_{m,d})` from **S4**. 
* **Per-group site alias builds (first use):** `∑_{(m,d,g) actually visited} O(N_{m,d,g})` from **S1** filtered by **site_timezones**.
* **Per selection:** `O(1) + O(1)` (one group decode, one site decode).

So **end-to-end:** `O(S) + O(∑ G_{m,d}) + O(∑ N_{m,d,g}^{visited})`, with the last two terms amortised by caching. Inputs are selected at **exactly** `[seed, manifest_fingerprint]` per the Dictionary. 

### 12.2 Caching strategy (deterministic, RNG-free)

* **GROUP_ALIAS[m,d]**: tiny alias over `p_group(m,d,*)` from **S4**; build on first use in stable PK order. Size `~ O(G_{m,d})`. 
* **SITE_ALIAS[m,d,g]**: alias over sites in group `g` using **S1** masses filtered by **site_timezones**; build on first use; size `~ O(N_{m,d,g})`.
* **Determinism requirement:** cache presence/eviction **must not** change outcomes; building or rebuilding yields identical selections (builders are RNG-free; stable serial sums).
* **Memory envelope (rule of thumb):** each alias holds two arrays of length `K` (e.g., `prob[K]` as float64; `alias[K]` as int of minimal width that covers `K`). Cap with an **LRU by bytes**; evict oldest group-aliases first. *(Implementation detail; spec remains engine-agnostic.)*

### 12.3 I/O pattern

* **Cold start:** open once per input at `[seed, manifest_fingerprint]`; stream **S4** rows by `(merchant_id, utc_day)`; stream **S1** rows by `(merchant_id)`; probe **site_timezones** by `site_id → tzid` (join or prebuilt keyed reader). 
* **S2 pre-flight (once/run):** verify `blob_sha256` of **s2_alias_blob** against **s2_alias_index** and the policy echo—**streaming** hash is fine; do **not** scan inside the blob beyond integrity.
* **Hot loop:** per arrival reads only the cached `(m,d)` group-alias and (if needed) builds/reads the `(m,d,g)` site-alias.

### 12.4 Concurrency & sharding (safe patterns)

* **Run-scoped logging envelope:** RNG events and core logs partition by **`[seed, parameter_hash, run_id]`**. Shard **across** `(run_id)` or **across utc_day** partitions; ensure **single-writer** per partition and preserve arrival order in any optional `s5_selection_log`. 
* **Within a run:** parallel workers may process **disjoint** `(utc_day)` or merchant shards **only if** RNG substreams/counters are disjoint per the routing policy; event order per arrival remains: **group → site**. (Satisfies trace reconciliation.) 

### 12.5 RNG evidence overhead

* **Two events per selection** (group, site) + **one trace append after each event**. The smallest durable units are event rows; batching **writes** (not logical rows) is allowed if it preserves **append order** and atomic publish in the log partitions. 

### 12.6 Cold-start & warm-cache behaviour

* **Warm-up:** optionally prebuild `GROUP_ALIAS[m,d]` for merchants with heavy volume (deterministic PK scan of S4 over the day range).
* **On-demand SITE_ALIAS:** build only for groups that actually occur; this keeps first-hit latency bounded by `O(N_{m,d,g})` and amortises quickly for busy groups.
* **Eviction:** LRU by bytes across `SITE_ALIAS` first, then `GROUP_ALIAS`. Rebuilds are deterministic; outcomes unchanged.

### 12.7 Memory & footprint considerations

* **Peak memory** ≈ `∑_{live (m,d)} O(G_{m,d}) + ∑_{live (m,d,g)} O(N_{m,d,g})` elements across aliases, plus small dictionaries for merchant/day indexes.
* **Practical knobs (implementation):** `cache_max_bytes`, `max_live_group_aliases_per_merchant`, `prewarm_top_k_merchants`, and I/O buffer sizes. *(Non-normative; policy does not carry these.)*

### 12.8 Throughput posture

* **Decode cost** is constant: index `j = ⌊u·K⌋`, one compare (`r < prob[j]`), one fallback (`alias[j]`).
* **Builder cost** is linear in `K` with a **stable serial reduction** (binary64 ties-to-even) and a classic small/large stack pass; done **once** per cached alias.
* **Net effect:** steady-state throughput is dominated by the two uniform draws + two table lookups per selection; sustained performance is therefore proportional to `S` once caches are warm. *(No change to draws: always 2.)*

### 12.9 Impact of S2/S4 sizes

* **S4** dictates `G_{m,d}`; more tz-groups per merchant/day increase group-alias build time and cache size but **not** per-selection decode cost. 
* **S2** dictates decode layout/endianness/alignment; S5 only **verifies** digest/echo and decodes per policy when building aliases from S1 (v1). Blob size affects **one** streaming hash at start, not the hot loop. 

### 12.10 Optional diagnostics cost

* If `s5_selection_log` is enabled, write amplification is proportional to routed arrivals (`O(S)`) with partitions **`[seed, parameter_hash, run_id, utc_day]`**; disable by default for production unless CI/replay requires it. 

### 12.11 Failure-free degradation

* **Memory pressure:** evict aliases (LRU) and rebuild on demand; determinism preserved.
* **Blob mismatch (S2 parity):** fail fast at pre-flight before hot routing; no partial logs. 

> Summary: Use **on-demand, deterministic caches** to amortise the one-time `O(G)`/`O(N)` builds; keep the hot path to **two uniform draws + two O(1) decodes**; partition all evidence by the **run-scoped RNG envelope** and read plan tables at **`[seed, manifest_fingerprint]`** only. This aligns exactly with S2/S4 contracts and the layer logging law.

---

## 13. **Change control & compatibility (Binding)**

**13.1 Versioning (SemVer)**

* **MAJOR** when any binding interface changes (IDs, `$ref` anchors, partition law, RNG **engine/streams/event family names or envelope**, number/order of draws, gate law, path↔embed equality).
* **MINOR** for backward-compatible additions (optional diagnostics, new **optional** fields in schemas, new WARN validators, doc clarifications) that **do not** change shapes, IDs, partitions, or RNG budgets.
* **PATCH** for typo/wording fixes only. 

**13.2 Compatibility surface (stable in S5 v1)**
Consumers **MAY rely** on the following remaining stable within a major:

* **Inputs & partitions:** S5 reads exactly `s4_group_weights`, `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `site_timezones` at **`[seed, manifest_fingerprint]`**; policies `route_rng_policy_v1`, `alias_layout_policy_v1` are **token-less** and selected by the **S0-sealed** path+digest.
* **Authority boundaries:** JSON-Schema = shape authority (`schemas.2B.yaml`, `schemas.2A.yaml`); Dictionary = IDs→paths/partitions; Registry = metadata only. 
* **Algorithmic contract:** two-stage router (group then site), **two single-uniform events per arrival** (`alias_pick_group`, `alias_pick_site`), **order = group→site**, counters strictly monotone, open-interval `u∈(0,1)`. 
* **Decode authority:** S2 index is the sole directory; `blob_sha256` must match raw blob bytes; S5 does **not** scan/guess inside the blob. 
* **Group probabilities:** S4 `p_group` is authoritative; S5 must not re-derive beyond alias construction. 
* **Identity & logs:** RNG evidence and core logs partition under **`[seed, parameter_hash, run_id]`**; plan/egress reads stay at **`[seed, manifest_fingerprint]`**. 

**13.3 Backward-compatible (MINOR) changes**
Allowed without breaking consumers:

* Add **optional** fields to S5’s run-report; add **optional** properties to S5-related anchors (kept fields-strict for required keys). 
* Register `s5_selection_log` as an **optional** dataset in the Dictionary (off by default); when present it must use `[seed, parameter_hash, run_id, utc_day]` and the `#/trace/s5_selection_log_row` anchor. 
* Add **optional** fields in S2 index header or policies (S5 already tolerates extra properties; policy anchors are permissive). 

**13.4 Breaking (MAJOR) changes**
Require a new **major** for S5 and coordinated updates to packs:

* Change **draws per selection** (≠2), RNG engine or **event family names**, or event order. 
* Change IDs, path families, or partitions of any S5 input; make selection log **mandatory**; alter its partition law. 
* Use any probability source other than S4 `p_group`, or alter alias decode law/ordering affecting outcomes. 
* Remove/rename required S2 index header fields or drop `blob_sha256`/`policy_digest` parity. 

**13.5 Coordination with S2/S3/S4 (matrix)**

* **S2** may add header fields or increase blob size **without** breaking S5 (S5 reads required subset and checks parity). Shape remains under `#/plan/s2_alias_index` & `#/binary/s2_alias_blob`. 
* **S3/S4** may change internal implementation as long as **anchors, partitions, and semantics** (γ echo; Σ=1 law; PK/writer order) hold.

**13.6 “Option B” (future group-slices) policy**

* **Not in v1.** S2 currently exposes **per-merchant** slices only; S5 v1 binds **Option-A** (build per-group alias from S1 + `site_timezones`). Introducing **group-slice offsets** in S2 could be a **MINOR** **only if**:
  (i) **draws remain 2**, (ii) decode semantics unchanged, and (iii) outcomes are **bit-identical** for the same sealed inputs. Otherwise it is **MAJOR**. 

**13.7 Validator/code namespace stability**

* Validator IDs (`V-01…`) and error codes (`2B-S5-…`) are **reserved**; adding new codes is allowed; changing meanings or reusing IDs is **breaking**. (Mirrors S4’s policy.) 

**13.8 Registry/Dictionary coordination**

* Dictionary edits that change ID names, path families, or partition tokens for S5 inputs are **breaking** unless published as **new IDs** with a migration plan. Registry metadata edits (owner/licence/retention) are compatible; edits impacting **existence** of required artefacts are breaking. (Same law as S4.) 

**13.9 Deprecation & migration protocol**

* Propose → review → ratify with **change log** (impact, validator diffs, new anchors, migration). For majors, prefer **dual-publish** (old & new side-by-side) or a consumer shim window. 

**13.10 Rollback policy**

* All S5 writes are **write-once**; rollback = publish a new `{seed,manifest_fingerprint}` (or revert to a previous manifest_fingerprint) that reproduces last-known-good behaviour. No in-place mutation. 

**13.11 Evidence of compatibility (release gate)**
Each S5 release **MUST** ship: schema diffs, validator table diffs, and a conformance run proving previously valid inputs still **PASS** (for minor/patch). CI **must** cover: Dictionary-only selection, S2 parity, S4 echo (Σ=1), two-event RNG accounting, identity/immutability, and deterministic replay. 

**13.12 No new authorities**
This section creates **no** new dataset authorities. Schemas remain governed by **`schemas.2B.yaml`**/layer pack; ID→paths/partitions remain governed by the **Dataset Dictionary**; Registry remains metadata only.

> Net effect: within a major, S5 remains a **two-stage, two-draw, group→site router** with stable inputs/partitions, RNG envelope, and authority boundaries; changes beyond that require a coordinated **major** with S2/S4 and the layer logging law.

---

## Appendix A — Normative cross-references *(Informative)*

> Shapes are governed by **schemas**; ID→path/partitions/format by the **Dataset Dictionary**; ownership/licence/retention by the **Artefact Registry**. Binding rules live in §§1–13.

### A.1 Authority chain (this segment)

* **Schema pack (shape authority):** `schemas.2B.yaml`
  **Anchors S5 reads:**
  • `#/plan/s4_group_weights` (day mixes) · `#/plan/s1_site_weights` (per-site masses) · `#/plan/s2_alias_index` (alias directory) · `#/binary/s2_alias_blob` (alias bytes) · `#/policy/route_rng_policy_v1` · `#/policy/alias_layout_policy_v1`. 
  **Common defs:** `#/$defs/hex64`, `#/$defs/partition_kv` *(token-less OK)*; timestamps reuse `schemas.layer1.yaml#/$defs/rfc3339_micros`. 

* **Dataset Dictionary (catalogue authority):** `dataset_dictionary.layer1.2B.yaml`
  **IDs & path families S5 resolves (all read-only):**
  • `s4_group_weights` → `data/layer1/2B/s4_group_weights/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (Parquet; `[seed, manifest_fingerprint]`) 
  • `s1_site_weights` → `…/2B/s1_site_weights/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (Parquet; `[seed, manifest_fingerprint]`) 
  • `s2_alias_index` → `…/2B/s2_alias_index/seed={seed}/manifest_fingerprint={manifest_fingerprint}/index.json` (JSON; `[seed, manifest_fingerprint]`) 
  • `s2_alias_blob` → `…/2B/s2_alias_blob/seed={seed}/manifest_fingerprint={manifest_fingerprint}/alias.bin` (binary; `[seed, manifest_fingerprint]`) 
  • Cross-segment `site_timezones` (2A egress) → `…/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (Parquet; `[seed, manifest_fingerprint]`) 
  • Policies (token-less, single files): `route_rng_policy_v1`, `alias_layout_policy_v1` (selected by **S0-sealed path + digest**). 

* **Artefact Registry (metadata only):** `artefact_registry_2B.yaml`
  Entries for `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, and cross-layer `site_timezones`, plus policy packs with their schema refs. 

---

### A.2 Prior state evidence (2B.S0)

* **`s0_gate_receipt_2B`** (manifest_fingerprint-scoped): `schemas.2B.yaml#/validation/s0_gate_receipt_v1`. 
* **`sealed_inputs_2B`** (manifest_fingerprint-scoped): `schemas.2B.yaml#/validation/sealed_inputs_2B`. 
  *(S5 verifies presence/identity; it does not re-hash the 1B bundle.)* 

---

### A.3 Inputs consumed by S5 (read-only)

* **Day mixes (group stage):** `s4_group_weights` → `schemas.2B.yaml#/plan/s4_group_weights` (PK `[merchant_id, utc_day, tz_group_id]`; `[seed, manifest_fingerprint]`). 
* **Per-site masses (site stage):** `s1_site_weights` → `#/plan/s1_site_weights` (writer order = PK; `[seed, manifest_fingerprint]`). 
* **Alias artefacts (parity checks):** `s2_alias_index` → `#/plan/s2_alias_index`; `s2_alias_blob` → `#/binary/s2_alias_blob` (both `[seed, manifest_fingerprint]`). 
* **Site→tz mapping (coherence):** `site_timezones` → `schemas.2A.yaml#/egress/site_timezones` (2A egress; `[seed, manifest_fingerprint]`). 
* **Policies (captured at S0; token-less):** `route_rng_policy_v1`, `alias_layout_policy_v1` → `schemas.2B.yaml#/policy/*`. Selection by **exact S0-sealed path + sha256**. 

---

### A.4 RNG evidence & core logs (layer envelope)

* **Core logs (run-scoped):** `rng_audit_log`, `rng_trace_log` under partitions `[seed, parameter_hash, run_id]` (programme-wide envelope; S5 appends one trace row after **each** event append). 
* **Event families (per arrival; single-uniform):** `alias_pick_group`, `alias_pick_site` — recorded under the same run-scoped envelope. *(Family schemas live in the layer pack alongside the RNG envelope; S5 relies on these names and budgets.)* 

---

### A.5 Optional diagnostic dataset (only if registered)

* **`s5_selection_log`** (optional): if the Dictionary registers this ID, partitions **`[seed, parameter_hash, run_id, utc_day]`** and row shape anchored at `schemas.2B.yaml#/trace/s5_selection_log_row` (fields-strict). If not registered, **MUST NOT** be written. 

---

### A.6 Cross-refs to upstream state specs (context)

* **2B.S2** (alias index/blob contracts; policy echo & `blob_sha256` law). 
* **2B.S4** (normalisation law; `p_group` authority for S5’s group pick). 
* **2A.S2** (authoritative `site_timezones` egress for mapping coherence). 
* **2B.S0** (gate receipt & sealed inputs S5 must verify). 

---

### A.7 Token & identity law (where to look)

* **Plan/egress inputs:** selected at **`[seed, manifest_fingerprint]`** exactly as per the Dictionary entries above. 
* **RNG logs/layer1/2B/events:** produced at **`[seed, parameter_hash, run_id]`** with the layer RNG envelope. 

---
