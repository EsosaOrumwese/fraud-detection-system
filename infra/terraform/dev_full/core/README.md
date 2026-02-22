# dev_full core stack

This stack materializes the `dev_full` core substrate baseline required by M2.B:

1. VPC and subnet baseline for downstream streaming/runtime stacks.
2. Core KMS key/alias.
3. Core S3 buckets (object-store, evidence, artifacts) with security posture.
4. Baseline IAM roles for EKS runtime/nodegroup lanes.

The stack uses remote-state backend config from `backend.hcl` (or equivalent `-backend-config` flags).
