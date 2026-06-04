from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_FRONTEND_DIST = str(Path(__file__).resolve().parents[2] / "frontend" / "dist")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    platform_database_url: str
    embedding_url: str
    ollama_url: str = "http://localhost:11434"
    mock_as400_url: str = "http://localhost:8400"
    frontend_dist: str = _DEFAULT_FRONTEND_DIST


settings = Settings()
