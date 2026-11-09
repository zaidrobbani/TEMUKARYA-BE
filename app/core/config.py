from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "TEMUKARYA API"
    APP_ENV: str = "development"
    DEBUG: bool = False

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "temukarya"
    DB_USER: str = "temukarya"
    DB_PASSWORD: str = ""

    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = Field(default=60 * 24, gt=0)

    PUBLIC_BASE_URL: str = "http://localhost:8000"

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = False
    EMAIL_FROM: str = "TEMUKARYA <no-reply@temukarya.id>"

    GOOGLE_CLIENT_ID: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
