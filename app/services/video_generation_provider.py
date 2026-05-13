from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol


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
