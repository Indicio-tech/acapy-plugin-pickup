"""Pickup Protocol."""

import logging
import json
from typing import AsyncGenerator, Optional, List, Set, cast

from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
from aries_cloudagent.transport.inbound.delivery_queue import (
    DeliveryQueue,
    QueuedMessage,
)
from aries_cloudagent.transport.inbound.manager import InboundTransportManager
from aries_cloudagent.transport.inbound.session import InboundSession
from aries_cloudagent.transport.outbound.message import OutboundMessage
from aries_cloudagent.transport.wire_format import BaseWireFormat

from .acapy import AgentMessage
from .acapy.error import HandlerException
from .valid import ISODateTime

LOGGER = logging.getLogger(__name__)
PROTOCOL = "https://didcomm.org/messagepickup/2.0"


class StatusRequest(AgentMessage):
    """StatusRequest message."""

    message_type = f"{PROTOCOL}/status-request"

    recipient_key: Optional[str] = None

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle StatusRequest message."""
        if not self.transport or self.transport.return_route != "all":
            raise HandlerException(
                "StatusRequest must have transport decorator with return "
                "route set to all"
            )
            
        manager = context.inject(InboundTransportManager)
        assert manager
        count = manager.undelivered_queue.message_count_for_key(
            context.message_receipt.sender_verkey
        )
        response = Status(message_count=count)
        response.assign_thread_from(self)
        await responder.send_reply(response)


class Status(AgentMessage):
    """Status message."""

    message_type = f"{PROTOCOL}/status"

    message_count: int
    recipient_key: Optional[str] = None
    duration_waited: Optional[int] = None
    newest_time: Optional[ISODateTime] = None
    oldest_time: Optional[ISODateTime] = None
    total_size: Optional[int] = None


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

        if queue.has_message_for_key(key):
            session = self.determine_session(manager, key)
            if session is None:
                LOGGER.warning("No session available to deliver messages as requested")
                return

            returned_count = 0
            async with context.session() as profile_session:

                for msg in get_messages_for_key(queue, key):
                    
                    recipient_key = msg.target_list[0].recipient_keys or context.message_receipt.recipient_verkey
                    routing_keys = msg.target_list[0].routing_keys or []
                    sender_key = msg.target_list[0].sender_key or key

                    # Depending on send_outbound() implementation, there is a race condition with the timestamp
                    # When ACA-Py is under load, there is a potential for this encryption to not match the actual encryption
                    # TODO: update ACA-Py to store all messages with an encrypted payload 
                    msg.enc_payload = await wire_format.encode_message(profile_session, msg.payload, 
                    recipient_key, routing_keys, sender_key)

                    if session.accept_response(msg):
                        returned_count += 1
                    else:
                        LOGGER.warning(
                            "Failed to return message to session when we were "
                            "expecting it would work"
                        )
                    if returned_count >= self.limit:
                        break
            return
        
        count = manager.undelivered_queue.message_count_for_key(
            context.message_receipt.sender_verkey
        )
        response = Status(message_count=count)
        response.assign_thread_from(self)
        await responder.send_reply(response)


# This is the start of a message updating the Live Delivery status
# Will require a deeper analysis of ACA-Py to fully implement
class LiveDeliveryChange(AgentMessage):
    """Live Delivery Change message."""

    message_type = f"{PROTOCOL}/live-delivery-change"
    live_delivery: bool = False

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle LiveDeliveryChange message"""
        return await super().handle(context, responder)


class MessagesReceived(AgentMessage):
    """MessageReceived acknowledgement message."""

    message_type = f"{PROTOCOL}/messages-received"
    message_tag_list: Set[str]

    @staticmethod
    def determine_session(manager: InboundTransportManager, key: str):
        """Determine the session associated with the given key."""
        for session in manager.sessions.values():
            session = cast(InboundSession, session)
            if key in session.reply_verkeys:
                return session
        return None

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
            remove_message_by_tag_list(queue, key, self.message_tag_list)

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
        if queued_message.msg.enc_payload is None or json.loads(queued_message.msg.enc_payload)["tag"] not in tag_list
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
