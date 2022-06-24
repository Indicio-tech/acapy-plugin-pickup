"""Delivery Request and wrapper message for Pickup Protocol."""

from abc import ABC, abstractmethod
from redis import asyncio as aioredis
import copy
import time
from datetime import timedelta
from hashlib import sha256
import json
import logging
from typing import List, Optional, Sequence, Set, cast, Dict, Any

from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
from aries_cloudagent.transport.inbound.manager import InboundTransportManager
from aries_cloudagent.transport.inbound.session import InboundSession
from aries_cloudagent.transport.outbound.message import OutboundMessage
from aries_cloudagent.transport.wire_format import BaseWireFormat
from pydantic import Field
from typing_extensions import Annotated

from ..acapy import AgentMessage, Attach
from ..acapy.error import HandlerException
from .status import Status

LOGGER = logging.getLogger(__name__)
PROTOCOL = "https://didcomm.org/messagepickup/2.0"


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


def msg_deserialize(value: dict) -> OutboundMessage:
    """Deserialize outbound message object."""
    value = copy.deepcopy(value)
    if "target" in value:
        value["target"] = ConnectionTarget.deserialize(value["target"])

    if "target_list" in value and value["target_list"]:
        value["target_list"] = [
            ConnectionTarget.deserialize(target) for target in value["target_list"]
        ]

    return OutboundMessage(**value)


