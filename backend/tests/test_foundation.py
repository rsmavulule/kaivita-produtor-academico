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


def test_alembic_head_is_the_initial_revision():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0001_initial"]


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
