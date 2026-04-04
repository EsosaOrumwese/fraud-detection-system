# Interface Operating Note v1

Operating rule:
1. keep the maintained analytical layer as the explicit producer surface
2. treat the reusable regeneration path as the controlled consumer
3. check required interface fields and maintained-layer grain before relying on regenerated outputs
4. use repeatability checks to confirm downstream equivalence remains exact

Current bounded support:
- governed input rows at the boundary: `4`
- downstream outputs protected: `4`
- audience-pack outputs protected: `2`
