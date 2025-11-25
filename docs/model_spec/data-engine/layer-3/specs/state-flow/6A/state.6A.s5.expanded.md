# 6A.S5 — Static fraud posture & 6A HashGate (Layer-3 / Segment 6A)

## 1. Purpose & scope *(Binding)*

6A.S5 is the **static fraud posture & segment-closure state** for Layer-3 / Segment 6A.

Its job is to take the fully-realised 6A world:

* parties (S1),
* accounts & products (S2),
* instruments (S3),
* devices, IPs & graph (S4),

and then:

1. **Assign static fraud posture (“fraud roles”)** over that graph, and
2. **Close 6A** by building the **6A validation bundle + `_passed.flag_6A`** that downstream (6B + the enterprise shell) will use as *the* signal that 6A is sealed and trustworthy.

---

### 1.1 Static fraud posture

S5 is the **only state** in 6A that assigns *static* fraud roles and risk posture to entities. At a minimum, S5 must:

* For **parties** (from S1):

  * assign roles such as `CLEAN`, `MULE`, `SYNTHETIC_ID`, `ORGANISER`, etc., derived from S5 priors and structural features (segments, graph structure, merchant mix, etc.).

* For **accounts** (from S2):

  * label accounts as `CLEAN_ACCOUNT`, `MULE_ACCOUNT`, `HIGH_RISK_PRODUCT`, etc., consistent with their owner’s role and product mix.

* For **merchants** (from L1 / S2/S3 context):

  * mark merchants as `NORMAL`, `COLLUSIVE`, `RISKY_MCC`, `MONEY_SERVICE_BUSINESS`, etc., according to merchant-level priors and graph signals.

* For **instruments** (from S3):

  * optionally tag instruments as `COMPROMISED`, `RISKY_INSTRUMENT`, `NEUTRAL`, consistent with party/account roles and configured priors.

* For **devices & IPs** (from S4):

  * assign static posture such as `NORMAL_DEVICE`, `RISKY_DEVICE`, `BOT_LIKE_DEVICE`,
  * and `NORMAL_IP`, `DATACENTRE_IP`, `PROXY_IP`, `HIGH_RISK_IP`, etc., based on priors plus graph patterns (sharing, degree, attachment to risky entities).

These roles are:

* **static** for the life of the world: they do not change over time,
* **segment-local**: they live entirely inside 6A and are not per-flow labels.

S5 **does not** simulate behaviour or dynamic labels (e.g. “this transaction is fraud”). Behavioural labels are the responsibility of 6B.

---

### 1.2 6A segment-level validation and HashGate

S5 is also the **closing gate** for 6A. Its second core purpose is to:

* Run **segment-level validation** over:

  * S1–S4 outputs,
  * the fraud roles S5 has assigned,
  * and any 6A-specific quality/consistency rules.

* Materialise a **6A validation bundle** for each `manifest_fingerprint`, containing:

  * `s5_validation_report_6A` — a structured summary of all checks (PASS/WARN/FAIL per check),
  * optional `s5_issue_table_6A` — row-level issues where needed,
  * supporting evidence artefacts (summaries, digests, counts) for S1–S4 + roles.

* Compute the **6A HashGate**:

  * build `validation_bundle_index_6A` listing bundle members and their SHA-256 digests under a canonical law,
  * compute a final `bundle_digest_sha256` over indexed evidence,
  * emit **`validation_passed_flag_6A`** (the `_passed.flag_6A` artefact) as a fingerprint-scoped object carrying this digest.

Downstream (6B, enterprise ingestion, any consumers of the fake bank) must treat:

> `validation_passed_flag_6A` present & valid
> ⇒ “Segment 6A is sealed; its world is safe to read.”

No `_passed.flag_6A` → **no read of 6A outputs** (S1–S5) for that `manifest_fingerprint`.

---

### 1.3 Scope boundaries

Within Layer-3 / Segment 6A, S5:

* **Does not**:

  * create new entities or edges — no new `party_id`, `account_id`, `instrument_id`, `device_id`, `ip_id`, or `merchant_id`,
  * modify any S1–S4 attributes or graph structure,
  * read or depend on individual arrivals/flows from 5B,
  * define dynamic, per-event fraud labels (those belong to 6B).

* **Does**:

  * read S1–S4 bases and links as sealed ground truth,
  * assign static fraud roles on top of that graph according to sealed S5 priors/configs,
  * run S5 validation checks over the entire 6A segment for each world,
  * produce 6A’s segment-level validation bundle + `_passed.flag_6A`.

All later components (6B, enterprise shell) must treat S5’s fraud-role surfaces as the **canonical static fraud posture** for 6A entities and must enforce `_passed.flag_6A` as the **hard gate** on whether any 6A world is considered usable.

---

## 2. Preconditions, upstream gates & sealed inputs *(Binding)*

6A.S5 only runs when **everything upstream of it is already sealed and trusted** for the relevant world and seed, and when the **S5-specific priors/configs** have been sealed into `sealed_inputs_6A`.

This section fixes those preconditions and the **minimum sealed inputs** S5 expects to see.

---

### 2.1 World-level preconditions (Layer-1 & Layer-2)

For a given `manifest_fingerprint` that S5 will serve, the engine MUST already have:

* Successfully run all required upstream segments:

  * Layer-1: `1A`, `1B`, `2A`, `2B`, `3A`, `3B`.
  * Layer-2: `5A`, `5B`.

* Successfully verified their HashGates (validation bundles + PASS flags), as recorded by 6A.S0.

S5 **does not** re-implement upstream HashGate logic. It **trusts S0’s view** via `s0_gate_receipt_6A`:

* For this `manifest_fingerprint`, every required segment in `upstream_gates` MUST have:

```text
gate_status == "PASS"
```

If any required segment has `gate_status ∈ {"FAIL","MISSING"}`, S5 MUST treat the world as **not eligible** and fail fast with a gate error (e.g. `6A.S5.S0_S1_S2_S3_S4_GATE_FAILED`).

---

### 2.2 6A.S0 preconditions (gate & sealed inputs)

S5 is not allowed to run unless the **6A.S0 gate is fully satisfied** for the world.

For the target `manifest_fingerprint`, S5 MUST:

1. **Validate S0 artefacts**

   * Confirm `s0_gate_receipt_6A` and `sealed_inputs_6A` exist under the correct `fingerprint={manifest_fingerprint}` partition.
   * Validate both against their schema anchors in `schemas.layer3.yaml`:

     * `#/gate/6A/s0_gate_receipt_6A`
     * `#/gate/6A/sealed_inputs_6A`.

2. **Verify sealed-inputs digest**

   * Recompute `sealed_inputs_digest_6A` from `sealed_inputs_6A` using the canonical row encoding and ordering defined in S0.
   * Require:

```text
recomputed_digest == s0_gate_receipt_6A.sealed_inputs_digest_6A
```

3. **Check S0 run-report status**

   * The latest 6A.S0 run-report for this `manifest_fingerprint` MUST have:

```text
status     == "PASS"
error_code == "" or null
```

If any of these checks fails, S5 MUST NOT attempt to assign fraud roles or build a validation bundle for that world and MUST fail with a gate/inputs error.

---

### 2.3 6A.S1–S4 preconditions (party, account, instrument, device/IP bases)

S5 sits on top of the entire 6A modelling stack. For each `(manifest_fingerprint, seed)` it will serve, S5 MUST ensure that **all** upstream 6A states are PASS and that their bases are present and valid.

For the target `(mf, seed)`:

1. **S1 (party base)**

   * Latest 6A.S1 run-report for `(mf, seed)` has:

```text
status     == "PASS"
error_code == "" or null
```

* `s1_party_base_6A` partition for `(seed={seed}, fingerprint={mf})`:

  * exists,
  * validates against `schemas.6A.yaml#/s1/party_base`,
  * has `COUNT(*) == total_parties` reported in the S1 run-report.

2. **S2 (account & holdings base)**

   * Latest 6A.S2 run-report for `(mf, seed)` has:

```text
status     == "PASS"
error_code == "" or null
```

* `s2_account_base_6A` and `s2_party_product_holdings_6A` partitions for `(seed={seed}, fingerprint={mf})`:

  * exist,
  * validate against `#/s2/account_base` and `#/s2/party_product_holdings`,
  * `COUNT(*)` over `s2_account_base_6A` equals `total_accounts` in the S2 run-report.

3. **S3 (instrument & account-instrument links)**

   * Latest 6A.S3 run-report for `(mf, seed)` has:

```text
status     == "PASS"
error_code == "" or null
```

* `s3_instrument_base_6A` and `s3_account_instrument_links_6A` for `(seed={seed}, fingerprint={mf})`:

  * exist,
  * validate against their schema anchors,
  * are consistent with S3 run-report metrics (e.g. `total_instruments`).

4. **S4 (device/IP base & graph links)**

   * Latest 6A.S4 run-report for `(mf, seed)` has:

```text
status     == "PASS"
error_code == "" or null
```

* `s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`, `s4_ip_links_6A` for `(seed={seed}, fingerprint={mf})`:

  * exist,
  * validate against their schema anchors,
  * are consistent with S4 run-report metrics (e.g. `total_devices`, `total_ips`, degree summaries).

If any of S1–S4 is missing or not PASS for `(mf, seed)`, S5 MUST fail with `6A.S5.S0_S1_S2_S3_S4_GATE_FAILED` (or equivalent) and MUST NOT assign fraud roles or emit a 6A HashGate for that world+seed.

---

### 2.4 Required sealed inputs for S5

S5 may only read artefacts that appear in `sealed_inputs_6A` for its `manifest_fingerprint` and have:

* `status ∈ {"REQUIRED","OPTIONAL"}`, and
* `read_scope = "ROW_LEVEL"` for data-level logic, or
* `read_scope = "METADATA_ONLY"` where only presence/shape is consulted.

Among those, S5 requires at minimum:

#### 2.4.1 Fraud-role priors & taxonomies

Artefacts with roles such as `"FRAUD_ROLE_PRIOR"`, `"FRAUD_PRIOR"`, `"TAXONOMY"`:

* **Fraud-role priors (per entity type)**:

  * e.g. per party:

    * target proportions for roles like `CLEAN`, `MULE`, `SYNTHETIC_ID`, `ORGANISER` per cell
      (cells may be defined by region, segment, product mix, simple graph features).

  * per account:

    * priors for `CLEAN_ACCOUNT`, `MULE_ACCOUNT`, `HIGH_RISK_ACCOUNT`, …

  * per merchant:

    * priors for `NORMAL`, `COLLUSIVE`, `HIGH_RISK_MCC`, `MSB`, …

  * per device/IP (if statically labelled at S5):

    * priors for `NORMAL_DEVICE`, `RISKY_DEVICE`, `BOT_LIKE_DEVICE`,
    * priors for `NORMAL_IP`, `PROXY_IP`, `DATACENTRE_IP`, `HIGH_RISK_IP`, etc.

* **Fraud taxonomies**:

  * enumerations of fraud roles per entity type:

    * `fraud_role_party`,
    * `fraud_role_account`,
    * `fraud_role_merchant`,
    * `fraud_role_device`,
    * `fraud_role_ip`,

  and any risk-tier enums S5 will emit (e.g. `STATIC_RISK_TIER ∈ {LOW, STANDARD, ELEVATED, HIGH}`).

The priors and taxonomies S5 depends on MUST be present as rows in `sealed_inputs_6A` with:

```text
status     == "REQUIRED"
read_scope == "ROW_LEVEL"   # for priors; taxonomies can be ROW_LEVEL or METADATA_ONLY
```

and MUST validate against their declared schemas.

#### 2.4.2 Validation policy / checklist

Artefacts with roles such as `"VALIDATION_POLICY_6A"` or `"SEGMENT_CHECKLIST_6A"`:

* define what S5 is obligated to check before declaring 6A PASS, for example:

  * coverage checks (no missing core datasets or key ranges),
  * basic sanity constraints (no negative counts, no orphan FKs, etc.),
  * fraud-role coverage and proportion tolerances per cell,
  * cross-entity consistency (e.g. no clean party with only mule accounts, if disallowed),
  * any global invariants (e.g. minimum amounts of fraud in the world, etc.).

S5 treats this as a “validation spec” for segment closure; it MUST be present (or a default be well-defined) if S5 is expected to emit a HashGate.

#### 2.4.3 6A contracts (metadata-only)

From `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"`:

* `schemas.layer3.yaml`
* `schemas.6A.yaml`
* `dataset_dictionary.layer3.6A.yaml`
* `artefact_registry_6A.yaml`

S5 uses these to:

* resolve schemas, dataset IDs, and paths for S5 outputs,
* ensure its fraud-role surfaces and validation artefacts are declared and shaped correctly.

S5 MUST NOT modify these contracts.

#### 2.4.4 Optional upstream context

If present and used by the design, S5 MAY also read contextual surfaces sealed in `sealed_inputs_6A`, for example:

* **Upstream risk profiles**:

  * e.g. S1/S2/S3/S4-derived summaries that S0 has chosen to seal (counts by MCC, region, graph features) if S5 uses them as additional signal.

* **Global policy parameters**:

  * e.g. target global fraud rates, “stress test” mode flags, etc.

Such artefacts MUST have appropriate `role` tags and `read_scope`, and their absence MUST have a clear meaning (e.g. “use default priors only”).

---

### 2.5 Axes of operation: world vs world+seed

S5’s work naturally splits into:

* **Per-seed artefacts** — fraud-role surfaces:

  * each `(manifest_fingerprint, seed)` has its own:

    * `s5_party_fraud_roles_6A`,
    * `s5_account_fraud_roles_6A`,
    * `s5_merchant_fraud_roles_6A`,
    * `s5_device_fraud_roles_6A`,
    * `s5_ip_fraud_roles_6A` (where those are in scope),

  because fraud posture is defined over each specific universe `(mf, seed)`.

* **Per-world artefacts** — validation bundle & HashGate:

  * `validation_bundle_6A` and `_passed.flag_6A` are **fingerprint-scoped**, not seed-scoped:

    * they summarise validation across all seeds and entity types for a given `mf`,
    * they tell 6B “this world as a whole is sealed”.

Preconditions per axis:

* For each `manifest_fingerprint`:

  * S0 MUST be PASS,
  * all upstream HashGates MUST be PASS.

* For each `(mf, seed)` S5 labels:

  * S1–S4 MUST be PASS,
  * S5’s role-assignment logic operates on that universe only.

The 6A HashGate (`_passed.flag_6A`) is written once per `mf` and is valid only if all required seeds and S5 checks for that world have PASSed.

---

### 2.6 Out-of-scope inputs

S5 explicitly **must not depend on**:

* individual arrivals from `arrival_events_5B` (no per-event logic here),
* any dynamic labels or flows produced by 6B or later states,
* environment or wall-clock time (beyond non-semantic audit timestamps),
* any artefact **not present** in `sealed_inputs_6A` for this `manifest_fingerprint`,
* any artefact present but marked with `read_scope="METADATA_ONLY"` for row-level fraud-role logic.

Any implementation that pulls in off-catalogue data or 6B-level behaviour to decide static fraud posture is **out of spec**, even if it appears to work operationally.

---

## 3. Inputs & authority boundaries *(Binding)*

This section fixes, for **6A.S5**, exactly:

* **what it is allowed to read**, and
* **who is allowed to define what** (L1, L2, S0–S4, S5),

so that 6B and any other consumers can trust that S5:

* only stands on sealed, catalogued inputs, and
* never redefines upstream worlds or structures.

S5 **must only** consume artefacts that:

* appear in `sealed_inputs_6A` for its `manifest_fingerprint` with `status ∈ {"REQUIRED","OPTIONAL"}`, and appropriate `read_scope`, **plus**
* the S1–S4 bases and links for the relevant `(manifest_fingerprint, seed)`.

Everything else is out of bounds.

---

### 3.1 Logical inputs S5 is allowed to use

Subject to §2 and `sealed_inputs_6A`, S5’s inputs fall into four groups.

#### 3.1.1 S0 / S1–S4 control-plane & base inputs

These are mandatory and **read-only** for S5:

* **From 6A.S0** (control plane):

  * `s0_gate_receipt_6A`

    * world identity: `manifest_fingerprint`,
    * parameter identity: `parameter_hash`,
    * upstream gate statuses (`upstream_gates`),
    * 6A contracts/priors summary,
    * `sealed_inputs_digest_6A`.

  * `sealed_inputs_6A`

    * enumerates all artefacts 6A may rely on, with:

      * `role`, `status`, `read_scope`,
      * `schema_ref`,
      * `path_template`, `partition_keys`,
      * `sha256_hex`.

* **From 6A.S1**:

  * `s1_party_base_6A`

    * authoritative party universe for `(mf, seed)`:

      * `party_id`,
      * party type (retail/business/etc.),
      * `segment_id`, home `country_iso`/`region_id`,
      * static attributes (`lifecycle_stage`, `income_band`, etc.).

* **From 6A.S2**:

  * `s2_account_base_6A`

    * authoritative account universe for `(mf, seed)`:

      * `account_id`,
      * `owner_party_id`, optional `owner_merchant_id`,
      * `account_type`, `product_family`, `currency_iso`, static flags.

  * `s2_party_product_holdings_6A`

    * per-party product holdings; useful context for fraud posture (e.g. “heavy borrowers”), but strictly derived from base tables.

* **From 6A.S3**:

  * `s3_instrument_base_6A`

    * `instrument_id`, owning `account_id` / `owner_party_id` (if carried),
    * `instrument_type`, `scheme`, static flags.

  * `s3_account_instrument_links_6A`

    * per-account instrument links; useful for “card-heavy” vs “card-light” posture, etc.

* **From 6A.S4**:

  * `s4_device_base_6A`

    * `device_id`, `device_type`, `os_family`, static risk flags, primary owner context.

  * `s4_ip_base_6A`

    * `ip_id`, `ip_type`, `asn_class`, geo hints, static IP risk flags.

  * `s4_device_links_6A`

    * device→party/account/instrument/merchant edges (who uses which device).

  * `s4_ip_links_6A`

    * IP→device/party/merchant edges (who is seen behind which IPs).

S5 **must** treat all these as:

* **sealed ground truth** for the world’s structure,
* immutable during S5 — S5 only *reads* them.

#### 3.1.2 S5 priors & fraud taxonomies (ROW_LEVEL)

From `sealed_inputs_6A` with `status ∈ {"REQUIRED","OPTIONAL"}` and `read_scope = "ROW_LEVEL"`:

* **Fraud-role priors** (by entity type):

  * For parties:

    * `π_party_role | cell`: priors over roles like `CLEAN`, `MULE`, `SYNTHETIC_ID`, `ORGANISER`, etc., conditioned on a **party cell** (e.g. region, segment, product mix, simple graph features).

  * For accounts:

    * priors for roles such as `CLEAN_ACCOUNT`, `MULE_ACCOUNT`, `HIGH_RISK_ACCOUNT`, etc., conditioned on owner segment, product family, region, instrument mix.

  * For merchants:

    * priors for `NORMAL`, `COLLUSIVE`, `HIGH_RISK_MCC`, `MSB`, etc., conditioned on MCC, region, volume/graph features.

  * For devices/IPs (if statically labelled):

    * priors for `NORMAL_DEVICE`, `RISKY_DEVICE`, `BOT_LIKE_DEVICE`,
    * priors for `NORMAL_IP`, `DATACENTRE_IP`, `PROXY_IP`, `HIGH_RISK_IP`, etc., conditioned on type/asn_class/degree.

