"""Backend-agnostic priority job queue for the index/import workers.

Until now the workers held their queue in a module-level
:class:`queue.PriorityQueue` living in the backend process (architecture-map
finding "Valkey/Redis previsto, não usado"). AGENTS.md lists Valkey as the
preferred local stack, so this module introduces a small abstraction with two
backends:

* :class:`InMemoryJobQueue` — default; identical to the previous behaviour,
  suited to dev / single-replica.
* :class:`RedisJobQueue` — backed by a Redis/Valkey sorted set + dedup set so
  the queue can be shared across backend replicas.

The backend is chosen by ``settings.queue_backend`` (``memory`` |
``redis`` | ``valkey``). If a Redis/Valkey backend is requested but
unreachable at startup, :func:`create_job_queue` logs a warning and falls
back to the in-memory queue so the app never fails to boot over a queue
outage.

Semantics shared by both backends:

* Items are opaque string ids.
* ``put`` is **dedup-guarded**: re-enqueuing an id that is still in flight
  (queued *or* being processed) is a no-op until :meth:`release` is called.
* Lower ``priority`` is served first; ties are FIFO (a monotonic sequence
  breaks ties so equal-priority items keep insertion order on both backends).
* ``requeue`` re-adds an in-flight id (used for retries) without touching the
  dedup marker.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from itertools import count
from queue import Empty, PriorityQueue
from threading import Lock

from app.core.config import settings

logger = logging.getLogger(__name__)

# Tie-breaker multiplier: keeps ``priority`` dominant while the monotonic
# sequence preserves FIFO within a priority band on the Redis sorted set.
_PRIORITY_SCALE = 1_000_000_000_000


class JobQueue(ABC):
    """Priority job queue with dedup used by the background workers."""

    @abstractmethod
    def put(self, item: str, priority: int = 0) -> bool:
        """Enqueue ``item`` unless it is already in flight.

        Returns ``True`` when the item was newly enqueued, ``False`` when it
        was a duplicate (already queued or being processed).
        """

    @abstractmethod
    def get(self, timeout: float) -> str | None:
        """Pop the highest-priority item, or ``None`` after ``timeout`` s."""

    @abstractmethod
    def release(self, item: str) -> None:
        """Clear the dedup marker once ``item`` finished processing."""

    @abstractmethod
    def requeue(self, item: str, priority: int = 0) -> None:
        """Re-add an in-flight ``item`` (retry) without dedup changes."""


class InMemoryJobQueue(JobQueue):
    """In-process queue — the historical behaviour, default backend."""

    def __init__(self) -> None:
        self._queue: PriorityQueue[tuple[int, int, str]] = PriorityQueue()
        self._lock = Lock()
        self._enqueued: set[str] = set()
        self._seq = count()

    def put(self, item: str, priority: int = 0) -> bool:
        with self._lock:
            if item in self._enqueued:
                return False
            self._enqueued.add(item)
            self._queue.put((priority, next(self._seq), item))
            return True

    def get(self, timeout: float) -> str | None:
        try:
            _priority, _seq, item = self._queue.get(timeout=timeout)
        except Empty:
            return None
        return item

    def release(self, item: str) -> None:
        with self._lock:
            self._enqueued.discard(item)

    def requeue(self, item: str, priority: int = 0) -> None:
        with self._lock:
            self._queue.put((priority, next(self._seq), item))


class RedisJobQueue(JobQueue):
    """Redis/Valkey-backed queue: a sorted set (priority+seq score) plus a
    dedup set, so the queue can be shared across backend replicas.

    ``get`` uses ``BZPOPMIN`` (atomic blocking pop) so concurrent workers
    never process the same item twice.
    """

    def __init__(self, client: object, namespace: str) -> None:
        self._client = client
        self._zset = f"tf:jobq:{namespace}:z"
        self._enqueued = f"tf:jobq:{namespace}:enq"
        self._seq_key = f"tf:jobq:{namespace}:seq"

    def _score(self, priority: int) -> float:
        seq = int(self._client.incr(self._seq_key))
        return priority * _PRIORITY_SCALE + seq

    def put(self, item: str, priority: int = 0) -> bool:
        if not self._client.sadd(self._enqueued, item):
            return False
        self._client.zadd(self._zset, {item: self._score(priority)})
        return True

    def get(self, timeout: float) -> str | None:
        result = self._client.bzpopmin(self._zset, timeout=timeout)
        if not result:
            return None
        member = result[1]
        return member.decode() if isinstance(member, bytes | bytearray) else str(member)

    def release(self, item: str) -> None:
        self._client.srem(self._enqueued, item)

    def requeue(self, item: str, priority: int = 0) -> None:
        self._client.zadd(self._zset, {item: self._score(priority)})


def create_job_queue(namespace: str) -> JobQueue:
    """Build the queue for ``namespace`` based on ``settings.queue_backend``.

    Falls back to :class:`InMemoryJobQueue` when a Redis/Valkey backend is
    requested but the client cannot connect, so a queue outage never blocks
    startup.
    """

    backend = (settings.queue_backend or "memory").lower()
    if backend in {"redis", "valkey"}:
        try:
            import redis  # lazy import: optional dependency at runtime

            client = redis.Redis.from_url(settings.redis_url)
            client.ping()
            logger.info(
                "job queue %s: backend %s (%s)", namespace, backend, settings.redis_url
            )
            return RedisJobQueue(client, namespace)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully to memory
            logger.warning(
                "job queue %s: backend %r indisponível (%s); usando fila em memória.",
                namespace,
                backend,
                exc,
            )
    return InMemoryJobQueue()


__all__ = [
    "InMemoryJobQueue",
    "JobQueue",
    "RedisJobQueue",
    "create_job_queue",
]
