"""Definições lidas do ambiente.

Há uma única configuração partilhada pela API e pelo Alembic.
A URL da base tem valor por omissão para desenvolvimento local.
O segredo JWT não tem: sem ``JWT_SECRET`` a aplicação não arranca.
"""

from pydantic import SecretStr, field_validator
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
    jwt_secret: SecretStr
    jwt_expires_in: int = 1800
    jwt_issuer: str = "kaivita-produtor-academico"

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_is_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET tem de ter pelo menos 32 caracteres.")
        return value

    @field_validator("jwt_expires_in")
    @classmethod
    def jwt_expiry_is_bounded(cls, value: int) -> int:
        if not 60 <= value <= 24 * 60 * 60:
            raise ValueError("JWT_EXPIRES_IN tem de estar entre 60 e 86400 segundos.")
        return value

    @field_validator("jwt_issuer")
    @classmethod
    def jwt_issuer_has_no_spaces(cls, value: str) -> str:
        if not value or any(character.isspace() for character in value):
            raise ValueError("JWT_ISSUER tem de ser um identificador sem espaços.")
        return value


settings = Settings()
