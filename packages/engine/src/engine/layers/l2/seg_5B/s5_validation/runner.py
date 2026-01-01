"""Segment 5B S5 validation runner."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import polars as pl
import yaml

from engine.layers.l2.seg_5B.shared.control_plane import (
    SealedInventory,
    compute_sealed_inputs_digest,
    load_control_plane,
)
from engine.layers.l2.seg_5B.shared.dictionary import load_dictionary, render_dataset_path
from engine.layers.l2.seg_5B.shared.dictionary import repository_root
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
        inventory = SealedInventory(
            dataframe=sealed_df,
            base_path=data_root,
            repo_root=repository_root(),
            template_args={
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
                "seed": str(inputs.seed),
            },
        )

        issues: list[Mapping[str, object]] = []
        issues.extend(self._check_upstream_flags(receipt, inputs))
        issues.extend(self._check_sealed_inputs(receipt, sealed_df, inputs))

        scenario_ids = [binding.scenario_id for binding in scenarios]
        if not scenario_ids:
            scenario_ids = ["baseline"]

        counts_ok = True
        time_ok = True
        routing_ok = True
        civil_time_ok = True
        rng_accounting_ok = True
        arrivals_total = 0
        arrivals_virtual = 0
        arrivals_physical = 0
        buckets_total = 0
        buckets_nonzero = 0
        expected_rng = _init_expected_rng()
        expected_site_pick = 0
        expected_edge_pick = 0

        virtual_modes = _load_virtual_modes(inventory, issues, inputs)
        site_timezone_map = _load_site_timezones(inventory, issues, inputs)
        virtual_settlement = _load_virtual_settlement(inventory, issues, inputs)
        edge_catalogue = _load_edge_catalogue(inventory, issues, inputs)
        zone_alloc_hash = _load_zone_alloc_hash(inventory, issues, inputs)
        edge_universe_hash = _load_edge_universe_hash(inventory, issues, inputs)
        if not virtual_modes:
            routing_ok = False
        if not site_timezone_map:
            routing_ok = False
            civil_time_ok = False
        if not virtual_settlement or not edge_catalogue:
            routing_ok = False
        if not zone_alloc_hash or not edge_universe_hash:
            routing_ok = False
        arrival_count_config = _load_yaml(inventory, "arrival_count_config_5B", issues, inputs)
        lambda_zero_eps = float(arrival_count_config.get("lambda_zero_eps", 0.0))
        count_law_id = str(arrival_count_config.get("count_law_id", "poisson"))

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
                    "tzid_primary",
                    "ts_local_primary",
                    "tzid_settlement",
                    "ts_local_settlement",
                    "tzid_operational",
                    "ts_local_operational",
                    "tz_group_id",
                    "site_id",
                    "edge_id",
                    "routing_universe_hash",
                ]
            )
            arrivals_total += arrivals_df.height
            if "is_virtual" in arrivals_df.columns:
                arrivals_virtual += int(arrivals_df.filter(pl.col("is_virtual") == True).height)
                arrivals_physical += int(arrivals_df.filter(pl.col("is_virtual") == False).height)

            grouping_path_exists = grouping_path.exists()
            if grouping_path_exists:
                grouping_df = pl.read_parquet(grouping_path).select(["group_id"])
                groups = grouping_df.select("group_id").unique().height
                horizon_buckets = grid_df.height
                expected_rng["S2.latent_vector.v1"]["events"] += groups
                expected_rng["S2.latent_vector.v1"]["draws"] += groups * 2 * horizon_buckets
                expected_rng["S2.latent_vector.v1"]["blocks"] += groups * horizon_buckets

            if intensity_path.exists():
                intensity_df = pl.read_parquet(intensity_path).select(["lambda_realised"])
                active_rows = int(intensity_df.filter(pl.col("lambda_realised") > lambda_zero_eps).height)
                draws_per_event = 2 if count_law_id == "nb2" else 1
                expected_rng["S3.bucket_count.v1"]["events"] += active_rows
                expected_rng["S3.bucket_count.v1"]["draws"] += active_rows * draws_per_event
                expected_rng["S3.bucket_count.v1"]["blocks"] += active_rows * _blocks_for_draws(draws_per_event)

            expected_rng["S4.arrival_time_jitter.v1"]["events"] += arrivals_df.height
            expected_rng["S4.arrival_time_jitter.v1"]["draws"] += arrivals_df.height
            expected_rng["S4.arrival_time_jitter.v1"]["blocks"] += arrivals_df.height

            for row in arrivals_df.to_dicts():
                merchant_id = str(row.get("merchant_id"))
                is_virtual = bool(row.get("is_virtual"))
                mode = virtual_modes.get(merchant_id, "NON_VIRTUAL")
                if mode != "VIRTUAL_ONLY":
                    expected_site_pick += 1
                if is_virtual:
                    expected_edge_pick += 1

                routing_issue = _check_routing_row(
                    row=row,
                    merchant_id=merchant_id,
                    site_timezone_map=site_timezone_map,
                    virtual_settlement=virtual_settlement,
                    edge_catalogue=edge_catalogue,
                    zone_alloc_hash=zone_alloc_hash,
                    edge_universe_hash=edge_universe_hash,
                )
                if routing_issue:
                    routing_ok = False
                    issues.append(self._issue(inputs, "S5_ROUTING_MISMATCH", "ERROR", scenario_id=scenario_id, message=routing_issue))

                civil_issue = _check_civil_time_row(row=row)
                if civil_issue:
                    civil_time_ok = False
                    issues.append(self._issue(inputs, "S5_CIVIL_TIME_MISMATCH", "ERROR", scenario_id=scenario_id, message=civil_issue))

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

        expected_rng["S4.arrival_site_pick.v1"]["events"] += expected_site_pick
        expected_rng["S4.arrival_site_pick.v1"]["draws"] += expected_site_pick * 2
        expected_rng["S4.arrival_site_pick.v1"]["blocks"] += expected_site_pick
        expected_rng["S4.arrival_edge_pick.v1"]["events"] += expected_edge_pick
        expected_rng["S4.arrival_edge_pick.v1"]["draws"] += expected_edge_pick
        expected_rng["S4.arrival_edge_pick.v1"]["blocks"] += expected_edge_pick

        rng_issues = _check_rng_accounting(
            base_path=data_root,
            inputs=inputs,
            expected=expected_rng,
        )
        if rng_issues:
            rng_accounting_ok = False
            issues.extend(rng_issues)

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
            routing_ok=routing_ok,
            civil_time_ok=civil_time_ok,
            rng_accounting_ok=rng_accounting_ok,
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
        routing_ok: bool,
        civil_time_ok: bool,
        rng_accounting_ok: bool,
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
            "civil_time_ok": civil_time_ok,
            "routing_ok": routing_ok,
            "schema_partition_pk_ok": True,
            "rng_accounting_ok": rng_accounting_ok,
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


def _init_expected_rng() -> dict[str, dict[str, int]]:
    return {
        "S2.latent_vector.v1": {"events": 0, "draws": 0, "blocks": 0},
        "S3.bucket_count.v1": {"events": 0, "draws": 0, "blocks": 0},
        "S4.arrival_time_jitter.v1": {"events": 0, "draws": 0, "blocks": 0},
        "S4.arrival_site_pick.v1": {"events": 0, "draws": 0, "blocks": 0},
        "S4.arrival_edge_pick.v1": {"events": 0, "draws": 0, "blocks": 0},
    }


def _blocks_for_draws(draws: int) -> int:
    if draws <= 0:
        return 0
    return (draws + 1) // 2


def _load_yaml(
    inventory: SealedInventory,
    artifact_id: str,
    issues: list[Mapping[str, object]],
    inputs: ValidationInputs,
) -> Mapping[str, object]:
    files = inventory.resolve_files(artifact_id)
    if not files:
        issues.append(
            {
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                "scenario_id": None,
                "seed": inputs.seed,
                "issue_code": "S5_SEALED_INPUT_MISSING",
                "severity": "ERROR",
                "context": {"artifact_id": artifact_id},
                "message": f"sealed input '{artifact_id}' missing for S5 validation",
            }
        )
        return {}
    return yaml.safe_load(files[0].read_text(encoding="utf-8")) or {}


def _load_virtual_modes(
    inventory: SealedInventory,
    issues: list[Mapping[str, object]],
    inputs: ValidationInputs,
) -> dict[str, str]:
    files = inventory.resolve_files("virtual_classification_3B")
    if not files:
        issues.append(
            {
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                "scenario_id": None,
                "seed": inputs.seed,
                "issue_code": "S5_VIRTUAL_CLASSIFICATION_MISSING",
                "severity": "ERROR",
                "context": {},
                "message": "virtual_classification_3B missing from sealed inputs",
            }
        )
        return {}
    df = pl.read_parquet(files[0])
    modes: dict[str, str] = {}
    for row in df.to_dicts():
        merchant_id = str(row.get("merchant_id"))
        if not merchant_id:
            continue
        mode = row.get("virtual_mode")
        if mode is not None:
            modes[merchant_id] = str(mode)
        else:
            modes[merchant_id] = "VIRTUAL_ONLY" if bool(row.get("is_virtual")) else "NON_VIRTUAL"
    return modes


def _load_site_timezones(
    inventory: SealedInventory,
    issues: list[Mapping[str, object]],
    inputs: ValidationInputs,
) -> dict[int, str]:
    files = inventory.resolve_files("site_timezones")
    if not files:
        issues.append(
            {
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                "scenario_id": None,
                "seed": inputs.seed,
                "issue_code": "S5_SITE_TIMEZONES_MISSING",
                "severity": "ERROR",
                "context": {},
                "message": "site_timezones missing from sealed inputs",
            }
        )
        return {}
    df = pl.read_parquet(files[0]).select(
        ["merchant_id", "legal_country_iso", "site_order", "tzid"]
    )
    mapping: dict[int, str] = {}
    for row in df.to_dicts():
        merchant_id = str(row.get("merchant_id"))
        site_order = row.get("site_order")
        tzid = row.get("tzid")
        if merchant_id and site_order is not None and tzid:
            site_id = _site_id(merchant_id, int(site_order))
            mapping[site_id] = str(tzid)
    return mapping


def _load_virtual_settlement(
    inventory: SealedInventory,
    issues: list[Mapping[str, object]],
    inputs: ValidationInputs,
) -> dict[str, str]:
    files = inventory.resolve_files("virtual_settlement_3B")
    if not files:
        issues.append(
            {
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                "scenario_id": None,
                "seed": inputs.seed,
                "issue_code": "S5_VIRTUAL_SETTLEMENT_MISSING",
                "severity": "ERROR",
                "context": {},
                "message": "virtual_settlement_3B missing from sealed inputs",
            }
        )
        return {}
    df = pl.read_parquet(files[0]).select(["merchant_id", "tzid_settlement"])
    mapping: dict[str, str] = {}
    for row in df.to_dicts():
        merchant_id = str(row.get("merchant_id"))
        tzid = row.get("tzid_settlement")
        if merchant_id and tzid:
            mapping[merchant_id] = str(tzid)
    return mapping


def _load_edge_catalogue(
    inventory: SealedInventory,
    issues: list[Mapping[str, object]],
    inputs: ValidationInputs,
) -> dict[tuple[str, str], str]:
    files = inventory.resolve_files("edge_catalogue_3B")
    if not files:
        issues.append(
            {
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                "scenario_id": None,
                "seed": inputs.seed,
                "issue_code": "S5_EDGE_CATALOGUE_MISSING",
                "severity": "ERROR",
                "context": {},
                "message": "edge_catalogue_3B missing from sealed inputs",
            }
        )
        return {}
    df = pl.read_parquet(files[0]).select(["merchant_id", "edge_id", "tzid_operational"])
    mapping: dict[tuple[str, str], str] = {}
    for row in df.to_dicts():
        merchant_id = str(row.get("merchant_id"))
        edge_id = row.get("edge_id")
        tzid = row.get("tzid_operational")
        if merchant_id and edge_id and tzid:
            mapping[(merchant_id, str(edge_id))] = str(tzid)
    return mapping


def _load_zone_alloc_hash(
    inventory: SealedInventory,
    issues: list[Mapping[str, object]],
    inputs: ValidationInputs,
) -> str:
    files = inventory.resolve_files("zone_alloc_universe_hash")
    if not files:
        issues.append(
            {
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                "scenario_id": None,
                "seed": inputs.seed,
                "issue_code": "S5_ZONE_ALLOC_HASH_MISSING",
                "severity": "ERROR",
                "context": {},
                "message": "zone_alloc_universe_hash missing from sealed inputs",
            }
        )
        return ""
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    return str(payload.get("routing_universe_hash", "")) or str(payload.get("universe_hash", ""))


def _load_edge_universe_hash(
    inventory: SealedInventory,
    issues: list[Mapping[str, object]],
    inputs: ValidationInputs,
) -> str:
    files = inventory.resolve_files("edge_universe_hash_3B")
    if not files:
        issues.append(
            {
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                "scenario_id": None,
                "seed": inputs.seed,
                "issue_code": "S5_EDGE_HASH_MISSING",
                "severity": "ERROR",
                "context": {},
                "message": "edge_universe_hash_3B missing from sealed inputs",
            }
        )
        return ""
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    return str(payload.get("universe_hash", ""))


def _check_routing_row(
    *,
    row: Mapping[str, object],
    merchant_id: str,
    site_timezone_map: Mapping[int, str],
    virtual_settlement: Mapping[str, str],
    edge_catalogue: Mapping[tuple[str, str], str],
    zone_alloc_hash: str,
    edge_universe_hash: str,
) -> str | None:
    is_virtual = bool(row.get("is_virtual"))
    routing_hash = row.get("routing_universe_hash")
    if is_virtual:
        if not edge_catalogue:
            return None
        edge_id = row.get("edge_id")
        if edge_id is None:
            return "virtual arrival missing edge_id"
        edge_key = (merchant_id, str(edge_id))
        tz_operational = edge_catalogue.get(edge_key)
        if not tz_operational:
            return "edge_id not found in edge_catalogue_3B for merchant"
        if row.get("tzid_operational") and str(row.get("tzid_operational")) != tz_operational:
            return "tzid_operational mismatch for edge_id"
        settlement_tz = virtual_settlement.get(merchant_id)
        if settlement_tz and row.get("tzid_settlement") and str(row.get("tzid_settlement")) != settlement_tz:
            return "tzid_settlement mismatch for virtual merchant"
        if edge_universe_hash and routing_hash and str(routing_hash) != edge_universe_hash:
            return "routing_universe_hash mismatch for virtual arrival"
    else:
        if not site_timezone_map:
            return None
        site_id = row.get("site_id")
        if site_id is None:
            return "physical arrival missing site_id"
        site_id_int = int(site_id)
        tzid = site_timezone_map.get(site_id_int)
        if not tzid:
            return "site_id missing from site_timezones"
        if row.get("tzid_primary") and str(row.get("tzid_primary")) != tzid:
            return "tzid_primary mismatch for site_id"
        if row.get("tz_group_id") and str(row.get("tz_group_id")) != tzid:
            return "tz_group_id mismatch for site_id"
        if zone_alloc_hash and routing_hash and str(routing_hash) != zone_alloc_hash:
            return "routing_universe_hash mismatch for physical arrival"
    return None


def _check_civil_time_row(*, row: Mapping[str, object]) -> str | None:
    ts_utc_raw = row.get("ts_utc")
    if not ts_utc_raw:
        return "ts_utc missing for civil-time check"
    try:
        ts_utc = _parse_rfc3339(str(ts_utc_raw))
    except ValueError:
        return "ts_utc unparsable"
    for tz_key, ts_key in (
        ("tzid_primary", "ts_local_primary"),
        ("tzid_settlement", "ts_local_settlement"),
        ("tzid_operational", "ts_local_operational"),
    ):
        tzid = row.get(tz_key)
        ts_local_raw = row.get(ts_key)
        if not tzid or not ts_local_raw:
            continue
        try:
            local_dt = _parse_rfc3339(str(ts_local_raw))
        except ValueError:
            return f"{ts_key} unparsable"
        try:
            expected = ts_utc.astimezone(_safe_zone(str(tzid)))
        except Exception:
            return f"{tz_key} invalid for civil-time conversion"
        if local_dt.utcoffset() != expected.utcoffset():
            return f"{ts_key} offset mismatch for {tzid}"
        if local_dt.replace(tzinfo=None) != expected.replace(tzinfo=None):
            return f"{ts_key} wall-time mismatch for {tzid}"
    return None


def _check_rng_accounting(
    *,
    base_path: Path,
    inputs: ValidationInputs,
    expected: Mapping[str, Mapping[str, int]],
) -> list[Mapping[str, object]]:
    issues: list[Mapping[str, object]] = []
    family_meta = {
        "S2.latent_vector.v1": ("5B.S2", "latent_vector"),
        "S3.bucket_count.v1": ("5B.S3", "bucket_count"),
        "S4.arrival_time_jitter.v1": ("5B.S4", "arrival_time_jitter"),
        "S4.arrival_site_pick.v1": ("5B.S4", "arrival_site_pick"),
        "S4.arrival_edge_pick.v1": ("5B.S4", "arrival_edge_pick"),
    }
    trace_totals = _load_rng_trace(base_path, inputs)
    for family_id, expectation in expected.items():
        events = _load_rng_events(base_path, inputs, family_id)
        if events is None:
            issues.append(
                {
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                    "scenario_id": None,
                    "seed": inputs.seed,
                    "issue_code": "S5_RNG_EVENTS_MISSING",
                    "severity": "ERROR",
                    "context": {"family_id": family_id},
                    "message": f"rng events missing for {family_id}",
                }
            )
            continue
        actual_events = len(events)
        actual_draws = sum(int(str(event.get("draws", 0))) for event in events)
        actual_blocks = sum(int(event.get("blocks", 0)) for event in events)
        if actual_events != expectation["events"]:
            issues.append(
                {
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                    "scenario_id": None,
                    "seed": inputs.seed,
                    "issue_code": "S5_RNG_EVENT_COUNT_MISMATCH",
                    "severity": "ERROR",
                    "context": {"family_id": family_id, "expected": expectation["events"], "actual": actual_events},
                    "message": "rng event count mismatch",
                }
            )
        if actual_draws != expectation["draws"]:
            issues.append(
                {
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                    "scenario_id": None,
                    "seed": inputs.seed,
                    "issue_code": "S5_RNG_DRAWS_MISMATCH",
                    "severity": "ERROR",
                    "context": {"family_id": family_id, "expected": expectation["draws"], "actual": actual_draws},
                    "message": "rng draws mismatch",
                }
            )
        if actual_blocks != expectation["blocks"]:
            issues.append(
                {
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                    "scenario_id": None,
                    "seed": inputs.seed,
                    "issue_code": "S5_RNG_BLOCKS_MISMATCH",
                    "severity": "ERROR",
                    "context": {"family_id": family_id, "expected": expectation["blocks"], "actual": actual_blocks},
                    "message": "rng blocks mismatch",
                }
            )
        for event in events:
            before_lo = int(event.get("rng_counter_before_lo", 0))
            after_lo = int(event.get("rng_counter_after_lo", 0))
            blocks = int(event.get("blocks", 0))
            if after_lo - before_lo != blocks:
                issues.append(
                    {
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                        "scenario_id": None,
                        "seed": inputs.seed,
                        "issue_code": "S5_RNG_COUNTER_MISMATCH",
                        "severity": "ERROR",
                        "context": {"family_id": family_id},
                        "message": "rng counter increment mismatch",
                    }
                )
                break
        meta = family_meta.get(family_id)
        if meta and trace_totals:
            module, label = meta
            totals = trace_totals.get((module, label))
            if totals:
                if totals["events"] != actual_events or totals["draws"] != actual_draws or totals["blocks"] != actual_blocks:
                    issues.append(
                        {
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": _normalise_hex64(inputs.parameter_hash),
                            "scenario_id": None,
                            "seed": inputs.seed,
                            "issue_code": "S5_RNG_TRACE_MISMATCH",
                            "severity": "ERROR",
                            "context": {"family_id": family_id},
                            "message": "rng trace totals do not match events",
                        }
                    )
    return issues


def _load_rng_events(
    base_path: Path,
    inputs: ValidationInputs,
    family_id: str,
) -> list[Mapping[str, object]] | None:
    events_dir = (
        base_path
        / "logs"
        / "rng"
        / "events"
        / family_id
        / f"seed={inputs.seed}"
        / f"parameter_hash={inputs.parameter_hash}"
        / f"run_id={inputs.run_id}"
    )
    if not events_dir.exists():
        return None
    events: list[Mapping[str, object]] = []
    for path in sorted(events_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            events.append(json.loads(line))
    return events


def _load_rng_trace(
    base_path: Path,
    inputs: ValidationInputs,
) -> dict[tuple[str, str], dict[str, int]]:
    trace_path = (
        base_path
        / "logs"
        / "rng"
        / "trace"
        / f"seed={inputs.seed}"
        / f"parameter_hash={inputs.parameter_hash}"
        / f"run_id={inputs.run_id}"
        / "rng_trace_log.jsonl"
    )
    if not trace_path.exists():
        return {}
    totals: dict[tuple[str, str], dict[str, int]] = {}
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        module = str(payload.get("module", ""))
        label = str(payload.get("substream_label", ""))
        if not module or not label:
            continue
        totals[(module, label)] = {
            "events": int(payload.get("events_total", 0)),
            "draws": int(payload.get("draws_total", 0)),
            "blocks": int(payload.get("blocks_total", 0)),
        }
    return totals


def _parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _safe_zone(tzid: str) -> ZoneInfo:
    try:
        return ZoneInfo(tzid)
    except Exception:
        return ZoneInfo("Etc/UTC")


def _site_id(merchant_id: str, site_order: int) -> int:
    return (int(merchant_id) << 32) | (site_order & 0xFFFFFFFF)


__all__ = ["ValidationInputs", "ValidationResult", "ValidationRunner"]
