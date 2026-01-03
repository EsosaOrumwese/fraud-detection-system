"""Segment 5B S3 bucket count runner."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl
import yaml

from engine.layers.l1.seg_1A.s0_foundations.l2.rng_logging import RNGLogWriter
from engine.layers.l2.seg_5B.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l2.seg_5B.shared.dictionary import load_dictionary, render_dataset_path, repository_root
from engine.layers.l2.seg_5B.shared.rng import derive_event, gamma_one_u_approx, poisson_one_u
from engine.layers.l2.seg_5B.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CountInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class CountResult:
    count_paths: dict[str, Path]
    run_report_path: Path


class CountRunner:
    """Convert realised intensities into bucket counts."""

    def run(self, inputs: CountInputs) -> CountResult:
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
        count_policy = _load_yaml(inventory, "arrival_count_config_5B")
        rng_logger = RNGLogWriter(
            base_path=data_root,
            seed=inputs.seed,
            parameter_hash=inputs.parameter_hash,
            manifest_fingerprint=inputs.manifest_fingerprint,
            run_id=inputs.run_id,
        )

        count_paths: dict[str, Path] = {}
        logger.info("5B.S3 bucket counts start scenarios=%s", len(scenarios))
        for scenario in scenarios:
            logger.info("5B.S3 scenario start scenario_id=%s", scenario.scenario_id)
            intensity_path = data_root / render_dataset_path(
                dataset_id="s2_realised_intensity_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
                },
                dictionary=dictionary,
            )
            grouping_path = data_root / render_dataset_path(
                dataset_id="s1_grouping_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                },
                dictionary=dictionary,
            )
            if not intensity_path.exists():
                raise FileNotFoundError(f"s2_realised_intensity_5B missing at {intensity_path}")
            if not grouping_path.exists():
                raise FileNotFoundError(f"s1_grouping_5B missing at {grouping_path}")

            intensity_df = pl.read_parquet(intensity_path)
            grouping_df = pl.read_parquet(grouping_path)
            intensity_df = intensity_df.join(
                grouping_df.select(
                    [
                        "merchant_id",
                        "zone_representation",
                        "channel_group",
                        "group_id",
                        "scenario_band",
                        "demand_class",
                        "virtual_band",
                    ]
                ),
                on=["merchant_id", "zone_representation", "channel_group"],
                how="left",
            )
            if intensity_df["group_id"].null_count() > 0:
                raise ValueError("group_id missing for some intensity rows")

            missing_classes = _missing_classes(intensity_df, count_policy)
            if missing_classes:
                raise ValueError(f"arrival_count_config_5B missing class multipliers for {missing_classes}")

            rows = []
            sorted_df = intensity_df.sort(["merchant_id", "zone_representation", "bucket_index"])
            total_rows = sorted_df.height
            log_every = 50000
            log_interval = 120.0
            last_log = time.monotonic()
            row_index = 0
            for row in sorted_df.iter_rows(named=True):
                row_index += 1
                lam = float(row.get("lambda_realised") or 0.0)
                count = _draw_count(
                    count_policy,
                    rng_logger=rng_logger,
                    manifest_fingerprint=inputs.manifest_fingerprint,
                    parameter_hash=inputs.parameter_hash,
                    seed=inputs.seed,
                    scenario_id=scenario.scenario_id,
                    merchant_id=str(row.get("merchant_id")),
                    zone_rep=str(row.get("zone_representation")),
                    bucket_index=int(row.get("bucket_index")),
                    lambda_value=lam,
                    scenario_band=str(row.get("scenario_band")),
                    demand_class=str(row.get("demand_class")),
                )
                rows.append(
                    {
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                        "seed": inputs.seed,
                        "scenario_id": scenario.scenario_id,
                        "merchant_id": row.get("merchant_id"),
                        "zone_representation": row.get("zone_representation"),
                        "channel_group": row.get("channel_group"),
                        "bucket_index": row.get("bucket_index"),
                        "count_N": int(count),
                        "s3_spec_version": "1.0.0",
                    }
                )
                now = time.monotonic()
                if row_index % log_every == 0 or (now - last_log) >= log_interval:
                    logger.info(
                        "5B.S3 progress %s/%s rows (scenario_id=%s)",
                        row_index,
                        total_rows,
                        scenario.scenario_id,
                    )
                    last_log = now

            count_df = pl.DataFrame(rows)
            count_path = _write_dataset(
                data_root,
                dictionary,
                dataset_id="s3_bucket_counts_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
                },
                df=count_df.sort(["merchant_id", "zone_representation", "bucket_index"]),
            )
            count_paths[scenario.scenario_id] = count_path

        run_report_path = _write_run_report(inputs, data_root, dictionary)
        return CountResult(count_paths=count_paths, run_report_path=run_report_path)


def _load_yaml(inventory: SealedInventory, artifact_id: str) -> Mapping[str, object]:
    files = inventory.resolve_files(artifact_id)
    if not files:
        raise FileNotFoundError(f"{artifact_id} missing from sealed inputs")
    return yaml.safe_load(files[0].read_text(encoding="utf-8")) or {}


def _missing_classes(df: pl.DataFrame, cfg: Mapping[str, object]) -> list[str]:
    count_law = str(cfg.get("count_law_id", "poisson"))
    if count_law != "nb2":
        return []
    class_mult = cfg.get("nb2", {}).get("kappa_law", {}).get("class_multipliers", {}) or {}
    classes = {str(value) for value in df.get_column("demand_class").unique().to_list()}
    return sorted([value for value in classes if value not in class_mult])


def _draw_count(
    cfg: Mapping[str, object],
    *,
    rng_logger: RNGLogWriter,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
    merchant_id: str,
    zone_rep: str,
    bucket_index: int,
    lambda_value: float,
    scenario_band: str,
    demand_class: str,
) -> int:
    lambda_zero_eps = float(cfg.get("lambda_zero_eps", 1e-6))
    if lambda_value <= lambda_zero_eps:
        return 0
    count_law = str(cfg.get("count_law_id", "poisson"))
    domain_key = f"merchant_id={merchant_id}|zone={zone_rep}|bucket_index={bucket_index}"
    if count_law == "poisson":
        event = derive_event(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
            scenario_id=scenario_id,
            family_id="S3.bucket_count.v1",
            domain_key=domain_key,
            draws=1,
        )
        rng_logger.log_event(
            family="S3.bucket_count.v1",
            module="5B.S3",
            substream_label="bucket_count",
            event="rng_event_bucket_count",
            counter_before=event.before_state(),
            counter_after=event.after_state(),
            blocks=event.blocks,
            draws=event.draws,
            payload={
                "scenario_id": scenario_id,
                "domain_key": domain_key,
            },
        )
        u = event.uniforms()[0]
        sampler = cfg.get("poisson_sampler", {}) or {}
        return poisson_one_u(
            u=u,
            lam=lambda_value,
            lam_exact_max=float(sampler.get("poisson_exact_lambda_max", 50.0)),
            n_cap_exact=int(sampler.get("poisson_n_cap_exact", 200000)),
            max_count=int(cfg.get("max_count_per_bucket", 200000)),
        )
    if count_law != "nb2":
        raise ValueError("unsupported count_law_id")

    nb2_cfg = cfg.get("nb2", {}) or {}
    kappa_cfg = nb2_cfg.get("kappa_law", {}) or {}
    base_by_band = kappa_cfg.get("base_by_scenario_band", {}) or {}
    class_mult = kappa_cfg.get("class_multipliers", {}) or {}
    bounds = kappa_cfg.get("kappa_bounds", [2.0, 200.0])
    kappa = float(base_by_band.get(scenario_band, base_by_band.get("baseline", 30.0)))
    kappa *= float(class_mult.get(demand_class, 1.0))
    kappa = max(float(bounds[0]), min(float(bounds[1]), kappa))

    event = derive_event(
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        seed=seed,
        scenario_id=scenario_id,
        family_id="S3.bucket_count.v1",
        domain_key=domain_key,
        draws=2,
    )
    rng_logger.log_event(
        family="S3.bucket_count.v1",
        module="5B.S3",
        substream_label="bucket_count",
        event="rng_event_bucket_count",
        counter_before=event.before_state(),
        counter_after=event.after_state(),
        blocks=event.blocks,
        draws=event.draws,
        payload={
            "scenario_id": scenario_id,
            "domain_key": domain_key,
        },
    )
    u1, u2 = event.uniforms()
    lambda_gamma = gamma_one_u_approx(lambda_value, kappa, u1)
    sampler = cfg.get("poisson_sampler", {}) or {}
    return poisson_one_u(
        u=u2,
        lam=lambda_gamma,
        lam_exact_max=float(sampler.get("poisson_exact_lambda_max", 50.0)),
        n_cap_exact=int(sampler.get("poisson_n_cap_exact", 200000)),
        max_count=int(cfg.get("max_count_per_bucket", 200000)),
    )


def _write_dataset(
    data_root: Path,
    dictionary: Mapping[str, object],
    *,
    dataset_id: str,
    template_args: Mapping[str, object],
    df: pl.DataFrame,
) -> Path:
    path_template = render_dataset_path(dataset_id=dataset_id, template_args=template_args, dictionary=dictionary)
    output_path = data_root / path_template
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path)
    return output_path


def _write_run_report(
    inputs: CountInputs,
    data_root: Path,
    dictionary: Mapping[str, object],
) -> Path:
    path = data_root / render_dataset_path(
        dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
    )
    payload = {
        "layer": "layer2",
        "segment": "5B",
        "state": "S3",
        "parameter_hash": inputs.parameter_hash,
        "manifest_fingerprint": inputs.manifest_fingerprint,
        "run_id": inputs.run_id,
        "status": "PASS",
    }
    key = SegmentStateKey(
        layer="layer2",
        segment="5B",
        state="S3",
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        run_id=inputs.run_id,
    )
    return write_segment_state_run_report(path=path, key=key, payload=payload)


__all__ = ["CountInputs", "CountResult", "CountRunner"]
