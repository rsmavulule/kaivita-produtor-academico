"""Contrato mínimo da API: /health e a documentação em /docs."""

from unittest.mock import patch

from app.config import settings


def test_health_reports_database_up(client):
    with patch("app.main.check_database", return_value=True):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_health_reports_database_down(client):
    with patch("app.main.check_database", return_value=False):
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "down"}


def test_docs_page_is_served(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_schema_exposes_health(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert document["info"]["title"] == settings.app_name
    assert "/health" in document["paths"]
    scheme = document["components"]["securitySchemes"]["HTTPBearer"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    me = document["paths"]["/auth/me"]["get"]
    assert me["security"] == [{"HTTPBearer": []}]
    assert "parameters" not in me
