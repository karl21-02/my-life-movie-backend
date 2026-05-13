from dataclasses import dataclass
from hashlib import sha256
import re
import tempfile
import time
from typing import Protocol

import httpx
from openai import OpenAI

from app.core.config import Settings
from app.services.storage_service import (
    StoredObject,
    StorageService,
    build_storage_key,
    build_storage_service,
)


@dataclass(frozen=True)
class VideoGenerationProviderResult:
    provider_job_id: str
    output_url: str
    thumbnail_url: str | None = None


class VideoGenerationProvider(Protocol):
    def generate(self, input_snapshot: dict) -> VideoGenerationProviderResult:
        ...


class MockVideoGenerationProvider:
    def generate(self, input_snapshot: dict) -> VideoGenerationProviderResult:
        prompt = str(input_snapshot.get("provider_prompt") or "my-life-movie")
        digest = sha256(prompt.encode("utf-8")).hexdigest()[:16]
        return VideoGenerationProviderResult(
            provider_job_id=f"mock_{digest}",
            output_url=f"https://cdn.mylifemovie.local/videos/{digest}.mp4",
            thumbnail_url=f"https://cdn.mylifemovie.local/thumbnails/{digest}.jpg",
        )


class FalVideoGenerationProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model_id: str,
        queue_base_url: str,
        poll_interval_seconds: float,
        max_wait_seconds: int,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise VideoGenerationProviderConfigError("FAL_KEY 환경 변수가 필요합니다.")

        self.api_key = api_key
        self.model_id = model_id.strip("/")
        self.queue_base_url = queue_base_url.rstrip("/")
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds
        self.client = client or httpx.Client(timeout=60)

    def generate(self, input_snapshot: dict) -> VideoGenerationProviderResult:
        payload = build_fal_payload(input_snapshot)
        submit_data = self._post_json(self._model_url(), payload)
        request_id = require_string(submit_data, "request_id")
        status_url = submit_data.get("status_url") or self._status_url(request_id)
        response_url = submit_data.get("response_url") or self._response_url(request_id)

        completed_status = self._wait_until_completed(str(status_url))
        if completed_status.get("error"):
            raise VideoGenerationProviderError(str(completed_status["error"]))

        result_data = unwrap_result_data(self._get_json(str(completed_status.get("response_url") or response_url)))
        output_url = extract_video_url(result_data)
        thumbnail_url = extract_thumbnail_url(result_data)
        return VideoGenerationProviderResult(
            provider_job_id=request_id,
            output_url=output_url,
            thumbnail_url=thumbnail_url,
        )

    def _wait_until_completed(self, status_url: str) -> dict:
        deadline = time.monotonic() + self.max_wait_seconds
        last_status: dict | None = None
        while time.monotonic() <= deadline:
            status_data = self._get_json(status_url)
            last_status = status_data
            status = status_data.get("status")
            if status == "COMPLETED":
                return status_data
            if status not in {"IN_QUEUE", "IN_PROGRESS"}:
                raise VideoGenerationProviderError(f"fal queue 상태를 처리할 수 없습니다: {status}")
            time.sleep(self.poll_interval_seconds)

        raise VideoGenerationProviderTimeoutError(
            f"fal 영상 생성 대기 시간이 초과되었습니다. 마지막 상태: {last_status}"
        )

    def _post_json(self, url: str, payload: dict) -> dict:
        response = self.client.post(url, headers=self._headers(), json=payload)
        response.raise_for_status()
        return response.json()

    def _get_json(self, url: str) -> dict:
        response = self.client.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

    def _model_url(self) -> str:
        return f"{self.queue_base_url}/{self.model_id}"

    def _status_url(self, request_id: str) -> str:
        return f"{self._model_url()}/requests/{request_id}/status"

    def _response_url(self, request_id: str) -> str:
        return f"{self._model_url()}/requests/{request_id}/response"


class OpenAIVideoGenerationProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        size: str,
        seconds: str,
        poll_interval_seconds: float,
        max_wait_seconds: int,
        storage: StorageService,
        video_prefix: str,
        thumbnail_prefix: str,
        client: OpenAI | None = None,
    ) -> None:
        if not api_key:
            raise VideoGenerationProviderConfigError("OPENAI_API_KEY 환경 변수가 필요합니다.")

        self.model = model
        self.size = size
        self.seconds = seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds
        self.storage = storage
        self.video_prefix = video_prefix
        self.thumbnail_prefix = thumbnail_prefix
        self.client = client or OpenAI(api_key=api_key)

    def generate(self, input_snapshot: dict) -> VideoGenerationProviderResult:
        prompt = build_openai_video_prompt(input_snapshot)
        video = self.client.videos.create(
            model=self.model,
            prompt=prompt,
            size=self.size,
            seconds=self.seconds,
        )
        completed_video = self._wait_until_completed(video)
        video_id = require_object_attr(completed_video, "id", "OpenAI 영상 응답에 id 값이 없습니다.")

        video_object = self._download_variant(
            video_id=video_id,
            variant="video",
            prefix=self.video_prefix,
            extension="mp4",
        )
        thumbnail_object = self._download_thumbnail(video_id)
        return VideoGenerationProviderResult(
            provider_job_id=video_id,
            output_url=video_object.url,
            thumbnail_url=thumbnail_object.url if thumbnail_object is not None else None,
        )

    def _wait_until_completed(self, video: object) -> object:
        deadline = time.monotonic() + self.max_wait_seconds
        current_video = video
        while time.monotonic() <= deadline:
            status = getattr(current_video, "status", None)
            if status == "completed":
                return current_video
            if status == "failed":
                raise VideoGenerationProviderError(openai_video_error_message(current_video))
            if status not in {"queued", "in_progress"}:
                raise VideoGenerationProviderError(f"OpenAI 영상 생성 상태를 처리할 수 없습니다: {status}")

            time.sleep(self.poll_interval_seconds)
            video_id = require_object_attr(current_video, "id", "OpenAI 영상 응답에 id 값이 없습니다.")
            current_video = self.client.videos.retrieve(video_id)

        raise VideoGenerationProviderTimeoutError("OpenAI 영상 생성 대기 시간이 초과되었습니다.")

    def _download_thumbnail(self, video_id: str) -> StoredObject | None:
        try:
            return self._download_variant(
                video_id=video_id,
                variant="thumbnail",
                prefix=self.thumbnail_prefix,
                extension="webp",
            )
        except Exception:
            return None

    def _download_variant(
        self,
        *,
        video_id: str,
        variant: str,
        prefix: str,
        extension: str,
    ) -> StoredObject:
        key = build_storage_key(prefix, f"{safe_generated_filename(video_id)}.{extension}")
        content = self.client.videos.download_content(video_id, variant=variant)
        return self.storage.put_bytes(
            key,
            read_binary_response(content),
            content_type=content_type_for_extension(extension),
        )


class VideoGenerationProviderError(RuntimeError):
    pass


class VideoGenerationProviderConfigError(VideoGenerationProviderError):
    pass


class VideoGenerationProviderTimeoutError(VideoGenerationProviderError):
    pass


def build_video_generation_provider(settings: Settings) -> VideoGenerationProvider:
    provider = settings.video_generation_provider
    if provider == "mock":
        return MockVideoGenerationProvider()
    if provider == "fal":
        return build_fal_video_generation_provider(settings)
    if provider == "openai":
        return build_openai_video_generation_provider(settings)
    if provider == "auto":
        if settings.openai_api_key:
            return build_openai_video_generation_provider(settings)
        if settings.fal_key:
            return build_fal_video_generation_provider(settings)
        return MockVideoGenerationProvider()

    raise VideoGenerationProviderConfigError(f"지원하지 않는 영상 생성 provider입니다: {provider}")


def build_fal_video_generation_provider(settings: Settings) -> FalVideoGenerationProvider:
    return FalVideoGenerationProvider(
        api_key=settings.fal_key,
        model_id=settings.fal_model_id,
        queue_base_url=settings.fal_queue_base_url,
        poll_interval_seconds=settings.fal_poll_interval_seconds,
        max_wait_seconds=settings.fal_max_wait_seconds,
    )


