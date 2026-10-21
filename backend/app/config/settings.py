from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration; business thresholds remain explicit and overridable."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="BOTTLENECK_",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'bottleneck.db'}"
    data_dir: Path = PROJECT_ROOT / "data"
    simulation_date: date = date(2026, 1, 15)
    planning_horizon_days: int = Field(default=30, ge=1, le=365)
    medium_risk_alternative_research: bool = True
    gemini_model: str = "gemini-flash-lite-latest"
    gemini_fallback_models: str = "gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    model_retry_attempts: int = Field(default=2, ge=1, le=5)
    model_stage_timeout_seconds: float = Field(default=75.0, ge=10.0, le=300.0)
    maximum_additional_budget: float = Field(default=100_000.0, ge=0)

    risk_delivery_weight: float = 0.25
    risk_inventory_weight: float = 0.30
    risk_financial_weight: float = 0.20
    risk_production_weight: float = 0.25

    strategy_cost_weight: float = 0.30
    strategy_delivery_weight: float = 0.30
    strategy_quality_weight: float = 0.20
    strategy_risk_weight: float = 0.20

    minimum_quality_score: float = Field(default=80.0, ge=0, le=100)
    maximum_replanning_attempts: int = Field(default=2, ge=0, le=5)


@lru_cache
def get_settings() -> Settings:
    return Settings()
