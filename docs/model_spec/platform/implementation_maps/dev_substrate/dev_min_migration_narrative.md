# Dev-Min Migration Narrative (Incremental)
_As of 2026-02-11_

This narrative is intentionally incremental.
Sections will be appended in discussion order, starting from local-parity implemented baseline and moving gate-by-gate into `dev_min`.

## Section 1: Bootstrap Before Swap (Flow Step 1)

We begin from a fully green local-parity platform: all planes function, flow logic is validated, and ownership boundaries are known. Performance is limited by local substrate, but semantics are trusted. So the first migration question is not "which component do we rewrite first?" but "what control surface will govern all rewrites?"

The first step in flow is a trust-and-control bootstrap in `dev_min`. That means establishing identity, credentials, and policy-bearing access for the shared substrates before any component migration. In practical terms, AWS and Confluent credentials are not treated as simple secrets; they are the first runtime control artifacts that define who can provision, publish, consume, observe, and audit.

Next, we stand up the meta-layers early: Run/Operate and Obs/Gov. This is intentional sequencing. If we migrate components before these layers exist, we recreate the same drift risk seen in local-parity evolution, where services can run but are not uniformly orchestrated, observed, or cost-governed.

Only after this bootstrap gate is green do we begin incremental plane migration. Each plane then enters through a controlled path: substrate resources are provisioned, component contracts are mapped, and runtime evidence is emitted under the same operate/govern rails from day one.

So this pre-decision is adopted as a flow law: bootstrap control and trust first, then swap tools and services incrementally under that control.

## Section 2: Oracle Store Migration

I’d treat the Oracle Store migration as a controlled authority transfer, not a data copy exercise. The first decision I would lock is boundary law: Oracle artifacts remain Data Engine-owned truth, and the platform is only a consumer with fail-closed checks. That single decision prevents almost every downstream mistake, because it means I never let platform code “fix” or reinterpret Oracle truth in transit. I would anchor that in the active dev-substrate planning surface (`docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md`) and keep all migration mechanics subordinate to it.

From there, I’d design the move as a deterministic landing pipeline from local-parity source to dev-min destination, with AWS S3 as the managed target. I would pin one canonical destination root and scenario pin format up front, then enforce write-once semantics for landed artifacts. No mutable overwrite lanes, no ad-hoc prefix reshaping during copy, no implicit discovery. Every landed pack would carry a manifest and digest footprint so we can prove byte-level continuity between source and destination.

The next major decision would be that stream-sorted views are first-class migration closure criteria, not optional post-processing. After landing raw Oracle artifacts, I’d build per-output sorted stream views in the destination, with explicit ordering policy. For `ts_utc` outputs I’d sort by canonical event time with deterministic tie-breakers; for non-`ts_utc` outputs I’d enforce a pinned fallback key policy. Then I’d emit per-output closure receipts that prove no dupes, no drops, stable row counts, and deterministic content hashes. If even one required output is missing closure evidence, the migration is not green.

Only after that would I allow runtime wiring changes. SR and WSP would be pointed to the destination Oracle root and scenario pins, and WSP would read from the sorted stream-view contract, not unsorted raw paths. I’d keep the existing control-plane laws intact: no PASS, no read; no strict validation, no READY. In practice, Oracle validation must happen before READY consumption is allowed in run/operate flow, so the platform cannot “start streaming and hope.”

I’d make security and cost decisions explicit before first production-like run. IAM would be least-privilege by prefix, S3 public access blocked, and evidence paths separated from transient migration paths. Since dev-min is budget-constrained and demo-destroy oriented, I’d keep only durable truth/evidence surfaces persistent and ensure every migration run emits enough telemetry to audit spend drivers and data movement without noisy high-cost observability.

For risk control, I would run a shadow period: the same bounded run materialized from both old and new Oracle roots, then compared via receipts, manifests, and stream-view hashes. That gives hard evidence of semantic parity before cutover. Rollback is then trivial and low-risk: switch root pointers back, because the process is additive and append-only rather than destructive.

The final acceptance decision would be narrative plus evidence, not just “tests passed.” I’d require run-scoped artifacts proving four things: landed truth continuity, stream-view deterministic closure, strict validation gates passing, and unchanged downstream behavior under the same run IDs and provenance pins. Once those are true, Oracle migration is complete in the only way that matters here: same platform laws, managed substrate wiring, no drift hidden behind operational convenience.

## Section 3: Scenario Runner Migration

While your Oracle upload is running, I would migrate SR as a contract-preserving adapter move, not a behavior rewrite.

I would begin by locking the SR boundary exactly as it exists in local-parity: SR remains the run-readiness authority that emits canonical `run_facts_view` and READY, and it keeps the same identity laws (`platform_run_id`, `scenario_run_id`, `run_config_digest`) and idempotency behavior on re-emit. The first deliberate choice is to forbid semantic edits during migration. In practice, that means no new “dev exceptions,” no alternate READY schema, and no relaxed gate posture. The migration succeeds only if SR in `dev_min` behaves like SR in `local_parity`, with only substrate wiring changed.

Then I would wire SR to `dev_min` profile surfaces as explicit pins, not implicit defaults. SR would consume the Oracle identity from `DEV_MIN_ORACLE_ENGINE_RUN_ROOT` and `DEV_MIN_ORACLE_SCENARIO_ID`, and it would refuse ambiguous roots. It would publish control-plane readiness into managed Kafka (`fp.bus.control.v1`) using the existing profile env names (`DEV_MIN_KAFKA_BOOTSTRAP`, key/secret envs), and all run evidence would write to managed S3 evidence paths. The critical decision here is that SR must not silently fall back to local paths when `dev_min` is active; if Oracle pins are missing or contradictory, SR fails closed before READY.

Next, I would migrate SR’s ingress-to-readiness flow with strict gate discipline. SR would still verify Oracle by-ref artifacts and only emit READY once required gate evidence is present and pinned. If the Oracle lane is partial or inconsistent, SR returns an explicit blocked posture (`WAITING` or fail-closed reason), but does not emit a deceptive READY. This keeps the “no PASS, no read” law intact and prevents downstream contamination in WSP/IG.

After that, I would enforce control-bus correctness under managed Kafka. READY publication remains idempotent and deterministic, keyed so replay/re-emit cannot create run-identity drift. I would explicitly test duplicate READY sends, stale run-id re-emit attempts, and cross-run contamination cases. If any of those pass incorrectly, migration stops. The point is not that SR can publish to Kafka; the point is that it publishes correctly under at-least-once and replay realities.

Once core wiring is stable, I would bring SR into run/operate and obs/gov for `dev_min` exactly the way the migration authority expects: operator-driven CLI orchestration, run-scoped evidence, and structured lifecycle events. SR must be operable as part of the integrated `3.C` lane, not as a one-off script that “worked once.” That includes health/readiness visibility, deterministic artifact locations, and governance-friendly evidence refs.

Validation would happen in a strict ladder. First, component-level SR gate checks with managed wiring. Then bounded integrated runs (`20`, `200`) once Oracle `3.C.1` is green, verifying that SR emits correct readiness facts and that downstream components consume the same run identity. I would include negative-path proofs (missing Oracle artifacts, pin mismatch, duplicate re-emit, stale run context) and require fail-closed outcomes for each.

Finally, cutover is profile-driven and reversible. `local_parity` remains untouched as the correctness harness; `dev_min` becomes the managed-substrate proof rung. If SR fails any semantic or provenance gate, rollback is immediate by reverting profile/runtime selection, not by patching behavior under pressure. That keeps migration controlled, auditable, and aligned with your pinned design law: same platform semantics, different managed wiring.
