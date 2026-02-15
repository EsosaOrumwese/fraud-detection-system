"""Build local parity spine graph assets (DOT, Mermaid, ASCII).

Source grounding:
- config/platform/profiles/local_parity.yaml
- config/platform/run_operate/packs/local_parity_*.v0.yaml
- docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt
- docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


OUTPUT_DIR = Path("docs/design/platform/local-parity/graph")


def dot_graph() -> str:
    return dedent(
        r'''
        digraph LocalParitySpineGreenV0 {
          graph [
            label="Local Parity Platform Graph (Spine Green v0, Implementation-True)",
            labelloc=t,
            fontsize=18,
            fontname="Helvetica",
            rankdir=LR,
            splines=true,
            pad=0.2,
            nodesep=0.35,
            ranksep=0.65
          ];

          node [
            shape=box,
            style="rounded,filled",
            fillcolor="#F8FAFC",
            color="#334155",
            fontname="Helvetica",
            fontsize=10,
            margin="0.08,0.06"
          ];

          edge [
            color="#334155",
            fontname="Helvetica",
            fontsize=9,
            arrowsize=0.8
          ];

          subgraph cluster_phase {
            label="Lifecycle Phase Gates (Spine Green v0)";
            color="#CBD5E1";
            style="rounded";

            p0 [label="P0-P1\nSubstrate Ready + Run Pinned", fillcolor="#EEF2FF"];
            p2 [label="P2\nDaemons Ready", fillcolor="#EEF2FF"];
            p3 [label="P3\nOracle Ready", fillcolor="#EEF2FF"];
            p4 [label="P4-P5\nIngest Ready + READY Published", fillcolor="#EEF2FF"];
            p6 [label="P6-P7\nStreaming Active + Ingest Committed", fillcolor="#EEF2FF"];
            p8 [label="P8\nRTDL Caught Up", fillcolor="#EEF2FF"];
            p9 [label="P9\nDecision Chain Committed", fillcolor="#EEF2FF"];
            p10 [label="P10\nCase + Labels Committed", fillcolor="#EEF2FF"];
            p11 [label="P11\nObs/Gov Closed", fillcolor="#EEF2FF"];

            p0 -> p2 -> p3 -> p4 -> p6 -> p8 -> p9 -> p10 -> p11;
          }

          subgraph cluster_identity {
            label="Run Scope + Substrates";
            color="#CBD5E1";
            style="rounded";

            active_run [label="ACTIVE_RUN_ID\nruns/fraud-platform/ACTIVE_RUN_ID", fillcolor="#F1F5F9"];
            obj [label="Object Store (MinIO, S3-compatible)\nPLATFORM_STORE_ROOT=s3://fraud-platform", shape=cylinder, fillcolor="#ECFEFF"];
            eb [label="Event Bus (Kinesis/LocalStack)\nEVENT_BUS_STREAM=auto/topic", shape=cylinder, fillcolor="#ECFEFF"];
            ctrl [label="Control Bus (Kinesis)\nstream: sr-control-bus", shape=cylinder, fillcolor="#ECFEFF"];
            pg [label="Postgres DSN Mesh\n(admission, checkpoints, projections, ledgers)", shape=cylinder, fillcolor="#ECFEFF"];
          }

          subgraph cluster_control_ingress {
            label="Pack: local_parity_control_ingress_v0";
            color="#BFDBFE";
            style="rounded";

            sr [label="Scenario Runner (SR)\nreadiness authority\n(sr/run_plan, run_record, ready_signal)", fillcolor="#EFF6FF"];
            oracle [label="Oracle Stream View\nORACLE_STREAM_VIEW_ROOT\npart-*.parquet + _stream_* receipts", shape=folder, fillcolor="#EFF6FF"];
            wsp [label="wsp_ready_consumer\nmodule: fraud_detection.world_streamer_producer.ready_consumer\nchecks required packs + run pin", fillcolor="#DBEAFE"];
            ig [label="ig_service\nmodule: fraud_detection.ingestion_gate.service\nPOST /v1/ingest/push (X-IG-Api-Key)", fillcolor="#DBEAFE"];

            ig_receipts [label="IG Receipts + Quarantine\ns3://fraud-platform/<platform_run_id>/ig/{receipts,quarantine}", shape=folder, fillcolor="#E0F2FE"];
            ig_index [label="IG Admission Index\nPARITY_IG_ADMISSION_DSN\nstate: IN_FLIGHT|ADMITTED|PUBLISH_AMBIGUOUS", shape=folder, fillcolor="#E0F2FE"];
          }

          subgraph cluster_topics {
            label="Event Bus Topic Lanes";
            color="#BBF7D0";
            style="rounded";

            t_traffic [label="Traffic Topics\nfp.bus.traffic.{fraud|baseline}.v1", shape=component, fillcolor="#DCFCE7"];
            t_context [label="Context Topics\narrival_events, arrival_entities, flow_anchor_{fraud|baseline}", shape=component, fillcolor="#DCFCE7"];
            t_rtdl [label="RTDL Lane\nfp.bus.rtdl.v1", shape=component, fillcolor="#DCFCE7"];
            t_case [label="Case Lane\nfp.bus.case.v1", shape=component, fillcolor="#DCFCE7"];
            t_audit [label="Audit Lane\nfp.bus.audit.v1", shape=component, fillcolor="#DCFCE7"];
          }

          subgraph cluster_rtdl_core {
            label="Pack: local_parity_rtdl_core_v0";
            color="#FDE68A";
            style="rounded";

            ieg [label="ieg_projector\nIdentity Entity Graph\nmodule: fraud_detection.identity_entity_graph.projector", fillcolor="#FEF9C3"];
            ofp [label="ofp_projector\nOnline Feature Plane\nmodule: fraud_detection.online_feature_plane.projector", fillcolor="#FEF9C3"];
            csfb [label="csfb_intake\nContext Store Flow Binding\nmodule: fraud_detection.context_store_flow_binding.intake", fillcolor="#FEF9C3"];
            arch [label="archive_writer_worker\nmodule: fraud_detection.archive_writer.worker", fillcolor="#FEF9C3"];

            ieg_db [label="IEG Projection Store\nPARITY_IEG_PROJECTION_DSN", shape=folder, fillcolor="#FFFBEB"];
            ofp_db [label="OFP Projection + Snapshot Index\nPARITY_OFP_PROJECTION_DSN\nPARITY_OFP_SNAPSHOT_INDEX_DSN", shape=folder, fillcolor="#FFFBEB"];
            csfb_db [label="CSFB Projection Store\nPARITY_CSFB_PROJECTION_DSN", shape=folder, fillcolor="#FFFBEB"];
            arch_store [label="Archive Evidence\ns3://fraud-platform/<platform_run_id>/archive/events/...", shape=folder, fillcolor="#FFFBEB"];
            arch_ledger [label="Archive Ledger\nPARITY_ARCHIVE_WRITER_LEDGER_DSN", shape=folder, fillcolor="#FFFBEB"];
          }

          subgraph cluster_decision {
            label="Pack: local_parity_rtdl_decision_lane_v0";
            color="#FBCFE8";
            style="rounded";

            dl [label="dl_worker\nDegrade Ladder\nmodule: fraud_detection.degrade_ladder.worker", fillcolor="#FCE7F3"];
            df [label="df_worker\nDecision Fabric\nmodule: fraud_detection.decision_fabric.worker", fillcolor="#FCE7F3"];
            al [label="al_worker\nAction Layer\nmodule: fraud_detection.action_layer.worker", fillcolor="#FCE7F3"];
            dla [label="dla_worker\nDecision Log & Audit\nmodule: fraud_detection.decision_log_audit.worker", fillcolor="#FCE7F3"];

            dl_store [label="DL Stores\nPARITY_DL_{POSTURE,OUTBOX,OPS}_DSN", shape=folder, fillcolor="#FDF2F8"];
            df_ckpt [label="DF Replay + Checkpoint\nPARITY_DF_{REPLAY,CHECKPOINT}_DSN", shape=folder, fillcolor="#FDF2F8"];
            al_ckpt [label="AL Ledger/Outcomes/Replay/Checkpoint\nPARITY_AL_*_DSN", shape=folder, fillcolor="#FDF2F8"];
            dla_idx [label="DLA Index\nPARITY_DLA_INDEX_DSN", shape=folder, fillcolor="#FDF2F8"];
            dla_records [label="DLA Append-only Records\ns3://fraud-platform/<platform_run_id>/decision_log_audit/records/<audit_id>.json", shape=folder, fillcolor="#FDF2F8"];
          }

          subgraph cluster_case_labels {
            label="Pack: local_parity_case_labels_v0";
            color="#FDBA74";
            style="rounded";

            ct [label="case_trigger_worker\nmodule: fraud_detection.case_trigger.worker", fillcolor="#FFEDD5"];
            cm [label="case_mgmt_worker\nmodule: fraud_detection.case_mgmt.worker", fillcolor="#FFEDD5"];
            ls [label="label_store_worker\nmodule: fraud_detection.label_store.worker", fillcolor="#FFEDD5"];

            ct_dsns [label="CaseTrigger Replay/Checkpoint/Publish Store\nPARITY_CASE_TRIGGER_*_DSN", shape=folder, fillcolor="#FFF7ED"];
            cm_store [label="CaseMgmt Locator\nPARITY_CASE_MGMT_LOCATOR", shape=folder, fillcolor="#FFF7ED"];
            ls_store [label="LabelStore Locator\nPARITY_LABEL_STORE_LOCATOR", shape=folder, fillcolor="#FFF7ED"];
          }

          subgraph cluster_obs {
            label="Pack: local_parity_obs_gov_v0";
            color="#A7F3D0";
            style="rounded";

            reporter [label="platform_run_reporter_worker\nmodule: fraud_detection.platform_reporter.worker", fillcolor="#ECFDF5"];
            conform [label="platform_conformance_worker\nmodule: fraud_detection.platform_conformance.worker", fillcolor="#ECFDF5"];

            run_report [label="Run Report\nruns/fraud-platform/<platform_run_id>/obs/platform_run_report.json", shape=folder, fillcolor="#F0FDF4"];
            env_conf [label="Environment Conformance\nruns/fraud-platform/<platform_run_id>/obs/environment_conformance.json", shape=folder, fillcolor="#F0FDF4"];
            gov_append [label="Governance Append (single writer)\ns3://fraud-platform/<platform_run_id>/obs/governance/events.jsonl", shape=folder, fillcolor="#F0FDF4"];
          }

          sr -> ctrl [label="publish READY (run-scoped)"];
          obj -> sr [label="read oracle metadata + write sr/* artifacts"];
          ctrl -> wsp [label="consume READY"];
          oracle -> wsp [label="read stream_view by output_id"];
          wsp -> ig [label="HTTP push envelopes\n(traffic + context)"];
          ig -> ig_receipts [label="append receipts/quarantine", penwidth=1.4];
          ig -> ig_index [label="upsert admission state", penwidth=1.4];

          ig -> t_traffic [label="publish ADMITTED traffic"];
          ig -> t_context [label="publish ADMITTED context"];
          df -> ig [label="publish decision_response + action_intent\n(via IG boundary)"];
          al -> ig [label="publish action_outcome\n(via IG boundary)"];
          ct -> ig [label="publish case_trigger\n(via IG boundary)"];

          t_traffic -> ieg [label="consume"];
          t_context -> ieg [label="consume"];
          t_traffic -> ofp [label="consume"];
          t_context -> csfb [label="consume"];
          t_traffic -> df [label="decision triggers"];
          t_rtdl -> al [label="consume action_intent"];
          t_rtdl -> dla [label="consume decision/intent/outcome"];
          t_rtdl -> ct [label="consume decision + outcome evidence"];
          t_case -> cm [label="consume case triggers"];

          ieg -> ieg_db [label="project graph state"];
          ofp -> ofp_db [label="project features + snapshots"];
          csfb -> csfb_db [label="project context bindings"];
          arch -> arch_store [label="write immutable archive evidence"];
          arch -> arch_ledger [label="checkpoint + idempotency"];

          dl -> dl_store [label="posture decision + outbox"];
          dl_store -> df [label="read current degrade posture"];
          df -> df_ckpt [label="replay + checkpoint gate"];
          al -> al_ckpt [label="ledger/outcomes/checkpoints"];
          dla -> dla_idx [label="lineage + reconciliation index"];
          dla -> dla_records [label="append audit records", penwidth=1.4];
          dla -> t_audit [label="optional audit facts stream", style=dashed];

          ct -> ct_dsns [label="replay + publish store"];
          cm -> cm_store [label="append case timeline"];
          cm -> ls [label="LabelStore writer boundary"];
          ls -> ls_store [label="append label assertions"];

          reporter -> run_report [label="emit lane summaries"];
          conform -> env_conf [label="emit parity checks"];
          reporter -> gov_append [label="append governance events"];

          obj -> ig_receipts [style=dashed, label="storage substrate"];
          obj -> arch_store [style=dashed, label="storage substrate"];
          obj -> dla_records [style=dashed, label="storage substrate"];
          obj -> run_report [style=dashed, label="storage substrate"];
          obj -> env_conf [style=dashed, label="storage substrate"];
          obj -> gov_append [style=dashed, label="storage substrate"];
          eb -> t_traffic [style=dashed, label="topic-backed stream"];
          eb -> t_context [style=dashed];
          eb -> t_rtdl [style=dashed];
          eb -> t_case [style=dashed];
          eb -> t_audit [style=dashed];

          pg -> ig_index [style=dashed, label="Postgres DSN"];
          pg -> ieg_db [style=dashed];
          pg -> ofp_db [style=dashed];
          pg -> csfb_db [style=dashed];
          pg -> arch_ledger [style=dashed];
          pg -> dl_store [style=dashed];
          pg -> df_ckpt [style=dashed];
          pg -> al_ckpt [style=dashed];
          pg -> dla_idx [style=dashed];
          pg -> ct_dsns [style=dashed];
          pg -> cm_store [style=dashed];
          pg -> ls_store [style=dashed];

          active_run -> wsp [style=dashed, color="#0F766E", label="require active run match"];
          active_run -> ieg [style=dashed, color="#0F766E", label="required_platform_run_id"];
          active_run -> ofp [style=dashed, color="#0F766E"];
          active_run -> csfb [style=dashed, color="#0F766E"];
          active_run -> arch [style=dashed, color="#0F766E"];
          active_run -> df [style=dashed, color="#0F766E"];
          active_run -> al [style=dashed, color="#0F766E"];
          active_run -> dla [style=dashed, color="#0F766E"];
          active_run -> ct [style=dashed, color="#0F766E"];
          active_run -> cm [style=dashed, color="#0F766E"];
          active_run -> ls [style=dashed, color="#0F766E"];
          active_run -> reporter [style=dashed, color="#0F766E"];
          active_run -> conform [style=dashed, color="#0F766E"];

          p4 -> sr [style=dotted, label="P5 READY_PUBLISHED"];
          p6 -> ig [style=dotted, label="P6-P7 ingress closure"];
          p8 -> ieg [style=dotted, label="P8"];
          p9 -> df [style=dotted, label="P9"];
          p10 -> cm [style=dotted, label="P10"];
          p11 -> reporter [style=dotted, label="P11"];
        }
        '''
    ).strip() + "\n"


def mermaid_graph() -> str:
    return dedent(
        '''
        %% Local Parity Platform Graph (Spine Green v0, Implementation-True)
        flowchart LR

          subgraph PHASE[Lifecycle Gates P0->P11]
            P0[P0-P1<br/>Substrate Ready + Run Pinned] --> P2[P2<br/>Daemons Ready] --> P3[P3<br/>Oracle Ready] --> P4[P4-P5<br/>Ingest Ready + READY Published] --> P6[P6-P7<br/>Streaming Active + Ingest Committed] --> P8[P8<br/>RTDL Caught Up] --> P9[P9<br/>Decision Chain Committed] --> P10[P10<br/>Case + Labels Committed] --> P11[P11<br/>Obs/Gov Closed]
          end

          subgraph ID[Run Scope + Substrates]
            ACTIVE[ACTIVE_RUN_ID<br/>runs/fraud-platform/ACTIVE_RUN_ID]
            OBJ[(MinIO Object Store<br/>s3://fraud-platform)]
            EB[(Kinesis Event Bus<br/>EVENT_BUS_STREAM=auto/topic)]
            CTRL[(Control Bus<br/>stream=sr-control-bus)]
            PG[(Postgres DSN Mesh)]
          end

          subgraph CI[Pack: local_parity_control_ingress_v0]
            SR[Scenario Runner<br/>readiness authority]
            ORACLE[[Oracle Stream View<br/>ORACLE_STREAM_VIEW_ROOT]]
            WSP[wsp_ready_consumer<br/>fraud_detection.world_streamer_producer.ready_consumer]
            IG[ig_service<br/>fraud_detection.ingestion_gate.service]
            IGR[[IG Receipts + Quarantine<br/>.../ig/{receipts,quarantine}]]
            IGX[[IG Admission Index<br/>PARITY_IG_ADMISSION_DSN]]
          end

          subgraph TOPICS[Event Bus Topic Lanes]
            TTR[[fp.bus.traffic.{fraud|baseline}.v1]]
            TCTX[[fp.bus.context.{arrival_events,arrival_entities,flow_anchor_*}.v1]]
            TRTDL[[fp.bus.rtdl.v1]]
            TCASE[[fp.bus.case.v1]]
            TAUD[[fp.bus.audit.v1]]
          end

          subgraph CORE[Pack: local_parity_rtdl_core_v0]
            IEG[ieg_projector]
            OFP[ofp_projector]
            CSFB[csfb_intake]
            ARCH[archive_writer_worker]
            IEGDB[[IEG Projection Store]]
            OFPDB[[OFP Projection + Snapshot Index]]
            CSFBDB[[CSFB Projection Store]]
            ARCHOBJ[[Archive Evidence<br/>.../archive/events/...]]
            ARCHLED[[Archive Ledger DSN]]
          end

          subgraph DEC[Pack: local_parity_rtdl_decision_lane_v0]
            DL[dl_worker<br/>Degrade Ladder]
            DF[df_worker<br/>Decision Fabric]
            AL[al_worker<br/>Action Layer]
            DLA[dla_worker<br/>Decision Log & Audit]
            DLDB[[DL posture/outbox/ops DSNs]]
            DFDB[[DF replay/checkpoint DSNs]]
            ALDB[[AL ledger/outcomes/checkpoint DSNs]]
            DLAIDX[[DLA index DSN]]
            DLAREC[[DLA Records<br/>.../decision_log_audit/records/audit_id.json]]
          end

          subgraph CL[Pack: local_parity_case_labels_v0]
            CT[case_trigger_worker]
            CM[case_mgmt_worker]
            LS[label_store_worker]
            CTDB[[CaseTrigger replay/checkpoint/publish DSNs]]
            CMDB[[CaseMgmt locator]]
            LSDB[[LabelStore locator]]
          end

          subgraph OG[Pack: local_parity_obs_gov_v0]
            REP[platform_run_reporter_worker]
            CONF[platform_conformance_worker]
            RPT[[platform_run_report.json]]
            CONFF[[environment_conformance.json]]
            GOV[[obs/governance/events.jsonl]]
          end

          SR -->|publish READY| CTRL
          OBJ -->|read/write sr/*| SR
          CTRL -->|consume READY| WSP
          ORACLE -->|read stream_view| WSP
          WSP -->|HTTP push traffic/context envelopes| IG
          IG -->|append evidence| IGR
          IG -->|upsert state| IGX

          IG -->|publish ADMITTED traffic| TTR
          IG -->|publish ADMITTED context| TCTX
          DF -->|decision_response + action_intent via IG| IG
          AL -->|action_outcome via IG| IG
          CT -->|case_trigger via IG| IG

          TTR --> IEG
          TCTX --> IEG
          TTR --> OFP
          TCTX --> CSFB
          TTR --> DF
          TRTDL --> AL
          TRTDL --> DLA
          TRTDL --> CT
          TCASE --> CM

          IEG --> IEGDB
          OFP --> OFPDB
          CSFB --> CSFBDB
          ARCH --> ARCHOBJ
          ARCH --> ARCHLED

          DL --> DLDB
          DLDB --> DF
          DF --> DFDB
          AL --> ALDB
          DLA --> DLAIDX
          DLA --> DLAREC
          DLA -. optional audit facts .-> TAUD

          CT --> CTDB
          CM --> CMDB
          CM -->|LabelStore writer boundary| LS
          LS --> LSDB

          REP --> RPT
          CONF --> CONFF
          REP --> GOV

          EB -. topic substrate .-> TTR
          EB -. topic substrate .-> TCTX
          EB -. topic substrate .-> TRTDL
          EB -. topic substrate .-> TCASE
          EB -. topic substrate .-> TAUD

          OBJ -. storage substrate .-> IGR
          OBJ -. storage substrate .-> ARCHOBJ
          OBJ -. storage substrate .-> DLAREC
          OBJ -. storage substrate .-> RPT
          OBJ -. storage substrate .-> CONFF
          OBJ -. storage substrate .-> GOV

          PG -. DSN substrate .-> IGX
          PG -. DSN substrate .-> IEGDB
          PG -. DSN substrate .-> OFPDB
          PG -. DSN substrate .-> CSFBDB
          PG -. DSN substrate .-> ARCHLED
          PG -. DSN substrate .-> DLDB
          PG -. DSN substrate .-> DFDB
          PG -. DSN substrate .-> ALDB
          PG -. DSN substrate .-> DLAIDX
          PG -. DSN substrate .-> CTDB
          PG -. DSN substrate .-> CMDB
          PG -. DSN substrate .-> LSDB

          ACTIVE -. required_platform_run_id / active-run match .-> WSP
          ACTIVE -. required_platform_run_id .-> IEG
          ACTIVE -. required_platform_run_id .-> OFP
          ACTIVE -. required_platform_run_id .-> CSFB
          ACTIVE -. required_platform_run_id .-> ARCH
          ACTIVE -. required_platform_run_id .-> DF
          ACTIVE -. required_platform_run_id .-> AL
          ACTIVE -. required_platform_run_id .-> DLA
          ACTIVE -. required_platform_run_id .-> CT
          ACTIVE -. required_platform_run_id .-> CM
          ACTIVE -. required_platform_run_id .-> LS
          ACTIVE -. required_platform_run_id .-> REP
          ACTIVE -. required_platform_run_id .-> CONF

          P4 -. P5 READY_PUBLISHED .-> SR
          P6 -. P6-P7 ingress closure .-> IG
          P8 -. P8 .-> IEG
          P9 -. P9 .-> DF
          P10 -. P10 .-> CM
          P11 -. P11 .-> REP
        '''
    ).strip() + "\n"


def ascii_graph() -> str:
    return dedent(
        '''
        LOCAL PARITY PLATFORM GRAPH (SPINE GREEN v0) - IMPLEMENTATION-TRUE
        ================================================================

        Phase spine (closure order)
        ---------------------------
        P0-P1 Substrate+RunPin -> P2 DaemonsReady -> P3 OracleReady -> P4-P5 IngestReady+READYPublished
        -> P6-P7 StreamingActive+IngestCommitted -> P8 RTDLCaughtUp -> P9 DecisionChainCommitted
        -> P10 Case+LabelsCommitted -> P11 Obs/GovClosed


        LAYER 0: RUN IDENTITY + SUBSTRATES
        ----------------------------------
        [ACTIVE_RUN_ID]  runs/fraud-platform/ACTIVE_RUN_ID
             | (required_platform_run_id / active-run match)
             +--> wsp_ready_consumer, ieg, ofp, csfb, archive_writer, df, al, dla,
             |    case_trigger, case_mgmt, label_store, reporter, conformance
             |
        [MinIO S3 root] s3://fraud-platform
        [Kinesis bus]   EVENT_BUS_STREAM=auto/topic
        [Kinesis ctrl]  sr-control-bus
        [Postgres DSN mesh] admission/checkpoints/projections/ledgers


        LAYER 1: CONTROL + INGRESS (pack: local_parity_control_ingress_v0)
        -------------------------------------------------------------------
        Scenario Runner (SR)
          - readiness authority, writes sr/run_plan, sr/run_record, sr/ready_signal
          - publishes READY to sr-control-bus

        Oracle stream-view
          - ORACLE_STREAM_VIEW_ROOT/output_id=.../part-*.parquet + _stream_* receipts

        wsp_ready_consumer (fraud_detection.world_streamer_producer.ready_consumer)
          - consumes READY from sr-control-bus
          - validates run pin + required packs + run-facts consistency
          - reads stream_view; bounded by WSP_MAX_EVENTS_PER_OUTPUT (Gate-20/Gate-200 protocol)
          - pushes envelopes to IG ingest API

        ig_service (fraud_detection.ingestion_gate.service)
          - endpoint: POST /v1/ingest/push (X-IG-Api-Key)
          - owns admission decision + dedupe + publish outcome state
          - writes append-only evidence:
              s3://fraud-platform/<platform_run_id>/ig/receipts/*.json
              s3://fraud-platform/<platform_run_id>/ig/quarantine/*.json
          - writes admission index (PARITY_IG_ADMISSION_DSN)
            state = IN_FLIGHT | ADMITTED | PUBLISH_AMBIGUOUS
          - publishes ADMITTED traffic/context into EB topics


        LAYER 2: EVENT BUS TOPIC LANES (local_parity)
        ----------------------------------------------
        traffic lane : fp.bus.traffic.{fraud|baseline}.v1
        context lane : fp.bus.context.arrival_events.v1
                       fp.bus.context.arrival_entities.v1
                       fp.bus.context.flow_anchor.{fraud|baseline}.v1
        rtdl lane    : fp.bus.rtdl.v1
        case lane    : fp.bus.case.v1
        audit lane   : fp.bus.audit.v1 (available lane; currently optional/sparse publisher usage)


        LAYER 3: RTDL CORE (pack: local_parity_rtdl_core_v0)
        -----------------------------------------------------
        ieg_projector  <- traffic + context topics  -> IEG projection store (PARITY_IEG_PROJECTION_DSN)
        ofp_projector  <- traffic topics            -> OFP projection + snapshot index
        csfb_intake    <- context topics            -> CSFB projection store
        archive_writer <- traffic + context + rtdl + case + audit topics
                        -> s3://fraud-platform/<platform_run_id>/archive/events/...
                        -> archive ledger DSN (PARITY_ARCHIVE_WRITER_LEDGER_DSN)


        LAYER 4: RTDL DECISION LANE (pack: local_parity_rtdl_decision_lane_v0)
        ------------------------------------------------------------------------
        dl_worker (Degrade Ladder)
          - control-loop posture engine; writes DL posture/outbox/ops DSNs
          - DF reads DL posture as gating signal

        df_worker (Decision Fabric)
          - consumes traffic trigger topics
          - uses context/projection stores + posture + replay/checkpoint DSNs
          - emits decision_response + action_intent via IG boundary

        al_worker (Action Layer)
          - consumes fp.bus.rtdl.v1 (action_intent)
          - writes ledger/outcomes/replay/checkpoint DSNs
          - emits action_outcome via IG boundary

        dla_worker (Decision Log & Audit)
          - consumes fp.bus.rtdl.v1 (decision/intent/outcome chain)
          - writes DLA index DSN + append-only records:
              s3://fraud-platform/<platform_run_id>/decision_log_audit/records/<audit_id>.json
          - optional audit facts stream publication is lane-available (fp.bus.audit.v1)


        LAYER 5: CASE + LABELS (pack: local_parity_case_labels_v0)
        -----------------------------------------------------------
        case_trigger_worker
          - consumes fp.bus.rtdl.v1
          - writes replay/checkpoint/publish DSNs
          - emits case_trigger via IG boundary

        IG publishes case_trigger ADMITTED events -> fp.bus.case.v1

        case_mgmt_worker
          - consumes fp.bus.case.v1
          - appends case timeline (PARITY_CASE_MGMT_LOCATOR)
          - calls LabelStore writer boundary

        label_store_worker
          - appends label assertions/timeline (PARITY_LABEL_STORE_LOCATOR)
          - idempotent append-only semantics


        LAYER 6: OBSERVABILITY + GOVERNANCE (pack: local_parity_obs_gov_v0)
        --------------------------------------------------------------------
        platform_run_reporter_worker
          -> runs/fraud-platform/<platform_run_id>/obs/platform_run_report.json
          -> s3://fraud-platform/<platform_run_id>/obs/governance/events.jsonl  (single-writer append)

        platform_conformance_worker
          -> runs/fraud-platform/<platform_run_id>/obs/environment_conformance.json


        OWNERSHIP LAWS REFLECTED IN THE GRAPH
        -------------------------------------
        1) SR is readiness authority and control-bus READY writer.
        2) IG is the admission boundary and only writes ADMITTED traffic/context/case/rtdl from HTTP ingest clients.
        3) DLA owns append-only audit truth records under decision_log_audit/records.
        4) Governance closeout is single-writer append for obs/governance/events.jsonl.
        5) Green closure claims require phase-appropriate commit evidence (not process-alive only).
        '''
    ).strip() + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assets = {
        "local_parity_spine_green_v0.graphviz.dot": dot_graph(),
        "local_parity_spine_green_v0.mermaid.mmd": mermaid_graph(),
        "local_parity_spine_green_v0.ascii.txt": ascii_graph(),
    }

    for filename, content in assets.items():
        path = OUTPUT_DIR / filename
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
