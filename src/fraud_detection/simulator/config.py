"""
Configuration loader & schema for the fraud simulator.
"""

from __future__ import annotations
from pathlib import Path
from datetime import date
from typing import Optional, Literal, Dict, List

import yaml  # type: ignore
from pydantic import BaseModel, Field, model_validator, ValidationError, ConfigDict


class FeatureConfig(BaseModel):
    """Feature sampling parameters."""

    device_types: Dict[str, float] = Field(
        ..., description="Weights for device_type sampling"
    )
    amount_distribution: Literal["lognormal", "normal", "uniform"] = Field(
        default="lognormal", description="Distribution for transaction amount"
    )
    lognormal_mean: float = Field(3.0, ge=0, description="Mean for lognormal/normal")
    lognormal_sigma: float = Field(1.0, gt=0, description="Sigma for lognormal/normal")
    uniform_min: float = Field(1.0, ge=0, description="Min for uniform distribution")
    uniform_max: float = Field(500.0, gt=0, description="Max for uniform distribution")

    model_config = ConfigDict(extra="forbid")


class CatalogConfig(BaseModel):
    """Parameters for entity catalogs, Zipf exponents, and fraud-risk Beta priors."""

    num_customers: int = Field(..., gt=0, description="Total unique customers")
    customer_zipf_exponent: float = Field(
        1.2, gt=0, description="Zipf exponent for customers"
    )

    num_merchants: int = Field(..., gt=0, description="Total unique merchants")
    merchant_zipf_exponent: float = Field(
        1.2, gt=0, description="Zipf exponent for merchants"
    )
    merchant_risk_alpha: float = Field(
        2.0, gt=0, description="Alpha parameter for merchant-risk Beta"
    )
    merchant_risk_beta: float = Field(
        5.0, gt=0, description="Beta  parameter for merchant-risk Beta"
    )

    num_cards: int = Field(..., gt=0, description="Total unique cards")
    card_zipf_exponent: float = Field(1.0, gt=0, description="Zipf exponent for cards")
    card_risk_alpha: float = Field(
        2.0, gt=0, description="Alpha parameter for card-risk Beta"
    )
    card_risk_beta: float = Field(
        5.0, gt=0, description="Beta  parameter for card-risk Beta"
    )

    max_size_mb: int = Field(
        default=5,
        description="Maximum allowable file size (MB) for each Parquet catalog",
    )
    parquet_row_group_size: int = Field(
        default=64_000_000,
        description="Row-group size (bytes) when writing Parquet for optimal chunking",
    )

    # Providing extra data is not permitted, and a ValidationError will be raised if this is the case
    model_config = ConfigDict(extra="forbid")


# new time‐of‐day component schema
class TimeComponentConfig(BaseModel):
    mean_hour: float = Field(..., ge=0, lt=24, description="Center hour of the Gaussian peak")
    std_hours: float = Field(..., gt=0, description="Std dev in hours for the peak")
    weight: float = Field(..., ge=0, description="Relative weight of this component")

    model_config = ConfigDict(extra="forbid")


