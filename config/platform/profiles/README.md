# Platform Profiles (v0)
_As of 2026-01-24_

Profiles separate **policy config** (outcome-affecting) from **wiring config** (endpoints/resources).
No secrets live in these files. Secrets are injected at runtime via environment/secret store.

## Location
```
config/platform/profiles/
```

## Shape (v0)
```
profile_id: <local|dev|prod>
policy:
  policy_rev: <version tag>
  partitioning_profile_id: <ig partition strategy id>
  require_gate_pass: true
wiring:
  object_store:
    bucket: fraud-platform
    endpoint: ${OBJECT_STORE_ENDPOINT}
  event_bus:
    topic_traffic: fp.bus.traffic.v1
    topic_control: fp.bus.control.v1
    topic_audit: fp.bus.audit.v1
```

Notes:
- `policy_rev` must be stamped into receipts/decisions/outcomes where applicable.
- `partitioning_profile_id` is chosen by IG policy; EB never infers partitioning.
- Wiring endpoints are placeholders; actual values come from env/secret store.

