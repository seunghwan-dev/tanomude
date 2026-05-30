from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    platform_database_url: str
    embedding_url: str
    ollama_url: str = "http://localhost:11434"
    mock_as400_url: str = "http://localhost:8000"


settings = Settings()
