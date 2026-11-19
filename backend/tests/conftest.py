"""Cliente HTTP em memória. Não precisa de PostgreSQL a correr."""

import os

# Segredo só deste processo. A aplicação não define um valor por omissão.
os.environ["JWT_SECRET"] = (
    "pytest-secret-only-for-tests-not-a-deployment-key-0123456789abcd"
)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
