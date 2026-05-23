"""SQLite backup helpers for the beta SaaS deployment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import hmac
import os
from pathlib import Path
import sqlite3
import tempfile
from urllib.error import URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


class BackupError(RuntimeError):
    """Raised when a database backup cannot be created or uploaded."""


@dataclass(frozen=True)
class BackupResult:
    bucket: str
    key: str
    size_bytes: int
    database_path: str
    created_at: str


def backup_sqlite_to_object_storage(db_path: str | Path) -> BackupResult:
    """Create a gzip SQLite backup and upload it to S3-compatible object storage."""
    archive, created_at = create_sqlite_backup_archive(db_path)
    bucket, key = _backup_destination(created_at)
    upload_s3_object(
        body=archive,
        bucket=bucket,
        key=key,
        content_type="application/gzip",
    )
    return BackupResult(
        bucket=bucket,
        key=key,
        size_bytes=len(archive),
        database_path=str(db_path),
        created_at=created_at,
    )


def create_sqlite_backup_archive(db_path: str | Path) -> tuple[bytes, str]:
    """Return a consistent gzip archive of a SQLite database."""
    source_path = Path(db_path)
    if not source_path.exists():
        raise BackupError(f"Database file does not exist: {source_path}")

    created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_path = Path(tmpdir) / "thermal_saas.sqlite"
        try:
            with sqlite3.connect(source_path) as source:
                with sqlite3.connect(snapshot_path) as snapshot:
                    source.backup(snapshot)
        except sqlite3.Error as exc:
            raise BackupError(f"Could not snapshot SQLite database: {exc}") from exc
        return gzip.compress(snapshot_path.read_bytes(), compresslevel=9), created_at


def upload_s3_object(
    *,
    body: bytes,
    bucket: str,
    key: str,
    content_type: str,
) -> None:
    """Upload an object using AWS Signature V4 and path-style S3 URLs."""
    endpoint = _required_env("THERMAL_BACKUP_S3_ENDPOINT").rstrip("/")
    region = os.environ.get("THERMAL_BACKUP_S3_REGION", "us-east-1")
    access_key = _required_env("THERMAL_BACKUP_S3_ACCESS_KEY_ID")
    secret_key = _required_env("THERMAL_BACKUP_S3_SECRET_ACCESS_KEY")

    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.netloc:
        raise BackupError("THERMAL_BACKUP_S3_ENDPOINT must be an absolute HTTP(S) URL.")

    escaped_key = "/".join(quote(part, safe="") for part in key.split("/"))
    canonical_uri = f"/{quote(bucket, safe='')}/{escaped_key}"
    url = f"{endpoint}{canonical_uri}"
    payload_hash = hashlib.sha256(body).hexdigest()
    amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = amz_date[:8]
    headers = {
        "Content-Type": content_type,
        "Host": parsed_endpoint.netloc,
        "X-Amz-Content-Sha256": payload_hash,
        "X-Amz-Date": amz_date,
    }
    authorization = _s3_authorization_header(
        method="PUT",
        canonical_uri=canonical_uri,
        headers=headers,
        payload_hash=payload_hash,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        date_stamp=date_stamp,
        amz_date=amz_date,
    )
    headers["Authorization"] = authorization
    request = Request(url, data=body, headers=headers, method="PUT")
    try:
        with urlopen(request, timeout=60) as response:
            if response.status not in {200, 201}:
                raise BackupError(f"Backup upload failed with HTTP {response.status}.")
    except URLError as exc:
        raise BackupError(f"Backup upload failed: {exc}") from exc


def _s3_authorization_header(
    *,
    method: str,
    canonical_uri: str,
    headers: dict[str, str],
    payload_hash: str,
    access_key: str,
    secret_key: str,
    region: str,
    date_stamp: str,
    amz_date: str,
) -> str:
    canonical_headers = "".join(
        f"{name.lower()}:{headers[name].strip()}\n"
        for name in sorted(headers, key=str.lower)
    )
    signed_headers = ";".join(name.lower() for name in sorted(headers, key=str.lower))
    canonical_request = "\n".join(
        [
            method,
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ],
    )
    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ],
    )
    signing_key = _s3_signing_key(secret_key, date_stamp, region)
    signature = hmac.new(
        signing_key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )


def _s3_signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    date_key = _hmac_sha256(f"AWS4{secret_key}".encode("utf-8"), date_stamp)
    region_key = _hmac_sha256(date_key, region)
    service_key = _hmac_sha256(region_key, "s3")
    return _hmac_sha256(service_key, "aws4_request")


def _hmac_sha256(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _backup_destination(created_at: str) -> tuple[str, str]:
    bucket = _required_env("THERMAL_BACKUP_S3_BUCKET")
    prefix = os.environ.get("THERMAL_BACKUP_S3_PREFIX", "thermal-saas/sqlite").strip("/")
    filename = f"thermal_saas-{created_at}.sqlite.gz"
    key = f"{prefix}/{filename}" if prefix else filename
    return bucket, key


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BackupError(f"{name} is required for backups.")
    return value
