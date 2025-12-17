```
        LAYER 1 · SEGMENT 3A — STATE S1 (MIXTURE POLICY & ESCALATION QUEUE)  [NO RNG]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3A @ data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json
      · proves: 3A.S0 completed for this manifest_fingerprint
      · binds: {parameter_hash, manifest_fingerprint, seed} for 3A
      · records: upstream_gates.{segment_1A,segment_1B,segment_2A}.status, catalogue_versions, sealed_policy_set
    - sealed_inputs_3A @ data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet
      · inventory of all artefacts 3A is allowed to read for this manifest_fingerprint
      · every artefact S1 reads MUST appear here with matching {logical_id, path, sha256_hex}

[Schema+Dict]
    - schemas.layer1.yaml                 (primitive types: id64, iso2, hex64, uint64; basic validation)
    - schemas.ingress.layer1.yaml         (shapes for ISO / tz-world references if used)
    - schemas.1A.yaml                     (shape for outlet_catalogue)
    - schemas.3A.yaml                     (anchors for s1_escalation_queue, s0_gate_receipt_3A, sealed_inputs_3A, zone_mixture_policy_3A)
    - dataset_dictionary.layer1.{1A,3A}.yaml
    - artefact_registry_{1A,3A}.yaml

[Upstream data-plane & references (must be listed in sealed_inputs_3A)]
    - outlet_catalogue
        · producer: 1A
        · scope: seed={seed} / fingerprint={manifest_fingerprint}
        · PK: (merchant_id, legal_country_iso, site_order)
        · S1’s allowed use: derive site_count(m,c) by grouping; MUST NOT mutate or re-emit
    - iso3166_canonical_2024
        · canonical country list; used to validate legal_country_iso
    - tz_world_2025a
        · ingress tz geometry; used to derive Z(c) (tzid universe per country) and zone_count_country(c)
    - (optional) tz_timetable_cache / country_tz_universe
        · if sealed, MAY be used to cross-check tzid universes but not to override tz_world

[3A mixture policy (sealed configuration)]
    - zone_mixture_policy_3A
        · owner_segment="3A", role="zone_mixture_policy"
        · schema_ref: schemas.3A.yaml#/policy/zone_mixture_policy_3A
        · defines thresholds and rules over:
            · site_count(m,c),
            · zone_count_country(c),
            · and any explicitly declared extra features
        · S1 MUST treat this as the **only authority** on monolithic vs escalated classification

[Numeric & RNG posture]
    - S1 is **RNG-free**:
        · MUST NOT consume any Philox stream or other RNG
        · MUST NOT depend on wall-clock time
    - Numeric:
        · integer counts only (site_count, zone_count_country); any real-valued logic is policy-defined but deterministic
    - Partitioning & identity:
        · S1 output partitions: [seed, manifest_fingerprint]
        · PK: (merchant_id, legal_country_iso) within each partition
        · path↔embed equality: embedded seed/manifest_fingerprint MUST equal path tokens


----------------------------------------------------------------------
DAG — 3A.S1 (mixture policy → escalation queue over merchant×country)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S1.1) Resolve S0 gate & ensure upstream segments are PASS
                    - Resolve, via the 3A dataset dictionary:
                        · s0_gate_receipt_3A@fingerprint={manifest_fingerprint}
                        · sealed_inputs_3A@fingerprint={manifest_fingerprint}
                    - Validate both against `schemas.3A.yaml#/validation/s0_gate_receipt_3A`
                      and `#/validation/sealed_inputs_3A`.
                    - From `s0_gate_receipt_3A.upstream_gates`:
                        · assert segment_1A.status == "PASS"
                        · assert segment_1B.status == "PASS"
                        · assert segment_2A.status == "PASS"
                    - If any upstream segment is not PASS → **precondition failure**; S1 MUST NOT run.
                    - Fix run identity:
                        · {parameter_hash, manifest_fingerprint, seed} ← S0 receipt
                        · S1 embeds these into `s1_escalation_queue` but does not branch on them.

