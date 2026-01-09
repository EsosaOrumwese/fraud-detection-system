# Authoring Guide — `arrival_routing_policy_5B` (5B.S4 routing: physical vs virtual, and router interface)

## 0) Purpose

`arrival_routing_policy_5B` is the **sealed authority** for 5B.S4 routing decisions. It pins:

* when an arrival is routed to **physical** sites vs **virtual** edges (per merchant / zone / scenario),
* how S4 constructs the **routing context keys** expected by Layer-1 routing artefacts (2B physical router, 3B virtual fabric),
* which overrides are permitted (v1: almost none),
* and fail-closed rules for missing upstream routing inputs.

This prevents S4 from inventing “routing logic” beyond what 2B/3B already define.

---

## 1) File identity (MUST)

* **Artefact ID:** `arrival_routing_policy_5B`
* **Path:** `config/layer2/5B/arrival_routing_policy_5B.yaml`
* **Schema anchor:** `schemas.5B.yaml#/config/arrival_routing_policy_5B` *(permissive; this guide pins real structure)*
* **Token-less posture:** do **not** embed digests/timestamps in-file (S0 sealing inventory records digests).

---

## 2) Pinned routing semantics (decision-free)

### 2.1 Physical vs virtual decision (v1)

S4 MUST determine routing mode for each merchant **without randomness**:

* Use `virtual_mode` from 3B (`NON_VIRTUAL`, `HYBRID`, `VIRTUAL_ONLY`), sealed in S0.

Routing mode mapping (v1 pinned):

* `NON_VIRTUAL`  → route **physical** only
* `VIRTUAL_ONLY` → route **virtual** only
* `HYBRID`       → route per-arrival using deterministic **hybrid split** (see §2.2)

If 3B virtual classification is not sealed (shouldn’t be in 5B) → FAIL CLOSED.

### 2.2 Hybrid split (deterministic; no extra RNG)

For `HYBRID` merchants, each arrival chooses physical vs virtual using **one existing RNG draw** (no new RNG family):

v1 pinned: use the **first uniform** of `arrival_site_pick` event (already budgeted at 2 u64) as the hybrid coin flip.
For HYBRID merchants, S4 MUST emit the `arrival_site_pick` RNG event for every arrival **before** applying the coin flip, even if the outcome is virtual (the second u64 may be unused when virtual).

* `u_hybrid = first_u` from the `arrival_site_pick` draw
* compare to `p_virtual_hybrid`:

  * if `u_hybrid < p_virtual_hybrid` → virtual
  * else → physical

This avoids adding a new RNG event.

### 2.3 Physical routing interface (2B)

For physical arrivals, S4 must route using the **2B alias router surfaces**:

* Required upstream artefacts (sealed):

  * `s2_alias_blob` + `s2_alias_index`
  * `s4_group_weights` (if 2B uses tz-group routing)
  * any `route_rng_policy_v1` / day-effect policy required by 2B’s router semantics

Pinned interface keys (v1):

* `router_key = (merchant_id, zone_representation, bucket_index)`
  where `zone_representation` is `tzid` in v1 5B.
* S4 MUST draw:

  * group selection (if enabled) then site alias pick
    using the `arrival_site_pick` event’s 2 uniforms.

### 2.4 Virtual routing interface (3B)

For virtual arrivals, S4 must route using **3B virtual edge alias surfaces**:

* Required upstream artefacts (sealed):

  * `edge_alias_blob_3B` + `edge_alias_index_3B`
  * `virtual_routing_policy_3B` (tells how to interpret settlement vs operational semantics)
  * `cdn_key_digest` (if used as key material / sanity check)

Pinned interface keys (v1):

* `edge_key = (merchant_id, bucket_index)`
* S4 MUST pick an edge using the `arrival_edge_pick` event’s 1 uniform.

---

## 3) Required policy structure (fields-strict by this guide)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `arrival_routing_policy_5B`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `virtual_mode_source` (MUST be `virtual_classification_3B`)
4. `hybrid_policy` (object; §3.1)
5. `physical_router` (object; §3.2)
6. `virtual_router` (object; §3.3)
7. `fail_closed_rules` (object; §3.4)
8. `realism_floors` (object; §4)

