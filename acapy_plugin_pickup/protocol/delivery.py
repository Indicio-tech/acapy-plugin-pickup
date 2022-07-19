"""Delivery Request and wrapper message for Pickup Protocol."""

import copy
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import timedelta
from hashlib import sha256
from typing import Any, Dict, List, Optional, Sequence, Set, Union, cast

from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
from aries_cloudagent.transport.inbound.manager import InboundTransportManager
from aries_cloudagent.transport.inbound.session import InboundSession
from aries_cloudagent.transport.outbound.message import OutboundMessage
from aries_cloudagent.transport.wire_format import BaseWireFormat
from base58 import b58encode
from pydantic import Field
from redis import asyncio as aioredis
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
    if "target" in value and value["target"]:
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
        queue = context.inject(UndeliveredInterface)

        key = context.message_receipt.sender_verkey
        message_attachments = []

        if queue.has_message_for_key(key):

            async with context.session() as profile_session:

                for msg in queue.get_messages_for_key(key=key, count=self.limit):

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
                        ident=message_id_for_outbound(msg), value=msg.enc_payload
                    )
                    message_attachments.append(attached_msg)

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
    async def get_messages_for_key(self, key: str, count: int) -> List[OutboundMessage]:
        """Return messages for the key up to the count specified."""

    @abstractmethod
    async def inspect_all_messages_for_key(self, key: str):
        """Return all messages for key."""

    @abstractmethod
    async def remove_messages_for_key(
        self, key: str, *msgs: Union[OutboundMessage, str]
    ):
        """Remove specified message from queue for key."""


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

    def __init__(self, redis: aioredis.Redis) -> None:
        """
        Initialize an instance of PersistenceQueue.
        This uses an in memory structure to queue messages,
        though the active Redis server prevents losing
        the queue should your machine turn off.
        """

        self.queue_by_key = redis  # Queue of messages and corresponding keys
        self.ttl_seconds = 60 * 60 * 24 * 3  # three days

    async def add_message(self, msg: OutboundMessage):
        """
        Add an OutboundMessage to delivery queue.
        The message is added once per recipient key
        Args:
            key: The recipient key of the connected
            agent
            msg: The OutboundMessage to add
        """

        keys = []
        if msg.target:
            keys.update(msg.target.recipient_keys)
        if msg.reply_to_verkey:
            keys.add(msg.reply_to_verkey)

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
        msg_ident = await self.queue_by_key.zrange(key, 0, 0)
        return bool(msg_ident)

    async def message_count_for_key(self, key: str):
        """
        Count of queued messages by key.
        Args:
            key: The key to use for lookup
        """
        return await self.queue_by_key.zcount(key, 0, -1)

    async def get_messages_for_key(self, key: str, count: int) -> List[OutboundMessage]:
        """
        Return a number of messages for a key.
        Args:
            key: The key to use for lookup
            count: the number of messages to return
        """
        msg_idents = await self.queue_by_key.zrange(key, 0, count)
        msgs = await self.queue_by_key.mget([msg_ident for msg_ident in msg_idents])

        msgs = [msg for msg in msgs if msg is not None]

        expired = [msg for msg in msgs if msg is None]
        await self.queue_by_key.zrem(*expired)

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
        self, key: str, *msgs: Union[OutboundMessage, str]
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
            self.message_id_for_outbound(msg)
            if isinstance(msg, OutboundMessage)
            else msg
            for msg in msgs
        ]
        await self.queue_by_key.zrem(key, *homogenized_msg_idents)
        await self.queue_by_key.delete(
            *[msg_ident for msg_ident in homogenized_msg_idents]
        )


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

    def add_message(self, msg: OutboundMessage):
        """
        Add an OutboundMessage to delivery queue.
        The message is added once per recipient key
        Args:
            msg: The OutboundMessage to add
        """
        keys = []
        if msg.target:
            keys.update(msg.target.recipient_keys)
        if msg.reply_to_verkey:
            keys.add(msg.reply_to_verkey)

        recipient_key = keys[0]
        if recipient_key not in self.queue_by_key:
            self.queue_by_key[recipient_key] = []
        self.queue_by_key[recipient_key].append(msg)

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

    def get_messages_for_key(self, key: str, count: int) -> List[OutboundMessage]:
        """
        Return a matching message.
        Args:
            key: The key to use for lookup
            count: the number of messages to return
        """

        if key in self.queue_by_key:
            msgs = [msg for msg in self.queue_by_key[key][0:count]]
            return msgs

    def inspect_all_messages_for_key(self, key: str):
        """
        Return all messages for key.
        Args:
            key: The key to use for lookup
        """
        if key in self.queue_by_key:
            for msg in self.queue_by_key[key]:
                yield msg

    def remove_messages_for_key(self, key: str, *msgs: Union[OutboundMessage, str]):
        """
        Remove specified message from queue for key.
        Args:
            key: The key to use for lookup
            msgs: The message to remove from the queue, or the hashes thereof
        """

        self.queue_by_key[key][:] = [
            queued_message
            for queued_message in self.queue_by_key[key]
            if queued_message.enc_payload is None
            or message_id_for_outbound(queued_message) not in msgs
        ]


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

        queue = context.inject(UndeliveredInterface)
        key = context.message_receipt.sender_verkey

        if queue.has_message_for_key(key):
            queue.remove_messages_for_key(key=key, msg=self.message_id_list)

        response = Status(message_count=queue.message_count_for_key(key))
        response.assign_thread_from(self)
        await responder.send_reply(response)


def message_id_for_outbound(self, msg: OutboundMessage) -> str:
    return b58encode(
        sha256(
            msg.payload.encode("utf-8")
            if isinstance(msg.enc_payload, str)
            else msg.enc_payload
        ).digest()
    ).decode("utf-8")
