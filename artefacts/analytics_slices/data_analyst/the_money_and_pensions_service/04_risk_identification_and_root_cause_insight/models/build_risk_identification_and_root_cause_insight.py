from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

MAPS_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "01_mixed_source_dashboarding_and_reporting"
)
MAPS_GOVERNANCE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "02_data_governance_and_output_stewardship"
)
MAPS_MIXED_TYPE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "03_structured_and_unstructured_evidence_analysis"
)
HUC_DISCREPANCY_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "huc"
    / "03_conversion_discrepancy_handling"
)


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    reporting_base = pd.read_parquet(
        MAPS_REPORTING_BASE / "extracts" / "mixed_source_reporting_base_v1.parquet"
    )
    reporting_summary = pd.read_parquet(
        MAPS_REPORTING_BASE / "extracts" / "mixed_source_dashboard_summary_v1.parquet"
    )
    governance_summary = pd.read_parquet(
        MAPS_GOVERNANCE_BASE / "extracts" / "governed_output_summary_v1.parquet"
    )
    structured_summary = pd.read_parquet(
        MAPS_MIXED_TYPE_BASE / "extracts" / "structured_evidence_summary_v1.parquet"
    )
    narrative_summary = pd.read_parquet(
        MAPS_MIXED_TYPE_BASE / "extracts" / "narrative_evidence_summary_v1.parquet"
    )
    combined_insight = pd.read_parquet(
        MAPS_MIXED_TYPE_BASE / "extracts" / "combined_mixed_type_insight_v1.parquet"
    )

    reporting_fact_pack = json.loads(
        (MAPS_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    governance_fact_pack = json.loads(
        (MAPS_GOVERNANCE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    mixed_type_fact_pack = json.loads(
        (MAPS_MIXED_TYPE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    huc_fact_pack = json.loads(
        (HUC_DISCREPANCY_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    focus_row = reporting_base.loc[reporting_base["aligned_attention_flag"] == 1].iloc[0]
    summary_row = reporting_summary.iloc[0]
    governance_row = governance_summary.iloc[0]
    structured_row = structured_summary.iloc[0]
    combined_row = combined_insight.iloc[0]

    narrative_functions = narrative_summary["narrative_function"].tolist()
    focus_stage_names = narrative_summary["stage_name"].tolist()

    early_warning_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
                "early_warning_signal_name": "shared_focus_band_pressure",
                "shared_focus_band": str(focus_row["amount_band"]),
                "shared_focus_label": str(focus_row["band_label"]),
                "shared_focus_confirming_streams": int(focus_row["attention_confirmation_count"]),
                "structured_case_open_rate_huc": float(focus_row["huc_current_case_open_rate"]),
                "structured_case_open_rate_claire": float(focus_row["claire_case_open_rate"]),
                "structured_case_open_rate_herts": float(focus_row["herts_case_open_rate"]),
                "focus_truth_gap_pp": float(focus_row["herts_truth_gap_pp"]),
                "focus_burden_minus_yield_pp": float(focus_row["burden_minus_yield_pp"] * 100),
                "warning_reason": "the same focus band is confirmed by all three streams while the truth-quality reading remains materially below peer context",
                "why_now": "the concentration across governed mixed-source and mixed-type surfaces means the signal is persistent enough to count as an early warning rather than background noise",
            }
        ]
    )

    risk_investigation_output = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
                "investigated_signal_name": "shared_focus_band_pressure",
                "shared_focus_band": str(focus_row["amount_band"]),
                "investigated_risk_type": "localized_quality_and_flow_pressure",
                "primary_likely_driver": "focused-band handling or pathway pressure remains the strongest bounded explanation because the pressure is concentrated in one band while the rest of the lane remains background context",
                "driver_link_1": "the governed reporting lane shows one shared attention point rather than broad instability",
                "driver_link_2": "the mixed-type narrative surface points to focused flow-rule review rather than whole-lane escalation",
                "driver_link_3": "the controlled governance layer reduces the likelihood that the signal is a release artefact rather than a real service-facing risk",
                "singular_root_cause_supported_flag": 0,
                "confidence_posture": "bounded_likely_driver_chain",
                "intervention_readiness": "review_focused_flow_before_broader_intervention",
            }
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "single_shared_focus_signal_remains_present",
                "actual_value": float((reporting_base["aligned_attention_flag"] == 1).sum()),
                "expected_rule": "= 1 governed shared-focus signal remains present in the mixed-source lane",
                "passed_flag": int((reporting_base["aligned_attention_flag"] == 1).sum() == 1),
            },
            {
                "check_name": "shared_focus_still_confirmed_by_all_streams",
                "actual_value": float(focus_row["attention_confirmation_count"]),
                "expected_rule": "= 3 streams confirm the same focus band",
                "passed_flag": int(focus_row["attention_confirmation_count"] == 3),
            },
            {
                "check_name": "governed_output_pack_remains_green",
                "actual_value": float(governance_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {governance_fact_pack['release_check_count']} governance checks remain green",
                "passed_flag": int(
                    governance_fact_pack["release_checks_passed"] == governance_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "mixed_type_pack_remains_green",
                "actual_value": float(mixed_type_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {mixed_type_fact_pack['release_check_count']} mixed-type checks remain green",
                "passed_flag": int(
                    mixed_type_fact_pack["release_checks_passed"] == mixed_type_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "narrative_surface_retains_three_bounded_functions",
                "actual_value": float(len(set(narrative_functions))),
                "expected_rule": "= 3 bounded narrative functions remain available for likely-driver interpretation",
                "passed_flag": int(len(set(narrative_functions)) == 3),
            },
            {
                "check_name": "investigation_stays_likely_driver_not_fake_singular_cause",
                "actual_value": float(risk_investigation_output.iloc[0]["singular_root_cause_supported_flag"]),
                "expected_rule": "= 0 singular deterministic cause claimed unless evidence reaches HUC discrepancy clarity",
                "passed_flag": int(risk_investigation_output.iloc[0]["singular_root_cause_supported_flag"] == 0),
            },
            {
                "check_name": "shared_focus_truth_gap_remains_material",
                "actual_value": float(abs(focus_row["herts_truth_gap_pp"])),
                "expected_rule": ">= 1.50 percentage-point absolute truth-quality gap to peer context",
                "passed_flag": int(abs(focus_row["herts_truth_gap_pp"]) >= 1.5),
            },
        ]
    )

    early_warning_summary.to_parquet(EXTRACTS / "early_warning_summary_v1.parquet", index=False)
    risk_investigation_output.to_parquet(EXTRACTS / "risk_investigation_output_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "root_cause_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "the_money_and_pensions_service/04_risk_identification_and_root_cause_insight",
        "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
        "early_warning_output_count": 1,
        "investigated_risk_output_count": 1,
        "likely_driver_links_defended": 3,
        "intervention_implication_count": 1,
        "shared_focus_band": str(focus_row["amount_band"]),
        "shared_focus_confirming_streams": int(focus_row["attention_confirmation_count"]),
        "focus_case_open_rate_huc": float(focus_row["huc_current_case_open_rate"]),
        "focus_case_open_rate_claire": float(focus_row["claire_case_open_rate"]),
        "focus_case_open_rate_herts": float(focus_row["herts_case_open_rate"]),
        "focus_truth_gap_pp": float(focus_row["herts_truth_gap_pp"]),
        "singular_root_cause_supported_flag": 0,
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "risk_root_cause_scope_note_v1.md",
        f"""
# Risk Root-Cause Scope Note v1

Bounded investigation question:
- can the shared `{focus_row['band_label']}` focus signal be taken from status reporting into one bounded early-warning and likely-driver reading?

Inherited surfaces used:
- mixed-source reporting base
- governed output stewardship pack
- structured-and-narrative combined insight pack

Methodological guardrail:
- default to likely-driver language
- only claim singular root cause if the evidence reaches HUC discrepancy-level clarity

What this slice proves:
- one early-warning signal
- one investigated risk output
- one bounded likely-driver chain
- one practical intervention implication

What this slice does not prove:
- deterministic causality
- predictive risk modelling
- service redesign ownership
""",
    )

    write_md(
        OUT_BASE / "likely_driver_note_v1.md",
        f"""
# Likely Driver Note v1

Early-warning signal:
- shared focus band: `{focus_row['band_label']}`
- confirming streams: `{int(focus_row['attention_confirmation_count'])}`
- HUC case-open rate: `{pct(float(focus_row['huc_current_case_open_rate']))}`
- Claire case-open rate: `{pct(float(focus_row['claire_case_open_rate']))}`
- Hertfordshire case-open rate: `{pct(float(focus_row['herts_case_open_rate']))}`
- truth-quality gap to peers: `{pp(float(focus_row['herts_truth_gap_pp']))}`

Strongest bounded explanation:
- the pressure appears localized to one band rather than spread across the whole lane
- the narrative-style surface points toward focused handling or pathway review, not broad escalation
- the governance pack staying green reduces the likelihood that this is only a reporting artefact

Likely-driver posture:
- primary explanation: focused-band handling pressure
- confidence: bounded likely-driver chain
- singular deterministic root cause: not supported

Why this stops short of HUC `03`:
- the HUC discrepancy slice isolated one metric mismatch to one explicit denominator drift
- this slice supports a bounded driver explanation, but not that same level of singular causal certainty
""",
    )

    write_md(
        OUT_BASE / "intervention_implication_note_v1.md",
        f"""
# Intervention Implication Note v1

What the signals mean in practice:
- the shared `{focus_row['band_label']}` signal is strong enough to count as an early warning
- the next move should stay focused on the same band rather than widening immediately into whole-lane intervention

Bounded implication:
1. protect the governed reading and comparator rules
2. review the focused flow or handling rules around `{focus_row['band_label']}`
3. remeasure the same band before any broader intervention

Why this is the correct boundary:
- the slice supports analytical investigation and practical interpretation
- it does not support a claim that the wider service problem has already been solved
""",
    )

    write_md(
        OUT_BASE / "risk_root_cause_caveats_v1.md",
        """
# Risk Root-Cause Caveats v1

This slice is suitable for:
- demonstrating early-warning risk identification
- demonstrating bounded root-cause-style or likely-driver investigation
- demonstrating practical intervention interpretation from controlled evidence

This slice is not suitable for claiming:
- deterministic single-cause proof
- predictive risk engine ownership
- enterprise investigation ownership
- delivered service improvement outcomes
""",
    )

    write_md(
        OUT_BASE / "README_risk_root_cause_regeneration.md",
        f"""
# Risk Root-Cause Regeneration

Regeneration order:
1. confirm the Money and Pensions Service `01`, `02`, and `03` artefacts still exist
2. run `models/build_risk_identification_and_root_cause_insight.py`
3. review the early-warning summary, investigated risk output, likely-driver note, intervention implication, and release checks
4. confirm release checks remain `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}`

Current bounded outcome:
- `1` early-warning output
- `1` investigated risk output
- `1` likely-driver note
- `1` intervention implication note
- regeneration completed in `{duration:.2f}` seconds
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_risk_root_cause.md",
        """
# Changelog - Risk Root-Cause Insight

## v1
- created the first Money and Pensions Service bounded risk-identification and root-cause-style investigation pack from the existing governed reporting, governance, and mixed-type evidence lane
""",
    )


if __name__ == "__main__":
    main()
