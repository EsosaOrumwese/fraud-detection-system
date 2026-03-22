Segment `5A` design recovery

These Mermaid flowcharts replace the deleted DAGs for `5A`.

They are not raw IO diagrams.

They are recovered design diagrams built from three surfaces together:

- state intent from [state-flow/5A](../../../../model_spec/data-engine/layer-2/specs/state-flow/5A)
- remediation and freeze logic from [segment_5A.build_plan.md](../../../../model_spec/data-engine/implementation_maps/segment_5A.build_plan.md)
- actual implemented posture from [segment_5A.impl_actual.md](../../../../model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md)

The intent is to show, for each state:

- what authority it reads
- what transformation it owns
- what output or gate it becomes authoritative for
- and which implementation-side remediations materially changed the actual design

Files in this folder:

- [5A-overview-design-flow.mmd](5A-overview-design-flow.mmd)
- [5A-state-synthesis-flow.mmd](5A-state-synthesis-flow.mmd)
- [5A-S0-design-flow.mmd](5A-S0-design-flow.mmd)
- [5A-S1-design-flow.mmd](5A-S1-design-flow.mmd)
- [5A-S2-design-flow.mmd](5A-S2-design-flow.mmd)
- [5A-S3-design-flow.mmd](5A-S3-design-flow.mmd)
- [5A-S4-design-flow.mmd](5A-S4-design-flow.mmd)
- [5A-S5-design-flow.mmd](5A-S5-design-flow.mmd)
- [5A-state-synthesis.md](5A-state-synthesis.md)

Reading rule:

- treat the state-flow docs as original design intent
- treat the build plan as the accepted remediation and freeze posture
- treat `impl_actual` as the record of what the implemented design actually became

So these charts aim to convey actual `5A` design, not just the earliest restrictive spec shape.