* **Fraud taxonomies** (`role="TAXONOMY"`):

  * enumerations of roles per entity type, e.g.:

    * `fraud_role_party` ∈ {`CLEAN`, `MULE`, `SYNTHETIC_ID`, …},
    * `fraud_role_account` ∈ {`CLEAN_ACCOUNT`, `MULE_ACCOUNT`, …},
    * `fraud_role_merchant`, `fraud_role_device`, `fraud_role_ip`,

  * any **static risk-tier** enums S5 will emit (e.g. `{LOW, STANDARD, ELEVATED, HIGH}`).

These priors and taxonomies are the sole authorities on:

* which labels exist,
* what they mean,
* and what target distributions S5 should aim for per cell.

#### 3.1.3 Validation policy / checklist (metadata + optional ROW_LEVEL)

From `sealed_inputs_6A` with roles such as `"VALIDATION_POLICY_6A"`, `"SEGMENT_CHECKLIST_6A"`:

* **Validation policy artefacts** define:

  * the set of **checks** S5 must run (coverage, consistency, proportion tolerances, structural invariants),
  * severity levels (e.g. `BLOCKING`, `WARN`, `INFO`),
  * whether any WARNs are allowed for a world to be considered PASS,
  * how to summarise issues in `s5_validation_report_6A` and `s5_issue_table_6A`.

They may be:

* `read_scope = "ROW_LEVEL"` (if expressed as tables), or
* `read_scope = "METADATA_ONLY"` (if expressed as config objects).

Either way, they are **authoritative** on what S5 must verify before emitting `_passed.flag_6A`.

#### 3.1.4 6A contracts (METADATA_ONLY)

From `sealed_inputs_6A` with `role="CONTRACT"` and `read_scope="METADATA_ONLY"`:

* `schemas.layer3.yaml`
* `schemas.6A.yaml`
* `dataset_dictionary.layer3.6A.yaml`
* `artefact_registry_6A.yaml`

S5 uses these to:

* discover schemas and paths for its outputs (fraud-role surfaces and validation artefacts),
* ensure its outputs are consistent with the catalogue.

S5 MUST NOT modify or reinterpret these contracts.

---

### 3.2 Upstream authority boundaries (Layer-1 & Layer-2)

S5 sits on top of a fully sealed L1/L2 world and Layer-3 modelling stack. The following boundaries are **binding**.

#### 3.2.1 Layer-1 & Layer-2

**Authority:**

* 1A–3B own: merchants, sites, zones, virtual overlay, routing structure, civil time, geo.
* 5A–5B own: arrival intensities, realised arrivals, bucket counts, arrival stream.

S5 **must not**:

* create or delete merchants or sites,
* change MCCs, merchant channels or country assignments,
* modify site coordinates, time zones, zone allocations, routing, or arrivals,
* rely on per-arrival behaviour for static roles — S5 is static posture only.

S5 may *use* coarse, sealed aggregates from these segments (if present in `sealed_inputs_6A`) as **context** (e.g. “high-volume MCCs”) but may not alter them.

#### 3.2.2 6A.S1–S4

Within 6A:

* **S1** is the sole authority on parties (`party_id`s, segments, home geo, static attributes).
* **S2** is the sole authority on accounts/products (`account_id`s, account→party/merchant mapping, product mix).
* **S3** is the sole authority on instruments/credentials (`instrument_id`s and their static attributes).
* **S4** is the sole authority on device & IP universes (`device_id`, `ip_id`) and static graph edges.

S5 **must not**:

* create any new IDs: no new parties/accounts/instruments/devices/IPs/merchants,
* change any attributes set by S1–S4,
* change any S4 graph edges.

S5 is layered **on top** of S1–S4; it annotates them with fraud roles and runs validation, but does not change the underlying world.

---

### 3.3 S5 authority boundaries

Within 6A, S5 has exactly two kinds of authority:

1. **Static fraud posture:**

   * To assign, per world+seed, static fraud roles and risk posture over:

     * parties,
     * accounts,
     * merchants,
     * instruments (if in scope),
     * devices & IPs.

   * These roles are **owned by S5**; no other 6A state may override them.

2. **6A closure & HashGate:**

   * To produce, per `manifest_fingerprint`, the **6A validation bundle** and `_passed.flag_6A`.
   * This is the **only** segment-level HashGate for 6A; 6B and outer systems must use it as the read gate for all 6A outputs.

S5 **must not**:

* define per-arrival or per-flow labels — those are 6B’s responsibility.
* define dynamic labels that depend on time/index within the arrival stream; its remit is *static* posture over the world S1–S4 define.

---

### 3.4 Forbidden dependencies & non-inputs

S5 explicitly **must not depend on**:

* Any artefact **not present** in `sealed_inputs_6A` for its `manifest_fingerprint`.

* Any artefact present with `read_scope="METADATA_ONLY"` for row-level fraud-role logic (beyond contracts and validation policies).

* Any 6B-level outputs (flows, scores, transaction labels, etc.).

* Wall-clock time or environment for semantics:

  * no “now” in role assignment,
  * no environment-specific toggles that change which roles are assigned.

* Any raw validation bundles from upstream segments beyond:

  * the verdicts and digests already validated by S0,
  * any specific evidence artefacts that S0 chooses to expose explicitly in `sealed_inputs_6A` with `role="CONTRACT"`.

If an implementation pulls in external files, services, or 6B outputs, it is **out of spec**, even if it appears to work.

---

### 3.5 How S0’s sealed-input manifest constrains S5

S5’s **effective input universe** is:

> all rows in `sealed_inputs_6A` for its `manifest_fingerprint` with
> `status ∈ {"REQUIRED","OPTIONAL"}`,
> plus S1–S4 base/link datasets for the relevant `(mf, seed)`.

S5 MUST:

1. Load `s0_gate_receipt_6A` and `sealed_inputs_6A`.

2. Verify `sealed_inputs_digest_6A` matches the recomputed digest.

3. Filter `sealed_inputs_6A` to:

   * fraud-role priors & taxonomies,
   * validation policy/checklist artefacts,
   * any optional context surfaces it is designed to use,
   * contracts (schemas/dictionary/registry) with `read_scope="METADATA_ONLY"`.

4. Treat any artefact that:

   * is absent from `sealed_inputs_6A` for this `mf`,
   * or has `status="IGNORED"`,
   * or has `read_scope="METADATA_ONLY"` but is not a contract or policy,

   as **off-limits** for S5’s business logic.

Downstream 6B and any external consumers can then safely assume:

* S5’s fraud roles and HashGate depend **only** on sealed, catalogued inputs for that world,
* there are no hidden ad-hoc dependencies,
* and any change to S5 priors/configs will be reflected in `sealed_inputs_6A` (and therefore in `sealed_inputs_digest_6A`), making it a different world from S5’s perspective.

---

## 4. Outputs (datasets) & identity *(Binding)*

6A.S5 produces two classes of outputs:

1. **Seed-scoped fraud-posture surfaces** — static fraud roles / risk posture over entities in the 6A graph.
2. **Fingerprint-scoped validation artefacts** — the 6A segment-level validation bundle and `_passed.flag_6A` HashGate.

These outputs are **binding** contracts for 6B and any external consumer. This section defines *what* they are, *what they mean*, and *how they are identified*.

---

### 4.1 Fraud-posture surfaces (seed-scoped)

For each `(manifest_fingerprint, seed)`, S5 emits fraud-role tables keyed by entity type. They all share:

* `manifest_fingerprint` — world identity,
* `parameter_hash` — parameter/prior pack identity,
* `seed` — RNG identity for this 6A universe.

S5 **must not** introduce new entity IDs here; every `party_id` / `account_id` / `merchant_id` / `device_id` / `ip_id` MUST exist in upstream bases.

#### 4.1.1 Party fraud roles

**Logical name:** `s5_party_fraud_roles_6A`
**Role:** static fraud posture for parties.

* **Domain & scope**

  For each `(mf, seed)`, contains **one row per party** in `s1_party_base_6A`.

* **Required content (logical fields)**

  * `manifest_fingerprint`, `parameter_hash`, `seed`

  * `party_id` — FK to `s1_party_base_6A` for `(mf, seed)`

  * `fraud_role_party` — enum from fraud taxonomy, e.g.:

    * `CLEAN`,
    * `MULE`,
    * `SYNTHETIC_ID`,
    * `ORGANISER`,
    * `ASSOCIATE`, …

  * optional `static_risk_tier_party` — e.g. `LOW`, `STANDARD`, `ELEVATED`, `HIGH`.

  * optional diagnostic fields (e.g. cell_id, risk_score_bucket) used for QA and validation but not for identity.

* **Identity & invariants**

  * Logical PK: `(manifest_fingerprint, seed, party_id)`.
  * Exactly one row per `party_id` in S1; no extra or missing parties.
  * `fraud_role_party` MUST be a valid enum value from the S5 taxonomy.

#### 4.1.2 Account fraud roles

**Logical name:** `s5_account_fraud_roles_6A`
**Role:** static fraud posture for accounts.

* **Domain & scope**

  For each `(mf, seed)`, contains **one row per account** in `s2_account_base_6A`.

* **Required content**

  * `manifest_fingerprint`, `parameter_hash`, `seed`

  * `account_id` — FK to `s2_account_base_6A`

  * optional `owner_party_id` — FK to `s1_party_base_6A` (redundant but convenient)

  * `fraud_role_account` — enum, e.g.:

    * `CLEAN_ACCOUNT`,
    * `MULE_ACCOUNT`,
    * `HIGH_RISK_ACCOUNT`,
    * `DORMANT_RISKY`, …

  * optional `static_risk_tier_account` (same tier taxonomy as parties or account-specific).

* **Identity & invariants**

  * PK: `(manifest_fingerprint, seed, account_id)`.
  * Exactly one row per `account_id` in S2.
  * FK to S2 and (if present) S1 must resolve.

#### 4.1.3 Merchant fraud roles

**Logical name:** `s5_merchant_fraud_roles_6A`
**Role:** static fraud posture for merchants (L1 world).

* **Domain & scope**

  For each `(mf, seed)` (or per `mf` if merchant roles are seed-independent), contains **one row per merchant** in the upstream merchant universe.

* **Required content**

  * `manifest_fingerprint`, `parameter_hash`, `seed` (or just `manifest_fingerprint` if seed-independent; the spec later will pin this choice)

  * `merchant_id` — FK to L1 merchant universe

  * `fraud_role_merchant` — enum, e.g.:

    * `NORMAL`,
    * `COLLUSIVE`,
    * `HIGH_RISK_MCC`,
    * `MONEY_SERVICE_BUSINESS`, …

  * optional `static_risk_tier_merchant`.

* **Identity & invariants**

  * PK: `(manifest_fingerprint, seed?, merchant_id)` as chosen in the schema.
  * Every `merchant_id` in this table must exist in upstream L1 egress.
  * No new merchants may be introduced here.

#### 4.1.4 Device fraud roles

**Logical name:** `s5_device_fraud_roles_6A`
**Role:** static fraud posture for devices.

* **Domain & scope**

  For each `(mf, seed)`, contains **one row per device** in `s4_device_base_6A`.

* **Required content**

  * `manifest_fingerprint`, `parameter_hash`, `seed`

  * `device_id` — FK to `s4_device_base_6A`

  * `fraud_role_device` — enum, e.g.:

    * `NORMAL_DEVICE`,
    * `RISKY_DEVICE`,
    * `BOT_LIKE_DEVICE`,
    * `SHARED_SUSPICIOUS_DEVICE`, …

  * optional `static_risk_tier_device`.

* **Identity & invariants**

  * PK: `(manifest_fingerprint, seed, device_id)`.
  * Exactly one row per `device_id` in S4; no new devices created.

#### 4.1.5 IP fraud roles

**Logical name:** `s5_ip_fraud_roles_6A`
**Role:** static fraud posture for IPs/endpoints.

* **Domain & scope**

  For each `(mf, seed)`, contains **one row per IP** in `s4_ip_base_6A`.

* **Required content**

  * `manifest_fingerprint`, `parameter_hash`, `seed`

  * `ip_id` — FK to `s4_ip_base_6A`

  * `fraud_role_ip` — enum, e.g.:

    * `NORMAL_IP`,
    * `PROXY_IP`,
    * `DATACENTRE_IP`,
    * `HIGH_RISK_IP`, …

  * optional `static_risk_tier_ip`.

* **Identity & invariants**

  * PK: `(manifest_fingerprint, seed, ip_id)`.
  * Exactly one row per `ip_id` in S4; no extra IPs created.

---

### 4.2 Validation artefacts & 6A HashGate (fingerprint-scoped)

These artefacts are **fingerprint-scoped**, not seed-scoped. They summarise:

* the outcome of S5’s validation checks across S1–S4 + fraud roles, and
* the evidence files that constitute the 6A validation bundle.

They live under a fingerprint-partitioned directory, for example:

```text
data/layer3/6A/validation/fingerprint={manifest_fingerprint}/...
```

#### 4.2.1 S5 validation report & issue table

**Logical names:**

* `s5_validation_report_6A`
* `s5_issue_table_6A` (optional but recommended)

**Role:** Structured summary and detailed issues from S5’s segment-level validation.

* **Domain & scope**

  * One logical **report** per `manifest_fingerprint` (per S5 run/spec version).
  * The issue table may have **zero or more rows per world**, each row describing a specific failing or borderline-check instance.

* **Required content (report)**

  The report object must include, at minimum:

  * `manifest_fingerprint`

  * `parameter_hash`

  * `spec_version_6A` / S5 version fields

  * `checks`: an array or map of:

    * `check_id`,
    * `check_description` (short text),
    * `severity ∈ {BLOCKING, WARN, INFO}`,
    * `status ∈ {PASS, FAIL, WARN}` (or compatible encoding),
    * optional metrics per check (counts, ratios, tolerances, etc.).

  * `overall_status ∈ {PASS, FAIL, WARN}` — with `PASS` meaning “eligible for `_passed.flag_6A`” per S5 policy.

  * optional `summary_metrics` — global counts, e.g. used later in dashboards.

* **Required content (issue table)**

  Each row should include:

  * `manifest_fingerprint`
  * `check_id`
  * `issue_id` (string or integer)
  * `severity`
  * `scope_type` (e.g. PARTY, ACCOUNT, MERCHANT, DEVICE, IP, or GLOBAL)
  * optional context identifiers (`seed`, `scenario_id`, `flow_id`, `case_id`, `event_seq`, or a cell index)
  * `message` describing the issue
  * optional fields: cell identifiers, numeric values for the failed check.

These datasets are **inputs** to the validation bundle, not stand-alone gates; the actual gate is `_passed.flag_6A`.

#### 4.2.2 6A validation bundle

**Logical name:** `validation_bundle_6A`
**Role:** directory-like bundle of evidence files and an index for 6A’s closure.

* **Contents**

  Under `validation/fingerprint={manifest_fingerprint}/`, S5 must materialise:

  * `validation_bundle_index_6A` - an index object that lists:

    * every file in the bundle (relative paths),
    * its `sha256_hex` digest,
    * its `role` (e.g. report, issue_table, summary, digest),
    * optional `schema_ref`.

  * evidence files referenced in the index, such as:

    * `s5_validation_report_6A.json`,
    * `s5_issue_table_6A.parquet` (if present),
    * additional summary/digest artefacts (e.g. per-entity-type counts, distribution snapshots),
    * optionally digests of S1–S4 bases, if you include them as part of S5’s closure.

* **Identity & invariants**

  * The index is **fingerprint-scoped**: only `manifest_fingerprint` matters, not `seed`.
  * The index order and digest law (which files are included, in what order) must be fixed and deterministic (details in later sections; here we only assert that there **is** such a law).

#### 4.2.3 `_passed.flag_6A` — 6A HashGate

**Logical name:** `validation_passed_flag_6A` (the `_passed.flag_6A` artefact)
**Role:** 6A segment-level HashGate: **no `_passed.flag_6A` → no read of 6A outputs**.

* **Domain & scope**

  * One small text file per `manifest_fingerprint`, stored under the same validation directory, e.g.:

    ```text
    data/layer3/6A/validation/fingerprint={manifest_fingerprint}/_passed.flag_6A
    ```

* **Required content**

  * `_passed.flag_6A` contains exactly one line:

    ```text
    sha256_hex = {bundle_digest_sha256}
    ```

    where `{bundle_digest_sha256}` is the SHA-256 digest computed over the evidence files listed in `validation_bundle_index_6A` according to the agreed law (canonical ordering, concatenation, etc.).

* **Identity & invariants**

  * Identity is simply `(manifest_fingerprint)`; S5 must treat this as **write-once** for a given bundle spec/version and priors.
  * Any consumer re-computing the bundle digest from `validation_bundle_index_6A` must obtain exactly `bundle_digest_sha256` from `_passed.flag_6A`.
  * If S5 is re-run for the same `manifest_fingerprint` and the same catalogue/prior state, the resulting `_passed.flag_6A` and `validation_bundle_6A` must be **byte-identical** or S5 must fail with an output-conflict error.

---

### 4.3 Relationship to upstream identity and downstream gating

* **Upstream alignment**

  * Fraud-role surfaces are keyed by `(manifest_fingerprint, seed, entity_id)` and must reference existing IDs from S1–S4 (and L1 for merchants).
  * Validation artefacts and `_passed.flag_6A` are **fingerprint-scoped** and rely on the same `manifest_fingerprint` and `parameter_hash` as S0–S4.

* **Downstream alignment**

  * 6B and any ingestion/enterprise components:

    * use fraud-role surfaces as the **canonical static posture** for entities (e.g. to seed campaigns and label flows),
    * must verify `_passed.flag_6A` (by recomputing the bundle digest from the index) before consuming any 6A outputs.

  * No downstream state is allowed to:

    * override S5 fraud roles (they may derive additional features on top, but not contradict them),
    * treat worlds without `_passed.flag_6A` as sealed.

In summary:

* Fraud-role datasets answer **“who is fraud-adjacent at the static entity level?”** for each `(mf, seed)`.
* The validation bundle & `_passed.flag_6A` answer **“is 6A sealed and safe to read?”** for each `manifest_fingerprint`.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

This section fixes **where the shapes for S5’s outputs live**, how they are wired into the **catalogue**, and how S5 and downstream consumers must discover and use them.

As everywhere else:

* **JSON-Schema + dataset dictionary are the only shape authorities.**
* This spec describes semantics and constraints; it must not be treated as an alternative schema.

S5 has two families of outputs:

1. **Fraud-posture surfaces (seed-scoped)**

   * `s5_party_fraud_roles_6A`
   * `s5_account_fraud_roles_6A`
   * `s5_merchant_fraud_roles_6A`
   * `s5_device_fraud_roles_6A`
   * `s5_ip_fraud_roles_6A`

