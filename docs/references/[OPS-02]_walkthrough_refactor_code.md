Alright, let’s unpack this script step-by-step, as if I’m sitting next to you walking you through it. I’ll show you each section of the code, explain what it does, and draw analogies to Python when it helps. Ready? Here we go.

---

```bash
#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# nuke.sh  v0.2 (2025-06-09)
# Safe, idempotent teardown for SANDBOX only:
#  • Confirms “NUKEME” (unless forced)
#  • Verifies TF workspace tag=“sandbox”
#  • Dry-run support
#  • Terraform destroy w/ retries
#  • S3 prefix emptying (handles versioned buckets)
#  • MLflow artifact purge (>7 days old) in remote S3 store
#  • Graceful error aggregation & exit code
#  • Structured logging (timestamps + levels)
# ------------------------------------------------------------------------------
```

1. **Shebang line (`#!/usr/bin/env bash`)**

   * Tells your system “run this file with the `bash` shell.”
   * Like a Python script starting with `#!/usr/bin/env python3`, it ensures portability.

2. **Header comment**

   * Documents the script name, version, date, and a bullet-list of its features.
   * Think of it as the module docstring in Python, summarizing what this script does.

---

```bash
set -o errexit -o nounset -o pipefail
```

3. **Strict error modes**

   * `errexit` (`-e`): if *any* command returns a non-zero (failure) status, the script immediately stops—no silent failures.

   * `nounset` (`-u`): using an undefined variable is an error (helps catch typos).

   * `pipefail`: if you chain commands with `|`, and *any* of them fails, the whole pipeline fails (not just the last one).

   > **Analogy:** Imagine in Python you `raise` any exception immediately you hit it—no loose ends.

---

## 1. Global Defaults

```bash
TF_DIR="infra/terraform"
DRY_RUN=false
FORCE=false
```

4. **Variables**

   * `TF_DIR` points to your Terraform folder. We’ll `cd` (change directory) into it later.

   * `DRY_RUN=false` means “by default, do the *real* teardown.” We’ll flip this to `true` if the user passes `--dry-run`.

   * `FORCE=false` means “by default, require the safety prompt.” Setting `--force` in the command line skips confirmation (useful in CI).

   > **Analogy:** Like default function arguments in Python:
   >
   > ```python
   > def nuke(dry_run=False, force=False):
   >     ...
   > ```

---

## 2. Helper Functions

```bash
log()   { printf '%(%Y-%m-%dT%H:%M:%S%z)T [%s] %s\n' "-1" "$1" "${@:2}"; }
die()   { log ERROR "$1"; exit "${2:-1}"; }
run()   {
  if $DRY_RUN; then
    log DRY "[dry-run]" "$*"
  else
    log INFO "Running:" "$*"
    eval "$@" || die "Command failed: $*"
  fi
}
```

5. **`log`**

   * Prints a timestamp, a log level (like `INFO` or `ERROR`), and your message.
   * Uses `printf` with `'%(%Y-%m-%dT%H:%M:%S%z)T'` to format the current time in ISO 8601 (e.g. `2025-06-09T14:23:01+0100`).

6. **`die`**

   * Shortcut for logging an `ERROR` and then exiting the script (`exit 1` by default).
   * Like doing `raise RuntimeError("…")` in Python.

7. **`run`**

   * Centralizes how we execute external commands (Terraform, AWS CLI, etc.).
   * If `DRY_RUN` is true, it only logs what *would* run; otherwise it:

     1. Logs at `INFO` level,

     2. Uses `eval` to actually run the command string,

     3. If that command fails, calls `die` to abort.

   > **Why?**
   >
   > * Keeps your script DRY (Don’t Repeat Yourself): no need to sprinkle `if…else` around every call.
   > * Ensures consistent logging and failure handling.

---

## 3. Usage / Help

```bash
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -n, --dry-run     Show what would be done, don’t execute.
  -f, --force       Skip confirmation prompt & tag-check (for CI).
  -h, --help        Show this help.
EOF
  exit 0
}
```

8. **`usage`**

   * Prints a helpful message about how to call the script, then exits.
   * `$(basename "$0")` inserts the script’s filename (e.g. `nuke.sh`).
   * Like using Python’s `argparse` with `parser.print_help()`.

---

## 4. Argument Parsing

```bash
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run) DRY_RUN=true ;;
    -f|--force)   FORCE=true ;;
    -h|--help)    usage ;;
    *) die "Unknown argument: $1" ;;
  esac
  shift
done
```

9. **`while [[ $# -gt 0 ]]`**

   * `"$#"` is the number of arguments left. Loop until none remain.