[S0 Gate & Identity],
[Schema+Dict],
sealed_inputs_3A
                ->  (S1.2) Resolve gated inputs & verify sealed-input integrity
                    - For each artefact S1 plans to read:
                        · `outlet_catalogue`,
                        · `iso3166_canonical_2024`,
                        · `tz_world_2025a`,
                        · `zone_mixture_policy_3A`,
                        · (optional) `tz_timetable_cache` / `country_tz_universe`,
                      S1 MUST:
                        · locate at least one matching row in `sealed_inputs_3A`
                          with `{logical_id, path, schema_ref}`,
                        · recompute SHA-256 over the concrete artefact bytes,
                        · assert equality with `sha256_hex` in `sealed_inputs_3A`.
                    - If any required artefact is missing from `sealed_inputs_3A` or digest mismatch occurs:
                        · treat as precondition failure; S1 MUST fail and MUST NOT continue.
                    - Resolve concrete paths and schema_refs via the catalogue (no hard-coded paths).

[Schema+Dict],
zone_mixture_policy_3A
                ->  (S1.3) Load & validate mixture policy
                    - Resolve `zone_mixture_policy_3A` via dictionary/registry using ID from sealed_inputs_3A.
                    - Validate content against `schemas.3A.yaml#/policy/zone_mixture_policy_3A`.
                    - Extract:
                        · mixture_policy_id       (logical ID, e.g. "zone_mixture_policy_3A"),
                        · mixture_policy_version  (version string, e.g. semver or digest-based).
                    - S1 MUST write the same mixture_policy_id/version into every `s1_escalation_queue` row
                      for this {parameter_hash, manifest_fingerprint}.
                    - Policy authority:
                        · defines the decision function f(m,c) → (is_escalated, decision_reason[, optional fields]),
                        · S1 MUST NOT override or partially apply this policy.

[Schema+Dict],
outlet_catalogue,
iso3166_canonical_2024
                ->  (S1.4) Derive merchant×country domain D and site_count(m,c)
                    - Resolve `outlet_catalogue@seed={seed}/fingerprint={manifest_fingerprint}` via dictionary.
                    - Validate its schema via `schemas.1A.yaml`.
                    - Domain:
                        · D_1A = { (merchant_id=m, legal_country_iso=c) |
                                    COUNT rows in outlet_catalogue with (m,c) ≥ 1 }.
                    - Grouping:
                        · For each (m,c) in D_1A:
                              site_count(m,c) = COUNT(*) in outlet_catalogue with that pair.
                        · site_count(m,c) MUST be ≥ 1.
                    - ISO validation:
                        · Every distinct `legal_country_iso` in D_1A MUST appear in `iso3166_canonical_2024`.
                        · Any non-canonical country code is an error; S1 MUST fail.

[Schema+Dict],
tz_world_2025a,
(optional) tz_timetable_cache
                ->  (S1.5) Derive zone universe Z(c) & zone_count_country(c)
                    - For each `legal_country_iso = c` present in D_1A:
                        · compute zone universe:
                              Z(c) = { tzid | tz_polygon(tzid) ∩ country_polygon(c) ≠ ∅ } from `tz_world_2025a`.
                        · zone_count_country(c) = |Z(c)|; an integer ≥ 0.
                    - Optional cross-check:
                        · if `tz_timetable_cache` or a `country_tz_universe` dataset is sealed,
                          S1 MAY assert that every tzid in Z(c) also appears in the cache universe.
                    - S1 MUST treat tz-world / tz-universe as read-only:
                        · MUST NOT add/remove tzids, only observe and count them.

[site_count(m,c) from S1.4],
[zone_count_country(c) from S1.5],
zone_mixture_policy_3A
                ->  (S1.6) Build decision context per (m,c)
                    - Construct an in-memory decision frame over the domain D_1A:
                        · for each (m,c):
                              seed,
                              manifest_fingerprint,
                              merchant_id = m,
                              legal_country_iso = c,
                              site_count(m,c),
                              zone_count_country(c),
                              plus any additional policy-governed features required by the mixture policy
                              (e.g. eligible_for_escalation, dominant_zone_share_bucket, notes).
                    - These fields form the **only** input S1 may pass into the mixture decision function
                      (no per-site tzids, no geometry, no 2B artefacts).

