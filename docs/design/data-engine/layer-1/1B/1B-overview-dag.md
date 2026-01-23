```
                     LAYER 1 - SEGMENT 1B (Outlet stubs → concrete site coordinates)

Authoritative inputs (sealed in S0)
-----------------------------------
[M] Upstream 1A egress & order authority:
    - validation_bundle_1A              @ [fingerprint]
    - validation_passed_flag_1A (_passed.flag)
    - outlet_catalogue                  @ [seed, fingerprint]
      · immutable outlet stubs; order-free; PK (merchant_id, legal_country_iso, site_order)
    - s3_candidate_set                  @ [parameter_hash]
      · sole inter-country order authority; home has candidate_rank = 0

[R] Reference spatial surfaces:
    - iso3166_canonical_2024
    - world_countries                  (country polygons; point-in-country authority)
    - population_raster_2025           (population prior for tiles)
    - tz_world_2025a                   (TZ polygons; civil-time legality, mainly for later layers) 

[N] Numeric & RNG profile (pinned by S0; shared with 1A):
    - numeric_policy.json, math_profile_manifest.json
    - philox2x64-10; IEEE-754 binary64; RN-even; FMA-off; **strict open-interval U(0,1)**
    - layer RNG envelope: before/after/blocks/draws, one trace append per event 


DAG
---
(M,R,N) --> (S0) Gate-in & foundations (no RNG)
                - Verify **1A validation gate** for this `manifest_fingerprint`:
                    * recompute SHA-256 over files listed in `index.json` (ASCII-lex `path`, flag excluded)
                    * assert `_passed.flag == SHA256(validation_bundle_1A)` for same fingerprint
                    * **No PASS → No read** of `outlet_catalogue`
                - Re-assert path↔embed identity rules (seed, parameter_hash, fingerprint, run_id)
                - Pin authority boundaries:
                    * inter-country order lives ONLY in 1A S3 `s3_candidate_set.candidate_rank`
                    * `outlet_catalogue` is order-free; gated by 1A bundle
                - Emit `s0_gate_receipt_1B` @ [fingerprint]
                    * proves 1A PASS
                    * enumerates sealed inputs 1B may read (1A+reference data)
                    * becomes the **must-have gate** for later 1B states 

                                  |
                                  | S0 receipt, RNG+numeric rails, sealed inputs
                                  v

             (S1) Tile index — eligible cells per country (no RNG)
                inputs: iso3166_canonical_2024, world_countries, population_raster_2025
                -> tile_index @ [parameter_hash]
                     - parameter-scoped; PK [country_iso, tile_id]; sort [country_iso, tile_id]
                     - enumerates eligible raster cells per ISO country
                         · tile_id = row_major_index(r,c)
                         · centroid_lon/lat, pixel_area_m2, inclusion_rule recorded
                     - **eligible universe of cells**; S1 does NOT read 1A egress and MUST NOT encode inter-country order 

             (S2) Tile weights — fixed-dp weights per tile (no RNG)
                inputs: tile_index, iso3166_canonical_2024, (optionally) world_countries, population_raster_2025
                -> tile_weights @ [parameter_hash]
                     - deterministic **fixed-decimal weights** per (country_iso, tile_id)
                     - choose basis (uniform / area / population) via governed config
                     - apply largest-remainder quantisation so Σ weight_fp = 10^dp per country
                     - **sole persisted spatial weight surface** for countries; parameter-scoped; RNG-free 

             (S3) Country requirements — site counts per merchant×country (no RNG)
                inputs: s0_gate_receipt_1B, outlet_catalogue, tile_weights, iso3166_canonical_2024
                -> s3_requirements @ [seed, fingerprint, parameter_hash]
                     - group `outlet_catalogue` rows to get `n_sites` per (merchant_id, legal_country_iso)
                     - enforce:
                         · `legal_country_iso` ∈ ISO table
                         · every country with n_sites>0 exists in tile_weights for this parameter_hash
                     - RNG-free **bridge** from 1A outlet stubs → “how many sites we must place per country” 

             (S4) Tile allocation plan — integer quotas per merchant×country×tile (no RNG)
                inputs: s3_requirements (n_sites), tile_weights (weight_fp, dp), tile_index, iso3166_canonical_2024
                -> s4_alloc_plan @ [seed, fingerprint, parameter_hash]
                     - for each (merchant, country):
                         · use weight_fp, dp to compute base allocations z_i and residues rnum_i
                         · distribute shortfall S = n_sites − Σ z_i by descending rnum_i (tie-break tile_id)
                     - emit rows only where n_sites_tile ≥ 1
                     - guarantees Σ_tile n_sites_tile == n_sites for each (merchant, country)
                     - **no RNG**; purely integer arithmetic guided by S2’s weights 

             (S5) Site→tile assignment — which sites fill which tile quotas  [RNG]
                inputs: s4_alloc_plan, tile_index, iso3166_canonical_2024
                -> s5_site_tile_assignment @ [seed, fingerprint, parameter_hash]
                     - for each (merchant, country):
                         · expand tiles into a multiset with `n_sites_tile` copies each
                         · build list of site_orders = 1..N (N = Σ n_sites_tile)
                         · draw one U(0,1) per site from RNG family `site_tile_assign`
                         · sort sites by (u, site_order) to get a permutation
                         · pair permuted sites with multiset of tiles → each site gets exactly one tile
                -> rng_event_site_tile_assign @ [seed, parameter_hash, run_id]
                     - exactly one event per site, blocks=1, draws="1"
                     - envelope+trace logging follows layer RNG law
                - **Result:** tile quotas from S4 are honoured, and we now know **which specific site stub lives in which tile** 

             (S6) In-cell jitter & point-in-country enforcement  [RNG]
                inputs: s5_site_tile_assignment, tile_index (geometry), world_countries
                -> s6_site_jitter @ [seed, fingerprint, parameter_hash]
                     - for each site:
                         · take its tile’s [min_lon,max_lon]×[min_lat,max_lat] rectangle
                         · draw two uniforms via `in_cell_jitter` → (u_lon, u_lat)
                         · map to (lon*, lat*) in the rectangle
                         · compute deltas (delta_lon_deg, delta_lat_deg) from tile centroid
                         · check point lies inside the country polygon for legal_country_iso
                         · if fail, resample (up to MAX_ATTEMPTS); overflow ⇒ hard fail
                -> rng_event_in_cell_jitter @ [seed, parameter_hash, run_id]
                     - ≥1 event per site (one per attempt), blocks=1, draws="2"
                - **Result:** every site now has a jitter vector such that “centroid + delta” is inside its tile AND inside its country polygon 

             (S7) Site synthesis — stitch assignment + jitter + geometry (no RNG)
                inputs: s5_site_tile_assignment, s6_site_jitter, tile_bounds, outlet_catalogue (via S0 gate)
                -> s7_site_synthesis @ [seed, fingerprint, parameter_hash]
                     - join per site:
                         · outlet key (merchant_id, legal_country_iso, site_order)
                         · tile_id from S5
                         · centroid from tile_bounds
                         · deltas from S6
                     - reconstruct lon_deg, lat_deg = centroid + delta
                     - enforce:
                         · 1:1 coverage with S5 keys
                         · 1:1 coverage with outlet_catalogue keys for this fingerprint
                         · reconstructed point lies inside the tile rectangle
                     - no RNG; S7 is a deterministic stitch that **turns 1A stubs into absolute coordinates** while checking geometric/legal invariants 

             (S8) Egress publish — `site_locations` (order-free; no RNG)
                inputs: s7_site_synthesis
                -> site_locations @ [seed, fingerprint]
                     - projection of S7 into the egress schema
                     - partitions: [seed, fingerprint]; writer sort: [merchant_id, legal_country_iso, site_order]
                     - order-free egress; **no inter-country order encoded**
                     - drops parameter_hash from partitions (fingerprint already pins parameters)
                     - S8 **must not** read 1A surfaces or RNG logs; it only shapes & publishes egress 

   (All planning tables + RNG logs + egress) --> (S9) Replay validation & PASS gate for 1B (no RNG)
                -> validation_bundle_1B/ @ [fingerprint]
                     - includes:
                         · S7↔S8 row/key parity & egress schema/partition/order checks
                         · RNG accounting & envelope/trace reconciliation for `site_tile_assign` and `in_cell_jitter`
                         · egress file checksums for `site_locations`
                         · path↔embed equality & Dictionary/Schema coherence checks
                -> _passed.flag       @ [fingerprint]
                     - content: `sha256_hex = <SHA256(bundle)>`
                     - hash is SHA-256 over raw bytes of files listed in `index.json`
                       in ASCII-lex order of `path` (flag excluded)
                - **Consumer law:** downstream **must verify** this flag before reading `site_locations`
                  for the same fingerprint → **No PASS → No read site_locations** 


Downstream touchpoints
----------------------
- **Layer-1 / Segment 2A** (time-zone assignment) and any other consumer that needs concrete site geometry:
    1) locate `validation_bundle_1B` under `fingerprint={manifest_fingerprint}`;
    2) recompute SHA-256 over bundle files per 1B.S9’s law;
    3) only then read `site_locations` @ [seed, fingerprint].  **No PASS → No read.**
- Any consumer that needs **inter-country order** (e.g., “home vs foreign outlet 1..K”) MUST:
    - treat `site_locations` as **order-free egress**, and
    - join 1A S3 `s3_candidate_set.candidate_rank` (home = 0) for ordering.
- `tile_index` and `tile_weights` are the **only persisted spatial priors**; downstream states MAY read them
  for analysis, but MUST NOT invent competing grids or weight surfaces.


Legend
------
(Sx) = state
[name @ partitions] = artefact + its partition keys
[RNG] = RNG-bounded state; events logged under [seed, parameter_hash, run_id] with 1 trace append per event
Order authority lives ONLY in 1A S3 (`s3_candidate_set.candidate_rank`); 1B egress (`site_locations`) is inter-country order-free.
```