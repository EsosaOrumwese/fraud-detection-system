"""Segment 3A S1 escalation queue runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

import polars as pl
import yaml
from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_3A.s0_gate.exceptions import err
from engine.layers.l1.seg_3A.s0_gate.l0 import aggregate_sha256, expand_files, hash_files
from engine.layers.l1.seg_3A.shared import SegmentStateKey, load_schema, write_segment_state_run_report
from engine.layers.l1.seg_3A.shared.dictionary import load_dictionary, render_dataset_path

_S0_RECEIPT_VALIDATOR = Draft202012Validator(load_schema("#/validation/s0_gate_receipt_3A"))
_SEALED_INPUT_VALIDATOR = Draft202012Validator(load_schema("#/validation/sealed_inputs_3A"))


@dataclass(frozen=True)
class EscalationInputs:
    data_root: Path
    manifest_fingerprint: str
    seed: int
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class EscalationResult:
    output_path: Path
    run_report_path: Path
    resumed: bool


@dataclass(frozen=True)
class PolicyRule:
    metric: str
    threshold: float
    decision_reason: str
    bucket: Optional[str] = None


@dataclass(frozen=True)
class MixturePolicy:
    policy_id: str
    version: str
    theta_mix: float
    rules: Sequence[PolicyRule]
    digest_hex: str


class EscalationRunner:
    """Deterministic, RNG-free escalation stage."""

    def run(self, inputs: EscalationInputs) -> EscalationResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        seed = int(inputs.seed)

        sealed_inputs_path = self._resolve_dataset_path(
            dictionary=dictionary,
            dataset_id="sealed_inputs_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            base=data_root,
        )
        receipt_path = self._resolve_dataset_path(
            dictionary=dictionary,
            dataset_id="s0_gate_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            base=data_root,
        )
        if not sealed_inputs_path.exists() or not receipt_path.exists():
            raise err("E_S0_PRECONDITION", "S0 artefacts missing; run S0 before S1")

        s0_receipt = self._load_json(receipt_path, _S0_RECEIPT_VALIDATOR)
        sealed_df = pl.read_parquet(sealed_inputs_path)
        self._validate_sealed_inputs(sealed_df)
        self._assert_upstream_pass(s0_receipt)

        sealed_index = {row["logical_id"]: row for row in sealed_df.to_dicts()}
        required_assets = [
            "zone_mixture_policy",
            "outlet_catalogue",
            "tz_world_2025a",
            "iso3166_canonical_2024",
        ]
        asset_paths: dict[str, Path] = {}
        for asset_id in required_assets:
            asset_paths[asset_id] = self._resolve_sealed_asset(sealed_index, asset_id)

        policy = self._load_policy(asset_paths["zone_mixture_policy"])
        outlet_df = pl.read_parquet(asset_paths["outlet_catalogue"])
        zone_df = pl.read_parquet(asset_paths["tz_world_2025a"])
        iso_df = pl.read_parquet(asset_paths["iso3166_canonical_2024"])

        classification = self._classify_pairs(
            outlet_df=outlet_df,
            tz_df=zone_df,
            iso_df=iso_df,
            policy=policy,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
        )

        output_dir = data_root / render_dataset_path(
            dataset_id="s1_escalation_queue",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "part-0.parquet"
        resumed = False
        if output_file.exists():
            existing = pl.read_parquet(output_file)
            if not existing.frame_equal(classification):
                raise err(
                    "E_IMMUTABILITY",
                    f"s1_escalation_queue already exists at '{output_file}' with different content",
                )
            resumed = True
        else:
            classification.write_parquet(output_file)

        run_report_path = (
            data_root
            / f"runs/layer1/3A/s1_escalation/seed={seed}/fingerprint={manifest_fingerprint}/run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = self._write_run_report(
            run_report_path,
            policy=policy,
            result_df=classification,
            manifest_fingerprint=manifest_fingerprint,
            seed=seed,
            s0_receipt=s0_receipt,
            resumed=resumed,
        )
        self._write_segment_state_row(
            base_path=data_root,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=s0_receipt.get("parameter_hash", ""),
            seed=seed,
            elapsed_ms=run_report["elapsed_ms"],
            result_path=output_file,
            run_report_path=run_report_path,
            resumed=resumed,
        )

        return EscalationResult(
            output_path=output_dir,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    # ------------------------------ helpers ------------------------------ #

    def _resolve_dataset_path(
        self,
        *,
        dictionary: Mapping[str, object],
        dataset_id: str,
        template_args: Mapping[str, object],
        base: Path,
    ) -> Path:
        relative = render_dataset_path(
            dataset_id=dataset_id,
            template_args=template_args,
            dictionary=dictionary,
        )
        return (base / relative).resolve()

    def _load_json(self, path: Path, validator: Draft202012Validator) -> Mapping[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        try:
            validator.validate(payload)
        except ValidationError as exc:
            raise err(
                "E_SCHEMA",
                f"'{path}' failed schema validation: {exc.message}",
            ) from exc
        return payload

    def _validate_sealed_inputs(self, sealed_df: pl.DataFrame) -> None:
        for row in sealed_df.to_dicts():
            try:
                _SEALED_INPUT_VALIDATOR.validate(row)
            except ValidationError as exc:
                raise err(
                    "E_SCHEMA",
                    f"sealed_inputs row for '{row.get('logical_id')}' invalid: {exc.message}",
                ) from exc

    def _assert_upstream_pass(self, receipt: Mapping[str, Any]) -> None:
        gates = receipt.get("upstream_gates", {})
        for segment in ("segment_1A", "segment_1B", "segment_2A"):
            status = gates.get(segment, {}).get("status")
            if status != "PASS":
                raise err("E_UPSTREAM_GATE", f"{segment} status '{status}' is not PASS")

    def _resolve_sealed_asset(self, sealed_index: Mapping[str, Mapping[str, Any]], logical_id: str) -> Path:
        row = sealed_index.get(logical_id)
        if row is None:
            raise err("E_ASSET_MISSING", f"sealed_inputs missing '{logical_id}'")
        path = Path(row["path"]).resolve()
        if not path.exists():
            raise err("E_ASSET_PATH", f"sealed asset '{logical_id}' missing at '{path}'")
        expected_sha = row["sha256_hex"]
        actual_sha = self._compute_sha256(path, logical_id)
        if actual_sha != expected_sha:
            raise err(
                "E_ASSET_DIGEST",
                f"sealed asset '{logical_id}' digest mismatch (expected {expected_sha}, got {actual_sha})",
            )
        return path

    def _compute_sha256(self, path: Path, logical_id: str) -> str:
        files = expand_files(path)
        digests = hash_files(files, error_prefix=logical_id)
        return aggregate_sha256(digests)

    def _load_policy(self, policy_path: Path) -> MixturePolicy:
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        policy_id = str(payload.get("policy_id") or payload.get("id") or "zone_mixture_policy")
        version = str(payload.get("version") or payload.get("semver") or "1.0.0")
        try:
            theta_mix = float(payload["theta_mix"])
        except Exception as exc:  # pragma: no cover - schema governs type/required
            raise err("E_POLICY_INVALID", "theta_mix missing or invalid") from exc

        rules_payload = payload.get("rules") or []
        rules: list[PolicyRule] = []
        if isinstance(rules_payload, Iterable):
            for entry in rules_payload:
                if not isinstance(entry, Mapping):
                    continue
                metric = str(entry.get("metric", "")).strip()
                if not metric:
                    continue
                try:
                    threshold = float(entry.get("threshold", 0.0))
                except Exception:
                    continue
                decision_reason = str(entry.get("decision_reason", "")).strip() or metric
                bucket = entry.get("bucket")
                rules.append(PolicyRule(metric=metric, threshold=threshold, decision_reason=decision_reason, bucket=bucket))

        digest_hex = sha256(policy_path.read_bytes()).hexdigest()
        return MixturePolicy(
            policy_id=policy_id,
            version=version,
            theta_mix=theta_mix,
            rules=tuple(rules),
            digest_hex=digest_hex,
        )

    def _classify_pairs(
        self,
        *,
        outlet_df: pl.DataFrame,
        tz_df: pl.DataFrame,
        iso_df: pl.DataFrame,
        policy: MixturePolicy,
        seed: int,
        manifest_fingerprint: str,
    ) -> pl.DataFrame:
        if outlet_df.is_empty():
            return pl.DataFrame(
                schema={
                    "seed": pl.Int64,
                    "manifest_fingerprint": pl.Utf8,
                    "merchant_id": pl.Int64,
                    "legal_country_iso": pl.Utf8,
                    "site_count": pl.Int64,
                    "zone_count_country": pl.Int64,
                    "is_escalated": pl.Boolean,
                    "decision_reason": pl.Utf8,
                    "mixture_policy_id": pl.Utf8,
                    "mixture_policy_version": pl.Utf8,
                    "theta_digest": pl.Utf8,
                    "eligible_for_escalation": pl.Boolean,
                    "dominant_zone_share_bucket": pl.Utf8,
                }
            )

        site_counts = (
            outlet_df.group_by(["merchant_id", "legal_country_iso"])
            .len()
            .rename({"len": "site_count"})
        )
        merchant_totals = (
            site_counts.group_by("merchant_id")
            .agg(pl.col("site_count").sum().alias("merchant_total"))
        )
        stats_df = site_counts.join(merchant_totals, on="merchant_id", how="left")

        country_col = self._detect_country_column(tz_df)
        zone_counts = (
            tz_df.group_by(country_col)
            .agg(pl.col("tzid").n_unique().alias("zone_count_country"))
            .rename({country_col: "legal_country_iso"})
        )
        stats_df = stats_df.join(zone_counts, on="legal_country_iso", how="left")

        iso_col = self._detect_country_column(iso_df)
        iso_codes = set(iso_df[iso_col].to_list())  # type: ignore[arg-type]

        missing_iso = stats_df.filter(~pl.col("legal_country_iso").is_in(iso_codes))
        if not missing_iso.is_empty():
            raise err(
                "E_ISO_DOMAIN",
                f"countries missing from ISO reference: {sorted(set(missing_iso['legal_country_iso']))}",
            )

        if stats_df.filter(pl.col("zone_count_country").is_null() | (pl.col("zone_count_country") <= 0)).height > 0:
            raise err("E_TZ_UNIVERSE", "zone universe missing for one or more countries")

        share_df = stats_df.with_columns(
            (pl.col("site_count") / pl.col("merchant_total")).alias("site_share")
        )

        records = []
        bucket_rules = [rule for rule in policy.rules if rule.metric == "share_bucket"]
        gating_rules = [rule for rule in policy.rules if rule.metric != "share_bucket"]

        for row in share_df.sort(["merchant_id", "legal_country_iso"]).to_dicts():
            site_count = int(row["site_count"])
            zone_count = int(row["zone_count_country"])
            share = float(row["site_share"])
            reason = None
            eligible = True
            for rule in gating_rules:
                if rule.metric == "min_sites" and site_count < rule.threshold:
                    reason = rule.decision_reason or "below_min_sites"
                    eligible = False
                    break
                if rule.metric == "min_zone_count" and zone_count < rule.threshold:
                    reason = rule.decision_reason or "single_zone_country"
                    break
                if rule.metric == "site_share_min" and share < rule.threshold:
                    reason = rule.decision_reason or "dominant_zone_threshold"
                    break

            if reason is None and share < policy.theta_mix:
                reason = "dominant_zone_threshold"

            is_escalated = reason is None
            final_reason = reason if reason is not None else "default_escalation"

            bucket_label = self._resolve_share_bucket(share, bucket_rules)

            records.append(
                {
                    "seed": seed,
                    "manifest_fingerprint": manifest_fingerprint,
                    "merchant_id": row["merchant_id"],
                    "legal_country_iso": row["legal_country_iso"],
                    "site_count": site_count,
                    "zone_count_country": zone_count,
                    "is_escalated": is_escalated,
                    "decision_reason": final_reason,
                    "mixture_policy_id": policy.policy_id,
                    "mixture_policy_version": policy.version,
                    "theta_digest": policy.digest_hex,
                    "eligible_for_escalation": eligible and zone_count > 0,
                    "dominant_zone_share_bucket": bucket_label,
                }
            )

        return pl.DataFrame(records)

    def _detect_country_column(self, df: pl.DataFrame) -> str:
        for candidate in ("country_iso", "legal_country_iso", "iso"):
            if candidate in df.columns:
                return candidate
        raise err("E_TZ_UNIVERSE", "unable to find country column in reference dataset")

    def _resolve_share_bucket(self, share: float, rules: Sequence[PolicyRule]) -> Optional[str]:
        if not rules:
            return None
        for rule in sorted(rules, key=lambda r: r.threshold):
            if share <= rule.threshold + 1e-12:
                return rule.bucket or rule.decision_reason
        return rules[-1].bucket or rules[-1].decision_reason

    def _write_run_report(
        self,
        path: Path,
        *,
        policy: MixturePolicy,
        result_df: pl.DataFrame,
        manifest_fingerprint: str,
        seed: int,
        s0_receipt: Mapping[str, Any],
        resumed: bool,
    ) -> Mapping[str, object]:
        started = datetime.now(timezone.utc)
        total_rows = result_df.height
        escalated = int(result_df.filter(pl.col("is_escalated")).height)
        elapsed = 0
        run_payload = {
            "layer": "layer1",
            "segment": "3A",
            "state": "S1",
            "status": "PASS",
            "error_code": None,
            "parameter_hash": s0_receipt.get("parameter_hash"),
            "manifest_fingerprint": manifest_fingerprint,
            "seed": seed,
            "pairs_total": total_rows,
            "pairs_escalated": escalated,
            "pairs_monolithic": total_rows - escalated,
            "escalation_rate": (escalated / total_rows) if total_rows else 0.0,
            "mixture_policy_id": policy.policy_id,
            "mixture_policy_version": policy.version,
            "theta_digest": policy.digest_hex,
        }
        gate_status = s0_receipt.get("upstream_gates", {})
        run_payload.update(
            {
                "s0_gate_status": "PASS",
                "gate_1A_status": gate_status.get("segment_1A", {}).get("status", "NOT_CHECKED"),
                "gate_1B_status": gate_status.get("segment_1B", {}).get("status", "NOT_CHECKED"),
                "gate_2A_status": gate_status.get("segment_2A", {}).get("status", "NOT_CHECKED"),
            }
        )
        bucket_counts = result_df.group_by("zone_count_country").agg(pl.len().alias("pair_count")).to_dicts()
        run_payload["pairs_by_zone_count_bucket"] = {
            str(record["zone_count_country"]): int(record["pair_count"]) for record in bucket_counts
        }
        finished = datetime.now(timezone.utc)
        elapsed = int((finished - started).total_seconds() * 1000)
        run_payload["started_at_utc"] = started.isoformat()
        run_payload["finished_at_utc"] = finished.isoformat()
        run_payload["elapsed_ms"] = elapsed
        run_payload["resumed"] = resumed

        path.write_text(json.dumps(run_payload, indent=2, sort_keys=True), encoding="utf-8")
        return run_payload

    def _write_segment_state_row(
        self,
        *,
        base_path: Path,
        manifest_fingerprint: str,
        parameter_hash: str | None,
        seed: int,
        elapsed_ms: int,
        result_path: Path,
        run_report_path: Path,
        resumed: bool,
    ) -> None:
        if not parameter_hash:
            return
        key = SegmentStateKey(
            layer="layer1",
            segment="3A",
            state="S1",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        payload = {
            **key.as_dict(),
            "status": "PASS",
            "attempt": 1,
            "elapsed_ms": elapsed_ms,
            "output_path": str(result_path),
            "run_report_path": str(run_report_path),
            "resumed": resumed,
        }
        write_segment_state_run_report(base_path=base_path, key=key, payload=payload)
