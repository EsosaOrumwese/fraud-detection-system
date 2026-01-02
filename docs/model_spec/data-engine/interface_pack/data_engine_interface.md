# Data Engine Interface (Binding)

## 1. Purpose and scope
This document defines the stable, black-box interface from the Data Engine to the rest of the platform. It specifies identity, determinism, discovery, join semantics, and HashGate rules. It does not describe internal segment/state algorithms.
The output catalogue enumerates all outputs under `data/` and `logs/` declared in the binding dictionaries; consumers should filter to the outputs they require by class, scope, and gate requirements.

## 2. Definitions
### 2.1 Identity tuple
The canonical identity tuple for engine outputs is:
- `parameter_hash` (world identity)
- `manifest_fingerprint` (world identity)
- `seed` (RNG identity)
- `scenario_id` (scenario identity)
- `run_id` (run identity)

These fields appear on outputs according to their scope and are the only supported equality keys for deterministic joins.

### 2.2 Output classes
- Surface: deterministic tables/caches and authority surfaces.
- Stream: event-style outputs or append-only logs.
- Gate: validation bundles and PASS receipts that authorize reads.

## 3. Determinism and replay guarantees
For a fixed identity tuple and sealed inputs, outputs are deterministic and replayable. Outputs written for a given partition are immutable once their owning segment publishes a PASS receipt.

## 4. Sealing and immutability
Every segment publishes a validation bundle and `_passed.flag` receipt. Downstream readers must verify the receipt before reading any output that lists the corresponding gate in `engine_outputs.catalogue.yaml`.

## 5. Discovery and addressing
Outputs are discovered by:
1. Output locators (preferred), or
2. `path_template` plus partition keys in `engine_outputs.catalogue.yaml`.

Path templates that are fingerprint-scoped must use the exact token `fingerprint={manifest_fingerprint}`.

## 6. Join semantics
Join keys are declared per output in `engine_outputs.catalogue.yaml`. Consumers must use only those declared keys and must not infer additional join columns.

Outputs marked `exposure: external` are intended for platform consumption; internal outputs remain in the catalogue for completeness.

### 6.1 Segment join key tables (external outputs)
Segment 1A
| Output | Join keys | Notes |
| --- | --- | --- |
| `outlet_catalogue` | `merchant_id, legal_country_iso, site_order` | Inter-country order is not encoded; join `s3_candidate_set.candidate_rank` for ordering. |

Segment 1B
| Output | Join keys | Notes |
| --- | --- | --- |
| `site_locations` | `merchant_id, legal_country_iso, site_order` | 1:1 with `outlet_catalogue` for the same `seed` + `fingerprint`. |

Segment 2A
| Output | Join keys | Notes |
| --- | --- | --- |
| `site_timezones` | `merchant_id, legal_country_iso, site_order` | Sole time-zone authority after 2A PASS. |

Segment 3A
| Output | Join keys | Notes |
| --- | --- | --- |
| `zone_alloc` | `merchant_id, legal_country_iso, tzid` | Zone-level counts per merchant and country. |

Segment 3B
| Output | Join keys | Notes |
| --- | --- | --- |
| `virtual_routing_policy_3B` | `manifest_fingerprint, parameter_hash` | Object-level policy (not row-joinable). |
| `virtual_validation_contract_3B` | `fingerprint, test_id` | Validation tests keyed by `test_id` within a fingerprint. |

Segment 5B
| Output | Join keys | Notes |
| --- | --- | --- |
| `arrival_events_5B` | `seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq` | Skeleton arrival stream for downstream flows. |

## 7. Gate rulebook
- No PASS, no read. A consumer must verify all gates listed in `read_requires_gates` before reading an output.
- Gate verification methods are defined in `engine_gates.map.yaml`. The default rule is a SHA-256 digest over lexicographically ordered bundle entries with `_passed.flag` excluded, compared to the digest recorded in the PASS receipt.

## 8. Compatibility and versioning
Breaking changes must be introduced by:
- new `output_id` values with explicit deprecation, or
- schema version bumps with a parallel support window.

Consumers must not rely on internal segment/state ordering. Only the interfaces in this pack are binding.

## 9. Appendix: Segment to output quick index (informative)
Use `engine_outputs.catalogue.yaml` for the complete inventory. Key externally consumed outputs include:
- Layer 1 (1A-3B): outlet catalogue, site locations, site timezones, time-zone cache, zone allocations, virtual edge catalogues.
- Layer 2 (5A-5B): arrival surfaces and arrival event skeleton streams.
- Layer 3 (6A-6B): entity graph surfaces, event streams, and label surfaces.
