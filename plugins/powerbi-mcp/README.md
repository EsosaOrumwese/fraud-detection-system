# Power BI MCP

`powerbi-mcp` gives Codex a Power-BI-shaped surface that matches the repo's BI, dashboarding, KPI-semantics, and decision-support claims without overstating enterprise ownership.

What it currently supports:

- Power BI service metadata reads when `POWERBI_ACCESS_TOKEN` is set
- workspace, dataset, report, page, and refresh-history inspection
- local semantic-model blueprint generation from governed datasets
- generated `DAX`, Power Query `M`, theme, page-spec, and QA-support files for interview prep and proof-surface work

Environment:

- service API tools require `POWERBI_ACCESS_TOKEN`
- local blueprint tools only require the project `.venv`

Planned boundary:

- this is aimed at report/product design, semantic logic, and governed output support
- it does not yet create or publish full `.pbix`/`.pbip` projects automatically
