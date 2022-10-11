"""In-Memory queue for undelivered messages."""

from typing import Iterable, List, Optional

from .base import UndeliveredQueue


class InMemoryQueue(UndeliveredQueue):
    """In memory undelivered queue.

    Manages undelivered messages.
    """

    def __init__(self) -> None:
        """Initialize an instance of InMemoryQueue.

        This uses an in memory structure to queue messages.
        """
        self.queue_by_key: dict[str, List[bytes]] = {}

    async def add_message(self, recipient_key: str, msg: bytes):
        """Add an OutboundMessage to delivery queue.

        The message is added once per recipient key
        Args:
            msg: The OutboundMessage to add
        """
        if recipient_key not in self.queue_by_key:
            self.queue_by_key[recipient_key] = []
        self.queue_by_key[recipient_key].append(msg)

    async def has_message_for_key(self, recipient_key: str):
        """Check for queued messages by key.

        Args:
            key: The key to use for lookup
        """
        return (
            recipient_key
            and self.queue_by_key
            and len(self.queue_by_key[recipient_key])
        )

    async def message_count_for_key(self, recipient_key: str):
        """Count of queued messages by key.

        Args:
            key: The key to use for lookup
        """
        if recipient_key in self.queue_by_key:
            return len(self.queue_by_key[recipient_key])
        return 0

    async def get_messages_for_key(
        self, recipient_key: str, count: Optional[int] = None
    ) -> List[bytes]:
        """Return a matching message.

        Args:
            key: The key to use for lookup
            count: the number of messages to return
        """
        msgs = []
        if recipient_key in self.queue_by_key:
            count = (
                count if count is not None else len(self.queue_by_key[recipient_key])
            )
            msgs = [msg for msg in self.queue_by_key[recipient_key][:count]]

        return msgs

    async def remove_messages_for_key(
        self, recipient_key: str, msg_idents: Iterable[bytes]
    ):
        """Remove specified message from queue for key.

        Args:
            key: The key to use for lookup
            msgs: The message to remove from the queue, or the hashes thereof
        """
        if recipient_key in self.queue_by_key:
            self.queue_by_key[recipient_key][:] = [
                queued_message
                for queued_message in self.queue_by_key[recipient_key]
                if self.ident_from_message(queued_message) not in msg_idents
            ]
