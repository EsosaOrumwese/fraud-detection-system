"""Segment 6A S4 device/IP network graph runner."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import polars as pl
import yaml

from engine.layers.l3.seg_6A.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l3.seg_6A.shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path, repository_root
from engine.layers.l3.shared.deterministic import normalise, stable_uniform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NetworkInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class NetworkOutputs:
    device_base_path: Path
    ip_base_path: Path
    device_links_path: Path
    ip_links_path: Path
    neighbourhoods_path: Path | None
    network_summary_path: Path | None


class NetworkRunner:
    """Build device/IP bases and static link graph for 6A.S4."""

    def run(self, inputs: NetworkInputs) -> NetworkOutputs:
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
        instrument_df = self._load_dataset(inputs, dictionary, "s3_instrument_base_6A")

        segmentation_priors = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_segmentation_6A", dictionary, sealed_df)
            )[0]
        )
        device_priors = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_device_counts_6A", dictionary, sealed_df)
            )[0]
        )
        ip_priors = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_ip_counts_6A", dictionary, sealed_df)
            )[0]
        )
        device_taxonomy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("taxonomy_devices_6A", dictionary, sealed_df)
            )[0]
        )
        ip_taxonomy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("taxonomy_ips_6A", dictionary, sealed_df)
            )[0]
        )
        linkage_rules = self._load_optional_yaml(
            inventory,
            dictionary,
            sealed_df,
            "device_linkage_rules_6A",
        )

        segment_profiles = {
            str(row.get("segment_id")): row
            for row in (segmentation_priors.get("segment_profiles") or [])
            if isinstance(row, Mapping)
        }
        device_types = [
            str(row.get("id"))
            for row in (device_taxonomy.get("device_types") or [])
            if isinstance(row, Mapping) and row.get("id")
        ]
        if not device_types:
            device_types = ["MOBILE_PHONE"]
        os_families = [
            str(row.get("id"))
            for row in (device_taxonomy.get("os_families") or [])
            if isinstance(row, Mapping) and row.get("id")
        ]
        if not os_families:
            os_families = ["UNKNOWN"]
        ip_types = [
            str(row.get("id"))
            for row in (ip_taxonomy.get("ip_types") or [])
            if isinstance(row, Mapping) and row.get("id")
        ]
        if not ip_types:
            ip_types = ["RESIDENTIAL"]
        asn_classes = [
            str(row.get("id"))
            for row in (ip_taxonomy.get("asn_classes") or [])
            if isinstance(row, Mapping) and row.get("id")
        ]
        if not asn_classes:
            asn_classes = ["CONSUMER_ISP"]

        account_map = self._group_ids(account_df, "owner_party_id", "account_id")
        instrument_map = self._group_ids(instrument_df, "account_id", "instrument_id")

        device_rows: list[Mapping[str, object]] = []
        device_links: list[Mapping[str, object]] = []
        ip_rows: list[Mapping[str, object]] = []
        ip_links: list[Mapping[str, object]] = []

        device_id = 1
        ip_id = 1
        total_parties = party_df.height
        log_every = 5000
        log_interval = 120.0
        start_time = time.monotonic()
        last_log = start_time
        party_index = 0
        for party in party_df.iter_rows(named=True):
            party_index += 1
            party_id = int(party.get("party_id"))
            party_type = str(party.get("party_type"))
            segment_id = str(party.get("segment_id"))
            region_id = party.get("region_id")
            country_iso = party.get("country_iso")

            device_lambda = self._device_lambda(device_priors, party_type, segment_id, segment_profiles)
            max_devices = self._max_devices_per_party(linkage_rules)
            device_count = self._realised_count(inputs, party_id, "device", device_lambda, max_devices)
            if device_count <= 0:
                continue

            type_weights = self._device_type_weights(device_priors, party_type, device_types)
            os_weights = self._device_os_weights(device_priors, os_families)

            account_ids = account_map.get(party_id, [])
            for device_index in range(device_count):
                device_type = self._choose_weighted(
                    device_types,
                    type_weights,
                    inputs.manifest_fingerprint,
                    inputs.parameter_hash,
                    party_id,
                    device_index,
                    "device_type",
                )
                os_family = self._choose_weighted(
                    os_families,
                    os_weights,
                    inputs.manifest_fingerprint,
                    inputs.parameter_hash,
                    party_id,
                    device_index,
                    "os_family",
                )
                device_rows.append(
                    {
                        "device_id": device_id,
                        "device_type": device_type,
                        "os_family": os_family,
                        "primary_party_id": party_id,
                        "home_region_id": region_id,
                        "home_country_iso": country_iso,
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                        "seed": inputs.seed,
                    }
                )
                device_links.append(
                    {
                        "device_id": device_id,
                        "party_id": party_id,
                        "link_role": "PRIMARY_OWNER",
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                        "seed": inputs.seed,
                    }
                )
                if account_ids:
                    account_id = account_ids[device_index % len(account_ids)]
                    device_links.append(
                        {
                            "device_id": device_id,
                            "account_id": account_id,
                            "link_role": "ASSOCIATED_ACCOUNT",
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "seed": inputs.seed,
                        }
                    )
                    instrument_ids = instrument_map.get(account_id, [])
                    if instrument_ids:
                        instrument_id = instrument_ids[device_index % len(instrument_ids)]
                        device_links.append(
                            {
                                "device_id": device_id,
                                "instrument_id": instrument_id,
                                "link_role": "ASSOCIATED_INSTRUMENT",
                                "manifest_fingerprint": inputs.manifest_fingerprint,
                                "parameter_hash": inputs.parameter_hash,
                                "seed": inputs.seed,
                            }
                        )

                ip_count = self._ip_count(ip_priors, device_type)
                for ip_index in range(ip_count):
                    ip_type = self._choose_weighted(
                        ip_types,
                        normalise([1.0] * len(ip_types)),
                        inputs.manifest_fingerprint,
                        inputs.parameter_hash,
                        device_id,
                        ip_index,
                        "ip_type",
                    )
                    asn_class = self._choose_weighted(
                        asn_classes,
                        normalise([1.0] * len(asn_classes)),
                        inputs.manifest_fingerprint,
                        inputs.parameter_hash,
                        device_id,
                        ip_index,
                        "asn_class",
                    )
                    ip_rows.append(
                        {
                            "ip_id": ip_id,
                            "ip_type": ip_type,
                            "asn_class": asn_class,
                            "country_iso": country_iso,
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "seed": inputs.seed,
                        }
                    )
                    ip_links.append(
                        {
                            "ip_id": ip_id,
                            "device_id": device_id,
                            "party_id": party_id,
                            "link_role": "DEVICE_ENDPOINT",
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "seed": inputs.seed,
                        }
                    )
                    ip_id += 1

                device_id += 1
            now = time.monotonic()
            if party_index % log_every == 0 or (now - last_log) >= log_interval:
                elapsed = max(now - start_time, 0.0)
                rate = party_index / elapsed if elapsed > 0 else 0.0
                remaining = total_parties - party_index
                eta = remaining / rate if rate > 0 else 0.0
                logger.info(
                    "6A.S4 network build progress %s/%s parties devices=%s ips=%s elapsed=%.1fs rate=%.2f/s eta=%.1fs",
                    party_index,
                    total_parties,
                    device_id - 1,
                    ip_id - 1,
                    elapsed,
                    rate,
                    eta,
                )
                last_log = now

        device_df = pl.DataFrame(device_rows)
        ip_df = pl.DataFrame(ip_rows)
        device_links_df = pl.DataFrame(device_links)
        ip_links_df = pl.DataFrame(ip_links)

        device_base_path = self._write_dataset(
            device_df, inputs, dictionary, "s4_device_base_6A"
        )
        ip_base_path = self._write_dataset(ip_df, inputs, dictionary, "s4_ip_base_6A")
        device_links_path = self._write_dataset(
            device_links_df, inputs, dictionary, "s4_device_links_6A"
        )
        ip_links_path = self._write_dataset(ip_links_df, inputs, dictionary, "s4_ip_links_6A")

        neighbourhoods_path = None
        network_summary_path = None
        if device_df.height:
            neighbourhoods_path = self._write_dataset(
                self._build_neighbourhoods(device_links_df, ip_links_df),
                inputs,
                dictionary,
                "s4_entity_neighbourhoods_6A",
            )
        network_summary_path = self._write_dataset(
            self._build_summary(device_df, ip_df, device_links_df, ip_links_df),
            inputs,
            dictionary,
            "s4_network_summary_6A",
        )

        logger.info(
            "6A.S4 devices=%s ips=%s device_links=%s ip_links=%s",
            device_df.height,
            ip_df.height,
            device_links_df.height,
            ip_links_df.height,
        )

        return NetworkOutputs(
            device_base_path=device_base_path,
            ip_base_path=ip_base_path,
            device_links_path=device_links_path,
            ip_links_path=ip_links_path,
            neighbourhoods_path=neighbourhoods_path,
            network_summary_path=network_summary_path,
        )

    @staticmethod
    def _load_yaml(path: Path) -> Mapping[str, object]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"expected mapping in {path}")
        return payload

    def _load_optional_yaml(
        self,
        inventory: SealedInventory,
        dictionary: Mapping[str, object] | Sequence[object],
        sealed_df: pl.DataFrame,
        dataset_id: str,
    ) -> Mapping[str, object]:
        try:
            manifest_key = self._manifest_key_for(dataset_id, dictionary, sealed_df)
            paths = inventory.resolve_files(manifest_key=manifest_key)
        except Exception:
            return {}
        if not paths:
            return {}
        return self._load_yaml(paths[0])

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
                raise RuntimeError(f"6A.S4 upstream segment {segment} not PASS")

    @staticmethod
    def _device_lambda(
        priors: Mapping[str, object],
        party_type: str,
        segment_id: str,
        segment_profiles: Mapping[str, Mapping[str, object]],
    ) -> float:
        density = priors.get("density_model") or {}
        party_lambda = density.get("party_lambda") or {}
        base_lambda = float(party_lambda.get("base_lambda_by_party_type", {}).get(party_type, 0.0))
        tilt = party_lambda.get("segment_feature_tilt") or {}
        clip = float(tilt.get("clip_log_multiplier", 0.0) or 0.0)
        features = [str(feature) for feature in (tilt.get("features") or [])]
        weights_by_feature = tilt.get("weights_by_feature") or {}
        profile = segment_profiles.get(segment_id, {})
        log_multiplier = 0.0
        for feature in features:
            weight = float(weights_by_feature.get(feature, 0.0))
            score = float(profile.get(feature, 0.5))
            log_multiplier += weight * (score - 0.5)
        if clip > 0:
            log_multiplier = max(-clip, min(clip, log_multiplier))
        return max(0.0, base_lambda * math.exp(log_multiplier))

    @staticmethod
    def _max_devices_per_party(linkage_rules: Mapping[str, object]) -> int | None:
        constraints = linkage_rules.get("constraints") or {}
        max_devices = constraints.get("max_devices_per_party")
        if max_devices is None:
            return None
        try:
            value = int(max_devices)
        except (TypeError, ValueError):
            return None
        return max(0, value)

    def _realised_count(
        self,
        inputs: NetworkInputs,
        party_id: int,
        label: str,
        lambda_value: float,
        max_value: int | None,
    ) -> int:
        if lambda_value <= 0:
            return 0
        base = int(math.floor(lambda_value))
        frac = lambda_value - base
        if stable_uniform(
            inputs.manifest_fingerprint,
            inputs.parameter_hash,
            party_id,
            label,
        ) < frac:
            base += 1
        if max_value is not None:
            base = min(base, max_value)
        return max(0, base)

    @staticmethod
    def _device_type_weights(
        priors: Mapping[str, object], party_type: str, device_types: list[str]
    ) -> list[float]:
        mix = priors.get("type_mix_model") or {}
        base_pi = mix.get("base_pi_by_party_type") or {}
        entries = base_pi.get(party_type) or []
        weights = {str(row.get("device_type")): float(row.get("share", 0.0)) for row in entries if isinstance(row, Mapping)}
        return normalise([weights.get(device_type, 0.0) for device_type in device_types])

    @staticmethod
    def _device_os_weights(priors: Mapping[str, object], os_families: list[str]) -> list[float]:
        models = priors.get("attribute_models") or {}
        os_mix = models.get("os_family_mix") or {}
        weights = {str(row.get("os_family")): float(row.get("share", 0.0)) for row in os_mix if isinstance(row, Mapping)}
        if not weights:
            return normalise([1.0] * len(os_families))
        return normalise([weights.get(os_family, 0.0) for os_family in os_families])

    @staticmethod
    def _ip_count(priors: Mapping[str, object], device_type: str) -> int:
        ip_model = priors.get("device_lambda_model") or {}
        lambda_by_device = ip_model.get("lambda_by_device_type") or {}
        value = float(lambda_by_device.get(device_type, ip_model.get("default_lambda", 1.0)))
        return max(1, int(round(value)))

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
    def _group_ids(df: pl.DataFrame, key_col: str, id_col: str) -> dict[int, list[int]]:
        groups: dict[int, list[int]] = {}
        for row in df.select([key_col, id_col]).iter_rows(named=True):
            key = row.get(key_col)
            value = row.get(id_col)
            if key is None or value is None:
                continue
            groups.setdefault(int(key), []).append(int(value))
        return groups

    @staticmethod
    def _build_neighbourhoods(
        device_links: pl.DataFrame, ip_links: pl.DataFrame
    ) -> pl.DataFrame:
        if device_links.is_empty():
            return pl.DataFrame([])
        device_counts = (
            device_links.drop_nulls(["party_id"]).group_by("party_id").len().rename({"len": "device_count"})
        )
        ip_counts = (
            ip_links.drop_nulls(["party_id"]).group_by("party_id").len().rename({"len": "ip_count"})
        )
        return device_counts.join(ip_counts, on="party_id", how="outer").fill_null(0)

    @staticmethod
    def _build_summary(
        device_df: pl.DataFrame,
        ip_df: pl.DataFrame,
        device_links: pl.DataFrame,
        ip_links: pl.DataFrame,
    ) -> pl.DataFrame:
        return pl.DataFrame(
            [
                {
                    "devices_total": device_df.height,
                    "ips_total": ip_df.height,
                    "device_links_total": device_links.height,
                    "ip_links_total": ip_links.height,
                }
            ]
        )

    @staticmethod
    def _write_dataset(
        df: pl.DataFrame,
        inputs: NetworkInputs,
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
        inputs: NetworkInputs,
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


__all__ = ["NetworkRunner", "NetworkInputs", "NetworkOutputs"]
