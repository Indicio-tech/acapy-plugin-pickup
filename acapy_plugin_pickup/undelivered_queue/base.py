"""Abstract Base Class for both the In-Memory and Redis Persisted queues."""

from abc import ABC, abstractmethod
from hashlib import sha256
from typing import Iterable, List, Optional

from base58 import b58encode


class UndeliveredQueueError(Exception):
    """Generic error for undelivered queue."""


class UndeliveredQueue(ABC):
    """Interface for undelivered message queue."""

    @abstractmethod
    async def add_message(self, recipient_key: str, msg: bytes) -> None:
        """Add an OutboundMessage to delivery queue."""

    @abstractmethod
    async def has_message_for_key(self, recipient_key: str) -> bool:
        """Check for queued messages by key."""

    @abstractmethod
    async def message_count_for_key(self, recipient_key: str) -> int:
        """Count of queued messages by key."""

    @abstractmethod
    async def get_messages_for_key(
        self, recipient_key: str, count: Optional[int] = None
    ) -> List[bytes]:
        """Return messages for the key up to the count specified."""

    @abstractmethod
    async def inspect_all_messages_for_key(self, recipient_key: str) -> List[bytes]:
        """Return all messages for key."""

    @abstractmethod
    async def remove_messages_for_key(
        self, recipient_key: str, msg_idents: Iterable[bytes]
    ):
        """Remove specified message from queue for key."""


def message_id_for_outbound(msg: bytes) -> bytes:
    """Return a hash of an OutboundMessage to be used as the message identifier."""
    return b58encode(
        sha256(msg.encode("utf-8") if isinstance(msg, str) else msg).digest()
    )
