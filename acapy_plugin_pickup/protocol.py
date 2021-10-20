"""Pickup Protocol."""

import logging
import json
from typing import AsyncGenerator, Optional, List, Set, cast

from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
from aries_cloudagent.transport.inbound.delivery_queue import DeliveryQueue
from aries_cloudagent.transport.inbound.manager import InboundTransportManager
from aries_cloudagent.transport.inbound.session import InboundSession

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
        """Handle status request message."""
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

        manager = context.inject(InboundTransportManager)
        assert manager
        queue = manager.undelivered_queue
        key = context.message_receipt.sender_verkey

        if queue.has_message_for_key(key):
            session = self.determine_session(manager, key)
            for _ in range(0, min(self.limit, queue.message_count_for_key(key))):
                msg = get_one_message_for_key_without_pop(queue, key, _)
                if not session.accept_response(msg):
                    LOGGER.warning(
                        "Failed to return message to session when we were "
                        "expecting it would work"
                    )
        else:
            await responder.send(
                Status(message_count=queue.message_count_for_key(key)),
                reply_to_verkey=key,
                to_session_only=True,
            )


# This is the start of a message updating the Live Delivery status
# Will require a deeper analysis of ACA-Py to fully implement
class LiveDeliveryChange(AgentMessage):
    """Live Delivery Change message."""
    message_type = f"{PROTOCOL}/live-delivery-change"
    live_delivery: bool = False

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle LiveDeliveryChange message"""
        return await super().handle(context, responder)


class MessageReceived(AgentMessage):
    """MessageReceived acknowledgement message."""

    message_type =  f"{PROTOCOL}/message-received"
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

        await responder.send(
                Status(message_count=queue.message_count_for_key(key)),
                reply_to_verkey=key,
                to_session_only=True,
            )


def remove_message_by_tag(queue: DeliveryQueue, recipient_key: str,  tag: str):
        """Remove a message from a recipient's queue by tag.
​
        Tag corresponds to a value in the encrypyed payload which is unique for
        each message.
        """
        return remove_message_by_tag_list(queue, recipient_key, {tag})

def remove_message_by_tag_list(queue: DeliveryQueue, 
                                recipient_key: str, 
                                tag_list: Set[str]):        
        if recipient_key not in queue.queue_by_key:
            return
        queue.queue_by_key[recipient_key][:] = [
        queued_message
        for queued_message in queue.queue_by_key[recipient_key]
        if json.loads(queued_message.msg.enc_payload)["tag"] not in tag_list
        ]

def get_one_message_for_key_without_pop(queue: DeliveryQueue, key: str, index: int = 0):
        """
        Return a matching message from the queue without removing it.

        Args:
            key: The key to use for lookup
            index: The index of the message in the list assigned to the key
        """
        if key in queue.queue_by_key:
            return queue.queue_by_key[key][index].msg
