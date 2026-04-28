from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
CATALOGUE_PATH = ROOT / "docs" / "model_spec" / "data-engine" / "interface_pack" / "engine_outputs.catalogue.yaml"
EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
)


TRAFFIC_PRIMITIVES = {
    "arrival_events_5B",
}

BEHAVIOURAL_STREAMS = {
    "s2_event_stream_baseline_6B",
    "s3_event_stream_with_fraud_6B",
}

BEHAVIOURAL_CONTEXT = {
    "s1_arrival_entities_6B",
    "s1_session_index_6B",
    "s2_flow_anchor_baseline_6B",
    "s3_flow_anchor_with_fraud_6B",
}

TRUTH_PRODUCTS = {
    "s4_event_labels_6B",
    "s4_case_timeline_6B",
    "s4_flow_truth_labels_6B",
    "s4_flow_bank_view_6B",
}

READ_AUTHORIZERS = {
    "validation_bundle_5B",
    "validation_bundle_index_5B",
    "validation_passed_flag_5B",
    "validation_bundle_6B",
    "validation_bundle_index_6B",
    "validation_passed_flag_6B",
}

DOWNSTREAM_OPERATING_ESTATE = (
    TRAFFIC_PRIMITIVES
    | BEHAVIOURAL_STREAMS
    | BEHAVIOURAL_CONTEXT
    | TRUTH_PRODUCTS
    | READ_AUTHORIZERS
)

OUT_OF_BOUNDS_SEGMENTS = ["1A", "1B", "2A", "2B", "3A", "3B", "5A", "6A"]

ROLE_MAP = {
    "arrival_events_5B": "traffic_primitives",
    "s2_event_stream_baseline_6B": "behavioural_streams",
    "s3_event_stream_with_fraud_6B": "behavioural_streams",
    "s1_arrival_entities_6B": "behavioural_context",
    "s1_session_index_6B": "behavioural_context",
    "s2_flow_anchor_baseline_6B": "behavioural_context",
    "s3_flow_anchor_with_fraud_6B": "behavioural_context",
    "s4_event_labels_6B": "truth_products",
    "s4_flow_truth_labels_6B": "truth_products",
    "s4_flow_bank_view_6B": "truth_products",
    "s4_case_timeline_6B": "truth_products",
    "validation_bundle_5B": "gate_artifacts",
    "validation_bundle_index_5B": "gate_artifacts",
    "validation_passed_flag_5B": "gate_artifacts",
    "validation_bundle_6B": "gate_artifacts",
    "validation_bundle_index_6B": "gate_artifacts",
    "validation_passed_flag_6B": "gate_artifacts",
}

OPERATING_ZONE_MAP = {
    "arrival_events_5B": "arrival_skeleton_and_upstream_join_surface",
    "s2_event_stream_baseline_6B": "canonical_behavioural_traffic",
    "s3_event_stream_with_fraud_6B": "canonical_behavioural_traffic",
    "s1_arrival_entities_6B": "same_cycle_arrival_enrichment",
    "s1_session_index_6B": "session_level_context_batch_only",
    "s2_flow_anchor_baseline_6B": "same_cycle_flow_enrichment",
    "s3_flow_anchor_with_fraud_6B": "same_cycle_flow_enrichment",
    "s4_event_labels_6B": "offline_truth_and_supervision",
    "s4_flow_truth_labels_6B": "offline_truth_and_supervision",
    "s4_flow_bank_view_6B": "offline_truth_and_case_bank_view",
    "s4_case_timeline_6B": "case_management_and_reconstruction",
    "validation_bundle_5B": "read_authorization_and_governance",
    "validation_bundle_index_5B": "read_authorization_and_governance",
    "validation_passed_flag_5B": "read_authorization_and_governance",
    "validation_bundle_6B": "read_authorization_and_governance",
    "validation_bundle_index_6B": "read_authorization_and_governance",
    "validation_passed_flag_6B": "read_authorization_and_governance",
}

