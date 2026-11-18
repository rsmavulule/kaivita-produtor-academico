"""Definições lidas do ambiente.

Há uma única configuração partilhada pela API e pelo Alembic.
Os valores por omissão servem para desenvolvimento local e para os testes.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Kaivita Produtor Académico"
    database_url: str = (
        "postgresql+psycopg://kaivita:kaivita_dev@localhost:5432/kaivita"
    )


settings = Settings()
