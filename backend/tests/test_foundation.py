"""Configuração essencial: definições, Alembic e ficheiros de arranque."""

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.config import Settings
from app.db import check_database

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


def test_settings_default_to_local_postgres(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    configured = Settings(_env_file=None)

    assert configured.app_name == "Kaivita Produtor Académico"
    assert configured.database_url.startswith("postgresql+psycopg://")
    assert configured.database_url.endswith("/kaivita")


def test_alembic_chain_preserves_the_empty_initial_revision():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    initial = script.get_revision("0001_initial")
    identity = script.get_revision("0002_identity_access")

    assert script.get_heads() == ["0002_identity_access"]
    assert initial is not None and initial.down_revision is None
    assert identity is not None and identity.down_revision == "0001_initial"

    source = (BACKEND_ROOT / "alembic" / "versions" / "0001_initial.py").read_text(
        encoding="utf-8"
    )
    source = source.replace("\r\n", "\n")
    assert "def upgrade() -> None:\n    pass\n" in source
    assert "def downgrade() -> None:\n    pass\n" in source


def test_compose_declares_the_three_services():
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "postgres:16-alpine" in compose
    for service in ("\n  db:", "\n  api:", "\n  web:"):
        assert service in compose


def test_env_example_and_gitignore_keep_secrets_out_of_git():
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "DATABASE_URL=postgresql+psycopg://" in example
    ignored_lines = {line.strip() for line in ignore.splitlines()}
    assert ".env" in ignored_lines
    assert ".env.example" not in ignored_lines


@pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.",
)
def test_real_database_answers():
    assert check_database() is True
