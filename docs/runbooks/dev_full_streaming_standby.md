# dev_full streaming standby runbook

This runbook exists to stop the standing-cost floor from the `dev_full` streaming substrate when the platform is under review and the runtime is already intentionally idled.

It controls only:

- `infra/terraform/dev_full/streaming`

which materially seats:

- the MSK Serverless cluster
- the bootstrap-broker SSM parameter
- the Glue schema registry baseline in that stack

It does **not** restore or scale application runtime by itself.

## Why this exists

`dev_full` can sit in a misleading middle state:

- EKS workloads scaled to `0`
- Aurora stopped
- replay tasks absent
- but MSK Serverless still alive and still accruing cluster-hour and partition-hour cost

This runbook makes that substrate explicitly destroyable and restorable.

## Preconditions for teardown

Default teardown is intentionally conservative. It refuses to run unless runtime is already in standby:

- EKS nodegroup `fraud-platform-dev-full-m6f-workers`
  - `min = 0`
  - `desired = 0`
- Aurora cluster `fraud-platform-dev-full-aurora`
  - status `stopped` or `stopping`

If you bypass that with `--force`, you are explicitly accepting that you may sever Kafka from a still-active runtime.

## Commands

From repo root:

```powershell
python scripts/dev_substrate/dev_full_streaming_standby.py teardown
```

To restore later:

```powershell
python scripts/dev_substrate/dev_full_streaming_standby.py restore
```

Optional explicit execution ids:

```powershell
python scripts/dev_substrate/dev_full_streaming_standby.py teardown --execution-id streaming_teardown_YYYYMMDDTHHMMSSZ
python scripts/dev_substrate/dev_full_streaming_standby.py restore --execution-id streaming_restore_YYYYMMDDTHHMMSSZ
```

Optional explicit backend config override:

```powershell
python scripts/dev_substrate/dev_full_streaming_standby.py teardown --backend-config infra/terraform/dev_full/streaming/backend.hcl
python scripts/dev_substrate/dev_full_streaming_standby.py restore --backend-config infra/terraform/dev_full/streaming/backend.hcl
```

## What teardown does

1. Checks standby preconditions unless `--force` is used.
2. Resolves the backend config file, defaulting to `infra/terraform/dev_full/streaming/backend.hcl.example`.
3. Runs `terraform init -reconfigure -backend-config=<resolved backend config>` in `infra/terraform/dev_full/streaming`.
4. Snapshots current Terraform outputs.
5. Reads current MSK cluster presence and bootstrap-SSM parameter presence.
6. Runs:

```powershell
terraform -chdir=infra/terraform/dev_full/streaming destroy -auto-approve -input=false -lock-timeout=5m
```

6. Verifies that:
   - the MSK cluster is no longer present
   - the bootstrap-SSM parameter is gone
   - the streaming Terraform state is empty
7. Writes a durable receipt under, including failure-path receipts if `terraform init` or `terraform destroy` aborts:

```text
runs/dev_substrate/dev_full/proving_plane/run_control/<execution_id>/streaming_teardown_receipt.json
```

## What restore does

1. Resolves the backend config file, defaulting to `infra/terraform/dev_full/streaming/backend.hcl.example`.
2. Runs `terraform init -reconfigure -backend-config=<resolved backend config>`.
3. Runs:

```powershell
terraform -chdir=infra/terraform/dev_full/streaming apply -auto-approve -input=false -lock-timeout=5m
```

4. Verifies that:
   - the MSK cluster exists again
   - the bootstrap-SSM parameter exists again
5. Writes a durable receipt under, including failure-path receipts if `terraform init` or `terraform apply` aborts:

```text
runs/dev_substrate/dev_full/proving_plane/run_control/<execution_id>/streaming_restore_receipt.json
```

## After restore

Restore of the streaming substrate does not itself warm the platform. To return to a runnable posture, you still need the normal runtime bring-up path afterward, for example:

- nodegroup restore
- `coredns` restore
- RTDL deployments restore
- Case + Label deployments restore
- Aurora start if needed

This runbook only controls the standing-cost streaming substrate.

## Files

- script: `scripts/dev_substrate/dev_full_streaming_standby.py`
- terraform stack: `infra/terraform/dev_full/streaming`
- receipts root: `runs/dev_substrate/dev_full/proving_plane/run_control/`
