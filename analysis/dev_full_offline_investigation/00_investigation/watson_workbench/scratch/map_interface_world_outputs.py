from __future__ import annotations

import json
from collections import Counter, defaultdict
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


def fixed_prefix_from_template(path_template: str) -> Path:
    parts = path_template.replace("\\", "/").split("/")
    fixed_parts: list[str] = []
    for part in parts:
        if "{" in part or "*" in part:
            break
        fixed_parts.append(part)
    return Path(*fixed_parts)


def classify_role(output_id: str, entry_class: str, owner_segment: str) -> str:
    if entry_class == "gate":
        return "gate_artifact"
    if output_id in TRAFFIC_PRIMITIVES:
        return "traffic_primitives"
    if output_id in BEHAVIOURAL_STREAMS:
        return "behavioural_streams"
    if output_id in BEHAVIOURAL_CONTEXT:
        return "behavioural_context"
    if output_id in TRUTH_PRODUCTS:
        return "truth_products"
    if output_id.startswith("rng_") or output_id.startswith("gamma_draw_log") or output_id in {"s5_selection_log", "s6_edge_log"}:
        return "audit_evidence"
    if output_id.startswith("segment_state_runs_") or "_run_report" in output_id or "_run_summary" in output_id:
        return "ops_telemetry"
    if (
        output_id.startswith("sealed_inputs_")
        or output_id.startswith("validation_")
        or "validation_report" in output_id
        or "issue_table" in output_id
    ):
        return "governance_validation_surface"
    if output_id.endswith("_policy") or output_id.endswith("_config") or output_id.endswith("_model") or output_id.endswith("_prior_pack"):
        return "policy_surface"
    if owner_segment in {"6A"}:
        return "entity_context_surface"
    if owner_segment in {"5A", "5B"}:
        return "behavioural_generation_surface"
    if owner_segment in {"1A", "1B", "2A", "2B", "3A", "3B"}:
        return "authority_surface"
    if owner_segment == "6B":
        return "traffic_support_surface"
    return "other_surface"


def classify_platform_area(role: str) -> str:
    return {
        "traffic_primitives": "traffic_construction",
        "behavioural_streams": "ingestion_event_bus_and_feature_entry",
        "behavioural_context": "rtdl_and_feature_enrichment",
        "truth_products": "offline_truth_and_case_operations",
        "audit_evidence": "observability_forensics_and_replay",
        "ops_telemetry": "operations_monitoring",
        "gate_artifact": "governance_and_release_readiness",
        "governance_validation_surface": "governance_and_validation",
        "policy_surface": "governance_and_simulation_control",
        "authority_surface": "structural_world_context",
        "behavioural_generation_surface": "behaviour_and_arrival_context",
        "entity_context_surface": "entity_graph_and_offline_analytics",
        "traffic_support_surface": "traffic_context_truth_and_case_support",
        "other_surface": "mixed_or_specialized",
    }.get(role, "mixed_or_specialized")


def classify_availability(role: str) -> str:
    return {
        "traffic_primitives": "pre_canonical_traffic_stage",
        "behavioural_streams": "live_traffic_time",
        "behavioural_context": "same_cycle_context_join",
        "truth_products": "post_hoc_truth_and_case_time",
        "audit_evidence": "forensic_after_run",
        "ops_telemetry": "run_monitoring_time",
        "gate_artifact": "must_verify_before_authoritative_read",
        "governance_validation_surface": "post_build_or_post_run_validation_time",
        "policy_surface": "pre_use_governed_control_surface",
        "authority_surface": "offline_structural_context_time",
        "behavioural_generation_surface": "traffic_generation_and_context_time",
        "entity_context_surface": "offline_entity_and_network_context_time",
        "traffic_support_surface": "traffic_and_truth_support_time",
        "other_surface": "specialized_or_mixed",
    }.get(role, "specialized_or_mixed")


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    catalogue = yaml.safe_load(CATALOGUE_PATH.read_text(encoding="utf-8"))["outputs"]
    rows: list[dict[str, object]] = []

    for entry in catalogue:
        output_id = entry["output_id"]
        prefix = fixed_prefix_from_template(entry["path_template"])
        abs_prefix = RUN_ROOT / prefix
        present = abs_prefix.exists()
        rows.append(
            {
                "output_id": output_id,
                "class": entry["class"],
                "exposure": entry["exposure"],
                "scope": entry["scope"],
                "owner_segment": entry["owner_segment"],
                "path_template": entry["path_template"],
                "fixed_prefix": str(prefix).replace("\\", "/"),
                "present_in_pinned_run": present,
                "platform_role": classify_role(output_id, entry["class"], entry["owner_segment"]),
                "platform_area": classify_platform_area(
                    classify_role(output_id, entry["class"], entry["owner_segment"])
                ),
                "availability_window": classify_availability(
                    classify_role(output_id, entry["class"], entry["owner_segment"])
                ),
                "description": entry.get("description", ""),
            }
        )

    df = pd.DataFrame(rows).sort_values(["owner_segment", "output_id"]).reset_index(drop=True)
    df.to_csv(EXPORT_DIR / "interface_output_inventory.csv", index=False)

    present_df = df.loc[df["present_in_pinned_run"]].copy()
    present_df.to_csv(EXPORT_DIR / "interface_output_inventory_present_only.csv", index=False)

    summary = {
        "catalogue_outputs_total": int(len(df)),
        "present_outputs_total": int(len(present_df)),
        "missing_outputs_total": int((~df["present_in_pinned_run"]).sum()),
        "catalogue_class_counts": df["class"].value_counts().sort_index().to_dict(),
        "present_class_counts": present_df["class"].value_counts().sort_index().to_dict(),
        "present_segment_counts": present_df["owner_segment"].value_counts().sort_index().to_dict(),
        "present_role_counts": present_df["platform_role"].value_counts().sort_index().to_dict(),
        "present_area_counts": present_df["platform_area"].value_counts().sort_index().to_dict(),
    }

    focused_groups = {
        "traffic_and_context_front_door": sorted(
            [
                output_id
                for output_id in present_df["output_id"]
                if output_id in TRAFFIC_PRIMITIVES | BEHAVIOURAL_STREAMS | BEHAVIOURAL_CONTEXT
            ]
        ),
        "truth_and_case_products": sorted(
            [output_id for output_id in present_df["output_id"] if output_id in TRUTH_PRODUCTS]
        ),
        "audit_and_ops": sorted(
            [
                output_id
                for output_id in present_df["output_id"]
                if present_df.set_index("output_id").loc[output_id, "platform_role"]
                in {"audit_evidence", "ops_telemetry", "gate_artifact", "governance_validation_surface"}
            ]
        ),
    }
    summary["focused_groups"] = focused_groups

    by_area_segment: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in present_df.itertuples(index=False):
        by_area_segment[row.platform_area][row.owner_segment].append(row.output_id)

    with (EXPORT_DIR / "interface_output_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    with (EXPORT_DIR / "interface_output_mapping_by_area.json").open("w", encoding="utf-8") as handle:
        json.dump(by_area_segment, handle, indent=2)

    print("SUMMARY")
    print(json.dumps(summary, indent=2))
    print("\nPRESENT BY SEGMENT")
    print(present_df.groupby("owner_segment").size().to_string())
    print("\nPRESENT BY ROLE")
    print(present_df.groupby("platform_role").size().to_string())
    print("\nKEY FRONT-DOOR OUTPUTS")
    for output_id in focused_groups["traffic_and_context_front_door"]:
        print(output_id)


if __name__ == "__main__":
    main()