class DeliveryRequest(AgentMessage):
    """DeliveryRequest message."""

    message_type = f"{PROTOCOL}/delivery-request"

    limit: int
    recipient_key: Optional[str] = None

    @staticmethod
    def determine_session(manager: InboundTransportManager, key: str):
        """Determine the session associated with the given key."""
        for session in manager.sessions.values():
            session = cast(InboundSession, session)
            if key in session.reply_verkeys:
                return session
        return None

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle DeliveryRequest message."""
        if not self.transport or self.transport.return_route != "all":
            raise HandlerException(
                "DeliveryRequest must have transport decorator with return "
                "route set to all"
            )

        wire_format = context.inject(BaseWireFormat)
        manager = context.inject(InboundTransportManager)
        assert manager
        queue = manager.undelivered_queue
        key = context.message_receipt.sender_verkey
        message_attachments = []

        if queue.has_message_for_key(key):
            session = self.determine_session(manager, key)
            if session is None:
                LOGGER.warning("No session available to deliver messages as requested")
                return

            returned_count = 0
            async with context.session() as profile_session:

                for msg in get_messages_for_key(queue, key):

                    recipient_key = (
                        msg.target_list[0].recipient_keys
                        or context.message_receipt.recipient_verkey
                    )
                    routing_keys = msg.target_list[0].routing_keys or []
                    sender_key = msg.target_list[0].sender_key or key

                    # This scenario is rare; a message will almost always have an
                    # encrypted payload. The only time it won't is if we're sending a
                    # message from the mediator itself, rather than forwarding a message
                    # from another agent.
                    # TODO: update ACA-Py to store all messages with an
                    # encrypted payload
                    if not msg.enc_payload:
                        msg.enc_payload = await wire_format.encode_message(
                            profile_session,
                            msg.payload,
                            recipient_key,
                            routing_keys,
                            sender_key,
                        )

                    attached_msg = Attach.data_base64(
                        ident=json.loads(msg.enc_payload)["tag"], value=msg.enc_payload
                    )
                    message_attachments.append(attached_msg)
                    returned_count += 1

                    if returned_count >= self.limit:
                        break

            response = Delivery(message_attachments=message_attachments)
            response.assign_thread_from(self)
            await responder.send_reply(response)

        else:
            response = Status(recipient_key=self.recipient_key, message_count=0)
            response.assign_thread_from(self)
            await responder.send_reply(response)


class Delivery(AgentMessage):
    """Message wrapper for delivering messages to a recipient."""

    class Config:
        allow_population_by_field_name = True

    message_type = f"{PROTOCOL}/delivery"

    recipient_key: Optional[str] = None
    message_attachments: Annotated[
        Sequence[Attach], Field(description="Attached messages", alias="~attach")
    ]


class UndeliveredInterface(ABC):
    """Interface for undelivered message queue."""

    @abstractmethod
    async def add_message(self, msg: OutboundMessage):
        """Add an OutboundMessage to delivery queue."""

    @abstractmethod
    async def has_message_for_key(self, key: str):
        """Check for queued messages by key."""

    @abstractmethod
    async def message_count_for_key(self, key: str):
        """Count of queued messages by key."""

    @abstractmethod
    async def get_one_message_for_key(self, key: str):
        """Remove and return a matching message."""

    @abstractmethod
    async def inspect_all_messages_for_key(self, key: str):
        """Return all messages for key."""

    @abstractmethod
    async def remove_message_for_key(self, key: str, msg: OutboundMessage):
        """Remove specified message from queue for key."""

    @abstractmethod
    async def flush_messages(self, key: str) -> Sequence[OutboundMessage]:
        """Clear and return messages for key."""


class RedisPersistedQueue(UndeliveredInterface):
    """PersistedQueue Class

    Manages undelivered messages.

    To support expiry of messages, the message queue is implemented in the
    following manner:

        messages are stored at db[sha(message.payload)]
        queue is stored db[recipient_key] where the value is a list of
            sha(message.payload)
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        """
        Initialize an instance of PersistenceQueue.
        This uses an in memory structure to queue messages,
        though the active Redis server prevents losing
        the queue should your machine turn off.
        """

        self.queue_by_key = redis  # Queue of messages and corresponding keys
        self.ttl_seconds = 604800  # one week
        self.exmessage_seconds = 259200  # three days

    async def add_message(self, key: str, msg: OutboundMessage):
        """
        Add an OutboundMessage to delivery queue.
        The message is added once per recipient key
        Args:
            key: The recipient key of the connected
            agent
            msg: The OutboundMessage to add
        """

        msg_key = sha256(
            msg.payload.encode("utf-8") if isinstance(msg.payload, str) else msg.payload
        ).digest()

        await self.queue_by_key.rpush(key, msg_key)
        await self.queue_by_key.expire(key, timedelta(seconds=self.ttl_seconds))
        await self.queue_by_key.setex(
            msg_key,
            timedelta(seconds=self.exmessage_seconds),
            json.dumps(msg_serialize(msg)),
        )

    async def has_message_for_key(self, key: str):
        """
        Check for queued messages by key.
        Args:
            key: The key to use for lookup
        """
        msg_key = await self.queue_by_key.lindex(key, 0)
        return bool(msg_key)

    async def message_count_for_key(self, key: str):
        """
        Count of queued messages by key.
        Args:
            key: The key to use for lookup
        """
        return await self.queue_by_key.llen(key)

    async def get_one_message_for_key(self, key: str):
        """
        Remove and return a matching message.
        Args:
            key: The key to use for lookup
        """
        msg_key = await self.queue_by_key.lpop(key)
        msg = None

        while msg is None and msg_key is not None:
            msg = await self.queue_by_key.get(msg_key)
            await self.queue_by_key.delete(msg_key)
            if msg is None:
                msg_key = await self.queue_by_key.lpop(key)

        return msg_deserialize(json.loads(msg))

    async def inspect_all_messages_for_key(self, key: str):
        """
        Return all messages for key.
        Args:
            key: The key to use for lookup
        """
        msg_keys = await self.queue_by_key.lrange(key, 0, -1)
        if msg_keys:
            msgs = [await self.queue_by_key.get(msg_key) for msg_key in msg_keys]
            msgs = [msg_deserialize(json.loads(msg)) for msg in msgs if msg]
            return msgs
        return []

    async def remove_message_for_key(self, key: str, msg: OutboundMessage):
        """
        Remove specified message from queue for key.
        Args:
            key: The key to use for lookup
            msg: The message to remove from the queue
        """
        msg_key = sha256(
            msg.payload.encode("utf-8") if isinstance(msg.payload, str) else msg.payload
        ).digest()

        await self.queue_by_key.lrem(key, 1, msg_key)
        await self.queue_by_key.delete(msg_key)

    async def flush_messages(self, key: str) -> Sequence[OutboundMessage]:
        messages = await self.queue_by_key.lrange(key, 0, -1)
        await self.queue_by_key.delete(key)
        return messages


class QueuedMessage:
    """
    Wrapper Class for queued messages.

    Allows tracking Metadata.
    """

    def __init__(self, msg: OutboundMessage):
        """
        Create Wrapper for queued message.

        Automatically sets timestamp on create.
        """
        self.msg = msg
        self.timestamp = time.time()

    def older_than(self, compare_timestamp: float) -> bool:
        """
        Age Comparison.

        Allows you to test age as compared to the provided timestamp.

        Args:
            compare_timestamp: The timestamp to compare
        """
        return self.timestamp < compare_timestamp


