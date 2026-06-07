import io
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])

# 허용되는 이미지 Content-Type
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# 리사이징 최대 크기 제한
_MAX_DIMENSION = 2000

# 원본 이미지 최대 바이트 (10MB) — 과대 응답 차단
_MAX_SOURCE_BYTES = 10 * 1024 * 1024

# 디코딩 허용 최대 픽셀 수 — decompression bomb 차단
_MAX_IMAGE_PIXELS = 40_000_000


@router.get(
    "/resize",
    summary="이미지 리사이징",
    description="S3에 저장된 이미지를 width, height 파라미터에 맞게 리사이징하여 반환합니다. "
                "파라미터 미입력 시 원본 이미지를 그대로 반환합니다.",
)
async def resize_image(
    url: str = Query(..., description="리사이징할 이미지 URL (S3 공개 base URL 하위만 허용)"),
    width: int | None = Query(None, gt=0, le=_MAX_DIMENSION, description="출력 너비 (px)"),
    height: int | None = Query(None, gt=0, le=_MAX_DIMENSION, description="출력 높이 (px)"),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    # SSRF 방지: 설정된 S3 공개 base URL 하위 자원만 허용
    if not _is_allowed_url(url, settings.s3_public_base_url):
        logger.warning("image_url_not_allowed", extra={"url": url})
        raise HTTPException(status_code=400, detail="허용되지 않은 이미지 URL입니다.")

    # 원본 이미지 fetch
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.warning("image_fetch_http_error", extra={"url": url, "status": e.response.status_code})
        raise HTTPException(status_code=502, detail="이미지를 가져오는 데 실패했습니다.")
    except httpx.RequestError as e:
        logger.warning("image_fetch_request_error", extra={"url": url, "error": str(e)})
        raise HTTPException(status_code=502, detail="이미지 URL에 접근할 수 없습니다.")

    # DoS 방지: 과대 원본 거부 (헤더 + 실제 바이트 양쪽 확인)
    declared_length = response.headers.get("content-length")
    if declared_length and declared_length.isdigit() and int(declared_length) > _MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="이미지 용량이 너무 큽니다.")
    if len(response.content) > _MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="이미지 용량이 너무 큽니다.")

    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"지원하지 않는 이미지 형식입니다: {content_type}")

    # width, height 미입력 시 원본 반환
    if width is None and height is None:
        return StreamingResponse(
            io.BytesIO(response.content),
            media_type=content_type,
        )

    # Pillow로 리사이징
    try:
        image = Image.open(io.BytesIO(response.content))
        _reject_oversized_pixels(image)
        original_width, original_height = image.size

        # 한쪽만 입력된 경우 비율 유지
        if width is None:
            width = int(original_width * height / original_height)
        elif height is None:
            height = int(original_height * width / original_width)

        resized = image.resize((width, height), Image.LANCZOS)

        output = io.BytesIO()
        fmt = _pil_format(content_type)
        resized.save(output, format=fmt)
        output.seek(0)
    except Image.DecompressionBombError:
        logger.warning("image_decompression_bomb", extra={"url": url})
        raise HTTPException(status_code=413, detail="이미지 용량이 너무 큽니다.")
    except UnidentifiedImageError:
        raise HTTPException(status_code=415, detail="이미지를 인식할 수 없습니다.")
    except Exception as e:
        logger.warning("image_resize_error", extra={"url": url, "error": str(e)})
        raise HTTPException(status_code=500, detail="이미지 리사이징에 실패했습니다.")

    logger.info(
        "image_resized",
        extra={"url": url, "width": width, "height": height},
    )
    return StreamingResponse(output, media_type=content_type)


def _is_allowed_url(url: str, base_url: str) -> bool:
    """url이 설정된 S3 공개 base URL과 같은 scheme/host 하위인지 검사한다."""
    if not base_url:
        return False
    base = urlsplit(base_url)
    target = urlsplit(url)
    if target.scheme not in ("http", "https"):
        return False
    if target.scheme != base.scheme or target.netloc.lower() != base.netloc.lower():
        return False
    # base에 경로가 있으면 그 하위 경로만 허용
    base_path = base.path.rstrip("/")
    if base_path and not target.path.startswith(base_path + "/") and target.path != base_path:
        return False
    return True


def _reject_oversized_pixels(image: Image.Image) -> None:
    width, height = image.size
    if width * height > _MAX_IMAGE_PIXELS:
        raise Image.DecompressionBombError(
            f"image pixels {width * height} exceed limit {_MAX_IMAGE_PIXELS}"
        )


def _pil_format(content_type: str) -> str:
    return {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
        "image/gif": "GIF",
    }.get(content_type, "JPEG")
