import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.movie import MovieStatus
from app.models.video_generation_job import VideoGenerationJob
from app.models.video_generation_job import VideoGenerationJobStatus
from app.repositories.movie_repository import SQLAlchemyMovieRepository
from app.repositories.video_generation_job_repository import SQLAlchemyVideoGenerationJobRepository
from app.services.video_generation_provider import VideoGenerationProviderResult
from app.services.video_generation_queue import QueueMessage
from app.services.video_generation_service import VideoGenerationService
from app.services.video_generation_worker_service import VideoGenerationWorkerService
from tests.factories import create_user
from tests.fakes import InMemoryVideoGenerationQueue


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


class UncalledProvider:
    """호출되면 안 되는 provider — 재실행 방지 검증용."""

    def __init__(self) -> None:
        self.called = False

    def generate(self, input_snapshot: dict, progress_callback=None) -> VideoGenerationProviderResult:
        self.called = True
        raise AssertionError("provider가 호출되면 안 됩니다.")


def build_worker_env(db_session: Session, provider):
    queue = InMemoryVideoGenerationQueue()
    generation_service = VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db_session),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db_session),
        queue=queue,
    )
    worker = VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=provider,
        queue=queue,
    )
    return generation_service, worker, queue


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


# ── 신규 entry 처리 ────────────────────────────────────────────

def test_process_message_marks_job_succeeded_and_acks(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(db_session, SuccessProvider())
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    message = queue.message_for(created.job.id)

    result = worker.process_message(message)

    db_session.refresh(movie)
    assert result.job.status == VideoGenerationJobStatus.SUCCEEDED
    assert result.job.progress == 100
    assert result.job.provider_job_id == "provider-job-1"
    assert result.job.output_url == "https://cdn.example.com/movie.mp4"
    assert result.job.thumbnail_url == "https://cdn.example.com/movie.jpg"
    assert movie.status == MovieStatus.COMPLETED
    assert message.message_id in queue.acked


def test_process_message_records_provider_progress(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(db_session, ProgressingProvider())
    created = service.request_generation(movie_id=movie.id, user_id=user.id)

    result = worker.process_message(queue.message_for(created.job.id))

    assert result.job.status == VideoGenerationJobStatus.SUCCEEDED
    assert result.job.progress == 100
    assert result.job.provider_job_id == "provider-job-progress"


def test_process_message_marks_job_failed_when_provider_fails(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(db_session, FailingProvider())
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    message = queue.message_for(created.job.id)

    result = worker.process_message(message)

    db_session.refresh(movie)
    assert result.job.status == VideoGenerationJobStatus.FAILED
    assert result.job.error_code == "PROVIDER_TIMEOUT"
    assert result.job.error_message == "provider timeout"
    assert movie.status == MovieStatus.FAILED
    assert message.message_id in queue.acked


def test_process_message_records_provider_moderation_failure_details(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(db_session, ModerationFailingProvider())
    created = service.request_generation(movie_id=movie.id, user_id=user.id)

    result = worker.process_message(queue.message_for(created.job.id))

    assert result.job.status == VideoGenerationJobStatus.FAILED
    assert result.job.error_code == "PROVIDER_MODERATION_BLOCKED"
    assert result.job.error_message.startswith("moderation_blocked")
    assert result.job.provider_job_id == "video_failed_1"


def test_process_message_yields_when_already_claimed(db_session: Session):
    # 다른 워커가 먼저 claim(RUNNING)한 상황 — provider 호출 없이 양보 + ack
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(db_session, UncalledProvider())
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    message = queue.message_for(created.job.id)
    service.claim_generation(job_id=created.job.id)  # 선점

    result = worker.process_message(message)

    assert result is None
    assert worker.provider.called is False
    assert message.message_id in queue.acked


def test_process_message_skips_when_job_removed_during_provider_execution(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(
        db_session, DeletingProvider(db_session, job_id=0)
    )
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    worker.provider.job_id = created.job.id
    message = queue.message_for(created.job.id)

    result = worker.process_message(message)

    assert result is None
    assert message.message_id in queue.acked


# ── 회수(reclaim) 처리 ─────────────────────────────────────────

def test_reclaimed_queued_job_is_processed_normally(db_session: Session):
    # 워커가 claim 전에 죽음 → 회수해서 정상 처리
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(db_session, SuccessProvider())
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    message = queue.message_for(created.job.id)

    result = worker.process_message(message, reclaimed=True)

    assert result.job.status == VideoGenerationJobStatus.SUCCEEDED
    assert message.message_id in queue.acked


def test_reclaimed_running_job_fails_without_rerun(db_session: Session):
    # 워커가 실행 중 죽음(RUNNING) → 재실행하지 않고 FAILED 처리
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(db_session, UncalledProvider())
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    service.claim_generation(job_id=created.job.id)  # RUNNING으로 만든 뒤 워커가 죽었다고 가정
    message = queue.message_for(created.job.id)

    result = worker.process_message(message, reclaimed=True)

    db_session.refresh(movie)
    assert result.job.status == VideoGenerationJobStatus.FAILED
    assert result.job.error_code == "WORKER_CRASHED"
    assert worker.provider.called is False
    assert movie.status == MovieStatus.FAILED
    assert message.message_id in queue.acked


def test_reclaimed_terminal_job_is_only_acked(db_session: Session):
    user, movie = create_ready_movie(db_session)
    service, worker, queue = build_worker_env(db_session, UncalledProvider())
    created = service.request_generation(movie_id=movie.id, user_id=user.id)
    service.claim_generation(job_id=created.job.id)
    service.mark_generation_succeeded(
        job_id=created.job.id, output_url="https://cdn.example.com/movie.mp4"
    )
    message = queue.message_for(created.job.id)

    result = worker.process_message(message, reclaimed=True)

    assert result is None
    assert worker.provider.called is False
    assert message.message_id in queue.acked
