# Authoring Guide — `virtual_logging_policy` (3B run-log rotation + retention)

## 0) Purpose

`virtual_logging_policy` governs **rotation + retention** for 3B’s run-scoped operational logs under:

* `logs/virtual/{run_id}/edge_progress.log`  *(crash-safe restart progress)*
* `logs/virtual/{run_id}/virtual_audit.log` *(batch audit lines)*

It’s sealed by 3B.S0 as a token-less config, so it must be **stable**, **non-toy**, and **decision-free** for Codex.

---

## 1) File identity (MUST)

* **Artefact name:** `virtual_logging_policy`
* **Path:** `config/logging/virtual_logging.yml`
* **Format:** YAML (UTF-8, LF newlines)
* **Digest posture:** **do not** embed any digest field in-file (S0 sealing inventory records file digest)

---

## 2) Required file shape (pinned by this guide)

Top-level YAML object with **exactly** these keys:

* `policy_id` : string, MUST be `virtual_logging_policy`
* `version` : string, non-placeholder (e.g. `v1.0.0`)
* `run_log_root` : string, MUST be `logs/virtual`
* `managed_logs` : list (exactly 2 entries; see §3)
* `retention` : object (run-directory retention; see §4)
* `housekeeping` : object (global disk caps + deletion order; see §5)

No extra keys at top-level.

---

## 3) Managed logs (MUST)

`managed_logs` MUST be a list with exactly these two entries (order pinned):

### 3.1 Entry 1 — edge progress log

```yaml
- logical_id: edge_progress_log
  filename: edge_progress.log
  write_mode: append_only
  flush_policy:
    flush_each_line: true
    fsync_every_n_lines: 50
  rotation:
    mode: size_bytes
    max_bytes: 16777216          # 16 MiB
    keep_files: 10
    compress_rotated: true
  protection:
    never_delete_active_file: true
```

### 3.2 Entry 2 — virtual audit log

```yaml
- logical_id: virtual_audit_log
  filename: virtual_audit.log
  write_mode: append_only
  flush_policy:
    flush_each_line: false
    fsync_every_n_lines: 200
  rotation:
    mode: size_bytes
    max_bytes: 268435456         # 256 MiB
    keep_files: 20
    compress_rotated: true
  protection:
    never_delete_active_file: true
```

**Pinned semantics (v1):**

* “Active file” means the non-suffixed file (`edge_progress.log` / `virtual_audit.log`) in the current `run_id` directory.
* Rotation naming is fixed:

  * on rotate: rename `X.log` → `X.log.1` (then compress to `.gz` if enabled)
  * shift existing suffixes upward (`.1` → `.2`, etc.), dropping anything beyond `keep_files`

---

## 4) Retention (run directories) (MUST)

`retention` is applied at the **run directory** level: `logs/virtual/{run_id}/`.

Pinned v1 shape:

```yaml
retention:
  keep_run_days: 365
  keep_min_completed_runs: 200
  never_delete_runs_newer_than_days: 14
```

Pinned v1 semantics:

* “Completed run” is defined by existence of either:

  * `data/layer1/3B/validation/fingerprint={manifest_fingerprint}/_passed.flag_3B` **or**
  * a run-local marker file `logs/virtual/{run_id}/RUN_COMPLETE.marker`
* Housekeeping MAY delete only completed runs (never delete incomplete runs).
* Even for completed runs:

  * never delete any run newer than `never_delete_runs_newer_than_days`
  * always keep at least `keep_min_completed_runs`

---

## 5) Housekeeping (global caps) (MUST; non-toy safeguards)

Pinned v1 shape:

```yaml
housekeeping:
  max_total_bytes_under_run_log_root: 214748364800   # 200 GiB
  max_bytes_per_run_dir: 2147483648                 # 2 GiB
  deletion_order: oldest_completed_first
  on_over_budget: delete_whole_run_dir
```

Pinned v1 semantics:

* If a single run dir exceeds `max_bytes_per_run_dir`, delete that run dir **only if completed**; otherwise abort housekeeping and emit an alert.
* If total bytes under `logs/virtual/` exceed `max_total_bytes_under_run_log_root`, delete **completed** run dirs oldest-first until under budget.
* Housekeeping MUST NOT partially delete log files inside a run dir when `on_over_budget=delete_whole_run_dir` (prevents “restart broken by partial deletion”).

---

## 6) Realism floors (MUST; prevents toy configs)

Codex MUST reject this config if any fail:

* `keep_run_days < 30`
* `keep_min_completed_runs < 50`
* `never_delete_runs_newer_than_days < 7`
* `edge_progress_log.rotation.max_bytes < 1_048_576` (1 MiB)
* `virtual_audit_log.rotation.max_bytes < 67_108_864` (64 MiB)
* `virtual_audit_log.rotation.keep_files < 10`
* `max_total_bytes_under_run_log_root < 53_687_091_200` (50 GiB)
* `max_bytes_per_run_dir < 536_870_912` (512 MiB)
* any managed log is missing `append_only` write mode or active-file protection

---

## 7) Recommended v1 production file (copy/paste)

```yaml
policy_id: virtual_logging_policy
version: v1.0.0
run_log_root: logs/virtual

managed_logs:
  - logical_id: edge_progress_log
    filename: edge_progress.log
    write_mode: append_only
    flush_policy:
      flush_each_line: true
      fsync_every_n_lines: 50
    rotation:
      mode: size_bytes
      max_bytes: 16777216
      keep_files: 10
      compress_rotated: true
    protection:
      never_delete_active_file: true

  - logical_id: virtual_audit_log
    filename: virtual_audit.log
    write_mode: append_only
    flush_policy:
      flush_each_line: false
      fsync_every_n_lines: 200
    rotation:
      mode: size_bytes
      max_bytes: 268435456
      keep_files: 20
      compress_rotated: true
    protection:
      never_delete_active_file: true

retention:
  keep_run_days: 365
  keep_min_completed_runs: 200
  never_delete_runs_newer_than_days: 14

housekeeping:
  max_total_bytes_under_run_log_root: 214748364800
  max_bytes_per_run_dir: 2147483648
  deletion_order: oldest_completed_first
  on_over_budget: delete_whole_run_dir
```

---

## 8) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Top-level keys exactly as §2; managed_logs exactly the two entries in §3.
3. All realism floors in §6 pass.
4. Deterministic formatting (UTF-8, LF). No timestamps/“generated_at”.
