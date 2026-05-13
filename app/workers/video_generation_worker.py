import time

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_session_factory
from app.repositories.movie_repository import SQLAlchemyMovieRepository
from app.repositories.video_generation_job_repository import SQLAlchemyVideoGenerationJobRepository
from app.services.video_generation_provider import build_video_generation_provider, resolve_video_generation_provider_name
from app.services.video_generation_service import VideoGenerationService
from app.services.video_generation_worker_service import VideoGenerationWorkerService

logger = get_logger(__name__)


def create_worker(db) -> VideoGenerationWorkerService:
    settings = get_settings()
    generation_service = VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db),
        provider_name=resolve_video_generation_provider_name(settings),
    )
    return VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=build_video_generation_provider(settings),
    )


def run_once() -> bool:
    session_factory = get_session_factory()
    with session_factory() as db:
        result = create_worker(db).run_next()
        if result is None:
            return False

        logger.info(
            "영상 생성 Job 처리 완료",
            extra={"event": "video_generation_job_processed"},
        )
        return True


def run_forever() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "영상 생성 worker 시작",
        extra={"event": "video_generation_worker_started"},
    )

    while True:
        processed = run_once()
        if not processed:
            time.sleep(settings.video_generation_worker_poll_interval_seconds)


if __name__ == "__main__":
    run_forever()
