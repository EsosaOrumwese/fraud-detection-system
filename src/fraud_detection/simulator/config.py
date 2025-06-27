from pydantic import BaseModel, Field
from pathlib import Path
from datetime import date
from typing import Optional

class GeneratorConfig(BaseModel):
    seed: int = Field(42, description="RNG seed for reproducibility")
    rows: int = Field(1_000_000, gt=0, description="Total number of transactions to generate")
    chunk_size: int = Field(100_000, gt=0, description="Number of rows per write batch")
    fraud_rate: float = Field(0.003, ge=0, le=1, description="Global fraud probability")
    num_customers: int = Field(100_000, gt=0, description="Unique customers in catalog")
    num_merchants: int = Field(10_000, gt=0, description="Unique merchants in catalog")
    num_cards: int = Field(200_000, gt=0, description="Unique cards in catalog")
    start_date: date = Field(default_factory=date.today, description="Date for transaction timestamps")
    output_dir: Path = Field(Path("outputs"), description="Local FS dir for Parquet files")
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name for upload (optional)")
