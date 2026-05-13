import pytest

from app.core.config import Settings
from app.services.storage_service import (
    LocalStorageService,
    S3StorageService,
    StorageConfigError,
    build_storage_key,
    build_storage_service,
    normalize_storage_key,
)


pytestmark = pytest.mark.unit


def test_local_storage_service_writes_file_and_returns_public_url(tmp_path):
    storage = LocalStorageService(root_dir=str(tmp_path), public_base_url="/generated")

    stored = storage.put_bytes("videos/movie.mp4", b"movie", content_type="video/mp4")

    assert stored.key == "videos/movie.mp4"
    assert stored.url == "/generated/videos/movie.mp4"
    assert stored.content_type == "video/mp4"
    assert stored.size == 5
    assert (tmp_path / "videos/movie.mp4").read_bytes() == b"movie"


def test_local_storage_service_rejects_path_traversal(tmp_path):
    storage = LocalStorageService(root_dir=str(tmp_path), public_base_url="/generated")

    with pytest.raises(StorageConfigError):
        storage.put_bytes("../secret.txt", b"secret")


class FakeS3Client:
    def __init__(self) -> None:
        self.put_objects: list[dict] = []
        self.deleted_keys: list[str] = []

    def put_object(self, **kwargs):
        self.put_objects.append(kwargs)

    def delete_object(self, **kwargs):
        self.deleted_keys.append(kwargs["Key"])

    def generate_presigned_url(self, operation_name, *, Params, ExpiresIn):
        assert operation_name == "put_object"
        return f"https://upload.test/{Params['Key']}?expires={ExpiresIn}"


def test_s3_storage_service_puts_object_and_returns_public_url():
    client = FakeS3Client()
    storage = S3StorageService(
        bucket_name="movie-bucket",
        region="ap-northeast-2",
        public_base_url="https://cdn.example.com",
        client=client,
    )

    stored = storage.put_bytes("generated/videos/movie.mp4", b"movie")

    assert stored.url == "https://cdn.example.com/generated/videos/movie.mp4"
    assert client.put_objects == [
        {
            "Bucket": "movie-bucket",
            "Key": "generated/videos/movie.mp4",
            "Body": b"movie",
            "ContentType": "video/mp4",
        }
    ]


def test_s3_storage_service_creates_presigned_upload():
    client = FakeS3Client()
    storage = S3StorageService(
        bucket_name="movie-bucket",
        region="ap-northeast-2",
        public_base_url="",
        client=client,
    )

    upload = storage.create_presigned_upload(
        "uploads/source.mp4",
        content_type="video/mp4",
        expires_seconds=60,
    )

    assert upload.method == "PUT"
    assert upload.url == "https://upload.test/uploads/source.mp4?expires=60"
    assert upload.headers == {"Content-Type": "video/mp4"}


def test_build_storage_service_uses_local_provider(tmp_path):
    settings = Settings(
        storage_provider="local",
        local_storage_dir=str(tmp_path),
        local_public_base_url="/generated",
    )

    storage = build_storage_service(settings)

    assert isinstance(storage, LocalStorageService)


def test_build_storage_service_requires_s3_bucket():
    with pytest.raises(StorageConfigError):
        build_storage_service(Settings(storage_provider="s3", s3_bucket_name=""))


def test_build_storage_key_normalizes_prefix_and_parts():
    assert build_storage_key("/generated/videos/", "/movie.mp4") == "generated/videos/movie.mp4"


def test_normalize_storage_key_rejects_empty_key():
    with pytest.raises(StorageConfigError):
        normalize_storage_key("")
