from dataclasses import dataclass
import mimetypes
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from botocore.client import BaseClient

from app.core.config import Settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    url: str
    content_type: str | None = None
    size: int | None = None


@dataclass(frozen=True)
class PresignedUpload:
    key: str
    url: str
    method: str
    expires_seconds: int
    headers: dict[str, str]


@dataclass(frozen=True)
class PresignedDownload:
    key: str
    url: str
    method: str
    expires_seconds: int


class StorageService(Protocol):
    def put_bytes(self, key: str, content: bytes, *, content_type: str | None = None) -> StoredObject:
        ...

    def delete(self, key: str) -> None:
        ...

    def public_url(self, key: str) -> str:
        ...

    def create_presigned_upload(
        self,
        key: str,
        *,
        content_type: str | None = None,
        expires_seconds: int = 900,
    ) -> PresignedUpload:
        ...

    def create_presigned_download(
        self,
        key: str,
        *,
        expires_seconds: int = 900,
    ) -> PresignedDownload:
        ...


class StorageConfigError(RuntimeError):
    pass


class LocalStorageService:
    def __init__(self, *, root_dir: str, public_base_url: str) -> None:
        self.root_dir = Path(root_dir)
        self.public_base_url = public_base_url.rstrip("/") or "/generated"

    def put_bytes(self, key: str, content: bytes, *, content_type: str | None = None) -> StoredObject:
        normalized_key = normalize_storage_key(key)
        output_path = self.root_dir / normalized_key
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        return StoredObject(
            key=normalized_key,
            url=self.public_url(normalized_key),
            content_type=content_type or guess_content_type(normalized_key),
            size=len(content),
        )

    def delete(self, key: str) -> None:
        path = self.root_dir / normalize_storage_key(key)
        if path.exists():
            path.unlink()

    def public_url(self, key: str) -> str:
        return join_public_url(self.public_base_url, normalize_storage_key(key))

    def create_presigned_upload(
        self,
        key: str,
        *,
        content_type: str | None = None,
        expires_seconds: int = 900,
    ) -> PresignedUpload:
        normalized_key = normalize_storage_key(key)
        headers = {"Content-Type": content_type} if content_type else {}
        return PresignedUpload(
            key=normalized_key,
            url=self.public_url(normalized_key),
            method="PUT",
            expires_seconds=expires_seconds,
            headers=headers,
        )

    def create_presigned_download(
        self,
        key: str,
        *,
        expires_seconds: int = 900,
    ) -> PresignedDownload:
        normalized_key = normalize_storage_key(key)
        return PresignedDownload(
            key=normalized_key,
            url=self.public_url(normalized_key),
            method="GET",
            expires_seconds=expires_seconds,
        )


class S3StorageService:
    def __init__(
        self,
        *,
        bucket_name: str,
        region: str,
        public_base_url: str,
        endpoint_url: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
        session_token: str = "",
        client: BaseClient | None = None,
    ) -> None:
        if not bucket_name:
            raise StorageConfigError("S3_BUCKET_NAME 환경 변수가 필요합니다.")

        self.bucket_name = bucket_name
        self.region = region
        self.public_base_url = public_base_url.rstrip("/")
        self.client = client or create_s3_client(
            region=region,
            endpoint_url=endpoint_url,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=session_token,
        )

    def put_bytes(self, key: str, content: bytes, *, content_type: str | None = None) -> StoredObject:
        normalized_key = normalize_storage_key(key)
        resolved_content_type = content_type or guess_content_type(normalized_key)
        extra_args: dict[str, str] = {}
        if resolved_content_type:
            extra_args["ContentType"] = resolved_content_type

        self.client.put_object(
            Bucket=self.bucket_name,
            Key=normalized_key,
            Body=content,
            **extra_args,
        )
        return StoredObject(
            key=normalized_key,
            url=self.public_url(normalized_key),
            content_type=resolved_content_type,
            size=len(content),
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket_name, Key=normalize_storage_key(key))

    def public_url(self, key: str) -> str:
        normalized_key = normalize_storage_key(key)
        if self.public_base_url:
            return join_public_url(self.public_base_url, normalized_key)
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{quote(normalized_key)}"

    def create_presigned_upload(
        self,
        key: str,
        *,
        content_type: str | None = None,
        expires_seconds: int = 900,
    ) -> PresignedUpload:
        normalized_key = normalize_storage_key(key)
        params: dict[str, str] = {
            "Bucket": self.bucket_name,
            "Key": normalized_key,
        }
        headers: dict[str, str] = {}
        if content_type:
            params["ContentType"] = content_type
            headers["Content-Type"] = content_type

        url = self.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_seconds,
        )
        return PresignedUpload(
            key=normalized_key,
            url=url,
            method="PUT",
            expires_seconds=expires_seconds,
            headers=headers,
        )

    def create_presigned_download(
        self,
        key: str,
        *,
        expires_seconds: int = 900,
    ) -> PresignedDownload:
        normalized_key = normalize_storage_key(key)
        url = self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": normalized_key,
            },
            ExpiresIn=expires_seconds,
        )
        return PresignedDownload(
            key=normalized_key,
            url=url,
            method="GET",
            expires_seconds=expires_seconds,
        )


def build_storage_service(settings: Settings) -> StorageService:
    if settings.storage_provider == "local":
        return LocalStorageService(
            root_dir=settings.local_storage_dir,
            public_base_url=settings.local_public_base_url,
        )
    if settings.storage_provider == "s3":
        return S3StorageService(
            bucket_name=settings.s3_bucket_name,
            region=settings.aws_region,
            public_base_url=settings.s3_public_base_url,
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            session_token=settings.aws_session_token,
        )

    raise StorageConfigError(f"지원하지 않는 storage provider입니다: {settings.storage_provider}")


def create_s3_client(
    *,
    region: str,
    endpoint_url: str = "",
    access_key_id: str = "",
    secret_access_key: str = "",
    session_token: str = "",
) -> BaseClient:
    import boto3

    kwargs: dict[str, str] = {"region_name": region}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if access_key_id and secret_access_key:
        kwargs["aws_access_key_id"] = access_key_id
        kwargs["aws_secret_access_key"] = secret_access_key
    if session_token:
        kwargs["aws_session_token"] = session_token

    return boto3.client("s3", **kwargs)


def build_storage_key(prefix: str, *parts: str) -> str:
    raw_key = "/".join([prefix.strip("/"), *[part.strip("/") for part in parts if part.strip("/")]])
    return normalize_storage_key(raw_key)


def normalize_storage_key(key: str) -> str:
    normalized = key.replace("\\", "/").strip("/")
    if not normalized or normalized in {".", ".."}:
        raise StorageConfigError("storage key가 비어 있습니다.")
    if any(part in {"", ".", ".."} for part in normalized.split("/")):
        raise StorageConfigError(f"허용되지 않는 storage key입니다: {key}")
    return normalized


def guess_content_type(key: str) -> str | None:
    return mimetypes.guess_type(key)[0]


def join_public_url(base_url: str, key: str) -> str:
    encoded_key = "/".join(quote(part) for part in key.split("/"))
    if base_url.startswith("/"):
        return f"{base_url.rstrip('/')}/{encoded_key}"
    return f"{base_url.rstrip('/')}/{encoded_key}"
