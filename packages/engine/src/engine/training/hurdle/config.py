"""Configuration helpers for hurdle/dispersion simulation priors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, MutableMapping

import yaml


def _require_mapping(node: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(node, Mapping):
        raise ValueError(f"{label} must be a mapping, got {type(node)!r}")
    return node  # type: ignore[return-value]


def _cast_float(value: object, *, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number, got {value!r}") from exc


def _cast_int(value: object, *, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer, got {value!r}") from exc


@dataclass(frozen=True)
class RNGConfig:
    algorithm: str
    seed: int


@dataclass(frozen=True)
class HurdlePrior:
    base_logit: float
    bucket_offsets: Mapping[int, float]
    channel_offsets: Mapping[str, float]
    mcc_offsets: Mapping[int, float]

    def bucket_offset(self, bucket: int) -> float:
        return self.bucket_offsets.get(bucket, 0.0)

    def channel_offset(self, channel: str) -> float:
        return self.channel_offsets.get(channel, 0.0)

    def mcc_offset(self, mcc: int) -> float:
        return self.mcc_offsets.get(mcc, 0.0)


@dataclass(frozen=True)
class NBMeanPrior:
    base_log_mean: float
    channel_offsets: Mapping[str, float]
    mcc_offsets: Mapping[int, float]

    def channel_offset(self, channel: str) -> float:
        return self.channel_offsets.get(channel, 0.0)

    def mcc_offset(self, mcc: int) -> float:
        return self.mcc_offsets.get(mcc, 0.0)


@dataclass(frozen=True)
class DispersionPrior:
    base_log_phi: float
    gdp_log_slope: float
    channel_offsets: Mapping[str, float]
    mcc_offsets: Mapping[int, float]

    def channel_offset(self, channel: str) -> float:
        return self.channel_offsets.get(channel, 0.0)

    def mcc_offset(self, mcc: int) -> float:
        return self.mcc_offsets.get(mcc, 0.0)


@dataclass(frozen=True)
class SimulationConfig:
    semver: str
    version: str
    rng: RNGConfig
    hurdle: HurdlePrior
    nb_mean: NBMeanPrior
    dispersion: DispersionPrior

    @staticmethod
    def from_mapping(data: Mapping[str, object]) -> "SimulationConfig":
        semver = str(data.get("semver", "0.0.0"))
        version = str(data.get("version", "0.0.0"))

        rng_node = _require_mapping(data.get("rng"), label="rng")
        rng = RNGConfig(
            algorithm=str(rng_node.get("algorithm", "philox2x64-10")),
            seed=_cast_int(rng_node.get("seed"), label="rng.seed"),
        )

        hurdle = _parse_hurdle_prior(_require_mapping(data.get("hurdle"), label="hurdle"))
        nb_mean = _parse_nb_prior(_require_mapping(data.get("nb_mean"), label="nb_mean"))
        dispersion = _parse_dispersion_prior(
            _require_mapping(data.get("dispersion"), label="dispersion")
        )

        return SimulationConfig(
            semver=semver,
            version=version,
            rng=rng,
            hurdle=hurdle,
            nb_mean=nb_mean,
            dispersion=dispersion,
        )


def _parse_bucket_offsets(node: Mapping[str, object]) -> Mapping[int, float]:
    mapping: MutableMapping[int, float] = {}
    for key, value in node.items():
        bucket = _cast_int(key, label="bucket_offsets key")
        mapping[bucket] = _cast_float(value, label=f"bucket_offsets[{bucket}]")
    return dict(mapping)


def _parse_channel_offsets(node: Mapping[str, object], *, label: str) -> Mapping[str, float]:
    mapping: Dict[str, float] = {}
    for key, value in node.items():
        mapping[str(key)] = _cast_float(value, label=f"{label}[{key}]")
    return mapping


def _parse_mcc_offsets(node: Mapping[str, object], *, label: str) -> Mapping[int, float]:
    mapping: MutableMapping[int, float] = {}
    for key, value in node.items():
        mcc = _cast_int(key, label=f"{label} key")
        mapping[mcc] = _cast_float(value, label=f"{label}[{mcc}]")
    return dict(mapping)


def _parse_hurdle_prior(node: Mapping[str, object]) -> HurdlePrior:
    base_logit = _cast_float(node.get("base_logit"), label="hurdle.base_logit")

    bucket_node = _require_mapping(node.get("bucket_offsets", {}), label="hurdle.bucket_offsets")
    channel_node = _require_mapping(
        node.get("channel_offsets", {}),
        label="hurdle.channel_offsets",
    )
    mcc_node = _require_mapping(node.get("mcc_offsets", {}), label="hurdle.mcc_offsets")

    return HurdlePrior(
        base_logit=base_logit,
        bucket_offsets=_parse_bucket_offsets(bucket_node),
        channel_offsets=_parse_channel_offsets(channel_node, label="hurdle.channel_offsets"),
        mcc_offsets=_parse_mcc_offsets(mcc_node, label="hurdle.mcc_offsets"),
    )


def _parse_nb_prior(node: Mapping[str, object]) -> NBMeanPrior:
    base_log_mean = _cast_float(node.get("base_log_mean"), label="nb_mean.base_log_mean")
    channel_node = _require_mapping(node.get("channel_offsets", {}), label="nb_mean.channel_offsets")
    mcc_node = _require_mapping(node.get("mcc_offsets", {}), label="nb_mean.mcc_offsets")
    return NBMeanPrior(
        base_log_mean=base_log_mean,
        channel_offsets=_parse_channel_offsets(channel_node, label="nb_mean.channel_offsets"),
        mcc_offsets=_parse_mcc_offsets(mcc_node, label="nb_mean.mcc_offsets"),
    )


def _parse_dispersion_prior(node: Mapping[str, object]) -> DispersionPrior:
    base_log_phi = _cast_float(node.get("base_log_phi"), label="dispersion.base_log_phi")
    gdp_log_slope = _cast_float(node.get("gdp_log_slope"), label="dispersion.gdp_log_slope")
    channel_node = _require_mapping(
        node.get("channel_offsets", {}),
        label="dispersion.channel_offsets",
    )
    mcc_node = _require_mapping(node.get("mcc_offsets", {}), label="dispersion.mcc_offsets")
    return DispersionPrior(
        base_log_phi=base_log_phi,
        gdp_log_slope=gdp_log_slope,
        channel_offsets=_parse_channel_offsets(channel_node, label="dispersion.channel_offsets"),
        mcc_offsets=_parse_mcc_offsets(mcc_node, label="dispersion.mcc_offsets"),
    )


def load_simulation_config(path: Path) -> SimulationConfig:
    """Load and validate the hurdle simulation config from ``path``."""
    if not path.exists():
        raise FileNotFoundError(f"simulation config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    node = _require_mapping(data, label="root")
    return SimulationConfig.from_mapping(node)
