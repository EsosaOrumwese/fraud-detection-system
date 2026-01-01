"""Segment 3A S6 runner - structural validation and receipts."""

from __future__ import annotations

import json
import re
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
_UNIVERSE_SCHEMA = Draft202012Validator(load_schema("#/validation/zone_alloc_universe_hash"))
_SEALED_INPUT_SCHEMA = Draft202012Validator(load_schema("#/validation/sealed_inputs_3A"))


@dataclass(frozen=True)
class ValidationInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str = "00000000000000000000000000000000"
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ValidationResult:
    report_path: Path
    issues_path: Path
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
        run_id = inputs.run_id
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise err("E_RUN_ID", "run_id must be 32 lowercase hex characters")

        precondition_issues: list[Mapping[str, Any]] = []

        s0_receipt = self._load_s0_receipt(
            base=data_root,
            manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
            issues=precondition_issues,
        )
        if s0_receipt and str(s0_receipt.get("parameter_hash")) != str(parameter_hash):
            precondition_issues.append(
                {
                    "issue_code": "PRECONDITION_PARAM_HASH",
                    "check_id": "s0_receipt",
                    "severity": "ERROR",
                    "message": "parameter_hash mismatch between inputs and S0 receipt",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )

        sealed_inputs = self._load_sealed_inputs(
            base=data_root,
            manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
            issues=precondition_issues,
        )
        s1_df = self._load_required_table(
            dataset_id="s1_escalation_queue",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            base=data_root,
            dictionary=dictionary,
            issues=precondition_issues,
        )
        s2_df = self._load_required_table(
            dataset_id="s2_country_zone_priors",
            template_args={"parameter_hash": parameter_hash},
            base=data_root,
            dictionary=dictionary,
            issues=precondition_issues,
        )
        s3_df = self._load_required_table(
            dataset_id="s3_zone_shares",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            base=data_root,
            dictionary=dictionary,
            issues=precondition_issues,
        )
        s4_df = self._load_required_table(
            dataset_id="s4_zone_counts",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            base=data_root,
            dictionary=dictionary,
            issues=precondition_issues,
        )
        zone_alloc_df = self._load_required_table(
            dataset_id="zone_alloc",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            base=data_root,
            dictionary=dictionary,
            issues=precondition_issues,
        )
        universe_payload = self._load_required_json(
            dataset_id="zone_alloc_universe_hash",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            base=data_root,
            dictionary=dictionary,
            issues=precondition_issues,
        )

        issues: list[Mapping[str, Any]] = list(precondition_issues)
        if not precondition_issues:
            issues.extend(
                self._run_checks(
                    manifest_fingerprint=manifest_fingerprint,
                    parameter_hash=parameter_hash,
                    seed=seed,
                    run_id=run_id,
                    sealed_inputs=sealed_inputs,
                    s1_df=s1_df,
                    s2_df=s2_df,
                    s3_df=s3_df,
                    s4_df=s4_df,
                    zone_alloc_df=zone_alloc_df,
                    universe_payload=universe_payload,
                    data_root=data_root,
                )
            )

        overall_status = "PASS" if not issues else "FAIL"

        report_path = data_root / render_dataset_path(
            dataset_id="s6_validation_report_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        issues_path = data_root / render_dataset_path(
            dataset_id="s6_issue_table_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        issues_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path = data_root / render_dataset_path(
            dataset_id="s6_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True)

        report_payload = self._write_validation_report(
            path=report_path,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            overall_status=overall_status,
            issues=issues,
        )

        self._write_issue_table(issues_path, manifest_fingerprint, issues)

        self._write_receipt(
            path=receipt_path,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            report_path=report_path,
            issues_path=issues_path,
            overall_status=overall_status,
        )

        run_report_path = data_root / render_dataset_path(
            dataset_id="s6_run_report_3A",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
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
                "output_path": str(report_path),
                "run_report_path": str(run_report_path),
                "resumed": False,
            },
        )

        return ValidationResult(
            report_path=report_path,
            issues_path=issues_path,
            receipt_path=receipt_path,
            run_report_path=run_report_path,
            resumed=False,
        )

    # -------------------------------------------------------------- helpers
    def _load_s0_receipt(
        self,
        *,
        base: Path,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
        issues: list[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        receipt_path = base / render_dataset_path(
            dataset_id="s0_gate_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not receipt_path.exists():
            issues.append(
                {
                    "issue_code": "PRECONDITION_S0_RECEIPT_MISSING",
                    "check_id": "s0_receipt",
                    "severity": "ERROR",
                    "message": f"S0 receipt missing at '{receipt_path}'",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return {}
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        try:
            _S0_RECEIPT_SCHEMA.validate(payload)
        except ValidationError as exc:
            issues.append(
                {
                    "issue_code": "PRECONDITION_S0_RECEIPT_SCHEMA",
                    "check_id": "s0_receipt",
                    "severity": "ERROR",
                    "message": f"s0 receipt invalid: {exc.message}",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return {}
        return payload

    def _load_sealed_inputs(
        self,
        *,
        base: Path,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
        issues: list[Mapping[str, Any]],
    ) -> pl.DataFrame:
        sealed_path = base / render_dataset_path(
            dataset_id="sealed_inputs_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not sealed_path.exists():
            issues.append(
                {
                    "issue_code": "PRECONDITION_SEALED_INPUTS_MISSING",
                    "check_id": "sealed_inputs",
                    "severity": "ERROR",
                    "message": f"sealed_inputs_3A missing at '{sealed_path}'",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return pl.DataFrame()
        df = pl.read_parquet(sealed_path)
        for row in df.to_dicts():
            try:
                _SEALED_INPUT_SCHEMA.validate(row)
            except ValidationError as exc:
                issues.append(
                    {
                        "issue_code": "PRECONDITION_SEALED_INPUTS_SCHEMA",
                        "check_id": "sealed_inputs",
                        "severity": "ERROR",
                        "message": f"sealed_inputs row invalid: {exc.message}",
                        "merchant_id": None,
                        "legal_country_iso": None,
                        "tzid": None,
                    }
                )
                return pl.DataFrame()
        return df

    def _load_required_table(
        self,
        *,
        dataset_id: str,
        template_args: Mapping[str, Any],
        base: Path,
        dictionary: Mapping[str, object],
        issues: list[Mapping[str, Any]],
    ) -> pl.DataFrame:
        rel_path = render_dataset_path(dataset_id=dataset_id, template_args=template_args, dictionary=dictionary)
        path = base / rel_path
        if not path.exists():
            issues.append(
                {
                    "issue_code": "PRECONDITION_DATASET_MISSING",
                    "check_id": dataset_id,
                    "severity": "ERROR",
                    "message": f"missing dataset '{dataset_id}' at '{path}'",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return pl.DataFrame()
        try:
            return pl.read_parquet(path)
        except Exception as exc:
            issues.append(
                {
                    "issue_code": "PRECONDITION_DATASET_LOAD",
                    "check_id": dataset_id,
                    "severity": "ERROR",
                    "message": f"failed reading dataset '{dataset_id}': {exc}",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return pl.DataFrame()

    def _load_required_json(
        self,
        *,
        dataset_id: str,
        template_args: Mapping[str, Any],
        base: Path,
        dictionary: Mapping[str, object],
        issues: list[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        rel_path = render_dataset_path(dataset_id=dataset_id, template_args=template_args, dictionary=dictionary)
        path = base / rel_path
        if not path.exists():
            issues.append(
                {
                    "issue_code": "PRECONDITION_DATASET_MISSING",
                    "check_id": dataset_id,
                    "severity": "ERROR",
                    "message": f"missing dataset '{dataset_id}' at '{path}'",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(
                {
                    "issue_code": "PRECONDITION_DATASET_LOAD",
                    "check_id": dataset_id,
                    "severity": "ERROR",
                    "message": f"failed reading dataset '{dataset_id}': {exc}",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return {}

    def _run_checks(
        self,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        seed: int,
        run_id: str,
        sealed_inputs: pl.DataFrame,
        s1_df: pl.DataFrame,
        s2_df: pl.DataFrame,
        s3_df: pl.DataFrame,
        s4_df: pl.DataFrame,
        zone_alloc_df: pl.DataFrame,
        universe_payload: Mapping[str, Any],
        data_root: Path,
    ) -> list[Mapping[str, Any]]:
        issues: list[Mapping[str, Any]] = []

        for dataset_id, df, schema_ref in (
            ("s1_escalation_queue", s1_df, "#/plan/s1_escalation_queue"),
            ("s2_country_zone_priors", s2_df, "#/plan/s2_country_zone_priors"),
            ("s3_zone_shares", s3_df, "#/plan/s3_zone_shares"),
            ("s4_zone_counts", s4_df, "#/plan/s4_zone_counts"),
            ("zone_alloc", zone_alloc_df, "#/egress/zone_alloc"),
        ):
            try:
                _validate_table_rows(df, load_schema(schema_ref), error_prefix=dataset_id)
            except Exception as exc:
                issues.append(
                    {
                        "issue_code": "SCHEMA_VALIDATION",
                        "check_id": dataset_id,
                        "severity": "ERROR",
                        "message": str(exc),
                        "merchant_id": None,
                        "legal_country_iso": None,
                        "tzid": None,
                    }
                )

        for df_name, df in (
            ("s1_escalation_queue", s1_df),
            ("s3_zone_shares", s3_df),
            ("s4_zone_counts", s4_df),
            ("zone_alloc", zone_alloc_df),
        ):
            if df.is_empty() or "fingerprint" not in df.columns:
                continue
            mismatched = df.filter(pl.col("fingerprint") != manifest_fingerprint)
            if mismatched.height > 0:
                issues.append(
                    {
                        "issue_code": "FINGERPRINT_MISMATCH",
                        "check_id": df_name,
                        "severity": "ERROR",
                        "message": f"{df_name} contains rows with fingerprint != manifest_fingerprint",
                        "merchant_id": None,
                        "legal_country_iso": None,
                        "tzid": None,
                    }
                )

        try:
            _UNIVERSE_SCHEMA.validate(universe_payload)
        except ValidationError as exc:
            issues.append(
                {
                    "issue_code": "UNIVERSE_SCHEMA",
                    "check_id": "zone_alloc_universe_hash",
                    "severity": "ERROR",
                    "message": f"zone_alloc_universe_hash invalid: {exc.message}",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
        if universe_payload:
            if str(universe_payload.get("manifest_fingerprint")) != str(manifest_fingerprint):
                issues.append(
                    {
                        "issue_code": "UNIVERSE_FINGERPRINT",
                        "check_id": "zone_alloc_universe_hash",
                        "severity": "ERROR",
                        "message": "zone_alloc_universe_hash manifest_fingerprint mismatch",
                        "merchant_id": None,
                        "legal_country_iso": None,
                        "tzid": None,
                    }
                )
            if str(universe_payload.get("parameter_hash")) != str(parameter_hash):
                issues.append(
                    {
                        "issue_code": "UNIVERSE_PARAMETER_HASH",
                        "check_id": "zone_alloc_universe_hash",
                        "severity": "ERROR",
                        "message": "zone_alloc_universe_hash parameter_hash mismatch",
                        "merchant_id": None,
                        "legal_country_iso": None,
                        "tzid": None,
                    }
                )

        issues.extend(
            self._validate_rng_accounting(
                manifest_fingerprint=manifest_fingerprint,
                parameter_hash=parameter_hash,
                seed=seed,
                run_id=run_id,
                s3_df=s3_df,
                data_root=data_root,
            )
        )

        # count conservation per pair (zone_alloc)
        if not zone_alloc_df.is_empty() and {"merchant_id", "legal_country_iso", "zone_site_count", "site_count"}.issubset(
            set(zone_alloc_df.columns)
        ):
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

    def _validate_rng_accounting(
        self,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        seed: int,
        run_id: str,
        s3_df: pl.DataFrame,
        data_root: Path,
    ) -> list[Mapping[str, Any]]:
        issues: list[Mapping[str, Any]] = []
        if s3_df.is_empty():
            return issues

        events_path = (
            data_root
            / "logs"
            / "rng"
            / "events"
            / "zone_dirichlet_share"
            / f"seed={seed}"
            / f"parameter_hash={parameter_hash}"
            / f"run_id={run_id}"
            / "part-00000.jsonl"
        )
        trace_path = (
            data_root
            / "logs"
            / "rng"
            / "trace"
            / f"seed={seed}"
            / f"parameter_hash={parameter_hash}"
            / f"run_id={run_id}"
            / "rng_trace_log.jsonl"
        )
        if not events_path.exists():
            issues.append(
                {
                    "issue_code": "RNG_EVENTS_MISSING",
                    "check_id": "rng_events",
                    "severity": "ERROR",
                    "message": f"rng events missing at '{events_path}'",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return issues
        if not trace_path.exists():
            issues.append(
                {
                    "issue_code": "RNG_TRACE_MISSING",
                    "check_id": "rng_trace",
                    "severity": "ERROR",
                    "message": f"rng trace missing at '{trace_path}'",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return issues

        module_name = "3A.zone_shares"
        substream_label = "zone_dirichlet_share"

        events = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                issues.append(
                    {
                        "issue_code": "RNG_EVENT_PARSE",
                        "check_id": "rng_events",
                        "severity": "ERROR",
                        "message": f"invalid rng event JSON: {exc}",
                        "merchant_id": None,
                        "legal_country_iso": None,
                        "tzid": None,
                    }
                )
                return issues

        draws_total = 0
        blocks_total = 0
        event_count = 0
        for event in events:
            if event.get("module") != module_name or event.get("substream_label") != substream_label:
                continue
            if str(event.get("run_id")) != str(run_id):
                issues.append(
                    {
                        "issue_code": "RNG_EVENT_RUN_ID",
                        "check_id": "rng_events",
                        "severity": "ERROR",
                        "message": "rng event run_id mismatch",
                        "merchant_id": event.get("merchant_id"),
                        "legal_country_iso": event.get("country_iso"),
                        "tzid": event.get("tzid"),
                    }
                )
            if str(event.get("parameter_hash")) != str(parameter_hash):
                issues.append(
                    {
                        "issue_code": "RNG_EVENT_PARAMETER_HASH",
                        "check_id": "rng_events",
                        "severity": "ERROR",
                        "message": "rng event parameter_hash mismatch",
                        "merchant_id": event.get("merchant_id"),
                        "legal_country_iso": event.get("country_iso"),
                        "tzid": event.get("tzid"),
                    }
                )
            if str(event.get("manifest_fingerprint")) != str(manifest_fingerprint):
                issues.append(
                    {
                        "issue_code": "RNG_EVENT_MANIFEST",
                        "check_id": "rng_events",
                        "severity": "ERROR",
                        "message": "rng event manifest_fingerprint mismatch",
                        "merchant_id": event.get("merchant_id"),
                        "legal_country_iso": event.get("country_iso"),
                        "tzid": event.get("tzid"),
                    }
                )
            try:
                draws_total += int(str(event.get("draws", "0")))
            except Exception:
                issues.append(
                    {
                        "issue_code": "RNG_EVENT_DRAWS",
                        "check_id": "rng_events",
                        "severity": "ERROR",
                        "message": "rng event draws not parseable",
                        "merchant_id": event.get("merchant_id"),
                        "legal_country_iso": event.get("country_iso"),
                        "tzid": event.get("tzid"),
                    }
                )
            try:
                blocks_total += int(event.get("blocks", 0))
            except Exception:
                issues.append(
                    {
                        "issue_code": "RNG_EVENT_BLOCKS",
                        "check_id": "rng_events",
                        "severity": "ERROR",
                        "message": "rng event blocks not parseable",
                        "merchant_id": event.get("merchant_id"),
                        "legal_country_iso": event.get("country_iso"),
                        "tzid": event.get("tzid"),
                    }
                )
            event_count += 1

        if event_count != s3_df.height:
            issues.append(
                {
                    "issue_code": "RNG_EVENT_COUNT",
                    "check_id": "rng_events",
                    "severity": "ERROR",
                    "message": f"rng event count {event_count} != s3_zone_shares rows {s3_df.height}",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )

        trace_entries = []
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                trace_entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        trace_entries = [
            entry
            for entry in trace_entries
            if entry.get("module") == module_name and entry.get("substream_label") == substream_label
        ]
        if not trace_entries:
            issues.append(
                {
                    "issue_code": "RNG_TRACE_EMPTY",
                    "check_id": "rng_trace",
                    "severity": "ERROR",
                    "message": "rng_trace_log missing module/substream entries",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
            return issues
        trace_entries.sort(
            key=lambda e: (
                int(e.get("rng_counter_after_hi", 0)),
                int(e.get("rng_counter_after_lo", 0)),
                str(e.get("ts_utc", "")),
            )
        )
        trace = trace_entries[-1]
        if int(trace.get("draws_total", -1)) != draws_total:
            issues.append(
                {
                    "issue_code": "RNG_TRACE_DRAWS",
                    "check_id": "rng_trace",
                    "severity": "ERROR",
                    "message": "rng trace draws_total mismatch",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
        if int(trace.get("blocks_total", -1)) != blocks_total:
            issues.append(
                {
                    "issue_code": "RNG_TRACE_BLOCKS",
                    "check_id": "rng_trace",
                    "severity": "ERROR",
                    "message": "rng trace blocks_total mismatch",
                    "merchant_id": None,
                    "legal_country_iso": None,
                    "tzid": None,
                }
            )
        if int(trace.get("events_total", -1)) != event_count:
            issues.append(
                {
                    "issue_code": "RNG_TRACE_EVENTS",
                    "check_id": "rng_trace",
                    "severity": "ERROR",
                    "message": "rng trace events_total mismatch",
                    "merchant_id": None,
                    "legal_country_iso": None,
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
