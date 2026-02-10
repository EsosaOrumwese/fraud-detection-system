# Ingestion Gate (IG) Policy Stubs
_As of 2026-01-24_

This folder contains **non‑secret policy stubs** for IG. These are examples and placeholders only.
They are versioned and intended to be referenced by `partitioning_profile_id`.

No credentials or secrets belong here. Inject secrets at runtime.

## Files
- `partitioning_profiles_v0.yaml` — deterministic partition routing profiles (v0).

## Stream class → profile mapping (v0)
Use the following `partitioning_profile_id` values by stream class:

| Stream class | Stream name | partitioning_profile_id |
| --- | --- | --- |
| traffic_baseline | `fp.bus.traffic.baseline.v1` | `ig.partitioning.v0.traffic.baseline` |
| traffic_fraud | `fp.bus.traffic.fraud.v1` | `ig.partitioning.v0.traffic.fraud` |
| traffic (legacy) | `fp.bus.traffic.v1` | `ig.partitioning.v0.traffic` |
| control | `fp.bus.control.v1` | `ig.partitioning.v0.control` |
| audit | `fp.bus.audit.v1` | `ig.partitioning.v0.audit` |
| rtdl_decision_lane | `fp.bus.rtdl.v1` | `ig.partitioning.v0.rtdl.decision` / `ig.partitioning.v0.rtdl.action_intent` / `ig.partitioning.v0.rtdl.action_outcome` |

**Note:** v0 control & ingress streams **traffic + context**; context topics are active and feed RTDL join state.
