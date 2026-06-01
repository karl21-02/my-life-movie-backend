import io

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from PIL import Image

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])

# 허용되는 이미지 Content-Type
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# 리사이징 최대 크기 제한
_MAX_DIMENSION = 2000


@router.get(
    "/resize",
    summary="이미지 리사이징",
    description="URL로 지정된 이미지를 width, height 파라미터에 맞게 리사이징하여 반환합니다. "
                "파라미터 미입력 시 원본 이미지를 그대로 반환합니다.",
)
async def resize_image(
    url: str = Query(..., description="리사이징할 이미지 URL"),
    width: int | None = Query(None, gt=0, le=_MAX_DIMENSION, description="출력 너비 (px)"),
    height: int | None = Query(None, gt=0, le=_MAX_DIMENSION, description="출력 높이 (px)"),
) -> StreamingResponse:
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
    except Exception as e:
        logger.warning("image_resize_error", extra={"url": url, "error": str(e)})
        raise HTTPException(status_code=500, detail="이미지 리사이징에 실패했습니다.")

    logger.info(
        "image_resized",
        extra={"url": url, "width": width, "height": height},
    )
    return StreamingResponse(output, media_type=content_type)


def _pil_format(content_type: str) -> str:
    return {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
        "image/gif": "GIF",
    }.get(content_type, "JPEG")
