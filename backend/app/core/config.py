from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    google_client_id: str
    access_token_expire_minutes: int = 60 * 24 * 7
    default_user_role: str = "user"
    app_env: str = "development"
    app_title: str = "DailyVerse Sentiment API"
    app_version: str = "1.0.0"
    scraper_parallelism: int = 2
    scraper_delay_seconds: float = 2.0
    scraper_start_year: int = 2015
    scraper_end_year: int = 2024
    scraper_total_target: int = 600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
