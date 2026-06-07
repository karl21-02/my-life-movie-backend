import io
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app

# 테스트에서 허용 처리할 S3 공개 base URL
_ALLOWED_BASE = "http://example.com"


def create_test_client(s3_public_base_url: str = _ALLOWED_BASE) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        s3_public_base_url=s3_public_base_url
    )
    return TestClient(app, raise_server_exceptions=False)


def _make_jpeg_bytes(width: int = 100, height: int = 100) -> bytes:
    from PIL import Image
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _mock_response(content: bytes, content_type: str = "image/jpeg", status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.content = content
    mock_resp.headers = {"content-type": content_type}
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _patch_fetch(content: bytes, content_type: str = "image/jpeg"):
    """httpx.AsyncClient.get이 주어진 응답을 반환하도록 패치하는 컨텍스트."""
    patcher = patch("app.routers.images.httpx.AsyncClient")
    mock_client_cls = patcher.start()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_mock_response(content, content_type))
    mock_client_cls.return_value = mock_client
    return patcher


# ── 정상 동작 ─────────────────────────────────────────────────

def test_resize_returns_200():
    jpeg = _make_jpeg_bytes(400, 600)
    patcher = _patch_fetch(jpeg)
    try:
        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=200&height=300"
        )
    finally:
        patcher.stop()

    assert response.status_code == 200


def test_resize_returns_image_content_type():
    jpeg = _make_jpeg_bytes(400, 600)
    patcher = _patch_fetch(jpeg)
    try:
        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=200&height=300"
        )
    finally:
        patcher.stop()

    assert "image/jpeg" in response.headers["content-type"]


def test_resize_output_dimensions():
    from PIL import Image
    jpeg = _make_jpeg_bytes(400, 600)
    patcher = _patch_fetch(jpeg)
    try:
        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=200&height=300"
        )
    finally:
        patcher.stop()

    result_img = Image.open(io.BytesIO(response.content))
    assert result_img.size == (200, 300)


def test_resize_without_params_returns_original():
    jpeg = _make_jpeg_bytes(400, 600)
    patcher = _patch_fetch(jpeg)
    try:
        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg"
        )
    finally:
        patcher.stop()

    assert response.status_code == 200
    assert len(response.content) == len(jpeg)


def test_resize_only_width_keeps_aspect_ratio():
    from PIL import Image
    jpeg = _make_jpeg_bytes(400, 200)
    patcher = _patch_fetch(jpeg)
    try:
        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=200"
        )
    finally:
        patcher.stop()

    result_img = Image.open(io.BytesIO(response.content))
    assert result_img.size == (200, 100)


# ── 에러 처리 ─────────────────────────────────────────────────

def test_resize_missing_url_returns_422():
    response = create_test_client().get("/api/images/resize?width=200&height=300")
    assert response.status_code == 422


def test_resize_invalid_content_type_returns_415():
    patcher = _patch_fetch(b"not an image", "text/html")
    try:
        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/page.html&width=200&height=300"
        )
    finally:
        patcher.stop()

    assert response.status_code == 415


def test_resize_width_exceeds_limit_returns_422():
    response = create_test_client().get(
        "/api/images/resize?url=http://example.com/img.jpg&width=9999"
    )
    assert response.status_code == 422


# ── SSRF 방지 ─────────────────────────────────────────────────

def test_resize_rejects_url_outside_allowlist_returns_400():
    # 허용된 호스트가 아니면 fetch 자체를 하지 않고 거부한다.
    response = create_test_client().get(
        "/api/images/resize?url=http://169.254.169.254/latest/meta-data/&width=100"
    )
    assert response.status_code == 400


def test_resize_rejects_subdomain_suffix_bypass_returns_400():
    # http://example.com.evil.com 같은 prefix 우회를 차단한다.
    response = create_test_client().get(
        "/api/images/resize?url=http://example.com.evil.com/img.jpg&width=100"
    )
    assert response.status_code == 400


def test_resize_rejects_when_base_url_unconfigured_returns_400():
    response = create_test_client(s3_public_base_url="").get(
        "/api/images/resize?url=http://example.com/img.jpg&width=100"
    )
    assert response.status_code == 400


# ── DoS 방지 ─────────────────────────────────────────────────

def test_resize_rejects_oversized_source_returns_413():
    oversized = b"\x00" * (10 * 1024 * 1024 + 1)
    patcher = _patch_fetch(oversized)
    try:
        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=100"
        )
    finally:
        patcher.stop()

    assert response.status_code == 413
