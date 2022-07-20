"""Status Request and Status messages for the Pickup Protocol."""

import logging
from typing import Optional

from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder

from protocol.delivery import UndeliveredInterface

from ..acapy import AgentMessage
from ..acapy.error import HandlerException
from ..valid import ISODateTime

LOGGER = logging.getLogger(__name__)
PROTOCOL = "https://didcomm.org/messagepickup/2.0"


class StatusRequest(AgentMessage):
    """StatusRequest message."""

    message_type = f"{PROTOCOL}/status-request"

    recipient_key: Optional[str] = None

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle status request message."""
        if not self.transport or self.transport.return_route != "all":
            raise HandlerException(
                "StatusRequest must have transport decorator with return "
                "route set to all"
            )
        recipient_key = self.recipient_key
        queue = context.inject(UndeliveredInterface)
        count = queue.message_count_for_key(
            recipient_key or context.message_receipt.sender_verkey
        )
        response = Status(message_count=count, recipient_key=recipient_key)
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
    live_mode: Optional[bool] = None
