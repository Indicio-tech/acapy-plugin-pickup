"""Delivery Request and wrapper message for Pickup Protocol."""

import json
import logging
from abc import ABC
from typing import List, Optional, Sequence, Set, cast

from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
from aries_cloudagent.transport.inbound.delivery_queue import DeliveryQueue
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

                    # Depending on send_outbound() implementation, there is a
                    # race condition with the timestamp. When ACA-Py is under
                    # load, there is a potential for this encryption to not
                    # match the actual encryption
                    # TODO: update ACA-Py to store all messages with an
                    # encrypted payload

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
    def expire_messages(self):
        """Expire messages that are past the time limit."""

    @abstractmethod
    def add_message(self, msg: OutboundMessage):
        """Add an OutboundMessage to delivery queue."""

    @abstractmethod
    def has_message_for_key(self, key: str):
        """Check for queued messages by key."""

    @abstractmethod
    def message_count_for_key(self, key: str):
        """Count of queued messages by key."""

    @abstractmethod
    def get_one_message_for_key(self, key: str):
        """Remove and return a matching message."""

    @abstractmethod
    def inspect_all_messages_for_key(self, key: str):
        """Return all messages for key."""

    @abstractmethod
    def remove_message_for_key(self, key: str, msg: OutboundMessage):
        """Remove specified message from queue for key."""


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
