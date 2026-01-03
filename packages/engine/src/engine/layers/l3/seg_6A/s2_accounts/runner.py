"""Segment 6A S2 account base runner."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import math
import polars as pl
import yaml

from engine.layers.l3.seg_6A.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l3.seg_6A.shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path, repository_root
from engine.layers.l3.shared.deterministic import largest_remainder, normal_icdf, stable_uniform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccountInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class AccountOutputs:
    account_base_path: Path
    holdings_path: Path
    merchant_account_path: Path | None
    account_summary_path: Path | None


class AccountRunner:
    """Builds the 6A.S2 account universe."""

    def run(self, inputs: AccountInputs) -> AccountOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        repo_root = repository_root()
        receipt, sealed_df = load_control_plane(
            data_root=inputs.data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        self._assert_upstream_pass(receipt.payload)
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

        party_path = inputs.data_root / render_dataset_path(
            dataset_id="s1_party_base_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        party_df = pl.read_parquet(party_path)

        segmentation_priors = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_segmentation_6A", dictionary, sealed_df)
            )[0]
        )
        account_taxonomy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("taxonomy_account_types_6A", dictionary, sealed_df)
            )[0]
        )
        product_mix = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_product_mix_6A", dictionary, sealed_df)
            )[0]
        )
        account_priors = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_account_per_party_6A", dictionary, sealed_df)
            )[0]
        )

        account_types = [
            row for row in (account_taxonomy.get("account_types") or []) if isinstance(row, Mapping)
        ]
        account_types_by_party: dict[str, list[str]] = {}
        for entry in account_types:
            if entry.get("owner_kind") != "PARTY":
                continue
            acc_id = str(entry.get("id"))
            for party_type in entry.get("allowed_party_types") or []:
                account_types_by_party.setdefault(str(party_type), []).append(acc_id)

        domain = product_mix.get("party_account_domain") or {}
        allowed_by_party = domain.get("allowed_account_types_by_party_type") or {}

        lambda_model = product_mix.get("party_lambda_model") or {}
        base_lambda = lambda_model.get("base_lambda_by_party_type") or {}

        segment_profiles = {
            str(row.get("segment_id")): row
            for row in (segmentation_priors.get("segment_profiles") or [])
            if isinstance(row, Mapping)
        }
        lambda_model = product_mix.get("party_lambda_model") or {}
        base_lambda = lambda_model.get("base_lambda_by_party_type") or {}
        segment_tilt = lambda_model.get("segment_tilt") or {}
        tilt_features = [str(feature) for feature in (segment_tilt.get("features") or [])]
        tilt_weights = segment_tilt.get("weights_by_feature") or {}
        tilt_clip = float(segment_tilt.get("clip_log_multiplier", 0.0) or 0.0)
        tilt_center = float(segment_tilt.get("feature_center", 0.5))

        rule_params = self._rule_params(account_priors)

        account_rows = []
        account_id = 1
        party_groups_df = (
            party_df.group_by(["region_id", "party_type", "segment_id"])
            .agg(pl.col("party_id").alias("party_ids"), pl.col("country_iso").first())
        )
        total_groups = party_groups_df.height
        log_every = 25
        log_interval = 120.0
        start_time = time.monotonic()
        last_log = start_time
        group_index = 0

        for group in party_groups_df.iter_rows(named=True):
            group_index += 1
            party_type = str(group.get("party_type"))
            segment_id = str(group.get("segment_id"))
            allowed_types = self._resolve_allowed_types(domain, party_type, segment_id, account_types_by_party)
            if not allowed_types:
                continue
            party_ids = [int(pid) for pid in group.get("party_ids") or []]
            if not party_ids:
                continue

            for account_type in allowed_types:
                lambda_value = self._compute_lambda(
                    party_type=party_type,
                    segment_id=segment_id,
                    account_type=account_type,
                    base_lambda=base_lambda,
                    segment_profiles=segment_profiles,
                    tilt_features=tilt_features,
                    tilt_weights=tilt_weights,
                    tilt_clip=tilt_clip,
                    tilt_center=tilt_center,
                )
                if lambda_value <= 0:
                    continue
                target = max(0, int(round(len(party_ids) * lambda_value)))
                if target == 0:
                    continue
                params = rule_params.get((party_type, account_type)) or rule_params.get((party_type, "*")) or {}
                weights = [
                    self._weight_for_party(
                        inputs=inputs,
                        party_id=party_id,
                        account_type=account_type,
                        params=params,
                    )
                    for party_id in party_ids
                ]
                allocations = largest_remainder(weights, target)
                for party_id, count in zip(party_ids, allocations):
                    if count <= 0:
                        continue
                    for _ in range(count):
                        account_rows.append(
                            {
                                "account_id": account_id,
                                "owner_party_id": party_id,
                                "account_type": account_type,
                                "party_type": party_type,
                                "segment_id": segment_id,
                                "region_id": group.get("region_id"),
                                "country_iso": group.get("country_iso"),
                                "seed": inputs.seed,
                                "manifest_fingerprint": inputs.manifest_fingerprint,
                                "parameter_hash": inputs.parameter_hash,
                            }
                        )
                        account_id += 1
            now = time.monotonic()
            if group_index % log_every == 0 or (now - last_log) >= log_interval:
                elapsed = max(now - start_time, 0.0)
                rate = group_index / elapsed if elapsed > 0 else 0.0
                remaining = total_groups - group_index
                eta = remaining / rate if rate > 0 else 0.0
                logger.info(
                    "6A.S2 account build progress groups=%s/%s accounts=%s elapsed=%.1fs rate=%.2f/s eta=%.1fs",
                    group_index,
                    total_groups,
                    account_id - 1,
                    elapsed,
                    rate,
                    eta,
                )
                last_log = now

        account_df = pl.DataFrame(account_rows)
        account_base_path = inputs.data_root / render_dataset_path(
            dataset_id="s2_account_base_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        account_base_path.parent.mkdir(parents=True, exist_ok=True)
        account_df.write_parquet(account_base_path)

        holdings_df = (
            account_df.group_by(["owner_party_id", "account_type"])
            .len()
            .rename({"len": "account_count"})
        )
        holdings_path = inputs.data_root / render_dataset_path(
            dataset_id="s2_party_product_holdings_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        holdings_path.parent.mkdir(parents=True, exist_ok=True)
        holdings_df.write_parquet(holdings_path)

        summary_df = (
            account_df.group_by(["country_iso", "region_id", "party_type", "account_type"])
            .len()
            .rename({"len": "account_count"})
        )
        summary_path = inputs.data_root / render_dataset_path(
            dataset_id="s2_account_summary_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.write_parquet(summary_path)

        logger.info("6A.S2 accounts=%s", len(account_rows))

        return AccountOutputs(
            account_base_path=account_base_path,
            holdings_path=holdings_path,
            merchant_account_path=None,
            account_summary_path=summary_path,
        )

    @staticmethod
    def _load_yaml(path: Path) -> Mapping[str, object]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"expected mapping in {path}")
        return payload

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6A missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6A.S2 upstream segment {segment} not PASS")

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
    def _resolve_allowed_types(
        domain: Mapping[str, object],
        party_type: str,
        segment_id: str,
        fallback: Mapping[str, list[str]],
    ) -> list[str]:
        mode = str(domain.get("mode") or "explicit_by_party_type")
        if mode == "explicit_by_party_type_and_segment":
            for row in domain.get("allowed_account_types_by_segment") or []:
                if not isinstance(row, Mapping):
                    continue
                if str(row.get("party_type")) != party_type:
                    continue
                if str(row.get("segment_id")) != segment_id:
                    continue
                allowed = row.get("allowed_account_types") or []
                return [str(account_type) for account_type in allowed if account_type]
        allowed = domain.get("allowed_account_types_by_party_type") or {}
        types = allowed.get(party_type) or []
        if types:
            return [str(account_type) for account_type in types if account_type]
        return list(dict.fromkeys(fallback.get(party_type, [])))

    @staticmethod
    def _compute_lambda(
        *,
        party_type: str,
        segment_id: str,
        account_type: str,
        base_lambda: Mapping[str, object],
        segment_profiles: Mapping[str, Mapping[str, object]],
        tilt_features: list[str],
        tilt_weights: Mapping[str, object],
        tilt_clip: float,
        tilt_center: float,
    ) -> float:
        base = float(base_lambda.get(party_type, {}).get(account_type, 0.0))
        if base <= 0:
            return 0.0
        profile = segment_profiles.get(segment_id, {})
        log_multiplier = 0.0
        for feature in tilt_features:
            weight_map = tilt_weights.get(feature) or {}
            weight = float(weight_map.get(account_type, 0.0))
            score = float(profile.get(feature, tilt_center))
            log_multiplier += weight * (score - tilt_center)
        if tilt_clip > 0:
            log_multiplier = max(-tilt_clip, min(tilt_clip, log_multiplier))
        return max(0.0, base * math.exp(log_multiplier))

    @staticmethod
    def _rule_params(priors: Mapping[str, object]) -> dict[tuple[str, str], Mapping[str, object]]:
        rules: dict[tuple[str, str], Mapping[str, object]] = {}
        for rule in priors.get("rules") or []:
            if not isinstance(rule, Mapping):
                continue
            party_type = str(rule.get("party_type") or "")
            account_type = str(rule.get("account_type") or "")
            if party_type and account_type:
                rules[(party_type, account_type)] = rule.get("params") or {}
        return rules

    def _weight_for_party(
        self,
        *,
        inputs: AccountInputs,
        party_id: int,
        account_type: str,
        params: Mapping[str, object],
    ) -> float:
        p_zero_weight = float(params.get("p_zero_weight", 0.3))
        sigma = float(params.get("sigma", 0.8))
        weight_floor = float(params.get("weight_floor_eps", 1e-6))
        p_zero_weight = max(0.0, min(1.0, p_zero_weight))
        sigma = max(0.0, sigma)

        u0 = stable_uniform(
            inputs.manifest_fingerprint,
            inputs.parameter_hash,
            party_id,
            account_type,
            "zero_gate",
        )
        if u0 < p_zero_weight:
            return 0.0
        u1 = stable_uniform(
            inputs.manifest_fingerprint,
            inputs.parameter_hash,
            party_id,
            account_type,
            "weight",
        )
        z = normal_icdf(u1)
        weight = math.exp(sigma * z - 0.5 * sigma * sigma)
        return max(weight_floor, weight)


__all__ = ["AccountRunner", "AccountInputs", "AccountOutputs"]
