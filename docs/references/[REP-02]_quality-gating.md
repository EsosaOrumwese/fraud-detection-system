# Summary notes
Summary notes for `[REP-02]:Pre-commit: ruff, black, pytest, terraform fmt`

---

## REP-02: Configure Pre-commit

**Goal**
Embed “fail-fast” quality checks (formatting, linting, type-checking, secrets scanning, Terraform hygiene) into every developer workflow, **before** code ever reaches GitHub.

**Why**

* Enforces a consistent code style and catches common errors locally.
* Reduces noisy, nit-picky CI failures and code-review comments.
* Prevents accidental commits of secrets or malformed Terraform.

**Acceptance Criteria**

* Running `pre-commit install` once enables hooks on every `git commit`.
* `pre-commit run --all-files` exits cleanly on a “clean” branch.
* The same command runs in CI and passes on your main/dev branches.

---

## Hooks used
Stored in `.pre-commit-config.yaml` in the root directory.
* [black](https://github.com/psf/black): An “uncompromising” Python code formatter. It reformats your `.py` files to a consistent style so you don’t have to worry about line‐lengths, quotes, indentation, etc.
* [ruff](https://github.com/astral-sh/ruff-pre-commit): A very fast linter for Python, covering style issues, unused imports/variables, complexity checks, possible bugs, etc. It’s often 10–100× faster than traditional tools like Flake8.
* [mypy](https://github.com/pre-commit/mirrors-mypy): Performs static type-checking of your Python code based on type hints. Catches mismatched types, missing attributes, incorrect function signatures, etc. Requires you to use types in your formatting.
* [detect-secrets](https://github.com/Yelp/detect-secrets): Scans your code for high-entropy strings or known secret patterns (API keys, tokens, passwords). Prevents accidental commits of credentials.
* [terraform_fmt](https://github.com/antonbabenko/pre-commit-terraform): Auto-format all your `.tf` files according to the standard HCL style.
* [terraform_validate](https://github.com/antonbabenko/pre-commit-terraform): Runs `terraform_validate` to ensure your Terraform configuration is syntactically valid and internally consistent (catching things like missing variables, bad references, etc.) before you even push it.

## Why use pre-commit hooks?
Better commit quality = better code quality

The goal of pre-commit hooks is to improve the quality of commits. 
This is achieved by making sure your commits meet some (formal) requirements, e.g:
* that they comply to a certain coding style (with the hook `style-files`).
* that you commit derivatives such as `README.md` or `.Rd` files with their source instead of spreading them over multiple commits.
* and so on. [source](https://cloud.r-project.org/web/packages/precommit/vignettes/why-use-hooks.html#:~:text=The%20goal%20of%20pre%2Dcommit,such%20as%20README.md%20or%20.)

## Why use the pre-commit framework?
Using hooks from a framework like pre-commit.com has multiple benefits compared to using simple bash scripts locally in .git/hooks or use boilerplate code in other CI services to perform these tasks:
* **Focus on your code**. Hooks are maintained, tested and documented outside of your repo, all you need a `.pre-commit-config.yaml` file to invoke them. No need to c/p hooks from one project to another or maintain boilerplate code.
* **A declarative configuration file for routine checks**. File filtering for specific hooks, language version of hooks, when to trigger them (push, commit, merge), configuration options - all controlled via a single configuration file: `.pre-commit-config.yaml`.
* **Locally and remotely. Or just one of the two.** You can use pre-commit locally and in the cloud with [pre-commit.ci](https://pre-commit.ci/, where hooks can auto-fix issues like styling and push them back to GitHub. Exact same execution and configuration.
* **Dependency isolation**. {precommit} leverages {renv} and hence ensures that anyone who uses the hooks uses the same version of the underlying tools, producing the same results, and does not touch your global R library or anything else unrelated to the hooks. _(This source is R based but it also applies to my Python usecase)_
* **No git history convolution**. Pre-commit detects problems before they enter your version control system, let’s you fix them, or fixes them automatically.
* **The power of the crowd**. Easily use hooks other people have created in bash, R, Python and other languages. There are a wealth of useful hooks available, most listed [here](https://pre-commit.com/hooks.html). For example, `check-added-large-files` prevents you from committing big files, other hooks validate json or yaml files and so on.
* **Extensible**. You can write your own R code to run as a hook, very easily.
* **Standing on the shoulders of giants**. Leveraging pre-commit.com drastically reduces complexity and abstracts away a lot of logic that is not R specific for the maintainers of {precommit}.
* **Independent.** pre-commit is not bound to GitHub, but runs on your local computer upon commit, and pre-commit.ci will support on other git hosts than GitHub in the future.

## Why REP-02: Pre-commit Hooks Exist Separate from CI
1. **Early, Local Feedback**
    - **Pre-commit** hooks run *on your machine* before you even type `git commit`.
    - They catch style/formatting errors, simple lint issues, and even run your smallest tests *instantaneously*, guiding you to fix things *before* you push. [example of lint issues include unused variables, unnecessary complexity, security vulnerabilities, formatting issues]
2. **CI Is Expensive & High-Latency**
    - The **OPS-01** CI pipeline (GitHub Actions) still runs the *same* checks when you open a PR—but that takes minutes, costs GitHub minutes, and clogs the CI queue if everyone skips local checks.
    - Pre-commit makes “green on the developer machine” the *norm*, so PRs rarely fail once they hit CI.
3. **Consistency and Onboarding**
    - A new contributor (or future me, six months later) clones the repo, installs pre-commit, and immediately formats code to my standards.
    - No more “But it looked fine on *my* laptop!”—the hook guarantees everyone’s running `black` with the same settings, the same `ruff` rules, and even `terraform fmt` on your IaC.
4. **Quality Gate vs. Quality Gate**
    - **Pre-commit** = *local* quality gate (fast, developer-facing).
    - **CI** = *remote* quality gate (authoritative, blocking merges).
    - Together they form a two-stage shield:
        1. You catch 90 % of issues locally, fixing them instantly.
        2. CI catches anything you missed (or anything new), ensuring the `main` branch stays rock solid.

## Remote CI workflow
Nothing magic is hiding in the CI workflow—each step simply invokes the tool you’ve already wired up locally. The only “formats” you need to have in place are the standard config files those tools expect. Here’s a quick rundown:

1. **GitHub-Actions YAML**
   * Must live at `.github/workflows/ci.yml` (or `.yaml`) and be valid YAML.
   * Top-level keys (`name`, `on`, `jobs`) must follow the GitHub Actions schema ← [(Read This)](https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions).

2. **actions/checkout**, **setup-python**
   * No special on-disk format beyond being in a Git repo.

3. **abatilo/actions-poetry & `poetry install`**
   * You need a **`pyproject.toml`** (and optionally a `poetry.lock`) in your repo root.

4. **`pre-commit run --all-files`**
   * Relies on your **`.pre-commit-config.yaml`** in the root.
   * The hooks listed (`black`, `ruff`, `mypy`, `detect-secrets`, `terraform_fmt`, `terraform_validate`) all read their configuration either from that file or from standard places (`pyproject.toml`, `.secrets.baseline`, `.terraform`).

5. **pytest + coverage**
   * Expects a `tests/` directory (or whatever you’ve configured in `pytest.ini` or `pyproject.toml`) with test files named `test_*.py`.
   * `coverage xml` will always produce `coverage.xml` which Codecov then reads.

6. **codecov/codecov-action**
   * Looks for a `coverage.xml` (or other coverage reports) in the path you point it at—here `./coverage.xml`.

7. **tfsec**
   * Scans any `.tf` files in your repo (or a directory you specify). No other format needed.

8. **checkov**
   * By default it will scan Terraform files and Dockerfiles anywhere in the repo. You’ve further narrowed it to `framework: terraform,dockerfile`.

---

**Bottom line:** as long as you have

* a valid GitHub Actions workflow YAML
* a `pyproject.toml` (for Poetry)
* a `.pre-commit-config.yaml`
* your `tests/` and terraform files in place

…then the CI steps will pick them up and run without any additional formatting requirements. The CI doesn’t enforce a new format—it just mirrors the config you’ve already set up locally.
