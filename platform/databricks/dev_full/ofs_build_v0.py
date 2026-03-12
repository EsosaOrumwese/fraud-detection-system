from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from pyspark.sql import functions as F


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_param(name: str, default: str = "") -> str:
    try:
        value = dbutils.widgets.get(name)  # type: ignore[name-defined]  # noqa: F821
        if value is not None:
            return str(value).strip()
    except Exception:
        pass
    return str(os.getenv(name, default)).strip()


def _read_text(path: str) -> str:
    try:
        content = dbutils.fs.head(path, 4096)  # type: ignore[name-defined]  # noqa: F821
        if content is not None:
            return str(content).strip()
    except Exception:
        pass
    rows = spark.read.text(path).limit(1).collect()  # type: ignore[name-defined]  # noqa: F821
    if rows:
        return str(rows[0][0]).strip()
    binary_rows = spark.read.format("binaryFile").load(path).limit(1).collect()  # type: ignore[name-defined]  # noqa: F821
    if not binary_rows:
        raise RuntimeError(f"text_unreadable:{path}")
    content = binary_rows[0].asDict(recursive=True).get("content")
    if content is None:
        return ""
    if isinstance(content, (bytes, bytearray)):
        return bytes(content).decode("utf-8", errors="replace").strip()
    return str(content).strip()


def _read_json(path: str) -> dict:
    rows = spark.read.option("multiline", "true").json(path).limit(1).collect()  # type: ignore[name-defined]  # noqa: F821
    if not rows:
        raise RuntimeError(f"json_unreadable:{path}")
    payload = rows[0].asDict(recursive=True)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def _list_schema_fields(df) -> list[str]:
    return [str(field.name) for field in df.schema.fields]


def _sample_row(df, columns: list[str]) -> dict:
    row = df.select(*columns).limit(1).collect()
    if not row:
        return {}
    return row[0].asDict(recursive=True)