10. **`case "$1"`**

    * Checks the first argument (`$1`), matches it against patterns:

      * `-n|--dry-run`: set our `DRY_RUN` flag.
      * `-f|--force`: set `FORCE`.
      * `-h|--help`: call `usage()` and exit.
      * `*`: any other string → error out via `die`.

11. **`shift`**

    * Discards the current `$1` and shifts all other arguments down (`$2` becomes `$1`, etc.).

> **Analogy:** Similar to consuming `sys.argv` in Python or using `argparse`.

---

## 5. Fetching S3 Bucket Names

```bash
if [[ -z "${RAW_BUCKET:-}" ]]; then
  RAW_BUCKET=$(aws ssm get-parameter --name /fraud/raw_bucket_name --query Parameter.Value --output text)
fi
if [[ -z "${ART_BUCKET:-}" ]]; then
  ART_BUCKET=$(aws ssm get-parameter --name /fraud/artifacts_bucket_name --query Parameter.Value --output text)
fi

[[ -z "$RAW_BUCKET" || -z "$ART_BUCKET" ]] \
  && die "RAW_BUCKET and ART_BUCKET must be set (env or SSM)."
```

12. **`${RAW_BUCKET:-}`**

    * Expands to the value of `$RAW_BUCKET`, or to empty if it’s unset.
    * `-z` tests if that expansion is empty (string length zero).

13. **`aws ssm get-parameter`**

    * Calls AWS Systems Manager Parameter Store to fetch a stored value (your bucket name).
    * `--query Parameter.Value --output text` extracts just the bucket name string.

14. **Final check**

    * If *either* bucket variable is still empty, abort via `die`.

> **Analogy:** In Python:
>
> ```python
> RAW_BUCKET = os.getenv("RAW_BUCKET") or fetch_from_ssm("/fraud/raw_bucket_name")
> if not RAW_BUCKET: raise RuntimeError("…")
> ```

---

## 6. Safety Checks

### a) Confirmation Prompt

```bash
confirm() {
  if $FORCE; then return; fi
  read -rp "Type NUKEME to confirm SANDBOX destroy: " ans
  [[ "$ans" == "NUKEME" ]] || die "User aborted."
}
```

15. **`confirm()`**

    * If `FORCE` is true, skip confirmation (return immediately).
    * Otherwise, use `read -rp` to:

      * `-r`: read raw input (no backslash escapes),
      * `-p`: prompt with `"Type NUKEME…"`.

16. **Check answer**

    * If the user didn’t type exactly `NUKEME`, call `die` to abort.

### b) Verify We’re in the Sandbox

```bash
check_sandbox_tag() {
  if $FORCE; then return; fi
  VPC_ID=$(terraform -chdir="$TF_DIR" output -raw vpc_id)
  TAGVAL=$(aws ec2 describe-tags \
    --filters "Name=resource-id,Values=$VPC_ID" "Name=key,Values=environment" \
    --query 'Tags[0].Value' --output text)
  [[ "$TAGVAL" == "sandbox" ]] \
    || die "VPC $VPC_ID tag.environment=$TAGVAL != sandbox"
}
```

17. **Terraform output**

    * `terraform -chdir="$TF_DIR" output -raw vpc_id` reads the `vpc_id` you defined in your Terraform state.
    * `-raw` gives just the string, no quotes or JSON.

18. **AWS EC2 tags**

    * `aws ec2 describe-tags`: fetches metadata for that VPC ID.
    * Filters: resource-id = your VPC, key = `environment`.
    * Grabs the first tag’s `.Value` (should be `sandbox`).

19. **Tag check**

    * If the tag value isn’t exactly `sandbox`, abort—so you can’t accidentally point this at prod.

> **Analogy:** Like checking `ENV == "sandbox"` in Python before doing dangerous ops.

---

## 7. Main Execution

```bash
START=$(date +%s)
confirm
check_sandbox_tag
```

20. **`START=$(date +%s)`**

    * Records the current time in seconds since the epoch—used to show how long teardown took.

21. **Run safety checks**

    * First `confirm()`, then `check_sandbox_tag()`. If either dies, the script stops here.

---

## 8. Terraform Destroy

```bash
log INFO "🔸 Terraform destroy"
run terraform -chdir="$TF_DIR" init -input=false
run terraform -chdir="$TF_DIR" destroy -auto-approve
```

22. **`terraform init`**

    * Bootstraps Terraform in that directory (downloads providers, etc.).
    * `-input=false` disables interactive prompts.

23. **`terraform destroy`**

    * Destroys *all* resources in that workspace.
    * `-auto-approve` skips the “are you sure?” prompt (we already confirmed).

> **Note:** Because we use `run …`, if `DRY_RUN` is true it will only *log* those commands instead of executing.

---

