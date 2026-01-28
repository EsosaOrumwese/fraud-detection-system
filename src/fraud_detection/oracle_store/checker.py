"""Oracle Store validation checks (engine-rooted)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.config import Config
import json
import yaml

from fraud_detection.ingestion_gate.catalogue import OutputCatalogue
from fraud_detection.scenario_runner.schemas import SchemaRegistry

from .config import OracleProfile
from .engine_reader import discover_scenario_ids, join_engine_path, read_run_receipt, resolve_engine_root
from .packer import OracleWorldKey


@dataclass
class OracleCheckReport:
    status: str
    reason_codes: list[str] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def ok(self) -> bool:
        return self.status in {"OK", "WARN"}

    def add_issue(self, code: str, *, detail: str | None = None, severity: str = "ERROR") -> None:
        if code not in self.reason_codes:
            self.reason_codes.append(code)
        payload = {"code": code, "severity": severity}
        if detail:
            payload["detail"] = detail
        self.issues.append(payload)
        if severity == "ERROR":
            self.errors.append(code if detail is None else f"{code}:{detail}")
        else:
            self.warnings.append(code if detail is None else f"{code}:{detail}")


class OracleStoreChecker:
    def __init__(self, profile: OracleProfile) -> None:
        self.profile = profile
        self.catalogue = OutputCatalogue(Path(profile.wiring.engine_catalogue_path))
        self.oracle_schema = SchemaRegistry(Path(profile.wiring.schema_root) / "oracle_store")
        self.gate_map = yaml.safe_load(Path(profile.wiring.gate_map_path).read_text(encoding="utf-8"))

    def check_engine_run(
        self,
        engine_run_root: str,
        *,
        scenario_id: str | None = None,
        strict_seal: bool = False,
        output_ids: list[str] | None = None,
    ) -> OracleCheckReport:
        report = OracleCheckReport(status="OK")
        resolved_root = resolve_engine_root(engine_run_root, self.profile.wiring.oracle_root)
        report.details["engine_run_root"] = resolved_root

        receipt = self._load_run_receipt(resolved_root, report)
        if receipt is None:
            report.status = "FAIL"
            return report

        scenario_value = self._resolve_scenario_id(resolved_root, scenario_id, report)
        if scenario_value is None:
            report.status = "FAIL"
            return report

        world_key = self._world_key_from_receipt(receipt, scenario_value, report)
        if world_key is None:
            report.status = "FAIL"
            return report

        tokens = {
            "manifest_fingerprint": world_key.manifest_fingerprint,
            "parameter_hash": world_key.parameter_hash,
            "scenario_id": world_key.scenario_id,
            "seed": world_key.seed,
            "run_id": str(receipt.get("run_id", "")),
        }
        report.details["world_key"] = world_key.as_dict()

        missing_gates = []
        if self.profile.policy.require_gate_pass:
            missing_gates = self._missing_gate_receipts(resolved_root, tokens, report)
            if missing_gates:
                report.add_issue(
                    "GATE_RECEIPT_MISSING",
                    detail=json.dumps(missing_gates, sort_keys=True),
                    severity="ERROR",
                )

        missing_outputs = 0
        if output_ids:
            missing_outputs = self._check_output_paths(resolved_root, tokens, output_ids, report)

        seal_missing, manifest_missing, manifest_invalid, manifests = self._check_pack_markers(resolved_root)
        if seal_missing:
            severity = "ERROR" if strict_seal else "WARN"
            report.add_issue("PACK_NOT_SEALED", detail=resolved_root, severity=severity)
        if manifest_missing:
            report.add_issue("PACK_MANIFEST_MISSING", detail=resolved_root, severity="WARN")
        if manifest_invalid:
            report.add_issue("PACK_MANIFEST_INVALID", detail=resolved_root, severity="ERROR")
        if strict_seal and seal_missing:
            report.status = "FAIL"
        if manifests:
            report.details["pack_manifests"] = manifests

        report.details["gates_missing"] = len(missing_gates)
        report.details["outputs_missing"] = missing_outputs

        if report.errors:
            report.status = "FAIL"
        elif report.warnings:
            report.status = "WARN"
        return report

    def _load_run_receipt(self, engine_root: str, report: OracleCheckReport) -> dict[str, Any] | None:
        try:
            return read_run_receipt(engine_root, self.profile)
        except Exception as exc:
            report.add_issue("RUN_RECEIPT_UNREADABLE", detail=str(exc), severity="ERROR")
            return None

    def _resolve_scenario_id(
        self,
        engine_root: str,
        scenario_id: str | None,
        report: OracleCheckReport,
    ) -> str | None:
        if scenario_id:
            return scenario_id
        candidates = discover_scenario_ids(engine_root)
        if len(candidates) == 1:
            return next(iter(candidates))
        if len(candidates) > 1:
            report.add_issue("SCENARIO_ID_AMBIGUOUS", detail=sorted(candidates).__repr__(), severity="ERROR")
            return None
        report.add_issue("SCENARIO_ID_MISSING", detail=engine_root, severity="ERROR")
        return None

    def _world_key_from_receipt(
        self, receipt: dict[str, Any], scenario_id: str, report: OracleCheckReport
    ) -> OracleWorldKey | None:
        try:
            return OracleWorldKey(
                manifest_fingerprint=receipt["manifest_fingerprint"],
                parameter_hash=receipt["parameter_hash"],
                scenario_id=scenario_id,
                seed=int(receipt["seed"]),
            )
        except Exception as exc:
            report.add_issue("RUN_RECEIPT_INVALID", detail=str(exc), severity="ERROR")
            return None

    def _missing_gate_receipts(
        self, engine_root: str, tokens: dict[str, Any], report: OracleCheckReport
    ) -> list[dict[str, str]]:
        missing: list[dict[str, str]] = []
        for gate in self.gate_map.get("gates", []):
            gate_id = gate.get("gate_id", "unknown")
            template = gate.get("passed_flag_path_template")
            if not template:
                continue
            relative = _render_path_template(template, tokens, report, gate_id)
            if not relative:
                continue
            candidate = join_engine_path(engine_root, relative)
            if not _path_exists(
                candidate,
                endpoint=self.profile.wiring.object_store_endpoint,
                region=self.profile.wiring.object_store_region,
                path_style=self.profile.wiring.object_store_path_style,
            ):
                missing.append({"gate_id": gate_id, "path": candidate})
        return missing

    def _check_output_paths(
        self,
        engine_root: str,
        tokens: dict[str, Any],
        output_ids: list[str],
        report: OracleCheckReport,
    ) -> int:
        missing = 0
        for output_id in output_ids:
            try:
                entry = self.catalogue.get(output_id)
            except KeyError:
                report.add_issue("OUTPUT_UNKNOWN", detail=output_id, severity="ERROR")
                missing += 1
                continue
            if not entry.path_template:
                report.add_issue("OUTPUT_TEMPLATE_MISSING", detail=output_id, severity="ERROR")
                missing += 1
                continue
            relative = _render_path_template(entry.path_template, tokens, report, output_id)
            if not relative:
                missing += 1
                continue
            candidate = join_engine_path(engine_root, relative)
            if not _path_exists(
                candidate,
                endpoint=self.profile.wiring.object_store_endpoint,
                region=self.profile.wiring.object_store_region,
                path_style=self.profile.wiring.object_store_path_style,
            ):
                missing += 1
                report.add_issue("OUTPUT_MISSING", detail=candidate, severity="ERROR")
        return missing

    def _check_pack_markers(
        self, engine_root: str
    ) -> tuple[bool, bool, bool, list[dict[str, Any]]]:
        manifests: list[dict[str, Any]] = []
        seal_paths = [
            join_engine_path(engine_root, "_SEALED.flag"),
            join_engine_path(engine_root, "_SEALED.json"),
        ]
        manifest_path = join_engine_path(engine_root, "_oracle_pack_manifest.json")
        seal_missing = not any(
            _path_exists(
                path,
                endpoint=self.profile.wiring.object_store_endpoint,
                region=self.profile.wiring.object_store_region,
                path_style=self.profile.wiring.object_store_path_style,
            )
            for path in seal_paths
        )
        manifest_missing = not _path_exists(
            manifest_path,
            endpoint=self.profile.wiring.object_store_endpoint,
            region=self.profile.wiring.object_store_region,
            path_style=self.profile.wiring.object_store_path_style,
        )
        manifest_invalid = False
        if not manifest_missing and not manifest_path.startswith("s3://"):
            try:
                manifest_payload = _read_json(Path(manifest_path))
                try:
                    self.oracle_schema.validate("oracle_pack_manifest.schema.yaml", manifest_payload)
                except Exception:
                    manifest_invalid = True
                    manifests.append({"pack_root": engine_root, "manifest": None})
                else:
                    manifests.append({"pack_root": engine_root, "manifest": manifest_payload})
            except Exception:
                manifests.append({"pack_root": engine_root, "manifest": None})
        return seal_missing, manifest_missing, manifest_invalid, manifests


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _render_path_template(
    template: str, tokens: dict[str, Any], report: OracleCheckReport, label: str
) -> str | None:
    try:
        return template.format(**tokens)
    except KeyError as exc:
        report.add_issue("TEMPLATE_TOKEN_MISSING", detail=f"{label}:{exc}", severity="ERROR")
        return None


def _resolve_oracle_path(path: str, oracle_root: str) -> str:
    if not path:
        return path
    if path.startswith("s3://"):
        return path
    normalized = path.replace("\\", "/")
    oracle_norm = oracle_root.replace("\\", "/").rstrip("/")
    if oracle_norm and normalized.startswith(oracle_norm):
        return path
    if Path(path).is_absolute():
        return path
    if oracle_root.startswith("s3://"):
        return f"{oracle_root.rstrip('/')}/{normalized.lstrip('/')}"
    return str(Path(oracle_root) / Path(path))


def _pack_root_from_locator(path: str, oracle_root: str) -> str | None:
    if not path or path.startswith("s3://"):
        return None
    oracle_path = Path(oracle_root)
    locator_path = Path(path)
    try:
        rel = locator_path.resolve().relative_to(oracle_path.resolve())
    except Exception:
        return None
    parts = rel.parts
    if not parts:
        return str(oracle_path)
    if parts[0] in {"data", "config", "reports"}:
        return str(oracle_path)
    return str(oracle_path / parts[0])


def _path_exists(path: str, *, endpoint: str | None, region: str | None, path_style: bool | None) -> bool:
    if not path:
        return False
    if path.startswith("s3://"):
        parsed = urlparse(path)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        if "*" in key:
            return bool(_list_s3_matches(bucket, key, endpoint, region, path_style))
        return _head_s3(bucket, key, endpoint, region, path_style)
    local = Path(path)
    if "*" in local.name:
        return bool(list(local.parent.glob(local.name)))
    return local.exists()


def _s3_client(endpoint: str | None, region: str | None, path_style: bool | None):
    config = None
    if path_style:
        config = Config(s3={"addressing_style": "path"})
    return boto3.client("s3", endpoint_url=endpoint, region_name=region, config=config)


def _head_s3(bucket: str, key: str, endpoint: str | None, region: str | None, path_style: bool | None) -> bool:
    client = _s3_client(endpoint, region, path_style)
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def _list_s3_matches(
    bucket: str,
    key_pattern: str,
    endpoint: str | None,
    region: str | None,
    path_style: bool | None,
) -> list[str]:
    from fnmatch import fnmatch

    client = _s3_client(endpoint, region, path_style)
    prefix = key_pattern.split("*", 1)[0]
    paginator = client.get_paginator("list_objects_v2")
    matches: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            candidate = item["Key"]
            if fnmatch(candidate, key_pattern):
                matches.append(candidate)
    return matches
