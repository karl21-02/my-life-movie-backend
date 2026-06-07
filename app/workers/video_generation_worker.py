import os
import socket

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_session_factory
from app.repositories.movie_repository import SQLAlchemyMovieRepository
from app.repositories.video_generation_job_repository import SQLAlchemyVideoGenerationJobRepository
from app.services.video_generation_provider import build_video_generation_provider, resolve_video_generation_provider_name
from app.services.video_generation_queue import (
    QueueMessage,
    VideoGenerationQueue,
    build_video_generation_queue,
)
from app.services.video_generation_service import VideoGenerationService
from app.services.video_generation_worker_service import VideoGenerationWorkerService

logger = get_logger(__name__)


def create_worker(db, queue: VideoGenerationQueue) -> VideoGenerationWorkerService:
    settings = get_settings()
    generation_service = VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db),
        provider_name=resolve_video_generation_provider_name(settings),
        queue=queue,
    )
    return VideoGenerationWorkerService(
        generation_service=generation_service,
        provider=build_video_generation_provider(settings),
        queue=queue,
    )


def _handle_message(queue: VideoGenerationQueue, message: QueueMessage, *, reclaimed: bool) -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        result = create_worker(db, queue).process_message(message, reclaimed=reclaimed)
    if result is not None:
        logger.info(
            "영상 생성 Job 처리 완료",
            extra={
                "event": "video_generation_job_processed",
                "job_id": result.job.id,
                "status": result.job.status.value,
            },
        )


def process_batch(queue: VideoGenerationQueue, *, consumer: str, settings: Settings) -> None:
    # 1) 죽은 워커가 ACK 못 한 채 방치한 entry 회수 (XAUTOCLAIM)
    reclaimed = queue.reclaim(
        consumer,
        min_idle_ms=settings.video_generation_reclaim_min_idle_ms,
        count=settings.video_generation_reclaim_count,
    )
    for message in reclaimed:
        _handle_message(queue, message, reclaimed=True)

    # 2) 신규 entry 수신 (XREADGROUP, block 동안 대기)
    messages = queue.consume(
        consumer,
        count=1,
        block_ms=settings.video_generation_block_ms,
    )
    for message in messages:
        _handle_message(queue, message, reclaimed=False)


def build_consumer_name() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def run_forever() -> None:
    settings = get_settings()
    configure_logging(settings)

    queue = build_video_generation_queue(settings)
    queue.ensure_group()
    consumer = build_consumer_name()

    logger.info(
        "영상 생성 worker 시작",
        extra={"event": "video_generation_worker_started", "consumer": consumer},
    )

    while True:
        process_batch(queue, consumer=consumer, settings=settings)


if __name__ == "__main__":
    run_forever()