### 3.1 `hybrid_policy` (MUST)

```yaml
hybrid_policy:
  p_virtual_hybrid: 0.35
  coin_source: arrival_site_pick.first_uniform
```

Rules:

* `0.05 ≤ p_virtual_hybrid ≤ 0.80` (non-toy)
* coin_source pinned exactly as above.

### 3.2 `physical_router` (MUST)

```yaml
physical_router:
  zone_representation: tzid
  router_key_fields: [merchant_id, tzid, bucket_index]
  use_group_weights: true
  rng_source: arrival_site_pick
  draws_required_u64: 2
```

### 3.3 `virtual_router` (MUST)

```yaml
virtual_router:
  edge_key_fields: [merchant_id, bucket_index]
  rng_source: arrival_edge_pick
  draws_required_u64: 1
  require_virtual_routing_policy_3B: true
```

### 3.4 `fail_closed_rules` (MUST)

```yaml
fail_closed_rules:
  require_2B_pass: true
  require_3B_pass_for_virtual: true
  require_site_alias_tables_for_physical: true
  require_edge_alias_tables_for_virtual: true
  forbid_missing_router_rows: true
  require_site_pick_event_for_hybrid_coin: true
```

Meaning:

* If an arrival requires physical routing and the merchant has no alias rows → abort.
* If virtual routing required and merchant has no edge alias rows → abort.

---

## 4) Realism floors (MUST; prevents toy routing)

Codex MUST reject authoring if any fail:

* `p_virtual_hybrid` within `[0.05, 0.80]`
* Hybrid uses existing RNG draw (`arrival_site_pick.first_uniform`), no extra RNG families
* Physical router requires group weights (unless you explicitly set `use_group_weights:false` and prove 2B router doesn’t need them)
* Fail-closed rules require 2B/3B PASS gates (no silent routing without validated inputs)

---

## 5) Recommended v1 policy file (copy/paste baseline)

```yaml
policy_id: arrival_routing_policy_5B
version: v1.0.0

virtual_mode_source: virtual_classification_3B

hybrid_policy:
  p_virtual_hybrid: 0.35
  coin_source: arrival_site_pick.first_uniform

physical_router:
  zone_representation: tzid
  router_key_fields: [merchant_id, tzid, bucket_index]
  use_group_weights: true
  rng_source: arrival_site_pick
  draws_required_u64: 2

virtual_router:
  edge_key_fields: [merchant_id, bucket_index]
  rng_source: arrival_edge_pick
  draws_required_u64: 1
  require_virtual_routing_policy_3B: true

fail_closed_rules:
  require_2B_pass: true
  require_3B_pass_for_virtual: true
  require_site_alias_tables_for_physical: true
  require_edge_alias_tables_for_virtual: true
  forbid_missing_router_rows: true
  require_site_pick_event_for_hybrid_coin: true

realism_floors:
  hybrid_p_virtual_bounds: [0.05, 0.80]
  require_existing_rng_coin: true
  require_pass_gates: true
```

---

## 6) Acceptance checklist (Codex MUST enforce)

1. YAML parses; keys exactly as §3; `policy_id` correct; `version` non-placeholder.
2. `virtual_mode_source` pinned to 3B classification.
3. Hybrid split uses `arrival_site_pick.first_uniform` (no extra RNG).
4. RNG draw requirements align with `arrival_rng_policy_5B` budgets.
5. Fail-closed rules enforce PASS gates + missing-row abort.
6. For HYBRID, `arrival_site_pick` is emitted for the coin flip even when the outcome is virtual.
7. No timestamps / in-file digests.

---

## Placeholder resolution (MUST)

- Replace `policy_id` and `version` with final identifiers.
- Set `hybrid_policy.p_virtual_hybrid` and confirm `coin_source` matches `arrival_site_pick.first_uniform`.
- Set `physical_router` and `virtual_router` key fields and `fail_closed_rules` to final values.

