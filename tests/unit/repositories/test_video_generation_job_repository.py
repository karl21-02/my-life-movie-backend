import pytest
from sqlalchemy.orm import Session

from app.models.video_generation_job import VideoGenerationJobStatus
from app.repositories.movie_repository import SQLAlchemyMovieRepository
from app.repositories.video_generation_job_repository import SQLAlchemyVideoGenerationJobRepository
from tests.factories import create_user


pytestmark = pytest.mark.unit


def _create_movie(db_session: Session):
    user = create_user(db_session)
    movie = SQLAlchemyMovieRepository(db_session).create(user_id=user.id, theme_id=1)
    return user, movie


def test_create_job_defaults_to_queued_and_mock_provider(db_session: Session):
    user, movie = _create_movie(db_session)
    repository = SQLAlchemyVideoGenerationJobRepository(db_session)

    job = repository.create(
        movie_id=movie.id,
        user_id=user.id,
        input_snapshot={"provider_prompt": "test prompt"},
    )

    assert job.id is not None
    assert job.status == VideoGenerationJobStatus.QUEUED
    assert job.provider == "mock"
    assert job.progress == 0
    assert job.input_snapshot["provider_prompt"] == "test prompt"


def test_get_latest_by_movie_id_returns_newest_job(db_session: Session):
    user, movie = _create_movie(db_session)
    repository = SQLAlchemyVideoGenerationJobRepository(db_session)

    first = repository.create(movie_id=movie.id, user_id=user.id, input_snapshot={"order": 1})
    second = repository.create(movie_id=movie.id, user_id=user.id, input_snapshot={"order": 2})

    latest = repository.get_latest_by_movie_id(movie.id)

    assert latest is not None
    assert latest.id == second.id
    assert latest.id != first.id


def test_get_in_progress_by_movie_id_returns_queued_or_running_job(db_session: Session):
    user, movie = _create_movie(db_session)
    repository = SQLAlchemyVideoGenerationJobRepository(db_session)

    finished = repository.create(movie_id=movie.id, user_id=user.id, input_snapshot={"status": "done"})
    finished.status = VideoGenerationJobStatus.SUCCEEDED
    repository.update(finished)
    running = repository.create(movie_id=movie.id, user_id=user.id, input_snapshot={"status": "running"})
    running.status = VideoGenerationJobStatus.RUNNING
    repository.update(running)

    in_progress = repository.get_in_progress_by_movie_id(movie.id)

    assert in_progress is not None
    assert in_progress.id == running.id


def test_get_in_progress_by_movie_id_ignores_terminal_jobs(db_session: Session):
    user, movie = _create_movie(db_session)
    repository = SQLAlchemyVideoGenerationJobRepository(db_session)

    job = repository.create(movie_id=movie.id, user_id=user.id, input_snapshot={"status": "failed"})
    job.status = VideoGenerationJobStatus.FAILED
    repository.update(job)

    assert repository.get_in_progress_by_movie_id(movie.id) is None
