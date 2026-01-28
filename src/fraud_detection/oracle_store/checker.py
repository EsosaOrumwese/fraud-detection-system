"""Oracle Store validation checks (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.config import Config
import json

from fraud_detection.ingestion_gate.catalogue import OutputCatalogue
from fraud_detection.scenario_runner.schemas import SchemaRegistry
from fraud_detection.scenario_runner.storage import LocalObjectStore, S3ObjectStore

from .config import OracleProfile


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
        self.schema = SchemaRegistry(Path(profile.wiring.schema_root) / "scenario_runner")

    def check_run_facts(
        self,
        run_facts_ref: str,
        *,
        strict_seal: bool = False,
        require_digest: bool = True,
    ) -> OracleCheckReport:
        report = OracleCheckReport(status="OK")
        facts = self._load_run_facts(run_facts_ref, report)
        if facts is None:
            report.status = "FAIL"
            return report
        if not self._validate_facts_schema(facts, report):
            report.status = "FAIL"
            return report

        output_roles = facts.get("output_roles", {})
        locators = facts.get("locators", [])
        traffic_outputs = {
            output_id for output_id, role in output_roles.items() if role == "business_traffic"
        }
        locator_ids = {loc.get("output_id") for loc in locators}
        traffic_outputs = {oid for oid in traffic_outputs if oid in locator_ids}

        if self.profile.policy.require_gate_pass:
            missing = self._missing_required_gates(facts, traffic_outputs)
            if missing:
                report.add_issue("GATE_PASS_MISSING", detail=json.dumps(missing, sort_keys=True), severity="ERROR")
                report.status = "FAIL"

        seal_missing = self._check_seal_markers(locators)
        for pack_root in seal_missing:
            severity = "ERROR" if strict_seal else "WARN"
            report.add_issue("PACK_NOT_SEALED", detail=pack_root, severity=severity)
        if strict_seal and seal_missing:
            report.status = "FAIL"

        missing_locators = 0
        missing_digests = 0
        for locator in locators:
            path = locator.get("path", "")
            resolved = _resolve_oracle_path(path, self.profile.wiring.oracle_root)
            if require_digest and not locator.get("content_digest"):
                missing_digests += 1
                report.add_issue("DIGEST_MISSING", detail=resolved, severity="ERROR")
            if not _path_exists(
                resolved,
                endpoint=self.profile.wiring.object_store_endpoint,
                region=self.profile.wiring.object_store_region,
                path_style=self.profile.wiring.object_store_path_style,
            ):
                missing_locators += 1
                report.add_issue("LOCATOR_MISSING", detail=resolved, severity="ERROR")
        if missing_digests and not require_digest:
            report.add_issue("DIGEST_MISSING", detail=str(missing_digests), severity="WARN")
        if missing_locators:
            report.status = "FAIL"

        if report.errors:
            report.status = "FAIL"
        elif report.warnings:
            report.status = "WARN"
        report.details = {
            "locators_total": len(locators),
            "locators_missing": missing_locators,
            "locators_missing_digest": missing_digests,
        }
        return report

    def _load_run_facts(self, run_facts_ref: str, report: OracleCheckReport) -> dict[str, Any] | None:
        try:
            if run_facts_ref.startswith("s3://"):
                parsed = urlparse(run_facts_ref)
                store = S3ObjectStore(
                    parsed.netloc,
                    prefix="",
                    endpoint_url=self.profile.wiring.object_store_endpoint,
                    region_name=self.profile.wiring.object_store_region,
                    path_style=self.profile.wiring.object_store_path_style,
                )
                return store.read_json(parsed.path.lstrip("/"))
            if Path(run_facts_ref).is_absolute():
                return _read_json(Path(run_facts_ref))
            store = _build_object_store(self.profile)
            return store.read_json(run_facts_ref)
        except Exception as exc:
            report.add_issue("RUN_FACTS_UNREADABLE", detail=str(exc), severity="ERROR")
            return None

    def _validate_facts_schema(self, facts: dict[str, Any], report: OracleCheckReport) -> bool:
        try:
            self.schema.validate("run_facts_view.schema.yaml", facts)
            return True
        except Exception as exc:
            report.add_issue("RUN_FACTS_INVALID", detail=str(exc), severity="ERROR")
            return False

    def _missing_required_gates(self, facts: dict[str, Any], output_ids: set[str]) -> dict[str, list[str]]:
        passed = {
            receipt.get("gate_id")
            for receipt in facts.get("gate_receipts", [])
            if receipt.get("status") == "PASS"
        }
        missing: dict[str, list[str]] = {}
        for output_id in output_ids:
            entry = self.catalogue.get(output_id)
            required = list(entry.read_requires_gates or [])
            missing_gates = [gate for gate in required if gate not in passed]
            if missing_gates:
                missing[output_id] = missing_gates
        return missing

    def _check_seal_markers(self, locators: list[dict[str, Any]]) -> list[str]:
        missing: list[str] = []
        oracle_root = self.profile.wiring.oracle_root
        seen: set[str] = set()
        for locator in locators:
            path = locator.get("path", "")
            pack_root = _pack_root_from_locator(path, oracle_root)
            if not pack_root or pack_root in seen:
                continue
            seen.add(pack_root)
            seal_paths = [
                str(Path(pack_root) / "_SEALED.flag"),
                str(Path(pack_root) / "_SEALED.json"),
                str(Path(pack_root) / "_oracle_pack_manifest.json"),
            ]
            if not any(Path(p).exists() for p in seal_paths):
                missing.append(pack_root)
        return missing


def _build_object_store(profile: OracleProfile) -> LocalObjectStore | S3ObjectStore:
    root = profile.wiring.object_store_root
    endpoint = profile.wiring.object_store_endpoint
    region = profile.wiring.object_store_region
    path_style = profile.wiring.object_store_path_style
    if root.startswith("s3://"):
        parsed = urlparse(root)
        return S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=endpoint,
            region_name=region,
            path_style=path_style,
        )
    return LocalObjectStore(Path(root))


def _read_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


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
