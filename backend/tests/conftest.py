"""Cliente HTTP em memória. Não precisa de PostgreSQL a correr."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
