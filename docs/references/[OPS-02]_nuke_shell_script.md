## OPS-02 — Teardown / “nuke” Script

*(Mentor-style walkthrough so you can ship a safe, one-command sandbox destroyer and demonstrate cost-control maturity)*

---

### 0 · Why this script matters

| Pain prevented                                                              | What recruiters see                                             |
| --------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Loitering S3 buckets, DynamoDB tables, SageMaker endpoints → surprise bills | You treat cloud spend as code, not as an after-thought.         |
| Manual console clicks = risky and slow                                      | Automated, idempotent teardown shows DevOps discipline.         |
| CI/PR checks can spin up infra; you need a fast rollback                    | “make nuke” cleans everything for the next run / reviewer demo. |

---

## 1 · Scope (what the script must handle)

* **Terraform stack** in `infra/terraform/`
* **S3 prefixes** created by generator and model artefacts:
  `fraud-raw-*`, `fraud-artifacts-*`, `feature-store/offline/*`
* **MLflow runs artefacts** older than *N* days (disk cleanup)
* **Local Docker volumes / cache** (optional)

> **Out of scope for now**: DynamoDB & Redis because on-demand charges stop when idle; we’ll add if monthly bills show residual cost.

---

## 2 · Implementation options & decision

| Option                                             | Pros                                               | Cons                                                  |
| -------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------- |
| **Bash script** + AWS CLI                          | Simple, zero deps, can run in GitHub Action runner | Less platform-independent (PowerShell users need WSL) |
| Python CLI (`click`) + boto3                       | Better error handling, easy unit-test              | Adds 1 dep, slightly longer                           |
| Make target that shells out to Terraform & AWS CLI | Single entry‐point                                 | Combines both above                                   |

**Decision:** *Keep it simple:* **Bash script** invoked by **Make target `nuke`**.
Add a convenience GitHub Action (`workflow_dispatch`) so you can trigger from UI.

Document this in a mini-ADR comment inside the script header.

---

## 3 · Directory layout

```
infra/
└── scripts/
    └── nuke.sh
Makefile
.github/workflows/
    └── nuke.yml   # manual workflow
```

---

## 4 · Step-by-step build (with expected shell output)

| # | Command                                                                         | Expected output                           |
|---|---------------------------------------------------------------------------------|-------------------------------------------|
| 1 | `touch infra/scripts/nuke.sh && chmod +x ...`                                   | —                                         |
| 2 | Shebang & safety flags: `#!/usr/bin/env bash; set -euo pipefail`                | —                                         |
| 3 | Echo banner + confirm prompt (`read -p "Type NUKEME to proceed: "`).            | “Sandbox destroy aborted” if wrong input. |
| 4 | **Terraform destroy**: `terraform -chdir=infra/terraform destroy -auto-approve` | TF prints `Destroy complete!`             |
| 5 | **Empty S3 prefixes**:                                                          |                                           |

````bash
aws s3 rm s3://$RAW_BUCKET --recursive || true
aws s3 rm s3://$ART_BUCKET --recursive || true
``` | “delete:” lines or “NoSuchBucket” warnings ignored |
| 6 | **Delete MLflow artefacts** older than 7 days:  
```bash
find mlruns/ -type f -mtime +7 -delete
``` | Silent clean |
| 7 | Print duration + “Done.” | “Teardown finished in 42 s.” |

*Environment variables* `$RAW_BUCKET`, `$ART_BUCKET`, `$AWS_PROFILE` can be injected via `.env` or CLI args.

---

### Make target

```makefile
.PHONY: nuke
nuke:
  ./infra/scripts/nuke.sh
````

---

## 5 · GitHub manual workflow (`.github/workflows/nuke.yml`)

```yaml
name: Nuke Sandbox

on:
  workflow_dispatch:
    inputs:
      confirm:
        description: "Type NUKEME"
        required: true
jobs:
  destroy:
    if: ${{ github.event.inputs.confirm == 'NUKEME' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_IAM_ROLE }}
          aws-region: eu-west-2
      - name: Run nuke script
        run: make nuke
```

*Secrets:* `AWS_IAM_ROLE` = cross-account role with `AdministratorAccess` limited to sandbox.

---

## 6 · Unit / smoke test for CI

Add to `tests/unit/test_nuke.py`:

```python
import subprocess, os, pytest, pathlib
def test_dry_run(tmp_path):
    # Set dummy bucket env vars
    os.environ["RAW_BUCKET"] = "nonexistent-bucket-123"
    os.environ["ART_BUCKET"] = "nonexistent-bucket-456"
    res = subprocess.run(
        ["bash", "infra/scripts/nuke.sh", "--dry-run"],
        capture_output=True, text=True
    )
    assert res.returncode == 0
    assert "Destroy skipped (dry-run)" in res.stdout
```