RTDL_STATUS_MAP = {
    "arrival_events_5B": "time_safe_join_surface",
    "s1_arrival_entities_6B": "time_safe_join_surface",
    "s1_session_index_6B": "oracle_only_batch_only",
    "s2_event_stream_baseline_6B": "traffic_emission_surface",
    "s2_flow_anchor_baseline_6B": "time_safe_join_surface",
    "s3_event_stream_with_fraud_6B": "traffic_emission_surface",
    "s3_flow_anchor_with_fraud_6B": "time_safe_join_surface",
    "s4_event_labels_6B": "offline_truth_only",
    "s4_flow_truth_labels_6B": "offline_truth_only",
    "s4_flow_bank_view_6B": "offline_truth_only",
    "s4_case_timeline_6B": "offline_truth_only",
    "validation_bundle_5B": "governance_readiness_only",
    "validation_bundle_index_5B": "governance_readiness_only",
    "validation_passed_flag_5B": "governance_readiness_only",
    "validation_bundle_6B": "governance_readiness_only",
    "validation_bundle_index_6B": "governance_readiness_only",
    "validation_passed_flag_6B": "governance_readiness_only",
}

WHY_IT_MATTERS_MAP = {
    "arrival_events_5B": "Earliest exposed arrival skeleton; useful for route/timezone-aware joins but not emitted as canonical traffic.",
    "s1_arrival_entities_6B": "Provides per-arrival entity attachments for downstream enrichment without reopening the engine.",
    "s1_session_index_6B": "Session-level join aid, but not live-safe because it contains full-session closure information.",
    "s2_event_stream_baseline_6B": "Baseline production-shaped traffic eligible for ingestion and feature-plane consumption.",
    "s2_flow_anchor_baseline_6B": "Flow-level context surface used to enrich the baseline traffic stream.",
    "s3_event_stream_with_fraud_6B": "Post-overlay production-shaped traffic, the stream that carries injected fraud/abuse behaviour.",
    "s3_flow_anchor_with_fraud_6B": "Flow-level context surface used to enrich the post-overlay traffic stream.",
    "s4_event_labels_6B": "Event-level offline truth used for supervision, evaluation, and after-the-fact analysis.",
    "s4_flow_truth_labels_6B": "Flow-level offline truth for supervision and analytical reconstruction.",
    "s4_flow_bank_view_6B": "Bank-view truth product describing what the receiving institution would later know about a flow.",
    "s4_case_timeline_6B": "Case-centric truth product used by investigations and fraud-operations workflows.",
    "validation_bundle_5B": "Authorizing bundle for reading the 5B arrival surface as an approved downstream asset.",
    "validation_bundle_index_5B": "Index proving what artefacts constitute the 5B validation bundle.",
    "validation_passed_flag_5B": "PASS receipt proving the 5B validation bundle digest.",
    "validation_bundle_6B": "Authorizing bundle for reading the 6B downstream operating estate as approved data.",
    "validation_bundle_index_6B": "Index proving what artefacts constitute the 6B validation bundle.",
    "validation_passed_flag_6B": "PASS receipt proving the 6B validation bundle digest.",
}


def fixed_prefix_from_template(path_template: str) -> Path:
    parts = path_template.replace("\\", "/").split("/")
    fixed_parts: list[str] = []
    for part in parts:
        if "{" in part or "*" in part:
            break
        fixed_parts.append(part)
    return Path(*fixed_parts)


