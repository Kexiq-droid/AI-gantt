from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = "dev-secret-change-me"
    database_url: str = f"sqlite:///{ROOT / 'data' / 'bioplan.db'}"
    cors_origins: str = "http://127.0.0.1:8100,http://localhost:8100,http://localhost:5173"
    cookie_secure: bool = False
    cookie_name: str = "bioplan_token"
    access_token_expire_minutes: int = 60 * 24 * 7

    demo_pm_password: str = "pm12345"

    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # Timeweb Cloud AI agent (OpenAI-compatible)
    timeweb_api_key: str = ""
    timeweb_base_url: str = ""
    timeweb_model: str = "deepseek/deepseek-v4-flash"

    api_host: str = "127.0.0.1"
    api_port: int = 8100

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider == "timeweb":
            return bool(self.timeweb_api_key and self.timeweb_base_url)
        return bool(self.deepseek_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
