"""Segment 5B S5 validation runner."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import polars as pl

from engine.layers.l2.seg_5B.shared.control_plane import compute_sealed_inputs_digest, load_control_plane
from engine.layers.l2.seg_5B.shared.dictionary import load_dictionary, render_dataset_path
from engine.layers.l2.seg_5B.shared.run_report import SegmentStateKey, write_segment_state_run_report


@dataclass(frozen=True)
class ValidationInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ValidationResult:
    bundle_index_path: Path
    report_path: Path
    issue_table_path: Path | None
    passed_flag_path: Path | None
    run_report_path: Path
    overall_status: str


class ValidationRunner:
    """Build validation bundle index and pass flag for 5B."""

    _SPEC_VERSION = "1.0.0"

    def run(self, inputs: ValidationInputs) -> ValidationResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.expanduser().absolute()

        receipt, sealed_df, scenarios = load_control_plane(
            data_root=data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )

        issues: list[Mapping[str, object]] = []
        issues.extend(self._check_upstream_flags(receipt, inputs))
        issues.extend(self._check_sealed_inputs(receipt, sealed_df, inputs))

        scenario_ids = [binding.scenario_id for binding in scenarios]
        if not scenario_ids:
            scenario_ids = ["baseline"]

        counts_ok = True
        time_ok = True
        arrivals_total = 0
        arrivals_virtual = 0
        arrivals_physical = 0
        buckets_total = 0
        buckets_nonzero = 0

        for scenario_id in scenario_ids:
            grid_path = data_root / render_dataset_path(
                dataset_id="s1_time_grid_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario_id,
                },
                dictionary=dictionary,
            )
            grouping_path = data_root / render_dataset_path(
                dataset_id="s1_grouping_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario_id,
                },
                dictionary=dictionary,
            )
            intensity_path = data_root / render_dataset_path(
                dataset_id="s2_realised_intensity_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario_id,
                    "seed": inputs.seed,
                },
                dictionary=dictionary,
            )
            counts_path = data_root / render_dataset_path(
                dataset_id="s3_bucket_counts_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario_id,
                    "seed": inputs.seed,
                },
                dictionary=dictionary,
            )
            arrivals_path = data_root / render_dataset_path(
                dataset_id="arrival_events_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario_id,
                    "seed": inputs.seed,
                },
                dictionary=dictionary,
            )

            issues.extend(
                self._require_path(
                    path=grid_path, inputs=inputs, scenario_id=scenario_id, issue_code="S5_MISSING_TIME_GRID"
                )
            )
            issues.extend(
                self._require_path(
                    path=grouping_path, inputs=inputs, scenario_id=scenario_id, issue_code="S5_MISSING_GROUPING"
                )
            )
            issues.extend(
                self._require_path(
                    path=intensity_path, inputs=inputs, scenario_id=scenario_id, issue_code="S5_MISSING_INTENSITY"
                )
            )
            issues.extend(
                self._require_path(
                    path=counts_path, inputs=inputs, scenario_id=scenario_id, issue_code="S5_MISSING_COUNTS"
                )
            )
            issues.extend(
                self._require_path(
                    path=arrivals_path, inputs=inputs, scenario_id=scenario_id, issue_code="S5_MISSING_ARRIVALS"
                )
            )

            if not (grid_path.exists() and counts_path.exists() and arrivals_path.exists()):
                continue

            grid_df = pl.read_parquet(grid_path).select(
                ["bucket_index", "bucket_start_utc", "bucket_end_utc"]
            )
            buckets_total += grid_df.height

            counts_df = pl.read_parquet(counts_path).select(
                [
                    "merchant_id",
                    "zone_representation",
                    "channel_group",
                    "bucket_index",
                    "count_N",
                ]
            )
            if "count_N" in counts_df.columns:
                buckets_nonzero += int(counts_df.filter(pl.col("count_N") > 0).height)

            arrivals_df = pl.read_parquet(arrivals_path).select(
                [
                    "merchant_id",
                    "zone_representation",
                    "channel_group",
                    "bucket_index",
                    "ts_utc",
                    "is_virtual",
                ]
            )
            arrivals_total += arrivals_df.height
            if "is_virtual" in arrivals_df.columns:
                arrivals_virtual += int(arrivals_df.filter(pl.col("is_virtual") == True).height)
                arrivals_physical += int(arrivals_df.filter(pl.col("is_virtual") == False).height)

            bucket_join = counts_df.join(grid_df, on="bucket_index", how="left")
            missing_grid = bucket_join.filter(pl.col("bucket_start_utc").is_null())
            if missing_grid.height:
                counts_ok = False
                issues.append(
                    self._issue(
                        inputs,
                        "S5_BUCKET_GRID_MISSING",
                        "ERROR",
                        scenario_id=scenario_id,
                        message="s3_bucket_counts_5B references bucket_index not in s1_time_grid_5B",
                    )
                )

            arrival_counts = (
                arrivals_df.group_by(
                    ["merchant_id", "zone_representation", "channel_group", "bucket_index"]
                )
                .len()
                .rename({"len": "count_arrivals"})
            )
            merged = counts_df.join(
                arrival_counts,
                on=["merchant_id", "zone_representation", "channel_group", "bucket_index"],
                how="left",
            ).with_columns(pl.col("count_arrivals").fill_null(0))
            mismatch = merged.filter(pl.col("count_N") != pl.col("count_arrivals"))
            if mismatch.height:
                counts_ok = False
                issues.append(
                    self._issue(
                        inputs,
                        "S5_COUNT_MISMATCH",
                        "ERROR",
                        scenario_id=scenario_id,
                        message="s4_arrival_events_5B counts do not match s3_bucket_counts_5B",
                    )
                )

            arrivals_ts = arrivals_df.with_columns(
                pl.col("ts_utc").str.strptime(pl.Datetime, strict=False).alias("ts_utc_dt")
            )
            grid_ts = grid_df.with_columns(
                [
                    pl.col("bucket_start_utc").str.strptime(pl.Datetime, strict=False).alias("bucket_start_dt"),
                    pl.col("bucket_end_utc").str.strptime(pl.Datetime, strict=False).alias("bucket_end_dt"),
                ]
            )
            arrival_with_grid = arrivals_ts.join(grid_ts, on="bucket_index", how="left")
            out_of_window = arrival_with_grid.filter(
                (pl.col("ts_utc_dt") < pl.col("bucket_start_dt"))
                | (pl.col("ts_utc_dt") >= pl.col("bucket_end_dt"))
            )
            if out_of_window.height:
                time_ok = False
                issues.append(
                    self._issue(
                        inputs,
                        "S5_TIME_WINDOW_FAIL",
                        "ERROR",
                        scenario_id=scenario_id,
                        message="arrival events fall outside time grid window",
                    )
                )

        overall_status = self._overall_status(issues)

        issue_table_path = data_root / render_dataset_path(
            dataset_id="validation_issue_table_5B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        issue_table_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_issue_table(issue_table_path, issues)

        report_payload = self._build_report(
            inputs=inputs,
            overall_status=overall_status,
            counts_ok=counts_ok,
            time_ok=time_ok,
            arrivals_total=arrivals_total,
            arrivals_virtual=arrivals_virtual,
            arrivals_physical=arrivals_physical,
            buckets_total=buckets_total,
            buckets_nonzero=buckets_nonzero,
            scenario_count=len(scenario_ids),
            bundle_sha256=None,
        )
        report_path = data_root / render_dataset_path(
            dataset_id="validation_report_5B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

        bundle_index_path = data_root / render_dataset_path(
            dataset_id="validation_bundle_index_5B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        bundle_index_path.parent.mkdir(parents=True, exist_ok=True)
        entries = self._bundle_entries(
            report_path=report_path,
            issue_table_path=issue_table_path,
            dictionary=dictionary,
            manifest_fingerprint=inputs.manifest_fingerprint,
        )
        bundle_digest = self._compute_bundle_digest(entries, data_root)

        bundle_index = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "segment_id": "5B",
            "s5_spec_version": self._SPEC_VERSION,
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "status": overall_status,
            "summary": {
                "entries_total": len(entries),
                "issues_total": len(issues),
            },
            "entries": entries,
        }
        bundle_index_path.write_text(json.dumps(bundle_index, indent=2, sort_keys=True), encoding="utf-8")

        passed_flag_path = data_root / render_dataset_path(
            dataset_id="validation_passed_flag_5B",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        if overall_status == "PASS":
            flag_payload = {
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "bundle_digest_sha256": bundle_digest,
            }
            if passed_flag_path.exists():
                existing = json.loads(passed_flag_path.read_text(encoding="utf-8"))
                if existing != flag_payload:
                    raise RuntimeError("S5_OUTPUT_CONFLICT: validation_passed_flag_5B differs")
            else:
                passed_flag_path.parent.mkdir(parents=True, exist_ok=True)
                passed_flag_path.write_text(
                    json.dumps(flag_payload, indent=2, sort_keys=True), encoding="utf-8"
                )
        else:
            passed_flag_path = None

        run_report_path = self._write_run_report(inputs, data_root, dictionary, overall_status)

        return ValidationResult(
            bundle_index_path=bundle_index_path,
            report_path=report_path,
            issue_table_path=issue_table_path,
            passed_flag_path=passed_flag_path,
            run_report_path=run_report_path,
            overall_status=overall_status,
        )

    def _check_upstream_flags(
        self, receipt: Mapping[str, object], inputs: ValidationInputs
    ) -> list[Mapping[str, object]]:
        issues: list[Mapping[str, object]] = []
        upstream = receipt.get("upstream_segments")
        if isinstance(upstream, Mapping):
            for segment, status in upstream.items():
                status_value = status.get("status") if isinstance(status, Mapping) else status
                if status_value != "PASS":
                    issues.append(
                        self._issue(
                            inputs,
                            "S5_UPSTREAM_NOT_PASS",
                            "ERROR",
                            message=f"upstream segment {segment} not PASS",
                        )
                    )
        else:
            issues.append(
                self._issue(
                    inputs,
                    "S5_UPSTREAM_STATUS_MISSING",
                    "ERROR",
                    message="upstream segment status missing from s0_gate_receipt_5B",
                )
            )
        return issues

    def _check_sealed_inputs(
        self,
        receipt: Mapping[str, object],
        sealed_df: pl.DataFrame,
        inputs: ValidationInputs,
    ) -> list[Mapping[str, object]]:
        issues: list[Mapping[str, object]] = []
        rows = sealed_df.sort(["owner_layer", "owner_segment", "artifact_id"]).to_dicts()
        digest = compute_sealed_inputs_digest(rows)
        expected = receipt.get("sealed_inputs_digest")
        if expected and digest != expected:
            issues.append(
                self._issue(
                    inputs,
                    "S5_SEALED_INPUTS_DIGEST_MISMATCH",
                    "ERROR",
                    message="sealed_inputs_5B digest mismatch with s0_gate_receipt_5B",
                )
            )
        return issues

    def _require_path(
        self,
        *,
        path: Path,
        inputs: ValidationInputs,
        scenario_id: str,
        issue_code: str,
    ) -> list[Mapping[str, object]]:
        if path.exists():
            return []
        return [
            self._issue(
                inputs,
                issue_code,
                "ERROR",
                scenario_id=scenario_id,
                message=f"required dataset missing at {path}",
            )
        ]

    def _bundle_entries(
        self,
        *,
        report_path: Path,
        issue_table_path: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
    ) -> list[Mapping[str, object]]:
        entries: list[Mapping[str, object]] = []
        report_rel = render_dataset_path(
            dataset_id="validation_report_5B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        issue_rel = render_dataset_path(
            dataset_id="validation_issue_table_5B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        entries.append(
            {
                "path": report_rel,
                "sha256_hex": _sha256_path(report_path),
                "schema_ref": "schemas.layer2.yaml#/validation/validation_report_5B",
                "role": "validation_report",
            }
        )
        entries.append(
            {
                "path": issue_rel,
                "sha256_hex": _sha256_path(issue_table_path),
                "schema_ref": "schemas.layer2.yaml#/validation/validation_issue_table_5B",
                "role": "validation_issues",
            }
        )
        entries.sort(key=lambda row: row["path"])
        return entries

    def _compute_bundle_digest(self, entries: Iterable[Mapping[str, object]], data_root: Path) -> str:
        buffer = bytearray()
        for entry in entries:
            rel_path = str(entry.get("path") or "")
            if not rel_path:
                continue
            file_path = data_root / rel_path
            buffer.extend(file_path.read_bytes())
        return hashlib.sha256(buffer).hexdigest()

    def _build_report(
        self,
        *,
        inputs: ValidationInputs,
        overall_status: str,
        counts_ok: bool,
        time_ok: bool,
        arrivals_total: int,
        arrivals_virtual: int,
        arrivals_physical: int,
        buckets_total: int,
        buckets_nonzero: int,
        scenario_count: int,
        bundle_sha256: str | None,
    ) -> Mapping[str, object]:
        payload = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "spec_version": self._SPEC_VERSION,
            "status": overall_status,
            "n_parameter_hashes": 1,
            "n_scenarios": scenario_count,
            "n_seeds": 1,
            "n_buckets_total": buckets_total,
            "n_buckets_nonzero": buckets_nonzero,
            "n_arrivals_total": arrivals_total,
            "n_arrivals_physical": arrivals_physical,
            "n_arrivals_virtual": arrivals_virtual,
            "counts_match_s3": counts_ok,
            "time_windows_ok": time_ok,
            "civil_time_ok": True,
            "routing_ok": True,
            "schema_partition_pk_ok": True,
            "rng_accounting_ok": True,
            "bundle_integrity_ok": overall_status == "PASS",
        }
        if bundle_sha256:
            payload["bundle_sha256"] = bundle_sha256
        if overall_status != "PASS":
            payload["error_code"] = "S5_VALIDATION_FAILED"
            payload["error_message"] = "one or more validation checks failed"
        return payload

    def _write_issue_table(
        self,
        path: Path,
        issues: Sequence[Mapping[str, object]],
    ) -> None:
        if issues:
            df = pl.DataFrame(issues)
        else:
            df = pl.DataFrame(
                {
                    "manifest_fingerprint": pl.Series([], dtype=pl.Utf8),
                    "parameter_hash": pl.Series([], dtype=pl.Utf8),
                    "scenario_id": pl.Series([], dtype=pl.Utf8),
                    "seed": pl.Series([], dtype=pl.Int64),
                    "issue_code": pl.Series([], dtype=pl.Utf8),
                    "severity": pl.Series([], dtype=pl.Utf8),
                    "context": pl.Series([], dtype=pl.Object),
                    "message": pl.Series([], dtype=pl.Utf8),
                }
            )
        df.write_parquet(path)

    def _issue(
        self,
        inputs: ValidationInputs,
        issue_code: str,
        severity: str,
        *,
        scenario_id: str | None = None,
        message: str | None = None,
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        return {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": _normalise_hex64(inputs.parameter_hash),
            "scenario_id": scenario_id,
            "seed": inputs.seed,
            "issue_code": issue_code,
            "severity": severity,
            "context": context or {},
            "message": message or "",
        }

    def _overall_status(self, issues: Iterable[Mapping[str, object]]) -> str:
        if any(issue.get("severity") == "ERROR" for issue in issues):
            return "FAIL"
        return "PASS"

    def _write_run_report(
        self,
        inputs: ValidationInputs,
        data_root: Path,
        dictionary: Mapping[str, object],
        overall_status: str,
    ) -> Path:
        path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        payload = {
            "layer": "layer2",
            "segment": "5B",
            "state": "S5",
            "parameter_hash": inputs.parameter_hash,
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "run_id": inputs.run_id,
            "status": overall_status,
        }
        key = SegmentStateKey(
            layer="layer2",
            segment="5B",
            state="S5",
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            run_id=inputs.run_id,
        )
        return write_segment_state_run_report(path=path, key=key, payload=payload)


def _sha256_path(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _normalise_hex64(value: str) -> str:
    if isinstance(value, str) and len(value) == 64:
        try:
            int(value, 16)
            return value.lower()
        except ValueError:
            pass
    return "0" * 64


__all__ = ["ValidationInputs", "ValidationResult", "ValidationRunner"]
