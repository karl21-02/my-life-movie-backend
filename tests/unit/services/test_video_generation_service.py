import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.movie import MovieStatus
from app.models.video_generation_job import VideoGenerationJobStatus
from app.repositories.movie_repository import SQLAlchemyMovieRepository
from app.repositories.video_generation_job_repository import SQLAlchemyVideoGenerationJobRepository
from app.services.video_generation_service import VideoGenerationService
from tests.factories import create_user
from tests.fakes import InMemoryVideoGenerationQueue


pytestmark = pytest.mark.unit


def create_service(db_session: Session) -> VideoGenerationService:
    return VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db_session),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db_session),
        queue=InMemoryVideoGenerationQueue(),
    )


def create_openai_service(db_session: Session) -> VideoGenerationService:
    return VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db_session),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db_session),
        provider_name="openai",
        queue=InMemoryVideoGenerationQueue(),
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


def test_request_generation_creates_queued_job_and_marks_movie_generating(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)

    result = service.request_generation(movie_id=movie.id, user_id=user.id)

    db_session.refresh(movie)
    assert result.job.status == VideoGenerationJobStatus.QUEUED
    assert result.job.progress == 0
    assert result.job.provider == "mock"
    assert result.job.input_snapshot["provider_prompt"] == "warm cinematic life story"
    assert movie.status == MovieStatus.GENERATING


def test_request_generation_enqueues_job(db_session: Session):
    user, movie = create_ready_movie(db_session)
    queue = InMemoryVideoGenerationQueue()
    service = VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db_session),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db_session),
        queue=queue,
    )

    result = service.request_generation(movie_id=movie.id, user_id=user.id)

    assert queue.enqueued == [result.job.id]


def test_claim_generation_transitions_queued_to_running_once(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)

    claimed = service.claim_generation(job_id=created.job.id)
    second = service.claim_generation(job_id=created.job.id)

    assert claimed is not None
    assert claimed.status == VideoGenerationJobStatus.RUNNING
    assert claimed.progress == 1
    assert claimed.started_at is not None
    # 이미 RUNNING이라 두 번째 claim은 진다(None)
    assert second is None


def test_request_generation_records_configured_provider(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_openai_service(db_session)

    result = service.request_generation(movie_id=movie.id, user_id=user.id)

    assert result.job.provider == "openai"


def test_request_generation_rejects_missing_generation_prompt(db_session: Session):
    user = create_user(db_session)
    movie = SQLAlchemyMovieRepository(db_session).create(user_id=user.id, theme_id=1)
    service = create_service(db_session)

    with pytest.raises(AppError) as exc_info:
        service.request_generation(movie_id=movie.id, user_id=user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "GENERATION_INPUT_NOT_READY"


def test_request_generation_rejects_duplicate_in_progress_job(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)

    service.request_generation(movie_id=movie.id, user_id=user.id)

    with pytest.raises(AppError) as exc_info:
        service.request_generation(movie_id=movie.id, user_id=user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "GENERATION_ALREADY_IN_PROGRESS"


def test_get_latest_generation_returns_latest_job(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)

    found = service.get_latest_generation(movie_id=movie.id, user_id=user.id)

    assert found.id == created.job.id


def test_mark_generation_failed_records_provider_job_id(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    service.start_generation(job_id=created.job.id)

    failed = service.mark_generation_failed(
        job_id=created.job.id,
        error_code="PROVIDER_MODERATION_BLOCKED",
        error_message="moderation_blocked",
        provider_job_id="video_failed_1",
    )

    assert failed.status == VideoGenerationJobStatus.FAILED
    assert failed.provider_job_id == "video_failed_1"
    assert failed.error_code == "PROVIDER_MODERATION_BLOCKED"


def test_get_latest_generation_returns_404_when_job_is_missing(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)

    with pytest.raises(AppError) as exc_info:
        service.get_latest_generation(movie_id=movie.id, user_id=user.id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "GENERATION_JOB_NOT_FOUND"


def test_start_generation_marks_job_running(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)

    job = service.start_generation(job_id=created.job.id, provider_job_id="provider-1")

    assert job.status == VideoGenerationJobStatus.RUNNING
    assert job.progress == 1
    assert job.provider_job_id == "provider-1"
    assert job.started_at is not None


def test_update_generation_progress_records_running_progress(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    service.start_generation(job_id=created.job.id)

    job = service.update_generation_progress(
        job_id=created.job.id,
        progress=45,
        provider_job_id="provider-progress-1",
    )

    assert job.status == VideoGenerationJobStatus.RUNNING
    assert job.progress == 45
    assert job.provider_job_id == "provider-progress-1"


def test_update_generation_progress_clamps_to_running_range(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    service.start_generation(job_id=created.job.id)

    low = service.update_generation_progress(job_id=created.job.id, progress=0)
    low_progress = low.progress
    high = service.update_generation_progress(job_id=created.job.id, progress=100)

    assert low_progress == 1
    assert high.progress == 99


def test_start_generation_rejects_terminal_job(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    job = service.start_generation(job_id=created.job.id)
    service.mark_generation_succeeded(job_id=job.id, output_url="https://cdn.example.com/movie.mp4")

    with pytest.raises(AppError) as exc_info:
        service.start_generation(job_id=job.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "GENERATION_INVALID_STATUS_TRANSITION"


def test_mark_generation_succeeded_completes_job_and_movie(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    service.start_generation(job_id=created.job.id)

    job = service.mark_generation_succeeded(
        job_id=created.job.id,
        output_url="https://cdn.example.com/movie.mp4",
        thumbnail_url="https://cdn.example.com/movie.jpg",
    )

    db_session.refresh(movie)
    assert job.status == VideoGenerationJobStatus.SUCCEEDED
    assert job.progress == 100
    assert job.output_url == "https://cdn.example.com/movie.mp4"
    assert job.thumbnail_url == "https://cdn.example.com/movie.jpg"
    assert job.completed_at is not None
    assert movie.status == MovieStatus.COMPLETED


def test_mark_generation_failed_fails_job_and_movie(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    service.start_generation(job_id=created.job.id)

    job = service.mark_generation_failed(
        job_id=created.job.id,
        error_code="PROVIDER_TIMEOUT",
        error_message="Provider request timed out.",
    )

    db_session.refresh(movie)
    assert job.status == VideoGenerationJobStatus.FAILED
    assert job.error_code == "PROVIDER_TIMEOUT"
    assert job.error_message == "Provider request timed out."
    assert job.completed_at is not None
    assert movie.status == MovieStatus.FAILED


def test_cancel_generation_cancels_in_progress_job_and_resets_movie(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service = create_service(db_session)
    service.request_generation(movie_id=movie.id, user_id=user.id)

    job = service.cancel_generation(movie_id=movie.id, user_id=user.id)

    db_session.refresh(movie)
    assert job.status == VideoGenerationJobStatus.CANCELED
    assert job.completed_at is not None
    assert movie.status == MovieStatus.DRAFT