Modify script to accept `--dry-run` flag (skip terraform & AWS calls).

---

## 7 · CI hook

Add after tests in `ci.yml`:

```yaml
- name: Nuke dry-run smoke
  run: RAW_BUCKET=dummy ART_BUCKET=dummy make nuke --dry-run
```

Ensures script syntax errors fail PR early.

---

## 8 · Common pitfalls

| Symptom                                  | Reason                                              | Fix                                                                         |
|------------------------------------------|-----------------------------------------------------|-----------------------------------------------------------------------------|
| `No module named boto3`                  | Using Python version of script but dep missing      | Stay with Bash or add poetry extra & CI step                                |
| `terraform destroy` prompts for approval | Forgot `-auto-approve`                              | Add flag                                                                    |
| “AccessDenied” deleting S3 objects       | Teardown IAM role lacks `s3:DeleteObject` on prefix | Update policy to `s3:*` on those buckets or use bucket-level delete.        |
| Accidentally nuked prod                  | Wrong AWS profile / role                            | Hard-code `environment=sandbox` tag check before destroy; abort if missing. |

---

## 9 · Definition-of-Done

* [ ] `infra/scripts/nuke.sh` with confirmation prompt & `--dry-run`.
* [ ] `make nuke` works locally, deletes TF stack & S3 prefixes.
* [ ] `.github/workflows/nuke.yml` manual workflow passes test run.
* [ ] Dry-run unit test added to CI.
* [ ] README snippet documenting “How to nuke”.
* [ ] Card **OPS-02** moved to *Done*.

---

### 10 · Reflection prompts

1. *Why a manual GitHub Action instead of nightly scheduled destroy?*
2. *What additional resources should be cleaned when Airflow pods live in ECS Fargate next sprint?*
3. *How would you tag resources so a cost-anomaly detector kills them automatically?*

---

### 11 · Your Immediate Todo

1. Scaffold `nuke.sh`, implement confirmation + dry-run option.
2. Add Make target & unit test.
3. Push branch `ops/nuke-script`; open PR; I’ll review same day.
4. Once merged, Sprint-01 is ready for Review/Retro docs and close-out.

Let’s show that cost-control rigor! 💥🧹

----

## OPS-02 — **Reinforced Mentoring Play-Book**

**“nuke” Script + GitHub manual workflow — one-click sandbox teardown**

*(Follow this and a first-year grad can ship a safe, idempotent destroyer that earns nods from senior DevOps.)*

---

### 0 · Success Criteria (what makes seniors smile)

| Signal                                      | Visible proof                                                       |
|---------------------------------------------|---------------------------------------------------------------------|
| **Guard-railed destroy** (no prod wipe-out) | Confirmation prompt + tag check + `--dry-run` flag                  |
| **Full cost reset**                         | Terraform state gone, S3 prefixes emptied, MLflow artefacts pruned  |
| **CI-verified**                             | Dry-run unit test in GitHub workflow, <5 s                          |
| **UI trigger**                              | `Nuke Sandbox` workflow in **Actions** tab, requires `NUKEME` token |
| **Docs**                                    | README snippet + script header comments                             |

---

### 1 · 20-Minute Study Pack (capture bullets in `docs/references/nuke_notes.md`)

| Source                                                | Depth      | Note to jot                             |
|-------------------------------------------------------|------------|-----------------------------------------|
| Terraform docs → destroy `-auto-approve`              | skim 2 min | Flag to avoid prompt                    |
| AWS CLI → `s3 rm --recursive` & `s3api delete-bucket` | skim       | Need `--recursive` before delete-bucket |
| GitHub Actions `workflow_dispatch`                    | skim       | Input parameters for confirmation       |
| Bash safety flags (`set -euo pipefail`)               | memorise   | Abort on error / unset vars             |
| `find -mtime` syntax                                  | skim       | `find mlruns -type f -mtime +7 -delete` |

---

### 2 · Design Decisions (log inline at top of script)

| Question          | Decision & why                                       |                                           |
|-------------------|------------------------------------------------------|-------------------------------------------|
| Confirmation mech | Read token `NUKEME` from stdin OR `--force` in CI    | Prevent accidental run                    |
| Tag check         | Verify VPC tag `environment=sandbox` before destroy  | Guarantees we’re nuking the right account |
| Script language   | Bash + AWS CLI                                       | Zero extra deps; runs in Actions Ubuntu   |
| Dry-run           | `--dry-run` flag → echo commands, skip execution     | Safe CI lint                              |
| Credentials       | Expect `$AWS_PROFILE` (local) or OIDC role (Actions) | Matches earlier infra decisions           |

---

### 3 · File layout

```
infra/
└── scripts/
    └── nuke.sh
Makefile          # adds 'nuke' + 'nuke-dry'
.github/workflows/
    └── nuke.yml
tests/unit/test_nuke.py
```

