from dataclasses import dataclass
from hashlib import sha256
import time
from typing import Protocol

import httpx

from app.core.config import Settings


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
    if provider == "auto":
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


def require_string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise VideoGenerationProviderError(f"fal 응답에 {key} 값이 없습니다.")
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
