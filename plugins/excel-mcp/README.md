# Excel MCP

`excel-mcp` gives Codex an Excel-shaped working surface that fits the BI and reporting claims repeated across the outward-facing materials:

- advanced `Excel` use for reporting, checking, reconciliation, and presentation
- repeatable KPI packs and trusted reporting outputs
- practical movement from governed data to audience-ready workbook deliverables

What it currently supports:

- local `.xlsx`, `.csv`, `.parquet`, and `.json` dataset inspection
- workbook/sheet reads and writes
- sheet profiling and QA summaries
- reporting-pack workbook generation from one governed input dataset
- Microsoft Graph workbook reads and writes when `MS_GRAPH_ACCESS_TOKEN` is set

Environment:

- local workbook tools use the project `.venv`
- Microsoft 365 workbook tools require `MS_GRAPH_ACCESS_TOKEN`

Planned boundary:

- this server supports bounded, interview-defensible workbook work
- it does not claim enterprise Excel admin ownership or SharePoint estate design
