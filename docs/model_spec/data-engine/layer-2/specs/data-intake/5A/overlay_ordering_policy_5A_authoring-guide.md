# Authoring Guide — `overlay_ordering_policy_5A` (5A.S4 precedence / conflict resolution for overlapping overlays)

## 0) Purpose

`overlay_ordering_policy_5A` is an **optional but important** companion to `scenario_overlay_policy_5A`. It exists to make overlap handling **explicit and realistic**, e.g. “outages override all uplifts,” and to prevent “multiple conflicting rules with no well-defined precedence.”

It does **not** define event→factor math (that’s `scenario_overlay_policy_5A`). Instead it defines:

* **which events are allowed to “stack” vs be suppressed**,
* **within-type aggregation** when multiple events of the same type apply, and
* **type-level precedence rules** (layering / masking).

S4 may implement multiplicative combination *or* layered precedence **as defined by policy**.

---

## 1) File identity (MUST)

* **Artefact ID:** `overlay_ordering_policy_5A`
* **Path:** `config/layer2/5A/scenario/overlay_ordering_policy_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/policy/overlay_ordering_policy_5A` *(guide pins the real contract)*
* **Token-less posture:** no timestamps / digests / host metadata in-file (S0 sealing inventory is authoritative).

---

## 2) Authority boundaries (MUST)

This policy MUST NOT:

* change the event vocabulary, shape kinds, amplitude bounds, or clamp range (`F_min/F_max`) — those live in `scenario_overlay_policy_5A`.
* invent new event types not present in the overlay vocab.

This policy MAY:

* change **how overlapping active events are combined** (e.g., suppress some types when a higher-priority type is active),
* define **within-type aggregation** (e.g., multiple CAMPAIGNs → take max effect),
* define deterministic **type priority** / masking rules.

If `overlay_ordering_policy_5A` is present, S4 MUST treat it as part of the “related configs” that influence precedence/layering.

---

## 3) Pinned v1 semantics (decision-free)

### 3.1 Operating unit

All rules are evaluated **per domain point and horizon bucket** `(m,z[,ch],h)` over the active event set `EVENTS[m,z[,ch],h]`.

### 3.2 Precedence is implemented as “masking”, not ad-hoc math

v1 expresses precedence only by:

1. selecting/aggregating events into **one factor per event_type**, then
2. applying deterministic **masking rules** that can neutralize or cap some type-factors, then
3. letting the overlay policy’s combination law (typically product + clamp) do the final combine.

This keeps the system deterministic and avoids “hidden tweaks” in S4.

### 3.3 Allowed masking operators (v1)

Masking can only use these commutative, deterministic transforms:

* `NEUTRALIZE`: set factor to `1.0`
* `CAP_AT_ONE`: replace factor with `min(f, 1.0)` (disallow uplifts, allow reductions)
* `FLOOR_AT_ONE`: replace factor with `max(f, 1.0)` (disallow reductions, allow uplifts)

No other transforms in v1.

---

## 4) Required payload shape (fields-strict)

Top-level YAML keys MUST be exactly:

1. `policy_id` (MUST be `overlay_ordering_policy_5A`)
2. `version` (e.g. `v1.0.0`)
3. `type_priority` (object)
4. `within_type_aggregation` (object)
5. `masking_rules` (list)
6. `notes` (string; optional)

No extra keys.

---

## 5) `type_priority` (MUST)

Defines a total order over the overlay policy’s event types.

### Required keys

* `priority` : mapping `event_type -> int` (higher = stronger precedence)
* `require_all_vocab_types_listed` : bool (MUST be `true` in v1)

### v1 recommended priorities (realistic defaults)

* `OUTAGE: 100` (strongest)
* `STRESS: 80`
* `CAMPAIGN: 60`
* `PAYDAY: 40`
* `HOLIDAY: 20`

Rationale: outages dominate, stress dominates marketing, marketing dominates calendar uplifts, etc. (You can still permit stacking via masking rules; priority mainly drives which rules trigger first.)

---

## 6) `within_type_aggregation` (MUST)

When multiple events of the same type are active for `(m,z[,ch],h)`, aggregate them into a single type-factor `F_type`.

### Required keys

For each event type in vocab, define:

* `mode`: one of `{PRODUCT, MAX, MIN}`
* `selection`: one of `{ALL, MOST_SPECIFIC_ONLY}`

#### 6.1 Selection: MOST_SPECIFIC_ONLY (recommended)

To avoid double-counting across scopes, v1 recommends:

