from dataclasses import dataclass

from app.core.errors import AppError
from app.models.movie import MovieStatus
from app.models.video_generation_job import VideoGenerationJob
from app.repositories.movie_repository import MovieRepository
from app.repositories.video_generation_job_repository import VideoGenerationJobRepository
from app.services.video_generation_input_builder import build_video_generation_input


@dataclass(frozen=True)
class VideoGenerationRequestResult:
    job: VideoGenerationJob


class VideoGenerationService:
    def __init__(
        self,
        *,
        movie_repository: MovieRepository,
        job_repository: VideoGenerationJobRepository,
    ) -> None:
        self.movie_repository = movie_repository
        self.job_repository = job_repository

    def request_generation(self, *, movie_id: int, user_id: int) -> VideoGenerationRequestResult:
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
        )
        movie.status = MovieStatus.GENERATING
        self.movie_repository.update(movie)
        return VideoGenerationRequestResult(job=job)

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
