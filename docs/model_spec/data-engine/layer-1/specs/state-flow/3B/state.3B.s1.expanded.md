# 3B.S1 — Virtual classification & settlement node construction

## 1. Purpose & scope *(Binding)*

1.1 **State identity and role in subsegment 3B**

1.1.1 This state, **3B.S1 — Virtual classification & settlement node construction** (“S1”), is the first **data-plane** state in Layer-1 subsegment **3B — Virtual merchants & CDN surfaces**. It executes only after **3B.S0 — Gate & environment seal** has successfully completed for the target `manifest_fingerprint`.

1.1.2 S1’s primary role is to define the **virtual-merchant universe** and to create a **single legal settlement node** for each such merchant. Concretely, S1:

* classifies merchants as **virtual** vs **non-virtual** using governed virtual-classification rules; and
* constructs exactly **one settlement node** per virtual merchant, with a stable identifier and a governed settlement coordinate and timezone.

1.1.3 S1 is a **control-plane + light data-plane** state: it writes small, merchant-level datasets that are subsequently consumed by later 3B states (edge catalogue construction, CDN alias and 3B validation), and by routing logic that needs a legal/settlement anchor for virtual merchants.

---

1.2 **High-level responsibilities**

1.2.1 S1 MUST:

* read the **sealed environment** established by S0 (`s0_gate_receipt_3B`, `sealed_inputs_3B`);
* apply the governed **virtual-classification policy** (e.g. MCC/channel rules and overrides) to the merchant universe;
* produce a **classification surface** that, for each merchant, records:

  * whether it is considered virtual for 3B, and
  * a **closed-vocabulary reason code** explaining the classification;
* construct a **settlement node** for each merchant classified as virtual, including:

  * a deterministic `settlement_site_id`,
  * a settlement latitude/longitude,
  * a settlement timezone `tzid_settlement`, and
  * provenance back to the settlement coordinate source and time-zone policy;
* write these results as 3B-owned datasets under the paths and partition laws defined in `dataset_dictionary.layer1.3B.yaml`.

1.2.2 S1 MUST ensure that its outputs are sufficient for later 3B states to:

* attach **legal / settlement semantics** to all virtual merchants (for accounting, reporting, cut-off time logic);
* build virtual routes and CDN edges without ever re-deciding “who is virtual?” or “where is the legal settlement anchor?”.

1.2.3 `virtual_settlement_3B` MUST NOT contain any rows for merchants that are not classified as virtual; non-virtual merchants have no settlement node in this dataset. For those merchants, the authoritative physical outlet and timezone information remains the upstream outputs of 1A, 1B and 2A, while `virtual_classification_3B` still records their classification outcome (`is_virtual = 0`) for completeness.

---

1.3 **Determinism and RNG-free scope**

1.3.1 S1 is **strictly RNG-free**. It MUST NOT:

* open or advance any Philox RNG stream;
* emit any RNG events (including, but not limited to, `cdn_edge_pick`);
* depend on any non-deterministic source such as wall-clock time, process ID, hostname or unordered filesystem iteration.

1.3.2 All S1 behaviour MUST be a **pure, deterministic function** of:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}` as established by the Layer-1 harness;
* the sealed artefacts enumerated by S0 in `sealed_inputs_3B` (virtual-classification rules, settlement-coord sources, geospatial and timezone assets, RNG policy packs, upstream bundles and egress datasets);
* the contents of the upstream merchant reference / attributes (MCC, channel, home country, etc.) as ingressed and validated by earlier segments.

1.3.3 Given unchanged inputs (same manifest, same sealed artefacts, same merchant universe), repeated executions of S1 for the same `{seed, parameter_hash, manifest_fingerprint}` MUST produce **bit-identical outputs** for all S1 datasets.

---

1.4 **Relationship to upstream segments and downstream 3B states**

1.4.1 S1 relies on upstream segments:

* **1A** for the merchant universe and core attributes (merchant IDs, MCCs, channels, legal countries);
* **1B** and **2A** for physical outlet and timezone information where needed for consistency checks;
* **3A** for the zone-allocation universe and `routing_universe_hash`, which may be used to enforce that virtual merchants are treated coherently alongside cross-zone merchants.

S1 does **not** re-validate upstream bundles directly; it trusts their PASS status via the gate receipt produced by S0.

1.4.2 S1’s outputs are **upstream authorities** for later 3B states:

* later 3B states MUST treat S1’s classification surface as the **sole authority** on which merchants are virtual vs non-virtual for the current manifest;
* later 3B states MUST treat `virtual_settlement` (or equivalent S1 egress) as the **sole authority** on the legal settlement node (ID, coordinate, timezone) for virtual merchants.

1.4.3 S1 MUST be written so that:

* 3B.S2 (edge catalogue construction) can consume the virtual universe and settlement nodes without needing to re-join on raw classification rules or raw coordinate sources;
* 2B’s virtual routing branch can, where needed, refer to S1 outputs for legal settlement semantics without recomputing them.

---

1.5 **Out-of-scope behaviour**

1.5.1 The following concerns are explicitly **out of scope** for S1 and are handled in other 3B states or segments:

* construction of **CDN edge catalogues** or edge coordinates (HRSL sampling, per-country edge allocation, edge IDs);
* construction of **CDN alias tables** or any per-event alias logic;
* any **per-arrival routing** decisions or the emission of `cdn_edge_pick` or other RNG events;
* any modification to physical `site_locations` or `site_timezones` for non-virtual merchants;
* the 3B segment-level validation bundle and `_passed.flag` (owned by the terminal 3B validation state).

1.5.2 S1 MUST NOT attempt to:

* infer or simulate CDN geographies;
* reinterpret upstream routing decisions;
* bundle or sign its own outputs with a HashGate flag.

Its sole mandate is to **classify merchants** and to construct a **single, legally-meaningful settlement node** per virtual merchant, under the deterministic, RNG-free and closed-world constraints defined above.

---

### Contract Card (S1) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3 for full list):**
* `s0_gate_receipt_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S0
* `sealed_inputs_3B` - scope: FINGERPRINT_SCOPED; source: 3B.S0
* `transaction_schema_merchant_ids` - scope: VERSION_SCOPED; scope_keys: [version]; sealed_inputs: required
* `mcc_channel_rules` - scope: UNPARTITIONED (sealed policy); sealed_inputs: required
* `virtual_settlement_coords` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `cdn_weights_ext_yaml` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `pelias_cached_sqlite` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `pelias_cached_bundle` - scope: UNPARTITIONED (sealed reference); sealed_inputs: required
* `outlet_catalogue` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional
* `site_locations` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional
* `site_timezones` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional
* `zone_alloc` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; sealed_inputs: optional

**Authority / ordering:**
* S1 is the sole authority on virtual classification and settlement nodes.

**Outputs:**
* `virtual_classification_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; gate emitted: none
* `virtual_settlement_3B` - scope: EGRESS_SCOPED; scope_keys: [seed, manifest_fingerprint]; gate emitted: none

**Sealing / identity:**
* External inputs MUST appear in `sealed_inputs_3B` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or policy violations -> abort; no outputs published.

## 2. Preconditions & gated inputs *(Binding)*

2.1 **Execution context & identity**

2.1.1 S1 SHALL execute only in the context of a Layer-1 run where the identity triple
`{seed, parameter_hash, manifest_fingerprint}` has already been resolved by the enclosing engine and is consistent with the Layer-1 identity and hashing policy.

2.1.2 At entry, S1 MUST be provided with:

* `seed` — the Layer-1 Philox seed for this run;
* `parameter_hash` — the governed parameter-hash for the 3B configuration;
* `manifest_fingerprint` — the enclosing manifest fingerprint.

2.1.3 S1 MUST NOT attempt to recompute or override these values. It MUST treat them as read-only identity inputs and MUST ensure that any identity it embeds in its outputs exactly matches the values recorded in `s0_gate_receipt_3B` for the same `manifest_fingerprint`.

---

2.2 **Dependence on 3B.S0 (gate & sealed inputs)**

2.2.1 S1 MUST treat **3B.S0** as a hard gate. For a given `manifest_fingerprint`, S1 MAY proceed only if both of the following artefacts exist and are schema-valid:

* `s0_gate_receipt_3B` at its canonical fingerprint-partitioned path;
* `sealed_inputs_3B` at its canonical fingerprint-partitioned path.

2.2.2 Before performing any data-plane work, S1 MUST:

* load and validate `s0_gate_receipt_3B` against `schemas.3B.yaml#/validation/s0_gate_receipt_3B`;
* load and validate `sealed_inputs_3B` against `schemas.3B.yaml#/validation/sealed_inputs_3B`;
* assert that `segment_id = "3B"` and `state_id = "S0"` in the gate receipt;
* assert that `manifest_fingerprint` in the gate receipt matches the run’s `manifest_fingerprint`;
* assert that, where present, `seed` and `parameter_hash` in the gate receipt match the values provided to S1.

2.2.3 S1 MUST also assert that, in `s0_gate_receipt_3B.upstream_gates`:

* `segment_1A.status = "PASS"`;
* `segment_1B.status = "PASS"`;
* `segment_2A.status = "PASS"`;
* `segment_3A.status = "PASS"`.

If any of these statuses is not `"PASS"`, S1 MUST treat the 3B environment as **not gated** and fail with a FATAL upstream-gate error. S1 MUST NOT attempt to re-verify upstream validation bundles directly.

2.2.4 If `s0_gate_receipt_3B` or `sealed_inputs_3B` is missing, schema-invalid, or inconsistent with the run identity, S1 MUST fail fast and MUST NOT attempt to “repair” S0 by re-sealing inputs.

---

2.3 **3B contracts: schemas, dictionary and registry**

2.3.1 Prior to using any 3B datasets, S1 MUST ensure that the following contracts are resolved and mutually compatible (either by trusting S0’s recorded `catalogue_versions` or reloading them):

* `schemas.3B.yaml`;
* `dataset_dictionary.layer1.3B.yaml`;
* `artefact_registry_3B.yaml`.

2.3.2 If S1 explicitly reloads these contracts, it MUST verify that:

* they match the versions recorded in `s0_gate_receipt_3B.catalogue_versions` (if present), **or**
* the configured compatibility rule for 3B (e.g. same MAJOR version for all three) is satisfied.

2.3.3 If S1 detects a mismatch between the loaded contracts and the versions recorded in `s0_gate_receipt_3B` (or detects a non-compatible triplet), it MUST fail with a catalogue/contract error and MUST NOT write any S1 outputs.

---

2.4 **Required control-plane inputs (from `sealed_inputs_3B`)**

2.4.1 S1 MUST treat `sealed_inputs_3B` as the **sole authority** on which artefacts are permitted as inputs for 3B. S1 MUST NOT resolve or open artefacts that are not listed in `sealed_inputs_3B` for the target `manifest_fingerprint`.

2.4.2 Specifically, S1 MUST confirm that `sealed_inputs_3B` contains rows for at least the following **mandatory 3B control-plane artefacts**, with well-formed entries (logical IDs and paths as defined in the 3B dictionary/registry):

* Virtual classification rules (e.g. `mcc_channel_rules` or equivalent);
* Virtual settlement coordinate source(s) (e.g. `virtual_settlement_coords.*`);
* Any 3B-specific overrides relevant to S1 (e.g. per-merchant allow/deny lists, brand-level mappings) if those are required by the classification/settlement design;
* Timezone/geospatial artefacts required for settlement tzid resolution, if S1 performs it directly (tz-world polygons, tzdb archive, tz overrides), or a clear indication that tz resolution will be delegated to an upstream/downstream segment that is already sealed.

2.4.3 For each such artefact, S1 MUST be able to:

* locate its row in `sealed_inputs_3B` via `logical_id` (and any other relevant columns),
* resolve the `path` and `schema_ref` (if applicable),
* open the artefact for read,
* and, if necessary, verify that its content has not drifted (by recomputing its digest and comparing to `sha256_hex`).

2.4.4 If any mandatory control-plane artefact required by S1’s algorithm is missing from `sealed_inputs_3B`, unreadable, or digest-mismatched, S1 MUST treat this as a FATAL S0/environment error and MUST NOT attempt to bypass S0 by resolving the artefact directly via the dictionary/registry.

---

2.5 **Required data-plane inputs (merchant universe & attributes)**

2.5.1 S1 MUST have access to a **merchant reference dataset** that defines the classification universe, typically:

* an ingress dataset (e.g. `merchant_ids`) or
* a derived 1A dataset containing, at minimum, the attributes needed for classification:

  * `merchant_id` (primary key),
  * `mcc` (merchant category code),
  * `channel` (or equivalent “e-commerce / card-not-present / physical” indicator),
  * `home_country_iso` or `legal_country_iso`.

The authoritative schema and path for this dataset are defined in `schemas.ingress.layer1.yaml` and/or the 1A dictionary; S1 MUST use those definitions.

2.5.2 That merchant reference dataset MAY be sealed as an upstream artefact (e.g. owned by ingress or 1A) and SHOULD appear in `sealed_inputs_3B` as a dataset artefact with `owner_segment` equal to the owning segment. S1 MUST treat this dataset as read-only.

2.5.3 S1 MUST verify, before classification, that:

* the merchant reference dataset is present and readable;
* the set of columns required for classification is present and type-correct;
* `merchant_id` is unique in the merchant reference view used for S1 (no duplicate rows per merchant).

2.5.4 If S1 performs consistency checks against upstream data (e.g. verifying that virtual merchants have zero physical outlets), it MAY also read:

* `outlet_catalogue` (1A) and/or
* `site_locations` / `site_timezones` (1B/2A),

provided these are present in `sealed_inputs_3B`. Such reads are **optional for correctness** of S1 outputs but MUST follow the partition and schema rules of their originating segments.

---

2.6 **Feature flags and configuration preconditions**

2.6.1 If the engine supports a configuration flag controlling whether the 3B virtual path is enabled (e.g. `enable_virtual_merchants`), S1 MUST:

* check the value of this flag (supplied via configuration or parameter set governed by `parameter_hash`);
* treat the flag as part of the 3B parameter set that contributed to `parameter_hash`.

2.6.2 Behaviour when the virtual path is **disabled** MUST be clearly defined in the 3B spec and implementation. Recommended pattern:

* S1 still runs as a control-plane sanity check,
* writes an empty or “all non-virtual” classification surface, and
* writes an empty `virtual_settlement` egress (no virtual merchants),

while preserving the closed-world guarantees (i.e. classification is still deterministic and documented as “no virtuals”).

2.6.3 If the configuration indicates virtual features that require additional artefacts (e.g. special handling for certain MCCs, brand-level settlement policies), S1 MUST treat those artefacts as **mandatory** for this mode and MUST fail if they are not present in `sealed_inputs_3B`.

---

2.7 **Data quality preconditions for classification and settlement**

2.7.1 For S1 to proceed, the following **minimum data quality conditions** MUST hold on its inputs:

* Every merchant in the classification universe has a non-null `merchant_id`.
* For any merchant that is candidates for virtual classification (per the rules), required fields such as `mcc`, `channel` and `home_country_iso` are present and valid according to their respective domains.
* The settlement coordinate source contains, at minimum:

  * a key that can be joined to merchants or brands (e.g. `merchant_id`, `brand_id`, or a mapping table from merchant to brand),
  * numeric `latitude` and `longitude` in the expected CRS (e.g. WGS84).

2.7.2 If S1 detects that:

* mandatory attributes for classification are missing (e.g. `mcc` null for a merchant that the rules attempt to evaluate), or
* settlement coordinates are missing for a merchant that is classified as virtual with no documented fallback,

then S1 MUST fail with a FATAL classification/settlement precondition error rather than silently dropping or misclassifying that merchant.

2.7.3 The exact failure handling (e.g. whether to allow partial classification with WARN vs require 100% coverage) MUST be defined in the S1 acceptance criteria (Section 8). As a precondition, any deviation from “full coverage” that is allowed MUST be explicitly configured (e.g. allowlisted MCCs or brand IDs) and NOT the result of silent data issues.

---

2.8 **Scope of gated inputs & downstream obligations**

2.8.1 The union of:

