def test_health_reports_ok_when_all_checks_pass(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"]["ok"] is True
    assert data["checks"]["upload_directory"]["ok"] is True
    assert data["checks"]["parser_configuration"]["ok"] is True


def test_parser_configuration_defaults_to_pymupdf(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("DOC_PARSER_PRIMARY", raising=False)

    assert Settings(_env_file=None).doc_parser_primary == "pymupdf"


def test_response_includes_request_id_header(client):
    response = client.get("/health")

    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id
    # Should be a UUID4 string, e.g. 8-4-4-4-12 hex groups.
    assert len(request_id) == 36
    assert request_id.count("-") == 4


def test_health_accepts_pdf_inspector_parser_configuration(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "doc_parser_primary", "pdf_inspector")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["checks"]["parser_configuration"] == {
        "ok": True,
        "parser_requested": "pdf_inspector",
    }


def test_health_flags_unknown_parser_configuration(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "doc_parser_primary", "not-a-real-parser")

    response = client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["parser_configuration"]["ok"] is False
