# dev_full runtime stack (M2.E runtime posture)

This stack materializes managed-first runtime-critical surfaces used by `M2.E`:
1. API edge (`APIGW + Lambda + DDB`) for IG ingress/health runtime contract.
2. Runtime-critical IAM roles (`Flink`, `Lambda IG`, `APIGW invoke`, `DDB RW`, `StepFunctions`).
3. Step Functions platform-run orchestrator state-machine surface.
4. Selective EKS cluster baseline ARN surface for downstream runtime lanes.
5. Private-subnet bootstrap endpoints (`ec2`, `ecr.api`, `ecr.dkr`, `sts`, `s3` gateway) for no-NAT worker lanes.
6. Managed EKS worker nodegroup surface for `M6.F` stream-lane scheduling closure.
7. Runtime-path governance contract outputs for fail-closed path selection.

It intentionally excludes non-runtime lanes (`MWAA`, `SageMaker`, `Databricks`) which are materialized in later M2 subphases.