def main() -> None:
    spec_json = _get_param("phase5_spec_json")
    if not spec_json:
        raise RuntimeError("PHASE5B_SPEC_JSON_REQUIRED")

    spec = json.loads(spec_json)
    facts = _read_json(str(spec.get("facts_view_ref") or ""))
    validation = _read_json(str(spec.get("sixb_validation_report_ref") or ""))
    passed_flag = _read_text(str(spec.get("sixb_passed_flag_ref") or ""))

    event_path = str(((spec.get("slice_files") or {}).get("events")) or "").strip()
    event_labels_path = str(((spec.get("slice_files") or {}).get("event_labels")) or "").strip()
    flow_labels_path = str(((spec.get("slice_files") or {}).get("flow_truth_labels")) or "").strip()
    case_timeline_path = str(((spec.get("slice_files") or {}).get("case_timeline")) or "").strip()
    label_asof_utc = str(spec.get("label_asof_utc") or "").strip()

    if not event_path or not event_labels_path or not flow_labels_path or not case_timeline_path:
        raise RuntimeError("PHASE5B_SLICE_FILES_UNRESOLVED")

    events_df = spark.read.parquet(event_path)  # type: ignore[name-defined]  # noqa: F821
    event_labels_df = spark.read.parquet(event_labels_path)  # type: ignore[name-defined]  # noqa: F821
    flow_labels_df = spark.read.parquet(flow_labels_path)  # type: ignore[name-defined]  # noqa: F821
    case_timeline_df = spark.read.parquet(case_timeline_path)  # type: ignore[name-defined]  # noqa: F821

    event_metrics = events_df.agg(
        F.count("*").alias("row_count"),
        F.min("ts_utc").alias("min_ts_utc"),
        F.max("ts_utc").alias("max_ts_utc"),
        F.sum(F.when(F.col("fraud_flag") == True, F.lit(1)).otherwise(F.lit(0))).alias("fraud_event_count"),  # noqa: E712
        F.countDistinct("campaign_id").alias("distinct_campaign_count"),
    ).collect()[0]
    event_label_metrics = event_labels_df.agg(
        F.count("*").alias("row_count"),
        F.sum(F.when(F.col("is_fraud_truth") == True, F.lit(1)).otherwise(F.lit(0))).alias("fraud_truth_event_count"),  # noqa: E712
    ).collect()[0]
    flow_label_metrics = flow_labels_df.agg(
        F.count("*").alias("row_count"),
        F.sum(F.when(F.col("is_fraud_truth") == True, F.lit(1)).otherwise(F.lit(0))).alias("fraud_truth_flow_count"),  # noqa: E712
        F.countDistinct("fraud_label").alias("distinct_flow_label_values"),
    ).collect()[0]
    case_metrics = case_timeline_df.agg(
        F.count("*").alias("row_count"),
        F.countDistinct("case_id").alias("distinct_case_count"),
        F.min("ts_utc").alias("min_ts_utc"),
        F.max("ts_utc").alias("max_ts_utc"),
    ).collect()[0]

    build_snapshot = {
        "phase": "PHASE5",
        "subphase": "PHASE5B_BUILD",
        "generated_at_utc": now_utc(),
        "execution_id": str(spec.get("execution_id") or "").strip(),
        "platform_run_id": str(spec.get("platform_run_id") or "").strip(),
        "scenario_run_id": str(spec.get("scenario_run_id") or "").strip(),
        "phase5a_execution_id": str(spec.get("phase5a_execution_id") or "").strip(),
        "semantic_basis": {
            "facts_view_ref": str(spec.get("facts_view_ref") or "").strip(),
            "intended_outputs": list(facts.get("intended_outputs") or []),
            "output_roles": dict(facts.get("output_roles") or {}),
            "sixb_passed_flag_ref": str(spec.get("sixb_passed_flag_ref") or "").strip(),
            "sixb_passed_flag_sha256_hex": passed_flag,
            "sixb_validation_report_ref": str(spec.get("sixb_validation_report_ref") or "").strip(),
            "sixb_validation_status": str(validation.get("overall_status") or "").strip().upper(),
            "sixb_validation_checks": {
                str(row.get("name") or row.get("check_id") or "").strip(): str(row.get("result") or row.get("status") or "").strip().upper()
                for row in (validation.get("checks") or [])
                if isinstance(row, dict)
            },
            "label_asof_utc": label_asof_utc,
            "label_maturity_days": int(spec.get("label_maturity_days") or 0),
        },
        "slice_files": {
            "events": event_path,
            "event_labels": event_labels_path,
            "flow_truth_labels": flow_labels_path,
            "case_timeline": case_timeline_path,
        },
        "slice_metrics": {
            "events": {
                "row_count": int(event_metrics["row_count"]),
                "min_ts_utc": str(event_metrics["min_ts_utc"]),
                "max_ts_utc": str(event_metrics["max_ts_utc"]),
                "fraud_event_count": int(event_metrics["fraud_event_count"] or 0),
                "distinct_campaign_count": int(event_metrics["distinct_campaign_count"] or 0),
                "schema_fields": _list_schema_fields(events_df),
                "sample_row": _sample_row(
                    events_df,
                    ["flow_id", "event_seq", "event_type", "ts_utc", "amount", "fraud_flag", "campaign_id"],
                ),
            },
            "event_labels": {
                "row_count": int(event_label_metrics["row_count"]),
                "fraud_truth_event_count": int(event_label_metrics["fraud_truth_event_count"] or 0),
                "schema_fields": _list_schema_fields(event_labels_df),
                "sample_row": _sample_row(
                    event_labels_df,
                    ["flow_id", "event_seq", "is_fraud_truth", "is_fraud_bank_view"],
                ),
            },
            "flow_truth_labels": {
                "row_count": int(flow_label_metrics["row_count"]),
                "fraud_truth_flow_count": int(flow_label_metrics["fraud_truth_flow_count"] or 0),
                "distinct_flow_label_values": int(flow_label_metrics["distinct_flow_label_values"] or 0),
                "schema_fields": _list_schema_fields(flow_labels_df),
                "sample_row": _sample_row(
                    flow_labels_df,
                    ["flow_id", "is_fraud_truth", "fraud_label"],
                ),
            },
            "case_timeline": {
                "row_count": int(case_metrics["row_count"]),
                "distinct_case_count": int(case_metrics["distinct_case_count"] or 0),
                "min_ts_utc": str(case_metrics["min_ts_utc"]),
                "max_ts_utc": str(case_metrics["max_ts_utc"]),
                "schema_fields": _list_schema_fields(case_timeline_df),
                "sample_row": _sample_row(
                    case_timeline_df,
                    ["case_id", "case_event_seq", "flow_id", "case_event_type", "ts_utc"],
                ),
            },
        },
        "notes": [
            "This Databricks build source now performs a bounded current-world OFS dataset-basis probe instead of a bootstrap-only liveness marker.",
            "The build emits current-world slice metrics so the paired quality gate can score admissibility, parity, time-bound safety, and supervision usefulness explicitly.",
        ],
    }
    print(json.dumps(build_snapshot, ensure_ascii=True))
    try:
        dbutils.notebook.exit(json.dumps(build_snapshot, ensure_ascii=True))  # type: ignore[name-defined]  # noqa: F821
    except Exception:
        pass


if __name__ == "__main__":
    main()
