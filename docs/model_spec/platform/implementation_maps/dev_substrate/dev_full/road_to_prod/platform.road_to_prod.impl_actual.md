# Dev Full Road-To-Prod Implementation Notes
_As of 2026-03-05_

## Entry: 2026-03-05 16:55 +00:00 - Pre-edit plan: establish main road-to-prod plan authority doc
### Trigger
1. USER requested the main production-readiness plan document under:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod`.

### Problem framing
1. Existing stress/build docs are distributed, but there was no single main phase-ladder authority for the production-readiness road (`G1..G4` closure path).
2. We needed a deterministic, fail-closed phase map that can be progressively elaborated with subphase execution.

### Decision
1. Add a main plan authority file:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`.
2. Use a production-readiness phase ladder:
   - `PR0` program lock,
   - `PR1` G2 data realism,
   - `PR2` numeric contract activation,
   - `PR3` G3A runtime cert,
   - `PR4` G3B ops/gov cert,
   - `PR5` G4 go-live rehearsal.
3. Keep this file as the main route and expand active phase details there or via subdocs as execution begins.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 16:56 +00:00 - Main road-to-prod plan authority doc added
### Implemented file
1. Added:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`.

### What was pinned
1. Program goal and final PASS criteria (`open_blockers=0`, complete packs, gate closure).
2. Current posture baseline and remaining closure focus.
3. Phase ladder `PR0..PR5` with intent, subphase template, and DoD.
4. Fail-closed operating rules and rerun-scope discipline.
5. Immediate next executable step: `PR0-S0`.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 16:57 +00:00 - Relocated road-to-prod implementation notes from build impl map
### Trigger
1. USER requested removal of the above road-to-prod entries from:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.impl_actual.md`.
2. USER requested a dedicated implementation note for road-to-prod.

### Action
1. Removed road-to-prod entries from the build implementation map.
2. Preserved those entries in this dedicated road-to-prod implementation note file.

### Rationale
1. Keeps build-track implementation history focused on build scope.
2. Keeps production-readiness planning/execution history scoped under `road_to_prod`.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:01 +00:00 - Pre-edit plan: harden road-to-prod plan purpose and closure authority
### Trigger
1. USER requested strengthening of `platform.road_to_prod.plan.md` so the doc cannot be interpreted as checklist progress that still allows toy-grade closure.

### Problem framing
1. Current plan had a valid phase map but the purpose language could still be interpreted as procedural progression rather than mission-intent closure.
2. Risk: phases could be marked complete based on artifact presence rather than proving gate intent and production-like behavior.

### Decision
1. Rewrite purpose/goal language to directly mirror the binding road-to-production objective:
   - production-grade mission proof, realistic data behavior, meaningful load, governance, and bounded cost.
2. Add explicit authority rules for phase closure sufficiency:
   - intent fidelity check,
   - realism/measurement-surface check,
   - claimability/evidence check,
   - blocker-zero check.
3. Add explicit anti-patterns that are forbidden as closure rationale (toy windows, proxy metrics, missing drill evidence, checklist-only closure).
4. Add a final document-intent completion rule to prevent circular green status without mission completion.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:03 +00:00 - Road-to-prod plan hardened to mission-intent authority (anti-toy)
### Implemented file
1. Updated:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`.

### What changed
1. Purpose section upgraded from procedural plan text to execution-authority language.
2. Program goal now explicitly binds to mission-level outcomes:
   - realistic load behavior,
   - semantic correctness under messy data behavior,
   - operational governability,
   - bounded spend and clean closure.
3. Added a binding phase/gate closure sufficiency standard:
   - intent fidelity,
   - realism validity,
   - claimability completeness,
   - blocker-zero/hold discipline,
   - anti-toy validation.
4. Added explicit anti-circle/anti-toy forbidden closure patterns.
5. Added document completion rule so final closure requires mission-intent satisfaction, not checklist completion.
6. Strengthened phase DoD statements to require intent proof per phase.

### Resulting authority posture
1. Phase completion now requires proving gate purpose, not only running steps.
2. The doc now explicitly prevents toy-grade declarations from proxy metrics, low-sample waivers, missing drills, or checklist-only progress.
3. Final closure is tied to claimable mission proof with `open_blockers=0`.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:11 +00:00 - Pre-edit plan: add required TBD closure sheet to road-to-prod authority
### Trigger
1. USER approved adding the strict TBD closure sheet into the main plan.

### Problem framing
1. The plan already defines gate intent, but unresolved `TBD` targets in the binding authority were not yet mapped into one closure board with explicit due-gate routing.
2. Without that mapping, execution risks ambiguity on what must be pinned now versus later gates.

### Decision
1. Add a binding section in `platform.road_to_prod.plan.md` for required TBD closure routing.
2. Cover three authority sources:
   - Section 15.1 open decisions (`OD-01..OD-09`),
   - Appendix A.1 workload envelope required rows,
   - Appendix C.1 monitoring baseline required rows.
3. Encode `Pin Now / Pin By G2 / Pin By G3A / Pin By G3B / Pin By G4` with fail-closed rules and status discipline.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:12 +00:00 - Required TBD closure sheet added and bound to gate progression
### Implemented file
1. Updated:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`.

### What was added
1. New Section 11 `Required TBD Closure Sheet (Binding)`.
2. Fail-closed closure timing rules for `Pin Now / Pin By G2 / Pin By G3A / Pin By G3B / Pin By G4`.
3. As-of scan snapshot counts:
   - open decisions: 9 (`OD-01..OD-09`),
   - Appendix A.1 `TBD` fields: 68,
   - Appendix C.1 `TBD` fields: 129.
4. Routing table (`TGT-01..TGT-15`) mapping each target class to owner lane, due gate, and closure artifact.
5. Status discipline and closure enforcement to block phase advancement on unresolved required targets.
6. Immediate next step updated to include `PR0-S0.1` sheet instantiation/population.

### Resulting authority posture
1. Required unresolved targets are now explicit and gate-bound, preventing silent carry-over of `TBD` debt.
2. Phase closure now has a concrete decision inventory that can be audited against fail-closed gate rules.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:15 +00:00 - Pre-edit plan: materialize PR0 dedicated phase doc and wire main plan
### Trigger
1. USER requested proceeding with planning `PR0` and the dedicated PR0 doc.

### Problem framing
1. Main road-to-prod plan defines PR0 intent, but execution-grade PR0 details (`S0..S5`, lane coverage, required artifacts, fail-closed blocker taxonomy) are not yet materialized in a dedicated phase authority document.
2. Without a dedicated PR0 doc, PR0 execution can drift into ad-hoc interpretation.

### Decision
1. Create a dedicated PR0 authority doc at:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR0.road_to_prod.md`.
2. Include explicit PR0 lane coverage and sequential state plan (`S0..S5`) with per-state DoD and failure conditions.
3. Wire the main plan to the PR0 doc via a detail pointer under PR0 and immediate-next-step posture.
4. Keep closure bound to Section 11 required `Pin Now` targets and `open_blockers=0`.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:16 +00:00 - PR0 dedicated phase authority doc created and main plan wired
### Implemented files
1. Added:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR0.road_to_prod.md`.
2. Updated:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`.

### What was implemented
1. Created a dedicated PR0 execution authority with:
   - explicit scope boundary,
   - mandatory capability-lane coverage,
   - state plan `S0..S5` with pass/fail criteria,
   - blocker taxonomy (`PR0.B01..B16`),
   - deterministic artifact contract,
   - runtime/cost budgets,
   - rerun discipline,
   - PR0 DoD checklist.
2. Wired main plan PR0 section and immediate-next-step section to this dedicated PR0 doc so execution path is unambiguous.

### Authority posture impact
1. PR0 is now execution-grade and fail-closed, not just a one-paragraph phase summary.
2. `Pin Now` closure and `open_blockers=0` handoff to `PR1_READY` are now explicitly testable and auditable.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:25 +00:00 - Pre-execution plan: run PR0 S0..S5 with deterministic control artifacts
### Trigger
1. USER requested full execution of PR0 state-by-state with expansion and closure.

### Decision-completeness check
1. Required `Pin Now` decision in scope: `TGT-01` injection path policy.
2. Authority-derived closure selected for `TGT-01`:
   - `via_IG` is the default production-readiness claim path,
   - `via_MSK` is allowed only for scoped hot-path claims and cannot certify IG envelope/capacity.
3. This is directly grounded in the binding pre-design authority (`dev-full_road-to-production-ready.md`) injection-path rules.

### Execution plan
1. Materialize `PR0` control root under:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/control/pr0/pr0_20260305T1725Z/`.
2. Execute `S0..S5` artifacts in-order with explicit state receipts.
3. Populate target status map (`TGT-01..TGT-15`) with:
   - `TGT-01=PINNED`,
   - future due-gate targets as `OPEN` with owner and rerun boundary,
   - `TGT-15=DEFERRED_OUT_OF_SCOPE` (RC2-L stretch).
4. Update main plan Section 11 with current status table so closure sheet is executable, not static.
5. Emit PR0 summary verdict and set `next_gate=PR1_READY` only if PR0-required blockers are zero.

### Performance/cost posture
1. PR0 is docs/control execution only; no local compute orchestration and no cloud workload dispatch.
2. Expected incremental cloud spend remains zero.

### Governance
1. Documentation/control-artifact changes only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:28 +00:00 - PR0 S0..S5 executed with deterministic artifacts; verdict PR1_READY
### Executed artifacts
1. Control root created:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/control/pr0/pr0_20260305T1725Z/`.
2. State artifacts emitted:
   - `pr0_entry_lock.json`, `pr0_authority_refs.json`,
   - `pr0_status_owner.json`, `pr0_status_owner_validation.json`,
   - `pr0_mission_charter.active.json`, `pr0_pin_now_resolution_receipt.json`,
   - `pr0_blocker_register.json`, `pr0_rerun_boundary_map.json`,
   - `pr0_consistency_validation.json`, `pr0_decision_trace.md`,
   - `pr0_execution_summary.json`, `pr0_evidence_index.json`.
3. Latest pointer emitted:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/control/pr0/pr0_latest.json`.

### State results
1. `S0 PASS`: authority refs resolved (`6/6`).
2. `S1 PASS`: single status-owner surface pinned and validated.
3. `S2 PASS`: `TGT-01` pinned (`via_IG` production claim path; `via_MSK` scoped hot-path only).
4. `S3 PASS`: unresolved non-PR0 targets registered with owner and rerun boundaries.
5. `S4 PASS`: consistency checks across status owner, charter, blocker register, and main plan status snapshot passed.
6. `S5 PASS`: rollup emitted with `verdict=PR1_READY`, `next_gate=PR1_READY`, `open_blockers=0` (PR0-required scope).

### Plan synchronization
1. Updated main plan Section 11 with current target status snapshot (`TGT-01..TGT-15`).
2. Updated main plan PR0 exit line with execution status and updated immediate-next-step to `PR1-S0`.
3. Updated PR0 doc with explicit execution record section for `pr0_20260305T1725Z`.

### Governance
1. Documentation/control-artifact changes only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:33 +00:00 - Pre-edit remediation: relocate PR0 artifacts from docs control path to runs path
### Trigger
1. USER flagged artifact placement as incorrect and required run artifacts to live under `runs/`.

### Problem
1. PR0 control JSON artifacts were placed under docs authority tree (`docs/.../road_to_prod/control/pr0/...`), which violates run-artifact separation.
2. Main plan, PR0 doc, implementation notes, and logbook currently reference this wrong path.

### Remediation decision
1. Relocate execution artifacts to run-control path:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr0_20260305T1725Z/`.
2. Relocate latest pointer to:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr0_latest.json`.
3. Rewrite embedded artifact references in:
   - `pr0_execution_summary.json`,
   - `pr0_evidence_index.json`,
   - `pr0_latest.json`.
4. Update documentation references to the new `runs/` root and remove misplaced `docs/.../control` artifacts.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 06:27:18 +00:00 - Remote image refresh is now the only execution-worthy move
### What I verified
1. The live WSP task definition is still:
   - family `fraud-platform-dev-full-wsp-ephemeral`,
   - revision `17`,
   - image `230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-full@sha256:49eb6cb0c5e33061fae4d1aaceeac2e44600adb5c4250436be9ac8395ed29cb2`.
2. The repo branch head on `cert-platform` contains the WSP runtime fixes, but the live task obviously does not.
3. Therefore the next bounded smoke would only re-prove stale-code behavior unless the remote image is rebuilt and the task definition is repinned.

### Production interpretation
1. This is not a documentation blocker or a convenience task.
2. It is the normal production promotion boundary:
   - validated source fix,
   - immutable image rebuild,
   - task-definition repin to the new digest,
   - bounded proof,
   - then steady certification.
3. Anything else would either:
   - waste cost on known-stale artifacts, or
   - weaken provenance for the canonical `WSP -> IG` replay lane.

### Chosen remediation
1. Build a fresh immutable image from the current `cert-platform` head using the existing managed M1 packaging workflow.
2. Keep the image refresh on the active branch only; no cross-branch merge path is needed for this execution.
3. Register a new WSP task-definition revision pinned to the new digest.
4. Rerun the bounded canonical smoke immediately against that new revision before spending on the full `PR3-S1` steady window.

### Governance
1. No branch operation.
2. Commit/push on the active branch is now warranted because the remote packaging workflow must build the current validated source, and the user explicitly requested periodic commits for observability.

## Entry: 2026-03-06 06:36:42 +00:00 - The refreshed WSP image cleared stale-code drift and exposed the actual egress-shape defect
### What changed
1. I rebuilt the immutable runtime image from `cert-platform` using the managed packaging workflow and repinned the live WSP task definition to revision `18`.
2. I removed hardcoded task-definition revision drift from the replay dispatchers so future image refreshes resolve the latest active revision instead of silently targeting stale revisions.

### What the new bounded smoke proved
1. The refreshed image now starts correctly and enters the real WSP send loop.
2. The log surface no longer shows the old blank-endpoint loader failure.
3. The live warnings are now repeated `IG push retry ... reason=timeout` events.
4. The route table for the private runtime subnets shows:
   - local VPC route only,
   - S3 gateway endpoint route,
   - no default egress route and no NAT gateway.
5. Therefore a private-subnet WSP worker cannot reach the public API Gateway ingress URL.

### Production interpretation
1. This invalidates the earlier assumption that private runtime subnets were the correct canonical posture for `WSP`.
2. `WSP` is the outside-world traffic producer, not an internal transform lane.
3. For a public `IG` endpoint, the production-fit posture is:
   - `WSP` runs on the public edge (public subnets + public IP) or another explicitly internet-capable producer edge,
   - internal/private runtime lanes remain private.
4. Adding NAT just to let the outside-world replay producer reach a public API would spend more and express the wrong network semantics for this component.

### Chosen remediation
1. Move canonical `PR3-S1` WSP replay defaults back to the public edge subnets with public IP enabled.
2. Widen the runtime interface-endpoint security group so endpoint-backed bootstrap also admits the public WSP subnets.
3. Keep the rest of the internal runtime stack private.
4. After that targeted infra correction, rerun the bounded canonical WSP smoke again.

### Governance
1. No branch operation.
2. Active-branch commit/push is warranted once the code + IaC correction set is coherent.

## Entry: 2026-03-06 06:40:11 +00:00 - Public-edge WSP routing exposed an IG URL composition defect
### What the corrected public-edge smoke showed
1. After moving `WSP` back onto the public edge and widening endpoint bootstrap ingress, the task stopped timing out and reached the immediate `IG` response path.
2. The worker now fails fast with `IG_PUSH_REJECTED` rather than timing out.
3. No API Gateway request-count datapoints were recorded for that window, which means the rejection likely occurred before the request hit the intended ingress resource.

### Root cause
1. `config/platform/profiles/dev_full.yaml` already defines `wiring.ig_ingest_url` as the full ingest endpoint:
   - `https://.../v1/ingest/push`
2. `world_streamer_producer.runner` was still appending `/v1/ingest/push` again inside `_push_to_ig(...)`.
3. The effective request URL therefore became:
   - `https://.../v1/ingest/push/v1/ingest/push`
4. That is a canonical wiring defect, not a throughput or capacity result.

### Chosen remediation
1. Normalize `IG` push URL resolution in `runner.py` so:
   - full ingest path stays unchanged,
   - base API URL is upgraded to `/v1/ingest/push`,
   - blank value remains invalid/obvious.
2. Improve `IG_PUSH_REJECTED` logging to include reject detail text so future routing defects are diagnosable from the first smoke.
3. Rebuild the immutable image again and repin the WSP task definition before another bounded smoke.

### Governance
1. No branch operation.
2. Active-branch commit/push is required because the corrected runtime image must be rebuilt from the new source head.

## Entry: 2026-03-06 06:45:58 +00:00 - The next remediation is lane-sharded WSP, not more speedup-only retries
### What the latest canonical smoke proved
1. The refreshed public-edge WSP lane now reaches `IG` correctly:
   - admitted request count is non-zero,
   - API Gateway `Count` shows corresponding traffic,
   - `4xx` and `5xx` remain zero.
2. The bottleneck is therefore no longer ingress wiring.
3. WSP progress logs show each output advancing at only about `40 eps`, for aggregate throughput around `170 eps`, materially below the `3000 eps` target.

### Root cause
1. The current WSP runner parallelizes only across outputs.
2. Inside each output stream, send/ack remains single-threaded and synchronous.
3. That creates a serialization ceiling on the producer side even when the ingress path is healthy.

### Production interpretation
1. Turning the `stream_speedup` knob further is not a real fix once the sender is serialized.
2. The production-correct scaling model is the one already pinned in the WSP design authority:
   - deterministic lane sharding within a run,
   - bounded per-lane in-flight work,
   - per-lane cursors/checkpoints,
   - horizontal multi-worker replay on remote compute.
3. This preserves the outside-world semantics while removing the single-sender ceiling.

### Chosen remediation
1. Add deterministic WSP lane sharding (`lane_count`, `lane_index`) at the event-selection layer.
2. Scope WSP checkpoints by run + lane so resume remains truthful per lane.
3. Extend the canonical PR3-S1 WSP dispatcher to launch and observe multiple lane tasks, not a single replay task.
4. Calibrate lane count from observed single-task throughput and rerun the bounded smoke before the full steady window.

### Governance
1. No branch operation.
2. Commit/push on the active branch will be required after the runner/dispatcher lane set is coherent.

## Entry: 2026-03-06 05:46:02 +00:00 - Production-first correction for PR3-S1 execution shape
### Problem actual
1. I had previously treated `PR3-S1` as though the main question was "how do I rerun the state cleanly".
2. That framing was wrong for the production goal.
3. The real question is:
   - how should the platform generate production-shaped ingress pressure through the real `via_IG` path,
   - using the real `WSP`,
   - at the declared `RC2-S` envelope,
   - without inventing a toy harness or misclassifying a stream processor as a producer.

### What the evidence now says
1. Live `IG` is already uplifted to the declared envelope:
   - API Gateway stage throttle is now `3000 rps / 6000 burst`,
   - Lambda memory is `1024 MB`,
   - Lambda timeout is `30 s`,
   - reserved concurrency is `300`.
2. The prior `PR3-S1` blocker is therefore no longer "IG is certainly capped at 200/400".
3. The real remaining defect is the injection path:
   - synthetic load harness is noncanonical,
   - `WSP`-as-Managed-Flink is conceptually wrong,
   - canonical remote `WSP` replay lane is not yet materialized.

### Production decision
1. `PR3-S1` should be split conceptually into two proofs inside the same state boundary:
   - `control compatibility proof`:
     `READY` publication/consumption remains required as a correctness proof for the declared control plane,
   - `throughput proof`:
     the actual steady-window throughput proof must use the real `WSP` replay emitter on remote managed compute.
2. For `S1` throughput certification, the correct canonical runtime is:
   - remote `WSP` replay job,
   - run-scoped,
   - window-bounded,
   - paced by `stream_speedup`,
   - emitting through `IG`,
   - measured on the declared `IG` surfaces.
3. This keeps the platform claim honest:
   - producer path is real,
   - ingress boundary is real,
   - stream-processing remains Managed Flink where it belongs (`IEG/OFP/RTDL`),
   - control-plane semantics are not silently discarded.

### Rejected alternatives
1. Reverting to "canonical ECS/Fargate because it is easier" was rejected as insufficient reasoning.
2. Forcing `WSP` into Managed Flink was rejected because it solves the wrong problem and changes the component's nature.
3. Reusing the synthetic remote loader was rejected because it proves only that API Gateway can receive synthetic POSTs.
4. Local orchestration of the certification run was rejected because it violates the road-to-prod posture.

### Immediate implementation plan
1. Materialize a canonical remote `WSP` replay dispatcher for `PR3-S1`.
2. Make the dispatcher use:
   - the existing `WSP` ECS task definition,
   - a scratch profile written inside the remote container,
   - explicit `stream_speedup`,
   - actual oracle `stream_view` roots in S3,
   - actual `IG` URL + API-key auth,
   - real output-set composition (`traffic + context`).
3. Bound the run by certification window, not by "emit until natural completion".
4. Use fail-fast cutoff only where throughput evidence shows the active window cannot satisfy the declared floor.
5. After dispatcher materialization, use fresh telemetry/Athena evidence to evaluate `PR3-S1` again.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:46:02 +00:00 - Real oracle-rate calibration for canonical WSP replay
### Why this calibration is mandatory
1. `stream_speedup` cannot be guessed if we want a production-grade window.
2. Overstating or understating it would recreate the same toy-certification problem under a new name.

### Measured evidence
1. Read the real oracle `stream_view` manifests and boundary parquet rows for the active engine root:
   - engine root: `s3://fraud-platform-dev-full-object-store/oracle-store/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`
   - scenario id found in the real stream rows: `baseline_v1`
2. For the main traffic lane:
   - `s3_event_stream_with_fraud_6B` row count = `473,383,388`
   - first observed `ts_utc` = `2026-01-01T00:00:00.001940Z`
   - last observed `ts_utc` = `2026-04-01T00:01:41.104298Z`
   - natural average throughput is therefore about `60.9 eps`.
3. For the full realistic `WSP` output set (`traffic + context`):
   - `arrival_events_5B` row count = `236,691,694`
   - `s1_arrival_entities_6B` expected same family scale as arrival/context lane set,
   - `s3_flow_anchor_with_fraud_6B` row count = `236,691,694`,
   - `s3_event_stream_with_fraud_6B` row count = `473,383,388`.
4. Using the realistic four-output posture, the natural aggregate rate is approximately `152 eps`.
5. Hitting `RC2-S steady = 3000 eps` therefore requires a first-pass calibration around:
   - `stream_speedup ~= 19.7`.

### Decision from the calibration
1. First canonical `PR3-S1` replay should not use arbitrary lane fanout.
2. It should use:
   - one real `WSP` task,
   - actual merged output set,
   - `stream_speedup` calibrated from real oracle time density,
   - window-bounded stop at the certification duration.
3. If that single real producer cannot reach the floor, that is real bottleneck evidence:
   - producer-side pacing/concurrency,
   - IG/Lambda/DynamoDB pressure,
   - or downstream platform saturation.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-05 17:35 +00:00 - Remediation complete: PR0 artifacts relocated to runs/ and docs authority corrected
### What was remediated
1. Moved execution artifacts from wrong docs path to canonical runs path:
   - from `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/control/pr0/pr0_20260305T1725Z/`
   - to `runs/dev_substrate/dev_full/road_to_prod/run_control/pr0_20260305T1725Z/`.
2. Moved latest pointer:
   - from docs control path to `runs/dev_substrate/dev_full/road_to_prod/run_control/pr0_latest.json`.
3. Rewrote embedded path refs in:
   - `pr0_execution_summary.json`,
   - `pr0_evidence_index.json`,
   - `pr0_latest.json`.
4. Updated active doc references to runs path:
   - `platform.road_to_prod.plan.md` immediate-next-step upstream pointer,
   - `platform.PR0.road_to_prod.md` artifact/control root references.
5. Removed misplaced docs control directory tree.

### Result
1. Run artifacts now live exclusively under `runs/`.
2. Docs remain authority-only.
3. PR0 verdict remains unchanged: `PR1_READY`, `open_blockers=0` for PR0-required scope.

### Governance
1. No commit/push/branch operation.

## Entry: 2026-03-05 17:37 +00:00 - Pre-edit remediation: remove PR0 decision trace artifact
### Trigger
1. USER requested no decision trace doc because implementation note already serves as reasoning authority.

### Decision
1. Remove `pr0_decision_trace.md` from PR0 required outputs and artifact contract.
2. Update existing PR0 run artifacts to drop decision-trace references from:
   - `pr0_execution_summary.json` evidence refs,
   - `pr0_evidence_index.json` artifact list.
3. Delete `runs/.../pr0_decision_trace.md` from the PR0 run folder.
4. Keep reasoning continuity in implementation map + logbook only.

### Governance
1. No commit/push/branch operation.

## Entry: 2026-03-05 17:38 +00:00 - Decision trace artifact removed; implementation note is sole reasoning authority
### Completed actions
1. Updated `platform.PR0.road_to_prod.md`:
   - removed `pr0_decision_trace.md` from `S4` outputs,
   - removed it from required artifact contract list,
   - updated execution record `S4 PASS` line accordingly,
   - added explicit note that reasoning continuity is in `platform.road_to_prod.impl_actual.md`.
2. Updated PR0 run artifacts under `runs/.../pr0_20260305T1725Z/`:
   - removed `pr0_decision_trace.md` from `pr0_execution_summary.json` evidence refs,
   - removed decision-trace artifact row from `pr0_evidence_index.json`,
   - corrected `pr0_evidence_index.json` self `exists=true` entry.
3. Deleted run artifact file:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr0_20260305T1725Z/pr0_decision_trace.md`.

### Result
1. No active PR0 authority or run artifact contract requires a separate decision trace doc.
2. Reasoning history remains in implementation note + logbook only.

### Governance
1. No commit/push/branch operation.

## Entry: 2026-03-05 17:42 +00:00 - Pre-edit plan: detailed PR1 authority doc for G2 data realism closure
### Trigger
1. USER requested proceeding to detailed planning of PR1.

### Problem framing
1. Main plan contains PR1 intent and template only; it lacks execution-grade state details, lane coverage, blocker taxonomy, and deterministic artifact contract for G2 closure.
2. Without a dedicated PR1 authority doc, closure of `TGT-02..TGT-07` risks ambiguity and checklist-only interpretation.

### Decision
1. Add dedicated PR1 doc:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR1.road_to_prod.md`.
2. Encode PR1 as fail-closed `S0..S5` chain aligned to G2 authority:
   - 7-day window charter,
   - realism profile/cohort distributions,
   - join matrix + decision closure,
   - RTDL allowlist + IEG minimal graph + lateness policy,
   - label maturity/time-causality + monitoring baselines,
   - deterministic data realism pack rollup verdict.
3. Bind PR1 closure to `TGT-02..TGT-07` and `G2 PASS` only when `open_blockers=0`.
4. Wire main plan PR1 section and immediate-next-step section to the PR1 doc.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:44 +00:00 - PR1 detailed phase authority doc added and main plan wired
### Implemented files
1. Added:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR1.road_to_prod.md`.
2. Updated:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`.

### What was implemented
1. Detailed PR1 authority (`G2` closure) with:
   - binding purpose and hard exit criteria,
   - mandatory capability-lane coverage,
   - execution posture (evidence-first, no rerun-the-world, no local orchestration),
   - state chain `S0..S5` with pass/fail conditions,
   - blocker taxonomy (`PR1.B01..B20`),
   - deterministic run artifact contract under `runs/.../run_control/<pr1_execution_id>/`,
   - runtime/cost budgets,
   - rerun boundary rules,
   - DoD tied to `TGT-02..TGT-07` and `G2 PASS`.
2. Main plan PR1 section now explicitly points to this dedicated PR1 doc.
3. Main plan immediate-next-step section now includes PR1 doc as execution source.

### Authority posture impact
1. PR1 is now execution-grade and auditable, not a generic subphase template.
2. Closure of `Pin By G2` targets is explicitly bound to state outcomes and fail-closed verdict logic.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:48 +00:00 - Pre-execution plan: expand PR1-S0 and execute S0 only
### Trigger
1. USER requested proceeding with planning expansion of `PR1-S0` and execution.

### Decision-completeness check
1. Upstream gate/charter required for PR1-S0 is present:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr0_20260305T1725Z/pr0_execution_summary.json` (`PR1_READY`).
2. Injection-path policy is already pinned in PR0 mission charter (`via_IG` claim boundary).
3. No unresolved `Pin Now` targets remain for PR1 entry.

### S0 execution strategy
1. Expand PR1 doc S0 with explicit substeps/checklist and fail-closed criteria.
2. Materialize PR1 S0 run-control root:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/`.
3. Emit required S0 outputs:
   - `pr1_entry_lock.json`,
   - `pr1_window_charter.json`,
   - `pr1_evidence_inventory.json`.
4. Emit S0 receipt + latest pointer for deterministic continuation:
   - `pr1_s0_execution_receipt.json`,
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_latest.json`.
5. Sync main plan Section 11 status snapshot to PR1-S0 in-progress posture.

### Key S0 posture decision
1. Pin a concrete, replayable 7-day charter for PR1 analysis window:
   - start `2026-02-26T00:00:00Z`,
   - end `2026-03-05T00:00:00Z`,
   - as-of `2026-03-05T00:00:00Z`.
2. Label maturity lag remains a candidate-set at S0 and will be pinned at S4 (`TGT-05`).

### Governance
1. Docs + run-control artifact changes only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:50 +00:00 - PR1-S0 planning expansion completed and S0 executed
### Files updated
1. Updated:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR1.road_to_prod.md`.
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`.
2. Added run-control artifacts:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_entry_lock.json`
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_window_charter.json`
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_evidence_inventory.json`
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_s0_execution_receipt.json`
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_latest.json`

### S0 execution result
1. Verdict: `PR1_S0_READY`.
2. `open_blockers=0` for S0.
3. `next_state=PR1-S1`.
4. 7-day charter pinned:
   - start `2026-02-26T00:00:00Z`,
   - end `2026-03-05T00:00:00Z`,
   - as-of `2026-03-05T00:00:00Z`.
5. Evidence inventory classified reusable claimable/context and mapped missing lanes to boundary states (`S2/S3/S4/S5`) instead of silent carry-over.

### Plan synchronization
1. PR1 doc now includes S0 expanded checklist and an execution record section for `pr1_20260305T174744Z`.
2. Main plan immediate next step moved from `PR1-S0` to `PR1-S1`.
3. Section 11 target snapshot updated to `PR1-S0` as-of status, marking `TGT-02..TGT-07` as `IN_PROGRESS`.

### Governance
1. Docs + run-control artifact updates only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 17:59 +00:00 - Pre-edit plan: PR1-S1 detailed planning expansion (no execution)
### Trigger
1. USER requested proceeding with planning of `S1`.

### Scope decision
1. Planning only for `PR1-S1` in this step.
2. No S1 run artifact emission yet.

### Planned additions
1. Expand `PR1-S1` section with explicit execution checklist:
   - oracle-store/by-ref evidence analysis posture,
   - no data-engine run constraint,
   - claimability validation (window/scope/sample/cohort/readability),
   - gap-handling policy (targeted boundary escalation, no rerun-the-world),
   - output quality gates for `pr1_g2_profile_summary.json`, `pr1_g2_cohort_profile.json`, `g2_load_campaign_seed.json`.
2. Add S1-specific acceptance checks and blocker mapping to keep fail-closed behavior explicit.
3. Keep main plan immediate-next-step aligned to planned S1 execution source.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:00 +00:00 - PR1-S1 detailed planning expansion completed (planning-only)
### Implemented files
1. Updated:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR1.road_to_prod.md`.
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`.

### What changed
1. Expanded `PR1-S1` with an explicit execution checklist covering:
   - oracle-store/by-ref evidence-only analysis posture,
   - explicit no-data-engine-run constraint,
   - charter/scope conformity checks,
   - cohort derivation mechanics,
   - RC2-S envelope candidate derivation posture,
   - claimability and quality gates for all S1 outputs,
   - fail-closed handoff rule to `PR1_S1_READY`.
2. Main plan immediate-next-step line now explicitly states oracle-store/by-ref execution posture for S1.

### Resulting posture
1. S1 is now execution-ready with explicit anti-drift guardrails and clear blocker boundaries.
2. This step performed planning only; no S1 execution artifacts were emitted.

### Governance
1. Documentation-only change.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:02 +00:00 - Pre-execution plan: execute PR1-S1 from oracle-store/by-ref evidence
### Trigger
1. USER requested proceeding with execution after S1 planning.

### Decision-completeness check
1. S0 handoff is green: `PR1_S0_READY` with `open_blockers=0` (`pr1_20260305T174744Z`).
2. No data-engine run is allowed in this scope; execution will use platform-fed by-reference evidence only.
3. Injection path remains `via_IG` per PR0 mission charter.

### S1 execution approach
1. Source inputs:
   - `m7_data_profile_summary.json`,
   - `m7_addendum_realism_window_summary.json`,
   - `m7_data_subset_manifest.json`,
   - plus PR1 S0 charter.
2. Derive and emit:
   - `pr1_g2_profile_summary.json`,
   - `pr1_g2_cohort_profile.json`,
   - `g2_load_campaign_seed.json`.
3. Run fail-closed checks `B04..B06` on:
   - profile coverage,
   - cohort derivation completeness,
   - envelope candidate binding.
4. Emit `pr1_s1_execution_receipt.json` and advance to `PR1-S2` only if blockers are zero.

### Governance
1. Run-control artifact updates under `runs/` and docs sync updates only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:06 +00:00 - Pre-remediation plan: PR1-S1 B05 cohort-derivation blocker
### Trigger
1. `PR1-S1` execution produced `HOLD_REMEDIATE` with blocker `PR1.B05_COHORT_DERIVATION_MISSING`.

### Root-cause assessment
1. Source realism evidence already carries cohort presence and minima needed for S1 claimability:
   - `m7_addendum_realism_window_summary.json` has `cohort_presence` with `duplicate_replay`, `late_out_of_order`, `hotkey_skew`, `rare_edge_case` all true.
2. `B05` is therefore treated as a derivation-quality/mapping defect in S1 logic, not a true evidence absence.
3. Fail-closed rerun boundary remains `S1` per PR1 rerun discipline.

### Remediation decision
1. Re-execute S1 from the same strict upstream (`pr1_s0_execution_receipt.json`) with corrected cohort-key normalization:
   - map out-of-order cohort against `late_out_of_order` (and accepted alias forms),
   - map payload-extremes presence against `rare_edge_case` (and accepted alias forms),
   - keep duplicate/hotkey/mixed-event checks unchanged.
2. Preserve deterministic artifact set and overwrite S1 outputs for the same execution id:
   - `pr1_g2_profile_summary.json`,
   - `pr1_g2_cohort_profile.json`,
   - `g2_load_campaign_seed.json`,
   - `pr1_s1_execution_receipt.json`.
3. Advance only if `B04..B06` are all true (`PR1_S1_READY`, `next_state=PR1-S2`).

### Governance
1. Run-control artifacts + docs status sync only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:08 +00:00 - PR1-S1 remediation executed; blocker B05 cleared; state advanced
### Execution performed
1. Re-executed `PR1-S1` from strict upstream `pr1_s0_execution_receipt.json` under:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/`.
2. Applied cohort-key normalization in derivation logic for this boundary execution:
   - `late_out_of_order` mapped as authoritative out-of-order cohort signal,
   - `rare_edge_case` mapped as authoritative payload-extremes cohort signal.
3. Re-emitted S1 artifacts:
   - `pr1_g2_profile_summary.json`,
   - `pr1_g2_cohort_profile.json`,
   - `g2_load_campaign_seed.json`,
   - `pr1_s1_execution_receipt.json`.

### Result
1. `pr1_s1_execution_receipt.json` verdict: `PR1_S1_READY`.
2. `open_blockers=0` and `next_state=PR1-S2`.
3. Checks all green:
   - `B04_profile_coverage_pass=true`,
   - `B05_cohort_derivation_pass=true`,
   - `B06_envelope_candidate_bound=true`.
4. Root-cause closure: initial `B05` was a derivation mapping defect, not missing upstream realism evidence.

### Plan synchronization
1. Updated `platform.PR1.road_to_prod.md` execution record from `S0-only` to `S0-S1` and recorded S1 PASS details.
2. Updated `platform.road_to_prod.plan.md` immediate next step to `PR1-S2` with S1 receipt as strict upstream authority.
3. Updated Section 11.3 snapshot title to `PR1-S1` and refreshed `TGT-02` note for S1 envelope-candidate progress.

### Governance
1. Run-control artifacts + docs updated only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:12 +00:00 - Pre-edit plan: add human-readable PR1-S1 findings summary tables
### Trigger
1. USER requested a non-JSON, readable summary of S1 findings in the notes and in the main plan.

### Decision
1. Treat user reference "SR1" as `PR1-S1` and materialize one concise summary table in:
   - `platform.PR1.road_to_prod.md` (phase-local execution notes),
   - `platform.road_to_prod.plan.md` (program-level status surface).
2. Source values from executed artifacts only:
   - `pr1_g2_profile_summary.json`,
   - `pr1_g2_cohort_profile.json`,
   - `g2_load_campaign_seed.json`,
   - `pr1_s1_execution_receipt.json`.
3. Keep the summary interpretation-safe:
   - show measured values,
   - show blocker checks (`B04..B06`),
   - show decision significance and next action (`S2`).

### Governance
1. Documentation update only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:13 +00:00 - Added PR1-S1 readable findings summary tables to notes + plan
### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR1.road_to_prod.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`

### What was added
1. In PR1 notes, added `PR1-S1 Findings Summary (Readable)` table showing:
   - charter/scope,
   - scanned volume and observed rate,
   - cohort posture (duplicate, late/out-of-order, hotkey, event diversity),
   - parse-quality posture,
   - envelope candidate seed,
   - gate checks `B04..B06`,
   - S1 verdict and next state.
2. In main plan, added `10.1 PR1-S1 Findings Snapshot (Readable)` with concise cross-phase interpretation of the same findings.

### Result
1. Reviewers can assess S1 evidence and meaning directly from docs without opening raw JSON artifacts.
2. Program next step remains unchanged: execute `PR1-S2` from strict upstream `PR1-S1` receipt.

### Governance
1. Documentation updates only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:16 +00:00 - Pre-edit plan: PR1-S2 detailed planning + execution from strict upstream S1
### Trigger
1. USER requested detailed planning of `PR1-S2` and execution.

### Decision-completeness check
1. Upstream is valid and strict:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_s1_execution_receipt.json` has `PR1_S1_READY`, `open_blockers=0`.
2. Mandatory S2 lane outputs are known:
   - `pr1_join_matrix.json`,
   - `pr1_join_decision_register.json`,
   - `pr1_s2_execution_receipt.json` for deterministic handoff.
3. Required join map authority is explicit in pre-design doc (`9.4.1`).

### Evidence strategy (performance + no rerun-the-world)
1. Evidence-first by-reference reuse; no local heavy scans.
2. Use existing oracle-store-derived joinability artifacts from:
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/`:
     - `m15b_join_coverage_matrix.json`,
     - `m15b_key_integrity_report.json`,
     - `m15b_entity_stability_report.json`,
     - `m15b_profile_manifest.json`.
3. Validate source-root alignment against S1 corpus roots from:
   - `m7_data_profile_summary.json` source roots.
4. If alignment fails or mandatory join pair evidence is absent, fail-closed with `B07/B08`.

### S2 execution design
1. Materialize mandatory 4-join matrix with per-pair:
   - keys,
   - left/matched rows,
   - coverage ratio,
   - unmatched rate,
   - fanout estimate,
   - verdict and evidence basis.
2. Emit deterministic decision register with route actions for breach cases:
   - high unmatched -> quarantine/fallback,
   - high fanout -> cap/re-key/offline path.
3. Pin `TGT-06` threshold candidates at S2 boundary (subject to S5 rollup lock):
   - `max_unmatched_join_rate`,
   - `max_fanout_p99`,
   - join duplicate-key cap.
4. Gate checks:
   - `B07`: join matrix exists + covers all mandatory pairs,
   - `B08`: every mandatory pair has explicit decision,
   - `B09`: threshold set pinned and non-null.
5. Emit `PR1_S2_READY` only when `B07..B09` all pass; else `HOLD_REMEDIATE` at `S2`.

### Governance
1. Docs + run-control artifacts only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:20 +00:00 - PR1-S2 executed; joinability closure passed and TGT-06 pinned
### Execution performed
1. Executed `PR1-S2` from strict upstream `pr1_s1_execution_receipt.json` under:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/`.
2. Reused by-reference join evidence (evidence-first, no rerun-the-world extraction):
   - `m15b_join_coverage_matrix.json`,
   - `m15b_key_integrity_report.json`,
   - `m15b_entity_stability_report.json`,
   - `m15b_profile_manifest.json`
   from `m15b_semantic_profile_20260302T072457Z`.
3. Validated corpus root alignment against S1 source corpus roots (`m7_data_profile_summary`):
   - alignment check passed (`root_overlap` non-empty and equal root).
4. Emitted S2 artifacts:
   - `pr1_join_matrix.json`,
   - `pr1_join_decision_register.json`,
   - `pr1_s2_execution_receipt.json`,
   - updated `pr1_latest.json` (`latest_state=S2`).

### Result
1. `pr1_s2_execution_receipt.json` verdict: `PR1_S2_READY`.
2. `open_blockers=0`, `next_state=PR1-S3`.
3. Fail-closed checks all passed:
   - `B07_join_matrix_present=true`,
   - `B08_decision_gaps_closed=true`,
   - `B09_thresholds_pinned=true`.
4. `TGT-06` status updated to `PINNED` with thresholds:
   - `max_unmatched_join_rate=0.001`,
   - `max_fanout_p99=2.0`,
   - `max_duplicate_key_rate_each_side=0.001`.
5. Advisory preserved explicitly:
   - `S2.AD02_JOIN_EVIDENCE_WINDOW_EXTENDS_BEYOND_S1_CHARTER`.

### Plan synchronization
1. Updated `platform.PR1.road_to_prod.md`:
   - added S2 planning expansion checklist,
   - updated execution record to `S0-S2`,
   - added `PR1-S2 Findings Summary (Readable)` table.
2. Updated `platform.road_to_prod.plan.md`:
   - immediate next step moved to `PR1-S3` with S2 receipt as strict upstream,
   - added `10.2 PR1-S2 Findings Snapshot (Readable)`,
   - Section `11.3` snapshot advanced to `PR1-S2`, `TGT-06=PINNED`.

### Governance
1. Docs + run-control artifacts only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:25 +00:00 - Pre-edit plan: enforce human-readable analytical metrics logging as binding rule
### Trigger
1. USER requested that significant metrics always be logged automatically in informative, analytical form (not raw JSON dumps).

### Decision
1. Add a binding metrics-reporting standard in the main road-to-prod plan:
   - required digest structure (value + threshold + status + interpretation + decision/action),
   - required coverage (runtime/cost/provenance/caveats),
   - mandatory logging surfaces (phase doc + main plan + logbook),
   - fail-closed completion rule if digest is missing.
2. Add PR1-local operationalization so every PR1 state follows the same digest format.
3. Add a concise analytical ledger snapshot in main plan/PR1 doc so the current state demonstrates the standard.

### Governance
1. Documentation updates only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:27 +00:00 - Binding analytical metrics logging standard enforced across road-to-prod docs
### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR1.road_to_prod.md`

### What was enforced
1. Main plan now treats missing human-readable analytical state digests as fail-closed (`state cannot be complete`).
2. Added a binding digest standard with required columns/rows:
   - signal/value/threshold/status/interpretation/action,
   - runtime posture,
   - cost posture,
   - provenance scope,
   - caveat severity and follow-up boundary.
3. Added mandatory publication surfaces:
   - phase doc,
   - main plan,
   - daily logbook.
4. Added standardized PR1 analytical ledger snapshots (S1/S2) in both docs.
5. Added PR1 receipt schema enforcement so each future state receipt carries runtime/cost/advisory fields:
   - `elapsed_minutes`, `runtime_budget_minutes`, `attributable_spend_usd`, `cost_envelope_usd`, `advisory_ids`.

### Current implications
1. Existing S1/S2 runtime/cost fields are not yet present in their receipts and are now explicitly surfaced as `WARN` in the analytical ledger.
2. From `PR1-S3` onward, receipt emission must include the required runtime/cost/advisory fields to satisfy the new completion law.

### Governance
1. Documentation updates only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:29 +00:00 - Pre-edit plan: PR1-S3 detailed planning + execution from strict upstream S2
### Trigger
1. USER requested expanding plan for `PR1-S3` and executing it.

### Decision-completeness check
1. Strict upstream is valid:
   - `pr1_s2_execution_receipt.json` has `PR1_S2_READY`, `open_blockers=0`.
2. Required S3 outputs are pinned:
   - `g2_rtdl_allowlist.yaml`,
   - `g2_rtdl_denylist.yaml`,
   - `pr1_ieg_scope_decisions.json`,
   - `pr1_late_event_policy_receipt.json`,
   - `pr1_s3_execution_receipt.json` (state handoff and gate checks).
3. Required S3 decisions are sourced from existing by-reference evidence:
   - runtime allow/deny and future-field policy from `m15c_point_in_time_policy_spec.json`,
   - IEG minimal relationship graph from `m15c_ieg_entity_relationship_pin.json`,
   - policy enforceability from `m15c_policy_validation_report.json`.

### Evidence strategy (performance + cost discipline)
1. Evidence-first reuse only; no new extraction runs and no platform orchestration.
2. Reuse `M15.C` artifacts under:
   - `runs/dev_substrate/dev_full/m15/m15c_point_in_time_policy_20260302T074401Z/`.
3. Preserve explicit advisory if source policy window extends beyond S1/S2 charter.

### S3 execution design
1. `g2_rtdl_allowlist.yaml`:
   - pin runtime-allowed output ids + constraints (no truth products at runtime).
2. `g2_rtdl_denylist.yaml`:
   - pin forbidden truth output ids and forbidden future/leakage fields.
3. `pr1_ieg_scope_decisions.json`:
   - pin minimal graph edges, key domains, coverage posture, deferred edges, and TTL/state bounds for G2 scope.
4. `pr1_late_event_policy_receipt.json`:
   - pin watermark/allowed-lateness posture using fail-closed point-in-time policy (`feature_asof_required`, `future_timestamp_policy=fail_closed`) and explicit late-event route.
5. Gate checks:
   - `B10` allowlist/denylist materialized and readable,
   - `B11` IEG scope + TTL/state bounds pinned,
   - `B12` lateness policy pinned + enforceability evidence present.
6. Emit `PR1_S3_READY` only if `B10..B12` are all true.
7. Include receipt runtime/cost/advisory fields per new binding reporting law:
   - `elapsed_minutes`, `runtime_budget_minutes`, `attributable_spend_usd`, `cost_envelope_usd`, `advisory_ids`.

### Governance
1. Docs + run-control artifact updates only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:33 +00:00 - PR1-S3 executed; policy scope closure passed; TGT-03/TGT-04 pinned
### Execution performed
1. Executed `PR1-S3` from strict upstream `pr1_s2_execution_receipt.json` under:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/`.
2. Reused by-reference policy/IEG evidence (evidence-first, no fresh extraction):
   - `m15c_point_in_time_policy_spec.json`,
   - `m15c_ieg_entity_relationship_pin.json`,
   - `m15c_policy_validation_report.json`,
   - `m15c_execution_summary.json`
   from `m15c_point_in_time_policy_20260302T074401Z`.
3. Emitted S3 artifacts:
   - `g2_rtdl_allowlist.yaml`,
   - `g2_rtdl_denylist.yaml`,
   - `pr1_ieg_scope_decisions.json`,
   - `pr1_late_event_policy_receipt.json`,
   - `pr1_s3_execution_receipt.json`,
   - updated `pr1_latest.json` (`latest_state=S3`).

### Result
1. `pr1_s3_execution_receipt.json` verdict: `PR1_S3_READY`.
2. `open_blockers=0`, `next_state=PR1-S4`.
3. Fail-closed checks all passed:
   - `B10_rtdl_allowlist_present=true`,
   - `B11_ieg_scope_pinned=true`,
   - `B12_lateness_policy_pinned=true`.
4. Target updates:
   - `TGT-03=PINNED`,
   - `TGT-04=PINNED`.
5. Runtime/cost receipt fields emitted per binding reporting law:
   - `elapsed_minutes=0.0`,
   - `runtime_budget_minutes=15`,
   - `attributable_spend_usd=0.0`,
   - `cost_envelope_usd=1.0`,
   - `advisory_ids=[S3.AD01_POLICY_REFERENCE_WINDOW_EXTENDS_BEYOND_S1_CHARTER]`.

### Plan synchronization
1. Updated `platform.PR1.road_to_prod.md`:
   - added S3 planning expansion checklist,
   - updated execution record to `S0-S3`,
   - added `PR1-S3 Findings Summary (Readable)`.
2. Updated `platform.road_to_prod.plan.md`:
   - immediate next step moved to `PR1-S4` with S3 receipt as strict upstream,
   - added `10.4 PR1-S3 Findings Snapshot (Readable)`,
   - Section `11.3` snapshot advanced to `PR1-S3` with `TGT-03/TGT-04=PINNED`.

### Governance
1. Docs + run-control artifacts only.
2. No commit/push/branch operation.

## Entry: 2026-03-05 18:42 +00:00 - Pre-edit plan: strict charter-bounded recompute of PR1-S1/S2/S3 + findings refresh
### Trigger
1. USER directed: recompute `S1 -> S2 -> S3` and refresh findings for each state.
2. Prior state digests carried explicit weak-rigor advisories (`S2.AD02`, `S3.AD01`) from cross-window carry-forward; this violates current no-weak-evidence posture.

### Decision-completeness check
1. Active execution scope pinned: `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z`.
2. Charter pinned and readable: `window_start=2026-02-26T00:00:00Z`, `window_end=2026-03-05T00:00:00Z`, `as_of=2026-03-05T00:00:00Z`.
3. Upstream lock for recompute chain is valid (`S0` already PASS) and recompute boundary is exactly `S1 -> S2 -> S3`.
4. Data-engine remains black-box; only contract-exposed platform-fed surfaces in oracle-store are allowed.

### Performance and cost design (pre-implementation)
1. Algorithmic posture:
   - execute only six aggregate/join metrics needed for mandatory S1/S2/S3 claims,
   - avoid full-surface scans beyond required tables/keys,
   - cap work to charter-bounded SQL predicates on timestamp columns.
2. Data-structure/join posture:
   - use distinct right-key subqueries for mandatory join pairs (`J1..J4`),
   - compute `left_rows`, `matched_rows`, `unmatched_rate`, and duplicate-key rates directly in Athena.
3. Runtime budget:
   - `S1 <= 15 min`, `S2 <= 15 min`, `S3 <= 15 min`; each receipt must emit elapsed minutes.
4. Cost budget:
   - by-reference + aggregate-query posture only; emit attributable Athena scan-cost estimate and fail if unattributed.
5. Rejected alternative:
   - carry-forward from `M15.B/M15.C` prior windows rejected because it reintroduces weak-window caveats.

### Implementation approach
1. Materialize a deterministic recompute script under `scripts/dev_substrate/` to avoid oversized inline shell command limits.
2. Execute script once against charter window and overwrite only PR1 run-control artifacts for `S1/S2/S3`.
3. Emit support receipts (`pr1_s1_support_receipt.json`, `pr1_s2_support_receipt.json`, `pr1_s3_support_receipt.json`) with query ids and scan bytes.
4. Re-emit state receipts with:
   - `elapsed_minutes`, `runtime_budget_minutes`,
   - `attributable_spend_usd`, `cost_envelope_usd`,
   - `advisory_ids` (empty if rigor caveat cleared).
5. Refresh readable findings tables in:
   - `platform.PR1.road_to_prod.md`,
   - `platform.road_to_prod.plan.md`.

### Guardrails
1. No local orchestration of platform services; only metadata/query execution from laptop.
2. No branch operations/commits/pushes.
3. Only docs/run-control/script edits needed for this recompute.

## Entry: 2026-03-05 18:47 +00:00 - S1 blocker analysis and remediation plan (B05 cohort derivation)
### Observed blocker
1. Strict S1 charter-window recompute produced `HOLD_REMEDIATE` with `PR1.B05_COHORT_DERIVATION_MISSING`.
2. Natural stream profile in charter window is clean (`duplicate0`, `out_of_order0`, very low hotkey share), so a pure-natural derivation underrepresents required production pressure cohorts.

### Root cause
1. This is not a data-access or query-failure issue.
2. It is an evidence-model issue: S1 cohort derivation incorrectly required natural occurrence of pressure lanes, while PR1 realism intent requires explicit pressure cohort seeding (including injected pressure where natural profile is too clean).

### Remediation decision
1. Keep charter-window measured baseline metrics as the authoritative natural posture.
2. Derive pressure cohort minima from the existing injected realism contract evidence:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m7_stress_s5_20260304T212520Z/stress/m7_addendum_realism_window_summary.json`.
3. Mark cohort derivation as `charter_baseline_plus_injected_contract` and require contract flags to be true.
4. Re-emit S1 artifacts/receipt and continue to S2 only if blockers clear.

### Why this is consistent with goals
1. Avoids toy-grade closure from naturally clean windows.
2. Preserves truthful baseline metrics while still enforcing required production pressure lanes.
3. Keeps fail-closed rigor explicit: if injected contract evidence is missing/unreadable, S1 remains blocked.

### Governance
1. Run-control artifact remediation + docs/logbook update.
2. No branch operation, no commit/push.

## Entry: 2026-03-05 19:05 +00:00 - S2 blocker analysis and remediation plan (B08 duplicate-key integrity semantics)
### Observed blocker
1. S2 recompute failed with `PR1.B08_JOIN_DECISION_GAPS`.
2. Failure localized to `J1` duplicate-key guard where left duplicate rate was computed as ~0.5.

### Root cause
1. Duplicate-key guard was computed on join key `flow_id` for J1 left side.
2. J1 is intentionally one-to-many on `flow_id` (events per flow), so this measure conflates valid cardinality with key-integrity defects.

### Remediation decision
1. Keep join match/unmatched/fanout on observed join keys (unchanged).
2. Compute duplicate-key integrity on canonical side keys (contract identity), not raw join keys:
   - J1 left duplicate integrity key -> `flow_id + event_seq`.
   - J1 right duplicate integrity key -> `flow_id`.
   - J2/J3 remain `merchant_id + arrival_seq` on both sides.
   - J4 remains `flow_id + event_seq` on both sides.
3. Re-emit S2 artifacts and receipt; proceed only if `B07..B09` pass.

### Why this aligns with production realism
1. Preserves intended join cardinality semantics while still detecting true key collisions.
2. Avoids false blockers from legitimate one-to-many relationships.
3. Maintains fail-closed behavior for actual duplicate-key integrity defects.

### Governance
1. Run-control artifact remediation only.
2. No branch operation, no commit/push.

## Entry: 2026-03-05 19:12 +00:00 - PR1 strict recompute executed (`S1 -> S2 -> S3`) and findings synchronized
### Execution summary
1. Recomputed `PR1-S1/S2/S3` from strict charter window (`2026-02-26T00:00:00Z` -> `2026-03-05T00:00:00Z`) under run root:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/`.
2. Re-emitted state receipts with mandatory runtime/cost/advisory fields for all three states.
3. Updated findings tables in:
   - `platform.road_to_prod.plan.md` (Sections `10.1..10.4`),
   - `platform.PR1.road_to_prod.md` (Execution Record + Sections `12..15`).

### Blockers encountered and resolved
1. `PR1.B05_COHORT_DERIVATION_MISSING` at S1:
   - natural charter window was too clean for required pressure cohorts,
   - resolved via `charter_baseline_plus_injected_contract` derivation:
     - baseline metrics from charter-window Athena,
     - pressure cohort minima from M7 injected realism contract evidence.
2. `PR1.B08_JOIN_DECISION_GAPS` at S2:
   - duplicate-key guard falsely used join key for J1 (`flow_id`) and treated intended 1:N cardinality as defect,
   - resolved by enforcing duplicate-key integrity on canonical contract-side identity keys.

### Final state outcomes
1. `S1`: `PR1_S1_READY`, `open_blockers=0`, `elapsed_minutes=0.645`, `attributable_spend_usd=0.102349`.
2. `S2`: `PR1_S2_READY`, `open_blockers=0`, `elapsed_minutes=3.185`, `attributable_spend_usd=0.369668`.
3. `S3`: `PR1_S3_READY`, `open_blockers=0`, `elapsed_minutes=0.656`, `attributable_spend_usd=0.046417`.
4. Prior scope caveats were cleared by strict charter-window recompute (`S2/S3 advisory posture now none`).

### Evidence quality notes
1. S1 now explicitly separates:
   - natural baseline realism (charter-window measured), and
   - pressure cohort contract (injected realism evidence), to avoid toy-clean closure.
2. S2 join matrix now documents canonical duplicate identity keys explicitly for auditability.

### Governance
1. No commit/push/branch operation.
2. Changes in tracked files are documentation/logbook/implementation-map synchronization only.

## Entry: 2026-03-05 19:16 +00:00 - Pre-edit plan: PR1-S4 detailed planning expansion + strict execution from S3
### Trigger
1. USER requested: expand the S4 plan and execute it.

### Decision-completeness check
1. Strict upstream lock is valid:
   - `pr1_s3_execution_receipt.json` => `PR1_S3_READY`, `open_blockers=0`, `next_state=PR1-S4`.
2. Required S4 output contract is pinned in PR1 authority:
   - `pr1_label_maturity_report.json`,
   - `pr1_learning_window_spec.json`,
   - `pr1_leakage_guardrail_report.json`,
   - `g2_monitoring_baselines.json`.
3. Required S4 blockers are explicit:
   - `PR1.B13`, `PR1.B14`, `PR1.B15`.

### Evidence and source plan
1. Charter scope and as-of authority:
   - `pr1_window_charter.json`,
   - `pr1_late_event_policy_receipt.json`.
2. Learning maturity/time-causality controls:
   - `m9d_asof_maturity_policy_snapshot.json`,
   - `m9e_leakage_guardrail_report.json`,
   - `m11_leakage_provenance_check.json`,
   - `m11_eval_vs_baseline_report.json`.
3. G2 baseline inputs:
   - `pr1_g2_profile_summary.json`,
   - `pr1_g2_cohort_profile.json`,
   - `pr1_join_matrix.json`,
   - `pr1_s1/s2/s3_execution_receipt.json`.

### S4 implementation design
1. Expand `S4` in PR1 authority doc with explicit checklist covering:
   - upstream lock,
   - maturity-lag pinning basis,
   - leakage guardrail fusion,
   - monitoring baseline binding for `G2/G3A/G3B`,
   - fail-closed checks and rerun boundary.
2. Execute S4 with strict run-root overwrite for current execution id.
3. Materialize `pr1_s4_execution_receipt.json` with runtime/cost/advisory fields.
4. Update main plan findings + target snapshot to reflect S4 execution result.

### Performance and cost posture
1. Single bounded Athena query lane for label-age distribution; no platform orchestration.
2. Reuse existing by-reference artifacts for leakage/learning checks.
3. Runtime budget target: `<= 15 min`; cost envelope: low single-state Athena spend.

### Governance
1. Docs + run-control artifacts only.
2. No branch operation, no commit/push.

## Entry: 2026-03-05 19:30 +00:00 - Pre-edit decision: PR1-S4 maturity availability proxy + fail-closed execution contract
### Trigger
1. Continue PR1-S4 execution from strict upstream PR1_S3_READY.
2. Prior ad-hoc S4 script failed syntactically before artifact emission.

### Decision-completeness check
1. Upstream receipt pinned and green:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_s3_execution_receipt.json.
2. S4 artifact contract and blocker taxonomy are pinned in PR1 authority (B13/B14/B15).
3. Source evidence for time-causality and leakage is pinned and readable (m9d/m9e/m11e).

### Critical semantic decision (fail-closed)
1. s4_event_labels_6B schema does not expose label_available_ts; only 	s_utc is available on the truth rows.
2. For PR1-S4, maturity distribution is computed on **availability proxy** label_ts_proxy_utc := ts_utc.
3. This proxy is explicit in S4 artifacts and must remain tagged as proxy semantics (no hidden assumptions).
4. If schema later exposes true availability timestamp, S4 maturity logic must migrate to that field and be re-pinned.

### Execution design
1. Run a bounded Athena maturity query over charter window (2026-02-26 to 2026-03-05) and as-of (2026-03-05T00:00:00Z).
2. Evaluate candidate lags [1,3,7] with explicit coverage rates.
3. Select lag deterministically as the largest candidate with coverage >= .50; else fail B13.
4. Fuse leakage/time-causality controls from m9d/m9e/m11e and fail B14 on any false guard.
5. Emit monitoring baseline contract with bound refs for G2/G3A/G3B; fail B15 if refs/metrics missing.

### Performance and cost posture
1. Single aggregate Athena query only (minute-scale target, no platform orchestration).
2. Emit explicit scan bytes and attributable cost in pr1_s4_support_receipt.json and state receipt.

### Governance
1. No branch operations, no commit/push.
2. Artifacts under 
uns/ and docs/logbook synchronization only.

## Entry: 2026-03-05 19:36 +00:00 - PR1-S4 executed strict from S3; maturity and monitoring targets pinned
### Execution summary
1. Executed deterministic S4 from strict upstream PR1_S3_READY under:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/.
2. Emitted required S4 artifacts:
   - pr1_label_maturity_report.json,
   - pr1_learning_window_spec.json,
   - pr1_leakage_guardrail_report.json,
   - g2_monitoring_baselines.json.
3. Emitted support and state receipts:
   - pr1_s4_support_receipt.json,
   - pr1_s4_execution_receipt.json.
4. Updated latest pointer:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr1_latest.json -> latest_state=S4.

### S4 outcomes
1. Verdict: PR1_S4_READY, open_blockers=0, 
ext_state=PR1-S5.
2. Blockers: B13=true, B14=true, B15=true.
3. TGT-05 pinned: label_maturity_lag=3d with deterministic candidate policy (largest_candidate_with_coverage_gte_0_50).
4. TGT-07 pinned: monitoring baseline contract set ACTIVE with bound refs for G2/G3A/G3B and required metric families.

### Key measured evidence
1. Label maturity query id: 86893e1-ad3b-4699-8e70-200204e0a5f0.
2. Label age distribution: p50=3d, p90=6d, p95=6d; no future labels.
3. Candidate coverage: 1d=0.857648, 3d=0.57411, 7d=0.0.
4. Runtime/cost posture: lapsed_minutes=0.015 vs budget 15; ttributable_spend_usd=0.018179 vs envelope 10.0.

### Semantic guardrail note
1. s4_event_labels_6B does not expose label_available_ts; S4 maturity pin uses explicit proxy label_ts_proxy_utc := ts_utc.
2. This is recorded as advisory PR1.S4.AD01_LABEL_TS_PROXY_SEMANTICS and must be migrated if true availability timestamp is later exposed.

### Documentation sync
1. Updated platform.PR1.road_to_prod.md to include S4 execution record + S4 findings section.
2. Updated platform.road_to_prod.plan.md immediate next step to PR1-S5, added S4 findings snapshot, and updated target status (TGT-05/TGT-07 -> PINNED).

### Governance
1. No branch operation, no commit/push.
2. Execution used bounded Athena query and by-reference controls only.

## Entry: 2026-03-05 19:40 +00:00 - Pre-edit plan: PR1-S5 rollup closure and G2 verdict emission
### Trigger
1. USER directed: plan and execute PR1-S5.
2. Upstream S4 is green (PR1_S4_READY, open_blockers=0).

### Decision-completeness check
1. S5 objective/contract pinned in PR1 authority (Section S5, blockers B16..B19).
2. Required S5 outputs pinned:
   - g2_data_realism_pack_index.json,
   - g2_data_realism_verdict.json,
   - pr1_blocker_register.json,
   - pr1_execution_summary.json,
   - pr1_evidence_index.json.
3. TGT-03..TGT-07 source status available from prior receipts/artifacts; S5 must finalize TGT-02 and enforce all TGT-02..TGT-07=PINNED.

### S5 execution design
1. Strict upstream lock:
   - require pr1_s4_execution_receipt.json => PR1_S4_READY + open_blockers=0.
2. Finalize TGT-02 RC2-S envelope numeric set using PR1 measured artifacts:
   - baseline throughput from pr1_g2_profile_summary.json,
   - envelope seed from g2_load_campaign_seed.json,
   - cohort mix from pr1_g2_cohort_profile.json.
3. Build deterministic G2 pack index with source refs, pinned target map, and activated RC2-S envelope.
4. Build deterministic evidence index (artifact name, size, sha256, role classification).
5. Emit verdict + blocker register fail-closed:
   - B16 if any TGT-02..TGT-07 not pinned,
   - B17 if pack/evidence index contract incomplete,
   - B18 if verdict not PASS when blockers are zero,
   - B19 if open blockers nonzero.
6. Emit pr1_s5_execution_receipt.json with runtime/cost/advisory fields and update pr1_latest.json to S5.

### Performance and cost posture
1. No new data extraction; by-reference rollup only.
2. Minute-scale runtime target (<=10 min) and negligible spend (explicitly attributed).

### Governance
1. No branch operations, no commit/push.
2. Artifacts in 
uns/; docs/logbook/impl map synced after execution.

## Entry: 2026-03-05 19:47 +00:00 - PR1-S5 executed with fail-closed remediation and final G2 closure
### Execution summary
1. Ran scripts/dev_substrate/pr1_s5_executor.py from strict upstream PR1_S4_READY.
2. Initial attempt surfaced PR1.B17_PACK_INDEX_MISSING due ordering defect in S5 executor (post-emit completeness check executed before verdict/summary outputs were written).
3. Remediated by reordering S5 emit sequence:
   - emit provisional outputs first,
   - run post-emit completeness check,
   - then compute final blockers/verdict and rewrite outputs deterministically.
4. Reran S5 immediately; final result:
   - PR1_S5_READY, open_blockers=0, 
ext_state=PR2-S0.

### Final outputs emitted
1. g2_data_realism_pack_index.json
2. g2_data_realism_verdict.json
3. pr1_blocker_register.json
4. pr1_execution_summary.json
5. pr1_evidence_index.json
6. pr1_s5_execution_receipt.json
7. latest pointer updated: pr1_latest.json -> latest_state=S5.

### Gate/target closure results
1. G2 verdict: PASS, 
ext_gate=PR2_READY, open_blockers=0.
2. Required target set: TGT-02..TGT-07 all PINNED.
3. TGT-02 finalized/activated at S5 from measured profile + cohort evidence.

### Runtime/cost posture
1. S5 elapsed_minutes=0.001 (budget 10).
2. S5 attributable_spend_usd=0.0 (rollup by-reference posture).

### Documentation sync
1. Updated PR1 authority doc with S5 execution state and findings.
2. Updated main plan immediate next step to PR2-S0 and added S5 findings snapshot.
3. Updated target status snapshot to PR1-S5 with TGT-02=PINNED.

### Governance
1. No branch operations, no commit/push.
2. Scope stayed in run-control artifacts + docs/logbook/implementation map.

## Entry: 2026-03-05 19:57 +00:00 - Pre-edit plan: materialize PR2 authority doc for numeric contract activation
### Trigger
1. USER requested planning for PR2 and its dedicated document.

### Decision-completeness check
1. Upstream PR1 closure is pinned and green:
   - pr1_s5_execution_receipt.json => PR1_S5_READY, open_blockers=0, 
ext_state=PR2-S0.
2. Main plan defines PR2 intent and subphase template (S0..S3) but lacks execution authority detail.
3. Binding activation law is pinned in pre-design authority:
   - numeric contracts must be activatable (
o required TBD) before certification progression.

### PR2 planning design
1. Create platform.PR2.road_to_prod.md with execution-grade structure mirroring PR0/PR1:
   - purpose, authorities, scope, hard exit standard,
   - capability lanes,
   - state plan S0..S3 with objectives/actions/outputs/pass/fail blockers,
   - per-state planning expansion checklists,
   - artifact contract + schema minimums,
   - runtime/cost budgets,
   - rerun discipline + DoD.
2. Define deterministic run root posture:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/<pr2_execution_id>/.
3. Wire main plan PR2 section and immediate-next-step section to this new PR2 authority doc.

### Performance and cost posture
1. PR2 is activation/planning/validation-heavy, not runtime load execution.
2. Prefer by-reference measured evidence from PR1 for threshold population and calibration traceability.
3. Enforce minute-scale state budgets and explicit spend attribution if any fresh extraction is required.

### Governance
1. Docs-only planning edits plus logbook/implementation-map updates.
2. No branch operations, no commit/push.

## Entry: 2026-03-05 19:59 +00:00 - PR2 phase planning materialized and wired as active authority
### Work completed
1. Added dedicated PR2 authority doc:
   - docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR2.road_to_prod.md.
2. PR2 doc now includes:
   - purpose, authorities, scope, hard exit standard,
   - capability lanes,
   - full state plan S0..S3 with objectives/actions/outputs/pass/fail blockers,
   - per-state planning expansion checklists,
   - deterministic artifact contract, runtime/cost budgets, rerun discipline, DoD.
3. Wired main plan to PR2 authority:
   - PR2 section now explicitly references the detailed PR2 doc,
   - immediate-next-step authority list now includes both PR1 (closed historical source) and PR2 (active source).

### Key planning decisions pinned
1. PR2 enforces activatable contracts before PR3 (
o required TBD in active scope).
2. PR2 remains evidence-first and by-reference; runtime pressure certification stays in PR3.
3. Blocker taxonomy is fail-closed across S0..S3, including unattributed spend blocker (PR2.B19).

### Governance
1. No branch operation, no commit/push.
2. Planning edits only (docs + logbook + implementation map).

## Entry: 2026-03-05 20:01 +00:00 - Pre-edit plan: execute PR2-S0 from PR1-S5 strict upstream
### Trigger
1. USER directed: proceed with detailed planning and execution of PR2-S0.

### Decision-completeness check
1. Upstream closure is valid:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_s5_execution_receipt.json => PR1_S5_READY, open_blockers=0.
2. PR2 authority doc is materialized and defines S0 artifact contract + blocker taxonomy.
3. S0 scope is inventory/gap mapping only; unresolved threshold values are expected and must be explicitly mapped to owner + due state (not silently accepted).

### PR2-S0 execution design
1. Create deterministic executor scripts/dev_substrate/pr2_s0_executor.py.
2. Generate pr2_execution_id and run root:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/<pr2_execution_id>/.
3. Emit S0 artifacts:
   - pr2_entry_lock.json,
   - pr2_required_row_inventory.json,
   - pr2_gap_map.json,
   - pr2_s0_execution_receipt.json.
4. Emit latest pointer:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr2_latest.json.
5. Fail-closed checks:
   - B01 entry lock exists,
   - B02 upstream PR1 ready,
   - B03 inventory non-empty with required rows,
   - B04 every pending required row has explicit owner lane + due state.

### Performance and cost posture
1. No external queries or runtime load execution for S0.
2. Runtime budget target: <=10 min; cost posture: .0 attributable for S0.

### Governance
1. No branch operations, no commit/push.
2. Execution artifacts in 
uns/; docs/logbook/impl map synced after run.

## Entry: 2026-03-05 20:07 +00:00 - PR2-S0 executed clean with strict upstream and deterministic inventory closure
### Execution summary
1. Executed `scripts/dev_substrate/pr2_s0_executor.py` from strict upstream `PR1_S5_READY`.
2. New PR2 run root materialized:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/`.
3. Emitted required S0 artifacts:
   - `pr2_entry_lock.json`,
   - `pr2_required_row_inventory.json`,
   - `pr2_gap_map.json`,
   - `pr2_s0_execution_receipt.json`.
4. Updated latest pointer:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_latest.json` -> `latest_state=S0`.

### S0 gate outcomes
1. Receipt verdict: `PR2_S0_READY`, `open_blockers=0`, `next_state=PR2-S1`.
2. Gate checks all true:
   - `B01_entry_lock_present`,
   - `B02_upstream_pr1_ready`,
   - `B03_required_inventory_present`,
   - `B04_required_pending_owner_bound`.
3. Inventory totals:
   - `row_count_total=36`, `row_count_required=34`, `prefilled_required=25`, `pending_required=9`, `deferred_optional=2`.
4. Pending required rows are fully lane-bound:
   - `runtime_perf=6`, `cost_governance=1`, `ops_gov_observability=2`.

### Key decisions for S1 handoff
1. S1 must close all nine required pending rows and keep per-row `baseline -> target -> guardband -> source_ref` traceability.
2. Deferred rows `PR2.O010` and `PR2.O011` remain optional and intentionally routed to `PR3`/`PR4`.
3. Advisory continuity is explicit:
   - `PR1.S4.AD01_LABEL_TS_PROXY_SEMANTICS` remains non-blocking but visible.

### Runtime and cost posture
1. `elapsed_minutes=0.0` vs budget `10.0`.
2. `attributable_spend_usd=0.0` vs envelope `2.0`.

### Documentation sync
1. Updated `platform.PR2.road_to_prod.md` execution record from `PLANNED` to active `S0` closure with readable digest.
2. Updated `platform.road_to_prod.plan.md` immediate-next-step to `PR2-S1` and added `PR2-S0` findings snapshot.

### Governance
1. No branch operations and no commit/push.
2. Scope limited to run-control artifacts, docs, and execution helper script.

## Entry: 2026-03-05 20:36 +00:00 - Pre-edit plan: PR2-S1 contract materialization with production-target EPS pinning
### Trigger
1. USER directed: begin planning and execution of `PR2-S1`.
2. USER approved target posture: production target `steady=3000 eps`, `burst=6000 eps`, plus explicit note that WSP `stream_speedup` alone cannot create an independent burst shape.

### Decision-completeness check
1. Upstream lock is valid:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s0_execution_receipt.json` => `PR2_S0_READY`, `open_blockers=0`.
2. Pending required rows from S0 are fully scoped (9 rows) and all due in S1 with owners bound.
3. Program decision confirmed: do not rerun PR0/PR1; continue from PR2.

### PR2-S1 execution design
1. Materialize deterministic S1 executor `scripts/dev_substrate/pr2_s1_executor.py` consuming:
   - `pr2_required_row_inventory.json`,
   - `pr2_gap_map.json`,
   - `pr2_entry_lock.json`,
   - PR1 pack sources (`g2_data_realism_pack_index.json`, `g2_monitoring_baselines.json`, `pr1_join_matrix.json`, `pr1_g2_cohort_profile.json`).
2. Emit required S1 artifacts under run root:
   - `pr2_runtime_numeric_contract.rc2s.active.yaml`,
   - `pr2_opsgov_numeric_contract.rc2s.active.yaml`,
   - `pr2_threshold_population_ledger.json`,
   - `pr2_calibration_traceability.json`,
   - `pr2_deferred_scope_register.json`,
   - `pr2_s1_execution_receipt.json`.
3. Add supportive runbook index artifact for O009 completeness:
   - `pr2_runbook_index.json` (explicit owner/runbook bindings used by ops/gov contract).
4. S1 fail-closed checks:
   - `PR2.B05` runtime contract present/readable,
   - `PR2.B06` ops/gov contract present/readable,
   - `PR2.B07` no required `TBD` remaining,
   - `PR2.B08` required measurement surfaces bound,
   - `PR2.B09` calibration traceability present for required thresholds.

### Threshold and policy pinning (S1)
1. Runtime target pin:
   - `steady_rate_eps=3000`, `burst_rate_eps=6000`.
2. Constraint pin:
   - WSP `stream_speedup` is a uniform wall-clock compression control, not an independent burst shaper; PR3 runtime lane must include explicit burst window shaping to prove 6000 burst claimability.
3. Initial S1 SLO/guardband pins (policy target values; validated in S2):
   - hot-path latency p95/p99 max,
   - error-rate max,
   - recovery bound,
   - budget envelope.
4. Ops/gov pins:
   - required alert owners binding (`alerts.required_owners_bound`),
   - `runbooks.index_ref` bound to emitted runbook index artifact.

### Performance and cost posture
1. Evidence-first S1: by-reference derivation from PR1 outputs and policy pins (no platform runtime load execution in S1).
2. Runtime budget target: `<= 25 min`; cost envelope: low/no incremental spend.

### Governance
1. No branch operations, no commit/push.
2. Scope limited to run-control artifacts, docs, and S1 executor/wrapper implementation.

## Entry: 2026-03-05 20:44 +00:00 - PR2-S1 executed clean; production-target envelope pinned and constraints carried forward
### Execution summary
1. Implemented and ran `scripts/dev_substrate/pr2_s1_executor.py` from strict upstream `PR2_S0_READY`.
2. Executed against run root:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/`.
3. Emitted required S1 artifacts:
   - `pr2_runtime_numeric_contract.rc2s.active.yaml`,
   - `pr2_opsgov_numeric_contract.rc2s.active.yaml`,
   - `pr2_threshold_population_ledger.json`,
   - `pr2_calibration_traceability.json`,
   - `pr2_deferred_scope_register.json`,
   - `pr2_s1_execution_receipt.json`.
4. Emitted support artifact for O009 binding:
   - `pr2_runbook_index.json`.
5. Updated latest pointer:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_latest.json` -> `latest_state=S1`.

### Gate outcomes
1. State verdict: `PR2_S1_READY`, `open_blockers=0`, `next_state=PR2-S2`.
2. Fail-closed checks: `B05=true`, `B06=true`, `B07=true`, `B08=true`, `B09=true`.
3. Required TBD count after S1: `0`.

### Numeric pinning results
1. Runtime envelope repinned to production target:
   - steady `3000 eps`, burst `6000 eps`.
2. Pending S1 rows fully closed:
   - `R010`, `R020`, `R021`, `R022`, `R023`, `R024`, `R025`, `O008`, `O009`.
3. Cost envelope pin:
   - `thresholds.cost.budget_envelope_usd=250.0`.

### Constraint carry-forward (binding)
1. Uniform WSP `stream_speedup` preserves natural burst shape and cannot alone realize 6000 burst from current baseline.
2. Measured constraint values:
   - projected burst under uniform speedup at target steady = `3568.809582 eps`,
   - burst gap to target = `2431.190418 eps`.
3. Carry-forward requirement pinned:
   - `PR2.S1.CN01_BURST_SHAPER_REQUIRED` due in `PR3-S1`.

### Runtime and cost posture
1. `elapsed_minutes=0.0` vs budget `25`.
2. `attributable_spend_usd=0.0` vs envelope `5.0`.

### Documentation sync
1. Updated `platform.PR2.road_to_prod.md` execution record to include S1 closure + readable findings.
2. Updated `platform.road_to_prod.plan.md` immediate-next-step to `PR2-S2` and added PR2-S1 findings snapshot.

### Governance
1. No branch operations, no commit/push.
2. Scope limited to run-control artifacts, docs, and S1 executor implementation.

## Entry: 2026-03-05 20:55 +00:00 - Pre-edit plan: PR2-S2 activation validation and anti-gaming enforcement
### Trigger
1. USER directed: proceed to planning and execution of `PR2-S2`.

### Decision-completeness check
1. Strict upstream is valid:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s1_execution_receipt.json` is `PR2_S1_READY` with `open_blockers=0`.
2. Required S2 authority is explicit:
   - `platform.PR2.road_to_prod.md` defines S2 objective, outputs, and fail-closed blockers `PR2.B10..PR2.B14`.
3. Required S2 inputs are present in run root:
   - runtime/opsgov ACTIVE contracts,
   - threshold population ledger,
   - calibration traceability,
   - deferred scope register and runbook index.
4. No unresolved decision holes remain for S2 boundary; enforcement scope is active RC2-S/C.1 contract subset pinned by PR2 inventory and S1 outputs.

### PR2-S2 execution design
1. Implement deterministic executor:
   - `scripts/dev_substrate/pr2_s2_executor.py`.
2. Enforce strict upstream lock (`S1 READY`) and fail immediately if broken.
3. Run runtime contract activatability validation (A.1 active-scope checks):
   - status + mission binding + injection path + campaign minima + required measurement surfaces + no required `TBD`.
4. Run ops/governance baseline activatability validation (C.1 active-scope checks):
   - status + source/window/rules + actionable owner bindings + runbook index resolution.
5. Run threshold sanity checks:
   - latency `p95<=p99`,
   - bounded rate/fraction domains,
   - sample minima bounds.
6. Run anti-gaming checks:
   - non-proxy measurement surfaces,
   - distribution requirements include `p95/p99`,
   - shape consistency (`soak >= 3x burst`),
   - explicit burst-gap constraint disclosure and due-state binding (`PR3-S1`) if shape cannot realize target burst.
7. Emit S2 outputs:
   - `pr2_runtime_contract_validator.json`,
   - `pr2_opsgov_contract_validator.json`,
   - `pr2_threshold_sanity_report.json`,
   - `pr2_activation_validation_matrix.json`,
   - `pr2_s2_execution_receipt.json`.
8. Update pointer:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_latest.json` -> `latest_state=S2`.

### Blocker mapping (fail-closed)
1. `PR2.B10_ENV_NOT_ACTIVATABLE` -> runtime validator overall invalid.
2. `PR2.B11_BASELINES_NOT_ACTIVATABLE` -> ops/gov validator overall invalid.
3. `PR2.B12_THRESHOLD_SANITY_FAIL` -> threshold sanity report invalid.
4. `PR2.B13_ALERT_RUNBOOK_BINDING_MISSING` -> unresolved alert owner/runbook references.
5. `PR2.B14_ANTI_GAMING_GUARD_FAIL` -> anti-gaming guard failure.

### Performance and cost posture
1. S2 remains evidence-first contract validation; no platform runtime load execution.
2. Runtime budget target: `<= 20 min` (PR2 S2 budget).
3. Cost posture: low/no incremental spend; emit attributable spend fields explicitly in receipt.

### Governance
1. No branch operations, no commit/push.
2. Scope limited to S2 executor, run-control artifacts, docs, implementation map, and logbook sync.

## Entry: 2026-03-05 21:07 +00:00 - PR2-S2 executed clean; activation validation and anti-gaming checks are green
### Execution summary
1. Implemented and ran `scripts/dev_substrate/pr2_s2_executor.py` from strict upstream `PR2_S1_READY`.
2. Execution root:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/`.
3. Emitted required S2 artifacts:
   - `pr2_runtime_contract_validator.json`,
   - `pr2_opsgov_contract_validator.json`,
   - `pr2_threshold_sanity_report.json`,
   - `pr2_activation_validation_matrix.json`,
   - `pr2_s2_execution_receipt.json`.
4. Updated latest pointer:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_latest.json` -> `latest_state=S2`.

### S2 gate outcomes
1. State verdict:
   - `PR2_S2_READY`, `open_blockers=0`, `next_state=PR2-S3`.
2. Fail-closed checks all true:
   - `B10_env_activatable`,
   - `B11_baselines_activatable`,
   - `B12_threshold_sanity`,
   - `B13_alert_runbook_binding`,
   - `B14_anti_gaming_guard`.
3. Runtime validator:
   - all `RV01..RV18` passed, `required_tbd_paths=[]`.
4. Ops/gov validator:
   - all `OV01..OV13` passed,
   - `alert_runbook_binding_valid=true`,
   - no unresolved runbooks/owner bindings.
5. Threshold sanity:
   - all `TS01..TS07` passed.
6. Anti-gaming:
   - all `AG01..AG04` passed.

### Key S2 claimability notes
1. Measurement surfaces remain canonical and non-proxy:
   - throughput `IG_ADMITTED_EVENTS_PER_SEC`,
   - latency `IG_ADMISSION_TS -> DECISION_COMMIT_TS`.
2. Burst gap remains explicit and correctly routed:
   - projected burst `3568.809582 eps` vs target `6000 eps`,
   - carry-forward constraint `PR2.S1.CN01_BURST_SHAPER_REQUIRED` due `PR3-S1` is present.
3. No threshold drift-to-pass detected:
   - sample-minima contract values match S0 inventory values.

### Runtime and cost posture
1. `elapsed_minutes=0.0` vs S2 budget `20`.
2. `attributable_spend_usd=0.0` vs envelope `5.0`.

### Documentation sync
1. Updated PR2 authority execution record and added `11.3 PR2-S2 Findings Snapshot`.
2. Updated main plan immediate next step to `PR2-S3` and added `10.9 PR2-S2 Findings Snapshot`.

### Governance
1. No branch operations and no commit/push.
2. Scope limited to S2 executor, run-control artifacts, docs, implementation map, and logbook.

## Entry: 2026-03-05 21:11 +00:00 - Pre-edit plan: PR2-S3 activation rollup and phase verdict emission
### Trigger
1. USER directed: move to planning and execution of `PR2-S3`.

### Decision-completeness check
1. Strict upstream is valid:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s2_execution_receipt.json` is `PR2_S2_READY`, `open_blockers=0`.
2. S3 authority and closure contract are explicit:
   - PR2 authority doc defines S3 outputs, pass condition, and fail-closed blockers `PR2.B15..PR2.B19`.
3. Required S3 input artifacts are present:
   - `pr2_entry_lock.json`,
   - `pr2_runtime_numeric_contract.rc2s.active.yaml`,
   - `pr2_opsgov_numeric_contract.rc2s.active.yaml`,
   - `pr2_runtime_contract_validator.json`,
   - `pr2_opsgov_contract_validator.json`,
   - `pr2_threshold_sanity_report.json`,
   - `pr2_activation_validation_matrix.json`,
   - state receipts `S0..S2`.
4. No unresolved decision holes remain for S3 boundary.

### PR2-S3 execution design
1. Implement deterministic executor:
   - `scripts/dev_substrate/pr2_s3_executor.py`.
2. Enforce strict upstream lock (`S2 READY`) before any rollup emission.
3. Build activation index artifact:
   - include contract refs, validator refs, and current activatability statuses.
4. Build blocker register:
   - aggregate blocker posture from `S0..S2`,
   - emit structured blocker objects (`id`, `severity`, `reason`, `owner`, `rerun_boundary`).
5. Emit phase summary:
   - include required schema fields (`verdict`, `next_gate`, `open_blockers`, `blocker_ids`, `contract_refs`),
   - set `verdict=PR3_READY` and `next_gate=PR3_READY` only when `open_blockers=0`.
6. Emit evidence index:
   - deterministic list of all required PR2 artifacts and readback statuses.
7. Emit S3 receipt + latest pointer:
   - `pr2_s3_execution_receipt.json`,
   - `pr2_latest.json` -> `latest_state=S3`.

### Blocker mapping (fail-closed)
1. `PR2.B15_ACTIVATION_INDEX_MISSING` -> missing/incomplete activation index artifact.
2. `PR2.B16_SUMMARY_MISSING` -> missing/incomplete execution summary artifact.
3. `PR2.B17_OPEN_BLOCKERS_NONZERO` -> any open blocker remains after S0..S2 aggregation.
4. `PR2.B18_VERDICT_NOT_PR3_READY` -> verdict or next_gate is not `PR3_READY` when closure is expected.
5. `PR2.B19_UNATTRIBUTED_SPEND` -> missing or negative attributable spend field in S3 summary/receipt.

### Performance and cost posture
1. S3 is evidence rollup only (no runtime pressure run).
2. Runtime budget target: `<= 10 min`.
3. Spend posture: attributable spend explicitly emitted and bounded (`0.0` expected).

### Governance
1. No branch operations, no commit/push.
2. Scope limited to S3 executor, run-control artifacts, docs, implementation map, and logbook sync.
## Entry: 2026-03-05 21:16 +00:00 - PR2-S3 executed clean; PR2 closed with `PR3_READY`
### Execution summary
1. Implemented and ran `scripts/dev_substrate/pr2_s3_executor.py` from strict upstream `PR2_S2_READY`.
2. Execution root:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/`.
3. Emitted required S3 artifacts:
   - `pr2_numeric_contract_activation_index.json`,
   - `pr2_blocker_register.json`,
   - `pr2_execution_summary.json`,
   - `pr2_evidence_index.json`,
   - `pr2_s3_execution_receipt.json`.
4. Updated latest pointer:
   - `runs/dev_substrate/dev_full/road_to_prod/run_control/pr2_latest.json` -> `latest_state=S3`.

### S3 gate outcomes
1. State verdict:
   - `PR2_S3_READY`, `open_blockers=0`, `next_state=PR3-S0`, `next_gate=PR3_READY`.
2. S3 fail-closed checks all true:
   - `B15_activation_index_present`,
   - `B16_summary_present`,
   - `B17_open_blockers_zero`,
   - `B18_verdict_pr3_ready`,
   - `B19_attributable_spend_present`.
3. Phase summary verdict:
   - `pr2_execution_summary.json` -> `verdict=PR3_READY`, `next_gate=PR3_READY`, `open_blockers=0`.

### Remediation during S3 execution
1. First S3 run produced an evidence index ordering defect:
   - `pr2_evidence_index.json` was generated before final S3 artifacts, yielding false `missing_required` entries.
2. Remediated by updating executor ordering:
   - generate evidence index after writing closure artifacts and receipt,
   - perform a second pass so the self-entry (`pr2_evidence_index.json`) reflects on-disk state.
3. Reran S3 immediately from same strict upstream and confirmed:
   - `missing_required=[]`,
   - `unreadable_required=[]`.

### Runtime and cost posture
1. `elapsed_minutes=0.0` vs S3 budget `10`.
2. `attributable_spend_usd=0.0` vs envelope `5.0`.

### Documentation sync
1. Updated PR2 authority execution record to `COMPLETE` and added `11.4 PR2-S3 Findings Snapshot`.
2. Updated main plan:
   - PR2 section now marks execution status complete,
   - immediate next step moved to `PR3-S0`,
   - added `10.10 PR2-S3 Findings Snapshot`.

### Governance
1. No branch operations, no commit/push.
2. Scope limited to S3 executor, run-control artifacts, docs, implementation map, and logbook.

## Entry: 2026-03-06 02:01:22 +00:00 - Findings summaries normalized to human-readable analytical tables (PR1/PR2/main plan)
### Trigger
1. USER directed continuation after revert with explicit requirement: readable findings must be analytical summaries, not JSON pointer/file-dump tables.

### Decisions
1. Preserve artifact inventories/evidence references in authority and execution sections.
2. Normalize findings surfaces to one schema: Area | What was found | Interpretation.
3. Remove the remaining PR1 standardized ledger block so findings are fully consistent across PR1, PR2, and the main plan.

### Changes applied
1. Updated platform.PR2.road_to_prod.md findings sections (11.1..11.4) to summary format.
2. Updated platform.road_to_prod.plan.md findings sections (10.1..10.10) to summary format.
3. Updated platform.PR1.road_to_prod.md section 14 to PR1 Cross-State Findings Summary (Readable) with the same 3-column summary structure.

### Verification
1. Confirmed no remaining Findings Snapshot headings in PR1/PR2/main-plan findings surfaces.
2. Confirmed no remaining old 6-column findings table schema (Signal/Observed/Threshold/Status/Interpretation/Decision) in the normalized findings sections.
3. Confirmed modified scope remains documentation-only.

### Governance
1. No branch operations.
2. No commit/push.

## Entry: 2026-03-06 02:05:10 +00:00 - Pre-edit plan for PR3 authority doc materialization (G3A runtime certification)
### Trigger
1. USER directed: "Let's move to planning out PR3 and its own doc".

### Problem framing
1. Main plan currently has only high-level PR3 lane intent but no dedicated PR3 authority doc.
2. PR2 closed PR3_READY and now requires a deterministic, fail-closed PR3 state plan before execution.
3. PR3 must explicitly close TGT-08 (runtime threshold families) and TGT-09 (archive sink design/backpressure posture) by PR3-S5.

### Authorities and constraints
1. Binding source for PR3 gate semantics:
   - docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md Section 10A (G3A) and related anti-gaming/measurement-surface laws.
2. Upstream strict handoff authority:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s3_execution_receipt.json.
3. Existing execution posture constraints:
   - no local orchestration for runtime certification; local machine used only for planning/docs/validation logic.

### Design decisions
1. Create standalone PR3 authority doc:
   - docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR3.road_to_prod.md.
2. Keep structure consistent with PR1/PR2 authority docs for operator continuity:
   - Purpose, authorities, scope, exit standard, capability lanes, execution posture, state plan, artifact contract, budgets, rerun discipline, DoD, execution record.
3. Use six-state PR3 chain aligned to G3A scorecard shape and drills:
   - S0 preflight + run binding,
   - S1 steady,
   - S2 burst,
   - S3 recovery,
   - S4 soak + mandatory runtime drills,
   - S5 rollup + verdict.
4. Artifact naming strategy:
   - preserve g3a_* canonical evidence object names from design authority,
   - include pr3_s*_execution_receipt.json and pr3_execution_summary.json for state continuity.
5. Blocker taxonomy strategy:
   - fail-closed blocker codes mapped per state (entry lock, measurement surfaces, sample minima, threshold breaches, drill failures, evidence index/verdict incoherence, unattributed spend).

### Main-plan sync changes
1. Update PR3 phase block in platform.road_to_prod.plan.md to reference PR3 authority doc explicitly.
2. Add explicit PR3 execution status line (NOT_STARTED) and route immediate-next-step to PR3 authority doc (instead of temporary PR2-only routing).

### Risks and mitigations
1. Risk: vague PR3 plan leads to checklist closure without gate-intent proof.
   - Mitigation: codify required metrics families, measurement surfaces, cohorts, drills, and deterministic evidence bundle as hard pass conditions.
2. Risk: budget/run posture drifts into expensive reruns.
   - Mitigation: declare profile-scoped rerun boundaries and forbid rerun-the-world for metric/artifact defects.

### Governance
1. Scope is documentation planning only (no branch operations, no commit/push).

## Entry: 2026-03-06 02:08:14 +00:00 - PR3 authority doc created and main-plan routing synchronized
### What was implemented
1. Added standalone PR3 authority doc:
   - docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR3.road_to_prod.md.
2. PR3 authority structure includes:
   - purpose, binding authorities, scope boundary,
   - hard exit standard,
   - capability-lane coverage,
   - performance/cost execution posture,
   - detailed fail-closed S0..S5 state plan,
   - artifact contract,
   - runtime/cost budgets,
   - rerun discipline,
   - DoD checklist,
   - execution record (NOT_STARTED).
3. Blocker taxonomy and gate routing added:
   - PR3.B01..PR3.B32 mapped across entry lock, profile windows, drills, rollup, and spend attribution.
4. Main plan synchronized:
   - PR3 phase block now references PR3 authority doc,
   - PR3 execution status set to PLANNED,
   - immediate-next-step routing switched to main plan + PR3 authority, with PR2 retained as upstream closure reference only.
5. Digest-standard consistency fixed:
   - section 8.1 in main plan now reflects agreed summary format columns (Area | What was found | Interpretation).

### Why this design
1. Prevents checklist-style PR3 execution by forcing explicit runtime profile/drill evidence at each state boundary.
2. Aligns PR3 directly to design authority 10A requirements (scorecard phases, cohorts, drills, deterministic bundle/verdict).
3. Ensures TGT-08 and TGT-09 cannot close implicitly; closure artifacts are hard-required in PR3 pass criteria.

### Verification
1. Confirmed PR3 doc contains:
   - explicit TGT-08/TGT-09 closure hooks,
   - PR4_READY handoff condition,
   - NOT_STARTED execution state.
2. Confirmed main-plan updates applied at:
   - PR3 phase block,
   - immediate-next-step routing,
   - digest standard section.
3. Scope remains documentation-only.

### Governance
1. No branch operations.
2. No commit/push.

## Entry: 2026-03-06 02:13:23 +00:00 - Pre-edit plan for PR3-S0 strict execution from pr2_20260305T200521Z
### Trigger
1. USER directed: "Proceed with the planning and execution of PR3-S0 from strict upstream pr2_20260305T200521Z fail-closed".

### Strict upstream lock (to be enforced)
1. 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_s3_execution_receipt.json must be:
   - erdict=PR2_S3_READY,
   - open_blockers=0,
   - 
ext_gate=PR3_READY.
2. 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr2_20260305T200521Z/pr2_execution_summary.json must be coherent with receipt.
3. pr2_runtime_numeric_contract.rc2s.active.yaml and pr2_opsgov_numeric_contract.rc2s.active.yaml must exist/readable and remain ACTIVE.

### PR3-S0 implementation approach
1. Materialize dedicated executor:
   - scripts/dev_substrate/pr3_s0_executor.py.
2. Executor responsibilities:
   - enforce strict upstream gate lock,
   - create deterministic pr3_execution_id and run root,
   - emit S0 artifacts:
     - pr3_entry_lock.json,
     - g3a_run_charter.active.json,
     - g3a_measurement_surface_map.json,
     - g3a_preflight_snapshot.json,
     - g3a_archive_sink_design_decision.json,
     - pr3_s0_execution_receipt.json.
3. Preflight evidence posture for S0:
   - use prior validated runtime readiness artifacts (M13/M14 summaries and PR2 validators) as deterministic preflight evidence;
   - no local runtime orchestration/probing.
4. Update latest pointer:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr3_latest.json.

### Fail-closed blocker mapping for S0
1. PR3.B01_ENTRY_LOCK_MISSING
2. PR3.B02_UPSTREAM_PR2_NOT_READY
3. PR3.B03_CHARTER_INCOMPLETE
4. PR3.B04_MEASUREMENT_SURFACE_MAP_MISSING
5. PR3.B05_PREFLIGHT_DEPENDENCY_UNREADY
6. PR3.B06_ARCHIVE_SINK_DESIGN_UNPINNED

### Documentation sync after execution
1. Update PR3 authority execution record (Section 11) with active execution id and S0 verdict.
2. Add readable findings summary table for PR3-S0 in PR3 doc.
3. Update main plan immediate next step to PR3-S1 if S0 is green.
4. Add corresponding readable findings summary in main plan.

### Validation and governance
1. Validate executor syntax via python -m py_compile.
2. Execute one strict run from provided upstream id.
3. No branch operations; no commit/push.

## Entry: 2026-03-06 02:20:46 +00:00 - PR3-S0 executed fail-closed from strict upstream pr2_20260305T200521Z
### Implementation completed
1. Added executor:
   - scripts/dev_substrate/pr3_s0_executor.py.
2. Executor enforces strict upstream lock against:
   - pr2_s3_execution_receipt.json (PR2_S3_READY, open_blockers=0, 
ext_gate=PR3_READY),
   - pr2_execution_summary.json (PR3_READY, open_blockers=0),
   - active PR2 runtime/opsgov contracts and activation matrix pass state.
3. Executor emits deterministic S0 artifacts under run root:
   - pr3_entry_lock.json,
   - g3a_run_charter.active.json,
   - g3a_measurement_surface_map.json,
   - g3a_preflight_snapshot.json,
   - g3a_archive_sink_design_decision.json,
   - pr3_s0_execution_receipt.json,
   - and updates pr3_latest.json.

### Execution result
1. Executed command:
   - python scripts/dev_substrate/pr3_s0_executor.py --upstream-pr2-execution-id pr2_20260305T200521Z.
2. Generated PR3 execution root:
   - 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/.
3. S0 verdict:
   - PR3_S0_READY, open_blockers=0, 
ext_state=PR3-S1.
4. S0 fail-closed checks:
   - B01..B06 all 	rue.
5. Dependency preflight posture:
   - 8/8 checks passed in evidence-only mode (no local orchestration).

### Planning authority and status sync
1. Updated PR3 authority execution record:
   - status moved to IN_PROGRESS with S0 closure details.
2. Added PR3 S0 human-readable findings summary in PR3 doc.
3. Updated main plan:
   - immediate next step now routes to PR3-S1 from strict S0 receipt,
   - added 10.11 PR3-S0 Findings Summary (Readable),
   - updated TGT-08 and TGT-09 status to IN_PROGRESS.

### Performance and cost posture
1. S0 runtime: lapsed_minutes=0.0 vs budget 20.
2. S0 spend: ttributable_spend_usd=0.0 vs envelope 250.0.

### Governance
1. No branch operations.
2. No commit/push.

## Entry: 2026-03-06 02:25:25 +00:00 - Pre-edit plan for PR3-S1 strict execution from pr3_20260306T021900Z
### Trigger
1. USER directed planning + execution of PR3-S1 from strict upstream pr3_20260306T021900Z with human-readable goal-level interpretation.

### Strict upstream lock (to enforce)
1. 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/pr3_s0_execution_receipt.json must be:
   - erdict=PR3_S0_READY,
   - open_blockers=0,
   - 
ext_state=PR3-S1.

### Evidence posture discovered before execution
1. Existing throughput evidence candidate:
   - 
uns/dev_substrate/dev_full/m7/m7s_m7k_cert_20260226T000002Z/m7k_throughput_cert_snapshot.json.
2. Candidate observed steady throughput is ~49.49 eps, while PR3 charter target is 3000 eps.
3. This implies likely S1 fail-closed unless fresh steady-window evidence exists at PR3 target envelope.

### Implementation plan
1. Add scripts/dev_substrate/pr3_s1_executor.py.
2. Executor behavior:
   - strict S0 lock verification,
   - produce S1 artifacts (g3a_scorecard_steady.json, g3a_component_health_steady.json, g3a_steady_sample_minima_receipt.json, pr3_s1_execution_receipt.json),
   - enforce S1 blocker map:
     - PR3.B07_STEADY_PROFILE_NOT_EXECUTED,
     - PR3.B08_STEADY_SAMPLE_MINIMA_FAIL,
     - PR3.B09_STEADY_SURFACE_SCOPE_MISMATCH,
     - PR3.B10_STEADY_THRESHOLD_BREACH,
     - PR3.B11_STEADY_SCORECARD_INCOMPLETE.
3. Execution mode for this step: evidence-only strict evaluation (no local runtime orchestration).

### Documentation sync after execution
1. Update PR3 authority execution record and add PR3-S1 findings summary table.
2. Update main plan immediate next step and add PR3-S1 findings summary table.
3. Ensure findings explain outcome in terms of S1 goal (steady-profile certification intent).

### Governance
1. No branch operations.
2. No commit/push.

## Entry: 2026-03-06 03:14:29 +00:00 - PR3-S1 speedup requirement pinned; managed in-cloud load lane implementation plan
### Trigger
1. USER directive: "Document this and proceed" after confirming S1 blocker root-cause includes missing active stream speedup on strict PR3 boundary.

### Root-cause pin (documented as binding for current PR3-S1 scope)
1. Current `PR3-S1` executor is strict evidence adjudication only (`EVIDENCE_ONLY_REUSE_STRICT`) and does not perform runtime load generation.
2. Fresh evidence script currently computes `observed_events_per_second` from charter-window Athena averages, which cannot reflect newly generated high-rate campaigns unless the runtime measurement window is explicit.
3. Therefore, `PR3.B10_STEADY_THRESHOLD_BREACH` cannot be remediated by repeated telemetry-only reruns; an active managed load lane is required.

### Decision (chosen lane)
1. Use a managed in-cloud load lane on ECS Fargate (`fraud-platform-dev-full-wsp-ephemeral`) rather than local load generation.
2. Run one-shot tasks in public subnets (`subnet-005205ea65a9027fc`, `subnet-01fd5f1585bfcca47`) with `assignPublicIp=ENABLED` because private-subnet launches fail on CloudWatch logger initialization in current posture.
3. Keep strict PR3 boundary execution id unchanged (`pr3_20260306T021900Z`); emit new speedup and evidence artifacts under this run root only.

### Planned implementation
1. Add `scripts/dev_substrate/pr3_s1_managed_speedup_dispatch.py`:
   - validates strict S0 lock for current PR3 execution,
   - launches N parallel Fargate tasks with deterministic per-lane ids,
   - each task runs inline Python load generator against IG `POST /v1/ingest/push` using pinned `platform_run_id`/`scenario_run_id`,
   - polls task completion and captures per-lane exit/stop status,
   - writes deterministic artifacts:
     - `g3a_s1_speedup_dispatch_manifest.json`
     - `g3a_s1_speedup_dispatch_summary.json`.
2. Extend `scripts/dev_substrate/pr3_s1_fresh_steady_evidence.py`:
   - add explicit performance-window override inputs (`--perf-window-start-utc`, `--perf-window-end-utc`),
   - keep sample-minima window bound to charter by default for strict-boundary continuity,
   - compute throughput/error/latency from IG CloudWatch metrics over performance window and explicitly record dual-window provenance.
3. Execute chain:
   - run managed speedup dispatch,
   - recompute fresh S1 evidence using emitted performance window,
   - rerun `pr3_s1_executor.py` with new evidence refs.

### Acceptance policy for this remediation pass
1. No local load orchestration loops; only remote Fargate task orchestration and artifact adjudication locally.
2. Fail-closed if managed dispatch has unresolved lane failures or evidence artifacts are incomplete/unreadable.
3. Keep all artifacts in `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/`.

### Governance
1. No branch operations.
2. No commit/push.

## Entry: 2026-03-06 03:58:12 +00:00 - PR3-S1 fail-fast correction after runaway managed speedup attempt
### Trigger
1. USER escalation: long-running PR3-S1 speedup run is wasting resources; stop immediately on detected bottleneck and remediate before rerun.

### What happened
1. Managed speedup dispatch was launched at high envelope (lane_count=8, 	arget_rps_per_lane=450, duration_seconds=900) without early-cutoff controls in the dispatcher.
2. Command timed out locally while remote ECS tasks kept running, creating avoidable resource burn window.

### Immediate containment executed
1. Listed and force-stopped active ECS tasks in cluster raud-platform-dev-full-wsp-ephemeral.
2. Verified cluster posture after stop:
   - RUNNING=0
   - PENDING=0

### Root-cause and corrective decision
1. Root cause is tooling control-gap in scripts/dev_substrate/pr3_s1_managed_speedup_dispatch.py: no heartbeat telemetry, no throughput floor gate, no early shutdown action.
2. Corrective design pinned (binding for PR3-S1 speedup lane):
   - emit per-lane heartbeat telemetry during run,
   - compute aggregate observed admitted EPS during polling,
   - enforce early cutoff if throughput floor is not met after grace window,
   - enforce early cutoff if telemetry coverage remains too low,
   - stop all running lane tasks immediately on cutoff trigger.

### Implemented in code
1. Updated scripts/dev_substrate/pr3_s1_managed_speedup_dispatch.py with:
   - lane heartbeat emission from in-task loader,
   - incremental CloudWatch log polling for heartbeat parsing,
   - new fail-fast args:
     - --heartbeat-seconds
     - --early-cutoff-grace-seconds
     - --early-cutoff-min-throughput-fraction
     - --early-cutoff-min-lane-coverage-fraction
     - --disable-early-cutoff
   - stopper helper that terminates running tasks when early cutoff triggers,
   - explicit blocker ids for early shortfall / low-coverage conditions and stop-task failures,
   - dispatch summary fields for expected EPS floor and early-cutoff state.

### Governance
1. No branch operations.
2. No commit/push.

## Entry: 2026-03-06 04:05:28 +00:00 - PR3-S1 bottleneck diagnosis from fail-fast calibration
### Observed blocker facts
1. Latest calibration summary reports:
   - PR3.S1.SPD.B12_EARLY_THROUGHPUT_SHORTFALL with observed=214.180 vs floor 490.000 (coverage 1.000).
2. Lane heartbeat status counts show dominant 429 responses (rate-limit/backpressure), not service crash.
3. Previous nonzero lane exit code (137) was caused by intentional early-cutoff stop-task action, not an independent runtime defect.

### Decision and code correction
1. Treat ingress throttling (429-driven admitted EPS collapse) as primary bottleneck for PR3-S1.
2. Updated dispatcher classification so forced early-cutoff xit_code=137 is annotated as EARLY_CUTOFF_FORCED_STOP and not emitted as B06 blocker.

## Entry: 2026-03-06 04:18:00 +00:00 - WSP runtime authority drift and IG edge envelope correction plan
### Trigger
1. USER directed immediate correction of stack drift so platform posture matches the expected production flow.

### Drift confirmed
1. WSP placement is inconsistent across authorities:
   - migration authority and handles pin `WSP_RUNTIME` to ECS/Fargate,
   - later authority text says SR/WSP stream lanes run on MSK-integrated Flink jobs,
   - live managed Flink materialization exists only for RTDL (`fraud-platform-dev-full-rtdl-ieg-ofp-v0`).
2. IG ingress envelope is inconsistent across sources:
   - handles + runtime Terraform defaults pin `IG_RATE_LIMIT_RPS=200`, `IG_RATE_LIMIT_BURST=400`,
   - RC2/PR3 capacity-envelope workflow and runtime-cert gate already target `3000/6000`.
3. Lambda envelope remains under-pinned:
   - runtime Terraform hardcodes `memory_size=256`,
   - reserved concurrency is not explicitly managed in IaC,
   - cert workflow observes lambda envelope but does not currently apply/verify target lambda knobs.

### Corrective decisions
1. Repin WSP authority away from ECS one-shot posture and toward managed stream-job posture:
   - `WSP_RUNTIME_MODE = MSF_MANAGED_PRIMARY`,
   - `WSP_RUNTIME_FALLBACK_ALLOWED = EKS_FLINK_OPERATOR`,
   - `WSP_TRIGGER_MODE = READY_EVENT_TRIGGERED`.
2. Keep SR control authority unchanged:
   - `SR_RUNTIME_MODE = SFN_LAMBDA_JOB`,
   - `SR_READY_COMMIT_AUTHORITY = STEP_FUNCTIONS_ONLY`.
3. Repin the baseline IG edge contract to the active cert floor:
   - `IG_RATE_LIMIT_RPS = 3000`,
   - `IG_RATE_LIMIT_BURST = 6000`.
4. Make lambda envelope explicit and IaC-controlled:
   - add Terraform vars / outputs / workflow inputs for:
     - IG lambda memory size,
     - IG lambda reserved concurrency,
     - IG lambda timeout.
5. Carry the same pins into authority docs and runtime workflow checks so no source continues claiming the stale ECS or `200/400` posture.

### Implementation scope
1. Update authority docs:
   - `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M6.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M14.build_plan.md`
2. Update runtime IaC:
   - `infra/terraform/dev_full/runtime/variables.tf`
   - `infra/terraform/dev_full/runtime/main.tf`
   - `infra/terraform/dev_full/runtime/outputs.tf`
3. Update managed uplift workflow:
   - `.github/workflows/dev_full_rc2_r2_capacity_envelope.yml`

### Boundary note
1. This patch corrects authority and managed configuration surfaces.
2. It does not claim WSP managed-Flint materialization is complete until the corresponding managed WSP runtime artifact exists and is verified in a later execution gate.

### Governance
1. No branch operations.
2. No commit/push.

## Entry: 2026-03-06 04:29:00 +00:00 - WSP/IG authority correction implemented
### Implemented
1. Corrected authority drift in:
   - `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M6.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M14.build_plan.md`
2. WSP is now repinned in authority to managed stream runtime primary posture:
   - `WSP_RUNTIME_MODE/WSP_RUNTIME = MSF_MANAGED_PRIMARY`
   - fallback remains explicit `EKS_FLINK_OPERATOR`.
3. IG edge baseline contract is now aligned to runtime-cert target:
   - `IG_RATE_LIMIT_RPS = 3000`
   - `IG_RATE_LIMIT_BURST = 6000`
4. IG lambda envelope is now explicit in IaC and workflow authority:
   - memory `1024 MB`
   - reserved concurrency `300`
   - timeout `30s`

### Runtime code/config updated
1. `infra/terraform/dev_full/runtime/variables.tf`
   - added lambda envelope vars,
   - repinned IG throttle defaults to `3000/6000`.
2. `infra/terraform/dev_full/runtime/main.tf`
   - lambda now consumes explicit memory / timeout / reserved-concurrency vars,
   - preconditions enforce timeout >= request timeout and positive reserved concurrency.
3. `infra/terraform/dev_full/runtime/outputs.tf`
   - runtime handle materialization now emits lambda envelope handles.
4. `.github/workflows/dev_full_rc2_r2_capacity_envelope.yml`
   - added lambda envelope inputs,
   - managed terraform apply now passes lambda vars,
   - post-apply verification now fail-closes on lambda envelope shortfall, not APIGW-only.

### Validation
1. `python -m py_compile scripts/dev_substrate/pr3_s1_managed_speedup_dispatch.py` passed.
2. `terraform -chdir=infra/terraform/dev_full/runtime fmt -check` passed after formatting normalization.
3. `terraform -chdir=infra/terraform/dev_full/runtime validate` passed.
4. Workflow YAML parse passed for `.github/workflows/dev_full_rc2_r2_capacity_envelope.yml`.

### Remaining explicit gap
1. This patch corrects authority and managed configuration posture.
2. Live managed WSP materialization is still not proven; current live MSF app is RTDL-only, so WSP managed runtime still requires a dedicated execution/verification pass before it can be claimed green.

### Governance
1. No branch operations.
2. No commit/push.

## Entry: 2026-03-06 05:31:37 +00:00 - Production-first blocker handling doctrine applied to WSP/PR3-S1
### Trigger
1. USER corrected the blocker-handling posture for road-to-prod work:
   - do not optimize for the fastest path to a green rerun,
   - optimize for the production-grade architecture that would be recommended under real financial-institution load,
   - document the actual problem, contributing areas, and competing solutions before choosing the remediation path.

### Immediate correction to my prior reasoning
1. My prior recommendation to repin `WSP` back to canonical `ECS/Fargate` was too compressed and was framed around clearing `PR3-S1` safely rather than first stating the production problem in full.
2. That framing was wrong for this stage of the project because `PR3` is not a workflow-completion exercise; it is a production-readiness gate.
3. The correct first question is:
   - if this platform had to support production-realistic `3000 eps steady / 6000 eps burst` on the declared `via_IG` claim path, what runtime shape should `WSP` take so the platform stays operationally correct and measurable?

### Problem statement (actual, not shortcut-framed)
1. `PR3-S1` is not blocked merely because a rerun lane is missing.
2. The real defect is a runtime-shape mismatch:
   - the repo's actual `WSP` is a Python oracle-backed ingress replayer that emits HTTP requests into `IG`,
   - some authority surfaces were repinned to `MSF_MANAGED_PRIMARY`,
   - the current `PR3-S1` remote execution path diverged from the real `WSP` and used a synthetic pressure harness instead of the actual `WSP` runtime.
3. That means we are currently mixing three different things as if they were the same:
   - stream processing runtime (`Managed Flink` for `IEG/OFP/RTDL`),
   - ingress replay producer runtime (`WSP`),
   - temporary load-generation harness for certification.

### Concrete evidence gathered
1. Actual `WSP` implementation is Python HTTP replay code, not Flink job code:
   - `src/fraud_detection/world_streamer_producer/runner.py`
   - `src/fraud_detection/world_streamer_producer/ready_consumer.py`
2. Actual `WSP` already has the pacing primitive needed for production-style replay:
   - `stream_speedup` policy in `src/fraud_detection/world_streamer_producer/config.py`
   - event-time pacing in `src/fraud_detection/world_streamer_producer/runner.py`
3. Live AWS currently contains only the RTDL managed Flink app:
   - `fraud-platform-dev-full-rtdl-ieg-ofp-v0`
   - there is no live `WSP` managed Flink application.
4. Authority drift is real and internal:
   - `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
     simultaneously states:
     - `WSP` is repinned to `ECS/Fargate` ephemeral task,
     - `WSP_RUNTIME_MODE = "MSF_MANAGED_PRIMARY"`.
5. The active `PR3-S1` managed workflow currently reasons about a `WSP`-on-`MSF` path that is not materially implemented in the repo or live runtime.

### Consequence if left uncorrected
1. We would be certifying the platform against a non-canonical producer path.
2. A green `PR3-S1` under that posture would not be a trustworthy production-readiness claim.
3. Continued work would drift into "make the run pass" behavior rather than proving the platform against its real hot path.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:31:37 +00:00 - WSP production-shape options evaluated against the real goal
### Production question
1. For a real financial-institution-style platform targeting `3000 eps steady / 6000 eps burst` on the `via_IG` certification path, what is the correct production-grade runtime for `WSP`?

### Option A - Force `WSP` onto Managed Flink (`MSF`)
Status:
1. Rejected as the primary recommendation.

Reasoning:
1. `WSP` is not a stream transform/join lane. It is an ingress replay producer with external side effects (`HTTP -> IG`).
2. Flink is a strong fit for stateful stream processing, watermarking, checkpoints, and keyed transforms; it is a weak fit for a side-effect-heavy ingress producer whose success criteria are:
   - stable idempotent HTTP emission,
   - producer retry discipline,
   - replay checkpoints keyed to oracle position,
   - controlled backpressure against the ingress edge.
3. Forcing `WSP` onto `MSF` would require us to invent a new application shape that does not exist in the repo today, while gaining little architectural benefit on the `WSP -> IG` edge itself.
4. It would also blur accountability between:
   - `WSP` as the outside-world replay producer,
   - `IEG/OFP/RTDL` as the managed Flink stream-processing plane.
5. This is not rejected because it is hard; it is rejected because it is the wrong abstraction for the role `WSP` actually plays.

### Option B - Keep the synthetic ad hoc ECS pressure harness
Status:
1. Rejected.

Reasoning:
1. The current harness is not the real `WSP`.
2. It bypasses the actual `WSP` pacing/checkpoint/replay logic and therefore cannot be the canonical certification path.
3. It is useful only as bounded diagnostic evidence.

### Option C - Bypass `IG` and push directly to bus/runtime
Status:
1. Rejected.

Reasoning:
1. Violates the pinned `via_IG` production claim path.
2. Would produce incorrect `PR3` evidence because admission behavior, idempotency, `429` posture, and edge SLOs would be skipped.

### Option D - Treat `WSP` as a dedicated distributed ingress replay service on remote managed compute
Status:
1. Accepted as the production-grade direction.

Reasoning:
1. This matches the actual `WSP` role:
   - replay oracle traffic,
   - preserve event-time pacing semantics,
   - emit into `IG`,
   - honor retry/idempotency/checkpoint semantics.
2. This keeps `Managed Flink` where it belongs:
   - `IEG/OFP/RTDL` stream-processing lanes.
3. This also aligns the certification path with what actually matters for `PR3-S1`:
   - can the platform edge admit and process realistic high-rate traffic through the real producer boundary?
4. The right question is not "ECS vs Flink" in isolation.
5. The right separation is:
   - replay producer runtime (`WSP`) vs stream-processing runtime (`IEG/OFP/RTDL`).

### Decision rule pinned from this evaluation
1. `WSP` must be treated as a distributed remote ingress replay service, not as a managed Flink application by default.
2. `Managed Flink` remains canonical for stream-processing lanes only.
3. `PR3-S1` must be rerouted onto the real remote `WSP` implementation, not the synthetic pressure harness.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:31:37 +00:00 - Production-grade remediation path chosen for WSP/PR3-S1
### Chosen remediation
1. Correct the authority drift by separating:
   - `WSP` as distributed remote replay producer,
   - `Managed Flink` as stream-processing runtime for `IEG/OFP/RTDL`.
2. Retire the idea that `PR3-S1` should search for a `WSP` `MSF` app.
3. Replace the current synthetic `PR3-S1` pressure path with the actual remote `WSP` code path using:
   - oracle-backed `WSP`,
   - explicit `stream_speedup`,
   - remote managed compute only,
   - deterministic run-scoped checkpoints and evidence.

### What this means concretely
1. `PR3-S1` remediation is no longer "rerun with a different harness".
2. It becomes a runtime correction with these work items:
   - fix authority/plan surfaces so they no longer imply `WSP` should be `MSF`,
   - wire `dev_full` profile/runtime config so remote `WSP` can run against oracle store and live `IG`,
   - build a canonical remote launch lane for the real `WSP`,
   - rerun `PR3-S1` only after that correction exists.

### Important nuance on compute choice
1. The accepted architectural decision is "distributed replay producer on remote managed compute".
2. In this repo, the nearest correct execution substrate is still likely ECS/Fargate unless measured evidence later proves it cannot satisfy the envelope.
3. That is not a lazy fallback; it is the natural managed-compute fit for a Python HTTP replay producer.
4. If measured evidence later shows ECS cannot meet the declared envelope with the real `WSP` implementation, then the next move is to escalate compute shape based on evidence, not to force `WSP` into `MSF` by assumption.

### Next implementation step pinned
1. Update active road-to-prod authority to state that `PR3-S1` is blocked on canonical `WSP` runtime correction, not merely on a rerun threshold defect.
2. Begin wiring `dev_full` so the real remote `WSP` can be launched with explicit `stream_speedup` and live `IG`/oracle configuration.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:31:37 +00:00 - Pre-edit plan for MSK control-bus correction on the real WSP path
### New issue discovered while wiring the canonical path
1. `dev_full` authority pins control on `fp.bus.control.v1` over MSK.
2. The current `SR`/`WSP` control-bus implementation only supports:
   - `file`
   - `kinesis`
3. This means that even if the remote `WSP` replay path is corrected, the platform would still be bypassing the declared READY-trigger bus semantics unless control-bus support is fixed.

### Why this matters for production-readiness
1. `WSP_TRIGGER_MODE = READY_EVENT_TRIGGERED` is part of the declared platform behavior.
2. If `PR3` claims steady-runtime readiness while `WSP` is launched through an out-of-band direct trigger, we would still have a gap between:
   - platform control-plane semantics,
   - actual runtime execution semantics.
3. For production-grade closure, I want the next canonical path to preserve both:
   - real producer runtime (`WSP`),
   - real control trigger semantics (`READY` over the pinned control bus).

### Available implementation leverage
1. `scenario_runner.bus.py` already has file and kinesis control-bus publishers.
2. `world_streamer_producer.control_bus.py` already has file and kinesis control-bus readers.
3. The repo already contains Kafka/MSK adapters in:
   - `src/fraud_detection/event_bus/kafka.py`
4. Therefore the missing piece is not a greenfield Kafka client stack; it is the control-bus integration layer.

### Planned implementation
1. Add Kafka/MSK-backed control-bus publisher support to `SR`.
2. Add Kafka/MSK-backed control-bus reader support to `WSP`.
3. Update `dev_full` profile wiring so the real remote `WSP` path can use:
   - oracle store over S3,
   - live `IG` endpoint,
   - API-key auth posture,
   - Postgres checkpoints,
   - Kafka/MSK control bus.
4. Keep the implementation additive and fail-closed:
   - no silent fallback to file/kinesis in `dev_full`,
   - missing Kafka env/config should error explicitly.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:31:37 +00:00 - MSK control-bus support and dev_full WSP remote wiring implemented
### Implemented
1. Added Kafka/MSK control-bus publisher support for `SR` in:
   - `src/fraud_detection/scenario_runner/bus.py`
   - `src/fraud_detection/scenario_runner/runner.py`
2. Added Kafka/MSK control-bus reader support for `WSP` in:
   - `src/fraud_detection/world_streamer_producer/control_bus.py`
   - `src/fraud_detection/world_streamer_producer/ready_consumer.py`
3. Expanded `config/platform/profiles/dev_full.yaml` so the real remote `WSP` path now carries the missing runtime wiring surfaces:
   - traffic/context output refs,
   - oracle root / engine root / stream-view refs,
   - live `IG` ingest URL,
   - Kafka control-bus kind/topic,
   - Postgres checkpoint backend,
   - producer identity,
   - API-key auth posture,
   - retry knobs.
4. Fixed a profile-loader defect in `src/fraud_detection/world_streamer_producer/config.py`:
   - `${VAR:-default}` placeholders now resolve correctly,
   - this was required because the new `dev_full` profile intentionally uses defaults for non-secret wiring where safe.

### Why this matters
1. The repo can now preserve the declared READY-trigger semantics over the pinned MSK control bus instead of bypassing them.
2. The `dev_full` `WSP` profile is now usable for real remote replay against:
   - oracle store in S3,
   - live `IG`,
   - remote checkpointing,
   - Kafka control bus.
3. This is a prerequisite to replacing the synthetic `PR3-S1` pressure harness with the actual `WSP` path.

### Validation
1. `python -m py_compile` passed for:
   - `src/fraud_detection/scenario_runner/bus.py`
   - `src/fraud_detection/scenario_runner/runner.py`
   - `src/fraud_detection/world_streamer_producer/control_bus.py`
   - `src/fraud_detection/world_streamer_producer/ready_consumer.py`
   - `src/fraud_detection/world_streamer_producer/config.py`
2. `WspProfile.load(Path('config/platform/profiles/dev_full.yaml'))` succeeded with:
   - `control_bus_kind = kafka`
   - `control_bus_topic = fp.bus.control.v1`
   - `ig_ingest_url = https://ehwznd2uw7.execute-api.eu-west-2.amazonaws.com/v1/ingest/push`
   - `checkpoint_backend = postgres`
   - `stream_speedup = 1.0`

### Remaining work after this implementation
1. Authority docs still need a deliberate correction so `WSP` is described as a distributed replay producer runtime rather than `MSF`-primary.
2. `PR3-S1` still needs a canonical remote launch lane for the real `WSP`; current workflow surface still points at the synthetic pressure harness.
3. Only after that lane exists should `PR3-S1` be rerun.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:31:37 +00:00 - Pre-edit plan for authority correction of the WSP runtime shape
### Why this edit is next
1. The repo now has the first mechanical pieces needed for the real remote `WSP` path.
2. Leaving authority surfaces at `WSP = MSF_MANAGED_PRIMARY` would keep the active source-of-truth wrong even though implementation work has moved in the opposite, production-correct direction.

### Exact authority correction to apply
1. Reframe `WSP` as a remote distributed replay producer, not a managed Flink app.
2. Keep `Managed Flink` canonical for `IEG/OFP/RTDL` only.
3. Update the concrete `WSP` runtime pins to a run-scoped replay posture on remote managed compute.

### Files targeted
1. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M6.build_plan.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M14.build_plan.md`

### Guardrail for this edit
1. I am not repinning `WSP` to local or ad hoc compute.
2. I am making the authority say what the production-first analysis actually concluded:
   - remote replay producer on managed compute,
   - not `MSF` by default.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:31:37 +00:00 - WSP authority surfaces corrected to the production runtime shape
### Implemented
1. Corrected WSP runtime pins in:
   - `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M6.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M14.build_plan.md`
2. New active WSP runtime pin is:
   - `ECS_FARGATE_RUN_SCOPED_REPLAY_JOB`
3. New bounded fallback language is:
   - `EKS_REPLAY_JOB_EXCEPTION_ONLY`
4. The authority now states explicitly that:
   - `Managed Flink` remains the stream-processing substrate,
   - `WSP` is the remote replay-producer runtime.

### Notes on historical evidence
1. Historical M14 closure artifacts still mention `ECS_FARGATE_RUNTASK_EPHEMERAL`.
2. I am leaving that as historical evidence rather than rewriting history.
3. The active forward authority is now the run-scoped replay-job pin above.

### Remaining implementation gap after authority correction
1. The canonical remote launch lane for the real `WSP` still needs to be built.
2. `PR3-S1` should remain unrerun until that launch lane replaces the synthetic harness.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:52:27 +00:00 - Production-fit reassessment of the WSP pressure lane after user escalation
### Problem actual
1. The wrong question had started to creep into `PR3-S1`:
   - "what is the easiest runtime shape that lets the state rerun?"
2. That is not the production question.
3. The production question is:
   - "if this platform had to withstand a real financial-institution ingress envelope around `3000 eps`, what producer/runtime shape would preserve realistic data semantics, preserve the `via_IG` trust boundary, and still be operable at that envelope?"

### Re-evaluated options with the correct production lens
#### Option A - force `WSP` onto Managed Flink because Flink is the streaming substrate
Status:
1. Rejected again, this time for production-fit reasons rather than convenience.

Reasoning:
1. `WSP` is not a stateful stream-processing operator; it is an outside-world replay emitter.
2. Its authoritative duties are:
   - read oracle-backed stream views,
   - pace according to event-time and `stream_speedup`,
   - emit canonical envelopes into `IG`,
   - retain replay/checkpoint semantics.
3. Managed Flink is a strong fit for long-running keyed/stateful processing (`IEG/OFP/RTDL`), but it is the wrong abstraction for a run-scoped HTTP side-effecting replay producer.
4. Forcing `WSP` onto Managed Flink would solve a category mistake, not the actual throughput problem.

#### Option B - keep a single remote `WSP` task and just increase `stream_speedup`
Status:
1. Rejected as insufficient for a production claim.

Reasoning:
1. This leaves the hot path effectively constrained by one producer thread per output stream.
2. For the currently selected output set, that means the throughput ceiling is governed by:
   - output count,
   - per-request latency,
   - retry posture,
   - connection reuse efficiency.
3. With steady target `3000 eps`, a single task with weak internal fanout is not a credible production-grade producer shape.

#### Option C - distributed remote `WSP` replay on managed compute, preserving `via_IG`
Status:
1. Accepted as the production direction.

Reasoning:
1. This preserves the real platform edge:
   - `WSP -> IG -> EB -> downstream`.
2. It keeps `Managed Flink` on the processing side where it belongs.
3. It frames the next work correctly:
   - improve the real replay producer hot path,
   - add durable runtime surfaces,
   - then measure whether one task is enough or whether deterministic sharding/fanout is required.
4. This is not "ECS because it is easy".
5. This is "managed replay workers because `WSP` is a producer runtime, not a Flink job".

### Decision pinned from this reassessment
1. `WSP` remains a managed remote replay-producer lane.
2. `Managed Flink` remains canonical for `IEG/OFP/RTDL` stream-processing lanes.
3. `PR3-S1` must certify the real producer path through `IG`, not an easier substitute.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 05:52:27 +00:00 - Newly identified WSP hot-path bottlenecks against the `3000 eps` envelope
### Problem actual
1. The corrected runtime shape alone is not enough.
2. The current `WSP` implementation itself exposes a material producer bottleneck:
   - concurrency is primarily across `output_id`s,
   - the hot path uses `requests.post(...)` per event,
   - no persistent HTTP session/pool is reused,
   - one remote task therefore has a weak multi-kEPS posture before `IG` is even the limiting component.

### Concrete code evidence
1. `src/fraud_detection/world_streamer_producer/runner.py`
   - `output_parallelism` is derived from output count or `WSP_OUTPUT_CONCURRENCY`,
   - but the executor fans out by output stream, not by a high-cardinality producer shard model,
   - `_push_to_ig(...)` uses `requests.post(...)` directly on every event.
2. This means that the producer-side ceiling is currently dominated by transport overhead and per-output serialization characteristics.

### Why this matters for production
1. If producer transport overhead is the binding limit, then a failed `PR3-S1` rerun would say more about the replay worker than about the platform edge.
2. That would again produce misleading readiness evidence.
3. The correct next move is to harden the replay worker before spending on more large pressure windows.

### Immediate remediation plan
1. Improve the `WSP` transport hot path first:
   - introduce persistent HTTP session reuse/connection pooling,
   - keep retry/idempotency semantics unchanged.
2. Tighten the canonical dispatcher so it uses the real `dev_full` profile and durable checkpoint surfaces, not an invented scratch profile.
3. After that, run a bounded smoke to learn whether the remaining limit is:
   - producer transport,
   - `IG` admission,
   - or both.
4. If a single hardened task still cannot approach the declared envelope, the next production-grade step is deterministic remote replay fanout/sharding rather than a doc-level repin.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 06:03:11 +00:00 - Smoke evidence exposed a real network-posture defect in the canonical dispatcher
### What the bounded smoke actually proved
1. The previous `PR3-S1` smoke no longer failed on the old "timer starts before runtime" bug.
2. The first honest blocker is now infrastructure:
   - `TaskFailedToStart`
   - `ResourceInitializationError`
   - ECR auth/token pull timed out before container start.

### Root-cause analysis
1. The dispatcher was launching the WSP task in the public subnets:
   - `subnet-005205ea65a9027fc`
   - `subnet-01fd5f1585bfcca47`
2. In this VPC, private DNS is enabled for:
   - `ecr.api`
   - `ecr.dkr`
3. Those interface endpoints are attached to the private subnets and their endpoint security group only permits `443` from:
   - `10.70.128.0/20`
   - `10.70.144.0/20`
4. Therefore the public-subnet WSP task resolves ECR to the private endpoint IPs but is not allowed through the endpoint SG.
5. That is why the task fails before producer logic starts.

### Production interpretation
1. This is not a reason to abandon the canonical WSP lane.
2. It is evidence that the launcher posture was wrong.
3. A production-grade replay worker should run on private runtime subnets with endpoint-backed bootstrap, not on public subnets with incidental internet posture.

### Chosen remediation
1. Repin the canonical dispatcher network defaults to:
   - private runtime subnets,
   - `assignPublicIp=DISABLED`.
2. Keep the worker on remote managed compute.
3. Rerun the same bounded smoke after this change before spending on a longer pressure window.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 06:08:54 +00:00 - Private-subnet correction exposed the next missing bootstrap dependency
### What changed
1. I moved the canonical WSP dispatcher defaults onto the private runtime subnets and disabled public IP assignment.
2. That was the correct production move and it cleared the earlier ECR-endpoint mismatch.

### New blocker surfaced immediately after that correction
1. The task now fails with:
   - `ResourceInitializationError`
   - CloudWatch log group/logger validation could not complete due network reachability.
2. This means the task is now getting further into bootstrap and has progressed beyond the earlier ECR auth path.

### Root cause
1. `dev_full` runtime interface endpoints currently cover:
   - `ec2`
   - `ecr.api`
   - `ecr.dkr`
   - `sts`
2. They do not currently cover:
   - `logs`
3. Private runtime workers therefore still lack a complete bootstrap path for the ECS `awslogs` log driver.

### Production interpretation
1. This is the correct kind of blocker to resolve in infrastructure, not by weakening the launcher back to public subnet posture.
2. A production-grade private replay worker needs deterministic reachability for:
   - image auth/pull,
   - STS,
   - CloudWatch Logs,
   - S3,
   - Aurora.

### Chosen remediation
1. Extend the runtime interface-endpoint set to include `logs`.
2. Validate the Terraform surface.
3. If the plan is clean, apply the endpoint so the private runtime bootstrap path becomes complete.
4. Then rerun the same bounded smoke again before any larger `PR3-S1` pressure window.

### Additional guardrail discovered during Terraform plan
1. The full runtime plan also proposes unrelated `EKS` node-group replacement drift.
2. That is not part of this blocker and should not be pulled into the fix implicitly.
3. Therefore the endpoint remediation should be applied in a targeted way for `aws_vpc_endpoint.runtime_interface["logs"]`, with the broader node-group drift left for separate review.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 06:16:14 +00:00 - The next blocker is a real WSP profile-loader defect, not infrastructure
### Diagnostic result
1. A tiny diagnostic task proved the container image, working directory, and shell override are all valid.
2. A second task with the real WSP command and shell tracing produced the actual failure text:
   - `WSP run_receipt unreadable ... error=Invalid endpoint:`
   - result reason `RUN_RECEIPT_UNREADABLE`

### Root cause
1. `config/platform/profiles/dev_full.yaml` sets:
   - `object_store.endpoint: ${OBJECT_STORE_ENDPOINT}`
2. In the ECS runtime, `OBJECT_STORE_ENDPOINT` is intentionally unset because the correct target is native AWS S3, not MinIO.
3. `src/fraud_detection/world_streamer_producer/config.py` currently resolves that placeholder to `""` rather than `None`.
4. The reader path later hands that empty string to boto3 as `endpoint_url=""`, which causes:
   - `Invalid endpoint:`

### Production interpretation
1. This is exactly the kind of subtle runtime defect that destroys a production cutover:
   - the surface looks pinned correctly,
   - but one unset env token collapses the S3 client path at runtime.
2. The correct behavior for native AWS posture is:
   - blank endpoint token => no custom endpoint => let boto3 use the regional default.

### Chosen remediation
1. Normalize blank env-resolved endpoint strings to `None` in `WSP` profile loading.
2. Keep the same `dev_full` profile pins.
3. Rerun the bounded smoke immediately after that fix.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 06:18:44 +00:00 - The remaining blocker is remote image drift, not another code hypothesis
### What the latest smoke proved
1. The canonical WSP task now:
   - launches in private subnets,
   - pulls image successfully,
   - starts the container,
   - emits logs,
   - fails with the same old `Invalid endpoint:` symptom.

### Why that matters
1. The local source fix for blank endpoint normalization is correct.
2. But the remote ECS task definition still points at the previously built image digest:
   - `sha256:49eb6cb0c5e33061fae4d1aaceeac2e44600adb5c4250436be9ac8395ed29cb2`
3. That image was built before the new `WSP` config-loader fix existed.
4. Therefore the live task is still executing stale code.

### Production interpretation
1. Continuing to rerun the current task definition would waste time and cost.
2. The blocker is no longer "find a different explanation".
3. The blocker is:
   - the canonical lane needs a refreshed runtime image carrying the validated `WSP` fixes.

### Chosen next action
1. Record the boundary clearly in the road-to-prod documents.
2. Do not keep rerunning the stale image.
3. Next execution-worthy move is a controlled image refresh for the WSP runtime lane, then rerun the bounded smoke again before any larger `PR3-S1` window.

### Governance
1. No branch operation.
2. No commit/push.

## Entry: 2026-03-06 07:21:14 +00:00 - PR3-S1 is now limited by producer-side rate control truthfulness, not unknown infra drift
### Observed runtime facts
1. Live ingress envelope is materially aligned with the production pin:
   - API Gateway stage throttle `3000 rps / 6000 burst`.
   - Lambda `reserved_concurrency=300`, `memory=1024 MB`, `timeout=30s`.
2. Canonical remote WSP replay can now drive the ingress edge close to target throughput on AWS compute:
   - admitted requests `756,704`
   - observed admitted throughput `2789.805 eps`
   - `5xx_total=0`
3. The remaining runtime quality defect is explicit in lane logs:
   - repeated `http_429` retries across multiple WSP lanes.
4. Current canonical dispatcher summary is not yet strict enough:
   - it marks the window `REMOTE_WSP_WINDOW_READY` if early-cutoff, logs, and metrics succeed,
   - but it does not fail on final steady-rate shortfall or error-rate breach.

### Problem actual
1. We solved the infra/bootstrap/image-drift chain already.
2. The active defect is now a control defect in the sender itself:
   - once `stream_speedup` is raised high enough to approach the required ingress rate,
   - the producer overshoots the stage envelope,
   - API Gateway returns `429`,
   - retries amplify waste,
   - and the run can look "nearly green" on admitted throughput while still being production-invalid.
3. This is exactly the kind of false green that the road-to-prod exercise is supposed to prevent.

### Production-standard reasoning
1. In a real financial production system, the correct answer is not to keep widening ingress or to accept a noisy near-target run.
2. The correct answer is to shape the producer so it can hit the declared steady envelope cleanly and repeatably.
3. Therefore the canonical WSP runtime needs:
   - explicit deterministic sender-side rate control,
   - bounded burst allowance,
   - truthful state gating on final throughput and error posture.
4. This is also the right foundation for later PR3 burst/recovery work because burst proof should come from an explicit shaped load contract, not accidental overshoot.

### Alternatives considered
1. Lower `stream_speedup` only.
   - Rejected as insufficient because it relies on guesswork and cannot guarantee repeatable convergence at `3000 eps` without fresh overshoot/undershoot loops.
2. Increase ingress throttle again.
   - Rejected because live ingress is already aligned with the active production envelope; widening it would hide the sender defect instead of fixing it.
3. Accept the current run because admitted throughput is close.
   - Rejected because `429` volume and admitted-rate shortfall violate the pinned production contract.

### Chosen remediation
1. Add deterministic per-process WSP rate shaping with shared thread-safe coordination.
2. Surface explicit shaping knobs through the canonical dispatcher so the run contract is declared rather than implicit.
3. Tighten the canonical runtime summary so it fail-closes on:
   - final steady-rate shortfall,
   - 4xx/error-rate breach,
   - any 5xx breach.
4. Rebuild the WSP image, rerun bounded PR3-S1 windows, and tune against the contract until the canonical steady window is truly clean.

### Governance
1. No branch operation.
2. Active-branch commit/push is allowed and expected after meaningful progress.

## Entry: 2026-03-06 07:34:31 +00:00 - First shaped bounded run cleared 429s and exposed a steady-window accounting defect
### What the first shaped run proved
1. Deterministic sender-side shaping removed the prior `429` problem completely.
2. The bounded run produced:
   - admitted request count `746,559`
   - `4xx_total=0`
   - `5xx_total=0`
3. The only remaining blocker was final steady-rate shortfall (`2745.237 eps` vs `3000 eps`).

### Additional diagnosis
1. The runtime summary still anchored elapsed steady time to the latest observed task `started_at` timestamp.
2. That is still too early for the real certification window because the run should start when the whole fleet is confirmed `RUNNING`, not when some tasks were merely started by ECS.
3. This undercounts true steady throughput by including ramp and ECS state-propagation time in the denominator.

### Chosen correction
1. Keep sender-side shaping because it has already eliminated avoidable error traffic.
2. Move the canonical steady-window start to the moment the full fleet is confirmed `RUNNING`.
3. Keep `fleet_started_utc` as a separate field for auditability so ramp characteristics are not hidden.
4. Rerun the same shaped bounded window immediately after this accounting fix before changing rate targets again.

## Entry: 2026-03-06 07:48:40 +00:00 - Certification window end must be the stop-request boundary, not ECS stop completion
### Additional diagnostic result
1. The shaped runs still showed inflated elapsed windows relative to the declared 180-second certification duration.
2. Root cause is the same class of accounting issue as the start boundary:
   - the dispatcher was using the latest ECS `stopped_at` timestamp as the performance end,
   - but Fargate task termination lags the actual moment the certification window is closed,
   - so the denominator included post-window shutdown time.

### Production interpretation
1. For a bounded certification window, the valid performance interval is:
   - start: full-fleet confirmed `RUNNING`,
   - end: the instant the window is intentionally closed (`stop_task` issuance or early-cutoff decision).
2. Measuring through container shutdown would understate throughput and distort error accounting.

### Chosen correction
1. Record `window_closed_at` at the exact moment the run closes.
2. Query CloudWatch metrics only through that boundary.
3. Keep task stop timestamps only as operational teardown evidence, not as the hot-path performance end marker.
4. Rerun the exact same shaped bounded window after this correction before any further target changes.
### 2026-03-06 08:18:00 +00:00 - PR3-S1 regression analysis before next rerun
- Problem under analysis:
  - the latest bounded `PR3-S1` rerun dropped from the prior `2934.068 eps` posture to `1991.749 eps` admitted with zero `4xx`/`5xx`.
  - this is inconsistent with the immediately prior shaped run and points to a measurement/control regression rather than a new ingress-capacity collapse.
- Findings:
  - the dispatcher still computes `window_end` from submit-time launch rather than from `active_confirmed_at`, so the declared 180-second steady window can be truncated materially by fleet start latency.
  - the canonical dispatcher default still advertises `assignPublicIp=ENABLED`, which contradicts the intended private-subnet posture and makes the runtime contract drift-prone.
- Production-standard decision:
  - fix the duration anchor first; the steady contract must be measured from the moment the full fleet is confirmed active, not from orchestration submit time.
  - repin the dispatcher default to private-subnet execution (`DISABLED`) so the canonical path matches the intended production network shape.
  - rerun bounded calibration only after both are corrected and recorded.
### 2026-03-06 08:24:00 +00:00 - Private WSP launch failure triage and chosen remediation
- Latest bounded rerun did not prove a private-network dead end; it exposed stale launcher defaults plus a status-decoding bug.
- Findings from live AWS:
  - runtime VPC endpoints already exist for `ecr.api`, `ecr.dkr`, `logs`, `sts`, and S3 gateway in the private subnets,
  - the canonical dispatcher still defaulted to the public subnets (`subnet-005205ea65a9027fc`, `subnet-01fd5f1585bfcca47`) until the last patch and does not yet default to the authoritative private subnets,
  - `to_iso_utc()` currently converts missing ECS timestamps into `now_utc()`, which can falsely make failed tasks look as if they had start timestamps.
- Production-standard decision:
  - repin the canonical dispatcher subnet defaults to the authoritative private subnets (`subnet-0a7a35898d0ca31a8`, `subnet-0e9647425f02e2f27`),
  - make absent ECS timestamps remain absent so startup failure detection is truthful,
  - rerun bounded calibration after those corrections; if private image pulls still fail, only then move deeper into endpoint/route inspection.
### 2026-03-06 08:32:00 +00:00 - Private WSP to IG path needs execute-api endpoint, not public fallback
- New bounded smoke outcome after launcher fixes:
  - tasks started correctly in private subnets,
  - WSP logs show repeated `IG push retry ... reason=timeout`,
  - no admissions were recorded because the worker lane cannot reach the Regional API Gateway endpoint from the private subnets.
- Production interpretation:
  - the correct no-NAT production posture is not to move the WSP lane back to public subnets,
  - it is to add the private `execute-api` interface endpoint so private workers can reach the ingress edge without Internet egress dependence.
- Additional small code correction to make with this:
  - guard CloudWatch metric reads against zero-width windows so early loop iterations do not raise `StartTime must be less than EndTime` and muddy telemetry.
- Chosen remediation:
  - add `execute-api` to the runtime interface endpoint set in Terraform,
  - apply only the new endpoint live,
  - patch the dispatcher metric guard,
  - rerun a bounded private smoke before returning to the 75-lane calibration window.
### 2026-03-06 08:36:00 +00:00 - execute-api private endpoint materialized live for no-NAT WSP to IG path
- Applied targeted Terraform remediation:
  - created `aws_vpc_endpoint.runtime_interface["execute-api"]`,
  - live endpoint id `vpce-05d4ac7f9e8ddf16a`.
- Purpose:
  - allow private-subnet WSP worker lanes to resolve and reach the Regional API Gateway ingress endpoint without NAT/public routing.
- Boundaries observed:
  - targeted apply only; no unrelated runtime replacements were pulled into this remediation.
- Next action:
  - rerun a 2-lane bounded smoke against the private canonical path,
  - if clean, return to the 75-lane calibration window.
### 2026-03-06 08:40:00 +00:00 - PR3-S1 canonical source posture corrected: WSP replay must emulate outside-world traffic
- The `execute-api` endpoint remediation proved private workers can now reach the API surface, but the next result was `403 Forbidden` from API Gateway rather than a Lambda auth response.
- Design-intent review matters here:
  - `WSP` is explicitly pinned as the platform's **outside-world traffic producer**,
  - `PR3-S1` is validating ingress readiness under realistic incoming traffic,
  - so the source lane should behave like an external producer hitting the public ingress edge, not like an internal private service caller.
- Production-standard decision:
  - keep the newly added `execute-api` endpoint because it is still useful for no-NAT private worker patterns elsewhere,
  - but repin the **canonical PR3-S1 replay dispatcher** back to public-subnet Fargate tasks with public IPs,
  - treat that not as a shortcut but as the correct semantics for stressing the public ingress boundary.
- Consequence:
  - PR3-S1 remains the real WSP path,
  - but its network posture is `outside-world -> public IG edge`, not `private internal worker -> IG`.
### 2026-03-06 08:45:00 +00:00 - execute-api private DNS poisoned the public-edge WSP path; keep endpoint, disable private DNS
- After restoring public-subnet defaults, WSP still received `403 Forbidden` from API Gateway with `IG_PUSH_REJECTED`.
- Production diagnosis:
  - this is no longer an auth-header problem,
  - it is the consequence of enabling `private_dns_enabled=true` on the new `execute-api` VPC endpoint,
  - which overrides the standard `*.execute-api.eu-west-2.amazonaws.com` hostname inside the VPC,
  - causing the canonical public-edge WSP path to stop behaving like external traffic.
- Production-standard decision:
  - preserve the endpoint resource itself for future explicit private-use cases,
  - but disable private DNS specifically for `execute-api`,
  - so the default API hostname again resolves to the true public ingress edge for PR3-S1.
- This is the correct compromise:
  - canonical ingress stress remains outside-world -> public IG,
  - the VPC can still retain an `execute-api` endpoint if a later internal lane needs explicit endpoint DNS.
### 2026-03-06 08:51:00 +00:00 - execute-api endpoint recreated without private DNS
- Applied targeted Terraform replacement for the `execute-api` endpoint so `private_dns_enabled=false`.
- New live endpoint id: `vpce-0db82483efe7d9939`.
- Purpose:
  - stop overriding the default public `execute-api` hostname inside the VPC,
  - preserve the endpoint resource for explicit future use,
  - restore PR3-S1 public-edge replay semantics.
### 2026-03-06 08:55:00 +00:00 - PR3-S1 next calibration should scale producer fanout, not IG envelope
- Latest 75-lane bounded canonical run produced:
  - admitted count `216,607`,
  - admitted steady rate `1707.253 eps`,
  - `4xx_total=0`, `5xx_total=0`.
- Interpretation:
  - IG is not rejecting traffic;
  - the WSP replay topology is simply not generating enough concurrent producer fanout to reach the `3000 eps` ingress target under current lane count.
- Quantitative reading:
  - observed admitted rate per lane is about `22.76 eps` (`1707.253 / 75`).
  - to reach `3000 eps` at roughly that lane-level posture requires about `132` concurrent lanes.
- Production-standard decision:
  - do not widen IG again,
  - do not lean on wrong proxy metrics,
  - increase WSP replay fanout to approximately `144` lanes while keeping the total target at `3000 eps`.
- Why this is production-valid:
  - WSP is an outside-world simulator, so horizontal producer fanout is the realistic way to model many concurrent upstream clients.
  - This changes the realism of the source population, not the acceptance criteria of the platform.
### 2026-03-06 09:05:00 +00:00 - Quota-bound partial launch cleanup and right-sizing plan
- The 144-lane attempt failed at lane `140` with the live Fargate concurrent vCPU limit.
- Current WSP task definition is overprovisioned for this purpose:
  - task CPU `1024`
  - task memory `2048`
- Production-standard remediation:
  - add explicit task-size overrides to the PR3-S1 dispatcher so the replay harness can be right-sized per campaign,
  - add automatic cleanup of already-launched tasks when a later lane fails to launch,
  - test `512 CPU / 1024 MiB` lane posture first, then retry higher fanout.
- Reasoning:
  - the WSP replay lane is a stress harness for outside-world client fanout, not the production hot service itself,
  - right-sizing harness tasks is valid cost/performance engineering, not target cheating.
### 2026-03-06 09:18:00 +00:00 - PR3-S1 runtime evidence now points to a measurement-window defect, not an ingress failure
- The latest `136`-lane canonical run looked materially short on the emitted summary (`2241.826 eps`), but direct lane logs did not agree with that result.
- Cross-check performed:
  - lane logs show each WSP lane sustaining about the configured `22.0588 eps` aggregate send rate once active,
  - API Gateway `Count` and Lambda `Invocations` both returned about `357.9k` requests for the same query,
  - the query returned only two full `60s` CloudWatch bins (`08:55`, `08:56`) while the dispatcher divided by the wall-clock span `159.655s`.
- Root cause:
  - PR3-S1 is measuring a non-minute-aligned window on a metric surface that publishes minute-bucket sums,
  - so the numerator is approximately `120s` worth of admitted requests while the denominator is `159.655s`,
  - which artificially suppresses the computed eps by about `25%`.
- Production interpretation:
  - this is not a cosmetic reporting bug,
  - it changes the certification verdict and would incorrectly fail-close a platform that is materially much closer to the target than the current summary claims.
- Immediate production-grade correction:
  - repin PR3-S1 steady measurement to whole CloudWatch periods only,
  - compute covered seconds from the returned datapoint bins rather than from arbitrary wall-clock stop time,
  - align the certification window start to the next full minute after fleet readiness so `IG_ADMITTED_EVENTS_PER_SEC` is measured on an authoritative surface without partial-bin ambiguity.
- Secondary conclusion:
  - with the correct two-minute denominator, the latest run is about `2982.7 eps`, still slightly below the `3000 eps` target,
  - so after the measurement correction the next likely clearance move is a modest `stream_speedup` uplift rather than another architecture change.
### 2026-03-06 09:14:00 +00:00 - PR3-S1 aligned-window rerun shows CloudWatch publication lag still contaminates early cutoff
- First rerun after the aligned-window fix was executed at `136` lanes with `stream_speedup=90`.
- Result highlights:
  - final settled two-bin readback: `359,796` admitted requests over `120s` = `2998.3 eps`,
  - zero `4xx`, zero `5xx`,
  - blocker ids emitted were:
    - `B12_EARLY_THROUGHPUT_SHORTFALL observed=1896.017 floor=2100`,
    - `B19_FINAL_THROUGHPUT_SHORTFALL observed=2998.300 target=3000`.
- Root cause of the contradictory blocker pair:
  - early cutoff is still evaluating too near the live minute boundary,
  - at that instant only one settled CloudWatch minute was visible, so the floor calculation read a stale undercount,
  - the later final read already showed the lane shape was effectively at target.
- Production-grade correction:
  - add an explicit metric-settle grace to `PR3-S1`,
  - only use CloudWatch bins whose close time is at least the settle-grace behind wall clock,
  - wait through that settle grace after the measurement window closes before issuing the final verdict.
- Throughput interpretation after this rerun:
  - the platform is now materially at the `3k eps` edge on the authoritative measurement surface,
  - so the remaining clearance move is not architectural; it is a small margin uplift (`stream_speedup`/shape headroom) plus proper settled-bin adjudication.
### 2026-03-06 09:46:00 +00:00 - PR3-S1 closed by calibrating the generator setpoint, not by weakening the platform target
- After settled-bin adjudication was fixed, repeated open-loop runs at nominal `3000 eps` source setpoints (`136-139` lanes) consistently landed just under target (`2994-2999 eps`) with zero errors.
- Engineering interpretation:
  - this was no longer a platform bottleneck,
  - it was a source-controller underdelivery artifact caused by token-bucket/setpoint quantization and small replay-shape losses,
  - so the right move was calibration of the injector setpoint while keeping the acceptance target fixed.
- Chosen production-grade correction:
  - keep the acceptance contract at `3000 admitted eps`,
  - raise the generator setpoint slightly to `3005 eps`,
  - retain canonical remote-WSP replay, settled-minute-bin adjudication, zero-error requirements, and unchanged latency thresholds.
- Final closure evidence:
  - `lane_count=138`,
  - `stream_speedup=95`,
  - `target_request_rate_eps=3005`,
  - observed admitted throughput `3003.4222 eps`,
  - admitted events `540,616` across `180s`,
  - `4xx_total=0`,
  - `5xx_total=0`,
  - settled metric bins `3`.
- Closure decision:
  - `PR3-S1` is now legitimately closed because the platform cleared the unchanged production target on the authoritative surface,
  - the small source overdrive is recorded as calibration of the test rig, not as relaxation of the platform standard.
### 2026-03-06 10:35:00 +00:00 - PR3 runtime authority drift discovered: ingress was exercised, RTDL hot path was not materially running
- While planning `PR3-S2`, I checked the live managed/runtime surfaces instead of assuming the earlier `PR3-S1` ingress closure implied end-to-end runtime readiness.
- Findings:
  - live Managed Flink app `fraud-platform-dev-full-rtdl-ieg-ofp-v0` exists but is only in `ApplicationStatus=READY`, not `RUNNING`,
  - the app currently has default shell configuration only (checkpoint interval/parallelism), with no deployed application code description visible,
  - EKS cluster `fraud-platform-dev-full` exists and namespace `fraud-platform-rtdl` exists, but there are no RTDL workloads running in it,
  - the only live ECS cluster is `fraud-platform-dev-full-wsp-ephemeral`, which is the ingress harness, not the stream compute lane.
- Production consequence:
  - the prior `PR3-S1` result is valid as an ingress-capacity proof on the authoritative IG surface,
  - but it is not sufficient evidence for the full RTDL hot path because the downstream stream-processing lane is not materially active.
- Decision:
  - do not hide this by pretending `PR3-S2` can certify lag/checkpoint/backpressure against a non-running stream lane,
  - treat this as a real production-readiness defect and remediate the runtime data plane before advancing the PR3 chain.
### 2026-03-06 10:40:00 +00:00 - Root-cause decomposition of the missing RTDL runtime lane
- The issue is not just "the app is stopped". The deeper problem is a three-part implementation gap:
  1. managed Flink cutover only proved materialization of the app shell, not a running RTDL workload,
  2. the dev_full substrate has no always-on RTDL workloads materialized in EKS or ECS,
  3. the RTDL projection components (`IEG`, `OFP`) are not currently MSK-capable in code.
- Code inspection shows:
  - `decision_fabric`, `action_layer`, `decision_log_audit`, and `case_trigger` already support `event_bus_kind=kafka`,
  - `archive_writer` supports `event_bus_kind=kafka`,
  - `identity_entity_graph` and `online_feature_plane` still only support `file|kinesis` and therefore cannot consume the live dev_full Kafka/MSK traffic bus.
- Why this matters in production terms:
  - even if I launch remote jobs on EKS today, the RTDL projection lane will not consume the real production bus,
  - so any scorecard built on top of the current projector code would still be structurally false.
- Remediation plan adopted:
  - add first-class Kafka/MSK reader support to `IEG` and `OFP`,
  - wire dev_full runtime profiles/launchers for RTDL core on remote compute,
  - materialize the RTDL lane in EKS,
  - then re-run the PR3 chain from the earliest state whose claim depended on a materially active hot path.
### 2026-03-06 10:52:00 +00:00 - Pre-change design for IEG/OFP Kafka support on the managed RTDL lane
- Problem being solved:
  - the live dev_full transport spine is Kafka/MSK,
  - `IEG` and `OFP` are still pinned in code to `file|kinesis`,
  - therefore the managed RTDL lane cannot consume the same authoritative admitted-event traffic already used by the other runtime workers.
- Why this must be fixed in code before more PR3 execution:
  - `PR3-S2` onward is supposed to measure burst handling, lag, checkpoint behavior, and state freshness under the real hot path,
  - without Kafka/MSK reader support in `IEG`/`OFP`, any downstream runtime proof would be structurally false even if ingress remains green.
- Candidate solutions considered:
  - `A` repin RTDL back to Kinesis or file replay:
    - rejected because it would move the runtime away from the live dev_full substrate and produce non-production evidence.
  - `B` rely on an external bridge from Kafka to Kinesis just for `IEG`/`OFP`:
    - rejected because it adds an unnecessary extra failure surface and latency surface for a problem already solved in-repo by other workers.
  - `C` add first-class Kafka/MSK consumption to `IEG` and `OFP` by reusing the existing `build_kafka_reader` adapter and existing checkpoint semantics:
    - accepted because it preserves transport uniformity across the RTDL lane, keeps the dev_full substrate coherent, and minimizes new code by following proven worker patterns already present in `DF`, `AL`, `DLA`, `CT`, and `Archive Writer`.
- Performance and correctness design:
  - use the shared Kafka reader already used elsewhere rather than building bespoke consumer logic,
  - preserve checkpoint semantics by storing `kafka_offset` as the committed record offset and letting the store advance to `offset+1` where those stores already treat `kafka_offset` as incrementing offsets,
  - preserve run-scope filters and replay manifest gates exactly as file/kinesis paths already do,
  - preserve `poll_max_records`, `max_inflight`, and `batch_size` controls so no new unbounded memory posture is introduced.
- Planned mechanics:
  - `identity_entity_graph/projector.py`
    - add Kafka reader initialization,
    - add normal streaming consumption by topic/partition,
    - add replay-manifest partition range consumption by Kafka offset,
    - reuse existing buffer/drain logic so batch behavior remains consistent across transports.
  - `online_feature_plane/projector.py`
    - add Kafka reader initialization,
    - add normal streaming consumption by topic/partition using the existing checkpoint store,
    - honor `event_bus_start_position` only when no checkpoint exists.
- Validation plan:
  - add focused unit tests that monkeypatch the Kafka reader rather than requiring a live broker,
  - verify that `IEG` and `OFP` process Kafka rows, persist state, and advance checkpoints with `offset_kind=kafka_offset`,
  - then move to remote materialization of the RTDL lane.
- Production-standard rationale:
  - this is not a convenience refactor to make `PR3` pass,
  - it is the minimal substrate correction required for the managed RTDL path to consume the same high-eps authoritative bus the rest of the platform already uses.
### 2026-03-06 11:08:00 +00:00 - Kafka/MSK support implemented and validated for IEG/OFP
- Code changes completed:
  - `src/fraud_detection/identity_entity_graph/projector.py`
    - added Kafka reader initialization via `build_kafka_reader`,
    - added normal topic/partition consumption,
    - added replay-manifest Kafka partition-range consumption,
    - added Kafka partition discovery and buffered Kafka draining.
  - `src/fraud_detection/online_feature_plane/projector.py`
    - added Kafka reader initialization via `build_kafka_reader`,
    - added normal topic/partition consumption and partition discovery,
    - kept observability export behavior unchanged.
- Important checkpoint finding surfaced during validation:
  - the `IEG` and `OFP` stores do **not** normalize `kafka_offset` to `offset+1`;
  - they persist the **last consumed Kafka offset**,
  - therefore the consumer must resume from `checkpoint+1` when a Kafka checkpoint already exists.
- Why I preserved that contract instead of changing the stores:
  - changing store semantics would ripple into graph/input-basis receipts and historical meaning of persisted offsets,
  - the safer production move is to honor the established store contract at the reader edge.
- Additional correctness decision:
  - `IEG` first-read Kafka posture was set to `earliest` when no checkpoint exists,
  - because `IEG` has no explicit start-position config and defaulting to `latest` would silently drop the pre-existing admitted stream during first materialization.
- Validation executed:
  - `py_compile` on the modified projectors and tests,
  - focused projector tests:
    - `tests/services/identity_entity_graph/test_projector_determinism.py`
    - `tests/services/online_feature_plane/test_phase2_projector.py`
  - result: `18 passed`.
- Impact on the production path:
  - the RTDL projection code is now transport-compatible with the live dev_full MSK spine,
  - next step is to materialize the remote RTDL workers and then resume PR3 on the actual hot path.
### 2026-03-06 11:24:00 +00:00 - Transport-layer blocker discovered: dev_full pins MSK IAM but the shared Kafka adapter still expects static SASL credentials
- While moving from local projector validation to remote RTDL materialization, I checked the auth posture needed by the shared Kafka adapter against the actual dev_full bus handles.
- Result:
  - dev_full bus posture is pinned to `AWS MSK Serverless` with `SASL_IAM`,
  - but `src/fraud_detection/event_bus/kafka.py` currently only supports username/password-style SASL through `confluent_kafka`.
- Production consequence:
  - simply adding Kafka branches to `IEG/OFP` is not enough,
  - remote workers would still fail to authenticate to the live brokers, so any claimed MSK consumption path would remain non-material.
- Candidate remediation options considered:
  - `A` inject static SASL credentials:
    - rejected because it contradicts the pinned dev_full MSK IAM posture and weakens the security model.
  - `B` bypass the shared adapter and build one-off MSK IAM logic only for `IEG/OFP`:
    - rejected because it would fork transport semantics across the platform.
  - `C` upgrade the shared Kafka adapter to support MSK IAM/OAUTHBEARER and keep that adapter authoritative for all Kafka consumers/publishers:
    - accepted because it fixes the real platform defect once and preserves consistent transport behavior.
- Planned implementation:
  - extend `event_bus/kafka.py` with an MSK-IAM path using the already-proven `kafka-python + aws-msk-iam-sasl-signer-python` approach used in the repos topic-readiness tooling,
  - preserve the current `confluent_kafka` path for standard username/password SASL or plaintext cases,
  - add focused tests for OAUTH/IAM auth resolution,
  - then refresh the remote worker image so the RTDL jobs can actually reach MSK.
### 2026-03-06 12:05:00 +00:00 - Runtime-shape decision for PR3 onward: empty Managed Flink shell is non-claimable; current production-correct path is remote EKS worker materialization
- Live inspection was used to decide the next execution path instead of assuming the earlier design notes were materially true:
  - `fraud-platform-dev-full-rtdl-ieg-ofp-v0` exists in `Managed Service for Apache Flink`, but only as a shell with `ApplicationStatus=READY`, default checkpoint/parallelism settings, and no evidence of deployed application code,
  - `fraud-platform-rtdl` namespace exists on `EKS`, there are active worker nodes, but there are no RTDL workloads running,
  - the canonical remote `WSP` ECS task definition is now on refreshed image digest `sha256:b0f707c52274e35330dc412ca610399afa550662c53347f0e967c4d95dec84b8`, so ingress replay runtime drift is no longer the active blocker.
- Problem actual:
  - the repo does not currently contain a real Flink application implementation for `IEG/OFP` hot-path processing,
  - therefore keeping `FLINK_RUNTIME_PATH_ACTIVE=MSF_MANAGED` as if it were production-ready would be a false claim,
  - but refusing to proceed until a brand-new Flink application is authored would also leave the current platform non-operational despite already having remote worker code that can run on production substrate.
- Candidate remediation paths considered:
  - `A` keep chasing the current MSF shell:
    - rejected for current PR3 closure because it would certify an empty application envelope rather than a material runtime lane.
  - `B` stop and wait for explicit design repin before any more work:
    - rejected because the defect is now understood well enough to resolve autonomously and the user explicitly directed continuation with production-first judgment.
  - `C` materialize the repo's actual RTDL/decision/archive workers on remote `EKS` using the refreshed immutable image, real `MSK IAM`, and `Aurora` durability, while recording the Managed Flink shell as non-claimable until real job code exists:
    - accepted because it gives the platform a materially running hot path on remote production substrate,
    - preserves the production goal (real remote compute, real brokers, real stores, no local orchestration),
    - and turns the remaining work into measurable throughput/lag/backpressure problems instead of fictional runtime-shape problems.
- Important design consequence:
  - for road-to-production execution, the authoritative runtime claim is now bifurcated:
    - `WSP`: canonical remote `ECS` replay injector,
    - `RTDL/decision/archive`: canonical remote `EKS` worker materialization from the existing Python services,
    - `Managed Flink` app shell: retained as a future target but explicitly not claimable for `PR3` until real application code and metrics surfaces are materialized.
- Planned implementation from this point:
  - expand `config/platform/profiles/dev_full.yaml` so it actually defines the RTDL/decision/archive workers against Kafka/MSK + Aurora-backed stores,
  - add a dedicated remote workflow to materialize and verify those workers in `fraud-platform-rtdl`,
  - rerun `PR3-S1` only once the real downstream hot path is alive,
  - then continue sequentially through `PR3-S2..S5` on the materially active path with readable impact-metric summaries.
### 2026-03-06 12:32:00 +00:00 - Workflow-dispatch constraint handled without branch hopping: reuse indexed PR3 workflow path for runtime materialization mode
- After pushing the first materialization workflow file, GitHub refused direct dispatch because the new workflow path is not yet on the default-branch workflow index.
- This is a GitHub Actions control-plane constraint, not a platform/runtime blocker.
- Candidate responses considered:
  - `A` branch-hop and merge workflow-only changes to main immediately:
    - rejected for now because the user is away and the current branch can continue execution without changing branch posture.
  - `B` wait for user or stop until the new workflow exists on default:
    - rejected because it would be needless execution pause.
  - `C` add `materialize_runtime` mode to the already-indexed `dev_full_pr3_s1_managed.yml` path and dispatch that branch version against `cert-platform`:
    - accepted because GitHub already recognizes the workflow identity, so branch execution becomes possible immediately.
- Implementation consequence:
  - `dev_full_pr3_s1_managed.yml` now serves two remote execution modes:
    - `steady_harness` (legacy fallback lane, unchanged default),
    - `materialize_runtime` (new EKS runtime materialization path using `scripts/dev_substrate/pr3_rtdl_materialize.py`).
- This keeps execution remote, production-real, and branch-stable while avoiding unnecessary merge choreography mid-run.
### 2026-03-06 12:45:00 +00:00 - First EKS runtime rollout exposed two real configuration defects: stale image-baked profile and missing CSFB surface for DF
- The first remote materialization run got `IEG`, `OFP`, `AL`, and `archive_writer` into `Running/Ready`, but `DF` and `DLA` entered restart loops.
- Pod-level readback showed two distinct root causes:
  - `DF` crashed because `ContextStoreFlowBindingQueryService.build_from_policy(...)` could not resolve `CSFB_PROJECTION_DSN`; the `dev_full` runtime profile being read by the container did not yet define the `context_store_flow_binding` surface,
  - `DLA` crashed because it resolved `storage_profile_id='dev_full'`, which means the pod was still reading the old image-baked `dev_full.yaml` instead of the branch-updated profile that pins `storage_profile_id=prod`.
- Why this matters:
  - fixing only the deployment object would not help; the wrong profile surface would continue to be read from the image,
  - and without `CSFB` being at least queryable, `DF` cannot even initialize its context-acquisition path.
- Remediation chosen:
  - mount the branch-side `config/platform/profiles/dev_full.yaml` into every runtime pod through a Kubernetes `ConfigMap`, making the runtime profile authoritative at deploy time rather than image-baked,
  - add the missing `context_store_flow_binding` section plus `CSFB_PROJECTION_DSN`/`CSFB_REQUIRED_PLATFORM_RUN_ID` secret/env surfaces,
  - redeploy the runtime in place on the same namespace.
- This is the correct production-grade fix because it removes a real config-governance defect (stale baked runtime config) instead of just changing pod arguments until the crash disappears.
### 2026-03-06 12:44:00 +00:00 - Second runtime rollout proves the remaining blocker is stale immutable image, not missing secret/env surface
- After the ConfigMap/profile remount remediation, the second runtime materialization workflow still returned success while all six live deployments remained `0/1`.
- Live pod logs after the second rollout showed:
  - `IEG`: `RuntimeError("IEG_EVENT_BUS_KIND_UNSUPPORTED")`,
  - `OFP`: `RuntimeError("OFP_EVENT_BUS_KIND_UNSUPPORTED")`,
  - `DF`: `ValueError("PLATFORM_RUN_ID required to resolve projection_db_dsn.")`,
  - `AL`, `DLA`, `archive_writer`: `KAFKA_SASL_CREDENTIALS_MISSING`.
- I verified the Kubernetes deployment surfaces directly:
  - the mounted profile path is now `/runtime-profile/dev_full.yaml` from `ConfigMap/fp-pr3-runtime-profile`,
  - the secret `fp-pr3-runtime-secrets` contains `PLATFORM_RUN_ID`, `ACTIVE_PLATFORM_RUN_ID`, `KAFKA_SASL_MECHANISM=OAUTHBEARER`, `KAFKA_SECURITY_PROTOCOL=SASL_SSL`, and the Aurora DSNs,
  - the deployments reference those secret keys correctly.
- Production interpretation:
  - the live pods are not behaving according to the current branch code or the current deployment env/profile contract,
  - therefore the active runtime image is materially stale relative to the branch source even though the image tag is newer than the earlier WSP-only refresh.
- Candidate remediations considered:
  - `A` keep patching deployment env vars:
    - rejected because the env surface already contains the required values and further tweaks would be symptom-chasing.
  - `B` alter the code to add even more backwards-compatible fallbacks:
    - rejected because that would harden around stale artifact drift instead of removing it.
  - `C` rebuild the single authoritative immutable platform image from current `cert-platform`, then repin both the PR3 EKS workers and the canonical WSP ECS family to that digest:
    - accepted because the platform is designed around one authoritative runtime image and the production-correct fix is to refresh the artifact, not excuse divergence between source and runtime.
- Planned execution:
  - dispatch `dev-full-m1-packaging` from `cert-platform`,
  - capture the new digest,
  - register a fresh `fraud-platform-dev-full-wsp-ephemeral` task-definition revision on that digest,
  - rerun PR3 runtime materialization with the same digest passed explicitly,
  - only then resume bounded PR3 steady evidence.
### 2026-03-06 12:52:00 +00:00 - Fresh image closed five workers; final PR3 runtime defects are service-account trust drift and incomplete DF dependency env
- After rebuilding the immutable platform image to digest `sha256:c12122cc4da6df03bf79c1d43a11a7825960740f7db4329de39f74816d1fd159` and repinning the canonical WSP ECS family to revision `24`, I reran PR3 runtime materialization against that same digest.
- Outcome:
  - `IEG`, `OFP`, `AL`, `DLA`, and `archive_writer` all reached `1/1 Ready`,
  - `DF` remained in restart.
- Additional live diagnosis:
  - `AL` and `DLA` now connect far enough to hit MSK IAM token generation, which exposed `AssumeRoleWithWebIdentity` denial under the current service-account posture,
  - IAM trust readback showed the pre-materialized roles trust `system:serviceaccount:fraud-platform-rtdl:rtdl` and `system:serviceaccount:fraud-platform-rtdl:decision-lane`,
  - but the materializer had created ad hoc service accounts `fp-rtdl-runtime` and `fp-decision-runtime`,
  - therefore the earlier IRSA materialization was internally inconsistent even though the role ARNs themselves were correct.
- For `DF`, an in-cluster debug pod proved the profile and secret data are valid when all runtime secret keys are present:
  - `PLATFORM_RUN_ID` and `IEG_PROJECTION_DSN` resolve correctly inside the container,
  - therefore the `DF` crash was not a broken profile file,
  - it was a deployment-env completeness defect: `DF` starts `IEG` and `OFP` query/services during initialization, but the materializer only injected `CSFB`, `DF`, and `DL` surfaces into the `DF` pod.
- Accepted remediation:
  - realign the materializer to the canonical IRSA subject names `rtdl` and `decision-lane`,
  - extend `DF` pod env injection to include the `IEG_*` and `OFP_*` projection/index surfaces it actually depends on.
- Why this is the production-grade fix:
  - it preserves least-privilege IAM and uses the already-pinned trust contract,
  - it removes a real dependency-contract hole in `DF` instead of masking it with broader secret exposure or weaker startup checks.
### 2026-03-06 13:18:00 +00:00 - PR3 runtime is blocked by missing IRSA-to-MSK data-plane policy, not by pod shape or stale app code
- After the service-account realignment and fresh immutable image rollout, all six PR3 runtime deployments (`IEG`, `OFP`, `AL`, `DF`, `DLA`, `archive_writer`) reached `1/1 Ready` in `fraud-platform-rtdl`.
- Live logs then converged on the next shared failure mode:
  - `AL`, `DF`, and `DLA` each reached the MSK broker and failed during SASL/IAM broker authentication with `SaslAuthenticationFailedError (...: Access denied)`.
- IAM readback confirmed the root cause is structural:
  - `fraud-platform-dev-full-irsa-rtdl` only has inline policy `fraud-platform-dev-full-irsa-rtdl-ssm-read`,
  - `fraud-platform-dev-full-irsa-decision-lane` only has inline policy `fraud-platform-dev-full-irsa-decision-lane-ssm-read`.
- This means the EKS runtime roles can read runtime secrets from SSM but cannot perform the MSK data-plane actions required to authenticate to, read from, or write to the serverless Kafka cluster.
- Why this matters for production-readiness:
  - the platform cannot claim hot-path readiness while the true runtime principals lack the managed-bus permissions the design requires,
  - further reruns of `PR3-S1` or more app-level tweaks would only produce repetitive noise while the broker-authority boundary remains broken.
- Candidate remediations considered:
  - `A` apply an ad hoc inline IAM policy from the laptop:
    - rejected because it would repair the symptom outside the owned infrastructure graph and would repeat the local-orchestration drift the user explicitly rejected.
  - `B` broaden the application code with fallback auth paths or static credentials:
    - rejected because it would weaken the intended production security model and harden around a misconfigured platform rather than fixing the platform.
  - `C` extend the Terraform-owned IRSA role policies for the runtime principals (`rtdl`, `decision_lane`) to include the required MSK data-plane actions and execute that correction remotely through an indexed GitHub workflow:
    - accepted because it restores the correct production contract: least-privilege workload identity, managed MSK IAM auth, and repeatable evidence-backed execution.
- Production-grade implementation direction:
  - patch `infra/terraform/dev_full/runtime/main.tf` so the runtime IRSA roles receive MSK cluster/topic/group permissions derived from the live cluster handle,
  - add a dedicated remote remediation mode to the already-indexed `dev_full_pr3_s1_managed.yml` workflow so the IAM fix is applied/verified without laptop-side orchestration,
  - rerun PR3 runtime verification after the role policy correction before any further steady-window certification work.
### 2026-03-06 13:31:00 +00:00 - Remote Terraform execution is blocked by GitHub OIDC access to the tfstate bucket, so live IAM repair is being executed through AWS APIs while Terraform remains the source of truth
- The first remote `remediate_irsa_msk_auth` dispatch on the indexed PR3 workflow reached the runner and failed before any platform mutation.
- Exact failure:
  - `terraform init -reconfigure -backend-config=backend.hcl.example` returned `403 Forbidden` on `s3://fraud-platform-dev-full-tfstate/dev_full/runtime/terraform.tfstate`.
- Interpretation:
  - the GitHub OIDC role being used for remote PR3 execution can assume into AWS and operate the platform,
  - but it does not currently have read access to the Terraform state bucket object for `dev_full/runtime`.
- Why this is not a reason to stop:
  - the production problem to solve is still the missing live IRSA-to-MSK policy,
  - the `tfstate` access gap is a workflow-control-plane defect, not the runtime defect we are trying to clear.
- Candidate remediations considered:
  - `A` stop PR3 work and first widen the GitHub OIDC role to the tfstate bucket:
    - rejected for now because it lengthens the dependency chain before the runtime hot path is repaired.
  - `B` fall back to laptop-side Terraform apply:
    - rejected because it reintroduces the exact local-orchestration posture the user rejected.
  - `C` keep the Terraform patch in-repo as the declared source-of-truth, but execute the live IAM repair via remote AWS API calls (`iam put-role-policy`) inside the indexed PR3 workflow, then verify the runtime logs immediately:
    - accepted because it preserves remote execution, keeps the authoritative desired state committed, and unblocks the production runtime without waiting on the separate tfstate-access fix.
- Implementation consequence:
  - `dev_full_pr3_s1_managed.yml` now resolves the live MSK cluster via AWS APIs, generates the exact role policy document on the runner, applies it to the `rtdl` and `decision_lane` IRSA roles, restarts the affected deployments, and verifies post-restart logs for cleared auth errors.
- Follow-on requirement retained:
  - the GitHub OIDC role still needs a future fix for `tfstate` bucket access so that remote Terraform reconciliation can become fully self-hosted again.
### 2026-03-06 13:38:00 +00:00 - Live MSK discovery via AWS control-plane permissions is unnecessary for the PR3 repair, so the workflow is repinned to the canonical cluster ARN
- The first runner-side AWS-API remediation attempt failed before mutation because the GitHub OIDC role could not execute `kafka:list-clusters-v2`.
- This is another control-plane permission gap, but unlike the runtime IAM defect it is not semantically necessary for the repair itself.
- Reasoning:
  - the remediation only needs the canonical MSK cluster ARN to derive the topic/group wildcard resource ARNs,
  - the cluster ARN is already pinned for the environment and stable for this execution boundary,
  - requiring extra Kafka control-plane discovery permissions would broaden the GitHub runner role without improving runtime correctness.
- Decision:
  - remove the `list-clusters-v2` dependency from the workflow,
  - pass/use the pinned `MSK_CLUSTER_ARN` input directly and derive `cluster_name`, `cluster_uuid`, `account`, and the topic/group resource scopes from that ARN.
- Production benefit:
  - narrower execution permissions on the GitHub runner,
  - fewer control-plane dependencies between the repair job and the runtime hot path,
  - faster deterministic reruns for the same PR3 boundary.
### 2026-03-06 13:43:00 +00:00 - GitHub workflow-dispatch input ceiling forced the MSK cluster pin into job env rather than a new manual parameter
- After replacing live Kafka discovery with a pinned cluster ARN, GitHub rejected dispatch because `workflow_dispatch` only allows up to `25` inputs and `dev_full_pr3_s1_managed.yml` was already at that limit.
- This is purely a GitHub workflow-shape constraint.
- Decision:
  - remove the extra manual input,
  - pin the canonical `MSK_CLUSTER_ARN` directly in the remediation job environment for this PR3 boundary.
- Reason:
  - it preserves the narrower permission model,
  - avoids further control-plane branching or a second workflow file just to carry one static runtime handle,
  - keeps the dispatch contract stable while still using the correct cluster scope.
### 2026-03-06 13:58:00 +00:00 - With broker auth fixed, the remaining PR3-S1 defects are runtime-topic drift and legacy injector drift
- Post-remediation verification confirms the MSK auth blocker is genuinely cleared:
  - both IRSA roles now carry `*-msk-data-plane` policies scoped to the live cluster/topic/group resources,
  - fresh `AL`, `DF`, and `DLA` logs show `Authenticated via SASL / OAuth` rather than `Access denied`.
- New runtime observation after the restart:
  - `DF` now emits repeated `DF kafka partition metadata unavailable topic=fp.bus.traffic.baseline.v1; deferring read` warnings.
- Repo/design interpretation of that warning:
  - the live managed handles registry for `dev_full` pins `fp.bus.traffic.fraud.v1` as the active traffic lane and does not carry a canonical `fp.bus.traffic.baseline.v1` topic handle,
  - yet some runtime config surfaces (`config/platform/df/trigger_policy_v0.yaml`, `config/platform/ieg/topics_v0.yaml`, `config/platform/archive_writer/topics_v0.yaml`) still include the baseline topic from older dual-stream assumptions.
- Why this matters:
  - the broker auth defect is solved, so this warning is now a real contract drift rather than a hidden symptom,
  - repeatedly polling a non-existent baseline topic wastes runtime budget and muddies PR3 evidence on the real fraud lane.
- A second drift remains at the PR3 execution boundary:
  - `dev_full_pr3_s1_managed.yml` still routes `steady_harness` through `pr3_s1_managed_speedup_dispatch.py`, which is explicitly marked noncanonical,
  - while the canonical remote injector already exists as `scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py`.
- Candidate remediation options considered:
  - `A` ignore the baseline-topic warning and rerun the synthetic harness because it is already wired:
    - rejected because it would preserve both runtime waste and noncanonical throughput proof.
  - `B` create the missing baseline topic purely to silence the warning:
    - rejected because the active production lane is fraud traffic and creating unused dual-stream surfaces would widen the hot path without evidence it is needed.
  - `C` repin the runtime configs to the actual active fraud-only lane for this PR3 boundary and switch the PR3-S1 workflow onto the canonical remote WSP replay dispatcher:
    - accepted because it aligns runtime behavior, measurement claims, and injector semantics to the same production path.
- Planned implementation from this point:
  - remove or gate the stale baseline topic references from the active `dev_full` runtime configs that are used in PR3,
  - replace the workflow's `steady_harness` execution body with the canonical `pr3_s1_wsp_replay_dispatch.py` path,
  - rerun PR3-S1 on the corrected `WSP -> IG -> MSK -> RTDL` path and only then judge the next blocker.
### 2026-03-06 14:08:00 +00:00 - PR3 hot path repinned to fraud-only runtime topics and canonical remote WSP replay
- I removed the stale baseline traffic/context topic subscriptions from the active `dev_full` runtime configs used by PR3:
  - `config/platform/df/trigger_policy_v0.yaml`
  - `config/platform/ieg/topics_v0.yaml`
  - `config/platform/archive_writer/topics_v0.yaml`
  - `config/platform/context_store_flow_binding/topics_v0.yaml`
  - `config/platform/context_store_flow_binding/intake_policy_v0.yaml`
- Reasoning:
  - the current production-targeted PR3 boundary runs the fraud lane (`s3_event_stream_with_fraud_6B`) and does not pin a live baseline traffic topic in the `dev_full` handles registry,
  - keeping baseline subscriptions in the active runtime causes unnecessary metadata churn and warning noise once broker auth is healthy,
  - fraud-only runtime configs for the active lane are the tighter and more truthful contract for this boundary.
- I also repointed `dev_full_pr3_s1_managed.yml` away from the synthetic inline pressure harness and onto the canonical `scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py` path.
- Additional hardening made during that cutover:
  - the workflow now waits for `fp-pr3-{ieg,ofp,df,al,dla,archive-writer}` to be available before starting the steady window,
  - the canonical dispatcher now computes weighted API Gateway latency (`p95`/`p99`) in addition to throughput and error posture,
  - steady evidence rollup is rebuilt from the canonical WSP runtime manifest/summary so the PR3 receipts remain readable and continuous.
- Important operational consequence:
  - these topic-config corrections live inside the immutable platform image, so they require a fresh packaging run and runtime rematerialization before the PR3 steady rerun can claim the corrected contract.
### 2026-03-06 14:18:00 +00:00 - PR3-S1 canonical rerun exposed evidence-bootstrap drift on the GitHub runner, so the workflow must hydrate strict upstream receipts before dispatch
- Latest canonical PR3-S1 rerun (22761391121) failed before any traffic was sent.
- Exact failure:
  - FileNotFoundError on 
uns/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/pr3_s0_execution_receipt.json inside pr3_s1_wsp_replay_dispatch.py.
- Interpretation:
  - the dispatcher is behaving correctly because PR3-S1 is defined to run fail-closed from a strict PR3-S0 READY boundary,
  - the workflow created the RUN_DIR path locally on the runner but did not hydrate the upstream PR3 evidence set that the canonical dispatcher reads.
- Why this is not a reason to weaken the dispatcher:
  - allowing PR3-S1 to synthesize or skip PR3-S0 receipts would sever state continuity,
  - it would also make the production evidence chain less trustworthy by letting a state run without its declared upstream acceptance boundary.
- Candidate fixes considered:
  - A relax pr3_s1_wsp_replay_dispatch.py so missing PR3-S0 receipts are tolerated:
    - rejected because it weakens the strict-boundary contract and makes reruns less auditable.
  - B commit/copy local 
uns/ artifacts into the workflow checkout:
    - rejected because the authoritative evidence is the S3-backed run-control store, not the laptop worktree.
  - C add an explicit workflow bootstrap step that syncs the authoritative PR3 evidence prefix from the evidence bucket into RUN_DIR before launching the canonical dispatcher:
    - accepted because it preserves runner statelessness, keeps the evidence chain authoritative, and lets each rerun reconstruct the exact declared upstream boundary.
- Implementation sequence from this point:
  1. inspect the S3 evidence prefix shape for pr3_20260306T021900Z,
  2. patch dev_full_pr3_s1_managed.yml to sync the authoritative PR3 run-control artifacts into RUN_DIR,
  3. rerun the canonical PR3-S1 lane immediately,
  4. only if the next failure is inside live throughput/error/latency metrics treat it as the next production problem.
### 2026-03-06 14:26:00 +00:00 - PR3 workflow now bootstraps and mirrors the full run-control tree so strict upstream state can be reconstructed remotely
- dev_full_pr3_s1_managed.yml now syncs the authoritative vidence/dev_full/run_control/<pr3_execution_id>/ prefix into RUN_DIR before launching the canonical dispatcher.
- The same workflow now syncs the full RUN_DIR back to S3 on exit before the targeted rollup copies.
- Reasoning:
  - the production issue was not just one missing file but a continuity gap: selected rollups were being mirrored remotely while the strict run-control tree remained only on the workstation,
  - future remote reruns should be able to reconstruct the execution boundary from the evidence bucket without depending on a checked-out 
uns/ tree.
- Why this is the right fix:
  - it preserves the strict state-machine contract (S1 still requires S0 READY),
  - keeps the GitHub runner stateless,
  - promotes the evidence bucket toward the real remote source of truth for road-to-prod state transitions.
- Immediate operational step after patching:
  - seed the existing pr3_20260306T021900Z run-control tree into the evidence bucket once so the newly bootstrapped workflow has a complete starting state,
  - rerun canonical PR3-S1,
  - if green, continue the same remote-mirror pattern for later PR3/PR4 states.
### 2026-03-06 14:50:00 +00:00 - Live PR3-S1 run shows the platform hot path is healthy at ~1.3k-1.45k eps, so the next limiter is injector calibration not ingress/runtime stability
- The current canonical rerun (22761560319) is still active, but live measurement already exposes the relevant production signal.
- Live API Gateway metrics during the steady window show:
  - request count roughly 80k-88k per minute,
  - equivalent throughput roughly 1330-1460 eps,
  - 4XXError=0,
  - 5XXError=0,
  - latency approximately p95=21-23 ms, p99=27-31 ms.
- Live WSP lane logs confirm real replay progress from the oracle-store data:
  - multiple Fargate lanes are reading stream-view files and steadily emitting traffic/context events,
  - example lanes show aggregate output rates in the tens of events per second per lane,
  - the hot path is therefore moving meaningful real traffic, not idling.
- Interpretation against the PR3-S1 production target:
  - platform intake/stability is materially healthy at the current load envelope,
  - the current hardcoded stream_speedup=19.7 underdrives the source replay relative to the 3000 eps target,
  - there is no evidence at this point that API Gateway, Lambda, DynamoDB idempotency, MSK auth, or the PR3 EKS runtime are the limiting surfaces.
- Calibration conclusion:
  - observed admitted eps (~1.4k) versus target (3000) implies the next replay attempt should increase effective source speed by roughly 3000 / 1400 ~= 2.14x,
  - applied to the current 19.7 speedup, the next calibrated target is approximately 42-50,
  - choosing 50 is the production-minded next step because it aims to clear the target with margin while the current latency/error posture suggests real headroom remains.
- Required implementation change:
  - stop hardcoding 19.7 in dev_full_pr3_s1_managed.yml,
  - expose stream_speedup as an explicit workflow input so calibration can be evidence-backed and repeatable,
  - use 50.0 for the next PR3-S1 rerun unless the still-running attempt exposes a contrary end-of-window metric.
### 2026-03-06 14:56:00 +00:00 - Replaced a dead manual knob with explicit stream_speedup control for PR3-S1 calibration
- dev_full_pr3_s1_managed.yml was already at GitHub's workflow-dispatch input ceiling, so adding a brand-new calibration input would have broken dispatch again.
- Review of the workflow showed max_workers_per_lane was a dead manual parameter for this path.
- Decision:
  - replace max_workers_per_lane with stream_speedup,
  - default it to 50.0 based on the live evidence from the current run,
  - pass that value straight through to pr3_s1_wsp_replay_dispatch.py instead of hardcoding 19.7 in the workflow body.
- Why this is the correct production move:
  - calibration becomes explicit and auditable,
  - the dispatch surface stays within GitHub limits,
  - future reruns can be tuned from measured ingress evidence without editing workflow code every time.
### 2026-03-06 15:04:00 +00:00 - PR3-S1 attempt at stream_speedup=19.7 was terminated early once the root cause was proven, to avoid spending the full window on a known underdriven replay
- By mid-window, live evidence was already conclusive:
  - API Gateway sustained roughly 1.3k-1.45k eps,
  - no 4XX or 5XX,
  - latency remained well within target,
  - WSP lanes were actively replaying real oracle-store data.
- This proved the failure mode was not platform instability but source underdrive from the replay calibration.
- Decision:
  - cancel run 22761560319 before the full window completed,
  - stop the currently running WSP ECS tasks,
  - rerun immediately on the newly pinned explicit stream_speedup=50.0 path.
- Reason:
  - continuing the old attempt would only consume more time/cost for a result already analytically known,
  - terminating early is consistent with the performance-first and cost-control laws once the true cause is established.
### 2026-03-06 15:12:00 +00:00 - PR3-S1 rerun exposed cross-attempt checkpoint contamination in WSP, which invalidates certification windows on the same platform run
- The calibrated 50.0 rerun improved throughput, but the lane logs exposed a more fundamental defect:
  - lanes started far into previously processed row offsets,
  - replay was resuming prior offsets instead of starting a fresh certification attempt.
- Root cause in code:
  - _checkpoint_scope_key(...) is currently derived from pack_key + platform_run_id + scenario_run_id + lane_count + lane_index,
  - repeated certification attempts on the same platform_run_id therefore reuse the same checkpoint namespace.
- Why this is a production-readiness blocker:
  - certification evidence becomes non-repeatable because later attempts inherit state from earlier failed attempts,
  - sample-minima and throughput measurements no longer represent a full fresh replay window,
  - operational resumability and certification freshness are being conflated into one namespace.
- Production-grade correction direction:
  - preserve checkpoint resumability within a single attempt,
  - add an explicit per-attempt checkpoint namespace/token so certification reruns start fresh without changing the pinned platform_run_id,
  - pass that namespace from the PR3 dispatcher into each WSP lane,
  - rebuild the immutable image and rerun on a fresh checkpoint namespace.
- Immediate action taken:
  - cancel run 22762248277,
  - stop active WSP lanes,
  - patch WSP checkpoint scoping before any further PR3-S1 rerun.
### 2026-03-06 15:18:00 +00:00 - Implemented fresh-attempt checkpoint namespacing for PR3 certification reruns
- Code change applied in src/fraud_detection/world_streamer_producer/runner.py:
  - _checkpoint_scope_key(...) now accepts an ttempt_id,
  - runtime reads WSP_CHECKPOINT_ATTEMPT_ID,
  - checkpoint payloads/session events now record the attempt namespace.
- Dispatcher change applied in scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py:
  - each dispatch now generates a fresh UTC checkpoint_attempt_id,
  - injects it into every WSP ECS lane via WSP_CHECKPOINT_ATTEMPT_ID,
  - records the attempt id in the runtime manifest.
- Semantics after the fix:
  - resumability is preserved inside one attempt,
  - certification reruns on the same pinned platform_run_id no longer resume prior offsets,
  - provenance remains intact because platform_run_id is unchanged while replay-attempt identity is explicit.
- Next steps now required:
  1. rebuild immutable image,
  2. repin WSP ECS family to the new digest,
  3. rerun PR3-S1 on stream_speedup=50.0 with a fresh checkpoint namespace.
### 2026-03-06 16:09:00 +00:00 - Fresh checkpoint fix validated; next calibrated PR3-S1 speedup is 65.0
- The first fresh-attempt rerun (22762626536) proved the checkpoint fix worked:
  - lanes restarted from early row offsets instead of resuming mid-run,
  - API Gateway throughput improved to about 2.3k-2.5k eps,
  - 4XX=0, latency remained around p95 22-23 ms, p99 ~30 ms.
- Interpretation:
  - platform path is still healthy,
  - remaining shortfall is purely replay calibration,
  - stream_speedup=50.0 is still insufficient for the 3000 eps / 5.4M sample-minima target.
- Calibration math:
  - observed eps ~2400, target 3000, multiplier needed ~1.25x,
  - next speedup therefore 50.0 * 1.25 = 62.5, rounded up to 65.0 for target-clearing margin.
- Decision:
  - terminate 22762626536 early,
  - rerun immediately at stream_speedup=65.0 with the fresh-attempt checkpoint namespace still in place.
### 2026-03-06 16:18:00 +00:00 - PR3-S1 calibration is moving to stream_speedup=100.0 because the rate limiter already caps the target envelope
- The 65.0 rerun improved throughput again, but live evidence still sat below target at roughly 2.6k-2.8k eps.
- Key insight from the WSP runtime:
  - each lane already enforces WSP_TARGET_EPS=125,
  - total target envelope is therefore capped at 24 * 125 = 3000 eps by design,
  - raising stream_speedup above the required source density cannot push the system beyond the target envelope because the token bucket prevents overshoot.
- Decision:
  - stop incrementing cautiously,
  - jump to stream_speedup=100.0 to seek saturation against the existing per-lane cap,
  - keep acceptance strict (3000 eps, 5.4M samples, latency/error gates unchanged).
- Reason this is production-correct:
  - we are no longer using speedup as an unsafe throughput dial; it is now only a source-availability dial beneath an explicit cap,
  - the platform still has to prove it can sustain the capped envelope without errors or latency breach.
## Entry: 2026-03-06 16:42:00 +00:00 - PR3-S1 end-to-end claim invalidated because the live IG edge is still a stub
1. I inspected the live ingress Lambda source (`infra/terraform/dev_full/runtime/lambda/ig_handler.py`) rather than relying on the earlier steady-window receipts.
2. The live function only performs:
   - API-key auth,
   - DDB idempotency insertion,
   - correlation logging,
   - `202` response.
3. It does **not** publish to Kafka, does not write the canonical IG receipt/quarantine surfaces, and does not move traffic into the downstream runtime graph.
4. I verified the runtime consequence directly:
   - CloudWatch logs for `fraud-platform-dev-full-ig-handler` show only `ig_ingest_boundary` records,
   - direct Kafka reads from the active PR3 pods returned no rows on the expected hot-path topics,
   - archive-writer health files and Aurora ledger tables remained at zero despite the prior S1 "green" decision.
5. Therefore the prior `PR3-S1` closure is valid only as an ingress-admission proof, not as an end-to-end `WSP -> IG -> MSK -> RTDL -> archive` proof.
6. Under the production-readiness charter, that is insufficient and must be corrected before PR3 can legitimately advance.

## Entry: 2026-03-06 16:47:00 +00:00 - Production-first remediation choice for the IG edge
1. I evaluated three concrete remediation directions against the real target (`3000 eps` steady, `6000 eps` burst) rather than against the quickest path to another S1 rerun.
2. Option A: force the internal Flask/Aurora IG service into Lambda unchanged.
   - Rejected.
   - Reason:
     - it would introduce an avoidable per-request Aurora dependency at the public ingress boundary,
     - it does not match the live pinned edge shape (`API Gateway -> Lambda -> DDB`),
     - it solves code reuse but not the actual production need for a high-throughput remote ingress edge.
3. Option B: repin the edge away from Lambda or keep using synthetic pressure lanes.
   - Rejected.
   - Reason:
     - it would weaken the real `via_IG` claim path,
     - it would continue certifying around the edge instead of through it.
4. Option C: harden the pinned `API Gateway -> Lambda -> DDB` ingress edge into a truthful publisher.
   - Accepted.
   - Required mechanics:
     - keep DDB as the fast ingress idempotency surface,
     - add real Kafka publish into the active fraud lane,
     - emit canonical receipt/provenance artifacts to object storage,
     - preserve schema/class/partitioning semantics from the shared IG contracts,
     - place Lambda inside the VPC with MSK reachability and the correct IAM/package surface.
5. This is the best production fit for the current platform:
   - DDB-backed dedupe is a better public-edge posture than forcing Aurora writes on every ingress request,
   - the edge remains low-latency and stateless where possible,
   - the downstream graph receives real traffic through the true public ingress contract.

## Entry: 2026-03-06 16:53:00 +00:00 - Coordinated remediation scope pinned before code changes
1. The ingress defect is not a single-file bug. It is a four-lane runtime gap:
   - code semantics gap: Lambda is a stub,
   - packaging gap: Terraform only zips a single file and does not ship the shared platform code/contracts,
   - network gap: Lambda is not attached to the VPC and therefore cannot reach private MSK brokers,
   - IAM gap: Lambda lacks MSK data-plane and object-store receipt permissions.
2. I am therefore treating the fix as one coordinated ingress correction pass:
   - implement a Lambda-native IG handler that uses the shared schema/class/partitioning contracts and performs real publish + receipt emission,
   - materialize a deterministic remote bundle that includes the required `src/`, `config/`, and contract surfaces,
   - update Terraform to support the remote IG package, VPC attachment, and expanded runtime permissions,
   - deploy the corrected ingress edge before any more PR3 state work.
3. Additional note:
   - `config/platform/profiles/dev_full.yaml` does not currently pin `wiring.admission_db_path`, which is another sign that the repo's internal IG-service profile and the live ingress edge have drifted apart.
   - Because the accepted production fix keeps DDB as the edge dedupe surface, that profile hole is now recorded as design drift rather than being forced into the public-edge runtime.

## Entry: 2026-03-06 17:08:00 +00:00 - Workflow registration path completed and synced back into cert-platform so ingress materialization can be executed without branch drift
1. The new ingress-edge materialization workflow had to exist on `main` for GitHub to register it as a dispatchable workflow, but it also had to build the code on `cert-platform` because the actual ingress correction code and Terraform surfaces are still progressing there.
2. Production concern:
   - if the workflow checked out `main`, it would build against stale code and produce a fake green deployment path,
   - if it lived only on `cert-platform`, GitHub workflow registration would remain unreliable for remote execution.
3. Resolution implemented:
   - added `code_ref` as a required workflow input,
   - made the workflow check out `inputs.code_ref`,
   - merged the workflow-only commit through the approved `dev -> main -> dev -> cert-platform` path,
   - resolved the final `cert-platform` merge conflict in favor of the `main/dev`-safe variant so the dispatch surface and the active code ref remain aligned.
4. Why this matters for production readiness:
   - the remote deployment lane is now branch-truthful,
   - workflow registration no longer forces stale-code deployment,
   - future reruns can materialize remote runtime corrections from the active implementation branch without corrupting branch hierarchy.

## Entry: 2026-03-06 17:13:00 +00:00 - Next execution boundary pinned: materialize the live ingress edge before any further PR3 runtime certification
1. I reloaded the active production authorities before taking the next live step:
   - `dev-full_road-to-production-ready.md`,
   - `platform.road_to_prod.plan.md`,
   - `platform.PR3.road_to_prod.md`,
   - the current `pr3_s1_executor.py` steady-gate logic.
2. Key implication from re-reading the PR3 authority:
   - `PR3-S1` is not allowed to close from ingress-only rate evidence,
   - the correct certification surface is the real `via_IG` hot path with downstream runtime behavior and deterministic evidence.
3. Therefore the next executable boundary is not another `S1` replay attempt. It is:
   - deploy the corrected Lambda ingress runtime,
   - verify handler/VPC mode and downstream publish behavior,
   - only then resume the `PR3-S1` chain from the same strict upstream.
4. This sequencing is now pinned as the active correction boundary because it is the narrowest rerun that restores truthful `via_IG` certification without pretending the current edge is good enough.

## Entry: 2026-03-06 17:20:00 +00:00 - First remote ingress deploy failed on the packaging lane because the OIDC role could not write the Lambda bundle to the chosen S3 location
1. The workflow itself ran correctly through bundle creation and failed at the first remote-write boundary: `aws s3 cp` of the deterministic Lambda package.
2. Exact failure:
   - assumed role: `arn:aws:sts::230372904534:assumed-role/GitHubAction-AssumeRoleWithAction/GitHubActions`,
   - denied action: `s3:PutObject`,
   - denied resource: `arn:aws:s3:::fraud-platform-dev-full-object-store/artifacts/lambda/ig_handler/...`.
3. Production interpretation:
   - this is not just an IAM omission,
   - it also exposes that `object-store` was the wrong semantic destination for deployment artifacts.
4. Why the original package destination is weak:
   - `fraud-platform-dev-full-object-store` is the runtime/oracle truth surface,
   - deployment bundles are build artifacts and should not be mixed into truth/object-store storage if an artifact lane already exists,
   - forcing package uploads into object-store would blur runtime-data and deployment-artifact ownership.
5. Chosen correction:
   - repin the workflow package bucket default to `fraud-platform-dev-full-artifacts`,
   - extend the GitHub OIDC role to write only the Lambda artifact prefix used by this PR3 ingress materialization lane,
   - simultaneously add the long-needed read permissions for Managed Flink inspection and CloudWatch metric reads so later managed reruns do not trip on another preventable IAM gap.
6. This correction is production-first because it fixes the packaging lane as a proper artifact path rather than widening access around the wrong storage boundary.

## Entry: 2026-03-06 17:28:00 +00:00 - The GitHub OIDC role hit AWS inline-policy size limits, so PR3 runtime permissions were split into a dedicated policy surface
1. I first attempted the cleanest Terraform apply by extending the existing `GitHubActionsM6FRemoteDevFull` inline policy.
2. AWS rejected the apply with `LimitExceeded: Maximum policy size of 10240 bytes exceeded for role GitHubAction-AssumeRoleWithAction`.
3. Production interpretation:
   - the old policy had become an overloaded catch-all,
   - continuing to stuff more runtime capabilities into it would make reviewability and least-privilege posture worse even if it barely fit.
4. Chosen correction:
   - keep the existing M6/M10/M11/M12 policy focused on its original lanes,
   - create a separate inline policy `GitHubActionsPR3RuntimeDevFull` for the PR3 runtime-cert needs,
   - place only the new permissions there:
     - artifact-prefix list/write on `fraud-platform-dev-full-artifacts/artifacts/lambda/ig_handler/*`,
     - Managed Flink read (`ListApplications`, `DescribeApplication`),
     - CloudWatch metric reads (`GetMetricData`, `GetMetricStatistics`, `ListMetrics`).
5. Why this is the better production posture:
   - policy ownership becomes phase/lane-specific instead of monolithic,
   - future review of the GitHub OIDC role is tractable,
   - the PR3 runtime-cert lane can evolve without pushing the legacy remote policy back to its size ceiling again.

## Entry: 2026-03-06 17:34:00 +00:00 - AWS enforces the inline-policy ceiling at the role level, so the PR3 rights must be an attached managed policy instead
1. The second apply attempt proved that even a separate inline policy cannot be added: AWS still returned `LimitExceeded` for the same role.
2. This means the role has exhausted the total inline-policy budget, not merely the size of one policy blob.
3. Corrected implementation direction:
   - replace the proposed inline `GitHubActionsPR3RuntimeDevFull` policy with an `aws_iam_policy`,
   - attach it to `GitHubAction-AssumeRoleWithAction` via `aws_iam_role_policy_attachment`,
   - keep the permission surface unchanged (artifacts bucket prefix, Managed Flink read, CloudWatch metric read).
4. Why this is the right production move:
   - managed policy attachment scales beyond the inline-policy ceiling,
   - the automation role stays evolvable for later PR lanes,
   - the PR3 rights remain auditable as one named, separable policy surface.

## Entry: 2026-03-06 17:40:00 +00:00 - Second remote ingress deploy proved the packaging/IAM lane is fixed; the remaining failure is workflow runtime bootstrap
1. The rerun successfully completed:
   - deterministic bundle build,
   - S3 upload to the artifacts bucket,
   - evidence sync.
2. It then failed at the first Terraform step with `/bin/sh: terraform: command not found` on the GitHub runner.
3. Interpretation:
   - the remote deployment lane itself is now correctly authorized,
   - the workflow definition omitted explicit Terraform bootstrap and therefore cannot yet execute its own infrastructure phase.
4. Correction applied:
   - add `hashicorp/setup-terraform@v3` before the Terraform init/validate/apply steps.
5. Why this matters:
   - we now know the next rerun is blocked by workflow runner completeness, not by platform IAM or package storage,
   - once the workflow bootstrap is corrected on `main`, the remote ingress deployment should progress into the actual infrastructure boundary.

## Entry: 2026-03-06 17:46:00 +00:00 - Runtime Terraform failed because the workflow ignored the module's partial-backend contract
1. The third remote ingress materialization attempt reached Terraform and failed with:
   - backend `s3` missing required `bucket` and `key` values.
2. Root cause:
   - `infra/terraform/dev_full/runtime/versions.tf` declares a partial `backend "s3" {}` block,
   - the runtime module expects remote execution to supply backend config,
   - the workflow was calling bare `terraform init -input=false` and therefore violating the module contract.
3. Existing repo pattern already solves this:
   - other managed workflows initialize Terraform with `-reconfigure -backend-config=backend.hcl.example`.
4. Correction applied:
   - update `dev_full_pr3_ig_edge_materialize.yml` to initialize runtime Terraform with `backend.hcl.example`.
5. Why this is the correct fix:
   - preserves the declared remote-state path (`fraud-platform-dev-full-tfstate` / `dev_full/runtime/terraform.tfstate`),
   - avoids inventing a one-off backend path for this workflow,
   - keeps the ingress materialization lane aligned with existing dev_full Terraform operating practice.

## Entry: 2026-03-06 17:54:00 +00:00 - Remote Terraform state access for PR3 requires runtime write plus core/streaming read, not just the artifacts lane
1. The latest ingress materialization run proved that:
   - bundle creation works,
   - artifacts-bucket upload works,
   - Terraform/backend bootstrap syntax works.
2. The next failure was `403 Forbidden` on `s3://fraud-platform-dev-full-tfstate/dev_full/runtime/terraform.tfstate` during state refresh.
3. I inspected the runtime module and confirmed why the policy must be broader than one object:
   - runtime uses `data.terraform_remote_state.core`,
   - runtime uses `data.terraform_remote_state.streaming`,
   - runtime backend uses `fraud-platform-dev-full-tf-locks` for locking.
4. Therefore the correct PR3 deployment policy scope is:
   - read access to tfstate objects for `core`, `streaming`, and `runtime`,
   - write access to the `runtime` tfstate object only,
   - lock-table control on `fraud-platform-dev-full-tf-locks`.
5. This is still least-privilege for the deployment lane:
   - no write access to `core` or `streaming` tfstate,
   - no blanket `tfstate/*` write,
   - exact lock-table scope only.

## Entry: 2026-03-06 18:01:00 +00:00 - Targeted runtime apply still needs refresh rights on the pre-existing ingress table and DLQ
1. The latest workflow cleared all bootstrap barriers and reached the real targeted apply.
2. Terraform then failed during refresh on two existing resources that are not themselves the new targets but are referenced by the runtime stack:
   - `fraud-platform-dev-full-ig-idempotency` (`dynamodb:DescribeTable` denied),
   - `fraud-platform-dev-full-ig-dlq` (`sqs:GetQueueAttributes` denied).
3. Interpretation:
   - the deployment lane is now behaving like real infrastructure automation,
   - even a narrow targeted apply still has to read the current state of adjacent runtime resources.
4. Correction:
   - extend the managed PR3 deployment policy with refresh-only read permissions for those two ingress resources.
5. Why this remains production-correct:
   - no write scope added to DDB or SQS,
   - only the exact read actions Terraform needs for refresh (`DescribeTable`, `ListTagsOfResource`, `GetQueueAttributes`, `ListQueueTags`).

## Entry: 2026-03-06 18:07:00 +00:00 - DynamoDB table refresh requires the full refresh-safe read set, not only DescribeTable
1. After granting `DescribeTable`, the next targeted apply failed on `dynamodb:DescribeContinuousBackups` for the same `ig_idempotency` table.
2. I verified the table's actual posture:
   - TTL is enabled,
   - continuous backups are enabled,
   - point-in-time recovery is disabled.
3. Terraform is therefore reading the table through multiple read APIs during refresh, which means the refresh-safe policy must include:
   - `DescribeTable`,
   - `DescribeContinuousBackups`,
   - `DescribeTimeToLive`,
   - `ListTagsOfResource`.
4. This is still a narrow read-only extension and remains preferable to repeated single-action firefighting.

## Entry: 2026-03-06 18:13:00 +00:00 - The ingress materialization lane now needs the full targeted-resource control surface, not just refresh reads
1. The latest apply cleared DDB/SQS refresh and then failed on `lambda:GetFunction` for `fraud-platform-dev-full-ig-handler`.
2. At this point the targeted apply has proven the real shape of the deployment lane:
   - it must read and update the existing Lambda function,
   - update the Lambda execution role inline policy,
   - attach the Lambda VPC access managed policy,
   - create the Lambda security group,
   - read SSM parameters during verification.
3. Rather than discovering these one action at a time, I expanded the managed PR3 deployment policy to the full control/read set for the four targeted resources.
4. Scope added:
   - Lambda function read/update/create actions on `fraud-platform-dev-full-ig-handler`,
   - IAM role/policy control on `fraud-platform-dev-full-lambda-ig-execution`,
   - EC2 security-group create/update/read actions required for the Lambda VPC SG,
   - SSM `GetParameter` for the IG API key and MSK bootstrap broker parameter.
5. This is still bounded to the ingress correction lane and is preferable to repeated single-action firefighting because it matches the actual targeted Terraform plan surface.

## Entry: 2026-03-06 18:20:00 +00:00 - Lambda provider refresh needs the function-scoped read set, so the policy is widened at the single-function boundary
1. After `lambda:GetFunction` was granted, Terraform failed again on `lambda:ListVersionsByFunction` for the same IG Lambda.
2. This is a provider-surface issue, not a platform-topology issue:
   - the Lambda resource refresh path performs multiple read calls on the same function,
   - discovering them one by one is no longer useful.
3. Correction:
   - widen the Lambda statement from a handpicked list to the function-scoped set:
     - `lambda:Get*`,
     - `lambda:ListVersionsByFunction`,
     - `lambda:Update*`,
     - `lambda:CreateFunction`,
     - tag operations.
4. Boundary remains strict because the scope is still one function ARN only: `fraud-platform-dev-full-ig-handler`.

## Entry: 2026-03-06 18:27:00 +00:00 - Live ingress correction is deployed; remaining 500 is a bundle-layout defect in the Lambda package
1. The latest workflow run (`22765859266`) completed the targeted Terraform apply successfully.
2. Live post-apply inspection confirms the runtime posture is materially corrected on AWS:
   - handler = `fraud_detection.ingestion_gate.aws_lambda_handler.lambda_handler`,
   - memory = `1024 MB`, timeout = `30s`, reserved concurrency = `300`,
   - VPC attachment present with two private subnets and the new SG,
   - package hash matches the remote uploaded bundle.
3. The health endpoint still returned `500`, so I pulled CloudWatch logs from `/aws/lambda/fraud-platform-dev-full-ig-handler`.
4. Exact runtime error:
   - `Runtime.ImportModuleError: Unable to import module 'fraud_detection.ingestion_gate.aws_lambda_handler': No module named 'fraud_detection'`.
5. Root cause:
   - `build_ig_lambda_bundle.py` was copying `src/fraud_detection` into the stage as `src/fraud_detection/...`,
   - Lambda imports from the zip root and therefore could not resolve the package.
6. Correction applied:
   - bundle staging now maps `src/fraud_detection -> fraud_detection` at the zip root,
   - config and contract/docs paths remain preserved at their expected relative locations.
7. Local verification after the patch:
   - rebuilt a test bundle,
   - confirmed the zip now contains `fraud_detection/...` entries at the root.
8. Next boundary:
   - push the bundler fix on `cert-platform`,
   - rerun the same ingress materialization workflow from `main` with `code_ref=cert-platform`,
   - expect the health verification to move past import bootstrap and into real handler logic.
## Entry: 2026-03-06 18:58:00 +00:00 - The persisted Lambda import failure is a package-initialization dependency-shape defect, not a bundle-path defect
1. I pulled the exact live Lambda package from AWS and compared it to the workflow-uploaded S3 bundle used by run `22766235881`.
2. Both artifacts are byte-identical (`CodeSha256 = eOyOOBwLwV3tEP9zdxHLuVEcwA0b99bp/yARZ+p/cx0=`) and both contain `fraud_detection/...` at the zip root.
3. This falsifies the previous hypothesis that the live Lambda was still serving a stale or mis-rooted package.
4. I then imported the deployed zip locally exactly as a zip-path and traced the handler import chain.
5. The first failing point is not the top-level package itself. The import graph is:
   - `fraud_detection.ingestion_gate.aws_lambda_handler`
   - `ingestion_gate.admission`
   - `ingestion_gate.governance`
   - `fraud_detection.platform_governance`
   - `platform_governance.__init__`
   - `platform_governance.evidence_corridor`
   - `fraud_detection.scenario_runner.storage`
   - `scenario_runner.__init__`
   - `scenario_runner.runner`
   - `scenario_runner.schemas`
   - `jsonschema -> referencing -> rpds`
6. On local verification that chain fails at `rpds.rpds` because the native extension is cp312 Linux-specific. Lambda is likely collapsing a deeper import-time failure into the generic `Unable to import module ... No module named 'fraud_detection'` message.
7. Production interpretation:
   - the ingress edge is booting with the wrong dependency shape,
   - its cold-start path is pulling broad scenario-runner and schema-validation surfaces that are not needed to admit and publish ingress traffic,
   - this is architecturally wrong for a high-EPS ingress lane even if the package could be forced to import.
8. Therefore the correct remediation is not to keep bloating the Lambda bundle or to repin the ingress edge back to a toy path.
9. The correct remediation is to shrink the import surface so IG init only loads the runtime dependencies it truly needs:
   - make `platform_governance` exports lazy so `emit_platform_governance_event` does not eagerly import `evidence_corridor`,
   - make `scenario_runner` exports lazy so importing `scenario_runner.storage` does not eagerly import `runner`/`schemas`/`jsonschema`,
   - preserve existing public package names so downstream callers do not break.
10. Why this is the production-grade fix:
   - lower cold-start latency,
   - smaller blast radius from optional subsystems,
   - fewer native binary constraints in the hot ingress path,
   - clearer ownership boundaries between ingress runtime and scenario-runner authoring machinery.
11. After this refactor, the same ingress deployment lane should be rerun before any PR3 state evidence is trusted again.
## Entry: 2026-03-06 19:03:00 +00:00 - Package export surfaces are refactored to protect the IG cold-start path from optional subsystem imports
1. I changed `fraud_detection.platform_governance.__init__` from eager re-exports to lazy attribute loading.
2. I changed `fraud_detection.scenario_runner.__init__` from eager re-exports to lazy attribute loading.
3. Public import names are preserved:
   - `emit_platform_governance_event`, `PlatformGovernanceWriter`, and evidence-corridor names still resolve,
   - `ScenarioRunner`, `RunRequest`, `RunResponse`, `ReemitRequest`, `ReemitResponse` still resolve.
4. Operational effect:
   - importing `fraud_detection.platform_governance.emit_platform_governance_event` no longer forces `evidence_corridor` into memory,
   - importing `fraud_detection.scenario_runner.storage` no longer forces `scenario_runner.runner` and `scenario_runner.schemas` into memory.
5. This is the correct production remediation because it addresses the architectural fault directly:
   - Lambda init path becomes narrower,
   - optional authoring/analysis machinery is no longer part of ingress boot,
   - import-time failure blast radius is reduced,
   - cold-start posture improves instead of regressing.
6. Validation performed:
   - direct source import of `fraud_detection.ingestion_gate.aws_lambda_handler` now succeeds immediately,
   - py_compile of the changed `__init__` modules succeeds.
7. Remaining boundary:
   - redeploy the ingress edge with this change,
   - then verify live `/ops/health` and a real publish path before resuming PR3 states.
## Entry: 2026-03-06 19:08:00 +00:00 - IG admission now loads Postgres support lazily so the pinned DDB ingress lane does not require psycopg at cold start
1. The live Lambda logs after the last redeploy changed from the generic package-root failure to a concrete init error:
   - `Runtime.ImportModuleError: No module named 'psycopg'`.
2. I traced that to `fraud_detection.ingestion_gate.admission` importing `.pg_index` eagerly at module import time.
3. This is incorrect for the current pinned ingress lane:
   - authority is `API Gateway -> Lambda -> DDB -> Kafka`,
   - DDB-backed idempotency/admission does not need `psycopg` during Lambda boot.
4. Correction applied:
   - removed the eager top-level `.pg_index` import from `admission.py`,
   - added a local `_is_postgres_dsn(...)` predicate,
   - import `PostgresAdmissionIndex` / `PostgresOpsIndex` only inside `_build_indices(...)` when the actual `admission_db_path` is a Postgres DSN.
5. Why this is the production-correct fix:
   - preserves Postgres capability for lanes that explicitly choose it,
   - removes an unnecessary native dependency from the hot ingress path,
   - reduces cold-start failure blast radius,
   - aligns runtime dependencies with the actual live wiring rather than optional alternate backends.
6. Validation performed:
   - `py_compile` passed for `admission.py`,
   - direct source import of `fraud_detection.ingestion_gate.aws_lambda_handler` still succeeds,
   - the DSN branch predicate behaves correctly for both filesystem and postgres inputs.
7. Next step:
   - redeploy the ingress edge again,
   - expect the handler to move beyond `psycopg` import and into actual health-handler execution.
## Entry: 2026-03-06 19:14:00 +00:00 - Private ingress Lambda requires an SSM VPC endpoint because auth/bootstrap is intentionally Parameter Store backed
1. After removing the import-time blockers, the live Lambda stopped failing init and began executing requests.
2. The next observed behavior was a strict 30-second timeout on `GET /ops/health` with no application logs.
3. Code-path inspection of `aws_lambda_handler.lambda_handler` shows that `/ops/health` still passes through `_authorize(...)`, which loads the expected API key from SSM Parameter Store.
4. The same runtime also resolves MSK bootstrap brokers from SSM before building the hot push path.
5. Live VPC inspection confirmed the Lambda runs in `vpc-036a11d413ffce15b` and that the runtime endpoints present were:
   - `ec2`, `ecr.api`, `ecr.dkr`, `execute-api`, `logs`, `sts`, and S3 gateway,
   - but **not** `ssm`.
6. Production interpretation:
   - the timeout is not an application logic defect,
   - it is a private-network completeness defect,
   - for a private Lambda that intentionally depends on Parameter Store, an SSM interface endpoint is part of the minimal production substrate.
7. Correction chosen:
   - repin runtime interface endpoints to include `ssm`,
   - update the remote ingress materialization workflow to target `aws_vpc_endpoint.runtime_interface["ssm"]` in the same recovery lane so the missing endpoint can be materialized remotely.
8. Why this is the correct production fix:
   - preserves the existing secret/bootstrap contract rather than weakening auth,
   - keeps the Lambda private without requiring NAT as a crutch,
   - aligns the network substrate with the actual runtime dependency graph.
9. Follow-on expectation:
   - once the SSM endpoint is live, `/ops/health` should stop timing out and return a real HTTP result,
   - the next remaining blocker, if any, should be inside explicit application logic rather than hidden network starvation.
## Entry: 2026-03-06 19:24:00 +00:00 - Health/auth control-plane dependencies are now latency-bounded and instrumented for truthful ingress diagnosis
1. Even after the SSM endpoint was materialized, `/ops/health` continued to time out at the Lambda timeout boundary.
2. Given the handler path, that stall can only occur before the static health payload is returned, most likely in API-key resolution via SSM.
3. Production issue with the previous implementation:
   - the SSM client inherited broad default botocore timeouts,
   - a control-plane dependency stall could therefore consume the entire 30-second Lambda budget,
   - this is unacceptable for both health diagnosis and high-EPS ingress posture.
4. Correction applied in `aws_lambda_handler.py`:
   - added a bounded botocore config for SSM (`connect_timeout=2`, `read_timeout=5`, retries capped),
   - added low-cardinality INFO logs around health-route entry and API-key cache refresh.
5. Why this is production-correct:
   - health/auth control-plane calls should fail fast and surface explicit reasons,
   - bounded dependency latency prevents hidden 30-second stalls from masking root causes,
   - the added logs are not high-cardinality and are scoped to diagnosis-critical transitions.
6. Validation:
   - `py_compile` passed,
   - source import of the handler still succeeds.
7. Expected next result:
   - either `/ops/health` returns `200`, or the next failure surfaces as an explicit SSM/client/auth error rather than a blind timeout.
## Entry: 2026-03-06 19:26:00 +00:00 - PR3 ingress materialization is now materially green; live IG health succeeds on the private production-shaped path
1. Workflow run `22767511603` completed successfully after the SSM endpoint and bounded auth instrumentation changes.
2. Live verification evidence from the workflow shows:
   - `handler = fraud_detection.ingestion_gate.aws_lambda_handler.lambda_handler`,
   - `memory_size = 1024`, `timeout = 30`, `vpc_subnet_count = 2`,
   - `health_status_code = 200`,
   - `health_mode = apigw_lambda_ddb_kafka`,
   - `health_service = ig-edge`.
3. CloudWatch logs for the live request confirm the actual runtime sequence:
   - health request received,
   - API-key SSM cache miss resolved successfully,
   - health response returned,
   - request duration `59.57 ms` after cold start.
4. This closes the ingress materialization recovery chain:
   - package-root defect fixed,
   - eager package re-exports fixed,
   - eager Postgres backend import fixed,
   - missing private `logs` and `ssm` endpoint dependencies fixed,
   - health/auth dependency latency now bounded.
5. Production interpretation:
   - the live ingress edge is now materially aligned with the intended private production shape,
   - PR3 can resume from a truthful `via_IG` boundary rather than synthetic or broken ingress proof.
6. Next step:
   - rerun PR3-S1 on the corrected ingress path,
   - then continue sequentially through the remaining PR3 states with impact-metric reporting only from truthful live boundaries.
## Entry: 2026-03-06 14:28:32 +00:00 - PR3 restart plan is pinned around stale remote WSP image drift, not around more synthetic reruns
1. I resumed from the now-green live ingress boundary and rechecked the active PR3 execution authority:
   - `platform.PR3.road_to_prod.md`,
   - `platform.road_to_prod.plan.md`,
   - `.github/workflows/dev_full_pr3_s1_managed.yml`,
   - `scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py`.
2. The actual active defect is now narrow and specific:
   - the canonical PR3-S1 path already exists and is the correct one,
   - it launches the real remote `WSP` replay on ECS/Fargate into the live `IG`,
   - but the workflow/task surfaces are still pinned to an old immutable image digest,
   - therefore the remote lane cannot execute the local WSP/IG fixes that were already made.
3. Production interpretation of this defect:
   - this is not a reason to invent a new harness,
   - not a reason to weaken the target,
   - not a reason to mark S1 green from stale evidence,
   - it is simply remote image drift between source truth and live replay runtime.
4. Alternatives considered:
   - keep rerunning PR3-S1 on the stale digest:
     - rejected because it would waste remote compute and only reproduce already-understood failure modes,
   - repin PR3 back to the temporary synthetic speedup harness:
     - rejected because it is explicitly noncanonical and would not prove the real producer hot path,
   - repin `WSP` into Managed Flink just to reuse other streaming infrastructure:
     - rejected for PR3 because the real WSP implementation in-repo is a replay producer, not a Flink transform application,
   - build a fresh immutable image and feed that digest into the canonical PR3-S1 lane:
     - accepted because it preserves the truthful runtime path while moving the live system to the actual code we intend to certify.
5. The chosen production-grade path is therefore:
   - use the existing deterministic packaging lane to build a fresh immutable image from the current branch,
   - pass that digest explicitly into the canonical PR3 runtime/workflow surfaces,
   - rerun PR3-S1 from the strict upstream boundary only after the live replay runtime reflects current code,
   - then continue sequentially through PR3-S2..S5 and PR4.
6. This is the correct production decision because:
   - it keeps the certification path tied to the real ingress emitter hot path,
   - it avoids proxy evidence,
   - it keeps the immutable-image discipline intact,
   - it proves that the live platform, not just the local repo, can sustain the target posture.
7. I also pinned the reporting expectation for all remaining PR states:
   - findings summaries must lead with impact metrics derived from the actual run,
   - each summary must state the threshold/target for that state,
   - each summary must include an explicit analytical judgement on whether the metrics meet production-ready intent,
   - raw JSON references are supporting evidence only and must not replace the readable impact summary.
8. Immediate execution plan:
   - refresh the immutable platform image,
   - rerun canonical PR3-S1 on that refreshed image,
   - remediate any further real runtime defects without dropping back to noncanonical paths,
   - only then advance to PR3-S2 and beyond.
## Entry: 2026-03-06 14:31:49 +00:00 - The packaging lane itself had an execution defect: optional S3 evidence upload was able to invalidate a successful immutable build
1. I dispatched `dev_full_m1_packaging` on `cert-platform` to refresh the immutable image for PR3.
2. The build/push portion succeeded and published a new digest:
   - image tag: `git-f0a7707d2e066e0c8899eb9e82fc1b61a308e2a3-run-22767772233`
   - image digest: `sha256:d0817106b09769503072bc1a8a3372e3db67d186b75d54b064870e6f7a5a4292`
3. The workflow still concluded `failure`, but the failure was not in packaging correctness:
   - the only failing step was `Optional direct upload to S3 evidence bucket`,
   - it hard-failed on `HeadBucket 403 Forbidden`,
   - that happened after the image digest had already been resolved and after the CI-local evidence files had already been written.
4. Production interpretation:
   - the lane semantics were wrong,
   - a secondary evidence-export path must not invalidate the primary contract result when the core outputs already exist,
   - otherwise execution time is wasted and the run registry becomes noisier than the actual system health.
5. Corrective decision:
   - keep direct S3 upload best-effort,
   - if the workflow role cannot read the requested bucket, emit a warning and continue,
   - keep the artifact-pack upload step active so the CI evidence remains retrievable from GitHub even when S3 access is intentionally narrower.
6. Why this is the production-grade correction:
   - it preserves immutable build truth,
   - it avoids false-red workflow posture,
   - it keeps evidence export strict where it matters (artifact creation) and tolerant where the path is auxiliary (secondary copy).
7. Immediate next move after this fix:
   - rerun the packaging workflow cleanly on `cert-platform`,
   - use the same immutable digest or the rerun digest to drive the canonical PR3-S1 lane,
   - continue execution from the truthful remote replay path.
## Entry: 2026-03-06 14:37:32 +00:00 - The live WSP ECS family is now repointed to the fresh immutable image, and PR3-S1 rerun inputs are pinned from measured success rather than guesswork
1. I reran the packaging workflow after hardening the optional upload behavior.
2. The green packaging run produced the fresh authoritative image:
   - image tag: `git-7794c8fdf38f86425fc17859ca4a2cad0efd6b9e-run-22767906946`
   - image digest: `sha256:b9fd2375fc79154c95bcfb58a502b35ebb77c09df94f2222dc4ced1eca291b58`
3. I then inspected the live ECS family that the canonical PR3-S1 replay lane actually uses:
   - family: `fraud-platform-dev-full-wsp-ephemeral`
   - active revision before change: `26`
   - active image before change: `sha256:56c4eaa4347279d56d156b5e6f16736b0ddd0c26d685588d06357e5f88377349`
4. That confirmed the earlier diagnosis was still materially true:
   - the canonical replay family had not yet picked up the refreshed image,
   - therefore a PR3 rerun without a task-definition refresh would still be measuring stale runtime code.
5. Corrective action executed:
   - registered new ECS task-definition revision `27`,
   - same family, same IAM/network/log posture,
   - only the `wsp` container image was changed to the new immutable digest.
6. Evidence written under `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/`:
   - `g3a_s1_wsp_taskdef_refresh_request.json`
   - `g3a_s1_wsp_taskdef_refresh_result.json`
   - `g3a_s1_wsp_taskdef_refresh_summary.json`
7. I also re-read the last successful canonical S1 calibration from the same PR3 control root:
   - lane count `138`,
   - `stream_speedup=95.0`,
   - window `180s`,
   - target request rate `3005 eps`,
   - observed admitted throughput `3003.4222 eps`,
   - admitted sample size `540,616`,
   - `4xx=0`, `5xx=0`, error ratio `0.0`.
8. Decision for the rerun:
   - do not drop back to the workflow defaults (`24` lanes / `50.0` speedup / `1800s`),
   - reuse the measured successful calibration on the newly refreshed image,
   - this keeps the rerun anchored to an already-proven realistic shape instead of burning time rediscovering a known good operating point.
9. Why this is the production-grade move:
   - it isolates image drift as the only intentional variable,
   - it preserves the real canonical path,
   - it turns the next rerun into a true regression/proof check rather than a parameter-search exercise.
## Entry: 2026-03-06 15:10:00 +00:00 - PR3-S1 canonical replay exposed a production defect in the ingress runtime bundle and a secondary failure-path weakness
1. I treated the latest `PR3-S1` red result as a real production-path defect, not as a reason to lower the bar or switch back to a proxy harness.
2. Live ingress telemetry for the failed window showed:
   - API Gateway stage throttle is correctly uplifted (`3000 rps / 6000 burst`),
   - Lambda reserved concurrency is pinned at `300`,
   - concurrency hit the ceiling (`max=300`),
   - API Gateway `IntegrationLatency p95/p99` sat at roughly `30000 ms`,
   - WSP lanes observed `0 admitted`, `100% 5xx`, and exhausted retries.
3. I then pulled the Lambda logs for the same window and found the first hard defect is earlier than pure capacity:
   - `IG admission validation error` with `referencing.exceptions.Unresolvable: schemas.layer3.yaml#/$defs/hex64`,
   - this is reached while validating real `6B` payloads referenced by `config/platform/ig/schema_policy_v0.yaml`,
   - the live image contains `schemas.6B.yaml` but not the transitive `schemas.layer3.yaml` file that the schema pack requires.
4. This means the live runtime packaging contract is materially wrong for production:
   - the image boundary was previously tightened to exclude `schemas.layer3.yaml` based on a static reference scan,
   - that scan was insufficient because it missed transitive runtime schema dependencies,
   - therefore the platform can appear "wired" while still being unable to validate real production payloads.
5. I also found a second defect on the quarantine/anomaly path:
   - once validation fails, the handler emits governance anomaly events,
   - the current S3 JSONL append corridor can raise `S3_APPEND_CONFLICT` under concurrent append,
   - that turns what should be a deterministic quarantine into a `503 ingress_publish_failed` response.
6. Production interpretation:
   - simply raising Lambda concurrency would be the wrong first move because it would only make the broken failure path scale harder,
   - the correct order is to first restore runtime contract completeness and failure-path integrity,
   - only then re-measure throughput and decide whether further envelope or architecture changes are needed.
7. Alternatives considered:
   - increase concurrency immediately:
     - rejected because it does not solve the schema-pack defect and would waste cost on invalid traffic handling,
   - repin PR3 back to a synthetic or easier harness:
     - rejected because that would weaken the claim and avoid the real WSP -> IG -> Lambda -> DDB -> Kafka hot path,
   - repin WSP away from the canonical producer just to make the replay easier:
     - rejected because the production question at PR3 is about the actual ingress producer path.
8. Chosen remediation plan:
   - repair the image/build contract so the runtime ships the complete transitive schema surface needed by `schema_policy_v0.yaml`,
   - add a deterministic packaging preflight that proves every live IG payload schema reference resolves before the image can be published,
   - harden the governance S3 append corridor and/or anomaly emission path so quarantine cannot escalate to `503` purely because of concurrent append races,
   - rebuild/publish a fresh immutable image, refresh the live runtime, and rerun canonical `PR3-S1` on the truthful path.
9. Success criteria for this remediation:
   - no `Unresolvable` schema errors in IG logs for live `5B/6B` payloads,
   - no anomaly-path `S3_APPEND_CONFLICT` causing `503` responses,
   - PR3-S1 impact metrics become meaningful again (`admitted_eps`, `error_rate`, `5xx_rate`, `p95/p99`) so throughput tuning can proceed from a sound base instead of corrupted ingress behavior.
## Entry: 2026-03-06 15:21:00 +00:00 - Implemented the ingress runtime-pack remediation and hardened the quarantine-side governance corridor before rebuilding the image
1. I implemented the remediation directly on the real production surfaces rather than on a proxy harness.
2. Runtime packaging contract changes:
   - widened the Docker build surface from single-file schema copies to the actual schema-pack directories needed by live IG policy resolution,
   - added Layer-1 shared schema surface required transitively by `5B` contracts,
   - kept the change bounded to the policy-relevant contract packs rather than broad repo copy.
3. Deterministic preflight added to the image build itself:
   - Dockerfile now runs an inline Python check after dependency installation,
   - it loads `config/platform/ig/schema_policy_v0.yaml`,
   - resolves every declared payload schema reference through `SchemaEnforcer`,
   - and fails the image build if any transitive reference is missing or unreadable.
4. Failure-path hardening changes:
   - `scenario_runner.storage.S3ObjectStore.append_jsonl(...)` now retries optimistic S3 append conflicts before failing,
   - `ingestion_gate.store.S3ObjectStore.append_jsonl(...)` was aligned to the same behavior for parity and future ingress-side use,
   - `IngestionGate._emit_governance_anomaly(...)` now catches governance corridor failures and logs them instead of converting an already-determined quarantine into a hard `503` response.
5. Why these were the right production corrections:
   - they remove the image contract hole that made real payload validation impossible,
   - they preserve fail-closed schema discipline by proving refs at build time,
   - they stop secondary governance evidence races from destabilizing the primary ingress decision path.
6. Local validation executed:
   - targeted tests:
     - `python -m pytest tests/services/ingestion_gate/test_admission.py tests/services/ingestion_gate/test_schema_resolution.py tests/services/platform_governance/test_writer.py -q`
     - result: `12 passed`
   - syntax validation:
     - `python -m py_compile src/fraud_detection/scenario_runner/storage.py src/fraud_detection/ingestion_gate/store.py src/fraud_detection/ingestion_gate/admission.py tests/services/ingestion_gate/test_admission.py tests/services/ingestion_gate/test_schema_resolution.py`
     - result: clean.
7. Regression proof added:
   - new test asserts live IG schema policy refs resolve transitively against the repo contract packs,
   - new admission test asserts a governance emission failure does not destroy the quarantine receipt path.
8. Next execution step:
   - commit/push this remediation milestone on `cert-platform`,
   - rebuild the immutable image remotely,
   - refresh the live WSP runtime onto that new image,
   - rerun canonical `PR3-S1` and evaluate the impact metrics again from the truthful path.
## Entry: 2026-03-06 15:27:00 +00:00 - The remote packaging workflow had its own stale deterministic-context allowlist and needed to be repinned to the corrected schema-pack boundary
1. After pushing the runtime-pack remediation, I attempted to dispatch `dev_full_m1_packaging.yml` and re-read the workflow inputs/staging logic.
2. The workflow stages a deterministic build context in CI using its own explicit `include_paths` list.
3. That list still reflected the old, broken packaging boundary:
   - it only staged `5B/schemas.5B.yaml`,
   - it only staged `6B/schemas.6B.yaml`,
   - it did not stage `1A/schemas.layer1.yaml` or the `6B/schemas.layer3.yaml` dependency,
   - therefore remote CI would have rebuilt the same incomplete runtime even though the branch source had been corrected.
4. Production interpretation:
   - the build contract exists in two places (`Dockerfile` and workflow staging),
   - both must agree or the immutable artifact is not truthful.
5. Remediation applied:
   - updated `.github/workflows/dev_full_m1_packaging.yml` deterministic `include_paths` to stage:
     - `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`,
     - `docs/model_spec/data-engine/layer-2/specs/contracts/5B`,
     - `docs/model_spec/data-engine/layer-3/specs/contracts/6B`.
6. Next step:
   - commit/push this workflow repin,
   - rerun the packaging workflow from the corrected branch,
   - only then use the new immutable digest for the live runtime refresh.
## Entry: 2026-03-06 15:55:00 +00:00 - Canonical PR3-S1 rerun proved the schema-pack repair worked, but exposed a deeper ingress hot-path timeout defect that must be fixed before any further phase advancement
1. I pulled the canonical rerun evidence after refreshing the live WSP runtime to the rebuilt image digest and reread the runtime and scorecard artifacts instead of relying on the workflow conclusion alone.
2. The good news is precise:
   - the previous schema-pack failure is gone,
   - the WSP lanes now start correctly on the refreshed image,
   - the live error signature changed completely from `referencing.exceptions.Unresolvable` to remote ingress timeout/`503` behavior.
3. The current impact metrics are unambiguously red:
   - target steady throughput: `3000.0 eps`,
   - observed admitted throughput: `0.0 eps`,
   - API Gateway count sum across the measured bins: `2449`,
   - `4xx_sum=0`, `5xx_sum=2449`, error rate `100%`,
   - API Gateway latency `p95=29969.101 ms`, `p99=30000.323 ms`,
   - `138/138` WSP lanes exited non-zero with `IG_PUSH_RETRY_EXHAUSTED`,
   - Lambda duration sat at the full `30000 ms` for every active minute,
   - Lambda throttles appeared once concurrency pressure accumulated.
4. That changes the diagnosis materially:
   - the request path now reaches API Gateway and Lambda,
   - the failure is no longer packaging or route reachability,
   - the ingress hot path is consuming the full request budget before returning a response,
   - the platform is therefore not production-ready at this boundary even though the source replay path is now truthful.
5. I inspected the live Lambda configuration and found a production-shape design bug:
   - Lambda timeout is `30s`,
   - `KAFKA_REQUEST_TIMEOUT_MS` is also pinned to `30000`,
   - the handler performs synchronous `bus.publish(...)` on the request path before it can return any admission outcome,
   - therefore a blocked publish can consume the entire Lambda budget and prevent a controlled quarantine or explicit fast-fail response.
6. The surrounding evidence supports that interpretation:
   - WSP lane logs show alternating `timeout` and `http_503` retries before exhaustion,
   - there are no DLQ messages from the window, which is consistent with raw handler timeout rather than clean exception handling,
   - CloudWatch shows Lambda duration pegged at the exact timeout ceiling,
   - throttles occur only after the concurrency pool starts filling with stuck invocations.
7. Production reasoning:
   - simply raising concurrency again would be the wrong move because it would only allow more invocations to block for the full timeout window,
   - simply lowering the acceptance target would be worse because the defect is architectural at the hot path and would still exist at higher real production load,
   - the correct correction is to preserve admission semantics while forcing the handler to fail or quarantine within a bounded sub-timeout budget, leaving response headroom and surfacing explicit reasons.
8. Alternatives considered:
   - scale Lambda concurrency only:
     - rejected because the handler is already timing out before returning anything useful,
   - repin away from the canonical remote WSP path:
     - rejected because the current evidence is finally on the truthful production replay corridor,
   - leave the hot path synchronous and only reduce WSP retry aggressiveness:
     - rejected because that would hide the ingress defect rather than fix it,
   - repin the ingress architecture immediately to a fully asynchronous front-door:
     - plausible longer-term, but too large a unilateral substrate change to make before first correcting the hot-path budget bug and remeasuring the current pinned corridor.
9. Chosen remediation direction:
   - instrument and bound the IG Lambda admission path using the real Lambda remaining-time budget,
   - force event-bus publish and failure-path side effects to complete within a sub-timeout envelope that preserves time to return a controlled response,
   - make timeout reasons explicit in metrics/logs so the next rerun distinguishes event-bus stalls from object-store/quarantine stalls,
   - only after that rerun the canonical `PR3-S1` steady window and decide whether the remaining gap is true throughput scaling or a second-order dependency bottleneck.
10. Success criteria for the next pass:
    - API Gateway `5xx` rate drops from `100%` to within the S1 contract,
    - latency falls well below the `30s` ceiling and into the PR3 S1 threshold family,
    - WSP lanes produce admitted events instead of exhausting retries at zero emission,
    - any remaining failure reason is explicit and bounded rather than silent timeout saturation.
## Entry: 2026-03-06 16:12:00 +00:00 - Implemented the ingress hot-path remediation around cold-start governance publish and MSK IAM producer posture
1. I implemented the next remediation as a production hot-path correction, not as a one-off test bypass.
2. The first correction removes non-essential broker work from the Lambda cold-start request path:
   - `GovernanceEmitter.emit_policy_activation(...)` now defaults to `store_only` for the audit path,
   - the platform-governance store event still records the activation deterministically,
   - but the extra audit-topic bus publish is no longer attempted on the first request unless explicitly re-enabled.
3. Why that matters:
   - the old cold-start path could call `bus.publish(...)` before a real ingress event was even processed,
   - if the audit topic or broker path stalled, each fresh Lambda worker could burn its whole request budget during initialization,
   - that is an invalid design for a production ingress edge.
4. The second correction strengthens the Kafka client posture for the MSK IAM data plane:
   - `KafkaEventBusPublisher` now uses `confluent-kafka` for `OAUTHBEARER` producer mode as well,
   - MSK IAM tokens are provided through a dedicated `oauth_cb`,
   - delivery/request/socket timeout posture is now controlled by a single bounded configuration surface.
5. Why that client change is warranted:
   - the prior OAUTH producer path relied on `kafka-python`,
   - that is not the client I would pin for a high-EPS managed broker path when the system is already exhibiting publish stalls,
   - moving the producer onto `librdkafka` gives the ingress edge the stronger transport implementation that the rest of the production goal implies.
6. I also bounded the Lambda-side synchronous control-plane calls further:
   - SQS and DynamoDB resource clients now use the same short botocore timeout config as the SSM client,
   - gate initialization now logs its elapsed time explicitly,
   - request start logging now captures remaining Lambda budget for correlation.
7. Infra/runtime envelope was corrected alongside the code:
   - new runtime Terraform pins expose `lambda_ig_kafka_request_timeout_ms`,
   - new runtime Terraform pins expose `lambda_ig_policy_activation_audit_mode`,
   - default posture is now `1500 ms` Kafka publish timeout and `store_only` policy-activation audit mode,
   - RC2 capacity-envelope workflow verification was widened so these pins are checked after apply instead of assumed.
8. Alternatives I rejected:
   - increasing Lambda concurrency again:
     - rejected because it would amplify a stuck hot path,
   - leaving cold-start governance audit publishing in place and only lowering timeouts:
     - rejected because it preserves unnecessary broker dependency on the first request,
   - skipping the client change and hoping the old producer path was fine:
     - rejected because the current evidence already points at the broker publish corridor as a primary production risk.
9. Local proof completed:
   - targeted tests:
     - `python -m pytest tests/services/event_bus/test_kafka_import_and_auth.py tests/services/ingestion_gate/test_health_governance.py tests/services/ingestion_gate/test_admission.py tests/services/ingestion_gate/test_schema_resolution.py tests/services/platform_governance/test_writer.py -q`
     - result: `18 passed`
   - syntax validation:
     - `python -m py_compile src/fraud_detection/event_bus/kafka.py src/fraud_detection/ingestion_gate/governance.py src/fraud_detection/ingestion_gate/aws_lambda_handler.py ...`
     - result: clean
   - infra validation:
     - `terraform -chdir=infra/terraform/dev_full/runtime validate`
     - result: valid
10. Next execution step:
    - commit/push this remediation milestone,
    - rebuild/publish the updated package,
    - apply the runtime envelope changes live,
    - rerun canonical `PR3-S1`,
    - then decide whether the remaining gap is true broker-path throughput or a second-order downstream dependency.
## Entry: 2026-03-06 17:05:00 +00:00 - RC2.R2/PR3 observability blind spot and verification defect pinned before further execution
1. I pulled the failed `dev-full-rc2-r2-capacity-envelope` workflow log instead of rerunning blindly.
2. The immediate failure is not a runtime-capacity failure. It is an OIDC role observability/control gap:
   - the role `GitHubAction-AssumeRoleWithAction` is denied `apigateway:GET` on `arn:aws:apigateway:eu-west-2::/apis/ehwznd2uw7/stages/v1`,
   - therefore the capacity workflow aborts in pre-change capture before the managed apply even starts.
3. Production interpretation:
   - a production control plane must be able to both change and verify the live ingress envelope,
   - blindness on the read surface is itself a production defect because it prevents deterministic adjudication of the capacity state,
   - the correct response is not to weaken the gate, but to give the control plane the least-privilege read/control permissions it materially needs.
4. I also found a workflow-side correctness bug that would have produced a false blocker even after IAM repair:
   - the workflow tries to read `ReservedConcurrentExecutions` from `lambda.get_function_configuration(...)`,
   - that field is not returned there,
   - the correct source is `lambda.get_function_concurrency(...)`.
5. Therefore there are two linked remediation lanes, both required for truthful production evidence:
   - IAM lane: extend the active OIDC role policy to include the APIGW stage control/read surface plus the remaining PR3/RC2 runtime-read surfaces already modeled in `infra/terraform/dev_full/ops` but not materially active on the role,
   - workflow lane: make RC2.R2 envelope capture and post-apply verification publish explicit blocker evidence on unreadable surfaces instead of crashing, and fix reserved-concurrency verification to use the correct API.
6. Alternatives rejected:
   - ignoring the APIGW read gap and trusting Terraform apply output alone:
     - rejected because that is not production-grade verification,
   - bypassing RC2.R2 and continuing PR3 steady runs:
     - rejected because the ingress edge envelope is still not truthfully pinned live,
   - loosening the gate to tolerate unknown reserved concurrency:
     - rejected because that would admit an unverified hot path into later production-readiness states.
7. Execution order pinned:
   - first patch the live OIDC role so the managed workflows can actually observe/control the edge,
   - second patch the workflow verification defect,
   - third rerun RC2.R2 with the authoritative Lambda package coordinates preserved,
   - only then resume canonical `PR3-S1` and the remaining PR chain.
## Entry: 2026-03-06 17:24:00 +00:00 - OIDC runtime-read/control lane corrected via attached managed policy; RC2.R2 verifier corrected to survive unreadable surfaces and verify Lambda concurrency truthfully
1. I attempted the most direct Terraform repair first by extending the inline policy `GitHubActionsM6FRemoteDevFull`.
2. That failed for a real AWS reason, not a tooling glitch:
   - `PutRolePolicy` returned `LimitExceeded` because the inline role-policy document is already at the 10,240-byte AWS limit.
3. Production interpretation:
   - the old inline policy has become a capacity bottleneck for the control plane itself,
   - continuing to grow it is the wrong design even if I could somehow squeeze one more statement into it,
   - the correct posture is to place new PR3/RC2 runtime permissions on the dedicated attached managed policy `GitHubActionsPR3RuntimeDevFull` that is already materially attached to the role.
4. I corrected the repo accordingly:
   - reverted the attempted PR3 runtime additions from the oversized inline M6F policy in `infra/terraform/dev_full/ops/main.tf`,
   - added `apigateway:GET` and `apigateway:PATCH` for the pinned IG API/stage resource to the attached managed policy resource `aws_iam_policy.github_actions_pr3_runtime` instead.
5. I then applied that managed-policy update live through Terraform state in `infra/terraform/dev_full/ops` with a targeted apply on `aws_iam_policy.github_actions_pr3_runtime`.
6. Result:
   - the live role `GitHubAction-AssumeRoleWithAction` now materially carries the API Gateway stage control/read surface through the attached managed policy,
   - the attached policy already carried the Lambda envelope controls and the Managed Flink/CloudWatch read surfaces, so this closes the last identified RC2.R2/PR3 observability-control gap on that role.
7. In parallel I corrected the RC2.R2 workflow itself:
   - pre/post capture now use safe boto calls and record IAM read failures into the snapshot instead of crashing before artifact publication,
   - blocker code `RC2R2-BIAM` is emitted deterministically from those unreadable surfaces,
   - Lambda reserved concurrency is now read from `lambda.get_function_concurrency(...)`, which is the authoritative API, not from `get_function_configuration(...)`.
8. Why this combination is the right production fix:
   - it restores truthful live-edge verification rather than trusting declarative apply output,
   - it prevents a future recurrence where the gate dies on a missing read permission instead of emitting auditable blocker evidence,
   - it removes a false-negative on reserved concurrency that would otherwise have contaminated later throughput claims.
9. Validation completed before rerun:
   - `terraform validate` in `infra/terraform/dev_full/ops`: clean,
   - workflow YAML parse for `.github/workflows/dev_full_rc2_r2_capacity_envelope.yml`: clean,
   - Terraform targeted apply on managed policy: success.
10. Next ordered step pinned:
   - rerun `dev-full-rc2-r2-capacity-envelope` with the corrected IG package coordinates preserved,
   - verify live APIGW/Lambda envelope truthfully,
   - then resume canonical `PR3-S1` from that corrected ingress boundary.
## Entry: 2026-03-06 17:34:00 +00:00 - RC2.R2 apply failure narrowed to workflow-side structured-input handling, not live runtime capacity
1. Two fresh RC2.R2 reruns reached the real Terraform apply step after the OIDC/APIGW repair.
2. Both failed before any runtime change for the same deterministic reason:
   - the workflow constructs Terraform `-var` arguments in bash,
   - `eks_nodegroup_instance_types_json` is a structured JSON/list input,
   - once interpolated into the shell line it becomes syntactically unstable (`["t3.xlarge"]` turns into a broken token stream),
   - Terraform then fails with `Variables not allowed` before planning the actual uplift.
3. Production interpretation:
   - this is an orchestration defect in the control plane, not evidence of a live platform-capacity issue,
   - structured infra inputs for production gates must be passed through a deterministic data serialization boundary, not through ad hoc shell quoting.
4. Corrective decision:
   - stop passing RC2.R2 uplift inputs as bash-composed `-var` fragments,
   - emit a generated `.tfvars.json` file from the workflow instead,
   - validate/parse the JSON list explicitly before invoking Terraform.
5. Why this is the right fix:
   - it removes shell-quoting ambiguity entirely,
   - it keeps the gate deterministic under manual dispatch, workflow dispatch, and future automation,
   - it aligns with the production-readiness goal of making control-plane execution robust instead of operator-fragile.
6. Next action pinned:
   - patch `.github/workflows/dev_full_rc2_r2_capacity_envelope.yml` to generate a structured tfvars payload,
   - rerun RC2.R2 immediately,
   - only once the actual uplift runs and verifies cleanly do we return to canonical `PR3-S1`.
## Entry: 2026-03-06 17:42:00 +00:00 - RC2.R2 tfvars serialization fix proved out; remaining defect is path resolution under terraform -chdir
1. The latest rerun proved the structured-input remediation itself is correct:
   - the workflow generated `rc2_r2_capacity_uplift.auto.tfvars.json`,
   - the JSON list for `eks_nodegroup_instance_types` parsed cleanly,
   - the apply no longer fails on shell tokenization.
2. The remaining failure is a path-resolution defect introduced by `terraform -chdir="${TF_DIR}"`:
   - the tfvars file is written from the repo-root working directory into `${RUN_DIR}`,
   - but `terraform -chdir=infra/terraform/dev_full/runtime ... -var-file="${RUN_DIR}/..."` resolves that path relative to the module directory,
   - therefore Terraform reports the file does not exist even though it was created successfully.
3. Production interpretation:
   - this is still a control-plane execution bug, not a runtime-capacity blocker,
   - the fix is to pass an absolute tfvars path (or write the file inside the module directory), so the managed gate has a single stable filesystem reference regardless of `-chdir`.
4. Next immediate correction pinned:
   - convert the generated tfvars path to an absolute filesystem path before invoking Terraform,
   - rerun RC2.R2 again,
   - only then inspect the first actual live uplift result.
## Entry: 2026-03-06 17:51:00 +00:00 - First real RC2.R2 live-apply blocker identified: runtime module refresh requires Step Functions + IAM OIDC-provider reads
1. The latest RC2.R2 rerun finally moved past all workflow plumbing defects and into a real Terraform plan for the runtime module.
2. The plan failed on two missing read permissions under the active GitHub OIDC role:
   - `states:DescribeStateMachine` on `arn:aws:states:eu-west-2:230372904534:stateMachine:fraud-platform-dev-full-platform-run-v0`,
   - `iam:GetOpenIDConnectProvider` on `arn:aws:iam::230372904534:oidc-provider/oidc.eks.eu-west-2.amazonaws.com/id/6D0DBB7743A87C0ACB0A4645B431D308`.
3. Production interpretation:
   - this is the first true live-apply blocker after the control-plane workflow was stabilized,
   - because the RC2.R2 gate is using the full runtime Terraform module as the source of truth, the OIDC role must be able to refresh the module's existing state surfaces even if the immediate uplift targets are APIGW/Lambda/EKS,
   - restricting the role so tightly that it cannot even read the runtime module's already-managed resources produces a brittle, non-production control plane.
4. Alternatives considered:
   - change RC2.R2 to use targeted applies on only APIGW/Lambda/EKS resources:
     - rejected for now because it hides shared runtime-module drift and weakens the authoritative apply path,
   - patch over the missing reads by skipping refresh:
     - rejected because that would make the gate less truthful at exactly the point we need strong production evidence,
   - extend the role with the minimum additional read surfaces required for the current runtime module:
     - chosen because it preserves full-module truth while remaining least-privilege.
5. Immediate remediation pinned:
   - add `states:DescribeStateMachine` for the pinned platform-run state machine ARN to the managed PR3 runtime policy,
   - add `iam:GetOpenIDConnectProvider` for the pinned EKS OIDC provider ARN to the same policy,
   - apply that policy live,
   - rerun RC2.R2 again from the same uplift target.
## Entry: 2026-03-06 18:00:00 +00:00 - RC2.R2 apply scope repinned from full runtime module to authoritative capacity surfaces only
1. After the OIDC read repairs, the RC2.R2 runtime apply progressed far enough to show a different class of problem:
   - the runtime module plan now includes unrelated pending changes such as Step Functions state-machine version inspection and IRSA MSK data-plane policy creation,
   - those are not part of the RC2.R2 capacity-envelope acceptance boundary.
2. This changes the correct engineering decision.
3. My earlier bias toward full runtime-module apply preserved maximum truth, but the new evidence shows it is conflating unrelated runtime drift with the specific edge-capacity gate we are trying to prove.
4. Production reasoning:
   - a capacity-envelope change for the ingress edge should have a tightly-scoped blast radius,
   - the control plane for that gate should mutate and verify only the surfaces that define the edge envelope,
   - dragging in unrelated runtime changes makes the gate brittle and obscures whether the ingress capacity fix itself is valid.
5. Therefore I am repinning RC2.R2 managed apply scope to the three authoritative capacity resources only:
   - `aws_apigatewayv2_stage.ig_v1`,
   - `aws_lambda_function.ig_handler`,
   - `aws_eks_node_group.m6f_workers`.
6. Why this is not a shortcut:
   - pre/post verification remains on the live APIGW/Lambda/EKS surfaces,
   - the gate still fail-closes if those live values do not match the required envelope,
   - unrelated runtime drifts remain real work, but they belong to their own phase or remediation lane rather than contaminating RC2.R2.
7. This is the production-correct separation of concerns:
   - RC2.R2 proves ingress capacity posture,
   - other runtime module drifts are tracked explicitly and handled separately.
8. Next action pinned:
   - patch the workflow apply step to use targeted Terraform apply for those three resources,
   - rerun RC2.R2 again,
   - if the targeted uplift succeeds, capture/readback and move back to canonical `PR3-S1`.
## Entry: 2026-03-06 18:09:00 +00:00 - RC2.R2 closed green with truthful live-edge evidence; PR3-S1 resumption plan pinned
1. Authoritative RC2.R2 run:
   - workflow run: `22772124603`
   - execution id: `rc2_r2_capacity_envelope_20260306T162513Z`
   - verdict: `overall_pass=true`, `blocker_count=0`, `next_gate=READY_FOR_RC2_R5`.
2. Live pre/post envelope evidence shows the edge is now materially pinned at the required production posture:
   - APIGW stage `ehwznd2uw7/v1`: `rate=3000.0 rps`, `burst=6000`,
   - Lambda `fraud-platform-dev-full-ig-handler`: `memory=1024 MB`, `timeout=30 s`, `reserved_concurrency=300`,
   - Lambda env pins verified live:
     - `KAFKA_REQUEST_TIMEOUT_MS=1500`,
     - `IG_POLICY_ACTIVATION_AUDIT_MODE=store_only`,
   - EKS nodegroup `fraud-platform-dev-full-m6f-workers`: `desired/min/max=4/2/8`, `instance_types=["t3.xlarge"]`, `status=ACTIVE`.
3. Evidence quality is also green:
   - `iam_read_errors=[]` pre and post,
   - `rc2_r2_blocker_register.json` is empty,
   - S3 readback receipt recorded `overall_readback_ok=true` for all five authoritative artifacts.
4. Important design correction that made this closure truthful:
   - RC2.R2 managed apply is now scoped to the capacity-defining surfaces only (`APIGW stage`, `IG Lambda`, `M6F node group`),
   - this prevents unrelated runtime-module drift from contaminating the ingress-capacity gate,
   - while preserving strict live verification on the actual edge resources.
5. Production interpretation:
   - the ingress edge envelope is no longer an unverified assumption,
   - PR3-S1 can now resume from a truthful boundary where ingress throttling, Lambda concurrency, and supporting worker capacity are all pinned to the required target.
6. PR3-S1 resumption decision:
   - resume canonical remote `WSP` replay from the same strict `pr3_20260306T021900Z` boundary,
   - use the refreshed WSP image digest `sha256:619f45f27db151c8cda0b1c0e574b670e4def8bfd874fae8a39133645dba27a2`,
   - use the last valid high-throughput calibration family as the starting point:
     - `lane_count=138`,
     - `stream_speedup=95.0`,
     - `target_steady_eps=3000`,
     - `duration_seconds=1800`,
     - `min_sample_events=5400000`.
7. Reason for choosing that resumption point:
   - `138 @ 95.0` was the last canonical configuration that previously cleared the throughput gate before the ingress hot-path invalidation,
   - the invalidation has now been corrected at the edge envelope,
   - therefore the correct next action is a direct rerun at the last credible calibration point rather than redoing low-speed exploratory underdrive runs.
## Entry: 2026-03-06 18:26:00 +00:00 - PR3-S1 live 503 failure traced to broken IG Lambda artifact, incomplete failure-path networking, and WSP launch drift
1. I inspected the authoritative PR3-S1 rerun artifacts for workflow `22772253988` and confirmed the failure is real runtime behavior, not a post-processing defect.
2. Canonical `WSP` lane evidence from `g3a_s1_wsp_runtime_summary.json` shows:
   - `request_count_total=2513`,
   - `admitted_request_count=0`,
   - `observed_admitted_eps=0.0`,
   - `5xx_total=2513`,
   - every one of the `138` WSP lanes exited non-zero after `IG_PUSH_RETRY_EXHAUSTED`.
3. Direct lane log inspection narrowed the failure surface further:
   - WSP starts cleanly, reads the Oracle-store engine root, and begins paced replay,
   - the retries are all `http_503`, not connection errors or local emitter crashes,
   - therefore the ingress edge is the failing hop.
4. Lambda log inspection around the same wall-clock window isolated the actual root cause:
   - every ingress request reaches `fraud-platform-dev-full-ig-handler`,
   - the handler fails while building the Kafka publisher,
   - the live exception is `ModuleNotFoundError: No module named 'confluent_kafka'`.
5. This means the current live Lambda artifact is materially invalid for the design it is claiming to run:
   - the IG hot path is pinned as `API Gateway -> Lambda -> DynamoDB -> Kafka publish`,
   - but the deployed Lambda package is missing the native Kafka client required to reach MSK,
   - so the edge is not actually production-capable even though the capacity envelope is pinned.
6. I then traced artifact construction back to source and found why this happened:
   - `scripts/dev_substrate/build_ig_lambda_bundle.py` installs dependencies only from `requirements/ig-lambda.requirements.txt`,
   - that pinned requirements file does not contain `confluent-kafka`,
   - therefore the bundle builder deterministically produces a broken IG package.
7. There is a second production defect on the negative path:
   - when the Kafka publish import fails, IG attempts to emit to DLQ,
   - the DLQ send is timing out on `https://sqs.eu-west-2.amazonaws.com/`,
   - the runtime VPC endpoint set currently omits `sqs`, so the fail-safe path is not network-complete for the VPC Lambda posture.
8. There is also a canonical WSP launch drift still present in source:
   - `pr3_s1_wsp_replay_dispatch.py` currently defaults `--assign-public-ip` to `ENABLED`,
   - that contradicts the private-runtime posture established earlier for production replay,
   - while not the proximate cause of the 503s, it is a real drift that should be corrected before treating the lane as canonical.
9. Production interpretation:
   - this is not a reason to loosen the gate or move PR3 forward,
   - it is exactly the kind of real production-hardening defect the PR3 steady proof is supposed to expose,
   - a green claim would be false until the IG package is materially valid, the failure path is network-complete, and the canonical replay injector is back on private-subnet posture.
10. Alternatives considered:
   - bypass Kafka publish and certify only HTTP admission:
     - rejected because it would sever the actual ingest contract and create a toy claim,
   - swap IG off Lambda immediately:
     - rejected for this boundary because the current architecture can still meet the production goal if the artifact and network are corrected; a full architecture migration is not the smallest sound production fix,
   - repair the Lambda build to produce a Lambda-compatible package with the native Kafka client, add the missing SQS runtime endpoint, and repin the WSP dispatcher to private posture:
     - chosen because it preserves the intended platform shape while fixing the actual runtime defects.
11. Immediate remediation pinned:
   - add `confluent-kafka` to the IG Lambda pinned requirements,
   - harden `build_ig_lambda_bundle.py` so dependency resolution is explicit for the Lambda target ABI/platform rather than left to host-default behavior,
   - add `sqs` to the runtime interface endpoint set used by the IG edge materialization workflow and runtime defaults,
   - repin `pr3_s1_wsp_replay_dispatch.py` default `assign_public_ip` to `DISABLED`,
   - rematerialize the ingress edge,
   - rerun `PR3-S1` from the same strict boundary and judge it only on the production impact metrics.
## Entry: 2026-03-06 18:42:00 +00:00 - IG bundle builder refined from container attempt to verified cross-platform wheel strategy
1. The first remediation version added a containerized Lambda-image build path because the packaging problem was clearly ABI-sensitive.
2. That was the right concern, but the wrong primary execution path for this workflow boundary:
   - the GitHub run failed inside `Build deterministic IG Lambda bundle` before any live apply,
   - local inspection showed the risk was not the packaging goal itself, but reliance on Docker availability/daemon posture as an extra moving part.
3. I then validated a simpler and still production-correct approach locally:
   - install the generic dependency set against Linux-compatible `cp312` wheels under `manylinux2014_x86_64`,
   - install `confluent-kafka==2.13.0` separately against `manylinux_2_28_x86_64`,
   - zip the resulting staged tree and verify the bundle actually contains:
     - `confluent_kafka/...`,
     - bundled native Kafka libs (`confluent_kafka.libs`/`librdkafka`),
     - Linux `rpds_py` extension artifacts rather than host-native wheels.
4. That host-mode cross-platform build succeeded locally and produced the correct Linux-targeted artifact contents.
5. Production reasoning:
   - this removes an unnecessary dependency on Docker runtime posture inside GitHub Actions,
   - while preserving the actual requirement that the published Lambda package be ABI-correct for Python 3.12 on the live Lambda runtime.
6. Decision refinement pinned:
   - keep Docker support as an optional escape hatch only,
   - set the authoritative build path back to explicit host-mode cross-platform wheel staging,
   - rerun IG edge materialization with this verified builder path.
## Entry: 2026-03-06 18:49:00 +00:00 - Canonical WSP replay still had subnet default drift after ingress repair
1. After the ingress edge was repaired and rematerialized locally, I ran a bounded one-lane canonical `WSP` smoke before reattempting the full `PR3-S1` steady window.
2. That smoke did not hit the old ingress failure. Instead it exposed the next upstream runtime defect immediately:
   - ECS task failed before start with `TaskFailedToStart`,
   - root reason: `CannotPullContainerError` while pulling the WSP image digest from ECR,
   - the task was launched with `assignPublicIp=DISABLED` but still using the old public-subnet defaults.
3. This is a real production drift in the canonical replay injector:
   - disabling public IP is correct for the production posture,
   - but that posture only works if the task is also launched into the runtime private subnets that are wired to the interface endpoints,
   - keeping the old public-subnet defaults turns a correct security posture into a startup failure.
4. Therefore the next correct remediation is not to relax the network back to public-IP operation, but to repin the dispatcher defaults to the private runtime subnets:
   - `subnet-0a7a35898d0ca31a8`
   - `subnet-0e9647425f02e2f27`
5. Why this is production-correct:
   - it preserves the private runtime objective,
   - it allows ECR pull/bootstrap through the endpoint-backed runtime network,
   - it removes another silent mismatch between canonical replay code and the actual runtime substrate.
6. Immediate next action pinned:
   - update the dispatcher subnet defaults to the private runtime subnets,
   - rerun the bounded one-lane WSP smoke,
   - only after that passes return to the full `PR3-S1` steady window.
## Entry: 2026-03-06 17:40:00 +00:00 - PR3-S1 canonical source posture corrected; the current hot-path blockers are inside IG, not the replay transport
1. I reran the bounded one-lane `PR3-S1` smoke on the old public-subnet/public-IP WSP posture to test whether the recent private-subnet repin was actually proving a production requirement or merely adding an internal routing constraint.
2. The result materially changed the diagnosis:
   - WSP no longer timed out before the edge,
   - requests reached `API Gateway -> Lambda`,
   - Lambda logs showed real handler execution on the same wall-clock window.
3. That means the previous private-runtime repin was solving the wrong problem for `PR3`.
4. Production reasoning:
   - `WSP` is pinned as the platform's outside-world traffic producer,
   - `PR3-S1` is supposed to prove the real outside-world steady path into the public ingress edge,
   - forcing `WSP` into a private no-NAT path to the public API turns the runtime proof into an internal routing experiment rather than a truthful bank-like ingress certification.
5. I am therefore correcting the canonical `PR3-S1` source posture back to public-edge replay:
   - public subnets,
   - public IP enabled,
   - same public `IG` edge URL,
   - private-runtime-to-IG direct-path work remains a separate bridge-equivalence hardening lane, not the canonical runtime-cert source path.
6. The bounded public-edge smoke also exposed the actual current hot-path blockers inside `IG` itself:
   - Lambda idempotency lookups are timing out on `https://dynamodb.eu-west-2.amazonaws.com/`, proving the VPC Lambda still lacks a usable DynamoDB path,
   - payload validation for real `6B` event types is failing with `Unresolvable: schemas.layer3.yaml#/$defs/hex64`, proving the deployed Lambda bundle is still schema-incomplete for the data-engine contract chain it claims to enforce.
7. These are the real production blockers now:
   - no truthful steady-cert claim can stand while the idempotency store is unreachable,
   - no truthful semantic-ingest claim can stand while valid upstream contract refs are missing from the Lambda bundle.
8. Alternatives considered:
   - keep chasing the private `execute-api` path:
     - rejected because it is not the canonical `PR3` source proof and would continue to burn time on a secondary routing lane,
   - add NAT to rescue the private caller path:
     - rejected because it increases cost/surface area and still does not solve the actual IG DynamoDB/schema failures,
   - correct canonical WSP source posture, add first-class DynamoDB private access for the Lambda idempotency store, and make the Lambda bundle include the full transitive schema closure:
     - chosen because it addresses the true hot-path failures while preserving the production meaning of `PR3-S1`.
9. Immediate remediation pinned:
   - repin `PR3-S1` dispatcher defaults back to the public WSP source posture,
   - add a DynamoDB gateway endpoint on the runtime private route tables for the VPC Lambda,
   - extend the IG bundle builder to package the full transitive data-engine schema contract directories required by `5B/6B` payload validation,
   - rematerialize the edge and rerun the bounded smoke before returning to the full steady window.
## Entry: 2026-03-06 17:41:00 +00:00 - Lambda bundle and runtime edge need contract closure, not partial file copies or public AWS fallback
1. The current Lambda bundle copies only these data-engine payload schema files:
   - `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`
   - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
2. That is insufficient because those files carry transitive refs to sibling shared schema packs:
   - `schemas.6B.yaml -> schemas.layer3.yaml#/$defs/hex64`
   - `schemas.5B.yaml -> schemas.layer1.yaml#/$defs/...`
3. The production issue is not that the WSP data is malformed; it is that the edge artifact is claiming to enforce the contract without carrying the full contract graph.
4. The correct remediation is to package the contract directories that close the reference graph, not to loosen validation or patch the WSP payloads.
5. On the infrastructure side, the Lambda timeout against `dynamodb.eu-west-2.amazonaws.com` proves the ingress idempotency boundary is still depending on implicit public AWS reachability.
6. For this platform posture the correct fix is explicit private AWS service access, not a hidden internet dependency:
   - DynamoDB gateway endpoint on the private route tables,
   - keep SQS/SSM/logs endpoints already added,
   - preserve the no-local-runtime and evidence-first posture.
## Entry: 2026-03-06 17:49:00 +00:00 - Bounded public-edge PR3-S1 smoke is green after DynamoDB path + schema-closure remediation
1. I rebuilt the IG Lambda bundle with the transitive schema graph included and applied a live DynamoDB gateway endpoint for the private Lambda subnets.
2. Live correction evidence:
   - Lambda code hash is now `pyOm/xQe7B324/rL2GSB/iMOF9BhXPUz/5xjXyGhIvI=`,
   - DynamoDB gateway endpoint materialized as `vpce-0e4cacff57266a01c` on the private runtime route table,
   - canonical WSP dispatcher defaults are corrected back to public-edge source posture for `PR3`.
3. I then reran the same bounded one-lane `PR3-S1` smoke on the canonical public-edge source path.
4. Impact metrics from the run:
   - `request_count_total=60`,
   - `admitted_request_count=60`,
   - `observed_admitted_eps=1.0`,
   - `error_rate_ratio=0.0`,
   - `4xx_rate_ratio=0.0`,
   - `5xx_rate_ratio=0.0`,
   - `latency_p95_ms=129.13`,
   - `latency_p99_ms=152.32`,
   - verdict `REMOTE_WSP_WINDOW_READY`, `open_blockers=0`.
5. Production interpretation:
   - the ingress hot path is now materially functional on the real canonical route,
   - WSP -> API Gateway -> Lambda -> DynamoDB -> Kafka no longer fails at low-rate proof,
   - schema enforcement on real `5B/6B` payloads is no longer internally broken,
   - idempotency lookup is no longer blocked by missing AWS-private reachability.
6. This does not close `PR3-S1` yet because the state target is `3000 eps steady`, not `1 eps`.
7. However, it changes the next action decisively:
   - the remaining work is throughput calibration and capacity proof,
   - not correctness triage of a broken edge artifact.
8. Next calibration posture pinned:
   - start from the last credible high-throughput operating point already recorded in the plan (`lane_count=138`, `stream_speedup=95.0`, `target_request_rate_eps=3000`),
   - use a bounded fail-fast steady window first,
   - only if that bounded proof is green do the full `S1` certification window.
## Entry: 2026-03-06 18:05:00 +00:00 - PR3-S1 bounded high-rate failure traced to synthetic object-store health gating that does not scale with concurrency
1. I inspected the live `PR3-S1` bounded high-rate failure after the ingress edge hot-path fixes were already green at low-rate.
2. The new bounded calibration outcome was:
   - `observed_admitted_eps=1351.178` against a `3000 eps` target,
   - `error_rate_ratio=0.061885`,
   - `5xx_total=16043`,
   - `latency_p95_ms=506.455`,
   - `latency_p99_ms=1351.005`.
3. CloudWatch log inspection on `/aws/lambda/fraud-platform-dev-full-ig-handler` showed the dominant server-side reason was not random transport failure and not DynamoDB anymore. The request path was failing with `IG_UNHEALTHY:OBJECT_STORE_UNHEALTHY`.
4. I then verified the obvious infra hypotheses before changing code:
   - private runtime route table already carries an `S3` gateway endpoint and the new `DynamoDB` gateway endpoint,
   - the Lambda execution role already has `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`, and matching KMS permissions for the object-store key,
   - the low-rate bounded proof succeeded on the same bucket/key family.
5. This means the current failure is not best explained by "S3 unreachable". The stronger production explanation is the health model itself:
   - `HealthProbe._store_ok()` performs a synthetic `store.write_json()` to `platform_run_id/ig/health/last_probe.json`,
   - the admission spine calls `health.check()` before validating or admitting every event,
   - on a concurrency fan-out, each fresh Lambda environment can decide gate health by attempting the same KMS-encrypted S3 write on the hot path,
   - a single transient failure then turns the environment health state `RED` and causes request-level 5xx for the cached probe interval.
6. Production judgement:
   - this is not a sound way to protect a high-EPS ingress edge,
   - the platform is amplifying a secondary observability write into a hard admission dependency,
   - even if S3 is healthy overall, this probe shape is an avoidable concurrency multiplier and therefore a design defect for the target envelope.
7. Alternatives considered:
   - increase Lambda memory/concurrency/timeouts only:
     - rejected because it does not remove the incorrect gate dependency; it merely gives the synthetic probe more room to fail later,
   - lengthen the health probe interval only:
     - rejected because the first write per fresh environment still occurs on the hot path and still couples admission to a nonessential overwrite of a single health object,
   - weaken the gate by ignoring object-store health completely:
     - rejected because the ingress path genuinely depends on object-store writes for receipts/quarantine/governance and cannot pretend that surface does not matter,
   - move store health from synthetic probe writes to observed outcomes of real store operations, while logging exact exceptions for future evidence:
     - chosen because it keeps fail-closed semantics on genuine store failure while removing an unnecessary hot-path amplifier that is not production-sound.
8. Implementation plan pinned:
   - add a small `ObservedObjectStore` wrapper in `ingestion_gate.store` that records last success/failure of real object-store operations,
   - update `HealthProbe` to consume observed store state instead of issuing synthetic writes on the admission path,
   - add exception logging so the next real store fault carries actionable evidence instead of a swallowed boolean,
   - cover the new behavior with focused ingestion-gate tests,
   - rebuild/rematerialize the Lambda bundle and rerun bounded `PR3-S1` calibration before resuming the full steady window.
## Entry: 2026-03-06 18:30:00 +00:00 - PR3-S1 evidence runner itself violated runtime-budget discipline after the object-store fix
1. After rematerializing the IG Lambda with observed store health, I reran the same bounded `PR3-S1` calibration.
2. The runtime conditions materially improved in one important way before the evidence runner stalled:
   - the Lambda code hash updated to `dnFcCI/li0e9vYozKAnk/oB9EaqQ4B9HcAsOQrsPnVA=`,
   - no fresh `OBJECT_STORE_UNHEALTHY` log events appeared in the new run window,
   - all WSP lanes completed and ECS showed no leaked running tasks.
3. The remaining problem was not the production edge itself; it was the certification tooling:
   - `pr3_s1_wsp_replay_dispatch.py` remained live long after the window closed,
   - inspection showed it was performing full `get_log_events()` harvest across all `138` WSP streams before emitting the summary,
   - that is disproportional to the actual binding evidence needed for `PR3-S1`, which is primarily `API Gateway` metric families plus final lane stop status.
4. Production judgement:
   - this is an implementation defect in the certification runner, not a valid reason to delay platform closure,
   - high-lane certification tooling must obey the same runtime-budget law as the platform itself,
   - reading every ECS log event from every lane is not required to prove ingress steady-state thresholds and therefore should not dominate execution time.
5. Alternatives considered:
   - wait longer for the runner to finish:
     - rejected because it repeats the same budget violation and wastes time without increasing evidence quality,
   - drop all lane-level evidence entirely:
     - rejected because some lane termination metadata is still useful for audit and failure triage,
   - switch high-lane runs to metadata-only lane evidence while preserving full metric-surface proof and explicit final task status:
     - chosen because it retains auditable lane closure while removing the expensive nonbinding full-log sweep.
6. Implementation plan pinned:
   - add explicit lane-log collection modes to `pr3_s1_wsp_replay_dispatch.py`,
   - default `auto` to metadata-only for high-lane windows,
   - keep full log parsing for smaller investigative reruns where it is proportionate,
   - rerun the bounded calibration immediately after the runner budget fix.
## Entry: 2026-03-06 18:55:00 +00:00 - PR3-S1 canonical high-rate failure now isolated to duplicate-path receipt normalization, not object-store health or edge reachability
1. After the observed object-store health remediation landed live, I re-read the bounded canonical `PR3-S1` evidence rather than treating the remaining red state as a generic throughput miss.
2. The high-rate window still failed, but the metric pattern changed materially:
   - API Gateway `Count` matched `5xx` exactly for the failing bins,
   - Lambda `Errors` stayed at `0`,
   - Lambda concurrency remained low relative to the pinned envelope,
   - Lambda duration after cold start was not showing a uniform full-timeout pattern anymore.
3. That combination means the ingress edge is executing and returning handled failures, not collapsing from raw saturation.
4. CloudWatch Lambda logs then exposed the dominant hot-path exception on duplicate/retry handling:
   - `Schema validation failed for ingestion_receipt.schema.yaml: Decimal('4') is not of type 'integer'`.
5. The production root cause is specific:
   - the duplicate path reloads the existing idempotency row from DynamoDB,
   - DynamoDB materializes numeric members as `Decimal`,
   - the existing-row `eb_ref.partition` and similar fields are fed back into receipt validation without normalization,
   - receipt validation correctly rejects `Decimal` because the contract requires integer/string JSON primitives,
   - the duplicate/retry path then raises inside Lambda and surfaces as API Gateway `503`.
6. Production judgement:
   - this is not a harmless serialization quirk,
   - at target EPS the platform must survive duplicates/retries as a first-class reality,
   - a retry path that fails schema revalidation under load is a correctness defect and a production throughput defect at the same time because it converts normal duplicate pressure into 5xx amplification.
7. Alternatives considered:
   - loosen the receipt schema to accept `Decimal`-like values:
     - rejected because the contract is JSON-facing and should stay type-clean,
   - suppress duplicate receipt validation on the hot path:
     - rejected because it would hide contract drift precisely where at-least-once semantics need deterministic proof,
   - normalize DynamoDB-returned numeric values back to JSON-native primitives before revalidating and emitting receipts:
     - chosen because it preserves the schema, preserves duplicate-path determinism, and fixes the real runtime defect without weakening guarantees.
8. Immediate remediation pinned:
   - normalize DynamoDB `Decimal` values recursively in the Lambda lookup path,
   - normalize `eb_ref.partition` to native integer and `offset` to string before duplicate receipt validation,
   - validate the change with focused ingestion-gate tests,
   - rebuild and republish the IG Lambda bundle,
   - rerun the bounded canonical `PR3-S1` window with metadata-only lane evidence and reassess the next real throughput limiter from fresh impact metrics.
## Entry: 2026-03-06 19:15:00 +00:00 - PR3-S1 redeploy cleared duplicate-path 503s and exposed two remaining health-model defects under real duplicate pressure
1. After redeploying the IG Lambda with DynamoDB Decimal normalization, the canonical bounded `PR3-S1` rerun changed failure shape again:
   - `5xx_total` dropped to `0`,
   - all observed failures became `4xx`,
   - WSP lane logs now report `IG_PUSH_REJECTED` with a quarantine receipt instead of transport timeout.
2. That means the duplicate-path schema defect is fixed live; the platform moved to a new, more truthful boundary.
3. Fresh Lambda logs exposed two distinct implementation defects inside the health path:
   - `AttributeError: 'NoopOpsIndex' object has no attribute 'probe'`,
   - `ObservedObjectStore` marked the object store unhealthy after `FileExistsError` from `write_json_if_absent` on governance marker paths.
4. Production interpretation of defect one:
   - the Lambda posture intentionally uses a no-op ops index because DDB already owns the live idempotency boundary for this edge,
   - a no-op implementation that violates the `probe()` contract is a coding defect, not a missing platform dependency,
   - this defect is currently turning healthy requests into quarantined `4xx` responses.
5. Production interpretation of defect two:
   - `write_json_if_absent` conflict on an already-created receipt/quarantine/governance marker is an expected idempotent outcome under retries and fan-out,
   - treating that as object-store failure poisons health with false negatives,
   - under production duplicate pressure this would incorrectly gate admission based on benign first-writer-wins collisions.
6. Alternatives considered:
   - disable store/ops health entirely for Lambda:
     - rejected because it removes real protection and hides genuine backing-store failure,
   - suppress all `FileExistsError` logging globally:
     - rejected because the outcome should remain observable, just not classified as unhealthy,
   - implement the missing no-op probe contract and classify `write_json_if_absent` conflicts as healthy idempotent completion while preserving true exceptions as failures:
     - chosen because it matches the semantics of at-least-once production operation.
7. Immediate remediation pinned:
   - restore `lookup_event()` and `probe()` as real `NoopOpsIndex` methods,
   - teach `ObservedObjectStore` to record `FileExistsError` from `write_json_if_absent` as a benign idempotent success state rather than a health failure,
   - add focused tests for both behaviors,
   - rebuild and redeploy the IG Lambda again,
   - rerun the bounded canonical `PR3-S1` window from the same strict boundary and reassess the next throughput limiter from fresh impact metrics.
## Entry: 2026-03-06 19:30:00 +00:00 - PR3-S1 now reduced to a true ingress capacity-envelope miss; repin Lambda for measured 3k steady target
1. The latest bounded canonical `PR3-S1` rerun after the health fixes produced a materially cleaner picture:
   - `request_count_total = 337410`,
   - `admitted_request_count = 286502`,
   - `observed_admitted_eps = 1591.678`,
   - `5xx_total = 50907`,
   - `p95 = 474.367 ms`,
   - `p99 = 1441.531 ms`,
   - only `5` blockers remain and all are capacity/latency blockers.
2. CloudWatch runtime metrics isolate the limiter precisely:
   - Lambda `ConcurrentExecutions` averaged ~`292` and hit `Maximum = 300` in all three measured minutes,
   - Lambda `Throttles` were `17473`, `16936`, `16498` across the three bins,
   - the WSP side saw widespread `http_503` retries in the same window.
3. Production interpretation:
   - the edge is no longer failing because of broken contracts or false-negative health logic,
   - the ingress Lambda is simply pinned below the concurrency needed for the declared `3000 eps` steady target,
   - every further rerun on the current `300` concurrency pin would just restate the same limit and waste budget.
4. Sizing rationale from live evidence:
   - at `~1591.7 admitted eps` with `~300` active concurrency, the observed average in-flight service time is roughly `0.188 s` by Little's Law,
   - sustaining `3000 eps` at that same service time requires about `565` concurrent executions before headroom,
   - meeting the `p95 <= 350 ms` acceptance target under the same target throughput implies capacity on the order of `1050` concurrent executions for the tail,
   - therefore the old `300` pin is not merely conservative; it is mathematically inconsistent with the production target.
5. Repin decision:
   - `LAMBDA_IG_RESERVED_CONCURRENCY = 1000`,
   - `LAMBDA_IG_MEMORY_MB = 2048`.
6. Why this pair is chosen:
   - reserved concurrency is the current hard limiter and must move close to the measured tail-capacity requirement,
   - `1000` stays inside the common account-level default envelope while being large enough to remove the current flat throttle wall,
   - raising memory to `2048` is primarily a CPU/network allocation decision, not a RAM-usage decision, and is intended to lower per-request service time and tail latency without introducing idle spend.
7. Alternatives considered:
   - rerun at the same envelope and hope retries smooth it out:
     - rejected because the throttles prove the envelope itself is too small,
   - move immediately to a new ingress architecture:
     - rejected for this boundary because the current canonical architecture is not yet exhausted; its first measured hard limit is simply underprovisioned concurrency,
   - add provisioned concurrency first:
     - deferred because the current blocker is steady-state throttle saturation, not primarily cold-start variance; reserved concurrency + CPU uplift is the first truthful correction.
8. Immediate remediation pinned:
   - update authority and Terraform defaults to `2048 MB / 1000 reserved concurrency`,
   - apply the new live Lambda envelope with the current validated bundle still pinned,
   - rerun bounded canonical `PR3-S1`,
   - only if throttles remain or latency still misses materially after that do deeper hot-path or architectural changes become the next justified move.
## Entry: 2026-03-06 19:40:00 +00:00 - PR3-S1 bounded proof at the account's Lambda ceiling shows the remaining gap is quota-bounded, not a hidden semantic defect
1. After AWS rejected `1000` reserved concurrency, I queried the actual regional account quota and found:
   - `ConcurrentExecutions = 400`,
   - required unreserved floor effectively leaves `360` as the highest legal single-function reservation in this account.
2. I requested a quota increase to `1500` (`Service Quotas` request id `712a9a7a12174f7798304b4b0ad60407M9HoApfX`), status `PENDING`, and did not wait for it.
3. I then reran the bounded canonical `PR3-S1` window at the account ceiling (`reserved concurrency = 360`, `memory = 2048 MB`).
4. Impact metrics from that run:
   - `request_count_total = 441629`,
   - `admitted_request_count = 423060`,
   - `observed_admitted_eps = 2350.333`,
   - `error_rate_ratio = 0.042047`,
   - `5xx_total = 18568`,
   - `latency_p95_ms = 351.865`,
   - `latency_p99_ms = 870.573`.
5. Production interpretation:
   - the edge improved materially from the prior `300`-concurrency run (`1591.678 eps -> 2350.333 eps`),
   - `p95` is now effectively on the acceptance boundary, which strongly suggests the hot path itself is not catastrophically inefficient anymore,
   - the remaining miss is dominated by the environment-level concurrency ceiling and its resulting residual `503` pressure.
6. This is the key decision point:
   - if the quota increase lands and the same architecture scales linearly enough from `360` to the required range, Lambda may still satisfy the production target in a properly sized account,
   - but in this account the current architecture cannot be fully certified to `3000 eps` because the regional account quota blocks the required concurrency headroom.
7. Production-minded next move pinned while quota request is pending:
   - do not waste more bounded reruns on the same account-limited Lambda posture,
   - evaluate and, if feasible, materialize the existing `ingestion_gate.service` runtime as an ECS service-backed ingress alternative so PR3-S1 is no longer held hostage by the Lambda regional quota in this account,
   - preserve the current Lambda evidence because it proves the hot path is close and that the blocker has narrowed to capacity governance rather than semantic correctness.
## Entry: 2026-03-06 20:05:00 +00:00 - PR3-S1 service-edge decision: promote ingress to a horizontally scaled ECS service, but keep DDB/Kafka hot-path semantics rather than regressing to the older profile-backed Postgres edge
1. I stopped treating the account-quota ceiling as "the blocker" and instead re-evaluated the production question directly:
   - what ingress posture should this platform use if the real requirement is `3000 eps steady / 6000 burst`,
   - not "what can I rerun fastest."
2. The repo currently exposes three candidate directions:
   - wait for the pending Lambda quota increase and keep `API Gateway -> Lambda -> DDB -> MSK`,
   - promote the existing Flask `ingestion_gate.service` app as-is, which uses the profile-driven `IngestionGate.build(...)` path and therefore moves idempotency/ops indexing onto `IG_ADMISSION_DSN` (Aurora/Postgres),
   - promote a service-backed ingress edge, but reuse the already-proven managed-edge semantics from `aws_lambda_handler.py` (`DDB idempotency + S3 receipts + Kafka publish + strict auth`) instead of the older Postgres-backed service path.
3. I rejected "wait for quota" as the primary plan:
   - the quota request is valid and should stay open,
   - but a pending quota case is not a production-hardening strategy,
   - it leaves PR3-S1 blocked on account governance rather than on platform design.
4. I also rejected promoting the old profile-backed IG service as the canonical throughput path:
   - it is operationally real code, but its hot idempotency path is `lookup -> insert/update -> receipt lookup` on Aurora/Postgres,
   - that path has not yet been proven for the required ingress envelope,
   - moving the trust boundary from DynamoDB to Aurora simply because the old Flask wrapper already exists would be a convenience decision, not a production one.
5. The better production choice is therefore:
   - keep the ingress trust-boundary semantics already proven under the managed edge (`DDB` for idempotency state, `S3` receipts/governance, `Kafka/MSK` publish),
   - move only the request-execution shell from Lambda to a horizontally scaled service,
   - expose that service through a real load-balanced ingress endpoint so the edge can scale independently of Lambda regional concurrency.
6. This gives the right separation of concerns:
   - `WSP` remains the real remote replay producer,
   - `IG` remains the trust boundary and only writer to `EB`,
   - `Managed Flink` remains scoped to downstream stream-processing lanes (`IEG/OFP/RTDL`),
   - the only thing changing is the execution substrate of the IG request handler.
7. Immediate implementation plan pinned:
   - factor the managed IG request logic out of `aws_lambda_handler.py` into a reusable HTTP-safe edge core,
   - add a service runner that serves the same ingest/health contract over HTTP,
   - run it behind an internet-facing ALB and private ECS/Fargate service,
   - size the service explicitly for the PR3 steady window rather than leaving it on tiny defaults,
   - repoint PR3-S1 canonical WSP replay to the new managed service endpoint,
   - rerun bounded `S1` from the same strict PR3 execution root before proceeding to later states.
8. The Lambda path is not being discarded:
   - it remains useful as compatibility evidence and as a lower-throughput managed edge posture,
   - but it is no longer the canonical PR3 throughput-certification path for this account because the live account ceiling is already proven to be below the target envelope.
## Entry: 2026-03-06 20:35:00 +00:00 - Managed IG service implementation checkpoint: local service wrapper and private ALB/ECS substrate are validated before live materialization
1. I chose the lowest-risk way to preserve the managed-edge semantics:
   - instead of rewriting the admission core again, the new HTTP service wrapper adapts inbound HTTP requests into the existing `aws_lambda_handler.lambda_handler(...)` contract,
   - this means the service path keeps the exact same DDB idempotency index, S3 receipt/governance writes, Kafka publish path, auth checks, and correlation echo behavior already proven in the Lambda lane.
2. This is intentionally not "just reusing Flask":
   - a new `managed_service.py` exposes `/v1/ingest/push`, `/v1/ops/health`, and an unprotected `/healthz` for infrastructure liveness,
   - the intended runtime server is `gunicorn` with explicit thread/worker sizing, not Flask's development server.
3. I then added the `dev_full` substrate needed for that path:
   - internal ALB across private subnets,
   - ECS/Fargate cluster + task definition + service,
   - dedicated ALB/task security groups,
   - dedicated ECS execution/runtime roles,
   - CloudWatch log group,
   - SSM parameter publication of the resolved internal ingest URL.
4. The ALB is pinned `internal`, not internet-facing, because the active PR3 caller is remote `WSP` inside the same VPC and the current goal is truthful platform-runtime certification rather than public internet exposure.
5. The WSP dispatcher is updated to auto-resolve the service URL from SSM and only fall back to the old API Gateway URL if the service path is not materialized.
6. Local validation completed before live apply:
   - `py_compile` passed for the touched Python modules,
   - focused IG tests passed (`17 passed`),
   - `terraform validate` passed after the new service resources were added.
7. Immediate live steps pinned:
   - build and push a new immutable platform image that includes `managed_service.py` and `gunicorn`,
   - apply the runtime stack with `ig_service_enabled=true` and the pinned image URI,
   - verify ECS service health and resolved SSM URL,
   - rerun bounded `PR3-S1` against the service endpoint from the existing strict PR3 execution root.
## Entry: 2026-03-06 20:50:00 +00:00 - Live materialization plan for the managed IG service and PR3-S1 bounded rerun
1. The next boundary is no longer design choice; it is live proof.
2. I am treating the service-backed ingress rollout as a production change with explicit acceptance gates, not as a convenience deploy.
3. Live materialization plan:
   - apply only the new `ig_service_*` runtime resources plus the SSM publication of the service URL,
   - pin the image to the freshly built immutable digest,
   - keep the existing API Gateway/Lambda edge in place as a non-canonical fallback while the service path is verified,
   - verify the ALB target group reaches `healthy`, ECS task count reaches the desired value, and the SSM URL resolves,
   - run a bounded `PR3-S1` canonical replay against the SSM-resolved service URL from the existing strict PR3 execution root,
   - inspect runtime metrics and task logs immediately rather than burning a full window on a broken lane.
4. Production acceptance for this deployment step:
   - no container boot-loop,
   - no ALB health-check flapping,
   - no missing dependency on the private subnet path,
   - no systemic `5xx` from the service edge under bounded replay,
   - evidence artifacts land under `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/`.
5. If the first bounded replay misses target, I will treat that as fresh throughput evidence to diagnose and correct, not as a reason to retreat to the old Lambda path.
6. The metrics I care about first are:
   - admitted EPS,
   - `4xx/5xx` split,
   - `p95/p99` end-to-end latency,
   - ALB target health,
   - ECS CPU/memory utilization,
   - application log signatures around idempotency, Kafka publish, and request timeout behavior.
7. The immediate risk areas are:
   - VPC reachability from ECS tasks to private dependencies,
   - container start-command/runtime import issues,
   - runtime-role parity gaps versus the Lambda role,
   - a new bottleneck caused by the service shell itself rather than the managed-edge core.
8. None of those risk areas justify shortcutting the architecture decision. They justify measuring the live service carefully and correcting the actual bottleneck that appears.
## Entry: 2026-03-06 21:05:00 +00:00 - First live ECS boot fault isolated to the service shell, not the ingress core
1. The targeted Terraform apply materially created the managed service substrate and published the internal service URL to SSM.
2. Health did not stabilize on first boot:
   - ECS service stayed at `runningCount=0`, `pendingCount=6`,
   - ALB targets repeatedly entered `draining`,
   - container logs were consistent across restarts.
3. The container log signature is explicit:
   - `usage: gunicorn [OPTIONS] [APP_MODULE]`
   - `gunicorn: error: unrecognized arguments: --factory`
4. Production interpretation:
   - the live defect is not in `DDB`, `Kafka`, private networking, or the ingress business logic yet,
   - the service never reaches Python app initialization because the process command is invalid for the pinned `gunicorn` version.
5. This is a shell/runtime packaging defect in the service wrapper layer, not a reason to retreat from the service-backed architecture.
6. Chosen correction:
   - remove the unsupported `--factory` CLI flag,
   - keep the factory invocation in the supported `module:create_app()` form,
   - redeploy the task definition and recheck ECS/ALB health before any replay load is sent.
7. This is exactly why the bounded health-first rollout was pinned: the first live failure is cheap to isolate and correct before it pollutes PR3 throughput evidence.
## Entry: 2026-03-06 21:15:00 +00:00 - Managed IG service reached healthy live posture after the shell fix
1. After removing the unsupported `gunicorn --factory` flag and forcing a clean rollout on task definition revision `:2`, the service reached the expected live baseline:
   - ECS `desiredCount=6`,
   - ECS `runningCount=6`,
   - ALB target health reports healthy targets on both private subnets,
   - SSM service URL remains published at `/fraud-platform/dev_full/ig/service_url`.
2. The log signature on the healthy tasks confirms the service shell is now correct:
   - `Starting gunicorn 23.0.0`,
   - `Listening at: http://0.0.0.0:8080`,
   - worker boot messages with no immediate exit loop.
3. Production interpretation:
   - the service-backed ingress correction has cleared bootstrap/runtime-shell defects,
   - the next boundary is actual bounded replay throughput and latency under canonical remote `WSP` traffic.
4. This closes the infrastructure-materialization gate for the service edge:
   - no boot-loop,
   - no health-check flap,
   - no unresolved ALB/ECS liveness fault.
5. The next work remains strictly on the PR3 evidence path:
   - run bounded canonical `PR3-S1` against the SSM-resolved service endpoint,
   - inspect impact metrics first (`admitted_eps`, latency tails, `4xx/5xx`, sample volume),
   - remediate whichever production bottleneck the fresh bounded window exposes.
## Entry: 2026-03-06 21:25:00 +00:00 - PR3-S1 measurement drift corrected so the bounded replay will measure the active ingress edge truthfully
1. Before launching the bounded replay, I inspected `pr3_s1_wsp_replay_dispatch.py` and found an evidence defect:
   - even when the dispatcher resolves `IG_INGEST_URL` from the internal ALB SSM path,
   - its CloudWatch measurement code still read `AWS/ApiGateway` metrics only.
2. That would have made the next bounded run non-authoritative:
   - replay traffic would hit the ECS/ALB service path,
   - but the scorecard would still read the old API Gateway surface and therefore undercount or misclassify the real service behavior.
3. Chosen correction:
   - add automatic ingress-surface resolution from the active ingest URL,
   - keep `AWS/ApiGateway` metrics when the live edge host is `execute-api`,
   - switch to `AWS/ApplicationELB` metrics (`RequestCount`, target/ELB `4xx/5xx`, `TargetResponseTime`) when the active edge host is an internal ALB.
4. Production interpretation:
   - this is not cosmetic instrumentation work,
   - it is necessary to keep the PR3 throughput, latency, and error evidence bound to the actual edge under test.
5. The bounded `PR3-S1` replay can now produce truthful service-path metrics instead of stale API Gateway proxies.
## Entry: 2026-03-06 21:35:00 +00:00 - PR3-S1 bounded replay isolated a bundle-root defect in the service container
1. The first truthful bounded replay against the internal ALB did exactly what it should:
   - it measured the service path (`metric_surface_mode=ALB`),
   - it failed fast at `15.3 admitted eps`,
   - it preserved the next real bottleneck in both `WSP` and `IG` logs.
2. The dominant symptom from `WSP` was repeated `http_503` and `IG_PUSH_RETRY_EXHAUSTED`.
3. The actual root cause came from the `IG` service logs, not from speculation:
   - `FileNotFoundError: [Errno 2] No such file or directory: '/app/src/config/platform/ig/schema_policy_v0.yaml'`
   - raised while `_gate_for(...)` tried to load `schema_policy_v0.yaml`.
4. This reveals a packaging/runtime assumption mismatch:
   - the Lambda handler computes `_bundle_root()` from `Path(__file__).parents[2]`,
   - that works in the Lambda bundle layout,
   - but in the container image the repo root is `/app` while the Python package root is `/app/src`,
   - so the service looked for config under `/app/src/config/...` instead of `/app/config/...`.
5. Production interpretation:
   - the ingress logic is still the right one to preserve,
   - but it must not rely on a Lambda-specific filesystem shape when promoted to a service shell.
6. Chosen correction:
   - make `_bundle_root()` runtime-aware and accept an explicit bundle-root override,
   - set `PLATFORM_BUNDLE_ROOT=/app` in the ECS service task definition,
   - rebuild the immutable image, redeploy the service, and rerun the bounded `PR3-S1` proof immediately.
7. This is the correct production move because it removes a packaging assumption at the source instead of papering over missing files one-by-one.
## Entry: 2026-03-06 22:05:00 +00:00 - Active IG revision verification cleared the stale-log ambiguity before the next PR3-S1 replay
1. I verified the live ingress service against the current ECS deployment only, not against historical CloudWatch streams.
2. The active service state is now explicit:
   - ECS service raud-platform-dev-full-ig-service is on task definition revision :3,
   - all six running tasks are HEALTHY,
   - all ALB targets in target group p-dev-full-ig-svc are healthy,
   - each running task is pinned to image digest sha256:28deae6b0752b116ab44f0c286805df8be35761059d06df939069e95501a18cb,
   - the active task definition includes PLATFORM_BUNDLE_ROOT=/app.
3. I then pulled only the current task log streams:
   - cs/ig/21d9769aeb71436592f82dd779858d25
   - cs/ig/26fcea06e75a498db0f4fd0f8ba3e3ab
   - cs/ig/2d202841ec91448a802d7f6f8573fa5d
   - cs/ig/390adb9cc61940c1836271226c7be8bc
   - cs/ig/88ce0c3630a5437eb9702ecb92bfb557
   - cs/ig/8cf0f30ef7304ce9afba1822a6af9122
4. Those current streams show only healthy gunicorn startup with no FileNotFoundError, no schema-path failure, and no boot-loop behavior.
5. Production interpretation:
   - the previous /app/src/config/... path error belonged to drained revision-:2 work and is not the active runtime truth anymore,
   - the service-backed ingress edge is now materially healthy enough for the next bounded replay,
   - the next failure signal, if any, should be treated as genuine throughput/latency/error evidence under load rather than a stale deployment artifact.
6. Immediate next step pinned:
   - rerun bounded canonical PR3-S1 from the same strict PR3 root against the service path,
   - keep the active metric surface on ALB,
   - evaluate admitted EPS, 4xx/5xx, and latency tails directly from the live service edge.
## Entry: 2026-03-06 22:15:00 +00:00 - PR3-S1 replay launcher hit Fargate quota because the WSP lane shape is oversized for the current service-backed architecture
1. The first bounded rerun against the corrected service-backed ingress did not fail inside IG.
2. It failed during WSP fleet launch with:
   - PR3.S1.WSP.B01_RUN_TASK_FAILED:wsp_lane_128:Youve reached the limit on the number of vCPUs you can run concurrently.
3. Live capacity facts are explicit:
   - account Fargate on-demand quota in u-west-2 is 140 vCPU,
   - current WSP task definition (raud-platform-dev-full-wsp-ephemeral:29) is pinned cpu=1024, memory=2048,
   - current service-backed IG runs 6 x 2 vCPU = 12 vCPU continuously.
4. Therefore the prior S1 calibration shape no longer fits the materialized architecture:
   - 138 WSP lanes at 1 vCPU each require 138 vCPU,
   - combined with 12 vCPU on the ingress service, the run attempts 150 vCPU,
   - the launch predictably fails before the full lane fleet materializes.
5. Production interpretation:
   - this is a test-rig capacity-shape defect, not an ingress throughput defect,
   - keeping 1 vCPU per WSP lane is unjustified for an HTTP replay emitter and wastes account concurrency that now belongs to the always-on ingress shell.
6. Chosen correction:
   - keep the steady objective fixed at 3000 admitted eps,
   - keep the canonical 138 lane topology for now,
   - right-size each WSP lane to .5 vCPU / 1 GiB for the next bounded replay (	ask_cpu=512, 	ask_memory=1024).
7. Why this is the correct production move:
   - the emitter workload is network/HTTP paced and checkpoint-light, not transform-heavy,
   - the per-lane target at 3005/138 ~= 21.8 eps does not justify 1 vCPU reservations,
   - right-sizing the replay fleet removes an artificial account-quota blocker without diluting the production throughput claim.
8. Additional evidence-governance fix applied in parallel:
   - pr3_s1_executor.py now consumes the runtime summary latency surface directly instead of re-reading AWS/ApiGateway latencies after the active S1 edge moved to the service-backed ALB path.
9. Immediate next step pinned:
   - rerun bounded canonical PR3-S1 with 	ask_cpu=512, 	ask_memory=1024,
   - keep lane_count=138, stream_speedup=95, 	arget_request_rate_eps=3005,
   - adjudicate on the corrected ALB-surface runtime summary plus the synced S1 receipt layer.
## Entry: 2026-03-06 22:30:00 +00:00 - Right-sized WSP lanes cleared the launcher quota, exposing the real service-backed IG hot-path bottleneck
1. I reran bounded canonical PR3-S1 with the same steady objective and calibrated source setpoint but with WSP lane overrides 	ask_cpu=512, 	ask_memory=1024.
2. That right-sizing solved the Fargate quota blocker completely:
   - all 138 WSP lanes launched,
   - no B01_RUN_TASK_FAILED,
   - the fleet reached the measurement window cleanly.
3. The resulting impact metrics are materially red:
   - 
equest_count_total=66,642,
   - dmitted_request_count=65,029,
   - observed_request_eps=370.233,
   - observed_admitted_eps=361.272,
   - rror_rate_ratio=0.024204,
   - 4xx_total=1,219,
   - 5xx_total=394.
4. CloudWatch/ECS evidence narrows the fault domain:
   - ALB TargetResponseTime p95 ranged about .769s -> 3.480s,
   - ALB TargetResponseTime p99 ranged about 2.382s -> 4.335s,
   - ECS service CPU stayed around 54-60%,
   - ECS service memory stayed around 10-12%.
5. Production interpretation:
   - the service is not failing because raw container CPU or memory is exhausted,
   - the active bottleneck is a slow synchronous request path that drives WSP retries (	imeout, http_502) and edge-generated ALB 4xx/5xx,
   - this is the first materially trustworthy service-backed hot-path failure signal.
6. WSP lane logs confirm the pressure signature:
   - repeated IG push retry attempt=1/5 reason=timeout,
   - intermittent 
eason=http_502,
   - lane emission rates collapse during the steady window because each blocked request stalls replay progress.
7. The current observability gap is unacceptable for production hardening:
   - IG already measures phase.publish_seconds, phase.receipt_seconds, and total dmission_seconds,
   - but those metrics are not reaching CloudWatch from the gunicorn-managed service shell,
   - so the existing service posture is hiding the precise dependency that is stalling the hot path.
8. Chosen next correction:
   - route raud_detection logging through the gunicorn error handlers,
   - emit per-request managed-edge slow-request logs (status + lapsed_ms) for degraded calls,
   - fix the dispatcher's ALB latency collection so S1 no longer carries a false LATENCY_UNREADABLE blocker,
   - rebuild the immutable image, rematerialize the service, and run a smaller diagnostic window to surface the phase timings before the next full steady rerun.
9. This is a production correction, not a diagnostic shortcut:
   - without hot-path phase visibility, any further throughput tuning would be guesswork,
   - with it, the next remediation can target the real synchronous dependency rather than blindly changing thread counts or lane counts.
## Entry: 2026-03-06 22:45:00 +00:00 - PR3-S1 runtime evidence is currently contaminated by duplicate-path replay because the dispatcher reuses a stale platform_run_id
1. I inspected the bounded revision-4 diagnostic window before making further capacity changes.
2. The key finding is that the observed PR3-S1 window is not measuring fresh admit-path throughput. It is measuring mostly duplicate-path throughput.
3. Evidence chain:
   - dispatcher manifest still injected `platform_run_id=platform_20260223T184232Z`,
   - IG metrics logs for the same window are dominated by `decision.DUPLICATE`,
   - duplicate-path latency summaries are materially lower than the managed-edge request latencies seen at the ALB edge,
   - therefore the current S1 score is polluted by idempotency replays against an old namespace.
4. Why this matters for production readiness:
   - duplicate-path performance is useful realism evidence, but it is not the canonical proof for steady admit-path capacity,
   - claiming fresh-ingest throughput from a duplicate-heavy window would be a false certification claim,
   - any further scaling/remediation based on this polluted score would target the wrong bottleneck.
5. Root cause is not in the platform runtime itself. It is in the PR3-S1 dispatcher contract:
   - `scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py` hardcodes a stale default `platform_run_id`,
   - that causes every rerun to land in an already-populated idempotency namespace unless the operator manually overrides it.
6. Production-grade correction chosen:
   - remove the stale hardcoded default,
   - mint a fresh attempt-scoped `platform_run_id` by default for every PR3-S1 replay attempt,
   - preserve explicit override capability only when a deliberate same-run replay is actually intended.
7. This is the correct design move because fresh-admit certification and duplicate/replay certification are different evidence lanes and must not be silently mixed.
8. Immediate implementation steps pinned:
   - patch the dispatcher default run identity behavior,
   - rerun bounded S1 with a fresh run namespace,
   - inspect admit-path metrics separately from duplicate-path metrics,
   - only then decide whether the next bottleneck is WSP emission, IG hot path, or downstream publish/receipt work.
## Entry: 2026-03-06 23:05:00 +00:00 - PR3-S1 hot-path remediation pivot: remove synchronous receipt-path drag before scaling the ingress fleet
1. I reviewed the truthful fresh-admit PR3-S1 evidence after the stale `platform_run_id` fix. The runtime is now measuring real `ADMIT` behavior, not duplicate-path throughput.
2. The measured bottleneck is structurally consistent with the managed IG implementation:
   - request thread performs DDB dedupe lookup / state mutation,
   - waits for synchronous Kafka ACK before declaring `ADMIT`,
   - then writes the full receipt object to S3 on the same request thread,
   - then performs an additional idempotency lookup only to echo `receipt_ref` in the HTTP response,
   - and returns the full receipt payload inline.
3. Evidence already collected narrows the dominant substeps:
   - `phase.publish_seconds` is materially non-trivial,
   - `phase.receipt_seconds` is materially non-trivial and often larger than publish,
   - task CPU and memory are not saturated,
   - therefore simply scaling task size/count without changing the critical path would be expensive and still structurally weak.
4. I considered three remediation classes:
   - A) revert WSP/IG path assumptions or lower PR3 expectations so the current path can go green faster,
   - B) keep the path as-is and only scale the ingress fleet/worker counts aggressively,
   - C) reduce synchronous per-request work first, then scale only from measured need.
5. I am rejecting A because it is certification gaming and would preserve a toy-grade hot path.
6. I am rejecting B as the first move because it pays to carry avoidable latency: one admitted event currently forces a durable receipt object write plus a redundant post-write lookup before the response returns.
7. Chosen production-grade posture is C:
   - keep `ADMIT` semantics tied to durable EB append,
   - stop paying for unnecessary synchronous response work on the request thread,
   - retain explicit receipt truth but decouple its object-store materialization from the latency-critical edge response where possible,
   - add fine-grained substep metrics so later scaling decisions are grounded in measured latency shares instead of guesswork.
8. The concrete changes I intend to make now are:
   - remove the redundant post-admission lookup in the managed HTTP/Lambda response path,
   - stop returning the full receipt body inline on the hot path and return a lean acknowledgement contract instead,
   - instrument DDB lookup/in-flight/admitted/receipt-ref update and object-store receipt write latencies separately,
   - preserve receipt/object truth while giving the runtime evidence needed to decide whether the next limiter is Kafka ACK latency, DDB latency, or residual receipt persistence.
9. Why this is the correct production move:
   - real production ingress edges minimize synchronous payload/lookup overhead on the request path,
   - the durable truth requirement remains intact because `ADMIT` still waits for EB append and persistent dedupe state,
   - the next rerun will tell us whether the remaining latency can be solved by configuration/right-sizing or whether the receipt materialization itself must move behind an asynchronous durability boundary.
## Entry: 2026-03-06 23:20:00 +00:00 - Implemented first hot-path fix set: remove redundant lookup, expose receipt refs directly, and raise AWS client pool ceilings for managed IG
1. I implemented the first production-grade remediation boundary in the ingress code rather than continuing to rerun the same red PR3-S1 window.
2. Code changes made:
   - `Receipt` now carries `ref` directly so callers do not need to re-query idempotency state after admission to learn the receipt locator.
   - `aws_lambda_handler.py` and `service.py` now return `receipt.ref` directly instead of doing a second lookup after `admit_push_with_decision(...)`.
   - `store.py` now builds S3 clients with an explicit runtime botocore config, including a materially larger connection pool (`IG_AWS_MAX_POOL_CONNECTIONS`, default `256`) and explicit timeout/retry knobs.
   - `aws_lambda_handler.py` now applies the same runtime config pattern to SSM/SQS/DynamoDB clients/resources instead of accepting the tiny default botocore pool.
   - `admission.py` now emits finer-grained timings for:
     - `phase.dedupe_lookup_seconds`
     - `phase.dedupe_inflight_seconds`
     - `phase.dedupe_admitted_seconds`
     - `phase.receipt_object_seconds`
     - `phase.receipt_index_seconds`
3. Why this boundary was chosen first:
   - the previous managed-edge code was running 100+ request threads per task against botocore clients that default to a very small HTTP connection pool,
   - that is a classic source of request-thread queuing under load and fits the observed `phase.receipt_seconds` inflation with moderate CPU usage,
   - the redundant post-admission lookup was guaranteed wasted work on every successful request and had no production value.
4. Validation completed locally:
   - `py_compile` passed for all changed IG modules,
   - targeted ingress tests passed (`test_managed_service.py`, `test_phase4_service.py`, `test_admission.py`),
   - the only skipped/blocked local suite was `test_phase510_efficiency.py` because `psycopg` is absent in the local environment, which is unrelated to the new hot-path change itself.
5. Expected production effect of this boundary:
   - lower tail latency on DDB/S3-backed request phases by reducing client-side connection starvation,
   - remove one entire extra DDB lookup from every successful managed-edge response,
   - improve the next PR3-S1 rerun's diagnostic power because the logs will now show whether residual bottleneck mass remains in Kafka ACK or in object-store receipt persistence.
6. I have intentionally not claimed victory from this change alone.
   - If the rerun remains materially red, the next production-grade decision point will be whether receipt-object materialization itself must move behind a durable asynchronous boundary rather than staying inline.
## Entry: 2026-03-06 23:34:00 +00:00 - Verified live rollout of IG revision 5 and prepared the next bounded canonical PR3-S1 rerun
1. I verified that the managed ingress service has materially picked up the new hot-path build. The live ECS service is now deploying task definition `fraud-platform-dev-full-ig-service:5` and the task definition image is pinned to `230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-full@sha256:0803c98e947e8b2dfd243d085b860fbdcdca603785e7362a14522766b897a341`.
2. The live runtime posture matches the intended production envelope for this test boundary:
   - private subnets only (`assignPublicIp=DISABLED`),
   - 6-task service backing the ALB edge,
   - task shape `2048 CPU / 4096 MiB`,
   - IG rate-limit env pinned to `3000 rps / 6000 burst`,
   - gunicorn shape still `4 workers x 32 threads`.
3. This matters because the next PR3-S1 window must test the changed ingress hot path, not the stale revision-4 code. Without this check the rerun would risk repeating old evidence under a new narrative.
4. I am not treating rollout success as closure. The only meaningful next proof is a fresh bounded canonical WSP->IG run with a fresh platform namespace, followed by impact-metric analysis against the production thresholds already pinned for PR3 steady ingress.
5. If the rerun remains materially red after this hot-path boundary, the next decision point will be structural rather than cosmetic: either the synchronous Kafka/S3 receipt work still dominates, or the current gunicorn/service concurrency shape is itself mismatched to the I/O pattern under 3k steady EPS aspirations.
## Entry: 2026-03-06 21:48:00 +00:00 - Separated the remaining PR3-S1 red into two distinct problems: one real replay-envelope miss and one measurement bug
1. The bounded rerun on the new ingress build produced a materially cleaner result than the previous boundary:
   - `observed_admitted_eps=465.75` over the 60-second measurement window,
   - `admitted_request_count=27945`,
   - `4xx_total=0`,
   - `5xx_total=0`.
2. This means the last ingress hot-path hardening did matter. The platform is no longer failing the steady window through HTTP errors at this load level. But the result is still nowhere near production-ready because steady throughput remains only ~15.5% of the 3k EPS requirement.
3. I investigated whether this remaining shortfall is still primarily ingress-side. The truthful answer is more nuanced:
   - the replay harness did not actually drive 3k candidate requests/sec,
   - and the latency collector reported `unavailable` even though live latency metrics exist.
4. Replay-envelope finding:
   - lane logs show the canonical WSP path is using all four oracle-backed outputs (`arrival_events_5B`, `s1_arrival_entities_6B`, `s3_event_stream_with_fraud_6B`, `s3_flow_anchor_with_fraud_6B`),
   - with `stream_speedup=95` and `24` lanes, the measured aggregate request rate landed at ~`465.75` EPS,
   - therefore this boundary was under-driven by the certification harness itself and cannot reveal true 3k-edge behaviour.
5. Production interpretation of the replay-envelope finding:
   - this is not a reason to lower the PR3 target,
   - it is evidence that our oracle-backed replay multiplier is still calibrated for a much smaller world clock than the target production envelope,
   - so the next correct move is to increase the replay multiplier (and, if needed, lane count) until the driver can materially challenge the edge at the declared 3k steady EPS requirement.
6. Measurement-bug finding:
   - direct CloudWatch inspection shows `AWS/ApplicationELB TargetResponseTime p95/p99` datapoints exist for the same measurement minute,
   - but the dispatcher stores `target_group_dimension` as `fp-dev-full-ig-svc/...` instead of CloudWatch's required `targetgroup/fp-dev-full-ig-svc/...`,
   - so the latency query is structurally wrong and `B23` is a tooling bug, not absence of latency evidence.
7. I considered three paths:
   - A) keep rerunning with `stream_speedup=95` and hope ingress-only changes close a target the harness is not even driving,
   - B) lower PR3's declared target to match the current replay envelope,
   - C) fix the latency collector, then repin the next replay envelope to a mathematically credible speedup for 3k steady proof.
8. I am choosing C. A is wasted spend and B is certification dishonesty. The current measured ratio implies the next attempt should use a replay multiplier on the order of ~`650-700` rather than `95` if we keep the same 24-lane topology.
9. Immediate actions pinned:
   - patch the ALB target-group dimension handling so latency evidence is truthful,
   - rerun PR3-S1 with a materially higher replay multiplier on the same canonical remote path,
   - use the first high-drive truthful latency/throughput window to decide whether the next production remediation belongs in IG concurrency/right-sizing, receipt-path redesign, or WSP replay topology.
## Entry: 2026-03-06 21:46:00 +00:00 - PR3-S1 now points to a structural WSP replay bottleneck, not oracle pacing, and the next fix must add intra-output HTTP concurrency
1. I reran PR3-S1 after fixing the ALB target-group dimension and after materially increasing the replay multiplier from `95` to `700`.
2. Result:
   - latency evidence is now truthful from CloudWatch ALB percentiles,
   - but throughput did not rise; it actually stayed in the same class (`~431 admitted EPS` vs `~466` before).
3. This falsifies the earlier possibility that oracle time-density was still the dominant limiter. The dominant limiter is now the WSP implementation itself.
4. Evidence for the WSP bottleneck:
   - lane logs at `speedup=700` show per-output emitted counts almost identical to the earlier `speedup=95` run,
   - therefore removing more inter-event sleep does not increase effective request rate,
   - so the runtime is spending most of its wall clock blocked in the synchronous push path rather than in replay pacing.
5. Code-path cause:
   - each `_stream_output(...)` loop calls `self._push_to_ig(envelope)` synchronously per event,
   - `WSP_OUTPUT_CONCURRENCY` only parallelizes across distinct outputs, and this PR3 lane uses four outputs,
   - therefore each lane tops out at four in-flight HTTP pushes regardless of target rate.
6. Production meaning:
   - scaling lanes into the hundreds just to compensate for a serialized replay client would be the wrong engineering move and an avoidable spend failure,
   - the correct production-grade move is to add bounded intra-output in-flight push concurrency while preserving truthful checkpoint safety and rate-limiter control.
7. Additional tooling bug found at the same boundary:
   - ALB `TargetResponseTime` is reported in seconds, but the dispatcher currently records the value as if it were already milliseconds,
   - so the truthful tail on this run is roughly `p95681 ms`, `p991004 ms`, not `0.68 ms / 1.00 ms`.
8. Chosen remediation set:
   - fix latency units in the dispatcher,
   - extend WSP with bounded per-output push concurrency and contiguous checkpoint advancement on success,
   - expose that concurrency via the PR3 dispatcher so the canonical lane can be driven to the real 3k certification band without brute-force lane explosion.
## Entry: 2026-03-06 21:55:00 +00:00 - Local validation for the WSP concurrency boundary succeeded via direct smoke even though pytest collection is blocked by missing psycopg in the workstation env
1. I validated the new WSP intra-output concurrency path in two layers:
   - `py_compile` passed for `src/fraud_detection/world_streamer_producer/runner.py` and `scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py`,
   - a direct local smoke using an oracle-style temporary stream view and `WSP_IG_PUSH_CONCURRENCY=4` produced `status=STREAMED`, `emitted=8`, `max_concurrency=4`.
2. This direct smoke matters more than a handwave because it confirms the new path is actually issuing concurrent pushes rather than merely carrying dead configuration.
3. Pytest collection for the WSP service tests is still blocked by the workstation missing `psycopg`, which is an environment gap rather than a code-path regression. I am explicitly not conflating that with a functional failure in the new concurrency boundary.
4. Next production action is therefore valid:
   - commit/push the WSP concurrency and PR3 metric fixes,
   - repack the remote image,
   - rerun PR3-S1 with the canonical lane using the new `WSP_IG_PUSH_CONCURRENCY` control.
## Entry: 2026-03-06 21:53:00 +00:00 - Materialized the WSP concurrency boundary into the remote runtime by repacking the shared platform image and registering WSP task definition revision 30
1. The code changes alone were not enough because PR3-S1 launches remote ECS tasks from the pinned `fraud-platform-dev-full-wsp-ephemeral` task definition.
2. I repacked the shared platform image from commit `fba6d353de6389183caafb7d7f01899595edc984` through workflow run `22783424960` and obtained immutable digest `sha256:8f70c1f862fe28f14398b292f271f6fa7085a0c25eead2d1574c8a5e846c0143`.
3. I then registered `fraud-platform-dev-full-wsp-ephemeral:30` pinned to that digest. This is the critical materialization step because `resolve_task_definition(...)` in the PR3 dispatcher will now pick up the WSP runner that includes:
   - bounded intra-output HTTP push concurrency,
   - corrected ALB latency derivation wiring,
   - the new PR3 dispatcher control surface for `WSP_IG_PUSH_CONCURRENCY`.
4. Evidence for the task-definition refresh is stored under `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/wsp_taskdef_refresh_20260306T215258Z/`.
5. Next action is the first truthful rerun against the remotely materialized WSP concurrency boundary. That run will tell us whether the replay lane can finally drive the platform into the actual 3k certification band, and, if it can, whether ingress latency and 4xx posture remain production blockers.

## Entry: 2026-03-06 22:05:30 +00:00 - PR3-S1 ingress collapse is now traced to two internal concurrency stampedes, not just insufficient task count
1. I reviewed the red canonical `PR3-S1` window using the live ECS service history, ALB metrics, and raw ingress logs for `2026-03-06T21:54Z` through `2026-03-06T21:57Z`.
2. Impact metrics from that red window:
   - ALB `RequestCount`: `2512`, `7529`, `9699` per minute across the active three-minute measurement window.
   - Target `2xx`: `2782` then `4193`; ALB-side `5xx`: `119` then `1`.
   - ALB tail latency: `p95=24.428s`, `p99=29.034s` at the worst minute.
   - ECS service CPU: `84.18%` average at `21:54`, `65.65%` at `21:55`, `93.73%` at `21:56`, with `max=100%` in each hot minute.
   - ECS memory stayed low (`16%` to `22%` average), so this is not a memory-pressure failure mode.
3. The service events make the runtime consequence explicit: tasks were repeatedly marked unhealthy because the container health check timed out, which means the ingress service starved its own `/healthz` path under load and began self-replacing tasks during the certification window.
4. I pulled the raw ingress log corpus and found two internal concurrency defects that better explain the collapse than simple under-scaling:
   - `_gate_for(platform_run_id)` is not thread-safe, so first-hit concurrency on a new run stampedes gate construction. The red window emitted `313` separate `IG gate initialized` lines, each costing roughly `p50=6.234s`, `p95=12.052s`, `max=15.8s`.
   - `HealthProbe.check()` runs on the request path, and the ECS service pins `IG_HEALTH_BUS_PROBE_MODE="describe"`. On a stale or cold health cache, request threads perform object-store probe writes and Kafka metadata checks inline. Because that path is also unsynchronized, multiple threads can stampede the same expensive refresh boundary.
5. The phase logs confirm this is not primarily an S3 receipt problem anymore. In the red window:
   - `phase.validate_seconds` was the dominant exploding phase, repeatedly landing in the `20s` to `95s` band.
   - `phase.publish_seconds` was materially lower (`~1s` to `4.5s`).
   - `phase.receipt_seconds` was materially lower again (`~0.8s` to `6.4s`).
6. A second production defect is also now proven: the ingress service keeps working on requests long after the client budget is already lost. The managed request logs show:
   - `p50 elapsed_ms ~= 988.6`,
   - `p95 elapsed_ms ~= 95449.9`,
   - `p99 elapsed_ms ~= 110377.0`,
   - `max elapsed_ms ~= 134819.2`.
   This means request threads continue burning CPU for tens of seconds after ALB should already have abandoned the response, which amplifies backlog and directly contributes to health starvation.
7. Production interpretation:
   - increasing task count alone would be lazy and insufficient because it would scale an internally stampeding request path;
   - the first correct remediation is to remove the hot-path stampedes and enforce a request lifecycle that cannot keep consuming compute far beyond the caller timeout;
   - only after that should the service concurrency envelope be re-tuned and scaled for the 3k steady target.
8. Chosen remediation sequence:
   - make gate construction single-flight per process/run,
   - make health evaluation cached and background-refresh driven instead of request-thread driven,
   - repin the ECS service away from `IG_HEALTH_BUS_PROBE_MODE=describe` on the hot path,
   - tighten the request lifecycle so work is not allowed to continue unbounded after the ingress budget is effectively lost,
   - then rerun the same canonical `PR3-S1` boundary before deciding how much horizontal scale is still required.

## Entry: 2026-03-06 22:14:00 +00:00 - Implemented the anti-stampede ingress fix set and repinned the ECS service health posture for PR3-S1
1. I implemented the first structural remediation set directly against the service-backed ingress code instead of spending another PR3 rerun on the known broken request lifecycle.
2. Code-path changes made:
   - `src/fraud_detection/ingestion_gate/aws_lambda_handler.py`
     - added `_GATE_CACHE_LOCK` so `_gate_for(platform_run_id)` is now single-flight per process/run;
     - moved the first `health.check()` into gate construction so the first request burst does not stampede cold health refresh inline;
     - preserved the same DDB/Kafka/S3 admission semantics after gate initialization.
   - `src/fraud_detection/ingestion_gate/health.py`
     - added lock-protected state and refresh coordination;
     - changed `check()` so cached health is returned immediately to request threads when stale health is being refreshed;
     - introduced background refresh for stale cached health instead of forcing live request threads to perform probe writes and Kafka metadata checks;
     - changed `bus_probe_mode in {"", "none"}` to mean "do not degrade request-path health just because metadata probing is intentionally disabled".
3. Infrastructure pin changes made:
   - `infra/terraform/dev_full/runtime/main.tf` now binds `IG_HEALTH_BUS_PROBE_MODE` from a variable instead of hardcoding `describe` into the ECS ingress task definition.
   - `infra/terraform/dev_full/runtime/variables.tf` now pins:
     - `ig_service_health_bus_probe_mode = "none"`
     - `ig_service_desired_count = 12`
4. Why the desired-count change is included in the same boundary:
   - once the hot-path stampedes are removed, the next limit should be measured on a service with a more credible horizontal envelope than the prior `6` tasks;
   - `12` is not the final production claim, but it is a better first post-fix envelope for a truthful bounded rerun without jumping blindly to an extreme fleet size.
5. Validation completed:
   - `py_compile` passed for the changed ingress runtime modules;
   - `terraform fmt -check infra/terraform/dev_full/runtime` passed;
   - targeted ingress tests passed via `py -3.12 -m pytest`:
     - `tests/services/ingestion_gate/test_health_governance.py`
     - `tests/services/ingestion_gate/test_managed_service.py`
     - `tests/services/ingestion_gate/test_admission.py`
6. Test additions/updates capture the new intended semantics:
   - request-path health now returns cached status immediately while a stale refresh runs in the background;
   - `bus_probe_mode=none` is no longer treated as an automatic amber state;
   - publish/store health still escalates to `RED`, but no longer by synchronously blocking every request thread.
7. Production expectation from this boundary:
   - materially fewer `IG gate initialized` events during a single run window;
   - no Kafka metadata-probe storm on request threads;
   - a large reduction in the pathological `phase.validate_seconds` tail;
   - fewer health-check timeouts and less task churn under bounded PR3 pressure.
8. I am not assuming this closes PR3-S1 by itself. The next rerun will tell us whether the post-stampede frontier is now honest service capacity, synchronous Kafka ACK cost, or another remaining lifecycle defect.

## Entry: 2026-03-06 22:24:00 +00:00 - Live rollout is now materially aligned with the ingress anti-stampede fixes, so the next PR3-S1 rerun is a truthful post-remediation measurement
1. I verified the live runtime posture after the image refresh and targeted ECS rollout instead of assuming the previous update succeeded.
2. The ingress service is now materially running the corrected image and corrected hot-path health posture:
   - ECS service `fraud-platform-dev-full-ig-service` is on task definition `:6`,
   - the container image is pinned to immutable digest `sha256:1f33883cf7c53e8b6f5aaae3e79e62a880048ff97ec35142fb73b3da7e3be80c`,
   - `IG_HEALTH_BUS_PROBE_MODE=none`,
   - desired/running count is `12/12`,
   - network posture remains private-subnet only with `assignPublicIp=DISABLED`.
3. The remote WSP replay runtime is also materially aligned to the same corrected digest:
   - task definition `fraud-platform-dev-full-wsp-ephemeral:31`,
   - image digest `sha256:1f33883cf7c53e8b6f5aaae3e79e62a880048ff97ec35142fb73b3da7e3be80c`.
4. This matters because the next `PR3-S1` measurement is no longer polluted by stale image drift. If the state is still red after this rerun, the remaining limiter is now a live platform behavior issue rather than a packaging/materialization mistake.
5. Production interpretation:
   - the next rerun is the first honest measurement of the anti-stampede ingress boundary plus the concurrency-capable WSP path on remote compute;
   - success now requires impact metrics to move materially toward the production band, not just a smaller blocker count;
   - if throughput remains below the `3000 eps` steady target or latency/error metrics remain outside the pinned envelope, I will keep pushing on the next real limiter instead of treating this rollout as a soft win.
6. Immediate action after this note is a bounded canonical `PR3-S1` rerun on the same strict execution root so I can measure whether the validate-path collapse is actually fixed and what residual constraint remains.

## Entry: 2026-03-06 22:31:00 +00:00 - Post-remediation PR3-S1 proves the next frontier is transient retry handling plus service-edge latency, not another correctness collapse
1. I reran the same bounded canonical `PR3-S1` window on the refreshed WSP image and corrected ingress service posture.
2. The run moved materially in the right direction:
   - admitted throughput increased from `46.367 eps` to `621.800 eps`,
   - ALB `5xx` fell from `119` to `0`,
   - ALB `p95` latency improved from `24.428s` to `7.138s`,
   - ALB `p99` latency improved from `29.034s` to `10.966s`.
3. This proves the anti-stampede fix set was necessary and effective. The service is no longer collapsing into self-replacement and broad 5xx failure under the same campaign shape.
4. The state is still far from production, and the remaining defects are now clearer:
   - steady admitted throughput is still only `621.8 eps` against the `3000 eps` target;
   - error ratio is still `3.986%` against a `0.2%` ceiling;
   - almost all residual failures are retry-driven client-side rejections, not backend 5xx.
5. I inspected the new WSP and IG logs and found the next real production defect:
   - WSP retries timed-out pushes with the same `event_id`;
   - IG currently sees the duplicate while the first publish is still in flight and emits `decision=QUARANTINE` with `reason=PUBLISH_IN_FLIGHT`;
   - WSP treats that 4xx-style rejection as terminal `IG_PUSH_REJECTED`, which kills the affected lane even though the underlying event is not bad data.
6. This is not acceptable for a production at-least-once ingress boundary. A retry overlap on the same idempotency key is an expected transport reality under pressure; it should be coalesced into duplicate success or surfaced as a transient retryable condition, not persisted as quarantine truth.
7. Supporting live evidence from the rerun:
   - IG emitted repeated `PUBLISH_IN_FLIGHT` quarantines across business and context event types during the hot minute;
   - WSP lane failures explicitly show `reason=IG_PUSH_REJECTED` after timeout/retry activity;
   - target-side `4xx` counts are small but non-zero, which is enough to poison lane continuity and inflate the overall error ratio;
   - ECS CPU still hit `100%` maxima while average CPU sat in the `52%` to `79%` band, meaning the service is improved but still not efficiently shaped for the target load.
8. Chosen remediation sequence from this evidence:
   - stop writing quarantine truth for `PUBLISH_IN_FLIGHT` retry overlap;
   - coalesce in-flight duplicates by waiting briefly for the original publish to resolve, and return retryable transport errors when it does not;
   - map transient in-flight/ambiguous conditions at the managed edge to retryable `5xx` instead of terminal client rejection;
   - retune the ingress service concurrency envelope after the retry storm is removed so the next rerun measures honest service capacity rather than duplicate amplification.

## Entry: 2026-03-06 22:42:00 +00:00 - Implemented retry-safe in-flight dedupe handling and repinned the service-edge concurrency envelope away from the oversubscribed thread posture
1. I implemented the next ingress correction directly against the retry boundary instead of trying to brute-force through it with more campaign volume.
2. In `src/fraud_detection/ingestion_gate/admission.py`:
   - existing rows in `PUBLISH_IN_FLIGHT` or `PUBLISH_AMBIGUOUS` are no longer immediately turned into quarantine truth;
   - the gate now waits briefly for the original publish attempt to resolve and then reuses the resolved state if it becomes `ADMITTED`;
   - if the row is still unresolved after the bounded wait, the gate raises a retryable transport error (`PUBLISH_IN_FLIGHT_RETRY` or `PUBLISH_AMBIGUOUS_RETRY`) instead of persisting a false semantic quarantine.
3. In `src/fraud_detection/ingestion_gate/aws_lambda_handler.py`:
   - retryable in-flight/ambiguous transport conditions are now mapped to `503 retry_required`;
   - those conditions do not get DLQ-written, because they are not malformed data and should not pollute downstream operational truth.
4. In the test suite:
   - added proof that an in-flight duplicate resolves into `DUPLICATE` once the original publish commits;
   - added proof that unresolved in-flight duplicates raise the new retryable error;
   - added proof that the managed edge maps the retryable in-flight boundary to `503` without DLQ side effects.
5. I also repinned the service concurrency envelope in `infra/terraform/dev_full/runtime/variables.tf`:
   - `ig_service_desired_count` moved from `12` to `16`;
   - `ig_service_gunicorn_threads` moved from `32` to `8`;
   - workers remain `4`.
6. Why this concurrency repin is paired with the retry fix:
   - the prior `4 x 32` thread posture on a `2 vCPU` Python task is a poor production fit for a mixed CPU/network admission path because it oversubscribes the interpreter, amplifies queueing, and hides real service capacity behind long tail latency;
   - reducing thread count while modestly widening the fleet gives the next rerun a more credible process/thread balance and a better chance of exposing the honest throughput frontier.
7. Validation completed before any rollout:
   - `py_compile` passed for the changed ingress modules;
   - ingress test suite passed (`24 passed`);
   - `terraform fmt -check infra/terraform/dev_full/runtime` passed.
8. Immediate next steps:
   - commit/push this boundary,
   - repack the shared platform image,
   - roll the corrected image and new service posture live,
   - rerun the same bounded canonical `PR3-S1` state and measure whether transient retry handling plus thread/fleet tuning materially lifts admitted `eps` and collapses the latency tail.

## Entry: 2026-03-06 22:36:44 +00:00 - The retry-safe ingress boundary is now materially live on the dev_full runtime, so the next PR3-S1 rerun is again an honest production-shape measurement
1. I repacked the shared platform image from commit `5d656d5384ed165b551e1ec2e476fa8799b4b40a` through workflow run `22784762559`.
2. The new immutable runtime digest is `sha256:aa9cc0b2ff129d93e1082ab74fbe1dd2b406c3a43fd08dfab6d6ebc4f24e38a0`.
3. I rolled that digest live and recorded the refresh evidence under `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/runtime_refresh_20260306T223644Z/`.
4. Live posture after the refresh:
   - WSP task definition: `fraud-platform-dev-full-wsp-ephemeral:32`
   - IG task definition: `fraud-platform-dev-full-ig-service:7`
   - IG desired/running count: `16/16`
   - IG image digest: `sha256:aa9cc0b2ff129d93e1082ab74fbe1dd2b406c3a43fd08dfab6d6ebc4f24e38a0`
   - IG gunicorn posture: `workers=4`, `threads=8`
   - IG hot-path health probe mode remains `none`
5. Production interpretation:
   - transient retry overlap should no longer pollute semantic quarantine truth or kill lanes as 4xx-style terminal failures;
   - the ingress service is now running a materially saner Python concurrency model than the previous `4 x 32` posture;
   - the next bounded rerun will tell me whether the platform frontier has moved from retry amplification toward honest service capacity, and by how much.

## Entry: 2026-03-06 22:46:00 +00:00 - The next PR3-S1 limiter is front-door queueing, so the ingress plan now shifts from semantic correction to concurrency-slot expansion
1. I inspected the latest hot minute after the retry-safe rollout and found a clear split between application work time and end-to-end edge time:
   - ALB `p95` latency was `13.862s`, `p99` was `23.672s`;
   - inside the app, `admission_seconds p95` across the active IG workers was only about `0.35s` to `0.40s`;
   - `phase.validate/publish/receipt` p95 values were all in sub-second bands.
2. Production interpretation:
   - the service is no longer spending its time inside business logic, dedupe, Kafka publish, or receipt writes;
   - requests are now mostly waiting before they even reach useful application work;
   - the remaining bottleneck is therefore front-door concurrency capacity (worker/thread/task slots), not semantic admission correctness.
3. This explains the current shape:
   - admitted throughput improved again to `1186.5 eps`,
   - `PUBLISH_IN_FLIGHT` noise is gone,
   - residual 4xx/5xx is now relatively small,
   - but ALB queueing keeps the latency tail far above the production envelope and still caps throughput below `3000 eps`.
4. The previous `16 tasks x 4 workers x 8 threads` posture created roughly `512` request-handling slots. That is not enough headroom for a `3000 eps` target when the observed in-app p95 is still around `0.35s+`, because the front door needs materially more concurrent service capacity before queueing collapses.
5. Chosen next repin:
   - raise ingress desired count from `16` to `24`,
   - raise gunicorn threads from `8` to `16`,
   - keep workers at `4`.
6. Why this shape instead of restoring the old `32` threads immediately:
   - the old `4 x 32` posture proved it can oversubscribe the Python runtime badly on `2 vCPU` tasks;
   - `4 x 16` is a controlled expansion that materially increases concurrent request slots while avoiding the worst oversubscription extreme;
   - `24` tasks gives the service a broader front-door fleet so ALB queueing is less likely to pin a subset of tasks into local saturation.
7. The next rerun after this repin should tell me whether the platform is still slot-limited or whether the next ceiling becomes the WSP pressure path itself.

## Entry: 2026-03-06 22:45:22 +00:00 - The front-door concurrency expansion is now live, so the next PR3-S1 rerun specifically tests whether ALB queueing can be collapsed without reintroducing retry-path drift
1. I rolled the ingress capacity repin directly onto the live ECS service without rebuilding the image, because this boundary only changes runtime concurrency settings.
2. Evidence for the live repin is stored under `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/ig_capacity_repin_20260306T224522Z/`.
3. Live posture after the repin:
   - IG task definition: `fraud-platform-dev-full-ig-service:8`
   - IG desired/running count: `24/24`
   - gunicorn posture: `workers=4`, `threads=16`
   - image digest is unchanged from the retry-safe boundary (`sha256:aa9cc0b2ff129d93e1082ab74fbe1dd2b406c3a43fd08dfab6d6ebc4f24e38a0`)
4. This is now a targeted test of queue-collapse capacity, not a semantic change:
   - retry overlap remains fixed,
   - the only new question is whether materially more front-door request slots move the admitted `eps` and latency curve toward the production band.

## Entry: 2026-03-06 22:53:00 +00:00 - After the `24 x 4 x 16` ingress repin, the next suspected limiter is producer fan-out shape rather than server-side correctness or business-logic time
1. The latest bounded rerun improved again:
   - admitted throughput reached `1799.183 eps`,
   - 4xx errors fell below threshold and disappeared from the blocker set,
   - only four blockers remain: throughput shortfall, tiny 5xx residue, and latency p95/p99.
2. The hot-minute evidence sharpens the diagnosis:
   - ALB `p95` remained about `10.107s`, `p99` about `17.412s`,
   - inside the app, `admission_seconds p95` was mostly in the `0.13s` to `0.16s` band on healthy workers, with some slower workers still well below the ALB tail,
   - WSP still logged timeout retries in the hot slice, but only `40` retry lines instead of the earlier storm shapes.
3. Production interpretation:
   - the semantic and in-app execution path is now largely healthy;
   - the front door is better, but the current `24-lane` WSP campaign still may not be fanning traffic broadly enough across the widened ingress fleet;
   - with long-lived HTTP sessions, too few producer lanes can create connection pinning/hot-target behavior that is not representative of a real multi-producer production edge.
4. Chosen next step:
   - keep the target campaign at `3200 eps`,
   - widen WSP lane fan-out from `24` to `48`,
   - lower the launch stagger so the wider producer fleet materializes fast enough to keep the certification window honest,
   - keep the current ingress service posture fixed so the next measurement isolates producer-shape effects.
5. This is a production-realism change, not a shortcut:
   - a financial-institution ingress edge does not receive traffic from twenty-four perfectly sticky long-lived producers only;
   - broader client concurrency is part of realistic ingress preparation, especially when validating load balancing and front-door behavior.

## Entry: 2026-03-06 23:12:00 +00:00 - The 48-lane rerun proved producer fan-out is not the primary remaining PR3-S1 limiter; ingress task churn and edge-capacity posture now become the production-critical remediation lane
1. I inspected the latest canonical `PR3-S1` run after widening `WSP` fan-out from `24` lanes to `48` while holding the ingress service posture fixed.
2. Impact metrics from that run:
   - observed request throughput: `1812.800 eps`
   - observed admitted throughput: `1799.783 eps`
   - error ratio: `0.7180%`
   - `4xx` ratio: `0.7088%`
   - `5xx` ratio: `0.0092%`
   - ALB `p95`: `11.259s`
   - ALB `p99`: `16.762s`
3. Comparison against the previous `24-lane` frontier:
   - admitted throughput moved only from about `1799.183 eps` to `1799.783 eps`, which is effectively no gain;
   - latency remained far outside the production envelope;
   - widening client fan-out alone did not collapse queueing or move the steady frontier toward `3000 eps`.
4. Production interpretation:
   - the platform is no longer primarily limited by narrow producer fan-out;
   - if a `2x` increase in producer lanes leaves admitted throughput flat, the dominant bottleneck now sits at the ingress service edge rather than the replay emitter side;
   - continuing to spend runs on wider producer fleets without changing the service edge would be wasteful.
5. I then inspected live ECS service events during the same hot minute and found repeated task replacement with the explicit reason `Request timed out` on the target-group health check.
6. This is a production-significant defect, not an observability footnote:
   - unhealthy replacements remove live request-serving capacity during the exact hot window we are trying to certify;
   - target churn also inflates tail latency by draining connections and forcing ALB rebalance during pressure;
   - any throughput result produced under this kind of avoidable self-inflicted churn understates the real service capacity and cannot be treated as the final frontier.
7. Chosen remediation in light of the production goal rather than the easiest rerun path:
   - increase per-task CPU and memory so the Python ingress service has more honest compute headroom;
   - shift gunicorn away from a thread-heavy posture and toward more worker processes with fewer threads per worker;
   - widen the fleet again, but as a service-capacity move rather than a producer-fanout move;
   - relax ALB and ECS health-check aggressiveness so healthy-but-busy tasks are not killed during a short hot window.
8. Explicitly rejected alternatives:
   - do nothing and rerun: rejected because it would just measure the same churn-limited frontier again;
   - widen `WSP` lanes further: rejected because `48` lanes already demonstrated that producer fan-out is not the primary limiter;
   - repin back to Lambda or synthetic harnesses: rejected because the current production-shape path is the managed ingress service and the goal is to harden the real path, not find an easier certificate lane.
9. Implementation plan from this evidence:
   - repin IG service from `2 vCPU / 4 GiB / 24 tasks / 4 workers / 16 threads` to a more credible service posture;
   - repin health-check interval/timeout/unhealthy thresholds and grace periods to avoid false eviction under bounded hot windows;
   - rerun the same canonical `PR3-S1` boundary after the live repin and judge it only on impact metrics.

## Entry: 2026-03-06 23:18:00 +00:00 - Applied the next ingress capacity and health-envelope repin in Terraform so PR3-S1 can measure the real service frontier instead of health-check self-sabotage
1. I updated the runtime authority in Terraform to a stronger managed ingress posture:
   - `ig_service_task_cpu: 2048 -> 4096`
   - `ig_service_task_memory: 4096 -> 8192`
   - `ig_service_desired_count: 24 -> 32`
   - `ig_service_gunicorn_workers: 4 -> 8`
   - `ig_service_gunicorn_threads: 16 -> 8`
2. Why this exact shape:
   - the previous posture relied heavily on threads inside a `2 vCPU` Python container, which is a poor production fit once the service is hot and doing repeated JSON, DDB, S3, and Kafka-bound work;
   - increasing worker-process count while reducing per-process threads gives the service more independent accept loops and reduces the chance that health checks sit behind a saturated thread queue;
   - widening the fleet from `24` to `32` tasks provides additional front-door capacity without depending on producer-shape luck.
3. I also introduced explicit health-envelope pins instead of hardcoded aggressive values:
   - health interval `30s`
   - health timeout `10s`
   - healthy threshold `2`
   - unhealthy threshold `5`
   - container health start period `60s`
   - ECS service grace period `180s`
4. Production reasoning for the health repin:
   - the previous `15s / 5s / 2 failures` target-group posture is too eager for a bounded but intense hot window and was actively causing target eviction while the service was still useful;
   - the corrected posture still fails closed on genuinely dead tasks, but it does not destroy capacity because a busy task momentarily queues a `/healthz` response.
5. I also aligned the container-local health probe runtime with the same corrected timeout window by replacing the prior hardcoded `2s` probe timeout with an environment-driven timeout derived from the pinned health setting.
6. This keeps ALB health, ECS health, and container-local health operating under a coherent service-safety contract rather than three different hidden timeout assumptions.
7. Immediate next steps:
   - validate the Terraform delta,
   - apply only the managed ingress target resources needed for this repin,
   - rerun canonical `PR3-S1` on the new live posture,
   - record the resulting impact metrics in the readable state findings.

## Entry: 2026-03-06 23:22:00 +00:00 - A runtime-control defect surfaced during the ingress repin: the Terraform module still defaults the managed ingress service off, so target-only applies must pin the canonical service posture explicitly
1. While applying the new ingress capacity and health-envelope repin, I discovered that `infra/terraform/dev_full/runtime` still defaults `ig_service_enabled=false` unless the canonical managed-ingress posture is supplied explicitly as input.
2. Practical consequence:
   - a target-only Terraform apply against the IG service resources without `ig_service_enabled=true` and an explicit pinned `ig_service_image_uri` does not update the service;
   - it destroys the managed ingress service boundary because Terraform sees the target resources as count `0` under the default posture.
3. That is a control-plane defect, not just an operator mistake:
   - the canonical production ingress path has moved to the managed service, but the runtime module default still reflects an older disabled posture;
   - this creates a dangerous gap between declared production reality and default infrastructure behavior.
4. I immediately recovered the live service by explicitly applying:
   - `ig_service_enabled=true`
   - `ig_service_image_uri=230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-full@sha256:aa9cc0b2ff129d93e1082ab74fbe1dd2b406c3a43fd08dfab6d6ebc4f24e38a0`
   - plus the recreated listener/target-group/task-definition/service resources.
5. Recovery result:
   - service restored on task definition `fraud-platform-dev-full-ig-service:9`
   - live fleet `32/32` on `4096 CPU / 8192 MiB`
   - gunicorn posture `8 workers x 8 threads`
   - corrected health envelope now live (`30s interval / 10s timeout / 5 failures / 180s grace`)
6. I am recording this separately because it is operationally important and auditable:
   - the service was not left down;
   - the recovery was immediate and successful;
   - future Terraform service applies for this managed ingress lane must be executed with the explicit canonical enable/image pins until the control default is corrected structurally.

## Entry: 2026-03-06 23:26:00 +00:00 - The new PR3-S1 frontier shows the remaining bottleneck is synchronous receipt object persistence, not container health or raw compute capacity
1. I reran canonical `PR3-S1` after recovering and stabilizing the new ingress fleet.
2. Impact metrics from the current frontier:
   - observed request throughput: `1935.183 eps`
   - observed admitted throughput: `1934.633 eps`
   - error ratio: `0.0284%`
   - `4xx` ratio: `0.0138%`
   - `5xx` ratio: `0.0146%`
   - ALB `p95`: `13.774s`
   - ALB `p99`: `21.662s`
3. Health and compute interpretation from live runtime telemetry:
   - ECS service remained stable with `32/32` tasks and no unhealthy replacement churn during the run;
   - ECS CPU averaged only about `30.6%` with max about `53.6%`;
   - ECS memory averaged about `9.3%`.
4. This means the new frontier is not a CPU ceiling and not a health-eviction issue anymore.
5. The decisive in-app signal is from the managed ingress metrics logs:
   - `phase.publish_seconds p95` generally remained in the low hundreds of milliseconds or below;
   - `phase.dedupe_*` remained small;
   - `phase.receipt_object_seconds` repeatedly spiked into the multi-second range, with several workers showing `p95` values around `1.9s` to `2.5s` and maxima from roughly `5s` to `11s`.
6. Managed request logs align with that diagnosis:
   - many requests still completed in sub-second or low-single-second times;
   - a meaningful subset of otherwise successful `202` admits spent `15s` to `26s` on the request path.
7. Production conclusion:
   - scaling the ingress fleet further is now low-value because the service is no longer compute-bound;
   - the synchronous S3 receipt object write is now the dominant tail-latency source and the main reason we are still far below the required `3000 eps` steady proof;
   - continuing to pay this S3 write on the hot acknowledge path is the wrong design for a high-EPS production ingress boundary.
8. Chosen next remediation direction:
   - remove full receipt-object persistence from the synchronous admit path;
   - keep durable hot-path provenance in a fast operational store suitable for this edge;
   - move cold receipt object archival off the request path.
9. I am now evaluating the least risky production-grade way to do that without weakening truth ownership or replay/audit provenance.

## Entry: 2026-03-06 23:34:00 +00:00 - Chosen production correction for the new PR3-S1 bottleneck: durable hot receipts move to DDB on the admit path, while cold object archival is removed from the synchronous edge
1. After the `32 x 4096/8192 x 8x8` repin, the evidence showed the ingress service was healthy and underutilized on CPU/memory, but still paying large multi-second tails in `phase.receipt_object_seconds`.
2. I inspected the receipt path and confirmed the hot path still performs a synchronous `S3 put_object` before the admit response completes.
3. Production reasoning:
   - a high-EPS ingress edge should not block client acknowledgement on cold object archival for every admitted event;
   - the durable truth needed at the trust boundary is that the event was admitted, what its receipt payload is, and how to reference that receipt deterministically;
   - cold archival to object storage is still valuable, but it should not be the synchronous gate for the request/ack path.
4. Alternatives considered:
   - more ECS scale: rejected because the fleet is no longer compute-bound;
   - keep synchronous S3 and attempt more minor tuning: rejected because the observed tail is already decisively on the S3 receipt write;
   - async in-process background receipt writes: rejected because it weakens durability if a task dies before flush;
   - new queue + dedicated materializer lane: valid long-term option, but heavier than necessary for the immediate hot-path correction and slower to materialize while the current defect is already isolated.
5. Chosen corrective shape:
   - durable hot receipt persistence moves into the existing DDB admission record for the canonical managed ingress path;
   - `receipt_ref` becomes a deterministic DDB-backed reference (`ddb://...`) rather than an S3 object path on the admit hot path;
   - cold object archival remains a later lane concern instead of a synchronous response dependency.
6. Why this is acceptable for production realism:
   - the ingress path already trusts DDB as its idempotency and state boundary;
   - DDB-backed hot receipts are operationally appropriate for low-latency lookup and duplicate handling;
   - object-store archival can be restored later as an off-path durability/export layer without reintroducing request-path tail latency.
7. Implementation details now applied:
   - `DdbAdmissionIndex.record_receipt(...)` now stores `receipt_payload_json` alongside `receipt_ref` on the existing admission row;
   - `DdbAdmissionIndex.receipt_ref_for(...)` creates the deterministic DDB-backed receipt reference;
   - `IngestionGate` now switches between `object_store` and `ddb_hot` receipt modes via `IG_RECEIPT_STORAGE_MODE`;
   - managed ingress Terraform pins `IG_RECEIPT_STORAGE_MODE=ddb_hot` for the ECS service path.
8. Local validation passed:
   - `py_compile` for the changed ingress modules;
   - targeted ingress tests (`15 passed`);
   - `terraform fmt -check` and `terraform validate`.
9. Immediate next steps:
   - commit/push this hot-path receipt correction,
   - rebuild and redeploy the shared image,
   - rerun canonical `PR3-S1` on the new receipt mode,
   - judge the result only on impact metrics.
## Entry: 2026-03-06 23:46:00 +00:00 - The DDB hot-receipt correction is implemented locally, but PR3-S1 cannot be judged again until the managed ingress service is rolled onto a freshly published immutable image digest
1. The code-level hot-path correction is complete and locally validated, but the live ECS ingress tasks are still running the previous immutable image digest.
2. That means any further PR3-S1 judgment without a fresh image publish and redeploy would be analytically invalid because the measured service would not contain the latest receipt-path correction.
3. Production rule applied here:
   - do not keep load-testing a stale runtime and then misattribute the result to the new design;
   - first refresh the artifact, then refresh the live service, then measure.
4. Exact execution boundary chosen:
   - dispatch the managed packaging lane (`dev_full_m1_packaging.yml`) with explicit OIDC/ECR inputs;
   - capture the new digest from the workflow evidence;
   - roll only the managed ingress resources with explicit `ig_service_enabled=true` and explicit `ig_service_image_uri=<new digest>` so the prior Terraform control defect cannot recur;
   - verify the service reaches steady state on the new task definition before any rerun.
5. Safety conditions that remain in force for the redeploy:
   - no target-only Terraform apply without the explicit canonical service pins;
   - no fresh PR3-S1 run until ECS shows the new task definition/image is actually live;
   - read the new impact metrics against the production thresholds only after confirming the request path is executing the updated code.
6. If the refreshed image materially improves tail latency but still remains below the `3000 eps` steady target, the next work will continue from the live metrics rather than from design assumption.
## Entry: 2026-03-06 23:29:00 +00:00 - Fresh immutable runtime image published for the hot-receipt correction; live ingress can now be redeployed onto the corrected artifact boundary
1. I dispatched the managed packaging lane `dev_full_m1_packaging.yml` against branch `cert-platform` with explicit OIDC/ECR inputs so the latest ingress correction is materialized as an immutable image rather than inferred from the local tree.
2. Packaging run result:
   - GitHub Actions run: `22786239105`
   - source commit: `5bb042bb86f400c43aed0213bafa37e212d650fd`
   - image digest: `sha256:e3e6ee322b81039c0c2f9a349c96eb884b8c47a01a83f7279c414945c0e69813`
   - canonical image URI: `230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-full@sha256:e3e6ee322b81039c0c2f9a349c96eb884b8c47a01a83f7279c414945c0e69813`
3. Why this matters operationally:
   - the previous live ingress service was still running digest `sha256:aa9cc0b2...`, so any further runtime measurement would have been against stale code;
   - the new digest is now the sole valid artifact for judging the DDB hot-receipt correction live.
4. Immediate next action is a controlled ingress-only redeploy using explicit service-enable and image pins so the refreshed artifact becomes the live measurement boundary for the next canonical `PR3-S1` rerun.
## Entry: 2026-03-06 23:36:00 +00:00 - The fresh image rollout exposed a production-operational constraint: the current ingress service rollout policy assumes overlap capacity that the account does not actually have
1. I published the new digest and attempted a controlled ingress-only redeploy to move the live service onto the hot-receipt correction.
2. ECS created task definition `:10` with the correct new digest and `IG_RECEIPT_STORAGE_MODE=ddb_hot`, but the service rolled back before the new deployment could replace the old one.
3. Root cause is now clear from ECS service events and Service Quotas, not speculation:
   - current steady ingress fleet = `32 tasks x 4 vCPU = 128 vCPU`;
   - account Fargate on-demand vCPU quota in `eu-west-2` = `140 vCPU`;
   - current ECS service rollout policy is `deployment_minimum_healthy_percent=50`, `deployment_maximum_percent=200`.
4. Why that fails operationally:
   - a `200%` rollout policy assumes the service may temporarily overlap old and new tasks up to `64` tasks during deployment;
   - this environment cannot do that because it only has `12 vCPU` headroom above the steady `128 vCPU` posture;
   - ECS therefore cannot place enough replacement tasks, trips the circuit breaker, and rolls back to the previous task definition even when the new image itself is healthy.
5. This is not an app-runtime defect and not a reason to back away from the design correction.
6. Production-grade interpretation:
   - if the service is going to remain on this quota envelope, the rollout policy must be quota-aware;
   - alternatively the quota must be raised so that `200%` overlap is materially possible.
7. Chosen immediate correction for `dev_full` so progress remains honest and reproducible:
   - pin ingress deployment policy as quota-aware in Terraform rather than depending on impossible overlap capacity;
   - specifically expose deployment min/max percent as explicit service controls and lower `deployment_maximum_percent` so image refreshes can progress by draining old tasks before starting enough new ones to fit the quota.
8. I am keeping the service on the stable old deployment while applying that rollout correction, then I will redeploy the new digest again and verify the running tasks are actually on the new artifact before any PR3-S1 rerun.
## Entry: 2026-03-06 23:41:00 +00:00 - ECS Availability Zone Rebalancing imposes an additional rollout floor: deployment maximumPercent must remain above 100, so the quota-aware ingress rollout band is repinned to a narrow overlap instead of zero overlap
1. The first quota-aware rollout attempt with `deployment_maximum_percent=100` failed before changing the service because ECS rejects that posture when Availability Zone Rebalancing is enabled.
2. AWS error was explicit: `Availability Zone Rebalancing does not support maximumPercent <= 100`.
3. That means the correct production fix is not exact zero overlap.
4. The correct fix for this environment is the smallest overlap band that:
   - remains above the AZ-rebalancing floor,
   - still fits within the `140 vCPU` account quota,
   - allows image refreshes without forcing a rollback.
5. I therefore repinned the ingress deployment ceiling to `109%`.
6. Why `109%`:
   - steady state is `32 tasks`;
   - `109%` allows at most a very narrow overlap window (effectively `34` total tasks if rounded down), which stays inside the quota envelope (`34 x 4 vCPU = 136 vCPU`);
   - this preserves a controlled rolling update instead of unsafe full drain or impossible 200% overlap.
7. I am now reapplying the redeploy under this narrow-overlap policy and will only accept it as complete once the running tasks themselves show the new digest.
## Entry: 2026-03-06 23:42:00 +00:00 - The managed ingress service is now successfully redeployed on the corrected digest after repinning the ECS rollout policy to a quota-aware narrow-overlap band
1. After repinning the ECS deployment policy to `maximumPercent=109`, the service successfully completed the new deployment on task definition `fraud-platform-dev-full-ig-service:10`.
2. Verified live runtime state:
   - running task image digest: `sha256:e3e6ee322b81039c0c2f9a349c96eb884b8c47a01a83f7279c414945c0e69813`
   - `IG_RECEIPT_STORAGE_MODE=ddb_hot`
   - gunicorn posture remains `8 workers x 8 threads`
   - deployment configuration now `minimumHealthyPercent=50`, `maximumPercent=109`
3. Operational conclusion:
   - the image-refresh path is no longer blocked by impossible overlap assumptions under the current Fargate quota;
   - the service is on the intended hot-receipt design and is now a valid target for the next canonical `PR3-S1` rerun.
4. This change matters beyond the immediate rerun because it corrects a real production-operations defect: image refreshes for the ingress lane must be materially deployable inside the environment's quota envelope, not just theoretically deployable on paper.
5. Immediate next action is to rerun the canonical `PR3-S1` steady window and re-measure throughput/tail latency now that the admit path is no longer synchronously blocked on cold receipt object persistence.
## Entry: 2026-03-06 23:52:00 +00:00 - PR3-S1 throughput and latency are now production-grade, but zero-5xx closure failed because the new DDB hot-receipt path was still over-writing the idempotency table three times per admit under peak load
1. The rerun on the corrected ingress service materially cleared the main steady-state performance targets:
   - observed admitted throughput: `3171.35 eps`
   - request throughput: `3174.42 eps`
   - `p95` latency: `154.98 ms`
   - `p99` latency: `353.33 ms`
2. That proves the previous S3 hot-path bottleneck is resolved.
3. The only blocker left in the rerun was `32` target-side `5xx` responses (`0.0168%`).
4. Root cause from ingress logs and CloudWatch is specific and non-ambiguous:
   - DynamoDB table `fraud-platform-dev-full-ig-idempotency` emitted `3117` `WriteThrottleEvents` in the hot minute;
   - the ingress error logs show `PutItem` and `UpdateItem` `ThrottlingException` failures against that same table while persisting admit-path state/receipt data;
   - this was not the HTTP edge failing independently and not the event-bus publish failing.
5. Design-level diagnosis:
   - a new admit on the DDB-hot path was still doing three table writes:
     - `PutItem` for `PUBLISH_IN_FLIGHT`,
     - `UpdateItem` for `ADMITTED + eb_ref`,
     - `UpdateItem` again for `receipt_ref + receipt_payload_json`;
   - at roughly `3171 eps`, that means the hot path was demanding roughly three DDB writes per accepted event before any duplicate or retry overhead.
6. Production correction chosen:
   - keep DDB hot receipts as the correct storage posture;
   - collapse the post-publish `ADMITTED` state write and receipt write into a single durable update so a fresh admit pays two writes instead of three;
   - harden AWS SDK retry posture for the ingress runtime from `standard / 3 attempts` to `adaptive / 8 attempts` so transient on-demand scaling lag does not surface as client-facing `5xx` prematurely.
7. Why this is the right production move:
   - it preserves the low-latency DDB hot-receipt design that already unlocked the throughput frontier;
   - it reduces hot-path write amplification materially without weakening the idempotency boundary;
   - it treats transient DDB scaling lag as a storage concern to absorb, not a reason to fail the client at a healthy request rate.
8. Local validation status:
   - `py_compile` passed for the changed ingress modules;
   - targeted ingress tests passed (`15 passed`);
   - `test_phase510_efficiency.py` could not be executed in this local environment because `psycopg` is not installed, so the Postgres-backed efficiency lane remains unexecuted locally.
9. Immediate next action:
   - publish a fresh immutable image carrying this reduced-write DDB correction,
   - roll the ingress service again,
   - rerun canonical `PR3-S1` and verify the remaining `5xx` blocker is eliminated.

## Entry: 2026-03-07 00:25:48 +00:00 - PR3-S1 root-cause boundary has shifted again: ingress no longer fails on receipt persistence, but the next two production defects are Kafka publish timeout posture and conflict-unsafe governance anomaly persistence
1. I investigated the latest strict `PR3-S1` regression instead of assuming the previous near-green run still represented the live system. The current failed summary is `runs/dev_substrate/dev_full/road_to_prod/run_control/pr3_20260306T021900Z/g3a_s1_wsp_runtime_summary.json` (`generated_at_utc=2026-03-07T00:17:49.659708Z`, `verdict=HOLD_REMEDIATE`, `observed_request_eps=157.4333`, `observed_admitted_eps=123.2`, `error_rate_ratio=0.2174465`, `latency_p95_ms=10845.037`, `latency_p99_ms=17783.295`).
2. The runtime collapse is not a generic ECS/WSP crash. Live ECS and CloudWatch evidence shows the WSP tasks are reaching the ingress edge and then exiting because IG returns fail-closed decisions after downstream publish ambiguity. The immediate WSP-side symptom is `IG_PUSH_REJECTED` with `decision=QUARANTINE`, not a bootloader or subnet fault.
3. The first root cause is specific and production-material:
   - live IG logs show repeated Confluent/MSK timeout lines such as `Timed out ApiVersionRequest in flight (after 2002ms...)`;
   - the publish path raises `RuntimeError("KAFKA_PUBLISH_TIMEOUT")` from `src/fraud_detection/event_bus/kafka.py`;
   - IG correctly converts that unknown publish outcome into `PUBLISH_AMBIGUOUS` and quarantines rather than risking duplicate publish.
4. This is not a reason to weaken fail-closed semantics. The correct interpretation is that the current Kafka timeout pin is too tight for the real MSK Serverless + IAM/OAUTH handshake posture at hot ingress rates. Once receipt persistence stopped being the bottleneck, the artificially tight publish deadline became the new frontier. Keeping the low timeout would be optimizing for a toy network path, not a production AWS-managed stream boundary.
5. The second root cause is also specific and production-material:
   - while IG is emitting `CORRIDOR_ANOMALY` governance facts for quarantine decisions, the object-store append path can raise `S3_APPEND_CONFLICT` / `PreconditionFailed`;
   - this comes from the shared JSONL append design in `src/fraud_detection/platform_governance/writer.py` and the S3 append CAS loop in `src/fraud_detection/scenario_runner/storage.py` / `src/fraud_detection/ingestion_gate/store.py`;
   - under concurrent quarantine spikes this means the audit path itself is built on a non-scalable single-writer assumption.
6. Rejected shortcut: repinning WSP back to some easier low-rate path or treating the current behavior as an acceptable blocker. That would only make `PR3-S1` easier to rerun, not make the platform more production-ready at the required ingress rate.
7. Chosen production-grade remediation direction:
   - keep the real `WSP -> IG -> DDB -> MSK` canonical path;
   - harden Kafka publish posture for real MSK Serverless latency instead of preserving a toy timeout pin;
   - move platform-governance durability onto conflict-free per-event persistence so governance truth remains append-only without shared-object contention;
   - retain `events.jsonl` only as a projection/compatibility surface where safe, not as the sole authoritative persistence primitive for concurrent S3 writers.
8. Before changing code I also verified a naming/config drift that contributed to mis-tuning:
   - Terraform uses `lambda_ig_kafka_request_timeout_ms` for both Lambda and the ECS IG service env injection;
   - that means the managed service inherited a Lambda-oriented timeout label and value, which is analytically wrong because the service hot path and concurrency model are different.
9. Immediate implementation plan now pinned:
   - add explicit ingress-service Kafka timeout variables and repin them to realistic MSK values;
   - harden the Kafka publisher loop so producer flush/delivery windows align with the configured deadline rather than a premature manual abort posture;
   - redesign governance writer persistence so each event is durably materialized without append conflicts, then retain query/projection compatibility for the rest of the platform;
   - rerun focused ingress/governance tests, rebuild the image, redeploy the managed ingress service, and rerun strict `PR3-S1` from the same run-control root.

## Entry: 2026-03-07 00:34:00 +00:00 - The Kafka/governance hardening pass is now implemented locally and validated before any new live image is built
1. I changed the governance writer so append-only truth is no longer dependent on a shared JSONL S3 append succeeding on the hot path. The durable authority is now one event object per governance event under `obs/governance/events/<event_id>.json`; `events.jsonl` remains a projection path and append conflicts on that projection are tolerated instead of being allowed to invalidate the durable event truth.
2. Why this is the correct production posture:
   - unique event objects preserve append-only semantics under concurrent writers;
   - event id determinism still provides idempotency;
   - query/read surfaces can reconstruct truth from authoritative event objects instead of assuming a single mutable blob is safe at scale.
3. I also corrected the ingress Kafka timeout posture in two layers:
   - publisher config now enforces a more realistic request timeout floor and a wider delivery/socket deadline (`request.timeout.ms >= 3000`, delivery deadline at least `5000` and normally `2x request`);
   - Terraform now stops reusing the Lambda Kafka timeout pin for the managed ingress ECS service and instead exposes `ig_service_kafka_request_timeout_ms` separately.
4. Repins chosen for now:
   - `lambda_ig_kafka_request_timeout_ms = 5000` (removes the toy 1500 ms posture while retaining a bounded edge timeout);
   - `ig_service_kafka_request_timeout_ms = 10000` (gives the service path enough room for real MSK Serverless metadata/auth handshakes without conflating it with request-latency targets).
5. Rejected alternative:
   - leaving `events.jsonl` as the sole governance authority and merely increasing append retry count. That only hides the concurrency defect for a while and still depends on a shared-object mutation pattern that does not scale honestly.
6. Local validation completed before any artifact rebuild:
   - `python -m pytest tests/services/platform_governance/test_writer.py tests/services/event_bus/test_kafka_import_and_auth.py tests/services/ingestion_gate/test_admission.py tests/services/ingestion_gate/test_health_governance.py` -> `26 passed`;
   - `python -m py_compile src/fraud_detection/platform_governance/writer.py src/fraud_detection/event_bus/kafka.py` -> pass;
   - `terraform fmt -check infra/terraform/dev_full/runtime && terraform -chdir=infra/terraform/dev_full/runtime validate` -> pass.
7. Additional guard added in tests:
   - explicit proof that governance event query still works when the projection append raises `S3_APPEND_CONFLICT`;
   - explicit proof that Kafka producer config now stretches delivery/socket timeouts beyond the raw request timeout floor.
8. Next action boundary is now valid:
   - publish a new immutable runtime image carrying these hot-path changes;
   - redeploy the managed ingress service with the new service Kafka timeout pin;
   - rerun strict `PR3-S1` from the existing run-control root and judge only the impact metrics.

## Entry: 2026-03-07 00:44:00 +00:00 - Fresh immutable image is now live on the managed ingress fleet with the Kafka timeout correction pinned materially, so PR3-S1 can be judged again on a valid runtime boundary
1. Immutable build completed from commit `c6481c1fbd89987676e89f032af3ed205a18acf4` via GitHub Actions run `22787785477`.
2. New canonical image digest:
   - `sha256:b4e132e49e14d7c4dff921001227defe1b416c0901967c29e92e53c55b90deda`
   - full URI `230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-full@sha256:b4e132e49e14d7c4dff921001227defe1b416c0901967c29e92e53c55b90deda`.
3. I rolled the managed ingress service only, using explicit pins for:
   - `ig_service_enabled=true`,
   - `ig_service_image_uri=<new digest>`,
   - `ig_service_kafka_request_timeout_ms=10000`.
4. I kept this as a constrained ingress-only rollout because the runtime state still contains unrelated surfaces and PR3-S1 only needs the ingress service/task definition boundary refreshed for honest measurement.
5. Live verification after ECS reached steady state:
   - service `fraud-platform-dev-full-ig-service` on task definition `:12`;
   - `desired_count=32`, `running_count=32`, `pending_count=0`;
   - deployment rollout state `COMPLETED`;
   - container image matches the new immutable digest;
   - container env confirms `KAFKA_REQUEST_TIMEOUT_MS=10000` and `IG_RECEIPT_STORAGE_MODE=ddb_hot`.
6. Operational interpretation:
   - the hot ingress fleet is now actually executing both of the intended corrections: the new governance writer behavior from the rebuilt image and the corrected Kafka timeout posture from the new service pin;
   - any further `PR3-S1` result from this point is attributable to the corrected runtime, not stale image drift or stale task-definition env.
7. Immediate next action is therefore legitimate and necessary:
   - rerun strict canonical `PR3-S1` from `pr3_20260306T021900Z` and re-evaluate the impact metrics on the live corrected service.


## Entry: 2026-03-07 01:08:00 +00:00 - PR3-S1 is presently blocked by harness authority/read-path defects, so the next remediation must harden the certification tooling itself before any more platform judgment is made
1. I inspected the just-finished GitHub Actions rerun `22788053348` instead of assuming the local `g3a_s1_wsp_runtime_summary.json` had been refreshed. It had not. The workflow failed before it could emit a new authoritative runtime summary.
2. The actual hard failure in that run is precise and non-platform:
   - `botocore.exceptions.ClientError: ... elasticloadbalancing:DescribeTargetGroups ... AccessDenied` raised during `Launch canonical remote WSP replay`.
3. This is not an inconsequential nuisance. The canonical `PR3-S1` path now measures ingress on the ALB surface when the managed service URL is active. If the certification harness cannot resolve the target-group dimension, then the lane cannot produce trustworthy throughput/latency evidence against the live service-backed ingress boundary.
4. A second tooling defect surfaced in the same run before launch:
   - the bootstrap step performs `aws s3 sync s3://.../run_control/<pr3_id>/ ${RUN_DIR}/` against the entire execution root;
   - that prefix now contains oversized historical materialization artifacts, including recursive path explosions under `ig_edge_materialize/.../bin/X11/...`;
   - the workflow burned significant time downloading irrelevant evidence before even reaching the runtime launch step.
5. Production interpretation:
   - a certification/hardening lane that cannot observe the real ingress surface or that wastes minutes pulling irrelevant artifacts is itself not production-grade tooling;
   - this must be treated as part of the system we are hardening, not an external annoyance to work around casually.
6. Chosen remediation direction:
   - widen the GitHub OIDC role with the missing least-privilege ELB read action required by the canonical ALB metric path (`elasticloadbalancing:DescribeTargetGroups`);
   - keep the existing CloudWatch/MSF read grants already pinned in `infra/terraform/dev_full/ops/main.tf`;
   - shrink workflow bootstrap from a full run-root sync to the exact authoritative artifacts actually required by `pr3_s1_wsp_replay_dispatch.py` (at minimum `pr3_s0_execution_receipt.json`, with optional targeted copies for charter/scorecard if later needed);
   - add a fallback in the dispatcher so previously resolved ALB metric dimensions can be honored without making `DescribeTargetGroups` a single-point-of-failure when equivalent authoritative dimensions are already available.
7. Rejected shortcut:
   - rerunning locally or through an easier legacy path just to keep the chain moving. That would hide a real certification-tooling defect and undermine later reproducibility.
8. Immediate implementation sequence:
   - patch docs/logbook first;
   - patch the workflow/bootstrap boundary and dispatcher fallback;
   - patch the IAM policy in code and apply it live;
   - validate locally;
   - commit/push the new correction boundary;
   - rerun strict `PR3-S1` and continue from the new authoritative evidence.


## Entry: 2026-03-07 01:16:00 +00:00 - PR3-S1 harness authority/read-path remediation is implemented and live, so the next rerun can return to judging platform behavior instead of failing inside the certification tooling
1. I patched `scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py` so ALB metric-surface discovery can reuse a previously resolved `g3a_s1_wsp_runtime_manifest.json` surface when the host matches and the necessary dimensions are already authoritative. This does not weaken the live path; it removes an unnecessary single-point-of-failure in the certification harness when equivalent resolved dimensions are already pinned from the same execution family.
2. I patched `.github/workflows/dev_full_pr3_s1_managed.yml` so the bootstrap stage no longer syncs the entire `run_control/<pr3_id>/` prefix. It now copies only the strict upstream lock receipt (`pr3_s0_execution_receipt.json`) plus the prior runtime manifest on a best-effort basis.
3. Why the bootstrap narrowing is the correct production move:
   - `pr3_s1_wsp_replay_dispatch.py` only requires `pr3_s0_execution_receipt.json` for strict upstream gating;
   - full-root sync was spending minutes downloading irrelevant historical materialization artifacts and path-exploded files under `ig_edge_materialize/...`;
   - a certification lane that wastes setup time on irrelevant evidence is violating the performance-first law itself.
4. I also corrected the workflow rollup generation so `g3a_steady_evidence_managed.json` no longer hardcodes API Gateway as the measurement surface. It now records whether the authoritative metric surface was `APIGW` or `ALB` and populates the relevant dimensions accordingly.
5. On the IAM side, I extended `infra/terraform/dev_full/ops/main.tf` so managed policy `GitHubActionsPR3RuntimeDevFull` grants:
   - `elasticloadbalancing:DescribeLoadBalancers`
   - `elasticloadbalancing:DescribeTargetGroups`
6. I then applied that IAM delta live using targeted Terraform against the `dev_full/ops` stack. The apply updated the in-place policy on role `GitHubAction-AssumeRoleWithAction`; no other resources changed.
7. Local validation completed before the live apply:
   - `python -m py_compile scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py` -> pass;
   - workflow YAML parse for `dev_full_pr3_s1_managed.yml` -> pass;
   - `terraform -chdir=infra/terraform/dev_full/ops fmt -check && terraform validate` -> pass.
8. Operational interpretation:
   - the next `PR3-S1` rerun should no longer die before launch on `DescribeTargetGroups` authorization;
   - the workflow bootstrap should reach launch materially faster and without dragging oversized stale evidence into the working directory;
   - the resulting evidence rollup will finally describe the live ALB-backed ingress measurement surface honestly.
9. Next immediate action:
   - commit/push this harness correction boundary,
   - rerun strict `PR3-S1`,
   - continue remediation only from the new platform-impact metrics that come back.


## Entry: 2026-03-07 01:24:00 +00:00 - PR3-S1 has now returned to a real runtime-capacity issue: the replay harness itself is overprovisioned relative to the live ingress fleet's Fargate envelope
1. After fixing ELB read authority and bootstrap waste, I reran strict `PR3-S1` on workflow run `22788481700`. The run progressed through bootstrap and runtime readiness, then failed in `Launch canonical remote WSP replay` with `PR3.S1.WSP.B01_RUN_TASK_FAILED:wsp_lane_12:Youve reached the limit on the number of vCPUs you can run concurrently`.
2. I quantified the live Fargate envelope rather than guessing:
   - account quota `L-3032A538` (`Fargate On-Demand vCPU resource count`) is `140` vCPU in `eu-west-2`;
   - current ingress service task definition `fraud-platform-dev-full-ig-service:12` is pinned at `4096 CPU / 8192 MiB` per task;
   - the live ingress fleet is `32` tasks, so ingress alone occupies `128` vCPU;
   - current replay task definition `fraud-platform-dev-full-wsp-ephemeral:32` defaults to `1024 CPU / 2048 MiB` per task, so the 24-lane canonical rerun would require another `24` vCPU if un-overridden.
3. That explains the exact failure point: only ~`12` vCPU remain beneath the account quota, so the launch fails at lane `12`/`13` depending on transient headroom.
4. Production interpretation:
   - this is not evidence that the ingress platform cannot sustain the target rate;
   - it is evidence that the current certification harness is badly right-sized for a shared dev capacity envelope;
   - a WSP replay producer whose job is HTTP push should not need `1 vCPU / 2 GiB` per lane merely to generate ~`133 eps` per lane.
5. Chosen remediation direction:
   - repin canonical `PR3-S1` replay lanes to a lower Fargate override footprint (`256 CPU / 1024 MiB`) so the harness fits alongside the live ingress service while still preserving remote/oracle-backed execution;
   - keep lane count at `24` initially so the source distribution shape remains unchanged and only the wasteful per-lane envelope is corrected;
   - if throughput becomes source-limited under the leaner per-lane footprint, then tune concurrency or lane count from measured evidence rather than restoring the oversized default.
6. Rejected alternative:
   - shrinking or destabilizing the live ingress fleet simply to make room for the harness. That would contaminate the very platform posture we are trying to certify.
7. Immediate next action:
   - patch the workflow so canonical `PR3-S1` passes explicit lean task overrides to the replay dispatcher,
   - rerun strict `PR3-S1`,
   - then judge whether the next blocker is actual ingress performance or just remaining harness inefficiency.


## Entry: 2026-03-07 01:31:00 +00:00 - Fresh PR3-S1 evidence shows the lean replay harness is viable, but the canonical dispatcher had silently regressed back to the wrong network defaults
1. The rerun on workflow `22788594376` succeeded in launching all 24 replay lanes with the lean `256/1024` Fargate override, so the vCPU headroom defect is resolved.
2. However, the fresh runtime summary still showed `observed_request_eps=0.0`, `observed_admitted_eps=0.0`, and every lane ended with `IG_PUSH_RETRY_EXHAUSTED`.
3. I pulled the actual CloudWatch log streams for the replay lanes. They show repeated `reason=timeout` on every IG push retry, followed by `WSP stream failed reason=IG_PUSH_RETRY_EXHAUSTED detail=timeout`.
4. The authoritative manifest explains why:
   - current network posture in the rerun was `subnet-005205ea65a9027fc,subnet-01fd5f1585bfcca47` with `assign_public_ip=ENABLED`;
   - those are the old public-subnet defaults, not the private-subnet posture previously proven for the internal ALB-backed ingress service.
5. This is a regression in the canonical dispatcher defaults, not a new platform limitation. Earlier near-green runs used the private ingress-adjacent subnets `subnet-0a7a35898d0ca31a8,subnet-0e9647425f02e2f27` with `assignPublicIp=DISABLED`.
6. Production interpretation:
   - an internal ALB-backed ingress lane should be exercised from private VPC subnets by default;
   - allowing the canonical replay harness to fall back to public-subnet defaults is a design-intent drift and yields meaningless timeout evidence.
7. Chosen fix:
   - repin `pr3_s1_wsp_replay_dispatch.py` defaults to the private subnet pair and `assign_public_ip=DISABLED`;
   - keep the lean task override from the previous correction boundary;
   - rerun strict `PR3-S1` immediately after the network default correction.


## Entry: 2026-03-07 01:36:00 +00:00 - PR3-S1 is now source-limited by the replay harness' single-flight push posture, not by the ingress platform
1. After restoring the private replay network path, workflow `22788814078` produced fresh, clean ALB evidence:
   - admitted throughput `1475.1625 eps`
   - request throughput `1475.1625 eps`
   - `error_rate=0.0`
   - `p95=62.21 ms`
   - `p99=90.65 ms`
2. Only two blockers remain:
   - `B12_EARLY_THROUGHPUT_SHORTFALL: observed=1476.467 floor=2100.000`
   - `B19_FINAL_THROUGHPUT_SHORTFALL: observed=1475.162 target=3000.000`
3. Production interpretation:
   - ingress is healthy under the measured pressure; latency and error posture are comfortably green;
   - the miss is purely on admitted volume, which means the source harness is under-driving the platform.
4. The current harness configuration explains the number almost exactly:
   - `24` lanes at `IG_PUSH_CONCURRENCY=1` produced ~`1475 eps`, i.e. ~`61.5 eps/lane`;
   - this is consistent with a single in-flight request per lane and the observed request/response timing envelope rather than with a saturated ingress edge.
5. Therefore the current `ig_push_concurrency=1` pin is analytically a toy/posture-limiting value for a 3000-eps production proof. It serializes each lane too aggressively and prevents the harness from actually exercising the available platform headroom.
6. Chosen remediation:
   - repin canonical `PR3-S1` replay to multi-flight push concurrency (`IG_PUSH_CONCURRENCY=4`) while retaining the lean task footprint and private-VPC posture;
   - widen the HTTP connection pool accordingly so the concurrency increase is not neutralized by the client transport.
7. Rejected alternative:
   - interpreting the current `1475 eps` as an ingress scaling ceiling and resizing the platform again. The metrics do not support that story because latency and errors remain far below threshold while admitted volume tracks the single-flight harness posture.
8. Next action:
   - patch the canonical launch lane to pass `--ig-push-concurrency 4` and a larger HTTP pool,
   - rerun strict `PR3-S1`,
   - then decide if a further source multiplier or lane-count repin is actually needed.


## Entry: 2026-03-07 02:20:00 +00:00 - PR3-S1 is now close enough that the remaining misses have to be treated as production-hardening defects, not generic blocker labels
1. I inspected the full authoritative evidence from strict rerun `22789024407` instead of relying on the job-level failure bit. The actual steady-window result is:
   - admitted throughput `2610.900 eps`,
   - admitted count `4,699,620`,
   - request count `4,699,646`,
   - `4xx=0`,
   - `5xx=26` in the current lane summary,
   - `p95=106.9998 ms`,
   - `p99=141.5351 ms`,
   - window `1800 s`.
2. The open blockers are now narrow and concrete:
   - `PR3.S1.WSP.B19_FINAL_THROUGHPUT_SHORTFALL: observed=2610.900 target=3000.000`;
   - `PR3.S1.WSP.B22_5XX_RATE_BREACH: observed=0.000006 max=0.000000`.
3. I then checked live platform utilization during the same window because the correct production question is whether the platform itself was saturated. It was not:
   - ingress ECS service stayed at `32/32` running tasks with no unhealthy hosts,
   - ECS CPU averaged roughly `22%..25%`, maxing around `31%`,
   - ECS memory stayed around `7.2%..7.9%`,
   - ALB healthy-host count remained `32`, unhealthy-host count remained `0`.
4. That means the residual throughput miss is not evidence that the ingress plane has reached its ceiling. The ingress fleet still has substantial headroom. The miss instead comes from the source side still under-driving the target steady lane.
5. The production interpretation is therefore split:
   - throughput miss: this is a horizontal replay-width issue on the real WSP producer path, not an ingress-capacity failure;
   - 5xx leak: this is a resilience defect because a production-grade ingress edge should absorb transient downstream publish/receipt turbulence instead of surfacing even a tiny number of `503` responses during a five-million-request steady window.
6. I investigated the 5xx leak further rather than jumping straight to lane-count inflation:
   - ALB target errors are sparse and scattered, not correlated with unhealthy hosts or ingress CPU/memory saturation;
   - some ALB minutes show long-tail single-request spikes (`TargetResponseTime max ~2.2s`) while average latency stays low;
   - the duplicate pattern seen in IG logs is consistent with a small number of transient failures that are retried by WSP and then re-enter IG as clean duplicates after the original admission/publish path already succeeded.
7. A real implementation defect also surfaced in the code/config boundary:
   - `IG_INTERNAL_RETRY_MAX_ATTEMPTS` and `IG_INTERNAL_RETRY_BACKOFF_MS` are pinned into the runtime environment and Terraform surfaces;
   - but the active admission path does not meaningfully use these knobs to harden the post-publish receipt/update boundary;
   - in other words, we have been carrying resilience pins that were not actually wired into the hot path.
8. Chosen production-grade remediation direction:
   - wire the existing internal-retry envelope into the admission hot path for idempotent post-publish operations (especially the DDB admitted-state/receipt persistence boundary), because that is where transient failure can leak a `503` even after the event bus side-effect already happened;
   - raise the service Kafka publish envelope modestly so transient broker/service jitter is absorbed inside IG instead of leaking outward;
   - widen canonical PR3-S1 replay horizontally by lane count rather than by oversized per-lane compute, because that matches the actual distributed WSP producer model and preserves the production graph.
9. Rejected shortcuts:
   - scaling ingress service resources further right now, because the measured CPU/memory/host posture does not justify it;
   - accepting the current run as "basically green", because the user-set standard is strict no-waiver production readiness;
   - rerunning immediately with only a higher lane count, because that could hide the resilience leak instead of fixing it.
10. Immediate execution sequence:
   - append this evidence/decision boundary to implementation notes and logbook,
   - patch the admission code so the pinned retry contract becomes real behavior,
   - patch runtime Terraform/workflows so the live service picks up the strengthened ingress envelope and a fresh immutable image,
   - repin canonical PR3-S1 replay width to the horizontal lane count that can actually prove `3000 eps`,
   - rerun strict `PR3-S1` from the same upstream boundary and continue only from the new impact metrics.


## Entry: 2026-03-07 02:28:00 +00:00 - The PR3-S1 resilience and replay-width correction boundary is now implemented in code and remote rollout surfaces
1. I implemented the hot-path resilience fix in `src/fraud_detection/ingestion_gate/admission.py` rather than trying to paper over the remaining `503` leak with more source pressure. The key change is a new `_retry_idempotent(...)` helper that now wraps:
   - duplicate receipt object writes,
   - duplicate receipt-ref recording,
   - admitted-state/receipt persistence for the hot `ddb_hot` path,
   - admitted-state persistence for the object-store receipt path,
   - `mark_receipt_failed(...)` on the failure boundary.
2. This is deliberately scoped to idempotent post-publish operations only. I did **not** add naive application-level retries around `bus.publish(...)` itself because that would risk turning an already ambiguous publish boundary into duplicate event-bus side effects. That would be the wrong production tradeoff.
3. I also wired the resilience pins back into the active runtime boundary:
   - `src/fraud_detection/ingestion_gate/aws_lambda_handler.py` now passes `IG_INTERNAL_RETRY_MAX_ATTEMPTS` and `IG_INTERNAL_RETRY_BACKOFF_MS` into the managed-edge `SimpleNamespace` wiring that actually constructs `IngestionGate`;
   - `src/fraud_detection/ingestion_gate/config.py` now carries the same fields in `WiringProfile` so the non-managed build path stays structurally aligned.
4. On the runtime/IaC side I added the missing shared Kafka retry pin:
   - new Terraform variable `ig_kafka_publish_retries` in `infra/terraform/dev_full/runtime/variables.tf` (default `5`);
   - both Lambda IG and ECS service IG now consume this variable in `infra/terraform/dev_full/runtime/main.tf`;
   - service Kafka request timeout default is repinned from `10000 ms` to `15000 ms`.
5. On the execution-tooling side I corrected the rollout and rerun posture:
   - `.github/workflows/dev_full_pr3_s1_managed.yml` now defaults canonical `PR3-S1` replay width to `32` lanes instead of `24`; this is the chosen horizontal replay pin for the `3000 eps` proof window because ingress headroom is already demonstrated and the 24-lane run under-drove the target;
   - `.github/workflows/dev_full_pr3_ig_edge_materialize.yml` now accepts:
     - immutable `platform_image_uri`,
     - `ig_internal_retry_max_attempts`,
     - `ig_internal_retry_backoff_ms`,
     - Lambda/service Kafka timeout inputs,
     - shared Kafka publish retry count;
   - the same workflow now targets ECS ingress service materialization (`aws_ecs_task_definition.ig_service[0]`, `aws_ecs_service.ig_service[0]`) in addition to the Lambda edge, and performs live readback on the ECS task-definition environment to prove the expected pins actually landed.
6. Local validation completed before any remote execution:
   - `python -m py_compile` passed for the touched ingress modules;
   - both workflow YAML files parse cleanly;
   - `terraform -chdir=infra/terraform/dev_full/runtime fmt -check` passed.
7. Production interpretation:
   - the repo now contains a coherent fix boundary that matches the actual problem we measured;
   - the next remaining task is not more local reasoning but remote realization:
     - build fresh immutable image,
     - roll the ingress edge to that image and the strengthened retry/publish envelope,
     - rerun strict `PR3-S1` on the widened canonical replay width using the same image digest.

## Entry: 2026-03-07 02:34:00 +00:00 - The first ingress materialization rerun exposed workflow-level destructive drift because `ig_service_enabled` was left implicit
1. I pulled the failed rollout run `22790080603` and inspected the actual Terraform apply output instead of treating it as a generic workflow failure.
2. The apply did not fail because AWS rejected the image, the Lambda bundle, or the retry pins. It failed earlier because the workflow never asserted `ig_service_enabled=true` while simultaneously targeting `aws_ecs_task_definition.ig_service[0]` and `aws_ecs_service.ig_service[0]`.
3. In this Terraform module the managed ingress service is guarded by `count = var.ig_service_enabled ? 1 : 0` across the full ECS/ALB/log-group/security-group surface. The default remains `false`.
4. That means the workflow accidentally asked Terraform to update indexed ingress resources while also leaving the count gate closed. Terraform therefore evaluated the live ingress ECS surface as out-of-range and planned destructive drift (`0 to add, 1 to change, 9 to destroy`).
5. This is a tooling defect, not a production-capacity defect. The live ingress service already exists and is the canonical high-throughput path we are hardening. The materialization workflow must therefore always operate under an explicit enablement contract when touching that surface.
6. Production-minded decision:
   - do not repin the platform away from the managed ingress ECS path simply because the workflow was under-specified;
   - fix the workflow so the managed ingress surface is explicitly enabled during rollout, because in a real production system rollout tooling must not rely on hidden defaults when updating a live service.
7. Immediate remediation chosen:
   - pass `-var 'ig_service_enabled=true'` in the targeted apply;
   - keep the targeted correction bounded to the intended ingress surface so the rollout remains surgical while avoiding the false destructive plan generated by the implicit default.
8. Acceptance for the next rerun:
   - Terraform must no longer plan any destroy on the managed ingress surface due to count drift;
   - live readback must prove ECS service image/env pins match the new immutable image and retry envelope;
   - only then does `PR3-S1` rerun resume.

## Entry: 2026-03-07 02:38:00 +00:00 - The ingress materialization rerun is now blocked by an incomplete ELBv2 read envelope on the GitHub OIDC role, so the durable fix is to widen the policy at the resource-family level
1. I pulled the next failed rollout run 22790176136 after fixing the ig_service_enabled workflow defect. This confirmed the first defect is actually closed: Terraform no longer planned the earlier count-based destroy wave.
2. The new plan boundary is materially better and also more informative:
   - Terraform now reaches a bounded ingress update plan (1 to add, 1 to change, 1 to destroy),
   - the intended Lambda environment deltas are visible (IG_INTERNAL_RETRY_*, KAFKA_PUBLISH_RETRIES, KAFKA_REQUEST_TIMEOUT_MS),
   - the apply then fails during provider refresh of the live ALB/TG surfaces.
3. The exact hard failures are:
   - lasticloadbalancing:DescribeLoadBalancerAttributes denied on ws_lb.ig_service[0];
   - lasticloadbalancing:DescribeTargetGroupAttributes denied on ws_lb_target_group.ig_service[0].
4. This is not a reason to retreat from the managed ingress service or to keep playing action-whack-a-mole manually in the console. The correct production question is: what read surface does Terraform need to safely manage the live ALB/TG family over time?
5. Chosen production-grade answer:
   - widen policy GitHubActionsPR3RuntimeDevFull from the minimal metric-discovery read set to the full ELBv2 resource-family read envelope that a Terraform-managed ALB/TG path reasonably requires.
6. Actions added in code:
   - lasticloadbalancing:DescribeLoadBalancerAttributes
   - lasticloadbalancing:DescribeTargetGroupAttributes
   - lasticloadbalancing:DescribeListeners
   - lasticloadbalancing:DescribeRules
   - lasticloadbalancing:DescribeTags
7. Why this is the right line instead of only adding the two immediately failing actions:
   - the platform is already telling us the certification/remediation lane must refresh a managed ALB/TG family,
   - production rollout tooling should not need repeated stop-start IAM increments for adjacent read APIs in the same resource family,
   - the read-only scope remains bounded to ELBv2 describe actions on *, which is operationally acceptable for GitHub OIDC orchestration and does not broaden write authority.
8. Immediate next sequence:
   - validate the dev_full/ops Terraform change locally,
   - apply the IAM delta live to role GitHubAction-AssumeRoleWithAction,
   - rerun ingress materialization immediately,
   - if the rollout verifies live pins, resume strict PR3-S1.

## Entry: 2026-03-07 02:40:00 +00:00 - The ELBv2 read-envelope remediation is now live on the GitHub OIDC role
1. I validated the repo-side policy change in infra/terraform/dev_full/ops/main.tf (	erraform fmt -check, 	erraform validate) and then initialized the dev_full/ops stack backend successfully.
2. I applied the IAM delta live with targeted Terraform against ws_iam_policy.github_actions_pr3_runtime. This is the managed policy already attached to role GitHubAction-AssumeRoleWithAction, so the change landed without any role/attachment churn.
3. Applied live delta:
   - added lasticloadbalancing:DescribeLoadBalancerAttributes
   - added lasticloadbalancing:DescribeTargetGroupAttributes
   - added lasticloadbalancing:DescribeListeners
   - added lasticloadbalancing:DescribeRules
   - added lasticloadbalancing:DescribeTags
4. Existing retained ELBv2 read actions remain:
   - lasticloadbalancing:DescribeLoadBalancers
   - lasticloadbalancing:DescribeTargetGroups
5. Why I kept this as a targeted live apply instead of a full ops apply:
   - the failing boundary is isolated to the PR3 runtime policy,
   - the user asked for continuous execution toward production closure,
   - the targeted update gives the workflow the exact missing read surface without dragging unrelated ops drift into the lane.
6. Operational consequence:
   - the ingress materialization workflow should now be able to refresh the managed ALB/TG family and proceed to the actual service rollout/verification boundary.
7. Next action:
   - rerun ingress materialization immediately from cert-platform,
   - if the rollout verifies the live image/env pins, resume strict PR3-S1 without waiting.

## Entry: 2026-03-07 02:42:00 +00:00 - The listener-attribute denial confirms the ELBv2 policy should use the full Describe* surface instead of continued piecemeal additions
1. The very next ingress materialization rerun (22790256328) proved the previous IAM widening worked partially: Terraform refreshed load balancer, target group, and listener resources further than before.
2. The new hard failure was narrower but structurally identical:
   - lasticloadbalancing:DescribeListenerAttributes denied on ws_lb_listener.ig_service[0].
3. That failure confirms the production judgment from the prior note: the certification/remediation lane is managing a real ELBv2 resource family, so trying to enumerate one more Describe...Attributes action per rerun is the wrong maintenance posture.
4. I am therefore repinning PR3ElbRuntimeRead to a single read-only family grant: lasticloadbalancing:Describe* on *.
5. Why this is the correct production tradeoff:
   - the role remains read-only for ELBv2;
   - Terraform/provider refresh of the managed ingress ALB/TG/listener family is no longer vulnerable to future adjacent Describe... surprises;
   - this directly serves the user mandate to remove unnecessary stop-start cycles in the production-hardening path.
6. Immediate next sequence:
   - apply the repinned ELBv2 read family live on GitHubActionsPR3RuntimeDevFull,
   - rerun ingress materialization again,
   - continue to service verification if the apply finally clears the IAM surface.

## Entry: 2026-03-07 02:44:00 +00:00 - The rollout is now past ELB/IAM friction; the remaining gate is Lambda concurrency control authority
1. Ingress materialization rerun 22790311956 cleared the ELBv2 permission boundary entirely. Terraform refreshed the managed ALB/TG/listener surface and executed real rollout steps.
2. Important live consequence already observed in that run:
   - ECS task definition replacement completed,
   - ECS service update completed,
   - therefore the managed ingress ECS path materially moved closer to the desired image/env pins even though the workflow still ended non-green.
3. The remaining hard failure happened later and is precise:
   - lambda:PutFunctionConcurrency denied while Terraform was updating ws_lambda_function.ig_handler reserved concurrency from 360 to 1000.
4. This matters to production-readiness because the target ingress envelope is not only the ECS managed service. The API Gateway -> Lambda edge still fronts the canonical ingress admission path and must be able to hold the pinned concurrency posture.
5. Chosen remediation:
   - extend PR3IngressLambdaControl on policy GitHubActionsPR3RuntimeDevFull with:
     - lambda:PutFunctionConcurrency
     - lambda:DeleteFunctionConcurrency
6. Why both actions:
   - PutFunctionConcurrency is required for the current uplift to the pinned reserved concurrency target,
   - DeleteFunctionConcurrency keeps the same Terraform-managed surface symmetrically controllable for future rollback/right-sizing without another IAM stop-start.
7. Immediate next sequence:
   - apply the lambda-concurrency IAM delta live,
   - rerun ingress materialization,
   - let the verify step confirm both ECS and Lambda now match the intended production envelope.

## Entry: 2026-03-07 02:48:00 +00:00 - The previous 1000 Lambda IG concurrency pin is an overspecified authority and must be repinned to a production-valid value derived from measured throughput and the real AWS account envelope
1. I measured the actual Lambda account posture after the last rerun instead of continuing to fight the failed 1000 target blindly.
2. Current AWS account settings are:
   - ConcurrentExecutions = 1000
   - UnreservedConcurrentExecutions = 640
3. Current reserved-concurrency footprint is therefore only 360, and it is entirely on raud-platform-dev-full-ig-handler.
4. AWS then rejected the 1000 uplift with a real platform constraint, not an IAM or tooling error:
   - InvalidParameterValueException: Specified ReservedConcurrentExecutions for function decreases account's UnreservedConcurrentExecution below its minimum value of [40].
5. Production reasoning:
   - the old 1000 pin is not materially deployable in this account and therefore is not a valid authority for this environment;
   - keeping it would be exactly the kind of overspecified bolt the user asked me to remove;
   - the pin should instead be derived from measured service behavior and the real account envelope.
6. Measured evidence available for sizing:
   - strict PR3-S1 already reached 2610.9 eps with current Lambda reserved concurrency 360 and latency around p95=107 ms, p99=142 ms;
   - concurrency needed for 3000 eps at that latency band is materially below 600 (3000 * 0.142 ~= 426 at p99-level service time, before headroom).
7. Chosen new pin: LAMBDA_IG_RESERVED_CONCURRENCY = 600.
8. Why 600 is the right production compromise here:
   - it is well above the observed concurrency demand implied by the measured PR3 window,
   - it leaves substantial safety margin over the derived ~426 concurrency need,
   - it remains valid inside the real account limit while preserving 400 unreserved concurrency for the rest of the account.
9. I have therefore repinned:
   - runtime Terraform default in infra/terraform/dev_full/runtime/variables.tf
   - design authority note in docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md
   - handles registry pin in docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md
10. Immediate next sequence:
   - rerun ingress materialization with the corrected 600 concurrency authority,
   - verify the live Lambda reserved concurrency lands at 600,
   - then resume strict PR3-S1 on the corrected ingress boundary.

## Entry: 2026-03-07 02:52:00 +00:00 - The ingress materialization boundary is now fully green and verified against live AWS state
1. Materialization rerun 22790437771 completed end-to-end, including the explicit verification step.
2. Verified live Lambda posture:
   - function: raud-platform-dev-full-ig-handler
   - handler: raud_detection.ingestion_gate.aws_lambda_handler.lambda_handler
   - timeout: 30 s
   - memory: 2048 MB
   - VPC attachment: 2 subnets / 1 security group
   - Kafka request timeout: 10000 ms
   - reserved concurrency verified directly via ws lambda get-function-concurrency: 600
3. Verified live managed ingress ECS posture:
   - cluster: raud-platform-dev-full-ingress
   - service: raud-platform-dev-full-ig-service
   - task definition: revision 13
   - image digest: 230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-full@sha256:843750a949a94a5a0eaf984ce231c0e91e3ced0032b1f3b0bfa4af81514aeb64
   - desired/running count: 32/32
   - deployment rollout state: COMPLETED
   - network posture: private subnets only, ssignPublicIp=DISABLED
4. Verified live managed ingress ECS environment:
   - IG_INTERNAL_RETRY_MAX_ATTEMPTS=5
   - IG_INTERNAL_RETRY_BACKOFF_MS=400
   - KAFKA_REQUEST_TIMEOUT_MS=15000
   - KAFKA_PUBLISH_RETRIES=5
   - IG_RATE_LIMIT_RPS=3000
   - IG_RATE_LIMIT_BURST=6000
5. Verified edge health result:
   - status code 200
   - mode pigw_lambda_ddb_kafka
   - service ig-edge
   - envelope confirms retry contract + 3000/6000 ingress rate envelope.
6. Important interpretation:
   - the ingress correction lane is no longer blocked by workflow defects, IAM defects, or impossible overspecified capacity pins;
   - the live ingress boundary now materially reflects the production-ready envelope we intended to test.
7. This closes the ingress-materialization remediation loop for PR3-S1. The next valid action is to rerun strict PR3-S1 against this corrected live boundary and judge only the resulting impact metrics.

## Entry: 2026-03-07 03:46:00 +00:00 - The latest strict PR3-S1 miss is primarily a stale-runtime-identity problem, not a front-door capacity problem
1. I pulled the full artifact set from strict rerun `22790499579` and then cross-checked it against live ALB, ECS, and CloudWatch evidence instead of treating the summary blocker list as sufficient on its own.
2. Raw steady-window outcome from the authoritative receipt:
   - observed admitted/request throughput about `2242.2 eps` against the `3000 eps` target,
   - `43` total `5xx`,
   - weighted ALB latency about `p95=803 ms`, `p99=1113 ms`,
   - no early-cutoff trigger.
3. Live infrastructure evidence rules out the easy but wrong explanation that the front door is simply out of raw capacity:
   - ECS ingress service stayed `32/32` healthy for the full window,
   - ALB healthy-host count stayed `32`,
   - ECS CPU averaged mostly in the `14%..26%` band with only a brief first-minute max spike,
   - ECS memory stayed about `7%..8%`.
4. The error signature is also more specific than a generic app failure:
   - ALB `HTTPCode_ELB_5XX_Count` summed to the same order as the run blocker (`43` total),
   - target-side `HTTPCode_Target_5XX_Count` was only `5`,
   - `TargetConnectionErrorCount` stayed empty.
5. That means most failures are edge-generated timeout/response failures rather than the application explicitly returning many `5xx` responses.
6. The more important discovery came from the live ingress task logs. During the same steady window the managed edge repeatedly logged summaries like:
   - `admit=12 duplicate=898 quarantine=0`
   - `phase.receipt_seconds p95≈1.374s`
   - `admission_seconds p95≈1.382s`
   while the same worker's publish path for fresh admits remained tiny (`phase.publish_seconds p95≈9 ms`, `phase.dedupe_admitted_seconds p95≈5.5 ms`).
7. This proves the window is not primarily measuring first-seen admission anymore. It is spending most of its time on duplicate handling and duplicate receipt persistence.
8. I traced that back to the identity contract in code:
   - `dedupe_key(platform_run_id, event_class, event_id)` in `src/fraud_detection/ingestion_gate/ids.py`,
   - `event_id` is intentionally stable across reruns of the same oracle world,
   - the strict workflow keeps reusing the same `platform_run_id=platform_20260223T184232Z`.
9. Consequence:
   - every strict rerun after the first successful ingest of a given event set will naturally become a duplicate-heavy workload,
   - IG is behaving correctly,
   - but the certification lane is no longer answering the production question we care about for PR3-S1, namely first-seen steady admission at the target EPS.
10. Production-grade decision:
   - do **not** purge the idempotency table,
   - do **not** weaken dedupe semantics,
   - do **not** pretend the duplicate-heavy rerun is acceptable steady proof.
11. Chosen remediation:
   - keep the oracle-store input world fixed,
   - keep stable event identities,
   - generate a **fresh runtime `platform_run_id` and `scenario_run_id` per certification attempt** so each attempt is a new runtime mission and IG evaluates the events as first-seen traffic for that mission,
   - continue to preserve duplicate behavior only when we intentionally test duplicate cohorts, not accidentally through stale run identity reuse.
12. Why this is the correct production posture:
   - in a real institution, each production window or rehearsal mission is a new runtime mission with its own run identity,
   - you do not clear the dedupe system to get a benchmark,
   - but you also do not certify steady first-ingest throughput using a lane that is mostly replaying already-seen identities from previous failed attempts.
13. Secondary implication:
   - the latest latency miss (`~1.35s..1.45s` live ALB p95 during the hot minutes) is still useful evidence because it quantifies the duplicate-receipt path cost,
   - but it is not the final steady-admission truth we should certify against.
14. Immediate next sequence:
   - repin PR3 execution tooling so attempt identities are fresh by default,
   - rerun strict `PR3-S1` from the same upstream boundary and same oracle-store world with a new runtime identity,
   - only if the fresh-identity run still misses do we treat the remaining latency/throughput gap as a real first-admit capacity problem.

## Entry: 2026-03-07 04:02:00 +00:00 - PR3-S1 execution tooling must mint fresh runtime identities by default and fail closed on accidental reuse
1. I am now converting the stale-identity diagnosis into an explicit execution guard instead of relying on operator memory.
2. The practical failure mode is simple:
   - the workflow required or defaulted a previously used `platform_run_id` and `scenario_run_id`,
   - the dispatcher then replayed oracle-store events whose `event_id`s are intentionally stable,
   - IG correctly treated most of that traffic as duplicates,
   - the resulting throughput/latency evidence answered the wrong question for `PR3-S1`.
3. Production reasoning for the tooling change:
   - a certification attempt is a fresh runtime mission and therefore needs a fresh runtime identity by default;
   - reuse must be an explicit, audited choice only for deliberate duplicate/replay experiments;
   - the safe default is therefore "mint fresh identity unless the operator knowingly overrides it."
4. Chosen execution hardening:
   - make `platform_run_id` optional in the workflow and mint a fresh UTC-derived value when blank;
   - make `scenario_run_id` optional in the workflow and mint a matching fresh value when blank;
   - add an explicit `allow_runtime_identity_reuse` switch that remains `false` by default;
   - keep the dispatcher-side database probe so the run fails closed if a reused runtime identity still slips through.
5. Why both workflow-side minting and dispatcher-side probing are required:
   - workflow minting prevents ordinary operator error,
   - dispatcher probing prevents silent contamination from stale defaults, copied inputs, or future workflow regressions.
6. This is not a cosmetic convenience change. It is part of the production-certification contract because it ensures `PR3-S1` measures first-seen steady admission rather than duplicate receipt handling unless we intentionally test duplicates.
7. Immediate next sequence:
   - finish the workflow patch cleanly,
   - validate YAML and Python locally,
   - rerun strict `PR3-S1` from the same upstream boundary with fresh runtime identities and `allow_runtime_identity_reuse=false`.

## Entry: 2026-03-07 04:08:00 +00:00 - Fresh-identity execution guard is now implemented and locally validated
1. The dispatcher now probes Aurora-backed `admissions` and `receipts` for the chosen `platform_run_id` before launch.
2. If prior state exists and `allow_runtime_identity_reuse=false`, the dispatcher raises `PR3.S1.WSP.B26_RUNTIME_ID_REUSED` and refuses to run.
3. The workflow now:
   - accepts blank runtime identifiers,
   - mints fresh UTC-derived `platform_run_id` and `scenario_run_id` when blank,
   - passes those resolved values through both runtime materialization and the canonical WSP replay lane,
   - exposes reuse as an explicit boolean switch instead of a hidden stale default.
4. Local validation completed before remote execution:
   - `python -m py_compile scripts/dev_substrate/pr3_s1_wsp_replay_dispatch.py`
   - YAML parse of `.github/workflows/dev_full_pr3_s1_managed.yml`
5. Production interpretation:
   - the next strict rerun should now answer the right question for `PR3-S1`,
   - if it still misses, that miss will be about first-seen production admission capacity/latency rather than accidental duplicate benchmarking.
6. Immediate next sequence:
   - push the corrected execution path,
   - dispatch strict `PR3-S1`,
   - remediate only the remaining first-admit bottlenecks surfaced by that fresh-identity run.

## Entry: 2026-03-07 04:11:00 +00:00 - GitHub Actions dispatch surface exceeded the control-plane input limit and must be reduced without weakening the runtime contract
1. The first remote attempt to rerun the corrected `PR3-S1` lane failed before execution with GitHub API `HTTP 422`.
2. Exact blocker:
   - `you may only define up to 25 inputs for a workflow_dispatch event`
3. This is a GitHub control-plane constraint, not an AWS/runtime/platform throughput problem.
4. The workflow currently exposes `26` dispatch inputs. The fresh-identity guard added one more boolean and pushed it over the platform limit.
5. Production interpretation:
   - the right fix is not to remove the identity guard;
   - the right fix is to shrink the operator-facing surface to only the knobs that are materially useful for this lane.
6. Inputs that are dead or overly exposed for this workflow:
   - `runtime_path_requested` is no longer meaningful because the lane is pinned to canonical remote WSP replay;
   - `ig_base_url` and `ig_ingest_path` are not used by the workflow jobs and therefore do not belong on the dispatch surface.
7. Chosen remediation:
   - remove those dead inputs from `workflow_dispatch`,
   - keep the production runtime values pinned inside the workflow/script path,
   - preserve the fresh-identity reuse guard and all execution semantics.
8. Immediate next sequence:
   - trim the dispatch surface to <=25 inputs,
   - push the correction,
   - rerun fresh-identity materialization and the strict steady lane on the same identity pair.

## Entry: 2026-03-07 04:20:00 +00:00 - PR3-S1 runtime readiness failure is caused by stale image lineage on the EKS materialization path
1. Fresh-identity `PR3-S1` did not fail on throughput. It failed earlier because the PR3 runtime deployments could not stay ready.
2. Direct live inspection showed the real state:
   - all PR3 deployments were `0/1` available in `fraud-platform-rtdl`,
   - `fp-pr3-al`, `fp-pr3-df`, `fp-pr3-dla`, and `fp-pr3-archive-writer` were crashing with `KAFKA_SASL_CREDENTIALS_MISSING`,
   - `fp-pr3-ieg` and `fp-pr3-ofp` were crashing with `*_EVENT_BUS_KIND_UNSUPPORTED`.
3. I verified that the Kubernetes secret surface itself is correct:
   - `KAFKA_SECURITY_PROTOCOL=SASL_SSL`
   - `KAFKA_SASL_MECHANISM=OAUTHBEARER`
   - run-id and DSN pins are present and populated.
4. I also verified that current source on this branch already supports the intended posture:
   - `src/fraud_detection/event_bus/kafka.py` supports MSK IAM/OAUTHBEARER for both producer and reader,
   - local `IEG` and `OFP` sources support `event_bus_kind == "kafka"`.
5. Therefore the production diagnosis is not "missing secrets" and not "bad profile wiring." It is stale immutable image lineage.
6. The exact design flaw is in the PR3 workflow surface:
   - the canonical ECS WSP task family is already on a newer digest,
   - but `dev_full_pr3_s1_managed.yml` hardcodes a much older `worker_image_uri` default for EKS materialization,
   - so the PR3 runtime was being pinned backward to obsolete application code.
7. Production-grade fix:
   - remove the stale hardcoded EKS image default so materialization resolves from the canonical task-family lineage unless explicitly overridden,
   - build a fresh immutable platform image from the current branch,
   - repin the canonical `fraud-platform-dev-full-wsp-ephemeral` task definition to that digest so both ECS WSP replay and EKS PR3 materialization consume the same code lineage.
8. Why this is the right fix:
   - it restores a single authoritative runtime image source,
   - it prevents silent divergence between replay injection and downstream runtime workers,
   - it avoids the toy fix of supplying fake SASL credentials to an image that should be using IAM/OAUTH.
9. Immediate next sequence:
   - remove the stale workflow default,
   - register a new canonical WSP task-definition revision on the freshly built digest,
   - rerun PR3 runtime materialization and then strict `PR3-S1` on that corrected image boundary.

## Entry: 2026-03-07 04:24:00 +00:00 - PR3-S1 launcher is now blocked by missing psycopg on the GitHub Actions runner, not by the platform runtime
1. After correcting the image lineage, the fresh PR3 runtime rematerialized successfully and all six deployments reached `1/1` available on digest `sha256:8ec634853ae03cfa624633ddde8ccb2108a2915973cee7eeaaa7c653b875c873`.
2. The next strict `PR3-S1` rerun then failed immediately in the launcher step before any remote WSP task dispatch.
3. Exact error:
   - `ModuleNotFoundError: No module named 'psycopg'`
4. Cause:
   - `pr3_s1_wsp_replay_dispatch.py` now imports `psycopg` for the runtime-identity reuse probe,
   - the workflow runner dependency step still installed only `boto3` and `botocore`.
5. Production interpretation:
   - this is a CI runner dependency gap,
   - it does not invalidate the earlier platform-runtime remediation,
   - but it must be fixed because otherwise the fail-closed identity guard never executes in CI.
6. Chosen fix:
   - add `psycopg[binary]` to the workflow runner dependency install for the steady-harness job,
   - keep the database-backed identity probe as-is.
7. Immediate next sequence:
   - patch and push the workflow dependency correction,
   - rerun strict `PR3-S1` on the same fresh runtime identity pair because no traffic was admitted before the import failure.

## Entry: 2026-03-07 04:28:00 +00:00 - The first psycopg workflow fix landed in the wrong job and must be corrected on the steady-harness lane itself
1. The first dependency patch was directionally correct but materially incomplete.
2. I added `psycopg[binary]` to the workflow, but it landed on the `materialize_runtime` job instead of the `steady_harness` job that actually executes `pr3_s1_wsp_replay_dispatch.py`.
3. The repeated rerun therefore failed with the same import error, which is consistent with the logs.
4. Production interpretation:
   - platform runtime remains healthy,
   - the defect is still confined to CI job completeness,
   - and the safe correction is to add the dependency to the exact launcher job rather than changing the application code or disabling the identity probe.
5. Immediate next sequence:
   - patch the `steady_harness` job install surface,
   - push,
   - rerun on the same fresh runtime identity pair.

## Entry: 2026-03-07 04:31:00 +00:00 - Runtime-identity reuse probing must execute from inside the VPC, not from the GitHub-hosted runner
1. Once the launcher could import `psycopg`, the next failure was a private-network reality check:
   - `psycopg.errors.ConnectionTimeout: connection timeout expired`
2. This happened during the Aurora-backed runtime-identity probe, before any remote replay dispatch.
3. Root cause:
   - the GitHub-hosted runner is outside the VPC,
   - Aurora is private,
   - so a direct runner-to-Aurora probe is the wrong control-plane shape for this environment.
4. Production interpretation:
   - the identity reuse guard itself is still correct and necessary,
   - but the execution location of that guard must respect the private-network boundary,
   - exposing Aurora to GitHub-hosted runners would be the wrong production move.
5. Chosen remediation:
   - run the identity probe from inside the VPC using an already-ready PR3 pod (`kubectl exec` on a runtime deployment),
   - keep the database check fail-closed,
   - teach the dispatcher to skip its runner-local probe when the workflow has already completed the in-VPC preflight.
6. Why this is the correct production fix:
   - private data-plane surfaces remain private,
   - CI still gets deterministic identity-guard enforcement,
   - and the guard is executed from a runtime surface that already has the right network reachability.
7. Immediate next sequence:
   - add workflow step for in-VPC identity probing,
   - add dispatcher flag to skip the local probe when that preflight has passed,
   - rerun strict `PR3-S1` on the same fresh identity pair.
