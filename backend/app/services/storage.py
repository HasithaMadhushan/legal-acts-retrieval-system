"""Upload storage backend.

Defaults to storing uploaded PDFs on local disk (under `UPLOAD_DIR`), which is
correct for a single-instance deployment where the app and its volume live
together. Set `S3_BUCKET` (plus the standard `AWS_ACCESS_KEY_ID` /
`AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` env vars, or an attached IAM
role) to instead store uploads in S3 or an S3-compatible service (Cloudflare
R2, MinIO, ...). This matters once the app runs as multiple containers/hosts
that don't share a filesystem, or uploads need to outlive a container/volume
being recreated.

The PDF parsers (`app/services/pdf_parser/*`) need a real local file path, so
the S3 backend transparently downloads to a small on-disk cache the first time
a file is read and reuses it afterwards -- callers don't need to know which
backend is active.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Storage:
    """Backend-agnostic interface for saving and reading uploaded PDFs."""

    def save(self, filename: str, content: bytes) -> str:
        """Persist `content` and return an opaque key to pass back to this
        same backend later (stored as `LegalAct.stored_file_path`)."""
        raise NotImplementedError

    def ensure_local_path(self, stored_key: str) -> Path:
        """Return a local filesystem path containing the file's bytes.

        For local disk storage this is just `Path(stored_key)`. For remote
        backends the file is downloaded to a cache directory first. Treat the
        returned path as read-only.
        """
        raise NotImplementedError

    def delete(self, stored_key: str) -> None:
        raise NotImplementedError

    def check_health(self) -> tuple[bool, str | None]:
        """Return `(ok, error_message)` for use in the `/health` endpoint."""
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def save(self, filename: str, content: bytes) -> str:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._base_dir / filename
        path.write_bytes(content)
        return str(path)

    def ensure_local_path(self, stored_key: str) -> Path:
        return Path(stored_key)

    def delete(self, stored_key: str) -> None:
        Path(stored_key).unlink(missing_ok=True)

    def check_health(self) -> tuple[bool, str | None]:
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            probe_path = self._base_dir / ".health_check"
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
            return True, None
        except OSError as exc:
            return False, str(exc)


class S3Storage(Storage):
    """Stores uploads as objects `s3://{bucket}/{prefix}/{filename}`."""

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "",
        endpoint_url: str | None = None,
        cache_dir: Path,
    ) -> None:
        # Imported lazily: boto3 is a fairly large dependency and most
        # deployments of this app never configure S3, so it's only required
        # to actually be installed when this backend is selected.
        import boto3

        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._cache_dir = cache_dir
        self._client = boto3.client("s3", endpoint_url=endpoint_url or None)

    def _key(self, filename: str) -> str:
        return f"{self._prefix}/{filename}" if self._prefix else filename

    def save(self, filename: str, content: bytes) -> str:
        key = self._key(filename)
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=content, ContentType="application/pdf"
        )
        logger.info("s3_upload_saved", bucket=self._bucket, key=key, size_bytes=len(content))
        return f"s3://{self._bucket}/{key}"

    def ensure_local_path(self, stored_key: str) -> Path:
        bucket, key = _parse_s3_uri(stored_key)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        local_path = self._cache_dir / key.replace("/", "__")
        if not local_path.exists():
            self._client.download_file(bucket, key, str(local_path))
        return local_path

    def delete(self, stored_key: str) -> None:
        bucket, key = _parse_s3_uri(stored_key)
        self._client.delete_object(Bucket=bucket, Key=key)

    def check_health(self) -> tuple[bool, str | None]:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True, None
        except Exception as exc:  # noqa: BLE001 - surfacing any boto3/network error verbatim
            return False, str(exc)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Not an S3 storage key: {uri!r}")
    _, _, rest = uri.partition("s3://")
    bucket, _, key = rest.partition("/")
    return bucket, key


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.s3_bucket:
        return S3Storage(
            settings.s3_bucket,
            prefix=settings.s3_prefix,
            endpoint_url=settings.s3_endpoint_url,
            cache_dir=settings.upload_path / ".s3-cache",
        )
    return LocalStorage(settings.upload_path)
