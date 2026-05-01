from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "Chanlan"
    binance_base_url: str = "https://api.binance.com"
    request_timeout_seconds: float = Field(default=12.0, gt=0)
    max_klines_limit: int = Field(default=1000, ge=100, le=1000)
    divergence_ratio: float = Field(default=0.8, gt=0, le=1)
    divergence_min_breakout_ratio: float = Field(default=0.05, ge=0)
    pivot_dedupe_overlap_ratio: float = Field(default=0.95, gt=0, le=1)

    model_config = SettingsConfigDict(env_prefix="CHANLAN_", env_file=".env", extra="ignore")


settings = Settings()
