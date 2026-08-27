from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.services import storage as storage_module
from app.services.storage import LocalStorage, S3Storage, get_storage


@pytest.fixture(autouse=True)
def _clear_storage_cache():
    get_storage.cache_clear()
    yield
    get_storage.cache_clear()


def test_get_storage_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    assert isinstance(get_storage(), LocalStorage)


def test_local_storage_save_and_read_round_trip(tmp_path):
    local = LocalStorage(tmp_path)

    stored_key = local.save("doc.pdf", b"%PDF-1.4 fake content")

    assert stored_key == str(tmp_path / "doc.pdf")
    local_path = local.ensure_local_path(stored_key)
    assert local_path.read_bytes() == b"%PDF-1.4 fake content"


def test_local_storage_save_artifact_round_trip_uses_nested_key(tmp_path):
    local = LocalStorage(tmp_path)
    logical_key = "act-id/extractions/job-id.schema-v1.json"

    pointer = local.save_artifact(logical_key, b'{"schema_version":"1"}', "application/json")

    assert pointer == str(tmp_path / logical_key)
    assert local.read_artifact(pointer) == b'{"schema_version":"1"}'


def test_s3_storage_save_artifact_uses_json_content_type(tmp_path):
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b'{"ok":true}')}
    with patch("boto3.client", return_value=mock_client):
        s3 = S3Storage("my-bucket", prefix="acts", cache_dir=tmp_path)

    pointer = s3.save_artifact("act/extractions/job.json", b'{"ok":true}', "application/json")

    assert pointer == "s3://my-bucket/acts/act/extractions/job.json"
    mock_client.put_object.assert_called_once_with(
        Bucket="my-bucket",
        Key="acts/act/extractions/job.json",
        Body=b'{"ok":true}',
        ContentType="application/json",
    )
    assert s3.read_artifact(pointer) == b'{"ok":true}'
    mock_client.get_object.assert_called_once_with(
        Bucket="my-bucket", Key="acts/act/extractions/job.json"
    )


def test_s3_storage_read_artifact_does_not_use_pdf_download_cache(tmp_path):
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"artifact-bytes")}
    with patch("boto3.client", return_value=mock_client):
        s3 = S3Storage("my-bucket", cache_dir=tmp_path)

    assert s3.read_artifact("s3://my-bucket/doc.json") == b"artifact-bytes"
    mock_client.download_file.assert_not_called()


def test_local_storage_delete_removes_file(tmp_path):
    local = LocalStorage(tmp_path)
    stored_key = local.save("doc.pdf", b"content")

    local.delete(stored_key)

    assert not (tmp_path / "doc.pdf").exists()


def test_local_storage_check_health_ok(tmp_path):
    local = LocalStorage(tmp_path)
    ok, error = local.check_health()
    assert ok is True
    assert error is None


def test_local_storage_check_health_reports_error_for_unwritable_dir(tmp_path):
    # A path nested under a file (not a directory) can never be created/written.
    blocking_file = tmp_path / "not_a_dir"
    blocking_file.write_text("x")
    local = LocalStorage(blocking_file / "uploads")

    ok, error = local.check_health()

    assert ok is False
    assert error


def test_s3_storage_save_uploads_and_returns_s3_uri(tmp_path):
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        s3 = S3Storage("my-bucket", prefix="acts", cache_dir=tmp_path)

    stored_key = s3.save("doc.pdf", b"pdf-bytes")

    assert stored_key == "s3://my-bucket/acts/doc.pdf"
    mock_client.put_object.assert_called_once_with(
        Bucket="my-bucket", Key="acts/doc.pdf", Body=b"pdf-bytes", ContentType="application/pdf"
    )


def test_s3_storage_ensure_local_path_downloads_once_and_caches(tmp_path):
    mock_client = MagicMock()

    def fake_download(bucket, key, dest):
        with open(dest, "wb") as fh:
            fh.write(b"downloaded-bytes")

    mock_client.download_file.side_effect = fake_download
    with patch("boto3.client", return_value=mock_client):
        s3 = S3Storage("my-bucket", cache_dir=tmp_path)

    first = s3.ensure_local_path("s3://my-bucket/doc.pdf")
    second = s3.ensure_local_path("s3://my-bucket/doc.pdf")

    assert first == second
    assert first.read_bytes() == b"downloaded-bytes"
    mock_client.download_file.assert_called_once_with("my-bucket", "doc.pdf", str(first))


def test_s3_storage_delete_calls_delete_object(tmp_path):
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        s3 = S3Storage("my-bucket", cache_dir=tmp_path)

    s3.delete("s3://my-bucket/acts/doc.pdf")

    mock_client.delete_object.assert_called_once_with(Bucket="my-bucket", Key="acts/doc.pdf")


def test_s3_storage_check_health_ok_and_error(tmp_path):
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        s3 = S3Storage("my-bucket", cache_dir=tmp_path)

    ok, error = s3.check_health()
    assert ok is True
    assert error is None

    mock_client.head_bucket.side_effect = RuntimeError("bucket unreachable")
    ok, error = s3.check_health()
    assert ok is False
    assert "bucket unreachable" in error


def test_get_storage_uses_s3_when_bucket_configured(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "s3_bucket", "configured-bucket")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    with patch("boto3.client", return_value=MagicMock()):
        result = get_storage()

    assert isinstance(result, S3Storage)
    assert result._bucket == "configured-bucket"


def test_parse_s3_uri_rejects_non_s3_key():
    with pytest.raises(ValueError, match="Not an S3 storage key"):
        storage_module._parse_s3_uri("/local/path/doc.pdf")
