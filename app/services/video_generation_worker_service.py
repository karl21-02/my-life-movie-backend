from dataclasses import dataclass

from app.core.errors import AppError
from app.core.logging import get_logger
from app.models.video_generation_job import VideoGenerationJob, VideoGenerationJobStatus
from app.services.video_generation_provider import VideoGenerationProvider
from app.services.video_generation_queue import QueueMessage, VideoGenerationQueue
from app.services.video_generation_service import VideoGenerationService

logger = get_logger(__name__)

# 워커 크래시로 회수된 진행중(RUNNING) job에 기록하는 실패 코드
WORKER_CRASHED_ERROR_CODE = "WORKER_CRASHED"
_WORKER_CRASHED_MESSAGE = "워커 중단으로 작업이 회수되었습니다."


@dataclass(frozen=True)
class VideoGenerationWorkerResult:
    job: VideoGenerationJob


class VideoGenerationWorkerService:
    def __init__(
        self,
        *,
        generation_service: VideoGenerationService,
        provider: VideoGenerationProvider,
        queue: VideoGenerationQueue,
    ) -> None:
        self.generation_service = generation_service
        self.provider = provider
        self.queue = queue

    def process_message(
        self,
        message: QueueMessage,
        *,
        reclaimed: bool = False,
    ) -> VideoGenerationWorkerResult | None:
        """스트림 entry 하나를 처리한다.

        reclaimed=False: XREADGROUP로 갓 받은 신규 entry.
        reclaimed=True: XAUTOCLAIM으로 회수한 entry (죽은 워커가 놓친 것).
        """
        if reclaimed:
            return self._process_reclaimed(message)
        return self._process_new(message)

    def _process_new(self, message: QueueMessage) -> VideoGenerationWorkerResult | None:
        claimed = self.generation_service.claim_generation(job_id=message.job_id)
        if claimed is None:
            # 이미 다른 워커가 claim 했거나 QUEUED 상태가 아님 — 양보하고 정리
            self.queue.ack(message.message_id)
            return None
        return self._run_claimed(claimed, message)

    def _process_reclaimed(self, message: QueueMessage) -> VideoGenerationWorkerResult | None:
        job = self.generation_service.get_job(job_id=message.job_id)
        if job is None:
            self.queue.ack(message.message_id)
            return None

        if job.status == VideoGenerationJobStatus.QUEUED:
            # 워커가 claim 전에 죽음 — 아직 시작 안 했으니 정상 처리해도 안전
            claimed = self.generation_service.claim_generation(job_id=message.job_id)
            if claimed is None:
                self.queue.ack(message.message_id)
                return None
            return self._run_claimed(claimed, message)

        if job.status == VideoGenerationJobStatus.RUNNING:
            # 워커가 실행 중 죽음 — 재실행하지 않고 실패 처리 (provider 중복 호출 방지)
            failed = self._fail_crashed(message.job_id)
            self.queue.ack(message.message_id)
            return VideoGenerationWorkerResult(job=failed) if failed is not None else None

        # 이미 종료 상태(SUCCEEDED/FAILED/CANCELED) — entry만 정리
        self.queue.ack(message.message_id)
        return None

    def _run_claimed(
        self,
        job: VideoGenerationJob,
        message: QueueMessage,
    ) -> VideoGenerationWorkerResult | None:
        try:
            provider_result = self.provider.generate(
                job.input_snapshot,
                progress_callback=lambda progress, provider_job_id: self._record_progress(
                    job_id=job.id,
                    progress=progress,
                    provider_job_id=provider_job_id,
                ),
            )
        except Exception as exc:
            result = self._mark_failed(job, exc)
            self.queue.ack(message.message_id)
            return result

        result = self._mark_succeeded(job, provider_result)
        self.queue.ack(message.message_id)
        return result

    def _mark_succeeded(self, job, provider_result) -> VideoGenerationWorkerResult | None:
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

    def _mark_failed(self, job, exc: Exception) -> VideoGenerationWorkerResult | None:
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
        except AppError as app_exc:
            self._log_skipped_job(job_id=job.id, exc=app_exc)
            return None
        return VideoGenerationWorkerResult(job=failed_job)

    def _fail_crashed(self, job_id: int) -> VideoGenerationJob | None:
        logger.warning(
            "중단된 영상 생성 Job을 회수해 실패 처리합니다.",
            extra={
                "event": "video_generation_job_reclaimed_failed",
                "job_id": job_id,
                "error_code": WORKER_CRASHED_ERROR_CODE,
            },
        )
        try:
            return self.generation_service.mark_generation_failed(
                job_id=job_id,
                error_code=WORKER_CRASHED_ERROR_CODE,
                error_message=_WORKER_CRASHED_MESSAGE,
            )
        except AppError as exc:
            self._log_skipped_job(job_id=job_id, exc=exc)
            return None

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

    def _record_progress(
        self,
        *,
        job_id: int,
        progress: int,
        provider_job_id: str | None,
    ) -> None:
        try:
            self.generation_service.update_generation_progress(
                job_id=job_id,
                progress=progress,
                provider_job_id=provider_job_id,
            )
        except AppError as exc:
            self._log_skipped_job(job_id=job_id, exc=exc)


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