* the merchant reference dataset,
* the classification rules and settlement coordinate sources, and
* any optional upstream datasets S1 is allowed to read,

as listed in `sealed_inputs_3B`, SHALL define the **closed input universe** for 3B.S1.

2.8.2 S1 MUST NOT:

* read additional artefacts by resolving IDs from the dictionary/registry that are not present in `sealed_inputs_3B`;
* use ad-hoc environment variables, local files, or network resources as classification inputs.

2.8.3 Downstream 3B states (e.g. edge catalogue construction) MAY assume that, if S1 has successfully completed:

* the virtual universe and settlement nodes were derived **only** from artefacts recorded in `sealed_inputs_3B`;
* any missing or inconsistent artefacts would have caused S1 to fail.

2.8.4 If S1 detects that a required input is missing from `sealed_inputs_3B` or is inconsistent with its own spec, S1 MUST fail and MUST NOT emit partially correct outputs.

---

## 3. Inputs & authority boundaries *(Binding)*

3.1 **Control-plane inputs from 3B.S0**

3.1.1 S1 SHALL treat the following 3B.S0 artefacts as **required control-plane inputs** for the target `manifest_fingerprint`:

* `s0_gate_receipt_3B` (fingerprint-scoped JSON);
* `sealed_inputs_3B` (fingerprint-scoped table).

3.1.2 `s0_gate_receipt_3B` is the **sole authority** for:

* the identity triple `{seed, parameter_hash, manifest_fingerprint}` S1 MUST embed in its outputs;
* the status of upstream gates for 1A, 1B, 2A, 3A (S1 MUST NOT re-verify bundles directly);
* the versions of `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` that S1 is expected to be compatible with.

3.1.3 `sealed_inputs_3B` is the **sole authority** for the set of artefacts that S1 is permitted to read. S1 MUST NOT resolve or read artefacts that are not listed in `sealed_inputs_3B` for the target `manifest_fingerprint`, even if they are resolvable via other catalogues.

3.1.4 Where S1 reloads a schema/dictionary/registry or input artefact, it MUST:

* locate the corresponding row in `sealed_inputs_3B` (by `logical_id` and, if necessary, `owner_segment` / `artefact_kind`);
* treat `path` as the canonical storage location;
* treat `sha256_hex` as the canonical digest; and
* treat `schema_ref` (if non-null) as the canonical JSON-Schema anchor for validation.

---

3.2 **Merchant reference / classification universe**

3.2.1 S1 MUST consume a **merchant reference dataset** that defines the classification universe `M`. This dataset SHALL:

* be declared in the Layer-1 ingress or 1A dictionary (e.g. `merchant_ids` or an equivalent 1A-derived view);
* be listed in `sealed_inputs_3B` as a dataset artefact;
* contain at least the following fields for each merchant:

  * `merchant_id` (primary key);
  * `mcc` (merchant category code) or an equivalent categorical code used by the virtual rules;
  * `channel` (e.g. card-present vs card-not-present, or a richer channel enum) if required by the rules;
  * `home_country_iso` and/or `legal_country_iso` as defined in upstream schemas.

3.2.2 The merchant reference dataset’s **shape and semantics** remain governed by its owning segment (ingress / 1A). S1 MUST:

* treat upstream JSON-Schema / dictionary definitions as the **only authority** on its structure;
* treat the merchant reference dataset as **read-only**;
* not deduplicate, aggregate or re-key it in a way that changes its meaning.

3.2.3 From S1’s perspective, the set of merchants it classifies is:

* the set of distinct `merchant_id` values in the merchant reference dataset;
* subject to any explicit allow/deny rules in the virtual-classification policy (see §3.3).

No other dataset MAY introduce new merchants into S1’s universe.

---

3.3 **Virtual-classification policy inputs**

3.3.1 S1 MUST consume a governed **virtual-classification policy** (e.g. `mcc_channel_rules`), declared as a policy artefact in `artefact_registry_3B.yaml` and sealed in `sealed_inputs_3B`. This policy SHALL be the **sole authority** on which merchants are eligible to be classified as virtual.

3.3.2 The classification policy MAY consist of:

* MCC-based rules (e.g. “MCC in {5815, 5816} ⇒ virtual-eligible”);
* channel-based rules (e.g. “channel = ECOM ⇒ virtual-eligible; channel = POS ⇒ not virtual”);
* allow/deny lists keyed by `merchant_id`, `brand_id` or other reference keys;
* per-country constraints if required (e.g. disallow virtuals for certain legal countries).

3.3.3 The policy MUST define:

* a closed vocabulary of **classification outcomes**, at minimum:

  * `VIRTUAL`,
  * `NON_VIRTUAL`;
* a closed vocabulary of **decision reasons** (e.g. `RULE_MCC_ECOM`, `RULE_DENYLIST`, `NO_RULE_MATCH`), which S1 MUST record for each merchant.

3.3.4 S1 MUST treat the virtual-classification policy as the **only source** of classification logic. In particular, S1 MUST NOT:

* infer “virtual” status from the presence or absence of physical outlets;
* derive “virtual” from MCCs or channels in an ad-hoc way not codified in the policy;
* override explicit deny/allow rules based on upstream data.

3.3.5 If the classification policy delegates to additional artefacts (e.g. a brand mapping table, special-case override lists), those artefacts:

* MUST be present in `sealed_inputs_3B`;
* MUST have their shapes governed by `schemas.3B.yaml` or an upstream schema;
* MUST be treated as part of the **authoritative classification configuration** for S1.

---

3.4 **Settlement coordinate sources**

3.4.1 S1 MUST consume one or more **settlement coordinate datasets** that define the legal settlement location for virtual merchants. Each such dataset SHALL:

* be declared in `dataset_dictionary.layer1.3B.yaml` as a 3B input or shared ingress asset;
* be listed in `sealed_inputs_3B` with `owner_segment = "3B"` or the owning segment;
* contain, at minimum:

  * a key that can be joined to merchants or brands (e.g. `merchant_id`, `brand_id`, or a mapping table from merchant→brand);
  * `latitude` and `longitude` in WGS84 (or another CRS explicitly declared in the schema);
  * optional provenance fields (e.g. `source`, `evidence_url`, `jurisdiction`).

3.4.2 The settlement coordinate datasets are the **sole authority** for settlement lat/lon values in S1. S1 MUST NOT:

* derive settlement coordinates from physical outlets;
* synthesise settlement coordinates via RNG or heuristics;
* modify the underlying coordinate values except as required for:

  * CRS conversion, if the schema explicitly permits, or
  * deterministic epsilon-nudging used solely for robust tzid assignment (see §3.5).

3.4.3 Where a mapping is required (e.g. merchants are mapped to brands that carry settlement coords), the mapping dataset:

* MUST be declared and sealed as part of `sealed_inputs_3B`;
* MUST have its semantics and key fields governed by its own schema;
* MUST be treated as the authority for how `merchant_id` values map into settlement coordinate keys.

3.4.4 If multiple candidate settlement rows exist for a single merchant (via direct or mapped keys), S1 MUST resolve them via a deterministic, documented rule (e.g. precedence by `brand_priority`, `jurisdiction`, or a stable tie-break on primary keys). S1 MUST NOT choose arbitrarily.

---

3.5 **Timezone and geospatial inputs for settlement tzid**

3.5.1 If S1 is responsible for computing `tzid_settlement` for each virtual merchant, it MUST use only the **timezone and geospatial artefacts** sealed in `sealed_inputs_3B`, which SHALL be:

* tz-world polygons at a pinned release;
* a pinned tzdb archive / release tag;
* optional tz overrides;
* world-country polygons if needed for jurisdictional checks.

These artefacts may be owned by 2A or 1B and are shared with those segments.

3.5.2 For tzid resolution, S1 MUST reuse the **authoritative logic profile** used in 2A (e.g. point-in-polygon with ε-nudge, then override rules), or delegate tzid assignment entirely to 2A/another segment according to the global design. In either case:

* 2A’s tz semantics remain the **authority** on IANA tzid meaning;
* S1 MUST NOT introduce a bespoke, incompatible interpretation of tzids.

3.5.3 If S1 only attaches a pre-computed `tzid_settlement` from the settlement coordinate source (i.e. tzid is already present in the coordinate dataset), S1 MUST:

* validate that the provided tzid values are well-formed (IANA tzid) according to `schemas.layer1.yaml`;
* treat the settlement coord artefact as the authority on those tzids;
* optionally perform sanity checks against tz-world/tzdb (e.g. is the coordinate plausibly in that tz?), but MUST NOT silently “repair” mismatches.

---

3.6 **Optional upstream data-plane inputs for consistency checks**

3.6.1 S1 MAY read certain upstream data-plane sets **only for consistency checks**, provided they are sealed in `sealed_inputs_3B`. Examples:

* `outlet_catalogue` (1A) — to verify that merchants classified as virtual do not have physical outlets, or to enforce a policy about mixed virtual/physical merchants;
* `site_locations` (1B) — to cross-check that virtual merchants have no physical sites;
* `site_timezones` (2A) or `zone_alloc` (3A) — to ensure that legal settlement semantics for virtual merchants are coherent with existing physical / zonal semantics, if required by policy.

3.6.2 When using these inputs, S1 MUST honour the authority boundaries of their owning segments:

* S1 MUST NOT change or reinterpret the meaning of physical outlets, site coordinates, per-site tzids or zone allocations;
* S1 MUST NOT write any new rows into those datasets;
* any consistency failure MUST result in a classification failure or policy-level decision (e.g. “mixed merchant not allowed”), not a mutation of upstream data.

3.6.3 S1 MUST remain correct even if such cross-checks are disabled or omitted (e.g. in a mode where the consistency feature flag is off). In that case, S1’s inputs are restricted to the merchant reference, classification rules and settlement coordinate sources.

---

3.7 **Authority boundaries overview**

3.7.1 S1 SHALL respect the following **authority boundaries**:

