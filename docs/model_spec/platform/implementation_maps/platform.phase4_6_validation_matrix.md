# Phase 4.6 Validation Matrix (Run/Operate + Obs/Gov)
_As of 2026-02-08_

## Scope
This matrix satisfies the written quality-gate requirement in `platform.build_plan.md` section `4.6.K` by providing explicit PASS/FAIL criteria and current status for `4.6.A..4.6.J`.

Validation baseline for orchestrated parity evidence:
- `platform_run_id`: `platform_20260208T193407Z`
- `scenario_run_id`: `24827c0356195144a6d9a847c3563347`

## Status Summary
- PASS: `4.6.F`, `4.6.J`
- FAIL: `4.6.A`, `4.6.B`, `4.6.C`, `4.6.D`, `4.6.E`, `4.6.G`, `4.6.H`, `4.6.I`
- Phase 5 unblock: **NO** (mandatory 4.6 gates are not all PASS)

## Matrix
| Gate | PASS Criteria (DoD Extract) | Current Status | Evidence | Gap to Close |
| --- | --- | --- | --- | --- |
| `4.6.A` Governance lifecycle fact stream | Required governance families are emitted and queryable (`RUN_READY_SEEN`, `RUN_STARTED`, `RUN_ENDED`, `RUN_CANCELLED`, `POLICY_REV_CHANGED`, corridor anomalies, `EVIDENCE_REF_RESOLVED`) with idempotent append-only writer posture | FAIL | Build-plan requirement: `docs/model_spec/platform/implementation_maps/platform.build_plan.md`; current run evidence shows SR event kinds such as `READY_COMMITTED`/`READY_PUBLISHED`, not the required governance family set | Implement governance event writer(s), schemas, and query surface for required v0 families |
| `4.6.B` Evidence-ref resolution corridor + access audit | Ref resolution is gated and every resolution attempt emits minimal access audit record; denied/invalid refs emit structured anomalies | FAIL | No dedicated evidence-ref resolution service/corridor implementation found in current platform runtime wiring; no `EVIDENCE_REF_RESOLVED` audit artifact in run evidence | Implement ref-resolution boundary with RBAC/allowlist and structured audit emission |
| `4.6.C` Service identity + auth posture by env | Local parity writer auth pinned/tested; dev/prod writer identity mechanism enforced uniformly; actor attribution from auth context | FAIL | Local producer allowlist posture exists in component policies; no complete dev/prod uniform auth mechanism surfaced in platform-wide runtime implementation | Add env-ladder identity contract and enforce at writer corridors with actor/source derivation |
| `4.6.D` Platform run reporter | A platform-level run-scoped reconciliation artifact exists with cross-plane counters + evidence refs | FAIL | Component reporters exist (IEG/OFP/CSFB/DF/DLA scopes), but no platform-wide reporter artifact under one canonical obs path | Build platform run reporter aggregator and wire scheduled/on-demand emission |
| `4.6.E` Deployment provenance stamp uniformity | Required runtime/governance records carry `service_release_id` + environment/config revision context | FAIL | No code-level `service_release_id` propagation discovered in runtime surfaces | Add release stamp plumbing and assert in validation checks |
| `4.6.F` Run/operate durability for downstream services | Always-on operation targets exist; restart/replay-safe supervision pinned; matrix-vs-daemon boundaries explicit | PASS | Orchestrator module and packs: `src/fraud_detection/run_operate/orchestrator.py`, `config/platform/run_operate/packs/local_parity_control_ingress.v0.yaml`, `config/platform/run_operate/packs/local_parity_rtdl_core.v0.yaml`; lifecycle targets in `makefile`; runbook section `3.1` in `docs/runbooks/platform_parity_walkthrough_v0.md`; clean run restart/status evidence recorded in `docs/model_spec/platform/implementation_maps/platform.impl_actual.md` | Maintain as baseline and extend onboarding packs for future planes |
| `4.6.G` Corridor checks + anomaly policy closure | Corridor checks pinned for IG/DLA/AL/evidence-ref/registry boundaries; anomaly taxonomy minimum set wired and verified | FAIL | Partial anomaly/corridor behavior exists in component scopes; evidence-ref and registry promotion boundaries not yet closed in v0 platform implementation | Complete missing corridor boundaries and run negative-path verification matrix |
| `4.6.H` Environment parity conformance gate | Same semantics validated across local_parity/dev/prod for envelope, governance schema, policy revision stamp, corridor behavior | FAIL | Local parity evidence exists; no explicit conformance checklist artifact covering dev/prod with same semantics | Create and execute environment conformance checklist with evidence bundle |
| `4.6.I` Closure evidence + handoff gate | Monitored parity run demonstrates governance lifecycle emission, evidence-ref audit, and platform run reporter; handoff note marks Phase 5 unblock | FAIL | Monitored orchestrated parity evidence exists for run/operate and stream path, but governance-lifecycle + evidence-ref + platform-run-reporter requirements are incomplete | Close `4.6.A`, `4.6.B`, `4.6.D`, then publish handoff/unblock note |
| `4.6.J` Platform orchestration contract | One plane-agnostic orchestration contract for lifecycle/readiness/run-scope/restart-safe behavior; packs onboarded declaratively; no RTDL hardcoding | PASS | Contract implementation and tests: `src/fraud_detection/run_operate/orchestrator.py`, `tests/services/run_operate/test_orchestrator.py` (`4 passed`); pack onboarding and make targets in `makefile`; clean run evidence in `docs/model_spec/platform/implementation_maps/platform.impl_actual.md` | Keep orchestrator business-agnostic and onboard new planes through pack-only additions |

## 4.6.K Rollup Check
- Written matrix exists: PASS (this file).
- Monitored orchestrated parity evidence exists: PASS for run/operate and stream/restart proof.
- Overall `4.6` mandatory-gate posture: FAIL (because `4.6.A/B/C/D/E/G/H/I` are not PASS).
