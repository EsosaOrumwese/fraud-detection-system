# Synthetic Cross-Border Policies (S0/S3)

## Overview
These synthetic policy artefacts unblock S0 and S3 in the absence of production governance data. Both versions are staged alongside the synthetic datasets and should be replaced once real policies become available.

## S0 – `config/policy/crossborder_hyperparams.yaml`
- **Semver**: 0.1.0 (synthetic)
- **Purpose**: Evaluated by S0 to flag merchants eligible for cross-border admission.
- **Structure**: Ordered ladder with explicit rule IDs, priorities, and closed reason codes.
- **Key rules**:
  - Deny high-risk CNP MCCs (`6011`, `6051`) globally.
  - Deny CNP travel ranges (`3000-3999`, `4722`).
  - Whitelist CP merchants across the synthetic EEA subset.
  - Catch-all default allow.
- **Dependencies**: Requires `iso_canonical` v2025-10-09 so all synthetic ISO codes resolve.

## S3 – `config/policy/s3.rule_ladder.yaml`
- **Semver**: 0.1.0 (synthetic)
- **Purpose**: Sole authority for S3 admission metadata and inter-country ordering (`candidate_rank`).
- **Structure**: Closed vocabularies (`reason_codes`, `filter_tags`) and total-ordered rules following the design precedence.
- **Key rules**:
  - Deny non-region destinations to enforce synthetic scope.
  - Deny sanctioned CP destinations (`IR`, `KP`, `RU`).
  - Allow home ISO first, then EEA grocery CNP destinations.
  - Non-decision CLASS marker and default fallback.

## Provenance
- Authored on 2025-10-09. YAML digests are tracked via `config/policy/...` in this repository.
- Synthetic assumptions mirror the synthetic merchant universe and can be swapped once real policy artefacts are available.
