from fastapi.testclient import TestClient

from dashboard.api.app.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "stock-dashboard-api"


def test_analysis_endpoint_returns_payload():
    response = client.get("/api/stocks/2330/analysis")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stock"]["stock_id"] == "2330"
    assert "technical_summary" in payload
    assert "indicator_summary" in payload
