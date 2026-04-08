from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from mcp.server.fastmcp import FastMCP


SERVER = FastMCP(
    "powerbi-mcp",
    instructions=(
        "Power BI metadata and blueprint tooling for governed BI/reporting proof surfaces."
    ),
    json_response=True,
)


def _normalize_path(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _coerce_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    if pd.isna(value):
        return None
    return value


def _load_tabular_data(path_text: str) -> pd.DataFrame:
    path = _normalize_path(path_text)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(path, lines=(suffix == ".jsonl"))
    if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file extension: {suffix}")


def _powerbi_headers() -> dict[str, str]:
    token = os.environ.get("POWERBI_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("POWERBI_ACCESS_TOKEN is not set.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _powerbi_get(path: str) -> dict[str, Any]:
    response = requests.get(
        f"https://api.powerbi.com/v1.0/myorg/{path.lstrip('/')}",
        headers=_powerbi_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _infer_roles(
    df: pd.DataFrame,
    date_column: str | None,
    dimension_columns: list[str],
    metric_columns: list[str],
) -> pd.DataFrame:
    inferred_date = date_column
    if not inferred_date:
        for column in df.columns:
            column_name = str(column).lower()
            if "date" in column_name or "time" in column_name:
                inferred_date = str(column)
                break
    inferred_dimensions = [column for column in dimension_columns if column in df.columns]
    if not inferred_dimensions:
        inferred_dimensions = [
            str(column)
            for column in df.columns
            if not pd.api.types.is_numeric_dtype(df[column]) and str(column) != inferred_date
        ][:6]
    inferred_metrics = [column for column in metric_columns if column in df.columns]
    if not inferred_metrics:
        inferred_metrics = [str(column) for column in df.select_dtypes(include=["number"]).columns]

    rows: list[dict[str, Any]] = []
    for column in df.columns:
        role = "attribute"
        if str(column) == inferred_date:
            role = "date"
        elif str(column) in inferred_dimensions:
            role = "dimension"
        elif str(column) in inferred_metrics:
            role = "measure_input"
        rows.append(
            {
                "column": str(column),
                "dtype": str(df[column].dtype),
                "role": role,
                "nulls": int(df[column].isna().sum()),
                "distinct_non_null": int(df[column].dropna().nunique()),
            }
        )
    return pd.DataFrame(rows)


def _build_measure_catalog(
    table_name: str,
    metric_columns: list[str],
    dimension_columns: list[str],
    date_column: str | None,
) -> list[dict[str, str]]:
    measures: list[dict[str, str]] = [
        {
            "measure_name": "Rows",
            "expression": f"COUNTROWS('{table_name}')",
            "purpose": "Record count.",
        }
    ]
    for column in metric_columns:
        measures.extend(
            [
                {
                    "measure_name": f"Total {column}",
                    "expression": f"SUM('{table_name}'[{column}])",
                    "purpose": f"Total {column} across current filter context.",
                },
                {
                    "measure_name": f"Average {column}",
                    "expression": f"AVERAGE('{table_name}'[{column}])",
                    "purpose": f"Average {column} across current filter context.",
                },
                {
                    "measure_name": f"Max {column}",
                    "expression": f"MAX('{table_name}'[{column}])",
                    "purpose": f"Maximum observed {column}.",
                },
            ]
        )
    for column in dimension_columns[:3]:
        measures.append(
            {
                "measure_name": f"Distinct {column}",
                "expression": f"DISTINCTCOUNT('{table_name}'[{column}])",
                "purpose": f"Distinct count of {column}.",
            }
        )
    if date_column and metric_columns:
        base_measure = f"[Total {metric_columns[0]}]"
        measures.append(
            {
                "measure_name": f"Latest {metric_columns[0]}",
                "expression": (
                    f"VAR LatestDate = MAX('{table_name}'[{date_column}]) "
                    f"RETURN CALCULATE({base_measure}, '{table_name}'[{date_column}] = LatestDate)"
                ),
                "purpose": "Latest period value for the lead metric.",
            }
        )
    return measures


def _build_m_query(source_path: Path, table_name: str) -> str:
    escaped = str(source_path).replace("\\", "\\\\")
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        return (
            "let\n"
            f"    Source = Csv.Document(File.Contents(\"{escaped}\"), [Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n"
            "    PromoteHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])\n"
            "in\n"
            "    PromoteHeaders"
        )
    if suffix == ".parquet":
        return (
            "let\n"
            f"    Source = Parquet.Document(File.Contents(\"{escaped}\"))\n"
            "in\n"
            "    Source"
        )
    if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return (
            "let\n"
            f"    Source = Excel.Workbook(File.Contents(\"{escaped}\"), null, true),\n"
            f"    {table_name} = Source{{0}}[Data],\n"
            f"    PromoteHeaders = Table.PromoteHeaders({table_name}, [PromoteAllScalars=true])\n"
            "in\n"
            "    PromoteHeaders"
        )
    return (
        "let\n"
        f"    Source = Json.Document(File.Contents(\"{escaped}\"))\n"
        "in\n"
        "    Source"
    )


def _page_specs(
    dimension_columns: list[str],
    metric_columns: list[str],
    date_column: str | None,
) -> list[dict[str, Any]]:
    lead_metric = metric_columns[0] if metric_columns else "Rows"
    pages = [
        {
            "page": "01 Executive Overview",
            "audience": "Leadership",
            "goal": "High-level KPI position and movement.",
            "visuals": [
                f"KPI cards for Rows and Total {lead_metric}",
                "Exception summary table",
                "Narrative callout for the main change driver",
            ],
        },
        {
            "page": "02 Operational Trend",
            "audience": "Operations",
            "goal": "Show direction of travel and recent pressure.",
            "visuals": [
                f"Line chart by {date_column or 'period'} for Total {lead_metric}",
                "Segmented bar chart for current state mix",
                "Filter panel for core dimensions",
            ],
        },
        {
            "page": "03 Quality And Exceptions",
            "audience": "Analyst / Governance",
            "goal": "Keep trust conditions visible before wider reuse.",
            "visuals": [
                "QA table for nulls, duplicates, and caveats",
                "Dimension completeness heatmap",
                "Outlier review matrix",
            ],
        },
    ]
    if dimension_columns:
        pages.append(
            {
                "page": "04 Segment Drilldown",
                "audience": "Analyst",
                "goal": "Find concentration and segment-specific drivers.",
                "visuals": [
                    f"Top-N bar chart by {dimension_columns[0]}",
                    "Detail table with cross-filtering",
                    "Variance view versus overall average",
                ],
            }
        )
    return pages


@SERVER.tool()
def powerbi_list_workspaces() -> dict[str, Any]:
    """List accessible Power BI workspaces."""
    payload = _powerbi_get("groups")
    return {
        "workspace_count": len(payload.get("value", [])),
        "workspaces": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "is_read_only": item.get("isReadOnly"),
                "is_on_dedicated_capacity": item.get("isOnDedicatedCapacity"),
            }
            for item in payload.get("value", [])
        ],
    }


@SERVER.tool()
def powerbi_list_datasets(workspace_id: str) -> dict[str, Any]:
    """List datasets in a Power BI workspace."""
    payload = _powerbi_get(f"groups/{workspace_id}/datasets")
    return {
        "workspace_id": workspace_id,
        "dataset_count": len(payload.get("value", [])),
        "datasets": payload.get("value", []),
    }


@SERVER.tool()
def powerbi_list_reports(workspace_id: str) -> dict[str, Any]:
    """List reports in a Power BI workspace."""
    payload = _powerbi_get(f"groups/{workspace_id}/reports")
    return {
        "workspace_id": workspace_id,
        "report_count": len(payload.get("value", [])),
        "reports": payload.get("value", []),
    }


@SERVER.tool()
def powerbi_list_report_pages(workspace_id: str, report_id: str) -> dict[str, Any]:
    """List pages for a report in a Power BI workspace."""
    payload = _powerbi_get(f"groups/{workspace_id}/reports/{report_id}/pages")
    return {
        "workspace_id": workspace_id,
        "report_id": report_id,
        "page_count": len(payload.get("value", [])),
        "pages": payload.get("value", []),
    }


@SERVER.tool()
def powerbi_get_refresh_history(workspace_id: str, dataset_id: str, top: int = 10) -> dict[str, Any]:
    """Get Power BI dataset refresh history."""
    payload = _powerbi_get(f"groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top={top}")
    return {
        "workspace_id": workspace_id,
        "dataset_id": dataset_id,
        "refreshes": payload.get("value", []),
    }


@SERVER.tool()
def powerbi_generate_semantic_blueprint(
    source_path: str,
    output_dir: str,
    model_name: str,
    date_column: str | None = None,
    dimension_columns: list[str] | None = None,
    metric_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Generate Power BI-ready semantic and reporting blueprint files from a governed dataset."""
    input_path = _normalize_path(source_path)
    df = _load_tabular_data(source_path)
    roles_df = _infer_roles(df, date_column, dimension_columns or [], metric_columns or [])
    role_rows = roles_df.to_dict(orient="records")
    resolved_date = next((row["column"] for row in role_rows if row["role"] == "date"), None)
    resolved_dims = [row["column"] for row in role_rows if row["role"] == "dimension"]
    resolved_metrics = [row["column"] for row in role_rows if row["role"] == "measure_input"]
    measures = _build_measure_catalog(model_name, resolved_metrics, resolved_dims, resolved_date)
    pages = _page_specs(resolved_dims, resolved_metrics, resolved_date)

    qa_rows = [
        {"check": "row_count", "value": int(len(df)), "status": "info"},
        {"check": "column_count", "value": int(len(df.columns)), "status": "info"},
        {"check": "duplicate_rows", "value": int(df.duplicated().sum()), "status": "warn"},
    ]

    destination = _normalize_path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "model_columns.csv").write_text(roles_df.to_csv(index=False), encoding="utf-8")
    (destination / "measures.dax").write_text(
        "\n\n".join(
            f"{measure['measure_name']} = {measure['expression']}\n// {measure['purpose']}"
            for measure in measures
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "power_query.m").write_text(_build_m_query(input_path, model_name) + "\n", encoding="utf-8")
    (destination / "report_pages.json").write_text(json.dumps(pages, indent=2) + "\n", encoding="utf-8")
    (destination / "semantic_model.json").write_text(
        json.dumps(
            {
                "model_name": model_name,
                "table_name": model_name,
                "date_column": resolved_date,
                "dimension_columns": resolved_dims,
                "metric_columns": resolved_metrics,
                "relationships": [],
                "measures": measures,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "theme.json").write_text(
        json.dumps(
            {
                "name": f"{model_name} Theme",
                "foreground": "#1F1F1F",
                "background": "#F7F7F7",
                "dataColors": ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "qa_checks.json").write_text(json.dumps(qa_rows, indent=2) + "\n", encoding="utf-8")
    (destination / "README.md").write_text(
        (
            f"# {model_name} Power BI Blueprint\n\n"
            f"Source dataset: `{input_path}`\n\n"
            "Generated files:\n"
            "- `model_columns.csv`\n"
            "- `measures.dax`\n"
            "- `power_query.m`\n"
            "- `report_pages.json`\n"
            "- `semantic_model.json`\n"
            "- `theme.json`\n"
            "- `qa_checks.json`\n"
        ),
        encoding="utf-8",
    )

    return {
        "source_path": str(input_path),
        "output_dir": str(destination),
        "model_name": model_name,
        "row_count": int(len(df)),
        "dimension_columns": resolved_dims,
        "metric_columns": resolved_metrics,
        "date_column": resolved_date,
        "files_created": [
            "README.md",
            "model_columns.csv",
            "measures.dax",
            "power_query.m",
            "report_pages.json",
            "semantic_model.json",
            "theme.json",
            "qa_checks.json",
        ],
    }


if __name__ == "__main__":
    SERVER.run()