* **JSON-Schemas** (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.3B.yaml`, and relevant upstream segment schemas) are the **sole authority on shapes** of datasets and policies. S1 MUST NOT relax or override them.

* The **dataset dictionaries** are the **sole authority on dataset identities and storage contracts** (paths, partition keys, writer sort). S1 MUST NOT hard-code alternative locations for inputs or outputs.

* The **artefact registries** are the **sole authority on artefact ownership, licence class and logical IDs**. S1 MUST NOT invent unregistered logical IDs or bypass registry ownership semantics.

* The **virtual-classification policy** is the **sole authority on “virtual vs non-virtual”**. S1 MUST NOT override explicit allow/deny rules or add implicit rules.

* The **settlement coordinate sources** are the **sole authority on settlement lat/lon**. S1 MAY derive tzids and jurisdictional semantics from them, but MUST NOT alter the underlying coordinate meaning.

3.7.2 If S1 detects any conflict between:

* what an artefact’s schema/dictionary/registry entry claims, and
* what S1 observes on disk (e.g. shape mismatch, missing columns, impossible coordinate values),

S1 MUST treat this as an input integrity problem (to be surfaced via error codes in §9), not as an opportunity to correct or reinterpret the artefact.

3.7.3 Any future S1 extensions that introduce new inputs (e.g. additional policy packs, external reference tables) MUST:

* register those artefacts in the dataset dictionary and/or artefact registry;
* add them to `sealed_inputs_3B`;
* define their authoritative semantics in their own schemas;
* and update this section to reflect their authority boundaries.

---

## 4. Outputs (datasets) & identity *(Binding)*

4.1 **Overview of S1 outputs**

4.1.1 S1 SHALL emit exactly two **state-owned datasets** for each successful run at a given `{seed, manifest_fingerprint}`:

* **`virtual_classification_3B`** — a per-merchant classification surface indicating whether the merchant is treated as virtual for 3B, with closed-vocabulary reason codes and provenance to the classification rules.
* **`virtual_settlement_3B`** — a per-virtual-merchant settlement-node surface, defining exactly one legal settlement node per virtual merchant (ID, coordinate, timezone, provenance).

4.1.2 Both datasets are **data-plane outputs** for 3B, but they serve different roles:

* `virtual_classification_3B` is a **control-plane data-plane hybrid**: it records classification decisions and is used by downstream 3B states and diagnostics, but is not directly used for routing.
* `virtual_settlement_3B` is a **core data-plane input** to later 3B states (edge catalogue, CDN alias) and to any routing components that need to attach legal settlement semantics to virtual merchants.

4.1.3 S1 MUST NOT emit any other persisted datasets (beyond any explicitly specified run-summary or debug surfaces in later sections). In particular, S1 MUST NOT emit alias tables, edge catalogues, or any validation bundles or PASS flags for 3B as a whole.

---

4.2 **`virtual_classification_3B` — classification surface**

4.2.1 `virtual_classification_3B` SHALL be the **authoritative classification surface** for 3B, mapping merchants in the classification universe `M` to:

* a binary classification flag (e.g. `is_virtual ∈ {0,1}` or `classification ∈ {"VIRTUAL","NON_VIRTUAL"}`), and
* a closed-vocabulary **decision reason** indicating which rule or override drove the decision.

4.2.2 At a minimum, each row in `virtual_classification_3B` MUST contain:

* `merchant_id` (primary key within this dataset);
* a classification field (`is_virtual` or equivalent) as per §5;
* `decision_reason` drawn from a closed enum defined in `schemas.3B.yaml`;
* optional additional provenance fields (e.g. `rule_id`, `rule_version`, `source_policy_id`) as defined in §5.

4.2.3 The rowset of `virtual_classification_3B` MUST:

* include exactly one row for each merchant in the classification universe `M` (no more, no less), unless the 3B specification explicitly permits a “virtual-only” view (in which case the semantics MUST be documented and the schema MUST reflect it);
* be **RNG-free** and reproducible given the same inputs.

4.2.4 Partitioning and path:

* `virtual_classification_3B` MUST be partitioned by `{seed, fingerprint}` and written under a path of the form:
  `data/layer1/3B/virtual_classification/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...`
* The exact `path_template`, `partition_keys` and `writer_sort` are binding and SHALL be defined in `dataset_dictionary.layer1.3B.yaml` and referenced in §5.

4.2.5 Downstream obligations:

* All later 3B states MUST treat `virtual_classification_3B` as the **sole authority** on which merchants are virtual vs non-virtual for the current `manifest_fingerprint`.
* They MUST NOT recompute or override the classification from raw MCC/channel rules or other inputs.

---

4.3 **`virtual_settlement_3B` — settlement node egress**

4.3.1 `virtual_settlement_3B` SHALL be the **authoritative settlement-node dataset** for 3B, containing exactly one record per merchant classified as virtual in `virtual_classification_3B` (or per brand/aggregate key, if the spec uses a higher-level identity; see §5).

4.3.2 At a minimum, each row in `virtual_settlement_3B` MUST contain:

* a key that unambiguously identifies the virtual merchant in 3B (e.g. `merchant_id`, or `merchant_key` if composite);
* a deterministic settlement-node identifier (e.g. `settlement_site_id`), derived via a documented one-way function (e.g. `SHA1(merchant_id, "SETTLEMENT")`);
* settlement coordinates `settlement_latitude` and `settlement_longitude` (WGS84 or another clearly declared CRS);
* a settlement timezone `tzid_settlement` (either computed by S1 or sourced from the coordinate artefact), conforming to `iana_tzid` from `schemas.layer1.yaml`;
* provenance fields linking back to:

  * the settlement coordinate source, and
  * the tz resolution policy (if applied).

4.3.3 The rowset of `virtual_settlement_3B` MUST satisfy:

* there is exactly one row per merchant that is classified as virtual (`is_virtual = 1`) in `virtual_classification_3B` (unless the spec explicitly defines a brand-level mapping);
* there are no rows for merchants that are not classified as virtual;
* the key used for joins with other datasets (e.g. `merchant_id`) is consistent with the key used in `virtual_classification_3B` and upstream segments.

4.3.4 Partitioning and path:

* `virtual_settlement_3B` MUST be partitioned by `{seed, fingerprint}` and written under a path of the form:
  `data/layer1/3B/virtual_settlement/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...`
* The exact `path_template`, `partition_keys` and `writer_sort` SHALL be defined in `dataset_dictionary.layer1.3B.yaml` and referenced in §5.

4.3.5 Downstream obligations:

* Downstream 3B states responsible for edge catalogue construction, CDN alias and routing MUST treat `virtual_settlement_3B` as the **only source** of legal settlement nodes for virtual merchants; they MUST NOT create alternative settlement nodes or modify these coordinates.
* 2B or other routing components that need a settlement anchor for virtual merchants MUST rely on `virtual_settlement_3B` (directly or via a downstream 3B projection) rather than deriving settlement semantics elsewhere.

---

4.4 **Identity fields, metadata & path↔embed equality**

4.4.1 Both `virtual_classification_3B` and `virtual_settlement_3B` are **run-scoped** datasets. Their identity is defined by:

* the enclosing triple `{seed, parameter_hash, manifest_fingerprint}`, and
* the fact that they are produced by 3B.S1 for that triple.

4.4.2 On disk, identity SHALL be expressed primarily via **partition keys** and path:

* `seed={seed}` and `fingerprint={manifest_fingerprint}` in the directory path;
* a single set of files per `{seed, fingerprint}` for each dataset.

4.4.3 The schemas for these datasets MAY include explicit `seed` and/or `manifest_fingerprint` columns as identity echoes. If present:

* their values MUST exactly match the partition values;
* the 3B validation state MUST include a path↔embed equality check as part of 3B’s segment-level validation (not S1).

4.4.4 No S1 output MAY include `parameter_hash` as a partition key. If `parameter_hash` appears as a column in any S1 dataset, it MUST:

* match the value recorded in `s0_gate_receipt_3B`;
* be treated as informative identity only;
* never be used to partition or shard S1 outputs.

---

4.5 **Relationship to 3B validation bundle & segment PASS**

4.5.1 S1 does **not** produce a 3B segment-level validation bundle or `_passed.flag`. Those artefacts are owned by the terminal 3B validation state.

4.5.2 However, `virtual_classification_3B` and `virtual_settlement_3B` are expected to be **members** of the 3B validation bundle. Therefore:

* their dataset IDs, `path_template`, `partition_keys` and `schema_ref` MUST be stable over time, subject to the change-control rules in §12;
* their contents MUST be reproducible from the sealed inputs for the run, so that the 3B validation state can compute stable `sha256_hex` digests for inclusion in the bundle index.

4.5.3 S1 MAY compute per-dataset digests (e.g. `virtual_classification_sha256`, `virtual_settlement_sha256`) and attach them to a run-summary surface or run-report record, but such digests are **informative**; the authoritative digests for HashGate purposes are those computed by the 3B validation state when building the segment-level validation bundle.

---

4.6 **Immutability & idempotence of S1 outputs**

4.6.1 For a fixed `{seed, parameter_hash, manifest_fingerprint}`, S1 outputs are **logically immutable**:

* Once `virtual_classification_3B` and `virtual_settlement_3B` have been successfully written, re-running S1 with the same inputs MUST either:

  * confirm that the existing dataset contents are bit-identical to the newly computed results, and treat the run as a no-op; or
  * detect a conflict (e.g. environment drift under stable fingerprint) and fail, without overwriting the existing data.

4.6.2 No other state MAY mutate `virtual_classification_3B` or `virtual_settlement_3B` in place. Any derived views or projections MUST be written to separate datasets with their own IDs and contracts.

4.6.3 Downstream 3B states MUST treat S1 outputs as **read-only** and MUST NOT append, delete or update rows in these datasets. Any additional per-state annotations (e.g. flags about edge coverage or validation results) MUST be stored in separate datasets keyed to S1 outputs via their primary keys.

---

4.7 **Visibility & consumption across segments**

4.7.1 Within Layer-1, `virtual_classification_3B` and `virtual_settlement_3B` are **owned by segment 3B** but MAY be consumed by other segments or layers (e.g. routing components) if explicitly authorised in their dictionaries. In such cases:

* those consumers MUST declare their dependency in their own dictionaries/registries;
* those consumers MUST honour the identity and authority rules defined here (no reclassification, no new settlement nodes).

4.7.2 Any cross-segment consumption of S1 outputs MUST still be guarded by:

* 3B’s segment-level PASS flag (once implemented), and
* the upstream S0/S1 gating and sealed-inputs discipline.

4.7.3 If, in a future revision, 3B introduces additional S1 outputs (e.g. a diagnostic dataset of merchants with ambiguous rules), those datasets MUST:

* be given explicit dataset IDs, schemas and dictionary entries;
* be clearly documented as **informative** or **diagnostic**;
* not alter the binding semantics of `virtual_classification_3B` and `virtual_settlement_3B` specified in this section.

---

## 5. Dataset shapes, schema anchors & catalogue links *(Binding)*

5.1 **`virtual_classification_3B` — dataset contract**

5.1.1 The dataset **`virtual_classification_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with at least:

* `dataset_id: virtual_classification_3B`
* `schema_ref: schemas.3B.yaml#/plan/virtual_classification_3B`
* `path_template: data/layer1/3B/virtual_classification/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
* `partition_keys: ["seed","fingerprint"]`
* `writer_sort: ["merchant_id"]` (or a stricter sort if required; see 5.1.4)

5.1.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference the same `dataset_id` and `schema_ref`,
* declare `owner_segment: "3B"`,
* set `type: "dataset"`,
* include a stable `manifest_key` (e.g. `"mlr.3B.virtual_classification_3B"`),
* and state downstream consumers explicitly (later 3B states and any other segments that read the classification surface).

5.1.3 `schemas.3B.yaml#/plan/virtual_classification_3B` MUST define `virtual_classification_3B` as a table-shaped dataset with **one row per merchant** in the classification universe. Required columns:

* `merchant_id`

  * type: as defined in ingress / 1A schemas (e.g. `schemas.ingress.layer1.yaml#/merchant/merchant_id`),
  * semantics: primary key of the row.

* `is_virtual` (or `classification`)

  * either:

    * `is_virtual`: integer or boolean (e.g. `{0,1}`), **or**
    * `classification`: enum `{"VIRTUAL","NON_VIRTUAL"}`
  * in either case, the schema MUST make the mapping between the two unambiguous.

* `decision_reason`

  * enum with a **closed vocabulary** of reasons, e.g.:

    * `RULE_MCC_POSITIVE`, `RULE_CHANNEL_POSITIVE`,
    * `RULE_DENYLIST`, `RULE_ALLOWLIST`,
    * `NO_RULE_MATCH`, `CONFLICTING_RULES`, etc.
  * the vocabulary MUST be defined in `schemas.3B.yaml`, not in code.

* `source_policy_id`

  * string, logical ID of the classification policy pack (e.g. `"mlr.3B.mcc_channel_rules_v1"`),
  * MUST be consistent across all rows for a given `{seed,fingerprint}`.

* `source_policy_version`

  * string or structured semver (e.g. `"1.2.0"`), matching the version recorded in the artefact registry.

5.1.4 Optional but recommended columns (MUST be explicitly marked `optional` in schema):

* `rule_id` / `rule_name` — identifier of the specific rule that fired, if the policy exposes rule-level IDs;
* `aux_flags` — optional bitfield or small struct for additional classification flags (e.g. “mixed merchant”, “requires manual review”), if the design uses them;
* `created_utc` — RFC3339 timestamp for when S1 wrote the dataset (informative);
* `seed`, `manifest_fingerprint`, `parameter_hash` — identity echoes (must match path and S0 receipt if present).

5.1.5 Structural constraints (expressed via schema or acceptance criteria):

* `merchant_id` MUST be unique within a given `{seed,fingerprint}` partition.
* `is_virtual` / `classification` MUST be non-null for all rows.
* `decision_reason` MUST be non-null and one of the enumerated values.
* `source_policy_id` and `source_policy_version` MUST be constant (or piecewise constant in a documented way) within each `{seed,fingerprint}` partition.

---

5.2 **`virtual_settlement_3B` — dataset contract**

5.2.1 The dataset **`virtual_settlement_3B`** MUST be registered in `dataset_dictionary.layer1.3B.yaml` with at least:

* `dataset_id: virtual_settlement_3B`
* `schema_ref: schemas.3B.yaml#/plan/virtual_settlement_3B`
* `path_template: data/layer1/3B/virtual_settlement/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
* `partition_keys: ["seed","fingerprint"]`
* `writer_sort: ["merchant_id"]` (or `[merchant_key,…]` if a composite key is used)

5.2.2 The corresponding entry in `artefact_registry_3B.yaml` MUST:

* reference the same `dataset_id` / `schema_ref`,
* declare `owner_segment: "3B"`,
* set `type: "dataset"`,
* specify a stable `manifest_key` (e.g. `"mlr.3B.virtual_settlement_3B"`),
* and record any cross-segment consumers (e.g. routing components).

5.2.3 `schemas.3B.yaml#/plan/virtual_settlement_3B` MUST define `virtual_settlement_3B` as a table-shaped dataset with **one row per virtual merchant** (or per brand key if the design is brand-level). Required columns:

* `merchant_id` (or `virtual_entity_id` / `merchant_key`)

  * key that unambiguously ties the row back to `virtual_classification_3B` and the merchant universe.
  * MUST be consistent with the key choices documented in the S1 spec.

* `settlement_site_id`

  * string, deterministic identifier of the settlement node,
  * MUST be generated via a documented, deterministic function of the key (e.g. `settlement_site_id = SHA1(merchant_id || ":SETTLEMENT")`),
  * MUST be unique within `{seed,fingerprint}` and, preferably, globally unique within Layer-1.

* `settlement_latitude_deg`

  * numeric, WGS84 latitude in degrees (e.g. `[-90,90]`),
  * derived from the settlement coordinate artefact or a deterministic CRS transform.

* `settlement_longitude_deg`

  * numeric, WGS84 longitude in degrees (e.g. `(-180,180]`),
  * derived similarly to latitude.

* `tzid_settlement`

  * string, IANA timezone ID for the settlement node,
  * MUST conform to `schemas.layer1.yaml#/time/iana_tzid`.

* `coord_source_id`

  * string, logical ID of the settlement coordinate artefact used (e.g. `"mlr.3B.virtual_settlement_coords_v1"`).

* `coord_source_version`

  * string / semver, version recorded in the artefact registry.

* `tz_source`

  * enum describing how `tzid_settlement` was obtained, e.g. `{"POLYGON","OVERRIDE","INGESTED"}`.

5.2.4 Optional but recommended columns (MUST be schema-optional):

* `jurisdiction_code` — code for the legal jurisdiction of settlement, if maintained separately from tzid;
* `evidence_url` or `evidence_ref` — link or ID pointing to documentary evidence for this settlement location, if present in the upstream coordinate source;
* `created_utc` — RFC3339 timestamp;
* `seed`, `manifest_fingerprint`, `parameter_hash` — identity echoes (must equal path/receipt if present).

5.2.5 Structural constraints:

* For each row in `virtual_settlement_3B`, there MUST exist exactly one row in `virtual_classification_3B` with the same key and `is_virtual = 1` / `classification = "VIRTUAL"`.
* There MUST be no rows in `virtual_settlement_3B` for merchants that are not virtual.
* `(merchant_id, settlement_site_id)` MUST be unique within a `{seed,fingerprint}` partition.
* `(settlement_latitude_deg, settlement_longitude_deg)` MUST lie within valid ranges, and `tzid_settlement` MUST be non-null.

---

5.3 **Schema anchors for S1 inputs**

5.3.1 All **input datasets** S1 reads MUST be anchored in the appropriate segment schemas and dictionaries. At minimum:

* Merchant reference:

  * `schema_ref`: something like `schemas.ingress.layer1.yaml#/merchant/merchant_reference` or `schemas.1A.yaml#/ingress/merchant_reference`,
  * `dataset_dictionary` entry in the owning segment (ingress / 1A).

* Virtual-classification policy:

  * `schema_ref`: `schemas.3B.yaml#/policy/virtual_classification_rules` (or equivalent),
  * path and logical ID declared in `artefact_registry_3B.yaml`.

* Settlement coordinate dataset(s):

  * `schema_ref`: `schemas.3B.yaml#/ingress/virtual_settlement_coords` (or equivalent),
  * dataset entry in `dataset_dictionary.layer1.3B.yaml` or in the ingress dictionary if shared.

* Optional mapping tables (merchant→brand):

  * `schema_ref`: `schemas.3B.yaml#/ingress/merchant_brand_mapping` (or equivalent).

5.3.2 For timezone / geospatial inputs (if S1 resolves `tzid_settlement`):

* tz-world polygons: `schemas.ingress.layer1.yaml#/geo/tz_world_*` (as per 2A/1B specs);
* tzdb archive: `schemas.ingress.layer1.yaml#/tzdb/archive` or a similar anchor used by 2A;
* any tz override packs: `schemas.2A.yaml#/policy/tz_override` or a 3B-local anchor if 3B owns overrides for settlement.

S1 MUST refer to these anchors rather than inventing its own schema definitions.

---

5.4 **Catalogue links & discoverability**

5.4.1 Every dataset and artefact that S1 reads or writes MUST:

* have a corresponding entry in a dataset dictionary or artefact registry, and
* be discoverable by logical ID from those catalogues, not by hard-coded paths.

5.4.2 In particular:

* `virtual_classification_3B` and `virtual_settlement_3B` MUST appear in both `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml`;
* the merchant reference dataset MUST appear in its owning segment’s dictionary and SHOULD appear in `sealed_inputs_3B` with a consistent `logical_id`;
* classification policies and settlement coordinate artefacts MUST be registered in `artefact_registry_3B.yaml` with stable logical IDs and path templates.

5.4.3 S1 MUST obtain:

* dataset paths and partition keys from the dataset dictionary, and
* ownership / licence and any descriptive metadata from the artefact registry.

It MUST NOT construct paths by string concatenation outside of the dictionary templates.

5.4.4 Any change to `path_template`, `partition_keys` or `schema_ref` of S1 outputs in the dictionary is a change to the 3B.S1 contract and MUST follow the change-control rules in §12.

---

5.5 **Key, sort and join discipline**

5.5.1 The schemas for `virtual_classification_3B` and `virtual_settlement_3B` MUST identify which fields form the **primary key** and which form the **natural join keys** for downstream states:

* `virtual_classification_3B`: PK and join key = `merchant_id` (or `merchant_key` if composite);
* `virtual_settlement_3B`: PK = `merchant_id` (or `merchant_key`) + `settlement_site_id`; join key to classification = `merchant_id` / `merchant_key`.

5.5.2 `writer_sort` for both datasets SHOULD reflect the primary join keys, for example:

* `virtual_classification_3B`: `["merchant_id"]`
* `virtual_settlement_3B`: `["merchant_id"]` (and optionally `["merchant_id","settlement_site_id"]` if needed)

5.5.3 These sort orders MUST be respected by S1 when writing the datasets; any downstream validation or routing component that assumes sorted reads MUST use these declared sort orders.

5.5.4 Any downstream dataset that joins to S1 outputs (e.g. edge catalogues) MUST use the keys and schema anchors defined here; S1 MUST not support ad-hoc join keys that are not reflected in schemas and dictionaries.

---

5.6 **Binding vs informative elements**

5.6.1 The content of this section is **binding** with respect to:

* the existence and names of `virtual_classification_3B` and `virtual_settlement_3B`;
* their `schema_ref`, `path_template`, `partition_keys` and `writer_sort` entries in the dictionary;
* their required columns and key constraints;
* the requirement that classification and settlement datasets are discoverable via the catalogues.

5.6.2 Optional columns and non-structural metadata described above (e.g. `created_utc`, `evidence_url`) are binding **only** in the sense that, if present, they MUST conform to their declared schemas and MUST NOT change the semantics of required fields.

5.6.3 Where any discrepancy arises between this section and the JSON-Schema definitions or dataset dictionary entries once those are finalised, the **schemas and dictionary are authoritative**, and this section MUST be updated to match them in the next non-editorial revision.

---

## 6. Deterministic algorithm (RNG-free) *(Binding)*

6.1 **Algorithm phases (informative overview)**

6.1.1 S1 SHALL implement a **single deterministic, RNG-free algorithm** comprising the following logical phases:

* **Phase A — Environment & contracts**
  Load and validate S0 artefacts (`s0_gate_receipt_3B`, `sealed_inputs_3B`), resolve required schemas, dictionaries, registries and artefact paths.

* **Phase B — Merchant universe & context**
  Load the merchant reference dataset and construct the classification universe `M` with the attributes required by the classification policy.

* **Phase C — Virtual classification**
  Evaluate the governed classification rules for each merchant, producing a per-merchant classification (`virtual` / `non-virtual`) and a closed-vocabulary decision reason.

* **Phase D — Settlement node resolution**
  For each merchant classified as virtual, resolve a unique settlement coordinate and timezone, and construct a deterministic `settlement_site_id`.

* **Phase E — Output materialisation**
  Materialise `virtual_classification_3B` and `virtual_settlement_3B` under the declared paths and partition keys, with deterministic ordering and idempotent semantics.

6.1.2 No phase MAY open or advance an RNG stream, emit RNG events, or depend on non-deterministic sources such as wall-clock time (except as explicitly allowed for `created_utc` / logging), process IDs, hostnames, or unsorted directory listings.

---

6.2 **Phase A — Environment & contracts**

6.2.1 S1 MUST:

1. Load `s0_gate_receipt_3B` and `sealed_inputs_3B` for `manifest_fingerprint` and validate them against their schemas.
2. Verify that:

   * `segment_id = "3B"` and `state_id = "S0"` in the gate receipt;
   * `seed`, `parameter_hash`, `manifest_fingerprint` (if present) match the run’s identity;
   * all upstream `upstream_gates.segment_{1A,1B,2A,3A}.status = "PASS"`.
3. Load (or trust via `catalogue_versions`) `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` and assert that they form a compatible triplet.

6.2.2 For each artefact S1 expects to use (merchant reference, classification policy, settlement coords, optional mapping tables, tz/geospatial inputs), S1 MUST:

* locate its row in `sealed_inputs_3B` by `logical_id` (and where necessary `owner_segment` / `artefact_kind`);
* take `path` as the canonical location and `schema_ref` as the canonical schema anchor;
* verify that the artefact is readable;
* optionally recompute a digest and compare with `sha256_hex` if S1 is configured to harden against mid-run changes.

Any failure here MUST result in a FATAL error as per §9.

---

6.3 **Phase B — Merchant universe & context**

6.3.1 S1 MUST load the **merchant reference dataset** specified in §3.2 via the dataset dictionary and the location recorded in `sealed_inputs_3B`. It MUST perform a **schema-only** validation to ensure presence and types of at least:

* `merchant_id`,
* `mcc` (or equivalent rule key),
* `channel` (if referenced by rules),
* `home_country_iso` / `legal_country_iso` (if referenced by rules).

6.3.2 S1 MUST construct the classification universe `M` as the set of distinct `merchant_id` values in the merchant reference dataset. If duplicates exist:

* S1 MUST treat this as a data-quality error;
* either reject the run (FATAL) or apply a documented deduplication rule **only if** such a rule is explicitly defined in the 3B spec (e.g. “first occurrence wins in sorted input”).
  The default expectation is **no duplicates**.

6.3.3 For each `merchant_id ∈ M`, S1 MUST build a **classification context** structure `ctx(m)` containing:

* the raw fields from the merchant reference needed by the rules (`mcc`, `channel`, `home_country_iso`, `legal_country_iso`, etc.);
* any additional derived fields required by the policy (e.g. normalised MCC groups, channel buckets), computed via deterministic, side-effect-free functions.

6.3.4 S1 MUST NOT read any further upstream data (e.g. outlet counts, site locations) during Phase B, except where explicitly required to construct `ctx(m)` as defined by the classification policy. In such cases, the dependencies MUST be declared in the 3B contracts and `sealed_inputs_3B`.

---

6.4 **Phase C — Virtual classification**

6.4.1 S1 MUST load the **virtual-classification policy artefact** (e.g. `mcc_channel_rules`) as a structured object whose schema is defined in `schemas.3B.yaml#/policy/virtual_classification_rules`.

6.4.2 The policy MUST define an ordered list of rules and/or override tables. At minimum, S1 MUST support the following deterministic precedence:

1. **Hard deny / allow overrides**

   * Merchant-keyed and/or brand-keyed allow/deny lists, if present.
   * A deny override MUST force `classification = NON_VIRTUAL` regardless of other rules.
   * An allow override MUST force `classification = VIRTUAL` regardless of other rules, subject to any explicitly documented global hard constraints (e.g. “merchant has no physical outlets” if that is part of the design).

2. **Rule ladder** (e.g. MCC/Channel/geo rules)

   * Each rule has at least: `rule_id`, `rule_priority`, a predicate over `ctx(m)`, and an action (`SET_VIRTUAL`, `SET_NON_VIRTUAL`, or no-op).
   * Rules are evaluated in **strict priority order**: descending `rule_priority`, then ascending `rule_id` as ASCII-lex tie-breaker.
   * The first rule whose predicate is true and whose action is not a no-op MUST determine the classification, unless an explicit policy field says “continue evaluation” (in which case evaluation rules MUST be documented).

3. **Default**

   * If no rule fires and no override applies, `classification = NON_VIRTUAL` with `decision_reason = "NO_RULE_MATCH"` (or equivalent enum).

6.4.3 For each `merchant_id ∈ M` in ascending order of `merchant_id`, S1 MUST:

1. Construct `ctx(m)` as per §6.3.3.
2. Check hard overrides (if present) and record the applicable override (if any).
3. If no hard override, evaluate rules according to 6.4.2.
4. Choose a **single** outcome `classification(m) ∈ {VIRTUAL, NON_VIRTUAL}` and a **single** `decision_reason(m)` from the policy’s closed vocabulary.
5. If conflicting instructions arise (e.g. multiple hard overrides for the same merchant, or contradictory rules where the policy does not define precedence), S1 MUST fail with a FATAL classification error rather than resolve conflicts arbitrarily.

6.4.4 S1 MUST populate `virtual_classification_3B` with exactly one row per `merchant_id ∈ M`, using:

* `merchant_id`;
* `is_virtual` or `classification` derived from `classification(m)`;
* `decision_reason = decision_reason(m)`;
* `source_policy_id` and `source_policy_version` from the policy artefact metadata;
* optional rule-level provenance (`rule_id`, `rule_group`, etc.) if exposed by the policy.

6.4.5 S1 MUST NOT adjust or “fix up” the classification based on downstream considerations (e.g. missing settlement coordinates). Any inconsistency between classification and settlement availability MUST be handled in Phase D or by failing the run, as defined in §8 and §9.

---

6.5 **Phase D — Settlement node resolution**

6.5.1 S1 MUST define the set of virtual merchants:

* `V = { m ∈ M | classification(m) = VIRTUAL }`.

If the configuration disables virtuals (e.g. `enable_virtual_merchants = false`), S1 MUST document whether:

* `V = ∅` by design (preferred), or
* a separate default classification is used.

6.5.2 S1 MUST load the **settlement coordinate dataset(s)** and any mapping tables (merchant→brand or similar) from the artefacts listed in `sealed_inputs_3B`.

6.5.3 For each `m ∈ V`, S1 MUST determine a **settlement key** `k(m)` used to join to settlement coordinates:

* If settlement coordinates are keyed directly by `merchant_id`, then `k(m) = merchant_id`.
* If they are keyed by `brand_id` or another aggregate key, S1 MUST obtain that key deterministically from a mapping dataset (also sealed via `sealed_inputs_3B`), using documented join semantics and handling for one-to-many / many-to-one mappings.

6.5.4 Once `k(m)` is known, S1 MUST find candidate settlement coordinate rows:

* Let `C(m) = { rows in settlement_coord | key(row) = k(m) }`.
* If `C(m)` is empty, S1 MUST treat this as a settlement-coverage failure (FATAL unless an explicit policy allows exception handling and provides a documented fallback).
* If `|C(m)| ≥ 1`, S1 MUST choose exactly **one** row `c*(m)` via a deterministic tie-break rule.

6.5.5 Tie-break rule MUST be specified and independent of storage/order effects. A recommended pattern:

1. For each `row ∈ C(m)`, construct a tie-break tuple:
   `tb(row) = (priority_rank, jurisdiction_rank, path_hash, row_index)`
   where:

   * `priority_rank` is derived from a field like `priority` (smaller is better) or a documented default,
   * `jurisdiction_rank` is derived from an enum or country ranking if multiple jurisdictions exist,
   * `path_hash` is a deterministic hash (e.g. low-64 bits of SHA-256) of `(logical_id, path)` from `sealed_inputs_3B` associated with this dataset,
   * `row_index` is the row offset within the dataset file(s) as read in a stable, sorted order (e.g. by primary key of the coordinate dataset).

2. Sort `C(m)` by `tb(row)` in lexicographic order and select the first row.

6.5.6 S1 MUST extract from `c*(m)` at least:

* `latitude`, `longitude` (in the advertised CRS), and
* any provenance fields required by `virtual_settlement_3B` (e.g. `evidence_ref`, `jurisdiction`).

If the CRS is not WGS84 but a convertible CRS, S1 MUST apply a deterministic conversion to WGS84 degrees for storage in `virtual_settlement_3B`.

---

6.6 **Settlement timezone resolution**

6.6.1 If the settlement coordinate dataset already contains a field that is the authoritative `tzid_settlement`, S1 MUST:

* validate that the field exists and is non-null for chosen rows `c*(m)`;
* validate that each value conforms to `iana_tzid` as defined in `schemas.layer1.yaml`;
* optionally sanity check that `(latitude, longitude)` is plausibly compatible with the tzid using tz-world/tzdb artefacts;
* use the provided tzid as `tzid_settlement` for `virtual_settlement_3B` with `tz_source = "INGESTED"`.

6.6.2 If `tzid_settlement` is not present in the coordinate dataset (or the spec requires using polygon-based resolution), S1 MUST compute `tzid_settlement` using a deterministic, RNG-free procedure aligned with 2A:

1. Use the sealed tz-world polygons and tzdb archive from `sealed_inputs_3B` (already validated in S0).
2. For each merchant `m ∈ V`, pass `(settlement_latitude_deg, settlement_longitude_deg)` through the same **point-in-polygon + ε-nudge** procedure used in 2A.S1 (same `tz_nudge` parameters and overrides), or a documented compatible variant.
3. Apply any tz overrides (site/merchant/country scoped) if the 3B design requires separate override packs for settlements, using fixed precedence rules (e.g. site ≻ merchant ≻ country).
4. If no tzid can be assigned (point falls outside all tz polygons even after nudge and overrides), S1 MUST treat this as a settlement-tz coverage failure and abort, unless a documented fallback exists.

6.6.3 The resulting tzid MUST be stored as `tzid_settlement` and accompanied by a provenance enum:

* `tz_source = "POLYGON"` if derived from tz-world polygons and tzdb;
* `tz_source = "OVERRIDE"` if an override changed the polygon-derived result;
* `tz_source = "INGESTED"` if taken directly from the coordinate artefact;

The vocabulary MUST be closed and declared in `schemas.3B.yaml`.

---

6.7 **`settlement_site_id` construction**

6.7.1 S1 MUST construct a deterministic, globally unique `settlement_site_id` for each virtual merchant settlement node. It MUST:

* be typed as an `id64` / `hex64` (or other explicit type defined in `schemas.layer1.yaml`);
* be guaranteed to be unique within Layer-1 with extremely high probability;
* not collide with the `site_id` space used by 1A/1B physical outlets (e.g. different type / format).

6.7.2 A normative construction example (binding once adopted):

* Let `key_bytes = UTF8("3B.SETTLEMENT") || 0x1F || UTF8(merchant_id)`
  (where `merchant_id` is the canonical string form).
* Compute `digest = SHA256(key_bytes)` (binary 32 bytes).
* Take `settlement_site_id_u64 = LOW64(digest)` (low-order 64 bits interpreted as big-endian unsigned integer).
* Encode `settlement_site_id_u64` as a 16-character, zero-padded, lower-case hex string.

6.7.3 S1 MUST use the same procedure for all virtual merchants for a given schema version. Any change to this construction is a breaking change and MUST follow the change-control rules in §12.

6.7.4 S1 MUST ensure that `settlement_site_id` is **functionally dependent** on the merchant key (and only on fields declared in the construction), so that it can be recomputed in validation without additional context.

---

6.8 **Phase E — Output materialisation & ordering**

6.8.1 Once classification and settlement nodes are computed, S1 MUST materialise:

* `virtual_classification_3B` with one row per `merchant_id ∈ M`;
* `virtual_settlement_3B` with one row per `m ∈ V`.

6.8.2 Before writing:

* `virtual_classification_3B` rows MUST be sorted by `merchant_id` (or composite `merchant_key`) ascending;
* `virtual_settlement_3B` rows MUST be sorted by the same key, and optionally by `settlement_site_id` as secondary sort, exactly as declared in `writer_sort`.

6.8.3 S1 MUST write both datasets under the declared `path_template` and `partition_keys` (`seed`, `fingerprint`) using an atomic write or move procedure to avoid partial observability.

6.8.4 If datasets already exist for the same `{seed, fingerprint}`:

* S1 MAY recompute the expected contents and compare them byte-for-byte;
* If identical, S1 MAY treat the run as a no-op;
* If different, S1 MUST treat this as an environment drift or replay inconsistency and fail without overwriting (see §7 and §9).

---

6.9 **Prohibited behaviours**

6.9.1 S1 MUST NOT:

* emit or append to any RNG logs (`rng_audit_log`, `rng_trace_log`) or RNG event streams;
* create, modify or delete physical outlets or timezone records managed by 1A/1B/2A;
* classify merchants based on implicit rules not encoded in the virtual-classification policy artefact;
* silently drop merchants from `virtual_classification_3B` or `virtual_settlement_3B` in the presence of data quality issues (such issues MUST be escalated as errors according to §8 and §9).

6.9.2 Any implementation that violates these constraints is **non-conformant** with this specification and MUST be treated as a bug in the engine or spec translation, not as an allowed behavioural variant.

---

## 7. Identity, partitions, ordering & merge discipline *(Binding)*

7.1 **Identity model for 3B.S1**

7.1.1 For S1, the **canonical run identity triple** is:

* `seed`
* `parameter_hash`
* `manifest_fingerprint`

These MUST be identical to the values recorded for the same manifest in `s0_gate_receipt_3B`.

7.1.2 For persisted S1 outputs, the **primary on-disk identity** is the pair:

* `seed`
* `manifest_fingerprint`

There MUST be at most one `virtual_classification_3B` dataset and at most one `virtual_settlement_3B` dataset for each `{seed, manifest_fingerprint}` pair in the storage namespace.

7.1.3 `parameter_hash` is part of the **logical run identity**, but MUST NOT be used as a partition key for any S1 output. If present as a column, it is a convenience echo only and MUST match the value recorded in `s0_gate_receipt_3B`.

7.1.4 If `run_id` is used by the Layer-1 harness, it MAY be recorded in S1 logs and optional columns, but:

* MUST NOT be used for partitioning;
* MUST NOT appear in dataset names or directory structure for S1 outputs;
* MUST NOT alter any observable behaviour of S1 with respect to identity or ordering.

7.1.5 For a given `{seed, parameter_hash, manifest_fingerprint}`, any downstream component MUST be able to identify the S1 outputs uniquely by:

* looking up `virtual_classification_3B` and `virtual_settlement_3B` via the dataset dictionary;
* substituting `seed` and `manifest_fingerprint` into the declared `path_template` fields.

---

7.2 **Partition law**

7.2.1 `virtual_classification_3B` MUST be partitioned exactly by:

* `seed={seed}`
* `fingerprint={manifest_fingerprint}`

and by no other keys. Its `path_template` MUST embed these tokens and no additional partition dimensions.

7.2.2 `virtual_settlement_3B` MUST also be partitioned exactly by:

* `seed={seed}`
* `fingerprint={manifest_fingerprint}`

with a path template of the same form. It MUST share the same `seed` and `manifest_fingerprint` values as the `virtual_classification_3B` produced by the same S1 run.

7.2.3 S1 MUST NOT create:

* per-`parameter_hash` partitions for S1 outputs;
* per-`run_id` partitions;
* any sharded or sub-partitioned layout beyond what is declared in the dictionary.

If additional sharding is needed for performance reasons, it MUST be modelled and versioned explicitly in the dataset dictionary and spec, not introduced ad-hoc.

7.2.4 For each `{seed, manifest_fingerprint}` partition, S1 MUST treat the set of files under that directory as an **atomic dataset**. Partial partitions (e.g. only some files or only one of the two datasets) MUST be treated as invalid.

---

7.3 **Primary keys, ordering & writer sort**

7.3.1 `virtual_classification_3B` MUST have a logical **primary key**:

* `PK_virtual_classification = (merchant_id)`
  (or `(merchant_key, …)` if a composite key is explicitly adopted).

Within a `{seed, fingerprint}` partition, there MUST be at most one row per primary key.

7.3.2 `virtual_settlement_3B` MUST have a logical **primary key**:

* `PK_virtual_settlement = (merchant_id, settlement_site_id)`
  (or `(merchant_key, settlement_site_id)` for a composite merchant key),

with the additional constraint that there is exactly **one** row per merchant key, i.e. different `settlement_site_id` values MUST NOT exist for the same merchant in the same run.

7.3.3 The **natural join key** from `virtual_settlement_3B` to `virtual_classification_3B` is:

* `(merchant_id)` (or the composite merchant key if adopted).

Downstream 3B states MUST use this key for joins and MUST NOT rely on incidental equality of other attributes.

7.3.4 `writer_sort` MUST be set and respected as follows:

* `virtual_classification_3B.writer_sort` = `["merchant_id"]` (or `["merchant_key", …]`),
* `virtual_settlement_3B.writer_sort` = `["merchant_id"]` (and optionally `["merchant_id","settlement_site_id"]` if defined in the dictionary).

S1 MUST sort records by these keys before writing. Any consumer that relies on sorted input MUST rely on these declarations, not on incidental file ordering.

7.3.5 When constructing `virtual_classification_3B` and `virtual_settlement_3B`, S1 MUST iterate over merchants in a deterministic order (e.g. ascending `merchant_id`) to ensure stable record ordering and reproducible outputs.

---

7.4 **Merge, overwrite & re-run discipline**

7.4.1 S1 outputs for a given `{seed, manifest_fingerprint}` are **logically immutable**. Once a successful S1 run has written both:

* `virtual_classification_3B@seed={seed}, fingerprint={manifest_fingerprint}`, and
* `virtual_settlement_3B@seed={seed}, fingerprint={manifest_fingerprint}`,

no subsequent run MAY mutate these datasets in place.

7.4.2 If S1 is invoked again for a `{seed, parameter_hash, manifest_fingerprint}` for which S1 outputs already exist:

* S1 MAY recompute the full expected contents of both datasets;
* S1 MUST compare the recomputed contents with the existing datasets (either via byte comparison or via a documented, deterministic digest method);
* If they are identical, S1 MAY treat the run as an idempotent no-op and leave the existing files untouched;
* If they differ, S1 MUST treat this as an identity / environment conflict and fail with a FATAL error. It MUST NOT overwrite the existing datasets.

7.4.3 S1 MUST ensure that writing outputs is **atomic** at the dataset level:

* It MUST NOT leave a state where `virtual_classification_3B` for a `{seed, fingerprint}` has been updated but `virtual_settlement_3B` has not (or vice versa);
* It MUST either publish both datasets successfully, or publish neither, for that `{seed, fingerprint}`.

7.4.4 Any partial or inconsistent state detected by downstream consumers (e.g. one dataset exists while the other is missing, or primary keys do not align) MUST be treated as an S1 failure, not as valid output. Such conditions MUST be reported using S1’s error namespace.

---

7.5 **Cross-segment identity & join discipline**

7.5.1 The `merchant_id` (or composite merchant key) used in S1 outputs MUST be:

* identical in type and semantics to the key used in the merchant reference dataset;
* compatible with the keys used in upstream segments (1A/1B/2A/3A) for the same merchants.

S1 MUST NOT introduce a different merchant identifier scheme without explicit change control.

7.5.2 Any 3B state that joins S1 outputs to upstream datasets (1A/1B/2A/3A) MUST:

* use the documented join keys (e.g. `merchant_id` + any necessary country/segment-specific keys);
* honour the partition rules of both sides (e.g. same `seed`, same `manifest_fingerprint`);
* treat mismatched or missing rows as data-quality issues, not as licence to invent or drop merchants silently.

7.5.3 S1 MUST ensure that its outputs **do not introduce new merchant IDs** that are not present in the merchant reference used in Phase B. Likewise, S1 MUST NOT drop merchants from `virtual_classification_3B` unless the design explicitly permits a virtual-only classification surface and the schema reflects that.

---

7.6 **Multi-manifest behaviour**

7.6.1 S1 MUST treat `manifest_fingerprint` as the boundary for its outputs. There is no requirement that:

* two different `manifest_fingerprint` values share the same virtual universe;
* classification or settlement decisions be identical across manifests.

Different manifests may seal different configurations and artefacts; S1 MUST only guarantee determinism **within** a single manifest.

7.6.2 Operators and downstream tools MUST assume that:

* S1 outputs for different manifests are independent;
* any cross-manifest comparison of `virtual_classification_3B` or `virtual_settlement_3B` is a higher-level concern (e.g. for drift detection), not part of the S1 contract.

---

7.7 **Non-conformance and correction**

7.7.1 Any implementation that:

* departs from the partition law in §7.2,
* uses alternative keys or unsorted writer order contrary to §7.3,
* silently overwrites existing S1 outputs without conflict detection, or
* mutates S1 outputs from another state,

is **non-conformant** with this specification.

7.7.2 Such behaviour MUST be treated as a bug in the engine or spec translation. Corrective action MUST restore:

* the partition and identity rules described above;
* immutability and idempotence guarantees;
* deterministic ordering of rows.

Where necessary, corrective migrations MAY be run to repair past outputs, but the repaired outputs MUST then conform to this section going forward.

---

## 8. Acceptance criteria & gating obligations *(Binding)*

8.1 **S1 state-level PASS criteria**

8.1.1 A run of 3B.S1 for a given `{seed, parameter_hash, manifest_fingerprint}` SHALL be considered **PASS** if and only if **all** of the following conditions hold:

**Identity & environment**

a. `s0_gate_receipt_3B` and `sealed_inputs_3B` exist for the target `manifest_fingerprint` and validate against their schemas.
b. `segment_id = "3B"` and `state_id = "S0"` in `s0_gate_receipt_3B`.
c. The `seed`, `parameter_hash`, and `manifest_fingerprint` that S1 uses match those in `s0_gate_receipt_3B`.
d. `upstream_gates.segment_1A/1B/2A/3A.status = "PASS"` in `s0_gate_receipt_3B`.

**Contracts & inputs**

e. `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml` form a compatible triplet, either as recorded in `catalogue_versions` or as reloaded by S1.
f. All mandatory artefacts required by S1 (merchant reference, virtual-classification policy, settlement coordinate source(s), any required mapping tables, and any tz/geospatial artefacts if S1 resolves tzid) are present in `sealed_inputs_3B`, readable, and schema-conformant.
g. The merchant reference dataset is present, readable, and satisfies minimum structural requirements:

* required columns (`merchant_id`, `mcc` / rule key, `channel` if used, `home_country_iso` / `legal_country_iso` if used) exist and have correct types;
* `merchant_id` is unique in the reference view used by S1 (or any allowed deduplication rule is explicitly triggered and recorded).

**Classification correctness**

h. For every merchant in the classification universe `M`, S1 produces exactly one classification record in `virtual_classification_3B` (unless the spec is explicitly in “virtual-only surface” mode; see 8.2.2).
i. All rows in `virtual_classification_3B` validate against `schemas.3B.yaml#/plan/virtual_classification_3B` and obey:

* `merchant_id` uniqueness within `{seed,fingerprint}`;
* non-null `is_virtual` / `classification`;
* non-null `decision_reason` in the allowed enum;
* consistent `source_policy_id` / `source_policy_version` within the partition.
  j. Every classification decision is traceable to the virtual-classification policy:
* exactly one rule/override path is responsible for each `decision_reason`;
* no merchant is classified via ad-hoc logic outside the policy.

**Settlement correctness**

k. Let `V = {m ∈ M | classification(m) = VIRTUAL}`. For each `m ∈ V`, S1 resolves a settlement coordinate row `c*(m)` via the deterministic join/tie-break rule, or fails with a documented error if none is available.
l. `virtual_settlement_3B` contains exactly one row per `m ∈ V`, and no rows for `m ∉ V`.
m. All rows in `virtual_settlement_3B` validate against `schemas.3B.yaml#/plan/virtual_settlement_3B` and obey:

* `(merchant_id, settlement_site_id)` uniqueness within `{seed,fingerprint}`;
* `settlement_latitude_deg` ∈ `[-90,90]`, `settlement_longitude_deg` in the declared longitude range;
* non-null, schema-conformant `tzid_settlement` (IANA tzid);
* non-null `coord_source_id` / `coord_source_version` consistent with sealed coordinate artefacts;
* non-null `tz_source` in its declared enum.
  n. The join key from `virtual_settlement_3B` to `virtual_classification_3B` (typically `merchant_id`) is complete and bijective on `V`:
* for every row in `virtual_settlement_3B`, there exists exactly one matching row in `virtual_classification_3B` with `is_virtual = 1`;
* there are no `virtual_classification_3B` rows with `is_virtual = 1` that lack a corresponding settlement row, unless explicitly permitted under configured partial-coverage rules (see 8.2.3).

**Output structure & identity**

o. Both `virtual_classification_3B` and `virtual_settlement_3B` are written under their canonical `path_template` with `partition_keys = ["seed","fingerprint"]` and with the declared `writer_sort`.
p. If identity echo columns (`seed`, `manifest_fingerprint`, `parameter_hash`) are present, they match the run identity and S0 receipt.
q. No RNG events are emitted and no 3B.S1 entries appear in RNG audit/trace logs; S1 has **zero** observable RNG activity.

8.1.2 If **any** of the criteria in 8.1.1 fail, the S1 run MUST be considered **FAIL**. S1 MUST NOT publish incomplete or partially correct outputs as if they were valid; any artefacts written before detecting failure MUST be treated as invalid and MUST NOT be used by downstream states.

---

8.2 **Classification & settlement coverage semantics**

8.2.1 By default, S1 operates in **full-coverage mode**, where:

* every merchant in `M` MUST have a classification row in `virtual_classification_3B`; and
* every merchant with `is_virtual = 1` MUST have a corresponding settlement row in `virtual_settlement_3B`.

8.2.2 A **virtual-only classification surface** (i.e. `virtual_classification_3B` containing only rows for `m ∈ V`) is allowed **only** if:

* this mode is explicitly declared in the 3B spec and encoded in `schemas.3B.yaml` (e.g. by schema naming and documentation), and
* downstream states and consumers are documented as relying on a virtual-only view.

In such a mode, S1 MUST still maintain 1:1 consistency between `virtual_settlement_3B` and the virtual-only classification surface.

8.2.3 Partial settlement coverage for virtual merchants (e.g. allowing some `m ∈ V` to have no settlement coordinates) is **NOT permitted** by default. If the design chooses to support it:

* it MUST be guarded by explicit configuration and described in the 3B spec;
* S1 MUST record affected merchants in a diagnostic surface and/or run-report, with specific error codes or flags;
* S1 MUST define clear downstream semantics (e.g. “these merchants are virtual but unroutable and MUST be excluded from traffic generation”) and such semantics MUST be reflected in sections for later states.

Until such a mode is explicitly introduced, **S1 PASS requires full settlement coverage for all `m ∈ V`.**

---

8.3 **Gating obligations on downstream 3B states**

8.3.1 For a given `{seed, manifest_fingerprint}`, every downstream 3B state (e.g. edge catalogue, CDN alias, 3B validation) MUST, before performing data-plane work:

* verify that `virtual_classification_3B` and `virtual_settlement_3B` exist at their canonical locations for that `{seed, fingerprint}`;
* validate these datasets against their schemas;
* check basic invariants:

  * key uniqueness and join consistency as in 8.1.1 h–n;
  * partition keys and identity echoes (if present) match run identity.

8.3.2 Downstream states MUST treat `virtual_classification_3B` as the **sole source** of virtual membership:

* they MUST NOT re-evaluate MCC/channel rules or other inputs to decide which merchants are virtual;
* they MUST NOT override `is_virtual` or `classification` flags from S1 in a way that changes the virtual set;
* any additional virtual categories (e.g. “semi-virtual”, “platform virtual”) MUST be modelled as additional flags or subclasses layered on top of `virtual_classification_3B`, not by changing it.

8.3.3 Downstream states MUST treat `virtual_settlement_3B` as the **sole source** of legal settlement anchors for virtual merchants:

* they MUST NOT invent alternative settlement coordinates for merchants in `V`;
* they MUST NOT treat physical outlet coordinates or other data sources as settlement nodes for these merchants.

If any downstream state needs a different representation (e.g. cluster-level settlements, jurisdictional groupings), it MUST derive these from `virtual_settlement_3B` and publish them as new datasets without mutating S1 outputs.

8.3.4 If a downstream state discovers:

* a merchant with `is_virtual = 1` but no settlement row, or
* a settlement row without corresponding classification, or
* any key inconsistency between S1 outputs,

it MUST treat this as an S1 failure / environment inconsistency and:

* MUST NOT attempt to repair it locally;
* MUST fail fast with an error that points to S1 (using S1’s error namespace where appropriate);
* MUST avoid emitting any downstream egress that depends on S1.

---

8.4 **Obligations with respect to S0 and upstream gates**

8.4.1 S1 acceptance is **nested inside** S0 acceptance. For a given `manifest_fingerprint`, S1 is only meaningful if:

* S0 has successfully sealed the inputs (`sealed_inputs_3B`) and
* recorded all upstream segment gates as `PASS`.

8.4.2 If, when reading `s0_gate_receipt_3B`, S1 finds any upstream `segment_*` with `status ≠ "PASS"`, S1 MUST:

* fail without writing any S1 outputs;
* log an error indicating that 3B is blocked by upstream;
* rely on S0 / upstream segments to correct the upstream failure.

8.4.3 S1 MUST NOT attempt to bypass S0 or re-open the upstream gating logic. Its obligations are:

* to enforce that its **own** preconditions are consistent with S0;
* to ensure that it only consumes artefacts that S0 has sealed;
* to propagate gating information via run-report and error codes for downstream visibility.

---

8.5 **Acceptance vs configuration / feature flags**

8.5.1 If a configuration flag indicates that 3B’s virtual path is **enabled**, S1 acceptance criteria in 8.1 and 8.2 apply fully.

8.5.2 If a configuration flag indicates that 3B’s virtual path is **disabled**, S1 MUST still behave deterministically and obey:

* identity and environment checks (8.1.1 a–g),
* schema correctness of outputs (8.1.1 h–p),

but the semantics are:

* `virtual_classification_3B` MUST explicitly encode that no merchants are virtual (e.g. `is_virtual = 0` for all `m ∈ M`, or `V = ∅` and the dataset clearly documented as “no virtuals”);
* `virtual_settlement_3B` MUST be empty for that `{seed, fingerprint}`;
* these behaviours MUST be documented and encoded in `schemas.3B.yaml` and the state spec (i.e. an empty `virtual_settlement_3B` under “virtual-disabled” is **PASS**, not error).

8.5.3 Any other configuration-sensitive behaviour (e.g. special handling for mixed virtual/physical merchants) MUST:

* be explicitly described in the 3B spec;
* be reflected in S1’s acceptance criteria;
* be recoded as distinct, documented modes rather than “best-effort” heuristics.

---

8.6 **Failure semantics and propagation**

8.6.1 Any violation of S1’s acceptance criteria (8.1–8.5) MUST result in:

* S1 returning a **FAIL** status for that run;
* no S1 outputs being published as “valid” for that `{seed, fingerprint}` (and partial artefacts removed or quarantined according to implementation policy);
* a canonical S1 error code being logged (namespace `E3B_S1_*`, see §9).

8.6.2 The Layer-1 run harness and any higher-level validation harness MUST treat an S1 failure as:

* a hard gate for downstream 3B states (no S2–S5 execution for that manifest);
* a **3B-level** failure for that manifest until S1 succeeds or the manifest is superseded.

8.6.3 Any downstream 3B state that detects a latent S1 failure (e.g. missing rows, key inconsistency, schema violations) MUST surface this as a S1-related configuration / data issue and MUST not proceed as if S1 were PASS, even if S1 itself previously reported PASS due to an implementation bug.

In all cases, **classification + settlement correctness and completeness** as specified above are the binding conditions under which S1 can be said to have “passed” for a given run.

---

## 9. Failure modes & canonical error codes *(Binding)*

9.1 **Error model & severity**

9.1.1 3B.S1 SHALL use a **state-local error namespace** of the form:

* `E3B_S1_<CATEGORY>_<DETAIL>`

All codes in this section are reserved for 3B.S1 and MUST NOT be reused by other states.

9.1.2 Every surfaced S1 failure MUST carry, at minimum:

* `segment_id = "3B"`
* `state_id = "S1"`
* `error_code`
* `severity ∈ {"FATAL","WARN"}`
* `manifest_fingerprint`
* optional `{seed, parameter_hash}`
* a human-readable `message` (non-normative)

9.1.3 Unless explicitly marked as `WARN`, all codes below are **FATAL** for S1:

* **FATAL** ⇒ S1 MUST NOT publish `virtual_classification_3B` or `virtual_settlement_3B` as valid outputs for that `{seed, fingerprint}`; the 3B segment MUST be considered **not classified / not settled** for that manifest.
* **WARN** ⇒ S1 MAY complete and publish outputs, but the condition MUST be observable via logs / run-report and SHOULD be visible in metrics.

---

### 9.2 Identity & gating failures

9.2.1 **E3B_S1_IDENTITY_MISMATCH** *(FATAL)*
Raised when the identity values observed by S1 do not align:

* `seed`, `parameter_hash`, or `manifest_fingerprint` provided to S1 differ from those embedded in `s0_gate_receipt_3B`; or
* `s0_gate_receipt_3B` embeds inconsistent identity fields.

Typical triggers:

* S0 and S1 invoked with different identity triples;
* manual editing of S0 artefacts.

Remediation:

* Ensure the run harness passes the same `{seed, parameter_hash, manifest_fingerprint}` to S0 and S1;
* regenerate S0 artefacts if they were tampered with.

---

9.2.2 **E3B_S1_GATE_MISSING_OR_INVALID** *(FATAL)*
Raised when S1 cannot use S0 outputs:

* `s0_gate_receipt_3B` or `sealed_inputs_3B` missing for the target fingerprint;
* or either artefact fails schema validation.

Typical triggers:

* S1 invoked before S0 has run;
* S0 failed but its failure was ignored by orchestration;
* storage corruption or schema drift.

Remediation:

* Run or fix 3B.S0 for the manifest;
* restore or regenerate the missing/invalid artefacts.

---

9.2.3 **E3B_S1_UPSTREAM_GATE_BLOCKED** *(FATAL)*
Raised when `s0_gate_receipt_3B.upstream_gates.segment_*` indicates that any of 1A, 1B, 2A or 3A is not `status = "PASS"`.

Typical triggers:

* upstream segment failed validation or never ran for this manifest.

Remediation:

* Repair or rerun the failing upstream segment;
* re-run S0 (and then S1) once upstream gates all PASS.

---

### 9.3 Contract & input-resolution failures

9.3.1 **E3B_S1_SCHEMA_PACK_MISMATCH** *(FATAL)*
Raised when `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, and `artefact_registry_3B.yaml` do not form a compatible set (e.g. MAJOR version mismatch, missing schema refs).

Typical triggers:

* partial deployment of 3B contracts;
* dictionary updated without schema or registry updates.

Remediation:

* align schema/dictionary/registry versions;
* redeploy a consistent contract set and rerun S0 then S1.

---

9.3.2 **E3B_S1_REQUIRED_INPUT_NOT_SEALED** *(FATAL)*
Raised when a **mandatory** S1 input artefact (merchant reference, classification policy, settlement coords, required mapping tables, mandatory tz/geospatial inputs) is not present in `sealed_inputs_3B`.

Typical triggers:

* artefact created but not registered in the catalogue;
* 3B spec updated but S0 not updated to seal the new artefact.

Remediation:

* register the artefact in dictionary/registry;
* update S0 sealing logic;
* rerun S0 then S1.

---

9.3.3 **E3B_S1_INPUT_OPEN_FAILED** *(FATAL)*
Raised when S1 resolves an artefact from `sealed_inputs_3B` but cannot open it for read.

Typical triggers:

* path in sealed_inputs is stale or incorrect;
* permissions / storage endpoint misconfigured.

Remediation:

* fix storage/permissions;
* ensure sealed_inputs paths match real storage layout;
* regenerate S0 if paths or artefacts changed.

---

9.3.4 **E3B_S1_INPUT_SCHEMA_MISMATCH** *(FATAL)*
Raised when an input dataset or policy artefact that declares a `schema_ref` does not conform to that schema.

Typical triggers:

* merchant reference missing required columns;
* classification policy violating its schema (e.g. unknown rule fields);
* settlement coord dataset with wrong column types.

Remediation:

* correct the underlying dataset/policy;
* or update schema/dictionary to reflect its true shape and redeploy.

---

9.3.5 **E3B_S1_MERCHANT_REF_INVALID** *(FATAL)*
Raised when the merchant reference dataset is structurally unusable for classification:

* `merchant_id` duplicates within the classification view;
* missing mandatory columns (`merchant_id`, `mcc` or equivalent, `channel` if required, `home_country_iso`/`legal_country_iso` if required);
* non-conforming values in fields required by the policy.

Remediation:

* fix the upstream ingress / 1A pipeline that produces the merchant reference;
* enforce uniqueness and field completeness before S1.

---

### 9.4 Classification failures

9.4.1 **E3B_S1_CLASS_POLICY_INVALID** *(FATAL)*
Raised when the virtual-classification policy artefact fails to parse or does not validate against `schemas.3B.yaml#/policy/virtual_classification_rules`.

Typical triggers:

* malformed YAML/JSON;
* missing required fields (e.g. rule_id, predicates);
* invalid enum values.

Remediation:

* fix the policy file content and/or schema;
* re-run S0 (to seal the corrected artefact) and then S1.

---

9.4.2 **E3B_S1_CLASS_ATTR_MISSING** *(FATAL)*
Raised when, for at least one merchant, the classification algorithm cannot evaluate rules due to missing attributes that the policy explicitly requires (e.g. `mcc` or `channel` is null).

Typical triggers:

* incomplete merchant reference;
* mismatch between policy expectations and available fields.

Remediation:

* ensure required fields are present for all merchants or adjust the policy to treat missing values explicitly (e.g. via dedicated rules and `decision_reason` codes).

---

9.4.3 **E3B_S1_CLASS_RULE_CONFLICT** *(FATAL)*
Raised when the classification policy produces conflicting instructions for a merchant and the policy does not define a precedence rule that resolves them.

Typical triggers:

* overlapping allow/deny lists without deterministic order;
* multiple override entries for the same merchant or brand;
* rules configured with ambiguous “continue evaluation” semantics.

Remediation:

* update the policy to enforce a deterministic precedence model;
* or adjust S1 spec + schema to encode precedence and re-run.

---

9.4.4 **E3B_S1_CLASS_DECISION_MISSING** *(FATAL)*
Raised when S1 completes rule evaluation but fails to assign a classification outcome for at least one merchant (e.g. due to an unhandled state in the evaluation logic).

Typical triggers:

* policy rules that all yield “no-op” for a merchant without a default;
* implementation error in the classification engine.

Remediation:

* add an explicit default rule to the policy;
* fix the S1 rule-evaluation logic to ensure every merchant gets a classification (`VIRTUAL` or `NON_VIRTUAL`).

---

9.4.5 **E3B_S1_CLASS_DECISION_OUT_OF_DOMAIN** *(FATAL)*
Raised when S1 produces a classification or `decision_reason` that is not in the policy’s allowed domain.

Typical triggers:

* implementation bug mapping internal states to enums;
* stale policy vocabulary vs schema.

Remediation:

* fix mapping logic;
* update schema/enum definitions and policy together.

---

### 9.5 Settlement coordinate & timezone failures

9.5.1 **E3B_S1_SETTLEMENT_KEY_MISSING** *(FATAL)*
Raised when S1 cannot derive the join key `k(m)` from a virtual merchant `m` to the settlement coordinate dataset(s) due to missing mapping data.

Typical triggers:

* missing `brand_id` / mapping row for a merchant;
* incomplete merchant→brand mapping dataset.

Remediation:

* fix or complete the mapping dataset;
* adjust the policy/spec if some merchants are intentionally unmapped (and then encode that behaviour explicitly).

---

9.5.2 **E3B_S1_SETTLEMENT_COORD_MISSING** *(FATAL)*
Raised when, for at least one `m ∈ V`, the settlement coordinate join yields no candidate rows:

* `C(m) = ∅`.

Typical triggers:

* coordinate dataset incomplete;
* mapping to coordinate keys incorrect;
* classification policy marking as virtual a set of merchants for which no coordinates exist.

Remediation:

* either fix/extend the settlement coordinate artefact;
* or adjust the classification policy to exclude such merchants from `V`.

---

9.5.3 **E3B_S1_SETTLEMENT_COORD_CONFLICT** *(FATAL)*
Raised when S1 finds multiple candidate settlement rows for a virtual merchant and cannot resolve them deterministically according to the spec (e.g. tie-break tuple undefined or ambiguous).

Typical triggers:

* multiple rows in the coordinate dataset for a given key, with no clear priority field;
* multiple mapping paths producing conflicting keys.

Remediation:

* amend the coordinate dataset to encode priorities;
* or extend the S1 spec and policy to define the tie-break law, then implement it.

---

9.5.4 **E3B_S1_SETTLEMENT_COORD_INVALID** *(FATAL)*
Raised when chosen settlement coordinates `c*(m)` are structurally invalid:

* non-finite or NaN `latitude` / `longitude`;
* values out of expected bounds (e.g. `|latitude| > 90`);
* CRS not convertible to WGS84 as assumed in S1.

Typical triggers:

* corrupt coordinate dataset;
* mis-declared CRS.

Remediation:

* fix the coordinate dataset;
* correct CRS declarations or add conversion logic in S1 (with appropriate schema updates).

---

9.5.5 **E3B_S1_TZ_RESOLUTION_FAILED** *(FATAL)*
Raised when S1 attempts to derive `tzid_settlement` and fails for one or more virtual merchants:

* no tzid found after point-in-polygon and ε-nudge;
* or applicable overrides are missing or inconsistent.

Typical triggers:

* settlement coordinate outside all tz polygons;
* tz-world / tzdb artefacts incomplete or inconsistent;
* erroneous override configuration.

Remediation:

* correct settlement coordinates or tz-world data;
* add or adjust overrides;
* verify S1’s tz resolution logic against 2A’s semantics.

---

9.5.6 **E3B_S1_TZID_INVALID** *(FATAL)*
Raised when `tzid_settlement` values in `virtual_settlement_3B`:

* are not valid IANA tzids according to `schemas.layer1.yaml`;
* or do not match any tzid in the sealed tz-world / tzdb artefacts (if checked).

Typical triggers:

* ingestion of free-text tz strings;
* inconsistent tzdb versions.

Remediation:

* fix ingestion / mapping to use canonical IANA tzids;
* align tz-world and tzdb artefacts with S1’s expectations.

---

### 9.6 Output structure, identity & consistency failures

9.6.1 **E3B_S1_VCLASS_SCHEMA_VIOLATION** *(FATAL)*
Raised when `virtual_classification_3B` fails validation against `schemas.3B.yaml#/plan/virtual_classification_3B`.

Typical triggers:

* missing required columns;
* wrong types for `merchant_id`, `is_virtual`, `decision_reason`;
* wrong partitioning or writer sort.

Remediation:

* fix S1 write path and sort;
* or correct schema/dictionary to match intended shape (with proper versioning).

---

9.6.2 **E3B_S1_VSETTLEMENT_SCHEMA_VIOLATION** *(FATAL)*
Raised when `virtual_settlement_3B` fails validation against `schemas.3B.yaml#/plan/virtual_settlement_3B`.

Typical triggers:

* missing columns (e.g. `settlement_site_id`);
* invalid coordinate or tzid types;
* wrong partitioning or sort order.

Remediation:

* fix S1 settlement-node construction and writing;
* adjust schema/dictionary if the intended shape differs.

---

9.6.3 **E3B_S1_JOIN_INCONSISTENT** *(FATAL)*
Raised when the join between S1 outputs is not coherent:

* some merchants with `is_virtual = 1` in `virtual_classification_3B` lack a row in `virtual_settlement_3B` (in coverage-required mode);
* there exist rows in `virtual_settlement_3B` for merchants not classified as virtual;
* duplicates violate key uniqueness constraints.

Remediation:

* correct classification or settlement logic;
* ensure full coverage and consistency;
* re-run S1 once the underlying issue is fixed.

---

9.6.4 **E3B_S1_OUTPUT_WRITE_FAILED** *(FATAL)*
Raised when S1 cannot complete the atomic write of one or both outputs (e.g. due to IO errors, insufficient permissions, storage outage).

Remediation:

* correct the underlying storage/permission problem;
* re-run S1;
* ensure the engine uses atomic write/move semantics for publishing datasets.

---

9.6.5 **E3B_S1_OUTPUT_INCONSISTENT_REWRITE** *(FATAL)*
Raised when S1 detects that existing outputs for the same `{seed, manifest_fingerprint}` are not identical to recomputed outputs in a subsequent run.

Typical triggers:

* environment drift (catalogues, policies, upstream data) under a constant `manifest_fingerprint`;
* manual tampering with S1 outputs.

Remediation:

* treat as manifest/environment inconsistency;
* either restore the environment that produced the original outputs, or recompute a **new** `manifest_fingerprint` and run S0+S1 under that new manifest.

---

### 9.7 RNG & non-determinism violations

9.7.1 **E3B_S1_RNG_USED** *(FATAL)*
Raised if any RNG activity is observed under S1:

* RNG events attributed to 3B.S1 in `rng_audit_log` / `rng_trace_log`;
* use of RNG APIs during classification or settlement resolution.

Typical triggers:

* accidental use of helper functions that emit RNG events;
* tests or debugging code left enabled.

Remediation:

* remove RNG usage from S1;
* add regression tests to ensure S1 remains RNG-free.

---

9.7.2 **E3B_S1_NONDETERMINISTIC_ENUMERATION** *(FATAL or WARN, deployment policy dependent)*
Raised when S1 exhibits non-deterministic behaviour between re-runs with identical inputs, such as:

* different row ordering in `virtual_classification_3B` or `virtual_settlement_3B`;
* different settlement node choices for some merchants;
* inconsistent classification results.

Typical triggers:

* reliance on unsorted directory listings or hash-map iteration order;
* non-canonical JSON/YAML parsing differences.

Remediation:

* enforce explicit ordering at all enumeration steps (merchants, rule sets, coordinate candidates);
* use canonical encoders for JSON/YAML where necessary.

For production, this SHOULD be treated as FATAL until determinism is proven.

---

### 9.8 Error propagation & downstream behaviour

9.8.1 Whenever S1 raises a FATAL error code, it MUST:

* log a structured error event including the fields in 9.1.2;
* ensure that neither `virtual_classification_3B` nor `virtual_settlement_3B` is exposed as **valid** for that `{seed, fingerprint}` (partially written artefacts MUST be treated as invalid).

9.8.2 The run harness MUST surface S1 FATAL errors as **“3B.S1 classification/settlement failure”** for the affected manifest and MUST:

* prevent downstream 3B states (S2–S5) from running for that manifest;
* avoid emitting any 3B egress that depends on S1.

9.8.3 Downstream 3B states that detect an S1-related inconsistency at consumption time (e.g. join failure, schema mismatch, missing rows) SHOULD:

* re-use the most appropriate `E3B_S1_*` error code, but
* tag themselves as the originating state in logs (e.g. `state_id = "S2"`),

so that it is clear the error is due to an S1 contract violation but was detected downstream.

9.8.4 Any new S1 failure condition introduced in future versions MUST:

* be assigned a unique `E3B_S1_...` code;
* be documented with severity, typical triggers and remediation guidance;
* not overload existing codes with incompatible new semantics.

---

## 10. Observability & run-report integration *(Binding)*

10.1 **Structured logging requirements**

10.1.1 S1 MUST emit, at minimum, the following **lifecycle log events** for each attempted run:

* a **`start`** event when S1 begins work for a given `{seed, parameter_hash, manifest_fingerprint}`, and
* a **`finish`** event when S1 either completes successfully or fails.

10.1.2 Both `start` and `finish` events MUST be structured and include at least:

* `segment_id = "3B"`
* `state_id = "S1"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `event_type ∈ {"start","finish"}`
* `ts_utc` (UTC timestamp of the log event)

10.1.3 The `finish` event MUST additionally include:

* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL; `null` or omitted for PASS)
* `classified_merchant_count` (size of classification universe `M`)
* `virtual_merchant_count` (size of `V`)
* `settlement_row_count` (row count of `virtual_settlement_3B` actually written; 0 is valid in “virtual disabled” mode)
* `outputs_written` — boolean indicating whether `virtual_classification_3B` and `virtual_settlement_3B` were successfully written and validated

10.1.4 For every FATAL error, S1 MUST emit at least one **error log event** containing the fields in §9.1.2 plus any relevant diagnostic context (e.g. problematic `merchant_id`, `logical_id` of offending artefact).

---

10.2 **Run-report record for 3B.S1**

10.2.1 S1 MUST produce a **run-report record** (per `{seed, manifest_fingerprint}`) consumable by the Layer-1 run-report harness. This may be a dedicated dataset or an in-memory record passed to the harness, but its content MUST include:

* `segment_id = "3B"`
* `state_id = "S1"`
* `manifest_fingerprint`
* `seed`
* `parameter_hash`
* `run_id` (if present)
* `status ∈ {"PASS","FAIL"}`
* `error_code` (for FAIL)
* `classified_merchant_count`
* `virtual_merchant_count`
* `settlement_row_count`
* `gate_receipt_path` (canonical path to `s0_gate_receipt_3B`)
* `sealed_inputs_path` (canonical path to `sealed_inputs_3B`)
* `virtual_classification_path` (canonical dataset root for `virtual_classification_3B`)
* `virtual_settlement_path` (canonical dataset root for `virtual_settlement_3B`)

10.2.2 Where available, the run-report record SHOULD also include:

* `source_policy_id` and `source_policy_version` for the classification policy used
* `coord_source_id` / `coord_source_version` for settlement coordinates
* a brief summary of **coverage metrics**, e.g.:

  * `virtual_without_coords_count` (should be 0 in full-coverage mode)
  * `invalid_coord_count` (e.g. out-of-bounds lat/lon, should be 0 on PASS)

10.2.3 The run-report harness MUST be able to determine, from S1’s record alone:

* whether S1 has successfully classified and settled virtual merchants for this `{seed, manifest_fingerprint}`;
* where to find the S1 outputs;
* whether any coverage issues exist that might impact downstream 3B states (even if S1 is formally PASS in certain “virtual disabled” configurations).

---

10.3 **Metrics & counters**

10.3.1 S1 MUST emit the following **metrics** (names illustrative; concrete names MAY vary but semantics MUST be equivalent):

* `3b_s1_runs_total{status="PASS|FAIL"}` — counter, incremented once per S1 run.
* `3b_s1_classified_merchants` — gauge or histogram; number of merchants in `M`.
* `3b_s1_virtual_merchants` — gauge or histogram; number of merchants in `V`.
* `3b_s1_settlement_rows` — gauge or histogram; number of rows written to `virtual_settlement_3B`.
* `3b_s1_classification_failures_total{error_code=...}` — counter; number of merchants that would have triggered a classification failure, aggregated by error code (these errors MUST ultimately result in a FATAL, but the metric is useful).
* `3b_s1_settlement_failures_total{error_code=...}` — counter; number of virtual merchants that could not be settled due to each failure mode.
* `3b_s1_duration_seconds` — S1 run latency from `start` to `finish`.

10.3.2 Metrics SHOULD be tagged with:

* `segment_id = "3B"`
* `state_id = "S1"`
* a reduced identifier for `manifest_fingerprint` (e.g. hash prefix or run label), to avoid unbounded cardinality
* where appropriate, `error_code` or `artefact_kind` (for failure counters)

10.3.3 Operators SHOULD be able to use these metrics to answer at least:

* “How many merchants are being classified and what fraction are virtual?”
* “Are any manifests failing S1, and with which error codes?”
* “Are we ever producing fewer settlement rows than virtual merchants (indicative of coverage problems)?”
* “Is S1 latency within expected SLOs?”

---

10.4 **Traceability & correlation**

10.4.1 S1 MUST ensure that outputs, logs and run-reports are **correlatable** via a consistent identity:

* `virtual_classification_3B` and `virtual_settlement_3B` paths embed `{seed, fingerprint}`;
* logs and run-reports include `{seed, parameter_hash, manifest_fingerprint}` and `run_id` (if present);
* `s0_gate_receipt_3B` path and identity are referenced explicitly in S1’s run-report record.

10.4.2 Given a specific merchant of interest (`merchant_id`), an operator MUST be able to:

* find its row in `virtual_classification_3B` for a given `{seed, fingerprint}`;
* find its corresponding row in `virtual_settlement_3B` (if `is_virtual = 1`);
* determine from S1 logs and run-report which rule / policy version led to its classification and which coordinate / tz source was used for its settlement node.

10.4.3 If the platform supports **correlation IDs** (e.g. trace IDs), S1 MAY include such IDs in logs and optionally embed them in diagnostic-only fields. These IDs are informational and MUST NOT affect algorithmic behaviour or dataset structure.

---

10.5 **Integration with Layer-1 / 4A–4B validation harness**

10.5.1 S1 MUST expose enough information for the Layer-1 “4A/4B”-style validation harness to:

* confirm that 3B.S1 has run (or not) for each `{seed, manifest_fingerprint}`;
* inspect S1’s PASS/FAIL status and error codes;
* correlate S1 status with S0 status and upstream segments.

10.5.2 The harness MUST be able to derive at least the following from S1’s run-report record:

* `3B.S1.status ∈ {"PASS","FAIL"}`
* `3B.S1.error_code` (if any)
* `3B.S1.classified_merchant_count`
* `3B.S1.virtual_merchant_count`
* `3B.S1.settlement_row_count`
* pointers to `virtual_classification_3B` and `virtual_settlement_3B` datasets

10.5.3 Where the harness builds a **global manifest summary**, S1 SHOULD contribute:

* a quick indicator of the **virtual landscape** (e.g. % of merchants virtual, whether virtual features are enabled);
* any critical WARN-level conditions that should be visible to operators even if S1 is PASS (e.g. a small number of merchants intentionally excluded from settlement by configuration).

---

10.6 **Operational diagnostics & debugability**

10.6.1 On any FATAL S1 failure, S1 SHOULD log **diagnostic context** sufficient for root-cause analysis without re-running S1 under a debugger, for example:

* for classification errors:

  * the affected `merchant_id` (or sample thereof),
  * the `decision_reason` (if any),
  * the relevant `rule_id` or override entry,
  * and the policy logical ID / version.

* for settlement errors:

  * the affected `merchant_id`,
  * the derived settlement key `k(m)` (e.g. `brand_id`),
  * the set size `|C(m)|` of candidate coordinate rows,
  * and any anomalies (e.g. missing coords, conflicting rows).

* for schema / catalogue errors:

  * the offending `logical_id`, `path`, `schema_ref`,
  * and a brief description of the mismatch.

10.6.2 If the engine supports a **debug / dry-run** mode for S1, that mode MUST:

* execute the same deterministic algorithm as normal mode (up to, but not including, writing outputs),
* run the same validations,
* log the same diagnostics,
* but skip publishing `virtual_classification_3B` and `virtual_settlement_3B`.

S1 MUST clearly indicate `mode = "dry_run"` vs `mode = "normal"` in logs and run-report records so operators do not confuse dry-run results with live outputs.

10.6.3 Additional observability features (e.g. sampling of classification decisions with full context, per-rule hit counts) MAY be implemented as long as they do not:

* change the binding dataset schemas or paths;
* introduce non-determinism;
* conflict with the logging and metrics requirements in this section.

Where there is any discrepancy between this section and the schemas or dataset dictionary, the schemas/dictionary SHALL be treated as authoritative, and this section MUST be updated accordingly.

---

## 11. Performance & scalability *(Informative)*

11.1 **Workload character**

11.1.1 3B.S1 is **merchant-centric** and mostly CPU + metadata I/O bound:

* It scans the **merchant reference** once.
* It loads a **moderate-sized classification policy** and **settlement coordinate** table(s).
* It writes two relatively small, merchant-level datasets (`virtual_classification_3B`, `virtual_settlement_3B`).

11.1.2 S1 does **not** read or write high-volume event streams or per-transaction tables. Its cost scales primarily with the number of merchants `|M|` and the size/shape of the settlement coordinate sources.

---

11.2 **Complexity & expected scale**

11.2.1 Let:

* `|M|` = number of merchants in the classification universe;
* `R`  = number of rules in the virtual-classification policy;
* `C`  = number of rows in the settlement coordinate dataset(s);
* `V`  = number of virtual merchants (`|V| ≤ |M|`).

11.2.2 As specified, a typical implementation has:

* **Rule evaluation:**

  * naive upper bound `O(|M| * R)`,
  * often reduced effectively to `O(|M| + R)` if rules are compiled into fast predicates or lookup tables.

* **Settlement lookup:**

  * `O(|M|)` to derive keys and build an index over coordinates (e.g. keyed by merchant/brand), plus
  * `O(|V|)` lookups into that index.

11.2.3 For realistic environments:

* `|M|` in the range **10³–10⁶**,
* `R` in the range **10–100**,
* `C` in the range **O(|M|)** or lower (brands << merchants),

S1 remains linear in `|M|` plus a modest constant factor from rules and joins.

---

11.3 **Latency considerations**

11.3.1 Critical latency components:

* **Merchant scan & rule evaluation** — pure CPU; easily parallelisable but should be fine single-threaded for moderate `|M|`.
* **Settlement join** — linear pass with lookups; dominated by coordinate index construction and join.
* **I/O** — reading merchant reference and coordinate tables, and writing the two S1 outputs.

11.3.2 For typical sizes, S1 should be comfortably within **sub-minute** latency for a single `{seed, manifest_fingerprint}` on a modest cluster, assuming:

* storage is local or low-latency;
* merchant and coordinate tables are not orders of magnitude larger than expected;
* no excessive logging or debugging is enabled.

11.3.3 If S1 becomes a bottleneck:

* profile whether time is spent in rule evaluation, coordinate join, or I/O;
* consider pre-indexing / pre-aggregating settlement coordinates (e.g. materialised “brand → coord” view) as a separate ingestion step;
* ensure merchant reference and settlement tables are compressed but efficiently splittable (e.g. columnar formats).

---

11.4 **Memory & parallelism**

11.4.1 A straightforward, single-process implementation that:

* streams the merchant reference;
* holds the classification policy in memory;
* holds a hash-map index of settlement coordinates keyed by merchant/brand,

should fit easily in memory for typical `|M|` and `C`.

11.4.2 If `|M|` or `C` is very large:

* it is RECOMMENDED to **stream merchants** and hold only a compact index of coordinates in memory;
* rule evaluation and settlement lookup can be **thread-parallelised per merchant** as long as determinism is preserved (e.g. final outputs are sorted by key before writing).

11.4.3 Any parallel implementation MUST:

* avoid concurrency races that could alter classification/settlement results;
* enforce deterministic ordering at write time (see §7.3);
* never use thread scheduling or unordered map iteration as an implicit source of randomness.

---

11.5 **I/O patterns & data locality**

11.5.1 S1’s I/O profile is:

* one or a small number of **sequential reads** of merchant reference dataset(s);
* one or a small number of **sequential reads** of settlement coordinate dataset(s) and optional mapping tables;
* two **sequential writes** for S1 outputs (`virtual_classification_3B`, `virtual_settlement_3B`).

11.5.2 Performance is best when:

* merchant and coordinate datasets are stored in a columnar format with predicate pushdown (even if S1 doesn’t use heavy predicates, it benefits from reading only relevant columns);
* data is located in the same region / cluster as the S1 compute;
* filesystem / object-store listings are fast and cached where possible (though S1 should not rely on listing order for correctness).

11.5.3 Because S1 outputs are small, storage footprint and write bandwidth are rarely limiting factors; S1 is more sensitive to **read latency** on its inputs than to size of its own outputs.

---

11.6 **Scaling strategy & SLOs**

11.6.1 Operators MAY define SLOs such as:

* `P95(3b_s1_duration_seconds) < T` for each environment, where T is chosen based on `|M|` and typical storage conditions;
* constraints on the ratio `virtual_merchant_count / classified_merchant_count` for sanity monitoring (e.g. alert if suddenly 90% of merchants become virtual).

11.6.2 If these SLOs are regularly violated, recommended investigations:

* Check `3b_s1_classified_merchants` / `3b_s1_virtual_merchants` and `3b_s1_settlement_rows` for unexpected growth or anomalies.
* Check upstream ingestion sizes and shapes (merchant and coordinate tables) for drift.
* Profile classification rule evaluation for inefficiencies (e.g. unoptimised regex rules, repeated parsing).
* Ensure S1 isn’t re-reading huge upstream artefacts unnecessarily (e.g. whole bundles for small metadata needs).

11.6.3 Where multiple `{seed, manifest_fingerprint}` combinations are run in parallel, S1’s workload scales **linearly in the number of manifests**, as S1 is manifest-local by design. Horizontal scaling over manifests is straightforward.

---

11.7 **Testing & performance regressions**

11.7.1 Performance regression tests for S1 SHOULD include:

* synthetic or real workloads at the high end of expected `|M|` and `C`;
* runs with complex classification policies (many rules, overlapping conditions);
* runs with large but sparse coordinate tables (many potential keys but relatively few actually used).

11.7.2 Tests SHOULD verify that:

* S1 runtime and memory usage scale approximately linearly with `|M|` for fixed policy and coordinate complexity;
* adding a small number of new optional artefacts or rules does not drastically increase runtime;
* classification and settlement decisions remain deterministic across re-runs.

11.7.3 Since this section is informative, specific numeric thresholds (e.g. target `P95` latencies) and hardware assumptions are left to deployment choices, provided that implementations maintain:

* determinism,
* the identity and ordering guarantees of §§6–7, and
* clear observability via the metrics and run-report fields described in §10.

---

## 12. Change control & compatibility *(Binding)*

12.1 **Scope of change control**

12.1.1 This section governs all changes that affect **3B.S1** and its control-/data-plane artefacts, specifically:

* The **behaviour** of 3B.S1 (classification rules application, settlement-node construction, tie-break rules).
* The **schemas and catalog entries** for:

  * `virtual_classification_3B`
  * `virtual_settlement_3B`
* Any S1-specific references to:

  * classification policies (e.g. `virtual_classification_rules`),
  * settlement coordinate sources,
  * mapping tables (merchant→brand),
  * tz/geospatial inputs used for `tzid_settlement` resolution (if owned or interpreted by 3B).

12.1.2 It does **not** govern:

* S0 contracts (`s0_gate_receipt_3B`, `sealed_inputs_3B`), which follow their own change-control rules.
* The intrinsic definitions of upstream artefacts (`merchant_ids`, `outlet_catalogue`, `site_locations`, `site_timezones`, `zone_alloc`, etc.), which are owned by ingress / 1A / 1B / 2A / 3A.
* The 3B segment-level validation bundle and `_passed.flag`, which are owned by the terminal 3B validation state.

---

12.2 **Versioning of S1-related contracts**

12.2.1 3B contracts impacting S1 MUST be versioned explicitly across:

* `schemas.3B.yaml`
* `dataset_dictionary.layer1.3B.yaml`
* `artefact_registry_3B.yaml`
* any S1-critical policy schemas (e.g. `#/policy/virtual_classification_rules`, `#/ingress/virtual_settlement_coords`, `#/ingress/merchant_brand_mapping`).

12.2.2 Implementations SHOULD follow a semantic-style scheme:

* **MAJOR** — incompatible/breaking changes to shapes, keys, partition law, or core semantics (e.g. redefining “virtual”).
* **MINOR** — backwards-compatible extensions (new optional fields, new optional artefacts, new decision reasons that older consumers can ignore).
* **PATCH** — non-semantic corrections (typos, doc clarifications, stricter validation that only rejects previously invalid data).

12.2.3 S1 MUST verify (directly or via `s0_gate_receipt_3B.catalogue_versions`) that:

* `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, and `artefact_registry_3B.yaml` form a **compatible triplet** for the S1 behaviour it implements (e.g. “same MAJOR version for all three”).

If the triplet is not compatible, S1 MUST fail with an appropriate FATAL error (e.g. `E3B_S1_SCHEMA_PACK_MISMATCH`) and MUST NOT write outputs.

12.2.4 When S1 behaviour changes in a way that affects schemas or catalogue entries, the corresponding version numbers MUST be incremented coherently, and S1 MUST be updated to enforce any new invariants.

---

12.3 **Backwards-compatible vs breaking changes**

12.3.1 The following are considered **backwards-compatible** (MINOR or PATCH) changes for S1, provided they preserve all binding guarantees in §§4–9:

* Adding **optional columns** to `virtual_classification_3B` or `virtual_settlement_3B` (e.g. `created_utc`, `jurisdiction_code`, `evidence_ref`), as long as:

  * no existing required field is removed or repurposed, and
  * default behaviour for missing values is well-defined (“unknown / not recorded”).

* Extending **enumerations** with new values where:

  * old values retain their semantics, and
  * older consumers can safely treat new values as “other” without breaking core logic.

* Introducing **new optional policy artefacts** or mapping datasets, while maintaining a clear default behaviour when they are absent (e.g. no brand mapping used).

* Tightening **validation** in a way that only rejects configurations that were already invalid or unspecified (e.g. enforcing uniqueness of keys that S1 already relied on).

12.3.2 The following are **breaking** (MAJOR) changes for S1:

* Removing or renaming any **required field** in `virtual_classification_3B` or `virtual_settlement_3B`.
* Changing the **type or semantics** of required fields (e.g. redefining `is_virtual` from simple boolean to a multi-valued status without an explicit compatibility layer).
* Changing `path_template`, `partition_keys`, or `writer_sort` for S1 outputs in the dataset dictionary.
* Changing the definition of the primary keys or join keys (e.g. moving from `merchant_id` to a different key without preserving the old one or providing a stable mapping).
* Changing the settlement-node law in a way that makes `settlement_site_id` non-deterministic or no longer a pure function of the merchant key + specified context.
* Redefining the classification semantics (e.g. changing what “virtual” means in a way that materially changes the set `V` under the same manifest and input artefacts) without bumping MAJOR and documenting the semantic shift.

12.3.3 Any breaking change MUST:

* bump the MAJOR version of `schemas.3B.yaml`;
* be accompanied by coordinated updates to `dataset_dictionary.layer1.3B.yaml` and `artefact_registry_3B.yaml`;
* be documented in a 3B/3B.S1 change log with clear migration guidance.

---

12.4 **Mixed-version environments**

12.4.1 A **mixed-version environment** arises when:

* historic S1 outputs (`virtual_classification_3B`, `virtual_settlement_3B`) exist for older 3B schema versions, and
* the current engine and contracts for 3B use a newer MAJOR or MINOR version.

12.4.2 S1 is concerned with **writing** outputs for the current run. It MUST:

* write new outputs using the **current** S1 contracts;
* not rewrite or “upgrade” historical S1 outputs in place.

12.4.3 Reading historical S1 artefacts under older schemas is the responsibility of:

* offline tooling and reporting;
* explicit migration utilities;
* or a 3B validation harness that is version-aware.

S1 MUST NOT silently interpret old outputs as if they conformed to the new schema.

12.4.4 If S1 is invoked for a `{seed, parameter_hash, manifest_fingerprint}` where S1 outputs already exist but **do not validate** against the current schemas:

* S1 MUST NOT overwrite them silently;
* S1 MUST fail with `E3B_S1_OUTPUT_INCONSISTENT_REWRITE` (or a similar FATAL error) and signal that the environment and manifest are inconsistent.

Operators MUST then either:

* treat the old outputs as belonging to a different contract version and stop reusing the same `manifest_fingerprint`; or
* explicitly migrate and re-emit S1 outputs under the new schema and a new fingerprint.

---

12.5 **Migration & deprecation**

12.5.1 When introducing a new field or behaviour that is intended to become **mandatory** in S1:

1. Add it as **optional** in the schema (MINOR bump), with clear semantics and safe defaults.
2. Update S1 to populate it whenever possible and log missing cases where they indicate configuration gaps.
3. Update downstream states and tools to prefer the new field when present.
4. In a later MAJOR version, promote it to **required** once adoption is confirmed.

12.5.2 Deprecating existing fields or artefacts used by S1 SHOULD follow a “two-step” pattern:

* Step 1 (MINOR): mark the field/artefact as deprecated in docs/schema comments, and discourage new uses.
* Step 2 (MAJOR): remove or repurpose it only after downstream consumers have been updated or replaced.

12.5.3 For settlement coordinates and classification policies:

* Deprecating a legacy coordinate source or policy pack SHOULD involve adding a new, preferred artefact and updating S0/S1 to seal and consume the new artefact.
* Only after the new artefact is in full use SHOULD the old artefact be dropped from `sealed_inputs_3B` and S1’s logic; doing so will typically be a breaking change.

---

12.6 **Compatibility with upstream segments & other 3B states**

12.6.1 Changes to S1 MUST remain compatible with the **authority boundaries** of upstream segments:

* S1 cannot redefine what `merchant_id`, `mcc`, `channel`, `legal_country_iso`, `site_locations` or `site_timezones` mean; these remain governed by ingress / 1A / 1B / 2A.
* Any new use of upstream fields MUST be declared in S1’s spec and validated against upstream schemas.

12.6.2 If upstream segments change:

* validation bundle laws, or
* the schemas / IDs of datasets S1 reads (e.g. merchant reference layout or coordinate CRS),

the 3B contracts and S1 spec MUST be updated accordingly. S1 MUST:

* adapt to new schemas in a way that preserves its own contracts (or bump MAJOR if not possible);
* ensure that any new upstream semantics do not silently alter the set `M` or the structure of the inputs S1 expects.

12.6.3 Changes to other 3B states (S2–S5) that depend on S1 outputs MUST consider:

* whether new join keys, fields or semantics are required from S1;
* whether S1 must be extended (MINOR/MAJOR) to provide these;
* whether new downstream behaviours can be layered on **without** changing S1 outputs (preferred).

12.6.4 If a downstream 3B state needs to introduce a fundamentally different view (e.g. multi-node settlements, multiple virtual classes), it SHOULD:

* add new datasets (e.g. `virtual_settlement_multi`) or additional columns,
* rather than repurposing S1’s existing outputs in incompatible ways.

If repurposing is unavoidable, the change MUST be treated as a breaking change.

---

12.7 **Change documentation & review**

12.7.1 Any non-trivial change to 3B.S1 behaviour or contracts MUST be:

* recorded in a change log (e.g. `CHANGELOG.3B.S1.md` or shared `CHANGELOG.3B.md`),
* linked to a specific schema/dictionary/registry version,
* accompanied by a short rationale and migration notes for operators/consumers.

12.7.2 Before deploying S1-affecting changes, implementers SHOULD:

* run regression tests against representative manifests to ensure:

  * deterministic behaviour is preserved,
  * outputs still satisfy all invariants in §§4–9,
  * downstream 3B states and validation harnesses remain compatible.
* explicitly test **idempotence**:

  * re-run S1 under the same `{seed, parameter_hash, manifest_fingerprint}` and confirm outputs are unchanged (or that any change is intentional and reflected in a new fingerprint).

12.7.3 Where this section conflicts with `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml` or `artefact_registry_3B.yaml`, those artefacts SHALL be treated as **authoritative**, and this section MUST be updated as part of the next non-editorial version bump to reflect the contracts actually in force.

---

## 13. Appendix A — Symbols & abbreviations *(Informative)*

> This appendix is descriptive only. Where it conflicts with any Binding section or with JSON-Schema / dictionary / registry entries, those sources take precedence.

---

### 13.1 Identity & governance

* **`seed`**
  Layer-1 Philox seed for the run. Shared across segments for a given manifest; part of the S1 run identity triple.

* **`parameter_hash`**
  Tuple-hash over the governed 3B parameter set (including S1-relevant configs such as feature flags). Logical identity input; not a partition key for S1 outputs.

* **`manifest_fingerprint`**
  Hash of the full Layer-1 manifest (ingress, policies, code, artefacts) as defined by the layer-wide spec. Primary partition key (with `seed`) for S1 outputs.

* **`run_id`**
  Optional, opaque identifier for a concrete execution of S1 under a given `{seed, parameter_hash, manifest_fingerprint}`. Used for logs / run-report only.

* **Numeric/RNG governance**
  Shorthand for the layer-wide numeric and RNG definitions in `schemas.layer1.yaml#/governance/*` and `#/rng/*`. S1 is RNG-free but still checks it is running in the expected governance environment.

---

### 13.2 Sets & per-merchant notation

* **`M`**
  Merchant classification universe. The set of all `merchant_id` values drawn from the merchant reference dataset used by S1 (after any explicit, documented filtering).

* **`V ⊂ M`**
  Set of **virtual merchants**:
  `V = { m ∈ M | classification(m) = VIRTUAL }`
  or equivalently `{ m | is_virtual(m) = 1 }`.

* **`ctx(m)`**
  Classification context for merchant `m ∈ M`: the bundle of attributes S1 uses from ingress/upstream to evaluate rules (e.g. `mcc`, `channel`, `home_country_iso`, `legal_country_iso`, derived buckets, etc.).

* **`classification(m)`**
  Logical classification outcome for merchant `m`:
  `classification(m) ∈ { VIRTUAL, NON_VIRTUAL }`, derived deterministically by evaluating the virtual-classification policy for `ctx(m)`.

* **`decision_reason(m)`**
  Closed-vocabulary reason code explaining the classification outcome for merchant `m` (e.g. `RULE_MCC_POSITIVE`, `RULE_DENYLIST`, `NO_RULE_MATCH`).

---

### 13.3 Settlement-node notation

* **`k(m)`**
  Deterministic **settlement key** for virtual merchant `m ∈ V`, used to join into settlement coordinate datasets. Examples:

  * `k(m) = merchant_id` (direct key), or
  * `k(m) = brand_id(m)` via a mapping table.

* **`C(m)`**
  Candidate settlement rows for a virtual merchant:
  `C(m) = { rows in settlement_coord | key(row) = k(m) }`.

* **`c*(m)`**
  The chosen **single** settlement coordinate row for merchant `m ∈ V`, obtained by applying S1’s deterministic tie-break rule to `C(m)`.

* **`settlement_latitude_deg`, `settlement_longitude_deg`**
  WGS84 latitude/longitude in degrees for the settlement node, derived from `c*(m)` (with CRS conversion if necessary).

* **`tzid_settlement`**
  IANA timezone identifier assigned to the settlement node for merchant `m`. Either:

  * ingested directly from the coordinate artefact, or
  * derived via tz-world / tzdb logic aligned with 2A.

* **`tz_source`**
  Closed enum describing how `tzid_settlement` was obtained, e.g.:

  * `"INGESTED"` — taken directly from coordinate artefact,
  * `"POLYGON"` — derived from tz-world polygons + tzdb,
  * `"OVERRIDE"` — tz override changed the polygon result.

* **`settlement_site_id`**
  Deterministic identifier for the settlement node (e.g. 64-bit hex), constructed as a pure function of the merchant key (and possibly a fixed namespace tag). Unique per virtual merchant within Layer-1.

---

### 13.4 Key datasets & artefacts (S1-relevant)

* **`merchant_reference`**
  Ingress / 1A-owned dataset defining `M`, with at least `merchant_id`, `mcc` (or equivalent), `channel`, `home_country_iso` / `legal_country_iso`. Read-only input to S1.

* **`virtual_classification_3B`**
  S1 egress. Per-merchant classification surface with one row per merchant in the classification universe (or per virtual merchant in “virtual-only” mode). Columns include `merchant_id`, `is_virtual`/`classification`, `decision_reason`, `source_policy_id`, `source_policy_version`, etc.

* **`virtual_settlement_3B`**
  S1 egress. One settlement node per virtual merchant (or per brand key), with `merchant_id` (or `merchant_key`), `settlement_site_id`, coordinates, `tzid_settlement`, and provenance.

* **`virtual_classification_rules`**
  Logical name for the **virtual-classification policy artefact** (e.g. `mcc_channel_rules.yaml`) that defines S1’s rule ladder and override logic.

* **`virtual_settlement_coords`**
  Logical name for the **settlement coordinate dataset(s)** used to provide lat/lon (and optionally tzid, jurisdiction, evidence) for virtual merchants, keyed by `merchant_id` or an intermediate key such as `brand_id`.

* **`merchant_brand_mapping`**
  Optional mapping dataset from `merchant_id` to brand or other aggregate key used to join into settlement coordinates.

* **`s0_gate_receipt_3B`, `sealed_inputs_3B`**
  S0 outputs. Sealed gate receipt and sealed-inputs inventory that S1 trusts for identity, upstream gates and permissible input artefacts.

---

### 13.5 Policy & provenance fields

* **`source_policy_id`**
  Logical ID of the classification policy pack used (e.g. `"mlr.3B.virtual_classification_rules.v1"`). Recorded in `virtual_classification_3B`.

* **`source_policy_version`**
  Version string (typically semantic) of the classification policy (e.g. `"1.2.0"`).

* **`coord_source_id`, `coord_source_version`**
  Logical ID and version of the settlement coordinate artefact from which `c*(m)` was drawn.

* **`decision_reason`**
  Enum value from the classification policy describing why a merchant is virtual / non-virtual (e.g. MCC rule, override, default).

---

### 13.6 Error & status codes (S1)

* **`E3B_S1_*`**
  Namespace for 3B.S1 canonical error codes (e.g. `E3B_S1_REQUIRED_INPUT_NOT_SEALED`, `E3B_S1_CLASS_RULE_CONFLICT`, `E3B_S1_SETTLEMENT_COORD_MISSING`, etc.), as defined in §9.

* **`status ∈ {"PASS","FAIL"}`**
  Run-level status for S1, as recorded in S1 logs and run-report records.

* **`severity ∈ {"FATAL","WARN"}`**
  Error severity associated with an `E3B_S1_*` code.

---

### 13.7 Miscellaneous abbreviations

* **MCC** — Merchant Category Code.
* **CDN** — Content Delivery Network (here, logical representation of “edge” nodes used for virtual routing; not constructed in S1).
* **FK** — Foreign key (join key across datasets).
* **IO** — Input/Output (filesystem / object-store operations).
* **RNG** — Random Number Generator (Philox2x64-10 across Layer-1; S1 is RNG-free).
* **SLO** — Service Level Objective (latency / reliability targets; informative).

---

13.8 **Cross-reference**

For authoritative definitions of shapes and contracts mentioned here, see:

* Layer-wide: `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`.
* Upstream segments: `schemas.1A.yaml`, `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.3A.yaml` and their dictionaries/registries.
* This subsegment: `schemas.3B.yaml`, `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml`.

This appendix is intended as a quick vocabulary reference for implementers and reviewers when reading or implementing 3B.S1.

---
