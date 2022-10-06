"""In-Memory queue for undelivered messages."""

from typing import List, Union

from aries_cloudagent.transport.outbound.message import OutboundMessage

from .base import UndeliveredQueue, message_id_for_outbound


class InMemoryQueue(UndeliveredQueue):
    """In memory undelivered queue.

    Manages undelivered messages.
    """

    def __init__(self) -> None:
        """Initialize an instance of InMemoryQueue.

        This uses an in memory structure to queue messages.
        """

        self.queue_by_key: dict[str, List[OutboundMessage]] = {}

    async def add_message(self, msg: OutboundMessage):
        """Add an OutboundMessage to delivery queue.

        The message is added once per recipient key
        Args:
            msg: The OutboundMessage to add
        """
        keys: List[str] = []
        if msg.target:
            keys.extend(msg.target.recipient_keys)
        if msg.reply_to_verkey:
            keys.append(msg.reply_to_verkey)

        recipient_key = keys[0]
        if recipient_key not in self.queue_by_key:
            self.queue_by_key[recipient_key] = []
        self.queue_by_key[recipient_key].append(msg)

    async def has_message_for_key(self, key: str):
        """Check for queued messages by key.

        Args:
            key: The key to use for lookup
        """
        if key in self.queue_by_key and len(self.queue_by_key[key]):
            return True
        return False

    async def message_count_for_key(self, key: str):
        """Count of queued messages by key.

        Args:
            key: The key to use for lookup
        """
        if key in self.queue_by_key:
            return len(self.queue_by_key[key])
        else:
            return 0

    async def get_messages_for_key(self, key: str, count: int) -> List[OutboundMessage]:
        """Return a matching message.

        Args:
            key: The key to use for lookup
            count: the number of messages to return
        """

        if key in self.queue_by_key:
            msgs = [msg for msg in self.queue_by_key[key][0:count]]
            return msgs
        return []

    async def inspect_all_messages_for_key(self, key: str):
        """Return all messages for key.

        Args:
            key: The key to use for lookup
        """
        return [msg for msg in self.queue_by_key[key]]

    async def remove_messages_for_key(
        self, key: str, msgs: List[Union[OutboundMessage, str]]
    ):
        """Remove specified message from queue for key.

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
