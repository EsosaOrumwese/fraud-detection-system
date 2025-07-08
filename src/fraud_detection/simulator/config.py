"""
Configuration loader & schema for the fraud simulator.
"""

from __future__ import annotations
from pathlib import Path
from datetime import date
from typing import Optional, Literal, Dict

import yaml  # type: ignore
from pydantic import BaseModel, Field, model_validator, ValidationError, ConfigDict

class FeatureConfig(BaseModel):
    """Feature sampling parameters."""
    device_types: Dict[str, float] = Field( ..., description="Weights for device_type sampling")
    amount_distribution: Literal["lognormal","normal","uniform"] = Field(
        default="lognormal", description="Distribution for transaction amount"
    )
    lognormal_mean:  float = Field(3.0, ge=0, description="Mean for lognormal/normal")
    lognormal_sigma: float = Field(1.0, gt=0, description="Sigma for lognormal/normal")
    uniform_min:     float = Field(1.0, ge=0, description="Min for uniform distribution")
    uniform_max:     float = Field(500.0, gt=0, description="Max for uniform distribution")

    model_config = ConfigDict(extra="forbid")


class CatalogConfig(BaseModel):
    """Parameters for entity catalogs, Zipf exponents, and fraud-risk Beta priors."""

    num_customers: int = Field(..., gt=0, description="Total unique customers")
    customer_zipf_exponent: float = Field(1.2, gt=0, description="Zipf exponent for customers")

    num_merchants: int = Field(..., gt=0, description="Total unique merchants")
    merchant_zipf_exponent: float = Field(1.2, gt=0, description="Zipf exponent for merchants")
    merchant_risk_alpha: float = Field(2.0, gt=0, description="Alpha parameter for merchant-risk Beta")
    merchant_risk_beta: float = Field(5.0, gt=0, description="Beta  parameter for merchant-risk Beta")

    num_cards: int = Field(..., gt=0, description="Total unique cards")
    card_zipf_exponent: float = Field(1.0, gt=0, description="Zipf exponent for cards")
    card_risk_alpha: float = Field(2.0, gt=0, description="Alpha parameter for card-risk Beta")
    card_risk_beta: float = Field(5.0, gt=0, description="Beta  parameter for card-risk Beta")

    max_size_mb: int = Field(default=5, description="Maximum allowable file size (MB) for each Parquet catalog")
    parquet_row_group_size: int = Field(default=64_000_000,
                                        description="Row-group size (bytes) when writing Parquet for optimal chunking"
                                        )

    # Providing extra data is not permitted, and a ValidationError will be raised if this is the case
    model_config = ConfigDict(extra="forbid")


class TemporalConfig(BaseModel):
    """Temporal span and time-of-day distribution settings."""

    start_date: date = Field(..., description="Inclusive start date for simulated events")
    end_date: date = Field(..., description="Inclusive end date for simulated events")

    @model_validator(mode="after")
    def check_date_order(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    model_config = ConfigDict(extra="forbid")


class GeneratorConfig(BaseModel):
    """
    Master config for data generation.
    All parameters are validated before generation begins.
    """

    # core knobs
    total_rows: int = Field(1_000_000, gt=0, description="Number of transactions to generate")
    fraud_rate: float = Field(0.01, ge=0, le=1, description="Global fraud probability")
    seed: Optional[int] = Field(None, description="RNG seed for reproducibility")
    realism: Literal["v1","v2"] = Field(
        "v1",
        description="Sampling mode: 'v1'=legacy in-memory, 'v2'=Zipf catalogs on disk"
    )

    # performance knobs
    batch_size: int = Field(100_000, gt=0, description="Number of rows to generate in each batch (for chunked/streamed writes)")
    num_workers: int = Field(1, gt=0, description="Number of parallel worker processes/threads for generation")

    # entity catalogs
    catalog: CatalogConfig

    # temporal settings
    temporal: TemporalConfig

    # feature sampling parameters
    feature: FeatureConfig

    # output settings
    out_dir: Path = Field(Path("outputs"), description="Local output directory")
    s3_upload: bool = Field(False, description="Whether to upload to S3 after generation")

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
