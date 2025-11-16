# 1B — State overview (S0–S9)

**S0 — Foundations & gate-in (deterministic)**
Verify 1A’s consumer gate (`_passed.flag`) for the target fingerprint, then read **`outlet_catalogue`** (authority for sites-to-materialise). Inherit the layer RNG envelope & numeric policy. **No PASS → no read.**  

**S1 — Country frame & tiling (deterministic)**
For each `legal_country_iso` present in `outlet_catalogue`, build a clipped tile index (eligible raster cells / polygons). FK integrity remains against canonical ISO-3166. 

**S2 — Within-country priors (deterministic)**
Compute per-tile weights (e.g., population/land-use priors) into a fixed-dp weight surface. No randomness; just a deterministic prior over eligible tiles.

**S3 — Pull N per (merchant, country) (deterministic read)**
Derive the required **site count `N_i`** per `(merchant_id, legal_country_iso)` from `outlet_catalogue` (row counts / `site_order` continuity). Cross-country order remains the sole authority of **`s3_candidate_set.candidate_rank`** (read-only here).  

**S4 — Fractional split → integer plan (deterministic by default)**
Turn priors into fractional shares and **integerise** to `N_i` via largest-remainder with a deterministic tie-break. Optional policy switch: Dirichlet lane → round deterministically (mirrors 1A’s stance on “deterministic default, optional stochastic lane”).

**S5 — Cell selection (RNG)**
For each allocated cell, emit one **`raster_pick_cell`** RNG event (single-uniform). Uses the same **layer RNG envelope** (`before/after/blocks/draws`, open-interval mapping).  

**S6 — Point jitter within cell (RNG)**
Uniform jitter inside the chosen pixel to get `(lat, lon)` (two-uniform family). Enforce point-in-country; bounded resample on predicate failure.

**S7 — Site synthesis & conformance (deterministic)**
Attach deterministic attributes (tile id, admin label if available), ensure **1:1** coverage with `outlet_catalogue`, preserve `site_order`, no duplicates. (Cross-country order still **not** encoded—downstreams join S3 if needed.) 

**S8 — Egress: `site_locations` (immutable, order-free)**
Publish geometry for every outlet stub under **`seed` + `fingerprint`** partitions (same partition law as 1A egress). Order is not encoded; consumers join S3 for `candidate_rank`.  

**S9 — Validation bundle & PASS gate**
Structural (point-in-country, row parity with 1A, path↔embed equality), distributional (tile-weight back-checks), and RNG budgeting under the **same gate recipe**: emit `validation_bundle_1B/` and `_passed.flag` whose content equals **SHA-256 over bundle files in ASCII-lexicographic order**. Consumers must verify this before reading 1B egress. (Same hashing rule you used in 1A.)  

---

### Cross-cuts this keeps identical to 1A

* **Consumer discipline:** verify 1A’s `_passed.flag` before any 1B reads of `outlet_catalogue`. 
* **Authority separation:** 1B **never** encodes inter-country order; **S3 `candidate_rank`** remains the sole order authority.  
* **Lineage & partitions:** path↔embed byte-equality; egress partitions by `[seed, fingerprint]`. 
* **RNG envelope & mapping:** Philox; open-interval U(0,1); `blocks`/`draws` budgeting and trace reconciliation. 

If you want, I can turn this into a **skeleton dictionary + schema anchor list** for 1B (IDs, paths, partitions, `$ref`s) in your house style, but the above is the picture we’ll implement.
