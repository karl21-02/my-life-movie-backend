from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import AppError
from app.models.movie import MovieStatus
from app.models.video_generation_job import VideoGenerationJob, VideoGenerationJobStatus
from app.repositories.movie_repository import MovieRepository
from app.repositories.video_generation_job_repository import VideoGenerationJobRepository
from app.services.video_generation_input_builder import build_video_generation_input
from app.services.video_generation_queue import VideoGenerationQueue


@dataclass(frozen=True)
class VideoGenerationRequestResult:
    job: VideoGenerationJob


class VideoGenerationService:
    def __init__(
        self,
        *,
        movie_repository: MovieRepository,
        job_repository: VideoGenerationJobRepository,
        provider_name: str = "mock",
        queue: VideoGenerationQueue | None = None,
    ) -> None:
        self.movie_repository = movie_repository
        self.job_repository = job_repository
        self.provider_name = provider_name
        self.queue = queue

    def request_generation(self, *, movie_id: int, user_id: int) -> VideoGenerationRequestResult:
        if self.queue is None:
            raise RuntimeError("영상 생성 요청에는 queue가 필요합니다.")

        movie = self.movie_repository.get_by_id(movie_id)
        if movie is None:
            raise generation_movie_not_found_error()
        if movie.user_id != user_id:
            raise generation_movie_forbidden_error()
        if not movie.generation_prompt:
            raise generation_input_not_ready_error()

        in_progress_job = self.job_repository.get_in_progress_by_movie_id(movie_id)
        if in_progress_job is not None:
            raise generation_already_in_progress_error()

        input_snapshot = build_video_generation_input(movie)
        job = self.job_repository.create(
            movie_id=movie.id,
            user_id=user_id,
            input_snapshot=input_snapshot,
            provider=self.provider_name,
        )
        self.queue.enqueue(job.id)
        movie.status = MovieStatus.GENERATING
        self.movie_repository.update(movie)
        return VideoGenerationRequestResult(job=job)

    def claim_generation(self, *, job_id: int) -> VideoGenerationJob | None:
        """QUEUED job을 원자적으로 RUNNING으로 전환한다. 이미 뺏겼으면 None."""
        return self.job_repository.claim(job_id)

    def get_job(self, *, job_id: int) -> VideoGenerationJob | None:
        return self.job_repository.get_by_id(job_id)

    def get_latest_generation(self, *, movie_id: int, user_id: int) -> VideoGenerationJob:
        movie = self.movie_repository.get_by_id(movie_id)
        if movie is None:
            raise generation_movie_not_found_error()
        if movie.user_id != user_id:
            raise generation_movie_forbidden_error()

        job = self.job_repository.get_latest_by_movie_id(movie_id)
        if job is None:
            raise generation_job_not_found_error()
        return job

    def get_next_queued_generation(self) -> VideoGenerationJob | None:
        return self.job_repository.get_next_queued()

    def start_generation(self, *, job_id: int, provider_job_id: str | None = None) -> VideoGenerationJob:
        job = self._get_job_or_raise(job_id)
        self._ensure_status(job, allowed=(VideoGenerationJobStatus.QUEUED,))

        job.status = VideoGenerationJobStatus.RUNNING
        job.progress = max(job.progress, 1)
        job.provider_job_id = provider_job_id
        job.started_at = now_utc()
        return self._update_job(job)

    def update_generation_progress(
        self,
        *,
        job_id: int,
        progress: int,
        provider_job_id: str | None = None,
    ) -> VideoGenerationJob:
        job = self._get_job_or_raise(job_id)
        self._ensure_status(job, allowed=(VideoGenerationJobStatus.RUNNING,))

        job.progress = max(job.progress, clamp_running_progress(progress))
        if provider_job_id is not None:
            job.provider_job_id = provider_job_id
        return self._update_job(job)

    def mark_generation_succeeded(
        self,
        *,
        job_id: int,
        output_url: str,
        thumbnail_url: str | None = None,
        provider_job_id: str | None = None,
    ) -> VideoGenerationJob:
        job = self._get_job_or_raise(job_id)
        self._ensure_status(job, allowed=(VideoGenerationJobStatus.RUNNING,))

        job.status = VideoGenerationJobStatus.SUCCEEDED
        job.progress = 100
        if provider_job_id is not None:
            job.provider_job_id = provider_job_id
        job.output_url = output_url
        job.thumbnail_url = thumbnail_url
        job.completed_at = now_utc()
        self._update_job(job)

        movie = self.movie_repository.get_by_id(job.movie_id)
        if movie is not None:
            movie.status = MovieStatus.COMPLETED
            self.movie_repository.update(movie)
        return job

    def mark_generation_failed(
        self,
        *,
        job_id: int,
        error_code: str,
        error_message: str,
        provider_job_id: str | None = None,
    ) -> VideoGenerationJob:
        job = self._get_job_or_raise(job_id)
        self._ensure_status(
            job,
            allowed=(VideoGenerationJobStatus.QUEUED, VideoGenerationJobStatus.RUNNING),
        )

        job.status = VideoGenerationJobStatus.FAILED
        job.error_code = error_code
        job.error_message = error_message
        if provider_job_id is not None:
            job.provider_job_id = provider_job_id
        job.completed_at = now_utc()
        self._update_job(job)

        movie = self.movie_repository.get_by_id(job.movie_id)
        if movie is not None:
            movie.status = MovieStatus.FAILED
            self.movie_repository.update(movie)
        return job

    def cancel_generation(self, *, movie_id: int, user_id: int) -> VideoGenerationJob:
        movie = self.movie_repository.get_by_id(movie_id)
        if movie is None:
            raise generation_movie_not_found_error()
        if movie.user_id != user_id:
            raise generation_movie_forbidden_error()

        job = self.job_repository.get_in_progress_by_movie_id(movie_id)
        if job is None:
            raise generation_job_not_found_error()

        job.status = VideoGenerationJobStatus.CANCELED
        job.completed_at = now_utc()
        self._update_job(job)

        movie.status = MovieStatus.DRAFT
        self.movie_repository.update(movie)
        return job

    def _get_job_or_raise(self, job_id: int) -> VideoGenerationJob:
        job = self.job_repository.get_by_id(job_id)
        if job is None:
            raise generation_job_not_found_error()
        return job

    def _update_job(self, job: VideoGenerationJob) -> VideoGenerationJob:
        try:
            return self.job_repository.update(job)
        except StaleDataError as exc:
            raise generation_job_state_conflict_error() from exc

    def _ensure_status(
        self,
        job: VideoGenerationJob,
        *,
        allowed: tuple[VideoGenerationJobStatus, ...],
    ) -> None:
        if job.status not in allowed:
            raise generation_invalid_status_transition_error(job.status, allowed)


