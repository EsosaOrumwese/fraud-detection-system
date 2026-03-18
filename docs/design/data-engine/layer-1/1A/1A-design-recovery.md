Segment `1A` design recovery

These Mermaid flowcharts replace the deleted DAGs for `1A`.

They are not raw IO diagrams.

They are recovered design diagrams built from three surfaces together:

- state intent from [state-flow/1A](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/model_spec/data-engine/layer-1/specs/state-flow/1A)
- remediation and freeze logic from [segment_1A.build_plan.md](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/model_spec/data-engine/implementation_maps/segment_1A.build_plan.md)
- actual implemented posture from [segment_1A.impl_actual.md](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md)

The intent is to show, for each state:

- what authority it reads
- what transformation it owns
- what output or gate it becomes authoritative for
- and which implementation-side remediations materially changed the actual design

Files in this folder:

- [1A-overview-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-overview-design-flow.mmd)
- [1A-state-synthesis-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-state-synthesis-flow.mmd)
- [1A-S0-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S0-design-flow.mmd)
- [1A-S1-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S1-design-flow.mmd)
- [1A-S2-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S2-design-flow.mmd)
- [1A-S3-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S3-design-flow.mmd)
- [1A-S4-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S4-design-flow.mmd)
- [1A-S5-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S5-design-flow.mmd)
- [1A-S6-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S6-design-flow.mmd)
- [1A-S7-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S7-design-flow.mmd)
- [1A-S8-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S8-design-flow.mmd)
- [1A-S9-design-flow.mmd](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-S9-design-flow.mmd)
- [1A-state-synthesis.md](C:/Users/LEGION/Documents/Data%20Science%20/Python%20%26%20R%20Scripts/fraud-detection-system/docs/design/data-engine/layer-1/1A/1A-state-synthesis.md)

Reading rule:

- treat the state-flow docs as original design intent
- treat the build plan as the accepted remediation and freeze posture
- treat `impl_actual` as the record of what the implemented design actually became

So these charts aim to convey actual `1A` design, not just the earliest restrictive spec shape.
