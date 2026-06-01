import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def create_test_client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


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


# ── 정상 동작 ─────────────────────────────────────────────────

def test_resize_returns_200():
    jpeg = _make_jpeg_bytes(400, 600)
    with patch("app.routers.images.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(jpeg))
        mock_client_cls.return_value = mock_client

        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=200&height=300"
        )

    assert response.status_code == 200


def test_resize_returns_image_content_type():
    jpeg = _make_jpeg_bytes(400, 600)
    with patch("app.routers.images.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(jpeg))
        mock_client_cls.return_value = mock_client

        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=200&height=300"
        )

    assert "image/jpeg" in response.headers["content-type"]


def test_resize_output_dimensions():
    from PIL import Image
    jpeg = _make_jpeg_bytes(400, 600)
    with patch("app.routers.images.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(jpeg))
        mock_client_cls.return_value = mock_client

        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=200&height=300"
        )

    result_img = Image.open(io.BytesIO(response.content))
    assert result_img.size == (200, 300)


def test_resize_without_params_returns_original():
    jpeg = _make_jpeg_bytes(400, 600)
    with patch("app.routers.images.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(jpeg))
        mock_client_cls.return_value = mock_client

        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg"
        )

    assert response.status_code == 200
    assert len(response.content) == len(jpeg)


def test_resize_only_width_keeps_aspect_ratio():
    from PIL import Image
    jpeg = _make_jpeg_bytes(400, 200)
    with patch("app.routers.images.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(jpeg))
        mock_client_cls.return_value = mock_client

        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/img.jpg&width=200"
        )

    result_img = Image.open(io.BytesIO(response.content))
    assert result_img.size == (200, 100)


# ── 에러 처리 ─────────────────────────────────────────────────

def test_resize_missing_url_returns_422():
    response = create_test_client().get("/api/images/resize?width=200&height=300")
    assert response.status_code == 422


def test_resize_invalid_content_type_returns_415():
    with patch("app.routers.images.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(b"not an image", "text/html"))
        mock_client_cls.return_value = mock_client

        response = create_test_client().get(
            "/api/images/resize?url=http://example.com/page.html&width=200&height=300"
        )

    assert response.status_code == 415


def test_resize_width_exceeds_limit_returns_422():
    response = create_test_client().get(
        "/api/images/resize?url=http://example.com/img.jpg&width=9999"
    )
    assert response.status_code == 422
