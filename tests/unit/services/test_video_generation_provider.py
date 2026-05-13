from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.services.video_generation_provider import (
    FalVideoGenerationProvider,
    MockVideoGenerationProvider,
    OpenAIVideoGenerationProvider,
    VideoGenerationProviderConfigError,
    VideoGenerationProviderError,
    build_fal_payload,
    build_openai_video_prompt,
    build_video_generation_provider,
    resolve_video_generation_provider_name,
)
from app.services.storage_service import LocalStorageService


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


def test_build_openai_video_prompt_requires_provider_prompt():
    assert build_openai_video_prompt({"provider_prompt": "cinematic story"}) == "cinematic story"

    with pytest.raises(VideoGenerationProviderError, match="provider_prompt"):
        build_openai_video_prompt({"provider_prompt": ""})


def test_openai_video_generation_provider_polls_downloads_and_returns_static_paths(tmp_path):
    class FakeBinaryContent:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def write_to_file(self, path: str) -> None:
            with open(path, "wb") as file:
                file.write(self.payload)

    class FakeVideos:
        def __init__(self) -> None:
            self.retrieve_count = 0
            self.downloads: list[str] = []

        def create(self, **kwargs):
            assert kwargs == {
                "model": "sora-2",
                "prompt": "warm cinematic life story",
                "size": "1280x720",
                "seconds": "4",
            }
            return SimpleNamespace(id="video_123", status="queued")

        def retrieve(self, video_id: str):
            self.retrieve_count += 1
            assert video_id == "video_123"
            return SimpleNamespace(id="video_123", status="completed")

        def download_content(self, video_id: str, *, variant: str):
            assert video_id == "video_123"
            self.downloads.append(variant)
            return FakeBinaryContent(f"{variant}-content".encode("utf-8"))

    class FakeClient:
        def __init__(self) -> None:
            self.videos = FakeVideos()

    client = FakeClient()
    provider = OpenAIVideoGenerationProvider(
        api_key="test-key",
        model="sora-2",
        size="1280x720",
        seconds="4",
        poll_interval_seconds=0,
        max_wait_seconds=1,
        storage=LocalStorageService(root_dir=str(tmp_path / "generated"), public_base_url="/generated"),
        video_prefix="videos",
        thumbnail_prefix="thumbnails",
        client=client,
    )

    result = provider.generate({"provider_prompt": "warm cinematic life story"})

    assert result.provider_job_id == "video_123"
    assert result.output_url == "/generated/videos/video_123.mp4"
    assert result.thumbnail_url == "/generated/thumbnails/video_123.webp"
    assert (tmp_path / "generated/videos/video_123.mp4").read_bytes() == b"video-content"
    assert (tmp_path / "generated/thumbnails/video_123.webp").read_bytes() == b"thumbnail-content"
    assert client.videos.downloads == ["video", "thumbnail"]


def test_build_video_generation_provider_auto_uses_mock_without_fal_key():
    provider = build_video_generation_provider(Settings(video_generation_provider="auto", fal_key=""))

    assert isinstance(provider, MockVideoGenerationProvider)
    assert resolve_video_generation_provider_name(Settings(video_generation_provider="auto", fal_key="")) == "mock"


def test_build_video_generation_provider_auto_uses_openai_with_openai_key():
    provider = build_video_generation_provider(
        Settings(
            video_generation_provider="auto",
            openai_api_key="test-key",
            openai_video_poll_interval_seconds=0,
            openai_video_max_wait_seconds=1,
        )
    )

    assert isinstance(provider, OpenAIVideoGenerationProvider)
    assert resolve_video_generation_provider_name(
        Settings(video_generation_provider="auto", openai_api_key="test-key")
    ) == "openai"


def test_build_video_generation_provider_auto_uses_fal_with_fal_key():
    provider = build_video_generation_provider(
        Settings(
            video_generation_provider="auto",
            openai_api_key="",
            fal_key="test-key",
            fal_queue_base_url="https://queue.test",
            fal_poll_interval_seconds=0,
            fal_max_wait_seconds=1,
        )
    )

    assert isinstance(provider, FalVideoGenerationProvider)
    assert resolve_video_generation_provider_name(
        Settings(video_generation_provider="auto", openai_api_key="", fal_key="test-key")
    ) == "fal"


def test_fal_video_generation_provider_requires_api_key():
    with pytest.raises(VideoGenerationProviderConfigError):
        FalVideoGenerationProvider(
            api_key="",
            model_id="fal-ai/wan-alpha",
            queue_base_url="https://queue.test",
            poll_interval_seconds=0,
            max_wait_seconds=1,
        )


def test_openai_video_generation_provider_requires_api_key():
    with pytest.raises(VideoGenerationProviderConfigError):
        OpenAIVideoGenerationProvider(
            api_key="",
            model="sora-2",
            size="1280x720",
            seconds="4",
            poll_interval_seconds=0,
            max_wait_seconds=1,
            storage=LocalStorageService(root_dir="generated", public_base_url="/generated"),
            video_prefix="videos",
            thumbnail_prefix="thumbnails",
        )
