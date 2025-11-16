# Layer 3 — Segment 6A: Entity & Product World
Here’s a conceptual **state-flow overview for Layer-3 / Segment 6A** in the same style as 5A/5B — high-level, non-binding, but structured enough that someone can see the flow.

**Role in the engine**

By the time 6A runs:

* **Layer-1** has fixed the world of merchants, outlets, zones, and edges.
* **Layer-2** has defined how busy that world is, but doesn’t know anything about *who* is transacting.

**Segment 6A is where we build the cast:**

* customers, accounts, cards, wallets, merchants as counterparties,
* devices and IPs,
* and the static fraud posture (mules, synthetic IDs, risky merchants).

It produces a closed, synthetic entity graph that 6B and everything downstream will use.

---

## 6A.S0 — Gate & sealed inputs

**Purpose**

Set the trust boundary for Layer-3 and freeze the configuration and priors 6A is allowed to use.

**Upstream dependencies**

* PASSed validation bundles for:

  * all relevant Layer-1 segments (1A–3B),
  * Layer-2 segments (5A/5B) if you want entity priors to be consistent with volume.
* Layer-3 contracts:

  * schemas for 6A/6B entities,
  * dataset dictionary entries for entity outputs,
  * artefact registry entries for priors/configs.

**Behaviour**

* Verify that required L1/L2 bundles are PASS for the current `manifest_fingerprint`.
* Resolve and seal:

  * population priors (how many customers/accounts/cards),
  * product mix configs,
  * device/IP distribution priors,
  * initial fraud role priors (mule rates, collusive merchant rates),
  * any taxonomies (customer segments, merchant risk classes).
* Record which artefacts 6A is allowed to read (ids, partitions, digests).

**Outputs**

* `s0_gate_receipt_6A`
  – small fingerprint-scoped receipt proving which upstream bundles/configs were checked.

* `sealed_inputs_6A`
  – inventory of all priors/configs and upstream datasets 6A can use.

---

## 6A.S1 — Customer & party base population

**Purpose**

Instantiate the **universe of customers and parties** from high-level priors.

**Inputs**

* Sealed priors from S0:

  * region-level population sizes,
  * segmentation priors (e.g. student, salaried, self-employed, SME, corporate),
  * household vs individual mixes.
* Layer-1 merchant metadata (for linking “home merchant” preferences later, if you want).

**Behaviour**

* Sample or derive:

  * a set of **customers** with basic attributes (region, segment, rough income/wealth band).
  * optionally, additional parties (e.g. business entities distinct from individual customers).
* Attach stable IDs and link to region/segment taxonomies.

**Outputs**

* `s1_customers_6A`
  – table/graph of customers/parties with attributes (segment, region, lifecycle flags).

This becomes the root set of actors Layer-3 will build on.

---

## 6A.S2 — Accounts & products

**Purpose**

Attach **accounts and products** to customers in a realistic way.

**Inputs**

* `s1_customers_6A`.
* Product mix priors:

  * distribution over products per segment (e.g. current account, credit card, personal loan, merchant account).
  * cross-product correlations (e.g. cards+loans more common in certain segments).

**Behaviour**

For each customer/party:

* Decide:

  * how many accounts they have (deposit, credit, loan, merchant),
  * which products they hold, and what basic parameters those have (limits, pricing tier, opening date).
* Instantiate:

  * **accounts** (with IDs, types, links to customers),
  * **merchant-side accounts** (e.g. merchant acquiring relationships, settlement accounts).

**Outputs**

* `s2_accounts_6A`
  – accounts table keyed by `account_id`, linking to customers and product types.

* `s2_product_links_6A`
  – relationship surface between customers and products (one-to-many, many-to-many as needed).

Now we know “who banks with us and what they hold”.

---

## 6A.S3 — Instruments & credentials

**Purpose**

Create the **instruments** and high-level credentials that will be used in flows:

* cards, account numbers, wallet identifiers,
* login identities at a conceptual level.

**Inputs**

