from dataclasses import dataclass
from typing import Protocol

from redis import Redis
from redis.exceptions import ResponseError

from app.core.logging import get_logger

logger = get_logger(__name__)

# XAUTOCLAIM 커서 시작 위치 (스트림 처음부터 훑는다)
_RECLAIM_START_ID = "0-0"
_JOB_ID_FIELD = "job_id"


@dataclass(frozen=True)
class QueueMessage:
    """스트림 entry 하나. message_id로 ACK 하고, job_id로 DB job을 찾는다."""

    message_id: str
    job_id: int


class VideoGenerationQueue(Protocol):
    def ensure_group(self) -> None:
        ...

    def enqueue(self, job_id: int) -> None:
        ...

    def consume(self, consumer: str, *, count: int, block_ms: int) -> list[QueueMessage]:
        ...

    def reclaim(self, consumer: str, *, min_idle_ms: int, count: int) -> list[QueueMessage]:
        ...

    def ack(self, message_id: str) -> None:
        ...


class RedisVideoGenerationQueue:
    """Redis Stream + consumer group 기반 영상 생성 작업 큐.

    - enqueue: XADD
    - consume: XREADGROUP (신규 entry, '>')
    - reclaim: XAUTOCLAIM (ACK 안 된 채 방치된 entry 회수 — 죽은 워커 복구)
    - ack: XACK + XDEL (처리 완료 entry 정리)
    """

    def __init__(
        self,
        *,
        redis_client: Redis | None = None,
        redis_url: str | None = None,
        stream_key: str = "video_generation:stream",
        consumer_group: str = "workers",
    ) -> None:
        if redis_client is None and redis_url is None:
            raise ValueError("Redis client 또는 redis_url이 필요합니다.")

        self.redis = redis_client or Redis.from_url(redis_url, decode_responses=True)
        self.stream_key = stream_key
        self.consumer_group = consumer_group

    def ensure_group(self) -> None:
        try:
            self.redis.xgroup_create(self.stream_key, self.consumer_group, id="$", mkstream=True)
        except ResponseError as exc:
            # 이미 그룹이 있으면 BUSYGROUP — 정상 (멱등)
            if "BUSYGROUP" not in str(exc):
                raise

    def enqueue(self, job_id: int) -> None:
        self.redis.xadd(self.stream_key, {_JOB_ID_FIELD: job_id})

    def consume(self, consumer: str, *, count: int, block_ms: int) -> list[QueueMessage]:
        response = self.redis.xreadgroup(
            self.consumer_group,
            consumer,
            {self.stream_key: ">"},
            count=count,
            block=block_ms,
        )
        if not response:
            return []
        # response: [(stream_key, [(message_id, {field: value}), ...])]
        _, entries = response[0]
        return [message for message in (_parse_entry(entry) for entry in entries) if message]

    def reclaim(self, consumer: str, *, min_idle_ms: int, count: int) -> list[QueueMessage]:
        # XAUTOCLAIM: 다른(죽은) consumer가 잡은 채 min_idle 넘긴 entry를 이 consumer로 회수
        result = self.redis.xautoclaim(
            self.stream_key,
            self.consumer_group,
            consumer,
            min_idle_time=min_idle_ms,
            start_id=_RECLAIM_START_ID,
            count=count,
        )
        # redis-py: (next_cursor, [(message_id, {fields}), ...], deleted_ids)
        entries = result[1] if len(result) > 1 else []
        return [message for message in (_parse_entry(entry) for entry in entries) if message]

    def ack(self, message_id: str) -> None:
        self.redis.xack(self.stream_key, self.consumer_group, message_id)
        self.redis.xdel(self.stream_key, message_id)


def build_video_generation_queue(settings) -> RedisVideoGenerationQueue:
    if not settings.redis_url:
        raise RuntimeError("영상 생성 큐에는 REDIS_URL이 필요합니다.")
    return RedisVideoGenerationQueue(
        redis_url=settings.redis_url,
        stream_key=settings.video_generation_stream_key,
        consumer_group=settings.video_generation_consumer_group,
    )


def _parse_entry(entry: tuple) -> QueueMessage | None:
    message_id, fields = entry
    raw_job_id = fields.get(_JOB_ID_FIELD) if fields else None
    if raw_job_id is None:
        logger.warning(
            "job_id 없는 큐 entry를 건너뜁니다.",
            extra={"event": "video_generation_queue_invalid_entry", "message_id": _to_str(message_id)},
        )
        return None
    try:
        job_id = int(raw_job_id)
    except (TypeError, ValueError):
        logger.warning(
            "job_id 파싱 실패 entry를 건너뜁니다.",
            extra={"event": "video_generation_queue_invalid_job_id", "message_id": _to_str(message_id)},
        )
        return None
    return QueueMessage(message_id=_to_str(message_id), job_id=job_id)


def _to_str(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)