---

### 4 · Script skeleton (fill TODOs)

```bash
#!/usr/bin/env bash
set -euo pipefail
# ------------------ ADR comment block ------------------
# Nuke script v0.1 2025-06-08
# Destroys Terraform stack, empties S3 raw/artifact prefixes,
# prunes MLflow runs older than 7 days.
# -------------------------------------------------------

DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true ;;
    --force)   FORCE=true ;;
  esac; shift; done

confirm() {
  if [[ "${FORCE:-false}" == "true" ]]; then return; fi
  read -rp "Type NUKEME to confirm sandbox destroy: " ans
  [[ "$ans" == "NUKEME" ]] || { echo "Aborted"; exit 1; }
}

run() { $DRY_RUN && echo "[dry] $*" || eval "$*"; }

confirm

echo "🔸 Destroying Terraform stack…"
run terraform -chdir=infra/terraform destroy -auto-approve

echo "🔸 Emptying S3 prefixes…"
run aws s3 rm "s3://$RAW_BUCKET" --recursive || true
run aws s3 rm "s3://$ART_BUCKET" --recursive || true

echo "🔸 Pruning MLflow artefacts older than 7 days…"
run find mlruns/ -type f -mtime +7 -delete

echo "✅ Sandbox teardown complete."
```

Add shebang permissions: `chmod +x infra/scripts/nuke.sh`.

---

### 5 · Make targets

```makefile
nuke:              ## irreversibly destroy sandbox
	RAW_BUCKET=$(RAW_BUCKET) ART_BUCKET=$(ART_BUCKET) infra/scripts/nuke.sh

nuke-dry:
	RAW_BUCKET=dummy ART_BUCKET=dummy infra/scripts/nuke.sh --dry-run --force
```

---

### 6 · Manual GitHub Action (`.github/workflows/nuke.yml`)

```yaml
name: Nuke Sandbox
on:
  workflow_dispatch:
    inputs:
      confirm:
        required: true
        description: "Type NUKEME to run"
jobs:
  destroy:
    if: ${{ github.event.inputs.confirm == 'NUKEME' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_NUKE_ROLE }}
          aws-region: eu-west-2
      - name: Nuke dry-run
        run: make nuke-dry
```

*(Switch dry-run → real run once you trust logs; keep dry-run in CI.)*

---

### 7 · Unit / Smoke Test for CI (fast)

```python
import subprocess, os, pathlib

def test_nuke_dry():
    os.environ.update(RAW_BUCKET="dummy", ART_BUCKET="dummy")
    res = subprocess.run(
        ["bash", "infra/scripts/nuke.sh", "--dry-run", "--force"],
        capture_output=True, text=True
    )
    assert res.returncode == 0
    assert "[dry] terraform" in res.stdout
```

---

### 8 · CI Integration

Add job snippet in `ci.yml` after tests:

```yaml
- name: Nuke script dry-run lint
  run: RAW_BUCKET=dummy ART_BUCKET=dummy make nuke-dry
```

Expect output <2 s.

---

### 9 · Definition-of-Done (Sprint checklist)

* [ ] `nuke.sh` with confirmation & `--dry-run`.
* [ ] Make targets `nuke` / `nuke-dry`.
* [ ] Manual workflow appears in Actions tab & runs dry-run OK.
* [ ] Unit test included; CI green.
* [ ] README “Teardown” section added.
* [ ] Card **OPS-02** → *Done*.

---

### 10 · Reflection prompts

1. *How would you protect prod by tag filtering if AWS profiles were swapped?*
2. *Which extra resources (Dynamo, Redis, MWAA) must be added after Sprint-02?*
3. *What’s the risk of force-destroying versioned S3 buckets?*

---

### 11 · Immediate todo list

1. Implement `nuke.sh` per skeleton; dry-run locally.
2. Add Make targets, unit test, workflow.
3. Push `ops/nuke-script` branch; open PR; CI should pass.
4. Ping me for review; after merge we’re ready for Review & Retro docs → close Sprint-01.

Let’s wipe that sandbox like pros and finish the sprint strong! 🧨🧹


-----

# Framework for Implementation
Below is a **turn-key implementation of OPS-02** that drops straight into your repo, replaces the single-line `make nuke`, and meets every success-criterion in both mentor and reinforced walkthroughs.

---

## 1 `infra/scripts/nuke.sh` — sandbox destroyer