class DeliveryQueue:
    """
    DeliveryQueue class.
    Manages undelivered messages.
    """

    def __init__(self) -> None:
        """
        Initialize an instance of DeliveryQueue.
        This uses an in memory structure to queue messages.
        """

        self.queue_by_key = {}
        self.ttl_seconds = 604800  # one week

    def expire_messages(self, ttl=None):
        """
        Expire messages that are past the time limit.
        Args:
            ttl: Optional. Allows override of configured ttl
        """

        ttl_seconds = ttl or self.ttl_seconds
        horizon = time.time() - ttl_seconds
        for key in self.queue_by_key.keys():
            self.queue_by_key[key] = [
                wm for wm in self.queue_by_key[key] if not wm.older_than(horizon)
            ]

    def add_message(self, msg: OutboundMessage):
        """
        Add an OutboundMessage to delivery queue.
        The message is added once per recipient key
        Args:
            msg: The OutboundMessage to add
        """
        keys = set()
        if msg.target:
            keys.update(msg.target.recipient_keys)
        if msg.reply_to_verkey:
            keys.add(msg.reply_to_verkey)
        wrapped_msg = QueuedMessage(msg)
        for recipient_key in keys:
            if recipient_key not in self.queue_by_key:
                self.queue_by_key[recipient_key] = []
            self.queue_by_key[recipient_key].append(wrapped_msg)

    def has_message_for_key(self, key: str):
        """
        Check for queued messages by key.
        Args:
            key: The key to use for lookup
        """
        if key in self.queue_by_key and len(self.queue_by_key[key]):
            return True
        return False

    def message_count_for_key(self, key: str):
        """
        Count of queued messages by key.
        Args:
            key: The key to use for lookup
        """
        if key in self.queue_by_key:
            return len(self.queue_by_key[key])
        else:
            return 0

    def get_one_message_for_key(self, key: str):
        """
        Remove and return a matching message.
        Args:
            key: The key to use for lookup
        """
        if key in self.queue_by_key:
            return self.queue_by_key[key].pop(0).msg

    def inspect_all_messages_for_key(self, key: str):
        """
        Return all messages for key.
        Args:
            key: The key to use for lookup
        """
        if key in self.queue_by_key:
            for wrapped_msg in self.queue_by_key[key]:
                yield wrapped_msg.msg

    def remove_message_for_key(self, key: str, msg: OutboundMessage):
        """
        Remove specified message from queue for key.
        Args:
            key: The key to use for lookup
            msg: The message to remove from the queue
        """
        if key in self.queue_by_key:
            for wrapped_msg in self.queue_by_key[key]:
                if wrapped_msg.msg == msg:
                    self.queue_by_key[key].remove(wrapped_msg)
                    if not self.queue_by_key[key]:
                        del self.queue_by_key[key]
                    break  # exit processing loop


class MessagesReceived(AgentMessage):
    """MessageReceived acknowledgement message."""

    message_type = f"{PROTOCOL}/messages-received"
    message_id_list: Set[str]

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle MessageReceived message."""
        if not self.transport or self.transport.return_route != "all":
            raise HandlerException(
                "MessageReceived must have transport decorator with return "
                "route set to all"
            )

        manager = context.inject(InboundTransportManager)
        assert manager
        queue = manager.undelivered_queue
        key = context.message_receipt.sender_verkey

        if queue.has_message_for_key(key):
            remove_message_by_tag_list(queue, key, self.message_id_list)

        response = Status(message_count=queue.message_count_for_key(key))
        response.assign_thread_from(self)
        await responder.send_reply(response)


def remove_message_by_tag(queue: DeliveryQueue, recipient_key: str, tag: str):
    """Remove a message from a recipient's queue by tag.

    Tag corresponds to a value in the encrypted payload which is unique for
    each message.
    """
    return remove_message_by_tag_list(queue, recipient_key, {tag})


def remove_message_by_tag_list(
    queue: DeliveryQueue, recipient_key: str, tag_list: Set[str]
):

    # For debugging, logs the contents of each message as it's retrieved from the queue
    for i in queue.queue_by_key[recipient_key]:
        LOGGER.debug("%s", i.msg)

    if recipient_key not in queue.queue_by_key:
        return
    LOGGER.debug(
        "Removing messages with tags from queue: %s", queue.queue_by_key[recipient_key]
    )
    queue.queue_by_key[recipient_key][:] = [
        queued_message
        for queued_message in queue.queue_by_key[recipient_key]
        if queued_message.msg.enc_payload is None
        or json.loads(queued_message.msg.enc_payload)["tag"] not in tag_list
    ]


def get_messages_for_key(queue: DeliveryQueue, key: str) -> List[OutboundMessage]:
    """
    Return messages for a given key from the queue without removing them.

    Args:
        key: The key to use for lookup
    """
    if key in queue.queue_by_key:
        return [queued.msg for queued in queue.queue_by_key[key]]
    return []
