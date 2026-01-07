# Implementation Readbacks

## Purpose
Implementation readbacks are implementer-authored execution walkthroughs that
sit between the binding specs/contracts and the code. They force an explicit,
reviewable operational story of how a segment/state will run so design drift is
caught before implementation.

## Authority and scope
- Binding sources remain the specs and contracts under `docs/model_spec/`.
- Readbacks are derived descriptions, not new requirements.
- If a spec ambiguity forces an assumption, record it and raise it for review.

## Decisions (to prevent drift)
- Granularity: one document per segment with per-state subsections.
- Location: `docs/implementation_readbacks/` is the canonical home.
- Format: execution spine + step-by-step expansion in run order.
- Gaps: label explicitly as `UNSPECIFIED` or `ASSUMPTION (needs approval)`.
- Traceability: lightweight references; keep citations minimal and focused.
- Review gate: steps are reviewed before implementation or closure.
- Depth: detailed walkthroughs are encouraged; no length limit.

## Workflow
1. Draft the execution spine (ordered steps only).
2. Expand one step at a time into a numbered run procedure, in detail.
3. Flag gaps/assumptions explicitly; do not invent missing behavior.
4. Review and approve step narratives before coding those steps.

## File naming
Use `layerX-seg-YY-execution-walkthrough.md`, for example:
- `layer1-seg-1A-execution-walkthrough.md`
- `layer2-seg-5B-execution-walkthrough.md`

## Update rules
- Update readbacks when binding specs or contracts change.
- Note unresolved questions and deviations explicitly.
- Log decision changes in the logbook before implementation changes land.
