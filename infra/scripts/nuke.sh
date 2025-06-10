#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# nuke.sh  v0.5  (2025-06-10)
# Safe, idempotent teardown for SANDBOX only:
#  • Confirms “NUKEME” (unless forced)
#  • Verifies TF workspace tag=“sandbox”
#  • Dry-run support (skips S3 & MLflow loops entirely)
#  • Empty versioned S3 buckets **before** Terraform destroy
#  • Terraform destroy
#  • MLflow run purge (>7 days old)
#  • Graceful failures & structured logs
# ------------------------------------------------------------------------------

set -o errexit -o nounset -o pipefail

TF_DIR="infra/terraform"
DRY_RUN=false
FORCE=false

log() { printf '%(%Y-%m-%dT%H:%M:%S%z)T [%s] %s\n' "-1" "$1" "$2"; }
die() { log ERROR "$1"; exit "${2:-1}"; }
run() {
  if $DRY_RUN; then
    log DRY "[dry-run] $*"
  else
    log INFO "Running: $*"
    eval "$@" || die "Command failed: $*"
  fi
}
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]
  -n, --dry-run  Show what would be done (no changes)
  -f, --force    Skip prompt & tag-check (for CI)
  -h, --help     Show this help
EOF
  exit 0
}

# ── Parse Flags ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    -n|--dry-run) DRY_RUN=true ;;
    -f|--force)   FORCE=true ;;
    -h|--help)    usage ;;
    *) die "Unknown argument: $1" ;;
  esac
  shift
done

# ─── Resolve bucket names ────────────────────────────────────────────────────
# In CI dry-run tests, the two FRAUD_* vars are already set and PATH is stubbed,
# so skip any poetry/python calls and just use those. Otherwise, fetch via SSM.

if [[ -z "${FRAUD_RAW_BUCKET_NAME:-}" ]]; then
  if $DRY_RUN; then
    RAW_BUCKET="dummy-bucket"
  else
    log INFO "🔸 Fetching raw bucket name from SSM"
    run poetry run python scripts/pull_raw_bucket.py
  fi
else
  RAW_BUCKET="$FRAUD_RAW_BUCKET_NAME"
fi

if [[ -z "${FRAUD_ARTIFACTS_BUCKET_NAME:-}" ]]; then
  if $DRY_RUN; then
    ART_BUCKET="dummy-bucket"
  else
    log INFO "🔸 Fetching artifacts bucket name from SSM"
    run poetry run python scripts/pull_artifacts_bucket.py
  fi
else
  ART_BUCKET="$FRAUD_ARTIFACTS_BUCKET_NAME"
fi

# If we ran the helpers above, source .env so their values land in our env
if ! $DRY_RUN && [[ -f .env ]]; then
  set -o allexport
  # shellcheck disable=SC1091
  source .env
  set +o allexport
  # overwrite in-script vars if the helpers wrote new values
  RAW_BUCKET="${FRAUD_RAW_BUCKET_NAME:-$RAW_BUCKET}"
  ART_BUCKET="${FRAUD_ARTIFACTS_BUCKET_NAME:-$ART_BUCKET}"
fi

# Final sanity check
[[ -n "${RAW_BUCKET:-}" && -n "${ART_BUCKET:-}" ]] \
  || die "RAW_BUCKET and ART_BUCKET must be set (env, test-env, or SSM)."


# ── Safety Checks ────────────────────────────────────────────────────────────
confirm() {
  $FORCE && return
  read -rp "Type NUKEME to confirm SANDBOX destroy: " ans
  [[ "$ans" == "NUKEME" ]] || die "Aborted by user."
}
check_sandbox_tag() {
  $FORCE && return
  VPC_ID=$(terraform -chdir="$TF_DIR" output -raw vpc_id)
  TAGVAL=$(aws ec2 describe-tags \
    --filters "Name=resource-id,Values=$VPC_ID" "Name=key,Values=environment" \
    --query 'Tags[0].Value' --output text)
  [[ "$TAGVAL" == "sandbox" ]] \
    || die "VPC $VPC_ID tag.environment=$TAGVAL != sandbox"
}

START=$(date +%s)
confirm
check_sandbox_tag

# ── 1) Empty S3 Buckets ───────────────────────────────────────────────────────
log INFO "🔸 Empty S3 prefixes (pre-destroy)"
if $DRY_RUN; then
  for bucket in "$RAW_BUCKET" "$ART_BUCKET"; do
    log DRY "[dry-run] would empty versioned bucket $bucket"
  done
else
  python - <<'PYCODE'
import os
import boto3

# we know DRY_RUN is false here (we’re in the else‐branch)
client = boto3.client("s3")
buckets = [
    os.environ["FRAUD_RAW_BUCKET_NAME"],
    os.environ["FRAUD_ARTIFACTS_BUCKET_NAME"],
]
for bucket in buckets:
    print(f"Emptying versioned bucket: {bucket}")
    paginator = client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket):
        for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
            client.delete_object(
                Bucket=bucket,
                Key=v["Key"],
                VersionId=v["VersionId"],
            )
            print(f"Deleted {v['Key']}@{v['VersionId']} in {bucket}")
PYCODE
fi

# ── 2) Terraform Destroy ─────────────────────────────────────────────────────
log INFO "🔸 Terraform destroy"
run terraform -chdir="$TF_DIR" init -input=false
run terraform -chdir="$TF_DIR" destroy -auto-approve

# ── 3) MLflow Purge ─────────────────────────────────────────────────────────
log INFO "🔸 Pruning MLflow runs older than 7 days"
if $DRY_RUN; then
  log DRY "[dry-run] would delete artifacts for run <run_id>"
else
  python - <<PYCODE
import time
from mlflow.tracking import MlflowClient

client = MlflowClient()
cutoff = int(time.time()*1000) - 7*86400*1000
for exp in client.search_experiments():
    for run in client.search_runs(exp.experiment_id, f"attributes.start_time < {cutoff}"):
        client.delete_run(run.info.run_id)
        print(f"Deleted MLflow run {run.info.run_id}")
PYCODE
fi

END=$(date +%s)
log INFO "✅ Teardown complete in $((END-START))s."