class TemporalConfig(BaseModel):
    """Temporal span and time-of-day distribution settings."""

    start_date: date = Field(
        ..., description="Inclusive start date for simulated events"
    )
    end_date: date = Field(..., description="Inclusive end date for simulated events")

    # SD-02 fields
    weekday_weights: Optional[Dict[int, float]] = Field(
        None, description="Map weekday (0=Mon … 6=Sun) to relative weight"
    )
    time_components: Optional[List[TimeComponentConfig]] = Field(
        None, description="List of Gaussian components for time-of-day"
    )
    distribution_type: Literal["gaussian"] = Field(
        "gaussian", description="Which TemporalDistribution to use"
    )
    timezone: str = Field(
        "UTC",
        description="IANA timezone name for sampling (e.g. 'UTC', 'Europe/London')"
    )
    chunk_size: Optional[int] = Field(
        None, ge=1, description="Max rows per internal sampling batch"
    )

    @model_validator(mode="after")
    def check_date_order(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    @model_validator(mode="after")
    def validate_and_normalize(self):
        # weekday_weights
        ww = self.weekday_weights
        if ww is not None:
            for k, v in ww.items():
                if k not in range(0, 7):
                    raise ValueError(f"Invalid weekday key {k!r}; must be 0–6")
                if v < 0:
                    raise ValueError(f"Negative weight for weekday {k!r}")
            total = sum(ww.values())
            if total <= 0:
                raise ValueError("Sum of weekday_weights must be > 0")
            normalized = {k: v / total for k, v in ww.items()}
            object.__setattr__(self, "weekday_weights", normalized)

        # time_components
        tcs = self.time_components
        if tcs is not None:
            total_w = sum(tc.weight for tc in tcs)
            if total_w <= 0:
                raise ValueError("Sum of time_components weights must be > 0")
            for tc in tcs:
                tc.weight /= total_w
            object.__setattr__(self, "time_components", tcs)

        # chunk_size
        cs = self.chunk_size
        if cs is not None and cs < 1:
            raise ValueError("chunk_size must be ≥ 1")

        return self

    model_config = ConfigDict(extra="forbid")


class GeneratorConfig(BaseModel):
    """
    Configuration for the fraud-data generator.

    Attributes:
      total_rows (int): Total number of transactions to generate.
      fraud_rate (float): Target fraction of fraudulent transactions.
      seed (Optional[int]): RNG seed for reproducibility.
      batch_size (int): Number of rows per chunk when writing in parallel.
      num_workers (int): Number of parallel worker processes.
      out_dir (Path): Local directory to write outputs.
      realism (Literal["v1","v2"]):
          "v1" = rebuild catalogs each chunk;
          "v2" = pre-load catalogs once and reuse.
      catalog (CatalogConfig): Nested settings for customer/merchant/card catalogs.
      temporal (TemporalConfig): Settings for timestamp sampling.
      feature (FeatureConfig): Settings for amount, device, geo distributions.
    """

    # core knobs
    total_rows: int = Field(
        1_000_000, gt=0, description="Number of transactions to generate"
    )
    fraud_rate: float = Field(0.01, ge=0, le=1, description="Global fraud probability")
    seed: Optional[int] = Field(None, description="RNG seed for reproducibility")
    realism: Literal["v1", "v2"] = Field(
        "v1",
        description="Sampling mode: 'v1'=legacy in-memory, 'v2'=Zipf catalogs on disk",
    )

    # performance knobs
    batch_size: int = Field(
        100_000,
        gt=0,
        description="Number of rows to generate in each batch (for chunked/streamed writes)",
    )
    num_workers: int = Field(
        1,
        gt=0,
        description="Number of parallel worker processes/threads for generation",
    )

    # entity catalogs
    catalog: CatalogConfig

    # temporal settings
    temporal: TemporalConfig

    # feature sampling parameters
    feature: FeatureConfig

    # output settings
    out_dir: Path = Field(Path("outputs"), description="Local output directory")
    s3_upload: bool = Field(
        False, description="Whether to upload to S3 after generation"
    )

    @model_validator(mode="before")
    def ensure_sections_present(cls, values):
        # values is the raw dict from YAML
        if "catalog" not in values:
            raise ValueError("Missing required `catalog` section")
        if "temporal" not in values:
            raise ValueError("Missing required `temporal` section")
        if "feature" not in values:
            raise ValueError("Missing required `feature` section")
        return values

    @model_validator(mode="before")
    def convert_paths(cls, values):
        # Ensure out_dir is a Path if provided as str
        od = values.get("out_dir")
        if isinstance(od, str):
            values["out_dir"] = Path(od)
        return values

    @model_validator(mode="after")
    def check_sections_present(self):
        # Ensure nested blocks aren’t missing
        if self.catalog is None:
            raise ValueError("Missing required `catalog` section")
        if self.temporal is None:
            raise ValueError("Missing required `temporal` section")
        if self.feature is None:
            raise ValueError("Missing required `feature` section")
        return self

    @model_validator(mode="before")
    def set_default_chunk_size(cls, values):
        """
        Stage 1 polish: ensure temporal.chunk_size always defaults to batch_size
        so downstream logic can assume it's an int (never None).
        """
        # Only apply if the user didn't explicitly set chunk_size in YAML/CLI
        batch = values.get("batch_size")
        temp  = values.get("temporal")
        if batch is not None and isinstance(temp, dict):
            # Only fill when missing or null
            if temp.get("chunk_size") is None:
                temp["chunk_size"] = batch
                values["temporal"] = temp
        return values

    model_config = ConfigDict(extra="forbid")


def load_config(path: Path) -> GeneratorConfig:
    """
    Load and validate a GeneratorConfig from a YAML file.

    Parameters
    ----------
    path : Path
        Path to a YAML config file following the template below.

    Returns
    -------
    GeneratorConfig
        Validated config object.

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    ValidationError
        If any field is missing or invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    data = yaml.safe_load(path.read_text())
    try:
        return GeneratorConfig.model_validate(data)
    except ValidationError as e:
        # Re-raise with a clearer prefix
        raise ValueError(f"Error parsing config '{path}':\n{e}") from e
