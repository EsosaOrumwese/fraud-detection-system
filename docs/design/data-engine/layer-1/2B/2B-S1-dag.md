```
        LAYER 1 · SEGMENT 2B — STATE S1 (PER-MERCHANT WEIGHT FREEZING)  [NO RNG]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2B @ data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 1B PASS gate verified for this manifest_fingerprint (via 1B bundle + _passed.flag)
      · binds: { seed, manifest_fingerprint, parameter_hash } for this 2B run
      · records: catalogue_resolution (dictionary/registry versions), determinism_receipt (engine + policy digests)
    - sealed_inputs_v1 @ data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/…
      · inventory of all artefacts S0 authorised for 2B under this fingerprint
      · S1 MUST treat its read set as a subset of this inventory (no new inputs)

[Schema+Dict]
    - schemas.layer1.yaml                 (layer-wide primitives + numeric/RNG/bundle index law)
    - schemas.1B.yaml                     (1B egress: site_locations shape)
    - schemas.2B.yaml                     (2B shapes incl. s1_site_weights, alias_layout_policy_v1)
    - schemas.2A.yaml                     (2A shapes for optional pins, if sealed)
    - schemas.ingress.layer1.yaml         (generic ingress primitives)
    - dataset_dictionary.layer1.1B.yaml   (IDs/paths/partitions for 1B, incl. site_locations)
    - dataset_dictionary.layer1.2A.yaml   (IDs/paths/partitions for optional pins: site_timezones, tz_timetable_cache)
    - dataset_dictionary.layer1.2B.yaml   (IDs/paths/partitions for s1_site_weights and policies)
    - artefact_registry_2B.yaml           (existence/licence/retention; non-authoritative for shape)

[Upstream egress: sites universe]
    - site_locations
        · producer: 1B
        · identity: `seed={seed} / fingerprint={manifest_fingerprint}`
        · PK: [merchant_id, legal_country_iso, site_order]
        · role here: defines the universe of sites per merchant; S1 SHALL NOT mutate keys

[Policy · alias layout & weighting]
    - alias_layout_policy_v1
        · declares: weight_source (column or deterministic transform),
                    floor_spec (absolute/relative floor, zero-mass fallback),
                    normalisation_epsilon = ε,
                    quantised_bits (b) and quantisation_epsilon = ε_q,
                    required provenance flags (weight_source, quantised_bits, floor_applied)
        · also constrains: allowed transforms, numeric tolerances, and bit-depth for S1→S2 handoff

[Optional pins from 2A] (all-or-none; read-only, not used by the core transform)
    - site_timezones         @ seed={seed} / fingerprint={manifest_fingerprint}
    - tz_timetable_cache     @ fingerprint={manifest_fingerprint}
      · If S0 sealed both → S1 MAY resolve both (for coherence/CI only).
      · If exactly one is present → S1 logs a WARN and proceeds as if neither were present.

[Numeric & RNG posture]
    - Numeric law:
        · IEEE-754 binary64, round-to-nearest-even, no FMA/FTZ/DAZ for decision maths
        · all sums are **serial reductions** in PK order (no parallel or reordered summations)
    - RNG law:
        · S1 is **RNG-free** — it consumes no Philox events, but must respect the RNG policy sealed at S0
          for downstream states (S2–S6).


----------------------------------------------------------------------
DAG — 2B.S1 (site_locations → frozen per-merchant probability law)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S1.1) Trust S0, fix run identity & environment
                    - Load s0_gate_receipt_2B for this manifest_fingerprint:
                        · verify schema, signature fields, and that it references this {seed, manifest_fingerprint}.
                        · treat s0_gate_receipt_2B as the sole attestation that 1B PASSED for this fingerprint.
                    - Load sealed_inputs_v1 for this manifest_fingerprint:
                        · build an in-memory set of sealed asset IDs + partitions + digests.
                    - Fix run identity:
                        · {seed, manifest_fingerprint} is fixed for all of S1,
                        · parameter_hash is carried through from S0 but NOT used as a partition key.
                    - Discover canonical created_utc:
                        · S1 SHALL echo S0.verified_at_utc into every s1_site_weights row.
                    - Confirm posture:
                        · Dictionary-only resolution (no literal paths),
                        · S1 is RNG-free and SHALL NOT re-hash upstream bundles.

[S0 Gate & Identity],
[Schema+Dict],
[Upstream egress: sites universe],
[Policy · alias layout & weighting],
[Optional pins from 2A]
                ->  (S1.2) Resolve inputs & basic sanity
                    - Resolve, via Dataset Dictionary only:
                        · site_locations @ data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
                        · alias_layout_policy_v1 @ contracts/policy/2B/alias_layout_policy_v1.json
                        · optional pins site_timezones/tz_timetable_cache iff BOTH are present in sealed_inputs_v1.
                    - Enforce **subset-of-S0**:
                        · every resolved artefact MUST appear in sealed_inputs_v1 for this fingerprint.
                    - Validate alias_layout_policy_v1:
                        · required keys present: weight_source, floor_spec, normalisation_epsilon,
                                                 quantised_bits, quantisation_epsilon, provenance flags.
                        · quantised_bits (b) is a positive integer; ε, ε_q > 0 and finite.
                    - Check site_locations:
                        · required columns for weight_source and any policy-declared transform exist,
                        · PK [merchant_id, legal_country_iso, site_order] is well-formed and unique within the selection.
                    - Note: optional pins, if resolved, are NOT used in the core weighting algorithm; they are
                      only available for possible CI/coherence checks.

[Schema+Dict],
site_locations
                ->  (S1.3) Group by merchant & fix processing order
                    - Derive merchant groups:
                        · group site_locations rows by merchant_id (implicitly carrying legal_country_iso, site_order).
                    - Within each merchant group:
                        · process rows strictly in PK order [merchant_id, legal_country_iso, site_order].
                    - All reductions (sums, max) and tie-breaks later in S1 SHALL use this PK order only.
                    - Edge cases:
                        · merchants with a single site are still valid (they get a degenerate 1-point distribution),
                        · merchants with **no** rows in site_locations must not appear in s1_site_weights.

[Policy · alias layout & weighting],
site_locations (grouped per merchant)
                ->  (S1.4) Base weight extraction (deterministic, per merchant)
                    - For each merchant group:
                        · construct base series w_i from the policy’s weight_source:
                            - either directly from a named column in site_locations, or
                            - from a deterministic pure function of sealed columns as described in the policy.
                        · Enforce domain:
                            - each w_i is finite and ≥ 0 (no NaN/±Inf/negative),
                            - Abort if any row violates this.
                        · Compute W0 = Σ_i w_i using serial addition in PK order.
                    - W0 is used to characterise the merchant, but S1 does NOT introduce RNG or inference here.

[Policy · alias layout & weighting],
(base weights w_i per merchant)
                ->  (S1.5) Apply floor/cap & zero-effective-mass fallback
                    - For each merchant:
                        · derive u_i from w_i according to floor_spec:
                            - e.g. absolute floor:  u_i = max(w_i, f_abs),
                               relative floor:     u_i = max(w_i, f_rel · max_j w_j),
                               optional caps:      u_i = min(u_i, c_abs|c_rel),
                               exact law defined by alias_layout_policy_v1.
                        · Set floor_applied = true for any row where the floor changed w_i.
                        · Compute U0 = Σ_i u_i in serial order.
                        · If U0 > 0:
                            - proceed with u_i as-is.
                        · If U0 == 0 (zero-effective-mass case):
                            - invoke the policy-declared **zero-mass fallback** for this merchant to obtain
                              a strictly positive effective series (e.g. uniform positive u_i),
                            - set floor_applied = true for all rows for this merchant.
                    - No randomness is permitted in floor/cap or fallback; all behaviour is policy + data deterministic.

[Policy · alias layout & weighting],
(effective u_i per merchant)
                ->  (S1.6) Per-merchant normalisation (real weights p_i)
                    - For each merchant:
                        · compute Σ_i u_i again as the normalisation denominator (serial reduction).
                        · define p_i = u_i / Σ_i u_i (binary64).
                        · Enforce total mass:
                            - |(Σ_i p_i) − 1| ≤ ε (normalisation_epsilon from policy),
                            - Abort if this tolerance is violated.
                        - Clamp tiny negatives:
                            - if −ε ≤ p_i < 0 for some i, clamp to 0 and mark floor_applied = true,
                            - if p_i < −ε for any i, Abort (invalid numeric behaviour).
                        · If any clamping occurs:
                            - recompute p_i with a single re-normalisation pass to restore Σ_i p_i ≈ 1 within ε.
                    - Result: per-merchant real weights p_i forming a valid probability distribution.

[Policy · alias layout & weighting],
(real weights p_i per merchant)
                ->  (S1.7) Quantisation onto policy grid (integer mass m_i)
                    - Let b = policy.quantised_bits (≥ 1), and define grid size G = 2^b.
                    - For each merchant:
                        · compute m_i* = p_i · G in binary64.
                        · compute base integers via round-half-to-even:
                            - m_i = round_half_to_even(m_i*).
                        · Let Δ = G − Σ_i m_i.
                            - If Δ = 0: keep m_i.
                            - If Δ > 0 (deficit):
                                · add +1 to the Δ rows with **largest** fractional remainders of (m_i* − floor(m_i*)).
                            - If Δ < 0 (surplus):
                                · subtract 1 from the |Δ| rows with **smallest** fractional remainders.
                            - Ties in remainders are broken deterministically by PK order.
                        · After adjustment, enforce Σ_i m_i = G exactly.
                        · Decode back to p̂_i = m_i / G (in binary64).
                        · Enforce quantisation tolerance:
                            - |p̂_i − p_i| ≤ ε_q (policy.quantisation_epsilon) for every row,
                            - Abort if any row violates this bound.
                    - Record bit-depth:
                        · for all rows of this merchant, set quantised_bits = b.

(S1.3–S1.7 results),
[Schema+Dict],
[S0 Gate & Identity]
                ->  (S1.8) Assemble s1_site_weights rows & provenance
                    - For each site row (merchant_id, legal_country_iso, site_order):
                        · carry PK directly from site_locations (no re-keying),
                        · attach p_weight = p_i (post-normalisation, pre-quantisation real weight),
                        · attach weight_source = alias_layout_policy_v1.weight_source (string ID),
                        · attach quantised_bits = b,
                        · attach floor_applied (true if any floor/fallback/clamp was applied for this row),
                        · attach created_utc = S0.verified_at_utc.
                    - Emit rows in **PK order** only: [merchant_id, legal_country_iso, site_order].
                    - Ensure no missing or extra PKs vs site_locations for this (seed, fingerprint):

                        site_locations PK set  ==  s1_site_weights PK set

(S1.8 assembled table),
[Schema+Dict]
                ->  (S1.9) Write s1_site_weights & enforce immutability
                    - Select target partition via Dictionary:
                        · data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/
                        · partitions: [seed, fingerprint], format: Parquet.
                    - Enforce write-once:
                        · if partition is empty → allowed to publish,
                        · if non-empty → only allowed if existing bytes are **bit-identical**
                          (idempotent re-emit); otherwise Abort with IMMUTABLE_OVERWRITE.
                    - Write behaviour:
                        · write to staging, fsync, then atomic move into final Dictionary path,
                        · re-open published data and check:
                            - schema validity against schemas.2B.yaml#/plan/s1_site_weights (columns_strict),
                            - path↔embed equality for manifest_fingerprint (and seed if embedded),
                            - writer sort is PK order.
                    - No post-publish mutation or append is permitted for this partition.

Downstream touchpoints
----------------------
- **2B.S2 — Alias construction:**
    - MUST treat s1_site_weights as the **only** authoritative per-site probability law.
    - MAY NOT recompute weights from site_locations or policy; it only encodes p_weight into alias tables.
- **2B.S3 — Day effects:**
    - Uses s1_site_weights as the static base mass over sites/zone-groups before applying γ day factors.
- **2B.S4 — Group weights:**
    - Relies on S1’s weights (aggregated by tz-group) to define base_group shares before γ renormalisation.
- **2B.S5–S6 — Routing & virtual edges:**
    - Route using S2/S4 plan surfaces whose semantics ultimately depend on S1’s frozen weights.
- **2B.S7–S8 — Audit & validation bundle:**
    - Include s1_site_weights in inputs_digest and mass/quantisation checks.
    - Upstream consumers (e.g. 5A/5B) MUST NOT bypass S2/S4 and MUST treat S1→S2→S4 as the routing-plan authority chain.
```