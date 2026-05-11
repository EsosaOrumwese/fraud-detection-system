# Patient-Level Dataset Maintenance Checklist v1

1. Confirm the stewardship window is bounded to `Mar 2026`.
2. Run source profiling before any maintained dataset build.
3. Confirm monthly `flow_id` remains unique at the bounded flow grain.
4. Confirm truth labels remain unique at `flow_id`.
5. Roll the case timeline to one row per `flow_id` before joining.
6. Confirm the maintained dataset contains only `case_opened_flag = 1` rows.
7. Confirm required maintained fields are complete.
8. Confirm the protected reporting-safe summary matches the InHealth `3.A` reporting lane before issuing downstream claims.