* `MOST_SPECIFIC_ONLY` for **all** types.

Specificity ordering (pinned for v1; S4 must implement exactly):

1. `merchant_id` present
2. `demand_class` present
3. `tzid` present
4. `country_iso` present
5. `global` only

Compute a “specificity vector” as the 5-tuple of booleans above; keep only events with maximal vector under lexicographic order.

#### 6.2 Aggregation modes (recommended defaults)

* `OUTAGE`: `MIN` (most severe outage wins)
* `CAMPAIGN`: `MAX` (strongest campaign wins; avoids unrealistic compound uplifts)
* `STRESS`: `MAX`
* `PAYDAY`: `MAX` (if multiple payday definitions collide, strongest wins)
* `HOLIDAY`: `MIN` (most suppressive holiday wins)

All modes are commutative and deterministic.

---

## 7) `masking_rules` (MUST)

A list of rules applied after within-type aggregation.

Each rule object MUST be fields-strict and contain:

* `name` (string)
* `when_active_types` (list of event_type) — trigger condition: aggregated factor exists (i.e., at least one matching event survived selection)
* `apply` (list of actions), each action:

  * `target_types` (list of event_type)
  * `operator` (one of `NEUTRALIZE | CAP_AT_ONE | FLOOR_AT_ONE`)

### v1 required rule (non-negotiable realism rule)

**Outage suppresses uplifts**:

* When `OUTAGE` is active, apply `CAP_AT_ONE` to `{CAMPAIGN, PAYDAY, STRESS}`.
* Do **not** cap `HOLIDAY` (allow further reductions).

This matches the “outages override everything” intent without requiring non-commutative logic.

### v1 recommended extra rule

**Stress suppresses marketing uplift** (optional but sensible):

* When `STRESS` is active, apply `CAP_AT_ONE` to `{CAMPAIGN}`.

---

## 8) Deterministic evaluation algorithm (S4 MUST follow)

For each `(m,z[,ch],h)`:

1. Compute per-event factors `f_e` using `scenario_overlay_policy_5A`.
2. Group events by `event_type`.
3. For each type:

   * apply `selection` (recommended: MOST_SPECIFIC_ONLY),
   * aggregate selected `f_e` using the type’s `mode` → `F_type`.
4. Apply `masking_rules` in **descending trigger priority** (use `type_priority` to order triggers; ties → stable alphabetical by `name`).
5. Multiply all remaining `F_type` values (including masked ones).
6. Apply clamp using the overlay policy’s `[min_factor,max_factor]` and any documented shutdown exception (if applicable).

If masking produces contradictory behavior (e.g. targets include trigger type), treat as policy-invalid and fail closed.

---

## 9) Recommended v1 example (copy/paste)

```yaml
policy_id: overlay_ordering_policy_5A
version: v1.0.0

type_priority:
  require_all_vocab_types_listed: true
  priority:
    OUTAGE: 100
    STRESS: 80
    CAMPAIGN: 60
    PAYDAY: 40
    HOLIDAY: 20

within_type_aggregation:
  OUTAGE:   { selection: MOST_SPECIFIC_ONLY, mode: MIN }
  STRESS:   { selection: MOST_SPECIFIC_ONLY, mode: MAX }
  CAMPAIGN: { selection: MOST_SPECIFIC_ONLY, mode: MAX }
  PAYDAY:   { selection: MOST_SPECIFIC_ONLY, mode: MAX }
  HOLIDAY:  { selection: MOST_SPECIFIC_ONLY, mode: MIN }

masking_rules:
  - name: outage_suppresses_uplifts
    when_active_types: [OUTAGE]
    apply:
      - target_types: [CAMPAIGN, PAYDAY, STRESS]
        operator: CAP_AT_ONE

  - name: stress_suppresses_campaign
    when_active_types: [STRESS]
    apply:
      - target_types: [CAMPAIGN]
        operator: CAP_AT_ONE

notes: "Defines precedence/masking for overlapping S4 overlays; event->factor math and clamps live in scenario_overlay_policy_5A."
```

---

## 10) Acceptance checklist (MUST)

1. YAML parses; no duplicate keys.
2. Top-level keys exactly as required; no extras.
3. `policy_id` matches exactly.
4. Every event type in `scenario_overlay_policy_5A.event_types` is present in:

   * `type_priority.priority`, and
   * `within_type_aggregation`.
5. All `mode` and `selection` enums are valid.
6. Masking operators are valid and do not target undefined event types.
7. At least the **outage suppresses uplifts** rule is present.
8. Token-less posture satisfied.

