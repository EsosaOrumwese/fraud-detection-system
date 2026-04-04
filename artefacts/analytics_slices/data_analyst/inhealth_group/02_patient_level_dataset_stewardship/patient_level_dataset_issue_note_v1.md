# Patient-Level Dataset Issue Note v1

Trust risk identified:
- the case surface is event-grain, not maintained reporting grain

Why this matters:
- `7,835,199` March flows linked to case activity
- those linked flows carry `20,581,909` raw case-event rows
- that is an average of `2.63` raw case-event rows per linked flow

Control applied:
- rolled the case timeline to one row per `flow_id` before joining it into the maintained detailed dataset

Reporting protection consequence:
- downstream monthly reporting can now use one maintained detailed dataset without event-grain duplication inflating case-linked counts
