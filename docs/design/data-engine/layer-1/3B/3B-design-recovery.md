Segment `3B` design recovery

These Mermaid flowcharts replace the deleted DAGs for `3B`.

They are not raw IO diagrams.

They are recovered design diagrams built from three surfaces together:

- state intent from [state-flow/3B](../../../../model_spec/data-engine/layer-1/specs/state-flow/3B)
- remediation and freeze logic from [segment_3B.build_plan.md](../../../../model_spec/data-engine/implementation_maps/segment_3B.build_plan.md)
- actual implemented posture from [segment_3B.impl_actual.md](../../../../model_spec/data-engine/implementation_maps/segment_3B.impl_actual.md)

The intent is to show, for each state:

- what authority it reads
- what transformation it owns
- what output or gate it becomes authoritative for
- and which implementation-side remediations materially changed the actual design

Files in this folder:

- [3B-overview-design-flow.mmd](3B-overview-design-flow.mmd)
- [3B-state-synthesis-flow.mmd](3B-state-synthesis-flow.mmd)
- [3B-S0-design-flow.mmd](3B-S0-design-flow.mmd)
- [3B-S1-design-flow.mmd](3B-S1-design-flow.mmd)
- [3B-S2-design-flow.mmd](3B-S2-design-flow.mmd)
- [3B-S3-design-flow.mmd](3B-S3-design-flow.mmd)
- [3B-S4-design-flow.mmd](3B-S4-design-flow.mmd)
- [3B-S5-design-flow.mmd](3B-S5-design-flow.mmd)
- [3B-state-synthesis.md](3B-state-synthesis.md)

Reading rule:

- treat the state-flow docs as original design intent
- treat the build plan as the accepted remediation and freeze posture
- treat `impl_actual` as the record of what the implemented design actually became

So these charts aim to convey actual `3B` design, not just the earliest restrictive spec shape.
