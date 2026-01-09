# Authoring Guide — `class_shape_templates_5A` (5A.S2 base template library, class×channel)

## 0) Purpose

`class_shape_templates_5A` is an **optional** “split-out” artefact for 5A.S2 that holds the **base weekly-shape template library** (the same template objects you currently author inside `shape_library_5A.templates`). It exists if you want to decompose the monolithic shape policy into smaller, read-only tables (e.g., templates vs resolution vs zone/channel modifiers). S2 treats such tables as **read-only** and interprets them only via their `schema_ref` + 5A policies. 

If you keep `shape_library_5A` as the single authority, then `class_shape_templates_5A` is **redundant** and should not be used (or must be kept byte-for-byte consistent as a mechanically derived “extract”).

---

## 1) File identity (MUST)

* **Artefact ID:** `class_shape_templates_5A`
* **Path (recommended):** `config/layer2/5A/policy/class_shape_templates_5A.v1.yaml`
* **Schema anchor (recommended):** `schemas.5A.yaml#/policy/class_shape_templates_5A` *(permissive; this guide pins the real contract)*
* **Token-less posture:** no timestamps, no embedded digests (sealed by S0 inventory). 

---

## 2) Authority boundaries (MUST)

* This artefact is the **only authority** for the **template objects** it contains (their parameters, families, and IDs).
* It MUST NOT introduce per-merchant logic (no `merchant_id` anywhere).
* `demand_class` values MUST come from `merchant_class_policy_5A.demand_class_catalog` (fail closed otherwise).
* `channel_group` enum MUST match the pinned channel groups used by S1/S2 (`card_present|card_not_present|mixed`).

---

## 3) Required top-level structure (fields-strict)

Top-level YAML object MUST contain **exactly**:

1. `table_id` (MUST be `class_shape_templates_5A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `templates` (list; §4)
4. `notes` (string; optional; no timestamps)

No extra keys.

---

## 4) `templates` list (MUST)

### 4.1 Template entry shape (MUST match S2 template semantics)

Each entry MUST be the same logical object shape as `shape_library_5A.templates[*]`: 

* `template_id` (string; unique; pattern `^[a-z][a-z0-9_.-]{2,63}$`)
* `demand_class` (string; MUST exist in `merchant_class_policy_5A`)
* `channel_group` (enum: `card_present|card_not_present|mixed`)
* `shape_kind` (enum; v1 pinned: `daily_gaussian_mixture`)
* `dow_weights` (list of 7 numbers; all > 0)
* `daily_components` (list; ≥ 1)
* `baseline_floor` (number; ≥ 0)
* `power` (number; in `[0.6, 2.0]`)
* `notes` (string; non-empty; no timestamps)

`daily_components[*]` MUST be: 

* `kind` (MUST be `gaussian_peak`)
* `center_min` (int in `[0, 1439]`)
* `sigma_min` (number in `[20, 240]`)
* `amplitude` (number > 0)

### 4.2 Sorting (MUST)

Templates MUST be sorted lexicographically by:
`(demand_class, channel_group, template_id)`.

---

## 5) Non-toy realism floors (MUST; fail closed)

These mirror the “no sample policy” posture from the shape library guide:

* Minimum total templates: **≥ 40**
* For every `(demand_class, channel_group)` pair: **≥ 2 templates**
* Every `demand_class` from `merchant_class_policy_5A` must appear in at least one template entry.
* Most templates must be non-flat (authoring-time check): `max_bucket / min_bucket ≥ 1.5` after compilation + normalisation onto the grid.

*(If you want the exact constraint knobs embedded, keep them in `shape_library_5A.constraints`; this table is intentionally “just templates”.)*

---

## 6) Deterministic authoring algorithm (Codex-no-input)

1. Read `merchant_class_policy_5A` and extract the full demand class catalog.
2. Use the pinned channel groups: `card_present|card_not_present|mixed`.
3. For each `(demand_class, channel_group)` generate **≥ 3** variants by perturbing:

   * peak centers (minutes),
   * weekend/weekday weights,
   * peak widths (`sigma_min`),
   * mild power differences (`power`).
4. Ensure at least ~40 total templates across classes and channel groups.
5. Run authoring-time realism checks (compile + normalise on the grid used by the parameter pack) and **fail closed** if any floor is not met.

---

## 7) Minimal example snippet (NOT a real file)

```yaml
table_id: class_shape_templates_5A
version: v1.0.0

templates:
  - template_id: t.office_hours.card_present.a
    demand_class: office_hours
    channel_group: card_present
    shape_kind: daily_gaussian_mixture
    dow_weights: [1.35, 1.35, 1.35, 1.35, 1.25, 0.55, 0.50]
    daily_components:
      - { kind: gaussian_peak, center_min: 600, sigma_min: 90, amplitude: 1.0 }   # ~10:00
      - { kind: gaussian_peak, center_min: 870, sigma_min: 110, amplitude: 0.8 }  # ~14:30
    baseline_floor: 0.02
    power: 1.10
    notes: "Weekday daytime heavy; low weekend."

  - template_id: t.online_24h.card_not_present.a
    demand_class: online_24h
    channel_group: card_not_present
    shape_kind: daily_gaussian_mixture
    dow_weights: [1.00, 1.00, 1.00, 1.00, 1.00, 1.05, 1.05]
    daily_components:
      - { kind: gaussian_peak, center_min: 90,  sigma_min: 140, amplitude: 0.8 }  # night bias
      - { kind: gaussian_peak, center_min: 1230, sigma_min: 180, amplitude: 0.6 } # evening
    baseline_floor: 0.08
    power: 0.95
    notes: "24/7 with mild circadian structure; slightly higher weekend."
```

---

## 8) Acceptance checklist (MUST)

1. YAML parses; top-level keys exactly `{table_id, version, templates, notes?}`.
2. `table_id` matches exactly; `version` non-placeholder.
3. Every template entry is fields-strict and matches §4.1. 
4. `demand_class` values exist in `merchant_class_policy_5A`.
5. Coverage + non-toy floors (§5) pass.
6. Deterministic ordering of templates (§4.2) holds.
7. Token-less posture satisfied (no timestamps/digests). 


