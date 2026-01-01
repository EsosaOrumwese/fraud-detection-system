"""Segment 5A S5 runner - validation bundle and pass flag."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import polars as pl

from engine.layers.l2.seg_5A.shared.control_plane import compute_sealed_inputs_digest
from engine.layers.l2.seg_5A.shared.dictionary import load_dictionary, render_dataset_path
from engine.layers.l2.seg_5A.shared.run_report import SegmentStateKey, write_segment_state_run_report


@dataclass(frozen=True)
class ValidationInputs:
    data_root: Path
    manifest_fingerprint: str
    run_id: str
    dictionary_path: Optional[Path] = None
    parameter_hash: Optional[str] = None


@dataclass(frozen=True)
class ValidationResult:
    bundle_index_path: Path
    report_path: Path
    issue_table_path: Path
    passed_flag_path: Path | None
    run_report_path: Path
    overall_status: str
    resumed: bool


class ValidationRunner:
    """Build the 5A validation bundle and `_passed.flag`."""

    _SPEC_VERSION = "1.0.0"

    def run(self, inputs: ValidationInputs) -> ValidationResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint

        receipt_path = data_root / render_dataset_path(
            dataset_id="s0_gate_receipt_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        sealed_path = data_root / render_dataset_path(
            dataset_id="sealed_inputs_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        receipt = self._load_json(receipt_path)
        sealed_df = self._load_parquet(sealed_path)

        issues: list[Mapping[str, Any]] = []
        if receipt is None:
            issues.append(
                self._issue(
                    manifest_fingerprint,
                    inputs.parameter_hash,
                    None,
                    "S5_PRECONDITION",
                    "S5_MISSING_RECEIPT",
                    "ERROR",
                    f"s0_gate_receipt_5A missing at {receipt_path}",
                )
            )
        if sealed_df is None:
            issues.append(
                self._issue(
                    manifest_fingerprint,
                    inputs.parameter_hash,
                    None,
                    "S5_PRECONDITION",
                    "S5_MISSING_SEALED_INPUTS",
                    "ERROR",
                    f"sealed_inputs_5A missing at {sealed_path}",
                )
            )

        parameter_hash = inputs.parameter_hash or (receipt or {}).get("parameter_hash")
        if not parameter_hash:
            parameter_hash = ""
            issues.append(
                self._issue(
                    manifest_fingerprint,
                    None,
                    None,
                    "S5_PRECONDITION",
                    "S5_MISSING_PARAMETER_HASH",
                    "ERROR",
                    "parameter_hash missing from receipt and inputs",
                )
            )
        parameter_hash_norm = self._normalise_parameter_hash(parameter_hash)

        scenario_ids = self._resolve_scenarios(
            data_root=data_root,
            manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
            receipt=receipt or {},
        )

        if receipt and receipt.get("manifest_fingerprint") != manifest_fingerprint:
            issues.append(
                self._issue(
                    manifest_fingerprint,
                    parameter_hash_norm,
                    None,
                    "S5_PRECONDITION",
                    "S5_RECEIPT_FINGERPRINT_MISMATCH",
                    "ERROR",
                    "s0_gate_receipt_5A manifest_fingerprint mismatch",
                )
            )

        if receipt and receipt.get("parameter_hash") not in (None, "", parameter_hash):
            issues.append(
                self._issue(
                    manifest_fingerprint,
                    parameter_hash_norm,
                    None,
                    "S5_PRECONDITION",
                    "S5_RECEIPT_PARAMETER_HASH_MISMATCH",
                    "ERROR",
                    "s0_gate_receipt_5A parameter_hash mismatch",
                )
            )

        if receipt and sealed_df is not None:
            rows = sealed_df.sort(["owner_layer", "owner_segment", "artifact_id"]).to_dicts()
            digest = compute_sealed_inputs_digest(rows)
            expected = receipt.get("sealed_inputs_digest")
            if expected and digest != expected:
                issues.append(
                    self._issue(
                        manifest_fingerprint,
                        parameter_hash_norm,
                        None,
                        "S5_PRECONDITION",
                        "S5_SEALED_DIGEST_MISMATCH",
                        "ERROR",
                        "sealed_inputs_5A digest mismatch with s0_gate_receipt_5A",
                    )
                )

        missing_outputs = self._check_outputs(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=str(parameter_hash),
            parameter_hash_norm=parameter_hash_norm,
            scenario_ids=scenario_ids,
            run_id=inputs.run_id,
        )
        issues.extend(missing_outputs)

        overall_status = self._overall_status(issues)
        passed_flag_path = data_root / render_dataset_path(
            dataset_id="validation_passed_flag_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if overall_status != "PASS" and passed_flag_path.exists():
            issues.append(
                self._issue(
                    manifest_fingerprint,
                    parameter_hash,
                    None,
                    "S5_GATE",
                    "S5_STALE_PASSED_FLAG",
                    "ERROR",
                    "existing _passed.flag present for FAILED bundle; manual intervention required",
                )
            )
            overall_status = self._overall_status(issues)

        issue_table_path = data_root / render_dataset_path(
            dataset_id="validation_issue_table_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        issue_table_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_issue_table(issue_table_path, issues)

        report_path = data_root / render_dataset_path(
            dataset_id="validation_report_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_payload = self._build_report(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash_norm,
            scenario_ids=scenario_ids,
            overall_status=overall_status,
            issues=issues,
            issue_path=issue_table_path,
        )
        report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

        index_path = data_root / render_dataset_path(
            dataset_id="validation_bundle_index_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        index_path.parent.mkdir(parents=True, exist_ok=True)
        entries = self._bundle_entries(
            report_path=report_path,
            issue_table_path=issue_table_path,
            receipt_path=receipt_path if receipt_path.exists() else None,
            sealed_path=sealed_path if sealed_path.exists() else None,
            sealed_outputs_path=self._sealed_outputs_path(
                data_root=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
            ),
        )
        bundle_digest = self._compute_bundle_digest(entries)
        index_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "segment_id": "5A",
            "s5_spec_version": self._SPEC_VERSION,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall_status,
            "summary": {
                "issues_total": len(issues),
                "entries_total": len(entries),
            },
            "entries": entries,
        }

        resumed = False
        if index_path.exists():
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if existing != index_payload:
                raise RuntimeError("S5_OUTPUT_CONFLICT: validation_bundle_index_5A differs")
            resumed = True
        else:
            index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")

        if overall_status == "PASS":
            flag_payload = {
                "manifest_fingerprint": manifest_fingerprint,
                "bundle_digest_sha256": bundle_digest,
            }
            if passed_flag_path.exists():
                existing = json.loads(passed_flag_path.read_text(encoding="utf-8"))
                if existing != flag_payload:
                    raise RuntimeError("S5_OUTPUT_CONFLICT: validation_passed_flag_5A differs")
                resumed = True
            else:
                passed_flag_path.parent.mkdir(parents=True, exist_ok=True)
                passed_flag_path.write_text(
                    json.dumps(flag_payload, indent=2, sort_keys=True), encoding="utf-8"
                )
        else:
            passed_flag_path = None

        run_report_path = data_root / render_dataset_path(
            dataset_id="s5_run_report_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer2",
            "segment": "5A",
            "state": "S5",
            "status": overall_status,
            "run_id": inputs.run_id,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash_norm,
            "overall_status": overall_status,
            "bundle_index_path": str(index_path),
            "validation_report_path": str(report_path),
            "validation_issue_table_path": str(issue_table_path),
            "passed_flag_path": str(passed_flag_path) if passed_flag_path else None,
            "resumed": resumed,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer2",
            segment="5A",
            state="S5",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash_norm,
            run_id=inputs.run_id,
        )
        segment_state_path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(
            path=segment_state_path,
            key=key,
            payload={
                **key.as_dict(),
                "status": overall_status,
                "run_report_path": str(run_report_path),
                "bundle_index_path": str(index_path),
                "overall_status": overall_status,
                "resumed": resumed,
            },
        )

        return ValidationResult(
            bundle_index_path=index_path,
            report_path=report_path,
            issue_table_path=issue_table_path,
            passed_flag_path=passed_flag_path,
            run_report_path=run_report_path,
            overall_status=overall_status,
            resumed=resumed,
        )

    def _resolve_scenarios(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
        receipt: Mapping[str, object],
    ) -> list[str]:
        manifest_path = data_root / render_dataset_path(
            dataset_id="scenario_manifest_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if manifest_path.exists():
            df = pl.read_parquet(manifest_path)
            ids = [str(val) for val in df.get_column("scenario_id").drop_nulls().unique().to_list()]
            return ids or ["baseline"]
        scenario_value = receipt.get("scenario_id")
        if isinstance(scenario_value, str):
            return [scenario_value]
        if isinstance(scenario_value, Sequence):
            ids = [str(item) for item in scenario_value if item]
            return ids or ["baseline"]
        return ["baseline"]

    def _check_outputs(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        parameter_hash: str,
        parameter_hash_norm: str,
        scenario_ids: Sequence[str],
        run_id: str,
    ) -> list[Mapping[str, Any]]:
        issues: list[Mapping[str, Any]] = []
        datasets = dictionary.get("datasets", [])  # type: ignore[arg-type]
        for entry in datasets:
            lineage = entry.get("lineage", {})
            produced_by = lineage.get("produced_by") or []
            if "5A.S5" in produced_by:
                continue
            if not any(tag in produced_by for tag in ("5A.S1", "5A.S2", "5A.S3", "5A.S4")):
                if "5A.S5" not in (lineage.get("consumed_by") or []):
                    continue
            dataset_id = entry.get("id")
            if not dataset_id:
                continue
            path_template = str(entry.get("path") or "")
            status = str(entry.get("status") or "optional").lower()
            if status == "ignored":
                continue
            severity = "ERROR" if status == "required" else "WARN"
            scenario_required = "{scenario_id}" in path_template
            targets = scenario_ids if scenario_required else [None]
            for scenario_id in targets:
                template_args = {
                    "manifest_fingerprint": manifest_fingerprint,
                    "fingerprint": manifest_fingerprint,
                    "parameter_hash": parameter_hash,
                    "run_id": run_id,
                }
                if scenario_id:
                    template_args["scenario_id"] = scenario_id
                rel_path = render_dataset_path(
                    dataset_id=dataset_id,
                    template_args=template_args,
                    dictionary=dictionary,
                )
                path = data_root / rel_path
                if not path.exists() and not Path(rel_path).is_absolute():
                    try:
                        from engine.layers.l2.seg_5A.shared.dictionary import repository_root

                        repo_path = repository_root() / rel_path
                        if repo_path.exists():
                            path = repo_path
                    except Exception:
                        pass
                if self._path_exists(path):
                    continue
                issues.append(
                    self._issue(
                        manifest_fingerprint,
                        parameter_hash_norm,
                        scenario_id,
                        "S5_OUTPUTS",
                        "S5_MISSING_OUTPUT",
                        severity,
                        f"missing output {dataset_id} at {path}",
                    )
                )
        return issues

    def _path_exists(self, path: Path) -> bool:
        if path.exists():
            if path.is_dir():
                return any(p.is_file() for p in path.rglob("*"))
            return True
        return False

    def _build_report(
        self,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        scenario_ids: Sequence[str],
        overall_status: str,
        issues: Sequence[Mapping[str, Any]],
        issue_path: Path,
    ) -> Mapping[str, Any]:
        scenario_statuses = []
        for scenario_id in scenario_ids:
            status = "PASS"
            scenario_issues = [i for i in issues if i.get("scenario_id") == scenario_id]
            if any(i.get("severity") == "ERROR" for i in scenario_issues):
                status = "FAIL"
            elif scenario_issues:
                status = "WARN"
            scenario_statuses.append(
                {"parameter_hash": parameter_hash, "scenario_id": scenario_id, "status": status}
            )
        missing_required = sum(1 for i in issues if i.get("severity") == "ERROR")
        missing_optional = sum(1 for i in issues if i.get("severity") == "WARN")
        checks = [
            {
                "check_id": "outputs_present",
                "status": overall_status if overall_status != "PASS" else "PASS",
                "metrics": {
                    "missing_required": missing_required,
                    "missing_optional": missing_optional,
                },
            }
        ]
        return {
            "manifest_fingerprint": manifest_fingerprint,
            "s5_spec_version": self._SPEC_VERSION,
            "parameter_hashes": [parameter_hash] if parameter_hash else [],
            "scenarios": scenario_statuses,
            "checks": checks,
            "issues_path": str(issue_path),
            "notes": "S5 validation bundle generated by engine",
        }

    def _write_issue_table(self, path: Path, issues: Sequence[Mapping[str, Any]]) -> None:
        df = pl.DataFrame(issues)
        if df.is_empty():
            df = pl.DataFrame(
                {
                    "manifest_fingerprint": pl.Series([], dtype=pl.Utf8),
                    "parameter_hash": pl.Series([], dtype=pl.Utf8),
                    "scenario_id": pl.Series([], dtype=pl.Utf8),
                    "segment": pl.Series([], dtype=pl.Utf8),
                    "check_id": pl.Series([], dtype=pl.Utf8),
                    "issue_code": pl.Series([], dtype=pl.Utf8),
                    "severity": pl.Series([], dtype=pl.Utf8),
                    "message": pl.Series([], dtype=pl.Utf8),
                }
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)

    def _bundle_entries(
        self,
        *,
        report_path: Path,
        issue_table_path: Path,
        receipt_path: Optional[Path],
        sealed_path: Optional[Path],
        sealed_outputs_path: Optional[Path],
    ) -> list[Mapping[str, Any]]:
        entries: list[Mapping[str, Any]] = []
        for path in [report_path, issue_table_path, receipt_path, sealed_path, sealed_outputs_path]:
            if path is None or not path.exists():
                continue
            entries.append({"path": str(path), "sha256_hex": self._sha256_path(path)})
        entries.sort(key=lambda row: row["path"])
        return entries

    def _compute_bundle_digest(self, entries: Sequence[Mapping[str, Any]]) -> str:
        concat = "".join(entry["sha256_hex"] for entry in entries)
        return sha256(concat.encode("ascii")).hexdigest()

    def _sha256_path(self, path: Path) -> str:
        if path.is_dir():
            digest = sha256()
            for file_path in sorted([p for p in path.rglob("*") if p.is_file()], key=lambda p: p.as_posix()):
                digest.update(file_path.read_bytes())
            return digest.hexdigest()
        return sha256(path.read_bytes()).hexdigest()

    def _issue(
        self,
        manifest_fingerprint: str,
        parameter_hash: Optional[str],
        scenario_id: Optional[str],
        check_id: str,
        issue_code: str,
        severity: str,
        message: str,
    ) -> Mapping[str, Any]:
        return {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": self._normalise_parameter_hash(parameter_hash or ""),
            "scenario_id": scenario_id,
            "segment": "5A",
            "check_id": check_id,
            "issue_code": issue_code,
            "severity": severity,
            "message": message,
        }

    def _overall_status(self, issues: Sequence[Mapping[str, Any]]) -> str:
        if any(issue.get("severity") == "ERROR" for issue in issues):
            return "FAIL"
        if issues:
            return "WARN"
        return "PASS"

    def _normalise_parameter_hash(self, value: str) -> str:
        if isinstance(value, str) and len(value) == 64:
            try:
                int(value, 16)
                return value.lower()
            except ValueError:
                pass
        return "0" * 64

    def _load_json(self, path: Path) -> Optional[Mapping[str, Any]]:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_parquet(self, path: Path) -> Optional[pl.DataFrame]:
        if not path.exists():
            return None
        return pl.read_parquet(path)

    def _sealed_outputs_path(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> Optional[Path]:
        path = data_root / render_dataset_path(
            dataset_id="sealed_outputs_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        return path if path.exists() else None


__all__ = ["ValidationInputs", "ValidationResult", "ValidationRunner"]
