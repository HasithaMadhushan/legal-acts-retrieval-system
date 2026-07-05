from app.core.config import get_settings

VALID_PDF = b"%PDF-1.4\n% test legal act pdf\n"


def test_admin_can_upload_pdf_and_metadata_is_stored(client, admin_token):
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["source_file_name"] == "sample.pdf"
    assert data["file_size"] == len(VALID_PDF)
    assert data["mime_type"] == "application/pdf"
    assert data["processing_status"] == "UPLOADED"


def test_non_admin_upload_is_blocked(client, user_token):
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {user_token}"},
        files={"file": ("sample.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 403


def test_upload_rejects_non_pdf_extension(client, admin_token):
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed."


def test_upload_rejects_pdf_extension_with_bad_signature(client, admin_token):
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file content is not a valid PDF."


def test_upload_rejects_bad_mime_type(client, admin_token):
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF MIME types are allowed."


def test_upload_rejects_oversize_pdf(client, admin_token, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 0)
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "application/pdf")},
    )
    assert response.status_code == 413


def test_upload_rejects_duplicate_hash(client, admin_token):
    first = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "application/pdf")},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("copy.pdf", VALID_PDF, "application/pdf")},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "This PDF has already been uploaded."


def test_upload_rejects_path_separator_in_file_name(client, admin_token):
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("../sample.pdf", VALID_PDF, "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "File name must not contain path separators."


def test_legal_advice_query_is_rejected(client, user_token):
    response = client.get(
        "/api/v1/search",
        params={"q": "what should I do in my case"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 400
    assert "cannot provide legal advice" in response.json()["detail"]
