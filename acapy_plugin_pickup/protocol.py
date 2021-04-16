"""Pickup Protocol."""

import logging
from typing import Optional, cast

from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
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
                msg = queue.get_one_message_for_key(key)
                if not session.accept_response(msg):
                    LOGGER.warning(
                        "Failed to return message to session when we were "
                        "expecting it would work"
                    )
                    queue.add_message(msg)

        await responder.send(
            Status(message_count=queue.message_count_for_key(key)),
            reply_to_verkey=key,
            to_session_only=True,
        )
