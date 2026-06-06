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


def test_phase3_endpoints_return_payloads():
    institutional = client.get("/api/stocks/2330/institutional?days=10")
    assert institutional.status_code == 200
    institutional_payload = institutional.json()
    assert institutional_payload["rows"]
    assert "summary" in institutional_payload

    main_force = client.get("/api/stocks/2330/main-force?days=10")
    assert main_force.status_code == 200
    main_force_payload = main_force.json()
    assert main_force_payload["rows"]
    assert "signal" in main_force_payload

    multi_period = client.get("/api/stocks/2330/multi-period")
    assert multi_period.status_code == 200
    multi_period_payload = multi_period.json()
    assert len(multi_period_payload["periods"]) == 3

    refresh = client.post("/api/stocks/2330/refresh?limit=120")
    assert refresh.status_code == 200
    refresh_payload = refresh.json()
    assert "institutional" in refresh_payload
    assert "main_force" in refresh_payload
    assert "multi_period" in refresh_payload


def test_phase4_endpoints_return_payloads():
    patterns = client.get("/api/stocks/2330/patterns")
    assert patterns.status_code == 200
    patterns_payload = patterns.json()
    assert "patterns" in patterns_payload
    assert "w_bottom" in patterns_payload["patterns"]

    signals = client.get("/api/stocks/2330/signals")
    assert signals.status_code == 200
    signals_payload = signals.json()
    assert "trading_suggestion" in signals_payload
    assert "win_rate" in signals_payload
    assert "direction_prediction" in signals_payload

    train = client.post("/api/stocks/2330/train-models")
    assert train.status_code == 200
    train_payload = train.json()
    assert "trained_at" in train_payload
    assert "metrics" in train_payload
