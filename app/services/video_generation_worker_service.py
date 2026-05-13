from dataclasses import dataclass

from app.models.video_generation_job import VideoGenerationJob
from app.services.video_generation_provider import VideoGenerationProvider
from app.services.video_generation_service import VideoGenerationService


@dataclass(frozen=True)
class VideoGenerationWorkerResult:
    job: VideoGenerationJob


class VideoGenerationWorkerService:
    def __init__(
        self,
        *,
        generation_service: VideoGenerationService,
        provider: VideoGenerationProvider,
    ) -> None:
        self.generation_service = generation_service
        self.provider = provider

    def run(self, *, job_id: int) -> VideoGenerationWorkerResult:
        job = self.generation_service.start_generation(job_id=job_id)

        try:
            provider_result = self.provider.generate(job.input_snapshot)
        except Exception:
            failed_job = self.generation_service.mark_generation_failed(
                job_id=job.id,
                error_code="PROVIDER_ERROR",
                error_message="영상 생성 provider 실행에 실패했습니다.",
            )
            return VideoGenerationWorkerResult(job=failed_job)

        succeeded_job = self.generation_service.mark_generation_succeeded(
            job_id=job.id,
            output_url=provider_result.output_url,
            thumbnail_url=provider_result.thumbnail_url,
            provider_job_id=provider_result.provider_job_id,
        )
        return VideoGenerationWorkerResult(job=succeeded_job)
