from functools import lru_cache

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