def build_catalogue_dataframe(catalogue: list[dict[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for entry in catalogue:
        output_id = str(entry["output_id"])
        prefix = fixed_prefix_from_template(str(entry["path_template"]))
        abs_prefix = RUN_ROOT / prefix
        rows.append(
            {
                "output_id": output_id,
                "class": entry["class"],
                "exposure": entry["exposure"],
                "scope": entry["scope"],
                "owner_segment": entry["owner_segment"],
                "path_template": entry["path_template"],
                "fixed_prefix": str(prefix).replace("\\", "/"),
                "present_in_pinned_run": abs_prefix.exists(),
                "description": entry.get("description", ""),
            }
        )

    return pd.DataFrame(rows).sort_values(["owner_segment", "output_id"]).reset_index(drop=True)


def build_downstream_estate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    downstream_df = df.loc[df["output_id"].isin(DOWNSTREAM_OPERATING_ESTATE)].copy()
    downstream_df["interface_pack_role"] = downstream_df["output_id"].map(ROLE_MAP)
    downstream_df["operating_zone"] = downstream_df["output_id"].map(OPERATING_ZONE_MAP)
    downstream_df["rtdl_status"] = downstream_df["output_id"].map(RTDL_STATUS_MAP)
    downstream_df["why_it_matters"] = downstream_df["output_id"].map(WHY_IT_MATTERS_MAP)
    return downstream_df.sort_values(["owner_segment", "output_id"]).reset_index(drop=True)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    catalogue = yaml.safe_load(CATALOGUE_PATH.read_text(encoding="utf-8"))["outputs"]
    df = build_catalogue_dataframe(catalogue)

    df.to_csv(EXPORT_DIR / "interface_output_inventory.csv", index=False)
    present_df = df.loc[df["present_in_pinned_run"]].copy()
    present_df.to_csv(EXPORT_DIR / "interface_output_inventory_present_only.csv", index=False)

    downstream_df = build_downstream_estate_dataframe(df)
    downstream_df.to_csv(EXPORT_DIR / "interface_downstream_estate_inventory.csv", index=False)

    present_downstream_df = downstream_df.loc[downstream_df["present_in_pinned_run"]].copy()
    present_downstream_df.to_csv(EXPORT_DIR / "interface_downstream_estate_present_only.csv", index=False)

    summary = {
        "downstream_catalogue_outputs_total": int(len(downstream_df)),
        "downstream_present_outputs_total": int(len(present_downstream_df)),
        "downstream_missing_outputs_total": int((~downstream_df["present_in_pinned_run"]).sum()),
        "present_breakdown_by_role": present_downstream_df["interface_pack_role"].value_counts().sort_index().to_dict(),
        "present_breakdown_by_segment": present_downstream_df["owner_segment"].value_counts().sort_index().to_dict(),
        "front_door_outputs_present": sorted(
            present_downstream_df.loc[
                present_downstream_df["interface_pack_role"].isin(
                    ["traffic_primitives", "behavioural_streams", "behavioural_context"]
                ),
                "output_id",
            ].tolist()
        ),
        "truth_products_present": sorted(
            present_downstream_df.loc[
                present_downstream_df["interface_pack_role"] == "truth_products", "output_id"
            ].tolist()
        ),
        "read_authorizers_present": sorted(
            present_downstream_df.loc[
                present_downstream_df["interface_pack_role"] == "gate_artifacts", "output_id"
            ].tolist()
        ),
        "rtdl_time_safe_surfaces_present": sorted(
            present_downstream_df.loc[
                present_downstream_df["rtdl_status"] == "time_safe_join_surface", "output_id"
            ].tolist()
        ),
        "batch_only_surfaces_present": sorted(
            present_downstream_df.loc[
                present_downstream_df["rtdl_status"].isin(["oracle_only_batch_only", "offline_truth_only"]),
                "output_id",
            ].tolist()
        ),
        "explicitly_out_of_bounds_segments_for_black_box_analysis": OUT_OF_BOUNDS_SEGMENTS,
    }

    with (EXPORT_DIR / "interface_downstream_estate_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print("DOWNSTREAM ESTATE SUMMARY")
    print(json.dumps(summary, indent=2))
    print("\nDOWNSTREAM ESTATE INVENTORY")
    print(
        present_downstream_df[
            ["output_id", "interface_pack_role", "owner_segment", "rtdl_status"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
