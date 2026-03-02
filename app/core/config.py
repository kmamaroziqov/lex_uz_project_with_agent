from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OLLAMA CONFIG
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "kmamaroziqov/alloma-8b-q4"
    OLLAMA_TEMPERATURE: float = 0.7

    TELEGRAM_BOT_TOKEN: str = ""

    DB_NAME: str = "lexuz_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "12345"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5433"

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    SESSIONS_DIR: str = "sessions"
    LEX_STRUCTURED_DIR: str = "lex_structured"
    LOGS_DIR: str = "logs"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def db_params(self) -> dict:
        return {
            "dbname": self.DB_NAME,
            "user": self.DB_USER,
            "password": self.DB_PASSWORD,
            "host": self.DB_HOST,
            "port": self.DB_PORT,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