2. **Validation & HashGate artefacts (fingerprint-scoped)**

   * `s5_validation_report_6A`
   * `s5_issue_table_6A` (optional)
   * `validation_bundle_index_6A` (6A bundle index)
   * `validation_bundle_6A` (bundle contents, directory of evidence)
   * `validation_passed_flag_6A` (the `_passed.flag_6A` HashGate)

---

### 5.1 JSON-Schema anchors (shape authority)

All S5 dataset shapes live under **Layer-3 / 6A schemas**, except for validation primitives, which are layer-wide.

Binding anchors (names indicative; you will define the exact pointers in your schema files):

#### 5.1.1 Fraud-posture surfaces (in `schemas.6A.yaml`)

* `schemas.6A.yaml#/s5/party_fraud_roles`

  * Required fields (conceptually):

    * `manifest_fingerprint`, `parameter_hash`, `seed`,
    * `party_id` (FK → `s1_party_base_6A`),
    * `fraud_role_party` (enum from party fraud-role taxonomy),
    * optional `static_risk_tier_party`, `cell_id`, etc.

* `schemas.6A.yaml#/s5/account_fraud_roles`

  * Required fields:

    * `manifest_fingerprint`, `parameter_hash`, `seed`,
    * `account_id` (FK → `s2_account_base_6A`),
    * optional `owner_party_id` (FK → `s1_party_base_6A`),
    * `fraud_role_account` (enum),
    * optional `static_risk_tier_account`.

* `schemas.6A.yaml#/s5/merchant_fraud_roles`

  * Required fields:

    * `manifest_fingerprint`, `parameter_hash`, `seed` (or just `manifest_fingerprint` if you choose merchant roles to be seed-independent; pick one and stick with it),
    * `merchant_id` (FK → L1 merchant universe),
    * `fraud_role_merchant` (enum),
    * optional `static_risk_tier_merchant`.

* `schemas.6A.yaml#/s5/device_fraud_roles`

  * Required fields:

    * `manifest_fingerprint`, `parameter_hash`, `seed`,
    * `device_id` (FK → `s4_device_base_6A`),
    * `fraud_role_device` (enum),
    * optional `static_risk_tier_device`.

* `schemas.6A.yaml#/s5/ip_fraud_roles`

  * Required fields:

    * `manifest_fingerprint`, `parameter_hash`, `seed`,
    * `ip_id` (FK → `s4_ip_base_6A`),
    * `fraud_role_ip` (enum),
    * optional `static_risk_tier_ip`.

Each of these schemas MUST:

* declare the logical primary key (`mf, seed, id`), via metadata if your schema flavour supports it,
* set `additionalProperties: false` (unless you have a documented extension mechanism),
* constrain `fraud_role_*` and any `*_risk_tier_*` fields to the appropriate enums from S5 taxonomies.

#### 5.1.2 Validation & HashGate shapes (in `schemas.layer3.yaml`)

Layer-3 validation primitives are shared across segments (you already have similar shapes for L1). For 6A, you must add anchors such as:

* `schemas.layer3.yaml#/validation/6A/validation_report_6A`

  * Object schema for `s5_validation_report_6A`, with:

    * `manifest_fingerprint`, `parameter_hash`,
    * `spec_version_6A` / `spec_version_6A_S5`,
    * `checks` array/map with `check_id`, `severity`, `status`, metrics,
    * `overall_status`.

* `schemas.layer3.yaml#/validation/6A/validation_issue_table_6A`

  * Tabular schema for `s5_issue_table_6A` (if implemented), with per-issue rows:

    * `manifest_fingerprint`,
    * `check_id`, `issue_id`, `severity`, `scope_type`,
    * optional `seed`, `scenario_id`, `flow_id`, `case_id`, `event_seq`,
    * `message`, optional metrics/context fields.

* `schemas.layer3.yaml#/validation/6A/validation_bundle_index_6A`

  * The index object listing bundle members:

    * `manifest_fingerprint`, `parameter_hash`, `spec_version_6A`,
    * `items: [ { path, sha256_hex, role, schema_ref? }, ... ]` sorted lexicographically by `path`.

* `schemas.layer3.yaml#/validation/6A/passed_flag_6A`

  * `_passed.flag_6A` is a plain-text value whose entire content is exactly:

    ```
    sha256_hex = {bundle_digest_sha256}
    ```

These shapes MUST align with your pre-existing HashGate law (same digest rules used in 1A–3B; just extended for 6A).

---

### 5.2 Dataset dictionary entries (catalogue links)

`dataset_dictionary.layer3.6A.yaml` MUST define entries for:

* each S5 fraud-role dataset (seed-scoped), and
* each validation artefact (fingerprint-scoped).

Below are **informal sketches**; exact YAML follows your house style.

#### 5.2.1 Party fraud roles (required)

```yaml
- id: s5_party_fraud_roles_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Static fraud posture for parties in Layer-3 / Segment 6A.
    One row per party per (manifest_fingerprint, seed), with
    fraud_role_party and optional static risk tier.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s5_party_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/s5_party_fraud_roles_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [party_id]
  schema_ref: schemas.6A.yaml#/s5/party_fraud_roles
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
      - '6B.S2'
  pii_class: synthetic_customer
  retention_class: core_entity
```

#### 5.2.2 Account fraud roles (required)

```yaml
- id: s5_account_fraud_roles_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Static fraud posture for accounts in Layer-3 / Segment 6A.
    One row per account per (manifest_fingerprint, seed), keyed by
    account_id, consistent with s2_account_base_6A.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s5_account_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/s5_account_fraud_roles_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [account_id]
  schema_ref: schemas.6A.yaml#/s5/account_fraud_roles
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
      - '6B.S2'
  pii_class: synthetic_customer
  retention_class: core_entity
```

#### 5.2.3 Merchant fraud roles (required)

```yaml
- id: s5_merchant_fraud_roles_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Static fraud posture for merchants in Layer-3 / Segment 6A.
    One row per merchant, keyed by merchant_id.
  version: '{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s5_merchant_fraud_roles_6A/fingerprint={manifest_fingerprint}/s5_merchant_fraud_roles_6A.parquet
  partitioning: [fingerprint]   # if seed-independent; otherwise [seed, fingerprint]
  ordering: [merchant_id]
  schema_ref: schemas.6A.yaml#/s5/merchant_fraud_roles
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
      - '6B.S2'
  pii_class: synthetic_customer
  retention_class: core_entity
```

(If you decide merchant roles are seed-scoped, change `version` and `partitioning` to include `seed` — but make that choice once and stick with it.)

#### 5.2.4 Device & IP fraud roles (required if you include them in S5)

```yaml
- id: s5_device_fraud_roles_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Static fraud posture for devices in Layer-3 / Segment 6A.
    One row per device per (manifest_fingerprint, seed), keyed by device_id.
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s5_device_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/s5_device_fraud_roles_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [device_id]
  schema_ref: schemas.6A.yaml#/s5/device_fraud_roles
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
  pii_class: synthetic_customer
  retention_class: core_entity
```

```yaml
- id: s5_ip_fraud_roles_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Static fraud posture for IPs/endpoints in Layer-3 / Segment 6A.
    One row per ip_id per (manifest_fingerprint, seed).
  version: '{seed}.{manifest_fingerprint}.{parameter_hash}'
  path: data/layer3/6A/s5_ip_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/s5_ip_fraud_roles_6A.parquet
  partitioning: [seed, fingerprint]
  ordering: [ip_id]
  schema_ref: schemas.6A.yaml#/s5/ip_fraud_roles
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
  pii_class: synthetic_customer
  retention_class: core_entity
```

#### 5.2.5 Validation report & issue table (fingerprint-scoped)

```yaml
- id: s5_validation_report_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Segment-level validation report for Layer-3 / Segment 6A,
    summarising the results of S5 checks across S1–S4 and S5 fraud roles.
  version: '{manifest_fingerprint}'
  path: data/layer3/6A/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6A.json
  partitioning: [fingerprint]
  ordering: []
  schema_ref: schemas.layer3.yaml#/validation/6A/validation_report_6A
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
  pii_class: none
  retention_class: engine_control_plane
```

```yaml
- id: s5_issue_table_6A
  owner_layer: 3
  owner_segment: 6A
  status: optional
  description: >
    Row-level issue table for 6A validation, containing one row per
    failing/ borderline check instance.
  version: '{manifest_fingerprint}'
  path: data/layer3/6A/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6A.parquet
  partitioning: [fingerprint]
  ordering: [check_id, scope_type, issue_id]
  schema_ref: schemas.layer3.yaml#/validation/6A/validation_issue_table_6A
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
  pii_class: synthetic_customer
  retention_class: engine_control_plane
```

#### 5.2.6 Bundle index & `_passed.flag_6A`

```yaml
- id: validation_bundle_index_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    Index for the Layer-3 / Segment 6A validation bundle, listing
    all evidence files and their SHA-256 digests.
  version: '{manifest_fingerprint}'
  path: data/layer3/6A/validation/fingerprint={manifest_fingerprint}/validation_bundle_index_6A.json
  partitioning: [fingerprint]
  ordering: []
  schema_ref: schemas.layer3.yaml#/validation/6A/validation_bundle_index_6A
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
  pii_class: none
  retention_class: engine_control_plane
```

```yaml
- id: validation_passed_flag_6A
  owner_layer: 3
  owner_segment: 6A
  status: required
  description: >
    HashGate flag for Layer-3 / Segment 6A. Contains the SHA-256
    digest over the validation bundle for this manifest_fingerprint.
  version: '{manifest_fingerprint}'
  path: data/layer3/6A/validation/fingerprint={manifest_fingerprint}/_passed.flag_6A
  partitioning: [fingerprint]
  ordering: []
  schema_ref: schemas.layer3.yaml#/validation/6A/passed_flag_6A
  columns_strict: true
  lineage:
    produced_by: [ '6A.S5' ]
    consumed_by:
      - '6B.S0'
      - '6B.S1'
  pii_class: none
  retention_class: engine_control_plane
```

(Here `columns_strict: true` means the JSON must adhere exactly to the declared schema shape.)

---

### 5.3 Artefact registry entries (runtime manifests)

`artefact_registry_6A.yaml` MUST register S5 outputs with stable `manifest_key`s and explicit dependencies.

Examples (informal):

#### 5.3.1 Fraud-role surfaces

```yaml
- manifest_key: engine.layer3.6A.s5.party_fraud_roles
  owner_layer: 3
  owner_segment: 6A
  dataset_id: s5_party_fraud_roles_6A
  semver: 1.0.0
  path_template: data/layer3/6A/s5_party_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/s5_party_fraud_roles_6A.parquet
  partition_keys: [seed, fingerprint]
  schema_ref: schemas.6A.yaml#/s5/party_fraud_roles
  produced_by: 6A.S5
  dependencies:
    - engine.layer3.6A.s0_gate_receipt
    - engine.layer3.6A.sealed_inputs
    - engine.layer3.6A.s1.party_base
    - engine.layer3.6A.s5.prior.party_roles      # example prior manifest_key
  retention_class: core_entity
  pii_class: synthetic_customer
```

You’d mirror this pattern for account/merchant/device/ip fraud roles:

```yaml
- manifest_key: engine.layer3.6A.s5.account_fraud_roles
  dataset_id: s5_account_fraud_roles_6A
  produced_by: 6A.S5
  dependencies:
    - engine.layer3.6A.s2.account_base
    - engine.layer3.6A.s1.party_base
    - engine.layer3.6A.s5.prior.account_roles
```

… and so on.

#### 5.3.2 Validation bundle & flag

```yaml
- manifest_key: engine.layer3.6A.validation.bundle_6A
  owner_layer: 3
  owner_segment: 6A
  dataset_id: validation_bundle_index_6A
  semver: 1.0.0
  path_template: data/layer3/6A/validation/fingerprint={manifest_fingerprint}/validation_bundle_index_6A.json
  partition_keys: [fingerprint]
  schema_ref: schemas.layer3.yaml#/validation/6A/validation_bundle_index_6A
  produced_by: 6A.S5
  dependencies:
    - engine.layer3.6A.s0_gate_receipt
    - engine.layer3.6A.s1.party_base
    - engine.layer3.6A.s2.account_base
    - engine.layer3.6A.s3.instrument_base
    - engine.layer3.6A.s4.device_base
    - engine.layer3.6A.s4.ip_base
    - engine.layer3.6A.s5.party_fraud_roles
    - engine.layer3.6A.s5.account_fraud_roles
    - engine.layer3.6A.s5.merchant_fraud_roles
    - engine.layer3.6A.s5.device_fraud_roles
    - engine.layer3.6A.s5.ip_fraud_roles
  retention_class: engine_control_plane
  pii_class: none
```

```yaml
- manifest_key: engine.layer3.6A.validation.passed_flag_6A
  owner_layer: 3
  owner_segment: 6A
  dataset_id: validation_passed_flag_6A
  semver: 1.0.0
  path_template: data/layer3/6A/validation/fingerprint={manifest_fingerprint}/_passed.flag_6A
  partition_keys: [fingerprint]
  schema_ref: schemas.layer3.yaml#/validation/6A/passed_flag_6A
  produced_by: 6A.S5
  dependencies:
    - engine.layer3.6A.validation.bundle_6A
  retention_class: engine_control_plane
  pii_class: none
```

These registry entries give CI/orchestration:

* stable keys for S5 artefacts,
* explicit dependency graphs for change impact and job ordering.

---

### 5.4 Catalogue discovery rules (for S5 and downstream consumers)

All S5 implementations and downstream consumers (6B, enterprise ingestion, tooling) MUST use the catalogue, **not** hard-coded paths or ad-hoc schemas.

**Shape discovery:**

1. Given a dataset ID (e.g. `s5_party_fraud_roles_6A`):

   * look it up in `dataset_dictionary.layer3.6A.yaml`,
   * read `schema_ref`,
   * resolve `schema_ref` in `schemas.6A.yaml` (or `schemas.layer3.yaml` for validation artefacts),
   * treat that JSON-Schema as the **only** shape authority.

2. Do **not** derive shapes from ORMs, structs, or existing data — those must conform to the schema, not redefine it.

**Location discovery:**

1. From the dictionary (and registry if needed):

   * read `path` / `path_template` and `partitioning`,
   * substitute `seed={seed}`, `fingerprint={manifest_fingerprint}` (or just `fingerprint` for fingerprint-scoped artefacts).

2. Do **not** hard-code file-system or object-store paths.

**No shadow datasets / shapes:**

* S5 MUST NOT write extra tables for fraud roles or validation artefacts that are not declared in dictionary/registry.
* Downstream MUST NOT read “sidecar” variants with diverging schemas or paths.

**No hidden merge rules:**

* Replace/merge semantics are defined in §7 (replace-not-append per `(mf, seed)` for roles, per `mf` for bundle/flag).
* Dictionary/registry partition definitions must match those semantics; implementations must respect them.

With these anchors, dictionary entries, and registry manifests in place, S5’s outputs are:

* globally **discoverable** via the catalogue,
* **uniquely shaped** by JSON-Schema,
* and correctly scoped (seed- or fingerprint-scoped) so that 6B and the enterprise shell can reliably gate on `_passed.flag_6A` and consume fraud-posture surfaces.

---

## 6. Deterministic algorithm (with RNG — fraud roles & 6A HashGate) *(Binding)*

6A.S5 must be **deterministic given**:

* the sealed 6A input universe (`s0_gate_receipt_6A`, `sealed_inputs_6A`),
* the S1–S4 bases & links (`s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`, `s4_device_base_6A`, `s4_ip_base_6A`, plus their link/holding tables),
* S5 priors & taxonomies (fraud-role priors, fraud-role enums, validation policy),
* `manifest_fingerprint`, `parameter_hash`, and `seed`.

This section defines **exactly what S5 does**, the **phase ordering**, and which parts are **RNG-bearing vs RNG-free**.
Implementers can choose how to code it, but **not** change the observable behaviour.

---

### 6.0 Overview & RNG discipline

For each `(manifest_fingerprint, seed)`:

1. Load gates, priors, taxonomies & validation policy (RNG-free).
2. Build deterministic **feature & cell surfaces** for each entity type (RNG-free).
3. Derive **continuous role targets** per entity cell (RNG-free).
4. Realise **integer role counts** per cell (RNG-bearing, optional if policy uses exact matching).
5. Assign **fraud roles to individual entities** (RNG-bearing) using those counts and features.
6. Run **segment-level validation checks** across S1–S4 + S5 (RNG-free).
7. Assemble the **6A validation bundle** & compute the **HashGate** (`_passed.flag_6A`) (RNG-free).

RNG discipline:

* S5 uses the Layer-3 Philox envelope; substreams keyed on:

  ```text
  (manifest_fingerprint, seed, "6A.S5", substream_label, context...)
  ```

* At minimum, distinct RNG families MUST exist for:

  * `fraud_role_sampling_party`
  * `fraud_role_sampling_account`
  * `fraud_role_sampling_merchant`
  * `fraud_role_sampling_device`
  * `fraud_role_sampling_ip`

  (You may internally split “count realisation” vs “per-entity sampling” per family, but these are the externally visible families.)

* Every RNG event MUST:

  * log `counter_before` / `counter_after`,
  * log `blocks`, `draws`,
  * include contextual identifiers (world, seed, entity type, cell ID, role family),
  * be incorporated in Layer-3 RNG trace/audit logs.

No RNG is used for schemas, paths, partitioning, or the HashGate digest.

---

### 6.1 Phase 1 — Load gates, priors, taxonomies & validation policy *(RNG-free)*

**Goal:** ensure S5 runs only on sealed worlds and with known priors/policies.

1. **Verify S0 gate & sealed inputs**

   * Read `s0_gate_receipt_6A` and `sealed_inputs_6A` for `manifest_fingerprint`.
   * Recompute `sealed_inputs_digest_6A` and ensure it matches the digest in the gate receipt.
   * Confirm `upstream_gates` shows `gate_status="PASS"` for `{1A,1B,2A,2B,3A,3B,5A,5B}`.

2. **Verify S1–S4 gates for `(mf, seed)`**

   * Latest S1, S2, S3, S4 run-reports for `(mf, seed)` MUST each have `status="PASS"` and empty `error_code`.
   * For each:

     * locate their base/link datasets via the dictionary/registry,
     * validate against their schema anchors,
     * verify counts match the corresponding run-report metrics (e.g. `total_parties`, `total_accounts`, `total_instruments`, `total_devices`, `total_ips`).

3. **Select S5-relevant `sealed_inputs_6A` rows**

   * Filter sealed-inputs entries with:

     * `role ∈ {"FRAUD_ROLE_PRIOR","FRAUD_PRIOR","TAXONOMY","VALIDATION_POLICY_6A","SEGMENT_CHECKLIST_6A"}`,
     * `status ∈ {"REQUIRED","OPTIONAL"}`.

   * Split them into:

     * fraud-role priors per entity type,
     * fraud taxonomies (`fraud_role_party`, `fraud_role_account`, etc.),
     * validation policy/checklist artefacts,
     * any optional context surfaces S5 is allowed to use,
     * contracts (schemas/dictionary/registry) with `read_scope="METADATA_ONLY"`.

