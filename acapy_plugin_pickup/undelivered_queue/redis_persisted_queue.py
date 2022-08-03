"""Persisted Queue using Redis for undelivered messages."""

import copy
import json
import logging
import time
from datetime import timedelta
from typing import Any, Dict, List, Union, Optional

from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.transport.outbound.message import OutboundMessage
from redis import asyncio as aioredis

from .base import UndeliveredInterface, message_id_for_outbound

LOGGER = logging.getLogger(__name__)


def msg_serialize(msg: OutboundMessage) -> Dict[str, Any]:
    """Serialize outbound message object."""
    outbound_dict = {
        prop: getattr(msg, prop)
        for prop in (
            "connection_id",
            "reply_session_id",
            "reply_thread_id",
            "reply_to_verkey",
            "reply_from_verkey",
            "to_session_only",
        )
    }
    outbound_dict["payload"] = (
        msg.payload.decode("utf-8") if isinstance(msg.payload, bytes) else msg.payload
    )
    outbound_dict["enc_payload"] = (
        msg.enc_payload.decode("utf-8")
        if isinstance(msg.enc_payload, bytes)
        else msg.enc_payload
    )
    outbound_dict["target"] = msg.target.serialize() if msg.target else None
    outbound_dict["target_list"] = [
        target.serialize() for target in msg.target_list if target
    ] or None
    return outbound_dict


def msg_deserialize(value: Dict[str, Any]) -> OutboundMessage:
    """Deserialize outbound message object."""
    value = copy.deepcopy(value)
    if "target" in value and value["target"]:
        value["target"] = ConnectionTarget.deserialize(value["target"])

    if "target_list" in value and value["target_list"]:
        value["target_list"] = [
            ConnectionTarget.deserialize(target) for target in value["target_list"]
        ]

    return OutboundMessage(**value)


class RedisPersistedQueue(UndeliveredInterface):
    """PersistedQueue Class

    Manages undelivered messages.

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
        """
        Initialize an instance of PersistenceQueue.
        This uses an in memory structure to queue messages,
        though the active Redis server prevents losing
        the queue should your machine turn off.
        """
        if ttl_seconds <= 0:
            raise ValueError("Time to live must be a positive integer")
        self.queue_by_key = redis  # Queue of messages and corresponding keys
        self.ttl_seconds = ttl_seconds or 60 * 60 * 24 * 3  # three days

    async def add_message(self, msg: OutboundMessage):
        """
        Add an OutboundMessage to delivery queue.
        The message is added once per recipient key
        Args:
            key: The recipient key of the connected
            agent
            msg: The OutboundMessage to add
        """

        keys: List[str] = []
        if msg.target:
            keys.extend(msg.target.recipient_keys)
        if msg.reply_to_verkey:
            keys.append(msg.reply_to_verkey)

        msg_ident = message_id_for_outbound(msg=msg)
        msg_score = time.time()
        serialized_msg = json.dumps(msg_serialize(msg))

        key = keys[0]

        await self.queue_by_key.zadd(key, {msg_ident: msg_score}, nx=True)
        await self.queue_by_key.expire(key, timedelta(seconds=self.ttl_seconds))
        await self.queue_by_key.setex(
            msg_ident,
            timedelta(seconds=self.ttl_seconds),
            serialized_msg,
        )

    async def has_message_for_key(self, key: str):
        """
        Check for queued messages by key.
        Args:
            key: The key to use for lookup
        """
        msg_ident: str = await self.queue_by_key.zrange(key, 0, 0)
        return bool(msg_ident)

    async def message_count_for_key(self, key: str):
        """
        Count of queued messages by key.
        Args:
            key: The key to use for lookup
        """

        await self.expire_helper(key)

        count: int = await self.queue_by_key.zcard(key)
        return count

    async def get_messages_for_key(self, key: str, count: int) -> List[OutboundMessage]:
        """
        Return a number of messages for a key.
        Args:
            key: The key to use for lookup
            count: the number of messages to return
        """

        await self.expire_helper(key)

        msg_idents: str = await self.queue_by_key.zrange(key, 0, count - 1)
        msgs = await self.queue_by_key.mget([msg_ident for msg_ident in msg_idents])

        return [msg_deserialize(json.loads(msg)) for msg in msgs]

    async def inspect_all_messages_for_key(self, key: str):
        """
        Return all messages for key.
        Args:
            key: The key to use for lookup
        """
        msg_idents = await self.queue_by_key.zrange(key, 0, -1)
        if msg_idents:
            msgs = await self.queue_by_key.mget([msg_ident for msg_ident in msg_idents])
            msgs = [msg_deserialize(json.loads(msg)) for msg in msgs if msg]
            return msgs
        return []

    async def remove_messages_for_key(
        self, key: str, msgs: List[Union[OutboundMessage, str]]
    ):
        """
        Remove specified message from queue for key.
        Args:
            key: The key to use for lookup
            msgs: Either (1) the message to remove from the queue
                  or (2) the hash (as described in the above function)
                  of the message payload, which serves as the identifier
        """
        homogenized_msg_idents = [
            message_id_for_outbound(msg) if isinstance(msg, OutboundMessage) else msg
            for msg in msgs
        ]
        if homogenized_msg_idents:
            await self.queue_by_key.zrem(key, *homogenized_msg_idents)
            await self.queue_by_key.delete(*homogenized_msg_idents)

    async def expire_helper(self, key):
        # TODO: This may need alterations when we have the queue refresh conversation
        msg_idents = await self.queue_by_key.zrange(
            key, 0, (time.time() - self.ttl_seconds), byscore=True
        )
        if msg_idents:
            await self.queue_by_key.zrem(key, *msg_idents)
