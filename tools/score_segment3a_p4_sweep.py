#!/usr/bin/env python3
"""Score Segment 3A P4 candidate sweep for S1 escalation-shape remediation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_candidate_metrics(reports_root: Path, run_id: str) -> dict[str, Any]:
    payload = _load_json(reports_root / f"segment3a_p0_candidate_vs_baseline_{run_id}.json")
    return payload["candidate"]


def _load_s6s7_status(runs_root: Path, run_id: str, seed: int, manifest_fingerprint: str) -> tuple[bool, bool]:
    s6_path = (
        runs_root
        / run_id
        / "reports"
        / "layer1"
        / "3A"
        / "state=S6"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "run_report.json"
    )
    s7_path = (
        runs_root
        / run_id
        / "reports"
        / "layer1"
        / "3A"
        / "state=S7"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "run_report.json"
    )
    s6 = _load_json(s6_path)
    s7 = _load_json(s7_path)
    s6_pass = str(s6.get("overall_status")) == "PASS"
    s7_pass = str(s7.get("status")) == "PASS"
    return s6_pass, s7_pass


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Segment 3A P4 Sweep Summary")
    lines.append("")
    lines.append(f"- anchor_run_id: `{payload['anchor_run_id']}`")
    lines.append(f"- decision: `{payload['decision']}`")
    selected = payload.get("selected_candidate")
    if selected:
        lines.append(f"- selected_variant: `{selected['variant']}`")
        lines.append(f"- selected_run_id: `{selected['run_id']}`")
        lines.append(f"- selected_J4: `{selected['J4']:+.6f}`")
    lines.append("")
    lines.append("## Ranked Candidates")
    lines.append("")
    for row in payload["ranked_candidates"]:
        veto = ",".join(row["veto_reasons"]) if row["veto_reasons"] else "NONE"
        lines.append(
            f"- {row['variant']} run `{row['run_id']}`: J4 `{row['J4']:+.6f}`, "
            f"dip `{row['s1']['major_dip_max_abs']:.6f}`, mono_viol `{row['s1']['monotonic_violations']}`, "
            f"phase_target `{row['phase_target_pass']}`, veto `{veto}`"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Decision `P4_POLICY_LOCK` means policy-only lane met P4 target envelope.")
    lines.append("- Decision `P4_NEEDS_CODE_SMOOTHING` means policy-only lane did not meet target envelope.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 3A P4 sweep candidates.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3A")
    parser.add_argument("--reports-root", default="runs/fix-data-engine/segment_3A/reports")
    parser.add_argument("--matrix-json", required=True)
    parser.add_argument("--anchor-run-id", default="3f2e94f2d1504c249e434949659a496f")
    parser.add_argument("--out-json", default="runs/fix-data-engine/segment_3A/reports/segment3a_p4_3_sweep_summary.json")
    parser.add_argument("--out-md", default="runs/fix-data-engine/segment_3A/reports/segment3a_p4_3_sweep_summary.md")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    reports_root = Path(args.reports_root)
    matrix = _load_json(Path(args.matrix_json))
    candidates = list(matrix.get("results", []))
    if not candidates:
        raise ValueError("matrix-json has no results")

    anchor = _load_candidate_metrics(reports_root, args.anchor_run_id)
    anchor_s1 = anchor["metrics"]["s1"]

    ranked: list[dict[str, Any]] = []
    for item in candidates:
        run_id = str(item["run_id"])
        cand = _load_candidate_metrics(reports_root, run_id)
        metrics = cand["metrics"]
        seed = int(cand["seed"])
        manifest_fingerprint = str(cand["manifest_fingerprint"])
        s6_pass, s7_pass = _load_s6s7_status(runs_root, run_id, seed, manifest_fingerprint)

        s1 = metrics["s1"]
        s3 = metrics["s3"]
        s4 = metrics["s4"]
        za = metrics["zone_alloc"]

        d_s1_dip_down = float(anchor_s1["zone_count_curve_major_dip_max_abs"]) - float(
            s1["zone_count_curve_major_dip_max_abs"]
        )
        d_s1_mono_viol_down = float(anchor_s1["zone_count_curve_monotonic_violations"]) - float(
            s1["zone_count_curve_monotonic_violations"]
        )
        j4 = 0.70 * d_s1_dip_down + 0.30 * d_s1_mono_viol_down

        phase_target_pass = bool(
            float(s1["zone_count_curve_major_dip_max_abs"]) <= 0.20
            and int(s1["zone_count_curve_monotonic_violations"]) <= 2
        )
        rails_ok = bool(
            float(s3["merchant_share_std_median"]) >= 0.020
            and float(s4["escalated_multi_zone_rate"]) >= 0.85
            and float(s4["top1_share_median"]) <= 0.80
            and float(za["top1_share_median"]) <= 0.80
            and bool(s4["count_conservation_all_pairs"])
            and bool(za["count_conservation_all_pairs"])
        )
        veto_reasons: list[str] = []
        if not s6_pass or not s7_pass:
            veto_reasons.append("S6_OR_S7_FAIL")
        if not rails_ok:
            veto_reasons.append("NON_REGRESSION_RAIL_BREACH")

        ranked.append(
            {
                "variant": str(item["variant"]),
                "run_id": run_id,
                "seed": seed,
                "knobs": item.get("knobs", {}),
                "s1": {
                    "major_dip_max_abs": float(s1["zone_count_curve_major_dip_max_abs"]),
                    "major_dip_count_gt_010": int(s1["zone_count_curve_major_dip_count_gt_010"]),
                    "monotonic_violations": int(s1["zone_count_curve_monotonic_violations"]),
                    "escalation_rate": float(s1["escalation_rate"]),
                },
                "rails": {
                    "s3_std": float(s3["merchant_share_std_median"]),
                    "s4_multi_zone": float(s4["escalated_multi_zone_rate"]),
                    "s4_top1": float(s4["top1_share_median"]),
                    "zone_alloc_top1": float(za["top1_share_median"]),
                    "s4_conservation": bool(s4["count_conservation_all_pairs"]),
                    "zone_alloc_conservation": bool(za["count_conservation_all_pairs"]),
                    "s6_pass": s6_pass,
                    "s7_pass": s7_pass,
                },
                "delta_vs_anchor": {
                    "d_s1_dip_down": d_s1_dip_down,
                    "d_s1_mono_viol_down": d_s1_mono_viol_down,
                },
                "J4": j4,
                "phase_target_pass": phase_target_pass,
                "veto_reasons": veto_reasons,
                "promotable": len(veto_reasons) == 0,
            }
        )

    ranked.sort(key=lambda row: row["J4"], reverse=True)
    promotable = [row for row in ranked if row["promotable"]]
    selected = promotable[0] if promotable else None
    decision = "P4_NEEDS_CODE_SMOOTHING"
    if selected is not None and selected["phase_target_pass"]:
        decision = "P4_POLICY_LOCK"

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P4.3",
        "segment": "3A",
        "anchor_run_id": args.anchor_run_id,
        "decision": decision,
        "ranked_candidates": ranked,
        "selected_candidate": selected,
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))
    print(decision)
    if selected is not None:
        print(selected["run_id"])


if __name__ == "__main__":
    main()
