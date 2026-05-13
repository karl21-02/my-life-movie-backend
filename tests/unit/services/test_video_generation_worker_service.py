import pytest
from sqlalchemy.orm import Session

from app.models.movie import MovieStatus
from app.models.video_generation_job import VideoGenerationJobStatus
from app.repositories.movie_repository import SQLAlchemyMovieRepository
from app.repositories.video_generation_job_repository import SQLAlchemyVideoGenerationJobRepository
from app.services.video_generation_provider import VideoGenerationProviderResult
from app.services.video_generation_service import VideoGenerationService
from app.services.video_generation_worker_service import VideoGenerationWorkerService
from tests.factories import create_user


pytestmark = pytest.mark.unit


class SuccessProvider:
    def generate(self, input_snapshot: dict) -> VideoGenerationProviderResult:
        return VideoGenerationProviderResult(
            provider_job_id="provider-job-1",
            output_url="https://cdn.example.com/movie.mp4",
            thumbnail_url="https://cdn.example.com/movie.jpg",
        )


class FailingProvider:
    def generate(self, input_snapshot: dict) -> VideoGenerationProviderResult:
        raise RuntimeError("provider timeout")


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
    assert result.job.error_code == "PROVIDER_ERROR"
    assert result.job.error_message == "영상 생성 provider 실행에 실패했습니다."
    assert movie.status == MovieStatus.FAILED
