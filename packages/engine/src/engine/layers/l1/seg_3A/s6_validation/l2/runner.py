"""Segment 3A S6 runner – validation bundle and receipt."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_3A.s0_gate.exceptions import err
from engine.layers.l1.seg_3A.s0_gate.l0 import aggregate_sha256, expand_files, hash_files
from engine.layers.l1.seg_3A.shared import SegmentStateKey, load_schema, render_dataset_path, write_segment_state_run_report
from engine.layers.l1.seg_3A.shared.dictionary import load_dictionary
from engine.layers.l1.seg_3A.s5_zone_alloc.l2.runner import _validate_table_rows

_S0_RECEIPT_SCHEMA = Draft202012Validator(load_schema("#/validation/s0_gate_receipt_3A"))
_ZONE_ALLOC_SCHEMA = Draft202012Validator(load_schema("#/egress/zone_alloc"))
_S6_VALIDATION_SCHEMA = Draft202012Validator(load_schema("#/validation/s6_validation_report_3A"))
_S6_ISSUE_SCHEMA = Draft202012Validator(load_schema("#/validation/s6_issue_table_3A"))
_S6_RECEIPT_SCHEMA = Draft202012Validator(load_schema("#/validation/s6_receipt_3A"))


@dataclass(frozen=True)
class ValidationInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ValidationResult:
    validation_bundle_path: Path
    receipt_path: Path
    run_report_path: Path
    resumed: bool


class ValidationRunner:
    """Structural validation and bundle creation for Segment 3A."""

    def run(self, inputs: ValidationInputs) -> ValidationResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        parameter_hash = inputs.parameter_hash
        seed = inputs.seed

        s0_receipt = self._load_s0_receipt(
            base=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
        )
        if str(s0_receipt.get("parameter_hash")) != str(parameter_hash):
            raise err("E_PARAM_HASH", "parameter_hash mismatch between inputs and S0 receipt")

        zone_alloc_path = data_root / render_dataset_path(
            dataset_id="zone_alloc",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not zone_alloc_path.exists():
            raise err("E_UPSTREAM_MISSING", "zone_alloc missing for S6")

        zone_alloc_df = pl.read_parquet(zone_alloc_path)
        issues = self._run_checks(zone_alloc_df)
        overall_status = "PASS" if not issues else "FAIL"

        validation_bundle_dir = data_root / render_dataset_path(
            dataset_id="validation_bundle_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        validation_bundle_dir.mkdir(parents=True, exist_ok=True)

        report_path = validation_bundle_dir / "s6_validation_report_3A.json"
        issues_path = validation_bundle_dir / "s6_issue_table_3A.parquet"
        receipt_path = validation_bundle_dir / "s6_receipt_3A.json"

        # Also write to catalogued dictionary paths
        report_dict_path = data_root / render_dataset_path(
            dataset_id="s6_validation_report_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        report_dict_path.parent.mkdir(parents=True, exist_ok=True)
        issues_dict_path = data_root / render_dataset_path(
            dataset_id="s6_issue_table_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        issues_dict_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_dict_path = data_root / render_dataset_path(
            dataset_id="s6_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        receipt_dict_path.parent.mkdir(parents=True, exist_ok=True)

        report_payload = self._write_validation_report(
            path=report_path,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            overall_status=overall_status,
            issues=issues,
        )
        report_dict_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

        self._write_issue_table(issues_path, manifest_fingerprint, issues)
        pl.read_parquet(issues_path).write_parquet(issues_dict_path)

        self._write_receipt(
            path=receipt_path,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            report_path=report_path,
            issues_path=issues_path,
            overall_status=overall_status,
        )
        receipt_dict_path.write_text(receipt_path.read_text(encoding="utf-8"), encoding="utf-8")

        flag_path = validation_bundle_dir / "_passed.flag_3A"
        if overall_status == "PASS":
            flag_path.write_text("PASS", encoding="utf-8")
        elif flag_path.exists():
            flag_path.unlink()

        run_report_path = (
            data_root
            / f"reports/l1/3A/s6_validation/seed={seed}/fingerprint={manifest_fingerprint}/run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3A",
            "state": "S6",
            "status": overall_status,
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "issues": len(issues),
            "validation_report_path": str(report_path),
            "issues_path": str(issues_path),
            "receipt_path": str(receipt_path),
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer1",
            segment="3A",
            state="S6",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        report_dataset_path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(
            path=report_dataset_path,
            key=key,
            payload={
                **key.as_dict(),
                "status": overall_status,
                "attempt": 1,
                "output_path": str(validation_bundle_dir),
                "run_report_path": str(run_report_path),
                "resumed": False,
            },
        )

        return ValidationResult(
            validation_bundle_path=validation_bundle_dir,
            receipt_path=receipt_path,
            run_report_path=run_report_path,
            resumed=False,
        )

    # -------------------------------------------------------------- helpers
    def _load_s0_receipt(self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]) -> Mapping[str, Any]:
        receipt_path = base / render_dataset_path(
            dataset_id="s0_gate_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not receipt_path.exists():
            raise err("E_S0_PRECONDITION", f"S0 receipt missing at '{receipt_path}'")
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        try:
            _S0_RECEIPT_SCHEMA.validate(payload)
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s0 receipt invalid: {exc.message}") from exc
        return payload

    def _run_checks(self, zone_alloc_df: pl.DataFrame) -> list[Mapping[str, Any]]:
        issues: list[Mapping[str, Any]] = []
        # schema-level validation using table plan
        try:
            _validate_table_rows(zone_alloc_df, load_schema("#/egress/zone_alloc"), error_prefix="zone_alloc")
        except Exception as exc:
            issues.append(
                {
                    "issue_code": "SCHEMA_ZONE_ALLOC",
                    "check_id": "schema",
                    "severity": "ERROR",
                    "message": str(exc),
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
        # count conservation per pair
        grouped = zone_alloc_df.group_by(["merchant_id", "legal_country_iso"]).agg(
            [
                pl.col("zone_site_count").sum().alias("zone_sum"),
                pl.col("site_count").first().alias("site_count"),
            ]
        )
        for rec in grouped.to_dicts():
            if int(rec["zone_sum"]) != int(rec["site_count"]):
                issues.append(
                    {
                        "issue_code": "COUNT_MISMATCH",
                        "check_id": "count_conservation",
                        "severity": "ERROR",
                        "message": f"zone counts sum {rec['zone_sum']} != site_count {rec['site_count']}",
                        "merchant_id": rec.get("merchant_id"),
                        "legal_country_iso": rec.get("legal_country_iso"),
                        "tzid": None,
                    }
                )
        return issues

    def _write_validation_report(
        self,
        *,
        path: Path,
        manifest_fingerprint: str,
        parameter_hash: str,
        overall_status: str,
        issues: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        checks = []
        if issues:
            checks_failed = len(issues)
            checks.append(
                {
                    "check_id": "schema_count",
                    "status": "FAIL",
                    "severity": "ERROR",
                    "affected_count": checks_failed,
                    "notes": "schema or count conservation failures",
                }
            )
        else:
            checks.append(
                {
                    "check_id": "schema_count",
                    "status": "PASS",
                    "severity": "INFO",
                    "affected_count": 0,
                    "notes": "",
                }
            )
        payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "overall_status": "PASS" if overall_status == "PASS" else "FAIL",
            "checks_passed_count": 0 if issues else 1,
            "checks_failed_count": len(issues),
            "checks_warn_count": 0,
            "checks": checks,
        }
        try:
            _S6_VALIDATION_SCHEMA.validate(payload)
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s6_validation_report invalid: {exc.message}") from exc
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    def _write_issue_table(self, path: Path, manifest_fingerprint: str, issues: Sequence[Mapping[str, Any]]) -> None:
        if not issues:
            df = pl.DataFrame(
                schema={
                    "manifest_fingerprint": pl.Utf8,
                    "issue_code": pl.Utf8,
                    "check_id": pl.Utf8,
                    "severity": pl.Utf8,
                    "message": pl.Utf8,
                    "merchant_id": pl.Int64,
                    "legal_country_iso": pl.Utf8,
                    "tzid": pl.Utf8,
                    "details": pl.Utf8,
                }
            )
            df.write_parquet(path)
            return
        rows = []
        for issue in issues:
            payload = {
                "manifest_fingerprint": manifest_fingerprint,
                "issue_code": issue.get("issue_code"),
                "check_id": issue.get("check_id"),
                "severity": issue.get("severity", "ERROR"),
                "message": issue.get("message"),
                "merchant_id": issue.get("merchant_id"),
                "legal_country_iso": issue.get("legal_country_iso"),
                "tzid": issue.get("tzid"),
                "details": issue.get("details"),
            }
            try:
                _S6_ISSUE_SCHEMA.validate(payload)
            except ValidationError as exc:
                raise err("E_SCHEMA", f"s6_issue_table row invalid: {exc.message}") from exc
            rows.append(payload)
        pl.DataFrame(rows).write_parquet(path)

    def _write_receipt(
        self,
        *,
        path: Path,
        manifest_fingerprint: str,
        parameter_hash: str,
        report_path: Path,
        issues_path: Path,
        overall_status: str,
    ) -> None:
        report_digest = aggregate_sha256(hash_files(expand_files(report_path), error_prefix="s6_report"))
        issues_digest = aggregate_sha256(hash_files(expand_files(issues_path), error_prefix="s6_issues"))
        payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "s6_version": "1.0.0",
            "overall_status": overall_status,
            "checks_passed_count": 0 if overall_status != "PASS" else 1,
            "checks_failed_count": 0 if overall_status == "PASS" else 1,
            "checks_warn_count": 0,
            "check_status_map": {
                "schema": {"status": "PASS" if overall_status == "PASS" else "FAIL", "severity": "INFO"}
            },
            "validation_report_digest": report_digest,
            "issue_table_digest": issues_digest,
            "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        try:
            _S6_RECEIPT_SCHEMA.validate(payload)
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s6_receipt invalid: {exc.message}") from exc
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
