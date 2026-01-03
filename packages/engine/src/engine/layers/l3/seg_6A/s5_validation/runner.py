"""Segment 6A S5 fraud posture + validation runner."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import polars as pl
import yaml

from engine.layers.l3.seg_6A.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l3.seg_6A.shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path, repository_root
from engine.layers.l3.shared.bundle import BundleIndex, IndexEntry, compute_index_digest
from engine.layers.l3.shared.deterministic import normalise, stable_uniform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostureInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class PostureOutputs:
    party_roles_path: Path
    account_roles_path: Path
    merchant_roles_path: Path
    device_roles_path: Path
    ip_roles_path: Path
    report_path: Path
    issue_table_path: Path
    bundle_index_path: Path
    passed_flag_path: Path | None


class PostureRunner:
    """Assign static fraud roles and emit validation bundle for 6A."""

    _SPEC_VERSION = "1.0.0"

    def run(self, inputs: PostureInputs) -> PostureOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        repo_root = repository_root()
        receipt, sealed_df = load_control_plane(
            data_root=inputs.data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        inventory = SealedInventory(
            dataframe=sealed_df,
            base_path=inputs.data_root,
            repo_root=repo_root,
            template_args={
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
                "seed": str(inputs.seed),
            },
        )
        self._assert_upstream_pass(receipt.payload)

        party_df = self._load_dataset(inputs, dictionary, "s1_party_base_6A")
        account_df = self._load_dataset(inputs, dictionary, "s2_account_base_6A")
        device_df = self._load_dataset(inputs, dictionary, "s4_device_base_6A")
        ip_df = self._load_dataset(inputs, dictionary, "s4_ip_base_6A")
        merchant_ids = self._load_merchants(inventory, dictionary, sealed_df)

        party_prior = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_party_roles_6A", dictionary, sealed_df)
            )[0]
        )
        account_prior = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_account_roles_6A", dictionary, sealed_df)
            )[0]
        )
        merchant_prior = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_merchant_roles_6A", dictionary, sealed_df)
            )[0]
        )
        device_prior = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_device_roles_6A", dictionary, sealed_df)
            )[0]
        )
        ip_prior = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_ip_roles_6A", dictionary, sealed_df)
            )[0]
        )

        party_roles = self._assign_roles(
            entity_df=party_df,
            id_col="party_id",
            prior=party_prior,
            inputs=inputs,
            role_field="fraud_role_party",
        )
        account_roles = self._assign_roles(
            entity_df=account_df,
            id_col="account_id",
            prior=account_prior,
            inputs=inputs,
            role_field="fraud_role_account",
        )
        merchant_roles = self._assign_roles_to_list(
            entity_ids=merchant_ids,
            prior=merchant_prior,
            inputs=inputs,
            role_field="fraud_role_merchant",
            id_field="merchant_id",
        )
        device_roles = self._assign_roles(
            entity_df=device_df,
            id_col="device_id",
            prior=device_prior,
            inputs=inputs,
            role_field="fraud_role_device",
        )
        ip_roles = self._assign_roles(
            entity_df=ip_df,
            id_col="ip_id",
            prior=ip_prior,
            inputs=inputs,
            role_field="fraud_role_ip",
        )

        party_roles_path = self._write_dataset(party_roles, inputs, dictionary, "s5_party_fraud_roles_6A")
        account_roles_path = self._write_dataset(account_roles, inputs, dictionary, "s5_account_fraud_roles_6A")
        merchant_roles_path = self._write_dataset(merchant_roles, inputs, dictionary, "s5_merchant_fraud_roles_6A")
        device_roles_path = self._write_dataset(device_roles, inputs, dictionary, "s5_device_fraud_roles_6A")
        ip_roles_path = self._write_dataset(ip_roles, inputs, dictionary, "s5_ip_fraud_roles_6A")

        issues = self._validate_outputs(inputs, dictionary)
        overall_status = "PASS" if not issues else "FAIL"

        report_payload = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "spec_version_6A": self._SPEC_VERSION,
            "overall_status": overall_status,
            "upstream_segments": self._upstream_payload(receipt.payload),
            "segment_states": {
                "6A.S1": "PASS",
                "6A.S2": "PASS",
                "6A.S3": "PASS",
                "6A.S4": "PASS",
                "6A.S5": overall_status,
            },
            "checks": self._summarise_checks(issues),
        }
        report_path = self._write_report(inputs, dictionary, report_payload)
        issue_table_path = self._write_issue_table(inputs, dictionary, issues)

        bundle_index_path, bundle_digest = self._write_bundle_index(
            inputs=inputs,
            dictionary=dictionary,
            report_path=report_path,
            issue_table_path=issue_table_path,
        )
        passed_flag_path = self._write_pass_flag(inputs, dictionary, bundle_digest, overall_status)

        logger.info(
            "6A.S5 roles: party=%s account=%s merchant=%s device=%s ip=%s",
            party_roles.height,
            account_roles.height,
            merchant_roles.height,
            device_roles.height,
            ip_roles.height,
        )

        return PostureOutputs(
            party_roles_path=party_roles_path,
            account_roles_path=account_roles_path,
            merchant_roles_path=merchant_roles_path,
            device_roles_path=device_roles_path,
            ip_roles_path=ip_roles_path,
            report_path=report_path,
            issue_table_path=issue_table_path,
            bundle_index_path=bundle_index_path,
            passed_flag_path=passed_flag_path,
        )

    @staticmethod
    def _load_yaml(path: Path) -> Mapping[str, object]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"expected mapping in {path}")
        return payload

    def _manifest_key_for(
        self,
        dataset_id: str,
        dictionary: Mapping[str, object] | Sequence[object],
        sealed_df: pl.DataFrame,
    ) -> str:
        entry = get_dataset_entry(dataset_id, dictionary=dictionary)
        path_template = str(entry.get("path") or "").strip()
        rows = sealed_df.filter(pl.col("path_template") == path_template).to_dicts()
        if rows:
            return str(rows[0].get("manifest_key"))
        return f"mlr.6A.dataset.{dataset_id}"

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6A missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6A.S5 upstream segment {segment} not PASS")

    def _assign_roles(
        self,
        *,
        entity_df: pl.DataFrame,
        id_col: str,
        prior: Mapping[str, object],
        inputs: PostureInputs,
        role_field: str,
    ) -> pl.DataFrame:
        entity_ids = [int(row[id_col]) for row in entity_df.select(id_col).to_dicts()]
        return self._assign_roles_to_list(
            entity_ids=entity_ids,
            prior=prior,
            inputs=inputs,
            role_field=role_field,
            id_field=id_col,
        )

    def _assign_roles_to_list(
        self,
        *,
        entity_ids: list[int],
        prior: Mapping[str, object],
        inputs: PostureInputs,
        role_field: str,
        id_field: str,
    ) -> pl.DataFrame:
        roles, weights = self._role_weights(prior)
        tiers = self._risk_tiers(prior)
        rows: list[Mapping[str, object]] = []
        for entity_id in entity_ids:
            role = self._choose_weighted(
                roles,
                weights,
                inputs.manifest_fingerprint,
                inputs.parameter_hash,
                entity_id,
                role_field,
            )
            tier = self._tier_for_role(role, tiers)
            rows.append(
                {
                    id_field: entity_id,
                    role_field: role,
                    "risk_tier": tier,
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": inputs.parameter_hash,
                    "seed": inputs.seed,
                }
            )
        return pl.DataFrame(rows)

    @staticmethod
    def _role_weights(prior: Mapping[str, object]) -> tuple[list[str], list[float]]:
        vocab = [
            str(row.get("role_id"))
            for row in (prior.get("role_vocabulary") or [])
            if isinstance(row, Mapping) and row.get("role_id")
        ]
        if not vocab:
            vocab = ["CLEAN"]
        probs = prior.get("role_probability_model") or {}
        base_probs = {
            str(row.get("role_id")): float(row.get("share", 0.0))
            for row in (probs.get("base_role_probs") or [])
            if isinstance(row, Mapping)
        }
        if not base_probs:
            if "CLEAN" in vocab:
                remaining = max(0.0, 1.0 - 0.97)
                per_other = remaining / max(1, len(vocab) - 1)
                base_probs = {role: (0.97 if role == "CLEAN" else per_other) for role in vocab}
            else:
                base_probs = {role: 1.0 for role in vocab}
        weights = normalise([base_probs.get(role, 0.0) for role in vocab])
        return vocab, weights

    @staticmethod
    def _risk_tiers(prior: Mapping[str, object]) -> list[str]:
        tiers = [
            str(row.get("tier_id"))
            for row in (prior.get("risk_tier_vocabulary") or [])
            if isinstance(row, Mapping) and row.get("tier_id")
        ]
        if not tiers:
            tiers = ["STANDARD"]
        return tiers

    @staticmethod
    def _tier_for_role(role: str, tiers: list[str]) -> str:
        if role != "CLEAN" and "HIGH" in tiers:
            return "HIGH"
        if "STANDARD" in tiers:
            return "STANDARD"
        return tiers[0] if tiers else "STANDARD"

    @staticmethod
    def _choose_weighted(
        values: list[str],
        weights: list[float],
        *seed_parts: object,
    ) -> str:
        if not values:
            return "UNKNOWN"
        if not weights or len(weights) != len(values):
            return values[0]
        u = stable_uniform(*seed_parts)
        cumulative = 0.0
        for value, weight in zip(values, weights):
            cumulative += weight
            if u <= cumulative:
                return value
        return values[-1]

    @staticmethod
    def _write_dataset(
        df: pl.DataFrame,
        inputs: PostureInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        dataset_id: str,
    ) -> Path:
        path = inputs.data_root / render_dataset_path(
            dataset_id=dataset_id,
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)
        return path

    @staticmethod
    def _load_dataset(
        inputs: PostureInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        dataset_id: str,
    ) -> pl.DataFrame:
        path = inputs.data_root / render_dataset_path(
            dataset_id=dataset_id,
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        return pl.read_parquet(path)

    def _load_merchants(
        self,
        inventory: SealedInventory,
        dictionary: Mapping[str, object] | Sequence[object],
        sealed_df: pl.DataFrame,
    ) -> list[int]:
        try:
            manifest_key = self._manifest_key_for("outlet_catalogue", dictionary, sealed_df)
            paths = inventory.resolve_files(manifest_key=manifest_key)
        except Exception:
            return []
        if not paths:
            return []
        df = pl.scan_parquet([path.as_posix() for path in paths]).select("merchant_id").unique().collect()
        return [int(row["merchant_id"]) for row in df.to_dicts() if row.get("merchant_id") is not None]

    def _validate_outputs(self, inputs: PostureInputs, dictionary: Mapping[str, object]) -> list[Mapping[str, object]]:
        issues: list[Mapping[str, object]] = []
        required_ids = [
            "s5_party_fraud_roles_6A",
            "s5_account_fraud_roles_6A",
            "s5_merchant_fraud_roles_6A",
            "s5_device_fraud_roles_6A",
            "s5_ip_fraud_roles_6A",
        ]
        for dataset_id in required_ids:
            path = inputs.data_root / render_dataset_path(
                dataset_id=dataset_id,
                template_args={
                    "seed": inputs.seed,
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": inputs.parameter_hash,
                },
                dictionary=dictionary,
            )
            if not path.exists():
                issues.append(
                    {
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "check_id": "S5_MISSING_OUTPUT",
                        "issue_id": f"{dataset_id}",
                        "severity": "FAIL",
                        "scope_type": "dataset",
                        "seed": inputs.seed,
                        "message": f"missing {dataset_id} at {path}",
                    }
                )
        return issues

    @staticmethod
    def _summarise_checks(issues: list[Mapping[str, object]]) -> list[Mapping[str, object]]:
        if not issues:
            return [
                {
                    "check_id": "S5_OUTPUTS_PRESENT",
                    "severity": "REQUIRED",
                    "result": "PASS",
                }
            ]
        return [
            {
                "check_id": "S5_OUTPUTS_PRESENT",
                "severity": "REQUIRED",
                "result": "FAIL",
                "metrics": {"issues_total": len(issues)},
            }
        ]

    @staticmethod
    def _upstream_payload(receipt: Mapping[str, object]) -> Mapping[str, object]:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            return {}
        payload: dict[str, object] = {}
        for segment, status in upstream.items():
            if isinstance(status, Mapping):
                payload[segment] = {
                    "status": status.get("status"),
                    "bundle_sha256": status.get("bundle_sha256"),
                    "flag_path": status.get("flag_path"),
                }
        return payload

    def _write_report(
        self,
        inputs: PostureInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        payload: Mapping[str, object],
    ) -> Path:
        path = inputs.data_root / render_dataset_path(
            dataset_id="s5_validation_report_6A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def _write_issue_table(
        self,
        inputs: PostureInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        issues: list[Mapping[str, object]],
    ) -> Path:
        path = inputs.data_root / render_dataset_path(
            dataset_id="s5_issue_table_6A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(issues).write_parquet(path)
        return path

    def _write_bundle_index(
        self,
        *,
        inputs: PostureInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        report_path: Path,
        issue_table_path: Path,
    ) -> tuple[Path, str]:
        bundle_dir = report_path.parent
        entries = [
            self._bundle_item(bundle_dir, report_path, role="validation_report"),
            self._bundle_item(bundle_dir, issue_table_path, role="issue_table"),
        ]
        index_payload = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "spec_version_6A": self._SPEC_VERSION,
            "items": entries,
        }
        index_path = inputs.data_root / render_dataset_path(
            dataset_id="validation_bundle_index_6A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")

        bundle_index = BundleIndex(
            entries=[
                IndexEntry(artifact_id=item["role"], path=item["path"], raw=item)
                for item in entries + [self._bundle_item(bundle_dir, index_path, role="index")]
            ]
        )
        digest = compute_index_digest(bundle_dir, bundle_index)
        return index_path, digest

    @staticmethod
    def _bundle_item(bundle_dir: Path, path: Path, *, role: str) -> Mapping[str, object]:
        rel_path = path.relative_to(bundle_dir).as_posix()
        sha256_hex = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "path": rel_path,
            "sha256_hex": sha256_hex,
            "role": role,
            "schema_ref": None,
        }

    def _write_pass_flag(
        self,
        inputs: PostureInputs,
        dictionary: Mapping[str, object] | Sequence[object],
        digest: str,
        overall_status: str,
    ) -> Path | None:
        path = inputs.data_root / render_dataset_path(
            dataset_id="validation_passed_flag_6A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        if overall_status != "PASS":
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"sha256_hex = {digest}", encoding="utf-8")
        return path


__all__ = ["PostureInputs", "PostureOutputs", "PostureRunner"]
