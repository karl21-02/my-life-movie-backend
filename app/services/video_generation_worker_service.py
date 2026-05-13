from dataclasses import dataclass

from app.core.errors import AppError
from app.core.logging import get_logger
from app.models.video_generation_job import VideoGenerationJob
from app.services.video_generation_provider import VideoGenerationProvider
from app.services.video_generation_service import VideoGenerationService

logger = get_logger(__name__)


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

    def run(self, *, job_id: int) -> VideoGenerationWorkerResult | None:
        try:
            job = self.generation_service.start_generation(job_id=job_id)
        except AppError as exc:
            self._log_skipped_job(job_id=job_id, exc=exc)
            return None

        try:
            provider_result = self.provider.generate(job.input_snapshot)
        except Exception as exc:
            provider_job_id = getattr(exc, "provider_job_id", None)
            error_message = sanitize_provider_error_message(exc)
            logger.warning(
                "영상 생성 provider 실행에 실패했습니다.",
                extra={
                    "event": "video_generation_provider_failed",
                    "job_id": job.id,
                    "movie_id": job.movie_id,
                    "provider_job_id": provider_job_id,
                    "error_type": type(exc).__name__,
                    "error_code": provider_error_code(error_message),
                },
            )
            try:
                failed_job = self.generation_service.mark_generation_failed(
                    job_id=job.id,
                    error_code=provider_error_code(error_message),
                    error_message=error_message,
                    provider_job_id=provider_job_id,
                )
            except AppError as exc:
                self._log_skipped_job(job_id=job.id, exc=exc)
                return None
            return VideoGenerationWorkerResult(job=failed_job)

        try:
            succeeded_job = self.generation_service.mark_generation_succeeded(
                job_id=job.id,
                output_url=provider_result.output_url,
                thumbnail_url=provider_result.thumbnail_url,
                provider_job_id=provider_result.provider_job_id,
            )
        except AppError as exc:
            self._log_skipped_job(job_id=job.id, exc=exc)
            return None
        return VideoGenerationWorkerResult(job=succeeded_job)

    def run_next(self) -> VideoGenerationWorkerResult | None:
        job = self.generation_service.get_next_queued_generation()
        if job is None:
            return None
        return self.run(job_id=job.id)

    def _log_skipped_job(self, *, job_id: int, exc: AppError) -> None:
        logger.warning(
            "영상 생성 Job 상태 반영을 건너뜁니다.",
            extra={
                "event": "video_generation_job_skipped",
                "job_id": job_id,
                "error_code": exc.code,
                "error_type": exc.type,
            },
        )


def sanitize_provider_error_message(exc: Exception) -> str:
    message = str(exc).strip() or "영상 생성 provider 실행에 실패했습니다."
    return message[:500]


def provider_error_code(message: str) -> str:
    normalized = message.lower()
    if "moderation_blocked" in normalized or "moderation" in normalized:
        return "PROVIDER_MODERATION_BLOCKED"
    if "timeout" in normalized or "시간이 초과" in normalized:
        return "PROVIDER_TIMEOUT"
    return "PROVIDER_ERROR"
