import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.movie import MovieStatus
from app.models.video_generation_job import VideoGenerationJob
from app.models.video_generation_job import VideoGenerationJobStatus
from app.repositories.movie_repository import SQLAlchemyMovieRepository
from app.repositories.video_generation_job_repository import SQLAlchemyVideoGenerationJobRepository
from app.services.video_generation_provider import VideoGenerationProviderResult
from app.services.video_generation_service import VideoGenerationService
from app.services.video_generation_worker_service import VideoGenerationWorkerService
from tests.factories import create_user


pytestmark = pytest.mark.unit


class SuccessProvider:
    def generate(self, input_snapshot: dict, progress_callback=None) -> VideoGenerationProviderResult:
        return VideoGenerationProviderResult(
            provider_job_id="provider-job-1",
            output_url="https://cdn.example.com/movie.mp4",
            thumbnail_url="https://cdn.example.com/movie.jpg",
        )


class ProgressingProvider:
    def generate(self, input_snapshot: dict, progress_callback=None) -> VideoGenerationProviderResult:
        if progress_callback is not None:
            progress_callback(45, "provider-job-progress")
        return VideoGenerationProviderResult(
            provider_job_id="provider-job-progress",
            output_url="https://cdn.example.com/movie.mp4",
            thumbnail_url="https://cdn.example.com/movie.jpg",
        )


class FailingProvider:
    def generate(self, input_snapshot: dict, progress_callback=None) -> VideoGenerationProviderResult:
        raise RuntimeError("provider timeout")


class ModerationFailingProvider:
    def generate(self, input_snapshot: dict, progress_callback=None) -> VideoGenerationProviderResult:
        exc = RuntimeError("moderation_blocked: Your request was blocked by our moderation system.")
        exc.provider_job_id = "video_failed_1"
        raise exc


class DeletingProvider:
    def __init__(self, db_session: Session, job_id: int) -> None:
        self.db_session = db_session
        self.job_id = job_id

    def generate(self, input_snapshot: dict, progress_callback=None) -> VideoGenerationProviderResult:
        self.db_session.execute(
            delete(VideoGenerationJob)
            .where(VideoGenerationJob.id == self.job_id)
            .execution_options(synchronize_session=False)
        )
        self.db_session.commit()
        return VideoGenerationProviderResult(
            provider_job_id="provider-job-1",
            output_url="https://cdn.example.com/movie.mp4",
            thumbnail_url="https://cdn.example.com/movie.jpg",
        )


def create_service(db_session: Session) -> VideoGenerationService:
    return VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db_session),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db_session),
    )


def create_ready_movie(db_session: Session):
    user = create_user(db_session)
    movie_repository = SQLAlchemyMovieRepository(db_session)
    movie = movie_repository.create(user_id=user.id, theme_id=1)
    movie.current_draft = "인생 영화 초안"
    movie.story_brief = {"title": "나의 이야기", "emotions": ["회상"]}
    movie.scene_plan = [{"order": 1, "summary": "시작 장면"}]
    movie.generation_prompt = "warm cinematic life story"
    movie_repository.update(movie)
    return user, movie


def test_worker_run_marks_job_succeeded(db_session: Session):
    user, movie = create_ready_movie(db_session)
    generation_service = create_service(db_session)
    created = generation_service.request_generation(movie_id=movie.id, user_id=user.id)
    worker = VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=SuccessProvider(),
    )

    result = worker.run(job_id=created.job.id)

    db_session.refresh(movie)
    assert result.job.status == VideoGenerationJobStatus.SUCCEEDED
    assert result.job.progress == 100
    assert result.job.provider_job_id == "provider-job-1"
    assert result.job.output_url == "https://cdn.example.com/movie.mp4"
    assert result.job.thumbnail_url == "https://cdn.example.com/movie.jpg"
    assert movie.status == MovieStatus.COMPLETED


def test_worker_run_records_provider_progress(db_session: Session):
    user, movie = create_ready_movie(db_session)
    generation_service = create_service(db_session)
    created = generation_service.request_generation(movie_id=movie.id, user_id=user.id)
    worker = VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=ProgressingProvider(),
    )

    result = worker.run(job_id=created.job.id)

    assert result.job.status == VideoGenerationJobStatus.SUCCEEDED
    assert result.job.progress == 100
    assert result.job.provider_job_id == "provider-job-progress"


def test_worker_run_marks_job_failed_when_provider_fails(db_session: Session):
    user, movie = create_ready_movie(db_session)
    generation_service = create_service(db_session)
    created = generation_service.request_generation(movie_id=movie.id, user_id=user.id)
    worker = VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=FailingProvider(),
    )

    result = worker.run(job_id=created.job.id)

    db_session.refresh(movie)
    assert result.job.status == VideoGenerationJobStatus.FAILED
    assert result.job.error_code == "PROVIDER_TIMEOUT"
    assert result.job.error_message == "provider timeout"
    assert movie.status == MovieStatus.FAILED


def test_worker_run_records_provider_moderation_failure_details(db_session: Session):
    user, movie = create_ready_movie(db_session)
    generation_service = create_service(db_session)
    created = generation_service.request_generation(movie_id=movie.id, user_id=user.id)
    worker = VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=ModerationFailingProvider(),
    )

    result = worker.run(job_id=created.job.id)

    assert result.job.status == VideoGenerationJobStatus.FAILED
    assert result.job.error_code == "PROVIDER_MODERATION_BLOCKED"
    assert result.job.error_message.startswith("moderation_blocked")
    assert result.job.provider_job_id == "video_failed_1"


def test_worker_run_next_processes_oldest_queued_job(db_session: Session):
    user, first_movie = create_ready_movie(db_session)
    movie_repository = SQLAlchemyMovieRepository(db_session)
    second_movie = movie_repository.create(user_id=user.id, theme_id=1)
    second_movie.current_draft = "두 번째 인생 영화 초안"
    second_movie.story_brief = {"title": "두 번째 이야기", "emotions": ["도전"]}
    second_movie.scene_plan = [{"order": 1, "summary": "두 번째 시작 장면"}]
    second_movie.generation_prompt = "second warm cinematic life story"
    movie_repository.update(second_movie)
    generation_service = create_service(db_session)
    first = generation_service.request_generation(movie_id=first_movie.id, user_id=user.id)
    second = generation_service.request_generation(movie_id=second_movie.id, user_id=user.id)
    worker = VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=SuccessProvider(),
    )

    result = worker.run_next()

    assert result is not None
    assert result.job.id == first.job.id
    assert result.job.id != second.job.id
    assert result.job.status == VideoGenerationJobStatus.SUCCEEDED


def test_worker_run_next_returns_none_when_queue_is_empty(db_session: Session):
    worker = VideoGenerationWorkerService(
        generation_service=create_service(db_session),
        provider=SuccessProvider(),
    )

    assert worker.run_next() is None


def test_worker_run_skips_when_job_is_removed_during_provider_execution(db_session: Session):
    user, movie = create_ready_movie(db_session)
    generation_service = create_service(db_session)
    created = generation_service.request_generation(movie_id=movie.id, user_id=user.id)
    worker = VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=DeletingProvider(db_session, created.job.id),
    )

    result = worker.run(job_id=created.job.id)

    assert result is None