4. **Load & validate priors/taxonomies**

   * For each required prior/taxonomy artefact:

     * resolve its path using `path_template` + `partition_keys`,
     * read contents and validate against `schema_ref`,
     * recompute SHA-256 digest and compare to `sha256_hex`.

   * Build in-memory structures:

     * per-entity-type priors `π_role|cell(entity_type, cell, role)`,
     * taxonomies for roles and risk tiers.

5. **Load validation policy/checklist**

   * Read S5 validation policy artefacts (row-level or object) defining:

     * `check_id`, `description`, `severity`,
     * formulas for metrics,
     * thresholds/tolerances,
     * conditions for `overall_status` to be considered PASS/WARN/FAIL.

This phase is **deterministic** and must either succeed or fail with `6A.S5.*` gate/prior/taxonomy errors. No RNG.

---

### 6.2 Phase 2 — Construct feature & cell surfaces *(RNG-free)*

**Goal:** build deterministic features per entity and assign each entity to a **fraud cell** for prior application.

S5 does this separately per entity type (party, account, merchant, device, IP). For each entity type `E`:

1. **Compute structural features**

   * From S1–S4 bases & links compute, per entity:

     * segmentation attributes (e.g. segment, region, party_type, account_type, MCC),
     * product/instrument features (e.g. number of cards/accounts/loans, card-heavy vs card-light),
     * graph features (e.g. degree statistics in device/IP graph, sharing patterns),
     * any other features the S5 priors reference.

   * These features MUST be:

     * deterministic functions of S1–S4 outputs (no randomness),
     * stable under re-run for the same inputs.

2. **Define fraud cells**

   * For each entity type, define a **cell** as a combination of:

     * core segmentation (region, segment, type),
     * coarse product structure (e.g. account_type_class, MCC_group),
     * coarse graph buckets (e.g. degree buckets for devices/IPs, “has_shared_device”, “has_datacentre_ip”),
     * any other dimension referenced by priors.

   * Example (for parties):

     ```text
     cell_party = (region_id, segment_id, party_type, card_density_bucket, shared_device_bucket, ip_profile_bucket)
     ```

   * Assign each entity to exactly one cell per entity type (no overlaps; cells must partition the entities).

3. **Aggregate counts per cell**

   * For each entity type `E` and cell `c`:

     ```text
     N_entities_E(c) = number of entities of type E assigned to cell c
     ```

   * Cells with `N_entities_E(c) = 0` may be dropped from subsequent steps.

This phase is **RNG-free** and sets up the surfaces where S5 priors will be applied.

---

### 6.3 Phase 3 — Derive continuous role targets per cell *(RNG-free)*

**Goal:** for each entity type, compute **continuous target counts** of each fraud role per cell from priors.

For each entity type `E` (party/account/merchant/device/ip) and each cell `c`:

1. **Fetch priors**

   * From the loaded S5 priors, get:

     ```text
     π_role|E,c(role)   for role ∈ RoleSet_E
     ```

   * These MUST be non-negative and typically sum to 1 per cell (or as per prior schema, with a normalisation step if specified).

2. **Compute continuous targets**

   * For each role:

     ```text
     N_target_E(c, role) = N_entities_E(c) * π_role|E,c(role)
     ```

3. **Sanity checks**

   * For each `(E, c)`:

     * all `N_target_E(c, role)` are finite and ≥ 0,
     * Σ_role `N_target_E(c, role)` is within a small tolerance of `N_entities_E(c)` (prior normalisation issues must be surfaced).

   * For each entity type E:

     * global continuous totals `N_target_E_world(role) = Σ_c N_target_E(c, role)` are finite,
     * configured global targets/intervals (e.g. overall mule rate bands) are satisfied up to allowed tolerance, unless the validation policy explicitly treats them only as QA metrics.

If any invariant is violated (e.g. NaN/Inf targets, negative targets, sums wildly off N_entities), S5 MUST fail with `6A.S5.FRAUD_ROLE_TARGETS_INCONSISTENT` and not proceed to integerisation.

This phase is **RNG-free**.

---

### 6.4 Phase 4 — Realise integer role counts per cell *(RNG-bearing, per policy)*

**Goal:** convert continuous `N_target_E(c, role)` into integer counts `N_role_E(c, role)` that S5 will actually assign, subject to policy.

Depending on validation policy, S5 may:

* aim for **exact** integer counts per cell (if roles must match priors closely), or
* treat `N_target_E(c, role)` as **soft recommendations** and only enforce global or per-cell ratio bands.

We define the strict version (integerisation); a policy can choose to bypass this and let per-entity sampling determine realised counts, but still must obey global constraints.

For each entity type `E`:

1. **Compute floors & residuals per cell/role**

   * For each cell `c` and role:

     ```text
     N_floor_E(c, role) = floor(N_target_E(c, role))
     r_E(c, role)       = N_target_E(c, role) - N_floor_E(c, role)
     ```

   * For each cell:

     ```text
     N_floor_sum_E(c) = Σ_role N_floor_E(c, role)
     R_cell(c)        = N_entities_E(c) - N_floor_sum_E(c)
     ```

2. **Allocate remaining units via RNG**

   * If `R_cell(c) > 0`:

     * use a `fraud_role_sampling_*` RNG family (e.g. `fraud_role_sampling_party` for parties) to add `R_cell(c)` extra role counts across roles in that cell, proportionally to residuals `r_E(c, role)`.

   * Result: integer counts:

     ```text
     N_role_E(c, role) ≥ 0
     Σ_role N_role_E(c, role) == N_entities_E(c)
     ```

3. **Emit RNG events**

   * For each entity type E and cell c:

     * emit `rng_event_fraud_role_count_E` (conceptual name, implemented via the relevant S5 RNG family):

       * context: `(mf, ph, seed, entity_type=E, cell_id=c)`,
       * envelope: `counter_before`, `counter_after`, `blocks`, `draws`,
       * optional summary: target vs realised role fractions for that cell.

4. **Sanity & constraint checks**

   * Optionally apply global constraints, e.g.:

     * some roles must have at least N_world_min occurrences globally,
     * some roles may have at most N_world_max occurrences.

   * If integerised counts cannot satisfy these constraints without violating priors beyond acceptable tolerance, S5 must either:

     * downgrade the run to WARN in the report (if policy allows), or
     * fail with `6A.S5.FRAUD_ROLE_ASSIGNMENT_FAILED`.

This phase is **RNG-bearing**. It defines *how many* entities per cell & role S5 will label.

---

### 6.5 Phase 5 — Assign fraud roles to individual entities *(RNG-bearing)*

**Goal:** for each entity type, assign a **single fraud role** (per taxonomy) to each entity, such that per-cell realised counts `N_realised_E(c, role)` match `N_role_E(c, role)` (or are within policy-specified tolerances).

S5 performs this separately for each entity type `E`. For each entity type:

#### 6.5.1 Compute per-entity scores (RNG-free)

For each entity `e` of type E:

1. **Gather features**

   * From the feature surfaces constructed in Phase 2 (and possibly from cross-type joins, e.g. devices per party, IP risk mix, etc.).

2. **Compute a deterministic score vector per role**

   * Using an S5-defined scoring function, for example:

     ```text
     score_E(e, role) = f_E( features(e), role, priors_for_cell(c_e, role) )
     ```

   * This function:

     * MUST be deterministic,
     * MUST NOT use RNG,
     * may be linear/logistic or piecewise over features; it is part of S5’s model design.

3. **Rank entities within each cell**

   * For each cell `c` and role `role`, define an ordering of entities in that cell by descending `score_E(e, role)`.
   * Ties MUST be broken deterministically using a fixed secondary key (e.g. entity ID) or, if required, via a tiebreak RNG event from the same S5 family.

#### 6.5.2 Assign roles using counts (RNG-bearing only for tie-breaks / overflow)

There are at least two reasonable patterns; the spec allows either if it is clearly pinned. A common pattern:

1. **Role assignment order**

   * Define a global, fixed priority order of roles per entity type, e.g.:

     * Parties: `MULE`, `SYNTHETIC_ID`, `ORGANISER`, `ASSOCIATE`, `CLEAN`.
     * Accounts: `MULE_ACCOUNT`, `HIGH_RISK_ACCOUNT`, `CLEAN_ACCOUNT`, etc.

2. **Greedy assignment per cell**

   * For each entity type E and cell c:

     * Start with all entities in `c` unassigned.
     * For each role in priority order:

       * take the top `N_role_E(c, role)` unassigned entities in that cell according to `score_E(e, role)`,
       * assign them that role,
       * mark them as assigned (they will not be used for other roles).

   * If `N_role_E(c, CLEAN)` is left as “what’s left” after all other roles, it will automatically be the remainder.

3. **RNG usage (optional, for tie-breaking/adjustments)**

   * If you need to break ties between entities with identical scores or need to randomly choose among similar candidates, you may:

     * use the appropriate `fraud_role_sampling_*` RNG family to select among tied entities,
     * emit an `rng_event_fraud_role_sampling_E` per tie-broken batch.

   * Under no circumstances may you reintroduce stochasticity that changes the aggregate counts per cell & role beyond what Phase 4 determined, except as allowed by the validation policy.

4. **Resulting fraud-role surfaces**

   * For each entity type E, and each entity `e`:

     * exactly one `fraud_role_E` is assigned from the taxonomy;
     * `fraud_role_E` is consistent with `N_role_E(c_e, role)` realised counts, up to any tolerances.

#### 6.5.3 Build fraud-role tables *(RNG-free)*

Using assignments above:

* Construct `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_merchant_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A` rows with:

  * identity columns (`manifest_fingerprint`, `parameter_hash`, `seed`, `*_id`),
  * corresponding `fraud_role_*` and optional `static_risk_tier_*`.

* Validate:

  * per-table PK uniqueness,
  * full coverage of entity bases (no missing or extra entities),
  * role values belong to their taxonomies.

Any failure here is an S5 error (`FRAUD_ROLE_ASSIGNMENT_FAILED`, `FRAUD_ROLE_PROP_MISMATCH`, etc.).

---

### 6.6 Phase 6 — Segment-level validation & QA checks *(RNG-free)*

**Goal:** run the validation policy for 6A segment closure and produce:

* `s5_validation_report_6A` (summary),
* `s5_issue_table_6A` (optional row-level issues).

Using:

* S1–S4 base/link datasets,
* S5 fraud-role tables,
* the S5 validation policy/checklist, S5 MUST:

1. **Compute per-check metrics**

   * For each `check_id` defined in policy (e.g. `PARTY_ROLE_COVERAGE`, `MULE_RATE_PER_SEGMENT`, `MERCHANT_COLLUSION_DENSITY`, `DEVICE_GRAPH_SANITY`):

     * compute required metrics (counts, proportions, min/mean/max, quantiles, etc.),
     * compare against thresholds/tolerances,
     * determine `result ∈ {PASS, WARN, FAIL}` for that check.

