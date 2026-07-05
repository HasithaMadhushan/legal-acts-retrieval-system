def test_health_reports_ok_when_all_checks_pass(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"]["ok"] is True
    assert data["checks"]["upload_directory"]["ok"] is True
    assert data["checks"]["parser_configuration"]["ok"] is True


def test_health_flags_unknown_parser_configuration(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "doc_parser_primary", "not-a-real-parser")

    response = client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["parser_configuration"]["ok"] is False
