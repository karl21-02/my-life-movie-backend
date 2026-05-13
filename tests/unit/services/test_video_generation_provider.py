import pytest

from app.services.video_generation_provider import MockVideoGenerationProvider


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
