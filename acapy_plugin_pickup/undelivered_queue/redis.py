"""Persisted Queue using Redis for undelivered messages."""

import logging
import time
from datetime import timedelta
from typing import Iterable, List, Optional, cast

from redis import asyncio as aioredis

from .base import UndeliveredQueue, UndeliveredQueueError

LOGGER = logging.getLogger(__name__)


class RedisUndeliveredQueue(UndeliveredQueue):
    """Redis Undelivered Queue.

    Stores undelivered messages in Redis.

    To support expiry of messages, the message queue is implemented in the
    following manner:

        messages are stored at db[sha(message.payload)]
        queue is stored db[recipient_key] where the value is a list of
            sha(message.payload)

        msg_queue is receipient_key = SortedSet[Hashed(OutboundMessage.enc_payload)]
        messages is Dict[
            f"recipient_key:Hashed(OutboundMessage.enc_payload)",
            serialized(OutboundMessage)
        ]

        For example, suppose the following:
            msg_queue [1, 2, 3, 4, 5]

        if msgs 1, 2, 3 are expired
        then
            msgs[1] == None
            msgs[2] == None
            msgs[3] == None
            msgs[4] == Some
            msgs[5] == Some
    """

    def __init__(
        self, redis: aioredis.Redis, ttl_seconds: Optional[int] = None
    ) -> None:
        """Initialize an instance of PersistenceQueue.

        This uses an in memory structure to queue messages,
        though the active Redis server prevents losing
        the queue should your machine turn off.
        """
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("Time to live must be a positive integer")
        self.queue_by_key = redis  # Queue of messages and corresponding keys
        self.ttl_seconds = ttl_seconds or 60 * 60 * 24 * 3  # three days

    async def add_message(self, recipient_key: str, msg: bytes):
        """Add an OutboundMessage encrypted payload to delivery queue.

        The message is added once per recipient key.

        Args:
            recipient_key: The recipient key of the connected agent
            msg: The enc_payload to add
        """

        msg_loaded = msg

        msg_ident = self.ident_from_message(msg=msg_loaded)
        msg_score = time.time()

        await self.queue_by_key.zadd(recipient_key, {msg_ident: msg_score}, nx=True)
        await self.queue_by_key.expire(
            recipient_key, timedelta(seconds=self.ttl_seconds)
        )
        await self.queue_by_key.setex(
            msg_ident, timedelta(seconds=self.ttl_seconds), msg_loaded
        )

    async def has_message_for_key(self, recipient_key: str):
        """Check for queued messages by key.

        Args:
            recipient_key: The key to use for lookup
        """
        await self._expire_helper(recipient_key)
        count: int = await self.queue_by_key.zcard(recipient_key)
        return bool(count)

    async def message_count_for_key(self, recipient_key: str):
        """Count of queued messages by key.

        Args:
            recipient_key: The key to use for lookup
        """

        await self._expire_helper(recipient_key)
        count: int = await self.queue_by_key.zcard(recipient_key)
        return count

    async def get_messages_for_key(
        self, recipient_key: str, count: Optional[int] = None
    ) -> List[bytes]:
        """Return a number of messages for a key.

        Args:
            recipient_key: The key to use for lookup
            count: the number of messages to return
        """
        if count is None:
            count = 0

        await self._expire_helper(recipient_key)

        msg_idents: List[bytes] = await self.queue_by_key.zrange(
            recipient_key, 0, count - 1
        )
        msgs = []
        if msg_idents:
            msgs = cast(List[Optional[bytes]], await self.queue_by_key.mget(msg_idents))

        return self._validate_retrieved_message_content_list(msgs)

    async def remove_messages_for_key(
        self, recipient_key: str, msg_idents: Iterable[bytes]
    ):
        """Remove specified message from queue for key.

        Args:
            recipient_key: The key to use for lookup
            msgs: Either (1) the message to remove from the queue
                  or (2) the hash (as described in the above function)
                  of the message payload, which serves as the identifier
        """
        await self._expire_helper(recipient_key)
        known_msg_idents = set(await self.queue_by_key.zrange(recipient_key, 0, -1))
        intersection = known_msg_idents & set(msg_idents)
        if intersection:
            await self.queue_by_key.zrem(recipient_key, *intersection)
            await self.queue_by_key.delete(*intersection)

    async def _expire_helper(self, recipient_key: str):
        """Remove expired msg idents from queue."""
        msg_idents = await self.queue_by_key.zrange(
            recipient_key,
            0,
            (time.time() - self.ttl_seconds),  # pyright: ignore
            byscore=True,
        )
        if msg_idents:
            await self.queue_by_key.zrem(recipient_key, *msg_idents)

    def _validate_retrieved_message_content_list(
        self, msgs: List[Optional[bytes]]
    ) -> List[bytes]:
        """Validate retrieved messages."""
        if [msg for msg in msgs if msg is None]:
            raise UndeliveredQueueError(
                "At least one of many retrieved messages was None"
            )

        return cast(List[bytes], msgs)
