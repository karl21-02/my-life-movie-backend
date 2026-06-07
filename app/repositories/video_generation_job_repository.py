from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.orm.exc import StaleDataError
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

    def get_by_id(self, job_id: int) -> VideoGenerationJob | None:
        ...

    def get_latest_by_movie_id(self, movie_id: int) -> VideoGenerationJob | None:
        ...

    def list_latest_by_movie_ids(self, movie_ids: list[int]) -> dict[int, VideoGenerationJob]:
        ...

    def get_in_progress_by_movie_id(self, movie_id: int) -> VideoGenerationJob | None:
        ...

    def get_next_queued(self) -> VideoGenerationJob | None:
        ...

    def claim(self, job_id: int) -> VideoGenerationJob | None:
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

    def get_by_id(self, job_id: int) -> VideoGenerationJob | None:
        return self.session.get(VideoGenerationJob, job_id, populate_existing=True)

    def get_latest_by_movie_id(self, movie_id: int) -> VideoGenerationJob | None:
        return self.session.scalar(
            select(VideoGenerationJob)
            .where(VideoGenerationJob.movie_id == movie_id)
            .order_by(VideoGenerationJob.created_at.desc(), VideoGenerationJob.id.desc())
            .limit(1)
        )

    def list_latest_by_movie_ids(self, movie_ids: list[int]) -> dict[int, VideoGenerationJob]:
        if not movie_ids:
            return {}

        jobs = self.session.scalars(
            select(VideoGenerationJob)
            .where(VideoGenerationJob.movie_id.in_(movie_ids))
            .order_by(
                VideoGenerationJob.movie_id.asc(),
                VideoGenerationJob.created_at.desc(),
                VideoGenerationJob.id.desc(),
            )
        )
        latest_jobs: dict[int, VideoGenerationJob] = {}
        for job in jobs:
            latest_jobs.setdefault(job.movie_id, job)
        return latest_jobs

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

    def get_next_queued(self) -> VideoGenerationJob | None:
        return self.session.scalar(
            select(VideoGenerationJob)
            .where(VideoGenerationJob.status == VideoGenerationJobStatus.QUEUED)
            .order_by(VideoGenerationJob.created_at.asc(), VideoGenerationJob.id.asc())
            .limit(1)
        )

    def claim(self, job_id: int) -> VideoGenerationJob | None:
        """QUEUED job을 원자적으로 RUNNING으로 전환한다.

        조건부 UPDATE(... WHERE status=QUEUED)라 동시에 여러 워커가 같은 job을
        잡아도 DB row 락으로 직렬화되어 정확히 한 워커만 rowcount==1을 받는다.
        나머지는 0을 받고 None을 돌려받아 처리를 양보한다.
        """
        result = self.session.execute(
            update(VideoGenerationJob)
            .where(
                VideoGenerationJob.id == job_id,
                VideoGenerationJob.status == VideoGenerationJobStatus.QUEUED,
            )
            .values(
                status=VideoGenerationJobStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                progress=1,
            )
        )
        self.session.commit()
        if result.rowcount != 1:
            return None
        return self.get_by_id(job_id)

    def update(self, job: VideoGenerationJob) -> VideoGenerationJob:
        try:
            self.session.commit()
        except StaleDataError:
            self.session.rollback()
            raise
        self.session.refresh(job)
        return job
