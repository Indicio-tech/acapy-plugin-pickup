"""Abstract Base Class for both the In-Memory and Redis Persisted queues."""

from abc import ABC, abstractmethod
from hashlib import sha256
from typing import List, Union

from aries_cloudagent.transport.outbound.message import OutboundMessage
from base58 import b58encode


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
        self, key: str, msgs: List[Union[OutboundMessage, str]]
    ):
        """Remove specified message from queue for key."""


def message_id_for_outbound(msg: OutboundMessage) -> str:
    """Return a hash of an OutboundMessage to be used as the message identifier."""
    return b58encode(
        sha256(
            msg.enc_payload.encode("utf-8")
            if isinstance(msg.enc_payload, str)
            else msg.enc_payload
        ).digest()
    ).decode("utf-8")