* `s2_accounts_6A`.
* Instrument priors:

  * cards per account/customer distributions,
  * which products get virtual cards or tokens,
  * channel mix assumptions (card present vs card not present, wallet usage, etc.).

**Behaviour**

* Generate:

  * card instruments (PANs/token IDs at a synthetic level),
  * bank account identifiers,
  * wallet IDs and any stored-card relationships.
* Associate:

  * primary + secondary instruments with accounts/customers,
  * simple credential stubs (e.g. login handle types per account; actual secrets are not materialised).

**Outputs**

* `s3_instruments_6A`
  – instrument table (cards, accounts, wallets) linked to `account_id`/`customer_id`.

* `s3_account_instrument_links_6A`
  – relationship surface mapping instruments to their owners and usage roles.

This tells later layers “what can be used to transact”, without yet saying *when* or *how*.

---

## 6A.S4 — Device & network graph

**Purpose**

Build the **device + IP footprint** that glues together customers, accounts and merchants in a realistic way.

**Inputs**

* `s1_customers_6A`, `s2_accounts_6A`, `s3_instruments_6A`.
* Priors on:

  * devices per customer,
  * IP address types (residential vs mobile vs corporate vs data centre),
  * sharing patterns (shared devices in a household, shared IPs in cafés or workplaces).

**Behaviour**

* Instantiate:

  * devices with attributes (type, OS, risk tags),
  * IPs with simple attributes (ASN, country, risk tags).
* Link:

  * devices to customers/accounts (some 1:1, some shared),
  * IPs to customers/devices/merchants in plausible patterns (e.g. a café IP shows up with many customers and a specific merchant).

**Outputs**

* `s4_devices_6A`
  – device table with device-level attributes.

* `s4_ips_6A`
  – IP table with network-level attributes.

* `s4_device_links_6A`
  – graph edges between devices, customers, accounts, merchants.

This is where shared-device/shared-IP structure that powers a lot of fraud patterns comes from.

---

## 6A.S5 — Static fraud posture & validation

**Purpose**

Assign **static risk roles** and sanity-check the entire entity graph before Layer-3 is allowed to use it.

**Inputs**

* All prior outputs from 6A:

  * `s1_customers_6A`, `s2_accounts_6A`, `s3_instruments_6A`, `s4_devices_6A`, `s4_device_links_6A`, etc.
* Fraud-role priors:

  * expected proportion of mules,
  * expected proportion of synthetic identities,
  * merchants that should be “risky” or collusive.

**Behaviour**

* Assign roles:

  * tag some customers/accounts as suspected mules,
  * tag some identities as synthetic,
  * mark some merchants as high-risk or collusive prospects (in a way that’s consistent with their graph position).
* Run structural checks:

  * degree distributions (devices per account, accounts per customer, etc.),
  * ensure there are no impossible patterns (e.g. zero devices for segments that should be device-heavy),
  * confirm population sizes and product mixes match priors.
* Summarise entity-level stats for a validation bundle.

**Outputs**

* `s5_fraud_roles_6A`
  – a surface of static roles per `customer_id`/`account_id`/`merchant_id`.

* `validation_bundle_6A` + `_passed.flag_6A`
  – Layer-3 bundle and PASS flag, analogous to what you’ve done in L1/L2:

  * index + SHA-256 for key 6A outputs,
  * high-level metrics (population sizes, mix, role proportions),
  * confirmation that the entity graph is structurally sound.

---

**After 6A**

At the end of Segment 6A you have:

* A **sealed entity graph** (customers, accounts, instruments, devices, IPs, merchants as counterparties).
* Static fraud roles (who *could* be involved in fraud, from a posture perspective).
* A validation bundle + PASS flag that 6B must respect (“no 6A PASS → no entity read”).

From there, **6B** can take the arrival stream from Layer-2 and:

* attach those arrivals to 6A’s entities,
* build flows,
* overlay fraud campaigns,
* and output transactions + labels,

without needing to reinvent or modify the entity world.
