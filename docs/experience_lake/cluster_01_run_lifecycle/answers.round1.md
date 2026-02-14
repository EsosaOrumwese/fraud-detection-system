# Cluster 01 - Round 1 Answers

## Q1) What "Spine Green v0" means in my language

`Spine Green v0` is a phase-closure claim, not a vibe claim.

It means the local-parity state machine closes `P0 -> P11` for in-scope lanes only, with gate evidence present at each critical commit point, and no fail-closed blockers open.

In-scope lanes are:
`Control+Ingress`, `RTDL`, `Case+Labels`, `Run/Operate+Obs/Gov`.

Out-of-scope for this baseline:
`Learning/Registry` lifecycle closure (`OFS/MF/MPR`).

### Pass criteria (must all be true)

1. Global phase closure condition:
Condition: `P7 INGEST_COMMITTED`, `P8 RTDL_CAUGHT_UP`, `P9 DECISION_CHAIN_COMMITTED`, `P10 CASE_LABELS_COMMITTED`, and `P11 OBS_GOV_CLOSED` are all true for the active `platform_run_id`.
Evidence hook: run-scoped artifacts under `runs/fraud-platform/<platform_run_id>/...` plus commit evidence in `s3://fraud-platform/<platform_run_id>/...`.

2. Control+Ingress closure:
Condition: IG admission commit is durable (receipt + `eb_ref`), `admitted_count > 0`, and no unresolved `PUBLISH_AMBIGUOUS` in closure set.
Evidence hook: `s3://fraud-platform/<platform_run_id>/ig/receipts/<receipt_id>.json`, IG admission index state, and run report ingress signal (`obs/platform_run_report.json` -> `ingress.admit > 0`).

3. WSP bounded-stream gate closure:
Condition: READY consumer processes in-scope outputs for active run and reaches bounded cap per output for the selected gate (`20` or `200`).
Evidence hook: `runs/fraud-platform/<platform_run_id>/operate/local_parity_control_ingress_v0/logs/wsp_ready_consumer.log` with stop markers (`emitted=<cap>` per required output).
Expected count source: Oracle stream-view output set and SR READY/run-facts references (`.../_stream_view_manifest.json`, `sr/run_facts_view/<run_id>.json`).

4. RTDL core closure (`P8`):
Condition: `ArchiveWriter`, `IEG`, `OFP`, and `CSFB` close with GREEN health and non-zero run activity (`seen_total`, `events_seen`, `join_hits` as applicable), and archive durability evidence exists.
Evidence hook: `archive_writer/health/last_health.json`, `identity_entity_graph/health/last_health.json`, `online_feature_plane/health/last_health.json`, `context_store_flow_binding/health/last_health.json`, and archive objects under `s3://fraud-platform/<platform_run_id>/archive/events/...`.

5. Decision-lane closure (`P9`):
Condition: decision chain commits through `DL/DF/AL/DLA`, audit stream advances, and DLA unresolved lineage is zero.
Evidence hook: `runs/fraud-platform/<platform_run_id>/decision_log_audit/health/last_health.json` (`health_state=GREEN`, `lineage_unresolved_total=0`) plus DLA reconciliation artifacts and audit-stream activity.

6. Case+Labels closure (`P10`):
Condition: `CaseTrigger`, `CM`, and `LS` are GREEN and each shows non-zero committed activity (`triggers_seen`, `cases_created`, `accepted`).
Evidence hook: `case_trigger/health/last_health.json`, `case_mgmt/health/last_health.json`, `label_store/health/last_health.json` and matching `metrics/last_metrics.json` files.

7. Obs/Gov closure (`P11`):
Condition: run report exists, conformance exists and passes, and governance append closes without concurrent-writer conflict.
Evidence hook: `runs/fraud-platform/<platform_run_id>/obs/platform_run_report.json`, `runs/fraud-platform/<platform_run_id>/obs/environment_conformance.json` (`status=PASS`), `s3://fraud-platform/<platform_run_id>/obs/governance/events.jsonl`.

### Why this definition matters

This definition prevents two failure modes:
1. Calling a run "green" while a critical gate is still open or ambiguous.
2. Blocking migration on out-of-scope learning-plane closure that was not part of the accepted baseline.

So "Spine Green v0" is a defensible migration baseline: explicit scope, explicit phase gates, explicit commit evidence, and explicit fail-closed behavior.
