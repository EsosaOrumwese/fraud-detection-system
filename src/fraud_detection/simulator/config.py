"""
Configuration loader & schema for the fraud simulator.
"""

from __future__ import annotations
from pathlib import Path
from datetime import date
from typing import Optional

import yaml  # type: ignore
from pydantic import BaseModel, Field, model_validator, ValidationError


class CatalogConfig(BaseModel):
    """Parameters for entity catalogs and Zipf exponents."""

    num_customers: int = Field(..., gt=0, description="Total unique customers")
    customer_zipf_exponent: float = Field(
        1.2, gt=0, description="Zipf exponent for customers"
    )
    num_merchants: int = Field(..., gt=0, description="Total unique merchants")
    merchant_zipf_exponent: float = Field(
        1.2, gt=0, description="Zipf exponent for merchants"
    )
    num_cards: int = Field(..., gt=0, description="Total unique cards")
    card_zipf_exponent: float = Field(1.0, gt=0, description="Zipf exponent for cards")

    # Providing extra data is not permitted, and a ValidationError will be raised if this is the case
    model_config = dict(extra="forbid")


class TemporalConfig(BaseModel):
    """Temporal span and time-of-day distribution settings."""

    start_date: date = Field(
        ..., description="Inclusive start date for simulated events"
    )
    end_date: date = Field(..., description="Inclusive end date for simulated events")

    @model_validator(mode="after")
    def check_date_order(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    model_config = dict(extra="forbid")


class GeneratorConfig(BaseModel):
    """
    Master config for data generation.
    All parameters are validated before generation begins.
    """

    # core knobs
    total_rows: int = Field(
        1_000_000, gt=0, description="Number of transactions to generate"
    )
    fraud_rate: float = Field(0.01, ge=0, le=1, description="Global fraud probability")
    seed: Optional[int] = Field(None, description="RNG seed for reproducibility")

    # entity catalogs
    catalog: CatalogConfig

    # temporal settings
    temporal: TemporalConfig

    # output settings
    out_dir: Path = Field(Path("outputs"), description="Local output directory")
    s3_upload: bool = Field(
        False, description="Whether to upload to S3 after generation"
    )

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
        return self

    model_config = dict(extra="forbid")


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