decision frame (m,c),
zone_mixture_policy_3A
                ->  (S1.7) Apply mixture policy deterministically
                    - For each (m,c) in D_1A:
                        · evaluate the policy’s decision function:
                              (is_escalated(m,c), decision_reason(m,c), optional_diag(m,c))
                              = f(policy, site_count(m,c), zone_count_country(c), other allowed features).
                        · Requirements:
                              - f MUST be deterministic given its inputs,
                              - decisions MUST NOT use RNG or wall-clock,
                              - `decision_reason` MUST be one of the policy’s enum codes.
                    - S1 MUST ensure:
                        · exactly one decision per (m,c),
                        · no ambiguous or conflicting decisions.
                    - These decisions are the **exclusive authority** for escalation in 3A:
                        · later states (S2–S4) MUST NOT re-evaluate f or change is_escalated/decision_reason.

decision outputs (m,c),
site_count,
zone_count_country,
mixture_policy_id/version,
[identity triple]
                ->  (S1.8) Assemble `s1_escalation_queue` rows
                    - For each (m,c) in D_1A:
                        · emit one row with:
                              seed,
                              manifest_fingerprint,
                              merchant_id,
                              legal_country_iso,
                              site_count,
                              zone_count_country,
                              is_escalated,
                              decision_reason,
                              mixture_policy_id,
                              mixture_policy_version,
                              optional diagnostic fields under names allowed by the schema.
                    - Writer sort:
                        · sort rows by (merchant_id ASC, legal_country_iso ASC) before writing.
                    - Domain & PK constraints:
                        · there MUST be exactly one row per (m,c) ∈ D_1A,
                        · there MUST be no rows for pairs not present in outlet_catalogue,
                        · PK within partition = (merchant_id, legal_country_iso).

[S1.8 rows],
[Schema+Dict]
                ->  (S1.9) Write `s1_escalation_queue` & enforce immutability
                    - Target path via dictionary:
                        · data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/...
                    - Validate the in-memory table against `schemas.3A.yaml#/plan/s1_escalation_queue`
                      (fields-strict, partition keys, PK).
                    - Immutability & idempotence:
                        · if partition does not exist → write using staging → fsync → atomic move.
                        · if partition exists:
                              - read existing dataset, normalise (schema + sort), and compare row-by-row;
                              - if byte-identical → treat as idempotent re-run (no-op),
                              - if any difference → FAIL with immutability violation; MUST NOT overwrite.
                    - Path↔embed equality:
                        · `seed` and `manifest_fingerprint` columns MUST equal their path tokens.

Downstream touchpoints
----------------------
- **3A.S2 — Country-zone priors:**
    - MUST use `s1_escalation_queue` only for:
        · domain D of merchant×country pairs,
        · site_count(m,c) as the total to be conserved,
        · is_escalated flags to define D_esc.
    - MUST NOT re-derive escalation decisions independently of S1.
- **3A.S3 — Zone share sampling:**
    - MUST derive its Dirichlet worklist as:
          D_esc = { (m,c) ∈ D | is_escalated(m,c) = true }.
    - MUST NOT draw zone shares for non-escalated pairs.
- **3A.S4 — Integer zone allocation:**
    - Uses `site_count(m,c)` and `is_escalated` exactly as written; MUST NOT invent new counts or escalation decisions.
- **3A.S6/S7 validation:**
    - MUST treat `s1_escalation_queue` as truth when checking:
        · D_S1 = D_1A,
        · zone_count_country(c) vs tz-world,
        · mixture policy replay (decisions consistent with policy),
        · that only escalated pairs receive zone shares and counts.
- **Cross-segment consumers (2B, tooling):**
    - MUST NOT read `s1_escalation_queue` as a public egress contract without additional governance; its authority is scoped to 3A.
```