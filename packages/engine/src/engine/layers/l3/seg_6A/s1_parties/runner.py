"""Segment 6A S1 party base runner."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import polars as pl
import yaml

from engine.layers.l3.seg_6A.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l3.seg_6A.shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path, repository_root
from engine.layers.l3.shared.deterministic import largest_remainder, normalise

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PartyInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class PartyOutputs:
    party_base_path: Path
    party_summary_path: Path | None


class PartyRunner:
    """Builds the 6A.S1 party base."""

    def run(self, inputs: PartyInputs) -> PartyOutputs:
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

        population_priors = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_population_6A", dictionary, sealed_df)
            )[0]
        )
        segmentation_priors = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("prior_segmentation_6A", dictionary, sealed_df)
            )[0]
        )
        party_taxonomy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("taxonomy_party_6A", dictionary, sealed_df)
            )[0]
        )

        outlet_counts = self._load_country_counts(
            inventory, dictionary, sealed_df, "outlet_catalogue_1A", inputs
        )
        arrival_counts = self._load_country_counts(
            inventory, dictionary, sealed_df, "merchant_zone_profile_5A", inputs
        )
        self._assert_required_hints(population_priors, outlet_counts, arrival_counts)

        world_target = self._compute_world_target(population_priors, outlet_counts, arrival_counts)
        countries = sorted(outlet_counts.keys()) if outlet_counts else []
        if not countries:
            countries = ["US"]
            outlet_counts = {"US": 1.0}
        weights = self._compute_country_weights(population_priors, outlet_counts, arrival_counts, countries)

        region_map = self._assign_regions(segmentation_priors, countries)
        region_weights = self._region_weights(weights, region_map)

        cell_counts = self._allocate_party_cells(
            population_priors,
            segmentation_priors,
            countries,
            weights,
            region_map,
            region_weights,
            int(round(world_target)),
        )

        party_rows = []
        party_id = 1
        for (country_iso, party_type, segment_id, region_id), count in cell_counts.items():
            for _ in range(count):
                party_rows.append(
                    {
                        "party_id": party_id,
                        "party_type": party_type,
                        "segment_id": segment_id,
                        "region_id": region_id,
                        "country_iso": country_iso,
                        "seed": inputs.seed,
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                    }
                )
                party_id += 1

        party_df = pl.DataFrame(party_rows)
        party_base_path = inputs.data_root / render_dataset_path(
            dataset_id="s1_party_base_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        party_base_path.parent.mkdir(parents=True, exist_ok=True)
        party_df.write_parquet(party_base_path)

        summary_df = (
            party_df.group_by(["country_iso", "region_id", "party_type", "segment_id"])
            .len()
            .rename({"len": "party_count"})
        )
        summary_path = inputs.data_root / render_dataset_path(
            dataset_id="s1_party_summary_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.write_parquet(summary_path)

        logger.info("6A.S1 party base rows=%s", len(party_rows))

        return PartyOutputs(party_base_path=party_base_path, party_summary_path=summary_path)

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

    def _load_country_counts(
        self,
        inventory: SealedInventory,
        dictionary: Mapping[str, object] | Sequence[object],
        sealed_df: pl.DataFrame,
        dataset_id: str,
        inputs: PartyInputs,
    ) -> Mapping[str, float]:
        try:
            manifest_key = self._manifest_key_for(dataset_id, dictionary, sealed_df)
            files = inventory.resolve_files(manifest_key=manifest_key)
        except Exception:
            return {}
        if not files:
            return {}
        df = pl.scan_parquet([file.as_posix() for file in files]).collect()
        for col in ("legal_country_iso", "country_iso", "home_country_iso"):
            if col in df.columns:
                counts = df.group_by(col).len().rename({"len": "count"}).to_dicts()
                return {row[col]: float(row["count"]) for row in counts}
        return {}

    def _compute_world_target(
        self,
        priors: Mapping[str, object],
        outlet_counts: Mapping[str, float],
        arrival_counts: Mapping[str, float],
    ) -> float:
        model = priors.get("world_size_model") or {}
        mode = str(model.get("mode") or "outlets_based_v1")
        n_min = float(model.get("N_world_min", 1))
        n_max = float(model.get("N_world_max", max(n_min, 1)))
        if mode == "arrivals_based_v1" and arrival_counts:
            arrivals = sum(arrival_counts.values())
            per_party = float(model.get("arrivals_per_active_party_per_week", 1.0))
            active_fraction = float(model.get("active_fraction", 1.0))
            target = arrivals / max(per_party, 1e-12) / max(active_fraction, 1e-12)
        else:
            outlets = sum(outlet_counts.values()) or 1.0
            parties_per_outlet = float(model.get("parties_per_outlet", 10.0))
            target = outlets * parties_per_outlet
        return max(n_min, min(n_max, target))

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6A missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6A.S1 upstream segment {segment} not PASS")

    @staticmethod
    def _assert_required_hints(
        priors: Mapping[str, object],
        outlet_counts: Mapping[str, float],
        arrival_counts: Mapping[str, float],
    ) -> None:
        inputs_allowed = priors.get("inputs_allowed") or {}
        required = set(inputs_allowed.get("required_hints") or [])
        if "OUTLET_COUNTS_BY_COUNTRY" in required and not outlet_counts:
            raise RuntimeError("population_priors_6A requires outlet counts but none were resolved")
        if "EXPECTED_ARRIVALS_BY_COUNTRY" in required and not arrival_counts:
            raise RuntimeError("population_priors_6A requires arrivals counts but none were resolved")

    def _compute_country_weights(
        self,
        priors: Mapping[str, object],
        outlet_counts: Mapping[str, float],
        arrival_counts: Mapping[str, float],
        countries: list[str],
    ) -> Mapping[str, float]:
        model = priors.get("country_weight_model") or {}
        use_outlets = bool(model.get("use_outlets", True))
        use_arrivals = bool(model.get("use_arrivals", bool(arrival_counts)))
        outlet_offset = float(model.get("outlet_offset", 0.0))
        outlet_exp = float(model.get("outlet_exponent", 1.0))
        arrival_offset = float(model.get("arrival_offset", 0.0))
        arrival_exp = float(model.get("arrival_exponent", 1.0))
        floor = float(model.get("country_weight_floor", 1e-6))

        weights = {}
        for country in countries:
            weight = 1.0
            if use_outlets:
                weight *= (outlet_counts.get(country, 0.0) + outlet_offset) ** outlet_exp
            if use_arrivals and arrival_counts:
                weight *= (arrival_counts.get(country, 0.0) + arrival_offset) ** arrival_exp
            weights[country] = max(weight, floor)
        normed = normalise(weights.values())
        return {country: normed[idx] for idx, country in enumerate(countries)}

    def _assign_regions(
        self, segmentation_priors: Mapping[str, object], countries: list[str]
    ) -> Mapping[str, str]:
        region_rows = segmentation_priors.get("region_party_type_mix") or []
        region_ids = [str(row.get("region_id")) for row in region_rows if isinstance(row, Mapping)]
        region_ids = [region for region in region_ids if region]
        if not region_ids:
            region_ids = ["REGION_1"]
        region_ids = sorted(set(region_ids))
        return {country: region_ids[idx % len(region_ids)] for idx, country in enumerate(sorted(countries))}

    def _region_weights(self, weights: Mapping[str, float], region_map: Mapping[str, str]) -> Mapping[str, float]:
        totals: dict[str, float] = {}
        for country, region_id in region_map.items():
            totals[region_id] = totals.get(region_id, 0.0) + weights.get(country, 0.0)
        return totals

    def _allocate_party_cells(
        self,
        population_priors: Mapping[str, object],
        segmentation_priors: Mapping[str, object],
        countries: list[str],
        weights: Mapping[str, float],
        region_map: Mapping[str, str],
        region_weights: Mapping[str, float],
        total_target: int,
    ) -> Mapping[tuple[str, str, str, str], int]:
        party_type_model = population_priors.get("party_type_model") or {}
        base_shares = party_type_model.get("base_shares") or {}
        party_types = party_type_model.get("party_types") or ["RETAIL", "BUSINESS", "OTHER"]
        party_types = [str(t) for t in party_types]

        region_party_mix = {
            str(row.get("region_id")): row.get("pi_type")
            for row in (segmentation_priors.get("region_party_type_mix") or [])
            if isinstance(row, Mapping)
        }
        region_segment_mix: dict[tuple[str, str], list[Mapping[str, object]]] = {}
        for row in segmentation_priors.get("region_type_segment_mix") or []:
            if not isinstance(row, Mapping):
                continue
            region_id = str(row.get("region_id"))
            party_type = str(row.get("party_type"))
            region_segment_mix[(region_id, party_type)] = row.get("pi_segment") or []

        cell_counts: dict[tuple[str, str, str, str], int] = {}
        for region_id, region_weight in region_weights.items():
            countries_in_region = [c for c in countries if region_map.get(c) == region_id]
            region_total = max(0, int(round(total_target * region_weight)))
            for party_type in party_types:
                mix = region_party_mix.get(region_id) or {}
                type_share = float(mix.get(party_type, base_shares.get(party_type, 1.0 / len(party_types))))
                type_total = max(0, int(round(region_total * type_share)))
                segment_rows = region_segment_mix.get((region_id, party_type)) or []
                segment_shares = {
                    str(item.get("segment_id")): float(item.get("share", 0.0))
                    for item in segment_rows
                    if isinstance(item, Mapping)
                }
                if not segment_shares:
                    segment_shares = {"SEGMENT_1": 1.0}
                seg_ids = list(segment_shares.keys())
                seg_weights = normalise(segment_shares.values())
                seg_counts = largest_remainder(seg_weights, type_total)
                for seg_id, seg_count in zip(seg_ids, seg_counts):
                    country_weights = [weights.get(country, 0.0) for country in countries_in_region]
                    alloc = largest_remainder(country_weights, seg_count)
                    for country, count in zip(countries_in_region, alloc):
                        key = (country, party_type, seg_id, region_id)
                        cell_counts[key] = cell_counts.get(key, 0) + count
        return cell_counts


__all__ = ["PartyRunner", "PartyInputs", "PartyOutputs"]
