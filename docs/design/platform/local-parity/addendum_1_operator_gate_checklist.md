```
# ============================================================
# SPINE GREEN v0 — MINIMUM GATE CHECKS (OPERATOR CHECKLIST)
# Goal: 10–15 checks that declare each run phase PASS (local_parity)
# NOTE: “CMD” lines use your make targets where available; otherwise “equivalent”.
# ============================================================

0) SUBSTRATE UP (P0)
   CMD:  make platform-parity-stack-status
   PASS: MinIO + LocalStack + Postgres all healthy/up

1) SUBSTRATE BOOTSTRAPPED (P0)
   CMD:  make platform-parity-bootstrap
         (or equivalent: list buckets + list streams)
   PASS: Buckets exist: oracle-store, fraud-platform
         Streams exist (min set):
           sr-control-bus
           fp.bus.traffic.fraud.v1
           fp.bus.context.arrival_events.v1
           fp.bus.context.arrival_entities.v1
           fp.bus.context.flow_anchor.fraud.v1
           fp.bus.rtdl.v1
           fp.bus.case.v1
           fp.bus.audit.v1

2) RUN ID PINNED (P1)
   CMD:  make platform-run-new
   PASS: runs/fraud-platform/ACTIVE_RUN_ID exists
         + run root folder created for that ID

3) PACKS RUNNING (P2)
   CMD:  make platform-operate-parity-status
   PASS: In-scope packs show RUNNING:
           control_ingress
           rtdl_core
           rtdl_decision_lane
           case_labels
           obs_gov
         AND you are NOT simultaneously running manual “once” consumers for the same lane

4) ORACLE SYNC COMPLETE (P3a)
   CMD:  make platform-oracle-sync
   PASS: Objects exist at s3://oracle-store/<engine_run_root>/... (non-empty)

5) ORACLE SEALED (P3b)
   CMD:  make platform-oracle-pack
         (optional) make platform-oracle-check-strict
   PASS: _SEALED.json exists under oracle pack root
         + strict check passes (or no errors)

6) STREAM_VIEW COMPLETE FOR REQUIRED output_id(s) (P3c)  **CRITICAL**
   CMD:  make platform-oracle-stream-sort
   PASS: For EACH required output_id:
           <ORACLE_STREAM_VIEW_ROOT>/output_id=<id>/part-*.parquet exists
           <...>/output_id=<id>/_stream_view_manifest.json exists
           <...>/output_id=<id>/_stream_sort_receipt.json exists
         Required output_id set (fraud-mode):
           traffic.fraud
           context.arrival_events
           context.arrival_entities
           context.flow_anchor.fraud

7) IG SERVICE READY (P4)
   CMD:  make platform-operate-control-ingress-status
         (or) curl IG health endpoint
   PASS: IG health responds; can write receipts to object store

8) SR READY COMMITTED + PUBLISHED (P5)
   CMD:  make platform-sr-run-reuse
   PASS: SR logs show “READY committed” and “READY published”
         AND control bus (sr-control-bus) contains READY for ACTIVE_RUN_ID

9) WSP STREAMING FINISHED (P6)
   CMD:  (pack running) observe WSP logs
         (or once) make platform-wsp-ready-consumer-once
   PASS: WSP logs show “stream start” -> “stream stop”
         AND emitted >0 events (unless intentionally a 0-event test)

10) IG ADMISSION COMMITTED (P7)
    CMD:  list receipts prefix
    PASS: s3://fraud-platform/<run_id>/ig/receipts/ contains receipts
          Receipt(s) include eb_ref + offset_kind=kinesis_sequence
          (Optional sanity) admitted_count > 0

11) EB HAS TRAFFIC + CONTEXT RECORDS (P7/P8)
    CMD:  kinesis stream get/list/describe (or platform helper)
    PASS: traffic + context streams show records (non-zero) for this run window

12) RTDL CORE CAUGHT UP (P8)
    CMD:  check run artifacts + projector checkpoints
    PASS: IEG reconciliation artifact exists:
            runs/fraud-platform/<run_id>/identity_entity_graph/.../reconciliation.json
          OFP + CSFB show advanced checkpoints / non-stuck health counters

13) DECISION CHAIN COMMITTED (P9)
    CMD:  inspect rtdl + audit streams and DLA artifacts
    PASS: fp.bus.rtdl.v1 contains decision/intent/outcome events
          fp.bus.audit.v1 contains audit events
          DLA reconciliation/artifacts exist under:
            runs/fraud-platform/<run_id>/decision_log_audit/...

14) CASE + LABELS COMMITTED (P10)
    CMD:  inspect case stream + CM/LS stores/artifacts
    PASS: fp.bus.case.v1 has trigger events
          CM shows case timeline updates for the run
          LS shows label assertions IF the run exercises labels

15) OBS/GOV CLOSED (P11)
    CMD:  make platform-run-report
          make platform-env-conformance
          (optional) make platform-governance-query
    PASS: runs/fraud-platform/<run_id>/obs/platform_run_report.json exists
          runs/fraud-platform/<run_id>/obs/environment_conformance.json exists (+ passes)
          s3://fraud-platform/<run_id>/obs/governance/events.jsonl appended
          (No append conflicts => no concurrent writers)

# RECOMMENDED SHORT-CIRCUIT VALIDATION (before full scale)
- Gate-20:  run with WSP caps ~20 events/output, require checks 0–15 pass
- Gate-200: run with caps ~200, require checks 0–15 pass
- Then full cap (e.g., 500k) once both bounded gates pass

```