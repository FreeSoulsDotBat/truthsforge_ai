"""Tests for the backend-agnostic worker job queue (architecture-map
finding "Valkey/Redis previsto, não usado")."""

from __future__ import annotations

from app.core.config import settings
from app.workers.job_queue import (
    InMemoryJobQueue,
    create_job_queue,
)


def test_put_is_dedup_guarded_until_release() -> None:
    q = InMemoryJobQueue()
    assert q.put("file-1") is True
    # Same id still in flight -> duplicate.
    assert q.put("file-1") is False
    assert q.get(timeout=0.1) == "file-1"
    # Still marked in flight after pop, until released.
    assert q.put("file-1") is False
    q.release("file-1")
    assert q.put("file-1") is True


def test_priority_order_then_fifo_within_priority() -> None:
    q = InMemoryJobQueue()
    q.put("low-a", priority=10)
    q.put("normal-a", priority=0)
    q.put("normal-b", priority=0)
    q.put("low-b", priority=10)

    # Lower priority value first; FIFO within the same priority band.
    assert q.get(timeout=0.1) == "normal-a"
    assert q.get(timeout=0.1) == "normal-b"
    assert q.get(timeout=0.1) == "low-a"
    assert q.get(timeout=0.1) == "low-b"


def test_get_returns_none_on_timeout() -> None:
    q = InMemoryJobQueue()
    assert q.get(timeout=0.05) is None


def test_requeue_readds_without_clearing_dedup() -> None:
    q = InMemoryJobQueue()
    assert q.put("file-1", priority=0) is True
    assert q.get(timeout=0.1) == "file-1"
    # Retry path: re-add without releasing the dedup marker.
    q.requeue("file-1", priority=11)
    assert q.put("file-1") is False  # still considered in flight
    assert q.get(timeout=0.1) == "file-1"
    q.release("file-1")
    assert q.put("file-1") is True


def test_create_job_queue_defaults_to_memory() -> None:
    q = create_job_queue("test-default")
    assert isinstance(q, InMemoryJobQueue)


def test_create_job_queue_falls_back_to_memory_when_redis_unreachable(monkeypatch) -> None:
    # Request a Redis backend but point at a refused port: the factory must
    # degrade gracefully to the in-memory queue instead of failing startup.
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")
    q = create_job_queue("test-fallback")
    assert isinstance(q, InMemoryJobQueue)
