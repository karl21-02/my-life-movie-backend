from app.services.video_generation_queue import QueueMessage


class InMemoryVideoGenerationQueue:
    """테스트용 영상 생성 큐 fake.

    Redis Streams 의미를 단순화한다: enqueue 시 곧바로 소비 가능한 메시지로 쌓고,
    consume 는 앞에서부터 꺼낸다. reclaim 은 명시적으로 채워둔 항목만 돌려준다.
    ack 된 message_id 는 기록해 검증에 쓴다.
    """

    def __init__(self) -> None:
        self.enqueued: list[int] = []
        self.acked: list[str] = []
        self.pending: list[QueueMessage] = []
        self.reclaimable: list[QueueMessage] = []
        self._by_job: dict[int, QueueMessage] = {}
        self._seq = 0

    def ensure_group(self) -> None:
        return None

    def enqueue(self, job_id: int) -> None:
        self._seq += 1
        message = QueueMessage(message_id=f"m-{self._seq}", job_id=job_id)
        self.enqueued.append(job_id)
        self.pending.append(message)
        self._by_job[job_id] = message

    def consume(self, consumer: str, *, count: int, block_ms: int) -> list[QueueMessage]:
        taken = self.pending[:count]
        self.pending = self.pending[count:]
        return taken

    def reclaim(self, consumer: str, *, min_idle_ms: int, count: int) -> list[QueueMessage]:
        taken = self.reclaimable[:count]
        self.reclaimable = self.reclaimable[count:]
        return taken

    def ack(self, message_id: str) -> None:
        self.acked.append(message_id)

    def message_for(self, job_id: int) -> QueueMessage:
        """해당 job_id로 enqueue 된 메시지를 돌려준다(테스트 편의)."""
        return self._by_job[job_id]
