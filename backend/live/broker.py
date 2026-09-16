"""
Live broker for real-time SSE event streaming (Sprint 5 Live Cockpit).

Single-instance Render is the current reality — `InProcessAsyncBroker` maintains
asyncio queues per connected subscriber.

SCALING SWAP:
In a multi-worker deployment (e.g. Render with multiple Web instances or background
workers), swap `InProcessAsyncBroker` with `RedisLiveBroker`:
- When publishing: `redis.publish("live:events", json.dumps({"event": event_type, "data": data}))`
- When subscribing: worker listens to the Redis channel via `pubsub.listen()` and forwards
  to local SSE subscriber queues.
Because consumers use `LiveBroker.publish_sync` and `LiveBroker.subscribe`, this swap is
a clean drop-in without touching any call sites in ConversationService or CampaignEngine.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LiveBroker(ABC):
    @abstractmethod
    async def subscribe(self) -> asyncio.Queue:
        """Create and register a new event queue for an SSE subscriber."""
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unregister an SSE subscriber queue."""
        raise NotImplementedError

    @abstractmethod
    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event asynchronously."""
        raise NotImplementedError

    @abstractmethod
    def publish_sync(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event from synchronous application code."""
        raise NotImplementedError


class InProcessAsyncBroker(LiveBroker):
    def __init__(self, max_queue_size: int = 100):
        self._subscribers: set[asyncio.Queue] = set()
        self._max_queue_size = max_queue_size

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._subscribers.add(queue)
        logger.debug("New live subscriber registered. Total: %d", len(self._subscribers))
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)
        logger.debug("Live subscriber unregistered. Remaining: %d", len(self._subscribers))

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        self.publish_sync(event_type, data)

    def publish_sync(self, event_type: str, data: dict[str, Any]) -> None:
        if not self._subscribers:
            return

        payload = {"event": event_type, "data": data}
        dead_queues = set()

        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop oldest event if subscriber is slow to keep memory bounded
                try:
                    queue.get_nowait()
                    queue.put_nowait(payload)
                except Exception:
                    dead_queues.add(queue)
            except Exception:
                dead_queues.add(queue)

        for dq in dead_queues:
            self._subscribers.discard(dq)


_broker_instance: Optional[LiveBroker] = None


def get_live_broker() -> LiveBroker:
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = InProcessAsyncBroker()
    return _broker_instance


def set_live_broker(broker: Optional[LiveBroker]) -> None:
    """Useful in tests to isolate broker state."""
    global _broker_instance
    _broker_instance = broker