## 9. Emptying Versioned S3 Buckets

```bash
log INFO "🔸 Empty S3 prefixes"
for BUCKET in "$RAW_BUCKET" "$ART_BUCKET"; do
  log INFO " • bucket: $BUCKET"
  run aws s3api list-object-versions --bucket "$BUCKET" \
      --query '[ Versions[].{Key:Key,VersionId:VersionId} , DeleteMarkers[].{Key:Key,VersionId:VersionId} ]' \
      --output json \
    | jq -c '.[]' \
    | while IFS= read -r obj; do
        KEY=$(jq -r .Key <<<"$obj")
        VID=$(jq -r .VersionId <<<"$obj")
        run aws s3api delete-object --bucket "$BUCKET" --key "$KEY" --version-id "$VID"
      done
done
```

24. **Why versioned buckets matter**

    * If your S3 bucket has *versioning* enabled, simply deleting objects with `aws s3 rm --recursive` leaves “delete markers” and old versions behind. They still incur storage costs.

25. **`list-object-versions`**

    * Returns both current object versions and delete markers as JSON.
    * We use a JMESPath query to emit a flat list of `[{Key,VersionId}, …]`.

26. **Piping into `jq -c '.[]'`**

    * `jq` is a lightweight JSON processor (like Python’s `json` module but on the command line).
    * `-c` means “compact output,” one JSON object per line.
    * `.[]` iterates over that list, emitting each `{Key,VersionId}` pair.

27. **`while IFS= read -r obj; do … done`**

    * Reads each JSON line into the shell variable `obj`.
    * `IFS=` prevents whitespace trimming; `-r` reads raw backslashes.

28. **Extracting fields**

    * `jq -r .Key <<<"$obj"` pulls out the object key (filename).
    * `jq -r .VersionId <<<"$obj"` pulls out that version’s ID.

29. **`aws s3api delete-object`**

    * Deletes that *specific* version or marker.
    * Wrapped in our `run`, so it obeys `dry-run` and logs failure cleanly.

---

## 10. MLflow Artifact Purge

```bash
log INFO "🔸 Pruning MLflow artifacts (>7 days)"
python3 - <<PYCODE
import os, time, boto3
from mlflow.tracking import MlflowClient

dry = ${DRY_RUN}

client = MlflowClient()
for exp in client.list_experiments():
    for run in client.search_runs(exp.experiment_id, f"attributes.start_time < {int(time.time()*1000) - 7*86400*1000}"):
        run_id = run.info.run_id
        if dry:
            print(f"[dry-run] would delete artifacts for run {run_id}")
        else:
            client.delete_run(run_id)
            print(f"Deleted MLflow run {run_id}")
PYCODE
```

30. **Here-document (`<<PYCODE … PYCODE`)**

    * Embeds a small Python script right inside your Bash script—convenient for complex logic.

31. **`MlflowClient()`**

    * Official Python API for interacting with MLflow.
    * `list_experiments()` returns all experiments; `search_runs(...)` finds runs older than 7 days.

32. **`time.time()*1000`**

    * MLflow timestamps are in milliseconds since epoch, so we subtract `7*86400*1000` ms (7 days).

33. **`client.delete_run(run_id)`**

    * Permanently deletes that run’s metadata and artifacts from your tracking store (which is backed by your S3 bucket).

34. **Dry-run logic**

    * Uses the same `DRY_RUN` flag imported from Bash. If true, just prints what *would* be deleted.

> **Analogy:** Treating MLflow like a database—query then delete old records.

---

## 11. Completion Message

```bash
END=$(date +%s)
log INFO "✅ Teardown complete in $((END-START))s."
```

35. **Compute elapsed time**

    * `END` is the timestamp at script end; `START` was captured earlier.
    * `$((…))` does integer arithmetic in Bash.
    * Final log: prints something like

      ```
      2025-06-09T14:24:07+0100 [INFO] ✅ Teardown complete in 42s.
      ```

---

### Putting it all together

* **Safety first:** you can’t run this by accident. You either type `NUKEME`, or you run with `--force`.
* **Dry-run mode:** `./nuke.sh --dry-run` shows you every step, without touching anything.
* **Terraform**: nukes all your AWS resources defined in Terraform.
* **S3 cleanup:** empties *every* object version in your raw and artifact buckets.
* **MLflow**: deletes old runs so you’re not paying for storage of stale models.
* **Structured logs**: easy to grep or pipe into monitoring tools.

From a high level, this is your “big red button” for tearing down an entire sandbox safely and cleanly. Each section is modular, testable, and wrapped in clear logging so you—and your future teammates—can always trace exactly what happened.

Feel free to ask about any piece, but I’ve aimed to spell out every command and decision. You’re all set!