2. **Populate report**

   * Build a single `s5_validation_report_6A` object for the `manifest_fingerprint` with:

     * `manifest_fingerprint`, `parameter_hash`, `spec_version_6A` / S5 version,

     * full list of checks with:

       * `check_id`, `description`, `severity`, `status`, metrics,
       * any derived flags (e.g. `threshold_exceeded`.

     * `overall_status` determined by combining per-check results according to policy (e.g. any `BLOCKING` check with `FAIL` → `overall_status=FAIL`).

3. **Populate issue table (if implemented)**

   * For checks that operate at entity/cell level and warrant fine-grained reporting, S5 may generate rows in `s5_issue_table_6A`:

     * one row per failing/borderline entity or cell, with:

       * `manifest_fingerprint`, `check_id`, `issue_id`, `severity`, `scope_type`,
       * optional `seed`, `scenario_id`, `flow_id`, `case_id`, `event_seq` (or cell index keys),
       * `message`, optional metrics.

4. **Decide eligibility for HashGate**

   * Based on `overall_status` and check severities, policy MUST explicitly define when 6A is eligible for `_passed.flag_6A`. In this spec:

     * `overall_status="PASS"` means “eligible to emit `_passed.flag_6A`”.
     * `overall_status="FAIL"` means “must NOT emit or must revoke `_passed.flag_6A`”.
     * `overall_status="WARN"` MAY be allowed by policy for `_passed.flag_6A` (if WARN-level issues are considered acceptable) or treated like FAIL; this must be clearly specified in your validation policy.

This phase is **RNG-free**.

---

### 6.7 Phase 7 — Assemble validation bundle & emit HashGate *(RNG-free)*

**Goal:** assemble the 6A validation bundle for this world and emit `_passed.flag_6A` if and only if validation conditions are met.

#### 6.7.1 Build validation bundle contents

For `manifest_fingerprint`:

1. **Determine evidence set**

   * The bundle MUST include at least:

     * `s5_validation_report_6A`,
     * `s5_issue_table_6A` (if present),
     * any additional evidence mandated by policy (e.g. summary JSON/Parquet with per-entity-type counts, set of S5 priors in canonical form, digests of S1–S4 bases if preferred).

   * Only include files that are fully written and schema-valid.

2. **Write evidence files**

   * Materialise evidence files under:

     ```text
     data/layer3/6A/validation/fingerprint={manifest_fingerprint}/...
     ```

   * Use schemas anchored in `schemas.layer3.yaml` / `schemas.6A.yaml`.

#### 6.7.2 Build `validation_bundle_index_6A`

1. **Collect paths**

   * Enumerate all evidence files that are part of the bundle, using **relative paths** from the bundle root directory.
   * Sort paths in strict ASCII-lexicographic order.

2. **Compute per-file digests**

   * For each file in this order:

     * read its raw bytes,
     * compute `sha256_hex(file)`.

3. **Build index object**

   * Write `validation_bundle_index_6A` as:

     * `manifest_fingerprint`, `parameter_hash`, `spec_version_6A`,
     * `items: [ { path, sha256_hex, role, schema_ref? }, ... ]`,
     * optional `index_version`, `created_utc`.

   * Persist it in the same validation directory.

#### 6.7.3 Compute bundle digest & write `_passed.flag_6A`

1. **Compute bundle digest**

   * Concatenate the raw bytes of all evidence files listed in `validation_bundle_index_6A`, in the index’s path order.

   * Compute:

     ```text
     bundle_digest_sha256 = SHA256(concatenated_bytes)
     ```

   * Represent `bundle_digest_sha256` as a 64-character lowercase hex string.

2. **Eligibility check**

   * If `s5_validation_report_6A.overall_status` meets the policy’s criteria for PASS (e.g. `overall_status="PASS"` and no blocking checks failed):

     * proceed to write `_passed.flag_6A` with:

       * `manifest_fingerprint`,
       * `bundle_digest_sha256`,
       * optional `parameter_hash`, `spec_version_6A`, `created_utc`.

   * If not eligible:

     * do **not** write `_passed.flag_6A`,
     * or overwrite an existing valid flag; treat this world as unsealed.

3. **Re-read and verify flag**

   * Re-read `_passed.flag_6A` from storage and verify:

     * `bundle_digest_sha256` matches the recomputed value,
     * `manifest_fingerprint` matches.

   * If any mismatch occurs, fail with `6A.S5.VALIDATION_DIGEST_MISMATCH` / `6A.S5.IO_WRITE_FAILED` and treat S5 as FAIL.

#### 6.7.4 Idempotency & conflict behaviour

* If S5 is re-run on the **same** `manifest_fingerprint` with the **same** catalogue state and priors:

  * it MUST either produce byte-identical `validation_bundle_index_6A`, evidence files, and `_passed.flag_6A`, or
  * fail with `6A.S5.OUTPUT_CONFLICT` and not modify existing outputs.

* S5 MUST NEVER:

  * silently overwrite an existing `_passed.flag_6A` with a different `bundle_digest_sha256`,
  * emit multiple inconsistent bundles for the same `manifest_fingerprint` without changing spec version.

This phase is **RNG-free**.

---

### 6.8 Determinism guarantees

Given:

* `manifest_fingerprint`,
* `parameter_hash`,
* `seed`,
* sealed S0–S4 inputs,
* sealed S5 priors/taxonomies/validation policies,

S5’s outputs:

* fraud-role tables (`s5_*_fraud_roles_6A` per entity type, per `(mf, seed)`),
* validation artefacts (`s5_validation_report_6A`, `s5_issue_table_6A`),
* `validation_bundle_index_6A`,
* `_passed.flag_6A`,

MUST be:

* **Bit-stable & idempotent**:

  * re-running S5 with the same inputs and seed (and same spec version) MUST produce byte-identical outputs.

* **Independent of**:

  * internal parallelism or scheduling,
  * physical file layout beyond the canonical ordering used for the bundle,
  * environment-specific details (hostnames, wall-clock, process IDs).

All randomness MUST flow exclusively through the declared S5 RNG families under the Layer-3 envelope and be fully accounted in RNG logs. Any change to:

* fraud-cell definitions,
* mapping from priors & features to role counts/assignments,
* validation policies and thresholds,
* the 6A HashGate digest law,

is a behavioural change and MUST be handled via S5’s change-control & versioning (§12), not as a hidden implementation detail.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

This section fixes **how S5’s outputs are identified, partitioned, ordered, and merged**.
All downstream components (especially 6B and any ingestion layer) must treat these rules as **part of the contract**, not implementation detail.

S5 has two families of outputs:

* **Seed-scoped fraud-posture surfaces** (over entities)

  * `s5_party_fraud_roles_6A`
  * `s5_account_fraud_roles_6A`
  * `s5_merchant_fraud_roles_6A`
  * `s5_device_fraud_roles_6A`
  * `s5_ip_fraud_roles_6A`

* **Fingerprint-scoped validation & HashGate artefacts**

  * `s5_validation_report_6A`
  * `s5_issue_table_6A` (optional)
  * `validation_bundle_index_6A`
  * `validation_passed_flag_6A` (aka `_passed.flag_6A`)

---

### 7.1 Identity axes

S5 uses the same identity axes as the other 6A states, with a split between **seed-scoped** and **world-scoped** artefacts:

* **World identity**

  * `manifest_fingerprint`
  * Identifies the sealed upstream world and 6A input universe.
  * All S5 outputs are tied to exactly one `manifest_fingerprint`.

* **Parameter identity**

  * `parameter_hash`
  * Identifies the priors/config pack (including S5 fraud priors and validation policy).
  * Stored as a **column** in S5 outputs; not used as a partition key.
  * For a given `(manifest_fingerprint, seed)`, all S5 surfaces must share the same `parameter_hash`.

* **RNG identity**

  * `seed`
  * Distinguishes different realisations of fraud posture across the same world & priors.
  * Different seeds under the same `(mf, ph)` yield different fraud-role assignments over the same structural graph.

* **Segment-level identity** (HashGate)

  * The 6A validation bundle & `_passed.flag_6A` are **fingerprint-scoped** only:

    * they summarise validation across *all* seeds for a given `manifest_fingerprint`,
    * they do not carry `seed` as a partition key.

`run_id` remains a **logging-only** identity (run-report); S5 business outputs MUST NOT depend on it.

---

### 7.2 Partitioning & path tokens

S5 outputs come in two partitioning regimes:

1. **Fraud-role surfaces — world+seed scoped**
2. **Validation artefacts & HashGate — world scoped**

#### 7.2.1 Fraud-role surfaces (seed + fingerprint)

For each fraud-role dataset (`s5_*_fraud_roles_6A`):

* Partition keys:

```text
[seed, fingerprint]
```

* Path template (schematic):

```text
data/layer3/6A/s5_party_fraud_roles_6A/
  seed={seed}/
  fingerprint={manifest_fingerprint}/
  s5_party_fraud_roles_6A.parquet

data/layer3/6A/s5_account_fraud_roles_6A/
  seed={seed}/
  fingerprint={manifest_fingerprint}/
  s5_account_fraud_roles_6A.parquet

... etc for device/ip roles
```

For merchants, you must choose one of:

* seed-independent roles:

  * partitioning `[fingerprint]`,
  * path like `.../fingerprint={mf}/s5_merchant_fraud_roles_6A.parquet`,
  * and omit `seed` as an axis; **or**

* seed-scoped roles:

  * same `[seed, fingerprint]` partitioning as others.

Whichever you choose, it becomes part of the contract and must be consistent with the dataset dictionary & PKs.

**Binding rules:**

* `seed={seed}` and `fingerprint={manifest_fingerprint}` tokens MUST match the columns inside the data.
* No additional partition keys (e.g. `parameter_hash`, `scenario_id`) may be added.
* Consumers MUST resolve locations via the catalogue and substitute these tokens; hard-coded paths are out of spec.

#### 7.2.2 Validation artefacts & HashGate (fingerprint only)

Validation & HashGate artefacts are **fingerprint-scoped**:

* Partition keys:

```text
[fingerprint]
```

* Path templates (schematic):

```text
data/layer3/6A/validation/
  fingerprint={manifest_fingerprint}/
    s5_validation_report_6A.json
    s5_issue_table_6A.parquet          # optional
    validation_bundle_index_6A.json
    _passed.flag_6A
    ... (other evidence files)
```

**Binding rules:**

* Only `fingerprint={manifest_fingerprint}` appears as a partition token here.
* These artefacts represent *the* 6A validation state for that world, independent of seed.

---

### 7.3 Primary keys, foreign keys & uniqueness

#### 7.3.1 Fraud-role surfaces

Each fraud-role table has a simple “one role per entity” law.

* **`s5_party_fraud_roles_6A`**

  * PK:

    ```text
    (manifest_fingerprint, seed, party_id)
    ```

  * Invariants:

    * `party_id` MUST exist in `s1_party_base_6A` for `(mf, seed)`.
    * Exactly one row per party in that base.
    * `fraud_role_party` must be in the party-role taxonomy.

* **`s5_account_fraud_roles_6A`**

  * PK:

    ```text
    (manifest_fingerprint, seed, account_id)
    ```

  * Invariants:

    * `account_id` MUST exist in `s2_account_base_6A` for `(mf, seed)`.
    * Exactly one row per account.
    * If `owner_party_id` is carried, it MUST match S2’s mapping.

* **`s5_merchant_fraud_roles_6A`**

  * If seed-independent:

    ```text
    PK = (manifest_fingerprint, merchant_id)
    ```

  * If seed-scoped:

    ```text
    PK = (manifest_fingerprint, seed, merchant_id)
    ```

  * Invariants:

    * `merchant_id` MUST exist in L1 merchant universe.
    * Exactly one row per merchant (per world or per world+seed per your choice).

* **`s5_device_fraud_roles_6A`**

  * PK:

    ```text
    (manifest_fingerprint, seed, device_id)
    ```

  * Invariants:

    * `device_id` MUST exist in `s4_device_base_6A` for `(mf, seed)`.
    * Exactly one row per device.

* **`s5_ip_fraud_roles_6A`**

  * PK:

    ```text
    (manifest_fingerprint, seed, ip_id)
    ```

  * Invariants:

    * `ip_id` MUST exist in `s4_ip_base_6A` for `(mf, seed)`.
    * Exactly one row per IP.

In all fraud-role tables:

* Every row MUST carry `parameter_hash` consistent with S5’s run for that `(mf, seed)`.
* There MUST be no duplicate PK rows, no missing entities, and no foreign keys that fail to resolve.

#### 7.3.2 Validation artefacts & HashGate

* **`s5_validation_report_6A`**

  * Logical key: `(manifest_fingerprint)` (one report per world).
  * The dataset representation (e.g. single JSON file) MUST have exactly one logical row/object per `manifest_fingerprint`.

* **`s5_issue_table_6A`** (if present)

  * PK is typically:

    ```text
    (manifest_fingerprint, check_id, scope_type, issue_id)
    ```

  * This is primarily diagnostic; uniqueness semantics are mostly to avoid duplicate issue rows.

* **`validation_bundle_index_6A`**

  * Logical key: `(manifest_fingerprint)`.
  * Contains the bundle index; there MUST be exactly one index per world.
  * Its `items[].path` values must be unique, sorted in canonical order.

* **`validation_passed_flag_6A`**

  * Logical key: `(manifest_fingerprint)`.
  * There MUST be at most one `_passed.flag_6A` per world.
  * It MUST carry a single `bundle_digest_sha256` that matches the bundle index’s evidence files.

---

### 7.4 Ordering: canonical vs semantic

We distinguish:

* **Canonical ordering** — ordering S5 writers must enforce to guarantee deterministic outputs and stable digests.
* **Semantic ordering** — ordering guarantees that consumers are allowed to rely on.

#### 7.4.1 Canonical writer ordering

The dataset dictionary **MUST** define an `ordering` for each S5 dataset. For example:

* `s5_party_fraud_roles_6A`:

  ```text
  ORDER BY party_id
  ```

* `s5_account_fraud_roles_6A`:

  ```text
  ORDER BY account_id
  ```

* `s5_device_fraud_roles_6A`:

  ```text
  ORDER BY device_id
  ```

* `s5_ip_fraud_roles_6A`:

  ```text
  ORDER BY ip_id
  ```

* `s5_merchant_fraud_roles_6A`:

  ```text
  ORDER BY merchant_id
  ```

For validation artefacts:

* `s5_validation_report_6A`:

  * single object; ordering inside arrays/maps (e.g. `checks[]`) MUST be deterministic (e.g. sorted by `check_id`).

* `s5_issue_table_6A`:

  ```text
  ORDER BY check_id, severity, scope_type, issue_id
  ```

* `validation_bundle_index_6A`:

  * `items` MUST be sorted lexicographically by `path` (ASCII) — this is crucial for bundle digest law.

Writers MUST honour these canonical orderings. This ensures:

* bit-stable outputs across re-runs,
* predictable HashGate digests when computing over ordered evidence.

#### 7.4.2 Semantic ordering

Consumers **must not** derive business meaning from physical row order in any S5 dataset:

* Fraud roles should be interpreted via PK/key joins, not via row order.
* Validation results should be interpreted by `check_id` / `severity` / `status`, not their sequence in a file.

Canonical ordering is for **determinism and digest integrity**, not a semantic contract.

---

### 7.5 Merge discipline & lifecycle

S5 has two distinct replace-not-append disciplines:

1. **Per `(mf, seed)` for fraud roles**
2. **Per `mf` for validation bundle & HashGate**

#### 7.5.1 Fraud-role surfaces — replace-not-append per `(mf, seed)`

For each `(manifest_fingerprint, seed)`:

* `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A` (and, if seed-scoped, `s5_merchant_fraud_roles_6A`) are **single, complete posture surfaces**:

  * each entity has exactly one row in its respective table,
  * tables cover the entire upstream base.

**Binding rules:**

* Re-running S5 for the same `(mf, seed)` with:

  * identical S0–S4 inputs,
  * identical S5 priors/taxonomies/policy,
  * identical spec version,

  MUST either:

  * produce **byte-identical** fraud-role datasets, or
  * fail with `6A.S5.OUTPUT_CONFLICT` (or equivalent) and leave existing outputs unchanged.

* S5 MUST NOT:

  * “append more roles” to a partial previous run,
  * mix multiple, incompatible role assignments for the same `(mf, seed)`.

#### 7.5.2 Validation bundle & `_passed.flag_6A` — replace-not-append per `mf`

For each `manifest_fingerprint`:

* `s5_validation_report_6A`, `s5_issue_table_6A`, `validation_bundle_index_6A` and `_passed.flag_6A` together form **the** 6A segment-level validation state for that world.

**Binding rules:**

* For a given `mf` and spec version:

  * there MUST be exactly one logical validation bundle index and at most one `_passed.flag_6A`,
  * re-running S5 under identical inputs MUST produce byte-identical bundle index, evidence files, and flag, or fail with `OUTPUT_CONFLICT`.

* S5 MUST NOT:

  * silently overwrite `_passed.flag_6A` with a different digest,
  * produce two different valid flags for the same `mf` and version.

* If S5 is updated (new spec version), a migration plan MUST dictate whether:

  * new bundles supersede old ones under a different `spec_version_6A`, or
  * worlds must be regenerated.

---

### 7.6 Consumption discipline for 6B & enterprise shell

Downstream systems must respect S5’s identity & merge discipline.

#### 7.6.1 Using fraud-role surfaces

For any `(mf, seed)`:

* 6B MUST:

  * treat fraud roles in `s5_*_fraud_roles_6A` as **authoritative static posture** for that world+seed,
  * join them by PK (`(mf, seed, id)`) to parties/accounts/merchants/devices/IPs,
  * NOT invent their own static roles that contradict S5.

* Any entity type not covered by S5 fraud roles MUST be documented; 6B should treat such entities as “unlabelled/neutral” rather than inferring roles from elsewhere.

#### 7.6.2 Using the 6A HashGate

For each `manifest_fingerprint`:

* 6B and any enterprise ingestion MUST gate on `_passed.flag_6A`:

  * locate `validation_bundle_index_6A` and `_passed.flag_6A` from the catalogue,
  * recompute `bundle_digest_sha256` from evidence files in index order,
  * compare against `_passed.flag_6A.bundle_digest_sha256`.

* If digest verification fails, or `_passed.flag_6A` is missing, the world MUST be treated as **unsealed**, and:

  * 6B MUST NOT read S1–S5 outputs for that `mf`,
  * ingestion must fail or quarantine that world.

Only when S5’s HashGate is verified do 6B and the outer system have permission, by contract, to consume 6A’s synthetic bank.

---

These identity, partition, ordering, and merge rules are **binding**.
Any implementation that violates them — e.g. appending to fraud-role tables, overwriting `_passed.flag_6A` without conflict detection, or ignoring the HashGate — is not a valid implementation of 6A.S5.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

This section defines exactly **when 6A.S5 is considered PASS**, and how **downstream components (especially 6B / enterprise ingestion)** are required to gate on S5’s outputs and HashGate.

There are two levels:

* **Seed-level**: fraud-role surfaces per `(manifest_fingerprint, seed)`.
* **World-level**: 6A validation bundle + `_passed.flag_6A` per `manifest_fingerprint`.

If any binding condition here fails, S5 is **FAIL**, and that world/seed **must not** be treated as a sealed 6A universe.

---

### 8.1 Seed-level PASS / FAIL — fraud-posture surfaces

For a given `(manifest_fingerprint, seed)`, S5’s fraud-role surfaces are **PASS** *iff* all of the following hold.

#### 8.1.1 Upstream gates & preconditions

1. **S0–S4 preconditions re-satisfied**

   * S0 gate & sealed-inputs check must still succeed (digest matches, `upstream_gates` all PASS).

   * S1–S4 run-reports for `(mf, seed)` each have:

     ```text
     status     == "PASS"
     error_code == "" or null
     ```

   * All S1–S4 bases/links resolve and validate as per their own specs.

If any of these preconditions fails at S5 time (e.g. catalogue drift), S5 MUST treat that `(mf, seed)` as **not eligible** and fail with `6A.S5.S0_S1_S2_S3_S4_GATE_FAILED`.

#### 8.1.2 Fraud-role surfaces: shape, coverage & FK invariants

For each entity type where S5 emits roles (party, account, merchant, device, IP):

2. **Tables exist & validate**

   * `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A` (and `s5_merchant_fraud_roles_6A` if seed-scoped) MUST:

     * exist for `(seed={seed}, fingerprint={mf})`,
     * validate against their schema anchors in `schemas.6A.yaml`,
     * have `columns_strict: true` enforced.

3. **Primary key & uniqueness**

   * PKs are respected:

     * `party`: `(mf, seed, party_id)`
     * `account`: `(mf, seed, account_id)`
     * `device`: `(mf, seed, device_id)`
     * `ip`: `(mf, seed, ip_id)`
     * `merchant`: either `(mf, merchant_id)` or `(mf, seed, merchant_id)` depending on your chosen axis.

   * There are **no duplicate PK rows**.

4. **Full coverage & no spurious IDs**

   * For each entity type:

     * every entity in the corresponding base (S1–S4 / L1) MUST have exactly one row in its fraud-role table,
     * no fraud-role row may reference an entity ID that does not exist in the upstream base.

   * Violations MUST be treated as assignment errors (e.g. `6A.S5.FRAUD_ROLE_ASSIGNMENT_FAILED` or `6A.S5.IDENTITY_INCONSISTENT` if you add such a code).

5. **Foreign keys**

   * Where fraud-role tables carry redundant IDs (e.g. `owner_party_id` in account roles), those FKs MUST match upstream mappings from S1–S4.

#### 8.1.3 Role values & proportion invariants

6. **Role enums & risk tiers valid**

   * For each `fraud_role_*`:

     * value MUST be a member of the corresponding fraud taxonomy,
     * no `null` or “UNKNOWN” roles unless explicitly permitted by the schema/taxonomy.

   * Any `static_risk_tier_*` fields MUST be members of their tier enums.

7. **Per-cell proportions match priors within tolerance**

   * For each entity type `E`, and each fraud cell `c` (as defined in §6/§3):

     * let `N_entities_E(c)` be number of entities in that cell,
     * let `N_realised_E(c, role)` be the count of entities assigned `role` in that cell.

   * The realised per-cell proportions:

     ```text
     p_realised_E(c, role) = N_realised_E(c, role) / N_entities_E(c)
     ```

     MUST be within configured tolerance bands around the priors `π_role|E,c(role)`, except where the validation policy explicitly marks the deviation as WARN-only.

   * Where the policy says a hard constraint applies (e.g. “at least one mule per cell if N_entities_E(c) > minimum”), those constraints MUST be met.

   * Violations of hard bounds MUST trigger errors like:

     * `6A.S5.FRAUD_ROLE_PROP_MISMATCH`,
     * `6A.S5.FRAUD_ROLE_TARGETS_INCONSISTENT`, or
     * `6A.S5.FRAUD_ROLE_ASSIGNMENT_FAILED` (depending on where detected).

8. **Global role proportions are sane**

   * Global realised proportions per entity type:

     ```text
     p_realised_E_world(role) = Σ_c N_realised_E(c, role) / Σ_c N_entities_E(c)
     ```

     MUST fall within any global bands specified in S5 priors/policy (e.g. overall mule rate between X and Y).

   * Deviations outside those bands MUST be represented as:

     * `FAIL` for the relevant checks (if designated blocking), or
     * `WARN` (if the policy allows), and reflected in the validation report.

#### 8.1.4 Structural consistency between roles and graph

9. **Cross-entity consistency rules met**

   * The validation policy may require, for example:

     * if a party is `CLEAN`, at most K of its accounts can be `MULE_ACCOUNT`,
     * if a merchant is `COLLUSIVE`, some of its neighbours (parties/accounts/devices/IPs) must exhibit suspicious structure,
     * `RISKY_DEVICE` / `HIGH_RISK_IP` roles align with graph patterns (e.g. high sharing degrees).

   * Where rules are **hard constraints**, S5 MUST enforce them or fail with:

     * `6A.S5.FRAUD_ROLE_ASSIGNMENT_FAILED`,
     * or `6A.S5.VALIDATION_CHECK_FAILED` for the specific check.

   * Where rules are labelled as WARN-level, S5 MUST reflect violations in the validation report but may still consider the world eligible for `_passed.flag_6A` (if policy allows).

If any of these seed-level conditions are not met, S5 MUST mark that `(mf, seed)` as FAIL in its run-report and treat the fraud-role surfaces as non-authoritative.

---

### 8.2 World-level PASS / FAIL — validation bundle & HashGate

For a given `manifest_fingerprint`, S5’s **world-level closure** is **PASS** *iff* both:

* all relevant seeds are acceptable, and
* the validation bundle & HashGate are structurally correct.

#### 8.2.1 Seed-level coverage for the world

10. **All required seeds processed & PASS**

* For every `seed` that the world’s orchestrator declares as part of the 6A universe:

  * There exists an S5 run-report for `(mf, seed)` with:

    ```text
    status     == "PASS"
    error_code == "" or null
    ```

  * If the policy allows some seeds to be WARN-level (e.g. partial test seeds), those rules must be defined and S5 must record them explicitly; by default, S5 should treat each target `(mf, seed)` as needing PASS to be included.

* The world-level validation report (`s5_validation_report_6A`) MUST reflect:

  * counts of seeds in PASS/WARN/FAIL,
  * whether any FAIL seeds are blocking for `_passed.flag_6A`.

#### 8.2.2 Validation report & issue table

11. **`s5_validation_report_6A` exists, valid & complete**

* `s5_validation_report_6A` exists under `validation/fingerprint={mf}/`, validates against its schema, and contains:

  * all checks defined in S5 validation policy,
  * a well-defined `overall_status ∈ {PASS, WARN, FAIL}`.

* All **required** checks MUST be present; missing checks MUST be treated as `6A.S5.VALIDATION_CHECK_FAILED`.

12. **Issue table (if implemented) is consistent**

* If `s5_issue_table_6A` is present:

  * it exists and validates against its schema,
  * all `check_id`+`scope_type`+`issue_id` combinations refer to valid checks/scopes,
  * any issues summarised in the report are explainable via this table (if that’s part of the policy).

#### 8.2.3 Validation bundle index & HashGate

13. **Bundle index is present & consistent**

* `validation_bundle_index_6A` exists, validates against `#/validation/validation_bundle_index_6A`, and:

  * its `items[]` cover exactly all evidence files considered part of the 6A bundle for this `mf`,
  * `items[].path`s are unique and sorted lexicographically,
  * `items[].sha256_hex` matches recomputed SHA-256 digests of the corresponding files.

14. **HashGate digest matches evidence**

* If and only if `s5_validation_report_6A.overall_status` meets the policy’s threshold for world PASS (e.g. `"PASS"` with no blocking failures):

  * `_passed.flag_6A` exists,
  * validates against `#/validation/passed_flag_6A`,
  * `bundle_digest_sha256` in `_passed.flag_6A` equals the SHA-256 digest computed over the concatenation of evidence-file bytes in exactly the order implied by `validation_bundle_index_6A`.

* If `overall_status` is FAIL (per policy), S5 MUST NOT emit `_passed.flag_6A` or must treat an existing flag as invalid; any mismatch between Flag vs recomputation MUST be treated as `6A.S5.VALIDATION_DIGEST_MISMATCH`.

If any of 11–14 fails, the world-level S5 state MUST be considered FAIL; `_passed.flag_6A` MUST be absent or treated as invalid, and 6B MUST treat the world as unsealed.

---

### 8.3 Gating obligations for 6B & external consumers

Downstream components (6B and enterprise ingestion) MUST respect S5’s outputs as the **final gate** for 6A.

#### 8.3.1 Seed-level gating on fraud roles

Before using fraud roles for a given `(mf, seed)`, 6B MUST:

1. Locate the latest S5 run-report for `(mf, seed)` and require:

   ```text
   status     == "PASS"
   error_code == "" or null
   ```

2. Confirm via the catalogue that:

   * the relevant `s5_*_fraud_roles_6A` tables exist for `(mf, seed)`,
   * they have valid schemas and PK coverage (no missing or extra entities).

If any of these checks fails, 6B MUST NOT:

* use S5 fraud-role surfaces for that `(mf, seed)`,
* derive campaign seeds or ground-truth labels from missing/invalid roles.

It MAY operate in a “roles unknown” mode for that seed if the design explicitly supports it, but MUST NOT treat S5 as PASS.

#### 8.3.2 World-level gating on `_passed.flag_6A`

Before ingesting **any** 6A outputs (S1–S5) for a world into downstream systems or 6B’s main flows, 6B / ingestion MUST:

1. Locate `validation_bundle_index_6A` and `_passed.flag_6A` for `manifest_fingerprint`.

2. Recompute `bundle_digest_sha256` by:

   * reading all evidence files listed in the index,
   * concatenating them in index order,
   * computing SHA-256 over the concatenated bytes.

3. Verify:

   ```text
   recomputed_digest == validation_passed_flag_6A.bundle_digest_sha256
   ```

If the flag is missing or the digest does not match, the world MUST be treated as **not sealed**:

* 6B MUST NOT treat S1–S5 outputs as part of a sealed, production-ready synthetic bank.
* Ingestion must fail or quarantine the world (e.g. only expose it for debugging).

Only if both:

* S5 run-reports for all relevant seeds are PASS, and
* `_passed.flag_6A` is present and digest-valid,

may 6B and external consumers treat the world as a sealed 6A universe.

---

### 8.4 Behaviour on failure & partial outputs

If S5 fails for a given `(mf, seed)` or for a world `mf`:

* Any partially written fraud-role surfaces or validation artefacts MUST NOT be treated as authoritative.
* S5’s run-report for that seed/world MUST have:

  * `status = "FAIL"`,
  * a `6A.S5.*` `error_code`,
  * a short `error_message`.

Under no circumstances may:

* fraud-role tables from a FAILED S5 run be silently used as if they were PASS,
* `_passed.flag_6A` from a prior run be “reused” when the new S5 run fails (this would break idempotency and trust).

The only valid states are:

* **S5 PASS (seed & world) →** 6A is sealed for that world; 6B may consume fraud roles and treat `_passed.flag_6A` as a valid gate.
* **S5 FAIL (seed or world) →** 6A is **not** sealed for that world; 6B and ingestion MUST NOT treat 6A outputs as production/trustworthy for that world, even if S1–S4 were PASS.

These acceptance criteria and gating obligations are **binding** and fully define what “6A.S5 is done and 6A is sealed” means for the rest of the system.

---

## 9. Failure modes & canonical error codes *(Binding)*

This section defines the **canonical error surface** for 6A.S5.

Every failure for a given world and/or seed **must** be mapped to exactly one of these codes in the `6A.S5.*` namespace.

All codes here are:

* **Fatal** for S5 for that `(manifest_fingerprint, [seed])`.
* **Blocking** for 6B and any enterprise ingestion of that world.

There is no “best effort” downgrade: if S5 fails, that world is **not sealed** for 6A.

---

### 9.1 Error class overview

S5 failures fall into six classes:

1. **Gate / sealed-input / S1–S4 errors**
2. **Priors & taxonomy errors (fraud-role priors, taxonomies, validation policy)**
3. **Fraud-role derivation & assignment errors**
4. **Validation / bundle / HashGate errors**
5. **RNG & accounting errors**
6. **IO / identity / internal errors**

Each class has a small, closed set of codes. Implementations must not invent ad-hoc codes.

---

### 9.2 Canonical error codes

#### 9.2.1 Gate / sealed-input / S1–S4 errors

These mean S5 cannot trust the world-level gate, the sealed input universe, or the S1–S4 modelling stack.

* `6A.S5.S0_S1_S2_S3_S4_GATE_FAILED`
  *Meaning:* At least one of the following is true:

  * S0 is missing or not PASS for this `manifest_fingerprint`, or
  * recomputed `sealed_inputs_digest_6A` does not match `s0_gate_receipt_6A.sealed_inputs_digest_6A`, or
  * one or more required upstream segments `{1A,1B,2A,2B,3A,3B,5A,5B}` have `gate_status != "PASS"` in `upstream_gates`, or
  * S1, S2, S3 **or** S4 is missing or not PASS for this `(manifest_fingerprint, seed)`.

* `6A.S5.SEALED_INPUTS_MISSING_REQUIRED`
  *Meaning:* One or more artefacts that S5 considers **required** (fraud-role priors, fraud taxonomies, validation policy) do not appear in `sealed_inputs_6A` for this `manifest_fingerprint`.

* `6A.S5.SEALED_INPUTS_SCOPE_INVALID`
  *Meaning:* A required artefact appears in `sealed_inputs_6A`, but has:

  * `status="IGNORED"`, or
  * `read_scope="METADATA_ONLY"` where S5 needs `ROW_LEVEL`.

These all mean: **“S5 cannot legally start; the world is not properly gated or sealed at 6A’s input level.”**

---

#### 9.2.2 Priors & taxonomy errors

These indicate that S5’s own priors, fraud-role taxonomies, or validation policy are not usable.

* `6A.S5.PRIOR_PACK_MISSING`
  *Meaning:* A required S5 prior/config artefact (e.g. party/account/merchant/device/IP fraud-role priors) referenced in `sealed_inputs_6A` cannot be resolved for this `(mf, ph)`.

* `6A.S5.PRIOR_PACK_INVALID`
  *Meaning:* A required prior/config artefact exists but fails validation against its `schema_ref` (wrong structure, missing required fields, invalid ranges, etc.).

* `6A.S5.PRIOR_PACK_DIGEST_MISMATCH`
  *Meaning:* SHA-256 digest computed from a prior/config artefact does not match `sha256_hex` recorded in `sealed_inputs_6A` (and/or in the registry).

* `6A.S5.TAXONOMY_MISSING_OR_INVALID`
  *Meaning:* A required fraud-role or risk-tier taxonomy is missing or invalid, e.g.:

  * missing schemas,
  * missing required enum values that S5 intends to assign,
  * inconsistent or duplicate codes.

* `6A.S5.VALIDATION_POLICY_MISSING_OR_INVALID`
  *Meaning:* The S5 validation policy / checklist artefact:

  * is missing from `sealed_inputs_6A`,
  * fails schema validation,
  * or cannot be parsed into a coherent set of checks/severities/thresholds.

These all mean: **“S5 doesn’t have a coherent definition of what roles exist, how many are expected, or what it must check.”**

---

#### 9.2.3 Fraud-role derivation & assignment errors

These indicate problems in turning priors into actual fraud roles on entities.

* `6A.S5.FRAUD_ROLE_TARGETS_INCONSISTENT`
  *Meaning:* Continuous target role counts per cell are ill-formed or inconsistent. Examples:

  * some `N_target_E(c, role)` are negative or NaN/Inf,
  * Σ_role `N_target_E(c, role)` is far from `N_entities_E(c)` beyond acceptable tolerance,
  * global target proportions implied by priors are obviously incompatible with entity counts.

* `6A.S5.FRAUD_ROLE_COUNT_INTEGERISATION_FAILED`
  *Meaning:* Converting continuous targets to integer counts `N_role_E(c, role)` cannot respect:

  * conservation (Σ_role `N_role_E(c, role) == N_entities_E(c)`), or
  * global/ per-cell min/max constraints on role counts,
  * even before assigning roles to specific entities.

* `6A.S5.FRAUD_ROLE_ASSIGNMENT_FAILED`
  *Meaning:* Assigning roles to individual entities cannot satisfy the cell-level integer counts and/or hard structural constraints, e.g.:

  * not enough candidates to assign a role in a cell, given scoring and eligibility,
  * greedy assignment or tie-breaking leads to contradictions or incomplete coverage.

* `6A.S5.FRAUD_ROLE_PROP_MISMATCH`
  *Meaning:* Realised role proportions are outside allowed tolerance bands. Examples:

  * per-cell `p_realised_E(c, role)` falls outside configured bounds around `π_role|E,c(role)`,
  * global realised proportions `p_realised_E_world(role)` violate configured global fraud-rate bands and the policy defines this as a blocking error.

* `6A.S5.IDENTITY_INCONSISTENT`
  *Meaning:* Role surfaces and upstream bases are not aligned, e.g.:

  * missing rows for some `party_id`/`account_id`/`device_id`/`ip_id`,
  * extra rows with IDs not present upstream,
  * duplicated IDs in role tables.

These all mean: **“S5 could not derive a consistent, valid fraud posture from the priors over the S1–S4 graph.”**

---

#### 9.2.4 Validation / bundle / HashGate errors

These indicate problems with the S5 validation checks and/or the 6A HashGate artefacts.

* `6A.S5.VALIDATION_CHECK_FAILED`
  *Meaning:* A check defined in the S5 validation policy failed in a way that the policy marks as **blocking** (e.g. a severe structural anomaly, or fraud proportions out of acceptable range). This refers to the logical failure of the world, not to an IO or schema error.

* `6A.S5.VALIDATION_BUNDLE_INCOMPLETE`
  *Meaning:* The validation bundle for this `manifest_fingerprint` is incomplete or inconsistent, e.g.:

  * `s5_validation_report_6A` missing,
  * required evidence files missing from disk or the index,
  * index lists a file that doesn’t exist.

* `6A.S5.VALIDATION_DIGEST_MISMATCH`
  *Meaning:* Digest consistency is broken:

  * recomputing SHA-256 per file disagree with `validation_bundle_index_6A.items[].sha256_hex`, or
  * recomputing `bundle_digest_sha256` from evidence files disagrees with `validation_passed_flag_6A.bundle_digest_sha256`.

These all mean: **“Either the world fails validation, or the validation bundle/flag is not trustworthy as a HashGate.”**

---

#### 9.2.5 RNG & accounting errors

These indicate that S5’s use of randomness for role assignment **cannot be trusted or audited**.

* `6A.S5.RNG_ACCOUNTING_MISMATCH`
  *Meaning:* Aggregate RNG metrics for S5 families:

  * `fraud_role_sampling_party`,
  * `fraud_role_sampling_account`,
  * `fraud_role_sampling_merchant`,
  * `fraud_role_sampling_device`,
  * `fraud_role_sampling_ip`,

  do not reconcile with expectations, e.g.:

  * too few/many RNG events recorded for a family,
  * overlapping or out-of-order Philox counter ranges,
  * total draws/blocks significantly outside configured budgets given entity and cell counts.

* `6A.S5.RNG_STREAM_CONFIG_INVALID`
  *Meaning:* S5’s RNG configuration is inconsistent with the Layer-3 RNG envelope, e.g.:

  * missing or mis-specified substream labels,
  * multiple logical contexts mapping to the same substream key,
  * mismatch between RNG event schemas and envelope requirements.

These errors mean: **“S5’s random role assignment cannot be reliably reproduced or audited.”**

---

#### 9.2.6 IO / identity / internal errors

These indicate IO-level issues, identity conflicts, or unexpected internal failures.

* `6A.S5.IO_READ_FAILED`
  *Meaning:* S5 failed to read a required artefact (priors, taxonomies, S0–S4 outputs, dictionary/registry, validation policy) due to IO issues (permissions, network, corruption), despite the catalogue indicating its presence.

* `6A.S5.IO_WRITE_FAILED`
  *Meaning:* S5 attempted to write one or more fraud-role surfaces or validation artefacts and the write did not complete atomically/durably.

* `6A.S5.OUTPUT_CONFLICT`
  *Meaning:* For a given `manifest_fingerprint` (and seed, for role surfaces), S5 outputs already exist and are **not** byte-identical to what S5 would produce given the current inputs and spec version. Under replace-not-append, S5 MUST NOT silently overwrite; such a run is a conflict.

* `6A.S5.INTERNAL_ERROR`
  *Meaning:* An unexpected, non-classified internal failure occurred (e.g. assertion failure, unhandled exception, programming bug) that does not map cleanly onto any other code. This should be rare and treated as an implementation bug.

These all mean: **“This S5 run is structurally invalid; its outputs (roles and/or HashGate) must not be trusted.”**

---

### 9.3 Mapping detection → error code

Implementations **must** map detected conditions to these codes deterministically. Examples:

* S0 gate fails or any S1–S4 run-report isn’t PASS → `6A.S5.S0_S1_S2_S3_S4_GATE_FAILED`.
* Fraud priors/taxonomies missing from `sealed_inputs_6A` → `6A.S5.PRIOR_PACK_MISSING` / `6A.S5.TAXONOMY_MISSING_OR_INVALID`.
* Validation policy missing/invalid → `6A.S5.VALIDATION_POLICY_MISSING_OR_INVALID`.
* Continuous role targets have NaNs/negative values or sums wildly inconsistent with entity counts → `6A.S5.FRAUD_ROLE_TARGETS_INCONSISTENT`.
* Integerisation of counts cannot satisfy conservation or min/max constraints → `6A.S5.FRAUD_ROLE_COUNT_INTEGERISATION_FAILED`.
* Assignment leaves unlabelled entities or double-labelled entities, or fails FK coverage → `6A.S5.FRAUD_ROLE_ASSIGNMENT_FAILED` / `6A.S5.IDENTITY_INCONSISTENT`.
* Realised role proportions out of tolerance bands → `6A.S5.FRAUD_ROLE_PROP_MISMATCH`.
* A blocking validation check fails (e.g. degree sanity, global fraud rate band) → `6A.S5.VALIDATION_CHECK_FAILED`.
* Validation bundle index missing files or file digests mismatched → `6A.S5.VALIDATION_BUNDLE_INCOMPLETE`.
* Recomputed bundle digest disagrees with `_passed.flag_6A` → `6A.S5.VALIDATION_DIGEST_MISMATCH`.
* RNG envelope/trace inconsistent → `6A.S5.RNG_ACCOUNTING_MISMATCH` / `6A.S5.RNG_STREAM_CONFIG_INVALID`.
* Attempting to overwrite non-identical existing S5 outputs → `6A.S5.OUTPUT_CONFLICT`.

If no specific code fits, S5 MUST use `6A.S5.INTERNAL_ERROR` and the spec should be extended later, not invent new codes ad hoc.

---

### 9.4 Run-report integration & propagation

For each S5 run (per `(mf, seed)` and per `mf` world-level closure):

* S5 run-report records MUST include:

  * `state_id = "6A.S5"`,

  * `manifest_fingerprint`, `parameter_hash`, `seed` (for seed-level surfaces),

  * `status ∈ {"PASS","FAIL"}`,

  * `error_code`:

    * empty/null for PASS,
    * one of the `6A.S5.*` codes for FAIL,

  * `error_message` (short human-readable text).

Downstream components (6B, ingestion, tooling) MUST:

* treat any `status != "PASS"` or non-empty `error_code` as a **hard gate failure** for that `(mf, seed)` or world, regardless of whether S5 outputs exist on disk,
* use `error_code` to reason about cause (e.g. modelling vs infra vs validation vs RNG),
* never interpret presence/absence of files as sufficient evidence of S5 success.

Combined with §8, these error codes and run-report semantics define the **only** valid way to propagate S5 failures and to gate on S5’s success when deciding whether a world is a sealed 6A universe.

---

## 10. Observability & run-report integration *(Binding)*

S5 is the **closure point** for 6A: it assigns static fraud roles and emits the 6A HashGate.
Its status and key metrics must be **explicitly observable and machine-checkable**, and downstream systems (especially 6B and any ingestion layer) must gate on **S5’s run-report *and* the `_passed.flag_6A`**.

This section fixes:

* what S5 must emit in its **run-report**,
* how that relates to **fraud-role tables** and the **validation bundle**,
* and how downstream components must use this information.

---

### 10.1 Seed-level run-report for 6A.S5 *(Binding)*

For **every attempted S5 run on a given `(manifest_fingerprint, seed)`**, the engine **MUST** emit exactly one run-report record with at least the following fields:

#### Identity

* `state_id = "6A.S5"`
* `manifest_fingerprint`
* `parameter_hash`
* `seed`
* `engine_version`
* `spec_version_6A` (and/or `spec_version_6A_S5` if you split by state)

#### Execution envelope

* `run_id` (execution identifier; non-semantic)
* `started_utc` (RFC 3339 with micros)
* `completed_utc` (RFC 3339 with micros)
* `duration_ms` (integer)

#### Status & error

* `status ∈ { "PASS", "FAIL" }`

* `error_code`

  * empty / null for PASS,
  * one of the `6A.S5.*` codes from §9 for FAIL.

* `error_message`

  * short, human-oriented description; non-normative.

#### Core fraud-posture metrics (binding for PASS)

For a **PASS** S5 run on `(mf, seed)`, the run-report MUST include, for each entity type where S5 emits roles:

* **Entity counts**

  * `total_parties` — `COUNT(*)` in `s1_party_base_6A`.
  * `total_accounts` — `COUNT(*)` in `s2_account_base_6A`.
  * `total_merchants` — count of merchants in the relevant L1 universe (or in S2 context).
  * `total_devices` — `COUNT(*)` in `s4_device_base_6A`.
  * `total_ips` — `COUNT(*)` in `s4_ip_base_6A`.

* **Role counts & proportions**

  Per entity type E (party/account/merchant/device/ip):

  * `roles_E_counts` — a map `fraud_role_E → count`.
  * `roles_E_proportions` — a map `fraud_role_E → proportion` (global, i.e. per-type count / total entities of type E).

  For example:

  * `roles_party_counts = { CLEAN: N_clean, MULE: N_mule, SYNTHETIC_ID: N_synth, … }`
  * `roles_party_proportions = { CLEAN: p_clean, MULE: p_mule, SYNTHETIC_ID: p_synth, … }`

* **Cell-level summary (optional but recommended)**

  * aggregated stats for key cells (e.g. per region × segment), such as:

    * `% mule parties per segment`,
    * `% collusive merchants per region`,
    * `% risky devices / IPs per `device_type`/`ip_type`.

These metrics MUST be computed from the actual fraud-role tables and S1–S4 bases; they are not informational fluff.

#### RNG metrics

S5 MUST also report RNG usage (per entity-type family) for auditing:

* `rng_party_role_events`, `rng_party_role_draws`
* `rng_account_role_events`, `rng_account_role_draws`
* `rng_merchant_role_events`, `rng_merchant_role_draws`
* `rng_device_role_events`, `rng_device_role_draws`
* `rng_ip_role_events`, `rng_ip_role_draws`

These MUST reconcile with Layer-3 RNG trace/audit logs (see §9.2.5 and §8.1.6).

---

### 10.2 PASS vs FAIL semantics in the run-report *(Binding)*

For a **PASS** seed-level S5 run `(mf, seed)`:

* `status == "PASS"`
* `error_code` is empty / null.
* All reported counts & proportions MUST be consistent with:

  * `s5_*_fraud_roles_6A` tables for that `(mf, seed)`, and
  * S1–S4 bases for entity counts.

Concretely:

* `total_parties == COUNT(*)` over `s1_party_base_6A` for `(mf, seed)`.
* `total_accounts == COUNT(*)` over `s2_account_base_6A` for `(mf, seed)`.
* `total_devices == COUNT(*)` over `s4_device_base_6A`, and so on.
* For each entity type E:

  * Σ_role `roles_E_counts[role] == total_entities_of_type_E`,
  * `roles_E_proportions[role] == roles_E_counts[role] / total_entities_of_type_E` (within rounding tolerances).

For a **FAIL** run:

* `status == "FAIL"`
* `error_code` is a non-empty `6A.S5.*` code (see §9).
* The numerical metrics MAY be omitted or set to sentinel values; they are **not** authoritative.
* Downstream components MUST treat any `status="FAIL"` or non-empty `error_code` as “S5 seed-level gate failed” for that `(mf, seed)`.

S5 MUST NOT set `status="PASS"` unless:

* all preconditions & acceptance criteria in §§2, 3, 4, 6, 7, 8 are satisfied for that `(mf, seed)`, and
* fraud-role tables are fully written and schema/PK/FK-valid.

---

### 10.3 World-level observability (validation report & HashGate) *(Binding)*

S5’s **world-level** closure for a given `manifest_fingerprint` is represented by:

* `s5_validation_report_6A` (dataset, not the run-report), and
* `_passed.flag_6A` (validation_passed_flag_6A dataset).

The **run-report for S5** MUST expose enough information for downstream components to know:

* whether S5 has:

  * built a validation bundle for this world, and
  * emitted a valid `_passed.flag_6A`.

Concretely, the S5 run-report MUST include:

* `validation_overall_status` — mirroring `s5_validation_report_6A.overall_status` for the world.
* `validation_bundle_present` — boolean indicating whether S5 wrote `validation_bundle_index_6A` for this world.
* `passed_flag_present` — boolean indicating whether `_passed.flag_6A` exists.
* optional `passed_flag_digest` — convenience echo of `_passed.flag_6A.bundle_digest_sha256` (non-binding; the binding digest is in the flag file itself).

**Binding semantics:**

* `validation_overall_status == "PASS"` AND `passed_flag_present == true`
  ⇒ S5 considers the world eligible for 6A HashGate.
* `validation_overall_status != "PASS"` OR `passed_flag_present == false`
  ⇒ the world is **not sealed** for 6A; `_passed.flag_6A` MUST NOT be trusted, even if present (e.g. from a previous spec version).

The actual gate for 6B is `_passed.flag_6A` + index/digest verification (see §8.3), but run-report must make the intended status visible.

---

### 10.4 Relationship between run-report, fraud-role tables & validation bundle *(Binding)*

For a **fully PASS** 6A.S5 state over a world `mf`:

* For every seed in the world’s seed-set:

  * the S5 run-report for `(mf, seed)` MUST be PASS,
  * fraud-role tables for `(mf, seed)` MUST be present and valid,
  * metrics in the run-report MUST match actual counts in those tables and S1–S4 bases.

* The world-level validation artefacts:

  * `s5_validation_report_6A` and optional `s5_issue_table_6A` MUST be present and schema-valid,
  * `validation_bundle_index_6A` MUST list all evidence files and have per-file digests that match recomputation,
  * `_passed.flag_6A` MUST be present and have a digest that matches recomputation over the evidence files (as per the bundle index).

The S5 run-report, fraud-role tables, and validation bundle MUST be in a **consistent state**; any mismatch is a spec violation and MUST surface as:

* `6A.S5.VALIDATION_BUNDLE_INCOMPLETE`,
* `6A.S5.VALIDATION_DIGEST_MISMATCH`,
* or another `6A.S5.*` error code.

For **FAIL**:

* S5 MUST NOT present the world as sealed in the run-report (e.g. `validation_overall_status != "PASS"`) and MUST NOT signal successful bundling & HashGate.
* If a valid `_passed.flag_6A` from a prior run is still present, 6B/ingestion MUST rely on **digest verification**, not the run-report alone, before trusting it.

---

### 10.5 Downstream consumption of S5 run-report *(Binding)*

Downstream systems (6B, ingestion, tooling) MUST use S5 run-report as part of their gates.

#### 10.5.1 Using fraud-role surfaces

Before using any S5 fraud-role tables for `(mf, seed)`, 6B MUST:

1. Read the latest S5 run-report for `(mf, seed)` and require:

   ```text
   status     == "PASS"
   error_code == "" or null
   ```

2. Confirm via the catalogue that:

   * the relevant S5 fraud-role datasets exist,
   * they validate against the schemas back-linked from the dictionary,
   * per-entity coverage is complete.

If any of these checks fails, 6B MUST:

* treat the fraud-posture surfaces as **non-authoritative** for that `(mf, seed)`,
* either refuse to run or switch to a documented “no static posture” mode if such a mode is explicitly supported.

#### 10.5.2 Gating on `_passed.flag_6A`

Before ingesting any world `mf` as a sealed 6A universe, 6B / ingestion MUST:

1. Check S5 world-level status:

   * ensure `validation_overall_status == "PASS"` in the S5 run-report,
   * ensure `passed_flag_present == true`.

2. Verify the HashGate:

   * read `validation_bundle_index_6A` and `_passed.flag_6A`,
   * recompute `bundle_digest_sha256` from evidence files as per §6.7,
   * verify it matches `_passed.flag_6A.bundle_digest_sha256`.

If either:

* seed-level S5 runs are FAIL, or
* world-level validation is FAIL, or
* digest verification fails,

then 6B MUST treat the world as **not sealed** and MUST NOT consume 6A outputs as part of a production / final synthetic bank.

---

### 10.6 Additional observability (recommended, non-semantic)

While the above is binding, it is **strongly recommended** that S5’s run-report also provide:

* Histograms or coarse distributions of:

  * per-cell mule rates (`% mule parties` per segment/region),
  * collusive merchant densities (per MCC, per region),
  * device/IP risk distributions (per device_type/ip_type),
  * simple graph-derived “fraud adjacency” metrics (e.g. how many clean parties have only mule neighbours).

* Counts of:

  * total issues per `check_id` and severity,
  * how many WARN vs FAIL checks were encountered.

These extra metrics are **non-binding** and may evolve, but they should make it easy for operators (or a dashboard) to answer:

> “For this world and seed, what fraud posture did S5 generate, and how healthy is the segment according to S5’s own checks?”

without directly querying the role surfaces and validation bundle by hand.

As long as the binding portions of this section are respected, changes to optional observability fields are allowed within S5’s backwards-compatible evolution space.

---

## 11. Performance & scalability *(Informative)*

S5 is mostly about **labeling** (one fraud role per entity) and **aggregating** (validation checks), not about generating huge new universes. It’s still O(#entities), but compared to S2–S4 it should be relatively cheap if you design it well.

This section is **non-binding**. It describes expected scale and tuning levers; it does *not* change any binding behaviour in §§1–10 & 12.

---

### 11.1 Complexity profile

For a given `(manifest_fingerprint, seed)`, define:

* `P` = number of parties: `|s1_party_base_6A|`.
* `A` = number of accounts: `|s2_account_base_6A|`.
* `M` = number of merchants (L1).
* `D` = number of devices: `|s4_device_base_6A|`.
* `I_ip` = number of IPs: `|s4_ip_base_6A|`.

Let:

* `N_party_cells`, `N_account_cells`, … = number of fraud “cells” per entity type.
* `R_E` = number of fraud-role options per entity type E (small, typically ≤ 10).

For each `(mf, seed)`:

* **Phase 1 – load gates, priors, taxonomies, policy**

  * O(N_cells + size of priors/taxonomies/policies).
  * Usually tiny compared to P/A/D/I_ip.

* **Phase 2 – feature construction & cell assignment**

  * O(P + A + M + D + I_ip) to compute features and map each entity to a cell.
  * Graph-derived features (e.g. degrees) are O(E_dev + E_ip), but those are computed once from S4.

* **Phase 3 – continuous role targets**

  * O(N_party_cells + N_account_cells + …) — per cell, per role arithmetic.
  * `N_cells` is usually in the hundreds–low thousands.

* **Phase 4 – integer role counts (if using explicit integerisation)**

  * O(N_cells × R_E) — very small compared to entity-level work.

* **Phase 5 – entity-level role assignment**

  * O(P + A + M + D + I_ip) for scoring and ranking within each cell,
  * plus O(P + A + M + D + I_ip) to actually assign roles.

* **Phase 6 – validation checks**

  * O(P + A + M + D + I_ip + N_cells) for aggregations & QA.
  * Some checks may rely on graph structure (e.g. adjacency sanity) but reuse the S4 universe; cost is similar to one or two full passes over S4’s link tables.

* **Phase 7 – bundle building & HashGate**

  * O(size_of_evidence_files) — usually small (metadata, summaries, reports), not data-plane scale.

So the total is essentially:

> **O(#entities + #edges)** = O(P + A + M + D + I_ip + E_dev + E_ip),

with constant factors smaller than S2–S4 (no new universes, mostly reading and labeling).

---

### 11.2 Expected sizes & comparative cost

Typical ranges (you’ll set actual priors yourself):

* `P ≈ 10⁶ – 10⁷`
* `A ≈ 1–5 × P`
* `D ≈ 1–4 × P`
* `I_ip ≈ 0.1–1 × D`

Entities S5 labels:

* parties: P
* accounts: A
* merchants: `M` (often ≪ P)
* devices: D
* IPs: I_ip

S5 is essentially:

* one pass to compute features per entity,
* one pass to assign roles per entity,
* plus aggregations.

Even at “bank-sized” scale (10⁶–10⁸ entities total across types), S5 should be significantly cheaper than:

* generating accounts (S2),
* generating all instruments (S3),
* generating and wiring devices & IPs (S4).

---

### 11.3 Parallelism & sharding

S5 is naturally parallelisable.

**Primary axis: seeds**

* Each `(mf, seed)` is an independent 6A universe.
* S5 runs for different seeds can be fully parallel; this is typically the main horizontal scaling axis.

**Within a seed: parallel per entity type and cell**

For a single `(mf, seed)`:

* You can run in parallel per **entity type**:

  * one worker for party roles,
  * one for account roles,
  * one for merchant roles,
  * one for device roles,
  * one for IP roles.

* Within an entity type, you can also parallelise per **cell**:

  * scoring and assignment can be done independently per cell,
  * as long as cells partition entities and the RNG substreams are derived deterministically from `(mf, seed, entity_type, cell_id, ...)`.

**Determinism requirements:**

* Whatever parallel strategy you use, you MUST preserve:

  * deterministic mapping from cells→substreams,
  * canonical ordering when you materialise outputs,
  * idempotence (same inputs → same outputs).

As long as substreams and write ordering only depend on stable keys (mf, seed, entity_type, cell_id, entity_id), parallelism won’t change semantics.

---

### 11.4 Memory & IO profile

**Memory**

The heavy part is entity-level features and role assignments:

* You *do not* need all entities in a single giant in-memory structure.

Recommended pattern:

* Process per entity type in **batches**:

  1. For a given entity type, load a chunk of its base table (e.g. parties for a subset of cells or regions).
  2. Compute features and assign each entity to a cell.
  3. Compute scores and roles within those cells.
  4. Write out that chunk’s role rows in canonical order; discard intermediate state and move on.

* If graph-derived features need neighbours:

  * precompute degrees or a small set of graph summaries from S4 link tables,
  * store these as compact per-entity scalars, not full adjacency lists.

This gives memory use roughly:

> **O(#entities in currently processed batch)** + O(N_cells × small) + small overhead for priors/policy.

**IO**

* **Reads:**

  * reading S1–S4 bases and links,
  * reading S5 priors/taxonomies/policies.

  These are sequential or partitioned reads; S4 edges can be read once to compute graph features.

* **Writes:**

  * fraud-role tables: 1 row per entity per relevant type,
  * validation report + issue table: small metadata,
  * bundle index + flag: tiny.

Overall, S5 IO is dominated by fraud-role tables themselves; everything else is cheap.

---

### 11.5 RNG cost & accounting

S5’s RNG usage is moderate:

* For each entity type E:

  * you may use RNG for:

    * tie-breaking when entities have equal scores,
    * stochastic integerisation of role counts per cell,
    * optional stochastic decisions within “soft” bands.

* Complexity:

  * ~O(#entities) draws if you use RNG frequently (but you can batch),
  * plus O(N_cells × R_E) for count-realisation draws.

To keep things efficient and auditable:

* Use **batched draws** per `(entity_type, cell)`:

  * e.g. call RNG once to draw many uniforms at once, then slice them per entity.

* Emit **coarse-grained RNG events**:

  * one `rng_event_*` per cell per operation (count realisation, tie-breaking), not per entity,
  * while still tracking total draws/blocks carefully.

The accounting requirement is that:

* S5’s RNG event counts and draw counts match what you’d expect given the number of entities and cells,
* there are no overlaps or gaps in counter ranges. That is a correctness concern, not a performance killer.

---

### 11.6 Operational tuning & “modes”

Because S5’s outputs directly shape fraud storylines, you may want different “modes” of S5 behaviour for different environments — implemented by *priors* and *validation policy*, not by hidden flags.

Examples:

* **Low-fraud dev/CI mode**

  * priors that yield very small fraud rates (e.g. 0.1% mules),
  * smaller entity counts overall (from S1–S4),
  * easier to debug behaviour and validation without flooding dev with fraud cases.

* **Realistic production mode**

  * priors capturing plausible industry fraud levels, skew across segments/regions, etc.,
  * stricter validation thresholds for deployment.

* **Stress-test / adversarial mode**

  * priors and policies that deliberately inject higher fraud rates, collusive structures, or more risky devices/IPs,
  * used to evaluate robustness of downstream systems.

All of these **must** be encoded in sealed priors/policies and so are reflected in `parameter_hash`. S5 itself remains deterministic once `ph` is fixed.

---

### 11.7 Behaviour at scale & failure regimes

In very large or extreme worlds, you might see:

* Very large fraud-role tables (millions of entities per type).
* Challenging priors (e.g. requiring many mules in low-degree cells).
* Validation policy that is “tighter” than what the graph can reasonably support.

The intended behaviour:

* If priors and graph structure are **incompatible** (e.g. you insist on a certain mule rate in an impossible cell), S5 should:

  * detect inconsistency in Phase 3 or 4, and
  * fail with `6A.S5.FRAUD_ROLE_TARGETS_INCONSISTENT` or `6A.S5.FRAUD_ROLE_ASSIGNMENT_FAILED`.

* If validation checks fail (e.g. degree sanity, improbable fraud distribution), S5 should:

  * record these as `VALIDATION_CHECK_FAILED`,
  * mark `overall_status="FAIL"` in the validation report,
  * **not** emit `_passed.flag_6A`.

Operators can then:

* inspect S5 run-reports and validation reports,
* adjust priors and/or policy,
* rerun S5 for that world.

For small/dev worlds, you can:

* scale down entity populations in S1–S4,
* use simpler priors (few roles, simple proportions),
* still exercise the full S5 pipeline (features → cells → roles → validation → bundle → HashGate) at a manageable scale.

None of these performance and scalability notes alter S5’s binding semantics. They are guidance for building an implementation that is **efficient, debuggable, and robust** as you scale up to realistic multi-million-entity synthetic banks.

---

## 12. Change control & compatibility *(Binding)*

This section fixes **how 6A.S5 is allowed to evolve** and what “compatible” means for:

* upstream segments (1A–3B, 5A–5B),
* upstream 6A states (S0–S4),
* downstream systems (6B, enterprise ingestion, QA tooling),

with respect to:

* S5’s **fraud-posture surfaces**, and
* the **6A validation bundle & `_passed.flag_6A` HashGate**.

Any change that violates these rules is a **spec violation**, even if a particular implementation “appears to work”.

---

### 12.1 Versioning model for S5

S5 participates in the same 6A versioning scheme as other states:

* `spec_version_6A` — version of the overall 6A spec (S0–S5).
* `spec_version_6A_S5` — effective version identifier for S5 (you may encode it inside `spec_version_6A` or expose separately in the run-report and/or validation report).

Schema versions:

* `schemas.6A.yaml#/s5/party_fraud_roles`
* `schemas.6A.yaml#/s5/account_fraud_roles`
* `schemas.6A.yaml#/s5/merchant_fraud_roles`
* `schemas.6A.yaml#/s5/device_fraud_roles`
* `schemas.6A.yaml#/s5/ip_fraud_roles`
* `schemas.layer3.yaml#/validation/6A/validation_report_6A`
* `schemas.layer3.yaml#/validation/6A/validation_issue_table_6A`
* `schemas.layer3.yaml#/validation/6A/validation_bundle_index_6A`
* `schemas.layer3.yaml#/validation/6A/passed_flag_6A`

Catalogue versions:

* `dataset_dictionary.layer3.6A.yaml` entries for all S5 outputs.
* `artefact_registry_6A.yaml` entries with `produced_by: 6A.S5`, including S5 priors/taxonomies/policy and validation artefacts.

**Binding requirements:**

* The S5 **run-report** MUST carry `spec_version_6A` (and/or `spec_version_6A_S5`).
* `s5_validation_report_6A` MUST record which spec version generated it.
* Downstream systems MUST be able to read those fields and reason about compatibility.

---

### 12.2 Backwards-compatible changes (allowed within a major version)

The following changes are **backwards compatible** within a given major S5 spec version, provided all binding constraints in §§1–11 still hold.

1. **Adding optional fields to S5 outputs**

   * Additional, *optional* columns in:

     * `s5_*_fraud_roles_6A` (for parties/accounts/merchants/devices/IPs),
     * `s5_issue_table_6A`,
     * `s5_validation_report_6A` (as long as existing fields are unchanged),
     * new optional evidence files included in the validation bundle and listed in the index.

   * Examples:

     * extra QA diagnostics (scores, cell IDs, debug flags),
     * more granular risk-tier fields,
     * new informative metrics in the validation report.

   * Existing consumers should be able to ignore unknown fields.

2. **Extending fraud-role & risk-tier taxonomies**

   * Adding new enum values to:

     * `fraud_role_party`, `fraud_role_account`, `fraud_role_merchant`, `fraud_role_device`, `fraud_role_ip`,
     * `static_risk_tier_*` enums,

     while preserving existing meanings.

   * Older consumers can treat unknown roles as “other/unknown” (or ignore) as long as their logic doesn’t rely on a closed set.

3. **Refining S5 priors numerically (same semantics)**

   * Adjusting numeric priors (e.g. target mule rates per segment, global fraud rate bands, device/IP risk rates) while keeping:

     * the same cell definitions,
     * the same role taxonomies,
     * the same validation policy semantics.

   * These changes affect **realised distributions** but not identity, schema, or HashGate law. They are visible in `parameter_hash` changes and run-report metrics, not in the spec shape.

4. **Adding optional validation checks and evidence**

   * Adding new checks to the validation policy with:

     * `severity` that can be tolerated (e.g. `INFO`),
     * new entries in `s5_validation_report_6A`,
     * potentially new evidence files referenced in `validation_bundle_index_6A`.

   * As long as **failure of these new checks** does not change **whether** `_passed.flag_6A` is emitted for worlds previously considered PASS, they are backward compatible.

5. **Implementation & performance optimisations**

   * Changes purely to how S5 is implemented (caching, parallelisation, streaming, file layout, job scheduling) are compatible if:

     * fraud-role surfaces are unchanged for fixed `(mf, ph, seed)`,
     * validation bundle contents and `_passed.flag_6A` are unchanged for fixed `mf/ph`,
     * RNG use and accounting remain correct and deterministic.

These changes typically correspond to **minor/patch** bumps to `spec_version_6A` / S5’s subversion and/or schema semver, and require no behavioural changes from consumers beyond “ignore unknown fields / checks”.

---

### 12.3 Soft-breaking changes (require coordination but can be staged)

Some changes are **not strictly breaking** if carefully managed, but they:

* may change which worlds/seeds pass S5, and
* require coordinated changes in downstream logic.

They MUST be accompanied by:

* a **spec/minor version bump**,
* clear documentation, and
* explicit handling in downstream components.

Examples:

1. **New mandatory fraud-role surfaces or entity types**

   * e.g. adding `s5_instrument_fraud_roles_6A` as a *required* dataset where previously no instrument roles existed, or enforcing device/IP roles where they were previously optional.

   * Requires:

     * new schemas and dictionary entries,
     * S5 to produce these surfaces,
     * 6B to be aware that new surfaces exist and possibly use them.

2. **New hard constraints in priors or validation policy**

   * Tightening constraints, for example:

     * stricter bounds on global/segment-level fraud rates,
     * new blocking checks on graph consistency (e.g. “clean party cannot have only mule neighbours” becomes a hard rule),
     * new blocking checks on role alignment between entities (party vs accounts vs devices/IPs).

   * This may cause worlds that previously PASSed to now FAIL under S5, which can be acceptable but must be understood and explicitly versioned.

3. **New roles that materially change downstream assumptions**

   * Introducing a new role (e.g. `HIGH_VALUE_TARGET` or very specific collusion roles) that 6B or business logic is expected to treat specially.

   * Backwards compatibility depends on whether old consumers can ignore these roles; if not, you must coordinate S5+6B updates.

4. **Changing how WARN vs FAIL is treated in HashGate eligibility**

   * For example, changing policy so that certain WARN-level checks now block `_passed.flag_6A`, or vice versa.

   * Even if schemas remain the same, gating semantics change, so downstream systems must consider spec version when interpreting worlds as “sealable”.

All such changes should bump **minor** `spec_version_6A_S5` and be visible in `s5_validation_report_6A` and run-reports. Consumers should check S5 version and adapt thresholds or behaviour accordingly.

---

### 12.4 Breaking changes (require major version bump)

The following are **breaking** and MUST NOT be introduced without:

* a **major** bump to `spec_version_6A` / `spec_version_6A_S5`,
* updated schemas/dictionaries/registries, and
* explicit migration guidance to all S5 consumers (6B, ingestion, QA tooling).

1. **Changing identity or partitioning**

   * Changing PK semantics, e.g.:

     * dropping `seed` or `manifest_fingerprint` from fraud-role PKs,
     * changing merchant roles from world-scoped to seed-scoped (or vice versa) without a clear migration path.

   * Changing partitioning:

     * altering `[seed, fingerprint]` to something else,
     * making HashGate artefacts seed-scoped instead of fingerprint-scoped.

2. **Changing semantics or encoding of core role fields**

   * Reinterpreting:

     * `fraud_role_party`, `fraud_role_account`, etc.,
     * risk tiers,
     * or resetting the meaning of existing enum labels.

   * Reusing old role labels for entirely different meanings (e.g. using `MULE` to mean “suspected but unconfirmed” when it previously meant “ground truth mule”).

3. **Changing the 6A HashGate digest law**

   * Modifying **how** `bundle_digest_sha256` is computed:

     * different file concatenation order,
     * inclusion/exclusion of different evidence files,
     * switching hash algorithm,

   without:

   * updating the `_passed.flag_6A` schema, and
   * versioning the digest law appropriately.

   Any change to the HashGate law MUST be reflected in schemas (`validation_bundle_index_6A`, `passed_flag_6A`), spec version, and consumer logic.

4. **Changing what “6A sealed” means**

   * For instance:

     * redefining PASS criteria so that a previously PASS world becomes FAIL **solely** due to a spec-level change (not a bug fix or prior misconfiguration),
     * or vice versa: treating previously FAILED worlds as PASS without additional checks.

   * These changes alter the contract between 6A and 6B and must be treated as a major spec change.

5. **Fundamental changes to fraud-role generation law**

   * e.g. moving from “one static role per entity” to:

     * multiple static roles allowed per entity, or
     * scenario-specific roles inside S5.

   * Changing the entire cell structure or feature basis such that compatibility with historical worlds and analysis is broken.

6. **Removing or rebranding core datasets**

   * Removing any required fraud-role table or validation artefact, or
   * renaming them while changing structure in a non-backward-compatible way.

Any such change MUST be treated as a new **major** S5 spec version; 6B and ingestion must explicitly support that version and reject worlds produced under versions they do not understand.

---

### 12.5 Compatibility obligations for downstream systems (6B, ingestion, tooling)

Downstream systems are not passive; they have obligations under this spec.

1. **Version pinning**

   * 6B and any ingestion/analysis layer MUST:

     * declare a **minimum supported S5 spec version** (or version range),
     * read S5’s version from the run-report or validation report,
     * **fail-fast** if a world’s S5 spec version is below the minimum or outside the supported band.

2. **Graceful handling of unknown roles/fields**

   * Within a supported major version:

     * 6B MUST tolerate unknown extra fields in fraud-role tables and validation reports,
     * may treat unknown fraud-role enums as “OTHER” or ignore them, unless their semantics are critical and the version suggests they should be known.

3. **No hard-coded path/shape assumptions**

   * 6B MUST:

     * resolve S5 datasets via the dictionary/registry,
     * resolve schemas via `schema_ref` → `schemas.6A.yaml` / `schemas.layer3.yaml`,
     * not assume raw file layouts beyond documented `seed={seed}` / `fingerprint={mf}` templates.

4. **No re-definition of S5 semantics**

   * Downstream specs/code MUST NOT:

     * override S5’s static fraud roles with contradictory labels,
     * treat worlds lacking `_passed.flag_6A` as “sealed” by some ad-hoc rule,
     * compute their own version of “6A sealed” independent of `_passed.flag_6A` and its validation index.

   * Derived features (e.g. “fraud adjacency score”) are allowed and encouraged, but must be clearly distinguished from S5’s roles.

---

### 12.6 Migration & co-existence strategy

When a breaking or soft-breaking S5 change is introduced:

* It MUST be reflected in `spec_version_6A` / `spec_version_6A_S5`.
* Worlds may coexist under different S5 versions in a catalogue.

Deployments may:

* route worlds to different pipelines based on S5 spec version,
* support **dual-mode** behaviour in 6B (e.g. legacy handling for S5 v1, richer handling for S5 v2),
* restrict certain analyses or features to worlds with a minimum S5 spec version.

However:

* A single world `manifest_fingerprint` MUST be internally consistent with **one** S5 spec version and **one** HashGate law.
* You MUST NOT merge fraud-role surfaces or validation bundles from different S5 versions as if they belonged to the same world.

---

### 12.7 Non-goals

This section does **not**:

* version or constrain upstream specs (1A–3B, 5A–5B) — they have their own change-control rules,
* dictate how often S5 priors/policies are updated — that is a modelling/ops choice (but every update changes `parameter_hash`),
* specify CI/CD workflows or branching strategies.

It **does** require that:

* any change in S5 that affects observable fraud roles, validation semantics, or the HashGate must be **explicitly versioned**,
* downstream must never simply “hope” compatibility — they must check S5’s version and `_passed.flag_6A` before trusting a world.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

This appendix collects shorthand and symbols used in **6A.S5**.
If anything here appears to conflict with §§1–12 or the JSON-Schemas, the binding sections and schemas win.

---

### 13.1 Identity axes & core IDs

* **`mf`**
  Shorthand for **`manifest_fingerprint`**.
  Identifies a sealed world (Layer-1 + Layer-2 + 6A input universe). All S5 work is anchored to a single `mf`.

* **`ph`**
  Shorthand for **`parameter_hash`**.
  Identifies the full parameter/prior pack in effect (including S5 fraud-role priors and validation policy). For a given `(mf, seed)`, all S5 surfaces share the same `ph`.

* **`seed`**
  RNG identity for 6A / Layer-3.
  Different seeds under the same `(mf, ph)` correspond to different realisations of the same structural world (different fraud-role assignments on the same S1–S4 graph).

* **`party_id`**
  Entity ID for a party/customer (S1). Unique per `(mf, seed)`.

* **`account_id`**
  Entity ID for an account (S2). Unique per `(mf, seed)`.

* **`merchant_id`**
  Entity ID for a merchant (L1). Typically world-scoped (per `mf`), optionally seed-scoped if you choose that model.

* **`instrument_id`**
  Entity ID for an instrument/credential (S3). Unique per `(mf, seed)`.

* **`device_id`**
  Entity ID for a device (S4). Unique per `(mf, seed)`.

* **`ip_id`**
  Entity ID for an IP / endpoint (S4). Unique per `(mf, seed)`.

---

### 13.2 Entity counts & domains

Per `(mf, seed)`:

* **`P`** — number of parties:
  `P = |s1_party_base_6A|`.

* **`A`** — number of accounts:
  `A = |s2_account_base_6A|`.

* **`M`** — number of merchants in scope (L1 / contextual subset).

* **`D`** — number of devices:
  `D = |s4_device_base_6A|`.

* **`I_ip`** — number of IPs/endpoints:
  `I_ip = |s4_ip_base_6A|`.

For each entity type **E ∈ {party, account, merchant, device, ip}**:

* **`Entities_E`** — the set of entities of type E in the world+seed (e.g. `Entities_party` = all `party_id`s in S1 base).

* **`RoleSet_E`** — allowed fraud-role values for entity type E, from the S5 fraud taxonomy. Example:

  * `RoleSet_party = {CLEAN, MULE, SYNTHETIC_ID, ORGANISER, ASSOCIATE, …}`.

---

### 13.3 Cells, priors & counts

S5 applies priors over **fraud cells** (coarse buckets of entities).

#### 13.3.1 Fraud cells

For each entity type E, S5 defines a set of cells `C_E`. A cell is typically:

```text
c_E ∈ C_E ≔ (region_id, segment_id, entity_type-specific buckets...)
```

Examples:

* For parties:

  ```text
  c_party = (region_id, segment_id, party_type, product_mix_bucket, graph_feature_bucket)
  ```

* For accounts:

  ```text
  c_account = (region_id, owner_segment_id, account_type_class, instrument_mix_bucket)
  ```

* For devices/IPs:

  ```text
  c_device = (region_id, device_type, degree_bucket, ip_profile_bucket)
  c_ip     = (region_id, ip_type, asn_class, degree_bucket)
  ```

Each entity belongs to exactly **one** cell for its type.

#### 13.3.2 Priors & continuous targets

For each entity type **E**, cell **c** and role **r ∈ RoleSet_E**:

* **`π_role|E,c(r)`**
  Prior probability that an entity of type E in cell c has role r. Typically:

  ```text
  Σ_{r ∈ RoleSet_E} π_role|E,c(r) = 1
  ```

* **`N_entities_E(c)`**
  Number of entities of type E assigned to cell c.

* **`N_target_E(c, r)`**
  Continuous target for **expected** number of E-entities with role r in cell c:

  ```text
  N_target_E(c, r) = N_entities_E(c) × π_role|E,c(r)
  ```

* **`N_target_E_world(r)`**
  Continuous target count world-wide:

  ```text
  N_target_E_world(r) = Σ_{c ∈ C_E} N_target_E(c, r)
  ```

#### 13.3.3 Integer role counts & realised assignments

* **`N_role_E(c, r)`**
  Integer number of E-entities in cell c assigned role r after integerisation (Phase 4). Subject to:

  ```text
  N_role_E(c, r) ≥ 0
  Σ_r N_role_E(c, r) == N_entities_E(c)
  ```

* **`N_realised_E_world(r)`**
  Realised integer count of E-entities with role r across the world:

  ```text
  N_realised_E_world(r) = Σ_c N_role_E(c, r)
  ```

* **`p_realised_E(c, r)`**
  Realised per-cell proportion:

  ```text
  p_realised_E(c, r) = N_role_E(c, r) / N_entities_E(c)
  ```

* **`p_realised_E_world(r)`**
  Realised global proportion:

  ```text
  p_realised_E_world(r) = N_realised_E_world(r) / Σ_c N_entities_E(c)
  ```

These are the values S5’s validation checks compare against priors/tolerances.

---

### 13.4 Fraud-role & risk-tier symbols

Per entity type E:

* **`fraud_role_party`**
  Fraud role for parties, e.g.:

  * `CLEAN`, `MULE`, `SYNTHETIC_ID`, `ORGANISER`, `ASSOCIATE`, etc.

* **`fraud_role_account`**
  Fraud role for accounts, e.g.:

  * `CLEAN_ACCOUNT`, `MULE_ACCOUNT`, `HIGH_RISK_ACCOUNT`, `DORMANT_RISKY`, etc.

* **`fraud_role_merchant`**
  Fraud role for merchants, e.g.:

  * `NORMAL`, `COLLUSIVE`, `HIGH_RISK_MCC`, `MSB`, etc.

* **`fraud_role_device`**
  Fraud role for devices, e.g.:

  * `NORMAL_DEVICE`, `RISKY_DEVICE`, `BOT_LIKE_DEVICE`, `SHARED_SUSPICIOUS_DEVICE`, etc.

* **`fraud_role_ip`**
  Fraud role for IPs/endpoints, e.g.:

  * `NORMAL_IP`, `PROXY_IP`, `DATACENTRE_IP`, `HIGH_RISK_IP`, etc.

Risk-tiers (optional, per entity type):

* **`static_risk_tier_*`**
  Enums for static risk posture, e.g.:

  * `{LOW, STANDARD, ELEVATED, HIGH}`.

These fields appear in the S5 fraud-role datasets and are constrained by S5’s taxonomies.

---

### 13.5 Validation symbols

S5’s validation layer uses:

* **`check_id`**
  Identifier of a specific validation check, e.g. `PARTY_ROLE_COVERAGE`, `MULE_RATE_PER_SEGMENT`, `DEVICE_GRAPH_SANITY`.

* **`severity`**
  Level of importance/impact for a check:

  ```text
  severity ∈ {BLOCKING, WARN, INFO}
  ```

* **`status`** (per check)

  ```text
  status ∈ {PASS, FAIL, WARN}
  ```

  Often interpreted as:

  * `PASS` — check satisfied;
  * `WARN` — out of tolerance but non-blocking;
  * `FAIL` — violation of a blocking constraint.

* **`overall_status`** (in `s5_validation_report_6A`)

  * combined status of all checks, e.g. one of `{PASS, WARN, FAIL}` determined by the validation policy (e.g. any BLOCKING FAIL → overall FAIL).

* **`issue_id`** / **`message`**
  Identifier and textual description of individual issues in `s5_issue_table_6A`.

* **`scope_type`**
  Identifies which entity (or cell) an issue pertains to; scope ∈ `{PARTY, ACCOUNT, MERCHANT, DEVICE, IP, CELL, GLOBAL}` (or similar policy-defined values).

---

### 13.6 HashGate & bundle symbols

* **`validation_bundle_6A`**
  Conceptual name for the directory `data/layer3/6A/validation/fingerprint={mf}/` containing:

  * `s5_validation_report_6A`,
  * `s5_issue_table_6A` (if present),
  * `validation_bundle_index_6A`,
  * any additional evidence files,
  * `_passed.flag_6A`.

* **`validation_bundle_index_6A`**

  * JSON/record object listing bundle members:

    * `items[]` with `path`, `sha256_hex`, `role`, and optional `schema_ref`.

* **`bundle_digest_sha256`**

  * Final HashGate digest:

    ```text
    bundle_digest_sha256
      = SHA256(concatenated_bytes_of_all_evidence_files_in_index_order)
    ```

  * Stored as a 64-character lowercase hex string in `_passed.flag_6A`.

* **`validation_passed_flag_6A` / `_passed.flag_6A`**

  * Small HashGate artefact indicating 6A is sealed for world `mf`, containing at minimum:

    * `manifest_fingerprint`,
    * `bundle_digest_sha256`.

Downstream systems recompute `bundle_digest_sha256` from `validation_bundle_index_6A` and evidence files to verify this flag.

---

### 13.7 RNG & event symbols

S5 uses the Layer-3 Philox-2x64-10 RNG via S5-specific families, e.g.:

* **`fraud_role_sampling_party`**
* **`fraud_role_sampling_account`**
* **`fraud_role_sampling_merchant`**
* **`fraud_role_sampling_device`**
* **`fraud_role_sampling_ip`**

Each RNG **event** (in a conceptual schema like `rng_event_fraud_role_*`) records:

* `counter_before`, `counter_after` — Philox counters before/after the event.
* `blocks`, `draws` — how many Philox blocks and individual draws were consumed.
* `entity_type` — which entity type the event pertains to.
* `cell_id` — which fraud cell was in use.
* Optional summary metrics (e.g. how many roles drawn, how many entities assigned in this batch).

RNG events are used for **auditability & reproducibility**, not for business semantics.

---

### 13.8 Miscellaneous shorthand & conceptual distinctions

* **“Static fraud posture” (S5)**
  Role assignments and risk tiers that are **fixed** for the life of the world and do **not** depend on individual events.

* **“Behavioural / flow labels” (6B)**
  Labels like `FLOW_IS_FRAUD`, `AUTH_IS_DECLINED`, etc., attached to individual transactions/flows.
  These are **not** part of S5; they depend on S5 posture but live in 6B.

* **“Cell”**
  Used in S5 to mean a grouping (bucket) of entities with similar characteristics; priors and validation metrics are usually defined over cells.

* **“World”**
  Shorthand for “everything under a single `manifest_fingerprint`”; it may contain multiple seeds, each with its own 6A universe.

* **“Sealed world” / “sealed 6A world”**
  A world `mf` for which:

  * S0–S4 are PASS,
  * S5 fraud-role surfaces are PASS for all relevant seeds,
  * `_passed.flag_6A` exists and its digest validates against `validation_bundle_index_6A` and evidence files.

This appendix is **informative** only; it exists to make the rest of the S5 spec easier to read and implement.

---
