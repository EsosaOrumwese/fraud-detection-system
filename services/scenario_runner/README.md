# Scenario Runner service
Status: v0 (in progress).
Purpose: Run authority + join surface publisher.
Owns: run_plan/run_record/run_status/run_facts_view; READY control signal.
Boundaries: engine internals; ingestion; downstream processing.

Notes: This service is the control-plane entrypoint for runs. It must stay fail-closed and by-ref.
