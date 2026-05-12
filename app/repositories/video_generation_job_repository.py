from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.video_generation_job import VideoGenerationJob, VideoGenerationJobStatus

IN_PROGRESS_STATUSES = (
    VideoGenerationJobStatus.QUEUED,
    VideoGenerationJobStatus.RUNNING,
)


class VideoGenerationJobRepository(Protocol):
    def create(
        self,
        *,
        movie_id: int,
        user_id: int,
        input_snapshot: dict,
        provider: str = "mock",
    ) -> VideoGenerationJob:
        ...

    def get_latest_by_movie_id(self, movie_id: int) -> VideoGenerationJob | None:
        ...

    def get_in_progress_by_movie_id(self, movie_id: int) -> VideoGenerationJob | None:
        ...

    def update(self, job: VideoGenerationJob) -> VideoGenerationJob:
        ...


class SQLAlchemyVideoGenerationJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        movie_id: int,
        user_id: int,
        input_snapshot: dict,
        provider: str = "mock",
    ) -> VideoGenerationJob:
        job = VideoGenerationJob(
            movie_id=movie_id,
            user_id=user_id,
            status=VideoGenerationJobStatus.QUEUED,
            provider=provider,
            progress=0,
            input_snapshot=input_snapshot,
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_latest_by_movie_id(self, movie_id: int) -> VideoGenerationJob | None:
        return self.session.scalar(
            select(VideoGenerationJob)
            .where(VideoGenerationJob.movie_id == movie_id)
            .order_by(VideoGenerationJob.created_at.desc(), VideoGenerationJob.id.desc())
            .limit(1)
        )

    def get_in_progress_by_movie_id(self, movie_id: int) -> VideoGenerationJob | None:
        return self.session.scalar(
            select(VideoGenerationJob)
            .where(
                VideoGenerationJob.movie_id == movie_id,
                VideoGenerationJob.status.in_(IN_PROGRESS_STATUSES),
            )
            .order_by(VideoGenerationJob.created_at.desc(), VideoGenerationJob.id.desc())
            .limit(1)
        )

    def update(self, job: VideoGenerationJob) -> VideoGenerationJob:
        self.session.commit()
        self.session.refresh(job)
        return job
