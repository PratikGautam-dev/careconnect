# core/storage.py
"""
Section 12.10: private object storage for patient documents -- checked this
repo and Spec.md for any prior S3/object-storage setup (the "DAAP Engage doc"
mentioned when this was scoped isn't part of this codebase, and no
boto3/storage dependency existed before this file) -- nothing existed, adding
fresh here.

Same "real backend, graceful local fallback" shape as core/session_store.py's
Redis-with-in-memory-fallback session store: `get_storage()` returns
S3Storage when S3_BUCKET/credentials are configured (works against real AWS
S3 *or* Cloudflare R2 -- R2 is S3-API-compatible via S3_ENDPOINT_URL, and is
the cheaper/likely default given this project's stated cost-minimization
priority), and LocalFileStorage otherwise -- so a developer can upload and
"send to WhatsApp" a document end to end without ever signing up for a cloud
account, matching how Redis-optional session storage already works here.

Every file is private -- no public bucket, no public-read ACL. Access is
ALWAYS through a short-lived signed URL, minted on demand by get_signed_url(),
never a stored/reusable public link. S3Storage uses S3's own presigned URLs;
LocalFileStorage mints an HMAC-signed, expiring token (same
"<payload>.<expires_epoch>.<signature>" shape portal.py's own session token
already uses) verified by the streaming endpoint in portal/routes/documents.py.
"""
import hashlib
import hmac
import time
import uuid
from pathlib import Path

from core.config import get_settings

_LOCAL_STORAGE_DIR = Path(get_settings().LOCAL_STORAGE_DIR)


def _storage_key(hospital_id: int, patient_id: int, file_name: str) -> str:
    """Namespaced per hospital/patient for organizational clarity -- NOT the
    access-control boundary itself (the patient_documents DB row, checked
    against the authenticated hospital_id before ever handing out a signed
    URL, is what actually gates access). A random prefix avoids collisions
    between two uploads of a same-named file and makes the key
    unguessable-by-enumeration on its own, defense in depth on top of the
    signed-URL requirement, not a substitute for it."""
    safe_name = file_name.replace("/", "_").replace("\\", "_")
    return f"patients/{hospital_id}/{patient_id}/{uuid.uuid4().hex}_{safe_name}"


class S3Storage:
    """Real backend -- AWS S3 or any S3-compatible provider (Cloudflare R2,
    Backblaze B2, ...) via S3_ENDPOINT_URL. Bucket is assumed already private
    (default for a freshly created bucket on every one of these providers) --
    this class never sets a public-read ACL on anything it uploads."""

    def __init__(self, bucket: str, region: str | None, endpoint_url: str | None,
                 access_key_id: str | None, secret_access_key: str | None):
        import boto3
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def upload(self, hospital_id: int, patient_id: int, file_name: str, content: bytes, content_type: str) -> str:
        key = _storage_key(hospital_id, patient_id, file_name)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=content_type)
        return key

    def get_signed_url(self, storage_key: str, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": storage_key}, ExpiresIn=expires_in,
        )

    def delete(self, storage_key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=storage_key)


class LocalFileStorage:
    """Dev/test fallback -- writes under LOCAL_STORAGE_DIR (gitignored, never
    committed) and mints an HMAC-signed, time-limited token instead of a real
    presigned URL. portal/routes/documents.py's document-download route verifies the
    token (signature + expiry) before streaming the file back -- same
    "basic protection, not production-grade auth" posture as every other
    signed token in this app (portal.py's own session cookie/Bearer token)."""

    def __init__(self, base_dir: Path, secret: str):
        self._base_dir = base_dir
        self._secret = secret.encode()

    def upload(self, hospital_id: int, patient_id: int, file_name: str, content: bytes, content_type: str) -> str:
        key = _storage_key(hospital_id, patient_id, file_name)
        path = self._base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def _sign(self, storage_key: str, expires_at: int) -> str:
        payload = f"{storage_key}.{expires_at}"
        sig = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{sig}"

    def get_signed_url(self, storage_key: str, expires_in: int = 3600) -> str:
        expires_at = int(time.time()) + expires_in
        token = self._sign(storage_key, expires_at)
        return f"/api/documents/local/{token}"

    def verify_token(self, token: str) -> str | None:
        """Returns the storage_key if the token's signature is valid and not
        expired, else None. `storage_key` itself may contain '.' inside the
        original file_name, so split from the right (rsplit) rather than the
        left -- the two well-known fields (expires_at, signature) are always
        the LAST two dot-separated segments."""
        try:
            storage_key, expires_at_str, sig = token.rsplit(".", 2)
            expires_at = int(expires_at_str)
        except (ValueError, TypeError):
            return None
        if time.time() > expires_at:
            return None
        expected = self._sign(storage_key, expires_at)
        if not hmac.compare_digest(expected, token):
            return None
        return storage_key

    def read(self, storage_key: str) -> bytes | None:
        path = self._base_dir / storage_key
        try:
            # Reject any path that escapes _base_dir (e.g. a storage_key
            # containing "../..") -- storage_key values are always ones this
            # class itself generated, but a corrupted/tampered token could in
            # principle still smuggle one in past signature verification if
            # the secret ever leaked, so this is a second, independent guard.
            path.resolve().relative_to(self._base_dir.resolve())
        except ValueError:
            return None
        if not path.is_file():
            return None
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self._base_dir / storage_key
        path.unlink(missing_ok=True)


def _build_storage() -> "S3Storage | LocalFileStorage":
    _settings = get_settings()
    bucket = _settings.S3_BUCKET
    if bucket:
        try:
            return S3Storage(
                bucket=bucket,
                region=_settings.S3_REGION,
                endpoint_url=_settings.S3_ENDPOINT_URL,  # set for R2/B2, unset for real AWS S3
                access_key_id=_settings.S3_ACCESS_KEY_ID,
                secret_access_key=_settings.S3_SECRET_ACCESS_KEY,
            )
        except Exception:
            pass
    secret = _settings.PORTAL_SECRET or "dev-only-local-storage-secret"
    return LocalFileStorage(_LOCAL_STORAGE_DIR, secret)


_STORAGE = _build_storage()


def get_storage() -> "S3Storage | LocalFileStorage":
    return _STORAGE


def reset_storage_for_tests(base_dir: Path | None = None) -> None:
    """Test-only: forces a fresh LocalFileStorage rooted at `base_dir` (a
    pytest tmp_path, typically) so tests never touch the real
    LOCAL_STORAGE_DIR or leak files between test runs. Not called anywhere
    in application code."""
    global _STORAGE
    secret = get_settings().PORTAL_SECRET or "dev-only-local-storage-secret"
    _STORAGE = LocalFileStorage(base_dir or _LOCAL_STORAGE_DIR, secret)
