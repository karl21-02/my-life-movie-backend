import pytest
import httpx

from app.core.config import Settings
from app.services.video_generation_provider import (
    FalVideoGenerationProvider,
    MockVideoGenerationProvider,
    VideoGenerationProviderConfigError,
    build_fal_payload,
    build_video_generation_provider,
)


pytestmark = pytest.mark.unit


def test_mock_video_generation_provider_returns_deterministic_result():
    provider = MockVideoGenerationProvider()
    input_snapshot = {"provider_prompt": "warm cinematic life story"}

    first = provider.generate(input_snapshot)
    second = provider.generate(input_snapshot)

    assert first == second
    assert first.provider_job_id.startswith("mock_")
    assert first.output_url.endswith(".mp4")
    assert first.thumbnail_url is not None
    assert first.thumbnail_url.endswith(".jpg")


def test_build_fal_payload_uses_generation_prompt_defaults():
    payload = build_fal_payload({"provider_prompt": "warm cinematic life story"})

    assert payload["prompt"] == "warm cinematic life story"
    assert payload["resolution"] == "480p"
    assert payload["aspect_ratio"] == "16:9"
    assert payload["video_output_type"] == "X264 (.mp4)"


def test_fal_video_generation_provider_submits_polls_and_reads_result():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "request_id": "fal-request-1",
                    "status_url": "https://queue.test/fal-ai/wan-alpha/requests/fal-request-1/status",
                    "response_url": "https://queue.test/fal-ai/wan-alpha/requests/fal-request-1/response",
                },
            )
        if request.url.path.endswith("/status"):
            return httpx.Response(
                200,
                json={
                    "status": "COMPLETED",
                    "response_url": "https://queue.test/fal-ai/wan-alpha/requests/fal-request-1/response",
                },
            )
        return httpx.Response(
            200,
            json={
                "video": {"url": "https://v3.fal.media/files/movie.mp4"},
                "image": {"url": "https://v3.fal.media/files/thumbnail.jpg"},
            },
        )

    provider = FalVideoGenerationProvider(
        api_key="test-key",
        model_id="fal-ai/wan-alpha",
        queue_base_url="https://queue.test",
        poll_interval_seconds=0,
        max_wait_seconds=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.generate({"provider_prompt": "warm cinematic life story"})

    assert result.provider_job_id == "fal-request-1"
    assert result.output_url == "https://v3.fal.media/files/movie.mp4"
    assert result.thumbnail_url == "https://v3.fal.media/files/thumbnail.jpg"
    assert requests[0].headers["authorization"] == "Key test-key"
    assert requests[0].url == "https://queue.test/fal-ai/wan-alpha"


def test_build_video_generation_provider_auto_uses_mock_without_fal_key():
    provider = build_video_generation_provider(Settings(video_generation_provider="auto", fal_key=""))

    assert isinstance(provider, MockVideoGenerationProvider)


def test_build_video_generation_provider_auto_uses_fal_with_fal_key():
    provider = build_video_generation_provider(
        Settings(
            video_generation_provider="auto",
            fal_key="test-key",
            fal_queue_base_url="https://queue.test",
            fal_poll_interval_seconds=0,
            fal_max_wait_seconds=1,
        )
    )

    assert isinstance(provider, FalVideoGenerationProvider)


def test_fal_video_generation_provider_requires_api_key():
    with pytest.raises(VideoGenerationProviderConfigError):
        FalVideoGenerationProvider(
            api_key="",
            model_id="fal-ai/wan-alpha",
            queue_base_url="https://queue.test",
            poll_interval_seconds=0,
            max_wait_seconds=1,
        )