def build_openai_video_generation_provider(settings: Settings) -> OpenAIVideoGenerationProvider:
    video_prefix = settings.s3_generated_video_prefix if settings.storage_provider == "s3" else "videos"
    thumbnail_prefix = settings.s3_generated_thumbnail_prefix if settings.storage_provider == "s3" else "thumbnails"
    return OpenAIVideoGenerationProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_video_model,
        size=settings.openai_video_size,
        seconds=settings.openai_video_seconds,
        poll_interval_seconds=settings.openai_video_poll_interval_seconds,
        max_wait_seconds=settings.openai_video_max_wait_seconds,
        storage=build_storage_service(settings),
        video_prefix=video_prefix,
        thumbnail_prefix=thumbnail_prefix,
    )


def build_fal_payload(input_snapshot: dict) -> dict:
    prompt = str(input_snapshot.get("provider_prompt") or "").strip()
    if not prompt:
        raise VideoGenerationProviderError("provider_prompt가 비어 있어 영상을 생성할 수 없습니다.")

    return {
        "prompt": prompt,
        "num_frames": 81,
        "fps": 16,
        "num_inference_steps": 8,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "enable_safety_checker": True,
        "video_output_type": "X264 (.mp4)",
        "video_quality": "medium",
        "video_write_mode": "balanced",
    }


def build_openai_video_prompt(input_snapshot: dict) -> str:
    prompt = str(input_snapshot.get("provider_prompt") or "").strip()
    if not prompt:
        raise VideoGenerationProviderError("provider_prompt가 비어 있어 영상을 생성할 수 없습니다.")
    return prompt


def require_string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise VideoGenerationProviderError(f"fal 응답에 {key} 값이 없습니다.")
    return value


def require_object_attr(target: object, attr_name: str, error_message: str) -> str:
    value = getattr(target, attr_name, None)
    if not isinstance(value, str) or not value:
        raise VideoGenerationProviderError(error_message)
    return value


def extract_video_url(data: dict) -> str:
    video = data.get("video")
    if isinstance(video, dict) and isinstance(video.get("url"), str):
        return video["url"]

    video_url = data.get("video_url")
    if isinstance(video_url, str):
        return video_url

    raise VideoGenerationProviderError("fal 결과에서 영상 URL을 찾을 수 없습니다.")


def extract_thumbnail_url(data: dict) -> str | None:
    image = data.get("image")
    if isinstance(image, dict) and isinstance(image.get("url"), str):
        return image["url"]

    thumbnail_url = data.get("thumbnail_url")
    if isinstance(thumbnail_url, str):
        return thumbnail_url

    return None


def unwrap_result_data(data: dict) -> dict:
    nested_data = data.get("data")
    if isinstance(nested_data, dict):
        return nested_data
    return data


def safe_generated_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", value).strip("._") or "video"


def read_binary_response(content: object) -> bytes:
    if hasattr(content, "write_to_file"):
        with tempfile.NamedTemporaryFile() as file:
            content.write_to_file(file.name)
            return file.read()

    if isinstance(content, (bytes, bytearray)):
        return bytes(content)

    response_content = getattr(content, "content", None)
    if isinstance(response_content, (bytes, bytearray)):
        return bytes(response_content)

    if hasattr(content, "read"):
        return content.read()

    raise VideoGenerationProviderError("OpenAI 영상 다운로드 응답을 bytes로 변환할 수 없습니다.")


def content_type_for_extension(extension: str) -> str:
    if extension == "mp4":
        return "video/mp4"
    if extension == "webp":
        return "image/webp"
    return "application/octet-stream"


def openai_video_error_message(video: object) -> str:
    error = getattr(video, "error", None)
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message

    message = getattr(error, "message", None)
    if isinstance(message, str) and message:
        return message

    return "OpenAI 영상 생성에 실패했습니다."
