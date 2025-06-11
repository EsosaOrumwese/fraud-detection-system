> My issue was that the lockfile I created (initially) during `terraform init` was different from the one an Ubuntu runner in the CI would create when running the `terraform init` for validation of the lockfile. As such there was a mismatch since I use a Windows system. 
> Because of this, I changed to the runner for my lint tests to `windows-latest` but this couldn't run shell scripts properly
> To solve this, I had to run the below and regenerate the lockfile for multi-os and change the runner to `ubuntu-latest`


To unblock your CI most cleanly, I’d go with **Option 1** from that Copilot advice—**run your bash-based nuke dry-run test on a Linux runner**—and at the same time fix the Terraform lockfile so you can consistently use Linux everywhere (and never need to juggle Windows vs. WSL). Here’s the recipe:

---

## 1) Regenerate your Terraform lockfile for all platforms

Rather than pin your CI to Windows or install WSL, let’s make the lockfile portable. On your local machine (or in a throwaway Linux container), run:

```bash
cd infra/terraform
terraform init
terraform providers lock \
  -platform=linux_amd64 \
  -platform=windows_amd64 \
  -platform=darwin_amd64
git add .terraform.lock.hcl
git commit -m "chore(terraform): regenerate lockfile for linux, windows, and mac"
```

This adds checksums for every OS so **`terraform validate`** or **`terraform destroy`** will succeed on any runner.

---

## 2) Switch your test job to **ubuntu-latest**

In your **`.github/workflows/ci.yml`**, change the job that runs pytest/tests so it uses Linux:

```diff
 jobs:
-  test:
-    runs-on: windows-latest
+  test:
+    runs-on: ubuntu-latest
     strategy:
       matrix:
         python-version: ["3.11", "3.12"]
     steps:
       - uses: actions/checkout@v4
       - name: Set up Python
         uses: actions/setup-python@v4
         with:
           python-version: ${{ matrix.python-version }}
       - name: Install deps
         run: |
           python -m pip install poetry
           poetry install --no-interaction --no-ansi
       - name: Run tests
         run: pytest -q
```

That way:

* Your **bash-based** `nuke.sh` dry-run test will find `/usr/bin/bash` and everything else it needs.
* Your **Terraform** validation and `destroy` logic also run on a Linux runner against the new lockfile checksums.
* You don’t need to install or configure WSL on Windows at all.

---

## 3) (Optional) Keep other jobs on Windows

If you still have Windows-specific jobs (e.g. packaging a Windows service), you can move **only** the `test` job to ubuntu and leave others on `windows-latest`. Or you can upgrade your entire CI to Linux now that the lockfile is portable.

---

### Why this is the least‐friction path

* **No more WSL headaches**: you never have to install or maintain WSL in your CI.
* **Lockfile portability**: by including checksums for all OSes, you’ll never see “provider checksum mismatch” again.
* **Bash & Python baked in**: the Ubuntu images come with `bash`, `python3`, and `poetry` easily installed.
* **Test fidelity**: your dry-run test still runs exactly as before, but now in an environment that actually supports it.

---

### Conventional-commit for this change

```text
chore(ci): switch tests to ubuntu-latest & regenerate terraform lockfile for multi-os
```

That commit covers both the CI runner change *and* the lockfile bump so the entire pipeline (terraform validate, pytest, nuke dry-run) is happy on Linux.
