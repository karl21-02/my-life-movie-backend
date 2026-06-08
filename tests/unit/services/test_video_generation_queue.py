import fakeredis
import pytest

from app.services.video_generation_queue import RedisVideoGenerationQueue

pytestmark = pytest.mark.unit


@pytest.fixture()
def queue() -> RedisVideoGenerationQueue:
    q = RedisVideoGenerationQueue(
        redis_client=fakeredis.FakeRedis(decode_responses=True),
        stream_key="test:video_generation:stream",
        consumer_group="test-workers",
    )
    q.ensure_group()
    return q


def test_ensure_group_is_idempotent(queue: RedisVideoGenerationQueue):
    # 두 번 호출해도 BUSYGROUP을 흡수하고 예외가 없어야 한다
    queue.ensure_group()
    queue.ensure_group()


def test_enqueue_then_consume_returns_job(queue: RedisVideoGenerationQueue):
    queue.enqueue(42)

    messages = queue.consume("worker-1", count=10, block_ms=100)

    assert len(messages) == 1
    assert messages[0].job_id == 42
    assert messages[0].message_id


def test_consume_only_delivers_new_entries_once(queue: RedisVideoGenerationQueue):
    queue.enqueue(7)
    first = queue.consume("worker-1", count=10, block_ms=100)
    # 같은 consumer group에서 '>'는 이미 전달된 entry를 다시 주지 않는다
    second = queue.consume("worker-1", count=10, block_ms=100)

    assert [m.job_id for m in first] == [7]
    assert second == []


def test_ack_removes_entry_from_pending(queue: RedisVideoGenerationQueue):
    queue.enqueue(99)
    [message] = queue.consume("worker-1", count=10, block_ms=100)

    queue.ack(message.message_id)

    # ack(XACK+XDEL) 후에는 회수(XAUTOCLAIM) 대상도 없어야 한다
    reclaimed = queue.reclaim("worker-2", min_idle_ms=0, count=10)
    assert reclaimed == []


def test_reclaim_picks_up_unacked_entry_from_dead_worker(queue: RedisVideoGenerationQueue):
    queue.enqueue(123)
    # 죽은 워커가 받기만 하고 ack 안 함
    queue.consume("dead-worker", count=10, block_ms=100)

    # 살아있는 워커가 idle 0 기준으로 회수
    reclaimed = queue.reclaim("alive-worker", min_idle_ms=0, count=10)

    assert [m.job_id for m in reclaimed] == [123]