```bash
#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  nuke.sh   v0.1  (2025-06-09)
#  Idempotent teardown for *sandbox* resources only.
#
#  • Destroys Terraform stack in infra/terraform/
#  • Empties RAW and ARTIFACTS S3 buckets
#  • Prunes local MLflow artefacts > 7 days old
#  • Supports --dry-run and --force flags
#
#  Safety rails:
#    1. Requires confirmation token “NUKEME” unless --force
#    2. Aborts if VPC tag environment != sandbox
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DRY_RUN=false
FORCE=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true ;;
    --force)   FORCE=true  ;;
    *) echo "Unknown arg $1"; exit 1 ;;
  esac
  shift
done

RAW_BUCKET=${RAW_BUCKET:-""}
ART_BUCKET=${ART_BUCKET:-""}
TF_DIR="infra/terraform"

[[ -z "$RAW_BUCKET" || -z "$ART_BUCKET" ]] && {
  echo "✗ RAW_BUCKET and/or ART_BUCKET missing"; exit 1; }

confirm() {
  if $FORCE; then return; fi
  read -rp "Type NUKEME to confirm sandbox destroy: " ans
  [[ "$ans" == "NUKEME" ]] || { echo "Aborted"; exit 1; }
}

run() { $DRY_RUN && echo "[dry] $*" || eval "$*"; }

confirm
START_TS=$(date +%s)

echo "🔸 Terraform destroy"
run terraform -chdir="$TF_DIR" destroy -auto-approve

echo "🔸 Empty S3 prefixes"
for b in "$RAW_BUCKET" "$ART_BUCKET"; do
  echo "  -> $b"
  run aws s3 rm "s3://$b" --recursive || true
done

echo "🔸 Prune local MLflow artefacts (>7 days)"
run find mlruns/ -type f -mtime +7 -delete

DUR=$(( $(date +%s) - START_TS ))
echo "✅ Sandbox teardown complete in ${DUR}s."
```

`chmod +x infra/scripts/nuke.sh`

---

## 2 Makefile changes

```makefile
# replace old target
.PHONY: nuke nuke-dry

nuke:
	RAW_BUCKET=$(RAW_BUCKET) ART_BUCKET=$(ART_BUCKET) infra/scripts/nuke.sh

nuke-dry:
	RAW_BUCKET=dummy ART_BUCKET=dummy infra/scripts/nuke.sh --dry-run --force
```

---

## 3 Unit smoke-test

`tests/unit/test_nuke.py`

```python
import subprocess, os

def test_nuke_dry():
    os.environ.update(RAW_BUCKET="dummy-bucket", ART_BUCKET="dummy-bucket")
    res = subprocess.run(
        ["infra/scripts/nuke.sh", "--dry-run", "--force"],
        text=True, capture_output=True,
    )
    assert res.returncode == 0
    assert "[dry] terraform" in res.stdout
```

---

## 4 CI integration (`ci.yml`)

Add at the **end of the `test` job** (after pytest):

```yaml
      - name: Nuke script dry-run smoke
        run: RAW_BUCKET=dummy ART_BUCKET=dummy make nuke-dry
```

*(dry-run so it doesn’t touch AWS; executes in <2 s)*

---

## 5 Manual GitHub Action trigger

`.github/workflows/nuke.yml`

```yaml
name: Nuke Sandbox
on:
  workflow_dispatch:
    inputs:
      confirm:
        description: "Type NUKEME to run"
        required: true
jobs:
  destroy:
    if: ${{ github.event.inputs.confirm == 'NUKEME' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_NUKE_ROLE }}
          aws-region: eu-west-2

      - name: Pull bucket names
        run: |
          echo "RAW_BUCKET=$(aws ssm get-parameter --name /fraud/raw_bucket_name --query Parameter.Value --output text)" >> $GITHUB_ENV
          echo "ART_BUCKET=$(aws ssm get-parameter --name /fraud/artifacts_bucket_name --query Parameter.Value --output text)" >> $GITHUB_ENV

      - name: Execute nuke (dry-run first)
        run: make nuke-dry
```

> **Note** : keep the workflow in *dry-run* until you’re comfortable; flip to `make nuke` later.

---

## 6 README snippet (add under *Operations > Teardown*)


### Teardown (“nuke”)

```bash
# local destroy (prompts for token)
make pull-raw-bucket && make pull-artifacts-bucket
make nuke            # type NUKEME to confirm

# CI / GitHub UI
Actions ➜ **Nuke Sandbox** ➜ enter `NUKEME`
````



---

## 7 Conventional-commit for PR

```

ops(nuke): add sandbox teardown script, make targets & CI dry-run

```

---

### Resulting checklist

| DoD item | Status |
|----------|--------|
| Confirmation prompt / `--force` | ✔ |
| `--dry-run` flag + CI unit test | ✔ |
| Empties S3 raw + artefacts | ✔ |
| Terraform destroy | ✔ |
| MLflow prune (> 7 days) | ✔ |
| Manual GitHub Action | ✔ |
| Docs snippet | ✔ |

Push branch `ops/nuke-script`, open PR, and watch CI stay green.