def generation_movie_not_found_error() -> AppError:
    return AppError(
        status_code=404,
        code="MOVIE_NOT_FOUND",
        title="Movie Not Found",
        detail="영화를 찾을 수 없습니다.",
        type_="movie_not_found",
    )


def generation_movie_forbidden_error() -> AppError:
    return AppError(
        status_code=403,
        code="MOVIE_FORBIDDEN",
        title="Movie Forbidden",
        detail="해당 영화에 접근할 권한이 없습니다.",
        type_="movie_forbidden",
    )


def generation_input_not_ready_error() -> AppError:
    return AppError(
        status_code=409,
        code="GENERATION_INPUT_NOT_READY",
        title="Generation Input Not Ready",
        detail="영상 생성 입력이 아직 준비되지 않았습니다.",
        type_="generation_input_not_ready",
    )


def generation_already_in_progress_error() -> AppError:
    return AppError(
        status_code=409,
        code="GENERATION_ALREADY_IN_PROGRESS",
        title="Generation Already In Progress",
        detail="이미 진행 중인 영상 생성 작업이 있습니다.",
        type_="generation_already_in_progress",
    )


def generation_job_not_found_error() -> AppError:
    return AppError(
        status_code=404,
        code="GENERATION_JOB_NOT_FOUND",
        title="Generation Job Not Found",
        detail="영상 생성 작업을 찾을 수 없습니다.",
        type_="generation_job_not_found",
    )


def generation_job_state_conflict_error() -> AppError:
    return AppError(
        status_code=409,
        code="GENERATION_JOB_STATE_CONFLICT",
        title="Generation Job State Conflict",
        detail="영상 생성 작업 상태가 이미 변경되어 현재 결과를 반영할 수 없습니다.",
        type_="generation_job_state_conflict",
    )


def generation_invalid_status_transition_error(
    current_status: VideoGenerationJobStatus,
    allowed_statuses: tuple[VideoGenerationJobStatus, ...],
) -> AppError:
    return AppError(
        status_code=409,
        code="GENERATION_INVALID_STATUS_TRANSITION",
        title="Generation Invalid Status Transition",
        detail=(
            "영상 생성 작업 상태를 변경할 수 없습니다. "
            f"현재 상태: {current_status.value}, 허용 상태: {', '.join(status.value for status in allowed_statuses)}"
        ),
        type_="generation_invalid_status_transition",
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clamp_running_progress(progress: int) -> int:
    return max(1, min(99, progress))
