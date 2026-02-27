# Dev Min Terraform Resource Architecture

This folder stores Terravision-generated architecture assets for the three dev_min Terraform roots:

- `infra/terraform/dev_min/core`
- `infra/terraform/dev_min/confluent`
- `infra/terraform/dev_min/demo`

## Generation command

Run from repo root:

```powershell
pwsh ./scripts/design/run_terravision_dev_min.ps1 -Target all -PullImage
```

Optional flags:

- `-Target core|confluent|demo|all`
- `-Formats svg,png`
- `-UseExampleVarfile` (uses `terraform.tfvars.example` when `terraform.tfvars` is absent)
- `-Show` (opens output after generation)

## Runtime prerequisites

- Docker Desktop running
- Terraform roots readable from repo
- Cloud credentials available to Terraform if Terravision needs to run live `terraform plan`

By default, the script mounts `~/.aws` into the container at `/home/terravision/.aws` when present.
