# IaC modules

## Status
Phase 2 implementation unlocked.

## Modules
- `core/`: persistent dev_min substrate (S3 stores, DynamoDB control/lock tables, optional budget alert).
- `demo/`: ephemeral demo substrate surfaces (Confluent contract materialization, ECS/network scaffolding, runtime DB, canonical SSM paths, manifests).

## Guardrails
- No NAT, no always-on load balancer, no always-on compute fleet.
- Tag every resource with `project/env/owner/expires_at` + `fp_phase/fp_tier`.
- Keep module inputs environment-agnostic where possible.
